"""`xw qa`: an independent final gate over the PUBLISHED wiki.

It does not trust the exporter. It re-reads the generated pages and re-checks, against the raw source text
stored in the database, that:
  * every published specification value appears in a thread the line cites, with the unit the line gives it
  * a torque, capacity or pressure value anywhere else on the page (prose, tools, parts) is also a published
    specification line on that page
  * every published part number appears in a thread the line cites
  * every torque-like value carries an allowed verification tag (consensus, manufacturer, or reviewed)
  * no cited thread id is unknown
  * generation separation: a page sits in its own generation's section (front matter `generation`), every thread it
    cites has a fact that routes to that generation (re-derived from the database, not read from the exporter), and
    no published line names another generation
The hand-curated pages under wiki/<generation>/vehicle/ have no thread text to check against; `check_curated` holds
them to a citation rule instead: every line that states a number cites a source listed on that page, or says
[Unverified]; and, like generated pages, they must not name another generation.
Exit status 1 on any violation, so it can gate commits and CI.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import json

from . import generations
from .config import DEFAULTS, Config
from .generations import Generation, other_marker
from .grounding import part_grounded, safety_values, spec_grounded, unit_grounded
from .export import CURATED_DIR, GENERATED, PARTIAL, SAFETY_NOTE, UNVERIFIED_VALUE, is_safety

SPEC_LINE = re.compile(r"^- \*\*(?P<item>.+?)\*\*: (?P<value>.+?) \[(?P<sids>t\d+(?:, t\d+)*)\] \((?P<tag>[^)]*)\)\s*$")
PART_LINE = re.compile(r"^- (?P<name>.+?) \((?P<pn>[^)]+)\)(?::.*?)? \[(?P<sids>t\d+(?:, t\d+)*)\]\s*$")
SAFE_TAGS = ("community-consensus", "manufacturer source", "Claude-reviewed", "Human-reviewed")
_URL = re.compile(r"https?://\S+")
SRC_KEY = re.compile(r"\[S(\d+)\]")
SRC_DEF = re.compile(r"^- \[S(\d+)\] .*https?://\S+")
_LOCAL_LINK = re.compile(r"\[(?P<text>[^\]]*)\]\((?!https?:)[^)]*\)")
_YEAR_NAV = re.compile(r"(?:← )?(?:19|20)\d\d(?: →)?")   # "[2005](years/2005.md)", "[← 2008](2008.md)"
_TABLE_RULE = re.compile(r"^\|?\s*:?-{3,}")


def _thread_text(conn: sqlite3.Connection, sid: str) -> str | None:
    tid = int(sid[1:])
    if not conn.execute("SELECT 1 FROM threads WHERE id=?", (tid,)).fetchone():
        return None
    return "\n".join(r["text"] for r in conn.execute("SELECT text FROM chunks WHERE thread_id=? ORDER BY idx", (tid,)))


def _thread_generations(cfg: Config, conn: sqlite3.Connection, gl: list[Generation]) -> dict[int, set[str]]:
    """thread id -> generations its facts route to, recomputed from fact years and source generations."""
    out: dict[int, set[str]] = {}
    for r in conn.execute("SELECT f.thread_id, f.fact_json, t.source_id FROM facts f JOIN threads t ON t.id=f.thread_id"):
        fact = json.loads(r["fact_json"])
        gid, _ = generations.route(fact.get("years") or [], generations.source_generation(cfg, r["source_id"]), gl,
                                   f"{fact.get('title', '')} {fact.get('topic', '')}")
        if gid:
            out.setdefault(r["thread_id"], set()).add(gid)
    return out


def check_wiki(cfg: Config, conn: sqlite3.Connection) -> list[str]:
    violations: list[str] = []
    wiki = Path(cfg.wiki_dir)
    gl = generations.load(cfg)
    gen_ids = {g.id for g in gl}
    for stray in sorted(wiki.glob("*/*.md")):   # the single-section layout from before the generations were split
        if stray.parent.name not in gen_ids and stray.read_text(encoding="utf-8", errors="ignore").startswith(GENERATED):
            violations.append(f"{stray.relative_to(wiki)}: generated page outside a generation's section")
    thread_gens = _thread_generations(cfg, conn, gl)
    for page in sorted(p for g in gl for p in (wiki / g.id).glob("*/*.md")):
        lines = page.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != GENERATED:
            continue
        rel = page.relative_to(wiki)
        gen = next(g for g in gl if g.id == rel.parts[0])
        body = lines.index("---", 2) + 1 if lines[1:2] == ["---"] and "---" in lines[2:] else 1
        if f"generation: {gen.id}" not in lines[1:body]:
            violations.append(f"{rel}: page is in the {gen.id} section but its front matter does not say generation: {gen.id}")
        for tid in sorted({int(s[1:]) for s in re.findall(r"\bt\d+\b", _URL.sub("", "\n".join(lines[body:])))}):   # not "albums/t503/"
            if gen.id not in thread_gens.get(tid, set()):
                violations.append(f"{rel}: cites t{tid}, which has no fact in the {gen.title}")
        sect = ""
        for line in lines[body:]:
            if line.startswith("## "):
                sect = line[3:].strip()
            elif sect != "Source attributions" and (o := other_marker(_URL.sub("", line), gen, gl)):
                violations.append(f"{rel}: names the {o.title} on a {gen.title} page: {line[:100]}")
        # only real Specifications lines count as published; a spec-shaped line elsewhere must not exempt itself
        published: set[tuple[str, str]] = set()
        unconfirmed: set[tuple[str, str]] = set()   # safety values published marked [Unverified]/[Partial]
        banner = SAFETY_NOTE in lines
        if any(UNVERIFIED_VALUE in line for line in lines[body:]) and not banner:
            violations.append(f"{rel}: [Unverified value] in the body but no warning banner")
        sec = ""
        for line in lines[body:]:
            if line.startswith("## "):
                sec = line[3:].strip()
            elif sec == "Specifications" and (m := SPEC_LINE.match(line)):
                published |= safety_values(m["value"])
                if not any(m["tag"].startswith(t) for t in SAFE_TAGS):
                    unconfirmed |= safety_values(m["value"])
        section = ""
        for line in lines[body:]:
            if line.startswith("## "):
                section = line[3:].strip()
                continue
            if section == "Specifications":
                m = SPEC_LINE.match(line)
                if line.startswith("- ") and "DISPUTED" in line:
                    if is_safety(line, "", False):
                        violations.append(f"{rel}: disputed torque-like value published: {line[:100]}")
                    continue
                if line.startswith("- ") and not m:
                    violations.append(f"{rel}: unparseable specification line: {line[:100]}")
                    continue
                if not m:
                    continue
                sids = m["sids"].split(", ")
                texts = [_thread_text(conn, s) for s in sids]
                if any(t is None for t in texts):
                    violations.append(f"{rel}: cites an unknown thread: {line[:100]}")
                    continue
                if not any(spec_grounded(m["value"], "", t or "") for t in texts):
                    violations.append(f"{rel}: value not found in cited thread(s): {m['item']}: {m['value']}")
                elif not any(unit_grounded(m["value"], "", t or "") for t in texts):
                    violations.append(f"{rel}: unit not found with that value in cited thread(s): {m['item']}: {m['value']}")
                confirmed = any(m["tag"].startswith(t) for t in SAFE_TAGS)
                marked = "[Unverified]" in m["tag"] or m["tag"].startswith(PARTIAL)
                need = int(cfg.verify.safety_min_threads)
                if is_safety(m["value"], "", False, m["item"]) and (c := re.match(r"community-consensus, (\d+) threads", m["tag"])) \
                        and int(c[1]) < need:
                    violations.append(f"{rel}: safety value tagged community-consensus with {c[1]} thread(s), below "
                                      f"verify.safety_min_threads ({need}): {m['item']}: {m['value']}")
                if is_safety(m["value"], "", False, m["item"]) and not confirmed and not (marked and banner):
                    violations.append(f"{rel}: safety-critical value without corroboration, review or a visible [Unverified]/[Partial] "
                                      f"mark under the warning banner: {m['item']}: {m['value']} ({m['tag']})")
                continue
            if section != "Source attributions":
                vals = safety_values(_URL.sub("", line))
                if vals & unconfirmed and UNVERIFIED_VALUE not in line:
                    violations.append(f"{rel}: unconfirmed safety value repeated in prose without {UNVERIFIED_VALUE}: {line[:100]}")
                loose = vals - published
                if loose and UNVERIFIED_VALUE in line:   # an unconfirmed value without a spec, marked as such (export.loose):
                    # the source must put that unit on that number (step lines cite their thread in the procedure footer)
                    texts = [_thread_text(conn, s_) or "" for s_ in sorted(set(re.findall(r"\bt\d+\b", "\n".join(lines))))]
                    if any(unit_grounded(_URL.sub("", line), "", tx) for tx in texts):
                        loose = set()
                if loose:
                    violations.append(f"{rel}: safety-critical value outside the specifications: {', '.join(f'{n} {u}' for n, u in sorted(loose))}: {line[:100]}")
            if section == "Parts":
                m = PART_LINE.match(line)
                if m:
                    texts = [_thread_text(conn, s) or "" for s in m["sids"].split(", ")]
                    if not any(part_grounded(m["pn"], t) for t in texts):
                        violations.append(f"{rel}: part number not found in cited thread(s): {m['name']} ({m['pn']})")
    return violations + check_curated(wiki, gl)


def check_curated(wiki_dir: Path, gens: list[Generation] | None = None) -> list[str]:
    """Hand-curated pages (wiki/<generation>/vehicle/): each needs a `## Sources` list of `- [S<n>] ... <url>` entries,
    every [S<n>] it uses must be listed, and any line stating a number (outside headings, table header rows and the
    list itself) must cite one or say [Unverified]. Only traceability is checked; that the source says it is still the
    author's job. A line must not name another generation (markers from the config, or the defaults)."""
    violations: list[str] = []
    gl = gens or generations.from_spec(DEFAULTS["generations"])
    by_id = {g.id: g for g in gl}
    if (wiki_dir / CURATED_DIR).is_dir():
        violations.append(f"{CURATED_DIR}/: curated pages outside a generation's section (move them to <generation>/{CURATED_DIR}/)")
    for page in sorted(p for g in gl for p in (wiki_dir / g.id / CURATED_DIR).rglob("*.md")):
        rel = page.relative_to(wiki_dir)
        gen = by_id[rel.parts[0]]
        lines = page.read_text(encoding="utf-8").splitlines()
        if lines and lines[0] == GENERATED:
            violations.append(f"{rel}: curated page carries the generated header")
            continue
        if "## Sources" not in lines:
            violations.append(f"{rel}: curated page has no '## Sources' section")
            continue
        listed = {m[1] for line in lines[lines.index("## Sources"):] if (m := SRC_DEF.match(line))}
        section = ""
        for i, line in enumerate(lines):
            if line.startswith("#"):
                section = line.lstrip("#").strip()
                continue
            if section == "Sources":
                if line.startswith("- ") and not SRC_DEF.match(line):
                    violations.append(f"{rel}: source entry without a key and URL: {line[:100]}")
                continue
            if _TABLE_RULE.match(line) or (i + 1 < len(lines) and _TABLE_RULE.match(lines[i + 1])):
                continue
            used = set(SRC_KEY.findall(line))
            if used - listed:
                violations.append(f"{rel}: cites unlisted source(s) {', '.join(f'S{n}' for n in sorted(used - listed))}: {line[:100]}")
            # a link's target states nothing, but its text can ("[Oil capacity is 5 qt](oil-change.md)");
            # only a bare model-year label is navigation
            unlinked = _LOCAL_LINK.sub(lambda m: "" if _YEAR_NAV.fullmatch(m["text"].strip()) else m["text"], line)
            bare = SRC_KEY.sub("", _URL.sub("", unlinked))
            if re.search(r"\d", bare) and not used and "[Unverified]" not in line:
                violations.append(f"{rel}: number without a source: {line[:100]}")
            if o := other_marker(_URL.sub("", line), gen, gl):
                violations.append(f"{rel}: names the {o.title} on a {gen.title} page: {line[:100]}")
    return violations
