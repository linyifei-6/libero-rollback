#!/usr/bin/env bash
# Full SmolVLA sweep of the B-plus matrix (rollback + c0 + l0; `fresh` is not
# executable in scripts/run_b_plus.py).
#
# Protocol is intentionally IDENTICAL to the pi05 settle queue
# (scripts/run_b_plus_settle_queue.sh): same matrix, split=both, budget
# 600 + 300, delay 10, replan 10, camera 256, settle_steps 10,
# settle_after_injection 10, stop-on-recovery, video 20 fps, seed 0,
# init_row 0.  Only the policy interpreter / checkpoint differ:
#   pi05   -> openpi/.venv + ~/workspace/roboot/model/openpi/openpi-assets/checkpoints/pi05_libero
#   smolvla-> ~/venvs/smolvla + libero-plus/models/smolvla_libero
#
# Order: Goal -> Object -> Spatial -> L10 (same order as the pi05 queue).
# Every suite is resumable: re-running skips finished summaries.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/tarowang/venvs/smolvla/bin/python"
LIBERO_HOME="/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero"
CHECKPOINT="/home/tarowang/workspace/roboot/model/libero-plus/models/smolvla_libero"
LOG="$REPO_ROOT/runs/b-plus-smolvla-queue-20261120.log"
mkdir -p "$REPO_ROOT/runs"

export MUJOCO_GL=osmesa
# The checkpoint references HuggingFaceTB/SmolVLM2-500M-Instruct; it is fully
# cached locally, so keep transformers/hub offline to avoid network stalls.
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$REPO_ROOT/src:$LIBERO_HOME"
export LIBERO_HOME

echo "=== smolvla queue start $(date -Is) ===" | tee -a "$LOG"
echo "policy=smolvla checkpoint=$CHECKPOINT" | tee -a "$LOG"
echo "python=$PY" | tee -a "$LOG"
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader | tee -a "$LOG" || true

run_suite() {
  local suite="$1"
  local out="$2"
  echo "" | tee -a "$LOG"
  echo "=== $suite start $(date -Is) out=$out ===" | tee -a "$LOG"
  "$PY" "$REPO_ROOT/scripts/run_b_plus.py" \
    --suite "$suite" \
    --split both \
    --settle-after-injection 10 \
    --video \
    --stop-on-recovery \
    --resume \
    --policy smolvla \
    --checkpoint "$CHECKPOINT" \
    --libero-home "$LIBERO_HOME" \
    --output "$out" 2>&1 | tee -a "$LOG"
  local rc="${PIPESTATUS[0]}"
  echo "=== $suite end $(date -Is) rc=$rc ===" | tee -a "$LOG"
  nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader | tee -a "$LOG" || true
  return 0
}

run_suite goal "$REPO_ROOT/runs/b-plus-goal-full-smolvla-20261120"
run_suite object "$REPO_ROOT/runs/b-plus-object-full-smolvla-20261120"
run_suite spatial "$REPO_ROOT/runs/b-plus-spatial-full-smolvla-20261120"
run_suite l10 "$REPO_ROOT/runs/b-plus-l10-full-smolvla-20261120"

echo "" | tee -a "$LOG"
echo "=== smolvla queue done $(date -Is) ===" | tee -a "$LOG"
