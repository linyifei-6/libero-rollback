"""CLI integration tests that must pass without LIBERO / MuJoCo / torch."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libero_rollback.cli import EXIT_FAIL, EXIT_OK, EXIT_SETUP, main

REPO_ROOT = Path(__file__).resolve().parents[1]
B_MATRIX = REPO_ROOT / "dataset" / "matrices" / "b-matrix.csv"


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--version"])
    assert raised.value.code == 0


def test_list_requires_matrix() -> None:
    assert main(["list", "--matrix", "does-not-exist.csv"]) == EXIT_SETUP


@pytest.mark.skipif(not B_MATRIX.is_file(), reason="B matrix not migrated yet")
def test_list_summarizes_b_matrix(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["list", "--matrix", str(B_MATRIX), "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["cases"] == 442
    assert payload["tasks"] == 40
    assert payload["by_suite"] == {"goal": 85, "l10": 197, "object": 80, "spatial": 80}


@pytest.mark.skipif(
    not (REPO_ROOT / "dataset" / "manifest.yaml").is_file(), reason="dataset not migrated"
)
def test_validate_dataset_passes(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["validate", "--dataset", str(REPO_ROOT / "dataset")])
    output = capsys.readouterr().out
    assert code == EXIT_OK, output
    assert "PASS" in output


def _mini_matrix(path: Path) -> Path:
    header = (
        "case_id,suite,task_idx,bddl_name,instruction,target,revoked_objects,"
        "revoked_predicates,family,level,param,semantics,trigger,delay_steps,"
        "repair_window,expected_relation_after,n_targets\n"
    )
    rows = [
        "b-goal-t000-c0,goal,0,open_the_middle_drawer_of_the_cabinet,Open the drawer,"
        "c0,,,-,C0,,relation_holds_control,all_done,10,300,true,1",
        "b-goal-t000-g-l0,goal,0,open_the_middle_drawer_of_the_cabinet,Open the drawer,"
        "g,wooden_cabinet_1,(Open wooden_cabinet_1_middle_region),joint,L0,,"
        "relation_then_resume,all_done,10,300,false,1",
        "b-goal-t000-g-l1-d03,goal,0,open_the_middle_drawer_of_the_cabinet,"
        "Open the drawer,g,wooden_cabinet_1,(Open wooden_cabinet_1_middle_region),"
        "joint,L1,d03,relation_then_resume,all_done,10,300,false,1",
    ]
    path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_run_dry_run_writes_plan(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    matrix = _mini_matrix(tmp_path / "b-mini.csv")
    output = tmp_path / "run"
    code = main(
        [
            "run",
            "--matrix",
            str(matrix),
            "--output",
            str(output),
            "--dry-run",
            "--model",
            "none",
            "--max-cases",
            "2",
        ]
    )
    assert code == EXIT_OK, capsys.readouterr().err
    plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
    assert plan["dry_run"] is True
    assert plan["selected"] == 2
    assert len(plan["case_ids"]) == 2
    assert not (output / "episodes.jsonl").exists()


def test_report_and_leaderboard(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run = tmp_path / "run"
    run.mkdir()
    episode = {
        "status": "ok",
        "case_id": "b-goal-t000-g-l0",
        "suite": "goal",
        "level": "L0",
        "target": "g",
        "trigger_reached": True,
        "case_valid": True,
        "verdict": "valid_recovered",
        "recovered": True,
        "steps": 600,
    }
    (run / "episodes.jsonl").write_text(json.dumps(episode) + "\n", encoding="utf-8")
    (run / "run-manifest.json").write_text(
        json.dumps({"defaults": {"policy": "pi05", "max_steps": 600}}), encoding="utf-8"
    )
    assert main(["report", "--run", str(run), "--out", str(tmp_path / "report")]) == EXIT_OK
    assert (tmp_path / "report" / "index.html").is_file()
    assert main(["leaderboard", "validate", "--run", str(run)]) == EXIT_OK


def test_leaderboard_flags_bad_submission(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "episodes.jsonl").write_text(
        json.dumps({"status": "ok", "suite": "goal"}) + "\n", encoding="utf-8"
    )
    assert main(["leaderboard", "validate", "--run", str(run)]) == EXIT_FAIL


def test_report_rejects_missing_run(tmp_path: Path) -> None:
    assert main(["report", "--run", str(tmp_path / "nope")]) == EXIT_SETUP

@pytest.mark.skipif(not (REPO_ROOT / "dataset" / "lite.yaml").is_file(), reason="lite split not migrated")
def test_run_dry_run_lite_split(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "lite-run"
    code = main(
        [
            "run",
            "--output",
            str(output),
            "--dry-run",
            "--model",
            "none",
            "--split",
            "lite",
            "--dataset",
            str(REPO_ROOT / "dataset"),
        ]
    )
    assert code == EXIT_OK, capsys.readouterr().err
    plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
    # Phase 1: the runner only executes B cases; lite has 10 B cases.
    assert plan["selected"] == 10
    assert all(case_id.startswith("b-") for case_id in plan["case_ids"])
