"""Static and fake-environment tests for the C/D in-execution runner.

No simulator is started and no model is loaded:

* loaders / asset paths for C (LIBERO_HOME) and D (COMPOSE_ROOT);
* ``WindowTrigger`` / ``JointProgressTrigger`` integration and the documented
  joint-``s2`` progress path;
* the CLI dry run (``plan.json`` only);
* a fake-environment smoke run of :func:`run_window_case` that exercises the
  trigger -> ``BInjector.inject`` -> repair-window bookkeeping.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from libero_rollback import window_runner
from libero_rollback.runtime.triggers import WindowObservation, WindowTrigger
from libero_rollback.window_matrix import (
    DEFAULT_COMPOSE_ROOT,
    WindowCase,
    load_c_matrix,
    load_d_matrix,
    load_window_matrix,
    resolve_compose_root,
    select_window_cases,
)
from libero_rollback.window_runner import (
    JointProgressObservation,
    JointProgressTrigger,
    JointTriggerConfig,
    S2Target,
    UnsupportedWindowError,
    WindowRunConfig,
    _make_trigger,
    joint_progress,
    lift_from_initial,
    resolve_s2,
    run_window_case,
    s2_undisturbed,
    xy_distance,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "run_window_matrix.py"

MINI_B_MATRIX = "\n".join(
    (
        "suite,task_idx,bddl_name",
        "l10,0,KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it",
        "l10,33,KITCHEN_SCENE4_put_the_black_bowl_in_the_bottom_drawer_and_close_it",
    )
) + "\n"

C_COLUMNS = (
    "case_id,test_suite,dimension,arm,sub,suite,task_idx,instruction,window,"
    "trigger_criterion,target,revoked_predicate,revoked_object,family,level,param,"
    "semantics,max_steps,repair_window,expected_relation_after,s2_must_stay_true"
)

MINI_C_MATRIX = "\n".join(
    (
        C_COLUMNS,
        "d-l10-t000-early-l0,libero-rollback,in-execution,rollback,native,l10,0,"
        "turn on the stove and put the moka pot on it,early,s1 first true,s1,"
        "(Turnon flat_stove_1),flat_stove_1,joint,L0,,relation_then_resume,8,5,"
        "false,true",
        "d-l10-t000-mid-l1-d03,libero-rollback,in-execution,rollback,native,l10,0,"
        "turn on the stove and put the moka pot on it,mid,"
        "s2 displacement > 5 cm,s1,(Turnon flat_stove_1),flat_stove_1,joint,L1,"
        "d03,relation_then_resume,8,5,false,true",
        "d-l10-t033-later-l0,libero-rollback,in-execution,rollback,native,l10,33,"
        "put the black bowl in the bottom drawer of the cabinet and close it,later,"
        "distance to s2 goal < 8 cm,s1,"
        "(In akita_black_bowl_1 white_cabinet_1_bottom_region),"
        "akita_black_bowl_1,pose,L0,,relation_then_resume,8,5,false,true",
    )
) + "\n"

D_COLUMNS = (
    "case_id,test_suite,dimension,arm,sub,suite,struct_id,source_suite,order,"
    "task_id,instruction,window,trigger_criterion,target,revoked_predicate,"
    "revoked_object,family,level,param,semantics,max_steps,repair_window,"
    "expected_relation_after,s2_must_stay_true,bddl_name,init_source,"
    "bddl_sha256,pruned_init_sha256,valid,class"
)

MINI_D_MATRIX = "\n".join(
    (
        D_COLUMNS,
        "compose-rollback-goal_pair_00_01-early-l0,compose,in-execution,rollback,"
        "compose,compose,goal_pair_00_01,LIBERO_GOAL,ab,goal_pair_00_01,"
        "open the middle drawer of the cabinet and put the bowl on the stove,early,"
        "s1 first true,s1,(Open wooden_cabinet_1_middle_region),"
        "wooden_cabinet_1,joint,L0,,relation_then_resume,8,5,false,true,"
        "goal_pair_00_01,bddl/goal_pair_00_01.pruned_init,sha-bddl,sha-init,"
        "true,compatible",
        "compose-rollback-goal_pair_00_01-later-l0,compose,in-execution,rollback,"
        "compose,compose,goal_pair_00_01,LIBERO_GOAL,ab,goal_pair_00_01,"
        "open the middle drawer of the cabinet and put the bowl on the stove,later,"
        "distance to s2 goal < 8 cm,s1,(Open wooden_cabinet_1_middle_region),"
        "wooden_cabinet_1,joint,L0,,relation_then_resume,8,5,false,true,"
        "goal_pair_00_01,bddl/goal_pair_00_01.pruned_init,sha-bddl,sha-init,"
        "true,compatible",
    )
) + "\n"


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_mini_c(tmp_path: Path) -> tuple[Path, Path]:
    matrix = write_text(tmp_path / "c-mini.csv", MINI_C_MATRIX)
    b_matrix = write_text(tmp_path / "b-mini.csv", MINI_B_MATRIX)
    return matrix, b_matrix


def fake_libero_tree(root: Path, bddl_names: tuple[str, ...]) -> Path:
    package = root / "libero" / "libero"
    for directory in ("bddl_files", "init_files", "assets"):
        (package / directory).mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    for name in bddl_names:
        write_text(package / "bddl_files" / "libero_10" / f"{name}.bddl", "")
        write_text(package / "init_files" / "libero_10" / f"{name}.pruned_init", "")
    return root


def fake_compose_tree(root: Path, bddl_names: tuple[str, ...]) -> Path:
    for name in bddl_names:
        write_text(root / "bddl" / f"{name}.bddl", "")
        write_text(root / "bddl" / f"{name}.pruned_init", "")
    return root


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    for name in ("LIBERO_HOME", "LIBERO_CONFIG_PATH", "MUJOCO_GL", "COMPOSE_ROOT"):
        env.pop(name, None)
    return env


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(REPO_ROOT),
        env=_clean_env(),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


# ---------------------------------------------------------------------------
# C loader and asset paths
# ---------------------------------------------------------------------------


def test_c_loader_maps_bddl_from_b_matrix_and_resolves_paths(tmp_path: Path) -> None:
    matrix_path, b_matrix = write_mini_c(tmp_path)
    matrix = load_c_matrix(matrix_path, b_matrix=b_matrix)
    assert matrix.kind == "C"
    assert [case.case_id for case in matrix.cases] == [
        "d-l10-t000-early-l0",
        "d-l10-t000-mid-l1-d03",
        "d-l10-t033-later-l0",
    ]
    first = matrix.cases[0]
    assert first.bddl_name == (
        "KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it"
    )
    assert first.window == "early"
    assert first.trigger_criterion == "s1 first true"
    assert first.revoked_predicates == ("(Turnon flat_stove_1)",)
    assert first.revoked_objects == ("flat_stove_1",)
    assert first.expected_relation_after is False
    assert first.s2_must_stay_true is True
    assert first.level_spec.kind == "init"

    root = fake_libero_tree(
        tmp_path / "LIBERO",
        (
            "KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it",
            "KITCHEN_SCENE4_put_the_black_bowl_in_the_bottom_drawer_and_close_it",
        ),
    )
    bddl = first.bddl_path(root)
    init = first.init_path(root)
    assert bddl == (
        root
        / "libero"
        / "libero"
        / "bddl_files"
        / "libero_10"
        / "KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it.bddl"
    )
    assert init == (
        root
        / "libero"
        / "libero"
        / "init_files"
        / "libero_10"
        / "KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it.pruned_init"
    )
    assert bddl.is_file() and init.is_file()
    # A second path layout (LIBERO_HOME pointing at the package itself) works too.
    package_root = root / "libero" / "libero"
    assert first.bddl_path(package_root) == bddl
    # BCase-compatible attributes the BInjector relies on.
    assert first.is_control is False
    assert first.parsed_predicates == (("Turnon", "flat_stove_1"),)
    assert first.target == "s1"


def test_c_loader_rejects_unknown_task_mapping(tmp_path: Path) -> None:
    matrix = write_text(
        tmp_path / "c-unknown.csv",
        "\n".join(
            (
                C_COLUMNS,
                "d-l10-t999-early-l0,libero-rollback,in-execution,rollback,native,"
                "l10,999,unknown,early,s1 first true,s1,(Turnon stove_1),stove_1,"
                "joint,L0,,relation_then_resume,800,600,false,true",
            )
        )
        + "\n",
    )
    b_matrix = write_text(tmp_path / "b-mini.csv", MINI_B_MATRIX)
    with pytest.raises(ValueError, match="no bddl_name"):
        load_c_matrix(matrix, b_matrix=b_matrix)


# ---------------------------------------------------------------------------
# D loader and asset paths
# ---------------------------------------------------------------------------


def test_d_loader_resolves_compose_assets(tmp_path: Path) -> None:
    matrix_path = write_text(tmp_path / "d-mini.csv", MINI_D_MATRIX)
    matrix = load_d_matrix(matrix_path)
    assert matrix.kind == "D"
    assert matrix.summary()["by_window"] == {"early": 1, "mid": 0, "later": 1}
    case = matrix.cases[0]
    assert case.bddl_name == "goal_pair_00_01"
    assert case.asset_source == "compose"
    assert case.task_key == ("compose", "goal_pair_00_01")
    assert case.level_spec.kind == "init"
    root = fake_compose_tree(tmp_path / "compose", ("goal_pair_00_01",))
    assert case.bddl_path(root) == root / "bddl" / "goal_pair_00_01.bddl"
    assert case.init_path(root) == root / "bddl" / "goal_pair_00_01.pruned_init"
    assert case.bddl_path(root).is_file()
    assert case.init_path(root).is_file()


def test_load_window_matrix_auto_detects_kind(tmp_path: Path) -> None:
    c_path, b_matrix = write_mini_c(tmp_path)
    assert load_window_matrix(c_path, b_matrix=b_matrix).kind == "C"
    d_path = write_text(tmp_path / "d-mini.csv", MINI_D_MATRIX)
    assert load_window_matrix(d_path).kind == "D"


def test_real_c_and_d_matrices_load_and_d_assets_exist() -> None:
    c_matrix = load_c_matrix()
    assert c_matrix.kind == "C"
    assert len(c_matrix.cases) == 180
    assert c_matrix.summary()["by_window"] == {"early": 60, "mid": 60, "later": 60}
    assert len({case.bddl_name for case in c_matrix.cases}) == 9
    assert all(case.asset_source == "native" for case in c_matrix.cases)

    d_matrix = load_d_matrix()
    assert d_matrix.kind == "D"
    assert len(d_matrix.cases) == 528
    assert d_matrix.summary()["tasks"] == 176
    assert d_matrix.summary()["by_window"] == {"early": 176, "mid": 176, "later": 176}
    root = resolve_compose_root()
    assert root == DEFAULT_COMPOSE_ROOT or root.is_dir()
    missing = [
        case.case_id
        for case in d_matrix.cases
        if not case.bddl_path(root).is_file() or not case.init_path(root).is_file()
    ]
    assert missing == []


# ---------------------------------------------------------------------------
# selection
# ---------------------------------------------------------------------------


def test_selection_filters_and_shards(tmp_path: Path) -> None:
    matrix_path, b_matrix = write_mini_c(tmp_path)
    matrix = load_c_matrix(matrix_path, b_matrix=b_matrix)
    assert [case.case_id for case in select_window_cases(matrix, windows=["mid"])] == [
        "d-l10-t000-mid-l1-d03"
    ]
    assert select_window_cases(matrix, levels=["L0"])[0].case_id == "d-l10-t000-early-l0"
    shards = [
        [case.case_id for case in select_window_cases(matrix, shard_index=i, shard_count=3)]
        for i in range(3)
    ]
    assert sorted(case_id for shard in shards for case_id in shard) == sorted(
        case.case_id for case in matrix.cases
    )
    assert len({case_id for shard in shards for case_id in shard}) == 3


# ---------------------------------------------------------------------------
# pure progress helpers
# ---------------------------------------------------------------------------


def test_progress_helpers() -> None:
    assert lift_from_initial([0.0, 0.0, 0.05], [0.0, 0.0, 0.01]) == pytest.approx(0.04)
    assert xy_distance([0.0, 0.0, 1.0], [0.03, 0.04, 0.0]) == pytest.approx(0.05)
    progress, displacement = joint_progress(0.5, 0.0, 0.0, 1.0)
    assert progress == pytest.approx(0.5) and displacement == pytest.approx(0.5)
    progress, displacement = joint_progress(-0.25, 0.0, -1.0, 1.0)
    assert progress == pytest.approx(0.25) and displacement == pytest.approx(-0.25)
    assert joint_progress(0.0, 0.0, -1.0, 1.0) == (0.0, 0.0)
    # Degenerate range: no progress instead of a division by zero.
    assert joint_progress(1.0, 0.0, 0.0, 0.0)[0] == 0.0


def test_s2_undisturbed_gate() -> None:
    before = {"kind": "pose", "position": [0.0, 0.0, 0.0]}
    assert s2_undisturbed(before, {"kind": "pose", "position": [0.001, 0.0, 0.0]}) == (
        True,
        pytest.approx(0.001),
    )
    ok, distance = s2_undisturbed(
        before, {"kind": "pose", "position": [0.02, 0.0, 0.0]}
    )
    assert ok is False and distance == pytest.approx(0.02)
    assert s2_undisturbed(
        {"kind": "joint", "q": 0.1}, {"kind": "joint", "q": 0.1005}
    )[0] is True
    assert s2_undisturbed(
        {"kind": "joint", "q": 0.1}, {"kind": "joint", "q": 0.2}
    )[0] is False


# ---------------------------------------------------------------------------
# s2 resolution and trigger integration
# ---------------------------------------------------------------------------


class _FakeInjectorForS2:
    def __init__(self, indices: list[int]) -> None:
        self.goal_atom_index = indices


def _mini_cases(tmp_path: Path) -> list[WindowCase]:
    matrix_path, b_matrix = write_mini_c(tmp_path)
    return load_c_matrix(matrix_path, b_matrix=b_matrix).cases


def test_resolve_s2_pose_and_joint(tmp_path: Path) -> None:
    early_case, _, later_case = _mini_cases(tmp_path)
    injector = _FakeInjectorForS2([0])
    pose = resolve_s2(
        early_case,
        injector,
        [("Turnon", "flat_stove_1"), ("On", "moka_pot_1", "flat_stove_1_cook_region")],
    )
    assert pose.kind == "pose"
    assert pose.object_name == "moka_pot_1"
    assert pose.region_name == "flat_stove_1_cook_region"
    assert pose.index == 1

    joint = resolve_s2(
        later_case, injector, [("On", "bowl_1", "plate_1"), ("Open", "cabinet_1")]
    )
    assert joint.kind == "joint"
    assert joint.joint_name == "cabinet_1"
    assert joint.index == 1


def test_resolve_s2_rejects_unsupported_shapes(tmp_path: Path) -> None:
    case = _mini_cases(tmp_path)[0]
    with pytest.raises(UnsupportedWindowError, match="exactly one revoked goal atom"):
        resolve_s2(case, _FakeInjectorForS2([]), [("On", "a", "r")])
    with pytest.raises(UnsupportedWindowError, match="no pending s2"):
        resolve_s2(case, _FakeInjectorForS2([0]), [("Turnon", "flat_stove_1")])
    with pytest.raises(UnsupportedWindowError, match="unsupported s2 predicate"):
        resolve_s2(
            case,
            _FakeInjectorForS2([0]),
            [("On", "a", "r"), ("Viewed", "b", "c")],
        )
    with pytest.raises(UnsupportedWindowError, match="no goal region"):
        resolve_s2(case, _FakeInjectorForS2([0]), [("On", "a", "r"), ("In", "b")])


def test_window_trigger_integration_for_pose_s2(tmp_path: Path) -> None:
    _, mid_case, later_case = _mini_cases(tmp_path)
    config = WindowRunConfig(lift_min_m=0.03, preplacement_max_xy_m=0.20)
    pose_s2 = S2Target(
        index=1,
        atom=("On", "moka_pot_1", "flat_stove_1_cook_region"),
        kind="pose",
        predicate="on",
        object_name="moka_pot_1",
        region_name="flat_stove_1_cook_region",
    )
    trigger = _make_trigger(mid_case, config, pose_s2)
    assert isinstance(trigger, WindowTrigger)

    def obs(step: int, *, lift: float | None, xy: float = 0.5, settled: bool = True):
        return WindowObservation(
            step=step,
            s1_done=True,
            s1_settled=settled,
            s2_started=lift is not None and lift > 0,
            s2_lift_m=lift,
            s2_to_goal_xy_m=xy,
        )

    assert trigger.observe(obs(0, lift=0.029)) is False
    assert trigger.observe(obs(1, lift=0.030)) is True
    assert trigger.events == [("mid", 1)]

    later = _make_trigger(later_case, config, pose_s2)
    assert isinstance(later, WindowTrigger)
    assert later.observe(obs(0, lift=0.0, xy=0.01)) is False
    assert later.observe(obs(1, lift=0.04, xy=0.30)) is False
    assert later.observe(obs(2, lift=0.04, xy=0.20)) is True


def test_joint_progress_trigger_mid_and_later() -> None:
    def obs(step: int, progress: float) -> JointProgressObservation:
        return JointProgressObservation(
            step=step,
            s1_done=True,
            s1_settled=True,
            s2_started=progress > 0,
            s2_joint_progress=progress,
            s2_joint_displacement=progress,
            s2_joint_name="cabinet_1_bottom_joint",
        )

    mid = JointProgressTrigger(config=JointTriggerConfig(0.10, 0.60), target="mid")
    assert mid.observe(obs(0, 0.05)) is False
    assert mid.observe(obs(1, 0.10)) is True
    assert mid.events == [("mid", 1)]

    later = JointProgressTrigger(config=JointTriggerConfig(0.10, 0.60), target="later")
    assert later.observe(obs(0, 0.10)) is False  # mid seen, later not reached
    assert later.observe(obs(1, 0.59)) is False
    assert later.observe(obs(2, 0.60)) is True

    early = JointProgressTrigger(config=JointTriggerConfig(0.10, 0.60), target="early")
    assert early.observe(obs(0, 0.0)) is True


def test_make_trigger_uses_joint_path_for_joint_s2(tmp_path: Path) -> None:
    _, mid_case, _ = _mini_cases(tmp_path)
    joint_s2 = S2Target(
        index=1,
        atom=("Close", "white_cabinet_1_bottom_region"),
        kind="joint",
        predicate="close",
        joint_name="white_cabinet_1_bottom_region",
    )
    trigger = _make_trigger(mid_case, WindowRunConfig(), joint_s2)
    assert isinstance(trigger, JointProgressTrigger)
    thresholds = window_runner.resolved_thresholds(
        mid_case, WindowRunConfig(), joint_s2
    )
    assert thresholds["s2_kind"] == "joint"
    assert "joint_mid_fraction" in thresholds
    assert "lift_min_m" not in thresholds


# ---------------------------------------------------------------------------
# dry run
# ---------------------------------------------------------------------------


def test_dry_run_writes_only_plan_json(tmp_path: Path) -> None:
    matrix, b_matrix = write_mini_c(tmp_path)
    output = tmp_path / "dry-run"
    completed = run_script(
        "--dry-run",
        "--matrix",
        str(matrix),
        "--b-matrix",
        str(b_matrix),
        "--output",
        str(output),
        "--policy",
        "none",
        "--windows",
        "mid",
    )
    assert completed.returncode == 0, completed.stderr
    assert "dry-run" in completed.stdout
    plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
    assert plan["dry_run"] is True
    assert plan["matrix"]["kind"] == "C"
    assert plan["selected"] == 1
    assert plan["by_window"] == {"early": 0, "mid": 1, "later": 0}
    assert plan["case_ids"] == ["d-l10-t000-mid-l1-d03"]
    assert plan["cases"][0]["trigger_event"] == "enter_next_subgoal_lift"
    assert plan["cases"][0]["level"] == "L1"
    assert plan["cases"][0]["s2_must_stay_true"] is True
    # A dry run is not evidence: plan.json is the only artifact.
    assert sorted(path.name for path in output.iterdir()) == ["plan.json"]


def test_dry_run_d_reports_missing_assets_without_failing(tmp_path: Path) -> None:
    matrix = write_text(tmp_path / "d-mini.csv", MINI_D_MATRIX)
    output = tmp_path / "dry-run-d"
    compose_root = tmp_path / "empty-compose"
    completed = run_script(
        "--dry-run",
        "--matrix",
        str(matrix),
        "--compose-root",
        str(compose_root),
        "--output",
        str(output),
        "--policy",
        "none",
    )
    assert completed.returncode == 0, completed.stderr
    plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
    assert plan["matrix"]["kind"] == "D"
    assert plan["assets"]["missing_cases"] == 2
    assert plan["assets"]["compose_root"] == str(compose_root)
    assert plan["cases"][0]["assets_present"] is False


def test_dry_run_rejects_missing_matrix(tmp_path: Path) -> None:
    completed = run_script(
        "--dry-run",
        "--matrix",
        str(tmp_path / "missing.csv"),
        "--output",
        str(tmp_path / "out"),
    )
    assert completed.returncode != 0
    assert "missing.csv" in completed.stderr


# ---------------------------------------------------------------------------
# fake-environment smoke run
# ---------------------------------------------------------------------------


class _FakeWorld:
    def __init__(self) -> None:
        self.steps = 0
        self.injected = False


class _FakeEnv:
    def __init__(self, *, bddl_file_name, camera_heights, camera_widths, horizon):
        self.world = _FakeWorld()
        self.horizon = horizon
        self.env = types.SimpleNamespace(
            parsed_problem={
                "goal_state": [
                    ("Turnon", "flat_stove_1"),
                    ("On", "moka_pot_1", "flat_stove_1_cook_region"),
                ]
            }
        )

    def seed(self, seed):
        self.seed_value = seed

    def _observations(self):
        return {
            "robot0_eef_pos": [0.0, 0.0, 0.0],
            "robot0_gripper_qpos": [-0.04, 0.04],
        }

    def reset(self):
        return self._observations()

    def set_init_state(self, row):
        return self._observations()

    def step(self, action):
        self.world.steps += 1
        return self._observations(), 0.0, False, {}

    def regenerate_obs_from_state(self, state):
        return self._observations()

    def get_sim_state(self):
        return {"qpos": []}

    def close(self):
        pass


class _FakeInjector:
    """BInjector stand-in: s1 true until injection, s2 never completes."""

    def __init__(self, env, case, goal_atoms) -> None:
        self.case = case
        self.world = env.world
        self.goal_atom_index = [0]
        self.targets = {"fake_object": types.SimpleNamespace(body_id=0, kind="free")}

    def goal_truth(self):
        return [True, self.world.steps >= 10_000]

    def revoked_truth(self):
        return [not self.world.injected]

    def inject(self, gripper_qpos=None):
        self.world.injected = True
        return {
            "kind": "init",
            "goal_before": [True, False],
            "revoked_before": [True],
            "goal_after": [True, False],
            "revoked_after": [False],
            "relation_after": False,
            "goal_preserved": None,
            "applied": [],
            "geometry": {"delta_translation_m": 0.03, "delta_angle_rad": 0.0},
            "max_velocity": 0.0,
            "zero_velocity": True,
            "penetration_m": 0.0,
            "no_penetration": True,
            "object_released": True,
            "restorable": True,
            "restore_probe": {},
        }


class _FakeMonitor:
    """Scripted monitor: the window fires at step ``s1_done_from``."""

    s1_done_from = 2

    def __init__(self, injector, s2, config) -> None:
        self.injector = injector
        self.s2 = s2
        self.config = config
        self.first_s1_done_step = None
        self.first_s2_started_step = None
        self.s2_object_movable = True

    def observe(self, step, gripper_qpos):
        s1_done = step >= self.s1_done_from
        if s1_done and self.first_s1_done_step is None:
            self.first_s1_done_step = step
        metrics = {
            "step": step,
            "s1_done": s1_done,
            "s1_settled": s1_done,
            "s2_started": False,
            "s2_kind": "pose",
            "s2_lift_m": 0.0,
            "s2_to_goal_xy_m": 1.0,
            "s2_object_movable": True,
        }
        observation = WindowObservation(
            step=step,
            s1_done=s1_done,
            s1_settled=s1_done,
            s2_started=False,
            s2_lift_m=0.0,
            s2_to_goal_xy_m=1.0,
        )
        return observation, metrics

    def progress_snapshot(self):
        return {
            "kind": "pose",
            "atom": ["On", "moka_pot_1", "flat_stove_1_cook_region"],
            "predicate_true": False,
            "object": "moka_pot_1",
            "position": [0.0, 0.0, 0.05],
            "lift_m": 0.0,
            "to_goal_xy_m": 1.0,
        }


def _install_fake_simulation(monkeypatch: pytest.MonkeyPatch, *, s1_done_from: int) -> None:
    import libero_rollback.runtime.env as runtime_env
    import libero_rollback.runtime.perturbation as perturbation

    envs_module = types.ModuleType("libero.libero.envs")
    envs_module.OffScreenRenderEnv = _FakeEnv
    monkeypatch.setitem(sys.modules, "libero", types.ModuleType("libero"))
    monkeypatch.setitem(sys.modules, "libero.libero", types.ModuleType("libero.libero"))
    monkeypatch.setitem(sys.modules, "libero.libero.envs", envs_module)
    monkeypatch.setattr(
        runtime_env,
        "load_init_row",
        lambda path, row, init_python=None: ([1], [0.0]),
    )
    monkeypatch.setattr(perturbation, "BInjector", _FakeInjector)

    class _ScriptedMonitor(_FakeMonitor):
        pass

    _ScriptedMonitor.s1_done_from = s1_done_from
    monkeypatch.setattr(window_runner, "WindowMonitor", _ScriptedMonitor)


def _run_fake_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, s1_done_from: int = 2
) -> tuple[dict, Path]:
    pytest.importorskip("numpy")
    _install_fake_simulation(monkeypatch, s1_done_from=s1_done_from)
    matrix_path, b_matrix = write_mini_c(tmp_path)
    case = load_c_matrix(matrix_path, b_matrix=b_matrix).cases[0]
    root = fake_libero_tree(tmp_path / "LIBERO", (case.bddl_name,))
    config = WindowRunConfig(
        max_steps=0,
        repair_window=5,
        settle_steps=2,
        video=False,
        libero_home=str(root),
    )
    output = tmp_path / "run"
    summary = run_window_case(case=case, config=config, policy=None, output=output)
    episode_dir = output / case.suite / case.case_id / f"seed-{config.seed}"
    return summary, episode_dir / "summary.json"


def test_run_window_case_triggers_injects_and_repairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary, summary_path = _run_fake_case(tmp_path, monkeypatch)
    assert summary["status"] == "ok", summary.get("error")
    assert summary["case_id"] == "d-l10-t000-early-l0"
    assert summary["window"] == "early"
    assert summary["trigger_criterion"] == "s1 first true"
    assert summary["trigger_event"] == "enter_first_subgoal_completed"
    assert summary["trigger_reached"] is True
    assert summary["trigger_step"] == 2
    assert summary["injection_step"] == 2
    # Matrix repair_window=5 + config repair_window=5 -> 5 steps after injection.
    assert summary["repair_budget_steps"] == 5
    assert summary["repair_steps_used"] == 5
    assert summary["total_budget_steps"] == 7
    assert summary["steps"] == 7
    assert summary["max_steps"] == 8  # row budget (config max_steps=0)
    assert summary["case_valid"] is True
    assert summary["relation_before"] is True
    assert summary["relation_after_injection"] is False
    assert summary["relation_final"] is False
    assert summary["recovered"] is False
    assert summary["recovery"] is False
    assert summary["final_goal_truth"] == [True, False]
    assert summary["revoked_goal_indices"] == [0]
    assert summary["pending_goal_indices"] == [1]
    assert summary["final_pending_truth"] == [False]
    assert summary["terminal_state"] == "neither"
    assert summary["subtask_progress"] == pytest.approx(0.5)
    assert summary["s2_undisturbed_by_injection"] is True
    assert summary["s2"]["kind"] == "pose"
    assert summary["resolved_thresholds"]["lift_min_m"] == pytest.approx(0.03)
    assert summary["resolved_thresholds"]["preplacement_max_xy_m"] == pytest.approx(0.20)
    assert summary_path.is_file()
    saved = json.loads(summary_path.read_text(encoding="utf-8"))
    assert saved["case_valid"] is True
    assert saved["window"] == "early"


def test_run_window_case_records_unreached_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary, summary_path = _run_fake_case(
        tmp_path, monkeypatch, s1_done_from=10_000
    )
    assert summary["status"] == "ok", summary.get("error")
    assert summary["trigger_reached"] is False
    assert summary["injection_step"] is None
    assert summary["repair_budget_steps"] is None
    assert summary["repair_steps_used"] is None
    assert summary["case_valid"] is False
    assert summary["recovered"] is None
    assert summary["termination"] == "trigger_not_reached"
    assert "not reached" in summary["trigger_skipped_reason"]
    assert summary["steps"] == summary["total_budget_steps"] == 8
    assert summary_path.is_file()


def test_run_window_case_fails_clearly_without_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("numpy")
    _install_fake_simulation(monkeypatch, s1_done_from=2)
    matrix_path, b_matrix = write_mini_c(tmp_path)
    case = load_c_matrix(matrix_path, b_matrix=b_matrix).cases[0]
    config = WindowRunConfig(
        repair_window=5, settle_steps=1, video=False, libero_home=str(tmp_path / "no-libero")
    )
    summary = run_window_case(
        case=case, config=config, policy=None, output=tmp_path / "run"
    )
    assert summary["status"] == "error"
    assert "FileNotFoundError" in summary["error"]


def test_preflight_assets_raises_with_paths(tmp_path: Path) -> None:
    matrix_path, b_matrix = write_mini_c(tmp_path)
    case = load_c_matrix(matrix_path, b_matrix=b_matrix).cases[0]
    config = WindowRunConfig(libero_home=str(tmp_path / "no-libero"))
    with pytest.raises(FileNotFoundError, match="window matrix assets missing"):
        window_runner._preflight_assets([case], config)


def test_real_run_fails_clearly_without_libero_home(tmp_path: Path) -> None:
    matrix, b_matrix = write_mini_c(tmp_path)
    completed = run_script(
        "--matrix",
        str(matrix),
        "--b-matrix",
        str(b_matrix),
        "--output",
        str(tmp_path / "run"),
        "--policy",
        "none",
        "--max-cases",
        "1",
    )
    assert completed.returncode == 2, completed.stderr
    assert "LIBERO checkout not configured" in completed.stderr


def test_joint_trigger_requires_s1_completion() -> None:
    def obs(progress: float, s1_done: bool) -> JointProgressObservation:
        return JointProgressObservation(
            step=0,
            s1_done=s1_done,
            s1_settled=s1_done,
            s2_started=True,
            s2_joint_progress=progress,
            s2_joint_displacement=progress,
        )

    trigger = JointProgressTrigger(config=JointTriggerConfig(0.10, 0.60), target="mid")
    assert trigger.observe(obs(0.60, False)) is False
    assert trigger.observe(obs(0.60, True)) is True


def test_run_window_matrix_preflights_before_bootstrap(tmp_path: Path) -> None:
    matrix_path, b_matrix = write_mini_c(tmp_path)
    matrix = load_c_matrix(matrix_path, b_matrix=b_matrix)
    root = tmp_path / "LIBERO"
    package = root / "libero" / "libero"
    for directory in ("bddl_files", "init_files", "assets"):
        (package / directory).mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    output = tmp_path / "run"
    with pytest.raises(FileNotFoundError, match="window matrix assets missing"):
        window_runner.run_window_matrix(
            matrix=matrix,
            cases=[matrix.cases[0]],
            output=output,
            model="none",
            config=WindowRunConfig(libero_home=str(root)),
        )
    # The preflight fails before the manifest / LIBERO config are written.
    assert not (output / "run-manifest.json").exists()
    assert not (output / "libero_config").exists()
