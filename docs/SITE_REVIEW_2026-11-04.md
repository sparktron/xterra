# Wiki review, 2026-11-04

**Updated 2026-11-05.** Figures below are from the 2026-11-04 snapshot and were not re-measured. Since then PR #16 added the Nov 3 chunks: the wiki is now 1,539 pages from 3,103 facts with 2,005 withheld, and 1,541 threads are queued. Rechecked on `master` (`65687a6`) and still open: the pinion claim (item 3), withheld text in `open_questions.md` (item 4, now 40 lines mentioning verbatim overlap), the 4 blank `[Partial]` steps (item 8), no `qa` check for missing pages (item 1), and no MkDocs config or `LICENSE` (items 6 and 17).

## Verdict

The wiki is really two products. The 85 hand-written pages (guides and vehicle reference) are good and could carry the site today. The 1,413 generated topic pages are grounded in their sources and traceable, but they are fragmented and hard to use, and they bury the good pages.

The suggestions below mostly concern structure and presentation. None of them loosens `grounding.py`, `export.gate` or `qa.py`.

**Don't crawl more until the structure is fixed.** There are 1,539 queued threads. At the current rate of about 1.9 facts per page, they would add many more one-fact pages.

## Fix first

### 1. An interrupted export can empty a wiki section

- **What happened:** an export on 2026-11-03 deleted all 930 generated second-gen pages from the working tree and never rewrote them. Nothing was committed, so the public `master` stayed intact.
- **Current state:** repaired. The "Guides and generation split" session regenerated the pages just after midnight on 2026-11-04, and that work is merged to `master` (PR 13).
- **Cause:** `export_all` calls `_remove_stale` first, then writes each generation in turn. Timestamps show the deletes around 07:33 on 2026-11-03, first-gen finished at 07:34:06, and second-gen was never written. A clean export on a copy of the same database wrote all 930 pages, so the data is fine and the run most likely stopped partway.
- **QA gap:** `xw qa` exits 0 with all 930 pages removed, because it only checks pages that exist. I confirmed this on a scratch copy with the pages actually deleted.
- **Suggested fix:**
  - **Done:** exports now build in a temp directory and move into place only after rendering finishes (PR 14).
  - **Still open:** make `qa` fail when an index link points at a missing page.

### 2. Don't act on `docs/QUALITY_REVIEW_2026-11-03.md` or its executive summary

Both were written after the pages disappeared, and they treat the damaged tree as real.

| The document says | What I found |
|---|---|
| Second gen has 77 files, so first gen has "stronger coverage" | Second gen has 930 generated pages against first gen's 483 |
| `run_all.sh` "executed successfully" | Nothing in `wiki/` was written after 07:34; the review is timestamped 23:06 |
| 265+ items withheld | Export reports 1,791 |
| Lower evidence thresholds for how-to threads | `AGENTS.md` forbids loosening these without a test showing why |
| Promote topics with 5+ threads to `community-consensus` | That isn't the gate's rule |
| Add cross-generation references | The sections are deliberately kept fully separate, and `qa` refuses lines naming the other generation |
| Discover more threads from thenewx.org | That source is marked blocked, and blocks are never worked around |

**Done:** both files were deleted on 2026-11-04 at your request.

### 3. A published torque instruction is wrong

`second-gen/reference/torque-specs.md` says "Torque the pinion nut to 5 in-lbs to increase preload" [t119]. The owner actually wrote that their measured preload was 5 in-lbs, well under spec. It is not a nut torque.

It passes every deterministic check because the number and unit really are in the source, and it carries `[Partial] [Unverified value]`. Reject it in `xw triage`.

This is a class of error: **a value lifted from a sentence that says something else.** Grounding can't catch it by design, so only review can. The 2026-10-27 review rejected 90 of 218 locally supported claims, although that sample was deliberately chosen and is not a population rate.

### 4. `open_questions.md` publishes what the gate refused

- **Verbatim text:** 38 lines (23 second-gen, 15 first-gen, committed at `HEAD`) print text withheld for "verbatim overlap with source". That undoes the no-copying rule on a public repo.
- **Rejected values:** the same two files (437 KB) list rejected and unsupported claims, including torque values such as "Tighten the three top strut mount bolts to 30 ft-lbs". They are labelled as withheld, but a search result or a skimming reader won't see that.
- **Suggested fix:** publish only counts, reasons and source links, and move the claim text to a gitignored report under `data/`. Add a `qa` rule covering these files.

## Reader experience

### 5. Every generated page opens with raw metadata

GitHub only treats YAML as front matter when `---` is the first line, and the `GENERATED` comment sits above it. So all 1,413 pages show a block of text like `title: ... applies_to: years: [] trims:` above the heading. I confirmed this on the live `engine-oil-change.md` page.

**Fixed in PR #15, merged 2026-11-04:** the metadata now sits in an HTML comment under the `GENERATED` line, and `qa` refuses it anywhere else. A future MkDocs build won't see that block without a step that extracts it.

### 6. Readers can't find the good content

- **No site or search:** GitHub Pages isn't enabled, and browsing relies on GitHub's file view.
- **Oversized index:** the second-gen index is a 115 KB alphabetical table of about 950 rows, including titles like `[[diagnostics] EVAP system faults]`.
- **Guides are secondary:** a guide appears only as a small link in a second column, and 15 rows show `not-started` right beside a guide link.
- **No cross-links:** none of the 1,413 topic pages has an internal link, so a reader on a topic page can't reach the guide for that job.
- **Unlinked pages:** `interchange.md`, `parts_diagrams.md`, `pending_verification.md` and `open_questions.md` in each section have no inbound links.
- **Stale hub:** the first-gen reference hub describes its guides as "oil change, timing belt, torsion bars and ride height", but there are now 9 guides plus a guide index.

**Suggested fix:**

- Lead each section with guides and reference, and move forum-derived pages to a "community notes" layer below them.
- Add a "Guide for this job" link at the top of the matching topic pages.
- Show a clear state, not `not-started`, when a guide exists.
- Publish with MkDocs Material on GitHub Pages, which gives you search and navigation cheaply.

### 7. The topic tree is fragmented

- **Very thin pages:** 1,413 pages hold 2,691 facts, about 1.9 per page, and 1,298 pages rest on one thread.
- **Same title, many pages:** 37 titles repeat across 84 pages. "Heater core and A/C problems" has four second-gen pages in four categories.
- **Near duplicates:** by title overlap there are about 80 clusters covering 198 pages. Second-gen titles alone include 15 mentioning SMOD, 29 radiator and 26 skid.
- **Catch-all pages:** 11 pages are titled just "Diagnostics", "Reference", "Mods", "Repair" or "Parts diagrams".
- **Weak categories:** `reference` holds 632 pages, and 389 of them contain a procedure.

**Suggested fix:**

- Use a closed topic list, with new model-proposed topics going through a review step.
- Take the category from the topic, not from the model's guess.
- Add an alias map, which also serves item 5 of the `docs/STATUS.md` plan.
- Set a minimum size for a standalone page, and fold smaller ones into their parent topic.

Keep the rule that different numbers, vehicles or generations never merge. I'd expect a few hundred useful pages to remain, though that is an estimate.

### 8. Most "procedures" aren't procedures

- **Too short:** 862 of 1,013 procedures (85%) have one or two steps. In 302 cases the single step just repeats the summary, for example "Compare the price of Xterra-specific rear backing plates against Titan equivalents."
- **Alternates:** 404 of 935 "Alternate procedure" blocks have one step, and 43 pages have five or more alternates. `bumpers-armor.md` has 76.
- **Empty steps:** four render as blank `1. [Partial]`, three of them on the first-gen torque page. This is a bug, and `qa` should refuse it.
- **Wrong form:** 108 steps are past-tense narration ("Torqued the rear shock...") and 72 are advice rather than actions.

**Suggested fix:** render anything under three steps as tips. Cap the alternates shown, group alternates by thread, and ask that a step be an imperative action. Moving text to tips changes no publishing decision.

### 9. The trust marks have stopped carrying information

- 1,364 of 1,413 pages contain `[Partial]`, 5,393 items carry it, and 1,008 of 1,013 procedures show the warning banner.
- A mark on nearly everything tells readers nothing, so they will learn to ignore it.

I hand-checked 30 random claims against the best-matching source sentences. This is too small for a rate, and I did not read the full threads, but the pattern is worth testing:

| Sample | Accurate | Lost context | Distorted or unsupported |
|---|---|---|---|
| 18 unmarked | 9 | 4 | 5 |
| 12 `[Partial]` | most | | at least 2 |

Examples from the unmarked set:

- "Install a rear breather extension to prevent fluid leaks": the owner only says they did it.
- "Use a specialized alignment tech method": the source describes one shop's preferred technician.
- "may become common practice": the owner wrote they weren't sure it was common practice.

So `[Partial]` may not separate good claims from bad ones, and unmarked does not mean right.

**Suggested fix:**

- Review the 853 random audit claims already queued. That gives the unbiased error rate `docs/STATUS.md` says is missing, and it should settle `publish_partial`.
- Consider one trust label per page or section in place of a tag on most lines. Keep the line marks required for safety values.

### 10. Claims lose their context

About 30 pages contain phrases like "this method", "the text refers to" or "listed below", where nothing is below. A deterministic check could hold these for review. Include the surrounding parent topic in the extraction prompt so each claim stands alone.

False disputes also appear. "Wheel Width (Custom)" is marked DISPUTED, but it lists two different wheels on different builds. Owners' setups shouldn't count as conflicting specs.

### 11. Key fields are empty

Of 2,694 stored facts:

| Field | Facts with a value |
|---|---|
| `engines` | 0 |
| `dtcs` | 0 |
| `est_time` | 15 |
| `difficulty` | 65 |
| `years` | 493 |

- **`engines`** matters most on first gen, where a procedure may apply to the KA24DE or the VG33E but not both. All 483 first-gen pages have no engine in their metadata.
- **`dtcs`** being empty leaves `dtc_table.csv` with only a header row in both sections.
- **`prompts/extract.md`** has no rule for engines or codes, which is the likely cause. I did not confirm it with a model run.

**Suggested fix:** add the rules, test on a small first-gen batch, and verify the results before any wider re-extraction. `interchange.md` should also move from topic rows ("Alternator failure symptoms | Frontier") to part-level rows, or be hidden until it's useful.

### 12. Hub pages collect unrelated material

- The torque page's summary includes "Select a relay rated for at least 30-AMPS" and a $18.69 camber bolt price as a spec.
- The fluid capacities page has "Rear Shock Lift Range" as a spec.

The curated `guides/torque-specs.md` and `fluids-capacities.md` are far better. Make those the canonical pages, and restrict the generated versions to matching spec types or drop them.

### 13. Check image links

The wiki cites 1,980 unique URLs. I tested a small sample of image hosts:

| Host | Result |
|---|---|
| ImageShack (including `tapatalk.imageshack.com`) | 8 of 8 failed |
| Photobucket | 5 of 6 returned an image |
| Tapatalk's other hosts | 4 of 4 worked |
| Imgur | 4 of 4 worked |

Add a periodic link checker that excludes blocked sources. Rename "Diagrams (links only)", since most entries are forum photos, along with some YouTube and product links.

## Content gaps

### 14. First gen is far behind

| | First gen | Second gen |
|---|---|---|
| Hand-written guides and reference pages | 13 | 72 |
| Topic rows marked `not-started` | 25 | 14 |

- **No curated first-gen page for:** model years, trims, paint codes, fuel economy, maintenance schedule, part numbers, trouble codes or fuse maps.
- **Also uncovered as topics:** oil-adjacent basics like coolant and belts, the KA24DE timing chain, clutch, and fuel pump.
- **Local manuals:** only part of the first-gen service manual is on disk (2000 EM/MA, 2002 EM/SU, 2004 EM/FAX/GI/MA), so this work needs more sections first.
- **Suggested start:** a maintenance schedule, then a trouble-code page, then coolant, then clutch.

### 15. Second-gen gaps are small

- **Topics:** "Torque converter shudder" and "Maintenance schedule" are the only rows with no guide. The second already has a curated page at `vehicle/maintenance-schedule.md`, so it only needs linking.
- **Year pages:** 2005-2007 each carry about 20 `[Unverified]` lines because Nissan doesn't host those owner's manuals. The local 2006 `MA.pdf` could firm up the 2006 rows. There is no local 2005 manual, and the local 2007 manual has no MA section.

### 16. The hand-written pages held up

- Guides are clear, sequenced, cited line by line, and they separate Nissan's values from owners' experience.
- I matched the 294 N·m values in the second-gen guides against the local manual text. 153 matched with the unit, 99 matched as a number only, and 42 weren't found.
- That isn't evidence of errors, because Nissan prints many torques on drawings and the guides say so. I checked one by eye: `leaf-springs.md`'s 190 and 73 N·m match the 2013 manual's drawing on RSU-7.
- A fuller check would have to read the drawings.

## Trust and project housekeeping

### 17. Public-facing gaps

- **Landing page:** the root `README.md` addresses developers. Readers get no plain explanation of what this is or how to read its marks.
- **Disclaimer:** the root index has no safety disclaimer, even though torque and fluid values drive real repairs.
- **License:** there is no `LICENSE` file, so reuse rights for your hand-written guides are undefined.
- **Corrections:** pages offer no way to report an error. A link to GitHub Issues on each page would feed `xw triage`.

### 18. Check your crawl identity

- `config/settings.local.yaml` sets `crawl.contact` to an address that doesn't match your git identity. `AGENTS.md` requires the User-Agent to stay honest, so please confirm that address is intended.
- `config/settings.yaml` sets `respect_robots` to false, overriding the code default of true. Consider setting it back to true before crawling resumes.

### 19. Documentation drift

- `README.md` still says LM Studio on port 1234 with `qwen3.8-27b`, while `docs/STATUS.md` says the default is now 1235.
- The Objective in `docs/STATUS.md` describes a second-gen wiki only, and that file is now 713 lines long.
- The README's verification list has two item 5s.

## Suggested order

1. **Now:** reject the pinion claim and stop publishing withheld text.
2. **Reader fixes:** add guide links, link the orphan pages, fix empty steps, and add the missing-page `qa` check.
3. **Structure:** closed topic list, merge duplicates, short procedures become tips.
4. **Measure:** run the 853-claim random audit, then decide how marks should work.
5. **Publish:** MkDocs site with search, landing page, disclaimer, license, and a corrections link.
6. **Data:** add engine and code extraction, then expand first-gen reference.
7. **Then** resume crawling the 1,539 queued threads.

Items 3-5 need a test wherever they touch `export`, and `export.render_page` and `qa.py` must change together.

## How this review was done

- **Snapshot:** I reviewed a copy of `HEAD` and a fresh export from a copy of the database, both in a scratch directory.
- **Coverage:** scripts measured all 1,510 markdown pages. I read about 25 pages closely, covering every category in both sections.
- **Claim check:** 30 random claims, compared with their best-matching source sentences rather than full threads.
- **Not run:** `pytest`, any LLM stage, or new crawling. I made no code or wiki changes; this report is the only file added.
- **Link test slip:** my image-link sample accidentally included one `thenewx.org` URL, a blocked source. The request got no response and was not repeated.
