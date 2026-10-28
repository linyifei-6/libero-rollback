"""Summarize native-state evidence without treating it as model recovery."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def summarize(directory: Path) -> dict:
    manifest = yaml.safe_load((ROOT / "dataset/current/manifest.yaml").read_text())
    entries = {entry["case_id"]: entry for entry in manifest["cases"]}
    cases, tasks, errors = {}, [], []
    for path in sorted(directory.rglob("libero_10_t*.json")):
        document = json.loads(path.read_text())
        counts = Counter()
        for case_id, row in document["cases"].items():
            if case_id not in entries:
                errors.append(f"unknown case {case_id}: {path}")
                continue
            if case_id in cases:
                errors.append(f"multiple preflight attempts for {case_id}: {path}")
                continue
            digest = hashlib.sha256((ROOT / entries[case_id]["path"]).read_bytes()).hexdigest()
            status = row["status"]
            if row.get("case_sha256") != digest:
                status = "stale_definition"
            if document["baseline_native_success"] is not True:
                status = "baseline_failed"
            if row.get("coordinates_restored") is False:
                status = "state_restoration_failed"
                errors.append(f"simulator state was not restored for {case_id}")
            cases[case_id] = {**row, "status": status, "evidence_file": str(path)}
            counts[status] += 1
        tasks.append(
            {
                "task_profile": document["task_profile"],
                "baseline_native_success": document["baseline_native_success"],
                "counts": dict(counts),
            }
        )
    for case_id in entries.keys() - cases.keys():
        cases[case_id] = {"case_id": case_id, "status": "not_run"}
    return {
        "schema_version": "libero-rollback.native-preflight-summary.v1",
        "definition_count": len(entries),
        "observed_task_count": len(tasks),
        "model_recovery_evaluated": False,
        "counts": dict(Counter(row["status"] for row in cases.values())),
        "tasks": tasks,
        "cases": cases,
        "errors": errors,
        "scope": (
            "Native endpoint trials on baseline states; temporal continuation and joint drives "
            "require live validation."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.preflight_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k not in {"cases", "tasks"}}, indent=2))
    return int(bool(result["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
