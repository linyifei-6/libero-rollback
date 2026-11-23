# C/D 窗口触发设计（GT events）

> 状态：**实现中（2026-11-21）**。对应问题：C/D 的 `early` / `mid` / `later` 如何从 GT 谓词与仿真状态判定。
> 参考实现：前序仓 `libero-rollback` 的 `libero_runtime/engine/triggers.py` 与 `dataset/runtime-profiles/libero_10_*.yaml`。
> 当前代码：[`src/libero_rollback/runtime/triggers.py`](../src/libero_rollback/runtime/triggers.py)；测试：[`tests/test_triggers.py`](../tests/test_triggers.py)。

---

## 0. 结论

- 前序仓**没有**一个独立的“5 cm / 8 cm”窗口判定；它用的是 **task profile 的 milestone 事件 + 几何量**：
  - `enter_first_subgoal_completed`：第一个子目标谓词为真，且已 release/settle；
  - `enter_next_subgoal_lift`：后序物体从初始位姿抬起 ≥ `min_lift_from_initial_m`（典型 0.03 m），且 eef 距离在范围内；
  - `enter_next_subgoal_preplacement`：后序物体到目标 region 的 XY 距离 ≤ `max_xy_distance_m`（典型 0.20–0.24 m），且曾经 lift 过。
- 旧标签 `s2 displacement > 5 cm` / `distance to s2 goal < 8 cm` 只是**来源矩阵的旧标签**，不是运行判据；实现不能复用 5/8 cm。
- 当前仓库已实现一个纯 stdlib 的 `WindowTrigger` 状态机，默认 `lift_min_m=0.03`、`preplacement_max_xy_m=0.20`；每个 case 只发目标窗口事件。
- 已接入 C/D runner：`window_matrix.py` + `window_runner.py` + `scripts/run_window_matrix.py`；静态/fake-env 已验证；真实仿真未跑。

---

## 1. 参考实现的语义

前序仓 `libero_runtime/engine/triggers.py` 的关键逻辑（摘要）：

| 事件 | 条件 | 备注 |
|---|---|---|
| `enter_first_subgoal_completed` | `len(subgoal_completion_order)==1` 且 `first_subgoal_settled=True` | 谓词为真还不够；必须 release + settle，避免“还抓着经过 region”就注入 |
| `enter_next_subgoal_lift` | `next_subgoal_lift_m >= min_lift_from_initial_m` 且 `eef_to_next_subgoal_m <= max_eef_distance_m` | profile 典型 0.03 m / 0.10 m |
| `enter_next_subgoal_preplacement` | `next_subgoal_to_goal_xy_m <= max_xy_distance_m` 且（若要求）`lifted_once` | profile 典型 0.20–0.24 m |
| `enter_next_subgoal_completed` | 后序子目标也完成 | 不是 C/D 的窗口，属于 after |

前序仓还使用 `enter_post_completion_retreat`、`enter_x3a_transport` 等任务专属事件；这些不是 C/D 的通用窗口，不能直接搬。

---

## 2. 当前 `WindowTrigger`

```python
WindowObservation(step, s1_done, s1_settled, s2_started,
                  s2_lift_m, s2_to_goal_xy_m)
WindowTrigger(config=TriggerConfig(lift_min_m=0.03,
                                   preplacement_max_xy_m=0.20),
              target="early"|"mid"|"later")
```

判定：

- `early`：`s1_done and s1_settled`
- `mid`：`s2_lift_m >= lift_min_m`
- `later`：`s2_lift_m` 曾达到 `lift_min_m`，且 `s2_to_goal_xy_m <= preplacement_max_xy_m`

特性：

- 每个 `WindowTrigger` 只发**目标窗口**一次；不会把 early/mid/later 混成一个列表。
- 不读旧 5/8 cm；阈值可配置并必须记录到 summary。
- 不依赖 LIBERO/MuJoCo，可在静态环境测试。

---

## 3. 接入 runner 前必须补的

1. **每任务的角色/阈值**：从 BDDL/任务 profile 生成 `s1`/`s2` 的 body/region、lift 阈值、preplacement 半径；当前默认值只是起点。
2. **joint `s2`**：`Open`/`Close`/`Turnon` 的 later 不能用 lift/xy；需要关节开度/比例规则（参考前序仓 `x3b_preplacement` / articulation 事件）。
3. **release/settle**：`early` 必须有“已释放且静止”的 GT 证据；不能只看 `In/On` 谓词。
4. **记录**：`trigger_step`、`trigger_window`、`trigger_criterion`、`lift_m`、`xy_m`、profile 版本；`trigger_rate` 分窗口统计。
5. **C/D runner**：已接入 `WindowTrigger`/`JointProgressTrigger`；C 的 `s2` 是 pending 目标，D 的 `s2` 是组合的第二原子。

---

## 4. 与旧 5/8 cm 的关系

- 旧矩阵的 `trigger_criterion` 是来源数据标签；保留在 CSV 仅用于追溯。
- 运行时一律映射到 `enter_first_subgoal_completed` / `enter_next_subgoal_lift` / `enter_next_subgoal_preplacement`；阈值来自 profile/实测，不是旧 5/8 cm。
- 如果 profile 阈值与默认值不同，summary 必须记录 resolved threshold；报告不能只写窗口名。

---

## 5. 测试

```bash
python -m pytest tests/test_triggers.py -q
```

覆盖：

- early 必须 settled；
- mid 用 0.03 m 而不是旧 5 cm；
- later 必须先 lift 再接近目标；
- 每个 trigger 只发目标窗口一次；
- 非法 window/config 报错。
