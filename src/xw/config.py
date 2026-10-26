"""Configuration: settings.yaml (+ optional settings.local.yaml), sources.yaml, topics.yaml."""
from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "paths": {"data_dir": "data", "wiki_dir": "wiki"},
    "llm": {
        "provider": "lmstudio",                 # lmstudio | openai (any OpenAI-compatible server) | ollama
        "endpoint": "http://localhost:1235",
        "model": "qwen3.8-27b",
        "api_key_env": "XW_LLM_API_KEY",        # NAME of the environment variable holding the server's API key (never the key itself)
        "reasoning_effort": "none",             # none | low | medium | high | "" (leave to the server)
        "num_ctx": 24576,                       # ollama only; for LM Studio set the context length when loading the model
        "temperature": 0.1,
        "timeout_s": 900,
        "max_retries": 2,
        "max_output_tokens": 12288,
    },
    "crawl": {
        "user_agent": "xterra-wiki-research/0.1",
        "contact": "",
        "min_delay_s": 4.0,
        "jitter_s": 2.0,
        "timeout_s": 30,
        "max_thread_pages": 15,
        "max_forum_pages": 5,
        "max_forum_depth": 3,
        "max_fetches_per_source": 150,
        "max_fetches_primary": 400,
        "respect_robots": True,
        "stop_statuses": [401, 402, 403],
        "max_consecutive_429": 3,
        "min_post_chars": 60,
    },
    "extract": {"max_chunk_chars": 14000, "min_chunk_chars": 400, "max_consecutive_failures": 5},
    "scope": {"years": [2000, 2016]},
    # The wiki has one completely separate section per generation (the user, 2026-10-20: "They are nothing alike").
    # A fact goes to the generation its stated model years fall in, else to its source's `generation`; one that spans
    # two generations, or has neither, publishes in none. `markers` name a generation: a claim on another
    # generation's page that matches them is withheld (export) and refused (qa).
    "generations": {
        "first-gen": {
            "title": "First generation (WD22), 2000-2004",
            "years": [2000, 2004],
            "prompt_vehicle": "first-generation Nissan Xterra (WD22, model years 2000-2004)",
            "prompt_offtopic": "second-generation Xterra 2005-2015",
            "markers": [r"\b(1st|first)[\s-]*gen(eration)?s?\b", r"\bgen[\s-]*(1|i|one)\b", r"\bwd22\b", r"\bd22\b",
                        r"\bka24(de)?\b", r"\bvg33(e|er)?\b", r"\b(2000|00)\s*[-–]\s*(2004|04)\b"],
        },
        "second-gen": {
            "title": "Second generation (N50), 2005-2015",
            "years": [2005, 2016],
            "prompt_vehicle": "second-generation Nissan Xterra (N50, about model years 2005-2015)",
            "prompt_offtopic": "first-generation Xterra 1999-2004",
            "markers": [r"\b(2nd|second)[\s-]*gen(eration)?s?\b", r"\bgen[\s-]*(2|ii|two)\b", r"\bn50\b", r"\bd40\b",
                        r"\bvq40(de)?\b", r"\b2005\s*[-–]\s*(2015|2016|15|16)\b", r"\b2005\+"],
        },
    },
    # Nothing the local model says is trusted on its own. See README "Verification".
    "verify": {
        "require_local_pass": True,        # text claims publish only if the local verifier judged them "supported" (or "partial", below)
        "publish_partial": True,           # a "partial" verdict publishes the claim marked [Partial] (needs more work; still queued)
        "safety_min_threads": 2,           # safety-critical values need N agreeing threads, a manufacturer source, or a reviewer's approval
        "publish_unverified_safety": True,   # an unconfirmed torque/capacity/pressure value publishes marked; still queued
        "verify_model": "",                # optional second model for the verifier pass (a different model catches different mistakes)
        "consensus_runs": 2,               # run the verifier this many times; a claim is "supported" only if every run said so
    },
    "review": {"audit_rate": 0.1, "batch_size": 25, "excerpt_chars": 900},
}


class Section:
    """Attribute access over a settings dict."""

    def __init__(self, data: dict[str, Any]):
        object.__setattr__(self, "_d", data)

    def __getattr__(self, key: str) -> Any:
        try:
            return self._d[key]
        except KeyError:
            raise AttributeError(key) from None

    def get(self, key: str, default: Any = None) -> Any:
        return self._d.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        return self._d


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def find_root(explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("XW_ROOT")
    if env:
        return Path(env).resolve()
    cwd = Path.cwd()
    if (cwd / "config" / "settings.yaml").exists():
        return cwd
    return Path(__file__).resolve().parents[2]


class Config:
    def __init__(self, root: Path, raw: dict[str, Any], sources: list[dict[str, Any]], topics: dict[str, Any]):
        self.root = root
        self.raw = raw
        self.paths = Section(raw["paths"])
        self.llm = Section(raw["llm"])
        self.crawl = Section(raw["crawl"])
        self.extract = Section(raw["extract"])
        self.scope = Section(raw["scope"])
        self.verify = Section(raw["verify"])
        self.review = Section(raw["review"])
        self.generations: dict[str, dict[str, Any]] = raw["generations"]
        self.sources = sources
        self.topics = topics   # {generation id: {"categories": {...}}}, from topics.yaml

    @classmethod
    def load(cls, root: str | Path | None = None) -> "Config":
        root_path = find_root(root)
        cfg_dir = root_path / "config"
        raw = _merge(DEFAULTS, _read_yaml(cfg_dir / "settings.yaml"))
        raw = _merge(raw, _read_yaml(cfg_dir / "settings.local.yaml"))
        sources = (_read_yaml(cfg_dir / "sources.yaml").get("sources")) or []
        tree = _read_yaml(cfg_dir / "topics.yaml")
        # one topic tree per generation; a legacy single tree (`categories:`) is the second generation's
        topics = tree.get("generations") or ({"second-gen": {"categories": tree["categories"]}} if tree.get("categories") else {})
        return cls(root_path, raw, sources, topics)

    @property
    def data_dir(self) -> Path:
        return self.root / self.paths.data_dir

    @property
    def wiki_dir(self) -> Path:
        return self.root / self.paths.wiki_dir

    @property
    def db_path(self) -> Path:
        return self.data_dir / "xw.sqlite"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
