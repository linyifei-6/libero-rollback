"""Policy adapters for the frozen VLA models used by the benchmark.

The runner only depends on the two-method adapter contract from README §8.4::

    class PolicyAdapter(Protocol):
        def reset_episode(self, seed: int) -> None: ...
        def predict_chunk(self, obs: dict, instruction: str) -> np.ndarray: ...

For convenience every adapter also exposes the short aliases ``reset(seed)`` and
``predict(obs, instruction)``.  Model frameworks (torch / JAX / LeRobot) are
imported lazily inside each adapter's constructor, so importing this package
never pulls in a model framework.

One adapter runs in one model environment; the runner loads exactly one adapter
per run (``--policy none`` loads no model at all).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PolicyAdapter(Protocol):
    """Structural type the runner relies on (README §8.4)."""

    metadata: Mapping[str, Any]

    def reset_episode(self, seed: int) -> None: ...

    def predict_chunk(
        self, obs: Mapping[str, Any], instruction: str
    ) -> Any: ...


POLICY_NAMES: tuple[str, ...] = (
    "pi05",
    "smolvla",
    "xvla",
    "xiaomi",
    "vla_jepa_lerobot",
    "molmoact2",
    "groot_lerobot",
    "fastwam",
    "openvla_oft",
    "vlajepa",
    "lightwam",
    "cosmos",
    "dm05",
    "himem",
    "dit4dit",
    "none",
)


def normalize_policy_name(name: str | None) -> str:
    """Validate/``normalize`` a ``--policy`` value."""

    value = (name or "none").strip().lower()
    if value not in POLICY_NAMES:
        raise ValueError(
            f"unknown policy {name!r}; expected one of {', '.join(POLICY_NAMES)}"
        )
    return value


def load_policy(
    name: str,
    *,
    checkpoint: str | None = None,
    config_name: str = "pi05_libero",
    unnorm_key: str | None = None,
    suites: Sequence[str] | None = None,
    workspace: str | None = None,
) -> PolicyAdapter | None:
    """Instantiate one policy adapter (``None`` for ``--policy none``).

    Import errors from the model framework are left intact but annotated with
    the interpreter requirement, because each model lives in its own env
    (README §8.4).
    """

    value = normalize_policy_name(name)
    if value == "none":
        return None
    if value == "pi05":
        from .pi05 import Pi05Policy

        if not checkpoint:
            raise ValueError("--policy pi05 requires --checkpoint (or PI05_CHECKPOINT)")
        return Pi05Policy(checkpoint, config_name)
    if value == "vla_jepa_lerobot":
        from .vla_jepa_lerobot import VlaJepaPolicy

        return VlaJepaPolicy(checkpoint)

    if value == "molmoact2":
        from .molmoact2 import MolmoAct2Policy

        return MolmoAct2Policy(checkpoint)

    if value == "fastwam":
        from .fastwam import FastWamPolicy

        return FastWamPolicy(checkpoint)

    if value == "groot_lerobot":
        from .groot_lerobot import GrootLiberoPolicy

        return GrootLiberoPolicy(checkpoint)

    if value == "xiaomi":
        from .xiaomi import XiaomiPolicy

        return XiaomiPolicy(checkpoint)

    if value == "xvla":
        from .xvla import XvlaPolicy

        if not checkpoint:
            raise ValueError("--policy xvla requires --checkpoint (or XVLA_CHECKPOINT)")
        return XvlaPolicy(checkpoint)

    if value == "smolvla":
        from .smolvla import SmolVlaPolicy

        if not checkpoint:
            raise ValueError(
                "--policy smolvla requires --checkpoint (or SMOLVLA_CHECKPOINT)"
            )
        return SmolVlaPolicy(checkpoint)
    if value == "vlajepa":
        from .vlajepa import VlaJepaPolicy

        if not checkpoint:
            raise ValueError(
                "--policy vlajepa requires --checkpoint (or VLAJEPA_CHECKPOINT)"
            )
        return VlaJepaPolicy(checkpoint, workspace)

    if value == "lightwam":
        from .lightwam import LightWamPolicy

        if not checkpoint:
            raise ValueError(
                "--policy lightwam requires --checkpoint (or LIGHTWAM_CHECKPOINT)"
            )
        return LightWamPolicy(checkpoint, workspace)

    if value == "cosmos":
        from .cosmos import CosmosPolicy

        if not checkpoint:
            raise ValueError(
                "--policy cosmos requires --checkpoint (or COSMOS_CHECKPOINT)"
            )
        return CosmosPolicy(checkpoint, workspace)

    if value == "dm05":
        from .dm05_opendm import Dm05Policy

        if not checkpoint:
            raise ValueError("--policy dm05 requires --checkpoint (or DM05_CHECKPOINT)")
        return Dm05Policy(checkpoint)

    if value == "himem":
        from .himem_wam import HiMemWamPolicy

        if not checkpoint:
            raise ValueError(
                "--policy himem requires --checkpoint (or HIMEM_WAM_CHECKPOINT)"
            )
        return HiMemWamPolicy(checkpoint, workspace)

    if value == "dit4dit":
        from .dit4dit import Dit4ditPolicy

        if not checkpoint:
            raise ValueError(
                "--policy dit4dit requires --checkpoint (or DIT4DIT_CHECKPOINT)"
            )
        return Dit4ditPolicy(checkpoint, workspace)

    if value == "openvla_oft":
        from .openvla_oft import OpenVlaOftPolicy

        return OpenVlaOftPolicy(
            checkpoint=checkpoint,
            unnorm_key=unnorm_key,
            workspace=workspace,
            suites=suites,
        )
    raise AssertionError(f"unreachable policy name: {value}")  # pragma: no cover


def native_replan(name: str | None) -> int | None:
    """Return a model's native query cadence from ``configs/models.yaml``.

    LIBERO-MAX queries each policy at its own interval (π0.5 Q=5,
    OpenVLA-OFT Q=8, VLA-JEPA Q=7, X-VLA Q=30, LingBot Q=16, ...).  The runner
    resolves an unset ``--replan`` from this field so an already-decoded action
    chunk is never silently truncated.  Unknown models / missing fields return
    ``None`` and the caller falls back to the protocol default.
    """
    import yaml

    key = (name or "").strip().lower()
    if not key or key == "none":
        return None
    registry = Path(__file__).resolve().parents[3] / "configs" / "models.yaml"
    try:
        data = yaml.safe_load(registry.read_text(encoding="utf-8")) or {}
    except OSError:
        return None
    model = (data.get("models") or {}).get(key)
    if not isinstance(model, dict):
        return None
    value = model.get("replan_steps")
    return int(value) if isinstance(value, int) else None


__all__ = [
    "POLICY_NAMES",
    "PolicyAdapter",
    "load_policy",
    "native_replan",
    "normalize_policy_name",
]
