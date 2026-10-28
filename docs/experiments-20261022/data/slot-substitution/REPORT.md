# LIBERO-10 场景内「保结构槽位替换」新双子任务候选（CPU 静态构造）

> 目标：在**同一 LIBERO-10 场景内**替换目标物体/容器/区域，批量构造新的两段式双子任务 baseline 候选，供 Lead 用 pi05 做动态筛选。
>
> 产物目录：`/home/tarowang/workspace/roboot/libero-rollback/runs/expand-tasks-20261022/artifacts/slot-substitution`
> 生成脚本：`scripts/build_slot_candidates.py`（v1.0.0，可重入）
> 执行环境：CPU-only，shadow 原版 LIBERO 包 + libero-runtime overlay；未加载任何策略模型、未使用 GPU（`CUDA_VISIBLE_DEVICES=""`，`MUJOCO_GL=osmesa`）。

## 1. 结论摘要

| 项目 | 结果 |
|---|---|
| 候选总数 | **45**（目标 ≥35，达标）|
| 覆盖场景 | 9 个 LIBERO-10 场景 |
| 风险分布 | low 36 / medium 5 / high 4 |
| BDDL 解析 | 45/45 通过；goal 原子数 2–3：全部满足 |
| env 实例化冒烟 | 45/45 通过；初始 `check_success()` 全为 False：是 |
| 静态验证失败项 | 无 |
| GPU 首轮建议 | phase A 每场景代表 9 个候选（见 §8）|

## 2. 背景与目标

pi05 在 10 个 LIBERO-10 原始任务上 baseline **40/40 成功**（结构/语言/场景都在训练分布内），而跨任务随机组合的双子任务单指令只有 **2/49** 成功（完成一个子任务后停滞）。本任务不再跨场景拼接，而是**在同一场景内做目标槽位替换**：保留原任务的两段式结构、官方语言风格、以及 `:regions/:fixtures/:objects/:init` 场景定义，只替换「哪个物体/容器/区域作为目标」，使新任务对模型更接近训练分布，预期 baseline 可解率更高。

## 3. 方法与生成规则

1. **模板**：每个候选取该场景的源 LIBERO-10 bddl 为模板（同场景多任务时共用同一静态模板）；
2. **只替换三段**：`:goal`（2–3 个原子）、`:language`（官方风格组合语言）、`:obj_of_interest`（目标原子的 object/region 所属对象/夹具并集）；其余段逐字节保持（脚本对替换前后做断言）；
3. **init 不变**：二进制拷贝源任务的 `.pruned_init`，作为同名 sibling 与 bddl 同目录（`<candidate_id>.pruned_init`），可直接 `--custom-bddl-dir` 使用；
4. **槽位合法性**：所有目标原子只引用该场景已有 objects / regions / fixtures；脚本逐原子校验引用存在性；
5. **风险标注**：low = 与原任务同结构、同类别物体的槽位替换；medium = 引入训练分布外的物体-区域配对或次序；high = 存在空间/几何/碰撞明显风险的组合（逐条给出原因）。

## 4. 场景与候选统计

| 场景 | 源任务（benchmark idx）| 候选数 | 风险分布 |
|---|---|---|---|
| LIVING_ROOM_SCENE2 | `LIVING_ROOM_SCENE2_put_both_the_alphabet_soup_and_the_tomato_sauce_in_the_basket`（idx 0）| 19 | low 19 / medium 0 / high 0 |
| KITCHEN_SCENE3 | `KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it`（idx 2）| 2 | low 0 / medium 1 / high 1 |
| KITCHEN_SCENE4 | `KITCHEN_SCENE4_put_the_black_bowl_in_the_bottom_drawer_of_the_cabinet_and_close_it`（idx 3）| 3 | low 0 / medium 1 / high 2 |
| LIVING_ROOM_SCENE5 | `LIVING_ROOM_SCENE5_put_the_white_mug_on_the_left_plate_and_put_the_yellow_and_white_mug_on_the_right_plate`（idx 4）| 5 | low 5 / medium 0 / high 0 |
| STUDY_SCENE1 | `STUDY_SCENE1_pick_up_the_book_and_place_it_in_the_back_compartment_of_the_caddy`（idx 5）| 4 | low 1 / medium 3 / high 0 |
| LIVING_ROOM_SCENE6 | `LIVING_ROOM_SCENE6_put_the_white_mug_on_the_plate_and_put_the_chocolate_pudding_to_the_right_of_the_plate`（idx 6）| 3 | low 3 / medium 0 / high 0 |
| LIVING_ROOM_SCENE1 | `LIVING_ROOM_SCENE1_put_both_the_alphabet_soup_and_the_cream_cheese_box_in_the_basket`（idx 7）| 5 | low 5 / medium 0 / high 0 |
| KITCHEN_SCENE8 | `KITCHEN_SCENE8_put_both_moka_pots_on_the_stove`（idx 8）| 2 | low 2 / medium 0 / high 0 |
| KITCHEN_SCENE6 | `KITCHEN_SCENE6_put_the_yellow_and_white_mug_in_the_microwave_and_close_it`（idx 9）| 2 | low 1 / medium 0 / high 1 |

## 5. 候选清单（按场景）

### LIVING_ROOM_SCENE2（19 个）

| candidate_id | risk | goal 原子数 | 语言 |
|---|---|---|---|
| `lr2_soup_cheese` | low | 2 | put both the alphabet soup and the cream cheese box in the basket |
| `lr2_soup_ketchup` | low | 2 | put both the alphabet soup and the ketchup in the basket |
| `lr2_soup_juice` | low | 2 | put both the alphabet soup and the orange juice in the basket |
| `lr2_soup_milk` | low | 2 | put both the alphabet soup and the milk in the basket |
| `lr2_soup_butter` | low | 2 | put both the alphabet soup and the butter in the basket |
| `lr2_cheese_tomato` | low | 2 | put both the cream cheese box and the tomato sauce in the basket |
| `lr2_cheese_ketchup` | low | 2 | put both the cream cheese box and the ketchup in the basket |
| `lr2_cheese_juice` | low | 2 | put both the cream cheese box and the orange juice in the basket |
| `lr2_cheese_milk` | low | 2 | put both the cream cheese box and the milk in the basket |
| `lr2_tomato_ketchup` | low | 2 | put both the tomato sauce and the ketchup in the basket |
| `lr2_tomato_juice` | low | 2 | put both the tomato sauce and the orange juice in the basket |
| `lr2_tomato_milk` | low | 2 | put both the tomato sauce and the milk in the basket |
| `lr2_tomato_butter` | low | 2 | put both the tomato sauce and the butter in the basket |
| `lr2_ketchup_juice` | low | 2 | put both the ketchup and the orange juice in the basket |
| `lr2_ketchup_milk` | low | 2 | put both the ketchup and the milk in the basket |
| `lr2_ketchup_butter` | low | 2 | put both the ketchup and the butter in the basket |
| `lr2_juice_milk` | low | 2 | put both the orange juice and the milk in the basket |
| `lr2_juice_butter` | low | 2 | put both the orange juice and the butter in the basket |
| `lr2_milk_butter` | low | 2 | put both the milk and the butter in the basket |

### KITCHEN_SCENE3（2 个）

| candidate_id | risk | goal 原子数 | 语言 |
|---|---|---|---|
| `k3_frypan_on_stove` | medium | 2 | turn on the stove and put the frying pan on it |
| `k3_moka_and_frypan_on_stove` | high | 3 | turn on the stove and put the moka pot and the frying pan on it |

### KITCHEN_SCENE4（3 个）

| candidate_id | risk | goal 原子数 | 语言 |
|---|---|---|---|
| `k4_wine_bottle_bottom_close` | high | 2 | put the wine bottle in the bottom drawer of the cabinet and close it |
| `k4_bowl_middle_close` | medium | 2 | put the black bowl in the middle drawer of the cabinet and close it |
| `k4_wine_bottle_middle_close` | high | 2 | put the wine bottle in the middle drawer of the cabinet and close it |

### LIVING_ROOM_SCENE5（5 个）

| candidate_id | risk | goal 原子数 | 语言 |
|---|---|---|---|
| `lr5_porcelain_left_red_right` | low | 2 | put the white mug on the left plate and put the red coffee mug on the right plate |
| `lr5_red_left_porcelain_right` | low | 2 | put the red coffee mug on the left plate and put the white mug on the right plate |
| `lr5_red_left_yellow_white_right` | low | 2 | put the red coffee mug on the left plate and put the yellow and white mug on the right plate |
| `lr5_yellow_white_left_porcelain_right` | low | 2 | put the yellow and white mug on the left plate and put the white mug on the right plate |
| `lr5_yellow_white_left_red_right` | low | 2 | put the yellow and white mug on the left plate and put the red coffee mug on the right plate |

### STUDY_SCENE1（4 个）

| candidate_id | risk | goal 原子数 | 语言 |
|---|---|---|---|
| `study_book_back_mug_right_comp` | medium | 2 | pick up the book and place it in the back compartment of the caddy and put the yellow and white mug in the right compartment of the caddy |
| `study_book_front_mug_left_comp` | medium | 2 | pick up the book and place it in the front compartment of the caddy and put the yellow and white mug in the left compartment of the caddy |
| `study_book_front_mug_right_comp` | medium | 2 | pick up the book and place it in the front compartment of the caddy and put the yellow and white mug in the right compartment of the caddy |
| `study_book_back_mug_table_right` | low | 2 | pick up the book and place it in the back compartment of the caddy and put the yellow and white mug to the right of the caddy |

### LIVING_ROOM_SCENE6（3 个）

| candidate_id | risk | goal 原子数 | 语言 |
|---|---|---|---|
| `lr6_red_plate_pudding_right` | low | 2 | put the red coffee mug on the plate and put the chocolate pudding to the right of the plate |
| `lr6_white_plate_red_right` | low | 2 | put the white mug on the plate and put the red coffee mug to the right of the plate |
| `lr6_red_plate_white_right` | low | 2 | put the red coffee mug on the plate and put the white mug to the right of the plate |

### LIVING_ROOM_SCENE1（5 个）

| candidate_id | risk | goal 原子数 | 语言 |
|---|---|---|---|
| `lr1_soup_tomato` | low | 2 | put both the alphabet soup and the tomato sauce in the basket |
| `lr1_soup_ketchup` | low | 2 | put both the alphabet soup and the ketchup in the basket |
| `lr1_cheese_tomato` | low | 2 | put both the cream cheese box and the tomato sauce in the basket |
| `lr1_cheese_ketchup` | low | 2 | put both the cream cheese box and the ketchup in the basket |
| `lr1_tomato_ketchup` | low | 2 | put both the tomato sauce and the ketchup in the basket |

### KITCHEN_SCENE8（2 个）

| candidate_id | risk | goal 原子数 | 语言 |
|---|---|---|---|
| `k8_right_pot_on_stove` | low | 2 | put the right moka pot on the stove and turn it on |
| `k8_left_pot_on_stove` | low | 2 | put the left moka pot on the stove and turn it on |

### KITCHEN_SCENE6（2 个）

| candidate_id | risk | goal 原子数 | 语言 |
|---|---|---|---|
| `k6_porcelain_mug_microwave_close` | low | 2 | put the white mug in the microwave and close it |
| `k6_both_mugs_microwave_close` | high | 3 | put the white mug and the yellow and white mug in the microwave and close it |

## 6. 风险标注明细

### 6.1 medium / high 候选逐条原因

- **`k3_frypan_on_stove`** [medium]：frying pan 比 moka pot 更大更重, 放到 cook_region 的接触/姿态更紧, 抓取与放置难度上升; 结构与 predicate 完全同源 (Turnon + On cook_region)。
- **`k3_moka_and_frypan_on_stove`** [high]：两件锅具同时放进同一 cook_region: 空间拥挤、互相碰撞, 且需在 turnon 后保持两物体均在区域内的姿态; 训练分布内从未出现。
- **`k4_wine_bottle_bottom_close`** [high]：酒瓶高度可能超过抽屉内净空, 放入/关闭抽屉时存在穿插与碰撞风险; 原任务只用 black bowl (矮) 验证过 bottom drawer, 分布外。
- **`k4_bowl_middle_close`** [medium]：middle 抽屉区域存在且碗尺寸适配; 但原任务仅 bottom 抽屉在训练分布内, 中层抽屉的开启/关闭时机与可达性需动态确认。
- **`k4_wine_bottle_middle_close`** [high]：酒瓶高度 + 中层抽屉可达性双重风险; 瓶子可能放不进或关闭时碰撞, 分布外。
- **`k6_both_mugs_microwave_close`** [high]：两个 mug 同时放入 microwave heating region: 空间狭窄、易互相碰撞, 且可能关不上门; 分布外。
- **`study_book_back_mug_right_comp`** [medium]：第一原子与原任务一致; 第二原子要求 mug 进入 caddy 右隔间: 隔间宽度/深度是否容纳 mug 未知 (训练分布只含 book→back compartment), 但区域与 In predicate 已存在。
- **`study_book_front_mug_left_comp`** [medium]：front/left 隔间区域均存在, 但原任务只把 book 放进 back 隔间: front 隔间几何较浅、mug 体积适配未知; 属于分布外组合。
- **`study_book_front_mug_right_comp`** [medium]：两个非原配隔间组合: front 隔间 + mug 进 right 隔间, 几何适配与可达性未在训练分布内。

### 6.2 low 候选的统一说明

low 候选均为**与原任务完全同构**的槽位替换：目标原子 predicate/区域与源任务一致，只替换同类别物体（grocery、mug、moka pot 等），物体与区域均在场景内已被 pi05 训练过。逐条原因见 `catalog.json` 的 `risk_reason` 字段。

## 7. 静态验证结果

每个候选执行两类验证（CPU-only、串行）：

1. **BDDL 解析**：`BDDLUtils.robosuite_parse_problem` + `BDDLUtils.get_problem_info`；
2. **env 实例化冒烟**：`OffScreenRenderEnv(bddl_file_name=..., camera_heights=256, camera_widths=256)` → `seed(1000)` → `reset()` → `set_init_state(init[0])` → `check_success()` → `env.env.parsed_problem["goal_state"]` → `close()`。

### 7.1 断言逐项统计

| 检查项 | 通过/总数 |
|---|---|
| `bddl_exists` | 45/45 |
| `init_sibling_exists` | 45/45 |
| `patched_sections_unique` | 45/45 |
| `no_double_open_paren` | 45/45 |
| `only_three_sections_changed` | 45/45 |
| `parse_ok` | 45/45 |
| `goal_atom_count_2_or_3` | 45/45 |
| `goal_atoms_match_expected` | 45/45 |
| `language_matches_expected` | 45/45 |
| `obj_of_interest_matches_expected` | 45/45 |
| `regions_match_source` | 45/45 |
| `fixtures_match_source` | 45/45 |
| `objects_match_source` | 45/45 |
| `init_state_match_source` | 45/45 |
| `atom_references_exist` | 45/45 |
| `init_sha256_matches_source` | 45/45 |
| `init_sha256_matches_record` | 45/45 |
| `init_shape_ok` | 45/45 |
| `env_goal_atom_count_2_or_3` | 45/45 |
| `env_goal_atoms_match_parsed` | 45/45 |

### 7.2 结果与耗时

- 通过率：**45/45**；失败项：无
- 初始 `check_success()` 全部 False：是；冒烟总尝试 45 次，需要重试的候选：无
- 解析耗时：总计 0.023 s，min/median/max = 0.0/0.001/0.001 s
- 冒烟耗时（含 env 构造+reset+set_init_state）：总计 233.331 s，min/median/max = 4.046/5.259/6.83 s
- **异常项：无**（45 个候选全部通过解析与 env 冒烟；无跳过项）

> 局限：静态验证只保证场景/BDDL 合法、语言正确、env 可构造、初始未满足目标；**不证明 pi05 可解或物体真能放入目标区域**（例如酒瓶进抽屉、双 mug 进微波炉的实际几何可行性），需由 Lead 用 GPU 动态筛选确认。

## 8. 建议 GPU 筛选顺序

按「low risk 优先 + 每场景先取代表」组织，分阶段跑（每个候选先 1 个 seed，`max-steps 600`）：

| 阶段 | 数量 | 说明 |
|---|---|---|
| A 每场景代表 | 9 | 每个场景先跑 1 个代表（优先 low risk；无 low 的场景取 medium 代表），快速判断哪些场景的新组合可解 |
| B 剩余 low risk | 29 | 覆盖全部同构低风险组合，估计新任务的可解率上限 |
| C 剩余 medium risk | 3 | 训练分布外但理论可行的组合（含 caddy 隔间、中层抽屉等）|
| D high risk | 4 | 几何/空间风险最高的组合（酒瓶进抽屉、双锅/双 mug 同区域），用于标注失败模式 |

### 8.1 Phase A（首轮建议，按顺序）

- `lr2_soup_cheese` [low] put both the alphabet soup and the cream cheese box in the basket
- `k3_frypan_on_stove` [medium] turn on the stove and put the frying pan on it
- `k4_bowl_middle_close` [medium] put the black bowl in the middle drawer of the cabinet and close it
- `lr5_porcelain_left_red_right` [low] put the white mug on the left plate and put the red coffee mug on the right plate
- `study_book_back_mug_table_right` [low] pick up the book and place it in the back compartment of the caddy and put the yellow and white mug to the right of the caddy
- `lr6_red_plate_pudding_right` [low] put the red coffee mug on the plate and put the chocolate pudding to the right of the plate
- `lr1_soup_tomato` [low] put both the alphabet soup and the tomato sauce in the basket
- `k8_right_pot_on_stove` [low] put the right moka pot on the stove and turn it on
- `k6_porcelain_mug_microwave_close` [low] put the white mug in the microwave and close it

### 8.2 Phase B（剩余 low risk，按顺序）

- `lr2_soup_ketchup`、`lr2_soup_juice`、`lr2_soup_milk`、`lr2_soup_butter`、`lr2_cheese_tomato`、`lr2_cheese_ketchup`、`lr2_cheese_juice`、`lr2_cheese_milk`、`lr2_tomato_ketchup`、`lr2_tomato_juice`、`lr2_tomato_milk`、`lr2_tomato_butter`、`lr2_ketchup_juice`、`lr2_ketchup_milk`、`lr2_ketchup_butter`、`lr2_juice_milk`、`lr2_juice_butter`、`lr2_milk_butter`、`lr1_soup_ketchup`、`lr1_cheese_tomato`、`lr1_cheese_ketchup`、`lr1_tomato_ketchup`、`lr5_red_left_porcelain_right`、`lr5_red_left_yellow_white_right`、`lr5_yellow_white_left_porcelain_right`、`lr5_yellow_white_left_red_right`、`lr6_white_plate_red_right`、`lr6_red_plate_white_right`、`k8_left_pot_on_stove`

### 8.3 Phase C（剩余 medium risk）

- `study_book_back_mug_right_comp`、`study_book_front_mug_left_comp`、`study_book_front_mug_right_comp`

### 8.4 Phase D（high risk）

- `k3_moka_and_frypan_on_stove`、`k4_wine_bottle_bottom_close`、`k4_wine_bottle_middle_close`、`k6_both_mugs_microwave_close`

### 8.5 完整优先级列表（candidate_id，从高到低）

- `lr2_soup_cheese`、`k3_frypan_on_stove`、`k4_bowl_middle_close`、`lr5_porcelain_left_red_right`、`study_book_back_mug_table_right`、`lr6_red_plate_pudding_right`、`lr1_soup_tomato`、`k8_right_pot_on_stove`、`k6_porcelain_mug_microwave_close`、`lr2_soup_ketchup`、`lr2_soup_juice`、`lr2_soup_milk`、`lr2_soup_butter`、`lr2_cheese_tomato`、`lr2_cheese_ketchup`、`lr2_cheese_juice`、`lr2_cheese_milk`、`lr2_tomato_ketchup`、`lr2_tomato_juice`、`lr2_tomato_milk`、`lr2_tomato_butter`、`lr2_ketchup_juice`、`lr2_ketchup_milk`、`lr2_ketchup_butter`、`lr2_juice_milk`、`lr2_juice_butter`、`lr2_milk_butter`、`lr1_soup_ketchup`、`lr1_cheese_tomato`、`lr1_cheese_ketchup`、`lr1_tomato_ketchup`、`lr5_red_left_porcelain_right`、`lr5_red_left_yellow_white_right`、`lr5_yellow_white_left_porcelain_right`、`lr5_yellow_white_left_red_right`、`lr6_white_plate_red_right`、`lr6_red_plate_white_right`、`k8_left_pot_on_stove`、`study_book_back_mug_right_comp`、`study_book_front_mug_left_comp`、`study_book_front_mug_right_comp`、`k3_moka_and_frypan_on_stove`、`k4_wine_bottle_bottom_close`、`k4_wine_bottle_middle_close`、`k6_both_mugs_microwave_close`

### 8.6 运行方式建议

```bash
$PY prep/run_combined_baseline.py \
    --runtime-root runs/expand-tasks-20261022/runtime \
    --bddl-dir runs/expand-tasks-20261022/artifacts/slot-substitution/bddl \
    --bddl-pattern '<phase候选过滤后的目录或全部 *.bddl>' \
    --seed-ids 0 --max-steps 600 --replan-steps 10 --video
```

`bddl/` 内每个候选 bddl 旁都有同名 sibling `.pruned_init`（源任务 init），overlay runner 会自动加载为固定初始状态；bddl 的 `:language` 即 policy instruction，可直接按 candidate_id 对照结果。

## 9. 与原始 10 个任务的差异、风险与下一步

1. **差异**：新候选与原任务共享同一场景与同一批 objects/regions/fixtures，只替换目标槽位与组合语言；因此比跨场景组合更接近训练分布，但仍存在模型未见过的「物体-目标区域」搭配。
2. **场景覆盖**：LIVING_ROOM_SCENE2 贡献 19 个 basket 组合（该场景 8 物体中 2 条原任务已覆盖）；LIVING_ROOM_SCENE1 +5；LIVING_ROOM_SCENE5 mug→plate +5；其余场景各 2–4 个。
3. **主要风险**（动态验证重点观察）：酒瓶进柜抽屉（高度/碰撞）、双锅/双 mug 同区域（空间拥挤）、mug 进 caddy 隔间（隔间宽度未知）、middle 抽屉（可达性未训练）。
4. **下一步**：Lead 按 §8 顺序跑 pi05 baseline；建议先 A 阶段 10 个代表，若某场景代表失败则该场景低风险候选可降低优先级；成功后用 B 阶段估计整体可解率上限。
5. **数据用途**：候选通过动态筛选后可作为后续「双子任务 baseline 可解集」，用于验证模型在组合任务上的真实能力边界。

## 10. 产物清单

| 路径 | 说明 | 数量 |
|---|---|---|
| `bddl/<candidate_id>.bddl` | 候选 BDDL | 45 |
| `bddl/<candidate_id>.pruned_init` | sibling init（源任务 init 二进制拷贝）| 45 |
| `catalog.json` | 候选机读清单（id/scene/源任务/goal atoms/语言/risk/risk_reason/init 来源/sha256）| 1 |
| `static-validation.json` | 逐候选验证明细 + 汇总 | 1 |
| `checksums.sha256` | bddl/init/catalog 产物哈希 | 1 |
| `scripts/build_slot_candidates.py` | 可重入生成+验证脚本 | 1 |
| `REPORT.md` | 本报告 | 1 |

## 11. 可重入性

脚本可重复执行：每次先清理 `bddl/` 下旧的 `*.bddl` / `*.pruned_init` 再按确定性规则重写；`bddl/`、`catalog.json`、`checksums.sha256` 内容确定（不含时间戳），重复运行 SHA256 一致；`static-validation.json` 与本文中的耗时统计随机器负载有微小波动。
