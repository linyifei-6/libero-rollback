"""Calibrate the stove articulation threshold for tasks 00 and 03.

`success_threshold_rad` decides when `articulation_completed` flips, which decides
when `enter_articulation_completed` fires. The value must be measured on the task,
not copied from T270.

The runner always resolves its config root to ``<runtime>/configs`` (no override
flag), so this script swaps the staged tree in for the duration of one baseline
episode and restores it afterwards, verifying the restore against a recorded
fingerprint. Baseline mode needs no binding, so only the task profile matters.

Usage:
    python scripts/calibrate_stove_threshold.py --task 0 --dry-run
    python scripts/calibrate_stove_threshold.py --task 0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runs/full-coverage/runtime"
LIVE_CONFIGS = RUNTIME / "configs"
STAGED_CONFIGS = ROOT / "runs/stove-articulation-staging/configs"
BACKUP = ROOT / "runs/stove-articulation-staging/configs-live-backup"
PLUS = ROOT.parent / "libero-plus"
PYTHON = PLUS / "openvla-oft-env/bin/python"
CHECKPOINT = PLUS / "models/openvla-7b-oft-finetuned-libero-spatial-object-goal-10"
OUTPUT = ROOT / "runs/stove-calibration"
# dataset task index -> runtime task index (the numeric source_task_locator)
TASKS = {"0": 0, "3": 133}


def fingerprint(tree: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(tree.rglob("*.yaml")):
        digest.update(str(path.relative_to(tree)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=sorted(TASKS), required=True)
    parser.add_argument("--max-steps", type=int, default=600)
    parser.add_argument("--video", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not STAGED_CONFIGS.is_dir():
        raise SystemExit(f"staged config tree missing: {STAGED_CONFIGS}")

    live_before = fingerprint(LIVE_CONFIGS)
    staged_fp = fingerprint(STAGED_CONFIGS)
    print(f"live configs fingerprint   : {live_before[:16]}")
    print(f"staged configs fingerprint : {staged_fp[:16]}")

    out_dir = OUTPUT / f"task-{args.task}"
    out_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(PYTHON), str(RUNTIME / "tools/run_benchmark.py"),
        "--model", "openvla_oft", "--mode", "baseline", "--suite", "LIBERO_10",
        "--task-idx", str(TASKS[args.task]), "--seed-ids", "0",
        "--max-steps", str(args.max_steps), "--replan-steps", "10",
        "--checkpoint", str(CHECKPOINT), "--output", str(out_dir),
    ]
    if args.video:
        command.append("--video")
    print("\ncommand:", " ".join(command))
    if args.dry_run:
        print("dry run: nothing swapped, nothing executed")
        return 0

    # swap: move the live tree aside, put the staged tree in place
    shutil.rmtree(BACKUP, ignore_errors=True)
    LIVE_CONFIGS.rename(BACKUP)
    try:
        shutil.copytree(STAGED_CONFIGS, LIVE_CONFIGS)
        print("\nswapped in the staged config tree")
        env = os.environ.copy()
        env["LIBERO_VIDEO_ENCODER_PYTHON"] = str(PLUS / "openpi/.venv/bin/python")
        env["PYTHONPATH"] = os.pathsep.join([str(PLUS / "LIBERO-plus"), str(RUNTIME)])
        with (out_dir / "runner.log").open("w") as log:
            proc = subprocess.run(command, cwd=str(RUNTIME), env=env, stdout=log,
                                  stderr=subprocess.STDOUT)
        print("runner returncode:", proc.returncode)
    finally:
        shutil.rmtree(LIVE_CONFIGS, ignore_errors=True)
        BACKUP.rename(LIVE_CONFIGS)
        live_after = fingerprint(LIVE_CONFIGS)
        print(f"restored live configs, fingerprint match: {live_after == live_before}")
        if live_after != live_before:
            print("WARNING: live config tree differs from before the swap; inspect it")

    # measure the knob travel
    results = sorted(out_dir.rglob("results.json"))
    if not results:
        print("no results produced; see", out_dir / "runner.log")
        return 1
    document = json.loads(results[-1].read_text())
    print("\n=== measurement ===")
    for task_data in document.values():
        if not isinstance(task_data, dict):
            continue
        for name, value in (task_data.get("results") or {}).items():
            if not isinstance(value, dict):
                continue
            trace = ((value.get("report") or {}).get("outcome") or {}).get("task_predicate_trace") or {}
            print(f"  {name[:60]:<62} success={value.get('success')} steps={value.get('steps')}")
            print(f"      final_subgoal_states={trace.get('final_subgoal_states')}")
            rows = (value.get("report") or {}).get("task_trace") or []
            print(f"      task_trace rows: {len(rows)}")
            if rows:
                positions = [
                    r.get("articulation_joint_position_rad") for r in rows
                    if r.get("articulation_joint_position_rad") is not None
                ]
                flags = [r.get("articulation_completed") for r in rows]
                print(f"      knob position range: {min(positions) if positions else None} .. "
                      f"{max(positions) if positions else None}")
                first_true = next((i for i, f in enumerate(flags) if f is True), None)
                print(f"      articulation_completed first True at trace row: {first_true}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
