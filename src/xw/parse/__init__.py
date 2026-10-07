"""Site adapters. Each adapter module exposes parse_forum(html, url) and parse_thread(html, url)."""
from __future__ import annotations

from types import ModuleType

from . import generic, xenforo


ADAPTERS: dict[str, ModuleType] = {"xenforo": xenforo, "generic": generic}


def get_adapter(name: str) -> ModuleType:
    try:
        return ADAPTERS[name]
    except KeyError:
        raise ValueError(f"unknown adapter {name!r}; available: {sorted(ADAPTERS)}") from None
