#!/usr/bin/env bash
# Thin wrapper around scripts/run_b_matrix.py for the B suite.
#
# Default behaviour is a DRY RUN (writes plan.json only).  Pass --execute to
# actually start the simulation; that requires the simulation environment
# (LIBERO + MuJoCo, requirements-sim.lock.txt) and, unless --policy none is
# used, a model environment:
#
#   LIBERO_HOME=/path/to/LIBERO LIBERO_PYTHON=/path/to/.venv-sim/bin/python \
#       scripts/run.sh --execute --policy none --suites goal --max-tasks 2 \
#       --output runs/b-smoke
#
# All arguments except --execute are forwarded verbatim to run_b_matrix.py.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

execute=0
forwarded=()
for arg in "$@"; do
    if [[ "$arg" == "--execute" ]]; then
        execute=1
    else
        forwarded+=("$arg")
    fi
done

if [[ "$execute" -eq 0 ]]; then
    if [[ " ${forwarded[*]:-} " != *" --dry-run "* ]]; then
        forwarded+=("--dry-run")
    fi
fi

if [[ -n "${LIBERO_PYTHON:-}" ]]; then
    python_bin="$LIBERO_PYTHON"
elif [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    python_bin="$REPO_ROOT/.venv/bin/python"
else
    python_bin="python3"
fi

exec "$python_bin" "$REPO_ROOT/scripts/run_b_matrix.py" "${forwarded[@]}"
