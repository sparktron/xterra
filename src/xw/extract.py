"""LLM extraction: one chunk in, validated + grounded facts out."""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Callable

from pydantic import ValidationError

from .config import Config
from .db import now
from .grounding import grounded_terms, ground_fact
from .llm import LLM, LLMError
from .schemas import Extraction, extraction_schema
from .topics import TopicIndex

Log = Callable[[str], None]


def build_system_prompt(cfg: Config, topics: TopicIndex) -> str:
    base = (cfg.root / "prompts" / "extract.md").read_text(encoding="utf-8")
    return f"{base}\nKNOWN TOPICS (use the exact title when the content fits):\n{topics.titles_for_prompt()}\n"


def _user_message(source_name: str, thread_title: str, text: str) -> str:
    return f"SOURCE: {source_name}\nTHREAD TITLE: {thread_title}\n\nTEXT:\n{text}"


def extract_chunk(llm: LLM, system: str, schema: dict, source_name: str, thread_title: str, text: str) -> Extraction:
    raw = llm.chat_json(system, _user_message(source_name, thread_title, text), schema)
    try:
        return Extraction.model_validate(raw)
    except ValidationError as exc:
        raise LLMError(f"schema validation failed: {exc.errors()[:2]}") from exc


def extract_pending(cfg: Config, conn: sqlite3.Connection, llm: LLM, topics: TopicIndex, *, source_id: str | None = None,
                    limit: int | None = None, log: Log = print) -> int:
    """Process pending chunks (highest-priority threads first). Returns the number of chunks processed."""
    system = build_system_prompt(cfg, topics)
    schema = extraction_schema()
    where, args = "c.status='pending'", []
    if source_id:
        where += " AND t.source_id=?"
        args.append(source_id)
    rows = conn.execute(
        f"""SELECT c.id AS cid, c.text, c.attempts, t.id AS tid, t.title, s.name AS sname
            FROM chunks c JOIN threads t ON t.id=c.thread_id JOIN sources s ON s.id=t.source_id
            WHERE {where} ORDER BY t.priority, t.views DESC, t.id, c.idx""",
        args,
    ).fetchall()
    processed = failures = 0
    for row in rows[: limit or None]:
        started = time.monotonic()
        try:
            result = extract_chunk(llm, system, schema, row["sname"], row["title"], row["text"])
        except LLMError as exc:
            failures += 1
            attempts = row["attempts"] + 1
            status = "error" if attempts >= 3 else "pending"
            conn.execute("UPDATE chunks SET attempts=?, status=?, error=? WHERE id=?", (attempts, status, str(exc)[:400], row["cid"]))
            conn.commit()
            log(f"  chunk {row['cid']}: {exc}")
            if failures >= cfg.extract.max_consecutive_failures:
                log("  too many consecutive LLM failures; stopping (is the model server running?)")
                break
            continue
        failures = 0
        stored = 0
        if result.relevant:
            for fact in result.facts:
                # Applicability metadata is only kept when the source text itself mentions it.
                lo, hi = cfg.scope.years
                stated = [y for y in fact.years if str(y) in row["text"]]
                if stated and not any(lo <= y <= hi for y in stated):
                    continue  # only out-of-scope model years (e.g. first-generation Xterra)
                fact.years = [y for y in stated if lo <= y <= hi]
                fact.trims = grounded_terms(fact.trims, row["text"])
                fact.engines = grounded_terms(fact.engines, row["text"])
                fact.drivetrain = grounded_terms(fact.drivetrain, row["text"])
                fact.shared_platform = grounded_terms(fact.shared_platform, row["text"])  # type: ignore[assignment]
                conn.execute(
                    "INSERT INTO facts(thread_id, chunk_id, fact_json, grounding_json, created_at) VALUES(?,?,?,?,?)",
                    (row["tid"], row["cid"], fact.model_dump_json(), json.dumps(ground_fact(fact, row["text"])), now()),
                )
                stored += 1
        conn.execute("UPDATE chunks SET status=?, error='' WHERE id=?", ("done" if stored else "irrelevant", row["cid"]))
        processed += 1
        conn.execute(
            """UPDATE threads SET status='extracted'
               WHERE id=? AND NOT EXISTS (SELECT 1 FROM chunks WHERE thread_id=? AND status='pending')""",
            (row["tid"], row["tid"]),
        )
        conn.commit()
        log(f"  chunk {row['cid']}: {stored} fact(s) in {time.monotonic() - started:.0f}s  [{row['title'][:50]}]")
    return processed
