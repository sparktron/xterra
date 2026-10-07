"""Second pass: the local model fact-checks every claim another call extracted, against the source text.

A model checking its own work is a filter, not proof (it can repeat the same mistake), so this layer
is combined with deterministic evidence checks (grounding.py), multi-thread agreement for
safety-critical values (export.py) and an optional Claude review of source excerpts (review.py).
The verifier fails closed: a claim it does not explicitly return as "supported" is not supported.
"""
from __future__ import annotations

import sqlite3
from typing import Callable

from .config import Config
from .db import now
from .llm import LLM, LLMError
from .schemas import Fact

Log = Callable[[str], None]

VERDICTS = ("supported", "partial", "unsupported")
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


def claims_for_fact(fact: Fact) -> list[tuple[str, str]]:
    """(claim_key, claim_text) for everything in a fact that is prose or a value."""
    out: list[tuple[str, str]] = []
    if fact.summary:
        out.append(("summary", fact.summary))
    out += [(f"symptom:{i}", t) for i, t in enumerate(fact.symptoms)]
    out += [(f"step:{i}", t) for i, t in enumerate(fact.steps)]
    out += [(f"tool:{i}", f"Tool needed: {t}") for i, t in enumerate(fact.tools)]
    out += [(f"tip:{i}", t) for i, t in enumerate(fact.tips)]
    out += [(f"mistake:{i}", t) for i, t in enumerate(fact.mistakes)]
    out += [(f"spec:{i}", f"{s.item}: {s.value} {s.unit}".strip()) for i, s in enumerate(fact.specs)]
    out += [(f"part:{i}", f"Part: {p.name} {p.part_number}".strip()) for i, p in enumerate(fact.parts)]
    out += [(f"dtc:{i}", f"Trouble code {d.code}: {d.description}".strip()) for i, d in enumerate(fact.dtcs)]
    return out


def verify_claims(llm: LLM, system: str, source_text: str, claims: list[tuple[str, str]]) -> dict[str, str]:
    """Return {claim_key: verdict}. Anything the model omits or garbles is 'unsupported'."""
    verdicts = {key: "unsupported" for key, _ in claims}
    for start in range(0, len(claims), MAX_CLAIMS_PER_CALL):
        batch = claims[start : start + MAX_CLAIMS_PER_CALL]
        listing = "\n".join(f"{n}. {text}" for n, (_, text) in enumerate(batch, 1))
        raw = llm.chat_json(system, f"SOURCE TEXT:\n{source_text}\n\nCLAIMS:\n{listing}", VERIFY_SCHEMA)
        for item in raw.get("verdicts", []):
            try:
                idx = int(item["id"]) - 1
                verdict = str(item["verdict"]).lower()
            except (KeyError, TypeError, ValueError):
                continue
            if 0 <= idx < len(batch) and verdict in VERDICTS:
                verdicts[batch[idx][0]] = verdict
    return verdicts


def verify_pending(cfg: Config, conn: sqlite3.Connection, llm: LLM, *, limit: int | None = None, log: Log = print) -> int:
    system = (cfg.root / "prompts" / "verify.md").read_text(encoding="utf-8")
    rows = conn.execute(
        """SELECT f.id, f.fact_json, c.text FROM facts f JOIN chunks c ON c.id=f.chunk_id
           WHERE NOT EXISTS (SELECT 1 FROM verdicts v WHERE v.fact_id=f.id AND v.by='local') ORDER BY f.id"""
    ).fetchall()
    done = failures = 0
    for row in rows[: limit or None]:
        fact = Fact.model_validate_json(row["fact_json"])
        claims = claims_for_fact(fact)
        try:
            verdicts = verify_claims(llm, system, row["text"], claims) if claims else {"_none": "supported"}
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
        conn.commit()
        done += 1
        counts = {v: list(verdicts.values()).count(v) for v in VERDICTS}
        log(f"  fact {row['id']}: {counts['supported']} supported, {counts['partial']} partial, {counts['unsupported']} unsupported")
    return done
