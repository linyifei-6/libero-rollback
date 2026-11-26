<!--
  标准实验报告模板 · experiment-report-v1.0 · Markdown 版
  ---------------------------------------------------------------------------
  用途：任意一次 LIBERO-Rollback 实验（A/B/C/D 任一矩阵、任一模型）的正式报告。
  配套：experiment-report.html（同结构、同 token、同口径）与 experiment-report.README.md（规范）。
  约定：
    * 占位符 = 双花括号之间写全大写名称；由生成器/填写者替换为文本，表格类必须替换为**完整表格**
                      （含表头与分隔行），模板只保留章节与说明。
    * <!-- ... -->   填写说明，渲染后不可见，发布前可整体删除。
    * 所有数字必须来自 aggregate.json / summary.json，不得手算、不得改写。
  红线（与 README 第 5 节一致）：
    1. Recovery 分母 = 注入有效且非 C0；C0、注入无效、触发未到达都不进分母；
    2. 不可触发记 N/A，不是 0%；N/A 必须单独计数；
    3. restorable oracle ≠ 策略恢复，不进恢复分子；
    4. 每个率给 Wilson 95% CI 与 k/N；
    5. 分母为 0 写 N/A，不得显示 0.0%；
    6. 页面/KPI/表/aggregate.json 数字必须一致；
    7. 报告内不得出现主机绝对路径与用户名。
-->

<!-- 例：# 实验报告：pi05 · B 矩阵 · 完成边界回滚（标题整串由 TITLE 提供） -->
# {{TITLE}}

**{{SUBTITLE}}**

> 报告 ID：`{{REPORT_ID}}` ｜ 模板：`{{TEMPLATE_VERSION}}` ｜ 生成时间：{{GENERATED_AT}} ｜ 状态：{{STATUS}}
> 模型：`{{MODEL}}` ｜ checkpoint：`{{CHECKPOINT}}`
> 矩阵：`{{MATRIX_PATH}}`（sha256 `{{MATRIX_SHA256}}`，冻结日 {{MATRIX_FROZEN_AT}}）
> 运行目录：`{{RUN_DIR}}` ｜ 协议：{{PROTOCOL_ONE_LINE}}
> 覆盖范围：{{SCOPE}} ｜ 实验类型：{{EXPERIMENT_KIND}} ｜ 报告性质：{{REPORT_KIND}} ｜ 证据等级：{{EVIDENCE_TIER}} ｜ 种子：{{SEED}} ｜ init_row：{{INIT_ROW}}

## 0. 摘要

<!-- 3–5 条，每条 = 结论 + 数字(k/N) + CI；先给结论再给口径。禁止出现无分母的百分数。 -->

{{SUMMARY_BULLETS}}

> **一句话**：{{ONE_LINE_VERDICT}}

{{MISREADING_WARNING}}

## 1. 实验问题与预注册判据

<!-- 判据必须在跑之前写死；跑完再补判据等于没有判据。若本轮改了判据，必须在第 12 节变更记录里写明。 -->

{{RQ_TABLE}}

## 2. 实验设计

### 2.1 用例集与矩阵

{{MATRIX_TABLE}}

{{MATRIX_NOTES}}

### 2.2 实验臂与对照

<!-- 每个 arm 一行：arm 名、含义、case 数、注入 level、是否 C0 对照、是否进 Recovery 分母。 -->

{{ARM_TABLE}}

### 2.3 触发与注入协议

{{TRIGGER_SPEC}}

### 2.4 运行参数

{{RUN_PARAMS_TABLE}}

### 2.5 模型与环境

{{ENV_TABLE}}

## 3. 执行与覆盖

<!-- 应跑 / 完成 / 失败 / N/A 必须能对上用例总数；对不上就写清差在哪。 -->

{{COVERAGE_TABLE}}

{{COVERAGE_NOTES}}

## 4. 指标定义与口径

{{METRIC_DEF_TABLE}}

### 4.1 口径红线

1. **Recovery 分母 = 注入有效且非 C0**；C0 对照、注入无效、触发未到达一律不进分母。
2. **不可触发 = `N/A`，不是 0%**；N/A 单独计数并进表格与结论。
3. **`restorable` oracle 只证明几何可修**，不等于策略自修复，不进恢复分子。
4. 每个率给 **Wilson 95% CI** 与 `k/N`；`N/A` / 分母为 0 时不得显示百分比。
5. 数字只从 `aggregate.json` 取；页面、表格、KPI、JSON 四处必须一致。
6. 不同协议（`max_steps`/`repair_window`/`stop_on_recovery`/`replan`）的 suite **不可直接横比**；
   必须横比时写成"描述性合并"并标注协议差异。

## 5. 结果

### 5.1 总体

{{KPI_TABLE}}

### 5.2 分 suite

{{SUITE_TABLE}}

### 5.3 分注入 level（剂量-效应）

{{LEVEL_TABLE}}

{{LEVEL_BARS}}

### 5.4 控制臂（C0）

{{CONTROL_TABLE}}

### 5.5 verdict 分布

{{VERDICT_TABLE}}

### 5.6 分 task（可选）

<!-- 只在与其它模型/其它轮次逐 task 对照时才需要；单轮报告可整节删除。 -->

{{TASK_TABLE}}

### 5.7 配对对照（可选）

<!-- McNemar / 逐 case 配对；必须说明配对单位与"仅两边都 valid"的过滤规则。 -->

{{PAIRED_TABLE}}

## 6. 失败模式分析

<!-- 四类分开数：触发未达(trigger_not_reached) / 注入无效(injection_invalid) /
     有效但未恢复(valid_not_recovered) / 未完成(incomplete)。四类之和必须等于总数减恢复数。 -->

{{FAILURE_TABLE}}

{{FAILURE_CASES}}

## 7. 讨论

{{DISCUSSION}}

## 8. 局限

{{LIMITATIONS}}

## 9. 结论

<!-- 编号列出，每条标注证据强度：强（多 seed / 大 N / 配对）/ 中 / 弱（单 seed、小 N、描述性）。 -->

{{CONCLUSIONS}}

## 10. 复现

```bash
{{REPRO_COMMANDS}}
```

{{REPRO_NOTES}}

## 11. 证据清单

{{EVIDENCE_TABLE}}

{{PROVENANCE_NOTE}}

## 12. 变更记录

{{CHANGELOG_TABLE}}
