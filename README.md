# xterra-wiki

A markdown wiki that works as an encyclopedia of the 2nd-gen Xterra. It has two parts that share one index: reference pages written by hand from manufacturer and government sources, and how-to, diagnostic and spec pages built by a pipeline that crawls (politely) or ingests Xterra forum threads, extracts structured facts with a local LLM, and verifies them. Scope: 2nd-gen Xterra (N50) plus the shared Frontier/Titan drivetrain.

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
The reference section of the wiki, `wiki/vehicle/`, holds pages written by hand rather than extracted: one page per model year (2005-2015) plus trims, paint codes, dimensions, engine and drivetrain, fuel economy, fluids, oil change, maintenance schedule, part numbers, recalls and VIN decoding. Sources are Nissan press kits, owner's manuals and maintenance schedules, EPA, NHTSA, and paint and parts catalogs. `xw export` leaves these pages alone and links their hub from the top of `wiki/index.md`; `xw qa` fails if a line on them states a number without citing a source listed on that page or marking it `[Unverified]`.

## Commands
`init doctor status discover harvest extract ingest summarize verify export review-export review-apply triage qa run reset-source`

## Legal
Honors rate limits and never circumvents paywalls or blocks (401/402/403 hard stop). robots.txt checking is off by default (`respect_robots` in settings.yaml) — re-enable it before crawling a site that asks you not to. Forum text is others' content: the wiki publishes paraphrased facts with source links, not copies. Check each site's terms.
