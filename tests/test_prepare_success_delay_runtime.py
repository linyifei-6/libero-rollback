"""Tests for the success-delay overlay builder (text-level source patching)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_success_delay_runtime as overlay  # noqa: E402


def _runner_fixture() -> str:
    """Concatenate every anchor block so each replacement has one target."""

    return "\n".join(old for _name, old, _new in overlay.REPLACEMENTS)


def test_patch_runner_source_adds_success_window_contract() -> None:
    patched = overlay.patch_runner_source(_runner_fixture())
    for needle in (
        "--success-delay",
        "SuccessWindow",
        "[SUCCESS_WINDOW]",
        "success_stable",
        "success_window",
        "episode_step_limit",
    ):
        assert needle in patched


def test_patch_applies_to_the_frozen_overlay_when_available() -> None:
    runner = ROOT / "runs/validation-runtime-20261019-v19/tools/run_benchmark.py"
    if not runner.is_file():
        pytest.skip("frozen evaluator overlay is not present in this checkout")
    patched = overlay.patch_runner_source(runner.read_text(encoding="utf-8"))
    assert "--success-delay" in patched
    assert "episode_step_limit" in patched


def test_prepare_builds_overlay_and_merges_capabilities(tmp_path: Path) -> None:
    base = tmp_path / "base"
    (base / "tools").mkdir(parents=True)
    (base / "tools/run_benchmark.py").write_text(_runner_fixture(), encoding="utf-8")
    (base / "rollback-capabilities.json").write_text(
        json.dumps({"protocol_version": 1, "capabilities": ["completed_pose"]}),
        encoding="utf-8",
    )
    output = tmp_path / "overlay"
    overlay.prepare(base, output)

    assert (output / "success_window.py").is_file()
    assert (output / "success-delay-provenance.json").is_file()
    capabilities = json.loads((output / "rollback-capabilities.json").read_text())[
        "capabilities"
    ]
    assert capabilities == ["completed_pose", "success_window"]
    runner = (output / "tools/run_benchmark.py").read_text(encoding="utf-8")
    assert "--success-delay" in runner
    provenance = json.loads((output / "success-delay-provenance.json").read_text())
    assert provenance["capability"] == "success_window"
    assert provenance["patch_count"] == len(overlay.REPLACEMENTS)

    with pytest.raises(ValueError, match="overwrite"):
        overlay.prepare(base, output)


def test_missing_anchor_fails_with_context() -> None:
    _name, old, _new = overlay.REPLACEMENTS[0]
    text = _runner_fixture().replace(old, "", 1)
    with pytest.raises(ValueError, match="runtime source changed"):
        overlay.patch_runner_source(text)
