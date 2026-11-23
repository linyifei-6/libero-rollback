"""Tests for the B-plus episode aggregator (``scripts/build_b_plus_summary.py``).

Pure-static: synthetic ``episodes.jsonl`` fixtures, no simulation and no model.
The tests pin the three definitional choices the report depends on:

* ``Recovery`` only counts valid ``O2`` injections (controls and untriggered
  cases never enter the denominator);
* ``C0`` no-op success is reported separately;
* the paired comparison compares identical case ids and ignores a pair when
  either side's injection was invalid.
"""

# ruff: noqa: E501

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_b_plus_summary.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_b_plus_summary", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _episode(case_id, *, level, valid=True, recovered=None, triggered=True, suite="object", param=None):
    return {
        "schema_version": 2,
        "status": "ok",
        "case_id": case_id,
        "suite": suite,
        "bddl_name": f"task_{suite}",
        "level": level,
        "param": param,
        "trigger_reached": triggered,
        "case_valid": valid and triggered,
        "recovered": recovered,
        "success": recovered if level == "C0" else False,
        "steps": 400,
        "elapsed_s": 100.0,
        "notice_latency": 20 if level == "O2" else None,
        "validity": {},
    }


def _write_run(tmp_path: Path, name: str, rows: list[dict]) -> Path:
    run = tmp_path / name
    run.mkdir()
    (run / "episodes.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    return run


def _summary_rows():
    module = _load_module()
    rows = [
        _episode("bp-object-t000-o2l1s1", level="O2", valid=True, recovered=True, param="l1s1"),
        _episode("bp-object-t000-o2l1s2", level="O2", valid=True, recovered=False, param="l1s2"),
        _episode("bp-object-t032-o2l2s1", level="O2", valid=False, recovered=None, param="l2s1"),
        _episode("bp-object-t032-o2l2s2", level="O2", valid=True, recovered=False, param="l2s2"),
        _episode("bp-object-t000-c0", level="C0", valid=True, recovered=True),
        _episode("bp-object-t032-c0", level="C0", valid=True, recovered=False),
        _episode("bp-object-t000-l0", level="L0", valid=True, recovered=True),
        _episode("bp-object-t000-o2l9s9", level="O2", valid=True, recovered=None, triggered=False, param="l3s1"),
    ]
    return module, rows


def test_recovery_excludes_controls_invalid_and_untriggered(tmp_path):
    module, rows = _summary_rows()
    run = _write_run(tmp_path, "run", rows)

    summary = module.summarize(module.load_runs([run]))
    overall = summary["overall"]

    # valid O2 = 3 (o2l1s1, o2l1s2, o2l2s2); invalid + untriggered are dropped
    assert overall["recovery_o2"]["n"] == 3
    assert overall["recovery_o2"]["k"] == 1
    # controls are reported on their own denominator
    assert overall["c0"]["n"] == 2
    assert overall["c0"]["k"] == 1
    assert overall["l0"]["n"] == 1
    assert overall["validity"]["o2"]["n"] == 5
    assert overall["validity"]["o2"]["k"] == 3
    assert summary["by_level"]["L1"]["valid"] == 2
    assert summary["by_level"]["L2"]["valid"] == 1


def test_later_record_wins_when_a_case_is_repaired(tmp_path):
    module = _load_module()
    first = _write_run(
        tmp_path,
        "run",
        [_episode("bp-object-t000-o2l1s1", level="O2", valid=False, recovered=None, param="l1s1")],
    )
    # append a repaired record for the same case
    with (first / "episodes.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                _episode("bp-object-t000-o2l1s1", level="O2", valid=True, recovered=True, param="l1s1")
            )
            + "\n"
        )

    summary = module.summarize(module.load_runs([first]))
    assert summary["overall"]["recovery_o2"]["n"] == 1
    assert summary["overall"]["recovery_o2"]["k"] == 1


def test_paired_comparison_ignores_invalid_pairs(tmp_path):
    module = _load_module()
    base = [
        _episode("bp-object-t000-o2l1s1", level="O2", valid=True, recovered=True, param="l1s1"),
        _episode("bp-object-t000-o2l1s2", level="O2", valid=True, recovered=False, param="l1s2"),
        _episode("bp-object-t000-o2l1s3", level="O2", valid=True, recovered=False, param="l1s3"),
        _episode("bp-object-t000-o2l1s4", level="O2", valid=False, recovered=None, param="l1s4"),
    ]
    other = [
        _episode("bp-object-t000-o2l1s1", level="O2", valid=True, recovered=False, param="l1s1"),
        _episode("bp-object-t000-o2l1s2", level="O2", valid=True, recovered=True, param="l1s2"),
        _episode("bp-object-t000-o2l1s3", level="O2", valid=True, recovered=False, param="l1s3"),
        _episode("bp-object-t000-o2l1s4", level="O2", valid=False, recovered=None, param="l1s4"),
    ]
    run_a = _write_run(tmp_path, "a", base)
    run_b = _write_run(tmp_path, "b", other)

    result = module.paired(module.load_runs([run_a]), module.load_runs([run_b]))
    assert result["shared_cases"] == 4
    assert result["o2_both_valid"] == 3
    assert result["only_a"] == 1
    assert result["only_b"] == 1
    assert result["neither"] == 1
    assert result["dropped_not_valid_in_both"] == 1
    # one discordant pair in each direction -> p = 1.0
    assert result["mcnemar_p"] == 1.0


def test_cli_writes_json(tmp_path, capsys):
    module = _load_module()
    _, rows = _summary_rows()
    run = _write_run(tmp_path, "run", rows)
    out = tmp_path / "summary.json"

    assert module.main([str(run), "--json", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["summary"]["overall"]["recovery_o2"]["k"] == 1
    assert "## B-plus summary" in capsys.readouterr().out
