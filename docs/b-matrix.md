# B 矩阵说明（b_matrix）：以 LIBERO-10 为重点

> **2026-11-21 base-only**：本文件就是新 B 主表（`b-matrix.csv`，442）；B-plus 退出主叙事。C/D 拆分与套件矩阵见 [`rollback-narrative.md`](rollback-narrative.md)。

> **术语**：本文件及 `dataset/matrices/b-matrix.csv` 简称 **base-rollback**；LIBERO-Plus O2 版本见 [B-matrix-plus.md](B-matrix-plus.md)，简称 **plus-rollback**。

> 版本：`2.0.0.dev0` ｜ 数据冻结日：2026-11-18 ｜ 机器可读源：[`dataset/matrices/b-matrix.csv`](../dataset/matrices/b-matrix.csv)
> 数据契约：[`docs/SPEC.md`](SPEC.md) §3.3；语义：[`README.md`](../README.md) §3.4–3.5、§5.2；加载与校验：[`src/libero_rollback/matrices.py`](../src/libero_rollback/matrices.py)
> 本文是 B 矩阵的阅读与使用说明，**不改变数据契约**；与 SPEC 冲突时以 SPEC 为准。文中计数按 CSV 逐行复核。

---

## 0. 速览

| 项 | 值 |
|---|---|
| 文件 | `dataset/matrices/b-matrix.csv`，UTF-8、LF、17 列 |
| 全量 | **442** cases / **40** tasks / 4 suites |
| LIBERO-10（`l10`） | **197** cases / **10** tasks，占全 B 的 **44.6%** |
| l10 分层 | `C0` 10 / `L0` 28 / `L1` 84 / `L2` 75（treatment 187） |
| l10 撤销目标 | `s1` 60 / `s2` 57 / `both` 63 / `g` 7 / `c0` 10 |
| 触发 | `all_done` + `delay_steps=10` |
| 预算 | 触发前最多 600 步；注入后追加 600 步修复窗口 |
| 当前证据状态 | 矩阵已冻结并通过静态校验；**v2 已跑完 442/442**（Goal 85 + Object 80 + Spatial 80 + L10 197）；L10 Recovery 42/181 = 23.2%，C0 9/10 |

五个要点：

- B 是**完成边界**（completion boundary）的撤销测试：任务已经成功后，才撤销一个或两个刚刚为真的关系；l10 是 B 中唯一系统覆盖多目标任务、也是与 D-native 对接的 suite。
- l10 的 10 个任务正好覆盖 LIBERO-10 的全部 10 个原生 BDDL 任务；D-native 只用其中 9 个（`t276` 是单目标，没有第二个子目标）。
- l10 的 197 条不是“10 个任务 × 固定模板”，而是 **10 条 C0 + 28 个扰动单元**的展开：L0 28、L1 84、L2 75。
- `s1`/`s2`/`both` 是**撤销哪个关系**，不是难度等级；`s1`/`s2` 按来源矩阵定义的子目标顺序（通常即执行顺序），不等于 BDDL `:goal` 的文本顺序。
- `n_targets` 不是 BDDL 原子数，也不是撤销关系数；l10 的 `n_targets` 为 3（9 个任务）或 1（`t276`），不能拿它当 `n` 做分层。

---

## 1. B 矩阵在整套实验中的位置

### 1.1 四个 suite 的分工

| 角色 | suite | 含义 | 任务数 | cases |
|---|---|---|---:|---:|
| **Rollback 维度 1** | **B** `completion-boundary-rollback` | **任务完成以后，完成状态（或某个子任务的完成状态）被外部撤销**——能否识别并恢复？ | **40** | **442** |
| 对照（能力上界） | A `single-intact` | 原始 LIBERO 单任务，不扰动 | 40 | 40 |
| 对照/剂量（Phase 2） | C `composition-intact` | 同场景配对生成的组合结构，不扰动 | — | 0（未构建） |
| **Rollback 维度 2** | D `in-execution-rollback` | 执行长程任务时，前序已完成子任务被撤销、后序仍 pending | 9（+120 结构） | 189 + 360（compose 为占位） |

**B 是本仓两个 Rollback 维度中的维度 1（完成后撤销）**；维度 2 是 D。A/C 是无撤销对照，不是 Rollback 维度（完整定义见 [docs/rollback-dimensions.md](rollback-dimensions.md)）。

B 与 A 使用**同一组 40 个任务键**，因此 A↔B 是一一配对；B 与 D-native 的公共底盘是 LIBERO-10 的 9 个多目标任务。

B 全量按 suite 的分布：

| suite | tasks | cases | C0 |
|---|---:|---:|---:|
| goal | 10 | 85 | 10 |
| object | 10 | 80 | 10 |
| spatial | 10 | 80 | 10 |
| **l10** | **10** | **197** | **10** |
| 合计 | 40 | 442 | 40 |

l10 只占 25% 的任务，却占 44.6% 的 case——因为多目标任务每个任务有 3 个可撤销目标单元，而 goal/object/spatial 大多只有 1 个。

### 1.2 B 的四个 level

| level | 做什么 | 撤销后关系 | 角色 |
|---|---|---|---|
| `C0` | **no-op 对照**：同样延迟、同样 post-success 窗口，不动状态 | 必须仍为真 | 排除“延迟/强制继续本身有害” |
| `L0` | 把被撤销物体/关节恢复到 **episode 初始位姿** | 必须为假 | 回到策略 t=0 见过的构型 |
| `L1` | `L0` + 沿“目标区域中心 → 初始位姿”水平射线外推 δ ∈ {3, 6, 10} cm | 必须为假 | 扰动形态 1 |
| `L2` | `L0` + 绕世界 z 轴 yaw θ ∈ {30°, 60°, 90°} | 必须为假 | 扰动形态 2 |

三条纪律：

1. **`L1`/`L2` 不是难度等级**，是两种扰动形态；不要写成“难度递增”。
2. **`C0` 不可省**：没有它，无法把“撤销的代价”与“延迟/继续跑本身的代价”分开。
3. 每条 case 必须记录实测几何量（`Δtranslation_m`、`Δangle_rad`、`axis`）；nominal δ/θ 不是保证值。

### 1.3 为什么 l10 是重点

- **只有 l10 有系统性的多目标撤销**：全 B 的 `s1`（60 条）和 `s2`（57 条）**全部来自 l10**；`both` 除 `goal-t030` 的 7 条外也全部在 l10（见 §3.3）。
- **l10 是 B 与 D 的桥**：B(l10) 在 `all_done` 撤销；D-native 在 `early`/`mid`/`later` 撤销。B(l10, `target=s1`) 的 60 条与 D-native 任一窗口的 60 条逐格对齐（见 §6）。
- **l10 覆盖长程任务**：厨房（开炉灶 + 放壶、放碗关抽屉、放杯关微波炉、两个壶）、客厅（双物体入篮、双杯上盘、杯 + 布丁）、书房（书入盒）。这些任务的完成态更依赖多个物体/关节同时保持。

---

## 2. 数据契约：17 列怎么读

### 2.1 列定义

| 列 | 类型 | 含义 | l10 示例 |
|---|---|---|---|
| `case_id` | str | 全库唯一、发布后不可变 | `b-l10-t000-s1-l1-d03` |
| `suite` | enum | `goal` / `object` / `spatial` / `l10` | `l10` |
| `task_idx` | int | 来源仓的 LIBERO 全局 task 下标，**不是 0–9 重编号** | `0` |
| `bddl_name` | str | BDDL stem | `KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it` |
| `instruction` | str | BDDL `:language` 逐字内容 | `turn on the stove and put the moka pot on it` |
| `target` | enum | `c0` / `g` / `s1` / `s2` / `both` / `pre` | `s1` |
| `revoked_objects` | str | 被撤销物体；多目标用逗号或竖线分隔 | `flat_stove_1` |
| `revoked_predicates` | str | 被撤销谓词；多个用竖线分隔，必须带括号 | `(Turnon flat_stove_1)` |
| `family` | enum | `pose` / `joint` / `mixed` / `-`（C0） | `joint` |
| `level` | enum | `C0` / `L0` / `L1` / `L2` | `L1` |
| `param` | str | 空 / `d03` / `d06` / `d10` / `r30` / `r60` / `r90` | `d03` |
| `semantics` | str | `relation_holds_control`（C0）或 `relation_then_resume` | `relation_then_resume` |
| `trigger` | str | B 固定为 `all_done` | `all_done` |
| `delay_steps` | int | B 固定为 `10` | `10` |
| `repair_window` | int | 注入后追加的修复步数（frozen 参考；suite/runner 下限 600） | `300` / suite 600 |
| `expected_relation_after` | bool | C0 为 `true`；非 C0 为 `false` | `false` |
| `n_targets` | int | 来源矩阵运行时跟踪的 goal atom 数；**不是 BDDL 原子数** | `3` |

### 2.2 case_id 语法

```text
b-<suite>-t<idx:03d>-c0                          # C0 no-op
b-<suite>-t<idx:03d>-<target>-<level>[-<param>]  # 非 C0
```

```text
b-l10-t000-c0
b-l10-t000-s1-l1-d03
b-l10-t033-both-l2-r60
```

- `<target> ∈ {g, s1, s2, both, pre, c0}`
- `<level> ∈ {C0, L0, L1, L2}`
- `<param> ∈ {d03, d06, d10, r30, r60, r90}`
- C0 不带 level/param；`L0` 不带 param；`L1` 必带 `d03/d06/d10`；`L2` 必带 `r30/r60/r90`。

### 2.3 一行原始数据

```csv
b-l10-t000-s1-l1-d03,l10,0,KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it,turn on the stove and put the moka pot on it,s1,flat_stove_1,(Turnon flat_stove_1),joint,L1,d03,relation_then_resume,all_done,10,300,false,3
```

读法：LIBERO-10、task 0、撤销 `s1`（炉灶的 `Turnon`）、`L1` 外推 3 cm、关节任务、`all_done` 后 10 步注入；CSV 里旧参考值是 300，runner 实际注入后追加 600 步修复窗口，期望关系变假。

### 2.4 来源与冻结

- 整表从 `libero-compose` 导入并冻结，来源仓路径、源文件 sha256、冻结 sha256、导入日期记录在 [`dataset/sources.yaml`](../dataset/sources.yaml)。
- 导入只做 CRLF→LF，内容不改；**不要直接编辑 CSV**。数据变更走版本号与新 manifest，不走手改行。

---

## 3. LIBERO-10 子集的结构

### 3.1 10 个任务

| `task_idx` | BDDL stem（场景） | `instruction` | BDDL `:goal` 原子（n） |
|---:|---|---|---:|
| 0 | `KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it` | turn on the stove and put the moka pot on it | `Turnon stove`; `On moka pot`（2） |
| 33 | `KITCHEN_SCENE4_put_the_black_bowl_in_the_bottom_drawer_of_the_cabinet_and_close_it` | put the black bowl in the bottom drawer of the cabinet and close it | `Close drawer`; `In bowl`（2） |
| 78 | `KITCHEN_SCENE6_put_the_yellow_and_white_mug_in_the_microwave_and_close_it` | put the yellow and white mug in the microwave and close it | `In mug`; `Close microwave`（2） |
| 133 | `KITCHEN_SCENE8_put_both_moka_pots_on_the_stove` | put both moka pots on the stove | `On pot1`; `On pot2`; `Turnon stove`（3） |
| 137 | `LIVING_ROOM_SCENE1_put_both_the_alphabet_soup_and_the_cream_cheese_box_in_the_basket` | put both the alphabet soup and the cream cheese box in the basket | `In soup`; `In cheese`（2） |
| 145 | `LIVING_ROOM_SCENE2_put_both_the_alphabet_soup_and_the_tomato_sauce_in_the_basket` | put both the alphabet soup and the tomato sauce in the basket | `In soup`; `In tomato`（2） |
| 158 | `LIVING_ROOM_SCENE2_put_both_the_cream_cheese_box_and_the_butter_in_the_basket` | put both the cream cheese box and the butter in the basket | `In cheese`; `In butter`（2） |
| 193 | `LIVING_ROOM_SCENE5_put_the_white_mug_on_the_left_plate_and_put_the_yellow_and_white_mug_on_the_right_plate` | put the white mug on the left plate and put the yellow and white mug on the right plate | `On mug1→plate1`; `On mug2→plate2`（2） |
| 237 | `LIVING_ROOM_SCENE6_put_the_white_mug_on_the_plate_and_put_the_chocolate_pudding_to_the_right_of_the_plate` | put the white mug on the plate and put the chocolate pudding to the right of the plate | `On mug→plate`; `On pudding→right region`（2） |
| 276 | `STUDY_SCENE1_pick_up_the_book_and_place_it_in_the_back_compartment_of_the_caddy` | pick up the book and place it in the back compartment of the caddy | `In book→caddy back`（1） |

这 10 个任务正好是 LIBERO-10 的 10 个原生 BDDL 任务。`task_idx` 是来源仓的全局下标（l10 取值 0–276 的子集），**不是** 0–9 的序号，也不是连续编号。

### 3.2 行数结构：28 个扰动单元 + 10 条 C0

把 `(task_idx, target)` 称为一个**扰动单元**。l10 有：

```text
多目标任务 9 个 × 3 个 target（s1/s2/both） = 27 个单元
单目标任务 t276 × 1 个 target（g）           =  1 个单元
----------------------------------------------------
                                              28 个单元
```

每个单元的行数：

```text
full unit（pose 或 mixed）: L0(1) + L1(3) + L2(3) = 7
joint unit（专用关节目标）: L0(1) + L1(3)         = 4   # 关节没有 L2
C0（每任务 1 条）                                  = 1
```

因此：

```text
28 单元 × L0(1)          = 28
28 单元 × L1(3 个 δ)     = 84
25 单元 × L2(3 个角度)   = 75    # 3 个 joint 单元没有 L2
10 任务 × C0(1)          = 10
--------------------------------
                          197
```

逐任务：

| `task_idx` | full units（7 行） | joint units（4 行） | C0 | 合计 |
|---:|---:|---:|---:|---:|
| 0 | 2 | 1 | 1 | **19** |
| 33 | 2 | 1 | 1 | **19** |
| 78 | 2 | 1 | 1 | **19** |
| 133 | 3 | 0 | 1 | **22** |
| 137 | 3 | 0 | 1 | **22** |
| 145 | 3 | 0 | 1 | **22** |
| 158 | 3 | 0 | 1 | **22** |
| 193 | 3 | 0 | 1 | **22** |
| 237 | 3 | 0 | 1 | **22** |
| 276 | 1 | 0 | 1 | **8** |
| 合计 | 25 | 3 | 10 | **197** |

- **22 行** = `1 + 3×7`：三个 target 都是 full unit（6 个 target 全为 pose 的多目标任务）。
- **19 行** = `1 + 2×7 + 4`：两个 full unit + 一个 joint unit（`t000`、`t033`、`t078`）。
- **8 行** = `1 + 1×7`：只有 `g`（`t276`）。

按 family 汇总：

| family | 单元数 | 每单元行 | 行数 |
|---|---:|---:|---:|
| pose（自由物体） | 22 | 7 | 154 |
| mixed（`both` 含一个关节） | 3 | 7 | 21 |
| joint（专用关节目标） | 3 | 4 | 12 |
| `-`（C0） | 10 | 1 | 10 |
| 合计 | 28 + 10 | — | **197** |

### 3.3 target 语义：到底撤销了什么

| `target` | 撤销关系数 | 含义 | l10 单元数 | l10 行数 |
|---|---:|---|---:|---:|
| `c0` | 0 | no-op 对照 | 10（每任务） | 10 |
| `g` | 1 | 任务唯一的原生 goal 原子 | 1（`t276`） | 7 |
| `s1` | 1 | 第 1 个（执行顺序）子目标 | 9 | 60 |
| `s2` | 1 | 第 2 个（执行顺序）子目标 | 9 | 57 |
| `both` | 2 | `s1` + `s2` 两个关系 | 9 | 63 |
| `pre` | 1 | 前置条件（不是 goal 原子） | 0 | 0 |

关键点：

1. **`s1`/`s2` 按执行顺序，不按 BDDL 文本顺序。** `t033` 的 BDDL 先写 `(Close ...)` 再写 `(In ...)`，但 CSV 里 `s1=In bowl`（先放碗）、`s2=Close drawer`（后关门）。以 `revoked_predicates` 为准，不要自己解析 BDDL 顺序。
2. **`both` 是“恰两个谓词”，不是“全部原生原子”。** `t133` 有 3 个原生原子，`both` 只撤销两个 `On`；`Turnon` 不在 `revoked_predicates` 里，保持为真。`n_targets=3` 也不能反推 `both` 撤销了 3 个。
3. **`g` 只出现在单目标任务。** l10 只有 `t276` 用 `g`；多目标任务用 `s1`/`s2`/`both`。
4. **l10 没有 `pre`。** `target=pre` 只定义在 `goal-t030`（开抽屉取碗的关节前置），l10 的关节本身都是 goal 原子（`Turnon` / `Close`），区别只在于是否被撤销（`t133` 的 `Turnon` 不撤销）。

全 B 的 target 分布，能看出 l10 的特殊性：

| target | l10 | 其它 suite | 全 B |
|---|---:|---:|---:|
| `s1` | 60 | 0 | 60 |
| `s2` | 57 | 0 | 57 |
| `both` | 63 | 7（`goal-t030`） | 70 |
| `g` | 7 | 204 | 211 |
| `pre` | 0 | 4（`goal-t030`） | 4 |
| `c0` | 10 | 30 | 40 |
| 合计 | **197** | **245** | **442** |

也就是说：**`s1`/`s2` 是 l10 独有的**；除 `goal-t030` 的 7 条 `both` + 4 条 `pre` 外，多目标撤销全部集中在 l10。这是“B 的 l10 必须单独看”的数据原因。

### 3.4 `n_targets`、BDDL 原子数、撤销数不是同一个量

| 量 | 含义 | l10 取值 |
|---|---|---|
| `n_targets` | 来源矩阵运行时跟踪的 goal atom 数（按数据卡说明，可包含运行时跟踪的前置原子） | 3（9 个任务）、1（`t276`） |
| BDDL 原子数 | `:goal` 中 `And` 展开后的谓词数（A 的 `n_goals`） | 2（8 个任务）、3（`t133`）、1（`t276`） |
| 撤销关系数 | 本 case 实际撤销的谓词数 | 1（`g`/`s1`/`s2`）、2（`both`） |

因此：

- 不要用 `n_targets` 当 `n` 做“n=1 vs n=2”的分层；B 的 `n` 是**撤销关系数**（1 或 2）。
- 不要用 A 的 `n_goals` 去对 B 的 `n_targets`；二者定义不同。
- `t133` 是唯一 BDDL 3 原子的 l10 任务，但它的 `both` 仍只撤销 2 个关系。

### 3.5 分布汇总

按 level：

| level | 行数 | 占 l10 | 组成 |
|---|---:|---:|---|
| `C0` | 10 | 5.1% | 10 个任务各 1 条 |
| `L0` | 28 | 14.2% | 28 个单元各 1 条 |
| `L1` | 84 | 42.6% | 28 个单元 × 3 个 δ |
| `L2` | 75 | 38.1% | 25 个 full unit × 3 个角度 |
| 合计 | **197** | 100% | — |

按 target：

| target | 行数 | 占 l10 |
|---|---:|---:|
| `s1` | 60 | 30.5% |
| `s2` | 57 | 28.9% |
| `both` | 63 | 32.0% |
| `g` | 7 | 3.6% |
| `c0` | 10 | 5.1% |

按 family：

| family | 行数 | 占 l10 |
|---|---:|---:|
| `pose` | 154 | 78.2% |
| `mixed` | 21 | 10.7% |
| `joint` | 12 | 6.1% |
| `-`（C0） | 10 | 5.1% |

按 param：

| param | 行数 | 说明 |
|---|---:|---|
| 空 | 38 | C0 10 + L0 28 |
| `d03` / `d06` / `d10` | 28 / 28 / 28 | L1 每个 δ 各 28 条 |
| `r30` / `r60` / `r90` | 25 / 25 / 25 | L2 每个角度各 25 条 |

从“撤销关系数”看：l10 有 **124 条单关系**（`s1` 60 + `s2` 57 + `g` 7）和 **63 条双关系**（`both`），合计 187 条 treatment。

---

## 4. 扰动几何：l10 上具体怎么注入

### 4.1 level 的几何

| level | 自由物体（pose） | 关节（joint） | l10 示例 |
|---|---|---|---|
| `C0` | 不写状态 | 不写状态 | `b-l10-t000-c0` |
| `L0` | 回到 episode 初始位置/四元数 | 回到 episode 初始关节值 | `b-l10-t000-both-l0` |
| `L1` | 初始位置 + 沿“区域中心 → 初始位姿”水平射线 δ | 初始→达成跨度的 10/25/40% | `b-l10-t000-s1-l1-d06` |
| `L2` | 初始位置 + 绕世界 z 轴 yaw θ | 不存在 | `b-l10-t000-s2-l2-r60` |

细节：

- `L0` 的“初始”是 **episode t=0、settle 之后**的快照（主表 `init_row=0`），不是注入前一刻的状态。
- `L1` 的方向是水平射线：从被撤销关系对应的区域中心指向物体初始 XY；δ 是 nominal 值。实现可能为了把关系变假而继续外推、为了不穿模而抬高/回退，**实际值以 `Δtranslation_m` 为准**，不要假设正好 3/6/10 cm。
- `L1` 的关节不是“位移 3/6/10 cm”，而是按**初始→达成开度跨度的 10/25/40%** 回退；若关系仍为真，会继续折半，直到变假，实际比例记录在注入结果里。
- `L2` 的 yaw 是在**初始位置**上改姿态，不是先把物体移到别处再转；只适用于自由物体。

### 4.2 `both` 与 mixed 的特殊规则

| case 形态 | `L1` 对 pose 部件 | `L1` 对 joint 部件 | `L2` |
|---|---|---|---|
| 单 pose target（`s1`/`s2`/`g`） | 平移 δ | — | yaw |
| 单 joint target（`s1`/`s2`） | — | 比例回退 | 无此 case |
| `both`，两个 pose（如 `t133`/`t137`） | 各自平移 δ | — | 各自 yaw |
| `both`，pose + joint（`t000`/`t033`/`t078`） | 平移 δ | **回初始值，不按比例** | pose yaw；joint 回初始值 |

这条规则来自 [`src/libero_rollback/runtime/perturbation.py`](../src/libero_rollback/runtime/perturbation.py)：`both`/`mixed` 的 `L1` 走“pose 平移 + joint 回初始”，只有**专用 joint target** 才走比例回退；`L2` 对 joint 部件一律回初始值。读 l10 的 `both` case 时不要假设“两个部件都按同一 level 变形”。

### 4.3 l10 里哪些单元是 joint / mixed

| `task_idx` | joint 单元 | mixed 单元（`both` 含关节） | 其余 |
|---:|---|---|---|
| 0 | `s1`（`Turnon stove`） | `both` | `s2` 为 pose |
| 33 | `s2`（`Close drawer`） | `both` | `s1` 为 pose |
| 78 | `s2`（`Close microwave`） | `both` | `s1` 为 pose |
| 133 | — | — | `s1`/`s2`/`both` 全为 pose |
| 137 / 145 / 158 / 193 / 237 | — | — | 全为 pose |
| 276 | — | — | `g` 为 pose |

因此：

- `t000` 的 `s1`、`t033` 的 `s2`、`t078` 的 `s2` 只有 `L0` + 3 个 `L1`，**没有 `L2`**；对应任务因此是 19 行而不是 22 行。
- `t000`/`t033`/`t078` 的 `both` 仍然是 7 行（含 `L2`），因为 `family=mixed`，`L2` 作用在 pose 部件、joint 部件回初始值。
- `t133` 的 `both` 是两个自由物体的 `On`，不是 mixed；`Turnon` 不在撤销集里。

---

## 5. 触发、预算与判定

### 5.1 触发

- `trigger=all_done`：**当前状态**下全部原生 goal 原子为真（不是历史账本、不是“曾经成功”）。
- 第一次 `all_done` 后等 `delay_steps=10`；注入瞬间还要求“全部 goal 为真且全部被撤销关系为真”，否则继续等，最多 `max_trigger_wait=60` 步。
- 等不到 → `trigger_not_reached`，该 case 记为 `N/A`，**不是 0%**，也不进 Recovery 分母。
- `delay_steps=10` 与 `replan_steps=10` 对齐，避免触发落在同一个动作块内。

### 5.2 预算

- 触发前最多 `max_steps=600` 步。
- 注入后 `total_budget_steps = injection_step + repair_window(600)`；也就是说**在触发步之后再追加 600 步**，不是固定 600+600=1200。触发越早，总步数越少。
- 必须记录 `repair_budget_steps` 与 `repair_steps_used`；旧 `b-matrix.csv` 的 `repair_window` 仍是 300（frozen 参考）；新 `completion-rollback.csv` 与 runner 用 600。
- 主表 `init_row=0`、`seed=0`、`camera=256`、`settle=10`、`replan=10`。
- 成功判定只用环境 `check_success()` + GT 谓词 trace；**禁止 VLM 判官进入指标路径**。

### 5.3 逐 case 验收

README §5.2 的验收项：

| 检查 | 判据 |
|---|---|
| `baseline_task_solvable` | 同任务在 A/基线协议下可成功（同模型同协议） |
| `completed_relation_true_before_intervention` | 触发时被撤销关系为真，来自 GT |
| `relation_false_after_intervention` | `L0/L1/L2` 注入后为假；`C0` 相反，必须仍为真 |
| `no_object_penetration` | 物体-场景侵入 ≤ 1 cm |
| `zero_velocity_after_intervention` | 注入后线/角速度归零 |
| `object_released` | 两指间距 > 1 cm（已松开） |
| `restorable` | 状态写回 oracle 能在 repair window 内恢复关系（只证明几何可修） |
| `geometry_recorded` | `Δtranslation_m`、`Δangle_rad`、`axis` 已落盘 |

实现注记（以当前代码为准）：

- `case_valid` 的硬门控实现了：注入前关系为真、注入后全假、无穿模、零速度（`pre` 目标另加 `goal_preserved`）；C0 走 no-op 分支，要求终局 goal 为真。
- `object_released` 与 `restorable` 记录在 `validity`/注入结果中并进入报告；当前 `case_valid` 不因 `restorable=false` 否决，但证据分类器会因 `object_released=false` 判 `injection_invalid`。
- l10 没有 `pre` 目标，因此不会走 `goal_preserved` 分支。

### 5.4 读数：Recovery 与 SR 不是一回事

| 读数 | 定义 | l10 注意 |
|---|---|---|
| **Recovery** | 终局时**全部被撤销关系**为真 | `s1`/`s2` 只看 1 个关系；`both` 看 2 个；`t133` 不含 `Turnon` |
| **SR** | 终局时**全部原生 goal 原子**为真 | `t133` 要求 3 个原子；`s1`/`s2` case 也要求另一个子目标仍为真 |

因此：

- `s1`/`s2` case 的 `recovered=true` 不代表整条任务成功；`success` 另算。
- `t133` 的 `both` 只撤销两个 `On`；如果模型在恢复两个壶的同时把炉灶关掉，可能 `recovered=true` 而 `success=false`。报告必须同时给 `Recovery` 与 `SR`，不能用一个替代另一个。
- `Recovery = valid_recovered / (valid_recovered + valid_not_recovered)`；`C0`、无效注入、外部复原、协议不完整、不可触发一律排除分母。
- `control_rate = valid_control / C0 attempted`；`C0` 必须终局成功才算 `valid_control`。
- 每个率给 Wilson 95% CI；主表数字必须带 init 数、预算、CI；单 seed/单 init 的点估计不能当稳定结论。

相关 verdict：`valid_recovered`、`valid_not_recovered`、`valid_control`、`injection_invalid`、`trigger_not_reached`、`truth_unverified`、`incomplete`。完整枚举见 [`docs/SPEC.md`](SPEC.md) §6.1。

---

## 6. 与 D-native 的配对（l10 的核心用法）

### 6.1 数据层面的对齐

| 维度 | B(l10) | D-native |
|---|---|---|
| case 数 | **197**（10 个任务） | **189**（9 个任务，无 `t276`） |
| 触发 | `all_done` + delay 10 | `early` / `mid` / `later` |
| 撤销目标 | `g`/`s1`/`s2`/`both`（`s1` 60 条） | 恒为 `s1` |
| level | `C0` 10 / `L0` 28 / `L1` 84 / `L2` 75 | `C0` 9 / `L0` 27 / `L1` 81 / `L2` 72 |
| 预算 | 600 + 600 | 800 + 600 |
| 控制 | 每任务 1 条矩阵 `C0`（`all_done`） | 9 条 `all_done_control`；窗口内没有矩阵 `C0` |

B 的 `l10 + target=s1` 子集正好 **60 条**，与 D-native **任一窗口**的 60 条逐格相同：

```text
B(l10, s1) 60 = L0 9 + L1 27 + L2 24
D(任一窗口) 60 = L0 9 + L1 27 + L2 24   # t000 的 s1 是 joint，没有 L2
```

case_id 可直接对齐（窗口任选，这里以 `early` 为例）：

```text
b-l10-t033-s1-l0      ↔ d-l10-t033-early-l0
b-l10-t033-s1-l1-d03  ↔ d-l10-t033-early-l1-d03
b-l10-t033-s1-l2-r30  ↔ d-l10-t033-early-l2-r30
```

`t276` 只有 B 侧（单目标、无第二个子目标），**不能**与 D 配对。

### 6.2 执行状态：配对是数据口径，不是现成结果

- 当前仓库的 B runner 已实现；**D 的窗口触发（`early`/`mid`/`later`）尚未实现**（`runtime/triggers.py` 缺失，见 [`docs/implementation-status.md`](implementation-status.md)）。
- 因此现在能产出 B(l10) 的 `all_done` 臂，**还不能产出 B↔D 的配对 ΔRecovery**。上表是数据分析口径，不是已跑结果。
- D 的 9 条 `C0` 全在 `all_done`，窗口内没有矩阵 `C0`；窗口 no-op 对照是已知数据缺口，不能拿 `all_done_control` 近似 `early`/`mid`/`later` 的对照。

### 6.3 比较纪律

- B 与 D 的触发、预算、控制结构都不同；**只做同任务/同 level/同 init 的配对差**，不要并排比绝对 Recovery。
- 若一定要比绝对率，先做预算对齐臂（B 用 `--max-steps 800`），并在附录标注“非主表协议”。
- 配对统计用 exact McNemar（同任务、同 level/param、同 init），并按 structure/task 聚类报 CI；不要按 episode 独立处理。
- `t276` 只进 B 的表，不进 B↔D 配对表。

---

## 7. 选择与运行（当前实现）

### 7.1 先分清“当前实现”和“规划中的 CLI”

[`docs/cli-spec.md`](cli-spec.md) 描述的是**目标 CLI**（`--rollback`、`--level`、`--window`、`--controls` 等）。当前仓库实际可用的是：

- `scripts/run_b_matrix.py`（薄 CLI，B runner）；
- `libero-rollback run`（同一套 `RunConfig`/`select_cases`，额外支持 `--split lite`）。

当前**没有** `--level`/`--window`/`--controls`；筛选靠 `--suites`、`--case-ids`、`--max-cases`、`--max-tasks`、`--shard-*`。下面的命令只使用当前实现，`cli-spec.md` 里的 `--level L1:d03` 等不要直接照抄。

### 7.2 常用选择与条数

| 目的 | 选择方式 | cases |
|---|---|---:|
| l10 全量 | `--suites l10` | **197** |
| l10 treatment（不含 C0） | case 列表过滤掉 `-c0` | 187 |
| l10 `s1`（与 D 配对） | `target=s1` | **60** |
| l10 `L1:d03` | `level=L1-d03` | **28** |
| l10 单任务（如 `t033`） | 前缀 `b-l10-t033-` | **19** |
| l10 单任务（如 `t133`） | 前缀 `b-l10-t133-` | **22** |
| l10 `C0` | `target=c0` | **10** |
| lite 中的 l10 | `libero-rollback run --split lite --suites l10` | **2** |

注意：`lite` 只含 `b-l10-t000-c0` 与 `b-l10-t000-s1-l0` 两条 l10 case；用 lite 冒烟**不能**代表 l10 的 28 个单元。

> 若要与 2026-11-18 的 Spatial 报告同口径（非 C0 首次恢复即停），加 `--stop-on-recovery`；默认仍是跑满 600 步修复窗口（B 主表口径）。

### 7.3 命令

```bash
# 0) 矩阵摘要 / l10 列表（197 行）
libero-rollback list --suite l10

# 1) 静态校验（不读 BDDL、不启仿真、不需要 GPU）
python scripts/validate_dataset.py --dataset dataset

# 2) l10 全量计划：只写 plan.json，不是证据
uv run python scripts/run_b_matrix.py --dry-run \
  --suites l10 --output runs/plan-b-l10

# 3) l10 全量执行：需要 LIBERO_HOME + 仿真环境 + 模型环境
uv run python scripts/run_b_matrix.py --suites l10 \
  --policy pi05 --checkpoint "$PI05_CHECKPOINT" --output runs/b-l10

# 3b) 与 Spatial 报告同口径：首次恢复即停（可选）
uv run python scripts/run_b_matrix.py --suites l10 --stop-on-recovery \
  --policy pi05 --checkpoint "$PI05_CHECKPOINT" --output runs/b-l10-earlystop

# 4) 报告
libero-rollback report --run runs/b-l10
```

只跑 `s1`（60 条）或某个 level：

```bash
# 从 list 里筛出 s1 的 60 条
libero-rollback list --suite l10 | awk '$4 == "s1" {print $1}' > runs/l10-s1.txt

uv run python scripts/run_b_matrix.py --suites l10 \
  --case-ids $(cat runs/l10-s1.txt) \
  --policy pi05 --checkpoint "$PI05_CHECKPOINT" --output runs/b-l10-s1

# 只跑 L1:d03（28 条）；注意当前 CLI 不会自动补 C0
libero-rollback list --suite l10 | awk '$3 == "L1-d03" {print $1}' > runs/l10-l1d03.txt
uv run python scripts/run_b_matrix.py --suites l10 \
  --case-ids $(cat runs/l10-l1d03.txt) --output runs/b-l10-l1d03
```

单任务：用前缀过滤，而不是 `--max-tasks`：

```bash
libero-rollback list --suite l10 | awk '$1 ~ /^b-l10-t033-/ {print $1}' > runs/l10-t033.txt
uv run python scripts/run_b_matrix.py --suites l10 \
  --case-ids $(cat runs/l10-t033.txt) --output runs/b-l10-t033
```

### 7.4 两个容易踩的坑

1. **`--max-tasks` 按矩阵全局任务顺序取前 N 个**（goal 在前），再与 `--suites` 求交。因此：

   ```bash
   python scripts/run_b_matrix.py --suites l10 --max-tasks 2   # → 0 条，不是 t000/t033
   ```

   任务级选择请用 `--case-ids` 前缀过滤；`--max-cases` 是按筛选后的 CSV 顺序截断（前 19 条正好是 `t000`，但不要依赖这个巧合）。

2. **当前 CLI 不会自动补控制臂。** 过滤出 28 条 `L1:d03` 就只跑 28 条，不会自动加 10 条 `C0`。若要“28 treatment + 10 C0 = 38”，需要把 `C0` 显式加入 `--case-ids`；规划中的 `--controls` 还未实现。

### 7.5 产物

```text
<output>/
├── run-manifest.json
├── matrix.json
├── episodes.jsonl
├── run-summary.json
├── report.md
└── <suite>/<case_id>/seed-<n>/
    ├── status.json
    ├── results.json
    ├── summary.json
    ├── trace.jsonl
    └── video.mp4
```

`--dry-run` 只写 `plan.json`；`plan.json` 不是证据，不能从中抄任何 Recovery/成功率。

---

## 8. 校验与不变量

### 8.1 loader 强制的不变量

`load_b_matrix()`（[`src/libero_rollback/matrices.py`](../src/libero_rollback/matrices.py)）在加载时校验全表，任何一条失败就抛错：

1. 17 列必须齐全；`case_id` 全库唯一。
2. `suite ∈ {goal, object, spatial, l10}`；`target ∈ {c0, g, s1, s2, both, pre}`。
3. `trigger` 必须为 `all_done`，`delay_steps` 必须为 10。
4. 每个任务**恰好一条 `C0`**；C0 的 `target=c0`、`revoked_*` 为空、`expected_relation_after=true`。
5. 非 C0 必须 `expected_relation_after=false`，且至少一个 `revoked_object` 和一个 `revoked_predicate`。
6. level/param 组合合法：`L0` 无 param；`L1 ∈ {d03,d06,d10}`；`L2 ∈ {r30,r60,r90}`。
7. `family=joint` 不允许 `L2`；`L0` 必须有 pose/joint family；`mixed` 允许 `L2`。
8. `target` 基数：`g`/`s1`/`s2`/`pre` 恰 1 个谓词；`both` 恰 2 个。
9. `target=pre` 只允许 `goal-t030`，且必须是 joint、恰 1 个谓词。
10. 谓词必须带括号、不能嵌套；每个谓词必须提到至少一个 `revoked_objects` 中的物体（前缀匹配）。
11. 同一任务的 `instruction`、`bddl_name` 必须一致。
12. C0 的 `semantics` 为 `relation_holds_control`，非 C0 为 `relation_then_resume`（数据约定）。

### 8.2 loader **不**检查的内容

- `n_targets` 与 BDDL 原子数是否一致（两者定义不同，见 §3.4）。
- BDDL/init 文件是否存在、是否可解（静态层不读 `LIBERO_HOME`）。
- 注入是否真的让关系变假、是否穿模、是否可复原（需要仿真/oracle）。
- 窗口触发是否可达（D 轴）。
- `repair_window`/预算是否被 runner 正确使用（需运行期检查）。

### 8.3 验证命令

```bash
python scripts/validate_dataset.py --dataset dataset
# [validate_dataset] rows: a=40 b=442 d_native=189 d_compose_provisional=360 c=0
# [validate_dataset] checks: 12/12 passed
# [validate_dataset] OK

python -m pytest tests/test_dataset.py -q   # CI 中同一组契约测试
```

本次写作时 `validate_dataset.py` 实测 12/12 通过；这不等于 l10 的仿真可解性/可复原性已通过。

---

## 9. 已知限制与易错点（l10）

1. **`task_idx` 不是 0–9 序号。** l10 的 `task_idx` 取值为 `0, 33, 78, 133, 137, 145, 158, 193, 237, 276`，是来源仓的全局下标；A/B/D 共享同一映射，不要重编号。SPEC §2.2 的旧措辞与冻结数据有出入，已在 [`dataset/README.md`](../dataset/README.md) §4 记录。
2. **`n_targets` 不能当 `n`。** l10 的 9 个多目标任务都是 `n_targets=3`，即使 BDDL 只有 2 个原子；`t276` 是 1。B 的 `n` 是撤销关系数（1/2）。
3. **`s1`/`s2` 不是 BDDL 顺序。** `t033` 是反例（BDDL 先 `Close` 后 `In`，CSV 的 `s1=In`、`s2=Close`）。以 `revoked_predicates` 为准。
4. **`both` 不是“全部原子”。** `t133` 的 `both` 只撤销两个 `On`，`Turnon` 保持真；`Recovery` 与 `SR` 可能分离。
5. **`t276` 是单目标，8 条，无 D-native 对应。** 它只能进 B 的表，不能进 B↔D 配对。
6. **3 个 joint 单元没有 `L2`。** `t000-s1`、`t033-s2`、`t078-s2` 只有 4 行；对应任务是 19 行不是 22 行。不要按 22 行去对齐。
7. **l10 没有 v2 全量执行结果。** 当前 v2 B 已跑 Goal+Object 165 + Spatial 80；l10 197 条未跑。本仓 2026-11-18 的 l10 all_done smoke 只有 8 条（8/8 触发、7/8 有效、0/5 恢复），其中 `b-l10-t033-s2-l0` 因抽屉复位与碗穿模 11.6 mm 被门控判 invalid。lite 里只有 2 条 l10 case；前序仓的 v1 l10 数据是另一套协议，不能当 B(l10) 的 Recovery。
8. **D 的窗口 runner 还没实现。** B↔D 的 60 对是数据口径；`early`/`mid`/`later` 触发、窗口 no-op 控制都还不能在当前仓库执行。
9. **B/D 预算不同。** B 是 600 步 + 注入后追加 600，D 是 800 + 600；跨 B/D 只做配对差，不做绝对率并排。
10. **`--max-tasks` 是全局任务序。** 见 §7.4；l10 任务级选择用 `--case-ids` 前缀。
11. **主表是单 seed、单 init。** 矩阵本身不含方差信息；报告必须带 init 数、预算、CI，不能把单点当稳定结论。
12. **数据是冻结导入的。** 改行会破坏 sha256 与 manifest；需要变更时走版本号/重新导入，不手改 CSV。

---

## 10. 附录

### 10.1 l10 case_id 模式

```text
b-l10-t000-c0
b-l10-t000-s1-l0
b-l10-t000-s1-l1-d03 / -d06 / -d10          # s1 是 joint，无 L2
b-l10-t000-s2-l0
b-l10-t000-s2-l1-d03 / -d06 / -d10
b-l10-t000-s2-l2-r30 / -r60 / -r90
b-l10-t000-both-l0
b-l10-t000-both-l1-d03 / -d06 / -d10
b-l10-t000-both-l2-r30 / -r60 / -r90

b-l10-t033-c0
b-l10-t033-s1-l0 + s1-l1-* + s1-l2-*        # s1 是 pose，全网格
b-l10-t033-s2-l0 + s2-l1-*                   # s2 是 joint，无 L2
b-l10-t033-both-l0 + both-l1-* + both-l2-*   # mixed

b-l10-t078-...                               # 同 t033 的模式

b-l10-t133-c0
b-l10-t133-{s1,s2,both}-{l0,l1-*,l2-*}       # 全 pose，22 条

b-l10-t137 / t145 / t158 / t193 / t237       # 同 t133 的 22 条模式

b-l10-t276-c0
b-l10-t276-g-l0 + g-l1-* + g-l2-*            # 8 条
```

### 10.2 快速复核计数

```bash
python - <<'PY'
import collections, csv

rows = [
    row
    for row in csv.DictReader(open("dataset/matrices/b-matrix.csv", encoding="utf-8"))
    if row["suite"] == "l10"
]
print("cases", len(rows), "tasks", len({row["task_idx"] for row in rows}))
print("level", dict(sorted(collections.Counter(row["level"] for row in rows).items())))
print("target", dict(sorted(collections.Counter(row["target"] for row in rows).items())))
print("family", dict(sorted(collections.Counter(row["family"] for row in rows).items())))
PY
```

预期输出：

```text
cases 197 tasks 10
level {'C0': 10, 'L0': 28, 'L1': 84, 'L2': 75}
target {'both': 63, 'c0': 10, 'g': 7, 's1': 60, 's2': 57}
family {'-': 10, 'joint': 12, 'mixed': 21, 'pose': 154}
```

### 10.3 术语

| 术语 | 含义 |
|---|---|
| B / b_matrix | completion-boundary rollback：任务完成后撤销已达成关系 |
| l10 | LIBERO-10，长程多目标 suite；B 的 40 个任务中有 10 个来自这里 |
| `all_done` | 当前状态下全部原生 goal 原子为真 |
| 扰动单元 | `(task_idx, target)`；一个单元展开 L0/L1/L2 的多条 case |
| `C0` | no-op 对照，不动状态 |
| `L0` / `L1` / `L2` | 回初始 / 外推 δ / yaw θ；`L1`/`L2` 是形态，不是难度 |
| `s1` / `s2` | 按执行顺序的第 1/2 个子目标 |
| `both` | `s1` + `s2` 两个关系（恰 2 个谓词） |
| Recovery | 条件恢复率：只看被撤销关系是否终局为真 |
| SR | 联合成功率：全部原生 goal 原子终局为真 |
| D-native | 执行中撤销（`early`/`mid`/`later`），与 B 的 `all_done` 相对 |

### 10.4 相关文档

- 数据契约：[`docs/SPEC.md`](SPEC.md) §3.3、§4、§5
- B 的设计与验收：[`README.md`](../README.md) §3.4–3.5、§5.2
- 数据卡与已知债务：[`dataset/README.md`](../dataset/README.md) §4
- 四套件 L0 恢复效果汇总：[`docs/l0-recovery-summary.md`](l0-recovery-summary.md)
- 实验设计与 B/D 分工：[`docs/cli-spec.md`](cli-spec.md) §11（注意：其中 `--rollback/--level/--window` 是规划 CLI）
- 实现状态：[`docs/implementation-status.md`](implementation-status.md)
- 加载/校验：[`src/libero_rollback/matrices.py`](../src/libero_rollback/matrices.py)
- 注入几何：[`src/libero_rollback/runtime/perturbation.py`](../src/libero_rollback/runtime/perturbation.py)
- B runner：[`src/libero_rollback/runner.py`](../src/libero_rollback/runner.py)
- 薄 CLI：[`scripts/run_b_matrix.py`](../scripts/run_b_matrix.py)
