#!/usr/bin/env python3
"""Build D-intact and D-rollback from the imported n=2 compose metadata.

The definition file is a frozen, valid-only subset of the LIBERO-Compose
``libero-goal-compose`` (76 ordered valid) and ``libero-object-compose``
(100 ordered valid) suites.  Only 2-atom tasks are used; conflict pairs are
excluded.  BDDL/init assets stay external (``LIBERO_COMPOSE_HOME``); this
script builds the case matrices, not the simulator assets.

Outputs:

* ``dataset/matrices/libero-compose/intact.csv``   (176 rows)
* ``dataset/matrices/libero-compose/rollback.csv`` (176 x 3 = 528 rows)
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SUITE = REPO_ROOT / "dataset" / "matrices" / "libero-compose"
DEFINITIONS = SUITE / "definitions" / "metadata.jsonl"
INTACT = SUITE / "intact.csv"
ROLLBACK = SUITE / "rollback.csv"

INTACT_COLUMNS = (
    "case_id",
    "test_suite",
    "dimension",
    "arm",
    "sub",
    "suite",
    "struct_id",
    "source_suite",
    "order",
    "task_id",
    "instruction",
    "goal_atoms",
    "n_atoms",
    "family",
    "level",
    "param",
    "semantics",
    "max_steps",
    "repair_window",
    "expected_relation_after",
    "bddl_name",
    "init_source",
    "bddl_sha256",
    "pruned_init_sha256",
    "valid",
    "class",
)
ROLLBACK_COLUMNS = (
    "case_id",
    "test_suite",
    "dimension",
    "arm",
    "sub",
    "suite",
    "struct_id",
    "source_suite",
    "order",
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
    "bddl_sha256",
    "pruned_init_sha256",
    "valid",
    "class",
)

TRIGGER = {
    "early": "s1 first true",
    "mid": "s2 displacement > 5 cm",
    "later": "distance to s2 goal < 8 cm",
}
JOINT_PREDICATES = {"open", "close", "turnon"}


def read_metadata() -> list[dict]:
    if not DEFINITIONS.is_file():
        raise SystemExit(f"missing compose metadata: {DEFINITIONS}")
    rows = []
    for line in DEFINITIONS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        atoms = row.get("goal_atoms") or []
        if len(atoms) != 2:
            raise SystemExit(f"{row.get('task_id')}: expected 2 goal atoms, got {len(atoms)}")
        rows.append(row)
    rows.sort(key=lambda row: (row.get("source_suite", ""), row.get("task_id", "")))
    return rows


def predicate_tokens(predicate: str) -> tuple[str, ...]:
    text = predicate.strip()
    if not (text.startswith("(") and text.endswith(")")):
        raise SystemExit(f"bad predicate: {predicate!r}")
    return tuple(token for token in text[1:-1].split() if token)


def family(predicate: str) -> str:
    name = predicate_tokens(predicate)[0].lower()
    return "joint" if name in JOINT_PREDICATES else "pose"


def actor_object(predicate: str) -> str:
    """Best-effort actor body for the first subgoal atom.

    For ``In``/``On`` the first argument is the manipulated object.  For
    ``Open``/``Close`` the argument is a *region* body, so strip the known
    region suffixes to get the articulated body (e.g.
    ``wooden_cabinet_1_middle_region`` -> ``wooden_cabinet_1``).
    ``Turnon`` takes the fixture body directly.
    """

    tokens = predicate_tokens(predicate)
    name = tokens[1] if len(tokens) > 1 else ""
    apply = tokens[0].lower()
    if apply in {"open", "close"}:
        for suffix in (
            "_middle_region",
            "_bottom_region",
            "_top_region",
            "_bottom_level",
            "_top_side",
            "_contain_region",
            "_cook_region",
            "_heating_region",
        ):
            if name.endswith(suffix):
                return name[: -len(suffix)]
    return name


def intact_rows(rows: list[dict]) -> list[dict[str, str]]:
    out = []
    for row in rows:
        task_id = row["task_id"]
        out.append(
            {
                "case_id": f"compose-intact-{task_id}",
                "test_suite": "compose",
                "dimension": "intact",
                "arm": "intact",
                "sub": "compose",
                "suite": "compose",
                "struct_id": task_id,
                "source_suite": row["source_suite"],
                "order": row["order"],
                "task_id": task_id,
                "instruction": row["instruction"],
                "goal_atoms": "|".join(row["goal_atoms"]),
                "n_atoms": str(len(row["goal_atoms"])),
                "family": family(row["goal_atoms"][0]),
                "level": "INTACT",
                "param": "",
                "semantics": "relation_holds_intact",
                "max_steps": "600",
                "repair_window": "0",
                "expected_relation_after": "true",
                "bddl_name": task_id,
                "init_source": f"bddl/{task_id}.pruned_init",
                "bddl_sha256": row["bddl_sha256"],
                "pruned_init_sha256": row["pruned_init_sha256"],
                "valid": "true",
                "class": row["class"],
            }
        )
    return out


def rollback_rows(rows: list[dict]) -> list[dict[str, str]]:
    out = []
    for row in rows:
        task_id = row["task_id"]
        s1 = row["goal_atoms"][0]
        actor = actor_object(s1)
        for window in ("early", "mid", "later"):
            out.append(
                {
                    "case_id": f"compose-rollback-{task_id}-{window}-l0",
                    "test_suite": "compose",
                    "dimension": "in-execution",
                    "arm": "rollback",
                    "sub": "compose",
                    "suite": "compose",
                    "struct_id": task_id,
                    "source_suite": row["source_suite"],
                    "order": row["order"],
                    "task_id": task_id,
                    "instruction": row["instruction"],
                    "window": window,
                    "trigger_criterion": TRIGGER[window],
                    "target": "s1",
                    "revoked_predicate": s1,
                    "revoked_object": actor,
                    "family": family(s1),
                    "level": "L0",
                    "param": "",
                    "semantics": "relation_then_resume",
                    "max_steps": "600",
                    "repair_window": "600",
                    "expected_relation_after": "false",
                    "s2_must_stay_true": "true",
                    "bddl_name": task_id,
                    "init_source": f"bddl/{task_id}.pruned_init",
                    "bddl_sha256": row["bddl_sha256"],
                    "pruned_init_sha256": row["pruned_init_sha256"],
                    "valid": "true",
                    "class": row["class"],
                }
            )
    return out


def render(columns: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare, do not write")
    args = parser.parse_args()

    rows = read_metadata()
    outputs = (
        (INTACT, INTACT_COLUMNS, intact_rows(rows)),
        (ROLLBACK, ROLLBACK_COLUMNS, rollback_rows(rows)),
    )
    for path, columns, payload in outputs:
        text = render(columns, payload)
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                raise SystemExit(f"[build_compose_suite] out of date: {path}")
            print(f"[build_compose_suite] OK {path.relative_to(REPO_ROOT)} ({len(payload)} rows)")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"[build_compose_suite] wrote {path.relative_to(REPO_ROOT)} ({len(payload)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
