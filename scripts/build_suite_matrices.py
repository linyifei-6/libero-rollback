#!/usr/bin/env python3
"""Build the two test-suite case matrices from the frozen base matrices.

Test suites (not A/B/C/D analysis dimensions):

* ``dataset/matrices/libero-rollback/completion-rollback.csv``
  B dimension: the base ``b-matrix.csv`` (442 cases), with
  ``test_suite=libero-rollback``, ``dimension=completion``.
* ``dataset/matrices/libero-rollback/in-execution-rollback.csv``
  C dimension: the base ``d-native-matrix.csv`` with
  ``window != all_done_control`` (180 cases), with
  ``test_suite=libero-rollback``, ``dimension=in-execution``.
D-intact / D-rollback are built by ``scripts/build_compose_suite.py`` from the
imported n=2 compose metadata, not from the legacy provisional CSV.

This script only reorganises frozen rows; it never invents rows/values.
Run with ``--check`` to verify the files are up to date.
"""

from __future__ import annotations

import argparse
import csv
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MATRICES = REPO_ROOT / "dataset" / "matrices"

EXTRA_COLUMNS = ("test_suite", "dimension", "arm")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise SystemExit(f"{path}: missing header")
        rows = list(reader)
        return list(reader.fieldnames), rows


def annotate(
    header: list[str],
    rows: list[dict[str, str]],
    *,
    test_suite: str,
    dimension: str,
    arm: Callable[[dict[str, str]], str],
) -> tuple[list[str], list[dict[str, str]]]:
    if any(column in header for column in EXTRA_COLUMNS):
        raise SystemExit(f"input already has suite columns: {header}")
    out_header = ["case_id", *EXTRA_COLUMNS, *[c for c in header if c != "case_id"]]
    out_rows = []
    for row in rows:
        out_row = {
            "case_id": row["case_id"],
            "test_suite": test_suite,
            "dimension": dimension,
            "arm": arm(row),
            **{column: row[column] for column in header if column != "case_id"},
        }
        # Rollback protocol floor: 600 post-injection steps (2026-11-21).
        # The legacy source matrices keep their frozen 300 reference; the
        # suite views carry the executable 600 value.
        if "repair_window" in out_row:
            out_row["repair_window"] = "600"
        out_rows.append(out_row)
    return out_header, out_rows


def write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build() -> list[tuple[Path, list[str], list[dict[str, str]]]]:
    b_header, b_rows = read_csv(MATRICES / "b-matrix.csv")
    b_header, b_rows = annotate(
        b_header,
        b_rows,
        test_suite="libero-rollback",
        dimension="completion",
        arm=lambda row: "control" if row["level"] == "C0" else "rollback",
    )

    c_header, c_source = read_csv(MATRICES / "d-native-matrix.csv")
    c_source = [row for row in c_source if row["window"] != "all_done_control"]
    c_header, c_rows = annotate(
        c_header,
        c_source,
        test_suite="libero-rollback",
        dimension="in-execution",
        arm=lambda row: "rollback",
    )

    return [
        (MATRICES / "libero-rollback" / "completion-rollback.csv", b_header, b_rows),
        (MATRICES / "libero-rollback" / "in-execution-rollback.csv", c_header, c_rows),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare, do not write")
    args = parser.parse_args()

    outputs = build()
    for path, header, rows in outputs:
        if args.check:
            if not path.is_file():
                raise SystemExit(f"[build_suite_matrices] missing {path}")
            existing = path.read_text(encoding="utf-8")
            if existing != _render(header, rows):
                raise SystemExit(f"[build_suite_matrices] out of date: {path}")
            print(f"[build_suite_matrices] OK {path.relative_to(REPO_ROOT)} ({len(rows)} rows)")
        else:
            write_csv(path, header, rows)
            print(f"[build_suite_matrices] wrote {path.relative_to(REPO_ROOT)} ({len(rows)} rows)")
    return 0


def _render(header: list[str], rows: list[dict[str, str]]) -> str:
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


if __name__ == "__main__":
    raise SystemExit(main())
