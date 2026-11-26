"""Shared plumbing for adapters that drive a LeRobot >= 0.7 policy.

The rollback runner only needs two methods: ``reset_episode(seed)`` and
``predict_chunk(obs, instruction) -> (T, 7)``.  This base class turns a LIBERO
observation dict into the LeRobot ``batch`` layout (two cameras + proprio + task string),
runs the policy's own pre/post-processor pipeline, and decodes the chunk back to
environment-sized 7-dim actions.
"""

from __future__ import annotations

import math
import os
import time
from collections.abc import Mapping
from typing import Any

import numpy as np


def quat2axisangle(quat: np.ndarray) -> np.ndarray:
    q = np.asarray(quat, dtype=np.float64)
    qw = float(np.clip(q[3], -1.0, 1.0))
    den = math.sqrt(max(1.0 - qw * qw, 0.0))
    if den < 1e-9:
        return np.zeros(3, dtype=np.float32)
    return (q[:3] * 2.0 * math.acos(qw) / den).astype(np.float32)


def quat2euler(quat: np.ndarray) -> np.ndarray:
    """Quaternion (x, y, z, w) -> roll/pitch/yaw (XYZ intrinsic), radians."""
    x, y, z, w = [float(v) for v in np.asarray(quat, dtype=np.float64)]
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    sinp = 2.0 * (w * y - z * x)
    pitch = math.asin(max(-1.0, min(1.0, sinp)))
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    return np.array([roll, pitch, yaw], dtype=np.float32)


def proprio(observation: Mapping[str, Any], orientation: str = "axisangle") -> np.ndarray:
    quat = np.asarray(observation["robot0_eef_quat"], dtype=np.float64)
    rot = quat2axisangle(quat) if orientation == "axisangle" else quat2euler(quat)
    return np.concatenate(
        [
            np.asarray(observation["robot0_eef_pos"], dtype=np.float64),
            rot,
            np.asarray(observation["robot0_gripper_qpos"], dtype=np.float64),
        ]
    ).astype(np.float32)


class LeRobotPolicyBase:
    """Drive a ``PreTrainedPolicy`` from LeRobot >= 0.7 on LIBERO observations."""

    control_mode = "relative"
    image_keys = ("observation.images.image", "observation.images.wrist_image")
    # state orientation encoding used by the checkpoint's training data
    state_orientation = "axisangle"
    # env toggle for camera-convention A/B tests: ROLLBACK_FLIP=0 keeps the raw views
    flip_images = os.environ.get("ROLLBACK_FLIP", "1") != "0"
    policy_name = "lerobot"

    def __init__(
        self,
        checkpoint: str | os.PathLike[str],
        policy: Any,
        logger: Any | None = None,
    ) -> None:
        import torch

        self._torch = torch
        self._logger = logger
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.checkpoint = str(checkpoint)
        started = time.time()
        self.policy = policy.to(self._device).eval()
        from lerobot.policies.factory import make_pre_post_processors

        overrides = {"device_processor": {"device": str(self._device)}}
        self.preprocess, self.postprocess = make_pre_post_processors(
            self.policy.config,
            self.checkpoint,
            preprocessor_overrides=overrides,
        )
        self.chunk_size = int(
            getattr(self.policy.config, "n_action_steps", None)
            or getattr(self.policy.config, "chunk_size", 10)
        )
        self.metadata = {
            "policy": self.policy_name,
            "checkpoint": self.checkpoint,
            "device": str(self._device),
            "torch": torch.__version__,
            "chunk_size": self.chunk_size,
            "control_mode": self.control_mode,
            "load_seconds": round(time.time() - started, 2),
        }

    def reset(self, seed: int) -> None:
        if hasattr(self.policy, "reset"):
            try:
                self.policy.reset()
            except TypeError:
                pass
        self._torch.manual_seed(int(seed))
        if self._torch.cuda.is_available():
            self._torch.cuda.manual_seed_all(int(seed))

    def _images(self, observation: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
        agent = np.asarray(observation["agentview_image"])
        wrist = np.asarray(observation["robot0_eye_in_hand_image"])
        if self.flip_images:
            agent = np.ascontiguousarray(agent[::-1, ::-1])
            wrist = np.ascontiguousarray(wrist[::-1, ::-1])
        return agent, wrist

    def _batch(self, observation: Mapping[str, Any], instruction: str) -> dict[str, Any]:
        import torch

        agent, wrist = self._images(observation)
        keys = self.image_keys
        batch: dict[str, Any] = {
            "observation.state": torch.from_numpy(
                proprio(observation, self.state_orientation)
            ).unsqueeze(0),
            "task": [str(instruction)],
        }
        for key, image in zip(keys, (agent, wrist)):
            batch[key] = torch.from_numpy(image).permute(2, 0, 1).unsqueeze(0).float() / 255.0
        return batch

    def predict(self, observation: Mapping[str, Any], instruction: str) -> np.ndarray:
        import torch

        batch = self.preprocess(self._batch(observation, instruction))
        with torch.inference_mode():
            action = self.policy.predict_action_chunk(batch)
            action = self.postprocess(action)
        chunk = action.detach().float().cpu().numpy()
        chunk = chunk[0] if chunk.ndim == 3 else chunk
        return np.asarray(chunk[:, :7], dtype=np.float64)

    def reset_episode(self, seed: int) -> None:
        self.reset(seed)

    def predict_chunk(self, obs: Mapping[str, Any], instruction: str) -> np.ndarray:
        return self.predict(obs, instruction)
