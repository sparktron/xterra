"""SQLite state. Everything the pipeline does is resumable from this database."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources(
  id TEXT PRIMARY KEY,
  rank INTEGER,
  name TEXT,
  base_url TEXT DEFAULT '',
  type TEXT DEFAULT 'forum',
  adapter TEXT DEFAULT 'generic',
  trust INTEGER DEFAULT 3,
  is_primary INTEGER DEFAULT 0,
  enabled INTEGER DEFAULT 1,
  status TEXT DEFAULT 'queued',          -- queued | in-progress | done | blocked
  reason TEXT DEFAULT '',
  fetch_count INTEGER DEFAULT 0,
  config_json TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS fetches(
  url TEXT PRIMARY KEY,
  source_id TEXT,
  status INTEGER,
  path TEXT,
  fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS threads(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL,
  url TEXT UNIQUE NOT NULL,
  title TEXT DEFAULT '',
  author TEXT DEFAULT '',
  posted TEXT DEFAULT '',
  kind TEXT DEFAULT 'discussion',        -- pinned | howto | discussion | manual
  priority REAL DEFAULT 2,
  views INTEGER DEFAULT 0,
  replies INTEGER DEFAULT 0,
  status TEXT DEFAULT 'queued',          -- queued | fetched | extracted | skipped | error
  pages_fetched INTEGER DEFAULT 0,
  error TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS chunks(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  thread_id INTEGER NOT NULL,
  idx INTEGER NOT NULL,
  text TEXT NOT NULL,
  status TEXT DEFAULT 'pending',         -- pending | done | irrelevant | error
  attempts INTEGER DEFAULT 0,
  error TEXT DEFAULT '',
  UNIQUE(thread_id, idx)
);
CREATE TABLE IF NOT EXISTS facts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  thread_id INTEGER NOT NULL,
  chunk_id INTEGER NOT NULL,
  fact_json TEXT NOT NULL,
  grounding_json TEXT NOT NULL,
  created_at TEXT
);
-- One row per checked claim. claim_key: summary | symptom:i | step:i | complete | tool:i | tip:i | mistake:i | spec:i |
--   part:i | dtc:i | applies | platform | difficulty | time
-- by='local'  -> verdict supported | partial | unsupported | decoy_failed   (local verifier model)
-- by='claude' -> verdict approve | reject | needs_human       (Claude review of source excerpts)
-- by='human'  -> same as claude; a human verdict overrides Claude's
CREATE TABLE IF NOT EXISTS verdicts(
  fact_id INTEGER NOT NULL,
  claim_key TEXT NOT NULL,
  by TEXT NOT NULL,
  verdict TEXT NOT NULL,
  note TEXT DEFAULT '',
  created_at TEXT,
  PRIMARY KEY(fact_id, claim_key, by)
);
-- One row per locally verified fact: planted false claims (decoys) shown to the verifier and how many it accepted.
CREATE TABLE IF NOT EXISTS decoy_checks(
  fact_id INTEGER NOT NULL,
  calls INTEGER,
  decoys INTEGER,
  accepted INTEGER,
  discarded INTEGER,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT,
  msg TEXT
);
CREATE INDEX IF NOT EXISTS idx_threads_status ON threads(source_id, status, priority);
CREATE INDEX IF NOT EXISTS idx_chunks_status ON chunks(status, thread_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def log(conn: sqlite3.Connection, msg: str) -> None:
    conn.execute("INSERT INTO log(ts, msg) VALUES(?, ?)", (now(), msg))
    conn.commit()


def seed_sources(conn: sqlite3.Connection, sources: list[dict[str, Any]]) -> None:
    """Insert or refresh sources from sources.yaml without clobbering runtime state."""
    for s in sources:
        extra = {k: v for k, v in s.items() if k in ("seeds", "thread_urls", "howto_hints", "skip_forums", "notes")}
        row = conn.execute("SELECT id FROM sources WHERE id=?", (s["id"],)).fetchone()
        values = (
            s.get("rank", 50), s.get("name", s["id"]), s.get("base_url", ""), s.get("type", "forum"),
            s.get("adapter", "generic"), int(s.get("trust", 3)), 1 if s.get("primary") else 0,
            1 if s.get("enabled", True) else 0, json.dumps(extra),
        )
        if row:
            conn.execute(
                "UPDATE sources SET rank=?, name=?, base_url=?, type=?, adapter=?, trust=?, is_primary=?, enabled=?, config_json=? WHERE id=?",
                (*values, s["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO sources(rank, name, base_url, type, adapter, trust, is_primary, enabled, config_json, id) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (*values, s["id"]),
            )
    conn.commit()


def set_source_status(conn: sqlite3.Connection, source_id: str, status: str, reason: str = "") -> None:
    conn.execute("UPDATE sources SET status=?, reason=? WHERE id=?", (status, reason, source_id))
    conn.commit()
