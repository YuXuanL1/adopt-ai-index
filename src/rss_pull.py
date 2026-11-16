"""Collect item metadata from an official RSS/Atom feed after human approval.

This intentionally does *not* discover feeds or bypass a site's normal access route.
First save the site's terms, run part1_check_sources.py, and set that source's
human_decision to ``approved`` in outputs/part1/source_register.csv. Then run:

    python src/rss_pull.py --source businesswire --rss-url 'https://...'

The supplied URL must be an official feed for the reviewed source. The script still
checks robots.txt, sends the declared User-Agent, paces requests, caches the XML,
and writes only item metadata (not copied article bodies).
"""
from __future__ import annotations

import argparse
import csv
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

from config import DATA, OUTPUTS, user_agent
from polite_http import PoliteSession

ATOM = "{http://www.w3.org/2005/Atom}"


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def items_from_feed(xml: bytes) -> list[dict[str, str]]:
    """Return portable metadata from RSS 2.0 or Atom; never return full article HTML."""
    root = ET.fromstring(xml)
    items: list[dict[str, str]] = []
    for item in root.findall("./channel/item"):
        items.append({
            "title": clean(item.findtext("title")),
            "url": clean(item.findtext("link")),
            "published": clean(item.findtext("pubDate")),
            "summary": clean(item.findtext("description")),
        })
    for entry in root.findall(f"{ATOM}entry"):
        link = next((x.get("href", "") for x in entry.findall(f"{ATOM}link")
                     if x.get("rel", "alternate") == "alternate"), "")
        items.append({
            "title": clean(entry.findtext(f"{ATOM}title")),
            "url": clean(link),
            "published": clean(entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated")),
            "summary": clean(entry.findtext(f"{ATOM}summary") or entry.findtext(f"{ATOM}content")),
        })
    return items


def load_row(path: Path, source_id: str) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["source_id"] == source_id:
                return row
    raise SystemExit(f"Source '{source_id}' is not in {path}")


def approved(review_path: Path, source_id: str) -> bool:
    if not review_path.exists():
        return False
    with review_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("source_id") == source_id:
                return row.get("human_decision", "").strip().lower() == "approved"
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="source_id from data/sources.csv")
    ap.add_argument("--rss-url", help="official RSS/Atom URL; required unless sources.csv supplies one")
    ap.add_argument("--sources", default=str(DATA / "sources.csv"))
    ap.add_argument("--review", default=str(OUTPUTS / "part1" / "source_register.csv"))
    ap.add_argument("--out", default=str(OUTPUTS / "rss"))
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()

    source = load_row(Path(a.sources), a.source)
    if source.get("access_method", "").lower() != "rss":
        raise SystemExit(f"{a.source} is not configured as an RSS source.")
    if not approved(Path(a.review), a.source):
        raise SystemExit(
            "RSS collection is blocked until you review the terms and set human_decision to "
            "'approved' in outputs/part1/source_register.csv."
        )
    rss_url = a.rss_url or source.get("rss_url")
    if not rss_url:
        raise SystemExit("Provide the official feed URL with --rss-url after confirming it belongs to this source.")

    session = PoliteSession(user_agent(), offline=a.offline)
    entries = items_from_feed(session.get(rss_url))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{a.source}_items.csv"
    with target.open("w", newline="", encoding="utf-8") as fh:
        fields = ["source_id", "feed_url", "title", "url", "published", "summary"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for entry in entries:
            writer.writerow({"source_id": a.source, "feed_url": rss_url, **entry})
    session.save_log()
    print(f"Wrote {len(entries)} feed items to {target}")


if __name__ == "__main__":
    main()
