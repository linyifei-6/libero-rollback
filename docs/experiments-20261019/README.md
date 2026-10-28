# experiments-20261019 数据说明

本目录是 2026-10-19 会话实验的**幸存数据留存**（原始 `runs/` 目录在事故中被删除，恢复重跑已按用户要求停止）。

| 文件 | 说明 |
|---|---|
| `baseline_pi05_4suite.json` | 标准 LIBERO 四套件 pi05 baseline：官方 prompt pass 40 条 episode 明细 + per-suite 统计；BDDL-prompt pass 的幸存 23 条 episode + 全套 per-suite 统计；两 pass 对照；协议/manifest；审计 verdict。来源：`.tmp/std-baseline-audit/` |
| `combined_twosubtask.json` | 组合双子任务实验：67 条 episode 明细（含 run/bddl/instruction/success/steps/time_s/subtasks/first_true_step/switch_step）、8 个 run 统计、静态产物计数、结论、审计 verdict。来源：`.tmp/combined-audit/` |
| `goal_pair_catalog.json` | 45 对 GOAL 组合任务目录（由事故后重新生成的 bddl + 审计分类重建） |
| `object_pair_catalog.json` | OBJECT 组合方法与审计口径统计；**精确 30 对选择清单随原 pairs.json 丢失，本文件不包含伪造的 pair 列表** |
| `recovered-artifacts/goal-pairs/` | 事故后完整恢复并验证的 GOAL 45 对静态产物（45 bddl + 45 init + pairs.json/pairs.md/static-validation.json/REPORT.md/checksums，45/45 通过） |
| `libero_std_task_spec.json` | 标准 40 个 base 任务的机读 spec（来源：`.tmp/std-baseline-audit/spec.json`） |
| `audit/` | 幸存审计报告/证据 JSON/审计脚本副本（权威数字来源） |

注意：本目录所有数字来自独立审计的复算；原始 videos/traces/results 不可找回。引用限定见 `docs/libero-experiments-20261019.md`。
