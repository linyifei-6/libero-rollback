"""Prevent invalid injections and external repairs from becoming model scores."""

import copy

import pytest

from libero_rollback.evidence import classify_result


def episode():
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
def test_recovery_requires_valid_native_transition_and_explicit_repair(
    valid, executed, errors, pre, post, repair, recovered, expected
):
    data = episode()
    report = data["report"]
    report.update(injection_valid=valid, rule_executed=executed, errors=errors)
    report["intervention"]["observed"].update(
        pre_predicate=pre, post_predicate=post, repair_completed=repair
    )
    report["outcome"]["recovered"] = recovered
    assert classify_result({}, data) == expected


def test_control_and_pose_probe_are_never_model_recovery():
    data = episode()
    data["report"]["intervention"]["observed"]["post_predicate"] = True
    assert (
        classify_result({"expected_evaluation_semantics": "relation_holds_control"}, data)
        == "valid_control"
    )
    assert (
        classify_result({"pose_role": "measured_relation_probe"}, data)
        == "valid_relation_preserving_probe"
    )
    data["report"]["intervention"]["observed"].pop("pre_predicate")
    assert classify_result({"pose_role": "measured_relation_probe"}, data) == "truth_unverified"


def test_explicitly_absent_trigger_is_not_an_invalid_injection_or_model_failure():
    data = episode()
    data["report"]["trigger"] = {"reached": False}
    data["report"]["injection_valid"] = False
    assert classify_result({}, data) == "trigger_not_reached"


def test_external_restoration_and_incomplete_repeat_are_separate():
    data = episode()
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


def test_relation_set_requires_each_target_to_have_been_revoked():
    case = {
        "rollback_target": {
            "state_change": {
                "kind": "restore_native_relation_set",
                "relations": [{"predicate": ["on", "a", "b"]}, {"predicate": ["turnon", "c"]}],
            }
        }
    }
    data = episode()
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
    for predicates in (["on", "wrong", "b"], ["on", "a", "b"]):
        invalid = copy.deepcopy(data)
        invalid["report"]["intervention"]["observed"]["relations"][1]["predicate"] = predicates
        assert classify_result(case, invalid) == "truth_unverified"
    observed["final_relation_states"] = [True, False]
    assert classify_result(case, data) == "truth_unverified"
