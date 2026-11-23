"""Load the C (native) and D (composed) in-execution rollback matrices.

The two matrices share one row schema but resolve their assets differently:

``C`` ``dataset/matrices/libero-rollback/in-execution-rollback.csv``
    Native LIBERO-10 tasks.  The CSV carries ``(suite, task_idx)`` but no
    ``bddl_name``, so the BDDL/init names are resolved through ``b-matrix.csv``:
    ``(l10, 0) -> KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it``.
    Assets come from ``LIBERO_HOME`` (``libero/libero/bddl_files/libero_10`` and
    ``libero/libero/init_files/libero_10``).

``D`` ``dataset/matrices/libero-compose/rollback.csv``
    Composed n=2 tasks.  Every row carries ``bddl_name`` and ``init_source``;
    assets are checked into the repo under ``dataset/compose/bddl``.

A :class:`WindowCase` carries the attributes :class:`libero_rollback.runtime.
perturbation.BInjector` reads (``case_id``, ``target``, ``level``, ``param``,
``family``, ``revoked_objects``, ``revoked_predicates``,
``expected_relation_after`` ...), so the C/D runner can reuse the B injector
unchanged.

The module is intentionally free of numpy / MuJoCo / torch imports so it can be
loaded (and its path logic tested) on the CPU-only static environment.
"""

from __future__ import annotations

import csv
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .matrices import LEVEL_SPECS, LevelSpec, _asset_root, parse_predicate

WINDOWS: tuple[str, ...] = ("early", "mid", "later")
MATRIX_KINDS: tuple[str, ...] = ("C", "D")

_REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_C_MATRIX = (
    _REPO_ROOT / "dataset" / "matrices" / "libero-rollback" / "in-execution-rollback.csv"
)
DEFAULT_D_MATRIX = (
    _REPO_ROOT / "dataset" / "matrices" / "libero-compose" / "rollback.csv"
)
#: C rows name their native task by ``(suite, task_idx)``; the BDDL name and the
#: instruction are taken from the frozen B matrix.
DEFAULT_B_MATRIX = _REPO_ROOT / "dataset" / "matrices" / "b-matrix.csv"
DEFAULT_COMPOSE_ROOT = _REPO_ROOT / "dataset" / "compose"

#: C is the LIBERO-10 suite only (nine multi-goal tasks).
C_SUITE = "l10"
C_SUITE_DIR = "libero_10"

_SPLIT_OBJECTS_RE = re.compile(r"[,|]")


# ---------------------------------------------------------------------------
# roots
# ---------------------------------------------------------------------------


def resolve_compose_root(cli_value: str | None = None) -> Path:
    """Resolve the D asset root (``--compose-root`` / ``COMPOSE_ROOT``).

    The default is the repo-local ``dataset/compose`` directory.  The path is
    returned even when it does not exist yet; the runner turns a missing root
    into a hard :class:`FileNotFoundError` with the exact expected location.
    """

    value = cli_value or os.environ.get("COMPOSE_ROOT")
    if value:
        return Path(value).expanduser()
    candidates = (Path.cwd() / "dataset" / "compose", DEFAULT_COMPOSE_ROOT)
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[-1]


# ---------------------------------------------------------------------------
# parsing helpers
# ---------------------------------------------------------------------------


def _as_bool(value: Any, *, field_name: str, case_id: str) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"{case_id}: {field_name} must be true/false, got {value!r}")


def _split_objects(value: Any) -> tuple[str, ...]:
    return tuple(
        item.strip() for item in _SPLIT_OBJECTS_RE.split(str(value)) if item.strip()
    )


def _split_predicates(value: Any) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(value).split("|") if item.strip())


def _first(row: Mapping[str, Any], *names: str) -> str:
    """Return the first present, non-empty column value (singular/plural forms)."""

    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


# ---------------------------------------------------------------------------
# WindowCase
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowCase:
    """One C or D row, BCase-compatible for the B injector.

    ``asset_source`` selects the asset layout:
    ``"native"`` uses ``LIBERO_HOME`` (C), ``"compose"`` uses ``COMPOSE_ROOT``
    (D, default ``dataset/compose``).
    """

    case_id: str
    test_suite: str
    dimension: str
    arm: str
    sub: str
    suite: str
    instruction: str
    window: str
    trigger_criterion: str
    target: str
    revoked_objects: tuple[str, ...]
    revoked_predicates: tuple[str, ...]
    family: str
    level: str
    param: str | None
    semantics: str
    max_steps: int
    repair_window: int
    expected_relation_after: bool
    s2_must_stay_true: bool
    bddl_name: str
    asset_source: str  # "native" (C) | "compose" (D)
    task_idx: int | None = None
    struct_id: str | None = None
    task_id: str | None = None
    source_suite: str | None = None
    order: str | None = None
    init_source: str | None = None
    bddl_sha256: str | None = None
    pruned_init_sha256: str | None = None
    valid: bool = True
    class_name: str | None = None
    n_targets: int = 2

    # -- BCase-compatible interface --------------------------------------

    @property
    def task_key(self) -> tuple[str, Any]:
        if self.asset_source == "compose":
            return (self.suite, self.task_id or self.struct_id or self.bddl_name)
        return (self.suite, self.task_idx)

    @property
    def is_control(self) -> bool:
        return self.level == "C0"

    @property
    def level_spec(self) -> LevelSpec:
        try:
            return LEVEL_SPECS[(self.level, self.param)]
        except KeyError as error:
            raise KeyError(
                f"{self.case_id}: no level spec for {self.level}/{self.param}"
            ) from error

    @property
    def parsed_predicates(self) -> tuple[tuple[str, ...], ...]:
        return tuple(parse_predicate(predicate) for predicate in self.revoked_predicates)

    @property
    def trigger_event(self) -> str:
        return WINDOW_EVENTS[self.window]

    # -- assets -----------------------------------------------------------

    @property
    def asset_root_name(self) -> str:
        return "LIBERO_HOME" if self.asset_source == "native" else "COMPOSE_ROOT"

    def bddl_relative(self) -> str:
        if self.asset_source == "compose":
            return f"bddl/{self.bddl_name}.bddl"
        return f"bddl_files/{C_SUITE_DIR}/{self.bddl_name}.bddl"

    def init_relative(self) -> str:
        if self.asset_source == "compose":
            source = (self.init_source or "").strip()
            return source or f"bddl/{self.bddl_name}.pruned_init"
        return f"init_files/{C_SUITE_DIR}/{self.bddl_name}.pruned_init"

    def bddl_path(self, root: str | Path) -> Path:
        if self.asset_source == "compose":
            return Path(root).expanduser() / "bddl" / f"{self.bddl_name}.bddl"
        return (
            _asset_root(root)
            / "bddl_files"
            / C_SUITE_DIR
            / f"{self.bddl_name}.bddl"
        )

    def init_path(self, root: str | Path) -> Path:
        if self.asset_source == "compose":
            return Path(root).expanduser() / self.init_relative()
        return (
            _asset_root(root)
            / "init_files"
            / C_SUITE_DIR
            / f"{self.bddl_name}.pruned_init"
        )

    def as_plan_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "test_suite": self.test_suite,
            "dimension": self.dimension,
            "arm": self.arm,
            "sub": self.sub,
            "suite": self.suite,
            "task_idx": self.task_idx,
            "struct_id": self.struct_id,
            "task_id": self.task_id,
            "window": self.window,
            "trigger_criterion": self.trigger_criterion,
            "trigger_event": self.trigger_event,
            "target": self.target,
            "level": self.level,
            "param": self.param,
            "family": self.family,
            "bddl_name": self.bddl_name,
            "asset_root": self.asset_root_name,
            "bddl": self.bddl_relative(),
            "init": self.init_relative(),
            "max_steps": self.max_steps,
            "repair_window": self.repair_window,
            "expected_relation_after": self.expected_relation_after,
            "s2_must_stay_true": self.s2_must_stay_true,
        }


WINDOW_EVENTS: Mapping[str, str] = {
    "early": "enter_first_subgoal_completed",
    "mid": "enter_next_subgoal_lift",
    "later": "enter_next_subgoal_preplacement",
}


# ---------------------------------------------------------------------------
# matrix
# ---------------------------------------------------------------------------


@dataclass
class WindowMatrix:
    cases: list[WindowCase]
    source: Path
    kind: str  # "C" | "D"
    issues: list[str] = field(default_factory=list)

    def by_task(self) -> dict[tuple[str, Any], list[WindowCase]]:
        grouped: dict[tuple[str, Any], list[WindowCase]] = {}
        for case in self.cases:
            grouped.setdefault(case.task_key, []).append(case)
        return grouped

    def tasks(self) -> list[tuple[str, Any]]:
        return list(self.by_task())

    def select(
        self,
        *,
        suites: Sequence[str] | None = None,
        windows: Sequence[str] | None = None,
        levels: Sequence[str] | None = None,
        case_ids: Iterable[str] | None = None,
    ) -> list[WindowCase]:
        wanted_suites = set(suites or ())
        wanted_windows = {str(window).lower() for window in (windows or ())}
        wanted_levels = {str(level).upper() for level in (levels or ())}
        wanted_ids = set(case_ids or ())
        return [
            case
            for case in self.cases
            if (not wanted_suites or case.suite in wanted_suites)
            and (not wanted_windows or case.window in wanted_windows)
            and (not wanted_levels or case.level in wanted_levels)
            and (not wanted_ids or case.case_id in wanted_ids)
        ]

    def summary(self) -> dict[str, Any]:
        by_suite: dict[str, int] = {}
        by_window: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_family: dict[str, int] = {}
        tasks: set[tuple[str, Any]] = set()
        for case in self.cases:
            by_suite[case.suite] = by_suite.get(case.suite, 0) + 1
            by_window[case.window] = by_window.get(case.window, 0) + 1
            by_level[case.level] = by_level.get(case.level, 0) + 1
            by_family[case.family] = by_family.get(case.family, 0) + 1
            tasks.add(case.task_key)
        return {
            "kind": self.kind,
            "cases": len(self.cases),
            "tasks": len(tasks),
            "by_suite": dict(sorted(by_suite.items())),
            "by_window": {window: by_window.get(window, 0) for window in WINDOWS},
            "by_level": dict(sorted(by_level.items())),
            "by_family": dict(sorted(by_family.items())),
            "source": str(self.source),
        }


# ---------------------------------------------------------------------------
# loaders
# ---------------------------------------------------------------------------


def _read_rows(path: str | Path) -> tuple[Path, list[str], list[dict[str, str]]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"window matrix not found: {source}")
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fieldnames = [str(name) for name in (reader.fieldnames or [])]
    if not rows:
        raise ValueError(f"empty window matrix: {source}")
    return source, fieldnames, rows


def _require_columns(source: Path, columns: Sequence[str], required: Iterable[str]) -> None:
    missing = sorted(set(required) - set(columns))
    if missing:
        raise ValueError(f"{source}: missing columns {missing}")


def detect_matrix_kind(columns: Sequence[str]) -> str:
    """Return ``"D"`` when the header carries compose columns, else ``"C"``."""

    lowered = {str(name).strip().lower() for name in columns}
    if {"struct_id", "bddl_name"} <= lowered:
        return "D"
    return "C"


def load_b_bddl_map(path: str | Path = DEFAULT_B_MATRIX) -> dict[tuple[str, int], str]:
    """Read ``(suite, task_idx) -> bddl_name`` from the frozen B matrix."""

    source, columns, rows = _read_rows(path)
    _require_columns(source, columns, ("suite", "task_idx", "bddl_name"))
    mapping: dict[tuple[str, int], str] = {}
    for row in rows:
        suite = str(row.get("suite", "")).strip()
        name = str(row.get("bddl_name", "")).strip()
        if not suite or not name:
            continue
        mapping.setdefault((suite, int(row["task_idx"])), name)
    if not mapping:
        raise ValueError(f"{source}: no (suite, task_idx, bddl_name) rows")
    return mapping


def _base_fields(
    row: Mapping[str, Any],
    *,
    case_id: str,
    asset_source: str,
    bddl_name: str,
    source: Path,
) -> dict[str, Any]:
    window = str(row.get("window", "")).strip().lower()
    if window not in WINDOWS:
        raise ValueError(f"{case_id}: unknown window {window!r}; expected {WINDOWS}")
    target = str(row.get("target", "")).strip().lower()
    if target != "s1":
        raise ValueError(
            f"{case_id}: in-execution rollback revokes s1, got target={target!r}"
        )
    predicates = _split_predicates(
        _first(row, "revoked_predicate", "revoked_predicates")
    )
    objects = _split_objects(_first(row, "revoked_object", "revoked_objects"))
    if not predicates or not objects:
        raise ValueError(f"{case_id}: missing revoked predicate/object")
    target_suite = str(row.get("suite", "")).strip()
    if asset_source == "native" and target_suite != C_SUITE:
        raise ValueError(
            f"{case_id}: C matrix supports suite={C_SUITE!r} only, "
            f"got {target_suite!r} (source {source})"
        )
    return {
        "case_id": case_id,
        "test_suite": str(row.get("test_suite", "")).strip(),
        "dimension": str(row.get("dimension", "")).strip(),
        "arm": str(row.get("arm", "")).strip(),
        "sub": str(row.get("sub", "")).strip(),
        "suite": target_suite,
        "instruction": str(row.get("instruction", "")).strip(),
        "window": window,
        "trigger_criterion": str(row.get("trigger_criterion", "")).strip(),
        "target": target,
        "revoked_objects": objects,
        "revoked_predicates": predicates,
        "family": str(row.get("family", "")).strip().lower(),
        "level": str(row.get("level", "")).strip().upper(),
        "param": (str(row.get("param", "")).strip().lower() or None),
        "semantics": str(row.get("semantics", "")).strip(),
        "max_steps": int(row.get("max_steps") or 0),
        "repair_window": int(row.get("repair_window") or 0),
        "expected_relation_after": _as_bool(
            row.get("expected_relation_after"),
            field_name="expected_relation_after",
            case_id=case_id,
        ),
        "s2_must_stay_true": _as_bool(
            row.get("s2_must_stay_true"),
            field_name="s2_must_stay_true",
            case_id=case_id,
        ),
        "bddl_name": bddl_name,
        "asset_source": asset_source,
    }


def load_c_matrix(
    path: str | Path = DEFAULT_C_MATRIX,
    *,
    b_matrix: str | Path = DEFAULT_B_MATRIX,
) -> WindowMatrix:
    """Load the C (native LIBERO-10 in-execution) matrix."""

    source, columns, rows = _read_rows(path)
    _require_columns(
        source,
        columns,
        (
            "case_id",
            "suite",
            "task_idx",
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
        ),
    )
    bddl_map = load_b_bddl_map(b_matrix)
    cases: list[WindowCase] = []
    for row in rows:
        case_id = str(row["case_id"]).strip()
        suite = str(row["suite"]).strip()
        task_idx = int(row["task_idx"])
        bddl_name = bddl_map.get((suite, task_idx))
        if not bddl_name:
            raise ValueError(
                f"{source}: {case_id}: no bddl_name for (suite={suite!r}, "
                f"task_idx={task_idx}) in {Path(b_matrix)}; pass --b-matrix"
            )
        fields = _base_fields(
            row,
            case_id=case_id,
            asset_source="native",
            bddl_name=bddl_name,
            source=source,
        )
        fields["task_idx"] = task_idx
        fields["struct_id"] = str(row.get("struct_id", "")).strip() or None
        cases.append(WindowCase(**fields))
    return _finish(cases, source, "C")


def load_d_matrix(path: str | Path = DEFAULT_D_MATRIX) -> WindowMatrix:
    """Load the D (composed in-execution) matrix."""

    source, columns, rows = _read_rows(path)
    _require_columns(
        source,
        columns,
        (
            "case_id",
            "struct_id",
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
        ),
    )
    cases: list[WindowCase] = []
    for row in rows:
        case_id = str(row["case_id"]).strip()
        bddl_name = str(row.get("bddl_name", "")).strip() or str(
            row.get("task_id", "")
        ).strip()
        if not bddl_name:
            raise ValueError(f"{source}: {case_id}: missing bddl_name/task_id")
        fields = _base_fields(
            row,
            case_id=case_id,
            asset_source="compose",
            bddl_name=bddl_name,
            source=source,
        )
        fields.update(
            {
                "struct_id": str(row.get("struct_id", "")).strip() or None,
                "task_id": str(row.get("task_id", "")).strip() or None,
                "source_suite": str(row.get("source_suite", "")).strip() or None,
                "order": str(row.get("order", "")).strip() or None,
                "init_source": str(row.get("init_source", "")).strip() or None,
                "bddl_sha256": str(row.get("bddl_sha256", "")).strip() or None,
                "pruned_init_sha256": (
                    str(row.get("pruned_init_sha256", "")).strip() or None
                ),
                "valid": _as_bool(
                    row.get("valid", "true"),
                    field_name="valid",
                    case_id=case_id,
                ),
                "class_name": str(row.get("class", "")).strip() or None,
            }
        )
        cases.append(WindowCase(**fields))
    return _finish(cases, source, "D")


def load_window_matrix(
    path: str | Path,
    *,
    kind: str = "auto",
    b_matrix: str | Path = DEFAULT_B_MATRIX,
) -> WindowMatrix:
    """Load a C or D matrix, detecting the kind from the header by default."""

    value = str(kind or "auto").strip().upper()
    if value == "AUTO":
        _, columns, _ = _read_rows(path)
        value = detect_matrix_kind(columns)
    if value == "C":
        return load_c_matrix(path, b_matrix=b_matrix)
    if value == "D":
        return load_d_matrix(path)
    raise ValueError(f"unknown matrix kind {kind!r}; expected auto/C/D")


def _finish(cases: list[WindowCase], source: Path, kind: str) -> WindowMatrix:
    issues: list[str] = []
    seen: set[str] = set()
    for case in cases:
        if case.case_id in seen:
            issues.append(f"duplicate case_id: {case.case_id}")
        seen.add(case.case_id)
        if case.level == "C0":
            # C is treatment-only and D has no matrix control (docs/c-matrix.md
            # §5, docs/d-matrix.md §5); a C0 row would need window-control
            # semantics that this runner does not implement.
            issues.append(
                f'{case.case_id}: C/D in-execution matrices have no C0 control'
            )
            continue
        if case.expected_relation_after:
            issues.append(
                f"{case.case_id}: non-C0 in-execution case must expect relation=false"
            )
        try:
            case.level_spec
        except KeyError as error:
            issues.append(str(error))
        try:
            case.parsed_predicates
        except ValueError as error:
            issues.append(f"{case.case_id}: {error}")
    if issues:
        preview = "\n".join(f"  - {issue}" for issue in issues[:30])
        suffix = "" if len(issues) <= 30 else f"\n  ... and {len(issues) - 30} more"
        raise ValueError(
            f"invalid {kind} window matrix ({len(issues)} issues):\n{preview}{suffix}"
        )
    return WindowMatrix(cases=cases, source=source, kind=kind, issues=issues)


def select_window_cases(
    matrix: WindowMatrix,
    *,
    suites: Sequence[str] | None = None,
    windows: Sequence[str] | None = None,
    levels: Sequence[str] | None = None,
    case_ids: Sequence[str] | None = None,
    max_cases: int = 0,
    shard_index: int = 0,
    shard_count: int = 1,
) -> list[WindowCase]:
    """Filter, limit and shard a C/D matrix (deterministic ``i % n`` shards)."""

    if shard_count < 1:
        raise ValueError(f"shard_count must be >= 1, got {shard_count}")
    if not 0 <= shard_index < shard_count:
        raise ValueError(f"shard_index must be in [0, {shard_count}), got {shard_index}")
    if max_cases < 0:
        raise ValueError("max_cases must be >= 0")
    cases = matrix.select(
        suites=suites, windows=windows, levels=levels, case_ids=case_ids
    )
    if max_cases:
        cases = cases[: int(max_cases)]
    if shard_count > 1:
        cases = [
            case
            for index, case in enumerate(cases)
            if index % shard_count == shard_index
        ]
    return cases


__all__ = [
    "C_SUITE",
    "DEFAULT_B_MATRIX",
    "DEFAULT_COMPOSE_ROOT",
    "DEFAULT_C_MATRIX",
    "DEFAULT_D_MATRIX",
    "MATRIX_KINDS",
    "WINDOW_EVENTS",
    "WINDOWS",
    "WindowCase",
    "WindowMatrix",
    "detect_matrix_kind",
    "load_b_bddl_map",
    "load_c_matrix",
    "load_d_matrix",
    "load_window_matrix",
    "resolve_compose_root",
    "select_window_cases",
]
