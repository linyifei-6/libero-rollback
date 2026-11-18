"""Load and validate the B case matrix (``dataset/matrices/b-matrix.csv``).

The B matrix is the completion-boundary rollback test set:

* one row per case, 442 rows in total (Goal 85 / Object 80 / Spatial 80 / L10 197);
* every task owns exactly one ``C0`` no-op control;
* ``L0`` restores the revoked relation to the episode-initial pose/joint;
* ``L1`` extrapolates 3/6/10 cm away from the target region (joint tasks use the
  documented 10/25/40 % opening fractions, see ``docs/SPEC.md`` §3.3);
* ``L2`` keeps the initial position and yaws the object by 30/60/90 degrees;
* ``target`` selects which already-true relation is revoked (``g`` / ``s1`` /
  ``s2`` / ``both`` / ``pre``).

The module is intentionally free of MuJoCo / torch imports so it can be unit
tested on any machine.
"""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

SUITE_DIRS: Mapping[str, str] = {
    "goal": "libero_goal",
    "object": "libero_object",
    "spatial": "libero_spatial",
    "l10": "libero_10",
}

SUITE_COUNTS: Mapping[str, int] = {
    "goal": 85,
    "object": 80,
    "spatial": 80,
    "l10": 197,
}

TARGETS = frozenset({"c0", "g", "s1", "s2", "both", "pre"})
# ``mixed`` marks a ``both`` case whose two revoked relations have different
# state kinds (e.g. goal-t030: bowl placement + drawer articulation).
FAMILIES = frozenset({"pose", "joint", "mixed", "-"})

_PARAM_RE = re.compile(r"^\((.*)\)$")


@dataclass(frozen=True)
class LevelSpec:
    """Geometry semantics of one matrix level."""

    level: str
    param: str | None
    kind: str  # c0 | init | translation | yaw
    translation_m: float | None = None
    yaw_rad: float | None = None
    joint_ratio: float | None = None

    @property
    def label(self) -> str:
        return self.level if not self.param else f"{self.level}-{self.param}"


LEVEL_SPECS: Mapping[tuple[str, str | None], LevelSpec] = {
    ("C0", None): LevelSpec("C0", None, "c0"),
    ("L0", None): LevelSpec("L0", None, "init"),
    ("L1", "d03"): LevelSpec("L1", "d03", "translation", translation_m=0.03, joint_ratio=0.10),
    ("L1", "d06"): LevelSpec("L1", "d06", "translation", translation_m=0.06, joint_ratio=0.25),
    ("L1", "d10"): LevelSpec("L1", "d10", "translation", translation_m=0.10, joint_ratio=0.40),
    ("L2", "r30"): LevelSpec("L2", "r30", "yaw", yaw_rad=math.radians(30.0)),
    ("L2", "r60"): LevelSpec("L2", "r60", "yaw", yaw_rad=math.radians(60.0)),
    ("L2", "r90"): LevelSpec("L2", "r90", "yaw", yaw_rad=math.radians(90.0)),
}


def parse_predicate(text: str) -> tuple[str, ...]:
    """Parse ``"(In bowl basket_region)"`` into ``("In", "bowl", "basket_region")``."""

    raw = str(text).strip()
    match = _PARAM_RE.match(raw)
    if match is None:
        raise ValueError(f"predicate is not parenthesised: {text!r}")
    inner = match.group(1).strip()
    tokens = tuple(token for token in re.split(r"\s+", inner) if token)
    if len(tokens) < 2:
        raise ValueError(f"predicate needs a name and at least one argument: {text!r}")
    if "(" in inner or ")" in inner:
        raise ValueError(f"nested predicates are not supported: {text!r}")
    return tokens


def _split_objects(value: str) -> tuple[str, ...]:
    # The CSV uses "," for pose-only multi-target rows and "|" for mixed rows.
    return tuple(
        item.strip()
        for item in re.split(r"[,|]", str(value))
        if item.strip()
    )


def _split_predicates(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(value).split("|") if item.strip())


def _as_bool(value: str, *, field_name: str, case_id: str) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"{case_id}: {field_name} must be true/false, got {value!r}")


@dataclass(frozen=True)
class BCase:
    """One row of the B matrix."""

    case_id: str
    suite: str
    task_idx: int
    bddl_name: str
    instruction: str
    target: str
    revoked_objects: tuple[str, ...]
    revoked_predicates: tuple[str, ...]
    family: str
    level: str
    param: str | None
    semantics: str
    trigger: str
    delay_steps: int
    repair_window: int
    expected_relation_after: bool
    n_targets: int

    @property
    def task_key(self) -> tuple[str, int]:
        return (self.suite, self.task_idx)

    @property
    def level_spec(self) -> LevelSpec:
        try:
            return LEVEL_SPECS[(self.level, self.param)]
        except KeyError as error:  # pragma: no cover - validation catches this first
            raise KeyError(f"{self.case_id}: no level spec for {self.level}/{self.param}") from error

    @property
    def parsed_predicates(self) -> tuple[tuple[str, ...], ...]:
        return tuple(parse_predicate(predicate) for predicate in self.revoked_predicates)

    @property
    def is_control(self) -> bool:
        return self.level == "C0"

    def bddl_path(self, libero_root: str | Path) -> Path:
        return _asset_root(libero_root) / "bddl_files" / SUITE_DIRS[self.suite] / f"{self.bddl_name}.bddl"

    def init_path(self, libero_root: str | Path) -> Path:
        return _asset_root(libero_root) / "init_files" / SUITE_DIRS[self.suite] / f"{self.bddl_name}.pruned_init"

    def geometry(self, sim, pred_index: int = 0) -> dict:
        """Resolve the concrete level geometry (kept for report/debug use)."""

        spec = self.level_spec
        return {
            "level": self.level,
            "param": self.param,
            "kind": spec.kind,
            "family": self.family,
            "translation_m": spec.translation_m,
            "joint_ratio": spec.joint_ratio,
            "yaw_deg": None if spec.yaw_rad is None else round(math.degrees(spec.yaw_rad), 3),
            "predicate": self.revoked_predicates[pred_index],
        }


def _asset_root(libero_root: str | Path) -> Path:
    """Resolve ``.../libero`` that directly contains ``bddl_files``/``init_files``."""

    root = Path(libero_root).expanduser()
    candidates = (
        root / "libero" / "libero",
        root,
        root / "libero",
    )
    for candidate in candidates:
        if (candidate / "bddl_files").is_dir() and (candidate / "init_files").is_dir():
            return candidate
    raise FileNotFoundError(
        f"cannot locate LIBERO bddl_files/init_files under {root} "
        f"(tried {[str(c) for c in candidates]})"
    )


@dataclass
class BMatrix:
    cases: list[BCase]
    source: Path
    issues: list[str] = field(default_factory=list)

    def by_task(self) -> dict[tuple[str, int], list[BCase]]:
        grouped: dict[tuple[str, int], list[BCase]] = {}
        for case in self.cases:
            grouped.setdefault(case.task_key, []).append(case)
        return grouped

    def tasks(self) -> list[tuple[str, int]]:
        return list(self.by_task())

    def select(
        self,
        *,
        suites: Sequence[str] | None = None,
        case_ids: Iterable[str] | None = None,
        max_tasks: int = 0,
    ) -> list[BCase]:
        wanted_suites = set(suites or ())
        wanted_ids = set(case_ids or ())
        selected = [
            case
            for case in self.cases
            if (not wanted_suites or case.suite in wanted_suites)
            and (not wanted_ids or case.case_id in wanted_ids)
        ]
        if max_tasks > 0:
            allowed = {task for task in self.tasks()[:max_tasks]}
            selected = [case for case in selected if case.task_key in allowed]
        return selected

    def summary(self) -> dict:
        by_suite: dict[str, int] = {}
        by_level: dict[str, int] = {}
        tasks: set[tuple[str, int]] = set()
        for case in self.cases:
            by_suite[case.suite] = by_suite.get(case.suite, 0) + 1
            by_level[case.level] = by_level.get(case.level, 0) + 1
            tasks.add(case.task_key)
        return {
            "cases": len(self.cases),
            "tasks": len(tasks),
            "by_suite": dict(sorted(by_suite.items())),
            "by_level": dict(sorted(by_level.items())),
            "source": str(self.source),
        }


def _validate(cases: list[BCase], issues: list[str]) -> None:
    seen: set[str] = set()
    for case in cases:
        if case.case_id in seen:
            issues.append(f"duplicate case_id: {case.case_id}")
        seen.add(case.case_id)
        if case.suite not in SUITE_DIRS:
            issues.append(f"{case.case_id}: unknown suite {case.suite!r}")
        if case.target not in TARGETS:
            issues.append(f"{case.case_id}: unknown target {case.target!r}")
        if case.family not in FAMILIES:
            issues.append(f"{case.case_id}: unknown family {case.family!r}")
        if case.trigger != "all_done":
            issues.append(f"{case.case_id}: B requires trigger=all_done, got {case.trigger!r}")
        if case.delay_steps != 10:
            issues.append(f"{case.case_id}: delay_steps must be 10, got {case.delay_steps}")
        # ``n_targets`` counts the task's native goal atoms, not the revoked
        # subset (a ``both`` case may revoke 2 of 3 atoms).
        if case.level == "C0":
            if case.revoked_objects or case.revoked_predicates:
                issues.append(f"{case.case_id}: C0 must not revoke anything")
            if not case.expected_relation_after:
                issues.append(f"{case.case_id}: C0 must expect the relation to stay true")
            if case.target != "c0":
                issues.append(f"{case.case_id}: C0 target must be 'c0', got {case.target!r}")
            continue
        if case.expected_relation_after:
            issues.append(f"{case.case_id}: non-C0 must expect the relation to become false")
        if not case.revoked_objects:
            issues.append(f"{case.case_id}: non-C0 needs at least one revoked object")
        if not case.revoked_predicates:
            issues.append(f"{case.case_id}: non-C0 needs at least one revoked predicate")
        key = (case.level, case.param)
        if key not in LEVEL_SPECS:
            issues.append(f"{case.case_id}: unsupported level/param {case.level}/{case.param}")
        if case.level == "L0" and case.param is not None:
            issues.append(f"{case.case_id}: L0 must not carry a param")
        if case.level == "L1" and case.param not in {"d03", "d06", "d10"}:
            issues.append(f"{case.case_id}: L1 param must be d03/d06/d10, got {case.param!r}")
        if case.level == "L2" and case.param not in {"r30", "r60", "r90"}:
            issues.append(f"{case.case_id}: L2 param must be r30/r60/r90, got {case.param!r}")
        if case.level == "L2" and case.family == "joint":
            issues.append(f"{case.case_id}: joint tasks have no L2 level")
        if case.level == "L0" and case.family == "-":
            issues.append(f"{case.case_id}: L0 needs a pose/joint family")
        if case.target == "pre":
            if not (case.suite == "goal" and case.task_idx == 30):
                issues.append(f"{case.case_id}: target=pre is only defined for goal-t030")
            if case.family != "joint":
                issues.append(f"{case.case_id}: target=pre must revoke a joint precondition")
            if len(case.revoked_predicates) != 1:
                issues.append(f"{case.case_id}: target=pre revokes exactly one predicate")
        if case.target in {"s1", "s2"} and len(case.revoked_predicates) != 1:
            issues.append(f"{case.case_id}: target={case.target} revokes exactly one predicate")
        if case.target == "both" and len(case.revoked_predicates) != 2:
            issues.append(f"{case.case_id}: target=both revokes exactly two predicates")
        if case.target == "g" and len(case.revoked_predicates) != 1:
            issues.append(f"{case.case_id}: target=g revokes exactly one predicate")
        for predicate in case.revoked_predicates:
            try:
                tokens = parse_predicate(predicate)
            except ValueError as error:
                issues.append(f"{case.case_id}: {error}")
                continue
            predicate_objects = {
                token for token in tokens[1:] if any(ch.isalpha() for ch in token)
            }
            matched = {
                obj
                for obj in case.revoked_objects
                for token in predicate_objects
                if token == obj or token.startswith(obj + "_")
            }
            if not matched:
                issues.append(
                    f"{case.case_id}: predicate {predicate!r} mentions no revoked object "
                    f"{case.revoked_objects}"
                )

    # exactly one C0 per task, and every non-C0 case belongs to a task with C0
    grouped = BMatrix(cases, Path("<memory>")).by_task()
    for task_key, task_cases in grouped.items():
        controls = [case for case in task_cases if case.level == "C0"]
        if len(controls) != 1:
            issues.append(f"{task_key}: expected exactly one C0 case, found {len(controls)}")
        if len({case.instruction for case in task_cases}) != 1:
            issues.append(f"{task_key}: instruction differs across cases")
        if len({case.bddl_name for case in task_cases}) != 1:
            issues.append(f"{task_key}: bddl_name differs across cases")


def load_b_matrix(path: str | Path) -> BMatrix:
    """Read, validate and return the B matrix."""

    source = Path(path)
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"empty B matrix: {source}")
    missing = {
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
    } - set(rows[0])
    if missing:
        raise ValueError(f"{source}: missing columns {sorted(missing)}")

    cases: list[BCase] = []
    for row in rows:
        case_id = row["case_id"].strip()
        cases.append(
            BCase(
                case_id=case_id,
                suite=row["suite"].strip(),
                task_idx=int(row["task_idx"]),
                bddl_name=row["bddl_name"].strip(),
                instruction=row["instruction"].strip(),
                target=row["target"].strip().lower(),
                revoked_objects=_split_objects(row["revoked_objects"]),
                revoked_predicates=_split_predicates(row["revoked_predicates"]),
                family=row["family"].strip().lower(),
                level=row["level"].strip().upper(),
                param=(row["param"].strip().lower() or None),
                semantics=row["semantics"].strip(),
                trigger=row["trigger"].strip(),
                delay_steps=int(row["delay_steps"]),
                repair_window=int(row["repair_window"]),
                expected_relation_after=_as_bool(
                    row["expected_relation_after"],
                    field_name="expected_relation_after",
                    case_id=case_id,
                ),
                n_targets=int(row["n_targets"]),
            )
        )

    issues: list[str] = []
    _validate(cases, issues)
    if issues:
        preview = "\n".join(f"  - {issue}" for issue in issues[:30])
        suffix = "" if len(issues) <= 30 else f"\n  ... and {len(issues) - 30} more"
        raise ValueError(f"invalid B matrix ({len(issues)} issues):\n{preview}{suffix}")
    return BMatrix(cases=cases, source=source, issues=issues)
