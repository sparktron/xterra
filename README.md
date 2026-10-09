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
1. Deterministic grounding: numbers (in values and in prose), part numbers, DTCs and links must appear in the source; a unit a value is given must be the unit the source puts on that number; spec/part evidence must be a real quote; verbatim copying is dropped. Re-applied on every export.
2. Local verifier pass, covering prose, values, a completeness check on each procedure, and the metadata the wiki prints (years, trims, shared platform, difficulty, time); anything not `supported` is withheld. Each call carries planted false claims (decoys); a call that accepts one is discarded. `xw status` shows the decoy accept rate.
3. Policy gate: procedures publish all-or-nothing; safety values (torque etc.) need 2+ agreeing threads from distinct authors, a manufacturer source, or reviewer approval, else they go to `wiki/pending_verification.md`; disputes are withheld; a safety value inside prose publishes only if it also published as a spec.
4. Optional Claude review (`/review-wiki` or `xw review-export` / `xw review-apply`): only the claim and a short excerpt are in the batch; you run it. Reports the verifier's false-accept rate.
5. `xw qa` re-checks the published pages against raw source text; exit 1 on violation.

## Reference section (hand-curated)
The reference section of the wiki, `wiki/vehicle/`, holds pages written by hand rather than extracted: one page per model year (2005-2015) plus trims, paint codes, dimensions, engine and drivetrain, fuel economy, fluids, oil change, maintenance schedule, part numbers, recalls and VIN decoding. Sources are Nissan press kits, owner's manuals and maintenance schedules, EPA, NHTSA, and paint and parts catalogs. `xw export` leaves these pages alone and links their hub from the top of `wiki/index.md`; `xw qa` fails if a line on them states a number without citing a source listed on that page or marking it `[Unverified]`.

## Commands
`init doctor status discover harvest extract ingest verify export review-export review-apply qa run reset-source`

## Legal
Honors robots.txt and rate limits, never circumvents paywalls or blocks. Forum text is others' content: the wiki publishes paraphrased facts with source links, not copies. Check each site's terms.
