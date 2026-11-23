# C 矩阵说明：LIBERO-10 in-execution rollback

> 状态：**基础矩阵 2026-11-21 冻结；pi05 全量 2026-11-22 完成（180/180）**。C 是分析维度，不是文件名；实际矩阵在
> [`dataset/matrices/libero-rollback/in-execution-rollback.csv`](../dataset/matrices/libero-rollback/in-execution-rollback.csv)。
> 叙事与 A/B/C/D 分工见 [`rollback-narrative.md`](rollback-narrative.md)；B 的 base 矩阵见 [`b-matrix.md`](b-matrix.md)。

---

## 0. 速览

| 项 | 值 |
|---|---|
| 维度 | **C = in-execution rollback**（原生长程任务，执行中撤销） |
| 文件 | `dataset/matrices/libero-rollback/in-execution-rollback.csv` |
| 行数 | **180** = 3 窗口 × 60 |
| 任务 | 9 个 L10 多目标任务（`t276` 不在 C） |
| 窗口 | `early` 60 / `mid` 60 / `later` 60 |
| level | `L0` 27 / `L1` 81 / `L2` 72；**无 C0** |
| 撤销 | 恒为 `s1`；`s2` pending；`s2_must_stay_true=true` |
| 预算 | 矩阵默认 800 + 600；**最新 pi05 评估覆盖为 600 + 600**（注入后追加 600） |
| 状态 | 矩阵已生成；C/D window runner 已实现；**pi05 全量 180/180 已跑完**：trigger 172/180，valid 157，Recovery **65/157=41.4%**，Full SR **60/157=38.2%**；视频 180 条 |

---

## 1. C 在叙事中的位置

C 是 **native × in-execution** 这一格：

- 任务来自原始 LIBERO-10，不是 Plus，也不是组合任务；
- 模型已完成 `s1`、正在做 `s2` 时，在 `early`/`mid`/`later` 撤销 `s1`；
- 场上仍有 pending 的 `s2`，这是 C 与 B 的唯一干净差异；
- C 只取 L10 的 9 个多目标任务，因为 Goal/Object/Spatial 基本没有“前序子任务 + 后续 pending”的结构。

C 不重复 `all_done_control`：`all_done` 时机的 no-op 控制已由 B 的 `C0` 覆盖。C 只在执行中，三窗口之外没有矩阵控制。

---

## 2. 数据与结构

### 2.1 180 条怎么来

```text
每窗口 = 8 个 pose 任务 × 7 + t000（joint s1）× 4
       = 56 + 4 = 60
C 总数 = 3 × 60 = 180
```

| `task_idx` | family | `early` | `mid` | `later` | 合计 |
|---:|---|---:|---:|---:|---:|
| 0 | joint | 4 | 4 | 4 | **12** |
| 33 | pose | 7 | 7 | 7 | **21** |
| 78 | pose | 7 | 7 | 7 | **21** |
| 133 | pose | 7 | 7 | 7 | **21** |
| 137 | pose | 7 | 7 | 7 | **21** |
| 145 | pose | 7 | 7 | 7 | **21** |
| 158 | pose | 7 | 7 | 7 | **21** |
| 193 | pose | 7 | 7 | 7 | **21** |
| 237 | pose | 7 | 7 | 7 | **21** |
| 合计 | — | 60 | 60 | 60 | **180** |

- `t000` 的 `s1` 是 `Turnon flat_stove_1`（joint），没有 `L2`；每窗口 `L0` + 3 个 `L1`。
- 其余 8 个任务每窗口 `L0` + 3 个 `L1` + 3 个 `L2`。
- C 从旧 `d-native-matrix.csv` 去掉 9 条 `all_done_control` 得到；case_id 保留旧 `d-l10-...` 以追溯。

### 2.2 分布

| 维度 | 取值 |
|---|---|
| level | `L0` 27 / `L1` 81 / `L2` 72（无 C0） |
| family | `pose` 168 / `joint` 12 |
| param | 空 27 / `d03` 27 / `d06` 27 / `d10` 27 / `r30` 24 / `r60` 24 / `r90` 24 |
| window | `early` 60 / `mid` 60 / `later` 60 |

### 2.3 列

在旧 19 列前增加三列：

| 列 | 值 | 含义 |
|---|---|---|
| `test_suite` | `libero-rollback` | 测试套 |
| `dimension` | `in-execution` | 分析维度 C |
| `arm` | `rollback` | C 全部为处理臂 |

示例行：

```csv
d-l10-t000-early-l0,libero-rollback,in-execution,rollback,native,l10,0,,turn on the stove and put the moka pot on it,early,s1 first true,s1,(Turnon flat_stove_1),flat_stove_1,joint,L0,,relation_then_resume,800,600,false,true
```

---

## 3. 窗口与触发

| `window` | 定义 | 数据里的旧标签 | 应映射到的 GT 事件 |
|---|---|---|---|
| `early` | 第一个子目标完成、后续尚未开始 | `s1 first true` | `enter_first_subgoal_completed` |
| `mid` | 后序目标物已被抓起 | `s2 displacement > 5 cm` | `enter_next_subgoal_lift` |
| `later` | 后序物已被运到目标上方、尚未放置 | `distance to s2 goal < 8 cm` | `enter_next_subgoal_preplacement` |

- 旧 5 cm / 8 cm 阈值**已作废**；实现必须用 GT 谓词与仿真状态映射到事件名。
- 窗口检测不能用 O2/Plus layout，也不能用外部 runtime profile。
- `trigger_rate` 是实测值；某窗口 `<20%` 时记 `N/A`，case 不删除。

---

## 4. 注入几何

| level | pose `s1`（8 个任务） | joint `s1`（`t000`） |
|---|---|---|
| `L0` | 回到 episode 初始位姿 | 回到初始关节值 |
| `L1` | 初始位姿 + 水平射线 δ ∈ {3,6,10} cm | 初始→达成开度跨度的 10/25/40% |
| `L2` | 初始位姿 + world-z yaw ∈ {30°,60°,90°} | 不存在 |

- 注入后必须让 `s1` 为假；`s2` 的进度不得被破坏（`s2_must_stay_true`）。
- 记录实测 `Δtranslation_m`、`Δangle_rad`、`axis`；nominal δ/θ 不是保证值。
- 无 `both`/`mixed`/`pre`；C 每个 case 只撤销一个 `s1` 关系。

---

## 5. 预算、门控与读数

- 预算：矩阵默认 `max_steps=800`；最新 pi05 评估覆盖为 `max_steps=600`，注入后 `total_budget_steps = injection_step + 600`（不是固定 1200）。
- 共用门控：pre 真、注入后假、无穿模 ≤1 cm、零速度、已释放、restorable、几何记录。
- D 额外门控不适用；C 额外只使用 `s2_must_stay_true` 与窗口 `trigger_rate`。
- 主指标：`Recovery`；分母 = 窗口触发且注入有效的 180 条 treatment；不可触发记 `N/A`。
- `recovered` 只看被撤销的 `s1`；`SR` 看全部原生 goal 原子。C 通常 `Recovery` 可高、`SR` 低，因为 `s2` 仍 pending。
- **C 没有矩阵 C0**：窗口 `control_rate` 目前只能 `N/A`；如果以后实现 synthetic no-op，再单独报。不能拿 B 的 `C0` 当 C 的窗口控制。

---

## 6. 与 B 的 60 对配对

B 的 base l10 `s1` 子集：

```text
B(l10, s1) = L0 9 + L1 27 + L2 24 = 60
C(任一窗口) = L0 9 + L1 27 + L2 24 = 60   # t000 joint 无 L2
```

- 同任务、同 `s1`、同 level，只换撤销时机（`all_done` vs 窗口）；
- 三个窗口各 60 对，共 180 对；
- B 的 l10 `C0` 10 条是 `all_done` 控制；C 没有 C0；不能把 B 的 C0 放进 C 的分母。

---

## 7. 生成与状态

```bash
python scripts/build_suite_matrices.py          # 重建 C
python scripts/build_suite_matrices.py --check  # 静态比对
```

- C 由旧 `d-native-matrix.csv` 过滤 `window != all_done_control` 得到；不新增/改值。
- C/D runner 已实现：`src/libero_rollback/window_runner.py` + `scripts/run_window_matrix.py`；当前没有 v2 C 结果（未跑真实仿真）。
- 旧 `docs/d-matrix.md` 的 native 部分即 C 的历史详细说明；本文件是 base-only 的新入口。

### 7.1 结果（pi05，2026-11-22）

| 项 | 值 |
|---|---:|
| cases | **180/180** |
| trigger | 172/180 = 95.6% |
| valid | 157 |
| Recovery | **65/157 = 41.4%** |
| Full SR | **60/157 = 38.2%** |
| s2 preserved | 157/157 |
| errors | 0 |
| video | 180 条，20 fps |

按窗口：

| window | trigger | valid | Recovery | Full SR |
|---|---:|---:|---:|---:|
| early | 59/60 | 58 | 27/58 = 46.6% | 25/58 = 43.1% |
| mid | 56/60 | 48 | 18/48 = 37.5% | 17/48 = 35.4% |
| later | 57/60 | 51 | 20/51 = 39.2% | 18/51 = 35.3% |

按 level：

| level | valid | Recovery | Full SR |
|---|---:|---:|---:|
| L0 | 24 | 11/24 = 45.8% | 8/24 = 33.3% |
| L1 | 71 | 27/71 = 38.0% | 25/71 = 35.2% |
| L2 | 62 | 27/62 = 43.5% | 27/62 = 43.5% |

无效构成：8 条 trigger 未到（N/A）、8 条 `restorable=False`、7 条 `object_released=False`（部分重叠）。报告：[experiments/c-matrix-pi05-20261121/index.html](../experiments/c-matrix-pi05-20261121/index.html)。

### 7.2 运行

```bash
# 计划（不启仿真）
python scripts/run_window_matrix.py --dry-run \
  --matrix dataset/matrices/libero-rollback/in-execution-rollback.csv \
  --windows early --output runs/c-plan

# 真实运行（需 LIBERO_HOME + 模型环境）
LIBERO_HOME=/path/to/LIBERO python scripts/run_window_matrix.py \
  --policy pi05 --checkpoint "$PI05_CHECKPOINT" \
  --matrix dataset/matrices/libero-rollback/in-execution-rollback.csv \
  --windows early mid later --output runs/c
```

### 7.3 动态 s1/s2（2026-11-23）

L10 中多个“放置到同一/不同区域”的目标可能被策略以任意顺序完成；固定矩阵的
`revoked_objects` 只能表示一种顺序。runner 现在在 episode 初始为每个候选 pose
目标各建一个 `BInjector`，运行时以**第一个完成的目标作为 s1**，另一个作为 s2，
再建立窗口 monitor 和注入。覆盖 C 的 t133/t137/t145/t158/t193/t237；Compose
任务解析同一 `goal_atoms` 后自动使用同一逻辑。

补测（L0，动态版）：15/15 valid，8/15 Recovery，7/15 Full SR。seed=1 正式
180 条使用同一动态逻辑；结束后报告写入 `experiments/c-matrix-seed1-20261123/`。

已审核的任务 profile 写在 `window_runner.TASK_WINDOW_PROFILES`：t033 mid/later
= 0.02/0.20，t078 mid/later = 0.05/0.65，t133 lift = 0.005 m。

### 7.4 seed=1 复跑（2026-11-23）

同一 180 条矩阵、`init_row=0`、`max_steps=600`、`repair_window=600`、video，
`seed=1`；动态 s1/s2 和任务 profile 已启用。正式汇总按 `case_id` 去重（
`episodes.jsonl` 有 188 行，其中 8 行是 `--retry-invalid` 的旧记录）。

| 项 | seed=0 | seed=1 |
|---|---:|---:|
| completed | 180 | **180** |
| trigger | 172 | **180** |
| valid | 157 | **180** |
| Recovery | 65/157 = 41.4% | **54/180 = 30.0%** |
| Full SR | 60/157 = 38.2% | **48/180 = 26.7%** |
| s2 preserved | 157/157 | **180/180** |

按窗口（seed=1）：early 60/60/19/16，mid 60/60/19/18，later 60/60/16/14
（分别为 cases/trigger/valid/Recovery/Full SR）。按 level：L0 27 valid / 7
Recovery；L1 81 / 22；L2 72 / 25。

`restorable` 是辅助 oracle，不进入 valid 硬门控；seed=1 有 10 条 valid 的
`restorable=False`，作为辅助诊断保留。修复后硬门控 invalid 0 条；此前 3 条
invalid 分别由 target-aware release 和 t237 pose 窗口 profile 解决。

报告：[experiments/c-matrix-seed1-20261123/index.html](../experiments/c-matrix-seed1-20261123/index.html)。
去重汇总：[runs/.../run-summary-dedup-fixed.json](../runs/c-matrix-pi05-20261123-seed1-fixed/run-summary-dedup-fixed.json)。
