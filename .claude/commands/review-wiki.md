---
description: Run the Claude review loop over pending review batches
---
1. Run `xw review-export` and list `data/review/batch-*.json` that have no matching `.verdicts.json`.
2. For each, use the `wiki-reviewer` agent to write the verdicts file.
3. Run `xw review-apply`, then `xw export` and `xw qa`.
4. Report the verifier false-accept rate and how many claims were approved, rejected or sent to a human.
