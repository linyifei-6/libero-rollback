"""GT-based in-execution window triggers (C/D).

This is a pure-stdlib state machine; it consumes ground-truth predicates and
object/end-effector geometry, not the old 5 cm / 8 cm heuristics.  It mirrors
the milestone semantics used by the predecessor ``libero_runtime`` trigger
engine:

* ``early``  -> first subgoal completed and settled (released / at rest);
* ``mid``    -> next-subgoal object lifted from its initial pose;
* ``later``  -> next-subgoal object near its goal region, after a lift.

Default thresholds come from the predecessor task profiles (``next_subgoal_lift``
uses 0.03 m; ``next_subgoal_preplacement`` uses 0.20 m).  Per-task profiles may
override them, but the runner must record the resolved values.
"""

from __future__ import annotations

from dataclasses import dataclass, field

WINDOWS = ("early", "mid", "later")


@dataclass(frozen=True)
class TriggerConfig:
    lift_min_m: float = 0.03
    preplacement_max_xy_m: float = 0.20
    require_settled_early: bool = True
    require_s2_started_early: bool = False
    early_delay_steps: int = 0
    pose_mid_at_start: bool = False
    pose_later_max_xy_m: float = 0.20

    def __post_init__(self) -> None:
        if self.lift_min_m <= 0:
            raise ValueError("lift_min_m must be positive")
        if self.preplacement_max_xy_m <= 0:
            raise ValueError("preplacement_max_xy_m must be positive")


@dataclass(frozen=True)
class WindowObservation:
    step: int
    s1_done: bool
    s1_settled: bool
    s2_started: bool
    s2_lift_m: float | None
    s2_to_goal_xy_m: float | None
    s1_done_step: int | None = None


@dataclass
class WindowTrigger:
    """Fire each GT window at most once; target one window per episode."""

    config: TriggerConfig = field(default_factory=TriggerConfig)
    target: str = "early"
    _fired: set[str] = field(default_factory=set, init=False)
    _lift_seen: bool = field(default=False, init=False)
    _s2_started_seen: bool = field(default=False, init=False)
    _mid_seen: bool = field(default=False, init=False)
    _events: list[tuple[str, int]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if self.target not in WINDOWS:
            raise ValueError(f"unknown window {self.target!r}; expected one of {WINDOWS}")

    @property
    def events(self) -> list[tuple[str, int]]:
        return list(self._events)

    @property
    def fired(self) -> bool:
        return self.target in self._fired

    def observe(self, observation: WindowObservation) -> bool:
        """Feed one step; return True iff the target window fired this step."""

        if observation.s2_lift_m is not None and observation.s2_lift_m >= self.config.lift_min_m:
            self._lift_seen = True
        if observation.s2_started:
            self._s2_started_seen = True

        mid_candidate = observation.s1_done and (
            self._s2_started_seen
            if self.config.pose_mid_at_start
            else self._lift_seen
        )
        if mid_candidate:
            self._mid_seen = True
        fired_before = self.target in self._fired
        candidates = {
            "early": observation.s1_done
            and (observation.s1_settled or not self.config.require_settled_early)
            and (observation.s2_started or not self.config.require_s2_started_early)
            and (
                self.config.early_delay_steps <= 0
                or observation.s1_done_step is None
                or observation.step - observation.s1_done_step
                >= self.config.early_delay_steps
            ),
            "mid": mid_candidate,
            "later": (
                observation.s1_done
                and self._mid_seen
                and observation.s2_to_goal_xy_m is not None
                and observation.s2_to_goal_xy_m
                <= (
                    self.config.pose_later_max_xy_m
                    if self.config.pose_mid_at_start
                    else self.config.preplacement_max_xy_m
                )
                and (self._s2_started_seen or not self.config.pose_mid_at_start)
            ),
        }
        # One case targets one window.  We still compute the shared lift state,
        # but only the requested window is emitted as an event.
        for window in (self.target,):
            if window in self._fired or not candidates[window]:
                continue
            self._fired.add(window)
            self._events.append((window, observation.step))
        return self.target in self._fired and not fired_before
