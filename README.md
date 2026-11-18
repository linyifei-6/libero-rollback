# LIBERO-Rollback

> **A controlled-perturbation benchmark for goal-state persistence in Vision-Language-Action policies.**
>
> 状态：**v2.0-draft（2026-11-18）** ｜ 纯 Benchmark 仓库 ｜ 运行期只依赖原始 [LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO)（MIT）
>
> 本 README 是仓库规范（数据、协议、指标、复现口径），同时如实说明实现状态（[§0](#0-现状速览)）。**未实现的能力不会写成已完成。**

---

## 摘要 / Abstract

Frozen vision-language-action (VLA) policies are close to saturation on LIBERO's single-task suites, yet they collapse when the task is only *structurally* perturbed — no new objects, no new scenes, no changed viewpoints, no changed instruction vocabulary. The same π0.5 policy that solves 40/40 single tasks succeeds on 2/49 compositions built from the goals it just solved, and 87–90% of those failures complete **exactly one** subgoal and stop. The same pattern appears in the temporal dimension: when an already-true relation is revoked, only 8.8% of episodes restore it.

**LIBERO-Rollback** is a model-independent, controlled-perturbation benchmark for this failure mode. It fixes the input distribution and varies only the *causal structure* of the task: how many goal predicates must hold at once (axis A), and whether a predicate that has become true is later revoked (axis B). Four suites — **A** single-task intact, **B** completion-boundary rollback, **C** composition intact, **D** in-execution rollback — form the measurement matrix, together about **1,191 cases**. Every revoked case is paired with a no-op control, a script-oracle solvability/restorability certificate, and a reference case that differs in one factor only. The flagship metric is a **conditional recovery rate**, reported separately from unconditional success rate.

The benchmark ships as versioned CSV matrices plus LIBERO-native assets; it adds **zero new assets and zero new scenes**. A full four-suite leaderboard entry costs roughly one GPU-day per model, and the 30-case `lite` repro costs under one GPU-hour.

**Keywords**: goal-state persistence · rollback · capacity cliff · VLA evaluation · controlled perturbation

---

## 0. 现状速览

本仓正在从两个前序仓（`libero-rollback`、`libero-compose`）迁移**必要的代码与数据**并重写实现层。**运行时不得 import、不得路径引用这两个仓**；它们的角色仅是开发期来源与历史证据。仓库当前状态：

| 层 | 组件 | 状态 | 说明 |
|---|---|---|---|
| 规范 | 本 README + `docs/SPEC.md` | ✅ Phase 1 冻结 | `docs/SPEC.md` 是数据契约与模块接口的唯一权威 |
| 数据 | A 矩阵 40 / B 矩阵 442 / D-native 189 | ✅ 已迁移 | A 由脚本生成，B/D-native 导入并冻结；逐文件 sha256 在 manifest |
| 数据 | D-compose 360（占位） | 🟡 暂存不执行 | 复用 C 的结构 id；C 未构建前不进任何 split |
| 数据 | C 套件（160 结构） | ⬜ Phase 2 | 前序仓 512 ordered 不能直接充当；需按 40-task pool 重建 |
| 数据 | `manifest.yaml` / `sources.yaml` / `lite.yaml` / 数据卡 | ✅ 已生成 | `build_manifest.py --check` 0 diff；`validate` PASS（1,031 case） |
| 代码 | 静态层（矩阵 / schema / validation / evidence / metrics / report / CLI） | ✅ 已实现并测试 | 纯 stdlib + PyYAML/jsonschema；`libero-rollback validate` PASS |
| 代码 | 运行层（B runner / 注入 / 视频 / 3 个模型适配器） | 🟡 移植完成，待真机验证 | 本机无 MuJoCo/权重；dry-run 与 fake-env 测试通过 |
| 代码 | D 轴 runner（窗口触发 + D-native 执行） | ⬜ Phase 2 | 需要 GT 窗口触发器与 D-native 执行链路 |
| 代码 | C 套件生成器 + 覆盖证明 | ⬜ Phase 2 | 见 [§13 路线图](#13-路线图) |
| 证据 | 证书 C1/C2/C5/C7/C8 | 🟡 部分 | C3 可解性 / C4 可复原性仍缺（脚本 oracle） |
| 发布 | pip / HF dataset / datasheet / leaderboard | 🟡 本地部分 | 报告与 `leaderboard validate` 可用；发布流程 Phase 2 |

> **Phase 1 迁移结果（2026-11-18）**：已落地 A/B/D-native 数据（1,031 个 case 中的 671 个可执行 case）、静态契约层、B 套件运行层（移植）、报告/CLI 与文档。`C` 与 `D-compose` 因前序仓从未构建 v2 结构而留到 Phase 2（**不做假数据**）。本机未跑真实仿真/真实模型，因此**本仓当前没有任何主表数字**：§2 的数字是前序仓 v1 证据，只用于动机；逐项状态与验收命令见 [`docs/implementation-status.md`](docs/implementation-status.md)。

---

## 1. 这是什么

**一句话**：本仓测量冻结 VLA 策略的**目标状态完整性**——一个已经为真的目标关系被外部撤销后，策略是否知道它需要被恢复。

它把“组合/长程能力”拆成两个可分别操纵、且可配对比较的问题：

| 问题 | 操纵的因子 | 对应套件 |
|---|---|---|
| **Q1 结构新颖性**：模型不会的是“合取”，还是“**没见过的**合取”？ | 目标谓词数 n 与结构是否见过 | A ↔ C |
| **Q2 状态完整性**：达成状态被否定后补不回来，是因为“检测不到”，还是因为“**还有个目标没做完**”？ | 撤销 + 撤销时场上是否有 pending 目标 | B ↔ D |

两条设计原则：

1. **不改输入分布，只改任务因果结构。** 资产、场景、物体、视角、指令词表全部固定；因此每一次性能落差都可以归因到**一个**结构因子。
2. **纯仪器，不是方法。** 本仓**不实现、不主张、不评测任何恢复算法或 test-time harness**；冻结策略原样执行，外部干预只写仿真状态，恢复必须由策略自己完成。

### 1.1 本仓不做什么

- ❌ 训练/微调代码、恢复算法、控制器、调度器、VLM 判官；
- ❌ 新物体、新场景、新视觉分布（这是 LIBERO-Plus / PRO / MAX 的战场）；
- ❌ 与 LIBERO 官方数字直接横比（自定义协议必须自带 init 数、预算、CI）；
- ❌ sim-to-real 结论（scope 明确为仿真内冻结策略）。

---

## 2. 现象与初步证据

> 本节数字来自前序仓已完成的实验与**进行中**的 run，只用于说明现象；主表将在 v2.0 协议冻结后重跑。每行都带协议脚注，v1 与 v2 不混表（见 [§10.3](#103-v1-与-v2-不混表)）。

### 2.1 悖论（Paradox）

| 条件 | 模型 | 结果 | 协议口径 |
|---|---|---|---|
| 标准四套件单任务上界 | π0.5 | **40/40** | 4 套件 × 10 任务，1 init，600 步【v1 实测】 |
| 组合（GOAL，同场景、仅目标合取） | π0.5 | **2/49 = 4.1%** | 单条合取指令，600 步【v1 实测】 |
| 组合（OBJECT，场景内组合） | π0.5 | **12/300 = 4.0%** | 单条合取指令，600 步【v1 实测】 |
| 组合（纯 VLA 单指令） | SmolVLA 0.45B | **0/76 = 0%** | 76 条全部超步数、零进展【v1 实测】 |
| 完成边界撤销（旧 catalog） | π0.5 | **42/477 = 8.8%** 严格自修复；**160/477 = 33.5%** 终局满足 | 注入有效 477/518；`relation_then_resume`【v1 实测】 |
| 完成边界撤销（B 矩阵，**进行中**） | π0.5 | **21/117 = 17.9%** 条件恢复；C0 对照 10/10（Goal 子集） | 142/442 case 完成；Goal 子集 21/68 = 30.9%【2026-11-18 快照，非最终】 |

**悖论**：模型能做的每一个单步都做得到，合起来只剩 4%；撤销一个它刚刚亲手达成的真关系，只剩 8.8%–17.9%。失败不是“乱做”，而是**精准地只做一件事然后停**：失败中 **87–90%** 恰好完成 1 个子目标后停滞（one-and-done 签名）。

### 2.2 初步容量读数

- n=1 成功率 ≈ 1.00（Obj/Goal/Spatial 30 个单目标任务，1 init；A 套件还含 LIBERO-10 的 n=2 参照，单独报告）；
- n=2 成功率 ≈ 0.04（GOAL / OBJECT 组合）；
- 有效目标容量 **EGC = Σₙ SR(n) ≈ 1.04** —— 操作上等价于“一次只保持一个目标”。

### 2.3 已排除的解释（每条都有证据）

| 解释 | 排除证据 |
|---|---|
| 步数/预算不足 | 600 → 990 → 1600 步，组合任务仍是 0/4；SR–预算曲线斜率 CI 含 0 |
| 指令写坏了 | 同内容 staged（逐句）成功率 65.1%（54/83 stage 级），说明语言与技能都在 |
| 感知/场景变了 | 同场景、同 init、同物体，只换 `:goal` 的合取结构 |
| 只是模型弱 | π0.5 单任务 40/40；同模型 staged 65%，合取单句 4% |

结论：缺的不是技能、不是感知、也不是预算，而是**同时表示并跟踪一组目标谓词**的能力。**Compose = 时间点上的合取；Rollback = 时间区间上的合取**——它们是同一构念的两个投影，这就是把 A/B/C/D 放进同一份仪器的理由。

---

## 3. 测试设计

### 3.1 两条主设计轴 + 一条排除轴

| 轴 | 因子 | 水平 | 承载套件 |
|---|---|---|---|
| **A 共时** | 目标谓词数 n | 1 / 2 / 3（嵌套族 `g₁ ⊂ g₁∧g₂ ⊂ …`，同场景同物体池） | C（n 阶梯）、A（n=1/2 上界） |
| **B 历时** | 达成状态的时间完整性 | `intact` / `revoke` / `control`（no-op）/ `probe`（关系仍为真，不得虚假修复） | B、D |
| C 语言（排除项） | 同一 `goal_atoms` 的措辞 | `canonical` / `naive_concat` / `staged` / `paraphrase` | 全套件（`instruction_variant` 字段） |

- 措辞变体是**同一任务的评测臂**，不重复计入任务数。
- 两条官方指令的 naive 拼接只作**对照臂**，不作主指令。

### 3.2 四个套件（A/B/C/D）

| 套件 | 底盘 | 扰动 | 触发时机 | n | case 数 | 主指标 |
|---|---|---|---|---:|---:|---|
| **A** `single-intact` | 原始 LIBERO 4 套件 ×10 任务 | 无 | — | 1–2 | **40** | `SR` |
| **B** `completion-boundary-rollback` | 同 A 的 40 任务（Goal 10 / Object 10 / Spatial 10 / LIBERO-10 10） | `C0/L0/L1/L2` | `all_done`（任务完成后 delay 10 步） | 1–2 | **442** | `Recovery`（条件） |
| **C** `composition-intact` | 40 任务内同场景配对生成的组合结构 | 无 | — | 2（+40 条 n=3） | **160** | `SR` |
| **D** `in-execution-rollback` | D-native：LIBERO-10 原生多目标（9 任务）<br>D-compose：C 的 120 个 n=2 结构 | `C0/L0/L1/L2` | `early` / `mid` / `later` | 2 | **549**（native 189 + compose 360） | `Recovery`（条件） |
| | | | | **合计** | **1,191** | |

**B 的 case 分布**（`b-matrix.csv` 实计）：

| 维度 | 取值 |
|---|---|
| suite | goal 85 / object 80 / spatial 80 / l10 197 |
| level | `C0` 40 / `L0` 60 / `L1` 180 / `L2` 162 |
| family | pose 350 / joint 24 / mixed 28 / C0 40 |
| target | `g` 211 / `s1` 60 / `s2` 57 / `both` 70 / `pre` 4 / `c0` 40 |

**D 的 case 分布**（`d-matrix.csv` 实计）：native 189（LIBERO-10 九个多目标任务：`early/mid/later` 三窗口 × `L0/L1/L2` 参数族 + 9 条 `all_done` no-op 对照）；compose 360（120 个 n=2 结构 × 3 窗口 × `L0`，level 曲线由 B 承担）。

> **A 的实测 `n_goals`**（BDDL `:goal` 展开）：31 条 n=1、8 条 n=2、1 条 n=3（LIBERO-10 的 n=2 任务与 GOAL t030 的 n=3）。因此 A 在套件表里写 `n=1–3`，报告时按 suite 分列：A(Obj/Goal/Spatial) 是 n=1 锚点，A(l10) 是 n=2 参照。

> **为什么 D 不要求基础任务完成**：D 只要求“存在一个已完成的子任务，在模型去处理另一个子任务时被撤销”。触发条件由**单目标能力**保证（A 已证明其存在），因此 case 集不依赖“模型能否把整条任务做完”。

### 3.3 可比较对（这张表是设计核心）

| 对比 | 唯一变化的因子 | 回答的问题 |
|---|---|---|
| A(Obj/Goal/Spatial) ↔ B(同套件, `L0`) | 撤销 | **n=1 上：撤销的净效应** |
| A(L10) ↔ B(l10, `L0`) | 撤销 | **n=2、无 pending 时：撤销的净效应** |
| B(l10, `all_done`) ↔ D-native(同任务, `early/mid/later`) | **撤销时场上是否有 pending 目标** | **撤销代价里有多少来自“还有个目标没做完”** |
| A ↔ C | 结构是否见过（合取） | 模型不是不会合取，是不会**没见过的**合取 |
| C ↔ D-compose（同结构、`L0`） | 撤销 | **已有结构上的状态完整性**（配对 `Δ`） |
| `C0` ↔ `L0/L1/L2` | 是否真的改变状态 | 排除“延迟/强制继续本身有害” |
| `revoke` ↔ `revoke+restate` ↔ `noop+restate` | 是否重发指令 | 分清“不知道”与“不能”（重述臂） |

所有主结论用**配对差**，不用边际差。

### 3.4 撤销扰动族：`C0` / `L0` / `L1` / `L2`

| level | 定义 | 谓词后置 | 备注 |
|---|---|---|---|
| `C0` | **no-op 对照**：同样 delay、同样 post-success 窗口，**不动状态** | 必须仍为真 | **必须成功**；每任务恰好 1 条 |
| `L0` | 把被撤销物体/关节恢复到 **episode 初始位姿**（init row 0 settle 后快照） | 必须为假 | 落在策略 t=0 见过的构型上 |
| `L1` | `L0` + 沿「目标区域中心 → 初始位姿」水平射线外推 δ ∈ {**3, 6, 10 cm**} | 必须为假 | 关节任务改为开度 **10 / 25 / 40%** |
| `L2` | `L0` + 绕世界 z 轴 yaw θ ∈ {**30°, 60°, 90°**} | 必须为假 | 姿态离流形 |

三条纪律：

1. **`L1`/`L2` 不是难度等级**，是两种扰动形态；三者距完成态都远，变的是“复原目标是否落在策略见过的构型上”。不要写成“难度递增”。
2. 每条 case 必须记录实测几何量 `Δtranslation_m`、`Δangle_rad`、`axis`。
3. **`C0` 不可省**——没有它，无法排除“延迟/强制继续本身有害”这个平凡解释。

实现上直接写 MuJoCo `qpos/qvel` 后 `mj_forward`，因此对自由物体与关节（抽屉/微波炉门/炉灶）都适用；注入后必须通过**有效性门控**（见 [§5.2](#52-逐-case-验收b--d)）。

### 3.5 触发时机

| 套件 | 触发事件 | 定义 |
|---|---|---|
| B | `all_done` | 任务的全部 native goal 成立（真实成功，非历史账本）；`delay_steps=10`（与 `replan_steps=10` 对齐） |
| D | `early` | 第一个子目标完成、后续尚未开始 |
| D | `mid` | 已抓起后序目标物 |
| D | `later` | 后序物已被运到目标上方、尚未放置 |

D 的窗口检测**只使用 GT 谓词与仿真状态**，复用环境已有事件语义，**不自造几何判据**（旧版的 5 cm / 8 cm 判据已作废）。触发率是**实测值**，不是假设：窗口在某模型上 `trigger_rate < 20%` 时，该窗口不进主表，只在附录报“不可达”并说明原因。

### 3.6 case 身份、命名与矩阵

- **case 身份** = `(suite, 场景指纹, 目标原子集合[有序], init 源)` + 扰动定义；指令措辞是 case 属性，**不是**身份。
- 命名规则（机器可读）：
  - B：`b-<suite>-t<idx:03d>-<target>-<level>[-<param>]`，无操作对照 `b-<suite>-t<idx>-c0`；
  - D：`d-l10-t<idx:03d>-<window>-<level>[-<param>]`、`d-compose-<struct_id>-<window>-l0`；
  - `<suite> ∈ {goal, object, spatial, l10}`，`<level> ∈ {C0,L0,L1,L2}`，`<param> ∈ {d03,d06,d10,r30,r60,r90}`，`<window> ∈ {early,mid,later}`。
- **case 矩阵 CSV 是唯一机器可读来源**；`dataset/matrices/*.csv` 的列契约在 `docs/SPEC.md` 冻结。发布后 case_id 与语义不可静默变更，数据变更走版本号。
- `task_idx` 沿用来源仓的 **LIBERO 全局任务下标**（goal 0–270 / object 0–235 / spatial 0–244 / l10 0–276 的子集），**不是 0–9 重编号**；A/B/D 共享同一 `(suite, task_idx)` 映射（见 SPEC §2.2）。

### 3.7 分层与 split

| split | 内容 | 用途 |
|---|---|---|
| `lite` | 30 条（A/B/C/D 均衡抽样） | 冒烟 / CI / 论文复现，< 1 GPU-h |
| `core` | A 40 + B 442 + C 160 + D 549 = **1,191** | 主表、leaderboard |
| `variance` | 100 case × 5 init（0–4）= 500 episodes（40 A + 30 B + 30 D） | 估任务间异质性与 run-to-run 方差 |
| `restate` | B/D 子集的重述臂 ≈ 100 episodes | `Restate Δ` |
| `full` | `core` + `variance` + `restate` ≈ 1,700 episodes | 全量发布 |
| `negative` | `conflict / degenerate / infeasible` 与 `probe` | 负对照，**不进执行主表** |

**统计效率**：主 sweep 用“多任务 × 1 init”，另用 `variance` 估方差；p≈0.04 时 1,000 级 episode 的 SE≈0.6%，足以区分 4% 与 8%。**不卖规模，卖可归因性与成本。**

---

## 4. 指标

### 4.1 指标定义

| 指标 | 定义 | 角色 |
|---|---|---|
| `SR` | 联合成功率（全部目标同时为真） | A/C 主指标；B/D 次要 |
| **`Recovery`** | **条件恢复率**：条件于“撤销前关系为真且注入有效” | **B/D 主指标** |
| `Restate Δ` | `Recovery(revoke+restate) − Recovery(revoke)` | 区分“自觉性”与“能力” |
| `EGC` | `Σₙ SR(n)` = 平均同时达成的目标谓词数 | 共时轴招牌指标（C + A 上界） |
| `PP` | `P(≥1 子任务达成)`（C 上） | 零进展 vs one-and-done；D 的适用性筛选 |
| `One-and-Done` | 失败中“恰好完成 1 个子目标”占比 | 容量=1 的签名 |
| `Zero-Progress` | 一个子目标都未完成的占比 | 与 one-and-done 并列报告 |
| `Trigger rate` | 各窗口实际触发比例（`trigger_status` 四值） | 窗口矩阵；可达性画像 |
| `Notice latency` | 撤销 → 首次朝被撤销物体移动的步数 | 行为读数，非 0/1 |
| `Retention` | `SR_case / SR_ref` | 跨模型可比，扣掉模型绝对能力 |
| `Cost` | `s/episode`、`GPU-h/模型`、`$/leaderboard 条目` | 采纳门槛 |

四类终局读数（B/D 通用）：`both` / `restore_only` / `pending_only` / `neither`；主读数用 `both`（终局联合目标满足率），并在 D 上区分“补了旧的丢了新的”与“做完新的无视撤销”。

### 4.2 报告纪律（红线）

1. **禁止**把 `Recovery`（条件量）与 `SR`（无条件和）并排放进主表当同一个量。
2. **不可触发 = `N/A`，不是 0%**：分母为零时表格写 `n/a (PP=0)`；`N/A` 是一等结果，必须进表与正文。
3. **判定只用环境 `check_success()` + GT 谓词 trace**；**禁止**在指标路径上使用 VLM 判官（判官 P/R 可另做分析，不进主指标）。
4. 每个数字必须带 **init 数 + 预算 + CI**；**禁止** 1 seed 点估计进主表。
5. micro（全 case）+ macro（按 suite/scene 等权）双列；`Retention` 只在同协议下比较。
6. 两类失败模式分开报（zero-progress vs one-and-done），被筛掉的模型也要报。

### 4.3 统计方法

- 每个率给 **Wilson 95% CI**；
- 同 `(structure, init)` 跨臂用 **exact McNemar** 配对检验；
- suite 级 CI 用**按 structure 聚类的 bootstrap**（不是按 episode）；
- 协变量分析用层次 logistic 回归：`success ~ n_pred + revoke_level + model + (1|structure) + (1|scene)`，报 odds ratio + CI；
- 效应量优先于 p 值（报告 pp 差 + CI）；Stage 1 预注册 P1–P6，避免跑完再挑显著。

---

## 5. 可归因性：证书与负对照

### 5.1 八张证书（缺一不可）

| # | 证书 | 要求 |
|---|---|---|
| C1 | 完整性 | 每个场景的候选全部归类、计数加总一致（覆盖证明） |
| C2 | 初始状态 | 每条 init `success=False`、无初始穿透、sha 对账 |
| C3 | **可解性** | 脚本 oracle 在预算内 ≥3/3 成功 |
| C4 | **可复原性** | 撤销后脚本 oracle（状态写回）能在预算内把关系恢复为真 |
| C5 | 非退化 | 合取目标 ≠ 任一单目标；两目标可区分 |
| C6 | 负对照 | `C0` 必须成功；`infeasible` 方向 SR=0；`probe` 不虚假修复 |
| C7 | **GT 记录** | 每次 check 写 `gt_atoms_raw`；episode 结束时**追加终点 GT 快照**（修掉旧 runner“终点 GT 恒为假”的缺陷） |
| C8 | 成本 | `s/episode`、`GPU-h/模型`、`$` |

> **C3/C4 是整篇工作的生死线**：没有可解性/可复原性证书，4% 或 8.8% 无法区分“模型不行”与“任务不可解/不可修”。

### 5.2 逐 case 验收（B / D）

每条 case 在一次真实 episode 中必须同时满足：

| 检查 | 判据 |
|---|---|
| `baseline_task_solvable` | 同任务在 A/基线协议下可成功（同模型同协议） |
| `completed_relation_true_before_intervention` | 触发时目标关系为真（来自 GT，不是历史账本） |
| `relation_false_after_intervention` | `L0/L1/L2` 注入后关系为假；`C0` 相反，必须仍为真 |
| `no_object_penetration` | 物体-场景侵入 ≤ **1 cm**（初始 resting contact 常见 ~8 mm） |
| `zero_velocity_after_intervention` | 注入后物体线/角速度归零 |
| `object_released` | 两指间距 > 1 cm（机器人已松开） |
| `restorable` | 状态写回 oracle 能在 repair window 内恢复关系（只证明“几何上能修”） |
| 几何量已记录 | `Δtranslation_m`、`Δangle_rad`、`axis` |

D 额外要求：`s1_reachable`（基线下第一个子目标可达成）、`event_fires_reproducibly`（同一轨迹 `trigger_step` 偏差 ≤1 步）、`s2_undisturbed_by_injection`（注入不得连带破坏后序进度）、`trigger_rate` 已实测。

### 5.3 负对照（三处）

1. **`C0` no-op 对照**：每任务 1 条，延迟但不改状态，**必须成功**；
2. **不可解/冲突方向**：`class ∈ {conflict, degenerate, infeasible}` 预期 **SR = 0**，不进入执行主表；
3. **`probe` 假阳性对照**：关系可能仍为真 → 模型若“修复”即假阳性，必须被单独分类。

### 5.4 reference case 与单轴扰动

每个 case 必须有一个 `reference_case`：**同模型、同协议下可解**的单任务锚点，且两者只差**一个因子**。分析报 `Retention = SR_case / SR_ref`，不报裸 SR。这是跨模型可比性的前提。

---

## 6. 评测协议

### 6.1 模型 roster 与筛选顺序

候选池（≥2 家族、优先公开 checkpoint）：**π0.5、OpenVLA-OFT、π0、SmolVLA 0.45B**（可选 X-VLA、GR00T N1.5）。名册**先筛后评**：

```
① A（40 任务 × 1 init）              → 剔除单任务都不行的模型
② C（160 结构 × 1 init，≈7 GPU-h）   → 算 PP，得到能力分层
③ 选 PP > 0 的 4–6 个模型进入 B / D
④ 报告筛选过程与被筛掉的模型（附 PP 与 zero-progress 率）
```

能力分层：**L0 零进展**（PP≈0，D 记 `N/A`）→ **L1 one-and-done**（PP≈0.9，D 正常评测）→ **L2 可组合**（PP≈1.0）。`N/A` 是“该模型不具备（部分）组合能力”的结论，不是基准的缺陷。

实测锚点（前序仓）：π0.5 单任务 **37/40–40/40**（两套协议不同，均带协议脚注）、SmolVLA **19/40**、OpenVLA-OFT **33/40**；π0.5 在合取下 one-and-done ≈88–94%，SmolVLA 在纯 VLA 合取下**零进展**。

### 6.2 协议参数（主表口径）

| 项 | 值 | 说明 |
|---|---|---|
| 成功判定 | 环境 `check_success()` + GT 谓词 trace | 禁止 VLM 判官 |
| `max_steps` | A/C：600；B：600 活跃步 + **300 repair window**；D-native：800；D-compose：600 | 注入后追加修复窗口，不挤占总预算；逐 episode 记录 `repair_budget_steps` |
| `replan_steps` | 10 | 与 `delay_steps=10` 对齐，避免同一动作块内触发 |
| `delay_steps` | 10（B） | 任务完成后延迟 |
| `init_row` | 0（主表）；0–4（variance 子集） | 每个数字注明 init 数 |
| `seed` | 0（主表）；另做 20 任务 × 5 重复估 run-to-run 方差 | 动作采样是随机的，必须报告 |
| `camera` / `settle` | 256 / 10 | 渲染设置随 run manifest pin |
| 指令 | 与 init 绑定，逐字入 manifest；措辞为 `instruction_variant` | 不新建任务 |
| pin | 模型 commit / ckpt sha / replan / wait / 渲染设置 / LIBERO commit | 复现所需全部可查 |

### 6.3 运行产物与断点续跑

每个 run 目录都是自描述证据（失败也写 `status=failed` + 错误 + 最小复现命令）：

```
<output>/
├── run-manifest.json      # 默认参数 + argv + 环境摘要
├── matrix.json            # 矩阵摘要（cases / tasks / by_suite / by_level）
├── plan.json              # dry-run 计划（不是证据）
├── episodes.jsonl         # 一行一个 case summary（追加写）
├── run-summary.json       # 运行级汇总（Recovery / C0 / trigger rate / 成本）
├── report.md / report/    # 自包含 HTML + aggregate.json
└── <suite>/<task_id>/<case_id>/seed-<n>/
    ├── status.json        # ok | failed | invalid_perturbation（+ error + repro cmd）
    ├── results.json       # success / steps / first_hit / GT 谓词 trace
    ├── summary.json
    ├── trace.jsonl        # episode_start / trigger / injection / step / episode_end（含终点 GT 快照）
    ├── provenance.json    # 本仓 git sha + LIBERO commit/worktree + asset digest + 模型 ckpt sha + pip freeze + env
    └── video.mp4          # H.264 / yuv420p / faststart（含 1 s 注入决策卡，20 fps）
```

- **断点续跑**：同一 `--output` 重跑时，`status=ok` 的 case 自动跳过；错误/非法 case 分别 `--retry-errors` / `--retry-invalid`。
- **分片**：`--shard-index/--shard-count`；`--dry-run` 只写 `plan.json`，**不得当作评测证据**。
- **聚合口径**：`Recovery = recovered / recoverable_valid`（排除 C0 与无效注入）；`control_rate = control_ok / controls`；C0 的 `recovery` 置 `None`。
- **任务身份用字符串**：`<suite>/<bddl_stem>`（如 `libero_10/KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it`），**不用整数 task index**（LIBERO 派生变体的注册表下标不可移植）。

### 6.4 leaderboard 提交格式

- 每个 case 一行 JSONL（`run-result.v1`：`case_id`、`dataset_version`、模型/ckpt、seed、`trigger_status`、`injection_valid`、`relation_after`、`recovery`、`cost`）；
- 附一个 `aggregate.json`（按 suite/level 的分子分母 + Wilson CI + 环境指纹）；
- 提交必须能通过 `libero-rollback leaderboard validate`，且**不得缺失分母**（`N/A` 也要显式提交）。

---

## 7. 仓库结构

```text
libero-rollback/
├── README.md
├── pyproject.toml                 # 核心依赖只有 PyYAML + jsonschema；runner 依赖在 extra
├── requirements-sim.lock.txt      # 仿真环境 pin（numpy / robosuite / mujoco / bddl / gym）
├── .env.example                   # LIBERO_HOME / LIBERO_CONFIG_PATH / MUJOCO_GL 模板
├── LICENSE / THIRD_PARTY_NOTICES
├── dataset/
│   ├── matrices/                  # a-matrix.csv / b-matrix.csv / c-matrix.csv / d-matrix.csv（唯一机器可读来源）
│   ├── compose/                   # C 套件：bddl/ + pruned_init/ + metadata.jsonl + 数据卡（自包含）
│   ├── cases/                     # B/D 的 case 定义与兼容性 YAML（如需要，CSV 为权威）
│   ├── sources.yaml               # 来源、上游 LIBERO commit、逐文件 sha256
│   ├── manifest.yaml              # 计数、sha256、evaluation_split、生成命令
│   └── lite/                      # 30 条冒烟子集清单
├── src/libero_rollback/
│   ├── cli.py                     # list / validate / run / report / leaderboard / repro
│   ├── matrices.py                # 矩阵加载、校验、选择、分片
│   ├── schema.py                  # case / metadata JSON Schema
│   ├── validation.py              # 静态校验 + 覆盖证明 + 路径卫生
│   ├── evidence.py                # 判定器（结果分类、分母口径）
│   ├── runtime/
│   │   ├── env.py                 # OffScreenRenderEnv 封装（只依赖上游 LIBERO）
│   │   ├── perturbation.py        # C0/L0/L1/L2 注入 + 几何量 + restorable oracle
│   │   ├── triggers.py            # all_done / early-mid-later（GT 谓词，无外部 profile）
│   │   └── trace.py               # GT atoms、逐步 trace、终点快照
│   ├── policies/                  # Policy 协议 + π0.5 / OpenVLA-OFT / SmolVLA / π0 适配器
│   ├── runner.py                  # 四态 runner（intact/revoke/control/probe）、续跑、分片
│   ├── metrics.py                 # SR / Recovery / EGC / PP / Retention / 统计
│   └── report.py                  # 自包含 HTML + aggregate.json
├── scripts/                       # bootstrap_libero.py、verify_libero.py、setup_env.py、build_*.py、run.py、report.py、repro.py
├── assets/
│   ├── libero.lock.yaml           # 上游 commit + clean_worktree + 仿真栈版本
│   └── manifest.yaml              # bddl/init 文件数与 sha256（只存校验和，不入库大文件）
├── configs/
│   ├── models.yaml                # 模型注册表：adapter / python / checkpoint / 采样参数
│   ├── protocol.yaml              # 预算/延迟/init/seed/camera
│   └── envs/                      # 每模型环境锁（仿 libero-plus 的 per-model env）
├── docs/
│   ├── SPEC.md                    # 数据规范（唯一权威）
│   ├── protocol.md                # 评测协议
│   ├── datasheet.md               # 数据卡（8 张证书 + 已知限制）
│   ├── attribution.md             # 与前序仓的关系、来源与致谢
│   └── implementation-status.md   # 实现进度（本文 §0 的详细版）
├── tests/                         # pytest：schema、矩阵、注入几何、证据口径、报告契约
├── examples/                      # 最小复现 notebook / 提交示例
├── .cache/                        # LIBERO_CONFIG_PATH（gitignored，绝不写 ~/.libero）
└── runs/                          # 运行产物（gitignored）
```

### 7.1 三层依赖隔离（必须保持）

| 层 | 能 import 什么 | 用途 |
|---|---|---|
| 数据工具（生成器 / 校验器） | **仅 stdlib**（+ YAML/JSON） | 可离线、可 `--check` 重建、CI 快速通过 |
| 矩阵 / 证据层 | PyYAML、jsonschema（+ numpy 可选） | 校验、判定、报告 |
| Runner / 适配器 | LIBERO（上游）、MuJoCo、模型框架 | 只在评测环境中安装 |

**禁止**：`import libero_rollback`（前序数据仓）、`import libero_compose`、`import libero_runtime`；`dataset/` 内不得出现绝对主机路径或前序仓引用（CI 检查）。

### 7.2 迁移映射（copy 后重写，不保留运行期依赖）

| 本仓模块 | 来源 | 处理 |
|---|---|---|
| `schema.py`、`validation.py`、`evidence.py` | `libero-rollback`：`schemas/`、`src/libero_rollback/{validation,evidence,success_window}.py` | 拷 schema 契约与判定语义，重写为 v2 口径 |
| `dataset/cases/`、`templates/coverage/manifest` 结构 | `libero-rollback`：`dataset/current/` | 借鉴结构；不沿用 2,112 条旧 case |
| `perturbation.py` | `libero-compose`：`libero_compose/benchmark/perturbation.py` | 重写（保留 C0/L0/L1/L2 语义与门控） |
| `matrices.py`、`runner.py` | `libero-compose`：`benchmark/b_matrix.py`、`scripts/run_b_matrix.py` | 重写并扩展到 A/C/D |
| `policies/*` | `libero-compose`：`harness/{pi05,smolvla,openvla_oft}_policy.py` | 保留 `reset_episode/predict_chunk` 协议，去掉 harness 依赖 |
| `report.py` | `libero-compose`：`scripts/build_b_report.py` + `docs/report-template/` | 重写为数据契约驱动 |
| `dataset/matrices/b-matrix.csv`、`d-matrix.csv` | `libero-compose`：`dataset/case-matrices/` | 按本仓命名/id 重新生成 |
| `dataset/compose/` | `libero-compose`：`dataset/libero-{goal,object,90}-compose/` | copy 必要 BDDL/init/metadata，重新生成 manifest |
| `dataset/cases/`（历史证据） | `libero-rollback`：2,112 条 catalog | 只作 evidence 参考，不进 v2 主表 |

---

## 8. 安装与快速开始

> **三类环境，三种职责，不要合并**：
> ① **本仓环境**（CPU，轻依赖）：静态校验、矩阵/证据、报告；
> ② **仿真环境**（LIBERO + MuJoCo/robosuite）：环境冒烟、注入有效性、可解性/可复原性 oracle；
> ③ **每个模型一个独立 env**：跑推理，由 runner 以子进程调用。
> 模型权重与 LIBERO 资产**不入库**，仓库只保存 pin、校验和与配置，保证“换一台机器只改路径、不改代码”。

### 8.1 原始 LIBERO 资产（唯一外部依赖）

本仓依赖的**唯一**数据源是上游 [LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO)（MIT），**不依赖任何 LIBERO 派生数据集**：

```bash
git clone https://github.com/Lifelong-Robot-Learning/LIBERO "$LIBERO_HOME"
git -C "$LIBERO_HOME" checkout f78abd68ee283de9f9be3c8f7e2a9ad60246e95c
```

| 资产 | 相对路径 | 体积 | 必需 |
|---|---|---|---:|
| BDDL 任务定义 | `libero/libero/bddl_files/<suite>/`（130 个 `.bddl` + `tasks_info.txt`） | ~1 MB | ✅ |
| 官方 init 状态 | `libero/libero/init_files/<suite>/*.pruned_init`（`torch.save` zip；torch≥2.6 读取需 `weights_only=False`） | ~13 MB | ✅ |
| 场景/网格/纹理 | `libero/libero/assets/` | ~3.1 GB | ✅ |
| 演示数据 `datasets/` | — | GB–TB | ❌（只用于训练） |

**三层 pin，缺一不可**：

1. **代码 pin**：`assets/libero.lock.yaml` 固定 commit `f78abd68…`，并要求 **clean worktree**；
2. **内容 pin**：`assets/manifest.yaml` 记录 bddl/init 文件数、逐文件 sha256、suite digest；
3. **运行时校验**：`scripts/verify_libero.py` 校验 commit / clean / 文件数 / digest / `robosuite`·`mujoco`·`bddl` 版本，**不匹配直接失败**；每个 run 写 `provenance.json`。

```bash
export LIBERO_HOME=/path/to/LIBERO
export LIBERO_CONFIG_PATH=$PWD/.cache/libero   # 仓库内；绝不使用 ~/.libero
python scripts/bootstrap_libero.py --libero-home "$LIBERO_HOME" --out "$LIBERO_CONFIG_PATH"
python scripts/verify_libero.py --libero-home "$LIBERO_HOME"
```

> **为什么不能只 pin commit**：`libero` 在 import 时读取 `$LIBERO_CONFIG_PATH/config.yaml`，缺省会**交互式提问**（CI/子进程会卡住）；而同一 commit 的 checkout 也可能被其它 LIBERO 变体打过补丁（本机就有一个“commit 对、工作区脏”的例子）。因此本仓采用 **repo-local config + clean-worktree + sha256** 三保险，并显式拒绝 `~/.libero` 全局配置。
> `config.yaml` 只需五个键：`benchmark_root`、`bddl_files`、`init_states`、`datasets`、`assets`。

### 8.2 仿真环境（LIBERO + MuJoCo）

```bash
uv venv --python 3.11 .venv-sim
uv pip install --python .venv-sim/bin/python -r requirements-sim.lock.txt
# 冻结前 smoke 验证的 pin：numpy==1.26.4, robosuite==1.4.0, mujoco==3.8.0, bddl==3.6.0, gym==0.25.2
export MUJOCO_GL=egl                                # 无 GPU / CI 用 osmesa
.venv-sim/bin/python scripts/smoke_env.py --tasks libero_10
```

**不要**把模型环境与仿真环境合并：runner 通过**子进程**调用模型 env 的解释器（`--model-python` / `configs/models.yaml`），并显式重建环境变量（`PYTHONPATH`、`MUJOCO_GL`、`XLA_FLAGS`），避免“哪个 env 的 libero 生效”这类隐式耦合。

### 8.3 本仓核心环境（CPU）

需要 Python 3.11+ 与 [uv](https://docs.astral.sh/uv/)（以下命令按 Linux 书写；Windows 对应 `.venv\Scripts\python.exe`）。

```bash
uv sync --extra dev            # 核心：pyyaml + jsonschema；dev：pytest + ruff
uv run libero-rollback list --suite all
uv run libero-rollback validate --dataset dataset        # 纯静态校验，不启动仿真
uv run pytest && uv run ruff check .
```

### 8.4 模型环境（每模型一个，仿 libero-plus）

| model id | 解释器（示例） | checkpoint（只记录不下载） | 备注 |
|---|---|---|---|
| `pi05` / `pi0` / `pi0_fast` | `openpi/.venv/bin/python`（Py3.11, JAX） | `~/.cache/openpi/openpi-assets/checkpoints/{pi05,pi0,pi0_fast}_libero` | action chunk 10；需 `XLA_FLAGS=--xla_gpu_deterministic_ops` |
| `openvla_oft` | `openvla-oft-env/bin/python`（Py3.10, torch 2.2.0） | `models/openvla-7b-oft-finetuned-libero-spatial-object-goal-10` | `center_crop=True`，`unnorm_key` 随 suite 变化，horizon 8 |
| `smolvla` | 独立 LeRobot env（Py3.11+） | `models/smolvla_libero` | 0.45B 轻量模型，零进展对照 |

```bash
# 注册表驱动；脚本与配置里不写死 /home/...
bash scripts/setup_env.sh pi05 \
  --openpi-root /path/to/openpi \
  --checkpoint  /path/to/pi05_libero
# → .venvs/pi05/ + configs/envs/pi05.lock，并在 configs/models.yaml 记录 checkpoint 与采样参数
```

**adapter 契约**（继承现有事实标准；runner 只依赖这两个方法）：

```python
class PolicyAdapter(Protocol):
    def reset_episode(self, seed: int) -> None: ...
    def predict_chunk(self, obs: dict, instruction: str) -> np.ndarray:  # (T, 7)
        ...
```

- **adapter 负责**：图像翻转/缩放/中心裁剪、proprio 拼接、quat→axis-angle、动作维度裁剪（如 32→7）、采样种子与确定性；
- **runner 负责**：episode 循环、四态注入、成功判定、trace/视频、结果落盘；
- 新增模型 = 建 env → 在 `configs/models.yaml` 注册 → 实现 adapter → 通过 `--dry-run` warmup 自检（加载模型并前向一次，不跑 episode）。

### 8.5 跑评测（接口草案）

```bash
# 0) dry-run 先数 episode（dry-run 只校验计划，不是证据）
uv run libero-rollback run --matrix dataset/matrices/b-matrix.csv --dry-run

# 1) 冒烟：lite 30 条（< 1 GPU-h）
bash scripts/run.sh --model pi05 --split lite --output runs/lite-pi05

# 2) 主套件（可断点续跑 / 分片）
bash scripts/run.sh --model pi05 --split core --suites b d --output runs/core-pi05 --video
bash scripts/run.sh --model pi05 --split core --shard-index 0 --shard-count 2 --output runs/core-pi05

# 3) 报告（自包含 HTML + aggregate.json）
uv run libero-rollback report --run runs/core-pi05 --out runs/core-pi05/report

# 4) 复现与提交
bash scripts/repro.sh --model pi05 --split lite        # 一条命令重建 lite 结果
uv run libero-rollback leaderboard validate --run runs/core-pi05
```

### 8.6 成本（估算，单模型）

| split | episodes | GPU-h |
|---|---:|---:|
| `lite` | 30 | < 1 |
| A（40 case，1 init） | 40 | ≈ 2 |
| A 上界（40 任务 × 10 init，独立报告） | 400 | ≈ 17 |
| B | 442 | ≈ 15–22 |
| C | 160 | ≈ 7 |
| D | 549 | ≈ 18–23 |
| **`core` 合计（主表）** | **1,191** | **≈ 45–55** |
| variance + restate（补充） | ≈ 600 | ≈ 22–28 |
| **完整 leaderboard 条目** | **≈ 1,800** | **≈ 68–83** |

> 一个完整 leaderboard 条目约 **1 GPU-day/模型**；B 实测均值约 180 s/case（含视频，π0.5，2026-11-18 快照）。该数字随模型与视频开关变化，报告时必须带协议。

---

## 9. 数据与资产

### 9.1 数据发布物

| 项 | 要求 |
|---|---|
| 矩阵 | `dataset/matrices/*.csv`：每行一个 case，列契约在 `docs/SPEC.md`；CSV 是**唯一机器可读来源** |
| C 套件 | `bddl/<task>.bddl` + sibling `<task>.pruned_init`（成对、无 strays）+ `metadata.jsonl` |
| 清单 | `manifest.yaml`：版本、计数、逐文件 sha256、suite digest、生成命令、`evaluation_split` |
| 覆盖证明 | 每场景：候选总数、各分类计数、valid 数、排除原因分布；**所有候选都被归类且加总一致** |
| 生成器 | 纯 stdlib、`--check` 可重建、与冻结产物 0 diff |
| 数据卡 | 已知偏差/限制、证书状态、口径变更历史（`docs/datasheet.md`） |
| 自包含 | `dataset/` 内 0 个绝对路径 / 0 处前序仓引用；只用 `LIBERO_HOME` 占位（由 bootstrap 生成 config） |

### 9.2 版本纪律

- **数据集版本**（`v2.x`）与 **case_id 语义**发布后不可静默变更；任何数据修改都要走版本号 + manifest sha256。
- 任务身份与指令绑定：同一 `goal_atoms` 的多条措辞写进 `instruction_variants[]`，**不新建任务**。
- 引用时必须同时注明**数据集版本 + case_id**；leaderboard 提交绑定 dataset digest 与模型 ckpt sha。

### 9.3 已知数据债务（必须写进数据卡，发布前逐条解决或标注）

1. **B 含 LIBERO-10（n=2）子集**：B 的 40 任务中含 10 个原生多目标任务，使“n=1”与“n=2”在 B 内部混合。处理：按 suite 分列报告；B(l10) 与 D-native 的 `pending` 对照单独成表，不与 n=1 混算。
2. **A 的四套件含 LIBERO-10**：A(Obj/Goal/Spatial) 是严格 n=1 锚点，A(l10) 是 n=2 参照；报告时分开。
3. **B 的 `max_steps` 口径**：来源实现为 600 总步（注入越晚修复预算越短）；本仓 v2 改为“600 活跃步 + 300 修复窗口”，并记录 `repair_budget_steps`。两套口径不得混表。
4. **`both` 撤销不彻底**：LIBERO-10 部分任务有 3 个目标原子（含 `Turnon` 类隐含前置），`both` 撤销后可能仍有一个原子为真；必须在 `notes` 标注。
5. **`valid` 是构造层判断**：不等于物理已验证；数据卡必须区分 “construction-level valid” 与 “physically verified”。
6. **窗口触发率**：D 的触发率是实测值；某窗口在某模型上不可达时按 `N/A` 处理，并从主表剔除原因而非删 case。
7. **编码**：全部数据与 metadata 统一 UTF-8；CI 校验编码与无 BOM。
8. **`task_idx` 不是 0–9 重编号**：导入矩阵沿用来源仓的 LIBERO 全局任务下标（goal 0–270 等），与 SPEC 早期草稿的“0–9 稳定编号”不同；A/B/D 已统一到导入矩阵的映射。发布前冻结此口径，不再重编号（重编号会改 case_id）。
9. **D-native 的 `trigger_criterion` 是旧标签**：导入矩阵保留来源仓的 `s1 first true` / `s2 displacement > 5 cm` / `distance to s2 goal < 8 cm` / `no injection`；其中 5 cm / 8 cm 几何判据已作废，M2 必须映射到 GT 事件名（`enter_first_subgoal_completed` / `enter_next_subgoal_lift` / `enter_next_subgoal_preplacement`），不得复用旧阈值。
10. **C 与 D-compose 未构建**：`c=0`，D-compose 360 行只是设计占位（`<from C>` 字面量）；所有 `EGC`/`PP`/A↔C 结论留到 Phase 2，发布前不得引用。

### 9.4 资产依赖与可复现 pin

- **唯一数据源**：上游 LIBERO 的 `bddl_files` / `init_files` / `assets` 三件套；**不引入新物体、新场景、新纹理**。
- **只读**：`LIBERO_HOME` 指向 clean checkout；本仓不修改上游代码，也不把 3.1 GB 资产拷进仓库。
- **三层 pin**：`assets/libero.lock.yaml`（commit + clean_worktree + 仿真栈版本）→ `assets/manifest.yaml`（逐文件 sha256 + suite digest）→ `verify_libero.py`（运行前硬失败）。
- **配置隔离**：`LIBERO_CONFIG_PATH` 指向仓库内 `.cache/libero`，**绝不写 `~/.libero`**（否则与本机其它 LIBERO 变体互相污染）。
- **run 级 provenance**：每个 run 记录本仓 git sha、LIBERO commit、worktree 是否 clean、asset digest、模型 ckpt sha、pip freeze 摘要、`MUJOCO_GL` / `CUDA_VISIBLE_DEVICES` / `XLA_FLAGS` 与完整命令行。
- **渲染设置**：camera 分辨率、`settle_steps`、视频编码参数随 run manifest pin。
- **C 套件是唯一派生数据**：BDDL + sibling `.pruned_init` 由纯 stdlib 生成器在本仓生成/重建，逐字节可审计。

---

## 10. 与前序仓的关系（Provenance）

### 10.1 来源与致谢

本仓的数据设计、case 语义、注入协议与报告契约在以下两个内部仓中孵化，v2.0 将其**必要代码与数据 copy 进来并重写实现层**：

| 前序仓 | 贡献 | 本仓处置 |
|---|---|---|
| `libero-rollback` | case schema、validity/evidence 判定、catalog/coverage/manifest 结构、`restore_*` 机制族、严格恢复率口径 | 拷 schema 与判定语义；不拷 2,112 条旧 case、不拷 runtime overlay |
| `libero-compose` | composition 数据生成、B/D case 矩阵、C0/L0/L1/L2 注入实现、runner/trace/video、报告契约 | 拷矩阵与协议；重写 runner 与 D 轴窗口检测 |
| `libero-plus` | 模型环境与资产组织方式（per-model env、资产 pin、models 目录） | 只借鉴组织方式，不依赖其代码 |

### 10.2 独立性约束（CI 强制）

- 运行期**不得** import / 路径引用 `libero_rollback`、`libero_compose`、`libero_runtime`；
- 不得依赖前序仓的 `runs/`、overlay、runtime profile、历史产物；
- 唯一外部 Python/资产依赖 = 上游 LIBERO（+ 各模型框架，在独立 env 中）。

### 10.3 v1 与 v2 不混表

前序仓的历史数字（40/40、2/49、0/76、42/477、2,112 case 等）属于 **v1 口径**，只作现象证据与本 README 的动机引用；**不得与本仓 v2 的主表混排**。v2 发布后，主表只报 v2 数字，或在明确标注的两列中并列。

---

## 11. 与相关工作的分工

| 工作 | 扰动的对象 | 本仓的差异 |
|---|---|---|
| LIBERO-Plus / PRO / MAX | **输入分布**（视角/噪声/光照/障碍/目标移动） | 本仓分布完全不动，只动任务结构；失败可归因到结构 |
| LiLo-VLA（Long++ / Ultra） | 技能顺序，21 个策划配置 | 他们**观察到**崩塌；本仓提供测量协议 + 对照 + 证书，且不限少量配置 |
| PACE / LIBERO-Gen | 目标链/空间组合，方法论文 | 他们报方法增益；本仓做枚举 + 证书 + 跨模型标量 |
| RoboCasa365 | 规模 + 新资产 + 移动底盘 | 本仓零新资产、单卡可复现、成本表可查 |
| LIBERO 原版 | 固定任务集 | 本仓不改 LIBERO 任务语义，只增加“撤销”这一因果因子 |

必读的一句主动认账：**“我们不是第一个观察到状态敏感性/顺序敏感性的工作；我们把它变成一个可控、可枚举、有证书的测量。”**

---

## 12. 局限与范围

- **仿真-only**：不宣称 sim-to-real；跨模拟器复现是 Stage 2 计划项。
- **冻结策略**：不评价训练方法，只测量推理时能力；不主张方法贡献。
- **LIBERO 资产**：物体/技能在分布内；异构分布外结论不适用。
- **适用性筛选**：D 对零进展模型记 `N/A`，这是结论而非缺陷；名册必须报告筛选过程。
- **构造层 valid ≠ 物理已验证**：数据卡区分两者；C3/C4 证书未完成前，主表不得发布。

---

## 13. 路线图

| 里程碑 | 内容 | 完成判据 |
|---|---|---|
| **M0 规范冻结** | 本 README + `docs/SPEC.md` + 协议/指标/证书/数据卡模板 | 评审可据此实现，无未定义口径 |
| **M1 数据迁移** | 四套件矩阵 + C 套件数据 + manifest/覆盖证明 + 证书 C1/C2/C5/C7 | `validate --dataset` PASS + 0 diff 重建 |
| **M2 Runner 与适配器** | 四态 runner、A/B/C/D 全链路、π0.5/OpenVLA-OFT/SmolVLA/π0 适配器、lite 复现 | lite 30 条跑通，报告可生成 |
| **M3 主 sweep 与发布** | core 全量 + variance 子集 + leaderboard + 数据卡 + `pip`/HF 发布 | 一条 `repro` 命令 < 1 GPU-h；leaderboard 可提交 |
| **M4 扩展** | C3/C4 oracle 全量、重述臂、多 init 方差、n≥3 阶梯、跨模拟器 | Stage 2 实验清单 |

当前进度：**M0 ✅**（README + `docs/SPEC.md` + 协议冻结）、**M1 ✅（Phase 1：A/B/D-native 数据 + 契约层 + 静态证书）**、**M2 🟡**（B 运行层已移植，dry-run 与 fake-env 测试通过，未在真实仿真/模型上验证）。C/D-compose 数据与 D runner 进入 M1 第二阶段。**Stage 1 只需要现有 B 全量 + D-native**；Stage 2 再冻结 v2.0 主表并跑全模型 sweep。

---

## 14. 引用与许可

### 14.1 引用

论文准备中；在正式引用条目发布前，请引用本仓版本与本 README 的基准名：

```bibtex
@misc{libero_rollback_2026,
  title        = {LIBERO-Rollback: A Controlled-Perturbation Benchmark for
                  Goal-State Persistence in Vision-Language-Action Policies},
  author       = {{LIBERO-Rollback Team}},
  year         = {2026},
  howpublished = {\url{https://github.com/<owner>/libero-rollback}},
  note         = {Benchmark v2.0, in preparation}
}
```

LIBERO 原始工作：

```bibtex
@article{liu2023libero,
  title   = {LIBERO: Benchmarking Knowledge Transfer for Lifelong Robot Learning},
  author  = {Liu, Bo and Liu, Yifeng and Liang, Xiaolong and Cai, Weidong and
             Guo, Jian and Xiong, Zhendong and Yuan, Yuan and others},
  journal = {arXiv preprint arXiv:2306.03310},
  year    = {2023}
}
```

### 14.2 许可

- **代码**：MIT（拟；发布前补 `LICENSE`）。
- **数据**：C 套件为在本仓生成的派生定义；底层 LIBERO 资产为 MIT，来源与修改说明写入 `THIRD_PARTY_NOTICES`。
- **模型权重**：不随本仓分发；遵守各模型原始许可。

---

## 15. 术语表（Glossary）

| 中文 | English | 定义 |
|---|---|---|
| 完成边界回滚 | completion-boundary rollback | 任务全部 native goal 为真后 delay 10 步注入撤销 |
| 执行中撤销 | in-execution rollback | 在 `early/mid/later` 窗口撤销已完成子任务 |
| 条件恢复率 | conditional recovery rate | 条件于“撤销前关系为真且注入有效”的分母 |
| 联合成功率 | joint success rate (SR) | 全部目标同时为真的成功率 |
| 有效目标容量 | Effective Goal Capacity (EGC) | `Σₙ SR(n)`，平均能同时达成的谓词数 |
| 一个就停 | one-and-done | 失败中恰好完成 1 个子目标的占比 |
| 零进展 | zero-progress | 一个子目标都没完成 |
| 部分进度 | partial progress (PP) | `P(≥1 子任务达成)` |
| 参照 case | reference case | 同协议、只差一个因子的可解锚点 |
| 保留率 | Retention | `SR_case / SR_ref` |
| 可解性 / 可复原性证书 | solvability / restorability certificate | 脚本 oracle ≥3/3；撤销后状态写回可复原 |
| 无操作对照 | no-op control (C0) | 同 delay / 窗口但不动状态 |
| 注入 | injection | 直接写 MuJoCo `qpos/qvel` 并 `mj_forward` |
| 触发率 | trigger rate | 各窗口实际触发比例 |
| 察觉延迟 | notice latency | 撤销 → 首次朝被撤销物体移动的步数 |
| 重述对照臂 | restate arm | 撤销后重发原指令，测自觉性缺口 |
| 能力 vs 自觉 | capability vs compliance | 会做 vs 知道要做 |
| 窗口 | window | `early` / `mid` / `later` |
| 结构 | structure | 同场景两任务目标并集 + 共享初始状态 |
| 覆盖证明 | completeness certificate | 所有候选被归类且加总一致 |

---

## 维护约定

- 本 README 与 `docs/SPEC.md` 冲突时，以 `docs/SPEC.md` 为准（本文件随其同步更新）。
- 任何数字进 README 前必须带**协议脚注**（模型、init 数、预算、CI）；v1/v2 不混表。
- 任何“已完成”声明必须可在 CI 或一条命令中复现；未实现项保持 ⬜ 并写入 `docs/implementation-status.md`。
- 设计变更须同时更新：矩阵 CSV → `manifest.yaml` → 数据卡 → 本 README 的口径表。
