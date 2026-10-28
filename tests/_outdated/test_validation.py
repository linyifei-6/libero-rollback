from pathlib import Path
from shutil import copytree

import pytest
import yaml

from libero_rollback.cli import _run_case_exit_code, _select_cases
from libero_rollback.runtime import _normalize_result, runtime_binding, source_task_index
from libero_rollback.validation import (
    check_manifest,
    load_yaml,
    schema_path,
    validate_case_data,
    validate_dataset,
)

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset" / "test-fixtures"


def test_published_case_is_valid() -> None:
    case_path = DATASET / "cases" / "libero-10-01-black-bowl-drawer-d0-early.yaml"
    case = load_yaml(case_path)
    assert validate_case_data(case) == []


def test_case_without_rollback_target_is_rejected() -> None:
    case = load_yaml(DATASET / "cases" / "libero-10-01-black-bowl-drawer-d0-early.yaml")
    del case["rollback_target"]
    errors = validate_case_data(case)
    assert any("rollback_target" in error for error in errors)


def test_case_cannot_contain_run_results() -> None:
    case = load_yaml(DATASET / "cases" / "libero-10-01-black-bowl-drawer-d0-early.yaml")
    case["run_result"] = {"success": True}
    errors = validate_case_data(case)
    assert any("run_result" in error for error in errors)


def test_dynamic_completed_relation_selector_is_valid() -> None:
    case_path = (
        DATASET / "cases" / "libero-10-03-first-moka-pot-stove-checkpoint-pregrasp-early.yaml"
    )
    case = load_yaml(case_path)
    assert validate_case_data(case) == []


def test_dataset_rejects_unknown_supporting_source(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    copytree(ROOT / "schemas", repo_root / "schemas")
    copytree(DATASET, repo_root / "dataset" / "test-fixtures")
    case_path = repo_root / "dataset/test-fixtures/cases/libero-10-01-black-bowl-drawer-d0-early.yaml"
    case = load_yaml(case_path)
    case["source"]["supporting_source_ids"] = ["missing-source"]
    case_path.write_text(yaml.safe_dump(case, sort_keys=False), encoding="utf-8")

    errors = validate_dataset(repo_root / "dataset" / "test-fixtures")
    assert any("unknown supporting source_id" in error for error in errors)


def test_dataset_rejects_case_missing_template_constraints(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    copytree(ROOT / "schemas", repo_root / "schemas")
    copytree(DATASET, repo_root / "dataset" / "test-fixtures")
    case_path = repo_root / "dataset/test-fixtures/cases/libero-10-01-black-bowl-drawer-d0-early.yaml"
    case = load_yaml(case_path)
    case["validity_constraints"].remove("task_remains_solvable")
    case_path.write_text(yaml.safe_dump(case, sort_keys=False), encoding="utf-8")

    errors = validate_dataset(repo_root / "dataset" / "test-fixtures")
    assert any("template constraints missing" in error for error in errors)


def test_dataset_rejects_task_id_index_mismatch(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    copytree(ROOT / "schemas", repo_root / "schemas")
    copytree(DATASET, repo_root / "dataset" / "test-fixtures")
    coverage_path = repo_root / "dataset/test-fixtures/coverage.yaml"
    coverage = load_yaml(coverage_path)
    coverage["tasks"][0]["task_id"] = "libero_10/09"
    coverage_path.write_text(yaml.safe_dump(coverage, sort_keys=False), encoding="utf-8")

    errors = validate_dataset(repo_root / "dataset" / "test-fixtures")
    assert any("task_id must be libero_10/00" in error for error in errors)


def test_all_cases_and_coverage_are_consistent() -> None:
    assert validate_dataset(DATASET) == []


def test_full_suite_release_covers_every_task_and_level() -> None:
    release = ROOT / "dataset" / "v1.1"
    assert validate_dataset(release) == []
    assert check_manifest(release) == []
    manifest = load_yaml(release / "manifest.yaml")
    levels_by_task: dict[str, set[str]] = {}
    for entry in manifest["cases"]:
        case = load_yaml(ROOT / entry["path"])
        levels_by_task.setdefault(case["task"]["task_id"], set()).add(case["severity"])
        if case["task"]["task_index"] in {0, 4, 5, 6, 8, 9}:
            assert case["source"]["case_source_id"] == "dataset-full-suite-design-20261009"
        binding = runtime_binding(case)["perturbation_binding"]["enabled_cases"][0]
        assert binding["trigger_event"] == case["trigger"]["event"]
    assert set(levels_by_task) == {f"libero_10/{index:02d}" for index in range(10)}
    assert all(
        levels == {"d0", "d1", "d2", "d3", "checkpoint"}
        for levels in levels_by_task.values()
    )
    assert len(manifest["cases"]) == 50


def test_manifest_references_and_digests_are_valid() -> None:
    assert check_manifest(DATASET) == []


def test_evaluation_selection_scales_from_case_to_task_and_full_dataset() -> None:
    one_case = _select_cases(
        DATASET,
        [],
        False,
        ["libero-10-01-black-bowl-drawer-d0-early"],
        [],
    )
    task_cases = _select_cases(DATASET, [], False, [], ["libero_10/01"])
    all_cases = _select_cases(DATASET, [], True, [], [])
    assert len(one_case) == 1
    assert len(task_cases) == 5
    assert len(all_cases) == 20
    assert {path for _, path in task_cases} <= {path for _, path in all_cases}


def test_manifest_rejects_changed_file_digest(tmp_path: Path) -> None:
    dataset_root = tmp_path / "dataset" / "v1"
    dataset_root.mkdir(parents=True)
    referenced_file = dataset_root / "metadata.yaml"
    referenced_file.write_text("value: original\n", encoding="utf-8")
    manifest = {
        "schema_file": "dataset/test-fixtures/metadata.yaml",
        "coverage_file": "dataset/test-fixtures/metadata.yaml",
        "sources_file": "dataset/test-fixtures/metadata.yaml",
        "cases": [],
        "files": [{"path": "dataset/test-fixtures/metadata.yaml", "sha256": "0" * 64}],
    }
    (dataset_root / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")

    errors = check_manifest(dataset_root)
    assert any("SHA-256 mismatch" in error for error in errors)


def test_dataset_rejects_rollback_target_not_declared_completed(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    copytree(ROOT / "schemas", repo_root / "schemas")
    copytree(DATASET, repo_root / "dataset" / "test-fixtures")
    case_path = repo_root / "dataset/test-fixtures/cases/libero-10-01-black-bowl-drawer-d0-early.yaml"
    case = load_yaml(case_path)
    case["rollback_target"]["predicate"] = "(Close white_cabinet_1_bottom_region)"
    case_path.write_text(yaml.safe_dump(case, sort_keys=False), encoding="utf-8")

    errors = validate_dataset(repo_root / "dataset" / "test-fixtures")
    assert any("rollback target is not listed as completed" in error for error in errors)


def test_schema_is_versioned() -> None:
    schema = load_yaml(schema_path())
    assert schema["$id"] == "urn:libero-rollback:schema:case:v1"


def test_runtime_binding_preserves_case_state_change() -> None:
    case = load_yaml(DATASET / "cases" / "libero-10-01-black-bowl-drawer-d1-early.yaml")
    binding = runtime_binding(case)["perturbation_binding"]
    assert source_task_index(case) == 33
    enabled = binding["enabled_cases"][0]
    assert binding["task_profile"] == "libero_10_t33"
    assert enabled["parameters"]["destination"] == "initial_offset"
    assert enabled["parameters"]["offset_m"] == [0.05, 0.05, 0.0]
    assert enabled["severities"] == ["l1_small_diagonal"]


@pytest.mark.parametrize(
    ("suffix", "level", "variant", "offset", "event"),
    [
        ("d0-early", "d0", "l1_t0", None, "enter_first_subgoal_completed"),
        (
            "d1-early",
            "d1",
            "l1_small_diagonal",
            [0.05, 0.05, 0.0],
            "enter_first_subgoal_completed",
        ),
        (
            "d2-early",
            "d2",
            "l2_side_diagonal",
            [-0.08, 0.06, 0.0],
            "enter_first_subgoal_completed",
        ),
        (
            "d3-early",
            "d3",
            "l2_large_diagonal",
            [0.10, 0.08, 0.0],
            "enter_first_subgoal_completed",
        ),
        (
            "checkpoint-pregrasp-early",
            "checkpoint",
            "l2_pregrasp_checkpoint",
            None,
            "enter_next_subgoal_approach",
        ),
    ],
)
def test_levels_preserve_source_transform_and_trigger(
    suffix: str, level: str, variant: str, offset: list[float] | None, event: str
) -> None:
    case = load_yaml(DATASET / "cases" / f"libero-10-07-white-mug-left-plate-{suffix}.yaml")
    assert validate_case_data(case) == []
    assert case["severity"] == level
    enabled = runtime_binding(case)["perturbation_binding"]["enabled_cases"][0]
    assert enabled["severities"] == [variant]
    assert enabled["parameters"].get("offset_m") == offset
    assert enabled["trigger_event"] == event


@pytest.mark.parametrize("legacy_level", ["r00", "r02", "r03", "r04", "unrated"])
def test_legacy_level_is_rejected(legacy_level: str) -> None:
    case = load_yaml(DATASET / "cases" / "libero-10-01-black-bowl-drawer-d0-early.yaml")
    case["severity"] = legacy_level
    assert any(error.startswith("severity:") for error in validate_case_data(case))
    with pytest.raises(ValueError, match="no external runtime severity mapping"):
        runtime_binding(case)


def test_runtime_binding_rejects_unknown_state_change() -> None:
    case = load_yaml(DATASET / "cases" / "libero-10-01-black-bowl-drawer-d0-early.yaml")
    case["rollback_target"]["state_change"]["kind"] = "invented_state_change"
    import pytest

    with pytest.raises(ValueError, match="no external runtime mapping"):
        runtime_binding(case)


def test_runtime_result_preserves_observed_relation_transition() -> None:
    case = load_yaml(DATASET / "cases/libero-10-01-black-bowl-drawer-d0-early.yaml")
    runner_document = {
        "LIBERO_10_T33": {
            "results": {
                "baseline_s0": {"kind": "baseline", "seed": 0, "success": True},
                "case_s0": {
                    "kind": "perturbation",
                    "seed": 0,
                    "success": False,
                    "report": {
                        "rule_executed": True,
                        "injection_step": 151,
                        "trigger": {"reached": True, "step": 151},
                        "intervention": {
                            "observed": {"pre_predicate": True, "post_predicate": False}
                        },
                        "injection_valid": True,
                    },
                },
            }
        }
    }

    result = _normalize_result(
        case,
        seed=0,
        adapter="test-adapter",
        checkpoint="/tmp/checkpoint",
        returncode=0,
        output_dir=Path("runs/test"),
        runner_result_path=Path("runs/test/results.json"),
        runner_document=runner_document,
    )

    assert result["trigger_reached"] is True
    assert result["state_change_applied"] is True
    assert result["pre_relation"] is True
    assert result["post_relation"] is False


def test_valid_negative_runtime_outcome_is_not_a_bridge_failure() -> None:
    assert (
        _run_case_exit_code(
            {
                "runner_result_path": "runs/result.json",
                "injection_valid": True,
                "runner_returncode": 2,
            }
        )
        == 0
    )
    assert (
        _run_case_exit_code(
            {
                "runner_result_path": "runs/result.json",
                "injection_valid": False,
                "runner_returncode": 2,
            }
        )
        == 2
    )

GRID = ROOT / "dataset" / "v1.2"

# Cases per task in the 1.2.0 grid release, bounded by the runtime dimensions each
# task profile actually exposes (see docs/runtime-dimension-grid.md).
GRID_CASE_COUNTS = {
    "libero_10/00": 6,
    "libero_10/01": 33,
    "libero_10/02": 33,
    "libero_10/03": 18,
    "libero_10/04": 18,
    "libero_10/05": 18,
    "libero_10/06": 18,
    "libero_10/07": 18,
    "libero_10/08": 18,
    "libero_10/09": 6,
}


def test_grid_release_is_valid_and_complete() -> None:
    """The 1.2.0 grid release: schema, cross-references, counts and digests."""

    assert validate_dataset(GRID) == []
    assert check_manifest(GRID) == []
    manifest = load_yaml(GRID / "manifest.yaml")
    assert len(manifest["cases"]) == sum(GRID_CASE_COUNTS.values())
    seen: dict[str, int] = {}
    for entry in manifest["cases"]:
        case = load_yaml(ROOT / entry["path"])
        assert validate_case_data(case) == []
        seen[case["task"]["task_id"]] = seen.get(case["task"]["task_id"], 0) + 1
    assert seen == GRID_CASE_COUNTS


def test_grid_release_covers_every_runtime_dimension() -> None:
    """Time points, destination classes and both goal kinds must all be present."""

    manifest = load_yaml(GRID / "manifest.yaml")
    cases = [load_yaml(ROOT / entry["path"]) for entry in manifest["cases"]]
    assert {case["trigger"]["event"] for case in cases} == {
        "enter_first_subgoal_completed",
        "enter_next_subgoal_approach",
        "enter_next_subgoal_lift",
        "enter_post_completion_retreat",
        "enter_x3a_actuation",
        "enter_articulation_completed",
    }
    assert {case["rollback_target"]["state_change"]["kind"] for case in cases} == {
        "restore_episode_initial_pose",
        "apply_episode_initial_offset",
        "restore_captured_checkpoint_pose",
        "restore_container_above_pose",
        "revert_articulation_goal",
    }
    # only the two articulation tasks can revoke a closure goal
    articulation = [case for case in cases if case["severity"] == "articulation"]
    assert {case["task"]["task_id"] for case in articulation} == {
        "libero_10/01",
        "libero_10/02",
    }
    # container hover is limited to the tasks whose goal region resolves
    above = [case for case in cases if case["severity"] == "above"]
    assert {case["task"]["task_id"] for case in above} == {"libero_10/01", "libero_10/02"}


def test_grid_cases_bind_to_the_runtime_without_losing_dimensions() -> None:
    """Every grid case must produce a binding that keeps its dimension."""

    manifest = load_yaml(GRID / "manifest.yaml")
    for entry in manifest["cases"]:
        case = load_yaml(ROOT / entry["path"])
        enabled = runtime_binding(case)["perturbation_binding"]["enabled_cases"][0]
        assert enabled["trigger_event"] == case["trigger"]["event"]
        assert len(enabled["severities"]) == 1
        parameters = enabled["parameters"]
        kind = case["rollback_target"]["state_change"]["kind"]
        if kind == "revert_articulation_goal":
            assert enabled["template"] == "hv_articulation_goal_rollback"
            # the articulation handler validates its parameter set by equality
            assert "destination" not in parameters
            assert parameters["zero_velocity"] is True
        else:
            assert enabled["template"] == "hv_completed_subgoal_rollback_grid"
            assert parameters["destination"] in {
                "initial_pose",
                "initial_offset",
                "checkpoint",
                "container_above",
            }
        if kind == "apply_episode_initial_offset":
            assert parameters["offset_m"] == case["rollback_target"]["state_change"]["offset_m"]
            assert parameters["offset_frame"] == "task_frame"
        if kind == "restore_container_above_pose":
            assert parameters["clearance_m"] > 0
