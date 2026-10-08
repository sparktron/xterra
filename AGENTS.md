# xterra wiki pipeline

Local-LLM pipeline (`xw`) that builds a wiki on 2nd-gen Nissan Xterra / Frontier / Titan work from forum threads.

- Setup: `scripts/bootstrap.sh`. Run: `scripts/run_all.sh`. Tests: `pytest -q`.
- Published facts must be grounded in source text. Do not loosen `grounding.py`, `export.gate` or `qa.py` without a test showing why.
- `wiki/` pages with the generated header are overwritten by `xw export`; never hand-edit them.
- Mark unverified claims `[Unverified]`. Do not commit `data/` or secrets.

## Architecture

`xw` (`src/xw/`) is a resumable pipeline whose state lives in SQLite (`data/xw.sqlite`) and whose output is
markdown in `wiki/`. Stages, each re-runnable: `discover`/`harvest` (polite fetch of forum threads into a
raw cache) or `ingest` (pages you saved yourself) → `extract` (local LLM turns chunks into structured facts)
→ `verify` (a second local-LLM pass) → `export` (policy gate, render pages) → `qa` (re-check the published
pages against raw source text). `xw run` chains crawl, extract and verify per source; `export` and `qa` are
separate. A source that blocks is marked `blocked` and skipped; the run continues. The optional Claude review
(`review-export` → `wiki-reviewer` agent → `review-apply`) feeds verdicts back into the gate.
The README's Verification section is the design statement; this file holds what must not be broken.

## Important invariants

The local model is not trusted. Each item names the guarding test, or says none exists.

- **Fail closed.** A claim publishes only if the verifier said `supported` (or a reviewer approved it).
  `verify.require_local_pass` must stay true; a missing verifier run publishes nothing.
  Tests: `test_fails_closed_when_verifier_has_not_run`, `test_verifier_disagreement_withholds_claims_and_whole_procedures`.
- **Procedures publish all-or-nothing.** One unsupported step withholds the whole procedure.
- **Grounding means "appears in the source", not "is correct".** Numbers, part numbers, DTCs and links must
  appear in the chunk; spec/part `evidence` must be a real quote (`grounding.evidence_in_text`).
  `ground_fact` returns lists index-aligned with the fact's lists; a new list field on `Fact` needs a matching
  entry. Tests: `tests/test_grounding.py`.
- **Safety classification is deterministic.** `export.is_safety` (torque, capacities, pressure, preload) never
  relies on the model's `safety_critical` flag, which defaults to false.
  Test: `test_non_torque_safety_values_are_classified_deterministically`.
- **Single-source safety values are withheld** (`verify.safety_min_threads: 2`, a manufacturer source, or a
  reviewer's approval); disputed values are withheld. Tests: `test_single_source_safety_value_is_withheld_until_reviewed`,
  `test_agreeing_threads_are_consensus_and_disputes_are_withheld`.
- **Everything published must have been verified.** `verify.claims_for_fact` must list every field the exporter
  prints (part notes and DTC causes/tests/fix included). Add a published field, add its claim.
  Tests: `test_verifier_sees_part_notes_and_dtc_advice`, `test_unverified_dtc_advice_is_not_published`.
- **No verbatim copying.** Text sharing a 12-word run with the source is dropped (`has_long_overlap`); the wiki
  paraphrases. Test: `test_copied_text_and_unstated_metadata_are_not_published`.
- **`qa.py` is coupled to the page format.** Its `SPEC_LINE`/`PART_LINE` regexes parse what `export.render_page`
  writes, and an unparseable line is a violation. Change one, change the other. Test: `test_qa_catches_tampering`.
- **The `GENERATED` first line is load-bearing.** `export` overwrites pages that carry it and `qa` checks only those.
  Removing it from a page hides that page from `qa`. No test covers hand-editing.
- **Blocks are never worked around.** 401/402/403 (`crawl.stop_statuses`), repeated 429, off-site redirects and
  challenge pages mark the source blocked; no retry, header spoofing, proxy, mirror or cache. Tests: `tests/test_fetch.py`.
- **Wiki scope years (`scope.years: [2005, 2016]`) are `[Unverified]`.** Out-of-scope years are dropped
  (`test_out_of_scope_years_are_dropped`); do not tighten the range without a source.
- **Reviewer instructions exist in three copies**: `.claude/agents/wiki-reviewer.md`, `.codex/agents/wiki-reviewer.toml`
  and `.agents/skills/source-command-review-wiki/`. Edit them together. No test covers drift.

## Repository layout

| Path | Role |
|---|---|
| `src/xw/` | Pipeline: `fetch`, `crawl`, `parse/`, `extract`, `grounding`, `verify`, `export`, `review`, `qa`, `llm`, `db`, `cli` |
| `config/` | `settings.yaml`, `sources.yaml` (ranked sources), `topics.yaml` (seed page tree); `settings.local.yaml` is gitignored |
| `prompts/` | `extract.md` and `verify.md`, the LLM system prompts |
| `tests/` | Offline suite with HTML fixtures; no network or LLM server needed |
| `wiki/` | Generated output; pages with the `GENERATED` header are overwritten by `xw export` |
| `data/` | SQLite state and raw page cache. Gitignored; holds other people's posts |
| `.claude/`, `.codex/`, `.agents/` | `/review-wiki` command and `wiki-reviewer` agent, per tool |

## Build commands

```bash
scripts/bootstrap.sh     # venv, pip install -e ".[dev]", xw init, pytest, xw doctor
scripts/run_all.sh       # xw doctor, run, export, qa
```

## Test commands

```bash
.venv/bin/pytest         # the gate; there is no CI in this repo
.venv/bin/xw qa          # exit 1 if a published page violates the grounding rules
```

## Validation requirements

The suite is offline and does not exercise a real LLM or a live forum. A change to `llm.py`, a prompt, or a parser
is not validated until `xw doctor` passes against the local server and a sample thread has been run through
`xw ingest` then `xw verify`. After any export-affecting change run `xw export && xw qa`. Dependencies are floors
with no ceiling (`httpx>=0.27`, `pydantic>=2.6`, `lxml>=5.0`, `beautifulsoup4>=4.12`); the suite passed at the
floors and at current releases on 2026-10-07 (see `docs/STATUS.md`).

## Cross-repository contracts

None. This repo is standalone. The internal contracts are the `data/review/batch-*.json` format written by
`review.py` and read by the reviewer agents, and the `{"verdicts": [...]}` file they write back.

## Security / safety constraints

- Never commit `data/`, `config/settings.local.yaml` or `.env`. The LLM API key is read from the environment
  variable named by `llm.api_key_env`; the key itself never goes in a file.
- Set `crawl.contact` before crawling; the User-Agent must stay honest. Do not disable `respect_robots` for a site
  that asks not to be crawled.
- Torque, fluid-capacity and part-number claims drive real repairs. Do not loosen `grounding.py`, `export.gate` or
  `qa.py` without a test showing why.
- Review batches send only a claim and a short excerpt to Claude, and only when you run the review step.
- Forum text is others' content: publish paraphrased facts with source links, not copies.

## Definition of done

- `pytest` passes; `xw export && xw qa` passes if output or the gate changed.
- A new published field is covered by grounding, by `claims_for_fact`, and by `qa` where it is a value.
- `docs/STATUS.md` updated, including what was not run.
- Nothing from `data/` or `wiki/` hand-edits is committed by accident.

## Where to find deeper context

| Topic | Document |
|---|---|
| Current state | `docs/STATUS.md` |
| Design and verification layers | `README.md` |
| Settings and their meaning | `config/settings.yaml` (commented) |
| Source list and trust ranks | `config/sources.yaml` |
