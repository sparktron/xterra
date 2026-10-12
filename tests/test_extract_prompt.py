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
