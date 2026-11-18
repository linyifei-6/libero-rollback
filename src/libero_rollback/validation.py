"""Dataset-level static validation (``docs/SPEC.md`` §1, §8, §9, §10).

The validator is deliberately pure-stdlib + PyYAML: it must run in the CPU-only
static job and never import the simulator. It never raises for bad datasets —
it returns a :class:`ValidationReport` with per-check error and warning lists so
``scripts/validate_dataset.py`` can print a full triage instead of only the
first failure.

What is checked:

* ``dataset/manifest.yaml``: version keys, LIBERO pin, counts, the four matrix
  files (path / SHA-256 / row count), splits and the provisional list;
* ``dataset/matrices/*.csv``: UTF-8 without BOM, ``case_id`` column, globally
  unique ids that match the frozen SPEC §4 naming scheme, row counts that
  agree with the manifest;
* ``dataset/lite.yaml``: N case ids, unique, all resolvable, identical to
  ``manifest.splits.lite``, with coverage warnings for the SPEC §10 rules;
* path hygiene: no absolute host paths, no CRLF CSVs, no BOMs anywhere in
  ``dataset/``.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

LIBERO_REPO = "https://github.com/Lifelong-Robot-Learning/LIBERO"
LIBERO_COMMIT = "f78abd68ee283de9f9be3c8f7e2a9ad60246e95c"
MANIFEST_GENERATOR = "scripts/build_manifest.py"
LITE_COUNT = 30

EXPECTED_COUNTS: Mapping[str, int] = {
    "a": 40,
    "b": 442,
    "d_native": 189,
    "d_compose_provisional": 360,
    "c": 0,
}

MATRIX_PATHS: Mapping[str, str] = {
    "a": "dataset/matrices/a-matrix.csv",
    "b": "dataset/matrices/b-matrix.csv",
    "d_native": "dataset/matrices/d-native-matrix.csv",
    "d_compose_provisional": "dataset/matrices/d-compose-provisional.csv",
}

REQUIRED_EXECUTION_SPLITS = frozenset({"a", "b", "d-native"})

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DATASET_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[.\-+][0-9A-Za-z.\-]+)?$")
_CSV_SUFFIXES = frozenset({".csv"})
_TEXT_SUFFIXES = frozenset({".csv", ".yaml", ".yml", ".json", ".jsonl", ".md", ".txt"})

_CASE_ID_PATTERNS: Mapping[str, re.Pattern[str]] = {
    "a": re.compile(r"^a-(?:goal|object|spatial|l10)-t\d{3}$"),
    "b": re.compile(
        r"^b-(?:goal|object|spatial|l10)-t\d{3}-(?:c0|"
        r"(?:g|s1|s2|both|pre)-(?:l0|l1-(?:d03|d06|d10)|l2-(?:r30|r60|r90)))$"
    ),
    "c": re.compile(r"^c-s\d{4}$"),
    "d": re.compile(
        r"^d-(?:l10-t\d{3}-(?:c0|"
        r"(?:early|mid|later)-(?:l0|l1-(?:d03|d06|d10)|l2-(?:r30|r60|r90)))"
        r"|compose-s\d{4}-(?:early|mid|later)-l0)$"
    ),
}

# Host-path detectors intentionally contain no machine-specific literals: a
# dedicated independence test greps the sources for host markers, and a checker
# that hardcodes them would trip its own guard (README §7.1, SPEC §12).
_ABSOLUTE_PATH_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Absolute POSIX paths: a leading slash plus at least one path segment. URLs
    # are excluded by the look-behind on ":" (a URL has a scheme before its slash).
    (re.compile(r"(?<![:\w/$.~])/(?:[A-Za-z0-9_.-]+/)+"), "absolute POSIX path"),
    # Windows drive-qualified path (C:\... or C:/...).
    (re.compile(r"(?<![\w.])[A-Za-z]:[\\/]"), "windows drive path"),
    # UNC path (\\server\share) and home-relative shorthand (~/...).
    (re.compile(r"\\\\[A-Za-z0-9_.-]+[\\/]"), "UNC path"),
    (re.compile(r"(?<![\w$])~/"), "home-relative path"),
)


class DatasetError(ValueError):
    """Raised when a dataset document cannot be parsed or is not a mapping."""


# ---------------------------------------------------------------------------
# report types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Check:
    """Outcome of one validation check."""

    name: str
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    detail: str = ""

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class ValidationReport:
    """Structured dataset validation result (never raised, always returned)."""

    dataset_root: Path
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    @property
    def errors(self) -> list[str]:
        return [error for check in self.checks for error in check.errors]

    @property
    def warnings(self) -> list[str]:
        return [warning for check in self.checks for warning in check.warnings]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "dataset_root": str(self.dataset_root),
            "checks": [
                {
                    "name": check.name,
                    "ok": check.ok,
                    "detail": check.detail,
                    "errors": list(check.errors),
                    "warnings": list(check.warnings),
                }
                for check in self.checks
            ],
        }

    def format(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        lines = [f"dataset validation: {status} ({self.dataset_root})"]
        for check in self.checks:
            marker = "ok" if check.ok else "FAIL"
            detail = f": {check.detail}" if check.detail else ""
            lines.append(f"  [{marker}] {check.name}{detail}")
            for warning in check.warnings:
                lines.append(f"      warning: {warning}")
            for error in check.errors:
                lines.append(f"      error: {error}")
        lines.append(
            f"  summary: {len(self.errors)} error(s), {len(self.warnings)} warning(s)"
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def load_yaml(path: str | Path) -> Any:
    """Load a YAML document (UTF-8) or raise :class:`DatasetError`."""

    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise DatasetError(f"cannot read {path}: {error}") from error
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise DatasetError(f"invalid YAML in {path}: {error}") from error


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _display(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _resolve_repo_path(dataset_root: Path, relative: str) -> Path | None:
    """Resolve a repo-relative manifest path (``dataset/...`` style)."""

    candidate = Path(relative)
    if candidate.is_absolute():
        return None
    for base in (dataset_root.parent, dataset_root):
        path = base / candidate
        if path.is_file():
            return path
    return None


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        header = list(reader.fieldnames or [])
    return header, rows


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _looks_absolute_path(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    if text.startswith(("/", "\\")):
        return True
    if re.match(r"^[A-Za-z]:[\\/]", text):
        return True
    return text.startswith("~/")


def _walk_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_strings(item)


def _validate_case_id(case_id: str) -> str | None:
    family = case_id.split("-", 1)[0]
    pattern = _CASE_ID_PATTERNS.get(family)
    if pattern is None:
        return f"unknown case_id family: {case_id!r}"
    if pattern.fullmatch(case_id) is None:
        return f"case_id does not match the frozen SPEC §4 naming scheme: {case_id!r}"
    return None


def _extract_case_ids(document: Any) -> list[str]:
    """Extract case ids from the supported ``lite.yaml`` shapes."""

    if isinstance(document, list):
        entries: list[Any] = document
    elif isinstance(document, Mapping):
        entries = document.get("cases") or document.get("case_ids") or []
        if not isinstance(entries, list):
            raise DatasetError("lite.yaml must define a list under 'cases'")
    else:
        raise DatasetError("lite.yaml must be a mapping or a list")
    case_ids: list[str] = []
    for entry in entries:
        if isinstance(entry, str):
            case_ids.append(entry.strip())
        elif isinstance(entry, Mapping) and isinstance(entry.get("case_id"), str):
            case_ids.append(entry["case_id"].strip())
        else:
            raise DatasetError(f"lite case entries must be case-id strings, got {entry!r}")
    return case_ids


# ---------------------------------------------------------------------------
# manifest check
# ---------------------------------------------------------------------------


def _validate_file_entry(
    dataset_root: Path,
    entry: Any,
    seen: set[str],
    errors: list[str],
    warnings: list[str],
    row_counts: dict[str, int],
) -> None:
    if not isinstance(entry, Mapping):
        errors.append("manifest file entries must be mappings with path/sha256/rows")
        return
    relative = entry.get("path")
    if not isinstance(relative, str) or not relative.strip():
        errors.append("manifest file entries must contain a path")
        return
    relative = relative.strip()
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        errors.append(f"unsafe manifest path: {relative}")
        return
    if relative in seen:
        errors.append(f"duplicate manifest path: {relative}")
        return
    seen.add(relative)
    target = _resolve_repo_path(dataset_root, relative)
    if target is None:
        errors.append(f"manifest file is missing: {relative}")
        return
    expected_sha = entry.get("sha256")
    if not isinstance(expected_sha, str) or _SHA256_RE.fullmatch(expected_sha) is None:
        errors.append(f"manifest SHA-256 is missing or malformed: {relative}")
    else:
        actual = sha256_file(target)
        if actual != expected_sha:
            errors.append(
                f"SHA-256 mismatch for {relative}: expected {expected_sha}, got {actual}"
            )
    rows = entry.get("rows")
    if target.suffix.lower() in _CSV_SUFFIXES:
        try:
            header, data_rows = _read_csv_rows(target)
        except (OSError, UnicodeDecodeError, csv.Error) as error:
            errors.append(f"cannot read CSV {relative}: {error}")
            return
        if not header:
            errors.append(f"CSV has no header row: {relative}")
        row_counts[relative] = len(data_rows)
        if isinstance(rows, bool) or not isinstance(rows, int):
            errors.append(f"manifest rows must be an integer for {relative}")
        elif rows != len(data_rows):
            errors.append(
                f"manifest rows mismatch for {relative}: manifest says {rows}, file has "
                f"{len(data_rows)}"
            )
    elif rows is not None and not isinstance(rows, int):
        warnings.append(f"manifest rows for non-CSV {relative} is not an integer")


def _manifest_check(
    dataset_root: Path,
    expected_counts: Mapping[str, int],
) -> tuple[Check, Mapping[str, Any] | None]:
    name = "manifest"
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = dataset_root / "manifest.yaml"
    if not manifest_path.is_file():
        return Check(name, (f"missing {manifest_path}",)), None
    try:
        manifest = load_yaml(manifest_path)
    except DatasetError as error:
        return Check(name, (str(error),)), None
    if not isinstance(manifest, Mapping):
        return Check(name, ("manifest.yaml must contain a mapping",)), None

    if manifest.get("schema_version") != 2:
        errors.append(f"manifest.schema_version must be 2, got {manifest.get('schema_version')!r}")
    dataset_version = manifest.get("dataset_version")
    version_valid = isinstance(dataset_version, str) and bool(
        _DATASET_VERSION_RE.fullmatch(dataset_version)
    )
    if not version_valid:
        errors.append(f"manifest.dataset_version is not a version string: {dataset_version!r}")
    if manifest.get("generated_by") != MANIFEST_GENERATOR:
        errors.append(f"manifest.generated_by must be {MANIFEST_GENERATOR!r}")
    libero = manifest.get("libero")
    if not isinstance(libero, Mapping):
        errors.append("manifest.libero must be a mapping with repo/commit")
    else:
        if libero.get("repo") != LIBERO_REPO:
            errors.append(f"manifest.libero.repo must be {LIBERO_REPO!r}")
        if libero.get("commit") != LIBERO_COMMIT:
            errors.append(f"manifest.libero.commit must be pinned to {LIBERO_COMMIT}")
    counts = manifest.get("counts")
    if not isinstance(counts, Mapping):
        errors.append("manifest.counts must be a mapping")
        counts = {}
    for key, expected in expected_counts.items():
        actual = counts.get(key)
        if isinstance(actual, bool) or not isinstance(actual, int):
            errors.append(f"manifest.counts.{key} must be an integer, got {actual!r}")
        elif actual != expected:
            errors.append(f"manifest.counts.{key} must be {expected}, got {actual}")

    seen: set[str] = set()
    row_counts: dict[str, int] = {}
    files = manifest.get("files")
    if not isinstance(files, list):
        errors.append("manifest.files must be a list")
        files = []
    for entry in files:
        _validate_file_entry(dataset_root, entry, seen, errors, warnings, row_counts)
    provisional = manifest.get("provisional") or []
    if not isinstance(provisional, list):
        errors.append("manifest.provisional must be a list of path mappings")
        provisional = []
    for entry in provisional:
        if isinstance(entry, str):
            # Tolerate the compact form as well: a bare path is still verifiable.
            entry = {"path": entry}
        # The provisional list is an annotation: a path that is already part of
        # ``files`` is validated once and must not count as a duplicate.
        if isinstance(entry, Mapping) and entry.get("path") in seen:
            continue
        _validate_file_entry(dataset_root, entry, seen, errors, warnings, row_counts)

    for key, expected in expected_counts.items():
        relative = MATRIX_PATHS.get(key)
        if relative is None:
            continue
        if expected > 0 and relative not in seen:
            errors.append(
                f"counts.{key} is {expected} but {relative} is not listed in manifest files"
            )
        if relative in row_counts and row_counts[relative] != expected:
            errors.append(
                f"counts.{key} is {expected} but {relative} has {row_counts[relative]} data rows"
            )

    splits = manifest.get("splits")
    if not isinstance(splits, Mapping):
        errors.append("manifest.splits must be a mapping")
    else:
        lite_split = splits.get("lite")
        if not isinstance(lite_split, list):
            errors.append("manifest.splits.lite must be a list of case ids")
        core = splits.get("core")
        if core is not None and not isinstance(core, list):
            errors.append("manifest.splits.core must be a list")
        elif core is not None and {str(item) for item in core} != REQUIRED_EXECUTION_SPLITS:
            warnings.append(
                "manifest.splits.core differs from the Phase 1 execution split "
                f"{sorted(REQUIRED_EXECUTION_SPLITS)}"
            )

    if not (dataset_root / "README.md").is_file():
        warnings.append("dataset/README.md (data-card draft) is missing")
    detail = (
        f"counts={dict(sorted(counts.items()))} files={len(files)}+{len(provisional)} provisional"
    )
    return Check(name, tuple(errors), tuple(warnings), detail), manifest


# ---------------------------------------------------------------------------
# matrix check
# ---------------------------------------------------------------------------


def _matrix_check(
    dataset_root: Path,
    expected_counts: Mapping[str, int],
) -> tuple[Check, dict[str, dict[str, str]]]:
    name = "matrices"
    errors: list[str] = []
    warnings: list[str] = []
    matrix_dir = dataset_root / "matrices"
    case_rows: dict[str, dict[str, str]] = {}
    if not matrix_dir.is_dir():
        return Check(name, (f"missing directory {matrix_dir}",)), case_rows
    for key, relative in MATRIX_PATHS.items():
        expected = expected_counts.get(key, 0)
        if expected > 0 and _resolve_repo_path(dataset_root, relative) is None:
            errors.append(f"required matrix file is missing: {relative}")
    files = sorted(matrix_dir.glob("*.csv"))
    if not files:
        errors.append(f"no matrix CSV files under {matrix_dir}")
    for path in files:
        relative = _display(path, dataset_root)
        if path.read_bytes()[:3] == b"\xef\xbb\xbf":
            errors.append(f"{relative}: UTF-8 BOM is forbidden (docs/SPEC.md §9.3)")
        try:
            header, rows = _read_csv_rows(path)
        except (OSError, UnicodeDecodeError, csv.Error) as error:
            errors.append(f"{relative}: cannot read CSV: {error}")
            continue
        if "case_id" not in header:
            errors.append(f"{relative}: missing 'case_id' column")
            continue
        if not rows:
            warnings.append(f"{relative}: matrix has a header but no data rows")
        for line_number, row in enumerate(rows, start=2):
            case_id = _text(row.get("case_id"))
            if not case_id:
                errors.append(f"{relative}:{line_number}: empty case_id")
                continue
            problem = _validate_case_id(case_id)
            if problem is not None:
                errors.append(f"{relative}:{line_number}: {problem}")
            previous = case_rows.get(case_id)
            if previous is not None:
                errors.append(
                    f"duplicate case_id {case_id!r} in {relative} and {previous['_file']}"
                )
                continue
            case_rows[case_id] = {"_file": relative, **{k: _text(v) for k, v in row.items()}}
    detail = f"{len(files)} CSV file(s), {len(case_rows)} unique case_id(s)"
    return Check(name, tuple(errors), tuple(warnings), detail), case_rows


# ---------------------------------------------------------------------------
# lite split check
# ---------------------------------------------------------------------------


def _lite_check(
    dataset_root: Path,
    case_rows: Mapping[str, Mapping[str, str]],
    manifest: Mapping[str, Any] | None,
    lite_count: int,
) -> tuple[Check, list[str]]:
    name = "lite split"
    errors: list[str] = []
    warnings: list[str] = []
    lite_path = dataset_root / "lite.yaml"
    if not lite_path.is_file():
        return Check(name, (f"missing {lite_path}",)), []
    try:
        document = load_yaml(lite_path)
        case_ids = _extract_case_ids(document)
    except DatasetError as error:
        return Check(name, (str(error),)), []
    if len(case_ids) != lite_count:
        errors.append(f"lite split must contain {lite_count} case ids, got {len(case_ids)}")
    duplicates = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
    if duplicates:
        errors.append(f"lite split contains duplicate case ids: {duplicates}")
    unknown = sorted(case_id for case_id in set(case_ids) if case_id not in case_rows)
    if unknown:
        errors.append(f"lite split references unknown case ids: {unknown}")
    if isinstance(manifest, Mapping):
        splits = manifest.get("splits")
        lite_split = splits.get("lite") if isinstance(splits, Mapping) else None
        if isinstance(lite_split, list):
            declared = [str(item).strip() for item in lite_split]
            if set(declared) != set(case_ids):
                errors.append("manifest.splits.lite does not match dataset/lite.yaml cases")
            elif declared != case_ids:
                warnings.append("manifest.splits.lite uses a different order than lite.yaml")
        else:
            errors.append("manifest.splits.lite must list the lite case ids")
    warnings.extend(_lite_coverage_warnings(case_ids, case_rows))
    detail = f"{len(case_ids)} case id(s)"
    return Check(name, tuple(errors), tuple(warnings), detail), case_ids


def _lite_coverage_warnings(
    case_ids: list[str],
    case_rows: Mapping[str, Mapping[str, str]],
) -> list[str]:
    warnings: list[str] = []
    known = [(case_id, case_rows[case_id]) for case_id in case_ids if case_id in case_rows]
    a_suites = {row.get("suite", "") for case_id, row in known if case_id.startswith("a-")}
    if a_suites and a_suites != {"goal", "object", "spatial", "l10"}:
        warnings.append(f"lite A cases do not cover all four suites: {sorted(a_suites)}")
    b_levels = {
        row.get("level", "").upper()
        for case_id, row in known
        if case_id.startswith("b-")
    }
    if b_levels and not {"C0", "L0", "L1", "L2"}.issubset(b_levels):
        warnings.append(f"lite B cases do not cover C0/L0/L1/L2: {sorted(b_levels)}")
    d_windows = {
        row.get("window", "")
        for case_id, row in known
        if case_id.startswith("d-")
    }
    if d_windows and not {"early", "mid", "later", "all_done_control"}.issubset(d_windows):
        warnings.append(f"lite D cases do not cover all windows: {sorted(d_windows)}")
    return warnings


# ---------------------------------------------------------------------------
# path hygiene check
# ---------------------------------------------------------------------------


def _path_check(dataset_root: Path) -> Check:
    name = "path hygiene"
    errors: list[str] = []
    warnings: list[str] = []
    scanned = 0
    if not dataset_root.is_dir():
        return Check(name, (f"missing dataset directory {dataset_root}",))
    for path in sorted(dataset_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        relative = _display(path, dataset_root)
        raw = path.read_bytes()
        if raw[:3] == b"\xef\xbb\xbf":
            errors.append(f"{relative}: UTF-8 BOM is forbidden")
        if path.suffix.lower() in _CSV_SUFFIXES and b"\r" in raw:
            errors.append(f"{relative}: CSV must use LF line endings")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"{relative}: not valid UTF-8")
            continue
        scanned += 1
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern, label in _ABSOLUTE_PATH_PATTERNS:
                if pattern.search(line):
                    errors.append(
                        f"{relative}:{line_number}: absolute host path ({label}): "
                        f"{line.strip()[:120]}"
                    )
    for structured in ("manifest.yaml", "sources.yaml", "lite.yaml"):
        path = dataset_root / structured
        if not path.is_file():
            continue
        try:
            document = load_yaml(path)
        except DatasetError as error:
            errors.append(str(error))
            continue
        for value in _walk_strings(document):
            if _looks_absolute_path(value):
                errors.append(f"{structured}: absolute path in value: {value[:120]}")
    detail = f"{scanned} text file(s) scanned"
    return Check(name, tuple(errors), tuple(warnings), detail)


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def validate_dataset(
    dataset_root: str | Path,
    *,
    expected_counts: Mapping[str, int] | None = None,
    lite_count: int = LITE_COUNT,
) -> ValidationReport:
    """Validate a ``dataset/`` directory and return a structured report.

    The defaults enforce the frozen Phase 1 counts (40 A / 442 B / 189
    D-native / 360 provisional D-compose / 0 C) and the 30-case lite split.
    The keyword overrides exist for unit tests with tiny fixtures; production
    callers should not pass them.
    """

    root = Path(dataset_root)
    counts = dict(EXPECTED_COUNTS if expected_counts is None else expected_counts)
    manifest_check, manifest = _manifest_check(root, counts)
    matrix_check, case_rows = _matrix_check(root, counts)
    lite_check, _ = _lite_check(root, case_rows, manifest, lite_count)
    checks = [manifest_check, matrix_check, lite_check, _path_check(root)]
    return ValidationReport(dataset_root=root, checks=checks)


def check_manifest(
    dataset_root: str | Path,
    *,
    expected_counts: Mapping[str, int] | None = None,
) -> list[str]:
    counts = dict(EXPECTED_COUNTS if expected_counts is None else expected_counts)
    check, _ = _manifest_check(Path(dataset_root), counts)
    return list(check.errors)


def check_matrices(
    dataset_root: str | Path,
    *,
    expected_counts: Mapping[str, int] | None = None,
) -> list[str]:
    counts = dict(EXPECTED_COUNTS if expected_counts is None else expected_counts)
    check, _ = _matrix_check(Path(dataset_root), counts)
    return list(check.errors)


def check_lite(dataset_root: str | Path, *, lite_count: int = LITE_COUNT) -> list[str]:
    root = Path(dataset_root)
    _, manifest = _manifest_check(root, dict(EXPECTED_COUNTS))
    _, case_rows = _matrix_check(root, dict(EXPECTED_COUNTS))
    check, _ = _lite_check(root, case_rows, manifest, lite_count)
    return list(check.errors)


def check_path_hygiene(dataset_root: str | Path) -> list[str]:
    return list(_path_check(Path(dataset_root)).errors)
