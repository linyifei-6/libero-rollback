#!/usr/bin/env bash
# Post-settle B-plus sweep: Object invalid subset -> Spatial full -> L10 full.
#
# The Object full run was executed with the original immediate-check protocol.
# This queue re-runs only its invalid O2 cases with `--settle-after-injection 10`,
# then runs Spatial/L10 under the same post-settle protocol.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python"
LIBERO_HOME="/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero"
CHECKPOINT="/home/tarowang/.cache/openpi/openpi-assets/checkpoints/pi05_libero"
IDS="$REPO_ROOT/runs/b-plus-object-invalid-ids.txt"
LOG="$REPO_ROOT/runs/b-plus-settle-queue-20261119.log"

if [[ ! -f "$IDS" ]]; then
  echo "missing $IDS; generate it from the completed Object run first" >&2
  exit 1
fi

export MUJOCO_GL=osmesa
export XLA_PYTHON_CLIENT_MEM_FRACTION="${XLA_PYTHON_CLIENT_MEM_FRACTION:-0.42}"
export PYTHONPATH="$REPO_ROOT/src:$LIBERO_HOME"
export LIBERO_HOME

echo "=== settle queue start $(date -Is) ===" | tee -a "$LOG"
echo "XLA_PYTHON_CLIENT_MEM_FRACTION=$XLA_PYTHON_CLIENT_MEM_FRACTION" | tee -a "$LOG"
echo "Object invalid ids: $(wc -l < "$IDS")" | tee -a "$LOG"

run_suite() {
  local suite="$1"; shift
  local out="$1"; shift
  echo "" | tee -a "$LOG"
  echo "=== $suite settle start $(date -Is) out=$out ===" | tee -a "$LOG"
  "$PY" "$REPO_ROOT/scripts/run_b_plus.py" \
    --suite "$suite" \
    --split both \
    --settle-after-injection 10 \
    --video \
    --stop-on-recovery \
    --resume \
    --libero-home "$LIBERO_HOME" \
    --checkpoint "$CHECKPOINT" \
    --output "$out" "$@" 2>&1 | tee -a "$LOG"
  local rc="${PIPESTATUS[0]}"
  echo "=== $suite settle end $(date -Is) rc=$rc ===" | tee -a "$LOG"
  return 0
}

run_suite object "$REPO_ROOT/runs/b-plus-object-invalid-settle-20261119" --case-ids-file "$IDS"
run_suite spatial "$REPO_ROOT/runs/b-plus-spatial-full-settle-20261119"
run_suite l10 "$REPO_ROOT/runs/b-plus-l10-full-settle-20261119"

echo "" | tee -a "$LOG"
echo "=== settle queue done $(date -Is) ===" | tee -a "$LOG"
