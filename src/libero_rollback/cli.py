"""Command-line interface for reading and validating the dataset."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .runtime import RuntimeBridgeError, run_case
from .validation import (
    DatasetError,
    check_manifest,
    load_yaml,
    validate_case_file,
    validate_dataset,
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _case_paths(dataset_root: Path) -> list[Path]:
    manifest = load_yaml(dataset_root / "manifest.yaml")
    root = dataset_root.resolve().parents[1]
    return [root / entry["path"] for entry in manifest.get("cases", [])]


def _list(dataset_root: Path, selected_task: str | None) -> int:
    coverage = load_yaml(dataset_root / "coverage.yaml")
    cases: list[dict[str, Any]] = []
    for path in _case_paths(dataset_root):
        case = load_yaml(path)
        if selected_task is None or case["task"]["task_id"] == selected_task:
            cases.append(case)

    print("TASKS")
    for task in coverage["tasks"]:
        if selected_task is not None and task["task_id"] != selected_task:
            continue
        print(
            f"{task['task_id']}  cases={task['case_count']}  "
            f"applicability={task['scenario_applicability']}  {task['task_name']}"
        )
    print("CASES")
    for case in cases:
        print(f"{case['case_id']}  task={case['task']['task_id']}")
    return 0


def _run_case_exit_code(result: dict[str, Any]) -> int:
    """Keep valid negative evaluation outcomes distinct from bridge failures."""

    if result.get("runner_result_path") and result.get("injection_valid") is True:
        return 0
    returncode = result.get("runner_returncode")
    if isinstance(returncode, int) and returncode != 0:
        return returncode
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="libero-rollback")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=repository_root() / "dataset" / "current",
        help="dataset catalog directory (default: dataset/current)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    case_parser = subparsers.add_parser(
        "validate-case", help="validate one YAML case against schema v1"
    )
    case_parser.add_argument("path", type=Path)

    subparsers.add_parser(
        "validate-dataset", help="validate case schemas and dataset cross-references"
    )
    subparsers.add_parser(
        "check-manifest", help="check manifest file references and SHA-256 digests"
    )

    list_parser = subparsers.add_parser("list", help="list covered tasks and cases")
    list_parser.add_argument(
        "--task", help="show cases for one stable task ID, such as libero_10/02"
    )

    run_parser = subparsers.add_parser(
        "run-case",
        aliases=["evaluate"],
        help="run one case through an explicitly installed LIBERO evaluator",
    )
    run_parser.add_argument("path", type=Path, nargs="*", help="one or more case YAML paths")
    run_parser.add_argument(
        "--all-cases", action="store_true", help="run every case in the selected dataset"
    )
    run_parser.add_argument(
        "--case-id", action="append", default=[], help="select a case ID (repeatable)"
    )
    run_parser.add_argument(
        "--task", action="append", default=[], help="select a stable task ID (repeatable)"
    )
    run_parser.add_argument(
        "--python",
        dest="python_executable",
        type=Path,
        required=True,
        help="Python executable from the external evaluator environment",
    )
    run_parser.add_argument(
        "--libero-root",
        type=Path,
        required=True,
        help="checkout containing the LIBERO package and assets",
    )
    run_parser.add_argument(
        "--runtime-root",
        type=Path,
        required=True,
        help="checkout containing tools/run_benchmark.py and runtime configs",
    )
    run_parser.add_argument(
        "--adapter",
        "--model",
        dest="adapter",
        required=True,
        help="adapter identifier understood by the external evaluator",
    )
    run_parser.add_argument("--suite", choices=("LIBERO_10",), default="LIBERO_10")
    run_parser.add_argument("--dimension", choices=("rollback",), default="rollback")
    run_parser.add_argument(
        "--severity",
        choices=(
            "d0",
            "d1",
            "d2",
            "d3",
            "checkpoint",
            "n3",
            "n5",
            "n8",
            "p3",
            "p5",
            "p8",
            "p10",
            "r05",
            "above",
            "articulation",
            "pose",
            "reference",
            "boundary",
        ),
    )
    run_parser.add_argument("--video", action="store_true", help="record evaluator videos")
    run_parser.add_argument("--mode", choices=("baseline", "perturbation", "both"), default="both")
    run_parser.add_argument(
        "--checkpoint",
        type=Path,
        help="checkpoint override; optional for cached OpenPI adapters such as pi05",
    )
    run_parser.add_argument("--seed", type=int, default=0)
    run_parser.add_argument("--max-steps", type=int, default=600)
    run_parser.add_argument("--replan-steps", type=int, default=10)
    run_parser.add_argument(
        "--success-delay",
        type=int,
        default=0,
        help=(
            "stable-success hold window: after the first success, require the "
            "task predicate to stay true for this many additional control "
            "steps; 0 keeps the legacy immediate stop"
        ),
    )
    run_parser.add_argument(
        "--success-check-interval",
        type=int,
        default=1,
        help="sample the predicate every N steps inside the hold window (1 = strict)",
    )
    run_parser.add_argument(
        "--output",
        type=Path,
        help="run directory (default: runs/<UTC timestamp>/<case_id>)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-case":
            errors = validate_case_file(args.path)
            if errors:
                print("\n".join(errors), file=sys.stderr)
                return 1
            print(f"valid: {args.path}")
            return 0
        if args.command == "validate-dataset":
            errors = validate_dataset(args.dataset_root)
            if errors:
                print("\n".join(errors), file=sys.stderr)
                return 1
            print(f"valid dataset: {args.dataset_root}")
            return 0
        if args.command == "check-manifest":
            errors = check_manifest(args.dataset_root)
            if errors:
                print("\n".join(errors), file=sys.stderr)
                return 1
            print(f"manifest files and digests valid: {args.dataset_root / 'manifest.yaml'}")
            return 0
        if args.command == "list":
            return _list(args.dataset_root, args.task)
        if args.command in {"run-case", "evaluate"}:
            selected = _select_cases(
                args.dataset_root,
                args.path,
                args.all_cases,
                args.case_id,
                args.task,
            )
            if not selected:
                raise DatasetError("selection matched no cases")
            output_root = args.output
            output_root = output_root or (
                Path("runs") / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            )
            output_root.mkdir(parents=True, exist_ok=True)
            summaries: list[dict[str, Any]] = []
            exit_code = 0
            for case_id, case_path in selected:
                case_output = output_root
                if len(selected) > 1 and case_output is not None:
                    case_output = case_output / case_id
                try:
                    result = run_case(
                        case_path,
                        python_executable=args.python_executable,
                        libero_root=args.libero_root,
                        runtime_root=args.runtime_root,
                        adapter=args.adapter,
                        checkpoint=args.checkpoint,
                        seed=args.seed,
                        max_steps=args.max_steps,
                        replan_steps=args.replan_steps,
                        success_delay=args.success_delay,
                        success_check_interval=args.success_check_interval,
                        output_root=case_output,
                        suite=args.suite,
                        dimension=args.dimension,
                        severity=args.severity,
                        video=args.video,
                        mode=args.mode,
                    )
                    result_path = Path(result["runner_output_dir"]) / "case_result.json"
                    print(f"{case_id}: {result_path}")
                    code = _run_case_exit_code(result)
                    exit_code = max(exit_code, code)
                    summaries.append(
                        {
                            "case_id": case_id,
                            "status": (
                                "completed" if result.get("injection_valid") is True else "invalid"
                            ),
                            "injection_valid": result.get("injection_valid"),
                            "episode_success": result.get("episode_success"),
                            "result": str(result_path),
                        }
                    )
                except (RuntimeBridgeError, OSError, KeyError, json.JSONDecodeError) as exc:
                    print(f"{case_id}: {exc}", file=sys.stderr)
                    exit_code = 1
                    summaries.append({"case_id": case_id, "status": "error", "error": str(exc)})
            if output_root is not None:
                manifest = load_yaml(args.dataset_root / "manifest.yaml")
                summary_path = output_root / "evaluation-summary.json"
                summary_path.write_text(
                    json.dumps(
                        {
                            "schema_version": "libero-rollback.evaluation-summary.v1",
                            "dataset_version": manifest.get("dataset_version"),
                            "model": args.adapter,
                            "suite": args.suite,
                            "dimension": args.dimension,
                            "severity": args.severity,
                            "max_steps": args.max_steps,
                            "success_delay": args.success_delay,
                            "success_check_interval": args.success_check_interval,
                            "video": args.video,
                            "cases": summaries,
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                print(f"evaluation summary: {summary_path}")
            return exit_code
    except (DatasetError, RuntimeBridgeError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 2


def _select_cases(
    dataset_root: Path,
    paths: list[Path],
    all_cases: bool,
    case_ids: list[str],
    tasks: list[str],
) -> list[tuple[str, Path]]:
    """Resolve an explicit list or filters against the versioned manifest."""
    selectors = bool(paths or all_cases or case_ids or tasks)
    if not selectors:
        raise DatasetError("provide case paths, --case-id, --task, or --all-cases")
    manifest = load_yaml(dataset_root / "manifest.yaml")
    root = dataset_root.resolve().parents[1]
    entries = manifest.get("cases", [])
    if paths:
        return [(str(load_yaml(path)["case_id"]), path) for path in paths]
    result = []
    for entry in entries:
        case_path = root / entry["path"]
        case = load_yaml(case_path)
        if all_cases or entry["case_id"] in case_ids or case["task"]["task_id"] in tasks:
            result.append((entry["case_id"], case_path))
    unknown = set(case_ids) - {item[0] for item in result}
    if unknown:
        raise DatasetError(f"unknown or unmatched case IDs: {', '.join(sorted(unknown))}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
