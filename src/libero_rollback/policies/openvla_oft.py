"""OpenVLA-OFT policy adapter.

Wraps the official deterministic ``OFTPolicy`` (the same class used by the
LIBERO evaluation scripts) so it can drive the rollback runner through the
common surface::

    reset(seed)                    -> None
    predict(obs, instruction)      -> np.ndarray (T, 7)

The wrapped policy performs its own observation preprocessing (180° rotation,
resize + centre crop, proprio normalisation), so the adapter must receive the
raw LIBERO observation dict produced by ``OffScreenRenderEnv``.

The LIBERO-OFT workspace is supplied at runtime through ``--workspace`` /
``OPENVLA_OFT_WORKSPACE`` (the directory that contains ``LIBERO-plus/``); the
checkpoint through ``--checkpoint`` / ``OPENVLA_OFT_CHECKPOINT``.  Nothing is
hard-coded to a host path.  One ``unnorm_key`` is needed per suite; it is
derived from the matrix ``suite`` column when the run selects a single suite.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

WORKSPACE_ENV = "OPENVLA_OFT_WORKSPACE"
CHECKPOINT_ENV = "OPENVLA_OFT_CHECKPOINT"

#: B matrix suite -> unnorm key exposed by the 4-suite OFT checkpoint.
SUITE_UNNORM_KEYS: Mapping[str, str] = {
    "goal": "libero_goal_no_noops",
    "object": "libero_object_no_noops",
    "spatial": "libero_spatial_no_noops",
    "l10": "libero_10_no_noops",
}


def _resolve_workspace(workspace: str | None) -> Path:
    value = workspace or os.environ.get(WORKSPACE_ENV)
    if not value:
        raise RuntimeError(
            "OpenVLA-OFT workspace not configured: pass --workspace or set "
            f"{WORKSPACE_ENV} to the directory that contains LIBERO-plus/"
        )
    path = Path(value).expanduser()
    if not path.is_dir():
        raise FileNotFoundError(f"OpenVLA-OFT workspace not found: {path}")
    return path


def _load_oft_class(workspace: Path):
    module_path = (
        workspace / "LIBERO-plus" / "evaluation_scripts" / "eval_openvla_oft_libero_plus.py"
    )
    if not module_path.exists():
        raise FileNotFoundError(f"OpenVLA-OFT evaluation module not found: {module_path}")
    package_root = str(workspace / "LIBERO-plus")
    if package_root not in sys.path:
        sys.path.insert(0, package_root)

    # The official eval module imports ``libero.libero.benchmark``, whose package
    # eagerly enumerates every BDDL at import time.  The rollback runner builds
    # environments straight from a BDDL path and never needs that registry, so
    # stub it out to keep the import side-effect free.
    if "libero.libero.benchmark" not in sys.modules:
        import types

        try:
            import libero.libero  # noqa: F401  (ensure the parent package exists)
        except Exception:  # noqa: BLE001 - the stub is best effort
            pass
        stub = types.ModuleType("libero.libero.benchmark")

        def get_benchmark(*_args, **_kwargs):
            raise RuntimeError(
                "libero benchmark registry is stubbed out by the rollback runner"
            )

        stub.get_benchmark = get_benchmark  # type: ignore[attr-defined]
        sys.modules["libero.libero.benchmark"] = stub

    spec = importlib.util.spec_from_file_location("openvla_oft_libero_eval", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load OpenVLA-OFT module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.OFTPolicy


def _resolve_unnorm_key(
    unnorm_key: str | None, suites: Sequence[str] | None
) -> str:
    if unnorm_key:
        return str(unnorm_key)
    selected = {str(suite) for suite in (suites or ())}
    if len(selected) == 1:
        suite = next(iter(selected))
        if suite in SUITE_UNNORM_KEYS:
            return SUITE_UNNORM_KEYS[suite]
    raise ValueError(
        "OpenVLA-OFT requires a single unnorm key: pass --unnorm-key, or select "
        "cases from exactly one suite (one of "
        f"{sorted(SUITE_UNNORM_KEYS)})"
    )


class OpenVlaOftPolicy:
    """Thin wrapper around the official deterministic OFT action chunk."""

    def __init__(
        self,
        checkpoint: str | None = None,
        unnorm_key: str | None = None,
        *,
        workspace: str | None = None,
        suites: Sequence[str] | None = None,
        logger: Any | None = None,
    ) -> None:
        import torch

        self._torch = torch
        workspace_path = _resolve_workspace(workspace)
        configured = checkpoint or os.environ.get(CHECKPOINT_ENV)
        if not configured:
            raise RuntimeError(
                "OpenVLA-OFT checkpoint not configured: pass --checkpoint or set "
                f"{CHECKPOINT_ENV}"
            )
        self.checkpoint = str(Path(configured).expanduser())
        self.unnorm_key = _resolve_unnorm_key(unnorm_key, suites)
        self.workspace = str(workspace_path)
        started = time.time()
        policy_class = _load_oft_class(workspace_path)
        self._policy = policy_class(
            checkpoint_path=self.checkpoint,
            unnorm_key=self.unnorm_key,
            use_proprio=True,
            use_l1_regression=True,
            logger=logger,
        )
        self.metadata = {
            "policy": "openvla_oft",
            "checkpoint": self.checkpoint,
            "workspace": self.workspace,
            "unnorm_key": self.unnorm_key,
            "torch": torch.__version__,
            "device": "cuda:0" if torch.cuda.is_available() else "cpu",
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "load_seconds": round(time.time() - started, 2),
        }

    def reset(self, seed: int) -> None:
        torch = self._torch
        np.random.seed(int(seed))
        torch.manual_seed(int(seed))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(seed))

    def predict(self, observation: Mapping[str, Any], instruction: str) -> np.ndarray:
        chunk = np.asarray(
            self._policy.predict_chunk(dict(observation), instruction), dtype=np.float64
        )
        if chunk.ndim != 2 or chunk.shape[1] < 7:
            raise ValueError(f"unexpected OpenVLA-OFT action chunk shape: {chunk.shape}")
        return chunk[:, :7]

    # -- README §8.4 adapter contract ------------------------------------

    def reset_episode(self, seed: int) -> None:
        self.reset(seed)

    def predict_chunk(
        self, obs: Mapping[str, Any], instruction: str
    ) -> np.ndarray:
        return self.predict(obs, instruction)
