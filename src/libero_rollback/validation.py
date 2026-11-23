"""Dataset-level static validation (``docs/SPEC.md`` §1, §8, §9, §10).

The validator is deliberately pure-stdlib + PyYAML: it must run in the CPU-only
static job and never import the simulator. It never raises for bad datasets —
it returns a :class:`ValidationReport` with per-check error and warning lists so
``scripts/validate_dataset.py`` can print a full triage instead of only the
first failure.

Schema v3 (2026-11-21) validates the base-only suite matrices:

* ``a``          ``dataset/matrices/a-matrix.csv``                             40
* ``b``          ``dataset/matrices/libero-rollback/completion-rollback.csv``  442
* ``c``          ``dataset/matrices/libero-rollback/in-execution-rollback.csv`` 180
* ``d_intact``   ``dataset/matrices/libero-compose/intact.csv``                176
* ``d_rollback`` ``dataset/matrices/libero-compose/rollback.csv``              528

The legacy ``b-matrix.csv`` / ``d-native-matrix.csv`` /
``d-compose-provisional.csv`` files stay on disk but are explicitly legacy:
they are listed under ``manifest.legacy`` and are never part of an executable
split.  They are not hashed or row-counted by this module.

What is checked:

* ``dataset/manifest.yaml``: schema version, LIBERO pin, canonical counts,
  the five matrix files (path / SHA-256 / row count), the canonical splits,
  the legacy annotation and an optional ``provisional`` annotation list;
* ``dataset/matrices``: the five canonical CSVs are UTF-8 without BOM, carry a
  ``case_id`` column, have globally unique ids that match the frozen naming
  scheme, carry the expected row counts and obey their suite contracts;
* ``dataset/lite.yaml``: 30 case ids, unique, all resolvable in the canonical
  matrices, identical to ``manifest.splits.lite``, 10 A / 10 B / 5 C / 2 D-intact
  / 3 D-rollback, with hard rules (C never uses C0, D-intact is valid n=2) and
  coverage warnings for the SPEC §10 rules;
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
MANIFEST_SCHEMA_VERSION = 3
LITE_SCHEMA_VERSION = 2
LITE_COUNT = 30

#: Canonical base-only suite matrices (schema v3).
EXPECTED_COUNTS: Mapping[str, int] = {
    "a": 40,
    "b": 442,
    "c": 180,
    "d_intact": 176,
    "d_rollback": 528,
}

MATRIX_PATHS: Mapping[str, str] = {
    "a": "dataset/matrices/a-matrix.csv",
    "b": "dataset/matrices/libero-rollback/completion-rollback.csv",
    "c": "dataset/matrices/libero-rollback/in-execution-rollback.csv",
    "d_intact": "dataset/matrices/libero-compose/intact.csv",
    "d_rollback": "dataset/matrices/libero-compose/rollback.csv",
}

#: Every canonical suite is part of the executable ``core`` split.
CORE_SPLIT = ("a", "b", "c", "d_intact", "d_rollback")

#: Lite quotas: 10 A + 10 B + 5 C + 5 D (2 intact + 3 rollback).
LITE_GROUPS: Mapping[str, int] = {
    "a": 10,
    "b": 10,
    "c": 5,
    "d_intact": 2,
    "d_rollback": 3,
}

#: Legacy files stay on disk but are not executable; counts are provenance.
LEGACY_COUNTS: Mapping[str, int] = {
    "b": 442,
    "d_native": 189,
    "d_compose_provisional": 360,
}

LEGACY_PATHS: Mapping[str, str] = {
    "b": "dataset/matrices/b-matrix.csv",
    "d_native": "dataset/matrices/d-native-matrix.csv",
    "d_compose_provisional": "dataset/matrices/d-compose-provisional.csv",
}

B_SUITES = frozenset({"goal", "object", "spatial", "l10"})
C_WINDOWS = frozenset({"early", "mid", "later"})
D_WINDOWS = frozenset({"early", "mid", "later"})
LEVEL_PARAMS = frozenset(
    {
        ("C0", ""),
        ("L0", ""),
        ("L1", "d03"),
        ("L1", "d06"),
        ("L1", "d10"),
        ("L2", "r30"),
        ("L2", "r60"),
        ("L2", "r90"),
    }
)

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
    # C reuses the frozen D-native ids, but never the all_done C0 control.
    "d": re.compile(
        r"^d-l10-t\d{3}-(?:early|mid|later)-"
        r"(?:l0|l1-(?:d03|d06|d10)|l2-(?:r30|r60|r90))$"
    ),
    "compose": re.compile(
        r"^compose-(?:intact-[a-z0-9_]+|rollback-[a-z0-9_]+-(?:early|mid|later)-l0)$"
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
        return f"case_id does not match the frozen naming scheme: {case_id!r}"
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


def _check_legacy(
    dataset_root: Path,
    legacy: Any,
    errors: list[str],
    warnings: list[str],
) -> int:
    if legacy is None:
        return 0
    if not isinstance(legacy, Mapping):
        errors.append("manifest.legacy must be a mapping when present")
        return 0
    counts = legacy.get("counts")
    if counts is not None:
        if not isinstance(counts, Mapping):
            errors.append("manifest.legacy.counts must be a mapping")
        else:
            for key, expected in LEGACY_COUNTS.items():
                actual = counts.get(key)
                if isinstance(actual, bool) or not isinstance(actual, int):
                    errors.append(f"manifest.legacy.counts.{key} must be an integer")
                elif actual != expected:
                    errors.append(
                        f"manifest.legacy.counts.{key} must be {expected}, got {actual}"
                    )
    files = legacy.get("files") or []
    if not isinstance(files, list):
        errors.append("manifest.legacy.files must be a list of paths")
        return 0
    for relative in files:
        if not isinstance(relative, str):
            errors.append(f"manifest.legacy.files entry is not a path: {relative!r}")
            continue
        if _resolve_repo_path(dataset_root, relative) is None:
            warnings.append(f"legacy provenance path is missing: {relative}")
    return len(files)


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

    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        errors.append(
            "manifest.schema_version must be "
            f"{MANIFEST_SCHEMA_VERSION}, got {manifest.get('schema_version')!r}"
        )
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
    for key in counts:
        if key not in expected_counts:
            warnings.append(f"manifest.counts has an unexpected key: {key!r}")

    seen: set[str] = set()
    row_counts: dict[str, int] = {}
    files = manifest.get("files")
    if not isinstance(files, list):
        errors.append("manifest.files must be a list")
        files = []
    for entry in files:
        _validate_file_entry(dataset_root, entry, seen, errors, warnings, row_counts)

    expected_paths = set(MATRIX_PATHS.values())
    for relative in sorted(expected_paths - seen):
        errors.append(f"manifest.files is missing the canonical matrix: {relative}")
    for relative in sorted(seen - expected_paths):
        warnings.append(f"manifest.files lists a non-canonical entry: {relative}")

    legacy_count = _check_legacy(dataset_root, manifest.get("legacy"), errors, warnings)

    # ``provisional`` is no longer required (D definitions are built), but a
    # legacy manifest may still annotate a non-executable file.  Validate it
    # when present instead of rejecting the document.
    provisional = manifest.get("provisional") or []
    if not isinstance(provisional, list):
        errors.append("manifest.provisional must be a list of path mappings when present")
        provisional = []
    for entry in provisional:
        if isinstance(entry, str):
            entry = {"path": entry}
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
        elif core is not None and [str(item) for item in core] != list(CORE_SPLIT):
            warnings.append(
                "manifest.splits.core differs from the canonical base-only split "
                f"{list(CORE_SPLIT)}"
            )

    if not (dataset_root / "README.md").is_file():
        warnings.append("dataset/README.md (data-card draft) is missing")
    detail = (
        f"counts={dict(sorted(counts.items()))} files={len(files)} "
        f"legacy={legacy_count} provisional={len(provisional)}"
    )
    return Check(name, tuple(errors), tuple(warnings), detail), manifest


# ---------------------------------------------------------------------------
# matrix check
# ---------------------------------------------------------------------------


def _matrix_row_errors(key: str, row: Mapping[str, str]) -> list[str]:
    """Suite-specific contract checks for one canonical matrix row."""

    case_id = row.get("case_id", "?")
    errors: list[str] = []
    level = _text(row.get("level"))
    param = _text(row.get("param"))
    window = _text(row.get("window"))
    relation = _text(row.get("expected_relation_after")).lower()
    repair = _text(row.get("repair_window"))

    if key == "a":
        if _text(row.get("suite")) not in B_SUITES:
            errors.append(f"{case_id}: unknown suite {row.get('suite')!r}")
        return errors

    if key == "b":
        if (level, param) not in LEVEL_PARAMS:
            errors.append(f"{case_id}: unsupported level/param {(level, param)}")
        if repair != "600":
            errors.append(f"{case_id}: repair_window must be 600, got {repair!r}")
        expected = "true" if level == "C0" else "false"
        if relation != expected:
            errors.append(f"{case_id}: expected_relation_after must be {expected!r}")
        return errors

    if key == "c":
        if level not in {"L0", "L1", "L2"} or (level, param) not in LEVEL_PARAMS:
            errors.append(f"{case_id}: C supports L0/L1/L2 only, got {(level, param)}")
        if window not in C_WINDOWS:
            errors.append(f"{case_id}: C window must be early/mid/later, got {window!r}")
        if repair != "600":
            errors.append(f"{case_id}: repair_window must be 600, got {repair!r}")
        if relation != "false":
            errors.append(f"{case_id}: C must expect the relation to become false")
        return errors

    if key == "d_intact":
        if level != "INTACT" or param:
            errors.append(f"{case_id}: D-intact must be level INTACT without param")
        if _text(row.get("valid")).lower() != "true":
            errors.append(f"{case_id}: D-intact rows must be valid")
        if _text(row.get("n_atoms")) != "2":
            errors.append(f"{case_id}: D-intact must be an n=2 structure")
        if repair != "0":
            errors.append(f"{case_id}: D-intact repair_window must be 0")
        if relation != "true":
            errors.append(f"{case_id}: D-intact must expect the relation to stay true")
        return errors

    if key == "d_rollback":
        if level != "L0" or param:
            errors.append(f"{case_id}: D-rollback must be level L0 without param")
        if window not in D_WINDOWS:
            errors.append(f"{case_id}: D-rollback window must be early/mid/later")
        if repair != "600":
            errors.append(f"{case_id}: D-rollback repair_window must be 600")
        if relation != "false":
            errors.append(f"{case_id}: D-rollback must expect the relation to become false")
        if _text(row.get("valid")).lower() != "true":
            errors.append(f"{case_id}: D-rollback rows must be valid")
        return errors

    return errors


def _matrix_check(
    dataset_root: Path,
    expected_counts: Mapping[str, int],
) -> tuple[Check, dict[str, dict[str, str]]]:
    name = "matrices"
    errors: list[str] = []
    warnings: list[str] = []
    case_rows: dict[str, dict[str, str]] = {}
    structs: dict[str, set[str]] = {"d_intact": set(), "d_rollback": set()}
    for key, relative in MATRIX_PATHS.items():
        expected = expected_counts.get(key, 0)
        target = _resolve_repo_path(dataset_root, relative)
        if target is None:
            if expected > 0:
                errors.append(f"required matrix file is missing: {relative}")
            continue
        try:
            header, rows = _read_csv_rows(target)
        except (OSError, UnicodeDecodeError, csv.Error) as error:
            errors.append(f"{relative}: cannot read CSV: {error}")
            continue
        if "case_id" not in header:
            errors.append(f"{relative}: missing 'case_id' column")
            continue
        if expected and len(rows) != expected:
            errors.append(f"{relative}: expected {expected} rows, found {len(rows)}")
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
            case_rows[case_id] = {
                "_file": relative,
                "_matrix": key,
                **{k: _text(v) for k, v in row.items()},
            }
            for problem in _matrix_row_errors(key, row):
                errors.append(f"{relative}:{problem}")
            if key in structs:
                struct_id = _text(row.get("struct_id"))
                if struct_id:
                    structs[key].add(struct_id)
    if structs["d_intact"] and structs["d_rollback"] and (
        structs["d_intact"] != structs["d_rollback"]
    ):
        only_intact = sorted(structs["d_intact"] - structs["d_rollback"])[:5]
        only_rollback = sorted(structs["d_rollback"] - structs["d_intact"])[:5]
        errors.append(
            "D-intact and D-rollback structure ids differ: "
            f"only intact={only_intact}, only rollback={only_rollback}"
        )
    detail = f"{len(MATRIX_PATHS)} canonical CSV file(s), {len(case_rows)} unique case_id(s)"
    return Check(name, tuple(errors), tuple(warnings), detail), case_rows


# ---------------------------------------------------------------------------
# lite split check
# ---------------------------------------------------------------------------


def _lite_group_errors(
    document: Mapping[str, Any],
    case_ids: list[str],
    case_rows: Mapping[str, Mapping[str, str]],
) -> list[str]:
    errors: list[str] = []
    splits = document.get("splits")
    if not isinstance(splits, Mapping):
        return ["lite.yaml.splits must be a mapping of the five lite groups"]
    if set(splits) != set(LITE_GROUPS):
        errors.append(
            "lite.yaml.splits must contain exactly "
            f"{sorted(LITE_GROUPS)}, got {sorted(splits)}"
        )
        return errors
    union: list[str] = []
    grouped: dict[str, list[str]] = {}
    for group, wanted in LITE_GROUPS.items():
        entries = splits.get(group)
        if not isinstance(entries, list) or not all(isinstance(item, str) for item in entries):
            errors.append(f"lite.yaml.splits.{group} must be a list of case ids")
            continue
        grouped[group] = entries
        if len(entries) != wanted:
            errors.append(
                f"lite.yaml.splits.{group} must contain {wanted} case ids, got {len(entries)}"
            )
        union.extend(entries)
    if sorted(union) != sorted(case_ids):
        errors.append("lite.yaml.splits groups do not union to lite.yaml.cases")

    for group, entries in grouped.items():
        for case_id in entries:
            row = case_rows.get(case_id)
            if row is None:
                continue
            if row.get("_matrix") != group:
                errors.append(
                    f"lite.yaml case {case_id!r} is in group {group!r} but belongs to "
                    f"matrix {row.get('_matrix')!r}"
                )
    for case_id in grouped.get("c", []):
        row = case_rows.get(case_id, {})
        if row.get("level") == "C0" or row.get("window") == "all_done_control":
            errors.append(f"lite.yaml C case {case_id!r} must not be a C0/all_done control")
    for case_id in grouped.get("d_intact", []):
        row = case_rows.get(case_id, {})
        if row.get("valid", "").lower() != "true" or row.get("n_atoms") != "2":
            errors.append(f"lite.yaml D-intact case {case_id!r} must be a valid n=2 structure")
    return errors


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
    production = lite_count == LITE_COUNT and isinstance(document, Mapping)
    if isinstance(document, Mapping):
        schema = document.get("schema_version")
        if schema is not None and schema != LITE_SCHEMA_VERSION:
            errors.append(
                f"lite.yaml.schema_version must be {LITE_SCHEMA_VERSION}, got {schema!r}"
            )
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
    if production:
        errors.extend(_lite_group_errors(document, case_ids, case_rows))
        warnings.extend(_lite_coverage_warnings(case_ids, case_rows))
    detail = f"{len(case_ids)} case id(s)"
    return Check(name, tuple(errors), tuple(warnings), detail), case_ids


def _lite_coverage_warnings(
    case_ids: list[str],
    case_rows: Mapping[str, Mapping[str, str]],
) -> list[str]:
    warnings: list[str] = []
    known = [(case_id, case_rows[case_id]) for case_id in case_ids if case_id in case_rows]
    a_suites = {
        row.get("suite", "") for _case_id, row in known if row.get("_matrix") == "a"
    }
    if a_suites and a_suites != B_SUITES:
        warnings.append(f"lite A cases do not cover all four suites: {sorted(a_suites)}")
    b_levels = {
        row.get("level", "").upper() for _case_id, row in known if row.get("_matrix") == "b"
    }
    if b_levels and not {"C0", "L0", "L1", "L2"}.issubset(b_levels):
        warnings.append(f"lite B cases do not cover C0/L0/L1/L2: {sorted(b_levels)}")
    b_suites = {
        row.get("suite", "") for _case_id, row in known if row.get("_matrix") == "b"
    }
    if b_suites and not B_SUITES.issubset(b_suites):
        warnings.append(f"lite B cases do not cover every suite: {sorted(b_suites)}")
    c_windows = {
        row.get("window", "") for _case_id, row in known if row.get("_matrix") == "c"
    }
    if c_windows and not C_WINDOWS.issubset(c_windows):
        warnings.append(f"lite C cases do not cover early/mid/later: {sorted(c_windows)}")
    d_windows = {
        row.get("window", "")
        for _case_id, row in known
        if row.get("_matrix") == "d_rollback"
    }
    if d_windows and not D_WINDOWS.issubset(d_windows):
        warnings.append(f"lite D-rollback cases do not cover early/mid/later: {sorted(d_windows)}")
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

    The defaults enforce the schema-v3 canonical counts (40 A / 442 B / 180 C /
    176 D-intact / 528 D-rollback) and the 30-case lite split (10 A / 10 B / 5 C
    / 2 D-intact / 3 D-rollback).  The keyword overrides exist for unit tests
    with tiny fixtures; production callers should not pass them.
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
