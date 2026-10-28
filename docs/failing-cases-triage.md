# 失效用例清单与修复建议

> **历史记录（勿按当前 catalog 解读）**：本文记录 失效用例分类 的实验，其中的用例总数（327 条）与逐条数字均为**当时口径**。2026-10-16 起 `progress-pulse-*`（24 条）已退出数据集（理由见 `archive/pulse-descoped-20261016/README.md`），当前 catalog 为 **288 条**。本文的数字未改写，以保证历史结论可追溯；需要当前口径时以 `docs/case-matrix-current.md` 与 `dataset/current/manifest.yaml` 为准。

数据来源：`runs/catalog-native-preflight-20261014-v11/summary.json`（327 条定义，原生端点预检）。本文只列**非「有效回滚」**的条目，并给出失效原因与是否有修复价值。

## 一、总览

| 分类 | 条数 | 是否有价值 |
| --- | ---: | --- |
| 有效 | 200 | — |
| 目标尚未完成 | 43 | 保留，换 seed |
| 穿透 | 39 | 保留（roll 族需重新论证） |
| 无合法原生边界对 | 8 | 保留，价值最高 |
| 触发未到达 | 7 | 保留，需协议支持 |
| 关系保持探针 | 7 | 保留，勿当作失效 |
| 动态驱动待验 | 5 | 保留，需独立 live |
| 对照 | 5 | — |
| 实体名未解析 | 4 | 已修复，需重验 |
| 关系未失效 | 3 | 保留为诊断证据 |
| 受保护接触 | 3 | 保留，属真实约束 |
| 基线失败 | 3 | 保留，换 seed |

合计 327 条。

## 二、逐类明细与修复建议

### 目标尚未完成（43 条）

- **判定**：保留，换 seed
- **原因**：该 seed/次序下撤销目标未完成
- **涉及任务**：03, 06
- **机制家族**：mid-offset-n3(2), mid-offset-n5(2), mid-offset-p3(2), mid-offset-p5(2), later-offset-n8(2), later-offset-p10(2), later-offset-p8(2), later-offset-r05(2), mid(2), early(2), later(2), first-moka-pot-stove-place-early(1), mid-offset-n8(1), mid-offset-p10(1), mid-offset-p8(1), mid-offset-r05(1), boundary-inside(1), boundary-outside(1), pair-moved(1), pulse-20(1), pulse-5(1), pulse-60(1), reference-moved(1), repeat-after-recovery(1), roll15-completed(1), roll30-completed(1), roll45-completed(1), roll60-completed(1), yaw180-completed(1), later-offset-n5(1), later-offset-p3(1), later-offset-p5(1)
- **修复建议**：任务 06 用 seed1（v12 已验证其 baseline 成功且 37 条预检齐备）；任务 03 同样用 seed1。这是 seed 次序问题，不是用例缺陷

| case_id | 任务 | 家族 | 窗口 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-03-first-moka-pot-stove-place-early-t0` | 03 | first-moka-pot-stove-place-early | t0 | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; completed so |
| `libero-10-03-first-moka-pot-stove-rollback-s1-later-offset-n8` | 03 | later-offset-n8 |  | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; completed so |
| `libero-10-03-first-moka-pot-stove-rollback-s1-later-offset-p10` | 03 | later-offset-p10 |  | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; completed so |
| `libero-10-03-first-moka-pot-stove-rollback-s1-later-offset-p8` | 03 | later-offset-p8 |  | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; completed so |
| `libero-10-03-first-moka-pot-stove-rollback-s1-later-offset-r05` | 03 | later-offset-r05 |  | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; completed so |
| `libero-10-03-first-moka-pot-stove-rollback-s1-mid-offset-n3` | 03 | mid-offset-n3 |  | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; completed so |
| `libero-10-03-first-moka-pot-stove-rollback-s1-mid-offset-n5` | 03 | mid-offset-n5 |  | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; completed so |
| `libero-10-03-first-moka-pot-stove-rollback-s1-mid-offset-p3` | 03 | mid-offset-p3 |  | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; completed so |
| `libero-10-03-first-moka-pot-stove-rollback-s1-mid-offset-p5` | 03 | mid-offset-p5 |  | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; completed so |
| `libero-10-06-cheese-butter-basket-rollback-s1-early-p1` | 06 | early | p1 | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-early-p2` | 06 | early | p2 | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-later-offset-n5` | 06 | later-offset-n5 |  | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-later-offset-n8` | 06 | later-offset-n8 |  | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-later-offset-p10` | 06 | later-offset-p10 |  | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-later-offset-p3` | 06 | later-offset-p3 |  | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-later-offset-p5` | 06 | later-offset-p5 |  | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-later-offset-p8` | 06 | later-offset-p8 |  | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-later-offset-r05` | 06 | later-offset-r05 |  | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-later-p1` | 06 | later | p1 | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-later-p2` | 06 | later | p2 | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-n3` | 06 | mid-offset-n3 |  | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-n5` | 06 | mid-offset-n5 |  | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-n8` | 06 | mid-offset-n8 |  | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-p10` | 06 | mid-offset-p10 |  | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-p3` | 06 | mid-offset-p3 |  | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-p5` | 06 | mid-offset-p5 |  | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-p8` | 06 | mid-offset-p8 |  | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-r05` | 06 | mid-offset-r05 |  | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-mid-p1` | 06 | mid | p1 | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-cheese-butter-basket-rollback-s1-mid-p2` | 06 | mid | p2 | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-progress-boundary-inside-mid` | 06 | boundary-inside | mid | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-progress-boundary-outside-mid` | 06 | boundary-outside | mid | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-progress-pair-moved-mid` | 06 | pair-moved | mid | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-progress-pulse-20-mid` | 06 | pulse-20 | mid | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-progress-pulse-5-mid` | 06 | pulse-5 | mid | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-progress-pulse-60-mid` | 06 | pulse-60 | mid | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-progress-reference-moved-mid` | 06 | reference-moved | mid | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-progress-repeat-after-recovery-mid` | 06 | repeat-after-recovery | mid | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-progress-roll15-completed-mid` | 06 | roll15-completed | mid | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-progress-roll30-completed-mid` | 06 | roll30-completed | mid | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-progress-roll45-completed-mid` | 06 | roll45-completed | mid | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-progress-roll60-completed-mid` | 06 | roll60-completed | mid | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |
| `libero-10-06-progress-yaw180-completed-mid` | 06 | yaw180-completed | mid | ValueError: target_subgoal 'cream_cheese_1_placement' has not completed; complet |

### 穿透（39 条）

- **判定**：保留（roll 族需重新论证）
- **原因**：目标位姿与容器/支撑几何冲突
- **涉及任务**：01, 02, 03, 04, 05, 07, 08
- **机制家族**：roll30-completed(7), roll45-completed(7), roll15-completed(6), roll60-completed(6), mid-pose-roll15(2), mid-pose-roll30(2), mid-pose-roll45(2), mid-pose-roll60(2), later-offset-r05(2), yaw180-completed(1), later-offset-n3(1), later-offset-n8(1)
- **修复建议**：roll 族：矩阵已说明转角不能证明失效，且容器内倾转必然穿透 → 建议删除或改为小型真值探针；r05 族：按抽屉/篮子几何重新标定偏移量，参照容器上方参数的做法

| case_id | 任务 | 家族 | 窗口 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-01-black-bowl-drawer-rollback-s1-later-offset-r05` | 01 | later-offset-r05 |  | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-01-black-bowl-drawer-rollback-s1-mid-pose-roll15` | 01 | mid-pose-roll15 |  | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-01-black-bowl-drawer-rollback-s1-mid-pose-roll30` | 01 | mid-pose-roll30 |  | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-01-black-bowl-drawer-rollback-s1-mid-pose-roll45` | 01 | mid-pose-roll45 |  | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-01-black-bowl-drawer-rollback-s1-mid-pose-roll60` | 01 | mid-pose-roll60 |  | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-01-progress-roll15-completed-mid` | 01 | roll15-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-01-progress-roll30-completed-mid` | 01 | roll30-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-01-progress-roll45-completed-mid` | 01 | roll45-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-01-progress-roll60-completed-mid` | 01 | roll60-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-01-progress-yaw180-completed-mid` | 01 | yaw180-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-02-progress-roll30-completed-mid` | 02 | roll30-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-02-progress-roll45-completed-mid` | 02 | roll45-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-02-progress-roll60-completed-mid` | 02 | roll60-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-02-yellow-rollback-s1-later-offset-n3` | 02 | later-offset-n3 |  | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-02-yellow-white-mug-microwave-rollback-s1-later-offset-n8` | 02 | later-offset-n8 |  | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-02-yellow-white-mug-microwave-rollback-s1-later-offset-r05` | 02 | later-offset-r05 |  | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-03-progress-roll15-completed-mid` | 03 | roll15-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-03-progress-roll30-completed-mid` | 03 | roll30-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-03-progress-roll45-completed-mid` | 03 | roll45-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-04-progress-roll15-completed-mid` | 04 | roll15-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-04-progress-roll30-completed-mid` | 04 | roll30-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-04-progress-roll45-completed-mid` | 04 | roll45-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-04-progress-roll60-completed-mid` | 04 | roll60-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-05-progress-roll15-completed-mid` | 05 | roll15-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-05-progress-roll30-completed-mid` | 05 | roll30-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-05-progress-roll45-completed-mid` | 05 | roll45-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-05-progress-roll60-completed-mid` | 05 | roll60-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-07-progress-roll15-completed-mid` | 07 | roll15-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-07-progress-roll30-completed-mid` | 07 | roll30-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-07-progress-roll45-completed-mid` | 07 | roll45-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-07-progress-roll60-completed-mid` | 07 | roll60-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-07-white-mug-left-plate-rollback-s1-mid-pose-roll15` | 07 | mid-pose-roll15 |  | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-07-white-mug-left-plate-rollback-s1-mid-pose-roll30` | 07 | mid-pose-roll30 |  | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-07-white-mug-left-plate-rollback-s1-mid-pose-roll45` | 07 | mid-pose-roll45 |  | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-07-white-mug-left-plate-rollback-s1-mid-pose-roll60` | 07 | mid-pose-roll60 |  | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-08-progress-roll15-completed-mid` | 08 | roll15-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-08-progress-roll30-completed-mid` | 08 | roll30-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-08-progress-roll45-completed-mid` | 08 | roll45-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |
| `libero-10-08-progress-roll60-completed-mid` | 08 | roll60-completed | mid | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_PENETRATIO |

### 无合法原生边界对（8 条）

- **判定**：保留，价值最高
- **原因**：未按原生谓词边界校准边界两侧位置
- **涉及任务**：01, 02, 04, 05
- **机制家族**：boundary-inside(4), boundary-outside(4)
- **修复建议**：这是矩阵 P1 的核心缺口：需按每个任务的 region 实际范围测量「恰好越界」与「界内」两个位置，而不是沿用初始位姿偏移

| case_id | 任务 | 家族 | 窗口 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-01-progress-boundary-inside-mid` | 01 | boundary-inside | mid | ValueError: NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR |
| `libero-10-01-progress-boundary-outside-mid` | 01 | boundary-outside | mid | ValueError: NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR |
| `libero-10-02-progress-boundary-inside-mid` | 02 | boundary-inside | mid | ValueError: NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR |
| `libero-10-02-progress-boundary-outside-mid` | 02 | boundary-outside | mid | ValueError: NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR |
| `libero-10-04-progress-boundary-inside-mid` | 04 | boundary-inside | mid | ValueError: NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR |
| `libero-10-04-progress-boundary-outside-mid` | 04 | boundary-outside | mid | ValueError: NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR |
| `libero-10-05-progress-boundary-inside-mid` | 05 | boundary-inside | mid | ValueError: NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR |
| `libero-10-05-progress-boundary-outside-mid` | 05 | boundary-outside | mid | ValueError: NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR |

### 触发未到达（7 条）

- **判定**：保留，需协议支持
- **原因**：成功后未出现完成的释放窗口
- **涉及任务**：01, 02, 09
- **机制家族**：initial-pose(3), both-goals(2), other-goal(2)
- **修复建议**：all-done 组依赖任务成功后的继续观察协议；需外部评测器在 success 后不终止并继续注入，属协议扩展而非用例修复

| case_id | 任务 | 家族 | 窗口 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-01-progress-both-goals-all-done` | 01 | both-goals | all-done |  |
| `libero-10-01-progress-initial-pose-all-done` | 01 | initial-pose | all-done |  |
| `libero-10-01-progress-other-goal-all-done` | 01 | other-goal | all-done |  |
| `libero-10-02-progress-both-goals-all-done` | 02 | both-goals | all-done |  |
| `libero-10-02-progress-initial-pose-all-done` | 02 | initial-pose | all-done |  |
| `libero-10-02-progress-other-goal-all-done` | 02 | other-goal | all-done |  |
| `libero-10-09-progress-initial-pose-all-done` | 09 | initial-pose | all-done |  |

### 关系保持探针（7 条）

- **判定**：保留，勿当作失效
- **原因**：设计预期即保持真值
- **涉及任务**：02, 03, 04, 05, 07, 08
- **机制家族**：yaw180-completed(6), roll15-completed(1)
- **修复建议**：yaw180 在轴对称物体上的设计预期即为保持真值；报告需单列，不计失效

| case_id | 任务 | 家族 | 窗口 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-02-progress-roll15-completed-mid` | 02 | roll15-completed | mid |  |
| `libero-10-02-progress-yaw180-completed-mid` | 02 | yaw180-completed | mid |  |
| `libero-10-03-progress-yaw180-completed-mid` | 03 | yaw180-completed | mid |  |
| `libero-10-04-progress-yaw180-completed-mid` | 04 | yaw180-completed | mid |  |
| `libero-10-05-progress-yaw180-completed-mid` | 05 | yaw180-completed | mid |  |
| `libero-10-07-progress-yaw180-completed-mid` | 07 | yaw180-completed | mid |  |
| `libero-10-08-progress-yaw180-completed-mid` | 08 | yaw180-completed | mid |  |

### 动态驱动待验（5 条）

- **判定**：保留，需独立 live
- **原因**：关节需独立 stepped episode
- **涉及任务**：00
- **机制家族**：s2-mid(1), function-boundary-inside(1), function-boundary-outside(1), s2-early(1), s2-later(1)
- **修复建议**：任务 00 的关节驱动必须走独立 stepped episode，原子关节重置不能替代动态路径验证

| case_id | 任务 | 家族 | 窗口 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-00-moka-pot-stove-rollback-s1-s2-early-p1` | 00 | s2-early | p1 | Joint drive requires an independent stepped episode |
| `libero-10-00-moka-pot-stove-rollback-s1-s2-later-p1` | 00 | s2-later | p1 | Joint drive requires an independent stepped episode |
| `libero-10-00-moka-pot-stove-rollback-s1-s2-mid-p1` | 00 | s2-mid | p1 | Joint drive requires an independent stepped episode |
| `libero-10-00-progress-function-boundary-inside-mid` | 00 | function-boundary-inside | mid | Joint drive requires an independent stepped episode |
| `libero-10-00-progress-function-boundary-outside-mid` | 00 | function-boundary-outside | mid | Joint drive requires an independent stepped episode |

### 对照（5 条）

- **判定**：—
- **原因**：设计预期为对照
- **涉及任务**：03, 05, 07, 08
- **机制家族**：boundary-inside(3), pair-moved(2)
- **修复建议**：—

| case_id | 任务 | 家族 | 窗口 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-03-progress-boundary-inside-mid` | 03 | boundary-inside | mid |  |
| `libero-10-05-progress-pair-moved-mid` | 05 | pair-moved | mid |  |
| `libero-10-07-progress-boundary-inside-mid` | 07 | boundary-inside | mid |  |
| `libero-10-08-progress-boundary-inside-mid` | 08 | boundary-inside | mid |  |
| `libero-10-08-progress-pair-moved-mid` | 08 | pair-moved | mid |  |

### 实体名未解析（4 条）

- **判定**：已修复，需重验
- **原因**：用例实体名与 profile 角色不符
- **涉及任务**：04, 07
- **机制家族**：mid-pair-moved(2), mid-ref-moved(2)
- **修复建议**：旧 4 条 reference 用 basket_1/plate_1，bridge 已改为按 profile 精确实体转 body 角色；需用新 runtime 复验绑定

| case_id | 任务 | 家族 | 窗口 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-04-soup-cheese-basket-rollback-s1-mid-pair-moved` | 04 | mid-pair-moved |  | RoleResolutionError: role 'basket_1' is not a resolved body |
| `libero-10-04-soup-cheese-basket-rollback-s1-mid-ref-moved` | 04 | mid-ref-moved |  | RoleResolutionError: role 'basket_1' is not a resolved body |
| `libero-10-07-white-mug-left-plate-rollback-s1-mid-pair-moved` | 07 | mid-pair-moved |  | RoleResolutionError: role 'plate_1' is not a resolved body |
| `libero-10-07-white-mug-left-plate-rollback-s1-mid-ref-moved` | 07 | mid-ref-moved |  | RoleResolutionError: role 'plate_1' is not a resolved body |

### 关系未失效（3 条）

- **判定**：保留为诊断证据
- **原因**：该机制在此任务上不改变原生谓词
- **涉及任务**：01, 04, 07
- **机制家族**：mid-pose-spin180(3)
- **修复建议**：记录「该机制不改变此任务的原生谓词」，是有效结论，不是缺陷

| case_id | 任务 | 家族 | 窗口 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-01-black-bowl-drawer-rollback-s1-mid-pose-spin180` | 01 | mid-pose-spin180 |  | ValueError: invalid completed-subgoal rollback: ROLLBACK_DID_NOT_INVALIDATE_SUBG |
| `libero-10-04-soup-cheese-basket-rollback-s1-mid-pose-spin180` | 04 | mid-pose-spin180 |  | ValueError: invalid completed-subgoal rollback: ROLLBACK_DID_NOT_INVALIDATE_SUBG |
| `libero-10-07-white-mug-left-plate-rollback-s1-mid-pose-spin180` | 07 | mid-pose-spin180 |  | ValueError: invalid completed-subgoal rollback: ROLLBACK_DID_NOT_INVALIDATE_SUBG |

### 受保护接触（3 条）

- **判定**：保留，属真实约束
- **原因**：目标位姿与受保护物体接触
- **涉及任务**：03, 05
- **机制家族**：early-offset-r05(1), mid-offset-r05(1), later-offset-r05(1)
- **修复建议**：injection 与受保护物体的接触是合法拒绝；可尝试其他触发窗口

| case_id | 任务 | 家族 | 窗口 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-03-first-rollback-s1-early-offset-r05` | 03 | early-offset-r05 |  | ValueError: ROLLBACK_CONTACTS_PROTECTED_BODY |
| `libero-10-05-soup-sauce-basket-rollback-s1-later-offset-r05` | 05 | later-offset-r05 |  | ValueError: ROLLBACK_CONTACTS_PROTECTED_BODY |
| `libero-10-05-soup-sauce-basket-rollback-s1-mid-offset-r05` | 05 | mid-offset-r05 |  | ValueError: ROLLBACK_CONTACTS_PROTECTED_BODY |

### 基线失败（3 条）

- **判定**：保留，换 seed
- **原因**：该 seed 下基线任务未完成
- **涉及任务**：06
- **机制家族**：both-goals(1), initial-pose(1), other-goal(1)
- **修复建议**：任务 03/06 的 baseline 在 seed0 下失败（06 是 butter 先完成而 cream_cheese 未完成）；seed1 下均成功

| case_id | 任务 | 家族 | 窗口 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-06-progress-both-goals-all-done` | 06 | both-goals | all-done |  |
| `libero-10-06-progress-initial-pose-all-done` | 06 | initial-pose | all-done |  |
| `libero-10-06-progress-other-goal-all-done` | 06 | other-goal | all-done |  |

