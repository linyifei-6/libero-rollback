"""Verdict tests for the migrated evidence layer (docs/SPEC.md §6.1)."""

from __future__ import annotations

import copy

import pytest

from libero_rollback.evidence import (
    CONTROL_VERDICTS,
    RECOVERY_VERDICTS,
    VERDICTS,
    classify_episode,
    classify_result,
)


def v2_summary(**overrides) -> dict:
    """A v2 B-runner summary with every field run_b_matrix.run_case writes."""

    summary = {
        "status": "ok",
        "case_id": "b-goal-t000-g-l0",
        "suite": "goal",
        "task_idx": 0,
        "level": "L0",
        "param": None,
        "target": "g",
        "family": "joint",
        "semantics": "relation_then_resume",
        "expected_relation_after": False,
        "trigger_reached": True,
        "trigger_step": 120,
        "injection_step": 120,
        "injection": {
            "kind": "init",
            "goal_before": [True],
            "revoked_before": [True],
            "goal_after": [False],
            "revoked_after": [False],
            "relation_after": False,
            "expected_relation_after": False,
            "goal_preserved": None,
            "applied": [{"target": "wooden_cabinet_1", "mode": "init"}],
            "no_penetration": True,
            "zero_velocity": True,
            "object_released": True,
            "restorable": True,
        },
        "relation_before": True,
        "relation_after_injection": False,
        "relation_final": True,
        "recovered": True,
        "recovery": True,
        "recovery_ever": True,
        "case_valid": True,
        "validity": {
            "completed_relation_true_before_intervention": True,
            "all_revoked_false_after_intervention": True,
            "no_object_penetration": True,
            "zero_velocity_after_intervention": True,
            "object_released_before_intervention": True,
            "restorable": True,
        },
        "success": False,
        "final_goal_truth": [False],
        "final_revoked_truth": [True],
    }
    summary.update(overrides)
    return summary


def control_summary(**overrides) -> dict:
    summary = v2_summary(
        case_id="b-goal-t000-c0",
        level="C0",
        target="c0",
        semantics="relation_holds_control",
        expected_relation_after=True,
        injection={
            "kind": "c0",
            "goal_before": [True],
            "revoked_before": [],
            "goal_after": [True],
            "revoked_after": [],
            "relation_after": True,
            "expected_relation_after": True,
            "applied": [],
            "no_penetration": True,
            "zero_velocity": True,
            "object_released": True,
            "restorable": True,
        },
        relation_before=True,
        relation_after_injection=True,
        relation_final=True,
        recovered=True,
        recovery=None,
        case_valid=True,
        success=True,
        final_goal_truth=[True],
        final_revoked_truth=[],
    )
    summary.update(overrides)
    return summary


# ---------------------------------------------------------------------------
# v2 runner summaries
# ---------------------------------------------------------------------------


def test_v2_summary_recovered() -> None:
    assert classify_episode(v2_summary()) == "valid_recovered"


def test_v2_summary_not_recovered() -> None:
    summary = v2_summary(
        relation_final=False,
        recovered=False,
        recovery=False,
        final_revoked_truth=[False],
    )
    assert classify_episode(summary) == "valid_not_recovered"


def test_v2_trigger_not_reached_is_not_zero_percent() -> None:
    summary = v2_summary(
        trigger_reached=False,
        trigger_skipped_reason="all_done not reached within max_steps",
        injection=None,
        relation_before=False,
        relation_after_injection=None,
        relation_final=None,
        recovered=None,
        recovery=None,
        case_valid=False,
        validity={"trigger_reached": False},
    )
    assert classify_episode(summary) == "trigger_not_reached"


def test_v2_explicitly_invalid_injection_is_not_model_failure() -> None:
    summary = v2_summary(case_valid=False)
    summary["injection"]["no_penetration"] = False
    assert classify_episode(summary) == "injection_invalid"
    assert classify_episode(v2_summary(status="invalid_perturbation")) == "injection_invalid"


def test_v2_unverified_pre_relation_is_truth_unverified() -> None:
    summary = v2_summary(relation_before=False)
    summary["validity"]["completed_relation_true_before_intervention"] = False
    assert classify_episode(summary) == "truth_unverified"


def test_v2_failed_revocation_is_truth_unverified() -> None:
    summary = v2_summary(relation_after_injection=True, recovered=False, relation_final=False)
    summary["injection"]["relation_after"] = True
    summary["injection"]["revoked_after"] = [True]
    assert classify_episode(summary) == "truth_unverified"


def test_v2_empty_state_write_is_injection_invalid() -> None:
    summary = v2_summary()
    summary["injection"]["applied"] = []
    assert classify_episode(summary) == "injection_invalid"


def test_v2_error_and_running_documents_are_incomplete() -> None:
    assert classify_episode(v2_summary(status="error")) == "incomplete"
    assert classify_episode(v2_summary(status="running")) == "incomplete"
    assert classify_episode({}) == "incomplete"
    assert classify_episode(None) == "incomplete"


def test_v2_missing_injection_is_incomplete() -> None:
    assert classify_episode(v2_summary(injection=None)) == "incomplete"


def test_v2_explicit_protocol_incomplete() -> None:
    summary = v2_summary(protocol_complete=False)
    assert classify_episode(summary) == "protocol_incomplete"
    transient = v2_summary()
    transient["temporal_protocol"] = {"complete": True, "second_event_applied": False}
    assert classify_episode(transient) == "protocol_incomplete"


def test_v2_external_restoration_is_not_model_recovery() -> None:
    assert classify_episode(v2_summary(external_restoration=True)) == "valid_external_restoration"


def test_v2_relation_preserving_probe_is_its_own_verdict() -> None:
    summary = v2_summary(
        semantics="relation_preserving_probe",
        expected_relation_after=True,
        relation_after_injection=True,
        recovered=True,
        relation_final=True,
    )
    summary["injection"]["relation_after"] = True
    summary["injection"]["revoked_after"] = [True]
    assert classify_episode(summary) == "valid_relation_preserving_probe"


def test_v2_control_pass_and_fail() -> None:
    assert classify_episode(control_summary()) == "valid_control"
    failed = control_summary(case_valid=False, success=False, final_goal_truth=[False])
    assert classify_episode(failed) == "valid_not_recovered"


def test_classify_result_dispatches_v2_summaries() -> None:
    assert classify_result({}, v2_summary()) == "valid_recovered"


# ---------------------------------------------------------------------------
# legacy (v1) evidence documents - semantics preserved
# ---------------------------------------------------------------------------


def legacy_episode() -> dict:
    return {
        "report": {
            "injection_valid": True,
            "rule_executed": True,
            "errors": [],
            "intervention": {
                "observed": {
                    "pre_predicate": True,
                    "post_predicate": False,
                    "repair_completed": True,
                }
            },
            "outcome": {"recovered": True},
        }
    }


@pytest.mark.parametrize(
    "valid,executed,errors,pre,post,repair,recovered,expected",
    [
        (True, True, [], True, False, True, True, "valid_recovered"),
        (False, True, [], True, False, True, True, "injection_invalid"),
        (True, False, [], True, False, True, True, "injection_invalid"),
        (True, True, [{"name": "penetration"}], True, False, True, True, "injection_invalid"),
        (None, True, [], True, False, True, True, "incomplete"),
        (True, True, [], False, False, True, True, "truth_unverified"),
        (True, True, [], None, False, True, True, "truth_unverified"),
        (True, True, [], True, True, True, True, "truth_unverified"),
        (True, True, [], True, False, False, True, "valid_not_recovered"),
        (True, True, [], True, False, True, False, "valid_not_recovered"),
    ],
)
def test_legacy_recovery_requires_valid_transition_and_explicit_repair(
    valid, executed, errors, pre, post, repair, recovered, expected
) -> None:
    data = legacy_episode()
    report = data["report"]
    report.update(injection_valid=valid, rule_executed=executed, errors=errors)
    report["intervention"]["observed"].update(
        pre_predicate=pre, post_predicate=post, repair_completed=repair
    )
    report["outcome"]["recovered"] = recovered
    assert classify_result({}, data) == expected


def test_legacy_control_and_probe_are_never_model_recovery() -> None:
    data = legacy_episode()
    data["report"]["intervention"]["observed"]["post_predicate"] = True
    control = {"expected_evaluation_semantics": "relation_holds_control"}
    assert classify_result(control, data) == "valid_control"
    probe = {"pose_role": "measured_relation_probe"}
    assert classify_result(probe, data) == "valid_relation_preserving_probe"
    data["report"]["intervention"]["observed"].pop("pre_predicate")
    assert classify_result(probe, data) == "truth_unverified"


def test_legacy_absent_trigger_is_trigger_not_reached() -> None:
    data = legacy_episode()
    data["report"]["trigger"] = {"reached": False}
    data["report"]["injection_valid"] = False
    assert classify_result({}, data) == "trigger_not_reached"


def test_legacy_external_restoration_and_temporal_protocol() -> None:
    data = legacy_episode()
    case = {"transient": {"destination": "pre_injection"}}
    observed = data["report"]["intervention"]["observed"]
    assert classify_result(case, data) == "protocol_incomplete"
    observed["temporal_protocol"] = {"complete": True, "second_event_applied": False}
    assert classify_result(case, data) == "protocol_incomplete"
    observed["temporal_protocol"]["second_event_applied"] = True
    assert classify_result(case, data) == "valid_external_restoration"
    case["transient"]["destination"] = "initial_offset"
    assert classify_result(case, data) == "valid_recovered"
    observed["repair_completed"] = False
    assert classify_result(case, data) == "valid_not_recovered"


def test_legacy_relation_set_requires_each_target_to_have_been_revoked() -> None:
    case = {
        "rollback_target": {
            "state_change": {
                "kind": "restore_native_relation_set",
                "relations": [{"predicate": ["on", "a", "b"]}, {"predicate": ["turnon", "c"]}],
            }
        }
    }
    data = legacy_episode()
    observed = data["report"]["intervention"]["observed"]
    assert classify_result(case, data) == "truth_unverified"
    observed["relations"] = [
        {"predicate": ["on", "a", "b"], "pre": True, "post": False},
        {"predicate": ["turnon", "c"], "pre": True, "post": False},
    ]
    observed["final_relation_states"] = [True, True]
    assert classify_result(case, data) == "valid_recovered"
    invalid = copy.deepcopy(data)
    invalid["report"]["intervention"]["observed"]["relations"][1]["post"] = True
    assert classify_result(case, invalid) == "truth_unverified"
    invalid = copy.deepcopy(data)
    invalid["report"]["intervention"]["observed"]["relations"][1]["predicate"] = [
        "on",
        "wrong",
        "b",
    ]
    assert classify_result(case, invalid) == "truth_unverified"
    observed["final_relation_states"] = [True, False]
    assert classify_result(case, data) == "truth_unverified"


def test_every_reported_verdict_is_in_the_frozen_verdict_set() -> None:
    samples = [
        classify_episode(v2_summary()),
        classify_episode(v2_summary(trigger_reached=False)),
        classify_episode(control_summary()),
        classify_result({}, legacy_episode()),
        classify_result({}, None),
    ]
    assert set(samples) <= set(VERDICTS)
    assert RECOVERY_VERDICTS == {"valid_recovered", "valid_not_recovered"}
    assert CONTROL_VERDICTS == {"valid_control"}
