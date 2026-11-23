"""Metric tests for the migrated contract layer (docs/SPEC.md §6.2-§6.3)."""

from __future__ import annotations

import pytest

from libero_rollback.evidence import classify_episode
from libero_rollback.metrics import (
    Rate,
    control_rate,
    effective_goal_capacity,
    egc,
    goal_progress,
    mean_goal_progress,
    mean_pending_preservation,
    one_and_done_rate,
    partial_progress_rate,
    pending_preservation_rate,
    progress_summary,
    recovery_rate,
    zero_progress_rate,
    retention,
    success_rate,
    summarize,
    trigger_rate,
    wilson_ci,
)


def episode(verdict: str, *, level: str = "L0", suite: str = "goal", **extra) -> dict:
    summary = {
        "verdict": verdict,
        "level": level,
        "suite": suite,
        "trigger_reached": True,
        "success": False,
    }
    summary.update(extra)
    return summary


def test_wilson_ci_matches_closed_form_values() -> None:
    low, high = wilson_ci(1, 10)
    assert low == pytest.approx(0.01786, abs=1e-4)
    assert high == pytest.approx(0.40414, abs=1e-4)
    assert wilson_ci(0, 10)[0] == 0.0
    assert wilson_ci(10, 10)[1] == pytest.approx(1.0)
    assert wilson_ci(0, 0) == (0.0, 1.0)


def test_wilson_ci_rejects_impossible_counts() -> None:
    with pytest.raises(ValueError):
        wilson_ci(3, 2)
    with pytest.raises(ValueError):
        wilson_ci(-1, 2)


def test_recovery_rate_excludes_controls_and_invalid_injections() -> None:
    episodes = [
        episode("valid_recovered"),
        episode("valid_not_recovered", level="L1"),
        episode("injection_invalid", level="L2"),
        episode("valid_control", level="C0"),
        episode("trigger_not_reached"),
    ]
    rate = recovery_rate(episodes)
    assert (rate.numerator, rate.denominator) == (1, 2)
    assert rate.value == pytest.approx(0.5)
    assert rate.ci is not None and rate.ci[0] < 0.5 < rate.ci[1]


def test_recovery_rate_of_nothing_is_na_not_zero() -> None:
    rate = recovery_rate([])
    assert rate.denominator == 0
    assert rate.value is None
    assert rate.ci is None
    assert rate.is_na
    assert rate.as_dict()["na"] is True


def test_control_rate_counts_only_c0_episodes() -> None:
    episodes = [
        episode("valid_control", level="C0"),
        episode("valid_not_recovered", level="C0"),
        episode("valid_recovered", level="L0"),
    ]
    rate = control_rate(episodes)
    assert (rate.numerator, rate.denominator) == (1, 2)


def test_trigger_rate_is_triggered_over_attempted() -> None:
    episodes = [
        episode("valid_recovered", trigger_reached=True),
        episode("valid_not_recovered", trigger_reached=True),
        episode("trigger_not_reached", trigger_reached=False),
    ]
    rate = trigger_rate(episodes)
    assert (rate.numerator, rate.denominator) == (2, 3)


def test_success_rate_uses_recorded_success_flags() -> None:
    episodes = [
        episode("valid_recovered", success=True),
        episode("valid_not_recovered", success=False),
        episode("trigger_not_reached", success=None),
    ]
    rate = success_rate(episodes)
    assert (rate.numerator, rate.denominator) == (1, 2)


def test_summarize_groups_by_suite_and_level() -> None:
    episodes = [
        episode("valid_recovered", suite="goal", level="L0"),
        episode("valid_not_recovered", suite="goal", level="L1"),
        episode("valid_recovered", suite="object", level="L0"),
    ]
    report = summarize(episodes)
    assert report["cases"] == 3
    assert report["by_verdict"] == {"valid_not_recovered": 1, "valid_recovered": 2}
    assert report["recovery"]["numerator"] == 2
    assert report["recovery"]["denominator"] == 3
    assert set(report["by_suite"]) == {"goal", "object"}
    assert report["by_suite"]["goal"]["cases"] == 2
    assert set(report["by_level"]) == {"L0", "L1"}
    assert report["by_level"]["L0"]["recovery"]["denominator"] == 2


def test_legacy_case_episode_pairs_are_supported() -> None:
    legacy = {
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
    rate = recovery_rate([({}, legacy)])
    assert (rate.numerator, rate.denominator) == (1, 1)


def test_effective_goal_capacity_sums_measured_levels() -> None:
    assert effective_goal_capacity({1: 1.0, 2: 0.04, 3: None}) == pytest.approx(1.04)
    assert egc([1.0, 0.0, 0.5]) == pytest.approx(1.5)
    assert egc({}) == 0.0


def test_retention_is_a_ratio_and_na_without_a_reference() -> None:
    assert retention(0.20, 0.50) == pytest.approx(0.4)
    assert retention(0.10, 0.0) is None
    assert retention(None, 0.5) is None


def test_rate_round_trips_through_dict() -> None:
    rate = Rate(1, 4, 0.25, (0.0456, 0.6994))
    payload = rate.as_dict()
    assert payload["numerator"] == 1
    assert payload["denominator"] == 4
    assert payload["value"] == 0.25
    assert payload["ci"] == [0.0456, 0.6994]
    assert payload["na"] is False


def test_unknown_explicit_verdict_is_rejected() -> None:
    with pytest.raises(ValueError):
        recovery_rate([episode("made_up_verdict")])


def test_summarize_accepts_unpreclassified_v2_summaries() -> None:
    summary = {
        "status": "ok",
        "level": "L0",
        "suite": "goal",
        "semantics": "relation_then_resume",
        "trigger_reached": True,
        "relation_before": True,
        "relation_after_injection": False,
        "relation_final": True,
        "recovered": True,
        "case_valid": True,
        "injection": {"applied": [{"target": "x", "mode": "init"}]},
        "validity": {},
    }
    report = summarize([summary])
    assert report["by_verdict"] == {classify_episode(summary): 1}


def test_progress_and_subtask_degree() -> None:
    episodes = [
        episode("valid_recovered", final_goal_truth=[True, False]),
        episode("valid_not_recovered", final_goal_truth=[False, False]),
        episode("valid_recovered", final_goal_truth=[True, True, False]),
    ]
    assert goal_progress(episodes[0]) == pytest.approx(0.5)
    assert mean_goal_progress(episodes) == pytest.approx((0.5 + 0.0 + 2 / 3) / 3)
    summary = progress_summary(episodes)
    assert summary["n"] == 3
    assert summary["median"] == pytest.approx(0.5)
    assert summary["iqr"] is not None


def test_partial_zero_and_one_and_done_rates() -> None:
    episodes = [
        episode("valid_recovered", final_goal_truth=[True, True]),
        episode("valid_not_recovered", final_goal_truth=[True, False]),
        episode("valid_not_recovered", final_goal_truth=[False, False]),
        episode("valid_not_recovered", final_goal_truth=[True]),
    ]
    pp = partial_progress_rate(episodes)
    assert (pp.numerator, pp.denominator) == (3, 4)
    zero = zero_progress_rate(episodes)
    assert (zero.numerator, zero.denominator) == (1, 4)
    # n>=2 failures: two calls (True,False), (False,False); one has exactly 1.
    oad = one_and_done_rate(episodes)
    assert (oad.numerator, oad.denominator) == (1, 2)


def test_pending_preservation_and_terminal_states() -> None:
    episodes = [
        episode("valid_recovered", final_pending_truth=[True], terminal_state="both"),
        episode("valid_not_recovered", final_pending_truth=[False], terminal_state="restore_only"),
        episode("valid_not_recovered", final_pending_truth=[True], terminal_state="pending_only"),
        episode("valid_not_recovered", final_pending_truth=[False], terminal_state="neither"),
    ]
    rate = pending_preservation_rate(episodes)
    assert (rate.numerator, rate.denominator) == (2, 4)
    assert mean_pending_preservation(episodes) == pytest.approx(0.5)
    counts = progress_summary([])
    assert counts["mean"] is None


def test_terminal_state_counts_are_separate() -> None:
    from libero_rollback.metrics import terminal_state_counts

    episodes = [
        episode("valid_recovered", terminal_state="both"),
        episode("valid_recovered", terminal_state="both"),
        episode("valid_not_recovered", terminal_state="restore_only"),
        episode("valid_not_recovered", terminal_state="pending_only"),
        episode("valid_not_recovered", terminal_state="neither"),
    ]
    assert terminal_state_counts(episodes) == {
        "both": 2,
        "restore_only": 1,
        "pending_only": 1,
        "neither": 1,
    }
