# 来源、迁移映射与独立性（Attribution）

> 日期：2026-11-18 ｜ 上位文档：[README.md](../README.md) · [docs/SPEC.md](SPEC.md)
> 本文说明：本仓的数据/代码从哪来、以什么方式进入本仓、为什么运行时**不依赖**任何前序仓，以及如何用命令验证这条边界。
> 迁移项的当前实现进度以 [docs/implementation-status.md](implementation-status.md) 为准（本文只记录映射关系与约束）。

---

## 1. 上游与第三方依赖

| 依赖 | 角色 | 许可 | 本仓处置 |
|---|---|---|---|
| [LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO) | **唯一**外部数据源：BDDL / 官方 init / 仿真资产 | MIT | 只读引用；pin commit `f78abd68…` + 三层校验；资产不入库 |
| robosuite / MuJoCo / bddl / gym / torch | 仿真栈 | 各自上游许可 | 版本 pin 在 `requirements-sim.lock.txt`；只装在仿真环境 |
| OpenPI（π0.5 / π0 / π0-FAST） | 模型推理框架 | 上游许可 | 只做 adapter；权重不入库 |
| OpenVLA-OFT | 模型推理框架 | 上游许可 | 只做 adapter；权重不入库 |
| SmolVLA（LeRobot） | 模型推理框架 | 上游许可 | 只做 adapter；权重不入库 |

不依赖任何 LIBERO 派生数据集（LIBERO-Plus / PRO / MAX 等）；`libero-plus` 只在开发期被借鉴“每模型独立环境 + 资产 pin”的组织方式（见 §2），其代码与资产不进入本仓运行期。

第三方声明汇总见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)；引用见 [CITATION.cff](../CITATION.cff)。

---

## 2. 前序仓的贡献与本仓处置

| 前序仓 | 贡献 | 本仓保留 | 本仓不保留 |
|---|---|---|---|
| `libero-rollback`（数据仓） | case schema、validity/evidence 判定、catalog/coverage/manifest 结构、`restore_*` 机制族、严格恢复率口径 | schema 契约与判定语义（重写为 v2 口径：`schema.py` / `validation.py` / `evidence.py` / `metrics.py`） | 2,112 条旧 catalog、`runs/`、overlay、runtime profile、v1 数字 |
| `libero-compose` | composition 数据生成、B/D case 矩阵、`C0/L0/L1/L2` 注入实现、runner/trace/video、报告契约 | B 矩阵与 D-native 数据（导入冻结）、`perturbation` / `video` / `env` / `policies` / `runner` 的实现语义（去依赖重写） | 运行期 import、任何路径引用、harness 依赖 |
| `libero-plus` | 每模型独立 env、资产 pin、models 目录组织方式 | 只借鉴组织方式（`configs/models.yaml`、`configs/envs/`、`assets/`） | 其代码、模型权重、LIBERO-Plus 数据 |

> 前序仓仅作为**开发期来源与历史证据**。本仓运行期不得 import、不得路径引用它们（SPEC §12，CI 强制）。

---

## 3. Phase 1 迁移映射（copy → rewrite）

| 本仓目标 | 前序来源 | 处理方式 | 进度 |
|---|---|---|---|
| `dataset/matrices/b-matrix.csv` | `libero-compose`：`dataset/case-matrices/b-matrix.csv` | 导入冻结；仅 CRLF→LF；sha256 双记录 | ✅ 见 `dataset/sources.yaml` |
| `dataset/matrices/d-native-matrix.csv` | 同仓 `d-matrix.csv` | 按 `sub == native` 切出，行内容不变 | ✅ |
| `dataset/matrices/d-compose-provisional.csv` | 同仓 `d-matrix.csv` | 按 `sub == compose` 切出；**仅设计占位** | 🟡 不执行 |
| `dataset/matrices/a-matrix.csv` | 本仓生成器 + 上游 BDDL | 由 B 的 40 个任务键生成（指令/目标数逐字来自 BDDL） | ✅ |
| `schemas/rollback-case.v1.schema.json` | `libero-rollback`：`schemas/` | 拷 schema 契约 | ✅ 文件已入仓 |
| `src/libero_rollback/{schema,validation,evidence,metrics}.py` | `libero-rollback`：`src/libero_rollback/*` | 重写为 v2 口径（纯 stdlib + PyYAML + jsonschema） | 🟡 代码已移植，验收以测试为准 |
| `src/libero_rollback/matrices.py` | `libero-compose`：`benchmark/b_matrix.py` | 重写为 B 矩阵加载/校验 | ✅ |
| `src/libero_rollback/runtime/perturbation.py` | `libero-compose`：`benchmark/perturbation.py` | 重写 import，保留 `C0/L0/L1/L2` 语义与门控 | 🟡 |
| `src/libero_rollback/runtime/env.py` | `libero-compose`：`scripts/smoke_env.py` 的 4 个 helper | 只移植必要 helper；改用 `LIBERO_HOME` | 🟡 |
| `src/libero_rollback/runtime/video.py` | `libero-compose`：`harness/video.py` | 移植 | 🟡 |
| `src/libero_rollback/runtime/{triggers,trace}.py` | — | **尚未移植**：D 窗口触发、逐步 GT trace/终点快照 | ⬜ Phase 2 |
| `src/libero_rollback/policies/{pi05,smolvla,openvla_oft}.py` | `libero-compose`：`harness/*_policy.py` | 保留 `reset/predict` 协议，去掉 harness 依赖 | 🟡 |
| `src/libero_rollback/runner.py` + `scripts/run_b_matrix.py` | `libero-compose`：`scripts/run_b_matrix.py` | 拆成 runner + 薄 CLI；`--dry-run` 不启仿真/模型 | 🟡 |
| `scripts/run.sh` | 本仓新增 | 薄封装：默认 dry-run，需 `--execute` | 🟡 |
| `src/libero_rollback/report.py`、`src/libero_rollback/cli.py` | `libero-compose`：`scripts/build_b_report.py` + 模板 | 重写为数据契约驱动 | ⬜ Phase 2 |
| `tests/` | 本仓新增 | 静态契约/数据/运行层测试 | 🟡 |

**迁移纪律**：copy 之后重写实现层，不保留运行期依赖；src 内不得出现前序仓模块名（`libero_rollback` 作为本仓包名除外，前序同名数据仓的 import 被 CI 以正则区分——见 `.github/workflows/ci.yml`）。

---

## 4. 独立性约束（CI 强制）

SPEC §12 与本仓 CI 的硬约束：

1. 静态层（`matrices` / `schema` / `validation` / `evidence` / `metrics` / `report`）只允许 stdlib + PyYAML + jsonschema，**不得** import numpy / torch / mujoco / robosuite / libero；
2. 运行层（`runtime/*`、`policies/*`、`runner.py`）在独立环境安装 LIBERO / MuJoCo / 模型框架；
3. **禁止** `import libero_compose` / `import libero_runtime` / 引用前序 `libero_rollback` 数据仓；禁止依赖其 `runs/`、overlay、runtime profile；
4. `dataset/` 内不得出现绝对主机路径；`src/`、`scripts/`、`tests/` 内不得出现主机绝对路径字面量；
5. 每个 run 的 `provenance.json` 记录本仓 git sha、LIBERO commit/worktree、asset digest、模型 ckpt sha、`pip freeze` 摘要、环境变量与完整 argv。

复核命令（本地等价于 CI）：

```bash
# 1) 前序仓 import（期望：无输出）
grep -RInE "^(import|from) (libero_compose|libero_runtime|libero_rollback\b)" src scripts tests

# 2) dataset/ 路径卫生 + 来源/计数/sha256 校验（期望：PASS，0 error）
uv run libero-rollback validate --dataset dataset

# 3) 源码路径卫生 + 独立性测试
uv run pytest tests/test_independence.py

# 4) CI 全套
uv run ruff check . && uv run pytest
```

> 当前仓库状态（2026-11-18 复核）：命令 1、2、3、4 的路径卫生与独立性部分均通过（`tests/test_independence.py` 已对“检测器文件”豁免，`validation.py` 不再包含裸路径字面量）；`ruff check .` 仍有 6 个非路径类告警，见 [implementation-status.md](implementation-status.md) 的 ISSUE-1。

---

## 5. 历史证据与引用边界

- 前序仓的 v1 实验数字（40/40、2/49、12/300、0/76、42/477 等）只作**动机引用与现象证据**，见 README §2；不得与本仓 v2 主表混排（README §10.3）。
- 本仓不复制前序仓的 `runs/`、视频、报告产物；它们不作为本仓证据。
- 任何在论文/报告中引用的结果，必须来自本仓 runner 的 `episodes.jsonl` / `summary.json` / `provenance.json`，并带数据集版本。

---

## 6. 致谢与引用

- 感谢 LIBERO 作者提供基准与仿真资产（MIT）：Liu et al., *LIBERO: Benchmarking Knowledge Transfer for Lifelong Robot Learning*, arXiv:2306.03310。
- 本仓的 case 语义、注入协议与报告契约在内部前序仓中孵化（`libero-rollback` / `libero-compose`），v2.0 将其必要部分 copy 并重写实现层。
- 引用本仓请使用 [CITATION.cff](../CITATION.cff)；同时引用上游 LIBERO。

---

## 7. 如何报告来源问题

若发现：
- 某文件实际来源与本文/`dataset/sources.yaml` 不符；
- 本仓代码仍隐式依赖前序仓或主机路径；
- 上游 LIBERO 资产与 pin 不一致；

请附上 `dataset/sources.yaml` 相关条目、`git rev-parse HEAD`、`scripts/verify_libero.py` 输出与最小复现命令提 issue。**不要**用“改哈希”或“关掉检查”的方式让 CI 变绿。
