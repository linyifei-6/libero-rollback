#!/usr/bin/env python3
"""Evaluate a frozen policy on the *original* LIBERO suites (no perturbation).

Protocol (LIBERO-MAX / LIBERO conventions):
  * suites      libero_spatial / libero_object / libero_goal / libero_10
  * max_steps   400 / 400 / 400 / 700
  * warmup      10 dummy actions ([0,0,0,0,0,0,-1]) before the policy acts
                 (official LIBERO/OFT `num_steps_wait`; --warmup overrides)
  * camera      256 x 256, both agentview and wrist
  * query cadence = the model's native replan (configs/models.yaml)
  * success     env.check_success() at the end of the episode
  * video       agentview + wrist, side by side, 20 fps (H.264 via cv2 mp4v)

This script is intentionally separate from the rollback runner: it exercises the
same PolicyAdapter contract (reset_episode / predict_chunk) on unperturbed
LIBERO tasks, so numbers are comparable to the LIBERO-MAX "Base" column.

Usage::

    python scripts/run_libero_eval.py --policy smolvla \
        --checkpoint work/ckpt/smolvla_local --suites libero_spatial --trials 1 \
        --output runs/libero-smolvla-spatial
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

SUITE_STEPS = {
    "libero_spatial": 400,
    "libero_object": 400,
    "libero_goal": 400,
    "libero_10": 700,
}
CAMERA = 256
WARMUP = 10
DUMMY_ACTION = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0], dtype=np.float32)


def _write_video(path: Path, frames: list[np.ndarray], fps: int = 20) -> None:
    import cv2

    if not frames:
        return
    h, w = frames[0].shape[:2]
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for frame in frames:
        writer.write(cv2.cvtColor(np.ascontiguousarray(frame), cv2.COLOR_RGB2BGR))
    writer.release()


def _stack(obs: dict) -> np.ndarray:
    agent = np.asarray(obs["agentview_image"], dtype=np.uint8)
    wrist = np.asarray(obs["robot0_eye_in_hand_image"], dtype=np.uint8)
    if wrist.ndim == 2:
        wrist = np.stack([wrist] * 3, axis=-1)
    if agent.ndim == 2:
        agent = np.stack([agent] * 3, axis=-1)
    return np.concatenate([agent, wrist], axis=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--policy", required=True, choices=("smolvla", "vlajepa", "openvla_oft"))
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--unnorm-key", default=None)
    parser.add_argument("--suites", nargs="+", default=list(SUITE_STEPS))
    parser.add_argument("--tasks", type=int, default=10, help="tasks per suite (10 max)")
    parser.add_argument("--trials", type=int, default=1, help="episodes per task")
    parser.add_argument("--max-steps", type=int, default=0, help="override the per-suite budget")
    parser.add_argument("--replan", type=int, default=0, help="0 = native cadence from models.yaml")
    parser.add_argument("--camera", type=int, default=CAMERA)
    parser.add_argument("--video", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--warmup", type=int, default=WARMUP, help="no-op steps before the policy acts")
    parser.add_argument("--env-seed", type=int, default=0, help="LIBERO env seed (Windows protocol used 1000)")
    parser.add_argument("--language-source", choices=("filename", "bddl"), default="filename",
                        help="instruction text: LIBERO benchmark (filename-derived) or the BDDL (:language)")
    args = parser.parse_args(argv)

    from libero.libero import benchmark, get_libero_path
    from libero.libero.envs import OffScreenRenderEnv

    from libero_rollback.policies import load_policy, native_replan

    replan = args.replan or native_replan(args.policy) or 10
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    policy = load_policy(
        args.policy,
        checkpoint=args.checkpoint,
        unnorm_key=args.unnorm_key,
        workspace=args.workspace,
        suites=args.suites,
    )
    bench = benchmark.get_benchmark_dict()

    results = []
    suite_unnorm: dict[str, str | None] = {}
    started = time.time()
    for suite in args.suites:
        task_suite = bench[suite]()
        setter = getattr(policy, "set_suite", None)
        if callable(setter):
            setter(suite)
        suite_unnorm[suite] = getattr(policy, "unnorm_key", None)
        steps = args.max_steps or SUITE_STEPS[suite]
        for task_id in range(min(args.tasks, task_suite.n_tasks)):
            task = task_suite.get_task(task_id)
            init_states = task_suite.get_task_init_states(task_id)
            bddl = os.path.join(get_libero_path("bddl_files"), task.problem_folder, task.bddl_file)
            language = task.language
            if args.language_source == "bddl":
                from libero.libero.envs import bddl_utils

                language = bddl_utils.get_problem_info(bddl)["language_instruction"]
            for trial in range(args.trials):
                env = OffScreenRenderEnv(
                    bddl_file_name=bddl,
                    camera_heights=args.camera,
                    camera_widths=args.camera,
                )
                # Official OFT eval always seeds the env with 0: the seed
                # influences object placement even for fixed init states.
                env.seed(args.env_seed)
                # robosuite's OSC controller initialises its goal/tracking state
                # in reset(); set_init_state() alone leaves it stale, which
                # corrupts the first commands (official OFT eval resets first).
                env.reset()
                obs = env.set_init_state(init_states[trial])
                for _ in range(args.warmup):
                    obs, _, _, _ = env.step(DUMMY_ACTION)
                policy.reset_episode(args.seed + trial)

                frames: list[np.ndarray] = []
                if args.video:
                    frames.append(_stack(obs))
                success = False
                t = 0
                while t < steps:
                    chunk = policy.predict_chunk(obs, language)
                    chunk = np.asarray(chunk, dtype=np.float32)
                    if chunk.ndim != 2 or chunk.shape[1] < 7:
                        raise ValueError(f"invalid action chunk shape: {chunk.shape}")
                    for j in range(min(replan, len(chunk))):
                        t += 1
                        obs, _, done, _ = env.step(chunk[j, :7])
                        if args.video:
                            frames.append(_stack(obs))
                        if env.check_success():
                            success = True
                            break
                        if done or t >= steps:
                            break
                    if success:
                        break
                success = success or bool(env.check_success())
                env.close()

                case_dir = output / suite / f"task{task_id:02d}" / f"trial{trial}"
                case_dir.mkdir(parents=True, exist_ok=True)
                video_path = None
                if args.video and frames:
                    video_path = case_dir / "video.mp4"
                    _write_video(video_path, frames)
                rec = {
                    "suite": suite,
                    "task_id": task_id,
                    "trial": trial,
                    "unnorm_key": getattr(policy, "unnorm_key", None),
                    "instruction": language,
                    "success": bool(success),
                    "steps": t,
                    "replan": replan,
                    "video": str(video_path) if video_path else None,
                    "elapsed_s": round(time.time() - started, 2),
                }
                results.append(rec)
                (case_dir / "result.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
                print(
                    f"[{suite} t{task_id:02d} trial{trial}] success={success} steps={t}",
                    flush=True,
                )

    by_suite: dict[str, dict[str, int]] = {}
    for rec in results:
        s = by_suite.setdefault(rec["suite"], {"successes": 0, "episodes": 0})
        s["successes"] += int(rec["success"])
        s["episodes"] += 1
    summary = {
        "policy": args.policy,
        "policy_metadata": dict(getattr(policy, "metadata", {}) or {}),
        "checkpoint": str(args.checkpoint),
        "replan": replan,
        "camera": args.camera,
        "warmup_steps": args.warmup,
        "max_steps_override": args.max_steps,
        "env_seed": args.env_seed,
        "language_source": args.language_source,
        "trials_per_task": args.trials,
        "episodes": len(results),
        "successes": sum(int(r["success"]) for r in results),
        "success_rate": (sum(int(r["success"]) for r in results) / len(results)) if results else None,
        "by_suite": {
            name: {
                **vals,
                "success_rate": vals["successes"] / vals["episodes"] if vals["episodes"] else None,
                "unnorm_key": suite_unnorm.get(name),
            }
            for name, vals in by_suite.items()
        },
        "results": results,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"episodes={summary['episodes']} success={summary['successes']} rate={summary['success_rate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
