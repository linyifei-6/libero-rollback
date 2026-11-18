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
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PolicyAdapter(Protocol):
    """Structural type the runner relies on (README §8.4)."""

    metadata: Mapping[str, Any]

    def reset_episode(self, seed: int) -> None: ...

    def predict_chunk(
        self, obs: Mapping[str, Any], instruction: str
    ) -> Any: ...


POLICY_NAMES: tuple[str, ...] = ("pi05", "smolvla", "openvla_oft", "none")


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
    if value == "smolvla":
        from .smolvla import SmolVlaPolicy

        if not checkpoint:
            raise ValueError(
                "--policy smolvla requires --checkpoint (or SMOLVLA_CHECKPOINT)"
            )
        return SmolVlaPolicy(checkpoint)
    if value == "openvla_oft":
        from .openvla_oft import OpenVlaOftPolicy

        return OpenVlaOftPolicy(
            checkpoint=checkpoint,
            unnorm_key=unnorm_key,
            workspace=workspace,
            suites=suites,
        )
    raise AssertionError(f"unreachable policy name: {value}")  # pragma: no cover


__all__ = [
    "POLICY_NAMES",
    "PolicyAdapter",
    "load_policy",
    "normalize_policy_name",
]
