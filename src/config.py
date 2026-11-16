"""Shared settings: paths, the SEC User-Agent, and a tiny .env loader.

Every script imports this first. Put your team's contact in a file called .env
in the project folder (copy .env.example), e.g.

    EDGAR_USER_AGENT=TeamName AI-Adoption-Index (Intro to AI) team-email@school.edu
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTPUTS = ROOT / "outputs"
CACHE = DATA / "cache"          # every downloaded file lands here, keyed by URL
RAW_EDGAR = DATA / "raw" / "edgar"


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Read KEY=VALUE lines from .env into os.environ (no extra package needed)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()


def user_agent() -> str:
    """The declared identity sent with every request. SEC requires a name + email."""
    ua = os.environ.get("EDGAR_USER_AGENT", "").strip()
    if "@" not in ua or len(ua.split()) < 2:
        raise SystemExit(
            "Set EDGAR_USER_AGENT in .env to your team name plus a shared team email,\n"
            "e.g. EDGAR_USER_AGENT=TeamName AI-Adoption-Index team-email@school.edu"
        )
    return ua


# Request pacing (requests per second). SEC's ceiling is 10/s across ALL of a team's
# machines, so we use half. Every other site gets one request every 5 seconds.
SEC_MAX_RPS = 5.0
OTHER_MAX_RPS = 0.2
