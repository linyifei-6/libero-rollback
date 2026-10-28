"""Run each task's five cases with one external model load and video evidence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import yaml

from libero_rollback.runtime import runtime_binding

ROOT = Path(__file__).resolve().parents[1]
PLUS = ROOT.parent / "libero-plus"
OUTPUT = ROOT / "runs/full-coverage"
RUNTIME = OUTPUT / "runtime"
DATASET = ROOT / "dataset/v1.1"
PYTHON = PLUS / "openvla-oft-env/bin/python"
CHECKPOINT = PLUS / "models/openvla-7b-oft-finetuned-libero-spatial-object-goal-10"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=int, nargs="+", default=[9, 0, 4, 5, 6, 8, 1, 2, 3, 7])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.seed < 0 or any(index not in range(10) for index in args.tasks):
        parser.error("seed must be nonnegative and task indices must be 0..9")
    manifest = yaml.safe_load((DATASET / "manifest.yaml").read_text())
    # Start with the single-goal boundary case to verify continuation semantics.
    for index in args.tasks:
        cases = [
            yaml.safe_load((ROOT / row["path"]).read_text())
            for row in manifest["cases"]
            if yaml.safe_load((ROOT / row["path"]).read_text())["task"]["task_index"] == index
        ]
        bindings = [runtime_binding(case)["perturbation_binding"] for case in cases]
        binding = {
            "perturbation_binding": {
                "task_profile": bindings[0]["task_profile"],
                "enabled_cases": [b["enabled_cases"][0] for b in bindings],
            }
        }
        output = args.output.resolve() / f"task-{index:02d}"
        output.mkdir(parents=True, exist_ok=True)
        # Existing terminal records are evidence; resume only tasks not yet attempted.
        terminal = output / "execution.json"
        if terminal.exists() and json.loads(terminal.read_text()).get("results"):
            print(f"skip completed task {index:02d}", flush=True)
            continue
        binding_path = output / "binding.yaml"
        binding_path.write_text(yaml.safe_dump(binding, sort_keys=False))
        command = [
            str(PYTHON),
            str(RUNTIME / "tools/run_benchmark.py"),
            "--model",
            "openvla_oft",
            "--mode",
            "both",
            "--suite",
            "LIBERO_10",
            "--task-idx",
            cases[0]["task"]["source_task_locator"][1:],
            "--binding",
            str(binding_path),
            "--dimension",
            "rollback",
            "--seed-ids",
            str(args.seed),
            "--max-steps",
            "600",
            "--replan-steps",
            "10",
            "--checkpoint",
            str(CHECKPOINT),
            "--output",
            str(output),
            "--video",
        ]
        if index in (0, 9):
            command.append("--post-success-window")
        record = {
            "dataset_version": "1.1.0",
            "task_id": f"libero_10/{index:02d}",
            "case_ids": [case["case_id"] for case in cases],
            "command": command,
            "runtime": str(RUNTIME),
            "model": "openvla_oft",
            "checkpoint": str(CHECKPOINT),
            "seed": args.seed,
            "max_steps": 600,
        }
        (output / "execution-plan.json").write_text(json.dumps(record, indent=2))
        env = os.environ.copy()
        env["LIBERO_VIDEO_ENCODER_PYTHON"] = str(PLUS / "openpi/.venv/bin/python")
        env["PYTHONPATH"] = os.pathsep.join(
            [str(PLUS / "LIBERO-plus"), str(RUNTIME), env.get("PYTHONPATH", "")]
        )
        print(f"start task {index:02d}: five cases + paired baseline, video enabled", flush=True)
        with (output / "runner.log").open("w") as log:
            process = subprocess.run(
                command, cwd=RUNTIME, env=env, stdout=log, stderr=subprocess.STDOUT
            )
        record["returncode"] = process.returncode
        record["results"] = [str(path) for path in output.rglob("results.json")]
        record["videos"] = [str(path) for path in output.rglob("*.mp4")]
        terminal.write_text(json.dumps(record, indent=2))
        print(
            f"end task {index:02d}: rc={process.returncode}, videos={len(record['videos'])}",
            flush=True,
        )


if __name__ == "__main__":
    main()
