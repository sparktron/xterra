"""Local-LLM client: Ollama native API or any OpenAI-compatible server (llama.cpp, LM Studio, vLLM).

Both backends use schema-constrained output so the model can only emit JSON that matches the schema.
[Unverified] Behaviour details (the `think` flag, json_schema support) vary by server version; run
`xw doctor --smoke` against your server to confirm.
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from .config import Config


class LLMError(Exception):
    pass


_THINK = re.compile(r"<think>.*?</think>", re.S)


def parse_json_loose(text: str) -> dict[str, Any]:
    """Parse a JSON object from model output, tolerating think-tags and stray prose or code fences."""
    text = _THINK.sub("", text).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise LLMError(f"no JSON object in model output: {text[:200]!r}") from None
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"invalid JSON from model: {exc}") from exc
    if not isinstance(value, dict):
        raise LLMError("model returned JSON that is not an object")
    return value


class LLM:
    def __init__(self, cfg: Config, client: httpx.Client | None = None, model: str | None = None):
        self.c = cfg.llm
        self.model = model or self.c.model
        self.client = client or httpx.Client(timeout=self.c.timeout_s)
        self.base = self.c.host.rstrip("/")

    # -- discovery --------------------------------------------------------------------------
    def list_models(self) -> list[str]:
        if self.c.backend == "ollama":
            r = self.client.get(f"{self.base}/api/tags")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        r = self.client.get(f"{self.base}/models")
        r.raise_for_status()
        return [m["id"] for m in r.json().get("data", [])]

    # -- chat -------------------------------------------------------------------------------
    def _raw_chat(self, system: str, user: str, schema: dict[str, Any] | None) -> str:
        if self.c.backend == "ollama":
            body: dict[str, Any] = {
                "model": self.model,
                "stream": False,
                "keep_alive": "30m",
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "options": {"temperature": self.c.temperature, "num_ctx": self.c.num_ctx},
            }
            if schema is not None:
                body["format"] = schema
            if self.c.disable_thinking:
                body["think"] = False
            r = self.client.post(f"{self.base}/api/chat", json=body)
            r.raise_for_status()
            return r.json()["message"]["content"]

        user_msg = user + ("\n\n/no_think" if self.c.disable_thinking else "")
        body = {
            "model": self.model,
            "temperature": self.c.temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        }
        if self.c.disable_thinking:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        if schema is not None:
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "extraction", "schema": schema}}
        r = self.client.post(f"{self.base}/chat/completions", json=body)
        if r.status_code == 400 and schema is not None:  # server without json_schema support
            body["response_format"] = {"type": "json_object"}
            r = self.client.post(f"{self.base}/chat/completions", json=body)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def chat_json(self, system: str, user: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return a parsed JSON object; retry with a repair note when the output is not valid JSON."""
        last: Exception | None = None
        prompt = user
        for _ in range(self.c.max_retries + 1):
            try:
                return parse_json_loose(self._raw_chat(system, prompt, schema))
            except LLMError as exc:
                last = exc
                prompt = user + "\n\nYour previous reply was not valid JSON. Reply with ONLY one JSON object that matches the schema."
            except httpx.HTTPError as exc:
                raise LLMError(f"LLM server error: {type(exc).__name__}: {exc}") from exc
        raise LLMError(str(last))
