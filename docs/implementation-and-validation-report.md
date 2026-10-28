# 实现与验证报告：P0–P2 修复

> **历史记录（勿按当前 catalog 解读）**：本文记录 实现与验证报告 的实验，其中的用例总数（312 / 327 / 122 条）与逐条数字均为**当时口径**。2026-10-16 起 `progress-pulse-*`（24 条）已退出数据集（理由见 `archive/pulse-descoped-20261016/README.md`），当前 catalog 为 **288 条**。本文的数字未改写，以保证历史结论可追溯；需要当前口径时以 `docs/case-matrix-current.md` 与 `dataset/current/manifest.yaml` 为准。

本轮按"一起修完、同步验证"执行。验证口径按用户指示：**只关注扰动注入是否有效、合理**，
不关注模型是否修复成功。

## 一、代码与数据改动

### 1. 真值探针不再被当作失败拒绝（影响 40 条）

`dataset/progress-failure` 的倾转/旋转探针声明 `expected_evaluation_semantics: relation_only`，
即"**旋转是真值探针**：按原生谓词的真前/真后判定属于关系保持对照还是回滚，
**绝不能仅凭角度推断失效**"。但验证器硬性要求 `post_predicate is False`，
于是把这类探针的**预期结果**当错误拒掉（如 `yaw180` 报
`ROLLBACK_DID_NOT_INVALIDATE_SUBGOAL`），用例存在的意义被丢弃。

**修复**：桥接层对 `relation_only` 用例发出运行时既有的
`expected_post_predicate: "measure"`（v12 overlay 的验证器已支持该语义：
`requested["expected_post_predicate"] == "measure"` 时跳过失效要求）。
不再引入并行标志，只用运行时已有的机制。

### 2. 倾转前先抬升（影响 32 条）

探针此前的 `state_change.offset_m` 为 `[0,0,0]` —— **只改朝向、不改位置**。
在封闭抽屉或篮筐内，倾转必然与容器壁相交，抽屉连 15° 都被拒
（`ROLLBACK_PATHOLOGICAL_PENETRATION`）。

**修复**：`displace_from_completed_pose` 新增 `lift_m` 参数，桥接层把它叠加到 z 分量
（上限 0.30 m）。用例按角度给出抬升梯度，使物体**先抬到容器内较高处再倾转**，
既让旋转有空间、又仍处于目标区域内，关系预期保持为真：

| 角度 | 抬升 |
| --- | --- |
| roll15 | 0.04 m |
| roll30 | 0.08 m |
| roll45 | 0.12 m |
| roll60 | 0.16 m |

`yaw180` 保持不抬升 —— 它是**退化对称性对照**（绕竖直轴转轴对称物体，预期无变化）。

### 3. 删除较弱的早期姿态集（-15 条）

`dataset/pose-control` 是本项目早期的尝试：它把倾转标为 `relation_then_resume`
（要求失效），且用了被验证器视为"必须回滚"的 kind。`dataset/progress-failure`
中的 40 条才是规范版本（带 `relation_only`）。**保留较弱版本只会造成重复与误导，故整体退役。**

### 4. 边界对：确认现有实现正确，缺口是真实几何结论

`displace_to_relation_boundary` 的解析逻辑在
`runs/validation-runtime-20261014-v12/rollback_extensions.py`：它沿射线步进搜索
关系翻转处，**遇到碰撞即停止**，并显式注释：

> "A collision at the boundary cannot be skipped to create a falsely labelled
> close-boundary pair."

即**拒绝为凑数而跳过碰撞**。对封闭抽屉与篮筐，物体水平移出目标区域必然先撞壁，
因此 `NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR`（8 条）是**真实的几何结论**，
不是实现缺陷。用例自身的 `open_questions` 也已预见并声明应"retain rejection"。

**结论**：该 8 条保留为拒绝记录，**不做水平边界对**。若要补该维度的真值配对，
需要改从**垂直方向**或**容器开口方向**搜索边界，属新一轮设计，不在本轮范围。

### 5. 数据集与校验状态

| 项 | 结果 |
| --- | --- |
| catalog 用例总数 | **312**（327 − 15 条退役的 pose-control） |
| 来源集合 | two-subtask 129、rollback-battery 57、reference-object 4、progress-failure 122 |
| `validate-dataset` | ✅ 通过 |
| `check-manifest` | ✅ 通过 |
| `pytest` | ✅ **866 passed / 119 skipped / 0 failed** |
| schema | 新增 `lift_m`（`displace_from_completed_pose`，范围 0–0.30 m） |

### 6. 运行环境

- 运行器默认 runtime：`runs/full-coverage/runtime`（**不含**边界扩展）
- 含边界扩展的是冻结 overlay：`runs/validation-runtime-20261014-v12`
- 本轮新建 **`runs/validation-runtime-20261014-v13`**：以 v12 为基线复制，
  叠加"truth probe 用 `expected_post_predicate=measure`"的桥接支持。
  **v12 保持冻结不变**，作为已发布基线。

## 二、验证

### 运行配置

```
--model pi05 --runtime-root runs/validation-runtime-20261014-v13
--cases dataset/progress-failure/cases
--baseline-only --native-preflight
--task-seed 03=1 --task-seed 06=1 --max-steps 600 --video
输出 runs/verify-v13-fixes
```

采用原生端点预检模式：每个任务先跑无扰动 baseline，然后在真实触发状态下
试写全部候选并还原 qpos/qvel/ctrl/act。**该模式不查询模型去逐步恢复**，
正符合"只看注入是否有效合理"的口径。

### 已完成部分（任务 00，8 条）

| 状态 | 条数 |
| --- | ---: |
| `requires_dynamic_drive_validation` | 5 |
| `preflight_rollback` | 3 |

任务 00 是 Turnon 功能任务：其 5 条关节驱动按设计需独立 stepped episode，
**原子关节重置不能替代动态路径验证**，这在 v11/v12 中也是同一结论。

其余任务（含本轮修改的 32 条抬升探针、8 条旋转探针、8 条边界对）仍在运行中。

## 三、待完成

1. **验证批次运行中**：任务 01–09 尚未产出结果。
2. **抬升量需按任务校准**：0.04–0.16 m 是首轮猜测值。若某任务在抬升后仍穿透，
   说明该容器的可用空间更小；若抬升过大导致物体离开目标区域，则关系会真的失效
   （此时应登记为 rollback 而非 probe）。两种情况都由本轮预检结果区分，
   不需要预先假定。
3. **边界对未做**：见第一节第 4 点，属真实几何约束，需另起设计（垂直或开口方向搜索）。
4. **P0 的 seed 事项**：任务 06 已由 v12 seed1 修复；任务 03 在本轮以 `--task-seed 03=1`
   运行，用于确认其 9 条此前"目标未完成"的用例。
