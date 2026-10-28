# LIBERO-OBJECT「场景内双目标（双抓取）」候选任务清单

## 设计

- **不合并场景、不新增物体**：沿用每个任务原有的场景（basket + 6 个可操作物体，7 个刚体，qpos 不变）。
- 原目标物 A 保持为目标；从 5 个干扰物中选 **1 个提升为第二个目标 B**，剩余 4 个继续作为干扰项。
- goal 由单原子改为 `(And (In A basket_1_contain_region) (In B basket_1_contain_region))`；`:obj_of_interest`=A∪B；`:language` = 两个官方 instruction 用 " and " 连接。
- **`:objects`/`:regions`/`:init` 完全不变，init 状态直接复用源任务 `.pruned_init`**（同一场景、同一组刚体）→ 无需 joint 名映射/重采样/新增槽位。
- B 的选取：任何干扰物类型都恰好是另一个任务的原始目标（10 个类型各作为目标 1 次），即 B 都是**已验证过可被操作的目标类型**；pi05 在 10 个原始 OBJECT 任务上 baseline 10/10。
- 每个场景 5 个候选（5 个干扰物各当一次 B）→ **共 50 个候选**。

## 逐任务候选清单（按 B 的初始槽位 R0→R4 排序）

### T0：A = **alphabet_soup**（任务 `pick_up_the_alphabet_soup_and_place_it_in_the_basket`）

| B（提升为第二目标） | B 初始槽位 | B 的原生任务（作为目标） | 剩余 4 个干扰项 | 候选 id |
|---|---|---|---|---|
| **salad_dressing** | R0 | T2 | cream_cheese, milk, tomato_sauce, butter | `t00_b_salad_dressing` |
| **cream_cheese** | R1 | T1 | salad_dressing, milk, tomato_sauce, butter | `t00_b_cream_cheese` |
| **milk** | R2 | T7 | salad_dressing, cream_cheese, tomato_sauce, butter | `t00_b_milk` |
| **tomato_sauce** | R3 | T5 | salad_dressing, cream_cheese, milk, butter | `t00_b_tomato_sauce` |
| **butter** | R4 | T6 | salad_dressing, cream_cheese, milk, tomato_sauce | `t00_b_butter` |

合并 instruction（示例按 B 槽位 R0 给出，其余同理）：

- `t00_b_salad_dressing`: pick up the alphabet soup and place it in the basket and pick up the salad dressing and place it in the basket
- `t00_b_cream_cheese`: pick up the alphabet soup and place it in the basket and pick up the cream cheese and place it in the basket
- `t00_b_milk`: pick up the alphabet soup and place it in the basket and pick up the milk and place it in the basket
- `t00_b_tomato_sauce`: pick up the alphabet soup and place it in the basket and pick up the tomato sauce and place it in the basket
- `t00_b_butter`: pick up the alphabet soup and place it in the basket and pick up the butter and place it in the basket

### T1：A = **cream_cheese**（任务 `pick_up_the_cream_cheese_and_place_it_in_the_basket`）

| B（提升为第二目标） | B 初始槽位 | B 的原生任务（作为目标） | 剩余 4 个干扰项 | 候选 id |
|---|---|---|---|---|
| **alphabet_soup** | R0 | T0 | milk, tomato_sauce, butter, orange_juice | `t01_b_alphabet_soup` |
| **milk** | R1 | T7 | alphabet_soup, tomato_sauce, butter, orange_juice | `t01_b_milk` |
| **tomato_sauce** | R2 | T5 | alphabet_soup, milk, butter, orange_juice | `t01_b_tomato_sauce` |
| **butter** | R3 | T6 | alphabet_soup, milk, tomato_sauce, orange_juice | `t01_b_butter` |
| **orange_juice** | R4 | T9 | alphabet_soup, milk, tomato_sauce, butter | `t01_b_orange_juice` |

合并 instruction（示例按 B 槽位 R0 给出，其余同理）：

- `t01_b_alphabet_soup`: pick up the cream cheese and place it in the basket and pick up the alphabet soup and place it in the basket
- `t01_b_milk`: pick up the cream cheese and place it in the basket and pick up the milk and place it in the basket
- `t01_b_tomato_sauce`: pick up the cream cheese and place it in the basket and pick up the tomato sauce and place it in the basket
- `t01_b_butter`: pick up the cream cheese and place it in the basket and pick up the butter and place it in the basket
- `t01_b_orange_juice`: pick up the cream cheese and place it in the basket and pick up the orange juice and place it in the basket

### T2：A = **salad_dressing**（任务 `pick_up_the_salad_dressing_and_place_it_in_the_basket`）

| B（提升为第二目标） | B 初始槽位 | B 的原生任务（作为目标） | 剩余 4 个干扰项 | 候选 id |
|---|---|---|---|---|
| **ketchup** | R0 | T4 | alphabet_soup, cream_cheese, milk, tomato_sauce | `t02_b_ketchup` |
| **alphabet_soup** | R1 | T0 | ketchup, cream_cheese, milk, tomato_sauce | `t02_b_alphabet_soup` |
| **cream_cheese** | R2 | T1 | ketchup, alphabet_soup, milk, tomato_sauce | `t02_b_cream_cheese` |
| **milk** | R3 | T7 | ketchup, alphabet_soup, cream_cheese, tomato_sauce | `t02_b_milk` |
| **tomato_sauce** | R4 | T5 | ketchup, alphabet_soup, cream_cheese, milk | `t02_b_tomato_sauce` |

合并 instruction（示例按 B 槽位 R0 给出，其余同理）：

- `t02_b_ketchup`: pick up the salad dressing and place it in the basket and pick up the ketchup and place it in the basket
- `t02_b_alphabet_soup`: pick up the salad dressing and place it in the basket and pick up the alphabet soup and place it in the basket
- `t02_b_cream_cheese`: pick up the salad dressing and place it in the basket and pick up the cream cheese and place it in the basket
- `t02_b_milk`: pick up the salad dressing and place it in the basket and pick up the milk and place it in the basket
- `t02_b_tomato_sauce`: pick up the salad dressing and place it in the basket and pick up the tomato sauce and place it in the basket

### T3：A = **bbq_sauce**（任务 `pick_up_the_bbq_sauce_and_place_it_in_the_basket`）

| B（提升为第二目标） | B 初始槽位 | B 的原生任务（作为目标） | 剩余 4 个干扰项 | 候选 id |
|---|---|---|---|---|
| **chocolate_pudding** | R0 | T8 | ketchup, salad_dressing, alphabet_soup, cream_cheese | `t03_b_chocolate_pudding` |
| **ketchup** | R1 | T4 | chocolate_pudding, salad_dressing, alphabet_soup, cream_cheese | `t03_b_ketchup` |
| **salad_dressing** | R2 | T2 | chocolate_pudding, ketchup, alphabet_soup, cream_cheese | `t03_b_salad_dressing` |
| **alphabet_soup** | R3 | T0 | chocolate_pudding, ketchup, salad_dressing, cream_cheese | `t03_b_alphabet_soup` |
| **cream_cheese** | R4 | T1 | chocolate_pudding, ketchup, salad_dressing, alphabet_soup | `t03_b_cream_cheese` |

合并 instruction（示例按 B 槽位 R0 给出，其余同理）：

- `t03_b_chocolate_pudding`: pick up the bbq sauce and place it in the basket and pick up the chocolate pudding and place it in the basket
- `t03_b_ketchup`: pick up the bbq sauce and place it in the basket and pick up the ketchup and place it in the basket
- `t03_b_salad_dressing`: pick up the bbq sauce and place it in the basket and pick up the salad dressing and place it in the basket
- `t03_b_alphabet_soup`: pick up the bbq sauce and place it in the basket and pick up the alphabet soup and place it in the basket
- `t03_b_cream_cheese`: pick up the bbq sauce and place it in the basket and pick up the cream cheese and place it in the basket

### T4：A = **ketchup**（任务 `pick_up_the_ketchup_and_place_it_in_the_basket`）

| B（提升为第二目标） | B 初始槽位 | B 的原生任务（作为目标） | 剩余 4 个干扰项 | 候选 id |
|---|---|---|---|---|
| **bbq_sauce** | R0 | T3 | salad_dressing, alphabet_soup, cream_cheese, milk | `t04_b_bbq_sauce` |
| **salad_dressing** | R1 | T2 | bbq_sauce, alphabet_soup, cream_cheese, milk | `t04_b_salad_dressing` |
| **alphabet_soup** | R2 | T0 | bbq_sauce, salad_dressing, cream_cheese, milk | `t04_b_alphabet_soup` |
| **cream_cheese** | R3 | T1 | bbq_sauce, salad_dressing, alphabet_soup, milk | `t04_b_cream_cheese` |
| **milk** | R4 | T7 | bbq_sauce, salad_dressing, alphabet_soup, cream_cheese | `t04_b_milk` |

合并 instruction（示例按 B 槽位 R0 给出，其余同理）：

- `t04_b_bbq_sauce`: pick up the ketchup and place it in the basket and pick up the bbq sauce and place it in the basket
- `t04_b_salad_dressing`: pick up the ketchup and place it in the basket and pick up the salad dressing and place it in the basket
- `t04_b_alphabet_soup`: pick up the ketchup and place it in the basket and pick up the alphabet soup and place it in the basket
- `t04_b_cream_cheese`: pick up the ketchup and place it in the basket and pick up the cream cheese and place it in the basket
- `t04_b_milk`: pick up the ketchup and place it in the basket and pick up the milk and place it in the basket

### T5：A = **tomato_sauce**（任务 `pick_up_the_tomato_sauce_and_place_it_in_the_basket`）

| B（提升为第二目标） | B 初始槽位 | B 的原生任务（作为目标） | 剩余 4 个干扰项 | 候选 id |
|---|---|---|---|---|
| **milk** | R0 | T7 | butter, orange_juice, chocolate_pudding, bbq_sauce | `t05_b_milk` |
| **butter** | R1 | T6 | milk, orange_juice, chocolate_pudding, bbq_sauce | `t05_b_butter` |
| **orange_juice** | R2 | T9 | milk, butter, chocolate_pudding, bbq_sauce | `t05_b_orange_juice` |
| **chocolate_pudding** | R3 | T8 | milk, butter, orange_juice, bbq_sauce | `t05_b_chocolate_pudding` |
| **bbq_sauce** | R4 | T3 | milk, butter, orange_juice, chocolate_pudding | `t05_b_bbq_sauce` |

合并 instruction（示例按 B 槽位 R0 给出，其余同理）：

- `t05_b_milk`: pick up the tomato sauce and place it in the basket and pick up the milk and place it in the basket
- `t05_b_butter`: pick up the tomato sauce and place it in the basket and pick up the butter and place it in the basket
- `t05_b_orange_juice`: pick up the tomato sauce and place it in the basket and pick up the orange juice and place it in the basket
- `t05_b_chocolate_pudding`: pick up the tomato sauce and place it in the basket and pick up the chocolate pudding and place it in the basket
- `t05_b_bbq_sauce`: pick up the tomato sauce and place it in the basket and pick up the bbq sauce and place it in the basket

### T6：A = **butter**（任务 `pick_up_the_butter_and_place_it_in_the_basket`）

| B（提升为第二目标） | B 初始槽位 | B 的原生任务（作为目标） | 剩余 4 个干扰项 | 候选 id |
|---|---|---|---|---|
| **tomato_sauce** | R0 | T5 | orange_juice, chocolate_pudding, bbq_sauce, ketchup | `t06_b_tomato_sauce` |
| **orange_juice** | R1 | T9 | tomato_sauce, chocolate_pudding, bbq_sauce, ketchup | `t06_b_orange_juice` |
| **chocolate_pudding** | R2 | T8 | tomato_sauce, orange_juice, bbq_sauce, ketchup | `t06_b_chocolate_pudding` |
| **bbq_sauce** | R3 | T3 | tomato_sauce, orange_juice, chocolate_pudding, ketchup | `t06_b_bbq_sauce` |
| **ketchup** | R4 | T4 | tomato_sauce, orange_juice, chocolate_pudding, bbq_sauce | `t06_b_ketchup` |

合并 instruction（示例按 B 槽位 R0 给出，其余同理）：

- `t06_b_tomato_sauce`: pick up the butter and place it in the basket and pick up the tomato sauce and place it in the basket
- `t06_b_orange_juice`: pick up the butter and place it in the basket and pick up the orange juice and place it in the basket
- `t06_b_chocolate_pudding`: pick up the butter and place it in the basket and pick up the chocolate pudding and place it in the basket
- `t06_b_bbq_sauce`: pick up the butter and place it in the basket and pick up the bbq sauce and place it in the basket
- `t06_b_ketchup`: pick up the butter and place it in the basket and pick up the ketchup and place it in the basket

### T7：A = **milk**（任务 `pick_up_the_milk_and_place_it_in_the_basket`）

| B（提升为第二目标） | B 初始槽位 | B 的原生任务（作为目标） | 剩余 4 个干扰项 | 候选 id |
|---|---|---|---|---|
| **cream_cheese** | R0 | T1 | tomato_sauce, butter, orange_juice, chocolate_pudding | `t07_b_cream_cheese` |
| **tomato_sauce** | R1 | T5 | cream_cheese, butter, orange_juice, chocolate_pudding | `t07_b_tomato_sauce` |
| **butter** | R2 | T6 | cream_cheese, tomato_sauce, orange_juice, chocolate_pudding | `t07_b_butter` |
| **orange_juice** | R3 | T9 | cream_cheese, tomato_sauce, butter, chocolate_pudding | `t07_b_orange_juice` |
| **chocolate_pudding** | R4 | T8 | cream_cheese, tomato_sauce, butter, orange_juice | `t07_b_chocolate_pudding` |

合并 instruction（示例按 B 槽位 R0 给出，其余同理）：

- `t07_b_cream_cheese`: pick up the milk and place it in the basket and pick up the cream cheese and place it in the basket
- `t07_b_tomato_sauce`: pick up the milk and place it in the basket and pick up the tomato sauce and place it in the basket
- `t07_b_butter`: pick up the milk and place it in the basket and pick up the butter and place it in the basket
- `t07_b_orange_juice`: pick up the milk and place it in the basket and pick up the orange juice and place it in the basket
- `t07_b_chocolate_pudding`: pick up the milk and place it in the basket and pick up the chocolate pudding and place it in the basket

### T8：A = **chocolate_pudding**（任务 `pick_up_the_chocolate_pudding_and_place_it_in_the_basket`）

| B（提升为第二目标） | B 初始槽位 | B 的原生任务（作为目标） | 剩余 4 个干扰项 | 候选 id |
|---|---|---|---|---|
| **orange_juice** | R0 | T9 | bbq_sauce, ketchup, salad_dressing, alphabet_soup | `t08_b_orange_juice` |
| **bbq_sauce** | R1 | T3 | orange_juice, ketchup, salad_dressing, alphabet_soup | `t08_b_bbq_sauce` |
| **ketchup** | R2 | T4 | orange_juice, bbq_sauce, salad_dressing, alphabet_soup | `t08_b_ketchup` |
| **salad_dressing** | R3 | T2 | orange_juice, bbq_sauce, ketchup, alphabet_soup | `t08_b_salad_dressing` |
| **alphabet_soup** | R4 | T0 | orange_juice, bbq_sauce, ketchup, salad_dressing | `t08_b_alphabet_soup` |

合并 instruction（示例按 B 槽位 R0 给出，其余同理）：

- `t08_b_orange_juice`: pick up the chocolate pudding and place it in the basket and pick up the orange juice and place it in the basket
- `t08_b_bbq_sauce`: pick up the chocolate pudding and place it in the basket and pick up the bbq sauce and place it in the basket
- `t08_b_ketchup`: pick up the chocolate pudding and place it in the basket and pick up the ketchup and place it in the basket
- `t08_b_salad_dressing`: pick up the chocolate pudding and place it in the basket and pick up the salad dressing and place it in the basket
- `t08_b_alphabet_soup`: pick up the chocolate pudding and place it in the basket and pick up the alphabet soup and place it in the basket

### T9：A = **orange_juice**（任务 `pick_up_the_orange_juice_and_place_it_in_the_basket`）

| B（提升为第二目标） | B 初始槽位 | B 的原生任务（作为目标） | 剩余 4 个干扰项 | 候选 id |
|---|---|---|---|---|
| **butter** | R0 | T6 | chocolate_pudding, bbq_sauce, ketchup, salad_dressing | `t09_b_butter` |
| **chocolate_pudding** | R1 | T8 | butter, bbq_sauce, ketchup, salad_dressing | `t09_b_chocolate_pudding` |
| **bbq_sauce** | R2 | T3 | butter, chocolate_pudding, ketchup, salad_dressing | `t09_b_bbq_sauce` |
| **ketchup** | R3 | T4 | butter, chocolate_pudding, bbq_sauce, salad_dressing | `t09_b_ketchup` |
| **salad_dressing** | R4 | T2 | butter, chocolate_pudding, bbq_sauce, ketchup | `t09_b_salad_dressing` |

合并 instruction（示例按 B 槽位 R0 给出，其余同理）：

- `t09_b_butter`: pick up the orange juice and place it in the basket and pick up the butter and place it in the basket
- `t09_b_chocolate_pudding`: pick up the orange juice and place it in the basket and pick up the chocolate pudding and place it in the basket
- `t09_b_bbq_sauce`: pick up the orange juice and place it in the basket and pick up the bbq sauce and place it in the basket
- `t09_b_ketchup`: pick up the orange juice and place it in the basket and pick up the ketchup and place it in the basket
- `t09_b_salad_dressing`: pick up the orange juice and place it in the basket and pick up the salad dressing and place it in the basket

## 汇总

- 候选总数：**50**（10 场景 × 5）；其中涉及的目标物对（无序）去重后为 N 个，部分目标物对会在两个不同场景中各出现一次（disractor 集合不同，仍是不同任务）。
- 每个物体类型：作为 A 1 次、作为 B 5 次（对应 6 个含它的场景任务）。
- 静态验证应全部通过（goal 两原子均可满足，初始 success=False；无场景/init 改动）；动态主要风险是 pi05 单条组合指令的链式执行（此前跨场景合并 0/4 的失败中包含合并场景第二物体不可达，本设计已消除该因素）。

生成时间：2026-10-23；数据源：官方 benchmark 顺序原版 BDDL 解析（见 object_task_inventory.json）。
