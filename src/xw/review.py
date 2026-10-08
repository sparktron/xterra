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
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from .config import Config
from .db import now
from .export import Policy, load_rows, pending_spec_keys
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
    "kind `complete` claims a step list is the whole procedure: approve only if the excerpt plainly covers the whole job "
    "and mentions no step, precaution or part the list leaves out; if the excerpt may be cut short, answer needs_human. "
    "kind `applies`/`platform`: approve only if the excerpt says the repair or part applies to those years, trims or vehicles, "
    "not merely that they are mentioned. "
    "Be strict: when unsure, do not approve. Write {\"verdicts\": [{\"id\": ..., \"verdict\": ..., \"note\": ...}]} to the verdict_file."
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


def build_queue(cfg: Config, conn: sqlite3.Connection, topics: TopicIndex) -> list[dict[str, Any]]:
    policy = Policy.from_cfg(cfg)
    rows = load_rows(conn)
    chunk_text = {r["id"]: r["text"] for r in conn.execute("SELECT f.id, c.text FROM facts f JOIN chunks c ON c.id=f.chunk_id")}
    pending = pending_spec_keys(rows, topics, policy, (cfg.scope.years[0], cfg.scope.years[1]))

    queue: list[dict[str, Any]] = []
    for r in rows:
        topic = topics.resolve(r.fact.topic, r.fact.category)
        text = chunk_text[r.id]
        evidence = {f"spec:{i}": s.evidence for i, s in enumerate(r.fact.specs)} | {f"part:{i}": p.evidence for i, p in enumerate(r.fact.parts)}
        for key, claim in claims_for_fact(r.fact):
            kind, _, idx = key.partition(":")
            if r.verdicts.get(key, {}).get("human") or r.verdicts.get(key, {}).get("claude"):
                continue  # already reviewed
            if kind in ("spec", "part", "dtc") and not r.grounding[kind + "s"][int(idx)]:
                continue  # fails the deterministic evidence checks: a reviewer cannot rescue it
            if kind in _PROSE and not r.grounding["numbers"][_PROSE[kind]][int(idx)]:
                continue
            if kind in _PROSE and kind != "tool" and r.grounding["copied"][_PROSE[kind]][int(idx)]:
                continue
            local = r.verdicts.get(key, {}).get("local")
            why, prio = "", None
            if (r.id, key) in pending:
                why, prio = f"safety-critical value awaiting corroboration ({pending[(r.id, key)]})", 0
            if prio is None and local == "partial":
                why, prio = "local verifier answered partial", 1
            if prio is None and local == DECOY_FAILED:
                why, prio = "local verifier could not be trusted on this call (it accepted a planted false claim)", 1
            if prio is None and local == "supported" and _audit_pick(r.id, key, float(cfg.review.audit_rate)):
                why, prio = "audit sample of a locally-supported claim", 2
            if prio is None:
                continue
            queue.append({
                "id": f"f{r.id}:{key}", "priority": prio, "why_queued": why, "kind": kind, "page": topic.title,
                "claim": claim, "evidence_quote": evidence.get(key, ""),
                "excerpt": excerpt_for(claim, evidence.get(key, ""), text, int(cfg.review.excerpt_chars) * (3 if kind == "complete" else 1)),
                "source_url": r.url, "thread_title": r.thread_title, "local_verdict": local or "not run",
            })
    queue.sort(key=lambda q: (q["priority"], q["id"]))
    return queue


def export_review(cfg: Config, conn: sqlite3.Connection, topics: TopicIndex) -> list[Path]:
    review_dir = cfg.data_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    already: set[str] = set()
    for f in review_dir.glob("batch-*.json"):
        if f.name.endswith(".verdicts.json"):
            continue
        already |= {i["id"] for i in json.loads(f.read_text(encoding="utf-8")).get("items", [])}
    items = [q for q in build_queue(cfg, conn, topics) if q["id"] not in already]
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
    applied = rejected_input = 0
    for f in files:
        data = json.loads(Path(f).read_text(encoding="utf-8"))
        for v in data.get("verdicts", []):
            item_id, verdict = str(v.get("id", "")), str(v.get("verdict", "")).lower()
            m = re.match(r"^f(\d+):(.+)$", item_id)
            if not m or verdict not in REVIEW_VERDICTS or not CLAIM_KEY.match(m.group(2)) or \
                    not conn.execute("SELECT 1 FROM facts WHERE id=?", (int(m.group(1)),)).fetchone():
                rejected_input += 1
                continue
            conn.execute("INSERT OR REPLACE INTO verdicts(fact_id, claim_key, by, verdict, note, created_at) VALUES(?,?,?,?,?,?)",
                         (int(m.group(1)), m.group(2), by, verdict, str(v.get("note", ""))[:500], now()))
            applied += 1
    conn.commit()
    return {"applied": applied, "invalid": rejected_input, **audit_stats(conn)}


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
