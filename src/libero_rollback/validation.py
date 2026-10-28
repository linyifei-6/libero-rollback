"""Schema and static consistency checks for dataset documents."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


class DatasetError(ValueError):
    """Raised when a dataset document is invalid or internally inconsistent."""


def load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DatasetError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise DatasetError(f"invalid YAML in {path}: {exc}") from exc


def schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / "rollback-case.v1.schema.json"


def validate_case_data(case: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Return schema validation errors for a parsed case mapping."""
    if schema is None:
        schema = json.loads(schema_path().read_text(encoding="utf-8"))
    try:
        validator = Draft202012Validator(schema)
    except SchemaError as exc:
        return [f"schema is not valid JSON Schema: {exc.message}"]
    errors = sorted(
        validator.iter_errors(case),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    messages = [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in errors
    ]
    if not messages and isinstance(case, dict):
        change = case["rollback_target"]["state_change"]
        if change["kind"] == "restore_native_relation_set":
            if case["trigger"].get("time_point") != "all_done":
                messages.append("native relation sets require the completion boundary")
            relations = change["relations"]
            identities = [tuple(r["predicate"]) for r in relations]
            if len(set(identities)) != len(identities):
                messages.append("native relation sets cannot repeat a predicate")
            actors = [r["actor_role"] for r in relations]
            if len(set(actors)) != len(actors):
                messages.append("native relation sets cannot write the same actor twice")
            declared = {r.get("predicate", "").lower() for r in case["completed_relations"]}
            if any("(" + " ".join(r["predicate"]).lower() + ")" not in declared for r in relations):
                messages.append(
                    "native relation set predicates must be declared completed relations"
                )
            if case.get("transient"):
                messages.append("native relation sets do not support temporal second writes")
    return messages


def validate_case_file(path: Path) -> list[str]:
    try:
        case = load_yaml(path)
        errors = validate_case_data(case)
    except (DatasetError, OSError, json.JSONDecodeError) as exc:
        return [str(exc)]
    return errors


def _manifest_context(dataset_root: Path) -> tuple[dict[str, Any], Path]:
    manifest_path = dataset_root / "manifest.yaml"
    manifest = load_yaml(manifest_path)
    if not isinstance(manifest, dict):
        raise DatasetError(f"{manifest_path} must contain a mapping")
    repo_root = dataset_root.resolve().parents[1]
    return manifest, repo_root


def check_manifest(dataset_root: Path) -> list[str]:
    """Check manifest file references, safe relative paths, and SHA-256 digests."""
    try:
        manifest, repo_root = _manifest_context(dataset_root)
    except DatasetError as exc:
        return [str(exc)]

    errors: list[str] = []
    version_policy = manifest.get("case_version_policy", "uniform")
    if version_policy not in {"uniform", "preserve"}:
        errors.append(f"unknown case_version_policy: {version_policy!r}")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        return ["manifest.files must be a list"]
    case_references = manifest.get("cases", [])
    if not isinstance(case_references, list):
        errors.append("manifest.cases must be a list")
        case_references = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            errors.append("each manifest.files entry must contain a path")
            continue
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"unsafe manifest path: {entry['path']}")
            continue
        if entry["path"] in seen:
            errors.append(f"duplicate manifest path: {entry['path']}")
            continue
        seen.add(entry["path"])
        target = repo_root / relative
        if not target.is_file():
            errors.append(f"manifest file is missing: {entry['path']}")
            continue
        expected = entry.get("sha256")
        if (
            not isinstance(expected, str)
            or len(expected) != 64
            or any(character not in "0123456789abcdef" for character in expected)
        ):
            errors.append(f"manifest SHA-256 is missing or malformed: {entry['path']}")
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != expected:
            errors.append(
                f"SHA-256 mismatch for {entry['path']}: expected {expected}, got {actual}"
            )

    required_references = [
        manifest.get("schema_file"),
        manifest.get("coverage_file"),
        manifest.get("sources_file"),
        manifest.get("templates_file"),
    ]
    required_references.extend(
        entry.get("path") for entry in case_references if isinstance(entry, dict)
    )
    for reference in required_references:
        if reference not in seen:
            errors.append(f"manifest reference is not included in files: {reference}")
    return errors


def validate_dataset(dataset_root: Path) -> list[str]:
    """Validate case schemas and cross-file IDs, source references, and task coverage counts."""
    try:
        manifest, repo_root = _manifest_context(dataset_root)
        schema_file = repo_root / manifest["schema_file"]
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
        coverage = load_yaml(repo_root / manifest["coverage_file"])
        sources_doc = load_yaml(repo_root / manifest["sources_file"])
        templates_doc = load_yaml(repo_root / manifest["templates_file"])
    except (DatasetError, KeyError, OSError, json.JSONDecodeError) as exc:
        return [f"cannot load dataset metadata: {exc}"]

    errors: list[str] = []
    sources = sources_doc.get("sources", {}) if isinstance(sources_doc, dict) else {}
    template_rows = templates_doc.get("templates", []) if isinstance(templates_doc, dict) else []
    if not isinstance(template_rows, list):
        return ["templates.templates must be a list"]
    templates: dict[str, dict[str, Any]] = {}
    for template in template_rows:
        if not isinstance(template, dict) or not isinstance(template.get("template_id"), str):
            errors.append("each template must contain a string template_id")
            continue
        template_id = template["template_id"]
        if template_id in templates:
            errors.append(f"duplicate template_id: {template_id}")
        templates[template_id] = template
        for source_id in template.get("source_ids", []):
            if not isinstance(source_id, str) or source_id not in sources:
                errors.append(f"unknown template source_id {source_id!r} in {template_id}")
    task_rows = coverage.get("tasks", []) if isinstance(coverage, dict) else []
    if not isinstance(task_rows, list):
        return ["coverage.tasks must be a list"]
    tasks: dict[str, dict[str, Any]] = {}
    task_indexes: list[int] = []
    for row in task_rows:
        if not isinstance(row, dict):
            errors.append("each coverage task must be a mapping")
            continue
        task_id = row.get("task_id")
        if not isinstance(task_id, str):
            errors.append("each coverage task must have a string task_id")
            continue
        if task_id in tasks:
            errors.append(f"duplicate coverage task_id: {task_id}")
        tasks[task_id] = row
        task_index = row.get("task_index")
        if isinstance(task_index, int) and not isinstance(task_index, bool):
            task_indexes.append(task_index)
            expected_task_id = f"libero_10/{task_index:02d}"
            if task_id != expected_task_id:
                errors.append(f"task_id must be {expected_task_id} for task_index {task_index}")
        else:
            errors.append(f"task_index must be an integer for {task_id}")
        if row.get("scenario_applicability") not in {
            "documented",
            "candidate",
            "requires_research",
        }:
            errors.append(f"invalid scenario_applicability for {task_id}")
        if not isinstance(row.get("candidate_rollback_events"), list):
            errors.append(f"candidate_rollback_events must be a list for {task_id}")
    actual_cases: dict[str, list[str]] = {task_id: [] for task_id in tasks}
    seen_case_ids: set[str] = set()
    case_entries = manifest.get("cases", [])
    if not isinstance(case_entries, list):
        return ["manifest.cases must be a list"]
    if manifest.get("case_count") != len(case_entries):
        errors.append("manifest.case_count does not match case references")

    for entry in case_entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            errors.append("each manifest.cases entry must contain a path")
            continue
        relative_path = Path(entry["path"])
        if relative_path.is_absolute() or ".." in relative_path.parts:
            errors.append(f"unsafe case path in manifest: {entry['path']}")
            continue
        path = repo_root / relative_path
        try:
            case = load_yaml(path)
        except DatasetError as exc:
            errors.append(str(exc))
            continue
        errors.extend(f"{path}: {error}" for error in validate_case_data(case, schema))
        if not isinstance(case, dict):
            continue
        case_id = case.get("case_id")
        task_data = case.get("task", {})
        task_id = task_data.get("task_id") if isinstance(task_data, dict) else None
        if isinstance(case_id, str):
            if case_id in seen_case_ids:
                errors.append(f"duplicate case_id: {case_id}")
            seen_case_ids.add(case_id)
        if case_id != entry.get("case_id"):
            errors.append(
                f"manifest case ID mismatch for {entry['path']}: "
                f"{entry.get('case_id')} != {case_id}"
            )
        case_version = case.get("dataset_version")
        if (
            not isinstance(case_version, str)
            or re.fullmatch(r"\d+\.\d+\.\d+", case_version) is None
        ):
            errors.append(f"invalid dataset version in {case_id}")
        if manifest.get("case_version_policy", "uniform") == "uniform" and (
            case_version != manifest.get("dataset_version")
        ):
            errors.append(f"dataset version mismatch in {case_id}")
        if entry.get("dataset_version", case_version) != case_version:
            errors.append(f"manifest case version mismatch in {case_id}")
        template_id = case.get("template_id")
        template = templates.get(template_id) if isinstance(template_id, str) else None
        if template is None:
            errors.append(f"unknown template_id {template_id!r} in {case_id}")
        else:
            rollback_data = case.get("rollback_target")
            state_change = (
                rollback_data.get("state_change", {}) if isinstance(rollback_data, dict) else {}
            )
            allowed_kinds = template.get("state_change_kinds", [template.get("state_change_kind")])
            if isinstance(state_change, dict) and state_change.get("kind") not in allowed_kinds:
                errors.append(f"state change does not match template {template_id} in {case_id}")
            required_values = template.get("required_validity_constraints", [])
            case_values = case.get("validity_constraints", [])
            required_constraints = (
                set(required_values) if isinstance(required_values, list) else set()
            )
            case_constraints = set(case_values) if isinstance(case_values, list) else set()
            if not required_constraints.issubset(case_constraints):
                missing = sorted(required_constraints - case_constraints)
                errors.append(f"template constraints missing in {case_id}: {missing}")
        rollback_target = case.get("rollback_target")
        completed_relations = case.get("completed_relations")
        if isinstance(rollback_target, dict) and isinstance(completed_relations, list):
            if isinstance(rollback_target.get("predicate"), str):
                completed_predicates = [
                    relation.get("predicate")
                    for relation in completed_relations
                    if isinstance(relation, dict) and isinstance(relation.get("predicate"), str)
                ]
                if rollback_target["predicate"] not in completed_predicates:
                    errors.append(f"rollback target is not listed as completed in {case_id}")
            elif isinstance(rollback_target.get("goal_id"), str):
                goal_ids = [
                    relation.get("goal_id")
                    for relation in completed_relations
                    if isinstance(relation, dict)
                ]
                if rollback_target["goal_id"] not in goal_ids:
                    errors.append(f"rollback goal is not declared as completed in {case_id}")
            else:
                selection_ids = [
                    relation.get("selection_id")
                    for relation in completed_relations
                    if isinstance(relation, dict)
                ]
                if rollback_target.get("selection_id") not in selection_ids:
                    errors.append(f"rollback selection is not declared as completed in {case_id}")
        if not isinstance(task_id, str) or task_id not in tasks:
            errors.append(f"unknown task_id {task_id!r} in {case_id}")
        else:
            if isinstance(case_id, str):
                actual_cases[task_id].append(case_id)
            task_row = tasks[task_id]
            if task_data.get("task_index") != task_row.get("task_index"):
                errors.append(f"task_index mismatch for {case_id}")
            allowed_bddls = task_row.get("allowed_source_bddls", [task_row.get("source_bddl")])
            if task_data.get("source_bddl") not in allowed_bddls:
                errors.append(f"source_bddl mismatch for {case_id}")
        source = case.get("source", {})
        for source_key in ("case_source_id", "task_source_id", "task_locator_source_id"):
            source_id = source.get(source_key) if isinstance(source, dict) else None
            if not isinstance(source_id, str) or source_id not in sources:
                errors.append(f"unknown {source_key} {source_id!r} in {case_id}")
        supporting_source_ids = (
            source.get("supporting_source_ids", []) if isinstance(source, dict) else []
        )
        if not isinstance(supporting_source_ids, list):
            errors.append(f"supporting_source_ids must be a list in {case_id}")
        else:
            for source_id in supporting_source_ids:
                if not isinstance(source_id, str) or source_id not in sources:
                    errors.append(f"unknown supporting source_id {source_id!r} in {case_id}")
        if entry.get("source_id") != source.get("case_source_id"):
            errors.append(f"manifest source ID mismatch for {case_id}")

    for task_id, row in tasks.items():
        case_ids = row.get("case_ids", [])
        if not isinstance(case_ids, list) or any(
            not isinstance(case_id, str) for case_id in case_ids
        ):
            errors.append(f"case_ids must be a list of strings for {task_id}")
            case_ids = []
        actual = sorted(actual_cases[task_id])
        case_count = row.get("case_count")
        if not isinstance(case_count, int) or isinstance(case_count, bool):
            errors.append(f"case_count must be an integer for {task_id}")
        elif case_count != len(actual):
            errors.append(
                f"coverage case_count mismatch for {task_id}: {case_count} != {len(actual)}"
            )
        if sorted(case_ids) != actual:
            errors.append(f"coverage case_ids mismatch for {task_id}: {case_ids} != {actual}")
    if len(tasks) != 10:
        errors.append(f"coverage must contain all 10 LIBERO-10 tasks, found {len(tasks)}")
    if len(task_indexes) == len(tasks) and sorted(task_indexes) != list(range(10)):
        errors.append("coverage task_index values must be exactly 0 through 9")
    return errors
