"""Optional bridge to an external LIBERO/MuJoCo evaluator.

The core package deliberately does not import MuJoCo, Torch, LIBERO, or an
adapter SDK.  This module only prepares a case-specific binding and starts an
already-installed evaluator in a caller-selected Python environment.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .evidence import classify_result
from .validation import load_yaml, validate_case_data


class RuntimeBridgeError(ValueError):
    """Raised when an external runtime invocation cannot be prepared."""


@lru_cache(maxsize=10)
def _profile_snapshot(index: int) -> Mapping[str, Any]:
    path = Path(__file__).resolve().parents[2] / (
        f"dataset/runtime-profiles/libero_10_t{index}.yaml"
    )
    return load_yaml(path)["task_profile"]


def _target_selector(case: Mapping[str, Any]) -> str | None:
    target = case["rollback_target"]
    selector = target.get("target_subgoal")
    if selector is not None:
        return selector
    actor = target.get("actor")
    if not actor or actor == "selected_relation_actor":
        return None  # Declared runtime selection: first in actual completion order.
    if target["state_change"]["kind"] == "revert_articulation_goal":
        return None
    profile = _profile_snapshot(source_task_index(case))
    matches = [
        goal
        for goal in profile["subgoals"]
        if profile["roles"][goal["actor_role"]]["name"] == actor
    ]
    if len(matches) != 1:
        raise RuntimeBridgeError(f"declared actor {actor!r} has no unique profile subgoal")
    goal = matches[0]
    expected = [
        goal["predicate"],
        actor,
        goal.get("goal_state_name", profile["roles"][goal["goal_role"]]["name"]),
    ]
    if "predicate" in target and re.findall(r"[^()\s]+", target["predicate"].lower()) != [
        str(x).lower() for x in expected
    ]:
        raise RuntimeBridgeError("declared target predicate differs from profile subgoal")
    return goal["id"]


def check_runtime_capabilities(case: Mapping[str, Any], runtime_root: Path) -> None:
    """Reject extension cases before loading a model in an incompatible runtime."""
    required = set()
    change = case["rollback_target"]["state_change"]
    if change["kind"] in {
        "displace_from_completed_pose",
        "move_to_relation_target",
        "displace_reference_object",
        "translate_relation_pair",
    }:
        required.add("completed_pose")
    if change["kind"] == "displace_to_relation_boundary":
        required.add("native_boundary")
    if change["kind"] == "restore_native_relation_set":
        required.add("atomic_relation_set")
    if "functional_boundary" in change:
        required.add("functional_boundary")
    if case.get("transient", {}).get("gate") == "relation_recovered":
        required.add("recovery_gate")
    if case.get("trigger", {}).get("time_point") == "all_done":
        required.add("completion_precondition")
    if change["kind"] == "revert_articulation_goal" and case["trigger"].get("delay_steps"):
        required.add("articulation_delay")
    if not required:
        return
    path = runtime_root / "rollback-capabilities.json"
    available = (
        set(json.loads(path.read_text()).get("capabilities", [])) if path.exists() else set()
    )
    if missing := required - available:
        raise RuntimeBridgeError(
            f"external evaluator lacks capabilities {sorted(missing)}; "
            "prepare an isolated runtime with scripts/prepare_validation_runtime.py"
        )
    if case.get("trigger", {}).get("time_point") == "all_done":
        profile_path = (
            runtime_root / "configs/task_profiles" / f"libero_10_t{source_task_index(case)}.yaml"
        )
        milestone = case["trigger"]["event"].removeprefix("enter_")
        if not profile_path.is_file() or milestone not in load_yaml(profile_path).get(
            "task_profile", {}
        ).get("milestones", {}):
            raise RuntimeBridgeError(
                f"external task profile does not enable completion milestone {milestone!r}"
            )


def runtime_capabilities(runtime_root: Path) -> set[str]:
    """Capabilities advertised by an isolated evaluator overlay."""

    path = runtime_root / "rollback-capabilities.json"
    if not path.is_file():
        return set()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    capabilities = document.get("capabilities", [])
    if not isinstance(capabilities, list):
        return set()
    return {str(item) for item in capabilities}


# Historical label -> runtime severity variant, kept for the 1.0.0/1.1.0 cases.
_SEVERITY_VARIANTS = {
    "d0": "l1_t0",
    "d1": "l1_small_diagonal",
    "d2": "l2_side_diagonal",
    "d3": "l2_large_diagonal",
    "checkpoint": "l2_pregrasp_checkpoint",
}

# Position/mechanism label -> base runtime variant used by the 1.2.0 grid release.
# The time point is appended so one template can declare every combination.
_GRID_VARIANTS = {
    "d0": ("l1", "t0"),
    "p3": ("l2", "p3"),
    "p5": ("l2", "p5"),
    "p8": ("l2", "p8"),
    "p10": ("l2", "p10"),
    "n3": ("l2", "n3"),
    "n5": ("l2", "n5"),
    "n8": ("l2", "n8"),
    "checkpoint": ("l1", "pregrasp"),
    "above": ("l2", "above"),
    "articulation": ("l3", "articulation"),
    "r05": ("l2", "r05"),
    # a pose-only change keeps the position, so it reuses the t0 support-surface label
    "pose": ("l2", "pose"),
    "boundary": ("l2", "pose"),
    # a reference-object move keeps the revoked object in place, so it also reuses the t0
    # support-surface label and carries its translation in `translation_m`
    "reference": ("l2", "reference"),
    "holding": ("l2", "holding"),
}

_DESTINATIONS = {
    "restore_episode_initial_pose": "initial_pose",
    "apply_episode_initial_offset": "initial_offset",
    "restore_captured_checkpoint_pose": "checkpoint",
    "restore_container_above_pose": "container_above",
    "revert_articulation_goal": "articulation",
    # The reference-object group needs a destination the handler recognises for a free
    # body whose pose comes from the measured pre-state, so it reuses `initial_offset`
    # with a zero offset; the actual translation is carried by `reference_object`.
    "displace_reference_object": "completed_offset",
    "displace_from_completed_pose": "completed_offset",
    "move_to_relation_target": "relation_target",
    "displace_to_relation_boundary": "relation_boundary",
    "translate_relation_pair": "completed_offset",
    "restore_native_relation_set": "initial_pose",
}

_TIME_POINT_BY_EVENT = {
    "enter_first_subgoal_completed": "early",
    "enter_post_completion_retreat": "mid",
    "enter_next_subgoal_approach": "mid",
    "enter_x3a_actuation": "later",
    "enter_x3a_transport": "later",
    "enter_next_subgoal_lift": "later",
    "enter_next_subgoal_completed": "after",
    "enter_articulation_completed": "after",
}


# Motion envelope for the articulation-setback handler; mirrors the delivered
# `libero_10_t33_x3b_articulation_setback` template values.
# Calibrated for centimetre-scale reopening. Measured on task 01 (T33 drawer,
# slide joint, target 0.060 m): a 40 N envelope reached only 0.0205 m while the
# joint reacted at 182.2 N; a 300 N envelope reached 0.0614 m but tripped the
# step-change gate; 600 N at 0.60 m/s with 60 monitor steps reached the target
# exactly with zero position error and a valid injection.
_ARTICULATION_DRIVE = {
    "linear_velocity_m_s": 0.60,
    "angular_velocity_rad_s": 1.20,
    "linear_force_limit_n": 600.0,
    "angular_torque_limit_nm": 60.0,
    "monitor_steps_after_completion": 60,
}

# The stove knob (t0) is driven by a separate, gentle envelope. The delivered T270
# stove template drives at 0.6 rad/s / 40 N, and the validator rejects large per-step
# body movement above 0.08 m, which the 600 N drawer envelope trips immediately.
_STOVE_DRIVE = {
    "linear_velocity_m_s": 0.08,
    "angular_velocity_rad_s": 0.50,
    "linear_force_limit_n": 40.0,
    "angular_torque_limit_nm": 8.0,
    "monitor_steps_after_completion": 60,
}


def _articulation_drive(case: Mapping[str, Any]) -> dict[str, Any]:
    """Return the drive envelope appropriate to this case's joint.

    A stove knob turns nearly half a radian of range and barely resists, whereas a
    drawer needs high force to overcome its closing action, so one shared envelope
    would either stall the drawer or slam the knob past the step-change gate.
    """

    profile = str(case.get("task", {}).get("source_task_locator") or "")
    if profile.upper() == "T0":
        return dict(_STOVE_DRIVE)
    return dict(_ARTICULATION_DRIVE)


# Setback magnitudes and their runtime variant labels, calibrated against the
# engine: the sliding drawer (T33) reaches 0.02/0.06/0.10 m with the 600 N envelope,
# while the hinged door (T78) is only supported in the 0.02-0.07 rad band.
_ARTICULATION_SETBACK_LABELS = (
    # 1.3.0 vocabulary: the drawer reaches these with the calibrated envelope and the
    # door stays inside the band the engine supports.
    (0.02, "s02"),
    (0.03, "s03"),
    (0.05, "s05"),
    (0.06, "s06"),
    (0.10, "s10"),
    (0.02, "h02"),
    (0.04, "h04"),
    (0.07, "h07"),
    # Legacy 1.2.0 magnitudes. They remain bindable so the superseded release stays
    # validatable and testable, but measurement showed they cannot be driven to
    # target (0.12 m trips the per-step gate; the door overshoots into penetration).
    # stove knob (hinge, range [-0.005, 2.1] rad): a near-half-range setback is needed
    # to revoke `(Turnon flat_stove_1)`, so it is labelled separately from drawer/door.
    (1.0, "k10"),
    # Position grid around the near-half-range value: 0.5 rad stays above the
    # Turnon threshold (control), 1.5 rad closes deeper than the revoking 1.0 rad.
    (0.5, "k05"),
    (1.5, "k15"),
    # stove knob (hinge, range [-0.005, 2.1] rad): a near-half-range setback is needed
    # to revoke `(Turnon flat_stove_1)`, so it is labelled separately from drawer/door.
    (1.0, "k10"),
    (0.12, "s12"),
    (0.10, "h10"),
    (0.30, "h30"),
    (0.60, "h60"),
)


def _articulation_variant(case: Mapping[str, Any], event: str) -> str:
    """Return the template severity variant holding this joint setback."""

    time_point = _TIME_POINT_BY_EVENT.get(event)
    if time_point is None:
        raise RuntimeBridgeError(f"no runtime time point mapping for trigger event {event!r}")
    state_change = case["rollback_target"]["state_change"]
    setback = float(state_change["setback"])
    for value, label in _ARTICULATION_SETBACK_LABELS:
        if abs(value - setback) < 1e-9:
            return f"l3_grid_art_{label}_{time_point}"
    raise RuntimeBridgeError(f"no runtime variant for joint setback {setback}")


def _grid_variant(severity: str, event: str) -> str:
    """Return the runtime severity variant for a 1.2.0 grid case."""

    try:
        level, base = _GRID_VARIANTS[severity]
    except KeyError as exc:
        # keep the historical wording for labels belonging to neither scheme
        raise RuntimeBridgeError(f"no external runtime severity mapping for {severity!r}") from exc
    time_point = _TIME_POINT_BY_EVENT.get(event)
    if time_point is None:
        raise RuntimeBridgeError(f"no runtime time point mapping for trigger event {event!r}")
    return f"{level}_grid_{base}_{time_point}"


def load_case_for_runtime(case_path: Path) -> dict[str, Any]:
    """Load and statically validate one case before starting a simulator."""

    case = load_yaml(case_path)
    errors = validate_case_data(case)
    if errors:
        raise RuntimeBridgeError(
            f"case is invalid and cannot be executed ({case_path}):\n" + "\n".join(errors)
        )
    if not isinstance(case, dict):
        raise RuntimeBridgeError(f"case root must be a mapping: {case_path}")
    return case


def source_task_index(case: Mapping[str, Any]) -> int:
    """Return the historical LIBERO task index used by the runtime profiles."""

    locator = case.get("task", {}).get("source_task_locator")
    match = re.fullmatch(r"T([0-9]+)", str(locator or ""))
    if match is None:
        raise RuntimeBridgeError(
            f"task.source_task_locator must be a runtime locator such as T33; got {locator!r}"
        )
    return int(match.group(1))


def _axis_angle_to_quaternion(axis: Sequence[float], angle_rad: float) -> list[float]:
    """Convert an axis-angle rotation into a (w, x, y, z) quaternion.

    Case authors describe a pose change as "rotate about this axis by this angle"; the
    handler wants a quaternion, so the conversion happens here rather than in every case.
    """

    norm = math.sqrt(sum(float(component) ** 2 for component in axis))
    if norm <= 0.0:
        raise RuntimeBridgeError("orientation axis must be non-zero")
    half = float(angle_rad) / 2.0
    scale = math.sin(half) / norm
    return [math.cos(half)] + [float(component) * scale for component in axis]


def _reference_object_parameters(state_change: Mapping[str, Any], kind: str) -> dict[str, Any]:
    """Resolve the reference-object payload for the two paired mechanisms.

    `translation_m` is always expressed in the world frame so the paired control can apply
    the identical vector to both entities; another frame is rejected rather than silently
    reinterpreted, because the two ends must move by the same world vector to cancel out.
    """

    role = state_change.get("reference_role")
    if not isinstance(role, str) or not role.strip():
        raise RuntimeBridgeError("a reference-object rollback requires reference_role")
    if role.strip().startswith("robot"):
        raise RuntimeBridgeError("the robot cannot be a reference object")
    translation = state_change.get("translation_m")
    if not isinstance(translation, (list, tuple)) or len(translation) != 3:
        raise RuntimeBridgeError("translation_m must contain three numeric values")
    if not all(
        isinstance(component, (int, float)) and not isinstance(component, bool)
        for component in translation
    ):
        raise RuntimeBridgeError("translation_m must contain three numeric values")
    frame = state_change.get("offset_frame", state_change.get("coordinate_frame", "world"))
    if str(frame) != "world":
        raise RuntimeBridgeError(
            "a reference-object translation must be declared in the world frame"
        )
    vector = [float(component) for component in translation]
    magnitude = math.sqrt(sum(component * component for component in vector))
    if magnitude <= 0.0:
        raise RuntimeBridgeError("translation_m must be non-zero")
    if magnitude > 0.30:
        raise RuntimeBridgeError("translation_m must not exceed 0.30 m")
    paired = kind == "translate_relation_pair"
    return {
        # the revoked object stays put unless the paired control moves both ends
        "offset_m": vector if paired else [0.0, 0.0, 0.0],
        "offset_frame": "world",
        "reference_object": {
            "reference_role": role.strip(),
            "translation_m": vector,
            "reference_frame": "world",
            "translate_revoked_object": paired,
        },
    }


def _orientation_parameter(state_change: Mapping[str, Any]) -> list[float] | None:
    """Resolve the declared pose delta into the handler's quaternion parameter."""

    explicit = state_change.get("orientation_delta_wxyz")
    if explicit is not None:
        if not isinstance(explicit, (list, tuple)) or len(explicit) != 4:
            raise RuntimeBridgeError("orientation_delta_wxyz must be a four-element sequence")
        return [float(value) for value in explicit]
    axis_angle = state_change.get("orientation_axis_angle")
    if axis_angle is None:
        return None
    if not isinstance(axis_angle, Mapping):
        raise RuntimeBridgeError("orientation_axis_angle must be a mapping")
    axis = axis_angle.get("axis")
    angle = axis_angle.get("angle_rad")
    if not isinstance(axis, (list, tuple)) or len(axis) != 3:
        raise RuntimeBridgeError("orientation_axis_angle.axis must have three components")
    if not isinstance(angle, (int, float)) or isinstance(angle, bool):
        raise RuntimeBridgeError("orientation_axis_angle.angle_rad must be numeric")
    return _axis_angle_to_quaternion(axis, float(angle))


def _state_parameters(case: Mapping[str, Any]) -> dict[str, Any]:
    rollback = case.get("rollback_target")
    state_change = rollback.get("state_change") if isinstance(rollback, Mapping) else None
    if not isinstance(state_change, Mapping):
        raise RuntimeBridgeError("rollback_target.state_change must be a mapping")
    kind = state_change.get("kind")
    try:
        destination = _DESTINATIONS[str(kind)]
    except KeyError as exc:
        raise RuntimeBridgeError(
            f"no external runtime mapping for state_change.kind={kind!r}"
        ) from exc
    parameters: dict[str, Any] = {
        "destination": destination,
        "zero_velocity": state_change.get("velocity") == "zero",
    }
    if kind == "displace_from_completed_pose":
        # A completion-pose change may combine a vertical lift with a rotation: the lift
        # gives a tilt room to clear the container walls while the object stays inside the
        # goal region, so the native relation is still expected to hold.
        lift = state_change.get("lift_m")
        if lift is not None:
            if not isinstance(lift, (int, float)) or isinstance(lift, bool):
                raise RuntimeBridgeError("lift_m must be numeric")
            lift = float(lift)
            if not 0.0 <= lift <= 0.30:
                raise RuntimeBridgeError("lift_m must be within [0.0, 0.30]")
            base = state_change.get("offset_m") or [0.0, 0.0, 0.0]
            if not isinstance(base, (list, tuple)) or len(base) != 3:
                raise RuntimeBridgeError("offset_m must contain three numeric values")
            parameters["offset_m"] = [float(base[0]), float(base[1]), float(base[2]) + lift]
            parameters["offset_frame"] = "world"
            parameters["lift_m"] = lift
    if kind == "move_to_relation_target":
        # Move the rolled-back object to the goal pose of a relation that is already declared
        # by the task (the pan onto the stove region, the mug onto the sibling plate, ...).
        # The pose is resolved in the runtime from the live goal geometry; the case only names
        # the relation, so it stays episode independent.
        relation = state_change.get("source_relation")
        if not isinstance(relation, str) or not relation.strip():
            raise RuntimeBridgeError("source_relation must be a non-empty relation string")
        parameters["target_relation"] = relation.strip()
        offset = state_change.get("height_offset_m")
        if offset is not None:
            if not isinstance(offset, (int, float)) or isinstance(offset, bool):
                raise RuntimeBridgeError("height_offset_m must be numeric")
            offset = float(offset)
            if not 0.0 <= offset <= 0.30:
                raise RuntimeBridgeError("height_offset_m must be within [0.0, 0.30]")
            parameters["height_offset_m"] = offset
        geometry = state_change.get("orientation")
        parameters["orientation_mode"] = "upright" if geometry == "upright" else "preserve"
    if kind in {"displace_reference_object", "translate_relation_pair"}:
        parameters.update(_reference_object_parameters(state_change, kind))
        reference = parameters["reference_object"]
        declared = reference["reference_role"]
        roles = _profile_snapshot(source_task_index(case))["roles"]
        if declared not in roles:
            # Older definitions use a body name; newer definitions use a role.
            # Resolve by exact identity, never by proximity or actor order.
            aliases = sorted(
                role for role, value in roles.items()
                if value.get("kind") == "body" and value.get("name") == declared
            )
            if not aliases:
                raise RuntimeBridgeError(f"reference {declared!r} has no profile body role")
            reference["reference_role"] = "goal_object" if "goal_object" in aliases else aliases[0]
        elif roles[declared].get("kind") != "body":
            raise RuntimeBridgeError(f"reference {declared!r} is not a profile body role")
    elif kind == "restore_native_relation_set":
        parameters["relation_set"] = list(state_change["relations"])
    elif destination in {"initial_offset", "completed_offset"}:
        offset = state_change.get("offset_m")
        if not isinstance(offset, list) or len(offset) != 3:
            raise RuntimeBridgeError("initial offset must contain three numeric values")
        parameters["offset_m"] = [float(value) for value in offset]
        # The dataset writes `offset_frame`; `coordinate_frame` is the legacy spelling.
        declared_frame = state_change.get(
            "offset_frame", state_change.get("coordinate_frame", "task_frame")
        )
        parameters["offset_frame"] = str(declared_frame).replace(
            "task_frame_longitudinal_lateral_vertical", "task_frame"
        )
    elif destination == "initial_pose":
        # A recorded episode-initial pose is not a collision query: the object can come to
        # rest a few millimetres below where it was sampled (the can in T04/T05 was written
        # 15.4 mm inside the table under a 5 mm penetration budget, so the runtime refused
        # the injection).  Ask the handler to lift the target along +Z in 2 mm steps, within
        # a bounded budget, until the penetration check passes; the applied lift is recorded
        # in the case evidence, so a "no_object_penetration" case stays honest.
        # Bounded +Z clearance budget.  The search returns at the LOWEST lift that meets the
        # penetration budget, so raising the cap cannot change any case that already succeeds;
        # it only lets poses that exhausted the old 50 mm cap (enclosed drawer, basket walls)
        # keep searching for a legal destination.
        parameters["target_lift_max_m"] = float(
            state_change.get("target_lift_max_m", 0.05)
        )
        parameters["target_lift_step_m"] = float(
            state_change.get("target_lift_step_m", 0.002)
        )
    elif destination == "relation_boundary":
        parameters["boundary"] = dict(state_change["boundary"])
    elif destination == "checkpoint":
        parameters["checkpoint"] = state_change.get("checkpoint")
    elif destination == "container_above":
        clearance = state_change.get("clearance_m")
        if not isinstance(clearance, (int, float)) or isinstance(clearance, bool):
            raise RuntimeBridgeError("container_above requires a numeric clearance_m")
        parameters["clearance_m"] = float(clearance)
        if isinstance(state_change.get("clearance_max_m"), (int, float)):
            parameters["clearance_max_m"] = float(state_change["clearance_max_m"])
        if state_change.get("above_container_top") is True:
            parameters["above_container_top"] = True
        if isinstance(state_change.get("edge_slide_m"), (int, float)):
            parameters["edge_slide_m"] = float(state_change["edge_slide_m"])
        if isinstance(state_change.get("clearance_step_m"), (int, float)):
            parameters["clearance_step_m"] = float(state_change["clearance_step_m"])
        if isinstance(state_change.get("min_robot_clearance_m"), (int, float)):
            parameters["min_robot_clearance_m"] = float(state_change["min_robot_clearance_m"])
    elif destination == "articulation":
        # `articulation_setback` requires its parameter set to equal its own
        # whitelist exactly, so nothing may be merged on top of it. The joint
        # setback magnitude lives in the template severity variant that
        # `_articulation_variant` selects, not in the intervention parameters.
        setback = state_change.get("setback")
        if not isinstance(setback, (int, float)) or isinstance(setback, bool):
            raise RuntimeBridgeError("articulation rollback requires a numeric setback")
        parameters.update(_articulation_drive(case))
        if "functional_boundary" in state_change:
            parameters["functional_boundary"] = dict(state_change["functional_boundary"])
            parameters["position_tolerance"] = state_change["position_tolerance"]
    if str(case.get("expected_evaluation_semantics", "")) == "relation_only":
        # A truth probe measures the relation instead of demanding its invalidation; the
        # runtime expresses that as `expected_post_predicate: measure`.
        parameters["expected_post_predicate"] = "measure"
    pose_delta = _orientation_parameter(state_change)
    if pose_delta is not None:
        if destination == "articulation":
            raise RuntimeBridgeError("an articulation setback has no orientation to change")
        parameters["orientation_delta_wxyz"] = pose_delta
    # `trigger.delay_steps` defers the injection by N control steps after the event.
    # The handler accepts delay_steps in [0, 10].
    delay = case.get("trigger", {}).get("delay_steps")
    if isinstance(delay, int) and not isinstance(delay, bool) and delay > 0:
        if delay > 10:
            raise RuntimeBridgeError(f"trigger.delay_steps must be within [0, 10], got {delay}")
        parameters["delay_steps"] = delay
    parameters["expected_post_predicate"] = (
        "measure"
        if state_change.get("orientation_axis_angle")
        and case.get("expected_evaluation_semantics") == "relation_only"
        else case.get("expected_evaluation_semantics") == "relation_holds_control"
    )
    if destination == "articulation":
        parameters.pop("expected_post_predicate")
    elif (
        case.get("stage", {}).get("name") == "completion_boundary"
        or case.get("trigger", {}).get("time_point") == "all_done"
    ):
        parameters["require_task_complete"] = True
    selector = _target_selector(case)
    if selector is not None:
        parameters["target_subgoal"] = selector
    transient = case.get("transient")
    if isinstance(transient, Mapping):
        if destination == "articulation":
            raise RuntimeBridgeError(
                "articulation rollback cannot carry a transient payload: the "
                "handler validates its parameter set by exact equality"
            )
        parameters["transient_pose"] = _transient_pose(transient)
    return parameters


def _transient_pose(transient: Mapping[str, Any]) -> dict[str, Any]:
    """Translate the dataset ``transient`` block into the handler parameter."""

    destination = str(transient.get("destination"))
    if destination not in {"pre_injection", "initial_offset"}:
        raise RuntimeBridgeError(
            f"transient.destination must be pre_injection or initial_offset, got {destination!r}"
        )
    payload: dict[str, Any] = {
        "after_steps": int(transient["after_steps"]),
        "destination": destination,
    }
    for key in ("gate", "hold_steps"):
        if key in transient:
            payload[key] = transient[key]
    if destination == "initial_offset":
        offset = transient.get("offset_m")
        if not isinstance(offset, list) or len(offset) != 3:
            raise RuntimeBridgeError("transient initial_offset must contain three values")
        payload["offset_m"] = tuple(float(value) for value in offset)
        payload["offset_frame"] = str(transient.get("offset_frame", "task_frame"))
    return payload


def runtime_binding(
    case: Mapping[str, Any], *, severity: str | None = None, dimension: str = "rollback"
) -> dict[str, Any]:
    """Translate a dataset case into the runtime's declarative binding format.

    The generated document is intentionally ephemeral.  Its case name is not
    exposed as a dataset identifier; normalized results retain the original
    ``case_id`` as the foreign key.
    """

    task = case.get("task")
    if not isinstance(task, Mapping):
        raise RuntimeBridgeError("case.task must be a mapping")
    source_index = source_task_index(case)
    severity = str(severity or case.get("severity"))
    event = str(case["trigger"]["event"])
    if severity == "articulation":
        variant = _articulation_variant(case, event)
    elif "time_point" in case.get("trigger", {}):
        # 1.2.0 grid cases always address a (destination, time point) variant.
        variant = _grid_variant(severity, event)
    elif severity in _SEVERITY_VARIANTS:
        variant = _SEVERITY_VARIANTS[severity]
    else:
        variant = _grid_variant(severity, event)
    # Placement rollback and articulation rollback are different handlers with
    # different validator signatures, so they bind to different templates.
    state_kind = case["rollback_target"]["state_change"]["kind"]
    is_articulation = state_kind == "revert_articulation_goal"
    template_id = (
        "hv_articulation_goal_rollback" if is_articulation else "hv_completed_subgoal_rollback_grid"
    )
    enabled_parameters = _state_parameters(case)
    if is_articulation:
        # The articulation handler validates its parameter set by exact equality.
        enabled_parameters = {
            key: value for key, value in enabled_parameters.items() if key != "destination"
        }
    case_name = "dataset_" + re.sub(r"[^a-z0-9]+", "_", str(case["case_id"]).lower()).strip("_")
    return {
        "perturbation_binding": {
            "task_profile": f"libero_10_t{source_index}",
            "enabled_cases": [
                {
                    "case_name": case_name,
                    "template": template_id,
                    "severities": [variant],
                    "trigger_event": event,
                    "parameters": enabled_parameters,
                    "description": str(case.get("intervention_description", "")),
                }
            ],
        }
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _find_runner_result(exp_dir: Path) -> tuple[Path | None, dict[str, Any] | None]:
    results_files = sorted(exp_dir.rglob("results.json"))
    if not results_files:
        return None, None
    result_path = results_files[-1]
    try:
        document = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return result_path, None
    return result_path, document


def _select_episode(
    document: Mapping[str, Any], seed: int
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Find the single perturbation and paired baseline produced by the runner."""

    perturbation = None
    baseline = None
    for task_data in document.values():
        if not isinstance(task_data, Mapping):
            continue
        results = task_data.get("results", {})
        if not isinstance(results, Mapping):
            continue
        for value in results.values():
            if not isinstance(value, Mapping):
                continue
            if value.get("kind") == "perturbation" and int(value.get("seed", seed)) == seed:
                perturbation = dict(value)
            elif value.get("kind") == "baseline" and int(value.get("seed", seed)) == seed:
                baseline = dict(value)
    return perturbation, baseline


def _normalize_result(
    case: Mapping[str, Any],
    *,
    seed: int,
    adapter: str,
    checkpoint: str | None,
    returncode: int,
    output_dir: Path,
    runner_result_path: Path | None,
    runner_document: Mapping[str, Any] | None,
    error: str | None = None,
    success_delay: int = 0,
    success_check_interval: int = 1,
) -> dict[str, Any]:
    perturbation, baseline = _select_episode(runner_document or {}, seed)
    report = perturbation.get("report") if perturbation else None
    if not isinstance(report, Mapping):
        report = {}
    trigger = report.get("trigger") if isinstance(report.get("trigger"), Mapping) else {}
    intervention = (
        report.get("intervention") if isinstance(report.get("intervention"), Mapping) else {}
    )
    state_mutation = report.get("state_mutation")
    if not isinstance(state_mutation, Mapping):
        state_mutation = intervention.get("state_mutation", {})
    observed = intervention.get("observed")
    if not isinstance(observed, Mapping):
        observed = {}
    pre_relation = observed.get("pre_predicate")
    post_relation = observed.get("post_predicate")
    if not isinstance(pre_relation, bool):
        pre_relation = None
    if not isinstance(post_relation, bool):
        post_relation = None
    applied = bool(report.get("rule_executed", False))
    injection_step = report.get("injection_step") if applied else None
    return {
        "schema_version": "libero-rollback.run-result.v1",
        "status": classify_result(case, perturbation),
        "dataset_version": case.get("dataset_version"),
        "case_id": case.get("case_id"),
        "task_id": case.get("task", {}).get("task_id"),
        "adapter": adapter,
        "model": adapter,
        "checkpoint": os.path.abspath(checkpoint) if checkpoint else None,
        "seed": seed,
        "environment": {
            "suite": "LIBERO-10",
            "source_task_locator": case.get("task", {}).get("source_task_locator"),
            "source_bddl": case.get("task", {}).get("source_bddl"),
        },
        "trigger_step": injection_step if injection_step is not None else trigger.get("step"),
        "intervention_step": injection_step,
        "trigger_reached": trigger.get("reached"),
        "state_change_applied": applied,
        "state_mutation": _json_safe(state_mutation),
        "pre_relation": pre_relation,
        "post_relation": post_relation,
        "episode_success": perturbation.get("success") if perturbation else None,
        "first_hit_success": (
            perturbation.get("first_hit_success") if perturbation else None
        ),
        "success_window": (
            _json_safe(perturbation.get("success_window")) if perturbation else None
        ),
        "success_delay": success_delay,
        "success_check_interval": success_check_interval,
        "baseline_success": baseline.get("success") if baseline else None,
        "injection_valid": report.get("injection_valid"),
        "runner_returncode": returncode,
        "runner_result_path": str(runner_result_path) if runner_result_path else None,
        "runner_output_dir": str(output_dir),
        "error": error,
        "raw_perturbation": _json_safe(perturbation),
    }


def run_case(
    case_path: Path,
    *,
    python_executable: Path,
    libero_root: Path,
    runtime_root: Path,
    adapter: str,
    checkpoint: Path | None,
    seed: int = 0,
    max_steps: int = 600,
    replan_steps: int = 10,
    success_delay: int = 0,
    success_check_interval: int = 1,
    output_root: Path | None = None,
    suite: str = "LIBERO_10",
    dimension: str = "rollback",
    severity: str | None = None,
    video: bool = False,
    mode: str = "both",
) -> dict[str, Any]:
    """Run one case through an external evaluator and persist an audit record."""

    case = load_case_for_runtime(case_path)
    # Keep venv interpreter symlinks intact; Path.resolve() may follow them to
    # the system Python and silently leave the evaluator environment.
    python_executable = Path(os.path.abspath(python_executable.expanduser()))
    libero_root = libero_root.expanduser().resolve()
    runtime_root = runtime_root.expanduser().resolve()
    check_runtime_capabilities(case, runtime_root)
    if checkpoint is not None:
        checkpoint = checkpoint.expanduser().resolve()
    if suite != "LIBERO_10":
        raise RuntimeBridgeError("this dataset release supports suite=LIBERO_10 only")
    if mode not in {"baseline", "perturbation", "both"}:
        raise RuntimeBridgeError("mode must be baseline, perturbation, or both")
    if dimension != "rollback":
        raise RuntimeBridgeError(
            "dataset v1 contains rollback cases only; dimension must be rollback"
        )
    for label, path in (
        ("python executable", python_executable),
        ("LIBERO root", libero_root),
        ("runtime root", runtime_root),
    ):
        if not path.exists():
            raise RuntimeBridgeError(f"{label} does not exist: {path}")
    cached_openpi = adapter in {"pi05", "pi05_lerobot", "pi0", "pi0_fast", "pi07"}
    if checkpoint is None and not cached_openpi:
        raise RuntimeBridgeError(
            f"--checkpoint is required for adapter {adapter!r}; cached OpenPI adapters may omit it"
        )
    if checkpoint is not None and not checkpoint.exists():
        raise RuntimeBridgeError(f"checkpoint does not exist: {checkpoint}")
    if not python_executable.is_file():
        raise RuntimeBridgeError(f"python executable is not a file: {python_executable}")
    runner = runtime_root / "tools" / "run_benchmark.py"
    if not runner.is_file():
        raise RuntimeBridgeError(f"runtime runner not found: {runner}")
    profile = (
        runtime_root / "configs" / "task_profiles" / f"libero_10_t{source_task_index(case)}.yaml"
    )
    if not profile.is_file():
        raise RuntimeBridgeError(f"runtime task profile not found: {profile}")
    post_success_window = (
        case.get("stage", {}).get("name") == "completion_boundary"
        or case.get("trigger", {}).get("time_point") == "all_done"
    )
    if success_delay > 0 and post_success_window:
        raise RuntimeBridgeError(
            "success_delay cannot be combined with the post-success observation "
            "window used by completion-boundary/all_done cases"
        )
    if success_delay > 0 and "success_window" not in runtime_capabilities(runtime_root):
        raise RuntimeBridgeError(
            "runtime overlay does not advertise 'success_window'; build one with "
            "`python scripts/prepare_success_delay_runtime.py --base <overlay> "
            "--output <overlay>`"
        )
    if max_steps <= 0 or replan_steps <= 0 or seed < 0:
        raise RuntimeBridgeError("seed must be non-negative and step limits must be positive")
    if success_delay < 0:
        raise RuntimeBridgeError("success_delay must be nonnegative")
    if success_check_interval < 1:
        raise RuntimeBridgeError("success_check_interval must be positive")
    if success_delay == 0 and success_check_interval != 1:
        raise RuntimeBridgeError("success_check_interval requires success_delay > 0")

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = output_root or Path("runs") / timestamp / str(case["case_id"])
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.rglob("results.json")) or (output_dir / "completion.json").exists():
        raise RuntimeBridgeError("output already contains evidence; choose a new output directory")
    binding_path = output_dir / "runtime-binding.yaml"
    binding_path.write_text(
        yaml.safe_dump(
            runtime_binding(case, severity=severity, dimension=dimension), sort_keys=False
        ),
        encoding="utf-8",
    )
    log_path = output_dir / "runner.log"
    env = os.environ.copy()
    python_path_entries = [str(libero_root), str(runtime_root)]
    if env.get("PYTHONPATH"):
        python_path_entries.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_path_entries)
    command = [
        str(python_executable),
        str(runner),
        "--model",
        adapter,
        "--mode",
        mode,
        "--suite",
        "LIBERO_10",
        "--task-idx",
        str(source_task_index(case)),
        "--binding",
        str(binding_path),
        "--dimension",
        dimension,
        "--seed-ids",
        str(seed),
        "--max-steps",
        str(max_steps),
        "--replan-steps",
        str(replan_steps),
        "--output",
        str(output_dir),
    ]
    if mode == "both":
        command.extend(["--strict-paired-baseline", "--require-successful-baseline"])
    if checkpoint is not None:
        command.extend(["--checkpoint", str(checkpoint)])
    if video:
        command.append("--video")
    if post_success_window:
        command.append("--post-success-window")
    if success_delay > 0:
        command.extend(["--success-delay", str(success_delay)])
        command.extend(["--success-check-interval", str(success_check_interval)])
    binding = yaml.safe_load(binding_path.read_text())
    (output_dir / "binding.yaml").write_text(yaml.safe_dump(binding, sort_keys=False))
    runtime_files = {
        str(path.relative_to(runtime_root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(runtime_root.rglob("*"))
        if path.is_file()
        and path.suffix in {".py", ".yaml", ".json", ".xml"}
        and "__pycache__" not in path.parts
    }
    runtime_digest = hashlib.sha256(json.dumps(runtime_files, sort_keys=True).encode()).hexdigest()
    plan = {
        "case_id": case["case_id"],
        "case_sha256": hashlib.sha256(case_path.read_bytes()).hexdigest(),
        "binding": binding,
        "runtime_sha256": runtime_digest,
        "command": command,
        "seed": seed,
        "max_steps": max_steps,
        "success_delay": success_delay,
        "success_check_interval": success_check_interval,
        "video": video,
        "mode": mode,
    }
    plan["fingerprint"] = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    (output_dir / "execution-plan.json").write_text(json.dumps(plan, indent=2))
    (output_dir / "runtime-provenance.json").write_text(json.dumps(runtime_files, indent=2))
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "libero-rollback.run-manifest.v1",
                "dataset_version": case["dataset_version"],
                "case_id": case["case_id"],
                "task_id": case["task"]["task_id"],
                "command": command,
                "python": str(python_executable),
                "libero_root": str(libero_root),
                "runtime_root": str(runtime_root),
                "adapter": adapter,
                "checkpoint": str(checkpoint) if checkpoint else None,
                "seed": seed,
                "suite": suite,
                "dimension": dimension,
                "severity": severity or case["severity"],
                "success_delay": success_delay,
                "success_check_interval": success_check_interval,
                "video": video,
                "mode": mode,
                "post_success_window": post_success_window,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    error = None
    returncode = 1
    try:
        with log_path.open("w", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                command,
                cwd=runtime_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="")
                log_file.write(line)
            returncode = process.wait()
    except OSError as exc:
        error = f"could not start external runtime: {exc}"
    result_path, document = _find_runner_result(output_dir)
    normalized = _normalize_result(
        case,
        seed=seed,
        adapter=adapter,
        checkpoint=str(checkpoint) if checkpoint else None,
        returncode=returncode,
        output_dir=output_dir,
        runner_result_path=result_path,
        runner_document=document,
        error=error,
        success_delay=success_delay,
        success_check_interval=success_check_interval,
    )
    if returncode != 0 and normalized["error"] is None:
        normalized["error"] = f"external runtime exited with code {returncode}"
    (output_dir / "case_result.json").write_text(
        json.dumps(_json_safe(normalized), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "completion.json").write_text(
        json.dumps(
            {
                "case_id": case["case_id"],
                "fingerprint": plan["fingerprint"],
                "returncode": returncode,
                "results": [
                    str(path.relative_to(output_dir)) for path in output_dir.rglob("results.json")
                ],
            },
            indent=2,
        )
    )
    return normalized
