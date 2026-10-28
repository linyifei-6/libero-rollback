# pi05 标准 LIBERO 四套件 baseline —— “官方 prompt”第一遍独立只读审计（task-4）

- 审计时间：2026-10-19T18:26:37+0800（Asia/Singapore）
- 运行目录：`/home/tarowang/workspace/roboot/libero-rollback/runs/libero-std-baseline-20261019`（pass：`run/first-pass/`；对照归档：`run/sensitivity-bddl-prompt/`）
- 权威 spec：`/home/tarowang/workspace/roboot/libero-rollback/.tmp/std-baseline-audit/spec.json`（task-1 审计产物）
- 官方协议参照：`/home/tarowang/workspace/roboot/libero-plus/openpi/examples/libero/main.py`
- 审计范围：CPU-only, read-only: JSON/log parsing + OpenCV video probe; no simulator, no model, no GPU
- **运行状态：COMPLETE** — 已审计 40/40 个 episode

## 0. 结论摘要

- **prompt 一致性（D1 修复验证）：已审计 40 条 episode 中 40 条等于官方 benchmark `task.language`（0 条不一致）**；40 个任务中有 25 个任务的 BDDL 语言与官方不同，即旧 pass 对这 25 个任务用了不同 prompt。
- 独立统计（新 pass，官方 prompt）：LIBERO_SPATIAL 10/10；LIBERO_OBJECT 10/10；LIBERO_GOAL 10/10；LIBERO_10 10/10；总体 40/40 = 100.0%
- 两 pass 对比（同一 40 任务 / init 0 / 同 seed）：旧 BDDL-prompt 39/40 → 新官方-prompt 40/40（Δ=+1）；其中 prompt 被改写的 25 个任务：旧 24 → 新 25（Δ=+1）；prompt 未变的 15 个任务：旧 15 → 新 15。
- **LIBERO_GOAL #4**（BDDL 语义错误 “put the bowl on the top of the drawer” → 官方 “put the bowl on top of the cabinet”）：旧 pass success=False steps=300，新 pass success=True steps=83 → prompt 修复直接救回该任务。
- **D6 更正**：`--model pi05` 实际加载 `libero_runtime.policies.pi0_policy.Pi0Policy` → openpi `policy_config.create_trained_policy(pytorch_device=…)`，即 **OpenPI 的 PyTorch 后端**；task-3 报告里称其为 `Pi05LeRobotPolicy` 是**错误的**（该类仅用于 `--model pi05_lerobot`）。与官方 openpi JAX policy server 后端仍有差异，数值可能有小偏差。
- 关键检查 26/26 通过；该 pass **可以作为** pi05 标准 LIBERO 四套件 base baseline 的“第一遍（1 init state/task）”可信证据。
- 限定：1 init state (index 0) per task => 1 sample/task; ±1 success swings 10pp at suite level
- 限定：only 1 of 50 official trials per task; cannot be compared 1:1 with official 50-trial pi05 numbers
- 限定：seed semantics differ from openpi (episode_seed 0 / env seed 1000 vs seed 7)
- 限定：inference backend is the OpenPI PyTorch implementation (Pi0Policy -> create_trained_policy), not the official openpi JAX policy server (same checkpoint/transforms; small numeric deviations possible)
- 限定：single seed only; no repeat run / no determinism re-run

## 1. 独立统计（重新从 results.json 计算，不使用 Lead 的 summary）

| suite | episodes | success | success_rate | mean steps | min/max/median |
|---|---:|---:|---:|---:|---|---|
| LIBERO_SPATIAL | 10 | 10 | 100.0% | 106.0 | 86/130/110.0 |
| LIBERO_OBJECT | 10 | 10 | 100.0% | 146.9 | 122/181/145.5 |
| LIBERO_GOAL | 10 | 10 | 100.0% | 125.5 | 75/260/87.0 |
| LIBERO_10 | 10 | 10 | 100.0% | 248.7 | 195/391/238.0 |
| **OVERALL** | **40** | **40** | **100.0%** | **156.8** | 75/391/131.0 |

与 Lead `summary.json` 对比：
- summary.json 存在；独立重算与之一致：**是**
- 对照 pass（sensitivity-bddl-prompt）的独立重算与已归档 summary.json 一致：**是**

## 2. manifest vs spec（40 任务逐项）

- manifest：`/home/tarowang/workspace/roboot/libero-rollback/runs/libero-std-baseline-20261019/run/first-pass/manifest.json`；逐项问题：**0**（0 = idx/name/instruction/bddl/init_states/max_steps 全一致）
- manifest.protocol.policy_prompt = `benchmark task.language (official openpi prompt; BDDL :language only as custom-scene fallback)`
- model：{"adapter": "pi05", "policy_config": "pi05_libero", "checkpoint": "/home/tarowang/.cache/openpi/openpi-assets/checkpoints/pi05_libero", "python": "/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python"}（checkpoint 存在：True）
- manifest.inference_backend：{"loaded_by": "libero_runtime.policies.pi0_policy.Pi0Policy", "openpi_api": "openpi.policies.policy_config.create_trained_policy (pytorch_device=cuda:0)", "backend": "OpenPI PyTorch implementation of pi05_libero", "official_eval": "openpi examples/libero/main.py + scripts/serve_policy.py serve the same checkpoint with the JAX backend", "note": "same checkpoint and transforms, different inference backend; small numeric deviations from the official JAX eval are possible"}
- manifest 声明的偏差：
  - num_steps_wait=10 patched into the runtime overlay copy to match openpi
  - policy prompt is benchmark task.language via an overlay patch; pass 1 with BDDL :language is archived under run/sensitivity-bddl-prompt
  - runtime seeds env with episode_seed+1000 and precomputes stabilized init states; openpi seeds np.random with 7 and starts from init_states[episode_idx]
  - runtime replan default is 10; 5 passed explicitly to match openpi
  - inference uses the in-process OpenPI PyTorch backend; the official openpi LIBERO eval uses the OpenPI JAX policy server

## 3. 协议一致性（官方 openpi 协议 vs 实际日志/结果）

| 协议项 | 官方 | 实际（日志/结果） | 结论 |
|---|---|---|---|
| max_steps LIBERO_SPATIAL | 220 | [220]（10 条日志） | ✅ |
| max_steps LIBERO_OBJECT | 280 | [280]（10 条日志） | ✅ |
| max_steps LIBERO_GOAL | 300 | [300]（10 条日志） | ✅ |
| max_steps LIBERO_10 | 520 | [520]（10 条日志） | ✅ |
| num_steps_wait / stabilization | 10 | 10 | ✅ |
| replan_steps | 5 | 5 | ✅ |
| model / policy config | pi05 / pi05_libero | pi05 / /home/tarowang/.cache/openpi/openpi-assets/checkpoints/pi05_libero | ✅ |
| init state index | 0（seed 0 取 init_states[0]） | select_init_state(seed=0)=init_states[0] | ✅（代码摘录见下） |
| num_trials_per_task | 50（=50 init states） | 1（本第一遍设计） | ⚠️ 设计如此 |

逐 episode 协议字段检查：
- 结果内 protocol 字段（stabilization_control_steps=10 / replan_steps=5 / model=pi05 / checkpoint=pi05_libero / environment_seed_offset=1000）：**0 个问题**
- runtime overlay 与 `libero-plus/libero-runtime` 的代码差异（Lead 修复后应含 3 处语义改动：num_steps_wait、官方 prompt、n_tasks 守卫）：
```diff
92c92
< NUM_STEPS_WAIT = 5
---
> NUM_STEPS_WAIT = 10
485c485,495
<     """Prefer the task instruction declared by BDDL over filename metadata."""
---
>     """Use the official benchmark task language as the policy prompt.
> 
>     The openpi LIBERO evaluation feeds ``task.language`` to the policy, so the
>     standard-baseline harness must not prefer the BDDL ``:language`` field,
>     which differs in wording (and for some LIBERO_GOAL tasks even in meaning).
>     BDDL stays as the fallback for custom scenes.
>     """
>     if task is not None:
>         language = str(getattr(task, "language", "") or "").strip()
>         if language:
>             return language
4321a4332,4339
>         # Guard: a patched LIBERO-Plus benchmark silently reports thousands of
>         # tasks; the standard baseline requires the original 10-task suites.
>         for _suite_name in sorted({c["suite"] for c in task_configs}):
>             _bm = get_benchmark(_suite_name)(task_order_index=0)
>             if _bm.n_tasks != 10:
>                 raise SystemExit(
>                     f"not a standard LIBERO benchmark: {_suite_name} has "
>                     f"n_tasks={_bm.n_tasks}, expected 10")
```

runtime 关键语义代码摘录（`runs/.../runtime/tools/run_benchmark.py`）：

```python
# NUM_STEPS_WAIT
92: NUM_STEPS_WAIT = 10
```

```python
# init state 选择（seed=0 ⇒ init_states[0]）
918: def select_init_state(init_states, seed: int):
919:     """Select the same deterministic benchmark state for a given seed."""
920:     if init_states is None or len(init_states) == 0:
921:         return None
922:     return init_states[seed % len(init_states)]
923:
```

```python
# 稳定化：10 个 dummy control steps
1869:     for _ in range(NUM_STEPS_WAIT):
1870:         stabilized_obs, _, _, _ = env.step(DUMMY_ACTION)
1871:     pass  # reset_step_counter not on OffScreenRenderEnv
```

```python
# 首个策略观测 = 稳定化后观测
1872:     if use_stabilized_policy_obs:
1873:         obs = stabilized_obs
```

```python
# 指令来源：优先官方 benchmark task.language（D1 修复）
484: def task_instruction(task, bddl_path: str) -> str:
485:     """Use the official benchmark task language as the policy prompt.
486: 
487:     The openpi LIBERO evaluation feeds ``task.language`` to the policy, so the
488:     standard-baseline harness must not prefer the BDDL ``:language`` field,
489:     which differs in wording (and for some LIBERO_GOAL tasks even in meaning).
490:     BDDL stays as the fallback for custom scenes.
491:     """
492:     if task is not None:
493:         language = str(getattr(task, "language", "") or "").strip()
494:         if language:
495:             return language
496:     try:
497:         instruction = str(
498:             BDDLUtils.get_problem_info(bddl_path).get("language_instruction", "")
499:         ).strip()
500:     except Exception:
501:         instruction = ""
502:     if instruction:
503:         return instruction
504:     if task is None:
505:         raise ValueError(f"custom BDDL has no :language field: {bddl_path}")
506:     return str(task.language)
507:
```

```python
# n_tasks==10 守卫（防止误用 LIBERO-Plus 2000+ 任务表）
4336:             if _bm.n_tasks != 10:
4337:                 raise SystemExit(
4338:                     f"not a standard LIBERO benchmark: {_suite_name} has "
4339:                     f"n_tasks={_bm.n_tasks}, expected 10")
4340: 
4341:     if args.mode == "baseline":
```

```python
# 成功判定：env.check_success()（与 openpi 的 env done 同源）
3947:                 default_success = bool(env.check_success())
3948:                 if instruction_switch_monitor is not None:
```

## 4. prompt 一致性（D1 修复验证）

- 官方 prompt 源：**benchmark task.language (openpi main.py: task_description = task.language)**
- 已审计 episode：**40**；与官方 language 一致：**40**；不一致：**0**；一致率 **100.0%**
- ✅ 审计到的每条 episode 的 policy prompt 都等于官方 `task.language`（40/40 预期）。

另有 **25/40** 个任务的 BDDL `:language` 与官方 language 不同 —— 这正是旧 pass 的偏差范围；修复后这些任务全部改为官方 prompt（明细见 task-3 的 D1 表或下方 §6 对照表的 `prompt_changed` 列）。

## 5. 对 task-3 报告的更正（D1 / D6 / D5）

| 原结论（task-3） | 本 task-4 复核 | 结论 |
|---|---|---|
| D1 (task-3 report)：policy prompt came from BDDL :language; 25/40 tasks differed from official benchmark task.language | prompt == official benchmark task.language in 40/40 audited episodes; overlay task_instruction patch + 40/40 prompt check in evidence | **FIXED in this pass** |
| D6 (task-3 report)：inference adapter was in-process PyTorch LeRobot Pi05LeRobotPolicy | `--model pi05` -> libero_runtime.policies.pi0_policy.Pi0Policy -> openpi.policies.policy_config.create_trained_policy(pytorch_device=...); Pi05LeRobotPolicy is only used by `--model pi05_lerobot`. Backend still differs from the official openpi JAX policy server. | **CORRECTED — that identification was wrong** |
| D5 (task-3 report)：overlay code diff vs libero-runtime was only NUM_STEPS_WAIT 5 -> 10 | NUM_STEPS_WAIT 5->10, task_instruction prefers benchmark task.language, n_tasks==10 guard | **SUPERSEDED — after the Lead's fix the overlay has 3 semantic changes** |

D6 代码证据：
- `/home/tarowang/workspace/roboot/libero-rollback/runs/libero-std-baseline-20261019/runtime/libero_runtime/policies/pi0_policy.py`：
```python
89: 
90:     Constructor accepts two positional args matching the benchmark runner's
91:     call signature: Pi0Policy(config_name, checkpoint_dir).
92:     """
93: 
94:     def __init__(
95:         self,
96:         config_name: str,
97:         checkpoint_dir: str,
98:         logger: logging.Logger | None = None,
99:     ):
100:         self._logger = logger or logging.getLogger("Pi0Policy")
101:         t0 = time.time()
102: 
103:         from openpi.training import config as _config
104:         from openpi.policies import policy_config as _policy_config
105: 
106:         self.train_config = _config.get_config(config_name)
107:         self.policy = _policy_config.create_trained_policy(
108:             self.train_config,
109:             checkpoint_dir,
110:             pytorch_device=DEVICE,
111:         )
112:         model_config = self.train_config.model
113:         self._explicit_noise_shape = (
114:             (
115:                 int(model_config.action_horizon),
```
- runner 模型分派（`--model pi05` 走 `else: policy = Pi0Policy(...)`，`Pi05LeRobotPolicy` 只属于 `pi05_lerobot`）：
```python
4514:     elif args.model == "pi05_lerobot":
4515:         ckpt = args.checkpoint or os.path.abspath(
4516:             os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "models", "pi05_libero_few_shot")
4517:         )
4518:         unnorm_key = None
4519:     else:
4520:         assert openpi_policy_spec is not None
4521:         policy_config, ckpt = openpi_policy_spec
4522:         unnorm_key = None
4523: 
4524:     log("Loading model...")
4525:     if args.model == "openvla_oft":
4526:         policy = OpenVlaOftPolicy(
4527:             ckpt,
4528:             unnorm_key=unnorm_key,
4529:         )
4530:         unnorm_key = policy.unnorm_key
4531:     elif args.model == "smolvla":
4532:         policy = SmolVlaPolicy(ckpt)
4533:     elif args.model == "pi05_lerobot":
4534:         policy = Pi05LeRobotPolicy(ckpt)
4535:     else:
4536:         log(f"OpenPI policy config: {policy_config}")
4537:         policy = Pi0Policy(policy_config, ckpt)
4538:     global _infer_fn, _reset_policy_fn, _sampling_protocol_fn, _sampling_audit_fn, _compare_instruction_fn, _reset_instruction_context_fn
4539:     _infer_fn = policy.predict_chunk
4540:     _reset_policy_fn = policy.reset_episode
4541:     _sampling_protocol_fn = getattr(policy, "sampling_protocol", None)
4542:     _sampling_audit_fn = getattr(policy, "sampling_audit", None)
4543:     _compare_instruction_fn = getattr(policy, "compare_instructions", None)
4544:     _reset_instruction_context_fn = getattr(
4545:         policy, "reset_instruction_context", None
4546:     )
```

## 6. 两 pass 逐任务对比（prompt 敏感性：BDDL :language vs 官方 task.language）

| suite | 旧 pass（BDDL prompt） | 新 pass（官方 prompt） | Δ success |
|---|---:|---:|---:|
| LIBERO_SPATIAL | 10/10（100.0%） | 10/10（100.0%） | +0 |
| LIBERO_OBJECT | 10/10（100.0%） | 10/10（100.0%） | +0 |
| LIBERO_GOAL | 9/10（90.0%） | 10/10（100.0%） | +1 |
| LIBERO_10 | 10/10（100.0%） | 10/10（100.0%） | +0 |
| **OVERALL** | **39/40（97.5%）** | **40/40（100.0%）** | **+1** |

- prompt 被改写任务（25 个）：旧 24 → 新 25（Δ=+1）；
  - 由失败转成功：['LIBERO_GOAL_T4']
  - 由成功转失败：[]
- prompt 未变任务（15 个）：旧 15 → 新 15（Δ=+0）；结果/步数与旧 pass 完全一致的任务数 = 15（其余为未对比/缺失）

| suite | idx | prompt 改写? | 旧 success/steps | 新 success/steps | Δ success | Δ steps |
|---|---:|---|---:|---:|---:|---:|
| LIBERO_SPATIAL | 0 | 是 | True/80 | True/111 | 0 | 31 |
| LIBERO_SPATIAL | 1 | 是 | True/111 | True/110 | 0 | -1 |
| LIBERO_SPATIAL | 2 | 是 | True/97 | True/100 | 0 | 3 |
| LIBERO_SPATIAL | 3 | 是 | True/90 | True/86 | 0 | -4 |
| LIBERO_SPATIAL | 4 | 是 | True/121 | True/130 | 0 | 9 |
| LIBERO_SPATIAL | 5 | 是 | True/85 | True/88 | 0 | 3 |
| LIBERO_SPATIAL | 6 | 是 | True/111 | True/110 | 0 | -1 |
| LIBERO_SPATIAL | 7 | 是 | True/113 | True/113 | 0 | 0 |
| LIBERO_SPATIAL | 8 | 是 | True/98 | True/93 | 0 | -5 |
| LIBERO_SPATIAL | 9 | 是 | True/119 | True/119 | 0 | 0 |
| LIBERO_OBJECT | 0 | 是 | True/139 | True/159 | 0 | 20 |
| LIBERO_OBJECT | 1 | 是 | True/132 | True/181 | 0 | 49 |
| LIBERO_OBJECT | 2 | 是 | True/123 | True/149 | 0 | 26 |
| LIBERO_OBJECT | 3 | 是 | True/160 | True/153 | 0 | -7 |
| LIBERO_OBJECT | 4 | 是 | True/145 | True/142 | 0 | -3 |
| LIBERO_OBJECT | 5 | 是 | True/115 | True/127 | 0 | 12 |
| LIBERO_OBJECT | 6 | 是 | True/162 | True/170 | 0 | 8 |
| LIBERO_OBJECT | 7 | 是 | True/126 | True/122 | 0 | -4 |
| LIBERO_OBJECT | 8 | 是 | True/143 | True/138 | 0 | -5 |
| LIBERO_OBJECT | 9 | 是 | True/125 | True/128 | 0 | 3 |
| LIBERO_GOAL | 0 | 是 | True/117 | True/115 | 0 | -2 |
| LIBERO_GOAL | 1 | 否 | True/89 | True/89 | 0 | 0 |
| LIBERO_GOAL | 2 | 是 | True/79 | True/75 | 0 | -4 |
| LIBERO_GOAL | 3 | 是 | True/256 | True/260 | 0 | 4 |
| LIBERO_GOAL | 4 | 是 | False/300 | True/83 | 1 | -217 |
| LIBERO_GOAL | 5 | 否 | True/132 | True/132 | 0 | 0 |
| LIBERO_GOAL | 6 | 是 | True/85 | True/85 | 0 | 0 |
| LIBERO_GOAL | 7 | 否 | True/82 | True/82 | 0 | 0 |
| LIBERO_GOAL | 8 | 否 | True/79 | True/79 | 0 | 0 |
| LIBERO_GOAL | 9 | 否 | True/255 | True/255 | 0 | 0 |
| LIBERO_10 | 0 | 否 | True/255 | True/255 | 0 | 0 |
| LIBERO_10 | 1 | 否 | True/241 | True/241 | 0 | 0 |
| LIBERO_10 | 2 | 否 | True/237 | True/237 | 0 | 0 |
| LIBERO_10 | 3 | 否 | True/228 | True/228 | 0 | 0 |
| LIBERO_10 | 4 | 否 | True/228 | True/228 | 0 | 0 |
| LIBERO_10 | 5 | 否 | True/195 | True/195 | 0 | 0 |
| LIBERO_10 | 6 | 否 | True/226 | True/226 | 0 | 0 |
| LIBERO_10 | 7 | 否 | True/239 | True/239 | 0 | 0 |
| LIBERO_10 | 8 | 否 | True/391 | True/391 | 0 | 0 |
| LIBERO_10 | 9 | 否 | True/247 | True/247 | 0 | 0 |

## 7. 偏差清单（相对官方 openpi 协议，修复后）

| id | 严重度 | 项 | 官方 | 实际 | 影响范围 |
|---|---|---|---|---|---|
| D1 (task-3) -> FIXED | resolved | policy prompt source | benchmark task.language (openpi main.py: task_description = task.language) | this pass: benchmark task.language for all audited episodes (overlay task_instruction patched); BDDL :language only as custom-scene fallback | prompt matches official in 40/40 audited episodes; 25/40 tasks are the ones where BDDL wording differs, i.e. the old pass fed a different prompt for 25 tasks |
| D2 | low | episode / environment / policy seed | np.random.seed(7); env.seed(7); policy RNG from seed 7 | np.random.seed(0); env.seed(1000) (episode_seed+1000); policy torch.manual_seed(0) | all audited episodes (documented in manifest) |
| D3 | none (implementation-only) | initial policy observation / stabilization | set_init_state -> 10 dummy actions -> policy starts from the post-dummy observation (openpi main.py: num_steps_wait=10) | set_init_state -> 10 dummy actions (NUM_STEPS_WAIT=10) -> first policy observation := post-stabilization observation; policy then runs without re-stepping the dummy actions | all episodes; identical number of dummy actions and identical first policy observation => observably equivalent |
| D4 | by-design | trials per task | 50 trials/task = one per init state | 1 trial/task (init_state_index=[0] only; seed 0 -> select_init_state = init_states[0]) | first pass; sample size 1 per task |
| D5 | low | runtime overlay code changes | openpi examples/libero/main.py | libero-runtime overlay; exactly 3 semantic changes vs libero-runtime: NUM_STEPS_WAIT 5 -> 10, task_instruction prefers benchmark task.language, n_tasks == 10 guard; per-task max_steps via configs/evaluation.max_steps | verified by diff of runs/.../runtime vs libero-plus/libero-runtime |
| D6 (task-3) -> CORRECTED | medium | inference backend | openpi official eval: pi05_libero served by openpi JAX websocket policy server (examples/libero/main.py + scripts/serve_policy.py) | libero_runtime.policies.pi0_policy.Pi0Policy -> openpi.policies.policy_config.create_trained_policy(pytorch_device=cuda:0): OpenPI PyTorch implementation of the same pi05_libero checkpoint. NOT Pi05LeRobotPolicy (that class is only used by --model pi05_lerobot). | all episodes; same checkpoint/transforms, different backend implementation vs official JAX server => small numeric deviations possible, not byte-identical to official pi05_libero numbers |

## 8. 日志与结果交叉核对 / 异常扫描

| suite | driver log | maxsteps(日志) | task headers | BASELINE_SUMMARY | results episodes | 一致性 |
|---|---|---|---:|---:|---:|---|
| LIBERO_SPATIAL | 有 | [220] | 10 | 10 | 10 | ✅ |
| LIBERO_OBJECT | 有 | [280] | 10 | 10 | 10 | ✅ |
| LIBERO_GOAL | 有 | [300] | 10 | 10 | 10 | ✅ |
| LIBERO_10 | 有 | [520] | 10 | 10 | 10 | ✅ |

- Traceback / Error / Exception 等异常行：**0**（benign 警告 84 条：robosuite/Gym/datasets-path 等）

## 9. 视频完整性

- 已完成 episode 应有视频：40；找到：40；总大小：6.57 MB
- 缺失：0；0 字节：0；未完成 episode 的录制中视频：0

| suite | expected | found | 总大小 MB | 视频探针结论 |
|---|---:|---:|---:|---|
| LIBERO_SPATIAL | 10 | 10 | 1.30 | ✅ fps=20/256×256/帧数≈steps+1 |
| LIBERO_OBJECT | 10 | 10 | 1.31 | ✅ fps=20/256×256/帧数≈steps+1 |
| LIBERO_GOAL | 10 | 10 | 1.24 | ✅ fps=20/256×256/帧数≈steps+1 |
| LIBERO_10 | 10 | 10 | 2.72 | ✅ fps=20/256×256/帧数≈steps+1 |

- 注：本机无 ffprobe，视频用 OpenCV 解码抽检（fps=20、256×256、帧数≈steps+1）。

## 10. 可复现性字段抽检

- 抽检 `LIBERO_SPATIAL_T0`：`episode_seed=0`、`environment_seed=1000`、`stabilized_observation_sha256=ec56072abcc62175…`、`base_policy_queries=23`
- episode_seed 集合=[0]；environment_seed 集合=[1000]（符合 manifest：seed 0 / env 1000）

## 11. 逐任务独立统计（新 pass）

| suite | idx | success | steps | time_s | policy prompt（实际） | =官方? |
|---|---:|---|---:|---:|---|---|
| LIBERO_SPATIAL | 0 | True | 111 | 41.0 | pick up the black bowl between the plate and the ramekin and place it on the plate | ✅ |
| LIBERO_SPATIAL | 1 | True | 110 | 38.0 | pick up the black bowl next to the ramekin and place it on the plate | ✅ |
| LIBERO_SPATIAL | 2 | True | 100 | 37.0 | pick up the black bowl from table center and place it on the plate | ✅ |
| LIBERO_SPATIAL | 3 | True | 86 | 32.0 | pick up the black bowl on the cookie box and place it on the plate | ✅ |
| LIBERO_SPATIAL | 4 | True | 130 | 50.0 | pick up the black bowl in the top drawer of the wooden cabinet and place it on the plate | ✅ |
| LIBERO_SPATIAL | 5 | True | 88 | 35.0 | pick up the black bowl on the ramekin and place it on the plate | ✅ |
| LIBERO_SPATIAL | 6 | True | 110 | 38.0 | pick up the black bowl next to the cookie box and place it on the plate | ✅ |
| LIBERO_SPATIAL | 7 | True | 113 | 41.0 | pick up the black bowl on the stove and place it on the plate | ✅ |
| LIBERO_SPATIAL | 8 | True | 93 | 34.0 | pick up the black bowl next to the plate and place it on the plate | ✅ |
| LIBERO_SPATIAL | 9 | True | 119 | 42.0 | pick up the black bowl on the wooden cabinet and place it on the plate | ✅ |
| LIBERO_OBJECT | 0 | True | 159 | 37.0 | pick up the alphabet soup and place it in the basket | ✅ |
| LIBERO_OBJECT | 1 | True | 181 | 42.0 | pick up the cream cheese and place it in the basket | ✅ |
| LIBERO_OBJECT | 2 | True | 149 | 32.0 | pick up the salad dressing and place it in the basket | ✅ |
| LIBERO_OBJECT | 3 | True | 153 | 34.0 | pick up the bbq sauce and place it in the basket | ✅ |
| LIBERO_OBJECT | 4 | True | 142 | 32.0 | pick up the ketchup and place it in the basket | ✅ |
| LIBERO_OBJECT | 5 | True | 127 | 32.0 | pick up the tomato sauce and place it in the basket | ✅ |
| LIBERO_OBJECT | 6 | True | 170 | 39.0 | pick up the butter and place it in the basket | ✅ |
| LIBERO_OBJECT | 7 | True | 122 | 28.0 | pick up the milk and place it in the basket | ✅ |
| LIBERO_OBJECT | 8 | True | 138 | 31.0 | pick up the chocolate pudding and place it in the basket | ✅ |
| LIBERO_OBJECT | 9 | True | 128 | 32.0 | pick up the orange juice and place it in the basket | ✅ |
| LIBERO_GOAL | 0 | True | 115 | 38.0 | open the middle drawer of the cabinet | ✅ |
| LIBERO_GOAL | 1 | True | 89 | 26.0 | put the bowl on the stove | ✅ |
| LIBERO_GOAL | 2 | True | 75 | 27.0 | put the wine bottle on top of the cabinet | ✅ |
| LIBERO_GOAL | 3 | True | 260 | 87.0 | open the top drawer and put the bowl inside | ✅ |
| LIBERO_GOAL | 4 | True | 83 | 30.0 | put the bowl on top of the cabinet | ✅ |
| LIBERO_GOAL | 5 | True | 132 | 39.0 | push the plate to the front of the stove | ✅ |
| LIBERO_GOAL | 6 | True | 85 | 29.0 | put the cream cheese in the bowl | ✅ |
| LIBERO_GOAL | 7 | True | 82 | 27.0 | turn on the stove | ✅ |
| LIBERO_GOAL | 8 | True | 79 | 26.0 | put the bowl on the plate | ✅ |
| LIBERO_GOAL | 9 | True | 255 | 82.0 | put the wine bottle on the rack | ✅ |
| LIBERO_10 | 0 | True | 255 | 65.0 | put both the alphabet soup and the tomato sauce in the basket | ✅ |
| LIBERO_10 | 1 | True | 241 | 61.0 | put both the cream cheese box and the butter in the basket | ✅ |
| LIBERO_10 | 2 | True | 237 | 75.0 | turn on the stove and put the moka pot on it | ✅ |
| LIBERO_10 | 3 | True | 228 | 59.0 | put the black bowl in the bottom drawer of the cabinet and close it | ✅ |
| LIBERO_10 | 4 | True | 228 | 43.0 | put the white mug on the left plate and put the yellow and white mug on the right plate | ✅ |
| LIBERO_10 | 5 | True | 195 | 40.0 | pick up the book and place it in the back compartment of the caddy | ✅ |
| LIBERO_10 | 6 | True | 226 | 43.0 | put the white mug on the plate and put the chocolate pudding to the right of the plate | ✅ |
| LIBERO_10 | 7 | True | 239 | 56.0 | put both the alphabet soup and the cream cheese box in the basket | ✅ |
| LIBERO_10 | 8 | True | 391 | 121.0 | put both moka pots on the stove | ✅ |
| LIBERO_10 | 9 | True | 247 | 60.0 | put the yellow and white mug in the microwave and close it | ✅ |

## 12. 检查清单

| # | check | critical | result | detail |
|---:|---|---|---|---|
| 1 | `spec_asset_files_unchanged` | yes | ✅ |  |
| 2 | `manifest_matches_spec_40_tasks` | yes | ✅ |  |
| 3 | `manifest_checkpoint_exists` | yes | ✅ |  |
| 4 | `shadow_benchmark_is_pristine_head` | yes | ✅ |  |
| 5 | `shadow_assets_are_pristine_third_party` | yes | ✅ |  |
| 6 | `results_parse_no_errors` | yes | ✅ |  |
| 7 | `single_result_dir_per_suite` | no | ✅ |  |
| 8 | `all_40_episodes_present` | no | ✅ |  |
| 9 | `one_baseline_episode_per_task` | yes | ✅ |  |
| 10 | `results_schema_complete` | yes | ✅ |  |
| 11 | `task_key_and_suite_fields_consistent` | yes | ✅ |  |
| 12 | `episode_protocol_fields_official` | yes | ✅ |  |
| 13 | `reproducibility_fields_sane` | yes | ✅ |  |
| 14 | `runtime_init_state_index_matches_manifest` | yes | ✅ |  |
| 15 | `runtime_stabilization_is_10_dummy_steps` | yes | ✅ |  |
| 16 | `runtime_prompt_patch_uses_official_task_language` | yes | ✅ |  |
| 17 | `runtime_ntasks_guard_present` | yes | ✅ |  |
| 18 | `prompt_matches_official_40_40` | yes | ✅ |  |
| 19 | `logs_maxsteps_official` | yes | ✅ |  |
| 20 | `logs_protocol_official` | yes | ✅ |  |
| 21 | `logs_counts_consistent` | yes | ✅ |  |
| 22 | `no_log_anomalies` | yes | ✅ |  |
| 23 | `results_match_logs` | yes | ✅ |  |
| 24 | `videos_one_per_completed_episode` | yes | ✅ |  |
| 25 | `video_probe_matches_steps_20hz` | no | ✅ |  |
| 26 | `no_unexplained_extra_videos` | yes | ✅ |  |
| 27 | `runtime_evaluation_summary_consistent` | no | ✅ |  |
| 28 | `inference_backend_is_openpi_pytorch_not_lerobot` | yes | ✅ |  |
| 29 | `runtime_overlay_has_expected_patches` | yes | ✅ |  |
| 30 | `archived_pass_independent_stats_match_its_summary` | no | ✅ |  |
| 31 | `two_pass_all_40_tasks_compared` | yes | ✅ |  |

## 13. 结论与后续建议

- **结论：该“官方 prompt 第一遍（1 init state/task）”可以作为 pi05 标准 LIBERO 四套件 base baseline 的可信证据**（独立统计与 Lead summary 一致；prompt 40/40 官方；协议/日志/视频/可复现性字段全部核验通过）。
- 但它**不是**官方 50-trial 口径的复现：每任务只有 init state 0 的 1 次 episode，且推理后端为 OpenPI PyTorch 实现（官方为 openpi JAX policy server）。对官方 50-trial 指标只能做“同量级/趋势”参考，不能逐位对比。
- **运行间确定性旁证**：prompt 未变（官方 language 与 BDDL 一致）的 15 个任务在两 pass 中 success 与 steps 完全一致（0 个 mismatch），说明同 checkpoint/seed/init/prompt 下该 pipeline 可复现。

后续建议：
- use this official-prompt pass as the 1-init-state preliminary baseline; do not quote it as the official 50-trial number
- for the official-protocol baseline run 50 trials/task (init states 0..49, expected 2000 episodes, same max_steps/replan/wait; consider seeds 0..4 as a small sweep subset first)
- to close the remaining backend gap, reproduce with the openpi JAX policy server (scripts/serve_policy.py) and compare per-task success/steps against this PyTorch-backend pass
- record prompt/backend/seed deviations in the run README; do not mix prompt sources across passes

## 14. 证据文件

- 机器可读证据：`evidence.json`（本目录；含逐 episode 明细、logs 解析、视频探针、两 pass 逐任务对比、检查项）
- 审计脚本：`run_audit_official.py`（本目录；只读运行目录，写入仅限 `.tmp/std-baseline-audit/run-audit-official/`）
- 权威 spec：`../spec.json`（task-1）；上一轮报告：`../run-audit/report.md`（task-3，本报告已更正其 D6）

