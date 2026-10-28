"""Audit result provenance and the recovery denominator without model dependencies."""

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_current_report import (  # noqa: E402
    analyse,
    copy_media,
    evaluation_settings,
    provenance_status,
    run_index,
    sha256,
)

from libero_rollback.runtime import runtime_binding  # noqa: E402


def test_provenance_rejects_missing_stale_and_mismatched_records(tmp_path):
    case_path = next((ROOT / "dataset/progress-failure/cases").glob("*.yaml"))
    case = yaml.safe_load(case_path.read_text())
    assert provenance_status(tmp_path, case, case_path) == "historical_unverified"
    plan = {"case_sha256": "obsolete", "fingerprint": "run-1"}
    (tmp_path / "execution-plan.json").write_text(json.dumps(plan))
    assert provenance_status(tmp_path, case, case_path) == "stale_definition"
    plan["case_sha256"] = sha256(case_path)
    (tmp_path / "execution-plan.json").write_text(json.dumps(plan))
    assert provenance_status(tmp_path, case, case_path) == "stale_binding"
    (tmp_path / "binding.yaml").write_text(yaml.safe_dump(runtime_binding(case)))
    assert provenance_status(tmp_path, case, case_path) == "incomplete"
    completion = {"fingerprint": "run-2", "returncode": 0}
    (tmp_path / "completion.json").write_text(json.dumps(completion))
    assert provenance_status(tmp_path, case, case_path) == "provenance_mismatch"
    completion["fingerprint"] = "run-1"
    (tmp_path / "completion.json").write_text(json.dumps(completion))
    assert provenance_status(tmp_path, case, case_path) is None
    completion["returncode"] = 1
    (tmp_path / "completion.json").write_text(json.dumps(completion))
    assert provenance_status(tmp_path, case, case_path) == "runtime_error"


def test_multiple_attempts_remain_available_for_provenance_selection(tmp_path):
    for name in ("old", "new"):
        (tmp_path / name / "case-1").mkdir(parents=True)
    assert len(run_index((tmp_path / "old", tmp_path / "new"))["case-1"]) == 2


def test_report_preserves_model_seed_budget_and_runtime_scope(tmp_path):
    assert evaluation_settings(tmp_path) == {}
    plan = {
        "command": [
            "python", "/overlay/tools/run_benchmark.py", "--model", "pi05", "--mode", "both"
        ],
        "seed": 1,
        "max_steps": 600,
        "runtime_sha256": "runtime-digest",
    }
    (tmp_path / "execution-plan.json").write_text(json.dumps(plan))
    assert evaluation_settings(tmp_path) == {
        "model": "pi05",
        "seed": 1,
        "max_steps": 600,
        "mode": "both",
        "runtime_sha256": "runtime-digest",
        "runtime_root": "/overlay",
    }


def test_controls_and_external_restoration_do_not_dilute_recovery_rate():
    statuses = [
        "valid_recovered",
        "valid_not_recovered",
        "valid_control",
        "valid_relation_preserving_probe",
        "valid_external_restoration",
        "injection_invalid",
        "protocol_incomplete",
        "stale_definition",
    ]
    rows = [
        {"status": status, "result_file": "result.json", "videos": [], "baseline_videos": []}
        for status in statuses
    ]
    analysis = analyse(rows, {"dataset_version": "1.0.0"}, ())
    assert analysis["evaluable_rollback_count"] == 2
    assert analysis["recovery_percent_of_evaluable_rollbacks"] == 50.0
    assert analysis["valid_injection_count"] == 5


def test_video_copy_refreshes_changed_content_of_same_size(tmp_path):
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    source = attempt / "baseline.mp4"
    source.write_bytes(b"old")
    report = tmp_path / "report"
    _, media = copy_media(attempt, report, "case-1")
    source.write_bytes(b"new")
    _, updated = copy_media(attempt, report, "case-1")
    assert media[0]["sha256"] != updated[0]["sha256"]
    assert (report / updated[0]["path"]).read_bytes() == b"new"
