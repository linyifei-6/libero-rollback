"""Conservative interpretation of external evidence, independent of model SDKs."""

from collections.abc import Mapping
from typing import Any


def classify_result(case: Mapping[str, Any], episode: Mapping[str, Any] | None) -> str:
    if episode is None:
        return "incomplete"
    report = episode.get("report") or {}
    if (report.get("trigger") or {}).get("reached") is False:
        return "trigger_not_reached"
    valid = report.get("injection_valid", episode.get("injection_valid"))
    if valid is False:
        return "injection_invalid"
    if valid is not True:
        return "incomplete"
    observed = (report.get("intervention") or {}).get("observed") or {}
    pre, post = observed.get("pre_predicate"), observed.get("post_predicate")
    if report.get("rule_executed") is False or report.get("errors"):
        return "injection_invalid"
    if pre is not True:
        return "truth_unverified"
    if case.get("expected_evaluation_semantics") == "relation_holds_control":
        return "valid_control" if pre is True and post is True else "truth_unverified"
    if case.get("pose_role") == "measured_relation_probe" and post is True:
        return "valid_relation_preserving_probe"
    if post is not False:
        return "truth_unverified"
    change = case.get("rollback_target", {}).get("state_change", {})
    if change.get("kind") == "restore_native_relation_set":
        relations = observed.get("relations") or []
        expected = {tuple(str(x).lower() for x in r["predicate"]) for r in change["relations"]}
        actual = {tuple(str(x).lower() for x in r.get("predicate", [])) for r in relations}
        if (
            len(relations) != len(change["relations"])
            or any(r.get("pre") is not True or r.get("post") is not False for r in relations)
            or actual != expected
        ):
            return "truth_unverified"
    temporal = case.get("transient")
    if temporal:
        protocol = observed.get("temporal_protocol") or {}
        if protocol.get("complete") is not True or protocol.get("second_event_applied") is not True:
            return "protocol_incomplete"
        if temporal["destination"] == "pre_injection":
            # The evaluator restored the object, so the relation being true again is not model
            # repair.  No current case uses this destination (the `progress-pulse` family was
            # de-scoped on 2026-10-16); the branch is kept for archived runs and for a revival.
            return "valid_external_restoration"
    outcome = report.get("outcome") or {}
    if observed.get("repair_completed") is True and outcome.get("recovered") is True:
        if change.get("kind") == "restore_native_relation_set":
            final = observed.get("final_relation_states")
            if (
                not isinstance(final, list)
                or len(final) != len(expected)
                or any(truth is not True for truth in final)
            ):
                return "truth_unverified"
        return "valid_recovered"
    return "valid_not_recovered"
