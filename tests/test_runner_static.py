"""Static tests for the runner: dry-run planning and module boundaries.

These tests never start a simulation and never load a model: they exercise
``scripts/run_b_matrix.py --dry-run`` (the README §6.3 requirement) in a
subprocess and assert that importing the runner does not pull numpy/torch/LIBERO
into the process.

The subprocess uses the same interpreter as pytest, so the tests behave the same
way in CI (``uv run pytest``) and in the repo-local venv.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "run_b_matrix.py"

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
    path = tmp_path / "b-matrix-mini.csv"
    path.write_text(MINI_MATRIX, encoding="utf-8")
    return path


def _clean_env() -> dict[str, str]:
    """Environment without simulation configuration (dry-run must not need it)."""

    env = dict(os.environ)
    for name in ("LIBERO_HOME", "LIBERO_CONFIG_PATH", "MUJOCO_GL"):
        env.pop(name, None)
    return env


def run_script(*args: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        env=_clean_env(),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _run_python(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        env=_clean_env(),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def test_import_runner_is_static_layer_only() -> None:
    """The top of ``libero_rollback.runner`` must not pull simulation deps."""

    code = (
        "import json, sys\n"
        "import libero_rollback.runner\n"
        "heavy = [name for name in ('numpy', 'torch', 'mujoco', 'robosuite',"
        " 'libero', 'PIL', 'cv2', 'av', 'imageio') if name in sys.modules]\n"
        "print(json.dumps(heavy))\n"
    )
    completed = _run_python(code)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout.strip().splitlines()[-1]) == []


def test_import_policies_is_lazy() -> None:
    code = (
        "import json, sys\n"
        "import libero_rollback.policies\n"
        "heavy = [name for name in ('numpy', 'torch', 'lerobot', 'openpi', 'libero')"
        " if name in sys.modules]\n"
        "print(json.dumps(heavy))\n"
    )
    completed = _run_python(code)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout.strip().splitlines()[-1]) == []


def test_dry_run_writes_only_plan_json(tmp_path: Path) -> None:
    matrix = write_mini_matrix(tmp_path)
    output = tmp_path / "dry-run"
    completed = run_script(
        "--dry-run",
        "--matrix",
        str(matrix),
        "--output",
        str(output),
        "--max-cases",
        "3",
        "--policy",
        "none",
    )
    assert completed.returncode == 0, completed.stderr
    assert "dry-run" in completed.stdout

    plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
    assert plan["dry_run"] is True
    assert plan["selected"] == 3
    assert plan["case_ids"] == [
        "b-goal-t000-c0",
        "b-goal-t000-g-l0",
        "b-goal-t132-c0",
    ]
    assert plan["defaults"]["policy"] == "none"
    # A dry run is not evidence: plan.json is the only artifact.
    assert sorted(path.name for path in output.iterdir()) == ["plan.json"]


def test_dry_run_defaults_to_pi05_without_loading_it(tmp_path: Path) -> None:
    matrix = write_mini_matrix(tmp_path)
    output = tmp_path / "dry-run-default"
    completed = run_script(
        "--dry-run",
        "--matrix",
        str(matrix),
        "--output",
        str(output),
        "--max-cases",
        "1",
    )
    assert completed.returncode == 0, completed.stderr
    plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
    assert plan["defaults"]["policy"] == "pi05"
    assert plan["selected"] == 1


def test_sharded_dry_runs_partition_the_matrix(tmp_path: Path) -> None:
    matrix = write_mini_matrix(tmp_path)
    collected: list[str] = []
    for index in range(2):
        output = tmp_path / f"shard-{index}"
        completed = run_script(
            "--dry-run",
            "--matrix",
            str(matrix),
            "--output",
            str(output),
            "--shard-index",
            str(index),
            "--shard-count",
            "2",
        )
        assert completed.returncode == 0, completed.stderr
        plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
        assert plan["shard"] == {"index": index, "count": 2}
        collected.extend(plan["case_ids"])
    assert len(collected) == len(set(collected)) == 8


def test_dry_run_without_libero_is_not_blocked(tmp_path: Path) -> None:
    """``LIBERO_HOME`` is unset in ``_clean_env``; dry-run still succeeds."""

    matrix = write_mini_matrix(tmp_path)
    completed = run_script(
        "--dry-run", "--matrix", str(matrix), "--output", str(tmp_path / "out")
    )
    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / "out" / "plan.json").is_file()


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


def test_aggregate_writes_run_summary(tmp_path: Path) -> None:
    from libero_rollback.runner import aggregate_episodes

    episodes = [
        {
            "case_id": "b-goal-t000-c0",
            "suite": "goal",
            "level": "C0",
            "param": None,
            "target": "c0",
            "status": "ok",
            "trigger_reached": True,
            "case_valid": True,
            "recovered": True,
            "success": True,
            "steps": 600,
        },
        {
            "case_id": "b-goal-t000-g-l0",
            "suite": "goal",
            "level": "L0",
            "param": None,
            "target": "g",
            "status": "ok",
            "trigger_reached": True,
            "case_valid": True,
            "recovered": False,
            "success": False,
            "steps": 700,
        },
        {"case_id": "b-goal-t000-g-l1-d03", "status": "error"},
    ]
    summary = aggregate_episodes(episodes, tmp_path, {"seed": 0})
    assert summary["cases"] == 3
    assert summary["ok"] == 2
    assert summary["errors"] == 1
    assert summary["triggered"] == 2
    assert summary["valid"] == 2
    assert summary["recoverable_valid"] == 1
    assert summary["recovered"] == 0
    assert summary["recovery_rate"] == 0.0
    assert summary["controls"] == 1
    assert summary["control_rate"] == 1.0
    assert (tmp_path / "run-summary.json").is_file()
    assert (tmp_path / "report.md").is_file()


# ---------------------------------------------------------------------------
# episode-loop bookkeeping with a fake environment (no simulation import)
# ---------------------------------------------------------------------------


def _fake_libero_tree(root: Path) -> Path:
    package = root / "libero" / "libero"
    for directory in ("bddl_files", "init_files", "assets"):
        (package / directory).mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    return root


class _FakeWorld:
    def __init__(self) -> None:
        self.steps = 0
        self.injected = False


class _FakeInjector:
    """Minimal BInjector stand-in: all_done at step 3, revocation never undone."""

    def __init__(self, env, case, goal_atoms) -> None:
        self.case = case
        self.world = env.world
        self.targets = {"fake_object": types.SimpleNamespace(body_id=0, kind="free")}
        self.sim = types.SimpleNamespace(
            data=types.SimpleNamespace(body_xpos=[[0.0, 0.0, 0.0]])
        )

    def goal_truth(self):
        return [self.world.steps >= 3]

    def revoked_truth(self):
        if self.case.is_control:
            return [True]
        return [not self.world.injected]

    def all_goal_true(self):
        return all(self.goal_truth())

    def inject(self, gripper_qpos=None):
        self.world.injected = True
        control = self.case.is_control
        return {
            "kind": "c0" if control else "init",
            "goal_before": [True],
            "revoked_before": [True],
            "goal_after": [True],
            "revoked_after": [True] if control else [False],
            "relation_after": bool(control),
            "goal_preserved": None,
            "applied": [],
            "geometry": {"delta_translation_m": 0.0, "delta_angle_rad": 0.0},
            "max_velocity": 0.0,
            "zero_velocity": True,
            "penetration_m": 0.0,
            "no_penetration": True,
            "object_released": True,
            "restorable": True,
            "restore_probe": {},
        }


class _FakeEnv:
    def __init__(self, *, bddl_file_name, camera_heights, camera_widths, horizon):
        self.world = _FakeWorld()
        self.horizon = horizon
        self.env = types.SimpleNamespace(
            parsed_problem={"goal_state": [("On", "fake_object", "region")]}
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


def _install_fake_simulation(monkeypatch: pytest.MonkeyPatch) -> None:
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


def _run_fake_case(
    tmp_path: Path, case_id: str, **config_kwargs
) -> tuple[dict, Path]:
    from libero_rollback.matrices import load_b_matrix
    from libero_rollback.runner import RunConfig, episode_directory, run_case

    matrix = load_b_matrix(write_mini_matrix(tmp_path))
    case = next(item for item in matrix.cases if item.case_id == case_id)
    root = _fake_libero_tree(tmp_path / "LIBERO")
    config = RunConfig(
        max_steps=20,
        delay_steps=10,
        repair_window=5,
        video=False,
        libero_home=str(root),
        **config_kwargs,
    )
    output = tmp_path / "run"
    summary = run_case(case=case, config=config, policy=None, output=output)
    return summary, episode_directory(output, case, config.seed) / "summary.json"


def test_run_case_keeps_repair_window_after_injection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("numpy")
    _install_fake_simulation(monkeypatch)
    summary, summary_path = _run_fake_case(tmp_path, "b-goal-t000-g-l0")
    assert summary["status"] == "ok", summary.get("error")
    assert summary["trigger_reached"] is True
    # 10 settle steps happen before the loop, so the loop sees all_done at its
    # first step; injection then happens at loop step 1 + delay 10.
    assert summary["injection_step"] == 11
    # The matrix ``repair_window`` column (300) is authoritative, not the
    # RunConfig fallback, and the repair window is appended after injection.
    assert summary["repair_budget_steps"] == 300
    assert summary["repair_steps_used"] == 300
    assert summary["total_budget_steps"] == 311
    assert summary["steps"] == 311
    assert summary["recovered"] is False
    assert summary["recovery"] is False
    assert summary["case_valid"] is True
    assert summary["validity"]["all_revoked_false_after_intervention"] is True
    assert summary_path.is_file()


def test_run_case_control_is_not_counted_as_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("numpy")
    _install_fake_simulation(monkeypatch)
    summary, _ = _run_fake_case(tmp_path, "b-goal-t000-c0")
    assert summary["status"] == "ok", summary.get("error")
    assert summary["level"] == "C0"
    assert summary["recovered"] is True
    assert summary["recovery"] is None
    assert summary["case_valid"] is True


def test_run_case_writes_error_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("numpy")
    import libero_rollback.runtime.env as runtime_env

    _install_fake_simulation(monkeypatch)

    def _raise(*args, **kwargs):
        raise RuntimeError("init unreadable")

    monkeypatch.setattr(runtime_env, "load_init_row", _raise)
    summary, summary_path = _run_fake_case(tmp_path, "b-goal-t000-c0")
    assert summary["status"] == "error"
    assert "init unreadable" in summary["error"]
    assert summary_path.is_file()

class _RecoveringFakeInjector(_FakeInjector):
    """Recovers one step after injection, so the opt-in early stop is testable."""

    def inject(self, gripper_qpos=None):
        result = super().inject(gripper_qpos)
        self.injected_at = self.world.steps
        return result

    def revoked_truth(self):
        if self.case.is_control:
            return [True]
        injected_at = getattr(self, "injected_at", None)
        if injected_at is None:
            return [True]
        return [self.world.steps >= injected_at + 1]


def test_run_case_stops_at_first_recovery_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("numpy")
    import libero_rollback.runtime.perturbation as perturbation

    _install_fake_simulation(monkeypatch)
    monkeypatch.setattr(perturbation, "BInjector", _RecoveringFakeInjector)
    summary, summary_path = _run_fake_case(
        tmp_path, "b-goal-t000-g-l0", stop_on_recovery=True
    )
    assert summary["status"] == "ok", summary.get("error")
    assert summary["early_stopped"] is True
    assert summary["stop_reason"] == "recovery"
    assert summary["termination"] == "recovered"
    assert summary["recovered"] is True
    assert summary["steps"] == summary["injection_step"] + 1
    assert summary["repair_steps_used"] == 1
    assert summary["total_budget_steps"] == summary["injection_step"] + 300
    assert summary_path.is_file()


def test_run_case_control_never_stops_on_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("numpy")
    import libero_rollback.runtime.perturbation as perturbation

    _install_fake_simulation(monkeypatch)
    monkeypatch.setattr(perturbation, "BInjector", _RecoveringFakeInjector)
    summary, _ = _run_fake_case(tmp_path, "b-goal-t000-c0", stop_on_recovery=True)
    assert summary["status"] == "ok", summary.get("error")
    assert summary["early_stopped"] is False
    assert summary["termination"] == "step_limit"
    assert summary["steps"] == summary["total_budget_steps"]
