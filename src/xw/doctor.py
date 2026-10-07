"""`xw doctor`: verify the local setup before a long run."""
from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Callable

import httpx

from .config import Config
from .llm import LLM, LLMError
from .schemas import extraction_schema

OK, WARN, FAIL = "ok  ", "warn", "FAIL"


def run(cfg: Config, *, smoke: bool = False, net: bool = False, out: Callable[[str], None] = print) -> int:
    problems = 0

    def line(level: str, msg: str) -> None:
        nonlocal problems
        if level == FAIL:
            problems += 1
        out(f"[{level}] {msg}")

    line(OK if sys.version_info >= (3, 10) else FAIL, f"python {sys.version.split()[0]} (need >= 3.10)")
    line(OK if (cfg.root / "prompts" / "extract.md").exists() else FAIL, "prompts/extract.md present")
    line(OK if cfg.sources else FAIL, f"{len(cfg.sources)} sources configured, {sum(1 for s in cfg.sources if s.get('enabled', True))} enabled")
    line(OK if cfg.topics else FAIL, f"{sum(len(c.get('topics', [])) for c in cfg.topics.values())} seed topics")
    if not cfg.crawl.contact:
        line(WARN, "crawl.contact is empty: set an email or URL in config/settings.local.yaml so site admins can reach you")
    else:
        line(OK, "crawl.contact set")

    if shutil.which("nvidia-smi"):
        try:
            res = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader"],
                                 capture_output=True, text=True, timeout=10)
            line(OK, f"GPU: {res.stdout.strip().splitlines()[0]}" if res.stdout.strip() else "nvidia-smi returned nothing")
        except (subprocess.SubprocessError, OSError) as exc:
            line(WARN, f"nvidia-smi failed: {exc}")
    else:
        line(WARN, "nvidia-smi not found (cannot report GPU memory)")

    llm = LLM(cfg)
    try:
        models = llm.list_models()
        line(OK, f"LLM server reachable at {cfg.llm.host} ({cfg.llm.backend}); {len(models)} model(s)")
        if cfg.llm.model in models:
            line(OK, f"model {cfg.llm.model!r} is available")
        else:
            near = [m for m in models if "qwen" in m.lower()] or models[:8]
            line(FAIL, f"model {cfg.llm.model!r} not found. Set llm.model in config/settings.local.yaml. Candidates: {near}")
    except (httpx.HTTPError, LLMError, KeyError, ValueError) as exc:
        line(FAIL, f"cannot reach the LLM server at {cfg.llm.host}: {type(exc).__name__}: {exc}. Is `ollama serve` running?")
        models = []

    if smoke and models:
        try:
            res = llm.chat_json(
                "Reply with JSON only.",
                'Return {"relevant": true, "facts": []}.',
                {"type": "object", "properties": {"relevant": {"type": "boolean"}, "facts": {"type": "array", "items": {"type": "object"}}},
                 "required": ["relevant", "facts"]},
            )
            line(OK, f"structured-output smoke test passed: {res}")
            extraction_schema()
            line(OK, "full extraction schema builds")
        except LLMError as exc:
            line(FAIL, f"smoke test failed: {exc}")

    if net:
        for s in cfg.sources:
            if not s.get("enabled", True) or not s.get("base_url"):
                continue
            try:
                r = httpx.get(s["base_url"], timeout=15, headers={"User-Agent": cfg.crawl.user_agent}, follow_redirects=False)
                level = OK if r.status_code == 200 else WARN
                line(level, f"{s['id']}: HTTP {r.status_code} from {s['base_url']}" + (" (bot wall?)" if r.status_code in cfg.crawl.stop_statuses else ""))
            except httpx.HTTPError as exc:
                line(WARN, f"{s['id']}: {type(exc).__name__}")

    out(f"\n{'all checks passed' if not problems else str(problems) + ' problem(s) need fixing'}")
    return 1 if problems else 0
