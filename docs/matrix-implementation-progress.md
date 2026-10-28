# 新矩阵落地进展

> **历史记录（勿按当前 catalog 解读）**：本文记录 矩阵实施进展 的实验，其中的用例总数（327 / 122 条）与逐条数字均为**当时口径**。2026-10-16 起 `progress-pulse-*`（24 条）已退出数据集（理由见 `archive/pulse-descoped-20261016/README.md`），当前 catalog 为 **288 条**。本文的数字未改写，以保证历史结论可追溯；需要当前口径时以 `docs/case-matrix-current.md` 与 `dataset/current/manifest.yaml` 为准。

> 更新：2026-10-14。当前已实现 327 条定义（205 条原集合＋122 条 progress-failure 候选），全量外部绑定编译接受。原生边界、姿态、参照物/成对移动、恢复门控、完成边界和原子关系集均已有 schema、binding 和独立运行时实现；articulation 延迟也已通过能力协商转发。下面是较早阶段的实施记录，不能作为当前未实现清单或验收结论。最新任务状态与真实验证结果见 [implementation-status.md](implementation-status.md)。

依据 `docs/case-matrix-current.md`（2026-10-14 版，由 current catalog 自动生成）。该文档第七节明确规定：
**先解决声明/binding 不一致，再落 P1 边界配对**。本轮完成前者。

## 一、已修复：第七节 7.1 的两处不一致

### 7.1a `trigger.delay_steps` 未被转发

**影响 11 条**。用例声明 `delay_steps: 10`，但桥接层从不把它写进干预参数，
因此这些用例实际在触发步就注入，"延迟 10 步"从未生效。

修复：桥接层按声明转发 `delay_steps`。**articulation 目标除外** ——
`articulation_setback` 的校验要求参数集精确相等，多一个参数即被拒。

验证：10 条放置类用例的 binding 现携带声明的延迟；articulation 用例不含该参数。

### 7.1b 坐标系字段名不匹配

**影响 143 条**。用例声明 `state_change.offset_frame: world`，桥接层却读
`coordinate_frame`，取不到便退回默认 `task_frame`。两个坐标系的 x 轴相差 180°，
**带符号偏移被反向施加**。

修复：改为读取 `offset_frame`，并保留 `coordinate_frame` 作为旧拼写兼容。

验证：143 条偏移用例的 binding 现全部携带 `world`。

## 二、顺带修正的三处缺陷

| 项 | 内容 |
| --- | --- |
| 任务 00 的 early 事件 | 该任务 s1 是 `Turnon`、s2 是放置摩卡壶，故 early 应为 `enter_next_subgoal_approach` + 延迟 10；原先写的是 `enter_first_subgoal_completed`，而该状态在开炉任务上语义不符 |
| battery 的 6 条容器上方用例 | 仍使用旧的 `clearance_m: 0.05` 单点参数，扫描被限制在 5 cm 高度，只能水平挤开。已补齐 `clearance_max_m: 0.45`（01 另加 `above_container_top` 与 `min_robot_clearance_m: 0.12`），与 runtime 已验证参数一致 |
| 测试套件 | 原 `test_validation.py` 读取已退役的 `dataset/current` 与旧 severity 词表（`l1_t0`/`d0..d3`），已归档到 `tests/_outdated/`（含说明）。新写 `tests/test_cases.py`：61 项，覆盖 schema 有效性、跨集 case_id 唯一性、档位词表、窗口与触发事件匹配、偏移三元组、容器上方的适用范围、以及上述两处 binding 修复的回归防护 |

## 三、当前状态

```
用例集     two-subtask 129 + rollback-battery 57 + pose-control 15 + reference-object 4 = 205
编译       205/205 通过 runtime binding 编译
测试       当前全量 pytest 通过（含 205 条 case 的 schema/binding 参数化检查）
```

## 四、下一步：P1 计划项（第八节之后的落地顺序）

矩阵第六节共列出 40 余个 `plan-tXX-*`，按优先级分三档。**P1 共 8 项**：

| 计划编号 | 任务 | 机制 | 前置条件 |
| --- | --- | --- | --- |
| `plan-t00-function-boundary` | 00 | 旋钮从开启位驱动至原生 `Turnon` 阈值外；配对为阈值内 | 需标定旋钮阈值与驱动结果 |
| `plan-t01-containment-boundary` | 01 | 黑碗移出 `bottom_region`；配对移至边界内 | 需 region 坐标 + 碰撞预检 |
| `plan-t02-containment-boundary` | 02 | 杯子移出 `heating_region`；配对区内 | 需门/杯碰撞预检 |
| `plan-t03-support-region` | 03 | 壶1 滑出炉面 cook_region；配对区内滑移 | 从**已完成位置**计算偏移 |
| `plan-t04-containment-boundary` | 04 | 汤罐移出篮子区域；配对区内 | 按本任务 episode 校准 |
| `plan-t05-containment-boundary` | 05 | 同上，各自独立校准 | 不复制任务 04 坐标 |
| `plan-t06-containment-boundary` | 06 | 奶酪盒移出篮子区域 | 考虑盒体几何与篮壁碰撞 |
| `plan-t07-support-boundary` | 07 | 白杯滑过 `On` 判定边界（object-on-object 水平中心距离阈值 0.03 m）；配对界内 | 以实际安装代码校准 |
| `plan-t08-support-boundary` | 08 | 白杯在盘面滑过 `On` 边界 | 以实际盘杯几何校准 |

### 实现 P1 需要新增的机制

现有 `apply_episode_initial_offset` 的参考点是**回合初始位姿**，而 P1 要求参考
**当前已完成位置 / 目标 region 边界**（矩阵第七节"完成位置参考"一行明确要求）。
因此需要：

1. **新的 state_change 类型**：例如 `displace_from_completed_pose`，参考点取注入前
   该对象的实际位姿，位移量由 region 边界几何推出；
2. **region 边界查询**：从 `context` 读取 `goal_state_name` 对应的 region 范围
   （矩形 xyrange 或 site 半径），据此计算"恰好越界"的位移；
3. **配对用例**：同一机制下产生"越界（失效）"与"界内（对照）"两个独立定义；
4. **保护校验**：不得写入当前 s2 对象或机器人，需碰撞预检。

矩阵同时要求这些新定义在 **mid、delay=0** 先落一组以隔离机制，验证通过后再复制到
early/later。

### 尚未解决的前置项（矩阵 7.1 其余各行）

| 项目 | 状态 |
| --- | --- |
| 任务 02 的 BDDL 引用 | 11 条 two-subtask 文件声明 `KITCHEN_SCENE6_put_the_yellow_and_white_mug_in_the_microwave.bddl`，源码目录中实际是带 `_and_close_it` 的文件名；需核对后修正 |
| 姿态写入 | 本地 `_state_parameters` 未转发 quaternion；P2 的姿态组需要先定义 schema 与坐标系 |
| 参照物 / 多实体 | 主流程只撤销单个目标对象；P2 的篮子/盘子移动组需要多实体写入支持 |
| 恢复门控 | 当前 transient 是延时二次写入，不检查谓词是否已恢复；P3 的 pulse/repeat 组需要门控 |
| 完成边界 | 03/07 有 `all_done` 定义，但任务成功即终止，需要外部评测器的继续观察协议 |
