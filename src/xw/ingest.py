"""Ingest pages or notes you saved yourself (HTML, text or markdown) as threads of the `manual` source.

Use this for content you are entitled to read but that a site does not let bots fetch. Respecting a
site's terms for how you save and use that content is up to you; the wiki rewrites facts in original
wording and attributes the original URL.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import Config
from .crawl import store_thread
from .parse import generic, xenforo
from .parse.base import Post, ThreadPage

MANUAL_SOURCE = "manual"


def _parse_html(html: str, url: str) -> ThreadPage:
    page = xenforo.parse_thread(html, url)
    if page.posts:
        return page
    return generic.parse_thread(html, url)


def ingest_file(cfg: Config, conn: sqlite3.Connection, path: Path, *, url: str = "", title: str = "", author: str = "",
                posted: str = "", kind: str = "manual") -> int | None:
    """Create/refresh a manual thread from a local file. Returns the thread id, or None if nothing usable."""
    suffix = path.suffix.lower()
    raw = path.read_text(encoding="utf-8", errors="replace")
    key = url or f"file://{path.resolve()}"
    if suffix in (".html", ".htm", ".xhtml"):
        page = _parse_html(raw, key)
        posts, ttl = page.posts, page.title
    else:
        posts, ttl = [Post(author=author, posted=posted, text=raw.strip())], path.stem.replace("_", " ")
    if not posts or not any(p.text for p in posts):
        return None
    if title:
        ttl = title
    conn.execute(
        "INSERT OR IGNORE INTO threads(source_id, url, title, author, kind, priority, status) VALUES(?,?,?,?,?,?, 'queued')",
        (MANUAL_SOURCE, key, ttl, author, kind, 1.0),
    )
    row = conn.execute("SELECT id, status FROM threads WHERE url=?", (key,)).fetchone()
    if author or posted:
        posts[0].author = posts[0].author or author
        posts[0].posted = posts[0].posted or posted
    # re-ingesting replaces pending chunks only; already-extracted chunks are kept to avoid duplicate facts
    if row["status"] in ("queued", "fetched"):
        store_thread(cfg, conn, row["id"], ttl, posts, 1)
    return int(row["id"])
