# 100 个候选任务 case 列表（含运行指令）

运行顺序 = `CUSTOM_T<idx>`，与 bddl 文件排序一致（下表 idx 即 runner task index）。

| idx | candidate_id | 场景任务 | 顺序 | A | B | 运行 instruction（= bddl :language） |
|---|---|---|---|---|---|---|
| 0 | `t00_b_butter_ab` | T0 | ab | alphabet_soup | butter | pick up the alphabet soup and place it in the basket and pick up the butter and place it in the basket |
| 1 | `t00_b_butter_ba` | T0 | ba | alphabet_soup | butter | pick up the butter and place it in the basket and pick up the alphabet soup and place it in the basket |
| 2 | `t00_b_cream_cheese_ab` | T0 | ab | alphabet_soup | cream_cheese | pick up the alphabet soup and place it in the basket and pick up the cream cheese and place it in the basket |
| 3 | `t00_b_cream_cheese_ba` | T0 | ba | alphabet_soup | cream_cheese | pick up the cream cheese and place it in the basket and pick up the alphabet soup and place it in the basket |
| 4 | `t00_b_milk_ab` | T0 | ab | alphabet_soup | milk | pick up the alphabet soup and place it in the basket and pick up the milk and place it in the basket |
| 5 | `t00_b_milk_ba` | T0 | ba | alphabet_soup | milk | pick up the milk and place it in the basket and pick up the alphabet soup and place it in the basket |
| 6 | `t00_b_salad_dressing_ab` | T0 | ab | alphabet_soup | salad_dressing | pick up the alphabet soup and place it in the basket and pick up the salad dressing and place it in the basket |
| 7 | `t00_b_salad_dressing_ba` | T0 | ba | alphabet_soup | salad_dressing | pick up the salad dressing and place it in the basket and pick up the alphabet soup and place it in the basket |
| 8 | `t00_b_tomato_sauce_ab` | T0 | ab | alphabet_soup | tomato_sauce | pick up the alphabet soup and place it in the basket and pick up the tomato sauce and place it in the basket |
| 9 | `t00_b_tomato_sauce_ba` | T0 | ba | alphabet_soup | tomato_sauce | pick up the tomato sauce and place it in the basket and pick up the alphabet soup and place it in the basket |
| 10 | `t01_b_alphabet_soup_ab` | T1 | ab | cream_cheese | alphabet_soup | pick up the cream cheese and place it in the basket and pick up the alphabet soup and place it in the basket |
| 11 | `t01_b_alphabet_soup_ba` | T1 | ba | cream_cheese | alphabet_soup | pick up the alphabet soup and place it in the basket and pick up the cream cheese and place it in the basket |
| 12 | `t01_b_butter_ab` | T1 | ab | cream_cheese | butter | pick up the cream cheese and place it in the basket and pick up the butter and place it in the basket |
| 13 | `t01_b_butter_ba` | T1 | ba | cream_cheese | butter | pick up the butter and place it in the basket and pick up the cream cheese and place it in the basket |
| 14 | `t01_b_milk_ab` | T1 | ab | cream_cheese | milk | pick up the cream cheese and place it in the basket and pick up the milk and place it in the basket |
| 15 | `t01_b_milk_ba` | T1 | ba | cream_cheese | milk | pick up the milk and place it in the basket and pick up the cream cheese and place it in the basket |
| 16 | `t01_b_orange_juice_ab` | T1 | ab | cream_cheese | orange_juice | pick up the cream cheese and place it in the basket and pick up the orange juice and place it in the basket |
| 17 | `t01_b_orange_juice_ba` | T1 | ba | cream_cheese | orange_juice | pick up the orange juice and place it in the basket and pick up the cream cheese and place it in the basket |
| 18 | `t01_b_tomato_sauce_ab` | T1 | ab | cream_cheese | tomato_sauce | pick up the cream cheese and place it in the basket and pick up the tomato sauce and place it in the basket |
| 19 | `t01_b_tomato_sauce_ba` | T1 | ba | cream_cheese | tomato_sauce | pick up the tomato sauce and place it in the basket and pick up the cream cheese and place it in the basket |
| 20 | `t02_b_alphabet_soup_ab` | T2 | ab | salad_dressing | alphabet_soup | pick up the salad dressing and place it in the basket and pick up the alphabet soup and place it in the basket |
| 21 | `t02_b_alphabet_soup_ba` | T2 | ba | salad_dressing | alphabet_soup | pick up the alphabet soup and place it in the basket and pick up the salad dressing and place it in the basket |
| 22 | `t02_b_cream_cheese_ab` | T2 | ab | salad_dressing | cream_cheese | pick up the salad dressing and place it in the basket and pick up the cream cheese and place it in the basket |
| 23 | `t02_b_cream_cheese_ba` | T2 | ba | salad_dressing | cream_cheese | pick up the cream cheese and place it in the basket and pick up the salad dressing and place it in the basket |
| 24 | `t02_b_ketchup_ab` | T2 | ab | salad_dressing | ketchup | pick up the salad dressing and place it in the basket and pick up the ketchup and place it in the basket |
| 25 | `t02_b_ketchup_ba` | T2 | ba | salad_dressing | ketchup | pick up the ketchup and place it in the basket and pick up the salad dressing and place it in the basket |
| 26 | `t02_b_milk_ab` | T2 | ab | salad_dressing | milk | pick up the salad dressing and place it in the basket and pick up the milk and place it in the basket |
| 27 | `t02_b_milk_ba` | T2 | ba | salad_dressing | milk | pick up the milk and place it in the basket and pick up the salad dressing and place it in the basket |
| 28 | `t02_b_tomato_sauce_ab` | T2 | ab | salad_dressing | tomato_sauce | pick up the salad dressing and place it in the basket and pick up the tomato sauce and place it in the basket |
| 29 | `t02_b_tomato_sauce_ba` | T2 | ba | salad_dressing | tomato_sauce | pick up the tomato sauce and place it in the basket and pick up the salad dressing and place it in the basket |
| 30 | `t03_b_alphabet_soup_ab` | T3 | ab | bbq_sauce | alphabet_soup | pick up the bbq sauce and place it in the basket and pick up the alphabet soup and place it in the basket |
| 31 | `t03_b_alphabet_soup_ba` | T3 | ba | bbq_sauce | alphabet_soup | pick up the alphabet soup and place it in the basket and pick up the bbq sauce and place it in the basket |
| 32 | `t03_b_chocolate_pudding_ab` | T3 | ab | bbq_sauce | chocolate_pudding | pick up the bbq sauce and place it in the basket and pick up the chocolate pudding and place it in the basket |
| 33 | `t03_b_chocolate_pudding_ba` | T3 | ba | bbq_sauce | chocolate_pudding | pick up the chocolate pudding and place it in the basket and pick up the bbq sauce and place it in the basket |
| 34 | `t03_b_cream_cheese_ab` | T3 | ab | bbq_sauce | cream_cheese | pick up the bbq sauce and place it in the basket and pick up the cream cheese and place it in the basket |
| 35 | `t03_b_cream_cheese_ba` | T3 | ba | bbq_sauce | cream_cheese | pick up the cream cheese and place it in the basket and pick up the bbq sauce and place it in the basket |
| 36 | `t03_b_ketchup_ab` | T3 | ab | bbq_sauce | ketchup | pick up the bbq sauce and place it in the basket and pick up the ketchup and place it in the basket |
| 37 | `t03_b_ketchup_ba` | T3 | ba | bbq_sauce | ketchup | pick up the ketchup and place it in the basket and pick up the bbq sauce and place it in the basket |
| 38 | `t03_b_salad_dressing_ab` | T3 | ab | bbq_sauce | salad_dressing | pick up the bbq sauce and place it in the basket and pick up the salad dressing and place it in the basket |
| 39 | `t03_b_salad_dressing_ba` | T3 | ba | bbq_sauce | salad_dressing | pick up the salad dressing and place it in the basket and pick up the bbq sauce and place it in the basket |
| 40 | `t04_b_alphabet_soup_ab` | T4 | ab | ketchup | alphabet_soup | pick up the ketchup and place it in the basket and pick up the alphabet soup and place it in the basket |
| 41 | `t04_b_alphabet_soup_ba` | T4 | ba | ketchup | alphabet_soup | pick up the alphabet soup and place it in the basket and pick up the ketchup and place it in the basket |
| 42 | `t04_b_bbq_sauce_ab` | T4 | ab | ketchup | bbq_sauce | pick up the ketchup and place it in the basket and pick up the bbq sauce and place it in the basket |
| 43 | `t04_b_bbq_sauce_ba` | T4 | ba | ketchup | bbq_sauce | pick up the bbq sauce and place it in the basket and pick up the ketchup and place it in the basket |
| 44 | `t04_b_cream_cheese_ab` | T4 | ab | ketchup | cream_cheese | pick up the ketchup and place it in the basket and pick up the cream cheese and place it in the basket |
| 45 | `t04_b_cream_cheese_ba` | T4 | ba | ketchup | cream_cheese | pick up the cream cheese and place it in the basket and pick up the ketchup and place it in the basket |
| 46 | `t04_b_milk_ab` | T4 | ab | ketchup | milk | pick up the ketchup and place it in the basket and pick up the milk and place it in the basket |
| 47 | `t04_b_milk_ba` | T4 | ba | ketchup | milk | pick up the milk and place it in the basket and pick up the ketchup and place it in the basket |
| 48 | `t04_b_salad_dressing_ab` | T4 | ab | ketchup | salad_dressing | pick up the ketchup and place it in the basket and pick up the salad dressing and place it in the basket |
| 49 | `t04_b_salad_dressing_ba` | T4 | ba | ketchup | salad_dressing | pick up the salad dressing and place it in the basket and pick up the ketchup and place it in the basket |
| 50 | `t05_b_bbq_sauce_ab` | T5 | ab | tomato_sauce | bbq_sauce | pick up the tomato sauce and place it in the basket and pick up the bbq sauce and place it in the basket |
| 51 | `t05_b_bbq_sauce_ba` | T5 | ba | tomato_sauce | bbq_sauce | pick up the bbq sauce and place it in the basket and pick up the tomato sauce and place it in the basket |
| 52 | `t05_b_butter_ab` | T5 | ab | tomato_sauce | butter | pick up the tomato sauce and place it in the basket and pick up the butter and place it in the basket |
| 53 | `t05_b_butter_ba` | T5 | ba | tomato_sauce | butter | pick up the butter and place it in the basket and pick up the tomato sauce and place it in the basket |
| 54 | `t05_b_chocolate_pudding_ab` | T5 | ab | tomato_sauce | chocolate_pudding | pick up the tomato sauce and place it in the basket and pick up the chocolate pudding and place it in the basket |
| 55 | `t05_b_chocolate_pudding_ba` | T5 | ba | tomato_sauce | chocolate_pudding | pick up the chocolate pudding and place it in the basket and pick up the tomato sauce and place it in the basket |
| 56 | `t05_b_milk_ab` | T5 | ab | tomato_sauce | milk | pick up the tomato sauce and place it in the basket and pick up the milk and place it in the basket |
| 57 | `t05_b_milk_ba` | T5 | ba | tomato_sauce | milk | pick up the milk and place it in the basket and pick up the tomato sauce and place it in the basket |
| 58 | `t05_b_orange_juice_ab` | T5 | ab | tomato_sauce | orange_juice | pick up the tomato sauce and place it in the basket and pick up the orange juice and place it in the basket |
| 59 | `t05_b_orange_juice_ba` | T5 | ba | tomato_sauce | orange_juice | pick up the orange juice and place it in the basket and pick up the tomato sauce and place it in the basket |
| 60 | `t06_b_bbq_sauce_ab` | T6 | ab | butter | bbq_sauce | pick up the butter and place it in the basket and pick up the bbq sauce and place it in the basket |
| 61 | `t06_b_bbq_sauce_ba` | T6 | ba | butter | bbq_sauce | pick up the bbq sauce and place it in the basket and pick up the butter and place it in the basket |
| 62 | `t06_b_chocolate_pudding_ab` | T6 | ab | butter | chocolate_pudding | pick up the butter and place it in the basket and pick up the chocolate pudding and place it in the basket |
| 63 | `t06_b_chocolate_pudding_ba` | T6 | ba | butter | chocolate_pudding | pick up the chocolate pudding and place it in the basket and pick up the butter and place it in the basket |
| 64 | `t06_b_ketchup_ab` | T6 | ab | butter | ketchup | pick up the butter and place it in the basket and pick up the ketchup and place it in the basket |
| 65 | `t06_b_ketchup_ba` | T6 | ba | butter | ketchup | pick up the ketchup and place it in the basket and pick up the butter and place it in the basket |
| 66 | `t06_b_orange_juice_ab` | T6 | ab | butter | orange_juice | pick up the butter and place it in the basket and pick up the orange juice and place it in the basket |
| 67 | `t06_b_orange_juice_ba` | T6 | ba | butter | orange_juice | pick up the orange juice and place it in the basket and pick up the butter and place it in the basket |
| 68 | `t06_b_tomato_sauce_ab` | T6 | ab | butter | tomato_sauce | pick up the butter and place it in the basket and pick up the tomato sauce and place it in the basket |
| 69 | `t06_b_tomato_sauce_ba` | T6 | ba | butter | tomato_sauce | pick up the tomato sauce and place it in the basket and pick up the butter and place it in the basket |
| 70 | `t07_b_butter_ab` | T7 | ab | milk | butter | pick up the milk and place it in the basket and pick up the butter and place it in the basket |
| 71 | `t07_b_butter_ba` | T7 | ba | milk | butter | pick up the butter and place it in the basket and pick up the milk and place it in the basket |
| 72 | `t07_b_chocolate_pudding_ab` | T7 | ab | milk | chocolate_pudding | pick up the milk and place it in the basket and pick up the chocolate pudding and place it in the basket |
| 73 | `t07_b_chocolate_pudding_ba` | T7 | ba | milk | chocolate_pudding | pick up the chocolate pudding and place it in the basket and pick up the milk and place it in the basket |
| 74 | `t07_b_cream_cheese_ab` | T7 | ab | milk | cream_cheese | pick up the milk and place it in the basket and pick up the cream cheese and place it in the basket |
| 75 | `t07_b_cream_cheese_ba` | T7 | ba | milk | cream_cheese | pick up the cream cheese and place it in the basket and pick up the milk and place it in the basket |
| 76 | `t07_b_orange_juice_ab` | T7 | ab | milk | orange_juice | pick up the milk and place it in the basket and pick up the orange juice and place it in the basket |
| 77 | `t07_b_orange_juice_ba` | T7 | ba | milk | orange_juice | pick up the orange juice and place it in the basket and pick up the milk and place it in the basket |
| 78 | `t07_b_tomato_sauce_ab` | T7 | ab | milk | tomato_sauce | pick up the milk and place it in the basket and pick up the tomato sauce and place it in the basket |
| 79 | `t07_b_tomato_sauce_ba` | T7 | ba | milk | tomato_sauce | pick up the tomato sauce and place it in the basket and pick up the milk and place it in the basket |
| 80 | `t08_b_alphabet_soup_ab` | T8 | ab | chocolate_pudding | alphabet_soup | pick up the chocolate pudding and place it in the basket and pick up the alphabet soup and place it in the basket |
| 81 | `t08_b_alphabet_soup_ba` | T8 | ba | chocolate_pudding | alphabet_soup | pick up the alphabet soup and place it in the basket and pick up the chocolate pudding and place it in the basket |
| 82 | `t08_b_bbq_sauce_ab` | T8 | ab | chocolate_pudding | bbq_sauce | pick up the chocolate pudding and place it in the basket and pick up the bbq sauce and place it in the basket |
| 83 | `t08_b_bbq_sauce_ba` | T8 | ba | chocolate_pudding | bbq_sauce | pick up the bbq sauce and place it in the basket and pick up the chocolate pudding and place it in the basket |
| 84 | `t08_b_ketchup_ab` | T8 | ab | chocolate_pudding | ketchup | pick up the chocolate pudding and place it in the basket and pick up the ketchup and place it in the basket |
| 85 | `t08_b_ketchup_ba` | T8 | ba | chocolate_pudding | ketchup | pick up the ketchup and place it in the basket and pick up the chocolate pudding and place it in the basket |
| 86 | `t08_b_orange_juice_ab` | T8 | ab | chocolate_pudding | orange_juice | pick up the chocolate pudding and place it in the basket and pick up the orange juice and place it in the basket |
| 87 | `t08_b_orange_juice_ba` | T8 | ba | chocolate_pudding | orange_juice | pick up the orange juice and place it in the basket and pick up the chocolate pudding and place it in the basket |
| 88 | `t08_b_salad_dressing_ab` | T8 | ab | chocolate_pudding | salad_dressing | pick up the chocolate pudding and place it in the basket and pick up the salad dressing and place it in the basket |
| 89 | `t08_b_salad_dressing_ba` | T8 | ba | chocolate_pudding | salad_dressing | pick up the salad dressing and place it in the basket and pick up the chocolate pudding and place it in the basket |
| 90 | `t09_b_bbq_sauce_ab` | T9 | ab | orange_juice | bbq_sauce | pick up the orange juice and place it in the basket and pick up the bbq sauce and place it in the basket |
| 91 | `t09_b_bbq_sauce_ba` | T9 | ba | orange_juice | bbq_sauce | pick up the bbq sauce and place it in the basket and pick up the orange juice and place it in the basket |
| 92 | `t09_b_butter_ab` | T9 | ab | orange_juice | butter | pick up the orange juice and place it in the basket and pick up the butter and place it in the basket |
| 93 | `t09_b_butter_ba` | T9 | ba | orange_juice | butter | pick up the butter and place it in the basket and pick up the orange juice and place it in the basket |
| 94 | `t09_b_chocolate_pudding_ab` | T9 | ab | orange_juice | chocolate_pudding | pick up the orange juice and place it in the basket and pick up the chocolate pudding and place it in the basket |
| 95 | `t09_b_chocolate_pudding_ba` | T9 | ba | orange_juice | chocolate_pudding | pick up the chocolate pudding and place it in the basket and pick up the orange juice and place it in the basket |
| 96 | `t09_b_ketchup_ab` | T9 | ab | orange_juice | ketchup | pick up the orange juice and place it in the basket and pick up the ketchup and place it in the basket |
| 97 | `t09_b_ketchup_ba` | T9 | ba | orange_juice | ketchup | pick up the ketchup and place it in the basket and pick up the orange juice and place it in the basket |
| 98 | `t09_b_salad_dressing_ab` | T9 | ab | orange_juice | salad_dressing | pick up the orange juice and place it in the basket and pick up the salad dressing and place it in the basket |
| 99 | `t09_b_salad_dressing_ba` | T9 | ba | orange_juice | salad_dressing | pick up the salad dressing and place it in the basket and pick up the orange juice and place it in the basket |

说明：`_ab` = 原目标 A 先；`_ba` = 提升目标 B 先。所有候选场景/init 与源任务一致（init 复制源任务 .pruned_init）。
