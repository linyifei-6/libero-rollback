"""Dataset-level static validation tests (docs/SPEC.md §1, §8-§10).

The fixtures are deliberately tiny: the expected counts and the lite split size
are overridable for tests, while the production defaults enforce the frozen
Phase 1 numbers (40 A / 442 B / 189 D-native / 360 provisional / 0 C, lite 30).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from libero_rollback.validation import (
    check_lite,
    check_manifest,
    check_matrices,
    check_path_hygiene,
    validate_dataset,
)

COUNTS = {"a": 2, "b": 2, "d_native": 2, "d_compose_provisional": 2, "c": 0}
LITE_IDS = ["a-goal-t000", "b-goal-t000-c0"]

MATRIX_FILES = {
    "a": "dataset/matrices/a-matrix.csv",
    "b": "dataset/matrices/b-matrix.csv",
    "d_native": "dataset/matrices/d-native-matrix.csv",
    "d_compose_provisional": "dataset/matrices/d-compose-provisional.csv",
}

CSV_ROWS = {
    "a": [
        ("a-goal-t000", "goal"),
        ("a-object-t001", "object"),
    ],
    "b": [
        ("b-goal-t000-c0", "goal", "C0"),
        ("b-goal-t001-g-l0", "goal", "L0"),
    ],
    "d_native": [
        ("d-l10-t000-c0", "l10", "C0", "all_done_control"),
        ("d-l10-t001-early-l0", "l10", "L0", "early"),
    ],
    "d_compose_provisional": [
        ("d-compose-s0001-early-l0", "goal", "early"),
        ("d-compose-s0002-mid-l0", "goal", "mid"),
    ],
}

CSV_HEADERS = {
    "a": ["case_id", "suite"],
    "b": ["case_id", "suite", "level"],
    "d_native": ["case_id", "suite", "level", "window"],
    "d_compose_provisional": ["case_id", "suite", "window"],
}


def _write_csv(path: Path, header: list[str], rows: list[tuple[str, ...]]) -> None:
    lines = [",".join(header), *[",".join(row) for row in rows]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_manifest(repo: Path, *, counts: dict | None = None, rows: dict | None = None) -> None:
    dataset_root = repo / "dataset"
    counts = counts if counts is not None else COUNTS
    rows = rows if rows is not None else {key: len(value) for key, value in CSV_ROWS.items()}
    files = []
    for key, relative in MATRIX_FILES.items():
        path = repo / relative
        files.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "rows": rows[key],
            }
        )
    manifest = {
        "schema_version": 2,
        "dataset_version": "2.0.0.dev0",
        "generated_by": "scripts/build_manifest.py",
        "libero": {
            "repo": "https://github.com/Lifelong-Robot-Learning/LIBERO",
            "commit": "f78abd68ee283de9f9be3c8f7e2a9ad60246e95c",
        },
        "counts": dict(counts),
        "files": files,
        "splits": {"lite": list(LITE_IDS), "core": ["a", "b", "d-native"]},
        "provisional": [
            {
                "path": MATRIX_FILES["d_compose_provisional"],
                "sha256": files[-1]["sha256"],
                "rows": rows["d_compose_provisional"],
            }
        ],
    }
    (dataset_root / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )


def _write_lite(dataset_root: Path, case_ids: list[str]) -> None:
    document = {
        "schema_version": 1,
        "split": "lite",
        "total": len(case_ids),
        "cases": case_ids,
        "splits": {"a": ["a-goal-t000"], "b": ["b-goal-t000-c0"], "d_native": []},
    }
    (dataset_root / "lite.yaml").write_text(
        yaml.safe_dump(document, sort_keys=False), encoding="utf-8"
    )


def make_dataset(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    dataset_root = repo / "dataset"
    (dataset_root / "matrices").mkdir(parents=True)
    for key, relative in MATRIX_FILES.items():
        _write_csv(repo / relative, CSV_HEADERS[key], CSV_ROWS[key])
    _write_manifest(repo)
    _write_lite(dataset_root, LITE_IDS)
    (dataset_root / "README.md").write_text("# fixture data card\n", encoding="utf-8")
    return repo, dataset_root


def _manifest(dataset_root: Path) -> dict:
    return yaml.safe_load((dataset_root / "manifest.yaml").read_text(encoding="utf-8"))


def _save_manifest(dataset_root: Path, manifest: dict) -> None:
    (dataset_root / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )


def _report(dataset_root: Path):
    return validate_dataset(dataset_root, expected_counts=COUNTS, lite_count=2)


def test_minimal_dataset_passes(tmp_path: Path) -> None:
    repo, dataset_root = make_dataset(tmp_path)
    report = _report(dataset_root)
    assert report.ok, report.format()
    assert report.errors == []
    assert {check.name for check in report.checks} == {
        "manifest",
        "matrices",
        "lite split",
        "path hygiene",
    }
    # The provisional list re-lists a file that is already in `files`: not a duplicate.
    assert not any("duplicate manifest path" in error for error in report.errors)


def test_granular_helpers_accept_the_fixture(tmp_path: Path) -> None:
    _, dataset_root = make_dataset(tmp_path)
    assert check_manifest(dataset_root, expected_counts=COUNTS) == []
    assert check_matrices(dataset_root, expected_counts=COUNTS) == []
    assert check_lite(dataset_root, lite_count=2) == []
    assert check_path_hygiene(dataset_root) == []


def test_missing_matrix_file_is_reported(tmp_path: Path) -> None:
    repo, dataset_root = make_dataset(tmp_path)
    (repo / MATRIX_FILES["b"]).unlink()
    report = _report(dataset_root)
    assert not report.ok
    assert any("required matrix file is missing" in error for error in report.errors)


def test_manifest_sha256_mismatch_is_reported(tmp_path: Path) -> None:
    _, dataset_root = make_dataset(tmp_path)
    manifest = _manifest(dataset_root)
    manifest["files"][0]["sha256"] = "0" * 64
    _save_manifest(dataset_root, manifest)
    errors = check_manifest(dataset_root, expected_counts=COUNTS)
    assert any("SHA-256 mismatch" in error for error in errors)


def test_manifest_count_mismatch_is_reported(tmp_path: Path) -> None:
    repo, dataset_root = make_dataset(tmp_path)
    manifest = _manifest(dataset_root)
    manifest["counts"]["b"] = 3
    _save_manifest(dataset_root, manifest)
    errors = check_manifest(dataset_root, expected_counts=COUNTS)
    assert any("manifest.counts.b must be 2" in error for error in errors)
    assert (repo / MATRIX_FILES["b"]).is_file()


def test_manifest_rows_mismatch_is_reported(tmp_path: Path) -> None:
    _, dataset_root = make_dataset(tmp_path)
    manifest = _manifest(dataset_root)
    manifest["files"][0]["rows"] = 7
    _save_manifest(dataset_root, manifest)
    errors = check_manifest(dataset_root, expected_counts=COUNTS)
    assert any("manifest rows mismatch" in error for error in errors)


def test_libero_pin_and_version_are_enforced(tmp_path: Path) -> None:
    _, dataset_root = make_dataset(tmp_path)
    manifest = _manifest(dataset_root)
    manifest["libero"]["commit"] = "deadbeef"
    manifest["dataset_version"] = "not-a-version"
    _save_manifest(dataset_root, manifest)
    errors = check_manifest(dataset_root, expected_counts=COUNTS)
    assert any("commit must be pinned" in error for error in errors)
    assert any("dataset_version" in error for error in errors)


def test_duplicate_case_id_is_reported(tmp_path: Path) -> None:
    repo, dataset_root = make_dataset(tmp_path)
    _write_csv(
        repo / MATRIX_FILES["a"],
        CSV_HEADERS["a"],
        [*CSV_ROWS["a"], ("a-goal-t000", "goal")],
    )
    _write_manifest(repo, rows={key: len(value) for key, value in CSV_ROWS.items()} | {"a": 3})
    errors = check_matrices(dataset_root, expected_counts={**COUNTS, "a": 3})
    assert any("duplicate case_id" in error for error in errors)


def test_case_id_naming_scheme_is_enforced(tmp_path: Path) -> None:
    repo, dataset_root = make_dataset(tmp_path)
    _write_csv(
        repo / MATRIX_FILES["a"],
        CSV_HEADERS["a"],
        [*CSV_ROWS["a"], ("a-goal-t5", "goal")],
    )
    errors = check_matrices(dataset_root)
    assert any("naming scheme" in error for error in errors)


def test_lite_unknown_reference_is_reported(tmp_path: Path) -> None:
    _, dataset_root = make_dataset(tmp_path)
    _write_lite(dataset_root, ["a-goal-t000", "a-goal-t999"])
    errors = check_lite(dataset_root, lite_count=2)
    assert any("unknown case ids" in error for error in errors)


def test_lite_count_is_reported(tmp_path: Path) -> None:
    _, dataset_root = make_dataset(tmp_path)
    _write_lite(dataset_root, ["a-goal-t000"])
    errors = check_lite(dataset_root, lite_count=2)
    assert any("must contain 2 case ids" in error for error in errors)


def test_manifest_lite_split_must_match_lite_yaml(tmp_path: Path) -> None:
    _, dataset_root = make_dataset(tmp_path)
    manifest = _manifest(dataset_root)
    manifest["splits"]["lite"] = ["a-goal-t000"]
    _save_manifest(dataset_root, manifest)
    errors = check_lite(dataset_root, lite_count=2)
    assert any("does not match dataset/lite.yaml" in error for error in errors)


def test_absolute_host_path_in_dataset_is_rejected(tmp_path: Path) -> None:
    _, dataset_root = make_dataset(tmp_path)
    (dataset_root / "notes.md").write_text(
        "data lives under /opt/data/rollback\n", encoding="utf-8"
    )
    errors = check_path_hygiene(dataset_root)
    assert any("absolute host path" in error for error in errors)


def test_absolute_path_in_structured_yaml_is_rejected(tmp_path: Path) -> None:
    _, dataset_root = make_dataset(tmp_path)
    _write_lite(dataset_root, LITE_IDS)
    lite = yaml.safe_load((dataset_root / "lite.yaml").read_text(encoding="utf-8"))
    lite["root"] = "/opt/data/rollback"
    (dataset_root / "lite.yaml").write_text(yaml.safe_dump(lite, sort_keys=False), encoding="utf-8")
    errors = check_path_hygiene(dataset_root)
    assert any("absolute path in value" in error for error in errors)


def test_bom_and_crlf_are_rejected(tmp_path: Path) -> None:
    repo, dataset_root = make_dataset(tmp_path)
    (repo / "dataset/matrices/bom-matrix.csv").write_bytes(
        b"\xef\xbb\xbfcase_id\n"
    )
    (repo / "dataset/matrices/crlf-matrix.csv").write_bytes(b"case_id\r\nx\r\n")
    errors = check_path_hygiene(dataset_root)
    assert any("BOM is forbidden" in error for error in errors)
    assert any("LF line endings" in error for error in errors)


def test_missing_manifest_is_reported(tmp_path: Path) -> None:
    _, dataset_root = make_dataset(tmp_path)
    (dataset_root / "manifest.yaml").unlink()
    report = _report(dataset_root)
    assert not report.ok
    assert any("missing" in error for error in report.errors)
    assert check_manifest(dataset_root, expected_counts=COUNTS)


def test_report_serialises_to_dict_and_text(tmp_path: Path) -> None:
    _, dataset_root = make_dataset(tmp_path)
    report = _report(dataset_root)
    payload = report.to_dict()
    assert payload["ok"] is True
    assert payload["dataset_root"] == str(dataset_root)
    assert len(payload["checks"]) == 4
    text = report.format()
    assert text.startswith("dataset validation: PASS")
    assert "summary: 0 error(s)" in text
    assert isinstance(report.warnings, list)


@pytest.mark.parametrize(
    "mutate,expected",
    [
        (
            lambda manifest: manifest["files"][1].update(path="../escape.csv"),
            "unsafe manifest path",
        ),
        (lambda manifest: manifest["counts"].update(c=1), "manifest.counts.c"),
    ],
)
def test_manifest_structural_errors(tmp_path: Path, mutate, expected: str) -> None:
    _, dataset_root = make_dataset(tmp_path)
    manifest = _manifest(dataset_root)
    mutate(manifest)
    _save_manifest(dataset_root, manifest)
    errors = check_manifest(dataset_root, expected_counts=COUNTS)
    assert any(expected in error for error in errors)
