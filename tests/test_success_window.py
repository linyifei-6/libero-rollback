"""Unit tests for the simulator-free post-success hold window."""

from __future__ import annotations

import pytest

from libero_rollback.success_window import SuccessWindow


def test_not_armed_until_first_success() -> None:
    window = SuccessWindow(delay=5)
    assert window.observe(0, False) == "idle"
    assert window.observe(1, False) == "idle"
    assert not window.armed
    assert window.observe(2, True) == "armed"
    assert window.armed
    assert window.first_success_step == 2
    assert window.status == "pending"


def test_stable_after_full_window() -> None:
    window = SuccessWindow(delay=5)
    assert window.observe(10, True) == "armed"
    events = [window.observe(step, True) for step in range(11, 16)]
    assert events == ["checkpoint", "checkpoint", "checkpoint", "checkpoint", "stable"]
    assert window.passed
    assert window.finished
    assert window.stable_success_step == 15
    assert [check["kind"] for check in window.checks] == [
        "checkpoint",
        "checkpoint",
        "checkpoint",
        "checkpoint",
        "final",
    ]
    assert window.to_dict()["first_success_step"] == 10


def test_any_false_step_fails_strict_window() -> None:
    window = SuccessWindow(delay=5, check_interval=1)
    window.observe(10, True)
    assert window.observe(11, True) == "checkpoint"
    assert window.observe(12, False) == "lost"
    assert window.failed
    assert not window.passed
    assert window.stable_success_step is None
    assert window.checks[-1]["step"] == 12


def test_sampled_window_ignores_unsampled_dips() -> None:
    window = SuccessWindow(delay=4, check_interval=2)
    window.observe(10, True)
    assert window.observe(11, False) == "pending"
    assert window.observe(12, True) == "checkpoint"
    assert window.observe(13, False) == "pending"
    assert window.observe(14, True) == "stable"
    assert window.passed
    # The trace still records the dips so a strict S(K) can be recomputed.
    assert [row["success"] for row in window.trace] == [True, False, True, False, True]


def test_sampled_checkpoint_false_fails() -> None:
    window = SuccessWindow(delay=4, check_interval=2)
    window.observe(10, True)
    window.observe(11, True)
    assert window.observe(12, False) == "lost"
    assert window.failed


def test_final_check_runs_even_when_delay_is_not_a_multiple_of_interval() -> None:
    window = SuccessWindow(delay=5, check_interval=2)
    window.observe(10, True)
    events = [window.observe(step, True) for step in range(11, 16)]
    assert events == ["pending", "checkpoint", "pending", "checkpoint", "stable"]
    assert window.checks[-1]["kind"] == "final"


def test_observe_is_idempotent_after_finish() -> None:
    window = SuccessWindow(delay=1)
    window.observe(3, True)
    assert window.observe(4, True) == "stable"
    assert window.observe(5, False) == "stable"
    assert len(window.trace) == 2


@pytest.mark.parametrize(
    ("delay", "interval"), [(0, 1), (-1, 1), (True, 1), (1, 0), (1, -2)]
)
def test_invalid_configuration_rejected(delay: int, interval: int) -> None:
    with pytest.raises(ValueError):
        SuccessWindow(delay=delay, check_interval=interval)
