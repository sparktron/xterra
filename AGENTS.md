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
- **Every verifier call carries decoys.** `verify.make_decoy` plants one or two claims that state a number the source
  never states; a call that calls one `supported` is retried once, then its claims are stored as `decoy_failed` (withheld).
  `decoy_checks` records the rate (`xw status`). Tests: `test_verifier_that_accepts_decoys_is_discarded`,
  `test_decoys_are_false_by_construction_and_honest_verifier_passes`. Test fakes must reject claims whose numbers are
  not in the source, or every call is discarded.
- **Procedures publish all-or-nothing.** One unsupported step, or an unsupported `complete` claim (the list leaves
  nothing out), withholds the whole procedure. Test: `test_incomplete_procedure_is_withheld`.
- **Grounding means "appears in the source", not "is correct".** Numbers (in specs and in prose), part numbers,
  DTCs and links must appear in the chunk; spec/part `evidence` must be a real quote (`grounding.evidence_in_text`);
  a unit a spec gives must be the unit the quote puts on that number (`grounding.unit_grounded`).
  `ground_fact` returns lists index-aligned with the fact's lists; a new list field on `Fact` needs a matching
  entry. `export.load_rows` recomputes grounding from chunk text on every export (`facts.grounding_json` is not read),
  so a tightened rule applies to old facts. Tests: `tests/test_grounding.py`.
- **Safety classification is deterministic.** `export.is_safety` (torque, capacities, pressure, preload) never
  relies on the model's `safety_critical` flag, which defaults to false.
  Test: `test_non_torque_safety_values_are_classified_deterministically`.
- **Single-source safety values are withheld** (`verify.safety_min_threads: 2` threads with as many distinct
  authors, a manufacturer source, or a reviewer's approval); disputed values are withheld.
  Tests: `test_single_source_safety_value_is_withheld_until_reviewed`, `test_agreeing_threads_are_consensus_and_disputes_are_withheld`,
  `test_same_author_in_two_threads_is_not_consensus`.
- **A safety value in prose needs a published spec.** A torque, capacity or pressure value (`grounding.safety_values`)
  in a summary, step, tip, tool, part or DTC text publishes only if the same number and unit published as a spec on
  that page (DTC table: never); `qa` enforces it. Test: `test_safety_values_in_prose_need_a_published_spec`.
- **The review queue takes pending values from the exporter** (`export.pending_spec_keys`), so it counts
  corroboration exactly as the gate does. Test: `test_review_queue_counts_corroboration_like_the_exporter`.
- **Near-duplicate merging never merges different numbers** (`export._similar`). Test: `test_dedupe_keeps_disagreeing_numbers_apart`.
- **Everything published must have been verified.** `verify.claims_for_fact` must list every field the exporter
  prints: part notes, DTC causes/tests/fix, and the front matter and interchange metadata (`applies`: years, trims,
  engines, drivetrain; `platform`; `difficulty`; `time`). Add a published field, add its claim, and add its key to
  `review.CLAIM_KEY`. Tests: `test_verifier_sees_part_notes_and_dtc_advice`, `test_unverified_dtc_advice_is_not_published`,
  `test_applicability_and_interchange_need_their_own_verdict`.
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
