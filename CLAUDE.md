# xterra wiki pipeline

Local-LLM pipeline (`xw`) that builds a wiki on 2nd-gen Nissan Xterra / Frontier / Titan work from forum threads.

- Setup: `scripts/bootstrap.sh`. Run: `scripts/run_all.sh`. Tests: `pytest -q`.
- Never bypass blocks: 401/402/403, robots.txt, and challenge pages mark a source blocked. thenewx.org returns 402 (TollBit); use `xw ingest` with pages the user saved.
- Published facts must be grounded in source text. Do not loosen `grounding.py`, `export.gate` or `qa.py` without a test showing why.
- `wiki/` pages with the generated header are overwritten by `xw export`; never hand-edit them.
- Mark unverified claims `[Unverified]`. Do not commit `data/` or secrets.
