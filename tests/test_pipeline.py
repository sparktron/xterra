"""End to end with a fake HTTP site and fake LLMs: crawl -> chunks -> extract -> verify -> merge -> review -> wiki -> qa."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import httpx

from xw import db
from xw.cli import main
from xw.crawl import build_chunks, discover, harvest
from xw.export import GENERATED, export_all
from xw.extract import extract_pending
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


def page_text(cfg, cat="repair", slug="control-arms-bushings"):
    return (cfg.wiki_dir / cat / f"{slug}.md").read_text()


def fact_id(conn):
    return conn.execute("SELECT id FROM facts ORDER BY id LIMIT 1").fetchone()[0]


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
    pv = (cfg.wiki_dir / "pending_verification.md").read_text()
    assert "Inner pivot bolt torque" in pv and "83 ft-lb" in pv and "only 1 thread" in pv
    oq = (cfg.wiki_dir / "open_questions.md").read_text()
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
    assert "local verifier: not run" in (cfg.wiki_dir / "open_questions.md").read_text()

    cfg.verify.as_dict()["require_local_pass"] = False        # explicit opt-out publishes prose again
    export(cfg, conn)
    assert "## Procedure" in page_text(cfg)


def test_verifier_disagreement_withholds_claims_and_whole_procedures(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("a", "Lower control arm job on a 2008. Torque the inner pivot bolts to 83 ft-lb on the lower arm. " * 6, "alice")])
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[])]})],
                       verifier=FakeVerifier(cfg, bad=("lower ball joint",), partial=("weight on the suspension",)))
    export(cfg, conn)
    page, oq = page_text(cfg), (cfg.wiki_dir / "open_questions.md").read_text()
    assert "## Procedure" not in page and "Remove the pivot bolts" not in page   # one bad step withholds the whole procedure
    assert "Final-tighten" not in page                                          # 'partial' is not enough
    assert "local verifier: unsupported" in oq and "local verifier: partial" in oq
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
    assert "sources disagree" in (cfg.wiki_dir / "pending_verification.md").read_text()
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
    path = cfg.wiki_dir / "repair" / "control-arms-bushings.md"
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


def test_copied_text_and_unstated_metadata_are_not_published(cfg, conn, tmp_path):
    text = "Loosen the lug nuts, raise the front, and support it on stands. Then continue on this 2008 Xterra X lower arm job. " * 4
    add_notes(cfg, conn, tmp_path, [("a", text, "alice")])
    extract_and_verify(cfg, conn, [("lug nuts", {"relevant": True, "facts": [arm_fact(
        steps=["Loosen the lug nuts, raise the front, and support it on stands.", "Drop the arm"],
        years=[2008, 2012], trims=["X", "SE", "Off-Road"], parts=[], specs=[], diagram_links=[])]})])
    export(cfg, conn)
    page = page_text(cfg)
    assert "Loosen the lug nuts, raise the front" not in page and "## Procedure" not in page    # verbatim -> withheld
    assert "verbatim overlap" in (cfg.wiki_dir / "open_questions.md").read_text()
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
    rows = list(csv.reader((cfg.wiki_dir / "dtc_table.csv").open()))
    assert [r[0] for r in rows[1:]] == ["P0340"]                  # ungrounded P0999 excluded
    ic = (cfg.wiki_dir / "interchange.md").read_text()
    assert "Frontier" in ic and "| Titan" not in ic and "Frontier, Titan" not in ic                 # 'Titan' is not in the source text, so it is dropped


def test_out_of_scope_years_are_dropped(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("gen1", "My 2001 Xterra first generation needs a new alternator belt and the procedure is simple enough. " * 6, "dan")])
    extract_and_verify(cfg, conn, [("2001", {"relevant": True, "facts": [arm_fact(years=[2001], parts=[], specs=[], diagram_links=[])]})])
    assert conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 0


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
    assert "thenewx" in (cfg.wiki_dir / "open_questions.md").read_text()


def test_build_chunks_splits_and_skips_noise():
    posts = [Post("a", "2014-01-01", "First post. " + "word " * 300), Post("b", "", "thanks"), Post("c", "", "long reply " * 200)]
    chunks = build_chunks("T", posts, max_chars=1500, min_chars=100, min_post_chars=60)
    assert len(chunks) >= 2 and all(c.startswith("THREAD: T") for c in chunks)
    assert not any("thanks" in c for c in chunks)
    assert "(continued)" in chunks[1]


def test_cli_init_status_export_qa(root, capsys):
    assert main(["--root", str(root), "init"]) == 0
    assert main(["--root", str(root), "status"]) == 0
    out = capsys.readouterr().out
    assert "thenewx" in out and "manual" in out
    assert main(["--root", str(root), "export"]) == 0
    assert main(["--root", str(root), "qa"]) == 0
    assert main(["--root", str(root), "review-export"]) == 0
    assert (root / "wiki" / "index.md").exists() and (root / "wiki" / "pending_verification.md").exists()


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
    assert "ECU" not in (cfg.wiki_dir / "dtc_table.csv").read_text()


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
    assert "extraction failed" in (cfg.wiki_dir / "open_questions.md").read_text()


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
    assert "local verifier: decoy_failed" in (cfg.wiki_dir / "open_questions.md").read_text()
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
    assert "83 ft-lb" not in page_text(cfg)
    assert "1 distinct known author" in (cfg.wiki_dir / "pending_verification.md").read_text()
    assert "confidence: community-consensus" not in page_text(cfg)


def test_review_queue_counts_corroboration_like_the_exporter(cfg, conn, tmp_path):
    """Thread b states the same value but its verifier pass rejected it, so the exporter has one supporting thread
    and withholds the value. The queue must offer it for review at priority 0, not skip it as already corroborated."""
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
    assert "only 1 thread" in (cfg.wiki_dir / "pending_verification.md").read_text()
    batch = json.loads(export_review(cfg, conn, TopicIndex(cfg.topics))[0].read_text())
    top = batch["items"][0]
    assert top["id"] == f"f{fact_id(conn)}:spec:0" and top["priority"] == 0 and "only 1 thread" in top["why_queued"]


def test_safety_values_in_prose_need_a_published_spec(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A + "Refill the diff with 2.75 qt of gear oil. " * 3, "alice")])
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(
        steps=["Support the truck on stands", "Torque the pivot bolts to 83 ft-lb with the arm loaded"],
        tips=["Top off the diff with 2.75 qt afterwards"], parts=[], diagram_links=[],
        specs=[spec("83", "Torque the inner pivot bolts to 83 ft-lb")])]})])
    export(cfg, conn)
    page, oq = page_text(cfg), (cfg.wiki_dir / "open_questions.md").read_text()
    assert "## Procedure" not in page and "2.75" not in page and "83 ft-lb" not in page   # spec is single-source -> pending
    assert "not published as a corroborated spec: 83 ft-lb" in oq and "2.75 qt" in oq
    assert check_wiki(cfg, conn) == []

    fid = fact_id(conn)
    claude_verdicts(cfg, conn, [{"id": f"f{fid}:spec:0", "verdict": "approve"}])     # the spec publishes -> the step may cite it
    export(cfg, conn)
    page = page_text(cfg)
    assert "Torque the pivot bolts to 83 ft-lb" in page and "2.75" not in page
    assert check_wiki(cfg, conn) == []

    path = cfg.wiki_dir / "repair" / "control-arms-bushings.md"
    path.write_text(page.replace("## Tools", "## Tips & gotchas\n\n- Fill it with 6 qt first [t1]\n\n## Tools"))
    assert any("outside the specifications: 6 qt" in v for v in check_wiki(cfg, conn))
    # a spec-shaped line outside Specifications must not count as a published spec (and exempt itself)
    path.write_text(page.replace("## Tools", "## Tips & gotchas\n\n- **Torque**: 99 ft-lb [t1] (community-consensus, 2 threads)\n\n## Tools"))
    assert any("outside the specifications: 99 ft-lb" in v for v in check_wiki(cfg, conn))


def test_incomplete_procedure_is_withheld(cfg, conn, tmp_path):
    add_notes(cfg, conn, tmp_path, [("a", NOTE_A, "alice")])
    extract_and_verify(cfg, conn, [("83 ft-lb", {"relevant": True, "facts": [arm_fact(parts=[], diagram_links=[], specs=[])]})],
                       verifier=FakeVerifier(cfg, partial=("whole procedure",)))
    export(cfg, conn)
    assert "## Procedure" not in page_text(cfg) and "Final-tighten" in page_text(cfg)       # every step supported, list incomplete
    assert "completeness (procedure withheld)" in (cfg.wiki_dir / "open_questions.md").read_text()


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
    assert "| Frontier" not in (cfg.wiki_dir / "interchange.md").read_text()
    oq = (cfg.wiki_dir / "open_questions.md").read_text()
    assert "applicability" in oq and "shared platform" in oq


def test_curated_pages_survive_export_and_every_number_cites_a_source(cfg, conn):
    from xw.qa import check_curated

    good = ("# 2009 Nissan Xterra\n\n| Item | 2009 |\n|---|---|\n| Engine oil with filter | 5-3/8 qt [S13] |\n\n"
            "- Back to [2008](2008.md) and the [hub](../index.md)\n- Solar Yellow offered in 2009 [Unverified]\n\n"
            "## Sources\n\n- [S13] Nissan, 2009 Xterra Owner's Manual. https://owners.nissanusa.com/x.pdf\n")
    page = cfg.wiki_dir / "encyclopedia" / "years" / "2009.md"
    page.parent.mkdir(parents=True)
    page.write_text(good)
    (cfg.wiki_dir / "encyclopedia" / "index.md").write_text("# Hub\n\n- [2009](years/2009.md)\n\n## Sources\n")
    export(cfg, conn)
    assert page.read_text() == good                       # not a topic category: export never deletes or rewrites it
    assert "](encyclopedia/index.md)" in (cfg.wiki_dir / "index.md").read_text()
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
