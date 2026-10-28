"""Exercise process boundaries and provenance without a simulator or model."""

import json
import sys
from pathlib import Path
from types import MappingProxyType

import pytest
import yaml

from libero_rollback.runtime import RuntimeBridgeError, run_case

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_grid_cases  # noqa: E402
from runtime_preflight import json_value  # noqa: E402
from summarize_preflight import summarize  # noqa: E402

CASE_ID = "libero-10-09-rollback-all_done-d0-book-initial-upright-restore"
CASE = ROOT / "dataset/progress-failure/cases" / f"{CASE_ID}.yaml"


def test_preflight_serializes_frozen_parameters_without_stringifying_truth():
    frozen = MappingProxyType(
        {"truth": True, "offset": (0.0, 0.1), "child": MappingProxyType({"n": 3})}
    )
    assert json.loads(json.dumps(json_value(frozen))) == {
        "truth": True,
        "offset": [0.0, 0.1],
        "child": {"n": 3},
    }


@pytest.mark.parametrize(
    "digest,success,restored,expected",
    [
        ("stale", True, True, "stale_definition"),
        ("current", False, True, "baseline_failed"),
        ("current", True, False, "state_restoration_failed"),
        ("current", True, True, "preflight_rollback"),
    ],
)
def test_native_evidence_requires_current_definition_success_and_state_restore(
    tmp_path, digest, success, restored, expected
):
    import hashlib

    payload = {
        "task_profile": "libero_10_t276",
        "baseline_native_success": success,
        "cases": {
            CASE_ID: {
                "case_id": CASE_ID,
                "case_sha256": hashlib.sha256(CASE.read_bytes()).hexdigest()
                if digest == "current"
                else digest,
                "status": "preflight_rollback",
                "coordinates_restored": restored,
            },
        },
    }
    (tmp_path / "libero_10_t276.json").write_text(json.dumps(payload))
    result = summarize(tmp_path)
    assert result["cases"][CASE_ID]["status"] == expected
    assert result["model_recovery_evaluated"] is False
    assert result["definition_count"] == sum(result["counts"].values())


def fake_runtime(tmp_path):
    runtime = tmp_path / "runtime"
    (runtime / "tools").mkdir(parents=True)
    (runtime / "configs/task_profiles").mkdir(parents=True)
    (runtime / "configs/task_profiles/libero_10_t276.yaml").write_text(
        "task_profile:\n  milestones:\n    next_subgoal_completed: {}\n"
    )
    (runtime / "rollback-capabilities.json").write_text(
        json.dumps({"capabilities": ["completion_precondition"]})
    )
    (runtime / "rollback_preflight.py").write_text("# fake capability for command testing\n")
    (runtime / "tools/run_benchmark.py").write_text(
        "import json,sys\n"
        "from pathlib import Path\n"
        "out=Path(sys.argv[sys.argv.index('--output')+1])/'attempt'\n"
        "out.mkdir()\n"
        "(out/'results.json').write_text(json.dumps({}))\n"
    )
    return runtime


def test_completion_capability_cannot_hide_a_disabled_profile_event(tmp_path):
    from libero_rollback.runtime import check_runtime_capabilities, load_case_for_runtime

    runtime = fake_runtime(tmp_path)
    profile = runtime / "configs/task_profiles/libero_10_t276.yaml"
    profile.write_text("task_profile: {}")
    with pytest.raises(RuntimeBridgeError, match="does not enable completion milestone"):
        check_runtime_capabilities(load_case_for_runtime(CASE), runtime)


def test_run_case_records_process_provenance_and_refuses_overwrite(tmp_path):
    runtime = fake_runtime(tmp_path)
    output = tmp_path / "output"
    options = dict(
        python_executable=Path(sys.executable),
        libero_root=tmp_path,
        runtime_root=runtime,
        adapter="pi05",
        checkpoint=None,
        output_root=output,
    )
    run_case(CASE, **options)
    plan = json.loads((output / "execution-plan.json").read_text())
    completion = json.loads((output / "completion.json").read_text())
    assert plan["case_id"] == CASE_ID
    assert len(plan["case_sha256"]) == len(plan["runtime_sha256"]) == 64
    assert completion["fingerprint"] == plan["fingerprint"]
    assert completion["results"] == ["attempt/results.json"]
    assert completion["returncode"] == 0
    assert yaml.safe_load((output / "binding.yaml").read_text()) == plan["binding"]
    assert (output / "runtime-binding.yaml").is_file()
    original = (output / "execution-plan.json").read_bytes()
    with pytest.raises(RuntimeBridgeError, match="already contains evidence"):
        run_case(CASE, **options)
    assert (output / "execution-plan.json").read_bytes() == original


@pytest.mark.parametrize("baseline_only", [True, False])
def test_grid_only_passes_paired_flags_in_both_mode(tmp_path, monkeypatch, baseline_only):
    runtime = fake_runtime(tmp_path)
    output = tmp_path / "grid"
    argv = [
        "run_grid_cases.py",
        "--dry-run",
        "--model",
        "pi05",
        "--runtime-root",
        str(runtime),
        "--cases",
        str(CASE.parent),
        "--case-id",
        CASE_ID,
        "--output",
        str(output),
    ]
    if baseline_only:
        argv += ["--baseline-only", "--native-preflight"]
    monkeypatch.setattr(sys, "argv", argv)
    assert run_grid_cases.main() == 0
    command = json.loads((output / CASE_ID / "execution-plan.json").read_text())["command"]
    assert ("--strict-paired-baseline" in command) is (not baseline_only)
    assert ("--require-successful-baseline" in command) is (not baseline_only)
    assert command[command.index("--mode") + 1] == ("baseline" if baseline_only else "both")
