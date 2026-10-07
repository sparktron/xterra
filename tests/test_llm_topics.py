import json

import httpx
import pytest

from xw.llm import LLM, LLMError, parse_json_loose
from xw.schemas import Extraction, extraction_schema
from xw.topics import TopicIndex, slugify


def test_parse_json_loose():
    assert parse_json_loose('{"a": 1}') == {"a": 1}
    assert parse_json_loose('<think>hmm</think>\n```json\n{"a": 2}\n```') == {"a": 2}
    assert parse_json_loose('Sure! {"a": 3} hope that helps') == {"a": 3}
    for bad in ("no json here", "[1, 2]", '{"a": '):
        with pytest.raises(LLMError):
            parse_json_loose(bad)


def _llm(cfg, handler, provider="ollama"):
    if provider:  # these tests exercise Ollama's native shape unless a test passes provider=None and sets its own config
        cfg.llm.as_dict().update({"provider": provider, "endpoint": "http://localhost:11434"})
    return LLM(cfg, client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_ollama_request_shape_and_response(cfg):
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"message": {"content": '{"relevant": false, "facts": []}'}})

    out = _llm(cfg, handler).chat_json("sys", "user", {"type": "object"})
    assert out == {"relevant": False, "facts": []}
    assert seen["url"].endswith("/api/chat")
    body = seen["body"]
    assert body["format"] == {"type": "object"} and body["think"] is False and body["stream"] is False
    assert body["options"]["num_ctx"] == cfg.llm.num_ctx


def test_retry_on_invalid_json_then_success(cfg):
    replies = iter(["not json", '{"relevant": true, "facts": []}'])

    def handler(req):
        return httpx.Response(200, json={"message": {"content": next(replies)}})

    assert _llm(cfg, handler).chat_json("s", "u", None)["relevant"] is True


def test_gives_up_after_retries(cfg):
    def handler(req):
        return httpx.Response(200, json={"message": {"content": "garbage"}})

    with pytest.raises(LLMError):
        _llm(cfg, handler).chat_json("s", "u", None)


def test_server_down_is_llm_error(cfg):
    def handler(req):
        raise httpx.ConnectError("refused")

    with pytest.raises(LLMError, match="LLM server error"):
        _llm(cfg, handler).chat_json("s", "u", None)


def test_openai_backend_falls_back_when_json_schema_unsupported(cfg):
    cfg.llm.as_dict().update({"provider": "lmstudio", "endpoint": "http://x.invalid", "reasoning_effort": ""})
    formats = []

    def handler(req):
        body = json.loads(req.content)
        formats.append(body["response_format"]["type"])
        if body["response_format"]["type"] == "json_schema":
            return httpx.Response(400, json={"error": "unsupported"})
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}]})

    assert _llm(cfg, handler, provider=None).chat_json("s", "u", {"type": "object"}) == {"ok": True}
    assert formats == ["json_schema", "json_object"]


def test_list_models(cfg):
    llm = _llm(cfg, lambda req: httpx.Response(200, json={"models": [{"name": "a:1"}, {"name": "b:2"}]}))
    assert llm.list_models() == ["a:1", "b:2"]


def test_schema_is_flat_and_valid():
    schema = extraction_schema()
    text = json.dumps(schema)
    assert "$ref" not in text and "$defs" not in text
    assert schema["type"] == "object" and "facts" in schema["properties"]
    ex = Extraction.model_validate({"relevant": True, "facts": [{"category": "repair", "topic": "t", "title": "x", "years": [2008, "2010", "bad", 1850], "difficulty": 9}]})
    assert ex.facts[0].years == [2008, 2010] and ex.facts[0].difficulty == 5


def test_topic_resolution(cfg):
    topics = TopicIndex(cfg.topics)
    assert topics.resolve("Engine oil and filter change", "maintenance").slug == "engine-oil-change"   # exact title
    assert topics.resolve("oil change", "maintenance").slug == "engine-oil-change"                    # alias
    assert topics.resolve("How to change ATF (pan drop)", "maintenance").slug == "atf-change"          # fuzzy via alias
    new = topics.resolve("Rear locker cable adjustment", "mods")
    assert not new.seeded and new.slug == "rear-locker-cable-adjustment"
    assert topics.resolve("Rear locker cable adjustment", "mods") is new                               # stable on repeat
    assert topics.resolve("Engine oil and filter change", "repair").slug != "engine-oil-change"        # categories stay separate
    assert slugify("  Weird / Title!! ") == "weird-title"


def test_lmstudio_endpoint_gets_v1_and_effort_is_sent_then_dropped_on_400(cfg):
    from xw.llm import base_url
    assert base_url("lmstudio", "http://127.0.0.1:42117") == "http://127.0.0.1:42117/v1"
    assert base_url("lmstudio", "http://127.0.0.1:42117/v1/") == "http://127.0.0.1:42117/v1"
    assert base_url("ollama", "http://localhost:11434") == "http://localhost:11434"
    seen = []

    def handler(req):
        body = json.loads(req.content)
        seen.append((req.url.path, body.get("reasoning_effort")))
        if "reasoning_effort" in body:
            return httpx.Response(400, json={"error": "unknown field"})
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}]})

    assert _llm(cfg, handler, provider=None).chat_json("s", "u", None) == {"ok": True}      # defaults: lmstudio, effort "none"
    assert seen == [("/v1/chat/completions", "none"), ("/v1/chat/completions", None)]


def test_unknown_provider_is_rejected(cfg):
    cfg.llm.as_dict()["provider"] = "bogus"
    with pytest.raises(LLMError, match="unknown llm.provider"):
        LLM(cfg, client=httpx.Client())
