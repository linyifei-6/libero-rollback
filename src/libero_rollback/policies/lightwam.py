"""Light-WAM policy adapter for the LIBERO-Rollback runner.

Wraps the released LIBERO checkpoint (state-fusion action expert + Wan2.1
backbone) with exactly the preprocessing/postprocessing used by Light-WAM's own
``experiments/libero/eval_libero_single.py``:

* images: 180-degree rotation, per-camera resize to 224x224, horizontal concat,
  aspect-preserving resize + center crop + mean/std 0.5 normalisation;
* proprio: ``eef_pos + quat2axisangle + gripper_qpos`` (8-D), normalised with
  the checkpoint's ``dataset_stats.json``;
* text: project-precomputed T5 prompt context, processed exactly like
  ``encode_prompt`` (pad tail zeroed, all-ones mask);
* actions: min/max denormalisation, gripper ``a*2-1`` -> invert -> binarise.

The model stack is imported lazily so the static layer can load the registry
without torch.  The adapter must run inside the Light-WAM environment
(``work/venvs/lightwam``); see README section 8.4.
"""

from __future__ import annotations

import csv
import os
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

_DEFAULT_ROOT = "/home/ubuntu/whj/work/third_party/Light-WAM"
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


class LightWamPolicy:
    """Expose a Light-WAM LIBERO checkpoint through the runner protocol."""

    def __init__(
        self,
        checkpoint: str | os.PathLike[str],
        root: str | os.PathLike[str] | None = None,
        logger: Any | None = None,
    ) -> None:
        import torch  # noqa: PLC0415

        root_path = Path(root or os.environ.get("LIGHTWAM_ROOT") or _DEFAULT_ROOT).resolve()
        if not root_path.is_dir():
            raise ValueError(
                f"Light-WAM root not found: {root_path} (pass --workspace or LIGHTWAM_ROOT)"
            )
        for entry in (str(root_path), str(root_path / "src")):
            if entry not in sys.path:
                sys.path.insert(0, entry)

        from hydra import compose, initialize_config_dir  # noqa: PLC0415
        from hydra.utils import instantiate  # noqa: PLC0415
        from lightwam.datasets.lerobot.utils.normalizer import (  # noqa: PLC0415
            load_dataset_stats_from_json,
        )

        from experiments.libero import eval_libero_single as eval_mod  # noqa: PLC0415

        ckpt = Path(str(checkpoint)).resolve()
        if not ckpt.is_file():
            raise FileNotFoundError(f"Light-WAM checkpoint not found: {ckpt}")
        stats_path = ckpt.parents[2] / "dataset_stats.json"
        if not stats_path.is_file():
            raise FileNotFoundError(
                f"dataset_stats.json not found next to the checkpoint: {stats_path}"
            )

        started = time.time()
        with initialize_config_dir(config_dir=str(root_path / "configs"), version_base="1.3"):
            cfg = compose(
                config_name="sim_libero",
                overrides=[
                    "task=libero_uncond_2cam224_1e-4",
                    "model.load_text_encoder=false",
                    "EVALUATION.use_training_run_config=false",
                    f"ckpt={ckpt}",
                    f"EVALUATION.dataset_stats_path={stats_path}",
                ],
            )
        # The precomputed T5 cache is resolved relative to CWD by the eval script;
        # pin it to the checkout so the runner can start from any directory.
        from omegaconf import OmegaConf  # noqa: PLC0415

        OmegaConf.update(
            cfg,
            "data.text_embedding_cache_dir",
            str(root_path / "data" / "text_embeds_cache" / "libero"),
            force_add=True,
        )

        device = "cuda"
        dtype = torch.bfloat16
        model = instantiate(cfg.model, model_dtype=dtype, device=device)
        model.load_checkpoint(str(ckpt))
        model = model.to(device).eval()

        dataset_stats = load_dataset_stats_from_json(str(stats_path))
        processor = instantiate(cfg.data.train.processor).eval()
        processor.set_normalizer_from_stats(dataset_stats)

        self._torch = torch
        self._eval = eval_mod
        self.cfg = cfg
        self.checkpoint = str(ckpt)
        self.root = str(root_path)
        self.model = model
        self.processor = processor
        self.action_horizon = int(cfg.data.train.num_frames) - 1
        self.input_h = int(cfg.data.train.video_size[0])
        self.input_w = int(cfg.data.train.video_size[1])
        self._num_video_frames = (
            (int(cfg.data.train.num_frames) - 1)
            // int(cfg.data.train.action_video_freq_ratio)
            + 1
        )
        self._context_cache: dict[str, tuple[Any, Any]] = {}
        self._instruction_map = self._build_instruction_map()
        self.metadata = {
            "policy": "lightwam",
            "checkpoint": str(ckpt),
            "workspace": str(root_path),
            "native_chunk": self.action_horizon,
            "action_horizon": self.action_horizon,
            "torch": torch.__version__,
            "text_context": "precomputed T5 cache (pad zeroed, all-ones mask)",
            "load_seconds": round(time.time() - started, 2),
        }

    @staticmethod
    def _build_instruction_map() -> dict[str, str]:
        """Map matrix instructions (LIBERO-plus wording) to LIBERO task language.

        The T5 cache is keyed by the canonical LIBERO language; the rollback
        matrix stores a different wording for the same BDDL task.
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

    def _context(self, task_description: str):
        cached = self._context_cache.get(task_description)
        if cached is not None:
            return cached
        context, mask = self._eval._maybe_preencode_task_prompt_context(
            task_description,
            self.model,
            self.cfg,
            model_device="cuda",
        )
        if context is None or mask is None:
            raise RuntimeError(
                "Light-WAM text context is unavailable: enable "
                "EVALUATION.preencode_prompt_context and provide the precomputed cache"
            )
        self._context_cache[task_description] = (context, mask)
        return context, mask

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
        import inspect  # noqa: PLC0415

        torch = self._torch
        eval_mod = self._eval
        language = self._instruction_map.get(instruction, instruction)
        context, context_mask = self._context(language)

        image, proprio, _ = eval_mod._obs_to_model_input(
            dict(observation),
            cfg=self.cfg,
            processor=self.processor,
            width=self.input_w,
            height=self.input_h,
            device="cuda",
            dtype=self.model.torch_dtype,
        )

        kwargs: dict[str, Any] = {
            "prompt": None,
            "input_image": image,
            "action_horizon": self.action_horizon,
            "negative_prompt": str(self.cfg.EVALUATION.get("negative_prompt", "")),
            "text_cfg_scale": float(self.cfg.EVALUATION.get("text_cfg_scale", 1.0)),
            "num_inference_steps": int(self.cfg.EVALUATION.get("num_inference_steps", 10)),
            "proprio": proprio,
            "sigma_shift": None,
            "seed": None,
            "rand_device": "cpu",
            "tiled": False,
            "context": context,
            "context_mask": context_mask,
        }
        if "num_video_frames" in inspect.signature(self.model.infer_action).parameters:
            kwargs["num_video_frames"] = self._num_video_frames

        with torch.no_grad():
            prediction = self.model.infer_action(**kwargs)

        action = eval_mod._denormalize_action(prediction["action"], self.processor)[0]
        action[..., -1] = action[..., -1] * 2 - 1
        action = eval_mod.invert_gripper_action(action)
        action[..., -1] = np.sign(action[..., -1])
        return np.asarray(action, dtype=np.float64)

    # -- README section 8.4 adapter contract -----------------------------

    def reset(self, seed: int) -> None:
        self.reset_episode(seed)

    def predict(self, obs: Mapping[str, Any], instruction: str) -> np.ndarray:
        return self.predict_chunk(obs, instruction)
