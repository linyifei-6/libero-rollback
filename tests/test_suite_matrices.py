"""Static contract tests for the base test-suite matrices (B/C/D)."""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MATRICES = REPO_ROOT / "dataset" / "matrices"

B_PATH = MATRICES / "b-matrix.csv"
C_SOURCE_PATH = MATRICES / "d-native-matrix.csv"

B_SUITE = MATRICES / "libero-rollback" / "completion-rollback.csv"
C_SUITE = MATRICES / "libero-rollback" / "in-execution-rollback.csv"
D_ROLLBACK = MATRICES / "libero-compose" / "rollback.csv"
D_INTACT = MATRICES / "libero-compose" / "intact.csv"

SUITE_COLUMNS = ("test_suite", "dimension", "arm")


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames is not None
        return list(reader.fieldnames), list(reader)


def test_suite_files_exist() -> None:
    assert B_SUITE.is_file()
    assert C_SUITE.is_file()
    assert D_ROLLBACK.is_file()
    assert D_INTACT.is_file()


def test_b_suite_is_the_base_b_matrix() -> None:
    b_header, b_rows = read_rows(B_PATH)
    header, rows = read_rows(B_SUITE)
    assert len(rows) == 442
    assert header[:4] == ["case_id", *SUITE_COLUMNS]
    assert set(header) == set(b_header) | set(SUITE_COLUMNS)
    assert [row["case_id"] for row in rows] == [row["case_id"] for row in b_rows]
    assert {row["test_suite"] for row in rows} == {"libero-rollback"}
    assert {row["dimension"] for row in rows} == {"completion"}
    assert all(row["repair_window"] == "600" for row in rows)
    assert sum(row["level"] == "C0" for row in rows) == 40
    assert sum(row["level"] != "C0" for row in rows) == 402
    assert {row["arm"] for row in rows if row["level"] == "C0"} == {"control"}
    assert {row["arm"] for row in rows if row["level"] != "C0"} == {"rollback"}


def test_c_suite_is_native_windows_without_controls() -> None:
    _source_header, source_rows = read_rows(C_SOURCE_PATH)
    header, rows = read_rows(C_SUITE)
    assert len(rows) == 180
    assert header[:4] == ["case_id", *SUITE_COLUMNS]
    assert {row["test_suite"] for row in rows} == {"libero-rollback"}
    assert {row["dimension"] for row in rows} == {"in-execution"}
    assert {row["arm"] for row in rows} == {"rollback"}
    assert {row["window"] for row in rows} == {"early", "mid", "later"}
    assert "all_done_control" not in {row["window"] for row in rows}
    assert "C0" not in {row["level"] for row in rows}
    assert {row["level"] for row in rows} == {"L0", "L1", "L2"}
    assert all(row["repair_window"] == "600" for row in rows)
    assert {row["task_idx"] for row in rows} == {"0", "33", "78", "133", "137", "145", "158", "193", "237"}

    expected_ids = {
        row["case_id"]
        for row in source_rows
        if row["window"] != "all_done_control"
    }
    assert {row["case_id"] for row in rows} == expected_ids

    by_task_window: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row["task_idx"], row["window"])
        by_task_window[key] = by_task_window.get(key, 0) + 1
    for task in {row["task_idx"] for row in rows}:
        expected = 4 if task == "0" else 7
        for window in ("early", "mid", "later"):
            assert by_task_window[(task, window)] == expected


def test_d_intact_is_the_176_valid_n2_compose_set() -> None:
    header, rows = read_rows(D_INTACT)
    assert len(rows) == 176
    assert header[:4] == ["case_id", *SUITE_COLUMNS]
    assert {row["test_suite"] for row in rows} == {"compose"}
    assert {row["dimension"] for row in rows} == {"intact"}
    assert {row["arm"] for row in rows} == {"intact"}
    assert {row["level"] for row in rows} == {"INTACT"}
    assert {row["param"] for row in rows} == {""}
    assert {row["n_atoms"] for row in rows} == {"2"}
    assert {row["valid"] for row in rows} == {"true"}
    assert Counter(row["source_suite"] for row in rows) == {
        "LIBERO_GOAL": 76,
        "LIBERO_OBJECT": 100,
    }
    assert all(row["repair_window"] == "0" for row in rows)
    assert all(row["expected_relation_after"] == "true" for row in rows)
    assert all(row["goal_atoms"].count("|") == 1 for row in rows)


def test_d_rollback_is_176_structures_x_3_windows() -> None:
    header, rows = read_rows(D_ROLLBACK)
    assert len(rows) == 528
    assert header[:4] == ["case_id", *SUITE_COLUMNS]
    assert {row["test_suite"] for row in rows} == {"compose"}
    assert {row["dimension"] for row in rows} == {"in-execution"}
    assert {row["arm"] for row in rows} == {"rollback"}
    assert {row["level"] for row in rows} == {"L0"}
    assert {row["window"] for row in rows} == {"early", "mid", "later"}
    assert all(row["repair_window"] == "600" for row in rows)
    assert {row["target"] for row in rows} == {"s1"}
    assert {row["s2_must_stay_true"] for row in rows} == {"true"}
    assert len({row["struct_id"] for row in rows}) == 176
    assert {row["valid"] for row in rows} == {"true"}
    for row in rows:
        assert row["instruction"] != "<from C>"
        assert row["revoked_predicate"].startswith("(")
        assert row["revoked_object"]
    counts = Counter((row["struct_id"], row["window"]) for row in rows)
    assert all(count == 1 for count in counts.values())
    assert len(counts) == 176 * 3


def test_d_rollback_struct_ids_match_intact() -> None:
    _h1, intact = read_rows(D_INTACT)
    _h2, rollback = read_rows(D_ROLLBACK)
    assert {row["struct_id"] for row in intact} == {row["struct_id"] for row in rollback}


def test_d_assets_exist_and_match_hashes() -> None:
    _header, rows = read_rows(D_INTACT)
    root = REPO_ROOT / "dataset" / "compose" / "bddl"
    for row in rows:
        task_id = row["task_id"]
        bddl = root / f"{task_id}.bddl"
        init = root / f"{task_id}.pruned_init"
        assert bddl.is_file(), bddl
        assert init.is_file(), init
        assert hashlib.sha256(bddl.read_bytes()).hexdigest() == row["bddl_sha256"]
        assert hashlib.sha256(init.read_bytes()).hexdigest() == row["pruned_init_sha256"]


def test_suite_rows_are_utf8_lf_without_bom() -> None:
    for path in (B_SUITE, C_SUITE, D_ROLLBACK, D_INTACT):
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), path
        assert b"\r" not in raw, path
        assert raw.endswith(b"\n"), path
        raw.decode("utf-8")
