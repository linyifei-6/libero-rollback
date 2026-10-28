"""Summarise a grid sweep: progress, per-dimension recovery, and failures.

Reads ``runs/v1.2-grid/<case_id>/**/results.json`` produced by
``scripts/run_grid_cases.py`` and reports the runtime dimensions each case
belongs to, so partial sweeps are readable while they run.

Usage:
    python scripts/analyze_grid_sweep.py
    python scripts/analyze_grid_sweep.py --output runs/v1.2-grid/summary.json --json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "dataset/v1.2/cases"

DIMENSION_KEYS = ("time_point", "destination", "goal_kind")


def case_index() -> dict[str, dict]:
    index = {}
    for path in sorted(CASES.glob("*.yaml")):
        case = yaml.safe_load(path.read_text())
        state = case["rollback_target"]["state_change"]
        index[case["case_id"]] = {
            "task_id": case["task"]["task_id"],
            "time_point": case["trigger"].get("time_point"),
            "trigger_event": case["trigger"]["event"],
            "state_change_kind": state["kind"],
            "severity": case["severity"],
            "goal_kind": (
                "articulation" if state["kind"] == "revert_articulation_goal" else "placement"
            ),
            "destination": state["kind"],
            "offset_m": state.get("offset_m"),
            "clearance_m": state.get("clearance_m"),
            "setback": state.get("setback"),
        }
    return index


def load_episodes(sweep: Path, index: dict[str, dict]) -> list[dict]:
    rows = []
    for result_path in sorted(sweep.rglob("results.json")):
        case_id = result_path.parents[1].name
        meta = index.get(case_id, {})
        try:
            document = json.loads(result_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for task_data in document.values():
            if not isinstance(task_data, dict):
                continue
            results = task_data.get("results", {})
            if not isinstance(results, dict):
                continue
            perturbation = next(
                (v for v in results.values() if isinstance(v, dict) and v.get("kind") == "perturbation"),
                None,
            )
            baseline = next(
                (v for v in results.values() if isinstance(v, dict) and v.get("kind") == "baseline"),
                None,
            )
            if perturbation is None:
                continue
            report = perturbation.get("report") or {}
            outcome = report.get("outcome") or {}
            trace = outcome.get("task_predicate_trace") or {}
            rows.append({
                "case_id": case_id,
                "result_path": str(result_path.relative_to(ROOT)),
                **meta,
                "injection_valid": report.get("injection_valid"),
                "task_success": perturbation.get("success"),
                "baseline_success": baseline.get("success") if baseline else None,
                "steps": perturbation.get("steps"),
                "baseline_steps": baseline.get("steps") if baseline else None,
                "recovered": outcome.get("recovered"),
                "recovery_latency_steps": outcome.get("recovery_latency_steps"),
                "recovery_verified": (outcome.get("recovery_verification") or {}).get(
                    "recovery_verified"
                ),
                "failure_reason": trace.get("final_success_false_reason"),
                "recovery_cost": outcome.get("recovery_cost"),
            })
    return rows


def _rate(hit: int, total: int) -> str:
    return "n/a" if not total else f"{hit / total:.1%}"


def _median(values):
    numbers = sorted(v for v in values if isinstance(v, (int, float)))
    if not numbers:
        return None
    mid = len(numbers) // 2
    return numbers[mid] if len(numbers) % 2 else (numbers[mid - 1] + numbers[mid]) / 2


def summarise(rows: list[dict], total_cases: int) -> dict:
    valid = [r for r in rows if r["injection_valid"] is True]
    recovered = [r for r in valid if r["task_success"] is True]

    def group(key: str) -> list[dict]:
        buckets: dict[str, list[dict]] = defaultdict(list)
        for row in valid:
            buckets[str(row.get(key))].append(row)
        return [
            {
                "key": name,
                "valid": len(items),
                "recovered": sum(1 for r in items if r["task_success"] is True),
                "rate": _rate(sum(1 for r in items if r["task_success"] is True), len(items)),
            }
            for name, items in sorted(buckets.items())
        ]

    steps_delta = [
        r["steps"] - r["baseline_steps"]
        for r in valid
        if isinstance(r.get("steps"), (int, float)) and isinstance(r.get("baseline_steps"), (int, float))
    ]
    return {
        "planned_cases": total_cases,
        "episodes": len(rows),
        "injection_valid": len(valid),
        "injection_invalid": len(rows) - len(valid),
        "recovered": len(recovered),
        "recovery_rate": _rate(len(recovered), len(valid)),
        "baseline_success": sum(1 for r in rows if r["baseline_success"] is True),
        "by_time_point": group("time_point"),
        "by_goal_kind": group("goal_kind"),
        "by_destination": group("state_change_kind"),
        "by_task": group("task_id"),
        "steps_delta_median": _median(steps_delta),
        "recovered_detail": [
            {
                "case_id": r["case_id"],
                "time_point": r.get("time_point"),
                "goal_kind": r.get("goal_kind"),
                "destination": r.get("state_change_kind"),
                "latency": r.get("recovery_latency_steps"),
                "steps": r.get("steps"),
                "baseline_steps": r.get("baseline_steps"),
                "verified": r.get("recovery_verified"),
            }
            for r in recovered
        ],
        "invalid_detail": [
            {
                "case_id": r["case_id"],
                "errors": (r.get("recovery_cost") or {}).get("validity_errors"),
            }
            for r in rows
            if r["injection_valid"] is not True
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep", type=Path, default=ROOT / "runs/v1.2-grid")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    sweep = args.sweep if args.sweep.is_absolute() else ROOT / args.sweep
    index = case_index()
    rows = load_episodes(sweep, index)
    summary = summarise(rows, len(index))

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"progress: {summary['episodes']}/{summary['planned_cases']} episodes")
        print(f"injection valid : {summary['injection_valid']}  (invalid {summary['injection_invalid']})")
        print(f"baseline success: {summary['baseline_success']}")
        print(f"recovered       : {summary['recovered']} / {summary['injection_valid']}"
              f"  ({summary['recovery_rate']})")
        print(f"steps delta     : median {summary['steps_delta_median']}")
        for label, key in (("time point", "by_time_point"), ("goal kind", "by_goal_kind"),
                           ("destination", "by_destination"), ("task", "by_task")):
            print(f"\n--- by {label} ---")
            for bucket in summary[key]:
                print(f"  {bucket['key']:<34} {bucket['recovered']}/{bucket['valid']:<4} {bucket['rate']}")
        if summary["recovered_detail"]:
            print("\n--- recovered episodes ---")
            for row in summary["recovered_detail"]:
                print(f"  {row['case_id']:<56} latency={row['latency']} "
                      f"steps={row['steps']} verified={row['verified']}")
        if summary["invalid_detail"]:
            print("\n--- invalid injections ---")
            for row in summary["invalid_detail"]:
                print(f"  {row['case_id']:<56} {row['errors']}")

    if args.output:
        target = args.output if args.output.is_absolute() else ROOT / args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nwrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
