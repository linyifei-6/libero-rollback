"""Conservative episode-verdict classification for the rollback contract.

Verdicts are fixed by ``docs/SPEC.md`` §6.1::

    valid_recovered / valid_not_recovered / valid_control /
    valid_relation_preserving_probe / valid_external_restoration /
    injection_invalid / trigger_not_reached / truth_unverified /
    protocol_incomplete / incomplete

Two entry points are provided:

``classify_result(case, episode)``
    Legacy (v1) evidence documents, migrated from the precursor data
    repository. The episode document carries a ``report`` mapping and the
    semantics are preserved exactly, because archived v1 runs must keep
    classifying as they did before the migration.

``classify_episode(summary)``
    The v2 B/D runner ``summary.json`` format written by
    ``run_b_matrix.run_case`` (``status`` / ``trigger_reached`` /
    ``injection`` / ``relation_before`` / ``relation_after_injection`` /
    ``relation_final`` / ``recovered`` / ``case_valid`` / ``validity`` /
    ``level`` / ``semantics``). This is the format the current runner emits.

The module is pure stdlib so the evidence layer never needs the simulator.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

VERDICTS = (
    "valid_recovered",
    "valid_not_recovered",
    "valid_control",
    "valid_relation_preserving_probe",
    "valid_external_restoration",
    "injection_invalid",
    "trigger_not_reached",
    "truth_unverified",
    "protocol_incomplete",
    "incomplete",
)

RECOVERY_VERDICTS = frozenset({"valid_recovered", "valid_not_recovered"})
CONTROL_VERDICTS = frozenset({"valid_control"})

_STATUS_INVALID = frozenset({"invalid_perturbation", "invalid-injection", "injection_invalid"})
_STATUS_OK = frozenset({"ok"})
_SUMMARY_KEYS = frozenset(
    {
        "status",
        "trigger_reached",
        "trigger_skipped_reason",
        "case_valid",
        "injection",
        "relation_before",
        "relation_after_injection",
        "relation_final",
        "recovered",
        "recovery",
        "validity",
    }
)


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def classify_result(case: Mapping[str, Any], episode: Mapping[str, Any] | None) -> str:
    """Classify one v1 episode result (legacy API) or dispatch a v2 summary.

    ``episode`` may be either the legacy evidence document (``report`` key) or
    a v2 runner summary. The v1 path is byte-for-byte compatible with the
    released classifier.
    """

    if episode is None or not isinstance(episode, Mapping):
        return "incomplete"
    if "report" not in episode and any(key in episode for key in _SUMMARY_KEYS):
        return classify_episode(episode)
    return _classify_legacy(case or {}, episode)


def classify_episode(summary: Mapping[str, Any] | None) -> str:
    """Classify one v2 runner ``summary.json`` document.

    Precedence (same spirit as the v1 classifier):

    1. error/invalid run documents are never evidence (``incomplete`` /
       ``injection_invalid``);
    2. an explicitly incomplete protocol is ``protocol_incomplete``;
    3. a missing trigger is ``trigger_not_reached`` (never 0 %, never an
       invalid injection);
    4. a control (``C0``) episode can only be ``valid_control``;
    5. a revocation whose pre-relation is unverified, whose state write failed
       or whose "after" relation is not false is never a model recovery;
    6. only then does the model's final relation decide
       ``valid_recovered`` / ``valid_not_recovered``.
    """

    if not isinstance(summary, Mapping) or not summary:
        return "incomplete"

    status = summary.get("status")
    if isinstance(status, str):
        normalised = status.strip().lower()
        if normalised in _STATUS_INVALID:
            return "injection_invalid"
        if normalised not in _STATUS_OK:
            return "incomplete"

    if _protocol_incomplete(summary):
        return "protocol_incomplete"

    injected = _injection(summary) is not None or summary.get("injected") is True
    trigger = _trigger_state(summary)
    if trigger is False:
        return "trigger_not_reached"
    if trigger is None and not injected:
        return "incomplete"

    if _is_control(summary):
        return _classify_control(summary)
    return _classify_rollback(summary)


# ---------------------------------------------------------------------------
# legacy (v1) classifier - semantics preserved
# ---------------------------------------------------------------------------


def _classify_legacy(case: Mapping[str, Any], episode: Mapping[str, Any]) -> str:
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
    rollback_target = case.get("rollback_target") or {}
    change = rollback_target.get("state_change") or {}
    if change.get("kind") == "restore_native_relation_set":
        relations = observed.get("relations") or []
        expected = {
            tuple(str(token).lower() for token in relation["predicate"])
            for relation in change["relations"]
        }
        actual = {
            tuple(str(token).lower() for token in relation.get("predicate", []))
            for relation in relations
        }
        if (
            len(relations) != len(change["relations"])
            or any(
                relation.get("pre") is not True or relation.get("post") is not False
                for relation in relations
            )
            or actual != expected
        ):
            return "truth_unverified"
    temporal = case.get("transient")
    if temporal:
        protocol = observed.get("temporal_protocol") or {}
        if protocol.get("complete") is not True or protocol.get("second_event_applied") is not True:
            return "protocol_incomplete"
        if temporal["destination"] == "pre_injection":
            # The evaluator restored the object, so the relation becoming true again is not
            # model repair. No current case uses this destination (the progress-pulse family
            # was de-scoped on 2026-10-16); the branch is kept for archived runs.
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


# ---------------------------------------------------------------------------
# v2 summary helpers
# ---------------------------------------------------------------------------


def _injection(summary: Mapping[str, Any]) -> Mapping[str, Any] | None:
    injection = summary.get("injection")
    return injection if isinstance(injection, Mapping) else None


def _validity(summary: Mapping[str, Any]) -> Mapping[str, Any]:
    validity = summary.get("validity")
    return validity if isinstance(validity, Mapping) else {}


def _is_control(summary: Mapping[str, Any]) -> bool:
    if summary.get("is_control") is True:
        return True
    level = summary.get("level")
    if isinstance(level, str) and level.strip().upper() == "C0":
        return True
    target = summary.get("target")
    if isinstance(target, str) and target.strip().lower() == "c0":
        return True
    semantics = summary.get("semantics")
    if isinstance(semantics, str) and "control" in semantics.lower():
        return True
    expected = summary.get("expected_evaluation_semantics")
    return isinstance(expected, str) and expected == "relation_holds_control"


def _is_probe(summary: Mapping[str, Any]) -> bool:
    if summary.get("probe") is True or _validity(summary).get("probe") is True:
        return True
    semantics = summary.get("semantics")
    if isinstance(semantics, str) and "probe" in semantics.lower():
        return True
    return summary.get("expected_relation_after") is True and not _is_control(summary)


def _trigger_state(summary: Mapping[str, Any]) -> bool | None:
    if _validity(summary).get("trigger_reached") is False:
        return False
    value = summary.get("trigger_reached")
    if isinstance(value, bool):
        return value
    if summary.get("trigger_skipped_reason"):
        return False
    return None


def _bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _relation_before(summary: Mapping[str, Any]) -> bool | None:
    value = _bool_or_none(summary.get("relation_before"))
    if value is not None:
        return value
    value = _bool_or_none(_validity(summary).get("completed_relation_true_before_intervention"))
    if value is not None:
        return value
    injection = _injection(summary) or {}
    revoked_before = injection.get("revoked_before")
    if isinstance(revoked_before, (list, tuple)) and revoked_before:
        return all(item is True for item in revoked_before)
    return None


def _relation_after(summary: Mapping[str, Any]) -> bool | None:
    value = _bool_or_none(summary.get("relation_after_injection"))
    if value is not None:
        return value
    injection = _injection(summary) or {}
    value = _bool_or_none(injection.get("relation_after"))
    if value is not None:
        return value
    revoked_after = injection.get("revoked_after")
    if isinstance(revoked_after, (list, tuple)) and revoked_after:
        return all(item is True for item in revoked_after)
    return None


def _relation_final(summary: Mapping[str, Any]) -> bool | None:
    value = _bool_or_none(summary.get("relation_final"))
    if value is not None:
        return value
    return _bool_or_none(summary.get("recovered"))


def _goal_success(summary: Mapping[str, Any]) -> bool | None:
    value = _bool_or_none(summary.get("success"))
    if value is not None:
        return value
    final_goal = summary.get("final_goal_truth")
    if isinstance(final_goal, (list, tuple)):
        return all(item is True for item in final_goal)
    return None


def _gate_failure(summary: Mapping[str, Any]) -> str | None:
    """Return the first failed injection gate name, or ``None``.

    Only *explicit* false values count: older archived summaries may not carry
    every gate, and a missing gate is "unverified", not "failed".
    """

    validity = _validity(summary)
    injection = _injection(summary) or {}
    checks: tuple[tuple[str, bool | None, bool | None], ...] = (
        (
            "no_object_penetration",
            _bool_or_none(validity.get("no_object_penetration")),
            _bool_or_none(injection.get("no_penetration")),
        ),
        (
            "zero_velocity_after_intervention",
            _bool_or_none(validity.get("zero_velocity_after_intervention")),
            _bool_or_none(injection.get("zero_velocity")),
        ),
        (
            "object_released_before_intervention",
            _bool_or_none(validity.get("object_released_before_intervention")),
            _bool_or_none(injection.get("object_released")),
        ),
    )
    for name, verdict_value, raw_value in checks:
        if verdict_value is False or raw_value is False:
            return name
    return None


def _protocol_incomplete(summary: Mapping[str, Any]) -> bool:
    if summary.get("protocol_complete") is False:
        return True
    validity = _validity(summary)
    if validity.get("protocol_complete") is False:
        return True
    if summary.get("temporal_protocol") is not None and not _protocol_events_complete(
        summary.get("temporal_protocol")
    ):
        return True
    if validity.get("temporal_protocol") is not None and not _protocol_events_complete(
        validity.get("temporal_protocol")
    ):
        return True
    return False


def _protocol_events_complete(protocol: Any) -> bool:
    if not isinstance(protocol, Mapping):
        return True
    return not (protocol.get("complete") is False or protocol.get("second_event_applied") is False)


def _external_restoration(summary: Mapping[str, Any]) -> bool:
    if summary.get("external_restoration") is True or summary.get("restored_externally") is True:
        return True
    if _validity(summary).get("external_restoration") is True:
        return True
    source = summary.get("recovery_source")
    return isinstance(source, str) and source.strip().lower() in {"external", "oracle", "evaluator"}


# ---------------------------------------------------------------------------
# v2 branch classifiers
# ---------------------------------------------------------------------------


def _classify_control(summary: Mapping[str, Any]) -> str:
    if _injection(summary) is None:
        return "incomplete"
    if _relation_before(summary) is False:
        return "truth_unverified"
    if _relation_after(summary) is False:
        return "truth_unverified"
    case_valid = _bool_or_none(summary.get("case_valid"))
    if case_valid is True:
        return "valid_control"
    if case_valid is False:
        # A no-op control whose final goal is no longer true is a valid run with a failed
        # control. SPEC §6.1 has no separate control-failure verdict, so it is reported as
        # ``valid_not_recovered``; metrics.control_rate keys on ``valid_control`` and
        # recovery_rate excludes C0 episodes.
        return "valid_not_recovered"
    success = _goal_success(summary)
    if success is True:
        return "valid_control"
    if success is False:
        return "valid_not_recovered"
    if _relation_final(summary) is True:
        return "valid_control"
    return "incomplete"


def _classify_rollback(summary: Mapping[str, Any]) -> str:
    injection = _injection(summary)
    if injection is None:
        return "incomplete"
    failed_gate = _gate_failure(summary)
    if failed_gate is not None:
        return "injection_invalid"
    if _validity(summary).get("goal_preserved_after_pre") is False:
        return "injection_invalid"
    applied = injection.get("applied")
    if isinstance(applied, (list, tuple)) and not applied and not _is_probe(summary):
        return "injection_invalid"
    if _relation_before(summary) is not True:
        return "truth_unverified"
    after = _relation_after(summary)
    if _is_probe(summary):
        if after is True:
            return "valid_relation_preserving_probe"
        if after is None:
            return "incomplete"
        return "truth_unverified"
    if after is None:
        return "incomplete"
    if after is not False:
        # The state write did not revoke the relation: no controlled perturbation happened.
        return "truth_unverified"
    if _external_restoration(summary):
        return "valid_external_restoration"
    recovered = _relation_final(summary)
    if recovered is None:
        return "incomplete"
    return "valid_recovered" if recovered else "valid_not_recovered"
