"""Polite, cache-first HTTP fetcher.

Rules enforced here (not left to the caller):
  * honest User-Agent (with contact info when configured); no header spoofing
  * robots.txt is honoured; a URL it disallows is skipped
  * per-host delay with jitter; Retry-After / backoff on 429 and 503
  * a hard stop on 401/402/403 (configurable): the source is marked blocked and nothing is retried
  * off-site redirects are refused (e.g. a bot-paywall redirect), never followed
  * bot-challenge / interstitial pages (captcha, "just a moment", payment walls) are treated as blocks
  * per-source fetch budgets
  * every successful response is cached on disk, so nothing is fetched twice
"""
from __future__ import annotations

import hashlib
import random
import re
import sqlite3
import time
from pathlib import Path
from typing import Callable, NamedTuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from .config import Config
from .db import now
from .parse.base import same_site


class FetchError(Exception):
    """Transient or per-URL failure. The caller may skip the URL."""


class Disallowed(FetchError):
    """robots.txt disallows this URL."""


class BudgetExceeded(Exception):
    """The per-source fetch budget is used up."""


class Blocked(Exception):
    """The site refuses automated access. Stop using this source."""

    def __init__(self, reason: str, status: int | None = None):
        super().__init__(reason)
        self.reason = reason
        self.status = status


class FetchResult(NamedTuple):
    url: str
    status: int
    text: str
    from_cache: bool


_CHALLENGE = re.compile(
    r"(captcha|cf-chl|just a moment|attention required|verify you are (a )?human|"
    r"payment required|tollbit|access denied|bot (detection|protection))",
    re.I,
)


def looks_like_challenge(text: str) -> bool:
    return len(text) < 6000 and bool(_CHALLENGE.search(text))


def _retry_after(resp: httpx.Response) -> float:
    raw = resp.headers.get("retry-after", "")
    try:
        return min(float(raw), 120.0)
    except ValueError:
        return 0.0


class Fetcher:
    def __init__(
        self,
        cfg: Config,
        conn: sqlite3.Connection,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.cfg = cfg
        self.c = cfg.crawl
        self.conn = conn
        self.sleep = sleep
        self.ua = self.c.user_agent + (f" (+{self.c.contact})" if self.c.contact else "")
        self.client = client or httpx.Client(
            headers={"User-Agent": self.ua, "Accept": "text/html,application/xhtml+xml"},
            timeout=self.c.timeout_s,
            follow_redirects=False,
        )
        self._last: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}
        self._consecutive_429 = 0

    # -- politeness -------------------------------------------------------------------------
    def _throttle(self, host: str) -> None:
        delay = self.c.min_delay_s + random.uniform(0, self.c.jitter_s)
        last = self._last.get(host)
        now_t = time.monotonic()
        if last is not None and now_t - last < delay:
            self.sleep(delay - (now_t - last))
        self._last[host] = time.monotonic()

    def _request(self, url: str, allow_cross_host: bool = False) -> tuple[httpx.Response, str]:
        start = url
        for _ in range(6):
            resp = self.client.get(url)
            if resp.status_code in (301, 302, 303, 307, 308):
                loc = resp.headers.get("location")
                if not loc:
                    raise FetchError(f"redirect without Location from {url}")
                nxt = urljoin(url, loc)
                if not allow_cross_host and not same_site(start, nxt):
                    raise Blocked(f"redirected off-site to {nxt}", resp.status_code)
                url = nxt
                continue
            return resp, url
        raise FetchError("too many redirects")

    def allowed(self, url: str) -> bool:
        p = urlparse(url)
        key = f"{p.scheme}://{p.netloc}"
        rp = self._robots.get(key)
        if rp is None:
            rp = RobotFileParser()
            try:
                self._throttle(p.netloc)
                resp, _ = self._request(f"{key}/robots.txt", allow_cross_host=True)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                elif resp.status_code >= 500:
                    rp.disallow_all = True
                else:
                    rp.parse([])
            except (httpx.HTTPError, FetchError):
                rp.disallow_all = True
            rp.modified()  # without this can_fetch() answers False after parse()
            self._robots[key] = rp
        return rp.can_fetch(self.ua, url)

    # -- cache ------------------------------------------------------------------------------
    def _cache_path(self, url: str) -> Path:
        return self.cfg.cache_dir / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".html")

    def _used(self, source_id: str) -> int:
        row = self.conn.execute("SELECT fetch_count FROM sources WHERE id=?", (source_id,)).fetchone()
        return int(row["fetch_count"]) if row else 0

    # -- main entry -------------------------------------------------------------------------
    def get(self, url: str, source_id: str, *, budget: int | None = None, refresh: bool = False) -> FetchResult:
        row = self.conn.execute("SELECT * FROM fetches WHERE url=?", (url,)).fetchone()
        if row and not refresh:
            text = ""
            if row["path"]:
                text = Path(row["path"]).read_text(encoding="utf-8", errors="replace")
            return FetchResult(url, int(row["status"]), text, True)

        if self.c.respect_robots and not self.allowed(url):
            raise Disallowed(f"robots.txt disallows {url}")
        if budget is not None and self._used(source_id) >= budget:
            raise BudgetExceeded(f"fetch budget {budget} reached for {source_id}")

        host = urlparse(url).netloc
        resp: httpx.Response | None = None
        for attempt in range(3):
            self._throttle(host)
            try:
                resp, _final = self._request(url)
            except httpx.HTTPError as exc:
                raise FetchError(f"{type(exc).__name__}: {exc}") from exc
            status = resp.status_code
            if status in self.c.stop_statuses:
                raise Blocked(f"HTTP {status}: site refuses automated access", status)
            if status in (429, 503):
                self._consecutive_429 += 1
                if self._consecutive_429 >= self.c.max_consecutive_429:
                    raise Blocked(f"HTTP {status} {self._consecutive_429}x in a row: rate-limited", status)
                self.sleep(_retry_after(resp) or 30.0 * (attempt + 1))
                continue
            break
        else:
            raise FetchError("still rate-limited after retries")
        assert resp is not None
        self._consecutive_429 = 0

        self.conn.execute("UPDATE sources SET fetch_count = fetch_count + 1 WHERE id=?", (source_id,))
        status = resp.status_code
        if status in (404, 410):
            self._record(url, source_id, status, None)
            return FetchResult(url, status, "", False)
        if status >= 400:
            self.conn.commit()
            raise FetchError(f"HTTP {status} for {url}")

        text = resp.text
        if looks_like_challenge(text):
            self.conn.commit()
            raise Blocked("bot-challenge or access-wall page returned", status)
        path = self._cache_path(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._record(url, source_id, status, str(path))
        return FetchResult(url, status, text, False)

    def _record(self, url: str, source_id: str, status: int, path: str | None) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO fetches(url, source_id, status, path, fetched_at) VALUES(?,?,?,?,?)",
            (url, source_id, status, path, now()),
        )
        self.conn.commit()
