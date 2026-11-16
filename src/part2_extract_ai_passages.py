"""PART 2 - Pull every AI-related passage out of the sampled filings, with its source metadata.

Which documents (--source):
  auto  (default)  the FROZEN outputs/part2/sample_manifest.csv if it exists, otherwise every pilot
                   filing on disk (provisional - printed as a warning)
  sample           the frozen sample only     draft   sample_manifest_draft.csv     all   every pilot filing on disk

How a passage is found (all settings in data/ files):
  1. Text: HTML via Part 1's html_to_text; annual-report PDFs page by page (page number kept).
  2. Terms from data/ai_keywords.csv. 'strong' terms always count; 'weak' ones (ML, algorithm,
     automation, ...) only within weak_window_sentences of a strong term; 'exclude' patterns
     veto matches inside them (e.g. Merrill Lynch 'ML'). 'AI' is case-sensitive and whole-word.
  3. Passage = the hit sentence +/- context_sentences; overlapping windows merge up to
     max_passage_sentences (data/part2_settings.json).
  4. Section = nearest heading before the passage (data/part2_sections.csv); best effort.
  5. Duplicates: the same text in two places (annual report repeating the 10-K, risk-factor
     boilerplate repeated each quarter) gets dup_of = the earliest passage id. Code it once.

Outputs (outputs/part2/):
  ai_passages.csv        one row per passage + source metadata
  open_coding_sheet.csv  blank columns for the team; re-running KEEPS anything already typed
                         (rows whose passage vanished are kept and marked 'orphaned')
  extraction_summary.md  coverage: documents, files read/failed, hits and passages per firm x form

Run:
  python src/part2_extract_ai_passages.py
  python src/part2_extract_ai_passages.py --source all
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

from config import ROOT
from part2_common import (PART2_OUT, coverage_table, coverage_warnings, find_hits, firm_info, load_keywords,
                          load_sections, load_settings, read_csv, read_text, scan_filings, section_at,
                          section_index, sentence_spans, write_csv)

PASSAGE_COLS = ["passage_id", "doc_set", "sample_id", "firm_id", "firm_name", "sectors", "quarter", "fiscal_year",
                "form", "accession", "filing_date", "file", "exhibit", "section", "page", "char_start", "char_end",
                "position_pct", "matched_terms", "n_strong", "n_weak", "dup_of", "dup_score", "truncated", "text"]
HUMAN_COLS = ["coder", "ai_subject", "use_description", "proposed_category", "notes"]
CODING_COLS = ["passage_id", "status", "firm_id", "quarter", "form", "section", "page", "dup_of",
               "matched_terms", "text"] + HUMAN_COLS
FORM_ORDER = {"10-K": 0, "10-Q": 1, "8-K": 2, "DEF 14A": 3, "ARS": 4}


# ------------------------------------------------------------------ passages from one text
def build_passages(text: str, hits: list, settings: dict) -> list[dict]:
    """Group hits into sentence windows. Returns dicts with char_start/char_end/text/hits/truncated."""
    if not hits:
        return []
    spans = sentence_spans(text)
    starts = [s for s, _ in spans]
    sent_of = lambda off: max(bisect.bisect_right(starts, off) - 1, 0)          # noqa: E731
    strong = sorted({sent_of(h.start) for h in hits if h.strength == "strong"})
    w = settings.get("weak_window_sentences", 2)

    def near_strong(i: int) -> bool:
        j = bisect.bisect_left(strong, i - w)
        return j < len(strong) and strong[j] <= i + w

    kept = [h for h in hits if h.strength == "strong" or near_strong(sent_of(h.start))]
    by_sent = defaultdict(list)
    for h in kept:
        by_sent[sent_of(h.start)].append(h)
    c = settings.get("context_sentences", 1)
    cap = max(settings.get("max_passage_sentences", 6), 2 * c + 1)
    windows = []
    for a in sorted(by_sent):
        lo, hi = max(0, a - c), min(len(spans) - 1, a + c)
        if windows and lo <= windows[-1][1] + 1 and hi - windows[-1][0] + 1 <= cap:
            windows[-1][1] = max(windows[-1][1], hi)
        else:
            if windows:
                lo = max(lo, windows[-1][1] + 1)
            windows.append([lo, hi])
    out, max_chars = [], settings.get("max_passage_chars", 3000)
    for lo, hi in windows:
        s, e = spans[lo][0], spans[hi][1]
        inside = [h for h in kept if s <= h.start < e]
        if not inside:
            continue
        truncated = False
        if e - s > max_chars:                       # flattened tables can make one 'sentence' huge
            mid = inside[0].start
            s2 = max(s, mid - max_chars // 2)
            s, e, truncated = s2, min(e, s2 + max_chars), True
            inside = [h for h in inside if s <= h.start < e]
        out.append({"char_start": s, "char_end": e, "text": text[s:e].strip(), "hits": inside, "truncated": truncated})
    return out


def exhibit_of(name: str) -> str:
    n = name.lower()
    if re.search(r"ex(?:hibit)?[-_]?99[-_.]?1(?!\d)|exhibit991|ex991", n):
        return "EX-99.1"
    if re.search(r"ex(?:hibit)?[-_]?99[-_.]?2(?!\d)|ex992", n):
        return "EX-99.2"
    return "main"


def passage_id(doc: dict, file: str, char_start: int) -> str:
    h = hashlib.sha1(f"{doc['accession']}|{file}|{char_start}".encode()).hexdigest()[:6]
    return f"{doc['firm_id']}-{doc['quarter']}-{doc['form'].replace(' ', '')}-{h}"


# ------------------------------------------------------------------ duplicates
def _grams(text: str, k: int = 12) -> set[str]:
    s = re.sub(r"[^a-z0-9]", "", text.lower())       # spacing/hyphen differences (PDF vs HTML) vanish
    return {s[i:i + k] for i in range(0, max(len(s) - k + 1, 1))}


def mark_duplicates(rows: list[dict], threshold: float = 0.8) -> None:
    """dup_of = earliest passage (filing date, then form) of the same firm whose text covers >= threshold."""
    order = sorted(range(len(rows)), key=lambda i: (rows[i]["filing_date"] or "9999", FORM_ORDER.get(rows[i]["form"], 9),
                                                    rows[i]["file"], int(rows[i]["char_start"])))
    seen: dict[str, list[tuple[str, set]]] = defaultdict(list)
    for i in order:
        r = rows[i]
        g = _grams(r["text"])
        best, best_id = 0.0, ""
        for pid, g2 in seen[r["firm_id"]]:
            score = len(g & g2) / max(min(len(g), len(g2)), 1)
            if score > best:
                best, best_id = score, pid
        if best >= threshold:
            r["dup_of"], r["dup_score"] = best_id, f"{best:.2f}"
        else:
            r["dup_of"], r["dup_score"] = "", ""
            seen[r["firm_id"]].append((r["passage_id"], g))


# ------------------------------------------------------------------ coding sheet (never loses human input)
def merge_coding_sheet(existing: list[dict], passages: list[dict]) -> list[dict]:
    old = {r["passage_id"]: r for r in existing}
    rows = []
    for p in passages:
        r = {c: p.get(c, "") for c in CODING_COLS if c not in HUMAN_COLS}
        r.update({c: old.get(p["passage_id"], {}).get(c, "") for c in HUMAN_COLS})
        r["status"] = "duplicate" if p.get("dup_of") else "to_code"
        rows.append(r)
    current = {p["passage_id"] for p in passages}
    for pid, r in old.items():
        if pid not in current and any((r.get(c) or "").strip() for c in HUMAN_COLS):
            rows.append({**{c: r.get(c, "") for c in CODING_COLS}, "status": "orphaned"})
    return rows


# ------------------------------------------------------------------ documents to read
def documents(source: str, settings: dict) -> tuple[list[dict], str]:
    from part2_sample_docs import to_rows
    frozen, draft = PART2_OUT / "sample_manifest.csv", PART2_OUT / "sample_manifest_draft.csv"
    if source in ("auto", "sample") and frozen.exists():
        return read_csv(frozen), "frozen_sample"
    if source == "sample":
        raise SystemExit(f"No frozen sample at {frozen}. Run part2_sample_docs.py --freeze, or use --source all.")
    if source == "draft":
        if not draft.exists():
            raise SystemExit(f"No draft sample at {draft}. Run src/part2_sample_docs.py first.")
        return read_csv(draft), "draft_sample"
    filings, _ = scan_filings()
    pilot = set(settings.get("pilot_firms", []))
    rows = to_rows([f for f in filings if not pilot or f.firm_id in pilot], firm_info())
    for r in rows:
        r["sample_id"] = ""
    return rows, "all_available"


def main() -> None:
    settings = load_settings()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", choices=["auto", "sample", "draft", "all"], default="auto")
    ap.add_argument("--out", type=Path, default=PART2_OUT)
    args = ap.parse_args()

    docs, doc_set = documents(args.source, settings)
    if doc_set == "all_available":
        print("WARNING: no frozen sample yet - reading EVERY pilot filing on disk (provisional run).")
    print(f"Documents: {len(docs)} ({doc_set})")
    terms, sections = load_keywords(), load_sections()
    passages, stats, failed = [], defaultdict(Counter), []
    t0 = time.time()
    for d in docs:
        key = (d["firm_id"], d["form"])
        stats[key]["documents"] += 1
        for fp in [p for p in (d.get("file_paths") or "").split(";") if p]:
            path = ROOT / fp
            if not path.exists():
                failed.append((fp, "file not found"))
                stats[key]["files_failed"] += 1
                continue
            try:
                doc = read_text(path)
            except Exception as exc:                          # one bad file must not stop the run
                failed.append((fp, f"{type(exc).__name__}: {exc}"))
                stats[key]["files_failed"] += 1
                continue
            stats[key]["files_read"] += 1
            hits = find_hits(doc.text, terms)
            sidx = section_index(doc.text, sections.get(d["form"], []))
            for p in build_passages(doc.text, hits, settings):
                stats[key]["hits"] += len(p["hits"])
                names = Counter(h.matched for h in p["hits"])
                passages.append({
                    "passage_id": passage_id(d, path.name, p["char_start"]), "doc_set": doc_set,
                    "sample_id": d.get("sample_id", ""), "firm_id": d["firm_id"], "firm_name": d.get("firm_name", ""),
                    "sectors": d.get("sectors", ""), "quarter": d["quarter"], "fiscal_year": d.get("fiscal_year", ""),
                    "form": d["form"], "accession": d["accession"], "filing_date": d.get("filing_date", ""),
                    "file": path.name, "exhibit": exhibit_of(path.name) if d["form"] == "8-K" else "",
                    "section": section_at(p["char_start"], sidx), "page": doc.page_at(p["char_start"]) or "",
                    "char_start": p["char_start"], "char_end": p["char_end"],
                    "position_pct": f"{100 * p['char_start'] / max(len(doc.text), 1):.1f}",
                    "matched_terms": "; ".join(f"{k} x{v}" if v > 1 else k for k, v in names.most_common()),
                    "n_strong": sum(h.strength == "strong" for h in p["hits"]),
                    "n_weak": sum(h.strength == "weak" for h in p["hits"]),
                    "truncated": "yes" if p["truncated"] else "", "text": p["text"]})
    mark_duplicates(passages)
    for p in passages:
        stats[(p["firm_id"], p["form"])]["passages"] += 1
        stats[(p["firm_id"], p["form"])]["unique_passages"] += 0 if p["dup_of"] else 1

    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "ai_passages.csv", passages, PASSAGE_COLS)
    sheet = args.out / "open_coding_sheet.csv"
    coding = merge_coding_sheet(read_csv(sheet), passages)
    write_csv(sheet, coding, CODING_COLS)

    lines = ["# Part 2 extraction summary", "", f"Documents: {len(docs)} (`{doc_set}`); "
             f"passages: {len(passages)}, of which unique: {sum(not p['dup_of'] for p in passages)}; "
             f"run time {time.time() - t0:.0f}s.", "",
             "| Firm | Form | Documents | Files read | Files failed | AI hits | Passages | Unique |", "|---|---|---|---|---|---|---|---|"]
    for (firm, form), s in sorted(stats.items()):
        lines.append(f"| {firm} | {form} | {s['documents']} | {s['files_read']} | {s['files_failed']} | {s['hits']} | "
                     f"{s['passages']} | {s['unique_passages']} |")
    lines += ["", "## Documents read: fiscal year x firm | form x firm", "", "```",
              coverage_table([{**d, "fiscal_year": d.get("fiscal_year", "")} for d in docs]) if docs else "(none)", "```", ""]
    warns = coverage_warnings(docs, settings.get("pilot_firms", []), settings)
    if doc_set == "all_available":
        warns.insert(0, "Provisional: no frozen sample - every pilot filing on disk was read")
    if warns or failed:
        lines += ["## Warnings", ""] + [f"- {w}" for w in warns] + [f"- Could not read `{f}`: {why}" for f, why in failed]
    term_count = Counter(t.strip().split(" x")[0].lower() for p in passages
                         for t in set(p["matched_terms"].split(";")) if t.strip())
    lines += ["", "## Matched terms (passages containing each)", "", "| Term | Passages |", "|---|---|"]
    lines += [f"| {t} | {n} |" for t, n in term_count.most_common()]
    (args.out / "extraction_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines[4:4 + len(stats) + 2]))
    for w in warns:
        print(f"WARNING: {w}")
    for f, why in failed:
        print(f"WARNING: could not read {f}: {why}")
    kept = sum(1 for r in coding if r["status"] == "orphaned")
    print(f"\nWrote {args.out / 'ai_passages.csv'} ({len(passages)} passages), {sheet}"
          + (f" ({kept} orphaned rows with team input kept)" if kept else "") + f", {args.out / 'extraction_summary.md'}")


if __name__ == "__main__":
    main()
