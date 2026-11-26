"""Policy registry contract: names, native cadence and configs/models.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from libero_rollback.policies import (
    POLICY_NAMES,
    load_policy,
    native_replan,
    normalize_policy_name,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS = REPO_ROOT / "configs" / "models.yaml"


def _registry() -> dict:
    return yaml.safe_load(MODELS.read_text(encoding="utf-8"))


def test_every_runner_policy_has_a_registry_entry() -> None:
    models = _registry()["models"]
    for name in POLICY_NAMES:
        if name == "none":
            continue
        assert name in models, f"{name} missing from configs/models.yaml"


def test_native_replan_matches_libero_max_cadence() -> None:
    assert native_replan("pi05") == 5
    assert native_replan("openvla_oft") == 8
    assert native_replan("vlajepa") == 7
    assert native_replan("none") is None
    assert native_replan("unknown-model") is None


def test_normalize_policy_name_accepts_vlajepa() -> None:
    assert normalize_policy_name("vlajepa") == "vlajepa"
    assert normalize_policy_name("VLAJEPA") == "vlajepa"
    with pytest.raises(ValueError):
        normalize_policy_name("not-a-policy")


def test_load_policy_requires_checkpoint_for_vlajepa() -> None:
    with pytest.raises(ValueError, match="VLAJEPA_CHECKPOINT"):
        load_policy("vlajepa", checkpoint=None)


def test_registry_native_cadence_is_positive() -> None:
    for name, entry in _registry()["models"].items():
        replan = entry.get("replan_steps")
        assert isinstance(replan, int) and replan > 0, f"{name}: bad replan_steps {replan!r}"
