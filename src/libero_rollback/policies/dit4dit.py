"""DiT4DiT adapter for the LIBERO-Rollback runner.

Wraps `Mondo-Robotics/DiT4DiT` (Cosmos-Predict2.5-2B DiT backbone + Qwen2.5-VL-7B
text encoder + Wan2.1 VAE + DiT-B flow-matching action head, 10.64B bf16) behind
the runner's two-method adapter contract (README §8.4)::

    reset_episode(seed)
    predict_chunk(observation, instruction) -> np.ndarray (T, 7)

Checkpoint reconstruction (no HF hub access)
--------------------------------------------
The released checkpoint (``<run>/final_model/pytorch_model.pt``, 20 GB, 1739
bf16 tensors) contains the *entire* model, but the official loader
``DiT4DiT -> Cosmos25FeatureExtractor -> diffusers.Cosmos2_5_PredictBasePipeline
.from_pretrained(model_id_or_path)`` expects the gated
``nvidia/Cosmos-Predict2.5-2B`` diffusers directory (``model_index.json`` +
per-component ``config.json`` + tokenizer), which is not available offline.
This adapter therefore rebuilds the three heavy components from the checkpoint's
key/shape signature (exactly the recipe of ``third_party/dit4dit_load_check.py``)
and monkeypatches ``from_pretrained`` so the *unmodified* repo loader receives a
locally assembled pipeline:

* ``CosmosTransformer3DModel``  (in=17 out=16, 16x128 heads, 28 layers, text 1024,
  adaln 256, patch (1,2,2), ``use_crossattn_projection`` in=100352);
* ``Qwen2_5_VLForConditionalGeneration`` (hidden 3584, 28 layers, 4 KV heads,
  vocab 152064, mrope [16,24,24]);
* ``AutoencoderKLWan`` — the **Wan2.1** layout (``is_residual=False``,
  ``patch_size=None``, ``temperal_downsample=[False, True, True]``, z_dim 16,
  base_dim 96), i.e. the class defaults.  With those defaults diffusers 0.43
  emits ``decoder.up_blocks.*.upsamplers.0.*`` exactly as the checkpoint does,
  so **all 194 VAE tensors load bit-equal** (the "0.35 vs 0.43 naming gap" only
  appears when the Wan2.2 ``is_residual=True`` layout is requested by mistake).
  ``latents_mean`` / ``latents_std`` are likewise the Wan2.1 constants, which the
  pipeline reads from ``vae.config``.
* the action head is built by ``build_framework(cfg)`` from the checkpoint's own
  ``config.yaml`` (DiT-B, hidden 2560, cross-attn 2048, action_dim 8, chunk 8,
  ``num_inference_timesteps=4``, ``state_dim=16``).

All 1739 tensors are then loaded with ``load_state_dict(strict=False,
assign=True)`` and compared bit-equal (see ``metadata["load"]``).

Two reconstruction traps worth knowing (both cost a full debugging round):
neither is discoverable from the checkpoint, and both silently destroy the
layer-17 hidden states the action head consumes.

1. ``latents_std`` sign.  The pinned diffusers commit that trained DiT4DiT
   (``3996788b``, see ``requirements.txt``) stores the *raw* ``latents_std`` on
   the pipeline, and the repo's extractor divides by it, i.e. training
   normalised the VAE latents as ``(z - mean) / std``.  diffusers 0.43 stores
   ``1 / latents_std`` there instead, so the attribute must be restored from
   ``vae.config`` (raw values) or every latent is scaled by ``std**2 ~ 8x``.
2. ``scheduler`` flow sigmas.  The checkpoint ships the Cosmos flow-matching
   scheduler (``prediction_type="flow_prediction"``, ``use_flow_sigmas=True``,
   ``num_train_timesteps=1000``).  Diffusers' default ``UniPCMultistepScheduler()``
   (``epsilon``) gives ``sigmas[0] = 157.4`` instead of ``1.0``, and that value
   becomes the timestep of the *future* latent frames in the single transformer
   pass that produces the hidden states -> out-of-distribution timestep
   embedding -> the policy emits saturated, jittery actions and never solves the
   task (measured: 30% of dims pinned at the dataset min/max, 5.3 m of eef travel
   in 300 steps without ever getting closer than 0.32 m to the object).

Preprocessing / postprocessing mirror ``examples/LIBERO/eval_files``
-------------------------------------------------------------------
``eval_libero.py`` + ``model2libero_interface.py`` of the DiT4DiT checkout:

* both cameras are rotated 180 deg (``[::-1, ::-1]``), resized to 224x224 with
  ``cv2.INTER_AREA`` and concatenated horizontally -> the 224x448 model input
  (this is what the checkpoint was trained on: ``obs: ["image_0"]``);
* proprio = ``[eef_pos(3), quat2axisangle(eef_quat)(3), gripper_qpos(2)]`` (8-D),
  then ``[sin(x), cos(x)]`` per dimension -> 16 dims (``state_dim``), no
  normalisation (matches ``Libero4in1DataConfig``'s ``StateActionSinCosTransform``);
* the 8-step chunk (``future_action_window_size=7``) is clipped to [-1, 1] and
  un-normalised with the checkpoint's ``dataset_statistics.json`` ``franka``
  min/max, action dims 0-5 masked-in, gripper (dim 6) already in [0, 1];
* the gripper is finally mapped to LIBERO env convention with the official
  ``1 - 2 * (open > 0.5)`` binarisation (dataset 1 = open -> env -1; 0 = close ->
  env +1), and the 6-D pose delta is fed to LIBERO's default **relative** OSC
  controller (``control_mode = "relative"``).

Environment knobs
-----------------
``DIT4DIT_ROOT``       repo checkout (default ``work/third_party/DiT4DiT``)
``DIT4DIT_TOKENIZER``  Qwen2.5-VL-7B tokenizer dir (default ``work/ckpt/qwen25-vl-7b-tokenizer``)
``DIT4DIT_TEXT_ENCODER`` ``cpu`` (default) or ``cuda`` — the 8.3B Qwen tower is
                       only needed once per unique instruction, so by default it
                       stays on the host and its prompt embeddings are cached
                       (in RAM, and optionally on disk via ``DIT4DIT_PROMPT_CACHE``).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

#: Native action chunk of the released LIBERO checkpoint
#: (``future_action_window_size + 1 = 8``).
NATIVE_CHUNK = 8
#: Training image resolution per camera (two cameras are concatenated to 224x448).
IMAGE_SIZE = 224
#: Diffusers prompt length used by ``Cosmos25FeatureExtractor``.
MAX_SEQUENCE_LENGTH = 512

_DEFAULT_ROOT = "/home/ubuntu/whj/work/third_party/DiT4DiT"
_DEFAULT_TOKENIZER = "/home/ubuntu/whj/work/ckpt/qwen25-vl-7b-tokenizer"
_PT_NAME = "pytorch_model.pt"
#: `flow_shift` of the released Cosmos-Predict2.5 flow-matching scheduler.  Only
#: `sigmas[0]` (= 1.0 for any shift) reaches the action branch (`num_inference_steps=1`
#: for the hidden capture), so this value only matters for future-video decoding.
_FLOW_SHIFT = 3.0


def quat2axisangle(quat: np.ndarray) -> np.ndarray:
    """Convert a quaternion ``(x, y, z, w)`` to an axis-angle vector (LIBERO)."""

    qw = float(quat[3])
    qw = max(-1.0, min(1.0, qw))
    denominator = math.sqrt(max(0.0, 1.0 - qw * qw))
    if math.isclose(denominator, 0.0, abs_tol=1e-9):
        return np.zeros(3, dtype=np.float64)
    return np.asarray(quat[:3], dtype=np.float64) * 2.0 * math.acos(qw) / denominator


def _resize(image: np.ndarray, size: int = IMAGE_SIZE) -> np.ndarray:
    """``cv2.resize(..., (size, size), interpolation=cv.INTER_AREA)`` with a PIL fallback."""

    try:
        import cv2  # noqa: PLC0415

        return cv2.resize(image, (size, size), interpolation=cv2.INTER_AREA)
    except Exception:  # noqa: BLE001 - cv2 is optional; stay numerically close
        from PIL import Image  # noqa: PLC0415

        out = Image.fromarray(np.asarray(image)).resize((size, size), Image.BOX)
        return np.asarray(out)


def _resolve_pt(checkpoint: str | os.PathLike[str]) -> Path:
    path = Path(str(checkpoint)).expanduser()
    if path.is_dir():
        for candidate in (path / "final_model" / _PT_NAME, path / _PT_NAME):
            if candidate.is_file():
                return candidate.resolve()
        raise FileNotFoundError(f"no {_PT_NAME} under {path}")
    if not path.is_file():
        raise FileNotFoundError(f"DiT4DiT checkpoint not found: {path}")
    return path.resolve()


class Dit4ditPolicy:
    """Expose a DiT4DiT LIBERO checkpoint through the runner protocol."""

    #: LIBERO's default relative OSC controller (delta EEF pose + gripper)
    control_mode = "relative"

    def __init__(
        self,
        checkpoint: str | os.PathLike[str],
        workspace: str | os.PathLike[str] | None = None,
        logger: Any | None = None,
    ) -> None:
        import torch  # noqa: PLC0415

        root = Path(
            workspace or os.environ.get("DIT4DIT_ROOT") or _DEFAULT_ROOT
        ).expanduser().resolve()
        if not (root / "DiT4DiT").is_dir():
            raise FileNotFoundError(
                f"DiT4DiT checkout not found at {root} (pass --workspace or DIT4DIT_ROOT)"
            )
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        pt = _resolve_pt(checkpoint)
        run_dir = pt.parents[1]
        tokenizer_dir = Path(
            os.environ.get("DIT4DIT_TOKENIZER") or _DEFAULT_TOKENIZER
        ).expanduser()
        if not (tokenizer_dir / "tokenizer.json").is_file():
            raise FileNotFoundError(
                f"Qwen2.5-VL-7B tokenizer not found at {tokenizer_dir} (DIT4DIT_TOKENIZER)"
            )

        started = time.time()
        self._torch = torch
        self._logger = logger
        self.checkpoint = str(pt)
        self.run_dir = str(run_dir)
        self.root = str(root)
        self.tokenizer_dir = str(tokenizer_dir)
        self.native_chunk = NATIVE_CHUNK
        self._seed = 0

        self._text_device = (
            os.environ.get("DIT4DIT_TEXT_ENCODER", "cpu").strip().lower() or "cpu"
        )
        if self._text_device not in ("cpu", "cuda"):
            raise ValueError("DIT4DIT_TEXT_ENCODER must be 'cpu' or 'cuda'")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._device = torch.device(device)

        model_config, norm_stats, load_report = _build_and_load(
            pt=pt, run_dir=run_dir, device=str(self._device), logger=logger
        )
        self.load_report = load_report
        self.model = model_config.pop("model")
        self.model_config = model_config
        self.cfg = self.model.config

        # ---- statistics / action space -----------------------------------
        key = "franka"
        stats = norm_stats.get(key) or next(iter(norm_stats.values()))
        self.norm_stats = stats
        self.unnorm_key = key
        action_stats = stats["action"]
        self._action_min = np.asarray(action_stats["min"], dtype=np.float64)
        self._action_max = np.asarray(action_stats["max"], dtype=np.float64)
        self._action_mask = np.asarray(
            action_stats.get("mask", np.ones_like(self._action_min, dtype=bool)),
            dtype=bool,
        )

        # ---- tokenizer + prompt-embedding cache ---------------------------
        from transformers import AutoTokenizer  # noqa: PLC0415

        self.tokenizer = AutoTokenizer.from_pretrained(
            str(tokenizer_dir), local_files_only=True, use_fast=True
        )
        self._prompt_cache: dict[str, "torch.Tensor"] = {}
        self._prompt_disk_cache = self._resolve_disk_cache()
        if self._prompt_disk_cache is not None:
            self._prompt_disk_cache.mkdir(parents=True, exist_ok=True)

        # ---- text-encoder device plumbing --------------------------------
        extractor = self.model.backbone_interface.extractor
        text_encoder = extractor.text_encoder
        text_device = (
            torch.device("cuda") if self._text_device == "cuda" else torch.device("cpu")
        )
        if next(text_encoder.parameters()).device != text_device:
            text_encoder.to(text_device)
        extractor.encode_prompt = self._make_encode_prompt(extractor)
        # `Cosmos25FeatureExtractor.device` is `next(self.parameters()).device`,
        # which is the *text encoder* (registered first).  When the 8.3B Qwen
        # tower lives on the host every latent must still be built on the GPU,
        # so pin the extractor's notion of "device" to the transformer.
        _override_extractor_device(extractor, self._device)
        # CRITICAL: the pinned diffusers commit that trained DiT4DiT stores the
        # *raw* `latents_std` on the pipeline, while 0.43 stores its reciprocal
        # (`1 / latents_std`).  The repo's extractor divides by this attribute,
        # i.e. training normalised the VAE latents as `(z - mean) / std`.  Handing
        # it 0.43's reciprocal would multiply by std (~2.8x) instead and the
        # action head would saturate, so the raw values are restored from the VAE
        # config (which is exactly what the pipeline did at training time).
        vae_config = self.model.backbone_interface.extractor.vae.config
        extractor.latents_mean = (
            torch.tensor(vae_config.latents_mean).view(1, int(vae_config.z_dim), 1, 1, 1)
            .float().to(self._device)
        )
        extractor.latents_std = (
            torch.tensor(vae_config.latents_std).view(1, int(vae_config.z_dim), 1, 1, 1)
            .float().to(self._device)
        )
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        self._action_stats: dict[str, Any] = {
            "calls": 0,
            "chunks": 0,
            "abs_mean_per_dim": [0.0] * 7,
            "gripper_open_frac": 0.0,
            "chunk_pos_norm_mean": 0.0,
            "chunk_rot_norm_mean": 0.0,
        }
        self.last_actions: np.ndarray | None = None

        self.metadata = {
            "policy": "dit4dit",
            "checkpoint": self.checkpoint,
            "workspace": self.root,
            "tokenizer": self.tokenizer_dir,
            "device": device,
            "torch": torch.__version__,
            "native_chunk": NATIVE_CHUNK,
            "action_horizon": int(self.model.future_action_window_size) + 1,
            "control_mode": self.control_mode,
            "action_representation": "delta_eef_pose+gripper (relative OSC)",
            "image_input": "224x448 (agentview || wrist, 180 deg flip)",
            "state_input": "8-D [eef_pos, axis-angle, gripper_qpos] -> sin/cos (16)",
            "flow_steps": int(getattr(self.model.action_model, "num_inference_timesteps", 0) or 0),
            "text_encoder_device": self._text_device,
            "load": self.load_report,
            "load_seconds": round(time.time() - started, 2),
        }
        self._log(f"DiT4DiT ready: {self.load_report}")

    # ---------------------------------------------------------------- loading
    def _resolve_disk_cache(self) -> Path | None:
        value = os.environ.get("DIT4DIT_PROMPT_CACHE", "").strip()
        if value.lower() in ("0", "off", "none"):
            return None
        if value:
            return Path(value).expanduser()
        return Path(self.run_dir) / "prompt_cache"

    def _make_encode_prompt(self, extractor: Any):
        """Drop-in replacement for ``Cosmos25FeatureExtractor.encode_prompt``.

        Reuses the repo's exact embedding recipe (chat template, per-layer
        mean/std normalisation, concatenation of layers 1..N) but caches the
        result per instruction and pins the text encoder to ``DIT4DIT_TEXT_ENCODER``.
        """

        import torch  # noqa: PLC0415

        text_encoder = extractor.text_encoder
        tokenizer = self.tokenizer
        text_device = next(text_encoder.parameters()).device
        cache = self._prompt_cache

        def encode_prompt(
            prompt: str | list[str],
            *,
            guidance_scale: float = 1.0,
            num_videos_per_prompt: int = 1,
            prompt_embeds: Any | None = None,
            negative_prompt_embeds: Any | None = None,
            max_sequence_length: int | None = None,
            device: Any | None = None,
            dtype: Any | None = None,
        ):
            _ = guidance_scale, prompt_embeds, negative_prompt_embeds
            target = device or self._device
            dtype = dtype or text_encoder.dtype
            max_len = max_sequence_length or MAX_SEQUENCE_LENGTH
            prompts = [prompt] if isinstance(prompt, str) else list(prompt)
            rows = []
            for text in prompts:
                embed = cache.get(text)
                if embed is None:
                    embed = self._prompt_embeds(
                        text, tokenizer=tokenizer, text_encoder=text_encoder,
                        text_device=text_device, max_len=max_len,
                    )
                    cache[text] = embed
                rows.append(embed)
            out = torch.cat(rows, dim=0) if len(rows) > 1 else rows[0]
            if num_videos_per_prompt > 1:
                out = out.repeat(num_videos_per_prompt, 1, 1)
            return out.to(device=target, dtype=dtype), None

        return encode_prompt

    def _prompt_embeds(
        self,
        text: str,
        *,
        tokenizer: Any,
        text_encoder: Any,
        text_device: Any,
        max_len: int,
    ):
        import torch  # noqa: PLC0415

        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
        disk = self._prompt_disk_cache / f"{digest}.npz" if self._prompt_disk_cache else None
        if disk is not None and disk.is_file():
            payload = np.load(disk)
            if str(payload["text"]) == text:
                stored = payload["embed"]
                tensor = torch.from_numpy(stored)
                if tensor.dtype == torch.int16:  # bf16 bits (exact, 102 MB)
                    tensor = tensor.view(torch.bfloat16)
                return tensor.to(text_device)

        conversations = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": "You are a helpful assistant who will provide prompts to an image generator.",
                    }
                ],
            },
            {"role": "user", "content": [{"type": "text", "text": text}]},
        ]
        ids = tokenizer.apply_chat_template(
            conversations,
            tokenize=True,
            add_generation_prompt=False,
            add_vision_id=False,
            max_length=max_len,
            truncation=True,
            padding="max_length",
        )
        if not isinstance(ids, list):
            ids = ids["input_ids"]
        input_ids = torch.LongTensor(list(ids)).unsqueeze(0).to(text_device)
        started = time.time()
        with torch.no_grad():
            outputs = text_encoder(input_ids, output_hidden_states=True)
            hidden_states = outputs.hidden_states
            normalized = []
            for layer in hidden_states[1:]:
                normalized.append(
                    (layer - layer.mean(dim=-1, keepdim=True))
                    / (layer.std(dim=-1, keepdim=True) + 1e-8)
                )
            embed = torch.cat(normalized, dim=-1).detach()
        if disk is not None:
            try:
                # store the bf16 bits as int16: exact round-trip at half the size
                np.savez(
                    disk,
                    text=np.asarray(text),
                    embed=embed.to(torch.bfloat16).cpu().view(torch.int16).numpy(),
                )
            except Exception:  # noqa: BLE001 - cache is best-effort
                pass
        self._log(
            f"prompt embeds for {text!r} in {time.time() - started:.1f}s "
            f"({tuple(embed.shape)}, {text_device})"
        )
        return embed

    # ------------------------------------------------------------- inference
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
        self._seed = int(seed)

    def _preprocess(self, observation: Mapping[str, Any], instruction: str) -> dict[str, Any]:
        primary = np.ascontiguousarray(np.asarray(observation["agentview_image"])[::-1, ::-1])
        wrist = observation.get("robot0_eye_in_hand_image")
        wrist = (
            np.ascontiguousarray(np.asarray(wrist)[::-1, ::-1])
            if wrist is not None
            else np.zeros_like(primary)
        )
        # model2libero_interface(): resize each view, then concat width-wise.
        concat = np.concatenate([_resize(primary), _resize(wrist)], axis=1)
        state = np.concatenate(
            [
                np.asarray(observation["robot0_eef_pos"], dtype=np.float64),
                quat2axisangle(
                    np.asarray(observation["robot0_eef_quat"], dtype=np.float64)
                ),
                np.asarray(observation["robot0_gripper_qpos"], dtype=np.float64),
            ]
        )
        sin_state = np.sin(state)
        cos_state = np.cos(state)
        packed = np.stack([sin_state, cos_state], axis=-1).reshape(1, -1)
        return {
            "image": [concat],
            "lang": instruction,
            "state": packed.astype(np.float32),
        }

    def _postprocess(self, normalized: np.ndarray) -> np.ndarray:
        """Repo postprocessing: clip -> gripper threshold -> min/max un-normalise."""

        actions = np.clip(np.asarray(normalized, dtype=np.float64)[:, :7], -1.0, 1.0)
        actions[:, 6] = np.where(actions[:, 6] < 0.5, 0.0, 1.0)
        low, high = self._action_min[:7], self._action_max[:7]
        actions = np.where(
            self._action_mask[:7],
            0.5 * (actions + 1.0) * (high - low) + low,
            actions,
        )
        # eval_libero.py::_binarize_gripper_open
        actions[:, 6] = 1.0 - 2.0 * (actions[:, 6] > 0.5)
        return actions

    def predict_chunk(
        self, observation: Mapping[str, Any], instruction: str
    ) -> np.ndarray:
        import torch  # noqa: PLC0415

        example = self._preprocess(observation, instruction)
        with torch.inference_mode():
            out = self.model.predict_action(examples=[example])
        normalized = np.asarray(out["normalized_actions"])[0]
        actions = self._postprocess(normalized)
        if actions.ndim != 2 or actions.shape[1] != 7:
            raise ValueError(f"DiT4DiT returned invalid actions: {actions.shape}")

        stats = self._action_stats
        stats["calls"] += 1
        stats["chunks"] += actions.shape[0]
        stats["abs_mean_per_dim"] = [
            (old * (stats["calls"] - 1) + float(np.abs(actions[:, dim]).mean())) / stats["calls"]
            for dim, old in enumerate(stats["abs_mean_per_dim"])
        ]
        open_frac = float((actions[:, 6] < 0).mean())
        stats["gripper_open_frac"] = (
            (stats["gripper_open_frac"] * (stats["calls"] - 1) + open_frac) / stats["calls"]
        )
        stats["chunk_pos_norm_mean"] = float(
            np.linalg.norm(actions[:, :3], axis=1).mean()
        )
        stats["chunk_rot_norm_mean"] = float(
            np.linalg.norm(actions[:, 3:6], axis=1).mean()
        )
        self.last_actions = actions
        if stats["calls"] == 1 or stats["calls"] % 10 == 0:
            self._log(
                f"chunk #{stats['calls']}: pos|a|={np.abs(actions[:, :3]).mean():.3f} "
                f"rot|a|={np.abs(actions[:, 3:6]).mean():.3f} "
                f"gripper_open={float((actions[:, 6] < 0).mean()):.2f} "
                f"clamp={float((np.abs(actions) >= 0.9374).mean()):.2f}"
            )
        return actions

    # ------------------------------------------------------ §8.4 aliases
    def reset(self, seed: int) -> None:
        self.reset_episode(seed)

    def predict(self, obs: Mapping[str, Any], instruction: str) -> np.ndarray:
        return self.predict_chunk(obs, instruction)

    # ---------------------------------------------------------------- utils
    def _log(self, message: str) -> None:
        logger = self._logger
        if logger is not None:
            try:
                logger(message)
                return
            except Exception:  # noqa: BLE001
                pass
        print(f"[dit4dit] {message}", flush=True)


def _override_extractor_device(extractor: Any, device: Any) -> None:
    """Make ``extractor.device`` report the transformer's device, not the text encoder's."""

    import torch  # noqa: PLC0415

    target = torch.device(device)
    base = type(extractor)

    if getattr(base, "_dit4dit_device_override", False):
        extractor._dit4dit_target_device = target
        return

    class _DevicePinnedExtractor(base):  # type: ignore[misc, valid-type]
        _dit4dit_device_override = True

        @property
        def device(self):
            return self._dit4dit_target_device

    extractor.__class__ = _DevicePinnedExtractor
    extractor._dit4dit_target_device = target


def _read_run_metadata(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    import yaml  # noqa: PLC0415

    config_path = run_dir / "config.yaml"
    stats_path = run_dir / "dataset_statistics.json"
    if not config_path.is_file():
        raise FileNotFoundError(f"missing DiT4DiT config.yaml: {config_path}")
    if not stats_path.is_file():
        raise FileNotFoundError(f"missing DiT4DiT dataset_statistics.json: {stats_path}")
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    with stats_path.open(encoding="utf-8") as handle:
        stats = json.load(handle)
    return config, stats


def _build_and_load(
    *, pt: Path, run_dir: Path, device: str, logger: Any | None
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Rebuild the DiT4DiT pipeline from checkpoint tensor shapes and load it."""

    import torch  # noqa: PLC0415

    from diffusers import (  # noqa: PLC0415
        AutoencoderKLWan,
        Cosmos2_5_PredictBasePipeline,
        CosmosTransformer3DModel,
        UniPCMultistepScheduler,
    )
    from transformers import (  # noqa: PLC0415
        Qwen2_5_VLConfig,
        Qwen2_5_VLForConditionalGeneration,
    )

    from DiT4DiT.model.framework.__init__ import build_framework  # noqa: PLC0415
    from DiT4DiT.model.framework.share_tools import dict_to_namespace  # noqa: PLC0415
    from DiT4DiT.model.modules.vlm.Cosmos25 import (  # noqa: PLC0415
        _DefaultDummySafetyChecker,
    )

    started = time.time()
    timings: dict[str, float] = {}
    previous_dtype = torch.get_default_dtype()
    torch.set_default_dtype(torch.bfloat16)
    try:
        state_dict = torch.load(str(pt), map_location="cpu", mmap=True, weights_only=True)
        timings["ckpt_mmap"] = round(time.time() - started, 1)

        transformer_cfg = dict(
            in_channels=17,
            out_channels=16,
            num_attention_heads=16,
            attention_head_dim=128,
            num_layers=28,
            mlp_ratio=4.0,
            text_embed_dim=1024,
            adaln_lora_dim=256,
            max_size=(128, 240, 240),
            patch_size=(1, 2, 2),
            rope_scale=(2.0, 1.0, 1.0),
            concat_padding_mask=True,
            extra_pos_embed_type=None,
            use_crossattn_projection=True,
            crossattn_proj_in_channels=100352,
            encoder_hidden_states_channels=1024,
        )
        text_cfg = dict(
            hidden_size=3584,
            intermediate_size=18944,
            num_hidden_layers=28,
            num_attention_heads=28,
            num_key_value_heads=4,
            head_dim=128,
            vocab_size=152064,
            rms_norm_eps=1e-6,
            rope_theta=1000000.0,
            max_position_embeddings=128000,
            hidden_act="silu",
            attention_bias=True,
            tie_word_embeddings=False,
            rope_scaling={
                "type": "default",
                "mrope_section": [16, 24, 24],
                "mrope_interleaved": True,
            },
        )
        vision_cfg = dict(
            depth=32,
            hidden_size=1280,
            num_heads=16,
            in_channels=3,
            patch_size=14,
            spatial_merge_size=2,
            temporal_patch_size=2,
            intermediate_size=3420,
            hidden_act="silu",
            out_hidden_size=3584,
            window_size=112,
            fullatt_block_indexes=[7, 15, 23, 31],
        )
        qwen_cfg = Qwen2_5_VLConfig(
            text_config=text_cfg,
            vision_config=vision_cfg,
            image_token_id=151655,
            video_token_id=151656,
            vision_start_token_id=151652,
            vision_end_token_id=151653,
            tie_word_embeddings=False,
        )

        # Built with real (bf16) storage rather than on the `meta` device: the
        # Qwen rotary embedding and the Cosmos 3D RoPE keep *non-persistent*
        # buffers that `load_state_dict(assign=True)` cannot replace, so a meta
        # build leaves `inv_freq` dataless and the first forward crashes.
        t_build = time.time()
        transformer = CosmosTransformer3DModel(**transformer_cfg)
        text_encoder = Qwen2_5_VLForConditionalGeneration(qwen_cfg)
        # Wan2.1 layout == diffusers defaults; the checkpoint keys line up 1:1
        # (`decoder.up_blocks.*.upsamplers.0.*`), so no remapping is needed.
        vae = AutoencoderKLWan(
            base_dim=96,
            z_dim=16,
            dim_mult=[1, 2, 4, 4],
            num_res_blocks=2,
            attn_scales=[],
            temperal_downsample=[False, True, True],
            dropout=0.0,
            is_residual=False,
            in_channels=3,
            out_channels=3,
            patch_size=None,
            scale_factor_temporal=4,
            scale_factor_spatial=8,
        )

        pipeline = Cosmos2_5_PredictBasePipeline(
            text_encoder=text_encoder,
            tokenizer=None,
            transformer=transformer,
            vae=vae,
            # CRITICAL: the checkpoint ships the Cosmos flow-matching scheduler
            # (`prediction_type="flow_prediction"`, `use_flow_sigmas=True`), so
            # `sigmas[0]` is 1.0 and the future latent frames enter the
            # transformer with `timestep ~= 1`.  Diffusers' default UniPC
            # (`epsilon`, no flow sigmas) yields `sigmas[0] = 157.4`, an
            # out-of-distribution timestep that corrupts the layer-17 hidden
            # captured for the action head.
            scheduler=UniPCMultistepScheduler(
                prediction_type="flow_prediction",
                use_flow_sigmas=True,
                flow_shift=_FLOW_SHIFT,
                num_train_timesteps=1000,
            ),
            safety_checker=_DefaultDummySafetyChecker(),
        )
        # Hand the locally assembled pipeline to the unmodified repo loader.
        Cosmos2_5_PredictBasePipeline.from_pretrained = classmethod(
            lambda cls, *args, **kwargs: pipeline
        )

        config, norm_stats = _read_run_metadata(run_dir)
        model = build_framework(cfg=dict_to_namespace(config))
        params = sum(p.numel() for p in model.parameters())
        timings["component_build"] = round(time.time() - t_build, 1)
    finally:
        torch.set_default_dtype(previous_dtype)

    t_load = time.time()
    result = model.load_state_dict(state_dict, strict=False, assign=True)
    timings["assign_load"] = round(time.time() - t_load, 1)
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    # bit-exactness audit (cheap: bf16 tensor equality on the assigned views)
    t_audit = time.time()
    model_sd = model.state_dict()
    not_equal: list[str] = []
    for key, tensor in model_sd.items():
        original = state_dict.get(key)
        if original is None:
            continue
        try:
            if not torch.equal(tensor, original):
                not_equal.append(key)
        except Exception:  # noqa: BLE001 - shape/stride mismatch
            not_equal.append(key)
    counts: dict[str, list[int]] = {}
    for key in model_sd:
        prefix = key.split(".")[0]
        if prefix == "backbone_interface":
            parts = key.split(".")
            prefix = ".".join(parts[:3])
        bucket = counts.setdefault(prefix, [0, 0])
        bucket[0] += 1
        if key in state_dict:
            bucket[1] += 1
    timings["bit_equal_audit"] = round(time.time() - t_audit, 1)
    report = {
        "params_b": round(params / 1e9, 3),
        "checkpoint_tensors": len(state_dict),
        "model_tensors": len(model_sd),
        "missing": len(result.missing_keys),
        "unexpected": len(result.unexpected_keys),
        "not_bit_equal": len(not_equal),
        "not_bit_equal_sample": not_equal[:8],
        "groups": {k: {"model": v[0], "loaded": v[1]} for k, v in sorted(counts.items())},
        "load_seconds": round(time.time() - started, 1),
        "timings_seconds": timings,
    }
    if result.missing_keys:
        report["missing_sample"] = list(result.missing_keys)[:8]
    if result.unexpected_keys:
        report["unexpected_sample"] = list(result.unexpected_keys)[:8]

    model = model.eval()
    if device.startswith("cuda"):
        t_gpu = time.time()
        model.backbone_interface.extractor.transformer.to(device)
        model.backbone_interface.extractor.vae.to(device)
        model.action_model.to(device)
        torch.cuda.empty_cache()
        report["timings_seconds"]["to_gpu"] = round(time.time() - t_gpu, 1)
    del state_dict
    config_out = {"model": model}
    config_out.update(config)
    return config_out, norm_stats, report
