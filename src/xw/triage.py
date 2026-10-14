"""Human triage: you confirm or reject whatever the pipeline is not sure about.

`xw triage` walks the low-confidence claims one at a time, with the source excerpt next to each, and stores your
answer as a `human` verdict, which outranks Claude's and the local verifier's (`export.gate`). Low confidence means:

  0. Claude reviewed it and answered `needs_human`, or it is a safety-critical value held in pending_verification.md
  1. the local verifier answered `partial`, or could not be trusted on that call (it accepted a planted false claim),
     or Claude found a procedure's steps right but its list possibly incomplete (it shows as [Partial])

Claims Claude approved or rejected, claims you already decided, and claims the verifier called `supported` are not
shown, and nothing that fails the deterministic evidence checks (a number or part number that is not in the source,
copied text) is ever shown: no answer from anyone can publish those.

Decisions are kept by content (`human_decisions`: thread + claim kind + normalised claim text), not only by fact id,
so after a re-extraction or a `verify --redo` the same claim in the same thread is decided again automatically
(`reapply_decisions`, called by verify, export and triage). A changed claim text is a new, undecided claim.

Answers: `a` approve, `r` reject, `p` (completeness claims only) the steps are right but the list may be incomplete,
so the procedure publishes marked [Partial]; anything typed after the letter is stored as your note. `s` skips,
`u` undoes your last answer, `q` quits.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import textwrap
from collections import Counter
from typing import Any, Callable

from .config import Config
from .db import now
from .review import build_queue
from .schemas import Fact
from .topics import TopicIndex
from .verify import claims_for_fact

Out = Callable[[str], None]
PRIORITY_LABELS = {0: "Claude was unsure, or a safety value awaits corroboration",
                   1: "verifier answered partial / could not be trusted, or a procedure is published as [Partial]"}
WIDTH = 100


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def claim_hash(text: str) -> str:
    return hashlib.sha1(_norm(text).encode("utf-8")).hexdigest()[:20]


def _kind(key: str) -> str:
    return key.partition(":")[0]


def _split(item_id: str) -> tuple[int, str]:
    m = re.match(r"^f(\d+):(.+)$", item_id)
    assert m, item_id
    return int(m.group(1)), m.group(2)


def triage_queue(cfg: Config, conn: sqlite3.Connection, topics: TopicIndex, *, kinds: set[str] | None = None,
                 page: str | None = None) -> list[dict[str, Any]]:
    reapply_decisions(conn)
    items = build_queue(cfg, conn, topics, triage=True)
    if kinds:
        items = [i for i in items if i["kind"] in kinds]
    if page:
        items = [i for i in items if page.lower() in i["page"].lower()]
    # same page together, so the source context carries over from one claim to the next
    items.sort(key=lambda i: (i["priority"], i["page"], _split(i["id"])[0], _split(i["id"])[1]))
    return items


def summarize_queue(items: list[dict[str, Any]]) -> str:
    if not items:
        return "Nothing is waiting for a human decision."
    lines = [f"{len(items)} claim(s) waiting for a human decision:"]
    for prio, n in sorted(Counter(i["priority"] for i in items).items()):
        lines.append(f"  {n:4d}  {PRIORITY_LABELS.get(prio, prio)}")
    lines.append("by kind: " + ", ".join(f"{k} {n}" for k, n in sorted(Counter(i["kind"] for i in items).items())))
    risky = Counter(i["risk"] for i in items if i["risk"])
    if risky:
        lines.append("take extra care with: " + ", ".join(f"{n} {k}" for k, n in risky.most_common()))
    lines.append("pages with the most: " + "; ".join(f"{p} ({n})" for p, n in Counter(i["page"] for i in items).most_common(5)))
    return "\n".join(lines)


# ---- decisions --------------------------------------------------------------------------------------------
def decide(conn: sqlite3.Connection, item: dict[str, Any], verdict: str, note: str = "") -> None:
    fid, key = _split(item["id"])
    conn.execute("INSERT OR REPLACE INTO verdicts(fact_id, claim_key, by, verdict, note, created_at) VALUES(?,?,?,?,?,?)",
                 (fid, key, "human", verdict, note[:500], now()))
    conn.execute("INSERT OR REPLACE INTO human_decisions(thread_id, claim_kind, claim_hash, claim_text, verdict, note, created_at) "
                 "VALUES(?,?,?,?,?,?,?)", (item["thread_id"], _kind(key), claim_hash(item["claim"]), item["claim"][:2000], verdict,
                                           note[:500], now()))
    conn.commit()


def undo(conn: sqlite3.Connection, item: dict[str, Any]) -> None:
    fid, key = _split(item["id"])
    conn.execute("DELETE FROM verdicts WHERE fact_id=? AND claim_key=? AND by='human'", (fid, key))
    conn.execute("DELETE FROM human_decisions WHERE thread_id=? AND claim_kind=? AND claim_hash=?",
                 (item["thread_id"], _kind(key), claim_hash(item["claim"])))
    conn.commit()


def reapply_decisions(conn: sqlite3.Connection) -> int:
    """Copy stored human decisions onto facts that state the same claim in the same thread and have no human verdict
    yet (a re-extraction creates new fact ids). Returns how many verdicts were added."""
    saved = {(r["thread_id"], r["claim_kind"], r["claim_hash"]): (r["verdict"], r["note"])
             for r in conn.execute("SELECT thread_id, claim_kind, claim_hash, verdict, note FROM human_decisions")}
    if not saved:
        return 0
    have = {(r["fact_id"], r["claim_key"]) for r in conn.execute("SELECT fact_id, claim_key FROM verdicts WHERE by='human'")}
    added = 0
    for row in conn.execute("SELECT id, thread_id, fact_json FROM facts").fetchall():
        for key, text in claims_for_fact(Fact.model_validate_json(row["fact_json"])):
            hit = saved.get((row["thread_id"], _kind(key), claim_hash(text)))
            if hit and (row["id"], key) not in have:
                conn.execute("INSERT INTO verdicts(fact_id, claim_key, by, verdict, note, created_at) VALUES(?,?,?,?,?,?)",
                             (row["id"], key, "human", hit[0], (hit[1] or "carried over from an earlier decision")[:500], now()))
                added += 1
    conn.commit()
    return added


# ---- the interactive loop -----------------------------------------------------------------------------------
def render(item: dict[str, Any], pos: int, total: int, excerpt_chars: int = 1200) -> str:
    wrap = lambda t, ind="": textwrap.fill(t, WIDTH, initial_indent=ind, subsequent_indent=ind)  # noqa: E731
    lines = ["", "=" * WIDTH, f"[{pos}/{total}]  {item['page']}   ({item['kind']}, local verifier: {item['local_verdict']})",
             f"why asked: {item['why_queued']}"]
    if item["risk"]:
        lines.append(f"!! {item['risk'].upper()}: your approval publishes it" + (" without a second source." if item["risk"] ==
                                                                                 "safety-critical value" else "."))
    lines += ["", "CLAIM:", wrap(item["claim"], "  ")]
    if item["evidence_quote"]:
        lines += ["", "QUOTE THE MODEL GAVE:", wrap(item["evidence_quote"], "  ")]
    lines += ["", f"SOURCE EXCERPT ({item['thread_title'][:60]}):", wrap(item["excerpt"][:excerpt_chars], "  "), f"  {item['source_url']}"]
    return "\n".join(lines)


def run_triage(cfg: Config, conn: sqlite3.Connection, topics: TopicIndex, *, kinds: set[str] | None = None, page: str | None = None,
               limit: int | None = None, input_fn: Callable[[str], str] = input, out: Out = print) -> Counter:
    items = triage_queue(cfg, conn, topics, kinds=kinds, page=page)
    if limit:
        items = items[:limit]
    out(summarize_queue(items))
    counts: Counter = Counter()
    done: list[tuple[dict[str, Any], str]] = []
    i = 0
    while True:
        if i >= len(items):
            if not done:
                break
            try:   # the last answer is not final until you say so
                raw = input_fn("\nend of the queue. [u]ndo your last answer, or anything else to finish\n> ").strip()
            except EOFError:
                break
            if raw.lower() == "u":
                last, verdict = done.pop()
                undo(conn, last)
                counts[verdict] -= 1
                i = items.index(last)
                continue
            break
        item = items[i]
        out(render(item, i + 1, len(items), int(cfg.review.excerpt_chars) * (2 if item["kind"] == "complete" else 1)))
        options = "[a]pprove  [r]eject" + ("  [p]artial: steps right, list may be incomplete" if item["kind"] == "complete" else "") \
                  + "  [s]kip  [u]ndo  [q]uit"
        try:
            raw = input_fn(f"\n{options}\n> ").strip()
        except EOFError:
            break
        cmd, _, note = raw.partition(" ")
        cmd = cmd.lower()
        verdict = {"a": "approve", "r": "reject", "p": "needs_human" if item["kind"] == "complete" else ""}.get(cmd, "")
        if verdict:
            decide(conn, item, verdict, note.strip())
            done.append((item, verdict))
            counts[verdict] += 1
            i += 1
        elif cmd == "s":
            counts["skipped"] += 1
            i += 1
        elif cmd == "u":
            if not done:
                out("nothing to undo")
                continue
            last, verdict = done.pop()
            undo(conn, last)
            counts[verdict] -= 1
            i = items.index(last)
        elif cmd == "q":
            break
        else:
            out("answer a, r, " + ("p, " if item["kind"] == "complete" else "") + "s, u or q")
    left = len(items) - i
    out(f"\nstopped: {counts['approve']} approved, {counts['reject']} rejected, {counts['needs_human']} marked partial, "
        f"{counts['skipped']} skipped, {left} not reached.\nNow run `xw export && xw qa` to publish what you confirmed.")
    return counts
