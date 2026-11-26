#!/usr/bin/env bash
# Formal C matrix, seed=1, all 180 cases, same 600+600/video protocol.
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python"
LIBERO_HOME="/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero"
CHECKPOINT="/home/tarowang/workspace/roboot/model/openpi/openpi-assets/checkpoints/pi05_libero"
OUT="$REPO_ROOT/runs/c-matrix-pi05-20261123-seed1"
mkdir -p "$OUT"
export MUJOCO_GL=osmesa
export XLA_PYTHON_CLIENT_MEM_FRACTION="${XLA_PYTHON_CLIENT_MEM_FRACTION:-0.42}"
export PYTHONPATH="$REPO_ROOT/src:$LIBERO_HOME"
export LIBERO_HOME

"$PY" "$REPO_ROOT/scripts/run_window_matrix.py" \
  --matrix "$REPO_ROOT/dataset/matrices/libero-rollback/in-execution-rollback.csv" \
  --windows early mid later --levels L0 L1 L2 \
  --seed 1 \
  --max-steps 600 --repair-window 600 --video --video-fps 20 \
  --policy pi05 --checkpoint "$CHECKPOINT" --libero-home "$LIBERO_HOME" \
  --output "$OUT" 2>&1 | tee "$OUT/run.log"
