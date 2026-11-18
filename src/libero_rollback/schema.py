"""JSON Schema and metadata validation for dataset documents.

This module is part of the static contract layer: it only depends on the
standard library and ``jsonschema`` so it can run on a CPU-only machine
(``docs/SPEC.md`` §11-§12).

Two document families are validated here:

* **case definitions** (``schema_version: libero-rollback.case.v1``), the
  versioned rollback-scenario contract copied from the precursor data
  repository (``schemas/rollback-case.v1.schema.json``);
* **composition metadata rows** (one JSON object per line of a future
  ``dataset/compose/metadata.jsonl``), the minimal frozen contract a C-suite
  structure must satisfy: a structure id, its source task slots, the ordered
  goal atoms, the instruction and a sibling init reference.

Matrix CSVs (``dataset/matrices/*.csv``) are validated by
:mod:`libero_rollback.matrices` and :mod:`libero_rollback.validation`; the
``$id`` of the copied schema is left untouched so the migrated contract stays
byte-comparable with the released v1 schema.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

SCHEMA_FILENAME = "rollback-case.v1.schema.json"
SCHEMA_ID = "urn:libero-rollback:schema:case:v1"
METADATA_SCHEMA_VERSION = "libero-rollback.compose-metadata.v1"

COMPOSE_SUITES = frozenset({"goal", "object", "spatial", "l10"})
_INIT_SOURCE_RE = (
    r"^libero/libero/init_files/(?:libero_goal|libero_object|libero_spatial|libero_10)"
    r"/[A-Za-z0-9_]+\.pruned_init$"
)
_PREDICATE_RE = r"^\([^()]+\)$"
_STRUCT_ID_RE = r"^s[0-9]{4}$"


def repo_root() -> Path:
    """Return the repository root that contains ``schemas/``."""

    return Path(__file__).resolve().parents[2]


def schemas_dir() -> Path:
    return repo_root() / "schemas"


def schema_path(name: str = SCHEMA_FILENAME) -> Path:
    """Resolve a schema file name (absolute paths pass through)."""

    candidate = Path(name)
    return candidate if candidate.is_absolute() else schemas_dir() / name


def load_schema(name: str = SCHEMA_FILENAME) -> dict[str, Any]:
    """Load and parse a JSON Schema document from ``schemas/``."""

    path = schema_path(name)
    if not path.is_file():
        raise FileNotFoundError(f"schema file not found: {path}")
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"schema is not valid JSON ({path}): {error}") from error
    if not isinstance(schema, dict):
        raise ValueError(f"schema must be a JSON object: {path}")
    return schema


@lru_cache(maxsize=4)
def _cached_schema(name: str = SCHEMA_FILENAME) -> Mapping[str, Any]:
    """Cached, read-only view of a schema document (never mutate it)."""

    return load_schema(name)


def _format_errors(validator: Draft202012Validator, document: Any) -> list[str]:
    errors = sorted(
        validator.iter_errors(document),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in errors
    ]


def _case_semantic_errors(case: Mapping[str, Any]) -> list[str]:
    """Contract rules the JSON Schema cannot express (migrated v1 semantics)."""

    messages: list[str] = []
    rollback_target = case.get("rollback_target")
    change = rollback_target.get("state_change") if isinstance(rollback_target, Mapping) else None
    if isinstance(change, Mapping) and change.get("kind") == "restore_native_relation_set":
        trigger = case.get("trigger")
        time_point = trigger.get("time_point") if isinstance(trigger, Mapping) else None
        if time_point != "all_done":
            messages.append("native relation sets require the completion boundary")
        relations = change.get("relations") or []
        identities = [tuple(relation.get("predicate") or ()) for relation in relations]
        if len(set(identities)) != len(identities):
            messages.append("native relation sets cannot repeat a predicate")
        actors = [relation.get("actor_role") for relation in relations]
        if len(set(actors)) != len(actors):
            messages.append("native relation sets cannot write the same actor twice")
        completed = case.get("completed_relations") or []
        declared = {
            str(relation.get("predicate") or "").lower()
            for relation in completed
            if isinstance(relation, Mapping)
        }
        for relation in relations:
            if not isinstance(relation, Mapping):
                continue
            predicate = relation.get("predicate") or ()
            rendered = "(" + " ".join(str(token) for token in predicate).lower() + ")"
            if rendered not in declared:
                messages.append(
                    "native relation set predicates must be declared completed relations"
                )
                break
        if case.get("transient"):
            messages.append("native relation sets do not support temporal second writes")
    return messages


def validate_case(
    case: Any,
    schema: Mapping[str, Any] | None = None,
    *,
    semantic_checks: bool = True,
) -> list[str]:
    """Return human-readable schema errors for one parsed case mapping."""

    if schema is None:
        schema = _cached_schema()
    try:
        validator = Draft202012Validator(schema)
    except SchemaError as error:
        return [f"schema is not valid JSON Schema: {error.message}"]
    messages = _format_errors(validator, case)
    if semantic_checks and not messages and isinstance(case, Mapping):
        messages.extend(_case_semantic_errors(case))
    return messages


def validate_case_file(path: str | Path, *, semantic_checks: bool = True) -> list[str]:
    """Load one YAML case file and return its schema errors."""

    try:
        case = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        return [f"cannot read {path}: {error}"]
    return validate_case(case, semantic_checks=semantic_checks)


# ---------------------------------------------------------------------------
# composition metadata rows
# ---------------------------------------------------------------------------

METADATA_ROW_SCHEMA: Mapping[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "urn:libero-rollback:schema:compose-metadata:v1",
    "title": "LIBERO Rollback composition metadata row v1",
    "description": (
        "One C-suite structure definition (a line of dataset/compose/metadata.jsonl). "
        "Execution results are not part of the definition."
    ),
    "type": "object",
    "required": [
        "struct_id",
        "suite",
        "source_tasks",
        "goal_atoms",
        "n_atoms",
        "instruction",
        "init_source",
        "valid",
    ],
    "properties": {
        "struct_id": {"type": "string", "pattern": _STRUCT_ID_RE},
        "suite": {"type": "string", "enum": sorted(COMPOSE_SUITES)},
        "source_tasks": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": ["suite", "task_idx", "bddl_name"],
                "properties": {
                    "suite": {"type": "string", "enum": sorted(COMPOSE_SUITES)},
                    "task_idx": {"type": "integer", "minimum": 0, "maximum": 9},
                    "bddl_name": {"type": "string", "minLength": 1},
                },
            },
        },
        "goal_atoms": {
            "type": "array",
            "minItems": 2,
            "maxItems": 3,
            "items": {"type": "string", "pattern": _PREDICATE_RE},
        },
        "n_atoms": {"type": "integer", "minimum": 2, "maximum": 3},
        "instruction": {"type": "string", "minLength": 1},
        "instruction_variants": {
            "type": "object",
            "additionalProperties": {"type": "string", "minLength": 1},
        },
        "init_source": {"type": "string", "pattern": _INIT_SOURCE_RE},
        "valid": {"type": "boolean"},
        "class": {"type": "string", "minLength": 1},
        "notes": {"type": "string"},
    },
}

_METADATA_VALIDATOR = Draft202012Validator(METADATA_ROW_SCHEMA)


def _looks_absolute(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    if text.startswith(("/", "\\", "~")):
        return True
    return len(text) >= 3 and text[1] == ":" and text[0].isalpha() and text[2] in {"/", "\\"}


def validate_metadata_row(row: Any) -> list[str]:
    """Validate one C-suite ``metadata.jsonl`` row (structure + invariants).

    Complements the JSON Schema with the cross-field rules a structure row
    must satisfy: ``n_atoms`` equals the number of goal atoms, atoms are
    parenthesised predicates with a name and at least one argument, and every
    reference path stays relative (``docs/SPEC.md`` §1, §2.3, §4).
    """

    messages = _format_errors(_METADATA_VALIDATOR, row)
    if not isinstance(row, Mapping):
        return messages or ["<root>: metadata row must be a JSON object"]

    goal_atoms = row.get("goal_atoms")
    n_atoms = row.get("n_atoms")
    if isinstance(goal_atoms, list) and isinstance(n_atoms, int):
        if n_atoms != len(goal_atoms):
            messages.append("n_atoms must equal the number of goal_atoms")
        for index, atom in enumerate(goal_atoms):
            if not isinstance(atom, str):
                continue
            inner = atom.strip().strip("()").strip()
            if len(inner.split()) < 2:
                messages.append(f"goal_atoms/{index}: predicate needs a name and an argument")
    init_source = row.get("init_source")
    if isinstance(init_source, str) and _looks_absolute(init_source):
        messages.append("init_source must be relative to LIBERO_HOME, not absolute")
    instruction = row.get("instruction")
    if isinstance(instruction, str) and _looks_absolute(instruction):
        messages.append("instruction must not contain an absolute host path")
    source_tasks = row.get("source_tasks")
    if isinstance(source_tasks, list):
        seen_slots: set[tuple[str, str]] = set()
        for index, task in enumerate(source_tasks):
            if not isinstance(task, Mapping):
                continue
            slot = (str(task.get("suite")), str(task.get("task_idx")))
            if slot in seen_slots:
                messages.append(f"source_tasks/{index}: duplicate source task slot {slot}")
            seen_slots.add(slot)
    return messages


def validate_metadata_file(path: str | Path, *, limit: int | None = None) -> list[str]:
    """Validate every JSONL row of a composition metadata file.

    Errors are prefixed with ``line N:`` so a failing dataset can be triaged
    without re-running the checker. ``limit`` caps the number of reported
    errors (useful for very large files).
    """

    errors: list[str] = []
    path = Path(path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        return [f"cannot read {path}: {error}"]
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            errors.append(f"line {number}: invalid JSON: {error}")
        else:
            errors.extend(f"line {number}: {message}" for message in validate_metadata_row(row))
        if limit is not None and len(errors) >= limit:
            errors.append(f"line {number}: ... more errors suppressed (limit={limit})")
            break
    return errors
