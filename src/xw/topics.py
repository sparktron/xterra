"""Topic registry: maps model-proposed topic titles onto stable wiki page slugs, one tree per model generation."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

DEFAULT_GENERATION = "second-gen"

_STOP = {"how", "to", "a", "the", "of", "and", "for", "on", "in", "my", "your", "nissan", "xterra", "diy", "guide", "install",
         "installation", "replace", "replacement", "replacing", "change", "changing", "fix", "repair"}


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len].rstrip("-")) or "untitled"


def _tokens(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in _STOP:
            continue
        out.add(w[:-1] if len(w) > 3 and w.endswith("s") else w)
    return out


def _score(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    ratio = SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio() if ta and tb else 0.0
    jac = len(ta & tb) / len(ta | tb) if ta and tb else 0.0
    return max(ratio, jac)


@dataclass
class Topic:
    category: str
    slug: str
    title: str
    aliases: list[str] = field(default_factory=list)
    seeded: bool = True
    generation: str = DEFAULT_GENERATION


class TopicIndex:
    """`spec` is topics.yaml's `generations` mapping ({gen: {"categories": {...}}}), or a legacy single tree of
    categories, which is the second generation's. Topics never match across generations."""

    THRESHOLD = 0.8

    def __init__(self, spec: dict[str, Any]):
        self.topics: list[Topic] = []
        self._categories: dict[str, dict[str, str]] = {}
        spec = spec or {}
        trees = spec if any(isinstance(v, dict) and "categories" in v for v in spec.values()) else \
            ({DEFAULT_GENERATION: {"categories": spec}} if spec else {})
        for gen, body in trees.items():
            cats = self._categories.setdefault(gen, {})
            for cat, cbody in (body.get("categories") or {}).items():
                cats[cat] = cbody.get("title", cat)
                for t in cbody.get("topics", []):
                    self.topics.append(Topic(cat, t["slug"], t["title"], list(t.get("aliases", [])), generation=gen))

    @property
    def generations(self) -> list[str]:
        return list(self._categories)

    def category_titles_for(self, generation: str = DEFAULT_GENERATION) -> dict[str, str]:
        return self._categories.get(generation, {})

    @property
    def category_titles(self) -> dict[str, str]:
        return self.category_titles_for(DEFAULT_GENERATION)

    def topics_for(self, generation: str = DEFAULT_GENERATION) -> list[Topic]:
        return [t for t in self.topics if t.generation == generation]

    def titles_for_prompt(self, generation: str = DEFAULT_GENERATION) -> str:
        return "\n".join(f"- [{t.category}] {t.title}" for t in self.topics_for(generation))

    def resolve(self, suggested: str, category: str, generation: str = DEFAULT_GENERATION) -> Topic:
        """Return the best matching topic (same generation and category), or register and return a new one."""
        best: tuple[float, Topic | None] = (0.0, None)
        for t in self.topics:
            if t.category != category or t.generation != generation:
                continue
            names = [t.title, t.slug.replace("-", " "), *t.aliases]
            exact = any(suggested.strip().lower() == n.lower() for n in names)
            score = 1.0 if exact else max(_score(suggested, n) for n in names)
            if score > best[0]:
                best = (score, t)
        if best[1] is not None and best[0] >= self.THRESHOLD:
            return best[1]
        slug = slugify(suggested)
        for t in self.topics:
            if t.category == category and t.slug == slug and t.generation == generation:
                return t
        new = Topic(category, slug, suggested.strip() or slug, seeded=False, generation=generation)
        self.topics.append(new)
        return new
