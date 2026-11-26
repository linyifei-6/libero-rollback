#!/usr/bin/env python3
"""Thin CLI for the C/D in-execution rollback runner (GT window triggers).

The runner logic lives in :mod:`libero_rollback.window_runner`; this script only
parses arguments, loads the C or D matrix and writes the dry-run plan.
``--dry-run`` writes ``plan.json`` only: no simulation is started, no model is
loaded, and the plan is **not** evaluation evidence.

Examples
--------
Dry run (works in the CPU-only env, no LIBERO / MuJoCo / torch)::

    python scripts/run_window_matrix.py --dry-run \\
        --matrix dataset/matrices/libero-rollback/in-execution-rollback.csv

Real run (inside the simulation environment)::

    LIBERO_HOME=/path/to/LIBERO \\
    python scripts/run_window_matrix.py --policy none --windows early \\
        --max-cases 2 --output runs/c-smoke

Composed D run (assets are repo-local under ``dataset/compose``)::

    LIBERO_HOME=/path/to/LIBERO COMPOSE_ROOT=dataset/compose \\
    python scripts/run_window_matrix.py --policy none \\
        --matrix dataset/matrices/libero-compose/rollback.csv \\
        --windows later --max-cases 1 --output runs/d-smoke
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Sequence
from pathlib import Path

# JAX preallocates 75% of the GPU by default; pi05 only needs ~10 GB.
os.environ.setdefault("XLA_PYTHON_CLIENT_MEM_FRACTION", "0.42")

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

DEFAULT_MATRIX = (
    REPO_ROOT / "dataset" / "matrices" / "libero-rollback" / "in-execution-rollback.csv"
)
DEFAULT_B_MATRIX = REPO_ROOT / "dataset" / "matrices" / "b-matrix.csv"
RULE = "-" * 78


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--matrix",
        type=Path,
        default=DEFAULT_MATRIX,
        help=(
            "C or D matrix CSV (default: "
            "dataset/matrices/libero-rollback/in-execution-rollback.csv)"
        ),
    )
    parser.add_argument(
        "--matrix-kind",
        choices=("auto", "C", "D"),
        default="auto",
        help="matrix kind; 'auto' detects D from struct_id/bddl_name columns",
    )
    parser.add_argument(
        "--b-matrix",
        type=Path,
        default=DEFAULT_B_MATRIX,
        help="B matrix used to map C (suite, task_idx) -> bddl_name",
    )
    parser.add_argument(
        "--compose-root",
        type=Path,
        default=None,
        help="D asset root (default: COMPOSE_ROOT or dataset/compose)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="run directory (default: runs/window-matrix/<UTC timestamp>)",
    )
    parser.add_argument("--suites", nargs="*", default=None, help="subset: l10 compose")
    parser.add_argument(
        "--windows",
        nargs="*",
        default=None,
        help="subset of windows: early mid later",
    )
    parser.add_argument("--levels", nargs="*", default=None, help="subset: L0 L1 L2")
    parser.add_argument("--case-ids", nargs="*", default=None)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--init-row", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--max-steps",
        type=int,
        default=0,
        help="override the matrix max_steps; 0 uses the row value (C 800 / D 600)",
    )
    parser.add_argument("--repair-window", type=int, default=600)
    parser.add_argument(
        "--stop-on-success-after-injection",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="after the injection, stop as soon as the full goal set is true again",
    )
    parser.add_argument("--replan", type=int, default=10)
    parser.add_argument("--camera", type=int, default=256)
    parser.add_argument("--settle-steps", type=int, default=10)
    parser.add_argument(
        "--require-settled-early",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="require s1 settled before firing the early window",
    )
    parser.add_argument(
        "--require-s2-started-early",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="require s2 motion before firing the early window",
    )
    parser.add_argument(
        "--lift-min-m",
        type=float,
        default=0.03,
        help="s2 lift threshold for the mid window (default 0.03 m)",
    )
    parser.add_argument(
        "--preplacement-max-xy-m",
        type=float,
        default=0.20,
        help="s2 goal-region XY threshold for the later window (default 0.20 m)",
    )
    parser.add_argument(
        "--settle-speed-m-s",
        type=float,
        default=0.01,
        help="target speed under which s1 counts as settled",
    )
    parser.add_argument("--settled-confirm-steps", type=int, default=3)
    parser.add_argument(
        "--joint-mid-fraction",
        type=float,
        default=0.10,
        help="joint s2 progress fraction that fires mid",
    )
    parser.add_argument(
        "--joint-later-fraction",
        type=float,
        default=0.60,
        help="joint s2 progress fraction that fires later",
    )
    parser.add_argument("--video", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--video-fps", type=int, default=20)
    parser.add_argument(
        "--policy",
        choices=("pi05", "smolvla", "openvla_oft", "none"),
        default="pi05",
        help="frozen policy adapter; 'none' runs zero actions with no model loaded",
    )
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--config-name", default="pi05_libero")
    parser.add_argument("--unnorm-key", default=None)
    parser.add_argument("--workspace", default=None)
    parser.add_argument(
        "--libero-home",
        default=None,
        help="upstream LIBERO checkout (or LIBERO_HOME)",
    )
    parser.add_argument(
        "--libero-python",
        default=None,
        help="fallback interpreter able to read .pruned_init (or LIBERO_INIT_PYTHON)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument(
        "--retry-invalid",
        action="store_true",
        help="with --resume, re-run cases whose existing summary has case_valid=false",
    )
    return parser


def _resolve_output(value: Path | None) -> Path:
    if value is not None:
        return value
    return (
        REPO_ROOT
        / "runs"
        / "window-matrix"
        / time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    from libero_rollback.window_matrix import (
        load_window_matrix,
        resolve_compose_root,
        select_window_cases,
    )
    from libero_rollback.window_runner import (
        WindowRunConfig,
        build_window_plan,
        run_window_matrix,
        write_window_plan,
    )

    matrix = load_window_matrix(
        args.matrix, kind=args.matrix_kind, b_matrix=args.b_matrix
    )
    output = _resolve_output(args.output).resolve()
    cases = select_window_cases(
        matrix,
        suites=args.suites,
        windows=args.windows,
        levels=args.levels,
        case_ids=args.case_ids,
        max_cases=args.max_cases,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
    )
    if not cases:
        print("error: the case selection is empty", file=sys.stderr)
        return 2
    print(RULE)
    print(f"{matrix.kind} matrix: {matrix.summary()}")
    print(
        f"selected: {len(cases)} cases / "
        f"{len({case.task_key for case in cases})} tasks"
    )
    print(RULE)

    config = WindowRunConfig(
        init_row=args.init_row,
        seed=args.seed,
        max_steps=args.max_steps,
        replan=args.replan,
        camera=args.camera,
        settle_steps=args.settle_steps,
        repair_window=args.repair_window,
        stop_on_success=bool(args.stop_on_success_after_injection),
        lift_min_m=args.lift_min_m,
        preplacement_max_xy_m=args.preplacement_max_xy_m,
        require_settled_early=bool(args.require_settled_early),
        require_s2_started_early=bool(args.require_s2_started_early),
        settle_speed_m_s=args.settle_speed_m_s,
        settled_confirm_steps=args.settled_confirm_steps,
        joint_mid_fraction=args.joint_mid_fraction,
        joint_later_fraction=args.joint_later_fraction,
        video=bool(args.video),
        video_fps=args.video_fps,
        policy=args.policy,
        libero_home=args.libero_home,
        libero_python=args.libero_python,
        compose_root=(
            str(args.compose_root) if args.compose_root is not None else None
        ),
    )

    if args.dry_run:
        # A dry run must work without the simulation assets; roots are resolved
        # best-effort only so the plan can report real paths when available.
        libero_home = None
        compose_root = None
        try:
            from libero_rollback.runtime.env import resolve_libero_home

            libero_home = str(resolve_libero_home(args.libero_home))
        except Exception:  # noqa: BLE001 - optional in a dry run
            libero_home = None
        if matrix.kind == "D" or any(case.asset_source == "compose" for case in cases):
            try:
                compose_root = str(resolve_compose_root(config.compose_root))
            except Exception:  # noqa: BLE001 - optional in a dry run
                compose_root = None
        import dataclasses

        plan_config = dataclasses.replace(
            config,
            libero_home=libero_home,
            compose_root=compose_root,
        )
        plan = build_window_plan(
            matrix=matrix,
            cases=cases,
            config=plan_config,
            checkpoint=args.checkpoint,
            config_name=args.config_name,
            shard_index=args.shard_index,
            shard_count=args.shard_count,
        )
        plan_path = write_window_plan(output, plan)
        print(
            f"[dry-run] plan written to {plan_path} "
            f"({plan['selected']} cases; no simulation, no model)"
        )
        print(
            f"[dry-run] windows={plan['by_window']} assets_missing="
            f"{plan['assets']['missing_cases']}"
        )
        return 0

    run_window_matrix(
        matrix=matrix,
        cases=cases,
        output=output,
        model=args.policy,
        checkpoint=args.checkpoint,
        config=config,
        config_name=args.config_name,
        unnorm_key=args.unnorm_key,
        workspace=args.workspace,
        resume=bool(args.resume),
        retry_errors=bool(args.retry_errors),
        retry_invalid=bool(args.retry_invalid),
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        # Missing assets / LIBERO checkout / policy setup: fail loudly and
        # concisely (a real run never silently skips a selected case).
        sys.stderr.write(f'error: {error}\n')
        raise SystemExit(2) from error
