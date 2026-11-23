"""Four-state B-suite episode runner: plan, run, resume, aggregate.

One case is one episode:

1. start the native LIBERO task from ``.pruned_init`` row ``--init-row`` and
   settle;
2. let the frozen policy solve the task;
3. wait ``--delay-steps`` after ``all_done`` (every native goal atom true);
4. inject the matrix perturbation (``C0``/``L0``/``L1``/``L2``, target
   ``g``/``s1``/``s2``/``both``/``pre``) and gate it on the README §5.2
   per-case checks;
5. keep the same policy running for ``repair_window`` extra steps and record
   whether the revoked relation comes back.

Artifacts per episode: ``summary.json``, ``trace.jsonl`` and (optional)
``video.mp4``, under ``<output>/<suite>/<case_id>/seed-<seed>/``.  A run directory
is resumable: a case whose ``summary.json`` has ``status == "ok"`` is skipped
when ``--resume`` is on.  ``run-summary.json`` / ``report.md`` are written at the
end of every run.

Module boundary (enforced by tests): the top level of this module imports only
the stdlib and :mod:`libero_rollback.matrices`.  numpy, LIBERO/MuJoCo, the
perturbation injector, the video recorder and the policy adapters are imported
inside the functions that use them, so ``--dry-run`` and ``--policy none`` work
in the CPU-only environment (no torch / MuJoCo / LIBERO required).
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .matrices import BCase, BMatrix

SCHEMA_VERSION = 2
RULE = "-" * 78
DUMMY_ACTION = [0.0] * 6 + [-1.0]

#: Environment variable that carries the default checkpoint per model.
CHECKPOINT_ENV: Mapping[str, str] = {
    "pi05": "PI05_CHECKPOINT",
    "smolvla": "SMOLVLA_CHECKPOINT",
    "openvla_oft": "OPENVLA_OFT_CHECKPOINT",
}


@dataclass(frozen=True)
class RunConfig:
    """Protocol parameters of one run (README §6.2)."""

    init_row: int = 0
    seed: int = 0
    max_steps: int = 600
    delay_steps: int = 10
    replan: int = 10
    camera: int = 256
    settle_steps: int = 10
    max_trigger_wait: int = 60
    repair_window: int = 600
    settle_after_injection: int = 0
    static_init: bool = False
    static_targets: str | None = None
    stop_on_recovery: bool = False
    recovery_confirm_steps: int = 1
    video: bool = True
    video_fps: int = 20
    policy: str = "none"
    libero_home: str | None = None
    libero_python: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "init_row": self.init_row,
            "seed": self.seed,
            "max_steps": self.max_steps,
            "delay_steps": self.delay_steps,
            "replan": self.replan,
            "camera": self.camera,
            "settle_steps": self.settle_steps,
            "max_trigger_wait": self.max_trigger_wait,
            "repair_window": self.repair_window,
            "settle_after_injection": self.settle_after_injection,
            "static_init": self.static_init,
            "static_targets": self.static_targets,
            "stop_on_recovery": self.stop_on_recovery,
            "recovery_confirm_steps": self.recovery_confirm_steps,
            "video": self.video,
            "video_fps": self.video_fps,
            "policy": self.policy,
            "libero_home": self.libero_home,
            "libero_python": self.libero_python,
        }


# ---------------------------------------------------------------------------
# planning (pure: stdlib + matrices)
# ---------------------------------------------------------------------------


def select_cases(
    matrix: BMatrix,
    *,
    suites: Sequence[str] | None = None,
    case_ids: Sequence[str] | None = None,
    max_tasks: int = 0,
    max_cases: int = 0,
    shard_index: int = 0,
    shard_count: int = 1,
) -> list[BCase]:
    """Select the cases of one run (suite/case-id filters, limits, sharding).

    Sharding is deterministic: case ``i`` belongs to shard ``i % shard_count``
    of the filtered, ordered case list, so the union of all shards equals the
    selection and every case runs exactly once.
    """

    if shard_count < 1:
        raise ValueError(f"shard_count must be >= 1, got {shard_count}")
    if not 0 <= shard_index < shard_count:
        raise ValueError(
            f"shard_index must be in [0, {shard_count}), got {shard_index}"
        )
    if max_cases < 0 or max_tasks < 0:
        raise ValueError("max_cases/max_tasks must be >= 0")
    cases = matrix.select(suites=suites, case_ids=case_ids, max_tasks=int(max_tasks))
    if max_cases:
        cases = cases[: int(max_cases)]
    if shard_count > 1:
        cases = [
            case
            for index, case in enumerate(cases)
            if index % shard_count == shard_index
        ]
    return cases


def build_plan(
    *,
    matrix: BMatrix,
    cases: Sequence[BCase],
    config: RunConfig,
    checkpoint: str | None = None,
    config_name: str = "pi05_libero",
    shard_index: int = 0,
    shard_count: int = 1,
) -> dict[str, Any]:
    """Return the ``plan.json`` payload for a dry run (not evidence)."""

    by_suite: dict[str, int] = {}
    by_level: dict[str, int] = {}
    for case in cases:
        by_suite[case.suite] = by_suite.get(case.suite, 0) + 1
        by_level[case.level] = by_level.get(case.level, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "dry_run": True,
        "matrix": matrix.summary(),
        "selected": len(cases),
        "tasks": len({case.task_key for case in cases}),
        "by_suite": dict(sorted(by_suite.items())),
        "by_level": dict(sorted(by_level.items())),
        "case_ids": [case.case_id for case in cases],
        "cases": [
            {
                "case_id": case.case_id,
                "suite": case.suite,
                "task_idx": case.task_idx,
                "bddl_name": case.bddl_name,
                "target": case.target,
                "level": case.level,
                "param": case.param,
                "delay_steps": case.delay_steps,
                "repair_window": max(int(case.repair_window), int(config.repair_window)),
                "expected_relation_after": case.expected_relation_after,
            }
            for case in cases
        ],
        "shard": {"index": shard_index, "count": shard_count},
        "defaults": {
            **config.as_dict(),
            "checkpoint": checkpoint,
            "config_name": config_name,
            "matrix": str(matrix.source),
        },
    }


def write_json(path: str | Path, payload: Any) -> Path:
    """Write a UTF-8 JSON file, creating parents."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    return target


def write_plan(output: str | Path, payload: Mapping[str, Any]) -> Path:
    """Write ``plan.json`` (the only artifact of a dry run)."""

    return write_json(Path(output) / "plan.json", payload)


def episode_directory(output: str | Path, case: BCase, seed: int) -> Path:
    """``<output>/<suite>/<case_id>/seed-<seed>/`` (run artifact layout)."""

    return Path(output) / case.suite / case.case_id / f"seed-{int(seed)}"


# ---------------------------------------------------------------------------
# small shared helpers
# ---------------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def _resolve_checkpoint(model: str, value: str | None) -> str | None:
    """Resolve the checkpoint path from the CLI, the model env var or a default."""

    if model == "none":
        return None
    if value:
        return str(Path(value).expanduser())
    env_name = CHECKPOINT_ENV.get(model)
    env_value = os.environ.get(env_name) if env_name else None
    if env_value:
        return str(Path(env_value).expanduser())
    if model == "pi05":
        return str(
            Path.home()
            / ".cache"
            / "openpi"
            / "openpi-assets"
            / "checkpoints"
            / "pi05_libero"
        )
    raise ValueError(
        f"--policy {model} needs --checkpoint"
        + (f" or {env_name}" if env_name else "")
    )


def _target_center(injector) -> Any:
    """Mean world position of the revoked targets (numpy, lazy)."""

    import numpy as np

    positions = []
    for target in injector.targets.values():
        if target.body_id is not None:
            positions.append(
                np.asarray(injector.sim.data.body_xpos[target.body_id], dtype=np.float64)
            )
    if positions:
        return np.mean(np.stack(positions, axis=0), axis=0)
    return None


def _reset_policy(policy, seed: int) -> None:
    reset = getattr(policy, "reset_episode", None)
    if reset is None:
        reset = getattr(policy, "reset", None)
    if reset is None:
        raise TypeError(
            "policy adapter must implement reset_episode(seed) or reset(seed)"
        )
    reset(int(seed))


def _predict_chunk(policy, obs: Mapping[str, Any], instruction: str) -> Any:
    predict = getattr(policy, "predict_chunk", None)
    if predict is None:
        predict = getattr(policy, "predict", None)
    if predict is None:
        raise TypeError(
            "policy adapter must implement predict_chunk(obs, instruction) "
            "or predict(obs, instruction)"
        )
    return predict(obs, instruction)


def _count_video_frames(path: Path) -> int | None:
    try:
        import cv2  # type: ignore

        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            return None
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        capture.release()
        return frames or None
    except Exception:  # noqa: BLE001 - optional dependency
        return None


def _environment_summary() -> dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": sys.platform,
        "mujoco_gl": os.environ.get("MUJOCO_GL"),
        "libero_config_path": os.environ.get("LIBERO_CONFIG_PATH"),
    }


# ---------------------------------------------------------------------------
# one episode
# ---------------------------------------------------------------------------


def run_case(
    *,
    case: BCase,
    config: RunConfig,
    policy,
    output: str | Path,
) -> dict[str, Any]:
    """Run one case; always writes ``summary.json`` (also on failure).

    The environment, injection and video backends are imported lazily: this
    function is only reachable from a real (non dry-run) run.
    """

    episode_dir = episode_directory(output, case, config.seed)
    episode_dir.mkdir(parents=True, exist_ok=True)
    trace_path = episode_dir / "trace.jsonl"
    trace = trace_path.open("w", encoding="utf-8")

    def emit(event: Mapping[str, Any]) -> None:
        trace.write(
            json.dumps(
                {"t": round(time.time(), 3), **_jsonable(dict(event))},
                ensure_ascii=False,
            )
            + "\n"
        )
        trace.flush()

    # Protocol floor: a rollback case gets at least 600 post-injection steps.
    # The frozen matrix column remains a reference value; the run config can
    # only raise it, never silently shorten it below the floor.
    repair_window = max(int(case.repair_window or 0), int(config.repair_window))
    total_budget = int(config.max_steps)
    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "running",
        "case_id": case.case_id,
        "task_id": case.case_id,
        "suite": case.suite,
        "task_idx": case.task_idx,
        "bddl_name": case.bddl_name,
        "instruction": case.instruction,
        "language": case.instruction,
        "target": case.target,
        "level": case.level,
        "param": case.param,
        "family": case.family,
        "semantics": case.semantics,
        "expected_relation_after": case.expected_relation_after,
        "revoked_objects": list(case.revoked_objects),
        "revoked_predicates": list(case.revoked_predicates),
        "goal_atoms": [],
        "subgoals": [],
        "setup": {
            "suite": case.suite,
            "init_row": config.init_row,
            "seed": config.seed,
            "max_steps": config.max_steps,
            "delay_steps": config.delay_steps,
            "replan": config.replan,
            "trigger": case.trigger,
            "repair_window": repair_window,
        },
        "max_steps": config.max_steps,
        "active_budget_steps": config.max_steps,
        "total_budget_steps": total_budget,
        "steps": 0,
        "checks": 0,
        "trigger_reached": False,
        "policy": None if policy is None else dict(policy.metadata),
        "config": config.as_dict(),
    }
    env = None
    recorder = None
    started = time.time()
    try:
        import numpy as np

        from .runtime.env import load_init_row
        from .runtime.perturbation import BInjector

        if not config.libero_home:
            raise RuntimeError(
                "run_case needs a resolved LIBERO checkout; call run_matrix "
                "(which resolves --libero-home / LIBERO_HOME first)"
            )
        from libero.libero.envs import OffScreenRenderEnv

        init_shape, init_row = load_init_row(
            case.init_path(config.libero_home),
            config.init_row,
            config.libero_python,
        )
        bddl_path = case.bddl_path(config.libero_home)
        env = OffScreenRenderEnv(
            bddl_file_name=str(bddl_path),
            camera_heights=config.camera,
            camera_widths=config.camera,
            # The v2 budget is 600 active steps + repair_window; the env
            # horizon must cover the extended post-injection budget.
            horizon=config.max_steps + repair_window + 100,
        )
        env.seed(config.seed)
        env.reset()
        obs = env.set_init_state(init_row)
        if not isinstance(obs, Mapping):
            obs = env.env._get_observations()  # noqa: SLF001 - LIBERO internal API
        for _ in range(config.settle_steps):
            obs, _, done, _ = env.step(DUMMY_ACTION)
            if done:
                raise RuntimeError(
                    "task succeeded during settling (init row must not be solved)"
                )

        problem = env.env
        goal_atoms = [
            tuple(atom) for atom in (problem.parsed_problem.get("goal_state") or [])
        ]
        summary["goal_atoms"] = [list(atom) for atom in goal_atoms]
        if not goal_atoms:
            raise RuntimeError("empty native goal state")
        injector = BInjector(env, case, goal_atoms)
        revoked_goal_indices = sorted(
            {idx for idx in getattr(injector, "goal_atom_index", ()) if idx >= 0}
        )
        pending_goal_indices = [
            idx for idx in range(len(goal_atoms)) if idx not in set(revoked_goal_indices)
        ]
        summary["revoked_goal_indices"] = revoked_goal_indices
        summary["pending_goal_indices"] = pending_goal_indices
        injector.static_init = config.static_init
        if config.static_targets:
            targets = json.loads(Path(config.static_targets).read_text(encoding="utf-8"))
            injector.static_target = targets.get(case.case_id)
        for name, target in injector.targets.items():
            if target.body_id is None:
                raise RuntimeError(f"cannot resolve revoked object body: {name}")
        emit(
            {
                "event": "episode_start",
                "case_id": case.case_id,
                "bddl": str(bddl_path),
                "init_shape": list(init_shape),
                "goal_atoms": [list(atom) for atom in goal_atoms],
                "targets": {
                    name: target.kind for name, target in injector.targets.items()
                },
                "settle_steps": config.settle_steps,
            }
        )

        if policy is not None:
            _reset_policy(policy, config.seed)
        if config.video:
            from .runtime.video import AnnotatedVideoRecorder

            recorder = AnnotatedVideoRecorder(
                episode_dir / "video.mp4", fps=config.video_fps
            )

        queue: list[Any] = []
        steps = 0
        first_all_done: int | None = None
        injected = False
        injection: dict[str, Any] | None = None
        injection_step: int | None = None
        injection_frame: int | None = None
        injection_wait_steps = 0
        pre_truths: list[bool] | None = None
        restored_at_step: int | None = None
        recovery_ever = False
        recovery_streak = 0
        early_stopped = False
        post_truths: list[list[bool]] = []
        notice_latency: int | None = None
        eef_baseline: float | None = None
        success_ever = False
        first_success_step: int | None = None
        stage_label = f"B {case.case_id} | {case.level}"
        if config.static_init:
            # Static baseline: apply the L0/L1 target pose at t=0, before the
            # policy has ever seen the task.  No all_done trigger, no rollback.
            injection = injector.inject(obs.get("robot0_gripper_qpos"))
            injection["static_init"] = True
            injection_step = 0
            injected = True
            pre_truths = list(injector.revoked_truth())
            post_truths = []
            if config.settle_after_injection:
                for _ in range(max(0, int(config.settle_after_injection))):
                    obs, _, done, _ = env.step(DUMMY_ACTION)
                    steps += 1
                injection = injector.revalidate(obs.get("robot0_gripper_qpos"))
                injection["static_init"] = True
            total_budget = steps + config.max_steps
            summary["static_init"] = True
            summary["injection"] = injection
            summary["injection_step"] = 0
            summary["total_budget_steps"] = total_budget
            summary["settle_after_injection"] = int(config.settle_after_injection)
            if recorder is not None:
                injection_frame = recorder.frames
                recorder.event_card(
                    obs["agentview_image"],
                    obs.get("robot0_eye_in_hand_image"),
                    title=f"STATIC-INIT  {case.case_id}  @ t=0",
                    lines=[
                        (
                            f"target={case.target} level={case.level}-{case.param or ''}",
                            (255, 230, 120),
                            recorder.font,
                        ),
                        (
                            f"relation before={all(pre_truths)} "
                            f"after={injection['relation_after']}",
                            (235, 235, 240),
                            recorder.font,
                        ),
                        (
                            f"delta_translation={injection['geometry']['delta_translation_m']} m",
                            (170, 200, 230),
                            recorder.font_small,
                        ),
                    ],
                    highlight=(110, 200, 255),
                )
        while steps < total_budget:
            if policy is None:
                action = np.zeros(7, dtype=np.float64)
            else:
                if not queue:
                    chunk = _predict_chunk(policy, obs, case.instruction)
                    queue.extend(
                        np.asarray(chunk, dtype=np.float64)[: max(1, config.replan)]
                    )
                action = np.asarray(queue.pop(0), dtype=np.float64)
            obs, _, done, _ = env.step(action.tolist())
            steps += 1
            goal_truth = injector.goal_truth()
            revoked_truth = injector.revoked_truth()
            all_done = bool(all(goal_truth))
            if all(goal_truth):
                if first_all_done is None:
                    first_all_done = steps
                    emit(
                        {
                            "event": "all_done",
                            "step": steps,
                            "goal": goal_truth,
                            "revoked": revoked_truth,
                        }
                    )
                if first_success_step is None:
                    first_success_step = steps
                success_ever = True
                if config.static_init:
                    summary["static_stopped_on_success"] = True
                    break

            should_inject = False
            if (
                not injected
                and first_all_done is not None
                and steps - first_all_done >= config.delay_steps
            ):
                if all(goal_truth) and all(revoked_truth):
                    should_inject = True
                else:
                    injection_wait_steps += 1
                    if injection_wait_steps >= config.max_trigger_wait:
                        summary["trigger_skipped_reason"] = (
                            "revoked relation was not true at all_done within "
                            f"{config.max_trigger_wait} steps"
                        )
                        break

            if should_inject:
                pre_truths = list(revoked_truth)
                post_truths.append(list(revoked_truth))
                # Record the last pre-injection frame, then the decision card.
                if recorder is not None:
                    recorder.step(
                        obs["agentview_image"],
                        obs.get("robot0_eye_in_hand_image"),
                        step=steps,
                        stage=stage_label,
                        horizon_index=0,
                        last_decision={
                            "line": (
                                f"all_done + delay={config.delay_steps} -> "
                                f"inject {case.level}"
                            )
                        },
                        success=False,
                        title=f"B matrix | {case.case_id}",
                        policy_label=f"frozen {config.policy}",
                        controller_label="pure policy",
                    )
                injection = injector.inject(obs.get("robot0_gripper_qpos"))
                injection_step = steps
                injected = True
                # v2 budget: the repair window is appended *after* injection and
                # is not squeezed by a total-step cap (README §9.3 item 3).
                total_budget = steps + repair_window
                summary["trigger_reached"] = True
                summary["trigger_step"] = steps
                summary["injection_step"] = steps
                summary["injection_wait_steps"] = injection_wait_steps
                summary["injection"] = injection
                summary["total_budget_steps"] = total_budget
                if recorder is not None:
                    injection_frame = recorder.frames
                    recorder.event_card(
                        obs["agentview_image"],
                        obs.get("robot0_eye_in_hand_image"),
                        title=f"B INJECTION  {case.case_id}  @ step {steps}",
                        lines=[
                            (
                                f"target={case.target} level={case.level}-"
                                f"{case.param or ''} family={case.family}",
                                (255, 230, 120),
                                recorder.font,
                            ),
                            (
                                f"relation before={all(pre_truths)}  "
                                f"after={injection['relation_after']}",
                                (235, 235, 240),
                                recorder.font,
                            ),
                            (
                                "delta_translation="
                                f"{injection['geometry']['delta_translation_m']} m  "
                                "delta_angle="
                                f"{injection['geometry']['delta_angle_rad']} rad",
                                (170, 200, 230),
                                recorder.font_small,
                            ),
                        ],
                        highlight=(255, 150, 110),
                    )
                queue.clear()
                obs = env.regenerate_obs_from_state(env.get_sim_state())
                settle_steps = max(0, int(config.settle_after_injection))
                if settle_steps:
                    immediate = dict(injection)
                    for settle_i in range(settle_steps):
                        obs, _, done, _ = env.step(DUMMY_ACTION)
                        steps += 1
                        if recorder is not None:
                            recorder.step(
                                obs["agentview_image"],
                                obs.get("robot0_eye_in_hand_image"),
                                step=steps,
                                stage=stage_label + " | settle",
                                horizon_index=0,
                                last_decision={
                                    "line": f"post-injection settle {settle_i + 1}/{settle_steps}"
                                },
                                success=False,
                                title=f"B matrix | {case.case_id}",
                                policy_label=f"frozen {config.policy}",
                                controller_label="physics settle",
                            )
                    injection = injector.revalidate(obs.get("robot0_gripper_qpos"))
                    injection["immediate"] = immediate
                    injection["settle_steps"] = settle_steps
                    injection["post_settle"] = True
                    total_budget = steps + repair_window
                    summary["injection"] = injection
                    summary["total_budget_steps"] = total_budget
                    summary["settle_after_injection"] = settle_steps
                    summary["injection_step"] = injection_step
                    goal_truth = injector.goal_truth()
                    revoked_truth = injector.revoked_truth()
                    post_truths.append(list(revoked_truth))
                emit(
                    {
                        "event": "injection",
                        "step": steps,
                        "case_id": case.case_id,
                        "level": case.level,
                        "param": case.param,
                        "target": case.target,
                        "pre_truths": pre_truths,
                        **{
                            key: injection[key]
                            for key in (
                                "kind",
                                "revoked_before",
                                "revoked_after",
                                "goal_before",
                                "goal_after",
                                "relation_after",
                                "goal_preserved",
                                "geometry",
                                "max_velocity",
                                "zero_velocity",
                                "penetration_m",
                                "no_penetration",
                                "object_released",
                                "restorable",
                                "restore_probe",
                                "applied",
                            )
                            if key in injection
                        },
                    }
                )
                continue

            if recorder is not None:
                recorder.step(
                    obs["agentview_image"],
                    obs.get("robot0_eye_in_hand_image"),
                    step=steps,
                    stage=stage_label + (" | revoked" if injected else " | solve"),
                    horizon_index=0,
                    last_decision={
                        "line": (
                            f"injected @ {injection_step}"
                            if injected
                            else "waiting for all_done"
                        )
                    },
                    success=bool(all(goal_truth)),
                    title=f"B matrix | {case.case_id}",
                    policy_label=f"frozen {config.policy}",
                    controller_label="pure policy",
                )

            if injected:
                post_truths.append(list(revoked_truth))
                if all(revoked_truth):
                    recovery_ever = True
                    recovery_streak += 1
                    if restored_at_step is None:
                        restored_at_step = steps
                else:
                    recovery_streak = 0
                center = _target_center(injector)
                if center is not None:
                    eef = np.asarray(obs["robot0_eef_pos"], dtype=np.float64)
                    distance = float(np.linalg.norm(eef - center))
                    if eef_baseline is None:
                        eef_baseline = distance
                    elif notice_latency is None and distance < eef_baseline - 0.01:
                        notice_latency = steps - injection_step
                if (
                    config.stop_on_recovery
                    and case.level != "C0"
                    and recovery_streak >= max(1, int(config.recovery_confirm_steps))
                ):
                    early_stopped = True
                    summary["stop_reason"] = "recovery"
                    summary["termination"] = "recovered"
                    break

            if steps % 5 == 0:
                emit(
                    {
                        "event": "step",
                        "step": steps,
                        "goal": goal_truth,
                        "revoked": revoked_truth,
                        "all_done": all_done,
                        "injected": injected,
                    }
                )

        final_goal = injector.goal_truth()
        final_revoked = injector.revoked_truth()
        final_pending = [final_goal[idx] for idx in pending_goal_indices]
        revoked_ok = all(final_revoked) if revoked_goal_indices else True
        pending_ok = all(final_pending) if final_pending else True
        summary["final_pending_truth"] = final_pending
        summary["atoms_completed"] = sum(1 for value in final_goal if value)
        summary["subtask_progress"] = (
            sum(1 for value in final_goal if value) / len(final_goal) if final_goal else None
        )
        summary["terminal_state"] = (
            "both"
            if revoked_ok and pending_ok
            else "restore_only"
            if revoked_ok
            else "pending_only"
            if pending_ok
            else "neither"
        )
        if config.static_init:
            summary["relation_before"] = bool(all(pre_truths or []))
            summary["relation_after_injection"] = (
                bool(injection["relation_after"]) if injection else None
            )
            summary["relation_final"] = bool(all(final_revoked))
            summary["recovered"] = None
            summary["recovery"] = None
            summary["validity"] = {
                "static_init": True,
                "no_object_penetration": bool(injection and injection["no_penetration"]),
                "zero_velocity_after_intervention": bool(
                    injection and injection["zero_velocity"]
                ),
                "object_released_before_intervention": bool(
                    injection and injection["object_released"]
                ),
            }
            summary["case_valid"] = bool(
                injection
                and injection["no_penetration"]
                and injection["zero_velocity"]
                and injection["object_released"]
            )
            summary["termination"] = "static_success" if all(final_goal) else "static_step_limit"
        elif injected:
            summary["relation_before"] = bool(all(pre_truths or []))
            summary["relation_after_injection"] = (
                bool(injection["relation_after"]) if injection else None
            )
            summary["relation_final"] = bool(all(final_revoked))
            summary["restored_at_step"] = restored_at_step
            summary["recovery_ever"] = recovery_ever
            summary["recovered"] = bool(all(final_revoked))
            summary["recovery"] = (
                None if case.level == "C0" else bool(all(final_revoked))
            )
            summary["notice_latency"] = notice_latency
            summary["validity"] = {
                "completed_relation_true_before_intervention": bool(
                    all(pre_truths or [])
                ),
                "all_revoked_false_after_intervention": bool(
                    injection
                    and all(not value for value in injection["revoked_after"])
                ),
                "no_object_penetration": bool(
                    injection and injection["no_penetration"]
                ),
                "zero_velocity_after_intervention": bool(
                    injection and injection["zero_velocity"]
                ),
                "object_released_before_intervention": bool(
                    injection and injection["object_released"]
                ),
                "restorable": bool(injection and injection["restorable"]),
                "goal_preserved_after_pre": (
                    injection.get("goal_preserved") if injection else None
                ),
            }
            control_ok = (
                case.level == "C0"
                and summary["validity"]["completed_relation_true_before_intervention"]
                and bool(all(final_revoked))
                and bool(all(final_goal))
            )
            perturbed_ok = (
                case.level != "C0"
                and summary["validity"]["completed_relation_true_before_intervention"]
                and summary["validity"]["all_revoked_false_after_intervention"]
                and summary["validity"]["no_object_penetration"]
                and summary["validity"]["zero_velocity_after_intervention"]
                and (
                    case.target != "pre"
                    or bool(summary["validity"]["goal_preserved_after_pre"])
                )
            )
            summary["case_valid"] = bool(control_ok or perturbed_ok)
        else:
            summary["trigger_skipped_reason"] = summary.get(
                "trigger_skipped_reason", "all_done not reached within max_steps"
            )
            summary["relation_before"] = False
            summary["relation_after_injection"] = None
            summary["relation_final"] = (
                bool(all(final_revoked)) if pre_truths else None
            )
            summary["recovered"] = None
            summary["recovery"] = None
            summary["validity"] = {"trigger_reached": False}
            summary["case_valid"] = False
            summary["termination"] = "trigger_not_reached"

        summary.update(
            status="ok",
            steps=steps,
            checks=steps,
            max_steps=config.max_steps,
            total_budget_steps=total_budget,
            repair_budget_steps=(
                None
                if injection_step is None
                else total_budget - injection_step - int(summary.get("settle_after_injection", 0))
            ),
            repair_steps_used=(
                None
                if injection_step is None
                else steps - injection_step - int(summary.get("settle_after_injection", 0))
            ),
            first_all_done_step=first_all_done,
            first_success_step=first_success_step,
            success_ever=success_ever,
            success=bool(all(final_goal)),
            final_goal_truth=final_goal,
            final_revoked_truth=final_revoked,
            termination=summary.get("termination")
            or ("step_limit" if steps >= total_budget else "done"),
            early_stopped=early_stopped,
            stop_reason=summary.get("stop_reason"),
            init_shape=list(init_shape),
            init_row=config.init_row,
            seed=config.seed,
        )
        if recorder is not None:
            recorder.close()
            recorder = None
            summary["video"] = {
                "path": str(episode_dir / "video.mp4"),
                "fps": config.video_fps,
                "frames": None,
                "injection_frame": injection_frame,
                "injection_time_s": (
                    None
                    if injection_frame is None
                    else round(injection_frame / config.video_fps, 3)
                ),
                "timing": "exact",
                "card_seconds": 1.0,
            }
        emit(
            {
                "event": "episode_end",
                "status": "ok",
                "steps": steps,
                "recovered": summary.get("recovered"),
            }
        )
        return summary
    except Exception:  # noqa: BLE001 - one failing case must not kill the run
        summary.update(status="error", error=traceback.format_exc())
        emit({"event": "episode_end", "status": "error", "error": traceback.format_exc()})
        return summary
    finally:
        summary["elapsed_s"] = round(time.time() - started, 2)
        try:
            trace.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if recorder is not None:
                recorder.close()
                summary.setdefault("video", {})["path"] = str(episode_dir / "video.mp4")
                summary["video"]["frames"] = recorder.frames
        except Exception:  # noqa: BLE001
            pass
        try:
            if env is not None:
                env.close()
        except Exception:  # noqa: BLE001
            pass
        write_json(episode_dir / "summary.json", _jsonable(summary))


# ---------------------------------------------------------------------------
# batch runner: resume, aggregate, report
# ---------------------------------------------------------------------------


def _load_existing_episodes(
    path: Path,
    *,
    resume: bool,
    retry_errors: bool,
    retry_invalid: bool,
) -> tuple[list[dict[str, Any]], set[str]]:
    """Read ``episodes.jsonl`` and compute the ids already finished."""

    episodes: list[dict[str, Any]] = []
    done_ids: set[str] = set()
    if not resume or not path.exists():
        return episodes, done_ids
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        episodes.append(record)
        case_id = record.get("case_id")
        if not case_id:
            continue
        completed_ok = record.get("status") == "ok" and (
            not retry_invalid or bool(record.get("case_valid"))
        )
        if completed_ok or (record.get("status") == "error" and not retry_errors):
            done_ids.add(str(case_id))
    return episodes, done_ids


def aggregate_episodes(
    episodes: Sequence[Mapping[str, Any]],
    output: str | Path,
    defaults: Mapping[str, Any],
) -> dict[str, Any]:
    """Write ``run-summary.json`` + ``report.md`` and return the summary.

    Denominator contract (``docs/SPEC.md`` §6.2): ``Recovery`` excludes ``C0``
    controls and invalid injections; ``C0`` is reported separately as
    ``control_rate``.
    """

    output = Path(output)
    ok = [episode for episode in episodes if episode.get("status") == "ok"]
    triggered = [episode for episode in ok if episode.get("trigger_reached")]
    valid = [episode for episode in ok if episode.get("case_valid")]
    recoverable = [episode for episode in valid if episode.get("level") != "C0"]
    recovered = [episode for episode in recoverable if episode.get("recovered")]
    controls = [episode for episode in valid if episode.get("level") == "C0"]
    control_ok = [episode for episode in controls if episode.get("success")]
    summary = {
        "schema_version": SCHEMA_VERSION,
        "cases": len(episodes),
        "ok": len(ok),
        "errors": len(episodes) - len(ok),
        "triggered": len(triggered),
        "valid": len(valid),
        "recoverable_valid": len(recoverable),
        "recovered": len(recovered),
        "early_stopped": sum(1 for episode in recoverable if episode.get("early_stopped")),
        "recovery_rate": (
            None if not recoverable else round(len(recovered) / len(recoverable), 4)
        ),
        "controls": len(controls),
        "control_ok": len(control_ok),
        "control_rate": (
            None if not controls else round(len(control_ok) / len(controls), 4)
        ),
        "defaults": dict(defaults),
    }
    write_json(output / "run-summary.json", summary)
    lines = [
        "# B matrix rollback run",
        "",
        f"- output: `{output}`",
        f"- cases: {summary['cases']} (ok {summary['ok']}, errors {summary['errors']})",
        f"- triggered: {summary['triggered']}",
        f"- valid: {summary['valid']}",
        f"- recovery: {summary['recovered']}/{summary['recoverable_valid']} "
        f"= {summary['recovery_rate']}",
        f"- early stopped: {summary['early_stopped']}",
        f"- C0 controls: {summary['control_ok']}/{summary['controls']} "
        f"= {summary['control_rate']}",
        "",
        "| case | suite | level | target | trigger | valid | recovered | steps | video |",
        "|---|---|---|---|---:|---|---:|---:|---|",
    ]
    for episode in episodes:
        video = episode.get("video") or {}
        lines.append(
            f"| {episode.get('case_id')} | {episode.get('suite')} | "
            f"{episode.get('level')}-{episode.get('param') or ''} | "
            f"{episode.get('target')} | {episode.get('trigger_reached')} | "
            f"{episode.get('case_valid')} | {episode.get('recovered')} | "
            f"{episode.get('steps')} | {'yes' if video.get('path') else '-'} |"
        )
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def run_matrix(
    *,
    matrix: BMatrix,
    cases: Sequence[BCase],
    output: str | Path,
    model: str = "none",
    checkpoint: str | None = None,
    config: RunConfig | None = None,
    config_name: str = "pi05_libero",
    unnorm_key: str | None = None,
    workspace: str | None = None,
    resume: bool = True,
    retry_errors: bool = False,
    retry_invalid: bool = False,
    script: str = "scripts/run_b_matrix.py",
) -> dict[str, Any]:
    """Run a batch of B cases and write the run-level artifacts.

    ``model="none"`` runs the environment with zero actions (no model loaded at
    all); any other value loads exactly one adapter from
    :mod:`libero_rollback.policies`.  The run is resumable and shardable; see
    :func:`select_cases`.
    """

    from .policies import load_policy, normalize_policy_name
    from .runtime.env import bootstrap_environment, resolve_libero_home

    policy_name = normalize_policy_name(model)
    config = replace(config or RunConfig(), policy=policy_name)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    libero_home = resolve_libero_home(config.libero_home)
    config = replace(config, libero_home=str(libero_home))
    checkpoint_path = _resolve_checkpoint(policy_name, checkpoint)
    if checkpoint_path is not None and not Path(checkpoint_path).exists():
        raise FileNotFoundError(f"{policy_name} checkpoint not found: {checkpoint_path}")

    defaults = {
        **config.as_dict(),
        "checkpoint": checkpoint_path,
        "config_name": config_name,
        "matrix": str(matrix.source),
        "script": script,
    }
    write_json(
        output / "run-manifest.json",
        {
            "schema_version": SCHEMA_VERSION,
            "defaults": defaults,
            "argv": list(sys.argv[1:]),
            "environment": _environment_summary(),
        },
    )
    write_json(output / "matrix.json", matrix.summary())
    runtime = bootstrap_environment(libero_home, output / "libero_config")
    print(f"[libero] root={runtime['libero_root']} config={runtime['libero_config_path']}")

    policy = load_policy(
        policy_name,
        checkpoint=checkpoint_path,
        config_name=config_name,
        unnorm_key=unnorm_key,
        suites=sorted({case.suite for case in cases}),
        workspace=workspace,
    )
    if policy is not None:
        metadata = dict(policy.metadata)
        print(
            f"[policy] {policy_name} loaded in {metadata.get('load_seconds')} s "
            f"({metadata.get('device')})",
            flush=True,
        )

    episodes_path = output / "episodes.jsonl"
    episodes, done_ids = _load_existing_episodes(
        episodes_path,
        resume=resume,
        retry_errors=retry_errors,
        retry_invalid=retry_invalid,
    )
    stream = episodes_path.open("a", encoding="utf-8")
    total = len(cases)
    run_started = time.time()
    completed = 0
    aggregate: dict[str, Any] = {}
    try:
        for index, case in enumerate(cases, 1):
            case_dir = episode_directory(output, case, config.seed)
            if (
                resume
                and case.case_id in done_ids
                and (case_dir / "summary.json").exists()
            ):
                print(f"[{index}/{total}] {case.case_id} ... skipped (resume)", flush=True)
                continue
            print(
                f"[{index}/{total}] {case.case_id} "
                f"({case.suite} t{case.task_idx} {case.target} "
                f"{case.level}{case.param or ''}) ...",
                flush=True,
            )
            started = time.time()
            summary = run_case(
                case=case, config=config, policy=policy, output=output
            )
            summary["elapsed_s"] = round(time.time() - started, 2)
            video = summary.get("video")
            if video and video.get("path"):
                frames = _count_video_frames(Path(video["path"]))
                if frames:
                    video["frames"] = frames
                    video["duration_s"] = round(frames / float(config.video_fps), 3)
            episodes.append(summary)
            stream.write(json.dumps(_jsonable(summary), ensure_ascii=False) + "\n")
            stream.flush()
            completed += 1
            elapsed = time.time() - run_started
            rate = elapsed / max(1, completed)
            eta = rate * max(0, total - index)
            print(
                f"    status={summary.get('status')} "
                f"trigger={summary.get('trigger_reached')} "
                f"valid={summary.get('case_valid')} "
                f"recovered={summary.get('recovered')} "
                f"steps={summary.get('steps')} "
                f"elapsed={summary.get('elapsed_s')}s eta={eta / 3600:.2f}h",
                flush=True,
            )
    finally:
        stream.close()
        aggregate = aggregate_episodes(episodes, output, defaults)
    print(RULE)
    print(f"done: output={output}")
    print(RULE)
    return aggregate
