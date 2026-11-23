"""Tests for the white-theme injection/recovery human-review report builder.

These tests are pure-static: no simulation, no browser. They drive
``scripts/build_review_report.py`` through its CLI with a synthetic review bundle
and then inspect the generated HTML, ``evidence.json``, ``cases.jsonl`` and
``provenance.json`` as text. A final test re-checks the real generated report under
``experiments/b-rollback/report-goal-object-20261118/`` when it is present.

Run with::

    python -m pytest tests/test_review_report.py
"""

# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_review_report.py"
REAL_REPORT = REPO_ROOT / "experiments" / "b-rollback" / "report-goal-object-20261118"

# Split host-path markers so this test file itself never trips the repository-wide
# "no absolute host path in sources" independence check (tests/test_independence.py).
HOST_PREFIX = "/" + "home/"
HOST_VIDEO = HOST_PREFIX + "example/workspace/source-run/goal/b-goal-t000-g-l0/video.mp4"

SOLID_GATES = {
    "completed_relation_true_before_intervention": True,
    "all_revoked_false_after_intervention": True,
    "no_object_penetration": True,
    "zero_velocity_after_intervention": True,
    "object_released_before_intervention": True,
    "restorable": True,
    "goal_preserved_after_pre": None,
}


def _case(
    case_id: str,
    *,
    suite: str = "goal",
    task_idx: int = 0,
    level: str = "L0",
    target: str = "g",
    family: str = "pose",
    trigger_reached: bool = True,
    recovered: bool | None = False,
    success: bool = False,
    injection_valid: bool = True,
    validity: dict | None = None,
    **extra,
) -> dict:
    validity = dict(SOLID_GATES if validity is None else validity)
    if not injection_valid:
        validity["all_revoked_false_after_intervention"] = False
    payload = {
        "case_id": case_id,
        "suite": suite,
        "task_idx": task_idx,
        "bddl_name": "pick_up_the_alphabet_soup_and_place_it_in_the_basket",
        "instruction": "Pick the alphabet soup and place it in the basket",
        "target": target,
        "level": level,
        "param": None,
        "family": family,
        "semantics": "relation_holds_control" if level == "C0" else "relation_then_resume",
        "expected_relation_after": level == "C0",
        "status": "ok",
        "max_steps": 600,
        "steps": 600,
        "termination": "step_limit",
        "trigger_reached": trigger_reached,
        "trigger_step": 200 if trigger_reached else None,
        "injection_step": 200 if trigger_reached else None,
        "injection_wait_steps": 0 if trigger_reached else None,
        "trigger_skipped_reason": None if trigger_reached else "all_done not reached within max_steps",
        "relation_before": True if trigger_reached else False,
        "relation_after_injection": (True if level == "C0" else False) if trigger_reached else None,
        "relation_final": recovered if trigger_reached else None,
        "recovered": recovered if trigger_reached else None,
        "recovery": recovered if trigger_reached and level != "C0" else None,
        "restored_at_step": 330 if recovered else None,
        "notice_latency": 12 if trigger_reached else None,
        "repair_budget_steps": 400 if trigger_reached else None,
        "success": success,
        "final_goal_truth": [bool(recovered)],
        "final_revoked_truth": [bool(recovered)],
        "validity": validity,
        "injection": None
        if not trigger_reached
        else {
            "geometry": {
                "delta_translation_m": 0.12345,
                "delta_angle_rad": 0.5,
                "delta_joint_max": 0.0,
                "axis": [0.0, 0.0, 1.0],
            },
            "penetration_m": 0.00001,
            "no_penetration": True,
            "max_velocity": 0.0,
            "zero_velocity": True,
            "object_released": True,
            "restorable": True,
        },
        "video": {
            "path": f"videos/{case_id}.mp4",
            "fps": 20,
            "injection_time_s": 10.0 if trigger_reached else None,
            "injection_frame": 200 if trigger_reached else None,
        },
    }
    payload.update(extra)
    return payload


def _write_bundle(tmp_path: Path) -> Path:
    cases = [
        _case("b-goal-t000-c0", level="C0", target="c0", family="-", recovered=True, success=True),
        _case("b-goal-t000-g-l0", recovered=True),
        _case("b-goal-t001-g-l1", task_idx=1, level="L1", recovered=False),
        _case("b-object-t000-g-l0", suite="object", recovered=False),
        _case(
            "b-goal-t002-g-l2",
            task_idx=2,
            level="L2",
            injection_valid=False,
            recovered=False,
        ),
        _case(
            "b-goal-t003-g-l0",
            task_idx=3,
            trigger_reached=False,
            recovered=None,
            validity={"trigger_reached": False},
        ),
    ]
    bundle = tmp_path / "cases.jsonl"
    bundle.write_text("".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases), encoding="utf-8")
    notes = tmp_path / "NOTES.txt"
    notes.write_text("合成测试备注：仅用于测试，非实验结论。\n", encoding="utf-8")
    return bundle


def _run(tmp_path: Path, bundle: Path, *extra: str, per_page: int = 2) -> Path:
    out = tmp_path / "report"
    command = [
        sys.executable,
        str(SCRIPT),
        "--cases",
        str(bundle),
        "--out",
        str(out),
        "--title",
        "合成审核报告",
        "--model",
        "pi05",
        "--protocol",
        "max_steps=600; trigger=all_done+delay=10; init_row=0; seed=0",
        "--source-run",
        "libero-compose:/runs/synthetic",
        "--notes",
        str(bundle.parent / "NOTES.txt"),
        "--per-page",
        str(per_page),
        "--generated-at",
        "2026-11-18T12:00:00+08:00",
        *extra,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return out


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_cli_help() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0
    assert "--from-run" in result.stdout
    assert "--per-page" in result.stdout
    assert "--reconcile-json" in result.stdout


def test_generates_files_and_numbers(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path)
    out = _run(tmp_path, bundle)
    for name in (
        "index.html",
        "goal-part1.html",
        "goal-part2.html",
        "object-part1.html",
        "evidence.json",
        "cases.jsonl",
        "README.md",
        "provenance.json",
        "videos/README.md",
    ):
        assert (out / name).is_file(), f"missing {name}"
    evidence = json.loads(_read(out / "evidence.json"))
    assert evidence["case_count"] == 6
    injection = evidence["injection"]
    assert injection["attempted"] == 6
    assert injection["triggered"] == 5
    assert injection["injection_valid"] == 4
    assert injection["injection_invalid"] == 1
    assert injection["not_triggered"] == 1
    assert injection["gates"]["restorable"]["hard"] is False
    recovery = evidence["recovery"]
    assert recovery["denominator"] == 3  # valid non-C0: goal L0, goal L1, object L0
    assert recovery["numerator"] == 1
    assert recovery["value"] == pytest.approx(1 / 3)
    assert evidence["verdict_counts"]["valid_recovered"] == 1
    assert evidence["verdict_counts"]["valid_control"] == 1
    assert evidence["verdict_counts"]["injection_invalid"] == 1
    assert evidence["verdict_counts"]["trigger_not_reached"] == 1
    index = _read(out / "index.html")
    assert "1/3" in index
    assert "33.3%" in index
    assert "N/A" in index


def test_white_theme_and_self_contained(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path)
    out = _run(tmp_path, bundle)
    for html_path in [out / "index.html", out / "goal-part1.html", out / "object-part1.html"]:
        text = _read(html_path)
        assert 'lang="zh-CN"' in text
        assert "background:#ffffff" in text
        assert "--bg:#ffffff" in text
        assert "position:sticky" in text
        assert "http://" not in text
        assert "https://" not in text
        assert "<link" not in text
        assert "<script src" not in text
        assert "prefers-color-scheme:dark" not in text
        assert "#0d1117" not in text and "#0f172a" not in text


def test_anchor_navigation_and_pager(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path)
    out = _run(tmp_path, bundle)
    part1 = _read(out / "goal-part1.html")
    index = _read(out / "index.html")
    assert 'id="case-b-goal-t000-g-l0"' in part1
    assert 'id="task-0"' in part1
    assert 'href="index.html"' in part1
    assert 'href="goal-part2.html"' in part1
    assert 'id="filters"' in part1
    assert 'goal-part1.html#case-b-goal-t000-g-l0' in index
    assert 'href="goal-part2.html"' in index
    assert 'href="object-part1.html"' in index
    assert 'id="case-index-table"' in index
    # every case in the index must be linked to a concrete part-page anchor
    for case_id in (
        "b-goal-t000-c0",
        "b-goal-t000-g-l0",
        "b-goal-t001-g-l1",
        "b-object-t000-g-l0",
        "b-goal-t002-g-l2",
        "b-goal-t003-g-l0",
    ):
        assert f"#case-{case_id}" in index


def test_injection_and_recovery_evidence_rendered(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path)
    out = _run(tmp_path, bundle)
    card_page = _read(out / "goal-part1.html")
    for needle in (
        "注入前关系为真",
        "注入后关系为假",
        "无物体穿模",
        "零速度",
        "已释放",
        "restorable",
        "restore_probe",
        "relation_true_after_state_write",
        "penetration_m",
        "delta_translation_m",
        "delta_angle_rad",
        "relation_final",
        "recovered",
        "restored_at_step",
        "notice_latency",
        "repair_budget_steps",
        "termination",
        'data-review="injection"',
        'data-review="recovery"',
        'data-review="note"',
        "导出审核 JSON",
        "localStorage",
        "跳到注入",
        "跳到首次恢复",
        "跳到结束",
    ):
        assert needle in card_page, needle
    evidence = json.loads(_read(out / "evidence.json"))
    facts = [case for case in evidence["cases"] if case["case_id"] == "b-goal-t000-g-l0"][0]
    assert facts["injection_valid"] is True
    assert facts["verdict"] == "valid_recovered"
    assert facts["relation_final"] is True
    assert facts["restored_at_step"] == 330
    assert facts["video"]["path"] == "videos/b-goal-t000-g-l0.mp4"


def test_na_is_not_zero_percent(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path)
    out = _run(tmp_path, bundle)
    parts = "".join(_read(path) for path in sorted(out.glob("goal-part*.html")))
    marker = parts.find("b-goal-t003-g-l0")
    assert marker != -1
    card = parts[marker : marker + 8000]
    assert "N/A（未注入，不是 0%）" in card or "N/A" in card
    assert "触发未到达" in card
    evidence = json.loads(_read(out / "evidence.json"))
    na_case = [case for case in evidence["cases"] if case["case_id"] == "b-goal-t003-g-l0"][0]
    assert na_case["verdict"] == "trigger_not_reached"
    assert na_case["injection_valid"] is False
    assert evidence["injection"]["not_triggered"] == 1
    assert evidence["recovery"]["denominator"] == 3


def test_review_state_and_export_hooks(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path)
    out = _run(tmp_path, bundle)
    text = _read(out / "index.html")
    report_id = json.loads(_read(out / "evidence.json"))["meta"]["report_id"]
    assert report_id in text
    assert "libero-rollback-review:v1:" in text
    assert "URL.createObjectURL" in text
    assert 'download = "review-" + REPORT_ID' in text


def test_cases_bundle_preserves_values_and_has_no_host_paths(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path)
    out = _run(tmp_path, bundle)
    rows = [_read(out / "cases.jsonl").splitlines()]
    assert len(rows[0]) == 6
    cases = [json.loads(line) for line in rows[0]]
    recovered = [case for case in cases if case["case_id"] == "b-goal-t000-g-l0"][0]
    assert recovered["injection"]["geometry"]["delta_translation_m"] == 0.12345
    assert recovered["injection"]["penetration_m"] == 0.00001
    assert recovered["trigger_step"] == 200
    assert recovered["injection_valid"] is True
    assert recovered["verdict"] == "valid_recovered"
    for name in ("cases.jsonl", "evidence.json", "index.html", "README.md", "provenance.json"):
        assert HOST_PREFIX not in _read(out / name)


def test_provenance_hashes_artifacts(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path)
    out = _run(tmp_path, bundle)
    provenance = json.loads(_read(out / "provenance.json"))
    assert provenance["template_version"] == "review-report-v1.0"
    hashes = provenance["sha256"]
    for relative in ("index.html", "evidence.json", "cases.jsonl", "README.md", "goal-part1.html"):
        assert relative in hashes
        actual = hashlib.sha256((out / relative).read_bytes()).hexdigest()
        assert hashes[relative] == actual
    assert HOST_PREFIX not in json.dumps(provenance, ensure_ascii=False)


def test_migrated_source_records_source_and_migrated_sha(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path)
    out = tmp_path / "report"
    out.mkdir(parents=True)
    migrated = out / "SUMMARY.md"
    migrated.write_text("migrated summary with sanitized note\n", encoding="utf-8")
    source = tmp_path / "source-SUMMARY.md"
    source.write_text("source summary original\n", encoding="utf-8")
    out = _run(
        tmp_path,
        bundle,
        "--extra-file",
        str(migrated),
        "--old-report",
        "libero-compose:/runs/synthetic/old-report",
        "--migrated-source",
        f"SUMMARY.md={source}",
    )
    provenance = json.loads(_read(out / "provenance.json"))
    entry = provenance["migrated_sources"]["SUMMARY.md"]
    assert entry["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert entry["migrated_sha256"] == hashlib.sha256(migrated.read_bytes()).hexdigest()
    assert entry["source_sha256"] != entry["migrated_sha256"]
    assert "libero-compose:/runs/synthetic/old-report/SUMMARY.md" in entry["source_label"]
    assert HOST_PREFIX not in json.dumps(provenance, ensure_ascii=False)


def test_video_missing_and_available(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path)
    # Pre-create videos/ so one case has a local video and the rest are missing.
    video_dir = tmp_path / "report" / "videos"
    video_dir.mkdir(parents=True)
    (video_dir / "b-goal-t000-g-l0.mp4").write_bytes(b"fake mp4")
    out = _run(tmp_path, bundle)
    part1 = _read(out / "goal-part1.html")
    assert 'src="videos/b-goal-t000-g-l0.mp4"' in part1
    assert "视频缺失" in part1
    evidence = json.loads(_read(out / "evidence.json"))
    assert evidence["videos"]["available"] == 1
    facts = [case for case in evidence["cases"] if case["case_id"] == "b-goal-t000-g-l0"][0]
    assert facts["video"]["available"] is True


def test_reconciliation_against_old_aggregate(tmp_path: Path) -> None:
    bundle = _write_bundle(tmp_path)
    old_aggregate = {
        "cases": 6,
        "triggered": 5,
        "valid": 4,
        "perturbed_valid": 3,
        "recovered": 1,
        "recovery_rate": 1 / 3,
        "gates": {
            "completed_relation_true_before_intervention": 5,
            "all_revoked_false_after_intervention": 4,
            "no_object_penetration": 5,
            "zero_velocity_after_intervention": 5,
            "object_released_before_intervention": 5,
            "restorable": 5,
            "goal_preserved_after_pre": 0,
        },
        "by_suite": {
            "goal": {"cases": 4, "valid": 2, "recovered": 1, "controls": 1, "control_success": 1},
            "object": {"cases": 1, "valid": 1, "recovered": 0, "controls": 0, "control_success": 0},
        },
        "by_level": {
            "C0": {"cases": 1, "valid": 0, "recovered": 0, "controls": 1, "control_success": 1},
            "L0": {"cases": 2, "valid": 2, "recovered": 1},
            "L1": {"cases": 1, "valid": 1, "recovered": 0},
            "L2": {"cases": 1, "valid": 0, "recovered": 0},
        },
        "by_target": {
            "c0": {"cases": 1, "valid": 0, "recovered": 0, "controls": 1},
            "g": {"cases": 4, "valid": 3, "recovered": 1},
        },
        "failures": {
            "valid_but_not_recovered": 2,
            "trigger_not_reached: all_done not reached within max_steps": 1,
        },
        "notice_latency": {"n": 5, "mean": 12.0, "median": 12},
        "geometry": {
            "L0": {"n": 2, "mean": 0.12345, "max": 0.12345},
            "L1": {"n": 1, "mean": 0.12345, "max": 0.12345},
            "L2": {"n": 1, "mean": 0.12345, "max": 0.12345},
        },
    }
    old_path = tmp_path / "old-aggregate.json"
    old_path.write_text(json.dumps(old_aggregate), encoding="utf-8")
    run_summary = {
        "cases": 5,
        "triggered": 4,
        "valid": 3,
        "recoverable_valid": 2,
        "recovered": 1,
    }
    run_summary_path = tmp_path / "run-summary.json"
    run_summary_path.write_text(json.dumps(run_summary), encoding="utf-8")
    out = _run(
        tmp_path,
        bundle,
        "--old-report",
        "libero-compose:/runs/synthetic/old-report",
        "--reconcile-json",
        str(old_path),
        "--run-summary",
        str(run_summary_path),
    )
    evidence = json.loads(_read(out / "evidence.json"))
    reconciliation = evidence["reconciliation"]
    assert reconciliation is not None
    assert reconciliation["checks"]
    assert all(item["match"] for item in reconciliation["checks"]), reconciliation["differences"]
    assert reconciliation["run_summary"]["match"] is False
    assert reconciliation["run_summary"]["recomputed_cases"] == 6
    assert reconciliation["geometry_checks"]
    index = _read(out / "index.html")
    assert "数据来源与对账" in index
    assert "不一致（已解释）" in index


def test_from_run_builds_bundle_and_strips_host_paths(tmp_path: Path) -> None:
    run = tmp_path / "run"
    case_dir = run / "goal" / "b-goal-t000-g-l0"
    case_dir.mkdir(parents=True)
    summary = _case("b-goal-t000-g-l0", recovered=True)
    summary["video"] = {
        "path": HOST_VIDEO,
        "fps": 20,
        "injection_frame": 200,
        "injection_time_s": 10.0,
        "card_seconds": 1.0,
        "timing": "exact",
    }
    (case_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    other = run / "object" / "b-object-t000-c0"
    other.mkdir(parents=True)
    (other / "summary.json").write_text(
        json.dumps(_case("b-object-t000-c0", suite="object", level="C0", target="c0", recovered=True, success=True)),
        encoding="utf-8",
    )
    out = tmp_path / "report-from-run"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--from-run",
            str(run),
            "--out",
            str(out),
            "--title",
            "从源 run 生成",
            "--model",
            "pi05",
            "--source-run",
            "libero-compose:/runs/synthetic",
            "--generated-at",
            "2026-11-18T12:00:00+08:00",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(_read(out / "evidence.json"))
    assert evidence["case_count"] == 2
    for name in ("cases.jsonl", "evidence.json", "index.html", "provenance.json", "README.md"):
        assert HOST_PREFIX not in _read(out / name), name
    cases = [json.loads(line) for line in _read(out / "cases.jsonl").splitlines()]
    assert all(case["video"]["path"].startswith("videos/") for case in cases)


@pytest.mark.skipif(not (REAL_REPORT / "evidence.json").is_file(), reason="real report not generated")
def test_real_report_consistency() -> None:
    evidence = json.loads(_read(REAL_REPORT / "evidence.json"))
    cases = evidence["cases"]
    assert len(cases) == evidence["case_count"]
    assert evidence["case_count"] == 165
    injection_valid = sum(1 for case in cases if case["injection_valid"])
    assert injection_valid == evidence["injection"]["injection_valid"]
    recovery_den = [case for case in cases if case["injection_valid"] and case["level"] != "C0"]
    recovery_num = [case for case in recovery_den if case["recovered"] is True]
    assert len(recovery_den) == evidence["recovery"]["denominator"]
    assert len(recovery_num) == evidence["recovery"]["numerator"]
    assert evidence["recovery"]["denominator"] == 137
    assert evidence["recovery"]["numerator"] == 23
    assert evidence["injection"]["triggered"] == 157
    assert evidence["injection"]["injection_valid"] == 157
    assert evidence["injection"]["controls"]["success"] == 20
    # every case must be linked from the index and exist on a part page
    index = _read(REAL_REPORT / "index.html")
    parts = {}
    for page in REAL_REPORT.glob("*-part*.html"):
        parts[page.name] = _read(page)
    for case in cases:
        case_id = case["case_id"]
        anchor = f"#case-{case_id}"
        assert anchor in index, case_id
        found = any(f'id="case-{case_id}"' in text for text in parts.values())
        assert found, case_id
    for page in parts:
        assert page in index
    for name in ("index.html", "evidence.json", "cases.jsonl", "SUMMARY.md", "NOTES.txt", "provenance.json"):
        assert HOST_PREFIX not in _read(REAL_REPORT / name), name
    provenance = json.loads(_read(REAL_REPORT / "provenance.json"))
    assert provenance["case_count"] == 165
    assert provenance["source_run"] == "libero-compose:/runs/b-matrix/full-20261118"

def test_from_run_accepts_runner_seed_layout(tmp_path: Path) -> None:
    """The B runner writes ``<suite>/<case>/seed-0/summary.json``."""

    run = tmp_path / "run"
    case_dir = run / "l10" / "b-l10-t000-g-l0" / "seed-0"
    case_dir.mkdir(parents=True)
    summary = _case("b-l10-t000-g-l0", suite="l10", level="L0", target="g")
    (case_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    out = tmp_path / "report-seed-layout"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--from-run",
            str(run),
            "--out",
            str(out),
            "--title",
            "seed layout",
            "--model",
            "pi05",
            "--source-run",
            "local:/runs/seed-layout",
            "--generated-at",
            "2026-11-18T12:00:00+08:00",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(_read(out / "evidence.json"))
    assert evidence["case_count"] == 1
    assert evidence["cases"][0]["case_id"] == "b-l10-t000-g-l0"
