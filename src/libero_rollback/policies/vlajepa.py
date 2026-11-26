"""VLA-JEPA policy adapter (LIBERO checkpoint, StarVLA inference stack).

Ported from the reference implementation in LIBERO-MAX
(``scripts/run_vlajepa_persistent_shard.py``): the observation preprocessing,
``franka`` action unnormalisation and gripper binarisation are kept byte-for-byte
compatible so numbers stay comparable with LIBERO-MAX.

The model stack (``starVLA`` + ``deployment``) is imported lazily from a
VLA-JEPA checkout because it is installed in its own environment
(README §8.4).  Query cadence is the checkpoint's native chunk
(``future_action_window_size + 1``, 7 for the released LIBERO checkpoint);
the runner reads that from ``configs/models.yaml``.
"""

from __future__ import annotations

import math
import os
import sys
import time
from collections.abc import Mapping
from typing import Any

import numpy as np


def _quat2axisangle(quat: np.ndarray) -> np.ndarray:
    quat = np.asarray(quat, dtype=np.float32).copy()
    quat[3] = np.clip(quat[3], -1.0, 1.0)
    denominator = math.sqrt(max(1.0 - quat[3] * quat[3], 0.0))
    if math.isclose(float(denominator), 0.0):
        return np.zeros(3, dtype=np.float32)
    return quat[:3] * 2.0 * math.acos(float(quat[3])) / denominator


def _unnormalize_actions(
    normalized_actions: np.ndarray, action_stats: Mapping[str, Any]
) -> np.ndarray:
    normalized = np.asarray(normalized_actions, dtype=np.float32).copy()
    mask = np.asarray(
        action_stats.get("mask", np.ones_like(action_stats["min"], dtype=bool)),
        dtype=bool,
    )
    action_high = np.asarray(action_stats["max"], dtype=np.float32)
    action_low = np.asarray(action_stats["min"], dtype=np.float32)
    normalized = np.clip(normalized, -1.0, 1.0)
    normalized[:, 6] = np.where(normalized[:, 6] < 0.5, 0.0, 1.0)
    return np.where(
        mask,
        0.5 * (normalized + 1.0) * (action_high - action_low) + action_low,
        normalized,
    )


def _to_libero_actions(raw_actions: np.ndarray) -> np.ndarray:
    raw = np.asarray(raw_actions, dtype=np.float32)
    if raw.ndim != 2 or raw.shape[1] < 7:
        raise ValueError(f"VLA-JEPA returned invalid raw actions: {raw.shape}")
    actions = raw[:, :7].copy()
    actions[:, 6] = 1.0 - 2.0 * (actions[:, 6] > 0.5)
    return actions.astype(np.float64)


class VlaJepaPolicy:
    """Expose a VLA-JEPA LIBERO checkpoint through the runner protocol."""

    def __init__(
        self,
        checkpoint: str | os.PathLike[str],
        root: str | os.PathLike[str] | None = None,
        logger: Any | None = None,
    ) -> None:
        import cv2  # noqa: PLC0415
        import torch  # noqa: PLC0415

        root_path = root or os.environ.get("VLAJEPA_ROOT")
        if not root_path:
            raise ValueError("VLA-JEPA requires --workspace (or VLAJEPA_ROOT)")
        if str(root_path) not in sys.path:
            sys.path.insert(0, str(root_path))

        from deployment.model_server.tools.image_tools import (  # noqa: PLC0415
            to_pil_preserve,
        )
        from starVLA.model.framework.base_framework import baseframework  # noqa: PLC0415
        from starVLA.model.tools import read_mode_config  # noqa: PLC0415

        self._cv = cv2
        self._torch = torch
        self._to_pil = to_pil_preserve
        self.checkpoint = str(checkpoint)
        started = time.time()
        model_config, norm_stats = read_mode_config(self.checkpoint)
        self.native_chunk = (
            int(model_config["framework"]["action_model"]["future_action_window_size"]) + 1
        )
        if "franka" not in norm_stats:
            raise KeyError("checkpoint is missing the official 'franka' norm key")
        self.action_stats = norm_stats["franka"]["action"]
        model = baseframework.from_pretrained(self.checkpoint)
        self.model = model.to(torch.bfloat16).to(torch.device("cuda:0")).eval()
        self.metadata = {
            "policy": "vlajepa",
            "checkpoint": self.checkpoint,
            "workspace": str(root_path),
            "native_chunk": self.native_chunk,
            "torch": torch.__version__,
            "load_seconds": round(time.time() - started, 2),
        }

    def reset_episode(self, seed: int) -> None:
        torch = self._torch
        import random  # noqa: PLC0415

        random.seed(int(seed))
        np.random.seed(int(seed))
        torch.manual_seed(int(seed))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(seed))
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    def predict_chunk(
        self, observation: Mapping[str, Any], instruction: str
    ) -> np.ndarray:
        cv = self._cv
        primary = np.ascontiguousarray(np.asarray(observation["agentview_image"])[::-1, ::-1])
        wrist = np.ascontiguousarray(
            np.asarray(observation["robot0_eye_in_hand_image"])[::-1, ::-1]
        )
        images = [
            cv.resize(image, (224, 224), interpolation=cv.INTER_AREA)
            for image in (primary, wrist)
        ]
        state = np.concatenate(
            (
                np.asarray(observation["robot0_eef_pos"], dtype=np.float32),
                _quat2axisangle(np.asarray(observation["robot0_eef_quat"])),
                np.asarray(observation["robot0_gripper_qpos"], dtype=np.float32),
            )
        )
        payload = {
            "batch_images": self._to_pil([images]),
            "instructions": [instruction],
            "unnorm_key": "franka",
            "do_sample": False,
            "use_ddim": True,
            "num_ddim_steps": 10,
            "state": [np.expand_dims(state, axis=0)],
        }
        with self._torch.no_grad():
            response = self.model.predict_action(**payload)
        normalized = np.asarray(response["normalized_actions"])[0]
        return _to_libero_actions(_unnormalize_actions(normalized, self.action_stats))

    # -- README §8.4 adapter contract ------------------------------------

    def reset(self, seed: int) -> None:
        self.reset_episode(seed)

    def predict(self, obs: Mapping[str, Any], instruction: str) -> np.ndarray:
        return self.predict_chunk(obs, instruction)
