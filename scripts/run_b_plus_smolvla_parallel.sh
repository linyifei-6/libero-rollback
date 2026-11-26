#!/usr/bin/env bash
# Parallel full SmolVLA sweep of the B-plus matrix (one process per suite).
#
# Protocol is IDENTICAL to the pi05 settle queue
# (scripts/run_b_plus_settle_queue.sh): same matrix, split=both,
# budget 600 + 300, delay 10, replan 10, camera 256, settle_steps 10,
# settle_after_injection 10, stop-on-recovery, video 20 fps, seed 0,
# init_row 0.  Only the policy interpreter / checkpoint differ:
#   pi05    -> openpi/.venv + ~/workspace/roboot/model/openpi/openpi-assets/checkpoints/pi05_libero
#   smolvla -> ~/venvs/smolvla + libero-plus/models/smolvla_libero
#
# The GPU has spare memory/utilisation while pi05 runs (pi05 is CPU/render
# bound), so four suites can run concurrently.  Every (suite, run dir) pair is
# independently resumable: re-running this script skips finished summaries.
#
# Usage: bash scripts/run_b_plus_smolvla_parallel.sh [suite ...]
#        (default: all four suites, in this order)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/tarowang/venvs/smolvla/bin/python"
LIBERO_HOME="/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero"
CHECKPOINT="/home/tarowang/workspace/roboot/model/libero-plus/models/smolvla_libero"
STAMP="${STAMP:-20261120}"
LOG_DIR="$REPO_ROOT/runs/smolvla-logs-$STAMP"
mkdir -p "$LOG_DIR" "$REPO_ROOT/runs"

export MUJOCO_GL=osmesa
# The checkpoint references HuggingFaceTB/SmolVLM2-500M-Instruct; it is fully
# cached locally, so keep the hub/transformers offline to avoid network stalls.
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$REPO_ROOT/src:$LIBERO_HOME"
export LIBERO_HOME

SUITES=("$@")
if [ ${#SUITES[@]} -eq 0 ]; then
  SUITES=(object spatial goal l10)
fi

echo "=== smolvla parallel sweep start $(date -Is) ==="
echo "suites: ${SUITES[*]}"
echo "checkpoint: $CHECKPOINT"
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader || true

pids=()
for suite in "${SUITES[@]}"; do
  out="$REPO_ROOT/runs/b-plus-$suite-full-smolvla-$STAMP"
  log="$LOG_DIR/$suite.log"
  echo "--- $suite -> $out (log $log)"
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
    --output "$out" >"$log" 2>&1 &
  pids+=($!)
  echo "$suite $! $out" >> "$LOG_DIR/pids.txt"
  sleep 3
done

echo "started ${#pids[@]} workers: ${pids[*]}"
fail=0
for i in "${!pids[@]}"; do
  if wait "${pids[$i]}"; then
    echo "=== ${SUITES[$i]} done rc=0 $(date -Is)"
  else
    rc=$?
    echo "=== ${SUITES[$i]} done rc=$rc $(date -Is)"
    fail=1
  fi
done
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader || true
echo "=== smolvla parallel sweep done $(date -Is) fail=$fail ==="
exit $fail
