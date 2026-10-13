"""The extractor only fills the fields its prompt and schema ask for.

A live run once stored 238 facts with 2 procedures and no summaries, because the prompt never told the
model to fill `steps` or `summary`; the pages published as a title and a forum link. A fake model cannot
catch that, so pin the instructions themselves. Real extraction still needs `xw doctor` and a sample thread.
"""
from pathlib import Path

from xw.schemas import extraction_schema

PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "extract.md").read_text(encoding="utf-8")


def test_prompt_tells_the_model_to_fill_steps_and_summary():
    for field in ("steps", "summary", "tips", "symptoms"):
        assert f"`{field}`" in PROMPT, field
    assert "EVERY step" in PROMPT and "ONE fact" in PROMPT


def test_schema_describes_steps_and_summary_to_the_model():
    fact = extraction_schema()["properties"]["facts"]["items"]["properties"]
    assert "every step" in fact["steps"]["description"].lower()
    assert fact["summary"]["description"]


# --- retry on an early-stopped procedure, and the separate summary call ---------------------------------------
from xw.extract import extract_chunk, fill_summary, numbered_steps
from xw.llm import LLMError
from xw.schemas import Fact

SRC = "THREAD: Reset\n\n1. Turn the key to ON.\n\n2. When it blinks, turn it off.\n\n3. Repeat 3 times.\n\n4. The light should stay off."


class _Scripted:
    """LLM stand-in that answers each chat_json call from a queue."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), 0

    def chat_json(self, system, user, schema=None):
        self.calls += 1
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _facts(n):
    return {"relevant": True, "facts": [{"category": "diagnostics", "topic": "Reset", "title": "Reset the light", "steps": [f"step {i}" for i in range(n)]}]}


def test_numbered_steps_counts_the_sources_own_numbering():
    assert numbered_steps(SRC) == 4
    assert numbered_steps("1. one\n3. three") == 1 and numbered_steps("no list here") == 0
    assert numbered_steps("1) a\n2) b") == 2


def test_early_stopped_procedure_is_retried_and_the_longest_run_kept():
    llm = _Scripted(_facts(2), _facts(4))
    res = extract_chunk(llm, "sys", {}, "src", "Reset", SRC)
    assert len(res.facts[0].steps) == 4 and llm.calls == 2


def test_retries_are_bounded_and_failures_do_not_lose_the_first_result():
    llm = _Scripted(_facts(2), LLMError("bad json"), _facts(3))
    res = extract_chunk(llm, "sys", {}, "src", "Reset", SRC)
    assert len(res.facts[0].steps) == 3 and llm.calls == 3          # one initial + two retries, never more
    llm = _Scripted(_facts(4))
    assert extract_chunk(llm, "sys", {}, "src", "Reset", SRC).facts[0].steps and llm.calls == 1   # complete: no retry
    llm = _Scripted(_facts(2))
    assert extract_chunk(llm, "sys", {}, "src", "Reset", "no numbered list at all " * 5).facts and llm.calls == 1


def test_summary_is_written_from_the_extracted_fact_and_never_overwrites():
    fact = Fact(category="diagnostics", topic="Reset", title="Reset the light", steps=["Turn the key to ON"])
    fill_summary(_Scripted({"summary": "  Resets   the light.  "}), fact)
    assert fact.summary == "Resets the light."
    fill_summary(_Scripted(AssertionError("must not be called")), fact)      # already has one
    empty = Fact(category="diagnostics", topic="Reset", title="Reset the light")
    fill_summary(_Scripted(AssertionError("must not be called")), empty)     # nothing to summarise from
    assert empty.summary == ""
    fill_summary(_Scripted(LLMError("down")), Fact(category="diagnostics", topic="x", title="y", steps=["a"]))   # best effort


def test_every_chat_request_caps_the_output_length(cfg):
    import httpx

    from xw.llm import LLM

    seen = []

    def handler(request):
        seen.append(__import__("json").loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    llm = LLM(cfg, client=httpx.Client(transport=httpx.MockTransport(handler)))
    llm.chat_json("sys", "user", {"type": "object"})
    assert seen and seen[0]["max_tokens"] == cfg.llm.max_output_tokens == 8192


def test_resummarize_rewrites_summaries_and_drops_only_their_verdicts(cfg, conn):
    from xw.extract import resummarize

    fact = Fact(category="diagnostics", topic="Reset", title="Reset the light", steps=["Turn the key to ON"], summary="Old.")
    sid = conn.execute("SELECT id FROM sources LIMIT 1").fetchone()
    assert sid is not None, "the conn fixture seeds sources"
    tid = conn.execute("INSERT INTO threads(source_id, url, title, status) VALUES(?,?,?,?)", (sid[0], "http://x.invalid/t", "T", "extracted")).lastrowid
    cid = conn.execute("INSERT INTO chunks(thread_id, idx, text, status) VALUES(?,?,?,?)", (tid, 0, "Turn the key to ON.", "done")).lastrowid
    fid = conn.execute("INSERT INTO facts(thread_id, chunk_id, fact_json, grounding_json, created_at) VALUES(?,?,?,?,?)",
                       (tid, cid, fact.model_dump_json(), "{}", "")).lastrowid
    for key in ("summary", "step:0"):
        conn.execute("INSERT INTO verdicts(fact_id, claim_key, by, verdict, created_at) VALUES(?,?,?,?,?)", (fid, key, "local", "supported", ""))
    conn.commit()
    assert resummarize(conn, _Scripted(AssertionError("must not run")), redo=False) == 0          # has a summary: untouched
    assert resummarize(conn, _Scripted({"summary": "Turns the key to ON."}), redo=True) == 1
    new = Fact.model_validate_json(conn.execute("SELECT fact_json FROM facts WHERE id=?", (fid,)).fetchone()[0])
    assert new.summary == "Turns the key to ON."
    keys = {r[0] for r in conn.execute("SELECT claim_key FROM verdicts WHERE fact_id=?", (fid,))}
    assert keys == {"step:0"}                                                                      # the summary verdict is stale
    assert resummarize(conn, _Scripted({"summary": ""}), redo=True) == 0                           # an empty answer keeps the old one
    assert Fact.model_validate_json(conn.execute("SELECT fact_json FROM facts WHERE id=?", (fid,)).fetchone()[0]).summary == new.summary


def test_a_reply_from_a_different_model_than_requested_is_refused(cfg):
    import httpx

    from xw.llm import LLM

    def answer(model):
        def handler(request):
            return httpx.Response(200, json={"model": model, "choices": [{"message": {"content": "{}"}}]})
        return httpx.Client(transport=httpx.MockTransport(handler))

    llm = LLM(cfg, model="big-model", client=answer("small-model"))
    try:
        llm.chat_json("s", "u", {"type": "object"})
    except LLMError as exc:
        assert "small-model" in str(exc) and "big-model" in str(exc)
    else:
        raise AssertionError("a swapped model must not be accepted")
    assert LLM(cfg, model="big-model", client=answer("big-model")).chat_json("s", "u", {"type": "object"}) == {}
