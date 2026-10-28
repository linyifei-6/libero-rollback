"""Reproduce the progress-change expansion without overwriting historical cases."""

from __future__ import annotations

import copy
import math
from pathlib import Path

import yaml
from build_current_catalog import TASK_DEFINITIONS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dataset/progress-failure/cases"
SOURCE = "progress-failure-expansion-20261014"


def generate() -> list[dict]:
    historical = []
    for group in ("two-subtask", "rollback-battery", "pose-control", "reference-object"):
        historical += [
            yaml.safe_load(p.read_text())
            for p in sorted((ROOT / "dataset" / group / "cases").glob("*.yaml"))
        ]
    cases = []

    def base(task, suffix, mechanism, state, control=False, completion=False):
        candidates = [
            c
            for c in historical
            if c["task"]["task_index"] == task
            and c["severity"] == "d0"
            and c["trigger"].get("time_point") == "mid"
        ]
        if not candidates:
            candidates = [c for c in historical if c["task"]["task_index"] == task]
        c = copy.deepcopy(candidates[0])
        c["case_id"] = f"libero-10-{task:02d}-progress-{suffix}"
        c["dataset_version"] = "1.8.0"
        c["source"]["case_source_id"] = SOURCE
        c["source"]["case_reference"] = f"docs/expansion-plan.md / task {task:02d} / {suffix}"
        c["template_id"] = f"completed-relation-rollback/{mechanism}/v1"
        c["rollback_target"]["state_change"] = state
        c["expected_evaluation_semantics"] = (
            "relation_holds_control" if control else "relation_then_resume"
        )
        c["stage"] = {
            "name": "completion_boundary" if completion else "next_subgoal_approach",
            "description": "All native goals hold before revocation; continue after success."
            if completion
            else "The first relation holds, the next operation is under way.",
        }
        event = (
            ("enter_first_subgoal_completed" if task == 9 else "enter_next_subgoal_completed")
            if completion
            else (
                "enter_post_completion_retreat" if task in {1, 2} else "enter_next_subgoal_approach"
            )
        )
        c["trigger"] = {
            "event": event,
            "time_point": "all_done" if completion else "mid",
            "delay_steps": 0,
            "window": c["stage"]["description"],
        }
        c["validity_constraints"] = [
            "completed_relation_true_before_intervention",
            "object_released_before_intervention",
            "zero_velocity_after_intervention",
            "no_object_penetration",
            "task_remains_solvable",
            "baseline_task_solvable",
        ]
        if not control and mechanism not in {"completed-pose"}:
            c["validity_constraints"].append("target_relation_false_after_intervention")
        c["assumptions"] = [
            "Project-authored extension; parameters are proposals, not measurements.",
            (
                "Native predicate, collision, release and protected actor checks must pass "
                "in each episode."
            ),
            "Runtime BDDL variant is recorded separately from the canonical LIBERO-10 task.",
        ]
        c["open_questions"] = [
            "Episode-specific physical validity and predicate truth require simulation evidence."
        ]
        c["intervention_description"] = (
            f"Task {task:02d}: {suffix}; preserve the instruction and protected goals."
        )
        c["severity_rationale"] = (
            "Mechanism label; concrete parameters are explicit and imply no model "
            "difficulty ranking."
        )
        for key in ("pose_role", "reference_role", "transient"):
            c.pop(key, None)
        cases.append(c)
        return c

    for task in range(1, 9):
        for side in ("inside", "outside"):
            c = base(
                task,
                f"boundary-{side}-mid",
                "native-boundary",
                {
                    "kind": "displace_to_relation_boundary",
                    "velocity": "zero",
                    "boundary": {"side": side, "resolution_m": 0.002, "max_distance_m": 0.25},
                },
                control=side == "inside",
            )
            c["severity"] = "boundary"
            c["open_questions"] += [
                (
                    "A horizontal legal pair may not exist for enclosed drawer/microwave or "
                    "basket walls; retain rejection rather than skipping collisions."
                )
            ]
        for angle in (15, 30, 45, 60, 180):
            spin = angle == 180
            suffix = f"{'yaw' if spin else 'roll'}{angle}-completed-mid"
            c = base(
                task,
                suffix,
                "completed-pose",
                {
                    "kind": "displace_from_completed_pose",
                    "offset_m": [0.0, 0.0, 0.0],
                    "offset_frame": "world",
                    "velocity": "zero",
                    "orientation_axis_angle": {
                        "axis": [0.0, 0.0, 1.0] if spin else [1.0, 0.0, 0.0],
                        "angle_rad": math.radians(angle),
                    },
                },
            )
            c["severity"] = "pose"
            c["pose_role"] = "measured_relation_probe"
            c["expected_evaluation_semantics"] = "relation_only"
            c["open_questions"] += [
                (
                    "Rotation is a truth probe: classify relation-preserving control or rollback"
                    " from native pre/post truth; never infer failure from angle alone."
                )
            ]
        # Duration is measured in control steps; re-revocation is gated by actual truth.
        for duration in (5, 20, 60):
            c = base(
                task,
                f"pulse-{duration}-mid",
                "temporal",
                {
                    "kind": "restore_episode_initial_pose",
                    "target": "episode_initial_pose",
                    "velocity": "zero",
                },
            )
            c["severity"] = "d0"
            c["transient"] = {
                "after_steps": duration,
                "destination": "pre_injection",
                "gate": "elapsed_steps",
            }
            c["open_questions"] += [
                "Restoration is external; do not count the restored relation as model recovery."
            ]
        c = base(
            task,
            "repeat-after-recovery-mid",
            "temporal",
            {
                "kind": "restore_episode_initial_pose",
                "target": "episode_initial_pose",
                "velocity": "zero",
            },
        )
        c["severity"] = "d0"
        c["transient"] = {
            "after_steps": 1,
            "destination": "initial_offset",
            "offset_m": [0.0, 0.0, 0.0],
            "offset_frame": "world",
            "gate": "relation_recovered",
            "hold_steps": 3,
        }
        c["open_questions"] += [
            (
                "Without spontaneous recovery, the second event must remain untriggered and "
                "be reported as such."
            )
        ]
    for task in (5, 6, 8):
        for paired in (False, True):
            c = base(
                task,
                f"{'pair' if paired else 'reference'}-moved-mid",
                "reference-object",
                {
                    "kind": "translate_relation_pair" if paired else "displace_reference_object",
                    "reference_role": "subgoal_goal_0",
                    "translation_m": [0.15, 0.0, 0.0],
                    "offset_frame": "world",
                    "velocity": "zero",
                },
                control=paired,
            )
            c["severity"] = "reference"
            c["validity_constraints"] += [
                "reference_object_is_not_a_fixed_fixture",
                "reference_motion_does_not_disturb_the_current_s2_object",
            ]
    for task in (0, 1, 2, 4, 5, 6, 8, 9):
        original = next(
            (c for c in historical if c["task"]["task_index"] == task and c["severity"] == "d0"),
            None,
        )
        # Task 09 takes the existing single-book definition and explicit profile T276.
        if task == 9:
            original = copy.deepcopy(historical[0])
            original["task"] = {
                "suite": "LIBERO-10",
                "task_id": "libero_10/09",
                "task_index": 9,
                "source_task_locator": "T276",
                "source_bddl": (
                    "STUDY_SCENE1_pick_up_the_book_and_place_it_in_the_back_compartment_of_the_c"
                    "addy.bddl"
                ),
            }
            predicate = "(In black_book_1 desk_caddy_1_back_contain_region)"
            original["completed_relations"] = [{"predicate": predicate, "source_task_goal": True}]
            original["rollback_target"] = {
                "actor": "black_book_1",
                "predicate": predicate,
                "state_change": {
                    "kind": "restore_episode_initial_pose",
                    "target": "episode_initial_pose",
                    "velocity": "zero",
                },
            }
            historical.append(original)
        if task == 0:
            original = copy.deepcopy(historical[0])
            original["task"] = copy.deepcopy(
                next(c["task"] for c in historical if c["task"]["task_index"] == 0)
            )
            predicate = "(On moka_pot_1 flat_stove_1_cook_region)"
            original["completed_relations"] = [{"predicate": predicate, "source_task_goal": True}]
            original["rollback_target"] = {
                "actor": "moka_pot_1",
                "predicate": predicate,
                "state_change": {
                    "kind": "restore_episode_initial_pose",
                    "target": "episode_initial_pose",
                    "velocity": "zero",
                },
            }
        c = base(
            task,
            "initial-pose-all-done",
            "episode-initial-pose",
            {
                "kind": "restore_episode_initial_pose",
                "target": "episode_initial_pose",
                "velocity": "zero",
            },
            completion=True,
        )
        c["severity"] = "d0"
        if task in (0, 9):
            c["completed_relations"] = copy.deepcopy(original["completed_relations"])
            c["rollback_target"] = copy.deepcopy(original["rollback_target"])
            c["task"] = copy.deepcopy(original["task"])
        c["open_questions"] += [
            (
                "Post-success continuation must expose at least one policy query after "
                "intervention; count separately from nonterminal rollback."
            )
        ]
    for side in ("inside", "outside"):
        c = base(
            0,
            f"function-boundary-{side}-mid",
            "functional-boundary",
            {
                "kind": "revert_articulation_goal",
                "joint_role": "articulation_target",
                "setback": 1.0,
                "position_tolerance": 0.05,
                "velocity": "zero",
                "functional_boundary": {"side": side, "margin_rad": 0.08},
            },
            control=side == "inside",
        )
        c["severity"] = "articulation"
        c["validity_constraints"].remove("object_released_before_intervention")
        c["open_questions"] += [
            (
                "Read Turnon threshold from installed stove object; verify native truth at "
                "drive completion, not travel magnitude."
            )
        ]
    # Complete the native two-goal completion matrix: revoke each goal alone,
    # then both atomically. Earlier groups already contain the first goal alone
    # (task 00: placement alone). A single-goal task cannot have this pair.
    articulation_predicates = {
        0: ["turnon", "flat_stove_1"],
        1: ["close", "white_cabinet_1_bottom_region"],
        2: ["close", "microwave_1"],
    }
    for task in range(9):
        locator = TASK_DEFINITIONS[task][1]
        profile = yaml.safe_load(
            (ROOT / f"dataset/runtime-profiles/libero_10_t{locator[1:]}.yaml").read_text()
        )["task_profile"]
        placement = [
            {
                "predicate": [
                    g["predicate"],
                    profile["roles"][g["actor_role"]]["name"],
                    g.get("goal_state_name", profile["roles"][g["goal_role"]]["name"]),
                ],
                "actor_role": g["actor_role"],
                "subgoal_id": g["id"],
                "restore": "episode_initial_pose",
            }
            for g in profile["subgoals"]
        ]
        if task in articulation_predicates:
            second = {
                "predicate": articulation_predicates[task],
                "actor_role": "articulation_target",
                "joint_name": profile["articulation"]["joint_name"],
                "restore": "episode_initial_joint_position",
            }
            goals = placement + [second]
        else:
            goals = placement
            second = goals[1]
        for label, relations in (("other-goal", [second]), ("both-goals", goals)):
            c = base(
                task,
                f"{label}-all-done",
                "native-relation-set",
                {
                    "kind": "restore_native_relation_set",
                    "relations": copy.deepcopy(relations),
                    "velocity": "zero",
                },
                completion=True,
            )
            c["severity"] = "d0"
            c["completed_relations"] = [
                {"predicate": "(" + " ".join(r["predicate"]) + ")", "source_task_goal": True}
                for r in goals
            ]
            c["rollback_target"] = {"state_change": c["rollback_target"]["state_change"]}
            c["open_questions"] += [
                (
                    "All target predicates must be true then false; preserve every non-target "
                    "native goal. Failed atomic writes restore all simulator coordinates."
                ),
                (
                    "Joint resets are external endpoint interventions, not a claim of a "
                    "collision-free continuous actuation path."
                ),
            ]
    # These new definitions use verified canonical names. Historical sources are
    # retained untouched and their runtime variants remain explicit in the profile.
    for c in cases:
        task = c["task"]["task_index"]
        c["task"]["source_bddl"] = TASK_DEFINITIONS[task][2]
        if c["trigger"]["time_point"] == "all_done":
            c["trigger"]["event"] = "enter_next_subgoal_completed"
        if "actor" in c["rollback_target"]:
            profile_path = (
                ROOT
                / f"dataset/runtime-profiles/libero_10_t{c['task']['source_task_locator'][1:]}.yaml"
            )
            profile = yaml.safe_load(profile_path.read_text())["task_profile"]
            actor = c["rollback_target"]["actor"]
            subgoal = next(
                g for g in profile["subgoals"] if profile["roles"][g["actor_role"]]["name"] == actor
            )
            c["rollback_target"]["target_subgoal"] = subgoal["id"]
    return cases


if __name__ == "__main__":
    rows = generate()
    OUT.mkdir(parents=True, exist_ok=True)
    for c in rows:
        p = OUT / (c["case_id"] + ".yaml")
        text = yaml.safe_dump(c, sort_keys=False, allow_unicode=True)
        # This unreleased generated collection is reproducible; historical
        # collections are never rewritten by this script.
        p.write_text(text)
    print(f"Generated {len(rows)} cases in {OUT}")
