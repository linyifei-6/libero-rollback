#!/usr/bin/env bash
set -euo pipefail

# Run one real paired baseline/rollback episode with an already-installed
# evaluator environment.  Override the variables below for another adapter.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUS_ROOT="${LIBERO_PLUS_ROOT:-"${ROOT_DIR}/../libero-plus"}"
PYTHON_EXECUTABLE="${LIBERO_PYTHON:-"${PLUS_ROOT}/openvla-oft-env/bin/python"}"
LIBERO_ROOT="${LIBERO_CHECKOUT:-"${PLUS_ROOT}/LIBERO-plus"}"
RUNTIME_ROOT="${LIBERO_RUNTIME_ROOT:-"${PLUS_ROOT}/libero-runtime"}"
ADAPTER="${LIBERO_MODEL:-${LIBERO_ADAPTER:-openvla_oft}}"
CHECKPOINT="${LIBERO_CHECKPOINT:-"${PLUS_ROOT}/models/openvla-7b-oft-finetuned-libero-spatial-object-goal-10"}"
CASE_PATH="${LIBERO_CASE:-"${ROOT_DIR}/dataset/v1/cases/libero-10-01-black-bowl-drawer-d0-early.yaml"}"
MAX_STEPS="${LIBERO_MAX_STEPS:-600}"
REPLAN_STEPS="${LIBERO_REPLAN_STEPS:-10}"
DIMENSION="${LIBERO_DIMENSION:-rollback}"
SEVERITY="${LIBERO_SEVERITY:-}"
VIDEO="${LIBERO_VIDEO:-0}"
SEED="${LIBERO_SEED:-0}"
OUTPUT="${LIBERO_OUTPUT:-"${ROOT_DIR}/runs/local-validation-t33-${SEED}"}"

for required_path in "$PYTHON_EXECUTABLE" "$LIBERO_ROOT" "$RUNTIME_ROOT" "$CHECKPOINT" "$CASE_PATH"; do
  if [[ ! -e "$required_path" ]]; then
    echo "required validation path does not exist: $required_path" >&2
    exit 1
  fi
done

cd "$ROOT_DIR"
args=(
  evaluate \
  "$CASE_PATH" \
  --python "$PYTHON_EXECUTABLE" \
  --libero-root "$LIBERO_ROOT" \
  --runtime-root "$RUNTIME_ROOT" \
  --model "$ADAPTER" \
  --suite LIBERO_10 \
  --dimension "$DIMENSION" \
  --checkpoint "$CHECKPOINT" \
  --seed "$SEED" \
  --max-steps "$MAX_STEPS" \
  --replan-steps "$REPLAN_STEPS" \
  --output "$OUTPUT"
)
if [[ -n "$SEVERITY" ]]; then
  args+=(--severity "$SEVERITY")
fi
if [[ "$VIDEO" == "1" ]]; then
  args+=(--video)
fi
uv run libero-rollback "${args[@]}"
