"""MuJoCo state perturbation for the B matrix (completion-boundary rollback).

The module implements the four perturbation levels from ``docs/SPEC.md`` and
README §3.4 on top of a live LIBERO ``OffScreenRenderEnv``:

``C0``  no-op control (same delay/post-success window, state untouched)
``L0``  restore the revoked object/joint to the episode-initial state
``L1``  L0 plus a 3/6/10 cm translation away from the target region
        (joint tasks: 10/25/40 % of the travelled joint range)
``L2``  L0 position plus a 30/60/90 degree yaw about world z

Everything is expressed through ``sim.data.qpos``/``sim.data.qvel`` so it works
for both free bodies and articulated fixtures.  After writing the state we run
``mj_forward`` (``sim.forward()``), evaluate the native BDDL predicates, measure
penetration / velocity / geometry and run a state-write oracle that temporarily
restores the pre-injection state to prove the relation is recoverable.  No
status is assumed: every gate is reported as a value and the runner derives
``case_valid`` from the gates.

The module needs numpy (runtime extra) but never imports torch or LIBERO.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..matrices import BCase, LevelSpec, parse_predicate

MJ_JNT_FREE = 0
MJ_JNT_BALL = 1
MJ_JNT_SLIDE = 2
MJ_JNT_HINGE = 3

EPS = 1e-8


# ---------------------------------------------------------------------------
# small math helpers
# ---------------------------------------------------------------------------


def _quat_or_default(value: Sequence[float] | None) -> Sequence[float]:
    return [1.0, 0.0, 0.0, 0.0] if value is None else value


def quat_mul(left: Sequence[float], right: Sequence[float]) -> np.ndarray:
    """Hamilton product of two ``wxyz`` quaternions."""

    lw, lx, ly, lz = (float(v) for v in left)
    rw, rx, ry, rz = (float(v) for v in right)
    return np.asarray(
        [
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        ],
        dtype=np.float64,
    )


def quat_normalize(quat: Sequence[float]) -> np.ndarray:
    value = np.asarray(quat, dtype=np.float64)
    norm = float(np.linalg.norm(value))
    if norm < EPS:
        return np.asarray([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
    return value / norm


def quat_angle(left: Sequence[float], right: Sequence[float]) -> float:
    a = quat_normalize(left)
    b = quat_normalize(right)
    dot = float(np.clip(abs(np.dot(a, b)), 0.0, 1.0))
    return 2.0 * math.acos(dot)


def quat_yaw(angle_rad: float) -> np.ndarray:
    half = 0.5 * float(angle_rad)
    return np.asarray([math.cos(half), 0.0, 0.0, math.sin(half)], dtype=np.float64)


def quat_to_axis_angle(quat: Sequence[float]) -> tuple[np.ndarray, float]:
    q = quat_normalize(quat)
    if q[0] < 0:
        q = -q
    w = float(np.clip(q[0], -1.0, 1.0))
    angle = 2.0 * math.acos(w)
    s = math.sqrt(max(0.0, 1.0 - w * w))
    if s < 1e-6:
        return np.asarray([0.0, 0.0, 1.0]), 0.0
    return np.asarray(q[1:] / s, dtype=np.float64), angle


def _body_position(sim, body_id: int) -> np.ndarray:
    return np.asarray(sim.data.body_xpos[body_id], dtype=np.float64).copy()


def _find_body_id(model, name: str) -> int | None:
    """Resolve a BDDL role name to a MuJoCo body id.

    LIBERO names objects as ``<role>_main`` / ``<role>_g0`` and regions as
    ``<role>`` or ``<role>_region``; prefer an exact match, then a free-joint
    body, then any prefix match.
    """

    names = list(model.body_names)
    lowered = {n.lower(): i for i, n in enumerate(names)}
    for candidate in (name, f"{name}_main", f"{name}_region"):
        hit = lowered.get(candidate.lower())
        if hit is not None:
            return hit
    prefix = [
        (i, n)
        for i, n in enumerate(names)
        if n.lower() == name.lower() or n.lower().startswith(name.lower() + "_")
    ]
    if not prefix:
        return None

    def score(item: tuple[int, str]) -> tuple[int, int]:
        index, body_name = item
        free = 0
        joint_addr = int(model.body_jntadr[index])
        joint_num = int(model.body_jntnum[index])
        if joint_num and int(model.jnt_type[joint_addr]) == MJ_JNT_FREE:
            free = 1
        region = 1 if body_name.lower().endswith("_region") else 0
        return (free, region)

    prefix.sort(key=score, reverse=True)
    return prefix[0][0]


def _body_subtree(model, root_id: int) -> set[int]:
    """All body ids whose ancestor chain contains ``root_id``."""

    result: set[int] = set()
    for body_id in range(model.nbody):
        current = body_id
        for _ in range(64):
            if current == root_id:
                result.add(body_id)
                break
            parent = int(model.body_parentid[current])
            if parent == current or parent <= 0:
                break
            current = parent
    return result


def _free_joint(model, body_id: int) -> int | None:
    start = int(model.body_jntadr[body_id])
    count = int(model.body_jntnum[body_id])
    for joint_id in range(start, start + count):
        if int(model.jnt_type[joint_id]) == MJ_JNT_FREE:
            return joint_id
    return None


def _joint_ids_in_subtree(model, body_id: int) -> list[int]:
    joints: list[int] = []
    for candidate in sorted(_body_subtree(model, body_id)):
        start = int(model.body_jntadr[candidate])
        count = int(model.body_jntnum[candidate])
        joints.extend(range(start, start + count))
    return joints


def _joint_qpos(sim, joint_id: int) -> float:
    address = int(sim.model.jnt_qposadr[joint_id])
    return float(sim.data.qpos[address])


def _set_joint_qpos(sim, joint_id: int, value: float) -> None:
    qpos_address = int(sim.model.jnt_qposadr[joint_id])
    dof_address = int(sim.model.jnt_dofadr[joint_id])
    sim.data.qpos[qpos_address] = float(value)
    if dof_address >= 0:
        sim.data.qvel[dof_address] = 0.0


def _free_qpos(sim, joint_id: int) -> tuple[np.ndarray, np.ndarray]:
    address = int(sim.model.jnt_qposadr[joint_id])
    return (
        np.asarray(sim.data.qpos[address : address + 3], dtype=np.float64).copy(),
        np.asarray(sim.data.qpos[address + 3 : address + 7], dtype=np.float64).copy(),
    )


def _set_free_qpos(
    sim, joint_id: int, position: Sequence[float], quat: Sequence[float]
) -> None:
    address = int(sim.model.jnt_qposadr[joint_id])
    dof_address = int(sim.model.jnt_dofadr[joint_id])
    sim.data.qpos[address : address + 3] = np.asarray(position, dtype=np.float64)
    sim.data.qpos[address + 3 : address + 7] = quat_normalize(quat)
    if dof_address >= 0:
        sim.data.qvel[dof_address : dof_address + 6] = 0.0


def _joint_range(model, joint_id: int) -> tuple[float, float] | None:
    if not bool(model.jnt_limited[joint_id]):
        return None
    low, high = (float(v) for v in model.jnt_range[joint_id])
    if high <= low:
        return None
    return low, high


# ---------------------------------------------------------------------------
# state capture
# ---------------------------------------------------------------------------


@dataclass
class TargetState:
    """Initial / injected state of one revoked object."""

    name: str
    body_id: int | None
    kind: str  # "free" | "joint"
    free_joint: int | None = None
    joint_ids: list[int] = field(default_factory=list)
    position: np.ndarray | None = None
    quat: np.ndarray | None = None
    joint_qpos: dict[int, float] = field(default_factory=dict)

    def copy_pose(self) -> tuple[np.ndarray | None, np.ndarray | None]:
        return (
            None if self.position is None else self.position.copy(),
            None if self.quat is None else self.quat.copy(),
        )


@dataclass
class TargetSnapshot:
    """Pose + joints of one target at one point in time."""

    name: str
    body_id: int | None
    kind: str
    position: np.ndarray | None = None
    quat: np.ndarray | None = None
    joint_qpos: dict[int, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "position": (
                None
                if self.position is None
                else [round(float(v), 6) for v in self.position]
            ),
            "quat": (
                None if self.quat is None else [round(float(v), 6) for v in self.quat]
            ),
            "joint_qpos": {str(k): round(float(v), 6) for k, v in self.joint_qpos.items()},
        }


class BInjector:
    """Capture, inject and validate one B perturbation."""

    def __init__(self, env, case: BCase, goal_atoms: Sequence[Sequence[Any]]):
        self.env = env
        self.case = case
        self.sim = env.env.sim
        self.model = self.sim.model
        self.problem = env.env
        self.goal_atoms = [tuple(atom) for atom in goal_atoms]
        self.revoked_atoms = [parse_predicate(p) for p in case.revoked_predicates]
        self.goal_atom_index = self._match_goal_atoms()
        self.eval_atoms = []
        for index, atom in enumerate(self.revoked_atoms):
            goal_index = self.goal_atom_index[index]
            if goal_index >= 0:
                # Reuse the native goal atom spelling exactly (BDDL atoms are
                # lower-case in this checkout).
                self.eval_atoms.append(self.goal_atoms[goal_index])
            else:
                # A precondition such as ``(Open ...)`` is not part of the goal;
                # the predicate registry is lower-case.
                self.eval_atoms.append((str(atom[0]).lower(), *atom[1:]))
        self.targets: dict[str, TargetState] = {}
        self.initial_qpos = np.asarray(self.sim.data.qpos, dtype=np.float64).copy()
        for object_name in case.revoked_objects:
            self.targets[object_name] = self._capture_target(object_name)
        self.region_centers: dict[str, np.ndarray] = {}
        for tokens in self.revoked_atoms:
            region = self._region_token(tokens)
            if region:
                self.region_centers[region] = self._region_center(region)
        self._initial: dict[str, TargetSnapshot] = {
            name: self.snapshot(name) for name in self.targets
        }

    # -- construction -----------------------------------------------------

    def _match_goal_atoms(self) -> list[int]:
        indices: list[int] = []
        for atom in self.revoked_atoms:
            lowered = tuple(str(token).lower() for token in atom)
            found = None
            for index, goal in enumerate(self.goal_atoms):
                if tuple(str(token).lower() for token in goal) == lowered:
                    found = index
                    break
            indices.append(-1 if found is None else found)
        return indices

    def _capture_target(self, name: str) -> TargetState:
        body_id = _find_body_id(self.model, name)
        if body_id is None:
            return TargetState(name=name, body_id=None, kind="missing")
        free_joint = _free_joint(self.model, body_id)
        if free_joint is not None:
            position, quat = _free_qpos(self.sim, free_joint)
            return TargetState(
                name=name,
                body_id=body_id,
                kind="free",
                free_joint=free_joint,
                position=position,
                quat=quat,
                joint_ids=[free_joint],
            )
        joint_ids = [
            joint_id
            for joint_id in _joint_ids_in_subtree(self.model, body_id)
            if int(self.model.jnt_type[joint_id]) in (MJ_JNT_SLIDE, MJ_JNT_HINGE)
        ]
        return TargetState(
            name=name,
            body_id=body_id,
            kind="joint",
            joint_ids=joint_ids,
            joint_qpos={
                joint_id: _joint_qpos(self.sim, joint_id) for joint_id in joint_ids
            },
        )

    def _region_token(self, tokens: Sequence[str]) -> str | None:
        for token in reversed(tokens[1:]):
            text = str(token)
            if text.lower().endswith("_region") or "region" in text.lower():
                return text
        return str(tokens[-1]) if len(tokens) > 1 else None

    def _region_center(self, name: str) -> np.ndarray:
        body_id = _find_body_id(self.model, name)
        if body_id is not None:
            return _body_position(self.sim, body_id)
        site_name = name if name in self.model.site_names else f"{name}_site"
        if site_name in self.model.site_names:
            site_id = self.model.site_names.index(site_name)
            return np.asarray(self.sim.data.site_xpos[site_id], dtype=np.float64).copy()
        return np.zeros(3, dtype=np.float64)

    # -- snapshots --------------------------------------------------------

    def snapshot(self, name: str) -> TargetSnapshot:
        target = self.targets[name]
        if target.kind == "free" and target.free_joint is not None:
            position, quat = _free_qpos(self.sim, target.free_joint)
            return TargetSnapshot(
                name=name,
                body_id=target.body_id,
                kind="free",
                position=position,
                quat=quat,
                joint_qpos={},
            )
        joints = {
            joint_id: _joint_qpos(self.sim, joint_id) for joint_id in target.joint_ids
        }
        return TargetSnapshot(
            name=name,
            body_id=target.body_id,
            kind="joint",
            joint_qpos=joints,
        )

    def snapshot_all(self) -> dict[str, TargetSnapshot]:
        return {name: self.snapshot(name) for name in self.targets}

    def restore(self, snapshots: Mapping[str, TargetSnapshot]) -> None:
        for snap in snapshots.values():
            self._apply_snapshot(snap)
        self._forward()

    def _apply_snapshot(self, snap: TargetSnapshot) -> None:
        target = self.targets.get(snap.name)
        if target is None:
            return
        if snap.kind == "free" and target.free_joint is not None and snap.position is not None:
            _set_free_qpos(
                self.sim,
                target.free_joint,
                snap.position,
                _quat_or_default(snap.quat),
            )
            return
        for joint_id, value in snap.joint_qpos.items():
            _set_joint_qpos(self.sim, joint_id, value)

    # -- truth ------------------------------------------------------------

    def goal_truth(self) -> list[bool]:
        return [bool(self.problem._eval_predicate(atom)) for atom in self.goal_atoms]

    def revoked_truth(self) -> list[bool]:
        return [bool(self.problem._eval_predicate(atom)) for atom in self.eval_atoms]

    def all_goal_true(self) -> bool:
        return all(self.goal_truth())

    def relation_after(self) -> bool:
        """True when *every* revoked relation is true after injection."""

        return all(self.revoked_truth())

    # -- injection --------------------------------------------------------

    def inject(self, gripper_qpos: Sequence[float] | None = None) -> dict[str, Any]:
        spec = self.case.level_spec
        # The injector is constructed right after settling (episode t=0), so
        # ``self._initial`` is the true initial state.  Joint values and
        # region centres, however, must be read at the injection instant.
        self.cache_injection_joint_qpos()
        self.region_centers = {
            region: self._region_center(region) for region in self.region_centers
        }
        pre_goal_state = self._pre_goal_state() if self.case.target == "pre" else []
        before = {
            "goal": self.goal_truth(),
            "revoked": self.revoked_truth(),
            "snapshots": {name: snap.as_dict() for name, snap in self.snapshot_all().items()},
        }
        applied: list[dict[str, Any]] = []
        if spec.kind == "c0":
            self._forward()
        elif spec.kind == "init":
            for name in self.targets:
                self._restore_initial(name)
                applied.append({"target": name, "mode": "init"})
            self._forward()
        elif spec.kind == "translation":
            # ``both`` (and mixed rows) apply the pose level to the object and
            # reset every articulated component to its initial value; only a
            # dedicated joint target (s1 / s2 / pre) uses the ratio level.
            joint_ratio = self.case.target != "both" and self.case.family != "mixed"
            for name, target in self.targets.items():
                if target.kind == "free":
                    applied.append(self._apply_translation(name, spec))
                elif joint_ratio:
                    applied.append(self._apply_joint_ratio(name, spec))
                else:
                    self._restore_initial(name)
                    applied.append({"target": name, "mode": "init_joint"})
            self._forward()
        elif spec.kind == "yaw":
            for name, target in self.targets.items():
                if target.kind == "free":
                    applied.append(self._apply_yaw(name, spec))
                else:
                    # ``both`` with a joint: documented rule is joint -> init.
                    self._restore_initial(name)
                    applied.append({"target": name, "mode": "init_joint"})
            self._forward()
        else:  # pragma: no cover
            raise ValueError(f"unsupported level kind: {spec.kind}")

        if pre_goal_state and spec.kind in ("init", "translation"):
            self._carry_pre_goal_objects(pre_goal_state)
        after = self.snapshot_all()
        geometry = self._geometry(
            before["snapshots"], {k: v.as_dict() for k, v in after.items()}
        )
        max_velocity = self._max_target_velocity()
        penetration, contact_bodies = self._penetration()
        released = self._object_released(gripper_qpos)
        goal_after = self.goal_truth()
        revoked_after = self.revoked_truth()
        result: dict[str, Any] = {
            "case_id": self.case.case_id,
            "level": self.case.level,
            "param": self.case.param,
            "kind": spec.kind,
            "goal_before": before["goal"],
            "revoked_before": before["revoked"],
            "goal_after": goal_after,
            "revoked_after": revoked_after,
            "relation_after": all(revoked_after),
            "expected_relation_after": self.case.expected_relation_after,
            "goal_preserved": bool(all(goal_after)) if self.case.target == "pre" else None,
            "applied": applied,
            "geometry": geometry,
            "max_velocity": round(float(max_velocity), 8),
            "zero_velocity": bool(max_velocity <= 1e-6),
            "penetration_m": round(float(penetration), 6),
            "no_penetration": bool(penetration <= 1e-2),
            "penetration_bodies": contact_bodies,
            "object_released": released,
            "snapshot_before": before["snapshots"],
            "snapshot_after": {k: v.as_dict() for k, v in after.items()},
        }
        result["restorable"], result["restore_probe"] = self._restorable_probe(
            before["snapshots"], after
        )
        return result

    def _restore_initial(self, name: str) -> None:
        initial = self._initial[name]
        if initial.kind == "free" and initial.position is not None:
            target = self.targets[name]
            if target.free_joint is not None:
                _set_free_qpos(
                    self.sim,
                    target.free_joint,
                    initial.position,
                    _quat_or_default(initial.quat),
                )
            return
        for joint_id, value in initial.joint_qpos.items():
            _set_joint_qpos(self.sim, joint_id, value)

    def _active_joint(self, name: str) -> int | None:
        target = self.targets[name]
        if not target.joint_ids:
            return None
        best = None
        best_score = -1.0
        tokens = {token.lower() for atom in self.revoked_atoms for token in atom}
        for joint_id in target.joint_ids:
            delta = abs(
                _joint_qpos(self.sim, joint_id) - target.joint_qpos.get(joint_id, 0.0)
            )
            joint_name = str(self.model.joint_names[joint_id]).lower()
            overlap = 0
            for token in tokens:
                parts = [
                    part
                    for part in token.split("_")
                    if part and part not in {"region", "main"}
                ]
                overlap += sum(1 for part in parts if part in joint_name)
            score = delta + 1e-3 * overlap
            if score > best_score:
                best, best_score = joint_id, score
        return best

    def _apply_translation(self, name: str, spec: LevelSpec) -> dict[str, Any]:
        target = self.targets[name]
        initial = self._initial[name]
        if initial.position is None:
            return {"target": name, "mode": "translation", "error": "no initial position"}
        region = self._region_for(name)
        center = self.region_centers.get(region or "", None)
        direction = np.asarray(initial.position[:2], dtype=np.float64)
        if center is not None:
            direction = direction - np.asarray(center[:2], dtype=np.float64)
        norm = float(np.linalg.norm(direction))
        if norm < 1e-6:
            direction = np.asarray([1.0, 0.0], dtype=np.float64)
        else:
            direction = direction / norm
        delta = float(spec.translation_m or 0.0)
        position = np.asarray(initial.position, dtype=np.float64).copy()
        position[:2] = position[:2] + direction * delta
        _set_free_qpos(self.sim, target.free_joint, position, _quat_or_default(initial.quat))
        # If the relation is still true (large region tolerance) push further
        # until it flips; record the actually applied distance.
        applied_delta = delta
        for _ in range(6):
            self._forward()
            if not all(self.revoked_truth()):
                break
            applied_delta += 0.02
            position[:2] = (
                np.asarray(initial.position, dtype=np.float64)[:2] + direction * applied_delta
            )
            _set_free_qpos(
                self.sim, target.free_joint, position, _quat_or_default(initial.quat)
            )
        self._forward()
        # The radial ray can point into a neighbouring fixture (e.g. goal-t030's
        # bowl is pushed onto the stove at 10 cm).  Keep the ray direction but
        # add the smallest vertical clearance that removes the penetration; if
        # that is not enough, shorten the radial distance.  Both adjustments are
        # recorded so the actual geometry stays auditable.
        initial_z = float(initial.position[2])
        clearance_lift = 0.0
        penetration, _ = self._penetration()
        if penetration > 1e-2:
            for lift in (0.01, 0.02, 0.03, 0.04, 0.05, 0.06):
                position[2] = initial_z + lift
                _set_free_qpos(
                    self.sim, target.free_joint, position, _quat_or_default(initial.quat)
                )
                self._forward()
                penetration, _ = self._penetration()
                if penetration <= 1e-2:
                    clearance_lift = lift
                    break
        if penetration > 1e-2:
            for step_back in range(1, 11):
                candidate = max(0.0, applied_delta - 0.01 * step_back)
                position[:2] = (
                    np.asarray(initial.position, dtype=np.float64)[:2]
                    + direction * candidate
                )
                position[2] = initial_z
                _set_free_qpos(
                    self.sim, target.free_joint, position, _quat_or_default(initial.quat)
                )
                self._forward()
                penetration, _ = self._penetration()
                if penetration <= 1e-2:
                    applied_delta = candidate
                    clearance_lift = 0.0
                    break
        self._forward()
        return {
            "target": name,
            "mode": "translation",
            "direction": [round(float(v), 6) for v in direction],
            "requested_delta_m": round(delta, 4),
            "applied_delta_m": round(applied_delta, 4),
            "clearance_lift_m": round(clearance_lift, 4),
            "penetration_after_adjust_m": round(float(penetration), 6),
            "region_center": None if center is None else [round(float(v), 6) for v in center],
        }

    def _apply_yaw(self, name: str, spec: LevelSpec) -> dict[str, Any]:
        target = self.targets[name]
        initial = self._initial[name]
        if initial.position is None:
            return {"target": name, "mode": "yaw", "error": "no initial position"}
        quat = quat_mul(quat_yaw(float(spec.yaw_rad or 0.0)), _quat_or_default(initial.quat))
        _set_free_qpos(self.sim, target.free_joint, initial.position, quat)
        return {
            "target": name,
            "mode": "yaw",
            "yaw_deg": round(math.degrees(float(spec.yaw_rad or 0.0)), 3),
            "quat": [round(float(v), 6) for v in quat_normalize(quat)],
        }

    def _apply_joint_ratio(self, name: str, spec: LevelSpec) -> dict[str, Any]:
        target = self.targets[name]
        initial = self._initial[name]
        active = self._active_joint(name)
        if active is None:
            return {"target": name, "mode": "joint_ratio", "error": "no articulated joint"}
        # Reset every changed joint of the object to its initial value first.
        for joint_id in target.joint_ids:
            _set_joint_qpos(
                self.sim,
                joint_id,
                initial.joint_qpos.get(joint_id, _joint_qpos(self.sim, joint_id)),
            )
        self._forward()
        q_init = _joint_qpos(self.sim, active)
        # Recover the injected joint value from the last snapshot.
        injected = self._pre_injection_joint(name, active)
        ratio = float(spec.joint_ratio if spec.joint_ratio is not None else 0.25)
        span = injected - q_init
        applied = ratio
        target_q = q_init + ratio * span
        _set_joint_qpos(self.sim, active, target_q)
        self._forward()
        for _ in range(7):
            if not all(self.revoked_truth()):
                break
            applied *= 0.5
            target_q = q_init + applied * span
            _set_joint_qpos(self.sim, active, target_q)
            self._forward()
        low, high = _joint_range(self.model, active) or (
            min(q_init, injected),
            max(q_init, injected),
        )
        return {
            "target": name,
            "mode": "joint_ratio",
            "joint": str(self.model.joint_names[active]),
            "requested_ratio": round(ratio, 4),
            "applied_ratio": round(applied, 4),
            "q_init": round(q_init, 6),
            "q_injected": round(injected, 6),
            "q_applied": round(target_q, 6),
            "joint_range": [round(low, 6), round(high, 6)],
        }

    def _pre_injection_joint(self, name: str, joint_id: int) -> float:
        # ``_capture_target`` already stored the initial joint qpos; the value at
        # injection time is recovered from the environment before we reset it.
        # ``inject()`` calls this after the reset, so keep a copy on the injector.
        cached = getattr(self, "_injection_joint_qpos", None)
        if cached is not None and name in cached and joint_id in cached[name]:
            return cached[name][joint_id]
        return _joint_qpos(self.sim, joint_id)

    # -- geometry / validity ---------------------------------------------

    def _pre_goal_state(self) -> list[dict[str, Any]]:
        """Goal objects that must stay true while a precondition is revoked."""

        state: list[dict[str, Any]] = []
        for atom in self.goal_atoms:
            tokens = [str(token) for token in atom]
            if len(tokens) < 3:
                continue
            predicate = tokens[0].lower()
            if predicate not in {"in", "on", "open", "close"}:
                continue
            object_name, region_name = tokens[1], tokens[2]
            body_id = _find_body_id(self.model, object_name)
            if body_id is None:
                continue
            free_joint = _free_joint(self.model, body_id)
            if free_joint is None:
                continue
            position, quat = _free_qpos(self.sim, free_joint)
            state.append(
                {
                    "free_joint": free_joint,
                    "position": position,
                    "quat": quat,
                    "region": region_name,
                    "region_center": self._region_center(region_name),
                }
            )
        return state

    def _carry_pre_goal_objects(self, state: Sequence[Mapping[str, Any]]) -> None:
        for item in state:
            region_after = self._region_center(str(item["region"]))
            delta = region_after - np.asarray(item["region_center"], dtype=np.float64)
            position = np.asarray(item["position"], dtype=np.float64) + delta
            _set_free_qpos(
                self.sim,
                int(item["free_joint"]),
                position,
                _quat_or_default(item["quat"]),
            )
        self._forward()

    def _region_for(self, name: str) -> str | None:
        for tokens in self.revoked_atoms:
            text = " ".join(str(token) for token in tokens[1:]).lower()
            if name.lower() in text and ("region" in text or len(tokens) > 2):
                return self._region_token(tokens)
        return None

    def _geometry(
        self,
        before: Mapping[str, Mapping[str, Any]],
        after: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        per_target: list[dict[str, Any]] = []
        max_translation = 0.0
        max_angle = 0.0
        max_joint = 0.0
        axis: list[float] = [0.0, 0.0, 1.0]
        for name in before:
            old = before[name]
            new = after[name]
            item: dict[str, Any] = {"target": name, "kind": new["kind"]}
            if old.get("position") is not None and new.get("position") is not None:
                old_pos = np.asarray(old["position"], dtype=np.float64)
                new_pos = np.asarray(new["position"], dtype=np.float64)
                translation = float(np.linalg.norm(new_pos - old_pos))
                angle = (
                    quat_angle(old["quat"], new["quat"]) if old.get("quat") else 0.0
                )
                if old.get("quat") and new.get("quat"):
                    inverse = [
                        old["quat"][0],
                        -old["quat"][1],
                        -old["quat"][2],
                        -old["quat"][3],
                    ]
                    rot_axis, _ = quat_to_axis_angle(quat_mul(new["quat"], inverse))
                else:
                    rot_axis = np.asarray([0, 0, 1.0])
                item.update(
                    {
                        "translation_m": round(translation, 5),
                        "angle_rad": round(angle, 5),
                        "axis": [round(float(v), 4) for v in rot_axis],
                        "from": [round(float(v), 5) for v in old_pos],
                        "to": [round(float(v), 5) for v in new_pos],
                    }
                )
                max_translation = max(max_translation, translation)
                if angle > max_angle:
                    max_angle, axis = angle, [round(float(v), 4) for v in rot_axis]
            elif old.get("joint_qpos") and new.get("joint_qpos"):
                deltas = {
                    str(joint_id): round(
                        float(new["joint_qpos"][joint_id])
                        - float(old["joint_qpos"].get(joint_id, 0.0)),
                        6,
                    )
                    for joint_id in new["joint_qpos"]
                }
                magnitude = max((abs(v) for v in deltas.values()), default=0.0)
                item.update({"joint_delta": deltas, "joint_delta_max": round(magnitude, 6)})
                max_joint = max(max_joint, magnitude)
            per_target.append(item)
        return {
            "per_target": per_target,
            "delta_translation_m": round(max_translation, 5),
            "delta_angle_rad": round(max_angle, 5),
            "delta_joint_max": round(max_joint, 5),
            "axis": axis,
        }

    def _max_target_velocity(self) -> float:
        maximum = 0.0
        for target in self.targets.values():
            if target.kind == "free" and target.free_joint is not None:
                dof = int(self.model.jnt_dofadr[target.free_joint])
                maximum = max(
                    maximum, float(np.max(np.abs(self.sim.data.qvel[dof : dof + 6])))
                )
            else:
                for joint_id in target.joint_ids:
                    dof = int(self.model.jnt_dofadr[joint_id])
                    if dof >= 0:
                        maximum = max(maximum, abs(float(self.sim.data.qvel[dof])))
        return maximum

    def _penetration(self) -> tuple[float, list[str]]:
        bodies: set[int] = set()
        for target in self.targets.values():
            if target.body_id is not None:
                bodies |= _body_subtree(self.model, target.body_id)
        if not bodies:
            return 0.0, []
        worst = 0.0
        names: set[str] = set()
        robot_prefixes = ("gripper", "robot", "panda", "mount", "rethink")
        for index in range(int(self.sim.data.ncon)):
            contact = self.sim.data.contact[index]
            body1 = int(self.model.geom_bodyid[contact.geom1])
            body2 = int(self.model.geom_bodyid[contact.geom2])
            if body1 not in bodies and body2 not in bodies:
                continue
            name1 = str(self.model.body_names[body1]).lower()
            name2 = str(self.model.body_names[body2]).lower()
            # ``no_object_penetration`` targets scene/object interpenetration.
            # A gripper finger resting on the manipulated fixture (e.g. the
            # stove knob at all_done) is robot contact, not object penetration.
            if any(name1.startswith(prefix) for prefix in robot_prefixes):
                continue
            if any(name2.startswith(prefix) for prefix in robot_prefixes):
                continue
            depth = -float(contact.dist)
            if depth > worst:
                worst = depth
                names = {name1, name2}
        return max(0.0, worst), sorted(names)

    def _object_released(self, gripper_qpos: Sequence[float] | None = None) -> bool:
        if gripper_qpos is None:
            return True
        values = np.asarray(gripper_qpos, dtype=np.float64).ravel()
        return bool(values.size >= 2 and float(np.max(values) - np.min(values)) > 0.01)

    def _restorable_probe(
        self,
        before: Mapping[str, Mapping[str, Any]],
        after: Mapping[str, TargetSnapshot],
    ) -> tuple[bool, dict[str, Any]]:
        injected = {
            name: TargetSnapshot(
                **{**snap.__dict__, "joint_qpos": dict(snap.joint_qpos)}
            )
            for name, snap in after.items()
        }
        # Restore every revoked target to its pre-injection snapshot, check the
        # native relation, then put the injected state back.
        probes: dict[str, Any] = {}
        for name, old in before.items():
            snapshot = TargetSnapshot(
                name=name,
                body_id=self.targets[name].body_id,
                kind=str(old["kind"]),
                position=(
                    None
                    if old.get("position") is None
                    else np.asarray(old["position"], dtype=np.float64)
                ),
                quat=(
                    None
                    if old.get("quat") is None
                    else np.asarray(old["quat"], dtype=np.float64)
                ),
                joint_qpos={
                    int(k): float(v) for k, v in (old.get("joint_qpos") or {}).items()
                },
            )
            self._apply_snapshot(snapshot)
        self._forward()
        restored_truth = self.revoked_truth()
        ok = all(restored_truth)
        probes["restored_truth"] = restored_truth
        probes["relation_true_after_state_write"] = ok
        self.restore(injected)
        self._forward()
        probes["reapplied_truth"] = self.revoked_truth()
        return ok, probes

    def _forward(self) -> None:
        self.sim.forward()

    # -- injection-time cache --------------------------------------------

    def cache_injection_joint_qpos(self) -> None:
        """Remember the joint values at injection *before* the first L0 reset."""

        self._injection_joint_qpos = {
            name: {
                joint_id: _joint_qpos(self.sim, joint_id)
                for joint_id in target.joint_ids
            }
            for name, target in self.targets.items()
        }


def make_injector(
    env, case: BCase, goal_atoms: Sequence[Sequence[Any]]
) -> BInjector:
    """Create the injector for one case (thin factory kept for the runner)."""

    return BInjector(env, case, goal_atoms)
