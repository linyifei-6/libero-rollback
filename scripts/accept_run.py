"""Acceptance checks for a batched evaluation run.

Verifies, for every case of one or more ``run_batched_eval.py`` output directories:

  structure     one baseline and one perturbation record per case, no duplicate runs left behind
  pairing       the runtime's own strict-pairing audit passed for every injected case
  evidence      injection validity, clearance-search evidence and the final penetration agree
  classification  the repo classifier's verdict is recomputed and compared with the summary
  provenance    if a summary file is given, per-case counters must match the raw records

Exit status is 1 when any check fails, so this can gate a report.

Usage:
    python scripts/accept_run.py --run runs/eval-mid-d0-pi05-fixed \
        --summary runs/eval-mid-d0-pi05-fixed/d0-mid-pi05-summary.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from libero_rollback.evidence import classify_result  # noqa: E402


def load_catalog() -> dict[str, dict]:
    """Case definitions for classification.

    Retired families live in archived snapshots, and a run that used them stays auditable only
    if classification uses the definition that was in force when it ran.  Archived definitions
    are therefore loaded as well; a live case always wins on an ID collision.
    """

    cases: dict[str, dict] = {}
    for archived in sorted((ROOT / "archive").glob("*/case-definitions/*.yaml")):
        case = yaml.safe_load(archived.read_text())
        if isinstance(case, dict) and case.get("case_id"):
            cases[case["case_id"]] = case
    manifest = yaml.safe_load((ROOT / "dataset/current/manifest.yaml").read_text())
    for entry in manifest["cases"]:
        cases[entry["case_id"]] = yaml.safe_load((ROOT / entry["path"]).read_text())
    return cases


def canonical(case_name: str) -> str:
    stripped = case_name[len("dataset_"):] if case_name.startswith("dataset_") else case_name
    return stripped.replace("_", "-")


def collect(run_root: Path, catalog: dict[str, dict]) -> tuple[list[dict], list[str]]:
    problems: list[str] = []
    rows: list[dict] = []
    for task_dir in sorted(run_root.glob("task*")):
        binding_path = task_dir / "binding.yaml"
        result_files = sorted((task_dir / "run").rglob("results.json"))
        if not binding_path.exists() or not result_files:
            problems.append(f"{task_dir.name}: missing binding or results.json")
            continue
        if len(result_files) > 1:
            problems.append(
                f"{task_dir.name}: {len(result_files)} results.json snapshots present "
                f"({[p.parent.name for p in result_files]}) -- stale run left behind?"
            )
        enabled = yaml.safe_load(binding_path.read_text())["perturbation_binding"]["enabled_cases"]
        latest = result_files[-1]
        doc = json.loads(latest.read_text())
        for task in doc.values():
            baselines = [v for v in task["results"].values() if v.get("kind") == "baseline"]
            perturbations = {k: v for k, v in task["results"].items()
                             if v.get("kind") == "perturbation"}
            if len(baselines) != 1:
                problems.append(f"{task_dir.name}: {len(baselines)} baseline records (expected 1)")
            if len(perturbations) != len(enabled):
                problems.append(
                    f"{task_dir.name}: {len(perturbations)} records for "
                    f"{len(enabled)} binding cases"
                )
            for label, value in perturbations.items():
                match = next((e for e in enabled if e["case_name"] in label), None)
                if match is None:
                    problems.append(f"{task_dir.name}: record {label} matches no binding case")
                    continue
                rows.append({
                    "task_dir": task_dir.name,
                    "case_id": canonical(match["case_name"]),
                    "label": label,
                    "baseline": baselines[0] if baselines else None,
                    "record": value,
                    "case": catalog.get(canonical(match["case_name"]), {}),
                })
    return rows, problems


def check(rows: list[dict]) -> tuple[list[str], Counter]:
    problems: list[str] = []
    verdicts: Counter = Counter()
    for row in rows:
        case_id = row["case_id"]
        record = row["record"]
        report = record.get("report") or {}
        observed = (report.get("intervention") or {}).get("observed") or {}
        baseline = row["baseline"] or {}
        valid = report.get("injection_valid")
        audit = record.get("pairing_audit") or {}

        # pairing: an injected case must carry a passing strict-pairing audit
        if valid is True and audit.get("eligible") is not True:
            problems.append(f"{case_id}: injection valid but pairing audit not eligible")
        if valid is True and audit.get("initial_observation_match") is not True:
            problems.append(f"{case_id}: paired baseline observation does not match")
        if valid is not True and audit:
            problems.append(f"{case_id}: rejected injection still carries a pairing audit")

        # evidence: the recorded search must explain the final penetration
        search = observed.get("clearance_search") or []
        final_pen = observed.get("max_penetration_m")
        requested = (report.get("intervention") or {}).get("requested") or {}
        budget = requested.get("maximum_penetration_m")
        if search:
            # the trace stores its measurements rounded, so compare with that tolerance
            last = search[-1]
            listed = float(last.get("max_penetration_m"))
            if abs(listed - float(final_pen)) > 1e-5:
                problems.append(
                    f"{case_id}: clearance search ends at {last.get('max_penetration_m')} "
                    f"but the record reports {final_pen}"
                )
            lift = float(observed.get("target_lift_m") or 0.0)
            if lift > 0 and abs(float(search[-1].get("lift_m") or 0.0) - lift) > 1e-9:
                problems.append(f"{case_id}: applied lift {lift} not the last search step")
        numeric = isinstance(final_pen, (int, float)) and isinstance(budget, (int, float))
        if valid is True and numeric:
            if final_pen > budget:
                problems.append(
                    f"{case_id}: accepted with penetration {final_pen} > budget {budget}"
                )

        # classification recomputed from the raw record; an unknown definition would be
        # classified as if it were a plain rollback case, so refuse to guess
        if not row["case"]:
            problems.append(f"{case_id}: no case definition found (live catalog or archive)")
            continue
        verdict = classify_result(row["case"], {"report": report,
                                                "injection_valid": valid})
        verdicts[verdict] += 1

        # a successful episode must not be counted as model recovery when the relation was
        # restored externally
        protocol = observed.get("temporal_protocol") or {}
        if protocol.get("external_restoration") is True and verdict == "valid_recovered":
            problems.append(f"{case_id}: external restoration classified as model recovery")
        # A `relation_recovered`-gated second event that never fired is the documented
        # outcome for a case the model did not repair: it is reported, not flagged."""


        # baseline must be successful for the case to be evaluable
        if baseline.get("success") is not True:
            problems.append(f"{case_id}: paired baseline failed; case is not evaluable")
    return problems, verdicts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--summary", type=Path, default=None)
    args = parser.parse_args()

    catalog = load_catalog()
    rows: list[dict] = []
    problems: list[str] = []
    for run in args.run:
        run_root = run if run.is_absolute() else ROOT / run
        collected, found = collect(run_root, catalog)
        rows.extend(collected)
        problems.extend(f"{run_root.name}: {item}" for item in found)

    problems.extend(check(rows)[0])
    verdicts = check(rows)[1]

    print(f"cases checked        : {len(rows)}")
    print(f"verdict distribution : {dict(verdicts)}")
    baseline_ok = sum(1 for r in rows if (r['baseline'] or {}).get('success') is True)
    print(f"paired baseline ok   : {baseline_ok}/{len(rows)}")

    if args.summary is not None:
        summary_path = args.summary if args.summary.is_absolute() else ROOT / args.summary
        summary = json.loads(summary_path.read_text())
        totals = summary.get("totals", {})
        expected = {
            "cases": len(rows),
            "baseline_success": baseline_ok,
            "injection_valid": sum(
                verdicts[name] for name in (
                    "valid_recovered", "valid_not_recovered",
                    "valid_external_restoration", "protocol_incomplete",
                )
            ),
            "model_recovered": verdicts["valid_recovered"],
        }
        for key, value in expected.items():
            if key in totals and totals[key] != value:
                problems.append(
                    f"summary.{key}={totals[key]} disagrees with the records ({value})"
                )
        if "model_recovered" in totals:
            external = verdicts["valid_external_restoration"]
            print(f"external restorations: {external} (excluded from model recovery)")

    print()
    if problems:
        print(f"FAILED with {len(problems)} problem(s):")
        for item in problems:
            print("  - " + item)
        return 1
    print("PASS: structure, pairing, clearance evidence, classification and provenance agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
