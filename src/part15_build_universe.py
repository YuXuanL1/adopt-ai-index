"""PART 1.5 - Define the firm universe: tag every firm with the sectors it actually belongs to.

Tags come from EVIDENCE, in this order, and every tag records where it came from:

  1. Segments  - the firm's reportable business segments and their full-year revenue,
                 read from the XBRL data in its latest 10-K. Each segment is mapped to
                 sectors with the rules in data/segment_rules.csv. A sector is tagged
                 if its segments are at least 10% of revenue (SEC's own segment test).
  2. SIC code  - for single-segment firms (BlackRock, T. Rowe Price, ...), the sector
                 implied by the SIC code in the firm's SEC record (data/sic_to_sector.csv).
  3. Recordkeeping test - "retirement plan provider" is a business line, not a segment
                 or a SIC code, so we count recordkeeping / 401(k) / plan-participant terms
                 in the 10-K's "Item 1. Business". Above the threshold -> retirement tag.
  4. Manual    - for firms with no 10-K (Vanguard, Fidelity, TIAA, ...) or traits no filing
                 states (fintech/AI-native): manual_sectors in data/firms.csv + a citation.

Primary sector = the sector with the largest revenue share (else the SIC sector).
The team's hand_sectors are kept as an independent CHECK; disagreements are flagged.
Optional: --nlp-check adds NLP-suggested sectors as a second opinion (see nlp_check.py).

Coverage plan: data/sector_plan.csv sets, per sector, a minimum firm count and backfill
depth (retirement is 'deep' by default). The report shows any shortfall, and
part1_edgar_pull.py backfills each firm to the deepest depth among its sectors.

Outputs (outputs/part15/):
  firm_universe.csv   one row per firm: SEC data, sectors, primary sector, evidence,
                      review flags, final_sectors (the team confirms this column)
  firm_segments.csv   every segment found: revenue, share, mapped sectors, rule used
  coverage_report.md  firms per sector vs the plan, disagreements, items to review

Run:
  python src/part15_build_universe.py                  all firms
  python src/part15_build_universe.py --firms jpm      one firm
  python src/part15_build_universe.py --nlp-check      add the NLP second opinion
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from config import DATA, OUTPUTS, user_agent
from segments import find_instance_name, load_rules, map_segment, member_label, segment_revenue
from text_utils import extract_business_section, html_to_text

MATERIALITY = 0.10
RECORDKEEPING = re.compile(
    r"\b(record-?\s?keep\w*|defined[\s-]contribution|401\(k\)|403\(b\)|457\(b\)|plan participants?|"
    r"participant accounts?|auto-?enrol+\w*)\b", re.I)
STOP_NAME_WORDS = {"inc", "corp", "corporation", "co", "company", "companies", "group", "the", "ltd",
                   "llc", "lllp", "lp", "plc", "financial", "of", "and", "de", "mn", "holdings"}


# ------------------------------------------------------------------ small helpers
def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def tagset(cell: str) -> set[str]:
    return {t.strip() for t in (cell or "").split(";") if t.strip()}


def name_matches(ours: str, sec: str) -> bool:
    def toks(x):
        return {t for t in re.findall(r"[a-z0-9]+", x.lower()) if t not in STOP_NAME_WORDS and len(t) > 1}
    return bool(toks(ours) & toks(sec))


PLAN_WORDS = re.compile(r"\b(plans?|401\(k\)|403\(b\)|457\(b\)|participants?|retirement|defined[\s-]contribution)\b", re.I)
RK_WORD = re.compile(r"\brecord-?\s?keep\w*", re.I)


def recordkeeping_test(text: str, threshold: float, min_sentences: int = 2) -> tuple[bool, float, str]:
    """(passes?, terms per 10k words, evidence).

    Passes only if (a) plan terms are dense enough AND (b) at least `min_sentences` sentences
    use "recordkeeping" together with a retirement-plan word. (b) stops banks and brokers,
    whose 10-Ks say "recordkeeping" about regulatory books-and-records rules, from passing.
    """
    from text_utils import split_sentences
    hits = [m.group(0).lower() for m in RECORDKEEPING.finditer(text)]
    density = 10_000 * len(hits) / max(1, len(text.split()))
    plan_rk = sum(1 for s in split_sentences(text) if RK_WORD.search(s) and PLAN_WORDS.search(s))
    top = ", ".join(f"{t} x{n}" for t, n in Counter(hits).most_common(4))
    evidence = (f"{density:.1f} plan terms per 10k words ({top}); {plan_rk} sentences on plan recordkeeping"
                if hits else "no recordkeeping terms")
    return (density >= threshold and plan_rk >= min_sentences), density, evidence


# ------------------------------------------------------------------ evidence for one SEC filer
def sec_evidence(s, firm: dict, rules, sic_map, rk_threshold: float, auto_dir: Path) -> dict:
    from edgar import all_filings, get_submissions, latest
    out = {"sec_name": "", "sic": "", "sic_description": "", "fiscal_year_end": "",
           "segments": [], "segment_source": "", "text": "", "text_source": "", "review": []}
    sub = get_submissions(s, firm["cik"], refresh_days=30)
    out.update(sec_name=sub.get("name", ""), sic=str(sub.get("sic", "")),
               sic_description=sub.get("sicDescription", ""), fiscal_year_end=sub.get("fiscalYearEnd", ""))
    if not name_matches(firm["name"], out["sec_name"]):
        out["review"].append(f"CIK name is '{out['sec_name']}' - check firms.csv")
    filings = all_filings(s, sub, since=date.today() - timedelta(days=3 * 365))

    # 1. segments from the latest 10-K's XBRL instance
    tenk = latest(filings, ["10-K"])
    if tenk and tenk.report_date:
        idx = s.get_json(f"{tenk.folder_url}/index.json")
        inst = find_instance_name([i["name"] for i in idx["directory"]["item"]])
        if inst:
            sr = segment_revenue(s.get(f"{tenk.folder_url}/{inst}"), tenk.report_date)
            out["segment_source"] = f"10-K FY ending {tenk.report_date}: {tenk.index_url}"
            if not sr:
                out["review"].append("no segment revenue found in XBRL - confirm the firm has a single "
                                     "segment (check the 10-K segment note)")
            if sr:
                for member, value in sorted(sr.segments.items(), key=lambda kv: -kv[1]):
                    label = member_label(member)
                    sectors, why = map_segment(label, firm["firm_id"], rules)
                    out["segments"].append({"member": member, "label": label, "revenue": value,
                                            "share": sr.share(member), "sectors": sectors, "rule": why,
                                            "concept": sr.concept})
                    if why.startswith("UNMAPPED"):
                        out["review"].append(f"segment '{label}' has no rule")
        else:
            out["review"].append("no XBRL instance found in latest 10-K")
    else:
        out["review"].append("no 10-K in the last 3 years")

    # text for the recordkeeping test (and the optional NLP check)
    manual = DATA / "descriptions" / f"{firm['firm_id']}.txt"
    if manual.exists():
        out["text"], out["text_source"] = manual.read_text(encoding="utf-8"), f"hand-saved {manual.name}"
    else:
        forms = [f.strip() for f in (firm.get("desc_forms") or "10-K").split(";") if f.strip()]
        doc = latest(filings, forms)
        if doc:
            full = html_to_text(s.get(doc.doc_url))
            biz = extract_business_section(full)
            out["text"] = biz or full[:80_000]
            out["text_source"] = f"{doc.form} {doc.filing_date} {'Item 1' if biz else 'first 80k chars'}: {doc.doc_url}"
            auto_dir.mkdir(parents=True, exist_ok=True)
            (auto_dir / f"{firm['firm_id']}.txt").write_text(f"SOURCE: {out['text_source']}\n\n{out['text']}",
                                                             encoding="utf-8")
    return out


def has_citation(firm: dict) -> bool:
    cite = (firm.get("manual_evidence") or "").strip()
    return bool(cite) and not cite.upper().startswith("TO CITE")


def decide_sectors(firm: dict, ev: dict, sic_map: dict, rk_threshold: float,
                   min_share: dict[str, float] | None = None) -> tuple[list, str, list]:
    """Return ([(sector, evidence, share)], primary sector, review notes).

    min_share: per-sector revenue threshold (data/sector_plan.csv); default MATERIALITY (10%).
    """
    min_share = min_share or {}
    tags: dict[str, list] = {}
    review = list(ev.get("review", []))
    manual_sectors = [t.strip() for t in firm.get("manual_sectors", "").split(";") if t.strip()]

    # 1. material segments
    share_by_sector: Counter = Counter()
    for seg in ev.get("segments", []):
        for sec in seg["sectors"]:
            share_by_sector[sec] += max(seg["share"], 0)
    for sec, share in share_by_sector.items():
        names = [g["label"] for g in ev["segments"] if sec in g["sectors"]]
        threshold = min_share.get(sec, MATERIALITY)
        if share >= threshold and share > 0:
            tags[sec] = [f"segments {', '.join(names)} = {share:.0%} of revenue", share]
        else:
            review.append(f"{sec}: segments {', '.join(names)} only {share:.0%} of revenue "
                          f"(below {threshold:.0%})")

    # 2. single-segment firms: SIC code. SIC is the LEGAL classification; a cited manual tag
    #    (what the firm actually does) replaces it - e.g. BlackRock files under 6211 (brokers).
    sic_sectors = sic_map.get(ev.get("sic", ""), set())
    if not ev.get("segments") and ev.get("sic") and manual_sectors and has_citation(firm):
        if sic_sectors and not sic_sectors <= set(manual_sectors):
            review.append(f"SIC {ev['sic']} ({ev['sic_description']}) implies "
                          f"{', '.join(sorted(sic_sectors))}; replaced by cited manual tag (legal vs functional)")
    elif not ev.get("segments") and ev.get("sic"):
        if sic_sectors:
            for sec in sic_sectors:
                tags.setdefault(sec, [f"single reportable segment; SIC {ev['sic']} {ev['sic_description']}", 1.0])
        else:
            review.append(f"single segment and SIC {ev['sic']} ({ev['sic_description']}) maps to no sector")

    # 3. recordkeeping test
    if ev.get("text"):
        passes, density, evidence = recordkeeping_test(ev["text"], rk_threshold)
        ev["recordkeeping"] = evidence
        if passes and "retirement" not in tags:
            tags["retirement"] = [f"recordkeeping test: {evidence}", 0.0]
            review.append("retirement tag from text test only - confirm the firm keeps plan records")
        if "retirement" in tags and not passes and tags["retirement"][1] and density == 0:
            review.append("retirement segment but no recordkeeping terms - may be annuities, not recordkeeping")

    # 4. manual tags with citations
    for sec in manual_sectors:  # keep order
        cite = firm.get("manual_evidence", "").strip()
        tags.setdefault(sec, [f"manual: {cite or 'NO CITATION'}", 0.0])
        if not has_citation(firm):
            review.append(f"manual tag '{sec}' still needs a citation")

    if not tags:
        review.append("no evidence found - add manual_sectors with a citation")
    ranked = sorted(tags.items(), key=lambda kv: -kv[1][1])
    primary = ranked[0][0] if ranked else ""
    if ranked and ranked[0][1][1] == 0.0 and sic_sectors & set(tags):
        primary = sorted(sic_sectors & set(tags))[0]
    return [(sec, e[0], e[1]) for sec, e in ranked], primary, review


# ------------------------------------------------------------------ main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--firms", nargs="*", help="firm_ids to run (default: all)")
    ap.add_argument("--rk-threshold", type=float, default=5.0,
                    help="recordkeeping terms per 10k words for the retirement tag")
    ap.add_argument("--nlp-check", action="store_true", help="add NLP-suggested sectors as a second opinion")
    ap.add_argument("--nlp-method", choices=["tfidf", "embed"], default="tfidf")
    ap.add_argument("--offline", action="store_true", help="use cached SEC files only")
    ap.add_argument("--no-sec", action="store_true", help="skip SEC entirely (manual tags only)")
    ap.add_argument("--out", default=str(OUTPUTS / "part15"))
    a = ap.parse_args()

    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    firms = read_csv(DATA / "firms.csv")
    if a.firms:
        firms = [f for f in firms if f["firm_id"] in a.firms]
    plan = {r["sector_id"]: r for r in read_csv(DATA / "sector_plan.csv")}
    rules = load_rules(DATA / "segment_rules.csv")
    min_share = {k: float(v["min_share"]) for k, v in plan.items() if (v.get("min_share") or "").strip()}
    sic_map: dict[str, set[str]] = {}
    for r in read_csv(DATA / "sic_to_sector.csv"):
        if plan.get(r["sector"], {}).get("include", "y") == "y":
            sic_map.setdefault(r["sic"], set()).add(r["sector"])

    s = None
    if not a.no_sec:
        from polite_http import PoliteSession
        s = PoliteSession(user_agent(), offline=a.offline)

    rows, seg_rows, texts = [], [], {}
    for firm in firms:
        fid = firm["firm_id"]
        print(f"{fid}: {firm['name']}")
        ev = {"review": []}
        if s is not None and firm["cik"].strip():
            try:
                ev = sec_evidence(s, firm, rules, sic_map, a.rk_threshold, DATA / "descriptions_auto")
            except (FileNotFoundError, RuntimeError) as e:
                ev = {"review": [f"SEC data unavailable: {e}"]}
        elif not firm["cik"].strip():
            manual = DATA / "descriptions" / f"{fid}.txt"
            if manual.exists():
                ev["text"], ev["text_source"] = manual.read_text(encoding="utf-8"), f"hand-saved {manual.name}"
        tags, primary, review = decide_sectors(firm, ev, sic_map, a.rk_threshold, min_share)
        tags = [t for t in tags if plan.get(t[0], {}).get("include", "y") == "y"]
        sectors = {t[0] for t in tags}
        hand = tagset(firm.get("hand_sectors", ""))
        if hand and hand != sectors:
            missing, extra = hand - sectors, sectors - hand
            review.append("differs from hand labels:"
                          + (f" evidence lacks {', '.join(sorted(missing))};" if missing else "")
                          + (f" evidence adds {', '.join(sorted(extra))}" if extra else ""))
        texts[fid] = ev.get("text", "")
        for g in ev.get("segments", []):
            seg_rows.append({"firm_id": fid, "segment": g["label"], "xbrl_member": g["member"],
                             "revenue_usd": f"{g['revenue']:.0f}", "share_of_revenue": f"{g['share']:.1%}",
                             "mapped_sectors": ";".join(sorted(g["sectors"])), "rule": g["rule"],
                             "material": "yes" if g["share"] >= MATERIALITY else "no",
                             "revenue_concept": g["concept"], "source": ev.get("segment_source", "")})
        rows.append({"firm_id": fid, "name": firm["name"], "ticker": firm.get("ticker", ""),
                     "cik": firm["cik"], "sec_filer": "yes" if firm["cik"].strip() else "no",
                     "sec_name": ev.get("sec_name", ""), "sic": ev.get("sic", ""),
                     "sic_description": ev.get("sic_description", ""),
                     "sic_sectors": ";".join(sorted(sic_map.get(ev.get("sic", ""), set()))),
                     "fiscal_year_end": ev.get("fiscal_year_end", ""),
                     "primary_sector": primary, "sectors": ";".join(sorted(sectors)),
                     "evidence": " | ".join(f"{sec}: {why}" for sec, why, _ in tags),
                     "recordkeeping_test": ev.get("recordkeeping", ""),
                     "hand_sectors": firm.get("hand_sectors", ""),
                     "needs_review": " | ".join(review),
                     "final_sectors": ";".join(sorted(sectors)),
                     "text_source": ev.get("text_source", ""), "notes": firm.get("notes", "")})
        print(f"   -> {primary or '?'} | {', '.join(sorted(sectors)) or 'no tags'}"
              + (f"  [REVIEW: {len(review)} item(s)]" if review else ""))

    if a.nlp_check and any(texts.values()):
        from nlp_check import similarity_scores, suggested
        defs = {k: v["definition"] for k, v in
                json.loads((DATA / "sector_definitions.json").read_text(encoding="utf-8")).items()
                if plan.get(k, {}).get("include", "y") == "y"}
        scores = similarity_scores(texts, defs, a.nlp_method)
        for r in rows:
            if r["firm_id"] in scores:
                sug = suggested(scores[r["firm_id"]])
                r["nlp_suggested"] = ";".join(sorted(sug))
                extra = sug - tagset(r["sectors"])
                if extra:
                    r["needs_review"] += (" | " if r["needs_review"] else "") + \
                        f"NLP also suggests {', '.join(sorted(extra))}"

    # ---- write outputs
    fields = list(rows[0]) + (["nlp_suggested"] if a.nlp_check and "nlp_suggested" not in rows[0] else [])
    with open(out_dir / "firm_universe.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    if seg_rows:
        with open(out_dir / "firm_segments.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(seg_rows[0]))
            w.writeheader()
            w.writerows(seg_rows)

    counts = Counter(sec for r in rows for sec in tagset(r["final_sectors"]))
    md = [f"# Part 1.5 firm universe - coverage report ({date.today()})", "",
          "## Coverage vs plan (data/sector_plan.csv)", "",
          "| Sector | Coverage | Firms tagged | Target | Backfill (quarters) | Status |",
          "| --- | --- | --- | --- | --- | --- |"]
    for sid, p in plan.items():
        if p.get("include", "y") != "y":
            continue
        n, target = counts.get(sid, 0), int(p["min_firms"] or 0)
        md.append(f"| {p['label']} | {p['coverage']} | {n} | {target} | {p['backfill_quarters']} | "
                  f"{'OK' if n >= target else f'SHORT by {target - n}'} |")
    md += ["", "Firms can count toward several sectors. Add firms to data/firms.csv to close a gap.", "",
           "## Firms", "", "| Firm | Primary | Sectors | Needs review |", "| --- | --- | --- | --- |"]
    for r in rows:
        md.append(f"| {r['firm_id']} | {r['primary_sector']} | {r['sectors'].replace(';', ', ')} | "
                  f"{r['needs_review'] or '-'} |")
    (out_dir / "coverage_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nWrote {out_dir / 'firm_universe.csv'}, firm_segments.csv and coverage_report.md")
    if s:
        s.save_log()


if __name__ == "__main__":
    main()
