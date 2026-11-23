#!/usr/bin/env bash
# Exact static-init ablation for all 402 base-rollback positions.
#
# Joint L1 targets are taken from the rollback run's actual q_applied (via
# runs/b-static-targets-20261120.json); L10 free targets use the rollback
# snapshot_after pose.  Goal/Object/Spatial free targets use the same nominal
# L0/L1/L2 transform as rollback (L0/mixed joint resets are exact).
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python"
LIBERO_HOME="/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero"
CHECKPOINT="/home/tarowang/.cache/openpi/openpi-assets/checkpoints/pi05_libero"
TARGETS="$REPO_ROOT/runs/b-static-targets-20261120.json"
LOG="$REPO_ROOT/runs/b-static-exact-20261121.log"

export MUJOCO_GL=osmesa
export XLA_PYTHON_CLIENT_MEM_FRACTION="${XLA_PYTHON_CLIENT_MEM_FRACTION:-0.42}"
export PYTHONPATH="$REPO_ROOT/src:$LIBERO_HOME"
export LIBERO_HOME

echo "=== exact static all start $(date -Is) ===" | tee -a "$LOG"
echo "targets=$TARGETS ($(wc -c < "$TARGETS") bytes)" | tee -a "$LOG"

run_suite() {
  local suite="$1"
  local out="$2"
  echo "" | tee -a "$LOG"
  echo "=== $suite exact static start $(date -Is) out=$out ===" | tee -a "$LOG"
  "$PY" "$REPO_ROOT/scripts/run_b_matrix.py" \
    --suites "$suite" \
    --levels L0 L1 L2 \
    --static-init \
    --static-targets "$TARGETS" \
    --max-steps 600 \
    --settle-after-injection 10 \
    --video \
    --policy pi05 \
    --checkpoint "$CHECKPOINT" \
    --libero-home "$LIBERO_HOME" \
    --output "$out" 2>&1 | tee -a "$LOG"
  local rc="${PIPESTATUS[0]}"
  echo "=== $suite exact static end $(date -Is) rc=$rc ===" | tee -a "$LOG"
  nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader | tee -a "$LOG" || true
  return 0
}

run_suite goal "$REPO_ROOT/runs/b-static-exact-goal-20261121"
run_suite object "$REPO_ROOT/runs/b-static-exact-object-20261121"
run_suite spatial "$REPO_ROOT/runs/b-static-exact-spatial-20261121"
run_suite l10 "$REPO_ROOT/runs/b-static-exact-l10-20261121"

echo "" | tee -a "$LOG"
echo "=== exact static all done $(date -Is) ===" | tee -a "$LOG"
