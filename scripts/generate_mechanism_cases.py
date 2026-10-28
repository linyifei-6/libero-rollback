"""Generate the mechanism-dimension batch on top of the grid generator.

Emits two cases per eligible task, reusing ``generate_grid_cases`` for the task
vocabulary, goal predicates and destination shapes:

  * ``transient``  — the revoked relation is briefly restored (``pre_injection``);
  * ``second``     — a second revocation while recovery is under way.

Eligible tasks are those whose first completed placement can be revoked and that
expose at least the early time point: every task except the two single-goal tasks
whose only destination set is the closure boundary (they remain eligible too, as
the mechanism is about the second write, not the trigger).

Usage:
    python scripts/generate_mechanism_cases.py --write            # staging only
    python scripts/generate_mechanism_cases.py --write --into-release
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "runs/mechanism-staging"
RELEASE_CASES = ROOT / "dataset/v1.2/cases"

TRANSIENT = {"after_steps": 20, "destination": "pre_injection"}
SECOND = {
    "after_steps": 60,
    "destination": "initial_offset",
    "offset_m": [0.05, 0.05, 0.0],
    "offset_frame": "task_frame",
}

# Which magnitude each mechanism probe revokes to, so the mechanism is the only
# variable against an existing grid case.
BASE_PLAN = {"suffix": "n5", "plan": "offset"}


def _load_generator():
    path = ROOT / "scripts/generate_grid_cases.py"
    spec = importlib.util.spec_from_file_location("gridgen", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def mechanism_cases(gen) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for task_index in sorted(gen.TASKS):
        window = "early"
        for label, block in (("transient", TRANSIENT), ("second-revocation", SECOND)):
            spec = {
                "goal": "place",
                "window": window,
                "suffix": BASE_PLAN["suffix"],
                "plan": BASE_PLAN["plan"],
            }
            case = gen.build_case(task_index, spec)
            slug = case["case_id"].rsplit("-", 2)[0]
            case["case_id"] = f"{slug}-{label}"
            case["transient"] = dict(block)
            case["severity_rationale"] = (
                f"Mechanism probe ({label}): reuses the 5 cm offset magnitude so the "
                "second state write is the only variable against its grid counterpart."
            )
            case["intervention_description"] = (
                "Revoke the first completed placement and then "
                + (
                    "restore the pre-injection pose so the relation is briefly true again."
                    if label == "transient"
                    else "revoke it a second time while recovery is under way."
                )
                + " Retain the instruction and every other goal."
            )
            case["stage"]["description"] = (
                f"{label}: {case['stage']['description']}"
            )
            out.append((label, case))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--into-release", action="store_true",
                        help="also write into dataset/v1.2/cases (do not use mid-sweep)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    gen = _load_generator()
    cases = mechanism_cases(gen)
    for label, case in cases:
        if args.verbose:
            print(f"  {case['case_id']:<62} {label}")
    print(f"mechanism cases: {len(cases)} across {len(gen.TASKS)} tasks")

    if args.write:
        STAGING.mkdir(parents=True, exist_ok=True)
        for _, case in cases:
            (STAGING / f"{case['case_id']}.yaml").write_text(
                yaml.safe_dump(case, sort_keys=True, allow_unicode=True, width=100),
                encoding="utf-8",
            )
        print(f"wrote {len(cases)} cases to {STAGING}")
    if args.into_release:
        for _, case in cases:
            (RELEASE_CASES / f"{case['case_id']}.yaml").write_text(
                yaml.safe_dump(case, sort_keys=True, allow_unicode=True, width=100),
                encoding="utf-8",
            )
        print(f"wrote {len(cases)} cases into {RELEASE_CASES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
