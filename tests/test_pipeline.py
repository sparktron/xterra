"""End to end with a fake HTTP site and fake LLMs: crawl -> chunks -> extract -> verify -> merge -> review -> wiki -> qa."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import httpx

from xw import db
from xw.cli import main
from xw.crawl import build_chunks, discover, harvest, is_guide_chunk, is_guide_title, store_thread
from xw.export import GENERATED, SAFETY_NOTE, export_all
from xw.extract import GUIDE_SYSTEM, extract_pending
from xw.fetch import Blocked, Fetcher
from xw.grounding import number_tokens, spec_grounded
from xw.ingest import ingest_file
from xw.llm import LLM
from xw.parse.base import Post
from xw.qa import check_wiki
from xw.review import apply_reviews, export_review
from xw.topics import TopicIndex
from xw.verify import verify_pending


class FakeLLM(LLM):
    """Extraction model: returns a canned payload when the chunk text contains the needle."""

    def __init__(self, cfg, answers):
        super().__init__(cfg, client=httpx.Client())
        self.answers = answers

    def chat_json(self, system, user, schema=None):
        for needle, payload in self.answers:
            if needle in user:
                return payload
        return {"relevant": False, "facts": []}


class FakeVerifier(LLM):
    """Verifier model: everything is 'supported' unless the claim contains one of the `bad` words, or states a number
    the source does not (which is how it catches the planted decoys, like a careful real verifier would).
    `rubber_stamp=True` supports everything, decoys included."""

    def __init__(self, cfg, bad=(), partial=(), rubber_stamp=False):
        super().__init__(cfg, client=httpx.Client())
        self.bad, self.partial, self.rubber_stamp = bad, partial, rubber_stamp
        self.calls = 0

    def chat_json(self, system, user, schema=None):
        self.calls += 1
        source, listing = user.split("SOURCE TEXT:\n", 1)[1].split("\n\nCLAIMS:\n", 1)
        claims = re.findall(r"^(\d+)\. (.*)$", listing, re.M)
        out = []
        for i, text in claims:
            if self.rubber_stamp:
                verdict = "supported"
            elif any(b in text for b in self.bad) or (number_tokens(text) and not spec_grounded(text, "", source)):
                verdict = "unsupported"
            else:
                verdict = "partial" if any(p in text for p in self.partial) else "supported"
            out.append({"id": int(i), "verdict": verdict})
        return {"verdicts": out}


def arm_fact(**over):
    fact = {
        "category": "repair", "topic": "Control arms and bushings", "title": "Replace front lower control arms",
        "summary": "Both front lower arms can be swapped in a driveway with basic hand tools.",
        "years": [2008, 2010], "trims": ["Off-Road", "SE"], "difficulty": 3, "est_time": "3 hours",
        "steps": ["Support the truck securely on stands", "Separate the lower ball joint with a fork", "Remove the pivot bolts and drop the arm"],
        "tools": ["21mm socket", "pickle fork"],
        "parts": [{"name": "Lower control arm", "part_number": "54500-EA000", "evidence": "New arm part number 54500-EA000"}],
        "specs": [{"item": "Inner pivot bolt torque", "value": "83", "unit": "ft-lb", "safety_critical": True,
                   "evidence": "Torque the inner pivot bolts to 83 ft-lb"}],
        "tips": ["Final-tighten the pivot bolts with the truck's weight on the suspension"],
        "diagram_links": ["https://example.invalid/diagrams/front-susp.png"],
    }
    fact.update(over)
    return fact


def spec(value, evidence, item="Inner pivot bolt torque"):
    return {"item": item, "value": value, "unit": "ft-lb", "safety_critical": True, "evidence": evidence}


def site_handler(req):
    path = req.url.path
    fixtures = Path(__file__).parent / "fixtures"
    if path == "/robots.txt":
        return httpx.Response(200, text="User-agent: *\nAllow: /\n")
    if path == "/forums/":
        return httpx.Response(200, text=(fixtures / "xenforo_forum.html").read_text())
    if path.startswith("/forums/diy-how-to.12/page-2") or path.startswith("/forums/for-sale"):
        return httpx.Response(200, text="<html><body>" + "x" * 300 + "</body></html>")
    if path.startswith("/forums/diy"):
        return httpx.Response(200, text=(fixtures / "xenforo_forum.html").read_text())
    if path == "/threads/how-to-replace-lower-control-arms.202/":
        return httpx.Response(200, text=(fixtures / "xenforo_thread.html").read_text())
    if path.startswith("/threads/"):
        return httpx.Response(200, text="<html><body><h1 class='p-title-value'>x</h1></body></html>")
    return httpx.Response(404)


def setup_site(cfg, conn):
    conn.execute("UPDATE sources SET config_json=?, base_url='https://forum.example.invalid' WHERE id='thenewx'",
                 (json.dumps({"seeds": ["https://forum.example.invalid/forums/"]}),))
    conn.commit()
    client = httpx.Client(transport=httpx.MockTransport(site_handler), follow_redirects=False)
    return Fetcher(cfg, conn, client=client, sleep=lambda s: None), conn.execute("SELECT * FROM sources WHERE id='thenewx'").fetchone()


def note(tmp_path, name, text, url, author):
    f = tmp_path / f"{name}.txt"
    f.write_text(text)
    return f, url, author


def add_notes(cfg, conn, tmp_path, notes):
    for name, text, author in notes:
        f = tmp_path / f"{name}.txt"
        f.write_text(text)
        ingest_file(cfg, conn, f, url=f"https://{name}.invalid/1", title=name, author=author)


def extract_and_verify(cfg, conn, answers, verifier=None):
    topics = TopicIndex(cfg.topics)
    extract_pending(cfg, conn, FakeLLM(cfg, answers), topics, log=lambda m: None)
    verify_pending(cfg, conn, verifier or FakeVerifier(cfg), log=lambda m: None)
    return topics


def export(cfg, conn):
    return export_all(cfg, conn, TopicIndex(cfg.topics))


def gen2(cfg):
    """The second-generation section: the test sources (`manual`, `thenewx`) are second-gen."""
    return cfg.wiki_dir / "second-gen"


def page_text(cfg, cat="repair", slug="control-arms-bushings"):
    return (gen2(cfg) / cat / f"{slug}.md").read_text()


def fact_id(conn):
    return conn.execute("SELECT id FROM facts ORDER BY id LIMIT 1").fetchone()[0]


def strict(cfg):
    """The fail-closed configuration (both off): partial verdicts and unconfirmed safety values are withheld."""
    cfg.verify.as_dict().update(publish_partial=False, publish_unverified_safety=False)


def claude_verdicts(cfg, conn, verdicts, by="claude"):
    path = cfg.data_dir / "review" / "manual.verdicts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"verdicts": verdicts}))
    return apply_reviews(cfg, conn, [path], by=by)


# ------------------------------------------------------------------------------------------------
def test_discover_prioritises_and_filters(cfg, conn):
    fetcher, src = setup_site(cfg, conn)
    discover(cfg, conn, fetcher, src, log=lambda m: None)
    rows = {r["title"]: r for r in conn.execute("SELECT * FROM threads")}
    assert rows["READ FIRST: Engine code list"]["kind"] == "pinned" and rows["READ FIRST: Engine code list"]["priority"] == 0
    assert rows["How to replace lower control arms"]["kind"] == "howto"
    assert "WTS roof rack $200" not in rows
    assert not any("for-sale" in r["url"] for r in conn.execute("SELECT url FROM threads"))
    assert conn.execute("SELECT title FROM threads ORDER BY priority, views DESC").fetchone()["title"] == "READ FIRST: Engine code list"


def test_single_source_safety_value_is_withheld_until_reviewed(cfg, conn):
    strict(cfg)   # the default publishes it marked instead: test_an_unconfirmed_safety_value_publishes_marked_and_is_rechecked
    fetcher, src = setup_site(cfg, conn)
    discover(cfg, conn, fetcher, src, log=lambda m: None)
    harvest(cfg, conn, fetcher, src, log=lambda m: None)
    t = conn.execute("SELECT * FROM threads WHERE title LIKE 'How to replace%'").fetchone()
    assert t["status"] == "fetched" and t["author"] == "trail_dave"
    chunk = conn.execute("SELECT text FROM chunks WHERE thread_id=?", (t["id"],)).fetchone()["text"]
    assert "bump" not in chunk and "83 ft-lb" in chunk

    extract_and_verify(cfg, conn, [("lower control arms", {"relevant": True, "facts": [arm_fact(
        specs=[spec("83", "Torque the inner pivot bolts to 83 ft-lb"),
               spec("120", "Torque the ball joint nut to 120 ft-lb", item="Ball joint nut torque")],      # invented
        parts=[{"name": "Lower control arm", "part_number": "54500-EA000", "evidence": "New arm part number 54500-EA000"},
               {"name": "Made up", "part_number": "11111-ZZ999", "evidence": "part number 11111-ZZ999"}],
    )]})])
    result = export(cfg, conn)
    assert result["pages"] == 1 and result["pending"] == 1

    page = page_text(cfg)
    assert "54500-EA000" in page and "Remove the pivot bolts" in page and "Final-tighten" in page   # verified prose + part published
    assert "83 ft-lb" not in page and "120" not in page and "11111-ZZ999" not in page              # nothing unverified in the body
    assert "https://example.invalid/diagrams/front-susp.png" in page
    assert "withheld until verified" in page
    pv = (gen2(cfg) / "pending_verification.md").read_text()
    assert "Inner pivot bolt torque" in pv and "83 ft-lb" in pv and "only 1 thread" in pv
    oq = (gen2(cfg) / "open_questions.md").read_text()
    assert "11111-ZZ999" in oq and "120 ft-lb" in oq and "not found in source" in oq
    assert check_wiki(cfg, conn) == []

    # Claude approves the value against the excerpt -> it is published, and tagged as reviewed
    fid = fact_id(conn)
    stats = claude_verdicts(cfg, conn, [{"id": f"f{fid}:spec:0", "verdict": "approve", "note": "excerpt states 83 ft-lb"}])
    assert stats["applied"] == 1
    export(cfg, conn)
    page = page_text(cfg)
    assert "**Inner pivot bolt torque**: 83 ft-lb" in page and "(Claude-reviewed)" in page
    assert "pending_safety_values: 0" in page
    assert check_wiki(cfg, conn) == []

    # a human rejection overrides Claude's approval
    claude_verdicts(cfg, conn, [{"id": f"f{fid}:spec:0", "verdict": "reject"}], by="human")
    export(cfg, conn)
    assert "83 ft-lb" not in page_text(cfg)


def test_fails_closed_when_verifier_has_not_run(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("a", "Lower control arm job on a 2008. Torque the inner pivot bolts to 83 ft-lb on the lower arm. " * 6, "alice")])
    topics = TopicIndex(cfg.topics)
    extract_pending(cfg, conn, FakeLLM(cfg, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[])]})]), topics, log=lambda m: None)
    export(cfg, conn)
    page = page_text(cfg)
    assert "_No verified summary yet._" in page and "## Procedure" not in page and "Final-tighten" not in page
    assert "local verifier: not run" in (gen2(cfg) / "open_questions.md").read_text()

    cfg.verify.as_dict()["require_local_pass"] = False        # explicit opt-out publishes prose again
    export(cfg, conn)
    assert "## Procedure" in page_text(cfg)


def test_verifier_disagreement_withholds_claims_and_whole_procedures(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("a", "Lower control arm job on a 2008. Torque the inner pivot bolts to 83 ft-lb on the lower arm. " * 6, "alice")])
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[])]})],
                       verifier=FakeVerifier(cfg, bad=("lower ball joint",), partial=("weight on the suspension",)))
    export(cfg, conn)
    page, oq = page_text(cfg), (gen2(cfg) / "open_questions.md").read_text()
    assert "## Procedure" not in page and "Remove the pivot bolts" not in page   # one unsupported step withholds the procedure
    assert "- [Partial] Final-tighten" in page                                  # 'partial' publishes, marked as needing work
    assert "local verifier: unsupported" in oq and "local verifier: partial" not in oq
    assert "pickle fork" in page                                                # unrelated verified tool still published
    assert "21mm socket" not in page and "number not found in source" in oq     # "21" is not in this source


def test_agreeing_threads_are_consensus_and_disputes_are_withheld(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [
        ("a", "Write-up a on a 2008 lower arm: torque the inner pivot bolt to 83 ft-lb on the lower arm. " * 6, "alice"),
        ("b", "Write-up b on a 2009 lower arm: torque the inner pivot bolt to 83 ft-lb on the lower arm. " * 6, "bob"),
        ("c", "Write-up c on a 2010 lower arm: the inner pivot bolt torque I used was 90 ft-lb on the lower arm. " * 6, "carol"),
    ])
    answers = [("Write-up a", {"relevant": True, "facts": [arm_fact(specs=[spec("83", "torque the inner pivot bolt to 83 ft-lb")], parts=[], diagram_links=[])]}),
               ("Write-up b", {"relevant": True, "facts": [arm_fact(specs=[spec("83", "torque the inner pivot bolt to 83 ft-lb")], parts=[], diagram_links=[])]}),
               ("Write-up c", {"relevant": True, "facts": [arm_fact(specs=[spec("90", "inner pivot bolt torque I used was 90 ft-lb")], parts=[], diagram_links=[])]})]
    extract_and_verify(cfg, conn, answers)
    export(cfg, conn)
    page = page_text(cfg)
    assert "DISPUTED" not in page and "83 ft-lb" not in page and "90 ft-lb" not in page    # a dispute on a safety value is not published
    assert "sources disagree" in (gen2(cfg) / "pending_verification.md").read_text()
    assert "disputed" in page

    # remove the dissenting thread: two agreeing threads are enough on their own
    conn.execute("DELETE FROM facts WHERE thread_id=(SELECT id FROM threads WHERE title='c')")
    conn.commit()
    export(cfg, conn)
    page = page_text(cfg)
    assert "83 ft-lb [t1, t2] (community-consensus, 2 threads)" in page
    assert check_wiki(cfg, conn) == []


def test_review_queue_prioritises_and_measures_the_verifier(cfg, conn, tmp_path):
    cfg.review.as_dict()["audit_rate"] = 1.0          # audit every locally-supported claim for the test
    add_notes(cfg, conn, tmp_path, [("a", "Lower control arm job on a 2008. Torque the inner pivot bolts to 83 ft-lb on the lower arm. " * 6, "alice")])
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(
        parts=[], diagram_links=[], specs=[spec("83", "Torque the inner pivot bolts to 83 ft-lb")])]})],
        verifier=FakeVerifier(cfg, partial=("lower ball joint",)))
    files = export_review(cfg, conn, TopicIndex(cfg.topics))
    assert len(files) == 1
    batch = json.loads(files[0].read_text())
    items = {i["id"]: i for i in batch["items"]}
    fid = fact_id(conn)
    top = batch["items"][0]
    assert top["id"] == f"f{fid}:spec:0" and top["priority"] == 0 and "corroboration" in top["why_queued"]
    assert "83 ft-lb" in top["excerpt"] and top["source_url"] == "https://a.invalid/1"
    assert items[f"f{fid}:step:1"]["why_queued"] == "local verifier answered partial"
    assert items[f"f{fid}:complete"]["why_queued"] == "local verifier answered partial"    # the list includes that step
    assert any(i["priority"] == 2 for i in batch["items"])                           # audit sample present
    assert "Do not use outside knowledge" in batch["instructions"]
    assert export_review(cfg, conn, TopicIndex(cfg.topics)) == []                  # already-batched items are not re-queued

    stats = claude_verdicts(cfg, conn, [
        {"id": f"f{fid}:spec:0", "verdict": "approve"},
        {"id": f"f{fid}:step:1", "verdict": "approve", "note": "fine"},
        {"id": f"f{fid}:complete", "verdict": "approve", "note": "no step left out"},
        {"id": f"f{fid}:tip:0", "verdict": "reject", "note": "excerpt does not mention it"},   # audited 'supported' claim Claude rejects
        {"id": "f999:spec:0", "verdict": "approve"},                                           # unknown fact
        {"id": f"f{fid}:spec:0", "verdict": "maybe"},                                          # invalid verdict
        {"id": "garbage", "verdict": "approve"},
    ])
    assert stats["applied"] == 4 and stats["invalid"] == 3
    assert stats["audited_rejected"] >= 1 and stats["verifier_false_accept_rate"] > 0
    export(cfg, conn)
    page = page_text(cfg)
    assert "Separate the lower ball joint" in page and "(Claude-reviewed)" in page      # rescued partial step -> procedure published
    assert "Final-tighten" not in page                                                  # reviewer rejected the tip


def test_qa_catches_tampering(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [
        ("a", "Write-up a on a 2008 lower arm: torque the inner pivot bolt to 83 ft-lb on the lower arm. 54500-EA000 is the part. " * 5, "alice"),
        ("b", "Write-up b on a 2009 lower arm: torque the inner pivot bolt to 83 ft-lb on the lower arm. " * 6, "bob"),
    ])
    s = spec("83", "torque the inner pivot bolt to 83 ft-lb")
    extract_and_verify(cfg, conn, [("Write-up a", {"relevant": True, "facts": [arm_fact(specs=[s], diagram_links=[], parts=[{"name": "Arm", "part_number": "54500-EA000", "evidence": "54500-EA000 is the part"}])]}),
                                   ("Write-up b", {"relevant": True, "facts": [arm_fact(specs=[s], parts=[], diagram_links=[])]})])
    export(cfg, conn)
    assert check_wiki(cfg, conn) == []
    path = gen2(cfg) / "repair" / "control-arms-bushings.md"
    good = path.read_text()

    path.write_text(good.replace("83 ft-lb [t1, t2] (community-consensus, 2 threads)", "99 ft-lb [t1, t2] (community-consensus, 2 threads)"))
    assert any("not found in cited thread" in v for v in check_wiki(cfg, conn))
    path.write_text(good.replace("(community-consensus, 2 threads)", "([Unverified] single report)"))
    assert any("without corroboration" in v for v in check_wiki(cfg, conn))
    path.write_text(good.replace("83 ft-lb [t1, t2]", "83 in-lb [t1, t2]"))
    assert any("unit not found" in v for v in check_wiki(cfg, conn))
    path.write_text(good.replace("(54500-EA000)", "(77777-AB123)"))
    assert any("part number not found" in v for v in check_wiki(cfg, conn))
    path.write_text(good.replace("[t1, t2]", "[t1, t9]"))
    assert any("unknown thread" in v for v in check_wiki(cfg, conn))


def test_part_name_in_parentheses_is_not_mistaken_for_a_part_number(cfg, conn, tmp_path):
    # qa.PART_LINE reads a trailing "(...)" as the part number; a numberless part named "Rear Bearing (NSK)" once
    # failed qa for that reason. The exporter now flattens parentheses in names; qa is no looser.
    add_notes(cfg, conn, tmp_path, [
        ("a", "Write-up a on a 2008 lower arm: replace the rear bearing, an NSK one, and the pivot bolt. 54500-EA000 is the arm. " * 5, "alice"),
    ])
    parts = [{"name": "Rear Bearing (NSK)", "part_number": "", "evidence": "replace the rear bearing, an NSK one"},
             {"name": "Arm (left)", "part_number": "54500-EA000", "evidence": "54500-EA000 is the arm"}]
    extract_and_verify(cfg, conn, [("Write-up a", {"relevant": True, "facts": [arm_fact(parts=parts, specs=[], diagram_links=[])]})])
    export(cfg, conn)
    path = gen2(cfg) / "repair" / "control-arms-bushings.md"
    page = path.read_text()
    assert "- Rear Bearing, NSK [t1]" in page and "- Arm, left (54500-EA000) [t1]" in page
    assert check_wiki(cfg, conn) == []
    path.write_text(page.replace("(54500-EA000)", "(77777-AB123)"))
    assert any("part number not found" in v for v in check_wiki(cfg, conn))


def test_a_numberless_part_whose_note_is_in_parentheses_is_not_mistaken_for_a_part_number(cfg, conn, tmp_path):
    # A numberless part rendered "- Wire: (12 AWG or larger) [t1]" failed qa: PART_LINE took "12 AWG or larger" for its
    # part number. The exporter now flattens parentheses in notes as well as names; qa is no looser.
    add_notes(cfg, conn, tmp_path, [
        ("a", "Write-up a on a 2008 lower arm: run new wire, 12 AWG or larger, to the lamp, and fit a shield (any brand). " * 5, "alice"),
    ])
    parts = [{"name": "Wire", "part_number": "", "notes": "(12 AWG or larger)", "evidence": "run new wire, 12 AWG or larger"},
             {"name": "Shield", "part_number": "", "notes": "Any brand (aftermarket)", "evidence": "fit a shield (any brand)"}]
    extract_and_verify(cfg, conn, [("Write-up a", {"relevant": True, "facts": [arm_fact(parts=parts, specs=[], diagram_links=[])]})])
    export(cfg, conn)
    page = (gen2(cfg) / "repair" / "control-arms-bushings.md").read_text()
    assert "- Wire: 12 AWG or larger [t1]" in page and "- Shield: Any brand, aftermarket [t1]" in page
    assert check_wiki(cfg, conn) == []


def test_copied_text_and_unstated_metadata_are_not_published(cfg, conn, tmp_path):
    text = "Loosen the lug nuts, raise the front, and support it on stands. Then continue on this 2008 Xterra X lower arm job. " * 4
    add_notes(cfg, conn, tmp_path, [("a", text, "alice")])
    extract_and_verify(cfg, conn, [("lug nuts", {"relevant": True, "facts": [arm_fact(
        steps=["Loosen the lug nuts, raise the front, and support it on stands.", "Drop the arm"],
        years=[2008, 2012], trims=["X", "SE", "Off-Road"], parts=[], specs=[], diagram_links=[])]})])
    export(cfg, conn)
    page = page_text(cfg)
    assert "Loosen the lug nuts, raise the front" not in page and "## Procedure" not in page    # verbatim -> withheld
    assert "verbatim overlap" in (gen2(cfg) / "open_questions.md").read_text()
    assert "- 2008" in page and "2012" not in page                                             # year not in source text is dropped
    assert "- X" in page and "SE" not in page.split("---")[1] and "Off-Road" not in page.split("---")[1]


def test_dtc_table_and_interchange(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("codes", "P0340 camshaft position sensor circuit on the Frontier and Xterra. Usually the sensor or its connector; check the connector first. " * 6, "carol")])
    answers = [("P0340", {"relevant": True, "facts": [{
        "category": "diagnostics", "topic": "Engine trouble codes (VQ40DE)", "title": "P0340", "summary": "Cam sensor fault.",
        "years": [], "shared_platform": ["Frontier", "Titan"],
        "dtcs": [{"code": "P0340", "description": "Camshaft position sensor circuit", "causes": ["Sensor", "Connector"], "tests": ["Check the connector"], "fix": "Replace the sensor"},
                 {"code": "P0999", "description": "invented"}]}]})]
    extract_and_verify(cfg, conn, answers)
    export(cfg, conn)
    rows = list(csv.reader((gen2(cfg) / "dtc_table.csv").open()))
    assert [r[0] for r in rows[1:]] == ["P0340"]                  # ungrounded P0999 excluded
    ic = (gen2(cfg) / "interchange.md").read_text()
    assert "Frontier" in ic and "| Titan" not in ic and "Frontier, Titan" not in ic                 # 'Titan' is not in the source text, so it is dropped


def test_out_of_scope_years_are_dropped(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("old", "My 1998 Pathfinder needs a new alternator belt and the procedure is simple enough. " * 6, "dan")])
    extract_and_verify(cfg, conn, [("1998", {"relevant": True, "facts": [arm_fact(years=[1998], parts=[], specs=[], diagram_links=[])]})])
    assert conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 0


GEN1_TEXT = "Lower control arm job on my 2001 Xterra with plenty of detail on the arm, the bolts and the ball joint here. " * 6


def test_a_fact_publishes_only_in_the_generation_of_its_stated_years(cfg, conn, tmp_path):
    # the user (2026-10-20): first and second generation "are nothing alike"; each has its own separate section
    pic = "https://img.invalid/albums/t999/arm.jpg"   # a thread-id-like path in a URL is not a citation (qa once read it as t999)
    add_notes(cfg, conn, tmp_path, [("gen1", GEN1_TEXT + f" Diagram: {pic}", "dan")])   # `manual` is second-gen; the year decides
    extract_and_verify(cfg, conn, [("2001", {"relevant": True, "facts": [arm_fact(years=[2001], parts=[], specs=[], diagram_links=[pic])]})])
    export(cfg, conn)
    page = (cfg.wiki_dir / "first-gen" / "repair" / "control-arms-bushings.md").read_text()
    assert "generation: first-gen" in page and "Remove the pivot bolts" in page
    assert not (gen2(cfg) / "repair" / "control-arms-bushings.md").exists()
    assert "](../second-gen/index.md)" in (cfg.wiki_dir / "first-gen" / "index.md").read_text()
    assert "](first-gen/index.md)" in (cfg.wiki_dir / "index.md").read_text()
    assert check_wiki(cfg, conn) == []


def test_a_fact_without_years_takes_its_sources_generation(cfg, conn, tmp_path):
    f = tmp_path / "saved.txt"
    f.write_text(GEN1_TEXT.replace("2001 ", ""))
    ingest_file(cfg, conn, f, url="https://gen1.invalid/1", title="arms", author="dan", source="manual-gen1")
    extract_and_verify(cfg, conn, [("Lower control arm", {"relevant": True, "facts": [arm_fact(years=[], parts=[], specs=[], diagram_links=[])]})])
    export(cfg, conn)
    assert (cfg.wiki_dir / "first-gen" / "repair" / "control-arms-bushings.md").exists()
    assert not (gen2(cfg) / "repair" / "control-arms-bushings.md").exists()


def test_a_fact_whose_years_span_both_generations_publishes_in_neither(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("both", GEN1_TEXT.replace("2001", "2003 and 2008"), "dan")])
    extract_and_verify(cfg, conn, [("2003", {"relevant": True, "facts": [arm_fact(years=[2003, 2008], parts=[], specs=[], diagram_links=[])]})])
    export(cfg, conn)
    assert not list(cfg.wiki_dir.glob("*-gen/repair/control-arms-bushings.md"))
    assert "its model years span" in (cfg.wiki_dir / "open_questions.md").read_text()


def test_a_fact_whose_title_names_the_other_generation_publishes_in_neither(cfg, conn, tmp_path):
    # live: a first-gen note in a second-gen subforum came out as "First-gen Xterra Corbeau bracket fitment notes"
    add_notes(cfg, conn, tmp_path, [("gen1", GEN1_TEXT.replace("2001 ", ""), "dan")])
    extract_and_verify(cfg, conn, [("Lower control arm", {"relevant": True, "facts": [arm_fact(
        years=[], title="First-gen lower arm notes", parts=[], specs=[], diagram_links=[])]})])
    export(cfg, conn)
    assert not list(cfg.wiki_dir.glob("*-gen/repair/control-arms-bushings.md"))
    assert "its title names the First generation" in (cfg.wiki_dir / "open_questions.md").read_text()
    assert check_wiki(cfg, conn) == []


def test_a_claim_naming_the_other_generation_is_withheld_and_qa_refuses_it(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("a", "Lower control arm job on a 2008. Unlike a first gen truck, tighten the pivot bolts with "
                                          "the weight on the wheels. Separate the ball joint with a fork. " * 5, "alice")])
    tip = "Unlike a first gen truck, final-tighten the pivot bolts with the weight on the wheels"
    extract_and_verify(cfg, conn, [("Lower control arm", {"relevant": True, "facts": [arm_fact(
        tips=[tip], parts=[], specs=[], diagram_links=[])]})])
    export(cfg, conn)
    page = page_text(cfg)
    assert "Remove the pivot bolts" in page and "first gen" not in page
    assert "names the First generation" in (gen2(cfg) / "open_questions.md").read_text()
    assert check_wiki(cfg, conn) == []
    path = gen2(cfg) / "repair" / "control-arms-bushings.md"
    path.write_text(page.replace("## Procedure", "## Procedure\n\nSame as the 1st gen. [t1]"))
    assert any("names the First generation" in v for v in check_wiki(cfg, conn))
    path.write_text(page)
    moved = cfg.wiki_dir / "first-gen" / "repair" / "control-arms-bushings.md"   # a page in the wrong section
    moved.parent.mkdir(parents=True, exist_ok=True)
    moved.write_text(page)
    v = check_wiki(cfg, conn)
    assert any("front matter does not say generation: first-gen" in x for x in v) and any("has no fact in the First" in x for x in v)


def test_llm_failure_stops_cleanly_and_chunks_stay_pending(cfg, conn, tmp_path):
    from xw.llm import LLMError

    class Down(LLM):
        def __init__(self, cfg):
            super().__init__(cfg, client=httpx.Client())

        def chat_json(self, *a, **k):
            raise LLMError("server down")

    add_notes(cfg, conn, tmp_path, [(f"n{i}", f"Note {i}: enough text about the xterra to become a chunk. " * 12, "") for i in range(8)])
    extract_pending(cfg, conn, Down(cfg), TopicIndex(cfg.topics), log=lambda m: None)
    assert conn.execute("SELECT COUNT(*) FROM chunks WHERE status='pending'").fetchone()[0] >= 3


def test_blocked_source_does_not_stop_the_run(cfg, conn):
    conn.execute("UPDATE sources SET config_json=? WHERE id='thenewx'", (json.dumps({"seeds": ["https://wall.invalid/forums/"]}),))
    conn.commit()

    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(402, text="Payment Required")

    fetcher = Fetcher(cfg, conn, client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None)
    src = conn.execute("SELECT * FROM sources WHERE id='thenewx'").fetchone()
    try:
        discover(cfg, conn, fetcher, src, log=lambda m: None)
    except Blocked as exc:
        db.set_source_status(conn, "thenewx", "blocked", exc.reason)
    row = conn.execute("SELECT status, reason FROM sources WHERE id='thenewx'").fetchone()
    assert row["status"] == "blocked" and "402" in row["reason"]
    export(cfg, conn)
    assert "thenewx" in (gen2(cfg) / "open_questions.md").read_text()


def test_build_chunks_splits_and_skips_noise():
    posts = [Post("a", "2014-01-01", "First post. " + "word " * 300), Post("b", "", "thanks"), Post("c", "", "long reply " * 200)]
    chunks = build_chunks("T", posts, max_chars=1500, min_chars=100, min_post_chars=60)
    assert len(chunks) >= 2 and all(c.startswith("THREAD: T") for c in chunks)
    assert not any("thanks" in c for c in chunks)
    assert "(continued)" in chunks[1]


def test_guide_thread_chunks_the_authors_writeup_alone():
    posts = [Post("op", "", "Pull the kick panel and remove the strip. " * 8), Post("op", "", "Then route the harness. " * 6),
             Post("b", "", "Great write-up, which socket did you use? " * 3), Post("op", "", "A 10mm socket for the bracket. " * 3)]
    chunks = build_chunks("How-to: 7-pin harness", posts, max_chars=14000, min_chars=100, min_post_chars=60, guide_first=True)
    assert len(chunks) == 2 and is_guide_chunk(chunks[0]) and not is_guide_chunk(chunks[1])
    assert "route the harness" in chunks[0] and "which socket" not in chunks[0]
    assert "10mm" in chunks[1]                      # the author's later answer is part of the discussion
    assert len(build_chunks("How-to: 7-pin harness", posts, 14000, 100, 60)) == 1   # without guide_first: unchanged
    # a one-line opener is not a write-up: the thread stays one discussion chunk
    opener = [Post("op", "", "Any write-ups on this?"), Post("b", "", "Here is how I did it. " * 10)]
    assert [is_guide_chunk(c) for c in build_chunks("How-to: x", opener, 14000, 100, 60, guide_first=True)] == [False]
    assert is_guide_title("How-to: Install 7-Pin Wiring Harness") and is_guide_title("DIY: Drop in Cargo Roof Rack")
    assert is_guide_title("Airbag Reset Procedure") and not is_guide_title("How to remove the rear seat?")
    assert not is_guide_title("*** PLEASE READ *** ~ Front Diff Failures")


def test_guide_steps_publish_as_one_procedure_with_a_pointer_to_the_photos(cfg, conn, tmp_path):
    """Live, the 9B model returned a write-up as many two-step facts. The guide's own chunk gets one steps-only call;
    its steps replace the fragments and still pass grounding and the verifier like any other step."""
    url = "https://forum.example.invalid/threads/hatch-struts.9/"
    conn.execute("INSERT INTO threads(source_id, url, title, kind, priority) VALUES('manual', ?, 'How-to: Hatch struts', 'manual', 1)", (url,))
    tid = conn.execute("SELECT id FROM threads WHERE url=?", (url,)).fetchone()["id"]
    guide = ("Open the hatch all the way and have a helper hold it, or prop it with a length of wood, so it cannot drop "
             "on you while a strut is off.\nPop the trim cover off with a plastic panel tool. [image: https://forum.example.invalid/a.jpg]\n"
             "Lever the old strut clips up with a flat screwdriver.\nPress the new strut onto both ball studs.\n"
             "Close the hatch, open it again and make sure it stays up on its own.")
    reply = "Nice job, mine took ten minutes start to finish with a borrowed panel tool."
    store_thread(cfg, conn, tid, "How-to: Hatch struts", [Post("op", "", guide), Post("b", "", reply)], 1)
    assert [is_guide_chunk(r["text"]) for r in conn.execute("SELECT text FROM chunks WHERE thread_id=? ORDER BY idx", (tid,))] == [True, False]
    frag = lambda steps: {"category": "repair", "topic": "Rear hatch strut replacement", "title": "Replace hatch struts", "steps": steps}  # noqa: E731
    answers = [("Pop the trim", {"relevant": True, "facts": [frag(["Remove the trim cover", "Release the strut clips"]),
                                                             frag(["Fit the new strut on the studs", "Test the hatch"])]})]
    steps = ["Have a helper hold the open hatch, or prop it with wood", "Take off the trim cover using a plastic panel tool",
             "Pry up the clips on the old strut with a flat screwdriver",
             "Push the new strut onto both ball studs", "Shut and reopen the hatch and check that it holds itself up"]

    class GuideLLM(FakeLLM):
        def chat_json(self, system, user, schema=None):
            return {"steps": steps} if system == GUIDE_SYSTEM else super().chat_json(system, user, schema)

    topics = TopicIndex(cfg.topics)
    extract_pending(cfg, conn, GuideLLM(cfg, answers), topics, log=lambda m: None)
    facts = [json.loads(r["fact_json"]) for r in conn.execute("SELECT fact_json FROM facts WHERE thread_id=?", (tid,))]
    assert [f["steps"] for f in facts if f["steps"]] == [steps]
    verify_pending(cfg, conn, FakeVerifier(cfg), log=lambda m: None)
    export(cfg, conn)
    page = next(p for p in gen2(cfg).glob("*/*.md") if "Push the new strut" in p.read_text())
    text = page.read_text()
    assert "5. Shut and reopen the hatch" in text and f"Photos of this job are in the source: <{url}>" in text
    assert check_wiki(cfg, conn) == []


def test_cli_init_status_export_qa(root, capsys):
    assert main(["--root", str(root), "init"]) == 0
    assert main(["--root", str(root), "status"]) == 0
    out = capsys.readouterr().out
    assert "thenewx" in out and "manual" in out
    assert main(["--root", str(root), "export"]) == 0
    assert main(["--root", str(root), "qa"]) == 0
    assert main(["--root", str(root), "review-export"]) == 0
    assert (root / "wiki" / "index.md").exists()
    for gen in ("first-gen", "second-gen"):   # one complete section per generation
        assert (root / "wiki" / gen / "index.md").exists() and (root / "wiki" / gen / "pending_verification.md").exists()


def test_ingest_html_via_cli(root, fixtures):
    main(["--root", str(root), "init"])
    assert main(["--root", str(root), "ingest", str(fixtures / "xenforo_thread.html"), "--url", "https://forum.example.invalid/threads/x.202/"]) == 0
    from xw.config import Config
    conn = db.connect(Config.load(root).db_path)
    t = conn.execute("SELECT * FROM threads WHERE source_id='manual'").fetchone()
    assert t["title"] == "How to replace lower control arms" and t["status"] == "fetched"


# ---- regressions from the Codex review of PR #1 ----------------------------------------------
def test_verifier_sees_part_notes_and_dtc_advice(cfg, conn, tmp_path):
    from xw.schemas import Fact
    from xw.verify import claims_for_fact
    fact = Fact.model_validate(arm_fact(parts=[{"name": "Arm", "part_number": "54500-EA000", "notes": "fits 2005 only", "evidence": "x"}],
                                        dtcs=[{"code": "P0340", "description": "Cam sensor", "causes": ["Sensor"], "tests": ["Check connector"], "fix": "Replace sensor"}]))
    claims = dict(claims_for_fact(fact))
    assert "fits 2005 only" in claims["part:0"]
    assert all(w in claims["dtc:0"] for w in ("Sensor", "Check connector", "Replace sensor"))


def test_unverified_dtc_advice_is_not_published(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("codes", "P0340 camshaft position sensor circuit on the Xterra. Usually the sensor or its connector; check the connector first. " * 6, "carol")])
    fact = {"category": "diagnostics", "topic": "Engine trouble codes (VQ40DE)", "title": "P0340", "summary": "Cam sensor fault.",
            "dtcs": [{"code": "P0340", "description": "Camshaft position sensor circuit", "causes": ["Sensor"], "fix": "Replace the ECU"}]}
    extract_and_verify(cfg, conn, [("P0340", {"relevant": True, "facts": [fact]})], verifier=FakeVerifier(cfg, bad=("Replace the ECU",)))
    export(cfg, conn)
    assert "ECU" not in (gen2(cfg) / "dtc_table.csv").read_text()


def test_non_torque_safety_values_are_classified_deterministically():
    from xw.export import is_safety
    assert is_safety("4.5", "qt", False, "Engine oil capacity") and is_safety("35", "psi", False, "Tire pressure")
    assert is_safety("12", "", False, "Axle nut torque") and not is_safety("2", "inches", False, "Lift height")


def test_oversized_paragraph_is_split_not_truncated():
    text = "".join(f"word{i} " for i in range(1200))  # one ~8k char paragraph
    chunks = build_chunks("t", [Post(author="a", posted="", text=text)], 2000, 100, 10)
    joined = " ".join(chunks)
    assert len(chunks) > 1 and "word0 " in joined and "word1199" in joined


def test_confidence_ignores_rows_whose_claims_were_all_withheld(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [
        ("a", "Lower control arm job on a 2008. Final-tighten the pivot bolts with the truck's weight on the suspension. " * 6, "alice"),
        ("b", "Lower control arm job on a 2009. Final-tighten the pivot bolts with the truck's weight on the suspension. " * 6, "bob")])
    answers = [("2008", {"relevant": True, "facts": [arm_fact(parts=[], specs=[], diagram_links=[])]}),
               ("2009", {"relevant": True, "facts": [arm_fact(parts=[], specs=[], diagram_links=[])]})]
    extract_and_verify(cfg, conn, answers, verifier=FakeVerifier(cfg, bad=("Support", "Separate", "Remove", "weight", "socket", "pickle", "swapped")))
    export(cfg, conn)
    assert "confidence: community-consensus" not in page_text(cfg)


def test_terminal_chunk_failure_marks_thread_error(cfg, conn, tmp_path):
    from xw.llm import LLMError

    class Boom(FakeLLM):
        def chat_json(self, *a, **k):
            raise LLMError("boom")

    add_notes(cfg, conn, tmp_path, [("a", "Lower control arm job on a 2008 with plenty of detail here. " * 8, "alice")])
    for _ in range(3):
        extract_pending(cfg, conn, Boom(cfg, []), TopicIndex(cfg.topics), log=lambda m: None)
    assert conn.execute("SELECT status FROM chunks").fetchone()[0] == "error"
    assert conn.execute("SELECT status FROM threads").fetchone()[0] == "error"
    export(cfg, conn)
    assert "extraction failed" in (gen2(cfg) / "open_questions.md").read_text()


# ---- regressions from the approach review (2026-10-07) -----------------------------------------
NOTE_A = "Lower control arm job on a 2008. Torque the inner pivot bolts to 83 ft-lb on the lower arm. " * 6


def test_verifier_that_accepts_decoys_is_discarded(cfg, conn, tmp_path):
    from xw.verify import DECOY_FAILED, decoy_stats
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice")])
    stamp = FakeVerifier(cfg, rubber_stamp=True)
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[])]})], verifier=stamp)
    assert stamp.calls == 2                                                   # one retry with fresh decoys, then give up
    local = {v["verdict"] for v in conn.execute("SELECT verdict FROM verdicts WHERE by='local'")}
    assert local == {DECOY_FAILED}
    d = decoy_stats(conn)
    assert d["accepted"] == d["decoys"] >= 2 and d["discarded_calls"] == 2
    export(cfg, conn)
    page = page_text(cfg)
    assert "_No verified summary yet._" in page and "## Procedure" not in page and "pickle fork" not in page
    assert "local verifier: decoy_failed" in (gen2(cfg) / "open_questions.md").read_text()
    batch = json.loads(export_review(cfg, conn, TopicIndex(cfg.topics))[0].read_text())
    assert any("planted false claim" in i["why_queued"] for i in batch["items"])   # a stronger reviewer can rescue them


def test_decoys_are_false_by_construction_and_honest_verifier_passes():
    import random
    from xw.verify import make_decoy
    src = "Torque the inner pivot bolts to 83 ft-lb. The 2008 needs part 54500-EA000."
    rng = random.Random("t")
    for claim in ("Inner pivot bolt torque: 83 ft-lb", "Part: Lower control arm 54500-EA000", "Support the truck on stands"):
        for _ in range(20):
            decoy = make_decoy(claim, src, rng)
            assert decoy != claim and not spec_grounded(decoy, "", src)       # it states a number the source never does


def test_verify_only_runs_missing_claims_and_redo_reruns(cfg, conn, tmp_path):
    from xw.verify import decoy_stats
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice")])
    v = FakeVerifier(cfg)
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[])]})], verifier=v)
    assert decoy_stats(conn)["accepted"] == 0 and v.calls == 1
    conn.execute("DELETE FROM verdicts WHERE claim_key='complete'")        # e.g. a claim type added after the fact was verified
    conn.commit()
    assert verify_pending(cfg, conn, v, log=lambda m: None) == 1 and v.calls == 2
    assert conn.execute("SELECT verdict FROM verdicts WHERE claim_key='complete'").fetchone()[0] == "supported"
    assert verify_pending(cfg, conn, v, log=lambda m: None) == 0           # nothing missing
    assert verify_pending(cfg, conn, v, redo=True, log=lambda m: None) == 1


def test_same_author_in_two_threads_is_not_consensus(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [
        ("a", "Write-up a on a 2008 lower arm: torque the inner pivot bolt to 83 ft-lb on the lower arm. " * 6, "alice"),
        ("b", "Write-up b on a 2009 lower arm: torque the inner pivot bolt to 83 ft-lb on the lower arm. " * 6, "Alice"),
    ])
    s = spec("83", "torque the inner pivot bolt to 83 ft-lb")
    extract_and_verify(cfg, conn, [(w, {"relevant": True, "facts": [arm_fact(specs=[s], parts=[], diagram_links=[])]}) for w in ("Write-up a", "Write-up b")])
    export(cfg, conn)
    page = page_text(cfg)
    assert "83 ft-lb [t1, t2] ([Unverified] not independently corroborated)" in page   # published, but not as confirmed
    assert SAFETY_NOTE in page and "confidence: community-consensus" not in page
    strict(cfg)
    export(cfg, conn)
    assert "83 ft-lb" not in page_text(cfg)
    assert "1 distinct known author" in (gen2(cfg) / "pending_verification.md").read_text()


def test_review_queue_counts_corroboration_like_the_exporter(cfg, conn, tmp_path):
    """Thread b states the same value but its verifier pass rejected it, so the exporter has one supporting thread
    and publishes the value only marked unconfirmed. The queue must offer it for review at priority 0, not skip it as
    already corroborated."""
    class RejectsB(FakeVerifier):
        def chat_json(self, system, user, schema=None):
            out = super().chat_json(system, user, schema)
            if "Write-up b" in user:
                out = {"verdicts": [{"id": v["id"], "verdict": "unsupported"} for v in out["verdicts"]]}
            return out

    add_notes(cfg, conn, tmp_path, [
        ("a", "Write-up a on a 2008 lower arm: torque the inner pivot bolt to 83 ft-lb on the lower arm. " * 6, "alice"),
        ("b", "Write-up b on a 2009 lower arm: torque the inner pivot bolt to 83 ft-lb on the lower arm. " * 6, "bob"),
    ])
    s = spec("83", "torque the inner pivot bolt to 83 ft-lb")
    extract_and_verify(cfg, conn, [(w, {"relevant": True, "facts": [arm_fact(specs=[s], parts=[], diagram_links=[])]}) for w in ("Write-up a", "Write-up b")],
                       verifier=RejectsB(cfg))
    export(cfg, conn)
    assert "needs 2 independent reports" in (gen2(cfg) / "pending_verification.md").read_text()
    batch = json.loads(export_review(cfg, conn, TopicIndex(cfg.topics))[0].read_text())
    top = batch["items"][0]
    assert top["id"] == f"f{fact_id(conn)}:spec:0" and top["priority"] == 0 and "published marked" in top["why_queued"]


def test_safety_values_in_prose_need_a_published_spec(cfg, conn, tmp_path):
    strict(cfg)   # with the defaults the single-source spec publishes marked: see the test after this one
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A + "Refill the diff with 2.75 qt of gear oil. " * 3, "alice")])
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(
        steps=["Support the truck on stands", "Torque the pivot bolts to 83 ft-lb with the arm loaded"],
        tips=["Top off the diff with 2.75 qt afterwards"], parts=[], diagram_links=[],
        specs=[spec("83", "Torque the inner pivot bolts to 83 ft-lb")])]})])
    export(cfg, conn)
    page, oq = page_text(cfg), (gen2(cfg) / "open_questions.md").read_text()
    assert "## Procedure" not in page and "2.75" not in page and "83 ft-lb" not in page   # spec is single-source -> pending
    assert "not published as a corroborated spec: 83 ft-lb" in oq and "2.75 qt" in oq
    assert check_wiki(cfg, conn) == []

    fid = fact_id(conn)
    claude_verdicts(cfg, conn, [{"id": f"f{fid}:spec:0", "verdict": "approve"}])     # the spec publishes -> the step may cite it
    export(cfg, conn)
    page = page_text(cfg)
    assert "Torque the pivot bolts to 83 ft-lb" in page and "2.75" not in page
    assert check_wiki(cfg, conn) == []

    path = gen2(cfg) / "repair" / "control-arms-bushings.md"
    path.write_text(page.replace("## Tools", "## Tips & gotchas\n\n- Fill it with 6 qt first [t1]\n\n## Tools"))
    assert any("outside the specifications: 6 qt" in v for v in check_wiki(cfg, conn))
    # a spec-shaped line outside Specifications must not count as a published spec (and exempt itself)
    path.write_text(page.replace("## Tools", "## Tips & gotchas\n\n- **Torque**: 99 ft-lb [t1] (community-consensus, 2 threads)\n\n## Tools"))
    assert any("outside the specifications: 99 ft-lb" in v for v in check_wiki(cfg, conn))


def test_an_unconfirmed_safety_value_publishes_marked_and_is_rechecked(cfg, conn, tmp_path):
    """Decided 2026-10-16: a possibly wrong torque/capacity/pressure value may publish if it is marked as such and checked
    again on later runs. It is tagged [Unverified] under a warning banner, prose repeating it says [Unverified value],
    pending_verification.md lists it, the review queue keeps it at priority 0, and a review removes the marks."""
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A + "Refill the diff with 2.75 qt of gear oil. " * 3, "alice")])
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(
        steps=["Support the truck on stands", "Torque the pivot bolts to 83 ft-lb with the arm loaded"],
        tips=["Top off the diff with 2.75 qt afterwards"], parts=[], diagram_links=[],
        specs=[spec("83", "Torque the inner pivot bolts to 83 ft-lb")])]})])
    export(cfg, conn)
    page = page_text(cfg)
    assert "**Inner pivot bolt torque**: 83 ft-lb [t1] ([Unverified] single report)" in page and SAFETY_NOTE in page
    assert "2. [Unverified value] Torque the pivot bolts to 83 ft-lb with the arm loaded" in page
    assert "- [Unverified value] Top off the diff with 2.75 qt afterwards [t1]" in page   # no spec, but the source says 2.75 qt
    pv = (gen2(cfg) / "pending_verification.md").read_text()
    assert pv.index("Published marked") < pv.index("83 ft-lb")
    assert check_wiki(cfg, conn) == []
    fid = fact_id(conn)
    top = json.loads(export_review(cfg, conn, TopicIndex(cfg.topics))[0].read_text())["items"][0]
    assert top["id"] == f"f{fid}:spec:0" and top["priority"] == 0

    path = gen2(cfg) / "repair" / "control-arms-bushings.md"
    path.write_text(page.replace(SAFETY_NOTE, ""))
    assert any("visible [Unverified]/[Partial] mark under the warning banner" in v for v in check_wiki(cfg, conn))
    path.write_text(page.replace("[Unverified value] ", ""))
    assert any("without [Unverified value]" in v for v in check_wiki(cfg, conn))

    claude_verdicts(cfg, conn, [{"id": f"f{fid}:spec:0", "verdict": "approve"}])
    export(cfg, conn)
    page = page_text(cfg)
    assert "83 ft-lb [t1] (Claude-reviewed)" in page and "2. Torque the pivot bolts to 83 ft-lb with the arm loaded" in page
    assert "- [Unverified value] Top off the diff with 2.75 qt afterwards [t1]" in page and SAFETY_NOTE in page   # still unconfirmed
    assert check_wiki(cfg, conn) == []


def test_partial_procedure_publishes_marked_partial_until_upgraded(cfg, conn, tmp_path):
    # Every step supported, but the verifier only says the list MAY leave something out: better shown (marked) than hidden.
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice")])
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[])]})],
                       verifier=FakeVerifier(cfg, partial=("whole procedure",)))
    export(cfg, conn)
    page = page_text(cfg)
    assert "## Procedure" in page and "[Partial]" in page and "Final-tighten" in page
    assert "completeness (procedure withheld)" not in (gen2(cfg) / "open_questions.md").read_text()
    assert check_wiki(cfg, conn) == []
    # a later verify/review that confirms completeness removes the marker on the next export
    conn.execute("UPDATE verdicts SET verdict='supported' WHERE claim_key='complete'")
    conn.commit()
    export(cfg, conn)
    assert "## Procedure" in page_text(cfg) and "[Partial]" not in page_text(cfg)


def test_unsupported_or_rejected_completeness_still_withholds_the_procedure(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice")])
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[])]})],
                       verifier=FakeVerifier(cfg, bad=("whole procedure",)))
    export(cfg, conn)
    assert "## Procedure" not in page_text(cfg) and "Final-tighten" in page_text(cfg)       # steps supported, list not
    assert "completeness (procedure withheld)" in (gen2(cfg) / "open_questions.md").read_text()
    # a partial local verdict does not survive a reviewer's reject ("a listed step is not in the source")
    conn.execute("UPDATE verdicts SET verdict='partial' WHERE claim_key='complete'")
    conn.execute("INSERT INTO verdicts(fact_id, claim_key, by, verdict, note, created_at) "
                 "SELECT fact_id, 'complete', 'claude', 'reject', '', '' FROM verdicts WHERE claim_key='complete'")
    conn.commit()
    export(cfg, conn)
    assert "## Procedure" not in page_text(cfg)
    # ... but a reviewer's needs_human ("steps are stated, the list may be incomplete") shows it, marked Partial,
    # even over a local `unsupported`; an approval shows it unmarked
    conn.execute("UPDATE verdicts SET verdict='needs_human' WHERE claim_key='complete' AND by='claude'")
    conn.execute("UPDATE verdicts SET verdict='unsupported' WHERE claim_key='complete' AND by='local'")
    conn.commit()
    export(cfg, conn)
    assert "## Procedure" in page_text(cfg) and "[Partial]" in page_text(cfg)
    conn.execute("UPDATE verdicts SET verdict='approve' WHERE claim_key='complete' AND by='claude'")
    conn.commit()
    export(cfg, conn)
    assert "## Procedure" in page_text(cfg) and "[Partial]" not in page_text(cfg)


def test_partial_never_rescues_an_unsupported_step(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice")])
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[])]})],
                       verifier=FakeVerifier(cfg))
    conn.execute("UPDATE verdicts SET verdict='partial' WHERE claim_key='complete'")
    conn.execute("UPDATE verdicts SET verdict='unsupported' WHERE claim_key='step:1'")
    conn.commit()
    export(cfg, conn)
    page = page_text(cfg)
    assert "## Procedure" not in page and "Separate the lower ball joint" not in page      # one bad step still withholds all


def test_applicability_and_interchange_need_their_own_verdict(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("codes", "P0340 camshaft position sensor circuit. I bought my 2008 Xterra from a guy with a Frontier. "
                                              "Usually the sensor or its connector; check the connector first. " * 6, "carol")])
    fact = {"category": "diagnostics", "topic": "Engine trouble codes (VQ40DE)", "title": "P0340", "summary": "Cam sensor fault.",
            "years": [2008], "shared_platform": ["Frontier"],
            "dtcs": [{"code": "P0340", "description": "Camshaft position sensor circuit", "causes": ["Sensor"]}]}
    extract_and_verify(cfg, conn, [("P0340", {"relevant": True, "facts": [fact]})],
                       verifier=FakeVerifier(cfg, bad=("applies to model years", "also applies to the Nissan")))
    export(cfg, conn)
    page = page_text(cfg, "diagnostics", TopicIndex(cfg.topics).resolve("Engine trouble codes (VQ40DE)", "diagnostics").slug)
    front = page.split("---")[1]
    assert "2008" not in front and "Frontier" not in front and "Cam sensor fault." in page
    assert "| Frontier" not in (gen2(cfg) / "interchange.md").read_text()
    oq = (gen2(cfg) / "open_questions.md").read_text()
    assert "applicability" in oq and "shared platform" in oq


def test_curated_pages_survive_export_and_every_number_cites_a_source(cfg, conn):
    from xw.qa import check_curated

    good = ("# 2009 Nissan Xterra\n\n| Item | 2009 |\n|---|---|\n| Engine oil with filter | 5-3/8 qt [S13] |\n\n"
            "- Back to [2008](2008.md) and the [hub](../index.md)\n- Solar Yellow offered in 2009 [Unverified]\n\n"
            "## Sources\n\n- [S13] Nissan, 2009 Xterra Owner's Manual. https://owners.nissanusa.com/x.pdf\n")
    page = gen2(cfg) / "vehicle" / "years" / "2009.md"
    page.parent.mkdir(parents=True)
    page.write_text(good)
    (gen2(cfg) / "vehicle" / "index.md").write_text("# Hub\n\n- [2009](years/2009.md)\n\n## Sources\n")
    export(cfg, conn)
    assert page.read_text() == good                       # not a topic category: export never deletes or rewrites it
    assert "](vehicle/index.md)" in (gen2(cfg) / "index.md").read_text()
    assert check_curated(cfg.wiki_dir) == [] and check_wiki(cfg, conn) == []

    page.write_text(good.replace(" [S13] |", " |"))
    assert any("number without a source" in v for v in check_curated(cfg.wiki_dir))
    page.write_text(good.replace("- Back to", "- [Oil capacity is 5 qt](oil-change.md)\n- Back to"))   # link text is a claim
    assert any("number without a source: - [Oil capacity" in v for v in check_curated(cfg.wiki_dir))
    page.write_text(good.replace("[S13] |", "[S14] |"))
    assert any("unlisted source(s) S14" in v for v in check_curated(cfg.wiki_dir))
    page.write_text(good.replace("https://owners.nissanusa.com/x.pdf", "the glovebox copy"))
    assert any("without a key and URL" in v for v in check_curated(cfg.wiki_dir))
    page.write_text(good.split("## Sources")[0])
    assert any("no '## Sources' section" in v for v in check_curated(cfg.wiki_dir))
    page.write_text(GENERATED + "\n" + good)
    assert any("generated header" in v for v in check_wiki(cfg, conn))


def test_a_curated_guide_is_linked_from_its_topic_in_the_index(cfg, conn):
    from xw.qa import check_curated

    guides = gen2(cfg) / "vehicle" / "guides"
    guides.mkdir(parents=True)
    guide = "# Spark plugs\n\n1. Remove the coil [S1]\n\n## Sources\n\n- [S1] Nissan, 2013 Xterra Service Manual, EM. https://x.example/em.pdf\n"
    (guides / "spark-plugs.md").write_text(guide)
    (guides / "index.md").write_text("# Guides\n\n- [Spark plugs](spark-plugs.md)\n\n## Sources\n")
    export(cfg, conn)
    idx = (gen2(cfg) / "index.md").read_text()
    assert "| Spark plug replacement | [Guide](vehicle/guides/spark-plugs.md) | not-started | 0 |" in idx
    assert "| Engine oil and filter change |  | not-started | 0 |" in idx        # no guide, no link
    assert "](vehicle/guides/index.md)" in idx
    assert (guides / "spark-plugs.md").read_text() == guide                       # export never touches a guide
    assert check_curated(cfg.wiki_dir) == []                                       # and qa holds guides to the curated rule


def test_curated_and_generated_pages_must_sit_in_their_generations_section(cfg, conn):
    from xw.qa import check_curated

    src = "\n\n## Sources\n\n- [S1] Nissan, 2001 Xterra Owner's Manual. https://x.example/2001.pdf\n"
    gen1 = cfg.wiki_dir / "first-gen" / "vehicle"
    gen1.mkdir(parents=True)
    (gen1 / "index.md").write_text("# First-gen reference\n\nOverall width 70.4 in [S1]" + src)
    export(cfg, conn)
    assert "](vehicle/index.md)" in (cfg.wiki_dir / "first-gen" / "index.md").read_text()   # export links each section's hub
    assert check_curated(cfg.wiki_dir) == [] and check_wiki(cfg, conn) == []

    (gen1 / "index.md").write_text("# First-gen reference\n\nNarrower than the 2nd gen [S1]" + src)   # names the other generation
    assert any("names the Second generation" in v for v in check_curated(cfg.wiki_dir))
    (gen1 / "index.md").write_text("# First-gen reference\n\nOverall width 70.4 in [S1]" + src)

    old = cfg.wiki_dir / "vehicle"                       # the pre-split curated folder must not linger
    old.mkdir()
    (old / "index.md").write_text("# Hub\n\n## Sources\n")
    assert any("curated pages outside a generation's section" in v for v in check_curated(cfg.wiki_dir))
    (old / "index.md").unlink()
    old.rmdir()

    stray = cfg.wiki_dir / "repair" / "old.md"           # a generated page from the single-section layout
    stray.parent.mkdir(exist_ok=True)
    stray.write_text(GENERATED + "\n# Old page\n")
    assert any("repair/old.md: generated page outside a generation's section" in v for v in check_wiki(cfg, conn))


# --- verifier consensus: "supported" needs every pass to agree ------------------------------------------------
class FlipVerifier(FakeVerifier):
    """A FakeVerifier whose Nth call downgrades 'supported' to 'partial' for claims containing given words, standing in
    for the small model flipping an answer between runs."""

    def __init__(self, cfg, flips=None, **kw):
        super().__init__(cfg, **kw)
        self.flips = flips or {}

    def chat_json(self, system, user, schema=None):
        out = super().chat_json(system, user, schema)
        texts = dict(re.findall(r"^(\d+)\. (.*)$", user.split("\n\nCLAIMS:\n", 1)[1], re.M))
        for v in out["verdicts"]:
            if v["verdict"] == "supported" and any(w in texts[str(v["id"])] for w in self.flips.get(self.calls, ())):
                v["verdict"] = "partial"
        return out


def test_consensus_combines_passes_conservatively():
    from xw.verify import DECOY_FAILED, consensus

    one = {"a": "supported", "b": "supported", "c": "partial", "d": "unsupported", "e": "supported", "f": "partial", "g": "supported"}
    two = {"a": "supported", "b": "partial", "c": "partial", "d": "unsupported", "e": "unsupported", "f": "unsupported", "g": DECOY_FAILED}
    assert consensus([one, two]) == {"a": "supported", "b": "partial", "c": "partial", "d": "unsupported",
                                     "e": "partial", "f": "unsupported", "g": DECOY_FAILED}
    assert consensus([one]) == one and consensus([one, one]) == one


def test_one_pass_can_publish_what_two_passes_do_not_when_the_model_flips(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice")])
    answers = [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[])]})]

    single = FlipVerifier(cfg, flips={2: ("lower ball joint",)})          # the flip would hit pass 2, which never runs
    extract_and_verify(cfg, conn, answers, verifier=single)
    export(cfg, conn)
    assert single.calls == 1 and "Separate the lower ball joint" in page_text(cfg)


def test_two_passes_must_agree_before_a_claim_is_supported(cfg, conn, tmp_path):
    from xw.verify import decoy_stats

    cfg.verify._d["consensus_runs"] = 2
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice")])
    v = FlipVerifier(cfg, flips={2: ("lower ball joint",)})               # pass 2 backs off one step
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[])]})], verifier=v)
    assert v.calls == 2                                                    # two full passes
    d = decoy_stats(conn)
    assert d["calls"] == 2 and d["decoys"] >= 2 and d["accepted"] == 0     # every pass plants its own decoys
    got = dict(conn.execute("SELECT claim_key, verdict FROM verdicts WHERE by='local'").fetchall())
    assert got["step:1"] == "partial" and got["step:0"] == "supported"     # disagreement is not support
    export(cfg, conn)
    page = page_text(cfg)
    assert "2. [Partial] Separate the lower ball joint" in page        # published, but marked: not shown as supported
    assert "1. Support the truck securely on stands" in page


def test_two_passes_that_agree_publish_as_before(cfg, conn, tmp_path):
    cfg.verify._d["consensus_runs"] = 2
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice")])
    v = FlipVerifier(cfg)
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[])]})], verifier=v)
    export(cfg, conn)
    assert v.calls == 2 and "## Procedure" in page_text(cfg) and "Separate the lower ball joint" in page_text(cfg)


def test_a_decoy_failure_in_either_pass_withholds_the_claim(cfg, conn, tmp_path):
    cfg.verify._d["consensus_runs"] = 2
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice")])
    stamp = FakeVerifier(cfg, rubber_stamp=True)                           # accepts decoys in both passes
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[])]})], verifier=stamp)
    verdicts = {r[0] for r in conn.execute("SELECT verdict FROM verdicts WHERE by='local'")}
    assert verdicts == {"decoy_failed"}


# --- human triage: confirm or reject what the pipeline is not sure about --------------------------------------
def _triage_setup(cfg, conn, tmp_path, **fact_over):
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice")])
    answers = [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[], **fact_over)]})]
    extract_and_verify(cfg, conn, answers, verifier=FakeVerifier(cfg, partial=("lower ball joint",)))
    return answers


def _answers(*replies):
    """Scripted terminal input; running out behaves like closed stdin (EOFError), which the loop treats as quitting."""
    it = iter(replies)

    def read(prompt):
        try:
            return next(it)
        except StopIteration:
            raise EOFError from None
    return read


def _human(conn):
    return {(f, k): (v, n) for f, k, v, n in conn.execute("SELECT fact_id, claim_key, verdict, note FROM verdicts WHERE by='human'")}


def test_triage_queue_holds_only_claims_nobody_has_settled(cfg, conn, tmp_path):
    from xw.triage import triage_queue

    _triage_setup(cfg, conn, tmp_path)
    fid = conn.execute("SELECT id FROM facts").fetchone()[0]
    topics = TopicIndex(cfg.topics)

    def put(key, by, verdict, note=""):
        conn.execute("INSERT OR REPLACE INTO verdicts(fact_id, claim_key, by, verdict, note, created_at) VALUES(?,?,?,?,?,'')", (fid, key, by, verdict, note))

    put("step:0", "local", "partial"); put("step:0", "claude", "approve")           # Claude was confident: settled
    put("step:2", "local", "partial"); put("step:2", "claude", "reject")            # Claude was confident: settled
    put("tip:0", "claude", "needs_human", "the excerpt is ambiguous")                # Claude unsure: ask a human
    put("summary", "local", "partial"); put("summary", "human", "approve")          # already decided by a human
    put("tool:0", "local", "supported")                                               # the verifier is happy: not low confidence
    put("tool:1", "local", "unsupported")                                             # judged false: not low confidence either
    conn.commit()
    items = {i["id"]: i for i in triage_queue(cfg, conn, topics)}
    assert set(items) == {f"f{fid}:step:1", f"f{fid}:complete", f"f{fid}:tip:0"}   # the two verifier partials + Claude's doubt
    assert items[f"f{fid}:tip:0"]["priority"] == 0 and "ambiguous" in items[f"f{fid}:tip:0"]["why_queued"]
    assert items[f"f{fid}:step:1"]["priority"] == 1 and items[f"f{fid}:step:1"]["thread_id"]


def test_triage_never_shows_what_the_evidence_checks_already_refuse(cfg, conn, tmp_path):
    from xw.triage import triage_queue

    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice")])
    s = spec("99", "torque the inner pivot bolt to 99 ft-lb")                          # 99 is nowhere in the source
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[s])]})])
    fid = conn.execute("SELECT id FROM facts").fetchone()[0]
    conn.execute("UPDATE verdicts SET verdict='partial' WHERE claim_key='spec:0'")
    conn.commit()
    assert f"f{fid}:spec:0" not in {i["id"] for i in triage_queue(cfg, conn, TopicIndex(cfg.topics))}


def test_triage_loop_approve_reject_partial_skip_and_undo(cfg, conn, tmp_path):
    from xw.triage import run_triage

    _triage_setup(cfg, conn, tmp_path)
    fid = conn.execute("SELECT id FROM facts").fetchone()[0]
    shown = []
    # queue order is complete, step:1. Approve both; at the end undo the last answer; reject that step with a note; finish.
    run_triage(cfg, conn, TopicIndex(cfg.topics), input_fn=_answers("a", "a", "u", "r the fork is not in the thread", "done"), out=shown.append)
    h = _human(conn)
    assert h[(fid, "complete")][0] == "approve" and h[(fid, "step:1")] == ("reject", "the fork is not in the thread")
    assert conn.execute("SELECT count(*) FROM human_decisions").fetchone()[0] == 2
    export(cfg, conn)
    assert "## Procedure" not in page_text(cfg)                                           # a rejected step withholds the procedure
    text = "\n".join(shown)
    assert "CLAIM:" in text and "SOURCE EXCERPT" in text and "2 claim(s) waiting" in text


def test_triage_approving_the_step_and_marking_the_list_partial_publishes_it_marked(cfg, conn, tmp_path):
    from xw.triage import run_triage

    _triage_setup(cfg, conn, tmp_path)
    run_triage(cfg, conn, TopicIndex(cfg.topics), input_fn=_answers("p steps are right, torque step missing", "a"), out=lambda m: None)
    export(cfg, conn)
    page = page_text(cfg)
    assert "Separate the lower ball joint" in page and "[Partial]" in page and check_wiki(cfg, conn) == []


def test_triage_confirming_the_whole_procedure_drops_the_partial_mark(cfg, conn, tmp_path):
    from xw.triage import run_triage

    _triage_setup(cfg, conn, tmp_path)
    run_triage(cfg, conn, TopicIndex(cfg.topics), input_fn=_answers("a", "a"), out=lambda m: None)
    export(cfg, conn)
    page = page_text(cfg)
    assert "Separate the lower ball joint" in page and "[Partial]" not in page


def test_triage_skip_quit_and_bad_input_decide_nothing(cfg, conn, tmp_path):
    from xw.triage import run_triage

    _triage_setup(cfg, conn, tmp_path)
    out = []
    counts = run_triage(cfg, conn, TopicIndex(cfg.topics), kinds={"step"}, input_fn=_answers("zzz", "p", "s"), out=out.append)
    assert not _human(conn) and counts["skipped"] == 1
    assert len([m for m in out if m.startswith("answer a, r,")]) == 2        # "zzz" and "p" (partial is for completeness claims only)
    counts = run_triage(cfg, conn, TopicIndex(cfg.topics), input_fn=_answers("a", "q"), out=lambda m: None)
    assert counts["approve"] == 1 and len(_human(conn)) == 1                 # q stops before the second claim
    assert run_triage(cfg, conn, TopicIndex(cfg.topics), input_fn=_answers(), out=lambda m: None)["approve"] == 0   # EOF ends cleanly


def test_a_human_decision_follows_its_claim_across_a_reextraction_and_a_redo(cfg, conn, tmp_path):
    from xw.triage import run_triage

    answers = _triage_setup(cfg, conn, tmp_path)
    old = conn.execute("SELECT id FROM facts").fetchone()[0]
    run_triage(cfg, conn, TopicIndex(cfg.topics), input_fn=_answers("a", "a"), out=lambda m: None)
    verify_pending(cfg, conn, FakeVerifier(cfg, partial=("lower ball joint",)), redo=True, log=lambda m: None)
    assert (old, "step:1") in _human(conn)                                                 # --redo leaves human verdicts alone

    conn.execute("DELETE FROM verdicts"); conn.execute("DELETE FROM facts"); conn.execute("UPDATE chunks SET status='pending', attempts=0")
    conn.commit()                                                                          # what a re-extraction does to fact ids
    extract_and_verify(cfg, conn, answers, verifier=FakeVerifier(cfg, partial=("lower ball joint",)))
    new = conn.execute("SELECT id FROM facts").fetchone()[0]
    assert new != old and _human(conn)[(new, "step:1")][0] == "approve" and _human(conn)[(new, "complete")][0] == "approve"
    export(cfg, conn)
    assert "Separate the lower ball joint" in page_text(cfg) and "[Partial]" not in page_text(cfg)


def test_a_reworded_claim_is_a_new_undecided_claim(cfg, conn, tmp_path):
    from xw.triage import run_triage, triage_queue

    answers = _triage_setup(cfg, conn, tmp_path)
    run_triage(cfg, conn, TopicIndex(cfg.topics), input_fn=_answers("a", "a"), out=lambda m: None)
    reworded = [(answers[0][0], {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[],
                steps=["Support the truck securely on stands", "Use a fork to separate the lower ball joint", "Remove the pivot bolts and drop the arm"])]})]
    conn.execute("DELETE FROM verdicts"); conn.execute("DELETE FROM facts"); conn.execute("UPDATE chunks SET status='pending', attempts=0")
    conn.commit()
    extract_and_verify(cfg, conn, reworded, verifier=FakeVerifier(cfg, partial=("lower ball joint",)))
    fid = conn.execute("SELECT id FROM facts").fetchone()[0]
    assert (fid, "step:1") not in _human(conn)
    assert f"f{fid}:step:1" in {i["id"] for i in triage_queue(cfg, conn, TopicIndex(cfg.topics))}


def test_triage_warns_before_a_single_source_safety_value_is_approved(cfg, conn, tmp_path):
    from xw.triage import run_triage

    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice")])
    s = spec("83", "Torque the inner pivot bolts to 83 ft-lb")
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[s])]})])
    out = []
    run_triage(cfg, conn, TopicIndex(cfg.topics), kinds={"spec"}, input_fn=_answers("a approved against the service manual"), out=out.append)
    assert any("SAFETY-CRITICAL VALUE" in m and "without a second source" in m for m in out)
    export(cfg, conn)
    assert "83 ft-lb" in page_text(cfg) and "Human-reviewed" in page_text(cfg) and check_wiki(cfg, conn) == []


def test_xw_triage_list_is_a_plain_report(root, capsys):
    assert main(["--root", str(root), "init"]) == 0
    assert main(["--root", str(root), "triage", "--list"]) == 0
    assert "Nothing is waiting" in capsys.readouterr().out


# --- review findings on the consensus/summary work -----------------------------------------------------------------
def test_raising_consensus_runs_re_judges_claims_that_only_had_one_pass(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice")])
    answers = [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[])]})]
    one = FlipVerifier(cfg)
    extract_and_verify(cfg, conn, answers, verifier=one)                              # consensus_runs is 1 in the test config
    assert one.calls == 1 and {r[0] for r in conn.execute("SELECT runs FROM verdict_runs")} == {1}
    assert dict(conn.execute("SELECT claim_key, verdict FROM verdicts WHERE by='local'").fetchall())["step:1"] == "supported"

    cfg.verify._d["consensus_runs"] = 2                                                # the operator turns consensus on...
    two = FlipVerifier(cfg, flips={2: ("lower ball joint",)})
    assert verify_pending(cfg, conn, two, log=lambda m: None) == 1                     # ...and a plain `xw verify` (no --redo) applies it
    assert two.calls == 2
    assert dict(conn.execute("SELECT claim_key, verdict FROM verdicts WHERE by='local'").fetchall())["step:1"] == "partial"
    assert {r[0] for r in conn.execute("SELECT runs FROM verdict_runs")} == {2}
    idle = FlipVerifier(cfg)
    assert verify_pending(cfg, conn, idle, log=lambda m: None) == 0 and idle.calls == 0   # now nothing is stale

    conn.execute("DELETE FROM verdict_runs")                                           # a database from before the table existed
    legacy = FlipVerifier(cfg)
    assert verify_pending(cfg, conn, legacy, log=lambda m: None) == 1 and legacy.calls == 2


def test_a_review_verdict_for_a_claim_that_was_rewritten_is_not_applied(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice")])
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[])]})])
    fid = conn.execute("SELECT id FROM facts").fetchone()[0]
    conn.execute("UPDATE verdicts SET verdict='partial' WHERE claim_key='summary'")    # queue the summary for review
    conn.commit()
    batches = export_review(cfg, conn, TopicIndex(cfg.topics))
    review_dir = cfg.data_dir / "review"
    import json as _json
    items = _json.loads(batches[0].read_text())["items"]
    assert any(i["id"] == f"f{fid}:summary" for i in items)
    (review_dir / "batch-001.verdicts.json").write_text(_json.dumps({"verdicts": [{"id": i["id"], "verdict": "approve", "note": "ok"} for i in items]}))

    # `xw summarize --redo` rewrites the summary and drops its verdicts, but the batch and the approval are still on disk
    fact = conn.execute("SELECT fact_json FROM facts").fetchone()[0]
    conn.execute("UPDATE facts SET fact_json=?", (fact.replace("Both front lower arms can be swapped", "A completely different claim about the arms"),))
    conn.execute("DELETE FROM verdicts WHERE claim_key='summary'")
    conn.commit()
    stats = apply_reviews(cfg, conn)
    assert stats["stale"] >= 1
    assert not conn.execute("SELECT 1 FROM verdicts WHERE claim_key='summary' AND by='claude'").fetchone()   # the old approval did not transfer

    conn.execute("INSERT INTO verdicts(fact_id, claim_key, by, verdict, created_at) VALUES(?,?,?,?,?)", (fid, "summary", "local", "partial", ""))
    conn.commit()
    again = export_review(cfg, conn, TopicIndex(cfg.topics))                          # the rewritten claim is queued again
    assert again and any(i["id"] == f"f{fid}:summary" for p in again for i in _json.loads(p.read_text())["items"])


# ---- reviewer corrections (docs/proposals/reviewer-corrections.md: option A, number changes wait for a person) -------
def correction_round(cfg, conn, name, verdicts, by="claude"):
    """Write a batch holding the claims these verdicts answer, as the pipeline shows them now, and its verdicts file;
    then apply it like `xw review-apply`."""
    from xw.corrections import displayed_claims

    review_dir = cfg.data_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for v in verdicts:
        fid, key = v["id"][1:].split(":", 1)
        items.append({"id": v["id"], "claim": displayed_claims(conn, int(fid)).get(key, "")})
    (review_dir / f"{name}.json").write_text(json.dumps({"items": items}))
    path = review_dir / f"{name}.verdicts.json"
    path.write_text(json.dumps({"verdicts": verdicts}))
    return apply_reviews(cfg, conn, [path], by=by)


def _row(conn):
    from xw.export import load_rows
    return load_rows(conn)[0]


def test_a_reviewer_correction_rewords_a_step_and_the_procedure_publishes(cfg, conn, tmp_path):
    """A garbled step used to leave only reject or needs_human, and either withholds the whole procedure."""
    _triage_setup(cfg, conn, tmp_path)                       # step 1 is `partial` locally: the procedure is withheld
    fid = fact_id(conn)
    stats = correction_round(cfg, conn, "batch-101", [
        {"id": f"f{fid}:step:1", "verdict": "correct", "corrected": "Pop the lower ball joint loose with a fork", "note": "wording"},
        {"id": f"f{fid}:complete", "verdict": "needs_human", "note": "judged with the correction in view"}])
    assert stats["corrected"] == 1 and stats["applied"] == 1 and stats["pending"] == stats["refused"] == 0
    export(cfg, conn)
    page = page_text(cfg)
    assert "2. Pop the lower ball joint loose with a fork" in page and "Separate the lower ball joint" not in page
    assert "[Partial]" in page and "1 step reworded by a reviewer" in page
    assert check_wiki(cfg, conn) == []
    assert "Separate the lower ball joint with a fork" in conn.execute("SELECT fact_json FROM facts").fetchone()[0]  # extraction kept


def test_a_correction_with_an_unsourced_number_or_copied_text_is_never_used(cfg, conn, tmp_path):
    from xw.corrections import store

    _triage_setup(cfg, conn, tmp_path)
    fid = fact_id(conn)
    stats = correction_round(cfg, conn, "batch-102", [
        {"id": f"f{fid}:step:1", "verdict": "correct", "corrected": "Separate the lower ball joint with a 32mm fork"},   # no 32 in the source
        {"id": f"f{fid}:step:2", "verdict": "correct",
         "corrected": "Lower control arm job on a 2008. Torque the inner pivot bolts to 83 ft-lb on the lower arm."}])  # copies the source
    assert stats["refused"] == 2 and stats["corrected"] == stats["pending"] == 0
    assert conn.execute("SELECT count(*) FROM corrections").fetchone()[0] == 0
    # a stored correction is re-checked on every export (rules may tighten after it was accepted): it is not used
    store(conn, _row(conn).thread_id, "step:1", "Separate the lower ball joint with a fork",
          "Pop the ball joint loose. Lower control arm job on a 2008. Torque the inner pivot bolts to 83 ft-lb on the lower arm.", "human")
    row = _row(conn)
    assert row.fact.steps[1] == "Separate the lower ball joint with a fork" and row.corrected == {}
    export(cfg, conn)
    assert "2. [Partial] Separate the lower ball joint with a fork" in page_text(cfg)   # original wording, still partial


def test_a_corrected_step_with_a_torque_value_is_marked_unconfirmed_or_needs_a_spec(cfg, conn, tmp_path):
    steps = ["Support the truck securely on stands", "Separate the lower ball joint with a fork", "Tighten the pivot bolts to 83 ft-lb"]
    _triage_setup(cfg, conn, tmp_path, steps=steps)          # no spec on the page
    fid = fact_id(conn)
    correction_round(cfg, conn, "batch-103", [
        {"id": f"f{fid}:step:1", "verdict": "approve"},
        {"id": f"f{fid}:step:2", "verdict": "correct", "corrected": "Snug the inner pivot bolts down to 83 ft-lb"},
        {"id": f"f{fid}:complete", "verdict": "approve"}])
    assert _row(conn).fact.steps[2] == "Snug the inner pivot bolts down to 83 ft-lb"
    export(cfg, conn)
    assert "3. [Unverified value] Snug the inner pivot bolts down to 83 ft-lb" in page_text(cfg)   # no spec here: marked
    assert check_wiki(cfg, conn) == []
    strict(cfg)
    export(cfg, conn)
    assert "## Procedure" not in page_text(cfg)              # strict: 83 ft-lb in prose needs a published spec
    cfg.verify.as_dict().update(publish_partial=True, publish_unverified_safety=True)
    # a person's correction outranks Claude's, and may change a number; without the torque value the procedure publishes
    stats = correction_round(cfg, conn, "batch-104", [
        {"id": f"f{fid}:step:2", "verdict": "correct", "corrected": "Snug the inner pivot bolts down"},
        {"id": f"f{fid}:complete", "verdict": "approve"}], by="human")
    assert stats["corrected"] == 1
    export(cfg, conn)
    page = page_text(cfg)
    assert "3. Snug the inner pivot bolts down" in page and "83 ft-lb" not in page and check_wiki(cfg, conn) == []


def test_a_correction_follows_its_claim_across_a_reextraction_and_lapses_when_the_text_changes(cfg, conn, tmp_path):
    answers = _triage_setup(cfg, conn, tmp_path)
    fid = fact_id(conn)
    correction_round(cfg, conn, "batch-105", [
        {"id": f"f{fid}:step:1", "verdict": "correct", "corrected": "Pop the lower ball joint loose with a fork"}])

    def reextract(ans):
        conn.execute("DELETE FROM verdicts")
        conn.execute("DELETE FROM facts")
        conn.execute("UPDATE chunks SET status='pending'")
        conn.commit()
        extract_and_verify(cfg, conn, ans, verifier=FakeVerifier(cfg, partial=("lower ball joint",)))

    reextract(answers)                                       # same text, new fact id
    row = _row(conn)
    assert row.id != fid and row.fact.steps[1] == "Pop the lower ball joint loose with a fork" and row.corrected == {"step:1": "claude"}
    reworded = [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[], steps=[
        "Support the truck securely on stands", "Split the lower ball joint using a fork", "Remove the pivot bolts and drop the arm"])]})]
    reextract(reworded)                                      # different text: the correction says nothing about it
    row = _row(conn)
    assert row.fact.steps[1] == "Split the lower ball joint using a fork" and row.corrected == {}


def test_a_complete_verdict_on_the_old_list_does_not_publish_a_corrected_procedure(cfg, conn, tmp_path):
    _triage_setup(cfg, conn, tmp_path)
    fid = fact_id(conn)
    correction_round(cfg, conn, "batch-106", [{"id": f"f{fid}:step:1", "verdict": "approve"},
                                              {"id": f"f{fid}:complete", "verdict": "approve"}])
    export(cfg, conn)
    assert "## Procedure" in page_text(cfg) and "[Partial]" not in page_text(cfg)
    correction_round(cfg, conn, "batch-107", [{"id": f"f{fid}:step:0", "verdict": "correct", "corrected": "Put the truck on jack stands"}])
    export(cfg, conn)
    assert "## Procedure" not in page_text(cfg)              # that approval judged the old list; local verdicts never count here
    queued = [i for p in export_review(cfg, conn, TopicIndex(cfg.topics)) for i in json.loads(p.read_text())["items"]]
    redo = next(i for i in queued if i["id"] == f"f{fid}:complete")
    assert "reworded" in redo["why_queued"] and "Put the truck on jack stands" in redo["claim"]
    correction_round(cfg, conn, "batch-108", [{"id": f"f{fid}:complete", "verdict": "approve"}])
    export(cfg, conn)
    page = page_text(cfg)
    assert "1. Put the truck on jack stands" in page and "[Partial]" not in page and "1 step reworded by a reviewer" in page


NOTE_C = "Front lower arm swap. Loosen the 2 pivot bolts first, then the 3 ball joint nuts. Torque the inner pivot bolts to 83 ft-lb. " * 4


def test_a_claude_correction_that_changes_a_number_waits_for_a_person(cfg, conn, tmp_path):
    from xw.triage import run_triage, triage_queue

    add_notes(cfg, conn, tmp_path, [("a", NOTE_C, "alice")])
    extract_and_verify(cfg, conn, [("pivot bolts first", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[], steps=[
        "Loosen the 3 pivot bolts", "Loosen the ball joint nuts"])]})], verifier=FakeVerifier(cfg, partial=("3 pivot",)))
    fid = fact_id(conn)
    stats = correction_round(cfg, conn, "batch-109", [
        {"id": f"f{fid}:step:0", "verdict": "correct", "corrected": "Loosen the 2 pivot bolts first", "note": "source says 2"}])
    assert stats["pending"] == 1 and stats["corrected"] == 0
    assert _row(conn).fact.steps[0] == "Loosen the 3 pivot bolts"                     # not used until a person accepts it
    queue = triage_queue(cfg, conn, TopicIndex(cfg.topics))
    item = queue[0]
    assert item["kind"] == "correction" and item["corrected"] == "Loosen the 2 pivot bolts first" and item["priority"] == 0
    assert sum(1 for i in queue if i["id"] == f"f{fid}:step:0") == 1                   # shown once, as the correction
    shown = []
    run_triage(cfg, conn, TopicIndex(cfg.topics), kinds={"correction"}, input_fn=_answers("a checked the source", "done"), out=shown.append)
    assert "CLAUDE'S CORRECTION" in "\n".join(shown)
    row = _row(conn)
    assert row.fact.steps[0] == "Loosen the 2 pivot bolts first" and row.corrected == {"step:0": "claude"}
    assert triage_queue(cfg, conn, TopicIndex(cfg.topics), kinds={"correction"}) == []
    # a rejected proposal is never used and not asked again
    stats = correction_round(cfg, conn, "batch-110", [
        {"id": f"f{fid}:step:1", "verdict": "correct", "corrected": "Loosen the 3 ball joint nuts"}])
    assert stats["pending"] == 1
    run_triage(cfg, conn, TopicIndex(cfg.topics), kinds={"correction"}, input_fn=_answers("r not what it says", "done"), out=lambda m: None)
    assert _row(conn).fact.steps[1] == "Loosen the ball joint nuts"
    assert triage_queue(cfg, conn, TopicIndex(cfg.topics), kinds={"correction"}) == []


def test_correcting_a_value_metadata_tool_or_complete_claim_is_invalid_input(cfg, conn, tmp_path):
    _triage_setup(cfg, conn, tmp_path)
    fid = fact_id(conn)
    stats = claude_verdicts(cfg, conn, [
        {"id": f"f{fid}:complete", "verdict": "correct", "corrected": "These steps are the whole job"},
        {"id": f"f{fid}:applies", "verdict": "correct", "corrected": "Applies to 2008"},
        {"id": f"f{fid}:tool:0", "verdict": "correct", "corrected": "Tool needed: 22mm socket"},
        {"id": f"f{fid}:step:1", "verdict": "correct"},                                                 # no wording given
        {"id": f"f{fid}:step:1", "verdict": "correct", "corrected": "Separate the lower ball joint with a fork."}])  # no change
    assert stats["invalid"] == 5 and stats["corrected"] == stats["pending"] == 0
    assert conn.execute("SELECT count(*) FROM corrections").fetchone()[0] == 0


def test_every_copy_of_the_reviewer_instructions_describes_corrections():
    from xw.review import INSTRUCTIONS

    root = Path(__file__).resolve().parents[1]
    for text in [(root / p).read_text() for p in (".claude/agents/wiki-reviewer.md", ".codex/agents/wiki-reviewer.toml")] + [INSTRUCTIONS]:
        assert "correct" in text and "corrected" in text and "never add a number" in text.lower(), text[:80]


def test_a_claude_correction_that_changes_only_a_unit_waits_and_one_the_source_contradicts_is_refused(cfg, conn, tmp_path):
    """Codex review of #9 (P2), for corrections: a unit is part of the number. 83 ft-lb -> 83 in-lb is a change a person
    must accept, and a unit the source never puts on that number is refused outright."""
    steps = ["Support the truck securely on stands", "Separate the lower ball joint with a fork", "Tighten the pivot bolts to 83 ft-lb"]
    _triage_setup(cfg, conn, tmp_path, steps=steps)
    fid = fact_id(conn)
    stats = correction_round(cfg, conn, "batch-111", [
        {"id": f"f{fid}:step:2", "verdict": "correct", "corrected": "Snug the inner pivot bolts down to 83 in-lb"}])
    assert stats["refused"] == 1 and stats["corrected"] == stats["pending"] == 0      # the source says 83 ft-lb
    from xw.corrections import changes_numbers
    assert changes_numbers("Use a 10mm socket", "Use a 10 cm socket") and changes_numbers("83 ft-lb", "83 in-lb")
    assert not changes_numbers("Tighten to 83 ft-lb", "Snug them to 83 ft-lbs")


def test_a_value_with_a_paraphrased_or_missing_quote_publishes_and_a_wrong_value_does_not(cfg, conn, tmp_path):
    """Only the value needs to be correct (2026-10-16): the model's `evidence` quote is not a gate any more."""
    note = ("Lower control arm job on a 2008. Use a 21mm socket on the pivot bolts. Torque the inner pivot bolts to 83 ft-lb. "
            "The new arm is 54500-EA000. ") * 6
    add_notes(cfg, conn, tmp_path, [("a", note, "alice")])
    specs = [{"item": "Pivot bolt socket size", "value": "21", "unit": "mm", "evidence": "the socket is twenty-one millimetres"},
             {"item": "Tie rod socket size", "value": "19", "unit": "mm", "evidence": ""},          # 19 is not in the source
             {"item": "Pivot bolt torque", "value": "83", "unit": "in-lb", "evidence": ""}]         # the source says ft-lb
    parts = [{"name": "Lower control arm", "part_number": "54500-EA000", "evidence": ""}]
    extract_and_verify(cfg, conn, [("21mm socket", {"relevant": True, "facts": [arm_fact(specs=specs, parts=parts, diagram_links=[])]})])
    export(cfg, conn)
    page = page_text(cfg)
    assert "**Pivot bolt socket size**: 21 mm [t1]" in page
    assert "- Lower control arm (54500-EA000) [t1]" in page                                       # no quote at all
    assert "19 mm" not in page and "83 in-lb" not in page
    assert check_wiki(cfg, conn) == []


# ---- partial claims publish flagged (verify.publish_partial, decided 2026-10-16) ----------------------------------------
def test_a_partial_claim_publishes_flagged_and_loses_the_flag_once_confirmed(cfg, conn, tmp_path):
    """387 of 686 withheld items were the local verifier's `partial`. They now publish marked [Partial] (needs more work)
    and stay queued, so a later supported verdict or a review drops the mark."""
    _triage_setup(cfg, conn, tmp_path)                       # step 1 and `complete` are partial locally
    fid = fact_id(conn)
    export(cfg, conn)
    page = page_text(cfg)
    assert "## Procedure" in page and "2. [Partial] Separate the lower ball joint with a fork" in page
    assert "1. Support the truck securely on stands" in page          # a supported step carries no mark
    assert "needs more work" in page.lower() and check_wiki(cfg, conn) == []
    queued = {i["id"] for p in export_review(cfg, conn, TopicIndex(cfg.topics)) for i in json.loads(p.read_text())["items"]}
    assert {f"f{fid}:step:1", f"f{fid}:complete"} <= queued          # still asked about
    claude_verdicts(cfg, conn, [{"id": f"f{fid}:step:1", "verdict": "approve"}, {"id": f"f{fid}:complete", "verdict": "approve"}])
    export(cfg, conn)
    page = page_text(cfg)
    assert "2. Separate the lower ball joint with a fork" in page and "[Partial]" not in page


def test_a_partial_safety_value_publishes_marked_and_a_partial_never_beats_a_firmer_no(cfg, conn, tmp_path):
    """Two independent threads agree on a torque value the verifier only partly supports: it publishes marked [Partial]
    under the warning banner and stays queued. A partial never overrides `unsupported` or a reviewer's reject."""
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice"), ("b", NOTE_A.replace("2008", "2010"), "bob")])
    fact = arm_fact(parts=[], diagram_links=[], specs=[spec("83", "Torque the inner pivot bolts to 83 ft-lb")],
                    tips=["Final-tighten the pivot bolts with the truck's weight on the suspension", "Grease the bushings first"])
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [fact]})],
                       verifier=FakeVerifier(cfg, partial=("83 ft-lb", "Grease"), bad=("weight on the suspension",)))
    export(cfg, conn)
    page = page_text(cfg)
    assert "**Inner pivot bolt torque**: 83 ft-lb [t1, t2] ([Partial] community-consensus, 2 threads)" in page
    assert SAFETY_NOTE in page and "83 ft-lb" in (gen2(cfg) / "pending_verification.md").read_text()
    assert "- [Partial] Grease the bushings first" in page              # an ordinary partial tip publishes, marked
    assert "Final-tighten" not in page                                 # unsupported stays out
    assert check_wiki(cfg, conn) == []
    claude_verdicts(cfg, conn, [{"id": f"f{r[0]}:tip:1", "verdict": "reject"} for r in conn.execute("SELECT id FROM facts")])
    export(cfg, conn)
    assert "Grease the bushings first" not in page_text(cfg) and check_wiki(cfg, conn) == []


def test_publish_partial_off_restores_fail_closed(cfg, conn, tmp_path):
    cfg.verify.as_dict()["publish_partial"] = False
    _triage_setup(cfg, conn, tmp_path)
    export(cfg, conn)
    page = page_text(cfg)
    assert "## Procedure" not in page and "[Partial]" not in page


def test_a_safety_value_in_prose_without_a_spec_needs_its_unit_in_the_source_and_a_mark(cfg, conn, tmp_path):
    """With publish_unverified_safety, a torque/capacity value stated only in prose publishes marked [Unverified value]
    when the source puts that unit on that number, and is queued at priority 0 until a reviewer confirms it."""
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A + "Refill the diff with 2.75 qt of gear oil. " * 3, "alice")])
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(
        tips=["Top off the diff with 2.75 qt afterwards", "Top off the diff with 2.75 L afterwards"], parts=[], diagram_links=[],
        specs=[])]})])
    export(cfg, conn)
    page = page_text(cfg)
    assert "- [Unverified value] Top off the diff with 2.75 qt afterwards [t1]" in page
    assert "2.75 L" not in page                                        # the source never says litres
    assert "does not state with that unit: 2.75 L" in (gen2(cfg) / "open_questions.md").read_text()
    assert check_wiki(cfg, conn) == []
    fid = fact_id(conn)
    queued = {i["id"]: i for p in export_review(cfg, conn, TopicIndex(cfg.topics)) for i in json.loads(p.read_text())["items"]}
    assert queued[f"f{fid}:tip:0"]["priority"] == 0
    path = gen2(cfg) / "repair" / "control-arms-bushings.md"
    path.write_text(page.replace("[Unverified value] Top off", "Top off"))
    assert any("outside the specifications: 2.75 qt" in v for v in check_wiki(cfg, conn))   # unmarked: refused


def test_a_part_note_with_an_unconfirmed_volume_is_marked(cfg, conn, tmp_path):
    """Found on the live export: a part note stating "12 quarts" published unmarked, and qa refused the page."""
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A + "Buy 12 quarts of Matic S ATF for the flush. " * 3, "alice")])
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(
        parts=[{"name": "Matic S ATF", "part_number": "", "notes": "12 quarts for the flush", "evidence": ""}],
        diagram_links=[], specs=[])]})])
    export(cfg, conn)
    page = page_text(cfg)
    assert "- [Unverified value] Matic S ATF: 12 quarts for the flush [t1]" in page and SAFETY_NOTE in page
    assert check_wiki(cfg, conn) == []


def test_consensus_below_a_raised_safety_threshold_is_marked_unverified(cfg, conn, tmp_path):
    """Codex review of #9 (P1): with safety_min_threads 3, two independent reports took the community-consensus tag
    unmarked although the value was not confirmed, and qa took that tag as confirmed."""
    cfg.verify.as_dict()["safety_min_threads"] = 3
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice"), ("b", NOTE_A.replace("2008", "2010"), "bob")])
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(
        parts=[], diagram_links=[], specs=[spec("83", "Torque the inner pivot bolts to 83 ft-lb")])]})])
    export(cfg, conn)
    page = page_text(cfg)
    assert "83 ft-lb [t1, t2] ([Unverified] community-consensus, 2 threads, needs 3)" in page and SAFETY_NOTE in page
    assert check_wiki(cfg, conn) == []
    path = gen2(cfg) / "repair" / "control-arms-bushings.md"
    path.write_text(page.replace("([Unverified] community-consensus, 2 threads, needs 3)", "(community-consensus, 2 threads)"))
    assert any("below verify.safety_min_threads" in v for v in check_wiki(cfg, conn))   # qa holds the threshold too
    cfg.verify.as_dict()["safety_min_threads"] = 2
    export(cfg, conn)
    assert "83 ft-lb [t1, t2] (community-consensus, 2 threads)" in page_text(cfg) and SAFETY_NOTE not in page_text(cfg)
