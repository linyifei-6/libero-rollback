#!/usr/bin/env bash
# Sequential full B-plus sweep (rollback + c0 + l0; fresh is skipped).
#
# Order: Goal (resume the completed core run) -> Object -> Spatial -> L10.
# Each suite is resumable: re-running this script skips finished summaries.
#
# JAX memory: pi05 is capped at 42% of the GPU so it can coexist with SmolVLA
# and rendering (same budget as the old staged-parallel script).
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python"
LIBERO_HOME="/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero"
CHECKPOINT="/home/tarowang/.cache/openpi/openpi-assets/checkpoints/pi05_libero"
LOG="$REPO_ROOT/runs/b-plus-queue-20261119.log"
mkdir -p "$REPO_ROOT/runs"

export MUJOCO_GL=osmesa
export XLA_PYTHON_CLIENT_MEM_FRACTION="${XLA_PYTHON_CLIENT_MEM_FRACTION:-0.42}"
export PYTHONPATH="$REPO_ROOT/src:$LIBERO_HOME"
export LIBERO_HOME

echo "=== queue start $(date -Is) ===" | tee -a "$LOG"
echo "XLA_PYTHON_CLIENT_MEM_FRACTION=$XLA_PYTHON_CLIENT_MEM_FRACTION" | tee -a "$LOG"
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader | tee -a "$LOG" || true

run_suite() {
  local suite="$1"
  local out="$2"
  echo "" | tee -a "$LOG"
  echo "=== $suite start $(date -Is) out=$out ===" | tee -a "$LOG"
  "$PY" "$REPO_ROOT/scripts/run_b_plus.py" \
    --suite "$suite" \
    --split both \
    --video \
    --stop-on-recovery \
    --resume \
    --libero-home "$LIBERO_HOME" \
    --checkpoint "$CHECKPOINT" \
    --output "$out" 2>&1 | tee -a "$LOG"
  local rc="${PIPESTATUS[0]}"
  echo "=== $suite end $(date -Is) rc=$rc ===" | tee -a "$LOG"
  nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader | tee -a "$LOG" || true
  return 0
}

# Goal: reuse the completed 56-case core run and resume the remaining 108 O2.
run_suite goal "$REPO_ROOT/runs/b-plus-goal-core-20261118-v2"
# Other suites: full rollback + controls (fresh is not executable in this runner).
run_suite object "$REPO_ROOT/runs/b-plus-object-full-20261119"
run_suite spatial "$REPO_ROOT/runs/b-plus-spatial-full-20261119"
run_suite l10 "$REPO_ROOT/runs/b-plus-l10-full-20261119"

echo "" | tee -a "$LOG"
echo "=== queue done $(date -Is) ===" | tee -a "$LOG"
