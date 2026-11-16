"""PART 2 - Draw the stratified document sample used to build the taxonomy (target 30-50 filings).

Unit = one filing (an 8-K's cover, press release and supplement count as one document).
Strata = firm x form, with the number per firm in data/part2_sample_plan.csv (default 9 per bank:
5 banks -> 45). Inside each firm x form the picks are spread over different fiscal years. Each
firm x form has its own seeded random stream, so adding a new bank later does not change the
picks for banks already in the sample.

Only files already on disk are used (data/raw/edgar/, hard links to data/cache/). Nothing is downloaded.

Two stages, so later downloads cannot silently change the sample:
  draft   (default)   writes outputs/part2/sample_manifest_draft.csv - re-run freely
  frozen  --freeze    writes outputs/part2/sample_manifest.csv - refuses if it already exists
          --freeze --resample --reason "..."  replaces it; the old one goes to outputs/part2/archive/
Every freeze/resample is logged in outputs/part2/sample_log.csv.

Also writes outputs/part2/filing_inventory.csv (every filing on disk) and prints a coverage
summary with warnings (one firm only, one year only, too few documents, missing files).

Run:
  python src/part2_sample_docs.py                                  draft + coverage report
  python src/part2_sample_docs.py --freeze --reason "5 banks downloaded, approved by team"
  python src/part2_sample_docs.py --freeze --resample --reason "WFC 2023 filings added"
"""
from __future__ import annotations

import argparse
import random
import shutil
from collections import defaultdict
from datetime import datetime

from config import DATA, OUTPUTS, RAW_EDGAR
from part2_common import (PART2_OUT, FilingDoc, coverage_table, coverage_warnings, firm_info, load_settings,
                          read_csv, rel, scan_filings, write_csv)

OUT = PART2_OUT                                    # module-level so tests can point them elsewhere
RAW_ROOT = RAW_EDGAR
P1_MANIFEST = OUTPUTS / "part1" / "edgar_manifest.csv"
MANIFEST_COLS = ["sample_id", "firm_id", "firm_name", "sectors", "quarter", "fiscal_year", "form", "accession",
                 "filing_date", "report_date", "n_files", "file_paths", "index_url", "stratum", "in_part1_manifest"]
LOG_COLS = ["timestamp", "action", "reason", "seed", "n_docs", "firms", "plan", "archived_as"]


def load_plan(path=DATA / "part2_sample_plan.csv") -> dict[str, int]:
    return {r["form"].strip(): int(r["docs_per_firm"]) for r in read_csv(path) if r.get("form")}


def pick_spread(filings: list[FilingDoc], n: int, rng: random.Random) -> list[FilingDoc]:
    """n filings spread over as many fiscal years as possible (random year order, random filing per year)."""
    by_year = defaultdict(list)
    for f in sorted(filings, key=lambda f: f.accession):
        by_year[f.fiscal_year].append(f)
    years = sorted(by_year)
    rng.shuffle(years)
    picked = []
    while len(picked) < n and any(by_year.values()):
        for y in years:
            if by_year[y] and len(picked) < n:
                picked.append(by_year[y].pop(rng.randrange(len(by_year[y]))))
    return picked


def draw(filings: list[FilingDoc], plan: dict[str, int], firms: list[str], seed: int) -> list[FilingDoc]:
    sample = []
    for firm in firms:
        for form, n in plan.items():
            pool = [f for f in filings if f.firm_id == firm and f.form == form and f.fiscal_year is not None]
            rng = random.Random(f"{seed}|{firm}|{form}")         # independent stream per stratum
            sample += pick_spread(pool, n, rng)
    return sorted(sample, key=lambda f: (f.firm_id, f.fiscal_year, f.period, f.form, f.accession))


def to_rows(sample: list[FilingDoc], info: dict) -> list[dict]:
    rows = []
    for i, f in enumerate(sample, 1):
        rows.append({"sample_id": f"S{i:03d}", "firm_id": f.firm_id, "firm_name": info.get(f.firm_id, {}).get("name", ""),
                     "sectors": info.get(f.firm_id, {}).get("sectors", ""), "quarter": f.period,
                     "fiscal_year": f.fiscal_year, "form": f.form, "accession": f.accession,
                     "filing_date": f.filing_date, "report_date": f.report_date, "n_files": len(f.files),
                     "file_paths": ";".join(rel(p) for p in f.files), "index_url": f.index_url,
                     "stratum": f"{f.firm_id}|{f.form}", "in_part1_manifest": "yes" if f.in_manifest else "no"})
    return rows


def main() -> None:
    settings = load_settings()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--firms", nargs="*", help="firm_ids (default: pilot_firms in data/part2_settings.json)")
    ap.add_argument("--seed", type=int, default=settings.get("seed", 0))
    ap.add_argument("--freeze", action="store_true", help="write the frozen outputs/part2/sample_manifest.csv")
    ap.add_argument("--resample", action="store_true", help="with --freeze: replace an existing frozen sample")
    ap.add_argument("--reason", default="", help="required with --freeze: why this sample is being fixed")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    frozen = OUT / "sample_manifest.csv"
    if args.freeze and not args.reason.strip():
        raise SystemExit('--freeze needs --reason "..." (it is written to sample_log.csv)')
    if args.freeze and frozen.exists() and not args.resample:
        raise SystemExit(f"{frozen} is FROZEN. To replace it on purpose: --freeze --resample --reason \"...\"")

    pilot = args.firms or settings.get("pilot_firms", [])
    plan = load_plan()
    info = firm_info()
    filings, problems = scan_filings(RAW_ROOT, P1_MANIFEST)

    inv_rows = to_rows(filings, info)
    for r in inv_rows:
        r.pop("sample_id")
    write_csv(OUT / "filing_inventory.csv", inv_rows, [c for c in MANIFEST_COLS if c != "sample_id"])

    print("== Filings on disk (data/raw/edgar) - fiscal year x firm | form x firm")
    print(coverage_table(inv_rows) if inv_rows else "  (none)")
    unplanned = sorted({f.form for f in filings} - set(plan))
    if unplanned:
        print(f"Forms on disk but not in data/part2_sample_plan.csv (ignored): {', '.join(unplanned)}")
    for p in problems:
        print(f"  MISSING: {p['firm_id']} {p['accession']}: {p['issue']}")

    sample = draw(filings, plan, pilot, args.seed)
    rows = to_rows(sample, info)
    print(f"\n== Sample (seed {args.seed}, plan per firm: "
          + ", ".join(f"{k} {v}" for k, v in plan.items()) + f") - {len(rows)} documents")
    print(coverage_table(rows, [f for f in pilot if any(r['firm_id'] == f for r in rows)]) if rows else "  (empty)")
    short = [(firm, form, n, sum(1 for r in rows if r["firm_id"] == firm and r["form"] == form))
             for firm in pilot for form, n in plan.items()]
    short = [s for s in short if s[3] < s[2] and any(r["firm_id"] == s[0] for r in rows)]
    for firm, form, want, got in short:
        print(f"  short: {firm} {form}: {got} of {want} available")
    warnings = coverage_warnings(rows, pilot, settings)
    for w in warnings:
        print(f"WARNING: {w}")

    if not args.freeze:
        write_csv(OUT / "sample_manifest_draft.csv", rows, MANIFEST_COLS)
        print(f"\nDRAFT written: {OUT / 'sample_manifest_draft.csv'} (not frozen).")
        if frozen.exists():
            kept = {r["accession"] for r in read_csv(frozen)}
            new = [r for r in rows if r["accession"] not in kept]
            print(f"A FROZEN sample exists ({len(kept)} docs) and stays in use. "
                  f"{len(new)} draft documents are not in it.")
        else:
            print('When the team approves it: python src/part2_sample_docs.py --freeze --reason "..."')
        return

    archived = ""
    if frozen.exists():
        arch = OUT / "archive"
        arch.mkdir(exist_ok=True)
        archived = f"archive/sample_manifest_{datetime.now():%Y%m%d_%H%M%S}.csv"
        shutil.move(str(frozen), OUT / archived)
        print(f"Old frozen sample moved to outputs/part2/{archived}")
    write_csv(frozen, rows, MANIFEST_COLS)
    log = OUT / "sample_log.csv"
    old_log = read_csv(log)
    old_log.append({"timestamp": datetime.now().isoformat(timespec="seconds"),
                    "action": "resample" if archived else "freeze", "reason": args.reason.strip(),
                    "seed": args.seed, "n_docs": len(rows), "firms": ";".join(sorted({r["firm_id"] for r in rows})),
                    "plan": ";".join(f"{k}:{v}" for k, v in plan.items()), "archived_as": archived})
    write_csv(log, old_log, LOG_COLS)
    print(f"\nFROZEN: {frozen} ({len(rows)} documents). Logged in {log}.")
    if warnings:
        print("Frozen WITH the warnings above - say so in the methodology.")


if __name__ == "__main__":
    main()
