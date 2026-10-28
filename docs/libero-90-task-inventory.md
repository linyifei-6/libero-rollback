# LIBERO-90 任务清单与 rollback 基础测试集筛选

这是对 LIBERO-90 的静态清点与候选筛选结果，不是数据集版本，也不含任何仿真验证证据。

## 来源与解析口径

- 任务顺序、BDDL 路径取自 `libero-plus` 源码 `libero/libero/bddl_files/libero_90/tasks_info.txt`（90 条，无缺项、无多余项），
  逐条解析同目录 BDDL 的 `:language`、`:goal`、`:init`。
- 本文件的任务编号 `00`–`89` 按该清单顺序固定，只在本文件内使用，不是数据集任务 ID。
- 90 条任务分布在 20 个场景；其中 11 条的目标是双原子条件，其余 79 条为单一目标。
- 复现：`python3 scripts/analyze_libero90_tasks.py`（只读解析，不运行仿真，不写数据集）。

## 判定规则：什么算“至少两段子任务”

rollback 基础用例要求存在“已完成的前序子任务 s1”和“正在执行的后续子任务 s2”，
合法性口径见 [`subtask-stages.md`](subtask-stages.md)。因此这里按三条同时成立来判定：

1. BDDL `:goal` 至少有两个原子条件；
2. 这些原子条件在 `:init` 中都不成立——初始即为真的条件不构成独立执行段；
3. 两段有固定先后顺序，s2 执行期间 s1 已完成且可被外部撤销。

按此规则，11 条双原子任务中 10 条成立，`17` 因 `Turnon` 已在 `:init` 成立而落选。

分级依据引擎现有机制（`revert_articulation_goal` 等回退效果见
[`rollback-case.v1.schema.json`](../schemas/rollback-case.v1.schema.json)）：

| 级别 | 含义 |
| --- | --- |
| A | s1、s2 都落在已建模机制内（放置关系 On/In、关节回退 Open/Close），可直接构造用例 |
| B | 机制可用，但 s1 与 s2 共用同一组物体、s2 期间物体在夹爪中，合法干预窗口受限 |
| C | 含开关类目标（Turnon/Turnoff），当前 runtime profile 未建模，需先补配置 |

pi05 baseline 实测：单 seed（seed 3）见 [`libero-90-baseline-pi05-seed3.md`](libero-90-baseline-pi05-seed3.md)，5 种子扫描与失败原因诊断见 [`libero-90-baseline-seed-sweep.md`](libero-90-baseline-seed-sweep.md)。

## 筛选结果：10 条基础候选

| 序号 | 指令 | s1（已完成，可回滚） | s2（执行中） | 机制 | 级别 | 建议优先级 |
| --- | --- | --- | --- | --- | --- | --- |
| `26` | 把前排的黄油放进橱柜上层抽屉并关上 | `(In butter_1 wooden_cabinet_1_top_region)` 前排黄油入上层抽屉 | `(Close wooden_cabinet_1_top_region)` 关上上层抽屉 | 放置 + 关节回退（`revert_articulation_goal`，slide） | A | P0 |
| `27` | 把后排的黄油放进橱柜上层抽屉并关上 | `(In butter_2 wooden_cabinet_1_top_region)` 后排黄油入上层抽屉 | `(Close wooden_cabinet_1_top_region)` 关上上层抽屉 | 放置 + 关节回退（slide） | A | P0 |
| `28` | 把巧克力布丁放进橱柜上层抽屉并关上 | `(In chocolate_pudding_1 wooden_cabinet_1_top_region)` 布丁入上层抽屉 | `(Close wooden_cabinet_1_top_region)` 关上上层抽屉 | 放置 + 关节回退（slide） | A | P0 |
| `00` | 打开橱柜上层抽屉，把碗放进去 | `(Open wooden_cabinet_1_top_region)` 打开上层抽屉 | `(In akita_black_bowl_1 wooden_cabinet_1_top_region)` 把碗放进抽屉 | 关节回退（slide）+ 放置 | A | P1 |
| `25` | 关上橱柜上层抽屉，把黑碗放到柜顶 | `(Close wooden_cabinet_1_top_region)` 关上上层抽屉 | `(On akita_black_bowl_1 wooden_cabinet_1_top_side)` 把黑碗放到柜顶 | 关节回退（slide）+ 放置 | A | P1 |
| `09` | 关上橱柜下层抽屉，打开上层抽屉 | `(Close white_cabinet_1_bottom_region)` 关上下层抽屉（初始为开） | `(Open white_cabinet_1_top_region)` 打开上层抽屉 | 关节回退 + 关节回退（同一柜体两个关节） | A | P2 |
| `40` | 把左边的碗叠到右边的碗上，再把两只碗一起放进托盘 | `(On akita_black_bowl_1 akita_black_bowl_2)` 把左碗叠到右碗上 | `(In akita_black_bowl_2 wooden_tray_1_contain_region)` 把叠好的碗一起放进托盘 | 放置 + 放置 | B | P3 |
| `41` | 把右边的碗叠到左边的碗上，再把两只碗一起放进托盘 | `(On akita_black_bowl_2 akita_black_bowl_1)` 把右碗叠到左碗上 | `(In akita_black_bowl_1 wooden_tray_1_contain_region)` 把叠好的碗一起放进托盘 | 放置 + 放置 | B | P3 |
| `05` | 打开炉子，把煎锅放上去 | `(Turnon flat_stove_1)` 打开炉子 | `(On chefmate_8_frypan_1 flat_stove_1_cook_region)` 把煎锅放上炉子 | 开关目标（当前未建模）+ 放置 | C | 暂不推荐 |
| `19` | 打开炉子，把煎锅放上去 | `(Turnon flat_stove_1)` 打开炉子 | `(On chefmate_8_frypan_1 flat_stove_1_cook_region)` 把煎锅放上炉子 | 开关目标（当前未建模）+ 放置 | C | 暂不推荐 |

### 逐条说明

#### `26` 把前排的黄油放进橱柜上层抽屉并关上

- 英文指令：`put the butter at the front in the top drawer of the cabinet and close it`
- 目标谓词：`(In butter_1 wooden_cabinet_1_top_region)` ; `(Close wooden_cabinet_1_top_region)`
- s1：`(In butter_1 wooden_cabinet_1_top_region)` 前排黄油入上层抽屉
- s2：`(Close wooden_cabinet_1_top_region)` 关上上层抽屉
- 机制：放置 + 关节回退（`revert_articulation_goal`，slide）
- 级别 / 优先级：A / P0
- 说明：与 LIBERO-10 `/01`（t33 黑碗入下层抽屉 + 关抽屉）同构，已跑通的三段合法窗口（`post_completion_retreat` / `x3a_actuation` / `x3b_completion_approach`）可直接迁移；与 #27 构成前排/后排对照。

#### `27` 把后排的黄油放进橱柜上层抽屉并关上

- 英文指令：`put the butter at the back in the top drawer of the cabinet and close it`
- 目标谓词：`(In butter_2 wooden_cabinet_1_top_region)` ; `(Close wooden_cabinet_1_top_region)`
- s1：`(In butter_2 wooden_cabinet_1_top_region)` 后排黄油入上层抽屉
- s2：`(Close wooden_cabinet_1_top_region)` 关上上层抽屉
- 机制：放置 + 关节回退（slide）
- 级别 / 优先级：A / P0
- 说明：与 #26 同场景、同关节，只替换被放置物体；两者对照可分离“物体身份/初始位姿”与“关节回退”两个因素。

#### `28` 把巧克力布丁放进橱柜上层抽屉并关上

- 英文指令：`put the chocolate pudding in the top drawer of the cabinet and close it`
- 目标谓词：`(In chocolate_pudding_1 wooden_cabinet_1_top_region)` ; `(Close wooden_cabinet_1_top_region)`
- s1：`(In chocolate_pudding_1 wooden_cabinet_1_top_region)` 布丁入上层抽屉
- s2：`(Close wooden_cabinet_1_top_region)` 关上上层抽屉
- 机制：放置 + 关节回退（slide）
- 级别 / 优先级：A / P0
- 说明：同场景第三种物体，验证结论不依赖单一物体几何（黄油盒 vs 布丁杯）。

#### `00` 打开橱柜上层抽屉，把碗放进去

- 英文指令：`open the top drawer of the cabinet and put the bowl in it`
- 目标谓词：`(Open wooden_cabinet_1_top_region)` ; `(In akita_black_bowl_1 wooden_cabinet_1_top_region)`
- s1：`(Open wooden_cabinet_1_top_region)` 打开上层抽屉
- s2：`(In akita_black_bowl_1 wooden_cabinet_1_top_region)` 把碗放进抽屉
- 机制：关节回退（slide）+ 放置
- 级别 / 优先级：A / P1
- 说明：与 #26–28 顺序相反：s1 是关节、s2 是放置，回滚 s1 等于把已打开的抽屉重新推回。覆盖“开放型关节目标被撤销”，现有数据集只有“关闭型”（t33/t78）。需确认回滚窗口内机械臂正持碗接近抽屉时抽屉回退不与之碰撞。

#### `25` 关上橱柜上层抽屉，把黑碗放到柜顶

- 英文指令：`close the top drawer of the cabinet and put the black bowl on top of it`
- 目标谓词：`(Close wooden_cabinet_1_top_region)` ; `(On akita_black_bowl_1 wooden_cabinet_1_top_side)`
- s1：`(Close wooden_cabinet_1_top_region)` 关上上层抽屉
- s2：`(On akita_black_bowl_1 wooden_cabinet_1_top_side)` 把黑碗放到柜顶
- 机制：关节回退（slide）+ 放置
- 级别 / 优先级：A / P1
- 说明：s2 的落点是柜顶平面（`top_side`）而非容器内部，可与 #26–28 对照“恢复后关系是否仍可达成”；回滚 s1 会让抽屉朝机械臂方向滑出，需在有效性约束中显式检查碰撞。

#### `09` 关上橱柜下层抽屉，打开上层抽屉

- 英文指令：`close the bottom drawer of the cabinet and open the top drawer`
- 目标谓词：`(Close white_cabinet_1_bottom_region)` ; `(Open white_cabinet_1_top_region)`
- s1：`(Close white_cabinet_1_bottom_region)` 关上下层抽屉（初始为开）
- s2：`(Open white_cabinet_1_top_region)` 打开上层抽屉
- 机制：关节回退 + 关节回退（同一柜体两个关节）
- 级别 / 优先级：A / P2
- 说明：唯一一条两段都是关节的目标。可检验“同一刚体上另一个关节正在动作时回退已完成的关节”。前提：上层与下层必须是可独立寻址的两个 joint_role，需在 runtime profile 中确认。

#### `40` 把左边的碗叠到右边的碗上，再把两只碗一起放进托盘

- 英文指令：`stack the left bowl on the right bowl and place them in the tray`
- 目标谓词：`(On akita_black_bowl_1 akita_black_bowl_2)` ; `(In akita_black_bowl_2 wooden_tray_1_contain_region)`
- s1：`(On akita_black_bowl_1 akita_black_bowl_2)` 把左碗叠到右碗上
- s2：`(In akita_black_bowl_2 wooden_tray_1_contain_region)` 把叠好的碗一起放进托盘
- 机制：放置 + 放置
- 级别 / 优先级：B / P3
- 说明：机制可用，但 s2 期间两碗作为一个整体在夹爪中移动，回滚 s1（把上碗取下）只能在放置完成后或搬运中的极窄窗口进行，需先定义可干预时机；完成后可分别撤销“入托盘”和“叠放”两个关系。

#### `41` 把右边的碗叠到左边的碗上，再把两只碗一起放进托盘

- 英文指令：`stack the right bowl on the left bowl and place them in the tray`
- 目标谓词：`(On akita_black_bowl_2 akita_black_bowl_1)` ; `(In akita_black_bowl_1 wooden_tray_1_contain_region)`
- s1：`(On akita_black_bowl_2 akita_black_bowl_1)` 把右碗叠到左碗上
- s2：`(In akita_black_bowl_1 wooden_tray_1_contain_region)` 把叠好的碗一起放进托盘
- 机制：放置 + 放置
- 级别 / 优先级：B / P3
- 说明：#40 的镜像，用于检验恢复顺序是否被固定物体身份影响。限制同 #40。

#### `05` 打开炉子，把煎锅放上去

- 英文指令：`turn on the stove and put the frying pan on it`
- 目标谓词：`(Turnon flat_stove_1)` ; `(On chefmate_8_frypan_1 flat_stove_1_cook_region)`
- s1：`(Turnon flat_stove_1)` 打开炉子
- s2：`(On chefmate_8_frypan_1 flat_stove_1_cook_region)` 把煎锅放上炉子
- 机制：开关目标（当前未建模）+ 放置
- 级别 / 优先级：C / 暂不推荐
- 说明：与 LIBERO-10 `/00`（t0）同构：runtime profile 未建模 Turnon，没有对应的 articulation/joint 段，s1 目前无法回滚。需先补开关建模配置才可入选。

#### `19` 打开炉子，把煎锅放上去

- 英文指令：`turn on the stove and put the frying pan on it`
- 目标谓词：`(Turnon flat_stove_1)` ; `(On chefmate_8_frypan_1 flat_stove_1_cook_region)`
- s1：`(Turnon flat_stove_1)` 打开炉子
- s2：`(On chefmate_8_frypan_1 flat_stove_1_cook_region)` 把煎锅放上炉子
- 机制：开关目标（当前未建模）+ 放置
- 级别 / 优先级：C / 暂不推荐
- 说明：#05 的同指令不同场景（KITCHEN_SCENE9，场景内另有白碗与双层架）。与 #05 同时入选才有对照价值，单独入选收益有限。

## 落选说明

| 序号 | 指令 | 目标谓词 | 落选原因 |
| --- | --- | --- | --- |
| `17` | 把右边的摩卡壶放到炉子上 | `(On moka_pot_1 flat_stove_1_cook_region)` ; `(Turnon flat_stove_1)` | `(Turnon flat_stove_1)` 已出现在 `:init` 中，初始即为真，实际只有“把摩卡壶放上炉子”一段有效阶段，不构成两段子任务。 |
| `58` | 把中间的黑碗叠到前排的黑碗上 | `(On akita_black_bowl_2 akita_black_bowl_3)` | 目标是单一 `On` 关系（叠放本身），只有一段执行阶段；`58`/`59` 是镜像对，可作为同一阶段内的物体选择变量，不满足两段要求。 |
| `59` | 把前排的黑碗叠到中间的黑碗上 | `(On akita_black_bowl_1 akita_black_bowl_2)` | 目标是单一 `On` 关系（叠放本身），只有一段执行阶段；`58`/`59` 是镜像对，可作为同一阶段内的物体选择变量，不满足两段要求。 |

其余 79 条任务的目标都是单一原子条件（一个 `On`/`In`/`Open`/`Close`/`Turnon`/`Turnoff`），只有一段执行阶段。
说明：其中“把物体放进抽屉/微波炉”一类任务的容器在 `:init` 中已经是打开状态
（如 `12`/`13`/`29`/`60`/`62`、`68`–`84` 的收纳架格），不存在隐含的“先开容器”阶段；
“pick up … and put it in …” 的 `pick up` 是达成同一目标的抓取过程，不是独立子任务。

`58` 另有一处来源标注不一致：指令写 “the black bowl at the front”，
但目标谓词叠到的是 `akita_black_bowl_3`，其初始位姿在 `..._back_init_region`。
本文件按指令原文翻译；若后续要用这条任务，必须先核对实际目标对象。

单目标任务并非不能做 rollback，但只能在完成边界撤销，
与“s2 执行中回滚 s1”不是同一类场景，因此不计入本基础测试集。

## 全部 90 条任务描述

“有效阶段数”= `:goal` 中在 `:init` 未成立的原子条件数。

| 序号 | 场景 | 英文指令（`:language`） | 中文 | 目标谓词 | 有效阶段数 | 入选 |
| --- | --- | --- | --- | --- | --- | --- |
| `00` | KITCHEN_SCENE1 | open the top drawer of the cabinet and put the bowl in it | 打开橱柜上层抽屉，把碗放进去 | `(Open wooden_cabinet_1_top_region)` ; `(In akita_black_bowl_1 wooden_cabinet_1_top_region)` | 2 | A |
| `01` | KITCHEN_SCENE1 | put the black bowl on top of the cabinet | 把黑碗放到橱柜顶上 | `(On akita_black_bowl_1 wooden_cabinet_1_top_side)` | 1 |  |
| `02` | KITCHEN_SCENE1 | put the black bowl on the plate | 把黑碗放到盘子上 | `(On akita_black_bowl_1 plate_1)` | 1 |  |
| `03` | KITCHEN_SCENE1 | open the top drawer of the cabinet | 打开橱柜上层抽屉 | `(Open wooden_cabinet_1_top_region)` | 1 |  |
| `04` | KITCHEN_SCENE1 | open the bottom drawer of the cabinet | 打开橱柜下层抽屉 | `(Open wooden_cabinet_1_bottom_region)` | 1 |  |
| `05` | KITCHEN_SCENE3 | turn on the stove and put the frying pan on it | 打开炉子，把煎锅放上去 | `(Turnon flat_stove_1)` ; `(On chefmate_8_frypan_1 flat_stove_1_cook_region)` | 2 | C |
| `06` | KITCHEN_SCENE3 | put the frying pan on the stove | 把煎锅放到炉子上 | `(On chefmate_8_frypan_1 flat_stove_1_cook_region)` | 1 |  |
| `07` | KITCHEN_SCENE3 | put the moka pot on the stove | 把摩卡壶放到炉子上 | `(On moka_pot_1 flat_stove_1_cook_region)` | 1 |  |
| `08` | KITCHEN_SCENE3 | turn on the stove | 打开炉子 | `(Turnon flat_stove_1)` | 1 |  |
| `09` | KITCHEN_SCENE4 | close the bottom drawer of the cabinet and open the top drawer | 关上橱柜下层抽屉，打开上层抽屉 | `(Close white_cabinet_1_bottom_region)` ; `(Open white_cabinet_1_top_region)` | 2 | A |
| `10` | KITCHEN_SCENE4 | put the wine bottle on the wine rack | 把酒瓶放到酒架上 | `(On wine_bottle_1 wine_rack_1_top_region)` | 1 |  |
| `11` | KITCHEN_SCENE4 | put the black bowl on top of the cabinet | 把黑碗放到橱柜顶上 | `(On akita_black_bowl_1 white_cabinet_1_top_side)` | 1 |  |
| `12` | KITCHEN_SCENE4 | put the black bowl in the bottom drawer of the cabinet | 把黑碗放进橱柜下层抽屉 | `(In akita_black_bowl_1 white_cabinet_1_bottom_region)` | 1 |  |
| `13` | KITCHEN_SCENE4 | put the wine bottle in the bottom drawer of the cabinet | 把酒瓶放进橱柜下层抽屉 | `(In wine_bottle_1 white_cabinet_1_bottom_region)` | 1 |  |
| `14` | KITCHEN_SCENE4 | close the bottom drawer of the cabinet | 关上橱柜下层抽屉 | `(Close white_cabinet_1_bottom_region)` | 1 |  |
| `15` | KITCHEN_SCENE6 | put the yellow and white mug to the front of the white mug | 把黄白马克杯放到白瓷杯前面 | `(On white_yellow_mug_1 kitchen_table_porcelain_mug_front_region)` | 1 |  |
| `16` | KITCHEN_SCENE6 | close the microwave | 关上微波炉 | `(Close microwave_1)` | 1 |  |
| `17` | KITCHEN_SCENE8 | put the right moka pot on the stove | 把右边的摩卡壶放到炉子上 | `(On moka_pot_1 flat_stove_1_cook_region)` ; `(Turnon flat_stove_1)` | 1 |  |
| `18` | KITCHEN_SCENE8 | turn off the stove | 关掉炉子 | `(Turnoff flat_stove_1)` | 1 |  |
| `19` | KITCHEN_SCENE9 | turn on the stove and put the frying pan on it | 打开炉子，把煎锅放上去 | `(Turnon flat_stove_1)` ; `(On chefmate_8_frypan_1 flat_stove_1_cook_region)` | 2 | C |
| `20` | KITCHEN_SCENE9 | put the frying pan on top of the cabinet | 把煎锅放到柜架顶上 | `(On chefmate_8_frypan_1 wooden_two_layer_shelf_1_top_side)` | 1 |  |
| `21` | KITCHEN_SCENE9 | put the white bowl on top of the cabinet | 把白碗放到柜架顶上 | `(On white_bowl_1 wooden_two_layer_shelf_1_top_side)` | 1 |  |
| `22` | KITCHEN_SCENE9 | put the frying pan on the cabinet shelf | 把煎锅放到柜架隔板上 | `(In chefmate_8_frypan_1 wooden_two_layer_shelf_1_top_region)` | 1 |  |
| `23` | KITCHEN_SCENE9 | put the frying pan under the cabinet shelf | 把煎锅放到柜架隔板下面 | `(In chefmate_8_frypan_1 wooden_two_layer_shelf_1_bottom_region)` | 1 |  |
| `24` | KITCHEN_SCENE9 | turn on the stove | 打开炉子 | `(Turnon flat_stove_1)` | 1 |  |
| `25` | KITCHEN_SCENE10 | close the top drawer of the cabinet and put the black bowl on top of it | 关上橱柜上层抽屉，把黑碗放到柜顶 | `(Close wooden_cabinet_1_top_region)` ; `(On akita_black_bowl_1 wooden_cabinet_1_top_side)` | 2 | A |
| `26` | KITCHEN_SCENE10 | put the butter at the front in the top drawer of the cabinet and close it | 把前排的黄油放进橱柜上层抽屉并关上 | `(In butter_1 wooden_cabinet_1_top_region)` ; `(Close wooden_cabinet_1_top_region)` | 2 | A |
| `27` | KITCHEN_SCENE10 | put the butter at the back in the top drawer of the cabinet and close it | 把后排的黄油放进橱柜上层抽屉并关上 | `(In butter_2 wooden_cabinet_1_top_region)` ; `(Close wooden_cabinet_1_top_region)` | 2 | A |
| `28` | KITCHEN_SCENE10 | put the chocolate pudding in the top drawer of the cabinet and close it | 把巧克力布丁放进橱柜上层抽屉并关上 | `(In chocolate_pudding_1 wooden_cabinet_1_top_region)` ; `(Close wooden_cabinet_1_top_region)` | 2 | A |
| `29` | KITCHEN_SCENE10 | put the black bowl in the top drawer of the cabinet | 把黑碗放进橱柜上层抽屉 | `(In akita_black_bowl_1 wooden_cabinet_1_top_region)` | 1 |  |
| `30` | KITCHEN_SCENE10 | close the top drawer of the cabinet | 关上橱柜上层抽屉 | `(Close wooden_cabinet_1_top_region)` | 1 |  |
| `31` | LIVING_ROOM_SCENE1 | pick up the ketchup and put it in the basket | 拿起番茄沙司放进篮子 | `(In ketchup_1 basket_1_contain_region)` | 1 |  |
| `32` | LIVING_ROOM_SCENE1 | pick up the cream cheese box and put it in the basket | 拿起奶油芝士盒放进篮子 | `(In cream_cheese_1 basket_1_contain_region)` | 1 |  |
| `33` | LIVING_ROOM_SCENE1 | pick up the alphabet soup and put it in the basket | 拿起字母汤罐头放进篮子 | `(In alphabet_soup_1 basket_1_contain_region)` | 1 |  |
| `34` | LIVING_ROOM_SCENE1 | pick up the tomato sauce and put it in the basket | 拿起番茄酱罐头放进篮子 | `(In tomato_sauce_1 basket_1_contain_region)` | 1 |  |
| `35` | LIVING_ROOM_SCENE2 | pick up the orange juice and put it in the basket | 拿起橙汁放进篮子 | `(In orange_juice_1 basket_1_contain_region)` | 1 |  |
| `36` | LIVING_ROOM_SCENE2 | pick up the milk and put it in the basket | 拿起牛奶放进篮子 | `(In milk_1 basket_1_contain_region)` | 1 |  |
| `37` | LIVING_ROOM_SCENE2 | pick up the butter and put it in the basket | 拿起黄油放进篮子 | `(In butter_1 basket_1_contain_region)` | 1 |  |
| `38` | LIVING_ROOM_SCENE2 | pick up the alphabet soup and put it in the basket | 拿起字母汤罐头放进篮子 | `(In alphabet_soup_1 basket_1_contain_region)` | 1 |  |
| `39` | LIVING_ROOM_SCENE2 | pick up the tomato sauce and put it in the basket | 拿起番茄酱罐头放进篮子 | `(In tomato_sauce_1 basket_1_contain_region)` | 1 |  |
| `40` | LIVING_ROOM_SCENE4 | stack the left bowl on the right bowl and place them in the tray | 把左边的碗叠到右边的碗上，再把两只碗一起放进托盘 | `(On akita_black_bowl_1 akita_black_bowl_2)` ; `(In akita_black_bowl_2 wooden_tray_1_contain_region)` | 2 | B |
| `41` | LIVING_ROOM_SCENE4 | stack the right bowl on the left bowl and place them in the tray | 把右边的碗叠到左边的碗上，再把两只碗一起放进托盘 | `(On akita_black_bowl_2 akita_black_bowl_1)` ; `(In akita_black_bowl_1 wooden_tray_1_contain_region)` | 2 | B |
| `42` | LIVING_ROOM_SCENE4 | pick up the black bowl on the left and put it in the tray | 拿起左边的黑碗放进托盘 | `(In akita_black_bowl_1 wooden_tray_1_contain_region)` | 1 |  |
| `43` | LIVING_ROOM_SCENE4 | pick up the salad dressing and put it in the tray | 拿起沙拉酱放进托盘 | `(In new_salad_dressing_1 wooden_tray_1_contain_region)` | 1 |  |
| `44` | LIVING_ROOM_SCENE4 | pick up the chocolate pudding and put it in the tray | 拿起巧克力布丁放进托盘 | `(In chocolate_pudding_1 wooden_tray_1_contain_region)` | 1 |  |
| `45` | LIVING_ROOM_SCENE5 | put the white mug on the left plate | 把白瓷杯放到左边的盘子上 | `(On porcelain_mug_1 plate_1)` | 1 |  |
| `46` | LIVING_ROOM_SCENE5 | put the yellow and white mug on the right plate | 把黄白马克杯放到右边的盘子上 | `(On white_yellow_mug_1 plate_2)` | 1 |  |
| `47` | LIVING_ROOM_SCENE5 | put the red mug on the left plate | 把红马克杯放到左边的盘子上 | `(On red_coffee_mug_1 plate_1)` | 1 |  |
| `48` | LIVING_ROOM_SCENE5 | put the red mug on the right plate | 把红马克杯放到右边的盘子上 | `(On red_coffee_mug_1 plate_2)` | 1 |  |
| `49` | LIVING_ROOM_SCENE6 | put the white mug on the plate | 把白瓷杯放到盘子上 | `(On porcelain_mug_1 plate_1)` | 1 |  |
| `50` | LIVING_ROOM_SCENE6 | put the red mug on the plate | 把红马克杯放到盘子上 | `(On red_coffee_mug_1 plate_1)` | 1 |  |
| `51` | LIVING_ROOM_SCENE6 | put the chocolate pudding to the left of the plate | 把巧克力布丁放到盘子左边 | `(On chocolate_pudding_1 living_room_table_plate_left_region)` | 1 |  |
| `52` | LIVING_ROOM_SCENE6 | put the chocolate pudding to the right of the plate | 把巧克力布丁放到盘子右边 | `(On chocolate_pudding_1 living_room_table_plate_right_region)` | 1 |  |
| `53` | KITCHEN_SCENE2 | put the black bowl at the back on the plate | 把后排的黑碗放到盘子上 | `(On akita_black_bowl_3 plate_1)` | 1 |  |
| `54` | KITCHEN_SCENE2 | put the black bowl at the front on the plate | 把前排的黑碗放到盘子上 | `(On akita_black_bowl_1 plate_1)` | 1 |  |
| `55` | KITCHEN_SCENE2 | put the black bowl in the middle on the plate | 把中间的黑碗放到盘子上 | `(On akita_black_bowl_2 plate_1)` | 1 |  |
| `56` | KITCHEN_SCENE2 | put the middle black bowl on top of the cabinet | 把中间的黑碗放到橱柜顶上 | `(On akita_black_bowl_2 wooden_cabinet_1_top_side)` | 1 |  |
| `57` | KITCHEN_SCENE2 | open the top drawer of the cabinet | 打开橱柜上层抽屉 | `(Open wooden_cabinet_1_top_region)` | 1 |  |
| `58` | KITCHEN_SCENE2 | stack the black bowl in the middle on the black bowl at the front | 把中间的黑碗叠到前排的黑碗上 | `(On akita_black_bowl_2 akita_black_bowl_3)` | 1 |  |
| `59` | KITCHEN_SCENE2 | stack the black bowl at the front on the black bowl in the middle | 把前排的黑碗叠到中间的黑碗上 | `(On akita_black_bowl_1 akita_black_bowl_2)` | 1 |  |
| `60` | KITCHEN_SCENE5 | put the black bowl in the top drawer of the cabinet | 把黑碗放进橱柜上层抽屉 | `(In akita_black_bowl_1 white_cabinet_1_top_region)` | 1 |  |
| `61` | KITCHEN_SCENE5 | put the black bowl on the plate | 把黑碗放到盘子上 | `(On akita_black_bowl_1 plate_1)` | 1 |  |
| `62` | KITCHEN_SCENE5 | put the ketchup in the top drawer of the cabinet | 把番茄沙司放进橱柜上层抽屉 | `(In ketchup_1 white_cabinet_1_top_region)` | 1 |  |
| `63` | KITCHEN_SCENE5 | put the black bowl on top of the cabinet | 把黑碗放到橱柜顶上 | `(On akita_black_bowl_1 white_cabinet_1_top_side)` | 1 |  |
| `64` | KITCHEN_SCENE5 | close the top drawer of the cabinet | 关上橱柜上层抽屉 | `(Close white_cabinet_1_top_region)` | 1 |  |
| `65` | KITCHEN_SCENE7 | put the white bowl on the plate | 把白碗放到盘子上 | `(On white_bowl_1 plate_1)` | 1 |  |
| `66` | KITCHEN_SCENE7 | put the white bowl to the right of the plate | 把白碗放到盘子右边 | `(On white_bowl_1 kitchen_table_plate_right_region)` | 1 |  |
| `67` | KITCHEN_SCENE7 | open the microwave | 打开微波炉 | `(Open microwave_1)` | 1 |  |
| `68` | STUDY_SCENE1 | pick up the book and place it in the left compartment of the caddy | 拿起书放进收纳架的左格 | `(In black_book_1 desk_caddy_1_left_contain_region)` | 1 |  |
| `69` | STUDY_SCENE1 | pick up the book and place it in the right compartment of the caddy | 拿起书放进收纳架的右格 | `(In black_book_1 desk_caddy_1_right_contain_region)` | 1 |  |
| `70` | STUDY_SCENE1 | pick up the book and place it in the front compartment of the caddy | 拿起书放进收纳架的前格 | `(In black_book_1 desk_caddy_1_front_contain_region)` | 1 |  |
| `71` | STUDY_SCENE1 | pick up the yellow and white mug and place it to the right of the caddy | 拿起黄白马克杯放到收纳架右边 | `(On white_yellow_mug_1 study_table_desk_caddy_right_region)` | 1 |  |
| `72` | STUDY_SCENE2 | pick up the book and place it in the left compartment of the caddy | 拿起书放进收纳架的左格 | `(In black_book_1 desk_caddy_1_left_contain_region)` | 1 |  |
| `73` | STUDY_SCENE2 | pick up the book and place it in the right compartment of the caddy | 拿起书放进收纳架的右格 | `(In black_book_1 desk_caddy_1_right_contain_region)` | 1 |  |
| `74` | STUDY_SCENE2 | pick up the book and place it in the front compartment of the caddy | 拿起书放进收纳架的前格 | `(In black_book_1 desk_caddy_1_front_contain_region)` | 1 |  |
| `75` | STUDY_SCENE2 | pick up the book and place it in the back compartment of the caddy | 拿起书放进收纳架的后格 | `(In black_book_1 desk_caddy_1_back_contain_region)` | 1 |  |
| `76` | STUDY_SCENE3 | pick up the book and place it in the left compartment of the caddy | 拿起书放进收纳架的左格 | `(In black_book_1 desk_caddy_1_left_contain_region)` | 1 |  |
| `77` | STUDY_SCENE3 | pick up the book and place it in the right compartment of the caddy | 拿起书放进收纳架的右格 | `(In black_book_1 desk_caddy_1_right_contain_region)` | 1 |  |
| `78` | STUDY_SCENE3 | pick up the book and place it in the front compartment of the caddy | 拿起书放进收纳架的前格 | `(In black_book_1 desk_caddy_1_front_contain_region)` | 1 |  |
| `79` | STUDY_SCENE3 | pick up the white mug and place it to the right compartment of the caddy | 拿起白瓷杯放到收纳架右侧 | `(On porcelain_mug_1 study_table_desk_caddy_right_region)` | 1 |  |
| `80` | STUDY_SCENE3 | pick up the red mug and place it to the right compartment of the caddy | 拿起红马克杯放到收纳架右侧 | `(On red_coffee_mug_1 study_table_desk_caddy_right_region)` | 1 |  |
| `81` | STUDY_SCENE4 | pick up the book on the right and place it under the cabinet shelf | 拿起右边的书放到柜架隔板下面 | `(In yellow_book_1 wooden_two_layer_shelf_1_bottom_region)` | 1 |  |
| `82` | STUDY_SCENE4 | pick up the book in the middle and place it on the cabinet shelf | 拿起中间的书放到柜架隔板上 | `(In black_book_1 wooden_two_layer_shelf_1_top_region)` | 1 |  |
| `83` | STUDY_SCENE4 | pick up the book on the left and place it on top of the shelf | 拿起左边的书放到架子顶上 | `(On yellow_book_2 wooden_two_layer_shelf_1_top_side)` | 1 |  |
| `84` | STUDY_SCENE4 | pick up the book on the right and place it on the cabinet shelf | 拿起右边的书放到柜架隔板上 | `(In yellow_book_1 wooden_two_layer_shelf_1_top_region)` | 1 |  |
| `85` | LIVING_ROOM_SCENE3 | pick up the alphabet soup and put it in the tray | 拿起字母汤罐头放进托盘 | `(In alphabet_soup_1 wooden_tray_1_contain_region)` | 1 |  |
| `86` | LIVING_ROOM_SCENE3 | pick up the tomato sauce and put it in the tray | 拿起番茄酱罐头放进托盘 | `(In tomato_sauce_1 wooden_tray_1_contain_region)` | 1 |  |
| `87` | LIVING_ROOM_SCENE3 | pick up the butter and put it in the tray | 拿起黄油放进托盘 | `(In butter_1 wooden_tray_1_contain_region)` | 1 |  |
| `88` | LIVING_ROOM_SCENE3 | pick up the cream cheese and put it in the tray | 拿起奶油芝士放进托盘 | `(In cream_cheese_1 wooden_tray_1_contain_region)` | 1 |  |
| `89` | LIVING_ROOM_SCENE3 | pick up the ketchup and put it in the tray | 拿起番茄沙司放进托盘 | `(In ketchup_1 wooden_tray_1_contain_region)` | 1 |  |

