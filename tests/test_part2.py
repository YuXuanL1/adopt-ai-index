"""Offline tests for Part 2 (pytest). No network, no real filings needed: everything is synthetic."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest  # noqa: E402

from part2_common import read_csv, write_csv  # noqa: E402

# ------------------------------------------------------------- document sample
def _fake_raw(root: Path, firms=("jpm",)):
    """A data/raw/edgar-style tree: per firm 3 10-Ks, 9 10-Qs, 12 8-Ks over 2023Q4-2026Q3, 1 proxy/year."""
    n = 0
    for firm in firms:
        quarters = [f"{y}Q{q}" for y in (2023, 2024, 2025, 2026) for q in (1, 2, 3, 4)][3:15]
        for qt in quarters:
            forms = ["8-K"] + (["10-K"] if qt.endswith("Q4") else ["10-Q"])
            for form in forms:
                n += 1
                d = root / firm / qt / f"{form}_0000000000-00-{n:06d}"
                d.mkdir(parents=True)
                (d / "doc.htm").write_text("<p>x</p>")
        for y in (2024, 2025, 2026):
            n += 1
            d = root / firm / f"{y}-annual" / f"DEF14A_0000000000-00-{n:06d}"
            d.mkdir(parents=True)
            (d / "proxy.htm").write_text("<p>x</p>")
    (root / firms[0] / "2024Q1" / "10-Q_empty").mkdir(parents=True)   # empty folder -> reported, skipped
    return root


def test_scan_filings_reads_tree_and_reports_gaps(tmp_path):
    from part2_common import scan_filings
    raw = _fake_raw(tmp_path / "raw")
    man = tmp_path / "m.csv"
    write_csv(man, [{"accession": "9999999999-99-999999", "firm_id": "jpm", "form": "10-K", "files": "a.htm"}],
              ["accession", "firm_id", "form", "files"])
    filings, problems = scan_filings(raw, man)
    forms = [f.form for f in filings]
    assert forms.count("10-K") == 3 and forms.count("10-Q") == 9 and forms.count("DEF 14A") == 3
    assert {p["issue"] for p in problems} == {"in manifest, not on disk", "folder is empty"}
    proxy = next(f for f in filings if f.form == "DEF 14A" and f.period == "2026-annual")
    assert proxy.fiscal_year == 2025                       # proxy filed in 2026 reports on FY2025
    _, none = scan_filings(tmp_path / "does-not-exist", tmp_path / "nope.csv")
    assert none == []


def test_sample_spread_deterministic_and_stable_when_firms_added(tmp_path):
    from part2_common import scan_filings
    from part2_sample_docs import draw
    plan = {"10-K": 2, "10-Q": 2, "8-K": 2, "DEF 14A": 1}
    one, _ = scan_filings(_fake_raw(tmp_path / "a", ("jpm",)), tmp_path / "none.csv")
    two, _ = scan_filings(_fake_raw(tmp_path / "b", ("jpm", "bac")), tmp_path / "none.csv")
    s1 = draw(one, plan, ["jpm"], seed=1)
    assert [f.accession for f in s1] == [f.accession for f in draw(one, plan, ["jpm"], seed=1)]
    assert len(s1) == 7
    for form in ("10-K", "10-Q", "8-K"):                   # two picks of a form come from two different years
        yrs = [f.fiscal_year for f in s1 if f.form == form]
        assert len(set(yrs)) == 2
    s2 = draw(two, plan, ["jpm", "bac"], seed=1)
    key = lambda fs: [(f.period, f.form) for f in fs if f.firm_id == "jpm"]   # noqa: E731
    assert key(s1) == key(s2)                               # adding BAC leaves JPM's picks unchanged


def test_sample_freeze_and_resample_rules(tmp_path, monkeypatch):
    import part2_sample_docs as sd
    monkeypatch.setattr(sd, "OUT", tmp_path / "out")
    monkeypatch.setattr(sd, "RAW_ROOT", _fake_raw(tmp_path / "raw"))
    monkeypatch.setattr(sd, "P1_MANIFEST", tmp_path / "none.csv")
    run = lambda *a: (monkeypatch.setattr(sys, "argv", ["x", "--firms", "jpm", *a]), sd.main())  # noqa: E731
    run()
    assert (tmp_path / "out" / "sample_manifest_draft.csv").exists()
    assert not (tmp_path / "out" / "sample_manifest.csv").exists()
    with pytest.raises(SystemExit):
        run("--freeze")                                     # no reason
    run("--freeze", "--reason", "test")
    frozen = read_csv(tmp_path / "out" / "sample_manifest.csv")
    with pytest.raises(SystemExit):
        run("--freeze", "--reason", "again")                # frozen: needs --resample
    run()                                                   # a draft run never touches the frozen file
    assert read_csv(tmp_path / "out" / "sample_manifest.csv") == frozen
    run("--freeze", "--resample", "--reason", "new data")
    log = read_csv(tmp_path / "out" / "sample_log.csv")
    assert [r["action"] for r in log] == ["freeze", "resample"] and log[1]["archived_as"]
    assert len(list((tmp_path / "out" / "archive").glob("sample_manifest_*.csv"))) == 1


# ------------------------------------------------------------- AI passage extraction
SETTINGS = {"context_sentences": 1, "weak_window_sentences": 2, "max_passage_sentences": 6, "max_passage_chars": 3000}


def _terms():
    from part2_common import load_keywords
    return load_keywords()          # the real data/ai_keywords.csv - tests guard the shipped list


def test_keywords_skip_false_positives():
    from part2_common import find_hits
    text = ("Shareholders voted AGAINST the plan. Said director sits on the board of GlobalAI Cloud Inc. "
            "We OBTAIN data. The CHAIRMAN spoke. Maintain controls.")
    assert [h for h in find_hits(text, _terms()) if h.strength == "strong"] == []
    hits = find_hits("We use AI, GenAI, machine-learning and an LLM Suite; see A.I. policy.", _terms())
    assert {h.term_id for h in hits} >= {"ai_acronym", "genai", "machine_learning", "llm_acronym", "ai_dotted"}


def test_merrill_ml_excluded_but_machine_learning_ml_kept():
    from part2_common import find_hits
    hits = find_hits("Clients of Merrill Lynch (ML) grew. We use AI/ML models.", _terms())
    ml = [h for h in hits if h.term_id == "ml_acronym"]
    assert len(ml) == 1 and ml[0].start > 30


def test_weak_terms_need_a_strong_term_nearby():
    from part2_common import find_hits
    from part2_extract_ai_passages import build_passages
    far = ("We use an automated valuation model for homes. " + "Filler sentence about deposits. " * 6
           + "We use artificial intelligence in fraud checks.")
    ps = build_passages(far, find_hits(far, _terms()), SETTINGS)
    assert len(ps) == 1 and "automated valuation" not in ps[0]["text"]
    near = "We use an automated valuation model. Filler sentence here. We use AI in fraud checks."
    ps = build_passages(near, find_hits(near, _terms()), SETTINGS)
    assert len(ps) == 1 and {h.term_id for h in ps[0]["hits"]} == {"automation", "ai_acronym"}


def test_passages_merge_and_cap():
    from part2_common import find_hits
    from part2_extract_ai_passages import build_passages
    sents = [f"Sentence {i} mentions AI here." if i in (2, 3, 20) else f"Sentence {i} is plain text." for i in range(25)]
    text = " ".join(sents)
    ps = build_passages(text, find_hits(text, _terms()), SETTINGS)
    assert len(ps) == 2                                   # 2 and 3 merge; 20 is separate
    assert ps[0]["text"].startswith("Sentence 1 ") and ps[0]["text"].endswith("Sentence 4 is plain text.")
    many = " ".join(f"Sentence {i} mentions AI." for i in range(20))
    ps = build_passages(many, find_hits(many, _terms()), SETTINGS)
    assert all(p["text"].count("Sentence") <= 6 for p in ps) and len(ps) >= 3
    assert all(a["char_end"] <= b["char_start"] for a, b in zip(ps, ps[1:]))     # no overlap


def test_section_detection_ignores_cross_references():
    from part2_common import load_sections, section_at, section_index
    text = ("Item 1. Business We bank. Item 1A. Risk Factors AI may fail. "
            "See Part I, Item 1A: Risk Factors on pages 9-30. Management’s discussion and analysis We use AI.")
    idx = section_index(text, load_sections()["10-K"])
    assert section_at(text.index("AI may"), idx) == "Item 1A Risk Factors"
    assert section_at(text.index("We use AI"), idx) == "MD&A"


def test_duplicates_marked_across_pdf_and_html_spacing():
    from part2_extract_ai_passages import mark_duplicates
    base = {"firm_id": "jpm", "file": "f", "char_start": 0}
    rows = [{**base, "passage_id": "ars", "form": "ARS", "filing_date": "2025-04-07",
             "text": "The Firm uses models, including those based on machine learning or AI tech - niques, across busi - nesses."},
            {**base, "passage_id": "k", "form": "10-K", "filing_date": "2025-02-14",
             "text": "The Firm uses models, including those based on machine learning or AI techniques, across businesses."},
            {**base, "passage_id": "other", "form": "10-K", "filing_date": "2025-02-14",
             "text": "Completely different text about AI coding assistants used by engineers."}]
    mark_duplicates(rows)
    by = {r["passage_id"]: r for r in rows}
    assert by["k"]["dup_of"] == "" and by["ars"]["dup_of"] == "k" and by["other"]["dup_of"] == ""


def test_coding_sheet_keeps_team_input():
    from part2_extract_ai_passages import merge_coding_sheet
    old = [{"passage_id": "p1", "use_description": "fraud scoring", "proposed_category": "C01"},
           {"passage_id": "gone", "use_description": "typed by a teammate"},
           {"passage_id": "gone-empty", "use_description": ""}]
    new = [{"passage_id": "p1", "text": "AI", "dup_of": ""}, {"passage_id": "p2", "text": "AI", "dup_of": "p1"}]
    rows = {r["passage_id"]: r for r in merge_coding_sheet(old, new)}
    assert rows["p1"]["proposed_category"] == "C01" and rows["p1"]["status"] == "to_code"
    assert rows["p2"]["status"] == "duplicate" and rows["gone"]["status"] == "orphaned"
    assert "gone-empty" not in rows


def test_exhibit_names():
    from part2_extract_ai_passages import exhibit_of
    assert exhibit_of("a1q26erfexhibit991narrative.htm") == "EX-99.1"
    assert exhibit_of("a1q26erfex992supplement.htm") == "EX-99.2"
    assert exhibit_of("jpm-20260414.htm") == "main"


def test_taxonomy_file_is_consistent():
    from config import DATA
    tax = read_csv(DATA / "taxonomy.csv")
    need = {"category_id", "category", "definition", "include_rules", "exclude_rules", "example_paraphrase", "example_citation"}
    assert need <= set(tax[0]) and len({t["category_id"] for t in tax}) == len(tax)
    assert all(t["status"].startswith("v0.1-DRAFT") for t in tax)


# ------------------------------------------------------------- taxonomy document
def test_taxonomy_doc_pairs_examples_and_flags_bad_citations():
    import part2_taxonomy_doc as td
    assert td.numbered("[1] first one [2] second [3] third") == ["first one", "second", "third"]
    rows = [{"category_id": "C01", "category": "Fraud", "definition": "d", "include_rules": "a; b",
             "exclude_rules": "x (-> C02). Y.", "is_ai_use": "y", "status": "v0.1-DRAFT",
             "example_paraphrase": "[1] p one [2] p two",
             "example_citation": "[1] Doc A; passage jpm-2025-annual-ARS-1eecf2 [2] Doc B; passage jpm-2024Q4-10-K-abcdef",
             "starter_mapping": "kept", "supporting_passages": "x;y", "review_notes": ""},
            {"category_id": "C00", "category": "Context", "definition": "d", "include_rules": "a",
             "exclude_rules": "z", "is_ai_use": "n", "status": "v0.1-DRAFT",
             "example_paraphrase": "[1] only one", "example_citation": "[1] Doc C; passage jpm-2026Q1-8-K-123456",
             "starter_mapping": "new", "supporting_passages": "", "review_notes": "check"}]
    passages = [{"passage_id": "jpm-2025-annual-ARS-1eecf2", "accession": "1", "firm_id": "jpm", "form": "ARS",
                 "dup_of": ""},
                {"passage_id": "jpm-2026Q1-8-K-123456", "accession": "2", "firm_id": "jpm", "form": "8-K",
                 "dup_of": ""}]
    problems = td.check_citations(rows, passages)
    assert any("jpm-2024Q4-10-K-abcdef" in p for p in problems)          # cited id not in passages
    assert any(p.startswith("C00: 1 examples") for p in problems)        # fewer than 2 examples
    doc = td.build(rows, [], passages, frozen=False, today="2026-01-01")
    assert "p one" in doc and "_Source: Doc A; passage jpm-2025-annual-ARS-1eecf2_" in doc
    assert "C00 — Context _(not an AI use)_" in doc and "sample not frozen" in doc


def test_taxonomy_doc_word_copy(tmp_path):
    pytest.importorskip("docx")
    import part2_taxonomy_doc as td
    from docx import Document
    md = "# Title\n\nText with **bold**, *it* and `code`.\n\n| A | B |\n|---|---|\n| x \\| y | z |\n\n1. one  \n   _Source: s_\n"
    out = tmp_path / "t.docx"
    assert td.md_to_docx(md, out)
    d = Document(out)
    assert d.paragraphs[0].text == "Title" and "**" not in d.paragraphs[1].text and "*" not in d.paragraphs[1].text
    assert d.tables[0].cell(1, 0).text == "x | y" and "Source: s" in d.paragraphs[-1].text
