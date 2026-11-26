"""Xiaomi-Robotics-0 (MiBoT) adapter for LIBERO-Rollback.

The 4.72B MiBoT checkpoint ships its own ``transformers`` remote code
(``configuration_mibot.py`` / ``modeling_mibot.py`` / ``processing_mibot.py``) plus the
LIBERO action normalisation statistics (``preprocessor_config.json``).  The reference
LIBERO client (verified in ``work/testability``) does:

* both camera views rotated 180 deg,
* proprio ``[eef_pos(3), axisangle(eef_quat)(3), gripper_qpos(2)]`` padded to 32,
* native 10-action chunk, ``relative`` OSC control, flow-matching with 5 steps,
* per-query ``seed`` for reproducible sampling.

The adapter returns env-ready 7-dim actions (the 7 active dims of the 32-dim padded
action vector) and declares ``control_mode = "relative"`` (LIBERO's default).
"""

from __future__ import annotations

import math
import os
import time
from collections.abc import Mapping
from typing import Any

import numpy as np

CKPT_DEFAULT = "/home/ubuntu/whj/work/ckpt/xiaomi_robotics_0"


def quat2axisangle(quat: np.ndarray) -> np.ndarray:
    q = np.asarray(quat, dtype=np.float64)
    qw = float(np.clip(q[3], -1.0, 1.0))
    den = math.sqrt(max(1.0 - qw * qw, 0.0))
    if den < 1e-9:
        return np.zeros(3, dtype=np.float32)
    return (q[:3] * 2.0 * math.acos(qw) / den).astype(np.float32)


def build_instruction(language: str) -> str:
    return (
        "<|im_start|>user\nThe following observations are captured from multiple views.\n"
        "# Base View\n<|vision_start|><|image_pad|><|vision_end|>\n"
        "# Left-Wrist View\n<|vision_start|><|image_pad|><|vision_end|>\n"
        "Generate robot actions for the task:\n"
        f"{language} /no_cot<|im_end|>\n"
        "<|im_start|>assistant\n<cot></cot><|im_end|>\n"
    )


class XiaomiPolicy:
    """Expose Xiaomi-Robotics-0 through the runner's reset/predict protocol."""

    control_mode = "relative"

    def __init__(
        self,
        checkpoint: str | os.PathLike[str] | None = None,
        logger: Any | None = None,
        num_steps: int = 5,
    ) -> None:
        import torch
        from transformers import AutoModel, AutoProcessor

        self._torch = torch
        self._logger = logger
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.checkpoint = str(checkpoint or CKPT_DEFAULT)
        self.num_steps = int(num_steps)
        started = time.time()
        self.processor = AutoProcessor.from_pretrained(
            self.checkpoint, trust_remote_code=True, use_fast=False
        )
        self.model = (
            AutoModel.from_pretrained(
                self.checkpoint,
                trust_remote_code=True,
                attn_implementation="eager",  # custom class rejects SDPA; no flash-attn here
                dtype=torch.bfloat16,
            )
            .to(self._device)
            .eval()
        )
        self.mask = self.processor.get_action_mask("libero_all").to(self._device, torch.bfloat16)
        self.active = torch.nonzero(self.mask[0, 0]).flatten().tolist()
        self.chunk_size = int(self.mask.shape[1])
        self._query = 0
        self.metadata = {
            "policy": "xiaomi",
            "checkpoint": self.checkpoint,
            "device": str(self._device),
            "torch": torch.__version__,
            "chunk_size": self.chunk_size,
            "active_action_dims": self.active,
            "control_mode": self.control_mode,
            "load_seconds": round(time.time() - started, 2),
        }

    def reset(self, seed: int) -> None:
        self._query = 0
        self._torch.manual_seed(int(seed))
        if self._torch.cuda.is_available():
            self._torch.cuda.manual_seed_all(int(seed))

    def predict(self, observation: Mapping[str, Any], instruction: str) -> np.ndarray:
        import torch
        from PIL import Image

        agent = np.asarray(observation["agentview_image"])
        wrist = np.asarray(observation["robot0_eye_in_hand_image"])
        agent = np.ascontiguousarray(agent[::-1, ::-1])
        wrist = np.ascontiguousarray(wrist[::-1, ::-1])
        state = np.zeros(32, dtype=np.float32)
        raw = np.concatenate(
            [
                np.asarray(observation["robot0_eef_pos"], dtype=np.float64),
                quat2axisangle(np.asarray(observation["robot0_eef_quat"], dtype=np.float64)),
                np.asarray(observation["robot0_gripper_qpos"], dtype=np.float64),
            ]
        )
        state[:8] = raw[:8]
        inputs = self.processor(
            text=[build_instruction(str(instruction))],
            images=[Image.fromarray(agent), Image.fromarray(wrist)],
            videos=None,
            padding=True,
            return_tensors="pt",
        ).to(self._device)
        inputs["state"] = torch.from_numpy(state).view(1, 1, -1).to(self._device, torch.bfloat16)
        with torch.inference_mode():
            out = self.model(
                state=inputs["state"],
                action_mask=self.mask,
                num_steps=self.num_steps,
                seed=torch.tensor(self._query, device=self._device),
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
                pixel_values=inputs["pixel_values"],
                image_grid_thw=inputs["image_grid_thw"],
            )
        self._query += 1
        chunk = self.processor.decode_action(out.actions, robot_type="libero_all")[0]
        chunk = chunk[:, self.active].float().cpu().numpy()
        return np.clip(np.asarray(chunk, dtype=np.float64), -1.0, 1.0)

    def reset_episode(self, seed: int) -> None:
        self.reset(seed)

    def predict_chunk(self, obs: Mapping[str, Any], instruction: str) -> np.ndarray:
        return self.predict(obs, instruction)
