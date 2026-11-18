#!/usr/bin/env bash
# Reproduce the Phase-1 evaluation pipeline (default: B-suite smoke / lite proxy).
#
# Plan by default: prints the exact ordered commands and reports which
# prerequisites exist in this checkout. Add --execute to actually run them.
#
#   export LIBERO_HOME=/path/to/LIBERO
#   bash scripts/repro.sh --policy pi05 --split lite
#   bash scripts/repro.sh --policy pi05 --split lite --execute
#
# Pipeline (docs/protocol.md):
#   1. static dataset validation      (no simulation, no GPU)
#   2. static test suite              (pytest, no simulation)
#   3. LIBERO asset pin verification  (commit / worktree / counts / sha256)
#   4. dry-run plan                   (plan.json is NOT evidence)
#   5. B-suite evaluation             (simulation + model environment)
#   6. report / leaderboard validate  (Phase 2; optional)
#
# Phase 1 executes the B suite only. The `lite` split's A/C/D parts and the
# exact lite case selection (`dataset/lite.yaml`) are wired in later; until the
# runner accepts `--split lite`, `--split lite` is approximated by `--max-cases`.
#
# Exit codes: 0 plan complete and all required steps available (or execution
# succeeded); 2 plan printed but a required prerequisite is missing (the
# checkout cannot reproduce the run yet); 1 configuration / execution error.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY="pi05"
SPLIT="lite"
OUTPUT=""
DATASET="dataset"
MATRIX="dataset/matrices/b-matrix.csv"
EXECUTE=0
VIDEO=1
ALLOW_DIRTY=0
SKIP_STATIC=0
SKIP_VERIFY=0
LITE_CASES=10
MISSING_REQUIRED=0
MISSING_OPTIONAL=0

usage() {
  cat <<'EOF'
Usage: bash scripts/repro.sh [options]

Options:
  --policy NAME       policy adapter: pi05 | smolvla | openvla_oft | none
                      (default: pi05; `none` runs no model, useful for a
                      simulation/injection smoke test)
  --split NAME        lite | b (default: lite; Phase 1 executes the B suite
                      only, `lite` maps to --max-cases 10)
  --output DIR        run output directory (default: runs/<split>-<policy>)
  --dataset DIR       dataset root (default: dataset)
  --matrix PATH       B matrix CSV (default: dataset/matrices/b-matrix.csv)
  --max-cases N       cap for --split lite (default: 10)
  --video / --no-video  record videos (default: on; `--no-video` for smoke)
  --allow-dirty       pass --allow-dirty to the LIBERO verify step
                      (development checkouts only)
  --skip-static       skip dataset validation and pytest
  --skip-verify       skip LIBERO asset verification
  --execute           actually run the plan (default: print it only)
  -h, --help          show this help

Environment:
  LIBERO_HOME         upstream LIBERO checkout (required by steps 3 and 5)
  LIBERO_PYTHON       interpreter able to import LIBERO (fallback for the runner)
  MUJOCO_GL           egl (GPU) or osmesa (CPU/CI); default: egl
EOF
}

die() {
  echo "[repro] FAIL: $*" >&2
  exit 1
}

info() {
  echo "[repro] $*"
}

warn() {
  echo "[repro] warning: $*" >&2
}

require_value() {
  local option="$1"
  local value="${2:-}"
  [[ -n "$value" ]] || die "option $option requires a value"
  printf '%s' "$value"
}

quote() {
  printf '%q' "$1"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help) usage; exit 0 ;;
      --policy|--model) POLICY="$(require_value "$1" "${2:-}")"; shift 2 ;;
      --policy=*|--model=*) POLICY="${1#*=}"; shift ;;
      --split) SPLIT="$(require_value "$1" "${2:-}")"; shift 2 ;;
      --split=*) SPLIT="${1#*=}"; shift ;;
      --output) OUTPUT="$(require_value "$1" "${2:-}")"; shift 2 ;;
      --output=*) OUTPUT="${1#*=}"; shift ;;
      --dataset) DATASET="$(require_value "$1" "${2:-}")"; shift 2 ;;
      --dataset=*) DATASET="${1#*=}"; shift ;;
      --matrix) MATRIX="$(require_value "$1" "${2:-}")"; shift 2 ;;
      --matrix=*) MATRIX="${1#*=}"; shift ;;
      --max-cases) LITE_CASES="$(require_value "$1" "${2:-}")"; shift 2 ;;
      --max-cases=*) LITE_CASES="${1#*=}"; shift ;;
      --video) VIDEO=1; shift ;;
      --no-video) VIDEO=0; shift ;;
      --allow-dirty) ALLOW_DIRTY=1; shift ;;
      --skip-static) SKIP_STATIC=1; shift ;;
      --skip-verify) SKIP_VERIFY=1; shift ;;
      --execute) EXECUTE=1; shift ;;
      -*) die "unknown option: $1 (see --help)" ;;
      *) die "unexpected argument: $1 (see --help)" ;;
    esac
  done
}

validate_config() {
  case "$POLICY" in
    pi05|smolvla|openvla_oft|none) ;;
    *)
      die "invalid --policy '$POLICY' (the Phase-1 runner supports pi05, smolvla, openvla_oft, none)"
      ;;
  esac
  case "$SPLIT" in
    lite|b) ;;
    *) die "invalid --split '$SPLIT' (Phase 1 supports lite and b)" ;;
  esac
  [[ "$LITE_CASES" =~ ^[1-9][0-9]*$ ]] || die "--max-cases must be a positive integer"
  if [[ -z "$OUTPUT" ]]; then
    OUTPUT="$REPO_ROOT/runs/$SPLIT-$POLICY"
  fi
  if [[ ! -e "$REPO_ROOT/$MATRIX" && "$MATRIX" != /* ]]; then
    warn "matrix not found (yet): $REPO_ROOT/$MATRIX"
  fi
}

has_file() {
  [[ -e "$REPO_ROOT/$1" ]]
}

# step <label> <prerequisite|-> <required|optional> <command>
step() {
  local label="$1"
  local prerequisite="$2"
  local requirement="$3"
  local command="$4"

  if [[ -n "$prerequisite" && "$prerequisite" != "-" ]] && ! has_file "$prerequisite"; then
    if [[ "$requirement" == "required" ]]; then
      echo "[missing] $label"
      echo "          prerequisite not in this checkout yet: $prerequisite"
      MISSING_REQUIRED=$((MISSING_REQUIRED + 1))
    else
      echo "[skip]    $label"
      echo "          optional prerequisite not in this checkout yet: $prerequisite"
      MISSING_OPTIONAL=$((MISSING_OPTIONAL + 1))
    fi
    return 0
  fi

  echo "[step] $label"
  echo "       $command"
  if [[ "$EXECUTE" -eq 1 ]]; then
    ( cd "$REPO_ROOT" && bash -lc "$command" )
  fi
}

build_plan() {
  local video_flag=""
  if [[ "$VIDEO" -eq 1 ]]; then
    video_flag=" --video"
  else
    video_flag=" --no-video"
  fi
  local dirty_flag=""
  if [[ "$ALLOW_DIRTY" -eq 1 ]]; then
    dirty_flag=" --allow-dirty"
  fi
  local max_cases_flag=""
  if [[ "$SPLIT" == "lite" ]]; then
    max_cases_flag=" --max-cases $LITE_CASES"
  fi
  local output_q dataset_q matrix_q
  output_q="$(quote "$OUTPUT")"
  dataset_q="$(quote "$DATASET")"
  matrix_q="$(quote "$MATRIX")"

  info "pipeline: split=$SPLIT policy=$POLICY"
  info "output:   $OUTPUT"
  info "mode:     $([[ "$EXECUTE" -eq 1 ]] && echo execute || echo plan-only)"

  if [[ "$SKIP_STATIC" -eq 0 ]]; then
    step "static dataset validation" "scripts/validate_dataset.py" required \
      "uv run python scripts/validate_dataset.py --dataset $dataset_q"
    step "static test suite" "tests" required \
      "uv run pytest"
  else
    info "static steps skipped (--skip-static)"
  fi

  if [[ "$SKIP_VERIFY" -eq 0 ]]; then
    if [[ -z "${LIBERO_HOME:-}" ]]; then
      echo "[missing] LIBERO asset verification"
      echo "          LIBERO_HOME is not set; export it or pass --skip-verify"
      MISSING_REQUIRED=$((MISSING_REQUIRED + 1))
    else
      step "LIBERO asset pin verification" "scripts/verify_libero.py" required \
        "uv run python scripts/verify_libero.py --libero-home $(quote "$LIBERO_HOME")$dirty_flag"
    fi
  else
    info "LIBERO verification skipped (--skip-verify)"
  fi

  step "dry-run plan (plan.json is not evidence)" "scripts/run_b_matrix.py" required \
    "uv run python scripts/run_b_matrix.py --dry-run --matrix $matrix_q --output $(quote "$OUTPUT/plan")"
  step "evaluate B suite (split $SPLIT)" "scripts/run.sh" required \
    "bash scripts/run.sh --execute --policy $POLICY --matrix $matrix_q --output $output_q$max_cases_flag$video_flag"
  step "build report" "src/libero_rollback/cli.py" optional \
    "uv run libero-rollback report --run $output_q --out $(quote "$OUTPUT/report")"
  step "leaderboard validate" "src/libero_rollback/cli.py" optional \
    "uv run libero-rollback leaderboard validate --run $output_q"

  echo ""
  if [[ "$MISSING_REQUIRED" -gt 0 ]]; then
    info "$MISSING_REQUIRED required step(s) unavailable, $MISSING_OPTIONAL optional step(s) unavailable"
    info "the checkout cannot reproduce this run yet (Phase 1 work in progress)"
    return 2
  fi
  info "all required steps available ($MISSING_OPTIONAL optional step(s) unavailable)"
  if [[ "$EXECUTE" -eq 0 ]]; then
    info "plan only; re-run with --execute to apply"
  fi
  return 0
}

main() {
  parse_args "$@"
  validate_config
  if [[ -z "${MUJOCO_GL:-}" ]]; then
    export MUJOCO_GL="egl"
    info "MUJOCO_GL not set; using egl (use osmesa on CPU/CI)"
  fi
  local status=0
  build_plan || status=$?
  exit "$status"
}

main "$@"
