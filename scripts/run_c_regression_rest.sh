#!/usr/bin/env bash
# t078/t133 regression only (t033 already finished 21/21).
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python"
LIBERO_HOME="/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero"
CHECKPOINT="/home/tarowang/workspace/roboot/model/openpi/openpi-assets/checkpoints/pi05_libero"
LOG="$REPO_ROOT/runs/c-regression-20261122/run-rest.log"
mkdir -p "$REPO_ROOT/runs/c-regression-20261122"
export MUJOCO_GL=osmesa
export XLA_PYTHON_CLIENT_MEM_FRACTION="${XLA_PYTHON_CLIENT_MEM_FRACTION:-0.42}"
export PYTHONPATH="$REPO_ROOT/src:$LIBERO_HOME"
export LIBERO_HOME

IDS=""
for w in early mid later; do
  IDS="$IDS d-l10-t078-$w-l0"
  for lvl in l1-d03 l1-d06 l1-d10 l2-r30 l2-r60 l2-r90; do
    IDS="$IDS d-l10-t078-$w-$lvl"
  done
done

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

run t078 \
  --matrix "$REPO_ROOT/dataset/matrices/libero-rollback/in-execution-rollback.csv" \
  --case-ids $IDS \
  --joint-mid-fraction 0.05 --joint-later-fraction 0.65

# t133 uses the observed first-pot order (pot2) for this seed.
run t133 \
  --matrix "$REPO_ROOT/runs/c-regression-20261122/t133-order.csv" \
  --case-ids $(echo "$IDS" | sed 's/t078/t133/g') \
  --lift-min-m 0.005 --preplacement-max-xy-m 0.20

echo "" | tee -a "$LOG"
echo "=== rest regression done $(date -Is) ===" | tee -a "$LOG"
