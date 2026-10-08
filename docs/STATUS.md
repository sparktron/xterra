# Current Status

**Updated:** 2026-10-07 · **Branch:** `docs/hub-standard` (from `master`) · **Commit:** `c22fe98` plus uncommitted working-tree changes (see Active work)

## Objective

Build a wiki for the 2nd-gen Nissan Xterra (N50) and the shared Frontier/Titan drivetrain from forum threads,
using a local LLM, where every published fact is grounded in source text and verified before it appears.

## Current state

- The pipeline is implemented end to end: fetch, parse, extract, verify, export, review loop, qa. Commands: `init doctor status discover harvest extract ingest verify export review-export review-apply qa run reset-source`.
- A wiki exists in `wiki/`. `wiki/index.md` lists 117 topics: 76 `[Unverified]`, 2 `community-consensus`, 1 `disputed`, 38 `not-started`. The `wiki/` pages are generated and untracked (only `wiki/.gitkeep` is committed).
- Per `xw status` on 2026-10-07: the `manual` source has 43 threads and 229 facts (from pages ingested by hand); `thenewx` is `blocked` (HTTP 409, 2 fetches, 0 threads); `nissan-frontier-forum` and `clubfrontier` are `queued` and have never fetched anything.

## Active work

The working tree on `master` carried uncommitted changes from other work when this document was written, none of them part of this documentation commit:

- `prompts/extract.md`, `src/xw/schemas.py`: make `title` required on every fact, with a fallback to `topic`.
- `src/xw/parse/xenforo.py`, `tests/test_parse.py`, `tests/fixtures/xenforo_thread_california.html`: parse customised XenForo themes (`article.js-post`).
- Untracked: generated `wiki/` output, `.codex/`, `.agents/` (Codex copies of the `/review-wiki` command and reviewer agent).

## Next

1. Decide what to do with the `thenewx` block. The pipeline stops on it by design; the options are `xw ingest` of pages saved from a browser session, or another source.
2. Run `nissan-frontier-forum` and `clubfrontier` for the first time. Their URLs and forum software are `[Unverified]` in `config/sources.yaml`.
3. Run the Claude review loop (`/review-wiki`) over the queued review batches (`xw review-export`).

## Blockers

- `thenewx` (the rank-1 primary source) refuses automated access. Nothing in this repo should work around that.

## Known problems

- `qa.py` globs `wiki/*/*.md` and checks only the `## Specifications` and `## Parts` sections. `wiki/dtc_table.csv`, `wiki/interchange.md` and `wiki/parts_diagrams.md` are not re-checked by `xw qa`. Found by reading the code; not tested.
- The recorded block reason says HTTP 409, which is not in the tracked `crawl.stop_statuses` (`[401, 402, 403]`). The cause is not established. `config/settings.local.yaml` was deliberately not read.
- The README said the pipeline was "not yet run against a real server", which is no longer true (229 facts extracted, `xw doctor` passes); that clause was removed in the same commit as this file.
- Dependencies are floors without ceilings and the repo has no CI.

## Validation state

| Check | Result | Detail |
|---|---|---|
| `pytest` on the working tree, current deps | passed | 63 passed; Python 3.10.12, pytest 9.1.1, pydantic 2.13.5, httpx 0.28.1, lxml 6.1.3, beautifulsoup4 4.15.0; commit `c22fe98` plus the uncommitted changes above |
| `pytest` at the declared floors | passed | 63 passed; pydantic 2.6.0, httpx 0.27.0, lxml 5.0.0, beautifulsoup4 4.12.0, PyYAML 6.0, pytest 8.0.0, same tree |
| `xw qa` | passed | against the current `data/xw.sqlite` and `wiki/` |
| `xw doctor` | passed | LM Studio reachable at `http://localhost:1234/v1`, model `qwen3.8-27b` available, RTX 3090, `crawl.contact` set |

Not run on this commit: `pytest` on a clean checkout of `c22fe98` without the working-tree changes; `scripts/bootstrap.sh`; `xw doctor --smoke`; a crawl of any source.

## Unverified

- Whether the verifier's false-accept rate is acceptable. The audit sample from `xw review-export` has not been reported anywhere in the repo.
- That the sources other than `manual` work at all: URLs, forum software and seed paths are marked `[Unverified]` in `config/sources.yaml`.
- Model-year scope 2005-2016 for the N50 (marked `[Unverified]` in `config/settings.yaml`).
- Context length 16384 fitting a 24 GB 3090 (marked `[Inference]` in the README).
- That the three copies of the reviewer instructions (`.claude/`, `.codex/`, `.agents/`) agree beyond the portion read.

## Recent decisions

No decision records exist. The design decisions are in `README.md` (Verification, Legal) and the module docstrings of `src/xw/verify.py` and `src/xw/fetch.py`; their consequences are listed under Important invariants in `AGENTS.md`.

## Deep context

| Topic | Document |
|---|---|
| Agent guidance and invariants | `AGENTS.md` |
| Design and verification layers | `README.md` |
| Settings | `config/settings.yaml` |
| Sources | `config/sources.yaml` |
| Commit history | `git log` (19 commits, 2026-10-06 to 2026-10-07) |
