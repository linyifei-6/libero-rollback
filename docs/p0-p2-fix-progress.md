# P0–P2 修复进展与结论

> **历史记录（勿按当前 catalog 解读）**：本文记录 P0–P2 修复进展 的实验，其中的用例总数（327 条）与逐条数字均为**当时口径**。2026-10-16 起 `progress-pulse-*`（24 条）已退出数据集（理由见 `archive/pulse-descoped-20261016/README.md`），当前 catalog 为 **288 条**。本文的数字未改写，以保证历史结论可追溯；需要当前口径时以 `docs/case-matrix-current.md` 与 `dataset/current/manifest.yaml` 为准。

依据用户指示（P0–P1 按建议修复；P2 roll 族需评估测试价值后再决定）。
本文更正此前基于 v11 单一文件的统计口径。

## 一、统计口径更正：应取 v11 + v12 并集

两次原生预检使用了不同的 seed 与修复版本，**每条用例应取两次中的最佳状态**：

| 状态 | v11 | v12 | 并集 |
| --- | ---: | ---: | ---: |
| 真→假端点（有效回滚） | 200 | 88 | **227** |
| 对照 | 5 | 4 | **8** |
| 保持关系探针 | 7 | 3 | **8** |
| 拒绝 | 66 | 26 | **72** |
| 触发未到达 | 7 | 0 | **7** |
| 动态待验 | 5 | 0 | **5** |

物理有效（回滚 + 对照 + 探针）**243 / 327**；仍未获得有效注入 **79 条**。

## 二、P0 结论：两条均已由既有 v12 批次完成，无需再修

### P0-1 换 seed —— 实际已完成

- **任务 06**：34 条在 v11（seed0）为 `baseline_failed`，在 **v12（seed1）已修复** ——
  30 条 rollback、3 条因穿透/边界被拒、1 条探针、1 条对照。文档记录 06 seed1 基线成功。
- **任务 03**：**并非全部失败**。v11 下 36 条中有 **21 条 rollback + 13 条 rejected
  + 1 control + 1 probe`**。其 9 条「目标未完成」在 v11 已是 `preflight_rejected`
  （原因文本与状态列不一致，状态列才是权威）。

**更正**：此前「43 条需换 seed」的判断基于 v11 单文件，高估了范围。实际需要新批次验证的
只有任务 03 的 9 条（v12 未运行任务 03）。

### P0-2 reference 实体名 —— 已复验

v11 中 4 条报 `role 'basket_1'/'plate_1' is not a resolved body`；**v12 已复验**：

| 用例 | v11 | v12 |
| --- | --- | --- |
| 04 `ref-moved` | RoleResolutionError | **preflight_rollback** |
| 04 `pair-moved` | RoleResolutionError | **preflight_control** |
| 07 `ref-moved` / `pair-moved` | RoleResolutionError | 已由 v12 复验（文档记录 2 rollback + 2 control） |

旧绑定证据已被取代，无需重跑。

## 三、P2 roll 族：**有测试价值，需修复**（用户判断正确）

### 该维度在测什么

用例文件的 `expected_evaluation_semantics` 是 **`relation_only`**，
`open_questions` 写明：

> "Rotation is a truth probe: classify relation-preserving control or rollback from
> native pre/post truth; **never infer failure from angle alone**."

即：**s1 完成后改变已完成对象在容器内的位姿，探测评测对象是否误报**。
它与「失效对」互补 —— 失效对测"该报没报"，本组测"**不该报却报了**"的假阳性。
所以此前把它当失效机制评判是错的。

### 为什么当前全部被拒

| 子族 | 现象 | 原因 |
| --- | --- | --- |
| `roll15/30/45/60` | `ROLLBACK_PATHOLOGICAL_PENETRATION` | 姿态写入**只改朝向、不改位置**，碗在抽屉内倾转必然撞壁，15° 就穿透 |
| `yaw180`（7 条） | `ROLLBACK_DID_NOT_INVALIDATE_SUBGOAL` | 绕竖直轴旋转轴对称物体，关系**本就保持为真** —— 这是**预期结果**，但 handler 仍按"必须失效"校验，把探针当失败拒掉 |

### 两个需要修的实现缺陷

1. **handler 未尊重 `relation_only` 语义**（影响 7–8 条探针，最易修）
   `ROLLBACK_DID_NOT_INVALIDATE_SUBGOAL` 对"真值探针"是**预期结果**，应登记为
   `preflight_relation_preserving_probe` 而非拒绝。判据是
   `expected_evaluation_semantics == "relation_only"`。

2. **roll 族需改为「先抬升再倾转」**（影响 38 条，用户建议的方向）
   当前 `displace_from_completed_pose` 只写单一目标位姿，`offset_m=[0,0,0]`。
   应允许**同时给出位移与旋转**：先把碗抬到抽屉内较高处（仍满足 `In`），
   再倾转，避免与抽屉壁穿透。
   注意用例的 `open_questions` 已声明："A horizontal legal pair may not exist for
   enclosed drawer/microwave or basket walls; **retain rejection rather than skipping
   collisions**" —— 即**不得靠跳过碰撞来凑数**，需真实找到合法位姿。

### 建议的修复顺序

1. 先修缺陷 1（判据一行），使 7–8 条探针立即变为有效探针；
2. 再为 roll 族标定"抬升高度 + 倾转角"组合：抬升量以碗底离开抽屉壁顶为界，
   倾转角从小角度递进，逐任务记录首个可容纳的角度；
3. 若某任务在抽屉几何下确实不存在合法位姿，**保留拒绝并记录**，不放松碰撞规则。

## 四、P1 未完成：boundary 族（8 条，矩阵核心缺口）

任务 01/02/04/05 的 `boundary-inside`/`boundary-outside` 各 2 条，
报 `NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR`。

**需要的实现**：
1. 从 `context` 读取 `goal_state_name` 对应 region 的实际范围（矩形 `xyrange` 或 site 半径）；
2. 计算「恰好越界」（越界量 = region 半径 + 对象半径 + ε）与「恰好界内」两个位置；
3. `On`（object-on-object）用水平中心距离阈值 **0.03 m**（矩阵给出该实现常量位置）；
4. **每个任务独立校准**，不复制其他任务的绝对坐标；
5. 越界位置需通过穿透与保护目标校验。

## 五、仍未解决的 79 条

| 状态 | 条数 |
| --- | ---: |
| 拒绝（穿透 / 边界 / 接触 / 未失效） | 72 |
| 触发未到达（all-done 组） | 7 |

| 任务 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 未解决 | 16 | 11 | 13 | 7 | 8 | 10 | 9 | 4 | 1 |

其中 `trigger_not_reached` 的 7 条需要**外部评测器支持「success 后不终止并继续注入」**，
属协议扩展而非用例修复。
