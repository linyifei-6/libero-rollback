"""VLA-JEPA (LeRobot port) adapter for LIBERO-Rollback.

LeRobot >= 0.7 ships ``lerobot.policies.vla_jepa``; the released checkpoint is a
LeRobot fine-tune whose config references the Qwen3-VL decoder and the V-JEPA2 video
encoder by Hub id.  ``work/ckpt/vla_jepa_lerobot-eval`` points those two fields at the
local copies (``ckpt/Qwen3-VL-2B-Instruct``, ``ckpt/vjepa2``) so the policy loads fully
offline.

Protocol used by the reference LIBERO client: both camera views rotated 180 deg,
proprio ``[eef_pos(3), axisangle(eef_quat)(3), gripper_qpos(2)]``, native 7-action
chunk, relative OSC control.
"""

from __future__ import annotations

import math
import os
import time
from collections.abc import Mapping
from typing import Any

import numpy as np

CHECKPOINT_DEFAULT = "/home/ubuntu/whj/work/ckpt/vla_jepa_lerobot-eval"


def quat2axisangle(quat: np.ndarray) -> np.ndarray:
    q = np.asarray(quat, dtype=np.float64)
    qw = float(np.clip(q[3], -1.0, 1.0))
    den = math.sqrt(max(1.0 - qw * qw, 0.0))
    if den < 1e-9:
        return np.zeros(3, dtype=np.float32)
    return (q[:3] * 2.0 * math.acos(qw) / den).astype(np.float32)


class VlaJepaPolicy:
    control_mode = "relative"

    def __init__(
        self,
        checkpoint: str | os.PathLike[str] | None = None,
        logger: Any | None = None,
    ) -> None:
        import torch
        from lerobot.policies.factory import make_pre_post_processors
        from lerobot.policies.vla_jepa import VLAJEPAPolicy

        self._torch = torch
        self._logger = logger
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.checkpoint = str(checkpoint or CHECKPOINT_DEFAULT)
        started = time.time()
        self.policy = VLAJEPAPolicy.from_pretrained(self.checkpoint).to(self._device).eval()
        self.preprocess, self.postprocess = make_pre_post_processors(
            self.policy.config,
            self.checkpoint,
            preprocessor_overrides={"device_processor": {"device": str(self._device)}},
        )
        self.chunk_size = int(getattr(self.policy.config, "n_action_steps", 7))
        self.metadata = {
            "policy": "vla_jepa_lerobot",
            "checkpoint": self.checkpoint,
            "device": str(self._device),
            "torch": torch.__version__,
            "chunk_size": self.chunk_size,
            "control_mode": self.control_mode,
            "load_seconds": round(time.time() - started, 2),
        }

    def reset(self, seed: int) -> None:
        if hasattr(self.policy, "reset"):
            self.policy.reset()
        self._torch.manual_seed(int(seed))
        if self._torch.cuda.is_available():
            self._torch.cuda.manual_seed_all(int(seed))

    def predict(self, observation: Mapping[str, Any], instruction: str) -> np.ndarray:
        import torch

        agent = np.ascontiguousarray(np.asarray(observation["agentview_image"])[::-1, ::-1])
        wrist = np.ascontiguousarray(np.asarray(observation["robot0_eye_in_hand_image"])[::-1, ::-1])
        state = np.concatenate(
            [
                np.asarray(observation["robot0_eef_pos"], dtype=np.float64),
                quat2axisangle(np.asarray(observation["robot0_eef_quat"], dtype=np.float64)),
                np.asarray(observation["robot0_gripper_qpos"], dtype=np.float64),
            ]
        ).astype(np.float32)
        batch = {
            "observation.images.image": torch.from_numpy(agent).permute(2, 0, 1).unsqueeze(0).float() / 255.0,
            "observation.images.image2": torch.from_numpy(wrist).permute(2, 0, 1).unsqueeze(0).float() / 255.0,
            "observation.state": torch.from_numpy(state).unsqueeze(0),
            "task": [str(instruction)],
        }
        batch = self.preprocess(batch)
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
