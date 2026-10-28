# `move_to_relation_target` 设计规格

目的：解锁 20 条受阻用例（任务 00 的 11 条 + 07/08 的 ⭐ 极端用例 9 条）。它们都需要同一种能力——
**把某个对象写到"另一个对象或区域所在的位置"**，而现有 10 种 `stateChange`
（`apply_episode_initial_offset` / `displace_from_completed_pose` / `restore_*` / `displace_reference_object` /
`translate_relation_pair` / `displace_to_relation_boundary` / `revert_articulation_goal` / `restore_native_relation_set`）
都无法表达。

## 1. 用例 schema（`schemas/rollback-case.v1.schema.json`）

在 `$defs/stateChange` 的 `oneOf` 中追加变体：

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["kind", "source_relation", "velocity"],
  "properties": {
    "kind": { "const": "move_to_relation_target" },
    "source_relation": { "type": "string", "minLength": 1 },
    "height_offset_m": { "type": "number" },
    "orientation": { "enum": ["preserve", "upright"] },
    "velocity": { "const": "zero" }
  }
}
```

- `source_relation`：一条**已声明的原生关系**字符串（例如 `(On white_yellow_mug_1 plate_2)`），
  用它同时指定"要写到哪个目标"（其 goal 端的位姿）与"谁来完成校验"；
- `height_offset_m`：写在目标位姿之上的抬升量（默认 0，正值用于避免与目标表面穿透）；
- `orientation: upright` 表示姿态复位为直立，`preserve` 保留对象当前姿态。

## 2. bridge 映射（`src/libero_rollback/runtime.py`）

新增分支：解析 `source_relation` 为 `(object_role, goal_role)`，写入 handler 参数
`target_relation_object` / `target_relation_goal` / `height_offset_m` / `orientation`，
并给出默认 severity 标签 `mr`（move-to-relation）。

## 3. overlay 侧（v18/v19）

1. `libero_runtime/engine/interventions/__init__.py` 注册 `move_to_relation_target` handler；
2. handler 复用既有写入与校验链路：
   - 读目标位姿：goal 是 **site region** → `sim.model.site_pos/site_quat`；goal 是 **body** → `body_xpos/xquat`；
   - 把对象写到该位姿（可加 `height_offset_m`）；
   - 之后**原样**走既有的三项校验：穿透预算（severity 的 `maximum_penetration_m`）、
     受保护接触、其他原生目标真值——**任何一项不过就整条拒绝**，不得放松；
3. `spec.py` 增加模板变体 `hv_move_to_relation_target_<severity>`（含 `_after` 变体，供 T09 类 all_done 用例使用）；
4. 净空搜索（`pose_clearance`）对该 kind 开放，但只允许**抬升与横移**，不允许跳过校验。

## 4. 验收标准

| 项 | 要求 |
| --- | --- |
| 落盘 | 20 条用例改用新 kind，`validate-dataset` / `check-manifest` 通过 |
| 注入有效性 | 逐任务原生预检：允许 `rollback` 或 `relation_preserving_probe`，按实测判定语义并回写用例 |
| 零回归 | 其余 522 条用例状态逐条不变 |
| 报告 | 涉及的 T00 / T07 / T08 各自出 HTML 报告 |

## 5. 已知风险与处置

- **目标位姿读取需按 goal 类型分派**（site vs body）——先在 T07 的 `plate_2`（body）与 T00 的
  `flat_stove_1_cook_region`（site）各做一条验证，两条都通过再批量；
- **目标位置可能本来就被占用**（例如 07 的右盘上已有物体）→ 该条应拒绝并记录
  `MOVE_TARGET_UNREACHABLE`，而不是把对象强行塞进去；
- 与 `T09` 的 `first_subgoal_settled` 修复（v18）互不影响，可独立推进。
