#!/usr/bin/env bash
# Create an isolated per-model Python environment and record its lock file.
#
# Three environments, three responsibilities (README §8, SPEC §12):
#   .venv        static benchmark layer (CPU, light dependencies)
#   .venv-sim    simulation (LIBERO + MuJoCo + robosuite + bddl)
#   .venvs/<m>   ONE environment per model family (inference only)
#
# This script only touches `.venvs/<model>/`. It never installs into `.venv`,
# `.venv-sim` or the model's own checkout, and it never downloads checkpoints:
# the checkpoint path is only recorded (basename, env-var name) in the lock.
#
# Plan by default: without --execute it prints the exact commands and exits
# without creating or changing anything. Environment creation and package
# installation are explicitly opt-in.
#
# Usage:
#   export LIBERO_HOME=/path/to/LIBERO
#   bash scripts/setup_env.sh pi05 --openpi-root /path/to/openpi \
#       --checkpoint /path/to/pi05_libero
#   bash scripts/setup_env.sh pi05 --openpi-root /path/to/openpi \
#       --checkpoint /path/to/pi05_libero --execute
#
# Models: pi05 | pi0 | pi0_fast | openvla_oft | smolvla
# Lock:   configs/envs/<model>.lock  (no absolute paths inside)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL=""
EXECUTE=0
FORCE=0
PYTHON_VERSION="3.11"
ENV_DIR=""
CHECKPOINT=""
OPENPI_ROOT="${OPENPI_ROOT:-}"
WORKSPACE=""
REQUIREMENTS=""
SKIP_LIBERO_CHECK=0
UV_BIN="${UV:-uv}"

usage() {
  cat <<'EOF'
Usage: bash scripts/setup_env.sh <model> [options]

Create .venvs/<model>/ and (with --execute) write configs/envs/<model>.lock.

Arguments:
  <model>                 one of: pi05 pi0 pi0_fast openvla_oft smolvla

Options:
  --python VERSION        base Python for the venv (default: 3.11)
  --env-dir DIR           environment directory (default: <repo>/.venvs/<model>)
  --uv PATH               uv executable (default: $UV, else `uv` on PATH)
  --checkpoint DIR        local checkpoint directory; recorded by basename only,
                          never downloaded and never written as an absolute path
  --openpi-root DIR       OpenPI checkout (pi05 / pi0 / pi0_fast only)
  --workspace DIR         model workspace root (openvla_oft / smolvla)
  --requirements FILE     extra requirements file installed into the env
  --skip-libero-check     do not require LIBERO_HOME (lock records "unknown")
  --execute               actually create the environment and install packages
  --force                 recreate the environment if it already exists
  -h, --help              show this help

Exit codes: 0 plan printed / command succeeded; 1 configuration error; 2 missing
runtime prerequisite (e.g. `uv` not found or --execute without a usable uv).
EOF
}

die() {
  echo "[setup_env] FAIL: $*" >&2
  exit 1
}

info() {
  echo "[setup_env] $*"
}

warn() {
  echo "[setup_env] warning: $*" >&2
}

require_value() {
  local option="$1"
  local value="${2:-}"
  [[ -n "$value" ]] || die "option $option requires a value"
  printf '%s' "$value"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help) usage; exit 0 ;;
      --python) PYTHON_VERSION="$(require_value "$1" "${2:-}")"; shift 2 ;;
      --python=*) PYTHON_VERSION="${1#*=}"; shift ;;
      --env-dir) ENV_DIR="$(require_value "$1" "${2:-}")"; shift 2 ;;
      --env-dir=*) ENV_DIR="${1#*=}"; shift ;;
      --uv) UV_BIN="$(require_value "$1" "${2:-}")"; shift 2 ;;
      --uv=*) UV_BIN="${1#*=}"; shift ;;
      --checkpoint) CHECKPOINT="$(require_value "$1" "${2:-}")"; shift 2 ;;
      --checkpoint=*) CHECKPOINT="${1#*=}"; shift ;;
      --openpi-root) OPENPI_ROOT="$(require_value "$1" "${2:-}")"; shift 2 ;;
      --openpi-root=*) OPENPI_ROOT="${1#*=}"; shift ;;
      --workspace) WORKSPACE="$(require_value "$1" "${2:-}")"; shift 2 ;;
      --workspace=*) WORKSPACE="${1#*=}"; shift ;;
      --requirements) REQUIREMENTS="$(require_value "$1" "${2:-}")"; shift 2 ;;
      --requirements=*) REQUIREMENTS="${1#*=}"; shift ;;
      --skip-libero-check) SKIP_LIBERO_CHECK=1; shift ;;
      --execute) EXECUTE=1; shift ;;
      --force) FORCE=1; shift ;;
      -*) die "unknown option: $1 (see --help)" ;;
      *)
        [[ -z "$MODEL" ]] || die "only one model may be given (got '$MODEL' and '$1')"
        MODEL="$1"
        shift
        ;;
    esac
  done
}

quote() {
  printf '%q' "$1"
}

model_family() {
  case "$MODEL" in
    pi05|pi0|pi0_fast) echo "openpi" ;;
    openvla_oft) echo "openvla_oft" ;;
    smolvla) echo "smolvla" ;;
    *) return 1 ;;
  esac
}

check_prerequisites() {
  [[ -n "$MODEL" ]] || die "missing model argument (see --help)"
  model_family >/dev/null || die "unknown model '$MODEL' (expected pi05, pi0, pi0_fast, openvla_oft or smolvla)"

  if [[ "$SKIP_LIBERO_CHECK" -eq 0 ]]; then
    if [[ -z "${LIBERO_HOME:-}" ]]; then
      die "LIBERO_HOME is not set; export it or pass --skip-libero-check"
    fi
    [[ -d "$LIBERO_HOME" ]] || die "LIBERO_HOME is not a directory: $LIBERO_HOME"
    [[ -f "$LIBERO_HOME/libero/libero/__init__.py" ]] \
      || die "LIBERO_HOME does not look like a LIBERO checkout: $LIBERO_HOME (missing libero/libero/__init__.py)"
    if [[ -f "$REPO_ROOT/scripts/verify_libero.py" ]]; then
      info "asset pin: run \`uv run python scripts/verify_libero.py --libero-home \"\$LIBERO_HOME\"\` before evaluation"
    fi
  else
    warn "--skip-libero-check: the lock will record libero_commit: unknown"
  fi

  case "$(model_family)" in
    openpi)
      if [[ -z "$OPENPI_ROOT" ]]; then
        die "$MODEL needs --openpi-root (or \$OPENPI_ROOT) pointing at the OpenPI checkout"
      fi
      [[ -d "$OPENPI_ROOT" ]] || die "openpi root is not a directory: $OPENPI_ROOT"
      [[ -f "$OPENPI_ROOT/pyproject.toml" ]] \
        || die "openpi root does not contain pyproject.toml: $OPENPI_ROOT"
      ;;
    openvla_oft|smolvla)
      if [[ -n "$WORKSPACE" && ! -d "$WORKSPACE" ]]; then
        die "--workspace is not a directory: $WORKSPACE"
      fi
      ;;
  esac
  if [[ -n "$CHECKPOINT" && ! -d "$CHECKPOINT" ]]; then
    warn "checkpoint directory not found locally: $CHECKPOINT (not downloaded; lock stores the basename only)"
  fi
  if [[ -n "$REQUIREMENTS" && ! -f "$REQUIREMENTS" ]]; then
    die "requirements file not found: $REQUIREMENTS"
  fi
}

default_env_dir() {
  if [[ -n "$ENV_DIR" ]]; then
    printf '%s' "$ENV_DIR"
  else
    printf '%s' "$REPO_ROOT/.venvs/$MODEL"
  fi
}

uv_available() {
  command -v "$UV_BIN" >/dev/null 2>&1
}

install_plan() {
  local env_python="$1"
  local family
  family="$(model_family)"
  echo "[setup_env] install plan (${family}):"
  case "$family" in
    openpi)
      echo "  $(quote "$UV_BIN") pip install --python $(quote "$env_python") -e $(quote "$OPENPI_ROOT")"
      echo "  # XLA_FLAGS=--xla_gpu_deterministic_ops is set by the runner (see configs/models.yaml)"
      ;;
    openvla_oft)
      echo "  # OpenVLA-OFT inference stack: torch 2.2.0 + the LIBERO-plus evaluation scripts"
      echo "  #   (the adapter imports the official OFT eval module from the workspace at load time;"
      echo "  #    no pip package is required for it). Freeze the exact stack with --requirements."
      if [[ -n "$REQUIREMENTS" ]]; then
        echo "  $(quote "$UV_BIN") pip install --python $(quote "$env_python") -r $(quote "$REQUIREMENTS")"
      else
        echo "  # TODO: pass --requirements <locked requirements.txt> once the OFT stack is frozen (Phase 2)"
      fi
      ;;
    smolvla)
      echo "  # SmolVLA / LeRobot inference stack (checkpoint-defined); freeze it with --requirements."
      if [[ -n "$REQUIREMENTS" ]]; then
        echo "  $(quote "$UV_BIN") pip install --python $(quote "$env_python") -r $(quote "$REQUIREMENTS")"
      else
        echo "  # TODO: pass --requirements <locked requirements.txt> once the LeRobot stack is frozen (Phase 2)"
      fi
      ;;
  esac
}

libero_commit() {
  if [[ "$SKIP_LIBERO_CHECK" -eq 0 ]] && command -v git >/dev/null 2>&1; then
    git -C "$LIBERO_HOME" rev-parse HEAD 2>/dev/null || echo "unknown"
  else
    echo "unknown"
  fi
}

write_lock() {
  local env_dir="$1"
  local env_python="$env_dir/bin/python"
  local lock_path="$REPO_ROOT/configs/envs/$MODEL.lock"
  local python_version uv_version packages
  python_version="$("$env_python" -c 'import platform; print(platform.python_version())')"
  uv_version="$( ("$UV_BIN" --version 2>/dev/null) || echo unknown)"
  packages="$( ("$UV_BIN" pip freeze --python "$env_python" 2>/dev/null) || "$env_python" -m pip freeze 2>/dev/null || true)"
  local checkpoint_name=""
  if [[ -n "$CHECKPOINT" ]]; then
    checkpoint_name="$(basename "$CHECKPOINT")"
  fi
  mkdir -p "$REPO_ROOT/configs/envs"
  {
    echo "schema_version: 1"
    echo "model: $MODEL"
    echo "generated_by: scripts/setup_env.sh --execute"
    echo "generated_at: \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\""
    echo "python_version: \"$python_version\""
    echo "uv_version: \"$uv_version\""
    echo "adapter: libero_rollback.policies.$(adapter_module)"
    echo "libero_commit: $(libero_commit)"
    if [[ -n "$checkpoint_name" ]]; then
      echo "checkpoint:"
      echo "  env: $(checkpoint_env_name)"
      echo "  name: \"$checkpoint_name\""
      echo "  digest: null"
    else
      echo "checkpoint: null"
    fi
    echo "packages:"
    if [[ -n "$packages" ]]; then
      while IFS= read -r line; do
        [[ -n "$line" ]] && printf '  - "%s"\n' "$line"
      done < <(printf '%s\n' "$packages" | sort)
    else
      echo "  []"
    fi
    echo "packages_sha256: null"
    echo "notes: \"generated on the machine that will run the model; no absolute paths recorded\""
  } > "$lock_path"
  info "wrote lock: $lock_path"
}

adapter_module() {
  case "$MODEL" in
    pi05|pi0|pi0_fast) echo "pi05" ;;
    openvla_oft) echo "openvla_oft" ;;
    smolvla) echo "smolvla" ;;
  esac
}

checkpoint_env_name() {
  case "$MODEL" in
    pi05) echo "PI05_CHECKPOINT" ;;
    pi0) echo "PI0_CHECKPOINT" ;;
    pi0_fast) echo "PI0_FAST_CHECKPOINT" ;;
    openvla_oft) echo "OPENVLA_OFT_CHECKPOINT" ;;
    smolvla) echo "SMOLVLA_CHECKPOINT" ;;
  esac
}

main() {
  parse_args "$@"
  check_prerequisites
  local env_dir env_python
  env_dir="$(default_env_dir)"
  env_python="$env_dir/bin/python"

  info "model:        $MODEL ($(model_family))"
  info "environment:  $env_dir"
  info "python:       $PYTHON_VERSION"
  info "lock:         $REPO_ROOT/configs/envs/$MODEL.lock (written only with --execute)"

  if ! uv_available; then
    echo "[setup_env] missing prerequisite: uv not found (install uv, or pass --uv /path/to/uv)" >&2
    return 2
  fi

  local create_cmd
  create_cmd="$(quote "$UV_BIN") venv --python $(quote "$PYTHON_VERSION") $(quote "$env_dir")"
  if [[ -e "$env_dir" && "$FORCE" -eq 0 ]]; then
    info "environment already exists; keeping it (use --force to recreate)"
  else
    echo "[setup_env] plan: $create_cmd"
  fi
  install_plan "$env_python"

  if [[ "$EXECUTE" -eq 0 ]]; then
    info "dry-run: nothing was created or installed. Re-run with --execute to apply."
    return 0
  fi

  set -x
  if [[ -e "$env_dir" && "$FORCE" -eq 1 ]]; then
    "$UV_BIN" venv --python "$PYTHON_VERSION" --allow-existing "$env_dir"
  else
    "$UV_BIN" venv --python "$PYTHON_VERSION" "$env_dir"
  fi
  case "$(model_family)" in
    openpi)
      "$UV_BIN" pip install --python "$env_python" -e "$OPENPI_ROOT"
      ;;
    openvla_oft|smolvla)
      if [[ -n "$REQUIREMENTS" ]]; then
        "$UV_BIN" pip install --python "$env_python" -r "$REQUIREMENTS"
      else
        set +x
        warn "no package install requested: pass --requirements for this model family"
        info "the environment was created; the lock will record its current (small) package set"
      fi
      ;;
  esac
  set +x
  write_lock "$env_dir"
  info "done. Activate with: source $(quote "$env_dir")/bin/activate"
}

main "$@"
