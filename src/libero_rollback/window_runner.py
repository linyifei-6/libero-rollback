"""In-execution (C/D) rollback runner: GT window trigger, inject, repair.

One case is one episode (README §5.1, docs/c-matrix.md §3, docs/d-matrix.md §5):

1. start the native (C) or composed (D) task from its ``.pruned_init`` and
   settle — this is the episode-initial state the ``L0`` level restores to;
2. run the frozen policy while monitoring ground-truth subgoal progress:
   ``s1`` (the revoked predecessor relation) completion + release/settle,
   ``s2`` (the pending successor) start, lift and goal-region XY distance
   (pose ``s2``), or its articulated joint progress (joint ``s2``);
3. fire the case's ``early`` / ``mid`` / ``later`` window with
   :class:`libero_rollback.runtime.triggers.WindowTrigger` (pose ``s2``) or
   :class:`JointProgressTrigger` (joint ``s2``);
4. inject the matrix perturbation through the *same* ``BInjector`` the B
   runner uses (no perturbation semantics are duplicated here);
5. append a repair window after the injection step (``--repair-window``,
   default 600; it is never squeezed by the pre-trigger budget) and record
   whether the revoked ``s1`` relation comes back while ``s2`` stays pending.

``s2`` selection
----------------
``s1`` is the native goal atom matched by the case's revoked predicate
(``BInjector.goal_atom_index``).  ``s2`` is the next native goal atom in BDDL
order that is not ``s1``.  This follows the frozen matrices: C t000 revokes
``(Turnon flat_stove_1)`` and leaves ``(On moka_pot_1 ...)`` pending; C t33
revokes ``(In akita_black_bowl_1 ...)`` and leaves ``(Close white_cabinet_1
_bottom_region)`` pending; D ``_ba`` rows revoke the first atom of the reversed
grammar and leave the other one pending.

Joint ``s2``
------------
``Open`` / ``Close`` / ``Turnon`` successors have no lift/XY geometry, so they
use :class:`JointProgressTrigger`: ``mid`` fires once the actuated joint has
travelled ``joint_mid_fraction`` (default 0.10) of its remaining range away
from the initial pose, ``later`` once it reaches ``joint_later_fraction``
(default 0.60) after ``mid``.  Lift/XY thresholds are never applied to a joint
``s2``; when the articulated joint cannot be resolved the runner raises
:class:`UnsupportedWindowError` instead of silently mis-triggering.

Artifacts per episode: ``summary.json``, ``trace.jsonl`` and (optional)
``video.mp4`` under ``<output>/<suite>/<case_id>/seed-<seed>/``.  A run is
resumable through ``episodes.jsonl``.

Module boundary: the top level imports only the stdlib plus in-repo,
simulation-free modules (``runner`` / ``window_matrix`` / ``triggers``), so
``--dry-run`` works without numpy / MuJoCo / LIBERO / torch.
"""

from __future__ import annotations

import json
import math
import sys
import time
import traceback
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .runner import (
    _environment_summary,
    _jsonable,
    _load_existing_episodes,
    _predict_chunk,
    _reset_policy,
    _resolve_checkpoint,
    episode_directory,
    write_json,
)
from .runtime.triggers import TriggerConfig, WindowObservation, WindowTrigger
from .window_matrix import (
    WINDOW_EVENTS,
    WINDOWS,
    WindowCase,
    WindowMatrix,
    resolve_compose_root,
    select_window_cases,
)

SCHEMA_VERSION = 2
RULE = "-" * 78
DUMMY_ACTION = [0.0] * 6 + [-1.0]

#: MuJoCo joint type constants used by the joint-``s2`` progress path.
_JNT_FREE = 0
_JNT_SLIDE = 2
_JNT_HINGE = 3

#: Published gate tolerance for ``s2_undisturbed_by_injection``.
_S2_POSITION_TOLERANCE_M = 0.005
_S2_JOINT_TOLERANCE_RAD = 1e-3

#: Reviewed window profiles for the repaired tasks.  The matrix carries the
#: same cases in every run; these values are the accepted trigger criteria.
TASK_WINDOW_PROFILES: dict[int, dict[str, float]] = {
    33: {"joint_mid_fraction": 0.02, "joint_later_fraction": 0.20},
    78: {"joint_mid_fraction": 0.05, "joint_later_fraction": 0.65},
    133: {"lift_min_m": 0.005},
}


def apply_task_profile(case: WindowCase, config: WindowRunConfig) -> WindowRunConfig:
    """Apply the reviewed per-task thresholds without changing the matrix."""

    values = TASK_WINDOW_PROFILES.get(int(case.task_idx or -1))
    return replace(config, **values) if values else config


CHECKPOINT_ENV = {
    "pi05": "PI05_CHECKPOINT",
    "smolvla": "SMOLVLA_CHECKPOINT",
    "openvla_oft": "OPENVLA_OFT_CHECKPOINT",
}


class UnsupportedWindowError(RuntimeError):
    """The case's ``s2`` cannot be monitored with the documented window rules."""


# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowRunConfig:
    """Protocol parameters of one C/D run (README §6.2, docs/trigger-design.md)."""

    init_row: int = 0
    seed: int = 0
    #: 0 = use the matrix row's ``max_steps`` (C 800 / D 600).
    max_steps: int = 0
    replan: int = 10
    camera: int = 256
    settle_steps: int = 10
    #: Appended after the injection step; the CLI default is the 600-step floor.
    repair_window: int = 600
    #: GT window thresholds (defaults from the predecessor task profiles).
    lift_min_m: float = 0.03
    preplacement_max_xy_m: float = 0.20
    require_settled_early: bool = True
    require_s2_started_early: bool = False
    settle_speed_m_s: float = 0.01
    settled_confirm_steps: int = 3
    s2_start_epsilon_m: float = 0.005
    #: Joint-``s2`` progress fractions (documented, never lift/XY).
    joint_mid_fraction: float = 0.10
    joint_later_fraction: float = 0.60
    joint_move_epsilon_rad: float = 0.01
    video: bool = True
    video_fps: int = 20
    policy: str = "none"
    libero_home: str | None = None
    libero_python: str | None = None
    compose_root: str | None = None

    def __post_init__(self) -> None:
        if self.max_steps < 0:
            raise ValueError("max_steps must be >= 0")
        if self.repair_window < 0:
            raise ValueError("repair_window must be >= 0")
        if self.lift_min_m <= 0 or self.preplacement_max_xy_m <= 0:
            raise ValueError("window thresholds must be positive")
        if not 0.0 <= self.joint_mid_fraction < self.joint_later_fraction <= 1.0:
            raise ValueError(
                "joint fractions must satisfy 0 <= mid < later <= 1, got "
                f"{self.joint_mid_fraction}/{self.joint_later_fraction}"
            )

    def trigger_config(self) -> TriggerConfig:
        return TriggerConfig(
            lift_min_m=float(self.lift_min_m),
            preplacement_max_xy_m=float(self.preplacement_max_xy_m),
            require_settled_early=bool(self.require_settled_early),
            require_s2_started_early=bool(self.require_s2_started_early),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "init_row": self.init_row,
            "seed": self.seed,
            "max_steps": self.max_steps,
            "replan": self.replan,
            "camera": self.camera,
            "settle_steps": self.settle_steps,
            "repair_window": self.repair_window,
            "lift_min_m": self.lift_min_m,
            "preplacement_max_xy_m": self.preplacement_max_xy_m,
            "require_settled_early": self.require_settled_early,
            "require_s2_started_early": self.require_s2_started_early,
            "settle_speed_m_s": self.settle_speed_m_s,
            "settled_confirm_steps": self.settled_confirm_steps,
            "s2_start_epsilon_m": self.s2_start_epsilon_m,
            "joint_mid_fraction": self.joint_mid_fraction,
            "joint_later_fraction": self.joint_later_fraction,
            "joint_move_epsilon_rad": self.joint_move_epsilon_rad,
            "video": self.video,
            "video_fps": self.video_fps,
            "policy": self.policy,
            "libero_home": self.libero_home,
            "libero_python": self.libero_python,
            "compose_root": self.compose_root,
        }


def _budget(case: WindowCase, config: WindowRunConfig) -> tuple[int, int]:
    """Return ``(pre_trigger_budget, repair_window)`` for one case."""

    budget = int(config.max_steps) if int(config.max_steps) > 0 else int(case.max_steps)
    if budget <= 0:
        raise ValueError(f"{case.case_id}: max_steps must be positive")
    repair = max(int(case.repair_window or 0), int(config.repair_window))
    return budget, repair


# ---------------------------------------------------------------------------
# pure progress helpers (unit-testable, no numpy / MuJoCo)
# ---------------------------------------------------------------------------


def xy_distance(left: Sequence[float], right: Sequence[float]) -> float:
    """XY-plane distance between two world positions."""

    return math.hypot(float(left[0]) - float(right[0]), float(left[1]) - float(right[1]))


def lift_from_initial(current: Sequence[float], initial: Sequence[float]) -> float:
    """World-Z displacement of the ``s2`` object relative to its initial pose."""

    return float(current[2]) - float(initial[2])


def joint_progress(
    q: float, q0: float, low: float, high: float
) -> tuple[float, float]:
    """Return ``(progress, displacement)`` of one articulated joint.

    ``progress`` is the fraction of the remaining joint range travelled away
    from the episode-initial value (clamped to ``[0, 1]``); ``displacement`` is
    the signed value change.  This is the documented joint-``s2`` analogue of
    the pose ``lift`` metric — lift/XY are never used for joints.
    """

    displacement = float(q) - float(q0)
    if abs(displacement) <= 0.0:
        return 0.0, displacement
    span = (float(high) - float(q0)) if displacement > 0 else (float(q0) - float(low))
    if span <= 1e-9:
        return 0.0, displacement
    return max(0.0, min(1.0, abs(displacement) / span)), displacement


# ---------------------------------------------------------------------------
# joint-s2 trigger
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JointTriggerConfig:
    mid_fraction: float = 0.10
    later_fraction: float = 0.60
    require_settled_early: bool = True
    require_s2_started_early: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.mid_fraction < self.later_fraction <= 1.0:
            raise ValueError(
                "joint fractions must satisfy 0 <= mid < later <= 1, got "
                f"{self.mid_fraction}/{self.later_fraction}"
            )


@dataclass(frozen=True)
class JointProgressObservation:
    step: int
    s1_done: bool
    s1_settled: bool
    s2_started: bool
    s2_joint_progress: float | None
    s2_joint_displacement: float | None
    s2_joint_name: str | None = None


@dataclass
class JointProgressTrigger:
    """GT window state machine for an articulated ``s2``.

    ``early`` uses the same ``s1_done``/``s1_settled`` evidence as
    :class:`WindowTrigger`; ``mid``/``later`` use joint progress fractions.
    """

    config: JointTriggerConfig = field(default_factory=JointTriggerConfig)
    target: str = "mid"
    _fired: set[str] = field(default_factory=set, init=False)
    _mid_seen: bool = field(default=False, init=False)
    _events: list[tuple[str, int]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if self.target not in WINDOWS:
            raise ValueError(f"unknown window {self.target!r}; expected one of {WINDOWS}")

    @property
    def events(self) -> list[tuple[str, int]]:
        return list(self._events)

    @property
    def fired(self) -> bool:
        return self.target in self._fired

    def observe(self, observation: JointProgressObservation) -> bool:
        progress = observation.s2_joint_progress
        if progress is not None and progress >= self.config.mid_fraction:
            self._mid_seen = True
        fired_before = self.target in self._fired
        candidates = {
            "early": observation.s1_done
            and (observation.s1_settled or not self.config.require_settled_early)
            and (observation.s2_started or not self.config.require_s2_started_early),
            "mid": observation.s1_done
            and progress is not None
            and progress >= self.config.mid_fraction,
            "later": observation.s1_done
            and self._mid_seen
            and progress is not None
            and progress >= self.config.later_fraction,
        }
        if not self._fired and candidates[self.target]:
            self._fired.add(self.target)
            self._events.append((self.target, observation.step))
        return self.target in self._fired and not fired_before


# ---------------------------------------------------------------------------
# s2 resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class S2Target:
    index: int
    atom: tuple[str, ...]
    kind: str  # "pose" | "joint"
    predicate: str
    object_name: str | None = None
    region_name: str | None = None
    joint_name: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "goal_index": self.index,
            "atom": list(self.atom),
            "kind": self.kind,
            "predicate": self.predicate,
            "object": self.object_name,
            "region": self.region_name,
            "joint": self.joint_name,
        }


def resolve_s2(
    case: WindowCase, injector, goal_atoms: Sequence[Sequence[Any]]
) -> S2Target:
    """Resolve the pending successor atom (raise when C/D window rules cannot apply)."""

    indices = sorted(
        {
            int(index)
            for index in getattr(injector, "goal_atom_index", ())
            if int(index) >= 0
        }
    )
    if len(indices) != 1:
        raise UnsupportedWindowError(
            f"{case.case_id}: in-execution rollback needs exactly one revoked goal "
            f"atom; BInjector matched {indices}"
        )
    s1_index = indices[0]
    candidates = [index for index in range(len(goal_atoms)) if index != s1_index]
    if not candidates:
        raise UnsupportedWindowError(
            f"{case.case_id}: no pending s2 goal atom (task has "
            f"{len(goal_atoms)} goal atom(s))"
        )
    s2_index = candidates[0]
    atom = tuple(str(token) for token in goal_atoms[s2_index])
    if len(atom) < 2:
        raise UnsupportedWindowError(
            f"{case.case_id}: malformed s2 goal atom {atom!r}"
        )
    predicate = atom[0].lower()
    if predicate in {"in", "on"}:
        if len(atom) < 3:
            raise UnsupportedWindowError(
                f"{case.case_id}: pose s2 atom has no goal region: {atom!r}"
            )
        return S2Target(
            index=s2_index,
            atom=atom,
            kind="pose",
            predicate=predicate,
            object_name=atom[1],
            region_name=atom[2],
        )
    if predicate in {"open", "close", "turnon"}:
        return S2Target(
            index=s2_index,
            atom=atom,
            kind="joint",
            predicate=predicate,
            joint_name=atom[1],
        )
    raise UnsupportedWindowError(
        f"{case.case_id}: unsupported s2 predicate {predicate!r} in {atom!r}; "
        "expected In/On (pose) or Open/Close/Turnon (joint)"
    )


def dynamic_s1_indices(goal_atoms: Sequence[Sequence[Any]]) -> list[int]:
    """Goal atom indices whose completion order may vary.

    A task such as "put both moka pots on the stove" has two interchangeable
    pose atoms (same predicate, same goal region, different object).  The
    first one completed is s1; the other is s2.  Multiple such atoms are the
    signal for runtime target selection instead of the matrix's fixed target.
    """

    pose_indices: list[int] = []
    objects: set[str] = set()
    for index, atom in enumerate(goal_atoms):
        if len(atom) < 3:
            continue
        predicate = str(atom[0]).lower()
        if predicate not in {"in", "on"}:
            continue
        pose_indices.append(index)
        objects.add(str(atom[1]))
    # Any task with two distinct placed objects has a runtime order choice:
    # same-region pairs (two pots on one stove) and different-region pairs
    # (two mugs on two plates) both qualify.
    return sorted(pose_indices) if len(objects) >= 2 else []


def _make_trigger(
    case: WindowCase, config: WindowRunConfig, s2: S2Target
) -> WindowTrigger | JointProgressTrigger:
    """Build the window trigger that matches the successor's state kind."""

    if s2.kind == "joint":
        return JointProgressTrigger(
            config=JointTriggerConfig(
                mid_fraction=float(config.joint_mid_fraction),
                later_fraction=float(config.joint_later_fraction),
                require_settled_early=bool(config.require_settled_early),
                require_s2_started_early=bool(config.require_s2_started_early),
            ),
            target=case.window,
        )
    return WindowTrigger(config=config.trigger_config(), target=case.window)


def resolved_thresholds(
    case: WindowCase, config: WindowRunConfig, s2: S2Target
) -> dict[str, Any]:
    """The exact thresholds used for this episode, recorded in ``summary.json``."""

    payload: dict[str, Any] = {
        "window": case.window,
        "event": WINDOW_EVENTS[case.window],
        "legacy_trigger_criterion": case.trigger_criterion,
        "s2_kind": s2.kind,
        "s2_predicate": s2.predicate,
        "require_settled_early": bool(config.require_settled_early),
        "require_s2_started_early": bool(config.require_s2_started_early),
        "settle_speed_m_s": float(config.settle_speed_m_s),
        "settled_confirm_steps": int(config.settled_confirm_steps),
    }
    if s2.kind == "pose":
        payload.update(
            {
                "lift_min_m": float(config.lift_min_m),
                "preplacement_max_xy_m": float(config.preplacement_max_xy_m),
                "s2_start_epsilon_m": float(config.s2_start_epsilon_m),
            }
        )
    else:
        payload.update(
            {
                "joint_mid_fraction": float(config.joint_mid_fraction),
                "joint_later_fraction": float(config.joint_later_fraction),
                "joint_move_epsilon_rad": float(config.joint_move_epsilon_rad),
            }
        )
    return payload


# ---------------------------------------------------------------------------
# MuJoCo geometry helpers (numpy-free, duck-typed)
# ---------------------------------------------------------------------------


def _model_body_names(model) -> list[str]:
    return [str(name) for name in model.body_names]


def _has_free_joint(model, body_id: int) -> bool:
    start = int(model.body_jntadr[body_id])
    count = int(model.body_jntnum[body_id])
    return any(int(model.jnt_type[joint]) == _JNT_FREE for joint in range(start, start + count))


def _find_body_id(model, name: str, *, prefer_free: bool = False) -> int | None:
    """Resolve a BDDL role name to a MuJoCo body id (same intent as the injector)."""

    names = _model_body_names(model)
    lowered = {body_name.lower(): index for index, body_name in enumerate(names)}
    indices: list[int] = []
    for candidate in (name, f"{name}_main", f"{name}_region"):
        index = lowered.get(candidate.lower())
        if index is not None and index not in indices:
            indices.append(index)
    prefix = name.lower() + "_"
    for index, body_name in enumerate(names):
        lowered_name = body_name.lower()
        if index not in indices and (
            lowered_name == name.lower() or lowered_name.startswith(prefix)
        ):
            indices.append(index)
    if not indices:
        return None
    if prefer_free:
        for index in indices:
            if _has_free_joint(model, index):
                return index
    return indices[0]


def _find_site_id(model, name: str) -> int | None:
    names = [str(site_name) for site_name in model.site_names]
    for candidate in (name, f"{name}_site", f"{name}_region"):
        if candidate in names:
            return names.index(candidate)
    return None


def _articulated_joints_in_subtree(model, root_id: int) -> list[int]:
    bodies: set[int] = set()
    for body_id in range(int(model.nbody)):
        current = body_id
        for _ in range(64):
            if current == root_id:
                bodies.add(body_id)
                break
            parent = int(model.body_parentid[current])
            if parent == current or parent <= 0:
                break
            current = parent
    joints: list[int] = []
    for body_id in sorted(bodies):
        start = int(model.body_jntadr[body_id])
        count = int(model.body_jntnum[body_id])
        for joint_id in range(start, start + count):
            if int(model.jnt_type[joint_id]) in (_JNT_SLIDE, _JNT_HINGE):
                joints.append(joint_id)
    return joints


def _resolve_joint_ids(model, token: str) -> list[int]:
    parts = str(token).split("_")
    candidates: list[str] = []
    for cut in range(len(parts), 1, -1):
        candidate = "_".join(parts[:cut])
        if candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates:
        body_id = _find_body_id(model, candidate)
        if body_id is None:
            continue
        joints = _articulated_joints_in_subtree(model, body_id)
        if joints:
            return joints
    raise UnsupportedWindowError(
        f"cannot resolve an articulated joint for s2 {token!r}; tried {candidates}"
    )


def _joint_qpos(sim, joint_id: int) -> float:
    address = int(sim.model.jnt_qposadr[joint_id])
    return float(sim.data.qpos[address])


def _joint_range(model, joint_id: int) -> tuple[float, float] | None:
    if not bool(model.jnt_limited[joint_id]):
        return None
    low, high = (float(value) for value in model.jnt_range[joint_id])
    if high <= low:
        return None
    return low, high


def _body_position(sim, body_id: int) -> list[float]:
    value = sim.data.body_xpos[body_id]
    return [float(value[0]), float(value[1]), float(value[2])]


def _target_speed(injector) -> float:
    """Max linear/angular speed of the revoked target(s) (same gate as B)."""

    sim = injector.sim
    model = injector.model
    maximum = 0.0
    for target in injector.targets.values():
        if target.kind == "free" and target.free_joint is not None:
            dof = int(model.jnt_dofadr[target.free_joint])
            for value in sim.data.qvel[dof : dof + 6]:
                maximum = max(maximum, abs(float(value)))
        else:
            for joint_id in target.joint_ids:
                dof = int(model.jnt_dofadr[joint_id])
                if dof >= 0:
                    maximum = max(maximum, abs(float(sim.data.qvel[dof])))
    return maximum


def _object_released(gripper_qpos: Sequence[float] | None) -> bool:
    if gripper_qpos is None:
        return True
    values = [float(value) for value in gripper_qpos]
    return bool(
        len(values) >= 2 and (max(values) - min(values)) > 0.01
    )


def s2_undisturbed(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> tuple[bool, float | None]:
    """Check the injection did not move the pending ``s2`` object/joint."""

    if before.get("kind") == "pose" and after.get("kind") == "pose":
        distance = math.dist(before["position"], after["position"])
        return bool(distance <= _S2_POSITION_TOLERANCE_M), distance
    if before.get("kind") == "joint" and after.get("kind") == "joint":
        before_joint = before.get("joint")
        after_joint = after.get("joint")
        if before_joint is not None and after_joint is not None and before_joint != after_joint:
            # A different joint was selected before/after: values are not comparable.
            return False, None
        delta = abs(float(after["q"]) - float(before["q"]))
        return bool(delta <= _S2_JOINT_TOLERANCE_RAD), delta
    return False, None


# ---------------------------------------------------------------------------
# per-step monitor
# ---------------------------------------------------------------------------


class WindowMonitor:
    """Turn one environment step into a GT window observation.

    Pose ``s2`` produces :class:`WindowObservation`; joint ``s2`` produces
    :class:`JointProgressObservation`.  ``observe`` also returns the resolved
    metrics so the runner can record them in the trace and summary.
    """

    def __init__(self, injector, s2: S2Target, config: WindowRunConfig) -> None:
        self.injector = injector
        self.s2 = s2
        self.config = config
        self.model = injector.model
        self.sim = injector.sim
        self.first_s1_done_step: int | None = None
        self.first_s2_started_step: int | None = None
        self._settled_streak = 0
        self.s2_object_movable: bool | None = None
        if s2.kind == "pose":
            self._object_body = _find_body_id(
                self.model, str(s2.object_name), prefer_free=True
            )
            if self._object_body is None:
                raise UnsupportedWindowError(
                    f"s2 object {s2.object_name!r} not found in the MuJoCo model"
                )
            self._object_initial = _body_position(self.sim, self._object_body)
            self._region_body = _find_body_id(self.model, str(s2.region_name))
            self._region_site = _find_site_id(self.model, str(s2.region_name))
            if self._region_body is None and self._region_site is None:
                raise UnsupportedWindowError(
                    f"s2 goal region {s2.region_name!r} not found in the MuJoCo model"
                )
            self.s2_object_movable = _has_free_joint(self.model, self._object_body)
        else:
            self._joint_ids = _resolve_joint_ids(self.model, str(s2.joint_name))
            self._initial_qpos = {
                joint_id: _joint_qpos(self.sim, joint_id)
                for joint_id in self._joint_ids
            }
            self._ranges = {
                joint_id: bounds
                for joint_id in self._joint_ids
                if (bounds := _joint_range(self.model, joint_id)) is not None
            }
            if not self._ranges:
                raise UnsupportedWindowError(
                    f"joint s2 {s2.joint_name!r} has no limited hinge/slide joint "
                    "to measure progress on"
                )
            self._active_joint = self._select_joint()

    # -- geometry --------------------------------------------------------

    def _region_position(self) -> list[float]:
        if self._region_body is not None:
            return _body_position(self.sim, self._region_body)
        assert self._region_site is not None
        value = self.sim.data.site_xpos[self._region_site]
        return [float(value[0]), float(value[1]), float(value[2])]

    def _select_joint(self) -> int:
        tokens = {
            part
            for part in str(self.s2.joint_name).lower().split("_")
            if part and part not in {"region", "main", "side"}
        }
        best, best_score = None, -1.0
        for joint_id in self._ranges:
            delta = abs(
                _joint_qpos(self.sim, joint_id) - self._initial_qpos[joint_id]
            )
            joint_name = str(self.model.joint_names[joint_id]).lower()
            overlap = sum(1 for token in tokens if token in joint_name)
            score = delta + 1e-3 * overlap
            if score > best_score:
                best, best_score = joint_id, score
        assert best is not None
        return best

    # -- observation -----------------------------------------------------

    def observe(
        self, step: int, gripper_qpos: Sequence[float] | None
    ) -> tuple[WindowObservation | JointProgressObservation, dict[str, Any]]:
        revoked = [bool(value) for value in self.injector.revoked_truth()]
        s1_done = bool(revoked) and all(revoked)
        if s1_done and self.first_s1_done_step is None:
            self.first_s1_done_step = step
        released = _object_released(gripper_qpos)
        speed = _target_speed(self.injector)
        settled_now = bool(
            speed <= float(self.config.settle_speed_m_s) and released
        )
        self._settled_streak = self._settled_streak + 1 if settled_now else 0
        s1_settled = bool(
            s1_done
            and self._settled_streak >= max(1, int(self.config.settled_confirm_steps))
        )
        metrics: dict[str, Any] = {
            "step": step,
            "s1_done": s1_done,
            "s1_settled": s1_settled,
            "gripper_released": released,
            "target_speed": round(float(speed), 6),
            "settled_streak": self._settled_streak,
            "s2_kind": self.s2.kind,
            "s2_object_movable": self.s2_object_movable,
        }
        if self.s2.kind == "pose":
            position = _body_position(self.sim, self._object_body)
            lift = lift_from_initial(position, self._object_initial)
            goal_xy = xy_distance(position, self._region_position())
            displacement = xy_distance(position, self._object_initial)
            started = bool(
                self.s2_object_movable
                and (
                    abs(lift) > float(self.config.s2_start_epsilon_m)
                    or displacement > float(self.config.s2_start_epsilon_m)
                )
            )
            metrics.update(
                {
                    "s2_started": started,
                    "s2_lift_m": round(lift, 6),
                    "s2_to_goal_xy_m": round(goal_xy, 6),
                    "s2_position": [round(value, 6) for value in position],
                }
            )
            if started and self.first_s2_started_step is None:
                self.first_s2_started_step = step
            observation = WindowObservation(
                step=step,
                s1_done=s1_done,
                s1_settled=s1_settled,
                s2_started=started,
                # Successor windows only open once s1 (the revoked
                # relation) is GT-true; never inject against a false s1.
                s2_lift_m=lift if s1_done else None,
                s2_to_goal_xy_m=goal_xy if s1_done else None,
            )
            return observation, metrics

        joint_id = self._select_joint()
        self._active_joint = joint_id
        q = _joint_qpos(self.sim, joint_id)
        low, high = self._ranges[joint_id]
        progress, displacement = joint_progress(
            q, self._initial_qpos[joint_id], low, high
        )
        started = abs(displacement) > float(self.config.joint_move_epsilon_rad)
        metrics.update(
            {
                "s2_started": started,
                "s2_joint_name": str(self.model.joint_names[joint_id]),
                "s2_joint_q": round(q, 6),
                "s2_joint_progress": round(progress, 6),
                "s2_joint_displacement": round(displacement, 6),
            }
        )
        if started and self.first_s2_started_step is None:
            self.first_s2_started_step = step
        observation = JointProgressObservation(
            step=step,
            s1_done=s1_done,
            s1_settled=s1_settled,
            s2_started=started,
            s2_joint_progress=progress,
            s2_joint_displacement=displacement,
            s2_joint_name=str(self.model.joint_names[joint_id]),
        )
        return observation, metrics

    # -- injection snapshot ---------------------------------------------

    def progress_snapshot(self) -> dict[str, Any]:
        """Pose/joint snapshot used for the ``s2_undisturbed`` gate."""

        snapshot: dict[str, Any] = {"kind": self.s2.kind, "atom": list(self.s2.atom)}
        try:
            snapshot["predicate_true"] = bool(
                self.injector.problem._eval_predicate(self.s2.atom)
            )
        except Exception:  # noqa: BLE001 - snapshot is diagnostic only
            snapshot["predicate_true"] = None
        if self.s2.kind == "pose":
            position = _body_position(self.sim, self._object_body)
            snapshot.update(
                {
                    "object": self.s2.object_name,
                    "position": [round(value, 6) for value in position],
                    "lift_m": round(
                        lift_from_initial(position, self._object_initial), 6
                    ),
                    "to_goal_xy_m": round(
                        xy_distance(position, self._region_position()), 6
                    ),
                }
            )
            return snapshot
        joint_id = self._active_joint
        q = _joint_qpos(self.sim, joint_id)
        low, high = self._ranges[joint_id]
        progress, displacement = joint_progress(
            q, self._initial_qpos[joint_id], low, high
        )
        snapshot.update(
            {
                "joint": str(self.model.joint_names[joint_id]),
                "q": round(q, 6),
                "progress": round(progress, 6),
                "displacement": round(displacement, 6),
            }
        )
        return snapshot


# ---------------------------------------------------------------------------
# one episode
# ---------------------------------------------------------------------------


def run_window_case(
    *, case: WindowCase, config: WindowRunConfig, policy, output: str | Path
) -> dict[str, Any]:
    """Run one C/D case; always writes ``summary.json`` (also on failure)."""

    config = apply_task_profile(case, config)
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

    budget, repair_window = _budget(case, config)
    total_budget = budget
    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "running",
        "is_control": case.is_control,
        "case_id": case.case_id,
        "task_id": case.task_id or case.case_id,
        "test_suite": case.test_suite,
        "dimension": case.dimension,
        "arm": case.arm,
        "sub": case.sub,
        "suite": case.suite,
        "task_idx": case.task_idx,
        "struct_id": case.struct_id,
        "source_suite": case.source_suite,
        "order": case.order,
        "bddl_name": case.bddl_name,
        "asset_source": case.asset_source,
        "instruction": case.instruction,
        "language": case.instruction,
        "window": case.window,
        "trigger_criterion": case.trigger_criterion,
        "trigger_event": WINDOW_EVENTS[case.window],
        "target": case.target,
        "level": case.level,
        "param": case.param,
        "family": case.family,
        "semantics": case.semantics,
        "expected_relation_after": case.expected_relation_after,
        "s2_must_stay_true": case.s2_must_stay_true,
        "revoked_objects": list(case.revoked_objects),
        "revoked_predicates": list(case.revoked_predicates),
        "goal_atoms": [],
        "subgoals": [],
        "setup": {
            "suite": case.suite,
            "init_row": config.init_row,
            "seed": config.seed,
            "max_steps": budget,
            "replan": config.replan,
            "window": case.window,
            "trigger_criterion": case.trigger_criterion,
            "repair_window": repair_window,
        },
        "max_steps": budget,
        "active_budget_steps": budget,
        "total_budget_steps": total_budget,
        "steps": 0,
        "checks": 0,
        "trigger_reached": False,
        "trigger_step": None,
        "injection_step": None,
        "injection": None,
        "policy": None if policy is None else dict(policy.metadata),
        "config": config.as_dict(),
        "resolved_thresholds": None,
        "s2": None,
    }
    env = None
    recorder = None
    started = time.time()
    trigger: WindowTrigger | JointProgressTrigger | None = None
    monitor: WindowMonitor | None = None
    try:
        import numpy as np

        from .runtime.env import load_init_row
        from .runtime.perturbation import BInjector

        if case.asset_source == "native" and not config.libero_home:
            raise RuntimeError(
                "C (native) cases need a resolved LIBERO checkout; call "
                "run_window_matrix (which resolves --libero-home / LIBERO_HOME)"
            )
        if case.asset_source == "compose" and not config.compose_root:
            raise RuntimeError(
                "D (compose) cases need a resolved COMPOSE_ROOT; call "
                "run_window_matrix (which resolves --compose-root / COMPOSE_ROOT)"
            )
        asset_root = (
            config.libero_home
            if case.asset_source == "native"
            else config.compose_root
        )
        bddl_path = case.bddl_path(str(asset_root))
        init_path = case.init_path(str(asset_root))
        for label, path in (("bddl", bddl_path), ("init", init_path)):
            if not path.is_file():
                raise FileNotFoundError(
                    f"{case.case_id}: {label} asset not found: {path}"
                )

        from libero.libero.envs import OffScreenRenderEnv

        init_shape, init_row = load_init_row(
            init_path, config.init_row, config.libero_python
        )
        env = OffScreenRenderEnv(
            bddl_file_name=str(bddl_path),
            camera_heights=config.camera,
            camera_widths=config.camera,
            horizon=budget + repair_window + 100,
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
        dynamic_indices = dynamic_s1_indices(goal_atoms)
        revoked_goal_indices: list[int] = []
        pending_goal_indices: list[int] = []
        dynamic_candidates: list[tuple[int, Any]] = []
        injector = None
        if dynamic_indices:
            for index in dynamic_indices:
                atom = goal_atoms[index]
                candidate_case = replace(
                    case,
                    revoked_objects=(str(atom[1]),),
                    revoked_predicates=("(" + " ".join(str(x) for x in atom) + ")",),
                )
                candidate = BInjector(env, candidate_case, goal_atoms)
                if any(
                    target.body_id is None for target in candidate.targets.values()
                ):
                    continue
                dynamic_candidates.append((index, candidate))
            summary["dynamic_s1_candidates"] = [
                list(goal_atoms[index]) for index, _ in dynamic_candidates
            ]
            summary["revoked_objects"] = []
            summary["revoked_predicates"] = []
            summary["revoked_goal_indices"] = []
            summary["pending_goal_indices"] = []
        if not dynamic_candidates:
            injector = BInjector(env, case, goal_atoms)
            revoked_goal_indices = sorted(
                {
                    int(index)
                    for index in getattr(injector, "goal_atom_index", ())
                    if int(index) >= 0
                }
            )
            pending_goal_indices = [
                index
                for index in range(len(goal_atoms))
                if index not in set(revoked_goal_indices)
            ]
            summary["revoked_goal_indices"] = revoked_goal_indices
            summary["pending_goal_indices"] = pending_goal_indices
            for name, target in injector.targets.items():
                if target.body_id is None:
                    raise RuntimeError(f"cannot resolve revoked object body: {name}")

        s2 = None
        monitor = None
        trigger = None
        if injector is not None:
            s2 = resolve_s2(case, injector, goal_atoms)
            monitor = WindowMonitor(injector, s2, config)
            trigger = _make_trigger(case, config, s2)
            summary["s2"] = s2.as_dict()
            summary["resolved_thresholds"] = resolved_thresholds(case, config, s2)
            summary["s2_object_movable"] = monitor.s2_object_movable

        emit(
            {
                "event": "episode_start",
                "case_id": case.case_id,
                "window": case.window,
                "bddl": str(bddl_path),
                "init": str(init_path),
                "init_shape": list(init_shape),
                "goal_atoms": [list(atom) for atom in goal_atoms],
                "revoked_goal_indices": revoked_goal_indices,
                "pending_goal_indices": pending_goal_indices,
                "s2": None if s2 is None else s2.as_dict(),
                "resolved_thresholds": summary["resolved_thresholds"],
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
        injected = False
        injection: dict[str, Any] | None = None
        injection_step: int | None = None
        injection_frame: int | None = None
        pre_truths: list[bool] | None = None
        s2_before: dict[str, Any] | None = None
        s2_after: dict[str, Any] | None = None
        s2_undisturbed_flag: bool | None = None
        s2_displacement: float | None = None
        post_truths: list[list[bool]] = []
        recovery_ever = False
        restored_at_step: int | None = None
        first_all_done: int | None = None
        first_success_step: int | None = None
        success_ever = False
        trigger_observation: dict[str, Any] | None = None
        stage_label = f"{case.asset_source.upper()} {case.case_id} | {case.window}"

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
            if injector is None:
                truths = [
                    bool(problem._eval_predicate(goal_atoms[index]))  # noqa: SLF001
                    for index, _ in dynamic_candidates
                ]
                chosen = next(
                    (
                        (index, candidate)
                        for (index, candidate), truth in zip(
                            dynamic_candidates, truths, strict=True
                        )
                        if truth
                    ),
                    None,
                )
                if chosen is None:
                    if recorder is not None:
                        recorder.step(
                            obs["agentview_image"],
                            obs.get("robot0_eye_in_hand_image"),
                            step=steps,
                            stage=stage_label + " | dynamic s1 selection",
                            horizon_index=0,
                            last_decision={"line": "waiting for first completed goal atom"},
                            success=False,
                            title=f"{case.asset_source.upper()} matrix | {case.case_id}",
                            policy_label=f"frozen {config.policy}",
                            controller_label="pure policy",
                        )
                    if steps % 5 == 0:
                        emit(
                            {
                                "event": "step",
                                "step": steps,
                                "goal": truths,
                                "window": case.window,
                                "dynamic_pending": True,
                            }
                        )
                    continue
                selected_index, injector = chosen
                atom = goal_atoms[selected_index]
                s2 = resolve_s2(case, injector, goal_atoms)
                monitor = WindowMonitor(injector, s2, config)
                trigger = _make_trigger(case, config, s2)
                summary["revoked_objects"] = [str(atom[1])]
                summary["revoked_predicates"] = [
                    "(" + " ".join(str(x) for x in atom) + ")"
                ]
                summary["revoked_goal_indices"] = [selected_index]
                summary["pending_goal_indices"] = [s2.index]
                summary["selected_s1_goal_index"] = selected_index
                summary["selected_s1_goal_atom"] = list(atom)
                summary["s2"] = s2.as_dict()
                summary["resolved_thresholds"] = resolved_thresholds(
                    case, config, s2
                )
                summary["s2_object_movable"] = monitor.s2_object_movable
                if recorder is not None:
                    recorder.step(
                        obs["agentview_image"],
                        obs.get("robot0_eye_in_hand_image"),
                        step=steps,
                        stage=stage_label + " | dynamic s1 selected",
                        horizon_index=0,
                        last_decision={"line": f"selected s1 {atom[1]}"},
                        success=False,
                        title=f"{case.asset_source.upper()} matrix | {case.case_id}",
                        policy_label=f"frozen {config.policy}",
                        controller_label="pure policy",
                    )
                emit(
                    {
                        "event": "dynamic_s1_selected",
                        "step": steps,
                        "goal_index": selected_index,
                        "goal_atom": list(atom),
                        "s2": s2.as_dict(),
                    }
                )
                continue
            goal_truth = injector.goal_truth()
            revoked_truth = injector.revoked_truth()
            observation, metrics = monitor.observe(
                steps, obs.get("robot0_gripper_qpos")
            )
            if all(goal_truth):
                if first_all_done is None:
                    first_all_done = steps
                    emit(
                        {
                            "event": "all_done",
                            "step": steps,
                            "goal": [bool(value) for value in goal_truth],
                            "revoked": [bool(value) for value in revoked_truth],
                        }
                    )
                success_ever = True
                if first_success_step is None:
                    first_success_step = steps

            if not injected:
                # t033 early: leave a short approach interval after s1 before
                # firing; the generic early trigger would fire immediately.
                if (
                    case.task_idx == 33
                    and case.window in ("mid", "later")
                    and not injector._object_released(  # noqa: SLF001
                        obs.get("robot0_gripper_qpos")
                    )
                ):
                    fired = False
                elif (
                    case.task_idx == 33
                    and case.window in ("mid", "later")
                    and monitor.first_s2_started_step is None
                ):
                    fired = False
                elif (
                    case.window == "early"
                    and case.task_idx == 33
                    and (
                        not injector._object_released(  # noqa: SLF001
                            obs.get("robot0_gripper_qpos")
                        )
                        or (
                            monitor.first_s1_done_step is not None
                            and steps - monitor.first_s1_done_step < 20
                        )
                    )
                ):
                    fired = False
                else:
                    fired = bool(trigger.observe(observation))
                if fired:
                    trigger_observation = dict(metrics)
                    trigger_observation["events"] = list(trigger.events)
                    pre_truths = [bool(value) for value in revoked_truth]
                    s2_before = monitor.progress_snapshot()
                    if recorder is not None:
                        recorder.step(
                            obs["agentview_image"],
                            obs.get("robot0_eye_in_hand_image"),
                            step=steps,
                            stage=stage_label,
                            horizon_index=0,
                            last_decision={
                                "line": (
                                    f"{case.window} window fired -> inject "
                                    f"{case.level}-{case.param or ''}"
                                )
                            },
                            success=False,
                            title=f"{case.asset_source.upper()} matrix | {case.case_id}",
                            policy_label=f"frozen {config.policy}",
                            controller_label="pure policy",
                        )
                    injection = injector.inject(obs.get("robot0_gripper_qpos"))
                    injection_step = steps
                    injected = True
                    # The repair window is appended after injection and never
                    # squeezed by the pre-trigger budget (README §9.3 item 3).
                    total_budget = steps + repair_window
                    summary.update(
                        {
                            "trigger_reached": True,
                            "trigger_step": steps,
                            "trigger_events": list(trigger.events),
                            "trigger_observation": trigger_observation,
                            "injection_step": steps,
                            "injection": injection,
                            "total_budget_steps": total_budget,
                            "s1_done_step": monitor.first_s1_done_step,
                            "s2_started_step": monitor.first_s2_started_step,
                            "s2_at_trigger": s2_before,
                        }
                    )
                    if monitor.first_s1_done_step is not None:
                        summary["steps_from_s1_done_to_trigger"] = (
                            steps - monitor.first_s1_done_step
                        )
                    if recorder is not None:
                        injection_frame = recorder.frames
                        recorder.event_card(
                            obs["agentview_image"],
                            obs.get("robot0_eye_in_hand_image"),
                            title=(
                                f"{case.asset_source.upper()} INJECTION  "
                                f"{case.case_id}  @ step {steps}"
                            ),
                            lines=[
                                (
                                    f"window={case.window} target={case.target} "
                                    f"level={case.level}-{case.param or ''}",
                                    (255, 230, 120),
                                    recorder.font,
                                ),
                                (
                                    f"s1 before={all(pre_truths)} "
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
                    s2_after = monitor.progress_snapshot()
                    s2_undisturbed_flag, s2_displacement = s2_undisturbed(
                        s2_before, s2_after
                    )
                    summary["s2_after_injection"] = s2_after
                    summary["s2_undisturbed_by_injection"] = bool(
                        s2_undisturbed_flag
                    )
                    summary["s2_injection_displacement"] = s2_displacement
                    emit(
                        {
                            "event": "injection",
                            "step": steps,
                            "case_id": case.case_id,
                            "window": case.window,
                            "level": case.level,
                            "param": case.param,
                            "target": case.target,
                            "pre_truths": pre_truths,
                            "s2_undisturbed_by_injection": bool(
                                s2_undisturbed_flag
                            ),
                            **{
                                key: injection[key]
                                for key in (
                                    "kind",
                                    "revoked_before",
                                    "revoked_after",
                                    "goal_before",
                                    "goal_after",
                                    "relation_after",
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
                        stage=stage_label + " | solve",
                        horizon_index=0,
                        last_decision={"line": "waiting for GT window"},
                        success=bool(all(goal_truth)),
                        title=f"{case.asset_source.upper()} matrix | {case.case_id}",
                        policy_label=f"frozen {config.policy}",
                        controller_label="pure policy",
                    )
                if steps % 5 == 0:
                    emit(
                        {
                            "event": "step",
                            "step": steps,
                            "goal": [bool(value) for value in goal_truth],
                            "revoked": [bool(value) for value in revoked_truth],
                            "window": case.window,
                            "s1_done": metrics.get("s1_done"),
                            "s1_settled": metrics.get("s1_settled"),
                            "s2_started": metrics.get("s2_started"),
                            "s2_lift_m": metrics.get("s2_lift_m"),
                            "s2_to_goal_xy_m": metrics.get("s2_to_goal_xy_m"),
                            "s2_joint_progress": metrics.get("s2_joint_progress"),
                            "injected": False,
                        }
                    )
                continue

            post_truths.append([bool(value) for value in revoked_truth])
            if all(revoked_truth):
                recovery_ever = True
                if restored_at_step is None:
                    restored_at_step = steps
            if recorder is not None:
                recorder.step(
                    obs["agentview_image"],
                    obs.get("robot0_eye_in_hand_image"),
                    step=steps,
                    stage=stage_label + " | revoked",
                    horizon_index=0,
                    last_decision={
                        "line": f"injected @ {injection_step}; repairing"
                    },
                    success=bool(all(goal_truth)),
                    title=f"{case.asset_source.upper()} matrix | {case.case_id}",
                    policy_label=f"frozen {config.policy}",
                    controller_label="pure policy",
                )
            if steps % 5 == 0:
                emit(
                    {
                        "event": "step",
                        "step": steps,
                        "goal": [bool(value) for value in goal_truth],
                        "revoked": [bool(value) for value in revoked_truth],
                        "window": case.window,
                        "s1_done": metrics.get("s1_done"),
                        "s2_started": metrics.get("s2_started"),
                        "s2_lift_m": metrics.get("s2_lift_m"),
                        "s2_to_goal_xy_m": metrics.get("s2_to_goal_xy_m"),
                        "s2_joint_progress": metrics.get("s2_joint_progress"),
                        "injected": True,
                    }
                )

        final_goal = [bool(value) for value in injector.goal_truth()]
        final_revoked = [bool(value) for value in injector.revoked_truth()]
        final_pending = [final_goal[index] for index in pending_goal_indices]
        revoked_ok = all(final_revoked) if revoked_goal_indices else True
        pending_ok = all(final_pending) if final_pending else True
        summary.update(
            final_goal_truth=final_goal,
            final_revoked_truth=final_revoked,
            final_pending_truth=final_pending,
            atoms_completed=sum(1 for value in final_goal if value),
            subtask_progress=(
                sum(1 for value in final_goal if value) / len(final_goal)
                if final_goal
                else None
            ),
            terminal_state=(
                "both"
                if revoked_ok and pending_ok
                else "restore_only"
                if revoked_ok
                else "pending_only"
                if pending_ok
                else "neither"
            ),
        )
        if injected:
            relation_before = bool(all(pre_truths or []))
            relation_after = bool(injection["relation_after"]) if injection else None
            relation_final = bool(all(final_revoked))
            restored = bool(all(final_revoked))
            validity = {
                "completed_relation_true_before_intervention": relation_before,
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
                "s2_undisturbed_by_injection": bool(s2_undisturbed_flag),
            }
            case_valid = all(
                validity[key]
                for key in (
                    "completed_relation_true_before_intervention",
                    "all_revoked_false_after_intervention",
                    "no_object_penetration",
                    "zero_velocity_after_intervention",
                    "object_released_before_intervention",
                    "restorable",
                    "s2_undisturbed_by_injection",
                )
            )
            summary.update(
                relation_before=relation_before,
                relation_after_injection=relation_after,
                relation_final=relation_final,
                restored_at_step=restored_at_step,
                recovery_ever=recovery_ever,
                recovered=restored,
                recovery=restored,
                validity=validity,
                case_valid=bool(case_valid),
                termination="step_limit" if steps >= total_budget else "done",
            )
        else:
            skipped_reason = (
                f"{case.window} window not reached within {total_budget} steps"
            )
            if (
                monitor is not None
                and case.window in ("mid", "later")
                and monitor.s2_object_movable is False
            ):
                skipped_reason = (
                    f"s2 object {monitor.s2.object_name!r} has no free joint; "
                    f"{case.window} window cannot be reached"
                )
            summary.update(
                trigger_skipped_reason=skipped_reason,
                relation_before=False,
                relation_after_injection=None,
                relation_final=None,
                recovered=None,
                recovery=None,
                validity={"trigger_reached": False},
                case_valid=False,
                termination="trigger_not_reached",
            )

        summary.update(
            status="ok",
            steps=steps,
            checks=steps,
            max_steps=budget,
            total_budget_steps=total_budget,
            repair_budget_steps=(
                None if injection_step is None else total_budget - injection_step
            ),
            repair_steps_used=(
                None if injection_step is None else steps - injection_step
            ),
            first_all_done_step=first_all_done,
            first_success_step=first_success_step,
            success_ever=success_ever,
            success=bool(all(final_goal)),
            early_stopped=False,
            stop_reason=None,
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
            }
        emit(
            {
                "event": "episode_end",
                "status": "ok",
                "steps": steps,
                "trigger_reached": summary.get("trigger_reached"),
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
# planning
# ---------------------------------------------------------------------------


def _case_asset_paths(
    case: WindowCase, config: WindowRunConfig
) -> tuple[Path | None, Path | None]:
    root = config.libero_home if case.asset_source == "native" else config.compose_root
    if not root:
        return None, None
    try:
        return case.bddl_path(root), case.init_path(root)
    except FileNotFoundError:
        return None, None


def build_window_plan(
    *,
    matrix: WindowMatrix,
    cases: Sequence[WindowCase],
    config: WindowRunConfig,
    checkpoint: str | None = None,
    config_name: str = "pi05_libero",
    shard_index: int = 0,
    shard_count: int = 1,
    script: str = "scripts/run_window_matrix.py",
) -> dict[str, Any]:
    """Return the ``plan.json`` payload of a C/D dry run (not evidence)."""

    by_window: dict[str, int] = {}
    by_level: dict[str, int] = {}
    by_suite: dict[str, int] = {}
    for case in cases:
        by_window[case.window] = by_window.get(case.window, 0) + 1
        by_level[case.level] = by_level.get(case.level, 0) + 1
        by_suite[case.suite] = by_suite.get(case.suite, 0) + 1
    case_payloads: list[dict[str, Any]] = []
    missing = 0
    for case in cases:
        budget, repair = _budget(case, config)
        bddl, init = _case_asset_paths(case, config)
        present = None
        if bddl is not None and init is not None:
            present = bool(bddl.is_file() and init.is_file())
            if not present:
                missing += 1
        item = case.as_plan_dict()
        item.update(
            {
                "max_steps": budget,
                "repair_window": repair,
                "bddl_path": None if bddl is None else str(bddl),
                "init_path": None if init is None else str(init),
                "assets_present": present,
            }
        )
        case_payloads.append(item)
    return {
        "schema_version": SCHEMA_VERSION,
        "dry_run": True,
        "matrix": matrix.summary(),
        "selected": len(cases),
        "tasks": len({case.task_key for case in cases}),
        "by_window": {window: by_window.get(window, 0) for window in WINDOWS},
        "by_level": dict(sorted(by_level.items())),
        "by_suite": dict(sorted(by_suite.items())),
        "case_ids": [case.case_id for case in cases],
        "cases": case_payloads,
        "shard": {"index": shard_index, "count": shard_count},
        "assets": {
            "libero_home": config.libero_home,
            "compose_root": config.compose_root,
            "missing_cases": missing,
        },
        "defaults": {
            **config.as_dict(),
            "checkpoint": checkpoint,
            "config_name": config_name,
            "matrix": str(matrix.source),
            "script": script,
        },
    }


def write_window_plan(output: str | Path, payload: Mapping[str, Any]) -> Path:
    """Write ``plan.json`` (the only artifact of a dry run)."""

    return write_json(Path(output) / "plan.json", payload)


# ---------------------------------------------------------------------------
# batch runner
# ---------------------------------------------------------------------------


def _preflight_assets(
    cases: Sequence[WindowCase], config: WindowRunConfig
) -> None:
    """Fail loudly (before any model loads) when a selected asset is missing."""

    problems: list[str] = []
    for case in cases:
        root = (
            config.libero_home
            if case.asset_source == "native"
            else config.compose_root
        )
        if not root:
            problems.append(
                f"{case.case_id}: {case.asset_root_name} is not configured"
            )
            continue
        try:
            bddl_path = case.bddl_path(root)
            init_path = case.init_path(root)
        except FileNotFoundError as error:
            problems.append(f"{case.case_id}: {error}")
            continue
        for label, path in (("bddl", bddl_path), ("init", init_path)):
            if not path.is_file():
                problems.append(f"{case.case_id}: {label} not found: {path}")
    if problems:
        preview = "\n".join(f"  - {problem}" for problem in problems[:20])
        suffix = (
            "" if len(problems) <= 20 else f"\n  ... and {len(problems) - 20} more"
        )
        raise FileNotFoundError(
            f"window matrix assets missing ({len(problems)} problems):\n"
            f"{preview}{suffix}"
        )


def aggregate_window_episodes(
    episodes: Sequence[Mapping[str, Any]],
    output: str | Path,
    defaults: Mapping[str, Any],
) -> dict[str, Any]:
    """Write ``run-summary.json`` + ``report.md`` for a C/D run."""

    output = Path(output)
    ok = [episode for episode in episodes if episode.get("status") == "ok"]
    triggered = [episode for episode in ok if episode.get("trigger_reached")]
    valid = [episode for episode in ok if episode.get("case_valid")]
    recoverable = [episode for episode in valid if not episode.get("is_control")]
    recovered = [episode for episode in recoverable if episode.get("recovered")]
    windows: dict[str, Any] = {}
    for window in WINDOWS:
        rows = [episode for episode in ok if episode.get("window") == window]
        window_triggered = [episode for episode in rows if episode.get("trigger_reached")]
        window_valid = [episode for episode in rows if episode.get("case_valid")]
        window_recovered = [
            episode for episode in window_valid if episode.get("recovered")
        ]
        windows[window] = {
            "cases": len(rows),
            "triggered": len(window_triggered),
            "valid": len(window_valid),
            "recovered": len(window_recovered),
            "trigger_rate": (
                None if not rows else round(len(window_triggered) / len(rows), 4)
            ),
            "recovery_rate": (
                None
                if not window_valid
                else round(len(window_recovered) / len(window_valid), 4)
            ),
        }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "kind": defaults.get("matrix_kind"),
        "cases": len(episodes),
        "ok": len(ok),
        "errors": len(episodes) - len(ok),
        "triggered": len(triggered),
        "valid": len(valid),
        "recoverable_valid": len(recoverable),
        "recovered": len(recovered),
        "recovery_rate": (
            None if not recoverable else round(len(recovered) / len(recoverable), 4)
        ),
        "controls": 0,
        "control_ok": 0,
        "control_rate": None,
        "windows": windows,
        "defaults": dict(defaults),
    }
    write_json(output / "run-summary.json", summary)
    lines = [
        "# C/D in-execution rollback run",
        "",
        f"- output: `{output}`",
        f"- matrix kind: {defaults.get('matrix_kind')}",
        f"- cases: {summary['cases']} (ok {summary['ok']}, errors {summary['errors']})",
        f"- triggered: {summary['triggered']}",
        f"- valid: {summary['valid']}",
        f"- recovery: {summary['recovered']}/{summary['recoverable_valid']} "
        f"= {summary['recovery_rate']}",
        "",
        "| window | cases | triggered | trigger rate | valid | recovered | recovery rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for window in WINDOWS:
        entry = windows[window]
        lines.append(
            f"| {window} | {entry['cases']} | {entry['triggered']} | "
            f"{entry['trigger_rate']} | {entry['valid']} | "
            f"{entry['recovered']} | {entry['recovery_rate']} |"
        )
    lines.extend(
        [
            "",
            "| case | window | level | s2 | trigger | trigger step | valid | recovered | "
            "terminal | steps |",
            "|---|---|---|---|---:|---:|---|---|---|---:|",
        ]
    )
    for episode in episodes:
        s2 = episode.get("s2") or {}
        lines.append(
            f"| {episode.get('case_id')} | {episode.get('window')} | "
            f"{episode.get('level')}-{episode.get('param') or ''} | "
            f"{s2.get('kind', '-')} | {episode.get('trigger_reached')} | "
            f"{episode.get('trigger_step')} | {episode.get('case_valid')} | "
            f"{episode.get('recovered')} | {episode.get('terminal_state', '-')} | "
            f"{episode.get('steps')} |"
        )
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def run_window_matrix(
    *,
    matrix: WindowMatrix,
    cases: Sequence[WindowCase],
    output: str | Path,
    model: str = "none",
    checkpoint: str | None = None,
    config: WindowRunConfig | None = None,
    config_name: str = "pi05_libero",
    unnorm_key: str | None = None,
    workspace: str | None = None,
    resume: bool = True,
    retry_errors: bool = False,
    retry_invalid: bool = False,
    preflight: bool = True,
    script: str = "scripts/run_window_matrix.py",
) -> dict[str, Any]:
    """Run a batch of C/D cases and write the run-level artifacts."""

    from .policies import load_policy, normalize_policy_name
    from .runtime.env import bootstrap_environment, resolve_libero_home

    policy_name = normalize_policy_name(model)
    config = replace(config or WindowRunConfig(), policy=policy_name)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    libero_home = resolve_libero_home(config.libero_home)
    config = replace(config, libero_home=str(libero_home))
    compose_root: str | None = None
    if any(case.asset_source == "compose" for case in cases):
        resolved = resolve_compose_root(config.compose_root)
        config = replace(config, compose_root=str(resolved))
        compose_root = str(resolved)
    checkpoint_path = _resolve_checkpoint(policy_name, checkpoint)
    if checkpoint_path is not None and not Path(checkpoint_path).exists():
        raise FileNotFoundError(f"{policy_name} checkpoint not found: {checkpoint_path}")
    if preflight:
        _preflight_assets(cases, config)

    defaults = {
        **config.as_dict(),
        "checkpoint": checkpoint_path,
        "config_name": config_name,
        "matrix": str(matrix.source),
        "matrix_kind": matrix.kind,
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
    if compose_root is not None:
        print(f"[compose] root={compose_root}")

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
                f"({case.asset_source} t"
                f"{case.task_idx if case.task_idx is not None else case.task_id} "
                f"{case.window} {case.level}{case.param or ''}) ...",
                flush=True,
            )
            summary = run_window_case(
                case=case, config=config, policy=policy, output=output
            )
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
                f"terminal={summary.get('terminal_state')} "
                f"steps={summary.get('steps')} "
                f"elapsed={summary.get('elapsed_s')}s eta={eta / 3600:.2f}h",
                flush=True,
            )
    finally:
        stream.close()
        aggregate = aggregate_window_episodes(episodes, output, defaults)
    print(RULE)
    print(f"done: output={output}")
    print(RULE)
    return aggregate


__all__ = [
    "CHECKPOINT_ENV",
    "JointProgressObservation",
    "JointProgressTrigger",
    "JointTriggerConfig",
    "SCHEMA_VERSION",
    "S2Target",
    "UnsupportedWindowError",
    "WindowMonitor",
    "WindowRunConfig",
    "aggregate_window_episodes",
    "build_window_plan",
    "joint_progress",
    "lift_from_initial",
    "resolved_thresholds",
    "resolve_s2",
    "run_window_case",
    "run_window_matrix",
    "s2_undisturbed",
    "select_window_cases",
    "write_window_plan",
    "xy_distance",
]
