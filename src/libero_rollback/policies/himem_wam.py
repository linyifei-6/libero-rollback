"""HiMem-WAM adapter for the LIBERO-Rollback runner.

Wraps the released LIBERO checkpoint (``himem-wam_libero.pt``: MoT video+action
experts, 6.7B params, bf16, step=30608) behind the runner's two-method adapter
contract (README §8.4)::

    reset_episode(seed)
    predict_chunk(observation, instruction) -> np.ndarray (T, 7)

The checkpoint is a *Wan2.2-style* model: it needs the DiffSynth-converted
Wan2.2 VAE and a UMT5-XXL text encoder.  Both files ship inside the FastWAM
checkpoint mirror (``work/ckpt/fastwam``) and their ``hash_model_file()`` values
are exactly the ones ``himem_wam/models/wan22/helpers/loader.py`` expects
(``e1de6c02cdac79f8b739f4d3698cd216`` for the VAE, ``9c8818c2cbea55eca56c7b447df170da``
for UMT5), so no checkpoint conversion is required:

* ``model.vae_pretrained_path`` -> ``Wan2.2_VAE.safetensors``;
* the text encoder is attached by this adapter from
  ``models_t5_umt5-xxl-enc-bf16.safetensors`` + the ``google/umt5-xxl``
  tokenizer, and each instruction's context is encoded once and cached.
  ``model.load_text_encoder`` stays **false**: the vendored ``ModelConfig``
  resolves the tokenizer to a *list* of files, which
  ``AutoTokenizer.from_pretrained`` cannot consume.  ``HIMEM_WAM_TEXT_ENCODER``
  selects where the 11 GB encoder lives (``cpu`` default, ``cuda`` to keep it
  resident on the GPU).

Preprocessing/postprocessing mirrors the official evaluator
(``experiments/libero/eval_libero_single.py``) so numbers stay comparable:

* both cameras are rotated 180 deg, centre-cropped/resized to 224x224 per view
  and concatenated horizontally into the 224x448 model input;
* proprio = ``[eef_pos(3), quat2axisangle(3), gripper_qpos(2)]`` (8-D),
  min/max-normalised with the checkpoint's ``*_dataset_stats.json``;
* action = **delta** end-effector pose (6) + gripper (1).  The dataset stats
  show ``|dxyz| <= 0.9375`` and ``|daxisangle| <= 0.375`` about zero (absolute
  poses would cluster at the table height), and the training processor declares
  ``delta_action_dim_mask = [true x6, false]``; the adapter therefore uses
  LIBERO's default relative OSC controller (``control_mode = "relative"``).
* the gripper is already in env convention (-1 open / +1 close) per the stats
  (``global_min=-1, global_max=1``), so it is only clipped and binarised
  (``EVALUATION.binarize_gripper: true``), exactly like the official eval.

Only the inference-time helpers of the official script are copied here (with
its own preprocessing constants); the adapter deliberately does not import
``experiments.libero`` because that pulls the training dataset stack (pyav,
lerobot) which the rollback runner does not need.

The hydra config of the official evaluator cannot be composed as shipped:
``configs/libero/eval.yaml`` declares ``defaults: - train``, which Hydra
resolves to the missing ``libero/train``.  The adapter composes the same file
from a temporary symlink mirror where it sits at the config root (``eval.yaml``
next to ``train.yaml``), which is what the release intended; the checkout is
left untouched.

The model stack is imported lazily so the static layer can load the registry
without torch.  Paths are resolved from ``--workspace`` / ``HIMEM_WAM_ROOT``
(the HiMem-WAM checkout) and ``HIMEM_WAM_ASSETS`` (the FastWAM mirror holding
the VAE, the UMT5 weights and the tokenizer).
"""

from __future__ import annotations

import csv
import math
import os
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

_DEFAULT_ROOT = "/home/ubuntu/whj/work/third_party/HiMem-WAM"
_DEFAULT_ASSETS = "/home/ubuntu/whj/work/ckpt/fastwam"
_VAE_FILE = "Wan2.2_VAE.safetensors"
_TEXT_ENCODER_FILE = "models_t5_umt5-xxl-enc-bf16.safetensors"
_TOKENIZER_DIR = Path("google") / "umt5-xxl"
#: Same prompt template the training data / official eval use.
DEFAULT_PROMPT = (
    "A video recorded from a robot's point of view executing the following "
    "instruction: {task}"
)
_MATRIX = (
    Path(__file__).resolve().parents[3]
    / "dataset"
    / "matrices"
    / "libero-rollback"
    / "completion-rollback.csv"
)
_SUITE_KEYS = {
    "spatial": "libero_spatial",
    "object": "libero_object",
    "goal": "libero_goal",
    "l10": "libero_10",
}


def quat2axisangle(quat: np.ndarray) -> np.ndarray:
    """``(x, y, z, w)`` quaternion -> axis-angle (robosuite / LIBERO helper)."""

    quat = np.asarray(quat, dtype=np.float64).copy()
    quat[3] = float(np.clip(quat[3], -1.0, 1.0))
    den = math.sqrt(max(1.0 - quat[3] * quat[3], 0.0))
    if math.isclose(den, 0.0):
        return np.zeros(3)
    return (quat[:3] * 2.0 * math.acos(quat[3])) / den


def extract_sim_state(observation: Mapping[str, Any]) -> np.ndarray:
    """8-D proprio: ``[eef_pos, axis-angle(eef_quat), gripper_qpos]``."""

    return np.concatenate(
        (
            np.asarray(observation["robot0_eef_pos"], dtype=np.float64),
            quat2axisangle(observation["robot0_eef_quat"]),
            np.asarray(observation["robot0_gripper_qpos"], dtype=np.float64),
        )
    ).astype(np.float32)


def _center_crop_resize(image: np.ndarray, width: int, height: int) -> np.ndarray:
    from PIL import Image  # noqa: PLC0415

    pil_image = Image.fromarray(image)
    src_w, src_h = pil_image.size
    scale = max(width / src_w, height / src_h)
    resized = pil_image.resize(
        (round(src_w * scale), round(src_h * scale)), resample=Image.BILINEAR
    )
    rw, rh = resized.size
    left = max((rw - width) // 2, 0)
    top = max((rh - height) // 2, 0)
    cropped = resized.crop((left, top, left + width, top + height))
    return np.asarray(cropped, dtype=np.uint8)


def _config_mirror(root: Path) -> str:
    """Build a hydra config dir that composes the official eval config.

    ``configs/libero/eval.yaml``'s ``defaults: - train`` is resolved relative to
    the config's group, so Hydra looks for ``libero/train.yaml`` - a file the
    release does not ship.  Mirroring the tree with ``eval.yaml`` at the root
    restores the intended layout without editing the checkout.
    """

    import tempfile

    mirror = Path(tempfile.mkdtemp(prefix="himem-wam-config-"))
    cfg_root = root / "configs"
    for name in ("train.yaml", "data", "model", "task"):
        os.symlink(cfg_root / name, mirror / name)
    os.symlink(cfg_root / "libero" / "eval.yaml", mirror / "eval.yaml")
    return str(mirror)


class HiMemWamPolicy:
    """Expose a HiMem-WAM LIBERO checkpoint through the runner protocol."""

    #: LIBERO's default relative OSC controller (delta EEF pose + gripper)
    control_mode = "relative"

    def __init__(
        self,
        checkpoint: str | os.PathLike[str],
        workspace: str | os.PathLike[str] | None = None,
        logger: Any | None = None,
    ) -> None:
        import torch  # noqa: PLC0415

        root = Path(workspace or os.environ.get("HIMEM_WAM_ROOT") or _DEFAULT_ROOT).resolve()
        if not (root / "himem_wam").is_dir():
            raise ValueError(
                f"HiMem-WAM checkout not found: {root} (pass --workspace or HIMEM_WAM_ROOT)"
            )
        assets = Path(os.environ.get("HIMEM_WAM_ASSETS") or _DEFAULT_ASSETS).resolve()
        vae_path = assets / _VAE_FILE
        text_path = assets / _TEXT_ENCODER_FILE
        tokenizer_dir = assets / _TOKENIZER_DIR
        for path in (vae_path, text_path):
            if not path.is_file():
                raise FileNotFoundError(f"HiMem-WAM Wan2.2 component not found: {path}")
        if not (tokenizer_dir / "tokenizer.json").is_file():
            raise FileNotFoundError(f"UMT5 tokenizer not found: {tokenizer_dir}")

        ckpt = Path(str(checkpoint)).expanduser().resolve()
        if not ckpt.is_file():
            raise FileNotFoundError(f"HiMem-WAM checkpoint not found: {ckpt}")
        stats_path = ckpt.with_name(f"{ckpt.stem}_dataset_stats.json")
        if not stats_path.is_file():
            stats_path = ckpt.parent / "dataset_stats.json"
        if not stats_path.is_file():
            raise FileNotFoundError(
                f"dataset stats not found next to the checkpoint: {ckpt.name}"
            )

        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        from hydra import compose, initialize_config_dir  # noqa: PLC0415
        from hydra.utils import instantiate  # noqa: PLC0415

        from himem_wam.datasets.lerobot.utils.normalizer import (  # noqa: PLC0415
            load_dataset_stats_from_json,
        )
        from himem_wam.models.wan22.helpers.loader import (  # noqa: PLC0415
            _load_registered_model,
        )
        from himem_wam.models.wan22.wan_video_text_encoder import (  # noqa: PLC0415
            HuggingfaceTokenizer,
        )
        from himem_wam.utils.config_resolvers import register_default_resolvers  # noqa: PLC0415

        register_default_resolvers()
        started = time.time()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16
        with initialize_config_dir(config_dir=_config_mirror(root), version_base="1.3"):
            cfg = compose(
                config_name="eval",
                overrides=[
                    "model.load_text_encoder=false",
                    "model.skip_dit_load_from_pretrain=true",
                    f"ckpt={ckpt}",
                    f"EVALUATION.dataset_stats_path={stats_path}",
                    f"model.vae_pretrained_path={vae_path}",
                    f"model.text_encoder_pretrained_path={text_path}",
                ],
            )

        model = instantiate(cfg.model, model_dtype=dtype, device=device)
        # ``load_checkpoint`` returns the raw 12 GB payload; do not keep it
        # alive on the GPU (that alone is ~12 GB of VRAM).
        model.load_checkpoint(str(ckpt))
        if torch.cuda.is_available():
            # The 12 GB checkpoint payload was materialised on the device; hand
            # the freed blocks back to the driver so co-resident policies fit.
            torch.cuda.empty_cache()
        model = model.to(device).eval()

        # ---- UMT5 text encoder (prompt context) -------------------------
        self._text_device = os.environ.get("HIMEM_WAM_TEXT_ENCODER", "cpu").lower()
        if self._text_device not in ("cpu", "cuda"):
            raise ValueError("HIMEM_WAM_TEXT_ENCODER must be 'cpu' or 'cuda'")
        self._text_encoder = _load_registered_model(
            str(text_path),
            "wan_video_text_encoder",
            torch_dtype=dtype,
            device=self._text_device,
        ).eval()
        self._tokenizer = HuggingfaceTokenizer(
            name=str(tokenizer_dir),
            seq_len=int(cfg.model.tokenizer_max_len),
            clean="whitespace",
        )
        self._context_cache: dict[str, tuple[Any, Any]] = {}

        dataset_stats = load_dataset_stats_from_json(str(stats_path))
        processor = instantiate(cfg.data.train.processor).eval()
        processor.set_normalizer_from_stats(dataset_stats)

        self._torch = torch
        self._logger = logger
        self.cfg = cfg
        self.checkpoint = str(ckpt)
        self.root = str(root)
        self.assets = str(assets)
        self.model = model
        self.processor = processor
        self.action_horizon = int(cfg.data.train.num_frames) - 1
        self.chunk_size = self.action_horizon
        self.input_h = int(cfg.data.train.video_size[0])
        self.input_w = int(cfg.data.train.video_size[1])
        self.num_inference_steps = int(cfg.EVALUATION.num_inference_steps)
        self.binarize_gripper = bool(cfg.EVALUATION.get("binarize_gripper", False))
        self._instruction_map = self._build_instruction_map()
        self.metadata = {
            "policy": "himem",
            "checkpoint": str(ckpt),
            "workspace": str(root),
            "assets": str(assets),
            "device": device,
            "torch": torch.__version__,
            "native_chunk": self.action_horizon,
            "action_horizon": self.action_horizon,
            "num_inference_steps": self.num_inference_steps,
            "control_mode": self.control_mode,
            "action_representation": "delta_eef_pose+gripper",
            "binarize_gripper": self.binarize_gripper,
            "image_input": f"{self.input_h}x{self.input_w} (2 cameras, 180 deg flip)",
            "text_encoder_device": self._text_device,
            "vae": str(vae_path),
            "text_encoder": str(text_path),
            "load_seconds": round(time.time() - started, 2),
        }

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _build_instruction_map() -> dict[str, str]:
        """Map matrix instructions onto the canonical LIBERO task language.

        The checkpoints are trained on ``task.language`` from the LIBERO
        benchmark; the rollback matrix paraphrases the same BDDL task.  Keyed by
        (suite, bddl_name) so both spellings of the same task collapse.
        """
        try:
            from libero.libero import benchmark  # noqa: PLC0415

            bddl_to_language: dict[tuple[str, str], str] = {}
            registry = benchmark.get_benchmark_dict()
            for suite_short, suite_key in _SUITE_KEYS.items():
                suite = registry[suite_key]()
                for index in range(suite.n_tasks):
                    task = suite.get_task(index)
                    bddl_to_language[(suite_short, task.name)] = task.language
        except Exception:  # noqa: BLE001 - LIBERO may be absent in the static layer
            return {}

        mapping: dict[str, str] = {}
        if not _MATRIX.is_file():
            return mapping
        with _MATRIX.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                language = bddl_to_language.get((row["suite"], row["bddl_name"]))
                if language:
                    mapping[row["instruction"]] = language
        return mapping

    def _prompt_context(self, task_description: str) -> tuple[Any, Any]:
        """UMT5 context for one instruction, cached (official ``encode_prompt``)."""
        import torch  # noqa: PLC0415

        prompt = DEFAULT_PROMPT.format(task=task_description)
        cached = self._context_cache.get(prompt)
        if cached is not None:
            return cached

        ids, mask = self._tokenizer(prompt, return_mask=True, add_special_tokens=True)
        ids = ids.to(self._text_device)
        mask = mask.to(self._text_device, dtype=torch.bool)
        with torch.no_grad():
            context = self._text_encoder(ids, mask)
        # Same post-processing as ``HiMemWAM.encode_prompt``: zero the padding
        # tail (it stays visible to cross-attention) and use an all-ones mask.
        seq_lens = mask.gt(0).sum(dim=1).long()
        for index, length in enumerate(seq_lens):
            context[index, int(length) :] = 0
        context = context.detach().to("cpu")
        mask = torch.ones_like(mask).to("cpu")
        self._context_cache[prompt] = (context, mask)
        return context, mask

    def _normalize_proprio(self, proprio: np.ndarray):
        import torch  # noqa: PLC0415

        state_meta = self.processor.shape_meta["state"]
        if len(state_meta) != 1:
            raise ValueError("LIBERO eval expects a single merged state key")
        state_key = state_meta[0]["key"]
        batch = {
            "state": {
                state_key: torch.as_tensor(proprio, dtype=torch.float32).unsqueeze(0)
            }
        }
        batch = self.processor.action_state_transform(batch)
        batch = self.processor.normalizer.forward(batch)
        return batch["state"][state_key]

    def _model_input(self, observation: Mapping[str, Any]):
        """Observation -> (image [1,3,H,W], proprio [1,8]) for ``infer_action``."""
        import torch  # noqa: PLC0415

        torch_dtype = self.model.torch_dtype
        device = str(self.model.device)
        images = {
            "image": np.ascontiguousarray(observation["agentview_image"][::-1, ::-1]),
            "wrist_image": np.ascontiguousarray(
                observation["robot0_eye_in_hand_image"][::-1, ::-1]
            ),
        }
        image_meta = self.processor.shape_meta["images"]
        if len(image_meta) < int(self.processor.num_output_cameras):
            raise ValueError(
                f"shape_meta.images has {len(image_meta)} entries, "
                f"but num_output_cameras={self.processor.num_output_cameras}"
            )

        def to_hw(meta: dict, camera_idx: int) -> tuple[int, int]:
            shape = meta["shape"]
            if len(shape) != 3:
                raise ValueError(
                    f"shape_meta.images[{camera_idx}].shape must be [C,H,W], got {shape}"
                )
            return int(shape[1]), int(shape[2])

        concatenation = self.cfg.data.train.get("concat_multi_camera", "horizontal")
        num_cameras = int(self.processor.num_output_cameras)
        if num_cameras == 1:
            primary_h, primary_w = to_hw(image_meta[0], camera_idx=0)
            rgb = _center_crop_resize(images["image"], width=primary_w, height=primary_h)
        elif num_cameras == 2:
            primary_h, primary_w = to_hw(image_meta[0], camera_idx=0)
            wrist_h, wrist_w = to_hw(image_meta[1], camera_idx=1)
            primary = _center_crop_resize(images["image"], width=primary_w, height=primary_h)
            wrist = _center_crop_resize(images["wrist_image"], width=wrist_w, height=wrist_h)
            if concatenation == "horizontal":
                rgb = np.concatenate([primary, wrist], axis=1)
            elif concatenation == "vertical":
                rgb = np.concatenate([primary, wrist], axis=0)
            else:
                raise ValueError(f"Invalid concat_multi_camera: {concatenation}")
        else:
            raise ValueError(
                f"LIBERO eval supports num_output_cameras in [1, 2], got {num_cameras}"
            )

        actual_h, actual_w = int(rgb.shape[0]), int(rgb.shape[1])
        if (actual_h, actual_w) != (self.input_h, self.input_w):
            raise ValueError(
                "Input image size mismatch after per-camera resize + concat: "
                f"got (H,W)=({actual_h},{actual_w}), expected "
                f"({self.input_h},{self.input_w})"
            )

        image = torch.tensor(rgb).permute(2, 0, 1).unsqueeze(0).to(
            device=device, dtype=torch_dtype
        )
        image = image * (2.0 / 255.0) - 1.0
        proprio = self._normalize_proprio(extract_sim_state(observation))
        return image, proprio

    def _denormalize_action(self, action):
        import torch  # noqa: PLC0415

        if action.ndim == 2:
            action = action.unsqueeze(0)
        if action.ndim != 3:
            raise ValueError(f"Expected action tensor [B, T, D], got {tuple(action.shape)}")
        action_meta = self.processor.shape_meta["action"]
        if len(action_meta) != 1:
            raise ValueError("LIBERO eval expects a single merged action key")
        action_key = action_meta[0]["key"]
        normalizer = self.processor.normalizer.normalizers["action"][action_key]
        denorm = normalizer.backward(action.to(dtype=torch.float32, device="cpu"))
        return denorm.numpy()

    def _postprocess_gripper(self, action: np.ndarray) -> np.ndarray:
        """Clip/binarise the gripper exactly like the official evaluator."""
        action = action.copy()
        action_meta = self.processor.shape_meta["action"]
        action_key = action_meta[0]["key"]
        stats = self.processor.normalizer.normalizers["action"][action_key].get_stats()
        action_min = np.asarray(stats["min"], dtype=np.float32)
        action_max = np.asarray(stats["max"], dtype=np.float32)
        gripper_min, gripper_max = float(action_min[-1]), float(action_max[-1])
        if gripper_min < -0.5 and gripper_max > 0.5:
            # training action already follows the env convention (-1 open/+1 close)
            action[..., -1] = np.clip(action[..., -1], -1.0, 1.0)
        elif gripper_min >= -0.05 and gripper_max <= 1.05:
            action[..., -1] = action[..., -1] * 2 - 1
            action[..., -1] = action[..., -1] * -1.0
        else:
            action[..., -1] = np.clip(action[..., -1], -1.0, 1.0)
        if self.binarize_gripper:
            action[..., -1] = np.where(action[..., -1] >= 0.0, 1.0, -1.0)
        return action

    # -------------------------------------------------------------- interface
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
        torch = self._torch
        language = self._instruction_map.get(instruction, instruction)
        context, context_mask = self._prompt_context(language)
        dtype = self.model.torch_dtype
        context = context.to(device=self.model.device, dtype=dtype)
        context_mask = context_mask.to(device=self.model.device, dtype=torch.bool)

        image, proprio = self._model_input(observation)
        with torch.no_grad():
            prediction = self.model.infer_action(
                prompt=None,
                input_image=image,
                action_horizon=self.action_horizon,
                proprio=proprio,
                context=context,
                context_mask=context_mask,
                negative_prompt="",
                text_cfg_scale=float(self.cfg.EVALUATION.get("text_cfg_scale", 1.0)),
                num_inference_steps=self.num_inference_steps,
                sigma_shift=None,
                seed=None,
                rand_device="cpu",
                tiled=False,
            )

        action = self._denormalize_action(prediction["action"])[0]
        action = self._postprocess_gripper(action)
        action = np.asarray(action, dtype=np.float64)
        if action.ndim != 2 or action.shape[1] != 7:
            raise ValueError(f"HiMem-WAM returned invalid actions: {action.shape}")
        return action

    # -- README §8.4 adapter contract ------------------------------------
    def reset(self, seed: int) -> None:
        self.reset_episode(seed)

    def predict(self, obs: Mapping[str, Any], instruction: str) -> np.ndarray:
        return self.predict_chunk(obs, instruction)
