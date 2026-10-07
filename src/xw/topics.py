"""Topic registry: maps model-proposed topic titles onto stable wiki page slugs."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

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


class TopicIndex:
    THRESHOLD = 0.8

    def __init__(self, categories: dict[str, Any]):
        self.topics: list[Topic] = []
        self.category_titles: dict[str, str] = {}
        for cat, body in (categories or {}).items():
            self.category_titles[cat] = body.get("title", cat)
            for t in body.get("topics", []):
                self.topics.append(Topic(cat, t["slug"], t["title"], list(t.get("aliases", []))))

    def titles_for_prompt(self) -> str:
        return "\n".join(f"- [{t.category}] {t.title}" for t in self.topics)

    def resolve(self, suggested: str, category: str) -> Topic:
        """Return the best matching topic (same category), or register and return a new one."""
        best: tuple[float, Topic | None] = (0.0, None)
        for t in self.topics:
            if t.category != category:
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
            if t.category == category and t.slug == slug:
                return t
        new = Topic(category, slug, suggested.strip() or slug, seeded=False)
        self.topics.append(new)
        return new
