# 双子任务组合实验 · 独立只读审计（task-11）

- 审计时间：2026-10-19T22:56:44+0800（Asia/Singapore）
- 工作目录：`/home/tarowang/workspace/roboot/libero-rollback/runs/combined-tasks-20261019`
- 范围：CPU-only, read-only: BDDL parsing, torch.load init states, results/trace/log parsing, OpenCV video probe; no env creation, no policy model, no GPU
- **状态：COMPLETE**
- sweep done marker: True；object-pilot done marker: True

## 0. 结论摘要

- 关键检查 **74/74** 通过（无 critical 异常）；另有 2 条非 critical 提示（详见 §6）：`cross_process_observation_variation`、`lead_summary_classification_lookup_issues`
- 单指令组合任务（GOAL，pilot+variant+sweep）：**2/49 成功**（4.1%）；失败 47 条中，完成 **1 个子任务** 41 条、完成 0 个 6 条 → **“完成恰好 1 个子任务后停滞”是主要失败模式**。
- 单子任务对照：bowl(两 init 源)=True/True、stove=True、soup=True、cheese(OBJECT 合并场景)=False → 对照结论成立。
- init 源影响（wine 单任务）：pair-init=False vs task2-init=True → 成立（同一目标仅 init 源不同，成功率不同）。
- 措辞变体（then/andthen/swap）：**0/7 成功** → 未改善（与 and 基线相比无提升）。
- staged 分阶段指令：**2/4 成功**，成功项：[('goal_pair_00_07', 579, 133), ('goal_pair_08_09', 390, 88)]
- OBJECT 单指令组合（object-pilot，0/4）：每对都只完成第 1 个 object（子任务完成分布 {1: 4}），同样呈现“完成 1 个子任务后停滞”；union 7/8/9 的 4 个 pair（00_01/00_03/00_04/08_09）全部失败。
- 与 Lead `combined-dynamic-summary.json` 对比：独立 episodes 67 vs Lead rows 66；字段差异 **0** 条；分类字段差异 **7** 条；Lead 未覆盖 run：[]。

## 1. 静态产物核对

| 产物 | 独立计数/检查 | 结果 |
|---|---|---|
| GOAL 组合对 | 45 bddl + 45 init(init/) + 45 sibling init；45 对唯一；goal 原子=2；language=lang_i and lang_j；scene 段=模板；init=(50,79) 且与 task_i 官方 init 逐字节一致 | ✅ |
| GOAL 分类 | compatible 33 / hard 5 / conflict 7 | ✅ |
| GOAL 分类独立复算 | conflict：由 goal atoms 推导“同一被操作物体被要求处于不同目标位”，与标注集合完全一致 ✅；hard：atom 规则候选 ['01_05', '01_06', '03_06', '04_06', '05_08', '06_08'] vs 标注 ['01_05', '01_06', '03_06', '04_06', '06_08']（多出 ['05_08']：如 05_08 可先放碗再推盘，按物理可顺序完成归 compatible） | ✅ conflict 精确复现；hard 为规则判断项 |
| 措辞变体 | 90 bddl（then 45 / andthen 45），language 模板、goal/scene/init 与基础对一致 | ✅ |
| OBJECT 组合对 | 30 bddl + 30 init + 30 meta；union 10/10/10；init shape 123/136/149×50；goal 原子=2 | ✅ |
| OBJECT 原型 | 2 bddl + 2 init；feasibility.json 存在 | ✅ |
| sweep / object-pilot / staged 输入 | sweep 33（=compatible）、object-pilot 4、staged 4 | ✅ |
| prep 目录来源核验 | pilot 9 / variant 7 / diag 5 / diag2 4 / smoke 1 / staged 4 / object-pilot 4 / sweep 33：语言、goal atoms、init sha 与 bddl 拷贝哈希逐项对照 builder 源 | ✅ |
| shadow / runtime overlay | shadow = baseline pristine shadow 软链（config 相同）；overlay 含 `NUM_STEPS_WAIT=10` 与 custom sibling `.pruned_init` 加载 patch | ✅ |

静态检查明细（失败的 critical 检查会在此列出，完整清单见 evidence.json）：

## 2. 动态 pi05 运行独立复算

| run | episodes | success | rate | mean steps | 子任务完成分布 0/1/2 | traces | videos | log | pending |
|---|---:|---:|---:|---:|---|---:|---:|---|---|
| smoke | 1 | 0 | 0.0% | 600.0 | 0/1/0 | 1/1 | 1 | ✅ | False |
| pilot(and) | 9 | 1 | 11.1% | 568.7 | 2/6/1 | 9/9 | 9 | ✅ | False |
| variant(then/swap) | 7 | 0 | 0.0% | 600.0 | 0/7/0 | 7/7 | 7 | ✅ | False |
| diag | 5 | 2 | 40.0% | 404.4 | 2/3/0 | 5/5 | 5 | ✅ | False |
| diag2 | 4 | 3 | 75.0% | 243.5 | 0/4/0 | 4/4 | 4 | ✅ | False |
| staged | 4 | 2 | 50.0% | 542.2 | 0/2/2 | 4/4 | 4 | ✅ | False |
| sweep-compatible | 33 | 1 | 3.0% | 593.8 | 4/28/1 | 33/33 | 33 | ✅ | False |
| object-pilot | 4 | 0 | 0.0% | 560.0 | 0/4/0 | 4/4 | 4 | ✅ | False |

> traces：每个 episode 一条 jsonl（含 `_meta`/`_summary` + 每 control step 的 goal atom truth）；trace 的 data rows = 10 个 stabilization steps + results.steps（审计已逐条核对）。

- 跨 run 一致性交叉验证：13 个（init sha + scene fingerprint）分组、67 episodes；stabilized **sim state** 逐组一致：✅；同一 run 内 stabilized **observation** 一致：✅。
- ⚠️ 跨进程渲染 caveat：5 组相同 sim state 在**不同批次进程**中得到不同 observation sha（早期 smoke/pilot 与后期 variant/diag/staged/sweep 之间），可能是不同启动 shell 的 MUJOCO_GL/渲染后端差异；属于跨进程渲染可复现性 caveat，不影响本审计的 success/steps/subtask 复算。

## 3. 关键结论验证

### 3.1 单指令组合任务：高失败率 + “完成恰好 1 个子任务后停滞”

- 汇总（GOAL 单指令：pilot 9 + variant 7 + sweep 33，共 49 条）：2 成功（4.1%）
- 失败 47 条的子任务完成分布：0 个=6，1 个=41，2 个=0
- 判定：✅ 结论成立（多数失败停在一半）

### 3.2 措辞变体（then / andthen / swap）

| variant bddl | success | subtasks | 同 pair 的 and 基线 success/subtasks |
|---|---|---|---|
| goal_pair_00_02_andthen | False | 1 | False/1 |
| goal_pair_00_02_swap | False | 1 | False/1 |
| goal_pair_00_07_andthen | False | 1 | False/1 |
| goal_pair_00_07_swap | False | 1 | False/1 |
| goal_pair_00_07_then | False | 1 | False/1 |
| obj_object_pair_00_01 | False | 1 | None/None |
| obj_object_pair_00_03 | False | 1 | None/None |

结论：0/7 成功，未改善 and 基线 → ✅ 成立。

### 3.3 staged 分阶段指令

| pair | success | steps | switch_step（trace: 首个 stage=2 行） | subtasks |
|---|---:|---:|---:|---|
| goal_pair_00_01 | False | 600 | 133 | 1 |
| goal_pair_00_07 | True | 579 | 133 | 2 |
| goal_pair_08_09 | True | 390 | 88 | 2 |
| obj_object_pair_00_01 | False | 600 | 164 | 1 |

- 结论：2/4 成功；切换步 [88, 133, 164] ∈ 预期 88–164 → ✅ staged 部分有效

### 3.4 init 源与单子任务对照

- wine 单任务：pair-init（goal_pair_00_02 的 init）success=False（600 步失败） vs task2-init（原 put_the_wine_bottle_on_top_of_the_cabinet init）success=True → ✅ init 源敏感成立
- bowl 单任务：task0-init=True、task1-init=True；stove=True；soup=True；cheese(OBJECT 合并场景)=False → ✅ 对照结论成立

diag / diag2 原始结果：

| run | stem | success | steps | subtasks |
|---|---|---|---:|---|
| diag | diag_goal_00_02_single_wine | False | 600 | 0 |
| diag | diag_goal_00_07_init_stove_task | False | 600 | 1 |
| diag | diag_goal_00_07_single_stove | True | 68 | 1 |
| diag | diag_obj_00_01_single_cheese | False | 600 | 0 |
| diag | diag_obj_00_01_single_soup | True | 154 | 1 |
| diag2 | diag2_goal_00_01_pair_task1init | False | 600 | 1 |
| diag2 | diag2_goal_00_01_single_bowl_task0init | True | 94 | 1 |
| diag2 | diag2_goal_00_01_single_bowl_task1init | True | 84 | 1 |
| diag2 | diag2_goal_00_02_single_wine_task2init | True | 196 | 1 |

## 4. 与 Lead 汇总的对比

- Lead summary：`/home/tarowang/workspace/roboot/libero-rollback/runs/combined-tasks-20261019/run/combined-dynamic-summary.json`（mtime 2026-10-19T22:49:16，rows=66）
- 独立 episodes=67；Lead 覆盖 run=['diag', 'diag2', 'object-pilot', 'pilot(and)', 'staged', 'sweep', 'variant(then/swap)']（Lead run 名与内部 run 名映射：{'sweep-compatible': 'sweep'}；内部统一用 sweep-compatible/object-pilot 命名）
- Lead 未覆盖的 run：[]（smoke 为冒烟测试，预期不入汇总）
- 字段差异（success/steps/bddl/instruction/subtask first_true/switch_step）：**0** 条
- 分类（status）字段差异：**7** 条（由 `analyze_combined.py` 的 pair-id 查找缺陷导致：object pair id 通过 `object_pair_` 前缀别名命中 goal pair 的 status；逆序 goal pair id 已在 Lead 的 patch 中修复）
  - {"run": "variant(then/swap)", "task_key": "CUSTOM_T5", "lead": "compatible", "independent": "object_validated=True,union=7"}
  - {"run": "variant(then/swap)", "task_key": "CUSTOM_T6", "lead": "compatible", "independent": "object_validated=True,union=9"}
  - {"run": "staged", "task_key": "CUSTOM_T3", "lead": "compatible", "independent": "object_validated=True,union=7"}
  - {"run": "object-pilot", "task_key": "CUSTOM_T0", "lead": "compatible", "independent": "object_validated=True,union=7"}
  - {"run": "object-pilot", "task_key": "CUSTOM_T1", "lead": "compatible", "independent": "object_validated=True,union=9"}
  - {"run": "object-pilot", "task_key": "CUSTOM_T2", "lead": "compatible", "independent": "object_validated=True,union=8"}
  - {"run": "object-pilot", "task_key": "CUSTOM_T3", "lead": "compatible", "independent": "object_validated=True,union=7"}

## 5. 逐对结果（关键 run 明细）

### pilot(and)

| task | bddl | success | steps | subtasks | first_true_step | switch |
|---|---|---:|---:|---|---|---|
| CUSTOM_T0 | goal_pair_00_02 | False | 600 | 1/2 | {"open wooden_cabinet_1_middle_region": 140} | None |
| CUSTOM_T1 | goal_pair_00_07 | False | 600 | 1/2 | {"open wooden_cabinet_1_middle_region": 124} | None |
| CUSTOM_T2 | goal_pair_00_09 | False | 600 | 1/2 | {"on wine_bottle_1 wine_rack_1_top_region": 133} | None |
| CUSTOM_T3 | goal_pair_02_09 | False | 600 | 1/2 | {"on wine_bottle_1 wooden_cabinet_1_top_side": 90} | None |
| CUSTOM_T4 | goal_pair_03_02 | False | 600 | 0/2 | {} | None |
| CUSTOM_T5 | goal_pair_05_06 | False | 600 | 0/2 | {} | None |
| CUSTOM_T6 | goal_pair_07_05 | False | 600 | 1/2 | {"turnon flat_stove_1": 88} | None |
| CUSTOM_T7 | goal_pair_08_06 | True | 318 | 2/2 | {"on akita_black_bowl_1 plate_1": 93, "on cream_cheese_1 akita_black_bowl_1": 327} | None |
| CUSTOM_T8 | goal_pair_08_09 | False | 600 | 1/2 | {"on wine_bottle_1 wine_rack_1_top_region": 127} | None |

### variant(then/swap)

| task | bddl | success | steps | subtasks | first_true_step | switch |
|---|---|---:|---:|---|---|---|
| CUSTOM_T0 | goal_pair_00_02_andthen | False | 600 | 1/2 | {"open wooden_cabinet_1_middle_region": 139} | None |
| CUSTOM_T1 | goal_pair_00_02_swap | False | 600 | 1/2 | {"on wine_bottle_1 wooden_cabinet_1_top_side": 104} | None |
| CUSTOM_T2 | goal_pair_00_07_andthen | False | 600 | 1/2 | {"open wooden_cabinet_1_middle_region": 128} | None |
| CUSTOM_T3 | goal_pair_00_07_swap | False | 600 | 1/2 | {"open wooden_cabinet_1_middle_region": 132} | None |
| CUSTOM_T4 | goal_pair_00_07_then | False | 600 | 1/2 | {"open wooden_cabinet_1_middle_region": 131} | None |
| CUSTOM_T5 | obj_object_pair_00_01 | False | 600 | 1/2 | {"in alphabet_soup_1 basket_1_contain_region": 147} | None |
| CUSTOM_T6 | obj_object_pair_00_03 | False | 600 | 1/2 | {"in alphabet_soup_1 basket_1_contain_region": 171} | None |

### staged

| task | bddl | success | steps | subtasks | first_true_step | switch |
|---|---|---:|---:|---|---|---|
| CUSTOM_T0 | goal_pair_00_01 | False | 600 | 1/2 | {"open wooden_cabinet_1_middle_region": 133} | 133 |
| CUSTOM_T1 | goal_pair_00_07 | True | 579 | 2/2 | {"open wooden_cabinet_1_middle_region": 133, "turnon flat_stove_1": 589} | 133 |
| CUSTOM_T2 | goal_pair_08_09 | True | 390 | 2/2 | {"on akita_black_bowl_1 plate_1": 88, "on wine_bottle_1 wine_rack_1_top_region": 400} | 88 |
| CUSTOM_T3 | obj_object_pair_00_01 | False | 600 | 1/2 | {"in alphabet_soup_1 basket_1_contain_region": 164} | 164 |

### diag

| task | bddl | success | steps | subtasks | first_true_step | switch |
|---|---|---:|---:|---|---|---|
| CUSTOM_T0 | diag_goal_00_02_single_wine | False | 600 | 0/1 | {} | None |
| CUSTOM_T1 | diag_goal_00_07_init_stove_task | False | 600 | 1/2 | {"open wooden_cabinet_1_middle_region": 135} | None |
| CUSTOM_T2 | diag_goal_00_07_single_stove | True | 68 | 1/1 | {"turnon flat_stove_1": 77} | None |
| CUSTOM_T3 | diag_obj_00_01_single_cheese | False | 600 | 0/1 | {} | None |
| CUSTOM_T4 | diag_obj_00_01_single_soup | True | 154 | 1/1 | {"in alphabet_soup_1 basket_1_contain_region": 163} | None |

### diag2

| task | bddl | success | steps | subtasks | first_true_step | switch |
|---|---|---:|---:|---|---|---|
| CUSTOM_T0 | diag2_goal_00_01_pair_task1init | False | 600 | 1/2 | {"open wooden_cabinet_1_middle_region": 182} | None |
| CUSTOM_T1 | diag2_goal_00_01_single_bowl_task0init | True | 94 | 1/1 | {"on akita_black_bowl_1 flat_stove_1_cook_region": 103} | None |
| CUSTOM_T2 | diag2_goal_00_01_single_bowl_task1init | True | 84 | 1/1 | {"on akita_black_bowl_1 flat_stove_1_cook_region": 93} | None |
| CUSTOM_T3 | diag2_goal_00_02_single_wine_task2init | True | 196 | 1/1 | {"on wine_bottle_1 wooden_cabinet_1_top_side": 205} | None |

### sweep-compatible

| task | bddl | success | steps | subtasks | first_true_step | switch |
|---|---|---:|---:|---|---|---|
| CUSTOM_T0 | goal_pair_00_01 | False | 600 | 1/2 | {"open wooden_cabinet_1_middle_region": 136} | None |
| CUSTOM_T1 | goal_pair_00_02 | False | 600 | 1/2 | {"open wooden_cabinet_1_middle_region": 139} | None |
| CUSTOM_T2 | goal_pair_00_03 | False | 600 | 1/2 | {"in akita_black_bowl_1 wooden_cabinet_1_top_region": 183} | None |
| CUSTOM_T3 | goal_pair_00_04 | False | 600 | 1/2 | {"open wooden_cabinet_1_middle_region": 130} | None |
| CUSTOM_T4 | goal_pair_00_05 | False | 600 | 1/2 | {"open wooden_cabinet_1_middle_region": 138} | None |
| CUSTOM_T5 | goal_pair_00_06 | False | 600 | 1/2 | {"open wooden_cabinet_1_middle_region": 131} | None |
| CUSTOM_T6 | goal_pair_00_07 | False | 600 | 1/2 | {"open wooden_cabinet_1_middle_region": 124} | None |
| CUSTOM_T7 | goal_pair_00_08 | False | 600 | 1/2 | {"open wooden_cabinet_1_middle_region": 137} | None |
| CUSTOM_T8 | goal_pair_00_09 | False | 600 | 1/2 | {"on wine_bottle_1 wine_rack_1_top_region": 136} | None |
| CUSTOM_T9 | goal_pair_01_02 | False | 600 | 1/2 | {"on wine_bottle_1 wooden_cabinet_1_top_side": 96} | None |
| CUSTOM_T10 | goal_pair_01_07 | False | 600 | 1/2 | {"on akita_black_bowl_1 flat_stove_1_cook_region": 94} | None |
| CUSTOM_T11 | goal_pair_01_09 | False | 600 | 1/2 | {"on wine_bottle_1 wine_rack_1_top_region": 130} | None |
| CUSTOM_T12 | goal_pair_02_03 | False | 600 | 1/2 | {"on wine_bottle_1 wooden_cabinet_1_top_side": 88} | None |
| CUSTOM_T13 | goal_pair_02_04 | False | 600 | 1/2 | {"on wine_bottle_1 wooden_cabinet_1_top_side": 87} | None |
| CUSTOM_T14 | goal_pair_02_05 | False | 600 | 1/2 | {"on wine_bottle_1 wooden_cabinet_1_top_side": 87} | None |
| CUSTOM_T15 | goal_pair_02_06 | False | 600 | 1/2 | {"on wine_bottle_1 wooden_cabinet_1_top_side": 87} | None |
| CUSTOM_T16 | goal_pair_02_07 | False | 600 | 1/2 | {"on wine_bottle_1 wooden_cabinet_1_top_side": 90} | None |
| CUSTOM_T17 | goal_pair_02_08 | False | 600 | 1/2 | {"on wine_bottle_1 wooden_cabinet_1_top_side": 85} | None |
| CUSTOM_T18 | goal_pair_03_05 | False | 600 | 1/2 | {"in akita_black_bowl_1 wooden_cabinet_1_top_region": 197} | None |
| CUSTOM_T19 | goal_pair_03_07 | False | 600 | 0/2 | {} | None |
| CUSTOM_T20 | goal_pair_03_09 | False | 600 | 0/2 | {} | None |
| CUSTOM_T21 | goal_pair_04_05 | False | 600 | 1/2 | {"on akita_black_bowl_1 wooden_cabinet_1_top_side": 96} | None |
| CUSTOM_T22 | goal_pair_04_07 | True | 397 | 2/2 | {"on akita_black_bowl_1 wooden_cabinet_1_top_side": 95, "turnon flat_stove_1": 406} | None |
| CUSTOM_T23 | goal_pair_04_09 | False | 600 | 0/2 | {} | None |
| CUSTOM_T24 | goal_pair_05_06 | False | 600 | 1/2 | {"on plate_1 main_table_stove_front_region": 143} | None |
| CUSTOM_T25 | goal_pair_05_07 | False | 600 | 1/2 | {"on plate_1 main_table_stove_front_region": 129} | None |
| CUSTOM_T26 | goal_pair_05_08 | False | 600 | 1/2 | {"on plate_1 main_table_stove_front_region": 134} | None |
| CUSTOM_T27 | goal_pair_05_09 | False | 600 | 0/2 | {} | None |
| CUSTOM_T28 | goal_pair_06_07 | False | 600 | 1/2 | {"on cream_cheese_1 akita_black_bowl_1": 141} | None |
| CUSTOM_T29 | goal_pair_06_09 | False | 600 | 1/2 | {"on wine_bottle_1 wine_rack_1_top_region": 127} | None |
| CUSTOM_T30 | goal_pair_07_08 | False | 600 | 1/2 | {"on akita_black_bowl_1 plate_1": 102} | None |
| CUSTOM_T31 | goal_pair_07_09 | False | 600 | 1/2 | {"on wine_bottle_1 wine_rack_1_top_region": 149} | None |
| CUSTOM_T32 | goal_pair_08_09 | False | 600 | 1/2 | {"on wine_bottle_1 wine_rack_1_top_region": 124} | None |

### object-pilot

| task | bddl | success | steps | subtasks | first_true_step | switch |
|---|---|---:|---:|---|---|---|
| CUSTOM_T0 | object_pair_00_01 | False | 560 | 1/2 | {"in alphabet_soup_1 basket_1_contain_region": 145} | None |
| CUSTOM_T1 | object_pair_00_03 | False | 560 | 1/2 | {"in alphabet_soup_1 basket_1_contain_region": 139} | None |
| CUSTOM_T2 | object_pair_00_04 | False | 560 | 1/2 | {"in alphabet_soup_1 basket_1_contain_region": 170} | None |
| CUSTOM_T3 | object_pair_08_09 | False | 560 | 1/2 | {"in chocolate_pudding_1 basket_1_contain_region": 152} | None |

## 6. 异常项

- ⚠️ `cross_process_observation_variation`: {"count": 5, "examples": [{"runs": ["diag", "diag2", "pilot(and)", "smoke", "staged", "sweep-compatible", "variant(then/swap)"], "n_obs": 2}, {"runs": ["diag2", "pilot(and)", "sweep-compatible"], "n_obs": 2}, {"runs": ["pilot(and)", "sweep-compatible"], "n_obs": 4}], "note": "同一个 init+scene 的 stabilized_sim_state 全部一致（custom init patch 生效且确定）；但早期批次与后期批次对相同 sim state 渲染出的 observation sha 不同 （可能是不同启动 shell 的 MUJOCO_GL/渲染后端差异），属于跨进程渲染可复现性 caveat，不影响本审计的 success/steps/subtask 复算。"}
- ⚠️ `lead_summary_classification_lookup_issues`: {"count": 7, "examples": [{"run": "variant(then/swap)", "task_key": "CUSTOM_T5", "lead": "compatible", "independent": "object_validated=True,union=7"}, {"run": "variant(then/swap)", "task_key": "CUSTOM_T6", "lead": "compatible", "independent": "object_validated=True,union=9"}, {"run": "staged", "task_key": "CUSTOM_T3", "lead": "compatible", "independent": "object_validated=True,union=7"}, {"run": "object-pilot", "task_key": "CUSTOM_T0", "lead": "compatible", "independent": "object_validated=True

## 7. 检查清单

| # | category | check | critical | result |
|---:|---|---|---|---|
| 1 | goal | `goal_pairs_45_files_exist` | yes | ✅ |
| 2 | goal | `goal_pairs_meta_45` | yes | ✅ |
| 3 | goal | `goal_pairs_unique_ids` | yes | ✅ |
| 4 | goal | `goal_pairs_unique_unordered_pairs` | yes | ✅ |
| 5 | goal | `goal_pairs_i_lt_j` | yes | ✅ |
| 6 | goal | `goal_pairs_classification_counts_33_5_7` | yes | ✅ |
| 7 | goal | `goal_classification_conflict_recomputed_exact` | yes | ✅ |
| 8 | goal | `goal_classification_hard_atom_candidates` | no | ✅ |
| 9 | goal | `goal_pairs_bddl_parse_structure_language_2atoms` | yes | ✅ |
| 10 | goal | `goal_pairs_init_shape_50x79_and_source` | yes | ✅ |
| 11 | goal | `goal_pairs_scene_sections_equal_templates` | yes | ✅ |
| 12 | goal | `goal_static_validation_claims_45_45` | yes | ✅ |
| 13 | goal | `goal_static_validation_initial_success_false` | yes | ✅ |
| 14 | goal | `goal_pairs_checksums_137_ok` | yes | ✅ |
| 15 | phrasings | `phrasings_then_45_files` | yes | ✅ |
| 16 | phrasings | `phrasings_then_metadata_45` | no | ✅ |
| 17 | phrasings | `phrasings_andthen_45_files` | yes | ✅ |
| 18 | phrasings | `phrasings_andthen_metadata_45` | no | ✅ |
| 19 | phrasings | `phrasings_90_language_and_scene_consistent` | yes | ✅ |
| 20 | phrasings | `phrasings_static_validation_45_45_each` | yes | ✅ |
| 21 | phrasings | `phrasings_checksums_271_ok` | yes | ✅ |
| 22 | object | `object_pairs_30_files` | yes | ✅ |
| 23 | object | `object_pairs_union_10_10_10` | yes | ✅ |
| 24 | object | `object_pairs_bddl_structure_language` | yes | ✅ |
| 25 | object | `object_pairs_init_shapes_123_136_149` | yes | ✅ |
| 26 | object | `object_validation_claims_30_30` | yes | ✅ |
| 27 | object | `object_scout_2_prototypes` | yes | ✅ |
| 28 | object | `object_scout_prototypes_parse` | yes | ✅ |
| 29 | object | `object_scout_feasibility_present` | yes | ✅ |
| 30 | staging | `staged_4_files` | yes | ✅ |
| 31 | staging | `staged_bddl_language_and_plan_consistent` | yes | ✅ |
| 32 | staging | `sweep_dir_33_compatible_pairs` | yes | ✅ |
| 33 | staging | `sweep_33_bddl_copied_correctly` | yes | ✅ |
| 34 | staging | `object_pilot_dir_4_pairs` | yes | ✅ |
| 35 | staging | `object_pilot_4_copied_correctly` | yes | ✅ |
| 36 | staging | `shadow_is_baseline_pristine_shadow` | yes | ✅ |
| 37 | staging | `runtime_overlay_custom_init_and_wait10_patch` | yes | ✅ |
| 38 | staging | `prep_smoke_pair_semantically_equal_artifact_00_01` | yes | ✅ |
| 39 | staging | `prep_pilot_pairs_match_builder_9` | yes | ✅ |
| 40 | staging | `prep_variant_pairs_match_builder_7` | yes | ✅ |
| 41 | staging | `prep_diag_controls_match_builder_5` | yes | ✅ |
| 42 | staging | `prep_diag2_controls_match_builder_4` | yes | ✅ |
| 43 | staging | `prep_staged_copies_exact` | yes | ✅ |
| 44 | staging | `prep_object_pilot_copies_exact_4` | yes | ✅ |
| 45 | staging | `prep_sweep_copies_exact_33` | yes | ✅ |
| 46 | dynamic | `smoke_episode_count_1` | no | ✅ |
| 47 | dynamic | `smoke_custom_t_mapping_ok` | yes | ✅ |
| 48 | dynamic | `smoke_trace_per_episode` | yes | ✅ |
| 49 | dynamic | `smoke_trace_offset_10_stabilization` | no | ✅ |
| 50 | dynamic | `smoke_trace_summary_first_true_consistent` | no | ✅ |
| 51 | dynamic | `smoke_videos_present` | no | ✅ |
| 52 | dynamic | `smoke_videos_nonzero` | no | ✅ |
| 53 | dynamic | `pilot(and)_episode_count_9` | no | ✅ |
| 54 | dynamic | `pilot(and)_custom_t_mapping_ok` | yes | ✅ |
| 55 | dynamic | `pilot(and)_trace_per_episode` | yes | ✅ |
| 56 | dynamic | `pilot(and)_trace_offset_10_stabilization` | no | ✅ |
| 57 | dynamic | `pilot(and)_trace_summary_first_true_consistent` | no | ✅ |
| 58 | dynamic | `pilot(and)_videos_present` | no | ✅ |
| 59 | dynamic | `pilot(and)_videos_nonzero` | no | ✅ |
| 60 | dynamic | `variant(then/swap)_episode_count_7` | no | ✅ |
| 61 | dynamic | `variant(then/swap)_custom_t_mapping_ok` | yes | ✅ |
| 62 | dynamic | `variant(then/swap)_trace_per_episode` | yes | ✅ |
| 63 | dynamic | `variant(then/swap)_trace_offset_10_stabilization` | no | ✅ |
| 64 | dynamic | `variant(then/swap)_trace_summary_first_true_consistent` | no | ✅ |
| 65 | dynamic | `variant(then/swap)_videos_present` | no | ✅ |
| 66 | dynamic | `variant(then/swap)_videos_nonzero` | no | ✅ |
| 67 | dynamic | `diag_episode_count_5` | no | ✅ |
| 68 | dynamic | `diag_custom_t_mapping_ok` | yes | ✅ |
| 69 | dynamic | `diag_trace_per_episode` | yes | ✅ |
| 70 | dynamic | `diag_trace_offset_10_stabilization` | no | ✅ |
| 71 | dynamic | `diag_trace_summary_first_true_consistent` | no | ✅ |
| 72 | dynamic | `diag_videos_present` | no | ✅ |
| 73 | dynamic | `diag_videos_nonzero` | no | ✅ |
| 74 | dynamic | `diag2_episode_count_4` | no | ✅ |
| 75 | dynamic | `diag2_custom_t_mapping_ok` | yes | ✅ |
| 76 | dynamic | `diag2_trace_per_episode` | yes | ✅ |
| 77 | dynamic | `diag2_trace_offset_10_stabilization` | no | ✅ |
| 78 | dynamic | `diag2_trace_summary_first_true_consistent` | no | ✅ |
| 79 | dynamic | `diag2_videos_present` | no | ✅ |
| 80 | dynamic | `diag2_videos_nonzero` | no | ✅ |
| 81 | dynamic | `staged_episode_count_4` | no | ✅ |
| 82 | dynamic | `staged_custom_t_mapping_ok` | yes | ✅ |
| 83 | dynamic | `staged_trace_per_episode` | yes | ✅ |
| 84 | dynamic | `staged_trace_offset_10_stabilization` | no | ✅ |
| 85 | dynamic | `staged_trace_summary_first_true_consistent` | no | ✅ |
| 86 | dynamic | `staged_videos_present` | no | ✅ |
| 87 | dynamic | `staged_videos_nonzero` | no | ✅ |
| 88 | dynamic | `sweep-compatible_episode_count_33` | no | ✅ |
| 89 | dynamic | `sweep-compatible_custom_t_mapping_ok` | yes | ✅ |
| 90 | dynamic | `sweep-compatible_trace_per_episode` | yes | ✅ |
| 91 | dynamic | `sweep-compatible_trace_offset_10_stabilization` | no | ✅ |
| 92 | dynamic | `sweep-compatible_trace_summary_first_true_consistent` | no | ✅ |
| 93 | dynamic | `sweep-compatible_videos_present` | no | ✅ |
| 94 | dynamic | `sweep-compatible_videos_nonzero` | no | ✅ |
| 95 | dynamic | `object-pilot_episode_count_4` | no | ✅ |
| 96 | dynamic | `object-pilot_custom_t_mapping_ok` | yes | ✅ |
| 97 | dynamic | `object-pilot_trace_per_episode` | yes | ✅ |
| 98 | dynamic | `object-pilot_trace_offset_10_stabilization` | no | ✅ |
| 99 | dynamic | `object-pilot_trace_summary_first_true_consistent` | no | ✅ |
| 100 | dynamic | `object-pilot_videos_present` | no | ✅ |
| 101 | dynamic | `object-pilot_videos_nonzero` | no | ✅ |
| 102 | dynamic | `smoke_replan_steps_10` | no | ✅ |
| 103 | dynamic | `smoke_steps_within_max_600` | no | ✅ |
| 104 | dynamic | `smoke_one_trace_per_episode` | no | ✅ |
| 105 | dynamic | `smoke_trace_summary_steps_consistent` | no | ✅ |
| 106 | dynamic | `smoke_trace_stage_semantics` | no | ✅ |
| 107 | dynamic | `smoke_no_extra_trace_files` | no | ✅ |
| 108 | dynamic | `smoke_covers_expected_pairs` | yes | ✅ |
| 109 | dynamic | `pilot(and)_replan_steps_10` | no | ✅ |
| 110 | dynamic | `pilot(and)_steps_within_max_600` | no | ✅ |
| 111 | dynamic | `pilot(and)_one_trace_per_episode` | no | ✅ |
| 112 | dynamic | `pilot(and)_trace_summary_steps_consistent` | no | ✅ |
| 113 | dynamic | `pilot(and)_trace_stage_semantics` | no | ✅ |
| 114 | dynamic | `pilot(and)_no_extra_trace_files` | no | ✅ |
| 115 | dynamic | `pilot(and)_covers_expected_pairs` | yes | ✅ |
| 116 | dynamic | `variant(then/swap)_replan_steps_10` | no | ✅ |
| 117 | dynamic | `variant(then/swap)_steps_within_max_600` | no | ✅ |
| 118 | dynamic | `variant(then/swap)_one_trace_per_episode` | no | ✅ |
| 119 | dynamic | `variant(then/swap)_trace_summary_steps_consistent` | no | ✅ |
| 120 | dynamic | `variant(then/swap)_trace_stage_semantics` | no | ✅ |
| 121 | dynamic | `variant(then/swap)_no_extra_trace_files` | no | ✅ |
| 122 | dynamic | `variant(then/swap)_covers_expected_pairs` | yes | ✅ |
| 123 | dynamic | `diag_replan_steps_10` | no | ✅ |
| 124 | dynamic | `diag_steps_within_max_600` | no | ✅ |
| 125 | dynamic | `diag_one_trace_per_episode` | no | ✅ |
| 126 | dynamic | `diag_trace_summary_steps_consistent` | no | ✅ |
| 127 | dynamic | `diag_trace_stage_semantics` | no | ✅ |
| 128 | dynamic | `diag_no_extra_trace_files` | no | ✅ |
| 129 | dynamic | `diag_covers_expected_pairs` | yes | ✅ |
| 130 | dynamic | `diag2_replan_steps_10` | no | ✅ |
| 131 | dynamic | `diag2_steps_within_max_600` | no | ✅ |
| 132 | dynamic | `diag2_one_trace_per_episode` | no | ✅ |
| 133 | dynamic | `diag2_trace_summary_steps_consistent` | no | ✅ |
| 134 | dynamic | `diag2_trace_stage_semantics` | no | ✅ |
| 135 | dynamic | `diag2_no_extra_trace_files` | no | ✅ |
| 136 | dynamic | `diag2_covers_expected_pairs` | yes | ✅ |
| 137 | dynamic | `staged_replan_steps_10` | no | ✅ |
| 138 | dynamic | `staged_steps_within_max_600` | no | ✅ |
| 139 | dynamic | `staged_one_trace_per_episode` | no | ✅ |
| 140 | dynamic | `staged_trace_summary_steps_consistent` | no | ✅ |
| 141 | dynamic | `staged_trace_stage_semantics` | no | ✅ |
| 142 | dynamic | `staged_no_extra_trace_files` | no | ✅ |
| 143 | dynamic | `staged_covers_expected_pairs` | yes | ✅ |
| 144 | dynamic | `sweep-compatible_replan_steps_10` | no | ✅ |
| 145 | dynamic | `sweep-compatible_steps_within_max_600` | no | ✅ |
| 146 | dynamic | `sweep-compatible_one_trace_per_episode` | no | ✅ |
| 147 | dynamic | `sweep-compatible_trace_summary_steps_consistent` | no | ✅ |
| 148 | dynamic | `sweep-compatible_trace_stage_semantics` | no | ✅ |
| 149 | dynamic | `sweep-compatible_no_extra_trace_files` | no | ✅ |
| 150 | dynamic | `sweep-compatible_covers_expected_pairs` | yes | ✅ |
| 151 | dynamic | `object-pilot_replan_steps_5` | no | ✅ |
| 152 | dynamic | `object-pilot_steps_within_max_560` | no | ✅ |
| 153 | dynamic | `object-pilot_one_trace_per_episode` | no | ✅ |
| 154 | dynamic | `object-pilot_trace_summary_steps_consistent` | no | ✅ |
| 155 | dynamic | `object-pilot_trace_stage_semantics` | no | ✅ |
| 156 | dynamic | `object-pilot_no_extra_trace_files` | no | ✅ |
| 157 | dynamic | `object-pilot_covers_expected_pairs` | yes | ✅ |
| 158 | dynamic | `all_episodes_environment_seed_1000` | no | ✅ |
| 159 | dynamic | `stabilized_sim_state_consistent_per_init_and_scene` | yes | ✅ |
| 160 | dynamic | `within_run_stabilized_obs_deterministic` | no | ✅ |
| 161 | logs | `smoke_log_episode_count` | no | ✅ |
| 162 | logs | `smoke_log_vs_results_success` | no | ✅ |
| 163 | logs | `smoke_log_no_traceback` | no | ✅ |
| 164 | logs | `smoke_log_max_steps_expected` | no | ✅ |
| 165 | logs | `pilot(and)_log_episode_count` | no | ✅ |
| 166 | logs | `pilot(and)_log_vs_results_success` | no | ✅ |
| 167 | logs | `pilot(and)_log_no_traceback` | no | ✅ |
| 168 | logs | `pilot(and)_log_max_steps_expected` | no | ✅ |
| 169 | logs | `variant(then/swap)_log_episode_count` | no | ✅ |
| 170 | logs | `variant(then/swap)_log_vs_results_success` | no | ✅ |
| 171 | logs | `variant(then/swap)_log_no_traceback` | no | ✅ |
| 172 | logs | `variant(then/swap)_log_max_steps_expected` | no | ✅ |
| 173 | logs | `diag_log_episode_count` | no | ✅ |
| 174 | logs | `diag_log_vs_results_success` | no | ✅ |
| 175 | logs | `diag_log_no_traceback` | no | ✅ |
| 176 | logs | `diag_log_max_steps_expected` | no | ✅ |
| 177 | logs | `diag2_log_episode_count` | no | ✅ |
| 178 | logs | `diag2_log_vs_results_success` | no | ✅ |
| 179 | logs | `diag2_log_no_traceback` | no | ✅ |
| 180 | logs | `diag2_log_max_steps_expected` | no | ✅ |
| 181 | logs | `staged_log_episode_count` | no | ✅ |
| 182 | logs | `staged_log_vs_results_success` | no | ✅ |
| 183 | logs | `staged_log_no_traceback` | no | ✅ |
| 184 | logs | `staged_log_max_steps_expected` | no | ✅ |
| 185 | logs | `sweep-compatible_log_episode_count` | no | ✅ |
| 186 | logs | `sweep-compatible_log_vs_results_success` | no | ✅ |
| 187 | logs | `sweep-compatible_log_no_traceback` | no | ✅ |
| 188 | logs | `sweep-compatible_log_max_steps_expected` | no | ✅ |
| 189 | logs | `sweep-compatible_done_marker` | no | ✅ |
| 190 | logs | `object-pilot_log_episode_count` | no | ✅ |
| 191 | logs | `object-pilot_log_vs_results_success` | no | ✅ |
| 192 | logs | `object-pilot_log_no_traceback` | no | ✅ |
| 193 | logs | `object-pilot_log_max_steps_expected` | no | ✅ |
| 194 | logs | `object-pilot_done_marker` | no | ✅ |
| 195 | dynamic | `smoke_video_probe_ok` | no | ✅ |
| 196 | dynamic | `pilot(and)_video_probe_ok` | no | ✅ |
| 197 | dynamic | `variant(then/swap)_video_probe_ok` | no | ✅ |
| 198 | dynamic | `diag_video_probe_ok` | no | ✅ |
| 199 | dynamic | `diag2_video_probe_ok` | no | ✅ |
| 200 | dynamic | `staged_video_probe_ok` | no | ✅ |
| 201 | dynamic | `sweep-compatible_video_probe_ok` | no | ✅ |
| 202 | dynamic | `object-pilot_video_probe_ok` | no | ✅ |
| 203 | conclusions | `staged_switch_step_consistent_with_atom0` | no | ✅ |
| 204 | summary | `lead_summary_rows_match_independent_counts` | yes | ✅ |
| 205 | summary | `lead_summary_fields_match_independent` | no | ✅ |
| 206 | conclusions | `conclusion_single_instruction_high_failure` | yes | ✅ |
| 207 | conclusions | `conclusion_failure_mode_exactly_one_subtask` | yes | ✅ |
| 208 | conclusions | `conclusion_phrasing_variants_no_improvement` | yes | ✅ |
| 209 | conclusions | `conclusion_staged_partially_effective` | yes | ✅ |
| 210 | conclusions | `conclusion_init_source_effect` | yes | ✅ |
| 211 | conclusions | `conclusion_single_subtask_controls` | yes | ✅ |

## 8. 结论与可信度

- **独立复算可信度**：静态产物（45 pair / 90 phrasing / 30 object / 2 prototype / staging 33+4+4）与动态运行（67 episodes）的关键检查 **全部通过**；与 Lead `combined-dynamic-summary.json` 的公共行字段差异 0 条→ 实验记录的 success/steps/subtasks/switch_step 数字**可以作为报告可信证据**（以本审计独立数字为准）。
- **结论**：① 单指令组合任务整体成功率极低（GOAL 2/49≈4%，OBJECT 0/4），主要失败模式是“完成恰好 1 个子任务后停滞”，不是完全无法操作；② then/andthen/swap 措辞变体没有改善；③ staged 分阶段指令可以救回部分 pair（>0 且 <全部），说明合并任务物理可行、瓶颈主要在一次性指令的组合理解；④ 单子任务对照与 init 源对照支持上述解释；⑤ 静态产物（BDDL/init/分类）质量与 Lead 声明一致；⑥ sweep 33 对唯一成功的是 goal_pair_04_07（397 步，先放碗到柜顶再开炉子），说明存在少量“可顺序完成”的 compatible pair。

限定与剩余风险：
- 每个 pair 仅 **1 个 seed × 1 episode**（sweep 33 pairs 提供覆盖广度，但逐对成功率是 1 样本估计，且每个 pair 只有 init 0）；
- 合并场景/自定义 BDDL 非官方 LIBERO benchmark；动态验证用 max_steps=600 / replan=10（object-pilot 560/5），不是官方 220–520/5 协议，不能与官方 pi05 数字横向对比；
- trace 的 `step` 是 0-based env control step，包含开头 10 个 stabilization steps；因此 first_true_step + 10 ≈ 策略执行步（results.steps 已与 trace 行数逐条核对：rows = 10 + steps）；
- Lead 汇总的 `status` 分类字段有 7 处 pair-id 查找问题（object pair 经 `object_pair_` 前缀别名命中 goal pair 的 status；不影响 success/steps）；建议修 `analyze_combined.py` 后再对外引用 object 行的分类列；
- sweep-compatible / object-pilot 的完整性与逐对数字以本审计最终版为准（若本报告 status=partial，则对应 run 仍 pending）。

建议：
- 对关键 pair（尤其 staged 成功/失败对照与 conflict/hard 分类）做多 seed 复跑（如 seed 0–4），报告成功率区间而非单点；
- staged 协议扩展到更多 compatible pair，并做 switch-step 敏感性（切换太早/太晚的影响）；
- object-pilot 完成后补充 OBJECT 组合的难度结论（union 7/8/9 与成功率关系）；
- 引用本实验时同时引用本审计的独立数字与限定，不要直接使用 Lead summary 的 status 分类列。

## 9. 复现

```bash
/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python \
  .tmp/combined-audit/audit_combined.py --mode audit
```

- 静态 BDDL/init 解析在子进程中用 pristine LIBERO shadow（`runs/libero-std-baseline-20261019/shadow`，`LIBERO_CONFIG_PATH` 同目录）+ `torch.load(..., weights_only=False)` 完成；
- 动态部分只读取 results.json / *-traces/*.jsonl / logs 与视频，未创建仿真环境、未加载模型、未用 GPU；
- 未写入 `runs/combined-tasks-20261019/` 任何内容。

