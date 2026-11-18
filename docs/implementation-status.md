# 实现状态（Implementation Status）

> 复核日期：2026-11-18 ｜ 复核人：task-4（docs-env）｜ 数据集版本 `2.0.0.dev0`（v2.0-draft）
> 上位文档：[README.md](../README.md) · [docs/SPEC.md](SPEC.md) · [docs/protocol.md](protocol.md)
> **本文件是当前仓库的事实快照**；README §0 的速览表是 M1 启动时的快照，尚未同步（README 不在本任务写 scope，需在 M1 收尾时按本文件更新）。

状态标记：✅ 已实现且**本次真实跑过验收命令并给出输出**；🟡 代码/数据已存在但未端到端验证、或验收未全绿；⬜ 未开始（Phase 2）。

**复核环境**：WSL2 Ubuntu 22.04；仓库 venv `.venv`（Python 3.12.11，PyYAML 6.0.3，pytest/ruff 已装）；`LIBERO_HOME` 指向一个 commit = `f78abd68…` 的上游 checkout（**worktree 脏，928 项变更**，所以资产校验用 `--allow-dirty`，clean 与内容 sha256 未认证）；本机未运行真实仿真 episode，也未加载任何模型权重（见 §4 ISSUE-8）。

---

## 1. 与 README §0 速览表的对应

| README §0 行 | README 快照 | 当前事实（本文件） | 对应章节 |
|---|---|---|---|
| 规范 README + SPEC | 🟡 v0.1 冻结 | ✅ SPEC v2.0-draft 已冻结为权威契约；README 与本文件同步待做 | §2.1 |
| 数据 `dataset/matrices/*` | 🟡 迁移中 | ✅ A 40 / B 442 / D-native 189 已冻结；D-compose 360 provisional；C 0 | §2.3 |
| 数据 C 套件 | 🟡 迁移中 | ⬜ Phase 2（未构建） | §2.3 |
| 数据 A 套件 | ⬜ 未开始 | ✅ 40 行已生成，`--check` 可重建 | §2.3 |
| 数据 manifest + 数据卡 + 覆盖证明 | ⬜ 未开始 | 🟡 manifest/sources/lite/数据卡已就绪；**覆盖证明未构建** | §2.3 |
| 代码 静态校验 | 🟡 移植中 | ✅ `validate_dataset.py` 12/12 + 140 个测试通过 | §2.4–§2.5 |
| 代码 注入与有效性门控 | 🟡 移植中 | 🟡 代码已移植（`runtime/perturbation.py`），未在仿真中执行 | §2.6 |
| 代码 四态 runner + trace + 视频 | 🟡 移植中 | 🟡 B 套件 dry-run 已验证；真实 episode 未跑；trace.py 缺失 | §2.6 |
| 代码 D 轴窗口触发 | ⬜ 未开始 | ⬜ `runtime/triggers.py` 不存在 | §2.6 |
| 代码 模型适配器 | 🟡 原型存在 | 🟡 三个 adapter 模块已移植；未加载权重 | §2.7 |
| 代码 报告 / leaderboard / 提交校验 | ⬜ 未开始 | 🟡 `report.py`/`cli.py` 已实现且有单测；无真实 run 端到端 | §2.8 |
| 证据证书 C1–C8 | 🟡 部分 | 🟡 C1 部分、C2 静态/冒烟缺、C3/C4 ⬜；细分见 [datasheet §6](datasheet.md#6-证书状态c1c8) | §2.9 |
| 发布 pip + HF + datasheet + leaderboard | ⬜ 未开始 | ⬜ Phase 2 | §5 |

---

## 2. Phase 1 逐模块状态

### 2.1 规范与文档

| 组件 | 状态 | 说明 |
|---|---|---|
| [README.md](../README.md) | 🟡 | 规范草案；§0 表、§3.2 的 A 的 n 范围、§3.7 variance 规模需按 [datasheet §8](datasheet.md#8-数据债务发布前逐条解决或明确标注) 更新 |
| [docs/SPEC.md](SPEC.md) | ✅ | 数据契约与接口唯一权威（v2.0-draft） |
| [docs/protocol.md](protocol.md) | ✅ | 本任务新增：S0–S5 阶段、预算/门控/产物/续跑/报告口径/禁止事项 |
| [docs/datasheet.md](datasheet.md) | ✅ | 本任务新增：套件/实测分布/来源/证书/数据债务/限制 |
| [docs/attribution.md](attribution.md) | ✅ | 本任务新增：来源与 copy 映射、独立性约束、复核命令 |
| [docs/implementation-status.md](implementation-status.md) | ✅ | 本文件 |

### 2.2 配置与资产

| 组件 | 状态 | 验收命令 / 证据 |
|---|---|---|
| [configs/protocol.yaml](../configs/protocol.yaml) | ✅ | YAML 可解析；断言 `budgets.b=600+300`、`d_native=800+300`、`a/c=600`、`replan=10`、`delay=10`、`camera=256`、`settle=10`、`fps=20`、`core.total=1191` 全部通过（本次脚本断言） |
| [configs/models.yaml](../configs/models.yaml) | ✅ | 5 个模型条目（pi05/pi0/pi0_fast/openvla_oft/smolvla）；`runner_policy_names=[pi05,smolvla,openvla_oft,none]`；pi0/pi0_fast 标 `runner_supported: false`（`load_policy()` 未接线） |
| [configs/envs/README.md](../configs/envs/README.md) | ✅ | 每模型 env 锁的生成流程与 schema；锁文件本身 ⬜（Phase 2，需模型栈） |
| [assets/libero.lock.yaml](../assets/libero.lock.yaml) | ✅ | 代码 pin（commit/clean 要求/suite 计数/sim stack draft）；`audit` 段如实记录 clean 与 sha256 未认证 |
| [assets/manifest.yaml](../assets/manifest.yaml) | 🟡 | 期望计数已写；`files: []` **故意为空**（内容 pin 为 Phase 2，禁止编造 hash）；`--require-hashes` 会因此失败，属预期 |
| [.env.example](../.env.example) | ✅ | 环境变量模板（LIBERO_HOME / LIBERO_CONFIG_PATH / MUJOCO_GL / 模型 checkpoint 覆盖） |

### 2.3 数据（`dataset/`）

| 组件 | 状态 | 验收命令 / 证据 |
|---|---|---|
| `matrices/a-matrix.csv`（40） | ✅ | `build_a_matrix.py --check` → up to date，sha256 `e03545a2…`（本次真实输出） |
| `matrices/b-matrix.csv`（442） | ✅ | 加载校验通过（85/80/80/197；C0 40/L0 60/L1 180/L2 162）；sha256 见 `manifest.yaml` |
| `matrices/d-native-matrix.csv`（189） | ✅ | 9 任务 × `early/mid/later`（各 60）+ 9 `all_done_control`；sha256 见 `manifest.yaml` |
| `matrices/d-compose-provisional.csv`（360） | 🟡 | 仅设计占位（字段为 `<from C>`），**不进入任何执行 split** |
| `c-matrix.csv` | ⬜ | 0 行；Phase 2 |
| `sources.yaml` | ✅ | 上游 pin + 3 个导入/派生条目的 source sha256 与冻结 sha256 + 归一化说明；记录 `task_idx` 编号口径偏差 |
| `manifest.yaml` | ✅ | `build_manifest.py --check` 零 diff（本次输出 sha256 `5aebb553…`）；4 个 CSV 逐文件 sha256 |
| `lite.yaml`（30） | ✅ | 10 A + 10 B（四 level/四 suite）+ 10 D-native（三窗口 + control） |
| `dataset/README.md`（数据卡 draft） | 🟡 | 内容与实测一致；覆盖证明、C3/C4 证书待补 |

### 2.4 数据工具脚本

| 脚本 | 状态 | 验收命令 / 证据 |
|---|---|---|
| `scripts/build_a_matrix.py` | ✅ | `--check --libero-home "$LIBERO_HOME"` → OK（纯 stdlib） |
| `scripts/build_manifest.py` | ✅ | `--check` → OK（确定性零 diff） |
| `scripts/validate_dataset.py` | ✅ | `--dataset dataset` → `checks: 12/12 passed`、`OK`、exit 0 |
| `scripts/smoke_env.py` | 🟡 | `--help` 可用；`--static-only` → `selected=4 passed=0 failed=0`、`status: static_only`（**仿真未执行**，如实报告）；真实 smoke 需仿真 env |

### 2.5 契约层（纯 stdlib + PyYAML + jsonschema）

| 模块 | 状态 | 证据 |
|---|---|---|
| `src/libero_rollback/matrices.py` | ✅ | B 矩阵加载/校验；`run --dry-run` 与 `list/validate` 均使用 |
| `src/libero_rollback/schema.py`（+ `schemas/rollback-case.v1.schema.json`） | ✅ | `tests/test_schema.py` 19 项通过 |
| `src/libero_rollback/validation.py` | ✅ | `libero-rollback validate --dataset dataset` → PASS，0 error / 0 warning |
| `src/libero_rollback/evidence.py` | ✅ | `tests/test_evidence.py` 通过 |
| `src/libero_rollback/metrics.py` | ✅ | `tests/test_metrics.py` 通过（Wilson CI / Recovery 分母 / EGC / Retention） |

### 2.6 运行层（需要仿真 / 模型环境）

| 组件 | 状态 | 说明 |
|---|---|---|
| `runtime/env.py` | 🟡 | LIBERO config/env 创建与 init row 读取已移植；未在仿真中执行 |
| `runtime/perturbation.py` | 🟡 | `C0/L0/L1/L2` 注入、几何量、restorable oracle 语义已移植；未在仿真中执行 |
| `runtime/video.py` | 🟡 | 录制器已移植；无真实录像产物 |
| `runtime/triggers.py` | ⬜ | **缺失**：D 窗口（early/mid/later）触发未实现 |
| `runtime/trace.py` | ⬜ | **缺失**：逐步 GT trace + 终点 GT 快照未落地（C7 缺口） |
| `runner.py` | 🟡 | B 套件四态 runner（plan/run/resume/aggregate）；`--dry-run` 实测通过，真实 episode 未跑；**仅 B 套件**，不含 A/C/D |
| `scripts/run_b_matrix.py` | ✅ | `--dry-run --output /tmp/rb-dry-uv --max-cases 3` → `plan.json`（exit 0，未启仿真/模型） |
| `scripts/run.sh` | ✅ | 薄封装：默认 dry-run，需 `--execute`；`bash -n` 通过 |
| `scripts/repro.sh` | ✅ | 默认只打印计划；本次 plan 输出 6 步且 exit 0（全部必需前置已就绪） |
| `scripts/bootstrap_libero.py` | ✅ | `--help`、`--check`（不写）、写入、再 `--check` 一致匹配 均实测通过 |
| `scripts/verify_libero.py` | ✅ | 默认因脏工作区 **FAIL（按设计）**；`--allow-dirty` → PASS 14 checks / 2 warnings；`--print-sha256` → 260 行 |
| `scripts/setup_env.sh` | ✅ | `--help` 与 pi05 dry-run 计划可用；`bash -n` 通过；`--execute` 未运行（不安装模型栈） |

### 2.7 模型适配器与 CLI

| 组件 | 状态 | 说明 |
|---|---|---|
| `policies/{pi05,smolvla,openvla_oft}.py` + `policies/__init__.py` | 🟡 | adapter 模块与 lazy import 已就位；`load_policy()` 只接 3 个 + `none`；未加载真实权重 |
| `cli.py`（`list/validate/run/report/leaderboard`） | ✅ | `validate`、`run --dry-run`、`run --split lite`（10 B cases）已实测（ISSUE-2 已修） |
| `report.py` | 🟡 | 自包含 HTML + `aggregate.json` 实现，`tests/test_report.py` 通过；无真实 run 端到端产物 |

### 2.8 测试与 CI

| 项 | 状态 | 证据 |
|---|---|---|
| `uv run pytest` | ✅ | **140 passed in 1.68s**（本次真实输出） |
| `uv run ruff check .` | ✅ | 0 errors（2026-11-18 M1 收尾修复，见 ISSUE-1） |
| 本任务脚本自身 ruff | ✅ | `ruff check scripts/bootstrap_libero.py scripts/verify_libero.py` → All checks passed |
| `bash -n` 全部 shell 脚本 | ✅ | `setup_env.sh` / `repro.sh` / `run.sh` 均通过 |
| 独立性守卫 | ✅ | `tests/test_independence.py` 通过（前序仓 import = 0；源码/数据无主机绝对路径） |
| CI（`.github/workflows/ci.yml`） | 🟡 | 结构就绪；因 ISSUE-1 的 ruff 失败当前不会全绿 |

### 2.9 证书（摘要）

| 证书 | 状态 | 缺口 |
|---|---|---|
| C1 完整性 | 🟡 | 计数/case_id 唯一/manifest sha256 有检查；B/D 逐场景覆盖证明未构建 |
| C2 初始状态 | 🟡 | 静态路径 + `--static-only` 冒烟通过；真实仿真冒烟、init 内容 sha 未冻结 |
| C3 可解性 | ⬜ | Phase 2 oracle |
| C4 可复原性 | ⬜ | Phase 2 oracle（`restorable` 字段/门控语义已在代码中保留） |
| C5 非退化 | 🟡 | 矩阵结构级检查；语义级需 oracle |
| C6 负对照 | 🟡 | 每任务一条 C0 已强制；`infeasible`/`probe` 未构建 |
| C7 GT 记录 | 🟡 | 格式已定义；`runtime/trace.py` 缺失，终点 GT 快照未落地 |
| C8 成本 | 🟡 | 字段与汇总逻辑已定义；无 v2 实测成本表 |

细分与证据见 [datasheet §6](datasheet.md#6-证书状态c1c8)。

---

## 3. 本次复核的验收命令与真实输出（2026-11-18）

> 全部命令在仓库根目录执行；`$LIBERO_HOME` 为本机上游 checkout（commit 正确、worktree 脏）。输出为本次真实捕获（省略部分中间行）。

```console
$ uv run python scripts/validate_dataset.py --dataset dataset
[validate_dataset] rows: a=40 b=442 d_native=189 d_compose_provisional=360 c=0
[validate_dataset] libero assets: not checked
[validate_dataset] checks: 12/12 passed
[validate_dataset] OK
exit=0

$ uv run python scripts/build_manifest.py --check
[build_manifest] OK: lite.yaml and manifest.yaml are up to date (manifest sha256 5aebb553b71b2cb4e3cecc43dfaecd69dd2ef90d14670fec6d25bf6c3a6afedb)
exit=0

$ uv run python scripts/build_a_matrix.py --check --libero-home "$LIBERO_HOME"
[build_a_matrix] OK: .../dataset/matrices/a-matrix.csv is up to date (sha256 e03545a2144195776137e287aa569193c1a78469fe037025456b97f328604f12)
exit=0

$ uv run pytest
140 passed in 1.68s

$ uv run libero-rollback validate --dataset dataset
dataset validation: PASS (dataset)
  [ok] manifest: counts={'a': 40, 'b': 442, 'c': 0, 'd_compose_provisional': 360, 'd_native': 189} files=4+1 provisional
  [ok] matrices: 4 CSV file(s), 1031 unique case_id(s)
  [ok] lite split: 30 case id(s)
  [ok] path hygiene: 8 text file(s) scanned
  summary: 0 error(s), 0 warning(s)
exit=0

$ uv run python scripts/run_b_matrix.py --dry-run --output /tmp/rb-dry-uv --max-cases 3
[dry-run] plan written to /tmp/rb-dry-uv/plan.json (3 cases; no simulation, no model)
exit=0

$ uv run python scripts/verify_libero.py --allow-dirty
[ok]   git.commit                f78abd68ee283de9f9be3c8f7e2a9ad60246e95c
[warn] git.clean                 worktree dirty (928 entries); --allow-dirty is for development checkouts only
[ok]   counts.bddl_files         130 == 130
[ok]   counts.pruned_init_files  130 == 130
[ok]   counts.libero_goal        bddl=10 pruned_init=10
[ok]   counts.libero_object      bddl=10 pruned_init=10
[ok]   counts.libero_spatial     bddl=10 pruned_init=10
[ok]   counts.libero_10          bddl=10 pruned_init=10
[ok]   counts.libero_90          bddl=90 pruned_init=90
[warn] sha256                    content pin is empty (sha256_frozen: false); freeze it from a clean checkout
verify_libero: PASS — 14 checks, 2 warning(s)
exit=0
# 不带 --allow-dirty 时按设计 FAIL（exit 1）：

$ uv run python scripts/bootstrap_libero.py --libero-home "$LIBERO_HOME" --out /tmp/rb-libero-config --check
[bootstrap_libero] bddl/init files : 130 .bddl / 130 .pruned_init (expected 130 / 130)
[bootstrap_libero] CHECK: layout OK; /tmp/rb-libero-config/config.yaml does not exist yet
exit=0

$ bash scripts/repro.sh --policy none --split lite --no-video
[repro] pipeline: split=lite policy=none
[step] static dataset validation ...
[step] static test suite ...
[step] LIBERO asset pin verification ...
[step] dry-run plan (plan.json is not evidence) ...
[step] evaluate B suite (split lite) ...
[step] build report ...
[step] leaderboard validate ...
[repro] all required steps available (0 optional step(s) unavailable)
exit=0
```

**已知不通过 / 未运行（不得写成通过）**：

- `uv run ruff check .` → 4 errors（均在 `src/libero_rollback/matrices.py`，ISSUE-1）；
- `uv run libero-rollback run --dry-run --split lite` → `dataset/lite.yaml: expected a 'case_ids' list`（ISSUE-2）；
- 真实仿真 episode、真实模型加载、真实 run → report 端到端：**本次未运行**（无仿真栈/权重，且不属于文档任务验收）；
- `verify_libero.py` **不带** `--allow-dirty`：FAIL（脏工作区；这是设计行为）；
- 资产内容 sha256：未冻结（`assets/manifest.yaml files: []`）。

---

## 4. 已知问题（阻塞 CI 或阻塞发布）

| ID | 问题 | 证据 | 建议修复 / owner |
|---|---|---|---|
| ISSUE-1 | **✅ 已修复（2026-11-18）**：`matrices.py` 的 UP035 + 3×E501 已修，`ruff check .` 0 errors | `uv run ruff check .` | — |
| ISSUE-2 | **✅ 已修复（2026-11-18）**：`_split_case_ids` 兼容 `splits{suite: []}` / `cases` / `case_ids` 三种形状；`run --split lite` 实测选中 10 个 B case | `uv run libero-rollback run --dry-run --split lite` | — |
| ISSUE-3 | `runtime/triggers.py` 与 `runtime/trace.py` 缺失（SPEC 已把它们标为 Phase 2；当前 runner 内联写 trace 与终点 `final_goal_truth`/`final_revoked_truth`） | 文件不存在，SPEC §11 已标注 Phase 2 | D 套件 runner 的前置；C7 的终点真值已由 runner 写入 summary |
| ISSUE-4 | runner 仅支持 B 套件；A/D 矩阵没有对应 loader；`run --split core/full` 实际不过滤（全部 B case） | `runner.py` docstring、`cli.py` `_split_case_ids` 对 core/full 返回 None | A/D/C runner 与 loader 为 Phase 2；在此之前不要宣称跑过 core |
| ISSUE-5 | 资产内容 pin 未冻结 + 本机 checkout 脏 → clean worktree 与内容 sha256 均未认证 | `verify_libero.py` 的 2 条 warning、`assets/libero.lock.yaml` `audit` 段 | 用干净 clone + `verify_libero.py --print-sha256` 填 `assets/manifest.yaml`，再把 `sha256_frozen: true` |
| ISSUE-6 | 无任何 `configs/envs/<model>.lock`；模型 adapter 未加载过权重 | `configs/envs/` 仅 README | Phase 2 按 `setup_env.sh --execute` 生成；在此之前模型结论只是代码级 |
| ISSUE-7 | **✅ 已同步（2026-11-18）**：README §0 改为 Phase 1 实测状态表；§3.2 增加 A 的 `n_goals` 实测（31/8/1）；§3.7 variance 改为 500 episodes；§9.3 增加 task_idx / trigger_criterion / C 三处数据债务；SPEC §2.2、§3.4、§11、§13 同步 | 见 README/SPEC diff | — |
| ISSUE-8 | 本环境未运行真实仿真与真实模型；本次所有“PASS”均不含 episode 证据 | 复核环境说明；`smoke_env.py --static-only` 明示 simulation NOT exercised | 不阻塞 M1 文档/数据提交，但**阻塞任何主表数字** |

---

## 5. Phase 2 未完成项（SPEC §13 映射）

| SPEC §13 | 状态 | 说明 |
|---|---|---|
| 1. C 套件（160）与 D-compose（360）数据构建 | ⬜ | 需要 40-task pool 结构生成器 + 覆盖证明；当前 D-compose 为 provisional |
| 2. D 轴 runner（窗口触发 + D-native 189 执行） | ⬜ | 依赖 ISSUE-3 |
| 3. 脚本 oracle（C3 可解性 / C4 可复原性） | ⬜ | 主表发布前置 |
| 4. 报告中的视频证据与决策卡 | 🟡 | `report.py` 已实现；视频/决策卡在真实 run 上的端到端未验证 |
| 5. leaderboard 服务端校验 | 🟡 | 本地 `libero-rollback leaderboard validate` 已实现并通过单测；服务端未开始 |
| 6. `pip` / HF dataset / datasheet 正式发布 | ⬜ | 当前只有 draft 文档与仓库内数据 |
| 另：模型 env 锁与 adapter 端到端验证 | ⬜ | ISSUE-6 |

---

## 6. 下一步建议（按优先级）

1. **先修 ISSUE-1、ISSUE-2**：CI 绿与 README §8.5 的 `--split lite` 工作流都依赖它们；两者都是小改动。
2. **干净 checkout 冻结资产内容 pin**（ISSUE-5）：这是“换一台机器只改路径”承诺的兑现点。
3. **补 `runtime/triggers.py` + `trace.py`**（ISSUE-3）：解锁 D 套件与 C7。
4. **真实仿真 smoke + 一条 B case 的端到端 run → report**：把 🟡 的 runtime/report 转成 ✅（需要仿真 env 与一个模型 env）。
5. **C3/C4 oracle**：主表发布的前置；之后才谈成本表与 leaderboard 条目。
6. **同步 README §0 / §3.2 / §3.7 与本文件、datasheet**（ISSUE-7）。

---

## 7. 维护约定

- 本文件只能由**跑过验收命令**的人更新；每行 ✅ 必须附“命令 + 真实输出摘要”，不允许“我看代码应该是好的”。
- 更新时同步：本文件日期、README §0、[datasheet](datasheet.md) 的证书/债务、[protocol.md](protocol.md) 的阶段状态。
- 新增的 🟡/⬜ 项要写进 §4 或 §5，并尽量给出复现命令；**不得**为了“看起来完成”而降级状态。
- 权威数据仍是 `dataset/matrices/*.csv` 与 `dataset/manifest.yaml`；本文件不复制它们的数字细节。

---

## 8. M1 收尾复核（Lead，2026-11-18 11:10 +08:00）

四份迁移任务全部提交后，由 Lead 统一复核（WSL2 Ubuntu 22.04，仓库 `.venv`）：

| 命令 | 结果 |
|---|---|
| `uv run ruff check .` | 0 errors |
| `uv run pytest` | 全部通过（静态层 + fake-env + CLI/report/independence） |
| `uv run libero-rollback validate --dataset dataset` | PASS：a=40 / b=442 / d_native=189 / d_compose_provisional=360 / c=0；1,031 unique case_id；lite 30；0 error / 0 warning |
| `uv run python scripts/validate_dataset.py --dataset dataset` | exit 0（12/12 checks + package validation ok） |
| `uv run python scripts/build_manifest.py --check` | 0 diff |
| `uv run python scripts/build_a_matrix.py --libero-home .cache/libero-src --check` | up to date |
| `uv run python scripts/run_b_matrix.py --dry-run --max-cases 3` | 只写 plan.json，不启动仿真 |
| `uv run libero-rollback run --dry-run --split lite` | 选中 10 个 B case，只写 plan.json |
| `uv run libero-rollback report --run <前序 B run>` | 生成自包含 HTML + aggregate.json |
| `uv run libero-rollback leaderboard validate --run <run>` | 本地提交校验可用 |

**仍未完成（如实）**：真实仿真 episode、真实模型推理、视频编码、D 套件 runner、C/D-compose 数据、C3/C4 脚本 oracle、资产内容 sha256 冻结（ISSUE-5/6/8）。
