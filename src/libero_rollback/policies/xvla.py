"""LeRobot X-VLA adapter (``lerobot/xvla-libero``, 0.88 B, flow matching).

The checkpoint emits **absolute** end-effector poses (OSC target: xyz + 6-D
rotation + gripper), so this adapter declares ``control_mode = "absolute"``;
the runner switches the LIBERO controller to absolute targets after the
settle phase.  Everything else mirrors the evaluation stack that reproduces
the checkpoint's published LIBERO behaviour:

* agentview is rotated 180 deg (HuggingFaceVLA/libero camera convention),
  the wrist view is used as-is;
* ImageNet normalisation happens **once**, on the environment side
  (``make_xvla_libero_pre_post_processors``), exactly like ``lerobot-eval``;
* proprio is ``[eef_pos(3), rot6d(eef_mat)(6)]`` padded to the model's 20-dim
  state vector, built from the same ``LiberoProcessorStep``;
* language is tokenised with the checkpoint's own
  ``policy_preprocessor.json`` (bart-large, ``max_length=50``, ``max_length``
  padding) and the LIBERO soft-prompt domain id (3) comes from that config;
* each query materialises a native 30-action chunk, de-normalised (IDENTITY)
  and converted from 6-D rotation to LIBERO axis-angle with the gripper
  binarised to -1/+1.

Run it inside the LeRobot env (``torch`` + ``lerobot >= 0.4.4`` with the
``xvla`` policy); imports are lazy so the runner can be imported without torch.
"""

from __future__ import annotations

import math
import os
import time
from collections.abc import Mapping
from typing import Any

import numpy as np


def _batch(tensor) -> Any:
    """Add the leading batch dimension the processors expect."""
    import torch

    if not isinstance(tensor, torch.Tensor):
        tensor = torch.from_numpy(np.asarray(tensor)).float()
    else:
        tensor = tensor.float()
    return tensor if tensor.ndim >= 2 and tensor.shape[0] == 1 else tensor.unsqueeze(0)


#: rotation between the LIBERO-Franka ``robot0_eef_quat`` frame and the
#: controller's world-frame ``ee_ori_mat`` (measured: constant across suites,
#: init states and settle phases). Only used when the runner cannot attach
#: ``robot0_eef_mat`` directly.
LIBERO_FRANKA_MOUNT = np.array(
    [
        [0.0025, -0.9983, 0.0574],
        [0.9983, 0.0000, -0.0574],
        [0.0574, 0.0574, 0.9967],
    ]
)


def quat_to_mat(quat: np.ndarray) -> np.ndarray:
    """``(x, y, z, w)`` quaternion -> 3x3 rotation matrix (robosuite convention)."""

    q = np.asarray(quat, dtype=np.float64)
    norm = float(np.linalg.norm(q))
    if norm < 1e-12:
        return np.eye(3)
    x, y, z, w = q / norm
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


class XvlaPolicy:
    """Expose X-VLA through the runner's reset/predict protocol."""

    #: the runner flips ``controller.use_delta`` to False for this model
    control_mode = "absolute"

    def __init__(
        self, checkpoint: str | os.PathLike[str], logger: Any | None = None
    ) -> None:
        import torch
        from lerobot.policies.factory import make_pre_post_processors
        from lerobot.policies.xvla.modeling_xvla import XVLAPolicy
        from lerobot.policies.xvla.processor_xvla import (
            make_xvla_libero_pre_post_processors,
        )

        self._torch = torch
        self._logger = logger
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.checkpoint = str(checkpoint)
        started = time.time()
        self.policy = (
            XVLAPolicy.from_pretrained(self.checkpoint).to(self._device).eval()
        )
        # official policy-side processors shipped with the checkpoint
        self.preprocess, self.postprocess = make_pre_post_processors(
            self.policy.config,
            self.checkpoint,
            preprocessor_overrides={"device_processor": {"device": str(self._device)}},
        )
        # LIBERO-side processors: 180 deg flip, single ImageNet pass, domain id,
        # 20-dim proprio; the same pair `lerobot-eval` uses.
        self.env_preprocess, self.env_postprocess = (
            make_xvla_libero_pre_post_processors()
        )
        self.chunk_size = int(self.policy.config.n_action_steps)
        self.metadata = {
            "policy": "xvla",
            "checkpoint": self.checkpoint,
            "device": str(self._device),
            "torch": torch.__version__,
            "chunk_size": self.chunk_size,
            "control_mode": self.control_mode,
            "load_seconds": round(time.time() - started, 2),
        }

    # ------------------------------------------------------------------ utils
    def reset(self, seed: int) -> None:
        torch = self._torch
        self.policy.reset()
        torch.manual_seed(int(seed))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(seed))

    @staticmethod
    def _image(image: np.ndarray):
        import torch

        array = np.ascontiguousarray(np.asarray(image))
        tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0).float()
        return tensor / 255.0

    def _observation(self, obs: Mapping[str, Any], instruction: str) -> dict[str, Any]:
        eef_pos = np.asarray(obs["robot0_eef_pos"], dtype=np.float64)
        eef_quat = np.asarray(obs["robot0_eef_quat"], dtype=np.float64)
        # The official LeRobot LIBERO env feeds ``controller.ee_ori_mat`` (world
        # frame). The runner attaches it as ``robot0_eef_mat``; standalone use
        # falls back to the quaternion with the fixed LIBERO-Franka mount.
        eef_mat = obs.get("robot0_eef_mat")
        if eef_mat is not None:
            eef_mat = np.asarray(eef_mat, dtype=np.float64)
        else:
            eef_mat = LIBERO_FRANKA_MOUNT @ quat_to_mat(eef_quat)
        robot_state = {
            "eef": {
                "pos": _batch(eef_pos),
                "quat": _batch(eef_quat),
                "mat": _batch(eef_mat),
            },
            "gripper": {
                "qpos": _batch(np.asarray(obs["robot0_gripper_qpos"], dtype=np.float64)),
                "qvel": _batch(
                    np.asarray(obs.get("robot0_gripper_qvel", np.zeros(2)), dtype=np.float64)
                ),
            },
            "joints": {
                "pos": _batch(
                    np.asarray(obs.get("robot0_joint_pos", np.zeros(7)), dtype=np.float64)
                ),
                "vel": _batch(
                    np.asarray(obs.get("robot0_joint_vel", np.zeros(7)), dtype=np.float64)
                ),
            },
        }
        return {
            "observation.images.image": self._image(obs["agentview_image"]),
            "observation.images.image2": self._image(obs["robot0_eye_in_hand_image"]),
            "observation.robot_state": robot_state,
            "task": [str(instruction)],
        }

    # -------------------------------------------------------------- interface
    def predict(self, observation: Mapping[str, Any], instruction: str) -> np.ndarray:
        import torch

        batch = self._observation(observation, instruction)
        batch = self.env_preprocess(batch)
        batch = self.preprocess(batch)
        actions = []
        with torch.inference_mode():
            for _ in range(self.chunk_size):
                action = self.postprocess(self.policy.select_action(batch))
                action = self.env_postprocess({"action": action})["action"]
                actions.append(action[0].detach().float().cpu().numpy())
        chunk = np.asarray(actions, dtype=np.float64)
        if chunk.ndim != 2 or chunk.shape[1] < 7:
            raise ValueError(f"unexpected X-VLA action chunk shape: {chunk.shape}")
        return chunk[:, :7]

    def reset_episode(self, seed: int) -> None:
        self.reset(seed)

    def predict_chunk(
        self, obs: Mapping[str, Any], instruction: str
    ) -> np.ndarray:
        return self.predict(obs, instruction)
