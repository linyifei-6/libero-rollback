# LIBERO-OBJECT 任务扩充实验汇总报告

- 日期：2026-10-25
- 范围：本会话围绕 LIBERO-OBJECT 套件（10 个原生任务）做的全部「任务扩充 / 组合 / 筛选 / 动态验证」实验
- 一句话结论：**OBJECT 场景内「提升第二目标」构造的 100 个双抓取候选是可行的任务扩充路线：静态 100/100 通过，pi05 零样本 300 episodes 得到 12 次成功（4.0%），其中 6 个候选至少成功 1 次、5 个候选跨 ≥2 seeds 成功、1 个候选 3/3 seeds 全成功；而跨任务合并场景的路线（45 组合→30 可用）动态 0/7 成功，已放弃。**

---

## 1. 实验全景（一共做了多少实验）

| # | 实验 | 构造/筛选规模 | 动态 episodes | 关键结果 |
|---|---|---|---|---|
| E1 | OBJECT 同套件「合并场景」静态构造 | C(10,2)=45 对 → 物体并集 union=7/8/9 各 10 对（共 30 对）+ union=10 的 15 对跳过；另 2 个原型 | — | **静态 30/30 通过，原型 2/2 通过** |
| E2 | 合并场景动态验证 | 4 对 object-pilot + 2 个原型措辞变体 + 1 个 staged + 2 个单物体控制 | **9**（7 组合 + 2 单任务控制） | 组合任务 **0/7**；单任务控制 soup 1/1（154 步）、cream cheese 0/1（600 步）→ 合并场景第二物体可达性有问题 |
| E3 | 场景内双目标候选 v1 构造 | 10 场景 × 5 个干扰物提升 = 50 组合 → ×2 顺序 = **100 个候选** | — | 静态 **100/100** 通过 |
| E4 | 运行时通道修复 + 预检 | 静态复验 100/100；2 个候选 ×（seed0；seeds1,2）真实仿真预检 | **6**（短 episode，20 步） | 全部 PASS：instruction/atoms/init 行 sha256 与设计一致 |
| E5 | v1 旧措辞三 seed 动态 | 100 候选 × seeds 0/1/2 | **300** | 0 成功；**但该批 runtime 未加载候选 .pruned_init（init 语义错误），结果作废，仅作历史参考** |
| E6 | v2 措辞草稿（`pick up the A and the B and place them in the basket`） | 100 个候选定义 | 0（未运行） | 静态 **100/100** 通过 |
| E7 | v3 措辞（LIBERO-10 模板）三 seed 动态 | 100 候选 × seeds 0/1/2 | **300** | **12 成功 = 4.0%**；见 §4 |
| 合计 | 7 组实验 | 合并 30 + 场景内 100 个候选（三代指令共 300 个 bddl 定义） | **有效动态 306 + 作废 300 + 预检 6** | 见下 |

> 说明：E5 的 300 条与 E7 的 300 条是同一批候选取不同指令/运行时设置，不重复计入有效结论；E2 的 9 条属于合并场景路线。

按 **seed 实验批次**统计：合并场景路线只用了 **1 个 seed 批次**（seed0，9 episodes）；v1 旧措辞用了 **3 个 seed 批次**（seeds 0/1/2，共 300 episodes，作废）；v3 模板用了 **3 个 seed 批次**（seeds 0/1/2，共 300 episodes，有效）→ **共 7 个 seed 批次**，其中有效 3 个（v3）。另有 6 条运行时预检短 episode（20 步）不计入模型实验。

---

## 2. 从多少组合任务中筛选出多少候选任务（筛选漏斗）

### 路线 A：同套件「合并场景」组合（已放弃）
1. 10 个 OBJECT 任务两两组合 = **45 对**（每任务「1 个目标 + basket + 5 个干扰物」，45 对在逻辑上全部兼容）。
2. 按合并后物体并集筛选：union=7 → 10 对、union=8 → 10 对、union=9 → 10 对、union=10 → 15 对；**union≤9 的 30 对可构造**（需要新增 1/2/3 个地面槽位），union=10 的 15 对需第 4 个安全槽位 → **跳过**。
3. 静态验证：**30/30 通过**（joint-name init 合成、50 行往返、0 碰撞、初始 success=False、双目标可满足性），2 个原型 2/2。
4. 动态筛选：试跑 **7 个组合任务**（object-pilot 4 + 措辞变体 2 + staged 1）→ **0/7 成功**；单任务控制暴露合并场景第二物体不可达（soup 可解、cream cheese 600 步失败）。→ **整条路线放弃**。

### 路线 B：场景内「提升第二目标」（采用）
1. 保留每个 OBJECT 任务的原场景（basket + 6 可操作物体 = 7 刚体，qpos/init 不变）；原目标 A 保留，从 5 个干扰物中提升 1 个为第二目标 B，剩 4 个干扰项 → **10 场景 × 5 个 B = 50 个组合**。
2. 每个组合生成 A 先 / B 先两种指令顺序 → **100 个候选任务**。
3. 三代指令措辞（v1 旧措辞、v2 草稿、v3 LIBERO-10 模板 `put both the A and the B in the basket`）各 100 个定义：**v1/v2/v3 静态验证均 100/100 通过**。
4. 动态筛选（v3，唯一有效批次）：100 候选 × 3 seeds = **300 episodes** → **6 个候选至少成功 1 次** → **5 个候选 ≥2 seeds 成功** → **1 个候选 3/3 seeds 全成功**。

### 一句话漏斗
**45 个合并场景组合 → 30 个可构造（动态 0/7，放弃）；50 个场景内组合 → 100 个候选 → 静态 100/100 → 300 episodes → 6 个成功候选 → 5 个跨 seed 稳定 → 1 个 3/3。**

---

## 3. 有效动态结果（v3：100 候选 × 3 seeds = 300 episodes）

| 指标 | 结果 |
|---|---|
| episodes | 300 |
| success | **12/300 = 4.0%** |
| 按 seed | seed0 5/100、seed1 2/100、seed2 5/100 |
| 至少 1 次成功的候选 | 6/100 |
| ≥2 seeds 成功的候选 | 5/100 |
| 3/3 seeds 全成功候选 | 1/100（`t00_b_cream_cheese_ab`） |
| 完成子任务数分布 | 0 个 17；1 个 271；2 个 12（12 条全部 success） |
| 首个完成对象 | A 252 / B 31 / 无 17 |
| 按顺序 | `_ab`（A 先）8/150（5.3%）；`_ba`（B 先）4/150（2.7%） |
| 按场景 | T0 **7/30（23.3%）**、T1 2/30（6.7%）、T5 3/30（10%）；其余 7 个场景 0 |
| 按 B | cream_cheese 5/30、butter 5/30、tomato_sauce 2/30；其余 B 全 0 |

### 跨 seed 稳定成功候选（核心结果）

| candidate | instruction | 3-seed 成功 | steps（seed0/1/2） |
|---|---|---|---|
| **t00_b_cream_cheese_ab** | put both the alphabet soup and the cream cheese in the basket | **3/3** | 267 / 331 / 262 |
| t00_b_cream_cheese_ba | put both the cream cheese and the alphabet soup in the basket | 2/3（0,2） | 316 / fail / 597 |
| t00_b_tomato_sauce_ab | put both the alphabet soup and the tomato sauce in the basket | 2/3（0,2） | 408 / fail / 351 |
| t01_b_butter_ab | put both the cream cheese and the butter in the basket | 2/3（0,2） | 412 / fail / 331 |
| t05_b_butter_ba | put both the butter and the tomato sauce in the basket | 2/3（0,2） | 318 / fail / 553 |
| t05_b_butter_ab | put both the tomato sauce and the butter in the basket | 1/3（1） | fail / 465 / fail |

### 3.1 两种候选筛选标准（按 v3 有效 300 episodes）

| 标准 | 定义 | 候选数 | 名单 |
|---|---|---|---|
| ① **至少成功一次** | 3 seeds 中 ≥1 次 success | **6 / 100** | `t00_b_cream_cheese_ab`（3/3）、`t00_b_cream_cheese_ba`（2/3）、`t00_b_tomato_sauce_ab`（2/3）、`t01_b_butter_ab`（2/3）、`t05_b_butter_ba`（2/3）、`t05_b_butter_ab`（1/3） |
| ② **稳定候选**（成功率 >50%） | 3 seeds 中 ≥2 次 success（2/3 = 66.7% 或 3/3 = 100%） | **5 / 100** | 上述 6 个中除 `t05_b_butter_ab`（1/3 = 33.3%）外的 5 个：1 个 3/3 + 4 个 2/3 |

> 注：每候选只有 3 个 seed episode，因此「成功率 >50%」等价于「3 个 seed 中至少成功 2 个」。若将标准放宽为成功率 ≥50%，在 3 次二元实验中仍是同一组 5 个候选（2/3 与 3/3），数量不变。

---

## 4. 有意义的发现

1. **OBJECT 套件天然适合"双物体入篮"组合**：10 个任务共享同一个 basket 与同一套 6 个物体槽位，45 对目标在逻辑上全部兼容（无冲突），这与 GOAL 套件存在"同物体两个位置"冲突形成鲜明对比。
2. **合并场景路线可行但动态不可用**：静态 30/30 通过（含 joint-name init 合成、50 行零碰撞），但动态 0/7；单任务控制显示合并场景中第二个物体可达性/摆放有问题（soup 1/1 成功、cream cheese 0/1）——失败不只是"组合指令链式执行"，还有场景构造问题。
3. **场景内"提升第二目标"是更优的构造方式**：不合并场景、不新增槽位、不重采样 init，直接把干扰物提升为目标；50 个组合扩展为 100 个候选，构建与验证成本远低于合并路线。
4. **指令措辞是决定性变量（但需注意对照组不完美）**：v1 旧措辞（`pick up A ... and pick up B ...`）在 300 条历史运行中 0 成功，而 v3 的 LIBERO-10 官方模板（`put both the A and the B in the basket`）在 300 条中得到 12 成功（4.0%）。需说明：v1 那批运行同时存在 init 语义错误（未加载候选 .pruned_init），因此两批差异不能全部归因于措辞；但"模板措辞 + 正确 init"下确实出现了非零成功率。
5. **pi05 的链式执行仍是主瓶颈**：271/300 只完成恰好 1 个子任务后停滞，17 条 0 个；真正完成两段（12 条）才成功。失败模式是"抓一个进篮后停下"，而不是抓取本身失败。
6. **场景/位置先验强于指令顺序**：首个完成对象 A 占 252/300（A 固定在源任务 `target_object_region`），B 仅 31；`_ab`（A 先）5.3% vs `_ba`（B 先）2.7%，顺序只有弱影响，且两种顺序都有成功案例。
7. **成功高度集中**：T0 场景占 7/12 成功（23.3%），T1/T5 少量，其余 7 个场景 0；B 为 cream_cheese / butter / tomato_sauce 占全部成功——说明场景与物体组合的可操作性比"多给任务"更重要。
8. **存在可复现的稳定候选**：`t00_b_cream_cheese_ab` 在 3/3 seeds 全成功（262–331 步），另有 4 个候选 2/3 成功；这批候选可作为后续 rollback 用例原型与任务基数扩充的可靠基底。
9. **与 LIBERO-10 04/05/06 的关系**：任务是"同模板族、指令文本部分重合、场景不同"——`t00_b_tomato_sauce_ab` 与 LIBERO-10/05 逐字一致，cream cheese 两个候选与 /04、`t01_b_butter_ab` 与 /06 近似（`cream cheese` vs `cream cheese box`），但场景/物体资产/初始状态完全不同；这可能是部分成功的有利因素，不能把结果简单外推为"新任务泛化能力"。
10. **实验基础设施教训**：曾因 runtime overlay 未加载候选 `.pruned_init` 导致 300 条结果作废；此后建立了"静态校验 + 运行时预检（instruction/atoms/init 行 sha256 一致）+ 视频证据"的三层验证流程，后续 300 条结果均通过预检。

---

## 5. 产物与证据索引

| 内容 | 位置 |
|---|---|
| v3 标准模板报告（100 候选 × 3 seeds，300 视频） | [report-template/index.html](runs/object-inscene-100-20261023/report-template/index.html) |
| v3 数据（300 episodes 逐条 + 聚合） | [evidence.json](runs/object-inscene-100-20261023/report-template/evidence.json) |
| v3 候选定义（100 个，含 v1/v2/v3 指令） | [candidates-v3.json](runs/object-inscene-100-20261023/candidates-v3.json) |
| v3 静态验证 / 预检证据 | [static-validation-v3.json](runs/object-inscene-100-20261023/static-validation-v3.json)、[preflight 证据](runs/object-inscene-100-20261023/logs/preflight-v3-post.json) |
| docs 永久备份（报告 + 300 视频 + 证据） | [docs 备份](docs/experiments-20261019/object_inscene_100_seed012_v3_video_template/index.html) |
| 单 seed 报告（seed0） | [seed0 报告](runs/object-inscene-100-20261023/report/index.html) |
| 合并场景路线：审计与静态/动态记录 | [合并任务实验记录](docs/libero-experiments-20261019.md)、[combined evidence](docs/experiments-20261019/combined_twosubtask.json) |
| 合并场景 OBJECT 产物/评估 | `runs/combined-tasks-20261019/artifacts/object-scout/`（可行性报告 + 原型配方） |
| 候选 case 列表 | [CASE_LIST-v3.md](runs/object-inscene-100-20261023/CASE_LIST-v3.md) |

---

## 6. 局限与下一步

- 每个候选仅 3 seeds（非官方 50 trials）；12 条成功为小样本，成功率点估计不稳定。
- pi05 使用 OpenPI PyTorch 后端；自定义场景 `max_steps=600 / replan=10` 非官方协议，不能与官方 pi05 数字直接对比。
- v1 旧措辞的 300 条因 init 语义错误作废，措辞效应需要一次"正确 init + 旧措辞"的对照实验才能定量（v2 未运行）。
- 下一步建议：
  1. 用 `t00_b_cream_cheese_ab`（3/3）+ 4 个 2/3 候选做 **rollback 用例原型**（完成 A → 撤销 → 自修复再完成 B）；
  2. 补跑正确 init 的 v2 对照，量化措辞效应；
  3. 沿 T0/T1/T5 场景扩展 B 组合，并尝试对 271 条"完成 1 个"的失败样本加 staged/instruction-switch，量化能否把 4.0% 提升。