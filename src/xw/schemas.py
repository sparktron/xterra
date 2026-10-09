"""Structured-extraction schema (what the local LLM must return for each text chunk).

Optional values are modelled as empty strings / 0 rather than null, because constrained-decoding
backends handle plain types more reliably than anyOf-with-null.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CATEGORIES = ("diagnostics", "maintenance", "repair", "mods", "reference")
Category = Literal["diagnostics", "maintenance", "repair", "mods", "reference"]


class _M(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Part(_M):
    name: str
    part_number: str = ""
    notes: str = ""
    evidence: str = ""


class Spec(_M):
    item: str
    value: str
    unit: str = ""
    safety_critical: bool = False
    evidence: str = ""


class Dtc(_M):
    code: str
    description: str = ""
    causes: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    fix: str = ""


class Fact(_M):
    category: Category
    topic: str
    title: str = Field(description="Short specific headline (5-12 words) naming what this fact is or does; never empty")
    summary: str = ""
    years: list[int] = Field(default_factory=list)
    trims: list[str] = Field(default_factory=list)
    engines: list[str] = Field(default_factory=list)
    drivetrain: list[str] = Field(default_factory=list)
    shared_platform: list[Literal["Frontier", "Titan"]] = Field(default_factory=list)
    difficulty: int = 0
    est_time: str = ""
    symptoms: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    parts: list[Part] = Field(default_factory=list)
    specs: list[Spec] = Field(default_factory=list)
    tips: list[str] = Field(default_factory=list)
    mistakes: list[str] = Field(default_factory=list)
    dtcs: list[Dtc] = Field(default_factory=list)
    diagram_links: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _fallback_title(cls, data: Any) -> Any:
        # Some local models omit the required title even when prompted; derive one from topic so a single
        # omission does not fail the whole chunk. Nothing downstream relies on the exact wording of title.
        if isinstance(data, dict):
            t = data.get("title")
            if not (isinstance(t, str) and t.strip()):
                topic = data.get("topic")
                data["title"] = topic.strip() if isinstance(topic, str) and topic.strip() else "General"
        return data

    @field_validator("difficulty", mode="before")
    @classmethod
    def _clamp_difficulty(cls, v: Any) -> int:
        try:
            n = int(v)
        except (TypeError, ValueError):
            return 0
        return max(0, min(5, n))

    @field_validator("years", mode="before")
    @classmethod
    def _years(cls, v: Any) -> list[int]:
        out: list[int] = []
        for item in v or []:
            try:
                n = int(item)
            except (TypeError, ValueError):
                continue
            if 1990 <= n <= 2030 and n not in out:
                out.append(n)
        return sorted(out)


class Extraction(_M):
    relevant: bool = True
    facts: list[Fact] = Field(default_factory=list)


def inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve $ref/$defs so grammar-based backends (llama.cpp, Ollama) get a flat schema."""
    defs = schema.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].rsplit("/", 1)[-1]
                return walk(defs[name])
            return {k: walk(v) for k, v in node.items() if k not in ("$defs", "title", "default")}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


def extraction_schema() -> dict[str, Any]:
    return inline_refs(Extraction.model_json_schema())
