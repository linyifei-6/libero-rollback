# pi05 验证报告：100 个 LIBERO-OBJECT 场景内双抓取候选（3 seeds, max_steps=600）

- 生成时间：2026-10-24T10:14:29
- episodes：300；success：0（0.0%）
- seeds：[0, 1, 2]；max_steps=600；replan_steps=10
- 至少 1 seed 成功候选：0/100；3 seeds 全成功候选：0/100
- 失败时完成子任务数分布：{'0': 10, '1': 290}

## 1. 按 instruction 顺序

| order | episodes | success | rate |
|---|---|---|---|
| ab | 150 | 0 | 0.0% |
| ba | 150 | 0 | 0.0% |

## 2. 按场景任务

| scene | episodes | success | rate |
|---|---|---|---|
| T0 | 30 | 0 | 0.0% |
| T1 | 30 | 0 | 0.0% |
| T2 | 30 | 0 | 0.0% |
| T3 | 30 | 0 | 0.0% |
| T4 | 30 | 0 | 0.0% |
| T5 | 30 | 0 | 0.0% |
| T6 | 30 | 0 | 0.0% |
| T7 | 30 | 0 | 0.0% |
| T8 | 30 | 0 | 0.0% |
| T9 | 30 | 0 | 0.0% |

## 3. 按提升目标 B

| B | episodes | success | rate |
|---|---|---|---|
| alphabet_soup | 30 | 0 | 0.0% |
| bbq_sauce | 30 | 0 | 0.0% |
| butter | 30 | 0 | 0.0% |
| chocolate_pudding | 30 | 0 | 0.0% |
| cream_cheese | 30 | 0 | 0.0% |
| ketchup | 30 | 0 | 0.0% |
| milk | 30 | 0 | 0.0% |
| orange_juice | 30 | 0 | 0.0% |
| salad_dressing | 30 | 0 | 0.0% |
| tomato_sauce | 30 | 0 | 0.0% |

## 4. 逐候选 3-seed 结果

| candidate_id | A | B | order | seeds | success | steps (seed0/1/2) | subtasks done |
|---|---|---|---|---|---|---|---|
| `t00_b_salad_dressing_ab` | alphabet_soup | salad_dressing | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t00_b_salad_dressing_ba` | alphabet_soup | salad_dressing | ba | [] | 0/3 | 600/600/600 | 1/1/0 |
| `t00_b_cream_cheese_ab` | alphabet_soup | cream_cheese | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t00_b_cream_cheese_ba` | alphabet_soup | cream_cheese | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t00_b_milk_ab` | alphabet_soup | milk | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t00_b_milk_ba` | alphabet_soup | milk | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t00_b_tomato_sauce_ab` | alphabet_soup | tomato_sauce | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t00_b_tomato_sauce_ba` | alphabet_soup | tomato_sauce | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t00_b_butter_ab` | alphabet_soup | butter | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t00_b_butter_ba` | alphabet_soup | butter | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t01_b_alphabet_soup_ab` | cream_cheese | alphabet_soup | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t01_b_alphabet_soup_ba` | cream_cheese | alphabet_soup | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t01_b_milk_ab` | cream_cheese | milk | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t01_b_milk_ba` | cream_cheese | milk | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t01_b_tomato_sauce_ab` | cream_cheese | tomato_sauce | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t01_b_tomato_sauce_ba` | cream_cheese | tomato_sauce | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t01_b_butter_ab` | cream_cheese | butter | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t01_b_butter_ba` | cream_cheese | butter | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t01_b_orange_juice_ab` | cream_cheese | orange_juice | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t01_b_orange_juice_ba` | cream_cheese | orange_juice | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t02_b_ketchup_ab` | salad_dressing | ketchup | ab | [] | 0/3 | 600/600/600 | 0/1/1 |
| `t02_b_ketchup_ba` | salad_dressing | ketchup | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t02_b_alphabet_soup_ab` | salad_dressing | alphabet_soup | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t02_b_alphabet_soup_ba` | salad_dressing | alphabet_soup | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t02_b_cream_cheese_ab` | salad_dressing | cream_cheese | ab | [] | 0/3 | 600/600/600 | 1/1/0 |
| `t02_b_cream_cheese_ba` | salad_dressing | cream_cheese | ba | [] | 0/3 | 600/600/600 | 0/1/1 |
| `t02_b_milk_ab` | salad_dressing | milk | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t02_b_milk_ba` | salad_dressing | milk | ba | [] | 0/3 | 600/600/600 | 0/1/1 |
| `t02_b_tomato_sauce_ab` | salad_dressing | tomato_sauce | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t02_b_tomato_sauce_ba` | salad_dressing | tomato_sauce | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t03_b_chocolate_pudding_ab` | bbq_sauce | chocolate_pudding | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t03_b_chocolate_pudding_ba` | bbq_sauce | chocolate_pudding | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t03_b_ketchup_ab` | bbq_sauce | ketchup | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t03_b_ketchup_ba` | bbq_sauce | ketchup | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t03_b_salad_dressing_ab` | bbq_sauce | salad_dressing | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t03_b_salad_dressing_ba` | bbq_sauce | salad_dressing | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t03_b_alphabet_soup_ab` | bbq_sauce | alphabet_soup | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t03_b_alphabet_soup_ba` | bbq_sauce | alphabet_soup | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t03_b_cream_cheese_ab` | bbq_sauce | cream_cheese | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t03_b_cream_cheese_ba` | bbq_sauce | cream_cheese | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t04_b_bbq_sauce_ab` | ketchup | bbq_sauce | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t04_b_bbq_sauce_ba` | ketchup | bbq_sauce | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t04_b_salad_dressing_ab` | ketchup | salad_dressing | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t04_b_salad_dressing_ba` | ketchup | salad_dressing | ba | [] | 0/3 | 600/600/600 | 1/0/1 |
| `t04_b_alphabet_soup_ab` | ketchup | alphabet_soup | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t04_b_alphabet_soup_ba` | ketchup | alphabet_soup | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t04_b_cream_cheese_ab` | ketchup | cream_cheese | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t04_b_cream_cheese_ba` | ketchup | cream_cheese | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t04_b_milk_ab` | ketchup | milk | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t04_b_milk_ba` | ketchup | milk | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t05_b_milk_ab` | tomato_sauce | milk | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t05_b_milk_ba` | tomato_sauce | milk | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t05_b_butter_ab` | tomato_sauce | butter | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t05_b_butter_ba` | tomato_sauce | butter | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t05_b_orange_juice_ab` | tomato_sauce | orange_juice | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t05_b_orange_juice_ba` | tomato_sauce | orange_juice | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t05_b_chocolate_pudding_ab` | tomato_sauce | chocolate_pudding | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t05_b_chocolate_pudding_ba` | tomato_sauce | chocolate_pudding | ba | [] | 0/3 | 600/600/600 | 0/1/1 |
| `t05_b_bbq_sauce_ab` | tomato_sauce | bbq_sauce | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t05_b_bbq_sauce_ba` | tomato_sauce | bbq_sauce | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t06_b_tomato_sauce_ab` | butter | tomato_sauce | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t06_b_tomato_sauce_ba` | butter | tomato_sauce | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t06_b_orange_juice_ab` | butter | orange_juice | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t06_b_orange_juice_ba` | butter | orange_juice | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t06_b_chocolate_pudding_ab` | butter | chocolate_pudding | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t06_b_chocolate_pudding_ba` | butter | chocolate_pudding | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t06_b_bbq_sauce_ab` | butter | bbq_sauce | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t06_b_bbq_sauce_ba` | butter | bbq_sauce | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t06_b_ketchup_ab` | butter | ketchup | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t06_b_ketchup_ba` | butter | ketchup | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t07_b_cream_cheese_ab` | milk | cream_cheese | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t07_b_cream_cheese_ba` | milk | cream_cheese | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t07_b_tomato_sauce_ab` | milk | tomato_sauce | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t07_b_tomato_sauce_ba` | milk | tomato_sauce | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t07_b_butter_ab` | milk | butter | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t07_b_butter_ba` | milk | butter | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t07_b_orange_juice_ab` | milk | orange_juice | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t07_b_orange_juice_ba` | milk | orange_juice | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t07_b_chocolate_pudding_ab` | milk | chocolate_pudding | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t07_b_chocolate_pudding_ba` | milk | chocolate_pudding | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t08_b_orange_juice_ab` | chocolate_pudding | orange_juice | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t08_b_orange_juice_ba` | chocolate_pudding | orange_juice | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t08_b_bbq_sauce_ab` | chocolate_pudding | bbq_sauce | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t08_b_bbq_sauce_ba` | chocolate_pudding | bbq_sauce | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t08_b_ketchup_ab` | chocolate_pudding | ketchup | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t08_b_ketchup_ba` | chocolate_pudding | ketchup | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t08_b_salad_dressing_ab` | chocolate_pudding | salad_dressing | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t08_b_salad_dressing_ba` | chocolate_pudding | salad_dressing | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t08_b_alphabet_soup_ab` | chocolate_pudding | alphabet_soup | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t08_b_alphabet_soup_ba` | chocolate_pudding | alphabet_soup | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t09_b_butter_ab` | orange_juice | butter | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t09_b_butter_ba` | orange_juice | butter | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t09_b_chocolate_pudding_ab` | orange_juice | chocolate_pudding | ab | [] | 0/3 | 600/600/600 | 0/1/1 |
| `t09_b_chocolate_pudding_ba` | orange_juice | chocolate_pudding | ba | [] | 0/3 | 600/600/600 | 1/0/1 |
| `t09_b_bbq_sauce_ab` | orange_juice | bbq_sauce | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t09_b_bbq_sauce_ba` | orange_juice | bbq_sauce | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t09_b_ketchup_ab` | orange_juice | ketchup | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t09_b_ketchup_ba` | orange_juice | ketchup | ba | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t09_b_salad_dressing_ab` | orange_juice | salad_dressing | ab | [] | 0/3 | 600/600/600 | 1/1/1 |
| `t09_b_salad_dressing_ba` | orange_juice | salad_dressing | ba | [] | 0/3 | 600/600/600 | 1/0/1 |

## 5. 说明

- 每候选每个 seed 的 init 行 = 源任务 `.pruned_init` 的第 seed 行；`_ab`/`_ba` 共用同一 init。
- 成功判定沿用合并 BDDL 的两个 goal atom 同时为真；失败时按 trace 中 first_true_step 统计完成子任务数。
- 本报告由 `prep/build_report.py` 从 `analysis/summary.json` 生成，队列每完成一个 seed 会重跑分析并更新。

## 6. 关键发现（补充分析）

- **300/300 episodes 全部跑满 600 步，success = 0**（`_ab` 0/150、`_ba` 0/150）；无任何候选在任一 seed 成功。
- **失败模式**：290/300 完成**恰好 1 个子任务**后停滞；10/300 完成 0 个；0 个完成 2 个 → 不是"抓取失败"，而是**无法从第一段继续到第二段**。
- **完成的是谁**：仅完成 A（原目标）273 条，仅完成 B（提升目标）17 条；按顺序拆分：`_ab` → A 141 / B 6 / 无 3；`_ba` → A 132 / B 11 / 无 7。**instruction 顺序只带来弱影响（B 完成从 6 增至 11），A 仍占绝对主导（88%–94%）**。
- **位置线索**：17 条完成 B 的 episode 中 **16 条 B 位于 R0 槽位**（`floor_other_object_region_0`），仅 1 条在 R2 → 场景位置先验（前景 R0 / A 的 `target_object_region`）可能覆盖 instruction 顺序。这与"模型主要靠场景线索选目标、而非真正解析组合指令"的解释一致。
- **时序**：完成 A 的 `first_true_step` 中位数 149（119–327）；完成 B 中位数 158（137–188）。
- **结论**：在完全保持原场景/init（无合并场景、无新增槽位、无 init 重采样）的条件下，pi05 zero-shot **仍无法完成同场景双抓取**。瓶颈是"单条组合指令下的链式执行"，且场景/位置先验会覆盖 instruction 顺序。
- **建议**：该设计若作为 baseline 使用，必须搭配 staged/instruction-switch 协议（此前 GOAL 组合 staged 2/4 有效），或对组合任务做微调；单纯改 A/B 指令顺序无效。
