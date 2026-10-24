"""Claude review loop (optional, opt-in, small).

`xw review-export` writes batches of claims plus the minimal source excerpt each claim must be judged
against. In Claude Code, the `wiki-reviewer` agent (.claude/agents/wiki-reviewer.md) reads a batch and writes
`<batch>.verdicts.json`; `xw review-apply` stores those verdicts, and the exporter then honours them.

What goes to Claude is only the claim and a short excerpt of public forum text or your own saved notes,
never the whole database. Nothing is sent anywhere by this code: you run the review step yourself.

Review queue, in priority order:
  0. safety-critical values the exporter is holding in pending_verification.md (taken from the exporter itself,
     so the queue counts corroboration exactly as the gate does)
  1. claims the local verifier judged "partial", or that it could not judge because it accepted a decoy
  2. an audit sample (verify.audit_rate) of claims the local verifier said "supported", used to measure
     how often the local verifier waves bad claims through
Claims the verifier judged "unsupported", and anything failing the deterministic evidence checks, are never queued.
A procedure whose steps a reviewer reworded (`correct`, see corrections.py) has its `complete` claim queued again at
priority 1, because the earlier verdicts judged the old list.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from . import corrections
from .config import Config
from .db import now
from .export import Policy, is_safety, load_rows, pending_spec_keys, route_rows
from .grounding import safety_values
from .topics import TopicIndex
from .verify import DECOY_FAILED, claims_for_fact

REVIEW_VERDICTS = ("approve", "reject", "needs_human")
CLAIM_KEY = re.compile(r"^(summary|symptom:\d+|step:\d+|complete|tool:\d+|tip:\d+|mistake:\d+|spec:\d+|part:\d+|dtc:\d+"
                       r"|applies|platform|difficulty|time)$")
_PROSE = {"step": "steps", "tip": "tips", "mistake": "mistakes", "symptom": "symptoms", "tool": "tools"}

INSTRUCTIONS = (
    "Judge each item ONLY against its `excerpt`. Do not use outside knowledge to approve anything. "
    "approve = the excerpt clearly states the claim (numbers, units, part numbers and conditions all match). "
    "reject = the excerpt does not state it, states something different, or it applies to another vehicle/year. "
    "needs_human = ambiguous, or it conflicts with something you know (say what in `note`; do not approve on your own memory). "
    "kind `complete` claims a step list is the whole procedure. Judge two things. (1) Is every listed step stated by the "
    "excerpt? If any listed step is not in the excerpt or is contradicted by it, answer reject and name that step. "
    "(2) If every listed step is stated: approve only if the excerpt plainly covers the whole job and mentions no step, "
    "precaution or part the list leaves out; if the list may leave something out or the excerpt may be cut short, answer "
    "needs_human and say what seems missing (the wiki then shows the steps marked Partial; reject would hide them). "
    "kind `applies`/`platform`: approve only if the excerpt says the repair or part applies to those years, trims or vehicles, "
    "not merely that they are mentioned. "
    "correct = (kinds step, summary, tip, mistake, symptom only) the excerpt states the action or fact but the claim garbles "
    "it (wrong object, place, order word or detail): add \"corrected\": the excerpt's meaning as one sentence in your own "
    "words. Never add a number, part, tool or step the excerpt does not state, never copy 12 words of it in a row, and do "
    "not use it to fix a list (a missing or extra step is a `complete` answer). If the excerpt does not state the claim at "
    "all, answer reject. A correction that changes a number waits for a person. When you correct steps of a procedure, "
    "judge its `complete` item in the same file with your corrections applied. "
    "Be strict: when unsure, do not approve. Write {\"verdicts\": [{\"id\": ..., \"verdict\": ..., \"note\": ...}]} "
    "(plus \"corrected\" on a correct verdict) to the verdict_file."
)


def _find_span(text: str, needle: str) -> int:
    words = re.findall(r"\S+", needle)
    if not words:
        return -1
    m = re.search(r"\s+".join(re.escape(w) for w in words), text, re.I)
    return m.start() if m else -1


def excerpt_for(claim: str, evidence: str, text: str, width: int) -> str:
    """A window of the source around the evidence quote, or around the best word overlap with the claim."""
    pos = _find_span(text, evidence) if evidence else -1
    if pos < 0:
        claim_words = set(re.findall(r"[a-z0-9]+", claim.lower())) - {"the", "a", "to", "and", "of", "is", "on", "in", "with"}
        best, pos = -1, 0
        for start in range(0, max(1, len(text) - width // 2), max(50, width // 6)):
            window = set(re.findall(r"[a-z0-9]+", text[start : start + width].lower()))
            score = len(claim_words & window)
            if score > best:
                best, pos = score, start
        return text[pos : pos + width].strip()
    lo = max(0, pos - width // 2)
    return text[lo : lo + width].strip()


def _audit_pick(fact_id: int, key: str, rate: float) -> bool:
    h = int(hashlib.sha1(f"{fact_id}:{key}".encode()).hexdigest(), 16) % 1000
    return h < rate * 1000


def _risk(r, kind: str, idx: str) -> str:
    """Why a wrong approval would matter: values and part numbers drive real repairs."""
    if kind == "spec":
        sp = r.fact.specs[int(idx)]
        return "safety-critical value" if is_safety(sp.value, sp.unit, sp.safety_critical, sp.item) else "specification"
    if kind == "part" and r.fact.parts[int(idx)].part_number:
        return "part number"
    return ""


def build_queue(cfg: Config, conn: sqlite3.Connection, topics: TopicIndex, *, triage: bool = False) -> list[dict[str, Any]]:
    """The Claude review queue. With `triage=True` it is the human's queue instead: claims Claude was unsure about
    (`needs_human`) come first, Claude's confident approvals and rejections stay decided, nothing is sampled for audit,
    and each item carries its thread, a risk label and Claude's note."""
    policy = Policy.from_cfg(cfg)
    rows = load_rows(conn)
    chunk_text = {r["id"]: r["text"] for r in conn.execute("SELECT f.id, c.text FROM facts f JOIN chunks c ON c.id=f.chunk_id")}
    pending = pending_spec_keys(rows, topics, policy, cfg)
    by_gen, _ = route_rows(cfg, rows)   # a fact that publishes in no generation's section is not worth reviewing
    gen_of = {r.id: gid for gid, rs in by_gen.items() for r in rs}
    claude_notes = {(v["fact_id"], v["claim_key"]): v["note"] for v in
                    conn.execute("SELECT fact_id, claim_key, note FROM verdicts WHERE by='claude'")} if triage else {}
    proposals = corrections.load_pending(conn) if triage else {}

    queue: list[dict[str, Any]] = []
    for r in rows:
        if r.id not in gen_of:
            continue
        topic = topics.resolve(r.fact.topic, r.fact.category, gen_of[r.id])
        text = chunk_text[r.id]
        evidence = {f"spec:{i}": s.evidence for i, s in enumerate(r.fact.specs)} | {f"part:{i}": p.evidence for i, p in enumerate(r.fact.parts)}
        for key, claim in claims_for_fact(r.fact):
            kind, _, idx = key.partition(":")
            fix = proposals.get((r.thread_id, kind, corrections.claim_hash(claim))) if kind in corrections.CORRECTABLE else None
            if fix:   # Claude's rewording changes a number: only a person can let it stand (whatever else was said of the claim)
                queue.append({
                    "id": f"f{r.id}:{key}", "priority": 0, "kind": "correction", "claim_kind": kind, "claim_hash": fix["claim_hash"],
                    "why_queued": "Claude reworded this claim and changed a number" + (f": {fix['note']}" if fix["note"] else ""),
                    "page": topic.title, "claim": claim, "corrected": fix["corrected"], "evidence_quote": "",
                    "excerpt": excerpt_for(fix["corrected"], "", text, int(cfg.review.excerpt_chars)),
                    "source_url": r.url, "thread_title": r.thread_title, "local_verdict": r.verdicts.get(key, {}).get("local") or "not run",
                    "thread_id": r.thread_id, "risk": _risk(r, kind, idx),
                })
                continue
            decided = r.verdicts.get(key, {})
            if decided.get("human") or (decided.get("claude") and not (triage and decided["claude"] == "needs_human")):
                continue  # already reviewed (in triage, Claude's own "unsure" is still open)
            if kind in ("spec", "part", "dtc") and not r.grounding[kind + "s"][int(idx)]:
                continue  # fails the deterministic evidence checks: a reviewer cannot rescue it
            if kind in _PROSE and not r.grounding["numbers"][_PROSE[kind]][int(idx)]:
                continue
            if kind in _PROSE and kind != "tool" and r.grounding["copied"][_PROSE[kind]][int(idx)]:
                continue
            local = r.verdicts.get(key, {}).get("local")
            why, prio = "", None
            if triage and decided.get("claude") == "needs_human":
                note = f": {claude_notes[(r.id, key)]}" if claude_notes.get((r.id, key)) else ""
                if key == "complete":   # not doubt: "every step is stated, the list may be incomplete". Already shown as [Partial].
                    why, prio = "Claude found the steps right but the list possibly incomplete (confirm it is complete to drop [Partial])" + note, 1
                else:
                    why, prio = "Claude was unsure" + note, 0
            if prio is None and (r.id, key) in pending:
                why, prio = f"safety-critical value awaiting corroboration ({pending[(r.id, key)]})", 0
            if prio is None and local == "partial":
                why, prio = "local verifier answered partial", 1
            if prio is None and local == DECOY_FAILED:
                why, prio = "local verifier could not be trusted on this call (it accepted a planted false claim)", 1
            if prio is None and kind in _PROSE and policy.publish_unverified_safety and safety_values(claim):
                why, prio = "states a torque/capacity/pressure value that no reviewer has confirmed (published marked if unconfirmed)", 0
            if prio is None and key == "complete" and any(k.startswith("step:") for k in r.corrected):
                why, prio = "a reviewer reworded steps of this procedure: judge the corrected list", 1
            if prio is None and not triage and local == "supported" and _audit_pick(r.id, key, float(cfg.review.audit_rate)):
                why, prio = "audit sample of a locally-supported claim", 2
            if prio is None:
                continue
            queue.append({
                "id": f"f{r.id}:{key}", "priority": prio, "why_queued": why, "kind": kind, "page": topic.title,
                "claim": claim, "evidence_quote": evidence.get(key, ""),
                "excerpt": excerpt_for(claim, evidence.get(key, ""), text, int(cfg.review.excerpt_chars) * (3 if kind == "complete" else 1)),
                "source_url": r.url, "thread_title": r.thread_title, "local_verdict": local or "not run",
                "thread_id": r.thread_id, "risk": _risk(r, kind, idx),
            })
    queue.sort(key=lambda q: (q["priority"], q["id"]))
    return queue


def export_review(cfg: Config, conn: sqlite3.Connection, topics: TopicIndex) -> list[Path]:
    review_dir = cfg.data_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    already: dict[str, set[str]] = {}
    for f in review_dir.glob("batch-*.json"):
        if f.name.endswith(".verdicts.json"):
            continue
        for i in json.loads(f.read_text(encoding="utf-8")).get("items", []):
            already.setdefault(i["id"], set()).add(i["claim"])
    # an id counts as already queued only for the same claim text: a rewritten summary is a new claim to review
    items = [q for q in build_queue(cfg, conn, topics) if q["claim"] not in already.get(q["id"], set())]
    n = len([f for f in review_dir.glob("batch-*.json") if not f.name.endswith(".verdicts.json")])
    size = int(cfg.review.batch_size)
    written: list[Path] = []
    for start in range(0, len(items), size):
        n += 1
        path = review_dir / f"batch-{n:03d}.json"
        path.write_text(json.dumps({
            "instructions": INSTRUCTIONS, "verdict_file": f"{path.stem}.verdicts.json", "items": items[start : start + size],
        }, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written


def apply_reviews(cfg: Config, conn: sqlite3.Connection, paths: list[Path] | None = None, by: str = "claude") -> dict[str, Any]:
    if by not in ("claude", "human"):
        raise ValueError("by must be 'claude' or 'human'")
    files = paths or sorted((cfg.data_dir / "review").glob("*.verdicts.json"))
    applied = rejected_input = stale = fixed = waiting = refused = 0
    for f in files:
        data = json.loads(Path(f).read_text(encoding="utf-8"))
        batch = Path(f).with_name(Path(f).name.replace(".verdicts.json", ".json"))   # the batch these verdicts answer
        judged = {i["id"]: i["claim"] for i in json.loads(batch.read_text(encoding="utf-8")).get("items", [])} if batch.exists() else {}
        entries = [(str(v.get("id", "")), str(v.get("verdict", "")).lower(), v) for v in data.get("verdicts", [])]

        # corrections first, so that a `complete` verdict in the same file counts for the corrected list
        table = corrections.load_accepted(conn)
        before: dict[int, dict[str, str]] = {}   # fact id -> claims as shown before this file's corrections
        touched: set[int] = set()                # facts whose steps this file corrected
        for item_id, verdict, v in entries:
            if verdict != "correct":
                continue
            m = re.match(r"^f(\d+):(.+)$", item_id)
            ctx = corrections.fact_context(conn, int(m.group(1))) if m and CLAIM_KEY.match(m.group(2)) else None
            new = " ".join(str(v.get("corrected") or "").split())
            if ctx is None or corrections.kind_of(m.group(2)) not in corrections.CORRECTABLE or not new:
                rejected_input += 1   # values, metadata, tools and `complete` are judged, never reworded
                continue
            fid, key = int(m.group(1)), m.group(2)
            fact, thread_id, source = ctx
            original = dict(claims_for_fact(fact)).get(key)
            shown = before.setdefault(fid, corrections.displayed_claims(conn, fid, table))
            if original is None or corrections._norm(new) == corrections._norm(shown.get(key, "")):
                rejected_input += 1
                continue
            if item_id in judged and judged[item_id] != shown[key]:
                stale += 1
                continue
            if corrections.refusal(new, source):
                refused += 1   # the same deterministic checks as any extracted claim
                continue
            status = corrections.store(conn, thread_id, key, original, new, by, str(v.get("note", "")))
            fixed += status == "accepted"
            waiting += status == "pending"
            if corrections.kind_of(key) == "step" and status == "accepted":
                touched.add(fid)

        table = corrections.load_accepted(conn)
        for item_id, verdict, v in entries:
            if verdict == "correct":
                continue
            m = re.match(r"^f(\d+):(.+)$", item_id)
            if not m or verdict not in REVIEW_VERDICTS or not CLAIM_KEY.match(m.group(2)) or \
                    not conn.execute("SELECT 1 FROM facts WHERE id=?", (int(m.group(1)),)).fetchone():
                rejected_input += 1
                continue
            fid, key = int(m.group(1)), m.group(2)
            shown = corrections.displayed_claims(conn, fid, table)
            if item_id in judged:   # a verdict judged THAT text; if the claim has changed since, it says nothing about the new one
                same_file = key == "complete" and fid in touched and judged[item_id] == before[fid].get(key)
                if shown.get(key) != judged[item_id] and not same_file:
                    stale += 1
                    continue
            conn.execute("INSERT OR REPLACE INTO verdicts(fact_id, claim_key, by, verdict, note, created_at) VALUES(?,?,?,?,?,?)",
                         (fid, key, by, verdict, str(v.get("note", ""))[:500], now()))
            if key == "complete" and key in shown:
                corrections.record_judged_list(conn, fid, by, shown[key])
            applied += 1
    conn.commit()
    return {"applied": applied, "invalid": rejected_input, "stale": stale, "corrected": fixed, "pending": waiting,
            "refused": refused, **audit_stats(conn)}


def audit_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    """How often did a reviewer reject a claim the local verifier had called 'supported'?"""
    rows = conn.execute(
        """SELECT c.verdict AS review FROM verdicts l JOIN verdicts c
             ON c.fact_id=l.fact_id AND c.claim_key=l.claim_key AND c.by IN ('claude','human')
           WHERE l.by='local' AND l.verdict='supported'"""
    ).fetchall()
    n = len(rows)
    bad = sum(1 for r in rows if r["review"] in ("reject", "needs_human"))
    return {"audited_supported": n, "audited_rejected": bad, "verifier_false_accept_rate": (bad / n) if n else None}
