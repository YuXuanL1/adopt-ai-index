"""SEC EDGAR helpers shared by Part 1 (filing pull) and Part 1.5 (firm metadata).

Only SEC's official endpoints are used:
  https://data.sec.gov/submissions/CIK##########.json   - company info + filing list
  https://www.sec.gov/Archives/edgar/data/<cik>/<acc>/   - the filed documents
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from polite_http import PoliteSession

# Forms that carry narrative text about the business (and so about AI)
NARRATIVE_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "DEF 14A", "ARS", "20-F", "40-F"}
# Big banks file thousands of these structured-note supplements; they are noise
NOISE_FORMS = {"424B2", "424B3", "FWP", "13F-HR", "13F-HR/A", "11-K", "4", "3", "5", "SC 13G",
               "SC 13G/A", "N-PX"}


def cik10(cik: str | int) -> str:
    return str(int(str(cik).strip())).zfill(10)


@dataclass
class Filing:
    cik: str
    accession: str
    form: str
    filing_date: str
    report_date: str
    primary_doc: str
    items: str
    period_label: str = ""

    @property
    def folder_url(self) -> str:
        return (f"https://www.sec.gov/Archives/edgar/data/{int(self.cik)}/"
                f"{self.accession.replace('-', '')}")

    @property
    def doc_url(self) -> str:
        return f"{self.folder_url}/{self.primary_doc}"

    @property
    def index_url(self) -> str:
        return f"{self.folder_url}/{self.accession}-index.htm"


def get_submissions(s: PoliteSession, cik: str | int, refresh_days: float = 1) -> dict:
    """Company record: name, SIC code, tickers, fiscal year end, and recent filings."""
    return s.get_json(f"https://data.sec.gov/submissions/CIK{cik10(cik)}.json",
                      max_age_days=refresh_days)


def _rows(block: dict, cik: str) -> list[Filing]:
    n = len(block["accessionNumber"])
    def col(name):
        return block.get(name) or [""] * n
    return [Filing(cik=cik10(cik), accession=block["accessionNumber"][i], form=block["form"][i],
                   filing_date=block["filingDate"][i], report_date=col("reportDate")[i] or "",
                   primary_doc=col("primaryDocument")[i] or "", items=col("items")[i] or "")
            for i in range(n)]


def all_filings(s: PoliteSession, sub: dict, since: date | None = None) -> list[Filing]:
    """Every filing for a company filed on or after `since` (None = all of them).

    The 'recent' block holds only ~1,000 filings. Firms like JPMorgan file thousands of
    note supplements a year, so older 10-Qs sit in extra pages listed under filings.files.
    We fetch only the extra pages that overlap the window we need.
    """
    cik = sub["cik"]
    out = _rows(sub["filings"]["recent"], cik)
    for page in sub["filings"].get("files", []):
        page_to = page.get("filingTo", "")
        if since and page_to and date.fromisoformat(page_to) < since:
            continue
        out += _rows(s.get_json(f"https://data.sec.gov/submissions/{page['name']}",
                                max_age_days=30), cik)
    return out


def quarter_of(d: date) -> str:
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def previous_quarter_of(d: date) -> str:
    q = (d.month - 1) // 3 + 1
    return f"{d.year - 1}Q4" if q == 1 else f"{d.year}Q{q - 1}"


def select_for_backfill(filings: list[Filing], start: date, end: date) -> list[Filing]:
    """Keep the narrative filings for the backfill window.

    * 10-K / 10-Q: keep if the period they report on is inside the window.
    * 8-K: keep only earnings releases (Item 2.02), labelled with the quarter they report.
    * DEF 14A / ARS: keep once a year if filed in the window (or the April after it).
    Quarter labels are calendar quarters of the period end date.
    """
    keep = []
    for f in filings:
        if f.form not in NARRATIVE_FORMS:
            continue
        fdate = date.fromisoformat(f.filing_date)
        if f.form.startswith(("10-K", "10-Q", "20-F", "40-F")):
            if not f.report_date:
                continue
            period = date.fromisoformat(f.report_date)
            if not start <= period <= end:
                continue
            f.period_label = quarter_of(period)
        elif f.form == "8-K":
            if "2.02" not in f.items:
                continue
            label = previous_quarter_of(fdate)
            year, q = int(label[:4]), int(label[-1])
            if not start <= date(year, q * 3, 28) <= end:
                continue
            f.period_label = label
        else:  # DEF 14A, ARS
            if not start <= fdate <= date(end.year + 1, 4, 30):
                continue
            f.period_label = f"{fdate.year}-annual"
        keep.append(f)
    return sorted(keep, key=lambda f: (f.filing_date, f.form))


def latest(filings: list[Filing], forms: list[str]) -> Filing | None:
    """Most recent filing whose form is in `forms`, trying the forms in the order given."""
    for form in forms:
        hits = [f for f in filings if f.form == form and f.primary_doc]
        if hits:
            return max(hits, key=lambda f: f.filing_date)
    return None


def exhibit_names(s: PoliteSession, f: Filing) -> list[str]:
    """File names of EX-99 exhibits (earnings release, supplement) in an 8-K."""
    idx = s.get_json(f"{f.folder_url}/index.json")
    names = [item["name"] for item in idx["directory"]["item"]]
    def is_ex99(n: str) -> bool:
        low = n.lower().replace("-", "").replace("_", "")
        return low.endswith((".htm", ".html", ".pdf", ".txt")) and ("ex99" in low or "exhibit99" in low
                                                                   or "991" in low or "992" in low)
    return [n for n in names if is_ex99(n)]
