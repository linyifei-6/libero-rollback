#!/usr/bin/env python3
"""Thin CLI for the B-suite rollback runner (completion-boundary rollback).

The runner logic lives in :mod:`libero_rollback.runner`; this script only parses
arguments, loads the matrix and writes the dry-run plan.  ``--dry-run`` writes
``plan.json`` only: no simulation is started, no model is loaded, and the plan
is **not** evaluation evidence (README §6.3).

Examples
--------
Dry run (works in the CPU-only env, no LIBERO / MuJoCo / torch)::

    python scripts/run_b_matrix.py --dry-run --matrix dataset/matrices/b-matrix.csv

Real run (inside the simulation environment, one model environment per policy)::

    LIBERO_HOME=/path/to/LIBERO \\
    python scripts/run_b_matrix.py --policy none --suites goal --max-tasks 2 \\
        --output runs/b-smoke
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Sequence
from pathlib import Path

# JAX preallocates 75% of the GPU by default; pi05 only needs ~10 GB.
# Keep the old parallel-with-SmolVLA budget unless the caller overrides it.
os.environ.setdefault("XLA_PYTHON_CLIENT_MEM_FRACTION", "0.42")

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

DEFAULT_MATRIX = REPO_ROOT / "dataset" / "matrices" / "libero-rollback" / "completion-rollback.csv"
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
        help="B matrix CSV (default: dataset/matrices/b-matrix.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="run directory (default: runs/b-matrix/<UTC timestamp>)",
    )
    parser.add_argument("--suites", nargs="*", default=None, help="subset: goal object spatial l10")
    parser.add_argument("--case-ids", nargs="*", default=None)
    parser.add_argument(
        "--levels",
        nargs="*",
        default=None,
        help="subset of levels, e.g. L0 L1 (used by static-init runs)",
    )
    parser.add_argument(
        "--static-init",
        action="store_true",
        help="apply the L0/L1 target pose at t=0 and run the policy without rollback",
    )
    parser.add_argument("--settle-after-injection", type=int, default=0)
    parser.add_argument(
        "--static-targets",
        type=Path,
        default=None,
        help="JSON case_id -> exact target state captured from rollback",
    )
    parser.add_argument("--max-tasks", type=int, default=0)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--init-row", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=600)
    parser.add_argument("--repair-window", type=int, default=600)
    parser.add_argument("--delay-steps", type=int, default=10)
    parser.add_argument("--replan", type=int, default=10)
    parser.add_argument("--camera", type=int, default=256)
    parser.add_argument("--settle-steps", type=int, default=10)
    parser.add_argument(
        "--max-trigger-wait",
        type=int,
        default=60,
        help="after all_done, wait at most N steps for every revoked relation to be true",
    )
    parser.add_argument(
        "--stop-on-recovery",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=("stop a non-C0 episode at the first confirmed recovery; "
              "default keeps the full repair window"),
    )
    parser.add_argument("--recovery-confirm-steps", type=int, default=1)
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
    parser.add_argument(
        "--workspace",
        default=None,
        help="OpenVLA-OFT workspace directory (or OPENVLA_OFT_WORKSPACE)",
    )
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
    return REPO_ROOT / "runs" / "b-matrix" / time.strftime("%Y%m%d_%H%M%S", time.gmtime())


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    from libero_rollback.matrices import load_b_matrix
    from libero_rollback.runner import (
        RunConfig,
        build_plan,
        run_matrix,
        select_cases,
        write_plan,
    )

    matrix = load_b_matrix(args.matrix)
    output = _resolve_output(args.output).resolve()
    cases = select_cases(
        matrix,
        suites=args.suites,
        case_ids=args.case_ids,
        max_tasks=args.max_tasks,
        max_cases=args.max_cases,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
    )
    if args.levels:
        wanted = {level.upper() for level in args.levels}
        cases = [case for case in cases if case.level.upper() in wanted]
    if args.static_init:
        args.stop_on_recovery = False
    print(RULE)
    print(f"B matrix: {matrix.summary()}")
    print(f"selected: {len(cases)} cases / {len({case.task_key for case in cases})} tasks")
    print(RULE)

    config = RunConfig(
        init_row=args.init_row,
        seed=args.seed,
        max_steps=args.max_steps,
        delay_steps=args.delay_steps,
        replan=args.replan,
        camera=args.camera,
        settle_steps=args.settle_steps,
        repair_window=args.repair_window,
        max_trigger_wait=args.max_trigger_wait,
        settle_after_injection=int(args.settle_after_injection),
        static_init=bool(args.static_init),
        static_targets=str(args.static_targets) if args.static_targets else None,
        stop_on_recovery=bool(args.stop_on_recovery),
        recovery_confirm_steps=int(args.recovery_confirm_steps),
        video=bool(args.video),
        video_fps=args.video_fps,
        policy=args.policy,
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
        plan_path = write_plan(output, plan)
        print(
            f"[dry-run] plan written to {plan_path} "
            f"({plan['selected']} cases; no simulation, no model)"
        )
        return 0

    run_matrix(
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
    raise SystemExit(main())
