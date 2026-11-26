"""FastWAM (LeRobot port) adapter for LIBERO-Rollback.

Checkpoint: ``work/ckpt/fastwam`` (LeRobot format, 6.02B params).  The policy needs the Wan2.2
diffusers pieces (VAE + UMT5 text encoder), which are mirrored locally under
``work/ckpt/wan22``; the vendored FastWAM code points at that path.  The checkpoint's
own pre/post processors own state/action normalisation.

Two input-contract fixes are required for this checkpoint (see the class docstrings):

* ``observation.state`` is ``eef_pos + quat2axisangle + gripper_qpos`` (axis-angle,
  matching LeRobot's own LIBERO integration), not Euler angles.
* The released checkpoint's preprocessor normalises images with ``VISUAL=MEAN_STD``
  and ``mean=std=0.5`` (i.e. ``[0, 1] -> [-1, 1]``), but FastWAM's model maps the
  image it receives from ``[0, 1]`` to ``[-1, 1]`` itself at the Wan VAE boundary
  (``_encode_input_image_latents_tensor``).  Keeping the saved visual normaliser
  therefore double-normalises to ``[-3, 1]``, which pushes the VAE latents far out
  of distribution and collapses the action expert to the dataset mean (near-zero
  EEF deltas, constant gripper).  The model contract is ``VISUAL=IDENTITY`` — see
  ``processor_fastwam.py`` — so the visual normaliser is neutralised here.
"""

from __future__ import annotations

import os

from .lerobot_base import LeRobotPolicyBase

CHECKPOINT_DEFAULT = "/home/ubuntu/whj/work/ckpt/fastwam-eval"


def _force_identity_visual_normalization(pipeline) -> bool:
    """Make the loaded preprocessor pass images through in ``[0, 1]``.

    The Wan VAE boundary inside FastWAM already maps ``[0, 1] -> [-1, 1]``; a
    ``VISUAL=MEAN_STD`` (mean=std=0.5) normaliser in front of it would map to
    ``[-1, 1]`` first and the model would then feed ``[-3, 1]`` to the VAE.
    Returns whether a visual normalisation mode was overridden.
    """
    from lerobot.configs import FeatureType, NormalizationMode
    from lerobot.processor import NormalizerProcessorStep

    changed = False
    for step in getattr(pipeline, "steps", []):
        if not isinstance(step, NormalizerProcessorStep):
            continue
        if step.norm_map.get(FeatureType.VISUAL) not in (None, NormalizationMode.IDENTITY):
            step.norm_map[FeatureType.VISUAL] = NormalizationMode.IDENTITY
            changed = True
    return changed


class FastWamPolicy(LeRobotPolicyBase):
    policy_name = "fastwam"
    # LeRobot's LIBERO integration builds the 8-D state as
    # ``eef_pos + quat2axisangle(eef_quat) + gripper_qpos``.
    state_orientation = "axisangle"
    # FastWAM's LeRobot export names the two cameras ``image`` and ``image2``.
    image_keys = ("observation.images.image", "observation.images.image2")

    def __init__(
        self,
        checkpoint: str | os.PathLike[str] | None = None,
        logger=None,
    ) -> None:
        from lerobot.policies.fastwam import FastWAMPolicy as _Policy

        path = str(checkpoint or CHECKPOINT_DEFAULT)
        policy = _Policy.from_pretrained(path)
        super().__init__(path, policy, logger=logger)
        self.visual_normalization_override = _force_identity_visual_normalization(
            self.preprocess
        )
        self.metadata["state_orientation"] = self.state_orientation
        self.metadata["visual_normalization"] = (
            "identity ([0,1] -> model VAE [-1,1])"
            if self.visual_normalization_override
            else "as-saved"
        )
