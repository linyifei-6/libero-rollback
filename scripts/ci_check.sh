#!/usr/bin/env bash
# Local mirror of CI: lint, tests, static dataset validation and independence guards.
# Usage: bash scripts/ci_check.sh
set -euo pipefail

cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"
RUFF="${RUFF:-.venv/bin/ruff}"
STATUS=0

if [ ! -x "$PY" ]; then
    echo "error: python not found at $PY (run: uv sync --extra dev)" >&2
    exit 2
fi

echo "[1/5] ruff"
if [ -x "$RUFF" ]; then
    "$RUFF" check .
else
    echo "  skipped: $RUFF not found"
fi

echo "[2/5] pytest"
"$PY" -m pytest

echo "[3/5] static dataset validation"
"$PY" -m libero_rollback.cli validate --dataset dataset

echo "[4/5] independence guards"
if grep -RInE '^[[:space:]]*(import|from)[[:space:]]+(libero_compose|libero_runtime)\b' src scripts tests; then
    echo "error: precursor-repository import found (see docs/attribution.md)" >&2
    STATUS=1
fi
if grep -RInE '/(home|Users)/|wsl\.localhost' src scripts dataset \
    --exclude=validation.py --exclude=validate_dataset.py; then
    echo "error: absolute host path found" >&2
    STATUS=1
fi

echo "[5/5] generated manifest check"
"$PY" scripts/build_manifest.py --check

exit "$STATUS"
