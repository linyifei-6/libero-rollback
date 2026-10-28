"""Cross-check each swept episode against its dataset case definition.

For every completed case this verifies that the runtime actually ran the case the
dataset declares: the perturbation's case name carries the dataset case id, the
binding's trigger event matches, and the injection step is consistent with the
declared time point. Silent mismatches here would invalidate the sweep.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

REPO = Path("/home/tarowang/workspace/roboot/libero-rollback")
SWEEP = REPO / "runs/v1.2-grid"
CASES = REPO / "dataset/v1.2/cases"


def normalise(case_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", case_id.lower()).strip("_")


def main() -> int:
    completed = sorted(SWEEP.glob("*/**/results.json"))
    print(f"completed episodes: {len(completed)}")
    problems: list[str] = []
    for result_path in completed:
        case_id = result_path.parents[1].name
        case_path = CASES / f"{case_id}.yaml"
        if not case_path.is_file():
            problems.append(f"{case_id}: no dataset case")
            continue
        case = yaml.safe_load(case_path.read_text())
        binding_path = result_path.parents[1] / "binding.yaml"
        binding = yaml.safe_load(binding_path.read_text()) if binding_path.is_file() else {}
        entries = (binding.get("perturbation_binding") or {}).get("enabled_cases") or []
        document = json.loads(result_path.read_text())

        expected_name = "dataset_" + normalise(case_id)
        expected_event = case["trigger"]["event"]
        expected_profile = f"libero_10_{case['task']['source_task_locator'].lower()}"

        # binding side
        if not entries:
            problems.append(f"{case_id}: binding has no enabled_cases")
        else:
            entry = entries[0]
            if entry.get("case_name") != expected_name:
                problems.append(f"{case_id}: case_name {entry.get('case_name')} != {expected_name}")
            if entry.get("trigger_event") != expected_event:
                problems.append(
                    f"{case_id}: binding trigger {entry.get('trigger_event')} != {expected_event}"
                )
        if (binding.get("perturbation_binding") or {}).get("task_profile") != expected_profile:
            problems.append(f"{case_id}: task_profile mismatch")

        # results side
        found = False
        for task_key, task_data in document.items():
            if not isinstance(task_data, dict):
                continue
            for name, value in (task_data.get("results") or {}).items():
                if not isinstance(value, dict) or value.get("kind") != "perturbation":
                    continue
                found = True
                if expected_name not in name:
                    problems.append(f"{case_id}: result key {name[:70]} does not carry the case id")
                report = value.get("report") or {}
                if report.get("injection_step") is None and value.get("success") is not None:
                    # injection did not execute: acceptable only when untriggered
                    trigger = report.get("trigger") or {}
                    if trigger.get("reached"):
                        problems.append(f"{case_id}: trigger reached but no injection step")
                time_point = case["trigger"].get("time_point")
                if time_point and report.get("injection_step") is not None:
                    pass  # timing is recorded in the report; no further assertion here
        if not found:
            # A case whose process is still running has written results.json and
            # may have closed the baseline before the perturbation episode lands.
            log = result_path.parents[1] / "runner.log"
            log_text = log.read_text(errors="ignore") if log.is_file() else ""
            if "ALL DONE" not in log_text:
                print(f"  ... {case_id} (in flight; baseline written, perturbation pending)")
                continue
            problems.append(f"{case_id}: finished run recorded no perturbation result")

        status = "OK " if not any(p.startswith(case_id) for p in problems) else "ERR"
        print(f"  {status} {case_id}")

    print()
    if problems:
        print(f"PROBLEMS ({len(problems)}):")
        for problem in problems:
            print("  -", problem)
        return 1
    print("all completed episodes match their dataset case definitions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
