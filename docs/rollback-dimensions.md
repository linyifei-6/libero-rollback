# 两个 Rollback 维度（数据集组织原则）

> **2026-11-21 base-only 已更新**：只考虑 base 测试（非 Plus）；B = 442，C = 180（无 C0），D = compose intact（未建）+ rollback（360 provisional）。
> 新叙事见 [`docs/rollback-narrative.md`](rollback-narrative.md)；本文件的两维版本保留作历史，待整体迁移。

> 版本：2026-11-19 ｜ 权威图：[`docs/figures/rollback-dimensions.svg`](figures/rollback-dimensions.svg) ｜ 数据契约：[`docs/SPEC.md`](SPEC.md) §3 ｜ 阅读说明：[`docs/b-matrix.md`](b-matrix.md) · [`docs/d-matrix.md`](d-matrix.md)
>
> 本文定义本仓**数据集组织的两个 Rollback 维度**，以及 A/C 两个无撤销对照。所有矩阵、case、指标和实验都按这四类归档；术语冲突时以本文与 SPEC 为准。

---

## 0. 一句话

本仓不是"又一个组合 benchmark"：数据集只围绕**两个 Rollback 维度**组织，A/C 是无撤销的对照/参照。

| 维度 | 套件 | 一句话 |
|---|---|---|
| **维度 1：完成后撤销**（completion-boundary rollback） | **B** | 一个任务完成以后，它的**完成状态**（或其中某个**子任务**的完成状态）被外部撤销——策略能否**识别**并**恢复**？ |
| **维度 2：执行中撤销**（in-execution rollback） | **D** | 在执行长程任务时，**前序已完成的子任务状态**被撤销，而后续子任务仍未完成——策略能否**识别**并**恢复**？ |
| 对照（非 Rollback） | **A** | 无撤销：单任务能力上界，作 Retention 参照 |
| 对照/剂量（非 Rollback，Phase 2） | **C** | 无撤销：共时合取的剂量阶梯，作 EGC 载体 |

![图 1：两个 Rollback 维度与两个对照](figures/rollback-dimensions.svg)

> 图 1 的文字描述见 §1；如果只记一句话：**维度 1 问"做完之后还能不能知道自己做过"，维度 2 问"做着下一件事时，上一件事被撤回还知不知道"**。

---

## 1. 两个维度的操作化定义

### 1.1 维度 1 · 完成后撤销（B）

- **触发**：任务的全部 native goal 为真（`all_done`），再延迟 `delay_steps=10` 个控制步；
- **撤销对象**：已完成关系（`target ∈ {g, s1, s2, both, pre}`）。`g` 撤销整个任务的完成状态；`s1` / `s2` 撤销某个子任务的完成状态；`both` 同时撤销两个；
- **场上状态**：撤销时**没有 pending 子目标**（任务已全部完成）——这是它与维度 2 的唯一干净差异；
- **控制**：每任务 1 条 `C0` no-op（同样延迟、同样 post-success 窗口，但不改变状态），必须成功；
- **主指标**：`Recovery`（条件恢复率 = 恢复数 / 注入有效且非 C0 的 case 数）；
- **文件**：`dataset/matrices/b-matrix.csv`（442 case / 40 任务）。

### 1.2 维度 2 · 执行中撤销（D）

- **触发**：任务执行中，前序子任务 `s1` 已完成、后续子任务 `s2` 仍 pending 时注入（`early` / `mid` / `later` 三个窗口）；
- **撤销对象**：已完成的 `s1`（D 恒为 `s1`；不撤销 `s2`/`both`）；
- **场上状态**：撤销时**仍有 pending 目标**——模型必须同时处理"恢复被撤销的旧关系"与"继续推进新目标"；
- **控制**：`all_done_control`（all_done 时机、不注入）作为 no-op 参照；窗口内没有矩阵 C0（已知数据债）；
- **主指标**：`Recovery`（条件恢复率，被撤销的 `s1` 终局是否为真）；
- **文件**：`dataset/matrices/d-native-matrix.csv`（189 case / 9 任务）；`d-compose-provisional.csv`（360 行设计占位，Phase 2）。

### 1.3 两个维度不可混报

两者共享 `C0/L0/L1/L2` 扰动族与同一 Recovery 判定，但**分母与触发不同**：

- B 的 Recovery 分母条件于"任务已完成 + 注入有效"；
- D 的 Recovery 分母条件于"`s1` 曾为真 + 窗口触发 + 注入有效"；
- D 的 `SR` 通常更低（任务本来未完成），B 的 `SR` 在 C0 下应接近基线；
- **禁止**把 B 的 Recovery 与 D 的 Recovery 并排当作同一个量；跨维度比较必须用配对子集（同任务、同 init、同撤销目标）并显式说明。

---

## 2. 与数据集/实验资产的对齐

| 角色 | 矩阵 / 数据 | case 数 | 当前状态 | 实验证据 |
|---|---|---:|---|---|
| **维度 1** | `dataset/matrices/b-matrix.csv` | 442 | ✅ 冻结 | π0.5 Goal+Object 165 审核报告（Recovery 23/137 = 16.8%）、Spatial 80（22/70 = 31.4%） |
| **维度 2** | `dataset/matrices/d-native-matrix.csv` | 189 | ✅ 数据冻结 | ⬜ runner/窗口触发未实现，**无 v2 D 执行结果** |
| 维度 2（占位） | `dataset/matrices/d-compose-provisional.csv` | 360 | 🟡 provisional，不执行 | — |
| 对照 A | `dataset/matrices/a-matrix.csv` | 40 | ✅ 生成 | 三模型 success-delay 历史证据（`experiments/a-libero/`） |
| 对照 C | `dataset/matrices/c-matrix.csv` | 0（目标 160） | ⬜ Phase 2 | 仅 v1 compose 历史证据（`experiments/c-compose/`） |

口径红线：`N/A` 不显示 0%；`restorable` 是状态写回 oracle，不等于模型恢复；外部复原不算模型自修；C0 必须单独报告。

---

## 3. 与历史实验的对应（重要）

前序仓 `libero-rollback` 的 v1 catalog 同时包含 `all_done` 与 `early/mid/later` 两类时机，**没有把两个维度拆开**；v2 把它们拆成：

- `all_done` → **B（维度 1）**；
- `early / mid / later` → **D（维度 2）**。

因此引用历史数字时必须注明它属于哪个维度：

| 历史实验 | 维度归属 | 说明 |
|---|---|---|
| `docs/3model-success-delay-probe-20261117.md`（A/success-delay） | **不是 Rollback** | 只测"完成状态在窗口中是否保持"，没有外部撤销；归 A 证据 |
| `experiment-d0-mid-pi05.md`（v1 d0+mid） | **混合（mid 属维度 2）** | 早期 18/30 是外部复原，已更正为 0/9；迁移后只作历史证据 |
| `basic-single-task-rollback`（all_done） | **维度 1** | 单任务完成后回滚，1/9 恢复 |

---

## 4. 测试与验收（按维度）

1. **维度 1**：B 矩阵逐 case 门控（注入前真、注入后假、无穿模、零速度、已释放、`restorable`）；C0 必须成功；Recovery 分母 = 注入有效且非 C0。
2. **维度 2**：D 矩阵逐 case 门控 + 窗口触发（`trigger_status ∈ {triggered, not_reached_s1, censored_by_s2, not_reached_window}`）+ `s2_undisturbed_by_injection`；只有 `triggered` 进 Recovery 分母。
3. 两个维度共用 `docs/SPEC.md` §5 预算：B 600 + 300；D-native 800 + 300。
4. 报告模板：`docs/report-template/README.md`（白色主题、逐 case 审核注入/恢复有效性）。

---

## 5. 当前缺口

- 维度 2（D）**没有 runner**：`runtime/triggers.py` 与 D-native 执行链路未实现，D 的 189 行数据尚未产生任何结果；
- D-compose 依赖 Phase 2 的 C 结构（120 个 n=2），当前 360 行只是占位；
- C 套件（160 结构）未构建，EGC/PP 不可用；
- B 矩阵尚未跑 L10（197/442），且只有 π0.5 一个模型；
- 所有历史证据为单 seed / 单 init。

---

## 6. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-11-19 | 首次定义"两个 Rollback 维度"：把 B/D 从"四个套件"中提为两个 Rollback 维度，A/C 明确降为无撤销对照；README §3、`docs/b-matrix.md`、`docs/d-matrix.md`、`docs/datasheet.md` 的套件表同步加入"角色"列；新增图 1 |
