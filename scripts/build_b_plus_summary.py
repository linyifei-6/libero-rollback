#!/usr/bin/env python3
"""Aggregate B-plus ``episodes.jsonl`` files into report tables.

One or more run directories are merged by ``case_id`` (first occurrence wins,
so an explicit precedence order can be used when a suite was split across
runs).  The script is stdlib-only and prints a Markdown summary plus an
optional JSON payload; it never re-simulates anything, it only re-counts the
recorded evidence.

Definitions follow ``docs/B-matrix-plus.md`` / ``src/libero_rollback/metrics.py``:

* ``Recovery`` = ``recovered / valid`` over the ``O2`` arm only.  Invalid
  injections, untriggered episodes and controls never enter the denominator.
* ``C0`` sanity = ``recovered / valid`` over the no-op arm (the goal must stay
  true when nothing is injected).
* ``L0`` = rollback to the episode init pose, reported separately: it is a
  different (much easier) geometric target than the LIBERO-Plus O2 pose.

Usage::

    python3 scripts/build_b_plus_summary.py \
        runs/b-plus-goal-full-smolvla-20261120 \
        runs/b-plus-object-full-smolvla-20261120 ... --json out.json

    # paired comparison of two policies on the shared case ids
    python3 scripts/build_b_plus_summary.py SMOLVLA_RUNS... --compare PI05_RUNS...
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
Z95 = 1.959963984540054


def load_runs(paths: list[Path]) -> list[dict]:
    """Merge ``<run>/episodes.jsonl`` files.

    When a case appears more than once (a resumed or repaired run), the later
    record wins; the first-seen order is kept so tables stay stable.
    """

    by_case: dict[str, dict] = {}
    order: list[str] = []
    for path in paths:
        path = path.resolve()
        episodes = path / "episodes.jsonl"
        if not episodes.is_file():
            raise SystemExit(f"missing {episodes}")
        for line in episodes.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            case_id = row.get("case_id") or row.get("task_id")
            if not case_id:
                continue
            row["_run"] = str(path)
            if case_id not in by_case:
                order.append(case_id)
            by_case[case_id] = row
    return [by_case[case_id] for case_id in order]


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def rate(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {
        "k": k,
        "n": n,
        "rate": (k / n) if n else None,
        "ci95": [lo, hi],
    }


def pct(value: float | None) -> str:
    return "—" if value is None else f"{100.0 * value:.1f}%"


def fmt_rate(r: dict) -> str:
    if not r["n"]:
        return "—"
    lo, hi = r["ci95"]
    return f"{r['k']}/{r['n']} = {pct(r['rate'])} [{100 * lo:.0f}–{100 * hi:.0f}]"


def arm_of(row: dict) -> str:
    level = row.get("level") or "?"
    if level == "C0":
        return "C0"
    if level == "L0":
        return "L0"
    if level == "O2":
        return "O2"
    return str(level)


def level_of(row: dict) -> str:
    if arm_of(row) != "O2":
        return arm_of(row)
    param = str(row.get("param") or "")
    if param.startswith("l") and "s" in param:
        return "L" + param[1 : param.index("s")]
    return "O2"


def median(values: list[float]) -> float | None:
    if not values:
        return None
    values = sorted(values)
    n = len(values)
    mid = n // 2
    return values[mid] if n % 2 else 0.5 * (values[mid - 1] + values[mid])


def summarize(rows: list[dict]) -> dict:
    o2 = [r for r in rows if arm_of(r) == "O2"]
    c0 = [r for r in rows if arm_of(r) == "C0"]
    l0 = [r for r in rows if arm_of(r) == "L0"]
    o2_valid = [r for r in o2 if r.get("case_valid")]
    c0_valid = [r for r in c0 if r.get("case_valid")]
    l0_valid = [r for r in l0 if r.get("case_valid")]

    invalid_reasons: Counter = Counter()
    penetration: list[float] = []
    for row in rows:
        if row.get("trigger_reached") and not row.get("case_valid"):
            validity = row.get("validity") or {}
            reasons = []
            if not validity.get("no_object_penetration", True):
                reasons.append("penetration")
            if not validity.get("zero_velocity_after_intervention", True):
                reasons.append("velocity")
            if not validity.get("object_released_before_intervention", True):
                reasons.append("not_released")
            if arm_of(row) != "C0" and row.get("relation_after_injection") is True:
                reasons.append("relation_still_true")
            if arm_of(row) == "C0" and row.get("success") is not True:
                reasons.append("c0_goal_lost")
            invalid_reasons.update(reasons or ["unknown"])
        value = (row.get("injection") or {}).get("penetration_m")
        if isinstance(value, (int, float)):
            penetration.append(float(value))

    c0_triggered = sum(1 for r in c0 if r.get("trigger_reached"))
    c0_preserved = sum(1 for r in c0_valid if r.get("recovered"))
    l0_triggered = sum(1 for r in l0 if r.get("trigger_reached"))
    outcomes = {
        "not_triggered": sum(1 for r in rows if not r.get("trigger_reached")),
        "invalid_injection": sum(
            1 for r in rows if r.get("trigger_reached") and not r.get("case_valid")
        ),
        "o2_recovered": sum(1 for r in o2_valid if r.get("recovered")),
        "o2_not_recovered": sum(1 for r in o2_valid if not r.get("recovered")),
        # A C0 case that triggered but lost the goal is a control failure, not
        # an invalid injection: keep it in the C0 denominator.
        "c0_triggered": c0_triggered,
        "c0_preserved": c0_preserved,
        "c0_lost": c0_triggered - c0_preserved,
        "l0_triggered": l0_triggered,
        "l0_valid": len(l0_valid),
        "l0_recovered": sum(1 for r in l0_valid if r.get("recovered")),
    }

    def group(items: list[dict]) -> dict:
        return {
            "cases": len(items),
            "ok": sum(1 for r in items if r.get("status") == "ok"),
            "error": sum(1 for r in items if r.get("status") not in (None, "ok")),
            "triggered": sum(1 for r in items if r.get("trigger_reached")),
            "valid": sum(1 for r in items if r.get("case_valid")),
            "recovered": sum(1 for r in items if r.get("recovered")),
        }

    overall = {
        "cases": len(rows),
        "status": dict(Counter(str(r.get("status")) for r in rows)),
        "trigger": rate(sum(1 for r in rows if r.get("trigger_reached")), len(rows)),
        "recovery_o2": rate(sum(1 for r in o2_valid if r.get("recovered")), len(o2_valid)),
        "c0": rate(sum(1 for r in c0_valid if r.get("recovered")), len(c0_valid)),
        "l0": rate(sum(1 for r in l0_valid if r.get("recovered")), len(l0_valid)),
        # Legacy run-report denominator: valid non-C0 injections (O2 + L0).
        # Kept only so older report.md numbers stay traceable.
        "recovery_non_control": rate(
            sum(1 for r in o2_valid + l0_valid if r.get("recovered")),
            len(o2_valid) + len(l0_valid),
        ),
        "validity": {
            "o2": rate(len(o2_valid), len(o2)),
            "c0": rate(len(c0_valid), len(c0)),
            "l0": rate(len(l0_valid), len(l0)),
        },
        "invalid_reasons": dict(invalid_reasons),
        "outcomes": outcomes,
        "early_stopped": sum(1 for r in rows if r.get("early_stopped")),
        "steps_median": median([float(r.get("steps") or 0) for r in rows]),
        "elapsed_s_median": median(
            [float(r.get("elapsed_s") or 0) for r in rows if r.get("elapsed_s")]
        ),
        "notice_latency_median": median(
            [
                float(r["notice_latency"])
                for r in o2_valid
                if isinstance(r.get("notice_latency"), (int, float))
            ]
        ),
        "penetration_m_max": max(penetration) if penetration else None,
        "arms": {
            "O2": group(o2),
            "C0": group(c0),
            "L0": group(l0),
        },
    }

    by_suite: dict[str, dict] = {}
    for suite in sorted({str(r.get("suite")) for r in rows}):
        subset = [r for r in rows if str(r.get("suite")) == suite]
        sub_o2 = [r for r in subset if arm_of(r) == "O2" and r.get("case_valid")]
        sub_c0 = [r for r in subset if arm_of(r) == "C0" and r.get("case_valid")]
        sub_l0 = [r for r in subset if arm_of(r) == "L0" and r.get("case_valid")]
        by_suite[suite] = {
            "cases": len(subset),
            "trigger": rate(sum(1 for r in subset if r.get("trigger_reached")), len(subset)),
            "o2_valid": len(sub_o2),
            "o2_total": sum(1 for r in subset if arm_of(r) == "O2"),
            "recovery_o2": rate(sum(1 for r in sub_o2 if r.get("recovered")), len(sub_o2)),
            "c0": rate(sum(1 for r in sub_c0 if r.get("recovered")), len(sub_c0)),
            "l0": rate(sum(1 for r in sub_l0 if r.get("recovered")), len(sub_l0)),
            "steps_median": median([float(r.get("steps") or 0) for r in subset]),
            "elapsed_s_median": median(
                [float(r.get("elapsed_s") or 0) for r in subset if r.get("elapsed_s")]
            ),
        }

    by_level: dict[str, dict] = {}
    for level in ["L1", "L2", "L3", "L4", "L5", "O2"]:
        subset = [r for r in o2_valid if level_of(r) == level]
        if not subset:
            continue
        by_level[level] = {
            "valid": len(subset),
            "recovered": sum(1 for r in subset if r.get("recovered")),
            "recovery": rate(sum(1 for r in subset if r.get("recovered")), len(subset)),
        }

    by_task: dict[str, dict] = {}
    for task in sorted({str(r.get("bddl_name")) for r in o2}):
        attempted = [r for r in o2 if str(r.get("bddl_name")) == task]
        subset = [r for r in attempted if r.get("case_valid")]
        by_task[task] = {
            "suite": attempted[0].get("suite"),
            "attempted": len(attempted),
            "triggered": sum(1 for r in attempted if r.get("trigger_reached")),
            "valid": len(subset),
            "recovered": sum(1 for r in subset if r.get("recovered")),
        }

    return {
        "overall": overall,
        "by_suite": by_suite,
        "by_level": by_level,
        "by_task": by_task,
        "cost": {
            "episodes": len(rows),
            "elapsed_total_s": round(sum(float(r.get("elapsed_s") or 0) for r in rows), 1),
            "elapsed_total_h": round(sum(float(r.get("elapsed_s") or 0) for r in rows) / 3600.0, 2),
            "steps_total": sum(int(r.get("steps") or 0) for r in rows),
        },
    }


def binom_two_sided(k: int, n: int) -> float:
    """Exact two-sided binomial p-value for p=0.5 (McNemar exact)."""

    if n <= 0:
        return 1.0
    probs = [math.comb(n, i) for i in range(n + 1)]
    total = float(sum(probs))
    observed = probs[k]
    return min(1.0, sum(p for p in probs if p <= observed) / total)


def paired(rows_a: list[dict], rows_b: list[dict]) -> dict:
    """McNemar-style paired comparison of two policies on identical case ids."""

    index_a = {r["case_id"]: r for r in rows_a if r.get("case_id")}
    index_b = {r["case_id"]: r for r in rows_b if r.get("case_id")}
    shared = [c for c in index_a if c in index_b]
    both = only_a = only_b = neither = invalid = 0
    per_suite: dict[str, Counter] = defaultdict(Counter)
    for case_id in shared:
        a, b = index_a[case_id], index_b[case_id]
        if arm_of(a) != "O2":
            continue
        if not (a.get("case_valid") and b.get("case_valid")):
            invalid += 1
            continue
        ra, rb = bool(a.get("recovered")), bool(b.get("recovered"))
        suite = str(a.get("suite"))
        if ra and rb:
            both += 1
            per_suite[suite]["both"] += 1
        elif ra:
            only_a += 1
            per_suite[suite]["only_a"] += 1
        elif rb:
            only_b += 1
            per_suite[suite]["only_b"] += 1
        else:
            neither += 1
            per_suite[suite]["neither"] += 1
    discordant = only_a + only_b
    return {
        "shared_cases": len(shared),
        "o2_both_valid": both + only_a + only_b + neither,
        "dropped_not_valid_in_both": invalid,
        "both": both,
        "only_a": only_a,
        "only_b": only_b,
        "neither": neither,
        "mcnemar_p": binom_two_sided(min(only_a, only_b), discordant),
        "by_suite": {suite: dict(counter) for suite, counter in sorted(per_suite.items())},
    }


def render(summary: dict, title: str) -> str:
    o = summary["overall"]
    lines = [f"## {title}", "", "| metric | value |", "|---|---|"]
    lines.append(f"| cases | {o['cases']} |")
    lines.append(f"| trigger rate | {fmt_rate(o['trigger'])} |")
    lines.append(f"| **O2 Recovery (valid only)** | **{fmt_rate(o['recovery_o2'])}** |")
    lines.append(f"| L0 Recovery | {fmt_rate(o['l0'])} |")
    lines.append(
        f"| Recovery, legacy non-C0 denominator (O2+L0) | "
        f"{fmt_rate(o['recovery_non_control'])} |"
    )
    lines.append(f"| C0 no-op success (valid injections only) | {fmt_rate(o['c0'])} |")
    lines.append(
        "| C0 goal preserved / triggered | "
        f"{o['outcomes']['c0_preserved']}/{o['outcomes']['c0_triggered']} |"
    )
    lines.append(
        f"| valid injections O2 / C0 / L0 | {fmt_rate(o['validity']['o2'])} / "
        f"{fmt_rate(o['validity']['c0'])} / {fmt_rate(o['validity']['l0'])} |"
    )
    lines.append(
        "| outcomes | "
        + ", ".join(f"{key}={value}" for key, value in o["outcomes"].items())
        + " |"
    )
    lines.append(f"| early stopped | {o['early_stopped']} |")
    lines.append(f"| steps (median) | {o['steps_median']} |")
    lines.append(f"| notice latency (median, O2) | {o['notice_latency_median']} |")
    if o["invalid_reasons"]:
        lines.append(f"| invalid reasons | {o['invalid_reasons']} |")
    lines.append("")
    lines.append("### by suite")
    lines.append("")
    lines.append(
        "| suite | cases | trigger | O2 valid | O2 recovery | L0 | C0 | steps median |"
    )
    lines.append("|---|---:|---|---:|---|---|---|---:|")
    for suite, s in summary["by_suite"].items():
        lines.append(
            f"| {suite} | {s['cases']} | {pct(s['trigger']['rate'])} | "
            f"{s['o2_valid']}/{s['o2_total']} | {fmt_rate(s['recovery_o2'])} | "
            f"{fmt_rate(s['l0'])} | {fmt_rate(s['c0'])} | {s['steps_median']} |"
        )
    lines.append("")
    lines.append("### by O2 task (attempted / triggered / valid / recovered)")
    lines.append("")
    lines.append("| suite | task | attempted | triggered | valid | recovered |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for task, s in summary["by_task"].items():
        short = task if len(task) <= 52 else task[:49] + "..."
        lines.append(
            f"| {s['suite']} | {short} | {s['attempted']} | {s['triggered']} | "
            f"{s['valid']} | {s['recovered']} |"
        )
    cost = summary["cost"]
    lines.append("")
    lines.append(
        f"episode wall clock: {cost['elapsed_total_h']} h over {cost['episodes']} episodes, "
        f"{cost['steps_total']} env steps."
    )
    lines.append("")
    lines.append("### by O2 level")
    lines.append("")
    lines.append("| level | valid | recovered | rate |")
    lines.append("|---|---:|---:|---|")
    for level, s in summary["by_level"].items():
        lines.append(
            f"| {level} | {s['valid']} | {s['recovered']} | {fmt_rate(s['recovery'])} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path, help="run directories")
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--title", default="B-plus summary")
    parser.add_argument(
        "--compare",
        nargs="+",
        type=Path,
        default=None,
        help="reference runs; prints a paired comparison against `runs`",
    )
    parser.add_argument("--compare-title", default="A vs B")
    args = parser.parse_args(argv)

    rows = load_runs(args.runs)
    summary = summarize(rows)
    print(render(summary, args.title))
    payload: dict = {"summary": summary}
    if args.compare:
        other = load_runs(args.compare)
        paired_result = paired(other, rows)
        payload["paired"] = paired_result
        print("")
        print(f"## paired: {args.compare_title}")
        print("")
        print("| bucket | count |")
        print("|---|---:|")
        buckets = (
            "shared_cases",
            "o2_both_valid",
            "both",
            "only_a",
            "only_b",
            "neither",
            "dropped_not_valid_in_both",
        )
        for key in buckets:
            print(f"| {key} | {paired_result[key]} |")
        print(f"| McNemar exact p | {paired_result['mcnemar_p']:.4g} |")
        print("")
        print("| suite | both | only_a | only_b | neither |")
        print("|---|---:|---:|---:|---:|")
        for suite, counts in paired_result["by_suite"].items():
            print(
                f"| {suite} | {counts.get('both', 0)} | {counts.get('only_a', 0)} | "
                f"{counts.get('only_b', 0)} | {counts.get('neither', 0)} |"
            )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
