# 失效用例修复进展（v11+v12 并集口径）

> **历史记录（勿按当前 catalog 解读）**：本文记录 失效用例修复进展（v11+v12 并集） 的实验，其中的用例总数（327 条）与逐条数字均为**当时口径**。2026-10-16 起 `progress-pulse-*`（24 条）已退出数据集（理由见 `archive/pulse-descoped-20261016/README.md`），当前 catalog 为 **288 条**。本文的数字未改写，以保证历史结论可追溯；需要当前口径时以 `docs/case-matrix-current.md` 与 `dataset/current/manifest.yaml` 为准。

本文取代 `failing-cases-triage.md` 中基于 v11 单一文件的统计。
每条用例取 v11、v12 两次原生预检中的**最佳状态**，因为两次使用了不同的 seed/修复版本。

## 一、并集总览

| 状态 | 条数 | 含义 |
| --- | ---: | --- |
| preflight_rollback | 227 | 端点合法、原生关系真→假（有效回滚） |
| preflight_rejected | 72 | 端点被拒（穿透/边界/接触等） |
| preflight_relation_preserving_probe | 8 | 真值探针，关系保持（非失效） |
| preflight_control | 8 | 设计即对照，关系保持为真 |
| trigger_not_reached | 7 | 成功后未出现释放窗口 |
| requires_dynamic_drive_validation | 5 | 关节驱动需独立 stepped episode |

合计 **327** 条；其中物理有效（回滚/对照/探针）**243** 条，仍未获得有效注入 **79** 条。

## 二、P0 结论：已完成，无需再修

原 P0 判断基于 v11 单文件，高估了范围：

| 原以为 | 实际 |
| --- | --- |
| 43 条「目标尚未完成」需换 seed | **任务 06 已由 v12 + seed1 修复**（37 条从 baseline_failed 变为 30 rollback / 3 rejected / 1 probe / 1 control）；**任务 03 在 v11 本就有 21 rollback + 13 rejected**，并非全部失败 |
| 4 条 reference 实体名未解析 | **v12 已复验**：04 的 ref-moved=rollback、pair-moved=control；旧绑定证据已被取代 |

两条 P0 均已由既有 v12 批次完成，**不需要重跑**。

## 三、仍未解决：79 条

| 状态 | 条数 |
| --- | ---: |
| preflight_rejected | 72 |
| trigger_not_reached | 7 |

| 任务 | 未解决条数 |
| --- | ---: |
| 01 | 16 |
| 02 | 11 |
| 03 | 13 |
| 04 | 7 |
| 05 | 8 |
| 06 | 10 |
| 07 | 9 |
| 08 | 4 |
| 09 | 1 |

### 按原因归类与修复建议

### 穿透 —— roll 族与个别偏移档（39 条）

- **修复建议**：roll 族需「先抬升再倾转」（见第四节）；偏移档按容器几何重标定

| case_id | 任务 | v11 | v12 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-01-black-bowl-drawer-rollback-s1-later-offset-r05` | 01 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-01-black-bowl-drawer-rollback-s1-mid-pose-roll15` | 01 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-01-black-bowl-drawer-rollback-s1-mid-pose-roll30` | 01 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-01-black-bowl-drawer-rollback-s1-mid-pose-roll45` | 01 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-01-black-bowl-drawer-rollback-s1-mid-pose-roll60` | 01 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-01-progress-roll15-completed-mid` | 01 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-01-progress-roll30-completed-mid` | 01 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-01-progress-roll45-completed-mid` | 01 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-01-progress-roll60-completed-mid` | 01 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-01-progress-yaw180-completed-mid` | 01 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-02-progress-roll30-completed-mid` | 02 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-02-progress-roll45-completed-mid` | 02 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-02-progress-roll60-completed-mid` | 02 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-02-yellow-rollback-s1-later-offset-n3` | 02 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-02-yellow-white-mug-microwave-rollback-s1-later-offset-n8` | 02 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-02-yellow-white-mug-microwave-rollback-s1-later-offset-r05` | 02 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-03-progress-roll15-completed-mid` | 03 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-03-progress-roll30-completed-mid` | 03 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-03-progress-roll45-completed-mid` | 03 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-04-progress-roll15-completed-mid` | 04 | preflight_rejected | preflight_rejected | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-04-progress-roll30-completed-mid` | 04 | preflight_rejected | preflight_rejected | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-04-progress-roll45-completed-mid` | 04 | preflight_rejected | preflight_rejected | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-04-progress-roll60-completed-mid` | 04 | preflight_rejected | preflight_rejected | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-05-progress-roll15-completed-mid` | 05 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-05-progress-roll30-completed-mid` | 05 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-05-progress-roll45-completed-mid` | 05 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-05-progress-roll60-completed-mid` | 05 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-07-progress-roll15-completed-mid` | 07 | preflight_rejected | preflight_rejected | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-07-progress-roll30-completed-mid` | 07 | preflight_rejected | preflight_rejected | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-07-progress-roll45-completed-mid` | 07 | preflight_rejected | preflight_rejected | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-07-progress-roll60-completed-mid` | 07 | preflight_rejected | preflight_rejected | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-07-white-mug-left-plate-rollback-s1-mid-pose-roll15` | 07 | preflight_rejected | preflight_rejected | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-07-white-mug-left-plate-rollback-s1-mid-pose-roll30` | 07 | preflight_rejected | preflight_rejected | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-07-white-mug-left-plate-rollback-s1-mid-pose-roll45` | 07 | preflight_rejected | preflight_rejected | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-07-white-mug-left-plate-rollback-s1-mid-pose-roll60` | 07 | preflight_rejected | preflight_rejected | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-08-progress-roll15-completed-mid` | 08 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-08-progress-roll30-completed-mid` | 08 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-08-progress-roll45-completed-mid` | 08 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |
| `libero-10-08-progress-roll60-completed-mid` | 08 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_PATHOLOGICAL_ |

### 目标尚未完成（19 条）

- **修复建议**：确认对应 seed 已启用

| case_id | 任务 | v11 | v12 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-03-first-moka-pot-stove-place-early-t0` | 03 | preflight_rejected | not_run | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; co |
| `libero-10-03-first-moka-pot-stove-rollback-s1-later-offset-n8` | 03 | preflight_rejected | not_run | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; co |
| `libero-10-03-first-moka-pot-stove-rollback-s1-later-offset-p10` | 03 | preflight_rejected | not_run | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; co |
| `libero-10-03-first-moka-pot-stove-rollback-s1-later-offset-p8` | 03 | preflight_rejected | not_run | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; co |
| `libero-10-03-first-moka-pot-stove-rollback-s1-later-offset-r05` | 03 | preflight_rejected | not_run | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; co |
| `libero-10-03-first-moka-pot-stove-rollback-s1-mid-offset-n3` | 03 | preflight_rejected | not_run | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; co |
| `libero-10-03-first-moka-pot-stove-rollback-s1-mid-offset-n5` | 03 | preflight_rejected | not_run | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; co |
| `libero-10-03-first-moka-pot-stove-rollback-s1-mid-offset-p3` | 03 | preflight_rejected | not_run | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; co |
| `libero-10-03-first-moka-pot-stove-rollback-s1-mid-offset-p5` | 03 | preflight_rejected | not_run | ValueError: target_subgoal 'moka_pot_1_on_stove' has not completed; co |
| `libero-10-06-cheese-butter-basket-rollback-s1-later-offset-n8` | 06 | baseline_failed | preflight_rejected | ValueError: target_subgoal 'cream_cheese_1_placement' has not complete |
| `libero-10-06-cheese-butter-basket-rollback-s1-later-offset-r05` | 06 | baseline_failed | preflight_rejected | ValueError: target_subgoal 'cream_cheese_1_placement' has not complete |
| `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-n8` | 06 | baseline_failed | preflight_rejected | ValueError: target_subgoal 'cream_cheese_1_placement' has not complete |
| `libero-10-06-cheese-butter-basket-rollback-s1-mid-offset-r05` | 06 | baseline_failed | preflight_rejected | ValueError: target_subgoal 'cream_cheese_1_placement' has not complete |
| `libero-10-06-progress-boundary-inside-mid` | 06 | baseline_failed | preflight_rejected | ValueError: target_subgoal 'cream_cheese_1_placement' has not complete |
| `libero-10-06-progress-boundary-outside-mid` | 06 | baseline_failed | preflight_rejected | ValueError: target_subgoal 'cream_cheese_1_placement' has not complete |
| `libero-10-06-progress-roll15-completed-mid` | 06 | baseline_failed | preflight_rejected | ValueError: target_subgoal 'cream_cheese_1_placement' has not complete |
| `libero-10-06-progress-roll30-completed-mid` | 06 | baseline_failed | preflight_rejected | ValueError: target_subgoal 'cream_cheese_1_placement' has not complete |
| `libero-10-06-progress-roll45-completed-mid` | 06 | baseline_failed | preflight_rejected | ValueError: target_subgoal 'cream_cheese_1_placement' has not complete |
| `libero-10-06-progress-roll60-completed-mid` | 06 | baseline_failed | preflight_rejected | ValueError: target_subgoal 'cream_cheese_1_placement' has not complete |

### 无合法原生边界对 —— boundary 族，矩阵 P1 的核心缺口（8 条）

- **修复建议**：按每个任务 region 的实际范围测量「恰好越界」与「界内」两个位置；封闭抽屉/微波炉可能确实不存在合法水平对，此时保留拒绝

| case_id | 任务 | v11 | v12 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-01-progress-boundary-inside-mid` | 01 | preflight_rejected | not_run | ValueError: NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR |
| `libero-10-01-progress-boundary-outside-mid` | 01 | preflight_rejected | not_run | ValueError: NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR |
| `libero-10-02-progress-boundary-inside-mid` | 02 | preflight_rejected | not_run | ValueError: NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR |
| `libero-10-02-progress-boundary-outside-mid` | 02 | preflight_rejected | not_run | ValueError: NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR |
| `libero-10-04-progress-boundary-inside-mid` | 04 | preflight_rejected | preflight_rejected | ValueError: NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR |
| `libero-10-04-progress-boundary-outside-mid` | 04 | preflight_rejected | preflight_rejected | ValueError: NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR |
| `libero-10-05-progress-boundary-inside-mid` | 05 | preflight_rejected | not_run | ValueError: NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR |
| `libero-10-05-progress-boundary-outside-mid` | 05 | preflight_rejected | not_run | ValueError: NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR |

### 触发未到达 —— all-done 组（7 条）

- **修复建议**：需外部评测器支持「success 后不终止并继续注入」，属协议扩展

| case_id | 任务 | v11 | v12 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-01-progress-both-goals-all-done` | 01 | trigger_not_reached | not_run |  |
| `libero-10-01-progress-initial-pose-all-done` | 01 | trigger_not_reached | not_run |  |
| `libero-10-01-progress-other-goal-all-done` | 01 | trigger_not_reached | not_run |  |
| `libero-10-02-progress-both-goals-all-done` | 02 | trigger_not_reached | not_run |  |
| `libero-10-02-progress-initial-pose-all-done` | 02 | trigger_not_reached | not_run |  |
| `libero-10-02-progress-other-goal-all-done` | 02 | trigger_not_reached | not_run |  |
| `libero-10-09-progress-initial-pose-all-done` | 09 | trigger_not_reached | not_run |  |

### 关系未失效（3 条）

- **修复建议**：真值探针的**预期结果**，见第四节

| case_id | 任务 | v11 | v12 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-01-black-bowl-drawer-rollback-s1-mid-pose-spin180` | 01 | preflight_rejected | not_run | ValueError: invalid completed-subgoal rollback: ROLLBACK_DID_NOT_INVAL |
| `libero-10-04-soup-cheese-basket-rollback-s1-mid-pose-spin180` | 04 | preflight_rejected | preflight_rejected | ValueError: invalid completed-subgoal rollback: ROLLBACK_DID_NOT_INVAL |
| `libero-10-07-white-mug-left-plate-rollback-s1-mid-pose-spin180` | 07 | preflight_rejected | preflight_rejected | ValueError: invalid completed-subgoal rollback: ROLLBACK_DID_NOT_INVAL |

### 受保护接触（3 条）

- **修复建议**：属真实约束；可尝试其他触发窗口

| case_id | 任务 | v11 | v12 | 原因 |
| --- | --- | --- | --- | --- |
| `libero-10-03-first-rollback-s1-early-offset-r05` | 03 | preflight_rejected | not_run | ValueError: ROLLBACK_CONTACTS_PROTECTED_BODY |
| `libero-10-05-soup-sauce-basket-rollback-s1-later-offset-r05` | 05 | preflight_rejected | not_run | ValueError: ROLLBACK_CONTACTS_PROTECTED_BODY |
| `libero-10-05-soup-sauce-basket-rollback-s1-mid-offset-r05` | 05 | preflight_rejected | not_run | ValueError: ROLLBACK_CONTACTS_PROTECTED_BODY |

