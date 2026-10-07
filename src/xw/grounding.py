"""Anti-hallucination checks. Local models invent numbers more readily than frontier models, so every
safety-relevant value must be traceable to the source text before it is published.

* spec values   : every number in the value must appear in the source chunk
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
    return all(re.search(rf"(?<![\d.]){re.escape(tok)}(?![\d]|\.\d)", hay) for tok in tokens)


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
    """A spec needs a real quote from the source, and its numbers must sit inside that quote."""
    return evidence_in_text(spec.evidence, text) and spec_grounded(spec.value, spec.unit, spec.evidence)


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
        "copied": {
            "summary": has_long_overlap(fact.summary, text),
            "symptoms": _flags(fact.symptoms, text),
            "steps": _flags(fact.steps, text),
            "tips": _flags(fact.tips, text),
            "mistakes": _flags(fact.mistakes, text),
        },
    }
