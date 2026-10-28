"""Baseline (no-perturbation) validation for LIBERO-90 rollback candidates.

This drives the stock LIBERO-Runtime benchmark runner
(``<runtime-root>/tools/run_benchmark.py``) in ``--mode baseline`` and reuses its
``main()`` unchanged, so results.json / evaluation_summary.json / videos keep the
standard format.  The only addition is a read-only probe: after every control
step each BDDL ``:goal`` atom is evaluated, which lets the baseline answer
"did the policy actually finish s1, and when" for the two-subtask candidates.

Why a probe instead of ``--phase-probe``: that flag needs a task profile
(``configs/task_profiles/<suite>_t<idx>.yaml``) and is silently ignored without
one; no LIBERO-90 profiles exist.

Traces are written to ``<trace-dir>/<bddl>__<n>.jsonl``, one line per control
step (``{"step": i, "truth": [bool, ...]}`` in ``:goal`` order), then a summary
line with per-atom true counts and first/last true step.  Evaluating the
predicates only reads simulator state; actions and episode dynamics are
unchanged.

Usage:
    <pi0-env>/bin/python scripts/run_libero90_baseline.py \
        --runtime-root ../libero-plus/libero-runtime \
        --output runs/libero90-candidates-baseline-pi05-seed3 \
        --trace-dir runs/libero90-candidates-baseline-pi05-seed3/atom-traces \
        --task-ids 4,3,5,8,1,23,63,64,21,45,38 --seed-ids 3 --max-steps 600 --video
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

TRACE_DIR: Path | None = None
_INSTANCE_COUNTER = {"n": 0}
# seed of the episode currently running; filled by the run_episode wrapper so
# trace files can be tagged with the seed that produced them.
CURRENT_SEED: dict[str, int | None] = {"value": None}


def _atom_label(state) -> str:
    return " ".join(str(part) for part in state)


def install_probe(module) -> None:
    """Wrap ``OffScreenRenderEnv.step`` on the runner's own env class."""
    env_cls = module.OffScreenRenderEnv
    original_step = env_cls.step

    def step_with_probe(self, action):
        obs = original_step(self, action)
        _record(self)
        return obs

    env_cls.step = step_with_probe

    # ``install_probe`` is used for baseline sweeps, where ``run_episode`` is the
    # only place that knows the episode seed.
    original_run_episode = module.run_episode

    def run_episode_with_seed(env, *args, **kwargs):
        seed = kwargs.get("seed")
        if seed is None and len(args) >= 6:
            seed = args[5]
        CURRENT_SEED["value"] = seed
        return original_run_episode(env, *args, **kwargs)

    module.run_episode = run_episode_with_seed


def _record(env) -> None:
    state = env.__dict__.setdefault("_atom_probe", None)
    if state is None:
        inner = getattr(env, "env", None)
        atoms = []
        if inner is not None:
            atoms = [list(a) for a in (inner.parsed_problem.get("goal_state") or [])]
        _INSTANCE_COUNTER["n"] += 1
        bddl = Path(str(getattr(env, "bddl_file_name", "unknown"))).stem
        seed = CURRENT_SEED["value"]
        seed_tag = f"seed{seed}" if seed is not None else "seed?"
        path = TRACE_DIR / f"{bddl}__{seed_tag}__{_INSTANCE_COUNTER['n']:03d}.jsonl"
        state = {
            "inner": inner,
            "atoms": atoms,
            "handle": path.open("w", encoding="utf-8"),
            "path": path,
            "step": 0,
            "count": {},
            "first": {},
            "last": {},
        }
        env._atom_probe = state
        state["handle"].write(
            json.dumps(
                {
                    "_meta": True,
                    "bddl": bddl,
                    "seed": seed,
                    "atoms": [_atom_label(a) for a in atoms],
                }
            )
            + "\n"
        )

    truth = []
    for atom in state["atoms"]:
        label = _atom_label(atom)
        try:
            value = bool(state["inner"]._eval_predicate(atom))
        except Exception:  # pragma: no cover - predicate without a live sim object
            value = None
        truth.append(value)
        if value:
            state["count"][label] = state["count"].get(label, 0) + 1
            state["first"].setdefault(label, state["step"])
            state["last"][label] = state["step"]
    state["handle"].write(json.dumps({"step": state["step"], "truth": truth}) + "\n")
    state["handle"].flush()
    state["step"] += 1


def close_traces(module) -> None:
    env_cls = module.OffScreenRenderEnv
    original_close = env_cls.close

    def close_with_summary(self):
        state = self.__dict__.get("_atom_probe")
        if state is not None:
            state["handle"].write(
                json.dumps(
                    {
                        "_summary": True,
                        "steps": state["step"],
                        "true_count": state["count"],
                        "first_true_step": state["first"],
                        "last_true_step": state["last"],
                    }
                )
                + "\n"
            )
            state["handle"].close()
            self.__dict__["_atom_probe"] = None
        return original_close(self)

    env_cls.close = close_with_summary


def main() -> int:
    global TRACE_DIR

    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--trace-dir", type=Path, required=True)
    ap.add_argument("--model", default="pi05")
    ap.add_argument("--suite", default="LIBERO_90")
    ap.add_argument("--task-ids", required=True)
    ap.add_argument("--seed-ids", required=True)
    ap.add_argument("--max-steps", type=int, default=600)
    ap.add_argument("--replan-steps", type=int, default=10)
    ap.add_argument(
        "--success-delay",
        type=int,
        default=0,
        help="hold window after the first success (0 = legacy immediate stop)",
    )
    ap.add_argument(
        "--success-check-interval",
        type=int,
        default=1,
        help="sample the success predicate every N steps inside the hold window",
    )
    ap.add_argument("--video", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    runtime_root = args.runtime_root.resolve()
    if not (runtime_root / "tools/run_benchmark.py").is_file():
        raise SystemExit(f"not a libero-runtime checkout: {runtime_root}")
    if args.success_delay:
        capability_path = runtime_root / "rollback-capabilities.json"
        capabilities: list[str] = []
        if capability_path.is_file():
            capabilities = json.loads(capability_path.read_text()).get("capabilities", [])
        if "success_window" not in capabilities:
            raise SystemExit(
                "the selected runtime overlay does not support --success-delay; "
                "build one with scripts/prepare_success_delay_runtime.py"
            )

    # Resolve every user-supplied path BEFORE chdir, otherwise a relative --output
    # would silently land inside the runtime checkout.
    output = args.output.resolve()
    TRACE_DIR = args.trace_dir.resolve()
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(runtime_root / "tools"))
    sys.path.insert(0, str(runtime_root))
    os.chdir(runtime_root)  # the rollback bridge also runs the runner from here

    import run_benchmark as runner  # noqa: E402

    install_probe(runner)
    close_traces(runner)

    argv = [
        "run_benchmark.py",
        "--model",
        args.model,
        "--mode",
        "baseline",
        "--suite",
        args.suite,
        "--task-ids",
        args.task_ids,
        "--seed-ids",
        args.seed_ids,
        "--max-steps",
        str(args.max_steps),
        "--replan-steps",
        str(args.replan_steps),
        "--output",
        str(output),
    ]
    if args.success_delay:
        argv += [
            "--success-delay",
            str(args.success_delay),
            "--success-check-interval",
            str(args.success_check_interval),
        ]
    if args.video:
        argv.append("--video")
    if args.dry_run:
        argv.append("--dry-run")

    old_argv = sys.argv
    sys.argv = argv
    try:
        return int(runner.main() or 0)
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    raise SystemExit(main())
