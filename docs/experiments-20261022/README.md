# 2026-10-22 任务扩展实验（数据与目录留存）

原始实验目录：`runs/expand-tasks-20261022/`（results/videos/traces 都在那里）。

> **报告已合并**：两次多 seed 实验（原始 45 ordered + 反向 45 ordered + 8 个新 goal 候选）已整合为一份总报告：
> `runs/report-90-combos-newgoal-20261023/report/index.html`（模板 `docs/html-report-prompt.md` v1.2，浅色主题）。
> 旧的 `REPORT.md`、`report/` HTML 报告、单文件版、docs 报告副本已按要求删除，仅保留这份总报告与原始运行数据。

本目录保留的数据：

- `data/expansion-summary.json/.md`：实验 1/3 的逐 episode 结果（dependency-pairs / longbudget / hint-upfront / hint-progress / longbudget2）。
- `data/slot-screen-summary.json/.md`：45 个槽位替换候选的 pi05 seed-0 筛选结果。
- `data/controls-summary.json/.md`：12 个单子任务控制 + 6 个原始任务顺序交换变体结果。
- `data/slot-confirm-summary.json/.md`：2 个 survivor 的 seeds 1,2 复核。
- `data/slot-substitution/`：45 候选的 catalog / static-validation / REPORT。
- `data/controls/`：control/order 变体 catalog / static-validation。
- `dependency-cases/`：依赖组合 case 目录（CASE_CATALOG.md / cases.json / 生成脚本）。

说明：本实验不是 rollback 扰动实验；总报告的维度口径（batch/group/seed/outcome）与各章节的模板适配说明见报告 §1.3 与 §5.5。
