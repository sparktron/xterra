from __future__ import annotations

import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    """A throwaway repo root with the real config and prompts, so tests never touch ./data or ./wiki."""
    shutil.copytree(REPO / "config", tmp_path / "config")
    shutil.copytree(REPO / "prompts", tmp_path / "prompts")
    (tmp_path / "config" / "settings.local.yaml").write_text(
        "crawl:\n  min_delay_s: 0\n  jitter_s: 0\n  contact: tests@example.invalid\n", encoding="utf-8"
    )
    return tmp_path


@pytest.fixture()
def cfg(root: Path):
    from xw.config import Config

    c = Config.load(root)
    c.ensure_dirs()
    return c


@pytest.fixture()
def conn(cfg):
    from xw import db

    c = db.connect(cfg.db_path)
    db.seed_sources(c, cfg.sources)
    return c
