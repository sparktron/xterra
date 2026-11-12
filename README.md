# xterra-wiki

The goal is one searchable, browsable place for web discussions about modifying and fixing the Nissan Xterra, mainly the second generation, alongside facts from the factory service manual. Readers should be able to compare every version of a fix and see clearly when sources disagree or a claim conflicts with the manual. Manual facts such as torque specifications should be easy to find; field experience should preserve conditions such as rust and seized fasteners.

## Objective

Each generation remains separate and will have two layers: **Known facts**, from the factory service manual and other manufacturer or government data, and **Field notes**, from forum jobs, fixes and experience. The manual will be a structured, first-class source for comparison. A closed list of jobs will govern topics; unmatched material will wait in a queue rather than become a model-created page. Rewriting modules, the database and the wiki layout, and fully re-extracting facts, are accepted. See [the roadmap](docs/ROADMAP.md) for the staged rebuild.

These are decisions dated 2026-11-12, not a description of completed functionality. Today `xw` builds Markdown from forum threads and the existing hand-curated reference pages live under `wiki/<generation>/vehicle/`. The current exporter still withholds disputed safety values; roadmap step 5 will instead show every sourced version marked `DISPUTED`, and show a manual conflict beside the manual value. The local model remains untrusted: numbers must appear in their sources, copying and bypassing blocks are forbidden, and `data/` is never committed.

## Quick start
```
scripts/bootstrap.sh     # venv, install, init, tests, doctor
# set crawl.contact and, if different, llm.endpoint / llm.model in config/settings.local.yaml
scripts/run_all.sh
```
Defaults assume LM Studio at `http://localhost:1234` with model `qwen3.8-27b` and `reasoning_effort: none` (model id confirmed by the local server); `ollama` is also supported via `llm.provider`. `xw doctor` checks the endpoint and model id. Context 16384 is an `[Inference]` for a 24 GB 3090; set it in LM Studio when loading the model.

## Sources
Sources are listed in `config/sources.yaml`; URLs and XenForo markup assumptions are `[Unverified]`. Pages you save yourself can be added with `xw ingest <files>`.

## Verification (the local model is not trusted)
1. Deterministic grounding: numbers (in values and in prose), part numbers, DTCs and links must appear in the source; a unit a value is given must be the unit the source puts on that number (only the value has to be right: the model's evidence quote is not checked); verbatim copying is dropped. Re-applied on every export.
2. Local verifier pass, covering prose, values, a completeness check on each procedure, and the metadata the wiki prints (years, trims, shared platform, difficulty, time). `supported` publishes; `partial` publishes marked `[Partial]` (needs more work, still queued; `verify.publish_partial`); anything else is withheld. Each call carries planted false claims (decoys); a call that accepts one is discarded. `xw status` shows the decoy accept rate.
3. Policy gate: a procedure publishes only if every step can (partial steps and a possibly incomplete list mark it `[Partial]`); a safety value (torque etc.) is confirmed by 2+ agreeing threads from distinct authors, a manufacturer source, or reviewer approval. An unconfirmed one publishes marked `[Unverified]`/`[Partial]` under a warning banner and stays queued for re-checking (`verify.publish_unverified_safety`; off = withheld to `wiki/pending_verification.md`); disputes are withheld; a safety value inside prose needs a spec on the page or the source's own unit on that number, and is marked `[Unverified value]` while unconfirmed.
4. Optional Claude review (`/review-wiki` or `xw review-export` / `xw review-apply`): only the claim and a short excerpt are in the batch; you run it. Reports the verifier's false-accept rate. A reviewer may also `correct` a garbled step, summary, tip, mistake or symptom with its own wording, which must pass the same grounding checks; a Claude correction that changes a number waits for a person in `xw triage`, and after a step is corrected the procedure's completeness is judged again (`src/xw/corrections.py`).
5. Human triage (`xw triage`): you confirm or reject what is still low confidence (Claude was unsure, a safety value awaits a second source, the verifier answered partial). Your answer outranks Claude's and the verifier's, and is stored by claim content so it survives re-extraction and `verify --redo`. `xw triage --list` shows what is waiting; `--limit`, `--kind step,spec,...` and `--page` narrow it.
5. `xw qa` re-checks the published pages against raw source text; exit 1 on violation.

## Reference section (hand-curated)
The second generation's reference section, `wiki/second-gen/vehicle/` (each generation has its own `vehicle/`), holds pages written by hand rather than extracted: one page per model year (2005-2015) plus trims, paint codes, dimensions, engine and drivetrain, fuel economy, fluids, oil change, maintenance schedule, part numbers, recalls and VIN decoding. Sources are Nissan press kits, owner's manuals and maintenance schedules, EPA, NHTSA, and paint and parts catalogs. `xw export` leaves these pages alone and links their hub from the top of the section's `index.md`; `xw qa` fails if a line on them states a number without citing a source listed on that page or marking it `[Unverified]`.

## Commands
`init doctor status discover harvest extract ingest summarize verify export review-export review-apply triage qa run reset-source`

## Legal
Honors rate limits and never circumvents paywalls or blocks (401/402/403 hard stop). robots.txt checking is off by default (`respect_robots` in settings.yaml) — re-enable it before crawling a site that asks you not to. Forum text is others' content: the wiki publishes paraphrased facts with source links, not copies. Check each site's terms.
