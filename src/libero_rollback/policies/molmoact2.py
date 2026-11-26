"""MolmoAct2 (allenai) LeRobot adapter for LIBERO-Rollback.

Checkpoint: ``work/ckpt/molmoact2`` (10.9 GB, 5.44B params, LeRobot format).
The policy needs the original HF base checkpoint for architecture/norm metadata; a
vendored offline patch lets it build the network from config alone, so only the 2 MB
of base metadata under ``work/ckpt/molmoact2-base`` is required.  The pre/post
processors saved with the checkpoint own normalisation, so this adapter feeds raw
LIBERO observations (both camera views rotated 180 deg, 8-dim proprio).
"""

from __future__ import annotations

import os

from .lerobot_base import LeRobotPolicyBase

CHECKPOINT_DEFAULT = "/home/ubuntu/whj/work/ckpt/molmoact2-eval"


class MolmoAct2Policy(LeRobotPolicyBase):
    policy_name = "molmoact2"
    image_keys = ("observation.images.image", "observation.images.wrist_image")

    def __init__(
        self,
        checkpoint: str | os.PathLike[str] | None = None,
        logger=None,
    ) -> None:
        from lerobot.policies.molmoact2 import MolmoAct2Policy as _Policy

        path = str(checkpoint or CHECKPOINT_DEFAULT)
        policy = _Policy.from_pretrained(path)
        super().__init__(path, policy, logger=logger)
