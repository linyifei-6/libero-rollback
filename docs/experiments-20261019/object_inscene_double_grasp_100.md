# LIBERO-OBJECT「场景内双目标（双抓取）」候选任务清单（100 个 = 50 × 2 顺序）

## 设计

- 沿用每个任务原有的场景（1 basket + 6 个可操作物体 = 7 个刚体，qpos/init 不变）。
- 原目标 A 保持；从 5 个干扰物中选 1 个提升为第二目标 B，剩 4 个干扰项。
- 每个 (场景, B) 生成 **2 个顺序变体**：
  - `_ab`：A 先、B 后 → `pick up the <A> ... and pick up the <B> ...`
  - `_ba`：B 先、A 后 → `pick up the <B> ... and pick up the <A> ...`
- **顺序调换只改变 instruction（语言）与 `:obj_of_interest` 顺序**；goal 仍是同样两个原子的 conjunction（And 可交换），场景与 init 不变、复用源任务 `.pruned_init`。
- B 都是其他任务的原生目标物（10 个类型各作为目标 1 次；pi05 原始 10 个任务 baseline 10/10），B 的初始位置是标准干扰槽 R0–R4。

## 逐任务候选清单

### T0：A = **alphabet_soup**（`pick_up_the_alphabet_soup_and_place_it_in_the_basket`）

| 候选 id | 顺序 | 第一目标 | 第二目标 | B 槽位 | 剩余 4 干扰项 | instruction |
|---|---|---|---|---|---|---|
| `t00_b_salad_dressing_ab` | A->B（原目标先） | alphabet_soup | salad_dressing | R0 | cream_cheese, milk, tomato_sauce, butter | pick up the alphabet soup and place it in the basket and pick up the salad dressing and place it in the basket |
| `t00_b_salad_dressing_ba` | B->A（提升目标先） | salad_dressing | alphabet_soup | R0 | cream_cheese, milk, tomato_sauce, butter | pick up the salad dressing and place it in the basket and pick up the alphabet soup and place it in the basket |
| `t00_b_cream_cheese_ab` | A->B（原目标先） | alphabet_soup | cream_cheese | R1 | salad_dressing, milk, tomato_sauce, butter | pick up the alphabet soup and place it in the basket and pick up the cream cheese and place it in the basket |
| `t00_b_cream_cheese_ba` | B->A（提升目标先） | cream_cheese | alphabet_soup | R1 | salad_dressing, milk, tomato_sauce, butter | pick up the cream cheese and place it in the basket and pick up the alphabet soup and place it in the basket |
| `t00_b_milk_ab` | A->B（原目标先） | alphabet_soup | milk | R2 | salad_dressing, cream_cheese, tomato_sauce, butter | pick up the alphabet soup and place it in the basket and pick up the milk and place it in the basket |
| `t00_b_milk_ba` | B->A（提升目标先） | milk | alphabet_soup | R2 | salad_dressing, cream_cheese, tomato_sauce, butter | pick up the milk and place it in the basket and pick up the alphabet soup and place it in the basket |
| `t00_b_tomato_sauce_ab` | A->B（原目标先） | alphabet_soup | tomato_sauce | R3 | salad_dressing, cream_cheese, milk, butter | pick up the alphabet soup and place it in the basket and pick up the tomato sauce and place it in the basket |
| `t00_b_tomato_sauce_ba` | B->A（提升目标先） | tomato_sauce | alphabet_soup | R3 | salad_dressing, cream_cheese, milk, butter | pick up the tomato sauce and place it in the basket and pick up the alphabet soup and place it in the basket |
| `t00_b_butter_ab` | A->B（原目标先） | alphabet_soup | butter | R4 | salad_dressing, cream_cheese, milk, tomato_sauce | pick up the alphabet soup and place it in the basket and pick up the butter and place it in the basket |
| `t00_b_butter_ba` | B->A（提升目标先） | butter | alphabet_soup | R4 | salad_dressing, cream_cheese, milk, tomato_sauce | pick up the butter and place it in the basket and pick up the alphabet soup and place it in the basket |

### T1：A = **cream_cheese**（`pick_up_the_cream_cheese_and_place_it_in_the_basket`）

| 候选 id | 顺序 | 第一目标 | 第二目标 | B 槽位 | 剩余 4 干扰项 | instruction |
|---|---|---|---|---|---|---|
| `t01_b_alphabet_soup_ab` | A->B（原目标先） | cream_cheese | alphabet_soup | R0 | milk, tomato_sauce, butter, orange_juice | pick up the cream cheese and place it in the basket and pick up the alphabet soup and place it in the basket |
| `t01_b_alphabet_soup_ba` | B->A（提升目标先） | alphabet_soup | cream_cheese | R0 | milk, tomato_sauce, butter, orange_juice | pick up the alphabet soup and place it in the basket and pick up the cream cheese and place it in the basket |
| `t01_b_milk_ab` | A->B（原目标先） | cream_cheese | milk | R1 | alphabet_soup, tomato_sauce, butter, orange_juice | pick up the cream cheese and place it in the basket and pick up the milk and place it in the basket |
| `t01_b_milk_ba` | B->A（提升目标先） | milk | cream_cheese | R1 | alphabet_soup, tomato_sauce, butter, orange_juice | pick up the milk and place it in the basket and pick up the cream cheese and place it in the basket |
| `t01_b_tomato_sauce_ab` | A->B（原目标先） | cream_cheese | tomato_sauce | R2 | alphabet_soup, milk, butter, orange_juice | pick up the cream cheese and place it in the basket and pick up the tomato sauce and place it in the basket |
| `t01_b_tomato_sauce_ba` | B->A（提升目标先） | tomato_sauce | cream_cheese | R2 | alphabet_soup, milk, butter, orange_juice | pick up the tomato sauce and place it in the basket and pick up the cream cheese and place it in the basket |
| `t01_b_butter_ab` | A->B（原目标先） | cream_cheese | butter | R3 | alphabet_soup, milk, tomato_sauce, orange_juice | pick up the cream cheese and place it in the basket and pick up the butter and place it in the basket |
| `t01_b_butter_ba` | B->A（提升目标先） | butter | cream_cheese | R3 | alphabet_soup, milk, tomato_sauce, orange_juice | pick up the butter and place it in the basket and pick up the cream cheese and place it in the basket |
| `t01_b_orange_juice_ab` | A->B（原目标先） | cream_cheese | orange_juice | R4 | alphabet_soup, milk, tomato_sauce, butter | pick up the cream cheese and place it in the basket and pick up the orange juice and place it in the basket |
| `t01_b_orange_juice_ba` | B->A（提升目标先） | orange_juice | cream_cheese | R4 | alphabet_soup, milk, tomato_sauce, butter | pick up the orange juice and place it in the basket and pick up the cream cheese and place it in the basket |

### T2：A = **salad_dressing**（`pick_up_the_salad_dressing_and_place_it_in_the_basket`）

| 候选 id | 顺序 | 第一目标 | 第二目标 | B 槽位 | 剩余 4 干扰项 | instruction |
|---|---|---|---|---|---|---|
| `t02_b_ketchup_ab` | A->B（原目标先） | salad_dressing | ketchup | R0 | alphabet_soup, cream_cheese, milk, tomato_sauce | pick up the salad dressing and place it in the basket and pick up the ketchup and place it in the basket |
| `t02_b_ketchup_ba` | B->A（提升目标先） | ketchup | salad_dressing | R0 | alphabet_soup, cream_cheese, milk, tomato_sauce | pick up the ketchup and place it in the basket and pick up the salad dressing and place it in the basket |
| `t02_b_alphabet_soup_ab` | A->B（原目标先） | salad_dressing | alphabet_soup | R1 | ketchup, cream_cheese, milk, tomato_sauce | pick up the salad dressing and place it in the basket and pick up the alphabet soup and place it in the basket |
| `t02_b_alphabet_soup_ba` | B->A（提升目标先） | alphabet_soup | salad_dressing | R1 | ketchup, cream_cheese, milk, tomato_sauce | pick up the alphabet soup and place it in the basket and pick up the salad dressing and place it in the basket |
| `t02_b_cream_cheese_ab` | A->B（原目标先） | salad_dressing | cream_cheese | R2 | ketchup, alphabet_soup, milk, tomato_sauce | pick up the salad dressing and place it in the basket and pick up the cream cheese and place it in the basket |
| `t02_b_cream_cheese_ba` | B->A（提升目标先） | cream_cheese | salad_dressing | R2 | ketchup, alphabet_soup, milk, tomato_sauce | pick up the cream cheese and place it in the basket and pick up the salad dressing and place it in the basket |
| `t02_b_milk_ab` | A->B（原目标先） | salad_dressing | milk | R3 | ketchup, alphabet_soup, cream_cheese, tomato_sauce | pick up the salad dressing and place it in the basket and pick up the milk and place it in the basket |
| `t02_b_milk_ba` | B->A（提升目标先） | milk | salad_dressing | R3 | ketchup, alphabet_soup, cream_cheese, tomato_sauce | pick up the milk and place it in the basket and pick up the salad dressing and place it in the basket |
| `t02_b_tomato_sauce_ab` | A->B（原目标先） | salad_dressing | tomato_sauce | R4 | ketchup, alphabet_soup, cream_cheese, milk | pick up the salad dressing and place it in the basket and pick up the tomato sauce and place it in the basket |
| `t02_b_tomato_sauce_ba` | B->A（提升目标先） | tomato_sauce | salad_dressing | R4 | ketchup, alphabet_soup, cream_cheese, milk | pick up the tomato sauce and place it in the basket and pick up the salad dressing and place it in the basket |

### T3：A = **bbq_sauce**（`pick_up_the_bbq_sauce_and_place_it_in_the_basket`）

| 候选 id | 顺序 | 第一目标 | 第二目标 | B 槽位 | 剩余 4 干扰项 | instruction |
|---|---|---|---|---|---|---|
| `t03_b_chocolate_pudding_ab` | A->B（原目标先） | bbq_sauce | chocolate_pudding | R0 | ketchup, salad_dressing, alphabet_soup, cream_cheese | pick up the bbq sauce and place it in the basket and pick up the chocolate pudding and place it in the basket |
| `t03_b_chocolate_pudding_ba` | B->A（提升目标先） | chocolate_pudding | bbq_sauce | R0 | ketchup, salad_dressing, alphabet_soup, cream_cheese | pick up the chocolate pudding and place it in the basket and pick up the bbq sauce and place it in the basket |
| `t03_b_ketchup_ab` | A->B（原目标先） | bbq_sauce | ketchup | R1 | chocolate_pudding, salad_dressing, alphabet_soup, cream_cheese | pick up the bbq sauce and place it in the basket and pick up the ketchup and place it in the basket |
| `t03_b_ketchup_ba` | B->A（提升目标先） | ketchup | bbq_sauce | R1 | chocolate_pudding, salad_dressing, alphabet_soup, cream_cheese | pick up the ketchup and place it in the basket and pick up the bbq sauce and place it in the basket |
| `t03_b_salad_dressing_ab` | A->B（原目标先） | bbq_sauce | salad_dressing | R2 | chocolate_pudding, ketchup, alphabet_soup, cream_cheese | pick up the bbq sauce and place it in the basket and pick up the salad dressing and place it in the basket |
| `t03_b_salad_dressing_ba` | B->A（提升目标先） | salad_dressing | bbq_sauce | R2 | chocolate_pudding, ketchup, alphabet_soup, cream_cheese | pick up the salad dressing and place it in the basket and pick up the bbq sauce and place it in the basket |
| `t03_b_alphabet_soup_ab` | A->B（原目标先） | bbq_sauce | alphabet_soup | R3 | chocolate_pudding, ketchup, salad_dressing, cream_cheese | pick up the bbq sauce and place it in the basket and pick up the alphabet soup and place it in the basket |
| `t03_b_alphabet_soup_ba` | B->A（提升目标先） | alphabet_soup | bbq_sauce | R3 | chocolate_pudding, ketchup, salad_dressing, cream_cheese | pick up the alphabet soup and place it in the basket and pick up the bbq sauce and place it in the basket |
| `t03_b_cream_cheese_ab` | A->B（原目标先） | bbq_sauce | cream_cheese | R4 | chocolate_pudding, ketchup, salad_dressing, alphabet_soup | pick up the bbq sauce and place it in the basket and pick up the cream cheese and place it in the basket |
| `t03_b_cream_cheese_ba` | B->A（提升目标先） | cream_cheese | bbq_sauce | R4 | chocolate_pudding, ketchup, salad_dressing, alphabet_soup | pick up the cream cheese and place it in the basket and pick up the bbq sauce and place it in the basket |

### T4：A = **ketchup**（`pick_up_the_ketchup_and_place_it_in_the_basket`）

| 候选 id | 顺序 | 第一目标 | 第二目标 | B 槽位 | 剩余 4 干扰项 | instruction |
|---|---|---|---|---|---|---|
| `t04_b_bbq_sauce_ab` | A->B（原目标先） | ketchup | bbq_sauce | R0 | salad_dressing, alphabet_soup, cream_cheese, milk | pick up the ketchup and place it in the basket and pick up the bbq sauce and place it in the basket |
| `t04_b_bbq_sauce_ba` | B->A（提升目标先） | bbq_sauce | ketchup | R0 | salad_dressing, alphabet_soup, cream_cheese, milk | pick up the bbq sauce and place it in the basket and pick up the ketchup and place it in the basket |
| `t04_b_salad_dressing_ab` | A->B（原目标先） | ketchup | salad_dressing | R1 | bbq_sauce, alphabet_soup, cream_cheese, milk | pick up the ketchup and place it in the basket and pick up the salad dressing and place it in the basket |
| `t04_b_salad_dressing_ba` | B->A（提升目标先） | salad_dressing | ketchup | R1 | bbq_sauce, alphabet_soup, cream_cheese, milk | pick up the salad dressing and place it in the basket and pick up the ketchup and place it in the basket |
| `t04_b_alphabet_soup_ab` | A->B（原目标先） | ketchup | alphabet_soup | R2 | bbq_sauce, salad_dressing, cream_cheese, milk | pick up the ketchup and place it in the basket and pick up the alphabet soup and place it in the basket |
| `t04_b_alphabet_soup_ba` | B->A（提升目标先） | alphabet_soup | ketchup | R2 | bbq_sauce, salad_dressing, cream_cheese, milk | pick up the alphabet soup and place it in the basket and pick up the ketchup and place it in the basket |
| `t04_b_cream_cheese_ab` | A->B（原目标先） | ketchup | cream_cheese | R3 | bbq_sauce, salad_dressing, alphabet_soup, milk | pick up the ketchup and place it in the basket and pick up the cream cheese and place it in the basket |
| `t04_b_cream_cheese_ba` | B->A（提升目标先） | cream_cheese | ketchup | R3 | bbq_sauce, salad_dressing, alphabet_soup, milk | pick up the cream cheese and place it in the basket and pick up the ketchup and place it in the basket |
| `t04_b_milk_ab` | A->B（原目标先） | ketchup | milk | R4 | bbq_sauce, salad_dressing, alphabet_soup, cream_cheese | pick up the ketchup and place it in the basket and pick up the milk and place it in the basket |
| `t04_b_milk_ba` | B->A（提升目标先） | milk | ketchup | R4 | bbq_sauce, salad_dressing, alphabet_soup, cream_cheese | pick up the milk and place it in the basket and pick up the ketchup and place it in the basket |

### T5：A = **tomato_sauce**（`pick_up_the_tomato_sauce_and_place_it_in_the_basket`）

| 候选 id | 顺序 | 第一目标 | 第二目标 | B 槽位 | 剩余 4 干扰项 | instruction |
|---|---|---|---|---|---|---|
| `t05_b_milk_ab` | A->B（原目标先） | tomato_sauce | milk | R0 | butter, orange_juice, chocolate_pudding, bbq_sauce | pick up the tomato sauce and place it in the basket and pick up the milk and place it in the basket |
| `t05_b_milk_ba` | B->A（提升目标先） | milk | tomato_sauce | R0 | butter, orange_juice, chocolate_pudding, bbq_sauce | pick up the milk and place it in the basket and pick up the tomato sauce and place it in the basket |
| `t05_b_butter_ab` | A->B（原目标先） | tomato_sauce | butter | R1 | milk, orange_juice, chocolate_pudding, bbq_sauce | pick up the tomato sauce and place it in the basket and pick up the butter and place it in the basket |
| `t05_b_butter_ba` | B->A（提升目标先） | butter | tomato_sauce | R1 | milk, orange_juice, chocolate_pudding, bbq_sauce | pick up the butter and place it in the basket and pick up the tomato sauce and place it in the basket |
| `t05_b_orange_juice_ab` | A->B（原目标先） | tomato_sauce | orange_juice | R2 | milk, butter, chocolate_pudding, bbq_sauce | pick up the tomato sauce and place it in the basket and pick up the orange juice and place it in the basket |
| `t05_b_orange_juice_ba` | B->A（提升目标先） | orange_juice | tomato_sauce | R2 | milk, butter, chocolate_pudding, bbq_sauce | pick up the orange juice and place it in the basket and pick up the tomato sauce and place it in the basket |
| `t05_b_chocolate_pudding_ab` | A->B（原目标先） | tomato_sauce | chocolate_pudding | R3 | milk, butter, orange_juice, bbq_sauce | pick up the tomato sauce and place it in the basket and pick up the chocolate pudding and place it in the basket |
| `t05_b_chocolate_pudding_ba` | B->A（提升目标先） | chocolate_pudding | tomato_sauce | R3 | milk, butter, orange_juice, bbq_sauce | pick up the chocolate pudding and place it in the basket and pick up the tomato sauce and place it in the basket |
| `t05_b_bbq_sauce_ab` | A->B（原目标先） | tomato_sauce | bbq_sauce | R4 | milk, butter, orange_juice, chocolate_pudding | pick up the tomato sauce and place it in the basket and pick up the bbq sauce and place it in the basket |
| `t05_b_bbq_sauce_ba` | B->A（提升目标先） | bbq_sauce | tomato_sauce | R4 | milk, butter, orange_juice, chocolate_pudding | pick up the bbq sauce and place it in the basket and pick up the tomato sauce and place it in the basket |

### T6：A = **butter**（`pick_up_the_butter_and_place_it_in_the_basket`）

| 候选 id | 顺序 | 第一目标 | 第二目标 | B 槽位 | 剩余 4 干扰项 | instruction |
|---|---|---|---|---|---|---|
| `t06_b_tomato_sauce_ab` | A->B（原目标先） | butter | tomato_sauce | R0 | orange_juice, chocolate_pudding, bbq_sauce, ketchup | pick up the butter and place it in the basket and pick up the tomato sauce and place it in the basket |
| `t06_b_tomato_sauce_ba` | B->A（提升目标先） | tomato_sauce | butter | R0 | orange_juice, chocolate_pudding, bbq_sauce, ketchup | pick up the tomato sauce and place it in the basket and pick up the butter and place it in the basket |
| `t06_b_orange_juice_ab` | A->B（原目标先） | butter | orange_juice | R1 | tomato_sauce, chocolate_pudding, bbq_sauce, ketchup | pick up the butter and place it in the basket and pick up the orange juice and place it in the basket |
| `t06_b_orange_juice_ba` | B->A（提升目标先） | orange_juice | butter | R1 | tomato_sauce, chocolate_pudding, bbq_sauce, ketchup | pick up the orange juice and place it in the basket and pick up the butter and place it in the basket |
| `t06_b_chocolate_pudding_ab` | A->B（原目标先） | butter | chocolate_pudding | R2 | tomato_sauce, orange_juice, bbq_sauce, ketchup | pick up the butter and place it in the basket and pick up the chocolate pudding and place it in the basket |
| `t06_b_chocolate_pudding_ba` | B->A（提升目标先） | chocolate_pudding | butter | R2 | tomato_sauce, orange_juice, bbq_sauce, ketchup | pick up the chocolate pudding and place it in the basket and pick up the butter and place it in the basket |
| `t06_b_bbq_sauce_ab` | A->B（原目标先） | butter | bbq_sauce | R3 | tomato_sauce, orange_juice, chocolate_pudding, ketchup | pick up the butter and place it in the basket and pick up the bbq sauce and place it in the basket |
| `t06_b_bbq_sauce_ba` | B->A（提升目标先） | bbq_sauce | butter | R3 | tomato_sauce, orange_juice, chocolate_pudding, ketchup | pick up the bbq sauce and place it in the basket and pick up the butter and place it in the basket |
| `t06_b_ketchup_ab` | A->B（原目标先） | butter | ketchup | R4 | tomato_sauce, orange_juice, chocolate_pudding, bbq_sauce | pick up the butter and place it in the basket and pick up the ketchup and place it in the basket |
| `t06_b_ketchup_ba` | B->A（提升目标先） | ketchup | butter | R4 | tomato_sauce, orange_juice, chocolate_pudding, bbq_sauce | pick up the ketchup and place it in the basket and pick up the butter and place it in the basket |

### T7：A = **milk**（`pick_up_the_milk_and_place_it_in_the_basket`）

| 候选 id | 顺序 | 第一目标 | 第二目标 | B 槽位 | 剩余 4 干扰项 | instruction |
|---|---|---|---|---|---|---|
| `t07_b_cream_cheese_ab` | A->B（原目标先） | milk | cream_cheese | R0 | tomato_sauce, butter, orange_juice, chocolate_pudding | pick up the milk and place it in the basket and pick up the cream cheese and place it in the basket |
| `t07_b_cream_cheese_ba` | B->A（提升目标先） | cream_cheese | milk | R0 | tomato_sauce, butter, orange_juice, chocolate_pudding | pick up the cream cheese and place it in the basket and pick up the milk and place it in the basket |
| `t07_b_tomato_sauce_ab` | A->B（原目标先） | milk | tomato_sauce | R1 | cream_cheese, butter, orange_juice, chocolate_pudding | pick up the milk and place it in the basket and pick up the tomato sauce and place it in the basket |
| `t07_b_tomato_sauce_ba` | B->A（提升目标先） | tomato_sauce | milk | R1 | cream_cheese, butter, orange_juice, chocolate_pudding | pick up the tomato sauce and place it in the basket and pick up the milk and place it in the basket |
| `t07_b_butter_ab` | A->B（原目标先） | milk | butter | R2 | cream_cheese, tomato_sauce, orange_juice, chocolate_pudding | pick up the milk and place it in the basket and pick up the butter and place it in the basket |
| `t07_b_butter_ba` | B->A（提升目标先） | butter | milk | R2 | cream_cheese, tomato_sauce, orange_juice, chocolate_pudding | pick up the butter and place it in the basket and pick up the milk and place it in the basket |
| `t07_b_orange_juice_ab` | A->B（原目标先） | milk | orange_juice | R3 | cream_cheese, tomato_sauce, butter, chocolate_pudding | pick up the milk and place it in the basket and pick up the orange juice and place it in the basket |
| `t07_b_orange_juice_ba` | B->A（提升目标先） | orange_juice | milk | R3 | cream_cheese, tomato_sauce, butter, chocolate_pudding | pick up the orange juice and place it in the basket and pick up the milk and place it in the basket |
| `t07_b_chocolate_pudding_ab` | A->B（原目标先） | milk | chocolate_pudding | R4 | cream_cheese, tomato_sauce, butter, orange_juice | pick up the milk and place it in the basket and pick up the chocolate pudding and place it in the basket |
| `t07_b_chocolate_pudding_ba` | B->A（提升目标先） | chocolate_pudding | milk | R4 | cream_cheese, tomato_sauce, butter, orange_juice | pick up the chocolate pudding and place it in the basket and pick up the milk and place it in the basket |

### T8：A = **chocolate_pudding**（`pick_up_the_chocolate_pudding_and_place_it_in_the_basket`）

| 候选 id | 顺序 | 第一目标 | 第二目标 | B 槽位 | 剩余 4 干扰项 | instruction |
|---|---|---|---|---|---|---|
| `t08_b_orange_juice_ab` | A->B（原目标先） | chocolate_pudding | orange_juice | R0 | bbq_sauce, ketchup, salad_dressing, alphabet_soup | pick up the chocolate pudding and place it in the basket and pick up the orange juice and place it in the basket |
| `t08_b_orange_juice_ba` | B->A（提升目标先） | orange_juice | chocolate_pudding | R0 | bbq_sauce, ketchup, salad_dressing, alphabet_soup | pick up the orange juice and place it in the basket and pick up the chocolate pudding and place it in the basket |
| `t08_b_bbq_sauce_ab` | A->B（原目标先） | chocolate_pudding | bbq_sauce | R1 | orange_juice, ketchup, salad_dressing, alphabet_soup | pick up the chocolate pudding and place it in the basket and pick up the bbq sauce and place it in the basket |
| `t08_b_bbq_sauce_ba` | B->A（提升目标先） | bbq_sauce | chocolate_pudding | R1 | orange_juice, ketchup, salad_dressing, alphabet_soup | pick up the bbq sauce and place it in the basket and pick up the chocolate pudding and place it in the basket |
| `t08_b_ketchup_ab` | A->B（原目标先） | chocolate_pudding | ketchup | R2 | orange_juice, bbq_sauce, salad_dressing, alphabet_soup | pick up the chocolate pudding and place it in the basket and pick up the ketchup and place it in the basket |
| `t08_b_ketchup_ba` | B->A（提升目标先） | ketchup | chocolate_pudding | R2 | orange_juice, bbq_sauce, salad_dressing, alphabet_soup | pick up the ketchup and place it in the basket and pick up the chocolate pudding and place it in the basket |
| `t08_b_salad_dressing_ab` | A->B（原目标先） | chocolate_pudding | salad_dressing | R3 | orange_juice, bbq_sauce, ketchup, alphabet_soup | pick up the chocolate pudding and place it in the basket and pick up the salad dressing and place it in the basket |
| `t08_b_salad_dressing_ba` | B->A（提升目标先） | salad_dressing | chocolate_pudding | R3 | orange_juice, bbq_sauce, ketchup, alphabet_soup | pick up the salad dressing and place it in the basket and pick up the chocolate pudding and place it in the basket |
| `t08_b_alphabet_soup_ab` | A->B（原目标先） | chocolate_pudding | alphabet_soup | R4 | orange_juice, bbq_sauce, ketchup, salad_dressing | pick up the chocolate pudding and place it in the basket and pick up the alphabet soup and place it in the basket |
| `t08_b_alphabet_soup_ba` | B->A（提升目标先） | alphabet_soup | chocolate_pudding | R4 | orange_juice, bbq_sauce, ketchup, salad_dressing | pick up the alphabet soup and place it in the basket and pick up the chocolate pudding and place it in the basket |

### T9：A = **orange_juice**（`pick_up_the_orange_juice_and_place_it_in_the_basket`）

| 候选 id | 顺序 | 第一目标 | 第二目标 | B 槽位 | 剩余 4 干扰项 | instruction |
|---|---|---|---|---|---|---|
| `t09_b_butter_ab` | A->B（原目标先） | orange_juice | butter | R0 | chocolate_pudding, bbq_sauce, ketchup, salad_dressing | pick up the orange juice and place it in the basket and pick up the butter and place it in the basket |
| `t09_b_butter_ba` | B->A（提升目标先） | butter | orange_juice | R0 | chocolate_pudding, bbq_sauce, ketchup, salad_dressing | pick up the butter and place it in the basket and pick up the orange juice and place it in the basket |
| `t09_b_chocolate_pudding_ab` | A->B（原目标先） | orange_juice | chocolate_pudding | R1 | butter, bbq_sauce, ketchup, salad_dressing | pick up the orange juice and place it in the basket and pick up the chocolate pudding and place it in the basket |
| `t09_b_chocolate_pudding_ba` | B->A（提升目标先） | chocolate_pudding | orange_juice | R1 | butter, bbq_sauce, ketchup, salad_dressing | pick up the chocolate pudding and place it in the basket and pick up the orange juice and place it in the basket |
| `t09_b_bbq_sauce_ab` | A->B（原目标先） | orange_juice | bbq_sauce | R2 | butter, chocolate_pudding, ketchup, salad_dressing | pick up the orange juice and place it in the basket and pick up the bbq sauce and place it in the basket |
| `t09_b_bbq_sauce_ba` | B->A（提升目标先） | bbq_sauce | orange_juice | R2 | butter, chocolate_pudding, ketchup, salad_dressing | pick up the bbq sauce and place it in the basket and pick up the orange juice and place it in the basket |
| `t09_b_ketchup_ab` | A->B（原目标先） | orange_juice | ketchup | R3 | butter, chocolate_pudding, bbq_sauce, salad_dressing | pick up the orange juice and place it in the basket and pick up the ketchup and place it in the basket |
| `t09_b_ketchup_ba` | B->A（提升目标先） | ketchup | orange_juice | R3 | butter, chocolate_pudding, bbq_sauce, salad_dressing | pick up the ketchup and place it in the basket and pick up the orange juice and place it in the basket |
| `t09_b_salad_dressing_ab` | A->B（原目标先） | orange_juice | salad_dressing | R4 | butter, chocolate_pudding, bbq_sauce, ketchup | pick up the orange juice and place it in the basket and pick up the salad dressing and place it in the basket |
| `t09_b_salad_dressing_ba` | B->A（提升目标先） | salad_dressing | orange_juice | R4 | butter, chocolate_pudding, bbq_sauce, ketchup | pick up the salad dressing and place it in the basket and pick up the orange juice and place it in the basket |

## 汇总

- 候选总数：**100**（10 场景 × 5 个 B × 2 顺序）。
- 唯一 goal 原子集合：**40**；若把「集合 + 顺序」也计入去重维度：**80**（10 个目标物对在两个场景各出现一次，造成 20 个场景内重复）。
- 每个物体类型：作为 A 1 次、作为 B 5 次（对应 6 个场景任务）；每个场景 10 个候选。

生成时间：2026-10-23；数据源：官方 benchmark 顺序原版 BDDL 解析（object_task_inventory.json）。
