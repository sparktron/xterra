#!/usr/bin/env bash
# One-time local setup: venv, install, init, tests, environment check.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
xw init
pytest -q
xw doctor
