"""DM05 / DM0.5 (Dexmal ``opendm``) adapter for LIBERO-Rollback.

Checkpoint: ``work/ckpt/dm05`` (``DM05-libero``: Gemma3-4B VLM + 680M action
expert, ~11 GB bf16).  The released LIBERO checkpoint is evaluated by the
official ``playground/dm05_libero.py`` + ``DM05InferenceConfig`` deployment
path.  That path defines the whole contract this adapter mirrors:

* both camera views rotated 180 deg (the dexbotic LIBERO client does
  ``obs["agentview_image"][::-1, ::-1]`` / ``"robot0_eye_in_hand_image"``),
* images then padded to square and resized to 448x448
  (``NoAugmentationPipeline`` inside opendm's ``PixelTransform``),
* 8-dim proprio ``[eef_pos(3), quat2axisangle(eef_quat)(3), gripper_qpos(2)]``
  normalised with the checkpoint's quantile ``norm_stats.json``,
* prompt built by ``ChatTokenization``:
  ``"Robot: Franka\\nOverall speed: 0.5\\nTask: <instruction>.\\n"
  "Head image: <img>Left wrist image: <img>"`` (``add_state=False``),
* native 10-action chunk (``--model-config.chunk-size 10``, must match
  training), 10 flow-matching steps,
* the action is the checkpoint's learned 7-dim LIBERO action, de-normalised
  with the checkpoint statistics and fed to the environment **as-is**.

Action/controller semantics (verified against the checkpoint's
``norm_stats.json`` and a real LIBERO observation):

* ``state`` 8-dim quantiles are ``[eef_pos, axis-angle, gripper_qpos]`` with
  eef z in ``[0.04, 1.27]`` and the downward orientation axis-angle x near
  ``pi`` - the adapter feeds exactly that.
* ``action`` 7-dim quantiles are ``pos ~[-0.9, 0.9]``, ``axis-angle
  ~[-0.34, 0.34]``, ``gripper [-1, 1]`` -- i.e. raw LIBERO OSC **delta**
  commands (the benchmark's ``action_mode=ABSOLUTE`` only means the JSONL
  carries explicit 7-dim action vectors instead of deriving them from future
  states; it is *not* an absolute EEF pose).
* the official dexbotic harness runs the unmodified upstream LIBERO
  (``Lifelong-Robot-Learning/LIBERO``) and calls ``env.step(action)`` with the
  default relative OSC controller; DM05's published 99 % LIBERO numbers use
  exactly that path.  This adapter therefore declares ``control_mode =
  "relative"``; declaring ``absolute`` would set ``controller.use_delta =
  False`` and interpret the delta commands as absolute poses, which sends the
  arm to garbage poses.

The adapter reconstructs opendm's deployment pipeline with the same classes
(``PixelTransform`` / ``Normalize`` / ``ChatTokenization`` / ``Denormalize``)
instead of importing ``opendm.exp.dm05_exp``: that module imports the Flask
service, tyro and the HF ``Trainer`` (and therefore peft), none of which the
offline DM05 rollout environment provides.  Model construction follows
``dm05_load_check.py``: checkpoint config first, VLM/action-expert attention
forced to ``sdpa`` (the checkpoint asks for flex/flash attention),
``chunk_size=10``, plus a small compatibility shim for transformers 5.5.3's
``Gemma3DecoderLayer.attention_type``.

The opendm checkout and its transformers 5.5.3 stack must be on
``PYTHONPATH`` (see ``configs/models.yaml``); every heavy import is lazy so
importing this module stays framework-free.
"""

from __future__ import annotations

import math
import os
import time
from collections.abc import Mapping
from typing import Any

import numpy as np

CKPT_DEFAULT = "/home/ubuntu/whj/work/ckpt/dm05"
IMAGE_PROMPTS = ("Head", "Left wrist")


def quat2axisangle(quat: np.ndarray) -> np.ndarray:
    """``(x, y, z, w)`` quaternion -> 3-dim axis-angle (robosuite convention)."""

    q = np.asarray(quat, dtype=np.float64)
    qw = float(np.clip(q[3], -1.0, 1.0))
    den = math.sqrt(max(1.0 - qw * qw, 0.0))
    if den < 1e-9:
        return np.zeros(3, dtype=np.float32)
    return (q[:3] * 2.0 * math.acos(qw) / den).astype(np.float32)


def _force_sdpa(config: Any) -> None:
    """Force every DM05 attention backend to ``sdpa`` before construction.

    The checkpoint's ``config.json`` asks for ``flex_attention`` (text) and
    ``flash_attention_2`` (vision).  transformers 5.5.3 exposes
    ``_attn_implementation`` as a property whose setter accepts a dict and
    propagates to the Gemma3 text/vision sub-configs, exactly like
    ``DM05ModelConfig._apply_attention_config_before_load``.  The top-level
    DM05 config is intentionally left alone: it does not advertise SDPA
    support, and the outer module only delegates to the VLM / action expert.
    """

    config.vlm_config._attn_implementation = {
        "": "sdpa",
        "text_config": "sdpa",
        "vision_config": "sdpa",
    }
    config.action_config._attn_implementation = "sdpa"


def _patch_action_expert_layer_types(model: Any) -> None:
    """Expose ``Gemma3DecoderLayer.attention_type`` for opendm's suffix forward.

    opendm's action-expert suffix loop reads ``layer.attention_type`` (its
    pinned transformers exposes it), but transformers 5.5.3 keeps the same
    information on ``Gemma3Attention.layer_type``.  Derive the attribute from
    there (falling back to ``config.layer_types[layer_idx]``) so the upstream
    suffix forward runs unchanged on this stack.
    """

    action_expert = getattr(getattr(model, "model", None), "action_expert", None)
    layers = getattr(action_expert, "layers", None)
    if not layers:
        return
    layer_types = getattr(getattr(action_expert, "config", None), "layer_types", None)
    for layer_idx, layer in enumerate(layers):
        if getattr(layer, "attention_type", None) is not None:
            continue
        layer_type = getattr(getattr(layer, "self_attn", None), "layer_type", None)
        if layer_type is None and layer_types:
            layer_type = layer_types[layer_idx]
        if layer_type is not None:
            layer.attention_type = layer_type


class Dm05Policy:
    """Expose DM05 (opendm) through the runner's reset/predict protocol."""

    #: DM05 emits LIBERO's standard relative OSC commands (delta pose + grip)
    control_mode = "relative"

    def __init__(
        self,
        checkpoint: str | os.PathLike[str] | None = None,
        logger: Any | None = None,
        diffusion_steps: int = 10,
        chunk_size: int = 10,
        model_max_length: int = 1024,
    ) -> None:
        import torch
        from transformers import AutoProcessor

        import opendm.data.normalize as normalize
        from opendm.data.augmentations import NoAugmentationPipeline
        from opendm.data.transforms import (
            ChatTokenization,
            Denormalize,
            Normalize,
            Pipeline,
            PixelTransform,
            ToDevice,
        )
        from opendm.model.dm05.dm05_arch import (
            DM05Config,
            DM05ForConditionalGeneration,
        )

        self._torch = torch
        self._logger = logger
        self.checkpoint = str(checkpoint or CKPT_DEFAULT)
        norm_stats_path = os.path.join(self.checkpoint, "norm_stats.json")
        if not os.path.isfile(norm_stats_path):
            raise FileNotFoundError(
                f"DM05 norm stats not found at {norm_stats_path}; the checkpoint "
                "directory must contain norm_stats.json"
            )
        self.diffusion_steps = int(diffusion_steps)
        self.chunk_size = int(chunk_size)
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        started = time.time()

        config = DM05Config.from_pretrained(self.checkpoint)
        _force_sdpa(config)
        # The checkpoint's config.json says chunk_size=50 (base DM05); the
        # LIBERO checkpoint was trained (and must be inferred) with 10.
        config.chunk_size = self.chunk_size
        model = DM05ForConditionalGeneration.from_pretrained(
            self.checkpoint,
            config=config,
            dtype=torch.bfloat16,
        )
        model.set_precision_policy("bf16_mixed")
        model.set_attention_implementation(
            llm_attn_implementation="sdpa",
            vision_attn_implementation="sdpa",
            action_attn_implementation="sdpa",
            bf16=True,
        )
        model.eval()
        model.to(self.device)
        _patch_action_expert_layer_types(model)
        self.model = model

        self.processor = AutoProcessor.from_pretrained(
            self.checkpoint, trust_remote_code=True
        )
        self.norm_stats_file = normalize.load_norm_stats_file(norm_stats_path)
        # Mirrors DM05InferenceConfig._initialize_preprocessing(...):
        #   use_absolute_action=False, add_state=False, is_history=False,
        #   clip_to_bounds=True, n_bins=256.
        self.input_transform = Pipeline(
            [
                PixelTransform(transform_pipeline=NoAugmentationPipeline()),
                Normalize(
                    norm_stats_path=norm_stats_path,
                    norm_keys=["state"],
                    use_quantiles=True,
                    norm_stats_file=self.norm_stats_file,
                    clip_to_bounds=True,
                ),
                ChatTokenization(
                    processor=self.processor,
                    n_bins=256,
                    max_length=int(model_max_length),
                    image_prompts=list(IMAGE_PROMPTS),
                    add_state=False,
                    is_history=False,
                ),
                ToDevice(device=self.device),
            ]
        )
        self.output_transform = Pipeline(
            [
                Denormalize(
                    norm_stats_path=norm_stats_path,
                    norm_keys=["action"],
                    use_quantiles=True,
                    norm_stats_file=self.norm_stats_file,
                )
            ]
        )
        self.metadata = {
            "policy": "dm05",
            "checkpoint": self.checkpoint,
            "device": str(self.device),
            "torch": torch.__version__,
            "chunk_size": self.chunk_size,
            "diffusion_steps": self.diffusion_steps,
            "control_mode": self.control_mode,
            "action_mode": "relative",
            "action_space": "libero_osc_delta",
            "load_seconds": round(time.time() - started, 2),
        }

    # ------------------------------------------------------------------ utils
    def reset(self, seed: int) -> None:
        torch = self._torch
        torch.manual_seed(int(seed))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(seed))

    def _observation(self, observation: Mapping[str, Any], instruction: str) -> dict:
        from PIL import Image

        # dexbotic LIBERO client: rotate both views 180 degrees.
        agent = np.ascontiguousarray(
            np.asarray(observation["agentview_image"])[::-1, ::-1]
        )
        wrist = np.ascontiguousarray(
            np.asarray(observation["robot0_eye_in_hand_image"])[::-1, ::-1]
        )
        if agent.dtype != np.uint8:
            agent = np.clip(agent, 0, 255).astype(np.uint8)
        if wrist.dtype != np.uint8:
            wrist = np.clip(wrist, 0, 255).astype(np.uint8)
        state = np.concatenate(
            [
                np.asarray(observation["robot0_eef_pos"], dtype=np.float64),
                quat2axisangle(observation["robot0_eef_quat"]),
                np.asarray(observation["robot0_gripper_qpos"], dtype=np.float64),
            ]
        ).astype(np.float32)
        return {
            "images": [Image.fromarray(agent), Image.fromarray(wrist)],
            "prompt": str(instruction),
            "state": state,
            "meta_data": {
                "robot_type": "Franka",
                "speed": "0.5",
            },
        }

    # -------------------------------------------------------------- interface
    def predict(self, observation: Mapping[str, Any], instruction: str) -> np.ndarray:
        import torch

        from opendm.model.dm05.dm05_utils import dm05_inference_context

        data = self._observation(observation, instruction)
        model_input = self.input_transform(data)
        dm05_model = self.model
        action_dim = dm05_model.model.config.action_dim
        dtype = dm05_model.model.action_in_proj.weight.dtype
        action_mask = torch.zeros(
            1, 1, action_dim, device=self.device, dtype=dtype
        )
        action_mask[..., :7] = 1.0

        if torch.cuda.is_available():
            torch.cuda.synchronize()
        with torch.inference_mode():
            with dm05_inference_context(
                self.device, dm05_model.precision_policy
            ):
                actions = dm05_model.inference_action(
                    input_ids=model_input["input_ids"],
                    attention_mask=model_input["attention_mask"],
                    pixel_values=model_input["pixel_values"],
                    token_type_ids=model_input["token_type_ids"],
                    diffusion_steps=self.diffusion_steps,
                    action_mask=action_mask,
                    history_pixel_values=model_input.get("history_pixel_values"),
                    history_mask=model_input.get("history_mask"),
                )
        raw_actions = (
            actions.to(torch.float32).detach().cpu().numpy()[0, :, :7]
        )
        outputs = self.output_transform(
            {
                "action": raw_actions,
                "state": data["state"],
                "meta_data": data["meta_data"],
            }
        )
        chunk = np.asarray(outputs["action"], dtype=np.float64)
        if chunk.ndim != 2 or chunk.shape[1] < 7:
            raise ValueError(f"unexpected DM05 action chunk shape: {chunk.shape}")
        chunk = chunk[:, :7].copy()
        # 7-dim LIBERO OSC command [delta_pos(3), delta_axisangle(3), grip(1)].
        # robosuite's scale_action clips every dimension to [-1, 1] anyway;
        # doing it here keeps the recorded chunk inside the action space.
        chunk = np.clip(chunk, -1.0, 1.0)
        return chunk

    def reset_episode(self, seed: int) -> None:
        self.reset(seed)

    def predict_chunk(
        self, obs: Mapping[str, Any], instruction: str
    ) -> np.ndarray:
        return self.predict(obs, instruction)
