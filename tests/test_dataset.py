"""Integrity tests for the Phase-1 ``dataset/`` tree.

These tests need **no simulation, no GPU and no LIBERO checkout**: they only read
the frozen CSVs/YAMLs and run the static scripts.  They are intentionally written
against the files (not against ``scripts/validate_dataset.py`` internals) so a
bug in the validator cannot hide a data defect, and a concurrent change to
``libero_rollback.validation`` cannot break them (the CLI test passes
``--no-package-validation``).

Run with::

    python -m pytest tests/test_dataset.py
"""

from __future__ import annotations

import csv
import hashlib
import re
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
D_NATIVE_ROWS = 189
D_COMPOSE_ROWS = 360
LITE_ROWS = 30
VARIANCE_CASES = 100

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

CASE_ID_RE = {
    "a": re.compile(r"^a-(goal|object|spatial|l10)-t\d{3}$"),
    "b": re.compile(
        r"^b-(goal|object|spatial|l10)-t\d{3}-"
        r"(c0|(g|s1|s2|both|pre)-(l0|l1-d(03|06|10)|l2-r(30|60|90)))$"
    ),
    "d_native": re.compile(
        r"^d-l10-t\d{3}-(c0|(early|mid|later)-(l0|l1-d(03|06|10)|l2-r(30|60|90)))$"
    ),
    "d_compose": re.compile(r"^d-compose-s\d{4}-(early|mid|later)-l0$"),
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
    return read_csv(MATRICES / "a-matrix.csv")


@pytest.fixture(scope="module")
def b_matrix() -> tuple[tuple[str, ...], list[dict[str, str]]]:
    return read_csv(MATRICES / "b-matrix.csv")


@pytest.fixture(scope="module")
def d_native_matrix() -> tuple[tuple[str, ...], list[dict[str, str]]]:
    return read_csv(MATRICES / "d-native-matrix.csv")


@pytest.fixture(scope="module")
def d_compose_matrix() -> tuple[tuple[str, ...], list[dict[str, str]]]:
    return read_csv(MATRICES / "d-compose-provisional.csv")


# ---------------------------------------------------------------------------
# Layout / encoding
# ---------------------------------------------------------------------------


def test_required_files_exist() -> None:
    for rel_path in (
        "dataset/matrices/a-matrix.csv",
        "dataset/matrices/b-matrix.csv",
        "dataset/matrices/d-native-matrix.csv",
        "dataset/matrices/d-compose-provisional.csv",
        "dataset/manifest.yaml",
        "dataset/lite.yaml",
        "dataset/sources.yaml",
        "dataset/README.md",
    ):
        assert (REPO_ROOT / rel_path).is_file(), f"missing {rel_path}"
    assert not (MATRICES / "c-matrix.csv").exists(), "C suite must stay unbuilt in Phase 1"
    assert not (DATASET / "compose").exists(), "C assets must stay absent in Phase 1"


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


def test_matrix_headers_and_counts(a_matrix, b_matrix, d_native_matrix, d_compose_matrix) -> None:
    assert a_matrix[0] == A_COLUMNS
    assert b_matrix[0] == B_COLUMNS
    assert d_native_matrix[0] == D_COLUMNS
    assert d_compose_matrix[0] == D_COLUMNS
    assert len(a_matrix[1]) == A_ROWS
    assert len(b_matrix[1]) == B_ROWS
    assert len(d_native_matrix[1]) == D_NATIVE_ROWS
    assert len(d_compose_matrix[1]) == D_COMPOSE_ROWS


def test_case_ids_unique_and_well_formed(
    a_matrix, b_matrix, d_native_matrix, d_compose_matrix
) -> None:
    groups = {
        "a": a_matrix[1],
        "b": b_matrix[1],
        "d_native": d_native_matrix[1],
        "d_compose": d_compose_matrix[1],
    }
    seen: set[str] = set()
    for matrix, rows in groups.items():
        for row in rows:
            case_id = row["case_id"]
            assert CASE_ID_RE[matrix].match(case_id), f"{matrix}: bad case id {case_id!r}"
            assert case_id not in seen, f"duplicate case id across matrices: {case_id}"
            seen.add(case_id)


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
# B matrix contracts
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
        assert row["repair_window"] == "300"


# ---------------------------------------------------------------------------
# D matrices
# ---------------------------------------------------------------------------


def test_d_native_contract(d_native_matrix, b_matrix) -> None:
    _header, rows = d_native_matrix
    _b_header, b_rows = b_matrix
    l10_keys = {(row["suite"], int(row["task_idx"])) for row in b_rows}
    tasks: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        assert row["sub"] == "native"
        assert row["suite"] == "l10"
        assert row["target"] == "s1"
        assert row["max_steps"] == "800"
        assert row["repair_window"] == "300"
        assert row["window"] in {"early", "mid", "later", "all_done_control"}
        tasks.setdefault(int(row["task_idx"]), []).append(row)
    assert len(tasks) == 9
    for task_idx, task_rows in tasks.items():
        assert ("l10", task_idx) in l10_keys
        windows = {row["window"] for row in task_rows}
        assert {"early", "mid", "later"} <= windows, task_idx
        controls = [row for row in task_rows if row["window"] == "all_done_control"]
        assert len(controls) == 1
        assert controls[0]["level"] == "C0"
        assert controls[0]["expected_relation_after"] == "true"


def test_d_compose_is_an_explicit_placeholder(d_compose_matrix) -> None:
    _header, rows = d_compose_matrix
    structs: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        assert row["sub"] == "compose"
        assert row["suite"] == "compose"
        assert row["level"] == "L0"
        assert row["param"] == ""
        assert row["expected_relation_after"] == "false"
        for field in ("instruction", "revoked_predicate", "revoked_object"):
            assert row[field] == "<from C>", f"{row['case_id']}: {field} is not the placeholder"
        structs.setdefault(row["struct_id"], []).append(row)
    assert len(structs) == 120
    for struct_id, struct_rows in structs.items():
        assert sorted(row["window"] for row in struct_rows) == ["early", "later", "mid"]
        assert CASE_ID_RE["d_compose"].match(struct_rows[0]["case_id"])


# ---------------------------------------------------------------------------
# manifest / lite / sources
# ---------------------------------------------------------------------------


def test_manifest_schema_and_counts() -> None:
    manifest = read_yaml(DATASET / "manifest.yaml")
    assert manifest["schema_version"] == 2
    assert manifest["generated_by"] == "scripts/build_manifest.py"
    assert manifest["dataset_version"]
    assert manifest["libero"]["commit"] == "f78abd68ee283de9f9be3c8f7e2a9ad60246e95c"
    assert manifest["counts"] == {
        "a": 40,
        "b": 442,
        "d_native": 189,
        "d_compose_provisional": 360,
        "c": 0,
    }
    assert manifest["c"]["status"] == "not_built"


def test_manifest_sha256_and_rows_match_files() -> None:
    manifest = read_yaml(DATASET / "manifest.yaml")
    listed = {entry["path"] for entry in manifest["files"]}
    expected = {
        "dataset/matrices/a-matrix.csv",
        "dataset/matrices/b-matrix.csv",
        "dataset/matrices/d-native-matrix.csv",
        "dataset/matrices/d-compose-provisional.csv",
    }
    assert set(listed) == expected
    for entry in manifest["files"]:
        path = REPO_ROOT / entry["path"]
        assert path.is_file(), entry["path"]
        assert sha256_of(path) == entry["sha256"], entry["path"]
        _header, rows = read_csv(path)
        assert len(rows) == entry["rows"], entry["path"]
    assert [entry["path"] for entry in manifest["provisional"]] == [
        "dataset/matrices/d-compose-provisional.csv"
    ]
    provisional = manifest["provisional"][0]
    assert sha256_of(REPO_ROOT / provisional["path"]) == provisional["sha256"]
    assert provisional["rows"] == D_COMPOSE_ROWS


def test_manifest_splits() -> None:
    manifest = read_yaml(DATASET / "manifest.yaml")
    lite_payload = read_yaml(DATASET / "lite.yaml")
    splits = manifest["splits"]
    assert splits["core"] == ["a", "b", "d-native"]
    assert len(splits["lite"]) == LITE_ROWS
    assert set(splits["lite"]) == set(lite_payload["cases"])
    variance = splits["variance"]
    assert variance["init_rows"] == [0, 1, 2, 3, 4]
    assert len(variance["cases"]) == VARIANCE_CASES
    assert len(set(variance["cases"])) == VARIANCE_CASES
    executable: set[str] = set()
    for name in ("a", "b", "d-native"):
        path = MATRICES / f"{name}-matrix.csv"
        _header, rows = read_csv(path)
        executable.update(row["case_id"] for row in rows)
    assert set(variance["cases"]) <= executable
    assert "dataset/matrices/d-compose-provisional.csv" not in splits.get("core", [])


def test_lite_split_covers_the_required_axes() -> None:
    lite = read_yaml(DATASET / "lite.yaml")
    cases = lite["cases"]
    assert len(cases) == LITE_ROWS
    assert len(set(cases)) == LITE_ROWS
    all_ids: set[str] = set()
    for path in MATRICES.glob("*.csv"):
        _header, rows = read_csv(path)
        all_ids.update(row["case_id"] for row in rows)
    assert set(cases) <= all_ids
    provisional_ids = {
        row["case_id"] for row in read_csv(MATRICES / "d-compose-provisional.csv")[1]
    }
    assert not (set(cases) & provisional_ids), "provisional cases must never be executable"
    coverage = lite["coverage"]
    assert set(coverage["b_levels"]) == {"C0", "L0", "L1", "L2"}
    assert set(coverage["b_suites"]) == {"goal", "object", "spatial", "l10"}
    assert set(coverage["d_windows"]) == {"early", "mid", "later", "all_done_control"}
    assert set(coverage["a_suites"]) == {"goal", "object", "spatial", "l10"}
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
            for token in ("libero_compose", "libero-compose", "libero_runtime", "libero-runtime"):
                assert token not in lowered, f"{path}: precursor reference {token!r}"


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
    (tampered_root / "dataset").mkdir(parents=True)
    for name in (
        "a-matrix.csv",
        "b-matrix.csv",
        "d-native-matrix.csv",
        "d-compose-provisional.csv",
    ):
        target = tampered_root / "dataset" / "matrices" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((MATRICES / name).read_bytes())
    for name in ("manifest.yaml", "lite.yaml", "sources.yaml", "README.md"):
        (tampered_root / "dataset" / name).write_bytes((DATASET / name).read_bytes())
    # Corrupt one manifest hash; the validator must refuse it.
    manifest_path = tampered_root / "dataset" / "manifest.yaml"
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest_text = manifest_text.replace('sha256: "82786b4c', 'sha256: "00000000', 1)
    manifest_path.write_text(manifest_text, encoding="utf-8")
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
