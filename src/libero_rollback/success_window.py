"""Post-success hold window used by the success-delay evaluator overlay.

The stock LIBERO task predicate is existential: the first control step whose
task state satisfies the goal ends the episode.  ``SuccessWindow`` turns that
single step into a hold requirement.  After the first success step it samples
the same effective predicate at fixed checkpoints of a control-step window; a
false sample at a checkpoint marks the episode ``lost`` and a window that
reaches its final checkpoint with every sample true marks it ``stable``.

Why a sampling window rather than a single re-check:

* a one-shot re-check cannot distinguish "held for K steps" from "held at the
  instant we looked";
* sampling every step (``check_interval=1``) is the strict definition; larger
  intervals are a deliberate tolerance for contact jitter and remain an
  explicit protocol choice rather than hidden smoothing;
* the per-step trace is always recorded, so a strict S(K) curve can be
  recomputed offline from one long rollout without re-running the simulator.

The module is deliberately simulator-free (pure Python) so it can be unit
tested without MuJoCo, torch, or LIBERO imports.  It is copied verbatim into a
disposable runtime overlay as ``success_window.py`` by
``scripts/prepare_success_delay_runtime.py``; the sibling ``libero-runtime``
checkout is reference material and is never modified.
"""

from __future__ import annotations

from typing import Any

SCHEMA = "libero.success-window.v1"


class SuccessWindow:
    """State machine for one episode's post-success hold window.

    Usage::

        window = SuccessWindow(delay=100, check_interval=20)
        for sim_step, success in rollout:
            event = window.observe(sim_step, success)
            if window.finished:
                break

    ``observe`` returns one of ``idle`` (not successful yet), ``armed`` (this
    step was the first success), ``checkpoint`` (a sampled checkpoint passed),
    ``pending`` (between checkpoints), ``stable`` (window passed) or ``lost``
    (a sampled checkpoint was false).
    """

    def __init__(self, delay: int, check_interval: int = 1) -> None:
        if isinstance(delay, bool) or not isinstance(delay, int) or delay < 1:
            raise ValueError("success window delay must be a positive integer")
        if (
            isinstance(check_interval, bool)
            or not isinstance(check_interval, int)
            or check_interval < 1
        ):
            raise ValueError("success window check interval must be a positive integer")
        self.delay = delay
        self.check_interval = check_interval
        self.first_success_step: int | None = None
        self.stable_success_step: int | None = None
        self.status = "idle"  # idle | pending | stable | lost
        self.checks: list[dict[str, Any]] = []
        self.trace: list[dict[str, Any]] = []

    @property
    def armed(self) -> bool:
        return self.first_success_step is not None

    @property
    def passed(self) -> bool:
        return self.status == "stable"

    @property
    def failed(self) -> bool:
        return self.status == "lost"

    @property
    def finished(self) -> bool:
        return self.status in {"stable", "lost"}

    def observe(self, sim_step: int, success: bool) -> str:
        """Record the effective task predicate for one executed control step."""

        if self.finished:
            return self.status
        success = bool(success)
        if self.first_success_step is None:
            if not success:
                return "idle"
            self.first_success_step = int(sim_step)
            self.status = "pending"
            self.trace.append({"step": int(sim_step), "success": True})
            return "armed"

        self.trace.append({"step": int(sim_step), "success": success})
        elapsed = int(sim_step) - self.first_success_step
        if elapsed >= self.delay:
            kind = "final"
        elif elapsed > 0 and elapsed % self.check_interval == 0:
            kind = "checkpoint"
        else:
            return "pending"

        self.checks.append(
            {
                "step": int(sim_step),
                "elapsed_steps": elapsed,
                "kind": kind,
                "success": success,
            }
        )
        if not success:
            self.status = "lost"
            return "lost"
        if kind == "final":
            self.status = "stable"
            self.stable_success_step = int(sim_step)
            return "stable"
        return "checkpoint"

    def to_dict(self) -> dict[str, Any]:
        observed_steps = (
            self.trace[-1]["step"] - self.first_success_step
            if self.trace and self.first_success_step is not None
            else 0
        )
        return {
            "schema": SCHEMA,
            "enabled": True,
            "delay": self.delay,
            "check_interval": self.check_interval,
            "status": self.status,
            "first_success_step": self.first_success_step,
            "stable_success_step": self.stable_success_step,
            "observed_window_steps": observed_steps,
            "checks": self.checks,
            "trace": self.trace,
        }
