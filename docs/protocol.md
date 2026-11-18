# 评测协议（Evaluation Protocol）

> 版本：v2.0-draft ｜ 日期：2026-11-18 ｜ 上位文档：[README.md](../README.md) · [docs/SPEC.md](SPEC.md)
> 机器可读常量镜像：[configs/protocol.yaml](../configs/protocol.yaml)。**本文件与 SPEC §5 冲突时以 SPEC 为准**，三处（SPEC §5 / 本文件 / `configs/protocol.yaml`）必须在同一次变更里一起改。
> 状态标记：✅ 已实现并验证；🟡 部分实现 / 待验证；⬜ 未开始（Phase 2）。

本文回答：**一次 LIBERO-Rollback 评测从零到可提交结果要经过哪些阶段、每个阶段的通过判据是什么、产物长什么样、哪些事绝对不能做**。方法学与指标定义见 README §4–§6，数据契约见 SPEC。

---

## 0. 阶段总览

| 阶段 | 入口 | 产物 | 通过判据 | 当前状态 |
|---|---|---|---|---|
| S0 静态校验 | `uv sync --extra dev` → `validate_dataset.py` → `pytest` → `ruff` | 终端输出 / 校验报告 | 退出码 0，dataset 与契约测试全绿 | 🟡 dataset + pytest 已通过；`ruff` 还有少量告警，见 [implementation-status.md](implementation-status.md) |
| S1 资产校验 | `scripts/bootstrap_libero.py` → `scripts/verify_libero.py` | `.cache/libero/config.yaml`、校验输出 | commit / clean / 计数 / sha256 全通过 | 🟡 计数与 commit 已可验证；sha256 内容 pin 为 Phase 2 |
| S2 环境冒烟 | `scripts/smoke_env.py`（需仿真 env） | `runs/smoke/smoke_env.json` | `success=False`、观测形状正确、无初始穿透 | 🟡 依赖仿真环境 |
| S3 计划（dry-run） | `scripts/run_b_matrix.py --dry-run` | `plan.json` | 计划可生成、不启动仿真/模型 | ✅ B 套件可用 |
| S4 评测 | `scripts/run.sh --execute ...` 或 `libero-rollback run` | run 目录（见 §5） | 逐 case 门控 + 聚合口径正确 | 🟡 B 套件链路存在；D 窗口触发未实现 |
| S5 报告与提交 | `libero-rollback report` / `leaderboard validate` / 人工审核报告 | 自包含 HTML + `aggregate.json` + 审核报告 | 契约校验、分母齐全、注入/恢复可逐 case 人工复核 | 🟡 本地报告与审核模板已实现（`docs/report-template/`、`scripts/build_review_report.py`）；真实 v2 主表 run 待 M2 |

> **只有 S4 的 episode 产物是评测证据。** `plan.json`、dry-run 输出、静态校验报告都**不是**证据，不得进表。

---

## 1. 三类环境，三种职责（不要合并）

| 环境 | 内容 | 用途 | 约定 |
|---|---|---|---|
| 仓库 `.venv` | Python 3.11+，仅 PyYAML + jsonschema（dev 额外 pytest/ruff/numpy） | 静态层：矩阵、校验、证据、指标、报告 | CPU、可离线、CI 快速通过 |
| 仿真 `.venv-sim` | `requirements-sim.lock.txt`：numpy/robosuite/mujoco/bddl/gym/torch | 环境冒烟、注入有效性、C3/C4 oracle | `MUJOCO_GL=egl`（GPU）或 `osmesa`（CPU/CI） |
| 每模型 `.venvs/<model>` | 各模型官方推理栈 | 只做推理，由 runner 以**子进程**调用 | 见 [configs/models.yaml](../configs/models.yaml) 与 [configs/envs/README.md](../configs/envs/README.md) |

环境变量模板见 [.env.example](../.env.example)。硬性要求：**仓库文件里不出现主机绝对路径**；`LIBERO_HOME` / `LIBERO_CONFIG_PATH` / `PI05_PYTHON` 等一律由环境提供。`LIBERO_CONFIG_PATH` 必须指向仓库内 `.cache/libero`，**绝不写 `~/.libero`**（会与本机其它 LIBERO 变体互相污染）。

---

## 2. S0 静态校验（无仿真、无 GPU）

```bash
uv sync --extra dev
uv run python scripts/validate_dataset.py --dataset dataset     # 矩阵/manifest/lite/路径卫生
uv run pytest                                                    # 静态契约测试
uv run ruff check .
```

通过判据：三条命令退出码 0。失败时**不得**进入 S1 之后的任何步骤；修复后从 S0 重跑（数据/契约变更必须同步 `manifest.yaml` 与数据卡，见 SPEC §8–§9）。

关键检查点：

1. `dataset/matrices/*.csv` 列契约与计数（A 40 / B 442 / D-native 189 / D-compose 360 provisional / C 0）；
2. `manifest.yaml` 逐文件 sha256 与计数一致，`--check` 可零 diff 重建；
3. `lite.yaml` 的 30 条全部能在矩阵中找到（跨矩阵 case_id 唯一）；
4. `dataset/` 内无绝对主机路径、无前序仓引用；
5. CI 独立性守卫（见 [attribution.md](attribution.md)）。

---

## 3. S1 资产 pin 校验（强制，运行前）

上游 LIBERO 是唯一外部数据源，commit / clean worktree / 逐文件内容三层 pin（README §8.1，[assets/libero.lock.yaml](../assets/libero.lock.yaml)）：

```bash
export LIBERO_HOME=/path/to/LIBERO
export LIBERO_CONFIG_PATH="$PWD/.cache/libero"

uv run python scripts/bootstrap_libero.py \
  --libero-home "$LIBERO_HOME" --out "$LIBERO_CONFIG_PATH"
uv run python scripts/verify_libero.py --libero-home "$LIBERO_HOME"
```

- `bootstrap_libero.py`：非交互写 `config.yaml`（`benchmark_root` / `bddl_files` / `init_states` / `datasets` / `assets` 五键），打印 `export` 行；`--check` 只校验不写；拒绝写 `~/.libero` 或写进上游 checkout。
- `verify_libero.py`：校验 commit `f78abd68…`、worktree clean、`.bddl`/`.pruned_init` 各 130 个（含 per-suite 计数）、assets 存在、以及 `assets/manifest.yaml` 中**已冻结**的 sha256（当前为空列表 → 仅 warning）。
- 开发机脏工作区可用 `--allow-dirty` 把 clean 检查降级为 warning；**评测/leaderboard run 禁止使用**。`--require-hashes` 供发布 CI 用（内容 pin 冻结前会失败，这是预期行为）。
- 内容 pin 未冻结前不得声称资产“已验证”：见 [assets/manifest.yaml](../assets/manifest.yaml) 的填充说明（`--print-sha256` 只在干净 checkout 上生成真实哈希）。

---

## 4. S2 环境冒烟（需要仿真环境）

```bash
export MUJOCO_GL=egl            # CPU/CI 用 osmesa
.venv-sim/bin/python scripts/smoke_env.py --libero-home "$LIBERO_HOME"
```

通过判据（任一条不满足即失败，**禁止假成功**）：BDDL 可加载；`OffScreenRenderEnv` 可创建；官方 `.pruned_init` 第 0 行可读取并 `set_init_state`；初始 `check_success()` 为 `False`；观测形状与相机设置符合协议。仿真/资产不可用时脚本必须**明确失败**并写最小复现命令，而不是跳过。

---

## 5. S3 dry-run 计划（plan.json 不是证据）

```bash
uv run python scripts/run_b_matrix.py --dry-run \
  --matrix dataset/matrices/b-matrix.csv \
  --output runs/plan-b --max-cases 3
```

- 只写 `plan.json`；**不启动仿真、不加载模型、不读 init 文件**；
- 用于确认 case 选择、分片、预算与 shard 切分正确；
- 任何报告中的数字都不能来自 plan.json。

---

## 6. S4 评测协议（主表口径）

### 6.1 预算与触发（SPEC §5，`configs/protocol.yaml`）

| 项 | 值 |
|---|---|
| A / C `max_steps` | 600（A 主表 1 init；10-init 上界协议另行报告） |
| B `max_steps` + `repair_window` | 600 活跃步 + 300 修复窗口 |
| D-native | 800 + 300 |
| D-compose（Phase 2） | 600 + 300 |
| B trigger | `all_done`（全部 native goal 由 GT 判定为真）+ `delay_steps=10` |
| D 窗口 | `early` / `mid` / `later`，**只用 GT 谓词与仿真状态**判定，禁止外部 runtime profile |
| `replan_steps` | 10（与 B `delay_steps` 对齐，触发不落在同一动作块内） |
| `init_row` / `seed` | 0 / 0（主表）；variance 用 init 0–4 |
| `camera` / `settle` | 256 / 10 |
| 视频 | 20 fps，H.264 / yuv420p / faststart，含 1 s 注入决策卡 |
| 成功判定 | 环境 `check_success()` + GT 谓词 trace；**禁止 VLM 判官** |

`repair_window` 是注入有效后**追加**的预算，不挤占主预算；每个 episode 必须记录实际 `repair_budget_steps`。

### 6.2 撤销扰动族（README §3.4）

`C0`（no-op，不动状态，关系必须仍为真，每任务恰好 1 条）/ `L0`（恢复 episode 初始位姿）/ `L1`（沿「目标区域中心 → 初始位姿」水平射线外推 δ ∈ {3, 6, 10} cm；关节任务改为开度 10/25/40%）/ `L2`（绕世界 z 轴 yaw ∈ {30°, 60°, 90°}）。

- `L1`/`L2` 是两种**扰动形态**，不是难度等级；不得写成“难度递增”。
- 每条非 C0 case 必须记录实测几何量 `dtranslation_m`、`dangle_rad`、`axis`。
- 注入直接写 MuJoCo `qpos/qvel` 后 `mj_forward`，不依赖运行时补丁。

### 6.3 逐 case 门控（B / D，缺一即 `injection_invalid`）

| 门控 | 判据 |
|---|---|
| `baseline_task_solvable` | 同任务在基线协议下可成功（同模型同协议） |
| `completed_relation_true_before_intervention` | 触发时关系为真，来自 GT（不是历史账本） |
| `relation_false_after_intervention` | `L0/L1/L2` 注入后关系为假；`C0` 相反，必须仍为真 |
| `no_object_penetration` | 物体-场景侵入 ≤ **1 cm** |
| `zero_velocity_after_intervention` | 注入后物体线/角速度归零 |
| `object_released` | 两指间距 > 1 cm |
| `restorable` | 状态写回 oracle 能在 repair window 内恢复关系（C4；全量为 Phase 2） |
| `geometry_recorded` | `dtranslation_m` / `dangle_rad` / `axis` 已落盘 |

D 额外：`s1_reachable`、`event_fires_reproducibly`（同一轨迹 `trigger_step` 偏差 ≤ 1 步）、`s2_undisturbed_by_injection`；`trigger_rate` 是**实测值**，窗口 `trigger_rate < 20%` 时按 `N/A` 从主表剔除并说明原因（不删 case）。

### 6.4 判定 verdict 与分母（SPEC §6）

判定器 verdicts：`valid_recovered` / `valid_not_recovered` / `valid_control` / `valid_relation_preserving_probe` / `valid_external_restoration` / `injection_invalid` / `trigger_not_reached` / `truth_unverified` / `protocol_incomplete` / `incomplete`。

```
Recovery     = valid_recovered / (valid_recovered + valid_not_recovered)
control_rate = valid_control / C0 attempted
trigger_rate = triggered / attempted
```

C0、无效注入、外部复原、协议不完整、不可触发**一律排除**出 Recovery 分母。不可触发 = `N/A`（**不是 0%**）。

---

## 7. 产物布局（run 目录即证据）

```text
<output>/
├── run-manifest.json      # 默认参数 + argv + 环境摘要
├── matrix.json            # 矩阵摘要（cases / tasks / by_suite / by_level）
├── plan.json              # dry-run 计划（不是证据）
├── episodes.jsonl         # 一行一个 case summary（追加写）
├── run-summary.json       # 运行级汇总（Recovery / control / trigger / 成本）
├── report.md / report/    # 自包含 HTML + aggregate.json（Phase 2）
└── <suite>/<task_id>/<case_id>/seed-<n>/
    ├── status.json        # ok | failed | invalid_perturbation（+ error + repro cmd）
    ├── results.json       # success / steps / first_hit / GT 谓词 trace
    ├── summary.json
    ├── trace.jsonl        # episode_start / trigger / injection / step / episode_end（含终点 GT 快照）
    ├── provenance.json    # 本仓 git sha + LIBERO commit/worktree + asset digest + ckpt sha + pip freeze + env
    └── video.mp4          # H.264 / yuv420p / faststart（20 fps，1 s 注入卡）
```

- 任务身份用字符串 `<suite>/<bddl_stem>`，**不用整数 task index**（LIBERO 派生变体的注册表下标不可移植）。
- 失败也写 `status=failed` + 错误 + 最小复现命令；**禁止**“静默跳过”。
- `provenance.json` 缺失 = 该 episode 结果不可用于主表。

---

## 8. 断点续跑、分片与试跑

| 场景 | 做法 |
|---|---|
| 中断续跑 | 同一 `--output` 重跑：`status=ok` 的 case 自动跳过 |
| 重试错误 | `--retry-errors`（只重跑 `status=failed`） |
| 重试无效注入 | `--retry-invalid`（只重跑 `case_valid=false`） |
| 分片并行 | `--shard-index i --shard-count n`（按确定序切分，分片间不重叠） |
| 只数 episode | `--dry-run`（只写 plan.json） |
| 无模型冒烟 | `--policy none`（不加载模型，验证注入与 trace） |

聚合前必须确认：分片并集 = 选中 case 集、无重复 case_id、无 `status=ok` 但缺 `provenance.json` 的 episode。

---

## 9. 报告口径（红线）

> 报告模板与人工审核流程见 [`docs/report-template/README.md`](report-template/README.md)；首份真实报告示例见 [`experiments/b-rollback/report-goal-object-20261118/index.html`](../experiments/b-rollback/report-goal-object-20261118/index.html)。审核只回答两件事：注入是否真实有效、恢复是否真实来自策略自修复。


1. **禁止**把 `Recovery`（条件量）与 `SR`（无条件和）并排当同一个量；
2. 不可触发 = `N/A`，不是 0%；`N/A` 是一等结果，必须进表与正文；
3. 判定只用环境 `check_success()` + GT 谓词 trace，**禁止 VLM 判官**进入指标路径；
4. 每个数字带 **init 数 + 预算 + Wilson 95% CI**；禁止单 seed 点估计进主表；
5. micro（全 case）+ macro（按 suite/scene 等权）双列；`Retention` 只在同协议内比较；
6. 两类失败模式分开报（zero-progress vs one-and-done），被筛掉的模型也要报；
7. 同 `(structure, init)` 跨臂用 exact McNemar；suite 级 CI 按 **structure 聚类 bootstrap**；
8. v1 数字（40/40、2/49、42/477、2,112 case 等）只作动机引用，**不得与 v2 主表混排**。

---

## 10. 复现入口

```bash
export LIBERO_HOME=/path/to/LIBERO
bash scripts/repro.sh --policy pi05 --split lite            # 默认只打印计划
bash scripts/repro.sh --policy pi05 --split lite --execute  # 真正执行
```

`repro.sh` 的顺序即本文 S0 → S4（S5 在 Phase 2 补上）；缺少必需前置文件时它以退出码 2 明确报告“当前 checkout 还不能复现”，不会假装成功。Phase 1 只执行 B 套件；`lite` 的精确选择由 [dataset/lite.yaml](../dataset/lite.yaml) 驱动，runner 接入 `--split lite` 之前 `repro.sh --split lite` 以 `--max-cases 10` 近似。

模型环境：`bash scripts/setup_env.sh <model> ...`（默认只打印计划，`--execute` 才创建），锁文件写法见 [configs/envs/README.md](../configs/envs/README.md)。

---

## 11. 禁止事项（硬约束）

- ❌ 修改/新增上游 LIBERO 资产、场景、纹理、物体；本仓零新资产。
- ❌ 运行期 import / 路径引用前序仓（`libero_rollback` 数据仓、`libero_compose`、`libero_runtime`），或依赖其 `runs/`、overlay、runtime profile。
- ❌ 在指标路径使用 VLM 判官、恢复算法、控制器、test-time harness。
- ❌ 用 `plan.json`、dry-run、静态报告冒充评测证据。
- ❌ 把 `N/A` 写成 0%、把条件量 `Recovery` 与无条件 `SR` 混排、单 seed 点估计进主表。
- ❌ 手写/伪造 sha256、声称“已验证”而无可复现命令。
- ❌ 写入 `~/.libero`、把主机绝对路径提交进仓库或 `dataset/`。
- ❌ 静默修改已发布的 `case_id` / case 语义（须走数据版本号 + manifest 更新）。

---

## 12. 与其它文档的关系

- 数据契约与接口：[docs/SPEC.md](SPEC.md)（唯一权威）；
- 套件/计数/证书/数据债务：[docs/datasheet.md](datasheet.md)；
- 前序仓来源与独立性：[docs/attribution.md](attribution.md)；
- 逐模块实现进度与验收命令：[docs/implementation-status.md](implementation-status.md)；
- 协议常量机器可读镜像：[configs/protocol.yaml](../configs/protocol.yaml)；
- 模型注册表：[configs/models.yaml](../configs/models.yaml)。
