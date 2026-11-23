#!/usr/bin/env python3
"""Static validator for the LIBERO-Rollback ``dataset/`` tree.

The checks are deliberately **self-contained** (stdlib + PyYAML): they can run on
a CPU-only machine without MuJoCo, LIBERO or model weights.  When the package
module ``libero_rollback.validation`` is importable it is also invoked (see
``--package-validation``), but the inline checks remain the authoritative gate
so this script and ``tests/test_dataset.py`` never depend on a concurrent
module implementation.

Schema v3 (base-only test-suite matrices, 2026-11-21)
-----------------------------------------------------
Canonical matrices and executable counts::

    a           dataset/matrices/a-matrix.csv                              40
    b           dataset/matrices/libero-rollback/completion-rollback.csv   442
    c           dataset/matrices/libero-rollback/in-execution-rollback.csv 180
    d_intact    dataset/matrices/libero-compose/intact.csv                 176
    d_rollback  dataset/matrices/libero-compose/rollback.csv               528

The legacy ``b-matrix.csv`` / ``d-native-matrix.csv`` /
``d-compose-provisional.csv`` files stay on disk untouched but are explicitly
legacy: they are never part of an executable split and are not hashed here.

What is checked
---------------
* layout / encoding: every required file exists, UTF-8 without BOM, LF endings;
* matrix contracts: exact column sets, row counts, ``case_id`` naming,
  one C0 per B task, no C0 in C, valid n=2 D-intact structures, 3 windows per
  D-rollback structure, compose asset hashes;
* ``manifest.yaml`` (schema 3): counts, per-file sha256/rows for the five
  canonical matrices, canonical splits, legacy annotation, no D provisional;
* ``lite.yaml`` (schema 2): 30 unique executable ids, 10 A / 10 B / 5 C /
  2 D-intact / 3 D-rollback, coverage block, consistent with manifest.lite;
* ``sources.yaml``: upstream pin and legacy import sha256/row counts;
* path hygiene: no absolute host paths and no runtime references to the
  precursor repositories inside ``dataset/``.

Exit codes: ``0`` all checks pass, ``1`` validation errors, ``2`` setup error.
Usage::

    python scripts/validate_dataset.py --dataset dataset
    python scripts/validate_dataset.py --dataset dataset --libero-home "$LIBERO_HOME"
    python scripts/validate_dataset.py --dataset dataset --json /tmp/report.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = REPO_ROOT / "dataset"

MATRIX_PATHS = {
    "a": "dataset/matrices/a-matrix.csv",
    "b": "dataset/matrices/libero-rollback/completion-rollback.csv",
    "c": "dataset/matrices/libero-rollback/in-execution-rollback.csv",
    "d_intact": "dataset/matrices/libero-compose/intact.csv",
    "d_rollback": "dataset/matrices/libero-compose/rollback.csv",
}
EXPECTED_COUNTS = {"a": 40, "b": 442, "c": 180, "d_intact": 176, "d_rollback": 528}
CORE_SPLIT = ["a", "b", "c", "d_intact", "d_rollback"]
LEGACY_PATHS = {
    "b": "dataset/matrices/b-matrix.csv",
    "d_native": "dataset/matrices/d-native-matrix.csv",
    "d_compose_provisional": "dataset/matrices/d-compose-provisional.csv",
}
LEGACY_COUNTS = {"b": 442, "d_native": 189, "d_compose_provisional": 360}
LITE_GROUPS = {"a": 10, "b": 10, "c": 5, "d_intact": 2, "d_rollback": 3}
LITE_COUNT = 30
VARIANCE_CASES = 100
VARIANCE_INIT_ROWS = [0, 1, 2, 3, 4]
LIBERO_REPO = "https://github.com/Lifelong-Robot-Learning/LIBERO"
LIBERO_COMMIT = "f78abd68ee283de9f9be3c8f7e2a9ad60246e95c"
DATASET_VERSION_FALLBACK = "2.0.0.dev0"
MANIFEST_SCHEMA_VERSION = 3
LITE_SCHEMA_VERSION = 2

SUITE_DIRS = {
    "goal": "libero_goal",
    "object": "libero_object",
    "spatial": "libero_spatial",
    "l10": "libero_10",
}

A_COLUMNS = (
    "case_id",
    "suite",
    "task_idx",
    "bddl_name",
    "instruction",
    "init_source",
    "n_goals",
    "semantics",
    "max_steps",
)
B_COLUMNS = (
    "case_id",
    "test_suite",
    "dimension",
    "arm",
    "suite",
    "task_idx",
    "bddl_name",
    "instruction",
    "target",
    "revoked_objects",
    "revoked_predicates",
    "family",
    "level",
    "param",
    "semantics",
    "trigger",
    "delay_steps",
    "repair_window",
    "expected_relation_after",
    "n_targets",
)
C_COLUMNS = (
    "case_id",
    "test_suite",
    "dimension",
    "arm",
    "sub",
    "suite",
    "task_idx",
    "struct_id",
    "instruction",
    "window",
    "trigger_criterion",
    "target",
    "revoked_predicate",
    "revoked_object",
    "family",
    "level",
    "param",
    "semantics",
    "max_steps",
    "repair_window",
    "expected_relation_after",
    "s2_must_stay_true",
)
D_INTACT_COLUMNS = (
    "case_id",
    "test_suite",
    "dimension",
    "arm",
    "sub",
    "suite",
    "struct_id",
    "source_suite",
    "order",
    "task_id",
    "instruction",
    "goal_atoms",
    "n_atoms",
    "family",
    "level",
    "param",
    "semantics",
    "max_steps",
    "repair_window",
    "expected_relation_after",
    "bddl_name",
    "init_source",
    "bddl_sha256",
    "pruned_init_sha256",
    "valid",
    "class",
)
D_ROLLBACK_COLUMNS = (
    "case_id",
    "test_suite",
    "dimension",
    "arm",
    "sub",
    "suite",
    "struct_id",
    "source_suite",
    "order",
    "task_id",
    "instruction",
    "window",
    "trigger_criterion",
    "target",
    "revoked_predicate",
    "revoked_object",
    "family",
    "level",
    "param",
    "semantics",
    "max_steps",
    "repair_window",
    "expected_relation_after",
    "s2_must_stay_true",
    "bddl_name",
    "init_source",
    "bddl_sha256",
    "pruned_init_sha256",
    "valid",
    "class",
)
EXPECTED_HEADERS = {
    "a": A_COLUMNS,
    "b": B_COLUMNS,
    "c": C_COLUMNS,
    "d_intact": D_INTACT_COLUMNS,
    "d_rollback": D_ROLLBACK_COLUMNS,
}

LEVEL_PARAMS = {
    ("C0", ""),
    ("L0", ""),
    ("L1", "d03"),
    ("L1", "d06"),
    ("L1", "d10"),
    ("L2", "r30"),
    ("L2", "r60"),
    ("L2", "r90"),
}
B_SUITES = frozenset(SUITE_DIRS)
B_TARGETS = frozenset({"c0", "g", "s1", "s2", "both", "pre"})
B_FAMILIES = frozenset({"pose", "joint", "mixed", "-"})
EXPECTED_BY_SUITE = {"goal": 85, "object": 80, "spatial": 80, "l10": 197}
EXPECTED_B_BY_LEVEL = {"C0": 40, "L0": 60, "L1": 180, "L2": 162}
C_WINDOWS = frozenset({"early", "mid", "later"})
D_WINDOWS = frozenset({"early", "mid", "later"})
C_TRIGGER_LABELS = frozenset(
    {"s1 first true", "s2 displacement > 5 cm", "distance to s2 goal < 8 cm"}
)
D_COMPOSE_TRIGGERS = {
    "early": "s1 first true",
    "mid": "s2 displacement > 5 cm",
    "later": "distance to s2 goal < 8 cm",
}

CASE_ID_PATTERNS = {
    "a": re.compile(r"^a-(goal|object|spatial|l10)-t\d{3}$"),
    "b": re.compile(
        r"^b-(goal|object|spatial|l10)-t\d{3}-"
        r"(c0|(g|s1|s2|both|pre)-(l0|l1-d(03|06|10)|l2-r(30|60|90)))$"
    ),
    "c": re.compile(
        r"^d-l10-t\d{3}-(early|mid|later)-(l0|l1-d(03|06|10)|l2-r(30|60|90))$"
    ),
    "d_intact": re.compile(r"^compose-intact-[a-z0-9_]+$"),
    "d_rollback": re.compile(r"^compose-rollback-[a-z0-9_]+-(early|mid|later)-l0$"),
}

# Generic path-shape patterns (built from shapes, not host-specific literals):
# POSIX absolute path, Windows drive path, UNC path, home-dir tilde path.
ABS_PATH_PATTERNS = (
    re.compile(r"(?<![:\w/$.~])/(?:[A-Za-z0-9_.-]+/)+"),
    re.compile(r"(?<![\w.])[A-Za-z]:[\\/]"),
    re.compile(r"\\\\[A-Za-z0-9_.-]+[\\/]"),
    re.compile(r"(?:^|[\s\"')(=:])~(?:/|\s|$)"),
)
PRECURSOR_TOKENS = ("libero_compose", "libero-compose", "libero_runtime", "libero-runtime")
HYGIENE_SUFFIXES = (".csv", ".yaml", ".yml", ".md", ".json")


class Report:
    """Collects errors/warnings and per-check status."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []
        self.checks: dict[str, bool] = {}

    def check(self, name: str, function, *args):
        before = len(self.errors)
        result = function(self, *args)
        self.checks[name] = len(self.errors) == before
        return result

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        header = tuple(reader.fieldnames or ())
        rows = list(reader)
    return header, rows


def load_yaml(path: Path):
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def is_true(value: str) -> bool:
    return str(value).strip().lower() == "true"


def is_false(value: str) -> bool:
    return str(value).strip().lower() == "false"


def task_idx_of(row: dict[str, str]) -> int:
    return int(str(row["task_idx"]).strip())


def level_key(row: dict[str, str]) -> tuple[str, str]:
    return (str(row.get("level", "")).strip(), str(row.get("param", "")).strip())


def expected_case_id(matrix: str, row: dict[str, str]) -> str | None:
    """Derive the case id from the row fields (None where not derivable)."""

    if matrix == "a":
        return f"a-{row['suite']}-t{task_idx_of(row):03d}"
    if matrix == "b":
        base = f"b-{row['suite']}-t{task_idx_of(row):03d}"
        level, param = level_key(row)
        if level == "C0":
            return f"{base}-c0"
        suffix = level.lower()
        if param:
            suffix = f"{suffix}-{param}"
        return f"{base}-{row['target']}-{suffix}"
    if matrix == "c":
        base = f"d-l10-t{task_idx_of(row):03d}"
        level, param = level_key(row)
        suffix = level.lower()
        if param:
            suffix = f"{suffix}-{param}"
        return f"{base}-{row['window']}-{suffix}"
    if matrix == "d_intact":
        return f"compose-intact-{row['struct_id']}"
    if matrix == "d_rollback":
        level, param = level_key(row)
        suffix = level.lower()
        if param:
            suffix = f"{suffix}-{param}"
        return f"compose-rollback-{row['struct_id']}-{row['window']}-{suffix}"
    return None


def matrix_path(dataset: Path, matrix: str) -> Path:
    return dataset.parent / MATRIX_PATHS[matrix]


def load_case_rows(dataset: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for matrix in MATRIX_PATHS:
        path = matrix_path(dataset, matrix)
        if not path.is_file():
            continue
        _header, matrix_rows = read_csv(path)
        for row in matrix_rows:
            case_id = str(row.get("case_id", "")).strip()
            if case_id and case_id not in rows:
                rows[case_id] = {"_matrix": matrix, **row}
    return rows


def coverage_of(groups: dict[str, list[str]], case_rows: dict[str, dict[str, str]]) -> dict:
    def counts(values: list[str]) -> dict[str, int]:
        result: dict[str, int] = {}
        for value in values:
            result[value] = result.get(value, 0) + 1
        return dict(sorted(result.items()))

    def rows(group: str) -> list[dict[str, str]]:
        return [case_rows[case_id] for case_id in groups[group] if case_id in case_rows]

    return {
        "a_suites": counts([row["suite"] for row in rows("a")]),
        "b_suites": counts([row["suite"] for row in rows("b")]),
        "b_levels": counts([row["level"] for row in rows("b")]),
        "c_windows": counts([row["window"] for row in rows("c")]),
        "c_levels": counts([row["level"] for row in rows("c")]),
        "d_intact_source_suites": counts([row["source_suite"] for row in rows("d_intact")]),
        "d_rollback_windows": counts([row["window"] for row in rows("d_rollback")]),
        "total": sum(len(entries) for entries in groups.values()),
    }


# ---------------------------------------------------------------------------
# Layout / encoding
# ---------------------------------------------------------------------------


def check_layout(report: Report, dataset: Path) -> None:
    required = [matrix_path(dataset, matrix) for matrix in MATRIX_PATHS]
    required.extend(
        [
            dataset / "manifest.yaml",
            dataset / "lite.yaml",
            dataset / "sources.yaml",
            dataset / "README.md",
        ]
    )
    for path in required:
        if not path.is_file():
            report.error(f"missing required file: {path}")
    compose_bddl = dataset / "compose" / "bddl"
    if not compose_bddl.is_dir():
        report.error(f"missing D-compose definition directory: {compose_bddl}")
    for matrix, rel_path in LEGACY_PATHS.items():
        if not (dataset.parent / rel_path).is_file():
            report.warn(f"legacy provenance file is missing: {rel_path}")
    if (dataset / "matrices" / "c-matrix.csv").exists():
        report.error(
            "dataset/matrices/c-matrix.csv must not exist; the C suite is the "
            "in-execution base view (dataset/matrices/libero-rollback/in-execution-rollback.csv)"
        )


def iter_dataset_text_files(dataset: Path):
    for path in sorted(dataset.rglob("*")):
        if path.is_file() and path.suffix.lower() in HYGIENE_SUFFIXES:
            yield path


def check_encoding(report: Report, dataset: Path) -> None:
    for path in iter_dataset_text_files(dataset):
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            report.error(f"{path}: UTF-8 BOM is not allowed")
        if b"\r" in raw:
            report.error(f"{path}: CR line endings are not allowed (must be LF)")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as error:
            report.error(f"{path}: not valid UTF-8 ({error})")
        if path.suffix.lower() == ".csv" and raw and not raw.endswith(b"\n"):
            report.error(f"{path}: CSV must end with a trailing newline")


# ---------------------------------------------------------------------------
# Matrix contracts
# ---------------------------------------------------------------------------


def check_matrix_headers(report: Report, dataset: Path) -> None:
    for matrix, rel_path in MATRIX_PATHS.items():
        path = dataset.parent / rel_path
        if not path.is_file():
            continue
        header, rows = read_csv(path)
        if header != EXPECTED_HEADERS[matrix]:
            report.error(
                f"{rel_path}: header mismatch; expected "
                f"{list(EXPECTED_HEADERS[matrix])}, got {list(header)}"
            )
        actual = len(rows)
        wanted = EXPECTED_COUNTS[matrix]
        if actual != wanted:
            report.error(f"{rel_path}: expected {wanted} data rows, found {actual}")


def _check_common_row(
    report: Report, matrix: str, rel_path: str, row: dict[str, str], seen: set[str]
) -> None:
    case_id = str(row.get("case_id", "")).strip()
    if not case_id:
        report.error(f"{rel_path}: row with empty case_id")
        return
    if case_id in seen:
        report.error(f"{rel_path}: duplicate case_id {case_id} (also used earlier)")
    seen.add(case_id)
    pattern = CASE_ID_PATTERNS[matrix]
    if not pattern.match(case_id):
        report.error(f"{rel_path}: case_id {case_id!r} does not match the naming scheme")
    derived = expected_case_id(matrix, row)
    if derived is not None and derived != case_id:
        report.error(
            f"{rel_path}: case_id {case_id!r} disagrees with row fields (expected {derived!r})"
        )


def _check_level_param(report: Report, rel_path: str, row: dict[str, str]) -> None:
    key = level_key(row)
    if key not in LEVEL_PARAMS:
        report.error(f"{rel_path}: {row.get('case_id')}: unsupported level/param {key}")


def _check_expected_relation(report: Report, rel_path: str, row: dict[str, str]) -> None:
    case_id = row.get("case_id")
    value = str(row.get("expected_relation_after", "")).strip().lower()
    if value not in {"true", "false"}:
        report.error(f"{rel_path}: {case_id}: expected_relation_after must be true/false")
        return
    if row.get("level") == "C0":
        if value != "true":
            report.error(f"{rel_path}: {case_id}: C0 must expect the relation to stay true")
    elif value != "false":
        report.error(f"{rel_path}: {case_id}: non-C0 must expect the relation to become false")


def check_a_matrix(report: Report, dataset: Path, seen: set[str]) -> None:
    rel_path = MATRIX_PATHS["a"]
    path = dataset.parent / rel_path
    if not path.is_file():
        return
    _header, rows = read_csv(path)
    for row in rows:
        case_id = row.get("case_id", "?")
        _check_common_row(report, "a", rel_path, row, seen)
        if row.get("semantics") != "intact":
            report.error(f"{rel_path}: {case_id}: semantics must be 'intact'")
        if str(row.get("max_steps")) != "600":
            report.error(f"{rel_path}: {case_id}: max_steps must be 600")
        try:
            n_goals = int(row.get("n_goals", ""))
        except ValueError:
            report.error(f"{rel_path}: {case_id}: n_goals is not an integer")
        else:
            if n_goals < 1:
                report.error(f"{rel_path}: {case_id}: n_goals must be >= 1")
        suite = row.get("suite")
        bddl_name = row.get("bddl_name", "")
        if suite not in SUITE_DIRS:
            report.error(f"{rel_path}: {case_id}: unknown suite {suite!r}")
        if bddl_name != Path(bddl_name).name or not bddl_name:
            report.error(f"{rel_path}: {case_id}: bddl_name must be a bare BDDL stem")
        expected_init = (
            f"libero/libero/init_files/{SUITE_DIRS.get(suite, '?')}/{bddl_name}.pruned_init"
        )
        if row.get("init_source") != expected_init:
            report.error(
                f"{rel_path}: {case_id}: init_source must be {expected_init!r} "
                f"(LIBERO_HOME-relative)"
            )


def check_b_suite(report: Report, dataset: Path, seen: set[str]) -> tuple[dict, list[dict]]:
    rel_path = MATRIX_PATHS["b"]
    path = dataset.parent / rel_path
    if not path.is_file():
        return {}, []
    _header, rows = read_csv(path)
    by_task: dict[tuple[str, int], list[dict[str, str]]] = {}
    suite_counts: dict[str, int] = {}
    level_counts: dict[str, int] = {}
    for row in rows:
        case_id = row.get("case_id", "?")
        _check_common_row(report, "b", rel_path, row, seen)
        _check_level_param(report, rel_path, row)
        _check_expected_relation(report, rel_path, row)
        if row.get("test_suite") != "libero-rollback" or row.get("dimension") != "completion":
            report.error(
                f"{rel_path}: {case_id}: expected test_suite=libero-rollback, "
                "dimension=completion"
            )
        expected_arm = "control" if row.get("level") == "C0" else "rollback"
        if row.get("arm") != expected_arm:
            report.error(f"{rel_path}: {case_id}: arm must be {expected_arm!r}")
        suite = str(row.get("suite", "")).strip()
        if suite not in B_SUITES:
            report.error(f"{rel_path}: {case_id}: unknown suite {suite!r}")
        if row.get("target") not in B_TARGETS:
            report.error(f"{rel_path}: {case_id}: unknown target {row.get('target')!r}")
        if row.get("family") not in B_FAMILIES:
            report.error(f"{rel_path}: {case_id}: unknown family {row.get('family')!r}")
        if row.get("trigger") != "all_done":
            report.error(f"{rel_path}: {case_id}: B requires trigger=all_done")
        if str(row.get("delay_steps")) != "10" or str(row.get("repair_window")) != "600":
            report.error(f"{rel_path}: {case_id}: delay_steps must be 10 and repair_window 600")
        semantics = "relation_holds_control" if row.get("level") == "C0" else "relation_then_resume"
        if row.get("semantics") != semantics:
            report.error(f"{rel_path}: {case_id}: semantics must be {semantics!r}")
        revoked_objects = str(row.get("revoked_objects", "")).strip()
        revoked_predicates = str(row.get("revoked_predicates", "")).strip()
        if row.get("level") == "C0":
            if revoked_objects or revoked_predicates:
                report.error(f"{rel_path}: {case_id}: C0 must not revoke anything")
            if row.get("target") != "c0":
                report.error(f"{rel_path}: {case_id}: C0 target must be 'c0'")
            if row.get("family") != "-":
                report.error(f"{rel_path}: {case_id}: C0 family must be '-'")
        else:
            if not revoked_objects or not revoked_predicates:
                report.error(f"{rel_path}: {case_id}: non-C0 needs revoked objects and predicates")
            for predicate in revoked_predicates.split("|"):
                if not predicate.strip().startswith("("):
                    report.error(
                        f"{rel_path}: {case_id}: predicate {predicate!r} is not parenthesised"
                    )
            if row.get("target") == "both":
                if len(revoked_predicates.split("|")) != 2:
                    report.error(
                        f"{rel_path}: {case_id}: target=both revokes exactly two predicates"
                    )
            elif len(revoked_predicates.split("|")) != 1:
                report.error(
                    f"{rel_path}: {case_id}: target={row.get('target')} revokes one predicate"
                )
        if row.get("level") == "L2" and row.get("family") == "joint":
            report.error(f"{rel_path}: {case_id}: joint tasks have no L2 level")
        try:
            if int(row.get("n_targets", "")) < 1:
                report.error(f"{rel_path}: {case_id}: n_targets must be >= 1")
        except ValueError:
            report.error(f"{rel_path}: {case_id}: n_targets is not an integer")
        task_key = (suite, task_idx_of(row))
        by_task.setdefault(task_key, []).append(row)
        suite_counts[suite] = suite_counts.get(suite, 0) + 1
        level_counts[str(row.get("level"))] = level_counts.get(str(row.get("level")), 0) + 1

    if len(by_task) != 40:
        report.error(f"{rel_path}: expected 40 task keys, found {len(by_task)}")
    if suite_counts != EXPECTED_BY_SUITE:
        report.error(f"{rel_path}: suite counts {suite_counts} != {EXPECTED_BY_SUITE}")
    if level_counts != EXPECTED_B_BY_LEVEL:
        report.error(f"{rel_path}: level counts {level_counts} != {EXPECTED_B_BY_LEVEL}")
    for task_key, task_rows in by_task.items():
        controls = [row for row in task_rows if row.get("level") == "C0"]
        if len(controls) != 1:
            report.error(
                f"{rel_path}: task {task_key}: expected exactly one C0, found {len(controls)}"
            )
        for field in ("instruction", "bddl_name"):
            values = {row.get(field, "") for row in task_rows}
            if len(values) != 1:
                report.error(f"{rel_path}: task {task_key}: {field} differs across cases")
    return by_task, rows


def check_c_suite(
    report: Report, dataset: Path, seen: set[str], b_by_task: dict
) -> None:
    rel_path = MATRIX_PATHS["c"]
    path = dataset.parent / rel_path
    if not path.is_file():
        return
    _header, rows = read_csv(path)
    by_task: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        case_id = row.get("case_id", "?")
        _check_common_row(report, "c", rel_path, row, seen)
        _check_level_param(report, rel_path, row)
        _check_expected_relation(report, rel_path, row)
        if row.get("test_suite") != "libero-rollback" or row.get("dimension") != "in-execution":
            report.error(
                f"{rel_path}: {case_id}: expected test_suite=libero-rollback, "
                "dimension=in-execution"
            )
        if row.get("arm") != "rollback":
            report.error(f"{rel_path}: {case_id}: C arm must be 'rollback'")
        if row.get("sub") != "native" or row.get("suite") != "l10":
            report.error(f"{rel_path}: {case_id}: expected sub=native, suite=l10")
        window = row.get("window", "")
        if window not in C_WINDOWS:
            report.error(f"{rel_path}: {case_id}: C window {window!r} must be early/mid/later")
        if row.get("level") == "C0":
            report.error(f"{rel_path}: {case_id}: C must not contain a C0 control")
        if row.get("target") != "s1":
            report.error(f"{rel_path}: {case_id}: C target must be 's1'")
        if row.get("trigger_criterion") not in C_TRIGGER_LABELS:
            report.error(
                f"{rel_path}: {case_id}: unexpected trigger_criterion "
                f"{row.get('trigger_criterion')!r}"
            )
        if str(row.get("max_steps")) != "800" or str(row.get("repair_window")) != "600":
            report.error(f"{rel_path}: {case_id}: C needs max_steps=800, repair_window=600")
        if row.get("s2_must_stay_true") not in {"true", "false"}:
            report.error(f"{rel_path}: {case_id}: s2_must_stay_true must be true/false")
        if row.get("semantics") != "relation_then_resume":
            report.error(f"{rel_path}: {case_id}: C semantics must be relation_then_resume")
        by_task.setdefault(task_idx_of(row), []).append(row)
    if len(by_task) != 9:
        report.error(f"{rel_path}: expected 9 native tasks, found {len(by_task)}")
    for task_idx, task_rows in by_task.items():
        if ("l10", task_idx) not in b_by_task:
            report.error(
                f"{rel_path}: C task l10/t{task_idx:03d} has no B-matrix l10 task key"
            )
        windows = {row["window"] for row in task_rows}
        if windows != C_WINDOWS:
            report.error(
                f"{rel_path}: task l10/t{task_idx:03d}: expected early/mid/later, "
                f"got {sorted(windows)}"
            )
        for window in C_WINDOWS:
            expected = 4 if task_idx == 0 else 7
            actual = sum(1 for row in task_rows if row["window"] == window)
            if actual != expected:
                report.error(
                    f"{rel_path}: task l10/t{task_idx:03d}/{window}: expected {expected} cases, "
                    f"found {actual}"
                )
        b_instruction = None
        for b_row in b_by_task.get(("l10", task_idx), []):
            b_instruction = b_row["instruction"]
            break
        instructions = {row.get("instruction", "") for row in task_rows}
        if b_instruction is not None and instructions != {b_instruction}:
            report.error(
                f"{rel_path}: task l10/t{task_idx:03d}: instruction differs from the B l10 task"
            )


def _check_compose_assets(
    report: Report, dataset: Path, rel_path: str, rows: list[dict[str, str]]
) -> None:
    root = dataset / "compose" / "bddl"
    for row in rows:
        case_id = row.get("case_id", "?")
        task_id = str(row.get("task_id", "")).strip()
        if not task_id:
            report.error(f"{rel_path}: {case_id}: task_id is required for the asset check")
            continue
        bddl = root / f"{task_id}.bddl"
        init = root / f"{task_id}.pruned_init"
        if not bddl.is_file():
            report.error(f"{rel_path}: {case_id}: missing D-compose BDDL {bddl.name}")
            continue
        if not init.is_file():
            report.error(f"{rel_path}: {case_id}: missing D-compose init {init.name}")
            continue
        if sha256_file(bddl) != row.get("bddl_sha256"):
            report.error(f"{rel_path}: {case_id}: bddl_sha256 does not match {bddl.name}")
        if sha256_file(init) != row.get("pruned_init_sha256"):
            report.error(f"{rel_path}: {case_id}: pruned_init_sha256 does not match {init.name}")


def check_d_intact(report: Report, dataset: Path, seen: set[str]) -> set[str]:
    rel_path = MATRIX_PATHS["d_intact"]
    path = dataset.parent / rel_path
    if not path.is_file():
        return set()
    _header, rows = read_csv(path)
    structs: set[str] = set()
    source_counts: dict[str, int] = {}
    for row in rows:
        case_id = row.get("case_id", "?")
        _check_common_row(report, "d_intact", rel_path, row, seen)
        if row.get("test_suite") != "compose" or row.get("dimension") != "intact":
            report.error(f"{rel_path}: {case_id}: expected test_suite=compose, dimension=intact")
        if row.get("arm") != "intact":
            report.error(f"{rel_path}: {case_id}: D-intact arm must be 'intact'")
        if row.get("sub") != "compose" or row.get("suite") != "compose":
            report.error(f"{rel_path}: {case_id}: expected sub=compose, suite=compose")
        if row.get("level") != "INTACT" or str(row.get("param", "")).strip():
            report.error(f"{rel_path}: {case_id}: D-intact must be level INTACT without param")
        if str(row.get("n_atoms")) != "2":
            report.error(f"{rel_path}: {case_id}: D-intact must be an n=2 structure")
        if not is_true(row.get("valid", "")):
            report.error(f"{rel_path}: {case_id}: D-intact rows must be valid")
        if not is_true(row.get("expected_relation_after", "")):
            report.error(f"{rel_path}: {case_id}: D-intact must expect the relation to stay true")
        if str(row.get("repair_window")) != "0" or str(row.get("max_steps")) != "600":
            report.error(f"{rel_path}: {case_id}: D-intact needs repair_window=0, max_steps=600")
        if row.get("semantics") != "relation_holds_intact":
            report.error(f"{rel_path}: {case_id}: D-intact semantics must be relation_holds_intact")
        if str(row.get("goal_atoms", "")).count("|") != 1:
            report.error(f"{rel_path}: {case_id}: D-intact goal_atoms must hold exactly two atoms")
        structs.add(str(row.get("struct_id", "")))
        source = str(row.get("source_suite", ""))
        source_counts[source] = source_counts.get(source, 0) + 1
    if len(structs) != 176:
        report.error(f"{rel_path}: expected 176 structures, found {len(structs)}")
    if source_counts != {"LIBERO_GOAL": 76, "LIBERO_OBJECT": 100}:
        report.error(
            f"{rel_path}: source_suite counts {source_counts} != "
            "LIBERO_GOAL 76 / LIBERO_OBJECT 100"
        )
    _check_compose_assets(report, dataset, rel_path, rows)
    return structs


def check_d_rollback(report: Report, dataset: Path, seen: set[str]) -> set[str]:
    rel_path = MATRIX_PATHS["d_rollback"]
    path = dataset.parent / rel_path
    if not path.is_file():
        return set()
    _header, rows = read_csv(path)
    structs: set[str] = set()
    by_struct: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        case_id = row.get("case_id", "?")
        _check_common_row(report, "d_rollback", rel_path, row, seen)
        if row.get("test_suite") != "compose" or row.get("dimension") != "in-execution":
            report.error(
                f"{rel_path}: {case_id}: expected test_suite=compose, dimension=in-execution"
            )
        if row.get("arm") != "rollback":
            report.error(f"{rel_path}: {case_id}: D-rollback arm must be 'rollback'")
        if row.get("sub") != "compose" or row.get("suite") != "compose":
            report.error(f"{rel_path}: {case_id}: expected sub=compose, suite=compose")
        if row.get("level") != "L0" or str(row.get("param", "")).strip():
            report.error(f"{rel_path}: {case_id}: D-rollback must be level L0 without param")
        if row.get("window") not in D_WINDOWS:
            report.error(f"{rel_path}: {case_id}: D-rollback window must be early/mid/later")
        if D_COMPOSE_TRIGGERS.get(str(row.get("window"))) != row.get("trigger_criterion"):
            report.error(f"{rel_path}: {case_id}: trigger_criterion does not match the window")
        if row.get("target") != "s1":
            report.error(f"{rel_path}: {case_id}: D-rollback target must be 's1'")
        if not is_true(row.get("valid", "")):
            report.error(f"{rel_path}: {case_id}: D-rollback rows must be valid")
        if not is_true(row.get("s2_must_stay_true", "")):
            report.error(f"{rel_path}: {case_id}: D-rollback requires s2_must_stay_true=true")
        if not is_false(row.get("expected_relation_after", "")):
            report.error(
                f"{rel_path}: {case_id}: D-rollback must expect the relation to become false"
            )
        if str(row.get("repair_window")) != "600" or str(row.get("max_steps")) != "600":
            report.error(
                f"{rel_path}: {case_id}: D-rollback needs repair_window=600, "
                "max_steps=600"
            )
        if row.get("semantics") != "relation_then_resume":
            report.error(
                f"{rel_path}: {case_id}: D-rollback semantics must be relation_then_resume"
            )
        struct_id = str(row.get("struct_id", ""))
        structs.add(struct_id)
        by_struct.setdefault(struct_id, []).append(row)
    if len(structs) != 176:
        report.error(f"{rel_path}: expected 176 structures, found {len(structs)}")
    for struct_id, struct_rows in by_struct.items():
        windows = sorted(row["window"] for row in struct_rows)
        if windows != ["early", "later", "mid"]:
            report.error(
                f"{rel_path}: structure {struct_id}: expected early/mid/later, got {windows}"
            )
    _check_compose_assets(report, dataset, rel_path, rows)
    return structs


def check_cross_matrix(report: Report, dataset: Path, intact: set[str], rollback: set[str]) -> None:
    if intact and rollback and intact != rollback:
        only_intact = sorted(intact - rollback)[:5]
        only_rollback = sorted(rollback - intact)[:5]
        report.error(
            "D-intact and D-rollback structure ids differ: "
            f"only intact={only_intact}, only rollback={only_rollback}"
        )


# ---------------------------------------------------------------------------
# manifest / lite / sources
# ---------------------------------------------------------------------------


def actual_row_counts(dataset: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for matrix, rel_path in MATRIX_PATHS.items():
        path = dataset.parent / rel_path
        if path.is_file():
            _header, rows = read_csv(path)
            counts[matrix] = len(rows)
    return counts


def executable_case_ids(dataset: Path) -> set[str]:
    return set(load_case_rows(dataset))


def check_manifest(report: Report, dataset: Path) -> None:
    path = dataset / "manifest.yaml"
    if not path.is_file():
        return
    try:
        manifest = load_yaml(path)
    except Exception as error:  # noqa: BLE001 - report parse failures as validation errors
        report.error(f"manifest.yaml: cannot parse ({type(error).__name__}: {error})")
        return
    if not isinstance(manifest, dict):
        report.error("manifest.yaml: top-level must be a mapping")
        return
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        report.error(
            f"manifest.yaml: schema_version must be {MANIFEST_SCHEMA_VERSION}, "
            f"got {manifest.get('schema_version')!r}"
        )
    version = str(manifest.get("dataset_version", "")).strip()
    if not version:
        report.error("manifest.yaml: dataset_version is missing")
    elif version != dataset_version():
        report.error(
            f"manifest.yaml: dataset_version {version!r} != pyproject version {dataset_version()!r}"
        )
    if manifest.get("generated_by") != "scripts/build_manifest.py":
        report.error("manifest.yaml: generated_by must be 'scripts/build_manifest.py'")
    libero = manifest.get("libero") or {}
    if not isinstance(libero, dict) or not libero.get("repo") or not libero.get("commit"):
        report.error("manifest.yaml: libero.repo and libero.commit are required")
    else:
        if libero["repo"] != LIBERO_REPO:
            report.error(f"manifest.yaml: libero.repo must be {LIBERO_REPO!r}")
        if libero["commit"] != LIBERO_COMMIT:
            report.error(f"manifest.yaml: libero.commit must be {LIBERO_COMMIT!r}")

    counts = manifest.get("counts") or {}
    if counts != EXPECTED_COUNTS:
        report.error(f"manifest.yaml: counts {counts} != expected {EXPECTED_COUNTS}")
    actual = actual_row_counts(dataset)
    for matrix, expected in EXPECTED_COUNTS.items():
        if actual.get(matrix, 0) != expected:
            report.error(
                f"manifest.yaml: count {matrix}={expected} but CSV has {actual.get(matrix, 0)} rows"
            )

    legacy = manifest.get("legacy")
    if not isinstance(legacy, dict):
        report.error("manifest.yaml: legacy must be a mapping listing the retained CSVs")
    else:
        if legacy.get("counts") != LEGACY_COUNTS:
            report.error(
                f"manifest.yaml: legacy.counts {legacy.get('counts')} != {LEGACY_COUNTS}"
            )
        legacy_files = legacy.get("files")
        if not isinstance(legacy_files, list) or set(map(str, legacy_files)) != set(
            LEGACY_PATHS.values()
        ):
            report.error(
                "manifest.yaml: legacy.files must list exactly "
                f"{sorted(LEGACY_PATHS.values())}"
            )
        for rel_path in LEGACY_PATHS.values():
            if not (dataset.parent / rel_path).is_file():
                report.warn(f"manifest.yaml: legacy file is missing on disk: {rel_path}")

    provisional = manifest.get("provisional")
    if provisional:
        report.error(
            "manifest.yaml: provisional must be absent/empty; the D definitions are built "
            "(legacy files belong under manifest.legacy)"
        )

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        report.error("manifest.yaml: files must be a non-empty list")
        return
    listed: dict[str, dict] = {}
    for entry in files:
        if not isinstance(entry, dict):
            report.error(f"manifest.yaml: files entry is not a mapping: {entry!r}")
            continue
        rel_path = str(entry.get("path", ""))
        if not rel_path.startswith("dataset/"):
            report.error(
                f"manifest.yaml: files path must be repo-relative under dataset/: {rel_path!r}"
            )
            continue
        listed[rel_path] = entry
        file_path = dataset.parent / rel_path
        if not file_path.is_file():
            report.error(f"manifest.yaml: files path does not exist: {rel_path}")
            continue
        sha = str(entry.get("sha256", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            report.error(f"manifest.yaml: {rel_path}: sha256 must be 64 lowercase hex chars")
        elif sha != sha256_file(file_path):
            report.error(f"manifest.yaml: {rel_path}: sha256 does not match the file on disk")
        if file_path.suffix == ".csv":
            _header, rows = read_csv(file_path)
            if entry.get("rows") != len(rows):
                report.error(f"manifest.yaml: {rel_path}: rows != {len(rows)}")
    expected_files = set(MATRIX_PATHS.values())
    if set(listed) != expected_files:
        report.error(
            "manifest.yaml: files must list exactly the five canonical matrices; "
            f"missing={sorted(expected_files - set(listed))}, "
            f"unexpected={sorted(set(listed) - expected_files)}"
        )

    splits = manifest.get("splits") or {}
    if not isinstance(splits, dict):
        report.error("manifest.yaml: splits must be a mapping")
        return
    lite = splits.get("lite")
    lite_path = dataset / "lite.yaml"
    if isinstance(lite, list) and lite_path.is_file():
        lite_payload = load_yaml(lite_path) or {}
        lite_cases = lite_payload.get("cases") or []
        if len(lite) != LITE_COUNT:
            report.error(
                f"manifest.yaml: splits.lite must have {LITE_COUNT} ids, found {len(lite)}"
            )
        if set(map(str, lite)) != set(map(str, lite_cases)):
            report.error("manifest.yaml: splits.lite != lite.yaml cases")
        if len(set(map(str, lite))) != len(lite):
            report.error("manifest.yaml: splits.lite contains duplicate case ids")
    else:
        report.error("manifest.yaml: splits.lite must be a list")
    if splits.get("core") != CORE_SPLIT:
        report.error(
            f"manifest.yaml: splits.core must be {CORE_SPLIT}, got {splits.get('core')!r}"
        )
    variance = splits.get("variance")
    if not isinstance(variance, dict):
        report.error("manifest.yaml: splits.variance must be a mapping")
    else:
        variance_cases = variance.get("cases")
        if not isinstance(variance_cases, list) or len(variance_cases) != VARIANCE_CASES:
            report.error(
                f"manifest.yaml: splits.variance.cases must list {VARIANCE_CASES} case ids"
            )
        else:
            executable = executable_case_ids(dataset)
            unknown = [case_id for case_id in variance_cases if case_id not in executable]
            if unknown:
                report.error(
                    f"manifest.yaml: splits.variance has non-executable cases: {unknown[:5]}"
                )
            if len(set(map(str, variance_cases))) != len(variance_cases):
                report.error("manifest.yaml: splits.variance contains duplicate case ids")
        if variance.get("init_rows") != VARIANCE_INIT_ROWS:
            report.error(f"manifest.yaml: splits.variance.init_rows must be {VARIANCE_INIT_ROWS}")


def check_lite(report: Report, dataset: Path) -> None:
    path = dataset / "lite.yaml"
    if not path.is_file():
        return
    try:
        payload = load_yaml(path)
    except Exception as error:  # noqa: BLE001
        report.error(f"lite.yaml: cannot parse ({type(error).__name__}: {error})")
        return
    if not isinstance(payload, dict):
        report.error("lite.yaml: top-level must be a mapping with a 'cases' list")
        return
    if payload.get("schema_version") != LITE_SCHEMA_VERSION:
        report.error(
            f"lite.yaml: schema_version must be {LITE_SCHEMA_VERSION}, "
            f"got {payload.get('schema_version')!r}"
        )
    cases = payload.get("cases")
    if not isinstance(cases, list) or not all(isinstance(case_id, str) for case_id in cases):
        report.error("lite.yaml: cases must be a list of case-id strings")
        return
    if len(cases) != LITE_COUNT:
        report.error(f"lite.yaml: expected {LITE_COUNT} cases, found {len(cases)}")
    if len(set(cases)) != len(cases):
        report.error("lite.yaml: duplicate case ids")
    case_rows = load_case_rows(dataset)
    unknown = [case_id for case_id in cases if case_id not in case_rows]
    if unknown:
        report.error(f"lite.yaml: ids not found in the canonical matrices: {unknown[:10]}")
    splits = payload.get("splits")
    if not isinstance(splits, dict) or set(splits) != set(LITE_GROUPS):
        report.error(f"lite.yaml: splits must contain exactly {sorted(LITE_GROUPS)}")
        return
    union: list[str] = []
    for key, wanted in LITE_GROUPS.items():
        group = splits.get(key)
        if not isinstance(group, list) or len(group) != wanted:
            report.error(f"lite.yaml: splits.{key} must contain {wanted} case ids")
            continue
        union.extend(group)
        for case_id in group:
            row = case_rows.get(case_id)
            if row is not None and row.get("_matrix") != key:
                report.error(
                    f"lite.yaml: case {case_id!r} is in splits.{key} but belongs to "
                    f"matrix {row.get('_matrix')!r}"
                )
    if sorted(union) != sorted(cases):
        report.error("lite.yaml: splits groups do not union to the cases list")
    for case_id in splits.get("c", []):
        row = case_rows.get(case_id, {})
        if row.get("level") == "C0" or row.get("window") == "all_done_control":
            report.error(f"lite.yaml: C case {case_id!r} must not be a C0/all_done control")
    for case_id in splits.get("d_intact", []):
        row = case_rows.get(case_id, {})
        if not is_true(row.get("valid", "")) or str(row.get("n_atoms")) != "2":
            report.error(f"lite.yaml: D-intact case {case_id!r} must be a valid n=2 structure")
    expected_coverage = coverage_of({key: list(value) for key, value in splits.items()}, case_rows)
    if payload.get("coverage") != expected_coverage:
        report.error(
            f"lite.yaml: coverage {payload.get('coverage')} != recomputed {expected_coverage}"
        )


def check_sources(report: Report, dataset: Path) -> None:
    path = dataset / "sources.yaml"
    if not path.is_file():
        return
    try:
        payload = load_yaml(path)
    except Exception as error:  # noqa: BLE001
        report.error(f"sources.yaml: cannot parse ({type(error).__name__}: {error})")
        return
    if not isinstance(payload, dict):
        report.error("sources.yaml: top-level must be a mapping")
        return
    upstream = payload.get("upstream") or {}
    if upstream.get("repo") != LIBERO_REPO or upstream.get("commit") != LIBERO_COMMIT:
        report.error("sources.yaml: upstream repo/commit must pin the LIBERO commit")
    imports = payload.get("imports")
    if not isinstance(imports, list) or not imports:
        report.error("sources.yaml: imports must be a non-empty list")
        return
    targets = set()
    for entry in imports:
        if not isinstance(entry, dict):
            report.error(f"sources.yaml: imports entry is not a mapping: {entry!r}")
            continue
        rel_path = str(entry.get("target", ""))
        targets.add(rel_path)
        target = dataset.parent / rel_path
        if not target.is_file():
            report.error(f"sources.yaml: import target does not exist: {rel_path}")
            continue
        sha = str(entry.get("sha256", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            report.error(f"sources.yaml: {rel_path}: sha256 must be 64 lowercase hex chars")
        elif sha != sha256_file(target):
            report.error(f"sources.yaml: {rel_path}: sha256 does not match the on-disk file")
        if "rows" in entry:
            _header, rows = read_csv(target)
            if entry["rows"] != len(rows):
                report.error(f"sources.yaml: {rel_path}: rows != {len(rows)}")
        if not str(entry.get("source_path", "")).strip():
            report.error(f"sources.yaml: {rel_path}: source_path is required")
    for matrix in ("b", "d_native", "d_compose_provisional"):
        if LEGACY_PATHS[matrix] not in targets:
            report.error(f"sources.yaml: missing import entry for {LEGACY_PATHS[matrix]}")
    generated = payload.get("generated")
    if not isinstance(generated, list):
        report.error("sources.yaml: generated must be a list")
    else:
        generated_targets = {
            str(entry.get("target", "")) for entry in generated if isinstance(entry, dict)
        }
        if MATRIX_PATHS["a"] not in generated_targets:
            report.error(f"sources.yaml: missing generated entry for {MATRIX_PATHS['a']}")


# ---------------------------------------------------------------------------
# Path hygiene
# ---------------------------------------------------------------------------


def check_path_hygiene(report: Report, dataset: Path) -> None:
    for path in iter_dataset_text_files(dataset):
        text = path.read_text(encoding="utf-8", errors="replace")
        rel_path = path.relative_to(dataset.parent)
        for pattern in ABS_PATH_PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                report.error(
                    f"{rel_path}:{line}: absolute host path is not allowed: {match.group(0)!r}"
                )
        if path.name == "sources.yaml":
            # provenance by design names the source repository (SPEC §9); only the
            # source_repo value may mention a precursor repository.
            for line_number, line in enumerate(text.splitlines(), start=1):
                if "source_repo" in line:
                    continue
                lowered = line.lower()
                for token in PRECURSOR_TOKENS:
                    if token in lowered:
                        report.error(
                            f"{rel_path}:{line_number}: precursor-repository reference "
                            f"{token!r} is only allowed in a source_repo field"
                        )
        else:
            lowered = text.lower()
            for token in PRECURSOR_TOKENS:
                if token not in lowered:
                    continue
                # The dataset directory itself is named libero-compose for the
                # D-compose suite; a path under dataset/matrices/libero-compose/
                # is a data location, not a runtime reference to a precursor repo.
                if token == "libero-compose":
                    offending = [
                        line
                        for line in text.splitlines()
                        if "libero-compose" in line.lower()
                        and "dataset/matrices/libero-compose/" not in line.lower()
                    ]
                    if not offending:
                        continue
                report.error(
                    f"{rel_path}: precursor-repository reference {token!r} is not allowed "
                    "inside dataset/"
                )


# ---------------------------------------------------------------------------
# Optional LIBERO-asset checks (only when --libero-home / LIBERO_HOME is given)
# ---------------------------------------------------------------------------


def _asset_root(libero_home: Path) -> Path | None:
    for candidate in (libero_home / "libero" / "libero", libero_home, libero_home / "libero"):
        if (candidate / "bddl_files").is_dir() and (candidate / "init_files").is_dir():
            return candidate
    return None


_LANGUAGE_RE = re.compile(r"\(:language\s+(.+?)\)\s*(?:\r?\n|$)", re.DOTALL)


def check_libero_assets(report: Report, dataset: Path, libero_home: Path) -> None:
    asset_root = _asset_root(libero_home)
    if asset_root is None:
        report.error(f"--libero-home {libero_home}: cannot locate bddl_files/init_files")
        return
    bddl_count = len(list((asset_root / "bddl_files").rglob("*.bddl")))
    init_count = len(list((asset_root / "init_files").rglob("*.pruned_init")))
    if bddl_count != 130 or init_count != 130:
        report.error(
            f"--libero-home: expected 130 bddl + 130 init files, found {bddl_count}/{init_count}"
        )
    a_path = matrix_path(dataset, "a")
    if a_path.is_file():
        _header, a_rows = read_csv(a_path)
        for row in a_rows:
            suite_dir = SUITE_DIRS.get(row["suite"])
            if suite_dir is None:
                continue
            bddl = asset_root / "bddl_files" / suite_dir / f"{row['bddl_name']}.bddl"
            init = asset_root / "init_files" / suite_dir / f"{row['bddl_name']}.pruned_init"
            if not bddl.is_file():
                report.error(f"--libero-home: missing BDDL for {row['case_id']}: {bddl}")
                continue
            if not init.is_file():
                report.error(f"--libero-home: missing init state for {row['case_id']}: {init}")
            match = _LANGUAGE_RE.search(bddl.read_text(encoding="utf-8"))
            if match is None:
                report.error(f"--libero-home: {bddl}: no (:language ...) declaration")
            elif match.group(1).strip() != row["instruction"]:
                report.error(f"--libero-home: {bddl}: language != A-matrix instruction")
    b_path = matrix_path(dataset, "b")
    if b_path.is_file():
        _header, b_rows = read_csv(b_path)
        seen_tasks: set[tuple[str, str]] = set()
        for row in b_rows:
            task_key = (row["suite"], row["bddl_name"])
            if task_key in seen_tasks:
                continue
            seen_tasks.add(task_key)
            suite_dir = SUITE_DIRS.get(row["suite"])
            if suite_dir is None:
                continue
            bddl = asset_root / "bddl_files" / suite_dir / f"{row['bddl_name']}.bddl"
            init = asset_root / "init_files" / suite_dir / f"{row['bddl_name']}.pruned_init"
            if not bddl.is_file():
                report.error(f"--libero-home: B task BDDL missing: {bddl}")
            if not init.is_file():
                report.error(f"--libero-home: B task init missing: {init}")


# ---------------------------------------------------------------------------
# Optional package-module hook
# ---------------------------------------------------------------------------


def _extract_messages(result, field: str) -> list[str]:
    value = result.get(field) if isinstance(result, dict) else getattr(result, field, None)
    if value is None:
        return []
    return [str(item) for item in value]


def run_package_validation(report: Report, dataset: Path, *, enabled: bool, strict: bool) -> None:
    if not enabled:
        report.notes.append("package validation disabled (--no-package-validation)")
        return
    try:
        from libero_rollback.validation import validate_dataset as package_validate
    except Exception as error:  # noqa: BLE001 - module may be absent during migration
        report.notes.append(
            "libero_rollback.validation not available "
            f"({type(error).__name__}: {error}); inline checks only"
        )
        return
    try:
        result = package_validate(dataset)
    except Exception as error:  # noqa: BLE001 - never let the optional module break the gate
        report.warnings.append(
            f"libero_rollback.validation raised {type(error).__name__}: {error}; inline checks only"
        )
        report.notes.append("package validation: not used")
        return
    errors = _extract_messages(result, "errors")
    warnings = _extract_messages(result, "warnings")
    ok = result.get("ok") if isinstance(result, dict) else getattr(result, "ok", None)
    report.notes.append(
        f"package validation: ok={ok} errors={len(errors)} warnings={len(warnings)}"
    )
    report.warnings.extend(f"[libero_rollback.validation] {message}" for message in warnings)
    for message in errors:
        if strict:
            report.error(f"[libero_rollback.validation] {message}")
        else:
            report.warnings.append(f"[libero_rollback.validation] {message}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def dataset_version() -> str:
    try:
        payload = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        return str(payload["project"]["version"])
    except Exception:  # noqa: BLE001
        return DATASET_VERSION_FALLBACK


def validate(
    dataset: Path, *, libero_home: Path | None, package_validation: bool, strict_package: bool
) -> Report:
    report = Report()
    if not dataset.is_dir():
        report.error(f"dataset directory does not exist: {dataset}")
        return report
    report.check("layout", check_layout, dataset)
    report.check("encoding", check_encoding, dataset)
    if not report.ok:
        return report
    seen: set[str] = set()
    report.check("matrix_headers", check_matrix_headers, dataset)
    report.check("a_matrix", check_a_matrix, dataset, seen)
    b_by_task = report.check("b_suite", check_b_suite, dataset, seen)[0]
    report.check("c_suite", check_c_suite, dataset, seen, b_by_task)
    intact = report.check("d_intact", check_d_intact, dataset, seen)
    rollback = report.check("d_rollback", check_d_rollback, dataset, seen)
    report.check("cross_matrix", check_cross_matrix, dataset, intact, rollback)
    report.check("manifest", check_manifest, dataset)
    report.check("lite", check_lite, dataset)
    report.check("sources", check_sources, dataset)
    report.check("path_hygiene", check_path_hygiene, dataset)
    if libero_home is not None:
        report.check("libero_assets", check_libero_assets, dataset, libero_home)
    run_package_validation(report, dataset, enabled=package_validation, strict=strict_package)
    return report


def print_report(report: Report, dataset: Path, libero_home: Path | None) -> None:
    counts = actual_row_counts(dataset) if dataset.is_dir() else {}
    summary = " ".join(f"{key}={counts.get(key, '?')}" for key in MATRIX_PATHS)
    print(f"[validate_dataset] dataset: {dataset}")
    print(f"[validate_dataset] rows: {summary}")
    print(f"[validate_dataset] libero assets: {libero_home if libero_home else 'not checked'}")
    failed = [name for name, ok in report.checks.items() if not ok]
    print(
        f"[validate_dataset] checks: {len(report.checks) - len(failed)}/{len(report.checks)} passed"
    )
    for note in report.notes:
        print(f"[validate_dataset] note: {note}")
    for warning in report.warnings:
        print(f"[validate_dataset] warning: {warning}")
    for error in report.errors:
        print(f"[validate_dataset] ERROR: {error}")
    if report.ok:
        print("[validate_dataset] OK")
    else:
        print(f"[validate_dataset] FAILED ({len(report.errors)} error(s))")


def build_json_report(report: Report, dataset: Path, libero_home: Path | None) -> dict:
    return {
        "dataset": str(dataset),
        "libero_home": None if libero_home is None else str(libero_home),
        "ok": report.ok,
        "checks": report.checks,
        "errors": report.errors,
        "warnings": report.warnings,
        "notes": report.notes,
        "counts": actual_row_counts(dataset),
    }


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Static dataset validator (no simulation required).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="dataset directory")
    parser.add_argument(
        "--libero-home",
        type=Path,
        default=None,
        help="optional upstream LIBERO checkout; enables BDDL/init existence checks "
        "(defaults to $LIBERO_HOME when set)",
    )
    parser.add_argument("--json", type=Path, default=None, help="write a machine-readable report")
    parser.add_argument("--quiet", action="store_true", help="only print the final verdict")
    parser.add_argument(
        "--no-package-validation",
        action="store_true",
        help="skip the optional libero_rollback.validation hook (used by tests)",
    )
    parser.add_argument(
        "--strict-package-validation",
        action="store_true",
        help="make libero_rollback.validation errors fatal (default: advisory warnings)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    libero_home = args.libero_home
    if libero_home is None:
        env_home = os.environ.get("LIBERO_HOME")
        libero_home = Path(env_home) if env_home else None
    if libero_home is not None and not libero_home.is_dir():
        print(f"[validate_dataset] setup error: --libero-home is not a directory: {libero_home}")
        return 2
    report = validate(
        args.dataset,
        libero_home=libero_home,
        package_validation=not args.no_package_validation,
        strict_package=args.strict_package_validation,
    )
    if not args.quiet:
        print_report(report, args.dataset, libero_home)
    elif report.ok:
        print("[validate_dataset] OK")
    else:
        print(f"[validate_dataset] FAILED ({len(report.errors)} error(s))")
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = build_json_report(report, args.dataset, libero_home)
        args.json.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
