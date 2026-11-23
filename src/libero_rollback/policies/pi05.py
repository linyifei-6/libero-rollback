"""OpenPI pi0.5 policy adapter (``pi05_libero`` checkpoint).

Only the inference surface the runner needs is implemented: load a
``pi05_libero`` checkpoint with OpenPI, reset the sampling seed per episode and
turn a LIBERO observation dict into an action chunk.  The observation
preprocessing mirrors the evaluation stack that produced the reference numbers
(180° image rotation, proprio state, action crop to 7 dims).

The adapter is self-contained: it imports ``torch`` / ``openpi`` lazily and
never imports a sibling repository.  Run it inside the openpi environment
(README §8.4).
"""

from __future__ import annotations

import math
import os
import time
from collections.abc import Mapping
from typing import Any

# Set before openpi/JAX is imported in Pi05Policy.__init__.
os.environ.setdefault("XLA_PYTHON_CLIENT_MEM_FRACTION", "0.42")

import numpy as np


def quat2axisangle(quat: np.ndarray) -> np.ndarray:
    """Convert a quaternion ``(x, y, z, w)`` to an axis-angle vector."""

    qw = float(quat[3])
    qw = max(-1.0, min(1.0, qw))
    denominator = math.sqrt(max(0.0, 1.0 - qw * qw))
    if math.isclose(denominator, 0.0, abs_tol=1e-9):
        return np.zeros(3, dtype=np.float64)
    return np.asarray(quat[:3], dtype=np.float64) * 2.0 * math.acos(qw) / denominator


class Pi05Policy:
    """Thin wrapper around ``openpi.policies.policy_config.create_trained_policy``."""

    def __init__(
        self, checkpoint: str | os.PathLike[str], config_name: str = "pi05_libero"
    ) -> None:
        import torch
        from openpi.policies import policy_config
        from openpi.training import config as train_config

        self._torch = torch
        self.checkpoint = str(checkpoint)
        self.config_name = config_name
        started = time.time()
        self.train_config = train_config.get_config(config_name)
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.policy = policy_config.create_trained_policy(
            self.train_config,
            self.checkpoint,
            pytorch_device=device,
        )
        self.metadata = {
            "policy": "pi05",
            "config_name": config_name,
            "checkpoint": self.checkpoint,
            "torch": torch.__version__,
            "device": device,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "load_seconds": round(time.time() - started, 2),
        }

    def reset(self, seed: int) -> None:
        """Reseed sampling; the runner calls this once per episode."""

        torch = self._torch
        torch.manual_seed(int(seed))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(seed))

    def predict(self, observation: Mapping[str, Any], instruction: str) -> np.ndarray:
        """Return one action chunk of shape ``(T, 7)``."""

        agentview = np.ascontiguousarray(np.asarray(observation["agentview_image"])[::-1, ::-1])
        wrist = observation.get("robot0_eye_in_hand_image")
        wrist_image = (
            np.ascontiguousarray(np.asarray(wrist)[::-1, ::-1])
            if wrist is not None
            else np.zeros_like(agentview)
        )
        state = np.concatenate(
            [
                np.asarray(observation["robot0_eef_pos"], dtype=np.float64),
                quat2axisangle(
                    np.asarray(observation["robot0_eef_quat"], dtype=np.float64)
                ),
                np.asarray(observation["robot0_gripper_qpos"], dtype=np.float64),
            ]
        )
        inputs = {
            "observation/image": agentview,
            "observation/wrist_image": wrist_image,
            "observation/state": state.astype(np.float32),
            "prompt": instruction,
        }
        result = self.policy.infer(inputs)
        actions = np.asarray(result["actions"], dtype=np.float64)
        if actions.ndim != 2 or actions.shape[1] < 7:
            raise ValueError(f"unexpected action chunk shape: {actions.shape}")
        return actions[:, :7]

    # -- README §8.4 adapter contract ------------------------------------

    def reset_episode(self, seed: int) -> None:
        self.reset(seed)

    def predict_chunk(
        self, obs: Mapping[str, Any], instruction: str
    ) -> np.ndarray:
        return self.predict(obs, instruction)
