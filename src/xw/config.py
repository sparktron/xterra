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
        "endpoint": "http://localhost:1234",
        "model": "qwen3.8-27b",
        "api_key_env": "XW_LLM_API_KEY",        # NAME of the environment variable holding the server's API key (never the key itself)
        "reasoning_effort": "none",             # none | low | medium | high | "" (leave to the server)
        "num_ctx": 16384,                       # ollama only; for LM Studio set the context length when loading the model
        "temperature": 0.1,
        "timeout_s": 900,
        "max_retries": 2,
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
    "scope": {"years": [2005, 2016]},
    # Nothing the local model says is trusted on its own. See README "Verification".
    "verify": {
        "require_local_pass": True,        # text claims publish only if the local verifier judged them "supported"
        "safety_min_threads": 2,           # safety-critical values need N agreeing threads, a manufacturer source, or a reviewer's approval
        "publish_unverified_safety": False,
        "verify_model": "",                # optional second model for the verifier pass (a different model catches different mistakes)
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
        self.sources = sources
        self.topics = topics

    @classmethod
    def load(cls, root: str | Path | None = None) -> "Config":
        root_path = find_root(root)
        cfg_dir = root_path / "config"
        raw = _merge(DEFAULTS, _read_yaml(cfg_dir / "settings.yaml"))
        raw = _merge(raw, _read_yaml(cfg_dir / "settings.local.yaml"))
        sources = (_read_yaml(cfg_dir / "sources.yaml").get("sources")) or []
        topics = (_read_yaml(cfg_dir / "topics.yaml").get("categories")) or {}
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
