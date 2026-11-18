#!/usr/bin/env python3
"""Static validator for the LIBERO-Rollback ``dataset/`` tree.

The checks are deliberately **self-contained** (stdlib + PyYAML): they can run on
a CPU-only machine without MuJoCo, LIBERO or model weights.  When the package
module ``libero_rollback.validation`` is importable it is also invoked (see
``--package-validation``), but the inline checks remain the authoritative Phase-1
gate so this script and ``tests/test_dataset.py`` never depend on a concurrent
module implementation.

What is checked
---------------
* layout / encoding: every required file exists, UTF-8 without BOM, LF endings;
* matrix contracts (``docs/SPEC.md`` §3–§4): exact column sets, row counts,
  ``case_id`` naming, per-task C0 rules, level/param combinations, expected
  relation direction, A↔B task-key pairing, D-native window coverage;
* ``manifest.yaml`` (SPEC §8): schema version, dataset version, counts, per-file
  sha256 and row counts, executable/provisional splits, variance selection;
* ``lite.yaml`` (SPEC §10): 30 unique executable case ids with the required
  A/B/D coverage, consistent with ``manifest.splits.lite``;
* ``sources.yaml`` (SPEC §9): upstream pin, import sha256/row counts, A-matrix
  generation provenance;
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

MATRICES = ("a", "b", "d_native", "d_compose_provisional")
MATRIX_PATHS = {
    "a": "dataset/matrices/a-matrix.csv",
    "b": "dataset/matrices/b-matrix.csv",
    "d_native": "dataset/matrices/d-native-matrix.csv",
    "d_compose_provisional": "dataset/matrices/d-compose-provisional.csv",
}
EXECUTABLE = ("a", "b", "d_native")
EXPECTED_COUNTS = {"a": 40, "b": 442, "d_native": 189, "d_compose_provisional": 360, "c": 0}
EXPECTED_BY_SUITE = {"goal": 85, "object": 80, "spatial": 80, "l10": 197}
EXPECTED_B_BY_LEVEL = {"C0": 40, "L0": 60, "L1": 180, "L2": 162}
EXPECTED_D_NATIVE_TASKS = 9
LITE_COUNT = 30
VARIANCE_CASES = 100
VARIANCE_INIT_ROWS = [0, 1, 2, 3, 4]
LIBERO_REPO = "https://github.com/Lifelong-Robot-Learning/LIBERO"
LIBERO_COMMIT = "f78abd68ee283de9f9be3c8f7e2a9ad60246e95c"
DATASET_VERSION_FALLBACK = "2.0.0.dev0"

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
D_COLUMNS = (
    "case_id",
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
D_WINDOWS = frozenset({"early", "mid", "later", "all_done_control"})
PLACEHOLDER = "<from C>"
#: Legacy trigger labels carried by the frozen D-native rows (see dataset/README.md).
D_TRIGGER_LABELS = frozenset(
    {"s1 first true", "s2 displacement > 5 cm", "distance to s2 goal < 8 cm", "no injection"}
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
    "d": re.compile(r"^d-l10-t\d{3}-(c0|(early|mid|later)-(l0|l1-d(03|06|10)|l2-r(30|60|90)))$"),
    "d_compose": re.compile(r"^d-compose-s\d{4}-(early|mid|later)-l0$"),
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
    """Derive the SPEC §4 case id from the row fields (None where not derivable)."""

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
    if matrix == "d_native":
        base = f"d-l10-t{task_idx_of(row):03d}"
        window = row["window"].strip()
        if window == "all_done_control":
            return f"{base}-c0"
        level, param = level_key(row)
        suffix = level.lower()
        if param:
            suffix = f"{suffix}-{param}"
        return f"{base}-{window}-{suffix}"
    if matrix == "d_compose":
        level, param = level_key(row)
        suffix = level.lower()
        if param:
            suffix = f"{suffix}-{param}"
        return f"d-compose-{row['struct_id']}-{row['window']}-{suffix}"
    return None


def matrix_case_pattern(matrix: str):
    if matrix == "a":
        return CASE_ID_PATTERNS["a"]
    if matrix == "b":
        return CASE_ID_PATTERNS["b"]
    if matrix == "d_native":
        return CASE_ID_PATTERNS["d"]
    return CASE_ID_PATTERNS["d_compose"]


# ---------------------------------------------------------------------------
# Layout / encoding
# ---------------------------------------------------------------------------


def check_layout(report: Report, dataset: Path) -> None:
    required = [
        dataset / "matrices" / "a-matrix.csv",
        dataset / "matrices" / "b-matrix.csv",
        dataset / "matrices" / "d-native-matrix.csv",
        dataset / "matrices" / "d-compose-provisional.csv",
        dataset / "manifest.yaml",
        dataset / "lite.yaml",
        dataset / "sources.yaml",
        dataset / "README.md",
    ]
    for path in required:
        if not path.is_file():
            report.error(f"missing required file: {path}")
    if (dataset / "matrices" / "c-matrix.csv").exists():
        report.error(
            "dataset/matrices/c-matrix.csv exists but manifest.counts.c = 0; "
            "the C suite is Phase 2 — do not add a partial C matrix"
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
    expected = {
        "a": A_COLUMNS,
        "b": B_COLUMNS,
        "d_native": D_COLUMNS,
        "d_compose_provisional": D_COLUMNS,
    }
    for matrix, rel_path in MATRIX_PATHS.items():
        path = dataset.parent / rel_path
        if not path.is_file():
            continue
        header, rows = read_csv(path)
        if header != expected[matrix]:
            report.error(
                f"{rel_path}: header mismatch; expected "
                f"{list(expected[matrix])}, got {list(header)}"
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
    pattern = matrix_case_pattern(matrix)
    if pattern and not pattern.match(case_id):
        report.error(f"{rel_path}: case_id {case_id!r} does not match SPEC §4 naming")
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
                f"(LIBERO_HOME-relative, SPEC §2.3)"
            )


def check_b_matrix(report: Report, dataset: Path, seen: set[str]) -> tuple[dict, list[dict]]:
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
        suite = str(row.get("suite", "")).strip()
        if suite not in B_SUITES:
            report.error(f"{rel_path}: {case_id}: unknown suite {suite!r}")
        if row.get("target") not in B_TARGETS:
            report.error(f"{rel_path}: {case_id}: unknown target {row.get('target')!r}")
        if row.get("family") not in B_FAMILIES:
            report.error(f"{rel_path}: {case_id}: unknown family {row.get('family')!r}")
        if row.get("trigger") != "all_done":
            report.error(f"{rel_path}: {case_id}: B requires trigger=all_done")
        if str(row.get("delay_steps")) != "10" or str(row.get("repair_window")) != "300":
            report.error(f"{rel_path}: {case_id}: delay_steps must be 10 and repair_window 300")
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


def check_d_native_matrix(report: Report, dataset: Path, seen: set[str], b_by_task: dict) -> None:
    rel_path = MATRIX_PATHS["d_native"]
    path = dataset.parent / rel_path
    if not path.is_file():
        return
    _header, rows = read_csv(path)
    by_task: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        case_id = row.get("case_id", "?")
        _check_common_row(report, "d_native", rel_path, row, seen)
        _check_level_param(report, rel_path, row)
        _check_expected_relation(report, rel_path, row)
        if row.get("sub") != "native" or row.get("suite") != "l10":
            report.error(f"{rel_path}: {case_id}: expected sub=native, suite=l10")
        window = row.get("window", "")
        if window not in D_WINDOWS:
            report.error(f"{rel_path}: {case_id}: unknown window {window!r}")
        if row.get("target") != "s1":
            report.error(f"{rel_path}: {case_id}: D-native target must be 's1'")
        if row.get("trigger_criterion") not in D_TRIGGER_LABELS:
            report.error(
                f"{rel_path}: {case_id}: unexpected trigger_criterion "
                f"{row.get('trigger_criterion')!r}"
            )
        if str(row.get("max_steps")) != "800" or str(row.get("repair_window")) != "300":
            report.error(f"{rel_path}: {case_id}: D-native needs max_steps=800, repair_window=300")
        if row.get("s2_must_stay_true") not in {"true", "false"}:
            report.error(f"{rel_path}: {case_id}: s2_must_stay_true must be true/false")
        if window == "all_done_control":
            if row.get("level") != "C0" or row.get("semantics") != "relation_holds_control":
                report.error(
                    f"{rel_path}: {case_id}: all_done_control must be C0 relation_holds_control"
                )
        elif row.get("semantics") != "relation_then_resume":
            report.error(
                f"{rel_path}: {case_id}: D-native rollback semantics must be relation_then_resume"
            )
        by_task.setdefault(task_idx_of(row), []).append(row)
    if len(by_task) != EXPECTED_D_NATIVE_TASKS:
        report.error(
            f"{rel_path}: expected {EXPECTED_D_NATIVE_TASKS} native tasks, found {len(by_task)}"
        )
    for task_idx, task_rows in by_task.items():
        if ("l10", task_idx) not in b_by_task:
            report.error(
                f"{rel_path}: D-native task l10/t{task_idx:03d} has no B-matrix l10 task key"
            )
        windows = {row["window"] for row in task_rows}
        missing = D_WINDOWS - windows
        if missing:
            report.error(f"{rel_path}: task l10/t{task_idx:03d} misses windows {sorted(missing)}")
        controls = [row for row in task_rows if row["window"] == "all_done_control"]
        if len(controls) != 1:
            report.error(
                f"{rel_path}: task l10/t{task_idx:03d}: exactly one all_done_control required"
            )
        expected_levels = {row["level"] for row in task_rows if row["window"] != "all_done_control"}
        for level in ("L0", "L1"):
            if level not in expected_levels:
                report.error(f"{rel_path}: task l10/t{task_idx:03d}: missing {level} family")
        b_instruction = None
        for b_row in b_by_task.get(("l10", task_idx), []):
            b_instruction = b_row["instruction"]
            break
        if b_instruction is not None and row_instruction(task_rows) != b_instruction:
            report.error(
                f"{rel_path}: task l10/t{task_idx:03d}: instruction differs from the B l10 task"
            )


def row_instruction(rows: list[dict[str, str]]) -> str | None:
    values = {row.get("instruction", "") for row in rows}
    return values.pop() if len(values) == 1 else None


def check_d_compose_matrix(report: Report, dataset: Path, seen: set[str]) -> None:
    rel_path = MATRIX_PATHS["d_compose_provisional"]
    path = dataset.parent / rel_path
    if not path.is_file():
        return
    _header, rows = read_csv(path)
    by_struct: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        case_id = row.get("case_id", "?")
        _check_common_row(report, "d_compose", rel_path, row, seen)
        _check_expected_relation(report, rel_path, row)
        if row.get("sub") != "compose" or row.get("suite") != "compose":
            report.error(f"{rel_path}: {case_id}: expected sub=compose, suite=compose")
        if str(row.get("task_idx", "")).strip():
            report.error(
                f"{rel_path}: {case_id}: provisional D-compose rows must leave task_idx empty"
            )
        if row.get("level") != "L0" or str(row.get("param", "")).strip():
            report.error(
                f"{rel_path}: {case_id}: provisional D-compose rows must be L0 without param"
            )
        if str(row.get("max_steps")) != "600" or str(row.get("repair_window")) != "300":
            report.error(f"{rel_path}: {case_id}: D-compose needs max_steps=600, repair_window=300")
        for field in ("instruction", "revoked_predicate", "revoked_object"):
            if str(row.get(field, "")).strip() != PLACEHOLDER:
                report.error(
                    f"{rel_path}: {case_id}: {field} must stay the explicit placeholder "
                    f"{PLACEHOLDER!r} until the C suite exists"
                )
        window = row.get("window", "")
        if D_COMPOSE_TRIGGERS.get(window) != row.get("trigger_criterion"):
            report.error(
                f"{rel_path}: {case_id}: trigger_criterion {row.get('trigger_criterion')!r} "
                f"does not match the frozen legacy label for window {window!r}"
            )
        if row.get("target") != "s1":
            report.error(f"{rel_path}: {case_id}: D-compose target must be 's1'")
        by_struct.setdefault(row.get("struct_id", ""), []).append(row)
    if len(by_struct) != 120:
        report.error(f"{rel_path}: expected 120 provisional structures, found {len(by_struct)}")
    for struct_id, struct_rows in by_struct.items():
        if not re.fullmatch(r"s\d{4}", struct_id):
            report.error(f"{rel_path}: bad struct_id {struct_id!r}")
        windows = sorted(row["window"] for row in struct_rows)
        if windows != ["early", "later", "mid"]:
            report.error(
                f"{rel_path}: structure {struct_id}: expected early/mid/later, got {windows}"
            )


# ---------------------------------------------------------------------------
# Cross-matrix contracts
# ---------------------------------------------------------------------------


def check_cross_matrix(report: Report, dataset: Path) -> None:
    a_path = dataset.parent / MATRIX_PATHS["a"]
    b_path = dataset.parent / MATRIX_PATHS["b"]
    if not (a_path.is_file() and b_path.is_file()):
        return
    _a_header, a_rows = read_csv(a_path)
    _b_header, b_rows = read_csv(b_path)
    b_tasks = {(row["suite"], task_idx_of(row)): row for row in b_rows}
    a_tasks = {(row["suite"], task_idx_of(row)): row for row in a_rows}
    if set(a_tasks) != set(b_tasks):
        only_a = sorted(set(a_tasks) - set(b_tasks))
        only_b = sorted(set(b_tasks) - set(a_tasks))
        report.error(f"A↔B task keys differ: only in A={only_a}, only in B={only_b}")
    for task_key in sorted(set(a_tasks) & set(b_tasks)):
        a_row, b_row = a_tasks[task_key], b_tasks[task_key]
        for field in ("bddl_name", "instruction"):
            if a_row.get(field) != b_row.get(field):
                report.error(
                    f"A↔B pairing broken for {task_key}: A.{field}={a_row.get(field)!r} "
                    f"but B.{field}={b_row.get(field)!r}"
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
    counts["c"] = 0
    return counts


def executable_case_ids(dataset: Path) -> set[str]:
    ids: set[str] = set()
    for matrix in EXECUTABLE:
        path = dataset.parent / MATRIX_PATHS[matrix]
        if path.is_file():
            _header, rows = read_csv(path)
            ids.update(row["case_id"] for row in rows)
    return ids


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
    if manifest.get("schema_version") != 2:
        report.error(
            f"manifest.yaml: schema_version must be 2, got {manifest.get('schema_version')!r}"
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
    for matrix, rel_path in MATRIX_PATHS.items():
        if rel_path not in listed:
            report.error(f"manifest.yaml: missing required matrix entry {rel_path}")

    provisional = manifest.get("provisional")
    if not isinstance(provisional, list):
        report.error("manifest.yaml: provisional must be a list")
    else:
        provisional_paths = set()
        for entry in provisional:
            if not isinstance(entry, dict) or "path" not in entry:
                report.error(
                    f"manifest.yaml: provisional entry must be a mapping with a path: {entry!r}"
                )
                continue
            rel_path = str(entry["path"])
            provisional_paths.add(rel_path)
            file_path = dataset.parent / rel_path
            if not file_path.is_file():
                report.error(f"manifest.yaml: provisional path does not exist: {rel_path}")
                continue
            if entry.get("sha256") != sha256_file(file_path):
                report.error(f"manifest.yaml: provisional {rel_path}: sha256 does not match")
            _header, rows = read_csv(file_path)
            if entry.get("rows") != len(rows):
                report.error(f"manifest.yaml: provisional {rel_path}: rows != {len(rows)}")
        if not provisional_paths:
            report.error("manifest.yaml: provisional must list d-compose-provisional.csv")
        for matrix in EXECUTABLE:
            if MATRIX_PATHS[matrix] in provisional_paths:
                report.error(
                    f"manifest.yaml: executable matrix {MATRIX_PATHS[matrix]} "
                    "must not be provisional"
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
    core = splits.get("core")
    if core != ["a", "b", "d-native"]:
        report.error(f"manifest.yaml: splits.core must be ['a','b','d-native'], got {core!r}")
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
    c_entry = manifest.get("c") or {}
    if not isinstance(c_entry, dict) or c_entry.get("status") != "not_built":
        report.error("manifest.yaml: c.status must be 'not_built' in Phase 1")


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
    if payload.get("schema_version") != 1:
        report.error(f"lite.yaml: schema_version must be 1, got {payload.get('schema_version')!r}")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not all(isinstance(case_id, str) for case_id in cases):
        report.error("lite.yaml: cases must be a list of case-id strings")
        return
    if len(cases) != LITE_COUNT:
        report.error(f"lite.yaml: expected {LITE_COUNT} cases, found {len(cases)}")
    if len(set(cases)) != len(cases):
        report.error("lite.yaml: duplicate case ids")
    executable = executable_case_ids(dataset)
    unknown = [case_id for case_id in cases if case_id not in executable]
    if unknown:
        report.error(f"lite.yaml: ids not found in the executable matrices: {unknown[:10]}")
    splits = payload.get("splits") or {}
    if not isinstance(splits, dict) or set(splits) != {"a", "b", "d_native"}:
        report.error("lite.yaml: splits must contain exactly a/b/d_native")
    else:
        union: list[str] = []
        for key, wanted in (("a", 10), ("b", 10), ("d_native", 10)):
            group = splits.get(key)
            if not isinstance(group, list) or len(group) != wanted:
                report.error(f"lite.yaml: splits.{key} must contain {wanted} case ids")
                continue
            union.extend(group)
        if sorted(union) != sorted(cases):
            report.error("lite.yaml: splits a/b/d_native union does not equal cases")
    coverage = payload.get("coverage") or {}
    a_suites = coverage.get("a_suites") or {}
    if set(a_suites) != set(SUITE_DIRS) or any(not 2 <= int(n) <= 3 for n in a_suites.values()):
        report.error("lite.yaml: coverage.a_suites must cover all four suites with 2-3 cases each")
    if set(coverage.get("b_levels") or {}) != {"C0", "L0", "L1", "L2"}:
        report.error("lite.yaml: coverage.b_levels must cover C0/L0/L1/L2")
    if set(coverage.get("b_suites") or {}) != set(B_SUITES):
        report.error("lite.yaml: coverage.b_suites must cover goal/object/spatial/l10")
    if set(coverage.get("d_windows") or {}) != D_WINDOWS:
        report.error("lite.yaml: coverage.d_windows must cover all_done_control/early/mid/later")


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
        report.error("sources.yaml: upstream repo/commit must pin the LIBERO commit in SPEC §2.1")
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
        if MATRIX_PATHS[matrix] not in targets:
            report.error(f"sources.yaml: missing import entry for {MATRIX_PATHS[matrix]}")
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
                if token in lowered:
                    report.error(
                        f"{rel_path}: precursor-repository reference {token!r} is not allowed "
                        "inside dataset/ (see SPEC §9.1/§10.2)"
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
    a_path = dataset.parent / MATRIX_PATHS["a"]
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
    b_path = dataset.parent / MATRIX_PATHS["b"]
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
    except Exception as error:  # noqa: BLE001 - module may be absent during M1 migration
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
    b_by_task = report.check("b_matrix", check_b_matrix, dataset, seen)[0]
    report.check("d_native_matrix", check_d_native_matrix, dataset, seen, b_by_task)
    report.check("d_compose_matrix", check_d_compose_matrix, dataset, seen)
    report.check("cross_matrix", check_cross_matrix, dataset)
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
    summary = " ".join(f"{key}={counts.get(key, '?')}" for key in MATRICES)
    print(f"[validate_dataset] dataset: {dataset}")
    print(f"[validate_dataset] rows: {summary} c=0")
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
