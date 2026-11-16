"""Shared helpers for the Part 2 scripts: settings, what filings are on disk, reading text, AI-term matching.

Nothing here touches the network. The source of truth for what exists is the folder tree
data/raw/edgar/<firm>/<period>/<FORM>_<accession>/ (hard links to the files in data/cache/).
outputs/part1/edgar_manifest.csv only adds filing dates and links: part1_edgar_pull.py rewrites it
on every run, so after `--firms bac` it would list BAC alone.
"""
from __future__ import annotations

import bisect
import csv
import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from config import DATA, OUTPUTS, RAW_EDGAR, ROOT

PART2_OUT = OUTPUTS / "part2"
FORM_DIRS = {"DEF14A": "DEF 14A"}          # folder names drop the space


# ------------------------------------------------------------------ settings and CSV helpers
def load_settings(path: Path = DATA / "part2_settings.json") -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def rel(path: Path) -> str:
    """Path relative to the project folder, with forward slashes (portable in CSVs)."""
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


# ------------------------------------------------------------------ what is on disk
@dataclass
class FilingDoc:
    firm_id: str
    period: str                 # folder label: 2025Q4 or 2026-annual
    form: str
    accession: str
    folder: Path
    files: list[Path] = field(default_factory=list)
    filing_date: str = ""
    report_date: str = ""
    index_url: str = ""
    in_manifest: bool = False

    @property
    def fiscal_year(self) -> int | None:
        """Year the filing reports on. '2026-annual' (proxy + annual report filed in 2026) covers FY2025."""
        m = re.match(r"(\d{4})Q[1-4]$", self.period)
        if m:
            return int(m.group(1))
        m = re.match(r"(\d{4})-annual$", self.period)
        return int(m.group(1)) - 1 if m else None


def scan_filings(raw_root: Path = RAW_EDGAR, manifest: Path = OUTPUTS / "part1" / "edgar_manifest.csv"
                 ) -> tuple[list[FilingDoc], list[dict]]:
    """Every filing folder on disk, enriched from the Part 1 manifest.

    Returns (filings, problems). problems lists manifest rows whose folder or files are missing,
    and folders that hold no files - nothing raises, so a half-finished Part 1 still works.
    """
    by_acc = {r["accession"]: r for r in read_csv(manifest)}
    filings, problems = [], []
    if raw_root.exists():
        for folder in sorted(p for p in raw_root.glob("*/*/*") if p.is_dir()):
            firm_id, period = folder.parent.parent.name, folder.parent.name
            if "_" not in folder.name:
                continue
            form_dir, accession = folder.name.split("_", 1)
            files = sorted(p for p in folder.iterdir() if p.is_file() and not p.name.startswith("."))
            m = by_acc.get(accession, {})
            fd = FilingDoc(firm_id, period, m.get("form") or FORM_DIRS.get(form_dir, form_dir), accession,
                           folder, files, m.get("filing_date", ""), m.get("report_date", ""),
                           m.get("index_url", ""), bool(m))
            if not files:
                problems.append({"accession": accession, "firm_id": firm_id, "issue": "folder is empty"})
                continue
            filings.append(fd)
    on_disk = {f.accession: f for f in filings}
    for acc, m in by_acc.items():
        if acc not in on_disk:
            problems.append({"accession": acc, "firm_id": m.get("firm_id", ""), "issue": "in manifest, not on disk"})
            continue
        names = {p.name for p in on_disk[acc].files}
        missing = [n for n in (m.get("files") or "").split(";") if n and n not in names]
        if missing:
            problems.append({"accession": acc, "firm_id": m.get("firm_id", ""),
                             "issue": "files missing: " + ";".join(missing)})
    return filings, problems


def firm_info() -> dict[str, dict]:
    """firm_id -> {name, sectors}. Sectors: Part 1.5 final_sectors > sectors > hand_sectors in firms.csv."""
    info = {r["firm_id"]: {"name": r.get("name", ""), "sectors": r.get("hand_sectors", "")}
            for r in read_csv(DATA / "firms.csv")}
    for r in read_csv(OUTPUTS / "part15" / "firm_universe.csv"):
        d = info.setdefault(r["firm_id"], {"name": r.get("name", ""), "sectors": ""})
        d["sectors"] = r.get("final_sectors") or r.get("sectors") or d["sectors"]
    return info


def coverage_table(rows: list[dict], firms: list[str] | None = None) -> str:
    """Plain-text table: firm x fiscal year counts, then firm x form counts."""
    firms = firms or sorted({r["firm_id"] for r in rows})
    years = sorted({str(r["fiscal_year"]) for r in rows})
    forms = sorted({r["form"] for r in rows})
    by_year = Counter((r["firm_id"], str(r["fiscal_year"])) for r in rows)
    by_form = Counter((r["firm_id"], r["form"]) for r in rows)
    lines = ["firm      " + "".join(f"{y:>8}" for y in years) + "   |" + "".join(f"{f:>9}" for f in forms) + "   total"]
    for firm in firms:
        tot = sum(by_year[(firm, y)] for y in years)
        lines.append(f"{firm:<10}" + "".join(f"{by_year[(firm, y)]:>8}" for y in years) + "   |"
                     + "".join(f"{by_form[(firm, f)]:>9}" for f in forms) + f"{tot:>8}")
    return "\n".join(lines)


def coverage_warnings(rows: list[dict], pilot: list[str], settings: dict) -> list[str]:
    """Gaps that would bias a sample (asked for in the brief: one bank only, one year only, too few docs)."""
    warn = []
    firms = {r["firm_id"] for r in rows}
    missing = [f for f in pilot if f not in firms]
    if missing:
        warn.append(f"No filings on disk for pilot firms: {', '.join(missing)} (Part 1 not yet run for them)")
    if len(firms) == 1:
        warn.append(f"Only ONE firm ({next(iter(firms))}): the taxonomy will describe that firm, not the sector")
    years = {r["fiscal_year"] for r in rows}
    if len(years) <= 1:
        warn.append(f"Only one fiscal year ({', '.join(map(str, years)) or 'none'}): no change over time visible")
    n = len(rows)
    if n < settings.get("target_docs_min", 30):
        warn.append(f"{n} documents < target minimum {settings.get('target_docs_min', 30)}")
    if n > settings.get("target_docs_max", 50):
        warn.append(f"{n} documents > target maximum {settings.get('target_docs_max', 50)}")
    return warn


# ------------------------------------------------------------------ reading text
@dataclass
class DocText:
    text: str
    page_starts: list[int] = field(default_factory=list)    # PDFs only: char offset where each page starts

    def page_at(self, offset: int) -> int | None:
        if not self.page_starts:
            return None
        return bisect.bisect_right(self.page_starts, offset)


def read_text(path: Path) -> DocText:
    """HTML -> plain text (Part 1's html_to_text); PDF -> text page by page with page offsets."""
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader                       # imported here: only needed for annual reports
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        parts, starts, pos = [], [], 0
        for page in PdfReader(str(path)).pages:
            t = re.sub(r"\s+", " ", page.extract_text() or "").strip()
            starts.append(pos)
            parts.append(t)
            pos += len(t) + 1
        return DocText(" ".join(parts), starts)
    from text_utils import html_to_text
    return DocText(html_to_text(path.read_bytes()))


# Same sentence rule as text_utils.split_sentences, but keeping character offsets.
_SENT_BREAK = re.compile(r"(?<=[\.\;\!\?])\s+(?=[A-Z\(\"“0-9•])|\s+(?=•)")


def sentence_spans(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in _SENT_BREAK.finditer(text):
        if m.start() > start:
            spans.append((start, m.start()))
        start = m.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans


# ------------------------------------------------------------------ AI terms
@dataclass
class Term:
    term_id: str
    regex: re.Pattern
    strength: str              # strong | weak | exclude


def load_keywords(path: Path = DATA / "ai_keywords.csv") -> list[Term]:
    terms = []
    for r in read_csv(path):
        flags = 0 if (r.get("case_sensitive") or "n").strip().lower().startswith("y") else re.I
        strength = (r.get("strength") or "").strip().lower()
        if strength not in ("strong", "weak", "exclude"):
            raise SystemExit(f"{path.name}: term '{r.get('term_id')}' has strength '{strength}' (use strong/weak/exclude)."
                             " A pattern containing a comma must be in double quotes.")
        try:
            terms.append(Term(r["term_id"], re.compile(r["pattern"], flags), strength))
        except re.error as exc:
            raise SystemExit(f"{path.name}: bad regex for term '{r['term_id']}': {exc}")
    return terms


@dataclass
class Hit:
    term_id: str
    strength: str
    start: int
    end: int
    matched: str


def find_hits(text: str, terms: list[Term]) -> list[Hit]:
    """All strong/weak matches, minus any that sit inside an 'exclude' match (e.g. 'Merrill Lynch (ML)')."""
    excl = [(m.start(), m.end()) for t in terms if t.strength == "exclude" for m in t.regex.finditer(text)]
    hits = []
    for t in terms:
        if t.strength == "exclude":
            continue
        for m in t.regex.finditer(text):
            if any(s <= m.start() and m.end() <= e for s, e in excl):
                continue
            hits.append(Hit(t.term_id, t.strength, m.start(), m.end(), m.group(0)))
    return sorted(hits, key=lambda h: h.start)


def load_sections(path: Path = DATA / "part2_sections.csv") -> dict[str, list[tuple[str, re.Pattern]]]:
    out: dict[str, list] = defaultdict(list)
    for r in read_csv(path):
        flags = 0 if (r.get("case_sensitive") or "n").strip().lower().startswith("y") else re.I
        for form in r["forms"].split(";"):
            out[form.strip()].append((r["label"], re.compile(r["pattern"], flags)))
    return out


def section_index(text: str, rules: list[tuple[str, re.Pattern]]) -> tuple[list[int], list[str]]:
    """Sorted (offset, label) of every heading match; the section of a hit = nearest heading before it."""
    marks = sorted((m.start(), label) for label, rx in rules for m in rx.finditer(text))
    return [o for o, _ in marks], [lab for _, lab in marks]


def section_at(offset: int, idx: tuple[list[int], list[str]]) -> str:
    offs, labels = idx
    i = bisect.bisect_right(offs, offset) - 1
    return labels[i] if i >= 0 else ""
