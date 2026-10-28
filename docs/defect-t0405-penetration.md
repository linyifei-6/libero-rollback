# 缺陷排查：回滚目标位姿穿透导致注入被拒（系统性）

> **历史记录（勿按当前 catalog 解读）**：本文记录 回滚目标位姿穿透缺陷排查 的实验，其中的用例总数（312 条 catalog）与逐条数字均为**当时口径**。2026-10-16 起 `progress-pulse-*`（24 条）已退出数据集（理由见 `archive/pulse-descoped-20261016/README.md`），当前 catalog 为 **288 条**。本文的数字未改写，以保证历史结论可追溯；需要当前口径时以 `docs/case-matrix-current.md` 与 `dataset/current/manifest.yaml` 为准。

本文记录 mid 窗口评测中 80 条注入无效用例的排查、根因与**系统性修复**。

- 现象：`INTERVENTION_ACTIVATION_FAILED / ROLLBACK_PATHOLOGICAL_PENETRATION`
- 影响面：mid 窗口 80 条无效中 **64 条**属此类（`apply_episode_initial_offset` 20、
  `displace_from_completed_pose` 34、`restore_episode_initial_pose` 10），
  涉及全 catalog **284 条**使用同一处理器的用例
- 结论：注入本身是"把物体写到一个从未做过碰撞检查的位姿"，其中一部分位姿与物体原本
  搁置的表面相交；评测器按 `no_object_penetration` 约束正确拒绝，但**拒绝率本可以更低**——
  缺的是"搜索一个合法目标位姿"的能力，而不是放松规则

## 一、mid 窗口注入无效的完整分布（修复前）

| 机制 | 用例 | 注入有效 | 无效 | 无效原因 |
| --- | ---: | ---: | ---: | --- |
| `apply_episode_initial_offset` | 60 | 36 | 24 | 穿透 20、目标未完成 4 |
| `displace_from_completed_pose` | 45 | 11 | 34 | 全部穿透 |
| `restore_episode_initial_pose` | 40 | 30 | 10 | 全部穿透 |
| `displace_to_relation_boundary` | 18 | 6 | 12 | 无合法原生边界对 |
| `translate_relation_pair` | 5 | 5 | 0 | — |
| `displace_reference_object` | 5 | 5 | 0 | — |
| `restore_container_above_pose` | 4 | 4 | 0 | — |
| `revert_articulation_goal` | 3 | 3 | 0 | — |
| **合计** | **180** | **100** | **80** | 穿透 64、目标未完成 4、无合法边界对 12 |

三类原因性质不同：

1. **穿透 64 条** —— 本缺陷，可修（目标位姿搜索）。
2. **目标未完成 4 条** —— 用例的 `target_subgoal` 在该 seed/窗口下尚未达成；属用例与
   seed 匹配问题，不是注入实现问题。
3. **无合法原生边界对 12 条** —— `displace_to_relation_boundary` 在封闭容器里找不到
   "恰好越界/界内"的合法配对；用例 `open_questions` 明确要求**不得靠跳过碰撞来凑数**，
   属真实几何约束，保持拒绝。

## 二、实测证据（修复前）

以 `libero-10-04-progress-pulse-20-mid` 为例，触发步 162 写入回滚位姿后：

```
ROLLBACK_PATHOLOGICAL_PENETRATION (penetration_m=0.015350 > 0.005000)
  penetration_bodies = ["living_room_table_col"]   ← 桌面
  position_error_m   = 0.0
  target_position    = [0.03972, -0.10056, 0.45999]
```

| 项 | 数值 |
| --- | --- |
| 实测穿透 | **15.35 mm** |
| 预算 | 5.00 mm（severity 参数 `maximum_penetration_m`，任务无关） |
| 超出 | 3.07×（真实几何重叠） |
| 碰撞体 | 桌面 `living_room_table_col`，不是篮筐 |
| 位置误差 | 0.0（位姿可达，问题在碰撞） |
| 任务 05 | 完全相同（15.35 mm、同一碰撞体） |

## 三、两处根因（都在代码里，不是数据）

### 根因 1：`initial_state` 记录的"初始位姿"不是回合初始位姿

`RuntimeContext.__init__`（`libero_runtime/engine/context.py`）在 **环境 reset 之后、
稳定化控制步之后**才读取 `body_xpos/body_xquat` 作为 `initial_state`。零动作实测（任务 137，
目标物体 `alphabet_soup_1`）：

| 时刻 | 物体位置 |
| --- | --- |
| reset 瞬间（冻结 qpos） | `[0.028, -0.109, 0.460]` |
| reset 后 1 步 | `z = 0.4638` |
| reset 后 5 步 | `z = 0.4786` |
| reset 后 25 步 | `z = 0.5429` |

物体在**没有任何指令**的情况下被抬升 —— 因为它初始就被放在略微嵌入桌面的位置，
MuJoCo 的软约束把它推开。于是：

- `restore_episode_initial_pose` 想表达"回合初始位姿"，实际拿到的是"稳定化若干步之后的位姿"；
- 同一用例同一触发步，预检记录 `z = 0.6278`（通过），live 运行记录 `z = 0.4600`（穿透 15.35 mm）。

**修法**：`RuntimeContext` 已保存 reset 瞬间的冻结 qpos（`_rollback_initial_qpos`），
现为每个自由体解析出 `rollback_initial` 位姿并随 `initial_state` 提供；
`initial_pose` / `initial_offset` 两个目标类型改读冻结位姿（观测值保留，供抬升量等指标使用）。

### 根因 2：从没有任何"目标位姿可达性"检查或搜索

处理器的目标位姿来自"记录值 / 解析值 / 实测值 + 偏移"，**写入前不做碰撞查询**，
写入后才发现穿透并整体拒绝。除 `relation_boundary` 与 `container_above` 自带净空扫描外，
`initial_pose`、`initial_offset`、`completed_offset`、`checkpoint` 都没有任何搜索。

**修法**：新增共享工具 `libero_runtime/engine/interventions/pose_clearance.py`，
对所有自由体目标类型做**有界 +Z 搜索**：按 `target_lift_step_m` 步进、
上限 `target_lift_max_m`，取最低的满足穿透预算的高度；预算耗尽则恢复原位姿并如实拒绝。
搜索过程逐档记入证据（`clearance_search`），最终位姿与抬升量（`target_lift_m`）一并记录。

## 四、代码改动清单

| 文件 | 改动 |
| --- | --- |
| `libero_runtime/engine/context.py` | 新增 `_rollback_pose()`：从冻结 reset qpos 解析自由体位姿；`initial_state[role]` 增加 `rollback_initial` |
| `libero_runtime/engine/interventions/pose_clearance.py` | **新增**：共享的有界净空搜索（含轨迹记录、预算耗尽回退） |
| `libero_runtime/engine/interventions/completed_subgoal_rollback.py` | ①`initial_pose`/`initial_offset` 改读冻结位姿；②删除内联抬升逻辑，改用共享工具；③搜索覆盖所有自由体目标类型；④抛出异常时保留 validator 的完整 detail 与结构化 `evidence`；⑤白名单放行 `target_lift_max_m`/`target_lift_step_m` |
| `src/libero_rollback/runtime.py` | 对 `destination == "initial_pose"` 与 `"initial_offset"` 默认写出有界搜索参数（默认 0.05 m / 0.002 m，可在用例里覆盖） |

其中第 ④ 项本身是**可诊断性缺陷**：处理器原来只拼错误**名**，把 validator 已经算出的
`penetration_m`、`penetration_bodies`、`position_error_m` 全部丢弃，导致 64 条用例的证据里
只剩一个光秃秃的错误名，无法定位。

## 五、修复验证

**单例（`libero-10-04-progress-pulse-20-mid`，live 配对）**：

| 上抬 | 实测穿透 |
| ---: | ---: |
| 0.000 | 0.01535（拒绝） |
| 0.004 | 0.01135 |
| 0.008 | 0.00735 |
| 0.010 | 0.00535 |
| **0.012** | **0.00335（通过）** |

- `injection_valid = true`，注入步 162，关系真→假（`post_predicate=false`）
- 基线成功 238 步；扰动 episode 成功 **236 步** → 模型确实恢复了
- 上抬 12 mm，罐头仍在 x,y 方向远离篮筐（写入点 y≈−0.10，篮筐足迹 y∈[0.19,0.34]），
  失效语义未被破坏

**T04/T05 全 10 条（`--severity d0 --window mid --task 04 --task 05`）**：已在新参数下
重跑，全部 `injection_valid = true`，rc=0。

**全量**：173 条 mid 用例在修复后的 runtime 上重跑（`runs/eval-mid-d0-pi05-fixed`、
`runs/eval-mid-rest-pi05-fixed`），修复前结果保留在 `runs/eval-mid-d0-pi05`、
`runs/eval-mid-rest-pi05` 以便逐条对照。

## 六、未改动 / 保留拒绝

1. **`displace_to_relation_boundary` 的 12 条**：封闭容器内不存在合法的"恰好越界"配对。
   用例 `open_questions` 明确"不得靠跳过碰撞来凑数"，保持拒绝；如需覆盖该维度，应改从
   垂直方向或容器开口方向搜索边界（`docs/verification-report-v13.md` 第六节）。
2. **4 条"目标未完成"**：属用例 `target_subgoal` 与 seed/窗口的匹配问题，需用例侧确认。
3. **`revert_articulation_goal`**：关节回退走 `articulation_setback`，其穿透校验是
   **增量**穿透（`max_incremental_penetration_m`，相对基线接触），不是"把物体瞬移进表面"，
   与本缺陷无关，未改动。
4. **`rigid_body_displace` / `dynamic_scene_occupancy` / `moving_obstacle`**：当前 catalog
   不使用这些处理器（它们各自已有净空/边界搜索逻辑），本次未改动；若将来启用，应复用
   `pose_clearance.ClearanceSearch`。
5. **`initial_state` 语义的其余使用者**：`manipulated_object` 别名与"物体是否被抬起"的
   判据仍用观测位姿，这是它们本来的用途（相对漂移量），未改动。