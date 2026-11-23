#!/usr/bin/env bash
# Protocol-sensitivity probe: the first core rollback case of every task (38),
# re-run with --replan 5 (SmolVLA's own historical A-suite used replan=5).
#
# Purpose: the main sweep uses replan=10 to match the pi05 protocol, but
# SmolVLA's checkpoint has n_action_steps=1 and its A-suite numbers used 5.
# This probe quantifies how much of the low trigger rate is a protocol artifact
# versus model capability.  Only `replan` differs; everything else is identical.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/tarowang/venvs/smolvla/bin/python"
LIBERO_HOME="/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero"
CHECKPOINT="/home/tarowang/workspace/roboot/libero-plus/models/smolvla_libero"
IDS="$REPO_ROOT/runs/b-plus-smolvla-first-rollback-ids.txt"
STAMP="${STAMP:-20261120}"
LOG="$REPO_ROOT/runs/b-plus-smolvla-replan5-probe-$STAMP.log"

export MUJOCO_GL=osmesa
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$REPO_ROOT/src:$LIBERO_HOME"
export LIBERO_HOME

for suite in goal object spatial l10; do
  echo "=== replan5 probe $suite start $(date -Is)" | tee -a "$LOG"
  "$PY" "$REPO_ROOT/scripts/run_b_plus.py" \
    --suite "$suite" \
    --split core \
    --case-ids-file "$IDS" \
    --replan 5 \
    --settle-after-injection 10 \
    --video --stop-on-recovery --resume \
    --policy smolvla --checkpoint "$CHECKPOINT" \
    --libero-home "$LIBERO_HOME" \
    --output "$REPO_ROOT/runs/b-plus-$suite-replan5-probe-smolvla-$STAMP" 2>&1 | tee -a "$LOG"
  echo "=== replan5 probe $suite end rc=${PIPESTATUS[0]} $(date -Is)" | tee -a "$LOG"
done
