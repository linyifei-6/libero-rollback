"""Run-level provenance record (repo sha, checkpoint digest, runtime, GPU flags).

``docs/protocol.md`` §7 and the leaderboard contract require a
``provenance.json`` per run.  The runner calls :func:`write_run_provenance`
automatically at the end of :func:`libero_rollback.runner.run_matrix`; the
standalone CLI in ``scripts/write_provenance.py`` reuses the same code for runs
produced before this module existed.

Everything here is best effort and never raises: a missing git checkout or an
un-importable package is recorded as ``null`` with a reason, never invented.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_sha(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"commit": None, "dirty": None, "reason": "no path"}
    try:
        sha = subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "-C", str(path), "status", "--porcelain"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
        return {"commit": sha, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None, "reason": "not a git checkout or git missing"}


def package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in ("torch", "numpy", "lerobot", "transformers", "robosuite", "mujoco", "bddl"):
        try:
            module = __import__(name)
            versions[name] = getattr(module, "__version__", "unknown")
        except Exception:  # noqa: BLE001 - version probe is best effort
            versions[name] = None
    return versions


def libero_counts(libero_home: Path | None) -> dict[str, int] | None:
    if libero_home is None:
        return None
    root = Path(libero_home) / "libero" / "libero"
    bddl_dir = root / "bddl_files"
    init_dir = root / "init_files"
    return {
        "bddl_files": len(list(bddl_dir.rglob("*.bddl"))) if bddl_dir.is_dir() else 0,
        "pruned_init_files": (
            len(list(init_dir.rglob("*.pruned_init"))) if init_dir.is_dir() else 0
        ),
    }


def checkpoint_digests(checkpoint: str | Path | None) -> dict[str, Any]:
    if checkpoint is None:
        return {"path": None}
    target = Path(checkpoint)
    result: dict[str, Any] = {"path": str(target)}
    if target.is_dir():
        weights = sorted(target.glob("*.safetensors")) or sorted(target.glob("*.pt"))
        result["files"] = [
            {"name": p.name, "bytes": p.stat().st_size, "sha256": sha256_file(p)} for p in weights
        ]
    elif target.is_file():
        result["files"] = [
            {"name": target.name, "bytes": target.stat().st_size, "sha256": sha256_file(target)}
        ]
    else:
        result["reason"] = "checkpoint path does not exist"
    return result


def build_provenance(
    run: Path,
    *,
    checkpoint: str | Path | None = None,
    libero_home: str | Path | None = None,
) -> dict[str, Any]:
    run = Path(run)
    manifest = run / "run-manifest.json"
    manifest_data: dict[str, Any] = {}
    if manifest.is_file():
        try:
            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest_data = {}
    episodes = run / "episodes.jsonl"
    jsonl_lines = None
    if episodes.is_file():
        jsonl_lines = sum(
            1
            for line in episodes.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run.resolve()),
        "runner_repo": git_sha(REPO_ROOT),
        "run_manifest_sha256": sha256_file(manifest),
        "matrix_json_sha256": sha256_file(run / "matrix.json"),
        "run_manifest": {
            key: manifest_data.get(key)
            for key in ("argv", "protocol_version", "dataset_version", "defaults")
            if key in manifest_data
        },
        "checkpoint": checkpoint_digests(checkpoint),
        "libero": {
            "home": str(libero_home) if libero_home else os.environ.get("LIBERO_HOME"),
            "git": git_sha(Path(libero_home) if libero_home else None),
            "counts": libero_counts(Path(libero_home) if libero_home else None),
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "packages": package_versions(),
            "gpu": {
                "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
                "CUDA_DEVICE_ORDER": os.environ.get("CUDA_DEVICE_ORDER"),
                "NCCL_P2P_DISABLE": os.environ.get("NCCL_P2P_DISABLE"),
                "NCCL_SHM_DISABLE": os.environ.get("NCCL_SHM_DISABLE"),
                "MUJOCO_GL": os.environ.get("MUJOCO_GL"),
            },
        },
        "episodes": {
            "jsonl_lines": jsonl_lines,
            "case_dirs": sum(1 for _ in run.rglob("summary.json")),
        },
    }


def write_run_provenance(
    run: Path,
    *,
    checkpoint: str | Path | None = None,
    libero_home: str | Path | None = None,
) -> Path | None:
    """Write ``<run>/provenance.json``; never raise (returns None on failure)."""
    try:
        payload = build_provenance(run, checkpoint=checkpoint, libero_home=libero_home)
        out = Path(run) / "provenance.json"
        out.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return out
    except Exception:  # noqa: BLE001 - provenance must never break a run
        return None
