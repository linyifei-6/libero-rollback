# Base-rollback · static-init 消融（Goal L0/L1/L2）

> 日期：2026-11-20 ｜ 模型：π0.5（`pi05_libero`）｜ 报告：[experiments/b-rollback-static-20261120/index.html](../experiments/b-rollback-static-20261120/index.html)

## 0. 命名

- **base-rollback**：非 plus 的 B v2 矩阵，`dataset/matrices/b-matrix.csv`（442 条）。
- **plus-rollback**：LIBERO-Plus O2 版本，`dataset/matrices/b-matrix-plus.csv`（1,394 条）。

本实验是 **base-rollback** 的消融，不是 plus-rollback。

## 1. 目的

B v2 的 rollback 失败可能有两种解释：

1. **rollback / 完成上下文**导致模型无法恢复；
2. 被撤销到的 **L0/L1 target pose 本身**就难（偏移太大、不可达、目标不可见）。

static-init 消融把同一 L0/L1 target pose 在 **t=0** 注入，让 π0.5 从一开始就看到它；如果静态条件下成功率高，而 all_done 回滚后 recovery 低，失败就应归因于 rollback/history，而不是 target offset。

## 2. 设计

| 项 | 值 |
|---|---|
| suite | Goal |
| cases | 75（L0 12 + L1 36 + L2 27；覆盖 10 个 task） |
| policy | π0.5，frozen |
| 预算 | `max_steps=600`；首次成功后停止 |
| 注入 | t=0 写 L0/L1/L2 target pose；settle 10 步；**不触发 all_done、不回滚** |
| seed / init | 0 / row 0 |
| 视频 | 20 fps |

L0 在 t=0 等价于“target 在 init、无扰动”的基线；L1 是“target 从 t=0 就平移 3/6/10 cm”的静态扰动；L2 是“target 从 t=0 就绕 z 轴 yaw 30/60/90°”的静态扰动。rollback 对照来自 base-rollback 的 Goal all_done 结果（同 L0/L1/L2 定义）。

## 3. 结果

| 条件 | 成功/恢复 | rate |
|---|---:|---:|
| Static L0（无扰动） | **12/12** | **100%** |
| Static L1（free object, raw） | **22/27** | **81.5%** |
| Static L1（valid only） | **27/30** | **90.0%** |
| Static L1（joint，no-op bug） | **9/9** | **100%（无效）** |
| Static L1（raw，含 no-op） | 31/36 | 86.1%（不能作为结论） |
| Static L2（init yaw） | **26/27** | **96.3%** |
| Rollback L0（Goal, base） | **3/10** | **30.0%** |
| Rollback L1（Goal, base） | **13/33** | **39.4%** |
| Rollback L2（Goal, base） | **5/25** | **20.0%** |

按 L1 δ：

| δ | Static success | Rollback recovery |
|---|---:|---:|
| 3 cm | 11/12 = 91.7% | 4/11 = 36.4% |
| 6 cm | 10/12 = 83.3% | 5/11 = 45.5% |
| 10 cm | 10/12 = 83.3% | 4/11 = 36.4% |

按 L2 yaw：

| yaw | Static success | Rollback recovery |
|---|---:|---:|
| 30° | 9/9 = 100% | 1/9 = 11.1% |
| 60° | 9/9 = 100% | 3/9 = 33.3% |
| 90° | 8/9 = 88.9% | 1/7 = 14.3% |

Static L1 有 6 条 `zero_velocity_after_intervention=False`（settle 10 步后目标仍在动），无 penetration；其中 5 条仍然 success。valid-only 口径与 raw 结论一致。

## 3.1 审计修正（2026-11-20）

复核视频发现 Goal L1 的 36 条里有 **9 条 joint-target case 的 `q_applied=0`**：

- `b-goal-t000-g-l1-d03/d06/d10`（cabinet middle）
- `b-goal-t030-pre-l1-d03/d06/d10`（cabinet top，pre）
- `b-goal-t270-g-l1-d03/d06/d10`（cabinet）

原因：`_apply_joint_ratio` 的 span 是“init → all_done 已达成的关节值”；在 t=0 尚未完成，span=0，ratio 扰动退化为 no-op。视频里当然没有位移。

- **L0 本来就没有扰动**：它是 baseline，不是 injected perturbation。
- **L1 free-object 27 条**有真实 3/6/10 cm 位移，22/27 成功（81.5%）。
- **L2 27 条**全部有 yaw 位移，26/27 成功（96.3%）。
- 因此旧 L1 raw 86.1% 被 9 条 no-op 抬高；**真实 free-object static L1 是 81.5%**，仍显著高于 rollback L1 29.2%（free 24 条中 7 条恢复）。
- joint L1 已改成“goal-side limit”静态目标并 smoke 验证（cabinet q_applied=-0.016），但这 9 条旧结果需要重跑后才能进入结论。

## 4. 解释

- **Static L0 100%**：target 在 init 时，π0.5 能正常完成任务。
- **Static L1 free 81.5%**：target 在 t=0 被平移 3–10 cm 时，π0.5 仍大多能完成；10 cm 也没有明显崩溃。
- **Static L2 96.3%**：yaw 30/60/90° 在 t=0 也几乎都能完成；90° 仅 1 条失败。
- **Rollback L1 39.4% / L2 20.0%**：同一个 target pose，在任务完成后再回滚，恢复率显著下降。
- 因此在本实验里，**rollback 失败主要不能归因于 target offset / 可达性**，而更符合“完成后 history/上下文导致不回补”的解释。
- 这是消融证据，不是严格因果证明：static 与 rollback 的 robot pose、其他物体、policy history 仍不同；要完全分离 history 需要 `fresh-state`（同完成态 + 目标 O2 + 空 history）。

## 5. 限制

- 单 seed、单 init；48 条点估计，L0 只有 12 条。
- static 与 rollback 的预算/停止规则不同：static 首次成功即停，rollback 跑完整窗口；只比较同 level 的率，不比较步数。
- static L1 的 6 条 invalid 是 settle 后未静止，不是 target pose 不可达；报告同时给 raw 与 valid-only。
- 该实验只覆盖 Goal；Object/Spatial 的静态消融尚未跑。
- L2 是 yaw 扰动，和 L1 的平移不是同一维度；静态/rollback 都按各自 level 的 nominal 参数执行。

## 6. exact static 全量（2026-11-21）

joint L1 已改为写入 rollback 实际 q_applied；L10 free 写入 rollback snapshot_after；覆盖全部 402 个 base-rollback 回滚位置（C0 除外）。

| suite | static success | valid success/valid | rollback recovery |
|---|---:|---:|---:|
| Goal | 68/75 = 90.7% | 65/69 = 94.2% | 21/68 = 30.9% |
| Object | 59/70 = 84.3% | 58/63 = 92.1% | 2/69 = 2.9% |
| Spatial | 61/70 = 87.1% | 54/57 = 94.7% | 22/70 = 31.4% |
| L10 | 140/187 = 74.9% | 138/183 = 75.4% | 42/181 = 23.2% |
| **合计** | **328/402 = 81.6%** | **315/372 = 84.7%** | **87/388 = 22.4%** |

- joint L1 9 条已与 rollback 对齐，例如 -goal-t000-g-l1-d03 q_applied=-0.016015。
- static 与 rollback 同 suite/level 下差距仍然很大；target pose/yaw 本身不是主要瓶颈。
- 报告：[experiments/b-rollback-static-exact-20261121/index.html](../experiments/b-rollback-static-exact-20261121/index.html)

