"""Cosmos-Policy adapter (``nvidia/Cosmos-Policy-LIBERO-Predict2-2B``).

Wraps the upstream LIBERO evaluator's inference helpers
(``cosmos_policy.experiments.robot.cosmos_utils``) so the benchmark runner can
drive the policy through the two-method adapter contract (README §8.4):

    reset_episode(seed)
    predict_chunk(observation, instruction) -> np.ndarray (T, 7)

Preprocessing is kept identical to the upstream LIBERO eval that produced the
published 98.5% numbers:

* both camera images are flipped up-down (LIBERO renders upside-down),
* proprio = [gripper_qpos (2), eef_pos (3), eef_quat (4)] — 9 dims, raw
  quaternion (no axis-angle conversion),
* images are resized / JPEG-compressed inside ``get_action`` exactly as in the
  official script,
* actions are unnormalised with ``libero_dataset_statistics.json`` and returned
  in LIBERO env scale, 16-step chunk, 5 denoising steps.

The model stack lives in the Cosmos Policy checkout's own virtualenv
(``uv sync --extra cu128 --group libero --python 3.10``), so torch /
transformers are imported lazily from that interpreter.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Mapping
from typing import Any

import numpy as np

#: Native action chunk of the released LIBERO checkpoint (``chunk_size``).
NATIVE_CHUNK = 16


class CosmosPolicy:
    """Expose a Cosmos-Policy LIBERO checkpoint through the runner protocol."""

    def __init__(
        self,
        checkpoint: str | os.PathLike[str],
        workspace: str | os.PathLike[str] | None = None,
        logger: Any | None = None,
    ) -> None:
        import torch  # noqa: PLC0415

        root = workspace or os.environ.get("COSMOS_POLICY_ROOT")
        if not root:
            raise ValueError(
                "Cosmos-Policy requires --workspace (or COSMOS_POLICY_ROOT) "
                "pointing at the NVlabs/cosmos-policy checkout"
            )
        root_path = str(root)
        if root_path not in sys.path:
            sys.path.insert(0, root_path)
        # The checkpoint directory also holds the dataset statistics and the
        # precomputed LIBERO T5 embeddings shipped in the HF repo.
        ckpt_path = str(checkpoint)
        ckpt_dir = os.path.dirname(os.path.abspath(ckpt_path))

        from cosmos_policy.experiments.robot.cosmos_utils import (  # noqa: PLC0415
            get_action,
            get_model,
            init_t5_text_embeddings_cache,
            load_dataset_stats,
        )
        from cosmos_policy.experiments.robot.libero.run_libero_eval import (  # noqa: PLC0415
            PolicyEvalConfig,
        )

        started = time.time()
        self._torch = torch
        self.checkpoint = ckpt_path
        self.workspace = root_path
        self._get_action = get_action
        self._seed = 0

        self.cfg = PolicyEvalConfig(
            config="cosmos_predict2_2b_480p_libero__inference_only",
            ckpt_path=ckpt_path,
            config_file="cosmos_policy/config/config.py",
            dataset_stats_path=os.path.join(ckpt_dir, "libero_dataset_statistics.json"),
            t5_text_embeddings_path=os.path.join(ckpt_dir, "libero_t5_embeddings.pkl"),
            use_third_person_image=True,
            num_third_person_images=1,
            use_wrist_image=True,
            num_wrist_images=1,
            use_proprio=True,
            normalize_proprio=True,
            unnormalize_actions=True,
            chunk_size=NATIVE_CHUNK,
            num_open_loop_steps=NATIVE_CHUNK,
            trained_with_image_aug=True,
            use_jpeg_compression=True,
            flip_images=True,
            use_variance_scale=False,
            ar_future_prediction=False,
            ar_value_prediction=False,
            ar_qvalue_prediction=False,
            num_denoising_steps_action=5,
            num_denoising_steps_future_state=1,
            num_denoising_steps_value=1,
            seed=0,
            randomize_seed=False,
            deterministic=True,
        )
        self.dataset_stats = load_dataset_stats(self.cfg.dataset_stats_path)
        init_t5_text_embeddings_cache(self.cfg.t5_text_embeddings_path)
        # The shipped T5 cache is keyed by the 40 canonical LIBERO instructions;
        # the rollback matrices paraphrase them.  A prebuilt alias table keeps
        # the lookup offline (the fallback path would run the 11B T5 encoder).
        alias_path = os.environ.get("COSMOS_T5_ALIAS", "")
        self.t5_alias: dict[str, str] = {}
        if alias_path:
            with open(alias_path, encoding="utf-8") as handle:
                payload = json.load(handle)
            self.t5_alias = dict(payload.get("alias") or payload)
        self.model, self.cosmos_config = get_model(self.cfg)
        self.native_chunk = NATIVE_CHUNK
        self.metadata = {
            "policy": "cosmos",
            "checkpoint": ckpt_path,
            "workspace": root_path,
            "native_chunk": self.native_chunk,
            "chunk_size": NATIVE_CHUNK,
            "denoising_steps_action": 5,
            "torch": torch.__version__,
            "load_seconds": round(time.time() - started, 2),
            "vae": os.environ.get("COSMOS_VAE_PTH"),
            "t5_alias": {"path": alias_path or None, "entries": len(self.t5_alias)},
        }

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

    def predict_chunk(
        self, observation: Mapping[str, Any], instruction: str
    ) -> np.ndarray:
        prompt = self.t5_alias.get(instruction, instruction)
        if self.t5_alias and prompt is instruction:
            raise KeyError(
                f"no canonical LIBERO instruction for {instruction!r}; "
                "rebuild the T5 alias table (work/build_cosmos_t5_alias.py)"
            )
        # Match the upstream ``prepare_observation``: flip up-down only.
        primary = np.flipud(np.asarray(observation["agentview_image"]))
        wrist = np.flipud(np.asarray(observation["robot0_eye_in_hand_image"]))
        proprio = np.concatenate(
            (
                np.asarray(observation["robot0_gripper_qpos"], dtype=np.float32),
                np.asarray(observation["robot0_eef_pos"], dtype=np.float32),
                np.asarray(observation["robot0_eef_quat"], dtype=np.float32),
            )
        )
        obs = {
            "primary_image": primary,
            "wrist_image": wrist,
            "proprio": proprio,
        }
        result = self._get_action(
            self.cfg,
            self.model,
            self.dataset_stats,
            obs,
            prompt,
            seed=self._seed,
            randomize_seed=False,
            num_denoising_steps_action=self.cfg.num_denoising_steps_action,
            generate_future_state_and_value_in_parallel=True,
        )
        actions = np.asarray(result["actions"], dtype=np.float64)
        if actions.ndim != 2 or actions.shape[1] != 7:
            raise ValueError(f"Cosmos-Policy returned invalid actions: {actions.shape}")
        return actions

    # -- README §8.4 adapter contract ------------------------------------

    def reset(self, seed: int) -> None:
        self.reset_episode(seed)

    def predict(self, obs: Mapping[str, Any], instruction: str) -> np.ndarray:
        return self.predict_chunk(obs, instruction)
