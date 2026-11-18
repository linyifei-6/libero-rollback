#!/usr/bin/env python3
"""Environment smoke test for the LIBERO-Rollback runner.

What it does
------------
1. resolves the upstream LIBERO checkout and writes a **repo-local**
   ``LIBERO_CONFIG_PATH/config.yaml`` (five keys: ``benchmark_root``,
   ``bddl_files``, ``init_states``, ``datasets``, ``assets``) — it never writes
   ``~/.libero``;
2. selects one frozen A-matrix task per LIBERO suite (override with
   ``--suite`` / ``--task-idx``);
3. imports ``robosuite`` / ``mujoco`` / ``libero.libero.envs`` and creates an
   ``OffScreenRenderEnv`` per task, resets it, applies the official
   ``.pruned_init`` row and asserts ``check_success() is False`` at the initial
   state (certificate C2 pre-check).

Failure semantics (no fake success)
-----------------------------------
* missing assets / unusable interpreter  -> exit ``2`` with ``environment
  unavailable`` and a copy-paste repro command;
* initial ``check_success()`` true or an exception while stepping the env ->
  exit ``1``;
* ``--static-only`` validates the paths/config/matrix selection **without**
  importing the simulation stack and prints ``static_only``; it never claims
  that the environment was verified.

Nothing here is hardcoded to a host path: ``--libero-home`` / ``LIBERO_HOME`` and
``--config-dir`` / ``LIBERO_CONFIG_PATH`` drive everything.

Usage::

    LIBERO_HOME=/path/to/LIBERO python scripts/smoke_env.py
    LIBERO_HOME=/path/to/LIBERO python scripts/smoke_env.py --static-only
    LIBERO_HOME=/path/to/LIBERO python scripts/smoke_env.py --suite l10 --json /tmp/smoke.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_DIR = REPO_ROOT / ".cache" / "libero"
DEFAULT_MATRIX = REPO_ROOT / "dataset" / "matrices" / "a-matrix.csv"

SUITE_DIRS = {
    "goal": "libero_goal",
    "object": "libero_object",
    "spatial": "libero_spatial",
    "l10": "libero_10",
}
SUITE_ORDER = ("goal", "object", "spatial", "l10")

INIT_ROW_PROBE = """
import json, sys
import numpy as np
import torch

payload = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
array = payload.detach().cpu().numpy() if torch.is_tensor(payload) else np.asarray(payload)
row = np.asarray(array[int(sys.argv[2])], dtype=np.float64)
print(json.dumps({"shape": [int(size) for size in array.shape], "row": [float(v) for v in row]}))
"""


class EnvironmentUnavailable(RuntimeError):
    """The simulation stack (or its assets) is not usable on this machine."""


def resolve_asset_root(libero_home: Path) -> Path:
    """Find the directory that directly contains ``bddl_files``/``init_files``."""

    for candidate in (libero_home / "libero" / "libero", libero_home, libero_home / "libero"):
        if (candidate / "bddl_files").is_dir() and (candidate / "init_files").is_dir():
            return candidate
    raise EnvironmentUnavailable(
        f"cannot locate bddl_files/init_files under LIBERO_HOME={libero_home}; "
        "point --libero-home at the upstream LIBERO repository root"
    )


def resolve_config_dir(cli_value: Path | None) -> Path:
    raw = cli_value or os.environ.get("LIBERO_CONFIG_PATH") or DEFAULT_CONFIG_DIR
    config_dir = Path(raw).expanduser()
    forbidden = Path.home() / ".libero"
    if config_dir.resolve() == forbidden.resolve():
        raise EnvironmentUnavailable(
            "LIBERO_CONFIG_PATH must be repo-local; refusing to write the shared ~/.libero config"
        )
    return config_dir


def write_libero_config(config_dir: Path, asset_root: Path) -> Path:
    """Write the five-key repo-local LIBERO config; never touches ~/.libero."""

    import yaml

    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config = {
        "benchmark_root": str(asset_root),
        "bddl_files": str(asset_root / "bddl_files"),
        "init_states": str(asset_root / "init_files"),
        "datasets": str(asset_root.parent / "datasets"),
        "assets": str(asset_root / "assets"),
    }
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path


def bootstrap_environment(libero_home: Path, config_dir: Path) -> dict:
    """Set the env vars needed before robosuite/libero import, write config."""

    os.environ.setdefault("MUJOCO_GL", "osmesa")
    os.environ["PYTHONPATH"] = os.pathsep.join(
        [str(libero_home), os.environ.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    config_path = write_libero_config(config_dir, resolve_asset_root(libero_home))
    os.environ["LIBERO_CONFIG_PATH"] = str(config_dir)
    if str(libero_home) not in sys.path:
        sys.path.insert(0, str(libero_home))
    return {
        "libero_home": str(libero_home),
        "libero_config_path": str(config_path),
        "pythonpath": os.environ["PYTHONPATH"],
        "mujoco_gl": os.environ.get("MUJOCO_GL"),
    }


def select_tasks(matrix_path: Path, suites: list[str], task_idx: int | None) -> list[dict]:
    """Pick one deterministic A-matrix task per requested suite."""

    try:
        with matrix_path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
    except OSError as error:
        raise EnvironmentUnavailable(f"cannot read A matrix {matrix_path}: {error}") from error
    wanted = (
        [suite for suite in SUITE_ORDER if suite in set(suites)] if suites else list(SUITE_ORDER)
    )
    selected: list[dict] = []
    for suite in wanted:
        candidates = [row for row in rows if row["suite"] == suite]
        if task_idx is not None:
            candidates = [row for row in candidates if int(row["task_idx"]) == task_idx]
        if not candidates:
            raise EnvironmentUnavailable(
                f"no A-matrix task for suite={suite!r} task_idx={task_idx!r}"
            )
        selected.append(sorted(candidates, key=lambda row: int(row["task_idx"]))[0])
    return selected


def load_init_row(path: Path, row_index: int) -> tuple[list[int], list[float]]:
    """Load one official ``.pruned_init`` row; requires torch (explicit error otherwise)."""

    try:
        import numpy as np
        import torch

        payload = torch.load(str(path), map_location="cpu", weights_only=False)
        array = payload.detach().cpu().numpy() if torch.is_tensor(payload) else np.asarray(payload)
        if array.ndim != 2 or row_index >= array.shape[0]:
            raise ValueError(
                f".pruned_init shape {list(array.shape)} cannot supply row {row_index}"
            )
        row = np.asarray(array[row_index], dtype=np.float64)
        return [int(size) for size in array.shape], [float(value) for value in row]
    except ImportError as error:
        raise EnvironmentUnavailable(
            f"cannot load {path.name}: torch is not importable in {sys.executable} "
            f"({error}); install the simulation stack or pass a --libero-python interpreter"
        ) from error


def _probe_init_row(python: str, path: Path, row_index: int) -> tuple[list[int], list[float]]:
    completed = subprocess.run(
        [python, "-c", INIT_ROW_PROBE, str(path), str(row_index)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if completed.returncode != 0:
        raise EnvironmentUnavailable(
            f"init-row probe with {python} failed: {completed.stderr.strip()[-400:]}"
        )
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    return list(payload["shape"]), list(payload["row"])


def describe_environment() -> dict:
    info = {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
    }
    try:
        import robosuite

        info["robosuite_version"] = getattr(robosuite, "__version__", "?")
    except ImportError:
        info["robosuite_version"] = None
    try:
        import mujoco

        info["mujoco_version"] = getattr(mujoco, "__version__", "?")
    except ImportError:
        info["mujoco_version"] = None
    try:
        import torch

        info["torch_version"] = getattr(torch, "__version__", "?")
    except ImportError:
        info["torch_version"] = None
    return info


def run_task(
    task: dict,
    *,
    asset_root: Path,
    init_python: str | None,
    init_row: int,
    seed: int,
    camera_size: int,
) -> dict:
    entry = {
        "case_id": task["case_id"],
        "suite": task["suite"],
        "task_idx": int(task["task_idx"]),
        "bddl_name": task["bddl_name"],
        "instruction": task["instruction"],
        "init_row": init_row,
        "seed": seed,
        "status": "error",
    }
    suite_dir = SUITE_DIRS[task["suite"]]
    bddl = asset_root / "bddl_files" / suite_dir / f"{task['bddl_name']}.bddl"
    init = asset_root / "init_files" / suite_dir / f"{task['bddl_name']}.pruned_init"
    if not bddl.is_file():
        entry["error"] = f"missing BDDL: {bddl}"
        return entry
    if not init.is_file():
        entry["error"] = f"missing init state: {init}"
        return entry
    try:
        try:
            init_shape, init_values = load_init_row(init, init_row)
        except EnvironmentUnavailable:
            if init_python is None:
                raise
            init_shape, init_values = _probe_init_row(init_python, init, init_row)
        entry["init_shape"] = init_shape
        from libero.libero.envs import OffScreenRenderEnv  # type: ignore import-not-found

        env = OffScreenRenderEnv(
            bddl_file_name=str(bddl),
            camera_heights=camera_size,
            camera_widths=camera_size,
        )
        try:
            env.seed(seed)
            observation = env.reset()
            env.set_init_state(init_values)
            success = bool(env.check_success())
            agentview = (
                observation.get("agentview_image") if isinstance(observation, dict) else None
            )
            if agentview is not None and hasattr(agentview, "shape"):
                entry["agentview_image_shape"] = [int(size) for size in agentview.shape]
        finally:
            try:
                env.close()
            except Exception:  # noqa: BLE001 - closing must not mask the verdict
                pass
    except EnvironmentUnavailable:
        raise
    except Exception as error:  # noqa: BLE001 - record the failure and keep going
        entry["error_type"] = type(error).__name__
        entry["error"] = f"{type(error).__name__}: {error}"
        entry["traceback"] = traceback.format_exc()[-2000:]
        return entry
    if success:
        entry["status"] = "failed"
        entry["error"] = (
            "check_success() is True at the initial state: the goal already holds before "
            "any action (invalid init/goal pairing, certificate C2 violation)"
        )
    else:
        entry["status"] = "passed"
    return entry


def repro_command(
    args: argparse.Namespace, libero_home: Path, config_dir: Path, python: str
) -> str:
    return " ".join(
        [
            f"cd {REPO_ROOT} &&",
            f"MUJOCO_GL={os.environ.get('MUJOCO_GL', 'osmesa')}",
            f"LIBERO_CONFIG_PATH={config_dir}",
            f"PYTHONPATH={libero_home}",
            python,
            "scripts/smoke_env.py",
            f"--libero-home {libero_home}",
            f"--config-dir {config_dir}",
            "--no-static-only",
        ]
    )


def print_report(result: dict) -> None:
    print("LIBERO-Rollback environment smoke")
    environment = result.get("environment", {})
    print(f"python: {environment.get('python_executable')} ({environment.get('python_version')})")
    print(f"libero_home: {environment.get('libero_home')}")
    print(f"libero_config_path: {environment.get('libero_config_path')}")
    versions = " ".join(
        f"{key}={environment.get(key)}"
        for key in ("robosuite_version", "mujoco_version", "torch_version")
    )
    print("versions: " + versions)
    for entry in result.get("results", []):
        print(
            f"  {entry['status']:8s} {entry['case_id']:14s} "
            f"bddl={entry['bddl_name']} init_row={entry['init_row']}"
        )
        if entry.get("error"):
            print(f"    error: {entry['error']}")
    summary = result.get("summary", {})
    print(
        "summary: selected={n_selected} passed={n_passed} failed={n_failed} error={n_error}".format(
            **summary
        )
    )
    if result.get("status") == "environment_unavailable":
        print(f"environment unavailable: {result.get('environment_error')}")
        print(f"repro: {result.get('repro_command')}")
    else:
        print(f"status: {result.get('status')}")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LIBERO environment smoke test (initial state must not already succeed).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--libero-home",
        type=Path,
        default=None,
        help="upstream LIBERO repository root (default: $LIBERO_HOME)",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=None,
        help=(
            "repo-local LIBERO_CONFIG_PATH directory "
            "(default: $LIBERO_CONFIG_PATH or .cache/libero)"
        ),
    )
    parser.add_argument(
        "--matrix", type=Path, default=DEFAULT_MATRIX, help="A matrix to pick tasks from"
    )
    parser.add_argument(
        "--suite", action="append", choices=SUITE_ORDER, default=[], help="repeatable"
    )
    parser.add_argument("--task-idx", type=int, default=None, help="restrict to one task index")
    parser.add_argument("--init-row", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--camera", type=int, default=256)
    parser.add_argument(
        "--libero-python",
        default=None,
        help="fallback interpreter for loading .pruned_init when torch is missing here",
    )
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="only validate paths/config/matrix selection; do NOT import the simulation stack",
    )
    parser.add_argument("--no-static-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--json", type=Path, default=None, help="write the JSON report here")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result: dict = {"environment": describe_environment(), "results": [], "status": "failed"}
    raw_home = args.libero_home or os.environ.get("LIBERO_HOME")
    if not raw_home:
        print("[smoke] setup error: --libero-home is required (or set LIBERO_HOME)")
        return 2
    libero_home = Path(raw_home).expanduser()
    if not libero_home.is_dir():
        print(f"[smoke] setup error: LIBERO home is not a directory: {libero_home}")
        return 2
    result["environment"]["libero_home"] = str(libero_home)
    config_dir = DEFAULT_CONFIG_DIR
    try:
        config_dir = resolve_config_dir(args.config_dir)
        asset_root = resolve_asset_root(libero_home)
        tasks = select_tasks(args.matrix, args.suite, args.task_idx)
        config_path = write_libero_config(config_dir, asset_root)
    except EnvironmentUnavailable as error:
        result["status"] = "environment_unavailable"
        result["environment_error"] = str(error)
        result["repro_command"] = repro_command(args, libero_home, config_dir, sys.executable)
        result["summary"] = _summary([])
        print_report(result)
        _write_json(args.json, result)
        return 2
    result["environment"]["libero_config_path"] = str(config_path)
    result["environment"]["asset_root"] = str(asset_root)
    if not (asset_root / "assets").is_dir():
        result["environment"]["assets_warning"] = "assets/ is missing; rendering will fail"
    if args.static_only:
        result["status"] = "static_only"
        result["summary"] = {
            "n_selected": len(tasks),
            "n_passed": 0,
            "n_failed": 0,
            "n_error": 0,
        }
        result["tasks"] = [
            {"case_id": task["case_id"], "bddl_name": task["bddl_name"]} for task in tasks
        ]
        print_report(result)
        print("static_only: paths/config/matrix selection validated; simulation NOT exercised")
        _write_json(args.json, result)
        return 0

    try:
        result["environment"].update(bootstrap_environment(libero_home, config_dir))
        import mujoco  # noqa: F401
        import robosuite  # noqa: F401
        from libero.libero.envs import OffScreenRenderEnv  # noqa: F401
    except ImportError as error:
        result["status"] = "environment_unavailable"
        result["environment_error"] = (
            f"simulation stack not importable in {sys.executable}: {type(error).__name__}: {error}"
        )
        result["environment"].update(describe_environment())
        result["repro_command"] = repro_command(args, libero_home, config_dir, sys.executable)
        result["summary"] = _summary([])
        print_report(result)
        _write_json(args.json, result)
        return 2

    init_python = args.libero_python
    entries: list[dict] = []
    try:
        for task in tasks:
            entries.append(
                run_task(
                    task,
                    asset_root=asset_root,
                    init_python=init_python,
                    init_row=args.init_row,
                    seed=args.seed,
                    camera_size=args.camera,
                )
            )
    except EnvironmentUnavailable as error:
        result["results"] = entries
        result["status"] = "environment_unavailable"
        result["environment_error"] = str(error)
        result["repro_command"] = repro_command(args, libero_home, config_dir, sys.executable)
        result["summary"] = _summary(entries)
        print_report(result)
        _write_json(args.json, result)
        return 2
    result["results"] = entries
    result["summary"] = _summary(entries)
    passed = [entry for entry in entries if entry["status"] == "passed"]
    result["status"] = "verified" if len(passed) == len(entries) and entries else "failed"
    print_report(result)
    _write_json(args.json, result)
    return 0 if result["status"] == "verified" else 1


def _summary(entries: list[dict]) -> dict:
    return {
        "n_selected": len(entries),
        "n_passed": sum(1 for entry in entries if entry["status"] == "passed"),
        "n_failed": sum(1 for entry in entries if entry["status"] == "failed"),
        "n_error": sum(1 for entry in entries if entry["status"] == "error"),
    }


def _write_json(path: Path | None, payload: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
