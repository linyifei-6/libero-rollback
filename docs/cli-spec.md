# 评测 CLI 规范（CLI Test Specification）

> 版本：v1-draft ｜ 日期：2026-11-18 ｜ 对象：`libero-rollback 2.0.0.dev0`（Phase 1）
> 上位文档：[docs/SPEC.md](SPEC.md)（数据契约唯一权威）· [docs/protocol.md](protocol.md)（评测协议）· [README.md](../README.md) §3/§6
> 本文分三部分：**Part I** 现状 CLI 的实测参考（逐参数）；**Part II** 面向本测试集的 v3 CLI 体系（`success-delay` / `rollback` 维度开关 + B/D 分离）；**Part III** LIBERO-10 上 B 与 D 如何分开的论证与推荐方案。
> 标记约定：✅ 已实现且本文实测过；🟡 实现存在但未端到端验证；⬜ 未实现（Phase 2）；💡 本文提出的设计建议。

---

## 0. 术语与阅读方式

| 术语 | 含义（本文口径） |
|---|---|
| **task key** | `(suite, task_idx)`，`suite ∈ {goal, object, spatial, l10}`；B/D 共用同一套 LIBERO 全局下标 |
| **case** | 矩阵一行 = 一次可执行 episode；`case_id` 发布后不可变（SPEC §4） |
| **trigger / 触发** | 注入撤销扰动的时机与判据（B：`all_done` + delay；D：`early/mid/later` 事件） |
| **injection / 注入** | 直接写 MuJoCo `qpos/qvel` 后 `mj_forward`，不是"发指令" |
| **repair window** | 注入**之后追加**的预算，不挤占 `max_steps`（SPEC §5） |
| **arm / 臂** | 一组协议取值的组合（例如 `rollback=L1:d03 × success-delay=10`）；一个 arm 是一个可独立聚合的分母单位 |
| **axis / 维度** | 可被 CLI 切换、且必须在产物里被记录的协议因子（`success-delay`、`rollback`、`window`、`target`、`init-row`、`seed`） |
| **evidence / 证据** | 只有真实 episode 的 `summary.json` / `episodes.jsonl` 是证据；`plan.json`、dry-run、静态校验**不是**（protocol §5） |

阅读顺序建议：先 Part I §4 与 §8（现状能做什么、不能做什么），再 Part II，最后 Part III（l10 的 B/D 决策）。

---

# Part I · 现状 CLI（实测）

## 1. 入口与命令树

### 1.1 两个入口（行为并不相同）

| 入口 | 安装方式 | 定位 | 关键差异 |
|---|---|---|---|
| `libero-rollback` | `pyproject.toml` `[project.scripts]`（[`pyproject.toml:34`](../pyproject.toml#L34)）→ `libero_rollback.cli:main` | 正式 CLI | `--policy` 默认 **`none`**；支持 `--split/--dataset`、`--repair-window`、`list/validate/report/leaderboard` |
| `python scripts/run_b_matrix.py` | 仓库内薄封装（[`scripts/run_b_matrix.py`](../scripts/run_b_matrix.py)） | B 套件快捷入口 | `--policy` 默认 **`pi05`**；**没有** `--split/--dataset`、`--repair-window`、`--model` 别名；其余参数同名同义 |

两者都只加载 **B 矩阵**（`matrices.load_b_matrix`），D-native 的 19 列 CSV 目前没有 loader（见 §8 G1）。

```text
libero-rollback
├── list        --matrix PATH [--suite ...] [--json]
├── validate    [--dataset DIR] [--json]
├── run         --output DIR [数据选择] [策略] [预算/触发] [渲染] [运行时] [断点] [--dry-run]
├── report      --run DIR [--out DIR]
└── leaderboard
    └── validate  --run DIR
```

实现锚点：[`cli.py:359`](../src/libero_rollback/cli.py#L359) `build_parser()`；子命令函数 `cmd_list/cmd_validate/cmd_run/cmd_report/cmd_leaderboard`。

### 1.2 退出码（[`cli.py:34-36`](../src/libero_rollback/cli.py#L34-L36)）

| code | 含义 | 触发点 |
|---:|---|---|
| `0` | 成功 | 正常返回；`--version` 也是 0 |
| `1` | 校验/评测失败 | `validate` 报告不 ok；`leaderboard validate` 有问题；`SystemExit(str)`（`--split lite` 缺 `lite.yaml`） |
| `2` | 用法或环境错误 | argparse 用法错误；矩阵缺失；`--checkpoint` 不存在；空选择；`shard_index` 越界；**任何未捕获异常**（除非设置 `LIBERO_ROLLBACK_DEBUG=1`） |

> ⚠️ 未捕获异常统一映射为 `2` 且只打印 `error: <Type>: <msg>`，因此参数写错与数据集缺陷在退出码上不可区分。v3 建议拆分（Part II §17）。

### 1.3 不联网

CLI 不监听端口、不启动服务、不做网络请求；所有产物是文件（protocol §1）。模型推理在**当前解释器**内完成（不是子进程），因此"每模型一个 venv"靠调用者选择解释器实现。

---

## 2. `list` —— 矩阵盘点（纯静态）

| 参数 | 类型 | 默认 | 语义 |
|---|---|---|---|
| `--matrix` | Path | 无（**必填**） | B 矩阵 CSV；省略时抛 `TypeError` → 退出码 2（实测） |
| `--suite` | `str...` | 无 | 只明细打印这些 suite 的 case（`goal/object/spatial/l10`） |
| `--json` | flag | off | 输出 `{cases, tasks, by_suite, by_level, source}` |

输出示例（实测）：`cases=442 tasks=40`，`by_suite={goal:85, l10:197, object:80, spatial:80}`，`by_level={C0:40, L0:60, L1:180, L2:162}`。
实现：[`cli.py:111`](../src/libero_rollback/cli.py#L111)；矩阵摘要 [`matrices.py:243`](../src/libero_rollback/matrices.py#L243)。

---

## 3. `validate` —— 数据集静态校验

| 参数 | 类型 | 默认 | 语义 |
|---|---|---|---|
| `--dataset` | Path | `dataset`（相对 **当前工作目录**） | 数据集根目录 |
| `--json` | flag | off | 输出结构化 `ValidationReport.to_dict()` |

检查内容（[`validation.py:629`](../src/libero_rollback/validation.py#L629)）：`manifest.yaml`（版本键、LIBERO pin、计数、4 个矩阵的 path/sha256/行数、splits、provisional）、`matrices/*.csv`（UTF-8 无 BOM、`case_id` 唯一且符合 SPEC §4 命名、行数与 manifest 一致）、`lite.yaml`（30 条、唯一、全部可解析、与 manifest 一致）、路径卫生（无绝对主机路径、无 CRLF/BOM）。
实测：`PASS`、`4 CSV / 1031 unique case_id / lite 30 / 0 error 0 warning`。**该命令永不启动仿真**，是 CI 的 S0 门禁。

---

## 4. `run` —— 主命令（全参数）

### 4.1 参数全表

下表 32 个参数全部来自 [`cli.py:155-190`](../src/libero_rollback/cli.py#L155-L190)，"落盘"指写入哪个产物。

#### A. 数据选择

| 参数 | 类型 | 默认 | 语义 | 落盘 |
|---|---|---|---|---|
| `--matrix` | Path | 见 §4.2 P1 | B 矩阵 CSV | `run-manifest.defaults.matrix`、`matrix.json.source` |
| `--output` | Path | **必填** | run 目录；自动 `mkdir` 并解析为绝对路径 | 全部产物 |
| `--split` | `lite\|core\|full` | `core` | 用 `dataset/lite.yaml` 过滤 case；`core/full` **不过滤**（当前只有 B 可执行） | 无 |
| `--dataset` | Path | `<repo>/dataset` | `--split lite` 的 `lite.yaml` 根目录 | 无 |
| `--suites` | `str...` | 无 | 按矩阵 `suite` 过滤（不是 B/D 选择！） | 无 |
| `--case-ids` | `str...` | 无 | 显式 case id 过滤 | 无 |
| `--max-tasks` | int | `0` | 取**全矩阵**前 N 个 task key 的所有 case（见 §4.2 P4 陷阱） | `plan.json` |
| `--max-cases` | int | `0` | 在 `--max-tasks` 之后截断 case 数 | `plan.json` |
| `--shard-index` | int | `0` | 分片序号，`0 ≤ i < count` | `plan.json.shard` |
| `--shard-count` | int | `1` | 分片数；按 `index % count` 确定性切分 | `plan.json.shard` |

#### B. 策略 / 模型

| 参数 | 类型 | 默认 | 语义 | 落盘 |
|---|---|---|---|---|
| `--model`（别名 `--policy`） | `pi05\|smolvla\|openvla_oft\|none` | `none` | 每 run 只加载一个 adapter；`none` = 零动作、不加载模型 | `defaults.policy`、每 episode `summary.policy.metadata` |
| `--checkpoint` | str | 见 §4.2 P2 | 权重路径 | `defaults.checkpoint` |
| `--config-name` | str | `pi05_libero` | OpenPI 配置名 | `defaults.config_name` |
| `--unnorm-key` | str | 无 | OpenVLA-OFT 归一化键（默认按 suite 查 `configs/models.yaml`） | `defaults`（无则该键不写） |
| `--workspace` | str | 无 | OpenVLA-OFT workspace（或 `OPENVLA_OFT_WORKSPACE`） | — |

#### C. 预算与触发（核心）

| 参数 | 类型 | 默认 | 语义 | 落盘 |
|---|---|---|---|---|
| `--max-steps` | int | `600` | **注入前**活跃预算。注入成功后总预算被改写为 `injection_step + repair_window` | `summary.max_steps`、`total_budget_steps` |
| `--delay-steps` | int | `10` | `first_all_done` 之后第 δ 步尝试注入；**CLI 覆盖矩阵列**（矩阵列仍为 10） | `summary.setup.delay_steps`（config 值），`plan.cases[].delay_steps`（**矩阵值**，见 §4.2 P5） |
| `--replan` | int | `10` | 每次重规划的 action 数（chunk 截断长度） | `defaults.replan` |
| `--max-trigger-wait` | int | `60` | 到达 delay 后若"目标全真 ∧ 被撤销关系全真"仍不成立，最多再等 N 步；超时则跳过触发 | `summary.injection_wait_steps` / `trigger_skipped_reason` |
| `--repair-window` | int | `300` | 注入后的追加预算；**B 矩阵每行都是 300 → CLI 实际无效**（见 §4.2 P6） | `summary.setup.repair_window`（case 值） |
| `--camera` | int | `256` | 渲染分辨率（宽=高） | `defaults.camera` |
| `--settle-steps` | int | `10` | `set_init_state` 后的零动作稳定步数 | `defaults.settle_steps` |
| `--init-row` | int | `0` | `.pruned_init` 的行号（主表 0；variance 0–4） | `summary.init_row`、`init_shape` |
| `--seed` | int | `0` | `env.seed` + 策略 `reset_episode` | `defaults.seed`、目录 `seed-<n>` |

#### D. 渲染 / 视频

| 参数 | 类型 | 默认 | 语义 |
|---|---|---|---|
| `--video` / `--no-video` | bool | `True` | 是否录制 `<case>/seed-N/video.mp4` |
| `--video-fps` | int | `20` | 帧率（注入卡固定 1 s） |

#### E. 运行时 / 路径

| 参数 | 类型 | 默认 | 语义 |
|---|---|---|---|
| `--libero-home` | str | `LIBERO_HOME` | 上游 LIBERO checkout；两处都没有 → 退出码 2（[`env.py:52`](../src/libero_rollback/runtime/env.py#L52)） |
| `--libero-python` | str | `LIBERO_INIT_PYTHON` | 仅用于**读取 `.pruned_init`** 的兜底解释器（当前解释器不能 import torch 时走子进程） |

#### F. 断点 / 分片 / 调试

| 参数 | 类型 | 默认 | 语义 |
|---|---|---|---|
| `--resume` / `--no-resume` | bool | `True` | 跳过 `episodes.jsonl.status == "ok"` **且** `summary.json` 存在的 case |
| `--retry-errors` | flag | off | 连同 `status == "error"` 的 case 一起重跑 |
| `--retry-invalid` | flag | off | 重跑 `status == "ok"` 但 `case_valid == false` 的 case |
| `--dry-run` | flag | off | 只写 `plan.json`；不启仿真、不加载模型、不读 init |

全局：`--version`（`2.0.0.dev0`）。

### 4.2 参数交互与优先级（8 条，均为实测/代码事实）

**P1 `--matrix` 解析顺序**（[`cli.py:50`](../src/libero_rollback/cli.py#L50)）：`LIBERO_ROLLBACK_MATRIX` → `<cwd>/dataset/matrices/b-matrix.csv` → `<repo>/dataset/matrices/b-matrix.csv` → 否则把第一个候选路径报"not found"（退出码 2）。

**P2 `--checkpoint` 解析顺序**（[`runner.py:224`](../src/libero_rollback/runner.py#L224)）：CLI → `PI05_CHECKPOINT` / `SMOLVLA_CHECKPOINT` / `OPENVLA_OFT_CHECKPOINT` → pi05 的 `~/.cache/openpi/.../pi05_libero` → 否则要求 `--checkpoint`；路径不存在 → `FileNotFoundError` → 退出码 2。`--model none` 不需要 checkpoint。

**P3 case 选择流水线（顺序即语义）**

```text
load_b_matrix
  → suites ∩ case_ids 过滤（matrices.select）
  → max_tasks（全矩阵前 N 个 task key；在 suites 过滤**之后**求交）
  → max_cases 截断
  → shard：index % count 切分        ← 此时还没做 --split
  → --split lite：与 lite.yaml 求交   ← shard 之后
  → 空选择 → 退出码 2
```

实测：`--shard-count 2 --split lite` 两个分片各 5 条（并集 = 10），但分片内容不均衡、且与"先 split 再分片"不同。**v3 修正：split 在 shard 之前**（Part II §11.3）。

**P4 `--max-tasks` 陷阱**：它取的是**全矩阵**前 N 个 task，不是当前 suite 子集的前 N 个。实测 `--suites l10 --max-tasks 1` → 选中 `goal/t000` 后与 l10 求交为空 → `error: the case selection is empty`（退出码 2）。

**P5 `--delay-steps` 覆盖生效但产物不一致**：runner 用 `config.delay_steps` 判定注入时机（[`runner.py:510`](../src/libero_rollback/runner.py#L510)），但 `plan.json` 的 `cases[].delay_steps` 仍打印矩阵列 `10`，`defaults.delay_steps` 打印覆盖值。实测 `--delay-steps 0`：`defaults=0`、`cases[0].delay_steps=10`。**两条真值来源并存**，违反"每个数字可追溯"。

**P6 `--repair-window` 对 B 无效**：`repair_window = case.repair_window if case.repair_window else config.repair_window`（[`runner.py:346`](../src/libero_rollback/runner.py#L346)）；B 矩阵 442 行全部为 `300`，所以 CLI 永远被忽略。实测 `--repair-window 5`：`defaults=5`、`cases[0].repair_window=300`。注意它与 P5 的优先级**方向相反**（delay：CLI 赢；repair：矩阵赢）。

**P7 触发判定是"延迟 + 等门控"两段式**（[`runner.py:510-526`](../src/libero_rollback/runner.py#L510-L526)）：`steps - first_all_done ≥ delay` 后，必须 `all(goal_truth) and all(revoked_truth)` 才注入；否则每个不满足的步递增 `injection_wait_steps`，达到 `max_trigger_wait` 即 `break`，摘要写 `trigger_skipped_reason`、`trigger_reached=false`、`case_valid=false`、`termination=trigger_not_reached`。

**P8 预算记账**：注入前 `total_budget = max_steps`；注入后 `total_budget = injection_step + repair_window`；env horizon = `max_steps + repair_window + 100`（[`runner.py:415`](../src/libero_rollback/runner.py#L415)）。摘要逐 episode 记录 `repair_budget_steps` 与 `repair_steps_used`，满足 SPEC §5。

### 4.3 一次 `run` 的执行语义

```text
for case in selected:                        # 模型只加载一次，跨 case 复用
    env.reset(); env.set_init_state(init_row)
    settle_steps × 零动作                     # 失败即 error（init 不能已被解）
    resolve goal_atoms = problem.parsed_problem["goal_state"]
    injector = BInjector(env, case, goal_atoms)
    loop steps < total_budget:
        action ← 策略 chunk（截断到 replan）或零动作
        obs ← env.step(action); steps += 1
        if all(goal_truth) 且 first_all_done 为空: 记 first_all_done
        if 未注入 且 steps-first_all_done ≥ delay 且 门控成立: 注入 → 清 queue → 重建 obs
        if 已注入: 记录 post_truths / recovered / notice_latency / eef 距离
        if steps % 5 == 0: 写 trace "step"
    收尾: final_goal_truth / final_revoked_truth / case_valid / video 元数据 → summary.json
聚合: run-summary.json + report.md（Recovery / control / trigger）
```

- `case_valid` 的构成见 [`runner.py:690-729`](../src/libero_rollback/runner.py#L690-L729)：`completed_relation_true_before_intervention` ∧ `all_revoked_false_after_intervention` ∧ `no_object_penetration` ∧ `zero_velocity_after_intervention` ∧（`target != "pre"` 或 `goal_preserved_after_pre`）；`C0` 走另一支（关系仍真 ∧ 最终目标真）。
- 聚合口径（[`runner.py:856`](../src/libero_rollback/runner.py#L856)）：`recoverable = valid ∧ level != C0`，`recovery_rate = recovered/recoverable_valid`，`control_rate = control_ok/controls`；`C0` 的 `recovery` 置 `None`。
- 续跑：`episodes.jsonl` 追加写；跳过条件 = `case_id ∈ done_ids` **且** 磁盘上 `summary.json` 存在。

---

## 5. `report` 与 `leaderboard`

| 命令 | 参数 | 行为 | 产物 |
|---|---|---|---|
| `report` | `--run DIR`（必填）、`--out DIR`（默认 `<run>/report`） | 读 `episodes.jsonl`、`run-manifest.json`、`run-summary.json`、`matrix.json`，算 Wilson 95% CI | `aggregate.json`、`SUMMARY.md`、自包含 `index.html` |
| `leaderboard validate` | `--run DIR`（必填） | 检查 episode 非空、`case_id` 唯一且非空、verdict 可判定、`run-manifest.json` 存在 | 终端 PASS/FAIL（退出码 0/1） |

`aggregate.json` 顶层键（[`report.py:179`](../src/libero_rollback/report.py#L179)）：`run{dir,mode,matrix,policy,checkpoint,config_name,init_row,seed,max_steps,delay_steps,repair_window,video}`、`matrix`、`episodes`、`recovery`、`control`、`trigger`、`success`、`by_verdict`、`by_suite`、`by_level`、`cases[]`。
`mode = "dry-run"` 当且仅当存在 `plan.json` 且无 episode —— 这是"plan 不是证据"在报告层的体现。

---

## 6. 环境变量

| 变量 | 使用者 | 作用 |
|---|---|---|
| `LIBERO_HOME` | runner（`--libero-home` 的兜底） | 上游 checkout 根；缺失 → 退出码 2 |
| `LIBERO_CONFIG_PATH` | **由 runner 写入** | 每 run 写 `<output>/libero_config/config.yaml`，禁止 `~/.libero` |
| `MUJOCO_GL` | runner | 默认 `osmesa`（`setdefault`，已设置则不覆盖） |
| `LIBERO_INIT_PYTHON` | `--libero-python` 兜底 | 读 `.pruned_init` 的备用解释器 |
| `PI05_CHECKPOINT` / `SMOLVLA_CHECKPOINT` / `OPENVLA_OFT_CHECKPOINT` | checkpoint 解析 | 权重路径 |
| `OPENVLA_OFT_WORKSPACE` | OpenVLA-OFT adapter | workspace 目录 |
| `LIBERO_ROLLBACK_MATRIX` | `--matrix` 兜底 | 默认矩阵路径 |
| `LIBERO_ROLLBACK_DEBUG` | `main()` | 非空则异常不被吞掉（便于栈回溯） |

`configs/models.yaml` 里的 `PI05_PYTHON` 等是"每模型独立解释器"的约定名，**runner 不使用**（不做子进程推理）。

---

## 7. 产物与证据等级

```text
<output>/
├── run-manifest.json   # defaults + argv + 环境摘要（覆盖式写入）
├── matrix.json         # 矩阵摘要
├── plan.json           # dry-run 计划 —— 证据等级 0
├── episodes.jsonl      # 一行一个 case summary（追加）
├── run-summary.json    # Recovery/control/trigger + defaults
├── report.md
├── libero_config/config.yaml
└── <suite>/<case_id>/seed-<seed>/
    ├── summary.json    # 唯一权威的 episode 证据（失败也写）
    ├── trace.jsonl     # episode_start/all_done/injection/step/episode_end
    └── video.mp4
```

| 产物 | 证据等级 | 说明 |
|---|---|---|
| `summary.json` / `episodes.jsonl` | **评测证据** | 只有真实 episode 产生 |
| `plan.json`、dry-run 输出、`validate` 报告 | 非证据 | 不得进表（protocol §5、§11） |
| `video.mp4` | 辅助证据 | 当前 `report.py` 只做引用/嵌入，不做判分 |

**⚠️ 路径不含 `init_row`、`delay`、`arm`**：`episode_directory = <output>/<suite>/<case_id>/seed-<seed>/`（[`runner.py:203`](../src/libero_rollback/runner.py#L203)）。因此同一 case 在不同 init 或不同 delay 下重跑会**互相覆盖** `summary.json`/`video.mp4`。这是 v3 必须引入 arm 目录的直接原因（Part II §19）。

---

## 8. 现状缺口（v3 的动机）

| ID | 缺口 | 证据 | 影响 |
|---|---|---|---|
| **G1** | 只有 B 矩阵 loader；D-native 19 列 CSV 无法加载 | `matrices.py` 仅 `load_b_matrix`；[`implementation-status.md`](implementation-status.md) ISSUE-4 | D 完全不可跑/不可 plan |
| **G2** | delay 硬编码语义：矩阵校验强制 `delay_steps == 10`（[`matrices.py:274`](../src/libero_rollback/matrices.py#L274)），CLI 覆盖却不入产物 | 实测 P5；§4.2 | 无法把"成功后多久撤销"当实验因子 |
| **G3** | 无 rollback 维度选择：只能按 suite/case-id 选，不能"只跑 L1:d03" | `BMatrix.select` 只有 suites/case_ids/max_tasks | 无法做扰动形态×参数的扫描 |
| **G4** | `--suites` 名字有歧义：它选的是 LIBERO suite（goal/object/spatial/l10），不是 B/D | [`cli.py:167`](../src/libero_rollback/cli.py#L167) | 用户自然想用它选 B/D，会误用 |
| **G5** | 无 arm/sweep 概念；`run-manifest.json` 每次覆盖，resume 不校验配置指纹 | `write_json(output/"run-manifest.json")`；`_load_existing_episodes` 只看 case_id | 同一 output 混入不同 delay/level 的 episode，聚合静默出错 |
| **G6** | 产物路径不含 init/arm（§7） | `episode_directory` | 跨 init/arm 覆盖 |
| **G7** | `--split` 在 shard 之后过滤；`--max-tasks` 按全矩阵取 | 实测 P3/P4 | 分片不均衡、suite+max-tasks 组合易空选 |
| **G8** | `--repair-window` 对 B 无效且与 delay 优先级相反 | 实测 P6 | 参数看起来生效、实际不生效 |
| **G9** | `list` 的 `--matrix` 实际必填，缺省报 `TypeError` | 实测 `error: TypeError: ... NoneType` | 体验与退出码不准确 |
| **G10** | 聚合只按 `suite`/`level` 分组（`metrics.summarize`） | [`metrics.py:272`](../src/libero_rollback/metrics.py#L272) | 无法按 arm/target/window 出分母 |
| **G11** | 缺 exact McNemar 与 cluster bootstrap（文档承诺、代码没有） | `metrics.py` 只有 Wilson | B↔D 配对检验无法落地 |
| **G12** | 未实现 D 触发（`runtime/triggers.py` 不存在）、C7 终点 GT 快照独立化 | ISSUE-3/4 | D 主表不可发布 |

---

# Part II · 面向本测试集的 v3 CLI 体系

## 9. 设计不变量（不可协商）

1. **矩阵冻结**：CLI 可以**选择**矩阵行、**覆盖运行期协议参数**，但绝不修改 `dataset/matrices/*.csv`，也不新造矩阵里没有的 case（唯一的例外是显式标注的 synthetic control，见 §13.3）。
2. **一切因子进产物**：任何影响结果的取值都必须写进 `run-manifest`、`plan`、`sweep.json` 与每 episode 的 `summary.axes`；报告中的数字必须能追到 arm。
3. **arm 隔离**：不同 arm 的 episode 不共享目录、不共享 `episodes.jsonl`、不混进同一分母。
4. **plan 不是证据**：dry-run 只写计划；报告拒绝把 `plan.json` 当成绩。
5. **不伪造**：缺 D 触发、缺 C3/C4 oracle 的地方，CLI 必须**明确拒绝执行**，而不是用近似判据跑出数字（沿用 protocol §11 的硬约束）。

## 10. 命令树 v3

```text
libero-rollback
├── list        --test {b,d-native} [--matrix PATH] [--dataset-suites ...] [--json]
├── validate    [--dataset DIR] [--test all|b|d-native] [--require-manifest] [--json]
├── plan        …与 run 相同的选择/轴参数，必写 --output            # run --dry-run 的别名
├── run         --test {b,d-native} --output DIR [选择] [轴] [协议] [模型] [渲染] [断点]
├── report      --run DIR | --sweep DIR [--out DIR] [--group-by arm|axis|window|target|level|suite]
├── compare     --a DIR --b DIR --paired-by case-key|task-idx [--out FILE]
└── leaderboard validate --run DIR
```

职责划分：

| 命令 | 职责 | 何时用 |
|---|---|---|
| `list` / `validate` | 静态盘点与门禁 | CI、动手前 |
| `plan` | 展开轴 → arms → 选中 case → 预算估计 → 写 `plan.json` | 每次开跑之前（强制习惯） |
| `run` | 真实 episode；一个进程加载一次模型、顺序跑所有 arm | 评测 |
| `report` | 单 run 或 sweep 的聚合 + Wilson CI + N/A 处理 | 跑完 |
| `compare` | 两个 run/arm 的配对检验（McNemar） | B↔D、跨 delay、跨 level |

## 11. axis 模型

### 11.1 定义与语法

```text
--axis NAME=VALUES          # 可重复；同一 NAME 出现多次则并集
VALUES := VALUE ("," VALUE)*
```

便捷别名（等价于对应 axis，二选一）：

```text
--success-delay 0,10,30        ⇔  --axis success-delay=0,10,30
--rollback L0,L1:d03,L2:r30    ⇔  --axis rollback=L0,L1:d03,L2:r30
```

| axis | 适用 test | 值域 | 默认 | 是否进 arm_id |
|---|---|---|---|---|
| `rollback` | b, d-native | `matrix` \| `all` \| `C0` \| `none` \| `L0` \| `L1[:d03\|d06\|d10]` \| `L2[:r30\|r60\|r90]`，可逗号组合 | `matrix` | 是 |
| `success-delay` | **b only** | 非负整数步；`replan:k` = `k × replan` | `10`（参考协议） | 是 |
| `window` | d-native only | `matrix` \| `all` \| `early` \| `mid` \| `later` | `matrix` | 是 |
| `target` | b only | `matrix` \| `g` \| `s1` \| `s2` \| `both` \| `pre` | `matrix` | 是 |
| `init-row` | b, d-native | 整数 ≥ 0（主表 0；variance 0–4） | `0` | 是 |
| `seed` | b, d-native | 整数 ≥ 0 | `0` | 是 |

### 11.2 arm 展开规则

1. **treatment arms** = `rollback × success-delay × window × target × init-row × seed` 的笛卡尔积，再与矩阵行求交；**交集为空即 setup error**（退出码 2），并打印"该组合下可用的 `(level,param,target,family,count)` 诊断表"，不允许静默跳过。
2. **control arms** 单独生成，不与 treatment 混在一个 arm：对每个 `(test, success-delay, window)` 组合生成 **1 个控制臂**（B：矩阵 `C0` 行；D：见 §13.3），从而避免"每个 rollback 臂都重复跑同一批 C0"。
3. **顺序**：规范化顺序固定为 `test → rollback → success-delay → window → target → init-row → seed`，值内按"数值/枚举序"排序（与命令行书写顺序无关），保证同一组 axis 永远生成同一组 arm_id。
4. **规模护栏**：`--max-arms N`（默认 64）超出即拒绝；`plan.json.totals.estimated_episodes` 必须打印。

### 11.3 case 选择流水线（修正 G7）

```text
load_matrix(test)
  → dataset_suites ∩ case_ids ∩ task_ids
  → --split {lite|core|full}（先用 lite.yaml 求交，lite 30 条含 a/b/d-native）
  → max_tasks（在**当前过滤结果**内按 task 顺序取前 N 个 task）
  → rollback/target/window 轴过滤
  → max_cases
  → shard（index % count）
  → 空 → error
```

与现状的差异：`split` 前置、`max_tasks` 只数当前子集。**默认行为**（不传 split/轴/shard）与现状等价：`--test b --split core` → 442 条。

## 12. `success-delay`（问题 1 的落地）

### 12.1 语义

δ 定义为：**`first_all_done_step` 之后第 δ 个环境步**尝试注入。判定仍是两段式（P7）：

```text
t - first_all_done ≥ δ  ∧  all(goal_truth)  ∧  all(revoked_truth)  →  注入
否则等待，累计 injection_wait_steps；达到 --trigger-wait 仍未满足 → trigger_skipped_reason
```

- δ=0：与 `all_done` 同一步注入；当前正被执行的 action chunk 尚未消费完，仍按 P7 清空 queue（记录 `queue_len_at_injection`）。
- δ 的单位是 **env step**，不是秒；1 步 = 1 次 `env.step()` = `replan` 的基本单位。
- **δ 对所有 level 一致**（含 C0）——这是把"延迟本身的影响"从"撤销的影响"里扣掉的前提。

### 12.2 参数与约束

| 项 | 规则 | 违反时 |
|---|---|---|
| 取值 | `δ ≥ 0`，整数；支持 `replan:k` | 退出码 2 |
| 上界 | `δ + trigger_wait < max_steps` | 退出码 2，并给出该 test 的合法上界（B：`δ ≤ 540`；D 不适用） |
| 与 replan 对齐 | 推荐 `δ % replan == 0`；不对齐允许但记为 `protocol_deviation: delay_not_replan_aligned` | 默认 `--delay-alignment warn`；`require` 时退出码 2；`off` 时不记录告警（仅内部调试） |
| 主表准入 | 带 `protocol_deviation` 的 arm 默认**不进主表**（报告放附录），除非 `report --include-deviations` | — |
| 适用 test | **仅 `b`**；`d-native` 传 `--success-delay` → 退出码 2，错误信息指向 `--axis window` | 退出码 2 |
| 与 C0 | 控制臂继承同一 δ；不允许单独给 C0 指定 δ | 退出码 2 |
| 参考值 | `10`（与 `replan=10` 对齐，等价现状） | — |

推荐扫描集：`{0, 10, 30, 60}`（10 = 参考臂；0 = 完成瞬间撤销；30/60 = 成功后继续执行/漂移）。

### 12.3 每个 episode 必须落盘的字段（修正 G2）

```jsonc
"axes": {"success_delay": 30, "rollback": "L1:d03", "target": "s1", "init_row": 0, "seed": 0},
"case_reference_delay": 10,          // 矩阵列值（冻结协议的参考值）
"delay_source": "axis",              // axis | matrix | protocol
"first_all_done_step": 212,
"injection_step": 242,
"injection_lag": 30,                 // = injection_step - first_all_done_step
"injection_gate": {"goal_all_true": true, "revoked_all_true": true, "waited": 0},
"delay_alignment": {"aligned_to_replan": true, "replan": 10, "deviation": null}
```

`plan.json` 必须同时给 `case_reference_delay` 与 `arm.axes.success_delay`，二者不得互相冒充。

### 12.4 预算与成本

注入后总预算 = `injection_step + repair_window`；注入前仍受 `max_steps` 约束。
`plan.json` 每 arm 给 `estimated_steps_per_case = p50(first_all_done) + δ + repair_window`（`first_all_done` 由 A 套件基线或历史 run 的 `first_all_done_step` 中位数估计；无历史则标 `unknown` 并给上限 `max_steps + repair_window`）。**不得**把估计值当实测成本写进表。

## 13. `rollback`（问题 2 的落地）

### 13.1 语法与语义

```text
--rollback matrix          # 默认：所选任务的全部非控制行（现状行为）
--rollback all             # 所选任务出现的所有 treatment level/param
--rollback C0              # 只用矩阵 no-op 控制行（做纯控制臂）
--rollback L0
--rollback L1              # 等价 L1:d03,L1:d06,L1:d10
--rollback L1:d03          # 单一参数
--rollback L2:r30,L2:r90
--rollback none            # 不注入，但同样触发、同样跑完 repair window（合成 no-op 对照）
```

规则：

- 轴只**选择矩阵行**，不改变几何；几何由 `LEVEL_SPECS`（[`matrices.py:65`](../src/libero_rollback/matrices.py#L65)）与 `runtime/perturbation.py` 定义，CLI 不提供"3cm 改成 5cm"这类覆盖。
- `L1`/`L2` 是**扰动形态**而非难度：报告中必须分形态报，禁止写成"L1 < L2 难度递增"（README §3.4）。
- `L2` 与 `family=joint` 互斥；若组合后为空，错误信息要列出"该 task 只支持 L0/L1"。
- `pre` 只存在于 `goal/t030`（矩阵校验强制，[`matrices.py:305`](../src/libero_rollback/matrices.py#L305)）。
- 同一 arm 内 `C0` 与 treatment 可以并存（`--rollback C0,L0`）；若 `--controls auto` 又会补 C0，则去重（按 case_id）。

### 13.2 组合示例

| 命令 | 生成的臂 | 用途 |
|---|---|---|
| `--rollback L0` | 1 个 treatment 臂 | 只看"恢复到初始位姿" |
| `--rollback L1` | 3 个臂（d03/d06/d10） | 外推距离曲线 |
| `--rollback L1:d03,L2:r30` | 2 个臂 | 两种形态的最小对比 |
| `--rollback matrix --success-delay 0,10,30` | 全部 level × 3 delay | 二维扫描 |
| `--rollback C0` | 1 个控制臂 | 单独复核"延迟+继续执行是否有害" |

### 13.3 `none` 与 synthetic control（D 窗口缺 C0 的解法）

`none` **不是**矩阵行：它复用所选 case 的触发时机与预算，但**不写 `qpos/qvel`**。命名规则是"去掉 level/param 后的 case_id + `-ctl-none`"，产物规则：

```jsonc
"case_id": "d-l10-t033-early-ctl-none",          // 加后缀，绝不冒充矩阵 case_id
"control_origin": "synthetic",
"planned_level": null, "rollback_applied": "none",
"validity": {"trigger_reached": true, "case_valid": true},
"recovery": null                                  // 控制不进 Recovery 分母
```

- 控制臂的生成方式：D 默认 `--controls matrix+synthetic`（含本项）；B 默认只有矩阵 `C0`，要用合成对照必须显式 `--controls synthetic`。`--rollback none` 本身也要求 controls 里含 synthetic。
- 矩阵 case 计数不受影响（`matrix.json` 只统计矩阵行）；报告把 `control_origin` 分成 `matrix` / `synthetic` 两列。
- 它的唯一用途是给"窗口触发"提供**时机匹配的 no-op 对照**（D 的矩阵 C0 全在 `all_done_control`，见 Part III §28）。

## 14. `window` 与触发策略（D 专用）

| 参数/值 | 语义 |
|---|---|
| `--test d-native --axis window=early` | 在"第一个子目标完成、后续尚未开始"时注入 |
| `--axis window=mid` | 在"已抓起后序目标物"时注入 |
| `--axis window=later` | 在"后序物已运到目标上方、尚未放置"时注入 |
| `--axis window=matrix`（默认） | 矩阵里出现的全部窗口（early/mid/later），按窗口分组出分母 |

- **触发只看 GT 谓词与仿真状态**（SPEC §3.4）；`trigger_criterion` 的历史字符串必须在运行时映射到事件名，并同时记录 `trigger_criterion_raw` 与 `mapped_event`（映射表见 Part III §30）。
- D 的 `success-delay` 被禁止：窗口是**语义事件**，不是"完成后的秒表"；给窗口加后置延迟会改变窗口定义。若将来确实需要"事件后 offset"，应新增独立 axis `window-offset` 并先走数据/协议评审（不进 v1）。
- 窗口准入：`trigger_rate < 0.20` 的窗口按 `N/A` 出表（`configs/protocol.yaml` `window_admissibility`），**不是 0%**，且要写明原因；`run-summary` 必须记录 `window_admissible`。
- D 额外门控（README §5.2）：`s1_reachable`、`event_fires_reproducibly`（同轨迹 `trigger_step` 偏差 ≤1 步）、`s2_undisturbed_by_injection`。未实现的判据要标 `unverified` 而不是 `pass`。

## 15. 其它轴

| axis | 说明 | 备注 |
|---|---|---|
| `target` | B 的 `g/s1/s2/both/pre`：撤销哪一个**已经为真**的关系 | 它是 B↔D 配对的关键（Part III）；D 固定 `s1`，传了即报错 |
| `init-row` | 0–4；variance 子集 | 必须进 arm_id 与路径（修 G6） |
| `seed` | 动作采样随机性 | 主表 seed=0；variance 另做重复 |
| `model` | **不是 axis**：一次 run 只加载一个模型 | 跨模型比较用 `compare --a/--b` |

`--axes-file FILE`（YAML）用于把一组轴冻结成可复现的 sweep 定义：

```yaml
test: d-native
axes:
  window: [early, mid, later]
  rollback: [L0, L1:d03, L2:r30]
  init-row: [0]
  seed: [0]
controls: matrix+synthetic
```

## 16. v3 参数总表（与现状差异用 ✚/✎ 标出）

### 16.1 选择与轴

| 参数 | 默认 | 说明 |
|---|---|---|
| `--test {b,d-native}` ✚ | `b` | **B/D 分离的唯一开关**；一次 run 只能一个 test |
| `--matrix` | 按 test 取默认矩阵 | 显式覆盖；`--test d-native` 默认 `dataset/matrices/d-native-matrix.csv` |
| `--dataset-suites` ✎ | 无 | 原 `--suites`（保留为别名）；值是 `goal/object/spatial/l10` |
| `--case-ids` | 无 | 不变 |
| `--task-ids` ✚ | 无 | 如 `l10:0,l10:33`；与 `--case-ids` 取交 |
| `--split {lite,core,full}` | `core` | **改为在 shard 之前** |
| `--max-tasks` / `--max-cases` | 0 | `--max-tasks` 改为"当前子集内" |
| `--shard-index` / `--shard-count` | 0 / 1 | 不变 |
| `--axis` / `--axes-file` ✚ | 无 | §11 |
| `--success-delay` / `--rollback` ✚ | 见 §11.1 | 两个维度开关的便捷别名 |
| `--max-arms` ✚ | 64 | 笛卡尔积护栏 |

### 16.2 协议（预算/触发/控制）

| 参数 | 默认 | 说明 |
|---|---|---|
| `--max-steps` ✎ | 按 test（B 600 / D 800） | 注入前预算 |
| `--repair-window` ✎ | 300 | **改为 CLI 优先**；矩阵列作为参考值记录；`--strict-matrix-protocol` 时禁止覆盖 |
| `--replan` | 10 | 不变 |
| `--trigger-wait` ✎ | 60 | 原 `--max-trigger-wait`（保留别名） |
| `--delay-alignment {require,warn,off}` ✚ | `warn` | §12.2 |
| `--controls {auto,matrix,synthetic,none,matrix+synthetic}` ✚ | `auto`（B→matrix，D→matrix+synthetic） | 控制臂策略；`none` = 无控制（`control_rate` 记 N/A） |
| `--camera` / `--settle-steps` | 256 / 10 | 不变 |

### 16.3 模型、渲染、运行时、断点

| 参数 | 说明 |
|---|---|
| `--model/--policy`、`--checkpoint`、`--config-name`、`--unnorm-key`、`--workspace` | 同现状，默认 `--model none` |
| `--video/--no-video`、`--video-fps` | 同现状 |
| `--libero-home`、`--libero-python` | 同现状 |
| `--resume/--no-resume` | 同现状，但**增加 arm 指纹校验**（§19） |
| `--retry-errors`、`--retry-invalid` | 同现状 |
| `--layout {auto,flat,arms}` ✚ | `auto`：1 臂扁平、>1 臂分目录 |
| `--require-manifest` ✚ | 校验矩阵 sha 与 `dataset/manifest.yaml` 一致 |
| `--dry-run` | 同现状（`plan` 为其别名） |

## 17. 校验规则与退出码

| 规则 | 检查 | 失败时 |
|---|---|---|
| V1 | `--test` 与轴兼容（`success-delay`/`target` 仅 b；`window` 仅 d-native） | 2，指名冲突轴 |
| V2 | 轴值语法（level/param/枚举） | 2，列出合法值 |
| V3 | 每个 arm 的矩阵交集非空 | 2，打印可用组合诊断表 |
| V4 | `L2` × joint / `pre` 非 goal-t030 / D 的 target 轴 | 2 |
| V5 | `--rollback none` 且 `--controls` 非 synthetic | 2 |
| V6 | `delay` 非负、上界、对齐策略 | 2 |
| V7 | `--max-arms` | 2 |
| V8 | `shard_count ≥ 1`、`0 ≤ index < count` | 2 |
| V9 | `--require-manifest` 时矩阵 sha 不匹配 | 2 |
| V10 | 输出目录已有 `sweep.json` 且 arm 指纹不同 | 2（除非 `--allow-config-change`） |
| V11 | 未知/未实现的 test（`a`/`c`）在 `run` 下 | 2，提示 Phase 2 |
| V12 | 真实执行时缺 `LIBERO_HOME` / checkpoint / init 文件 | 2 |

退出码沿用 `0/1/2`：`1` 仅用于"校验或评测跑完但结论失败"（`validate` FAIL、leaderboard FAIL、报告口径校验失败）。v3 不新增退出码，避免上游脚本（`repro.sh`/CI）改判。

## 18. `plan.json` v3 与 `sweep.json` 契约

### 18.1 `plan.json`

```jsonc
{
  "schema_version": 3,
  "kind": "plan", "evidence": false, "dry_run": true,
  "test": "d-native",
  "matrix": {"path": "...", "sha256": "...", "cases": 189, "tasks": 9, "by_suite": {...}, "by_level": {...}},
  "protocol": {"max_steps": 800, "repair_window": 300, "replan": 10, "trigger_wait": 60,
                "trigger": {"kind": "window", "mapping": "gt_events_v1"},
                "delay_alignment": "warn", "gates": ["completed_relation_true_before_intervention", "..."]},
  "axes": {"rollback": ["L0", "L1:d03", "L2:r30"], "window": ["early", "mid", "later"],
           "success_delay": null, "target": null, "init_row": [0], "seed": [0]},
  "arms": [
    {"arm_id": "d-native__win-early__rb-L1-d03__i0__s0__a1b2c3d4e5",
     "role": "treatment",                 // treatment | control
     "axes": {"window": "early", "rollback": "L1:d03", "init_row": 0, "seed": 0},
     "selected": 9, "tasks": 9,
     "by_suite": {"l10": 9}, "by_level": {"L1": 9}, "by_target": {"s1": 9},
     "controls": {"matrix": 0, "synthetic": 0},
     "case_ids": ["d-l10-t000-early-l1-d03", "..."],
     "estimated_steps_per_case": 1100, "budget_source": "max_steps+repair_window",
     "protocol_deviations": []},
    {"arm_id": "d-native__win-early__rb-none__i0__s0__f6e5d4c3b2",
     "role": "control",
     "axes": {"window": "early", "rollback": "none", "init_row": 0, "seed": 0},
     "selected": 9, "tasks": 9,
     "controls": {"matrix": 0, "synthetic": 9},
     "case_ids": ["d-l10-t000-early-ctl-none", "..."],
     "estimated_steps_per_case": 1100, "protocol_deviations": []}
  ],
  "totals": {"arms": 12, "treatment_arms": 9, "control_arms": 3,
              "matrix_cases": 78, "synthetic_controls": 27, "estimated_episodes": 105},
  "shard": {"index": 0, "count": 1},
  "defaults": {"policy": "pi05", "checkpoint": "...", "camera": 256, "video": true, "argv": ["..."]}
}
```

示例口径：`window × rollback` = 3 × 3 = 9 个 treatment 臂；每个窗口 1 个 synthetic control 臂（共 3 个），
每个控制臂覆盖该窗口的 9 个任务；`matrix_cases` = 每窗口 (L0 9 + L1:d03 9 + L2:r30 8) × 3 窗口 = 78。
与 v2 的差异：`arms[]` 取代单一 case 列表；每个 case 仍保留 `case_reference_delay` / `case_reference_max_steps`（矩阵冻结值）；`selected` 仍可用（=各 arm 之和）。

### 18.2 `sweep.json`（sweep 根目录）

```jsonc
{"schema_version": 3, "created_at": "...", "tool": "libero-rollback 2.0.0.dev0",
 "test": "b", "matrix_sha256": "...", "protocol_fingerprint": "sha256:...",
 "axes": {...}, "arms": [{arm_id, role, dir, fingerprint, selected}],
 "argv": ["..."], "git": {"commit": "...", "dirty": false}}
```

`protocol_fingerprint` = sha256(矩阵 sha + 协议常量 + 模型 id + checkpoint sha + axes 规范化 JSON)，用于 resume 与"报告拒绝混表"。

## 19. 产物布局、断点与 arm

```text
<output>/                                # 多臂
├── sweep.json
└── arms/
    └── b__dly-10__rb-L1-d03__i0__s0__a1b2c3d4e5/
        ├── run-manifest.json            # axes + fingerprint + protocol + argv
        ├── matrix.json
        ├── episodes.jsonl
        ├── run-summary.json
        ├── report.md
        └── l10/<case_id>/init-0/seed-0/{summary.json,trace.jsonl,video.mp4}
```

- `--layout flat`（或单臂 auto）：产物直接落在 `<output>/`，与现状兼容（消费方无需改造）。
- **路径含 `init-<i>`**：修复 G6 的覆盖问题；`seed-<s>` 保留。
- resume 键 = `(fingerprint, case_id, init, seed)`；`episodes.jsonl` 每行写 `fingerprint`。指纹不匹配 → 退出码 2（V10），防止 G5 的静默混表。
- 顶层 `report --sweep DIR` 会为每个 arm 调一次 `report`，再出跨臂表。

## 20. report / compare 口径

`report --sweep DIR` 输出：

```text
arm | test | rollback | delay | window | target | n(valid) | Recovery(95% CI) | control_rate | trigger_rate | SR | N/A?
```

规则（全部沿用 SPEC §6 / protocol §9 的红线）：

1. `Recovery = valid_recovered / (valid_recovered + valid_not_recovered)`；C0、无效注入、外部复原、协议不完整、不可触发**一律排除**。
2. `control_rate` 分母 = 该 arm 尝试的 C0（含 synthetic），并按 `control_origin` 分列。
3. `trigger_rate` 分母 = 尝试的 case；窗口 `trigger_rate < 0.20` → `N/A` 并写原因。
4. 每个数字带 **init 数 + 预算（max_steps + repair_window）+ Wilson 95% CI**。
5. `protocol_deviation` 非空的 arm 默认进附录，`--include-deviations` 才进主表。
6. 禁止把不同 `test`、不同 `matrix_sha256` 的 arm 放进同一张表。

`compare --a ARM_A --b ARM_B --paired-by case-key`：

- `case-key = (test-independent 部分：suite, task_idx, level, param, target)`；B(`target=s1`) 与 D(任窗口) 在这套 key 下**逐格对齐**（Part III §26）。
- 输出 `ΔRecovery`（pp）+ 配对表（a-only / b-only / both / neither）+ **exact McNemar** p 值（需要新增 `metrics.exact_mcnemar`，见 §22）。
- 预算不同必须在输出里带 `budget_note`；不允许隐藏。

## 21. 兼容性映射（旧 → 新）

| 旧 | 新 | 行为是否变化 |
|---|---|---|
| `run --matrix b-matrix.csv` | `run --test b --matrix ...` | 不变（`--test b` 是默认） |
| `--suites l10` | `--dataset-suites l10` | 语义不变，旧名保留为别名 |
| `--delay-steps 30` | `--success-delay 30`（单值） | 数值生效方式不变，但产物现在记录 `axes.success_delay` |
| `--delay-steps 0,10`（不支持） | `--success-delay 0,10` | 新增多值 → 多臂 |
| （无） | `--rollback L1:d03` | 新增选择能力 |
| `--repair-window 5` | 同左，但**现在生效** | 行为变化（修 G8），需在 CHANGELOG 说明 |
| `--max-trigger-wait` | `--trigger-wait` | 别名保留 |
| `--split lite` + shard | 先 split 再 shard | 行为变化（修 G7），分片内容可能不同 |
| `report --run DIR` | 同左；多臂用 `report --sweep DIR` | 单臂输出保持兼容 |

**默认路径回归测试必须证明**：`run --test b --split core --dry-run` 的 `case_ids` 与 v2 完全一致（442 条），`--split lite` 仍为 10 条 B。

## 22. 实现清单

| 文件 | 改动 | 规模 |
|---|---|---|
| `src/libero_rollback/axes.py` ✚ | axis 解析/规范化/笛卡尔积/arm_id/指纹；纯 stdlib | ~300 行 |
| `src/libero_rollback/matrices.py` ✎ | 新增 `DCase`/`DMatrix`/`load_d_matrix`、`load_matrix(test)`；B 校验保留 | ~200 行 |
| `src/libero_rollback/cli.py` ✎ | `--test`/轴参数/`--controls`/`plan`/`compare`；旧参数映射 | ~200 行 |
| `src/libero_rollback/runner.py` ✎ | `RunConfig` 拆 `ProtocolConfig` + `ArmAxes`；`run_case` 接 `TriggerPolicy`；`run_sweep`（单次模型加载跑多臂）；v3 plan | ~350 行 |
| `src/libero_rollback/runtime/triggers.py` ✚ | `AllDoneTrigger`（含 delay）、`WindowTrigger`（GT 事件 + legacy 映射 + 可复现性检查） | ~250 行 |
| `src/libero_rollback/runtime/trace.py` ✚ | 独立 trace writer + 终点 GT 快照（C7） | ~120 行 |
| `src/libero_rollback/report.py` ✎ | 按 arm/axis 分组、N/A、deviation、synthetic control 分列 | ~150 行 |
| `src/libero_rollback/metrics.py` ✎ | `exact_mcnemar`、`cluster_bootstrap`、`group_by(axes)` | ~150 行 |
| `tests/test_axes.py` ✚ | 语法、展开、arm_id 稳定性、空交集、越界 | ~200 行 |
| `tests/test_cli_axes.py` ✚ | plan 的 arms/case 数、refusal 用例、v2 默认回归 | ~150 行 |
| `tests/test_d_matrix.py` ✚ | D loader 契约（189 行、窗口、legacy→event 映射） | ~80 行 |
| `configs/protocol.yaml` ✎ | 新增 `axes` 允许集、`delay_alignment`、`window_admissibility` 已有 | — |
| `docs/SPEC.md` §5 / `docs/protocol.md` §6.1 | 增加"delay 是轴、repair 优先级、B/D 不混 run" | — |
| `README.md` §6.2 | 协议参数表补 axis 一节 | — |

测试必须覆盖的拒绝用例：`--test d-native --success-delay 10`、`--rollback L2` 只选到 joint、`--rollback none` 无 synthetic、`shard_index` 越界、空交集、`--max-arms` 超限、指纹不匹配的 resume。

---

# Part III · LIBERO-10：B 与 D 应如何分开

## 23. 数据事实（全部实测）

| 维度 | B（`b-matrix.csv`） | D-native（`d-native-matrix.csv`） |
|---|---|---|
| l10 case 数 | **197** | **189** |
| l10 task 数 | **10**（t000/033/078/133/137/145/158/193/237/**276**） | **9**（同上，**无 t276**） |
| 触发 | `all_done`（全部 native goal 真）+ `delay_steps=10` | `early` / `mid` / `later`（GT 事件） |
| level 分布（l10） | C0 10 / L0 28 / L1 84 / L2 75 | C0 9 / L0 27 / L1 81 / L2 72 |
| 每任务每窗口构成 | s1：L0 1 + L1 3 + L2 3（joint 任务无 L2） | L0 1 + L1 3 + L2 3（joint 无 L2） |
| 撤销目标 | `g/s1/s2/both/pre`（l10：g 7 / s1 60 / s2 57 / both 63 / c0 10） | 恒为 `s1` |
| 预算 | 600 + 300 | **800 + 300** |
| 控制 | 每任务 1 条 `C0`，触发在 `all_done` | **9 条 `all_done_control`，全部触发在 `all_done`**（窗口内无 C0） |
| 额外门控 | — | `s1_reachable`、`event_fires_reproducibly`、`s2_undisturbed_by_injection`、窗口 `trigger_rate` |

**关键配对事实**：B 的 `l10 + target=s1` 子集 = **60 条**，任务恰好是 D 的 9 个任务，且每任务层级构成（L0 1 / L1 3 / L2 3）与 D 的**任一窗口**（每窗口 60 条：L0 9 / L1 27 / L2 24）**逐格相同**；case_id 后缀可直接对齐：

```text
b-l10-t033-s1-l0      ↔ d-l10-t033-early-l0
b-l10-t033-s1-l1-d03  ↔ d-l10-t033-early-l1-d03
b-l10-t033-s1-l2-r30  ↔ d-l10-t033-mid-l2-r30
```

这是全数据集中**唯一**完全配对的 B↔D 对比（其余 B(l10) 行没有 D 对应；t276 只有 B）。

## 24. 三个问题先拆开

用户的疑问实际包含三个可分离的决策：

1. **测量对象**：B 测"任务全部完成后，已达成状态能否被保住"；D 测"任务未完成、尚有 pending 目标时，撤销一个已达成子目标的代价"。→ 不同问题，不能互相替代。
2. **配对单位**：若要比较两者，唯一可比的是"同一任务、同一 level/param、同一被撤销谓词"的格子；l10 上这正好是 B(`target=s1`) × D(窗口)。
3. **预算与门控**：B 600、D 800，且 D 多三个门控 → 即使配对，也只能做**配对的条件差**，不能做"B vs D 的绝对率"比较。

## 25. 为什么不能放进同一个 run / 同一张表（5 条）

1. **触发语义不同**：B 的 `trigger_rate` 是"任务被完成的比例"；D 的是"窗口可达率"，且 <20% 要按 `N/A` 剔除。混在一起会让两个分母互相污染。
2. **预算不同**：B 600+300、D 800+300；`Cost`/步数分布不可比（除非显式对齐，见 §26.3）。
3. **门控不同**：D 多 `s2_undisturbed_by_injection` 等；两者 `case_valid` 的含义不同 → 分母不同。
4. **控制结构不同**：B 有矩阵 `C0`；D 只有 `all_done` 的 C0，窗口内没有 no-op（§28）。
5. **聚合键冲突**：两者 `suite` 都是 `l10`，`metrics.summarize` 会按 suite 合并（G10），把两种协议混成一个 `by_suite.l10`。

**结论**：`--test b` 与 `--test d-native` 必须各自成 run；跨 test 的比较只能由 `compare` 在两个 run 之间按 case-key 配对完成。

## 26. 推荐分法（l10 的具体臂族）

### 26.1 三个臂族

| 臂族 | 命令 | 回答的问题 | 进主表？ |
|---|---|---|---|
| **B-l10 参考** | `run --test b --dataset-suites l10 --axis target=s1 --success-delay 10` | 完成后 10 步撤销、无 pending 的净效应（与 A(l10) 配对） | ✅ 主表 |
| **B-l10 延迟敏感性** | 同上，`--success-delay 0,30,60` | "完成后多久撤销"是否重要；C0 继承同一 δ | ✅ 主表（附录给未对齐臂） |
| **D-l10 三窗口** | `run --test d-native --axis window=early,mid,later` | 有 pending 时的撤销代价；窗口进程效应 | ✅ 主表（分窗口，不合并） |

补充臂（可选）：`B-l10 target=s2/both/g`（B 内部对比：撤销哪一个已达成原子）——它不参与 B↔D 配对，但在 B 表里回答"撤销位置"。

### 26.2 配对对比（唯一合法的 B↔D 单因子对比）

```text
对比 1（early 桥）：B(l10,target=s1,δ=10)  vs  D(l10,window=early)
  → 设计上唯一变化的因子：撤销时是否已存在 pending 目标（另有"关系年龄"混淆，见 §26.5）
对比 2（窗口进程）：D(early) vs D(mid) vs D(later)
  → 唯一变化的因子：另一目标的执行进度（B 无此条件）
```

- **对比 1 用 `compare --paired-by case-key`**：8 个 pose 任务 × 7 格 + 1 个 joint 任务 × 4 格 = **60 对/窗口**；B 侧用 `target=s1` 子集（60 条，与任一窗口同构）。
- **对比 2 不能由 B 的 `success-delay` 产生**：δ 再大，`s2` 也已为真，不存在"部分进展"；所以 mid/later 是 B 无法覆盖的条件。
- **不要做**：`B 全部 197 vs D 全部 189` 的裸率对比——任务集不同（t276）、目标不同（s1/s2/both/g）、预算不同。

### 26.3 预算混杂的处理

B 600 < D 800。两个选项（推荐后者）：

| 方案 | 做法 | 代价 |
|---|---|---|
| 接受并标注 | 所有数字带预算脚注；只比配对差 | 最省，但审稿人可能质疑"B 预算更短所以更差" |
| **预算对齐敏感性臂** | B 臂再跑一次 `--max-steps 800`（同一批 60 条） | 多 60 episode；能证明结论不依赖预算 |

若做对齐臂，`compare` 必须把 `budget_note` 写进输出，且主表仍用 600 的参考臂（与协议一致），800 臂进附录。

### 26.4 配对时必须匹配的字段

`suite + task_idx + level + param + target(=s1) + init_row + seed`；`model/checkpoint` 必须一致（由 `run-manifest` 指纹校验）；`replan/camera/settle` 必须一致。任何一项不同 → `compare` 拒绝配对（退出码 2）。

### 26.5 配对并不"纯"：混淆与协变量（诚实说明）

B(l10, s1, δ) ↔ D(early) 的差**不是单一因子**。在 D 的 `early`，被撤销的 `s1` 刚刚为真（"关系年龄"≈0 步）；
而 B 在 `all_done` 时，`s1` 已经为真了"完成 s2 所需的全部步数 + δ"。因此该对比同时改变了两件事：

1. 是否已有 pending 目标（0 → 1）；
2. 被撤销关系的**年龄**（长 → 短），即关系连续为真的时长。

同理，D 的 `early → later` 同时改变 s2 的进度与 s1 的年龄。当前数据**无法**把这两个因子完全解耦。

可做的补救（按代价从低到高）：

| 做法 | 说明 |
|---|---|
| 记录协变量 | 每 episode 写 `s1_true_since_step`、`first_all_done_step`、`pending_progress`（s2 距目标距离/是否抓起），报告把"关系年龄"作为协变量或分层变量 |
| 分层报告 | 按 `first_all_done_step` 三分位分层报 Recovery，看效应是否随"完成耗时"变化（耗时越长，s1 年龄越大 → 越接近 B 的条件） |
| 未来臂 | 新增 `window-offset`：在固定窗口事件后 k 步注入，只变关系年龄、不变进度（需数据/协议评审，不进 v1） |

结论：B↔D 的配对差应表述为"pending-ness + 关系年龄"的**联合效应**，不要写成"纯粹的 pending 效应"。

## 27. `success-delay` 能不能替代 `window`？——不能

这是最容易走错的推理，单独说清：

| 量 | B(`all_done + δ`) | D(`early/mid/later`) |
|---|---|---|
| 注入时"全部目标"状态 | 全为真 | 部分为真（s2 未达成） |
| 注入时另一目标的进度 | 已完成 | 未开始 / 已抓起 / 已到位待放 |
| 模型需要做的事 | **保住**已完成的状态（可能什么都不用做） | **继续完成 pending** 且不能丢掉被撤销的 |
| 失败模式 | 漂移/遗忘 | one-and-done、补了旧的丢了新的 |
| 预算 | 600（激活阶段已用完大半） | 800（还要做完剩下的） |

**δ 增大只是让"完成后继续执行更久"，pending 始终为 0**。因此：

- B 的大 δ 不能产生 D 的 `mid/later` 条件；
- D 的 `early` 也不能由 B 的 δ 复现（early 时 s2 尚未为真）；
- 反过来，D 的窗口也无须 δ：窗口本身就是"撤销时机"；给窗口再叠加延迟会越过窗口定义。
- 结论：**两个 timing 轴度量不同条件，都必须保留；`--success-delay` 只允许在 `--test b` 下使用**（CLI 层强制，V1）。

## 28. D 的窗口对照缺口（重要数据债）

现状：D 的 9 条 C0 全部是 `all_done_control`（触发在任务完成时），**没有任何窗口内的 no-op 对照**。这意味着 D 的 `early/mid/later` 臂缺少"同样在窗口注入、但不改状态"的基线，无法把"撤销的代价"与"在窗口处打断/继续的代价"分开。

三种处理，推荐 **B → A**：

| 方案 | 内容 | 优点 | 缺点 |
|---|---|---|---|
| **A（推荐，长期）** | 数据变更 v2.1：每个窗口增加 1 条 C0（`d-l10-tXXX-<window>-c0`），走 manifest/版本号 | 与 B 的 C0 语义一致、可发布 | 需改冻结矩阵（版本升级、9×3=27 行） |
| **B（推荐，Phase 2 临时）** | CLI `--rollback none --controls synthetic`：同窗口触发、不注入 | 不改数据、立刻可用、显式标注 `control_origin=synthetic` | 不是矩阵 case，不能与矩阵计数混报 |
| C（不推荐） | 用 `all_done_control` 近似窗口控制 | 零成本 | **时机不同，不能替代**；会低估/高估窗口效应 |

报告要求：D 表的 `control_rate` 必须按 `control_origin` 分行；若某窗口只有 synthetic 控制，脚注写明"矩阵无该窗口 C0（数据债 D-C0-WINDOW）"。

## 29. 主表 / 附录建议（l10）

| 表 | 内容 | 口径 |
|---|---|---|
| 表 1（B 主表） | B 全 442，按 suite × level × target；l10 单列 | `Recovery` + `control_rate` + `trigger_rate`；budget 600+300 |
| 表 2（D 主表） | D-native 189，按 window × level；三窗口分列不合并 | `Recovery` + 窗口 `trigger_rate`（<20% 记 N/A）+ 控制（matrix/synthetic 分行）；budget 800+300 |
| 表 3（配对） | B(l10,s1,δ=10) ↔ D(early/mid/later) 的 ΔRecovery + McNemar | 只报配对差；budget 差异脚注；n=60/窗口 |
| 附录 A | B 的 δ 敏感性（0/30/60）、未对齐臂、预算对齐臂（800） | 标明 deviation |
| 附录 B | B(l10) 的 `target=s2/both/g`、t276 | 不与 D 配对 |
| 附录 C | D 的 synthetic 窗口控制 | `control_origin=synthetic` |

## 30. `trigger_criterion` 映射（D runner 的硬要求）

矩阵里的 `trigger_criterion` 是**来源仓旧标签**（`dataset/README.md` §4.2 已列为数据债），运行时必须映射，不得复用 5 cm / 8 cm 阈值：

| 窗口 | 矩阵旧标签 | 映射后的 GT 事件（SPEC §3.4） | 备注 |
|---|---|---|---|
| `early` | `s1 first true` | `enter_first_subgoal_completed` | s1 首次为真；s2 尚未开始 |
| `mid` | `s2 displacement > 5 cm` | `enter_next_subgoal_lift` | **5 cm 判据作废**，改用"后序物被抓起" |
| `later` | `distance to s2 goal < 8 cm` | `enter_next_subgoal_preplacement` | **8 cm 判据作废**，改用"已到位未放置" |
| `all_done_control` | `no injection` | `all_done` | 与 B 的触发同义 |

trace 里同时写 `trigger_criterion_raw`（矩阵原文）、`mapped_event`、`event_source: gt_predicate`、`trigger_step`；`event_fires_reproducibly` 用同一轨迹重放比较 `trigger_step` 偏差 ≤1 步。

## 31. 一页结论

1. **B 与 D 是两套协议**：不同触发、不同预算、不同门控、不同控制结构 → `--test b` / `--test d-native` 分开跑、分开出表；跨 test 只用 `compare` 做配对差。
2. **l10 的合法配对只有一个**：`B(l10, target=s1, δ=10)` ↔ `D(l10, 任一窗口)`，8×7 + 1×4 = 60 对/窗口，格子逐一同构；`early` 是桥接窗口，`mid/later` 是 B 无法覆盖的"部分进展"条件。
3. **`success-delay` 只属于 B**，是"完成后多久撤销"的秒表；**`window` 只属于 D**，是"任务进行到哪一步撤销"的事件。两者不可互换、不可合并成同一 axis。
4. **`rollback` 是统一的扰动维**：`matrix/all/C0/none/L0/L1[:dNN]/L2[:rNN]`；`none` 是 D 窗口唯一可行的时机匹配对照，必须标 `control_origin=synthetic`。
5. **数据债要写下来**：D 的三个窗口没有矩阵 C0（`D-C0-WINDOW`）；`trigger_criterion` 旧标签必须映射；B 的 t276 无 D 对应；B/D 预算差 200 步需对齐臂或脚注。

---

## 附录 A · 参数速查（现状 → v3）

| 目的 | 现状命令 | v3 命令 |
|---|---|---|
| 冒烟 B lite | `run --split lite --dry-run --model none` | 同左（默认 `--test b`） |
| 只跑 L1:d03 | 只能 `--case-ids`（手抄 ID） | `--rollback L1:d03` |
| 成功后 0/10/30 步撤销 | 重跑三次、手工分目录 | `--success-delay 0,10,30`（3 臂自动隔离） |
| 控制组 | 矩阵 C0 自动包含 | `--controls auto`（默认） |
| D 窗口 | 不支持 | `--test d-native --axis window=early,mid,later` |
| 窗口 no-op 对照 | 不支持 | `--test d-native --controls synthetic --rollback none` |
| B↔D 配对 | 手工 | `compare --a runs/b-l10s1 --b runs/d-l10 --paired-by case-key` |
| 断点续跑 | `--resume`（只按 case_id） | 同左 + arm 指纹校验 |
| 报告 | `report --run` | `report --run`（单臂）/ `--sweep`（多臂） |

## 附录 B · arm_id 与命名

```text
arm_id   = "<test>__<slug>__<sha256(canonical_axes_json)[:10]>"
slug     = 各轴的短标签，固定顺序（不含 test 前缀）：
           b: dly-<δ>__rb-<level[-param]>__tgt-<target>__i<init>__s<seed>
           d: win-<window>__rb-<level[-param]>__i<init>__s<seed>
role     = treatment | control
case 目录 = <arm>/<suite>/<case_id>/init-<i>/seed-<s>/
synthetic case_id = <去掉 level/param 的 case_id>-ctl-none
```

`canonical_axes_json` 的键按 §11.2 的固定顺序、值排序后序列化，保证"同一组轴 → 同一 arm_id"。

## 附录 C · 本文需要同步修改的文档

| 文档 | 需要改的内容 |
|---|---|
| `docs/SPEC.md` §5 | 增加"`delay_steps` 是运行期轴（矩阵列 10 为参考值）"；明确 `repair_window` 的 CLI 优先级 |
| `docs/protocol.md` §6.1 | 增加 axis 语义、`--test` 分离、D 的 synthetic 控制规则 |
| `configs/protocol.yaml` | 增加 `axes` 允许集、`delay_alignment`、`control_origin` 枚举 |
| `README.md` §6.2 | 协议参数表补 `--success-delay` / `--rollback` 两行；§3.5 补"δ 与 window 不可互换" |
| `dataset/README.md` §4 | 新增数据债 `D-C0-WINDOW`（每窗口无 C0）与 t276 无 D 对应 |
| `docs/implementation-status.md` | ISSUE-4/G1–G12 的处置状态 |
