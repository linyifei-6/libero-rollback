"""LeRobot SmolVLA policy adapter (0.45 B lightweight baseline).

The adapter loads a LIBERO-finetuned SmolVLA checkpoint directly through
LeRobot — no ``libero_runtime`` / sibling-repository import.  The observation
preprocessing (180° image rotation, proprio state, action crop to 7 dims)
matches the evaluation stack that produced the reference SmolVLA numbers.

Run it inside an env with ``torch`` + ``lerobot`` (README §8.4); the imports are
lazy so the runner can be imported without them.
"""

from __future__ import annotations

import math
import os
import time
from collections.abc import Mapping
from typing import Any

import numpy as np


def _quat2axisangle(quat: np.ndarray) -> np.ndarray:
    qw = float(np.clip(quat[3], -1.0, 1.0))
    denominator = math.sqrt(max(1.0 - qw * qw, 0.0))
    if denominator < 1e-9:
        return np.zeros(3, dtype=np.float32)
    return (
        np.asarray(quat[:3], dtype=np.float32)
        * (2.0 * math.acos(qw) / denominator)
    ).astype(np.float32)


class SmolVlaPolicy:
    """Expose SmolVLA through the runner's reset/predict protocol."""

    def __init__(
        self, checkpoint: str | os.PathLike[str], logger: Any | None = None
    ) -> None:
        import torch
        from lerobot.policies.factory import make_pre_post_processors
        from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

        self._torch = torch
        self._logger = logger
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.checkpoint = str(checkpoint)
        started = time.time()
        self.policy = (
            SmolVLAPolicy.from_pretrained(self.checkpoint).to(self._device).eval()
        )
        self.preprocess, self.postprocess = make_pre_post_processors(
            self.policy.config,
            self.checkpoint,
            preprocessor_overrides={"device_processor": {"device": str(self._device)}},
        )
        self.metadata = {
            "policy": "smolvla",
            "checkpoint": self.checkpoint,
            "device": str(self._device),
            "torch": torch.__version__,
            "chunk_size": int(getattr(self.policy.config, "chunk_size", 50)),
            "load_seconds": round(time.time() - started, 2),
        }

    def reset(self, seed: int) -> None:
        torch = self._torch
        self.policy.reset()
        torch.manual_seed(int(seed))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(seed))

    def _observation(self, obs: Mapping[str, Any]) -> dict[str, np.ndarray]:
        agentview = np.ascontiguousarray(np.asarray(obs["agentview_image"])[::-1, ::-1])
        wrist = np.ascontiguousarray(
            np.asarray(obs["robot0_eye_in_hand_image"])[::-1, ::-1]
        )
        state = np.concatenate(
            [
                np.asarray(obs["robot0_eef_pos"], dtype=np.float64),
                _quat2axisangle(np.asarray(obs["robot0_eef_quat"], dtype=np.float64)),
                np.asarray(obs["robot0_gripper_qpos"], dtype=np.float64),
            ]
        ).astype(np.float32)
        return {
            "observation.images.image": agentview,
            "observation.images.image2": wrist,
            "observation.state": state,
        }

    def predict(self, observation: Mapping[str, Any], instruction: str) -> np.ndarray:
        import torch
        from lerobot.policies.utils import prepare_observation_for_inference

        batch = prepare_observation_for_inference(
            self._observation(observation), self._device, task=str(instruction)
        )
        batch = self.preprocess(batch)
        with torch.inference_mode():
            action = self.policy.predict_action_chunk(batch)
            action = self.postprocess(action)
        array = action.detach().float().cpu().numpy()
        chunk = array[0] if array.ndim == 3 else array
        chunk = np.asarray(chunk, dtype=np.float64)
        if chunk.ndim != 2 or chunk.shape[1] < 7:
            raise ValueError(f"unexpected SmolVLA action chunk shape: {chunk.shape}")
        return chunk[:, :7]

    # -- README §8.4 adapter contract ------------------------------------

    def reset_episode(self, seed: int) -> None:
        self.reset(seed)

    def predict_chunk(
        self, obs: Mapping[str, Any], instruction: str
    ) -> np.ndarray:
        return self.predict(obs, instruction)
