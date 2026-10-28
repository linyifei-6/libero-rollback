"""Run a selected catalog through an external evaluator, with resumable provenance.

Run results stay in --output. Resume requires identical case, binding, runtime
code/configuration, model identifier, seed and evaluation settings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_cli_config as cli  # noqa: E402
# Overlay used when --runtime-root is not given. It must carry the perturbation
# extensions this catalog needs; regenerate it with scripts/prepare_validation_runtime.py
# if the evaluator is updated.
RUNTIME = ROOT / "runs/validation-runtime-20261014-v14"
CASES = ROOT / "dataset/current"

sys.path.insert(0, str(ROOT / "src"))
from libero_rollback.runtime import (  # noqa: E402
    check_runtime_capabilities,
    load_case_for_runtime,
    runtime_binding,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    cli.add_common_arguments(parser)
    # The shared set leaves the runtime unset so a caller must choose deliberately; this
    # runner has a preferred overlay, and `--runtime-root` still overrides it.
    parser.set_defaults(runtime_root=RUNTIME)
    # Options this runner adds on top of the shared set.
    parser.add_argument(
        "--native-preflight",
        action="store_true",
        help="test native-state injection candidates during the paired baseline",
    )
    parser.add_argument(
        "--baseline-only",
        action="store_true",
        help="collect baseline preflight only; does not test model recovery",
    )
    args, forwarded = cli.parse_with_forwarding(parser)
    output_root = args.output if args.output.is_absolute() else ROOT / args.output
    output_root.mkdir(parents=True, exist_ok=True)
    CASES = args.cases if args.cases.is_absolute() else ROOT / args.cases



    if args.max_steps <= 0 or args.replan_steps <= 0 or args.seed < 0 or args.limit < 0:
        parser.error("step limits must be positive; seed and limit must be non-negative")
    try:
        task_seeds = dict(item.split("=", 1) for item in args.task_seed)
        if any(
            k not in {f"{i:02d}" for i in range(10)} or int(v) < 0 for k, v in task_seeds.items()
        ):
            raise ValueError("invalid task or seed")
    except ValueError as exc:
        parser.error(f"--task-seed expects NN=nonnegative_integer: {exc}")
    runtime_root = args.runtime_root.resolve()
    manifest_path = CASES / "manifest.yaml"
    paths = (
        [ROOT / row["path"] for row in yaml.safe_load(manifest_path.read_text())["cases"]]
        if manifest_path.exists()
        else sorted(CASES.glob("*.yaml"))
    )
    selected: list[Path] = []
    for path in paths:
        case = yaml.safe_load(path.read_text())
        task_id = case["task"]["task_id"]  # libero_10/NN
        if args.task and task_id.split("/")[1] not in args.task:
            continue
        if not cli.matches_filters(case, args):
            continue
        if args.case_id and case["case_id"] not in args.case_id:
            continue
        selected.append(path)
    if args.limit:
        selected = selected[: args.limit]
    if args.case_id and set(args.case_id) - {load_case_for_runtime(p)["case_id"] for p in selected}:
        parser.error("one or more --case-id values do not match the selection")
    if not selected:
        parser.error("selection contains no cases")
    print(f"selected {len(selected)} cases -> {output_root}")
    runtime_files = {}
    for base in (runtime_root / "libero_runtime", runtime_root / "configs", runtime_root / "tools"):
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix in {".py", ".yaml", ".json", ".xml"}:
                runtime_files[str(p.relative_to(runtime_root))] = hashlib.sha256(
                    p.read_bytes()
                ).hexdigest()
    for name in ("rollback_extensions.py", "rollback_preflight.py", "overlay-provenance.json"):
        p = runtime_root / name
        if p.exists():
            runtime_files[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    runtime_digest = hashlib.sha256(json.dumps(runtime_files, sort_keys=True).encode()).hexdigest()
    (output_root / "runtime-provenance.json").write_text(json.dumps(runtime_files, indent=2))

    env = os.environ.copy()
    env["LIBERO_VIDEO_ENCODER_PYTHON"] = str(cli.resolve_video_encoder(args))
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src"), str(Path(os.environ.get("LIBERO_PLUS_ROOT", ROOT.parent / "libero-plus")) / "LIBERO-plus"), str(runtime_root)]
    )

    done = skipped = failed = 0
    summary = {"selected": len(selected), "cases": []}
    started = time.time()
    for index, path in enumerate(selected, 1):
        case = load_case_for_runtime(path)
        case_id = case["case_id"]
        check_runtime_capabilities(case, runtime_root)
        out_dir = output_root / case_id
        out_dir.mkdir(parents=True, exist_ok=True)
        seed = int(task_seeds.get(f"{case['task']['task_index']:02d}", args.seed))
        if args.native_preflight:
            if not (runtime_root / "rollback_preflight.py").is_file():
                parser.error("--native-preflight requires a prepared validation runtime")
            env["ROLLBACK_DATASET_ROOT"] = str(ROOT)
            env["ROLLBACK_PREFLIGHT_OUTPUT"] = str(out_dir / "native-preflight")
        binding = runtime_binding(case)
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "case_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "binding": binding,
                    "model": args.model,
                    "max_steps": args.max_steps,
                    "seed": seed,
                    "video": args.video,
                    "replan_steps": args.replan_steps,
                    "strict_paired_baseline": not args.baseline_only,
                    "native_preflight": args.native_preflight,
                    "baseline_only": args.baseline_only,
                    "runtime_sha256": runtime_digest,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        completion = out_dir / "completion.json"
        results = list(out_dir.rglob("results.json"))
        if completion.exists() and results:
            previous = json.loads(completion.read_text())
            if previous.get("fingerprint") == fingerprint and previous.get("returncode") in (
                0,
                2,
                3,
            ):
                skipped += 1
                summary["cases"].append(previous)
                print(f"[{index}/{len(selected)}] skip (verified provenance) {case_id}")
                continue
            raise SystemExit(f"stale results in {out_dir}; choose a new --output directory")
        if results:
            raise SystemExit(
                f"unverified existing results in {out_dir}; choose a new --output directory"
            )
        binding_path = out_dir / "binding.yaml"
        binding_path.write_text(yaml.safe_dump(binding, sort_keys=False), encoding="utf-8")
        command = [
            str(cli.resolve_model_python(args)),
            str(runtime_root / "tools/run_benchmark.py"),
            "--model",
            args.model,
            "--mode",
            "baseline" if args.baseline_only else "both",
            "--suite",
            str(args.suite),
            "--task-idx",
            case["task"]["source_task_locator"][1:],
            "--binding",
            str(binding_path),
            "--dimension",
            str(args.dimension),
            "--seed-ids",
            str(seed),
            "--max-steps",
            str(args.max_steps),
            "--replan-steps",
            str(args.replan_steps),
            "--output",
            str(out_dir),
        ]
        if not args.baseline_only:
            command += ["--strict-paired-baseline", "--require-successful-baseline"]
        if args.native_preflight:
            command.append("--phase-probe")
        command += forwarded
        # Only OpenVLA-OFT is loaded from a local checkpoint path; the OpenPI models
        # (pi0 / pi05) resolve their own config and checkpoint from the cache. The path
        # comes from --checkpoint or the per-model default, never from a literal here.
        _checkpoint = cli.resolve_checkpoint(args)
        if _checkpoint is not None:
            command += ["--checkpoint", str(_checkpoint)]
        if args.video:
            command.append("--video")
        if (
            case["stage"]["name"] == "completion_boundary"
            or case["trigger"].get("time_point") == "all_done"
        ):
            command.append("--post-success-window")
        (out_dir / "execution-plan.json").write_text(
            json.dumps(
                {
                    "case_id": case_id,
                    "command": command,
                    "max_steps": args.max_steps,
                    "seed": seed,
                    "fingerprint": fingerprint,
                    "case_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "runtime_sha256": runtime_digest,
                    "video": args.video,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        if args.dry_run:
            print(f"[{index}/{len(selected)}] DRY {case_id}")
            continue
        print(f"[{index}/{len(selected)}] run {case_id}", flush=True)
        stamp = time.time()
        with (out_dir / "runner.log").open("w") as log:
            proc = subprocess.run(
                command, cwd=str(runtime_root), env=env, stdout=log, stderr=subprocess.STDOUT
            )
        elapsed = time.time() - stamp
        record = {
            "case_id": case_id,
            "fingerprint": fingerprint,
            "returncode": proc.returncode,
            "elapsed_seconds": elapsed,
            "results": [str(p.relative_to(out_dir)) for p in out_dir.rglob("results.json")],
        }
        completion.write_text(json.dumps(record, indent=2), encoding="utf-8")
        summary["cases"].append(record)
        (output_root / "evaluation-summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        if proc.returncode == 0:
            done += 1
        elif proc.returncode in (2, 3):
            done += 1  # gate not passed: a valid negative evaluation outcome
        else:
            failed += 1
        print(
            f"    rc={proc.returncode} in {elapsed / 60:.1f} min "
            f"(ok={done} failed={failed} skipped={skipped})",
            flush=True,
        )

    print(
        f"\nsweep finished: ok={done} failed={failed} skipped={skipped} "
        f"in {(time.time() - started) / 3600:.1f} h"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
