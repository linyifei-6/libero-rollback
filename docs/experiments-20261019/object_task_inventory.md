# LIBERO-OBJECT 任务物体清单（官方 benchmark 顺序）

## 0. 结构说明

- 每个任务场景实例化 **7 个刚体 = 1 个 basket + 6 个可操作物体（1 个目标 + 5 个干扰项）**；basket 是 10 个任务共享的同一实例。
- 场景有 **7 个固定地面槽位**：`floor_target_object_region`（目标位）+ `floor_other_object_region_0..4`（5 个干扰位）+ `floor_bin_region`（basket 位）。
- 10 个任务的槽位物理坐标完全相同，任务之间只是「哪个物体类型放在哪个槽位」的置换（外加目标物类型不同）。
- **每个任务需要操作的物体只有 1 个**：目标物体（goal = `(In <target>_1 basket_1_contain_region)`）；5 个干扰项不需要操作，basket 是容器、不需要移动。
- 10 个物体类型：`alphabet_soup, cream_cheese, salad_dressing, bbq_sauce, ketchup, tomato_sauce, butter, milk, chocolate_pudding, orange_juice`；每个类型恰好作为目标 1 次、作为干扰项 5 次（在 6 个任务中出现），basket 出现在全部 10 个任务。

## 1. 逐任务物体清单

| idx | 任务（bddl 名） | 目标物体（需操作） | 干扰物（5 个，不需要操作） | basket |
|---|---|---|---|---|
| 0 | pick_up_the_alphabet_soup_and_place_it_in_the_basket | **alphabet_soup_1(alphabet_soup)**（起始 `floor_target_object_region`） | salad_dressing_1(salad_dressing), cream_cheese_1(cream_cheese), milk_1(milk), tomato_sauce_1(tomato_sauce), butter_1(butter) | basket_1 |
| 1 | pick_up_the_cream_cheese_and_place_it_in_the_basket | **cream_cheese_1(cream_cheese)**（起始 `floor_target_object_region`） | alphabet_soup_1(alphabet_soup), milk_1(milk), tomato_sauce_1(tomato_sauce), butter_1(butter), orange_juice_1(orange_juice) | basket_1 |
| 2 | pick_up_the_salad_dressing_and_place_it_in_the_basket | **salad_dressing_1(salad_dressing)**（起始 `floor_target_object_region`） | ketchup_1(ketchup), alphabet_soup_1(alphabet_soup), cream_cheese_1(cream_cheese), milk_1(milk), tomato_sauce_1(tomato_sauce) | basket_1 |
| 3 | pick_up_the_bbq_sauce_and_place_it_in_the_basket | **bbq_sauce_1(bbq_sauce)**（起始 `floor_target_object_region`） | chocolate_pudding_1(chocolate_pudding), ketchup_1(ketchup), salad_dressing_1(salad_dressing), alphabet_soup_1(alphabet_soup), cream_cheese_1(cream_cheese) | basket_1 |
| 4 | pick_up_the_ketchup_and_place_it_in_the_basket | **ketchup_1(ketchup)**（起始 `floor_target_object_region`） | bbq_sauce_1(bbq_sauce), salad_dressing_1(salad_dressing), alphabet_soup_1(alphabet_soup), cream_cheese_1(cream_cheese), milk_1(milk) | basket_1 |
| 5 | pick_up_the_tomato_sauce_and_place_it_in_the_basket | **tomato_sauce_1(tomato_sauce)**（起始 `floor_target_object_region`） | milk_1(milk), butter_1(butter), orange_juice_1(orange_juice), chocolate_pudding_1(chocolate_pudding), bbq_sauce_1(bbq_sauce) | basket_1 |
| 6 | pick_up_the_butter_and_place_it_in_the_basket | **butter_1(butter)**（起始 `floor_target_object_region`） | tomato_sauce_1(tomato_sauce), orange_juice_1(orange_juice), chocolate_pudding_1(chocolate_pudding), bbq_sauce_1(bbq_sauce), ketchup_1(ketchup) | basket_1 |
| 7 | pick_up_the_milk_and_place_it_in_the_basket | **milk_1(milk)**（起始 `floor_target_object_region`） | cream_cheese_1(cream_cheese), tomato_sauce_1(tomato_sauce), butter_1(butter), orange_juice_1(orange_juice), chocolate_pudding_1(chocolate_pudding) | basket_1 |
| 8 | pick_up_the_chocolate_pudding_and_place_it_in_the_basket | **chocolate_pudding_1(chocolate_pudding)**（起始 `floor_target_object_region`） | orange_juice_1(orange_juice), bbq_sauce_1(bbq_sauce), ketchup_1(ketchup), salad_dressing_1(salad_dressing), alphabet_soup_1(alphabet_soup) | basket_1 |
| 9 | pick_up_the_orange_juice_and_place_it_in_the_basket | **orange_juice_1(orange_juice)**（起始 `floor_target_object_region`） | butter_1(butter), chocolate_pudding_1(chocolate_pudding), bbq_sauce_1(bbq_sauce), ketchup_1(ketchup), salad_dressing_1(salad_dressing) | basket_1 |

## 2. 初始摆位（:init → 槽位）

| idx | 目标位 `floor_target_object_region` | 5 个干扰位 `floor_other_object_region_0..4`（按槽位 0→4 顺序） | basket 位 `floor_bin_region` |
|---|---|---|---|
| 0 | alphabet_soup_1(alphabet_soup) | R0: salad_dressing_1(salad_dressing); R1: cream_cheese_1(cream_cheese); R2: milk_1(milk); R3: tomato_sauce_1(tomato_sauce); R4: butter_1(butter) | basket_1 |
| 1 | cream_cheese_1(cream_cheese) | R0: alphabet_soup_1(alphabet_soup); R1: milk_1(milk); R2: tomato_sauce_1(tomato_sauce); R3: butter_1(butter); R4: orange_juice_1(orange_juice) | basket_1 |
| 2 | salad_dressing_1(salad_dressing) | R0: ketchup_1(ketchup); R1: alphabet_soup_1(alphabet_soup); R2: cream_cheese_1(cream_cheese); R3: milk_1(milk); R4: tomato_sauce_1(tomato_sauce) | basket_1 |
| 3 | bbq_sauce_1(bbq_sauce) | R0: chocolate_pudding_1(chocolate_pudding); R1: ketchup_1(ketchup); R2: salad_dressing_1(salad_dressing); R3: alphabet_soup_1(alphabet_soup); R4: cream_cheese_1(cream_cheese) | basket_1 |
| 4 | ketchup_1(ketchup) | R0: bbq_sauce_1(bbq_sauce); R1: salad_dressing_1(salad_dressing); R2: alphabet_soup_1(alphabet_soup); R3: cream_cheese_1(cream_cheese); R4: milk_1(milk) | basket_1 |
| 5 | tomato_sauce_1(tomato_sauce) | R0: milk_1(milk); R1: butter_1(butter); R2: orange_juice_1(orange_juice); R3: chocolate_pudding_1(chocolate_pudding); R4: bbq_sauce_1(bbq_sauce) | basket_1 |
| 6 | butter_1(butter) | R0: tomato_sauce_1(tomato_sauce); R1: orange_juice_1(orange_juice); R2: chocolate_pudding_1(chocolate_pudding); R3: bbq_sauce_1(bbq_sauce); R4: ketchup_1(ketchup) | basket_1 |
| 7 | milk_1(milk) | R0: cream_cheese_1(cream_cheese); R1: tomato_sauce_1(tomato_sauce); R2: butter_1(butter); R3: orange_juice_1(orange_juice); R4: chocolate_pudding_1(chocolate_pudding) | basket_1 |
| 8 | chocolate_pudding_1(chocolate_pudding) | R0: orange_juice_1(orange_juice); R1: bbq_sauce_1(bbq_sauce); R2: ketchup_1(ketchup); R3: salad_dressing_1(salad_dressing); R4: alphabet_soup_1(alphabet_soup) | basket_1 |
| 9 | orange_juice_1(orange_juice) | R0: butter_1(butter); R1: chocolate_pudding_1(chocolate_pudding); R2: bbq_sauce_1(bbq_sauce); R3: ketchup_1(ketchup); R4: salad_dressing_1(salad_dressing) | basket_1 |

## 3. 物体 × 任务矩阵（T=目标需操作，D=干扰物，B=basket）

| 物体 \ 任务 | T0 | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | 出现次数（T/D） |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| alphabet_soup | T | D | D | D | D |  |  |  | D |  | 1 T / 5 D |
| salad_dressing | D |  | T | D | D |  |  |  | D | D | 1 T / 5 D |
| cream_cheese | D | T | D | D | D |  |  | D |  |  | 1 T / 5 D |
| milk | D | D | D |  | D | D |  | T |  |  | 1 T / 5 D |
| tomato_sauce | D | D | D |  |  | T | D | D |  |  | 1 T / 5 D |
| butter | D | D |  |  |  | D | T | D |  | D | 1 T / 5 D |
| orange_juice |  | D |  |  |  | D | D | D | D | T | 1 T / 5 D |
| ketchup |  |  | D | D | T |  | D |  | D | D | 1 T / 5 D |
| bbq_sauce |  |  |  | T | D | D | D |  | D | D | 1 T / 5 D |
| chocolate_pudding |  |  |  | D |  | D | D | D | T | D | 1 T / 5 D |

说明：每个物体类型恰好 1 次作为目标（T）、5 次作为干扰项（D），总计 6 个任务；basket 在 10 个任务全部存在（B）。

## 4. 组合任务时的含义

- 同套件两两组合 = 把两个任务的目标物体都放进 basket：goal = `(In A basket) ∧ (In B basket)`，需要操作的物体变成 2 个；basket 始终只保留一个。
- 合并场景要放下两个任务的**非-basket 物体并集**（7/8/9/10 个），而原场景只有 6 个物体槽（目标位 + 5 干扰位），因此需要新增 1~4 个地面槽位（union7→+1、8→+2、9→+3、10→+4），并做几何与 50 行碰撞验证。
- union=10 的 15 对需要第 4 个新增槽，未验证 → 在原始实验中被跳过；实际构造并静态验证通过的是 union≤9 的 30 对。

来源：`openpi/third_party/libero` 原版 `bddl_files/libero_object/*.bddl`；官方 benchmark 顺序 `task_order_index=0`；解析脚本重跑于 2026-10-23。
