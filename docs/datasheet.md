# 数据卡（Datasheet）

> **2026-11-21 base-only 迁移注记**：B = `b-matrix.csv`（442），C = `libero-rollback/in-execution-rollback.csv`（180，无 C0），D = `libero-compose`（intact 176 + rollback 528）；Plus 不进入主表。
> 新叙事见 [`rollback-narrative.md`](rollback-narrative.md)；本文件旧 B/D 口径待迁移。

> 版本：`2.0.0.dev0`（v2.0-draft）｜ 日期：2026-11-18 ｜ 上位文档：[README.md](../README.md) · [docs/SPEC.md](SPEC.md) · [docs/protocol.md](protocol.md)
> 本文件描述**当前仓库里的真实数据**；数字以 `dataset/matrices/*.csv` 与 [dataset/manifest.yaml](../dataset/manifest.yaml) 为准。未构建的数据不会写成已构建。

---

## 1. 基本信息

| 项 | 值 |
|---|---|
| 名称 | LIBERO-Rollback（受控扰动基准） |
| 能力 | 冻结 VLA 策略的目标状态持久性 / 条件恢复率测量；**不是**方法、训练代码或恢复算法 |
| 版本 | 数据集 `2.0.0.dev0`（draft；发布后 case_id 与语义冻结） |
| 创建/复核日期 | 2026-11-18 |
| 许可 | 代码 MIT（见 [LICENSE](../LICENSE)）；数据为派生定义；底层 LIBERO 资产 MIT，**不随本仓分发** |
| 上游唯一数据源 | [LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO)，commit `f78abd68ee283de9f9be3c8f7e2a9ad60246e95c` |
| 仓库自包含约束 | `dataset/` 内 0 个绝对主机路径、0 处前序仓引用；资产与模型权重不入库 |
| 机器可读来源 | `dataset/matrices/*.csv`（唯一权威）+ `dataset/manifest.yaml`（计数/sha256/splits）+ `dataset/sources.yaml`（来源与导入哈希） |
| 冒烟子集 | `dataset/lite.yaml`：30 条（A 10 / B 10 / D-native 10） |
| 引用方式 | 数据集版本 + `case_id`（例：`2.0.0.dev0`，`b-goal-t000-g-l1-d03`） |

---

## 2. 四个套件（Phase 1 实际状态）

| 角色 | 套件 | 底盘 | 扰动 | 触发 | n | case 数 | 状态 |
|---|---|---|---|---|---|---:|---|
| **Rollback 维度 1** | **B** `completion-boundary-rollback` | 同 A 的 40 任务 | `C0/L0/L1/L2` | `all_done` + delay 10 | 1–2 | **442** | ✅ 已导入冻结（`b-matrix.csv`） |
| **Rollback 维度 2** | **D-native** `in-execution-rollback` | LIBERO-10 原生多目标（9 任务） | `C0/L0/L1/L2` | `early` / `mid` / `later` | 2 | **189** | ✅ 已导入冻结（`d-native-matrix.csv`） |
| 维度 2（占位） | **D-compose**（Phase 2） | C 的 120 个 n=2 结构 | `L0` | 3 窗口 | 2 | 360（占位） | 🟡 仅 provisional，**不执行** |
| 对照（无撤销） | **A** `single-intact` | 原始 LIBERO 4 套件 ×10 任务 | 无 | — | 1–3（实测，见 §4） | **40** | ✅ 已生成（`a-matrix.csv`） |
| 对照/剂量（无撤销，Phase 2） | **C** `composition-intact` | 40-task pool 内同场景配对 | 无 | — | 2（+40 条 n=3） | **0**（目标 160） | ⬜ Phase 2，尚未构建 |

> 角色定义：两个 Rollback 维度 = **维度 1 完成后撤销（B）** 与 **维度 2 执行中撤销（D）**；A/C 是无撤销对照。完整定义与不可混报规则见 [docs/rollback-dimensions.md](rollback-dimensions.md)。

**Phase 1 可执行 case 总数 = A 40 + B 442 + D-native 189 = 671**（README 的目标 `core` 是 1,191，其中 C 160 与 D-compose 360 待 Phase 2）。`lite` 30 条见 `dataset/lite.yaml`。

> D-compose 的 360 行是**设计占位**：`instruction` / `revoked_predicate` / `revoked_object` 为字面量 `<from C>`，没有绑定任何真实 C 结构。它列在 `manifest.yaml` 的 `provisional` 中，**不进入任何执行 split**。

---

## 3. B 套件分布（`b-matrix.csv` 实测）

| 维度 | 取值 |
|---|---|
| 任务数 | 40（goal / object / spatial 各 10，l10 10） |
| suite | goal 85 / object 80 / spatial 80 / l10 197 |
| level | `C0` 40 / `L0` 60 / `L1` 180 / `L2` 162 |
| family | pose 350 / joint 24 / mixed 28 / `-`（C0）40 |
| target | `g` 211 / `s1` 60 / `s2` 57 / `both` 70 / `pre` 4 / `c0` 40 |

规则（加载时强制）：每任务恰好 1 条 C0；`L0` 不带 param；`L1` ∈ {d03,d06,d10}；`L2` ∈ {r30,r60,r90}；joint 任务无 L2；`target=pre` 只出现在 `goal-t030`；`expected_relation_after` 对 C0 为 `true`、对非 C0 为 `false`。实现见 `src/libero_rollback/matrices.py`。

---

## 4. D-native 与 A 套件分布（实测）

**D-native（189 行，9 个 LIBERO-10 多目标任务）**

| 维度 | 取值 |
|---|---|
| window | `early` 60 / `mid` 60 / `later` 60 / `all_done_control` 9 |
| level | `C0` 9 / `L0` 27 / `L1` 81 / `L2` 72 |
| family | pose 176 / joint 13 |
| trigger_criterion | `enter_first_subgoal_completed` / `enter_next_subgoal_lift` / `enter_next_subgoal_preplacement` / `no injection`（C0） |
| 预算 | `max_steps=800` + `repair_window=600` |

**A（40 行）**：按 B 的 40 个任务键生成，指令与 `n_goals` 逐字读取上游 BDDL。实测 `n_goals` 分布：**31 条 n=1、8 条 n=2、1 条 n=3**（n=3 的是 `KITCHEN_SCENE8_put_both_moka_pots_on_the_stove`，见 §8 债务 9）。A 的 `max_steps=600`，每行只绑定 init row 0（10-init 上界协议另行报告）。

---

## 5. 来源与可复现性

| 项 | 记录位置 | 内容 |
|---|---|---|
| 上游 LIBERO pin | `assets/libero.lock.yaml`、`dataset/sources.yaml`、`dataset/manifest.yaml` | repo + commit + 期望 130 `.bddl` / 130 `.pruned_init` |
| 导入矩阵来源 | `dataset/sources.yaml` | 来源仓（`libero-compose`）、来源相对路径、来源 sha256、导入日期、归一化说明（CRLF→LF） |
| 冻结矩阵哈希 | `dataset/manifest.yaml` | 4 个 CSV 的逐文件 sha256 + 行数 |
| A 矩阵生成器 | `scripts/build_a_matrix.py` | 纯 stdlib，`--check` 可重建比对 |
| manifest/lite 生成器 | `scripts/build_manifest.py` | 确定性，`--check` 零 diff |
| 资产内容 pin | `assets/manifest.yaml` | **Phase 1 为空**（`files: []`）；冻结流程见文件内说明，禁止手写哈希 |
| 运行期资产校验 | `scripts/verify_libero.py` | commit / clean worktree / 计数 / 已冻结 sha256 |

导入时的取数方式：上游 checkout 工作区不干净，因此只从 `git archive HEAD` 取干净的 `bddl_files` / `init_files`；主机绝对路径被刻意排除在 `dataset/` 之外（`sources.yaml` 有说明）。

---

## 6. 证书状态（C1–C8）

> “已实现/可验证”指本仓当前有检查代码或命令；**不等于**已在全部 case 上实测通过。

| # | 证书 | 当前状态 | 证据 / 缺口 |
|---|---|---|---|
| C1 | 完整性（覆盖证明，计数加总一致） | 🟡 | 矩阵计数、case_id 唯一、manifest sha256 由静态校验覆盖；**B/D 的逐场景候选覆盖证明**尚未构建 |
| C2 | 初始状态（`success=False`、无穿透、sha 对账） | 🟡 | init 引用为 `LIBERO_HOME` 相对路径；`scripts/smoke_env.py` 冒烟可验证；init 逐文件内容 sha 未冻结 |
| C3 | **可解性**（脚本 oracle ≥3/3） | ⬜ Phase 2 | 无 oracle；主表在 C3 完成前不得发布 |
| C4 | **可复原性**（撤销后状态写回可恢复） | ⬜ Phase 2 | 同上；逐 case `restorable` 字段已定义，全量未跑 |
| C5 | 非退化（合取 ≠ 单目标、两目标可区分） | 🟡 | B 矩阵的 target/谓词结构由 loader 校验；语义级 C5 需要 oracle |
| C6 | 负对照（`C0` 必成功、`infeasible` SR=0、`probe` 不虚假修复） | 🟡 | 每任务恰好 1 条 C0 已强制；`infeasible` / `probe` 负对照集未构建（Phase 2） |
| C7 | **GT 记录**（逐 check `gt_atoms_raw` + 终点快照） | 🟡 | trace/终点 GT 格式已在 README §6.3 定义；`runtime/trace.py` 尚未移植，终点快照待落地 |
| C8 | 成本（`s/episode`、GPU-h、`$`） | 🟡 | 成本字段与口径已定义；**v2 实测成本表未产出**（README 中的成本为估算/前序仓 v1 经验） |

---

## 7. 已知限制

1. **仿真-only**：不宣称 sim-to-real；跨模拟器复现是 Stage 2。
2. **冻结策略**：不训练、不评测恢复算法；测量的是推理时能力。
3. **资产域内**：物体/技能/场景来自 LIBERO 原始分布，异分布结论不适用。
4. **适用性筛选**：D 对零进展模型记 `N/A`，这是结论而非缺陷；名册必须报告筛选过程与被筛掉的模型。
5. **构造层 valid ≠ 物理已验证**：C3/C4 未完成前，主表不得发布。
6. **D-compose / C 未构建**：任何把 360 provisional 行当作结果的做法都是错误的。
7. **任务编号口径未统一**（见 §8 债务 8）：`task_idx` 目前是来源仓的 LIBERO 全局下标，不是 SPEC §2.2 的 0–9 稳定编号。

---

## 8. 数据债务（发布前逐条解决或明确标注）

1. **B 内混合 n=1 与 n=2**：B 的 40 任务含 10 个 LIBERO-10 原生多目标任务；报告必须按 suite 分列，B(l10) 与 D-native 的 pending 对照单独成表，不与 n=1 混算。
2. **A 含 LIBERO-10**：A(Obj/Goal/Spatial) 是严格 n=1 锚点，A(l10) 是 n=2（及 1 条 n=3）参照；报告分开。
3. **B 的 `max_steps` 口径变更**：来源实现为 600 总步；v2 为“600 活跃步 + 600 修复窗口”，逐 episode 记 `repair_budget_steps`。两套口径不得混表。
4. **`both` 撤销不彻底**：部分 LIBERO-10 任务有 3 个目标原子（含 `Turnon` 类隐含前置），`both` 撤销后可能仍有一个原子为真；必须在 case `notes` / 数据卡标注。
5. **`valid` 是构造层判断**：不等于物理验证；数据卡区分 “construction-level valid” 与 “physically verified”。
6. **窗口触发率**：D 的触发率是实测值；某窗口不可达时按 `N/A` 处理并从主表剔除原因，**不删 case**。
7. **编码纪律**：全部数据 `UTF-8`（无 BOM）、LF 行尾；CI 校验。
8. **`task_idx` 编号口径冲突（新增，未解决）**：SPEC §2.2 规定 `task_idx` 是本仓稳定编号 0–9；但导入的 A/B/D 矩阵实际使用来源仓的 **LIBERO 全局任务下标**（0–276，例如 `a-l10-t133`、`b-l10-t276-c0`），`dataset/sources.yaml` 已记录该偏差。发布前必须二选一：重新生成矩阵（数据版本号 + manifest 更新）**或**修订 SPEC（需评审）。在此之前把 `(suite, task_idx)` 当作不透明稳定键使用，**不得**当作 LIBERO-Plus 注册表下标。
9. **A 的 `n_goals=3` 行（新增）**：README §3.2 称 A 的 n 为 1–2；实测 1 条 l10 样本展开为 3 个目标原子。需在 README/SPEC 口径表中修正或按 n=3 单列报告。
10. **`variance` split 实现口径（新增）**：README §3.7 写“100 结构 × 5 init ≈400 episodes”；`manifest.yaml` 实际实现为“100 case × 5 init = 500 episodes”。以 manifest 为准，README 的 ≈ 数字需在 M3 前对齐。
11. **导入行归一化**：b/d 矩阵导入时仅做 CRLF→LF（`.gitattributes` 要求 LF），内容逐字节保持；来源 sha256 与冻结 sha256 均记录在 `sources.yaml`，可审计。

---

## 9. 版本与变更纪律

- 数据集版本 `2.0.0.dev0` 为 Phase 1 迁移快照；**任何数据修改**都要：改 CSV → 重建 `manifest.yaml` → 更新 `sources.yaml` 与数据卡 → 升版本号。禁止静默改 `case_id` 或语义。
- v1 与 v2 不混表：前序仓的 v1 数字（40/40、2/49、0/76、42/477、2,112 case 等）只作动机引用（README §10.3）。
- 引用时注明**数据集版本 + case_id**；leaderboard 提交绑定 dataset digest 与模型 ckpt sha。

---

## 10. 不包含什么

- ❌ 上游 LIBERO 资产（3.1 GB，由用户自行 clone 并按 pin 校验）；
- ❌ 模型权重 / checkpoint（只记录环境变量名与 basename，不下载、不分发）；
- ❌ 运行产物（`runs/` 全部 gitignored，视频/日志不入库）；
- ❌ 训练代码、恢复算法、VLM 判官、新场景/新物体（见 README §1.1 的“不做什么”）。
