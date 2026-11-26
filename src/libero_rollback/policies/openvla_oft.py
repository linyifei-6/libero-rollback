"""OpenVLA-OFT policy adapter.

Two interchangeable backends wrap the same frozen 4-suite OpenVLA-OFT
checkpoint and expose the common adapter surface::

    reset(seed)                    -> None
    predict_chunk(obs, instruction) -> np.ndarray (T, 7)   # env-ready actions

``predict_chunk`` returns actions that can be passed straight to
``OffScreenRenderEnv.step`` -- the LIBERO gripper convention (open = -1,
close = +1) is applied inside the adapter, as is proprio normalisation and the
image preprocessing the checkpoint was trained with (180 degree rotation,
resize + centre crop, fused two-image stacking).

Backends
--------
``libero_plus``
    The official deterministic ``OFTPolicy`` shipped with LIBERO-plus
    (``evaluation_scripts/eval_openvla_oft_libero_plus.py``).  Selected when
    ``--workspace`` points at a tree that contains ``LIBERO-plus/``.

``hf_direct``
    A self-contained loader built on the upstream ``openvla-oft`` code
    (``prismatic/extern/hf/modeling_prismatic.py``) -- the route documented in
    ``work/MODELS.md``.  Selected when LIBERO-plus is absent: ``--workspace``
    (or ``OPENVLA_OFT_REPO``) must point at an ``openvla-oft`` checkout that
    contains ``prismatic/``.

The checkpoint is supplied through ``--checkpoint`` / ``OPENVLA_OFT_CHECKPOINT``;
one ``unnorm_key`` is needed per suite and is derived from the matrix ``suite``
column when the run selects a single suite.  Nothing is hard-coded to a host
path.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

WORKSPACE_ENV = "OPENVLA_OFT_WORKSPACE"
CHECKPOINT_ENV = "OPENVLA_OFT_CHECKPOINT"
CODE_REPO_ENV = "OPENVLA_OFT_REPO"

#: Vision input size of the 4-suite OFT checkpoint (preprocessor_config.json).
IMAGE_SIZE = 224
#: Centre-crop scale applied after the 224 resize (training distribution).
CROP_SCALE = 0.9
#: Proprioceptive state dimension for LIBERO (3 pos + 3 axis-angle + 2 gripper).
PROPRIO_DIM = 8
#: Camera views fed to the checkpoint (agentview + wrist).
NUM_IMAGES_IN_INPUT = 2

#: B matrix suite -> unnorm key exposed by the 4-suite OFT checkpoint.
SUITE_UNNORM_KEYS: Mapping[str, str] = {
    "goal": "libero_goal_no_noops",
    "object": "libero_object_no_noops",
    "spatial": "libero_spatial_no_noops",
    "l10": "libero_10_no_noops",
}

#: Native LIBERO suite names (``scripts/run_libero_eval.py --suites``) -> same keys.
NATIVE_SUITE_UNNORM_KEYS: Mapping[str, str] = {
    "libero_spatial": "libero_spatial_no_noops",
    "libero_object": "libero_object_no_noops",
    "libero_goal": "libero_goal_no_noops",
    "libero_10": "libero_10_no_noops",
}


def _resolve_workspace(workspace: str | None) -> Path | None:
    value = workspace or os.environ.get(WORKSPACE_ENV)
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_dir():
        raise FileNotFoundError(f"OpenVLA-OFT workspace not found: {path}")
    return path


def unnorm_key_for_suite(suite: str) -> str:
    """Map a LIBERO suite name (native or B-matrix) to the checkpoint key."""

    name = str(suite)
    for table in (SUITE_UNNORM_KEYS, NATIVE_SUITE_UNNORM_KEYS):
        if name in table:
            return table[name]
    raise ValueError(
        f"no OpenVLA-OFT unnorm key for suite {suite!r}; known suites: "
        f"{sorted(set(SUITE_UNNORM_KEYS) | set(NATIVE_SUITE_UNNORM_KEYS))}"
    )


def _resolve_unnorm_key(
    unnorm_key: str | None, suites: Sequence[str] | None
) -> str | None:
    if unnorm_key:
        return str(unnorm_key)
    selected = {str(suite) for suite in (suites or ())}
    if len(selected) == 1:
        return unnorm_key_for_suite(next(iter(selected)))
    # Multi-suite runs switch the key per suite via ``set_suite``; defer here.
    return None


# ---------------------------------------------------------------------------
# LIBERO-plus backend (unchanged behaviour)
# ---------------------------------------------------------------------------


def _libero_plus_module(workspace: Path) -> Path:
    return (
        workspace
        / "LIBERO-plus"
        / "evaluation_scripts"
        / "eval_openvla_oft_libero_plus.py"
    )


def _load_oft_class(workspace: Path):
    module_path = _libero_plus_module(workspace)
    if not module_path.exists():
        raise FileNotFoundError(f"OpenVLA-OFT evaluation module not found: {module_path}")
    package_root = str(workspace / "LIBERO-plus")
    if package_root not in sys.path:
        sys.path.insert(0, package_root)

    # The official eval module imports ``libero.libero.benchmark``, whose package
    # eagerly enumerates every BDDL at import time.  The rollback runner builds
    # environments straight from a BDDL path and never needs that registry, so
    # stub it out to keep the import side-effect free.
    if "libero.libero.benchmark" not in sys.modules:
        import types

        try:
            import libero.libero  # noqa: F401  (ensure the parent package exists)
        except Exception:  # noqa: BLE001 - the stub is best effort
            pass
        stub = types.ModuleType("libero.libero.benchmark")

        def get_benchmark(*_args, **_kwargs):
            raise RuntimeError(
                "libero benchmark registry is stubbed out by the rollback runner"
            )

        stub.get_benchmark = get_benchmark  # type: ignore[attr-defined]
        sys.modules["libero.libero.benchmark"] = stub

    spec = importlib.util.spec_from_file_location("openvla_oft_libero_eval", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load OpenVLA-OFT module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.OFTPolicy


# ---------------------------------------------------------------------------
# hf_direct backend -- upstream openvla-oft classes, no TensorFlow, no LIBERO-plus
# ---------------------------------------------------------------------------


def _resolve_code_repo(workspace: Path | None) -> Path:
    """Locate the upstream ``openvla-oft`` checkout that contains ``prismatic/``."""

    candidates: list[Path] = []
    if workspace is not None:
        candidates.append(workspace)
    env_value = os.environ.get(CODE_REPO_ENV)
    if env_value:
        candidates.append(Path(env_value).expanduser())
    for path in candidates:
        if (path / "prismatic" / "extern" / "hf" / "modeling_prismatic.py").is_file():
            return path
    raise RuntimeError(
        "cannot locate the upstream openvla-oft code: pass --workspace or set "
        f"{CODE_REPO_ENV} to a checkout that contains prismatic/"
    )


def _import_prismatic(repo: Path) -> dict[str, Any]:
    import types

    import transformers

    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))

    # The upstream ``prismatic/__init__.py`` eagerly imports the training stack
    # (draccus, wandb, ...).  Register empty parent packages so the leaf modules
    # we need load from their files without pulling in the training registry.
    for name in (
        "prismatic",
        "prismatic.extern",
        "prismatic.extern.hf",
        "prismatic.models",
        "prismatic.training",
        "prismatic.vla",
    ):
        existing = sys.modules.get(name)
        if existing is not None and getattr(existing, "__path__", None):
            continue
        stub = types.ModuleType(name)
        stub.__path__ = [str(repo.joinpath(*name.split(".")))]
        stub.__package__ = name
        sys.modules[name] = stub

    from prismatic.extern.hf.configuration_prismatic import OpenVLAConfig
    from prismatic.extern.hf.modeling_prismatic import OpenVLAForActionPrediction
    from prismatic.extern.hf.processing_prismatic import (
        PrismaticImageProcessor,
        PrismaticProcessor,
    )
    from prismatic.models.action_heads import (
        DiffusionActionHead,
        L1RegressionActionHead,
    )
    from prismatic.models.projectors import NoisyActionProjector, ProprioProjector
    from prismatic.vla import constants as vla_constants

    try:  # transformers >= 4.4x raises when a model type is already registered
        from transformers import AutoConfig

        AutoConfig.register("openvla", OpenVLAConfig)
    except ValueError:
        pass

    # Upstream hard-fails on `timm.__version__` outside {0.9.10, 0.9.11, 0.9.12,
    # 0.9.16}.  timm 1.x keeps the two APIs this checkpoint uses
    # (`create_model(..., pretrained=False, num_classes=0, img_size, act_layer)`
    # and `get_intermediate_layers`), and 0.9.x is not available offline here, so
    # report the closest whitelisted version for the duration of the run.
    import timm

    if tuple(int(p) for p in timm.__version__.split(".")[:2]) >= (1, 0):
        timm.__version__ = "0.9.16"

    # timm 1.x returns `get_intermediate_layers(...)` as a list where 0.9.x
    # returned a tuple; upstream's `unpack_tuple` only unwraps tuples, so the
    # vision backbone would hand lists to `torch.cat`.  Restore tuple semantics.
    from timm.models.vision_transformer import VisionTransformer

    if not getattr(VisionTransformer, "_oft_tuple_compat", False):
        original = VisionTransformer.get_intermediate_layers

        def _tuple_compat(self, *args, **kwargs):
            result = original(self, *args, **kwargs)
            return tuple(result) if isinstance(result, list) else result

        VisionTransformer.get_intermediate_layers = _tuple_compat
        VisionTransformer._oft_tuple_compat = True

    # The upstream class predates transformers' attention-backend dispatch: it
    # declares no `_supports_*` flags, which *transformers >= 4.5x* dereferences
    # during ``PreTrainedModel.__init__``.  Declare "eager only" there so loading
    # falls back cleanly instead of raising ``AttributeError``.  On 4.40.x (the
    # version this checkpoint was trained/validated with) leave the flags alone:
    # forcing eager there changes SDPA numerics and the produced actions.
    _tv = tuple(int(p) for p in transformers.__version__.split(".")[:2])
    if _tv >= (4, 50):
        for attr in (
            "_supports_sdpa",
            "_supports_flash_attn",
            "_supports_flash_attn_2",
            "_supports_flex_attn",
        ):
            setattr(OpenVLAForActionPrediction, attr, False)

    return {
        "OpenVLAConfig": OpenVLAConfig,
        "OpenVLAForActionPrediction": OpenVLAForActionPrediction,
        "PrismaticImageProcessor": PrismaticImageProcessor,
        "PrismaticProcessor": PrismaticProcessor,
        "DiffusionActionHead": DiffusionActionHead,
        "L1RegressionActionHead": L1RegressionActionHead,
        "NoisyActionProjector": NoisyActionProjector,
        "ProprioProjector": ProprioProjector,
        "constants": vla_constants,
    }



def _import_tf_cpu_only():
    """Import TensorFlow without letting it claim GPU memory.

    Only ``tf.image`` ops on CPU arrays are needed; by default TF grabs several
    GB of VRAM (and JIT-compiles PTX on H100), which hurts multi-worker runs.
    """

    import tensorflow as tf

    try:
        tf.config.set_visible_devices([], "GPU")
    except Exception:  # noqa: BLE001 - best effort, TF may already be initialised
        pass
    return tf

def _resize_for_policy(image: np.ndarray, size: int = IMAGE_SIZE) -> np.ndarray:
    """Resize a raw LIBERO camera frame to the policy input size.

    When TensorFlow is importable (the official environment ships it) this is the
    upstream pipeline verbatim: ``encode_jpeg`` -> ``decode_image`` ->
    Lanczos3 resize with antialiasing.  Otherwise a Pillow equivalent (JPEG q95
    + antialiased Lanczos resample) is used.
    """

    image = np.asarray(image, dtype=np.uint8)
    if image.shape[:2] == (size, size):
        return image

    try:  # official path
        tf = _import_tf_cpu_only()

        encoded = tf.image.encode_jpeg(image)
        decoded = tf.io.decode_image(encoded, expand_animations=False, dtype=tf.uint8)
        resized = tf.image.resize(decoded, (size, size), method="lanczos3", antialias=True)
        return tf.cast(tf.clip_by_value(tf.round(resized), 0, 255), tf.uint8).numpy()
    except ImportError:
        pass

    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.fromarray(image).save(buffer, format="JPEG", quality=95)
    buffer.seek(0)
    pil = Image.open(buffer).convert("RGB").resize((size, size), Image.LANCZOS)
    return np.asarray(pil, dtype=np.uint8)


def _center_crop(image: np.ndarray, size: int = IMAGE_SIZE) -> np.ndarray:
    """Centre-crop ``CROP_SCALE`` of the area and resize back.

    Uses the upstream TensorFlow ``crop_and_resize`` when available; otherwise
    reproduces its sampling grid (normalised box, ``align_corners=True``).
    """

    if os.environ.get("OPENVLA_FORCE_TF_FREE") != "1":
        try:
            tf = _import_tf_cpu_only()
        except ImportError:
            tf = None
        if tf is not None:
            tensor = tf.convert_to_tensor(np.asarray(image, dtype=np.uint8))
            original_dtype = tensor.dtype
            floats = tf.image.convert_image_dtype(tensor, tf.float32)
            batch = tf.expand_dims(floats, axis=0)
            ratio = tf.reshape(
                tf.clip_by_value(tf.sqrt(CROP_SCALE), 0, 1), shape=(1,)
            )
            offsets = (1 - ratio) / 2
            boxes = tf.stack(
                [offsets, offsets, offsets + ratio, offsets + ratio], axis=1
            )
            cropped = tf.image.crop_and_resize(
                batch, boxes, tf.range(1), (size, size)
            )
            cropped = tf.clip_by_value(cropped[0], 0, 1)
            restored = tf.image.convert_image_dtype(
                cropped, original_dtype, saturate=True
            )
            return restored.numpy()

    img = np.asarray(image, dtype=np.float32)
    height, width = img.shape[:2]
    ratio = float(np.sqrt(CROP_SCALE))
    y1 = (1.0 - ratio) / 2.0
    y2 = y1 + ratio
    ys = y1 * (height - 1) + np.arange(size) * (y2 - y1) * (height - 1) / (size - 1)
    xs = y1 * (width - 1) + np.arange(size) * (y2 - y1) * (width - 1) / (size - 1)

    y0 = np.clip(np.floor(ys).astype(np.intp), 0, height - 1)
    x0 = np.clip(np.floor(xs).astype(np.intp), 0, width - 1)
    y1i = np.clip(y0 + 1, 0, height - 1)
    x1i = np.clip(x0 + 1, 0, width - 1)
    wy = (ys - y0)[:, None, None]
    wx = (xs - x0)[None, :, None]

    top = img[y0][:, x0] * (1.0 - wx) + img[y0][:, x1i] * wx
    bottom = img[y1i][:, x0] * (1.0 - wx) + img[y1i][:, x1i] * wx
    out = top * (1.0 - wy) + bottom * wy
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def _rotated(image: np.ndarray) -> np.ndarray:
    """LIBERO frames are stored upside down vs. training (rotate 180 deg)."""

    return np.ascontiguousarray(np.asarray(image)[::-1, ::-1])


def _quat2axisangle(quat: np.ndarray) -> np.ndarray:
    """robosuite ``quat2axisangle`` (x, y, z, w) -> axis-angle vector."""

    quat = np.array(quat, dtype=np.float64, copy=True)
    quat[3] = float(np.clip(quat[3], -1.0, 1.0))
    denom = np.sqrt(max(0.0, 1.0 - quat[3] * quat[3]))
    if denom < 1e-8:
        return np.zeros(3, dtype=np.float64)
    return (quat[:3] * 2.0 * np.arccos(quat[3])) / denom


def _normalize_proprio(proprio: np.ndarray, norm_stats: Mapping[str, Any]) -> np.ndarray:
    """BOUNDS_Q99 proprio normalisation (the LIBERO checkpoint's scheme)."""

    proprio = np.asarray(proprio, dtype=np.float64)
    q01 = np.asarray(norm_stats["q01"], dtype=np.float64)
    q99 = np.asarray(norm_stats["q99"], dtype=np.float64)
    mask = norm_stats.get("mask")
    mask = np.ones_like(q01, dtype=bool) if mask is None else np.asarray(mask, dtype=bool)
    scaled = 2.0 * (proprio - q01) / (q99 - q01 + 1e-8) - 1.0
    return np.clip(np.where(mask, scaled, proprio), -1.0, 1.0)


def _env_ready_gripper(chunk: np.ndarray) -> np.ndarray:
    """Map the checkpoint's [0, 1] gripper to LIBERO's -1 (open) / +1 (close)."""

    chunk = np.array(chunk, dtype=np.float64, copy=True)
    sign = np.sign(2.0 * chunk[..., -1] - 1.0)
    sign[sign == 0] = 1.0
    chunk[..., -1] = -sign
    return chunk


class _HfDirectPolicy:
    """Upstream ``OpenVLAForActionPrediction`` + L1 head, loaded from disk."""

    def __init__(self, checkpoint: Path, unnorm_key: str, repo: Path) -> None:
        import torch
        from transformers import AutoTokenizer

        self._torch = torch
        self.checkpoint = checkpoint
        self.unnorm_key = unnorm_key
        self.repo = repo
        parts = _import_prismatic(repo)
        self._constants = parts["constants"]

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

        config = parts["OpenVLAConfig"].from_pretrained(str(checkpoint))
        # The card is shared with other long-running evaluations, so fit into
        # whatever VRAM is free: if a full bf16 copy does not fit comfortably,
        # let accelerate place the tail of the stack on CPU instead of OOM-ing.
        model_class = parts["OpenVLAForActionPrediction"]
        self._placement = "cuda"
        free_bytes = 0
        if torch.cuda.is_available():
            free_bytes, _ = torch.cuda.mem_get_info()
        fits = free_bytes >= 18 * 1024**3 or not torch.cuda.is_available()
        if fits:
            model = model_class.from_pretrained(
                str(checkpoint),
                config=config,
                torch_dtype=dtype,
                low_cpu_mem_usage=True,
            )
            model.to(self.device).eval()
        else:
            import accelerate  # noqa: F401  (required for device_map dispatch)

            budget = max(int(free_bytes) - 3 * 1024**3, 4 * 1024**3)
            model = model_class.from_pretrained(
                str(checkpoint),
                config=config,
                torch_dtype=dtype,
                low_cpu_mem_usage=True,
                device_map="auto",
                max_memory={0: budget, "cpu": "128GiB"},
            )
            model.eval()
            self._placement = "device_map"
            self._device_budget_gb = round(budget / 1024**3, 2)
        self._model = model
        # This checkpoint was trained with two camera views (agentview + wrist);
        # the fused backbone only splits 12 channels when told there are 2 images.
        model.vision_backbone.set_num_images_in_input(NUM_IMAGES_IN_INPUT)
        # The HF config carries Open-X action stats; the LIBERO ``*_no_noops``
        # keys live in dataset_statistics.json (what the official loader swaps in).
        stats_path = checkpoint / "dataset_statistics.json"
        if stats_path.is_file():
            with stats_path.open("r", encoding="utf-8") as handle:
                model.norm_stats = json.load(handle)
        if unnorm_key not in model.norm_stats:
            raise KeyError(
                f"{unnorm_key!r} missing from {stats_path}; available: "
                f"{sorted(model.norm_stats)}"
            )

        image_processor = parts["PrismaticImageProcessor"].from_pretrained(str(checkpoint))
        tokenizer = AutoTokenizer.from_pretrained(str(checkpoint), use_fast=True)
        self._processor = parts["PrismaticProcessor"](image_processor, tokenizer)

        llm_dim = int(getattr(model, "llm_dim"))
        action_dim = int(self._constants.ACTION_DIM)
        action_head = parts["L1RegressionActionHead"](
            input_dim=llm_dim, hidden_dim=llm_dim, action_dim=action_dim
        )
        action_head.load_state_dict(self._load_component(checkpoint, "action_head"))
        action_head.to(device=self.device, dtype=dtype).eval()

        proprio_projector = parts["ProprioProjector"](
            llm_dim=llm_dim, proprio_dim=PROPRIO_DIM
        )
        proprio_projector.load_state_dict(
            self._load_component(checkpoint, "proprio_projector")
        )
        proprio_projector.to(device=self.device, dtype=dtype).eval()

        self._action_head = action_head
        self._proprio_projector = proprio_projector
        self._chunk_size = int(self._constants.NUM_ACTIONS_CHUNK)

    @staticmethod
    def _load_component(checkpoint: Path, name: str) -> Mapping[str, Any]:
        import torch

        candidates = sorted(checkpoint.glob(f"{name}--*_checkpoint.pt"))
        if not candidates:
            raise FileNotFoundError(f"no {name}--*_checkpoint.pt in {checkpoint}")
        state = torch.load(candidates[-1], map_location="cpu", weights_only=True)
        if isinstance(state, Mapping) and "state_dict" in state:
            state = state["state_dict"]
        # Upstream ships these components from DDP runs ("module." prefix).
        return {
            (key[len("module.") :] if key.startswith("module.") else key): value
            for key, value in state.items()
        }

    def _prepare_image(self, image: np.ndarray):
        from PIL import Image

        resized = _resize_for_policy(_rotated(image))
        cropped = _center_crop(resized)
        return Image.fromarray(cropped).convert("RGB")

    def predict(self, observation: Mapping[str, Any], instruction: str) -> np.ndarray:
        torch = self._torch
        model = self._model

        primary = self._prepare_image(observation["agentview_image"])
        wrist = self._prepare_image(observation["robot0_eye_in_hand_image"])
        proprio = np.concatenate(
            (
                np.asarray(observation["robot0_eef_pos"], dtype=np.float64),
                _quat2axisangle(observation["robot0_eef_quat"]),
                np.asarray(observation["robot0_gripper_qpos"], dtype=np.float64),
            )
        )
        proprio = _normalize_proprio(
            proprio, model.norm_stats[self.unnorm_key]["proprio"]
        )

        prompt = f"In: What action should the robot take to {instruction.lower()}?\nOut:"
        with torch.inference_mode():
            inputs = self._processor(prompt, primary).to(self.device, dtype=torch.bfloat16)
            wrist_inputs = self._processor(prompt, wrist).to(
                self.device, dtype=torch.bfloat16
            )
            pixel_values = torch.cat(
                [inputs["pixel_values"], wrist_inputs["pixel_values"]], dim=1
            )
            actions, _ = model.predict_action(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
                pixel_values=pixel_values,
                unnorm_key=self.unnorm_key,
                do_sample=False,
                proprio=proprio,
                proprio_projector=self._proprio_projector,
                action_head=self._action_head,
                use_film=False,
            )
        chunk = np.asarray(actions, dtype=np.float64)
        if chunk.ndim == 3:  # (batch, chunk, action)
            chunk = chunk[0]
        chunk = chunk[: self._chunk_size]
        return _env_ready_gripper(chunk)

    def metadata(self) -> dict[str, Any]:
        import torch
        import transformers

        return {
            "backend": "hf_direct",
            "code_repo": str(self.repo),
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "device": str(self.device),
            "placement": self._placement,
            "device_budget_gb": getattr(self, "_device_budget_gb", None),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "proprio_dim": PROPRIO_DIM,
            "action_chunk": self._chunk_size,
        }


# ---------------------------------------------------------------------------
# Public adapter
# ---------------------------------------------------------------------------


class OpenVlaOftPolicy:
    """Thin wrapper that normalises both OFT backends to one action chunk."""

    def __init__(
        self,
        checkpoint: str | None = None,
        unnorm_key: str | None = None,
        *,
        workspace: str | None = None,
        suites: Sequence[str] | None = None,
        logger: Any | None = None,
    ) -> None:
        import torch

        self._torch = torch
        workspace_path = _resolve_workspace(workspace)
        configured = checkpoint or os.environ.get(CHECKPOINT_ENV)
        if not configured:
            raise RuntimeError(
                "OpenVLA-OFT checkpoint not configured: pass --checkpoint or set "
                f"{CHECKPOINT_ENV}"
            )
        self.checkpoint = str(Path(configured).expanduser())
        resolved_key = _resolve_unnorm_key(unnorm_key, suites)
        # Multi-suite runs call ``set_suite`` before each suite; bootstrap with a
        # key the checkpoint definitely has so the weights load and validate.
        self.unnorm_key: str = resolved_key or unnorm_key_for_suite("libero_spatial")
        extended = {"checkpoint": self.checkpoint, "unnorm_key": self.unnorm_key}

        started = time.time()
        if workspace_path is not None and _libero_plus_module(workspace_path).exists():
            self.backend = "libero_plus"
            self.workspace = str(workspace_path)
            policy_class = _load_oft_class(workspace_path)
            self._policy = policy_class(
                checkpoint_path=self.checkpoint,
                unnorm_key=self.unnorm_key,
                use_proprio=True,
                use_l1_regression=True,
                logger=logger,
            )
            extended.update({"workspace": self.workspace, "backend": self.backend})
        else:
            repo = _resolve_code_repo(workspace_path)
            self.backend = "hf_direct"
            self.workspace = str(repo)
            self._policy = _HfDirectPolicy(
                Path(self.checkpoint).expanduser(), self.unnorm_key, repo
            )
            extended.update(self._policy.metadata())

        self.metadata = {
            "policy": "openvla_oft",
            "checkpoint": self.checkpoint,
            "unnorm_key": self.unnorm_key,
            "suite_unnorm_keys": dict(NATIVE_SUITE_UNNORM_KEYS),
            "load_seconds": round(time.time() - started, 2),
            **extended,
        }

    def reset(self, seed: int) -> None:
        torch = self._torch
        np.random.seed(int(seed))
        torch.manual_seed(int(seed))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(seed))

    # -- per-suite action un-normalisation -------------------------------

    def set_unnorm_key(self, unnorm_key: str) -> str:
        """Switch the action un-normalisation statistics (one key per suite)."""

        key = str(unnorm_key)
        stats = getattr(getattr(self._policy, "_model", None), "norm_stats", None)
        if stats is not None and key not in stats:
            raise KeyError(
                f"unnorm key {key!r} not in checkpoint statistics: {sorted(stats)}"
            )
        self.unnorm_key = key
        if hasattr(self._policy, "unnorm_key"):
            self._policy.unnorm_key = key
        self.metadata["unnorm_key"] = key
        return key

    def set_suite(self, suite: str) -> str:
        """Switch to the un-norm key that belongs to ``suite``."""

        return self.set_unnorm_key(unnorm_key_for_suite(suite))

    def predict(self, observation: Mapping[str, Any], instruction: str) -> np.ndarray:
        chunk = np.asarray(
            self._policy.predict(dict(observation), instruction), dtype=np.float64
        )
        if chunk.ndim != 2 or chunk.shape[1] < 7:
            raise ValueError(f"unexpected OpenVLA-OFT action chunk shape: {chunk.shape}")
        return chunk[:, :7]

    # -- README §8.4 adapter contract ------------------------------------

    def reset_episode(self, seed: int) -> None:
        self.reset(seed)

    def predict_chunk(
        self, obs: Mapping[str, Any], instruction: str
    ) -> np.ndarray:
        return self.predict(obs, instruction)
