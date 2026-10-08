"""Anti-hallucination checks. Local models invent numbers more readily than frontier models, so every
safety-relevant value must be traceable to the source text before it is published.

* spec values   : every number in the value must appear in the source chunk, and a unit the claim gives
                  (ft-lb, in-lb, N·m, qt, L, psi, ...) must be the unit the evidence quote puts on that number
* prose numbers : every number in summaries, steps, symptoms, tips, mistakes and tools must appear in the chunk
* part numbers  : must appear in the chunk (ignoring spaces and dashes)
* trouble codes : must appear in the chunk
* links         : must appear in the chunk
* copying       : text sharing a long verbatim run with the source is flagged (wiki text must be reworded)

Passing a check means "the number appears in the source", not "the number is right for this
procedure". Single-source safety-critical values stay labelled [Unverified] in the wiki.
"""
from __future__ import annotations

import re
from typing import Iterable

from .schemas import Fact

_NUM = re.compile(r"\d+(?:\.\d+)?")


def _flat(text: str) -> str:
    """Lowercase, collapse whitespace, and normalize 1,000 -> 1000 and 7,5 -> 7.5."""
    text = text.lower().replace(" ", " ")
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    return re.sub(r"\s+", " ", text)


def number_tokens(value: str) -> list[str]:
    return _NUM.findall(_flat(value))


def spec_grounded(value: str, unit: str, text: str) -> bool:
    """True when every number in `value` appears in `text` (as a whole number, not a fragment)."""
    tokens = number_tokens(value)
    if not tokens:
        return False
    hay = _flat(text)
    return all(_has_number(tok, hay) for tok in tokens)


def _has_number(tok: str, flat_text: str) -> bool:
    return re.search(rf"(?<![\d.]){re.escape(tok)}(?![\d]|\.\d)", flat_text) is not None


# Canonical units for torque, fluid volume, pressure and small lengths. Order matters: in-lb before N·m etc.
_UNIT_PATTERNS = (
    ("ft-lb", r"ft\.?[\s\-·/]*lbs?\.?f?|lbs?\.?[\s\-·]*f(?:ee)?t\b|foot[\s\-]*pounds?|ft[\s\-]*pounds?|pound[\s\-]*f(?:ee|oo)?t\b"),
    ("in-lb", r"in\.?[\s\-·/]*lbs?\.?f?|lbs?\.?[\-·]?in(?:ch)?\b|inch[\s\-]*pounds?|in[\s\-]*pounds?"),
    ("N·m", r"n[\s\-·.]*m\b|newton[\s\-]*met(?:er|re)s?"),
    ("kgf·m", r"kgf?[\s\-·.]*m\b"),
    ("qt", r"qts?\b|quarts?\b"),
    ("gal", r"gal(?:lon)?s?\b"),
    ("pt", r"pints?\b"),
    ("fl oz", r"(?:us\s*)?fl\.?\s*oz\b|fluid[\s\-]*ounces?\b"),
    ("oz", r"oz\b|ounces?\b"),   # plain ounces are usually weight ("16 oz hammer"), so not a fluid volume
    ("ml", r"ml\b|cc\b"),
    ("L", r"l\b|lit(?:er|re)s?\b|ltrs?\b"),
    ("psi", r"psi\b"),
    ("kPa", r"kpa\b"),
    ("bar", r"bar\b"),
    ("mm", r"mm\b"),
)
_U = "(?<![a-z])(?:" + "|".join(f"(?P<u{i}>{p})" for i, (_, p) in enumerate(_UNIT_PATTERNS)) + ")"
# A unit belongs to a number only when it sits right next to it: "83 ft-lb", "83ft-lbs", "80-90 ft lbs",
# "80 to 90 N·m", or before it as "ft-lbs: 80". "2 sway bar bolts" gives 2 no unit.
_UNIT_AFTER = re.compile(r"\s*(?:(?:-|–|to|or|/|~)\s*\d+(?:\.\d+)?\s*)?" + _U)
_UNIT_BEFORE = re.compile(_U + r"\.?\s*[:=]?\s*$")
SAFETY_UNITS = frozenset({"ft-lb", "in-lb", "N·m", "kgf·m", "qt", "gal", "pt", "fl oz", "ml", "L", "psi", "kPa", "bar"})
# Engine displacements on this platform (QR25DE 2.5L, VQ40DE 4.0L, VK56DE 5.6L) are engine names, not fluid volumes.
_DISPLACEMENTS = frozenset({"2.5", "4.0", "5.6"})


def _canon(m: re.Match) -> str:
    return next(_UNIT_PATTERNS[int(k[1:])][0] for k, v in m.groupdict().items() if k.startswith("u") and v is not None)


def _unit_near(flat: str, start: int, end: int) -> str | None:
    after = _UNIT_AFTER.match(flat, end)
    if after:
        return _canon(after)
    before = _UNIT_BEFORE.search(flat[max(0, start - 25):start])
    return _canon(before) if before else None


def numbers_with_units(text: str) -> list[tuple[str, str | None]]:
    """(number, canonical unit or None) for every number in `text`."""
    flat = _flat(text)
    return [(m.group(), _unit_near(flat, m.start(), m.end())) for m in _NUM.finditer(flat)]


def unit_grounded(value: str, unit: str, text: str) -> bool:
    """Every number the claim gives a unit to must carry that same unit somewhere in `text`.
    Catches "80 ft-lb" claimed from a source that says "80 in-lb" or "80 Nm" (spec_grounded only sees "80")."""
    have: dict[str, set[str | None]] = {}
    for num, u in numbers_with_units(text):
        have.setdefault(num, set()).add(u)
    return all(u in have.get(num, set()) for num, u in numbers_with_units(f"{value} {unit}") if u is not None)


def safety_values(text: str) -> set[tuple[str, str]]:
    """(number, unit) pairs in `text` whose unit is a torque, fluid-volume or pressure unit."""
    return {(n, u) for n, u in numbers_with_units(text) if u in SAFETY_UNITS and not (u == "L" and n in _DISPLACEMENTS)}


_SMALL = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve")


def numbers_grounded(candidate: str, text: str) -> bool:
    """Every number in reworded prose must appear in the source (a small count may appear spelled out)."""
    hay = _flat(text)
    for tok in number_tokens(candidate):
        if _has_number(tok, hay):
            continue
        if tok.isdigit() and int(tok) < len(_SMALL) and re.search(rf"\b{_SMALL[int(tok)]}\b", hay):
            continue
        return False
    return True


def _compact(s: str) -> str:
    return re.sub(r"[^0-9a-z]", "", s.lower())


def part_grounded(part_number: str, text: str) -> bool:
    pn = _compact(part_number)
    if len(pn) < 4:
        return False
    return pn in _compact(text)


def dtc_grounded(code: str, text: str) -> bool:
    code = code.strip()
    if not code:
        return False
    return re.search(rf"(?<![0-9a-z]){re.escape(code)}(?![0-9a-z])", text, re.I) is not None


def link_grounded(url: str, text: str) -> bool:
    return bool(url) and url in text


def _squash(s: str) -> str:
    s = s.lower().replace(" ", " ")
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("–", "-"), ("—", "-"), ("−", "-")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def evidence_in_text(evidence: str, text: str, min_len: int = 8) -> bool:
    """The model's quoted evidence must exist in the source (whitespace/case/quote-style insensitive)."""
    ev = re.sub(r"^(\.\.\.|…)+|(\.\.\.|…)+$", "", _squash(evidence)).strip(" .")
    return len(ev) >= min_len and ev in _squash(text)


def spec_evidenced(spec, text: str) -> bool:
    """A spec needs a real quote from the source, its numbers must sit inside that quote, and a unit the
    claim gives must be the unit the quote puts on that number."""
    return (evidence_in_text(spec.evidence, text) and spec_grounded(spec.value, spec.unit, spec.evidence)
            and unit_grounded(spec.value, spec.unit, spec.evidence))


def part_evidenced(part, text: str) -> bool:
    if not part.part_number:
        return True
    return evidence_in_text(part.evidence, text) and part_grounded(part.part_number, part.evidence)


def grounded_terms(terms: list[str], text: str) -> list[str]:
    """Keep only terms (trims, engines, platforms) that the source text actually mentions."""
    out = []
    for t in terms:
        t = t.strip()
        # word-boundary match so a short trim like "SE" is not "found" inside "raise"
        if t and re.search(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])", text, re.I):
            out.append(t)
    return out


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


def has_long_overlap(candidate: str, source: str, n: int = 12) -> bool:
    """True when `candidate` shares a run of `n` consecutive words with `source`."""
    cw = _words(candidate)
    if len(cw) < n:
        return False
    sw = _words(source)
    grams = {tuple(sw[i : i + n]) for i in range(len(sw) - n + 1)}
    return any(tuple(cw[i : i + n]) in grams for i in range(len(cw) - n + 1))


def _flags(items: Iterable[str], source: str) -> list[bool]:
    return [has_long_overlap(i, source) for i in items]


def ground_fact(fact: Fact, text: str) -> dict:
    """Per-item grounding and copy flags, index-aligned with the lists inside `fact`."""
    return {
        "specs": [spec_grounded(s.value, s.unit, text) and spec_evidenced(s, text) for s in fact.specs],
        "parts": [(part_grounded(p.part_number, text) and part_evidenced(p, text)) if p.part_number else True for p in fact.parts],
        "dtcs": [dtc_grounded(d.code, text) for d in fact.dtcs],
        "diagrams": [link_grounded(u, text) for u in fact.diagram_links],
        "numbers": {
            "summary": numbers_grounded(fact.summary, text),
            "symptoms": [numbers_grounded(i, text) for i in fact.symptoms],
            "steps": [numbers_grounded(i, text) for i in fact.steps],
            "tools": [numbers_grounded(i, text) for i in fact.tools],
            "tips": [numbers_grounded(i, text) for i in fact.tips],
            "mistakes": [numbers_grounded(i, text) for i in fact.mistakes],
        },
        "copied": {
            "summary": has_long_overlap(fact.summary, text),
            "symptoms": _flags(fact.symptoms, text),
            "steps": _flags(fact.steps, text),
            "tips": _flags(fact.tips, text),
            "mistakes": _flags(fact.mistakes, text),
        },
    }
