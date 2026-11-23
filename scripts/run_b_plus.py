#!/usr/bin/env python3
"""Goal-suite runner for the isolated B-plus matrix.

This is a separate entry point: it reads ``dataset/matrices/plus/b-matrix-plus.csv``
and does **not** touch the v2 ``b-matrix.csv`` loader.  Only the ``rollback``,
``c0`` and ``l0`` arms are executable here; ``fresh`` is the LIBERO-Plus O2
baseline and is not run by this script.

The injection is a single-state write of the revoked target's 7-DoF pose from
the LIBERO-Plus O2 ``.pruned_init``; the episode itself starts from the normal
LIBERO task/init and is completed by the policy first.

Examples
--------
Dry run::

    PYTHONPATH=src .venv/bin/python scripts/run_b_plus.py --dry-run --split core

Real run (same env as the previous B run)::

    MUJOCO_GL=osmesa PYTHONPATH=src \\
    "$OPENPI/.venv/bin/python" \\
        scripts/run_b_plus.py --suite goal --split core --video \\
        --stop-on-recovery \\
        --libero-home "$OPENPI/third_party/libero" \\
        --checkpoint "$OPENPI_CHECKPOINTS/pi05_libero" \\
        --output runs/b-plus-goal-core
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

# JAX preallocates 75% of the GPU by default; pi05 only needs ~10 GB.
# Keep the old parallel-with-SmolVLA budget unless the caller overrides it.
os.environ.setdefault("XLA_PYTHON_CLIENT_MEM_FRACTION", "0.42")

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

DEFAULT_MATRIX = REPO_ROOT / "dataset" / "matrices" / "plus" / "b-matrix-plus.csv"
DEFAULT_O2_ROOT = REPO_ROOT / ".cache" / "liberoplus-clone"
RULE = "-" * 78


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--o2-root", type=Path, default=DEFAULT_O2_ROOT)
    parser.add_argument("--suite", default="goal", choices=("goal", "object", "spatial", "l10"))
    parser.add_argument("--arms", nargs="*", default=["rollback", "c0", "l0"])
    parser.add_argument("--split", default="core", choices=("core", "full", "both"))
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--case-ids", nargs="*", default=None)
    parser.add_argument(
        "--case-ids-file",
        type=Path,
        default=None,
        help="one case_id per line; combined with --case-ids",
    )
    parser.add_argument("--init-row", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=600)
    parser.add_argument("--delay-steps", type=int, default=10)
    parser.add_argument("--repair-window", type=int, default=300)
    parser.add_argument(
        "--settle-after-injection",
        type=int,
        default=10,
        help="physics settle steps after the O2 write; 0 keeps the immediate-check protocol",
    )
    parser.add_argument("--replan", type=int, default=10)
    parser.add_argument("--camera", type=int, default=256)
    parser.add_argument("--settle-steps", type=int, default=10)
    parser.add_argument("--max-trigger-wait", type=int, default=60)
    parser.add_argument("--stop-on-recovery", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--recovery-confirm-steps", type=int, default=1)
    parser.add_argument("--video", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--video-fps", type=int, default=20)
    parser.add_argument(
        "--policy", choices=("pi05", "smolvla", "openvla_oft", "none"), default="pi05"
    )
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--config-name", default="pi05_libero")
    parser.add_argument("--libero-home", default=None)
    parser.add_argument("--libero-python", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    return parser


def _resolve_output(value: Path | None) -> Path:
    if value is not None:
        return value
    return REPO_ROOT / "runs" / "b-plus" / time.strftime("%Y%m%d_%H%M%S", time.gmtime())


def _case_from_row(row: dict[str, str], o2_root: Path):
    from libero_rollback.matrices import BCase

    arm = row["arm"].strip()
    common = dict(
        case_id=row["case_id"].strip(),
        suite=row["suite"].strip(),
        task_idx=int(row["task_idx"]),
        bddl_name=row["bddl_name"].strip(),
        instruction=row["instruction"].strip(),
        trigger="all_done",
        delay_steps=int(row.get("delay_steps") or 10),
        repair_window=int(row.get("repair_window") or 300),
    )
    if arm == "c0":
        return BCase(
            **common,
            target="c0",
            revoked_objects=(),
            revoked_predicates=(),
            family="-",
            level="C0",
            param=None,
            semantics="relation_holds_control",
            expected_relation_after=True,
            n_targets=0,
            o2_init=None,
        )
    if arm == "l0":
        return BCase(
            **common,
            target="g",
            revoked_objects=(row["target_obj"].strip(),),
            revoked_predicates=(row["revoked_predicate"].strip(),),
            family="pose",
            level="L0",
            param=None,
            semantics="relation_then_resume",
            expected_relation_after=False,
            n_targets=1,
            o2_init=None,
        )
    if arm == "rollback":
        init_rel = row["o2_init"].strip()
        o2_init = str((o2_root / init_rel).resolve()) if init_rel else None
        return BCase(
            **common,
            target="g",
            revoked_objects=(row["target_obj"].strip(),),
            revoked_predicates=(row["revoked_predicate"].strip(),),
            family="pose",
            level="O2",
            param=f"l{int(row['o2_level'])}s{int(row['o2_sample'])}",
            semantics="relation_then_resume",
            expected_relation_after=False,
            n_targets=1,
            o2_init=o2_init,
        )
    raise ValueError(f"unsupported arm {arm!r} (fresh is not executable here)")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if "fresh" in args.arms:
        raise SystemExit("fresh arm is not executable in run_b_plus.py; run it separately")

    from libero_rollback.matrices import BMatrix
    from libero_rollback.runner import RunConfig, build_plan, run_matrix, write_plan

    matrix_path = args.matrix.resolve()
    rows = list(csv.DictReader(matrix_path.open(encoding="utf-8")))
    wanted = set(args.arms)
    selected = []
    for row in rows:
        if row["suite"].strip() != args.suite:
            continue
        if row["arm"].strip() not in wanted:
            continue
        if args.split != "both" and row["split"].strip() != args.split:
            continue
        wanted_ids = set(args.case_ids or [])
        if args.case_ids_file:
            wanted_ids.update(
                line.strip()
                for line in args.case_ids_file.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            )
        if wanted_ids and row["case_id"].strip() not in wanted_ids:
            continue
        selected.append(row)
    if args.max_cases:
        selected = selected[: args.max_cases]
    cases = [_case_from_row(row, args.o2_root) for row in selected]
    matrix = BMatrix(cases=cases, source=matrix_path)
    output = _resolve_output(args.output).resolve()

    print(RULE)
    print(f"B-plus matrix: {matrix.summary()}")
    print(f"selected: {len(cases)} cases / {len({c.task_key for c in cases})} tasks")
    print(RULE)

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
        settle_after_injection=int(args.settle_after_injection),
        stop_on_recovery=bool(args.stop_on_recovery),
        recovery_confirm_steps=args.recovery_confirm_steps,
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
        )
        path = write_plan(output, plan)
        print(f"[dry-run] plan written to {path} ({len(cases)} cases)")
        return 0

    run_matrix(
        matrix=matrix,
        cases=cases,
        output=output,
        model=args.policy,
        checkpoint=args.checkpoint,
        config=config,
        config_name=args.config_name,
        resume=bool(args.resume),
        script="scripts/run_b_plus.py",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
