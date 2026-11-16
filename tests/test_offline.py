"""Offline tests: run with `pytest` (or the Testing panel in VS Code). No network needed."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest  # noqa: E402

from edgar import Filing, cik10, select_for_backfill  # noqa: E402
from part1_check_sources import flag_clauses, recommend  # noqa: E402
from nlp_check import similarity_scores  # noqa: E402
from part15_build_universe import decide_sectors, name_matches, recordkeeping_test  # noqa: E402
from part1_edgar_pull import quarter_start  # noqa: E402
from rss_pull import items_from_feed  # noqa: E402
from web_scrape import text_from_html  # noqa: E402
from gdelt_news import article_rows  # noqa: E402
from segments import (find_instance_name, load_rules, map_segment, member_label,  # noqa: E402
                      segment_revenue)
from text_utils import extract_business_section, html_to_text, split_sentences  # noqa: E402

import json  # noqa: E402

DEFS = {k: v["definition"] for k, v in json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "sector_definitions.json").read_text()).items()}


# ------------------------------------------------------------- EDGAR filing selection
def f(form, filed, period="", items=""):
    return Filing("0000019617", f"0000019617-{filed[2:4]}-{abs(hash((form, filed))) % 10**6:06d}",
                  form, filed, period, "doc.htm", items)


def test_backfill_keeps_twelve_quarters_and_drops_noise():
    filings = []
    for y in (2023, 2024, 2025):
        filings.append(f("10-K", f"{y + 1}-02-20", f"{y}-12-31"))
    for y in (2023, 2024, 2025, 2026):
        for m in ("03-31", "06-30", "09-30"):
            filings.append(f("10-Q", f"{y}-{int(m[:2]) + 2:02d}-05", f"{y}-{m}"))
        for m in ("01", "04", "07", "10"):
            filings.append(f("8-K", f"{y}-{m}-14", items="2.02,9.01"))
    filings += [f("8-K", "2025-05-20", items="5.07"), f("424B2", "2025-03-01"),
                f("13F-HR", "2025-05-12", "2025-03-31"), f("11-K", "2025-06-27", "2024-12-31")]
    picked = select_for_backfill(filings, date(2023, 10, 1), date(2026, 9, 30))
    forms = [p.form for p in picked]
    assert forms.count("10-K") == 3 and forms.count("10-Q") == 9 and forms.count("8-K") == 12
    assert not {"424B2", "13F-HR", "11-K"} & set(forms)
    jan8k = next(p for p in picked if p.form == "8-K" and p.filing_date == "2025-01-14")
    assert jan8k.period_label == "2024Q4"          # January release reports prior Q4


def test_cik_padding():
    assert cik10(19617) == "0000019617" and cik10("0000019617") == "0000019617"


# ------------------------------------------------------------- text handling
def test_business_section_skips_table_of_contents():
    body = "We operate a bank. " * 200
    html = (f"<html><body><p>Item 1. Business ..... 3</p><p>Item 1A. Risk Factors ..... 9</p>"
            f"<p>ITEM 1. BUSINESS</p><p>{body}</p><p>Item 1A. Risk Factors</p><p>Risks...</p></body></html>")
    sec = extract_business_section(html_to_text(html))
    assert sec is not None and sec.count("We operate a bank") == 200


def test_sentence_split():
    assert len(split_sentences("You may not scrape this site. You may read it for personal use.")) == 2


# ------------------------------------------------------------- Part 1 clause flags
TERMS = ("You agree not to use any robot, spider or other automatic device to copy our pages. "
         "Content is for your personal, non-commercial use only. "
         "You may not use content to train a machine learning or AI system. "
         "You may retrieve our RSS feeds. Said content may be emailed to friends.")


def test_clause_flags():
    fl = flag_clauses(TERMS)
    assert fl["automated_access"] and fl["personal_use_only"] and fl["permitted_channels"]
    assert len(fl["ai_training"]) == 1             # "Said"/"emailed" must not match "AI"


def test_recommendations():
    fl = flag_clauses(TERMS)
    assert recommend("manual", "unknown", True, fl).startswith("MANUAL ONLY")
    assert recommend("api", "y", True, fl).startswith("AUTOMATED OK")
    assert recommend("api", "n", True, fl).startswith("EXCLUDE")
    assert recommend("manual", "unknown", False, fl).startswith("EXCLUDE")
    assert recommend("manual", "unknown", True, None).startswith("BLOCKED")


def test_rss_and_atom_metadata_parsing():
    rss = b"""<rss><channel><item><title>AI release</title><link>https://example.com/a</link><pubDate>Today</pubDate><description>Short update</description></item></channel></rss>"""
    atom = b"""<feed xmlns=\"http://www.w3.org/2005/Atom\"><entry><title>AI note</title><link href=\"https://example.com/b\"/><updated>2026-11-05</updated><summary>Summary</summary></entry></feed>"""
    assert items_from_feed(rss) == [{"title": "AI release", "url": "https://example.com/a", "published": "Today", "summary": "Short update"}]
    assert items_from_feed(atom)[0]["url"] == "https://example.com/b"


def test_web_scraper_removes_navigation_and_scripts():
    html = b"<html><head><title>AI page</title><script>ignore()</script></head><body><nav>Menu</nav><main><h1>AI launch</h1><p>We deployed AI.</p></main><footer>Footer</footer></body></html>"
    assert text_from_html(html) == ("AI page", "AI launch\nWe deployed AI.")


def test_gdelt_article_metadata_parsing():
    payload = {"articles": [{"title": "JPM AI update", "url": "https://example.com/news", "seendate": "20261105T120000Z", "domain": "example.com", "language": "English", "sourcecountry": "United States"}]}
    row = article_rows(payload, "jpm", "JPMorgan Chase & Co.", "query")[0]
    assert row["firm_id"] == "jpm" and row["title"] == "JPM AI update" and row["publisher_domain"] == "example.com"


# ------------------------------------------------------------- Part 1.5 NLP
SAMPLES = {
    "bank": ("We are a bank holding company. Our bank takes deposits from consumers and businesses "
             "through branches and ATMs and makes mortgages, credit card and commercial loans. Net interest "
             "income and the allowance for credit losses drive results. The Federal Reserve and FDIC regulate "
             "our capital and liquidity. ") * 20,
    "recordkeeper": ("We provide recordkeeping for 401(k) and 403(b) defined contribution plans. Plan sponsors "
                     "rely on us to administer participant accounts, auto-enrollment and target-date funds for "
                     "millions of plan participants, and we offer retirement income solutions. ") * 20,
    "insurer": ("We underwrite life insurance, annuities and group benefits. We collect premiums, pay claims "
                "and policyholder benefits, hold statutory reserves and use reinsurance, regulated by state "
                "insurance departments. ") * 20,
}


def test_tfidf_ranks_the_right_sector_first():
    scores = similarity_scores(SAMPLES, DEFS, "tfidf")
    top = {fid: max(s, key=s.get) for fid, s in scores.items()}
    assert top == {"bank": "bank", "recordkeeper": "retirement", "insurer": "insurance"}


def test_name_check():
    assert name_matches("T. Rowe Price Group, Inc.", "PRICE T ROWE GROUP INC")
    assert not name_matches("MetLife Inc", "PRUDENTIAL FINANCIAL INC")


# ------------------------------------------------------------- Part 1.5 evidence-based tagging
ROOT = Path(__file__).resolve().parent.parent
RULES = load_rules(ROOT / "data" / "segment_rules.csv")
SIC_MAP = {"6021": {"bank"}, "6282": {"asset_mgmt"}, "6311": {"insurance"}}

INSTANCE = b"""<?xml version="1.0"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
  xmlns:us-gaap="http://fasb.org/us-gaap/2025" xmlns:jpm="http://www.jpmorganchase.com/20251231">
 <xbrli:context id="FY"><xbrli:entity><xbrli:identifier scheme="x">19617</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:context id="FY_PRIOR"><xbrli:entity><xbrli:identifier scheme="x">19617</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period></xbrli:context>
 SEGCTX
 <us-gaap:Revenues contextRef="FY" unitRef="usd" decimals="-6">180000000000</us-gaap:Revenues>
 <us-gaap:Revenues contextRef="FY_PRIOR" unitRef="usd" decimals="-6">170000000000</us-gaap:Revenues>
 SEGFACTS
</xbrli:xbrl>"""
SEGS = {"jpm:ConsumerCommunityBankingMember": 72e9, "jpm:CommercialInvestmentBankMember": 70e9,
        "jpm:AssetWealthManagementMember": 22e9, "jpm:CorporateSegmentMember": 16e9}


def _instance() -> bytes:
    ctx, facts = [], []
    for i, (m, v) in enumerate(SEGS.items()):
        ctx.append(f'<xbrli:context id="S{i}"><xbrli:entity><xbrli:identifier scheme="x">19617</xbrli:identifier>'
                   f'<xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">{m}'
                   f'</xbrldi:explicitMember></xbrli:segment></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01'
                   f'</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>')
        facts.append(f'<us-gaap:Revenues contextRef="S{i}" unitRef="usd" decimals="-6">{v:.0f}</us-gaap:Revenues>')
    return INSTANCE.replace(b"SEGCTX", "".join(ctx).encode()).replace(b"SEGFACTS", "".join(facts).encode())


def test_xbrl_segment_revenue_and_shares():
    sr = segment_revenue(_instance(), "2025-12-31")
    assert sr.concept == "Revenues" and sr.consolidated == 180e9 and len(sr.segments) == 4
    assert round(sr.share("jpm:AssetWealthManagementMember"), 3) == round(22 / 180, 3)


def test_member_labels_and_instance_name():
    assert member_label("jpm:ConsumerCommunityBankingMember") == "Consumer Community Banking"
    assert member_label("jpm:CorporateSegmentMember") == "Corporate"
    assert find_instance_name(["jpm-20251231.htm", "jpm-20251231_htm.xml", "jpm-20251231_cal.xml"]) == "jpm-20251231_htm.xml"


@pytest.mark.parametrize("firm,label,expected", [
    ("jpm", "Consumer Community Banking", {"bank"}),
    ("jpm", "Asset Wealth Management", {"asset_mgmt", "broker_wealth"}),
    ("jpm", "Corporate", set()),
    ("lnc", "Retirement Plan Services", {"retirement"}),
    ("met", "Retirement And Income Solutions", {"insurance"}),     # firm rule: annuities, not recordkeeping
    ("voya", "Wealth Solutions", {"retirement"}),                   # firm rule
    ("pru", "PGIM", {"asset_mgmt"}),
    ("ms", "Institutional Securities", {"broker_wealth"}),
])
def test_segment_rules(firm, label, expected):
    assert map_segment(label, firm, RULES)[0] == expected


def _jpm_evidence(text=""):
    sr = segment_revenue(_instance(), "2025-12-31")
    segs = []
    for m, v in SEGS.items():
        lab = member_label(m)
        sectors, why = map_segment(lab, "jpm", RULES)
        segs.append({"member": m, "label": lab, "revenue": v, "share": sr.share(m), "sectors": sectors,
                     "rule": why, "concept": "Revenues"})
    return {"segments": segs, "sic": "6021", "sic_description": "National Commercial Banks",
            "text": text, "review": []}


def test_jpm_tags_bank_primary_plus_asset_and_wealth():
    tags, primary, review = decide_sectors({"firm_id": "jpm"}, _jpm_evidence("We are a bank. " * 300),
                                           SIC_MAP, 5.0)
    assert primary == "bank"
    assert {t[0] for t in tags} == {"bank", "asset_mgmt", "broker_wealth"}
    assert "retirement" not in {t[0] for t in tags}


def test_small_segment_is_not_tagged():
    ev = _jpm_evidence()
    for g in ev["segments"]:
        if g["label"] == "Asset Wealth Management":
            g["share"] = 0.05
    tags, _, review = decide_sectors({"firm_id": "jpm"}, ev, SIC_MAP, 5.0)
    assert "asset_mgmt" not in {t[0] for t in tags} and any("below 10%" in r for r in review)


def test_single_segment_uses_sic_and_recordkeeping_test():
    text = ("We manage mutual funds. We provide recordkeeping for 401(k) plans and serve plan participants. " * 50)
    ev = {"segments": [], "sic": "6282", "sic_description": "Investment Advice", "text": text, "review": []}
    tags, primary, _ = decide_sectors({"firm_id": "trow"}, ev, SIC_MAP, 5.0)
    assert primary == "asset_mgmt" and {t[0] for t in tags} == {"asset_mgmt", "retirement"}


def test_recordkeeping_needs_the_word_recordkeeping():
    passes, _, _ = recordkeeping_test("Our 401(k) plan matches employee contributions. " * 40, 5.0)
    assert not passes                      # a firm's OWN employee 401(k) is not recordkeeping


def test_manual_tags_flag_missing_citation():
    tags, primary, review = decide_sectors(
        {"firm_id": "vanguard", "manual_sectors": "asset_mgmt;retirement", "manual_evidence": "TO CITE: x"},
        {"review": []}, SIC_MAP, 5.0)
    assert primary == "asset_mgmt" and any("citation" in r for r in review)


def test_quarter_window():
    assert quarter_start(date(2026, 9, 30), 12) == date(2023, 10, 1)
    assert quarter_start(date(2026, 9, 30), 16) == date(2022, 10, 1)


def test_regulatory_recordkeeping_is_not_retirement():
    text = ("Our broker-dealer is subject to SEC recordkeeping and reporting requirements. "
            "We must comply with recordkeeping rules for client communications. ") * 40
    assert not recordkeeping_test(text, 5.0)[0]
