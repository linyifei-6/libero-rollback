"""Static tests for the runtime layer (no sim, no model, no torch).

Covers the parts of the runtime layer that are pure enough to test on a CPU-only
machine:

* matrix planning (selection, limits, sharding) and ``plan.json`` payloads;
* the ``LevelSpec`` geometry contract from ``docs/SPEC.md`` §3.4 / README §3.4;
* the pure quaternion math of ``runtime/perturbation.py`` (numpy only);
* the LIBERO bootstrap helpers in ``runtime/env.py`` that do not import LIBERO.

Real injection / episode execution is exercised only on an evaluation machine
(full run, see README §8.5); this file never fakes a simulation.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

MINI_MATRIX = "\n".join(
    (
        "case_id,suite,task_idx,bddl_name,instruction,target,revoked_objects,"
        "revoked_predicates,family,level,param,semantics,trigger,delay_steps,"
        "repair_window,expected_relation_after,n_targets",
        "b-goal-t000-c0,goal,0,open_the_middle_drawer_of_the_cabinet,"
        "Open the middle layer of the drawer,c0,,,-,C0,,"
        "relation_holds_control,all_done,10,300,true,1",
        "b-goal-t000-g-l0,goal,0,open_the_middle_drawer_of_the_cabinet,"
        "Open the middle layer of the drawer,g,wooden_cabinet_1,"
        "(Open wooden_cabinet_1_middle_region),joint,L0,,"
        "relation_then_resume,all_done,10,300,false,1",
        "b-goal-t132-c0,goal,132,put_the_bowl_on_the_stove,"
        "Put the bowl on the stove,c0,,,-,C0,,"
        "relation_holds_control,all_done,10,300,true,1",
        "b-goal-t132-g-l1-d03,goal,132,put_the_bowl_on_the_stove,"
        "Put the bowl on the stove,g,akita_black_bowl_1,"
        "(On akita_black_bowl_1 flat_stove_1_cook_region),pose,L1,d03,"
        "relation_then_resume,all_done,10,300,false,1",
        "b-spatial-t000-c0,spatial,0,"
        "pick_up_the_black_bowl_between_the_plate_and_the_ramekin_and_place_it_on_the_plate,"
        "Pick the akita black bowl between the plate and the ramekin and place it "
        "on the plate,c0,,,-,C0,,relation_holds_control,all_done,10,300,true,1",
        "b-spatial-t000-g-l2-r30,spatial,0,"
        "pick_up_the_black_bowl_between_the_plate_and_the_ramekin_and_place_it_on_the_plate,"
        "Pick the akita black bowl between the plate and the ramekin and place it "
        "on the plate,g,akita_black_bowl_1,(On akita_black_bowl_1 plate_1),pose,L2,"
        "r30,relation_then_resume,all_done,10,300,false,1",
        "b-l10-t000-c0,l10,0,"
        "KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it,"
        "turn on the stove and put the moka pot on it,c0,,,-,C0,,"
        "relation_holds_control,all_done,10,300,true,3",
        "b-l10-t000-s1-l0,l10,0,"
        "KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it,"
        "turn on the stove and put the moka pot on it,s1,flat_stove_1,"
        "(Turnon flat_stove_1),joint,L0,,relation_then_resume,all_done,10,300,false,3",
    )
) + "\n"


def write_mini_matrix(tmp_path: Path) -> Path:
    """Write a tiny but fully valid B matrix and return its path."""

    path = tmp_path / "b-matrix-mini.csv"
    path.write_text(MINI_MATRIX, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# matrix planning
# ---------------------------------------------------------------------------


def test_select_cases_filters_and_limits(tmp_path: Path) -> None:
    from libero_rollback.matrices import load_b_matrix
    from libero_rollback.runner import select_cases

    matrix = load_b_matrix(write_mini_matrix(tmp_path))

    assert len(select_cases(matrix)) == 8
    assert len(select_cases(matrix, suites=["goal"])) == 4
    assert len(select_cases(matrix, suites=["goal", "l10"])) == 6
    assert len(select_cases(matrix, suites=["object"])) == 0
    assert [case.case_id for case in select_cases(matrix, max_cases=3)] == [
        "b-goal-t000-c0",
        "b-goal-t000-g-l0",
        "b-goal-t132-c0",
    ]
    selected_tasks = {case.task_key for case in select_cases(matrix, max_tasks=2)}
    assert selected_tasks == {("goal", 0), ("goal", 132)}
    wanted = ["b-l10-t000-c0", "b-goal-t132-c0"]
    assert [case.case_id for case in select_cases(matrix, case_ids=wanted)] == [
        "b-goal-t132-c0",
        "b-l10-t000-c0",
    ]


def test_shard_partition_is_exhaustive_and_disjoint(tmp_path: Path) -> None:
    from libero_rollback.matrices import load_b_matrix
    from libero_rollback.runner import select_cases

    matrix = load_b_matrix(write_mini_matrix(tmp_path))
    shards = [
        select_cases(matrix, shard_index=index, shard_count=3) for index in range(3)
    ]
    flat = [case.case_id for shard in shards for case in shard]
    assert len(flat) == len(set(flat)) == len(matrix.cases)
    assert set(flat) == {case.case_id for case in matrix.cases}


def test_invalid_shard_arguments_raise(tmp_path: Path) -> None:
    from libero_rollback.matrices import load_b_matrix
    from libero_rollback.runner import select_cases

    matrix = load_b_matrix(write_mini_matrix(tmp_path))
    with pytest.raises(ValueError):
        select_cases(matrix, shard_index=0, shard_count=0)
    with pytest.raises(ValueError):
        select_cases(matrix, shard_index=2, shard_count=2)


def test_build_plan_payload(tmp_path: Path) -> None:
    from libero_rollback.matrices import load_b_matrix
    from libero_rollback.runner import RunConfig, build_plan, select_cases, write_plan

    matrix = load_b_matrix(write_mini_matrix(tmp_path))
    cases = select_cases(matrix, max_cases=4)
    plan = build_plan(
        matrix=matrix,
        cases=cases,
        config=RunConfig(seed=3, policy="none"),
        config_name="pi05_libero",
    )

    assert plan["dry_run"] is True
    assert plan["selected"] == 4
    assert plan["tasks"] == 2
    assert plan["by_suite"] == {"goal": 4}
    assert plan["by_level"] == {"C0": 2, "L0": 1, "L1": 1}
    assert plan["case_ids"][0] == "b-goal-t000-c0"
    assert plan["shard"] == {"index": 0, "count": 1}
    assert plan["defaults"]["seed"] == 3
    assert plan["defaults"]["policy"] == "none"

    output = tmp_path / "run"
    plan_path = write_plan(output, plan)
    assert plan_path == output / "plan.json"
    assert plan_path.is_file()
    assert sorted(path.name for path in output.iterdir()) == ["plan.json"]


# ---------------------------------------------------------------------------
# LevelSpec geometry (SPEC §5 / README §3.4)
# ---------------------------------------------------------------------------


def test_level_spec_geometry_contract() -> None:
    import math

    from libero_rollback.matrices import LEVEL_SPECS

    assert LEVEL_SPECS[("C0", None)].kind == "c0"
    assert LEVEL_SPECS[("L0", None)].kind == "init"

    expected_translation = {"d03": 0.03, "d06": 0.06, "d10": 0.10}
    expected_joint_ratio = {"d03": 0.10, "d06": 0.25, "d10": 0.40}
    for param, distance in expected_translation.items():
        spec = LEVEL_SPECS[("L1", param)]
        assert spec.kind == "translation"
        assert spec.translation_m == pytest.approx(distance)
        assert spec.joint_ratio == pytest.approx(expected_joint_ratio[param])

    for param, degrees in {"r30": 30.0, "r60": 60.0, "r90": 90.0}.items():
        spec = LEVEL_SPECS[("L2", param)]
        assert spec.kind == "yaw"
        assert spec.yaw_rad == pytest.approx(math.radians(degrees))

    assert LEVEL_SPECS[("L1", "d03")].label == "L1-d03"
    assert LEVEL_SPECS[("L0", None)].label == "L0"


# ---------------------------------------------------------------------------
# perturbation: pure math only (numpy), no MuJoCo
# ---------------------------------------------------------------------------


def test_perturbation_math() -> None:
    np = pytest.importorskip("numpy")
    from libero_rollback.runtime import perturbation

    identity = np.zeros(4)
    identity[0] = 1.0
    yaw90 = perturbation.quat_yaw(np.pi / 2.0)
    composed = perturbation.quat_mul(yaw90, identity)
    assert np.allclose(perturbation.quat_normalize(composed), composed)
    assert perturbation.quat_angle(identity, yaw90) == pytest.approx(np.pi / 2.0)

    axis, angle = perturbation.quat_to_axis_angle(yaw90)
    assert angle == pytest.approx(np.pi / 2.0)
    assert np.allclose(axis, np.asarray([0.0, 0.0, 1.0]))

    # Round trip: q * q^{-1} = identity.
    inverse = np.asarray([yaw90[0], -yaw90[1], -yaw90[2], -yaw90[3]])
    assert np.allclose(
        perturbation.quat_normalize(perturbation.quat_mul(yaw90, inverse)), identity
    )
    assert np.allclose(perturbation.quat_normalize([0.0, 0.0, 0.0, 0.0]), identity)


def test_perturbation_reuses_matrix_types() -> None:
    pytest.importorskip("numpy")
    from libero_rollback import matrices
    from libero_rollback.runtime import perturbation

    # The runtime layer must reuse the static matrix contract, not redefine it.
    assert perturbation.BCase is matrices.BCase
    assert perturbation.LevelSpec is matrices.LevelSpec
    assert perturbation.parse_predicate is matrices.parse_predicate
    assert callable(perturbation.make_injector)


# ---------------------------------------------------------------------------
# runtime/env: LIBERO bootstrap helpers (no LIBERO import)
# ---------------------------------------------------------------------------


def _fake_libero_tree(root: Path) -> Path:
    package = root / "libero" / "libero"
    for directory in ("bddl_files", "init_files", "assets"):
        (package / directory).mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    return root


def test_resolve_libero_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libero_rollback.runtime.env import resolve_libero_home

    monkeypatch.delenv("LIBERO_HOME", raising=False)
    with pytest.raises(RuntimeError, match="LIBERO_HOME"):
        resolve_libero_home()

    monkeypatch.setenv("LIBERO_HOME", str(tmp_path))
    assert resolve_libero_home() == tmp_path
    assert resolve_libero_home(str(tmp_path / "cli")) == tmp_path / "cli"


def test_write_libero_config_roundtrip(
    tmp_path: Path,
) -> None:
    import yaml

    from libero_rollback.runtime.env import write_libero_config

    root = _fake_libero_tree(tmp_path / "LIBERO")
    config_path = write_libero_config(tmp_path / "cache" / "libero", root)
    assert config_path.is_file()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert set(config) == {
        "benchmark_root",
        "bddl_files",
        "init_states",
        "datasets",
        "assets",
    }
    assert config["bddl_files"] == str(root / "libero" / "libero" / "bddl_files")

    with pytest.raises(FileNotFoundError):
        write_libero_config(tmp_path / "cache2", tmp_path / "missing")


def test_bootstrap_environment_sets_local_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from libero_rollback.runtime.env import bootstrap_environment

    root = _fake_libero_tree(tmp_path / "LIBERO")
    for name, value in (
        ("MUJOCO_GL", "osmesa"),
        ("PYTHONPATH", ""),
        ("LIBERO_CONFIG_PATH", ""),
    ):
        monkeypatch.setenv(name, value)
    runtime = bootstrap_environment(root, tmp_path / "run" / "libero_config")
    assert runtime["libero_root"] == str(root)
    assert Path(runtime["libero_config_path"]).is_file()
    assert os.environ["LIBERO_CONFIG_PATH"] == str(tmp_path / "run" / "libero_config")
    assert str(root) in os.environ["PYTHONPATH"]


def test_load_init_row_reports_missing_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from libero_rollback.runtime.env import load_init_row

    monkeypatch.delenv("LIBERO_INIT_PYTHON", raising=False)
    missing = tmp_path / "does-not-exist.pruned_init"
    with pytest.raises(FileNotFoundError):
        load_init_row(missing, 0)

    # The file exists but this env cannot read it (no torch) and no fallback
    # interpreter is configured: the helper must fail loudly, never fabricate a
    # state.
    init_file = tmp_path / "task.pruned_init"
    init_file.write_bytes(b"not-a-real-checkpoint")
    with pytest.raises(RuntimeError, match="fallback interpreter"):
        load_init_row(init_file, 0)
