# Proposal: reviewer corrections (corrected wording)

**Status:** accepted 2026-10-15 (option A with the number carve-out) and implemented in `src/xw/corrections.py` ·
**Written:** 2026-10-15

Differences from the text below, as built:
- `tool` claims are not correctable. The claim text is "Tool needed: <name>", and a wrong tool name is a reject.
- `complete` after a correction: each reviewer `complete` verdict records the hash of the list it judged
  (`complete_lists`). Only a verdict on the corrected list counts, never the local verifier's. The exception for a
  verdict in the same file as the correction is kept. This replaces comparing timestamps, which have one-second
  resolution and would also let a re-applied human decision on the old list count again.
- A person writes a correction with `xw review-apply --by human`. Triage only accepts or rejects Claude's pending ones;
  there is no `e <text>` answer.
- `review.audit_stats` (the verifier false-accept rate) does not count a correction of a locally `supported` claim as a
  rejection.

## Problem

A procedure publishes all-or-nothing (AGENTS.md, "Procedures publish all-or-nothing"), and a reviewer, Claude or a
person, can only answer `approve`, `reject` or `needs_human`. When one step of a long guide is misworded, the only
honest answer is reject or needs_human, and the whole procedure disappears. The other steps are fine and already
approved.

The 2026-10-14 review of the guide-first extraction (batches 007-010, 76 claims) shows the cost:

| Guide | Steps | Steps approved or locally supported | What withheld it |
|---|---|---|---|
| ShrockWorks sliders (t29) | 21 | 19 | step 11 misreads the photo caption "Above a right angle drill helps"; step 17 attaches the over-tightening warning to the final torque; the `complete` reject also names step 3 ("long", "from above") |
| License-plate lights (t31) | 21 | 20 | step 15 puts the LEDs "into their housings" (source: into the bulb connectors, housings later) |
| PMF flush (t34) | 11 | 10 | step 7 says fluid flows "out of the bucket" (source: out of the hose, into the bucket); the `complete` reject also names step 4 (the 10mm socket removes the cap) and step 9 (checks the level with the engine running, which the source does later) |
| 2wd-to-4x4 transmission (t35) | 59 | 54 | `complete` reject names step 1 ("using a 10mm bolt to close it"; source: a 10mm bolt holds it closed) and step 37 ("grease rings"; source: seal rings greased with petroleum jelly); steps 31, 36, 39, 40, 52 needs_human for wording |
| Hatch struts (t9) | 7 | 5 | steps 4-5 misplace which strut end gets the new ball socket |

"Steps approved or locally supported" counts steps with a Claude approval or a local `supported` verdict and no
Claude reject. Some locally supported steps were still misworded; the `complete` reviews named them.

In each case the source states the action and the 9B model garbled the sentence. Today the remedies are:

- Re-extract. The output is nondeterministic, the facts get new ids so their verdicts are lost, and the 9B misreads
  about one step in ten of a long guide anyway.
- `xw triage`. A person can approve or reject a claim but cannot fix it.

## Proposal

Add a fourth review answer, `correct`, that carries replacement wording for one prose claim.

```json
{"verdicts": [{"id": "f564:step:7", "verdict": "correct",
               "corrected": "Run the engine until the fluid coming out of the hose into the bucket turns red.",
               "note": "Source: run it until the fluid came out red; it flows from the hose into the bucket."}]}
```

### Rules

1. **Which claims.** Only prose claims whose text the wiki prints: `step:i`, `summary`, `tip:i`, `mistake:i`,
   `symptom:i`, `tool:i`. Not `spec`, `part`, `dtc`, `applies`, `platform`, `difficulty` or `time` (values and
   metadata stay extract-and-judge only), and not `complete`.
2. **Rewrite only.** A correction replaces the text of one existing claim. It cannot insert, delete or reorder steps.
   Those change what `complete` means, and a reviewer keeps answering `needs_human` or `reject` for them as today.
3. **Stored beside the extraction, not over it.** A new table keyed like `human_decisions`:
   `corrections(thread_id, claim_kind, claim_hash, original, corrected, by, note, status, created_at)`, with
   `claim_hash` = `triage.claim_hash(original)`. The extracted text stays in `facts.fact_json` as provenance. A
   re-extraction that produces the same original text picks the correction up again (as `triage.reapply_decisions`
   does for decisions); a different text means the correction lapses.
4. **Every deterministic gate still runs, on the corrected text.** `export.load_rows` swaps the corrected text into
   a copy of the fact before `ground_fact`, so the same checks apply: numbers must appear in the chunk
   (`grounding.numbers_grounded`), no 12-word run copied from it (`grounding.has_long_overlap`), and a torque,
   capacity or pressure value in prose needs a published spec on the page (`render_page.loose`). If a correction
   fails any check it is not used, and the claim stays withheld under its original text (fail closed).
5. **Gate.** For a corrected claim, an accepted correction counts as that reviewer's approval of the new text. The
   local verifier's verdict on the old text is ignored for it. `gate` returns a `Claude-corrected` or `Human-corrected`
   tag.
6. **`complete` is re-judged.** A `complete` verdict judged the old list. When a step of a fact is corrected, that
   fact's existing `complete` verdicts no longer count. The exception is a `complete` verdict in the same verdict file,
   which the reviewer gave with the corrections in view. Without a fresh verdict the procedure is withheld until
   `review-export` queues `complete` again.
7. **Staleness.** As `apply_reviews` already does for verdicts: a correction whose `id` no longer states the text the
   batch showed is skipped and counted as stale.
8. **Display.** The procedure footer says how many steps a reviewer reworded, e.g. "_Procedure reported by [t34];
   2 steps reworded by a reviewer._" The page stays honest about who wrote what.

## Decision needed: who may publish a correction

Today Claude only judges text the local model wrote. With corrections, Claude or a person writes text that
publishes. The options:

- **A. Claude corrections publish directly**, tagged `Claude-corrected`, the way Claude approvals publish today.
  Fastest. Claude becomes an author, limited to rewording, and the deterministic gates still apply.
- **B. Claude corrections are proposals.** They publish only after a person accepts them in `xw triage`, which would
  show the original, the correction and the excerpt and take a new answer such as `c` (accept). Corrections typed by
  a person in triage (`e <text>`) publish directly. Safest; throughput is limited by a person.
- **C. Claude corrections are re-checked by the local verifier.** Not recommended: on 2026-10-14 its false-accept rate
  on Claude-reviewed claims was 48% (32 of 66), so its check adds little.

**Recommendation: A, with one carve-out to B.** A Claude correction whose numbers differ from the original claim's
numbers (`sorted(number_tokens(corrected)) != sorted(number_tokens(original))`) goes to human triage as in B. Every
case in the table above is a wording fix with the same numbers, so it would publish under A. A number change (the
airbag reset's "three times" against the source's four cycles) is where a confident wrong correction does the most
harm, and it is rare enough for a person to check.

## What changes

| File | Change |
|---|---|
| `src/xw/db.py` | `corrections` table (CREATE TABLE IF NOT EXISTS, as `verdict_runs` and `human_decisions` were added) |
| `src/xw/review.py` | `REVIEW_VERDICTS` gains `correct`; `apply_reviews` validates the claim kind, a non-empty `corrected` that differs from the original, and staleness, then writes `corrections`; `INSTRUCTIONS` says when to correct and when to reject |
| `src/xw/export.py` | `load_rows` applies accepted corrections before grounding; `gate` tag; `complete` invalidation; footer count |
| `src/xw/triage.py` | show pending Claude corrections (option B and the number carve-out); `c` accept, `e <text>` type a correction; `reapply_decisions` also reapplies corrections |
| `src/xw/cli.py` | `xw review-apply` prints applied, refused (failed a gate) and stale corrections |
| `.claude/agents/wiki-reviewer.md`, `.codex/agents/wiki-reviewer.toml`, `.agents/skills/source-command-review-wiki/SKILL.md` | the three reviewer copies: correct only when the excerpt states the action and the claim garbles it; write the source's meaning in new words; never add a number, part or step; still reject a claim the excerpt does not state at all |
| `AGENTS.md` | new invariant: "A correction never bypasses grounding", naming its tests |

`qa.py` needs no change for this, but it does not re-check procedure steps today (see `docs/STATUS.md`, Known
problems). It would be worth adding step checks in the same change, since corrections put new step text on pages.

## Tests to write first

- A correction stating a number the source does not state is not applied, and the procedure stays withheld.
- A correction copying 12 words of the source is not applied.
- A corrected step carrying a torque value still needs that value published as a spec on the page.
- A correction follows its claim across a re-extraction that produces the same text, and lapses when the text differs.
- A `complete` verdict given before a step was corrected does not publish the procedure; one in the same file does.
- A Claude correction that changes a number waits for a person (recommended option).
- A verdict file correcting a `spec`, `part` or `complete` claim is refused as invalid input.
- The three reviewer copies all describe `correct` (the first test of their drift, which has none today).

## Expected yield

Applied to the 2026-10-14 batch, rewording-only corrections would have published the sliders (21 steps), PMF flush
(11), license-plate lights (21) and hatch struts (7) procedures. They would publish marked `[Partial]` unless a reviewer
also approved `complete`. The 2wd-to-4x4 guide (59) would still wait on its torque values being published as specs.
