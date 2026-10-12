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
