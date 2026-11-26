"""Command line interface: ``libero-rollback``.

Subcommands
-----------
``list``
    Summarise one case matrix (counts by suite / level / task).
``validate``
    Static dataset validation (manifest, matrices, lite split, path hygiene).
    Never starts a simulator; safe in CI.
``run``
    Run the B matrix (or a filtered subset) with a frozen policy.  ``--dry-run``
    writes only ``plan.json`` and never starts the simulation.
``report``
    Build a self-contained HTML report + ``aggregate.json`` from a run directory.
``leaderboard``
    Validate a submission directory locally (case-level JSONL + aggregate).

Exit codes: ``0`` success, ``1`` validation/evaluation failure, ``2`` usage or
setup error (missing matrix, missing dataset, ...).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_SETUP = 2


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    """Best-effort repository root (``<repo>/src/libero_rollback/cli.py``)."""

    return Path(__file__).resolve().parents[2]


def _default_matrix() -> Path:
    candidates = []
    env_value = os.environ.get("LIBERO_ROLLBACK_MATRIX")
    if env_value:
        candidates.append(Path(env_value).expanduser())
    candidates.append(
        Path.cwd() / "dataset" / "matrices" / "libero-rollback" / "completion-rollback.csv"
    )
    candidates.append(
        _repo_root() / "dataset" / "matrices" / "libero-rollback" / "completion-rollback.csv"
    )
    candidates.append(Path.cwd() / "dataset" / "matrices" / "b-matrix.csv")
    candidates.append(_repo_root() / "dataset" / "matrices" / "b-matrix.csv")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _load_yaml(path: Path) -> Any:
    import yaml

    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def _split_case_ids(dataset_root: Path, split: str) -> list[str] | None:
    """Return the case ids of a named split, or ``None`` when unconstrained."""

    if split in {"core", "full", "all"}:
        return None
    lite_path = dataset_root / "lite.yaml"
    if not lite_path.is_file():
        raise SystemExit(f"split {split!r} needs {lite_path} (run build_manifest.py first)")
    payload = _load_yaml(lite_path) or {}
    # ``build_manifest.py`` writes the ids grouped by suite under ``splits``;
    # older drafts used a flat ``case_ids`` / ``cases`` list.  Accept all three.
    grouped = payload.get("splits")
    case_ids: list[str] = []
    if isinstance(grouped, dict):
        for entries in grouped.values():
            if isinstance(entries, list):
                case_ids.extend(str(case_id) for case_id in entries)
    else:
        flat = payload.get("case_ids", payload.get("cases"))
        if isinstance(flat, list):
            case_ids.extend(str(case_id) for case_id in flat)
    if not case_ids:
        raise SystemExit(f"{lite_path}: expected 'splits' or a flat case id list")
    seen: set[str] = set()
    unique = []
    for case_id in case_ids:
        if case_id not in seen:
            seen.add(case_id)
            unique.append(case_id)
    return unique


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> int:
    from .matrices import load_b_matrix

    matrix = load_b_matrix(args.matrix)
    summary = matrix.summary()
    if args.json:
        _print_json(summary)
        return EXIT_OK
    print(f"matrix: {matrix.source}")
    print(f"cases : {summary['cases']}  tasks: {summary['tasks']}")
    for suite, count in summary["by_suite"].items():
        print(f"  suite {suite:<8} {count:>4}")
    for level, count in summary["by_level"].items():
        print(f"  level {level:<8} {count:>4}")
    if args.suite:
        wanted = set(args.suite)
        rows = [case for case in matrix.cases if case.suite in wanted]
        for case in rows:
            level = case.level if case.param is None else f"{case.level}-{case.param}"
            print(f"  {case.case_id:<40} {case.suite:<8} {level:<8} {case.target}")
    return EXIT_OK


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> int:
    from .validation import validate_dataset

    report = validate_dataset(args.dataset)
    if args.json:
        _print_json(report.to_dict())
    else:
        print(report.format())
    return EXIT_OK if report.ok else EXIT_FAIL


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


def _add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--matrix", type=Path, default=None, help="B case matrix CSV")
    parser.add_argument("--model", "--policy", dest="model", default="none",
                        help="policy id from configs/models.yaml, or 'none'")
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--config-name", default="pi05_libero")
    parser.add_argument("--unnorm-key", default=None)
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", default="core", choices=("lite", "core", "full"))
    parser.add_argument("--dataset", type=Path, default=None,
                        help="dataset root for --split lite (default: <repo>/dataset)")
    parser.add_argument("--suites", nargs="*", default=None)
    parser.add_argument("--case-ids", nargs="*", default=None)
    parser.add_argument("--max-tasks", type=int, default=0)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--init-row", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=600)
    parser.add_argument("--delay-steps", type=int, default=10)
    parser.add_argument("--replan", type=int, default=None,
                        help="query cadence; default = model's native cadence "
                             "from configs/models.yaml (LIBERO-MAX convention)")
    parser.add_argument("--camera", type=int, default=256)
    parser.add_argument("--settle-steps", type=int, default=10)
    parser.add_argument("--max-trigger-wait", type=int, default=60)
    parser.add_argument("--repair-window", type=int, default=600)
    parser.add_argument("--stop-on-recovery", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--stop-on-success-after-injection", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--recovery-confirm-steps", type=int, default=1)
    parser.add_argument("--video", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--video-fps", type=int, default=20)
    parser.add_argument("--libero-home", default=None)
    parser.add_argument("--libero-python", default=None)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--retry-invalid", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="write plan.json only; do not start simulation or load a model")


def cmd_run(args: argparse.Namespace) -> int:
    from .matrices import load_b_matrix
    from .runner import RunConfig, build_plan, run_matrix, select_cases, write_plan

    matrix_path = args.matrix or _default_matrix()
    if not matrix_path.is_file():
        print(f"error: matrix not found: {matrix_path}", file=sys.stderr)
        return EXIT_SETUP
    matrix = load_b_matrix(matrix_path)

    cases = select_cases(
        matrix,
        suites=args.suites,
        case_ids=args.case_ids,
        max_tasks=args.max_tasks,
        max_cases=args.max_cases,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
    )
    if args.split == "lite":
        dataset_root = args.dataset or (_repo_root() / "dataset")
        lite_ids = _split_case_ids(dataset_root, "lite")
        if lite_ids is not None:
            wanted = set(lite_ids)
            cases = [case for case in cases if case.case_id in wanted]
    if not cases:
        print("error: the case selection is empty", file=sys.stderr)
        return EXIT_SETUP

    if args.replan is None:
        from .policies import native_replan

        args.replan = native_replan(args.model) or 10

    config = RunConfig(
        init_row=args.init_row,
        seed=args.seed,
        max_steps=args.max_steps,
        delay_steps=args.delay_steps,
        replan=args.replan,
        camera=args.camera,
        settle_steps=args.settle_steps,
        max_trigger_wait=args.max_trigger_wait,
        repair_window=args.repair_window,
        stop_on_recovery=bool(args.stop_on_recovery),
        stop_on_success=bool(args.stop_on_success_after_injection),
        recovery_confirm_steps=int(args.recovery_confirm_steps),
        video=args.video,
        video_fps=args.video_fps,
        policy=args.model,
        libero_home=args.libero_home,
        libero_python=args.libero_python,
    )
    if args.dry_run:
        plan = build_plan(
            matrix=matrix,
            cases=cases,
            config=config,
            checkpoint=args.checkpoint,
            config_name=args.config_name,
            shard_index=args.shard_index,
            shard_count=args.shard_count,
        )
        path = write_plan(args.output, plan)
        print(f"[dry-run] {len(cases)} case(s) selected; plan written to {path}")
        print("dry-run is a plan only, not evaluation evidence (docs/SPEC.md §8)")
        return EXIT_OK

    if args.model == "none":
        print("[warn] --model none runs the environment with zero actions; "
              "results are not model evidence", file=sys.stderr)
    summary = run_matrix(
        matrix=matrix,
        cases=cases,
        output=args.output,
        model=args.model,
        checkpoint=args.checkpoint,
        config=config,
        config_name=args.config_name,
        unnorm_key=args.unnorm_key,
        workspace=args.workspace,
        resume=args.resume,
        retry_errors=args.retry_errors,
        retry_invalid=args.retry_invalid,
    )
    print(
        f"run finished: cases={summary.get('cases')} ok={summary.get('ok')} "
        f"errors={summary.get('errors')} recovery={summary.get('recovered')}"
        f"/{summary.get('recoverable_valid')} "
        f"control={summary.get('control_ok')}/{summary.get('controls')}"
    )
    print(f"report: libero-rollback report --run {args.output}")
    return EXIT_OK


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def cmd_report(args: argparse.Namespace) -> int:
    from .report import write_report

    if not Path(args.run).is_dir():
        print(f"error: run directory not found: {args.run}", file=sys.stderr)
        return EXIT_SETUP
    aggregate = write_report(args.run, args.out)
    out_dir = Path(args.out) if args.out else Path(args.run) / "report"
    print(f"report written: {out_dir / 'index.html'}")
    recovery = aggregate["recovery"]
    print(
        f"cases={aggregate['episodes']} recovery={_format_rate(recovery)} "
        f"control={_format_rate(aggregate['control'])} "
        f"trigger={_format_rate(aggregate['trigger'])}"
    )
    return EXIT_OK


def _format_rate(rate: Any) -> str:
    if not isinstance(rate, dict) or rate.get("na"):
        return "N/A"
    value = rate.get("value")
    if value is None:
        return "N/A"
    return f"{float(value) * 100:.1f}% ({rate.get('numerator')}/{rate.get('denominator')})"


# ---------------------------------------------------------------------------
# leaderboard
# ---------------------------------------------------------------------------


def cmd_leaderboard(args: argparse.Namespace) -> int:
    from .evidence import VERDICTS, classify_episode
    from .report import load_episodes

    run_dir = Path(args.run)
    episodes = load_episodes(run_dir)
    problems: list[str] = []
    if not episodes:
        problems.append("no episodes recorded (episodes.jsonl missing or empty)")
    seen: set[str] = set()
    for episode in episodes:
        case_id = episode.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            problems.append("episode without case_id")
            continue
        if case_id in seen:
            problems.append(f"duplicate case_id in submission: {case_id}")
        seen.add(case_id)
        verdict = episode.get("verdict")
        if not isinstance(verdict, str) or verdict not in VERDICTS:
            episode = dict(episode)
            episode["verdict"] = classify_episode(episode)
            verdict = episode["verdict"]
            if verdict not in VERDICTS:
                problems.append(f"{case_id}: cannot derive a verdict")
    manifest = run_dir / "run-manifest.json"
    if not manifest.is_file():
        problems.append("run-manifest.json missing (needed for provenance)")
    if problems:
        print("leaderboard submission: FAIL")
        for problem in problems:
            print(f"  error: {problem}")
        return EXIT_FAIL
    print(f"leaderboard submission: OK ({len(episodes)} episodes, {len(seen)} unique case ids)")
    return EXIT_OK


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="libero-rollback",
        description="LIBERO-Rollback: controlled-perturbation benchmark for goal-state persistence",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="summarise a case matrix")
    list_parser.add_argument("--matrix", type=Path, default=None)
    list_parser.add_argument("--suite", nargs="*", default=None)
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(func=cmd_list)

    validate_parser = subparsers.add_parser("validate", help="static dataset validation")
    validate_parser.add_argument("--dataset", type=Path, default=Path("dataset"))
    validate_parser.add_argument("--json", action="store_true")
    validate_parser.set_defaults(func=cmd_validate)

    run_parser = subparsers.add_parser("run", help="run the B matrix")
    _add_run_arguments(run_parser)
    run_parser.set_defaults(func=cmd_run)

    report_parser = subparsers.add_parser("report", help="build a run report")
    report_parser.add_argument("--run", type=Path, required=True)
    report_parser.add_argument("--out", type=Path, default=None)
    report_parser.set_defaults(func=cmd_report)

    leaderboard_parser = subparsers.add_parser("leaderboard", help="leaderboard tooling")
    leaderboard_sub = leaderboard_parser.add_subparsers(dest="leaderboard_command", required=True)
    leaderboard_validate = leaderboard_sub.add_parser("validate", help="validate a submission")
    leaderboard_validate.add_argument("--run", type=Path, required=True)
    leaderboard_validate.set_defaults(func=cmd_leaderboard)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except SystemExit:
        raise
    except FileNotFoundError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_SETUP
    except Exception as error:  # noqa: BLE001 - CLI boundary
        if os.environ.get("LIBERO_ROLLBACK_DEBUG"):
            raise
        print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_SETUP


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
