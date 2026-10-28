"""Batched runner: one model load per evaluation, one baseline per task, all cases in sequence.

Reads the catalog, groups cases by task, writes one binding per task containing that task's
cases, then invokes the benchmark once per task with `--all-tasks` scoping. The model is
loaded once inside the benchmark, the paired baseline runs once per task, and every case for
that task executes consecutively.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from libero_rollback.runtime import runtime_binding  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_cli_config as cli  # noqa: E402


def dataset_task_index(case: dict) -> int:
    """The dataset task index 0-9 (the T locator is a separate namespace)."""

    return int(case["task"]["task_index"])

def load_cases(cases_dir: Path) -> list[dict]:
    manifest = cases_dir / "manifest.yaml"
    out = []
    if manifest.exists():
        doc = yaml.safe_load(manifest.read_text())
        for entry in doc["cases"]:
            p = ROOT / entry["path"]
            case = yaml.safe_load(p.read_text())
            case["_path"] = p
            out.append(case)
    else:
        for p in sorted(cases_dir.glob("*.yaml")):
            case = yaml.safe_load(p.read_text())
            case["_path"] = p
            out.append(case)
    return out


def batch_binding(cases: list[dict]) -> dict:
    """Merge several cases of one task into a single binding document."""

    enabled = []
    profile = None
    for case in cases:
        one = runtime_binding(case)["perturbation_binding"]
        profile = profile or one["task_profile"]
        if one["task_profile"] != profile:
            raise SystemExit(f"task profile mismatch within a task: {one['task_profile']}")
        enabled.extend(one["enabled_cases"])
    names = [c["case_name"] for c in enabled]
    if len(set(names)) != len(names):
        raise SystemExit(f"duplicate case_name inside a task batch: {names}")
    return {"perturbation_binding": {"task_profile": profile, "enabled_cases": enabled}}


def case_label_suffix(case: dict) -> str:
    """Perturbation label the benchmark records for this case (``<case_name>_l..._s<seed>``)."""

    enabled = runtime_binding(case)["perturbation_binding"]["enabled_cases"][0]
    return str(enabled["case_name"])


def recorded_case_result(batch_dir: Path, case: dict) -> dict | None:
    """The perturbation record this batch already wrote for ``case``, if any.

    A batch becomes resumable per case: the benchmark writes a results snapshot after every
    episode, so an interrupted batch can be finished by rerunning only its missing cases.
    """

    marker = case_label_suffix(case)
    for path in sorted((batch_dir / "run").rglob("results.json")):
        try:
            doc = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        for task_data in doc.values():
            if not isinstance(task_data, dict):
                continue
            for label, value in (task_data.get("results") or {}).items():
                if isinstance(value, dict) and value.get("kind") == "perturbation" \
                        and marker in label:
                    return value
    return None


def batch_completed(batch_dir: Path) -> bool:
    """True when this task batch already produced a finished run.

    A batch is complete when its benchmark output holds results and the batch log reports
    completion, so an interrupted run is retried rather than silently skipped.
    """

    run_dir = batch_dir / "run"
    if not run_dir.is_dir():
        return False
    results = list(run_dir.rglob("results.json"))
    if not results:
        return False
    log = batch_dir / "batch.log"
    if log.exists() and "ALL DONE" not in log.read_text(errors="replace"):
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Batched rollback evaluation: one model load per run, one baseline per "
                    "task, every case for that task executed consecutively.")
    cli.add_common_arguments(ap)
    args, forwarded = cli.parse_with_forwarding(ap)
    if args.runtime_root is None:
        raise SystemExit("--runtime-root is required (the evaluator overlay to run)")

    # the benchmark runs with cwd=runtime_root, so the runtime path must be absolute
    args.runtime_root = args.runtime_root.resolve()
    if not (args.runtime_root / "tools/run_benchmark.py").is_file():
        raise SystemExit(f"no tools/run_benchmark.py under {args.runtime_root}")

    cases = load_cases(args.cases)
    if args.task:
        wanted = {str(t) for t in args.task}
        cases = [c for c in cases if f"{dataset_task_index(c):02d}" in wanted]
    # every other selection axis applies regardless of whether --task was used
    cases = [c for c in cases if cli.matches_filters(c, args)]
    task_seeds = cli.task_seed_map(args)
    seed_ids = cli.selected_seed_ids(args)
    print(f"seeds: {seed_ids}")

    groups: dict[int, list[dict]] = defaultdict(list)
    for case in cases:
        groups[dataset_task_index(case)].append(case)

    if args.dry_run:
        # Report the selection and stop before any subprocess is launched, so this mode
        # never loads a model or touches the GPU.
        total = sum(len(v) for v in groups.values())
        print(f"\nDRY RUN: {total} cases across {len(groups)} task batches")
        for task in sorted(groups):
            override = task_seeds.get(f"{task:02d}")
            seeds = [int(override)] if override is not None else list(seed_ids)
            print(f"  task {task:02d}: {len(groups[task]):>3} cases, seeds={seeds}")
            for case in groups[task]:
                print(f"      {case['case_id']}")
        return 0

    out_root = args.output.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    summary_path = out_root / "batch-summary.json"
    summary = {"model": args.model, "cases": len(cases), "tasks": {}, "batches": []}

    python = cli.resolve_model_python(args)
    checkpoint = cli.resolve_checkpoint(args)
    print(f"model={args.model}  cases={len(cases)}  tasks={len(groups)}")
    print(f"runtime={args.runtime_root}")
    print(f"output={out_root}\n")

    for task in sorted(groups):
        task_cases = groups[task]
        override = task_seeds.get(f"{task:02d}")
        batch_seeds = [int(override)] if override is not None else list(seed_ids)
        binding = batch_binding(task_cases)
        batch_dir = out_root / f"task{task:02d}"
        batch_dir.mkdir(parents=True, exist_ok=True)

        recorded_results: list[dict] = []
        if args.resume and not args.overwrite and not batch_completed(batch_dir):
            missing = [c for c in task_cases if recorded_case_result(batch_dir, c) is None]
            recorded_results = [
                recorded_case_result(batch_dir, c) for c in task_cases
                if recorded_case_result(batch_dir, c) is not None
            ] if len(missing) != len(task_cases) else []
            if not missing:
                # every case already produced a record; only the completion marker is absent
                print(f"[task {task:02d}] all cases already recorded -> skipped (--resume)")
                summary["tasks"][f"{task:02d}"] = {
                    "cases": len(task_cases), "seeds": batch_seeds, "returncode": 0,
                    "elapsed_s": 0.0, "per_case_s": 0.0, "skipped": True,
                    "binding": str((batch_dir / "binding.yaml").relative_to(out_root)),
                    "log": str((batch_dir / "batch.log").relative_to(out_root)),
                }
                summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
                continue
            if len(missing) != len(task_cases):
                print(f"[task {task:02d}] --resume -> {len(task_cases) - len(missing)} case(s) "
                      f"already recorded, rerunning the remaining {len(missing)}")
                task_cases = missing
                binding = batch_binding(task_cases)

        if batch_completed(batch_dir):
            if args.resume and not args.overwrite:
                print(f"[task {task:02d}] already complete -> skipped (--resume)")
                summary["tasks"][f"{task:02d}"] = {
                    "cases": len(task_cases), "seeds": batch_seeds, "returncode": 0,
                    "elapsed_s": 0.0, "per_case_s": 0.0, "skipped": True,
                    "binding": str((batch_dir / "binding.yaml").relative_to(out_root)),
                    "log": str((batch_dir / "batch.log").relative_to(out_root)),
                }
                summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
                continue
            if args.overwrite:
                print(f"[task {task:02d}] --overwrite -> clearing previous results")
                shutil.rmtree(batch_dir / "run", ignore_errors=True)
            elif not args.resume:
                raise SystemExit(
                    f"{batch_dir} already holds results; pass --resume to skip it or "
                    f"--overwrite to rerun it, or choose a new --output directory")
        binding_path = batch_dir / "binding.yaml"
        binding_path.write_text(
            yaml.safe_dump(binding, sort_keys=False, allow_unicode=True, width=100),
            encoding="utf-8")

        locator = task_cases[0]["task"]["source_task_locator"]
        command = [
            str(python),
            str(args.runtime_root / "tools/run_benchmark.py"),
            "--model", args.model,
            "--mode", "both",
            "--suite", str(args.suite),
            "--task-idx", locator[1:],
            "--binding", str(binding_path),
            "--dimension", str(args.dimension),
            "--seed-ids", ",".join(str(s) for s in batch_seeds),
            "--max-steps", str(args.max_steps),
            "--replan-steps", str(args.replan_steps),
            "--strict-paired-baseline",
            "--require-successful-baseline",
            "--output", str(batch_dir / "run"),
        ]
        # only forward a camera resolution when the caller chose one, so the runtime's own
        # default stays authoritative
        if args.cam:
            command += ["--cam", str(args.cam)]
        if args.video:
            command.append("--video")
        if checkpoint is not None:
            command += ["--checkpoint", str(checkpoint)]
        # everything the runner does not model itself goes straight to the benchmark
        command += cli.forwarded_runtime_options(
            args, exclude=("--seed-ids", "--seeds", "--cam", "--suite", "--dimension",
                           "--task-idx", "--binding", "--max-steps", "--replan-steps",
                           "--output", "--mode", "--model", "--checkpoint"))

        print(f"[task {task:02d}] {len(task_cases)} cases, seeds={batch_seeds} "
              f"-> one baseline + {len(task_cases)} perturbations")
        t0 = time.time()
        env = cli.base_environment(args)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(ROOT / "src"), str(args.runtime_root)])
        log_path = batch_dir / "batch.log"
        with log_path.open("w") as handle:
            proc = subprocess.run(command, cwd=str(args.runtime_root), env=env,
                                  stdout=handle, stderr=subprocess.STDOUT)
        elapsed = time.time() - t0
        rc = proc.returncode
        if recorded_results:
            # a resumed batch only reran its missing cases; fold the records that were
            # already on disk back in so the batch keeps every case in one results.json
            merged = 0
            for path in sorted((batch_dir / "run").rglob("results.json")):
                try:
                    doc = json.loads(path.read_text())
                except (OSError, ValueError):
                    continue
                changed = False
                for task_data in doc.values():
                    if not isinstance(task_data, dict):
                        continue
                    records = task_data.get("results")
                    if not isinstance(records, dict):
                        continue
                    for record in recorded_results:
                        label = next((key for key in records if record.get("pert_id") in key),
                                     None)
                        if label is None:
                            records[f"{record.get('pert_id')}_s{batch_seeds[0]}"] = record
                            merged += 1
                            changed = True
                if changed:
                    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False),
                                    encoding="utf-8")
            if merged:
                print(f"    merged {merged} previously recorded case(s) back into results.json")
        print(f"    rc={rc} in {elapsed/60:.1f} min "
              f"({elapsed/max(len(task_cases),1):.0f} s/case)")
        summary["tasks"][f"{task:02d}"] = {
            "cases": len(task_cases), "seeds": batch_seeds, "returncode": rc,
            "elapsed_s": round(elapsed, 1),
            "per_case_s": round(elapsed / max(len(task_cases), 1), 1),
            "binding": str(binding_path.relative_to(out_root)),
            "log": str(log_path.relative_to(out_root)),
        }
        summary["batches"].append(f"task{task:02d}")
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    total = sum(v["elapsed_s"] for v in summary["tasks"].values())
    print(f"\nALL TASKS DONE in {total/3600:.2f} h over {len(groups)} model loads")
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
