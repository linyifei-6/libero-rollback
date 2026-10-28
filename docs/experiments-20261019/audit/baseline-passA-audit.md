# pi05 标准 LIBERO 四套件 baseline 第一遍 —— 独立只读审计

- 审计时间：2026-10-19T17:18:42+0800（Asia/Singapore）
- 运行目录：`/home/tarowang/workspace/roboot/libero-rollback/runs/libero-std-baseline-20261019`
- 权威 spec：`/home/tarowang/workspace/roboot/libero-rollback/.tmp/std-baseline-audit/spec.json`（task-1 审计产物）
- 官方协议参照：`/home/tarowang/workspace/roboot/libero-plus/openpi/examples/libero/main.py`
- 审计范围：CPU-only, read-only: JSON/log parsing + OpenCV video probe; no simulator, no model, no GPU
- **运行状态：PARTIAL** — 已审计 23/40 个 episode

## 0. 结论摘要

- 关键检查 19/19 通过；运行尚未完成（已审计 23/40），本报告为 **部分完成** 版；已完成套件的数字可以作为早期信号，但不能作为四套件完整结论。
- 限定：PARTIAL RUN: only 23/40 episodes present at audit time
- 限定：1 init state (index 0) per task
- 限定：prompt text differs from official benchmark language for 25/40 tasks (BDDL :language)
- 限定：seed semantics differ from openpi (episode_seed 0 / env seed 1000 vs seed 7)
- 限定：inference stack is the in-process LeRobot PyTorch pi05 adapter, not the openpi JAX policy server

## 1. 独立统计（重新从 results.json 计算，未使用 Lead 的 summary）

| suite | episodes | success | success_rate | mean steps | min/max/median | full-budget episodes |
|---|---:|---:|---:|---:|---|---:|
| LIBERO_SPATIAL | 10 | 10 | 100.0% | 102.5 | 80/121/104.5 | 0 |
| LIBERO_OBJECT | 10 | 10 | 100.0% | 137.0 | 115/162/135.5 | 0 |
| LIBERO_GOAL | 3 | 3 | 100.0% | 168.3 | 117/256/132 | 0 |
| LIBERO_10 | 0 | - | - | - | - | - |
| **OVERALL** | **23** | **23** | **100.0%** | **126.1** | 80/256/121 | |

与 Lead `summary.json` 对比：
- 审计时 `run/first-pass/summary.json` **尚不存在**（Lead 的分析脚本未运行）；本报告 §1 的数字即独立重算结果，可用于生成/核对 Lead summary。

## 2. manifest vs spec（40 任务逐项）

- manifest：`/home/tarowang/workspace/roboot/libero-rollback/runs/libero-std-baseline-20261019/run/first-pass/manifest.json`；任务数问题：**0**（0 = 逐项一致）
- 逐项核对字段：idx / name / instruction(=官方 language) / bddl / init_states / max_steps；结果：全部一致
- manifest.protocol：init_state_index=[0]、num_trials=1、num_steps_wait=10、replan_steps=5、max_steps={'LIBERO_SPATIAL': 220, 'LIBERO_OBJECT': 280, 'LIBERO_GOAL': 300, 'LIBERO_10': 520}
- model/checkpoint：{"adapter": "pi05", "policy_config": "pi05_libero", "checkpoint": "/home/tarowang/.cache/openpi/openpi-assets/checkpoints/pi05_libero", "python": "/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python"}（checkpoint 存在：True）
- benchmark_code：{"source": "/home/tarowang/workspace/roboot/libero-plus/openpi/third_party/libero/libero/libero (original LIBERO package)", "restored_files": ["benchmark/__init__.py <- benchmark/__init__.py.bak", "benchmark/libero_suite_task_map.py <- benchmark/libero_suite_task_map.py.bak"], "third_party_git_commit": "f78abd68ee283de9f9be3c8f7e2a9ad60246e95c"}
- manifest 自己声明的偏差：
  - num_steps_wait=10 patched into the runtime overlay copy to match openpi
  - runtime seeds env with episode_seed+1000 and precomputes stabilized init states; openpi seeds np.random with 7 and starts from init_states[episode_idx]
  - runtime replan default is 10; 5 passed explicitly to match openpi

## 3. 协议一致性（官方 openpi 协议 vs 实际日志/结果）

| 协议项 | 官方 | 实际（日志/结果） | 结论 |
|---|---|---|---|
| max_steps LIBERO_SPATIAL | 220 | [220]（10 条日志） | ✅ |
| max_steps LIBERO_OBJECT | 280 | [280]（10 条日志） | ✅ |
| max_steps LIBERO_GOAL | 300 | [300]（4 条日志） | ✅ |
| max_steps LIBERO_10 | 520 | None（0 条日志） | ⏳未跑 |
| num_steps_wait / stabilization | 10 | 10 | ✅ |
| replan_steps | 5 | 5 | ✅ |
| model | pi05 | pi05 | ✅ |
| checkpoint | pi05_libero | /home/tarowang/.cache/openpi/openpi-assets/checkpoints/pi05_libero | ✅ |
| env resolution | 256 | 256（视频 256×256，fps 20 抽检） | ✅ |
| num_trials_per_task | 50（=50 init states，每状态 1 次） | 1（init_state_index=[0]） | ⚠️ 第一遍设计如此 |

逐 episode 协议字段检查：
- 结果内 protocol 字段（stabilization_control_steps=10 / replan_steps=5 / model=pi05 / checkpoint=pi05_libero / environment_seed_offset=1000）：**0 个问题**
- runtime overlay 与 `libero-plus/libero-runtime` 的代码差异（应为仅 num_steps_wait 5→10）：
```diff
92c92
< NUM_STEPS_WAIT = 5
---
> NUM_STEPS_WAIT = 10
```

runtime 关键语义代码摘录（源自 `runs/.../runtime/tools/run_benchmark.py`）：

```python
# NUM_STEPS_WAIT
92: NUM_STEPS_WAIT = 10
```

```python
# init state 选择（seed=0 ⇒ init_states[0]）
908: def select_init_state(init_states, seed: int):
909:     """Select the same deterministic benchmark state for a given seed."""
910:     if init_states is None or len(init_states) == 0:
911:         return None
912:     return init_states[seed % len(init_states)]
913:
```

```python
# 稳定化：10 个 dummy control steps
1859:     for _ in range(NUM_STEPS_WAIT):
1860:         stabilized_obs, _, _, _ = env.step(DUMMY_ACTION)
1861:     pass  # reset_step_counter not on OffScreenRenderEnv
```

```python
# 首个策略观测 = 稳定化后观测
1862:     if use_stabilized_policy_obs:
1863:         obs = stabilized_obs
```

```python
# 指令来源：优先 BDDL :language（偏差 D1）
484: def task_instruction(task, bddl_path: str) -> str:
485:     """Prefer the task instruction declared by BDDL over filename metadata."""
486:     try:
487:         instruction = str(
488:             BDDLUtils.get_problem_info(bddl_path).get("language_instruction", "")
489:         ).strip()
490:     except Exception:
491:         instruction = ""
492:     if instruction:
493:         return instruction
494:     if task is None:
```

```python
# 成功判定：env.check_success()（与 openpi 的 env done 同源）
3937:                 default_success = bool(env.check_success())
3938:                 if instruction_switch_monitor is not None:
```

## 4. 偏差清单（相对官方 openpi 协议）

| id | 严重度 | 项 | 官方 | 实际 | 影响范围 |
|---|---|---|---|---|---|
| D1 | medium | policy prompt source | benchmark task.language (openpi main.py: task_description = task.language) | BDDL :language via libero-runtime task_instruction() | 25/40 tasks differ (episodes audited: 22 differed of 23) |
| D2 | low | episode / environment / policy seed | np.random.seed(7); env.seed(7); policy RNG from seed 7 | np.random.seed(0); env.seed(1000) (episode_seed+1000); policy torch.manual_seed(0) | all audited episodes (documented in manifest) |
| D3 | none (implementation-only) | initial policy observation / stabilization | set_init_state -> 10 dummy actions -> policy starts from the post-dummy observation (openpi main.py: num_steps_wait=10) | set_init_state -> 10 dummy actions (NUM_STEPS_WAIT=10) -> first policy observation := post-stabilization observation; policy then runs without re-stepping the dummy actions | all episodes; identical number of dummy actions and identical first policy observation => observably equivalent |
| D4 | by-design | trials per task | 50 trials/task = one per init state | 1 trial/task (init_state_index=[0] only; seed 0 -> select_init_state = init_states[0]) | first pass; sample size 1 per task |
| D5 | low | runtime overlay code changes | openpi examples/libero/main.py | libero-runtime overlay; only code diff vs libero-runtime = NUM_STEPS_WAIT 5 -> 10; per-task max_steps via configs/evaluation.max_steps | verified by diff of runs/.../runtime vs libero-plus/libero-runtime |
| D6 | medium | inference stack / policy server | openpi official eval: pi05_libero served by openpi JAX websocket policy server (examples/libero/main.py + scripts/serve_policy.py) | in-process PyTorch LeRobot `Pi05LeRobotPolicy` (lerobot.policies.pi05 + OpenPI transformer replacements) loading the same pi05_libero checkpoint; 180-deg image flip, eef_pos+axisangle+gripper state padded to 32, 3-camera LeRobot schema with right wrist black | all episodes; same checkpoint but different inference implementation => numbers are 'pi05 via LeRobot runtime', not byte-comparable to openpi's official pi05_libero numbers |

**D1 指令偏差明细（25/40 个任务；本次已审计 episode 中 22/23 条受影响）**：

| suite | idx | 官方 benchmark language（openpi 输入） | 实际 BDDL language（本次输入） |
|---|---:|---|---|
| LIBERO_SPATIAL | 0 | pick up the black bowl between the plate and the ramekin and place it on the plate | Pick the akita black bowl between the plate and the ramekin and place it on the plate |
| LIBERO_SPATIAL | 1 | pick up the black bowl next to the ramekin and place it on the plate | Pick the akita black bowl next to the ramekin and place it on the plate |
| LIBERO_SPATIAL | 2 | pick up the black bowl from table center and place it on the plate | Pick the akita black bowl from table center and place it on the plate |
| LIBERO_SPATIAL | 3 | pick up the black bowl on the cookie box and place it on the plate | Pick the akita black bowl on the cookies box and place it on the plate |
| LIBERO_SPATIAL | 4 | pick up the black bowl in the top drawer of the wooden cabinet and place it on the plate | Pick the akita black bowl in the top layer of the wooden cabinet and place it on the plate |
| LIBERO_SPATIAL | 5 | pick up the black bowl on the ramekin and place it on the plate | Pick the akita black bowl on the ramekin and place it on the plate |
| LIBERO_SPATIAL | 6 | pick up the black bowl next to the cookie box and place it on the plate | Pick the akita black bowl next to the cookies box and place it on the plate |
| LIBERO_SPATIAL | 7 | pick up the black bowl on the stove and place it on the plate | Pick the akita black bowl on the stove and place it on the plate |
| LIBERO_SPATIAL | 8 | pick up the black bowl next to the plate and place it on the plate | Pick the akita black bowl next to the plate and place it on the plate |
| LIBERO_SPATIAL | 9 | pick up the black bowl on the wooden cabinet and place it on the plate | Pick the akita black bowl on the wooden cabinet and place it on the plate |
| LIBERO_OBJECT | 0 | pick up the alphabet soup and place it in the basket | Pick the alphabet soup and place it in the basket |
| LIBERO_OBJECT | 1 | pick up the cream cheese and place it in the basket | Pick the cream cheese and place it in the basket |
| LIBERO_OBJECT | 2 | pick up the salad dressing and place it in the basket | Pick the salad dressing and place it in the basket |
| LIBERO_OBJECT | 3 | pick up the bbq sauce and place it in the basket | Pick the bbq sauce and place it in the basket |
| LIBERO_OBJECT | 4 | pick up the ketchup and place it in the basket | Pick the ketchup and place it in the basket |
| LIBERO_OBJECT | 5 | pick up the tomato sauce and place it in the basket | Pick the tomato sauce and place it in the basket |
| LIBERO_OBJECT | 6 | pick up the butter and place it in the basket | Pick the butter and place it in the basket |
| LIBERO_OBJECT | 7 | pick up the milk and place it in the basket | Pick the milk and place it in the basket |
| LIBERO_OBJECT | 8 | pick up the chocolate pudding and place it in the basket | Pick the chocolate pudding and place it in the basket |
| LIBERO_OBJECT | 9 | pick up the orange juice and place it in the basket | Pick the orange juice and place it in the basket |
| LIBERO_GOAL | 0 | open the middle drawer of the cabinet | Open the middle layer of the drawer |
| LIBERO_GOAL | 2 | put the wine bottle on top of the cabinet | Put the wine bottle on the top of the drawer |
| LIBERO_GOAL | 3 | open the top drawer and put the bowl inside | Open the top layer of the drawer and put the bowl inside |
| LIBERO_GOAL | 4 | put the bowl on top of the cabinet | Put the bowl on the top of the drawer |
| LIBERO_GOAL | 6 | put the cream cheese in the bowl | Put the cream cheese on the bowl |

> 说明：runtime `task_instruction()` 明确 “Prefer the task instruction declared by BDDL over filename metadata”（`tools/run_benchmark.py:484-493`），因此 25/40 个任务的 prompt 与 openpi 官方输入不同；其中 LIBERO_GOAL 的 BDDL 语言与任务描述语义有明显偏差（如 “open the middle layer of the drawer”）。这会影响与官方 pi05 数字的可比性。

## 5. 日志与结果交叉核对 / 异常扫描

| suite | driver log | maxsteps(日志) | task headers | BASELINE_SUMMARY | results episodes | 一致性 |
|---|---|---|---:|---:|---:|---|
| LIBERO_SPATIAL | 有 | [220] | 10 | 10 | 10 | ✅ |
| LIBERO_OBJECT | 有 | [280] | 10 | 10 | 10 | ✅ |
| LIBERO_GOAL | 有 | [300] | 4 | 3 | 3 | ✅ |
| LIBERO_10 | 无/未跑 | None | - | - | 0 | ⏳ |

- 进行中/未开始 suite：LIBERO_GOAL 3/10（已跑 3 个任务）; LIBERO_10 0/10（已跑 0 个任务）
- 进行中 episode 的 eval.log 会有 task header 但尚无 EPISODE_REPRODUCIBILITY/BASELINE_SUMMARY，属于正常中间态，审计已按“仅统计已完成 episode”处理。
- Traceback / Error / Exception 等异常行：**0**（已知 benign 警告 51 条，如 robosuite/Gym/datasets-path 警告）
- `Specs: 0`（无扰动注入）& baseline 模式：日志中每 episode 均出现，符合 baseline 设计
- ANOMALY_SCAN：日志中无 Traceback / ERROR / Exception（截至审计时刻）

## 6. 视频完整性

- 已完成 episode 应有视频数：23；实际找到：23；总大小：3.04 MB
- 缺失：0；0 字节：0；未完成 episode 的进行中视频（extra）：0

| suite | expected | found | 总大小 MB | 视频探针结论 |
|---|---:|---:|---:|---|
| LIBERO_SPATIAL | 10 | 10 | 1.26 | ✅ 全部 fps=20/256×256/帧数≈steps+1 |
| LIBERO_OBJECT | 10 | 10 | 1.20 | ✅ 全部 fps=20/256×256/帧数≈steps+1 |
| LIBERO_GOAL | 3 | 3 | 0.58 | ✅ 全部 fps=20/256×256/帧数≈steps+1 |
| LIBERO_10 | 0 | 0 | 0.00 | ✅ 全部 fps=20/256×256/帧数≈steps+1 |

- 注：本机未安装 ffprobe，视频用 OpenCV 解码抽检（fps=20、256×256、帧数≈steps+1；已审计视频均符合）。

## 7. 可复现性字段抽检

- 抽检 `LIBERO_SPATIAL_T0`：`reproducibility.episode_seed=0`、`environment_seed=1000`、`stabilized_observation_sha256=ec56072abcc62175…`、`base_policy_queries=16` 条
- 全部 23 个 episode 的 sha256 格式合法且 base_policy_queries ≥1：✅
- 全部 episode 的 episode_seed 集合 = [0]；environment_seed 集合 = [1000]（符合 manifest：seed 0 / env 1000）

## 8. 逐任务独立统计

| suite | idx | success | steps | time_s | instruction（实际输入） | matches official? |
|---|---:|---|---:|---:|---|---|
| LIBERO_SPATIAL | 0 | True | 80 | 28.0 | pick the akita black bowl between the plate and the ramekin and place it on the  | ❌ |
| LIBERO_SPATIAL | 1 | True | 111 | 38.0 | pick the akita black bowl next to the ramekin and place it on the plate | ❌ |
| LIBERO_SPATIAL | 2 | True | 97 | 34.0 | pick the akita black bowl from table center and place it on the plate | ❌ |
| LIBERO_SPATIAL | 3 | True | 90 | 32.0 | pick the akita black bowl on the cookies box and place it on the plate | ❌ |
| LIBERO_SPATIAL | 4 | True | 121 | 41.0 | pick the akita black bowl in the top layer of the wooden cabinet and place it on | ❌ |
| LIBERO_SPATIAL | 5 | True | 85 | 34.0 | pick the akita black bowl on the ramekin and place it on the plate | ❌ |
| LIBERO_SPATIAL | 6 | True | 111 | 36.0 | pick the akita black bowl next to the cookies box and place it on the plate | ❌ |
| LIBERO_SPATIAL | 7 | True | 113 | 42.0 | pick the akita black bowl on the stove and place it on the plate | ❌ |
| LIBERO_SPATIAL | 8 | True | 98 | 34.0 | pick the akita black bowl next to the plate and place it on the plate | ❌ |
| LIBERO_SPATIAL | 9 | True | 119 | 41.0 | pick the akita black bowl on the wooden cabinet and place it on the plate | ❌ |
| LIBERO_OBJECT | 0 | True | 139 | 32.0 | pick the alphabet soup and place it in the basket | ❌ |
| LIBERO_OBJECT | 1 | True | 132 | 30.0 | pick the cream cheese and place it in the basket | ❌ |
| LIBERO_OBJECT | 2 | True | 123 | 29.0 | pick the salad dressing and place it in the basket | ❌ |
| LIBERO_OBJECT | 3 | True | 160 | 34.0 | pick the bbq sauce and place it in the basket | ❌ |
| LIBERO_OBJECT | 4 | True | 145 | 29.0 | pick the ketchup and place it in the basket | ❌ |
| LIBERO_OBJECT | 5 | True | 115 | 25.0 | pick the tomato sauce and place it in the basket | ❌ |
| LIBERO_OBJECT | 6 | True | 162 | 36.0 | pick the butter and place it in the basket | ❌ |
| LIBERO_OBJECT | 7 | True | 126 | 28.0 | pick the milk and place it in the basket | ❌ |
| LIBERO_OBJECT | 8 | True | 143 | 32.0 | pick the chocolate pudding and place it in the basket | ❌ |
| LIBERO_OBJECT | 9 | True | 125 | 28.0 | pick the orange juice and place it in the basket | ❌ |
| LIBERO_GOAL | 0 | True | 117 | 37.0 | open the middle layer of the drawer | ❌ |
| LIBERO_GOAL | 3 | True | 256 | 83.0 | open the top layer of the drawer and put the bowl inside | ❌ |
| LIBERO_GOAL | 5 | True | 132 | 40.0 | push the plate to the front of the stove | ✅ |

## 9. 检查清单

| # | check | critical | result | detail |
|---:|---|---|---|---|
| 1 | `spec_asset_files_unchanged` | yes | ✅ |  |
| 2 | `manifest_matches_spec_40_tasks` | yes | ✅ |  |
| 3 | `manifest_checkpoint_exists` | yes | ✅ |  |
| 4 | `shadow_benchmark_is_pristine_head` | yes | ✅ |  |
| 5 | `shadow_assets_are_pristine_third_party` | yes | ✅ |  |
| 6 | `results_parse_no_errors` | yes | ✅ |  |
| 7 | `all_40_episodes_present` | no | ❌ | {"present": 23, "expected": 40, "missing_suites": ["LIBERO_10"], "missing_tasks": {"LIBERO_SPATIAL": [], "LIBERO_OBJECT": [], "LIBERO_GOAL": [1, 2, 4, 6, 7, 8, 9], "LIBERO_10": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]}} |
| 8 | `one_baseline_episode_per_task` | yes | ✅ |  |
| 9 | `results_schema_complete` | yes | ✅ |  |
| 10 | `task_key_and_suite_fields_consistent` | yes | ✅ |  |
| 11 | `episode_protocol_fields_official` | yes | ✅ |  |
| 12 | `reproducibility_fields_sane` | yes | ✅ |  |
| 13 | `runtime_init_state_index_matches_manifest` | yes | ✅ |  |
| 14 | `runtime_stabilization_is_10_dummy_steps` | yes | ✅ |  |
| 15 | `instruction_matches_official_benchmark` | no | ❌ | {"audited_episodes": 23, "mismatching_episodes": 22, "all_40_bddl_vs_official": 25} |
| 16 | `logs_maxsteps_official` | yes | ✅ |  |
| 17 | `logs_protocol_official` | yes | ✅ |  |
| 18 | `logs_counts_consistent` | yes | ✅ |  |
| 19 | `no_log_anomalies` | yes | ✅ |  |
| 20 | `results_match_logs` | yes | ✅ |  |
| 21 | `videos_one_per_completed_episode` | no | ✅ |  |
| 22 | `video_probe_matches_steps_20hz` | no | ✅ |  |
| 23 | `no_unexplained_extra_videos` | no | ✅ |  |
| 24 | `runtime_evaluation_summary_consistent` | no | ✅ |  |
| 25 | `runtime_overlay_only_num_steps_wait_patch` | yes | ✅ |  |

## 10. 证据文件

- 机器可读证据：`evidence.json`（本目录，含每个 episode 明细、日志解析、视频探针、检查项）
- 审计脚本：`run_audit.py`（本目录；只读运行目录，写入仅限 `.tmp/std-baseline-audit/run-audit/`）
- 权威 spec：`../spec.json`（task-1）

