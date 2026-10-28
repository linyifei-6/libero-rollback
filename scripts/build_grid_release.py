"""Assemble the dataset/v1.2 grid release from the generated cases.

Writes the templates registry, sources registry, coverage matrix and manifest
(includng SHA-256 digests) for the dimension-grid release. Case YAMLs themselves
are produced by ``scripts/generate_grid_cases.py --write``.

Usage:
    python scripts/build_grid_release.py
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
# Defaults describe the release being built; the CLI overrides them so a corrected
# vocabulary can ship as a new version while earlier releases stay intact.
RELEASE = ROOT / "dataset/v1.3"
CASES = RELEASE / "cases"
VERSION = "1.3.0"
SCHEMA = "schemas/rollback-case.v1.schema.json"

BASE_CONSTRAINTS = [
    "completed_relation_true_before_intervention",
    "target_relation_false_after_intervention",
    "object_released_before_intervention",
    "zero_velocity_after_intervention",
    "target_pose_within_workspace",
    "target_pose_collision_free",
    "no_object_penetration",
    "task_remains_solvable",
    "baseline_task_solvable",
]
ARTICULATION_CONSTRAINTS = [
    "completed_relation_true_before_intervention",
    "target_relation_false_after_intervention",
    "zero_velocity_after_intervention",
    "no_object_penetration",
    "task_remains_solvable",
    "baseline_task_solvable",
]


def build_templates() -> None:
    templates = yaml.safe_load((ROOT / "dataset/v1.1/templates.yaml").read_text())
    templates["templates"] += [
        {
            "template_id": "completed-relation-rollback/container-above/v1",
            "description": (
                "Invalidate one completed placement by hovering the object above its own "
                "container instead of returning it to the table."
            ),
            "source_ids": [
                "runtime-grid-expansion-20261009",
                "scenario-timing-position-matrix-20260926",
            ],
            "state_change_kind": "restore_container_above_pose",
            "required_validity_constraints": BASE_CONSTRAINTS,
            "task_parameters": [
                "task_id", "completed_relation_predicate", "affected_object",
                "trigger_window", "clearance_m", "above_container_top",
            ],
        },
        {
            "template_id": "completed-relation-rollback/articulation-goal/v1",
            "description": (
                "Invalidate a completed articulation goal by driving its joint back out of "
                "the completed state during or just after the closing action."
            ),
            "source_ids": [
                "runtime-grid-expansion-20261009",
                "scenario-validity-severity-guidance-20260922",
            ],
            "state_change_kind": "revert_articulation_goal",
            "required_validity_constraints": ARTICULATION_CONSTRAINTS,
            "task_parameters": [
                "task_id", "articulation_goal", "joint_role", "trigger_window",
                "setback", "position_tolerance",
            ],
        },
    ]
    seen: set[str] = set()
    unique = []
    for template in templates["templates"]:
        if template["template_id"] in seen:
            continue
        seen.add(template["template_id"])
        unique.append(template)
    templates["templates"] = unique
    (RELEASE / "templates.yaml").write_text(
        yaml.safe_dump(templates, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )


def build_sources() -> None:
    sources = yaml.safe_load((ROOT / "dataset/v1.1/sources.yaml").read_text())
    sources["sources"]["runtime-grid-expansion-20261009"] = {
        "title": "Runtime rollback dimension grid adopted by libero-rollback",
        "repository": "https://github.com/linyifei-6/libero-runtime",
        "paths": [
            "configs/task_profiles/",
            "libero_runtime/engine/interventions/completed_subgoal_rollback.py",
            "libero_runtime/engine/interventions/articulation_setback.py",
            "libero_runtime/engine/context.py",
        ],
        "use": (
            "Defines the time points (early/mid/later plus the closure instant), the "
            "destination classes (initial pose, signed offsets, pre-grasp checkpoint, "
            "container-above hover) and the articulation-setback mechanism adopted by the "
            "1.2.0 grid cases. The rollback target is the first subgoal completed in "
            "execution order, as the engine binds that alias at run time; magnitudes "
            "remain project choices."
        ),
        "semantic_group": "runtime_dimension_grid",
    }
    (RELEASE / "sources.yaml").write_text(
        yaml.safe_dump(sources, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )


def build_coverage(case_docs: list[dict]) -> None:
    coverage = yaml.safe_load((ROOT / "dataset/v1.1/coverage.yaml").read_text())
    coverage["coverage_version"] = 2
    per_task: dict[str, list[dict]] = {row["task_id"]: [] for row in coverage["tasks"]}
    for case in case_docs:
        per_task[case["task"]["task_id"]].append(case)
    for row in coverage["tasks"]:
        docs = per_task[row["task_id"]]
        row["case_ids"] = sorted(case["case_id"] for case in docs)
        row["case_count"] = len(docs)
        row["covered_state_change_kinds"] = sorted(
            {case["rollback_target"]["state_change"]["kind"] for case in docs}
        )
        row["covered_trigger_events"] = sorted({case["trigger"]["event"] for case in docs})
    coverage["task_id_rule"] = (
        "libero_10/NN follows the ten base entries in tasks_info.txt; NN is the "
        "zero-padded list index."
    )
    (RELEASE / "coverage.yaml").write_text(
        yaml.safe_dump(coverage, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )


def build_manifest(case_paths: list[Path], case_docs: list[dict]) -> None:
    case_entries = [
        {
            "case_id": case["case_id"],
            "path": str(path.relative_to(ROOT)),
            "source_id": case["source"]["case_source_id"],
        }
        for path, case in zip(case_paths, case_docs, strict=True)
    ]
    manifest_files = [
        SCHEMA,
        f"{RELEASE.relative_to(ROOT)}/coverage.yaml",
        f"{RELEASE.relative_to(ROOT)}/sources.yaml",
        f"{RELEASE.relative_to(ROOT)}/templates.yaml",
    ] + [entry["path"] for entry in case_entries]
    (RELEASE / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "manifest_version": 1,
                "dataset_name": "libero-rollback",
                "dataset_version": VERSION,
                "schema_version": "libero-rollback.case.v1",
                "release_status": "candidate",
                "validation": {
                    "validator": "libero-rollback",
                    "validator_version": "1.0.0",
                    "status": "pending",
                    "checks": ["validate-dataset", "check-manifest"],
                    "scope": (
                        "YAML/JSON Schema validity, cross-file IDs and counts, file "
                        "references, and SHA-256 integrity"
                    ),
                },
                "schema_file": SCHEMA,
                "coverage_file": f"{RELEASE.relative_to(ROOT)}/coverage.yaml",
                "sources_file": f"{RELEASE.relative_to(ROOT)}/sources.yaml",
                "templates_file": f"{RELEASE.relative_to(ROOT)}/templates.yaml",
                "cases": case_entries,
                "files": [
                    {"path": path, "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}
                    for path in manifest_files
                ],
            },
            sort_keys=False,
            allow_unicode=True,
            width=100,
        ),
        encoding="utf-8",
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", default="dataset/v1.3")
    parser.add_argument("--version", default="1.3.0")
    args = parser.parse_args()

    global RELEASE, CASES, VERSION
    RELEASE = ROOT / args.release
    CASES = RELEASE / "cases"
    VERSION = args.version

    case_paths = sorted(CASES.glob("*.yaml"))
    if not case_paths:
        raise SystemExit("no cases found; run scripts/generate_grid_cases.py --write first")
    case_docs = [yaml.safe_load(path.read_text()) for path in case_paths]
    RELEASE.mkdir(parents=True, exist_ok=True)
    build_templates()
    build_sources()
    build_coverage(case_docs)
    build_manifest(case_paths, case_docs)
    counts: dict[str, int] = {}
    for case in case_docs:
        counts[case["task"]["task_id"]] = counts.get(case["task"]["task_id"], 0) + 1
    print(f"dataset/v1.2: {len(case_paths)} cases")
    for task_id in sorted(counts):
        print(f"  {task_id}: {counts[task_id]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
