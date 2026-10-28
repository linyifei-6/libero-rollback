# LIBERO 实验记录（2026-10-19）：标准四套件 baseline 与“双子任务”组合验证

> **状态说明**：本会话的两个实验目录（`runs/libero-std-baseline-20261019/`、`runs/combined-tasks-20261019/`）
> 在 2026-10-19 23:05 左右被误删。原始 results / videos / traces 文件不可找回；恢复重跑已按用户要求停止。
> 本文档由**幸存的独立审计证据**（原 `.tmp/std-baseline-audit/`、`.tmp/combined-audit/`，已复制到
> [`docs/experiments-20261019/audit/`](experiments-20261019/audit/)）与部分恢复的静态产物重建；
> 所有数字以审计中的独立复算为准。

## 0. 一页摘要

| 实验 | 规模 | 主结果 |
|---|---|---|
| A. pi05 标准 LIBERO 四套件 base baseline（第一遍，1 init state/task） | 4 套件 × 10 任务 = 40 episodes | 官方 prompt 下 **40/40 = 100%**（per-suite 全 10/10）；BDDL-prompt 对照 pass 39/40（LIBERO_GOAL #4 失败） |
| B. 组合双子任务（GOAL 45 对 / OBJECT 30 对 / 90 措辞变体） | 静态验证 45/45 + 90/90 + 30/30；动态 67 episodes | pi05 单指令组合 **2/49 = 4.1%**（失败主因：完成恰好 1 个子任务后停滞，41/47）；staged 分阶段指令 2/4；OBJECT 动态 0/4 |

**关键结论**：

1. 标准 LIBERO baseline：pi05 在四套件各 10 个 base 任务上第一遍全成功；但 prompt 源必须对齐官方 `task.language`（BDDL `:language` 会引入 25/40 任务的偏差，并直接导致 Goal #4 失败）。
2. 组合任务本身可行：GOAL 45 对（33 compatible / 5 hard / 7 conflict）、OBJECT 30 对在 BDDL/场景/初始状态层面全部静态验证通过；单子任务在合并场景中可解。
3. 但 pi05 zero-shot **无法用单条组合指令完成双子任务**（2/49 = 4.1%，compatible 33 对 sweep 仅 1/33）；失败模式是完成恰好一个子任务后停滞；措辞变体（then / and then / 交换顺序）0/7 无改善。
4. **分阶段指令（staged）是唯一被验证有效的 workaround**（2/4：00_07 579 步、08_09 390 步），说明物理可行、瓶颈在一次性组合指令的链式执行；但步数接近 600 上限且非全部 pair 成功。
5. 初始状态来源影响第二子任务可解性（wine-on-cabinet：task0 init 失败 600 步 / task2 init 196 步成功）；OBJECT 合并场景动态 0/4（cream cheese 单任务在合并场景失败），需进一步调试。

## 1. 实验 A：pi05 标准 LIBERO 四套件 base baseline

### 1.1 目标与协议

用户要求用 pi05 跑一遍标准 LIBERO 四套件（spatial/object/goal/libero_10，各 10 个原始 base 任务）base baseline；第一遍为每任务 1 个官方初始状态（index 0），共 40 episodes。

| 项 | 官方 openpi `examples/libero/main.py` | 本次 |
|---|---|---|
| 模型 | pi05_libero checkpoint | 同 |
| 任务 | 4 套件 × 10 base 任务（benchmark 顺序） | 同 |
| prompt | `task.language` | 同（第二遍修正后） |
| max_steps | 220 / 280 / 300 / 520 | 同 |
| num_steps_wait | 10 | 10（overlay patch） |
| replan_steps | 5 | 5 |
| trials/task | 50（50 个官方 init states） | **1（init state 0）**，第一遍设计 |
| video | 20 fps 256×256 | 同 |
| 推理后端 | openpi JAX policy server | openpi PyTorch 后端（同 checkpoint，数值可能有小偏差） |
| seed | np.random.seed(7) | episode_seed 0 / env seed 1000 |

### 1.2 环境关键坑：本机 `libero` 包是 LIBERO-Plus 扩展 benchmark

- 默认 pip `libero` 的 4 个套件 `n_tasks` = **2402 / 2518 / 2591 / 2519**（10,030 个扰动实例），不是标准 10 任务；直接跑会静默跑成扰动任务集。
- 标准 40 个 base 任务只存在于 `openpi/third_party/libero`（git HEAD `f78abd6`，上游 LIBERO 官方）；其 live benchmark 文件也被补丁过，但 `.bak` 与 git HEAD 逐字节相同。
- 解决：shadow 包（复制原版代码、恢复 `.bak`、`LIBERO_CONFIG_PATH` 指向原版资产），runtime overlay 加 `n_tasks==10` 守卫、`NUM_STEPS_WAIT=10`、`task_instruction()` 优先官方 `task.language`。
- 资产：third_party 原版资产（与 LIBERO-plus 的 40 bddl + 40 init 逐字节一致，但 LIBERO-plus 有 29 个纹理被降采样/修改，故未用其渲染）。

### 1.3 结果：prompt 源修正前后两遍

**Pass A（BDDL `:language` 作 prompt）**：39/40 = 97.5%

| 套件 | episodes | success | rate | mean steps |
|---|---|---|---|---|
| LIBERO_SPATIAL | 10 | 10 | 100.0% | 102.5 |
| LIBERO_OBJECT | 10 | 10 | 100.0% | 137.0 |
| LIBERO_GOAL | 3 | 3 | 100.0% | 168.33333333333334 |
| LIBERO_10 | 0 | 0 | 0.0% | None |

**Pass B（官方 `task.language` 作 prompt，正式结果）**：40/40 = 100%

| 套件 | episodes | success | rate | mean steps |
|---|---|---|---|---|
| LIBERO_SPATIAL | 10 | 10 | 100.0% | 106.0 |
| LIBERO_OBJECT | 10 | 10 | 100.0% | 146.9 |
| LIBERO_GOAL | 10 | 10 | 100.0% | 125.5 |
| LIBERO_10 | 10 | 10 | 100.0% | 248.7 |

**关键差异**：两 pass 中 25/40 任务的 prompt 文本不同（如 `Pick the akita black bowl...` vs 官方 `pick up the black bowl...`；部分 Goal 任务语义都不同，如 `open the middle layer of the drawer` vs 官方 `open the middle drawer of the cabinet`）。唯一 success 翻转是 **LIBERO_GOAL #4**：Pass A `put the bowl on the top of the drawer` 300 步耗尽失败 → Pass B 官方 `put the bowl on top of the cabinet` 83 步成功；15 个 prompt 未变的任务在两 pass 中 success + steps 完全一致（运行间确定性旁证）。

### 1.4 限定

- 每任务只跑了 1 个初始状态（官方协议 50 个），40 episodes 不是官方 500/套件基线，成功率是点估计。
- 推理为 OpenPI PyTorch 后端（非官方 JAX policy server）；episode/env seed 语义与 openpi（np.random.seed(7)）不同。
- 原始 40 episodes 的 videos/results 已随目录删除；本记录数字来自独立审计证据（`.tmp/std-baseline-audit/`，已复制留存）。
- 标准四套件之外，本会话还跑过 LIBERO-90 候选基线（历史文档 `docs/libero-90-baseline-pi05-seed3.md`），不属于本次事故范围。

### 1.5 事故前产物与幸存证据

- 原始产物（已删除）：`runs/libero-std-baseline-20261019/analysis/first-pass/report.html`（40 段视频内嵌的 HTML 报告）、summary.*、episodes.csv、PROTOCOL.md、run/first-pass 结果与视频。
- 幸存：`.tmp/std-baseline-audit/{audit.md, spec.json}`、`run-audit/`（Pass A 审计）、`run-audit-official/`（Pass B 审计，含 40 条 episode 明细与独立复算）。已复制到 [`experiments-20261019/audit/`](experiments-20261019/audit/)。

## 2. 实验 B：组合“双子任务”基线任务

### 2.1 动机

`libero-rollback` 的 rollback 用例目前只基于 LIBERO-10 的 10 个任务（本身即双子任务），任务基数过小。目标：把其他三个标准套件的单子任务两两组合成新的双子任务，扩充任务基数。

### 2.2 套件可行性分析

| 套件 | 结构 | 同套件组合可行性 |
|---|---|---|
| LIBERO-GOAL（10 任务） | 10 个任务的 `:regions/:fixtures/:objects/:init` 四段完全相同，每任务 1 个目标原子 | ✅ 45 对可无损组合（只需替换 `:goal/:obj_of_interest/:language`） |
| LIBERO-OBJECT（10 任务） | 每任务实例化 7 个物体（1 个目标 + basket + 5 干扰，子集/顺序不同）；目标 `(In <obj> basket_1_contain_region)` | ✅ 需合并场景 + 按 joint/body 名字合成 init 状态；30 对 union≤9 可行 |
| LIBERO-SPATIAL（10 任务） | 所有任务 goal 完全相同 `(On akita_black_bowl_1 plate_1)`，只有初始摆放不同 | ❌ 无法组合出两个不同子任务 |
| 跨套件（spatial↔goal 等） | 同名 region 物理坐标冲突、qpos 布局不同、goal 语义重复 | ❌ 判定不值得做 |

### 2.3 构造方法

**GOAL 45 对**：以任务 i 的 bddl 为模板，`:goal=(And atom_i atom_j)`，`:obj_of_interest` 取并集，`:language = "{lang_i} and {lang_j}"`（官方 benchmark language）；init 状态拷贝任务 i 的 `.pruned_init`（(50,79)，场景同构有效）。

冲突分类规则：同一被操作物体被要求处于两个不同目标位置 → conflict（bowl 集合 {1,3,4,8} 6 对 + wine {2,9} 1 对 = 7）；同物体关系目标但可顺序共存/空间紧邻 → hard（5 对）；其余 compatible（33 对）。分类明细见[附录 A/B](#附录-a45-goal-对目录)。

**GOAL 措辞变体 90 个**：45 对 × {`then` = "first A, then B"、`andthen` = "A and then B"}，其余与基线相同（静态验证 90/90）。

**OBJECT 30 对**：合并两个任务的 `:objects/:regions/:init`（basket 去重），goal=(And atomA atomB)，language=两官方语言连接；因合并后 qpos 布局变化（110→123/136/149），初始状态用 joint-name 映射从两个源任务分别取物体位姿合成（`torch.save(np.ndarray, [50,1+nq+nv])`；每个任务 50 条初始状态，50/50 行往返 0 误差、0 碰撞、初始 success=False、双目标可满足性验证通过）。union=10 的 15 对因无第 4 个安全槽位暂跳过。

### 2.4 静态验证结果（来自幸存审计）

| 产物 | 数量 | 验证内容 | 结果 |
|---|---|---|---|
| GOAL 组合 bddl+init | 45 | BDDL 解析、goal 原子数=2、language、obj_of_interest、env 实例化冒烟、初始 success=False | **45/45** |
| GOAL 措辞变体 | 90 | 同上 + 与基线仅 `:language` 不同 | **90/90** |
| OBJECT 组合 bddl+init | 30 | init 状态合成、50/50 行往返、0 碰撞、初始 success=False、双目标可满足性、runtime 通道复刻 | **30/30** |
| OBJECT 原型 | 2 | object_pair_00_01 / 00_03 | **2/2** |

分类独立复算：conflict 7/7 由 goal atoms 精确复现；hard 5 与 atom 规则候选 6 差一项（`05_08`：物理上可先放碗再推盘，归 compatible 属规则判断项）。

### 2.5 动态 pi05 baseline 验证（7 批，1 seed/对，共 67 episodes）

| run | episodes | success | rate | mean steps | 内容 |
|---|---|---|---|---|---|
| pilot(and) | 9 | 1 | 11.1% | 568.6666666666666 | 9 对 GOAL 组合，"A and B" 官方措辞 |
| variant(then/swap) | 7 | 0 | 0.0% | 600.0 | 7 条措辞/顺序变体（then/andthen/swap + 2 个 OBJECT 原型） |
| diag | 5 | 2 | 40.0% | 404.4 | 5 条单子任务/init 源控制 |
| diag2 | 4 | 3 | 75.0% | 243.5 | 4 条单子任务/碗 init 源对照 |
| staged | 4 | 2 | 50.0% | 542.25 | 4 条分阶段指令验证 |
| sweep-compatible | 33 | 1 | 3.0% | 593.8484848484849 | 33 对 compatible 全量单指令 |
| object-pilot | 4 | 0 | 0.0% | 560.0 | 4 个 OBJECT 组合 |

**单指令组合任务汇总**（pilot + 措辞变体 + compatible sweep = 49 条）：**2/49 = 4.1%**。失败 47 条中 **41 条完成恰好 1 个子任务后停滞**、6 条完成 0 个；只有 2 条成功（`goal_pair_04_07`：put the bowl on top of the cabinet + turn on the stove，397 步；`goal_pair_08_06`：put the bowl on the plate + put the cream cheese in the bowl，318 步；后者 canonical 编号为 `06_08`，属 hard 分类）。

**措辞变体**：0/7，未改善。**init 源敏感**：wine-on-cabinet 单任务用 pair init 600 步失败、用 task2 init 196 步成功；碗/stove/soup 单任务在不同 init 源下均可解。**OBJECT 动态**：0/4（全部只完成第 1 个 object），单任务控制中 cream cheese 在合并场景失败 → 合并场景 init/摆放需调试。

**分阶段指令（staged）**：同一 episode + 同一组合 goal，先给子任务 A 的 instruction，检测到 A 目标为真后切换到 B 的 instruction（`switch_step` = 首个 stage=2 控制步）。结果 2/4：

| pair | 阶段 A / B instruction | switch_step | 结果 | steps |
|---|---|---|---|---|
| goal_pair_00_01 | open the middle drawer of the cabinet / put the bowl on the stove | 133 | ❌ | 600 |
| goal_pair_00_07 | open the middle drawer of the cabinet / turn on the stove | 133 | ✅ | 579 |
| goal_pair_08_09 | put the bowl on the plate / put the wine bottle on the rack | 88 | ✅ | 390 |
| obj_object_pair_00_01 | pick up the alphabet soup… / pick up the cream cheese… | 164 | ❌ | 600 |

### 2.6 结论与建议

1. 组合任务本身在静态/物理层面完全可行（GOAL 45 对、OBJECT 30 对全部静态验证通过；单子任务在组合场景可解）。
2. pi05 zero-shot **单指令组合不可行**：仅 2/49 成功；失败模式是完成一个子任务后停滞（OOD 组合指令的链式执行问题），改措辞/顺序无效。
3. 分阶段指令/instruction-switch 是**已被验证可行**的 workaround（2/4，但步数接近上限、非全部 pair 成功）。
4. 若用于 rollback 测试集扩展，可选路线：
   - **(a)** 只用单指令可解 pair（目前仅 2 个，任务基数扩展有限）；
   - **(b) 推荐**：采用 staged/instruction-switch 协议，把组合任务作为新的双子任务基线；先在 `04_07 / 08_06 / 00_07 / 08_09` 上做 staged 全量（建议 max_steps ≥ 800）+ rollback 用例原型（第一阶段完成 → 撤销 → 第二阶段中自修复）；
   - **(c)** 对组合任务微调 pi05（成本高，中期方向）。
5. OBJECT 路线需先修复合并场景的 init/摆放（第二个物体在合并场景不可达/难抓），当前不宜进入动态 baseline 集。

### 2.7 限定

- 动态验证每 pair 仅 1 seed × 1 episode；成功率是点估计。
- 推理为 OpenPI PyTorch 后端（非官方 JAX server）；自定义合并场景 max_steps 600/replan 10（object-pilot 560/5）非官方协议，不能直接与官方 pi05 数字对比。
- 审计发现跨进程渲染 caveat：同一 sim state 在早期批（smoke/pilot）与后期批（variant/diag/staged/sweep）渲染出的 observation sha 不同（疑似 MUJOCO_GL/渲染后端差异；不影响 success/steps/subtask 复算，但跨批次 bitwise 观测量不可复现）。

## 3. 数据与文件清单

### 3.1 权威数据（幸存，已复制留存）

| 路径 | 内容 |
|---|---|
| [`experiments-20261019/baseline_pi05_4suite.json`](experiments-20261019/baseline_pi05_4suite.json) | 标准 baseline：官方 pass 40 条 episode 明细、pass A 幸存的 23 条 + 全套 per-suite 统计、两 pass 对照、协议/manifest、审计 verdict |
| [`experiments-20261019/combined_twosubtask.json`](experiments-20261019/combined_twosubtask.json) | 组合实验：67 条 episode 明细（run/bddl/instruction/success/steps/time/subtasks/switch_step 等）、8 个 run 统计、静态计数、结论、审计 verdict |
| [`experiments-20261019/goal_pair_catalog.json`](experiments-20261019/goal_pair_catalog.json) | 45 对 GOAL 组合任务目录（pair_id/i/j/任务名/组合语言/goal atoms/分类） |
| [`experiments-20261019/object_pair_catalog.json`](experiments-20261019/object_pair_catalog.json) | OBJECT 组合方法、union 分布（审计口径 7/8/9 各 10 对、跳过 15 对）；**精确 30 对 pair 选择清单随原 `pairs.json` 丢失，未伪造** |
| [`experiments-20261019/libero_std_task_spec.json`](experiments-20261019/libero_std_task_spec.json) | 标准 40 个 base 任务清单（benchmark 顺序/name/language/bddl/init/协议） |
| [`experiments-20261019/recovered-artifacts/goal-pairs/`](experiments-20261019/recovered-artifacts/goal-pairs/) | 事故后完整恢复的 GOAL 45 对静态产物（bddl/init + pairs.json + static-validation + REPORT + checksums），已验证 45/45 |
| [`experiments-20261019/audit/`](experiments-20261019/audit/) | 幸存审计报告与证据 JSON（baseline 任务/协议审计、Pass A 与 Pass B 结果审计、combined 审计、审计脚本；共 ~1MB） |

### 3.2 事故中删除、且未恢复的内容

- `runs/libero-std-baseline-20261019/` 的 run 数据与报告：40 episodes 的 results.json / videos / eval.log、analysis（summary.*、episodes.csv、40 段视频内嵌的 report.html）、Pass A 的 40 episodes 原始数据。
- `runs/combined-tasks-20261019/` 的 run 数据：67 episodes 的 results.json / videos / traces（7 批）；原始静态产物（45 对 bddl/init、90 措辞变体、30 对 OBJECT bddl/init、pairs.json、static-validation.json、各 REPORT.md）中的大部分。
- 恢复重跑在 2026-10-19 23:15 左右被用户叫停；不要在任一 `runs/*` 残缺目录中寻找结果数据。

### 3.3 部分恢复的静态产物（非权威，仅供线索/复现）

- ✅ **GOAL 45 对静态产物已完整恢复并永久归档**：`docs/experiments-20261019/recovered-artifacts/goal-pairs/`（45 bddl + 45 sibling init + pairs.json + pairs.md + static-validation.json + REPORT.md + checksums；静态验证 **45/45**、checksums 137 条自校验通过；`runs/` 下保留同源副本）。
- ⚠️ GOAL 措辞变体：`runs/combined-tasks-20261019/artifacts/goal-pairs-phrasings/{then,andthen}/` 已生成 45+45 bddl 与 init（共 270 个 bddl/init 文件），但 pairs.json / static-validation / REPORT 未写（按停止指令未补齐），**不作为权威归档**；
- `runs/combined-tasks-20261019/artifacts/object-scout/`：OBJECT/SPATIAL/跨套件可行性 REPORT、feasibility.json 与 scripts（已恢复）；
- `runs/combined-tasks-20261019/artifacts/object-pairs/`：REPORT.md 与 scripts（bddl 未生成）；
- `runs/combined-tasks-20261019/prep/`：全部 harness 脚本（run_combined_baseline、run_staged_baseline、analyze_combined、build_combined_report、各批 build 脚本、setup_combined）；
- `runs/libero-std-baseline-20261019/`：shadow、runtime overlay、`PROTOCOL.md`、`run/first-pass/manifest.json`、`prep/` 脚本（运行数据未恢复）。
- 各残缺目录内已放 `RECOVERY_STATUS.md` 说明状态。

## 4. 复现指引（若以后需要完整重跑）

**标准 baseline**：

```bash
# 1) 用 runs/libero-std-baseline-20261019/prep/setup_shadow_runtime.sh 重建 shadow(原版 LIBERO 包+.bak 恢复)+runtime overlay
BASE=runs/libero-std-baseline-20261019
export PYTHONPATH="$BASE/shadow:$BASE/runtime" LIBERO_CONFIG_PATH="$BASE/shadow"
export LIBERO_VIDEO_ENCODER_PYTHON=/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python
# 2) 官方 prompt baseline（每套件）：
openpi/.venv/bin/python "$BASE/runtime/tools/run_benchmark.py" --model pi05 --mode baseline \
  --suite LIBERO_SPATIAL --all-tasks --seed-ids 0 --replan-steps 5 --video \
  --output "$BASE/run/first-pass/libero_spatial"
# 其余 3 套件同理（max_steps 由 runtime configs/tasks/<suite>/*.yaml 提供：220/280/300/520）
```

> 注意：`runtime/tools/run_benchmark.py` 必须保留三处 overlay 修改（`NUM_STEPS_WAIT=10`、`task_instruction` 优先官方 benchmark language、`n_tasks==10` 守卫）；否则会静默跑成 LIBERO-Plus 的 2402/2518/2591/2519 任务或产生 prompt 偏差。

**组合任务**：

```bash
C=runs/combined-tasks-20261019
export PYTHONPATH="runs/libero-std-baseline-20261019/shadow:$C/runtime" LIBERO_CONFIG_PATH=runs/libero-std-baseline-20261019/shadow
python $C/prep/build_pilot_pairs.py            # 重建各批 prep/*-pairs（需先有 artifacts 静态产物）
python $C/prep/run_combined_baseline.py --runtime-root $C/runtime --bddl-dir $C/prep/sweep-compatible \
  --output $C/run/sweep-compatible --trace-dir $C/run/sweep-compatible-traces \
  --seed-ids 0 --max-steps 600 --replan-steps 10 --video
python $C/prep/run_staged_baseline.py --runtime-root $C/runtime --bddl-dir $C/prep/staged-pairs \
  --plan $C/prep/staged-plan.json --output $C/run/staged --trace-dir $C/run/staged-traces \
  --seed-ids 0 --max-steps 600 --replan-steps 10 --video
python $C/prep/analyze_combined.py --config $C/prep/analysis-config.json --output $C/run/combined-dynamic-summary.json
python $C/prep/build_combined_report.py
```

**关键运行纪律**（来自历史会话）：单卡 24GB 同时只跑一个模型进程；启动前检查 `nvidia-smi --query-compute-apps` 为空；custom-bddl 会在 bddl 目录生成 `*.M008_backup`（runner 自身逻辑，不影响 `*.bddl` glob）；WSL UNC 写文件不稳定，脚本/文件在 WSL 内写。

## 附录 A：45 GOAL 对目录

| pair_id | 组合语言 | 分类 |
|---|---|---|
| 00_01 | open the middle drawer of the cabinet and put the bowl on the stove | compatible |
| 00_02 | open the middle drawer of the cabinet and put the wine bottle on top of the cabinet | compatible |
| 00_03 | open the middle drawer of the cabinet and open the top drawer and put the bowl inside | compatible |
| 00_04 | open the middle drawer of the cabinet and put the bowl on top of the cabinet | compatible |
| 00_05 | open the middle drawer of the cabinet and push the plate to the front of the stove | compatible |
| 00_06 | open the middle drawer of the cabinet and put the cream cheese in the bowl | compatible |
| 00_07 | open the middle drawer of the cabinet and turn on the stove | compatible |
| 00_08 | open the middle drawer of the cabinet and put the bowl on the plate | compatible |
| 00_09 | open the middle drawer of the cabinet and put the wine bottle on the rack | compatible |
| 01_02 | put the bowl on the stove and put the wine bottle on top of the cabinet | compatible |
| 01_03 | put the bowl on the stove and open the top drawer and put the bowl inside | conflict |
| 01_04 | put the bowl on the stove and put the bowl on top of the cabinet | conflict |
| 01_05 | put the bowl on the stove and push the plate to the front of the stove | hard |
| 01_06 | put the bowl on the stove and put the cream cheese in the bowl | hard |
| 01_07 | put the bowl on the stove and turn on the stove | compatible |
| 01_08 | put the bowl on the stove and put the bowl on the plate | conflict |
| 01_09 | put the bowl on the stove and put the wine bottle on the rack | compatible |
| 02_03 | put the wine bottle on top of the cabinet and open the top drawer and put the bowl inside | compatible |
| 02_04 | put the wine bottle on top of the cabinet and put the bowl on top of the cabinet | compatible |
| 02_05 | put the wine bottle on top of the cabinet and push the plate to the front of the stove | compatible |
| 02_06 | put the wine bottle on top of the cabinet and put the cream cheese in the bowl | compatible |
| 02_07 | put the wine bottle on top of the cabinet and turn on the stove | compatible |
| 02_08 | put the wine bottle on top of the cabinet and put the bowl on the plate | compatible |
| 02_09 | put the wine bottle on top of the cabinet and put the wine bottle on the rack | conflict |
| 03_04 | open the top drawer and put the bowl inside and put the bowl on top of the cabinet | conflict |
| 03_05 | open the top drawer and put the bowl inside and push the plate to the front of the stove | compatible |
| 03_06 | open the top drawer and put the bowl inside and put the cream cheese in the bowl | hard |
| 03_07 | open the top drawer and put the bowl inside and turn on the stove | compatible |
| 03_08 | open the top drawer and put the bowl inside and put the bowl on the plate | conflict |
| 03_09 | open the top drawer and put the bowl inside and put the wine bottle on the rack | compatible |
| 04_05 | put the bowl on top of the cabinet and push the plate to the front of the stove | compatible |
| 04_06 | put the bowl on top of the cabinet and put the cream cheese in the bowl | hard |
| 04_07 | put the bowl on top of the cabinet and turn on the stove | compatible |
| 04_08 | put the bowl on top of the cabinet and put the bowl on the plate | conflict |
| 04_09 | put the bowl on top of the cabinet and put the wine bottle on the rack | compatible |
| 05_06 | push the plate to the front of the stove and put the cream cheese in the bowl | compatible |
| 05_07 | push the plate to the front of the stove and turn on the stove | compatible |
| 05_08 | push the plate to the front of the stove and put the bowl on the plate | compatible |
| 05_09 | push the plate to the front of the stove and put the wine bottle on the rack | compatible |
| 06_07 | put the cream cheese in the bowl and turn on the stove | compatible |
| 06_08 | put the cream cheese in the bowl and put the bowl on the plate | hard |
| 06_09 | put the cream cheese in the bowl and put the wine bottle on the rack | compatible |
| 07_08 | turn on the stove and put the bowl on the plate | compatible |
| 07_09 | turn on the stove and put the wine bottle on the rack | compatible |
| 08_09 | put the bowl on the plate and put the wine bottle on the rack | compatible |

## 附录 B：分类明细

- **conflict（7）**：01_03, 01_04, 01_08, 02_09, 03_04, 03_08, 04_08
- **hard（5）**：01_05, 01_06, 03_06, 04_06, 06_08
- **compatible（33）**：00_01, 00_02, 00_03, 00_04, 00_05, 00_06, 00_07, 00_08, 00_09, 01_02, 01_07, 01_09, 02_03, 02_04, 02_05, 02_06, 02_07, 02_08, 03_05, 03_07, 03_09, 04_05, 04_07, 04_09, 05_06, 05_07, 05_08, 05_09, 06_07, 06_09, 07_08, 07_09, 08_09

## 附录 C：配对指标口径（审计复算）

- 单指令组合任务（GOAL）：episodes = 49；success = 2（4.1%）；subtask 完成分布 = {2: 2, 1: 41, 0: 6}；失败 47 条中完成恰好 1 个 = 41、0 个 = 6（来自 combined 审计 `conclusions`）。
- staged：4 条；成功 2（00_07 switch=133, steps=579；08_09 switch=88, steps=390）；失败 2（00_01, object_pair_00_01）。
- OBJECT 动态：object-pilot 4 条全部失败，且均只完成第 1 个 object。
- 原始逐条明细见 [`combined_twosubtask.json`](experiments-20261019/combined_twosubtask.json) 的 `episodes` 字段（67 条）。

## 附录 D：审计证据索引

| 文件 | 内容 |
|---|---|
| [`audit/baseline-task-protocol-audit.md`](experiments-20261019/audit/baseline-task-protocol-audit.md) | 原版 LIBERO 40 任务与官方协议独立审计（n_tasks=10、50 init states、协议参数、资产完整性、shadow 方案） |
| [`audit/baseline-task-spec.json`](experiments-20261019/audit/baseline-task-spec.json) | 40 任务机读 spec |
| [`audit/baseline-passA-audit.md`](experiments-20261019/audit/baseline-passA-audit.md) / [`...evidence.json`](experiments-20261019/audit/baseline-passA-evidence.json) | Pass A（BDDL prompt，23 条保留 episode + 统计） |
| [`audit/baseline-officialpass-audit.md`](experiments-20261019/audit/baseline-officialpass-audit.md) / [`...evidence.json`](experiments-20261019/audit/baseline-officialpass-evidence.json) | Pass B（官方 prompt，40/40，含两 pass 对照与 D1–D6 偏差清单） |
| [`audit/combined-audit.md`](experiments-20261019/audit/combined-audit.md) / [`...evidence.json`](experiments-20261019/audit/combined-evidence.json) | 组合实验最终独立审计（67 episodes、74/74 checks、结论与限定） |
| [`audit/audit_combined.py`](experiments-20261019/audit/audit_combined.py) | 该审计的可复现只读脚本 |

---

_本文档生成于 2026-10-19（事故后重建）。原始实验数据无法找回；引用本文数字时请附上“1 seed/1 init state、OpenPI PyTorch 后端、非官方合并场景协议、原始数据因事故丢失（数字来自独立审计复算）”的限定。_
