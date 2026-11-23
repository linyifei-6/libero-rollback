#!/usr/bin/env bash
# Full regression for t033/t078/t133 after window fixes.
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python"
LIBERO_HOME="/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero"
CHECKPOINT="/home/tarowang/.cache/openpi/openpi-assets/checkpoints/pi05_libero"
LOG="$REPO_ROOT/runs/c-regression-20261122/run.log"
mkdir -p "$REPO_ROOT/runs/c-regression-20261122"
export MUJOCO_GL=osmesa
export XLA_PYTHON_CLIENT_MEM_FRACTION="${XLA_PYTHON_CLIENT_MEM_FRACTION:-0.42}"
export PYTHONPATH="$REPO_ROOT/src:$LIBERO_HOME"
export LIBERO_HOME

run() {
  local name="$1"; shift
  local out="$REPO_ROOT/runs/c-regression-20261122/$name"
  echo "" | tee -a "$LOG"
  echo "=== $name start $(date -Is) ===" | tee -a "$LOG"
  "$PY" "$REPO_ROOT/scripts/run_window_matrix.py" \
    --windows early mid later --levels L0 L1 L2 \
    --max-steps 600 --repair-window 600 --video \
    --policy pi05 --checkpoint "$CHECKPOINT" --libero-home "$LIBERO_HOME" \
    --output "$out" "$@" 2>&1 | tee -a "$LOG"
  echo "=== $name end $(date -Is) rc=${PIPESTATUS[0]} ===" | tee -a "$LOG"
}

run t033 \
  --matrix "$REPO_ROOT/dataset/matrices/libero-rollback/in-execution-rollback.csv" \
  --case-ids d-l10-t033-early-l0 d-l10-t033-mid-l0 d-l10-t033-later-l0 \
    d-l10-t033-early-l1-d03 d-l10-t033-mid-l1-d03 d-l10-t033-later-l1-d03 \
    d-l10-t033-early-l1-d06 d-l10-t033-mid-l1-d06 d-l10-t033-later-l1-d06 \
    d-l10-t033-early-l1-d10 d-l10-t033-mid-l1-d10 d-l10-t033-later-l1-d10 \
    d-l10-t033-early-l2-r30 d-l10-t033-mid-l2-r30 d-l10-t033-later-l2-r30 \
    d-l10-t033-early-l2-r60 d-l10-t033-mid-l2-r60 d-l10-t033-later-l2-r60 \
    d-l10-t033-early-l2-r90 d-l10-t033-mid-l2-r90 d-l10-t033-later-l2-r90 \
  --no-require-settled-early --no-require-s2-started-early \
  --joint-mid-fraction 0.50 --joint-later-fraction 0.70

run t078 \
  --matrix "$REPO_ROOT/dataset/matrices/libero-rollback/in-execution-rollback.csv" \
  --joint-mid-fraction 0.05 --joint-later-fraction 0.65

run t133 \
  --matrix "$REPO_ROOT/runs/c-regression-20261122/t133-order.csv" \
  --lift-min-m 0.005 --preplacement-max-xy-m 0.20

echo "" | tee -a "$LOG"
echo "=== regression done $(date -Is) ===" | tee -a "$LOG"
