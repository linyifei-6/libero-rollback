#!/usr/bin/env bash
# Archive the SmolVLA B-plus sweep into experiments/b-plus-smolvla-<STAMP>/.
#
# Produces:
#   summary.json     machine-readable aggregate (all four suites merged)
#   summary.md       the same aggregate as Markdown tables
#   provenance.json  matrix/checkpoint sha256, env versions, run dirs, counts
#   <suite>/index.html  self-contained per-suite report (videos linked relatively)
#
# Usage: bash scripts/archive_b_plus_smolvla.sh [stamp]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="${1:-20261120}"
OUT="$REPO_ROOT/experiments/b-plus-smolvla-$STAMP"
SUITES=(goal object spatial l10)
SMOLVLA_PY="${SMOLVLA_PY:-/home/tarowang/venvs/smolvla/bin/python}"
CHECKPOINT="${SMOLVLA_CHECKPOINT:-/home/tarowang/workspace/roboot/libero-plus/models/smolvla_libero}"
mkdir -p "$OUT"

RUN_ARGS=()
for suite in "${SUITES[@]}"; do
  RUN_ARGS+=("$REPO_ROOT/runs/b-plus-$suite-full-smolvla-$STAMP")
done

echo "== aggregate"
python3 "$REPO_ROOT/scripts/build_b_plus_summary.py" "${RUN_ARGS[@]}" \
  --title "SmolVLA · B-plus full ($STAMP)" \
  --json "$OUT/summary.json" | grep -v '^wrote ' > "$OUT/summary.md"
cp "$OUT/summary.md" "$REPO_ROOT/runs/b-plus-smolvla-$STAMP.summary.md"

echo "== per-suite html"
for suite in "${SUITES[@]}"; do
  python3 "$REPO_ROOT/scripts/build_b_plus_report.py" \
    --run "$REPO_ROOT/runs/b-plus-$suite-full-smolvla-$STAMP" \
    --out "$OUT/$suite" \
    --title "SmolVLA · B-plus $suite · $STAMP"
done

echo "== provenance"
python3 - "$REPO_ROOT" "$STAMP" "$OUT" "$SMOLVLA_PY" "$CHECKPOINT" <<'PY'
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1])
stamp = sys.argv[2]
out = Path(sys.argv[3])
smolvla_py = sys.argv[4]
checkpoint = Path(sys.argv[5])
suites = ["goal", "object", "spatial", "l10"]
expected = {"goal": 164, "object": 215, "spatial": 197, "l10": 159}


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()
    except Exception:
        return None


def environment_version(package: str) -> str | None:
    code = (
        "import importlib.metadata as md\n"
        "try:\n"
        f"    print(md.version({package!r}))\n"
        "except Exception:\n"
        "    print('')\n"
    )
    try:
        return subprocess.check_output([smolvla_py, "-c", code], text=True).strip() or None
    except Exception:
        return None


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.name


runs = {}
for suite in suites:
    run = repo / "runs" / f"b-plus-{suite}-full-smolvla-{stamp}"
    summaries = list(run.glob("*/**/summary.json")) if run.is_dir() else []
    runs[suite] = {
        "path": repo_relative(run),
        "planned": expected[suite],
        "completed": len(summaries),
        "episodes_sha256": sha256(run / "episodes.jsonl"),
    }

matrix = repo / "dataset" / "matrices" / "plus" / "b-matrix-plus.csv"
provenance = {
    "schema_version": 1,
    "generated_at": subprocess.check_output(["date", "-Is"], text=True).strip(),
    "experiment": f"b-plus-smolvla-{stamp}",
    "purpose": "SmolVLA on the full LIBERO-Plus O2 B-plus matrix; protocol identical to the pi05 settle sweep",
    "git_commit": git("rev-parse", "HEAD"),
    "git_dirty": bool(git("status", "--porcelain")),
    "matrix": {
        "path": repo_relative(matrix),
        "sha256": sha256(matrix),
        "rows": sum(1 for _ in matrix.open(encoding="utf-8")) - 1,
    },
    "model": {
        "policy": "smolvla",
        # the checkpoint lives outside this checkout; record a workspace-relative
        # label plus the weights sha256 instead of a host-absolute path
        "checkpoint": f"libero-plus/models/{checkpoint.name}",
        "weights_sha256": sha256(checkpoint / "model.safetensors"),
        "config": json.loads((checkpoint / "config.json").read_text()),
    },
    "environment": {
        "python": subprocess.check_output([smolvla_py, "-V"], text=True).strip(),
        "interpreter": "~/venvs/smolvla/bin/python",
        "MUJOCO_GL": os.environ.get("MUJOCO_GL", "osmesa"),
        "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE", "1"),
        "versions": {
            package: environment_version(package)
            for package in ("torch", "lerobot", "transformers", "mujoco", "robosuite", "numpy", "bddl")
        },
    },
    "runs": runs,
    "protocol": {
        "matrix_split": "both",
        "arms": ["rollback", "c0", "l0"],
        "max_steps": 600,
        "repair_window": 300,
        "delay_steps": 10,
        "replan": 10,
        "camera": 256,
        "settle_steps": 10,
        "settle_after_injection": 10,
        "seed": 0,
        "init_row": 0,
        "stop_on_recovery": True,
        "video_fps": 20,
        "fresh_arm": "not executable in run_b_plus.py; matches the pi05 sweep",
    },
}
(out / "provenance.json").write_text(
    json.dumps(provenance, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(f"wrote {out / 'provenance.json'}")
PY

echo "== sanitize host paths"
python3 - "$REPO_ROOT" "$OUT" <<'PY'
import sys
from pathlib import Path

repo = Path(sys.argv[1])
out = Path(sys.argv[2])
replacements = [
    (str(repo) + "/", ""),
    (str(repo.parent) + "/", ""),
    ("/home/tarowang/", "~/"),
    ("/home/tarowang", "~"),
]
for path in out.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".html", ".txt"}:
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    new = text
    for old, replacement in replacements:
        new = new.replace(old, replacement)
    if new != text:
        path.write_text(new, encoding="utf-8")
        print(f"sanitized {path.relative_to(out)}")
PY

echo "== done: $OUT"
