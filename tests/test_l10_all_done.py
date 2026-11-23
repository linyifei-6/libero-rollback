"""Static contract tests for the LIBERO-10 slice of the B matrix.

The tests deliberately do not start a simulator: they pin the all_done window
selection, the 10-task l10 inventory and the representative case set that the
simulation smoke run uses.  The actual injection/rollback behaviour is covered
by ``tests/test_runtime_static.py`` (geometry) and by the l10 smoke run.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from libero_rollback.matrices import load_b_matrix
from libero_rollback.runner import RunConfig, build_plan, select_cases

REPO_ROOT = Path(__file__).resolve().parents[1]
MATRIX = REPO_ROOT / "dataset" / "matrices" / "b-matrix.csv"

L10_LEVELS = {"C0": 10, "L0": 28, "L1": 84, "L2": 75}
L10_TARGETS = {"c0": 10, "g": 7, "s1": 60, "s2": 57, "both": 63}
L10_TASKS = {0, 33, 78, 133, 137, 145, 158, 193, 237, 276}

# One representative case for every l10 form that needs a separate injection
# path: C0, dedicated pose/joint targets, mixed both, two-free-object both,
# a 3-atom task (t133) and the single-goal task (t276).
REPRESENTATIVE_CASES = {
    "b-l10-t000-c0",
    "b-l10-t000-s1-l0",       # joint target
    "b-l10-t000-s1-l1-d03",
    "b-l10-t000-s2-l0",       # pose target
    "b-l10-t000-s2-l2-r30",
    "b-l10-t000-both-l0",     # mixed both
    "b-l10-t000-both-l1-d06",
    "b-l10-t033-s2-l1-d03",   # second joint target in a 19-row task
    "b-l10-t133-both-l0",     # 3 native atoms, both revokes only 2
    "b-l10-t133-both-l2-r60",
    "b-l10-t276-g-l0",        # single-goal task, only g
    "b-l10-t276-g-l1-d10",
}


@pytest.fixture(scope="module")
def matrix():
    return load_b_matrix(MATRIX)


@pytest.fixture(scope="module")
def l10(matrix):
    return [case for case in matrix.cases if case.suite == "l10"]


def test_l10_inventory_matches_frozen_matrix(l10):
    assert len(l10) == 197
    assert {case.task_idx for case in l10} == L10_TASKS
    assert Counter(case.level for case in l10) == Counter(L10_LEVELS)
    assert Counter(case.target for case in l10) == Counter(L10_TARGETS)


def test_l10_is_an_all_done_window(l10):
    assert all(case.trigger == "all_done" for case in l10)
    assert all(case.delay_steps == 10 for case in l10)
    assert all(case.repair_window == 300 for case in l10)
    assert all(case.expected_relation_after == (case.level == "C0") for case in l10)


def test_every_l10_task_has_exactly_one_c0(l10):
    by_task: dict[int, list] = {}
    for case in l10:
        by_task.setdefault(case.task_idx, []).append(case)
    for task_idx, cases in by_task.items():
        controls = [case for case in cases if case.level == "C0"]
        assert len(controls) == 1, task_idx
        control = controls[0]
        assert control.target == "c0"
        assert control.revoked_objects == ()
        assert control.revoked_predicates == ()


def test_l10_target_units_and_joint_l2_rule(l10):
    units = {(case.task_idx, case.target) for case in l10 if case.target != "c0"}
    assert len(units) == 28
    joint_units = {
        (case.task_idx, case.target)
        for case in l10
        if case.family == "joint" and case.level == "L0"
    }
    assert joint_units == {(0, "s1"), (33, "s2"), (78, "s2")}
    l2_units = {(case.task_idx, case.target) for case in l10 if case.level == "L2"}
    assert l2_units == units - joint_units
    assert all(
        (case.task_idx, case.target) not in joint_units
        for case in l10
        if case.level == "L2"
    )


def test_t133_both_revokes_only_two_of_three_atoms(l10):
    both = next(
        case
        for case in l10
        if case.task_idx == 133 and case.target == "both" and case.level == "L0"
    )
    assert both.n_targets == 3
    assert len(both.revoked_predicates) == 2
    assert {predicate for predicate in both.revoked_predicates} == {
        "(On moka_pot_1 flat_stove_1_cook_region)",
        "(On moka_pot_2 flat_stove_1_cook_region)",
    }
    assert all("Turnon" not in predicate for predicate in both.revoked_predicates)


def test_t276_is_single_goal_only(l10):
    t276 = [case for case in l10 if case.task_idx == 276]
    assert len(t276) == 8
    assert {case.target for case in t276} == {"c0", "g"}
    assert all(case.family in {"-", "pose"} for case in t276)


def test_l10_has_no_pre_target(l10):
    assert all(case.target != "pre" for case in l10)


def test_l10_selection_and_plan_are_all_done(matrix):
    cases = select_cases(matrix, suites=["l10"])
    assert len(cases) == 197
    assert {case.task_key for case in cases} == {("l10", idx) for idx in L10_TASKS}

    plan = build_plan(matrix=matrix, cases=cases, config=RunConfig(policy="none"))
    assert plan["selected"] == 197
    assert plan["tasks"] == 10
    assert plan["by_suite"] == {"l10": 197}
    assert plan["by_level"] == {"C0": 10, "L0": 28, "L1": 84, "L2": 75}
    assert plan["defaults"]["stop_on_recovery"] is False
    assert all(case["delay_steps"] == 10 for case in plan["cases"])
    assert all(case["repair_window"] == 600 for case in plan["cases"])


def test_representative_cases_resolve(matrix):
    by_id = {case.case_id: case for case in matrix.cases}
    missing = sorted(REPRESENTATIVE_CASES - set(by_id))
    assert not missing
    selected = select_cases(matrix, case_ids=sorted(REPRESENTATIVE_CASES))
    assert {case.case_id for case in selected} == REPRESENTATIVE_CASES
    assert all(case.suite == "l10" for case in selected)
    assert {case.target for case in selected} == {"c0", "g", "s1", "s2", "both"}
    assert {case.level for case in selected} == {"C0", "L0", "L1", "L2"}
