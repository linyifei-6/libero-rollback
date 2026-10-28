"""Check the v1.3 run root: progress, articulation verdicts, envelope consistency.

Guards against the mistake made while seeding this run: episodes measured under one
drive envelope must not be mixed with episodes measured under another. Every
articulation episode's recorded binding must carry the calibrated envelope.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO = Path("/home/tarowang/workspace/roboot/libero-rollback")
V13 = REPO / "dataset/v1.3/cases"
OUT = REPO / "runs/v1.3-grid"
RUNTIME = REPO / "runs/full-coverage/runtime"

TEMPLATE = yaml.safe_load(
    (RUNTIME / "configs/perturbation_templates/high_value/hv_articulation_goal_rollback.yaml").read_text()
)["case_template"]["intervention"]["parameters"]

v13_ids = {p.stem for p in V13.glob("*.yaml")}
dirs = [d for d in OUT.iterdir() if d.is_dir() and d.name in v13_ids]

# A seeded case keeps its v1.2 log, so progress must be judged from the output path
# the log records, not from the presence of a log or a results file.
fresh, reused, in_flight, pending = [], [], [], []
for case_dir in sorted(dirs, key=lambda p: p.name):
    log = case_dir / "runner.log"
    text = log.read_text(errors="ignore") if log.exists() else ""
    done = "ALL DONE" in text
    if done and "runs/v1.3-grid" in text:
        fresh.append(case_dir)
    elif done:
        reused.append(case_dir)
    elif text:
        in_flight.append(case_dir)
    else:
        pending.append(case_dir)

print(f"planned {len(v13_ids)}")
print(f"  fresh v1.3 episodes : {len(fresh)}")
print(f"  reused v1.2 evidence: {len(reused)}")
print(f"  in flight           : {len(in_flight)}"
      + (f"  {[d.name for d in in_flight]}" if in_flight else ""))
# the runner creates case directories lazily, so anything without a directory is
# still pending rather than absent
not_created = len(v13_ids) - len(dirs)
print(f"  not started         : {len(pending) + not_created}"
      + (f"  ({len(pending)} created, {not_created} not yet created)" if not_created else ""))

with_results = fresh
print(f"expected envelope: force={TEMPLATE['linear_force_limit_n']} "
      f"steps={TEMPLATE['monitor_steps_after_completion']}")

problems: list[str] = []
articulation_ok = articulation_bad = 0
for case_dir in sorted(with_results):
    if "close-" not in case_dir.name:
        continue
    for binding_path in case_dir.glob("*/binding.yaml"):
        params = yaml.safe_load(binding_path.read_text())[
            "perturbation_binding"]["enabled_cases"][0]["parameters"]
        if params.get("linear_force_limit_n") != TEMPLATE["linear_force_limit_n"]:
            problems.append(
                f"{case_dir.name}: binding force {params.get('linear_force_limit_n')} "
                f"!= template {TEMPLATE['linear_force_limit_n']}"
            )
    for result_path in case_dir.glob("*/results.json"):
        document = json.loads(result_path.read_text())
        for task_data in document.values():
            for value in (task_data.get("results") or {}).values():
                if not isinstance(value, dict) or value.get("kind") != "perturbation":
                    continue
                report = value.get("report") or {}
                observed = (report.get("intervention") or {}).get("observed") or {}
                requested = (report.get("intervention") or {}).get("requested") or {}
                achieved = observed.get("actual_setback_m") or observed.get("actual_setback")
                errors = [e.get("name") for e in (report.get("errors") or [])
                          if isinstance(e, dict)]
                valid = report.get("injection_valid") is True
                articulation_ok += bool(valid)
                articulation_bad += (not valid)
                print(f"  {'OK ' if valid else 'BAD'} {case_dir.name[:56]:<58} "
                      f"req={requested.get('setback')} achieved={achieved} "
                      f"errors={errors if errors else '[]'}")

print(f"\narticulation verdicts: valid {articulation_ok}  invalid {articulation_bad}")
if problems:
    print(f"\nENVELOPE CONSISTENCY PROBLEMS ({len(problems)}):")
    for problem in problems:
        print("  -", problem)
else:
    print("envelope consistency: all articulation bindings carry the calibrated envelope")
