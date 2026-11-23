# D 矩阵说明：组合任务的 in-execution rollback

> 状态：**base-only / case 定义已构建（2026-11-21）**。D 是分析维度，不是文件名。
> 实际套件：[`dataset/matrices/libero-compose/`](../dataset/matrices/libero-compose/)。
> 叙事见 [`rollback-narrative.md`](rollback-narrative.md)；C 见 [`c-matrix.md`](c-matrix.md)；窗口触发见 [`trigger-design.md`](trigger-design.md)。

---

## 0. 速览

| 项 | 值 |
|---|---|
| 维度 | **D = compose in-execution rollback** |
| D-intact | **176** = 76 goal + 100 object（valid n=2） |
| D-rollback | **528** = 176 结构 × 3 窗口 × `L0` |
| 数据源 | 已构建的 compose n=2 定义；只取 valid（排除 14 个 goal conflict ordered） |
| 文件 | [`intact.csv`](../dataset/matrices/libero-compose/intact.csv)、[`rollback.csv`](../dataset/matrices/libero-compose/rollback.csv) |
| 撤销 | D-rollback 恒为 `s1`；`s2` pending，`s2_must_stay_true=true` |
| 预算 | 600 + 600（注入后追加） |
| 控制 | 无矩阵 C0；目标设计是窗口 synthetic no-op，未实现 |
| 状态 | 矩阵/定义/资产已建；D window runner 已实现（静态 + fake-env 验证）；未跑真实仿真/无 D 结果 |

---

## 1. D 在叙事中的位置

D 是 **composed × in-execution** 这一格：

- 任务来自组合结构：goal 的 45 个无序对（ordered 90）和 object 的 50 个无序对（ordered 100），**只取 n=2**；
- 只取 `valid=true`：goal 76（14 个 conflict 排除）+ object 100 = **176**；
- **不做 n=3/n=4**：旧 `160 = 120 n=2 + 40 n=3` 的口径作废；
- D-intact 是同一批结构的无撤销基线；D-rollback 是撤销 `s1` 的执行中臂；
- D 与 C 的差异是任务结构（native vs composed），不是撤销时机。

当前矩阵与 BDDL/init 资产都已入仓；D window runner 已实现，尚未跑真实仿真。

---

## 2. 两个子集

### 2.1 D-intact（176）

| 项 | 值 |
|---|---|
| goal valid | 76（90 ordered 中排除 14 conflict） |
| object valid | 100 |
| 总计 | **176** |
| 每个结构 | 1 条，无撤销 |
| level | `INTACT` |
| `semantics` | `relation_holds_intact` |
| 预算 | `max_steps=600`，`repair_window=0` |
| `case_id` | `compose-intact-<task_id>` |

D-intact 回答“模型会不会做这个 n=2 组合”，不是 Rollback 结论。

### 2.2 D-rollback（528）

| 项 | 值 |
|---|---|
| 结构 | 176 |
| 窗口 | `early` / `mid` / `later`，各 176 |
| level | 全部 `L0` |
| 行数 | **528** = 176 × 3 |
| `s1` | 该 ordered 任务的第一 goal 原子 |
| `s2` | 第二 goal 原子；`s2_must_stay_true=true` |
| 预算 | 600 + 600 |
| `case_id` | `compose-rollback-<task_id>-<window>-l0` |

D-rollback 只用 `L0`；D 的 level 曲线不在本套件。不要期待 D 有 `L1`/`L2`。

---

## 3. 数据源与资产

- 定义快照：[`dataset/matrices/libero-compose/definitions/metadata.jsonl`](../dataset/matrices/libero-compose/definitions/metadata.jsonl)，176 行 valid-only。
- 来源：已构建的 compose n=2 套件（goal 76 valid / object 100 valid）；每行保留 `task_id`、`goal_atoms`、`bddl_sha256`、`pruned_init_sha256`。
- BDDL/init 已复制进本仓 `dataset/compose/bddl/`；`bddl_name = task_id`，`init_source = bddl/<task_id>.pruned_init`，`COMPOSE_ROOT=dataset/compose`。352 个文件与哈希逐一对应。
- 14 个 goal `conflict` ordered 被排除；不要把它们算进 D 主表。

---

## 4. 列

### 4.1 D-intact

关键列：

```text
case_id, test_suite=compose, dimension=intact, arm=intact,
sub=compose, suite=compose, struct_id, source_suite, order,
task_id, instruction, goal_atoms, n_atoms, family,
level=INTACT, param="", semantics=relation_holds_intact,
max_steps=600, repair_window=0, expected_relation_after=true,
bddl_name, init_source, bddl_sha256, pruned_init_sha256, valid, class
```

- `goal_atoms` 用 `|` 连接两个原子。
- `family` 按 `s1` 的谓词类型：`Open`/`Close`/`Turnon` 为 joint，`In`/`On` 为 pose。
- 分布：pose 158 / joint 18；goal 76 / object 100。

### 4.2 D-rollback

关键列：

```text
case_id, test_suite=compose, dimension=in-execution, arm=rollback,
sub=compose, suite=compose, struct_id, source_suite, order,
task_id, instruction, window, trigger_criterion, target=s1,
revoked_predicate, revoked_object, family, level=L0, param="",
semantics=relation_then_resume, max_steps=600, repair_window=600,
expected_relation_after=false, s2_must_stay_true=true,
bddl_name, init_source, bddl_sha256, pruned_init_sha256, valid, class
```

- `trigger_criterion` 是旧标签：`s1 first true` / `s2 displacement > 5 cm` / `distance to s2 goal < 8 cm`；实现必须映射到 GT 事件，不得复用旧阈值。
- `revoked_object` 是 `s1` 谓词的被操物体；joint 的 region 后缀会剥离到 body（如 `wooden_cabinet_1`）。
- 分布：pose 474 / joint 54；goal 228 / object 300（每结构 3 窗口）。

---

## 5. 预算、门控与读数

- 预算：`max_steps=600`，注入后 `total_budget_steps = injection_step + 600`。
- 共用门控：pre 真、注入后假、无穿模 ≤1 cm、零速度、已释放、restorable、几何记录。
- D 额外：`s1_reachable`、`event_fires_reproducibly`、`s2_undisturbed_by_injection`；窗口 `trigger_rate` 实测。
- 主指标：`Recovery`；D-intact 不产生 Recovery，提供 `SR` / `EGC` / `PP` 基线。
- 评估口径见 [`evaluation.md`](evaluation.md)：`Recovery` + `Progress` + 配对 `ΔProgress/ΔSR`。
- D 没有矩阵 C0；窗口 `control_rate` 当前只能 `N/A`；目标设计是 synthetic no-op，未实现。
- D 目前是**定义矩阵**，不是结果矩阵；不能报 D Recovery。

---

## 6. 与 B/C/A 的关系

| 对比 | 回答的问题 |
|---|---|
| A ↔ D-intact | 组合结构是否本身可做（不撤销） |
| D-intact ↔ D-rollback | 同一组合结构上的执行中撤销 |
| C ↔ D | in-execution 在 native vs composed 上是否不同（跨结构，非同任务配对） |
| B ↔ C | 同任务、同 s1、同 level，只换撤销时机（60 对/窗口） |

D 不能和 B/C 合并 Recovery 分母；D-intact 不是 Rollback。

---

## 7. 生成与静态校验

```bash
python scripts/build_compose_suite.py          # 重建 intact.csv + rollback.csv
python scripts/build_compose_suite.py --check  # 静态比对
```

- 生成器从 `definitions/metadata.jsonl` 读取 valid-only n=2 定义；不新增/改写 case 值。
- `scripts/build_suite_matrices.py` 只负责 B/C；D 由 `build_compose_suite.py` 负责。
- 静态测试：[tests/test_suite_matrices.py](../tests/test_suite_matrices.py)。

### 7.1 运行

```bash
# D 计划（资产已在仓内）
python scripts/run_window_matrix.py --dry-run \
  --matrix dataset/matrices/libero-compose/rollback.csv \
  --compose-root dataset/compose --output runs/d-plan

# 真实 D 运行（仍需 LIBERO_HOME 提供网格/场景资产）
LIBERO_HOME=/path/to/LIBERO COMPOSE_ROOT=dataset/compose \
python scripts/run_window_matrix.py --policy pi05 --checkpoint "$PI05_CHECKPOINT" \
  --matrix dataset/matrices/libero-compose/rollback.csv \
  --windows later --max-cases 1 --output runs/d-smoke
```

---

## 8. 当前状态

| 项 | 状态 |
|---|---|
| D-intact 176 | ✅ 定义矩阵 |
| D-rollback 528 | ✅ 定义矩阵 |
| D BDDL/init 资产 | ✅ 已入仓 `dataset/compose/bddl/`（176×2 文件） |
| D runner / 窗口触发 | ✅ 已实现 `window_runner`（未跑真实仿真） |
| D 结果 | ⬜ 无 |
| D 控制 | ⬜ synthetic no-op 未实现 |

---

## 9. 限制

- 矩阵与 BDDL/init 资产已入仓；静态测试校验文件/哈希，但仍未跑真实仿真。
- 没有真实 D 执行结果；不能把 528 行当 Recovery 证据。
- 14 个 goal conflict ordered 排除；object 全部 valid。
- 没有矩阵 C0；窗口控制 `N/A` 或 synthetic。
- 旧 `d-compose-provisional.csv`（360 行 `<from C>`）已被本定义矩阵取代，保留作历史。
