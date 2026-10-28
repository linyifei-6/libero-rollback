"""Build the versioned catalog for all case collections in the working tree.

The source collections intentionally remain in place.  ``dataset/current`` is a
derived, reproducible catalog: it records every case path, source ID, original
case version, and digest without rewriting the case definitions.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CASE_COLLECTIONS = (
    ROOT / "dataset" / "two-subtask" / "cases",
    ROOT / "dataset" / "rollback-battery" / "cases",
    ROOT / "dataset" / "pose-control" / "cases",
    ROOT / "dataset" / "reference-object" / "cases",
    ROOT / "dataset" / "progress-failure" / "cases",
)
TASK_DEFINITIONS = (
    (
        0,
        "T0",
        "KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it.bddl",
        "Turn on the stove and put the moka pot on it",
    ),
    (
        1,
        "T33",
        "KITCHEN_SCENE4_put_the_black_bowl_in_the_bottom_drawer_of_the_cabinet_and_close_it.bddl",
        "Put the black bowl in the bottom drawer and close it",
    ),
    (
        2,
        "T78",
        "KITCHEN_SCENE6_put_the_yellow_and_white_mug_in_the_microwave_and_close_it.bddl",
        "Put the yellow and white mug in the microwave and close it",
    ),
    (
        3,
        "T133",
        "KITCHEN_SCENE8_put_both_moka_pots_on_the_stove.bddl",
        "Put both moka pots on the stove",
    ),
    (
        4,
        "T137",
        "LIVING_ROOM_SCENE1_put_both_the_alphabet_soup_and_the_cream_cheese_box_in_the_basket.bddl",
        "Put the alphabet soup and cream cheese box in the basket",
    ),
    (
        5,
        "T145",
        "LIVING_ROOM_SCENE2_put_both_the_alphabet_soup_and_the_tomato_sauce_in_the_basket.bddl",
        "Put the alphabet soup and tomato sauce in the basket",
    ),
    (
        6,
        "T158",
        "LIVING_ROOM_SCENE2_put_both_the_cream_cheese_box_and_the_butter_in_the_basket.bddl",
        "Put the cream cheese box and butter in the basket",
    ),
    (
        7,
        "T193",
        (
            "LIVING_ROOM_SCENE5_put_the_white_mug_on_the_left_plate_and_put_the_yellow_a"
            "nd_white_mug_on_the_right_plate.bddl"
        ),
        "Put the white mug on the left plate and the yellow and white mug on the right plate",
    ),
    (
        8,
        "T237",
        (
            "LIVING_ROOM_SCENE6_put_the_white_mug_on_the_plate_and_put_the_chocolate_pud"
            "ding_to_the_right_of_the_plate.bddl"
        ),
        "Put the white mug on the plate and the chocolate pudding to the right of the plate",
    ),
    (
        9,
        "T256",
        "STUDY_SCENE1_pick_up_the_book_and_place_it_in_the_back_compartment_of_the_caddy.bddl",
        "Pick up the book and place it in the back compartment of the caddy",
    ),
)

SOURCE_DESCRIPTIONS = {
    "articulation-position-grid-20261016": {
        "kind": "project_authored_scenario_collection",
        "description": (
            "Position grid for articulation setbacks: quarter- and three-quarter-range "
            "stove-knob setbacks around the calibrated half-range value; unreleased "
            "proposals require runtime validation."
        ),
        "location": "docs/libero-10用例整改与扩充.md",
    },
    "progress-failure-expansion-20261014": {
        "kind": "project_authored_scenario_collection",
        "description": (
            "Native boundary pairs, completed-pose probes, temporal and atomic native "
            "relation-set protocols; unreleased proposals require runtime validation."
        ),
        "location": "docs/expansion-plan.md",
    },
    "libero-plus-task-definitions-v1": {
        "kind": "task_definition",
        "description": "LIBERO-plus LIBERO-10 tasks_info.txt and corresponding BDDL files.",
        "location": "../libero-plus/LIBERO-plus/libero/libero/bddl_files/libero_10/tasks_info.txt",
    },
    "full-suite-runtime-crosswalk-20261009": {
        "kind": "runtime_crosswalk",
        "description": (
            "Persistent snapshots of the local evaluator profiles. Canonical LIBERO-10 "
            "identities and installed BDDL variants are distinct; T256 uses runtime T276."
        ),
        "location": "dataset/runtime-profiles",
        "origin": "runs/full-coverage/runtime/configs/task_profiles",
    },
    "two-subtask-expansion-20261012": {
        "kind": "scenario_collection",
        "description": "Two-subtask rollback expansion collection retained as individual cases.",
        "location": "dataset/two-subtask/cases",
    },
    "rollback-battery-20261012": {
        "kind": "scenario_collection",
        "description": "Rollback battery collection covering timing and perturbation grids.",
        "location": "dataset/rollback-battery/cases",
    },
    "runtime-grid-expansion-20261009": {
        "kind": "scenario_collection",
        "description": "Runtime grid expansion cases produced during task profile validation.",
        "location": "dataset/two-subtask/cases",
    },
    "runtime-grid-expansion-20261010": {
        "kind": "scenario_collection",
        "description": "Runtime grid expansion cases for the living-room task variants.",
        "location": "dataset/two-subtask/cases",
    },
    "runtime-validated-above-20261012": {
        "kind": "scenario_collection",
        "description": (
            "Container-above cases retained with their separate physical-validation provenance."
        ),
        "location": "dataset/two-subtask/cases",
    },
    "matrix-p2-pose-20261013": {
        "kind": "scenario_collection",
        "description": "Pose perturbation cases from the P2 matrix extension.",
        "location": "dataset/pose-control/cases",
    },
    "matrix-p2-reference-object-20261013": {
        "kind": "scenario_collection",
        "description": "Reference-object perturbation cases from the P2 matrix extension.",
        "location": "dataset/reference-object/cases",
    },
    "scenario-timing-position-matrix-20260926": {
        "kind": "design_guidance",
        "description": "Timing-window and signed-position guidance used by scenario definitions.",
        "location": (
            "../libero-plus/libero-"
            "runtime/docs/PFCR_ROLLBACK_BENCHMARK_CASE_MATRIX_V2_GRID_20260926.md"
        ),
    },
    "scenario-validity-severity-guidance-20260922": {
        "kind": "design_guidance",
        "description": "Validity and perturbation-label guidance used by scenario definitions.",
        "location": "../libero-plus/libero-runtime/docs/PFCR_ROLLBACK_BENCHMARK_PLAN_20260922.md",
    },
}


def _write_yaml(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _case_files() -> list[tuple[Path, dict]]:
    rows: list[tuple[Path, dict]] = []
    for collection in CASE_COLLECTIONS:
        for path in sorted(collection.glob("*.yaml")):
            case = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(case, dict):
                raise ValueError(f"case is not a mapping: {path}")
            rows.append((path, case))
    return rows


def _build_sources(rows: list[tuple[Path, dict]]) -> dict:
    used: set[str] = {"libero-plus-task-definitions-v1"}
    for _, case in rows:
        source = case.get("source", {})
        if isinstance(source, dict):
            for key in ("case_source_id", "task_source_id", "task_locator_source_id"):
                if isinstance(source.get(key), str):
                    used.add(source[key])
            for source_id in source.get("supporting_source_ids", []):
                if isinstance(source_id, str):
                    used.add(source_id)
    sources = {}
    for source_id in sorted(used):
        sources[source_id] = SOURCE_DESCRIPTIONS.get(
            source_id,
            {
                "kind": "referenced_source",
                "description": "Referenced by one or more case definitions.",
            },
        )
    return {"sources_version": "1", "sources": sources}


def _build_templates(rows: list[tuple[Path, dict]]) -> dict:
    by_template: dict[str, list[dict]] = defaultdict(list)
    for _, case in rows:
        by_template[case["template_id"]].append(case)
    templates = []
    for template_id in sorted(by_template):
        cases = by_template[template_id]
        kinds = sorted({c["rollback_target"]["state_change"]["kind"] for c in cases})
        common = set(cases[0].get("validity_constraints", []))
        for case in cases[1:]:
            common.intersection_update(case.get("validity_constraints", []))
        row = {
            "template_id": template_id,
            "description": {
                "completed-relation-rollback/articulation-goal/v1": (
                    "Revoke a completed articulation or functional goal."
                ),
                "completed-relation-rollback/container-above/v1": (
                    "Move a released object to a legal pose above its container."
                ),
                "completed-relation-rollback/episode-initial-pose/v1": (
                    "Restore the released object to its episode initial pose."
                ),
                "completed-relation-rollback/reference-object/v1": (
                    "Move a relation reference object or relation pair."
                ),
                "completed-relation-rollback/support-surface-offset/v1": (
                    "Apply a signed offset relative to the episode initial pose."
                ),
                "completed-relation-rollback/native-relation-set/v1": (
                    "Atomically reset one or two verified native goals at completion."
                ),
                "completed-relation-rollback/temporal/v1": (
                    "External timed restoration or revocation gated by native recovery."
                ),
                "completed-relation-rollback/completed-pose/v1": (
                    "Rotate the completed pose and measure native predicate truth."
                ),
                "completed-relation-rollback/native-boundary/v1": (
                    "Search adjacent legal native-predicate inside/outside poses."
                ),
                "completed-relation-rollback/functional-boundary/v1": (
                    "Actuate to either side of the installed native functional threshold."
                ),
            }.get(template_id, "Reusable rollback scenario template."),
            "state_change_kinds": kinds,
            "required_validity_constraints": sorted(common),
            "source_ids": sorted(
                {
                    c.get("source", {}).get("case_source_id")
                    for c in cases
                    if isinstance(c.get("source"), dict)
                    and isinstance(c["source"].get("case_source_id"), str)
                }
            ),
        }
        templates.append(row)
    return {"templates_version": "1", "templates": templates}


def _build_coverage(rows: list[tuple[Path, dict]]) -> dict:
    by_task: dict[int, list[tuple[Path, dict]]] = defaultdict(list)
    for path, case in rows:
        by_task[case["task"]["task_index"]].append((path, case))
    task_rows = []
    for index, locator, canonical_bddl, name in TASK_DEFINITIONS:
        group = by_task.get(index, [])
        runtime_locator = "T276" if index == 9 else locator
        profile_path = ROOT / f"dataset/runtime-profiles/libero_10_t{runtime_locator[1:]}.yaml"
        profile = yaml.safe_load(profile_path.read_text())["task_profile"]
        runtime_bddl = profile["bddl_name"] + ".bddl"
        allowed_bddls = {canonical_bddl, runtime_bddl}
        for _, case in group:
            if case["task"]["source_bddl"] not in allowed_bddls:
                raise ValueError(f"unverified BDDL name in {case['case_id']}")
        events = sorted({c["trigger"]["event"] for _, c in group})
        mechanisms = sorted({c["rollback_target"]["state_change"]["kind"] for _, c in group})
        task_rows.append(
            {
                "task_id": f"libero_10/{index:02d}",
                "task_index": index,
                "task_name": name,
                "source_task_locator": locator,
                "source_bddl": canonical_bddl,
                "canonical_bddl": canonical_bddl,
                "runtime_task_locator": runtime_locator,
                "runtime_bddl": runtime_bddl,
                "allowed_source_bddls": sorted(allowed_bddls),
                "crosswalk_source_id": "full-suite-runtime-crosswalk-20261009",
                "runtime_profile_sha256": _sha256(profile_path),
                "scenario_applicability": (
                    "candidate" if index == 9 else "documented" if group else "requires_research"
                ),
                "candidate_rollback_events": events,
                "candidate_state_change_kinds": mechanisms,
                "case_count": len(group),
                "case_ids": sorted(c["case_id"] for _, c in group),
                "open_questions": (
                    sorted(
                        {
                            question
                            for _, case in group
                            for question in case.get("open_questions", [])
                        }
                    )
                    if group
                    else [
                        "No runnable rollback case is established for this task in current catalog."
                    ]
                ),
            }
        )
    return {
        "coverage_version": "1",
        "suite": "LIBERO-10",
        "task_source": "libero-plus-task-definitions-v1",
        "tasks": task_rows,
    }


def build() -> Path:
    rows = _case_files()
    if not rows:
        raise ValueError("no case files found")
    current = ROOT / "dataset" / "current"
    current.mkdir(parents=True, exist_ok=True)
    sources = _build_sources(rows)
    templates = _build_templates(rows)
    coverage = _build_coverage(rows)
    _write_yaml(current / "sources.yaml", sources)
    _write_yaml(current / "templates.yaml", templates)
    _write_yaml(current / "coverage.yaml", coverage)

    file_rows = [
        {"path": "schemas/rollback-case.v1.schema.json", "role": "schema"},
        {"path": "dataset/current/coverage.yaml", "role": "coverage"},
        {"path": "dataset/current/sources.yaml", "role": "sources"},
        {"path": "dataset/current/templates.yaml", "role": "templates"},
    ]
    file_rows.extend(
        {"path": p.relative_to(ROOT).as_posix(), "role": "runtime_profile"}
        for p in sorted((ROOT / "dataset/runtime-profiles").glob("*.yaml"))
    )
    case_entries = []
    for path, case in sorted(rows, key=lambda item: item[1]["case_id"]):
        relative = path.relative_to(ROOT).as_posix()
        case_entries.append(
            {
                "case_id": case["case_id"],
                "path": relative,
                "dataset_version": case["dataset_version"],
                "source_id": case["source"]["case_source_id"],
            }
        )
        file_rows.append({"path": relative, "role": "case"})
    for entry in file_rows:
        entry["sha256"] = _sha256(ROOT / entry["path"])
    manifest = {
        "manifest_version": 1,
        "dataset_name": "libero-rollback",
        "dataset_version": "1.0.0",
        "case_version_policy": "preserve",
        "schema_version": "libero-rollback.case.v1",
        "schema_file": "schemas/rollback-case.v1.schema.json",
        "coverage_file": "dataset/current/coverage.yaml",
        "sources_file": "dataset/current/sources.yaml",
        "templates_file": "dataset/current/templates.yaml",
        "case_count": len(case_entries),
        "definition_status": {
            "preserved_collection_count": sum(
                case["source"]["case_source_id"] != "progress-failure-expansion-20261014"
                for _, case in rows
            ),
            "unreleased_candidate_count": sum(
                case["source"]["case_source_id"] == "progress-failure-expansion-20261014"
                for _, case in rows
            ),
            "physical_acceptance": "recorded_separately_in_external_evidence",
        },
        "cases": case_entries,
        "files": file_rows,
    }
    _write_yaml(current / "manifest.yaml", manifest)
    # Add the manifest itself after it is written; it is deliberately not self-hashed.
    return current / "manifest.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    path = build()
    print(f"wrote {path}")
    print(f"cases: {len(_case_files())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
