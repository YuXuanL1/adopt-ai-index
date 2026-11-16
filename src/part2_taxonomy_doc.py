"""PART 2 - Build the taxonomy document (the Part 2 deliverable) from the taxonomy data files.

The categories, rules and examples live in data/taxonomy.csv and data/taxonomy_starter_crosswalk.csv;
this script only lays them out as a readable document, adds the method and sample numbers from
outputs/part2/, and checks that every cited passage id really exists. Edit the CSVs, not the output -
re-run after every taxonomy revision so the document never drifts from the data.

Reads (missing files are reported, never fatal):
  data/taxonomy.csv                          categories, rules, paraphrased examples + citations
  data/taxonomy_starter_crosswalk.csv        what happened to each starter-list category
  outputs/part2/ai_passages.csv              to count passages and check cited passage ids
  outputs/part2/sample_manifest.csv          frozen sample, if any (else the draft is noted)

Output:
  outputs/part2/taxonomy_document.md

Run:
  python src/part2_taxonomy_doc.py
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path

from config import DATA
from part2_common import PART2_OUT, read_csv, rel

TAXONOMY = DATA / "taxonomy.csv"
CROSSWALK = DATA / "taxonomy_starter_crosswalk.csv"
PASSAGES = PART2_OUT / "ai_passages.csv"
FROZEN = PART2_OUT / "sample_manifest.csv"
OUT = PART2_OUT / "taxonomy_document.md"
OUT_DOCX = PART2_OUT / "taxonomy_document.docx"

# Uses inside kept categories that the sample never showed. Update when the taxonomy is revised.
OTHER_GAPS = [
    ("Insurance underwriting", "starter 'Underwriting' example; banks only lend, so C02 covers lending only. "
                               "Add a sub-tag if insurers join."),
    ("Customer chatbots", "starter 'Customer service' example; no JPM passage names one (BAC's Erica is expected)."),
    ("AI for cyber-defence", "not in the starter list and not in the sample; C01 excludes it for now."),
]

_NUM = re.compile(r"\[(\d+)\]\s*")
_PID = re.compile(r"passage ([A-Za-z0-9-]+-[0-9a-f]{6})\b")


def numbered(text: str) -> list[str]:
    """'[1] a [2] b' -> ['a', 'b']; text without numbers -> [text]."""
    parts = [p.strip() for p in _NUM.split(text or "")]
    if len(parts) == 1:
        return [parts[0]] if parts[0] else []
    return [parts[i + 1] for i in range(1, len(parts) - 1, 2)]


def is_use(row: dict) -> bool:
    return (row.get("is_ai_use") or "y").strip().lower().startswith("y")


def cited_ids(rows: list[dict]) -> dict[str, list[str]]:
    return {r["category_id"]: _PID.findall(r.get("example_citation", "")) for r in rows}


def check_citations(rows: list[dict], passages: list[dict]) -> list[str]:
    """Problems with the examples: wrong count, unpaired citations, ids not in ai_passages.csv."""
    known = {p["passage_id"] for p in passages}
    out = []
    for r in rows:
        cid = r["category_id"]
        ex, cit = numbered(r.get("example_paraphrase", "")), numbered(r.get("example_citation", ""))
        if not 2 <= len(ex) <= 3:
            out.append(f"{cid}: {len(ex)} examples (the assignment asks for 2-3)")
        if len(ex) != len(cit):
            out.append(f"{cid}: {len(ex)} examples but {len(cit)} citations")
        if known:
            for pid in _PID.findall(r.get("example_citation", "")):
                if pid not in known:
                    out.append(f"{cid}: cited passage {pid} is not in {rel(PASSAGES)}")
    return out


def sample_facts(passages: list[dict]) -> dict:
    docs = {p["accession"] for p in passages}
    return {
        "passages": len(passages),
        "unique": sum(1 for p in passages if not (p.get("dup_of") or "").strip()),
        "docs_with_ai": len(docs),
        "firms": sorted({p["firm_id"] for p in passages}),
        "by_form": Counter(p["form"] for p in passages if not (p.get("dup_of") or "").strip()),
        "doc_set": sorted({p.get("doc_set", "") for p in passages} - {""}),
    }


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def build(rows: list[dict], cross: list[dict], passages: list[dict], frozen: bool, today: str) -> str:
    use = [r for r in rows if is_use(r)]
    non = [r for r in rows if not is_use(r)]
    status = sorted({r.get("status", "") for r in rows} - {""})
    f = sample_facts(passages) if passages else None
    o = [f"# AI-Use Categorization Taxonomy — {status[0] if len(status) == 1 else 'draft'}", "",
         f"_Generated {today} by `src/part2_taxonomy_doc.py` from `{rel(TAXONOMY)}` and `{rel(CROSSWALK)}`. "
         "Edit those files and re-run; do not edit this document by hand._", ""]

    if f:
        firms = ", ".join(x.upper() for x in f["firms"])
        o += ["> **Status.** Draft for team review. Built from "
              + ("the frozen document sample" if frozen else "all filings on disk (sample not frozen yet)")
              + f" for **{firms}** only. Categories must be re-checked when the other pilot banks are added.", ""]

    # 1. Purpose
    o += ["## 1. Purpose and unit of analysis", "",
          "The taxonomy classifies **AI passages** — a sentence that mentions AI plus one sentence either side, "
          "merged when hits are close — taken from SEC filings. Each passage gets **one** category: what the AI "
          "is used for. It is built to separate firms *using* AI from firms *talking about* AI, so it has two kinds "
          "of category:", "",
          f"- **AI-use categories** ({', '.join(r['category_id'] for r in use)}): the passage names a business "
          "function where the firm applies AI.",
          f"- **Non-use categories** ({', '.join(r['category_id'] for r in non)}): AI is mentioned, but no specific "
          "use is the subject — strategy and spending, risks and governance, or text that is not about the firm's "
          "own AI at all. These are kept, not discarded, so later parts can measure how much AI text is talk rather "
          "than use.", ""]

    # 2. Method
    o += ["## 2. How it was built", ""]
    if f:
        forms = ", ".join(f"{k} {v}" for k, v in sorted(f["by_form"].items()))
        o += [f"1. **Documents.** Filings already downloaded in Part 1 (10-K, 10-Q, earnings 8-K, proxy DEF 14A, "
              f"annual report ARS). AI terms were found in {f['docs_with_ai']} documents.",
              f"2. **Passages.** A keyword list (`data/ai_keywords.csv`) found {f['passages']} AI passages; "
              f"{f['unique']} remain after removing repeated text (e.g. the annual report reprinting the 10-K). "
              f"Unique passages by form: {forms}.",
              "3. **Open coding.** Unique passages were read and their AI use described in free text before any "
              "category list was applied. For this draft that pass was done with AI assistance; the team's own "
              f"open coding (`{rel(PART2_OUT / 'open_coding_sheet.csv')}`) is the check on it.",
              "4. **Grouping.** Similar uses were grouped into categories, then compared with the assignment's "
              "starter list: categories were kept, merged, split, or added when the filings required it "
              "(section 6). Uses with no supporting passage were not adopted (section 7).",
              "5. **Rules.** Each category got inclusion/exclusion rules written from the boundary cases met in "
              "coding, and 2–3 paraphrased examples cited to the filing, page/section and passage id.", ""]
    else:
        o += [f"_`{rel(PASSAGES)}` not found — run `src/part2_extract_ai_passages.py` to add sample numbers._", ""]

    # 3. Overview
    o += ["## 3. Categories at a glance", "",
          "| ID | Category | AI use? | Definition | Supporting passages |", "|---|---|---|---|---|"]
    for r in rows:
        n = len([x for x in (r.get("supporting_passages") or "").split(";") if x.strip()])
        o.append(f"| {r['category_id']} | {_cell(r['category'])} | {'yes' if is_use(r) else 'no'} | "
                 f"{_cell(r['definition'])} | {n} |")
    o += ["", "_Supporting passages = passages linked to the category while drafting; not a full count._", ""]

    # 4. General rules
    o += ["## 4. How to assign a category", "",
          "Give each passage the **one** category it says most about. Work through these questions in order:", "",
          "1. Is the passage about **this firm's own** AI (its use, plans, spending, risks or oversight)? "
          "If not — macro commentary, public policy, AI companies as clients, metaphors, glossary — code **C00**.",
          "2. Does it name a **specific business use** of AI as its main subject? Code that use (**C01–C10**), "
          "even if strategy words appear around it. If several uses are named, pick the one described most.",
          "3. Is it about **risks created by AI**, AI regulation or **oversight** of AI? Code **C12**.",
          "4. Otherwise — ambition, budgets, data readiness, talent, use-case counts, rankings — code **C11**.", "",
          "Judge only from the passage text. Automation, algorithms or models with **no AI term** in the passage "
          "are not AI. Boundary rules for each category are in section 5.", ""]

    # 5. Category entries
    o += ["## 5. Category definitions", ""]
    for r in rows:
        ex, cit = numbered(r.get("example_paraphrase", "")), numbered(r.get("example_citation", ""))
        o += [f"### {r['category_id']} — {r['category']}" + ("" if is_use(r) else " _(not an AI use)_"), "",
              f"**Definition.** {r['definition']}", "",
              "**Include:**", ""] + [f"- {_cap(x.strip())}" for x in r["include_rules"].split(";") if x.strip()] + [
              "", "**Exclude:**", ""] + [f"- {x.strip()}" for x in re.split(r"(?<=[.)])\s+(?=[A-Z'])", r["exclude_rules"]) if x.strip()] + [
              "", "**Examples (paraphrased):**", ""]
        for i, e in enumerate(ex):
            o.append(f"{i + 1}. {e}  \n   _Source: {cit[i] if i < len(cit) else 'citation missing'}_")
        o += ["", f"**Relation to starter list:** {r.get('starter_mapping', '')}"]
        if (r.get("review_notes") or "").strip():
            o += ["", f"**Note for reviewers:** {r['review_notes']}"]
        o.append("")

    # 6. Crosswalk
    o += ["## 6. Changes from the starter list", "",
          "| Starter category | v0.1 | Decision | Evidence in sample | Reason |", "|---|---|---|---|---|"]
    for c in cross:
        o.append(f"| {_cell(c['starter_category'])} | {_cell(c['v01_category_ids'])} | {_cell(c['decision'])} | "
                 f"{_cell(c['evidence_in_sample'])} | {_cell(c['reason'])} |")
    gaps = [c for c in cross if (c.get("evidence_in_sample") or "").strip().lower() in ("none", "partial")]
    o += ["", "## 7. Not yet supported by evidence", ""]
    o += [f"- **{c['starter_category']}** ({c['starter_examples']}): {c['reason']}" for c in gaps] or ["- none"]
    o += [f"- **{name}**: {why}" for name, why in OTHER_GAPS]
    o += ["", "These stay out of the taxonomy until passages from other firms or sectors support them. "
          "The retirement-plan sub-tags described in Part 1.5 (participant advice, retirement income modelling, "
          "plan design and auto-features, sponsor analytics, participant chatbots) are also not covered yet: "
          "they need filings from retirement-plan providers.", ""]

    # 8. Limits
    o += ["## 8. Limitations", ""]
    if f and len(f["firms"]) == 1:
        o.append(f"- **One firm.** Every example comes from {f['firms'][0].upper()}, so the taxonomy describes how one "
                 "bank talks about AI. Category boundaries may move when other banks are added.")
    o += ["- **Where the text comes from.** Most concrete uses appear in annual-report shareholder letters, which "
          "are promotional and unaudited; the categories record what firms *say*, not verified deployment.",
          "- **Keyword recall.** Uses described without any AI term are not found, so some uses may be missing.",
          "- **One category per passage.** Passages that name several uses are coded by their main use; the others "
          "are lost at this level.",
          "- **Drafted with AI assistance.** The team must check every definition, rule and paraphrase against the "
          "cited passages before submission.", ""]
    o += ["## 9. Citation and paraphrase policy", "",
          "Examples are paraphrased, never copied, and each cites the firm, document, filing date, SEC accession "
          f"number, page or section, and the passage id. The full passage text is in `{rel(PASSAGES)}` for checking; "
          "it is a working file and is not reproduced here (see the appendix).", ""]

    # Appendix: the passage file
    o += [f"## Appendix: Source passages (`{rel(PASSAGES)}`)", "",
          "This file is the raw material the taxonomy was built from: every passage in the filings that mentions AI, "
          "one passage per row. `src/part2_extract_ai_passages.py` scans each filing for the AI terms in "
          "`data/ai_keywords.csv` (e.g. AI, artificial intelligence, machine learning, generative AI), cuts out the "
          "matching sentence with one sentence either side, and merges matches that sit close together."]
    if f:
        o[-1] += (f" It currently holds {f['passages']} passages ({f['unique']} unique) from "
                  f"{', '.join(x.upper() for x in f['firms'])}.")
    o += ["", "| Column | Meaning |", "|---|---|",
          "| `passage_id` | Unique id; the examples in section 5 cite it — search for it to find the original text |",
          "| `firm_id`, `quarter`, `form` | Firm, period and document type the passage comes from |",
          "| `section`, `page` | Where in the document it sits (e.g. Item 1A Risk Factors; PDF page for annual reports) |",
          "| `text` | The passage itself (verbatim) |",
          "| `matched_terms` | The AI terms found in it |",
          "| `dup_of` | Filled when the passage repeats an earlier one (e.g. the annual report reprinting the 10-K); "
          "such rows are read once |",
          "", "Other columns (accession number, filing date, character positions) trace each passage back to the "
          "exact filing on SEC EDGAR.", "",
          "The `text` column is copied verbatim from the filings. It is kept as an internal working file for "
          "checking and coding only; any text used in a report is paraphrased and cited, as in section 5.", ""]
    return "\n".join(o)


# ------------------------------------------------------------------ Word version
_INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|(?<![\w])_[^_].*?_(?![\w])|(?<![\w*])\*[^*\s][^*]*\*(?![\w*]))")
FONT = "Arial"
TEXT_WIDTH_IN = 6.7                     # US Letter minus 0.9" margins


def _col_widths(rows: list[list[str]]) -> list[float]:
    """Column widths in inches, roughly in proportion to how much text each column holds."""
    n = len(rows[0])
    weight = [max(len(rows[0][c]), sum(len(r[c]) for r in rows[1:]) / max(1, len(rows) - 1)) ** 0.6
              for c in range(n)]                                    # damped so short columns stay readable
    raw = [max(0.6, TEXT_WIDTH_IN * w / sum(weight)) for w in weight]
    return [w * TEXT_WIDTH_IN / sum(raw) for w in raw]


def _shade(cell, hex_fill: str) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hex_fill)
    cell._tc.get_or_add_tcPr().append(shd)


def _runs(par, text: str, italic: bool = False) -> None:
    """Add text to a python-docx paragraph, turning **bold**, _italic_ and `code` into formatted runs."""
    for piece in _INLINE.split(text):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**"):
            r = par.add_run(piece[2:-2]); r.bold = True; r.italic = italic
        elif piece.startswith("`") and piece.endswith("`"):
            r = par.add_run(piece[1:-1]); r.font.name = "Courier New"; r.italic = italic
        elif len(piece) > 1 and piece[0] == piece[-1] and piece[0] in "_*":
            _runs(par, piece[1:-1], italic=True)
        else:
            r = par.add_run(piece.replace("\\|", "|")); r.italic = italic


def _table_cells(line: str) -> list[str]:
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]


def md_to_docx(md: str, path: Path) -> bool:
    """Write the Markdown this script produces (headings, lists, tables, quotes) as a .docx.
    Returns False when python-docx is not installed."""
    try:
        from docx import Document
        from docx.enum.section import WD_ORIENT  # noqa: F401  (kept portrait)
        from docx.shared import Pt, RGBColor, Inches
    except ImportError:
        return False
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)          # US Letter
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Inches(0.9))
    base = doc.styles["Normal"]
    base.font.name, base.font.size = FONT, Pt(10)
    base.paragraph_format.space_after = Pt(4)
    for name, size in (("Title", 20), ("Heading 1", 15), ("Heading 2", 12.5)):
        st = doc.styles[name]
        st.font.name, st.font.size, st.font.bold = FONT, Pt(size), True
        st.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
        st.paragraph_format.space_before, st.paragraph_format.space_after = Pt(12), Pt(4)
        st.paragraph_format.keep_with_next = True

    lines = md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        if s.startswith("|"):                                            # table block
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i]); i += 1
            rows = [_table_cells(b) for b in block if not re.fullmatch(r"\|[\s\-|:]+\|", b.strip())]
            t = doc.add_table(rows=len(rows), cols=len(rows[0]))
            t.style = "Table Grid"
            t.autofit = False
            widths = _col_widths(rows)
            for c, w in enumerate(widths):
                t.columns[c].width = Inches(w)
            for r, cells in enumerate(rows):
                for c, txt in enumerate(cells):
                    cell = t.cell(r, c)
                    cell.width = Inches(widths[c])                       # Word reads the cell width
                    cell.paragraphs[0].text = ""
                    cell.paragraphs[0].paragraph_format.space_after = Pt(0)
                    _runs(cell.paragraphs[0], f"**{txt}**" if r == 0 else txt)
                    for run in cell.paragraphs[0].runs:
                        run.font.size = Pt(8.5)
                    if r == 0:
                        _shade(cell, "DCE6F0")
            doc.add_paragraph()
            continue
        if s.startswith("# "):
            doc.add_paragraph(s[2:], style="Title")
        elif s.startswith("## "):
            p = doc.add_paragraph(style="Heading 1"); _runs(p, s[3:])
        elif s.startswith("### "):
            p = doc.add_paragraph(style="Heading 2"); _runs(p, s[4:])
        elif s.startswith("> "):
            p = doc.add_paragraph(); p.paragraph_format.left_indent = Inches(0.3); _runs(p, s[2:], italic=True)
        elif s.startswith("- "):
            p = doc.add_paragraph(style="List Bullet"); _runs(p, s[2:])
        elif re.match(r"\d+\. ", s):
            # numbers written out: Word's List Number would keep counting across the whole document
            p = doc.add_paragraph()
            p.paragraph_format.left_indent, p.paragraph_format.first_line_indent = Inches(0.3), Inches(-0.25)
            _runs(p, s.rstrip())
            while i + 1 < len(lines) and lines[i + 1].startswith("   ") and lines[i + 1].strip():
                i += 1                                                    # '  \n   _Source: ..._' continuation
                p.add_run().add_break()
                _runs(p, lines[i].strip())
                for run in p.runs[-1:]:
                    run.font.size = Pt(9)
        else:
            p = doc.add_paragraph(); _runs(p, s)
        i += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return True


def main() -> None:
    rows, cross, passages = read_csv(TAXONOMY), read_csv(CROSSWALK), read_csv(PASSAGES)
    print("Inputs:")
    for path, data in ((TAXONOMY, rows), (CROSSWALK, cross), (PASSAGES, passages), (FROZEN, read_csv(FROZEN))):
        print(f"  {'ok     ' if data else 'MISSING'} {rel(path)} ({len(data)} rows)")
    if not rows:
        raise SystemExit(f"No categories in {rel(TAXONOMY)} - nothing to write.")
    problems = check_citations(rows, passages)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    md = build(rows, cross, passages, FROZEN.exists(), date.today().isoformat())
    OUT.write_text(md, encoding="utf-8")
    wrote_docx = md_to_docx(md, OUT_DOCX)
    n_ex = sum(len(numbered(r.get("example_paraphrase", ""))) for r in rows)
    print(f"Categories: {len(rows)} ({sum(map(is_use, rows))} AI-use, {sum(not is_use(r) for r in rows)} non-use); "
          f"examples: {n_ex}; starter categories mapped: {len(cross)}")
    if not passages:
        print("WARNING: no ai_passages.csv - cited passage ids were not checked")
    if not FROZEN.exists():
        print("WARNING: sample not frozen - the document says so")
    for p in problems:
        print(f"WARNING: {p}")
    print(f"Wrote {rel(OUT)}" + (f" and {rel(OUT_DOCX)}" if wrote_docx else
                                 " (no Word copy: pip install python-docx)"))


if __name__ == "__main__":
    main()
