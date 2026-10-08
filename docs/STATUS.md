# Current Status

**Updated:** 2026-10-07 · **Branch:** `docs/hub-standard` · **Commit:** the approach-review fixes on top of `1873f9a`, plus uncommitted work from elsewhere (see Active work)

## Objective

Build a wiki for the 2nd-gen Nissan Xterra (N50) and the shared Frontier/Titan drivetrain from forum threads,
using a local LLM, where every published fact is grounded in source text and verified before it appears.

## Current state

- The pipeline is implemented end to end: fetch, parse, extract, verify, export, review loop, qa. Commands: `init doctor status discover harvest extract ingest verify export review-export review-apply qa run reset-source`.
- A wiki exists in `wiki/`. `wiki/index.md` lists 117 topics: 76 `[Unverified]`, 2 `community-consensus`, 1 `disputed`, 38 `not-started`. The `wiki/` pages are generated and untracked (only `wiki/.gitkeep` is committed). After the 2026-10-07 review loop: 79 pages, 152 items withheld, 0 safety values pending, 94 spec lines tagged `Claude-reviewed`.
- Per `xw status` on 2026-10-07: the `manual` source has 43 threads and 229 facts (from pages ingested by hand); `thenewx` is `blocked` (HTTP 409, 2 fetches, 0 threads); `nissan-frontier-forum` and `clubfrontier` are `queued` and have never fetched anything.

## Active work

Committed on this branch: fixes from the 2026-10-07 approach review (`verify.py`, `grounding.py`, `export.py`, `review.py`, `qa.py`, `db.py`,
`cli.py`, `prompts/verify.md`, tests, `README.md`, `AGENTS.md`, `config/settings.yaml` comment):

1. Decoys: every verifier call carries planted false claims; a call that accepts one is retried, then discarded (`decoy_failed`). `decoy_checks` table, shown by `xw status` and `xw verify`.
2. Units: a spec's unit must be the unit its evidence quote puts on the number (`grounding.unit_grounded`); `qa` re-checks.
3. Numbers in prose must appear in the source; a torque/capacity/pressure value in prose publishes only if it also published as a spec on the page (DTC table: never). `qa` re-checks.
4. Near-duplicate merging never merges texts with different numbers.
5. Safety consensus needs distinct authors as well as distinct threads (author case-insensitive, also in page confidence and interchange status).
6. The review queue's priority 0 comes from the exporter's own pending list (`export.pending_spec_keys`).
7. Metadata the wiki prints is verified: `applies` (years, trims, engines, drivetrain), `platform`, `difficulty`, `time`. Interchange needs `platform`.
8. Procedures need a supported `complete` claim (the step list leaves nothing out).

Also: grounding is recomputed on every export (old facts get new rules); `xw verify` verifies only missing claim keys, `--redo` re-verifies all.

Earlier uncommitted changes from other work, not part of the review fixes:

- `prompts/extract.md`, `src/xw/schemas.py`: make `title` required on every fact, with a fallback to `topic`.
- `src/xw/parse/xenforo.py`, `tests/test_parse.py`, `tests/fixtures/xenforo_thread_california.html`: parse customised XenForo themes (`article.js-post`).
- Untracked: generated `wiki/` output, `.codex/`, `.agents/` (Codex copies of the `/review-wiki` command and reviewer agent).

## Next

1. Decide what to do with the `thenewx` block. The pipeline stops on it by design; the options are `xw ingest` of pages saved from a browser session, or another source.
2. Run `nissan-frontier-forum` and `clubfrontier` for the first time. Their URLs and forum software are `[Unverified]` in `config/sources.yaml`.
3. Resolve the 28 `needs_human` review verdicts (`xw review-apply --by human`), listed in `data/review/*.verdicts.json`.
4. Spec claims drop conditions the source attaches to a value ("replace after removal", new crush washer, RTV). Reviewers flagged it on the Torque Specs thread; the values publish without those notes. Not fixed.
5. A reviewer approval stands in for two-thread corroboration, but it only shows the forum text says the value. 76 of the 94 `Claude-reviewed` values come from one hand-copied "Torque Specs" thread whose poster warns of errors. Consider a distinct tag, or requiring a manufacturer source for single-thread safety values.

## Blockers

- `thenewx` (the rank-1 primary source) refuses automated access. Nothing in this repo should work around that.

## Known problems

- `qa.py` globs `wiki/*/*.md`: it checks spec values and units, part numbers, and loose safety values in page bodies. `wiki/dtc_table.csv`, `wiki/interchange.md` and `wiki/parts_diagrams.md` are not re-checked by `xw qa`.
- The decoys only test changed or invented numbers, the easiest error to catch; 0/202 accepted does not show the verifier catches wrong conditions, vehicles or missing context. The review audit did find those (below).
- The recorded block reason says HTTP 409, which is not in the tracked `crawl.stop_statuses` (`[401, 402, 403]`). The cause is not established. `config/settings.local.yaml` was deliberately not read.
- The README said the pipeline was "not yet run against a real server", which is no longer true (229 facts extracted, `xw doctor` passes); that clause was removed in the same commit as this file.
- Dependencies are floors without ceilings and the repo has no CI.

## Validation state

| Check | Result | Detail |
|---|---|---|
| `pytest` on the working tree, current deps | passed | 74 passed, after the review fixes; Python 3.10.12, pytest 9.1.1, pydantic 2.13.5, httpx 0.28.1, lxml 6.1.3, beautifulsoup4 4.15.0 |
| `pytest` at the declared floors | not re-run | 63 passed before the review fixes |
| `xw doctor` | passed | LM Studio at `http://localhost:1234/v1`, `qwen3.8-27b`, RTX 3090, `crawl.contact` set |
| `xw verify --redo` (real model) | done | 229 facts, 198 calls, decoys accepted 0/202, 0 calls discarded. Database backed up first (session scratchpad, not in repo) |
| Claude review loop | done | 175 items in 7 batches: 108 approve, 39 reject, 28 needs_human. Verifier false-accept rate 9% (9/102 reviewed `supported` claims rejected or sent to a human); audit sample alone 2/19 |
| `xw export && xw qa` | passed | after review-apply |

Not run: `pytest` at the dependency floors after the fixes; a clean checkout; `scripts/bootstrap.sh`; `xw doctor --smoke`; a crawl of any source; `xw extract` with the changed code (only verify changed behaviour against the model).

## Unverified

- Whether a 9% false-accept rate is acceptable. It rests on 102 reviewed claims, mostly torque specs; by kind, metadata claims fared far worse (`applies`: 6 of 51 approved, all 51 had been `partial` locally).
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
