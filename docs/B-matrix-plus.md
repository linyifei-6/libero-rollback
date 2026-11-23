# B-matrix-plus：基于 LIBERO-Plus O2 的回滚矩阵（隔离版）

> **2026-11-21 退出主叙事**：最新设计只考虑 base 测试（非 Plus）；本文件保留为历史/可选资产，不进入 `libero-rollback` 主表或静态测试。

> **术语**：本文件及 `dataset/matrices/plus/b-matrix-plus.csv` 简称 **plus-rollback**；非 plus 的 B v2 矩阵见 [b-matrix.md](b-matrix.md)，简称 **base-rollback**。

> 日期：2026-11-18（2026-11-20 更新运行状态）｜ 状态：**已接入独立 runner；π0.5 与 SmolVLA 的全量可执行部分（735 case）均已跑完** ｜ 上游：`sylvestf/LIBERO-plus` @ `4976dc30028e805ff8094b55501d532c48fec182`
>
> 关联：[B-matrix.md](b-matrix.md)（现有 B v2，冻结）、[benchmark-perturbation-alignment.md](benchmark-perturbation-alignment.md) §1.2.1 / §5.6、[O2 审计](../experiments/plus-o2-audit/README.md)
>
> 一句话：**只把 LIBERO-Plus O2 的 target pose 拿来做 all_done 回滚目标，其他物体保持完成态；另加一条从 t=0 reset 到同一 O2 状态的 fresh-start 对照。** 与现有 B v2 完全隔离，不改 `b-matrix.csv`、不改 runner、不进 CI。

---

## 1. 为什么可以以 Plus 为基础

LIBERO-Plus 的 O2（`_level` / goal `_moved`）在仓库里有：

- **696 个基准 case**，覆盖 40 个任务；
- 每个 case 都有 BDDL + **单状态 init**（`init_files/libero_newobj/<suite>/...pruned_init`）；
- 目标物体的初始 pose 可以直接从 init 读出，不需要重新生成。

O2 本来是为 **reset 场景**设计的：如果整条 init 写进去，所有物体都会按 O2 layout 重排，那是 layout 扰动。我们的用法是：

- **只写被撤销目标的 7 维 pose**（x,y,z,quat）；
- 其他物体、机器人保持 all_done 的完成态；
- 因此 other-object layout 不变，变的是“完成后目标被移到 O2 初始位置”。

这样得到的是 **post-completion target-state invalidation**，而不是把 LIBERO-Plus 的整场景 layout 再引入一次。

### 1.1 哪些 case 能用 target-only

| suite | O2 case | free target（可用） | fixture target（不可用） |
|---|---:|---:|---:|
| object | 195 | 195 | 0 |
| spatial | 177 | 177 | 0 |
| goal | 185 | 148 | **37** |
| l10 | 139 | 139 | 0 |
| **合计** | **696** | **659** | **37** |

- fixture target：`wooden_cabinet_1`（open drawer，19 个）和 `flat_stove_1`（turn on stove，18 个）。它们没有 free joint，target-only 写不了；本矩阵**排除**这 37 个。
- 如果以后要做“fixture 也移动”的版本，应另开 `B-plus-full-layout`，不要混进本矩阵。

### 1.2 不做 O1

`_add_*` 是 O1（加干扰物，829 个基准 case），不是目标初始位置；本矩阵**不使用**。

### 1.3 goal `_moved` 不缩放、不丢弃

goal `_moved` 的 target 位移是 **16–44 cm**，比 object/spatial 的 1–10 cm 大一档。本矩阵**原样保留**（不改 pose、不丢 case），只在 `risk_flag` 里标 `large_move`，分析时单独分层；是否可达由 validity gate 和 fresh-start 对照来回答，不靠预先缩小位移。

---

## 2. 矩阵设计

### 2.1 四个 arm

| arm | 含义 | 起始 | 目标状态 | 预算 |
|---|---|---|---|---|
| `rollback` | all_done 后回滚 | 规范 episode，完成后 | 只写目标 = O2 target pose | 600 + 300 |
| `fresh` | **fresh-start 对照** | reset 到 O2 init（t=0） | O2 整条 init | 600 |
| `c0` | no-op 控制 | 规范 episode，完成后 | 不动 | 600 + 300 |
| `l0` | 回滚到 episode init | 规范 episode，完成后 | 目标 = episode Init | 600 + 300 |

- `rollback` 和 `fresh` 使用**同一个 O2 case**（同 task / level / sample），配对键是 `(suite, bddl_name, o2_name)`。
- `fresh` 的 F = **fresh-start**，不是统计 F 检验；它 reset 到**整条 O2 init**，复现 LIBERO-Plus O2 的完整 reset 条件。它是 **Plus O2 基准臂**，不是纯粹的 history 对照：和 `rollback` 相比，它还改了 robot pose、其他物体位置。
- 要做严格的“同状态、不同 history”对照，需要运行时臂 **`fresh-state`**：加载同一条完成态（robot + 其他物体），只把目标写成 O2 pose，再清空 policy history 从 t=0 跑。它依赖完成态，不能从 O2 init 静态生成，所以不在本 CSV。
- `c0` / `l0` 每个可用任务各 1 条（38 个任务）。

### 2.2 触发与预算

- `rollback` / `c0` / `l0`：`trigger=all_done`、`delay_steps=10`、`repair_window=300`、`max_steps=600`。
- `fresh`：`trigger=reset`、`delay_steps=0`、`repair_window=0`、`max_steps=600`。
- 全部只做**最终状态写回**：直接写 `qpos/qvel` + `sim.forward()`，不模拟移动过程。

### 2.3 有效性门控

沿用 B 的口径，但明确都是**写后最终状态**检查：

| 门控 | 判据 | 说明 |
|---|---|---|
| `no_penetration` | 目标子树与场景/其他物体穿透 ≤ 1 cm（robot 接触排除） | 防止写完被物理弹开 |
| `zero_velocity` | 目标物体写后速度 ≤ 1e-6 | 防止写后漂移 |
| `object_released` | 注入时两指间距 > 1 cm | all_done 应天然满足；不满足记 `injection_invalid` |
| `restorable` | 状态写回 oracle 可恢复 | 沿用现有 C4 |

> **2026-11-19 起：post-settle 协议。** `run_b_plus.py` 默认 `--settle-after-injection 10`：写完 O2 target 后先用 dummy action settle 10 步，再判 `no_penetration` / `zero_velocity` / `object_released`，然后才开始 `repair_window`。settle 步数不计入 repair budget；`injection.immediate` 保留写入瞬间的值，`injection.post_settle=true` 表示这是 settle 后的判定。旧数据（Goal / Object 首批）标 `immediate-v1`，不要与新数据混表。
>
> `no_penetration` 不是“移动过程中的穿模”，是**最终位姿是否有效**。如果最终位姿和别的物体重叠，下一步物理会把物体推开，实际回滚位姿就 ≠ 请求位姿。

### 2.4 core / full

- `split=core`：每个 `(suite, bddl_name, o2_level)` 只取 1 个 sample；用于第一轮扫描。
- `split=full`：659 个 O2 case 全量；用于最终表。
- `c0` / `l0` 统一标 `core`（full run 也包含它们）。

### 2.5 case_id

```
bp-<suite>-t<idx:03d>-o2l<level>s<sample>        # rollback
bp-f-<suite>-t<idx:03d>-o2l<level>s<sample>      # fresh
bp-<suite>-t<idx:03d>-c0                          # no-op
bp-<suite>-t<idx:03d>-l0                          # 回滚到 episode init
```

示例：`bp-object-t000-o2l3s2`、`bp-f-object-t000-o2l3s2`。

### 2.6 O2 init 的 qpos 偏移（实现必须注意）

LIBERO 的 `.pruned_init` 存的是 `sim.get_state().flatten()`，布局是 **`[time, qpos, qvel]`**；`set_init_state` 按这个布局消费。因此从 O2 init 里读目标 qpos 时：

```
文件索引 = 模型 jnt_qposadr + 1
```

写错会读到前一个物体的四元数，表现为 x/y/z 错位、穿模或「目标跑到桌子外」。本仓 2026-11-18 首轮 Goal 跑踩过这个坑；`_apply_o2` 已按 `offset=1` 修正，并在 smoke 中用 `push_the_plate` / `open_the_top_drawer` 两个 case 验证了目标 pose 与 O2 init 一致。

### 2.7 被撤销关系

`revoked_predicate` = 原始 BDDL 的 `:goal` 中包含 O2 target object 的那个原子。

- 例：`(In alphabet_soup_1 basket_1_contain_region)`、`(On akita_black_bowl_1 plate_1)`；
- 659 个 case 全部解析成功（0 失败）；
- 对 plate 作为 target 的 case，移动 plate 会撤销 `(On bowl plate)`，但 plate 上的物体可能失去支撑；这些 case 标 `risk_flag=support_object`，建议单独看。

---

## 3. 数量

### 3.1 总量

| 量 | 数 |
|---|---:|
| rollback | 659 |
| fresh | 659 |
| c0 | 38 |
| l0 | 38 |
| **full 总计** | **1,394** |
| **core 总计** | **446**（185 rollback + 185 fresh + 76 controls） |

### 3.2 按 suite

| suite | 任务 | rollback | fresh | c0 | l0 | full 总 | core 总 |
|---|---:|---:|---:|---:|---:|---:|---:|
| goal | 8 | 148 | 148 | 8 | 8 | 312 | 96 |
| object | 10 | 195 | 195 | 10 | 10 | 410 | 120 |
| spatial | 10 | 177 | 177 | 10 | 10 | 374 | 118 |
| l10 | 10 | 139 | 139 | 10 | 10 | 298 | 112 |
| **合计** | **38** | **659** | **659** | **38** | **38** | **1,394** | **446** |

### 3.3 risk_flag

| risk_flag | 数量 | 含义 |
|---|---:|---|
| `support_object` | 49 | target 是 `plate_1`（l10 30 + goal 19）；移动支撑物可能让上面的物体失去支撑 |
| `large_move` | 90 | target 位移 > 15 cm（全部在 goal `_moved`） |
| `unknown_distance` | 90 | target 在 `In` 类容器里，BDDL `On` 解析不到距离（spatial） |
| 空 | 430 | 常规小位移/自由目标 |

> `large_move` 和 `support_object` 不重叠（49+90+90+430=659）。`target_dist_cm` 为空是“BDDL 里没有 On 关系、无法算距离”，不是缺数据。

---

## 4. CSV schema

文件：[`dataset/matrices/plus/b-matrix-plus.csv`](../dataset/matrices/plus/b-matrix-plus.csv)

| 列 | 含义 |
|---|---|
| `case_id` | 唯一 id，`bp-` / `bp-f-` 前缀 |
| `arm` | `rollback` / `fresh` / `c0` / `l0` |
| `split` | `core` / `full` |
| `suite` | `goal` / `object` / `spatial` / `l10` |
| `task_idx` | 沿用 B v2 的 LIBERO 全局 task index |
| `bddl_name` | 原始任务名 |
| `instruction` | 原始 instruction |
| `o2_name` | LIBERO-Plus O2 文件名（不含 `.bddl`） |
| `o2_level` / `o2_sample` | `_level{L}_sample{S}` |
| `target_obj` | O2 target object |
| `revoked_predicate` | 要撤销的 goal 原子 |
| `family` | 本矩阵全为 `pose` |
| `trigger` | `all_done` / `reset` |
| `delay_steps` | 10 / 0 |
| `repair_window` | 300 / 0 |
| `expected_relation_after` | `c0=true`，其余 `false` |
| `max_steps` | 600 |
| `target_dist_cm` | BDDL target region 位移，仅参考；空 = 无法解析 |
| `risk_flag` | `support_object` / `large_move` / `unknown_distance` / 空 |
| `o2_bddl` | 相对 LIBERO-plus 根目录的 BDDL 路径 |
| `o2_init` | 相对 LIBERO-plus 根目录的 init 路径 |
| `source` | `libero-plus@4976dc3` |

---

## 5. 指标

```
Recovery(δ)      = valid_recovered / (valid_recovered + valid_not_recovered)   # rollback
FreshSuccess(δ)  = full_task_success / fresh attempts                          # fresh
Δ_history(δ)     = Recovery(δ) − FreshSuccess(δ)                               # 配对
```

- 配对键：`(suite, bddl_name, o2_name)`；rollback 和 fresh 必须用同一个 O2 case。
- 同时报告 `relation_restored` 与 `full_task_success`；fresh 的主指标是完整任务成功，rollback 的主指标是关系恢复 + 任务成功。
- 报告 `applied_delta_m`、实际 target pose、`no_penetration` 排除率、`object_released` 排除率。
- `large_move` / `support_object` 分开出表；不要和常规小位移混在一起。

### 5.1 判读

| rollback | fresh（Plus O2） | 解释 |
|---|---|---|
| 失败 | 成功 | history/完成上下文导致失败 |
| 失败 | 失败 | 这个 O2 状态在 all_done 的预算/robot pose 下就难，不是 history |
| 成功 | 失败 | history 有帮助 |
| 成功 | 成功 | 状态可恢复，history 无显著影响 |

> `fresh` 是整条 O2 reset，和 `rollback` 还差 robot pose / 其他物体位置；上表严格说是“对 Plus O2 基准”的判读。要归因到 history，需 `fresh-state`（同完成态 + 目标 O2 + 空 history）。

---

## 6. D 扩展（设计，不在本 CSV）

D-native 的 s1 只有 **8 个 pose 任务 + 1 个 joint（t000）**。O2 没有 joint 状态，t000 保留现有 L0/L1；本矩阵只覆盖 8 个 pose 任务的 107 个 O2 case/window。

| 方案 | / window | ×3 window | + joint | + c0 | 总 D |
|---|---:|---:|---:|---:|---:|
| 全部 107 个 l10 pose O2 | 107 | 321 | 12 | 9 | **342** |
| 5 levels × 8 pose 任务（≈40） | 40 | 120 | 12 | 9 | **141** |
| 3 levels × 8 pose 任务 | 24 | 72 | 12 | 9 | **93** |
| 1 O2 / 现有 56 个 pose case | 56 | 168 | 12 | 9 | **189** |

- 三个 window 使用**同一个 O2 state**；window 是“执行 s2 的什么 timing 去回滚 s1”，不是“该阶段的状态”。
- early = s1 刚完成，机器人还在附近；mid/later 机器人已转向 s2，s1 物体可能更远。哪个更好要按 window 实测 validity，不预设。
- 只做状态写回；只要写后状态满足 gates，不需要物理移动路径。

---

## 7. 与当前实现的隔离

本矩阵早期是**纯数据层新增**，2026-11-18 起通过独立入口接入，不改 v2 主矩阵的代码路径：

1. 文件放在 `dataset/matrices/plus/`，文件名 `b-matrix-plus.csv`；
2. case id 前缀 `bp-` / `bp-f-`，不会和 `b-*` / `d-*` 冲突；
3. `dataset/matrices/b-matrix.csv` 不动；`scripts/run_b_plus.py` 是**独立 loader + 独立入口**，只读 `plus/b-matrix-plus.csv`，现有 `run_b_matrix.py` 不受影响；
4. `BCase` 增加 `O2` level（`src/libero_rollback/matrices.py`），`BInjector` 支持 target-only 状态写回（`src/libero_rollback/runtime/perturbation.py`）；
5. `fresh` 仍不可执行（需要整条 O2 init 的 reset 路径，不是 rollback 臂）；`rollback` / `c0` / `l0` 可执行。

---

## 8. 已知限制

1. **target-only 不等于“已证明 history”**：还要看 fresh / fresh-state 对照；`fresh` 是 Plus O2 整条 reset，包含 robot/其他物体差异；`fresh-state` 才是严格同状态对照。
2. **37 个 fixture target 被排除**：open drawer / turn on stove；如果要做，需另开 full-layout。
3. **all_done 的 reachability**：O2 pose 在 reset 下有效，不等于在完成态 300 步内可达；必须报告排除率。
4. **support_object**：移动 plate 可能让上面的物体失去支撑，`zero_velocity` 只查 target；这些 case 建议单独分析。
5. **goal `_moved` 的 16–44 cm**：和 1–10 cm 不是同一剂量；本矩阵保留原样，分析时分层。
6. **569 个 case 的 `target_dist_cm` 可解析，90 个 spatial 为空**：空是 `In` 容器任务无法从 BDDL `On` 算距离，不是缺 BDDL/init。
7. **696 个 O2 只有 195 个 `(task, level)` cell**：core 是 185 个 free-target cell，不是完整 40×5 网格。

---

## 9. 复现

```bash
# 1) 稀疏 clone LIBERO-plus（只需 BDDL + O2 init）
git clone --depth 1 --filter=blob:none --sparse https://github.com/sylvestf/LIBERO-plus.git .cache/liberoplus-clone
cd .cache/liberoplus-clone
git sparse-checkout set libero/libero/bddl_files libero/libero/init_files/libero_newobj
cd -

# 2) O2 审计（本仓 experiments/plus-o2-audit 的数据来源）
.venv/bin/python .cache/o2_full_diff2.py

# 3) 生成 B-plus 矩阵（一次性脚本，未入库）
.venv/bin/python .cache/build_b_plus.py
```

校验：`case_id` 唯一、rollback/fresh 659 对、core 185 cell、0 条 predicate 失败、0 条路径缺失。

---

## 10. 运行状态（2026-11-20）

### 10.1 已完成的运行

| 模型 | 运行目录 | case | 协议 | 报告 |
|---|---|---:|---|---|
| π0.5 | `runs/b-plus-goal-core-20261118-v2` / `b-plus-object-merged-20261119` / `b-plus-spatial-full-settle-20261119` / `b-plus-l10-full-settle-20261119` | 735/735 | mixed（Goal/Object 首批 immediate-v1，其余 post-settle） | `runs/b-plus-pi05-20261120.summary.md` |
| SmolVLA 0.45B | `runs/b-plus-{goal,object,spatial,l10}-full-smolvla-20261120` | 735/735 | post-settle-v1（`settle_after_injection=10`） | [experiment-report-b-plus-smolvla.md](experiment-report-b-plus-smolvla.md) |

两模型的其它参数逐项一致：`--split both`、`max_steps=600`、`repair_window=300`、`delay_steps=10`、`replan=10`、`camera=256`、`settle_steps=10`、`seed=0`、`init_row=0`、`stop-on-recovery`、20 fps 视频。

### 10.2 关键结果

| 指标 | π0.5 | SmolVLA |
|---|---:|---:|
| trigger（case） | 707/735 = 96.2% | 260/735 = 35.4% |
| trigger（task，≥1） | 38/38 | 13/38 |
| O2 注入有效 | 557/659 = 84.5% | 215/659 = 32.6% |
| **O2 Recovery** | **84/557 = 15.1%** | **0/215 = 0.0%** |
| C0 保持 / 触发 | 34/37 | 11/13 |
| 配对（两侧 valid，n=213） | 25 | 0（McNemar p≈6e-08） |

> **N/A ≠ invalid ≠ 0%**：未触发的 case（策略没完成原任务）不计入 Recovery 分母，也不标记为 invalid；SmolVLA 的 735 个 case 里 475 个属于 N/A。

---

## 11. 示例

| case_id | arm | split | target_obj | revoked_predicate | o2_name | risk |
|---|---|---|---|---|---|---|
| `bp-object-t000-o2l1s1` | rollback | core | `alphabet_soup_1` | `(In alphabet_soup_1 basket_1_contain_region)` | `pick_up_the_alphabet_soup..._level1_sample1` | — |
| `bp-f-object-t000-o2l1s1` | fresh | core | `alphabet_soup_1` | 同上 | 同上 | — |
| `bp-goal-t030-o2l1s1` | rollback | core | `akita_black_bowl_1` | `(In akita_black_bowl_1 wooden_cabinet_1_top_region)` | `open_the_top_drawer..._moved_level1_sample1` | large_move |
| `bp-spatial-t121-o2l3s2` | rollback | full | `akita_black_bowl_1` | `(On akita_black_bowl_1 plate_1)` | `pick_up_the_black_bowl_next_to_the_plate..._level3_sample2` | — |
| `bp-l10-t193-o2l4s1` | rollback | core | `plate_1` | `(On porcelain_mug_1 plate_1)` | `LIVING_ROOM_SCENE5..._level4_sample1` | support_object |
