"""Generate the full case-matrix batch (all engine-expressible cases of v3).

Scope decisions, forced by measurement rather than preference:

* The rollback handler hardcodes `subgoal_completion_order[0]`
  (`interventions/completed_subgoal_rollback.py:278`), so a case cannot choose *which*
  completed subgoal to revoke. Therefore, for the three-subgoal tasks 04-06 the matrix's
  "s3 rolls back s2" group cannot be expressed, and "s3 rolls back s1" collapses onto the
  same (target, window, position) triple as the s2 group. Only the s2-window group is
  generated; see docs/case-matrix-v3-full.md for the deferred groups.
* Tasks 01-03 and 07 keep the runtime RB1-RB4 sets and are not regenerated here.

Generated here: tasks 04, 05, 06, 08 — 3 windows x 3 positions = 9 cases each, plus the
`container_above` row for the tasks whose profile declares a goal region.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO = Path("/home/tarowang/workspace/roboot/libero-rollback")
OUT = REPO / "dataset/matrix-v3/cases"
VERSION = "1.5.0"

# task index -> (slug, bddl, T-locator, s1 actor/predicate, first_subgoal id)
TASKS = {
    4: dict(
        slug="soup-cheese-basket", locator="T137", task_id="libero_10/04",
        bddl="LIVING_ROOM_SCENE1_put_both_the_alphabet_soup_and_the_cream_cheese_box_in_the_basket_table_1.bddl",
        actor="alphabet_soup_1", predicate="(In alphabet_soup_1 basket_1_contain_region)",
        s2="cream_cheese_1", region="basket_1"),
    5: dict(
        slug="soup-sauce-basket", locator="T145", task_id="libero_10/05",
        bddl="LIVING_ROOM_SCENE2_put_both_the_alphabet_soup_and_the_tomato_sauce_in_the_basket_table_1.bddl",
        actor="alphabet_soup_1", predicate="(In alphabet_soup_1 basket_1_contain_region)",
        s2="tomato_sauce_1", region="basket_1"),
    6: dict(
        slug="cheese-butter-basket", locator="T158", task_id="libero_10/06",
        bddl="LIVING_ROOM_SCENE2_put_both_the_cream_cheese_box_and_the_butter_in_the_basket_table_1.bddl",
        actor="cream_cheese_1", predicate="(In cream_cheese_1 basket_1_contain_region)",
        s2="butter_1", region="basket_1"),
    8: dict(
        slug="mug-pudding-placement", locator="T237", task_id="libero_10/08",
        bddl="LIVING_ROOM_SCENE6_put_the_white_mug_on_the_plate_and_put_the_chocolate_pudding_to_the_right_of_the_plate_table_1.bddl",
        actor="porcelain_mug_1", predicate="(On porcelain_mug_1 plate_1)",
        s2="chocolate_pudding_1", region="plate_1"),
}

# the window is measured during s2's execution; the trigger events are the ones the
# profiles declare and the bridge maps onto its mid/later/after vocabulary
WINDOWS = {
    "early": ("enter_first_subgoal_completed", "s1 has just been released and settled; s2 has not started"),
    "mid":   ("enter_next_subgoal_approach", "s2 is being executed, the arm is approaching the next object"),
    "later": ("enter_next_subgoal_lift", "s2 is being executed and its object has been picked up"),
}

POSITIONS = {
    # name -> (template_id, severity, state_change)
    "p1": ("completed-relation-rollback/episode-initial-pose/v1", "d0",
           {"kind": "restore_episode_initial_pose", "target": "episode_initial_pose",
            "velocity": "zero"}),
    "p2": ("completed-relation-rollback/support-surface-offset/v1", "n3",
           {"kind": "apply_episode_initial_offset", "offset_m": [-0.03, 0.03, 0.0],
            "offset_frame": "world", "velocity": "zero"}),
    "p3": ("completed-relation-rollback/pregrasp-checkpoint/v1", "checkpoint",
           {"kind": "restore_captured_checkpoint_pose", "target": "checkpoint",
            "checkpoint": "pregrasp", "velocity": "zero"}),
}


def build(task_index: int, spec: dict, window: str, position: str) -> dict:
    event, description = WINDOWS[window]
    template_id, severity, state_change = POSITIONS[position]
    case_id = (f"libero-10-{task_index:02d}-{spec['slug']}-rollback-s1-{window}-{position}")
    return {
        "schema_version": "libero-rollback.case.v1",
        "dataset_version": VERSION,
        "case_id": case_id,
        "template_id": template_id,
        "source": {
            "case_source_id": "runtime-grid-expansion-20261010",
            "task_source_id": "libero-plus-task-definitions-v1",
            "task_locator_source_id": "full-suite-runtime-crosswalk-20261009",
            "case_reference": (f"matrix v3 / task {task_index:02d} / roll back s1 "
                               f"({spec['actor']}) while s2 ({spec['s2']}) is executed / "
                               f"{window} / {position}"),
            "supporting_source_ids": ["scenario-timing-position-matrix-20260926",
                                      "scenario-validity-severity-guidance-20260922"],
        },
        "task": {
            "suite": "LIBERO-10",
            "task_id": spec["task_id"],
            "task_index": task_index,
            "source_bddl": spec["bddl"],
            "source_task_locator": spec["locator"],
        },
        "stage": {
            "name": {"early": "first_completed_subgoal",
                     "mid": "next_subgoal_approach",
                     "later": "next_subgoal_lift"}[window],
            "description": description,
        },
        "trigger": {
            "event": event,
            "window": description,
            "delay_steps": 10 if window == "early" else 0,
            "time_point": window,
        },
        "intervention_description": (
            f"Revoke the completed s1 relation {spec['predicate']} by restoring "
            f"{spec['actor']} to its {position} state while s2 ({spec['s2']}) is being "
            f"executed; retain the instruction and every other goal."
        ),
        "completed_relations": [
            {"predicate": spec["predicate"], "source_task_goal": True}
        ],
        "rollback_target": {
            "actor": spec["actor"],
            "predicate": spec["predicate"],
            "state_change": state_change,
        },
        "validity_constraints": [
            "completed_relation_true_before_intervention",
            "target_relation_false_after_intervention",
            "object_released_before_intervention",
            "zero_velocity_after_intervention",
            "target_pose_within_workspace",
            "target_pose_collision_free",
            "no_object_penetration",
            "task_remains_solvable",
            "baseline_task_solvable",
        ],
        "scenario_type": "completed_relation_rollback",
        "severity": severity,
        "severity_rationale": (
            "Runtime-dimension label; the concrete signed offset or checkpoint is recorded "
            "in state_change. No claim of comparable model difficulty."
        ),
        "expected_evaluation_semantics": "relation_then_resume",
        "assumptions": [
            "The rollback target is the first subgoal completed in execution order; the "
            "runtime binds the completed-subgoal alias to that subgoal at run time.",
            "The affected relation must hold and the object must be released before mutation.",
            "Offsets and checkpoints are design parameters and need episode-specific preflight.",
        ],
        "open_questions": [
            "Verify collision-free support, no penetration, release, and task solvability.",
        ],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for task_index, spec in TASKS.items():
        for window in WINDOWS:
            for position in POSITIONS:
                case = build(task_index, spec, window, position)
                path = OUT / f"{case['case_id']}.yaml"
                path.write_text(
                    yaml.safe_dump(case, sort_keys=True, allow_unicode=True, width=100),
                    encoding="utf-8",
                )
                written.append(case["case_id"])
    print(f"wrote {len(written)} cases to {OUT.relative_to(REPO)}")
    by_task: dict[int, int] = {}
    for cid in written:
        by_task[int(cid.split('-')[2])] = by_task.get(int(cid.split('-')[2]), 0) + 1
    for task_index in sorted(by_task):
        print(f"  task {task_index:02d}: {by_task[task_index]}")
    (REPO / "dataset/matrix-v3/README.md").write_text(
        "# matrix-v3 batch\n\n"
        "Engine-expressible subset of the v3 case matrix (see "
        "`docs/case-matrix-v3-full.md`).\n\n"
        "Generated: tasks 04, 05, 06, 08 — 3 windows x 3 positions = 9 cases each.\n\n"
        "Deferred, because the rollback handler hardcodes `subgoal_completion_order[0]`\n"
        "(`interventions/completed_subgoal_rollback.py:278`):\n\n"
        "* the `s3 rolls back s2` group needs a case-level target selector;\n"
        "* the `s3 rolls back s1` group would be an exact duplicate of the `s2 rolls back\n"
        "  s1` group under the current engine;\n"
        "* the synchronous `s1 + s2` group needs a multi-target intervention.\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
