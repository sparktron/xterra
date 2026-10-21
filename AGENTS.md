# xterra wiki pipeline

Local-LLM pipeline (`xw`) that builds a wiki on Nissan Xterra (first and second generation, in separate sections) / Frontier / Titan work from forum threads.

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

- **Nothing unconfirmed publishes unmarked.** A claim publishes if the verifier said `supported` or a reviewer approved it,
  or (decided 2026-10-16, `verify.publish_partial`, default on) the verifier said `partial`: then it carries a visible
  `[Partial]` mark ("needs more work", `export.PARTIAL`), the page says so, and the claim stays in the review/triage
  queues so a later verify, review or source drops the mark. `unsupported`, `decoy_failed`, a missing verifier run and a
  reviewer's `reject`/`needs_human` still publish nothing. `verify.require_local_pass` must stay true. Setting
  `publish_partial` and `publish_unverified_safety` to false restores the fail-closed policy (`strict` in the tests).
  Tests: `test_fails_closed_when_verifier_has_not_run`, `test_verifier_disagreement_withholds_claims_and_whole_procedures`,
  `test_a_partial_claim_publishes_flagged_and_loses_the_flag_once_confirmed`, `test_publish_partial_off_restores_fail_closed`.
- **`supported` needs every verifier pass to agree** (`verify.consensus_runs`, default 2; `verify.consensus`). Tests: `test_two_passes_must_agree_before_a_claim_is_supported`, `test_a_decoy_failure_in_either_pass_withholds_the_claim`. `tests/conftest.py` pins the other tests to one pass so their verifier call counts stay meaningful.
- **A human answer outranks every model and persists.** `xw triage` stores `human` verdicts (`triage.decide`) and a content-keyed copy in
  `human_decisions` (thread + claim kind + normalised claim text); `triage.reapply_decisions` runs in verify, export and triage, so a
  decision follows its claim across re-extraction and `verify --redo`, and a reworded claim is new and undecided. A human cannot publish what
  the deterministic evidence checks refuse: those claims are never queued and `export` drops them before the gate. Approving a safety value
  publishes it without a second source (the prompt says so). Tests: `test_a_human_decision_follows_its_claim_across_a_reextraction_and_a_redo`,
  `test_triage_never_shows_what_the_evidence_checks_already_refuse`, `test_triage_warns_before_a_single_source_safety_value_is_approved`.
- **A verdict is only as good as the passes and the text behind it.** Each local verdict records its pass count (`verdict_runs`; no row = one pass),
  so raising `verify.consensus_runs` makes a plain `xw verify` re-judge older claims. A review verdict applies only to the claim text it judged
  (`review.apply_reviews` compares the batch's claim with the current one and skips stale ones; `export_review` re-queues a changed claim), so
  `summarize --redo` cannot inherit an old approval. Tests: `test_raising_consensus_runs_re_judges_claims_that_only_had_one_pass`,
  `test_a_review_verdict_for_a_claim_that_was_rewritten_is_not_applied`.
- **Every verifier call carries decoys.** `verify.make_decoy` plants one or two claims that state a number the source
  never states; a call that calls one `supported` is retried once, then its claims are stored as `decoy_failed` (withheld).
  `decoy_checks` records the rate (`xw status`). Tests: `test_verifier_that_accepts_decoys_is_discarded`,
  `test_decoys_are_false_by_construction_and_honest_verifier_passes`. Test fakes must reject claims whose numbers are
  not in the source, or every call is discarded.
- **A procedure publishes only with every step publishable.** One unsupported or withheld step, or an `unsupported` or
  reviewer-`reject`ed `complete` claim (reject = a listed step is not in the source), withholds the whole procedure. A step the
  verifier only partly supports is shown with `[Partial]` before it; if any step is partial, or the list only *may* leave
  something out (local verifier `partial`, or a reviewer's `needs_human` on `complete`), the procedure carries `export.PARTIAL_NOTE`,
  sorts after complete procedures, and loses the mark on the next export once a verify or review upgrades the verdict.
  Tests: `test_partial_procedure_publishes_marked_partial_until_upgraded`,
  `test_unsupported_or_rejected_completeness_still_withholds_the_procedure`, `test_partial_never_rescues_an_unsupported_step`.
- **Grounding means "appears in the source", not "is correct".** Numbers (in specs and in prose), part numbers,
  DTCs and links must appear in the chunk, and a unit a spec gives must be the unit the chunk puts on that number
  (`grounding.spec_value_grounded`, `unit_grounded`). Only the value needs to be correct (decided 2026-10-16): the
  model's `evidence` quote is not a gate, it only helps the verifier and reviewer find the value
  (`test_a_value_needs_to_be_in_the_source_not_the_models_quote`,
  `test_a_value_with_a_paraphrased_or_missing_quote_publishes_and_a_wrong_value_does_not`).
  `ground_fact` returns lists index-aligned with the fact's lists; a new list field on `Fact` needs a matching
  entry. `export.load_rows` recomputes grounding from chunk text on every export (`facts.grounding_json` is not read),
  so a tightened rule applies to old facts. Tests: `tests/test_grounding.py`.
- **Safety classification is deterministic.** `export.is_safety` (torque, capacities, pressure, preload) never
  relies on the model's `safety_critical` flag, which defaults to false. `grounding.safety_values` does not read an
  engine's displacement ("VQ40DE 4.0L", "Ford 4.6L", "5.3L V8") as a fluid volume, or a part named "bar" before a
  number ("frame bar: 42"") as a pressure; a volume or pressure next to an engine name still counts.
  Tests: `test_non_torque_safety_values_are_classified_deterministically`,
  `test_a_swap_engine_name_or_a_part_called_bar_is_not_a_safety_value`.
- **An unconfirmed safety value publishes only marked, and keeps being re-checked.** Confirmed means
  `verify.safety_min_threads` (2) threads with as many distinct authors, a manufacturer source, or a reviewer's approval.
  Decided 2026-10-16 (`verify.publish_unverified_safety`, default on): an unconfirmed torque/capacity/pressure value
  publishes with `[Unverified]` or `[Partial]` in its spec tag under `export.SAFETY_NOTE`, prose repeating it carries
  `[Unverified value]`, `pending_verification.md` lists it, and the review queue keeps it at priority 0. With the setting
  off it is withheld. Disputed safety values are always withheld. `qa` refuses an unconfirmed safety spec without a mark
  and the banner, and an unconfirmed value repeated in prose without `[Unverified value]`.
  Tests: `test_an_unconfirmed_safety_value_publishes_marked_and_is_rechecked`,
  `test_a_partial_safety_value_publishes_marked_and_a_partial_never_beats_a_firmer_no`,
  `test_consensus_below_a_raised_safety_threshold_is_marked_unverified` (qa also refuses a `community-consensus` tag
  with fewer threads than `safety_min_threads`),
  `test_single_source_safety_value_is_withheld_until_reviewed` (strict), `test_agreeing_threads_are_consensus_and_disputes_are_withheld`,
  `test_same_author_in_two_threads_is_not_consensus`.
- **A safety value in prose is backed by a spec or marked.** A torque, capacity or pressure value (`grounding.safety_values`)
  in a summary, step, tip, tool or part text publishes if the same number and unit published as a spec on that page (marked
  `[Unverified value]` when that spec is unconfirmed), or, with `publish_unverified_safety`, if the source puts that unit
  on that number (`unit_grounded`); then it is marked `[Unverified value]` and queued at priority 0. The DTC table never
  carries one. `qa` enforces it. Tests: `test_safety_values_in_prose_need_a_published_spec` (strict),
  `test_a_safety_value_in_prose_without_a_spec_needs_its_unit_in_the_source_and_a_mark`, `test_a_part_note_with_an_unconfirmed_volume_is_marked`.
- **The review queue takes pending and unconfirmed values from the exporter** (`export.pending_spec_keys`), so it counts
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
- **Wiki scope years (`scope.years: [2000, 2016]`) are `[Unverified]`.** Facts stating only years outside it are dropped
  (`test_out_of_scope_years_are_dropped`); do not tighten the range without a source.
- **Each generation is a completely separate section** (decided 2026-10-20: the first-gen WD22 and second-gen N50 "are
  nothing alike"). `generations.route` sends a fact to the generation of its stated years, else its source's
  `generation` (sources.yaml); years in two generations, no generation at all, or a fact title naming another
  generation publish nowhere (top-level `open_questions.md`). Export writes `wiki/<generation>/...` with its own index,
  topic tree (`topics.yaml` `generations:`) and supporting files, and withholds any claim that names another generation
  (`config.DEFAULTS["generations"]` markers); corroboration and the review queue are per generation. `qa` re-derives the
  routing from the database and refuses a page in the wrong section, a cited thread with no fact in that generation,
  and a line (generated or curated) naming another generation. A new source needs a `generation`. Tests:
  `test_a_fact_publishes_only_in_the_generation_of_its_stated_years`, `test_a_fact_without_years_takes_its_sources_generation`,
  `test_a_fact_whose_years_span_both_generations_publishes_in_neither`,
  `test_a_fact_whose_title_names_the_other_generation_publishes_in_neither`,
  `test_a_claim_naming_the_other_generation_is_withheld_and_qa_refuses_it`,
  `test_curated_and_generated_pages_must_sit_in_their_generations_section` (a curated page naming the other generation,
  a leftover top-level `wiki/vehicle/`, and a generated page outside a generation's folder are all refused).
- **A correction never bypasses grounding.** A reviewer's `correct` verdict (`corrections.py`) rewords one step, summary,
  tip, mistake or symptom; values, metadata, tools and `complete` are only judged, and steps cannot be added or reordered.
  The corrected text is re-checked against the chunk on every load (numbers in the source, no 12-word copy) and still
  needs a published spec for a safety value. A Claude correction that changes a number waits for a person (`xw triage`).
  After a step is corrected, only a reviewer's `complete` verdict on the corrected list counts (`complete_lists`), never
  the local verifier's. Tests: `test_a_correction_with_an_unsourced_number_or_copied_text_is_never_used`,
  `test_a_corrected_step_with_a_torque_value_is_marked_unconfirmed_or_needs_a_spec`,
  `test_a_complete_verdict_on_the_old_list_does_not_publish_a_corrected_procedure`,
  `test_a_claude_correction_that_changes_a_number_waits_for_a_person`,
  `test_correcting_a_value_metadata_tool_or_complete_claim_is_invalid_input`.
- **Reviewer instructions exist in three copies**: `.claude/agents/wiki-reviewer.md`, `.codex/agents/wiki-reviewer.toml`
  and `.agents/skills/source-command-review-wiki/` (with `review.INSTRUCTIONS` in each batch). Edit them together.
  `test_every_copy_of_the_reviewer_instructions_describes_corrections` checks only the `correct` rules; nothing else
  covers drift.
- **`wiki/<generation>/vehicle/` is each section's hand-curated reference section, outside the pipeline.** The wiki is one product; these folders are the part nothing generates. Model-year, paint, dimension, fluid, maintenance,
  part-number and recall pages from manufacturer, EPA, NHTSA and catalog sources. `export.CURATED_DIR` is not a topic
  category, so export never deletes or rewrites it (it only links the hub from `index.md`); do not add `vehicle`
  to `topics.yaml`. Its pages must not carry the `GENERATED` line. `qa.check_curated` requires every line that states a
  number to cite an `[S<n>]` listed under that page's `## Sources` (with a URL) or say `[Unverified]`; that checks
  traceability, not truth. Test: `test_curated_pages_survive_export_and_every_number_cites_a_source`.

## Repository layout

| Path | Role |
|---|---|
| `src/xw/` | Pipeline: `fetch`, `crawl`, `parse/`, `extract`, `grounding`, `verify`, `export`, `review`, `corrections`, `triage`, `qa`, `llm`, `db`, `cli` |
| `config/` | `settings.yaml`, `sources.yaml` (ranked sources), `topics.yaml` (seed page tree); `settings.local.yaml` is gitignored |
| `prompts/` | `extract.md` and `verify.md`, the LLM system prompts |
| `tests/` | Offline suite with HTML fixtures; no network or LLM server needed |
| `wiki/` | Generated output; pages with the `GENERATED` header are overwritten by `xw export`. Committed, so regenerate and review the diff before committing |
| `wiki/<generation>/vehicle/` | A generation's reference section: hand-curated pages (one per model year plus reference pages); edit by hand, cite every number, never name the other generation |
| `wiki/<generation>/vehicle/guides/` | Hand-written how-to guides, same rules. Regenerate the second-gen hub with `scripts/guides_hub.py`. Name a guide after its `topics.yaml` slug and the index links it from that topic's row (`export.GUIDES_DIR`, `test_a_curated_guide_is_linked_from_its_topic_in_the_index`) |
| `data/` | SQLite state and raw page cache. Gitignored; holds other people's posts |
| `.claude/`, `.codex/`, `.agents/` | `/review-wiki` command and `wiki-reviewer` agent, per tool |

## Build commands

```bash
scripts/bootstrap.sh     # venv, pip install -e ".[dev]", xw init, pytest, xw doctor
scripts/run_all.sh       # xw doctor, run, export, qa
```

## Test commands

```bash
.venv/bin/pytest         # the gate, also run by CI on every push to master and every pull request
.venv/bin/xw qa          # exit 1 if a published page violates the grounding rules (local only: needs data/)
```

CI (`.github/workflows/ci.yml`, GitHub Actions) runs `pytest` on Python 3.10, 3.12 and 3.13 with current releases and on
3.10 with every dependency at its declared floor (read from `pyproject.toml`), fails if anything under `data/`,
`config/settings.local.yaml` or a `.env` is tracked, and runs `qa.check_curated` on every `wiki/<generation>/vehicle/`. It cannot run
`xw qa` on the generated pages (they are checked against `data/xw.sqlite`, which is never committed) or anything that
needs the LLM server, so those stay local steps before a wiki commit.

## Validation requirements

The suite is offline and does not exercise a real LLM or a live forum. A change to `llm.py`, a prompt, or a parser
is not validated until `xw doctor` passes against the local server and a sample thread has been run through
`xw ingest` then `xw verify`. After any export-affecting change run `xw export && xw qa`. Dependencies are floors
with no ceiling (`httpx>=0.27`, `pydantic>=2.6`, `lxml>=5.0`, `beautifulsoup4>=4.12`); CI's `test-floors` job runs the
suite at exactly those floors on every change (it passed locally at the floors on 2026-10-17, see `docs/STATUS.md`).

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
