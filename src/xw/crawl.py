"""Discovery (forum listings -> thread queue) and harvest (thread pages -> text chunks)."""
from __future__ import annotations

import json
import re
import sqlite3
from collections import deque
from typing import Callable

from .config import Config
from .fetch import BudgetExceeded, Disallowed, FetchError, Fetcher
from .parse import get_adapter
from .parse.base import Post, same_site

DEFAULT_HINTS = ["how to", "how-to", "diy", "write-up", "writeup", "faq", "guide", "tutorial", "install", "swap", "replace", "fix"]
DEFAULT_SKIP = ["for sale", "classified", "marketplace", "off topic", "off-topic", "introduc", "meet", "event", "vendor", "giveaway"]
JUNK_TITLE = re.compile(r"\b(wtb|wts|fs:|f/s|for sale|wanted|meet ?up|introduc\w*|welcome|new member|hello from|raffle|giveaway)\b", re.I)

Log = Callable[[str], None]


def source_budget(cfg: Config, source: sqlite3.Row) -> int:
    return cfg.crawl.max_fetches_primary if source["is_primary"] else cfg.crawl.max_fetches_per_source


def _forum_key(url: str) -> str:
    return re.sub(r"/page-\d+/?$", "/", url)


def _add_thread(conn: sqlite3.Connection, source_id: str, url: str, title: str, kind: str, priority: float,
                author: str = "", views: int = 0, replies: int = 0) -> bool:
    cur = conn.execute(
        "INSERT OR IGNORE INTO threads(source_id, url, title, author, kind, priority, views, replies) VALUES(?,?,?,?,?,?,?,?)",
        (source_id, url, title, author, kind, priority, views, replies),
    )
    return cur.rowcount > 0


def discover(cfg: Config, conn: sqlite3.Connection, fetcher: Fetcher, source: sqlite3.Row, log: Log = print) -> int:
    """Walk forum listings from the seeds, queue threads (pinned first, then how-to-looking titles)."""
    scfg = json.loads(source["config_json"] or "{}")
    adapter = get_adapter(source["adapter"])
    hints = [h.lower() for h in scfg.get("howto_hints", DEFAULT_HINTS)]
    skip = [s.lower() for s in scfg.get("skip_forums", DEFAULT_SKIP)]
    sid = source["id"]
    budget = source_budget(cfg, source)
    added = 0

    for url in scfg.get("thread_urls", []):
        added += _add_thread(conn, sid, url, "", "howto", 1.0)

    queue: deque[tuple[str, int, str, int]] = deque((u, 0, _forum_key(u), 1) for u in scfg.get("seeds", []))
    seen: set[str] = set()
    while queue:
        url, depth, fkey, page_no = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        try:
            res = fetcher.get(url, sid, budget=budget)
        except Disallowed:
            log(f"  skip (robots): {url}")
            continue
        except BudgetExceeded:
            log("  fetch budget reached during discovery")
            break
        except FetchError as exc:
            log(f"  fetch error: {exc}")
            continue
        if res.status != 200:
            continue
        page = adapter.parse_forum(res.text, url)
        for t in page.threads:
            if JUNK_TITLE.search(t.title):
                continue
            if t.pinned:
                kind, prio = "pinned", 0.0
            elif any(h in t.title.lower() for h in hints):
                kind, prio = "howto", 1.0
            else:
                kind, prio = "discussion", 2.0
            added += _add_thread(conn, sid, t.url, t.title, kind, prio, t.author, t.views, t.replies)
        for title, sub in page.subforums:
            if depth < cfg.crawl.max_forum_depth and same_site(sub, url) and not any(w in title.lower() for w in skip):
                queue.append((sub, depth + 1, _forum_key(sub), 1))
        if page.next_url and page_no < cfg.crawl.max_forum_pages:
            queue.append((page.next_url, depth, fkey, page_no + 1))
        conn.commit()
    conn.commit()
    log(f"  discovered {added} new threads")
    return added


def build_chunks(title: str, posts: list[Post], max_chars: int, min_chars: int, min_post_chars: int) -> list[str]:
    """Group posts into LLM-sized chunks at post boundaries; split oversized posts at paragraphs."""
    blocks: list[str] = []
    for i, p in enumerate(posts):
        if i > 0 and len(p.text) < min_post_chars:
            continue  # "bump", "thanks", "subscribed"
        header = f"### Post {i + 1}" + (f" by {p.author}" if p.author else "") + (f" ({p.posted[:10]})" if p.posted else "")
        body = p.text
        if len(body) + len(header) > max_chars:
            paras, cur = body.split("\n\n"), ""
            for para in paras:
                if len(cur) + len(para) + 2 > max_chars - len(header) and cur:
                    blocks.append(f"{header} (part)\n{cur}")
                    cur = ""
                cur += ("\n\n" if cur else "") + para[: max_chars - len(header)]
            if cur:
                blocks.append(f"{header} (part)\n{cur}")
        else:
            blocks.append(f"{header}\n{body}")

    chunks: list[str] = []
    cur = ""
    for b in blocks:
        if cur and len(cur) + len(b) + 2 > max_chars:
            chunks.append(cur)
            cur = ""
        cur += ("\n\n" if cur else "") + b
    if cur:
        chunks.append(cur)
    chunks = [c for c in chunks if len(c) >= min_chars] or chunks[:1]
    return [f"THREAD: {title}" + ("" if i == 0 else " (continued)") + "\n\n" + c for i, c in enumerate(chunks)]


def store_thread(cfg: Config, conn: sqlite3.Connection, thread_id: int, title: str, posts: list[Post], pages: int) -> int:
    first = posts[0] if posts else None
    conn.execute(
        "UPDATE threads SET title=COALESCE(NULLIF(?, ''), title), author=COALESCE(NULLIF(?, ''), author), posted=?, pages_fetched=?, status='fetched', error='' WHERE id=?",
        (title, first.author if first else "", first.posted if first else "", pages, thread_id),
    )
    conn.execute("DELETE FROM chunks WHERE thread_id=? AND status='pending'", (thread_id,))
    chunks = build_chunks(
        title, posts, cfg.extract.max_chunk_chars, cfg.extract.min_chunk_chars, cfg.crawl.min_post_chars
    )
    for idx, text in enumerate(chunks):
        conn.execute("INSERT OR IGNORE INTO chunks(thread_id, idx, text) VALUES(?,?,?)", (thread_id, idx, text))
    conn.commit()
    return len(chunks)


def harvest(cfg: Config, conn: sqlite3.Connection, fetcher: Fetcher, source: sqlite3.Row, limit: int | None = None,
            log: Log = print) -> int:
    adapter = get_adapter(source["adapter"])
    sid = source["id"]
    budget = source_budget(cfg, source)
    rows = conn.execute(
        "SELECT * FROM threads WHERE source_id=? AND status='queued' ORDER BY priority, views DESC, id", (sid,)
    ).fetchall()
    done = 0
    for t in rows[: limit or None]:
        url, pages, posts, title = t["url"], 0, [], t["title"]
        status_note = ""
        try:
            while url and pages < cfg.crawl.max_thread_pages:
                res = fetcher.get(url, sid, budget=budget)
                if res.status != 200:
                    status_note = f"HTTP {res.status}"
                    break
                tp = adapter.parse_thread(res.text, url)
                if pages == 0:
                    title = tp.title or title  # later pages must not overwrite the title
                posts.extend(tp.posts)
                pages += 1
                url = tp.next_url or ""
        except Disallowed:
            conn.execute("UPDATE threads SET status='skipped', error='robots.txt' WHERE id=?", (t["id"],))
            conn.commit()
            continue
        except FetchError as exc:
            conn.execute("UPDATE threads SET status='error', error=? WHERE id=?", (str(exc)[:300], t["id"]))
            conn.commit()
            continue
        except BudgetExceeded:
            log("  fetch budget reached; remaining threads stay queued")
            break
        if not posts:
            conn.execute("UPDATE threads SET status='skipped', error=? WHERE id=?", (status_note or "no posts parsed", t["id"]))
            conn.commit()
            continue
        n = store_thread(cfg, conn, t["id"], title, posts, pages)
        done += 1
        log(f"  harvested: {title[:70]} ({pages} page(s), {n} chunk(s))")
    return done
