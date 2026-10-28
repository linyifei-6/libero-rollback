"""Tests for the current case sets.

Replaces the retired suite, which encoded `dataset/v1` and the old severity vocabulary.
Each test here checks something the new sets can actually violate: schema validity,
cross-set uniqueness, window/position coverage, and the two bridge behaviours that were
measured to be broken earlier (declared offset frame and trigger delay).
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from libero_rollback.runtime import (  # noqa: E402
    RuntimeBridgeError,
    check_runtime_capabilities,
    runtime_binding,
)
from libero_rollback.validation import validate_case_data, validate_dataset  # noqa: E402

SETS = {
    "two-subtask": ROOT / "dataset/two-subtask/cases",
    "rollback-battery": ROOT / "dataset/rollback-battery/cases",
    "reference-object": ROOT / "dataset/reference-object/cases",
    "progress-failure": ROOT / "dataset/progress-failure/cases",
}
POSITION_LABELS = {
    "d0",
    "n3",
    "n5",
    "n8",
    "p3",
    "p5",
    "p8",
    "p10",
    "r05",
    "above",
    "articulation",
    "pose",
    "reference",
    "boundary",
    "holding",
}
PLACEMENT_KINDS = {
    "restore_episode_initial_pose",
    "apply_episode_initial_offset",
    "restore_container_above_pose",
}
ARTICULATION_KIND = "revert_articulation_goal"
# task 00 rolls back a functional (Turnon) relation and tasks 01/02 roll back a placement
# before actuating the drawer or door; those three profiles declare `next_subgoal_*`
# milestones only for the *next* placement, so their windows use the events below.
# Tasks 03-08 place two objects and use the plain next-subgoal milestones.
NON_PLACEMENT_PAIR_TASKS = {0, 1, 2}
PLACEMENT_WINDOW_EVENTS = {
    "early": {"enter_first_subgoal_completed"},
    "mid": {"enter_next_subgoal_approach"},
    "later": {"enter_next_subgoal_lift", "enter_x3a_transport"},
    "all_done": {"enter_next_subgoal_completed"},
}
ARTICULATION_WINDOW_EVENTS = {
    # the pot is still to be placed, so "early" is the approach milestone
    "early": {"enter_first_subgoal_completed", "enter_next_subgoal_approach"},
    "mid": {"enter_next_subgoal_approach", "enter_post_completion_retreat"},
    "later": {"enter_next_subgoal_lift", "enter_x3a_actuation"},
}


def load_all() -> list[tuple[str, Path, dict]]:
    out = []
    for set_name, d in SETS.items():
        for path in sorted(d.glob("*.yaml")):
            out.append((set_name, path, yaml.safe_load(path.read_text())))
    return out


CASES = load_all()


def test_all_case_collections_are_present_and_populated() -> None:
    assert SETS
    for set_name, d in SETS.items():
        assert d.is_dir(), f"{set_name} missing"
        assert list(d.glob("*.yaml")), f"{set_name} is empty"


def test_case_ids_are_unique_across_sets() -> None:
    seen: dict[str, str] = {}
    for set_name, path, case in CASES:
        cid = case["case_id"]
        assert cid == path.stem, f"{path.name}: case_id must match the filename"
        assert cid not in seen, f"duplicate case_id {cid} in {set_name} and {seen.get(cid)}"
        seen[cid] = set_name


def test_current_catalog_contains_all_cases_and_all_tasks() -> None:
    manifest = yaml.safe_load((ROOT / "dataset/current/manifest.yaml").read_text())
    assert manifest["case_count"] == len(CASES)
    assert len(manifest["cases"]) == len(CASES)
    coverage = yaml.safe_load((ROOT / "dataset/current/coverage.yaml").read_text())
    assert [row["task_id"] for row in coverage["tasks"]] == [
        f"libero_10/{index:02d}" for index in range(10)
    ]
    assert sum(row["case_count"] for row in coverage["tasks"]) == len(CASES)
    assert coverage["tasks"][-1]["case_count"] > 0


def test_current_catalog_static_validation_is_clean() -> None:
    assert validate_dataset(ROOT / "dataset/current") == []


def test_every_case_is_schema_valid() -> None:
    for _, path, case in CASES:
        assert validate_case_data(case) == [], path


def test_schema_rejects_missing_required_field_and_unknown_property() -> None:
    case = copy.deepcopy(CASES[0][2])
    case.pop("case_id")
    case["unexpected_result"] = {"success": True}
    errors = validate_case_data(case)
    assert any("case_id" in error for error in errors)
    assert any("unexpected_result" in error for error in errors)


def test_schema_rejects_invalid_state_change_parameter() -> None:
    case = copy.deepcopy(next(case for _, _, case in CASES if case["severity"] == "n3"))
    case["rollback_target"]["state_change"]["offset_m"] = [0.1, 0.2]
    errors = validate_case_data(case)
    assert any("offset_m" in error for error in errors)


def progress_case(suffix):
    return yaml.safe_load((SETS["progress-failure"] / f"libero-10-{suffix}.yaml").read_text())


@pytest.mark.parametrize(
    "side,resolution,distance",
    [
        ("unknown", 0.002, 0.25),
        ("outside", 0, 0.25),
        ("outside", 0.002, -1),
    ],
)
def test_boundary_rejects_undefined_side_and_nonpositive_search(side, resolution, distance):
    case = progress_case("07-rollback-mid-d0-mug-boundary-outside-upright-restore")
    case["rollback_target"]["state_change"]["boundary"] = {
        "side": side,
        "resolution_m": resolution,
        "max_distance_m": distance,
    }
    assert validate_case_data(case)


def test_temporal_recovery_gate_requires_offset_and_hold():
    case = progress_case("03-rollback-mid-d0-pot-initial-upright-v2-restore")
    case["transient"].pop("hold_steps")
    assert validate_case_data(case)
    case = progress_case("03-rollback-mid-d0-pot-initial-upright-v2-restore")
    case["transient"].pop("offset_m")
    assert validate_case_data(case)


def test_relation_set_rejects_duplicates_undeclared_predicates_and_wrong_window():
    original = progress_case("03-rollback-all_done-d0-pot-relations-s1-upright-restore")
    case = copy.deepcopy(original)
    case["trigger"]["time_point"] = "mid"
    assert any("completion boundary" in e for e in validate_case_data(case))
    case = copy.deepcopy(original)
    case["rollback_target"]["state_change"]["relations"][1] = copy.deepcopy(
        case["rollback_target"]["state_change"]["relations"][0]
    )
    assert validate_case_data(case)
    case = copy.deepcopy(original)
    case["rollback_target"]["state_change"]["relations"][0]["predicate"][1] = "made_up_actor"
    assert any("declared completed" in e for e in validate_case_data(case))


def test_extensions_are_rejected_before_starting_an_unsupported_runtime(tmp_path):
    case = progress_case("03-rollback-all_done-d0-pot-relations-s1-upright-restore")
    with pytest.raises(RuntimeBridgeError, match="atomic_relation_set"):
        check_runtime_capabilities(case, tmp_path)


def test_reference_bindings_resolve_body_names_and_reject_unknown_entities():
    references = [
        case for _, _, case in CASES
        if case["rollback_target"]["state_change"]["kind"]
        in {"displace_reference_object", "translate_relation_pair"}
    ]
    for case in references:
        binding = runtime_binding(case)["perturbation_binding"]
        profile = yaml.safe_load(
            (ROOT / f"dataset/runtime-profiles/{binding['task_profile']}.yaml").read_text()
        )["task_profile"]
        payload = binding["enabled_cases"][0]["parameters"]["reference_object"]
        assert payload["reference_role"] in profile["roles"]
        assert profile["roles"][payload["reference_role"]]["kind"] == "body"
    case = copy.deepcopy(references[0])
    case["rollback_target"]["state_change"]["reference_role"] = "unknown_container"
    with pytest.raises(RuntimeBridgeError, match="no profile body role"):
        runtime_binding(case)
    case["rollback_target"]["state_change"]["reference_role"] = "agent_camera"
    with pytest.raises(RuntimeBridgeError, match="not a profile body role"):
        runtime_binding(case)


def test_bindings_preserve_temporal_target_and_functional_tolerance():
    case = progress_case("03-rollback-mid-d0-pot-initial-upright-v2-restore")
    entry = runtime_binding(case)["perturbation_binding"]["enabled_cases"][0]
    parameters = entry["parameters"]
    assert parameters["transient_pose"]["gate"] == "relation_recovered"
    assert parameters["transient_pose"]["hold_steps"] == 3
    # Temporal definitions select the first relation in actual completion order.
    assert "target_subgoal" not in parameters
    case = progress_case("09-rollback-all_done-d0-book-initial-upright-restore")
    entry = runtime_binding(case)["perturbation_binding"]["enabled_cases"][0]
    assert entry["parameters"]["target_subgoal"] == case["rollback_target"]["target_subgoal"]
    case = progress_case("00-rollback-mid-d0-target-joint-upright-setback1-v2-restore")
    entry = runtime_binding(case)["perturbation_binding"]["enabled_cases"][0]
    assert entry["parameters"]["position_tolerance"] == 0.05
    assert entry["parameters"]["functional_boundary"]["side"] == "outside"


def test_every_case_declares_a_known_position_label() -> None:
    for _, path, case in CASES:
        assert case["severity"] in POSITION_LABELS, f"{path.name}: severity {case['severity']!r}"


def test_every_case_declares_a_window_and_matching_event() -> None:
    for _, path, case in CASES:
        task = case["task"]["task_index"]
        window = case["trigger"]["time_point"]
        event = case["trigger"]["event"]
        if window == "all_done":
            assert event in {
                "enter_next_subgoal_completed",
                "enter_first_subgoal_completed",
                "enter_articulation_completed",
            }
            continue
        table = (
            ARTICULATION_WINDOW_EVENTS
            if task in NON_PLACEMENT_PAIR_TASKS
            else PLACEMENT_WINDOW_EVENTS
        )
        assert window in table, f"{path.name}: unknown window {window!r}"
        assert event in table[window], (
            f"{path.name}: task {task:02d} has no milestone {event!r} in the {window} window; "
            f"expected one of {sorted(table[window])}"
        )


def test_completion_events_are_enabled_in_every_catalog_profile() -> None:
    for _, path, case in CASES:
        if case["trigger"].get("time_point") != "all_done":
            continue
        locator = case["task"]["source_task_locator"][1:]
        profile = yaml.safe_load(
            (ROOT / f"dataset/runtime-profiles/libero_10_t{locator}.yaml").read_text()
        )["task_profile"]
        milestone = case["trigger"]["event"].removeprefix("enter_")
        assert milestone in profile["milestones"], f"{path.name}: disabled {milestone}"


def test_articulation_cases_never_target_a_placement_relation() -> None:
    for _, path, case in CASES:
        kind = case["rollback_target"]["state_change"]["kind"]
        if kind == ARTICULATION_KIND:
            assert case["task"]["task_index"] == 0, (
                f"{path.name}: only task 00 rolls back an articulation goal"
            )


def test_offset_cases_carry_a_three_component_offset() -> None:
    for _, path, case in CASES:
        change = case["rollback_target"]["state_change"]
        if change["kind"] != "apply_episode_initial_offset":
            continue
        offset = change.get("offset_m")
        assert isinstance(offset, list) and len(offset) == 3, f"{path.name}: bad offset_m"
        assert all(isinstance(v, (int, float)) for v in offset), f"{path.name}: non-numeric"


def test_container_above_is_only_used_where_it_is_meaningful() -> None:
    # the drawer (01) and microwave (02) tasks are the only ones with a container opening
    # that the rollback can lift the object above
    for _, path, case in CASES:
        change = case["rollback_target"]["state_change"]
        if change["kind"] == "restore_container_above_pose":
            assert case["task"]["task_index"] in {1, 2}, (
                f"{path.name}: container_above is only defined for tasks 01 and 02"
            )
            assert "clearance_max_m" in change, (
                f"{path.name}: without clearance_max_m the scan is capped at clearance_m"
            )


@pytest.mark.parametrize("set_name,path,case", CASES, ids=[p.stem for _, p, _ in CASES])
def test_binding_declares_the_same_offset_frame_as_the_case(set_name, path, case) -> None:
    change = case["rollback_target"]["state_change"]
    declared = change.get("offset_frame")
    if declared is None:
        pytest.skip("not an offset case")
    entry = runtime_binding(case)["perturbation_binding"]["enabled_cases"][0]
    assert entry["parameters"]["offset_frame"] == declared


@pytest.mark.parametrize("set_name,path,case", CASES, ids=[p.stem for _, p, _ in CASES])
def test_binding_forwards_a_declared_trigger_delay(set_name, path, case) -> None:
    delay = case["trigger"].get("delay_steps", 0)
    entry = runtime_binding(case)["perturbation_binding"]["enabled_cases"][0]
    if not delay:
        assert "delay_steps" not in entry["parameters"]
        return
    assert entry["parameters"]["delay_steps"] == delay


@pytest.mark.parametrize("set_name,path,case", CASES, ids=[p.stem for _, p, _ in CASES])
def test_binding_uses_the_placement_or_articulation_template(set_name, path, case) -> None:
    kind = case["rollback_target"]["state_change"]["kind"]
    entry = runtime_binding(case)["perturbation_binding"]["enabled_cases"][0]
    expected = (
        "hv_articulation_goal_rollback"
        if kind == ARTICULATION_KIND
        else "hv_completed_subgoal_rollback_grid"
    )
    assert entry["template"] == expected
