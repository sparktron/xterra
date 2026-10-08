"""`xw qa`: an independent final gate over the PUBLISHED wiki.

It does not trust the exporter. It re-reads the generated pages and re-checks, against the raw source text
stored in the database, that:
  * every published specification value appears in a thread the line cites, with the unit the line gives it
  * a torque, capacity or pressure value anywhere else on the page (prose, tools, parts) is also a published
    specification line on that page
  * every published part number appears in a thread the line cites
  * every torque-like value carries an allowed verification tag (consensus, manufacturer, or reviewed)
  * no cited thread id is unknown
Exit status 1 on any violation, so it can gate commits and CI.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from .config import Config
from .grounding import part_grounded, safety_values, spec_grounded, unit_grounded
from .export import GENERATED, is_safety

SPEC_LINE = re.compile(r"^- \*\*(?P<item>.+?)\*\*: (?P<value>.+?) \[(?P<sids>t\d+(?:, t\d+)*)\] \((?P<tag>[^)]*)\)\s*$")
PART_LINE = re.compile(r"^- (?P<name>.+?) \((?P<pn>[^)]+)\)(?::.*?)? \[(?P<sids>t\d+(?:, t\d+)*)\]\s*$")
SAFE_TAGS = ("community-consensus", "manufacturer source", "Claude-reviewed", "Human-reviewed")
_URL = re.compile(r"https?://\S+")


def _thread_text(conn: sqlite3.Connection, sid: str) -> str | None:
    tid = int(sid[1:])
    if not conn.execute("SELECT 1 FROM threads WHERE id=?", (tid,)).fetchone():
        return None
    return "\n".join(r["text"] for r in conn.execute("SELECT text FROM chunks WHERE thread_id=? ORDER BY idx", (tid,)))


def check_wiki(cfg: Config, conn: sqlite3.Connection) -> list[str]:
    violations: list[str] = []
    for page in sorted(Path(cfg.wiki_dir).glob("*/*.md")):
        lines = page.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != GENERATED:
            continue
        rel = page.relative_to(cfg.wiki_dir)
        body = lines.index("---", 2) + 1 if lines[1:2] == ["---"] and "---" in lines[2:] else 1
        # only real Specifications lines count as published; a spec-shaped line elsewhere must not exempt itself
        published: set[tuple[str, str]] = set()
        sec = ""
        for line in lines[body:]:
            if line.startswith("## "):
                sec = line[3:].strip()
            elif sec == "Specifications" and (m := SPEC_LINE.match(line)):
                published |= safety_values(m["value"])
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
                if is_safety(m["value"], "", False, m["item"]) and not any(m["tag"].startswith(t) for t in SAFE_TAGS):
                    violations.append(f"{rel}: safety-critical value without corroboration/review: {m['item']}: {m['value']} ({m['tag']})")
                continue
            if section != "Source attributions":
                loose = safety_values(_URL.sub("", line)) - published
                if loose:
                    violations.append(f"{rel}: safety-critical value outside the specifications: {', '.join(f'{n} {u}' for n, u in sorted(loose))}: {line[:100]}")
            if section == "Parts":
                m = PART_LINE.match(line)
                if m:
                    texts = [_thread_text(conn, s) or "" for s in m["sids"].split(", ")]
                    if not any(part_grounded(m["pn"], t) for t in texts):
                        violations.append(f"{rel}: part number not found in cited thread(s): {m['name']} ({m['pn']})")
    return violations
