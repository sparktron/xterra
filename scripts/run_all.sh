#!/usr/bin/env bash
# Full unattended run. Resumable: rerun after any interruption.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .venv/bin/activate ] && . .venv/bin/activate
xw doctor
xw run
xw export
xw qa
echo "Done. Optional: run /review-wiki in Claude Code, then xw export && xw qa."
