"""Contract tests for the migrated case/meta JSON Schemas (docs/SPEC.md §11)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml

from libero_rollback.schema import (
    METADATA_ROW_SCHEMA,
    SCHEMA_ID,
    load_schema,
    schema_path,
    validate_case,
    validate_case_file,
    validate_metadata_file,
    validate_metadata_row,
)


def valid_case() -> dict:
    return {
        "schema_version": "libero-rollback.case.v1",
        "dataset_version": "2.0.0",
        "case_id": "libero-10-00-rollback-test",
        "template_id": "completed-subgoal-rollback",
        "source": {
            "case_source_id": "dataset-fixture",
            "task_source_id": "task-fixture",
            "task_locator_source_id": "locator-fixture",
            "case_reference": "fixture-reference",
        },
        "task": {
            "suite": "LIBERO-10",
            "task_id": "libero_10/00",
            "task_index": 0,
            "source_bddl": "libero_10/turn_on_the_stove.bddl",
        },
        "stage": {"name": "completion-boundary", "description": "all native goals hold"},
        "trigger": {"event": "all_done", "window": "after completion", "delay_steps": 10},
        "intervention_description": "restore the completed relation to the episode-initial pose",
        "completed_relations": [{"predicate": "(On bowl plate)", "source_task_goal": True}],
        "rollback_target": {
            "predicate": "(On bowl plate)",
            "actor": "bowl",
            "state_change": {
                "kind": "restore_episode_initial_pose",
                "target": "episode_initial_pose",
                "velocity": "zero",
            },
        },
        "validity_constraints": ["completed_relation_true_before_intervention"],
        "scenario_type": "completed_relation_rollback",
        "severity": "d0",
        "severity_rationale": "episode-initial pose restore",
        "expected_evaluation_semantics": "relation_then_resume",
        "assumptions": [],
        "open_questions": [],
    }


def native_relation_set_case() -> dict:
    case = valid_case()
    case["trigger"]["time_point"] = "all_done"
    case["completed_relations"] = [
        {"predicate": "(On a b)", "source_task_goal": True},
        {"predicate": "(Turnon c)", "source_task_goal": True},
    ]
    case["rollback_target"] = {
        "selection_id": "selector-1",
        "actor": "selected_relation_actor",
        "state_change": {
            "kind": "restore_native_relation_set",
            "velocity": "zero",
            "relations": [
                {
                    "predicate": ["On", "a", "b"],
                    "actor_role": "gripper",
                    "subgoal_id": "subgoal-1",
                    "restore": "episode_initial_pose",
                },
                {
                    "predicate": ["Turnon", "c"],
                    "actor_role": "articulation_target",
                    "joint_name": "c_joint",
                    "restore": "episode_initial_joint_position",
                },
            ],
        },
    }
    return case


def metadata_row() -> dict:
    return {
        "struct_id": "s0001",
        "suite": "goal",
        "source_tasks": [
            {
                "suite": "goal",
                "task_idx": 0,
                "bddl_name": "open_the_middle_drawer_of_the_cabinet",
            },
            {
                "suite": "object",
                "task_idx": 1,
                "bddl_name": "pick_up_the_alphabet_soup_and_place_it_in_the_basket",
            },
        ],
        "goal_atoms": [
            "(Open wooden_cabinet_1_middle_region)",
            "(In alphabet_soup_1 basket_1_contain_region)",
        ],
        "n_atoms": 2,
        "instruction": "open the middle drawer and put the soup in the basket",
        "init_source": (
            "libero/libero/init_files/libero_goal/"
            "open_the_middle_drawer_of_the_cabinet.pruned_init"
        ),
        "valid": True,
    }


def test_released_v1_schema_is_copied_with_its_id() -> None:
    path = schema_path()
    assert path.is_file()
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["$id"] == SCHEMA_ID
    assert document["properties"]["schema_version"]["const"] == "libero-rollback.case.v1"
    assert load_schema()["$id"] == SCHEMA_ID


def test_valid_case_passes() -> None:
    assert validate_case(valid_case()) == []


def test_case_without_rollback_target_is_rejected() -> None:
    case = valid_case()
    del case["rollback_target"]
    errors = validate_case(case)
    assert any("rollback_target" in error for error in errors)


def test_case_cannot_contain_run_results() -> None:
    case = valid_case()
    case["run_result"] = {"success": True}
    errors = validate_case(case)
    assert any("run_result" in error for error in errors)


def test_native_relation_set_is_valid_at_completion_boundary() -> None:
    assert validate_case(native_relation_set_case()) == []


def test_native_relation_set_requires_the_completion_boundary() -> None:
    case = native_relation_set_case()
    case["trigger"]["time_point"] = "early"
    assert validate_case(case) == ["native relation sets require the completion boundary"]


def test_native_relation_set_rejects_repeated_predicate() -> None:
    case = native_relation_set_case()
    case["rollback_target"]["state_change"]["relations"][0]["predicate"] = ["Turnon", "c"]
    errors = validate_case(case)
    assert "native relation sets cannot repeat a predicate" in errors


def test_native_relation_set_rejects_repeated_actor() -> None:
    case = native_relation_set_case()
    case["rollback_target"]["state_change"]["relations"][0]["actor_role"] = "articulation_target"
    errors = validate_case(case)
    assert "native relation sets cannot write the same actor twice" in errors


def test_native_relation_set_requires_declared_completed_relation() -> None:
    case = native_relation_set_case()
    case["completed_relations"][0]["predicate"] = "(Other x y)"
    errors = validate_case(case)
    assert "native relation set predicates must be declared completed relations" in errors


def test_native_relation_set_rejects_temporal_second_write() -> None:
    case = native_relation_set_case()
    case["transient"] = {"after_steps": 5, "destination": "pre_injection"}
    errors = validate_case(case)
    assert "native relation sets do not support temporal second writes" in errors


def test_validate_case_file_reads_yaml(tmp_path: Path) -> None:
    path = tmp_path / "case.yaml"
    path.write_text(yaml.safe_dump(valid_case(), sort_keys=False), encoding="utf-8")
    assert validate_case_file(path) == []
    path.write_text("not: [valid", encoding="utf-8")
    assert validate_case_file(path)


def test_metadata_schema_is_versioned() -> None:
    assert METADATA_ROW_SCHEMA["$id"] == "urn:libero-rollback:schema:compose-metadata:v1"
    assert METADATA_ROW_SCHEMA["required"][0] == "struct_id"


def test_valid_metadata_row_passes() -> None:
    assert validate_metadata_row(metadata_row()) == []


def test_metadata_row_rejects_atom_count_mismatch() -> None:
    row = metadata_row()
    row["n_atoms"] = 3
    errors = validate_metadata_row(row)
    assert "n_atoms must equal the number of goal_atoms" in errors


def test_metadata_row_rejects_bad_struct_id() -> None:
    row = metadata_row()
    row["struct_id"] = "task-1"
    errors = validate_metadata_row(row)
    assert any("struct_id" in error for error in errors)


def test_metadata_row_rejects_absolute_init_source() -> None:
    row = metadata_row()
    row["init_source"] = "/opt/LIBERO/libero/libero/init_files/x.pruned_init"
    errors = validate_metadata_row(row)
    assert "init_source must be relative to LIBERO_HOME, not absolute" in errors


def test_metadata_row_rejects_unparenthesised_atom() -> None:
    row = metadata_row()
    row["goal_atoms"] = ["Open wooden_cabinet_1_middle_region", "(In a b)"]
    errors = validate_metadata_row(row)
    assert any("goal_atoms/0" in error for error in errors)


def test_metadata_row_rejects_duplicate_source_slot() -> None:
    row = metadata_row()
    row["source_tasks"] = copy.deepcopy(row["source_tasks"])
    row["source_tasks"][1].update(suite="goal", task_idx=0)
    errors = validate_metadata_row(row)
    assert any("duplicate source task slot" in error for error in errors)


def test_validate_metadata_file_prefixes_line_numbers(tmp_path: Path) -> None:
    path = tmp_path / "metadata.jsonl"
    bad = metadata_row()
    bad["valid"] = "yes"
    path.write_text(
        json.dumps(metadata_row()) + "\n" + json.dumps(bad) + "\n",
        encoding="utf-8",
    )
    errors = validate_metadata_file(path)
    assert errors
    assert all(error.startswith("line 2:") for error in errors)
