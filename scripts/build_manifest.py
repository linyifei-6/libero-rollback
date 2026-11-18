#!/usr/bin/env python3
"""Generate ``dataset/manifest.yaml`` and ``dataset/lite.yaml``.

Both files are deterministic: the script never embeds a timestamp, so
``--check`` can rebuild them in memory and byte-compare against the frozen
files.  ``scripts/validate_dataset.py`` (and CI) call this mode.

What is generated
-----------------
* ``dataset/lite.yaml`` -- the 30-case smoke/reproduction split (``docs/SPEC.md``
  §10): 10 A single-task anchors, 10 B rollback cases covering all four levels
  and all four suites, 10 D-native cases covering ``early/mid/later`` plus an
  ``all_done_control`` no-op control.  Selection is a pure function of the
  matrices, so it is reproducible.
* ``dataset/manifest.yaml`` -- counts, per-file sha256, the evaluation splits,
  the provisional-file list and the upstream LIBERO pin (``docs/SPEC.md`` §8).

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

#: The four matrices of the Phase-1 data tree.
MATRIX_FILES = (
    ("a", "dataset/matrices/a-matrix.csv", "a-matrix", 40),
    ("b", "dataset/matrices/b-matrix.csv", "b-matrix", 442),
    ("d_native", "dataset/matrices/d-native-matrix.csv", "d-native-matrix", 189),
    (
        "d_compose_provisional",
        "dataset/matrices/d-compose-provisional.csv",
        "d-compose-provisional",
        360,
    ),
)

#: Executable (non-provisional) matrices that form the Phase-1 ``core`` split.
CORE_SPLIT = ["a", "b", "d-native"]

#: Phase-1 ``variance`` selection: one case per structure, 5 init rows.
VARIANCE_INIT_ROWS = [0, 1, 2, 3, 4]
VARIANCE_CASES = 100

#: Deterministic ordering of suites / levels / windows used by the selections.
A_SUITE_QUOTA = (("goal", 3), ("l10", 2), ("object", 3), ("spatial", 2))
B_SUITES = ("goal", "l10", "object", "spatial")
B_LEVELS = ("L0", "L1", "L2")
D_WINDOWS = ("early", "mid", "later")
D_LEVELS = ("L0", "L1", "L2")


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


def load_matrices() -> dict[str, list[dict[str, str]]]:
    """Load and sanity-check every matrix mentioned in ``MATRIX_FILES``."""

    rows: dict[str, list[dict[str, str]]] = {}
    for key, rel_path, _stem, expected_rows in MATRIX_FILES:
        matrix_rows = _read_rows(REPO_ROOT / rel_path)
        if len(matrix_rows) != expected_rows:
            _fail(f"{rel_path}: expected {expected_rows} rows, found {len(matrix_rows)}")
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


def select_d_lite(d_rows: list[dict[str, str]]) -> list[str]:
    """10 D-native cases: one control + early/mid/later x (L0, L1, L2)."""

    ordered = sorted(
        d_rows,
        key=lambda row: (
            _window_rank(row),
            _level_rank(row),
            row.get("param") or "",
            _task_idx(row),
        ),
    )
    chosen: list[str] = []
    controls = [row for row in ordered if row["window"] == "all_done_control"]
    if not controls:
        _fail("lite: no D-native all_done_control case found")
    chosen.append(controls[0]["case_id"])
    for window in D_WINDOWS:
        for level in D_LEVELS:
            candidates = [
                row
                for row in ordered
                if row["window"] == window
                and row["level"] == level
                and row["case_id"] not in chosen
            ]
            if not candidates:
                _fail(f"lite: no D-native case with window={window!r} level={level!r}")
            chosen.append(candidates[0]["case_id"])
    if len(chosen) != 10:
        _fail(f"lite: D selection produced {len(chosen)} cases, expected 10")
    return chosen


def build_lite(rows: dict[str, list[dict[str, str]]]) -> dict:
    a_cases = select_a_lite(rows["a"])
    b_cases = select_b_lite(rows["b"])
    d_cases = select_d_lite(rows["d_native"])
    return {
        "a": a_cases,
        "b": b_cases,
        "d_native": d_cases,
        "cases": [*a_cases, *b_cases, *d_cases],
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
    d_rows = [by_id[case_id] for case_id in lite["d_native"]]
    return {
        "a_suites": _counts([row["suite"] for row in a_rows]),
        "b_suites": _counts([row["suite"] for row in b_rows]),
        "b_levels": _counts([row["level"] for row in b_rows]),
        "d_windows": _counts([row["window"] for row in d_rows]),
        "d_levels": _counts([row["level"] for row in d_rows]),
        "total": len(lite["cases"]),
    }


def build_variance(rows: dict[str, list[dict[str, str]]]) -> dict:
    """Deterministic 100-case subset of the core split (one case per structure)."""

    def _stride(case_ids: list[str], count: int) -> list[str]:
        if count >= len(case_ids):
            return list(case_ids)
        step = (len(case_ids) - 1) / (count - 1)
        indices = sorted({round(index * step) for index in range(count)})
        if len(indices) != count:
            _fail("variance: stride selection produced duplicate case ids")
        return [case_ids[index] for index in indices]

    a_cases = sorted(row["case_id"] for row in rows["a"])
    b_cases = _stride(sorted(row["case_id"] for row in rows["b"]), 30)
    d_cases = _stride(sorted(row["case_id"] for row in rows["d_native"]), 30)
    cases = [*a_cases, *b_cases, *d_cases]
    if len(cases) != VARIANCE_CASES:
        _fail(f"variance: built {len(cases)} cases, expected {VARIANCE_CASES}")
    return {
        "rule": (
            "40 A anchors (all) + 30 B + 30 D-native cases picked by uniform "
            "stride over the sorted case ids of each matrix; one case per "
            "structure, evaluated on init rows 0-4"
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
        "schema_version: 1",
        "split: lite",
        "total: " + str(coverage["total"]),
        "rule: >-",
        "  A: 10 single-task anchors (goal/l10/object/spatial = 3/2/3/2).",
        "  B: 10 rollback cases: one C0 control per suite plus two cases per",
        "  perturbation level (L0/L1/L2), suite-cycled, deterministic order.",
        "  D-native: 10 cases, one all_done_control plus early/mid/later x (L0, L1, L2),",
        "  picked in deterministic (window, level, param, task_idx) order.",
        "splits:",
    ]
    for key in ("a", "b", "d_native"):
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
    provisional_entry: list[str] = []
    for key, rel_path, _stem, expected_rows in MATRIX_FILES:
        entry = _file_entry(rel_path, _sha256(REPO_ROOT / rel_path), expected_rows)
        files.append(entry)
        if key == "d_compose_provisional":
            provisional_entry = list(entry)
    lines: list[str] = [
        "# LIBERO-Rollback dataset manifest -- generated by "
        "scripts/build_manifest.py; do not edit.",
        "# Deterministic: rebuild with `python scripts/build_manifest.py --check`.",
        "schema_version: 2",
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
    for key, _rel_path, _stem, expected_rows in MATRIX_FILES:
        lines.append(f"  {key}: {expected_rows}")
    lines.append("  c: 0")
    lines.append("files:")
    for entry in files:
        lines.extend(entry)
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
    lines.append("provisional:")
    lines.extend(provisional_entry)
    lines.append("c:")
    lines.append("  status: not_built")
    lines.append(
        "  note: "
        + _q(
            "C suite (120 n=2 structures + 40 n=3 structures) is Phase 2; the provisional "
            "D-compose matrix stays out of every executable split until C ships."
        )
    )
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
    print(f"[build_manifest] wrote {LITE_PATH} (30 cases) and {MANIFEST_PATH}")
    print(
        "[build_manifest] manifest sha256 "
        + hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
