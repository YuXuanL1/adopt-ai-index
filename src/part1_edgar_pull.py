"""PART 1 - Pull the narrative SEC filings for every firm in data/firms.csv that has a CIK.

Per firm and quarter it downloads the 10-Q (or 10-K), the earnings 8-K with its
EX-99 exhibits (press release, financial supplement), and once a year the proxy
(DEF 14A) and annual report (ARS). Structured-note supplements (424B2, FWP),
13F holdings and 11-K plan reports are skipped.

Window: ends Q3 2026 (--end) and goes back as many quarters as data/sector_plan.csv
asks for the firm's sectors - 12 by default, 16 for retirement firms (deeper coverage
for the book chapter). --start overrides this for every firm.
Quarter labels are CALENDAR quarters of the period end; firms with other fiscal
years (e.g. Wealthfront, January year-end) keep their real report dates in the manifest.

Outputs:
  data/raw/edgar/<firm_id>/<quarter>/<form>_<accession>/<files>
  outputs/part1/edgar_manifest.csv      one row per filing, with links
  outputs/compliance/request_log_*.json every request made

Run:
  python src/part1_edgar_pull.py --dry-run              list what would be downloaded
  python src/part1_edgar_pull.py --firms jpm            one firm
  python src/part1_edgar_pull.py                        every SEC filer in firms.csv
"""
from __future__ import annotations

import argparse
import csv
import os
from collections import Counter
from datetime import date
from pathlib import Path

from config import DATA, OUTPUTS, RAW_EDGAR, user_agent
from edgar import all_filings, exhibit_names, get_submissions, select_for_backfill
from polite_http import PoliteSession


def save_filing_file(s: PoliteSession, url: str, dest: Path) -> None:
    """Put the file at dest WITHOUT a second copy on disk.

    s.get() downloads it into data/cache/ (or reuses the cached copy); dest is then a hard link to
    that cached file - two names, one copy. Deleting either name keeps the other. Falls back to a
    normal copy if the filesystem can't link (e.g. cache on another drive).
    """
    body = s.get(url)
    cached = s.cache_path(url)
    if dest.exists() or dest.is_symlink():
        dest.unlink()
    try:
        os.link(cached, dest)
    except OSError:
        dest.write_bytes(body)


def quarter_start(end: date, quarters: int) -> date:
    """First day of the window that ends with end's quarter and spans `quarters` quarters."""
    q_index = end.year * 4 + (end.month - 1) // 3 - (quarters - 1)
    return date(q_index // 4, (q_index % 4) * 3 + 1, 1)


def backfill_depth(firm: dict) -> int:
    """Deepest backfill among the firm's sectors (data/sector_plan.csv; retirement = 16)."""
    plan = {r["sector_id"]: int(r["backfill_quarters"] or 12)
            for r in csv.DictReader(open(DATA / "sector_plan.csv", newline="", encoding="utf-8"))}
    sectors = firm.get("hand_sectors", "")
    universe = OUTPUTS / "part15" / "firm_universe.csv"   # use confirmed tags once Part 1.5 has run
    if universe.exists():
        for r in csv.DictReader(open(universe, newline="", encoding="utf-8")):
            if r["firm_id"] == firm["firm_id"] and r.get("final_sectors"):
                sectors = r["final_sectors"]
    depths = [plan.get(t.strip(), 12) for t in sectors.split(";") if t.strip()]
    return max(depths or [12])


def load_firms(path: Path, only: list[str] | None) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        firms = [r for r in csv.DictReader(fh) if r["cik"].strip()]
    if only:
        firms = [f for f in firms if f["firm_id"] in only]
    return firms


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--firms", nargs="*", help="firm_ids to pull (default: all with a CIK)")
    ap.add_argument("--start", help="override the window start for every firm (YYYY-MM-DD)")
    ap.add_argument("--end", default="2026-09-30", help="last quarter's end date")
    ap.add_argument("--dry-run", action="store_true", help="list filings, download nothing")
    ap.add_argument("--no-exhibits", action="store_true", help="skip 8-K EX-99 exhibits")
    ap.add_argument("--offline", action="store_true", help="cache only")
    a = ap.parse_args()

    end = date.fromisoformat(a.end)
    s = PoliteSession(user_agent(), offline=a.offline)
    firms = load_firms(DATA / "firms.csv", a.firms)
    manifest = []

    for firm in firms:
        quarters = backfill_depth(firm)
        start = date.fromisoformat(a.start) if a.start else quarter_start(end, quarters)
        sub = get_submissions(s, firm["cik"])
        chosen = select_for_backfill(all_filings(s, sub, since=start), start, end)
        counts = Counter(f.form for f in chosen)
        print(f"\n{firm['firm_id']}: {sub['name']} (CIK {sub['cik']}, SIC {sub.get('sic')}) - "
              f"{start} to {end} ({quarters} quarters) - "
              + ", ".join(f"{k} x{v}" for k, v in sorted(counts.items())))
        for f in chosen:
            files = [f.primary_doc]
            if not a.dry_run:
                folder = RAW_EDGAR / firm["firm_id"] / f.period_label / f"{f.form.replace(' ', '').replace('/', '-')}_{f.accession}"
                folder.mkdir(parents=True, exist_ok=True)
                save_filing_file(s, f.doc_url, folder / f.primary_doc)
                if f.form == "8-K" and not a.no_exhibits:
                    for ex in exhibit_names(s, f):
                        if ex != f.primary_doc:
                            save_filing_file(s, f"{f.folder_url}/{ex}", folder / ex)
                            files.append(ex)
            manifest.append({"firm_id": firm["firm_id"], "firm_name": firm["name"], "cik": f.cik,
                             "period": f.period_label, "form": f.form, "filing_date": f.filing_date,
                             "report_date": f.report_date, "accession": f.accession,
                             "files": ";".join(files), "index_url": f.index_url})
            print(f"   {f.period_label:<12} {f.form:<8} filed {f.filing_date}  {f.accession}")

    out = OUTPUTS / "part1"
    out.mkdir(parents=True, exist_ok=True)
    if manifest:
        with open(out / "edgar_manifest.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(manifest[0]))
            w.writeheader()
            w.writerows(manifest)
        print(f"\nManifest: {out / 'edgar_manifest.csv'}  ({len(manifest)} filings)")
    log = s.save_log()
    if log:
        print(f"Request log: {log}")


if __name__ == "__main__":
    main()
