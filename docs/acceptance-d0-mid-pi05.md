# 验收记录：d0 档位 mid 窗口（修复后重跑）

> **状态（2026-10-16）**：`progress-pulse-*`（24 条）已暂时退出当前数据集，相关定义、实验数据、报告与代码快照归档在 `archive/pulse-descoped-20261016/`。本文保留，作为该维度重启时的设计依据。
> 退出理由：外部复原使该维度无法测量模型修复（18/18 条 `repair_step == externally_restored_step`），且 `pulse-5` 的窗口短于一个策略查询周期。


- 运行：`runs/eval-mid-d0-pi05-fixed`（修复前为 `runs/eval-mid-d0-pi05`）
- 规模：**40 条用例 / 8 个任务批次 / 8 次模型加载 / 1.32 h**（task01–08 全部完成，无执行错误）
- 选择：`--severity d0 --window mid`，seed 0，任务 03/06 用 seed 1，`--max-steps 600 --video`
- runtime：`runs/validation-runtime-20261014-v14`（含本次系统性修复）
- 验收脚本：`scripts/accept_run.py`，结论 **PASS**（exit 0）

## 一、六层验收结果

| 层 | 检查内容 | 结果 |
| --- | --- | --- |
| 1 结构 | 每条用例恰好 1 条基线 + 1 条扰动；无残留的旧 `results.json` 快照 | **40/40 通过** |
| 2 配对 | 每条注入有效的用例都带 `audit_strict_pairing` 且 `eligible=true`、`initial_observation_match=true` | **40/40 通过** |
| 3 净空证据 | 搜索轨迹末档穿透 == 记录的最终穿透（容差 1e-5）；上抬量 == 末档步长；通过者不超预算 | **10/10 通过**（10 条触发搜索，均上抬 12 mm） |
| 4 分类口径 | 用 `libero_rollback.evidence.classify_result()` 重算逐条判定，与汇总一致；外部复原不得计为模型恢复 | **一致** |
| 5 provenance | `overlay-provenance.json` 记录的 570 个文件哈希与磁盘一致（仅 4 个 assets 未纳入摘要，属既有状态） | **一致** |
| 6 绑定保真 | 8 个任务的 `binding.yaml` 与当前桥接输出逐字段相同（类型规范化后比较） | **40/40 一致** |
| 附 视频 | 48 段（8 基线 + 40 扰动）全部通过完整解码，20.6 MB | **0 失败** |
| 附 可复现 | 抽两条语义不同的用例（`-initial-pose` 与 `pulse-60`）在新目录重跑，逐字段相同 | **2/2 IDENTICAL** |

## 二、修复前后对照

| 指标 | 修复前 | 修复后 |
| --- | ---: | ---: |
| 注入有效 | 30/40 | **40/40** |
| 注入无效（穿透拒绝） | 10（T04/T05 全部） | **0** |
| 扰动 episode 成功 | 18 | 24 |
| 触发净空搜索 | 0（无此能力） | 10 条，均上抬 12 mm |

## 三、按口径的逐条判定（修复后）

| 判定 | 条数 | 含义 |
| --- | ---: | --- |
| `valid_recovered` | **0** | 模型自行修复进度丢失 |
| `valid_not_recovered` | **9** | 注入有效、模型未恢复（`*-initial-pose` 类、`-p1` 单子任务类） |
| `valid_external_restoration` | 24 | pulse 系列：外部复原，**不计模型恢复** |
| `protocol_incomplete` | 7 | `repeat-after-recovery`：模型未恢复 → 第二次撤销未触发（用例要求的记录方式） |
| `injection_invalid` | 0 | — |

**结论**：修复后 d0 批的 40 条全部成为可评估用例（基线 40/40 成功、注入 40/40 有效、配对 40/40 成立），
而在"要求模型自己修复"的语义下，**模型自修成功次数为 0**。

> 口径更正：`docs/experiment-d0-mid-pi05.md` 早期版本把 18 条"外部复原 + 后续完成"记为"模型恢复"，
> 该表述已在本轮修正（见该文第六节与 `docs/pulse-series.md`）。

## 四、本轮发现并修掉的 1 个数据侧问题、3 个脚本侧问题

| 类型 | 问题 | 处理 |
| --- | --- | --- |
| 数据 | 无 | — |
| 脚本 | `accept_run.py` 比较穿透时未留容差（记录按 5 位取整），产生 10 条假警报 | 已加 1e-5 容差；复核实测真实偏差 **0** |
| 脚本 | 把 `protocol_incomplete` 当成缺陷 | 改为"按用例要求记录的结果"，不计入失败 |
| 脚本 | 汇总校验漏计 `protocol_incomplete`，导致 `injection_valid` 对不上（33 vs 40） | 已把该判定计入注入有效计数 |

## 六、退场后的口径说明

本记录的 40 条 d0+mid 集合**包含 24 条 `progress-pulse-*`**；该族已于 2026-10-16 退出数据集，因此本记录中 24 条 `valid_external_restoration` 不再属于当前 catalog。退场后同一筛选（`--severity d0 --window mid`）为 **16 条**（每任务 2 条：1 条 offset + 1 条 repeat 或 initial-pose）。数据与报告已归档到 `archive/pulse-descoped-20261016/`。

## 五、遗留（未处理，需你确认后另开）

1. **子目标判定与成功判据矛盾**：T04/T05 的 8 条记录里环境判定 `task_success`，但同一记录的
   `final_subgoal_states` 仍为 `false`（如 `cream_cheese_1_placement`），而 BDDL 目标是两者皆成立。
   这会动摇"哪一步算完成、被撤销的是哪一个"，建议作为独立缺陷排查。
2. **process 证据字段**（`repair_step`、`old_subgoal_restore_count` 等）按你的指示作为**记录项**补充，
   不进入成功门控。
3. **用例重构**：`docs/pulse-series.md` 与讨论中的 s1→s2 依赖改造（优先 T00/T01/T02）尚未开工。