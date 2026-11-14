"""`xw qa`: an independent final gate over the PUBLISHED wiki.

It independently checks the saved models against the raw source text in the database, and checks that rendered
files match those models. For a modified page it also parses the page to give detailed tampering diagnostics. It checks that:
  * every published specification value appears in a thread the line cites, with the unit the line gives it
  * a torque, capacity or pressure value anywhere else on the page (prose, tools, parts) is also a published
    specification line on that page
  * every published part number appears in a thread the line cites
  * every torque-like value carries an allowed verification tag (consensus, manufacturer, or reviewed)
  * no cited thread id is unknown
  * generation separation: a page sits in its own generation's section (front matter `generation`), every thread it
    cites has a fact that routes to that generation (re-derived from the database, not read from the exporter), and
    no published line names another generation
  * no step or list item is empty: nothing but marks such as [Partial] and thread ids
  * every local link in a generated index or page reaches a file, so an export that lost pages cannot pass, and a
    topic page's guide link goes stale only until the next export
The hand-curated pages under wiki/<generation>/vehicle/ have no thread text to check against; `check_curated` holds
them to a citation rule instead: every line that states a number cites a source listed on that page, or says
[Unverified]; and, like generated pages, they must not name another generation.
Exit status 1 on any violation, so it can gate commits and CI.
"""
from __future__ import annotations

import re
import sqlite3
from difflib import SequenceMatcher
from pathlib import Path

import json

from . import generations
from .config import DEFAULTS, Config
from .generations import Generation, other_marker
from .grounding import dtc_grounded, grounded_years, number_tokens, part_grounded, safety_values, spec_grounded, unit_grounded
from .export import COMMENT_END, CURATED_DIR, GENERATED, PARTIAL, SAFETY_NOTE, UNVERIFIED_VALUE, is_safety

SPEC_LINE = re.compile(r"^- \*\*(?P<item>.+?)\*\*: (?P<value>.+?) \[(?P<sids>t\d+(?:, t\d+)*)\] \((?P<tag>[^)]*)\)\s*$")
PART_LINE = re.compile(r"^- (?P<name>.+?) \((?P<pn>[^)]+)\)(?::.*?)? \[(?P<sids>t\d+(?:, t\d+)*)\]\s*$")
SAFE_TAGS = ("community-consensus", "manufacturer source", "Claude-reviewed", "Human-reviewed")
_URL = re.compile(r"https?://\S+")
SRC_KEY = re.compile(r"\[S(\d+)\]")
SRC_DEF = re.compile(r"^- \[S(\d+)\] .*https?://\S+")
_LOCAL_LINK = re.compile(r"\[(?P<text>[^\]]*)\]\((?!https?:)[^)]*\)")
_YEAR_NAV = re.compile(r"(?:← )?(?:19|20)\d\d(?: →)?")   # "[2005](years/2005.md)", "[← 2008](2008.md)"
_TABLE_RULE = re.compile(r"^\|?\s*:?-{3,}")
_EMPTY_ITEM = re.compile(rf"^(?:-|\d+\.)(?:\s*(?:{re.escape(PARTIAL)}|{re.escape(UNVERIFIED_VALUE)}|\[t\d+(?:, t\d+)*\]))*\s*$")
_LINK_TARGET = re.compile(r"\]\((?P<target>[^)\s]+)\)")


def _metadata_end(lines: list[str]) -> int | None:
    """Index of the line after a generated page's metadata comment (export._metadata_comment), or None if the metadata
    is not wholly inside one: then it would show as text above the page's heading."""
    if lines[1:3] != ["<!--", "---"]:
        return None
    end = next((i for i, line in enumerate(lines[3:], 3) if COMMENT_END.search(line)), None)
    return end + 1 if end and lines[end] == "-->" and lines[end - 1] == "---" else None


def _thread_text(conn: sqlite3.Connection, sid: str) -> str | None:
    tid = int(sid[1:])
    if not conn.execute("SELECT 1 FROM threads WHERE id=?", (tid,)).fetchone():
        return None
    return "\n".join(r["text"] for r in conn.execute("SELECT text FROM chunks WHERE thread_id=? ORDER BY idx", (tid,)))


def _thread_generations(cfg: Config, conn: sqlite3.Connection, gl: list[Generation]) -> dict[int, set[str]]:
    """thread id -> generations its facts route to, recomputed from fact years and source generations."""
    out: dict[int, set[str]] = {}
    for r in conn.execute("SELECT f.thread_id, f.fact_json, t.source_id, c.text FROM facts f JOIN threads t ON t.id=f.thread_id "
                          "JOIN chunks c ON c.id=f.chunk_id"):
        fact = json.loads(r["fact_json"])
        years = grounded_years(fact.get("years") or [], r["text"])   # the exporter's rule: a post header's date is not a model year
        gid, _ = generations.route(years, generations.source_generation(cfg, r["source_id"]), gl,
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
        # Source validation runs on the saved model. If the rendered file was edited, retain the legacy
        # diagnostics as well as the model-consistency failure, so existing tampering checks stay informative.
        from .export import PageModel, render_model
        try:
            saved = json.loads((cfg.data_dir / "model" / rel.with_suffix(".json")).read_text(encoding="utf-8"))
            same_as_model = page.read_text(encoding="utf-8") == render_model(PageModel(**saved))[0] + "\n"
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            same_as_model = False
        body = _metadata_end(lines)
        if body is None:
            violations.append(f"{rel}: metadata is not in an HTML comment, so it shows as text on the page")
            body = 1
        violations += _missing_links(page, lines[body:], wiki)
        if same_as_model:
            # Source checks run on the model. Keep small format checks so a renderer regression cannot make
            # an unparseable specification, visible metadata or an empty list item look like a valid page.
            if f"generation: {gen.id}" not in lines[1:body]:
                violations.append(f"{rel}: page is in the {gen.id} section but its front matter does not say generation: {gen.id}")
            banner = SAFETY_NOTE in lines
            if (saved["single_source_safety"] or saved["unconfirmed_values"]) and not banner:
                violations.append(f"{rel}: unconfirmed safety values without warning banner")
            unconfirmed_values = set(map(tuple, saved["unconfirmed_values"]))
            for spec in saved["specifications"]:
                if "alternatives" not in spec and not any(spec["tag"].startswith(t) for t in SAFE_TAGS):
                    unconfirmed_values |= safety_values(spec["display"])
            section = ""
            for line in lines[body:]:
                if line.startswith("## "):
                    section = line[3:].strip()
                elif _EMPTY_ITEM.match(line):
                    violations.append(f"{rel}: empty step or list item: {line!r}")
                elif section == "Specifications" and line.startswith("- ") and "DISPUTED" not in line and not SPEC_LINE.match(line):
                    violations.append(f"{rel}: unparseable specification line: {line[:100]}")
                elif section == "Specifications" and line.startswith("- ") and "DISPUTED" in line and is_safety(line, "", False):
                    violations.append(f"{rel}: disputed torque-like value published: {line[:100]}")
                elif section == "Specifications" and (spec_line := SPEC_LINE.match(line)):
                    tag = spec_line["tag"]
                    if is_safety(spec_line["value"], "", False, spec_line["item"]):
                        confirmed = any(tag.startswith(t) for t in SAFE_TAGS)
                        marked = "[Unverified]" in tag or tag.startswith(PARTIAL)
                        consensus = re.match(r"community-consensus, (\d+) threads", tag)
                        if consensus and int(consensus[1]) < int(cfg.verify.safety_min_threads):
                            violations.append(f"{rel}: safety value tagged community-consensus below verify.safety_min_threads")
                        if not confirmed and not (marked and banner):
                            violations.append(f"{rel}: safety-critical value without corroboration, review or a visible mark under the warning banner")
                elif section not in ("Specifications", "Source attributions") and safety_values(_URL.sub("", line)) & unconfirmed_values and UNVERIFIED_VALUE not in line:
                    violations.append(f"{rel}: unconfirmed safety value repeated in prose without {UNVERIFIED_VALUE}: {line[:100]}")
            # Parsing below is retained for detailed diagnostics on manually edited files.
            continue
        if f"generation: {gen.id}" not in lines[1:body]:
            violations.append(f"{rel}: page is in the {gen.id} section but its front matter does not say generation: {gen.id}")
        for line in lines[1:body]:   # front matter metadata (engines, trims, shared platform) is published too
            if o := other_marker(_URL.sub("", line), gen, gl):
                violations.append(f"{rel}: names the {o.title} in the front matter of a {gen.title} page: {line[:100]}")
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
            if _EMPTY_ITEM.match(line):
                violations.append(f"{rel}: empty step or list item: {line!r}")
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
                if not same_as_model:
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
                    texts = [] if same_as_model else [_thread_text(conn, s_) or "" for s_ in sorted(set(re.findall(r"\bt\d+\b", "\n".join(lines))))]
                    if same_as_model or any(unit_grounded(_URL.sub("", line), "", tx) for tx in texts):
                        loose = set()
                if loose:
                    violations.append(f"{rel}: safety-critical value outside the specifications: {', '.join(f'{n} {u}' for n, u in sorted(loose))}: {line[:100]}")
            if section == "Parts":
                m = PART_LINE.match(line)
                if m and not same_as_model:
                    texts = [_thread_text(conn, s) or "" for s in m["sids"].split(", ")]
                    if not any(part_grounded(m["pn"], t) for t in texts):
                        violations.append(f"{rel}: part number not found in cited thread(s): {m['name']} ({m['pn']})")
    return violations + check_page_models(cfg, conn) + check_index_links(wiki, gl) + check_curated(wiki, gl)


def check_page_models(cfg: Config, conn: sqlite3.Connection) -> list[str]:
    """Rebuild gated data against current source chunks, and compare model and rendered page."""
    from dataclasses import asdict
    from .export import (DiagramReportModel, DtcTableModel, IndexModel, InterchangeModel, PageModel, PendingModel, Policy, QuestionsModel, SourceReportModel, UnroutedModel, WikiIndexModel,
                         build_diagram_report, build_dtc_model, build_index_model, build_interchange_model,
                         build_page_model, build_pages, build_questions_model, build_source_report, build_unrouted_model, load_rows, render_diagram_report, render_dtc_model,
                         render_index_model, render_interchange_model, render_model, render_pending_model, render_questions_model, render_source_report, render_unrouted_model, render_wiki_index, route_rows, GUIDES_DIR)
    from .topics import TopicIndex

    violations: list[str] = []
    models = cfg.data_dir / "model"
    gl = generations.load(cfg)
    routed, unrouted = route_rows(cfg, load_rows(conn))
    thread_gens = _thread_generations(cfg, conn, gl)
    topics, policy = TopicIndex(cfg.topics), Policy.from_cfg(cfg)
    expected_paths = set()
    for gen in gl:
        summary = {}
        pending, unconfirmed, dropped, disputes, single = [], [], [], [], []
        for (category, slug), page in sorted(build_pages(routed[gen.id], topics, gen.id).items()):
            rel = Path(gen.id) / category / f"{slug}.json"
            expected_paths.add(rel)
            guide = f"../{GUIDES_DIR}/{slug}.md" if (cfg.wiki_dir / gen.id / GUIDES_DIR / f"{slug}.md").exists() else ""
            expected = build_page_model(page, gen.years, policy, gl, guide)
            summary[f"{category}/{slug}"] = {"title": page.topic.title, **render_model(expected)[1]}
            pending += [{"topic": page.topic.title, **d} for d in expected.pending]
            unconfirmed += [{"topic": page.topic.title, **d} for d in expected.unconfirmed]
            dropped += [(page.topic.title, d) for d in page.dropped]
            disputes += [(page.topic.title, d) for d in page.disputes]
            single += [(page.topic.title, d) for d in page.single_source_safety]
            model_path, wiki_path = models / rel, cfg.wiki_dir / rel.with_suffix(".md")
            try:
                saved = json.loads(model_path.read_text(encoding="utf-8"))
                # JSON normalizes tuples to arrays; compare the same representation.
                expected_data = json.loads(json.dumps(asdict(expected), ensure_ascii=False))
                if saved != expected_data:
                    violations.append(f"{rel}: page model differs from source-grounded gate")
                violations += check_model_values(saved, conn, rel, int(cfg.verify.safety_min_threads),
                                                 bool(cfg.verify.get("publish_unverified_safety", True)))
                violations += check_model_generation(saved, gen, gl, thread_gens, rel)
                rendered, _ = render_model(PageModel(**saved))
                if not wiki_path.exists() or wiki_path.read_text(encoding="utf-8") != rendered + "\n":
                    violations.append(f"{wiki_path.relative_to(cfg.wiki_dir)}: rendered page differs from page model")
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                violations.append(f"{rel}: missing or invalid page model: {exc}")
        rel = Path(gen.id) / "reports" / "dtc_table.json"
        expected_paths.add(rel)
        try:
            saved = json.loads((models / rel).read_text(encoding="utf-8"))
            expected = build_dtc_model(routed[gen.id], policy, lambda text: other_marker(text, gen, gl) is None)
            if saved != asdict(expected):
                violations.append(f"{rel}: DTC model differs from source-grounded gate")
            for item in saved["items"]:
                sids = item["source_ids"]
                texts = [_thread_text(conn, sid) for sid in sids if re.fullmatch(r"t\d+", sid)]
                if not any(dtc_grounded(item["code"], text or "") for text in texts):
                    violations.append(f"{rel}: DTC not found in cited thread(s): {item['code']}")
                for text in [item["description"], *item["likely_causes_ranked"], *item["test_steps"], *item["fix"]]:
                    if safety_values(text) or other_marker(text, gen, gl):
                        violations.append(f"{rel}: invalid DTC advice: {text}")
            violations += check_dtc_provenance(saved, conn, rel)
            target = cfg.wiki_dir / gen.id / "dtc_table.csv"
            if not target.is_file() or target.read_bytes() != render_dtc_model(DtcTableModel(**saved)).encode("utf-8"):
                violations.append(f"{target.relative_to(cfg.wiki_dir)}: rendered table differs from DTC model")
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            violations.append(f"{rel}: missing or invalid DTC model: {exc}")
        rel = Path(gen.id) / "reports" / "parts_diagrams.json"
        expected_paths.add(rel)
        try:
            saved = json.loads((models / rel).read_text(encoding="utf-8"))
            if saved != asdict(build_diagram_report(routed[gen.id], topics, gen)):
                violations.append(f"{rel}: diagram model differs from source-grounded gate")
            for item in saved["items"]:
                sid = item["source_id"]
                source = _thread_text(conn, sid) if re.fullmatch(r"t\d+", sid) else None
                if not source or item["url"] not in source:
                    violations.append(f"{rel}: diagram link not found in cited thread: {item['url']}")
            target = cfg.wiki_dir / gen.id / "parts_diagrams.md"
            if not target.is_file() or target.read_text(encoding="utf-8") != render_diagram_report(DiagramReportModel(**saved)):
                violations.append(f"{target.relative_to(cfg.wiki_dir)}: rendered report differs from diagram model")
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            violations.append(f"{rel}: missing or invalid diagram model: {exc}")
        rel = Path(gen.id) / "reports" / "interchange.json"
        expected_paths.add(rel)
        try:
            saved = json.loads((models / rel).read_text(encoding="utf-8"))
            if saved != asdict(build_interchange_model(routed[gen.id], topics, gen, gl, policy)):
                violations.append(f"{rel}: interchange model differs from source-grounded gate")
            for item in saved["items"]:
                if other_marker(" ".join(item["platforms"]), gen, gl):
                    violations.append(f"{rel}: interchange names another generation")
                for sid in item["source_ids"]:
                    if not re.fullmatch(r"t\d+", sid) or _thread_text(conn, sid) is None:
                        violations.append(f"{rel}: interchange cites unknown thread {sid}")
                platforms, years = set(), set()
                for claim in item["provenance"]:
                    source = conn.execute("SELECT f.fact_json, f.thread_id, c.text FROM facts f JOIN chunks c ON c.id=f.chunk_id WHERE f.id=?",
                                          (claim["fact_id"],)).fetchone()
                    if not source or claim["source_id"] != f"t{source['thread_id']}" or claim["claim_key"] != "platform":
                        violations.append(f"{rel}: invalid interchange source claim")
                        continue
                    fact = json.loads(source["fact_json"])
                    if not set(claim["platforms"]) <= set(fact.get("shared_platform") or []):
                        violations.append(f"{rel}: interchange platform absent from source claim")
                    if claim["years"] and (claim["years_claim_key"] != "applies" or
                                           not set(claim["years"]) <= set(grounded_years(fact.get("years") or [], source["text"]))):
                        violations.append(f"{rel}: interchange year absent from source claim")
                    platforms.update(claim["platforms"])
                    years.update(claim["years"])
                if platforms != set(item["platforms"]) or years != set(item["years"]):
                    violations.append(f"{rel}: interchange provenance does not cover published values")
            target = cfg.wiki_dir / gen.id / "interchange.md"
            if not target.is_file() or target.read_text(encoding="utf-8") != render_interchange_model(InterchangeModel(**saved)):
                violations.append(f"{target.relative_to(cfg.wiki_dir)}: rendered report differs from interchange model")
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            violations.append(f"{rel}: missing or invalid interchange model: {exc}")
        rel = Path(gen.id) / "reports" / "index.json"
        expected_paths.add(rel)
        try:
            saved = json.loads((models / rel).read_text(encoding="utf-8"))
            if saved != asdict(build_index_model(topics, gen, gl, cfg.wiki_dir / gen.id, summary)):
                violations.append(f"{rel}: index model differs from source-grounded pages")
            target = cfg.wiki_dir / gen.id / "index.md"
            if not target.is_file() or target.read_text(encoding="utf-8") != render_index_model(IndexModel(**saved)):
                violations.append(f"{target.relative_to(cfg.wiki_dir)}: rendered index differs from model")
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            violations.append(f"{rel}: missing or invalid index model: {exc}")
        rel = Path(gen.id) / "reports" / "pending_verification.json"
        expected_paths.add(rel)
        try:
            saved = json.loads((models / rel).read_text(encoding="utf-8"))
            expected = PendingModel(gen.title, policy.safety_min_threads, pending, unconfirmed)
            if saved != json.loads(json.dumps(asdict(expected), ensure_ascii=False)):
                violations.append(f"{rel}: pending model differs from source-grounded pages")
            target = cfg.wiki_dir / gen.id / "pending_verification.md"
            if not target.is_file() or target.read_text(encoding="utf-8") != render_pending_model(PendingModel(**saved)):
                violations.append(f"{target.relative_to(cfg.wiki_dir)}: rendered report differs from pending model")
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            violations.append(f"{rel}: missing or invalid pending model: {exc}")
        rel = Path(gen.id) / "reports" / "sources.json"
        expected_paths.add(rel)
        try:
            saved = json.loads((models / rel).read_text(encoding="utf-8"))
            if saved != asdict(build_source_report(conn, routed[gen.id], topics, gen)):
                violations.append(f"{rel}: source report model differs from database")
            target = cfg.wiki_dir / gen.id / "sources.json"
            if not target.is_file() or target.read_text(encoding="utf-8") != render_source_report(SourceReportModel(**saved)):
                violations.append(f"{target.relative_to(cfg.wiki_dir)}: rendered report differs from source model")
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            violations.append(f"{rel}: missing or invalid source model: {exc}")
        rel = Path(gen.id) / "reports" / "open_questions.json"
        expected_paths.add(rel)
        try:
            saved = json.loads((models / rel).read_text(encoding="utf-8"))
            missing = [t for t in topics.topics_for(gen.id) if f"{t.category}/{t.slug}" not in summary]
            expected = build_questions_model(cfg, conn, gen, disputes, single, dropped, missing)
            if saved != asdict(expected):
                violations.append(f"{rel}: questions model differs from source-grounded pages")
            target = cfg.wiki_dir / gen.id / "open_questions.md"
            if not target.is_file() or target.read_text(encoding="utf-8") != render_questions_model(QuestionsModel(**saved)):
                violations.append(f"{target.relative_to(cfg.wiki_dir)}: rendered report differs from questions model")
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            violations.append(f"{rel}: missing or invalid questions model: {exc}")
    rel = Path("reports/index.json")
    expected_paths.add(rel)
    try:
        saved = json.loads((models / rel).read_text(encoding="utf-8"))
        expected = WikiIndexModel([{"id": gen.id, "title": gen.title,
                                   "pages": len(build_pages(routed[gen.id], topics, gen.id)),
                                   "facts": len(routed[gen.id])} for gen in gl])
        if saved != asdict(expected):
            violations.append(f"{rel}: wiki index model differs from source-grounded pages")
        target = cfg.wiki_dir / "index.md"
        if not target.is_file() or target.read_text(encoding="utf-8") != render_wiki_index(WikiIndexModel(**saved)):
            violations.append("index.md: rendered index differs from model")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        violations.append(f"{rel}: missing or invalid wiki index model: {exc}")
    rel = Path("reports/open_questions.json")
    expected_paths.add(rel)
    try:
        saved = json.loads((models / rel).read_text(encoding="utf-8"))
        if saved != asdict(build_unrouted_model(conn, unrouted)):
            violations.append(f"{rel}: unrouted model differs from source routing")
        target = cfg.wiki_dir / "open_questions.md"
        if not target.is_file() or target.read_text(encoding="utf-8") != render_unrouted_model(UnroutedModel(**saved)):
            violations.append("open_questions.md: rendered report differs from model")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        violations.append(f"{rel}: missing or invalid unrouted model: {exc}")
    if models.exists():
        for model_path in models.rglob("*.json"):
            if model_path.relative_to(models) not in expected_paths:
                violations.append(f"{model_path.relative_to(models)}: stale page model")
    return violations


def check_model_generation(model: dict, gen: Generation, gl: list[Generation],
                           thread_gens: dict[int, set[str]], rel: Path) -> list[str]:
    violations = []
    if model["metadata"]["generation"] != gen.id:
        violations.append(f"{rel}: model is in the wrong generation")
    # Source attribution titles and URLs are citations, not claims about the page's generation.
    claims = [model["title"], json.dumps(model["metadata"], ensure_ascii=False)]
    claims += [entry[0] for entries in model["lists"].values() for entry in entries]
    claims += [step for procedure in model["procedures"] for step in procedure["steps"]]
    claims += [" ".join([part["name"], part["part_number"], *part["notes"]]) for part in model["parts"]]
    for spec in model["specifications"]:
        claims.append(spec["item"])
        claims += [value["display"] for value in spec.get("alternatives", [spec])]
    for claim in claims:
        if other := other_marker(_URL.sub("", claim), gen, gl):
            violations.append(f"{rel}: model names the {other.title} on a {gen.title} page: {claim[:100]}")
    cited = {source["sid"] for source in model["sources"]}
    cited.update(sid for entries in model["lists"].values() for _, sids, _ in entries for sid in sids)
    cited.update(procedure["sid"] for procedure in model["procedures"])
    cited.update(sid for part in model["parts"] for sid in part["sids"])
    cited.update(sid for spec in model["specifications"] for value in spec.get("alternatives", [spec]) for sid in value["sids"])
    cited.update(sid for _, sid in model["diagrams"])
    for sid in sorted(cited):
        if not re.fullmatch(r"t\d+", sid) or gen.id not in thread_gens.get(int(sid[1:]), set()):
            violations.append(f"{rel}: model cites {sid}, which has no fact in the {gen.title}")
    return violations


def check_dtc_provenance(model: dict, conn: sqlite3.Connection, rel: Path) -> list[str]:
    """Check that each published DTC field is attributable to an actual source claim."""
    violations = []
    items = {item["code"]: item for item in model["items"]}
    covered: set[tuple[str, str, str]] = set()
    codes: set[str] = set()
    for claim in model["provenance"]:
        code = claim["code"]
        source = conn.execute("SELECT f.fact_json, f.thread_id, c.text FROM facts f JOIN chunks c ON c.id=f.chunk_id WHERE f.id=?",
                              (claim["fact_id"],)).fetchone()
        match = re.fullmatch(r"dtc:(\d+)", claim["claim_key"])
        if not source or not match or claim["source_id"] != f"t{source['thread_id']}" or code not in items:
            violations.append(f"{rel}: invalid DTC source claim: {code}")
            continue
        dtcs = json.loads(source["fact_json"]).get("dtcs", [])
        index = int(match[1])
        if index >= len(dtcs) or dtcs[index].get("code", "").strip().upper() != code or not dtc_grounded(code, source["text"]):
            violations.append(f"{rel}: DTC source claim is not grounded: {code}")
            continue
        codes.add(code)
        dtc = dtcs[index]
        for field, values in claim["fields"].items():
            original = {"description": [dtc.get("description", "")], "likely_causes_ranked": dtc.get("causes", []),
                        "test_steps": dtc.get("tests", []), "fix": [dtc.get("fix", "")]}.get(field, [])
            published = [items[code][field]] if field == "description" else items[code].get(field, [])
            for value in values:
                def corresponds(raw: str) -> bool:
                    if raw == value or raw.strip() == value:
                        return True
                    normalize = lambda text: re.sub(r"\W+", " ", text.lower()).strip()
                    return (field in ("test_steps", "fix") and sorted(number_tokens(raw)) == sorted(number_tokens(value))
                            and SequenceMatcher(None, normalize(raw), normalize(value)).ratio() >= 0.88)
                if value not in published or not any(corresponds(raw) for raw in original if raw):
                    violations.append(f"{rel}: DTC field lacks a matching source claim: {code}: {value}")
                else:
                    covered.add((code, field, value))
    for code, item in items.items():
        if code not in codes:
            violations.append(f"{rel}: DTC has no source claim: {code}")
        for field in ("description", "likely_causes_ranked", "test_steps", "fix"):
            values = [item[field]] if field == "description" else item[field]
            for value in values:
                if value and (code, field, value) not in covered:
                    violations.append(f"{rel}: DTC field has no source claim: {code}: {value}")
    return violations


def check_model_values(model: dict, conn: sqlite3.Connection, rel: Path, safety_min_threads: int = 2,
                       publish_unverified_safety: bool = True) -> list[str]:
    """Independently check model values against the cited threads, not rendered Markdown."""
    violations: list[str] = []
    cache: dict[str, str | None] = {}

    def texts(sids: list[str]) -> list[str]:
        result = []
        for sid in sids:
            if not re.fullmatch(r"t\d+", sid):
                violations.append(f"{rel}: invalid source id: {sid}")
                continue
            if sid not in cache:
                cache[sid] = _thread_text(conn, sid)
            if cache[sid] is None:
                violations.append(f"{rel}: cites an unknown thread: {sid}")
            else:
                result.append(cache[sid])
        return result

    for spec in model["specifications"]:
        for value in spec.get("alternatives", [spec]):
            sources = texts(value["sids"])
            display = value["display"]
            if not any(spec_grounded(display, "", t) for t in sources):
                violations.append(f"{rel}: model value not found in cited thread(s): {spec['item']}: {display}")
            elif not any(unit_grounded(display, "", t) for t in sources):
                violations.append(f"{rel}: model unit not found with value in cited thread(s): {spec['item']}: {display}")
            if is_safety(display, "", False, spec["item"]):
                if "alternatives" in spec:
                    violations.append(f"{rel}: disputed safety value in model: {spec['item']}: {display}")
                    continue
                tag = value["tag"]
                confirmed = any(tag.startswith(t) for t in SAFE_TAGS)
                marked = "[Unverified]" in tag or tag.startswith(PARTIAL)
                consensus = re.match(r"community-consensus, (\d+) threads", tag)
                if consensus and int(consensus[1]) < safety_min_threads:
                    violations.append(f"{rel}: model consensus below safety threshold: {spec['item']}: {display}")
                if not confirmed and not marked:
                    violations.append(f"{rel}: model safety value without confirmation or mark: {spec['item']}: {display}")
                if not confirmed and marked and not (model.get("single_source_safety") or model.get("unconfirmed_values")):
                    violations.append(f"{rel}: model safety value has no warning banner: {spec['item']}: {display}")
    for part in model["parts"]:
        if part["part_number"] and not any(part_grounded(part["part_number"], t) for t in texts(part["sids"])):
            violations.append(f"{rel}: model part number not found in cited thread(s): {part['name']} ({part['part_number']})")
    metadata_fields = {"years": ("years", "applies"), "trims": ("trims", "applies"),
                       "engine": ("engines", "applies"), "drivetrain": ("drivetrain", "applies"),
                       "shared_platform": ("shared_platform", "platform"), "difficulty": ("difficulty", "difficulty"),
                       "est_time": ("est_time", "time")}
    if "metadata" in model:
        fm = model["metadata"]
        expected_metadata = {(name, value) for name, values in (
            ("years", fm["applies_to"]["years"]), ("trims", fm["applies_to"]["trims"]),
            ("engine", fm["applies_to"]["engine"]), ("drivetrain", fm["applies_to"]["drivetrain"]),
            ("shared_platform", fm["shared_platform"]),
            ("difficulty", [fm["difficulty"]] if fm["difficulty"] else []),
            ("est_time", [fm["est_time"]] if fm["est_time"] else [])) for value in values}
        recorded_metadata = {(item["field"], item["value"]) for item in model["metadata_provenance"]}
        if expected_metadata != recorded_metadata:
            violations.append(f"{rel}: metadata provenance does not cover published values")
    for item in model.get("metadata_provenance", []):
        field, claim_key = metadata_fields[item["field"]]
        if not item["claims"]:
            violations.append(f"{rel}: metadata value has no source claim: {item['field']}: {item['value']}")
        for claim in item["claims"]:
            source = conn.execute("SELECT f.fact_json, f.thread_id, c.text FROM facts f JOIN chunks c ON c.id=f.chunk_id WHERE f.id=?",
                                  (claim["fact_id"],)).fetchone()
            if not source or claim["source_id"] != f"t{source['thread_id']}" or claim["claim_key"] != claim_key:
                violations.append(f"{rel}: invalid metadata source claim: {item['field']}: {item['value']}")
                continue
            fact = json.loads(source["fact_json"])
            values = fact.get(field) or []
            if field == "years":
                values = grounded_years(values, source["text"])
            if not (item["value"] in values if isinstance(values, list) else item["value"] == values):
                violations.append(f"{rel}: metadata value absent from source claim: {item['field']}: {item['value']}")
    published = set()
    unconfirmed_specs = set()
    unconfirmed = set(map(tuple, model["unconfirmed_values"]))
    for spec in model["specifications"]:
        if "alternatives" not in spec:
            values = safety_values(spec["display"])
            published |= values
            if not any(spec["tag"].startswith(t) for t in SAFE_TAGS):
                unconfirmed_specs |= values
            if (is_safety(spec["display"], "", False, spec["item"])
                    and not any(spec["tag"].startswith(t) for t in SAFE_TAGS) and not values <= unconfirmed):
                violations.append(f"{rel}: unconfirmed model safety value missing from prose marks: {spec['display']}")

    def check_prose(text: str, sids: list[str]) -> None:
        if not text.strip():
            violations.append(f"{rel}: empty model item")
            return
        values = safety_values(text)
        if values & unconfirmed_specs - unconfirmed:
            violations.append(f"{rel}: unconfirmed model safety value repeated without a mark: {text[:100]}")
        loose = values - published
        if loose and (not publish_unverified_safety or not loose <= unconfirmed
                      or not any(unit_grounded(text, "", t) for t in texts(sids))):
            violations.append(f"{rel}: model prose has ungrounded or unmarked safety value: {text[:100]}")

    for items in model["lists"].values():
        for text, sids, _ in items:
            check_prose(text, sids)
    for procedure in model["procedures"]:
        for step in procedure["steps"]:
            check_prose(step, [procedure["sid"]])
    from .export import _flat
    for part in model["parts"]:
        check_prose(" ".join([_flat(part["name"]), *(_flat(note) for note in part["notes"])]), part["sids"])
    return violations


def check_index_links(wiki: Path, gl: list[Generation]) -> list[str]:
    """Every local link in a generated index (wiki/index.md and each section's index.md) must reach a file. The checks
    above read only the pages that exist, so an export that lost a section's pages (2026-11-03) passed without this."""
    violations: list[str] = []
    for index in [wiki / "index.md", *(wiki / g.id / "index.md" for g in gl)]:
        if not index.is_file():
            continue
        lines = index.read_text(encoding="utf-8").splitlines()
        if lines and lines[0] == GENERATED:
            violations += _missing_links(index, lines, wiki)
    return violations


def _missing_links(page: Path, lines: list[str], wiki: Path) -> list[str]:
    out: list[str] = []
    for line in lines:
        for m in _LINK_TARGET.finditer(line):
            target = m["target"].split("#", 1)[0]
            if not target or re.match(r"[a-z][a-z0-9+.-]*:", target, re.I):   # anchor, URL or mailto
                continue
            if not (page.parent / target).is_file():
                out.append(f"{page.relative_to(wiki)}: links to a missing page: {target}")
    return out


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
