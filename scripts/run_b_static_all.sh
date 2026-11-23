#!/usr/bin/env bash
# Static-init ablation for every base-rollback position (L0/L1/L2) in Object,
# Spatial and L10.  Goal is already in runs/b-static-goal-20261120 and
# runs/b-static-goal-l2-20261120.
#
# Each suite starts the policy at t=0 with the target pose already written;
# there is no all_done trigger and no rollback.  First success stops the case.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python"
LIBERO_HOME="/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero"
CHECKPOINT="/home/tarowang/.cache/openpi/openpi-assets/checkpoints/pi05_libero"
LOG="$REPO_ROOT/runs/b-static-all-20261120.log"

export MUJOCO_GL=osmesa
export XLA_PYTHON_CLIENT_MEM_FRACTION="${XLA_PYTHON_CLIENT_MEM_FRACTION:-0.42}"
export PYTHONPATH="$REPO_ROOT/src:$LIBERO_HOME"
export LIBERO_HOME

echo "=== static all start $(date -Is) ===" | tee -a "$LOG"
echo "XLA_PYTHON_CLIENT_MEM_FRACTION=$XLA_PYTHON_CLIENT_MEM_FRACTION" | tee -a "$LOG"

run_suite() {
  local suite="$1"
  local out="$2"
  echo "" | tee -a "$LOG"
  echo "=== $suite static start $(date -Is) out=$out ===" | tee -a "$LOG"
  "$PY" "$REPO_ROOT/scripts/run_b_matrix.py" \
    --suites "$suite" \
    --levels L0 L1 L2 \
    --static-init \
    --max-steps 600 \
    --settle-after-injection 10 \
    --video \
    --policy pi05 \
    --checkpoint "$CHECKPOINT" \
    --libero-home "$LIBERO_HOME" \
    --output "$out" 2>&1 | tee -a "$LOG"
  local rc="${PIPESTATUS[0]}"
  echo "=== $suite static end $(date -Is) rc=$rc ===" | tee -a "$LOG"
  nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader | tee -a "$LOG" || true
  return 0
}

run_suite object "$REPO_ROOT/runs/b-static-object-20261120"
run_suite spatial "$REPO_ROOT/runs/b-static-spatial-20261120"
run_suite l10 "$REPO_ROOT/runs/b-static-l10-20261120"

echo "" | tee -a "$LOG"
echo "=== static all done $(date -Is) ===" | tee -a "$LOG"
