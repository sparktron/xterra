"""Reviewer corrections: a reviewer may reword a garbled prose claim instead of rejecting it.

Decided 2026-10-15 (docs/proposals/reviewer-corrections.md, option A with the number carve-out). A procedure publishes
all-or-nothing, so one misworded step used to withhold a 20-60 step guide whose other steps were fine.

- A `correct` verdict carries replacement wording for one `step`, `summary`, `tip`, `mistake` or `symptom` claim. Values,
  metadata, tools and `complete` cannot be corrected; steps cannot be added, removed or reordered.
- A correction is kept beside the extraction, keyed like `human_decisions` (thread + claim kind + hash of the ORIGINAL
  claim text), so it follows the claim across a re-extraction that states the same text and lapses when it changes.
- It is applied when facts are loaded (`export.load_rows`, and through it review and triage). Every deterministic check
  runs on the corrected text: a correction stating a number the source does not, giving a number a unit the source does
  not, or copying 12 words of it, is not used and the claim keeps its original text and verdicts. A torque, capacity or pressure value still needs a published spec.
- Who publishes: a person's correction, and Claude's when it keeps the original's numbers and units, are `accepted`.
  Claude's that changes a number or a unit is `pending` until a person accepts it in `xw triage`.
- After a step is corrected, `complete` counts only a reviewer verdict on the corrected list (`complete_lists` holds
  the hash of the list each reviewer judged); the local verifier's never counts, because it judged the old wording.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from typing import Any

from .db import now
from .grounding import has_long_overlap, numbers_grounded, same_measures, unit_grounded
from .schemas import Fact
from .verify import claims_for_fact

CORRECTABLE = {"step": "steps", "summary": "summary", "tip": "tips", "mistake": "mistakes", "symptom": "symptoms"}
Table = dict[tuple[int, str, str], tuple[str, str]]   # (thread_id, kind, hash of original) -> (corrected, by)


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def claim_hash(text: str) -> str:
    return hashlib.sha1(_norm(text).encode("utf-8")).hexdigest()[:20]


def kind_of(key: str) -> str:
    return key.partition(":")[0]


def refusal(corrected: str, source: str) -> str:
    """Why `corrected` may not stand in for a claim from `source`, or "" if the deterministic checks pass."""
    if not numbers_grounded(corrected, source):
        return "states a number the source does not"
    if not unit_grounded(corrected, "", source):
        return "gives a number a unit the source does not"
    if has_long_overlap(corrected, source):
        return "copies 12 or more words of the source"
    return ""


def changes_numbers(original: str, corrected: str) -> bool:
    """A number added, dropped or changed, or a number given another unit."""
    return not same_measures(original, corrected)


def load_accepted(conn: sqlite3.Connection) -> Table:
    table: Table = {}
    for r in conn.execute("SELECT thread_id, claim_kind, claim_hash, corrected, by FROM corrections WHERE status='accepted' "
                          "ORDER BY CASE by WHEN 'human' THEN 1 ELSE 0 END"):   # a person's correction wins
        table[(r["thread_id"], r["claim_kind"], r["claim_hash"])] = (r["corrected"], r["by"])
    return table


def load_pending(conn: sqlite3.Connection) -> dict[tuple[int, str, str], dict[str, Any]]:
    return {(r["thread_id"], r["claim_kind"], r["claim_hash"]): dict(r)
            for r in conn.execute("SELECT * FROM corrections WHERE status='pending'")}


def apply(fact: Fact, thread_id: int, source: str, table: Table) -> tuple[Fact, dict[str, str]]:
    """A copy of `fact` with its accepted corrections swapped in, and {claim_key: by} of the claims that were corrected.
    A correction that fails the deterministic checks against `source` is skipped."""
    out, done = fact.model_copy(deep=True), {}
    for key, text in claims_for_fact(fact):
        kind, _, idx = key.partition(":")
        hit = table.get((thread_id, kind, claim_hash(text))) if kind in CORRECTABLE else None
        if not hit or refusal(hit[0], source):
            continue
        if kind == "summary":
            out.summary = hit[0]
        else:
            getattr(out, CORRECTABLE[kind])[int(idx)] = hit[0]
        done[key] = hit[1]
    return out, done


def fact_context(conn: sqlite3.Connection, fact_id: int) -> tuple[Fact, int, str] | None:
    row = conn.execute("SELECT f.fact_json, f.thread_id, c.text FROM facts f JOIN chunks c ON c.id=f.chunk_id WHERE f.id=?",
                       (fact_id,)).fetchone()
    return (Fact.model_validate_json(row[0]), row[1], row[2]) if row else None


def displayed_claims(conn: sqlite3.Connection, fact_id: int, table: Table | None = None) -> dict[str, str]:
    """{claim_key: text} as the pipeline shows the fact now (accepted corrections applied)."""
    ctx = fact_context(conn, fact_id)
    if ctx is None:
        return {}
    fact, _ = apply(ctx[0], ctx[1], ctx[2], load_accepted(conn) if table is None else table)
    return dict(claims_for_fact(fact))


def store(conn: sqlite3.Connection, thread_id: int, key: str, original: str, corrected: str, by: str, note: str = "") -> str:
    """Record a correction; returns its status. Claude's that changes a number waits for a person (`pending`)."""
    status = "pending" if by == "claude" and changes_numbers(original, corrected) else "accepted"
    pk = (thread_id, kind_of(key), claim_hash(original), by)
    old = conn.execute("SELECT corrected, status FROM corrections WHERE thread_id=? AND claim_kind=? AND claim_hash=? AND by=?",
                       pk).fetchone()
    if old and old["corrected"] == corrected:
        return old["status"]   # the same wording again (a re-applied verdict file): a person's accept or reject stands
    conn.execute("INSERT OR REPLACE INTO corrections(thread_id, claim_kind, claim_hash, original, corrected, by, status, note, "
                 "created_at) VALUES(?,?,?,?,?,?,?,?,?)", (*pk[:3], original[:2000], corrected[:2000], by, status, note[:500], now()))
    conn.commit()
    return status


def decide_pending(conn: sqlite3.Connection, thread_id: int, kind: str, chash: str, accept: bool, note: str = "") -> None:
    """A person's answer to a pending Claude correction (`xw triage`)."""
    conn.execute("UPDATE corrections SET status=?, note=CASE WHEN ?='' THEN note ELSE note || ' | person: ' || ? END "
                 "WHERE thread_id=? AND claim_kind=? AND claim_hash=? AND by='claude'",
                 ("accepted" if accept else "rejected", note, note, thread_id, kind, chash))
    conn.commit()


def reopen(conn: sqlite3.Connection, thread_id: int, kind: str, chash: str) -> None:
    conn.execute("UPDATE corrections SET status='pending' WHERE thread_id=? AND claim_kind=? AND claim_hash=? AND by='claude'",
                 (thread_id, kind, chash))
    conn.commit()


def record_judged_list(conn: sqlite3.Connection, fact_id: int, by: str, complete_claim: str) -> None:
    """Remember which step list a reviewer's `complete` verdict judged, so a later step correction voids it."""
    conn.execute("INSERT OR REPLACE INTO complete_lists(fact_id, by, list_hash) VALUES(?,?,?)", (fact_id, by, claim_hash(complete_claim)))
