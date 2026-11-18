"""Pure-stdlib metric helpers for the rollback contract (SPEC §6.2-§6.3).

All functions operate on *episode documents*: either a v2 runner
``summary.json`` mapping, the legacy v1 evidence mapping (only inside
``(case, episode)`` pairs), or a mapping that already carries a ``verdict``
string. The evidence classifier owns *what happened*; this module only owns
*how it is counted*:

* ``Recovery`` excludes ``C0`` controls, invalid injections, externally
  restored episodes and incomplete protocols from its denominator;
* ``control_rate`` is a no-op-control pass rate over attempted ``C0`` cases;
* ``trigger_rate`` is a plain attempted/triggered ratio;
* every rate carries a Wilson 95 % confidence interval, and a zero denominator
  is ``N/A`` (value/CI ``None``), never 0 %.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .evidence import (
    CONTROL_VERDICTS,
    RECOVERY_VERDICTS,
    VERDICTS,
    classify_episode,
    classify_result,
)

Z_95 = 1.959963984540054

Episode = Mapping[str, Any] | tuple[Mapping[str, Any], Mapping[str, Any]]


@dataclass(frozen=True)
class Rate:
    """A numerator/denominator pair with a Wilson 95 % interval."""

    numerator: int
    denominator: int
    value: float | None
    ci: tuple[float, float] | None = None

    @property
    def is_na(self) -> bool:
        """True when the denominator is zero (report ``N/A``, not 0 %)."""

        return self.denominator == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
            "value": self.value,
            "ci": None if self.ci is None else [self.ci[0], self.ci[1]],
            "na": self.is_na,
        }


def wilson_ci(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for ``k`` successes out of ``n`` trials.

    A zero denominator returns the uninformative interval ``(0.0, 1.0)``;
    callers that report rates must surface ``N/A`` instead of that interval
    (see :class:`Rate`).
    """

    invalid_counts = (
        isinstance(k, bool)
        or isinstance(n, bool)
        or not isinstance(k, int)
        or not isinstance(n, int)
    )
    if invalid_counts:
        raise TypeError("wilson_ci expects integer counts")
    if n < 0:
        raise ValueError("n must be non-negative")
    if not 0 <= k <= n:
        raise ValueError(f"k must be in [0, n], got k={k}, n={n}")
    if n == 0:
        return (0.0, 1.0)
    proportion = k / n
    z_squared = z * z
    denominator = 1.0 + z_squared / n
    centre = (proportion + z_squared / (2.0 * n)) / denominator
    margin = z * math.sqrt(
        proportion * (1.0 - proportion) / n + z_squared / (4.0 * n * n)
    ) / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def _rate(numerator: int, denominator: int) -> Rate:
    if numerator > denominator:
        raise ValueError(f"numerator {numerator} exceeds denominator {denominator}")
    if denominator == 0:
        return Rate(0, 0, None, None)
    return Rate(numerator, denominator, numerator / denominator, wilson_ci(numerator, denominator))


def _summary_of(episode: Episode) -> Mapping[str, Any]:
    if isinstance(episode, tuple) and len(episode) == 2:
        summary = episode[1]
        if not isinstance(summary, Mapping):
            raise TypeError("episode tuple must be (case, summary) mappings")
        return summary
    if not isinstance(episode, Mapping):
        raise TypeError(f"episode must be a mapping or (case, summary), got {type(episode)!r}")
    return episode


def _case_of(episode: Episode) -> Mapping[str, Any]:
    if isinstance(episode, tuple) and len(episode) == 2:
        case = episode[0]
        return case if isinstance(case, Mapping) else {}
    return {}


def _verdict_of(episode: Episode) -> str:
    summary = _summary_of(episode)
    explicit = summary.get("verdict")
    if isinstance(explicit, str):
        if explicit not in VERDICTS:
            raise ValueError(f"unknown verdict {explicit!r}; expected one of {VERDICTS}")
        return explicit
    if "report" in summary:
        # Legacy v1 evidence document: it needs the case mapping to classify.
        return classify_result(dict(_case_of(episode)), summary)
    return classify_episode(summary)


def _normalised(value: Any) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def _is_control(episode: Episode) -> bool:
    summary = _summary_of(episode)
    case = _case_of(episode)
    if _normalised(summary.get("level") or case.get("level")) == "c0":
        return True
    if _normalised(summary.get("target") or case.get("target")) == "c0":
        return True
    semantics = _normalised(summary.get("semantics") or case.get("semantics"))
    if "control" in semantics:
        return True
    if summary.get("is_control") is True:
        return True
    if _normalised(summary.get("expected_evaluation_semantics")) == "relation_holds_control":
        return True
    return summary.get("verdict") in CONTROL_VERDICTS


def _suite_of(episode: Episode) -> str | None:
    summary = _summary_of(episode)
    value = summary.get("suite") or _case_of(episode).get("suite")
    return str(value) if value else None


def _level_of(episode: Episode) -> str | None:
    summary = _summary_of(episode)
    value = summary.get("level") or _case_of(episode).get("level")
    return str(value) if value else None


def _triggered(episode: Episode) -> bool:
    summary = _summary_of(episode)
    if summary.get("trigger_reached") is True:
        return True
    validity = summary.get("validity")
    return isinstance(validity, Mapping) and validity.get("trigger_reached") is True


def _successful(episode: Episode) -> bool | None:
    summary = _summary_of(episode)
    value = summary.get("success")
    if isinstance(value, bool):
        return value
    final_goal = summary.get("final_goal_truth")
    if isinstance(final_goal, (list, tuple)):
        return all(item is True for item in final_goal)
    return None


# ---------------------------------------------------------------------------
# rates
# ---------------------------------------------------------------------------


def recovery_rate(episodes: Iterable[Episode]) -> Rate:
    """Conditional recovery rate: recovered / (valid recovered + not recovered).

    C0 controls, invalid injections, externally restored episodes and
    incomplete protocols never enter the denominator (SPEC §6.2).
    """

    numerator = denominator = 0
    for episode in episodes:
        if _is_control(episode):
            continue
        verdict = _verdict_of(episode)
        if verdict not in RECOVERY_VERDICTS:
            continue
        denominator += 1
        if verdict == "valid_recovered":
            numerator += 1
    return _rate(numerator, denominator)


def control_rate(episodes: Iterable[Episode]) -> Rate:
    """No-op control pass rate: ``valid_control`` / attempted ``C0`` episodes."""

    numerator = denominator = 0
    for episode in episodes:
        if not _is_control(episode):
            continue
        denominator += 1
        if _verdict_of(episode) in CONTROL_VERDICTS:
            numerator += 1
    return _rate(numerator, denominator)


def trigger_rate(episodes: Iterable[Episode]) -> Rate:
    """Share of attempted episodes whose trigger event fired."""

    numerator = denominator = 0
    for episode in episodes:
        denominator += 1
        if _triggered(episode):
            numerator += 1
    return _rate(numerator, denominator)


def success_rate(episodes: Iterable[Episode]) -> Rate:
    """Unconditional joint success rate over episodes that recorded ``success``.

    This is the primary A/C metric (``SR``); for B/D it is a secondary reading
    and must never be reported next to ``Recovery`` as the same quantity.
    """

    numerator = denominator = 0
    for episode in episodes:
        successful = _successful(episode)
        if successful is None:
            continue
        denominator += 1
        if successful:
            numerator += 1
    return _rate(numerator, denominator)


# ---------------------------------------------------------------------------
# aggregation
# ---------------------------------------------------------------------------


def _group_summary(episodes: Sequence[Episode]) -> dict[str, Any]:
    by_verdict: dict[str, int] = {}
    for episode in episodes:
        verdict = _verdict_of(episode)
        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1
    return {
        "cases": len(episodes),
        "by_verdict": dict(sorted(by_verdict.items())),
        "recovery": recovery_rate(episodes).as_dict(),
        "control": control_rate(episodes).as_dict(),
        "trigger": trigger_rate(episodes).as_dict(),
        "success": success_rate(episodes).as_dict(),
    }


def summarize(episodes: Iterable[Episode]) -> dict[str, Any]:
    """Aggregate episodes into overall / by-suite / by-level summaries."""

    episode_list = list(episodes)
    by_suite: dict[str, list[Episode]] = {}
    by_level: dict[str, list[Episode]] = {}
    for episode in episode_list:
        suite = _suite_of(episode)
        if suite is not None:
            by_suite.setdefault(suite, []).append(episode)
        level = _level_of(episode)
        if level is not None:
            by_level.setdefault(level, []).append(episode)
    overall = _group_summary(episode_list)
    return {
        **overall,
        "by_suite": {name: _group_summary(rows) for name, rows in sorted(by_suite.items())},
        "by_level": {name: _group_summary(rows) for name, rows in sorted(by_level.items())},
    }


# ---------------------------------------------------------------------------
# capacity / retention / effect size
# ---------------------------------------------------------------------------


def effective_goal_capacity(
    success_rates: Mapping[Any, float | None] | Iterable[float | None],
) -> float:
    """``EGC = Σₙ SR(n)``: mean number of simultaneously satisfied goal atoms.

    ``None`` entries are unmeasured levels and are skipped rather than counted
    as zero (``docs/SPEC.md`` §6.3, README §4.1).
    """

    values = success_rates.values() if isinstance(success_rates, Mapping) else success_rates
    total = 0.0
    for value in values:
        if value is None:
            continue
        total += float(value)
    return total


egc = effective_goal_capacity


def retention(
    case_success_rate: float | None,
    reference_success_rate: float | None,
) -> float | None:
    """``Retention = SR_case / SR_ref``; ``None`` when either side is N/A."""

    if case_success_rate is None or reference_success_rate is None:
        return None
    reference = float(reference_success_rate)
    if reference == 0.0:
        return None
    return float(case_success_rate) / reference
