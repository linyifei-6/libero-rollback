#!/usr/bin/env bash
# Control probe: run only the 38 C0 (no-op) cases for SmolVLA.
#
# Purpose: the 0/… O2 recovery can only be read as "cannot repair" if the model
# can hold a completed state when nothing is injected.  The main sweep runs its
# C0 cases last; this probe gets them early without changing any parameter.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/tarowang/venvs/smolvla/bin/python"
LIBERO_HOME="/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero"
CHECKPOINT="/home/tarowang/workspace/roboot/libero-plus/models/smolvla_libero"
IDS="$REPO_ROOT/runs/b-plus-smolvla-c0-ids.txt"
STAMP="${STAMP:-20261120}"
LOG="$REPO_ROOT/runs/b-plus-smolvla-c0-probe-$STAMP.log"

export MUJOCO_GL=osmesa
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$REPO_ROOT/src:$LIBERO_HOME"
export LIBERO_HOME

for suite in goal object spatial l10; do
  echo "=== c0 probe $suite start $(date -Is)" | tee -a "$LOG"
  "$PY" "$REPO_ROOT/scripts/run_b_plus.py" \
    --suite "$suite" \
    --split both \
    --case-ids-file "$IDS" \
    --settle-after-injection 10 \
    --video --stop-on-recovery --resume \
    --policy smolvla --checkpoint "$CHECKPOINT" \
    --libero-home "$LIBERO_HOME" \
    --output "$REPO_ROOT/runs/b-plus-$suite-c0-probe-smolvla-$STAMP" 2>&1 | tee -a "$LOG"
  echo "=== c0 probe $suite end rc=${PIPESTATUS[0]} $(date -Is)" | tee -a "$LOG"
done
