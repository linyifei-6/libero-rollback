#!/usr/bin/env bash
# L0 supplement for the remaining order-ambiguous C tasks.
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python"
LIBERO_HOME="/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero"
CHECKPOINT="/home/tarowang/.cache/openpi/openpi-assets/checkpoints/pi05_libero"
OUT="$REPO_ROOT/runs/c-supp-20261123"
mkdir -p "$OUT"
export MUJOCO_GL=osmesa
export XLA_PYTHON_CLIENT_MEM_FRACTION="${XLA_PYTHON_CLIENT_MEM_FRACTION:-0.42}"
export PYTHONPATH="$REPO_ROOT/src:$LIBERO_HOME"
export LIBERO_HOME

IDS=""
for t in 137 145 158 193 237; do
  for w in early mid later; do
    IDS="$IDS d-l10-t${t}-${w}-l0"
  done
done

"$PY" "$REPO_ROOT/scripts/run_window_matrix.py" \
  --matrix "$REPO_ROOT/dataset/matrices/libero-rollback/in-execution-rollback.csv" \
  --windows early mid later --levels L0 \
  --case-ids $IDS \
  --max-steps 600 --repair-window 600 --video \
  --policy pi05 --checkpoint "$CHECKPOINT" --libero-home "$LIBERO_HOME" \
  --output "$OUT" 2>&1 | tee "$OUT/run.log"
