"""Model generations. The wiki keeps one completely separate section per generation (the first-generation WD22
Xterra and the second-generation N50 share almost nothing), so every fact is routed to exactly one generation or
published in none.

Routing is deterministic and does not trust the model:
  * the model years a fact states (kept only when the source text names them, see extract.py) decide first;
  * a fact that states none takes its source's `generation` (sources.yaml), e.g. a 2005-2015 subforum;
  * years in two generations, or no years and no source generation: the fact publishes nowhere and is listed
    in the top-level open questions.
A claim that names another generation ("unlike the first gen ...", "VG33", "2nd gen") is withheld from a page
by the exporter, and `qa` refuses it independently, so one generation's facts never appear in the other's section.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .config import Config

DEFAULT = "second-gen"   # the generation of a legacy single-tree topics.yaml


@dataclass(frozen=True)
class Generation:
    id: str
    title: str
    years: tuple[int, int]
    markers: re.Pattern[str]
    prompt_vehicle: str
    prompt_offtopic: str

    def covers(self, year: int) -> bool:
        return self.years[0] <= year <= self.years[1]


def load(cfg: Config) -> list[Generation]:
    return from_spec(cfg.generations)


def from_spec(spec: dict) -> list[Generation]:
    out = []
    for gid, g in spec.items():
        out.append(Generation(gid, g["title"], (int(g["years"][0]), int(g["years"][1])),
                              re.compile("|".join(f"(?:{m})" for m in g.get("markers") or [r"(?!x)x"]), re.I),
                              g.get("prompt_vehicle", g["title"]), g.get("prompt_offtopic", "other vehicles")))
    return sorted(out, key=lambda g: g.years)


def by_id(cfg: Config) -> dict[str, Generation]:
    return {g.id: g for g in load(cfg)}


def source_generation(cfg: Config, source_id: str) -> str | None:
    for s in cfg.sources:
        if s.get("id") == source_id:
            return s.get("generation") or None
    return None


def route(years: list[int], source_gen: str | None, gens: list[Generation], title: str = "") -> tuple[str | None, str]:
    """(generation id, why) for a fact: why is empty when it is routed, else the reason it publishes nowhere.
    `title`: the fact's own title and topic. A fact whose title names another generation than the one it would go to
    (a first-gen note posted in a second-gen forum, say) is not trusted to either and publishes nowhere."""
    hit = {g.id for y in years for g in gens if g.covers(y)}
    if len(hit) > 1:
        return None, "its model years span " + " and ".join(g.title for g in gens if g.id in hit)
    gid = hit.pop() if hit else (source_gen if source_gen and any(g.id == source_gen for g in gens) else None)
    if gid is None:
        return None, "it states no model year and its source has no generation"
    gen = next(g for g in gens if g.id == gid)
    if title and (o := other_marker(title, gen, gens)):
        return None, f"it would go to the {gen.title} but its title names the {o.title}"
    return gid, ""


def other_marker(text: str, gen: Generation, gens: list[Generation]) -> Generation | None:
    """The other generation `text` names, if any (it must not publish on `gen`'s pages)."""
    for g in gens:
        if g.id != gen.id and g.markers.search(text):
            return g
    return None
