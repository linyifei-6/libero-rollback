"""Shared CLI configuration for the evaluation runners.

Every environment-specific value (repository roots, interpreter paths, checkpoint) and every
benchmark parameter is exposed here instead of being embedded in a runner. Runners add these
arguments, then forward anything they do not model themselves straight to the benchmark, so a
runtime option can be used without editing code.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLUS_ROOT = ROOT.parent / "libero-plus"

# Which interpreter each model needs. Overridable with --model-python.
DEFAULT_MODEL_PYTHONS = {
    "pi05": "openpi/.venv/bin/python",
    "pi0": "openpi/.venv/bin/python",
    "pi0_fast": "openpi/.venv/bin/python",
    "pi05_lerobot": "openpi/.venv/bin/python",
    "openvla_oft": "openvla-oft-env/bin/python",
    "smolvla": "openvla-oft-env/bin/python",
}
DEFAULT_CHECKPOINT = ("models/openvla-7b-oft-finetuned-libero-spatial-object-goal-10")
DEFAULT_VIDEO_ENCODER_PYTHON = "openpi/.venv/bin/python"
MODELS = sorted(DEFAULT_MODEL_PYTHONS)

# Timing windows a case can declare in `trigger.time_point`. `all_done` covers the
# completion-boundary group, which only fires after the task has already succeeded.
WINDOWS = ("early", "mid", "later", "all_done")

# Parameters the runner itself controls; everything else on the command line is forwarded.
RUNNER_OWNED = {
    "--model", "--model-python", "--plus-root", "--checkpoint", "--video-encoder-python",
    "--runtime-root", "--cases", "--output", "--suite", "--dimension", "--task-idx",
    "--seed", "--task-seed", "--task", "--case-id", "--limit", "--forward",
    "--dry-run", "--help", "-h",
}


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Register the parameters shared by every runner."""

    parser.add_argument("--model", default="pi05", choices=MODELS)
    parser.add_argument("--plus-root", type=Path, default=DEFAULT_PLUS_ROOT,
                        help="root of the sibling libero-plus checkout")
    parser.add_argument("--model-python", type=Path, default=None,
                        help="interpreter that can import the policy; defaults per model")
    parser.add_argument("--checkpoint", type=Path, default=None,
                        help="policy checkpoint; defaults per model")
    parser.add_argument("--video-encoder-python", type=Path, default=None,
                        help="interpreter used to encode videos")
    parser.add_argument("--runtime-root", type=Path, default=None,
                        help="evaluator overlay holding tools/run_benchmark.py")
    parser.add_argument("--cases", type=Path, default=ROOT / "dataset/current",
                        help="catalog directory with manifest.yaml, or a case directory")
    parser.add_argument("--output", type=Path, default=ROOT / "runs/current-validation")
    parser.add_argument("--suite", default="LIBERO_10")
    parser.add_argument("--dimension", default="rollback")
    parser.add_argument("--max-steps", type=int, default=600)
    parser.add_argument("--replan-steps", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0,
                        help="single explicit seed; overridden by --seed-ids or --seeds")
    parser.add_argument("--seed-ids", default="",
                        help="comma-separated explicit seed ids, e.g. --seed-ids 0,1,2")
    parser.add_argument("--seeds", type=int, default=0,
                        help="number of seeds to sweep from 0, e.g. --seeds 3 -> 0,1,2. "
                             "A single run then covers every seed, so the model is loaded once")
    parser.add_argument(
        "--cam", type=int, default=0,
        help="camera resolution in pixels; the runtime default (256) applies when unset",
    )
    parser.add_argument("--resume", action="store_true",
                        help="skip cases whose results already exist and are complete")
    parser.add_argument("--overwrite", action="store_true",
                        help="delete existing results for the selected cases and rerun them")
    parser.add_argument("--task-seed", action="append", default=[],
                        help="per-task seed override, e.g. 03=1")
    parser.add_argument("--task", action="append", default=[],
                        help="restrict to dataset task indexes, e.g. --task 03")
    parser.add_argument("--window", action="append", default=[], choices=WINDOWS,
                        help="restrict to trigger timing windows: " + ", ".join(WINDOWS))
    parser.add_argument("--severity", action="append", default=[],
                        help="restrict to case severity labels, e.g. --severity n3 --severity pose")
    parser.add_argument("--mechanism", action="append", default=[],
                        help="restrict to a rollback mechanism (state_change.kind), e.g. "
                             "apply_episode_initial_offset")
    parser.add_argument("--semantics", action="append", default=[],
                        help="restrict to expected evaluation semantics, e.g. relation_only")
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--video", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--forward", action="append", default=[],
                        help="extra benchmark argument, e.g. --forward=--post-success-window")


def resolve_model_python(args: argparse.Namespace) -> Path:
    """The interpreter that can import the policy.

    Deliberately not resolved: `venv/bin/python` is a symlink to the base interpreter, and
    dereferencing it would drop the environment that holds the model dependencies.
    """

    if args.model_python is not None:
        return Path(os.path.abspath(args.model_python))
    rel = DEFAULT_MODEL_PYTHONS.get(args.model)
    if rel is None:
        raise SystemExit(
            f"no default interpreter for model {args.model!r}; pass --model-python")
    return Path(os.path.abspath(args.plus_root / rel))


def resolve_checkpoint(args: argparse.Namespace) -> Path | None:
    if args.model != "openvla_oft":
        return None
    if args.checkpoint is not None:
        return Path(os.path.abspath(args.checkpoint))
    return Path(os.path.abspath(args.plus_root / DEFAULT_CHECKPOINT))


def resolve_video_encoder(args: argparse.Namespace) -> Path:
    if args.video_encoder_python is not None:
        return Path(os.path.abspath(args.video_encoder_python))
    return Path(os.path.abspath(args.plus_root / DEFAULT_VIDEO_ENCODER_PYTHON))


def parse_with_forwarding(
    parser: argparse.ArgumentParser, argv: list[str] | None = None
) -> tuple[argparse.Namespace, list[str]]:
    """Parse the runner's own options and keep everything else for the benchmark.

    Any benchmark option that the runner does not model is returned untouched, so extending
    the evaluation never requires editing the runner.
    """

    args, unknown = parser.parse_known_args(argv)
    forwarded: list[str] = []
    for item in args.forward:
        forwarded.extend(item.split())
    forwarded.extend(unknown)
    args.forward = forwarded
    return args, forwarded


def forwarded_arguments(args: argparse.Namespace) -> list[str]:
    """Benchmark options collected by `parse_with_forwarding`."""

    return list(getattr(args, "forward", []) or [])


def base_environment(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    env["LIBERO_VIDEO_ENCODER_PYTHON"] = str(resolve_video_encoder(args))
    return env

def case_window(case: dict) -> str | None:
    """The declared timing window of a case, or None when it declares none."""

    trigger = case.get("trigger") or {}
    value = trigger.get("time_point")
    return str(value) if value is not None else None


def matches_window(case: dict, wanted: list[str]) -> bool:
    """`--window` filter. An empty list keeps every case."""

    if not wanted:
        return True
    return case_window(case) in set(wanted)

def case_severity(case: dict) -> str | None:
    value = case.get("severity")
    return str(value) if value is not None else None


def case_mechanism(case: dict) -> str | None:
    """The rollback mechanism: the state_transform kind this case performs."""

    change = (case.get("rollback_target") or {}).get("state_change") or {}
    value = change.get("kind")
    return str(value) if value is not None else None


def case_semantics(case: dict) -> str | None:
    value = case.get("expected_evaluation_semantics")
    return str(value) if value is not None else None


def matches_filters(case: dict, args) -> bool:
    """Apply every selection axis the runner exposes. Empty selections keep everything."""

    def keep(values: list[str], actual: str | None) -> bool:
        return not values or actual in set(values)

    return (
        keep(args.window, case_window(case))
        and keep(args.severity, case_severity(case))
        and keep(args.mechanism, case_mechanism(case))
        and keep(args.semantics, case_semantics(case))
        and keep(args.case_id, case["case_id"])
    )

def selected_seed_ids(args) -> list[int]:
    """The seeds this run should cover.

    `--seed-ids` is explicit, `--seeds N` sweeps 0..N-1, and `--seed` covers one seed. The
    runtime prefers `--seed-ids` over `--seeds`, so a sweep is expressed as an explicit list
    and every seed is covered inside a single model load.
    """

    if args.seed_ids:
        ids = [int(item.strip()) for item in str(args.seed_ids).split(",") if item.strip()]
        if not ids or any(i < 0 for i in ids):
            raise SystemExit("--seed-ids needs non-negative integers, e.g. 0,1,2")
        return sorted(set(ids))
    if args.seeds:
        if args.seeds < 1:
            raise SystemExit("--seeds must be at least 1")
        return list(range(args.seeds))
    return [int(args.seed)]


def task_seed_map(args) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in args.task_seed:
        key, _, value = str(item).partition("=")
        if not key or not value:
            raise SystemExit(f"--task-seed expects NN=seed, got {item!r}")
        mapping[key] = value
    return mapping


def forwarded_runtime_options(args, exclude: tuple[str, ...] = ()) -> list[str]:
    """Forwarded benchmark options, minus anything the runner sets itself."""

    blocked = set(exclude)
    out: list[str] = []
    pending = list(forwarded_arguments(args))
    index = 0
    while index < len(pending):
        token = pending[index]
        if token in blocked:
            index += 1
            if index < len(pending) and not pending[index].startswith("--"):
                index += 1
            continue
        out.append(token)
        index += 1
    return out
