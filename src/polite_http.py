"""A polite HTTP client: the Part 1 memo's rules, enforced in code.

* Declares who we are (User-Agent with a team email) on every request.
* Paces requests per site: 5/s for SEC (shared across sec.gov hosts), 1 per 5 s elsewhere.
* Checks robots.txt before fetching any page, and refuses if it disallows us.
* Caches every response on disk by URL and never downloads the same thing twice.
* Honors Retry-After, backs off exponentially, and stops after 3 straight failures.
* Logs every request so the team can show the instructor what was fetched.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from config import CACHE, OTHER_MAX_RPS, SEC_MAX_RPS, OUTPUTS


class RobotsDisallowed(Exception):
    pass


class PoliteSession:
    def __init__(self, user_agent: str, offline: bool = False, max_failures: int = 3):
        self.user_agent = user_agent
        self.agent_token = user_agent.split()[0]          # name robots.txt rules match on
        self.offline = offline                            # True = read cache only
        self.max_failures = max_failures
        self.http = requests.Session()
        self.http.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._failures = 0
        self.log: list[dict] = []

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _site_key(host: str) -> str:
        # SEC counts all of its hosts together toward the 10 req/s limit
        return "sec.gov" if host == "sec.gov" or host.endswith(".sec.gov") else host

    def _pace(self, host: str) -> None:
        key = self._site_key(host)
        rps = SEC_MAX_RPS if key == "sec.gov" else OTHER_MAX_RPS
        rp = self._robots.get(f"https://{host}") or self._robots.get(f"http://{host}")
        if rp is not None and key != "sec.gov":
            delay = rp.crawl_delay(self.agent_token)
            if delay:
                rps = min(rps, 1.0 / float(delay))
        gap = 1.0 / rps
        wait = gap - (time.monotonic() - self._last_request.get(key, 0.0))
        if wait > 0:
            time.sleep(wait)
        self._last_request[key] = time.monotonic()

    @staticmethod
    def cache_path(url: str) -> Path:
        p = urlparse(url)
        rel = p.path.lstrip("/") or "index"
        if rel.endswith("/"):
            rel += "index"
        if p.query:
            rel += "__" + hashlib.sha1(p.query.encode()).hexdigest()[:12]
        return CACHE / p.netloc / rel

    # ---------------------------------------------------------------- robots.txt
    def robots_for(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        """Download (once) and parse a site's robots.txt. None = site has no robots.txt."""
        p = urlparse(url)
        key = f"{p.scheme}://{p.netloc}"
        if key in self._robots:
            return self._robots[key]
        robots_url = f"{key}/robots.txt"
        # network errors propagate: "couldn't check" must not be mistaken for "no rules"
        body, status = self._fetch(robots_url, use_cache=True, max_age_days=7, allow_404=True)
        if status == 404 or not body.strip():
            rp = None
        else:
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(body.decode("utf-8", errors="replace").splitlines())
        self._robots[key] = rp
        return rp

    def allowed(self, url: str) -> bool:
        rp = self.robots_for(url)
        return True if rp is None else rp.can_fetch(self.agent_token, url)

    # ---------------------------------------------------------------- fetching
    def get(self, url: str, use_cache: bool = True, max_age_days: float | None = None,
            check_robots: bool = True) -> bytes:
        """Return the body of url, from cache when possible."""
        if check_robots and not url.endswith("/robots.txt") and not self.allowed(url):
            raise RobotsDisallowed(f"robots.txt disallows {url} for agent '{self.agent_token}'")
        body, _ = self._fetch(url, use_cache=use_cache, max_age_days=max_age_days)
        return body

    def get_json(self, url: str, **kw):
        return json.loads(self.get(url, **kw))

    def _fetch(self, url: str, use_cache: bool, max_age_days: float | None,
               allow_404: bool = False) -> tuple[bytes, int]:
        path = self.cache_path(url)
        if use_cache and path.exists():
            age_days = (time.time() - path.stat().st_mtime) / 86400
            if max_age_days is None or age_days <= max_age_days or self.offline:
                return path.read_bytes(), 200
        if self.offline:
            raise FileNotFoundError(f"Offline mode and not cached: {url}")

        host = urlparse(url).netloc
        delay = 1.0
        for attempt in range(5):
            self._pace(host)
            resp = self.http.get(url, timeout=60)
            self.log.append({"time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             "url": url, "status": resp.status_code})
            if resp.status_code == 200:
                self._failures = 0
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(resp.content)
                return resp.content, 200
            # robots.txt convention: any 4xx = the site states no rules; 5xx = retry, then fail
            if allow_404 and 400 <= resp.status_code < 500:
                return b"", 404
            if resp.status_code in (403, 429) or resp.status_code >= 500:
                ra = resp.headers.get("Retry-After", "")
                time.sleep(float(ra) if ra.isdigit() else delay)
                delay *= 2
                continue
            resp.raise_for_status()
        self._failures += 1
        if self._failures >= self.max_failures:
            self.save_log()
            raise SystemExit(f"Stopping after {self.max_failures} consecutive failures (last: {url}). "
                             "If SEC returned 403, check your User-Agent and slow down.")
        raise RuntimeError(f"Gave up on {url}")

    def save_log(self) -> Path | None:
        if not self.log:
            return None
        out = OUTPUTS / "compliance" / f"request_log_{datetime.now():%Y%m%d_%H%M%S}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.log, indent=1))
        return out
