# 目标初始位置扰动：LIBERO-Plus / LIBERO-Pro 调研与回滚对齐方案

> 日期：2026-11-18 ｜ 关联：[protocol.md](protocol.md) §6.2、[b-matrix.md](b-matrix.md) §4、[README.md](../README.md) §11、[perturbation.py](../src/libero_rollback/runtime/perturbation.py)
>
> 问题：B/D 的回滚位置都是「episode Init + 偏移」。如果把回滚位置直接对齐 LIBERO-Plus / LIBERO-Pro 的静态扰动，是否等价于直接做了一个消融实验？
>
> 结论：**方向对，但不能“直接保持一致”。** 两个基准扰动的都是 **reset 时的初始状态分布**，不是 rollout 中途的状态写回；其中只有 LIBERO-Pro 的 Pos 扰动在结构上能和我们的“单目标回滚”干净对齐。对齐后得到的是 **「同一目标状态、不同历史/上下文」的对照**，可以做成消融，但必须补一条 **fresh-start 对照臂**；否则只是外部效度，不是消融。LIBERO-Plus 的 layout 是**整场景重采样**，单目标回滚无法复现。

---

## 0. TL;DR

| 问题 | 答案 |
|---|---|
| 两个基准扰动的是什么？ | reset 时改初始状态/场景（静态）；不是执行中途改状态（动态） |
| LIBERO-Pro Pos 怎么动？ | **只动目标物体的 placement region**，沿 +x 或 +y 平移；在 object 任务中目标在 init 里被钉住（std=0），所以是**确定性平移**；标称 `0.1–0.5`，**实测物理位移 `0.07–0.35 m`**；region 大小/朝向不变 |
| LIBERO-Plus layout 怎么动？ | **整个场景所有 region 重新采样**；level `L` 的位移半径约 `L×1 cm`（桌面场景）或 `L×3 cm`（地面场景），方向随机；目标只是其中一个 |
| Plus O2 有多少可用？ | **696 个基准 case / 800 个生成实例**，覆盖 B 的全部 40 个任务；每个 case 有 BDDL + 单状态 init，目标 qpos 可直接读 |
| 我们的 L1 是什么？ | `episode init + δ`，δ ∈ {3,6,10} cm，方向是「目标 region 中心 → init」的径向；实测 applied δ 与标称一致 |
| 我们的 L2 是什么？ | `episode init` 位置不变，绕世界 z 轴 yaw ∈ {30,60,90}° |
| 现有网格和基准重合吗？ | 只是部分重叠：3/6/10 cm 落在 Plus 的 1–5 cm（桌面）/ 3–15 cm（地面）区间内；Pro 是 7/14/21/28/35 cm，只有 10 cm 落在 Pro P1–P2 之间 |
| 对齐后是不是消融？ | **是**「静态扰动 vs 完成后动态回滚」的消融，前提是加 **同状态、从 t=0 跑的对照臂**；否则只是把 B 变成 Pro 的一个特例 |
| 建议 | **不要改冻结的 L1**；新增独立的 `B-ext` 矩阵：`B-Pro-P1..P5{x,y}` + `F-Pro-P1..P5{x,y}`（fresh-start），Plus 只做单目标边际近似或另开整场景臂 |

---

## 1. 两个基准到底怎么扰动目标初始位置

### 1.1 LIBERO-Pro 的 Position（Pos）扰动

官方仓：[Zxy-MLlab/LIBERO-PRO](https://github.com/Zxy-MLlab/LIBERO-PRO)、镜像 [RLinf/LIBERO-PRO](https://github.com/RLinf/LIBERO-PRO)。论文：[arXiv:2510.03827](https://arxiv.org/abs/2510.03827)。

**协议原文（README「Initial Position Perturbation Experiment」）**：

- X 轴：`x0.1`、`x0.2`、`x0.3`、`x0.4`、`x0.5`；
- Y 轴：`y0.1` … `y0.5`；
- 做法：把对应 `libero_object_temp_<axis><level>` 的 BDDL 与 init 文件复制到 `libero_object_temp`，再正常 reset/eval。

**它实际改了什么（我们逐文件核对）**：

- 只改 BDDL 里的 `target_object_region`（目标物体的采样区域），**不改** `bin_region` / `other_object_region_*`；
- `:ranges` 的**宽度不变**（本例 `0.05 m × 0.05 m`），只平移中心；
- **没有** `:yaw_rotation` 块，Pos 不旋转目标；
- `libero_object_temp_*/…pruned_init` 仍是 50 条 init（shape `(50, 110)`）；但**目标物体的 x/y 在 50 条里 std=0**，固定在 region 中心（`-0.12,-0.24` → `-0.05,-0.24`），变的是 robot qpos 与其他物体。也就是说在 object 任务中 Pos 是**确定性平移**，不是区域内随机采样。

> **关键核对：官方 LIBERO init 与 Pro base 逐字节一致**（`max abs diff = 0.0`）。Pro 没有改 base init，只改了 BDDL 的 target region 与对应 init 文件；目标在官方 init 里本来就是钉住的。

**实测位移（`pick_up_the_alphabet_soup_and_place_it_in_the_basket`，两个任务交叉验证）**：

| 配置 | target region 中心 | 相对原始中心位移 |
|---|---|---|
| 原始 | `(-0.120, -0.240)` | — |
| `x0.1` | `(-0.050, -0.240)` | `+0.070 m` |
| `x0.2` | `(+0.020, -0.240)` | `+0.140 m` |
| `x0.3` | `(+0.090, -0.240)` | `+0.210 m` |
| `x0.4` | `(+0.160, -0.240)` | `+0.280 m` |
| `x0.5` | `(+0.230, -0.240)` | `+0.350 m` |

Y 轴同理：`y0.1` → `+0.07 m`，…，`y0.5` → `+0.35 m`。

> **注意 0：Pos 的随机性在“轴/水平”，不在目标抖动。** 在 object 任务里，目标在 50 条 init 中完全相同（x/y std=0）；每 episode 变的是 robot qpos 和其他物体。**但不是所有 suite 都这样**：spatial 任务的目标 x/y std ≈ 0.008（在 2 cm region 内采样），见 §3.3。
>
> **注意 1：标称 ≠ 物理位移。** 发布文件里存在稳定的 `0.7×` 系数（`0.1 → 0.07`、`0.5 → 0.35`），发布代码没有解释这个系数。引用论文时可以说 “0.1–0.5 units”，但写物理距离时必须写 **0.07–0.35 m**，或者明确写“标称 0.1–0.5，实测 0.07–0.35 m”。
>
> **注意 2：Pos 是仅目标物体的扰动。** 目标容器/参照物（basket、plate 等）不动，其他干扰物也不动。这一点和我们的单目标回滚结构一致。
>
> **注意 3：公开仓只带了 `libero_object` 的 Pos 预打包文件。** `init_files/*_temp_[xy]0.[1-5]` 只存在 `libero_object_temp_*`；README/leaderboard 里其他 suite 的 Pos 列没有对应的预打包文件，复现需要自己按同样规则生成（生成器未发布）。

**论文里的剂量-反应**：Figure 4 报告 OpenVLA / π0 在位移超过 **0.2 units** 后成功率迅速掉到 0，π0.5 能撑到约 **0.4 units**。这里的 “units” 是标称值；按实测系数，0.2 units ≈ 14 cm，0.4 units ≈ 28 cm。

### 1.2 LIBERO-Plus 的 Objects Layout 扰动

官方仓：[sylvestf/LIBERO-plus](https://github.com/sylvestf/LIBERO-plus)。论文：[arXiv:2510.13626](https://arxiv.org/abs/2510.13626)（CVPR 2026 版）。补充材料 §A.1。

**协议原文（补充材料 §A.1）**：

- **O1: Confounding Objects**：随机加入 `n` 个未见过的干扰物（416 类），改 BDDL，文件名带 `_add` 后缀；
- **O2: Target Object Pose**：对目标物体的初始位置 `(x, y, z)` 和朝向 `(pitch, yaw, roll)` 做随机扰动；不改目标物体本身；保持与其他物体的必要语义关系（例如 “next to the cookie box” 的目标身份不变）。

**发布文件的实际结构**：

- 每个任务有 `_level{L}_sample{S}.bddl`（`L ∈ 1..5`，`S ∈ 1..4`），以及 `_add_*`、`_language_*`、`_light_*` 等维度变体；
- `_level` 变体把**所有** `:regions` 的 `:ranges` 中心重新采样，region 宽度保持不变；
- 在我们抽样的两个任务里，所有 region 的 `:yaw_rotation` 都是 `(0, 0)`（`cabinet_region` 除外，它是固定的 affordance region）。也就是说，这批 layout 变体**实际只动了位置**；O2 声明的 orientation 扰动没有体现在这批 BDDL 里（是否体现在 init 文件或其他任务，待核实）。

**实测位移（scene 内所有 region 的最大位移，4 个 sample/level）**：

| level | 桌面场景（`libero_spatial` 任务，region 宽 2 cm） | 地面场景（`libero_object` 任务，目标 region 宽 5 cm） |
|---|---|---|
| L1 | 1.0 cm | 2.6 cm |
| L2 | 1.9 cm | 5.6 cm |
| L3 | 2.9 cm | 8.1 cm |
| L4 | 3.9 cm | 11.7 cm |
| L5 | 4.8 cm | 14.3 cm |

目标物体自己的位移是**随机抽取**的，不一定取到最大值。例如桌面任务 L5 的 4 个 sample，目标位移均值 3.1 cm、最大 4.5 cm；地面任务 L5 均值 9.3 cm、最大 13.2 cm。

> **补充：Figure 4 的子类怎么来。** 论文把 layout 拆成 Confounding / Displacement 两个子类；发布文件里没有单独的 `_displacement_*` 后缀，Displacement 很可能是在这批 `_level` 文件里按“目标 region 位移”筛选或重算的。若要把 B-ext 对齐到 Figure 4 的某根柱子，先确认它用的是哪一批文件/哪些任务，不要假设 `_level` 就是图上的 Displacement。
>
> **注意 4：level 不是统一的 cm 网格，是相对场景/区域的尺度。** 桌面场景近似 `L × 1 cm`，地面场景近似 `L × 3 cm`；生成器未公开，精确半径必须按任务实测，不能直接写 “L1=1cm, L5=5cm”。
>
> **注意 5：Plus 是整场景重采样，不是单目标平移。** 目标容器/参照物（plate、basket 等）的 region 也会一起动。因此**单目标回滚无法复现 Plus 的联合 layout**；最多只能匹配目标物体的**边际分布**。
>
> **注意 6：level 的语义有歧义。** 发布文件的 `levelN` 与位移幅度单调对应（上面两行就是证据）；但 arXiv v1 附录 C.3 把 L1–L5 定义为“4 个模型里有几个解出”的**事后难度分层**。CVPR 版则说是“参数化后校准成 5 个难度级”。写论文时要区分：**文件名的 level 是扰动参数级**，不是“模型难度级”。

### 1.2.1 O2 全量盘点（2026-11-18 补）

对 `git tree`（21,032 entries）和 `task_classification.json`（10,030 rows）做全量检索。判定：`category == "Objects Layout"` 且名字以 `_level{L}_sample{S}` 结尾 = O2（goal 任务为 `<task>_moved_level...`）；同 category 下 `_add_*` = O1。

| 量 | 数 |
|---|---:|
| 全仓 BDDL（含 `libero_mix` 重复） | 16,330 |
| `_level*` BDDL（O2 候选） | 1,600 |
| `_level*` init（`init_files/libero_newobj/`） | 1,600 |
| 唯一 O2 实例（task × level × sample） | **800** = 40 × 5 × 4 |
| 基准测试集 O2（`task_classification.json`） | **696** |
| 基准 Objects Layout 合计 | 1,525 = O2 696 + O1 829 |

**按 suite（基准测试集）**：

| suite | O2 `_level` | O1 `_add` | B 任务 | O2 覆盖 |
|---|---:|---:|---:|---:|
| goal | 185 | 240 | 10 | 10/10 |
| object | 195 | 208 | 10 | 10/10 |
| spatial | 177 | 208 | 10 | 10/10 |
| l10 | 139 | 173 | 10 | 10/10 |
| 合计 | **696** | **829** | **40** | **40/40** |

**文件与命名**：

- BDDL：`libero/libero/bddl_files/<suite>/<task>_level{L}_sample{S}.bddl`；goal 为 `<task>_moved_level{L}_sample{S}.bddl`。
- init：`libero/libero/init_files/libero_newobj/<suite>/<task>_level{L}_sample{S}.pruned_init`。
- **696/696 都有 BDDL + init**（逐个校验，0 missing）；init 是**单状态**（本例 110 维），不是 50 条，可直接读目标 qpos（torch.save 格式，成员 `*/data.pkl`）。

**实测（`pick_up_the_alphabet_soup...` sample1）**：目标相对 base 的位移 `L1..L5 = 1.7 / 5.8 / 8.0 / 11.2 / 9.2 cm`；z 不变，四元数不变（`angle=0`）。所以 O2 的 level 是**任务相关的实际位移**，不是统一的 3/6/10 cm。

**全量审计（696 case，target 平均位移 / scene max 平均，cm）**：

| suite | L1 | L2 | L3 | L4 | L5 | target max | 变更特征 |
|---|---:|---:|---:|---:|---:|---:|---|
| object | 2.1 | 4.1 | 6.0 | 7.9 | 9.8 | 14.9 | 7/7 region 全动 |
| spatial | 0.7 | 1.3 | 2.0 | 2.6 | 3.2 | 4.9 | 11/11 region 全动 + `table_center` 高 2→5 cm |
| goal `_moved` | 16.2 | 18.2 | 17.8 | 18.6 | 20.5 | 43.8 | 目标大幅搬家，level 不单调 |
| l10 | 0.7 | 1.4 | 1.8 | 3.1 | 3.5 | 8.7 | 全 region 动 |

**全量变更统计**：696/696 所有 region 中心都变；`:yaw_rotation` 变化 **0**；`:language` / `:objects` / `:init` / `:goal` 变化 **0**；spatial 177/177 有 1 个 region 尺寸变化（`table_center` 高 2→5 cm），其他 suite 0。逐 case 表见 [`experiments/plus-o2-audit/o2-change-table.csv`](../experiments/plus-o2-audit/o2-change-table.csv)。

**O1 是干扰物，不是目标初始位置**：`_add_*` 加 n 个未见过的干扰物（416 类），基准里 829 个 case。若研究问题是“rollback vs layout”，O1 应作为独立因子排除，不要混进 O2 计数。

**结论**：O2 能作为回滚目标，且数量足够：**696 个基准 case / 800 个生成实例，覆盖 B 的全部 40 个任务；每个 case 都有完整 BDDL + 单状态 init，目标 qpos 可直接读。**

**与 B 的严格配对**：以 BDDL `:obj_of_interest` 的第一个对象作为任务的主目标，B 的 378 个 pose/mixed treatment 里 **252** 个撤销的正是该对象（goal 56/63、object 70/70、spatial 70/70、l10 56/175）；其余 126 个撤销的是容器/夹具/第二物体，只能用 O2 的“副作用位姿”，需单独标注。

**但把它当回滚目标，有四个语义问题**：

1. `_level` 是**整场景 region 重采样**，不是只动 target；只写 target qpos = 目标边际；写全 state = 整场景 layout，会同时撤销多个关系。
2. O2 的 target 是任务的操作对象；B 的 `s1`/`s2` 可能是容器/夹具（basket/plate/stove）。O2 init 里这些物体也动了，但语义上不是 O2 target。
3. O2 level 的位移是任务相关的；要对 B 的 3/6/10 cm，需 (a) 用 O2 level 当剂量并记录实测位移，或 (b) 按最近邻从 4 个 sample 里选；不要假设 `L3=3cm`。
4. 抽样中 O2 目标四元数不变（`angle=0`），B 的 L2 yaw 暂时没有 O2 对照；全量 orientation 需再核。

### 1.3 一句话对比

| 维度 | LIBERO-Pro Pos | LIBERO-Plus Layout | 我们的 L1 | 我们的 L2 |
|---|---|---|---|---|
| 扰动对象 | 仅目标物体 | **整场景所有物体** | 被撤销的目标 | 被撤销的目标 |
| 基准 | 规范 BDDL region | 规范 BDDL region | **episode 采样后的 Init** | **episode 采样后的 Init** |
| 幅度 | 标称 0.1–0.5；实测 0.07–0.35 m | `L×1 cm`（桌面）/ `L×3 cm`（地面），随机 ≤ 半径 | 3/6/10 cm | 30/60/90° |
| 方向 | **+x 或 +y** | **每个物体随机二维方向** | **region 中心 → Init 的径向** | 世界 z 轴 yaw |
| 朝向 | 不变 | O2 声明会扰动；抽样的 BDDL 里为 0 | 不变 | 只加 yaw |
| region 大小 | 不变 | 不变 | 状态写回，无 region 概念 | 同左 |
| 发生时机 | **reset 时（静态）** | **reset 时（静态）** | **完成后（动态）** | **完成后（动态）** |

---

## 2. 我们的 L0 / L1 / L2 到底是什么

代码依据：[`perturbation.py`](../src/libero_rollback/runtime/perturbation.py)

- `L0`（`_restore_initial`，L518）：把目标恢复到 **episode 初始快照**（injector 在 settle 后、t=0 时捕获的 `_initial`）；
- `L1`（`_apply_translation`，L558）：`initial.position` 的 XY 加上 `direction * δ`，`direction` 是「目标 region 中心 → initial XY」的单位向量；如果关系仍为真会**继续外推**，穿模会**抬高/回退**，实际值记录在 `applied_delta_m`；
- `L2`（`_apply_yaw`，L640）：`quat_yaw(θ) * initial.quat`，位置保持 `initial.position`。

**已跑 Goal+Object 165 例的实测**（`experiments/b-rollback/report-goal-object-20261118/cases.jsonl`）：

| level | n | 标称 | `applied_delta_m` 实测 | 说明 |
|---|---|---|---|---|
| L1 goal d03 | 8 | 3 cm | mean 3.0 cm | 无外推 |
| L1 goal d06 | 8 | 6 cm | mean 6.0 cm | 无外推 |
| L1 goal d10 | 8 | 10 cm | mean 10.0 cm | 3 例有 clearance lift |
| L1 object d03 | 9 | 3 cm | mean 3.0 cm | 无外推 |
| L1 object d06 | 10 | 6 cm | mean 5.9 cm | 无外推 |
| L1 object d10 | 10 | 10 cm | mean 8.7 cm | 部分回退以避免穿模 |

L1 的方向分布（实测 `applied[].direction`）：

- `object` suite：几乎全是 `-y`（mean `(-0.05, -0.98)`，约 `-93°`）——因为 basket 在 `+y`，径向自然指向 `-y`；
- `goal` suite：混合（mean `+75°`，范围 `-67°…+180°`）。

> **关键区分：`geometry.delta_translation_m` 不是 L1 的剂量。** 它是「完成态 → 注入态」的总位移（goal 0.17–0.42 m，object 0.43–0.63 m），包含了从目标位置回到 Init 的那一大段。对外比较必须用 `injection.applied[].applied_delta_m`（相对 Init 的偏移），不要用 `geometry.delta_translation_m`，否则会把“回到初始位置”误读成“扰动了 40 cm”。
>
> 同理，L2 的 `geometry.delta_angle_rad` 也不是施加的 yaw：它是「完成态四元数 → 注入态四元数」的夹角，包含了物体初始朝向与完成朝向的差。施加的 yaw 看 `injection.applied[].yaw_deg`。

---

## 3. “位置对齐”的三种含义

### 3.1 名义对齐（只对数字）

把 L1 的 δ 改成 `{0.1, 0.2, 0.3, 0.4, 0.5}` m，但方向和基准分布不变。**这不算对齐**，因为：

- Pro 实测是 0.07–0.35 m，不是 0.1–0.5 m；
- Pro 是 +x/+y 轴，我们的 L1 是径向（object suite 是 -y）；
- Pro 的 region 大小/朝向不变，我们的 L1 从 Init 出发、可能把物体推出 region 或推到 fixture 里。

### 3.2 逐点对齐（Pro 可以做到，至少 object 任务是精确的）

我们核对了官方 LIBERO 的 init 文件与 LIBERO-Pro 的 base init：

- `libero_object/pick_up_the_alphabet_soup...pruned_init` 两边**逐字节一致**（max abs diff `0.0`）；
- 目标物体的 qpos x/y 在 50 条 init 中 **std = 0**，固定在 region 中心 `(-0.12, -0.24)`；
- Pro 的 `x0.1` 把它改成 `(-0.05, -0.24)`，`y0.5` 改成 `(-0.12, 0.11)`，也是 50 条全部相同（std = 0）。

所以在 object 任务中，Pro 的 Pos 是**确定性的目标位姿平移**，不是“在平移后的 region 内重新采样”。我们的 episode 用同一份 official init，`initial.position` 就是那个固定点；`initial.position + δ` 与 Pro 的 `x0.k` / `y0.k` **逐点相同**，朝向也相同（L1 保留 `initial.quat`，Pro 不改朝向）。这意味着：**对目标被钉住的任务，`init + δ` 就是精确对齐，不需要 replay init 文件。**

> **统计含义：** 因为目标位姿不随 init_row 变，B 的 165 条里目标状态只由 `(task, δ, direction)` 决定；`init_row` 不是目标位姿的独立重复。配对分析要按 task 聚类（或把 init_row 当 robot/其他物体的重复），不要把 50 个 init_row 当成 50 个独立的目标样本。

### 3.3 什么时候只能“同分布”，什么时候必须 replay

如果某个任务的目标在 init 里不是钉住的（`std > 0`），那么设 `X ~ Uniform(R)`、基准平移 `δ`：

```
X + δ  ~  Uniform(R + δ)
```

它与基准从 `R + δ` 采样的 `X'` **同分布**，但不是同一个点。此时：

- 论文只写“same perturbation distribution”：`init + δ` 就够；
- 论文要写“same state / 同一绝对位姿”：必须 **replay 基准的 init 文件**（加载 `libero_object_temp_x0.3/...pruned_init` 的第 `i` 条 state，取目标 qpos，再在回滚时写入），不能靠 offset。

**反例（必须逐任务核对）：** 我们抽查了 spatial 任务 `pick_up_the_black_bowl_next_to_the_plate_and_place_it_on_the_plate`，目标 qpos 的 x/y std ≈ `0.008`，是在 2 cm region 内采样的，不是钉住的。因此 object 与 spatial 的行为不同：

- object 任务（本例）：`init + δ` **逐点精确**；
- spatial 任务（本例）：`init + δ` 只保证**同分布**，要逐点必须 replay。

对 LIBERO-Plus 的整场景 layout，即使目标被钉住，其他物体/容器的 region 也动了，单目标 offset 仍然只能匹配目标的边际；见 §3.4。

### 3.4 LIBERO-Plus 的特殊困难

Plus 的 layout 是**整场景重采样**：目标、目标容器、干扰物的 region 一起动。我们的回滚只写被撤销的目标（`case.revoked_objects`），因此：

- 只能匹配**目标物体的边际分布**：`X_target + Δ`，`Δ` 从 Plus 的随机位移分布里采；
- 不能匹配联合 layout：basket/plate 的位置、其他物体的位置仍停在完成态，和 Plus 的 reset 状态不同；
- 如果强行把 `revoked_objects` 扩展到所有物体，单条 case 会同时撤销多个关系，破坏 B 的“单关系撤销”归因。

所以：**Plus 的 layout 不适合作为 B 的单目标对齐目标**；它更适合另开一个“整场景 layout”臂，和 B 的主表分开。

---

## 4. 对齐后是不是消融实验？

### 4.1 是「静态 vs 动态/历史」的消融，不是「rollback vs no rollback」

把条件写成 2×2：

| | 目标初始状态 = 规范 Init | 目标初始状态 = 基准扰动后的 Init |
|---|---|---|
| **从 t=0 开始（无完成历史）** | LIBERO 原版 / C0 基线 | **LIBERO-Pro Pos / Plus layout（基准）** |
| **完成后回滚（有完成历史）** | 我们的 **L0** | 我们的 **B-ext（对齐后）** |

把这张表写成两个因子：**L = layout（规范 vs O2 全 state）**，**R = rollback（fresh reset vs 完成后写回）**。

| | L=0（规范 layout） | L=1（O2 layout） |
|---|---|---|
| **R=0（fresh）** | LIBERO 原版 / C0 基线 | **LIBERO-Plus O2（696 case）** |
| **R=1（rollback）** | **B L0（54 条 pose/mixed）** | **B-O2（最多 696 case）** |

- Layout 主效应（fresh）：`Success(L1,R0) − Success(L0,R0)`；
- Layout 主效应（rollback）：`Recovery(L1,R1) − Recovery(L0,R1)`；
- Rollback 主效应（规范）：`Recovery(L0,R1) − Success(L0,R0)`；
- Rollback 主效应（layout）：`Recovery(L1,R1) − Success(L1,R0)`；
- 交互 = 两个主效应之差（difference-in-differences）。

**只有同时有 L=1,R=0（Plus O2）和 L=0,R=0（基线），才能说“失败是 rollback 还是 layout 造成的”；只跑 B-O2 只能得到 layout 下的 rollback 效果。**

**注意 O2 的“layout”是整场景**：`_level` 把所有物体的 region 重新采样，不是只动 target。如果只把 O2 的 target qpos 写回，你测的是 **target displacement**，不是 layout；这时 L=1 的定义要改成“target displacement”，不能和 Plus O2 的整场景成功率混在一起说。

**696 怎么变成 B 的 case 数**（不要把 696 当成“现有 B 自动扩到 696”；它是新增的 L=1,R=1 臂）：

| 设计 | B-O2 | F-O2 | 说明 |
|---|---:|---:|---|
| 1 个 O2 case = 1 个 B-O2 case | 696 | 696 | 全量；1,392 runs |
| 1 sample / (task, level) | 195 | 195 | 195 个 task-level cell；390 runs |
| 3 个 level（1/3/5）× 1 sample | 116 | 116 | 232 runs |
| 只配 B 的严格主目标 case | 252 | 252 | B 的 378 个 pose/mixed 里撤销主目标的 252 个 |

- 左下 vs 左上 = “回滚”本身（历史/上下文）在**规范状态**下的效果；
- 右下 vs 右上 = “回滚”在**扰动状态**下的效果；
- 右下 vs 右上 就是你说的“直接对齐”带来的对照：**目标状态逐点相同（目标在 init 中被钉住的任务）或同分布（未被钉住的任务），唯一系统差异是“完成历史 + 机器人/其他物体在完成态”**。

换句话说，**L0 已经是 δ=0 的那一格对齐臂**（object 任务是逐点相同，spatial 任务是同分布）；B-ext 只是把 δ>0 的格子补上。

这确实是一个消融，但消融的因子是 **history / timing（静态 reset vs 完成后动态写回）**，不是“回滚机制”本身。写论文时建议叫 **“state-matched, history-controlled comparison”** 或 **“ablation of perturbation timing”**，不要叫“rollback 的消融”。

### 4.2 为什么必须加 fresh-start 对照臂

如果只跑 B-ext（右下），然后拿 LIBERO-Pro 论文里的 Pos 成功率（右上）来比，会有四个不可控差异：

1. 模型 checkpoint / 训练数据可能不同；
2. 任务子集不同（Pro 公开的 Pos 只有 `libero_object` 10 个任务）；
3. horizon / 成功判定不同（Pro 是完整任务成功；B 是撤销关系恢复 + 任务成功）；
4. 初始 robot pose 不同（Pro reset；B 在完成态）。

所以必须在**自己的 harness** 里补一条：

- **`F-Pro-P{1..5}{x,y}`（fresh-start）**：reset 环境，把目标写到与 B-ext **完全相同**的扰动后位姿，robot 回 reset pose，其他物体回规范 layout，从 t=0 跑同样的总预算，测完整任务成功。

然后：

```
Δ_history(δ) = Recovery_Bext(δ) − FreshSuccess_F(δ)
```

- `Δ_history > 0`：完成历史/上下文有帮助（例如策略已经知道目标在哪、抓取姿态更好）；
- `Δ_history < 0`：完成历史有害（例如策略重复失败轨迹、卡在完成姿态）；
- `Δ_history ≈ 0`：回滚等价于“从扰动初始状态重跑”，没有额外历史收益。

这就是一个干净的、可配对的消融。

### 4.3 如果没有 fresh-start 臂，会发生什么

- 你只是把 B 的 L1 换成了 Pro 的一个特例：**“在 Pro 的扰动状态上，从完成态恢复”**；
- 你无法区分“恢复率高”是因为 rollback 有用，还是因为这个状态本来就容易/难；
- 如果直接把 L1 的 3/6/10 改成 0.1–0.5，还会**破坏 v2 主表的可比性**（165 条 goal+object、197 条 l10 都按旧网格跑）；
- 与 [README §11](../README.md) 的声明冲突：那里写“本仓分布完全不动，只动任务结构；失败可归因到结构”。对齐后，B-ext 的目标状态分布**确实**和 LIBERO-Pro/Plus 的输入分布重合了，必须把这句话限定为“**episode 初始分布不动；B-ext 是完成后状态写回，不是 reset 分布**”。

---

## 5. 建议的实验设计（B-ext）

### 5.1 原则

1. **不改冻结的 B 矩阵**（`dataset/matrices/b-matrix.csv`）和现有 L1/L2 语义；
2. 新增独立矩阵 `dataset/matrices/b-ext-pro.csv`（以及可选的 `b-ext-plus.csv`），用新的 level 枚举；
3. 每条 B-ext case 必须能配对一条 F（fresh-start）case，配对键 = `(suite, task_idx, init_row, level, param)`；
4. B-ext 的数字**不进主表**，单独一张“外部校准/消融”表。

### 5.2 臂定义

| 臂 | 目标状态 | robot / 其他物体 | 起始 | 用途 |
|---|---|---|---|---|
| `C0` | 不动 | 完成态 | 完成后 | 控制 |
| `L0` | episode Init | 完成态 | 完成后 | 基准对照（规范初始状态） |
| `B-Pro-P{1..5}{x,y}` | Init + Pro 平移（7/14/21/28/35 cm，+x/+y） | 完成态 | 完成后 | 对齐 Pro Pos |
| `F-Pro-P{1..5}{x,y}` | 同 B-Pro | **reset pose / 规范 layout** | **t=0** | fresh-start 对照 |
| `L2` | Init + yaw | 完成态 | 完成后 | 独立形态（无基准对照） |
| `B-O2-L{1..5}` | O2 init 的 target qpos（只写 target） | 完成态 | 完成后 | 用 Plus O2 作为回滚目标 |
| `F-O2-L{1..5}` | O2 init 全状态（reset） | reset pose / O2 layout | **t=0** | Plus O2 的 fresh-start 基准 |
| `B-Plus-full-L{1..5}`（可选，另表） | 整场景 region 重采样 | 完成态 | 完成后 | 整场景 layout；多关系撤销，不做单因子 Recovery |

**方向选择**：Pro 的 +x/+y 是固定轴；建议每个任务做 `+x` 和 `+y` 两个方向（与 Pro 一致），不要用当前 L1 的径向。径向可以作为 B 主表的独立形态保留，但不要混进 B-ext。

**幅度选择**：用实测的 7/14/21/28/35 cm，不要用标称 0.1–0.5 m。如果论文表格要写“0.1–0.5 units”，在脚注里给实测换算。

**Plus O2 臂**：696 个基准 case（800 生成）全部覆盖 B 的 40 个任务；每个 case 有单状态 init，直接读 target qpos 写回。只写 target 时，其他物体保持完成态；要复现 Plus 初始条件，`F-O2` 用 `load_init_row` reset 到整条 O2 init。O2 的 level 位移是任务相关的（抽样 object 任务 L1–L5 = 1.7/5.8/8.0/11.2/9.2 cm），不要当 3/6/10 cm；剂量用实测 `applied_delta_m` 记录。整场景写入另开 `B-Plus-full`，会撤销多个关系。

### 5.6 直接用 O2 作为 all_done / D window 的注入目标？

**可以，但要区分两种实现，结论完全相反**：

- **target-only**：只写被撤销目标的 O2 qpos，其他物体/robot 保持完成态。这样 other-object layout 固定，是“完成后目标状态失效”的干净操作；可以支持“历史状态失效影响任务”的论点。
- **full-state**：写整条 O2 init，会把所有物体搬到 O2 layout；这时 layout 没有被排除，反而被引入，失败不能归因到 history。

**target-only 仍不能单独证明“历史”**：O2 target pose 本身可能很难（远/遮挡/碰撞）。必须配对 **F-O2**（F = fresh-start：reset 到同一 O2 初始状态，从 t=0 跑；不是 F 检验；同一 runner/模型/预算），否则 B-O2 失败可能只是状态难，不是历史失效。

**all_done 的风险**：O2 pose 是为 reset 场景生成的，**在 Init 时刻是有效的**；问题不是用例本身无效，而是同一个 pose 在 all_done 的 robot 位姿、其他物体位置、300 步修复预算下不一定可达/无碰撞。现有 `no_penetration` / `s1_reachable` 会排除一部分，必须报告排除率。goal `_moved` 是 16–44 cm，和 object/spatial 的 1–10 cm 不是同一档；**建议按 small/large 分层分析，不是修改或丢弃 `_moved` case**。

**D 三窗口**：D-native s1 只有 **8 个 pose 任务 + 1 个 joint（t000）**。O2 没有 joint 状态，t000 不能直接用。early = s1 刚完成，机器人还在 s1 附近，夹爪可能离目标近；mid/later 机器人已转向 s2，s1 物体留在原地，反而可能更远。**三种 window 都是状态写回，不要求物理 teleport 路径；只要写后状态满足 gates 即可**。所以 early 不是天然更危险；reachability 要逐 window 实测。

**B all_done 的 case 数估算**（保留 L0/C0 对照）：

| 方案 | B-O2 | + L0 | + C0 | 总 B |
|---|---:|---:|---:|---:|
| 1 O2 case = 1 B-O2（全量 696） | 696 | 60 | 40 | **796** |
| 1 sample / (task, level)（195 cell） | 195 | 60 | 40 | **295** |
| 3 个 level（1/3/5）× 1 sample | 116 | 60 | 40 | **216** |
| 只配严格主目标（B 的 252 个） | 252 | 60 | 40 | **352** |

**D 三窗口的 case 数估算**（8 个 pose 任务；joint t000 保留 12 条 L0/L1；C0 9）：

| 方案 | / window | ×3 window | + joint | + C0 | 总 D |
|---|---:|---:|---:|---:|---:|
| 全部 107 个 l10 pose O2 | 107 | 321 | 12 | 9 | **342** |
| 5 levels × 8 pose 任务（≈40） | 40 | 120 | 12 | 9 | **141** |
| 3 levels × 8 pose 任务 | 24 | 72 | 12 | 9 | **93** |
| 1 O2 / 现有 56 个 pose case | 56 | 168 | 12 | 9 | **189** |

> 5 levels × 8 任务是上界；l10 有 5 个任务缺一个 level，实际约 37–40/window。

### 5.3 度量

```
Recovery(δ)      = valid_recovered / (valid_recovered + valid_not_recovered)      # 现有口径
FreshSuccess(δ)  = 完整任务成功 / F 臂 attempts
Δ_history(δ)     = Recovery(δ) − FreshSuccess(δ)                                  # 配对 bootstrap CI
```

- 配对键：`(suite, task_idx, init_row, level, direction)`；同一 `init_row` 的 B 和 F 必须用同一个 base Init；
- 同时报告 `relation_restored` 与 `full_task_success` 两个口径；Pro 的成功是完整任务成功，不是“关系恢复”；
- 报告 `applied_delta_m` 的分布（mean/median/p90/max）和 `direction` 的单位向量，证明 B 与 F 的目标状态逐点相同（钉住任务）或同分布（未钉住任务）；
- **state-match 检查**：对 B 与 F 的目标初始位姿做 mean/std/KS 检验；要求 `|Δmean| < 5 mm` 且 KS 不显著，否则“同状态”不成立；
- 有效性门控沿用现有：`relation_false_after_intervention`、`no_object_penetration`、`zero_velocity`、`object_released`；Pro 对齐后如果目标被推进 fixture，该 case 记 `injection_invalid` 并报告排除率。

### 5.4 实现落点（不改现有协议）

- `schema`/`matrices.py`：新增 `level ∈ {P1..P5}`、`param ∈ {x07,x14,x21,x28,x35,y07,...}`，或复用 `L1` + 新 `source` 列；
- `perturbation.py`：给 `_apply_translation` 加一个 `direction_mode: radial | +x | +y` 和 `base: init | canonical`；B-ext 用 `base=init, direction=+x/+y`；
- `runner.py`：新增 F 臂——reset 到规范 init，写入目标扰动，从 t=0 跑；不要复用 B 的 `all_done` 触发；
- `dataset/sources.yaml` / `manifest.yaml`：记录从 LIBERO-Pro 实测得到的 region 中心与换算系数，以及从 LIBERO-Plus BDDL 实测的 `r_L`；
- 报告：B-ext 单独一张表，标题写明“post-completion rollback at benchmark-matched initial states”；不要与主表混排。

### 5.5 成本

- 现有 B 主表 l10 197 条尚未跑；B-ext 建议先用 O2 的 object suite（195 个基准 case，195 B + 195 F），确认 `Δ_history` 的方向后再扩；Pro 臂（7/14/21/28/35 cm × 2 方向）可作为第二组；
- 如果 F 臂复用同一 env/模型，单条成本与 B 接近；配对设计可以用同一 `init_row` 减少方差。

---

## 6. 对现有结论/声明的影响

1. **不要改 L1 的 3/6/10**：它是 B 主表的协议常量，改了之后 165 条 goal+object 和未来 197 条 l10 都不可比。要新开 B-ext。
2. **README §11 需要加限定**：现在写“本仓分布完全不动，只动任务结构”。B-ext 的目标状态分布与 Pro/Plus 的初始分布重合，但发生在完成后，不是 reset。建议改成：“episode 初始分布不动；B 的注入是完成后状态写回；B-ext 仅用于与静态扰动基准做 state-matched 对照，不改变 B 主表的归因口径。”
3. **L2 仍是独立形态**：Pro Pos 不旋转；Plus 的 O2 虽然声明 orientation，但抽样的 BDDL 里 yaw=0。L2 目前没有外部基准对照，不要强行说“对齐 Plus”。
4. **“消融”措辞**：建议写“ablation of perturbation timing / history”，不要写“rollback 的消融”。回滚机制没有被去掉，去掉的是“完成历史”。
5. **不要用 `geometry.delta_translation_m` 做跨基准比较**：它是完成态到注入态的总位移，不是相对 Init 的扰动剂量。

---

## 7. 待核实清单

- [ ] LIBERO-Pro 的 `0.7×` 系数来源：是坐标缩放、桌面尺寸，还是生成脚本的刻意缩放？在两个任务上稳定，但发布代码没有解释。
- [ ] LIBERO-Pro Pos 是否只发布了 `libero_object`：公开树里 `init_files/*_temp_[xy]*` 只有 object；其他 suite 的 Pos 结果如何复现？
- [ ] LIBERO-Plus `level` 的生成规则：桌面 `L×1 cm`、地面 `L×3 cm` 是场景尺度还是 region 尺度？需要更多任务拟合。
- [ ] LIBERO-Plus O2 的 orientation 扰动：在哪些任务/文件里实际非零？抽样的两个任务 yaw 全为 0。
- [x] LIBERO-Plus 的 `libero_goal` 是否有 layout 变体：**有**，命名是 `<task>_moved_level{L}_sample{S}.bddl`，185 个基准 O2 case；此前抽查漏了 `_moved` 前缀。
- [ ] 其他 suite 的目标是否也在 init 中被钉住：本文核对了 object 任务（std=0，钉住）和 spatial 任务（std≈0.008，未钉住）。钉住 → offset 即逐点对齐；未钉住 → 只能同分布或 replay。
- [ ] LIBERO 官方 init 是否严格 `Uniform(region)`：如果目标未钉住且经过拒绝采样/碰撞筛选，3.3 的“同分布”只是近似。
- [ ] F 臂的 robot 初始 pose：Pro 是 reset pose；B 是完成 pose。如果要做更细的分解，需要再加一个“robot 回 reset、其他物体完成态”的中间臂。

---

## 附录 A：实测数据与复现

### A.1 LIBERO-Pro region 中心（`pick_up_the_alphabet_soup_and_place_it_in_the_basket`）

```text
base   target_object_region: (-0.145 -0.265 -0.095 -0.215)  center (-0.120, -0.240)
x0.1   target_object_region: (-0.075 -0.265 -0.025 -0.215)  center (-0.050, -0.240)
x0.2   target_object_region: (-0.005 -0.265  0.045 -0.215)  center (+0.020, -0.240)
x0.3   target_object_region: ( 0.065 -0.265  0.115 -0.215)  center (+0.090, -0.240)
x0.4   target_object_region: ( 0.135 -0.265  0.185 -0.215)  center (+0.160, -0.240)
x0.5   target_object_region: ( 0.205 -0.265  0.255 -0.215)  center (+0.230, -0.240)
```

Y 轴：`y0.k` 的 center y = `-0.240 + 0.07k`（`k=1..5`）。

**核对结论**：官方 `libero-src/.../libero_object/pick_up_the_alphabet_soup...pruned_init` 与 Pro base 完全一致（max abs diff `0.0`）；目标 qpos x/y 在 50 条 init 中 std=0（`-0.12,-0.24`），`x0.1` 为 `-0.05,-0.24`。因此 Pro Pos 是确定性平移，`init + 0.07` 与 `x0.1` 逐点相同。

### A.2 LIBERO-Plus level 位移（scene max |d|，4 sample/level）

```text
libero_spatial 任务（region 宽 0.02 m）:
  L1 1.0 cm, L2 1.9 cm, L3 2.9 cm, L4 3.9 cm, L5 4.8 cm
libero_object 任务（目标 region 宽 0.05 m）:
  L1 2.6 cm, L2 5.6 cm, L3 8.1 cm, L4 11.7 cm, L5 14.3 cm
```

文件命名：`libero/libero/bddl_files/<suite>/<task>_level{L}_sample{S}.bddl`；`_add_*` 是 O1 干扰物，`_language_*` / `_light_*` 是其他维度。

### A.3 我们的 B（Goal+Object 165 例）

```text
L1 applied_delta_m: goal 3/6/10 cm 精确；object d10 均值 8.7 cm（部分回退）
L1 direction: object ≈ (0, -1)；goal 混合，均值约 +75°
L2 yaw 标称 30/60/90°；geometry.delta_angle_rad 不是施加的 yaw
```

### A.4 复现命令（在 WSL 仓内）

```bash
# LIBERO-Pro init 对比
.venv/bin/python .cache/analyze_init.py

# LIBERO-Plus level 位移
.venv/bin/python .cache/parse_plus_agg.py

# B 的 realized geometry
.venv/bin/python .cache/analyze_b_geometry2.py
```

> 上述 `.cache/*.py` 是本次调研的一次性脚本，未入库；正式复现应把读取 BDDL/init 的逻辑收进 `scripts/` 并加测试。
