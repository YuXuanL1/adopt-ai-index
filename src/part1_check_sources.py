"""PART 1 - Source review: robots.txt check + terms-of-use clause flagging.

For every site in data/sources.csv this script:
  1. downloads robots.txt (the one file every site publishes for crawlers) and tests
     whether the paths we plan to use are allowed for our User-Agent;
  2. reads the site's terms of use from data/terms/<source_id>.txt - a copy the team
     saves BY HAND from a browser (see README: we don't script sites before we know
     their terms allow it);
  3. splits the terms into sentences and flags clauses about automated access,
     AI/ML training, personal-use-only licences, reuse limits, permitted channels
     (API/RSS), rate limits and attribution, using keyword rules;
  4. writes a source register with an automatic recommendation and EMPTY columns for
     the human decision - a person must confirm every row before collection starts.

Outputs (outputs/part1/):
  source_register.csv   one row per site
  terms_evidence.csv    every flagged clause, so reviewers can read them
  robots/<id>_<date>.txt snapshots of each robots.txt (keep for the memo)

Run:  python src/part1_check_sources.py            (add --offline to use cache only)
"""
from __future__ import annotations

import argparse
import csv
import re
from datetime import date
from pathlib import Path

from config import DATA, OUTPUTS, user_agent
from polite_http import PoliteSession
from text_utils import split_sentences

# Keyword rules for each kind of clause we care about. Edit these as you read more terms.
CLAUSE_RULES: dict[str, re.Pattern] = {
    "automated_access": re.compile(
        r"\b(robots?|spiders?|crawl\w*|scrap\w*|data[\s-]?min\w*|harvest\w*|bots?|"
        r"automated (means|devices?|process\w*|tools?|access|systems?)|automatic (device|means|process)|"
        r"scripts?)\b", re.I),
    # "AI" and "LLM" must be capitals (so "said" or "mail" never match); the rest any case
    "ai_training": re.compile(
        r"\b(AI|LLMs?|(?i:machine learning|artificial intelligence|agentic|large language models?|"
        r"train(ing)? (an? |any )?(model|system|algorithm)s?))\b"),
    "personal_use_only": re.compile(
        r"\b(personal,? non-?commercial|non-?commercial use|personal use|individual use|"
        r"internal use only)\b", re.I),
    "reuse_limits": re.compile(
        r"\b(reproduc\w*|republish\w*|redistribut\w*|retransmit\w*|derivative works?|"
        r"stored? for (subsequent|later) use|frame|mirror|may not (be )?cop(y|ied))\b", re.I),
    "permitted_channels": re.compile(
        r"\b(RSS|APIs?|(?i:feeds?|bulk (data|download)\w*|developers?|download\w* (the )?data))\b"),
    "rate_limits": re.compile(
        r"\b(requests? per second|rate (limit|request)\w*|excessive (requests?|load)|"
        r"disproportionately large load|fair access|unreasonabl\w* load)\b", re.I),
    "attribution": re.compile(r"\b(attribut\w*|citation|cite|credit (to )?the)\b", re.I),
}


def flag_clauses(terms_text: str) -> dict[str, list[str]]:
    """Return {category: [matching sentences]} for one terms document."""
    found: dict[str, list[str]] = {k: [] for k in CLAUSE_RULES}
    for sent in split_sentences(terms_text):
        for cat, rule in CLAUSE_RULES.items():
            if rule.search(sent):
                found[cat].append(sent)
    return found


def recommend(access_method: str, license_ok: str, robots_ok: bool | None,
              flags: dict[str, list[str]] | None) -> str:
    """First-pass decision. A human confirms or overrides it in the register."""
    method = access_method.strip().lower()
    if license_ok.strip().lower() == "n":
        return "EXCLUDE - licence/plan does not permit this use"
    if robots_ok is False:
        return "EXCLUDE from scripts - robots.txt disallows our planned paths"
    if flags is None:
        return "BLOCKED - save the terms text in data/terms/ and re-run"
    if method in {"api", "bulk", "rss"}:
        return f"AUTOMATED OK via official {method.upper()} - confirm terms and limits"
    if flags["automated_access"] or flags["ai_training"]:
        return "MANUAL ONLY - terms restrict automated access or AI use"
    if flags["personal_use_only"] or flags["reuse_limits"]:
        return "MANUAL OR LIMITED - personal-use/reuse limits; quote briefly, cite"
    return "REVIEW - no restrictive clause flagged; read the full terms anyway"


def check_robots(s: PoliteSession, base_url: str, paths: list[str], snapshot_dir: Path,
                 source_id: str) -> tuple[bool | None, str, str]:
    """(all planned paths allowed?, crawl-delay, note)."""
    robots_url = base_url.rstrip("/") + "/robots.txt"
    try:
        rp = s.robots_for(base_url)
    except Exception as e:  # noqa: BLE001 - report any network problem in the register
        return None, "", f"could not fetch robots.txt ({type(e).__name__})"
    cached = s.cache_path(robots_url)
    if cached.exists():
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        (snapshot_dir / f"{source_id}_{date.today()}.txt").write_bytes(cached.read_bytes())
    if rp is None:
        return True, "", "no robots.txt published (no restrictions stated)"
    blocked = [p for p in paths if p and not rp.can_fetch(s.agent_token, base_url.rstrip("/") + p)]
    delay = rp.crawl_delay(s.agent_token)
    note = "all planned paths allowed" if not blocked else "disallowed: " + " ".join(blocked)
    return not blocked, str(delay or ""), note


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", default=str(DATA / "sources.csv"))
    ap.add_argument("--terms-dir", default=str(DATA / "terms"))
    ap.add_argument("--out", default=str(OUTPUTS / "part1"))
    ap.add_argument("--offline", action="store_true", help="use cached robots.txt only")
    ap.add_argument("--skip-robots", action="store_true", help="don't touch the network at all")
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    s = None if a.skip_robots else PoliteSession(user_agent(), offline=a.offline)
    terms_dir = Path(a.terms_dir)

    register, evidence = [], []
    with open(a.sources, newline="", encoding="utf-8") as fh:
        sources = list(csv.DictReader(fh))

    for src in sources:
        sid = src["source_id"]
        paths = [p.strip() for p in src["planned_paths"].split(";") if p.strip()]
        if s is None:
            robots_ok, delay, rnote = None, "", "skipped (--skip-robots)"
        else:
            robots_ok, delay, rnote = check_robots(s, src["base_url"], paths, out / "robots", sid)

        tfile = terms_dir / f"{sid}.txt"
        flags = flag_clauses(tfile.read_text(encoding="utf-8")) if tfile.exists() else None
        rec = recommend(src["access_method"], src.get("license_ok", ""),
                        robots_ok if robots_ok is not None else None, flags)

        row = {
            "source_id": sid, "name": src["name"], "terms_url": src["terms_url"],
            "access_method": src["access_method"], "planned_paths": src["planned_paths"],
            "robots_allows_paths": {True: "yes", False: "no", None: "unknown"}[robots_ok],
            "robots_crawl_delay_s": delay, "robots_note": rnote,
            "terms_saved": "yes" if flags is not None else "NO",
        }
        for cat in CLAUSE_RULES:
            row[f"n_{cat}"] = len(flags[cat]) if flags else ""
        row.update({"license_note": src.get("license_note", ""), "auto_recommendation": rec,
                    "human_decision": "", "reviewed_by": "", "review_date": ""})
        register.append(row)

        for cat, sents in (flags or {}).items():
            for sent in sents:
                evidence.append({"source_id": sid, "category": cat, "clause": sent[:600]})
        print(f"{sid:<16} robots={row['robots_allows_paths']:<7} terms={row['terms_saved']:<3} -> {rec}")

    with open(out / "source_register.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(register[0]))
        w.writeheader()
        w.writerows(register)
    with open(out / "terms_evidence.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["source_id", "category", "clause"])
        w.writeheader()
        w.writerows(evidence)
    if s:
        s.save_log()
    print(f"\nWrote {out / 'source_register.csv'} and {out / 'terms_evidence.csv'}")
    print("Next: read terms_evidence.csv, then fill human_decision / reviewed_by / review_date.")


if __name__ == "__main__":
    main()
