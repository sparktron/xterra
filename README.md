# xterra-wiki

Pipeline that crawls (politely) or ingests Xterra forum threads, extracts structured facts with a local LLM, verifies them, and exports a markdown wiki. Scope: 2nd-gen Xterra (N50) plus the shared Frontier/Titan drivetrain.

## Quick start
```
scripts/bootstrap.sh     # venv, install, init, tests, doctor
# set crawl.contact and, if different, llm.endpoint / llm.model in config/settings.local.yaml
scripts/run_all.sh
```
Defaults assume LM Studio at `http://localhost:1234` with model `qwen3.8-27b` and `reasoning_effort: none` (model id confirmed by the local server); `ollama` is also supported via `llm.provider`. Not yet run against a real server: `xw doctor` checks the endpoint and model id. Context 16384 is an `[Inference]` for a 24 GB 3090; set it in LM Studio when loading the model.

## Sources
Sources are listed in `config/sources.yaml`; URLs and XenForo markup assumptions are `[Unverified]`. Pages you save yourself can be added with `xw ingest <files>`.

## Verification (the local model is not trusted)
1. Deterministic grounding: numbers, part numbers, DTCs and links must appear in the source; spec/part evidence must be a real quote; verbatim copying is dropped.
2. Local verifier pass; anything not `supported` is withheld.
3. Policy gate: procedures publish all-or-nothing; safety values (torque etc.) need 2+ agreeing threads, a manufacturer source, or reviewer approval, else they go to `wiki/pending_verification.md`; disputes are withheld.
4. Optional Claude review (`/review-wiki` or `xw review-export` / `xw review-apply`): only the claim and a short excerpt are in the batch; you run it. Reports the verifier's false-accept rate.
5. `xw qa` re-checks the published pages against raw source text; exit 1 on violation.

## Commands
`init doctor status discover harvest extract ingest verify export review-export review-apply qa run reset-source`

## Legal
Honors robots.txt and rate limits, never circumvents paywalls or blocks. Forum text is others' content: the wiki publishes paraphrased facts with source links, not copies. Check each site's terms.
