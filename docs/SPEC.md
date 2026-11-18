# LIBERO-Rollback 数据与接口规范（SPEC）

> 版本：v2.0-draft ｜ 日期：2026-11-18 ｜ 上位文档：[README.md](../README.md)
> 本文件是**数据契约与模块接口的唯一权威来源**；README 与本文件冲突时以本文件为准。
> 状态标记：✅ 已完成并验证；🟡 迁移中；⬜ 未开始。

---

## 0. 本阶段（Phase 1）范围

Phase 1 迁移**可验证的部分**：

| 套件 | 数据 | 说明 |
|---|---|---|
| A `single-intact` | ✅ 40 行（`dataset/matrices/a-matrix.csv`） | 由 B 的 40 个任务键 + 上游 LIBERO BDDL 生成 |
| B `completion-boundary-rollback` | ✅ 442 行（导入，`b-matrix.csv`） | 前序仓已定稿；本仓复制并加 provenance |
| D-native | ✅ 189 行（`d-native-matrix.csv`） | 从 `d-matrix.csv` 切出 native 子集 |
| D-compose | ⬜ 360 行（暂存占位，不提交执行） | 依赖 C 的 120 个 n=2 结构；C 尚未构建 |
| C `composition-intact` | ⬜ 0 行 | 依赖按 40-task pool 重新生成；前序仓 512 ordered 不能直接充当 C |

> **不做假数据**：`d-matrix.csv` 的 compose 行（`s0001`–`s0120`）目前没有绑定真实结构，只作为设计矩阵保存为 `dataset/matrices/d-compose-provisional.csv`，不进入执行 split，直到 C 构建完成。

---

## 1. 目录契约

```text
dataset/
├── matrices/
│   ├── a-matrix.csv                 # A 套件（40 行）
│   ├── b-matrix.csv                 # B 套件（442 行，导入）
│   ├── d-native-matrix.csv          # D-native（189 行，导入）
│   └── d-compose-provisional.csv    # D-compose 设计占位（360 行，不执行）
├── sources.yaml                     # 来源 + 上游 pin + 导入文件 sha256
├── manifest.yaml                    # 计数 + 逐文件 sha256 + split
├── lite.yaml                        # 冒烟子集（30 case）
└── README.md                        # 数据卡（draft）
```

- 所有 CSV：UTF-8（无 BOM）、LF、首行列名、逗号分隔；禁止绝对主机路径。
- `manifest.yaml` 由 `scripts/build_manifest.py` 生成，必须可通过 `--check` 复现。
- 大文件（LIBERO 资产、模型权重、视频）**不入库**。

---

## 2. 任务身份与 LIBERO 映射

### 2.1 上游资产 pin

- 仓库：`https://github.com/Lifelong-Robot-Learning/LIBERO`
- commit：`f78abd68ee283de9f9be3c8f7e2a9ad60246e95c`
- 要求 **clean worktree**；仅使用 `libero/libero/{bddl_files,init_files,assets}`。
- LIBERO 通过 `LIBERO_CONFIG_PATH/config.yaml` 定位资产（见 `scripts/bootstrap_libero.py`）；**禁止** `~/.libero`。

### 2.2 task key 与 suite 映射

```
task_key = (suite, task_idx)      suite ∈ {goal, object, spatial, l10}
LIBERO_SUITE_DIRS = {
  "goal": "libero_goal", "object": "libero_object",
  "spatial": "libero_spatial", "l10": "libero_10",
}
```

- `task_idx` 是**本仓稳定编号**（0–9），不是 LIBERO-plus 的全局整数下标。
- `bddl_name` 是 BDDL stem，例如 `libero_10/KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it`。
- A 套件的 40 个任务**完全由 B 的 40 个 task key 派生**（`suite, task_idx, bddl_name` 一一对应），保证 A↔B 配对。
- D-native 的 `task_idx` 使用与 B 的 `l10` 相同的编号映射。

### 2.3 init 引用

`init_source` 为相对 `LIBERO_HOME` 的路径：
`libero/libero/init_files/<suite_dir>/<bddl_name>.pruned_init`。

---

## 3. 矩阵 CSV 契约

### 3.1 通用规则

1. `case_id` 全库唯一、发布后不可变；格式见 §4。
2. 一行 = 一个可执行的 case；列顺序可读但不作为契约（按列名解析）。
3. 布尔列只允许 `true` / `false`（小写）。
4. 所有引用（bddl / init）为**相对 LIBERO_HOME** 的路径。
5. `expected_relation_after`：`C0` 必须为 `true`；`L0/L1/L2` 必须为 `false`。

### 3.2 A 矩阵（`a-matrix.csv`，40 行）

| 列 | 类型 | 说明 |
|---|---|---|
| `case_id` | str | `a-<suite>-t<idx:03d>` |
| `suite` | enum | `goal/object/spatial/l10` |
| `task_idx` | int | 0–9 |
| `bddl_name` | str | BDDL stem |
| `instruction` | str | 从 BDDL `:language` 提取，逐字保存 |
| `init_source` | str | 相对 `LIBERO_HOME` 的 init 路径 |
| `n_goals` | int | BDDL `:goal` 的原子数（`And` 展开后） |
| `semantics` | str | 固定 `intact` |
| `max_steps` | int | 600（主表 1 init；上界协议 10 init 另行报告） |

### 3.3 B 矩阵（`b-matrix.csv`，442 行，导入 + 冻结）

列（17）：`case_id,suite,task_idx,bddl_name,instruction,target,revoked_objects,revoked_predicates,family,level,param,semantics,trigger,delay_steps,repair_window,expected_relation_after,n_targets`。

- 语义定义见 README §3.4–3.5 与 `libero_rollback.matrices`；
- 校验由 `libero_rollback.matrices.load_b_matrix()` 强制（level/param 组合、C0 规则、谓词覆盖、每任务唯一 C0、同任务指令一致）。

### 3.4 D-native 矩阵（`d-native-matrix.csv`，189 行，导入 + 冻结）

列（19）：`case_id,sub,suite,task_idx,struct_id,instruction,window,trigger_criterion,target,revoked_predicate,revoked_object,family,level,param,semantics,max_steps,repair_window,expected_relation_after,s2_must_stay_true`。

- `sub == "native"`，`suite == "l10"`；`window ∈ {early,mid,later,all_done_control}`；
- `target == "s1"`（`all_done_control` 除外，无撤销）；
- `trigger_criterion` 是事件名（`enter_first_subgoal_completed` / `enter_next_subgoal_lift` / `enter_next_subgoal_preplacement` / `no injection`）；
- `max_steps=800`（native），`repair_window=300`；
- D 的触发检测**只使用 GT 谓词与仿真状态**，不得依赖任何外部 runtime profile。

### 3.5 C 矩阵（⬜ 未提交）

目标：120 个 n=2 结构 + 40 个 n=3 结构。列契约在 C 构建时冻结；`case_id = c-<struct_id>`，`struct_id` 形如 `sNNNN`。
D-compose 的 360 行复用同一 `struct_id`（`d-compose-<struct_id>-<window>-l0`）。

---

## 4. case_id 命名

```
a-<suite>-t<idx:03d>
b-<suite>-t<idx:03d>-<target>-<level>[-<param>]      # b-<suite>-t<idx>-c0 为 no-op
d-l10-t<idx:03d>-<window>-<level>[-<param>]          # d-l10-t<idx>-c0 为 no-op
d-compose-<struct_id>-<window>-l0
c-<struct_id>
```

`<target> ∈ {g, s1, s2, both, pre, c0}`；`<level> ∈ {C0, L0, L1, L2}`；`<param> ∈ {d03, d06, d10, r30, r60, r90}`；`<window> ∈ {early, mid, later, all_done_control}`。

---

## 5. 协议常量（主表）

| 项 | 值 |
|---|---|
| B trigger | `all_done`（全部 native goal 为真）+ `delay_steps=10` |
| B budget | 600 活跃步 + 300 `repair_window`（注入后追加；逐 episode 记 `repair_budget_steps`） |
| D-native budget | 800 + 300 |
| A / C budget | 600 |
| `replan_steps` | 10 |
| `init_row` | 0（主表）；0–4（variance 子集） |
| `seed` | 0（主表） |
| `camera` / `settle` | 256 / 10 |
| 视频 | 20 fps，H.264/yuv420p/faststart，注入卡 1 s |
| 成功判定 | 环境 `check_success()` + GT 谓词 trace；**禁止 VLM 判官** |

---

## 6. 判定与指标

### 6.1 判定器 verdicts（`libero_rollback.evidence.classify_result`）

`valid_recovered` / `valid_not_recovered` / `valid_control` / `valid_relation_preserving_probe` / `valid_external_restoration` / `injection_invalid` / `trigger_not_reached` / `truth_unverified` / `protocol_incomplete` / `incomplete`。

### 6.2 分母口径

```
Recovery  = (valid_recovered) / (valid_recovered + valid_not_recovered)
control_rate = valid_control / (number of C0 cases attempted)
trigger_rate = triggered / attempted
```

- `C0` 与无效注入、外部复原、协议不完整一律**排除**出 Recovery 分母；
- 不可触发 = `N/A`（不是 0%）；
- 每个数字必须带 init 数、预算、CI。

### 6.3 指标（`libero_rollback.metrics`）

`SR`、`Recovery`、`Restate Δ`、`EGC = Σₙ SR(n)`、`PP = P(≥1 子任务达成)`、`One-and-Done`、`Zero-Progress`、`Trigger rate`、`Notice latency`、`Retention = SR_case/SR_ref`、`Cost`。
统计：Wilson 95% CI、exact McNemar（配对）、按 structure 的 cluster bootstrap。

---

## 7. 证书与验收

- 8 张证书 C1–C8（README §5.1）。Phase 1 已实现/可验证：C1（矩阵完整性）、C2（初始状态，冒烟）、C5（非退化）、C7（GT 记录格式）、C8（成本字段）；**C3/C4 需要脚本 oracle，Phase 2**。
- B 逐 case 验收与 D 逐 case 验收字段见 README §5.2。

---

## 8. `manifest.yaml` 契约

```yaml
schema_version: 2
dataset_version: "2.0.0.dev0"
libero:
  repo: https://github.com/Lifelong-Robot-Learning/LIBERO
  commit: f78abd68ee283de9f9be3c8f7e2a9ad60246e95c
counts:
  a: 40
  b: 442
  d_native: 189
  d_compose_provisional: 360
  c: 0
files:
  - path: dataset/matrices/a-matrix.csv
    sha256: <hex>
    rows: 40
splits:
  lite: [<case_id>, ...]        # 30 条，见 dataset/lite.yaml
  core: [a, b, d-native]
  variance: ...
provisional:
  - dataset/matrices/d-compose-provisional.csv
generated_by: scripts/build_manifest.py
```

## 9. `sources.yaml` 契约

记录每个导入文件的来源仓、相对路径、sha256、导入日期与对应设计文档；以及上游 LIBERO pin。示例：

```yaml
imports:
  - target: dataset/matrices/b-matrix.csv
    source_repo: libero-compose
    source_path: dataset/case-matrices/b-matrix.csv
    sha256: <hex>
    note: "442 rows frozen 2026-11-18"
```

---

## 10. lite split

30 条，确定性选取规则（脚本生成，见 `dataset/lite.yaml`）：

- A：10 条（4 suite 各 2–3 条）
- B：10 条（`C0/L0/L1/L2` 四档覆盖，含 goal/object/spatial/l10）
- D-native：10 条（`early/mid/later` 三窗口 + `all_done_control`）
- 选择键按 `(suite, task_idx, level/window)` 排序后固定抽取，可复现。

---

## 11. 包结构与接口

```
src/libero_rollback/
├── __init__.py
├── cli.py             # libero-rollback {list,validate,run,report,leaderboard}
├── matrices.py        # 矩阵加载/校验（纯 stdlib）
├── schema.py          # JSON Schema + metadata 校验
├── validation.py      # dataset 级静态校验（manifest/覆盖/路径卫生）
├── evidence.py        # episode verdict 分类器
├── metrics.py         # SR/Recovery/EGC/CI
├── report.py          # 自包含 HTML + aggregate.json
├── runner.py          # B/D episode 循环 + 批跑 + 聚合
├── runtime/
│   ├── env.py         # LIBERO config/env 创建 + init row 读取
│   ├── perturbation.py# C0/L0/L1/L2 注入 + 几何 + restorable oracle
│   ├── triggers.py    # all_done + D 窗口（GT 谓词）
│   ├── trace.py       # trace.jsonl / 终点 GT 快照
│   └── video.py       # 视频录制 + 注入卡
└── policies/
    ├── __init__.py    # PolicyAdapter 协议 + load_policy()
    ├── pi05.py
    ├── smolvla.py
    └── openvla_oft.py
```

关键接口（必须保持稳定）：

```python
# matrices.py
load_b_matrix(path) -> BMatrix
BMatrix.cases: list[BCase]; .by_task(); .select(suites=, case_ids=, max_tasks=); .summary()
BCase: case_id, suite, task_idx, bddl_name, instruction, target, revoked_objects,
       revoked_predicates, family, level, param, semantics, trigger, delay_steps,
       repair_window, expected_relation_after, n_targets;
       .is_control; .level_spec; .bddl_path(libero_home); .init_path(libero_home)
SUITE_DIRS; LEVEL_SPECS; parse_predicate(text)

# evidence.py
classify_result(case: Mapping, episode: Mapping | None) -> str

# metrics.py
wilson_ci(k, n) -> tuple[float, float]
recovery_rate(episodes) -> Rate( numerator, denominator, value, ci )
summarize(episodes) -> dict

# runner.py
run_matrix(*, matrix, cases, output, model, checkpoint=None, ...) -> dict
```

---

## 12. 依赖与独立性约束（CI 强制）

- 静态层（`matrices/schema/validation/evidence/metrics/report`）只允许 stdlib + PyYAML + jsonschema；**不得 import numpy/torch/libero**。
- 运行层（`runtime/*`、`policies/*`、`runner`）在独立环境中安装 LIBERO/MuJoCo/模型框架。
- **禁止** import 或路径引用 `libero_rollback`（前序数据仓）、`libero_compose`、`libero_runtime`；禁止 `runs/`、overlay、runtime profile。
- `dataset/` 内不得出现绝对主机路径；CI 用 grep 与 `validation.py` 双重检查。

---

## 13. Phase 1 未完成项（进入 `docs/implementation-status.md`）

1. C 套件（160 结构）与 D-compose（360）数据构建（需要 40-task pool 的结构生成器 + 覆盖证明）。
2. D 轴 runner（窗口触发 + D-native 189 执行）。
3. 脚本 oracle（C3 可解性 / C4 可复原性）。
4. 报告中的视频证据与决策卡（简化版报告先落地）。
5. leaderboard 服务端校验（本地 `leaderboard validate` 先落地）。
6. `pip` / HF dataset / datasheet 发布。
