# LIBERO_GOAL 双子任务 BDDL 构建与静态验证报告

> 目标：把 LIBERO_GOAL 的 10 个单目标原子任务两两组合成 45 个无序“双子任务（two-subtask）” BDDL 基线场景，并完成 CPU-only 静态验证与冲突分类。
>
> 产物目录：`/home/tarowang/workspace/roboot/libero-rollback/runs/combined-tasks-20261019/artifacts/goal-pairs`
> 生成脚本：`scripts/build_goal_pairs.py`（v1.0.0，可重入）
> 执行环境：CPU-only，shadow 原版 LIBERO 包 + libero-runtime overlay；未加载任何策略模型、未使用 GPU（`CUDA_VISIBLE_DEVICES=""`，`MUJOCO_GL=osmesa`）。

## 1. 结论摘要

| 项目 | 结果 |
|---|---|
| 任务对数 | 45/45 |
| BDDL 文件 | 45 个（`bddl/goal_pair_*.bddl`）|
| init 状态文件 | 45 个（`init/` 规范副本）+ 45 个（`bddl/` 同目录 sibling，供 runner 直接加载）|
| 冲突分类 | conflict 7 / hard 5 / compatible 33 |
| BDDL 解析验证 | 45/45 通过 |
| env 实例化冒烟 | 45/45 通过；初始 `check_success()` 全为 False：是 |
| 静态验证失败项 | 无 |
| 推荐 pilot | 首条 `goal_pair_00_01`（用户示例）+ compatible 全量 33 对 + 2 个 hard 对照 |

## 2. 数据源与场景同构性

### 2.1 任务顺序（重要修正）

LIBERO_GOAL 的官方 benchmark task 顺序（`libero_task_map['libero_goal']` + `task_orders[0]`）**不等于** bddl 文件名字母序。本产物一律使用 benchmark 顺序：`get_benchmark("LIBERO_GOAL")(task_order_index=0).get_task(i)`，因此 `goal_pair_00_01` = open_the_middle_drawer_of_the_cabinet + put_the_bowl_on_the_stove（即用户示例）。脚本对 10 个位置的 `name` 与 `goal atom` 做了 fail-fast 断言，顺序变化会直接报错。

### 2.2 场景段同构性校验

对 10 个任务同时做**原始文本段**与**解析后结构**双重比较（`section_span` 括号配对取段后归一化空白）：

| 段 | 原始文本一致 | 解析结构一致 |
|---|---|---|
| `:regions` | ✅ | ✅ |
| `:fixtures` | ✅ | ✅ |
| `:objects` | ✅ | ✅ |
| `:init` | ✅ | ✅ |

- 场景指纹 `scene_fingerprint_sha256`：`6ed41dc58c1095a06785447cdc336cb00e6b2467167f90fb7d066b3b81d4dba4`
- init states：每个任务 50 条，形状统一为 `[50, 79]`，dtype `float64`；合并场景的 init 直接二进制拷贝自任务 i（同场景结构，79 维 joint state 完全兼容）。
- 组合目标：`:goal` = `(And atom_i atom_j)`；本环境 `_check_success()` 对 `goal_state` 列表逐原子做逻辑与，因此合并目标语义为“两个子任务都完成”。

### 2.3 语言来源与 bddl 内 `:language` 偏差

组合 instruction 一律使用 benchmark 官方 `get_task(i).language`，即 `f"{lang_i} and {lang_j}"`，并写入合并 bddl 的 `:language`。

原始 bddl 文件内部的 `:language` 与 benchmark language 存在偏差的任务（合并产物已统一覆盖为 benchmark 版本）：

| idx | 任务 | bddl 内 `:language` | benchmark language |
|---|---|---|---|
| 0 | `open_the_middle_drawer_of_the_cabinet` | open the middle layer of the drawer | open the middle drawer of the cabinet |
| 2 | `put_the_wine_bottle_on_top_of_the_cabinet` | put the wine bottle on the top of the drawer | put the wine bottle on top of the cabinet |
| 3 | `open_the_top_drawer_and_put_the_bowl_inside` | open the top layer of the drawer and put the bowl inside | open the top drawer and put the bowl inside |
| 4 | `put_the_bowl_on_top_of_the_cabinet` | put the bowl on the top of the drawer | put the bowl on top of the cabinet |
| 6 | `put_the_cream_cheese_in_the_bowl` | put the cream cheese on the bowl | put the cream cheese in the bowl |

## 3. 生成方法

以任务 i 的原始 bddl 为模板，仅替换三段（其余 `:regions` / `:fixtures` / `:objects` / `:init` 原样保留）：

| 段 | 合并规则 |
|---|---|
| `:goal` | `(And atom_i atom_j)`，两个原子来自 10 个单任务的目标 |
| `:obj_of_interest` | 两任务对象集合去重并集（保持 i 的顺序，再追加 j 中新增项）|
| `:language` | `f"{lang_i} and {lang_j}"`（benchmark 官方 language，小写、单行）|
| `:init` | 二进制拷贝任务 i 的 `*.pruned_init`（50×79）|

段替换使用**括号配对定位**：先用 `\(` + 段名（带 `(?=[\s)])` 边界）在文本中找到该 section 起始左括号，再做深度计数找到配对右括号后整段替换；替换后强制 `BDDLUtils.robosuite_parse_problem` 复核，避免 Lead 冒烟时发现的 `((:language` / 吞掉下一个 section 的损坏。

init 文件写两份：`init/goal_pair_<ii>_<jj>.pruned_init`（规范副本）与 `bddl/goal_pair_<ii>_<jj>.pruned_init`（同目录 sibling）。后者是 Lead 的 `prep/run_combined_baseline.py` / overlay runner 的约定：runner 会读取 `os.path.splitext(bddl_path)[0] + ".pruned_init"`，因此 `--custom-bddl-dir .../bddl` 可直接运行，无需额外配置。

## 4. 任务表（benchmark idx）

| idx | 任务名 | benchmark language | goal atom | obj_of_interest | init 文件 |
|---|---|---|---|---|---|
| 0 | `open_the_middle_drawer_of_the_cabinet` | open the middle drawer of the cabinet | `(Open wooden_cabinet_1_middle_region)` | `wooden_cabinet_1_middle_region` | `open_the_middle_drawer_of_the_cabinet.pruned_init` |
| 1 | `put_the_bowl_on_the_stove` | put the bowl on the stove | `(On akita_black_bowl_1 flat_stove_1_cook_region)` | `akita_black_bowl_1, flat_stove_1_cook_region` | `put_the_bowl_on_the_stove.pruned_init` |
| 2 | `put_the_wine_bottle_on_top_of_the_cabinet` | put the wine bottle on top of the cabinet | `(On wine_bottle_1 wooden_cabinet_1_top_side)` | `wine_bottle_1, wooden_cabinet_1_top_side` | `put_the_wine_bottle_on_top_of_the_cabinet.pruned_init` |
| 3 | `open_the_top_drawer_and_put_the_bowl_inside` | open the top drawer and put the bowl inside | `(In akita_black_bowl_1 wooden_cabinet_1_top_region)` | `akita_black_bowl_1, wooden_cabinet_1_top_region` | `open_the_top_drawer_and_put_the_bowl_inside.pruned_init` |
| 4 | `put_the_bowl_on_top_of_the_cabinet` | put the bowl on top of the cabinet | `(On akita_black_bowl_1 wooden_cabinet_1_top_side)` | `akita_black_bowl_1, wooden_cabinet_1_top_side` | `put_the_bowl_on_top_of_the_cabinet.pruned_init` |
| 5 | `push_the_plate_to_the_front_of_the_stove` | push the plate to the front of the stove | `(On plate_1 main_table_stove_front_region)` | `plate_1, main_table_stove_front_region` | `push_the_plate_to_the_front_of_the_stove.pruned_init` |
| 6 | `put_the_cream_cheese_in_the_bowl` | put the cream cheese in the bowl | `(On cream_cheese_1 akita_black_bowl_1)` | `cream_cheese_1, akita_black_bowl_1` | `put_the_cream_cheese_in_the_bowl.pruned_init` |
| 7 | `turn_on_the_stove` | turn on the stove | `(Turnon flat_stove_1)` | `flat_stove_1` | `turn_on_the_stove.pruned_init` |
| 8 | `put_the_bowl_on_the_plate` | put the bowl on the plate | `(On akita_black_bowl_1 plate_1)` | `akita_black_bowl_1, plate_1` | `put_the_bowl_on_the_plate.pruned_init` |
| 9 | `put_the_wine_bottle_on_the_rack` | put the wine bottle on the rack | `(On wine_bottle_1 wine_rack_1_top_region)` | `wine_bottle_1, wine_rack_1_top_region` | `put_the_wine_bottle_on_the_rack.pruned_init` |

## 5. 冲突分类

### 5.1 分类规则

- **conflict**：同一被操作物体被要求处于两个不同目标位置 (单刚体不可能同时满足): akita_black_bowl_1 的目标集合 = benchmark idx [1, 3, 4, 8] 两两冲突; wine_bottle_1 = benchmark idx [2, 9] 冲突。
- **hard**：cream_cheese_1 On akita_black_bowl_1 (idx 6) 与碗位置目标 [1, 3, 4, 8] 组合: 需先把碗放到最终位置再把奶酪放上去 (或搬运带奶酪的碗, 奶酪在碗面上易滑落), 次序受限、接触脆弱, 可共存但预期成功率偏低。
- **hard**：plate_1 推到 main_table_stove_front_region (idx 5) 与碗放到 flat_stove_1_cook_region (idx 1) 组合: 两目标区域空间相邻, 推盘路径与炉体/炉上碗存在碰撞、遮挡风险, 需要精细次序与间隙。
- **compatible**：两个目标分别作用于不同被操作物体与不同目标位置 (不存在同一物体的异位要求), 目标原子可同时成立; 个别组合存在有利次序, 在 reason 中给出次序提示。

> 规则调整说明：最初按“bddl 文件名字母序”给出的示例规则（bowl 集合 {1,3,4,5}、plate {2} 与 bowl {4} 的 hard 组合）已按 Lead 修正后的 benchmark 顺序重新映射为：bowl 目标集合 = **{1,3,4,8}**、wine_bottle 集合 = **{2,9}**、cream_cheese(6) 与 {1,3,4,8} 为 hard、plate(5) 与 bowl-on-stove(1) 为 hard。逐对原因中的任务编号均为 benchmark idx。

### 5.2 统计

| 分类 | 对数 | pair_id |
|---|---|---|
| conflict | 7 | `01_03`, `01_04`, `01_08`, `02_09`, `03_04`, `03_08`, `04_08` |
| hard | 5 | `01_05`, `01_06`, `03_06`, `04_06`, `06_08` |
| compatible | 33 | `00_01`, `00_02`, `00_03`, `00_04`, `00_05`, `00_06`, `00_07`, `00_08`, `00_09`, `01_02`, `01_07`, `01_09`, `02_03`, `02_04`, `02_05`, `02_06`, `02_07`, `02_08`, `03_05`, `03_07`, `03_09`, `04_05`, `04_07`, `04_09`, `05_06`, `05_07`, `05_08`, `05_09`, `06_07`, `06_09`, `07_08`, `07_09`, `08_09` |

### 5.3 conflict 对逐对原因（逻辑上不可同时完成）

- **`goal_pair_01_03`**（put_the_bowl_on_the_stove + open_the_top_drawer_and_put_the_bowl_inside）：t1(put_the_bowl_on_the_stove) 与 t3(open_the_top_drawer_and_put_the_bowl_inside) 都要求 akita_black_bowl_1 处于不同目标位置: (On akita_black_bowl_1 flat_stove_1_cook_region) vs (In akita_black_bowl_1 wooden_cabinet_1_top_region)。同一刚体不可能同时满足两个互斥的位置谓词, 合并目标在逻辑上不可能同时成立, 归为 conflict。
- **`goal_pair_01_04`**（put_the_bowl_on_the_stove + put_the_bowl_on_top_of_the_cabinet）：t1(put_the_bowl_on_the_stove) 与 t4(put_the_bowl_on_top_of_the_cabinet) 都要求 akita_black_bowl_1 处于不同目标位置: (On akita_black_bowl_1 flat_stove_1_cook_region) vs (On akita_black_bowl_1 wooden_cabinet_1_top_side)。同一刚体不可能同时满足两个互斥的位置谓词, 合并目标在逻辑上不可能同时成立, 归为 conflict。
- **`goal_pair_01_08`**（put_the_bowl_on_the_stove + put_the_bowl_on_the_plate）：t1(put_the_bowl_on_the_stove) 与 t8(put_the_bowl_on_the_plate) 都要求 akita_black_bowl_1 处于不同目标位置: (On akita_black_bowl_1 flat_stove_1_cook_region) vs (On akita_black_bowl_1 plate_1)。同一刚体不可能同时满足两个互斥的位置谓词, 合并目标在逻辑上不可能同时成立, 归为 conflict。
- **`goal_pair_02_09`**（put_the_wine_bottle_on_top_of_the_cabinet + put_the_wine_bottle_on_the_rack）：t2(put_the_wine_bottle_on_top_of_the_cabinet) 与 t9(put_the_wine_bottle_on_the_rack) 都要求 wine_bottle_1 处于不同目标位置: (On wine_bottle_1 wooden_cabinet_1_top_side) vs (On wine_bottle_1 wine_rack_1_top_region)。单一酒瓶不能同时在柜顶与酒架顶, 合并目标逻辑冲突。
- **`goal_pair_03_04`**（open_the_top_drawer_and_put_the_bowl_inside + put_the_bowl_on_top_of_the_cabinet）：t3(open_the_top_drawer_and_put_the_bowl_inside) 与 t4(put_the_bowl_on_top_of_the_cabinet) 都要求 akita_black_bowl_1 处于不同目标位置: (In akita_black_bowl_1 wooden_cabinet_1_top_region) vs (On akita_black_bowl_1 wooden_cabinet_1_top_side)。同一刚体不可能同时满足两个互斥的位置谓词, 合并目标在逻辑上不可能同时成立, 归为 conflict。
- **`goal_pair_03_08`**（open_the_top_drawer_and_put_the_bowl_inside + put_the_bowl_on_the_plate）：t3(open_the_top_drawer_and_put_the_bowl_inside) 与 t8(put_the_bowl_on_the_plate) 都要求 akita_black_bowl_1 处于不同目标位置: (In akita_black_bowl_1 wooden_cabinet_1_top_region) vs (On akita_black_bowl_1 plate_1)。同一刚体不可能同时满足两个互斥的位置谓词, 合并目标在逻辑上不可能同时成立, 归为 conflict。
- **`goal_pair_04_08`**（put_the_bowl_on_top_of_the_cabinet + put_the_bowl_on_the_plate）：t4(put_the_bowl_on_top_of_the_cabinet) 与 t8(put_the_bowl_on_the_plate) 都要求 akita_black_bowl_1 处于不同目标位置: (On akita_black_bowl_1 wooden_cabinet_1_top_side) vs (On akita_black_bowl_1 plate_1)。同一刚体不可能同时满足两个互斥的位置谓词, 合并目标在逻辑上不可能同时成立, 归为 conflict。

### 5.4 hard 对逐对原因（可共存但次序/空间受限）

- **`goal_pair_01_05`**（put_the_bowl_on_the_stove + push_the_plate_to_the_front_of_the_stove）：t5 要求把 plate_1 推到 main_table_stove_front_region, t1 要求把 akita_black_bowl_1 放到 flat_stove_1_cook_region; 两目标区域空间相邻, 推盘路径与炉体/炉上碗存在碰撞与遮挡风险, 需要精细的次序与间隙, 归为 hard。
- **`goal_pair_01_06`**（put_the_bowl_on_the_stove + put_the_cream_cheese_in_the_bowl）：t6 要求 cream_cheese_1 最终置于 akita_black_bowl_1 上, 而 t1(put_the_bowl_on_the_stove) 又要求把碗移动到 (On akita_black_bowl_1 flat_stove_1_cook_region); 两者可共存, 但必须先完成碗的最终摆放再把奶酪放上去 (或搬运带奶酪的碗, 奶酪在碗面上易滑落), 次序受限、接触脆弱, 归为 hard。
- **`goal_pair_03_06`**（open_the_top_drawer_and_put_the_bowl_inside + put_the_cream_cheese_in_the_bowl）：t6 要求 cream_cheese_1 最终置于 akita_black_bowl_1 上, 而 t3(open_the_top_drawer_and_put_the_bowl_inside) 又要求把碗移动到 (In akita_black_bowl_1 wooden_cabinet_1_top_region); 两者可共存, 但必须先完成碗的最终摆放再把奶酪放上去 (或搬运带奶酪的碗, 奶酪在碗面上易滑落), 次序受限、接触脆弱, 归为 hard。
- **`goal_pair_04_06`**（put_the_bowl_on_top_of_the_cabinet + put_the_cream_cheese_in_the_bowl）：t6 要求 cream_cheese_1 最终置于 akita_black_bowl_1 上, 而 t4(put_the_bowl_on_top_of_the_cabinet) 又要求把碗移动到 (On akita_black_bowl_1 wooden_cabinet_1_top_side); 两者可共存, 但必须先完成碗的最终摆放再把奶酪放上去 (或搬运带奶酪的碗, 奶酪在碗面上易滑落), 次序受限、接触脆弱, 归为 hard。
- **`goal_pair_06_08`**（put_the_cream_cheese_in_the_bowl + put_the_bowl_on_the_plate）：t6 要求 cream_cheese_1 最终置于 akita_black_bowl_1 上, 而 t8(put_the_bowl_on_the_plate) 又要求把碗移动到 (On akita_black_bowl_1 plate_1); 两者可共存, 但必须先完成碗的最终摆放再把奶酪放上去 (或搬运带奶酪的碗, 奶酪在碗面上易滑落), 次序受限、接触脆弱, 归为 hard。

### 5.5 已识别但保留 compatible 的次序耦合（在 reason 中给出次序提示）

- **`goal_pair_00_01`**：用户示例组合: 先开中抽屉再放碗到炉灶区 (或反之), 互不冲突。
- **`goal_pair_00_02`**：放酒瓶到柜顶与打开中抽屉可共容; 同一柜体, 建议先放瓶再开抽屉避免碰撞。
- **`goal_pair_00_03`**：两个目标都涉及木质柜抽屉; 建议先开上抽屉放碗、再开中抽屉, 避免中抽屉伸出遮挡上抽屉取放路径。
- **`goal_pair_00_04`**：先开中抽屉或先放碗到柜顶均可, 互不冲突。
- **`goal_pair_01_07`**：先放碗到炉灶区再开炉 (或先开炉) 均可; 仿真中炉子开启不改变碗的放置判定。
- **`goal_pair_02_04`**：酒瓶与碗都放到 wooden_cabinet_1 的 top_side, 被操作物体不同; 柜顶面足够容纳两者, 注意摆放间距。
- **`goal_pair_03_05`**：碗入上抽屉与推盘到炉前区分属不同区域, 互不冲突。
- **`goal_pair_05_08`**：先推盘到炉前区再把碗放到盘上更稳 (反之亦可, 但推带碗的盘子更脆弱)。

## 6. 组合指令清单（45 条）

- `goal_pair_00_01` [compatible]: open the middle drawer of the cabinet and put the bowl on the stove
- `goal_pair_00_02` [compatible]: open the middle drawer of the cabinet and put the wine bottle on top of the cabinet
- `goal_pair_00_03` [compatible]: open the middle drawer of the cabinet and open the top drawer and put the bowl inside
- `goal_pair_00_04` [compatible]: open the middle drawer of the cabinet and put the bowl on top of the cabinet
- `goal_pair_00_05` [compatible]: open the middle drawer of the cabinet and push the plate to the front of the stove
- `goal_pair_00_06` [compatible]: open the middle drawer of the cabinet and put the cream cheese in the bowl
- `goal_pair_00_07` [compatible]: open the middle drawer of the cabinet and turn on the stove
- `goal_pair_00_08` [compatible]: open the middle drawer of the cabinet and put the bowl on the plate
- `goal_pair_00_09` [compatible]: open the middle drawer of the cabinet and put the wine bottle on the rack
- `goal_pair_01_02` [compatible]: put the bowl on the stove and put the wine bottle on top of the cabinet
- `goal_pair_01_03` [conflict]: put the bowl on the stove and open the top drawer and put the bowl inside
- `goal_pair_01_04` [conflict]: put the bowl on the stove and put the bowl on top of the cabinet
- `goal_pair_01_05` [hard]: put the bowl on the stove and push the plate to the front of the stove
- `goal_pair_01_06` [hard]: put the bowl on the stove and put the cream cheese in the bowl
- `goal_pair_01_07` [compatible]: put the bowl on the stove and turn on the stove
- `goal_pair_01_08` [conflict]: put the bowl on the stove and put the bowl on the plate
- `goal_pair_01_09` [compatible]: put the bowl on the stove and put the wine bottle on the rack
- `goal_pair_02_03` [compatible]: put the wine bottle on top of the cabinet and open the top drawer and put the bowl inside
- `goal_pair_02_04` [compatible]: put the wine bottle on top of the cabinet and put the bowl on top of the cabinet
- `goal_pair_02_05` [compatible]: put the wine bottle on top of the cabinet and push the plate to the front of the stove
- `goal_pair_02_06` [compatible]: put the wine bottle on top of the cabinet and put the cream cheese in the bowl
- `goal_pair_02_07` [compatible]: put the wine bottle on top of the cabinet and turn on the stove
- `goal_pair_02_08` [compatible]: put the wine bottle on top of the cabinet and put the bowl on the plate
- `goal_pair_02_09` [conflict]: put the wine bottle on top of the cabinet and put the wine bottle on the rack
- `goal_pair_03_04` [conflict]: open the top drawer and put the bowl inside and put the bowl on top of the cabinet
- `goal_pair_03_05` [compatible]: open the top drawer and put the bowl inside and push the plate to the front of the stove
- `goal_pair_03_06` [hard]: open the top drawer and put the bowl inside and put the cream cheese in the bowl
- `goal_pair_03_07` [compatible]: open the top drawer and put the bowl inside and turn on the stove
- `goal_pair_03_08` [conflict]: open the top drawer and put the bowl inside and put the bowl on the plate
- `goal_pair_03_09` [compatible]: open the top drawer and put the bowl inside and put the wine bottle on the rack
- `goal_pair_04_05` [compatible]: put the bowl on top of the cabinet and push the plate to the front of the stove
- `goal_pair_04_06` [hard]: put the bowl on top of the cabinet and put the cream cheese in the bowl
- `goal_pair_04_07` [compatible]: put the bowl on top of the cabinet and turn on the stove
- `goal_pair_04_08` [conflict]: put the bowl on top of the cabinet and put the bowl on the plate
- `goal_pair_04_09` [compatible]: put the bowl on top of the cabinet and put the wine bottle on the rack
- `goal_pair_05_06` [compatible]: push the plate to the front of the stove and put the cream cheese in the bowl
- `goal_pair_05_07` [compatible]: push the plate to the front of the stove and turn on the stove
- `goal_pair_05_08` [compatible]: push the plate to the front of the stove and put the bowl on the plate
- `goal_pair_05_09` [compatible]: push the plate to the front of the stove and put the wine bottle on the rack
- `goal_pair_06_07` [compatible]: put the cream cheese in the bowl and turn on the stove
- `goal_pair_06_08` [hard]: put the cream cheese in the bowl and put the bowl on the plate
- `goal_pair_06_09` [compatible]: put the cream cheese in the bowl and put the wine bottle on the rack
- `goal_pair_07_08` [compatible]: turn on the stove and put the bowl on the plate
- `goal_pair_07_09` [compatible]: turn on the stove and put the wine bottle on the rack
- `goal_pair_08_09` [compatible]: put the bowl on the plate and put the wine bottle on the rack

## 7. 静态验证结果

每个合并 bddl 执行两类验证（均为 CPU-only、串行）：

1. **解析验证**：`BDDLUtils.robosuite_parse_problem` + `BDDLUtils.get_problem_info`；
2. **env 实例化冒烟**：`OffScreenRenderEnv(bddl_file_name=..., camera_heights=256, camera_widths=256)` → `seed(1000)` → `reset()` → `set_init_state(init[0])` → `get_named_joint_state()` → `check_success()` → `close()`。

### 7.1 断言逐项统计

| 检查项 | 通过/总数 |
|---|---|
| `bddl_exists` | 45/45 |
| `init_exists` | 45/45 |
| `runner_sibling_init_exists` | 45/45 |
| `patched_sections_unique` | 45/45 |
| `no_double_open_paren` | 45/45 |
| `no_nested_section_artifact` | 45/45 |
| `parse_ok` | 45/45 |
| `goal_atom_count_is_2` | 45/45 |
| `goal_atoms_match_expected` | 45/45 |
| `language_matches_combined` | 45/45 |
| `obj_of_interest_matches_union` | 45/45 |
| `regions_match_template` | 45/45 |
| `fixtures_match_template` | 45/45 |
| `objects_match_template` | 45/45 |
| `init_state_match_template` | 45/45 |
| `raw_static_sections_intact` | 45/45 |
| `init_sha256_matches_source` | 45/45 |
| `init_sibling_sha256_matches` | 45/45 |
| `init_array_shape_ok` | 45/45 |

### 7.2 结果与耗时

- 解析验证：45/45 通过（失败项：无）
- env 冒烟：45/45 通过；初始 `check_success()` 全部为 False：是
- 冒烟重试：总尝试 45 次；需要重试的对：无
- 解析耗时：总计 0.025 s，min/median/max = 0.0/0.001/0.001 s
- 冒烟耗时（含 env 构造+reset+set_init_state）：总计 201.54 s，min/median/max = 4.261/4.435/5.756 s
- **失败/异常项：无**（45 对全部通过；无 env 实例化失败，无需根因分析）

> 局限：静态验证只证明“场景可被 BDDL 解析、env 可构造、初始状态未满足目标”，**不证明目标可解/可达/可学习**；动态可解性与成功率需由 Lead 用 pi05 baseline 实测（见 §9）。

## 8. 推荐 pilot 子集

分阶段建议（先小后大，控制 GPU 成本）：

### 8.1 首条 smoke（用户示例，1 对）

- `goal_pair_00_01`：open the middle drawer of the cabinet and put the bowl on the stove

### 8.2 compatible 全量（33 对，主 baseline 臂）

- `goal_pair_00_01`：open the middle drawer of the cabinet and put the bowl on the stove
- `goal_pair_00_02`：open the middle drawer of the cabinet and put the wine bottle on top of the cabinet
- `goal_pair_00_03`：open the middle drawer of the cabinet and open the top drawer and put the bowl inside
- `goal_pair_00_04`：open the middle drawer of the cabinet and put the bowl on top of the cabinet
- `goal_pair_00_05`：open the middle drawer of the cabinet and push the plate to the front of the stove
- `goal_pair_00_06`：open the middle drawer of the cabinet and put the cream cheese in the bowl
- `goal_pair_00_07`：open the middle drawer of the cabinet and turn on the stove
- `goal_pair_00_08`：open the middle drawer of the cabinet and put the bowl on the plate
- `goal_pair_00_09`：open the middle drawer of the cabinet and put the wine bottle on the rack
- `goal_pair_01_02`：put the bowl on the stove and put the wine bottle on top of the cabinet
- `goal_pair_01_07`：put the bowl on the stove and turn on the stove
- `goal_pair_01_09`：put the bowl on the stove and put the wine bottle on the rack
- `goal_pair_02_03`：put the wine bottle on top of the cabinet and open the top drawer and put the bowl inside
- `goal_pair_02_04`：put the wine bottle on top of the cabinet and put the bowl on top of the cabinet
- `goal_pair_02_05`：put the wine bottle on top of the cabinet and push the plate to the front of the stove
- `goal_pair_02_06`：put the wine bottle on top of the cabinet and put the cream cheese in the bowl
- `goal_pair_02_07`：put the wine bottle on top of the cabinet and turn on the stove
- `goal_pair_02_08`：put the wine bottle on top of the cabinet and put the bowl on the plate
- `goal_pair_03_05`：open the top drawer and put the bowl inside and push the plate to the front of the stove
- `goal_pair_03_07`：open the top drawer and put the bowl inside and turn on the stove
- `goal_pair_03_09`：open the top drawer and put the bowl inside and put the wine bottle on the rack
- `goal_pair_04_05`：put the bowl on top of the cabinet and push the plate to the front of the stove
- `goal_pair_04_07`：put the bowl on top of the cabinet and turn on the stove
- `goal_pair_04_09`：put the bowl on top of the cabinet and put the wine bottle on the rack
- `goal_pair_05_06`：push the plate to the front of the stove and put the cream cheese in the bowl
- `goal_pair_05_07`：push the plate to the front of the stove and turn on the stove
- `goal_pair_05_08`：push the plate to the front of the stove and put the bowl on the plate
- `goal_pair_05_09`：push the plate to the front of the stove and put the wine bottle on the rack
- `goal_pair_06_07`：put the cream cheese in the bowl and turn on the stove
- `goal_pair_06_09`：put the cream cheese in the bowl and put the wine bottle on the rack
- `goal_pair_07_08`：turn on the stove and put the bowl on the plate
- `goal_pair_07_09`：turn on the stove and put the wine bottle on the rack
- `goal_pair_08_09`：put the bowl on the plate and put the wine bottle on the rack

### 8.3 hard 对照（2 对，验证次序/空间耦合是否真的降低成功率）

- `goal_pair_01_05` [hard]：put the bowl on the stove and push the plate to the front of the stove
- `goal_pair_01_06` [hard]：put the bowl on the stove and put the cream cheese in the bowl

### 8.4 不进入动态 baseline 的 conflict 对（7 对）

这些组合的目标在逻辑上不可同时成立，理论上成功率应为 0；可作为“BDDL 目标检查是否被正确执行”的 negative control（可选，需谨慎解读）：

- `01_03`、`01_04`、`01_08`、`02_09`、`03_04`、`03_08`、`04_08`

### 8.5 运行方式建议

Lead 可直接复用 `prep/run_combined_baseline.py`：

```bash
$PY prep/run_combined_baseline.py \
    --runtime-root runs/combined-tasks-20261019/runtime \
    --bddl-dir runs/combined-tasks-20261019/artifacts/goal-pairs/bddl \
    --bddl-pattern '*.bddl' \
    --seed-ids 0 --max-steps 600 --replan-steps 10 --video
```

`bddl/` 目录内已放置同名 sibling `.pruned_init`，overlay runner 会自动把它们作为固定初始状态加载。

## 9. 风险与下一步

1. **静态验证 ≠ 动态可解性**：本报告只做 BDDL 解析 + env 实例化冒烟；下一步必须由 Lead 跑 pi05 baseline（先 `goal_pair_00_01`，再 compatible 全量，再 hard 对照）。
2. **conflict 对不可完成**（7 对）：若进入动态跑分，预期成功率≈0；不要把它们混入兼容臂统计。
3. **hard 对成功率预期偏低**（5 对）：cream cheese 与移动碗的接触/滑落、推盘与炉台的空间紧邻与碰撞，建议单独统计并与 compatible 臂做对照。
4. **可达性风险**：单臂 Panda 下，打开中抽屉后可能遮挡上抽屉取放（(0,3) 组合）；柜顶放置（top_side）与炉前区推盘的到达高度/间隙需在动态实验中确认。
5. **初始化随机性**：每个合并场景沿用任务 i 的 50 条 init 状态；Lead runner 按 seed 选择其中一条，不同 seed 的摆放差异可能影响成功率，建议多 seed 统计。
6. **runner 副作用**：overlay runner 运行自定义 bddl 时会在同目录生成 `*.M008_backup`（其自身逻辑），不影响 `--custom-bddl-pattern '*.bddl'` 的匹配；重跑本脚本的清理逻辑只处理 `goal_pair_*`。
7. **语言一致性**：合并 bddl 的 `:language` 统一使用 benchmark 官方 instruction（如 `open the middle drawer of the cabinet and put the bowl on the stove`），与原始 bddl 内部 `:language` 的部分偏差已在本产物中纠正。

## 10. 产物清单

| 路径 | 说明 | 数量 |
|---|---|---|
| `bddl/goal_pair_*.bddl` | 45 个合并 BDDL | 45 |
| `bddl/goal_pair_*.pruned_init` | 45 个 sibling init（runner 直接加载）| 45 |
| `init/goal_pair_*.pruned_init` | 45 个规范 init 副本 | 45 |
| `pairs.json` | 45 对机读清单（任务表/规则/语言/goal atoms/分类/原因/pilot/哈希）| 1 |
| `pairs.md` | 45 对可读清单（总表 + 逐对明细）| 1 |
| `static-validation.json` | 45 对静态验证明细与汇总 | 1 |
| `checksums.sha256` | bddl/init/pairs 产物哈希（可重入性核对）| 1 |
| `scripts/build_goal_pairs.py` | 可重入生成+验证脚本 | 1 |
| `REPORT.md` | 本报告 | 1 |

## 11. 可重入性

脚本可重复执行：每次先清理 `bddl/`、`init/` 下旧的 `goal_pair_*` 文件再按确定性规则重写；`bddl/`、`init/`、`pairs.json`、`pairs.md`、`checksums.sha256` 内容确定（不含时间戳），重复运行 SHA256 一致。`static-validation.json` 与本文中的耗时统计随机器负载有微小波动，属预期差异。

本次交付实测核对（连续两次全量运行，每次 45 对生成 + 45 次 env 冒烟）：

- `diff -q`：`checksums.sha256`、`pairs.json`、`pairs.md` 两次运行字节级一致；
- `sha256sum -c checksums.sha256`：137/137 条目校验通过；
- `static-validation.json`：剔除所有 `*_s` 耗时字段后两次完全一致；
- `REPORT.md`：归一化耗时数字后两次完全一致；
- 文件清点：`bddl/` 90 个（45 个 bddl + 45 个 sibling init）、`init/` 45 个，无陈旧/多余文件（重跑清理逻辑只处理 `goal_pair_*`，不影响其他产物）。
