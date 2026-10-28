# LIBERO_GOAL 双子任务 45 对清单

- 套件: `LIBERO_GOAL` (benchmark `task_order_index=0`，非文件名字母序)
- 任务数: 10；无序对 (i<j): 45
- 生成脚本: `scripts/build_goal_pairs.py` (v1.0.0)
- 产物目录: `/home/tarowang/workspace/roboot/libero-rollback/runs/combined-tasks-20261019/artifacts/goal-pairs`
- 分类统计: conflict 7 / hard 5 / compatible 33
- 场景同构校验: :regions/:fixtures/:objects/:init 在 10 个任务间完全一致 (scene_fingerprint=6ed41dc58c1095a0…)，init 形状统一为 [50, 79]

## 分类规则

- **conflict**: 同一被操作物体被要求处于两个不同目标位置 (单刚体不可能同时满足): akita_black_bowl_1 的目标集合 = benchmark idx [1, 3, 4, 8] 两两冲突; wine_bottle_1 = benchmark idx [2, 9] 冲突。
- **hard**: cream_cheese_1 On akita_black_bowl_1 (idx 6) 与碗位置目标 [1, 3, 4, 8] 组合: 需先把碗放到最终位置再把奶酪放上去 (或搬运带奶酪的碗, 奶酪在碗面上易滑落), 次序受限、接触脆弱, 可共存但预期成功率偏低。
- **hard**: plate_1 推到 main_table_stove_front_region (idx 5) 与碗放到 flat_stove_1_cook_region (idx 1) 组合: 两目标区域空间相邻, 推盘路径与炉体/炉上碗存在碰撞、遮挡风险, 需要精细次序与间隙。
- **compatible**: 两个目标分别作用于不同被操作物体与不同目标位置 (不存在同一物体的异位要求), 目标原子可同时成立; 个别组合存在有利次序, 在 reason 中给出次序提示。

## 45 对总表

| # | pair_id | i | j | 任务 i | 任务 j | 组合指令 | 分类 |
|---|---|---|---|---|---|---|---|
| 1 | `00_01` | 0 | 1 | `open_the_middle_drawer_of_the_cabinet` | `put_the_bowl_on_the_stove` | open the middle drawer of the cabinet and put the bowl on the stove | **compatible** |
| 2 | `00_02` | 0 | 2 | `open_the_middle_drawer_of_the_cabinet` | `put_the_wine_bottle_on_top_of_the_cabinet` | open the middle drawer of the cabinet and put the wine bottle on top of the cabinet | **compatible** |
| 3 | `00_03` | 0 | 3 | `open_the_middle_drawer_of_the_cabinet` | `open_the_top_drawer_and_put_the_bowl_inside` | open the middle drawer of the cabinet and open the top drawer and put the bowl inside | **compatible** |
| 4 | `00_04` | 0 | 4 | `open_the_middle_drawer_of_the_cabinet` | `put_the_bowl_on_top_of_the_cabinet` | open the middle drawer of the cabinet and put the bowl on top of the cabinet | **compatible** |
| 5 | `00_05` | 0 | 5 | `open_the_middle_drawer_of_the_cabinet` | `push_the_plate_to_the_front_of_the_stove` | open the middle drawer of the cabinet and push the plate to the front of the stove | **compatible** |
| 6 | `00_06` | 0 | 6 | `open_the_middle_drawer_of_the_cabinet` | `put_the_cream_cheese_in_the_bowl` | open the middle drawer of the cabinet and put the cream cheese in the bowl | **compatible** |
| 7 | `00_07` | 0 | 7 | `open_the_middle_drawer_of_the_cabinet` | `turn_on_the_stove` | open the middle drawer of the cabinet and turn on the stove | **compatible** |
| 8 | `00_08` | 0 | 8 | `open_the_middle_drawer_of_the_cabinet` | `put_the_bowl_on_the_plate` | open the middle drawer of the cabinet and put the bowl on the plate | **compatible** |
| 9 | `00_09` | 0 | 9 | `open_the_middle_drawer_of_the_cabinet` | `put_the_wine_bottle_on_the_rack` | open the middle drawer of the cabinet and put the wine bottle on the rack | **compatible** |
| 10 | `01_02` | 1 | 2 | `put_the_bowl_on_the_stove` | `put_the_wine_bottle_on_top_of_the_cabinet` | put the bowl on the stove and put the wine bottle on top of the cabinet | **compatible** |
| 11 | `01_03` | 1 | 3 | `put_the_bowl_on_the_stove` | `open_the_top_drawer_and_put_the_bowl_inside` | put the bowl on the stove and open the top drawer and put the bowl inside | **conflict** |
| 12 | `01_04` | 1 | 4 | `put_the_bowl_on_the_stove` | `put_the_bowl_on_top_of_the_cabinet` | put the bowl on the stove and put the bowl on top of the cabinet | **conflict** |
| 13 | `01_05` | 1 | 5 | `put_the_bowl_on_the_stove` | `push_the_plate_to_the_front_of_the_stove` | put the bowl on the stove and push the plate to the front of the stove | **hard** |
| 14 | `01_06` | 1 | 6 | `put_the_bowl_on_the_stove` | `put_the_cream_cheese_in_the_bowl` | put the bowl on the stove and put the cream cheese in the bowl | **hard** |
| 15 | `01_07` | 1 | 7 | `put_the_bowl_on_the_stove` | `turn_on_the_stove` | put the bowl on the stove and turn on the stove | **compatible** |
| 16 | `01_08` | 1 | 8 | `put_the_bowl_on_the_stove` | `put_the_bowl_on_the_plate` | put the bowl on the stove and put the bowl on the plate | **conflict** |
| 17 | `01_09` | 1 | 9 | `put_the_bowl_on_the_stove` | `put_the_wine_bottle_on_the_rack` | put the bowl on the stove and put the wine bottle on the rack | **compatible** |
| 18 | `02_03` | 2 | 3 | `put_the_wine_bottle_on_top_of_the_cabinet` | `open_the_top_drawer_and_put_the_bowl_inside` | put the wine bottle on top of the cabinet and open the top drawer and put the bowl inside | **compatible** |
| 19 | `02_04` | 2 | 4 | `put_the_wine_bottle_on_top_of_the_cabinet` | `put_the_bowl_on_top_of_the_cabinet` | put the wine bottle on top of the cabinet and put the bowl on top of the cabinet | **compatible** |
| 20 | `02_05` | 2 | 5 | `put_the_wine_bottle_on_top_of_the_cabinet` | `push_the_plate_to_the_front_of_the_stove` | put the wine bottle on top of the cabinet and push the plate to the front of the stove | **compatible** |
| 21 | `02_06` | 2 | 6 | `put_the_wine_bottle_on_top_of_the_cabinet` | `put_the_cream_cheese_in_the_bowl` | put the wine bottle on top of the cabinet and put the cream cheese in the bowl | **compatible** |
| 22 | `02_07` | 2 | 7 | `put_the_wine_bottle_on_top_of_the_cabinet` | `turn_on_the_stove` | put the wine bottle on top of the cabinet and turn on the stove | **compatible** |
| 23 | `02_08` | 2 | 8 | `put_the_wine_bottle_on_top_of_the_cabinet` | `put_the_bowl_on_the_plate` | put the wine bottle on top of the cabinet and put the bowl on the plate | **compatible** |
| 24 | `02_09` | 2 | 9 | `put_the_wine_bottle_on_top_of_the_cabinet` | `put_the_wine_bottle_on_the_rack` | put the wine bottle on top of the cabinet and put the wine bottle on the rack | **conflict** |
| 25 | `03_04` | 3 | 4 | `open_the_top_drawer_and_put_the_bowl_inside` | `put_the_bowl_on_top_of_the_cabinet` | open the top drawer and put the bowl inside and put the bowl on top of the cabinet | **conflict** |
| 26 | `03_05` | 3 | 5 | `open_the_top_drawer_and_put_the_bowl_inside` | `push_the_plate_to_the_front_of_the_stove` | open the top drawer and put the bowl inside and push the plate to the front of the stove | **compatible** |
| 27 | `03_06` | 3 | 6 | `open_the_top_drawer_and_put_the_bowl_inside` | `put_the_cream_cheese_in_the_bowl` | open the top drawer and put the bowl inside and put the cream cheese in the bowl | **hard** |
| 28 | `03_07` | 3 | 7 | `open_the_top_drawer_and_put_the_bowl_inside` | `turn_on_the_stove` | open the top drawer and put the bowl inside and turn on the stove | **compatible** |
| 29 | `03_08` | 3 | 8 | `open_the_top_drawer_and_put_the_bowl_inside` | `put_the_bowl_on_the_plate` | open the top drawer and put the bowl inside and put the bowl on the plate | **conflict** |
| 30 | `03_09` | 3 | 9 | `open_the_top_drawer_and_put_the_bowl_inside` | `put_the_wine_bottle_on_the_rack` | open the top drawer and put the bowl inside and put the wine bottle on the rack | **compatible** |
| 31 | `04_05` | 4 | 5 | `put_the_bowl_on_top_of_the_cabinet` | `push_the_plate_to_the_front_of_the_stove` | put the bowl on top of the cabinet and push the plate to the front of the stove | **compatible** |
| 32 | `04_06` | 4 | 6 | `put_the_bowl_on_top_of_the_cabinet` | `put_the_cream_cheese_in_the_bowl` | put the bowl on top of the cabinet and put the cream cheese in the bowl | **hard** |
| 33 | `04_07` | 4 | 7 | `put_the_bowl_on_top_of_the_cabinet` | `turn_on_the_stove` | put the bowl on top of the cabinet and turn on the stove | **compatible** |
| 34 | `04_08` | 4 | 8 | `put_the_bowl_on_top_of_the_cabinet` | `put_the_bowl_on_the_plate` | put the bowl on top of the cabinet and put the bowl on the plate | **conflict** |
| 35 | `04_09` | 4 | 9 | `put_the_bowl_on_top_of_the_cabinet` | `put_the_wine_bottle_on_the_rack` | put the bowl on top of the cabinet and put the wine bottle on the rack | **compatible** |
| 36 | `05_06` | 5 | 6 | `push_the_plate_to_the_front_of_the_stove` | `put_the_cream_cheese_in_the_bowl` | push the plate to the front of the stove and put the cream cheese in the bowl | **compatible** |
| 37 | `05_07` | 5 | 7 | `push_the_plate_to_the_front_of_the_stove` | `turn_on_the_stove` | push the plate to the front of the stove and turn on the stove | **compatible** |
| 38 | `05_08` | 5 | 8 | `push_the_plate_to_the_front_of_the_stove` | `put_the_bowl_on_the_plate` | push the plate to the front of the stove and put the bowl on the plate | **compatible** |
| 39 | `05_09` | 5 | 9 | `push_the_plate_to_the_front_of_the_stove` | `put_the_wine_bottle_on_the_rack` | push the plate to the front of the stove and put the wine bottle on the rack | **compatible** |
| 40 | `06_07` | 6 | 7 | `put_the_cream_cheese_in_the_bowl` | `turn_on_the_stove` | put the cream cheese in the bowl and turn on the stove | **compatible** |
| 41 | `06_08` | 6 | 8 | `put_the_cream_cheese_in_the_bowl` | `put_the_bowl_on_the_plate` | put the cream cheese in the bowl and put the bowl on the plate | **hard** |
| 42 | `06_09` | 6 | 9 | `put_the_cream_cheese_in_the_bowl` | `put_the_wine_bottle_on_the_rack` | put the cream cheese in the bowl and put the wine bottle on the rack | **compatible** |
| 43 | `07_08` | 7 | 8 | `turn_on_the_stove` | `put_the_bowl_on_the_plate` | turn on the stove and put the bowl on the plate | **compatible** |
| 44 | `07_09` | 7 | 9 | `turn_on_the_stove` | `put_the_wine_bottle_on_the_rack` | turn on the stove and put the wine bottle on the rack | **compatible** |
| 45 | `08_09` | 8 | 9 | `put_the_bowl_on_the_plate` | `put_the_wine_bottle_on_the_rack` | put the bowl on the plate and put the wine bottle on the rack | **compatible** |

## 逐对明细 (原因 / goal atoms / obj_of_interest / init 来源)

### conflict (7 对)

#### `goal_pair_01_03` — put_the_bowl_on_the_stove + open_the_top_drawer_and_put_the_bowl_inside

- 组合指令: put the bowl on the stove and open the top drawer and put the bowl inside
- goal atoms: `(On akita_black_bowl_1 flat_stove_1_cook_region)` + `(In akita_black_bowl_1 wooden_cabinet_1_top_region)`
- obj_of_interest: `akita_black_bowl_1, flat_stove_1_cook_region, wooden_cabinet_1_top_region`
- init 来源: `put_the_bowl_on_the_stove.pruned_init` (benchmark idx 1)
- 分类: **conflict**；pilot 组: `excluded_conflict`
- 原因: t1(put_the_bowl_on_the_stove) 与 t3(open_the_top_drawer_and_put_the_bowl_inside) 都要求 akita_black_bowl_1 处于不同目标位置: (On akita_black_bowl_1 flat_stove_1_cook_region) vs (In akita_black_bowl_1 wooden_cabinet_1_top_region)。同一刚体不可能同时满足两个互斥的位置谓词, 合并目标在逻辑上不可能同时成立, 归为 conflict。

#### `goal_pair_01_04` — put_the_bowl_on_the_stove + put_the_bowl_on_top_of_the_cabinet

- 组合指令: put the bowl on the stove and put the bowl on top of the cabinet
- goal atoms: `(On akita_black_bowl_1 flat_stove_1_cook_region)` + `(On akita_black_bowl_1 wooden_cabinet_1_top_side)`
- obj_of_interest: `akita_black_bowl_1, flat_stove_1_cook_region, wooden_cabinet_1_top_side`
- init 来源: `put_the_bowl_on_the_stove.pruned_init` (benchmark idx 1)
- 分类: **conflict**；pilot 组: `excluded_conflict`
- 原因: t1(put_the_bowl_on_the_stove) 与 t4(put_the_bowl_on_top_of_the_cabinet) 都要求 akita_black_bowl_1 处于不同目标位置: (On akita_black_bowl_1 flat_stove_1_cook_region) vs (On akita_black_bowl_1 wooden_cabinet_1_top_side)。同一刚体不可能同时满足两个互斥的位置谓词, 合并目标在逻辑上不可能同时成立, 归为 conflict。

#### `goal_pair_01_08` — put_the_bowl_on_the_stove + put_the_bowl_on_the_plate

- 组合指令: put the bowl on the stove and put the bowl on the plate
- goal atoms: `(On akita_black_bowl_1 flat_stove_1_cook_region)` + `(On akita_black_bowl_1 plate_1)`
- obj_of_interest: `akita_black_bowl_1, flat_stove_1_cook_region, plate_1`
- init 来源: `put_the_bowl_on_the_stove.pruned_init` (benchmark idx 1)
- 分类: **conflict**；pilot 组: `excluded_conflict`
- 原因: t1(put_the_bowl_on_the_stove) 与 t8(put_the_bowl_on_the_plate) 都要求 akita_black_bowl_1 处于不同目标位置: (On akita_black_bowl_1 flat_stove_1_cook_region) vs (On akita_black_bowl_1 plate_1)。同一刚体不可能同时满足两个互斥的位置谓词, 合并目标在逻辑上不可能同时成立, 归为 conflict。

#### `goal_pair_02_09` — put_the_wine_bottle_on_top_of_the_cabinet + put_the_wine_bottle_on_the_rack

- 组合指令: put the wine bottle on top of the cabinet and put the wine bottle on the rack
- goal atoms: `(On wine_bottle_1 wooden_cabinet_1_top_side)` + `(On wine_bottle_1 wine_rack_1_top_region)`
- obj_of_interest: `wine_bottle_1, wooden_cabinet_1_top_side, wine_rack_1_top_region`
- init 来源: `put_the_wine_bottle_on_top_of_the_cabinet.pruned_init` (benchmark idx 2)
- 分类: **conflict**；pilot 组: `excluded_conflict`
- 原因: t2(put_the_wine_bottle_on_top_of_the_cabinet) 与 t9(put_the_wine_bottle_on_the_rack) 都要求 wine_bottle_1 处于不同目标位置: (On wine_bottle_1 wooden_cabinet_1_top_side) vs (On wine_bottle_1 wine_rack_1_top_region)。单一酒瓶不能同时在柜顶与酒架顶, 合并目标逻辑冲突。

#### `goal_pair_03_04` — open_the_top_drawer_and_put_the_bowl_inside + put_the_bowl_on_top_of_the_cabinet

- 组合指令: open the top drawer and put the bowl inside and put the bowl on top of the cabinet
- goal atoms: `(In akita_black_bowl_1 wooden_cabinet_1_top_region)` + `(On akita_black_bowl_1 wooden_cabinet_1_top_side)`
- obj_of_interest: `akita_black_bowl_1, wooden_cabinet_1_top_region, wooden_cabinet_1_top_side`
- init 来源: `open_the_top_drawer_and_put_the_bowl_inside.pruned_init` (benchmark idx 3)
- 分类: **conflict**；pilot 组: `excluded_conflict`
- 原因: t3(open_the_top_drawer_and_put_the_bowl_inside) 与 t4(put_the_bowl_on_top_of_the_cabinet) 都要求 akita_black_bowl_1 处于不同目标位置: (In akita_black_bowl_1 wooden_cabinet_1_top_region) vs (On akita_black_bowl_1 wooden_cabinet_1_top_side)。同一刚体不可能同时满足两个互斥的位置谓词, 合并目标在逻辑上不可能同时成立, 归为 conflict。

#### `goal_pair_03_08` — open_the_top_drawer_and_put_the_bowl_inside + put_the_bowl_on_the_plate

- 组合指令: open the top drawer and put the bowl inside and put the bowl on the plate
- goal atoms: `(In akita_black_bowl_1 wooden_cabinet_1_top_region)` + `(On akita_black_bowl_1 plate_1)`
- obj_of_interest: `akita_black_bowl_1, wooden_cabinet_1_top_region, plate_1`
- init 来源: `open_the_top_drawer_and_put_the_bowl_inside.pruned_init` (benchmark idx 3)
- 分类: **conflict**；pilot 组: `excluded_conflict`
- 原因: t3(open_the_top_drawer_and_put_the_bowl_inside) 与 t8(put_the_bowl_on_the_plate) 都要求 akita_black_bowl_1 处于不同目标位置: (In akita_black_bowl_1 wooden_cabinet_1_top_region) vs (On akita_black_bowl_1 plate_1)。同一刚体不可能同时满足两个互斥的位置谓词, 合并目标在逻辑上不可能同时成立, 归为 conflict。

#### `goal_pair_04_08` — put_the_bowl_on_top_of_the_cabinet + put_the_bowl_on_the_plate

- 组合指令: put the bowl on top of the cabinet and put the bowl on the plate
- goal atoms: `(On akita_black_bowl_1 wooden_cabinet_1_top_side)` + `(On akita_black_bowl_1 plate_1)`
- obj_of_interest: `akita_black_bowl_1, wooden_cabinet_1_top_side, plate_1`
- init 来源: `put_the_bowl_on_top_of_the_cabinet.pruned_init` (benchmark idx 4)
- 分类: **conflict**；pilot 组: `excluded_conflict`
- 原因: t4(put_the_bowl_on_top_of_the_cabinet) 与 t8(put_the_bowl_on_the_plate) 都要求 akita_black_bowl_1 处于不同目标位置: (On akita_black_bowl_1 wooden_cabinet_1_top_side) vs (On akita_black_bowl_1 plate_1)。同一刚体不可能同时满足两个互斥的位置谓词, 合并目标在逻辑上不可能同时成立, 归为 conflict。

### hard (5 对)

#### `goal_pair_01_05` — put_the_bowl_on_the_stove + push_the_plate_to_the_front_of_the_stove

- 组合指令: put the bowl on the stove and push the plate to the front of the stove
- goal atoms: `(On akita_black_bowl_1 flat_stove_1_cook_region)` + `(On plate_1 main_table_stove_front_region)`
- obj_of_interest: `akita_black_bowl_1, flat_stove_1_cook_region, plate_1, main_table_stove_front_region`
- init 来源: `put_the_bowl_on_the_stove.pruned_init` (benchmark idx 1)
- 分类: **hard**；pilot 组: `hard_control`
- 原因: t5 要求把 plate_1 推到 main_table_stove_front_region, t1 要求把 akita_black_bowl_1 放到 flat_stove_1_cook_region; 两目标区域空间相邻, 推盘路径与炉体/炉上碗存在碰撞与遮挡风险, 需要精细的次序与间隙, 归为 hard。

#### `goal_pair_01_06` — put_the_bowl_on_the_stove + put_the_cream_cheese_in_the_bowl

- 组合指令: put the bowl on the stove and put the cream cheese in the bowl
- goal atoms: `(On akita_black_bowl_1 flat_stove_1_cook_region)` + `(On cream_cheese_1 akita_black_bowl_1)`
- obj_of_interest: `akita_black_bowl_1, flat_stove_1_cook_region, cream_cheese_1`
- init 来源: `put_the_bowl_on_the_stove.pruned_init` (benchmark idx 1)
- 分类: **hard**；pilot 组: `hard_control`
- 原因: t6 要求 cream_cheese_1 最终置于 akita_black_bowl_1 上, 而 t1(put_the_bowl_on_the_stove) 又要求把碗移动到 (On akita_black_bowl_1 flat_stove_1_cook_region); 两者可共存, 但必须先完成碗的最终摆放再把奶酪放上去 (或搬运带奶酪的碗, 奶酪在碗面上易滑落), 次序受限、接触脆弱, 归为 hard。

#### `goal_pair_03_06` — open_the_top_drawer_and_put_the_bowl_inside + put_the_cream_cheese_in_the_bowl

- 组合指令: open the top drawer and put the bowl inside and put the cream cheese in the bowl
- goal atoms: `(In akita_black_bowl_1 wooden_cabinet_1_top_region)` + `(On cream_cheese_1 akita_black_bowl_1)`
- obj_of_interest: `akita_black_bowl_1, wooden_cabinet_1_top_region, cream_cheese_1`
- init 来源: `open_the_top_drawer_and_put_the_bowl_inside.pruned_init` (benchmark idx 3)
- 分类: **hard**；pilot 组: `excluded_conflict`
- 原因: t6 要求 cream_cheese_1 最终置于 akita_black_bowl_1 上, 而 t3(open_the_top_drawer_and_put_the_bowl_inside) 又要求把碗移动到 (In akita_black_bowl_1 wooden_cabinet_1_top_region); 两者可共存, 但必须先完成碗的最终摆放再把奶酪放上去 (或搬运带奶酪的碗, 奶酪在碗面上易滑落), 次序受限、接触脆弱, 归为 hard。

#### `goal_pair_04_06` — put_the_bowl_on_top_of_the_cabinet + put_the_cream_cheese_in_the_bowl

- 组合指令: put the bowl on top of the cabinet and put the cream cheese in the bowl
- goal atoms: `(On akita_black_bowl_1 wooden_cabinet_1_top_side)` + `(On cream_cheese_1 akita_black_bowl_1)`
- obj_of_interest: `akita_black_bowl_1, wooden_cabinet_1_top_side, cream_cheese_1`
- init 来源: `put_the_bowl_on_top_of_the_cabinet.pruned_init` (benchmark idx 4)
- 分类: **hard**；pilot 组: `excluded_conflict`
- 原因: t6 要求 cream_cheese_1 最终置于 akita_black_bowl_1 上, 而 t4(put_the_bowl_on_top_of_the_cabinet) 又要求把碗移动到 (On akita_black_bowl_1 wooden_cabinet_1_top_side); 两者可共存, 但必须先完成碗的最终摆放再把奶酪放上去 (或搬运带奶酪的碗, 奶酪在碗面上易滑落), 次序受限、接触脆弱, 归为 hard。

#### `goal_pair_06_08` — put_the_cream_cheese_in_the_bowl + put_the_bowl_on_the_plate

- 组合指令: put the cream cheese in the bowl and put the bowl on the plate
- goal atoms: `(On cream_cheese_1 akita_black_bowl_1)` + `(On akita_black_bowl_1 plate_1)`
- obj_of_interest: `cream_cheese_1, akita_black_bowl_1, plate_1`
- init 来源: `put_the_cream_cheese_in_the_bowl.pruned_init` (benchmark idx 6)
- 分类: **hard**；pilot 组: `excluded_conflict`
- 原因: t6 要求 cream_cheese_1 最终置于 akita_black_bowl_1 上, 而 t8(put_the_bowl_on_the_plate) 又要求把碗移动到 (On akita_black_bowl_1 plate_1); 两者可共存, 但必须先完成碗的最终摆放再把奶酪放上去 (或搬运带奶酪的碗, 奶酪在碗面上易滑落), 次序受限、接触脆弱, 归为 hard。

### compatible (33 对)

#### `goal_pair_00_01` — open_the_middle_drawer_of_the_cabinet + put_the_bowl_on_the_stove

- 组合指令: open the middle drawer of the cabinet and put the bowl on the stove
- goal atoms: `(Open wooden_cabinet_1_middle_region)` + `(On akita_black_bowl_1 flat_stove_1_cook_region)`
- obj_of_interest: `wooden_cabinet_1_middle_region, akita_black_bowl_1, flat_stove_1_cook_region`
- init 来源: `open_the_middle_drawer_of_the_cabinet.pruned_init` (benchmark idx 0)
- 分类: **compatible**；pilot 组: `primary`
- 原因: t0(open_the_middle_drawer_of_the_cabinet) = 打开 wooden_cabinet_1 的中抽屉 (middle_region); t1(put_the_bowl_on_the_stove) = 把 akita_black_bowl_1 放到 flat_stove_1 的 cook_region (炉灶烹饪区)。两者作用于不同被操作物体 (wooden_cabinet_1 vs akita_black_bowl_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。 次序提示: 用户示例组合: 先开中抽屉再放碗到炉灶区 (或反之), 互不冲突。

#### `goal_pair_00_02` — open_the_middle_drawer_of_the_cabinet + put_the_wine_bottle_on_top_of_the_cabinet

- 组合指令: open the middle drawer of the cabinet and put the wine bottle on top of the cabinet
- goal atoms: `(Open wooden_cabinet_1_middle_region)` + `(On wine_bottle_1 wooden_cabinet_1_top_side)`
- obj_of_interest: `wooden_cabinet_1_middle_region, wine_bottle_1, wooden_cabinet_1_top_side`
- init 来源: `open_the_middle_drawer_of_the_cabinet.pruned_init` (benchmark idx 0)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t0(open_the_middle_drawer_of_the_cabinet) = 打开 wooden_cabinet_1 的中抽屉 (middle_region); t2(put_the_wine_bottle_on_top_of_the_cabinet) = 把 wine_bottle_1 放到 wooden_cabinet_1 的 top_side (柜顶)。两者作用于不同被操作物体 (wooden_cabinet_1 vs wine_bottle_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。 次序提示: 放酒瓶到柜顶与打开中抽屉可共容; 同一柜体, 建议先放瓶再开抽屉避免碰撞。

#### `goal_pair_00_03` — open_the_middle_drawer_of_the_cabinet + open_the_top_drawer_and_put_the_bowl_inside

- 组合指令: open the middle drawer of the cabinet and open the top drawer and put the bowl inside
- goal atoms: `(Open wooden_cabinet_1_middle_region)` + `(In akita_black_bowl_1 wooden_cabinet_1_top_region)`
- obj_of_interest: `wooden_cabinet_1_middle_region, akita_black_bowl_1, wooden_cabinet_1_top_region`
- init 来源: `open_the_middle_drawer_of_the_cabinet.pruned_init` (benchmark idx 0)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t0(open_the_middle_drawer_of_the_cabinet) = 打开 wooden_cabinet_1 的中抽屉 (middle_region); t3(open_the_top_drawer_and_put_the_bowl_inside) = 把 akita_black_bowl_1 放入 wooden_cabinet_1 的 top_region (上抽屉内)。两者作用于不同被操作物体 (wooden_cabinet_1 vs akita_black_bowl_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。 次序提示: 两个目标都涉及木质柜抽屉; 建议先开上抽屉放碗、再开中抽屉, 避免中抽屉伸出遮挡上抽屉取放路径。

#### `goal_pair_00_04` — open_the_middle_drawer_of_the_cabinet + put_the_bowl_on_top_of_the_cabinet

- 组合指令: open the middle drawer of the cabinet and put the bowl on top of the cabinet
- goal atoms: `(Open wooden_cabinet_1_middle_region)` + `(On akita_black_bowl_1 wooden_cabinet_1_top_side)`
- obj_of_interest: `wooden_cabinet_1_middle_region, akita_black_bowl_1, wooden_cabinet_1_top_side`
- init 来源: `open_the_middle_drawer_of_the_cabinet.pruned_init` (benchmark idx 0)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t0(open_the_middle_drawer_of_the_cabinet) = 打开 wooden_cabinet_1 的中抽屉 (middle_region); t4(put_the_bowl_on_top_of_the_cabinet) = 把 akita_black_bowl_1 放到 wooden_cabinet_1 的 top_side (柜顶)。两者作用于不同被操作物体 (wooden_cabinet_1 vs akita_black_bowl_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。 次序提示: 先开中抽屉或先放碗到柜顶均可, 互不冲突。

#### `goal_pair_00_05` — open_the_middle_drawer_of_the_cabinet + push_the_plate_to_the_front_of_the_stove

- 组合指令: open the middle drawer of the cabinet and push the plate to the front of the stove
- goal atoms: `(Open wooden_cabinet_1_middle_region)` + `(On plate_1 main_table_stove_front_region)`
- obj_of_interest: `wooden_cabinet_1_middle_region, plate_1, main_table_stove_front_region`
- init 来源: `open_the_middle_drawer_of_the_cabinet.pruned_init` (benchmark idx 0)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t0(open_the_middle_drawer_of_the_cabinet) = 打开 wooden_cabinet_1 的中抽屉 (middle_region); t5(push_the_plate_to_the_front_of_the_stove) = 把 plate_1 推到 main_table 的 stove_front_region (炉前区)。两者作用于不同被操作物体 (wooden_cabinet_1 vs plate_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_00_06` — open_the_middle_drawer_of_the_cabinet + put_the_cream_cheese_in_the_bowl

- 组合指令: open the middle drawer of the cabinet and put the cream cheese in the bowl
- goal atoms: `(Open wooden_cabinet_1_middle_region)` + `(On cream_cheese_1 akita_black_bowl_1)`
- obj_of_interest: `wooden_cabinet_1_middle_region, cream_cheese_1, akita_black_bowl_1`
- init 来源: `open_the_middle_drawer_of_the_cabinet.pruned_init` (benchmark idx 0)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t0(open_the_middle_drawer_of_the_cabinet) = 打开 wooden_cabinet_1 的中抽屉 (middle_region); t6(put_the_cream_cheese_in_the_bowl) = 把 cream_cheese_1 放到 akita_black_bowl_1 上。两者作用于不同被操作物体 (wooden_cabinet_1 vs cream_cheese_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_00_07` — open_the_middle_drawer_of_the_cabinet + turn_on_the_stove

- 组合指令: open the middle drawer of the cabinet and turn on the stove
- goal atoms: `(Open wooden_cabinet_1_middle_region)` + `(Turnon flat_stove_1)`
- obj_of_interest: `wooden_cabinet_1_middle_region, flat_stove_1`
- init 来源: `open_the_middle_drawer_of_the_cabinet.pruned_init` (benchmark idx 0)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t0(open_the_middle_drawer_of_the_cabinet) = 打开 wooden_cabinet_1 的中抽屉 (middle_region); t7(turn_on_the_stove) = 打开 flat_stove_1 (Turnon)。两者作用于不同被操作物体 (wooden_cabinet_1 vs flat_stove_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_00_08` — open_the_middle_drawer_of_the_cabinet + put_the_bowl_on_the_plate

- 组合指令: open the middle drawer of the cabinet and put the bowl on the plate
- goal atoms: `(Open wooden_cabinet_1_middle_region)` + `(On akita_black_bowl_1 plate_1)`
- obj_of_interest: `wooden_cabinet_1_middle_region, akita_black_bowl_1, plate_1`
- init 来源: `open_the_middle_drawer_of_the_cabinet.pruned_init` (benchmark idx 0)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t0(open_the_middle_drawer_of_the_cabinet) = 打开 wooden_cabinet_1 的中抽屉 (middle_region); t8(put_the_bowl_on_the_plate) = 把 akita_black_bowl_1 放到 plate_1 上。两者作用于不同被操作物体 (wooden_cabinet_1 vs akita_black_bowl_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_00_09` — open_the_middle_drawer_of_the_cabinet + put_the_wine_bottle_on_the_rack

- 组合指令: open the middle drawer of the cabinet and put the wine bottle on the rack
- goal atoms: `(Open wooden_cabinet_1_middle_region)` + `(On wine_bottle_1 wine_rack_1_top_region)`
- obj_of_interest: `wooden_cabinet_1_middle_region, wine_bottle_1, wine_rack_1_top_region`
- init 来源: `open_the_middle_drawer_of_the_cabinet.pruned_init` (benchmark idx 0)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t0(open_the_middle_drawer_of_the_cabinet) = 打开 wooden_cabinet_1 的中抽屉 (middle_region); t9(put_the_wine_bottle_on_the_rack) = 把 wine_bottle_1 放到 wine_rack_1 的 top_region (酒架顶)。两者作用于不同被操作物体 (wooden_cabinet_1 vs wine_bottle_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_01_02` — put_the_bowl_on_the_stove + put_the_wine_bottle_on_top_of_the_cabinet

- 组合指令: put the bowl on the stove and put the wine bottle on top of the cabinet
- goal atoms: `(On akita_black_bowl_1 flat_stove_1_cook_region)` + `(On wine_bottle_1 wooden_cabinet_1_top_side)`
- obj_of_interest: `akita_black_bowl_1, flat_stove_1_cook_region, wine_bottle_1, wooden_cabinet_1_top_side`
- init 来源: `put_the_bowl_on_the_stove.pruned_init` (benchmark idx 1)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t1(put_the_bowl_on_the_stove) = 把 akita_black_bowl_1 放到 flat_stove_1 的 cook_region (炉灶烹饪区); t2(put_the_wine_bottle_on_top_of_the_cabinet) = 把 wine_bottle_1 放到 wooden_cabinet_1 的 top_side (柜顶)。两者作用于不同被操作物体 (akita_black_bowl_1 vs wine_bottle_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_01_07` — put_the_bowl_on_the_stove + turn_on_the_stove

- 组合指令: put the bowl on the stove and turn on the stove
- goal atoms: `(On akita_black_bowl_1 flat_stove_1_cook_region)` + `(Turnon flat_stove_1)`
- obj_of_interest: `akita_black_bowl_1, flat_stove_1_cook_region, flat_stove_1`
- init 来源: `put_the_bowl_on_the_stove.pruned_init` (benchmark idx 1)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t1(put_the_bowl_on_the_stove) = 把 akita_black_bowl_1 放到 flat_stove_1 的 cook_region (炉灶烹饪区); t7(turn_on_the_stove) = 打开 flat_stove_1 (Turnon)。两者作用于不同被操作物体 (akita_black_bowl_1 vs flat_stove_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。 次序提示: 先放碗到炉灶区再开炉 (或先开炉) 均可; 仿真中炉子开启不改变碗的放置判定。

#### `goal_pair_01_09` — put_the_bowl_on_the_stove + put_the_wine_bottle_on_the_rack

- 组合指令: put the bowl on the stove and put the wine bottle on the rack
- goal atoms: `(On akita_black_bowl_1 flat_stove_1_cook_region)` + `(On wine_bottle_1 wine_rack_1_top_region)`
- obj_of_interest: `akita_black_bowl_1, flat_stove_1_cook_region, wine_bottle_1, wine_rack_1_top_region`
- init 来源: `put_the_bowl_on_the_stove.pruned_init` (benchmark idx 1)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t1(put_the_bowl_on_the_stove) = 把 akita_black_bowl_1 放到 flat_stove_1 的 cook_region (炉灶烹饪区); t9(put_the_wine_bottle_on_the_rack) = 把 wine_bottle_1 放到 wine_rack_1 的 top_region (酒架顶)。两者作用于不同被操作物体 (akita_black_bowl_1 vs wine_bottle_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_02_03` — put_the_wine_bottle_on_top_of_the_cabinet + open_the_top_drawer_and_put_the_bowl_inside

- 组合指令: put the wine bottle on top of the cabinet and open the top drawer and put the bowl inside
- goal atoms: `(On wine_bottle_1 wooden_cabinet_1_top_side)` + `(In akita_black_bowl_1 wooden_cabinet_1_top_region)`
- obj_of_interest: `wine_bottle_1, wooden_cabinet_1_top_side, akita_black_bowl_1, wooden_cabinet_1_top_region`
- init 来源: `put_the_wine_bottle_on_top_of_the_cabinet.pruned_init` (benchmark idx 2)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t2(put_the_wine_bottle_on_top_of_the_cabinet) = 把 wine_bottle_1 放到 wooden_cabinet_1 的 top_side (柜顶); t3(open_the_top_drawer_and_put_the_bowl_inside) = 把 akita_black_bowl_1 放入 wooden_cabinet_1 的 top_region (上抽屉内)。两者作用于不同被操作物体 (wine_bottle_1 vs akita_black_bowl_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_02_04` — put_the_wine_bottle_on_top_of_the_cabinet + put_the_bowl_on_top_of_the_cabinet

- 组合指令: put the wine bottle on top of the cabinet and put the bowl on top of the cabinet
- goal atoms: `(On wine_bottle_1 wooden_cabinet_1_top_side)` + `(On akita_black_bowl_1 wooden_cabinet_1_top_side)`
- obj_of_interest: `wine_bottle_1, wooden_cabinet_1_top_side, akita_black_bowl_1`
- init 来源: `put_the_wine_bottle_on_top_of_the_cabinet.pruned_init` (benchmark idx 2)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t2(put_the_wine_bottle_on_top_of_the_cabinet) = 把 wine_bottle_1 放到 wooden_cabinet_1 的 top_side (柜顶); t4(put_the_bowl_on_top_of_the_cabinet) = 把 akita_black_bowl_1 放到 wooden_cabinet_1 的 top_side (柜顶)。两者作用于不同被操作物体 (wine_bottle_1 vs akita_black_bowl_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。 次序提示: 酒瓶与碗都放到 wooden_cabinet_1 的 top_side, 被操作物体不同; 柜顶面足够容纳两者, 注意摆放间距。

#### `goal_pair_02_05` — put_the_wine_bottle_on_top_of_the_cabinet + push_the_plate_to_the_front_of_the_stove

- 组合指令: put the wine bottle on top of the cabinet and push the plate to the front of the stove
- goal atoms: `(On wine_bottle_1 wooden_cabinet_1_top_side)` + `(On plate_1 main_table_stove_front_region)`
- obj_of_interest: `wine_bottle_1, wooden_cabinet_1_top_side, plate_1, main_table_stove_front_region`
- init 来源: `put_the_wine_bottle_on_top_of_the_cabinet.pruned_init` (benchmark idx 2)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t2(put_the_wine_bottle_on_top_of_the_cabinet) = 把 wine_bottle_1 放到 wooden_cabinet_1 的 top_side (柜顶); t5(push_the_plate_to_the_front_of_the_stove) = 把 plate_1 推到 main_table 的 stove_front_region (炉前区)。两者作用于不同被操作物体 (wine_bottle_1 vs plate_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_02_06` — put_the_wine_bottle_on_top_of_the_cabinet + put_the_cream_cheese_in_the_bowl

- 组合指令: put the wine bottle on top of the cabinet and put the cream cheese in the bowl
- goal atoms: `(On wine_bottle_1 wooden_cabinet_1_top_side)` + `(On cream_cheese_1 akita_black_bowl_1)`
- obj_of_interest: `wine_bottle_1, wooden_cabinet_1_top_side, cream_cheese_1, akita_black_bowl_1`
- init 来源: `put_the_wine_bottle_on_top_of_the_cabinet.pruned_init` (benchmark idx 2)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t2(put_the_wine_bottle_on_top_of_the_cabinet) = 把 wine_bottle_1 放到 wooden_cabinet_1 的 top_side (柜顶); t6(put_the_cream_cheese_in_the_bowl) = 把 cream_cheese_1 放到 akita_black_bowl_1 上。两者作用于不同被操作物体 (wine_bottle_1 vs cream_cheese_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_02_07` — put_the_wine_bottle_on_top_of_the_cabinet + turn_on_the_stove

- 组合指令: put the wine bottle on top of the cabinet and turn on the stove
- goal atoms: `(On wine_bottle_1 wooden_cabinet_1_top_side)` + `(Turnon flat_stove_1)`
- obj_of_interest: `wine_bottle_1, wooden_cabinet_1_top_side, flat_stove_1`
- init 来源: `put_the_wine_bottle_on_top_of_the_cabinet.pruned_init` (benchmark idx 2)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t2(put_the_wine_bottle_on_top_of_the_cabinet) = 把 wine_bottle_1 放到 wooden_cabinet_1 的 top_side (柜顶); t7(turn_on_the_stove) = 打开 flat_stove_1 (Turnon)。两者作用于不同被操作物体 (wine_bottle_1 vs flat_stove_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_02_08` — put_the_wine_bottle_on_top_of_the_cabinet + put_the_bowl_on_the_plate

- 组合指令: put the wine bottle on top of the cabinet and put the bowl on the plate
- goal atoms: `(On wine_bottle_1 wooden_cabinet_1_top_side)` + `(On akita_black_bowl_1 plate_1)`
- obj_of_interest: `wine_bottle_1, wooden_cabinet_1_top_side, akita_black_bowl_1, plate_1`
- init 来源: `put_the_wine_bottle_on_top_of_the_cabinet.pruned_init` (benchmark idx 2)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t2(put_the_wine_bottle_on_top_of_the_cabinet) = 把 wine_bottle_1 放到 wooden_cabinet_1 的 top_side (柜顶); t8(put_the_bowl_on_the_plate) = 把 akita_black_bowl_1 放到 plate_1 上。两者作用于不同被操作物体 (wine_bottle_1 vs akita_black_bowl_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_03_05` — open_the_top_drawer_and_put_the_bowl_inside + push_the_plate_to_the_front_of_the_stove

- 组合指令: open the top drawer and put the bowl inside and push the plate to the front of the stove
- goal atoms: `(In akita_black_bowl_1 wooden_cabinet_1_top_region)` + `(On plate_1 main_table_stove_front_region)`
- obj_of_interest: `akita_black_bowl_1, wooden_cabinet_1_top_region, plate_1, main_table_stove_front_region`
- init 来源: `open_the_top_drawer_and_put_the_bowl_inside.pruned_init` (benchmark idx 3)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t3(open_the_top_drawer_and_put_the_bowl_inside) = 把 akita_black_bowl_1 放入 wooden_cabinet_1 的 top_region (上抽屉内); t5(push_the_plate_to_the_front_of_the_stove) = 把 plate_1 推到 main_table 的 stove_front_region (炉前区)。两者作用于不同被操作物体 (akita_black_bowl_1 vs plate_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。 次序提示: 碗入上抽屉与推盘到炉前区分属不同区域, 互不冲突。

#### `goal_pair_03_07` — open_the_top_drawer_and_put_the_bowl_inside + turn_on_the_stove

- 组合指令: open the top drawer and put the bowl inside and turn on the stove
- goal atoms: `(In akita_black_bowl_1 wooden_cabinet_1_top_region)` + `(Turnon flat_stove_1)`
- obj_of_interest: `akita_black_bowl_1, wooden_cabinet_1_top_region, flat_stove_1`
- init 来源: `open_the_top_drawer_and_put_the_bowl_inside.pruned_init` (benchmark idx 3)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t3(open_the_top_drawer_and_put_the_bowl_inside) = 把 akita_black_bowl_1 放入 wooden_cabinet_1 的 top_region (上抽屉内); t7(turn_on_the_stove) = 打开 flat_stove_1 (Turnon)。两者作用于不同被操作物体 (akita_black_bowl_1 vs flat_stove_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_03_09` — open_the_top_drawer_and_put_the_bowl_inside + put_the_wine_bottle_on_the_rack

- 组合指令: open the top drawer and put the bowl inside and put the wine bottle on the rack
- goal atoms: `(In akita_black_bowl_1 wooden_cabinet_1_top_region)` + `(On wine_bottle_1 wine_rack_1_top_region)`
- obj_of_interest: `akita_black_bowl_1, wooden_cabinet_1_top_region, wine_bottle_1, wine_rack_1_top_region`
- init 来源: `open_the_top_drawer_and_put_the_bowl_inside.pruned_init` (benchmark idx 3)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t3(open_the_top_drawer_and_put_the_bowl_inside) = 把 akita_black_bowl_1 放入 wooden_cabinet_1 的 top_region (上抽屉内); t9(put_the_wine_bottle_on_the_rack) = 把 wine_bottle_1 放到 wine_rack_1 的 top_region (酒架顶)。两者作用于不同被操作物体 (akita_black_bowl_1 vs wine_bottle_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_04_05` — put_the_bowl_on_top_of_the_cabinet + push_the_plate_to_the_front_of_the_stove

- 组合指令: put the bowl on top of the cabinet and push the plate to the front of the stove
- goal atoms: `(On akita_black_bowl_1 wooden_cabinet_1_top_side)` + `(On plate_1 main_table_stove_front_region)`
- obj_of_interest: `akita_black_bowl_1, wooden_cabinet_1_top_side, plate_1, main_table_stove_front_region`
- init 来源: `put_the_bowl_on_top_of_the_cabinet.pruned_init` (benchmark idx 4)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t4(put_the_bowl_on_top_of_the_cabinet) = 把 akita_black_bowl_1 放到 wooden_cabinet_1 的 top_side (柜顶); t5(push_the_plate_to_the_front_of_the_stove) = 把 plate_1 推到 main_table 的 stove_front_region (炉前区)。两者作用于不同被操作物体 (akita_black_bowl_1 vs plate_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_04_07` — put_the_bowl_on_top_of_the_cabinet + turn_on_the_stove

- 组合指令: put the bowl on top of the cabinet and turn on the stove
- goal atoms: `(On akita_black_bowl_1 wooden_cabinet_1_top_side)` + `(Turnon flat_stove_1)`
- obj_of_interest: `akita_black_bowl_1, wooden_cabinet_1_top_side, flat_stove_1`
- init 来源: `put_the_bowl_on_top_of_the_cabinet.pruned_init` (benchmark idx 4)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t4(put_the_bowl_on_top_of_the_cabinet) = 把 akita_black_bowl_1 放到 wooden_cabinet_1 的 top_side (柜顶); t7(turn_on_the_stove) = 打开 flat_stove_1 (Turnon)。两者作用于不同被操作物体 (akita_black_bowl_1 vs flat_stove_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_04_09` — put_the_bowl_on_top_of_the_cabinet + put_the_wine_bottle_on_the_rack

- 组合指令: put the bowl on top of the cabinet and put the wine bottle on the rack
- goal atoms: `(On akita_black_bowl_1 wooden_cabinet_1_top_side)` + `(On wine_bottle_1 wine_rack_1_top_region)`
- obj_of_interest: `akita_black_bowl_1, wooden_cabinet_1_top_side, wine_bottle_1, wine_rack_1_top_region`
- init 来源: `put_the_bowl_on_top_of_the_cabinet.pruned_init` (benchmark idx 4)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t4(put_the_bowl_on_top_of_the_cabinet) = 把 akita_black_bowl_1 放到 wooden_cabinet_1 的 top_side (柜顶); t9(put_the_wine_bottle_on_the_rack) = 把 wine_bottle_1 放到 wine_rack_1 的 top_region (酒架顶)。两者作用于不同被操作物体 (akita_black_bowl_1 vs wine_bottle_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_05_06` — push_the_plate_to_the_front_of_the_stove + put_the_cream_cheese_in_the_bowl

- 组合指令: push the plate to the front of the stove and put the cream cheese in the bowl
- goal atoms: `(On plate_1 main_table_stove_front_region)` + `(On cream_cheese_1 akita_black_bowl_1)`
- obj_of_interest: `plate_1, main_table_stove_front_region, cream_cheese_1, akita_black_bowl_1`
- init 来源: `push_the_plate_to_the_front_of_the_stove.pruned_init` (benchmark idx 5)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t5(push_the_plate_to_the_front_of_the_stove) = 把 plate_1 推到 main_table 的 stove_front_region (炉前区); t6(put_the_cream_cheese_in_the_bowl) = 把 cream_cheese_1 放到 akita_black_bowl_1 上。两者作用于不同被操作物体 (plate_1 vs cream_cheese_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_05_07` — push_the_plate_to_the_front_of_the_stove + turn_on_the_stove

- 组合指令: push the plate to the front of the stove and turn on the stove
- goal atoms: `(On plate_1 main_table_stove_front_region)` + `(Turnon flat_stove_1)`
- obj_of_interest: `plate_1, main_table_stove_front_region, flat_stove_1`
- init 来源: `push_the_plate_to_the_front_of_the_stove.pruned_init` (benchmark idx 5)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t5(push_the_plate_to_the_front_of_the_stove) = 把 plate_1 推到 main_table 的 stove_front_region (炉前区); t7(turn_on_the_stove) = 打开 flat_stove_1 (Turnon)。两者作用于不同被操作物体 (plate_1 vs flat_stove_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_05_08` — push_the_plate_to_the_front_of_the_stove + put_the_bowl_on_the_plate

- 组合指令: push the plate to the front of the stove and put the bowl on the plate
- goal atoms: `(On plate_1 main_table_stove_front_region)` + `(On akita_black_bowl_1 plate_1)`
- obj_of_interest: `plate_1, main_table_stove_front_region, akita_black_bowl_1`
- init 来源: `push_the_plate_to_the_front_of_the_stove.pruned_init` (benchmark idx 5)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t5(push_the_plate_to_the_front_of_the_stove) = 把 plate_1 推到 main_table 的 stove_front_region (炉前区); t8(put_the_bowl_on_the_plate) = 把 akita_black_bowl_1 放到 plate_1 上。两者作用于不同被操作物体 (plate_1 vs akita_black_bowl_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。 次序提示: 先推盘到炉前区再把碗放到盘上更稳 (反之亦可, 但推带碗的盘子更脆弱)。

#### `goal_pair_05_09` — push_the_plate_to_the_front_of_the_stove + put_the_wine_bottle_on_the_rack

- 组合指令: push the plate to the front of the stove and put the wine bottle on the rack
- goal atoms: `(On plate_1 main_table_stove_front_region)` + `(On wine_bottle_1 wine_rack_1_top_region)`
- obj_of_interest: `plate_1, main_table_stove_front_region, wine_bottle_1, wine_rack_1_top_region`
- init 来源: `push_the_plate_to_the_front_of_the_stove.pruned_init` (benchmark idx 5)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t5(push_the_plate_to_the_front_of_the_stove) = 把 plate_1 推到 main_table 的 stove_front_region (炉前区); t9(put_the_wine_bottle_on_the_rack) = 把 wine_bottle_1 放到 wine_rack_1 的 top_region (酒架顶)。两者作用于不同被操作物体 (plate_1 vs wine_bottle_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_06_07` — put_the_cream_cheese_in_the_bowl + turn_on_the_stove

- 组合指令: put the cream cheese in the bowl and turn on the stove
- goal atoms: `(On cream_cheese_1 akita_black_bowl_1)` + `(Turnon flat_stove_1)`
- obj_of_interest: `cream_cheese_1, akita_black_bowl_1, flat_stove_1`
- init 来源: `put_the_cream_cheese_in_the_bowl.pruned_init` (benchmark idx 6)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t6(put_the_cream_cheese_in_the_bowl) = 把 cream_cheese_1 放到 akita_black_bowl_1 上; t7(turn_on_the_stove) = 打开 flat_stove_1 (Turnon)。两者作用于不同被操作物体 (cream_cheese_1 vs flat_stove_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_06_09` — put_the_cream_cheese_in_the_bowl + put_the_wine_bottle_on_the_rack

- 组合指令: put the cream cheese in the bowl and put the wine bottle on the rack
- goal atoms: `(On cream_cheese_1 akita_black_bowl_1)` + `(On wine_bottle_1 wine_rack_1_top_region)`
- obj_of_interest: `cream_cheese_1, akita_black_bowl_1, wine_bottle_1, wine_rack_1_top_region`
- init 来源: `put_the_cream_cheese_in_the_bowl.pruned_init` (benchmark idx 6)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t6(put_the_cream_cheese_in_the_bowl) = 把 cream_cheese_1 放到 akita_black_bowl_1 上; t9(put_the_wine_bottle_on_the_rack) = 把 wine_bottle_1 放到 wine_rack_1 的 top_region (酒架顶)。两者作用于不同被操作物体 (cream_cheese_1 vs wine_bottle_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_07_08` — turn_on_the_stove + put_the_bowl_on_the_plate

- 组合指令: turn on the stove and put the bowl on the plate
- goal atoms: `(Turnon flat_stove_1)` + `(On akita_black_bowl_1 plate_1)`
- obj_of_interest: `flat_stove_1, akita_black_bowl_1, plate_1`
- init 来源: `turn_on_the_stove.pruned_init` (benchmark idx 7)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t7(turn_on_the_stove) = 打开 flat_stove_1 (Turnon); t8(put_the_bowl_on_the_plate) = 把 akita_black_bowl_1 放到 plate_1 上。两者作用于不同被操作物体 (flat_stove_1 vs akita_black_bowl_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_07_09` — turn_on_the_stove + put_the_wine_bottle_on_the_rack

- 组合指令: turn on the stove and put the wine bottle on the rack
- goal atoms: `(Turnon flat_stove_1)` + `(On wine_bottle_1 wine_rack_1_top_region)`
- obj_of_interest: `flat_stove_1, wine_bottle_1, wine_rack_1_top_region`
- init 来源: `turn_on_the_stove.pruned_init` (benchmark idx 7)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t7(turn_on_the_stove) = 打开 flat_stove_1 (Turnon); t9(put_the_wine_bottle_on_the_rack) = 把 wine_bottle_1 放到 wine_rack_1 的 top_region (酒架顶)。两者作用于不同被操作物体 (flat_stove_1 vs wine_bottle_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

#### `goal_pair_08_09` — put_the_bowl_on_the_plate + put_the_wine_bottle_on_the_rack

- 组合指令: put the bowl on the plate and put the wine bottle on the rack
- goal atoms: `(On akita_black_bowl_1 plate_1)` + `(On wine_bottle_1 wine_rack_1_top_region)`
- obj_of_interest: `akita_black_bowl_1, plate_1, wine_bottle_1, wine_rack_1_top_region`
- init 来源: `put_the_bowl_on_the_plate.pruned_init` (benchmark idx 8)
- 分类: **compatible**；pilot 组: `compatible_arm`
- 原因: t8(put_the_bowl_on_the_plate) = 把 akita_black_bowl_1 放到 plate_1 上; t9(put_the_wine_bottle_on_the_rack) = 把 wine_bottle_1 放到 wine_rack_1 的 top_region (酒架顶)。两者作用于不同被操作物体 (akita_black_bowl_1 vs wine_bottle_1), 不存在同一物体的异位要求, 目标原子可同时成立, 归为 compatible。

