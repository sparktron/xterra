"""LLM extraction: one chunk in, validated + grounded facts out."""
from __future__ import annotations

import json
import re
import sqlite3
import time
from typing import Callable

from pydantic import ValidationError

from .config import Config
from .db import now
from .grounding import grounded_terms, ground_fact
from .llm import LLM, LLMError
from .schemas import Extraction, Fact, extraction_schema
from .topics import TopicIndex

Log = Callable[[str], None]


def build_system_prompt(cfg: Config, topics: TopicIndex) -> str:
    base = (cfg.root / "prompts" / "extract.md").read_text(encoding="utf-8")
    return f"{base}\nKNOWN TOPICS (use the exact title when the content fits):\n{topics.titles_for_prompt()}\n"


def _user_message(source_name: str, thread_title: str, text: str) -> str:
    return f"SOURCE: {source_name}\nTHREAD TITLE: {thread_title}\n\nTEXT:\n{text}"


_NUMBERED = re.compile(r"^\s*(\d{1,2})[.)]\s+\S", re.M)
STEP_RETRIES = 2


def numbered_steps(text: str) -> int:
    """How many steps the source itself numbers: the longest 1, 2, 3, ... run of numbered lines (0 if none)."""
    n = 0
    for m in _NUMBERED.finditer(text):
        if int(m.group(1)) == n + 1:
            n += 1
    return n


def _most_steps(result: Extraction) -> int:
    return max((len(f.steps) for f in result.facts), default=0)


def _extract_once(llm: LLM, system: str, schema: dict, source_name: str, thread_title: str, text: str) -> Extraction:
    raw = llm.chat_json(system, _user_message(source_name, thread_title, text), schema)
    try:
        return Extraction.model_validate(raw)
    except ValidationError as exc:
        raise LLMError(f"schema validation failed: {exc.errors()[:2]}") from exc


def extract_chunk(llm: LLM, system: str, schema: dict, source_name: str, thread_title: str, text: str) -> Extraction:
    """One extraction. The local model sometimes stops a numbered procedure early; when the source numbers more steps
    than came back, retry (a few times) and keep the run with the most steps. Everything still goes through grounding
    and the verifier, so a retry can only add candidate steps, never skip a check."""
    best = _extract_once(llm, system, schema, source_name, thread_title, text)
    want = numbered_steps(text)
    for _ in range(STEP_RETRIES):
        if not want or _most_steps(best) >= want:
            break
        try:
            again = _extract_once(llm, system, schema, source_name, thread_title, text)
        except LLMError:
            continue
        if _most_steps(again) > _most_steps(best):
            best = again
    return best


SUMMARY_SYSTEM = (
    "You write the one-to-two sentence summary line of a wiki page about a 2nd-generation Nissan Xterra repair or "
    "modification. Use ONLY the title, steps, tips and values given. Say what the job is and what it achieves or when "
    "you would do it. Do not add any fact, cause, benefit or part that is not in the input, do not copy the steps, and "
    'do not mention forum users. Reply with one JSON object: {"summary": "..."}.'
)
SUMMARY_SCHEMA = {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}


def fill_summary(llm: LLM, fact: Fact) -> None:
    """The extractor leaves `summary` empty on a small model whatever the prompt says, so write it in a second, tiny
    call from what was already extracted. The verifier checks it against the source like any other claim."""
    if fact.summary.strip() or not (fact.steps or fact.tips or fact.specs):
        return
    lines = [f"TITLE: {fact.title}", f"TOPIC: {fact.topic}"]
    lines += [f"STEP {i}: {t}" for i, t in enumerate(fact.steps, 1)] + [f"TIP: {t}" for t in fact.tips]
    lines += [f"VALUE: {sp.item}: {sp.value} {sp.unit}".strip() for sp in fact.specs[:6]]
    try:
        out = llm.chat_json(SUMMARY_SYSTEM, "\n".join(lines), SUMMARY_SCHEMA)
    except LLMError:
        return
    text = out.get("summary") if isinstance(out, dict) else None
    if isinstance(text, str) and text.strip():
        fact.summary = " ".join(text.split())[:400]


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
            if status == "error":  # surface permanent failures on the thread so run/status/open_questions see them
                conn.execute("UPDATE threads SET status='error', error=? WHERE id=?", (f"extraction failed: {str(exc)[:200]}", row["tid"]))
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
                fill_summary(llm, fact)
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
