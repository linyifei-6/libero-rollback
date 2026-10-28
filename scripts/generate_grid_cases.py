"""Generate the rollback case matrix for dataset release 1.2.0.

Dimension vocabulary follows libero-plus/libero-runtime, restricted to what the
engine actually supports (verified against the runtime source):

  * the rollback target is always the FIRST completed subgoal of the episode
    (`completed_subgoal_rollback.py:278` selects `subgoal_completion_order[0]`);
    the `completed_subgoal_object` alias resolves to that subgoal's actor role at
    runtime (`context.py:624-636`), so every profile is usable as long as the
    binding passes the profile's own first-subgoal actor role.
  * placement rollback time points: early (`enter_first_subgoal_completed`),
    mid (`enter_next_subgoal_approach`), later (`enter_next_subgoal_lift`).
  * articulation tasks add `enter_post_completion_retreat`, `enter_x3a_actuation`
    and `enter_articulation_completed`.
  * destinations: episode initial pose, signed task-frame offsets, pre-grasp
    checkpoint, container-above hover (only where the goal region exists), and
    articulation setback (only where the profile declares an articulation block).

Usage:
    python scripts/generate_grid_cases.py --write
    python scripts/generate_grid_cases.py --task 1 --verbose
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
# Defaults describe the release being authored; `--release`/`--version` override them
# so a corrected vocabulary can ship as a new version while the earlier release stays
# intact as historical evidence.
RELEASE = ROOT / "dataset/v1.3"
CASES = RELEASE / "cases"
VERSION = "1.3.0"
SOURCE_ID = "runtime-grid-expansion-20261009"

POSE_TEMPLATE = "completed-relation-rollback/episode-initial-pose/v1"
OFFSET_TEMPLATE = "completed-relation-rollback/support-surface-offset/v1"
CHECKPOINT_TEMPLATE = "completed-relation-rollback/pregrasp-checkpoint/v1"
ABOVE_TEMPLATE = "completed-relation-rollback/container-above/v1"
ARTICULATION_TEMPLATE = "completed-relation-rollback/articulation-goal/v1"

OFFSETS = {
    "n3": [0.03, 0.03, 0.0],
    "n5": [0.05, 0.05, 0.0],
    "p3": [-0.03, -0.03, 0.0],
    "p5": [-0.05, -0.05, 0.0],
    "p8": [-0.08, -0.06, 0.0],
    "p10": [-0.10, -0.08, 0.0],
    "n8": [0.08, 0.06, 0.0],
}

ABOVE_VARIANTS = [("c05", 0.05), ("c20", 0.20)]

# Articulation magnitudes, calibrated against the engine rather than guessed.
# Task 1 is the sliding drawer (T33): the joint reacts at 182-425 N, so the drive
# needs force, and the largest magnitude additionally needs a lower velocity for the
# per-step body-jump gate to pass.
# Task 2 is the hinged microwave door (T78): it reacts at 0.8-3.4 N and the delivered
# templates only ever nudge it by 0.03-0.07 rad; requests of 0.10-0.60 rad could not
# be driven to target, so its vocabulary stays inside the supported band.
ARTICULATION_VARIANTS = {
    1: [("s02", 0.02), ("s03", 0.03), ("s05", 0.05)],
    2: [("h02", 0.02), ("h04", 0.04), ("h07", 0.07)],
}

TASKS = {
    0: dict(slug="moka-pot-stove", idx=0, kind="placement",
            actor="moka_pot_1", actor_role="subgoal_object_0",
            goal="(On moka_pot_1 flat_stove_1_cook_region)", region="flat_stove_1_cook_region",
            stage="completion_boundary", above=False),
    1: dict(slug="black-bowl-drawer", idx=33, kind="articulation",
            actor="akita_black_bowl_1", actor_role="subgoal_object_a",
            goal="(In akita_black_bowl_1 white_cabinet_1_bottom_region)",
            region="white_cabinet_1_bottom_region",
            stage="first_completed_subgoal", above=True, joint_role="articulation_target"),
    2: dict(slug="yellow-white-mug-microwave", idx=78, kind="articulation",
            actor="white_yellow_mug_1", actor_role="subgoal_object_a",
            goal="(In white_yellow_mug_1 microwave_1_heating_region)",
            region="microwave_1_heating_region",
            stage="first_completed_subgoal", above=True, joint_role="articulation_target"),
    3: dict(slug="first-moka-pot-stove", idx=133, kind="placement",
            actor="moka_pot_1", actor_role="subgoal_object_a",
            goal="(On moka_pot_1 flat_stove_1_cook_region)", region="flat_stove_1_cook_region",
            stage="first_completed_subgoal", above=False),
    4: dict(slug="soup-cheese-basket", idx=137, kind="placement",
            actor="alphabet_soup_1", actor_role="subgoal_object_0",
            goal="(In alphabet_soup_1 basket_1_contain_region)", region="basket_1_contain_region",
            stage="first_completed_subgoal", above=False),
    5: dict(slug="soup-sauce-basket", idx=145, kind="placement",
            actor="alphabet_soup_1", actor_role="subgoal_object_0",
            goal="(In alphabet_soup_1 basket_1_contain_region)", region="basket_1_contain_region",
            stage="first_completed_subgoal", above=False),
    6: dict(slug="cheese-butter-basket", idx=158, kind="placement",
            actor="cream_cheese_1", actor_role="subgoal_object_0",
            goal="(In cream_cheese_1 basket_1_contain_region)", region="basket_1_contain_region",
            stage="first_completed_subgoal", above=False),
    7: dict(slug="white-mug-left-plate", idx=193, kind="placement",
            actor="porcelain_mug_1", actor_role="subgoal_object_a",
            goal="(On porcelain_mug_1 plate_1)", region=None,
            stage="first_completed_subgoal", above=False),
    8: dict(slug="mug-pudding-placement", idx=237, kind="placement",
            actor="porcelain_mug_1", actor_role="subgoal_object_0",
            goal="(On porcelain_mug_1 plate_1)", region="plate_1",
            stage="first_completed_subgoal", above=False),
    9: dict(slug="book-caddy", idx=276, kind="placement",
            actor="black_book_1", actor_role="subgoal_object_0",
            goal="(In black_book_1 desk_caddy_1_back_contain_region)",
            region="desk_caddy_1_back_contain_region",
            stage="completion_boundary", above=False),
}

BDDL = {
    0: "KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it.bddl",
    1: "KITCHEN_SCENE4_put_the_black_bowl_in_the_bottom_drawer_of_the_cabinet_and_close_it.bddl",
    2: "KITCHEN_SCENE6_put_the_yellow_and_white_mug_in_the_microwave_and_close_it.bddl",
    3: "KITCHEN_SCENE8_put_both_moka_pots_on_the_stove.bddl",
    4: "LIVING_ROOM_SCENE1_put_both_the_alphabet_soup_and_the_cream_cheese_box_in_the_basket.bddl",
    5: "LIVING_ROOM_SCENE2_put_both_the_alphabet_soup_and_the_tomato_sauce_in_the_basket.bddl",
    6: "LIVING_ROOM_SCENE2_put_both_the_cream_cheese_box_and_the_butter_in_the_basket.bddl",
    7: "LIVING_ROOM_SCENE5_put_the_white_mug_on_the_left_plate_and_put_the_yellow_and_white_mug_on_the_right_plate.bddl",
    8: "LIVING_ROOM_SCENE6_put_the_white_mug_on_the_plate_and_put_the_chocolate_pudding_to_the_right_of_the_plate.bddl",
    9: "STUDY_SCENE1_pick_up_the_book_and_place_it_in_the_back_compartment_of_the_caddy.bddl",
}

PLACEMENT_WINDOWS = {
    "early": ("enter_first_subgoal_completed", "first placement has just been confirmed and released"),
    "mid": ("enter_next_subgoal_approach", "the arm has turned towards the next object but has not touched it"),
    "later": ("enter_next_subgoal_lift", "the next object has already been lifted off its surface"),
}
ARTICULATION_WINDOWS = {
    "early": ("enter_first_subgoal_completed", "placement has just been confirmed and released"),
    "mid": ("enter_post_completion_retreat", "the arm has withdrawn from the container and is turning to the closing handle"),
    "later": ("enter_x3a_actuation", "the closing action has already begun"),
    "after": ("enter_articulation_completed", "the drawer or door has just reached its closed position"),
}

PLACEMENT_CONSTRAINTS = [
    "completed_relation_true_before_intervention",
    "target_relation_false_after_intervention",
    "object_released_before_intervention",
    "zero_velocity_after_intervention",
    "target_pose_within_workspace",
    "target_pose_collision_free",
    "no_object_penetration",
    "task_remains_solvable",
    "baseline_task_solvable",
]
SURFACE_CONSTRAINTS = PLACEMENT_CONSTRAINTS + [
    "target_pose_on_support_surface",
    "orientation_preserved",
]
ARTICULATION_CONSTRAINTS = [
    "completed_relation_true_before_intervention",
    "target_relation_false_after_intervention",
    "zero_velocity_after_intervention",
    "no_object_penetration",
    "task_remains_solvable",
    "baseline_task_solvable",
]


def _placement_destinations(task: dict) -> list[tuple[str, str]]:
    rows = [("t0", "pose")]
    rows += [(label, "offset") for label in ("n3", "n5", "p5", "p10")]
    rows.append(("checkpoint", "checkpoint"))
    if task.get("above") and task.get("region"):
        rows += [(f"above-{label}", f"above:{label}") for label, _ in ABOVE_VARIANTS]
    return rows


def matrix(task_index: int) -> list[dict]:
    """Placement rollback uses the three pre-closure time points; the closure
    instant itself only applies to the articulation goal, because
    `completed_subgoal_rollback` rejects `enter_articulation_completed`."""

    task = TASKS[task_index]
    if task["stage"] == "completion_boundary":
        placement_windows = ["early"]
    elif task["kind"] == "articulation":
        placement_windows = ["early", "mid", "later"]
    else:
        placement_windows = ["early", "mid", "later"]

    rows: list[dict] = []
    for window in placement_windows:
        for suffix, plan in _placement_destinations(task):
            rows.append({"goal": "place", "window": window, "suffix": suffix, "plan": plan})
    if task["kind"] == "articulation":
        for window in ("mid", "later", "after"):
            for label, setback in ARTICULATION_VARIANTS[task_index]:
                rows.append({
                    "goal": "close", "window": window, "suffix": label,
                    "plan": f"articulation:{setback}",
                })
    return rows


def build_case(task_index: int, spec: dict) -> dict:
    task = TASKS[task_index]
    window, suffix, plan = spec["window"], spec["suffix"], spec["plan"]
    windows = PLACEMENT_WINDOWS if task["kind"] == "placement" else ARTICULATION_WINDOWS
    event, window_text = windows[window]
    is_articulation = spec["goal"] == "close"
    case_id = (
        f"libero-10-{task_index:02d}-{task['slug']}-"
        f"{'close' if is_articulation else 'place'}-{window}-{suffix}"
    )

    if plan == "pose":
        state_change = {
            "kind": "restore_episode_initial_pose",
            "target": "episode_initial_pose",
            "velocity": "zero",
        }
        template_id, severity, constraints = POSE_TEMPLATE, "d0", SURFACE_CONSTRAINTS
    elif plan == "offset":
        state_change = {
            "kind": "apply_episode_initial_offset",
            "offset_m": OFFSETS[suffix],
            "coordinate_frame": "task_frame_longitudinal_lateral_vertical",
            "velocity": "zero",
        }
        template_id, severity, constraints = OFFSET_TEMPLATE, suffix, SURFACE_CONSTRAINTS
    elif plan == "checkpoint":
        state_change = {
            "kind": "restore_captured_checkpoint_pose",
            "target": "captured_checkpoint_pose",
            "checkpoint": "pregrasp",
            "capture_event": "first_valid_precontact_approach",
            "velocity": "zero",
        }
        template_id, severity, constraints = CHECKPOINT_TEMPLATE, "checkpoint", PLACEMENT_CONSTRAINTS
    elif plan.startswith("above:"):
        label = plan.split(":", 1)[1]
        clearance = dict(ABOVE_VARIANTS)[label]
        state_change = {
            "kind": "restore_container_above_pose",
            "target": "container_top_hover_pose",
            "clearance_m": clearance,
            "clearance_max_m": 0.45,
            "above_container_top": True,
            "velocity": "zero",
        }
        template_id, severity, constraints = ABOVE_TEMPLATE, "above", PLACEMENT_CONSTRAINTS
    elif plan.startswith("articulation:"):
        setback = float(plan.split(":", 1)[1])
        state_change = {
            "kind": "revert_articulation_goal",
            "joint_role": task.get("joint_role", "articulation_target"),
            "setback": setback,
            "position_tolerance": 0.005,
            "velocity": "zero",
        }
        template_id, severity, constraints = (
            ARTICULATION_TEMPLATE, "articulation", ARTICULATION_CONSTRAINTS,
        )
    else:
        raise ValueError(f"unknown plan {plan}")

    stage_name = task["stage"]
    if window == "after" or stage_name == "completion_boundary":
        stage_name = "completion_boundary"

    if is_articulation:
        completed = [{
            "goal_id": "articulation_goal",
            "joint_role": task.get("joint_role", "articulation_target"),
            "source_task_goal": True,
        }]
        rollback = {
            "goal_id": "articulation_goal",
            "joint_role": task.get("joint_role", "articulation_target"),
            "state_change": state_change,
        }
    else:
        completed = [{"predicate": task["goal"], "source_task_goal": True}]
        rollback = {"predicate": task["goal"], "actor": task["actor"], "state_change": state_change}

    return {
        "schema_version": "libero-rollback.case.v1",
        "dataset_version": VERSION,
        "case_id": case_id,
        "template_id": template_id,
        "source": {
            "case_source_id": SOURCE_ID,
            "task_source_id": "libero-plus-task-definitions-v1",
            "task_locator_source_id": "full-suite-runtime-crosswalk-20261009",
            "case_reference": (
                f"Runtime grid expansion / task {task_index:02d} / "
                f"{'articulation goal' if is_articulation else 'first completed placement'} / "
                f"{window} / {suffix}"
            ),
            "supporting_source_ids": [
                "scenario-timing-position-matrix-20260926",
                "scenario-validity-severity-guidance-20260922",
            ],
        },
        "task": {
            "suite": "LIBERO-10",
            "task_id": f"libero_10/{task_index:02d}",
            "task_index": task_index,
            "source_bddl": BDDL[task_index],
            "source_task_locator": f"T{task['idx']}",
        },
        "stage": {"name": stage_name, "description": f"{window}: {window_text}."},
        "trigger": {
            "event": event,
            "window": window_text,
            "delay_steps": 0,
            "time_point": (
                "all_done" if window == "after" or stage_name == "completion_boundary" else window
            ),
        },
        "intervention_description": (
            f"Revoke the completed {'articulation goal' if is_articulation else 'placement'} "
            f"at the {window} time point using {plan}; retain the instruction and every other goal."
        ),
        "completed_relations": completed,
        "rollback_target": rollback,
        "validity_constraints": constraints,
        "scenario_type": "completed_relation_rollback",
        "severity": severity,
        "severity_rationale": (
            "Runtime-dimension label; the concrete signed offset, clearance or joint "
            "setback is recorded in state_change. No claim of comparable model difficulty."
        ),
        "expected_evaluation_semantics": "relation_then_resume",
        "assumptions": [
            "Runtime-dimension expansion: offsets, clearance and setback magnitudes are "
            "explicit design parameters and need episode-specific physical preflight.",
            "The affected relation must hold and the object must be released before mutation.",
            "The rollback target is the first subgoal completed in execution order; the "
            "runtime binds the completed-subgoal alias to that subgoal at run time.",
        ],
        "open_questions": [
            "Verify collision-free support, no penetration, release, and task solvability "
            "for the selected episode.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--task", type=int, action="append", default=[])
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--release", default="dataset/v1.3",
                        help="release directory, relative to the repository root")
    parser.add_argument("--version", default="1.3.0", help="dataset_version written into cases")
    args = parser.parse_args()

    global RELEASE, CASES, VERSION
    RELEASE = ROOT / args.release
    CASES = RELEASE / "cases"
    VERSION = args.version
    targets = args.task or list(range(10))
    written = 0
    total = 0
    for task_index in targets:
        specs = matrix(task_index)
        total += len(specs)
        if args.verbose:
            print(f"\n=== task {task_index:02d} ({TASKS[task_index]['kind']}): {len(specs)} cases ===")
        for spec in specs:
            case = build_case(task_index, spec)
            if args.verbose:
                print(f"  {case['case_id']:<58} {case['severity']:<12} {case['trigger']['event']}")
            if args.write:
                CASES.mkdir(parents=True, exist_ok=True)
                (CASES / f"{case['case_id']}.yaml").write_text(
                    yaml.safe_dump(case, sort_keys=True, allow_unicode=True, width=100),
                    encoding="utf-8",
                )
                written += 1
        print(f"task {task_index:02d}: {len(specs)} cases")
    print(f"\ntotal planned: {total}; written: {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
