"""Materialize the full-suite release and an isolated external runtime overlay."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUS = ROOT.parent / "libero-plus"
RELEASE = ROOT / "dataset" / "v1.1"
OVERLAY = ROOT / "runs" / "full-coverage" / "runtime"
TASKS = {
    0: (0, "moka-pot-stove"),
    4: (137, "soup-cheese-basket"),
    5: (145, "soup-sauce-basket"),
    6: (158, "cheese-butter-basket"),
    8: (237, "mug-pudding-placement"),
    9: (276, "book-caddy"),
}
SOURCE = "dataset-full-suite-design-20261009"


def write_yaml(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def main() -> None:
    if RELEASE.exists():
        prepare_runtime(yaml.safe_load((RELEASE / "coverage.yaml").read_text()))
        return
    shutil.copytree(ROOT / "dataset/v1", RELEASE)
    coverage = yaml.safe_load((RELEASE / "coverage.yaml").read_text())
    source = yaml.safe_load((RELEASE / "sources.yaml").read_text())
    source["sources"][SOURCE] = {
        "title": "Full-suite rollback definitions authored for libero-rollback",
        "path": "docs/full-suite-design.md",
        "use": (
            "Project-authored definitions for six formerly uncovered tasks; "
            "numeric offsets are design choices, not inherited task evidence."
        ),
        "semantic_group": "project_authored_full_suite_cases",
    }
    source["sources"]["full-suite-runtime-crosswalk-20261009"] = {
        "title": "Local LIBERO-plus task configuration crosswalk",
        "repository": "https://github.com/linyifei-6/libero-runtime",
        "paths": ["configs/tasks/libero_10/", "libero_runtime/engine/context.py"],
        "use": (
            "Runtime indices checked against task names and benchmark map; "
            "generated variants are recorded separately in run manifests."
        ),
    }
    write_yaml(RELEASE / "sources.yaml", source)
    for path in (RELEASE / "cases").glob("*.yaml"):
        case = yaml.safe_load(path.read_text())
        case["dataset_version"] = "1.1.0"
        write_yaml(path, case)
    levels = {
        "d0": "d0-early",
        "d1": "d1-early",
        "d2": "d2-early",
        "d3": "d3-early",
        "checkpoint": "checkpoint-pregrasp-early",
    }
    for index, (locator, slug) in TASKS.items():
        row = coverage["tasks"][index]
        relations = [r for r in row["goal_relations"] if r.startswith(("(In ", "(On "))]
        for level, suffix in levels.items():
            case = yaml.safe_load(
                (
                    ROOT / "dataset/v1/cases" / f"libero-10-01-black-bowl-drawer-close-after-s06{suffix}.yaml"
                ).read_text()
            )
            case["dataset_version"] = "1.1.0"
            case["case_id"] = f"libero-10-{index:02d}-{slug}-{suffix}"
            case["source"] = {
                "case_source_id": SOURCE,
                "task_source_id": "libero-plus-task-definitions-v1",
                "task_locator_source_id": "full-suite-runtime-crosswalk-20261009",
                "case_reference": f"Full-suite design / task {index:02d} / {level}",
            }
            case["task"] = {
                "suite": "LIBERO-10",
                "task_id": row["task_id"],
                "task_index": index,
                "source_bddl": row["source_bddl"],
                "source_task_locator": f"T{locator}",
            }
            state = case["rollback_target"]["state_change"]
            if len(relations) > 1:
                case["completed_relations"] = [
                    {
                        "selection_id": "first-completed-placement",
                        "selection_strategy": "first_completed_subgoal_in_execution_order",
                        "candidates": [
                            {"predicate": rel, "actor": rel.split()[1], "source_task_goal": True}
                            for rel in relations
                        ],
                    }
                ]
                case["rollback_target"] = {
                    "selection_id": "first-completed-placement",
                    "actor": "selected_relation_actor",
                    "state_change": state,
                }
            else:
                case["completed_relations"] = [
                    {"predicate": relations[0], "source_task_goal": True}
                ]
                case["rollback_target"] = {
                    "predicate": relations[0],
                    "actor": relations[0].split()[1],
                    "state_change": state,
                }
            window = (
                (
                    "Placement is complete and released; revoke it and continue under an "
                    "explicit post-success observation window."
                )
                if index in (0, 9)
                else (
                    "First placement is complete and released; "
                    "the other placement remains to be completed."
                )
            )
            case["stage"] = {
                "name": "completion_boundary" if index in (0, 9) else "first_completed_subgoal",
                "description": window,
            }
            case["trigger"] = {
                "event": "enter_first_subgoal_completed",
                "window": window,
                "delay_steps": 0,
            }
            case["intervention_description"] = (
                f"Revoke the selected completed placement using {level}; retain the "
                f"instruction and unrelated scene state."
            )
            case["assumptions"] = [
                (
                    "Project-authored extension: the offset vectors are proposed design "
                    "parameters and require episode-specific physical preflight."
                ),
                (
                    "The selected placement must be true and the affected object released "
                    "before state mutation."
                ),
                (
                    "The historical runtime locator may use a generated scene variant; its "
                    "actual BDDL must be recorded in the run evidence."
                ),
            ]
            if index in (0, 9):
                case["assumptions"].append(
                    "Enable the explicit post-success observation protocol; this boundary "
                    "scenario is reported separately from nonterminal multi-placement "
                    "rollback."
                )
            case["open_questions"] = [
                (
                    "Verify collision-free support, no penetration, release, and task "
                    "solvability for the selected episode."
                )
            ]
            case["severity_rationale"] = (
                "Project-defined transformation label; the concrete reference pose and "
                "signed offset, if any, are recorded in state_change. No claim of "
                "comparable model difficulty."
            )
            write_yaml(RELEASE / "cases" / (case["case_id"] + ".yaml"), case)
        row["case_ids"] = [f"libero-10-{index:02d}-{slug}-{suffix}" for suffix in levels.values()]
        row["case_count"] = 5
        row["scenario_applicability"] = "documented"
        row["open_questions"] = [
            (
                "Project-authored cases require independent physical validity evidence; "
                "completion-boundary cases use an explicit continuation protocol."
            )
        ]
    write_yaml(RELEASE / "coverage.yaml", coverage)
    manifest = yaml.safe_load((RELEASE / "manifest.yaml").read_text())
    manifest["dataset_version"] = "1.1.0"
    manifest["release_status"] = "candidate"
    manifest["cases"] = []
    for path in sorted((RELEASE / "cases").glob("*.yaml")):
        case = yaml.safe_load(path.read_text())
        manifest["cases"].append(
            {
                "case_id": case["case_id"],
                "path": str(path.relative_to(ROOT)),
                "source_id": case["source"]["case_source_id"],
            }
        )
    for key in ("coverage_file", "sources_file", "templates_file"):
        manifest[key] = manifest[key].replace("dataset/v1/", "dataset/v1.1/")
    manifest["files"] = [entry for entry in manifest["files"] if entry["role"] != "case"]
    for entry in manifest["files"]:
        entry["path"] = entry["path"].replace("dataset/v1/", "dataset/v1.1/")
    manifest["files"] += [{"path": entry["path"], "role": "case"} for entry in manifest["cases"]]
    manifest["files"].append({"path": "docs/full-suite-design.md", "role": "scenario-design"})
    for entry in manifest["files"]:
        entry["sha256"] = hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest()
    write_yaml(RELEASE / "manifest.yaml", manifest)
    prepare_runtime(coverage)


def prepare_runtime(coverage: dict) -> None:
    # Use a disposable overlay; never edit the sibling runtime checkout.
    runtime = PLUS / "libero-runtime"
    OVERLAY.mkdir(parents=True, exist_ok=True)
    shutil.copytree(runtime / "configs", OVERLAY / "configs", dirs_exist_ok=True)
    (OVERLAY / "tools").mkdir(exist_ok=True)
    for path in (runtime / "tools").iterdir():
        destination = OVERLAY / "tools" / path.name
        if path.name == "run_benchmark.py":
            shutil.copy2(path, destination)
        elif not destination.exists():
            destination.symlink_to(path.resolve(), target_is_directory=path.is_dir())
    for folder in ("libero_runtime",):
        destination = OVERLAY / folder
        if not destination.exists():
            destination.symlink_to((runtime / folder).resolve(), target_is_directory=True)
    profile = yaml.safe_load((runtime / "configs/task_profiles/libero_10_t133.yaml").read_text())[
        "task_profile"
    ]
    task_map = ast.literal_eval(
        ast.parse(
            (PLUS / "LIBERO-plus/libero/libero/benchmark/libero_suite_task_map.py").read_text()
        )
        .body[0]
        .value
    )["libero_10"]
    for index, (locator, slug) in TASKS.items():
        row = coverage["tasks"][index]
        assert task_map[locator].startswith(Path(row["source_bddl"]).stem)
        relations = [r for r in row["goal_relations"] if r.startswith(("(In ", "(On "))]
        current = copy.deepcopy(profile)
        current.update(id=f"libero_10_t{locator}", task_idx=locator, bddl_name=task_map[locator])
        current["subgoals"] = []
        for n, relation in enumerate(relations):
            predicate, actor, goal = relation.strip("()").split()
            goal_body = (
                "flat_stove_1"
                if goal.startswith("flat_stove_1")
                else "desk_caddy_1"
                if goal.startswith("desk_caddy_1")
                else "living_room_table"
                if goal.startswith("living_room_table")
                else goal.split("_contain_region")[0]
                if "_contain_region" in goal
                else goal
            )
            role = f"subgoal_object_{n}"
            goal_role = f"subgoal_goal_{n}"
            current["roles"][role] = {"kind": "body", "name": actor}
            current["roles"][goal_role] = {"kind": "body", "name": goal_body}
            current["subgoals"].append(
                {
                    "id": f"{actor}_placement",
                    "predicate": predicate.lower(),
                    "actor_role": role,
                    "goal_role": goal_role,
                    "goal_state_name": goal,
                }
            )
        actor = relations[0].split()[1]
        first_goal_role = current["subgoals"][0]["goal_role"]
        for role in ("manipulated_object", "subgoal_object_a", "completed_subgoal_object"):
            current["roles"][role] = {"kind": "body", "name": actor}
        for role in ("goal_object", "subgoal_goal_a", "completed_subgoal_goal"):
            current["roles"][role] = dict(current["roles"][first_goal_role])
        other = relations[-1].split()[1]
        for role in ("subgoal_object_b", "next_subgoal_object"):
            current["roles"][role] = {"kind": "body", "name": other}
        for role in ("subgoal_goal_b", "next_subgoal_goal"):
            current["roles"][role] = dict(current["roles"][current["subgoals"][-1]["goal_role"]])
        current["manipulated_object_candidates"] = [s["actor_role"] for s in current["subgoals"]]
        if len(current["subgoals"]) == 1:
            current.pop("manipulated_object_candidates", None)
        write_yaml(
            OVERLAY / f"configs/task_profiles/libero_10_t{locator}.yaml", {"task_profile": current}
        )
    (OVERLAY / "preparation.json").write_text(
        json.dumps(
            {
                "dataset": "1.1.0",
                "external_runtime": str(runtime),
                "task_map": {
                    str(index): {"runtime_index": locator, "actual_bddl": task_map[locator]}
                    for index, (locator, _) in TASKS.items()
                },
            },
            indent=2,
        )
    )
    print(f"Prepared 50 cases: {RELEASE}\nIsolated runtime: {OVERLAY}")


if __name__ == "__main__":
    main()
