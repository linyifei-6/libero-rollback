"""Tests for the static report builder (no simulation required)."""

from __future__ import annotations

import json
from pathlib import Path

from libero_rollback.report import (
    SCHEMA,
    build_aggregate,
    load_episodes,
    render_html,
    render_markdown,
    write_report,
)


def _episode(
    case_id: str,
    *,
    verdict: str,
    suite: str = "goal",
    level: str = "L0",
    param: str | None = None,
    **extra,
) -> dict:
    payload = {
        "status": "ok",
        "case_id": case_id,
        "suite": suite,
        "level": level,
        "param": param,
        "target": "g",
        "trigger_reached": True,
        "case_valid": verdict
        not in {"injection_invalid", "trigger_not_reached", "truth_unverified"},
        "verdict": verdict,
        "recovered": verdict == "valid_recovered",
        "relation_final": verdict == "valid_recovered",
        "steps": 600,
        "video": {"path": f"{suite}/{case_id}/video.mp4", "fps": 20},
    }
    payload.update(extra)
    return payload


def _write_run(tmp_path: Path) -> Path:
    run = tmp_path / "run"
    run.mkdir()
    episodes = [
        _episode("b-goal-t000-c0", verdict="valid_control", level="C0", target="c0"),
        _episode("b-goal-t000-g-l0", verdict="valid_recovered"),
        _episode("b-goal-t001-g-l0", verdict="valid_not_recovered"),
        _episode("b-goal-t002-g-l0", verdict="injection_invalid"),
        _episode("b-object-t000-g-l1", verdict="valid_not_recovered", suite="object"),
    ]
    (run / "episodes.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in episodes), encoding="utf-8"
    )
    (run / "run-manifest.json").write_text(
        json.dumps({"defaults": {"policy": "pi05", "max_steps": 600, "seed": 0}}),
        encoding="utf-8",
    )
    (run / "matrix.json").write_text(json.dumps({"cases": 5}), encoding="utf-8")
    return run


def test_load_episodes_skips_broken_lines(tmp_path: Path) -> None:
    run = _write_run(tmp_path)
    with (run / "episodes.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("{not json}\n")
    assert len(load_episodes(run)) == 5


def test_aggregate_denominators(tmp_path: Path) -> None:
    run = _write_run(tmp_path)
    aggregate = build_aggregate(run)
    assert aggregate["schema_version"] == SCHEMA
    assert aggregate["episodes"] == 5
    # Recovery excludes C0 and invalid injections: 3 in the denominator, 1 recovered.
    assert aggregate["recovery"]["numerator"] == 1
    assert aggregate["recovery"]["denominator"] == 3
    assert aggregate["recovery"]["value"] == 1 / 3
    assert aggregate["control"]["numerator"] == 1
    assert aggregate["control"]["denominator"] == 1
    assert aggregate["by_suite"]["goal"]["cases"] == 4
    assert len(aggregate["cases"]) == 5


def test_aggregate_reports_na_when_no_denominator(tmp_path: Path) -> None:
    run = tmp_path / "empty"
    run.mkdir()
    (run / "episodes.jsonl").write_text(
        json.dumps(_episode("b-goal-t000-c0", verdict="valid_control", level="C0")) + "\n",
        encoding="utf-8",
    )
    aggregate = build_aggregate(run)
    assert aggregate["recovery"]["na"] is True
    assert "N/A" in render_html(aggregate) or "n/a" in render_html(aggregate)


def test_report_writes_self_contained_html(tmp_path: Path) -> None:
    run = _write_run(tmp_path)
    out = tmp_path / "report"
    aggregate = write_report(run, out)
    assert (out / "aggregate.json").is_file()
    assert (out / "SUMMARY.md").is_file()
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "LIBERO-Rollback run report" in html
    assert "b-goal-t000-g-l0" in html
    assert "http://" not in html and "https://" not in html
    assert json.loads((out / "aggregate.json").read_text())["episodes"] == 5
    assert aggregate["cases"][1]["video"].endswith("video.mp4")


def test_render_markdown_lists_metrics(tmp_path: Path) -> None:
    run = _write_run(tmp_path)
    markdown = render_markdown(build_aggregate(run))
    assert "| Recovery |" in markdown
    assert "b-object-t000-g-l1" in markdown
