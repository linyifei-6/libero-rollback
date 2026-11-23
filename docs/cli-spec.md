# 评测 CLI 规范（v2 · 简化版）

> **2026-11-21 base-only 迁移注记**：B = `b-matrix.csv`（442），C = `libero-rollback/in-execution-rollback.csv`（180，无 C0），D = `libero-compose`（intact 未建 + rollback 360 provisional）；Plus 不进入主表。
> 新叙事见 [`rollback-narrative.md`](rollback-narrative.md)；本文件旧 B/D 口径待迁移。

> 版本：v2-draft ｜ 日期：2026-11-18 ｜ 对象：`libero-rollback 2.0.0.dev0`
> 上位文档：[docs/SPEC.md](SPEC.md)（数据契约）· [docs/protocol.md](protocol.md)（评测协议）· [README.md](../README.md) §3/§6
> 本文只描述**目标接口**；现状对照见 §9。第一轮的长参数参考已按批注压缩，避免把内部实现暴露成接口。

---

## 0. 设计原则

一句话：**本 CLI = LIBERO 原生评测 + 六个能力开关 + 一个控制开关**。不开启任何新开关时，行为就是 LIBERO 的四套件评测（A 基线）。

| 我们比 LIBERO 多的 | 开关 | 取值 | 默认 | 作用 |
|---|---|---|---|---|
| 1. 成功后的延迟 | `--success-delay` | `0,10,30,…`（步） | 10 | 任务完成后第 δ 步才注入 |
| 2. 撤销扰动 | `--rollback` | `goal object spatial l10 goal-compose object-compose` | 关闭 | 开启回滚族，并指定测试套 |
| 3. 组合结构 | `--compose` | `goal-compose object-compose` | 关闭 | 开启组合族（intact，无扰动） |
| 4. 撤销的时机 | `--window` | `all_done early mid later` | 见 §3.4 | B 用 `all_done`，D 用三个窗口 |
| 5. 撤销的强度/形态 | `--level` | `C0 L0 L1[:d03\|d06\|d10] L2[:r30\|r60\|r90]` | 全部 | 撤销到什么状态 |
| 6. 撤销的目标 | `--target` | `g s1 s2 both pre` | 全部 | 撤销哪一个已为真的关系 |
| 7. 控制组 | `--controls` | `auto matrix synthetic both none` | `auto` | 自动补 no-op 对照的方式（§3.7） |

其余参数（模型、输出、预算、渲染、断点续跑）与 LIBERO 评测一致，不新增概念。

三条纪律：

1. **数据文件不是接口**：矩阵的路径、schema、sha256、split 都由 CLI 按"族 + 测试套"内部解析，命令里不出现文件名。
2. **一个 run 可以扫多个取值**：`--level L0,L1:d03`、`--window early,mid,later`、`--success-delay 0,10,30`
   会展开成多个组合，每个组合落在自己的子目录（§7），`report` 一次汇总。
3. **不做假数据**：数据未就绪或触发未实现时，命令明确失败（退出码 2），不产出"看起来像结果"的数字。

---

## 1. 命令

| 命令 | 作用 | 是否核心 |
|---|---|---|
| `run` | 唯一执行入口；`--dry-run` 时只枚举 episode、写计划 | ✅ |
| `report` | 从一个 run 目录生成 `aggregate.json` / `SUMMARY.md` / 自包含 `index.html` | ✅ |
| `validate` | 数据集静态校验（manifest、矩阵、split、路径卫生），不启仿真 | 辅助 / CI |
| `leaderboard validate` | 校验一份提交（episode 齐全、case_id 唯一、可判 verdict） | 辅助 |
| `list` | 打印矩阵清单（当前实现保留，不属于新接口） | 辅助 |

```text
libero-rollback run    --output DIR [--rollback ...] [--compose ...]
                       [--level ...] [--window ...] [--target ...] [--success-delay ...]
                       [--controls ...]
                       [--model ...] [--split ...] [常规参数] [--dry-run]
libero-rollback report --run DIR [--out DIR]
libero-rollback validate [--dataset DIR] [--json]
libero-rollback leaderboard validate --run DIR
```

退出码：`0` 成功；`1` 跑完但校验/结论失败（`validate` FAIL、leaderboard FAIL）；`2` 用法或环境错误
（族/维度组合非法、数据未就绪、缺 `LIBERO_HOME`/checkpoint、空选择等）。

### 1.1 `--dry-run` 的角色（原 `plan` 子命令已删除）

`--dry-run` 不启动仿真、不加载模型，只做三件事：

1. 把 `--rollback/--compose/--level/--window/--target/--success-delay` 展开成具体 case 列表（控制按 `--controls` 补）；
2. 打印每个组合的 episode 数与预算估计（`max_steps + repair_window`）；
3. 写 `<output>/plan.json`（`evidence: false`）。

它和 `run` 的选择逻辑完全同源，所以**不再单独提供 `plan` 子命令**——多一个入口只会让"计划/执行"两套
代码有分叉风险。计划不是证据，任何报告数字都不得来自 `plan.json`（protocol §5）。

---

## 2. 四个族的表达

### 2.1 族 → 开关

| 族 | 命令 | 数据（内部） | 预算 |
|---|---|---|---|
| **A** `single-intact` | 不带 `--rollback` / `--compose` | `a-matrix.csv`（40） | 600 |
| **B** `completion-boundary-rollback` | `--rollback`（默认全部 native 套件） | `b-matrix.csv`（442） | 600 + 300 |
| **C** `composition-intact` | `--compose`（默认两个 compose 套件） | `c-matrix.csv`（目标 160，未构建） | 600 |
| **D-native** | `--rollback l10 --window early,mid,later` | `d-native-matrix.csv`（189） | 800 + 300 |
| **D-compose** | `--rollback goal-compose object-compose` | `d-compose-matrix.csv`（360 占位） | 600 + 300 |

### 2.2 测试套（suite）

| suite | 属于 | 内容 |
|---|---|---|
| `goal` / `object` / `spatial` / `l10` | native | 40 个原生任务（每套 10 个） |
| `goal-compose` / `object-compose` | compose | C 的 120 个 n=2 结构（+40 个 n=3） |

### 2.3 规则

1. **一条命令可以混多个族**：`--rollback goal-compose object-compose l10` 一次加载模型、顺序跑 B(l10) 与
   D-compose；`--compose` 也可以和 `--rollback` 同时给（C 的 intact case 与回滚 case 同批）。
   每个 case 按自己的族取触发判据、预算与门控（§6.1/§6.3），所以**同一个 run 里可以同时存在
   `all_done` 与窗口两种协议**。
2. **`--rollback` 的 suite 决定每个 case 的族**：`goal/object/spatial` → B；`l10` 默认 B、带窗口 → D-native；
   `goal-compose/object-compose` → D-compose。`--compose` 单独用 = C（intact，无注入）。
3. **维度只作用于回滚 case**：`--level/--window/--target` 对 B、D 的 case 生效；`--success-delay` 只对 B 的 `all_done` case 生效；A、C 的 case 不受影响。
4. **过滤不得清空任何一个已选的回滚族**：`--level/--window/--target` 过滤后，每个出现在 `--rollback` 里的族
   都必须至少剩 1 条，否则退出码 2，并列出该族可用取值（例：`--level L1:d03` 遇上只有 L0 的 D-compose）。
5. **族之间只在报告层分开**：`report` 与 `run-summary` 按 `family`（suite）分块，禁止把 B、D、C 放进同一分母。
   可以同批跑，不可以同表比。
6. 不带族开关 = A 基线；此时给维度参数 → 退出码 2。

---

## 3. 七个开关

### 3.1 `--rollback [suite ...]`

```text
--rollback                          # B：全部 native 套件、全部 level
--rollback l10                      # B：只跑 l10（197 条）
--rollback goal object              # B：只跑 goal 与 object
--rollback goal-compose             # D-compose：在组合结构上做撤销
--rollback l10 --window early       # D-native：执行中撤销
--rollback goal-compose object-compose l10   # 混批：D-compose + B(l10)
```

- 无参数 = 全部 native 套件（`goal object spatial l10`）。
- suite 只接受 §2.2 的六个名字；不接受 level（level 用 `--level`）。
- 可以混不同族（§2.3 规则 1）：每个 case 用自己族的协议，报告分族出表；不会混进同一分母。

### 3.2 `--compose [suite ...]`

```text
--compose                      # C：两个 compose 套件都测
--compose goal-compose         # 只测 goal-compose
```

- 无参数 = `goal-compose` + `object-compose`。
- C 是 **intact**（不注入）；要"组合结构 + 撤销"请用 `--rollback <compose suite>`。

### 3.3 `--level`

```text
--level L0                     # 只恢复初始位姿
--level L1                     # 三种外推距离都跑（d03/d06/d10）
--level L1:d03,L2:r30          # 两种形态各取一个参数
--level C0                     # 只跑 no-op 对照
```

| 取值 | 含义 | 备注 |
|---|---|---|
| `C0` | no-op 对照（不动状态） | 每任务 1 条；不写 `--level` 时自动补进控制臂 |
| `L0` | 恢复到 episode 初始位姿/关节 | |
| `L1[:d03\|d06\|d10]` | 沿"目标区域中心 → 初始位姿"外推 3/6/10 cm | 关节任务用开度 10/25/40 % |
| `L2[:r30\|r60\|r90]` | 绕世界 z 轴 yaw 30/60/90° | joint 任务没有 L2 |

- 默认 = 所选 suite 里出现的全部 treatment level（不含 C0；C0 由控制臂自动补齐）。
- `L1`/`L2` 是两种**扰动形态**，不是难度等级；报告必须分形态。
- 参数可省略（= 该 level 的全部参数）；逗号或空格分隔。

### 3.4 `--window`

| 取值 | 含义 | 适用 |
|---|---|---|
| `all_done` | 全部 native goal 为真（任务完成）后再等 `--success-delay` 步 | B |
| `early` | 第一个子目标完成、后续尚未开始 | D-native / D-compose |
| `mid` | 已抓起后序目标物 | D-native / D-compose |
| `later` | 后序物已运到目标上方、尚未放置 | D-native / D-compose |

- 默认：native 回滚 case → `all_done`；compose 回滚 case → `early,mid,later`；混批时按每个 case 的族取默认。
- `--window early|mid|later` 且未指定 suite 时，自动收窄到 `l10`；显式写了非 `l10` 的 native suite → 退出码 2。
- 窗口判定**只用 GT 谓词与仿真状态**（SPEC §3.4）；历史 `trigger_criterion` 字符串必须映射到事件名
  （映射表见 §11.6），不得复用已作废的 5 cm / 8 cm 判据。
- 窗口 `trigger_rate < 20%` 时，该窗口按 `N/A` 出表（不是 0%），并写明原因。

### 3.5 `--target`

| 取值 | 撤销对象 |
|---|---|
| `g` | 任务的目标关系本身 |
| `s1` / `s2` | 第 1 / 第 2 个子目标关系（**D 恒为 `s1`**） |
| `both` | 两个已达成关系一起撤销 |
| `pre` | 撤销前置条件（只存在于 `goal/t030`） |

- 默认 = 矩阵里出现的全部 target。
- 只过滤 B 的 case；D 的 target 恒为 `s1`（`--target s1` 时 D 不受影响）。若给的是其他值且 run 里含 D 的 case，D 会被过滤光 → 按 §2.3 规则 4 报错。

### 3.6 `--success-delay`

```text
--success-delay 10        # 参考协议（默认）
--success-delay 0,10,30   # 三个组合：完成瞬间 / 10 步 / 30 步后撤销
```

- 定义：`first_all_done_step` 之后第 δ 个环境步尝试注入；δ 单位是 env step。
- 门控（沿用现状两段式）：到点后必须"目标全真 ∧ 被撤销关系全真"才注入；否则最多再等
  `--trigger-wait` 步（默认 60），仍不满足则记 `trigger_skipped_reason` 并跳过注入。
- 约束：
  - 只作用于 `all_done` 的 case；纯 D（只有窗口 case）传 `--success-delay` → 退出码 2。
  - `δ + trigger_wait < max_steps`；δ 非负；推荐 `δ % replan == 0`（不对齐会记
    `delay_not_replan_aligned`，默认不进主表）。
  - **C0 控制臂继承同一 δ**：这是把"延迟本身的影响"从"撤销的影响"里扣掉的前提。
- 产物里必须记录：`success_delay`、`case_reference_delay`（矩阵里的参考值 10）、
  `first_all_done_step`、`injection_step`、`injection_lag`。

### 3.7 `--controls`

```text
--controls auto        # 默认：按每个 case 的族自动补（下表）
--controls matrix      # 只补矩阵里的 no-op 行（B 的 C0 / D 的 all_done_control）
--controls synthetic   # 只补窗口匹配的 synthetic no-op（-ctl-none）
--controls both        # 矩阵 + synthetic
--controls none        # 不自动补；control_rate 记 N/A
```

| 模式 | B | D-native | D-compose | A / C |
|---|---|---|---|---|
| `auto` | 矩阵 C0 | 矩阵 C0 + 窗口 synthetic | 窗口 synthetic | 无 |
| `matrix` | 矩阵 C0 | 矩阵 C0（只覆盖 `all_done`） | 无（占位矩阵没有 C0） | 无 |
| `synthetic` | 无窗口 case 时整体拒绝 | 窗口 synthetic | 窗口 synthetic | 无 |
| `both` | 矩阵 C0 | 矩阵 C0 + 窗口 synthetic | 窗口 synthetic | 无 |
| `none` | 无 | 无 | 无 | 无 |

- 混批 run 里按每个 case 的族解析，互不影响；`auto` 就是"每族各取默认"。
- synthetic 控制 = 同窗口触发、不写状态、case_id 加 `-ctl-none`、`control_origin=synthetic`；只对窗口 case 有意义。
- `--level C0` 与 `--controls` 不同：前者把矩阵 C0 当 **case 显式选中**，后者自动补控制；同一 case 会去重。
- 控制不进 Recovery 分母；`--controls none` 时报告 `control_rate = N/A`，不得写成 0%。
- 纯 A/C 的 run 传 `--controls` → 退出码 2（没有可补的控制）。

---

## 4. 示例集

### 4.1 B：全量（442 条）

```bash
libero-rollback run --rollback --output runs/b-full --model pi05 \
  --checkpoint "$PI05_CHECKPOINT"
# 402 treatment（L0 60 / L1 180 / L2 162）+ 40 条 C0 = 442
```

### 4.2 B：只测 l10 的 L1-d03（38 条）

```bash
libero-rollback run --rollback l10 --level L1:d03 --output runs/b-l10-l1d03 ...
# 28 treatment + 10 C0 = 38
```

### 4.3 B：延迟扫描（3 × 442 = 1,326 episodes）

```bash
libero-rollback run --rollback --success-delay 0,10,30 --output runs/b-delay ...
# 每个 δ 一组独立目录；控制臂继承同一 δ
```

### 4.4 D-native：三个窗口（90 条）

```bash
libero-rollback run --rollback l10 --window early,mid,later \
  --level L0,L1:d03 --output runs/d-native ...
# 每窗口 18 treatment × 3 窗口 = 54；控制 = 矩阵 C0 9 + 窗口 synthetic 27 = 36
```

### 4.5 C：组合 intact（Phase 2，目标 160 条）

```bash
libero-rollback run --compose --output runs/c-intact ...
# 当前 c-matrix.csv 为 0 行 → 退出码 2（数据未构建）
```

### 4.6 组合任务的回滚扰动（D-compose）

```bash
# ① 先看规模（不启仿真、不加载模型）
libero-rollback run --rollback goal-compose object-compose \
  --level L0 --window early,mid,later \
  --output runs/plan-d-compose --dry-run
# 3 个组合（每窗口 1 个）；360 条 treatment（120 struct × 3 窗口）

# ② 正式执行（C 就绪后）；窗口 no-op 控制自动补 360 条
libero-rollback run --rollback goal-compose object-compose \
  --level L0 --window early,mid,later \
  --model pi05 --checkpoint "$PI05_CHECKPOINT" \
  --output runs/d-compose
# 共 720 episodes（360 treatment + 360 synthetic control）

# ③ 报告
libero-rollback report --run runs/d-compose
```

**今天**跑会怎样（如实）：`c-matrix.csv` 是 0 行，D-compose 的 360 行是 `<from C>` 占位，
所以 `--dry-run` 可以列出计划（标 `data_status: provisional`），`run` 直接退出码 2：
`error: D-compose data is provisional (C is not built)`。不做假数据，也不产出"看起来像结果"的数字。

### 4.7 一条命令混跑 B(l10) 与 D-compose

```bash
libero-rollback run --rollback goal-compose object-compose l10 \
  --controls auto \
  --model pi05 --checkpoint "$PI05_CHECKPOINT" --output runs/mixed
# 一次模型加载，顺序跑两部分：
#   l10        → B        : all_done + δ=10, 600+600, 197 条 + 10 C0
#   *-compose  → D-compose: 三窗口, 600+600, 360 条 + 360 synthetic
# report 按 suite/family 分块，B 与 D-compose 各自成表
```

为什么以前说"不能混"：那不是数据的要求，而是上一版为了让 `run` 只有一个"当前协议"而加的简化。
runner 本来就是逐 case 循环，只要**每个 case 自带 (family, trigger, budget, gates)**，一次 run 完全可以混族；
代价只是报告必须分族、不能合并分母（§2.3 规则 5）。

今天：l10 部分可跑；compose 部分因 C 未构建会让整条命令退出码 2（不静默跳过）。只想跑能跑的用
`--rollback l10`；`--dry-run` 能看到两部分的完整计划。

---

## 5. 全部参数（`run`）

### 5.1 七个开关

六个能力开关 + 控制开关，见 §3.1–§3.7。

### 5.2 沿用的常规参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--output` | 必填 | run 目录 |
| `--model` / `--checkpoint` | `none` / 模型环境变量 | 每 run 只加载一个 adapter；`none` = 零动作 |
| `--split` | `core` | `lite / core / full`；`lite` 按 `lite.yaml`（30 条）过滤 |
| `--max-tasks` / `--max-cases` | 0 | 截断；`--max-tasks` 在当前子集内取前 N 个 task |
| `--shard-index` / `--shard-count` | 0 / 1 | 按 `index % count` 切分，先 split 后分片 |
| `--init-row` / `--seed` | 0 / 0 | 单值（variance 子集用 0–4，外部循环） |
| `--max-steps` / `--repair-window` | 按族（600/800）+ 600 | 注入后的修复窗口是**追加**预算 |
| `--replan` / `--trigger-wait` | 10 / 60 | chunk 长度 / 到点后最多再等 |
| `--camera` / `--settle-steps` | 256 / 10 | 渲染与稳定步数 |
| `--video` / `--video-fps` | 开 / 20 | 视频与注入卡 |
| `--libero-home` / `--libero-python` | 环境变量 | LIBERO checkout / 读 init 的兜底解释器 |
| `--resume` / `--retry-errors` / `--retry-invalid` | 开 / 关 / 关 | 断点续跑（键含组合维度，见 §7） |
| `--dry-run` | 关 | 只写 `plan.json` |

旧接口里的**矩阵文件路径参数**、**suite 过滤参数**、独立的 `plan`/`compare` 子命令均已删除；
suite 直接写在 `--rollback` / `--compose` 里。

---

## 6. 语义（一遍讲清）

### 6.1 触发

| 族 | 触发 | 注入时刻 |
|---|---|---|
| B | `all_done`（全部 native goal 真） | 完成后第 δ 步（`--success-delay`） |
| D | `early/mid/later`（GT 事件） | 事件当步 |
| A / C | 无注入 | — |

### 6.2 注入与有效性门控

- 注入直接写 MuJoCo `qpos/qvel` 后 `mj_forward`；`C0` 不写状态（no-op 对照）。
- 每条非 C0 case 必须同时通过：`completed_relation_true_before_intervention`、
  `relation_false_after_intervention`、`no_object_penetration`（≤1 cm）、
  `zero_velocity_after_intervention`、`object_released`（两指间距 > 1 cm），否则记 `injection_invalid`。
- D 额外：`s1_reachable`、`event_fires_reproducibly`（`trigger_step` 偏差 ≤1 步）、
  `s2_undisturbed_by_injection`。

### 6.3 预算

| 族 | `max_steps` | 注入后追加 | 说明 |
|---|---|---|---|
| A / C | 600 | — | 无注入 |
| B | 600 | 600 | 注入后总预算 = `injection_step + 600` |
| C / D-native | 800 | 600 | 任务未完成，需要更长 |
| D-compose | 600 | 600 | |

逐 episode 记录 `repair_budget_steps` 与 `repair_steps_used`。

### 6.4 控制

由 `--controls` 决定（默认 `auto`，模式表见 §3.7）。要点：

- B 的 `auto` = 矩阵 C0（每个 δ 一份）；D-native = 矩阵 C0 + 每窗口 synthetic；D-compose = 窗口 synthetic。
- synthetic 控制：同窗口触发、不写状态、case_id 加 `-ctl-none`、`control_origin=synthetic`；
  D 的矩阵 C0 全在 `all_done`，所以窗口内没有现成对照（数据债见 §11.5）。
- 混批 run 里每个 case 按自己的族取控制，互不影响。
- 控制不进 Recovery 分母；报告按 `control_origin` 分列；`--controls none` 时 `control_rate = N/A`。

### 6.5 每条 episode 必记字段

```jsonc
"dimensions": {"suite": "l10", "window": "early", "level": "L1", "param": "d03",
                "target": "s1", "success_delay": 10},
"control_origin": null,            // null | "matrix" | "synthetic"
"first_all_done_step": 212, "injection_step": 242, "injection_lag": 10,
"relation_before": true, "relation_after_injection": false, "relation_final": false,
"case_valid": true, "recovered": false, "repair_budget_steps": 600, "repair_steps_used": 187
```

---

## 7. 产物与目录

```text
<output>/
├── run-manifest.json     # 开关、解析出的族/数据 sha、argv、环境摘要
├── plan.json             # 仅 --dry-run（evidence: false）
├── episodes.jsonl        # 一行一个 case（含 dimensions，追加写）
├── run-summary.json      # Recovery / control / trigger / 成本
├── report.md
├── report/               # report 命令产物：aggregate.json / SUMMARY.md / index.html
└── <suite>/<case_id>/[dly-<δ>/]init-<i>/seed-<s>/
    ├── summary.json      # 唯一权威的 episode 证据（失败也写）
    ├── trace.jsonl       # episode_start / trigger / injection / step / episode_end
    └── video.mp4
```

- `dly-<δ>` 只在 δ ≠ 参考值（10）时出现，避免和主表目录混在一起。
- 断点续跑键 = `(suite, case_id, δ, init, seed)`；`summary.json.status == "ok"` 且维度一致才跳过。
- 一个 run 扫多个维度时，上述结构只有一份 `episodes.jsonl`，按 `dimensions` 分组聚合，
  不需要额外的 sweep 文件。

报告口径（SPEC §6 / protocol §9）：

1. `Recovery = valid_recovered / (valid_recovered + valid_not_recovered)`；控制、无效注入、外部复原、
   协议不完整、不可触发**一律排除**。
2. `control_rate` 按 `control_origin` 分列。
3. `trigger_rate` 分母 = 尝试数；窗口 < 20% → `N/A`（不是 0%）。
4. 每个数字带 **init 数 + 预算 + Wilson 95% CI**。
5. 未对齐 δ（`delay_not_replan_aligned`）与 provisional 数据默认进附录。

---

## 8. 校验与退出码

| 规则 | 检查 | 失败 |
|---|---|---|
| V1 | 纯 A/C 的 run 带维度开关（`--level/--window/--target/--success-delay`） | 2 |
| V2 | suite 名字合法（§2.2 的六个）；混族时按每个 case 解析 | 2 |
| V3 | `--level` 语法（`C0/L0/L1[:d0x]/L2[:r0x]`）与 `L2`×joint、`pre` 只在 `goal/t030` | 2 |
| V4 | `--window` 取值与 case 族匹配（窗口只在 `l10` / compose 有定义） | 2 |
| V5 | `--success-delay` 至少作用于一个 `all_done` case；δ 非负且 `δ+trigger_wait < max_steps` | 2 |
| V6 | `--target` 只在 native 回滚族 | 2 |
| V7 | 过滤后每个已选回滚族非空（§2.3 规则 4） | 2（打印该族可用取值） |
| V8 | 数据就绪（C 未构建 / D-compose provisional 时 `run` 拒绝） | 2 |
| V9 | `--dry-run` 之外的必需环境（`LIBERO_HOME`、checkpoint、init 文件） | 2 |
| V10 | `--shard-count ≥ 1`、`0 ≤ index < count` | 2 |
| V11 | `--controls` 取值合法；`synthetic` 无窗口 case 时拒绝；纯 A/C 传 `--controls` | 2 |

`1` 只用于"跑完但结论失败"（`validate` FAIL、leaderboard FAIL、报告口径校验失败）。

---

## 9. 与现状的差异（迁移）

| 现状 | 新接口 | 说明 |
|---|---|---|
| 必须显式给矩阵文件路径 | 删除；按 suite 内部解析 | 用户只表达"测什么" |
| suite 过滤参数 | 写进 `--rollback` / `--compose` | 一个概念一个地方 |
| 固定 `delay=10`（矩阵强制） | `--success-delay` 多值扫描 | 产物记录真实 δ 与参考值 |
| 无 level 选择（只能手抄 case_id） | `--level` | |
| 无窗口触发（D 未实现） | `--window` | 依赖 `runtime/triggers.py`（Phase 2） |
| 无 target 选择 | `--target` | |
| `--repair-window` 被矩阵覆盖、不生效 | CLI 优先，矩阵值仅作参考记录 | 行为变化，需写 CHANGELOG |
| 分片在 split 之前 | 先 split 再分片 | 分片内容可能变化 |
| 产物路径不含 delay/init | 含 `dly-<δ>` 与 `init-<i>` | 修掉跨维度覆盖 |
| 控制只能自动补 | `--controls auto/matrix/synthetic/both/none` | `none` 时显式 N/A，不再"看起来有控制" |

**默认路径回归**：`run --rollback --dry-run` 必须仍选中 442 条 B case；`--split lite` 仍为 10 条 B。

---

## 10. 实现清单

| 文件 | 改动 |
|---|---|
| `src/libero_rollback/families.py` ✚ | suite/level/window/target 解析，族判定，内部数据解析 |
| `src/libero_rollback/matrices.py` ✎ | 增加 `load_d_native`、`load_c`（Phase 2）、`load_d_compose`（provisional）、`load_a` |
| `src/libero_rollback/cli.py` ✎ | 删旧参数；新增六个能力开关 + `--controls`；`--dry-run` 写 plan；支持混族批次 |
| `src/libero_rollback/runner.py` ✎ | 每个 case 自带 family/trigger/budget/gates；`run_case` 接 `TriggerPolicy`；多组合循环（模型只加载一次） |
| `src/libero_rollback/runtime/triggers.py` ✚ | `AllDoneTrigger`、`WindowTrigger`（GT 事件 + legacy 映射 + 可复现性） |
| `src/libero_rollback/runtime/trace.py` ✚ | 独立 trace writer + 终点 GT 快照（C7） |
| `src/libero_rollback/report.py` ✎ | 按 `dimensions` 分组；`control_origin` 分列；N/A；deviation 附录 |
| `src/libero_rollback/metrics.py` ✎ | 分组聚合 + Wilson（已部分具备）；配对检验放离线脚本 |
| `tests/test_families.py` ✚ · `tests/test_runner_windows.py` ✚ · `tests/test_cli_flags.py` ✚ | 解析/混族批次/控制模式/拒绝用例/默认 442 回归 |
| `docs/SPEC.md` §5 · `docs/protocol.md` §6 · `configs/protocol.yaml` | 同步六个开关、预算、窗口、控制口径 |

必须覆盖的拒绝用例：纯 A/C 带维度开关、`--rollback goal-compose --level L1:d03`（无该行）、
`--rollback goal --window early`（窗口只在 l10）、`--window early --success-delay 10`、
`--compose` 上的 `--target`、纯 B 传 `--controls synthetic`、纯 A/C 传 `--controls`、
C 未构建时的 `run`、空交集、`shard_index` 越界。

---

## 11. LIBERO-10：B 与 D 的分工

### 11.1 数据事实

| 维度 | B(l10) | D-native |
|---|---|---|
| case 数 | 197（10 个任务） | 189（9 个任务，无 t276） |
| 触发 | `--window all_done` + `--success-delay 10` | `--window early/mid/later` |
| level | C0 10 / L0 28 / L1 84 / L2 75 | C0 9 / L0 27 / L1 81 / L2 72 |
| 撤销目标 | `g/s1/s2/both/pre`（s1 60 条） | 恒为 `s1` |
| 预算 | 600 + 300 | 800 + 300 |
| 控制 | 每任务 1 条 C0（`all_done`） | 9 条 `all_done_control`（窗口内无 C0） |
| 命令 | `--rollback l10` | `--rollback l10 --window early,mid,later` |

**配对事实**：B 的 `l10 + target=s1` 子集正好 **60 条**，覆盖 D 的 9 个任务，层级构成
（L0 1 / L1 3 / L2 3，joint 无 L2）与 D 的**任一窗口**（60 条）逐格相同，case_id 可直接对齐：

```text
b-l10-t033-s1-l0      ↔ d-l10-t033-early-l0
b-l10-t033-s1-l1-d03  ↔ d-l10-t033-early-l1-d03
b-l10-t033-s1-l2-r30  ↔ d-l10-t033-mid-l2-r30
```

这是全数据集中唯一完全配对的 B↔D 对比（t276 只有 B）。

### 11.2 为什么分开跑

1. **问题不同**：B 测"全部完成后已达成状态能否保住"；D 测"还有 pending 目标时撤销一个已达成子目标的代价"。
2. **预算/门控不同**：600 vs 800，D 多三个门控 → 只能做配对差，不能比绝对率。
3. **控制结构不同**：B 有矩阵 C0；D 窗口内没有，必须补 synthetic（§6.4）。
4. **聚合键冲突**：两者 suite 都是 `l10`，混在一张表会把两种协议合并。

### 11.3 推荐表

| 表 | 内容 |
|---|---|
| B 主表 | 全 442，按 suite × level × target；l10 单列 |
| D 主表 | 189，按窗口 × level；三窗口分列不合并，窗口 <20% 记 `N/A` |
| 配对表 | B(l10,s1,δ=10) ↔ D(窗口)：60 对/窗口的 ΔRecovery（离线脚本做 exact McNemar） |
| 附录 | B 的 δ 敏感性（0/30/60）、预算对齐臂（`--max-steps 800`）、D 的 synthetic 控制 |

### 11.4 `--success-delay` 不能替代 `--window`

δ 再大，`s2` 也已在完成时变真，pending 恒为 0；`--window early` 时 `s2` 还没开始，D 才覆盖
"部分进展"。反过来，窗口也无须 δ：窗口本身就是撤销时机。两者不可互换。

### 11.5 D 的窗口对照缺口（数据债）

D 的 9 条 C0 全在 `all_done`。所以：

- **现在**：CLI 自动为每个窗口补 synthetic no-op（`-ctl-none`，`control_origin=synthetic`），报告分行；
- **长期**：数据 v2.1 给每个窗口加 1 条 C0（9×3=27 行），走 manifest/版本号；
- 不能用 `all_done_control` 近似窗口控制（时机不同）。

### 11.6 `trigger_criterion` 映射（实现硬要求）

| 窗口 | 矩阵旧标签 | 映射后的 GT 事件 |
|---|---|---|
| `early` | `s1 first true` | `enter_first_subgoal_completed` |
| `mid` | `s2 displacement > 5 cm` | `enter_next_subgoal_lift` |
| `later` | `distance to s2 goal < 8 cm` | `enter_next_subgoal_preplacement` |
| `all_done` | `no injection`（控制） | `all_done` |

trace 同时写 `trigger_criterion_raw` 与 `mapped_event`；5 cm / 8 cm 判据作废。

### 11.7 结论

1. B（`--rollback`）与 D（`--rollback l10 --window ...`）分开跑、分开出表；跨族用配对差。
2. l10 唯一合法配对：B(`target=s1`,δ=10) ↔ D(任一窗口)，60 对/窗口；`early` 是桥。
3. `--success-delay` 属于 B；`--window` 属于 D；不可互换。
4. `--level` 是统一扰动维；D 窗口的 no-op 对照自动补并标 `synthetic`。
5. 数据债：窗口 C0、旧 `trigger_criterion`、t276 无 D 对应、B/D 预算差 200 步。

---

## 附录 A · 速查

| 目的 | 命令 |
|---|---|
| B 全量 | `run --rollback --output runs/b` |
| B 只跑 l10 | `run --rollback l10 --output runs/b-l10` |
| 只看 L1-d03 | `--level L1:d03` |
| 延迟扫描 | `--success-delay 0,10,30` |
| D-native 三窗口 | `--rollback l10 --window early,mid,later` |
| C intact | `--compose` |
| D-compose | `--rollback goal-compose object-compose --level L0 --window early,mid,later` |
| 混批 B(l10) + D-compose | `--rollback goal-compose object-compose l10` |
| 只要矩阵控制 | `--controls matrix` |
| 不要自动控制 | `--controls none` |
| 只出计划 | 任意 `run` 加 `--dry-run` |
| 报告 | `report --run <output>` |

## 附录 B · 需要同步的文档

| 文档 | 需改内容 |
|---|---|
| `docs/SPEC.md` §5 | `delay_steps` 是运行期维度（矩阵列 10 为参考值）；`repair_window` CLI 优先 |
| `docs/protocol.md` §6/§8 | 六个开关；窗口/延迟边界；provisional 拒绝执行 |
| `configs/protocol.yaml` | `families` / 维度允许集；控制自动补的规则 |
| `README.md` §3.5/§6.2/§8.5 | B/D 分工；示例命令；δ 与 window 不可互换 |
| `dataset/README.md` §4 | 数据债 `D-C0-WINDOW`；C 未构建与 D-compose provisional |
| `docs/implementation-status.md` | 旧缺口处置与新实现状态 |
