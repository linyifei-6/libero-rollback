"""Integrity tests for the schema-v3 ``dataset/`` tree.

These tests need **no simulation, no GPU and no LIBERO checkout**: they only read
the frozen CSVs/YAMLs and run the static scripts.  They are intentionally written
against the files (not against ``scripts/validate_dataset.py`` internals) so a
bug in the validator cannot hide a data defect.

Schema v3 (2026-11-21) is the base-only test-suite tree::

    a           a-matrix.csv                              40
    b           libero-rollback/completion-rollback.csv   442
    c           libero-rollback/in-execution-rollback.csv 180
    d_intact    libero-compose/intact.csv                 176
    d_rollback  libero-compose/rollback.csv               528

The legacy ``b-matrix.csv`` / ``d-native-matrix.csv`` /
``d-compose-provisional.csv`` files stay on disk untouched but are never part
of an executable split.

Run with::

    python -m pytest tests/test_dataset.py
"""

from __future__ import annotations

import csv
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET = REPO_ROOT / "dataset"
MATRICES = DATASET / "matrices"

A_ROWS = 40
B_ROWS = 442
C_ROWS = 180
D_INTACT_ROWS = 176
D_ROLLBACK_ROWS = 528
LITE_ROWS = 30
VARIANCE_CASES = 100
LITE_GROUPS = {"a": 10, "b": 10, "c": 5, "d_intact": 2, "d_rollback": 3}

A_PATH = MATRICES / "a-matrix.csv"
B_PATH = MATRICES / "libero-rollback" / "completion-rollback.csv"
C_PATH = MATRICES / "libero-rollback" / "in-execution-rollback.csv"
D_INTACT_PATH = MATRICES / "libero-compose" / "intact.csv"
D_ROLLBACK_PATH = MATRICES / "libero-compose" / "rollback.csv"

LEGACY_B = MATRICES / "b-matrix.csv"
LEGACY_D_NATIVE = MATRICES / "d-native-matrix.csv"
LEGACY_D_COMPOSE = MATRICES / "d-compose-provisional.csv"
CANONICAL_PATHS = (
    "dataset/matrices/a-matrix.csv",
    "dataset/matrices/libero-rollback/completion-rollback.csv",
    "dataset/matrices/libero-rollback/in-execution-rollback.csv",
    "dataset/matrices/libero-compose/intact.csv",
    "dataset/matrices/libero-compose/rollback.csv",
)
LEGACY_PATHS = (
    "dataset/matrices/b-matrix.csv",
    "dataset/matrices/d-native-matrix.csv",
    "dataset/matrices/d-compose-provisional.csv",
)

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

CASE_ID_RE = {
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


def read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        return tuple(reader.fieldnames or ()), list(reader)


def read_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def b_tasks(rows: list[dict[str, str]]) -> dict[tuple[str, int], list[dict[str, str]]]:
    tasks: dict[tuple[str, int], list[dict[str, str]]] = {}
    for row in rows:
        tasks.setdefault((row["suite"], int(row["task_idx"])), []).append(row)
    return tasks


@pytest.fixture(scope="module")
def a_matrix() -> tuple[tuple[str, ...], list[dict[str, str]]]:
    return read_csv(A_PATH)


@pytest.fixture(scope="module")
def b_matrix() -> tuple[tuple[str, ...], list[dict[str, str]]]:
    return read_csv(B_PATH)


@pytest.fixture(scope="module")
def c_matrix() -> tuple[tuple[str, ...], list[dict[str, str]]]:
    return read_csv(C_PATH)


@pytest.fixture(scope="module")
def d_intact_matrix() -> tuple[tuple[str, ...], list[dict[str, str]]]:
    return read_csv(D_INTACT_PATH)


@pytest.fixture(scope="module")
def d_rollback_matrix() -> tuple[tuple[str, ...], list[dict[str, str]]]:
    return read_csv(D_ROLLBACK_PATH)


# ---------------------------------------------------------------------------
# Layout / encoding
# ---------------------------------------------------------------------------


def test_required_files_exist() -> None:
    for rel_path in (
        *CANONICAL_PATHS,
        *LEGACY_PATHS,
        "dataset/manifest.yaml",
        "dataset/lite.yaml",
        "dataset/sources.yaml",
        "dataset/README.md",
    ):
        assert (REPO_ROOT / rel_path).is_file(), f"missing {rel_path}"
    assert (DATASET / "compose" / "bddl").is_dir(), "D-compose definitions must be built"
    assert not (MATRICES / "c-matrix.csv").exists(), "C is the in-execution suite view"


def test_rows_are_utf8_lf_without_bom() -> None:
    for path in sorted(DATASET.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".csv", ".yaml", ".yml", ".md"}:
            continue
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{path}: BOM found"
        assert b"\r" not in raw, f"{path}: CR line ending found"
        raw.decode("utf-8")  # raises on invalid UTF-8
        if path.suffix.lower() == ".csv":
            assert raw.endswith(b"\n"), f"{path}: CSV must end with LF"


def test_matrix_headers_and_counts(
    a_matrix, b_matrix, c_matrix, d_intact_matrix, d_rollback_matrix
) -> None:
    assert a_matrix[0] == A_COLUMNS
    assert b_matrix[0] == B_COLUMNS
    assert c_matrix[0] == C_COLUMNS
    assert d_intact_matrix[0] == D_INTACT_COLUMNS
    assert d_rollback_matrix[0] == D_ROLLBACK_COLUMNS
    assert len(a_matrix[1]) == A_ROWS
    assert len(b_matrix[1]) == B_ROWS
    assert len(c_matrix[1]) == C_ROWS
    assert len(d_intact_matrix[1]) == D_INTACT_ROWS
    assert len(d_rollback_matrix[1]) == D_ROLLBACK_ROWS


def test_case_ids_unique_and_well_formed(
    a_matrix, b_matrix, c_matrix, d_intact_matrix, d_rollback_matrix
) -> None:
    groups = {
        "a": a_matrix[1],
        "b": b_matrix[1],
        "c": c_matrix[1],
        "d_intact": d_intact_matrix[1],
        "d_rollback": d_rollback_matrix[1],
    }
    seen: set[str] = set()
    for matrix, rows in groups.items():
        for row in rows:
            case_id = row["case_id"]
            assert CASE_ID_RE[matrix].match(case_id), f"{matrix}: bad case id {case_id!r}"
            assert case_id not in seen, f"duplicate case id across matrices: {case_id}"
            seen.add(case_id)


def test_legacy_files_are_retained_but_not_executable() -> None:
    assert len(read_csv(LEGACY_B)[1]) == 442
    assert len(read_csv(LEGACY_D_NATIVE)[1]) == 189
    assert len(read_csv(LEGACY_D_COMPOSE)[1]) == 360
    manifest = read_yaml(DATASET / "manifest.yaml")
    assert set(manifest["legacy"]["files"]) == set(LEGACY_PATHS)
    assert set(manifest["legacy"]["counts"].items()) == {
        ("b", 442),
        ("d_native", 189),
        ("d_compose_provisional", 360),
    }
    executable = {entry["path"] for entry in manifest["files"]}
    assert not (set(LEGACY_PATHS) & executable)


# ---------------------------------------------------------------------------
# A matrix
# ---------------------------------------------------------------------------


def test_a_matrix_is_one_row_per_b_task(a_matrix, b_matrix) -> None:
    _header, a_rows = a_matrix
    _b_header, b_rows = b_matrix
    a_tasks = {(row["suite"], int(row["task_idx"])): row for row in a_rows}
    b_tasks_by_key: dict[tuple[str, int], dict[str, str]] = {}
    for row in b_rows:
        b_tasks_by_key.setdefault((row["suite"], int(row["task_idx"])), row)
    assert set(a_tasks) == set(b_tasks_by_key)
    assert len(a_tasks) == 40
    for key, a_row in a_tasks.items():
        b_row = b_tasks_by_key[key]
        assert a_row["bddl_name"] == b_row["bddl_name"], key
        assert a_row["instruction"] == b_row["instruction"], key
        expected_init = (
            f"libero/libero/init_files/{SUITE_DIRS[key[0]]}/{a_row['bddl_name']}.pruned_init"
        )
        assert a_row["init_source"] == expected_init, key
        assert a_row["semantics"] == "intact"
        assert a_row["max_steps"] == "600"
        assert int(a_row["n_goals"]) >= 1
        assert a_row["case_id"] == f"a-{key[0]}-t{key[1]:03d}"


# ---------------------------------------------------------------------------
# B (completion rollback) matrix contracts
# ---------------------------------------------------------------------------


def test_b_has_exactly_one_c0_per_task_with_correct_semantics(b_matrix) -> None:
    _header, rows = b_matrix
    tasks = b_tasks(rows)
    assert len(tasks) == 40
    for key, task_rows in tasks.items():
        controls = [row for row in task_rows if row["level"] == "C0"]
        assert len(controls) == 1, f"{key}: {len(controls)} C0 rows"
        control = controls[0]
        assert control["target"] == "c0"
        assert control["revoked_objects"] == ""
        assert control["revoked_predicates"] == ""
        assert control["expected_relation_after"] == "true"
        for row in task_rows:
            if row["level"] == "C0":
                continue
            assert row["expected_relation_after"] == "false", row["case_id"]
            assert row["revoked_objects"], row["case_id"]
            assert row["revoked_predicates"], row["case_id"]


def test_b_suite_and_level_counts_match_spec(b_matrix) -> None:
    _header, rows = b_matrix
    suites: dict[str, int] = {}
    levels: dict[str, int] = {}
    for row in rows:
        suites[row["suite"]] = suites.get(row["suite"], 0) + 1
        levels[row["level"]] = levels.get(row["level"], 0) + 1
    assert suites == {"goal": 85, "object": 80, "spatial": 80, "l10": 197}
    assert levels == {"C0": 40, "L0": 60, "L1": 180, "L2": 162}


def test_b_level_param_combinations_are_valid(b_matrix) -> None:
    _header, rows = b_matrix
    valid = {
        ("C0", ""),
        ("L0", ""),
        ("L1", "d03"),
        ("L1", "d06"),
        ("L1", "d10"),
        ("L2", "r30"),
        ("L2", "r60"),
        ("L2", "r90"),
    }
    for row in rows:
        assert (row["level"], row["param"]) in valid, row["case_id"]
        assert row["trigger"] == "all_done"
        assert row["delay_steps"] == "10"
        assert row["repair_window"] == "600"
        assert row["test_suite"] == "libero-rollback"
        assert row["dimension"] == "completion"
        assert row["arm"] == ("control" if row["level"] == "C0" else "rollback")


# ---------------------------------------------------------------------------
# C (in-execution rollback) matrix contracts
# ---------------------------------------------------------------------------


def test_c_suite_contract(c_matrix, b_matrix) -> None:
    _header, rows = c_matrix
    _b_header, b_rows = b_matrix
    b_l10 = {
        int(row["task_idx"]): row
        for row in b_rows
        if row["suite"] == "l10"
    }
    tasks: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        assert row["test_suite"] == "libero-rollback"
        assert row["dimension"] == "in-execution"
        assert row["arm"] == "rollback"
        assert row["sub"] == "native"
        assert row["suite"] == "l10"
        assert row["target"] == "s1"
        assert row["max_steps"] == "800"
        assert row["repair_window"] == "600"
        assert row["expected_relation_after"] == "false"
        assert row["window"] in {"early", "mid", "later"}
        assert row["window"] != "all_done_control"
        assert row["level"] in {"L0", "L1", "L2"}
        assert row["level"] != "C0"
        assert row["trigger_criterion"] in {
            "s1 first true",
            "s2 displacement > 5 cm",
            "distance to s2 goal < 8 cm",
        }
        assert row["instruction"] == b_l10[int(row["task_idx"])]["instruction"]
        tasks.setdefault(int(row["task_idx"]), []).append(row)
    assert len(tasks) == 9
    assert {row["task_idx"] for row in rows} == {
        "0",
        "33",
        "78",
        "133",
        "137",
        "145",
        "158",
        "193",
        "237",
    }
    for task_idx, task_rows in tasks.items():
        assert {row["window"] for row in task_rows} == {"early", "mid", "later"}
        for window in ("early", "mid", "later"):
            expected = 4 if task_idx == 0 else 7
            assert (
                sum(1 for row in task_rows if row["window"] == window) == expected
            ), (task_idx, window)


def test_c_suite_is_the_legacy_native_rows_without_controls(c_matrix) -> None:
    _header, legacy_rows = read_csv(LEGACY_D_NATIVE)
    _header, rows = c_matrix
    expected_ids = {
        row["case_id"] for row in legacy_rows if row["window"] != "all_done_control"
    }
    assert {row["case_id"] for row in rows} == expected_ids
    assert len(expected_ids) == 180


# ---------------------------------------------------------------------------
# D (compose) matrices
# ---------------------------------------------------------------------------


def test_d_intact_contract(d_intact_matrix) -> None:
    _header, rows = d_intact_matrix
    structs: set[str] = set()
    for row in rows:
        assert row["test_suite"] == "compose"
        assert row["dimension"] == "intact"
        assert row["arm"] == "intact"
        assert row["sub"] == "compose"
        assert row["suite"] == "compose"
        assert row["level"] == "INTACT"
        assert row["param"] == ""
        assert row["n_atoms"] == "2"
        assert row["valid"] == "true"
        assert row["repair_window"] == "0"
        assert row["expected_relation_after"] == "true"
        assert row["goal_atoms"].count("|") == 1
        structs.add(row["struct_id"])
    assert len(structs) == 176


def test_d_rollback_contract(d_rollback_matrix) -> None:
    _header, rows = d_rollback_matrix
    structs: set[str] = set()
    for row in rows:
        assert row["test_suite"] == "compose"
        assert row["dimension"] == "in-execution"
        assert row["arm"] == "rollback"
        assert row["sub"] == "compose"
        assert row["suite"] == "compose"
        assert row["level"] == "L0"
        assert row["param"] == ""
        assert row["window"] in {"early", "mid", "later"}
        assert row["target"] == "s1"
        assert row["repair_window"] == "600"
        assert row["valid"] == "true"
        assert row["expected_relation_after"] == "false"
        assert row["s2_must_stay_true"] == "true"
        structs.add(row["struct_id"])
    assert len(structs) == 176
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row["struct_id"], row["window"])
        counts[key] = counts.get(key, 0) + 1
    assert len(counts) == 176 * 3
    assert all(count == 1 for count in counts.values())


def test_d_rollback_struct_ids_match_intact(d_intact_matrix, d_rollback_matrix) -> None:
    assert {row["struct_id"] for row in d_intact_matrix[1]} == {
        row["struct_id"] for row in d_rollback_matrix[1]
    }


def test_d_assets_exist_and_match_hashes(d_intact_matrix) -> None:
    root = DATASET / "compose" / "bddl"
    for row in d_intact_matrix[1]:
        task_id = row["task_id"]
        bddl = root / f"{task_id}.bddl"
        init = root / f"{task_id}.pruned_init"
        assert bddl.is_file(), bddl
        assert init.is_file(), init
        assert sha256_of(bddl) == row["bddl_sha256"]
        assert sha256_of(init) == row["pruned_init_sha256"]


def test_legacy_provisional_compose_is_not_executable() -> None:
    _header, rows = read_csv(LEGACY_D_COMPOSE)
    assert len(rows) == 360
    assert {row["instruction"] for row in rows} == {"<from C>"}
    manifest = read_yaml(DATASET / "manifest.yaml")
    lite = read_yaml(DATASET / "lite.yaml")
    assert "provisional" not in manifest or not manifest["provisional"]
    legacy_ids = {row["case_id"] for row in rows}
    assert not (legacy_ids & set(lite["cases"]))
    assert "dataset/matrices/d-compose-provisional.csv" not in manifest["splits"]["core"]


# ---------------------------------------------------------------------------
# manifest / lite / sources
# ---------------------------------------------------------------------------


def test_manifest_schema_and_counts() -> None:
    manifest = read_yaml(DATASET / "manifest.yaml")
    assert manifest["schema_version"] == 3
    assert manifest["generated_by"] == "scripts/build_manifest.py"
    assert manifest["dataset_version"]
    assert manifest["libero"]["commit"] == "f78abd68ee283de9f9be3c8f7e2a9ad60246e95c"
    assert manifest["counts"] == {
        "a": 40,
        "b": 442,
        "c": 180,
        "d_intact": 176,
        "d_rollback": 528,
    }
    assert "c" not in manifest, "the old C status block is superseded by counts.c"
    assert "provisional" not in manifest or not manifest["provisional"]


def test_manifest_sha256_and_rows_match_files() -> None:
    manifest = read_yaml(DATASET / "manifest.yaml")
    listed = {entry["path"] for entry in manifest["files"]}
    assert listed == set(CANONICAL_PATHS)
    for entry in manifest["files"]:
        path = REPO_ROOT / entry["path"]
        assert path.is_file(), entry["path"]
        assert sha256_of(path) == entry["sha256"], entry["path"]
        _header, rows = read_csv(path)
        assert len(rows) == entry["rows"], entry["path"]
    for rel_path in LEGACY_PATHS:
        assert (REPO_ROOT / rel_path).is_file(), rel_path


def test_manifest_splits() -> None:
    manifest = read_yaml(DATASET / "manifest.yaml")
    lite_payload = read_yaml(DATASET / "lite.yaml")
    splits = manifest["splits"]
    assert splits["core"] == ["a", "b", "c", "d_intact", "d_rollback"]
    assert len(splits["lite"]) == LITE_ROWS
    assert set(splits["lite"]) == set(lite_payload["cases"])
    variance = splits["variance"]
    assert variance["init_rows"] == [0, 1, 2, 3, 4]
    assert len(variance["cases"]) == VARIANCE_CASES
    assert len(set(variance["cases"])) == VARIANCE_CASES
    executable: set[str] = set()
    for rel_path in CANONICAL_PATHS:
        _header, rows = read_csv(REPO_ROOT / rel_path)
        executable.update(row["case_id"] for row in rows)
    assert set(variance["cases"]) <= executable
    for rel_path in LEGACY_PATHS:
        assert rel_path not in splits["core"]


def test_lite_split_covers_the_required_axes() -> None:
    lite = read_yaml(DATASET / "lite.yaml")
    assert lite["schema_version"] == 2
    cases = lite["cases"]
    assert len(cases) == LITE_ROWS
    assert len(set(cases)) == LITE_ROWS
    all_ids: dict[str, dict[str, str]] = {}
    for rel_path in CANONICAL_PATHS:
        _header, rows = read_csv(REPO_ROOT / rel_path)
        for row in rows:
            all_ids[row["case_id"]] = row
    assert set(cases) <= set(all_ids)

    groups = lite["splits"]
    assert set(groups) == set(LITE_GROUPS)
    assert {key: len(value) for key, value in groups.items()} == LITE_GROUPS
    assert sorted(cases) == sorted(case_id for value in groups.values() for case_id in value)

    for case_id in groups["c"]:
        row = all_ids[case_id]
        assert row["level"] != "C0"
        assert row["window"] != "all_done_control"
    for case_id in groups["d_intact"]:
        row = all_ids[case_id]
        assert row["valid"] == "true"
        assert row["n_atoms"] == "2"
    for case_id in groups["d_rollback"]:
        assert all_ids[case_id]["window"] in {"early", "mid", "later"}

    coverage = lite["coverage"]
    assert coverage["total"] == 30
    assert coverage["b_levels"] == {"C0": 4, "L0": 2, "L1": 2, "L2": 2}
    assert set(coverage["b_suites"]) == {"goal", "object", "spatial", "l10"}
    assert set(coverage["c_windows"]) == {"early", "mid", "later"}
    assert set(coverage["c_levels"]) == {"L0", "L1", "L2"}
    assert set(coverage["d_rollback_windows"]) == {"early", "mid", "later"}
    assert sum(coverage["a_suites"].values()) == 10


def test_sources_hashes_match_imported_files() -> None:
    sources = read_yaml(DATASET / "sources.yaml")
    assert sources["upstream"]["commit"] == "f78abd68ee283de9f9be3c8f7e2a9ad60246e95c"
    assert sources["imports"]
    for entry in sources["imports"]:
        path = REPO_ROOT / entry["target"]
        assert path.is_file(), entry["target"]
        assert sha256_of(path) == entry["sha256"], entry["target"]
        _header, rows = read_csv(path)
        assert len(rows) == entry["rows"], entry["target"]
    generated = {entry["target"] for entry in sources["generated"]}
    assert "dataset/matrices/a-matrix.csv" in generated


def test_dataset_has_no_absolute_host_paths() -> None:
    # Generic path-shape patterns (built from shapes, not host-specific literals):
    # POSIX absolute path, Windows drive path, UNC path, home-dir tilde path.
    patterns = (
        re.compile(r"(?<![:\w/$.~])/(?:[A-Za-z0-9_.-]+/)+"),
        re.compile(r"(?<![\w.])[A-Za-z]:[\\/]"),
        re.compile(r"\\\\[A-Za-z0-9_.-]+[\\/]"),
        re.compile(r"(?:^|[\s\"')(=:])~(?:/|\s|$)"),
    )
    for path in sorted(DATASET.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {
            ".csv",
            ".yaml",
            ".yml",
            ".md",
            ".json",
        }:
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            match = pattern.search(text)
            assert match is None, f"{path}: looks like an absolute host path: {match.group(0)!r}"
        if path.name != "sources.yaml":
            lowered = text.lower()
            for token in ("libero_compose", "libero_runtime", "libero-runtime"):
                assert token not in lowered, f"{path}: precursor reference {token!r}"
            # The D-compose directory legitimately contains the phrase; only
            # standalone (runtime/precursor) references are forbidden.
            stripped = lowered.replace("dataset/matrices/libero-compose/", "")
            assert "libero-compose" not in stripped, f"{path}: precursor reference"


# ---------------------------------------------------------------------------
# Scripts (subprocess, no simulation)
# ---------------------------------------------------------------------------


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def test_validate_dataset_script_passes() -> None:
    result = run_script(
        "scripts/validate_dataset.py", "--dataset", "dataset", "--no-package-validation"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_build_manifest_check_is_reproducible() -> None:
    result = run_script("scripts/build_manifest.py", "--check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_validator_rejects_tampered_manifest(tmp_path) -> None:
    tampered_root = tmp_path / "repo"
    shutil.copytree(DATASET, tampered_root / "dataset")
    manifest_path = tampered_root / "dataset" / "manifest.yaml"
    manifest_text = manifest_path.read_text(encoding="utf-8")
    tampered = re.sub(
        r'sha256: "[0-9a-f]{64}"',
        'sha256: "' + "0" * 64 + '"',
        manifest_text,
        count=1,
    )
    assert tampered != manifest_text
    manifest_path.write_text(tampered, encoding="utf-8")
    result = run_script(
        "scripts/validate_dataset.py",
        "--dataset",
        str(tampered_root / "dataset"),
        "--no-package-validation",
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "sha256" in result.stdout.lower()


def test_build_a_matrix_check_when_clean_libero_cache_is_present() -> None:
    cache = REPO_ROOT / ".cache" / "libero-src"
    if not (cache / "libero" / "libero" / "bddl_files").is_dir():
        pytest.skip("clean LIBERO HEAD extraction (.cache/libero-src) is not available")
    result = run_script("scripts/build_a_matrix.py", "--libero-home", str(cache), "--check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
