# `progress-pulse` / `progress-repeat-after-recovery` 用例族的用途与口径

> **状态（2026-10-16）**：`progress-pulse-*`（24 条）已暂时退出当前数据集，相关定义、实验数据、报告与代码快照归档在 `archive/pulse-descoped-20261016/`。本文保留，作为该维度重启时的设计依据。
> 退出理由：外部复原使该维度无法测量模型修复（18/18 条 `repair_step == externally_restored_step`），且 `pulse-5` 的窗口短于一个策略查询周期。


本文说明 `progress-pulse-{5,20,60}-mid`（24 条）与 `progress-repeat-after-recovery-mid`（8 条）
这一族用例的构造、测什么、以及**为什么不能把它们的任务成功当成模型恢复**。

## 一、构造

两组用例的第一次写入完全相同：在 mid 窗口触发时，把**已完成的第一个子目标**撤销
（`restore_episode_initial_pose`），使该关系真→假。差别在第二段写入：

| 族 | 条数 | 第二次写入 | 触发条件 |
| --- | ---: | --- | --- |
| `progress-pulse-5-mid` | 8 | `pre_injection`：**外部**把物体放回注入前的位置 | 注入后 **5** 个控制步 |
| `progress-pulse-20-mid` | 8 | 同上 | 注入后 **20** 个控制步 |
| `progress-pulse-60-mid` | 8 | 同上 | 注入后 **60** 个控制步 |
| `progress-repeat-after-recovery-mid` | 8 | `initial_offset`（偏移 0）：**再次**撤销同一关系 | 关系真值**保持 3 步**之后，且 `after_steps=1` |

实现位置：`rollback_extensions.py` 的 `update_transient_gate()` / `_apply_transient()` /
`check_transient_write()`；用例侧是 YAML 的 `transient` 块。

## 二、测什么

### 1. 三种时长的脉冲（24 条）—— 测「短暂进度丢失」下的行为

第一次撤销制造一个**长度可控的脆弱窗口**：物体离位、前序目标为假，随后由**外部**复原。
窗口长度是唯一的自变量（5 / 20 / 60 控制步），因此这一族回答的是：

- 模型在这个窗口里会不会**乱动**（把它当成新指令、把另一个物体也弄丢、反复抓取）；
- 窗口结束、物体被外部放回后，模型能否**接着把 s2 做完**（不许要求它自己修，因为修不是它做的）；
- 恢复的**代价**（与基线相比多走多少步、多少路径、多少次动作反转）。

### 2. 恢复后再次撤销（8 条）—— 测「修好了又被撤销」的第二次修复

`repeat` 变体刻意**不**靠时间门控：它要求关系**真的重新为真并保持 3 步**，才触发第二次撤销。
因此：

- 如果模型没有恢复关系，第二次撤销**永不触发**，协议按不完整记录
  （用例 `open_questions` 明确要求："Without spontaneous recovery, the second event must
  remain untriggered and be reported as such."）；
- 如果模型恢复了，第二次撤销再把它打掉，测的是**第二次修复**：第一次修好不代表第二次也能修好
  （实现里显式清空 `repair_completed`/`repair_step` 并保留 `first_repair_step` 正是为此）。

这一族是全 catalog 里**唯一**要求模型先真实修复、再施加同型扰动的用例族。

## 三、口径：脉冲复原不计为模型恢复（实测确认）

评测口径要求"外部 pulse 复原不能计作模型恢复"（`docs/expansion-plan.md` 验证顺序第 3 条）。
代码在 `src/libero_rollback/evidence.py::classify_result()` 里落实：

```
transient → 若 temporal_protocol 不完整 → "protocol_incomplete"
          → 若 destination == "pre_injection" → "valid_external_restoration"   ← 直接返回
          → 否则才进入 "valid_recovered" / "valid_not_recovered" 判定
```

即 `pre_injection` 的用例**永远拿不到 `valid_recovered`** —— 外部复原发生在"模型修复"判定之前。

实测逐条核对（mid 窗口 32 条，修复前的完成批次）：

| 观察 | 结果 |
| --- | --- |
| `repair_step` 与 `externally_restored_step` 相等 | **18/18**（所有注入有效的 pulse 都是"外部复原那一步"被记为修复） |
| 即：模型在窗口内自行修复的条数 | **0/18** |
| `repeat` 中第二次事件未触发（模型没恢复） | 5/6 已跑条目（另一条触发了第二次撤销） |
| 第二次事件触发后的结果（任务 01） | 第二次修复失败，episode 耗尽 600 步 |

**结论：pulse 系列的"任务成功"衡量的是"外部复原之后模型能否顺手完成剩余目标"，
不是"模型能否发现并修复丢进度"。** 把它计入模型恢复率会高估能力。

### 窗口有多短（实测）

| 用例 | 注入步 | 复原步 | 窗口（控制步） | 窗口内策略查询次数（≈窗口/10） |
| --- | ---: | ---: | ---: | ---: |
| `pulse-5`（任务 01/06） | 167 | 172 | 5 | **≈0.5 次** |
| `pulse-20` | 167 | 187 | 20 | ≈2 次 |
| `pulse-60` | 167 | 227 | 60 | ≈6 次 |

按 `replan_steps=10` 计，`pulse-5` 的窗口只有**半个策略查询周期** —— 模型极可能**根本没观测到**
被撤销的状态，外部就把它放回去了。因此 `pulse-5` 更适合作为"瞬态扰动鲁棒性"探针
（模型不该因此乱动），而不是"响应与修复"的测量。三档时长合起来给出的是
**可见性阈值**：窗口越短越测"是否被打乱"，越长越接近真正的"察觉 + 响应"。

## 四、读结果时不要做的事

1. 不要把 pulse 的 `task_success=true` 写成"模型恢复"（本文第三节）。
2. 不要把 `repeat` 的"第二次事件未触发"写成模型失败 —— 那是**协议不完整**，
   应报 `protocol_incomplete`，并说明模型未恢复第一段关系。
3. 不要用 `pulse-5` 的恢复延迟当"响应速度" —— 它的窗口短于一个查询周期，
   该数值实际反映的是外部复原之后的完成过程。