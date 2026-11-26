# 标准实验报告模板规范 v1（`experiment-report-v1.0`）

> 适用对象：**任意一次** LIBERO-Rollback 实验的正式结果报告——A/B/C/D 任一矩阵、任一模型、
> 单次运行或多 run 汇总。
>
> 本规范同时约束两份模板：
> - [`experiment-report.md`](experiment-report.md)：Markdown 版（进仓库、可 review、可 diff）；
> - [`experiment-report.html`](experiment-report.html)：HTML 版（自包含、白底、`file://` 双击可开）。
>
> 两者**章节顺序、token 名称、数字口径完全一致**，同一份 `aggregate.json` 必须能填出两份。
> 唯一例外：HTML 的 `STATUS_CLASS` 是纯展示 token（徽标配色），Markdown 版不需要。
>
> 与其它模板的分工：
>
> | 模板 | 回答什么 | 粒度 |
> |---|---|---|
> | 本模板 `experiment-report-v1.0` | 这次实验**结论是什么**、数字可信到什么程度 | 一轮实验 |
> | [`review-report-v1.0`](README.md) | 逐 case **注入/恢复是否真实有效**（人工审核台账） | 每个 case |
> | [`b-plus-progress`](b-plus-progress.README.md) | 单次跑批的**进度与可播放证据**（KPI + 视频网格） | 每个 case 的视频 |

---

## 1. 生成方式（目标形态）

```bash
# 1) 跑实验（CLI，拒绝一次性脚本）
libero-rollback run --matrix dataset/matrices/libero-rollback/completion-rollback.csv \
  --model pi05 --output runs/<run-id> --seed 0 --init-row 0 --max-steps 600

# 2) 出聚合（写 aggregate.json / SUMMARY.md / index.html）
libero-rollback report --run runs/<run-id> --out experiments/<report-dir>

# 3) 填标准报告（当前：按本文 token 表填写；目标：report 命令加 --template）
```

产物命名固定为 `<report-dir>/`：

```text
<report-dir>/
├── experiment-report.md      # 本模板填充结果（进仓库）
├── experiment-report.html    # 本模板填充结果（自包含）
├── aggregate.json            # 唯一数字来源
├── provenance.json           # 生成命令、矩阵 sha256、artifact 哈希
└── cases.jsonl               # 逐 case 投影（可选，供复核）
```

---

## 2. Token 契约

替换规则：

- 占位符（双花括号 + 全大写名称）一律**全部匹配**替换，不许残留未替换的占位符；
- 以 `_TABLE` 结尾的 token 必须是**完整表格**：HTML 版为 `<table class="dt">…</table>`
  （含 `<thead>`/`<tbody>`），Markdown 版为含表头与分隔行的完整表格块；
- `_BARS` / `_BULLETS` / `_NOTES` / `_CASES` / `_COMMANDS` / `_VERDICT` / `_WARNING` 允许内联 HTML/Markdown 片段；
- 取不到的字段写 `未记录`，**不得推测、不得补零**。

### 2.1 页头与元数据

| token | 必需 | 来源 | 说明 |
|---|---|---|---|
| `TITLE` | ✅ | 人工 | 报告主标题：模型 · 矩阵 · 实验类型 |
| `SUBTITLE` | ✅ | 人工 | 一句话副标题，含核心数字 |
| `MODEL` | ✅ | `run.policy` | 模型 id（如 `pi05`） |
| `SCOPE` | ✅ | `matrix` | 覆盖的 suite/task 范围 |
| `EXPERIMENT_KIND` | ✅ | 人工 | 如 `完成边界回滚` / `执行中回滚` / `无扰动基线` |
| `REPORT_ID` | ✅ | 生成器 | 稳定 ID（如 `er-<12 hex>`） |
| `TEMPLATE_VERSION` | ✅ | 常量 | `experiment-report-v1.0` |
| `GENERATED_AT` | ✅ | 生成器 | ISO-8601 带时区 |
| `STATUS` | ✅ | 人工 | `完成` / `部分完成` / `dry-run` |
| `STATUS_CLASS` | HTML 必需 | 人工 | 徽标配色 `ok` / `warn` / `na`；纯展示，不参与两版一致性校验 |
| `CHECKPOINT` | ✅ | `run.checkpoint` | 只记录路径标识，**不得写入主机绝对路径** |
| `MATRIX_PATH` / `MATRIX_SHA256` / `MATRIX_FROZEN_AT` | ✅ | `matrix` | 仓内相对路径 + sha256 前 12 位 + 冻结日 |
| `RUN_DIR` | ✅ | `run.dir` | 仓内相对标记（如 `runs/<run-id>`） |
| `PROTOCOL_ONE_LINE` | ✅ | `run.*` | `max_steps/trigger/delay/replan/camera/seed/init_row` 单行摘要 |
| `REPORT_KIND` | ✅ | 人工 | `单次运行` / `多 run 汇总`（汇总必须列出各 run） |
| `EVIDENCE_TIER` | ✅ | 人工 | `E1 单跑` / `E2 多 seed` / `E3 多模型或配对` |
| `SEED` / `INIT_ROW` | ✅ | `run.seed` / `run.init_row` | 单 seed 必须在局限里点明 |

> 旧元数据拼接片段已取消：元数据统一由上面这组显式 token 渲染，两版模板共用同一组字段。

### 2.2 摘要与判据

| token | 必需 | 说明 |
|---|---|---|
| `SUMMARY_BULLETS` | ✅ | 3–5 条，每条 `结论 + k/N + % + Wilson CI`；禁止无分母百分数 |
| `ONE_LINE_VERDICT` | ✅ | 一句话总判断，必须能被第 9 节结论复述 |
| `MISREADING_WARNING` | ✅ | 「不要这样读」提示块；单 seed / 不可横比 / N/A≠0% 至少写一条 |
| `RQ_TABLE` | ✅ | 列：`编号｜研究问题｜判据（什么算支持）｜结果｜结论` |

### 2.3 设计、执行与口径

| token | 必需 | 说明 |
|---|---|---|
| `MATRIX_TABLE` | ✅ | 列：`suite｜来源（仓内路径）｜cases｜level 分布｜sha256｜冻结日` |
| `MATRIX_NOTES` | 可选 | 排除项、same-object conflict 剔除等说明 |
| `ARM_TABLE` | ✅ | 列：`arm｜含义｜cases｜注入 level｜是否 C0｜进 Recovery 分母` |
| `TRIGGER_SPEC` | ✅ | 触发语义（`all_done` + delay）、level 定义、**5 个注入硬门控**清单 |
| `RUN_PARAMS_TABLE` | ✅ | 列：`参数｜值｜来源（run-manifest.json / 人工）`；至少 `max_steps, delay_steps, repair_window, replan, camera, settle_steps, stop_on_recovery, seed, init_row, video_fps` |
| `ENV_TABLE` | ✅ | 列：`项｜值`；至少 模型、checkpoint、解释器与版本、框架（JAX/torch）、机器与并发、确定性设置 |
| `COVERAGE_TABLE` | ✅ | 列：`suite｜应跑｜完成｜失败｜N/A｜完成率`；合计必须等于用例总数 |
| `COVERAGE_NOTES` | 可选 | 缺口原因、断点续跑、耗时 |
| `METRIC_DEF_TABLE` | ✅ | 列：`指标｜定义｜分子｜分母｜N/A 规则`；至少 Recovery、trigger_rate、valid_rate、control_rate、SR |

### 2.4 结果

| token | 必需 | 说明 |
|---|---|---|
| `KPI_TABLE` | ✅ | 列：`指标｜k/N｜比率｜Wilson 95% CI｜N/A｜备注`；至少 Recovery、trigger、valid、C0、SR、zero-progress |
| `SUITE_TABLE` | ✅ | 列：`suite｜cases｜trigger k/N｜valid k/N｜recovery k/N｜%｜CI｜control｜备注` |
| `LEVEL_TABLE` | ✅ | 列：`level｜cases｜valid｜recovery k/N｜%｜CI` |
| `LEVEL_BARS` | ✅ | 与 `LEVEL_TABLE` 同数据的横向条形（不得引入表外数字） |
| `CONTROL_TABLE` | ✅ | 列：`arm｜cases｜success k/N｜control_rate｜说明`；C0 不进 Recovery |
| `VERDICT_TABLE` | ✅ | 列：`verdict｜含义｜n｜占比｜进 Recovery 分母`；六类 verdict 逐一列出，0 也要列 |
| `TASK_TABLE` | 可选 | 列：`task｜cases｜recovery k/N｜%｜CI｜备注`；单轮报告可整节省略 |
| `PAIRED_TABLE` | 可选 | 列：`对照｜配对单位｜n_pairs｜a-only｜b-only｜McNemar p｜结论`；必须写明过滤规则 |

### 2.5 解释与证据

| token | 必需 | 说明 |
|---|---|---|
| `FAILURE_TABLE` | ✅ | 列：`类别｜n｜占 cases｜典型原因｜是否计入模型失败`；四类之和 = 总数 − 恢复数 |
| `FAILURE_CASES` | 可选 | 典型 case 列表（`case_id` + 一句现象）；不得贴视频本地路径 |
| `DISCUSSION` | ✅ | 与先前结果的一致性、替代解释、机制解释 |
| `LIMITATIONS` | ✅ | 单 seed / 单 init_row / 模型版本 / 协议不可横比 / 覆盖缺口 |
| `CONCLUSIONS` | ✅ | 编号结论，每条标注证据强度（强/中/弱） |
| `REPRO_COMMANDS` | ✅ | 只允许 CLI 命令（`libero-rollback run/report/list/validate`），**不得出现一次性脚本调用** |
| `REPRO_NOTES` | 可选 | 环境变量、矩阵来源、随机性说明 |
| `EVIDENCE_TABLE` | ✅ | 列：`文件｜内容｜sha256`；至少 `aggregate.json`、`provenance.json`、`cases.jsonl`、本报告两份 |
| `PROVENANCE_NOTE` | 可选 | `provenance.json` 的生成命令与时间 |
| `CHANGELOG_TABLE` | ✅ | 列：`版本｜日期｜变更｜影响`；判据或口径改动必须在此声明 |

---

## 3. 数据契约：`aggregate.json`

由 `libero-rollback report` 写出（`src/libero_rollback/report.py::build_aggregate`）。**报告里的每个数字都必须能在这里找到**。

```jsonc
{
  "schema_version": 1,
  "generator": "libero-rollback <version>",
  "run":      { "dir", "mode", "matrix", "policy", "checkpoint", "config_name",
                "init_row", "seed", "max_steps", "delay_steps", "repair_window", "video" },
  "matrix":   { "source", "sha256", "cases", "..." },
  "episodes": 180,
  "recovery": Rate, "control": Rate, "trigger": Rate, "success": Rate,
  "progress": {...}, "pp": Rate, "zero_progress": Rate, "one_and_done": Rate,
  "pending_preservation": Rate, "mean_pending_preservation": number,
  "terminal_states": {...},
  "by_verdict": { "<verdict>": n },
  "by_suite": { "<suite>": <group summary> },
  "by_level": { "<level>": <group summary> },
  "cases":    [ { "case_id", "suite", "level", "target", "status", "trigger_reached",
                  "case_valid", "verdict", "recovered", "relation_before",
                  "relation_after_injection", "relation_final", "steps",
                  "repair_budget_steps", "delta_translation_m", "delta_angle_rad", "video" } ]
}
```

`Rate` 对象（`src/libero_rollback/metrics.py::Rate.as_dict`）：

```jsonc
{ "numerator": 12, "denominator": 66, "value": 0.1818, "ci": [0.1071, 0.2909], "na": false }
```

渲染规则：

- `na == true` → 输出 `N/A`（含分数列），**不得**输出 `0.0%`；
- `ci == null` 且 `na == false` → 只输出比率，不编造区间（正常不会出现）；
- 百分数统一两位以内小数（推荐 1 位），CI 用 `[lo, hi]` 百分数形式；
- 分母为 0 时 `numerator`/`denominator` 均按 `0/0` 处理，表格写 `N/A`。

`<group summary>`（`_group_summary`）字段：
`cases, by_verdict, recovery, control, trigger, success, progress, pp, zero_progress, one_and_done, pending_preservation, mean_pending_preservation, terminal_states`。

---

## 4. 数字口径（红线）

1. **Recovery 分母 = 注入有效且非 C0**；C0、注入无效、触发未到达都不进分母。
2. **不可触发 = `N/A`，不是 0%**；N/A 单独计数并进表格与结论。
3. **`restorable` oracle ≠ 策略恢复**，不进恢复分子。
4. 每个率给 **Wilson 95% CI** 与 `k/N`；分母为 0 写 `N/A`。
5. 页面 KPI、各表、正文、`aggregate.json` 四处数字必须一致。
6. 协议不同的 suite **不可直接横比**；必须横比时标注为"描述性合并"。
7. 报告内 **0 处主机绝对路径与用户名**（自检项见第 5 节）。

---

## 5. 验收清单

生成后逐项勾（多数可用文本检索验证）：

- [ ] 两份模板的**章节数与顺序**一致（0–12 共 13 节）；
- [ ] 全文无残留 `{{` / `}}`；
- [ ] `TITLE / MODEL / SCOPE / REPORT_ID / TEMPLATE_VERSION / GENERATED_AT` 均非空且非占位值；
- [ ] 页头含矩阵 sha256、seed、init_row、协议单行摘要；
- [ ] 摘要 3–5 条，每条都有 `k/N` 与 CI；无"无分母百分数"；
- [ ] 口径红线（第 4 节 7 条）在报告正文中可见（HTML 版为固定块）；
- [ ] `KPI_TABLE` 与 `aggregate.json` 的 `recovery` / `control` / `trigger` / `success` 完全一致；
- [ ] `SUITE_TABLE`、`LEVEL_TABLE`、`LEVEL_BARS` 三处数字互相一致且与 `by_suite`/`by_level` 一致；
- [ ] `VERDICT_TABLE` 列出全部 verdict（含 0 值行），合计 = `episodes`；
- [ ] `FAILURE_TABLE` 四类之和 = `episodes − recovery.numerator`；
- [ ] 所有 `N/A` 都显示为 `N/A`，没有 `0.0%` 伪装；
- [ ] `REPRO_COMMANDS` 只用 CLI，无 `bash scripts/xxx.sh` 这类一次性脚本；
- [ ] `EVIDENCE_TABLE` 的 sha256 与实际文件匹配；
- [ ] HTML 自检：`background:#ffffff` 存在；无 `http://`、`https://`、`<link`、`<script src`、`prefers-color-scheme:dark`；`lang="zh-CN"`、`<meta charset="utf-8">` 存在；`file://` 双击可开；
- [ ] HTML 左侧 sticky 导航 13 个章节链接全部可跳转，无死锚点；
- [ ] 报告文件内 0 处 `/home/`、`C:\`、用户名。

---

## 6. 版本历史

| 版本 | 日期 | 变更 |
|---|---|---|
| `experiment-report-v1.0` | 2026-11-26 | 首版：13 节标准结构；MD + HTML 双模板；token 契约 33 项；与 `aggregate.json` 对齐；CLI-only 复现；口径红线与验收清单 |

## 7. 已知限制

- 目前需按 token 表手工/半自动填充；`libero-rollback report --template` 尚未实现，是本模板的落地目标；
- 模板不承担逐 case 审核职责（那是 `review-report-v1.0` 的职责）；
- 单 run 报告天然是单 seed/单 init_row，模板只能**声明**该局限，不能消除它。
