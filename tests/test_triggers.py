"""Tests for the GT-based in-execution window triggers."""

from __future__ import annotations

import pytest

from libero_rollback.runtime.triggers import (
    TriggerConfig,
    WindowObservation,
    WindowTrigger,
)


def obs(
    step: int = 0,
    *,
    s1_done: bool = True,
    s1_settled: bool = True,
    s2_started: bool = False,
    lift: float | None = None,
    xy: float | None = None,
) -> WindowObservation:
    return WindowObservation(
        step=step,
        s1_done=s1_done,
        s1_settled=s1_settled,
        s2_started=s2_started,
        s2_lift_m=lift,
        s2_to_goal_xy_m=xy,
    )


def test_early_requires_completed_and_settled() -> None:
    trigger = WindowTrigger(target="early")
    assert trigger.observe(obs(s1_settled=False)) is False
    assert trigger.observe(obs(step=1, s1_settled=True)) is True
    assert trigger.observe(obs(step=2)) is False
    assert trigger.events == [("early", 1)]


def test_mid_uses_lift_threshold_not_old_five_cm() -> None:
    trigger = WindowTrigger(target="mid")
    assert trigger.observe(obs(lift=0.029)) is False
    assert trigger.observe(obs(step=1, lift=0.03)) is True
    assert trigger.events == [("mid", 1)]


def test_later_requires_lift_and_goal_xy() -> None:
    trigger = WindowTrigger(target="later")
    assert trigger.observe(obs(lift=0.04, xy=0.30)) is False
    assert trigger.observe(obs(step=1, lift=0.04, xy=0.20)) is True
    assert trigger.events == [("later", 1)]


def test_later_does_not_fire_without_lift() -> None:
    trigger = WindowTrigger(target="later")
    assert trigger.observe(obs(lift=0.0, xy=0.01)) is False
    assert trigger.observe(obs(step=1, lift=0.0, xy=0.01)) is False


def test_target_window_is_the_only_success_signal() -> None:
    trigger = WindowTrigger(target="later")
    # early fires, but the episode target is later -> no success yet.
    assert trigger.observe(obs(step=0)) is False
    assert trigger.observe(obs(step=1, lift=0.04, xy=0.30)) is False
    assert trigger.observe(obs(step=2, lift=0.04, xy=0.10)) is True
    # Only the requested window is emitted; early/mid are not target events.
    assert trigger.events == [("later", 2)]


def test_invalid_target_and_config() -> None:
    with pytest.raises(ValueError):
        WindowTrigger(target="all_done")
    with pytest.raises(ValueError):
        TriggerConfig(lift_min_m=0)
    with pytest.raises(ValueError):
        TriggerConfig(preplacement_max_xy_m=0)
