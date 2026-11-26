#!/usr/bin/env bash
# L0-only validation for the three task fixes:
# - t033: s2 (drawer close) progress windows
# - t078: mid at handle contact / later during closing
# - t133: rollback the first-placed moka pot (order observed for seed 0)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python"
LIBERO_HOME="/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero"
CHECKPOINT="/home/tarowang/workspace/roboot/model/openpi/openpi-assets/checkpoints/pi05_libero"
LOG="$REPO_ROOT/runs/c-l0-audit/run.log"
mkdir -p "$REPO_ROOT/runs/c-l0-audit"

export MUJOCO_GL=osmesa
export XLA_PYTHON_CLIENT_MEM_FRACTION="${XLA_PYTHON_CLIENT_MEM_FRACTION:-0.42}"
export PYTHONPATH="$REPO_ROOT/src:$LIBERO_HOME"
export LIBERO_HOME

run() {
  local name="$1"; shift
  local out="$REPO_ROOT/runs/c-l0-audit/$name"
  echo "" | tee -a "$LOG"
  echo "=== $name start $(date -Is) ===" | tee -a "$LOG"
  "$PY" "$REPO_ROOT/scripts/run_window_matrix.py" \
    --windows early mid later --levels L0 \
    --max-steps 600 --repair-window 600 --video \
    --policy pi05 --checkpoint "$CHECKPOINT" --libero-home "$LIBERO_HOME" \
    --output "$out" "$@" 2>&1 | tee -a "$LOG"
  echo "=== $name end $(date -Is) rc=${PIPESTATUS[0]} ===" | tee -a "$LOG"
}

run t033 \
  --matrix "$REPO_ROOT/dataset/matrices/libero-rollback/in-execution-rollback.csv" \
  --case-ids d-l10-t033-early-l0 d-l10-t033-mid-l0 d-l10-t033-later-l0 \
  --require-s2-started-early \
  --joint-mid-fraction 0.50 --joint-later-fraction 0.85

run t078 \
  --matrix "$REPO_ROOT/dataset/matrices/libero-rollback/in-execution-rollback.csv" \
  --case-ids d-l10-t078-early-l0 d-l10-t078-mid-l0 d-l10-t078-later-l0 \
  --joint-mid-fraction 0.05 --joint-later-fraction 0.65

run t133 \
  --matrix "$REPO_ROOT/runs/c-l0-audit/t133-order.csv" \
  --case-ids d-l10-t133-early-l0 d-l10-t133-mid-l0 d-l10-t133-later-l0 \
  --lift-min-m 0.005 --preplacement-max-xy-m 0.20

echo "" | tee -a "$LOG"
echo "=== L0 audit done $(date -Is) ===" | tee -a "$LOG"
