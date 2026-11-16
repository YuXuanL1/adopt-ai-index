"""Collect recent AI-related news *metadata* from GDELT's official DOC API.

Example (one firm):
    python src/gdelt_news.py --firms jpm

The query combines the firm's official name with AI terms. Results contain titles,
publication timestamps, publishers, and original URLs. This script does not download
or store article bodies; read and cite any article manually before relying on it.
GDELT searches recent coverage (up to three months for article lists), so SEC filings
remain the historical backbone of the index.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from urllib.parse import urlencode

from config import DATA, OUTPUTS, user_agent
from polite_http import PoliteSession

API = "https://api.gdeltproject.org/api/v2/doc/doc"
AI_QUERY = '(AI OR "artificial intelligence" OR "machine learning" OR "generative AI")'


def article_rows(payload: dict, firm_id: str, firm_name: str, query: str) -> list[dict[str, str]]:
    """Normalize the fields returned by GDELT ArtList JSON."""
    rows = []
    for item in payload.get("articles", []):
        rows.append({
            "firm_id": firm_id, "firm_name": firm_name, "query": query,
            "title": str(item.get("title", "")), "url": str(item.get("url", "")),
            "published": str(item.get("seendate", "")), "publisher_domain": str(item.get("domain", "")),
            "language": str(item.get("language", "")), "source_country": str(item.get("sourcecountry", "")),
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--firms", help="semicolon-separated firm IDs; omit for all firms")
    ap.add_argument("--timespan", default="3months", help="GDELT period, e.g. 7days or 3months")
    ap.add_argument("--max-records", type=int, default=50, choices=range(1, 251))
    ap.add_argument("--out", default=str(OUTPUTS / "news"))
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()

    with (DATA / "firms.csv").open(newline="", encoding="utf-8") as fh:
        firms = list(csv.DictReader(fh))
    wanted = set(a.firms.split(";")) if a.firms else {f["firm_id"] for f in firms}
    selected = [f for f in firms if f["firm_id"] in wanted]
    missing = wanted - {f["firm_id"] for f in selected}
    if missing:
        raise SystemExit(f"Unknown firm IDs: {', '.join(sorted(missing))}")

    session = PoliteSession(user_agent(), offline=a.offline)
    all_rows = []
    for firm in selected:
        query = f'"{firm["name"]}" {AI_QUERY}'
        url = API + "?" + urlencode({"query": query, "mode": "ArtList", "format": "json",
                                      "maxrecords": a.max_records, "timespan": a.timespan,
                                      "sort": "DateDesc"})
        rows = article_rows(session.get_json(url, max_age_days=1), firm["firm_id"], firm["name"], query)
        all_rows.extend(rows)
        print(f"{firm['firm_id']}: {len(rows)} GDELT news results")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "gdelt_articles.csv"
    fields = ["firm_id", "firm_name", "query", "title", "url", "published", "publisher_domain", "language", "source_country"]
    with target.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_rows)
    session.save_log()
    print(f"Wrote {len(all_rows)} article records to {target}")


if __name__ == "__main__":
    main()
