"""Second pass: the local model fact-checks every claim another call extracted, against the source text.

A model checking its own work is a filter, not proof (it can repeat the same mistake), so this layer
is combined with deterministic evidence checks (grounding.py), multi-thread agreement for
safety-critical values (export.py) and an optional Claude review of source excerpts (review.py).
The verifier fails closed: a claim it does not explicitly return as "supported" is not supported.

Decoys: every call also carries one or two planted false claims (a real claim with one number changed to a
number the source never states, or a real claim with an invented torque step appended). A verifier that calls a
decoy "supported" is rubber-stamping, so that call's verdicts are discarded; after a second failed attempt every
claim in it is stored as `decoy_failed` and withheld. `decoy_checks` records the rate per fact (`xw status`).
"""
from __future__ import annotations

import random
import re
import sqlite3
from collections import defaultdict
from typing import Any, Callable

from .config import Config
from .db import now
from .grounding import spec_grounded
from .llm import LLM, LLMError
from .schemas import Fact

Log = Callable[[str], None]

VERDICTS = ("supported", "partial", "unsupported")
DECOY_FAILED = "decoy_failed"   # stored local verdict: the call judging this claim also accepted a planted false claim
VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "verdict": {"type": "string", "enum": list(VERDICTS)}},
                "required": ["id", "verdict"],
            },
        }
    },
    "required": ["verdicts"],
}
MAX_CLAIMS_PER_CALL = 30
DECOY_ATTEMPTS = 2
DIFFICULTY_WORDS = {1: "very easy", 2: "easy", 3: "moderate", 4: "hard", 5: "very hard"}
_NUM = re.compile(r"\d+(?:\.\d+)?")


def claims_for_fact(fact: Fact) -> list[tuple[str, str]]:
    """(claim_key, claim_text) for everything the exporter publishes from a fact: prose, values and metadata."""
    out: list[tuple[str, str]] = []
    if fact.summary:
        out.append(("summary", fact.summary))
    out += [(f"symptom:{i}", t) for i, t in enumerate(fact.symptoms)]
    out += [(f"step:{i}", t) for i, t in enumerate(fact.steps)]
    if fact.steps:
        # each step can be true while the list still drops one; the procedure publishes only if this holds too
        out.append(("complete", "These steps are the whole procedure the source gives for this job, with no step, "
                                "precaution or required part left out: " + "; ".join(fact.steps)))
    out += [(f"tool:{i}", f"Tool needed: {t}") for i, t in enumerate(fact.tools)]
    out += [(f"tip:{i}", t) for i, t in enumerate(fact.tips)]
    out += [(f"mistake:{i}", t) for i, t in enumerate(fact.mistakes)]
    out += [(f"spec:{i}", f"{s.item}: {s.value} {s.unit}".strip()) for i, s in enumerate(fact.specs)]
    out += [(f"part:{i}", _part_claim(p)) for i, p in enumerate(fact.parts)]
    out += [(f"dtc:{i}", _dtc_claim(d)) for i, d in enumerate(fact.dtcs)]
    applies = _applies_claim(fact)
    if applies:
        out.append(("applies", applies))
    if fact.shared_platform:
        out.append(("platform", "The same part or procedure also applies to the Nissan " + " and the Nissan ".join(fact.shared_platform) + "."))
    if fact.difficulty:
        out.append(("difficulty", f"The source indicates this job is {DIFFICULTY_WORDS[fact.difficulty]}."))
    if fact.est_time:
        out.append(("time", f"The job takes about {fact.est_time}."))
    return [(key, _one_line(text)) for key, text in out]


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def _applies_claim(fact: Fact) -> str:
    """Years, trims, engines and drivetrain are printed in each page's front matter, so they are claims too."""
    parts = []
    if fact.years:
        parts.append("model years " + ", ".join(str(y) for y in fact.years))
    for label, values in (("trims", fact.trims), ("engines", fact.engines), ("drivetrain", fact.drivetrain)):
        if values:
            parts.append(f"{label} " + ", ".join(values))
    return f"This repair, part or information applies to {'; '.join(parts)}." if parts else ""


def _part_claim(p) -> str:
    """Everything the exporter publishes about a part (name, number AND notes) must be verified."""
    claim = f"Part: {p.name} {p.part_number}".strip()
    return _one_line(claim + (f". Note: {p.notes}" if p.notes else ""))


def _dtc_claim(d) -> str:
    """Everything the DTC table publishes (description, causes, tests, fix) must be verified."""
    claim = f"Trouble code {d.code}: {d.description}".strip()
    if d.causes:
        claim += ". Possible causes: " + "; ".join(d.causes)
    if d.tests:
        claim += ". Tests: " + "; ".join(d.tests)
    if d.fix:
        claim += f". Fix: {d.fix}"
    return _one_line(claim)


# ---- decoys ---------------------------------------------------------------------------------------
def _fresh_number(tok: str, source_text: str, rng: random.Random) -> str:
    """A number near `tok`, in the same format, that does not appear anywhere in the source."""
    decimals = len(tok.split(".")[1]) if "." in tok else 0
    base = float(tok)
    for _ in range(100):
        delta = rng.choice((1, 2, 3, 5, 7, 10, 15, 20, 25, 40)) * (0.5 if decimals else 1)
        cand = base - delta if base - delta > 0 and rng.random() < 0.4 else base + delta
        text = f"{cand:.{decimals}f}"
        if text != tok and not spec_grounded(text, "", source_text):
            return text
    return f"{base + 997:.{decimals}f}"


def make_decoy(claim: str, source_text: str, rng: random.Random) -> str:
    """A claim that is false against `source_text` by construction: it states a number the source never states."""
    nums = list(_NUM.finditer(claim))
    if nums:
        m = rng.choice(nums)
        return claim[: m.start()] + _fresh_number(m.group(), source_text, rng) + claim[m.end():]
    n = _fresh_number(str(rng.randint(20, 90)), source_text, rng)
    return f"{claim.rstrip('. ')}, then torque the bolts to {n} ft-lb."


def _new_stats() -> dict[str, int]:
    return {"calls": 0, "decoys": 0, "accepted": 0, "discarded": 0}


def _judge(llm: LLM, system: str, source_text: str, batch: list[tuple[str, str]], attempt: int,
           stats: dict[str, int]) -> tuple[dict[str, str], bool]:
    """One verifier call over `batch` plus planted decoys. Returns (verdicts for real claims, decoys all caught)."""
    rng = random.Random("\x1f".join([source_text, *(t for _, t in batch), str(attempt)]))
    decoys = [make_decoy(rng.choice(batch)[1], source_text, rng) for _ in range(1 if len(batch) < 10 else 2)]
    items: list[tuple[str | None, str]] = list(batch) + [(None, d) for d in decoys]
    rng.shuffle(items)
    listing = "\n".join(f"{n}. {text}" for n, (_, text) in enumerate(items, 1))
    raw = llm.chat_json(system, f"SOURCE TEXT:\n{source_text}\n\nCLAIMS:\n{listing}", VERIFY_SCHEMA)
    got: dict[int, str] = {}
    for item in raw.get("verdicts", []):
        try:
            idx = int(item["id"]) - 1
            verdict = str(item["verdict"]).lower()
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= idx < len(items) and verdict in VERDICTS:
            got[idx] = verdict
    accepted = sum(1 for i, (key, _) in enumerate(items) if key is None and got.get(i) == "supported")
    stats["calls"] += 1
    stats["decoys"] += len(decoys)
    stats["accepted"] += accepted
    return {items[i][0]: v for i, v in got.items() if items[i][0] is not None}, accepted == 0  # type: ignore[misc]


def verify_claims(llm: LLM, system: str, source_text: str, claims: list[tuple[str, str]],
                  stats: dict[str, int] | None = None) -> dict[str, str]:
    """Return {claim_key: verdict}. Anything the model omits or garbles is 'unsupported'; anything judged in a
    call that also accepted a decoy (twice) is 'decoy_failed'."""
    stats = stats if stats is not None else _new_stats()
    verdicts = {key: "unsupported" for key, _ in claims}
    for start in range(0, len(claims), MAX_CLAIMS_PER_CALL):
        batch = claims[start : start + MAX_CLAIMS_PER_CALL]
        for attempt in range(DECOY_ATTEMPTS):
            result, clean = _judge(llm, system, source_text, batch, attempt, stats)
            if clean:
                verdicts.update(result)
                break
            stats["discarded"] += 1
        else:
            verdicts.update({key: DECOY_FAILED for key, _ in batch})
    return verdicts


def decoy_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    r = conn.execute("SELECT COALESCE(SUM(calls),0) c, COALESCE(SUM(decoys),0) d, COALESCE(SUM(accepted),0) a, "
                     "COALESCE(SUM(discarded),0) x FROM decoy_checks").fetchone()
    return {"calls": r["c"], "decoys": r["d"], "accepted": r["a"], "discarded_calls": r["x"],
            "decoy_accept_rate": (r["a"] / r["d"]) if r["d"] else None}


def verify_pending(cfg: Config, conn: sqlite3.Connection, llm: LLM, *, limit: int | None = None, redo: bool = False,
                   log: Log = print) -> int:
    """Verify every claim that has no local verdict yet (so claims added to `claims_for_fact` later get checked on
    existing facts). `redo` re-verifies everything. Returns the number of facts verified."""
    system = (cfg.root / "prompts" / "verify.md").read_text(encoding="utf-8")
    have: dict[int, set[str]] = defaultdict(set)
    if not redo:
        for v in conn.execute("SELECT fact_id, claim_key FROM verdicts WHERE by='local'"):
            have[v["fact_id"]].add(v["claim_key"])
    rows = conn.execute("SELECT f.id, f.fact_json, c.text FROM facts f JOIN chunks c ON c.id=f.chunk_id ORDER BY f.id").fetchall()
    done = failures = 0
    for row in rows:
        if limit and done >= limit:
            break
        fact = Fact.model_validate_json(row["fact_json"])
        all_claims = claims_for_fact(fact)
        claims = [c for c in all_claims if c[0] not in have[row["id"]]]
        if not all_claims and "_none" not in have[row["id"]]:
            conn.execute("INSERT OR REPLACE INTO verdicts(fact_id, claim_key, by, verdict, created_at) VALUES(?,?,?,?,?)",
                         (row["id"], "_none", "local", "supported", now()))
            conn.commit()
            done += 1
            continue
        if not claims:
            continue
        stats = _new_stats()
        try:
            verdicts = verify_claims(llm, system, row["text"], claims, stats)
        except LLMError as exc:
            failures += 1
            log(f"  fact {row['id']}: {exc}")
            if failures >= cfg.extract.max_consecutive_failures:
                log("  too many consecutive LLM failures; stopping verification")
                break
            continue
        failures = 0
        conn.executemany(
            "INSERT OR REPLACE INTO verdicts(fact_id, claim_key, by, verdict, created_at) VALUES(?,?,?,?,?)",
            [(row["id"], key, "local", verdict, now()) for key, verdict in verdicts.items()],
        )
        conn.execute("INSERT INTO decoy_checks(fact_id, calls, decoys, accepted, discarded, created_at) VALUES(?,?,?,?,?,?)",
                     (row["id"], stats["calls"], stats["decoys"], stats["accepted"], stats["discarded"], now()))
        conn.commit()
        done += 1
        counts = {v: list(verdicts.values()).count(v) for v in (*VERDICTS, DECOY_FAILED)}
        decoy_note = f"; decoys accepted {stats['accepted']}/{stats['decoys']}" if stats["accepted"] else ""
        log(f"  fact {row['id']}: {counts['supported']} supported, {counts['partial']} partial, {counts['unsupported']} unsupported"
            + (f", {counts[DECOY_FAILED]} discarded (verifier accepted a decoy)" if counts[DECOY_FAILED] else "") + decoy_note)
    return done
