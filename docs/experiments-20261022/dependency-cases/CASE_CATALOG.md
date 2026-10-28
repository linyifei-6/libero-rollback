# LIBERO-GOAL 依赖型双子任务 case 目录（2026-10-22 审核版）

> 目的：拓展 **“put A on/in B, and put B on/in C”** 类型的双子任务（A→B→C 链式依赖）。
> 本次先做第一项工作：45 个反向 ordered 组合 + 原生依赖重点组多 seed 动态验证；新 goal 候选留待后续。
> 数据来源：LIBERO 原始 GOAL bddl/init、`docs/experiments-20261019/`（上一轮 45 对结果与 10 任务清单）。

## 0. 摘要与已确认口径

**任务定义**：task = 环境 + 初始状态 + goal 判定 + instruction；instruction 变体也是候选任务，成功即成立

**可行性判定**：max_steps 内任一 seed 成功即可视为可行任务（多 seed 用于报告稳定性，不作为硬门槛）

| 项目 | 数量 |
|---|---|
| GOAL 单任务 | 10 |
| 原有 ordered 组合（i<j，上一轮 45 对） | 45 |
| 反向 ordered 组合（j→i，本次补齐的 45 对） | 45 |
| **本次运行候选任务（去重）** | **50**（45 反向 + focus 6，去重后 50） |
| 原生依赖 case（container_move 5 / reverse_dependency 5 / turnon 1） | 11 |
| 新 goal 候选（后续再做） | 8 |
| instruction 变体（候选任务，成功即可作为新任务） | 5 |

**关键结论（按最新审核口径）**

- **instruction 变体是候选任务**：task = 环境 + init + goal + instruction；不同 instruction 顺序/措辞若跑通，即可作为新任务对待。
  例：若 06-01 成功而 01-06 失败，则 06-01 可以算作新任务（不是“仅对照”）。
- 多 seed 的成功判定**放宽**：只要 max_steps 内**任一 seed 成功**即视为可行任务；多 seed 用于报告稳定性/成功率，不作为硬门槛。
- 上一轮的单 seed 结果仅作参考：06-08 成功（单 seed，318/278 步），04-07 也成功但视频显示是探索/重试后的偶然成功。
- plate 移动只保留 **push the plate to the front of the stove** 一条；三段链**纳入候选**。

## 1. LIBERO-GOAL 10 个单任务

| idx | task 名 | 官方 language | BDDL goal atoms |
|---|---|---|---|
| 0 | open_the_middle_drawer_of_the_cabinet | open the middle drawer of the cabinet | (Open wooden_cabinet_1_middle_region) |
| 1 | put_the_bowl_on_the_stove | put the bowl on the stove | (On akita_black_bowl_1 flat_stove_1_cook_region) |
| 2 | put_the_wine_bottle_on_top_of_the_cabinet | put the wine bottle on top of the cabinet | (On wine_bottle_1 wooden_cabinet_1_top_side) |
| 3 | open_the_top_drawer_and_put_the_bowl_inside | open the top drawer and put the bowl inside | (In akita_black_bowl_1 wooden_cabinet_1_top_region) |
| 4 | put_the_bowl_on_top_of_the_cabinet | put the bowl on top of the cabinet | (On akita_black_bowl_1 wooden_cabinet_1_top_side) |
| 5 | push_the_plate_to_the_front_of_the_stove | push the plate to the front of the stove | (On plate_1 main_table_stove_front_region) |
| 6 | put_the_cream_cheese_in_the_bowl | put the cream cheese in the bowl | (On cream_cheese_1 akita_black_bowl_1) |
| 7 | turn_on_the_stove | turn on the stove | (Turnon flat_stove_1) |
| 8 | put_the_bowl_on_the_plate | put the bowl on the plate | (On akita_black_bowl_1 plate_1) |
| 9 | put_the_wine_bottle_on_the_rack | put the wine bottle on the rack | (On wine_bottle_1 wine_rack_1_top_region) |

说明：场景是同一个 kitchen/living-room 场景，可动物体只有 `akita_black_bowl_1`、`cream_cheese_1`、`wine_bottle_1`、`plate_1`；
`plate_1` 是“可推动”（任务 5）而不是常规抓取物体；`wooden_cabinet_1`、`flat_stove_1`、`wine_rack_1`、`main_table` 为 fixture。

## 2. 45 + 45 个 ordered 组合（候选任务）

> 说明：反向 ordered pair 与 canonical（i<j）**goal/init 相同**、instruction 顺序不同。
> 按最新口径，它们是**候选任务**：实际是否作为新任务，由多 seed 动态结果决定（任一 seed 成功即可）。

### 2.1 原有 45 个 ordered 组合（i<j，上一轮已评估 goal）

| pair_id | 顺序 | instruction | goal atoms | 依赖模式 | 上一轮结果 |
|---|---|---|---|---|---|
| 00_01 | 0→1 | open the middle drawer of the cabinet and put the bowl on the stove | (Open wooden_cabinet_1_middle_region)<br>(On akita_black_bowl_1 flat_stove_1_cook_region) | — | 失败（3 条；最多完成子任务 1） |
| 00_02 | 0→2 | open the middle drawer of the cabinet and put the wine bottle on top of the cabinet | (Open wooden_cabinet_1_middle_region)<br>(On wine_bottle_1 wooden_cabinet_1_top_side) | — | 失败（2 条；最多完成子任务 1） |
| 00_03 | 0→3 | open the middle drawer of the cabinet and open the top drawer and put the bowl inside | (Open wooden_cabinet_1_middle_region)<br>(In akita_black_bowl_1 wooden_cabinet_1_top_region) | — | 失败（1 条；最多完成子任务 1） |
| 00_04 | 0→4 | open the middle drawer of the cabinet and put the bowl on top of the cabinet | (Open wooden_cabinet_1_middle_region)<br>(On akita_black_bowl_1 wooden_cabinet_1_top_side) | — | 失败（1 条；最多完成子任务 1） |
| 00_05 | 0→5 | open the middle drawer of the cabinet and push the plate to the front of the stove | (Open wooden_cabinet_1_middle_region)<br>(On plate_1 main_table_stove_front_region) | — | 失败（1 条；最多完成子任务 1） |
| 00_06 | 0→6 | open the middle drawer of the cabinet and put the cream cheese in the bowl | (Open wooden_cabinet_1_middle_region)<br>(On cream_cheese_1 akita_black_bowl_1) | — | 失败（1 条；最多完成子任务 1） |
| 00_07 | 0→7 | open the middle drawer of the cabinet and turn on the stove | (Open wooden_cabinet_1_middle_region)<br>(Turnon flat_stove_1) | — | 成功（3 条；成功步数 579；runs: pilot(and),staged,sweep-compatible） |
| 00_08 | 0→8 | open the middle drawer of the cabinet and put the bowl on the plate | (Open wooden_cabinet_1_middle_region)<br>(On akita_black_bowl_1 plate_1) | — | 失败（1 条；最多完成子任务 1） |
| 00_09 | 0→9 | open the middle drawer of the cabinet and put the wine bottle on the rack | (Open wooden_cabinet_1_middle_region)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 失败（2 条；最多完成子任务 1） |
| 01_02 | 1→2 | put the bowl on the stove and put the wine bottle on top of the cabinet | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(On wine_bottle_1 wooden_cabinet_1_top_side) | — | 失败（1 条；最多完成子任务 1） |
| 01_03 | 1→3 | put the bowl on the stove and open the top drawer and put the bowl inside | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(In akita_black_bowl_1 wooden_cabinet_1_top_region) | — | 未测（上一轮未覆盖） |
| 01_04 | 1→4 | put the bowl on the stove and put the bowl on top of the cabinet | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(On akita_black_bowl_1 wooden_cabinet_1_top_side) | — | 未测（上一轮未覆盖） |
| 01_05 | 1→5 | put the bowl on the stove and push the plate to the front of the stove | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(On plate_1 main_table_stove_front_region) | — | 未测（上一轮未覆盖） |
| 01_06 | 1→6 | put the bowl on the stove and put the cream cheese in the bowl | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(On cream_cheese_1 akita_black_bowl_1) | 反向依赖（先移动 B → 再把 A 放 B 上） | 未测（上一轮未覆盖） |
| 01_07 | 1→7 | put the bowl on the stove and turn on the stove | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(Turnon flat_stove_1) | — | 失败（1 条；最多完成子任务 1） |
| 01_08 | 1→8 | put the bowl on the stove and put the bowl on the plate | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(On akita_black_bowl_1 plate_1) | — | 未测（上一轮未覆盖） |
| 01_09 | 1→9 | put the bowl on the stove and put the wine bottle on the rack | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 失败（1 条；最多完成子任务 1） |
| 02_03 | 2→3 | put the wine bottle on top of the cabinet and open the top drawer and put the bowl inside | (On wine_bottle_1 wooden_cabinet_1_top_side)<br>(In akita_black_bowl_1 wooden_cabinet_1_top_region) | — | 失败（2 条；最多完成子任务 1） |
| 02_04 | 2→4 | put the wine bottle on top of the cabinet and put the bowl on top of the cabinet | (On wine_bottle_1 wooden_cabinet_1_top_side)<br>(On akita_black_bowl_1 wooden_cabinet_1_top_side) | — | 失败（1 条；最多完成子任务 1） |
| 02_05 | 2→5 | put the wine bottle on top of the cabinet and push the plate to the front of the stove | (On wine_bottle_1 wooden_cabinet_1_top_side)<br>(On plate_1 main_table_stove_front_region) | — | 失败（1 条；最多完成子任务 1） |
| 02_06 | 2→6 | put the wine bottle on top of the cabinet and put the cream cheese in the bowl | (On wine_bottle_1 wooden_cabinet_1_top_side)<br>(On cream_cheese_1 akita_black_bowl_1) | — | 失败（1 条；最多完成子任务 1） |
| 02_07 | 2→7 | put the wine bottle on top of the cabinet and turn on the stove | (On wine_bottle_1 wooden_cabinet_1_top_side)<br>(Turnon flat_stove_1) | — | 失败（1 条；最多完成子任务 1） |
| 02_08 | 2→8 | put the wine bottle on top of the cabinet and put the bowl on the plate | (On wine_bottle_1 wooden_cabinet_1_top_side)<br>(On akita_black_bowl_1 plate_1) | — | 失败（1 条；最多完成子任务 1） |
| 02_09 | 2→9 | put the wine bottle on top of the cabinet and put the wine bottle on the rack | (On wine_bottle_1 wooden_cabinet_1_top_side)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 失败（1 条；最多完成子任务 1） |
| 03_04 | 3→4 | open the top drawer and put the bowl inside and put the bowl on top of the cabinet | (In akita_black_bowl_1 wooden_cabinet_1_top_region)<br>(On akita_black_bowl_1 wooden_cabinet_1_top_side) | — | 未测（上一轮未覆盖） |
| 03_05 | 3→5 | open the top drawer and put the bowl inside and push the plate to the front of the stove | (In akita_black_bowl_1 wooden_cabinet_1_top_region)<br>(On plate_1 main_table_stove_front_region) | — | 失败（1 条；最多完成子任务 1） |
| 03_06 | 3→6 | open the top drawer and put the bowl inside and put the cream cheese in the bowl | (In akita_black_bowl_1 wooden_cabinet_1_top_region)<br>(On cream_cheese_1 akita_black_bowl_1) | 反向依赖（先移动 B → 再把 A 放 B 上） | 未测（上一轮未覆盖） |
| 03_07 | 3→7 | open the top drawer and put the bowl inside and turn on the stove | (In akita_black_bowl_1 wooden_cabinet_1_top_region)<br>(Turnon flat_stove_1) | — | 失败（1 条；最多完成子任务 0） |
| 03_08 | 3→8 | open the top drawer and put the bowl inside and put the bowl on the plate | (In akita_black_bowl_1 wooden_cabinet_1_top_region)<br>(On akita_black_bowl_1 plate_1) | — | 未测（上一轮未覆盖） |
| 03_09 | 3→9 | open the top drawer and put the bowl inside and put the wine bottle on the rack | (In akita_black_bowl_1 wooden_cabinet_1_top_region)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 失败（1 条；最多完成子任务 0） |
| 04_05 | 4→5 | put the bowl on top of the cabinet and push the plate to the front of the stove | (On akita_black_bowl_1 wooden_cabinet_1_top_side)<br>(On plate_1 main_table_stove_front_region) | — | 失败（1 条；最多完成子任务 1） |
| 04_06 | 4→6 | put the bowl on top of the cabinet and put the cream cheese in the bowl | (On akita_black_bowl_1 wooden_cabinet_1_top_side)<br>(On cream_cheese_1 akita_black_bowl_1) | 反向依赖（先移动 B → 再把 A 放 B 上） | 未测（上一轮未覆盖） |
| 04_07 | 4→7 | put the bowl on top of the cabinet and turn on the stove | (On akita_black_bowl_1 wooden_cabinet_1_top_side)<br>(Turnon flat_stove_1) | — | 成功（1 条；成功步数 397；runs: sweep-compatible） |
| 04_08 | 4→8 | put the bowl on top of the cabinet and put the bowl on the plate | (On akita_black_bowl_1 wooden_cabinet_1_top_side)<br>(On akita_black_bowl_1 plate_1) | — | 未测（上一轮未覆盖） |
| 04_09 | 4→9 | put the bowl on top of the cabinet and put the wine bottle on the rack | (On akita_black_bowl_1 wooden_cabinet_1_top_side)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 失败（1 条；最多完成子任务 0） |
| 05_06 | 5→6 | push the plate to the front of the stove and put the cream cheese in the bowl | (On plate_1 main_table_stove_front_region)<br>(On cream_cheese_1 akita_black_bowl_1) | 反向依赖（先移动 B → 再把 A 放 B 上） | 失败（2 条；最多完成子任务 1） |
| 05_07 | 5→7 | push the plate to the front of the stove and turn on the stove | (On plate_1 main_table_stove_front_region)<br>(Turnon flat_stove_1) | — | 失败（2 条；最多完成子任务 1） |
| 05_08 | 5→8 | push the plate to the front of the stove and put the bowl on the plate | (On plate_1 main_table_stove_front_region)<br>(On akita_black_bowl_1 plate_1) | — | 失败（1 条；最多完成子任务 1） |
| 05_09 | 5→9 | push the plate to the front of the stove and put the wine bottle on the rack | (On plate_1 main_table_stove_front_region)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 失败（1 条；最多完成子任务 0） |
| 06_07 | 6→7 | put the cream cheese in the bowl and turn on the stove | (On cream_cheese_1 akita_black_bowl_1)<br>(Turnon flat_stove_1) | — | 失败（1 条；最多完成子任务 1） |
| 06_08 | 6→8 | put the cream cheese in the bowl and put the bowl on the plate | (On cream_cheese_1 akita_black_bowl_1)<br>(On akita_black_bowl_1 plate_1) | 容器移动（A 放 B 上/里 → B 移到 C） | 成功（1 条；成功步数 318；runs: pilot(and)） |
| 06_09 | 6→9 | put the cream cheese in the bowl and put the wine bottle on the rack | (On cream_cheese_1 akita_black_bowl_1)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 失败（1 条；最多完成子任务 1） |
| 07_08 | 7→8 | turn on the stove and put the bowl on the plate | (Turnon flat_stove_1)<br>(On akita_black_bowl_1 plate_1) | — | 失败（1 条；最多完成子任务 1） |
| 07_09 | 7→9 | turn on the stove and put the wine bottle on the rack | (Turnon flat_stove_1)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 失败（1 条；最多完成子任务 1） |
| 08_09 | 8→9 | put the bowl on the plate and put the wine bottle on the rack | (On akita_black_bowl_1 plate_1)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 成功（3 条；成功步数 390；runs: pilot(and),staged,sweep-compatible） |

### 2.2 本次补齐的 45 个反向 ordered 组合（j→i，本次正在跑多 seed）

| pair_id | 顺序 | instruction | goal atoms | 依赖模式 | 上一轮结果 |
|---|---|---|---|---|---|
| 01_00 | 1→0 | put the bowl on the stove and open the middle drawer of the cabinet | (Open wooden_cabinet_1_middle_region)<br>(On akita_black_bowl_1 flat_stove_1_cook_region) | — | 失败（3 条；最多完成子任务 1） |
| 02_00 | 2→0 | put the wine bottle on top of the cabinet and open the middle drawer of the cabinet | (Open wooden_cabinet_1_middle_region)<br>(On wine_bottle_1 wooden_cabinet_1_top_side) | — | 失败（2 条；最多完成子任务 1） |
| 03_00 | 3→0 | open the top drawer and put the bowl inside and open the middle drawer of the cabinet | (Open wooden_cabinet_1_middle_region)<br>(In akita_black_bowl_1 wooden_cabinet_1_top_region) | — | 失败（1 条；最多完成子任务 1） |
| 04_00 | 4→0 | put the bowl on top of the cabinet and open the middle drawer of the cabinet | (Open wooden_cabinet_1_middle_region)<br>(On akita_black_bowl_1 wooden_cabinet_1_top_side) | — | 失败（1 条；最多完成子任务 1） |
| 05_00 | 5→0 | push the plate to the front of the stove and open the middle drawer of the cabinet | (Open wooden_cabinet_1_middle_region)<br>(On plate_1 main_table_stove_front_region) | — | 失败（1 条；最多完成子任务 1） |
| 06_00 | 6→0 | put the cream cheese in the bowl and open the middle drawer of the cabinet | (Open wooden_cabinet_1_middle_region)<br>(On cream_cheese_1 akita_black_bowl_1) | — | 失败（1 条；最多完成子任务 1） |
| 07_00 | 7→0 | turn on the stove and open the middle drawer of the cabinet | (Open wooden_cabinet_1_middle_region)<br>(Turnon flat_stove_1) | — | 成功（3 条；成功步数 579；runs: pilot(and),staged,sweep-compatible） |
| 08_00 | 8→0 | put the bowl on the plate and open the middle drawer of the cabinet | (Open wooden_cabinet_1_middle_region)<br>(On akita_black_bowl_1 plate_1) | — | 失败（1 条；最多完成子任务 1） |
| 09_00 | 9→0 | put the wine bottle on the rack and open the middle drawer of the cabinet | (Open wooden_cabinet_1_middle_region)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 失败（2 条；最多完成子任务 1） |
| 02_01 | 2→1 | put the wine bottle on top of the cabinet and put the bowl on the stove | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(On wine_bottle_1 wooden_cabinet_1_top_side) | — | 失败（1 条；最多完成子任务 1） |
| 03_01 | 3→1 | open the top drawer and put the bowl inside and put the bowl on the stove | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(In akita_black_bowl_1 wooden_cabinet_1_top_region) | — | 未测（上一轮未覆盖） |
| 04_01 | 4→1 | put the bowl on top of the cabinet and put the bowl on the stove | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(On akita_black_bowl_1 wooden_cabinet_1_top_side) | — | 未测（上一轮未覆盖） |
| 05_01 | 5→1 | push the plate to the front of the stove and put the bowl on the stove | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(On plate_1 main_table_stove_front_region) | — | 未测（上一轮未覆盖） |
| 06_01 | 6→1 | put the cream cheese in the bowl and put the bowl on the stove | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(On cream_cheese_1 akita_black_bowl_1) | 容器移动（A 放 B 上/里 → B 移到 C） | 未测（上一轮未覆盖） |
| 07_01 | 7→1 | turn on the stove and put the bowl on the stove | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(Turnon flat_stove_1) | 先开火再放（Turnon F → 物体放 F） | 失败（1 条；最多完成子任务 1） |
| 08_01 | 8→1 | put the bowl on the plate and put the bowl on the stove | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(On akita_black_bowl_1 plate_1) | — | 未测（上一轮未覆盖） |
| 09_01 | 9→1 | put the wine bottle on the rack and put the bowl on the stove | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 失败（1 条；最多完成子任务 1） |
| 03_02 | 3→2 | open the top drawer and put the bowl inside and put the wine bottle on top of the cabinet | (On wine_bottle_1 wooden_cabinet_1_top_side)<br>(In akita_black_bowl_1 wooden_cabinet_1_top_region) | — | 失败（2 条；最多完成子任务 1） |
| 04_02 | 4→2 | put the bowl on top of the cabinet and put the wine bottle on top of the cabinet | (On wine_bottle_1 wooden_cabinet_1_top_side)<br>(On akita_black_bowl_1 wooden_cabinet_1_top_side) | — | 失败（1 条；最多完成子任务 1） |
| 05_02 | 5→2 | push the plate to the front of the stove and put the wine bottle on top of the cabinet | (On wine_bottle_1 wooden_cabinet_1_top_side)<br>(On plate_1 main_table_stove_front_region) | — | 失败（1 条；最多完成子任务 1） |
| 06_02 | 6→2 | put the cream cheese in the bowl and put the wine bottle on top of the cabinet | (On wine_bottle_1 wooden_cabinet_1_top_side)<br>(On cream_cheese_1 akita_black_bowl_1) | — | 失败（1 条；最多完成子任务 1） |
| 07_02 | 7→2 | turn on the stove and put the wine bottle on top of the cabinet | (On wine_bottle_1 wooden_cabinet_1_top_side)<br>(Turnon flat_stove_1) | — | 失败（1 条；最多完成子任务 1） |
| 08_02 | 8→2 | put the bowl on the plate and put the wine bottle on top of the cabinet | (On wine_bottle_1 wooden_cabinet_1_top_side)<br>(On akita_black_bowl_1 plate_1) | — | 失败（1 条；最多完成子任务 1） |
| 09_02 | 9→2 | put the wine bottle on the rack and put the wine bottle on top of the cabinet | (On wine_bottle_1 wooden_cabinet_1_top_side)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 失败（1 条；最多完成子任务 1） |
| 04_03 | 4→3 | put the bowl on top of the cabinet and open the top drawer and put the bowl inside | (In akita_black_bowl_1 wooden_cabinet_1_top_region)<br>(On akita_black_bowl_1 wooden_cabinet_1_top_side) | — | 未测（上一轮未覆盖） |
| 05_03 | 5→3 | push the plate to the front of the stove and open the top drawer and put the bowl inside | (In akita_black_bowl_1 wooden_cabinet_1_top_region)<br>(On plate_1 main_table_stove_front_region) | — | 失败（1 条；最多完成子任务 1） |
| 06_03 | 6→3 | put the cream cheese in the bowl and open the top drawer and put the bowl inside | (In akita_black_bowl_1 wooden_cabinet_1_top_region)<br>(On cream_cheese_1 akita_black_bowl_1) | 容器移动（A 放 B 上/里 → B 移到 C） | 未测（上一轮未覆盖） |
| 07_03 | 7→3 | turn on the stove and open the top drawer and put the bowl inside | (In akita_black_bowl_1 wooden_cabinet_1_top_region)<br>(Turnon flat_stove_1) | — | 失败（1 条；最多完成子任务 0） |
| 08_03 | 8→3 | put the bowl on the plate and open the top drawer and put the bowl inside | (In akita_black_bowl_1 wooden_cabinet_1_top_region)<br>(On akita_black_bowl_1 plate_1) | — | 未测（上一轮未覆盖） |
| 09_03 | 9→3 | put the wine bottle on the rack and open the top drawer and put the bowl inside | (In akita_black_bowl_1 wooden_cabinet_1_top_region)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 失败（1 条；最多完成子任务 0） |
| 05_04 | 5→4 | push the plate to the front of the stove and put the bowl on top of the cabinet | (On akita_black_bowl_1 wooden_cabinet_1_top_side)<br>(On plate_1 main_table_stove_front_region) | — | 失败（1 条；最多完成子任务 1） |
| 06_04 | 6→4 | put the cream cheese in the bowl and put the bowl on top of the cabinet | (On akita_black_bowl_1 wooden_cabinet_1_top_side)<br>(On cream_cheese_1 akita_black_bowl_1) | 容器移动（A 放 B 上/里 → B 移到 C） | 未测（上一轮未覆盖） |
| 07_04 | 7→4 | turn on the stove and put the bowl on top of the cabinet | (On akita_black_bowl_1 wooden_cabinet_1_top_side)<br>(Turnon flat_stove_1) | — | 成功（1 条；成功步数 397；runs: sweep-compatible） |
| 08_04 | 8→4 | put the bowl on the plate and put the bowl on top of the cabinet | (On akita_black_bowl_1 wooden_cabinet_1_top_side)<br>(On akita_black_bowl_1 plate_1) | — | 未测（上一轮未覆盖） |
| 09_04 | 9→4 | put the wine bottle on the rack and put the bowl on top of the cabinet | (On akita_black_bowl_1 wooden_cabinet_1_top_side)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 失败（1 条；最多完成子任务 0） |
| 06_05 | 6→5 | put the cream cheese in the bowl and push the plate to the front of the stove | (On plate_1 main_table_stove_front_region)<br>(On cream_cheese_1 akita_black_bowl_1) | 容器移动（A 放 B 上/里 → B 移到 C） | 失败（2 条；最多完成子任务 1） |
| 07_05 | 7→5 | turn on the stove and push the plate to the front of the stove | (On plate_1 main_table_stove_front_region)<br>(Turnon flat_stove_1) | — | 失败（2 条；最多完成子任务 1） |
| 08_05 | 8→5 | put the bowl on the plate and push the plate to the front of the stove | (On plate_1 main_table_stove_front_region)<br>(On akita_black_bowl_1 plate_1) | — | 失败（1 条；最多完成子任务 1） |
| 09_05 | 9→5 | put the wine bottle on the rack and push the plate to the front of the stove | (On plate_1 main_table_stove_front_region)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 失败（1 条；最多完成子任务 0） |
| 07_06 | 7→6 | turn on the stove and put the cream cheese in the bowl | (On cream_cheese_1 akita_black_bowl_1)<br>(Turnon flat_stove_1) | — | 失败（1 条；最多完成子任务 1） |
| 08_06 | 8→6 | put the bowl on the plate and put the cream cheese in the bowl | (On cream_cheese_1 akita_black_bowl_1)<br>(On akita_black_bowl_1 plate_1) | 反向依赖（先移动 B → 再把 A 放 B 上） | 成功（1 条；成功步数 318；runs: pilot(and)） |
| 09_06 | 9→6 | put the wine bottle on the rack and put the cream cheese in the bowl | (On cream_cheese_1 akita_black_bowl_1)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 失败（1 条；最多完成子任务 1） |
| 08_07 | 8→7 | put the bowl on the plate and turn on the stove | (Turnon flat_stove_1)<br>(On akita_black_bowl_1 plate_1) | — | 失败（1 条；最多完成子任务 1） |
| 09_07 | 9→7 | put the wine bottle on the rack and turn on the stove | (Turnon flat_stove_1)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 失败（1 条；最多完成子任务 1） |
| 09_08 | 9→8 | put the wine bottle on the rack and put the bowl on the plate | (On akita_black_bowl_1 plate_1)<br>(On wine_bottle_1 wine_rack_1_top_region) | — | 成功（3 条；成功步数 390；runs: pilot(and),staged,sweep-compatible） |

## 3. 原生依赖 case（GOAL 10 任务内部即可构成；均为候选任务）

依赖模式定义：

- **container_move**：第一个子任务把 A 放到 B（可动物体）上/里，第二个子任务把 B 移到 C；
- **turnon_then_place**：第一个子任务打开 fixture，第二个子任务把物体放到该 fixture 上；
- **reverse_dependency**：先移动 B，再把 A 放到 B 上（与 container_move 同 goal、顺序相反）。

### 3.1 原生依赖（container_move：A 放 B → B 移到 C）

| case | instruction | goal atoms | 上一轮结果 | 说明 |
|---|---|---|---|---|
| 06_08 | put the cream cheese in the bowl and put the bowl on the plate | (On cream_cheese_1 akita_black_bowl_1)<br>(On akita_black_bowl_1 plate_1) | 成功（1 条；成功步数 318；runs: pilot(and)） | 上一轮唯一成功过的 GOAL 组合之一（pilot 318 步；dependency 复测 278 步，seed-0） |
| 06_01 | put the cream cheese in the bowl and put the bowl on the stove | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(On cream_cheese_1 akita_black_bowl_1) | 未测（上一轮未覆盖） | 与反向 01_06 同 goal |
| 06_03 | put the cream cheese in the bowl and open the top drawer and put the bowl inside | (In akita_black_bowl_1 wooden_cabinet_1_top_region)<br>(On cream_cheese_1 akita_black_bowl_1) | 未测（上一轮未覆盖） | 与反向 03_06 同 goal |
| 06_04 | put the cream cheese in the bowl and put the bowl on top of the cabinet | (On akita_black_bowl_1 wooden_cabinet_1_top_side)<br>(On cream_cheese_1 akita_black_bowl_1) | 未测（上一轮未覆盖） | 与反向 04_06 同 goal |
| 06_05 | put the cream cheese in the bowl and push the plate to the front of the stove | (On plate_1 main_table_stove_front_region)<br>(On cream_cheese_1 akita_black_bowl_1) | 失败（2 条；最多完成子任务 1） | 用户口径加入 container_move：第二个子任务移动的是 plate（C=plate），B=bowl 本身未移动；按用户定义归入该组，语义上更接近场景级并行依赖 |

### 3.2 原生依赖（turnon_then_place：先开火，再放物体）

| case | instruction | goal atoms | 上一轮结果 | 说明 |
|---|---|---|---|---|
| 07_01 | turn on the stove and put the bowl on the stove | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(Turnon flat_stove_1) | 失败（1 条；最多完成子任务 1） | 与反向 01_07 同 goal |

### 3.3 反向依赖（先移动 B，再把 A 放到 B 上）

| case | instruction | goal atoms | 上一轮结果 | 说明 |
|---|---|---|---|---|
| 01_06 | put the bowl on the stove and put the cream cheese in the bowl | (On akita_black_bowl_1 flat_stove_1_cook_region)<br>(On cream_cheese_1 akita_black_bowl_1) | 未测（上一轮未覆盖） | 用户口径：reverse_dependency 组 |
| 03_06 | open the top drawer and put the bowl inside and put the cream cheese in the bowl | (In akita_black_bowl_1 wooden_cabinet_1_top_region)<br>(On cream_cheese_1 akita_black_bowl_1) | 未测（上一轮未覆盖） | 用户口径：reverse_dependency 组 |
| 04_06 | put the bowl on top of the cabinet and put the cream cheese in the bowl | (On akita_black_bowl_1 wooden_cabinet_1_top_side)<br>(On cream_cheese_1 akita_black_bowl_1) | 未测（上一轮未覆盖） | 用户口径：reverse_dependency 组 |
| 05_06 | push the plate to the front of the stove and put the cream cheese in the bowl | (On plate_1 main_table_stove_front_region)<br>(On cream_cheese_1 akita_black_bowl_1) | 失败（2 条；最多完成子任务 1） | 用户口径：reverse_dependency 组 |
| 08_06 | put the bowl on the plate and put the cream cheese in the bowl | (On cream_cheese_1 akita_black_bowl_1)<br>(On akita_black_bowl_1 plate_1) | 成功（1 条；成功步数 318；runs: pilot(and)） | 与 06_08 同 goal；该顺序在上一轮 pilot 中成功过（318 步，单 seed） |

## 4. 新 goal 候选（后续再做，本轮先聚焦第一项工作）

生成规则：B=`akita_black_bowl_1`、A=`cream_cheese_1` 固定；C 从 GOAL 场景 region/object 中枚举；
风险为静态物理判断（低/中/高），未跑动态。

### 4.1 新 goal 候选（待第一项工作完成后再做）

| case_id | 类型/模式 | instruction | goal atoms | risk | 建议 | 备注 |
|---|---|---|---|---|---|---|
| synthetic_dep_bowl_woodencabinet1middle | container_move | put the cream cheese on the bowl and open the middle drawer of the cabinet and put the bowl inside | (On cream_cheese_1 akita_black_bowl_1)<br>(In akita_black_bowl_1 wooden_cabinet_1_middle_region) | 中 | 备选 | 新 goal 组合：场景 region 存在；需生成 bddl 后做静态/动态验证 |
| synthetic_dep_bowl_woodencabinet1bottom | container_move | put the cream cheese on the bowl and open the bottom drawer of the cabinet and put the bowl inside | (On cream_cheese_1 akita_black_bowl_1)<br>(In akita_black_bowl_1 wooden_cabinet_1_bottom_region) | 中 | 备选 | 新 goal 组合：场景 region 存在；需生成 bddl 后做静态/动态验证 |
| synthetic_dep_bowl_winerack1top | container_move | put the cream cheese on the bowl and put the bowl on the wine rack | (On cream_cheese_1 akita_black_bowl_1)<br>(On akita_black_bowl_1 wine_rack_1_top_region) | 高 | 风险高/最后 | 新 goal 组合：场景 region 存在；需生成 bddl 后做静态/动态验证 |
| synthetic_dep_bowl_maintablestovefront | container_move | put the cream cheese on the bowl and put the bowl at the front of the stove | (On cream_cheese_1 akita_black_bowl_1)<br>(On akita_black_bowl_1 main_table_stove_front_region) | 中 | 备选 | 新 goal 组合：场景 region 存在；需生成 bddl 后做静态/动态验证 |
| synthetic_dep_plate_maintablestovefront | container_move_plate | put the cream cheese on the plate and push the plate to the front of the stove | (On cream_cheese_1 plate_1)<br>(On plate_1 main_table_stove_front_region) | 高 | 风险高/最后 | plate 是可推动物体（任务5）但非抓取物体；推动中 cheese 可能滑落 → 高风险 |
| synthetic_chain_cheese_bowl_plate_stove_front | extended_chain | put the cream cheese on the bowl, put the bowl on the plate, and push the plate to the front of the stove | (On cream_cheese_1 akita_black_bowl_1)<br>(On akita_black_bowl_1 plate_1)<br>(On plate_1 main_table_stove_front_region) | 高 | 纳入候选（三段链，高风险） | 三段链；600 步可能不够，建议 800–1000+ |
| synthetic_chain_cheese_bowl_stove_on | extended_chain | put the cream cheese on the bowl, put the bowl on the stove, and turn on the stove | (On cream_cheese_1 akita_black_bowl_1)<br>(On akita_black_bowl_1 flat_stove_1_cook_region)<br>(Turnon flat_stove_1) | 中 | 纳入候选（三段链，用户已确认） | 三段链；最后 turnon 是 GOAL 任务7 目标 |
| synthetic_chain_open_middle_bowl_cheese | extended_chain | open the middle drawer of the cabinet, put the bowl inside, and put the cream cheese on the bowl | (Open wooden_cabinet_1_middle_region)<br>(In akita_black_bowl_1 wooden_cabinet_1_middle_region)<br>(On cream_cheese_1 akita_black_bowl_1) | 高 | 纳入候选（三段链，高风险） | 含 open 原子；抽屉打开后放碗；碗在抽屉里再放 cheese 可能不可达 |

### 4.2 已有 goal 的 instruction 变体（**候选任务**：成功即可能作为新任务）

| case_id | instruction | goal atoms | 说明 |
|---|---|---|---|
| goal_pair_06_01 | put the cream cheese on the bowl and put the bowl on the stove | (On cream_cheese_1 akita_black_bowl_1)<br>(On akita_black_bowl_1 flat_stove_1_cook_region) | 与已有 pair 06_01 相同 goal（仅 instruction 顺序不同，不是新任务） |
| goal_pair_06_04 | put the cream cheese on the bowl and put the bowl on the top of the cabinet | (On cream_cheese_1 akita_black_bowl_1)<br>(On akita_black_bowl_1 wooden_cabinet_1_top_side) | 与已有 pair 06_04 相同 goal（仅 instruction 顺序不同，不是新任务） |
| goal_pair_06_08 | put the cream cheese on the bowl and put the bowl on the plate | (On cream_cheese_1 akita_black_bowl_1)<br>(On akita_black_bowl_1 plate_1) | 与已有 pair 06_08 相同 goal（仅 instruction 顺序不同，不是新任务） |
| goal_pair_06_03 | put the cream cheese on the bowl and open the top drawer of the cabinet and put the bowl inside | (On cream_cheese_1 akita_black_bowl_1)<br>(In akita_black_bowl_1 wooden_cabinet_1_top_region) | 与已有 pair 06_03 相同 goal（仅 instruction 顺序不同，不是新任务） |
| synthetic_chain_open_top_bowl_cheese | put the cream cheese on the bowl, open the top drawer of the cabinet, and put the bowl inside | (On cream_cheese_1 akita_black_bowl_1)<br>(In akita_black_bowl_1 wooden_cabinet_1_top_region) | 与 06_03 相同 goal（仅 instruction 多写明 open），不是新任务 |

### 4.3 用户审核排除的候选

| case_id | instruction | 排除原因 |
|---|---|---|
| synthetic_dep_plate_woodencabinet1topside | put the cream cheese on the plate and put the plate on the top of the cabinet | 用户审核：plate 移动只保留 push the plate to the front of the stove；本候选排除 |
| synthetic_dep_plate_flatstove1cook | put the cream cheese on the plate and put the plate on the stove | 用户审核：plate 移动只保留 push the plate to the front of the stove；本候选排除 |

## 5. 关于 04-07 的“幸运成功”：对任务扩充的启发

`goal_pair_04_07`（bowl on cabinet top + turn on stove）上一轮单 seed 成功（397 步），但从视频看：
完成 subtask1 后模型先去开了抽屉、又尝试多次才完成 subtask2——**不是干净的依赖链执行，而是探索/重试后的偶然成功**。启发：

1. 本实验按“任一 seed 成功即可行”放宽门槛找候选任务，但报告里要同时记录成功率与步数分布（避免把偶然成功当稳定任务）。
2. 组合任务的可解性更取决于“第二子任务是否在模型技能分布内 + 目标可达”，而不是语义依赖本身（04-07 的两个子任务都简单）。
3. 对 rollback 设计：模型自身有“失败→重试/乱探索”行为，注入点应避开探索期，或记录 exploration 步数作为协变量。

## 6. 关于顺序/paraphrase 变体的最新口径

- **修正**：instruction 变体是候选任务（task = 环境 + init + goal + instruction）；若某条 instruction 跑通，则它可以作为新任务。
  例如 06-01（put cream cheese on bowl, put bowl on stove）成功而 01-06 失败 → 06-01 可作为新任务；
  同理 06-03/06-04/06-05/06-08 与 01-06/03-06/04-06/05-06/08-06 各自独立判定。
- 文献上“VLA 对指令不敏感”解释的是**行为相似性**；本实验以动态结果为准，不预先排除 instruction 变体。

## 7. 本轮（第一项工作）执行情况与判定

| 批次 | 内容 | seeds | 状态 |
|---|---|---|---|
| native-focus | 01-06 / 03-06 / 04-06 / 05-06 / 08-06 / 06-08 | 0,1,2 | 运行中（`runs/reversed-multiseed-20261022`） |
| reversed-45 | 45 个反向 ordered 组合 | 0,1,2（分 3 个 run） | 排队中（focus 完成后自动开始） |

- 判定：**同一候选任务只要任一 seed 在 max_steps 内成功，即视为可行任务**；失败 seed 用于记录稳定性/失败模式。
- 报告：实验完成后按 `docs/html-report-prompt.md` v1.1 生成（固定左侧导航、§2.7 拆解、§5 附录、视频证据）。

## 8. 后续（第二项工作）候选建议

1. **新 goal 候选 10 条**（§4.1）：plate 移动只保留 push-to-stove-front；三段链已确认纳入候选；优先级按 risk 从低到高。
2. 先做**静态验证 + 单 seed 试探**（同一“任一 seed 成功”口径），再决定是否补多 seed。
3. 通过后并入 baseline 任务池；任务池按 instruction 粒度记录（同 goal 不同 instruction 可分别成立）。

## 9. 审核结论（已确认）

1. plate 移动 3 条 → **只保留 push the plate to the front of the stove**；其余 2 条排除（见 §4.3）。
2. 三段链 → **纳入候选**。
3. 多 seed 判定 → **max_steps 内任一 seed 成功即视为可行任务**，不做 2/3 硬门槛。
4. 原生依赖 → **不是“仅对照”**：哪个 instruction 跑通，哪个就作为新任务（例：06-01 成功而 01-06 失败 → 06-01 成立）。

---

_生成脚本：`runs/expand-tasks-20261022/artifacts/dependency-cases/build_cases.py`（数据）与 `render_cases_md.py`（本文）；本文件为静态目录，动态结果以 `runs/reversed-multiseed-20261022/` 为准。_
