#!/usr/bin/env python3
"""Generate ``dataset/matrices/a-matrix.csv`` (A suite, 40 rows).

The A suite is the *single-task intact* anchor: one row per task key that
appears in the B matrix (10 Goal / 10 Object / 10 Spatial / 10 LIBERO-10), with
no perturbation.  It adds **no new data**: the instruction and the goal arity
are read verbatim from the upstream LIBERO BDDL of that task, and the init file
is referenced relative to ``LIBERO_HOME`` (see ``docs/SPEC.md`` §2–§3).

Usage::

    LIBERO_HOME=/path/to/LIBERO python scripts/build_a_matrix.py
    LIBERO_HOME=/path/to/LIBERO python scripts/build_a_matrix.py --check

``--check`` rebuilds the matrix in memory and exits non-zero on any diff; it
never writes.  The script is pure stdlib and does not import the package.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = REPO_ROOT / "dataset" / "matrices" / "b-matrix.csv"
DEFAULT_OUT = REPO_ROOT / "dataset" / "matrices" / "a-matrix.csv"

#: LIBERO suite id -> its directory name under ``bddl_files`` / ``init_files``.
SUITE_DIRS = {
    "goal": "libero_goal",
    "object": "libero_object",
    "spatial": "libero_spatial",
    "l10": "libero_10",
}

#: A-suite protocol constants (``docs/SPEC.md`` §3.2 / §5).
A_MAX_STEPS = 600
A_SEMANTICS = "intact"

HEADER = (
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

#: ``init_source`` is always relative to ``LIBERO_HOME`` (``docs/SPEC.md`` §2.3).
INIT_SOURCE_TEMPLATE = "libero/libero/init_files/{suite_dir}/{bddl_name}.pruned_init"

_LANGUAGE_RE = re.compile(r"\(:language\s+(.+?)\)\s*(?:\r?\n|$)", re.DOTALL)
_AND_RE = re.compile(r"^\(And\s+(.*)\)$", re.DOTALL)
_HEADER_RE = re.compile(r"\(:diff\s+(.*)\)\s*$", re.DOTALL)


def _fail(message: str, *, code: int = 2) -> None:
    raise SystemExit(f"[build_a_matrix] error: {message} (exit {code})")


def _asset_root(libero_home: Path) -> Path:
    """Locate the directory that directly contains ``bddl_files``/``init_files``.

    ``LIBERO_HOME`` is the upstream *repository* root, so the assets live in
    ``<root>/libero/libero``; the package directory or the assets parent are
    accepted as convenience fallbacks.
    """

    root = libero_home.expanduser()
    for candidate in (root / "libero" / "libero", root, root / "libero"):
        if (candidate / "bddl_files").is_dir() and (candidate / "init_files").is_dir():
            return candidate
    _fail(
        f"cannot locate bddl_files/init_files under {root} "
        f"(tried {root / 'libero' / 'libero'}, {root}, {root / 'libero'})"
    )
    raise AssertionError("unreachable")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        _fail(f"cannot read {path}: {error}")


def _balanced_block(text: str, start: int) -> str:
    """Return the balanced ``(...)`` block that starts at ``text[start] == '('``."""

    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    _fail("unbalanced parentheses while parsing a BDDL goal block")
    raise AssertionError("unreachable")


def parse_language(bddl_text: str) -> str:
    """Extract the ``(:language ...)`` string verbatim."""

    match = _LANGUAGE_RE.search(bddl_text)
    if match is None:
        _fail("BDDL has no (:language ...) declaration")
    return match.group(1).strip()


def parse_goal_atoms(bddl_text: str) -> list[str]:
    """Return the ``:goal`` predicate atoms (``And`` expanded, not canonicalised)."""

    marker = bddl_text.find("(:goal")
    if marker < 0:
        _fail("BDDL has no (:goal ...) block")
    block = _balanced_block(bddl_text, marker)
    inner = block[len("(:goal") : block.rindex(")")].strip()
    if not inner:
        _fail("empty :goal block")
    match = _AND_RE.match(inner)
    if match is None:
        return [inner]
    body = match.group(1)
    atoms: list[str] = []
    index = 0
    while index < len(body):
        char = body[index]
        if char == "(":
            atom = _balanced_block(body, index)
            atoms.append(atom)
            index += len(atom)
        elif char.isspace():
            index += 1
        else:
            _fail(f"unexpected token {char!r} in :goal And block")
    if not atoms:
        _fail(":goal And block contains no atoms")
    return atoms


def load_task_keys(matrix_path: Path) -> list[dict[str, str]]:
    """Return the unique ``(suite, task_idx)`` task keys of the B matrix."""

    try:
        with matrix_path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
    except OSError as error:
        _fail(f"cannot read B matrix {matrix_path}: {error}")
    if not rows:
        _fail(f"empty B matrix: {matrix_path}")
    missing = {"case_id", "suite", "task_idx", "bddl_name", "instruction"} - set(rows[0])
    if missing:
        _fail(f"{matrix_path}: missing columns {sorted(missing)}")

    tasks: dict[tuple[str, int], dict[str, str]] = {}
    for row in rows:
        suite = (row.get("suite") or "").strip()
        if suite not in SUITE_DIRS:
            _fail(f"{row.get('case_id')}: unsupported suite {suite!r}")
        try:
            task_idx = int(str(row.get("task_idx") or "").strip())
        except ValueError:
            _fail(f"{row.get('case_id')}: task_idx is not an integer")
        key = (suite, task_idx)
        entry = {
            "suite": suite,
            "task_idx": task_idx,
            "bddl_name": (row.get("bddl_name") or "").strip(),
            "instruction": (row.get("instruction") or "").strip(),
        }
        previous = tasks.get(key)
        if previous is not None and previous != entry:
            _fail(f"task key {key} maps to inconsistent rows in {matrix_path}")
        tasks[key] = entry
    if len(tasks) != 40:
        _fail(f"expected 40 task keys in the B matrix, found {len(tasks)}")
    return [tasks[key] for key in sorted(tasks)]


def build_rows(matrix_path: Path, libero_home: Path) -> list[dict[str, str]]:
    asset_root = _asset_root(libero_home)
    rows: list[dict[str, str]] = []
    for task in load_task_keys(matrix_path):
        suite = task["suite"]
        suite_dir = SUITE_DIRS[suite]
        bddl_name = task["bddl_name"]
        bddl_path = asset_root / "bddl_files" / suite_dir / f"{bddl_name}.bddl"
        init_path = asset_root / "init_files" / suite_dir / f"{bddl_name}.pruned_init"
        if not bddl_path.is_file():
            _fail(f"missing upstream BDDL: {bddl_path}")
        if not init_path.is_file():
            _fail(f"missing upstream init state: {init_path}")
        bddl_text = _read_text(bddl_path)
        language = parse_language(bddl_text)
        if language != task["instruction"]:
            _fail(
                f"instruction mismatch for {suite}/t{task['task_idx']:03d} "
                f"({bddl_name}): B matrix keeps {task['instruction']!r} but the BDDL says "
                f"{language!r}; the A<->B pairing requires the same instruction"
            )
        goals = parse_goal_atoms(bddl_text)
        rows.append(
            {
                "case_id": f"a-{suite}-t{task['task_idx']:03d}",
                "suite": suite,
                "task_idx": str(task["task_idx"]),
                "bddl_name": bddl_name,
                "instruction": language,
                "init_source": INIT_SOURCE_TEMPLATE.format(
                    suite_dir=suite_dir, bddl_name=bddl_name
                ),
                "n_goals": str(len(goals)),
                "semantics": A_SEMANTICS,
                "max_steps": str(A_MAX_STEPS),
            }
        )
    if len(rows) != 40:
        _fail(f"expected 40 A rows, built {len(rows)}")
    return rows


def render(rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(HEADER), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the A-suite matrix (40 single-task intact cases).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX, help="B matrix (task keys)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output A matrix")
    parser.add_argument(
        "--libero-home",
        type=Path,
        default=None,
        help="upstream LIBERO repository root (default: $LIBERO_HOME)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="rebuild in memory and fail on diff instead of writing",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    raw_home = args.libero_home or os.environ.get("LIBERO_HOME")
    if not raw_home:
        _fail("--libero-home is required (or set LIBERO_HOME to the upstream LIBERO checkout)")
    libero_home = Path(raw_home)
    if not libero_home.is_dir():
        _fail(f"LIBERO home is not a directory: {libero_home}")

    expected = render(build_rows(args.matrix, libero_home))
    expected_sha = sha256_text(expected)

    if args.check:
        if not args.out.is_file():
            _fail(f"--check: output does not exist: {args.out}", code=1)
        actual = args.out.read_text(encoding="utf-8")
        if actual != expected:
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
            _fail(
                f"--check: {args.out} is stale (first diff at line {first + 1}); "
                "re-run without --check",
                code=1,
            )
        print(f"[build_a_matrix] OK: {args.out} is up to date (sha256 {expected_sha})")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(expected.encode("utf-8"))
    print(f"[build_a_matrix] wrote 40 rows -> {args.out} (sha256 {expected_sha})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
