# LIBERO Rollback Dataset

> **catalog 状态（2026-10-16）**：`dataset/current` 当前 **288 条**定义（`progress-pulse-*` 24 条已退出，归档于 `archive/pulse-descoped-20261016/`）。用例矩阵以 `docs/case-matrix-current.md` 为准。


这是面向 LIBERO-10 的模型无关 rollback 评测用例数据集。它记录任务中已确认完成的关系被外部干预撤销时，评测器需要重现的场景、状态变化、有效性条件和预期评测语义。仓库交付数据、来源、规范和静态校验工具；不实现恢复算法、控制器、仿真器、模型或实验调度。

首版覆盖 LIBERO-10 的十个基础任务。任务名称、顺序和目标谓词来自 LIBERO-plus 源码中的 `libero/libero/bddl_files/libero_10/tasks_info.txt` 及对应 BDDL 文件；详见 [`dataset/current/sources.yaml`](dataset/current/sources.yaml)。任务 ID `libero_10/00`–`libero_10/09` 按该十项基础清单顺序固定。来源文档中的 `T33`、`T78`、`T133`、`T193` 仅作为来源定位符，不是本数据集的任务 ID。

## 当前数据

catalog 版本 1.0.0 收录四个来源集合的 **288 条 YAML 用例定义**：
two-subtask 129 条、rollback-battery 57 条、reference-object 4 条、progress-failure 98 条。
（2026-10-16 变更：`progress-pulse-*` 24 条退出，归档于 `archive/pulse-descoped-20261016/`；更早退役的 15 条 pose-control 弱姿态集亦不在当前 catalog 内。）
dataset/current/manifest.yaml 是唯一入口；它保留每条 case 原始 dataset_version（1.3.0–1.8.0），并记录来源、文件摘要和 10 项任务覆盖。任务 09 有一条完成边界候选。
新增 progress-failure 是未发布的扩展候选；定义、绑定编译通过和物理验收通过分别统计。运行结果不写入 case 文件。实施和验证进度持续记录在 [docs/implementation-status.md](docs/implementation-status.md)，本轮验证范围和逐任务结果见 [docs/validation-current.md](docs/validation-current.md)。

常用静态检查和报告命令：

~~~bash
uv sync --extra dev
uv run libero-rollback --dataset-root dataset/current validate-dataset
uv run libero-rollback --dataset-root dataset/current check-manifest
uv run pytest
uv run ruff check .
uv run python scripts/build_current_report.py
~~~

HTML 报告输出到 runs/final-report/index.html；JSON 汇总和视频证据在同一目录。报告只聚合已有运行产物，不会启动测试。

每次实验 HTML 报告的统一章节结构、指标口径与视频证据版式（含标准提示词）见 [docs/html-report-prompt.md](docs/html-report-prompt.md)。

新增候选覆盖原生关系边界两侧、已完成位姿探针、恢复后再次失效（repeat）、参照物与成对移动对照、任务完成边界和原生多关系原子重置。候选参数是明确记录的项目构造假设，未测得的可行性不会写成事实。姿态改变后关系仍真、外部复原（当前 catalog 已无此类用例，分类分支保留）、重复协议未完成和碰撞拒绝均单独分类。

- dataset/current/manifest.yaml：版本、案例路径、来源、SHA-256 和版本策略。
- dataset/current/coverage.yaml：LIBERO-10 全部十项任务的覆盖矩阵。
- dataset/current/sources.yaml：任务定义、场景集合和设计资料来源。
- dataset/current/templates.yaml：可复用模板及其状态变化和约束。
- schemas/rollback-case.v1.schema.json：版本化 case schema。
- docs/dataset-card.md：范围、限制、版本与引用。
- docs/schema.md：字段语义与 severity 标签。
- docs/model-integration.md：外部评测器接入契约。
- docs/case-matrix-current.md：逐任务用例矩阵与扩展方向。

## 安装和检查

需要 Python 3.11+ 与 `uv`。默认依赖只有 YAML 读取和 JSON Schema 校验库；测试与代码检查放在开发依赖中。

```bash
uv sync --extra dev
uv run libero-rollback list
uv run libero-rollback validate-case dataset/two-subtask/cases/libero-10-01-black-bowl-drawer-rollback-s1-mid-offset-n3.yaml
uv run libero-rollback validate-dataset
uv run libero-rollback check-manifest
uv run pytest
uv run ruff check .
```

校验器只检查结构、引用、版本、任务覆盖计数和文件摘要，不运行仿真或模型推理。

如果同级环境已经安装 LIBERO、MuJoCo 和外部适配器，可用统一命令实际运行单条或批量用例。桥接层通过
`--python` 指定外部环境，不把大型依赖装入本仓库；它从用例生成一次性 runtime binding，并将结果写入
`runs/`，不会修改用例文件：

```bash
uv run libero-rollback evaluate \
  dataset/two-subtask/cases/libero-10-01-black-bowl-drawer-rollback-s1-mid-offset-n3.yaml \
  --python /path/to/evaluator-env/bin/python \
  --libero-root /path/to/LIBERO-plus \
  --runtime-root /path/to/libero-runtime \
  --model openvla_oft \
  --suite LIBERO_10 \
  --dimension rollback \
  --severity d0 \
  --max-steps 600 \
  --video \
  --checkpoint /path/to/external-checkpoint
```

该命令的运行结果是外部评测记录，不属于数据集 v1；`case_result.json` 用 `case_id` 和
`dataset_version` 关联回不可变用例。未安装外部运行时的环境仍可完整执行本仓库的静态校验和测试。

通过 `--case-id`（可重复）、`--task`（可重复）或 `--all-cases` 选择测试集；也可在命令后传入多个
用例 YAML 路径。批量运行的每个用例单独写入输出子目录，根目录写 `evaluation-summary.json`：

```bash
uv run libero-rollback evaluate --all-cases \
  --python /path/to/evaluator-env/bin/python \
  --libero-root /path/to/LIBERO-plus \
  --runtime-root /path/to/libero-runtime \
  --model openvla_oft --suite LIBERO_10 --dimension rollback \
  --severity d0 --max-steps 600 --video \
  --checkpoint /path/to/external-checkpoint --output runs/full-suite
```

`--suite` 和 `--dimension` 是显式可配置参数；v1 目前只包含 `LIBERO_10` 与 `rollback`，其他值会在
启动外部评测器前拒绝。`--severity` 选择已记录的扰动变体，不会自动生成用例中没有依据的物理参数。
批次退出状态代表所有扰动是否有效执行；模型未完成任务仍会作为有效评测结果记录在摘要和每例结果中。

`severity` 保留来源集合的变换标签。历史标签为 `d0/d1/d2/d3/checkpoint`，来源中的 R01–R05 只放在来源字段；
当前网格还使用 `n3/n5/n8`、`p3/p5/p8/p10`、`r05`、`above`、`articulation`、`pose`、`reference` 和 `boundary`。
`d0` 为恢复 episode 初始位姿，`d1/d2/d3` 为相对初始位姿的不同偏移档位；
`checkpoint` 为恢复捕获的 pregrasp 位姿。这些标签不代表跨任务可比较的恢复难度。
具体向量和参考坐标见 [schema 说明](docs/schema.md)，后续覆盖建议见
[测试集扩展计划](docs/expansion-plan.md)。

OpenPI 的 `pi05`、`pi0` 和 `pi0_fast` 适配器可以使用外部环境中已缓存的默认 checkpoint，
因此统一命令可省略 `--checkpoint`；OpenVLA 等适配器仍必须显式提供 checkpoint。运行时需要指向
包含对应 case template 的已安装 `libero-runtime` checkout。

本地已有同级 `../libero-plus` 时，也可以直接运行 `bash scripts/run_local_validation.sh`；
脚本默认复用其中的 Python 环境和 checkpoint，不下载模型。验证记录见
[`docs/real-validation.md`](docs/real-validation.md)。

## 版本与引用

已发布用例的含义不可静默改变。按数据卡中的版本规则发布新数据集版本；引用时同时注明数据集版本和具体 `case_id`。本仓库目前没有为数据集指定学术论文引用；引用格式见 [`docs/dataset-card.md`](docs/dataset-card.md)。
