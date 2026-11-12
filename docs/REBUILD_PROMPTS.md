# Rebuild prompts

Eleven prompts that take the repo from "a gate that stops a local model publishing something false" to the goal:
one searchable place holding everything known about the Xterra, with manual facts easy to find, every version of a
fix shown side by side, and disagreements marked.

## How to use

- Run each prompt in a fresh session in this repo, in order. Each one ends in one pull request.
- Merge a prompt's PR before starting the next. Later prompts assume the earlier ones landed.
- Prompts 6 and 10 need the local LLM server and take hours. Prompt 8 needs you at the keyboard.
- Each prompt is written to stand alone. `AGENTS.md` loads automatically and carries the rules.

## Order and why

| # | Prompt | Why here |
|---|---|---|
| 1 | Charter and decisions | `AGENTS.md` currently forbids several of the changes below; later sessions would refuse them |
| 2 | Split gating from rendering | Every later prompt adds a view; do it once on a clean seam |
| 3 | Manual facts store | The source of truth has to exist before anything can be compared with it |
| 4 | Known-facts section | First visible payoff: torque, fluids and capacities generated from the store |
| 5 | Canonical items, manual cross-check, visible disputes | Makes "known or suspected wrong" a computed mark |
| 6 | Extraction v2 and re-extraction | Schema changes must land before facts are regrouped, or the grouping is done twice |
| 7 | Jobs and fix variants | The "several versions of the same fix" view |
| 8 | Trust calibration | Marks need measuring once the structure has settled |
| 9 | Site and search | Publish what the earlier prompts built |
| 10 | Sources and crawl | Only now is more input worth having |
| 11 | Housekeeping | Docs, license, landing page |

---

## Prompt 1: Charter and decisions

```text
This repo builds a wiki about the Nissan Xterra from forum threads and the factory service manual. I am
redirecting it, and AGENTS.md has to say so before any code changes, because it currently forbids some of
what I want. This session changes documents only: no code, no wiki pages.

The goal, in my words: comb the web for discussions about modifying or fixing the Xterra (mainly second
generation) and collect all of it into one place that is easy to search and browse. When there are several
versions of the same fix I want them all shown for comparison, with anything known or suspected to be wrong
(because it disagrees with other versions or with the manual) clearly marked. Facts freely available in the
manual, such as torque specs, must be easy to find. There is a "known facts" section, and a separate section
for nuanced field experience, such as how to do a job on a truck that is old and rusted.

Decisions to record (dated today), each replacing the rule it contradicts:
1. The factory service manual becomes a structured, first-class source. Forum values are compared against it.
2. Disagreement is shown, never hidden. A safety value that sources dispute publishes with every version
   listed and a clear DISPUTED mark. The current invariant "disputed safety values are always withheld" is
   retired. A value that conflicts with the manual publishes marked as conflicting, beside the manual value.
3. The wiki has two layers per generation: Known facts (manual and other manufacturer or government data) and
   Field notes (forum-derived jobs, fixes and experience). The names are final.
4. Topics become a closed list of jobs. The model may not create pages; unmatched material waits in a queue.
5. This is a new project. Rewriting modules, the database schema and the wiki layout is allowed, and a full
   re-extraction is acceptable.
6. Unchanged: the local model is not trusted; numbers must appear in their source; no verbatim copying;
   blocks are never worked around; generations stay separate; nothing from data/ is committed.

Do this:
- Rewrite the opening and the Objective of AGENTS.md, README.md and docs/STATUS.md to state the goal above.
- In AGENTS.md "Important invariants", edit only the items these decisions change, and mark each edited item
  with the decision date. Leave every other invariant as it is.
- Add docs/ROADMAP.md listing the eleven steps in docs/REBUILD_PROMPTS.md with a status column, and mark
  step 1 done.
- Move everything in docs/STATUS.md older than 2026-11-01 into docs/STATUS_ARCHIVE.md so the live file is
  short.

Done when: the three documents agree with each other and with the decisions, pytest still passes, and the
PR description lists each invariant that changed with its old and new wording.
```

---

## Prompt 2: Split gating from rendering

```text
In this repo, src/xw/export.py decides what may publish, merges facts into pages and writes markdown, all
inside render_page (about 370 lines). src/xw/qa.py then re-parses that markdown with regexes to check it.
Every new view I want (a comparison view, a search index, a website) would need both edited again. Separate
the three jobs so later work has a clean seam. docs/ROADMAP.md has the plan; this is step 2.

Target shape:
- A gate stage that turns database rows into a page model: plain dataclasses holding every item that
  publishes, its marks, its sources and the reason for each withheld item. No markdown in it.
- A markdown renderer that takes the page model and nothing else.
- The page model is also written as JSON under data/model/ (gitignored) on each export.
- qa checks the page model against the source text. It keeps a small check that the rendered files match the
  model, so a hand-edited generated page still fails.

This step must not change what publishes. Prove it: export before the change into a scratch copy, export
after, and diff the two wiki trees. The diff must be empty, or every difference explained in the PR.

Constraints: do not loosen grounding.py, the gate rules or what qa refuses. Keep the atomic export (render to
a temp directory, move into place, delete stale pages last). Existing tests must pass; where a test reaches
into render_page, port it to the new seam without weakening its assertion.

Also add schema versioning to src/xw/db.py: a schema_version table and an ordered list of migrations, with
the current schema as version 1. Later steps add tables.

Done when: pytest passes, `xw export && xw qa` passes on the real database, the before/after wiki diff is
empty, and AGENTS.md and docs/STATUS.md describe the new modules.
```

---

## Prompt 3: Manual facts store

```text
This repo's best source of truth, the Nissan factory service manual, is not part of the pipeline. About
131 MB of manual section PDFs sit in data/fsm/<year>/, with extracted text and page images in data/fsm_text,
data/fsm_compact and data/fsm_img (inspect them first; I have not documented their layout). Today they are
only read by hand to write guides. Build a structured store of manual facts. This is step 3 of
docs/ROADMAP.md.

What a manual fact is: one value with its meaning and its citation. For example: component "rear
differential drain plug", measure "torque", value 49, unit "N·m", second value 36 "ft-lb", applies to
second-gen, years 2005-2015, variant "C200 axle", source "2012 FSM, section DLN, page DLN-183". Also cover
fluid types and capacities, service intervals, clearances, pressures, part numbers and trouble-code
definitions.

Build:
- A schema for manual facts, and a committed store under facts/manual/<generation>/<system>.yaml. Values and
  citations are facts, so they can be committed; manual text and images cannot (data/ stays gitignored, and
  nothing is copied verbatim).
- `xw manual extract`: walks the manual text section by section and proposes facts with the local LLM,
  reusing the existing grounding checks so a value is kept only if that number, with that unit, is on the
  cited page.
- `xw manual check`: re-verifies every stored fact against the page text, and exits 1 on a miss. Add it to
  the local qa run. CI cannot run it (no data/), so CI validates the schema and citation format only.
- A status field per fact: `text-verified` (found on the page), `drawing` (the manual prints it on a
  drawing, so it needs a person to read the image) or `human-verified`.
- A review command that shows me a `drawing` fact beside its page image path and records my answer.

Seed the store from what already exists: the hand-written pages under wiki/second-gen/vehicle/ cite manual
values with [S<n>] references. Import those values as candidates, then run the check on them and report how
many verify, how many are drawings and how many are not found.

Start with the second generation. Report which years and sections are on disk and which are missing; do not
download anything.

Done when: the store holds second-gen torque, fluid and capacity facts with page citations, `xw manual
check` passes, tests cover the schema, the grounding of a manual fact and a deliberately wrong value being
refused, and docs/STATUS.md gives the counts by status and the gaps.
```

---

## Prompt 4: Known-facts section

```text
facts/manual/ in this repo now holds structured factory-manual facts (torque, fluids, capacities,
intervals, part numbers, trouble codes), each with a page citation and a verification status. Generate the
wiki's "Known facts" layer from it. This is step 4 of docs/ROADMAP.md. The reader's need: someone under the
truck wants the rear differential drain plug torque in a few seconds and wants to know it came from the
manual.

Build, per generation:
- Generated reference pages by system (engine, cooling, driveline, axles, suspension, steering, brakes,
  electrical, body): tables of component, value in both units, the years and variants it applies to, and the
  manual citation.
- One complete torque table and one complete fluids and capacities table across all systems.
- A trouble-code page from the manual's code definitions.
- A machine-readable copy of each table (CSV or JSON) for the search step later.
- A value whose status is `drawing` and not yet read by a person shows a visible mark saying so.

The hand-written pages under wiki/<generation>/vehicle/ stay hand-written, but they should stop restating
numbers by hand where the store has them. Pick the lighter approach and tell me which: either a qa rule that
a manual number on a curated page must equal the store's value, or an include marker the exporter fills in.

Restructure each generation's section so the top level reads: Known facts, Field notes, Guides. Rename the
forum-derived `reference` category, since it collides with this layer; fold its pages into the category
their content fits.

Constraints: qa must verify every generated known-facts value against the store, and the store against the
manual text. Generations stay separate. Keep the generated-file header and the atomic export.

Done when: I can open one page and find any second-gen torque or capacity the manual gives, each with its
citation; `xw export && xw qa` passes; tests cover rendering, the drawing mark and qa refusing a tampered
value.
```

---

## Prompt 5: Canonical items, manual cross-check, visible disputes

```text
This repo publishes forum-derived values next to factory-manual values, but never compares them. One
generated page says to refill the front differential with 1.6 L while the manual store says the front holds
0.85 L and 1.6 L is the rear C200. Disagreement between forum threads is also detected badly: values are
grouped by the exact item name the model wrote, so "Rear diff capacity" and "Rear differential fluid
capacity" never meet, while "Lift height" from four unrelated builds is called a dispute. Fix the
comparison. This is step 5 of docs/ROADMAP.md, and AGENTS.md records the decision that disagreement is
shown, not hidden.

Build:
- A canonical key for every value: component, measure, and variant where it matters (axle, engine,
  transmission, year range). The manual store's components are the vocabulary. Map each forum spec to a key
  deterministically where possible, and with the local LLM otherwise; the mapping is a claim the verifier
  judges like any other, and an unmapped value stays unmapped and is treated as an owner's own measurement.
- A distinction between a specification (a value the truck should have) and an owner's choice or measurement
  (their lift height, their tire size). Only specifications can be disputed.
- A comparison status on every published forum specification:
  `matches manual`, `conflicts with manual` (the manual value is shown beside it), `not in manual` or
  `sources disagree` (every version listed with its threads).
- Gate changes: a manual match confirms a safety value. A conflict or a dispute publishes, marked, with all
  versions visible; it is no longer withheld. Unit conversions count as a match within rounding (49 N·m and
  36 ft-lb).
- A generated "Conflicts and disputes" page per generation listing every one, as a work queue for me.

Constraints: numbers must still appear in their source. Different numbers are still never merged into one
line. Every changed gate rule needs a test that fails before the change. qa must refuse a conflicting value
published without its mark.

Done when: the differential example above publishes with a conflict mark and the manual value beside it;
the false "Lift height" dispute is gone; `xw export && xw qa` passes; docs/STATUS.md gives counts for each
comparison status.
```

---

## Prompt 6: Extraction v2 and re-extraction

```text
This repo extracts structured facts from forum thread chunks with a local LLM (prompts/extract.md,
src/xw/schemas.py, src/xw/extract.py). The schema loses what makes forum knowledge valuable and leaves key
fields empty. Of about 3,100 stored facts, none has an engine or a trouble code, and there is nowhere to
record the conditions a tip applies to. Revise the schema and prompt, then re-extract everything from the
chunks already stored in the database. No crawling. This is step 6 of docs/ROADMAP.md; a full re-extraction
is an accepted cost.

Schema changes:
- `conditions`: when the advice applies, in the source's terms (seized or rusted fasteners, salt-belt
  trucks, lifted trucks, high mileage, cold weather).
- `kind` on each fact: `procedure`, `diagnosis`, `spec`, `experience` (what happened to one owner) or
  `opinion`. A narrated "I torqued it to X" is experience, not a procedure step.
- `outcome`: whether the source says the fix worked, failed or is unknown, and after how long if stated.
- Engines and trouble codes, with prompt rules and grounding for both.
- Post-level provenance: each fact records which post or posts in the chunk it came from, so the wiki can
  cite the post, not only the thread. Chunks carry "### Post N by name (date)" headers.
- The model picks from the closed list of topics it is shown, or answers "none of these". It no longer
  proposes page titles.
- Empty strings in lists are dropped at extraction.

Every new published field needs grounding, a verifier claim in verify.claims_for_fact, an entry in
review.CLAIM_KEY and qa coverage, as AGENTS.md requires. The reviewer instructions exist in three copies;
update them together.

Process:
1. Back up data/xw.sqlite.
2. Run 30 chunks through the new prompt and show me a before/after comparison, including how often each new
   field is filled and five examples you judge wrong. Tune the prompt on that sample.
3. Re-extract every chunk, then verify. Human decisions and accepted corrections are keyed by content and
   must still attach; report how many did.
4. Export and run qa.

Validation: `xw doctor --smoke` must pass against the model that will do the run, and the run must not
start if a different model is loaded. Record the model, timings, failures and decoy rate in docs/STATUS.md.

Done when: the new fields are populated at the rates the sample predicted, pytest and `xw export && xw qa`
pass, and docs/STATUS.md says what changed in the counts and what was not run.
```

---

## Prompt 7: Jobs and fix variants

```text
This repo publishes one page per model-proposed topic: about 1,500 pages at under two facts each, most
resting on one thread. When several threads describe the same repair, one procedure is shown and the rest
are collapsed as "Alternate procedure" with no comparison. I want the opposite: one page per job or problem,
holding every version of the fix side by side, with their differences and anything suspect marked. This is
step 7 of docs/ROADMAP.md. Facts now carry kind, conditions, outcome, post-level provenance and a canonical
key for each value.

Build:
- A closed list of jobs and problems per generation in config (extend topics.yaml): a few hundred at most,
  each with a category, aliases and the manual section it relates to. Derive the first draft from the
  existing topics, the manual's section list and the clusters of current page titles, and give me the draft
  to edit before it is final.
- Assignment of every fact to one job, deterministic where the extraction named a listed topic, otherwise
  proposed by the local LLM and verified. What fits nowhere goes to an unassigned queue page, never to a new
  page.
- A variant: one source's complete way of doing a job. Group facts from the same thread and author into a
  variant. A procedure under three steps is not a variant; its content becomes tips.
- A job page laid out as:
  1. Known facts for this job, pulled from the manual store (specs, fluids, the manual's own procedure
     outline by citation).
  2. Variants compared: a table of what differs between them (parts used, values used, tools, steps one has
     and another lacks, conditions, reported outcome), then each variant in full.
  3. Marks on any variant value that conflicts with the manual or with the other variants.
  4. Field notes: conditions-specific advice (rusted, seized, lifted), tips, mistakes and one-owner
     experience, grouped by condition.
  5. Sources, cited to the post.
- A category comes from the job, not from the model's guess.

Constraints: text is still paraphrased, numbers still grounded, generations still separate. A procedure
still publishes only if every step can. Different numbers are never merged; that is what the comparison
table is for.

Done when: second-gen has a few hundred job pages in place of roughly a thousand; a job with several
threads (radiator and transmission cooler failure, lift kits, differential fluid) shows a real comparison;
the index fits on a screen per category; `xw export && xw qa` passes; tests cover variant grouping, the
difference table and a conflict mark inside a variant.
```

---

## Prompt 8: Trust calibration

```text
In this repo the trust marks have stopped carrying information. The local verifier called more claims
"partial" than "supported", so nearly every line and procedure carries a [Partial] mark, and a Claude review
rejected 234 of 585 claims it judged, though that sample was not random. No human decision has ever been
recorded, and 12 corrections are waiting for one. Measure how reliable each mark is, then simplify the marks
to what the measurement supports. This is step 8 of docs/ROADMAP.md. I will be at the keyboard for the
triage parts.

Do this:
1. Draw a random sample of published claims, stratified by verdict (supported, partial) and by kind (value,
   step, tip, metadata), at least 60 per cell. Review them with the wiki-reviewer agent against the full
   chunk, not a short excerpt.
2. Report the error rate per cell with its uncertainty, and say plainly whether "partial" separates good
   claims from bad.
3. Walk me through `xw triage` for the pending corrections and the conflicts-and-disputes queue, most
   safety-relevant first.
4. Propose a mark scheme based on the numbers, then implement the one I pick. My starting preference:
   - Values keep per-line status: matches manual, conflicts with manual, sources disagree, single report.
   - Prose gets one trust statement per variant or section instead of a tag on most lines.
   - Anything a reviewer or I rejected never publishes.
5. If the verifier adds nothing for some claim kind, say so and propose dropping or replacing that pass
   rather than keeping it for show.

Constraints: no gate rule loosens without the measurement and a test. Safety values keep a visible per-line
status in every scheme. Record the sample, the method and the rates in docs/ so the decision can be
re-examined.

Done when: docs holds the measured error rates, the mark scheme is implemented and tested, the pending
corrections are decided, and a typical job page carries a handful of marks that each mean something.
```

---

## Prompt 9: Site and search

```text
This repo's wiki is markdown browsed through GitHub's file view. There is no website and no search, which
fails the main requirement: one place that is easy to search and browse. Publish it as a static site. This
is step 9 of docs/ROADMAP.md. Export already produces a page model as JSON and machine-readable tables for
manual facts, and pages are organised as Known facts, Field notes and Guides per generation.

Build:
- A static site built from the page model and the curated markdown. MkDocs Material is my default; use
  something else only if you can say why it is better here. Deployed to GitHub Pages by a workflow.
- Full-text search across everything.
- Structured lookup pages that work without a server:
  - a torque and capacity finder (filter by system, component, year, variant),
  - a part-number finder,
  - a trouble-code finder linking each code to its manual definition and the jobs that mention it.
- Navigation: pick a generation, then Known facts, Field notes or Guides. A job page links its known facts,
  its guide and its related jobs.
- A landing page for readers: what this is, how to read the marks, a safety disclaimer, and how to report
  an error (a link that opens a prefilled GitHub issue naming the page).
- Every forum-derived item links to its source post.

Constraints: the site is generated; nothing is hand-edited in the build output. Search results must not
surface withheld or rejected text, so confirm the build reads only the published model. Check that a search
for a value in the withheld list returns nothing. Generations stay separate in navigation and in search
filters.

Done when: the site builds in CI and deploys, I can find the rear differential drain plug torque in one
search, the three finders work offline in a browser, and a link checker passes on internal links.
```

---

## Prompt 10: Sources and crawl

```text
This repo aims to collect everything on the web about fixing and modifying the Xterra, but almost all of
its forum content comes from one site. The primary source (thenewx) answers bots with HTTP 409 and is
blocked; another is pay-per-crawl and disabled; a third shows status "done" with zero fetches and zero
threads; about 1,500 discovered threads are queued. Widen the intake without ever working around a block.
This is step 10 of docs/ROADMAP.md. The page structure can now absorb more material: facts attach to a
closed list of jobs.

Do this:
- A source that discovers nothing must not read as done. Add an explicit state and reason ("discovery found
  no threads", "seed returned 404"), surface it in `xw status`, and find out why nissan-frontier-forum
  fetched nothing.
- Bulk ingest for pages I save myself: `xw ingest` over a directory, reading the URL, title, author and date
  from the saved page, so a blocked site can still contribute through my own browser. Write a short how-to.
- Source types beyond XenForo, each as an adapter with tests on saved fixtures: a generic article or blog
  page, a video transcript I supply as a file, and technical service bulletins (data/tsb/ already holds
  some PDFs; these are manufacturer documents and belong with the known facts).
- A refresh pass: revisit a harvested thread when its reply count or last-post date has changed, add only
  the new posts as new chunks, and leave existing facts and decisions alone.
- A prioritised queue: threads matching jobs with thin coverage first.
- A written inventory of candidate sources (research/ has a first one) with each site's terms and robots
  position. I decide which to enable.

Then resume: crawl, extract, verify, export and qa on the queued threads, in batches with a database backup
before each.

Constraints, unchanged and not negotiable: 401, 402, 403, 409, repeated 429, challenge pages and off-site
redirects mark a source blocked; no retries, spoofed headers, proxies, mirrors or caches. Set
`respect_robots` back to true unless I say otherwise for a named site, and confirm the `crawl.contact`
value with me before the first request. Every new source needs a generation.

Done when: `xw status` tells the truth about every source, the queued threads are processed or their
failures listed, coverage per job is reported before and after, and docs/STATUS.md records what ran, on
which model, and what did not.
```

---

## Prompt 11: Housekeeping

```text
This repo has been restructured over ten steps (docs/ROADMAP.md) into a searchable Xterra knowledge base
with a Known facts layer from the factory manual and a Field notes layer from forums. Bring the documents
and project hygiene up to date with what now exists. No behaviour changes in this session.

Do this:
- Rewrite README.md for two readers: a short top section for someone using the site, then the developer
  section. Remove anything that describes the old design.
- Reconcile AGENTS.md with the code: for every invariant, confirm the named test exists and still guards
  it, fix or remove stale entries, and list any invariant with no test.
- Cut docs/STATUS.md to current state, active work and known gaps; archive the rest.
- Remove dead code and settings left from the old page-per-topic design, and say what you removed.
- Add a LICENSE. Ask me which licence I want for the code and for the hand-written guides before adding
  it; do not choose for me.
- Make CI cover what it can: tests, schema checks on facts/manual/, the curated-page check and the site
  build.
- Write docs/OPERATIONS.md: the routine for adding a source, running a batch, reviewing conflicts, and
  publishing, as a checklist I can follow in a month without rereading the code.

Done when: a new reader can tell from README.md what the project is and how to run it, AGENTS.md matches
the tests, CI is green, and docs/ROADMAP.md shows all eleven steps done with a short list of what remains.
```
