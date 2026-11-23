#!/usr/bin/env bash
# SmolVLA B-plus smoke: same experimental parameters as the running pi05 queue,
# only the policy/checkpoint/interpreter differ.
set -uo pipefail
REPO_ROOT=/home/tarowang/workspace/roboot/libero-rollback-2
PY=/home/tarowang/venvs/smolvla/bin/python
LIBERO_HOME=/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero
CHECKPOINT=/home/tarowang/workspace/roboot/libero-plus/models/smolvla_libero

export MUJOCO_GL=osmesa
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export PYTHONPATH="$REPO_ROOT/src:$LIBERO_HOME"
export TOKENIZERS_PARALLELISM=false

cd "$REPO_ROOT"
"$PY" scripts/run_b_plus.py \
  --suite goal --split core \
  --case-ids bp-goal-t030-c0 bp-goal-t030-l0 bp-goal-t030-o2l1s1 \
  --settle-after-injection 10 \
  --video --stop-on-recovery --resume \
  --policy smolvla --checkpoint "$CHECKPOINT" \
  --libero-home "$LIBERO_HOME" \
  --output runs/smolvla-smoke-20261120 2>&1 | tee runs/smolvla-smoke-20261120.log
echo "SMOKE EXIT rc=${PIPESTATUS[0]}"
