# Rollback 叙事（base-only 决策版）：任务结构 × 撤销时机

> 状态：**base-only 决策版（2026-11-21）**。
> 本版以最新要求为准：**只考虑 base 测试（非 Plus）**；B 回到 `b-matrix.csv`（442），不再使用 B-plus。
> 四条已定决策：B 用 base；C 只做 in-execution（180，无 C0）；旧 C-intact 并入 D；case 矩阵按测试套命名。
>
> 机器可读矩阵：
> [`libero-rollback/completion-rollback.csv`](../dataset/matrices/libero-rollback/completion-rollback.csv) ·
> [`libero-rollback/in-execution-rollback.csv`](../dataset/matrices/libero-rollback/in-execution-rollback.csv) ·
> [`libero-compose/rollback.csv`](../dataset/matrices/libero-compose/rollback.csv)

---

## 0. 一句话与 2 轴网格

**一句话**：本仓研究“一个已经完成的子任务被外部撤销后，模型能否识别并恢复”；区别只在于**撤销发生在完成边界还是执行中**，以及**任务来自原生 LIBERO 还是组合结构**。

```text
                          任务结构
                  native（LIBERO）              composed（组合）
              ┌──────────────────────────┬──────────────────────────┐
  no rollback │ A  原始 LIBERO，40        │ D-intact  组合基线，176 │
              │    无撤销，SR/Retention    │    无撤销，SR/EGC/PP        │
              ├──────────────────────────┼──────────────────────────┤
  completion  │ B  base 442，all_done     │ （未来：compose completion）│
  rollback    │    C0/L0/L1/L2            │                          │
              ├──────────────────────────┼──────────────────────────┤
  in-execution│ C  L10，180（3 windows）  │ D-rollback 组合执行中撤销   │
  rollback    │    无 all_done_control    │    3 windows，528│
              └──────────────────────────┴──────────────────────────┘
```

四个结论：

1. **A 不是 Rollback 维度**，是无撤销基线；B/C/D 是三种 Rollback 条件。
2. **B 是 base 版本**：`b-matrix.csv`，442 条；不再使用 B-plus。
3. **C 只保留 in-execution 的三个窗口**；`all_done_control` 已由 B 的 `C0` 覆盖，C 不再重复。
4. **D = D-intact + D-rollback**；旧 C-intact 不再独立成套件；D-intact 是组合结构的无撤销基线。

---

## 1. 四个分析维度（不是矩阵文件名）

| 维度 | 描述 | 要回答的问题 | 撤销时机 | 任务结构 | 当前数据 |
|---|---|---|---|---|---|
| **A** | `native-intact` | 不做撤销时，原生单任务能力上界 | — | 原生 LIBERO 4 suites | `a-matrix.csv`，40 |
| **B** | `native-completion-rollback` | 任务完成后，完成状态（或子任务）被撤销——能否识别并恢复 | `all_done` + delay 10 | 原生 LIBERO 4 suites | `b-matrix.csv`，**442**（C0 40 / L0 60 / L1 180 / L2 162） |
| **C** | `native-in-execution-rollback` | 执行原生长程任务时，前序 `s1` 已完成、`s2` 仍 pending，`s1` 被撤销——能否识别并恢复 | `early` / `mid` / `later` | 原生 LIBERO-10（9 任务） | **180**：3 窗口 × 60，无 C0 |
| **D** | `compose-in-execution-rollback` | 组合长程任务中，前序子任务被撤销——能否识别并恢复 | `early` / `mid` / `later` | 组合结构（n=2，goal+object valid） | D-intact 176；D-rollback 528 |

> **矩阵文件名不使用 A/B/C/D。** 实际 case 矩阵按测试套组织（见 §7）；A/B/C/D 只出现在分析、报告与维度表。

---

## 2. 两个轴

### 2.1 轴 1：撤销时机

| 时机 | 定义 | 维度 |
|---|---|---|
| `completion` | 任务全部 native goal 为真后，再撤销已完成关系 | **B** |
| `in-execution` | 任务执行中，前序子任务已完成、后续仍 pending 时撤销 | **C**（native）、**D**（composed） |

### 2.2 轴 2：任务结构

| 结构 | 定义 | 维度 |
|---|---|---|
| `native` | 原始 LIBERO 任务；不改变场景/物体/指令，只做状态写回 | **A**（基线）、**B**、**C** |
| `composed` | 由旧 C `composition-intact` 在 40-task pool 内配对生成的结构 | **D**（intact + rollback） |

### 2.3 为什么 C 只覆盖 L10

- Goal/Object/Spatial 基本是**单目标**，没有“前序子任务 + 后续 pending 子任务”的结构，in-execution 撤销无从定义。
- LIBERO-10 是原生多目标任务，有 `s1`/`s2` 和多窗口；C 只取 9 个多目标任务（`t276` 单目标，不在 C）。
- B 在 `all_done` 可以覆盖全部 4 个 suite，因为任何任务都有完成状态；C 只在有子任务结构的 L10 上成立。这是分工，不是缺口。

### 2.4 为什么 D 需要 D-intact

- D 的问题不是“会不会做组合任务”，而是“组合任务里，前序状态被撤销后能否恢复”。
- 没有 D-intact，D-rollback 的失败无法区分“组合本身不会”与“撤销后不会恢复”。
- 因此旧 C `composition-intact` **并入 D**，不再是独立套件；旧 C 的 EGC/PP 指标保留为 D baseline 分析。

---

## 3. B：base completion rollback

### 3.1 数据

B 使用 `dataset/matrices/b-matrix.csv`（base，非 Plus）：

| 维度 | 值 |
|---|---|
| rows | **442** |
| suite | goal 85 / object 80 / spatial 80 / l10 197 |
| level | `C0` 40 / `L0` 60 / `L1` 180 / `L2` 162 |
| target | `g` 211 / `s1` 60 / `s2` 57 / `both` 70 / `pre` 4 / `c0` 40 |
| family | pose 350 / joint 24 / mixed 28 / C0 40 |
| 触发 | `all_done` + `delay_steps=10` |
| 预算 | 600 + 600（注入后追加） |

- 每任务恰好 1 条 `C0`；`C0` 是 `all_done` 时机的 no-op 控制。
- l10 有 197 条（C0 10 / L0 28 / L1 84 / L2 75）；l10 `s1` 60 条（`L0` 9 / `L1` 27 / `L2` 24）。

### 3.2 Plus 退出主叙事

- `dataset/matrices/plus/`、`docs/B-matrix-plus.md` 保留为历史/可选资产，但**不进入** base 主表、静态测试或本叙事。
- B 不再有 B-plus/B-core 双表；不再引用 O2 落点。
- 这样 B 与 C 的落点/level 定义一致，B(l10, s1) ↔ C 的 60 对配对重新成立（见 §6）。

### 3.3 `all_done_control` 已在 B 里

- B 的 `C0` 覆盖 `all_done` 时机的 no-op 控制（l10 10 条）。
- C 不再重复 `all_done_control`；C 的 9 条旧控制行被移除（189 → 180）。
- B 的 `C0` **不能**代替 C 的窗口控制：时机不同（`all_done` vs `early/mid/later`）。C 如果以后需要窗口 no-op，只能另做 synthetic 控制；当前 C 矩阵没有控制。

---

## 4. C：只做 in-execution rollback

### 4.1 C 的数据

| 项 | 值 |
|---|---|
| 来源 | 旧 `d-native-matrix.csv`，**去掉** 9 条 `all_done_control` |
| 行数 | **180** = 3 窗口 × 60 |
| 任务 | 9 个 L10 多目标任务 |
| 窗口 | `early` 60 / `mid` 60 / `later` 60 |
| level | `L0` 27 / `L1` 81 / `L2` 72；**无 C0** |
| 每任务 | `t000` 12；其余 8 个任务各 21 |
| 撤销 | 恒为 `s1`；`s2` pending；`s2_must_stay_true=true` |
| 预算 | 800 + 600 |
| 状态 | 矩阵已生成；C/D window runner 已实现（未跑真实仿真） |

### 4.2 C 的结构

```text
每窗口 = 8 个 pose 任务 × 7 + t000（joint s1）× 4
       = 56 + 4 = 60
C 总数 = 3 × 60 = 180
```

- `t000` 的 `s1` 是关节（`Turnon stove`），无 `L2`；每窗口 4 条（L0 + 3 L1），3 窗口 12 条。
- 其余 8 个任务每窗口 7 条（L0 + 3 L1 + 3 L2），3 窗口 21 条。

按 level / family / param：

| 维度 | 取值 |
|---|---|
| level | `L0` 27 / `L1` 81 / `L2` 72（无 C0） |
| family | `pose` 168 / `joint` 12 |
| param | 空 27 / `d03` 27 / `d06` 27 / `d10` 27 / `r30` 24 / `r60` 24 / `r90` 24 |
| window | `early` 60 / `mid` 60 / `later` 60 |

### 4.3 C 的对照问题

- C 没有矩阵内控制；`all_done_control` 由 B 覆盖，但**不是窗口控制**。
- 如果报告需要窗口 `control_rate`，只能：报 `N/A`，或实现 synthetic no-op（目标设计，当前未实现）。不能拿 B 的 `C0` 当 C 的窗口控制。
- C 的主指标仍是 `Recovery`；分母 = 窗口触发且注入有效的 180 条 treatment；不可触发记 `N/A`。

---

## 5. D：intact + rollback

### 5.1 两个子集

| 子集 | 旧名 | 数据 | 目标 | 状态 |
|---|---|---|---|---|
| **D-intact** | 旧 C `composition-intact` | `intact.csv` 176 | 76 goal + 100 object valid n=2，无撤销 | ✅ 定义已建 |
| **D-rollback** | 旧 D-compose | `rollback.csv`（528） | 176 个 n=2 结构 × 3 窗口 × `L0` | ✅ 定义/资产已建；runner 已实现 |

### 5.2 叙事

- **D-intact** 是组合结构的无撤销基线；回答“模型会不会做这个组合”，不是 Rollback 结论。
- **D-rollback** 是同一结构上的执行中撤销；回答“组合结构上前序状态能否恢复”。
- D 的定义矩阵已真实（不再有 `<from C>` 占位）；BDDL/init 资产已入仓 `dataset/compose/bddl/`；D window runner 已实现。
- D 的控制：窗口内没有矩阵 C0，目标设计是 synthetic no-op；当前未实现。
- D-intact 是**每个结构一条**，不按窗口展开；窗口只属于 D-rollback。否则会把“结构能力”和“触发时机”混在一起。

### 5.3 D-rollback 的 528 行

- 176 个真实 n=2 `struct_id` × `early`/`mid`/`later` × `L0`。
- `instruction` / `revoked_predicate` / `revoked_object` 来自 compose 定义，已绑定。
- `max_steps=600`、`repair_window=600`、`target=s1`、`expected_relation_after=false`；`s2_must_stay_true=true`。
- 不能当 D 结果（尚未跑真实仿真）；不能和 B/C 的分母合并。

---

## 6. 可比较对

| 对比 | 唯一变化的因子 | 回答的问题 | 使用数据 |
|---|---|---|---|
| A ↔ B | 完成后的撤销 | 原生任务上，完成状态保持的净效应 | A + B |
| B(l10, s1) ↔ C(任一窗口) | 撤销时机（`all_done` vs 窗口） | pending 目标带来的额外恢复代价 | B + C；每个窗口 **60 对** |
| A ↔ D-intact | 结构是否组合 | 模型是不是“不会没见过的组合” | A + D-intact |
| D-intact ↔ D-rollback | 执行中撤销 | 组合结构上的状态完整性 | D-intact + D-rollback |
| C ↔ D | 任务结构（native vs composed） | 执行中撤销在组合结构上是否更难 | C + D（跨结构，非同任务配对） |
| `C0` ↔ `L0/L1/L2` | 是否真的改变状态 | 排除“延迟/继续本身有害” | B/C（各自口径） |
| `revoke` ↔ `revoke+restate` ↔ `noop+restate` | 是否重发指令 | 分清“不知道”与“不能” | B/C/D 子集 |

**B↔C 的 60 对**：

```text
B(l10, s1)  = L0 9 + L1 27 + L2 24 = 60
C(任一窗口) = L0 9 + L1 27 + L2 24 = 60   # t000 的 s1 是 joint，无 L2
```

- 这是 base 版本重新成立的干净配对：同任务、同 `s1`、同 level，只换撤销时机。
- B 的 l10 `C0` 10 条是 `all_done` 控制；C 没有 C0；B 的 C0 不能当 C 的窗口控制。

**红线**：

- B、C、D 的 Recovery 分母不同，不能并排成一个量。
- B 与 C 不能合并；C 与 D 不能合并。
- 跨套件只做配对差；C↔D 是跨结构比较，必须显式说明不是同任务配对。
- D-rollback 是定义矩阵，runner 已实现但尚未跑真实仿真，不能报 D 结果。

---

## 7. Case 矩阵按测试套组织

### 7.1 两个测试套

```text
dataset/matrices/
├── libero-rollback/                 # 测试套 1：B + C
│   ├── completion-rollback.csv      # B：base b-matrix，442
│   ├── in-execution-rollback.csv    # C：L10 三窗口，180，无 C0
│   └── README.md
├── libero-compose/                  # 测试套 2：D-intact + D-rollback
│   ├── intact.csv                   # D-intact：176
│   ├── rollback.csv                 # D-rollback：528
│   └── README.md
└── a-matrix.csv                     # A：原始 LIBERO 基线
```

- **B/C/D 不出现在文件名里**；它们是分析维度，写在 `dimension`/`arm`/`test_suite` 列和报告分组里。
- A 保留原始 LIBERO 基线；如果以后统一套件命名，可迁到 `libero-native/`，但不塞进两个 rollback 套件。
- `libero-rollback` 是**套件目录**，不是把 B/C 硬拼成一个 CSV：B 是 17 列 + 3 列标签，C 是 19 列 + 3 列标签；强行合并会出现大量空列。
- 如果必须“一个套件一个 CSV”，建议只做 `suite.yaml` / `cases.csv` 索引，不硬合并 schema。

### 7.2 列标签

| 列 | 取值 | 用途 |
|---|---|---|
| `test_suite` | `libero-rollback` / `compose` | 矩阵归属（`compose` 对应显示名 `libero-compose`；dataset 文本禁止前序仓 token） |
| `dimension` | `completion` / `in-execution` / `intact` | 报告映射到 B/C/D |
| `arm` | `rollback` / `control` | B 的 C0 为 control；C/D 全为 rollback（D 无控制） |

- 不使用 `dimension=B` 这类字母列；报告再把 `completion` 映射到 B、`in-execution` 映射到 C/D。
- case_id 保留来源 id（`b-...` / `d-l10-...` / `d-compose-...`）用于追溯；新 id 规则另做版本化评审。

### 7.3 生成器

```bash
python scripts/build_suite_matrices.py          # 重建三个 suite CSV
python scripts/build_suite_matrices.py --check  # 静态比对，不写文件
```

生成器只重组冻结行：
- B：`b-matrix.csv` → `completion-rollback.csv`（442）
- C：`d-native-matrix.csv` 过滤 `window != all_done_control` → `in-execution-rollback.csv`（180）
- D-intact：compose valid n=2 → `intact.csv`（176）
- D-rollback：176 × 3 窗口 × L0 → `rollback.csv`（528）

---

## 8. 叙事/章节结构

1. **问题**：模型是否知道并修复一个已经被外部撤销的已完成子任务？
2. **两个轴**：撤销时机（completion vs in-execution）× 任务结构（native vs composed）；A 是无撤销基线。
3. **B：completion × native**：base 442；C0/L0/L1/L2；l10 s1 60 是 C 的配对入口。
4. **C：in-execution × native**：L10 三窗口；`s1` 撤销、`s2` pending；180 条，无 C0；all_done 控制由 B 负责。
5. **D：in-execution × composed**：D-intact 先证明组合能力，D-rollback 再谈撤销；BDDL/init 资产已入仓，D window runner 已实现。
6. **指标与控制**：Recovery/SR/trigger_rate/Retention；各套件控制分离；不可混报。
7. **结果与证据状态**：B 有 pi05 结果；C/D 定义矩阵已建，但无 v2 执行结果。
8. **限制**：C 无窗口控制；D 尚未跑真实仿真；单 seed/init。

---

## 9. 当前状态与缺口

| 维度 | 数据 | Runner | 结果 | 主要缺口 |
|---|---|---|---|---|
| A | 40，冻结 | 基线 | 历史三模型 | 无 |
| B | 442，base | B runner | pi05 已完成 | L10 全量/统计口径 |
| C | 180，已生成 | **无** | **无** | C loader/runner + `runtime/triggers.py` |
| D-intact | 176，定义已建 | 无 | 无 | D runner 已实现 |
| D-rollback | 528，定义已建 | 无 | 无 | 控制、runner |

---

## 10. 仍需确认

1. **C 的窗口控制**：没有矩阵 C0；报告是直接 `N/A`，还是实现 synthetic no-op？当前都没有实现。
2. **A 的矩阵归属**：保留 `a-matrix.csv`，还是迁到 `libero-native/`？不影响 B/C/D 主叙事。
3. **D 资产路径**：已复制入仓；统一使用 `COMPOSE_ROOT=dataset/compose` 解析。

---

## 11. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-11-20 | 初版：A/B/C/D 两轴叙事 |
| 2026-11-20 | 按批注修订：B-plus 替换 B-core；C 去 `all_done_control`；D-intact 并入 D；矩阵按测试套命名 |
| 2026-11-21 | **base-only 修订**：B 回到 `b-matrix.csv`（442）；Plus 退出主叙事；C 180 base 矩阵已生成；D-intact 176 / D-rollback 528 定义矩阵已生成；新增 `libero-rollback` / `libero-compose` 套件与生成器 |
