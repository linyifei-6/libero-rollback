"""GR00T N1.7 (LeRobot port) adapter for LIBERO-Rollback.

Checkpoint: ``work/ckpt/groot_lerobot/libero_spatial`` (LeRobot-format export of
``nvidia/GR00T-N1.7-LIBERO``).  LeRobot >= 0.7 supports N1.7 natively; the checkpoint
carries its own ``processor_config.json`` (Gr00tN1d7Processor) which performs the
GR00T-specific image/state normalisation and action decoding.  The language key
is ``task``.

Conventions (mirror ``NVIDIA/Isaac-GR00T`` ``gr00t/eval/sim/LIBERO/libero_env.py``):

* both cameras are rotated 180 deg before the processor;
* proprio is ``[eef_pos(3), axisangle(eef_quat)(3), gripper_qpos(2)]`` -- the
  modality keys are *named* ``roll/pitch/yaw`` but the official LIBERO wrapper
  fills them with :func:`quat2axisangle`, not Euler angles;
* the decoded 7-D action is the raw LIBERO OSC **delta** action
  ``[dx, dy, dz, dax, day, daz, gripper]``; the checkpoint's LIBERO decode
  transform already maps the dataset's ``[0, 1]`` gripper to the environment's
  ``-1 = open / +1 = close`` convention (``-sign(2g - 1)``), so the chunk is
  env-ready and must be executed through LIBERO's default *relative* controller;
* NVIDIA replans after 8 of the 16 decoded steps (``configs/models.yaml``
  ``replan_steps: 8``).
"""

from __future__ import annotations

import os

from .lerobot_base import LeRobotPolicyBase

CHECKPOINT_DEFAULT = "/home/ubuntu/whj/work/ckpt/groot_lerobot/libero_spatial"


class GrootLiberoPolicy(LeRobotPolicyBase):
    policy_name = "groot_n1.7"
    # Isaac-GR00T's LiberoEnv feeds quat2axisangle(robot0_eef_quat) under the
    # roll/pitch/yaw state keys.  GROOT_STATE_ORIENTATION=euler reproduces the
    # original (wrong) A/B baseline.
    state_orientation = os.environ.get("GROOT_STATE_ORIENTATION", "axisangle")
    # The decoded action is a LIBERO OSC delta action, not an absolute pose.
    control_mode = "relative"
    image_keys = ("observation.images.image", "observation.images.wrist_image")

    def __init__(
        self,
        checkpoint: str | os.PathLike[str] | None = None,
        logger=None,
    ) -> None:
        from lerobot.policies.groot import GrootPolicy as _Policy

        path = str(checkpoint or CHECKPOINT_DEFAULT)
        policy = _Policy.from_pretrained(path)
        # The LeRobot GR00T loader keeps the generic default tag; the LIBERO export
        # ships normalisation stats under the "libero_sim" tag and needs the LIBERO
        # relative-action decode.
        policy.config.embodiment_tag = "libero_sim"
        policy.config.action_decode_transform = "libero"
        super().__init__(path, policy, logger=logger)
