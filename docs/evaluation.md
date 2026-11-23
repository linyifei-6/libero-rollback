# 评估体系（Rollback Impact + Subtask Completion）

> 状态：**重构草案（2026-11-21，base-only）**。取代“只看 SR”的旧口径。
> 适用范围：A 基线、B 完成边界回滚、C L10 执行中回滚、D 组合任务回滚。
> 相关：矩阵见 [`dataset/matrices/libero-rollback/`](../dataset/matrices/libero-rollback/)、[`dataset/matrices/libero-compose/`](../dataset/matrices/libero-compose/)；协议见 [`configs/protocol.yaml`](../configs/protocol.yaml)。

---

## 0. 一句话

**不要用“任务成功率”作为一个数来评价 Rollback。** 我们的测试集关心两件事：

1. **Rollback 对任务进行的影响**：撤销之后，模型是否识别、是否恢复、恢复多少、是否保住未撤销的进度；
2. **组合/长程任务中子任务的完成程度**：完成了几个原子、停在哪个阶段、是 one-and-done 还是 zero-progress。

因此评估分成四层：**有效性/触发 → 状态与完成度 → Rollback 影响（配对）→ 行为与成本**。

---

## 1. 为什么 SR 不够

| 问题 | SR 的盲点 | 需要的读数 |
|---|---|---|
| C/D 任务在注入时本来就没完成 | SR 低是任务未完成，不是 rollback 失败 | `Recovery`、`PendingPreservation`、`Progress` |
| 组合任务有 2–3 个目标原子 | SR 把“完成 1/2”和“完成 0/2”都记 0 | `Progress`、`PP`、`One-and-Done`、`Zero-Progress` |
| 模型可能“修了旧的、丢新的” | SR 只看最终联合目标 | 四类终局：`both` / `restore_only` / `pending_only` / `neither` |
| 需要知道撤销到底造成多大代价 | SR 不区分 control 与 rollback | `ΔSR`、`ΔProgress`、`Retention` |
| 需要知道恢复有多晚 | SR 只在终点看 | `Notice latency`、`time-to-restore` |
| 需要知道是否可触发 | SR 把 N/A 当 0 | `trigger_rate`、`N/A`、失效原因 |

---

## 2. 四层评估

### L0：有效性与触发（不是性能）

| 指标 | 定义 | 分母 |
|---|---|---|
| `valid_rate` | 注入有效 / attempted | attempted |
| `trigger_rate` | 触发事件发生 / attempted | attempted |
| `control_rate` | `valid_control` / attempted C0 | C0 attempted |
| `invalid_reason` | `injection_invalid` / `truth_unverified` / `protocol_incomplete` 等 | — |
| `N/A` | 不可触发、无控制、无数据 | 显式写 `N/A`，不是 0% |

> L0 的失败不能进 L1 的分母。先报“多少 case 根本不可评”，再谈性能。

### L1：状态与完成度

设任务的原生 goal 原子为 `G = {g1..gn}`，终局真值为 `g_i ∈ {0,1}`；被撤销关系集合为 `R ⊆ G`（`|R|=r`），pending 集合为 `P = G \ R`（`|P|=p`）。

| 指标 | 公式 | 说明 |
|---|---|---|
| `SR` | `1[Σ_i g_i = n]` | 联合成功；A 的主指标，B/C/D 的次要读数 |
| `Recovery` | `1[∀i∈R: g_i=1]` | 条件恢复率；只看被撤销关系，不看 pending |
| `Progress` | `(1/n) Σ_i g_i` | **子任务完成度**，0–1；C/D 的核心读数 |
| `Atoms` | `Σ_i g_i` | 完成的原子数；EGC 的单 episode 版本 |
| `EGC` | `mean(Atoms)` | 平均完成原子数；组合能力的主读数 |
| `PP` | `P(Σ_i g_i ≥ 1)` | 至少完成一个子任务 |
| `One-and-Done` | `P(Σ_i g_i = 1; n≥2, SR=0)` | 失败中“恰好完成一个”的占比；容量=1 的签名 |
| `Zero-Progress` | `P(Σ_i g_i = 0)` | 一个都没完成 |
| `PendingPreservation` | `(1/p) Σ_{i∈P} g_i` | 未撤销的 pending 进度保住了多少；C/D 特有 |
| `pending_ok` | `1[∀i∈P: g_i=1]` | pending 全保住的 case |

**四类终局**（C/D 的主表要并列）：

| 终局 | 定义 | 读法 |
|---|---|---|
| `both` | `R` 全真且 `P` 全真 | 旧关系修好、新进度也保住 |
| `restore_only` | `R` 全真、`P` 不全真 | 补了旧的，丢了新的 |
| `pending_only` | `R` 不全真、`P` 全真 | 做完新的，无视撤销 |
| `neither` | 两者都不全真 | 都没做好 |

- B 没有 pending（`P=∅`），`Recovery` 与 `SR` 在单目标/多目标上可能重合；仍需分别报。
- C/D 主表只报 `Recovery`、`Progress`、`ΔProgress`；`PendingPreservation`、四类终局进附录/分析。

### L2：Rollback 影响（配对）

不要用边际差。对同一 `(task, structure, init, level)` 的 reference `ref` 与 rollback `rb`：

```text
ΔSR       = SR(ref)       - SR(rb)          # 正 = rollback 有害
ΔProgress = Progress(ref) - Progress(rb)    # 正 = rollback 降低完成度
ΔAtoms    = EGC(ref)      - EGC(rb)
Retention = SR(rb) / SR(ref)                # ref>0；不是裸 SR
```

- `Δ*` 是**向量**，不要压成一个“总分”；报告时分开。
- `ref` 的选择：
  - B：同任务的 `C0`（no-op）或 A 的 intact；
  - C：B(l10, s1) 的 `all_done` 对照，或同任务的 `C0`（如果有窗口控制）；
  - D：`D-intact`（176）同结构基线；D 的 Rollback 影响必须用它配对，不能只看 D-rollback。
- `Recovery` 是条件量，不能和 `SR`/`Progress` 并排当同一个数。

### L3：行为与成本

| 指标 | 定义 | 用途 |
|---|---|---|
| `Notice latency` | 注入 → 首次朝被撤销物体移动的步数；中位数/IQR | 识别速度 |
| `time-to-restore` | 注入 → 首次 `R` 全真的步数；未恢复为 censored | 恢复速度，不是 0/1 |
| `repair_steps_used` | 实际使用的修复步数 | 预算效率 |
| `s/episode`、`GPU-h/model`、`$/entry` | 成本 | 采纳门槛 |
| `trigger_rate` by window | `early/mid/later` 实测 | 窗口可达性；<20% → N/A |

**censored 规则**：`time-to-restore` 只在恢复发生的 case 上给中位数；未恢复不能当“无穷大”混进均值，单独报 `not_recovered`。

---

## 3. 论文主表只放 2+1 个指标

主表只保留 **2 个核心读数 + 1 个配对效应**；其余全部进附录/分析，不进主表：

| 主表列 | 定义 | 回答 |
|---|---|---|
| **`Recovery`** | 被撤销关系终局全真 | 模型有没有识别并修回旧状态 |
| **`Progress`** | `(1/n) Σ g_i`，终局完成原子占比 | 任务/组合整体推进到哪 |
| **`ΔProgress`** | `Progress(ref) - Progress(rollback)` | Rollback 让完成度掉了多少（配对） |

- **A** 没有 rollback，主表用 `SR` + `Progress`；`SR` 也是 B/C/D 的 baseline 列。
- **B/C/D** 主表列：`Recovery`、`Progress`、`ΔProgress`（+ `SR` 作 baseline）。
- `ΔSR`、`PP`、`One-and-Done`、`Zero-Progress`、`PendingPreservation`、`EGC`、四类终局、`Notice latency`、`time-to-restore` **全部进附录/分析**；需要时再按套件展开。
- 协议读数（`valid_rate`、`trigger_rate`、`control_rate`）单独成表，不占性能主表列。

### 3.1 分套件主表 / 附录

| 套件 | 主表列 | 附录/分析 | 禁止 |
|---|---|---|---|
| **A** | `SR`、`Progress` | `Atoms`/`EGC`（l10 n=2/3） | 把 A 当 Rollback 结果 |
| **B** | `Recovery`、`Progress`、`ΔProgress` vs `C0`/A | `SR`、四类终局、`Notice latency`、`time-to-restore` | 把 B 的 `Recovery` 与 C/D 合并 |
| **C** | `Recovery`、`Progress`、`ΔProgress` vs B(l10,s1) | `PendingPreservation`、`PP`、终端四态、`trigger_rate` 分窗口、`Notice latency` | 把 C 的 `all_done_control` 当窗口控制（C 无 C0） |
| **D** | `Recovery`、`Progress`、`ΔProgress` vs D-intact | `PP`、`One-and-Done`、`Zero-Progress`、`EGC`、四类终局、按结构聚类 | 用 528 定义矩阵当执行结果；D-intact 未配对就报“不可归因” |

**B/C 配对**：B(l10, s1) 60 条 ↔ C 任一窗口 60 条；同任务、同 level、只换时机。报 `ΔRecovery`、`ΔProgress`、`ΔAtoms`，不要只报两个 Recovery。

**C/D 比较**：跨结构，不是同任务配对；只能做分层/趋势，不能做 exact McNemar 的直接配对。

---

## 4. 控制与分母

| 套件 | 控制/基线 | 分母 |
|---|---|---|
| A | 无 | 有 `success` 的 episode |
| B | 每任务 `C0`（all_done no-op） | `Recovery` = 有效非 C0；`control_rate` = C0 attempted |
| C | 无矩阵 C0；`all_done` 控制由 B 覆盖，但**不是窗口控制** | `Recovery` = 有效非 C0；窗口 `control_rate` 先 `N/A` 或 synthetic |
| D | D-intact 基线；窗口 synthetic 待实现 | `Recovery` = 有效非 C0；D-intact 不进 Recovery |

- `C0`、无效注入、外部复原、协议不完整、不可触发**全部排除** Recovery 分母。
- `N/A` 是一等结果；不能写成 0%。
- 一个窗口 `trigger_rate < 20%` 时，该窗口记 `N/A`，case 不删除。

---

## 5. 预算：repair_window 至少 600

旧协议 `repair_window=300` 对长程任务太短：C/D 的 pending 子任务本身可能就要 300+ 步，300 会把“还没开始修”误判成“修不好”。新协议：

| 套件 | `max_steps`（注入前） | `repair_window`（注入后追加） | 说明 |
|---|---:|---:|---|
| A | 600 | 0 | 无注入 |
| **B** | 600 | **600** | 完成边界回滚；至少一个正常任务步数 |
| **C** | 800 | **600** | L10 未完成，主预算更长 |
| **D** | 600 | **600** | 组合任务 |
| D-intact | 600 | 0 | 无撤销 |

规则：

- `total_budget_steps = injection_step + repair_window`；不是固定 1200/1400。
- `repair_window` 是**协议下限 600**；矩阵里的 300 是旧参考值，runner 取 `max(600, case.repair_window)`，不得低于 600。
- 逐 episode 记录 `repair_budget_steps`、`repair_steps_used`、`injection_step`、`trigger_step`。
- 旧 300 步结果标 `protocol: repair300`，不得与新 600 结果混表。

---

## 6. 报告纪律

1. **分套件**：A/B/C/D 分别出表；B/C/D 不合并 Recovery 分母。
2. **分窗口**：C/D 的 `early/mid/later` 分列；`trigger_rate <20%` 的窗口 `N/A`。
3. **分结构**：D 按 `struct_id` 聚类；不能把 120 个结构当独立样本。
4. **配对**：B/C 用同任务/同 level/同 init 的配对差；D 用 D-intact 配对；报 exact McNemar 或配对 bootstrap。
5. **双读数**：`Recovery` 与 `Progress` 并排；`SR` 只作次要。
6. **CI**：每个率带 Wilson 95% CI；每个 `Progress` 带均值 + 分布（至少 median/IQR）。
7. **N/A**：不可触发、无控制、无 intact 都写 `N/A` 并解释；不写 0%。
8. **不合并**：B 的 `Recovery`、C 的 `Recovery`、D 的 `Recovery` 不是同一个量；`Δ*` 也不能跨套件相加。
9. **单 seed/init**：主表必须带 init 数、预算、CI；点估计不能当稳定结论。
10. **成本**：`s/episode`、`GPU-h/model`、`$/entry` 与质量指标同表。

---

## 7. 实现落点

| 层 | 已有 | 需要补 |
|---|---|---|
| 矩阵 | `goal_atoms`/`n_targets`、B/C/D case | C 180、D-intact 176、D-rollback 528（定义已建） |
| Runner | `final_goal_truth`、`final_revoked_truth`、`recovery_ever`、`restored_at_step`、`notice_latency`、`final_pending_truth`、`terminal_state`、`subtask_progress` | `revoked_goal_indices`、`pending_goal_indices`、`final_pending_truth`、`repair_window=600` |
| Metrics | `Recovery`、`control`、`trigger`、`SR`、`EGC`、`Retention` | `Progress`、`Atoms`、`PP`、`One-and-Done`、`Zero-Progress`、`PendingPreservation`、四类终局、`Δ*`、`time-to-restore` |
| Report | aggregate/HTML | 分窗口/分结构、四类终局、progress 分布、N/A 解释、protocol 版本 |

**字段约定（建议）**：

```jsonc
"final_goal_truth": [true, false, true],
"revoked_goal_indices": [0, 2],
"pending_goal_indices": [1],
"final_pending_truth": [false],
"subtask_progress": 0.667,
"atoms_completed": 2,
"terminal_state": "restore_only",
"recovery_ever": true,
"restored_at_step": 143,
"injection_step": 88,
"notice_latency": 12,
"repair_window": 600,
"repair_budget_steps": 600,
"repair_steps_used": 600
```

- `terminal_state` 由 `R`/`P` 真值自动推导，不手填。
- `subtask_progress` 对 B 也适用（n=1/2/3），便于和 A/C/D 对照。
- 对 `pre` 目标（B 只有 goal-t030），`R` 不在 goal 原子内，`Progress` 用 `goal_atoms` 全量，`Recovery` 用注入关系；不要混。

---

## 8. 当前状态与下一步

| 项 | 状态 |
|---|---|
| B base 矩阵 | ✅ 442；pi05 已跑（旧 300 窗口） |
| C 180 矩阵 | ✅ 已生成；C/D window runner 已实现 |
| D-intact 176 / D-rollback 528 | ✅ 定义矩阵与资产已入仓；runner 未就绪 |
| repair_window 600 | ✅ 协议/runner/套件矩阵已改 |
| Progress/PP/终局 metrics | ✅ `metrics.py` 核心函数 + `report.aggregate` 已加；HTML 卡片/分窗口待补 |
| C/D runner | ✅ 已实现（静态 + fake-env 验证；未跑真实仿真） |

下一步（建议顺序）：

1. 跑 C/D window runner（GT `early/mid/later`，600 窗口）；
2. 在 runner 记录 `revoked_goal_indices`/`pending_goal_indices`/`final_pending_truth`；
3. 补 metrics 函数与测试：`Progress`、`PP`、`One-and-Done`、`Zero-Progress`、`PendingPreservation`、四类终局、`Δ*`；
4. 报告按 B/C/D + window + structure 分表；
5. D 的 BDDL/init 资产已入仓；runner 已实现但尚未跑真实仿真，D-rollback 不报结果；
6. B 旧 300 结果标 `protocol=repair300`，新 600 结果另表。

---

## 9. 版本

| 日期 | 变更 |
|---|---|
| 2026-11-21 | 初版：四层评估、Progress/PP/终局、配对 Δ、repair_window 600；替代 SR-only 口径 |
