"""A deliberately small, compliant HTML scraper for approved public pages.

It does not discover URLs or work around access controls. Add reviewed page URLs to
data/web_targets.csv, set that source's ``access_method`` to ``web`` only if its
terms permit HTML automation, and set its ``human_decision`` to ``approved`` in the
Part 1 review register. Example:

    python src/web_scrape.py

For every target, this uses robots.txt, a declared User-Agent, rate limiting,
caching, and a request log through PoliteSession. It saves readable text only, not
the original HTML, and limits saved text to 30,000 characters by default.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from bs4 import BeautifulSoup

from config import DATA, OUTPUTS, user_agent
from polite_http import PoliteSession


def text_from_html(html: bytes, max_chars: int = 30_000) -> tuple[str, str]:
    """Extract a page title and readable visible text, omitting navigation/scripts."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "form"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = re.sub(r"\n{3,}", "\n\n", main.get_text("\n", strip=True))
    return title, text[:max_chars]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(row for row in fh if not row.lstrip().startswith("#")))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--targets", default=str(DATA / "web_targets.csv"))
    ap.add_argument("--sources", default=str(DATA / "sources.csv"))
    ap.add_argument("--review", default=str(OUTPUTS / "part1" / "source_register.csv"))
    ap.add_argument("--out", default=str(OUTPUTS / "web_scrape"))
    ap.add_argument("--max-chars", type=int, default=30_000)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()

    targets = read_rows(Path(a.targets))
    if not targets:
        raise SystemExit("Add reviewed target URLs to data/web_targets.csv first.")
    sources = {r["source_id"]: r for r in read_rows(Path(a.sources))}
    reviews = {r["source_id"]: r for r in read_rows(Path(a.review))}

    session = PoliteSession(user_agent(), offline=a.offline)
    out = Path(a.out)
    text_dir = out / "text"
    text_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for target in targets:
        source = sources.get(target["source_id"])
        review = reviews.get(target["source_id"], {})
        if source is None:
            raise SystemExit(f"Unknown source_id: {target['source_id']}")
        if source.get("access_method", "").strip().lower() != "web":
            raise SystemExit(f"{target['source_id']} is not approved for web scraping; keep it manual or use RSS/API.")
        if review.get("human_decision", "").strip().lower() != "approved":
            raise SystemExit(f"{target['source_id']} lacks a human 'approved' decision in the Part 1 register.")
        html = session.get(target["url"])
        title, text = text_from_html(html, a.max_chars)
        target_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", target["target_id"]).strip("_")
        saved = text_dir / f"{target_id}.txt"
        saved.write_text(text + "\n", encoding="utf-8")
        manifest.append({"target_id": target_id, "source_id": target["source_id"], "url": target["url"],
                         "purpose": target.get("purpose", ""), "title": title,
                         "text_file": str(saved.relative_to(out)), "characters_saved": len(text)})
        print(f"{target_id}: saved {len(text):,} characters")

    with (out / "manifest.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["target_id", "source_id", "url", "purpose", "title", "text_file", "characters_saved"])
        writer.writeheader()
        writer.writerows(manifest)
    session.save_log()
    print(f"Wrote {out / 'manifest.csv'}")


if __name__ == "__main__":
    main()
