#!/usr/bin/env python3
"""Generate ``dataset/manifest.yaml`` and ``dataset/lite.yaml``.

Both files are deterministic: the script never embeds a timestamp, so
``--check`` can rebuild them in memory and byte-compare against the frozen
files.  ``scripts/validate_dataset.py`` (and CI) call this mode.

What is generated
-----------------
* ``dataset/lite.yaml`` -- the 30-case smoke/reproduction split: 10 A
  single-task anchors, 10 B completion-rollback cases, 5 C in-execution
  rollback cases and 5 D compose cases (2 intact + 3 rollback).  Selection is
  a pure function of the matrices, so it is reproducible.
* ``dataset/manifest.yaml`` -- schema v3: counts, per-file sha256 for the five
  canonical base matrices, the evaluation splits, an explicitly-legacy list and
  the upstream LIBERO pin.

Canonical matrices (base-only suite views, 2026-11-21)
------------------------------------------------------
``a``           ``dataset/matrices/a-matrix.csv``                             40
``b``           ``dataset/matrices/libero-rollback/completion-rollback.csv``  442
``c``           ``dataset/matrices/libero-rollback/in-execution-rollback.csv`` 180
``d_intact``    ``dataset/matrices/libero-compose/intact.csv``                176
``d_rollback``  ``dataset/matrices/libero-compose/rollback.csv``              528

The legacy ``b-matrix.csv`` / ``d-native-matrix.csv`` /
``d-compose-provisional.csv`` files stay on disk untouched but are no longer
part of the executable split; they are listed under ``legacy`` for provenance.

Usage::

    python scripts/build_manifest.py           # write both files
    python scripts/build_manifest.py --check   # rebuild + compare, never write
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = REPO_ROOT / "dataset"
MATRICES_DIR = DATASET_DIR / "matrices"
MANIFEST_PATH = DATASET_DIR / "manifest.yaml"
LITE_PATH = DATASET_DIR / "lite.yaml"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"

#: Upstream LIBERO pin (``docs/SPEC.md`` §2.1).
LIBERO_REPO = "https://github.com/Lifelong-Robot-Learning/LIBERO"
LIBERO_COMMIT = "f78abd68ee283de9f9be3c8f7e2a9ad60246e95c"

#: Manifest / lite document versions (schema v3: base-only suite matrices).
SCHEMA_VERSION = 3
LITE_SCHEMA_VERSION = 2
LITE_TOTAL = 30

#: The five canonical base matrices of the dataset tree: (key, path, rows).
CANONICAL_FILES = (
    ("a", "dataset/matrices/a-matrix.csv", 40),
    ("b", "dataset/matrices/libero-rollback/completion-rollback.csv", 442),
    ("c", "dataset/matrices/libero-rollback/in-execution-rollback.csv", 180),
    ("d_intact", "dataset/matrices/libero-compose/intact.csv", 176),
    ("d_rollback", "dataset/matrices/libero-compose/rollback.csv", 528),
)

#: Legacy frozen CSVs retained on disk for provenance only (never executed).
LEGACY_FILES = (
    ("b", "dataset/matrices/b-matrix.csv", 442),
    ("d_native", "dataset/matrices/d-native-matrix.csv", 189),
    ("d_compose_provisional", "dataset/matrices/d-compose-provisional.csv", 360),
)

#: Every canonical suite is executable in the ``core`` split.
CORE_SPLIT = [key for key, _rel_path, _rows in CANONICAL_FILES]

#: Phase-1 ``variance`` selection: 100 cases over the canonical matrices.
VARIANCE_INIT_ROWS = [0, 1, 2, 3, 4]
VARIANCE_CASES = 100
VARIANCE_QUOTA = (
    ("a", None),  # all A anchors
    ("b", 30),
    ("c", 15),
    ("d_intact", 9),
    ("d_rollback", 6),
)

#: Minimum columns each canonical matrix must carry for the selections below.
REQUIRED_COLUMNS = {
    "a": ("case_id", "suite", "task_idx"),
    "b": ("case_id", "suite", "task_idx", "level", "param"),
    "c": ("case_id", "suite", "task_idx", "window", "level", "param"),
    "d_intact": ("case_id", "struct_id", "source_suite", "n_atoms", "valid"),
    "d_rollback": ("case_id", "struct_id", "window", "level", "param"),
}

#: Deterministic ordering of suites / levels / windows used by the selections.
A_SUITE_QUOTA = (("goal", 3), ("l10", 2), ("object", 3), ("spatial", 2))
B_SUITES = ("goal", "l10", "object", "spatial")
B_LEVELS = ("L0", "L1", "L2")
C_LITE_PAIRS = (
    ("early", "L0"),
    ("mid", "L1"),
    ("later", "L2"),
    ("early", "L1"),
    ("mid", "L2"),
)
D_WINDOWS = ("early", "mid", "later")


def _fail(message: str, *, code: int = 2) -> None:
    raise SystemExit(f"[build_manifest] error: {message} (exit {code})")


def _read_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))
    except OSError as error:
        _fail(f"cannot read {path}: {error}")


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        _fail(f"cannot hash {path}: {error}")


def _q(value: str) -> str:
    """Render a string as a double-quoted YAML scalar (JSON string syntax)."""

    return json.dumps(value, ensure_ascii=False)


def _dataset_version() -> str:
    try:
        import tomllib

        payload = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
        version = payload["project"]["version"]
    except Exception:  # noqa: BLE001 - a missing/unreadable pyproject must not block the build
        return "2.0.0.dev0"
    return str(version)


def _task_idx(row: dict[str, str]) -> int:
    try:
        return int(row["task_idx"])
    except (KeyError, ValueError):
        _fail(f"{row.get('case_id')}: bad task_idx {row.get('task_idx')!r}")
    raise AssertionError("unreachable")


def _level_rank(row: dict[str, str]) -> int:
    order = {"C0": 0, "L0": 1, "L1": 2, "L2": 3}
    return order.get(row.get("level", ""), 99)


def _window_rank(row: dict[str, str]) -> int:
    order = {"all_done_control": 0, "early": 1, "mid": 2, "later": 3}
    return order.get(row.get("window", ""), 99)


def _stride(case_ids: list[str], count: int) -> list[str]:
    """Pick ``count`` ids by uniform stride over an already sorted id list."""

    if count >= len(case_ids):
        return list(case_ids)
    if count <= 0:
        _fail(f"variance: invalid stride count {count}")
    step = (len(case_ids) - 1) / (count - 1)
    indices = sorted({round(index * step) for index in range(count)})
    if len(indices) != count:
        _fail("variance: stride selection produced duplicate case ids")
    return [case_ids[index] for index in indices]


def load_matrices() -> dict[str, list[dict[str, str]]]:
    """Load and sanity-check every canonical matrix mentioned in ``CANONICAL_FILES``."""

    rows: dict[str, list[dict[str, str]]] = {}
    seen: set[str] = set()
    for key, rel_path, expected_rows in CANONICAL_FILES:
        matrix_rows = _read_rows(REPO_ROOT / rel_path)
        if len(matrix_rows) != expected_rows:
            _fail(f"{rel_path}: expected {expected_rows} rows, found {len(matrix_rows)}")
        header = set(matrix_rows[0]) if matrix_rows else set()
        missing = [column for column in REQUIRED_COLUMNS[key] if column not in header]
        if missing:
            _fail(f"{rel_path}: missing required columns {missing}")
        for row in matrix_rows:
            case_id = row.get("case_id")
            if not case_id:
                _fail(f"{rel_path}: row with empty case_id")
            if case_id in seen:
                _fail(f"{rel_path}: duplicate case_id {case_id!r}")
            seen.add(case_id)
        rows[key] = matrix_rows
    return rows


# ---------------------------------------------------------------------------
# Split selection
# ---------------------------------------------------------------------------


def select_a_lite(a_rows: list[dict[str, str]]) -> list[str]:
    """10 A anchors: 3 goal + 2 l10 + 3 object + 2 spatial (SPEC §10)."""

    selected: list[str] = []
    for suite, quota in A_SUITE_QUOTA:
        candidates = sorted(
            (row for row in a_rows if row["suite"] == suite),
            key=lambda row: _task_idx(row),
        )
        if len(candidates) < quota:
            _fail(f"lite: suite {suite!r} has only {len(candidates)} A cases (< {quota})")
        selected.extend(row["case_id"] for row in candidates[:quota])
    return selected


def select_b_lite(b_rows: list[dict[str, str]]) -> list[str]:
    """10 B cases covering C0/L0/L1/L2 and every suite (SPEC §10)."""

    ordered = sorted(
        b_rows,
        key=lambda row: (
            row["suite"],
            _task_idx(row),
            _level_rank(row),
            row.get("param") or "",
        ),
    )
    chosen: list[str] = []

    def _take(candidates: list[dict[str, str]]) -> None:
        for row in candidates:
            if row["case_id"] not in chosen:
                chosen.append(row["case_id"])
                return

    # One C0 control per suite (4 cases).
    for suite in B_SUITES:
        _take([row for row in ordered if row["level"] == "C0" and row["suite"] == suite])
    # Two cases per perturbation level (L0 / L1 / L2); the first one is
    # suite-cycled so the perturbations are not all taken from one suite.
    for offset, level in enumerate(B_LEVELS):
        suite = B_SUITES[(offset + 1) % len(B_SUITES)]
        _take([row for row in ordered if row["level"] == level and row["suite"] == suite])
        _take([row for row in ordered if row["level"] == level])
    # Fill up to 10 from the deterministic order, skipping already chosen.
    for row in ordered:
        if len(chosen) == 10:
            break
        if row["case_id"] not in chosen:
            chosen.append(row["case_id"])
    if len(chosen) != 10:
        _fail(f"lite: B selection produced {len(chosen)} cases, expected 10")
    return chosen


def select_c_lite(c_rows: list[dict[str, str]]) -> list[str]:
    """5 C cases: one per (window, level) pair, no C0 control."""

    chosen: list[str] = []
    for window, level in C_LITE_PAIRS:
        candidates = sorted(
            (row for row in c_rows if row.get("window") == window and row.get("level") == level),
            key=lambda row: (_task_idx(row), row.get("param") or "", row["case_id"]),
        )
        for row in candidates:
            if row["case_id"] not in chosen:
                chosen.append(row["case_id"])
                break
        else:
            _fail(f"lite: no C case with window={window!r} level={level!r}")
    if any(row.get("level") == "C0" for row in c_rows if row["case_id"] in chosen):
        _fail("lite: C selection must not contain a C0 control")
    if len(chosen) != len(C_LITE_PAIRS):
        _fail(f"lite: C selection produced {len(chosen)} cases, expected 5")
    return chosen


def select_d_lite(
    intact_rows: list[dict[str, str]],
    rollback_rows: list[dict[str, str]],
) -> tuple[list[str], list[str]]:
    """5 D cases: 2 valid n=2 intact structures + one rollback case per window."""

    by_struct: dict[str, dict[str, str]] = {}
    for row in sorted(intact_rows, key=lambda row: row["case_id"]):
        by_struct.setdefault(row["struct_id"], row)
    if len(by_struct) < 2:
        _fail("lite: fewer than two D-intact structures")
    intact_structs = _stride(sorted(by_struct), 2)
    intact_cases = [by_struct[struct_id]["case_id"] for struct_id in intact_structs]
    for struct_id in intact_structs:
        row = by_struct[struct_id]
        if row.get("valid") != "true" or row.get("n_atoms") != "2":
            _fail(f"lite: D-intact {row['case_id']} is not a valid n=2 structure")

    rollback_cases: list[str] = []
    used_structs: set[str] = set()
    for window in D_WINDOWS:
        candidates = sorted(
            (row for row in rollback_rows if row.get("window") == window),
            key=lambda row: (row["struct_id"], row.get("param") or "", row["case_id"]),
        )
        if not candidates:
            _fail(f"lite: no D-rollback case with window={window!r}")
        pick = next(
            (row for row in candidates if row["struct_id"] not in used_structs),
            candidates[0],
        )
        used_structs.add(pick["struct_id"])
        rollback_cases.append(pick["case_id"])
    return intact_cases, rollback_cases


def build_lite(rows: dict[str, list[dict[str, str]]]) -> dict:
    a_cases = select_a_lite(rows["a"])
    b_cases = select_b_lite(rows["b"])
    c_cases = select_c_lite(rows["c"])
    d_intact_cases, d_rollback_cases = select_d_lite(rows["d_intact"], rows["d_rollback"])
    cases = [*a_cases, *b_cases, *c_cases, *d_intact_cases, *d_rollback_cases]
    if len(cases) != LITE_TOTAL:
        _fail(f"lite: built {len(cases)} cases, expected {LITE_TOTAL}")
    if len(set(cases)) != len(cases):
        _fail("lite: selection contains duplicate case ids")
    return {
        "a": a_cases,
        "b": b_cases,
        "c": c_cases,
        "d_intact": d_intact_cases,
        "d_rollback": d_rollback_cases,
        "cases": cases,
    }


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def lite_coverage(
    lite: dict,
    rows: dict[str, list[dict[str, str]]],
) -> dict:
    by_id: dict[str, dict[str, str]] = {}
    for matrix_rows in rows.values():
        for row in matrix_rows:
            by_id.setdefault(row["case_id"], row)
    a_rows = [by_id[case_id] for case_id in lite["a"]]
    b_rows = [by_id[case_id] for case_id in lite["b"]]
    c_rows = [by_id[case_id] for case_id in lite["c"]]
    d_intact_rows = [by_id[case_id] for case_id in lite["d_intact"]]
    d_rollback_rows = [by_id[case_id] for case_id in lite["d_rollback"]]
    return {
        "a_suites": _counts([row["suite"] for row in a_rows]),
        "b_suites": _counts([row["suite"] for row in b_rows]),
        "b_levels": _counts([row["level"] for row in b_rows]),
        "c_windows": _counts([row["window"] for row in c_rows]),
        "c_levels": _counts([row["level"] for row in c_rows]),
        "d_intact_source_suites": _counts([row["source_suite"] for row in d_intact_rows]),
        "d_rollback_windows": _counts([row["window"] for row in d_rollback_rows]),
        "total": len(lite["cases"]),
    }


def build_variance(rows: dict[str, list[dict[str, str]]]) -> dict:
    """Deterministic 100-case subset of the five canonical matrices."""

    cases: list[str] = []
    for key, quota in VARIANCE_QUOTA:
        ids = sorted(row["case_id"] for row in rows[key])
        selected = ids if quota is None else _stride(ids, quota)
        cases.extend(selected)
    if len(cases) != VARIANCE_CASES:
        _fail(f"variance: built {len(cases)} cases, expected {VARIANCE_CASES}")
    return {
        "rule": (
            "40 A anchors (all) + 30 B + 15 C + 9 D-intact + 6 D-rollback cases "
            "picked by uniform stride over the sorted case ids of each canonical "
            "matrix; one case per structure, evaluated on init rows 0-4"
        ),
        "init_rows": VARIANCE_INIT_ROWS,
        "cases": cases,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_lite(lite: dict, coverage: dict) -> str:
    lines: list[str] = [
        "# LIBERO-Rollback lite split -- generated by scripts/build_manifest.py; do not edit.",
        "# Selection rule: docs/SPEC.md §10 (deterministic, a pure function of the matrices).",
        f"schema_version: {LITE_SCHEMA_VERSION}",
        "split: lite",
        "total: " + str(coverage["total"]),
        "rule: >-",
        "  A: 10 single-task anchors (goal/l10/object/spatial = 3/2/3/2).",
        "  B: 10 completion-rollback cases: one C0 control per suite plus two cases",
        "  per perturbation level (L0/L1/L2), suite-cycled, deterministic order.",
        "  C: 5 in-execution cases, one per (window, level) pair in the fixed order",
        "  early-L0, mid-L1, later-L2, early-L1, mid-L2; no C0 control.",
        "  D: 2 valid n=2 intact structures (uniform stride over sorted struct ids)",
        "  plus one rollback case per window (early/mid/later), distinct structures",
        "  where possible.",
        "splits:",
    ]
    for key in ("a", "b", "c", "d_intact", "d_rollback"):
        lines.append(f"  {key}:")
        lines.extend(f"    - {_q(case_id)}" for case_id in lite[key])
    lines.append("cases:")
    lines.extend(f"  - {_q(case_id)}" for case_id in lite["cases"])
    lines.append("coverage:")
    for group, counts in coverage.items():
        if isinstance(counts, dict):
            lines.append(f"  {group}:")
            lines.extend(f"    {_q(name)}: {value}" for name, value in counts.items())
        else:
            lines.append(f"  {group}: {counts}")
    return "\n".join(lines) + "\n"


def _file_entry(rel_path: str, sha: str, row_count: int | None) -> list[str]:
    lines = [f"  - path: {_q(rel_path)}", f"    sha256: {_q(sha)}"]
    if row_count is not None:
        lines.append(f"    rows: {row_count}")
    return lines


def render_manifest(
    lite: dict,
    variance: dict,
    version: str,
) -> str:
    files: list[list[str]] = []
    for _key, rel_path, expected_rows in CANONICAL_FILES:
        files.append(_file_entry(rel_path, _sha256(REPO_ROOT / rel_path), expected_rows))
    lines: list[str] = [
        "# LIBERO-Rollback dataset manifest -- generated by "
        "scripts/build_manifest.py; do not edit.",
        "# Deterministic: rebuild with `python scripts/build_manifest.py --check`.",
        f"schema_version: {SCHEMA_VERSION}",
        f"dataset_version: {_q(version)}",
        "generated_by: scripts/build_manifest.py",
        "libero:",
        f"  repo: {_q(LIBERO_REPO)}",
        f"  commit: {_q(LIBERO_COMMIT)}",
        "  assets:",
        f"    repo_root: {_q('LIBERO_HOME')}",
        f"    bddl_files: {_q('libero/libero/bddl_files')}",
        f"    init_files: {_q('libero/libero/init_files')}",
        "counts:",
    ]
    for key, _rel_path, expected_rows in CANONICAL_FILES:
        lines.append(f"  {key}: {expected_rows}")
    lines.append("files:")
    for entry in files:
        lines.extend(entry)
    lines.append("legacy:")
    lines.append(
        "  note: "
        + _q(
            "Frozen pre-migration CSVs retained on disk for provenance only. They are "
            "not hashed here, not executable and not part of any split; the canonical "
            "base-only suite views above supersede them."
        )
    )
    lines.append("  counts:")
    for key, _rel_path, expected_rows in LEGACY_FILES:
        lines.append(f"    {key}: {expected_rows}")
    lines.append("  files:")
    lines.extend(f"    - {_q(rel_path)}" for _key, rel_path, _rows in LEGACY_FILES)
    lines.append("splits:")
    lines.append("  lite:")
    lines.extend(f"    - {_q(case_id)}" for case_id in lite["cases"])
    lines.append("  core:")
    lines.extend(f"    - {_q(name)}" for name in CORE_SPLIT)
    lines.append("  variance:")
    lines.append(f"    rule: {_q(variance['rule'])}")
    lines.append("    init_rows:")
    lines.extend(f"      - {init_row}" for init_row in variance["init_rows"])
    lines.append("    cases:")
    lines.extend(f"      - {_q(case_id)}" for case_id in variance["cases"])
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_all() -> tuple[str, str]:
    rows = load_matrices()
    lite = build_lite(rows)
    coverage = lite_coverage(lite, rows)
    lite_text = render_lite(lite, coverage)
    variance = build_variance(rows)
    manifest_text = render_manifest(
        lite=lite,
        variance=variance,
        version=_dataset_version(),
    )
    return lite_text, manifest_text


def _compare(path: Path, expected: str) -> bool:
    try:
        actual = path.read_text(encoding="utf-8")
    except OSError:
        print(f"[build_manifest] --check: missing {path}")
        return False
    if actual == expected:
        return True
    actual_lines = actual.splitlines()
    expected_lines = expected.splitlines()
    first = next(
        (
            index
            for index, (left, right) in enumerate(zip(actual_lines, expected_lines))
            if left != right
        ),
        min(len(actual_lines), len(expected_lines)),
    )
    print(f"[build_manifest] --check: {path} is stale (first diff at line {first + 1})")
    return False


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or check dataset/manifest.yaml and dataset/lite.yaml.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--check", action="store_true", help="rebuild and compare; never write")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    lite_text, manifest_text = build_all()
    if args.check:
        ok = _compare(LITE_PATH, lite_text)
        ok = _compare(MANIFEST_PATH, manifest_text) and ok
        if not ok:
            print("[build_manifest] --check: FAILED; re-run without --check")
            return 1
        print(
            "[build_manifest] OK: lite.yaml and manifest.yaml are up to date "
            f"(manifest sha256 {hashlib.sha256(manifest_text.encode('utf-8')).hexdigest()})"
        )
        return 0
    LITE_PATH.write_bytes(lite_text.encode("utf-8"))
    MANIFEST_PATH.write_bytes(manifest_text.encode("utf-8"))
    print(f"[build_manifest] wrote {LITE_PATH} ({LITE_TOTAL} cases) and {MANIFEST_PATH}")
    print(
        "[build_manifest] manifest sha256 "
        + hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
