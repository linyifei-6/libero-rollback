# LIBERO 系 benchmark：任务规模与 case 规模（含我们的 libero-rollback）

**一句话结论**：LIBERO 是 130 个任务的基线；LIBERO-Plus / LIBERO-PRO / LIBERO-MAX 都只沿用 LIBERO 的 4 个标准评测套件（共 **40 个参考任务**），任务数不再增长，规模增长来自“静态扰动 → 多轴扰动 → 执行中动态事件”，把单模型评测从约 2,000 次 rollout 放大到 1 万～1.6 万次（MAX 全量 14 个策略合计 22.4 万次）。**本仓库的 libero-rollback 走的是相反路线**：任务收窄到 LIBERO-10 单套件（**10 个任务**），但把测试集做成 **524 条“已完成关系被撤销”的语义回滚定义**——单模型全量仅 **524 次 rollout**（≈ LIBERO-10 单套件标准评测的 500 次量级），是五者中规模最小、但唯一覆盖“执行中语义回滚 / 恢复”维度的测试集。

**口径说明**：
- **任务规模（task scale）** = 不同任务定义的数量；
- **case 规模** = 实际评测实例数 = 任务 × 扰动配置 × 重复次数；
- **rollout 规模** = 单模型实际执行的 episode 数 = case × 每 case 重复次数（MAX 还要 × Base/Dynamic 两臂；libero-rollback 另加每任务 1 条配对 baseline）；
- **libero-rollback 的 case 规模 = 定义级**（524 条 YAML 定义，不等于物理验收通过数或累计运行次数），见第 5 节。

---

## 总览

| Benchmark | 时间 / 出处 | 任务规模（独立任务） | case 规模（定义数） | 每 case 重复 | 单模型评测 rollout |
|---|---|---|---|---|---|
| **LIBERO** | 2023，NeurIPS 2023 D&B | **130**（4 个套件） | 130 个任务 × 固定初始状态 | 50 次/任务（原 lifelong 代码默认 20） | **2,000**（4 套件×10 任务×50）；代码默认 800 |
| **LIBERO-Plus** | 2025.10 arXiv；CVPR 2026 | **40** 基础任务 | **10,030** 个扰动任务实例 | 1 次/实例 | **10,030** |
| **LIBERO-PRO** | 2025.10 arXiv | **40** 基础任务 | 约 **200** 个扰动配置（论文未公布总数） | 50 次/任务 | 约 **12,000**（2,000 原始 + 10,000 扰动） |
| **LIBERO-MAX** | 2026.09 arXiv（NeurIPS'26 WAM Workshop oral） | **40** 参考任务 | **8,000** 个 Base/Dynamic 配对 case | 1 对（Base+Dynamic） | **16,000**；14 个策略合计 **224,000** |
| **libero-rollback（本项目）** | 2026.10，本仓库 [`dataset/current`](../dataset/current/manifest.yaml)（catalog 1.0.0） | **10**（LIBERO-10 单套件） | **524** 条 rollback 场景定义（restore 380 / probe 128 / control 16） | 1 次/定义（单 seed，无重复） | **524**（+10 条任务级 baseline = **534** episodes；14 策略纯 case rollout 合计 **7,336**） |

---

## 1. LIBERO（基线，2023）

| 套件 | 任务数 | 说明 |
|---|---|---|
| LIBERO-Spatial | 10 | 同一组物体，仅空间关系不同 |
| LIBERO-Object | 10 | 每任务一个独特物体 |
| LIBERO-Goal | 10 | 物体/布局固定，仅任务目标不同 |
| LIBERO-100 | 100 | = **LIBERO-90**（90，预训练）+ **LIBERO-Long/LIBERO-10**（10，下游评测） |
| **合计（去重）** | **130** | 每任务 50 条人类遥操作 demo → **6,500 条**（LIBERO-90 占 4,500） |

- **评测协议**：稀疏目标谓词上的成功率；官方随任务提供 **50 个固定初始状态**/任务，主流 VLA 评测沿用 **50 rollouts/任务 → 500/套件 → 四套件共 2,000 次**。原 lifelong 代码里 `n_eval: 20`（20 次/任务，共 800）、`max_steps: 600`、控制频率 20 Hz。
- **测什么**：终身学习/知识迁移（声明性 vs 程序性知识），指标 FWT / NBT / AUC。

## 2. LIBERO-Plus（静态多维度扰动，2025.10 / CVPR 2026）

- **任务底座**：论文明确“从 LIBERO 的 40 个评测任务出发”（4 套件 × 10，**不是 130**）。
- **case 生成**：4 套件 × 7 扰动维度 × 500 候选 = 14,000 → 过滤“天花板效应”并均衡后得 **10,030 个扰动任务实例**（README、论文、manifest 三处一致）。

**按套件**（发布 manifest）与**按维度**（论文 Table 6 与仓库 JSON 完全一致）：

| 套件 | 扰动实例 | | 扰动维度 | 实例数 |
|---|---:|---|---|---:|
| libero_spatial | 2,402 | | Camera Viewpoints（视角） | 1,599 |
| libero_object | 2,518 | | Robot Initial States（初始位姿） | 1,550 |
| libero_goal | 2,591 | | Language Instructions（LLM 改写） | 1,537 |
| libero_10 | 2,519 | | Sensor Noise（模糊/雾/玻璃模糊） | 1,601 |
| **合计** | **10,030** | | Light / Background / Layout | 1,142 / 1,076 / 1,525 |

- **评测**：设 `num_trials_per_task` 从 50 改为 **1**（每个 case 本身就是一个固定扰动配置）→ **单模型 10,030 次 rollout**；10 个基线全部 **zero-shot**（test-only benchmark）。另有 **L1–L5 难度分层**（按 4 个参考模型成功数打标，非训练课程）。
- **训练侧**：另有自动生成的 **>20,000 条**成功轨迹训练集（HF `libero_plus_rlds/lerobot`），OpenVLA-OFT+ mix-SFT 后 Total 达 **79.6%**。
- **典型结果**：原 LIBERO 95%+ → 中度过扰动后 **<30%**。
- 注：CVPR 版本更名 *A Progressive Robustness Benchmark*（pp. 38574–38583）；“56K robustness scenarios”是生成管道（训练+测试）总量，不是测试集。仓库另有 90 个无扰动的 `libero_90` 任务，故任务定义总数为 10,030 + 90 = **10,120**。

## 3. LIBERO-PRO（记忆/公平性压力测试，2025.10）

- **任务底座**：40 个任务（4 标准套件 × 10）。
- **5 类扰动**（论文摘要写“4 个维度”，Fig.6/README 为 5 类，存在措辞不一致）：物体属性（颜色/纹理/尺寸+干扰物）、初始位置（x/y 各 0.1–0.5）、指令（语义改写 + 任务级改写）、任务（换目标/物体集）、环境（背景/光照/纹理）；任务级扰动静止与其他轴组合，其余可自由组合。
- **case 规模**：40 任务 × 5 轴 = **约 200 个扰动配置**（推导值，论文为 0 表格、未公布总数）；榜单口径是每任务 6 个条件（原始 + 5 轴）× **50 episodes** → **约 12,000 次 rollout/模型**（含原始 2,000、扰动 10,000）。位置轴若把 10 档位移全展开，case 数更多。
- **典型结果**：标准 LIBERO >90% → 位置/任务扰动下 **≈0.0%**；pi0.5 在 libero-goal 位置扰动下 0.38，其余模型 0。

## 4. LIBERO-MAX（执行中动态变化，2026.09）

- **case 规模**：**8,000 个配对 case = 8 类事件 × 1,000**；每 case 有 Base（不加事件）与 Dynamic（同一执行前缀后注入一次事件）两条 rollout → **16,000 次/策略**；评测 **14 个** VLA/混合/WAM 策略 → **224,000 次**（中文报道的“22.4 万次仿真”即此乘积）。
- **来源构成**：**5,600** 个来自 LIBERO-Plus 的 7 类 case（800/类）+ **2,400** 个来自 LIBERO-PRO 的 10 类 case（240/类）= 17 个来源类别；任务底座为 4 个 LIBERO 套件的 **40 个参考任务**（case 按套件分布：Object 2,448 / LIBERO-10 2,028 / Spatial 1,868 / Goal 1,656）。
- **8 类事件（4 族，各 1,000 对）**：几何—目标移动、容器移动；观测—相机视角切换、传感器噪声突现；外观/杂物—光照切换、视觉主题切换、干扰物爆发；路径—障碍物插入。
- **协议**：单 seed 195、每臂 1 次；事件在末端执行器首次接近目标 **0.18 m** 时确定性触发（mid-episode）；指标为 Base/Dynamic 成功率、配对差（pp）、条件回退率、覆盖率、四象限配对结果。**Lite 版**：800 对 / 1,600 次，约为全量 1/10。
- **典型结果**：所有策略下降 **11.0–25.7 pp**；Base 成功中 **20.8%–56.1%** 在事件后转为失败。

## 5. libero-rollback（我们的测试集：已完成关系被撤销后的恢复评测，2026-10）

> 本节数字以本仓库 [`dataset/current/manifest.yaml`](../dataset/current/manifest.yaml)（case_count = 524）为权威口径，并由 2026-10-19 的 catalog 审计与评测协议审计逐项复核（审计记录见 `.tmp/scale-audit/`）。仓库内 README / dataset-card / case-matrix 等文档仍停留在 **288 条**时代，引用时一律以 manifest 为准。

### 5.1 是什么、任务规模多大

libero-rollback 不是又一个“任务级 benchmark”，而是叠加在 **LIBERO-10** 上的 **case 级 rollback 诊断集**。每条 case 定义一个可执行场景：在某个触发窗口（early / mid / later / all_done）里，一个**已经为真的子目标关系**被外部事件撤销（位置/区域、关节状态、多关系原子重置等），模型应在**同一个 episode 内**发现并重建已完成进度。仓库只交付定义、schema、coverage、provenance、静态校验器和外部评测桥接，不包含模型、仿真器、恢复算法或训练数据。

- **任务规模：10**。即 LIBERO-10 全部 10 个基础任务（9 个 `documented` + T09 一个 `candidate`），也是 LIBERO 四个标准套件中的 long-horizon 套件。
- 相对四个外部 benchmark：是 LIBERO **130** 个任务的 1/13，是 Plus / PRO / MAX 共用的 **40** 个参考任务的 **1/4**。与它们不同，本测试集**只覆盖 4 个套件中的 LIBERO-10**。
- 任务名、顺序和 BDDL 定义来自 LIBERO-plus 源码的 `libero_10/tasks_info.txt` 与对应 BDDL；任务 ID `libero_10/00`–`09` 固定。

### 5.2 case 规模：524 条定义

**524** 这一数字在 `manifest.case_count`、磁盘上的 524 个 case YAML、`coverage` 十个任务的计数三者之间完全一致（0 缺失、0 孤儿、0 重复 ID，524 个 SHA-256 全部对账通过），`validate-dataset` 与 `check-manifest` 均通过。

| 维度 | 构成 |
|---|---|
| 每任务分布 | T00 12 / T01 59 / T02 53 / T03 63 / T04–T06 各 70 / T07 58 / T08 56 / T09 13；均值 **52.4 条/任务** |
| 语义（期望评测） | **restore 380**（撤销关系后期望恢复）/ **probe 128**（完成位姿探针，关系可能仍真）/ **control 16**（关系保持对照，排除“任意扰动都会失败”） |
| 触发窗口 | mid 223 / later 141 / early 120 / all_done 40 |
| 机制（`state_change.kind`） | schema 枚举 11 种、实际在用 **10 种**：apply_episode_initial_offset 243、displace_from_completed_pose 137、restore_episode_initial_pose 45、displace_reference_object 35、restore_native_relation_set 18、displace_to_relation_boundary 16、restore_container_above_pose 12、revert_articulation_goal 9、translate_relation_pair 5、move_to_relation_target 4 |
| 失效方向（顶层） | 位置/区域、功能状态、姿态、参照物、持续性/重复失效、完成边界、多历史关系（7 个方向） |
| 来源 | 物理目录 4 个：two-subtask 237 / rollback-battery 126 / reference-object 25 / progress-failure 136；provenance 为 8 个 `source_id` |
| 定义状态 | preserved **380** / unreleased candidate **144**（manifest 按 `case_source_id` 机械二分，不等于“已发布”或“已物理验收”） |
| 数据体量 | 524 个 YAML / 1,407,197 B（≈1.34 MiB）/ 36,316 行；另有 11 个模板、13 个 sources、10 个 runtime profile；**无训练 demo / 生成轨迹** |

### 5.3 rollout 规模与评测协议

- **每 case 1 次 rollout、单 seed**（默认 `seed=0`；主全量中 T03/T06/T09 用 seed 1），无重复采样、无多 seed 默认；`max_steps=600`、`replan_steps=10`（20 Hz 控制）。
- 干预在**同一 episode 内**：模型执行到 trigger 时，已完成关系真值被撤销，然后同一 episode 继续自修；**不是**“每个 case 先跑 base、再跑扰动”的两条 rollout。
- 每个任务另有 **1 条任务级配对 baseline**（独立 episode，10 个任务共 10 条），用于门控“基线失败则扰动 episode 不启动”。
- 因此：**单模型全量 = 524 次 case rollout + 10 次任务级 baseline = 534 个仿真 episode**；纯 case rollout 按 MAX 的 14 策略口径折算为 **7,336 次**（不含 baseline）。
- 本地实测成本：pi05 的 518 条主全量（`runs/retest-20261018`）共 528 episodes，benchmark 耗时 **61,197 s ≈ 17.0 h**、**118 s/case**；524 条全量估算 **17–20 h**（单卡、单模型）。

### 5.4 与四个 benchmark 的规模对照

| 维度 | LIBERO | LIBERO-Plus | LIBERO-PRO | LIBERO-MAX | **libero-rollback（本项目）** |
|---|---|---|---|---|---|
| 任务规模 | 130 | 40 | 40 | 40 | **10**（仅 LIBERO-10） |
| case 定义数 | 130 | 10,030 | ~200 配置 | 8,000 配对 | **524** 定义 |
| 每 case 重复 | 50 | 1 | 50 | 1 对（Base+Dynamic） | **1**（单 seed） |
| 单模型 rollout | 2,000 | 10,030 | ~12,000 | 16,000 | **524**（+10 baseline） |
| 单任务 rollout 深度 | 50 | 250.75 | 300 | 400 | **52.4** |
| 相对本测试集 rollout 倍数 | 3.8× | 19.1× | 22.9× | 30.5× | 1× |

> 注：LIBERO 的“单任务 rollout 深度 50”按其主流评测口径 2,000 ÷ 40 个评测任务（4 套件 × 10）计算，LIBERO-90 的 90 个预训练任务不参与该评测协议；Plus / PRO / MAX 均按各自的 40 个参考任务计算。

- **规模位置**：524 次 ≈ LIBERO-10 单套件标准评测（10 任务 × 50 = 500 次）的 **104.8%**；是 LIBERO 全量 2,000 的 **26.2%**、Plus 10,030 的 **5.2%**、PRO 约 12,000 的 **4.4%**、MAX 16,000 的 **3.3%**（也仅为 MAX Lite 1,600 的 32.8%）。按 14 策略的纯 case rollout 合计 7,336 次，是 MAX 224,000 的 3.3%。
- **密度位置**：平均 **52.4 条定义/任务**，与 LIBERO 的 50 次/任务几乎相同——即“用大约一个标准套件的评测成本，换 10 个任务的 52 种语义场景诊断”。case 定义数约为 LIBERO（130）的 4.0 倍、PRO 配置数（~200）的 2.6 倍，但只有 Plus 的 5.2%、MAX 配对 case 的 6.6%。

### 5.5 维度互补性（为什么不是“更小的 MAX”）

- **vs LIBERO-Plus**：Plus 在 **reset 时**做 7 维静态扰动，靠“任务 × 扰动配置”扩张到 10,030 个实例；rollback 的干预发生在**执行中**，且撤销的是**已为真的语义关系**，不是初始状态采样。
- **vs LIBERO-PRO**：PRO 也是 reset 时扰动，用位置/任务等轴揭穿“记忆式”高分；rollback 用 **probe（关系可能仍真）+ control（关系保持真值）** 两类阴性对照和**注入有效性门控**，区分“模型真的修复”与“扰动本身无效”。
- **vs LIBERO-MAX**：MAX 最接近（同为执行中干预），但其 8 类事件是**环境/观测/路径**扰动（相机、光照、噪声、障碍、目标移动），测 Base/Dynamic 配对退化（pp）与回退率；rollback 的事件是**语义状态回滚**（位置/区域、关节、多关系原子重置），测的是“已完成进度被否定后能否重建”，主指标是严格自修恢复率。
- **一句话**：Plus 做“大而全”的静态扰动诊断，PRO 做“小而狠”的记忆性/公平性质疑，MAX 测执行中环境变化下的可靠性，**libero-rollback 补的是“执行中语义回滚 / 恢复”这一维**，四者递进关系之外再加一条互补轴。

### 5.6 本地证据与当前状态

- **主全量实测（pi05，2026-10-18）**：518 条 / 600 步 / 528 episodes；基线成功 518/518，**注入有效 477/518 = 92.1%**，**严格自修恢复 42/477 = 8.8%**，episode 成功（宽松）160/477 = 33.5%，未生效 41 条（33 触发未到达 + 8 注入失败）。
- **新增 6 条用例**：T00 ×2、T07 ×3、T08 ×1，已单独评测（T07/T08 有 600 步证据；T00 ×2 仅 400 步且 `truth_unverified`），均 0 恢复，尚未并入主报告。当前 catalog 524 条**全部至少跑过 1 次**；600 步主报告覆盖 518 条。
- **累计运行**：当前 catalog 上累计 698 个 perturbation episode（524 条 case 全覆盖：407 条 ×1、61 条 ×2、55 条 ×3、1 条 ×4）；`runs/` 全部去重后 2,420 episodes（628 baseline + 1,792 perturbation；pi05 2,360、openvla_oft 60）。当前 catalog 全量只有 pi05 跑过。
- **数据仓库状态**：`validate-dataset` / `check-manifest` / `pytest` 全绿；静态校验只证明定义自洽，**不证明物理可行性**，逐条物理验收记录在外部证据中。

### 5.7 读数注意（口径陷阱）

1. **524 是定义数**，不是 rollout 数、不是物理验收通过数；单模型跑一遍才是 524 次 rollout（+10 baseline = 534 episodes）。
2. **518 是主报告覆盖数**，524 才是当前 catalog；差 6 条新用例（T00×2、T07×3、T08×1）单列。
3. **restore 380 / probe 128 / control 16** 是 case 语义分类；**preserved 380 / unreleased 144** 是按 `case_source_id` 的机械二分——两个“380”不是同一批（preserved 380 = restore 301 / probe 75 / control 4）。
4. **恢复率严格口径 42/477 = 8.8%**；episode 成功 160/477 = 33.5%；runtime 原始 `recovered=True` 的 168 条不是严格恢复数。排除 probe/control 后的敏感性口径为 43/338 = 12.7%。
5. **“11 种机制”是 schema 枚举数**，当前用例实际使用 10 种（`restore_captured_checkpoint_pose` 为 0，第 11 种 `move_to_relation_target` 仅 4 条）；severity 枚举 19 种、实际在用 14 种。
6. **524 ≠ 本地累计运行数**：累计 perturbation episode 698、`runs/` 去重 2,420，含重跑、验证与旧 catalog；不能当作测试集规模。

---

## 横向关系与选型

| 维度 | LIBERO | LIBERO-Plus | LIBERO-PRO | LIBERO-MAX | **libero-rollback（本项目）** |
|---|---|---|---|---|---|
| 任务规模 | 130 | 40 | 40 | 40 | **10**（LIBERO-10 单套件） |
| 干预/扰动位置 | 无 | **reset 时**静态扰动 | reset 时静态扰动 | **执行中**环境/观测/路径事件 | **执行中**语义回滚（已完成关系被撤销） |
| case 规模 | 130 | 10,030 | ~200 配置 | 8,000 配对 | **524** 定义（restore 380 / probe 128 / control 16） |
| 单模型 rollout | 2,000 | 10,030 | ~12,000 | 16,000 | **524**（+10 baseline） |
| 单任务 rollout 深度 | 50 | 250.75 | 300 | 400 | **52.4** |
| 主要用途 | 标准可比基线 | 大规模鲁棒性画像/诊断 | 低成本揭穿“记忆式”高分 | 执行中变化下的可靠性 | **完成关系被撤销后的自修复/重规划诊断** |

- 四个外部 benchmark 是**递进关系而非替代**：Plus 做“大而全”的静态扰动诊断，PRO 做“小而狠”的记忆性/公平性质疑，MAX 在 Plus+PRO 的 case 上再叠加“执行中变化”的动态维度；libero-rollback 是**另一个方向的收窄与加深**——只取 LIBERO-10 一个套件，把每个任务的“已完成进度被否定”做成 52 条左右的语义场景，用约一个标准套件的 rollout 成本测恢复能力。
- **读数注意**：10,030 是“扰动任务实例”不是独立任务；8,000 是配对 case 不是 8,000 个任务；PRO 的 200/12,000 与 MAX 的 224,000 是推导/乘积值（论文未直接印出）；LIBERO 的 50 次/任务是下游惯例，原论文代码默认是 20 次/任务。libero-rollback 的 524 是**定义数**，单模型 rollout 也是 524（每 case 1 次、单 seed），不要与 LIBERO 的“50 rollouts/任务”或 PRO 的“50 episodes/条件”混用。
- **选型建议**：要标准可比基线 → LIBERO；要大而全的静态鲁棒性画像 → Plus；要低成本检验记忆性/公平性 → PRO；要执行中环境变化的可靠性 → MAX；要“已完成关系被撤销后模型能否自修恢复” → libero-rollback（成本约为 LIBERO 全量的 1/4，且带 probe/control 阴性对照）。

## 主要来源

**四个外部 benchmark**：

- LIBERO：[arXiv:2306.03310](https://arxiv.org/abs/2306.03310) · [代码仓库](https://github.com/Lifelong-Robot-Learning/LIBERO) · [论文 HTML](https://arxiv.org/html/2306.03310v2)
- LIBERO-Plus：[arXiv:2510.13626](https://arxiv.org/abs/2510.13626) · [CVPR 2026 页面](https://www.openaccess.thecvf.com/content/CVPR2026/html/Fei_LIBERO-Plus_A_Progressive_Robustness_Benchmark_for_Visual-Language-Action_Models_CVPR_2026_paper.html) · [GitHub](https://github.com/sylvestf/LIBERO-plus)
- LIBERO-PRO：[arXiv:2510.03827](https://arxiv.org/abs/2510.03827) · [GitHub](https://github.com/Zxy-MLlab/LIBERO-PRO) · [项目页](https://zxy-mllab.github.io/LIBERO-PRO-Webpage/)
- LIBERO-MAX：[arXiv:2609.36518](https://arxiv.org/abs/2609.36518) · [项目页](https://liberomax.github.io/) · [GitHub](https://github.com/liberomax/LIBERO-MAX) · [BENCHMARK_SPEC](https://github.com/liberomax/LIBERO-MAX/blob/main/docs/BENCHMARK_SPEC.md)

**libero-rollback（本仓库）**：

- 定义入口：[`dataset/current/manifest.yaml`](../dataset/current/manifest.yaml)（case_count = 524）· [`coverage.yaml`](../dataset/current/coverage.yaml) · [`sources.yaml`](../dataset/current/sources.yaml) · [`templates.yaml`](../dataset/current/templates.yaml)
- 规范与协议：[`docs/dataset-card.md`](dataset-card.md) · [`docs/schema.md`](schema.md) · [`docs/evaluation-cli.md`](evaluation-cli.md) · [`docs/case-matrix-current.md`](case-matrix-current.md)（后两份的数字仍是 288 时代，以 manifest 为准）
- 审计与复现：本次规模审计记录在 `.tmp/scale-audit/`（`catalog-scale.md`、`eval-protocol.md` 及脚本/原始输出）；复核命令：`.venv/bin/libero-rollback --dataset-root dataset/current validate-dataset`、`check-manifest`、`list`。
