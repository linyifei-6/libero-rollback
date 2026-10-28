# LIBERO-90 单目标任务的双目标组合：候选构造方法与候选任务清单

> **状态**：静态设计与候选清单（只读解析 LIBERO-90 BDDL + 参考本仓库已完成的 LIBERO-GOAL / LIBERO-OBJECT 双目标构造实验）。**本轮没有在 LIBERO-90 上跑任何仿真**；所有"可行性/优先级"是构造层判断，动态可解性必须以第 10 节的验证漏斗实测为准。
> **口径**：任务编号 `00–89` 沿用 [`libero-90-task-inventory.md`](libero-90-task-inventory.md) 的 `tasks_info.txt` 顺序（不是 benchmark 字母序，映射见 §8.2）；指令文本一律使用 **benchmark 官方 language（文件名派生）**，不是 BDDL 内联 `:language`（两者有 4 条不一致，见 §1.4）。
> **分场景 HTML 报告**：[`runs/libero-90-combos-20261025/report/index.html`](../runs/libero-90-combos-20261025/report/index.html)（20 个场景 × 单任务 / 模板化组合指令 / pi0 参考 baseline 视频）。
> **修订 v1（2026-10-25，用户逐场景复核）**：`KITCHEN_SCENE1` 的 `00` 本身已经是双子任务，按用户意见**移出组合池**（KS1 只用 01–04 组合）→ 组合池 **82 条**、M1 **143 对 / 286 ordered**、合计 **322** 个候选。其他场景本轮暂无修改意见；口径源：[`scene_review_decisions.json`](../runs/libero-90-combos-20261025/scene_review_decisions.json)。
> **pi05 × 3 seeds 验证（2026-10-26）**：低难度子集 161 条 × seeds {0,1,2} = 483 episodes → **41 成功 = 8.49%**；**19 个候选 ≥1 次成功、12 个 ≥2 seeds、10 个 3/3 全成功**；T1 模板（put both A and B in C）14.06% 最强。详见 §15 与 [验证报告](../runs/libero-90-easy-pi05-20261026/report/index.html)。
> **去重审计（2026-10-26）**：322 条候选中 **16 条 ordered（8 任务）与 LIBERO-10/LIBERO-90 已有任务完全重复**（7 个 L10 官方任务 + L90/05），另有 42 条 semantic 重复（同 goal 不同环境）。上条 8.49% 含已知 L10 任务贡献：**exact 重复组 23/24 = 95.8% 成功，真正 unique 任务仅 17/387 = 4.39%**。净候选口径：严格去重 306 ordered / 新颖性口径 **258 ordered（129 任务）**。详见 §16 与 [去重审计](../runs/libero-90-combos-20261025/dup-audit/DUPLICATE_AUDIT.md)。
> **按用户口径的处置（2026-10-26）**：**A 类（场景+任务+指令全同）15 条无需验证**（valid 9），**B 类（指令不同）7 条需验证**（已验 4），C 类 42（同 goal 异场景，按"场景重复"定义不算重复），D 类 258 全新。成功候选 19 个中 **A 类 4 条不能计入 rollback 基数**，可用基数 **15 candidates / 11 tasks**（严格全新 C+D = 11/7）。详见 §17 与 [DEDUP_DECISION.md](../runs/libero-90-combos-20261025/dup-audit/DEDUP_DECISION.md)。
> **高难度剩余候选单 seed 验证（2026-10-26）**：去重后剩余 **92 条**（有效 97 − A 类 5；含 M2 33/S1 2/P1 5/P2 36 与跨场景 C 类 16）单 seed0、600 步、双 worker 跑完 → **6/92 = 6.52%**；其中 **4 条是真正新任务（D：LR4 M2 提升任务）**、2 条是 B 类指令变体（L10/00、L10/06 的重复任务）。合并两次验证：**新任务（C+D）成功率 4.01%（22/548）**；rollback 可用成功候选累计 **21 个 / 15 任务**（严格全新 C+D = 15/9）。详见 §18 与 [`runs/libero-90-hard-pi05-20261026/analysis/summary.md`](../runs/libero-90-hard-pi05-20261026/analysis/summary.md)。
> **hard 成功候选 seed1/2 稳定性补测（2026-10-26，verifier PASS 0/0/0）**：6 条成功候选 × seeds{1,2} = 12 episodes → **9/12 = 75%**；合并 seed0 共 **18 eps，15/18 = 83.3%**；**4 条 3/3**（其中 2 条为 L10 重复任务的 B 指令变体、2 条为真正新任务 `LR4_42`）；5 条 ≥2，1 条仅 1。rollback 稳定基数：3/3 候选 easy 10 + hard 4；其中真正新任务累计 5 条（LR3 三条 + LR4_42 两条）、B 指令变体 5 条。详见 §19 与 [`runs/libero-90-hard-success-seeds12-20261026/analysis/summary.md`](../runs/libero-90-hard-success-seeds12-20261026/analysis/summary.md)。
> **hard 全量 92 条 × seeds 1/2 补跑（2026-10-27）**：**184/184 episodes 完成**（seed1 92 + seed2 92），success **9/184 = 4.89%**；合并 3-seed **15/276 = 5.43%**；**新增可用候选 0 条**（seed0 单 seed 已找到全部 6 个成功候选，seed1/2 无漏检补充）→ hard 集合已榨干。3-seed 稳定性确认 **4 条 3/3 + 1 条 ≥2**；分布上 P1/P2 与 class hard **0/108**、C 类 **0/48**，证明这些层需要 staged/instruction-switch 而非继续加 seed。详见 §20 与 [`runs/libero-90-hard-seeds12-full-20261026/analysis/summary.md`](../runs/libero-90-hard-seeds12-full-20261026/analysis/summary.md)。
> **合并 HTML 验证报告（2026-10-27）**：easy 161 + hard 92 两批实验合并 → **253 candidates / 759 episodes / 56 success = 7.38%**（easy 8.49% / hard 5.43%；去重后 novel C+D **3.72%**；25 any / 17 ≥2 / 14 3/3）。报告 [`runs/libero-90-validation-merged-20261027/report/index.html`](../runs/libero-90-validation-merged-20261027/report/index.html)（单文件离线，`--check` 40/40）。
> **官方 LIBERO 5 套件 × pi05 参考评测（2026-10-27）**：130 tasks（SPATIAL/OBJECT/GOAL/10/90）× 单 seed0、max_steps=500、replan=5、**video on** → **69/130 = 53.08%**（LIBERO_90 **29/90 = 32.22%**，其余 4 套件各 100%）；130/130 mp4（43.1MB）全部可解码；队列 wall 3.59h。含视频证据 HTML 报告：[`runs/libero-official-5suites-pi05-20261027/report/index.html`](../runs/libero-official-5suites-pi05-20261027/report/index.html)。详见 §21。
> **组合任务补跑 seeds3/4（2026-10-28）**：253 组合候选（easy161+hard92）× seeds{3,4} = **506 eps** 完成（success **41/506 = 8.10%**；seed3 23、seed4 18；9.83h）。合并 5-seed（253×seeds0–4 = **1265 eps**）→ **97/1265 = 7.67%**；≥2 22 / ≥3 17 / ≥4 14 / **5/5 12**；**新增可用 7 条**（KS5×2、LR2×3、LR3×2）。rollback 稳定基数（剔除 A 重复）：**≥3 = 13 条（B 6 + 新任务 7）**、≥4 = 10、5/5 = 8。详见 §22 与 [`runs/libero-90-combos-seeds345-20261027/analysis/summary.md`](../runs/libero-90-combos-seeds345-20261027/analysis/summary.md)。
> **补 seed5 / 合并 6-seed（2026-10-28）**：253 组合候选 × seed5 = **253 eps** 完成（**24/253 = 9.49%**，5.33h）。合并 6-seed（253×seeds0–5 = **1518 eps**）→ **121/1518 = 7.97%**；至少一次 34 / ≥2 25 / ≥3 20 / ≥4 17 / **6/6 12**（5/5 的 12 条全部维持）；**seed5 新增可用 2 条**（`LR2_37_39_ab`、`LR4_42_43_ba`，均仅 1/6）；rollback 可用基数（A 排除）= **≥3 16 / ≥4 13 / ≥5 9 / 6/6 8**。详见 §23 与 [`runs/libero-90-combos-seed5-20261028/analysis/summary.md`](../runs/libero-90-combos-seed5-20261028/analysis/summary.md)。
> **可行候选清单与逐 seed 完成详情（2026-10-28）**：6 seeds 中任意一次成功的 **34 条可行候选**（B 6 / C 5 / D 19 / A 4；A 为重复对照，usable 30）→ 指令、场景、模板与 **每 seed 完成 steps** 见 §24；rollback 可用基数 ≥3 16 / ≥4 13 / 6/6 8。
> **产物**：模板化候选 [`candidates-instructed.json`](../runs/libero-90-combos-20261025/candidates-instructed.json)、原始机读清单 [`candidates.json`](../runs/libero-90-combos-20261025/candidates.json)、全量表格 [`CASE_LIST.md`](../runs/libero-90-combos-20261025/CASE_LIST.md)、指令模板 [`INSTRUCTION_TEMPLATES.md`](../runs/libero-90-combos-20261025/INSTRUCTION_TEMPLATES.md)、生成器 [`scripts/build_libero90_combos.py`](../scripts/build_libero90_combos.py) / [`scripts/build_libero90_instructions.py`](../scripts/build_libero90_instructions.py)。证据与审计在 `.tmp/libero90-combos/`。

## 0. 一页结论

1. **83 条单目标任务 = 90 − 7 条双目标任务**（BDDL 口径 C）。7 条双目标按"两个 goal 原子指向不同目标实体"判定：`05, 09, 17, 19, 25, 40, 41`；`00/26/27/28` 虽有 2 个原子，但两个原子是同一容器区域上的"开/合 + 放入"谓词对，目标实体只有一个，BDDL 口径下计为单目标（§1.1 有 11/10/7 三种口径对账）。**逐场景复核 v1 后**：KS1 的 `00` 被认定为既有双子任务、移出组合池 → 参与组合的单目标 **82 条**（§1.1 末段）。
2. **组合以场景为单位**：90 条任务分布在 **20 个场景**，同场景内四段结构一致、可直接组合；20 个场景的 `:regions`+`:fixtures` 指纹两两不同，场景之间没有可共享的实例。
3. **同一场景内，所有任务的 `:objects` / `:init` 原子集合 / `:regions` 名集合 / init 宽度完全一致**（20/20 场景各只有 1 个变体）。这使 LIBERO-90 在结构上**等价于 LIBERO-GOAL**（10 任务共享同一场景），因此 **LIBERO-GOAL 的"直接组合"配方可以整体照搬**：以同场景任一任务为模板，只改 `:goal` / `:obj_of_interest` / `:language`，`:objects/:regions/:fixtures/:init` 与 `.pruned_init` 全部复用。
4. 候选规模：**143 个同场景无序对 ×2 指令顺序 = 286 个 ordered 组合（M1 主路线）**（BDDL 口径为 147 对/294 ordered；复核 v1 剔除 KS1/00 的 4 对/8 方向）；**合并指令按 LIBERO-10 / LIBERO-GOAL / LIBERO-OBJECT 已验证的成功任务模板重建**（不是两条官方句子直接拼接，模板见 §7.1）；另有 M2 补充路线 **17 个无序对（×2 = 34 ordered）**、S1 stranded 特殊候选 **1 个无序对（×2 = 2 ordered）**；合计 **286 + 34 + 2 = 322** 个候选任务定义。
5. 合并后目标原子数不恒为 2：147 对里 **138 对是 2 原子、9 对是 3 原子**（与 `00/26/27/28` 这类"同容器双谓词"任务组合时出现），没有 4 原子对。生成器必须按 **去重后的原子并集** 断言，不能硬编码 `==2`。
6. 语义分类（147 对）：**compatible 92 / hard 19 / conflict 29 / degenerate 3**。conflict 与 degenerate 不进动态集；hard 需要固定次序与 staged 协议。
7. **共识：只做同场景组合，不做跨场景**。组合在结构上等价于 LIBERO-GOAL 的直接组合：同场景任务的四段结构一致，只改 goal/obj_of_interest/language、复用 init。
8. 优先级按 rollback 可用性排序：**P0 178 / P1 6 / P2 38 / P3 64**（294 个 ordered M1 候选口径）。P0 = compatible 且指定方向的 s1 是已建模可回退关系（放置类 On/In 或关节类 Open/Close）；Turnon/Turnoff 只能作 s2，作 s1 的 6 个方向降为 P1。
9. **不要预期单条组合指令可解**：本仓库在 GOAL 上实测单指令组合 ≈ **2/47 = 4.3%**（发布口径 2/49 = 4.1%，含 2 条 OBJECT 对照）、OBJECT 场景内提升 **12/300 = 4.0%**；失败模式是"完成一个子任务后停滞"（GOAL 39/45、OBJECT 271/300）。**分阶段指令（staged / instruction-switch）是唯一被验证有效的 workaround**（GOAL 2/3）；第一批候选必须按 staged 协议设计。
10. **先补 83 条单目标的 pi05 baseline**：L90 目前只实测过 11 个候选（10 条两段 + 1 条单段对照 `17`），且仅对照 `17` 通过，83 条单目标任务本身尚未测（`docs/libero-90-baseline-pi05-seed3.md`、`docs/libero-90-baseline-seed-sweep.md`）。在没有单任务可解性基线前，"可行/稳定"筛选没有意义。

## 1. 口径与事实基础

### 1.1 为什么是 7 + 83（三种口径对账）

| 口径 | 判定规则 | 双目标 | 单目标 | 任务编号 |
| --- | --- | --- | --- | --- |
| A. goal 原子数 = 2 | `:goal` 有两个原子（无论是否同一实体） | 11 | 79 | `00 05 09 17 19 25 26 27 28 40 41` |
| B. 有效阶段数 = 2 | 口径 A 且两原子都不在 `:init` 中成立 | 10 | 80 | 口径 A 去掉 `17`（`Turnon` 初始已真） |
| C. 两原子目标实体不同 | 口径 A 且两原子最后一个参数不是同一实体 | **7** | **83** | `05 09 17 19 25 40 41` |

题设的 **7 + 83** 对应口径 C。被计为单目标的 4 条双原子任务是 `00`（`Open drawer` + `In bowl drawer`）、`26/27/28`（`In X drawer` + `Close drawer`）：两个谓词作用于同一个抽屉区域，目标实体只有一个，实际是"容器目标 + 谓词"，不是两个独立目标。
> 这 4 条在 BDDL 口径下仍在 83 池内，组合时会贡献 2 个原子（如 `26` 与 `29` 组合 → 3 原子：`In butter` + `Close` + `In bowl`）。这是 LIBERO-90 与 LIBERO-GOAL（每任务恒 1 原子）的差异，生成器必须支持 N 原子。

**逐场景复核 v1（2026-10-25，用户）**：`KITCHEN_SCENE1` 的 `00`（open the top drawer of the cabinet and put the bowl in it）本身已经是双子任务（`Open` + `In` 两段），按用户意见**不再参与组合**，KS1 只用 `01–04` 两两组合。因此**参与组合的池 = 82 条**，M1 从 147 对/294 ordered 降为 **143 对/286 ordered**；`00` 仍作为 LIBERO-90 既有双子任务保留在任务表/报告里（标注"双目标，已移出组合池"）。其余 19 个场景本轮暂无修改意见；结构相近的 `26/27/28` 未被点名、暂保留在池内（若后续同样确认排除，只需在 [`scene_review_decisions.json`](../runs/libero-90-combos-20261025/scene_review_decisions.json) 追加 decisions 并重跑 4 个生成器）。

### 1.2 20 个场景与 143 个同场景对

| 场景 | 任务数 | 全部任务 | 单目标池 | 场景内对数 | 场景指纹 |
| --- | ---: | --- | --- | ---: | --- |
| `KITCHEN_SCENE1` | 5 | 00, 01, 02, 03, 04 | 01, 02, 03, 04 | 6 | `18fe50f91880dcdb` |
| `KITCHEN_SCENE3` | 4 | 05, 06, 07, 08 | 06, 07, 08 | 3 | `af8be858a1de1ff9` |
| `KITCHEN_SCENE4` | 6 | 09, 10, 11, 12, 13, 14 | 10, 11, 12, 13, 14 | 10 | `ed57d7e79c62c648` |
| `KITCHEN_SCENE6` | 2 | 15, 16 | 15, 16 | 1 | `3a8f631600c98a00` |
| `KITCHEN_SCENE8` | 2 | 17, 18 | 18 | 0 | `652a5269ccad165c` |
| `KITCHEN_SCENE9` | 6 | 19, 20, 21, 22, 23, 24 | 20, 21, 22, 23, 24 | 10 | `3825e47479697a77` |
| `KITCHEN_SCENE10` | 6 | 25, 26, 27, 28, 29, 30 | 26, 27, 28, 29, 30 | 10 | `c3d3600b4c5ef5b2` |
| `LIVING_ROOM_SCENE1` | 4 | 31, 32, 33, 34 | 31, 32, 33, 34 | 6 | `2b017692718510ca` |
| `LIVING_ROOM_SCENE2` | 5 | 35, 36, 37, 38, 39 | 35, 36, 37, 38, 39 | 10 | `1a5d5412fbc12bde` |
| `LIVING_ROOM_SCENE4` | 5 | 40, 41, 42, 43, 44 | 42, 43, 44 | 3 | `46d4ee6d9948a108` |
| `LIVING_ROOM_SCENE5` | 4 | 45, 46, 47, 48 | 45, 46, 47, 48 | 6 | `385d0a003c1dfaf4` |
| `LIVING_ROOM_SCENE6` | 4 | 49, 50, 51, 52 | 49, 50, 51, 52 | 6 | `1a6551427b9abef8` |
| `KITCHEN_SCENE2` | 7 | 53, 54, 55, 56, 57, 58, 59 | 53, 54, 55, 56, 57, 58, 59 | 21 | `9e9fdb0a52c15b8d` |
| `KITCHEN_SCENE5` | 5 | 60, 61, 62, 63, 64 | 60, 61, 62, 63, 64 | 10 | `aec797b5ee6c6f09` |
| `KITCHEN_SCENE7` | 3 | 65, 66, 67 | 65, 66, 67 | 3 | `86a1b9e05b848448` |
| `STUDY_SCENE1` | 4 | 68, 69, 70, 71 | 68, 69, 70, 71 | 6 | `5796efb3ca92716d` |
| `STUDY_SCENE2` | 4 | 72, 73, 74, 75 | 72, 73, 74, 75 | 6 | `fe4f3b06e3e43cc1` |
| `STUDY_SCENE3` | 5 | 76, 77, 78, 79, 80 | 76, 77, 78, 79, 80 | 10 | `31ab352af5823349` |
| `STUDY_SCENE4` | 4 | 81, 82, 83, 84 | 81, 82, 83, 84 | 6 | `f4a57033c5e383aa` |
| `LIVING_ROOM_SCENE3` | 5 | 85, 86, 87, 88, 89 | 85, 86, 87, 88, 89 | 10 | `2f4e252a74968312` |

- 场景内组合池无序对合计 **143 对**（×2 顺序 = **286** 个 ordered 候选）；其中 `KITCHEN_SCENE1` 因剔除 `00` 由 10 对降为 6 对（12 ordered）。

| 场景 | 池内任务 | M1 对 | ordered | 复核状态 | 说明 |
| --- | ---: | ---: | ---: | --- | --- |
| `KITCHEN_SCENE1` | 01, 02, 03, 04 | 6 | 12 | 已复核（v1） | 剔除任务 00（用户复核：00 本身即双子任务，不再参与组合） |
| `KITCHEN_SCENE3` | 06, 07, 08 | 3 | 6 | 暂无修改意见 | 待用户逐场景复核 |
| `KITCHEN_SCENE4` | 10, 11, 12, 13, 14 | 10 | 20 | 暂无修改意见 | 待用户逐场景复核 |
| `KITCHEN_SCENE6` | 15, 16 | 1 | 2 | 暂无修改意见 | 待用户逐场景复核 |
| `KITCHEN_SCENE8` | 18 | 0 | 0 | 暂无修改意见 | 待用户逐场景复核 |
| `KITCHEN_SCENE9` | 20, 21, 22, 23, 24 | 10 | 20 | 暂无修改意见 | 待用户逐场景复核 |
| `KITCHEN_SCENE10` | 26, 27, 28, 29, 30 | 10 | 20 | 暂无修改意见 | 待用户逐场景复核 |
| `LIVING_ROOM_SCENE1` | 31, 32, 33, 34 | 6 | 12 | 暂无修改意见 | 待用户逐场景复核 |
| `LIVING_ROOM_SCENE2` | 35, 36, 37, 38, 39 | 10 | 20 | 暂无修改意见 | 待用户逐场景复核 |
| `LIVING_ROOM_SCENE4` | 42, 43, 44 | 3 | 6 | 暂无修改意见 | 待用户逐场景复核 |
| `LIVING_ROOM_SCENE5` | 45, 46, 47, 48 | 6 | 12 | 暂无修改意见 | 待用户逐场景复核 |
| `LIVING_ROOM_SCENE6` | 49, 50, 51, 52 | 6 | 12 | 暂无修改意见 | 待用户逐场景复核 |
| `KITCHEN_SCENE2` | 53, 54, 55, 56, 57, 58, 59 | 21 | 42 | 暂无修改意见 | 待用户逐场景复核 |
| `KITCHEN_SCENE5` | 60, 61, 62, 63, 64 | 10 | 20 | 暂无修改意见 | 待用户逐场景复核 |
| `KITCHEN_SCENE7` | 65, 66, 67 | 3 | 6 | 暂无修改意见 | 待用户逐场景复核 |
| `STUDY_SCENE1` | 68, 69, 70, 71 | 6 | 12 | 暂无修改意见 | 待用户逐场景复核 |
| `STUDY_SCENE2` | 72, 73, 74, 75 | 6 | 12 | 暂无修改意见 | 待用户逐场景复核 |
| `STUDY_SCENE3` | 76, 77, 78, 79, 80 | 10 | 20 | 暂无修改意见 | 待用户逐场景复核 |
| `STUDY_SCENE4` | 81, 82, 83, 84 | 6 | 12 | 暂无修改意见 | 待用户逐场景复核 |
| `LIVING_ROOM_SCENE3` | 85, 86, 87, 88, 89 | 10 | 20 | 暂无修改意见 | 待用户逐场景复核 |
- `KITCHEN_SCENE8` 只有 1 条单目标任务（`18` turn off the stove；同场景 `17` 是双目标被排除）→ **stranded 任务 1 条**，见 §5 的特殊候选 S1。

### 1.3 关键前提：同场景四段结构一致（本条决定方法选型）

对每个场景内所有任务比较：

| 项 | 结论 | 证据 |
| --- | --- | --- |
| `:objects`（已实例化物体集合） | 20/20 场景内变体数 = 1 | `.tmp/libero90-combos/inventory.json` 的 `object_names` |
| `:init` 原子集合 | 20/20 场景内变体数 = 1 | 同文件 `init_atoms` |
| `:regions` 名集合 / `:fixtures` | 20/20 场景内变体数 = 1；20 个场景之间指纹两两不同 | `region_fp` / `fixture_fp` / `scene_fp` |
| `.pruned_init` 宽度 | 同场景内一致；全库 10 种宽度（[50,45]–[50,123]） | `init_width` |
| `.pruned_init` 具体内容 | **同场景内各任务文件 sha256 不同**（50 行位姿采样不同） | `scratch/init_hash.py` |

推论：
- **可以照搬 LIBERO-GOAL 的直接组合配方**（模板 + 改 3 段 + init 复用），因为"场景内结构一致"正是 GOAL 方法的唯一前提；
- **不需要任何 init 合成**（同场景物体集合、`:init` 约束一致，直接复用模板任务的 `.pruned_init`）；
- **但不能假设 init 源无关**：同场景两条任务的 init 文件内容不同，而 GOAL 已实测 init 源可翻转单任务成败（wine-on-cabinet：pair init 600 步失败 / task2 init 196 步成功，`docs/libero-experiments-20261019.md:134`）。init 源必须作为候选参数记录并做对照。

### 1.4 指令文本来源与 benchmark 顺序（两个必须处理的坑）

1. **官方 language 是文件名派生，不是 BDDL 内联值**。`libero.benchmark.grab_language_from_filename`（`libero/libero/benchmark/__init__.py:46-56`）对 LIBERO-90 用"去掉 `SCENE…` 前缀、下划线换空格"的文件名文本。实测 **4 条不一致**：

| # | 官方 language（用作 prompt） | BDDL 内联 `:language` |
| --- | --- | --- |
| `55` | put the middle black bowl on the plate | put the black bowl in the middle on the plate |
| `58` | stack the middle black bowl on the back black bowl | stack the black bowl in the middle on the black bowl at the front |
| `79` | pick up the white mug and place it to the right of the caddy | … to the right compartment of the caddy |
| `80` | pick up the red mug and place it to the right of the caddy | … to the right compartment of the caddy |

> GOAL 的教训是 prompt 源必须对齐 benchmark 官方值（BDDL 内联值曾导致 25/40 任务 prompt 偏差、并把 LIBERO_GOAL #4 从成功翻成失败，`docs/libero-experiments-20261019.md:70`）。**组合指令一律用官方值拼接**。
2. **benchmark 顺序是字母序**，与 `tasks_info.txt` 顺序不同；`scripts/prepare_libero90_task_configs.py` 从 `libero_suite_task_map.py` 解析映射（`docs/libero-90-baseline-pi05-seed3.md:41-60`）。候选 ID 用 tasks_info 序，跑 runtime 时再换 benchmark idx（映射表：`.tmp/libero90-combos/official-language-and-benchmark-map.json`）。

## 2. 两个参考方法的内核

### 2.1 LIBERO-GOAL：直接组合（本方法的主配方）

- **前提**：10 个任务的 `:regions/:fixtures/:objects/:init` 逐字节相同，init 统一 `[50,79]`（场景指纹 `6ed41dc5…`）。
- **配方**：以任务 i 的 BDDL 为模板 → `:goal := (And atom_i atom_j)`；`:obj_of_interest := 两任务去重并集`；`:language := "{lang_i} and {lang_j}"`；其余段逐字节保留；init 二进制拷贝任务 i 的 `.pruned_init`。命名 `goal_pair_<ii>_<jj>.bddl` + sibling `.pruned_init`。
- **规模**：45 无序对 → 90 ordered（45 原始 + 45 反向，goal/init 相同、只对调 instruction）；另有 90 个 `then`/`andthen` 措辞变体、8 个 new-goal 候选。
- **分类**：conflict 7 / hard 5 / compatible 33（规则见 §6）。
- **实测**：单指令组合 2/47 ≈ 4.3%；失败 45 条中 39 条"恰好完成 1 个子任务后停滞"；staged 2/3；990/1600 步长预算与 hints 均无效；16 个可行 ordered（6-seed 33/96，≥3/6 = 6 个）→ 去重后 13 个可行 pair、5 个稳定 pair。
- **可迁移结论**：配方可整体照搬；但 prompt 用官方 language、init 源要选、单指令大概率不可解（要 staged）、分类规则要按 L90 物体重算。

### 2.2 LIBERO-OBJECT：场景内"提升第二目标"（本方法的 M2 参考与验证体系）

| 维度 | 内容 |
| --- | --- |
| 做法 | 保留源任务场景/init 完全不动，把 1 个已实例化的干扰物提升为第二目标（只改 `:goal/:obj_of_interest/:language`） |
| 结果 | 50 组合 ×2 顺序 = 100 候选；静态 100/100；pi05 动态 **12/300 = 4.0%**，6 个至少成功一次、5 个 ≥2/3 seeds、1 个 3/3 |
| 对 L90 的适用性 | **部分适用**：L90 场景内大多数物体已经是别的任务目标（等价于 M1 任务组合）；真正"未被任何 goal 引用"的纯干扰物只有少数 → 作为 M2 补充路线 |
| 可迁移的部分 | ① 场景/init 完全不动、只改 goal/obj_of_interest/language 的构造方式；② 静态验证 + 运行时 sha256 预检 + 单任务控制 + 多 seed 的验证漏斗；③ v3 指令模板 `put both the {A} and the {B} in the basket`（本方法 T1 的来源） |

### 2.3 三套件结构对比：为什么 L90 走 GOAL 内核

| 维度 | LIBERO-GOAL | LIBERO-OBJECT | LIBERO-90 |
| --- | --- | --- | --- |
| 任务数 / 场景数 | 10 / 1 | 10 / 1 | 90 / 20 |
| 每任务 goal 原子数 | 1 | 1 | 1 或 2（11 条双原子） |
| 场景内 `:objects` 变体 | **1** | **10**（每任务 7 物体子集/顺序不同） | **1**（场景级裁剪） |
| 场景内 `:init` 原子变体 | 1 | 10 | 1 |
| init 宽度 | [50,79] | [50,110]（每任务一致） | 10 种（同场景一致） |
| 组合方式 | 直接组合 | 场景内提升（B） | **同场景直接组合（M1）+ 少量提升（M2）** |
| 单指令组合成功率 | 4.3% | 4.0% | 未测（预期同为个位数） |

## 3. 主路线 M1：同场景任务级直接组合（294 个 ordered 候选）

### 3.1 字段级配方（Step 0–8）

**Step 0 建表与 fail-fast**：按 `tasks_info.txt` 顺序建 90 条任务表；解析 `:goal` 原子（保留 And/Not 处理）、`:objects`、`:regions`、`:fixtures`、`:init`；从 benchmark 取官方 language；断言 83 池内每条任务至少 1 个原子。
**Step 1 场景分组断言**：同一场景内所有任务的 `:objects` 有序列表、`:init` 原子集合、`:regions`+`:fixtures` 指纹、init 宽度必须全同（当前 20/20 成立）；非同场景的 pair 直接排除。
**Step 2 逐对生成**（模板 = 同场景任一任务，推荐取 goal 原子集合更大者，减少 obj_of_interest 变化）：
- `:goal := (And <atom 并集>)`：按"任务 i 原子顺序 + 任务 j 新增原子"拼接，**完全相同的原子去重**；
- `:obj_of_interest := 两任务去重并集`（可动物体 + 目标容器 fixture；与 GOAL 一致，region 名不写入）；
- `:language := "{lang_i} and {lang_j}"`（官方 language；反向候选对调子句）；
- `:objects/:regions/:fixtures/:init` **逐字节原样保留**（段替换必须括号配对定位，不要正则切割）。
**Step 3 命名与 init**：候选 ID `L90_<SCENE>_<ii>_<jj>_<ab|ba>`；产物 `<stem>.bddl` + sibling `<stem>.pruned_init`（内容 = 模板任务官方 `.pruned_init` 的字节拷贝）；反向候选 `ba` 同样拷贝模板 init（模板与 init 源可以不同任务，见 §3.3）。
**Step 4 分类与清单**：按 §6 规则写 `class/dependency/n_atoms/s1_revertable/priority`。
**Step 5 静态验证**：按 §10.1 的 19 项 + N 原子断言 + 初始 success=False。
**Step 6 指令变体**（可选）：`then` = `first {A}, then {B}`、`andthen` = `{A} and then {B}`；只改 `:language`，断言其余段不变。
**Step 7 动态协议**：单指令 baseline（1 seed 冒烟）→ staged/instruction-switch（推荐主协议）→ 多 seed。
**Step 8 rollback 用例**：指定 s1/s2，s1 必须是已建模可回退关系（On/In/Open/Close）；Turnon/Turnoff 只能当 s2。

### 3.2 示例（LIVING_ROOM_SCENE2，任务 36 + 37）

```
原始 36：pick up the milk and put it in the basket        goal: (In milk_1 basket_1_contain_region)
原始 37：pick up the butter and put it in the basket      goal: (In butter_1 basket_1_contain_region)

组合 L90_LR2_36_37_ab（milk 先）：
  :language  put both the milk and the butter in the basket
             ↑ T1 模板（LIBERO-10 /04 /05 /06 官方 + LIBERO-OBJECT v3，不是两条官方句直接拼接）
  :goal      (And (In milk_1 basket_1_contain_region) (In butter_1 basket_1_contain_region))
  :obj_of_interest  milk_1 butter_1 basket_1
  :objects / :regions / :fixtures / :init   与任务 36 逐字节相同
  .pruned_init = 任务 36 的官方 .pruned_init（50 行字节拷贝）
  对照（naive 拼接，保留在 candidates-instructed.json 的原 `language` 字段）= "pick up the milk and put it in the basket and pick up the butter and put it in the basket"
```

### 3.3 模板与 init 源选择（2×2 参数）

组合候选有两个独立参数：
- **模板（决定 `:objects` 顺序、`:init` 文本、problem name）**：同场景内两任务在这几段上一致，因此模板对解析语义无影响；推荐取 goal 原子集合较大者，使 `:obj_of_interest` 只需追加。
- **init 源（决定 50 行具体位姿）**：可取任务 i 的、任务 j 的，或用两条各半/重采样。**必须记录并在静态验证阶段对两个源都做"单任务可解性"控制**（GOAL 已有 init 源翻转成败的实例）。默认 `init_source = s1 任务`，备选 `= s2 任务`；两者都进候选参数表。

### 3.4 N 原子与去重

| 组合情形 | 去重后原子数 | 例子 |
| --- | --- | --- |
| 两条 1 原子任务 | 2 | 绝大多数（134 对） |
| 1 原子 + `26/27/28`（2 原子） | 3 | `26`+`29` → `In butter` + `Close` + `In bowl` |
| `00` 与 `03/04` | 2（无新增） | `00`+`03`：`Open` 重复 → 原子集合等于 `00` 本身 → degenerate |
| 两条同容器双谓词 | 3 | `26`+`27` → `In butter_1` + `In butter_2` + `Close` |

生成器断言：`n_atoms == len(去重后的原子并集)`，且合并后的原子集合不能等于任一侧任务的 goal 集合（否则 degenerate）；当前 147 对里 2 原子 138 对（其中 degenerate 4 对）、3 原子 9 对，无 4 原子对。

## 4. 补充路线 M2：场景内提升（OBJECT 路线 B 的 L90 版）

### 4.1 判定条件

对场景 s 中的任务 a（单目标池），若存在物体 b：
1. b ∈ 场景 s 的 `:objects`，且 b 在 `:init` 中已有位姿（`(On b ...)`）；
2. b 不是**任何**场景内任务的 goal 目标物（否则该"提升"等价于 M1 的任务组合，直接走 M1）；
3. 场景 s 内存在一个 b 作为目标物的官方（或其他场景同物体）instruction 可借用；
4. b 的落点在场景 s 的 `:regions`/`:fixtures` 中存在（容器 = 同场景已有 `contain_region`/目标区域）。
满足 1–4 时，把 `atom_b` 并入任务 a 的 goal，得到"任务 a + 提升目标 b"的双目标候选（init/objects/regions 完全不动）。

### 4.2 LIBERO-90 上的命中（为什么只有 17 个 unordered / 34 个 ordered；另有 1 个 KITCHEN_SCENE8 特殊候选见 §5）

L90 的 `:objects` 是场景级裁剪结果，绝大多数物体都已被场景内某条任务当作目标。**通过 §4.1 条件 1–4（已有位姿 + 无场景内 goal 引用 + 有可借用措辞 + 有可用落点）的纯干扰物只有**：

（另有 `KITCHEN_SCENE6` 的 `porcelain_mug_1` 未被任何 goal 引用，但它是任务 15 的参照物且本场景没有可用落点/措辞，故剔除；各场景的 `basket/tray/plate` 是落点容器，本身不作被抓目标。）


| 场景 | 纯干扰物 | 可借用的官方措辞 | 可组合的任务 | 候选数（×2 顺序） |
| --- | --- | --- | --- | --- |
| `LIVING_ROOM_SCENE2` | `cream_cheese_1`, `ketchup_1` | `32`（cream cheese）/`31`（ketchup）的 basket 句 | `35 36 37 38 39` | 10 × 2 |
| `STUDY_SCENE2` | `red_coffee_mug_1` | `73` 的 "in the right compartment of the caddy" 从句 + `80` 的 red mug 名词（合成措辞，需人工确认） | `72 73 74 75` | 4 × 2 |
| `LIVING_ROOM_SCENE4` | `akita_black_bowl_2` | `42` 的 tray 句（bowl 左右由 initial region 区分） | `42 43 44` | 3 × 2 |
| `KITCHEN_SCENE8` | `moka_pot_2`（左壶） | `07` "put the moka pot on the stove" | `18` | 1 × 2（并入 S1） |

> M2 的指令**不是该场景官方原文**（是借用同物体在其他场景/任务的措辞），清单里必须标注"instruction 需人工确认"。

| candidate_id | 场景 | 任务 | 提升的物体 | 合并指令 | class | priority |
| --- | --- | --- | --- | --- | --- | --- |
| `L90_LR2_35_cream_cheese_1_ab` | LIVING_ROOM_SCENE2 | `35` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the orange juice and the cream cheese box in the basket | compatible | P0 |
| `L90_LR2_35_cream_cheese_1_ba` | LIVING_ROOM_SCENE2 | `35` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the cream cheese box and the orange juice in the basket | compatible | P0 |
| `L90_LR2_35_ketchup_1_ab` | LIVING_ROOM_SCENE2 | `35` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the orange juice and the ketchup in the basket | compatible | P0 |
| `L90_LR2_35_ketchup_1_ba` | LIVING_ROOM_SCENE2 | `35` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the ketchup and the orange juice in the basket | compatible | P0 |
| `L90_LR2_36_cream_cheese_1_ab` | LIVING_ROOM_SCENE2 | `36` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the milk and the cream cheese box in the basket | compatible | P0 |
| `L90_LR2_36_cream_cheese_1_ba` | LIVING_ROOM_SCENE2 | `36` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the cream cheese box and the milk in the basket | compatible | P0 |
| `L90_LR2_36_ketchup_1_ab` | LIVING_ROOM_SCENE2 | `36` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the milk and the ketchup in the basket | compatible | P0 |
| `L90_LR2_36_ketchup_1_ba` | LIVING_ROOM_SCENE2 | `36` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the ketchup and the milk in the basket | compatible | P0 |
| `L90_LR2_37_cream_cheese_1_ab` | LIVING_ROOM_SCENE2 | `37` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the butter and the cream cheese box in the basket | compatible | P0 |
| `L90_LR2_37_cream_cheese_1_ba` | LIVING_ROOM_SCENE2 | `37` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the cream cheese box and the butter in the basket | compatible | P0 |
| `L90_LR2_37_ketchup_1_ab` | LIVING_ROOM_SCENE2 | `37` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the butter and the ketchup in the basket | compatible | P0 |
| `L90_LR2_37_ketchup_1_ba` | LIVING_ROOM_SCENE2 | `37` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the ketchup and the butter in the basket | compatible | P0 |
| `L90_LR2_38_cream_cheese_1_ab` | LIVING_ROOM_SCENE2 | `38` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the alphabet soup and the cream cheese box in the basket | compatible | P0 |
| `L90_LR2_38_cream_cheese_1_ba` | LIVING_ROOM_SCENE2 | `38` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the cream cheese box and the alphabet soup in the basket | compatible | P0 |
| `L90_LR2_38_ketchup_1_ab` | LIVING_ROOM_SCENE2 | `38` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the alphabet soup and the ketchup in the basket | compatible | P0 |
| `L90_LR2_38_ketchup_1_ba` | LIVING_ROOM_SCENE2 | `38` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the ketchup and the alphabet soup in the basket | compatible | P0 |
| `L90_LR2_39_cream_cheese_1_ab` | LIVING_ROOM_SCENE2 | `39` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the tomato sauce and the cream cheese box in the basket | compatible | P0 |
| `L90_LR2_39_cream_cheese_1_ba` | LIVING_ROOM_SCENE2 | `39` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the cream cheese box and the tomato sauce in the basket | compatible | P0 |
| `L90_LR2_39_ketchup_1_ab` | LIVING_ROOM_SCENE2 | `39` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the tomato sauce and the ketchup in the basket | compatible | P0 |
| `L90_LR2_39_ketchup_1_ba` | LIVING_ROOM_SCENE2 | `39` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the ketchup and the tomato sauce in the basket | compatible | P0 |
| `L90_LR4_42_akita_black_bowl_2_ab` | LIVING_ROOM_SCENE4 | `42` | akita_black_bowl_2 → (In akita_black_bowl_2 wooden_tray_1_contain_region) | put both the black bowl on the left and the black bowl on the right in the tray | compatible | P0 |
| `L90_LR4_42_akita_black_bowl_2_ba` | LIVING_ROOM_SCENE4 | `42` | akita_black_bowl_2 → (In akita_black_bowl_2 wooden_tray_1_contain_region) | put both the black bowl on the right and the black bowl on the left in the tray | compatible | P0 |
| `L90_LR4_43_akita_black_bowl_2_ab` | LIVING_ROOM_SCENE4 | `43` | akita_black_bowl_2 → (In akita_black_bowl_2 wooden_tray_1_contain_region) | put both the salad dressing and the black bowl on the right in the tray | compatible | P0 |
| `L90_LR4_43_akita_black_bowl_2_ba` | LIVING_ROOM_SCENE4 | `43` | akita_black_bowl_2 → (In akita_black_bowl_2 wooden_tray_1_contain_region) | put both the black bowl on the right and the salad dressing in the tray | compatible | P0 |
| `L90_LR4_44_akita_black_bowl_2_ab` | LIVING_ROOM_SCENE4 | `44` | akita_black_bowl_2 → (In akita_black_bowl_2 wooden_tray_1_contain_region) | put both the chocolate pudding and the black bowl on the right in the tray | compatible | P0 |
| `L90_LR4_44_akita_black_bowl_2_ba` | LIVING_ROOM_SCENE4 | `44` | akita_black_bowl_2 → (In akita_black_bowl_2 wooden_tray_1_contain_region) | put both the black bowl on the right and the chocolate pudding in the tray | compatible | P0 |
| `L90_ST2_72_red_coffee_mug_1_ab` | STUDY_SCENE2 | `72` | red_coffee_mug_1 → (In red_coffee_mug_1 desk_caddy_1_right_contain_region) | put the book in the left compartment of the caddy and put the red mug in the right compartment of the caddy | compatible | P0 |
| `L90_ST2_72_red_coffee_mug_1_ba` | STUDY_SCENE2 | `72` | red_coffee_mug_1 → (In red_coffee_mug_1 desk_caddy_1_right_contain_region) | put the red mug in the right compartment of the caddy and put the book in the left compartment of the caddy | compatible | P0 |
| `L90_ST2_73_red_coffee_mug_1_ab` | STUDY_SCENE2 | `73` | red_coffee_mug_1 → (In red_coffee_mug_1 desk_caddy_1_right_contain_region) | put both the book and the red mug in the right compartment of the caddy | compatible | P0 |
| `L90_ST2_73_red_coffee_mug_1_ba` | STUDY_SCENE2 | `73` | red_coffee_mug_1 → (In red_coffee_mug_1 desk_caddy_1_right_contain_region) | put both the red mug and the book in the right compartment of the caddy | compatible | P0 |
| `L90_ST2_74_red_coffee_mug_1_ab` | STUDY_SCENE2 | `74` | red_coffee_mug_1 → (In red_coffee_mug_1 desk_caddy_1_right_contain_region) | put the book in the front compartment of the caddy and put the red mug in the right compartment of the caddy | compatible | P0 |
| `L90_ST2_74_red_coffee_mug_1_ba` | STUDY_SCENE2 | `74` | red_coffee_mug_1 → (In red_coffee_mug_1 desk_caddy_1_right_contain_region) | put the red mug in the right compartment of the caddy and put the book in the front compartment of the caddy | compatible | P0 |
| `L90_ST2_75_red_coffee_mug_1_ab` | STUDY_SCENE2 | `75` | red_coffee_mug_1 → (In red_coffee_mug_1 desk_caddy_1_right_contain_region) | put the book in the back compartment of the caddy and put the red mug in the right compartment of the caddy | compatible | P0 |
| `L90_ST2_75_red_coffee_mug_1_ba` | STUDY_SCENE2 | `75` | red_coffee_mug_1 → (In red_coffee_mug_1 desk_caddy_1_right_contain_region) | put the red mug in the right compartment of the caddy and put the book in the back compartment of the caddy | compatible | P0 |

## 5. 特殊候选 S1：`18`（stranded）的救法

- 问题：`KITCHEN_SCENE8` 的两条任务中，`17`（put the right moka pot on the stove）是双目标被排除；`18`（turn off the stove）在 83 池内没有同场景伙伴。
- 关键事实（BDDL 原文核实）：`17` 的 goal 是 `(And (On moka_pot_1 flat_stove_1_cook_region) (Turnon flat_stove_1))`；`17/18` 的 `:init` 都包含 `(Turnon flat_stove_1)`（**炉子初始就是开的**），`moka_pot_1` 在右 init 区域、`moka_pot_2` 在左 init 区域。
- 救法：把 `moka_pot_2`（左壶，纯干扰物）提升为第二目标，与 `18` 的 `(Turnoff flat_stove_1)` 组合：
  `:goal = (And (On moka_pot_2 flat_stove_1_cook_region) (Turnoff flat_stove_1))`，`:language = "put the left moka pot on the stove and turn it off"`（T8 模板：`07` 的放置句 + `18` 的关火句 + LIBERO-GOAL `it` 指代；反向为 "turn off the stove and put the left moka pot on it"）。
- 为什么成立：`Turnon` 在 init 已真、`Turnoff` 初始为假 → 两个原子都是有效阶段；`On moka_pot_2` 是可回退的放置关系 → **s1 = 放左壶（可回退），s2 = 关火**，是真正可用于 rollback 的双阶段候选。
- 分类：compatible（两个目标作用于不同实体，且关火与放壶互不阻塞）；优先级 P0（s1 可回退），但 instruction 为合成措辞，需人工确认。

| candidate_id | merged goal atoms | 合并指令（模板化） | 说明 |
| --- | --- | --- | --- |
| `L90_KS8_18_moka_pot_2_ab` | (On moka_pot_2 flat_stove_1_cook_region) ; (Turnoff flat_stove_1) | put the left moka pot on the stove and turn it off | synthesized instruction (not official); '(Turnon flat_stove_1)' dropped because it already holds in :init; ab s1 = place the left moka pot (revertable, P0), ba s1 = Turnoff (not revertable, P1). |
| `L90_KS8_18_moka_pot_2_ba` | (Turnoff flat_stove_1) ; (On moka_pot_2 flat_stove_1_cook_region) | turn off the stove and put the left moka pot on it | synthesized instruction (not official); '(Turnon flat_stove_1)' dropped because it already holds in :init; ab s1 = place the left moka pot (revertable, P0), ba s1 = Turnoff (not revertable, P1). |

## 6. 语义分类与组合结构（147 对）

### 6.1 分类规则（互斥）

| 类 | 判定 | 处理 |
| --- | --- | --- |
| `conflict` | 两个 goal 原子逻辑上不可同时成立：① 同一可动物体被要求处于两个不同位置/落点（`On/In X A` vs `On/In X B`，A≠B）；② 同一关节同时 `Open` 与 `Close`；③ 同一 fixture 同时 `Turnon` 与 `Turnoff` | 不进动态集（可留作对照） |
| `degenerate` | 去重后的原子集合等于其中一条任务的 goal 集合（一方 goal 是另一方子集，合并没有引入新阶段，如 `03`+`00`、`30`+`26`） | 不进动态集；清单里以 `valid=false` 保留 8 个 ordered 记录作对照 |
| `hard` | 可共存但存在真正的**次序/接触依赖**：① 放入容器 + 关闭同一容器（`In X C` + `Close C`，必须先放后关）；② 打开容器 + 放入同一容器（必须先开后放）；③ 一个物体作为另一个的落点基底（`On X Y` 与另一原子移动 Y，叠放链）；④ 落点区域是同层相邻区域（空间拥挤/易碰撞） | 需要固定次序 + staged，优先级降一档 |
| `compatible` | 上述都不命中（不同可动物体、不同落点或**同落点但不同物体**、互不干扰） | 默认候选；同落点情形打 `same_destination` 标签 + `capacity_caveat`（容量/遮挡风险，参考 GOAL 02_04 与 OBJECT 路线 B） |

### 6.2 依赖类型（可多值，用于 staged 顺序设计）

`place_then_close`（先放后关）、`open_then_place`（先开再放）、`same_destination`（同落点/同容器）、`stack_anchor`（叠放基底）、`adjacent_regions`（同层相邻区域）、`same_object`（同物体被两条任务使用）、`same_furniture`/`same_fixture`/`same_container_family`（共享家具/夹具/同族容器，单独出现不改变 class）、`subset`/`duplicate_atom`（子集/重复原子，用于 degenerate）、`independent`（独立）。完整计数见 `pair-semantics.json` 的 `stats.class_x_dependency`。

### 6.3 分类统计

| class | 对数 | 占比 | 合并后原子数分布 | 主要依赖标签 |
| --- | ---: | ---: | --- | --- |
| `compatible` | 92 | 64.3% | 2:92 | same_destination:41, same_furniture:9, same_fixture:2, same_container_family:1, independent:40 |
| `hard` | 19 | 13.3% | 2:13 / 3:6 | place_then_close:11, stack_anchor:4, adjacent_regions:4, same_destination:6 |
| `conflict` | 29 | 20.3% | 2:29 | same_object:29 |
| `degenerate` | 3 | 2.1% | 2:3 | place_then_close:3 |

| 依赖标签 | same_object | place_then_close | open_then_place | stack_anchor | adjacent_regions | same_destination | same_furniture | same_fixture | same_container_family | independent |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 对数（可多标签） | 29 | 14 | 0 | 4 | 4 | 47 | 9 | 2 | 1 | 40 |

### 6.4 典型例子

- **compatible（同落点）**：`36`+`37`（牛奶+黄油入同一篮子：不同物体、同容器 → `same_destination` + `capacity_caveat`，按规则归 compatible，与 LIBERO-OBJECT 路线 B"两物体入同一 basket"同构）。
- **conflict**：`47`+`48`（红杯放左盘 / 红杯放右盘，同一物体两个互斥落点）。
- **hard**：`26`+`29`（黄油入上层抽屉并关上 + 黑碗入同一抽屉：必须先把两件都放进去再关抽屉）。
- **degenerate**：`03`+`00`（`Open top drawer` 被 `00` 的 `Open top drawer + In bowl` 包含，去重后剩 2 原子但实为同一任务的重复表达）→ 归 degenerate/无新增阶段。

> 完整逐对分类、依赖、证据与两方向 `s1_revertable` 见 `.tmp/libero90-combos/pair-semantics.json`（由 `scripts/build_libero90_combos.py --check` 复核一致性）。

## 7. 指令与协议

### 7.1 指令模板（替代 naive 拼接）

**结论：合并指令不再用两条官方 language 直接拼接**，而是按"合并后 goal 原子结构 + class/dependency"套用参考套件里已验证的任务模板。naive 拼接保留在原 `language` 字段（于 `candidates-instructed.json` 中作对照）。

| 模板 | 用到的候选数 | 依据的成功任务/实验 | 示例指令 |
| --- | ---: | --- | --- |
| `T1` | 92 | 同容器双物体（In+In 同一容器）；LIBERO-10 /04; LIBERO-10 /05; LIBERO-10 /06; LIBERO-OBJECT v3；LIBERO-10 /04 /05 /06 official: `put both the A and the B in the basket` (same  | put both the black bowl and the wine bottle in the bottom drawer of the cabinet |
| `T10` | 20 | 其余两/三子句链（放置/关节/开关混合）；LIBERO-10 /09; LIBERO-90 multi-clause official；LIBERO-10 /09 + LIBERO-90 multi-clause official languages: normalized put/stack/open/close/t | open the top drawer of the cabinet and open the bottom drawer of the cabinet |
| `T2` | 18 | 同落点双物体（On+On / 同目标短语）；LIBERO-10 /03；LIBERO-10 /03 official: `put both moka pots on the stove`; GOAL `both` on two objects on the same surface showed no gain (0/ | put both the frying pan and the moka pot on the stove |
| `T3` | 126 | 不同落点双物体（放置+放置）；LIBERO-10 /07; LIBERO-10 /08；LIBERO-10 /07 /08 official: two `put ...` clauses for two different destinations | put the black bowl on top of the cabinet and put the black bowl on the plate |
| `T4` | 16 | 放置+关闭同一容器（单物体）；LIBERO-10 /01; LIBERO-10 /02；LIBERO-10 /01 /02 official: `put ... in ... and close it`; LIBERO-GOAL `then` variant: 06_08 5/9 -> 7/9 (+2), 06_07  | put the black bowl in the bottom drawer of the cabinet and close it |
| `T4b` | 12 | 双物体入同一容器+关闭；LIBERO-10 /01; LIBERO-10 /02; LIBERO-10 /04; LIBERO-10 /05; LIBERO-10 /06；LIBERO-10 /01 /02 official: `put ... in ... and close it`; LIBERO-10 /04 / | put both the butter at the front and the butter at the back in the top drawer of the cabinet and close it |
| `T6` | 24 | 放置+打开（不同容器）；LIBERO-10 /09; LIBERO-90 /01 /03；LIBERO-10 /09 + LIBERO-90 multi-clause official languages: normalized put/stack/open/close/turn two-clause chains | put the black bowl on top of the cabinet and open the top drawer of the cabinet |
| `T7` | 4 | 放置+Turnon（同一炉体）；LIBERO-10 /00；LIBERO-10 /00 official: `turn on the stove and put the moka pot on it`; LIBERO-GOAL `it`-ellipsis variant: 07_01 4/9 -> 7/9 (+3);  | put the frying pan on the stove and turn it on |
| `T8` | 2 | 放置+Turnoff（同一炉体）；LIBERO-10 /00; S1 rescue；LIBERO-10 /00 official: `turn on the stove and put the moka pot on it`; LIBERO-GOAL `it`-ellipsis variant: 07_01 4/9 - | put the left moka pot on the stove and turn it off |
| `T9` | 8 | 叠放链（stack_anchor）；LIBERO-90 /40; LIBERO-90 /41; KITCHEN_SCENE2 stack pairs；LIBERO-90 /40 /41 official: `stack the left bowl on the right bowl and place them in  | put the black bowl at the back on the plate and stack the middle black bowl on top of it |

模板来源与证据：
- **T1/T2/T4**：LIBERO-10 官方成功任务（pi0 8/10、pi05 10/10）——"put both the alphabet soup and the cream cheese box in the basket"、"put both moka pots on the stove"、"put the black bowl in the bottom drawer of the cabinet and close it"；T1 同时是 LIBERO-OBJECT v3 模板（12/300 = 4.0%）。
- **T3/T10**：LIBERO-10 07/08 的"双 put 子句"结构（"put the white mug on the left plate and put the yellow and white mug on the right plate" / "… and put the chocolate pudding to the right of the plate"）。
- **T7/T8**：LIBERO-10 00 + LIBERO-GOAL `it` 改写实验（07_01 4/9→7/9，最强正信号）。
- **T9**：LIBERO-90 自身双目标任务 40/41 的 stack 官方模板（"stack the left bowl on the right bowl and place them in the tray"）。
- **T12（变体策略，不是候选级模板 id）**：GOAL `then` 改写对容器依赖任务的正收益（06_08 +2、06_07 +4），写入 `instruction_variants.then`，hard/P2 候选的 `instruction_preferred_variant=then`。
- 候选级模板 id 实际共 **11 个（T1–T10 + T4b）**；下表由 `candidates-instructed.json` 自动统计。
- 反例证据：naive 拼接（GOAL 45 对里的 and 拼接）单指令成功率仅 2/47≈4.3%；`integrated` 改写灾难负收益（06_01 8/9→0/9），故不采用。

每条候选在 `candidates-instructed.json` 里记录：`instruction`（主指令）、`instruction_template`（T1–T10 + T4b）、`instruction_variants`（`and`/`then`/`both`/`it` 变体）、`instruction_evidence`（模板来源与数字）、`instruction_source`（`template:…`/`borrowed:nn`/`synthesized`）。同一模板族内只允许名词短语/落点短语不同，句式必须一致，便于做"模板 vs naive"的对照实验。

### 7.2 staged / instruction-switch（推荐主协议）

同一 episode、同一合并 goal：先给 s1 的 instruction，检测 s1 目标首次为真后切到 s2 的 instruction。GOAL 实测 2/3（`00_07` switch=133、579 步；`08_09` switch=88、390 步）。L90 候选数量大、单指令预期低，**建议新候选一律先按 staged 协议验证**，再决定是否值得做单指令 baseline。

## 8. init 源与运行时构造

### 8.1 init 源策略

- 同场景两条任务的 `.pruned_init` 都满足同一组 `:init` 原子，但 50 行采样位姿不同 → 记录 `init_source ∈ {s1, s2}`，两者都做静态验证；动态先各跑 1 seed 冒烟，选单任务控制通过率高的源。
- init 只能复用同场景任务的 `.pruned_init`（不同场景的关节集合/宽度不同）。

### 8.2 runtime 通道（否则整批结果作废）

1. 候选 BDDL 是自定义 stem → 官方 benchmark 通道找不到 packaged init，会 `env.reset()` 随机采样；必须给每个候选配 **sidecar `<stem>.pruned_init`** 并让 runner 在 custom-bddl 分支加载它（约 10 行 patch）。历史上漏加载 init 曾导致 300 episodes 整批作废。
2. 候选 ID 是 tasks_info 序；跑 runtime 要换 **benchmark 字母序 idx**（映射表见 §1.4）。
3. **三层 sha256 预检**：BDDL sha、init sha、instruction/atoms/stabilized sim state sha 与设计值一致后才可扩量。

## 9. 优先级与首批推荐

### 9.1 优先级口径（ordered 候选）

| 优先级 | 条件 | 用途 |
| --- | --- | --- |
| **P0** | `class=compatible` 且该方向 s1 可回退（On/In/Open/Close，即 s1 不是 Turnon/Turnoff） | 可直接进静态验证 + rollback 原型；同落点候选另带 `capacity_caveat` |
| **P1** | `class=compatible` 但 s1 是 Turnon/Turnoff（s1 不可回退） | 只作双目标任务（Turnon/Turnoff 只能放 s2），不作 rollback |
| **P2** | `class=hard`（place_then_close / open_then_place / stack_anchor / adjacent_regions） | 需固定次序 + staged，第二批 |
| **P3** | `class=degenerate/conflict` | 不推荐（保留作对照/排除） |

### 9.2 首批建议（每个场景取 1–2 对，优先 P0 + 同容器场景）

| # | 场景 | candidate_id | class | 方向（s1→s2） | 合并指令 | 原子数 | 选它的理由 |
| ---: | --- | --- | --- | --- | --- | ---: | --- |
| 1 | LIVING_ROOM_SCENE2 | `L90_LR2_36_37_ab` | compatible | `36`→`37` | put both the milk and the butter in the basket | 2 | OBJECT 路线 B 同构：两个不同物体进同一 basket（最可迁移的一类） |
| 2 | LIVING_ROOM_SCENE3 | `L90_LR3_85_86_ab` | compatible | `85`→`86` | put both the alphabet soup and the tomato sauce in the tray | 2 | 同 tray 的两个物体（OBJECT 同构，换容器） |
| 3 | LIVING_ROOM_SCENE1 | `L90_LR1_31_32_ab` | compatible | `31`→`32` | put both the ketchup and the cream cheese box in the basket | 2 | 同 basket 双物体 + 两物体单指令都很短 |
| 4 | LIVING_ROOM_SCENE4 | `L90_LR4_43_44_ab` | compatible | `43`→`44` | put both the salad dressing and the chocolate pudding in the tray | 2 | 同 tray 双物体；且避开两个黑碗的叠放冲突 |
| 5 | LIVING_ROOM_SCENE6 | `L90_LR6_49_51_ab` | compatible | `49`→`51` | put the white mug on the plate and put the chocolate pudding to the left of the plate | 2 | 不同物体 + 不同落点（plate / plate 左侧区域）的干净独立对 |
| 6 | KITCHEN_SCENE1 | `L90_KS1_02_03_ab` | compatible | `02`→`03` | put the black bowl on the plate and open the top drawer of the cabinet | 2 | 最干净的 R1 独立对：放置 + 关节，无共享物体 |
| 7 | KITCHEN_SCENE4 | `L90_KS4_10_14_ab` | compatible | `10`→`14` | put the wine bottle on the wine rack and close the bottom drawer of the cabinet | 2 | 放置 + 关闭另一关节（不同物体、不同关节） |
| 8 | KITCHEN_SCENE6 | `L90_KS6_15_16_ab` | compatible | `15`→`16` | put the yellow and white mug to the front of the white mug and close the microwave | 2 | 放置 + 关闭微波炉（不同物体、不同关节） |
| 9 | LIVING_ROOM_SCENE5 | `L90_LR5_45_46_ab` | compatible | `45`→`46` | put the white mug on the left plate and put the yellow and white mug on the right plate | 2 | 不同杯子 + 左右两个盘子（落点不同） |
| 10 | KITCHEN_SCENE2 | `L90_KS2_53_57_ab` | compatible | `53`→`57` | put the black bowl at the back on the plate and open the top drawer of the cabinet | 2 | 不同物体 + 不同落点（plate / 抽屉关节） |

> 首批选择原则：① 两任务单指令都简单（"pick up X and put it in the basket/plate"）；② 两个落点不同或同容器容量充足；③ s1 是放置关系（可回退）；④ 每场景 1–2 对，覆盖 20 个场景里语义最干净的 8–10 个，先验证管线再扩。

## 10. 验证漏斗（从 147 对到可用的双目标/rollback 任务）

### 10.1 静态（CPU，全部候选先过）
1. BDDL 解析通过；`n_atoms == len(去重后的原子并集)` 且 ≥2；
2. `:language` == 模板化 instruction（逐字符断言，来源 `candidates-instructed.json`）；naive 拼接仅作对照；
3. `:obj_of_interest` == 两任务并集；`:objects/:regions/:fixtures/:init` 与模板逐字节相同；
4. 段替换损坏检查（无 `((`、无 `((:`，每段只出现 1 次）；
5. init：sibling sha == 源 init sha；shape == 场景 env `state_len`；50 行；
6. env 冒烟：`seed(1000)+reset()+set_init_state(init[0])+10 步稳定化` → 不抛异常、初始 `check_success()==False`、每个 goal 原子初始为 False；
7. 双目标可满足性探针：把目标实体瞬移到关系成立位置 → 所有原子 True 且 `check_success()==True`（GOAL 路线没有程序化可满足性检查，L90 建议补上；OBJECT 路线 B 的 100/100 就是这么过的）。

### 10.2 通道预检（每候选 1 episode）
instruction / goal atoms / init row / stabilized sim state 的 sha256 与设计一致；`episode_seed` 正确。

### 10.3 动态筛选（分层，控制成本）
1. **单任务基线**：组合池 82 条单目标 × 1 seed（先把 L90 的"可解任务子集"建出来；KS1 的 `00` 等既有双子任务另作对照）；
2. **单任务控制**：对每个候选，在所选 init 源下分别跑 s1、s2 的单指令，确认两者各自可解（历史教训：第二目标在改造场景中不可解时，静态验证全过也救不回来）；
3. **组合单指令冒烟**：1 seed / 候选（P0 优先），预期成功率个位数；
4. **staged 复筛**：对冒烟完成过 1 段的候选做 staged（GOAL 唯一有效 workaround）；
5. **多 seed 稳定性**：同一问 3 seeds；口径参考 OBJECT（≥2/3 稳定）与 GOAL（≥3/6 = B 级），引用时必须带分母；
6. **rollback 原型**：s1 成功后注入回退（`revert_articulation_goal` 或放置类 `displace_from_completed_pose` / `displace_to_relation_boundary`），s2 执行中观察自修复。

### 10.4 预期产出规模（基于 GOAL/OBJECT 经验的外推，非 L90 实测）

> **实测更新（2026-10-26）**：低难度 161 条已按本漏斗的"组合单指令"层实测（pi05 × 3 seeds，483 eps）→ 41 成功 = 8.49%，其中 10 个候选 3/3 全成功；详见 §15。
- 静态：147 对 ×2 顺序 - conflict/degenerate 后约 222 个 ordered 候选预计可全过；
- 组合单指令：预期 ≤5%（GOAL 4.3% / OBJECT 4.0%）→ 294 个里乐观估计 10+ 个至少成功一次；
- staged：GOAL 2/3，L90 需实测；建议先做 8–10 对首批，再决定是否扩量。

## 11. 候选清单（全量）

### 11.1 统计

| 指标 | 数值 |
| --- | ---: |
| M1 ordered 候选 | 286 |
| M2 提升候选 | 34 |
| S1 特殊候选 | 2 |
| 合计 | 322 |
| class compatible / hard / conflict / degenerate（M1） | 184 / 38 / 58 / 6 |
| priority P0 / P1 / P2 / P3（M1） | 178 / 6 / 38 / 64 |
| n_atoms 2 / 3（M1；无 4 原子候选） | 274 / 12 |
| s1_revertable 方向数（ab / ba） | 143 / 137 |

### 11.2 全量 ordered 清单

完整表格见 [`runs/libero-90-combos-20261025/CASE_LIST.md`](../runs/libero-90-combos-20261025/CASE_LIST.md)（按场景分节，含 candidate_id / class / priority / 合并指令 / n_atoms / s1_revertable / init 源）；机读定义见 [`candidates.json`](../runs/libero-90-combos-20261025/candidates.json)。

下表每行是一个 unordered pair：`class` 是 pair 级分类；`推荐 s1→s2` 是 `pair-semantics.json` 给出的首选方向（按 s1 是否为可回退关系与次序约束排序）；`合并指令（推荐方向）` 是该方向候选在 `candidates-instructed.json` 里的**模板化指令**（T1–T10 + T4b；早期 naive 拼接保留在 `language` 字段作对照）。conflict/degenerate 行也保留（作对照/排除项），其指令仅供检查语义，不进入动态集。

#### `KITCHEN_SCENE1`（6 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `01_02` | conflict | 2 | `01`→`02` | put the black bowl on top of the cabinet and put the black bowl on the plate |
| `01_03` | compatible | 2 | `01`→`03` | put the black bowl on top of the cabinet and open the top drawer of the cabinet |
| `01_04` | compatible | 2 | `01`→`04` | put the black bowl on top of the cabinet and open the bottom drawer of the cabinet |
| `02_03` | compatible | 2 | `02`→`03` | put the black bowl on the plate and open the top drawer of the cabinet |
| `02_04` | compatible | 2 | `02`→`04` | put the black bowl on the plate and open the bottom drawer of the cabinet |
| `03_04` | compatible | 2 | `03`→`04` | open the top drawer of the cabinet and open the bottom drawer of the cabinet |

#### `KITCHEN_SCENE3`（3 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `06_07` | compatible | 2 | `06`→`07` | put both the frying pan and the moka pot on the stove |
| `06_08` | compatible | 2 | `06`→`08` | put the frying pan on the stove and turn it on |
| `07_08` | compatible | 2 | `07`→`08` | put the moka pot on the stove and turn it on |

#### `KITCHEN_SCENE4`（10 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `10_11` | compatible | 2 | `10`→`11` | put the wine bottle on the wine rack and put the black bowl on top of the cabinet |
| `10_12` | compatible | 2 | `10`→`12` | put the wine bottle on the wine rack and put the black bowl in the bottom drawer of the cabinet |
| `10_13` | conflict | 2 | `10`→`13` | put the wine bottle on the wine rack and put the wine bottle in the bottom drawer of the cabinet |
| `10_14` | compatible | 2 | `10`→`14` | put the wine bottle on the wine rack and close the bottom drawer of the cabinet |
| `11_12` | conflict | 2 | `11`→`12` | put the black bowl on top of the cabinet and put the black bowl in the bottom drawer of the cabinet |
| `11_13` | compatible | 2 | `11`→`13` | put the black bowl on top of the cabinet and put the wine bottle in the bottom drawer of the cabinet |
| `11_14` | compatible | 2 | `11`→`14` | put the black bowl on top of the cabinet and close the bottom drawer of the cabinet |
| `12_13` | compatible | 2 | `12`→`13` | put both the black bowl and the wine bottle in the bottom drawer of the cabinet |
| `12_14` | hard | 2 | `12`→`14` | put the black bowl in the bottom drawer of the cabinet and close it |
| `13_14` | hard | 2 | `13`→`14` | put the wine bottle in the bottom drawer of the cabinet and close it |

#### `KITCHEN_SCENE6`（1 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `15_16` | compatible | 2 | `15`→`16` | put the yellow and white mug to the front of the white mug and close the microwave |

#### `KITCHEN_SCENE9`（10 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `20_21` | compatible | 2 | `20`→`21` | put both the frying pan and the white bowl on top of the cabinet |
| `20_22` | conflict | 2 | `20`→`22` | put the frying pan on top of the cabinet and put the frying pan on the cabinet shelf |
| `20_23` | conflict | 2 | `20`→`23` | put the frying pan on top of the cabinet and put the frying pan under the cabinet shelf |
| `20_24` | compatible | 2 | `20`→`24` | put the frying pan on top of the cabinet and turn on the stove |
| `21_22` | hard | 2 | `21`→`22` | put the white bowl on top of the cabinet and put the frying pan on the cabinet shelf |
| `21_23` | compatible | 2 | `21`→`23` | put the white bowl on top of the cabinet and put the frying pan under the cabinet shelf |
| `21_24` | compatible | 2 | `21`→`24` | put the white bowl on top of the cabinet and turn on the stove |
| `22_23` | conflict | 2 | `22`→`23` | put the frying pan on the cabinet shelf and put the frying pan under the cabinet shelf |
| `22_24` | compatible | 2 | `22`→`24` | put the frying pan on the cabinet shelf and turn on the stove |
| `23_24` | compatible | 2 | `23`→`24` | put the frying pan under the cabinet shelf and turn on the stove |

#### `KITCHEN_SCENE10`（10 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `26_27` | hard | 3 | `26`→`27` | put both the butter at the front and the butter at the back in the top drawer of the cabinet and close it |
| `26_28` | hard | 3 | `26`→`28` | put both the butter at the front and the chocolate pudding in the top drawer of the cabinet and close it |
| `26_29` | hard | 3 | `29`→`26` | put both the black bowl and the butter at the front in the top drawer of the cabinet and close it |
| `26_30` | degenerate | 2 | `30`→`26` | put the butter at the front in the top drawer of the cabinet and close it |
| `27_28` | hard | 3 | `27`→`28` | put both the butter at the back and the chocolate pudding in the top drawer of the cabinet and close it |
| `27_29` | hard | 3 | `29`→`27` | put both the black bowl and the butter at the back in the top drawer of the cabinet and close it |
| `27_30` | degenerate | 2 | `30`→`27` | put the butter at the back in the top drawer of the cabinet and close it |
| `28_29` | hard | 3 | `29`→`28` | put both the black bowl and the chocolate pudding in the top drawer of the cabinet and close it |
| `28_30` | degenerate | 2 | `30`→`28` | put the chocolate pudding in the top drawer of the cabinet and close it |
| `29_30` | hard | 2 | `29`→`30` | put the black bowl in the top drawer of the cabinet and close it |

#### `LIVING_ROOM_SCENE1`（6 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `31_32` | compatible | 2 | `31`→`32` | put both the ketchup and the cream cheese box in the basket |
| `31_33` | compatible | 2 | `31`→`33` | put both the ketchup and the alphabet soup in the basket |
| `31_34` | compatible | 2 | `31`→`34` | put both the ketchup and the tomato sauce in the basket |
| `32_33` | compatible | 2 | `32`→`33` | put both the cream cheese box and the alphabet soup in the basket |
| `32_34` | compatible | 2 | `32`→`34` | put both the cream cheese box and the tomato sauce in the basket |
| `33_34` | compatible | 2 | `33`→`34` | put both the alphabet soup and the tomato sauce in the basket |

#### `LIVING_ROOM_SCENE2`（10 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `35_36` | compatible | 2 | `35`→`36` | put both the orange juice and the milk in the basket |
| `35_37` | compatible | 2 | `35`→`37` | put both the orange juice and the butter in the basket |
| `35_38` | compatible | 2 | `35`→`38` | put both the orange juice and the alphabet soup in the basket |
| `35_39` | compatible | 2 | `35`→`39` | put both the orange juice and the tomato sauce in the basket |
| `36_37` | compatible | 2 | `36`→`37` | put both the milk and the butter in the basket |
| `36_38` | compatible | 2 | `36`→`38` | put both the milk and the alphabet soup in the basket |
| `36_39` | compatible | 2 | `36`→`39` | put both the milk and the tomato sauce in the basket |
| `37_38` | compatible | 2 | `37`→`38` | put both the butter and the alphabet soup in the basket |
| `37_39` | compatible | 2 | `37`→`39` | put both the butter and the tomato sauce in the basket |
| `38_39` | compatible | 2 | `38`→`39` | put both the alphabet soup and the tomato sauce in the basket |

#### `LIVING_ROOM_SCENE4`（3 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `42_43` | compatible | 2 | `42`→`43` | put both the black bowl on the left and the salad dressing in the tray |
| `42_44` | compatible | 2 | `42`→`44` | put both the black bowl on the left and the chocolate pudding in the tray |
| `43_44` | compatible | 2 | `43`→`44` | put both the salad dressing and the chocolate pudding in the tray |

#### `LIVING_ROOM_SCENE5`（6 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `45_46` | compatible | 2 | `45`→`46` | put the white mug on the left plate and put the yellow and white mug on the right plate |
| `45_47` | compatible | 2 | `45`→`47` | put both the white mug and the red mug on the left plate |
| `45_48` | compatible | 2 | `45`→`48` | put the white mug on the left plate and put the red mug on the right plate |
| `46_47` | compatible | 2 | `46`→`47` | put the yellow and white mug on the right plate and put the red mug on the left plate |
| `46_48` | compatible | 2 | `46`→`48` | put both the yellow and white mug and the red mug on the right plate |
| `47_48` | conflict | 2 | `47`→`48` | put the red mug on the left plate and put the red mug on the right plate |

#### `LIVING_ROOM_SCENE6`（6 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `49_50` | compatible | 2 | `49`→`50` | put both the white mug and the red mug on the plate |
| `49_51` | compatible | 2 | `49`→`51` | put the white mug on the plate and put the chocolate pudding to the left of the plate |
| `49_52` | compatible | 2 | `49`→`52` | put the white mug on the plate and put the chocolate pudding to the right of the plate |
| `50_51` | compatible | 2 | `50`→`51` | put the red mug on the plate and put the chocolate pudding to the left of the plate |
| `50_52` | compatible | 2 | `50`→`52` | put the red mug on the plate and put the chocolate pudding to the right of the plate |
| `51_52` | conflict | 2 | `51`→`52` | put the chocolate pudding to the left of the plate and put the chocolate pudding to the right of the plate |

#### `KITCHEN_SCENE2`（21 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `53_54` | compatible | 2 | `53`→`54` | put both the black bowl at the back and the black bowl at the front on the plate |
| `53_55` | compatible | 2 | `53`→`55` | put both the black bowl at the back and the middle black bowl on the plate |
| `53_56` | compatible | 2 | `53`→`56` | put the black bowl at the back on the plate and put the middle black bowl on top of the cabinet |
| `53_57` | compatible | 2 | `53`→`57` | put the black bowl at the back on the plate and open the top drawer of the cabinet |
| `53_58` | hard | 2 | `53`→`58` | put the black bowl at the back on the plate and stack the middle black bowl on top of it |
| `53_59` | compatible | 2 | `53`→`59` | put the black bowl at the back on the plate and stack the black bowl at the front on the black bowl in the middle |
| `54_55` | compatible | 2 | `54`→`55` | put both the black bowl at the front and the middle black bowl on the plate |
| `54_56` | compatible | 2 | `54`→`56` | put the black bowl at the front on the plate and put the middle black bowl on top of the cabinet |
| `54_57` | compatible | 2 | `54`→`57` | put the black bowl at the front on the plate and open the top drawer of the cabinet |
| `54_58` | compatible | 2 | `54`→`58` | put the black bowl at the front on the plate and stack the middle black bowl on the back black bowl |
| `54_59` | conflict | 2 | `54`→`59` | put the black bowl at the front on the plate and stack the black bowl at the front on the black bowl in the middle |
| `55_56` | conflict | 2 | `55`→`56` | put the middle black bowl on the plate and put the middle black bowl on top of the cabinet |
| `55_57` | compatible | 2 | `55`→`57` | put the middle black bowl on the plate and open the top drawer of the cabinet |
| `55_58` | conflict | 2 | `55`→`58` | put the middle black bowl on the plate and stack the middle black bowl on the back black bowl |
| `55_59` | hard | 2 | `55`→`59` | put the middle black bowl on the plate and stack the black bowl at the front on top of it |
| `56_57` | compatible | 2 | `56`→`57` | put the middle black bowl on top of the cabinet and open the top drawer of the cabinet |
| `56_58` | conflict | 2 | `56`→`58` | put the middle black bowl on top of the cabinet and stack the middle black bowl on the back black bowl |
| `56_59` | hard | 2 | `56`→`59` | put the middle black bowl on top of the cabinet and stack the black bowl at the front on top of it |
| `57_58` | compatible | 2 | `57`→`58` | open the top drawer of the cabinet and stack the middle black bowl on the back black bowl |
| `57_59` | compatible | 2 | `57`→`59` | open the top drawer of the cabinet and stack the black bowl at the front on the black bowl in the middle |
| `58_59` | hard | 2 | `58`→`59` | stack the middle black bowl on the back black bowl and stack the black bowl at the front on top of it |

#### `KITCHEN_SCENE5`（10 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `60_61` | conflict | 2 | `60`→`61` | put the black bowl in the top drawer of the cabinet and put the black bowl on the plate |
| `60_62` | compatible | 2 | `60`→`62` | put both the black bowl and the ketchup in the top drawer of the cabinet |
| `60_63` | conflict | 2 | `60`→`63` | put the black bowl in the top drawer of the cabinet and put the black bowl on top of the cabinet |
| `60_64` | hard | 2 | `60`→`64` | put the black bowl in the top drawer of the cabinet and close it |
| `61_62` | compatible | 2 | `61`→`62` | put the black bowl on the plate and put the ketchup in the top drawer of the cabinet |
| `61_63` | conflict | 2 | `61`→`63` | put the black bowl on the plate and put the black bowl on top of the cabinet |
| `61_64` | compatible | 2 | `61`→`64` | put the black bowl on the plate and close the top drawer of the cabinet |
| `62_63` | hard | 2 | `62`→`63` | put the ketchup in the top drawer of the cabinet and put the black bowl on top of the cabinet |
| `62_64` | hard | 2 | `62`→`64` | put the ketchup in the top drawer of the cabinet and close it |
| `63_64` | compatible | 2 | `63`→`64` | put the black bowl on top of the cabinet and close the top drawer of the cabinet |

#### `KITCHEN_SCENE7`（3 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `65_66` | conflict | 2 | `65`→`66` | put the white bowl on the plate and put the white bowl to the right of the plate |
| `65_67` | compatible | 2 | `65`→`67` | put the white bowl on the plate and open the microwave |
| `66_67` | compatible | 2 | `66`→`67` | put the white bowl to the right of the plate and open the microwave |

#### `STUDY_SCENE1`（6 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `68_69` | conflict | 2 | `68`→`69` | put the book in the left compartment of the caddy and put the book in the right compartment of the caddy |
| `68_70` | conflict | 2 | `68`→`70` | put the book in the left compartment of the caddy and put the book in the front compartment of the caddy |
| `68_71` | compatible | 2 | `68`→`71` | put the book in the left compartment of the caddy and put the yellow and white mug to the right of the caddy |
| `69_70` | conflict | 2 | `69`→`70` | put the book in the right compartment of the caddy and put the book in the front compartment of the caddy |
| `69_71` | compatible | 2 | `69`→`71` | put the book in the right compartment of the caddy and put the yellow and white mug to the right of the caddy |
| `70_71` | compatible | 2 | `70`→`71` | put the book in the front compartment of the caddy and put the yellow and white mug to the right of the caddy |

#### `STUDY_SCENE2`（6 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `72_73` | conflict | 2 | `72`→`73` | put the book in the left compartment of the caddy and put the book in the right compartment of the caddy |
| `72_74` | conflict | 2 | `72`→`74` | put the book in the left compartment of the caddy and put the book in the front compartment of the caddy |
| `72_75` | conflict | 2 | `72`→`75` | put the book in the left compartment of the caddy and put the book in the back compartment of the caddy |
| `73_74` | conflict | 2 | `73`→`74` | put the book in the right compartment of the caddy and put the book in the front compartment of the caddy |
| `73_75` | conflict | 2 | `73`→`75` | put the book in the right compartment of the caddy and put the book in the back compartment of the caddy |
| `74_75` | conflict | 2 | `74`→`75` | put the book in the front compartment of the caddy and put the book in the back compartment of the caddy |

#### `STUDY_SCENE3`（10 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `76_77` | conflict | 2 | `76`→`77` | put the book in the left compartment of the caddy and put the book in the right compartment of the caddy |
| `76_78` | conflict | 2 | `76`→`78` | put the book in the left compartment of the caddy and put the book in the front compartment of the caddy |
| `76_79` | compatible | 2 | `76`→`79` | put the book in the left compartment of the caddy and put the white mug to the right of the caddy |
| `76_80` | compatible | 2 | `76`→`80` | put the book in the left compartment of the caddy and put the red mug to the right of the caddy |
| `77_78` | conflict | 2 | `77`→`78` | put the book in the right compartment of the caddy and put the book in the front compartment of the caddy |
| `77_79` | compatible | 2 | `77`→`79` | put the book in the right compartment of the caddy and put the white mug to the right of the caddy |
| `77_80` | compatible | 2 | `77`→`80` | put the book in the right compartment of the caddy and put the red mug to the right of the caddy |
| `78_79` | compatible | 2 | `78`→`79` | put the book in the front compartment of the caddy and put the white mug to the right of the caddy |
| `78_80` | compatible | 2 | `78`→`80` | put the book in the front compartment of the caddy and put the red mug to the right of the caddy |
| `79_80` | compatible | 2 | `79`→`80` | put both the white mug and the red mug to the right of the caddy |

#### `STUDY_SCENE4`（6 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `81_82` | compatible | 2 | `81`→`82` | put the book on the right under the cabinet shelf and put the book in the middle on the cabinet shelf |
| `81_83` | compatible | 2 | `81`→`83` | put the book on the right under the cabinet shelf and put the book on the left on top of the shelf |
| `81_84` | conflict | 2 | `81`→`84` | put the book on the right under the cabinet shelf and put the book on the right on the cabinet shelf |
| `82_83` | hard | 2 | `82`→`83` | put the book in the middle on the cabinet shelf and put the book on the left on top of the shelf |
| `82_84` | compatible | 2 | `82`→`84` | put both the book in the middle and the book on the right on the cabinet shelf |
| `83_84` | hard | 2 | `83`→`84` | put the book on the left on top of the shelf and put the book on the right on the cabinet shelf |

#### `LIVING_ROOM_SCENE3`（10 对）

| pair | class | 原子数 | 推荐 s1→s2 | 合并指令（推荐方向） |
| --- | --- | ---: | --- | --- |
| `85_86` | compatible | 2 | `85`→`86` | put both the alphabet soup and the tomato sauce in the tray |
| `85_87` | compatible | 2 | `85`→`87` | put both the alphabet soup and the butter in the tray |
| `85_88` | compatible | 2 | `85`→`88` | put both the alphabet soup and the cream cheese in the tray |
| `85_89` | compatible | 2 | `85`→`89` | put both the alphabet soup and the ketchup in the tray |
| `86_87` | compatible | 2 | `86`→`87` | put both the tomato sauce and the butter in the tray |
| `86_88` | compatible | 2 | `86`→`88` | put both the tomato sauce and the cream cheese in the tray |
| `86_89` | compatible | 2 | `86`→`89` | put both the tomato sauce and the ketchup in the tray |
| `87_88` | compatible | 2 | `87`→`88` | put both the butter and the cream cheese in the tray |
| `87_89` | compatible | 2 | `87`→`89` | put both the butter and the ketchup in the tray |
| `88_89` | compatible | 2 | `88`→`89` | put both the cream cheese and the ketchup in the tray |


### 11.3 M2 / S1

**M2 场景内提升（34 个候选）**



| candidate_id | 场景 | 任务 | 提升的物体 | 合并指令 | class | priority |
| --- | --- | --- | --- | --- | --- | --- |
| `L90_LR2_35_cream_cheese_1_ab` | LIVING_ROOM_SCENE2 | `35` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the orange juice and the cream cheese box in the basket | compatible | P0 |
| `L90_LR2_35_cream_cheese_1_ba` | LIVING_ROOM_SCENE2 | `35` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the cream cheese box and the orange juice in the basket | compatible | P0 |
| `L90_LR2_35_ketchup_1_ab` | LIVING_ROOM_SCENE2 | `35` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the orange juice and the ketchup in the basket | compatible | P0 |
| `L90_LR2_35_ketchup_1_ba` | LIVING_ROOM_SCENE2 | `35` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the ketchup and the orange juice in the basket | compatible | P0 |
| `L90_LR2_36_cream_cheese_1_ab` | LIVING_ROOM_SCENE2 | `36` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the milk and the cream cheese box in the basket | compatible | P0 |
| `L90_LR2_36_cream_cheese_1_ba` | LIVING_ROOM_SCENE2 | `36` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the cream cheese box and the milk in the basket | compatible | P0 |
| `L90_LR2_36_ketchup_1_ab` | LIVING_ROOM_SCENE2 | `36` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the milk and the ketchup in the basket | compatible | P0 |
| `L90_LR2_36_ketchup_1_ba` | LIVING_ROOM_SCENE2 | `36` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the ketchup and the milk in the basket | compatible | P0 |
| `L90_LR2_37_cream_cheese_1_ab` | LIVING_ROOM_SCENE2 | `37` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the butter and the cream cheese box in the basket | compatible | P0 |
| `L90_LR2_37_cream_cheese_1_ba` | LIVING_ROOM_SCENE2 | `37` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the cream cheese box and the butter in the basket | compatible | P0 |
| `L90_LR2_37_ketchup_1_ab` | LIVING_ROOM_SCENE2 | `37` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the butter and the ketchup in the basket | compatible | P0 |
| `L90_LR2_37_ketchup_1_ba` | LIVING_ROOM_SCENE2 | `37` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the ketchup and the butter in the basket | compatible | P0 |
| `L90_LR2_38_cream_cheese_1_ab` | LIVING_ROOM_SCENE2 | `38` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the alphabet soup and the cream cheese box in the basket | compatible | P0 |
| `L90_LR2_38_cream_cheese_1_ba` | LIVING_ROOM_SCENE2 | `38` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the cream cheese box and the alphabet soup in the basket | compatible | P0 |
| `L90_LR2_38_ketchup_1_ab` | LIVING_ROOM_SCENE2 | `38` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the alphabet soup and the ketchup in the basket | compatible | P0 |
| `L90_LR2_38_ketchup_1_ba` | LIVING_ROOM_SCENE2 | `38` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the ketchup and the alphabet soup in the basket | compatible | P0 |
| `L90_LR2_39_cream_cheese_1_ab` | LIVING_ROOM_SCENE2 | `39` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the tomato sauce and the cream cheese box in the basket | compatible | P0 |
| `L90_LR2_39_cream_cheese_1_ba` | LIVING_ROOM_SCENE2 | `39` | cream_cheese_1 → (In cream_cheese_1 basket_1_contain_region) | put both the cream cheese box and the tomato sauce in the basket | compatible | P0 |
| `L90_LR2_39_ketchup_1_ab` | LIVING_ROOM_SCENE2 | `39` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the tomato sauce and the ketchup in the basket | compatible | P0 |
| `L90_LR2_39_ketchup_1_ba` | LIVING_ROOM_SCENE2 | `39` | ketchup_1 → (In ketchup_1 basket_1_contain_region) | put both the ketchup and the tomato sauce in the basket | compatible | P0 |
| `L90_LR4_42_akita_black_bowl_2_ab` | LIVING_ROOM_SCENE4 | `42` | akita_black_bowl_2 → (In akita_black_bowl_2 wooden_tray_1_contain_region) | put both the black bowl on the left and the black bowl on the right in the tray | compatible | P0 |
| `L90_LR4_42_akita_black_bowl_2_ba` | LIVING_ROOM_SCENE4 | `42` | akita_black_bowl_2 → (In akita_black_bowl_2 wooden_tray_1_contain_region) | put both the black bowl on the right and the black bowl on the left in the tray | compatible | P0 |
| `L90_LR4_43_akita_black_bowl_2_ab` | LIVING_ROOM_SCENE4 | `43` | akita_black_bowl_2 → (In akita_black_bowl_2 wooden_tray_1_contain_region) | put both the salad dressing and the black bowl on the right in the tray | compatible | P0 |
| `L90_LR4_43_akita_black_bowl_2_ba` | LIVING_ROOM_SCENE4 | `43` | akita_black_bowl_2 → (In akita_black_bowl_2 wooden_tray_1_contain_region) | put both the black bowl on the right and the salad dressing in the tray | compatible | P0 |
| `L90_LR4_44_akita_black_bowl_2_ab` | LIVING_ROOM_SCENE4 | `44` | akita_black_bowl_2 → (In akita_black_bowl_2 wooden_tray_1_contain_region) | put both the chocolate pudding and the black bowl on the right in the tray | compatible | P0 |
| `L90_LR4_44_akita_black_bowl_2_ba` | LIVING_ROOM_SCENE4 | `44` | akita_black_bowl_2 → (In akita_black_bowl_2 wooden_tray_1_contain_region) | put both the black bowl on the right and the chocolate pudding in the tray | compatible | P0 |
| `L90_ST2_72_red_coffee_mug_1_ab` | STUDY_SCENE2 | `72` | red_coffee_mug_1 → (In red_coffee_mug_1 desk_caddy_1_right_contain_region) | put the book in the left compartment of the caddy and put the red mug in the right compartment of the caddy | compatible | P0 |
| `L90_ST2_72_red_coffee_mug_1_ba` | STUDY_SCENE2 | `72` | red_coffee_mug_1 → (In red_coffee_mug_1 desk_caddy_1_right_contain_region) | put the red mug in the right compartment of the caddy and put the book in the left compartment of the caddy | compatible | P0 |
| `L90_ST2_73_red_coffee_mug_1_ab` | STUDY_SCENE2 | `73` | red_coffee_mug_1 → (In red_coffee_mug_1 desk_caddy_1_right_contain_region) | put both the book and the red mug in the right compartment of the caddy | compatible | P0 |
| `L90_ST2_73_red_coffee_mug_1_ba` | STUDY_SCENE2 | `73` | red_coffee_mug_1 → (In red_coffee_mug_1 desk_caddy_1_right_contain_region) | put both the red mug and the book in the right compartment of the caddy | compatible | P0 |
| `L90_ST2_74_red_coffee_mug_1_ab` | STUDY_SCENE2 | `74` | red_coffee_mug_1 → (In red_coffee_mug_1 desk_caddy_1_right_contain_region) | put the book in the front compartment of the caddy and put the red mug in the right compartment of the caddy | compatible | P0 |
| `L90_ST2_74_red_coffee_mug_1_ba` | STUDY_SCENE2 | `74` | red_coffee_mug_1 → (In red_coffee_mug_1 desk_caddy_1_right_contain_region) | put the red mug in the right compartment of the caddy and put the book in the front compartment of the caddy | compatible | P0 |
| `L90_ST2_75_red_coffee_mug_1_ab` | STUDY_SCENE2 | `75` | red_coffee_mug_1 → (In red_coffee_mug_1 desk_caddy_1_right_contain_region) | put the book in the back compartment of the caddy and put the red mug in the right compartment of the caddy | compatible | P0 |
| `L90_ST2_75_red_coffee_mug_1_ba` | STUDY_SCENE2 | `75` | red_coffee_mug_1 → (In red_coffee_mug_1 desk_caddy_1_right_contain_region) | put the red mug in the right compartment of the caddy and put the book in the back compartment of the caddy | compatible | P0 |



**S1 特殊候选（2 个）**



| candidate_id | merged goal atoms | 合并指令（模板化） | 说明 |
| --- | --- | --- | --- |
| `L90_KS8_18_moka_pot_2_ab` | (On moka_pot_2 flat_stove_1_cook_region) ; (Turnoff flat_stove_1) | put the left moka pot on the stove and turn it off | synthesized instruction (not official); '(Turnon flat_stove_1)' dropped because it already holds in :init; ab s1 = place the left moka pot (revertable, P0), ba s1 = Turnoff (not revertable, P1). |
| `L90_KS8_18_moka_pot_2_ba` | (Turnoff flat_stove_1) ; (On moka_pot_2 flat_stove_1_cook_region) | turn off the stove and put the left moka pot on it | synthesized instruction (not official); '(Turnon flat_stove_1)' dropped because it already holds in :init; ab s1 = place the left moka pot (revertable, P0), ba s1 = Turnoff (not revertable, P1). |

## 12. 风险与未验证项

1. **实测覆盖仍不完整**：低难度子集 161 条已完成 pi05 × 3 seeds 实测（41/483 = 8.49%，见 §15）；**其余 161 条**（M2 34、S1 2、P1 7、P2 38、P3 64 与 17 条 held-out）尚未实测，不能外推。早期 10 条两段候选 + 对照 17 的基线见 `docs/libero-90-baseline-pi05-seed3.md`、`docs/libero-90-baseline-seed-sweep.md`。
2. **组合池 82 条单目标任务本身尚未测 pi05 baseline**：必须先补，否则"可行/稳定"筛选无意义。
3. **init 源敏感性未测**：GOAL 已证 init 源可翻转单任务成败，L90 同场景 init 文件内容不同 → 必须做 init 源对照。
4. **staged 在 L90 上的效果未测**：GOAL 2/3 是 10 任务单场景的结果，不能直接外推。
5. **指令是模板化合成（T1–T10 + T4b）**：L90 官方 language 存在多实例（butter_1/2、bowl_1/2/3、moka_pot_1/2、plate_1/2、yellow_book_1/2）与空间描述（front/back/left/right/middle）差异 → 模板化后仍可能出现指代歧义，需要人工抽检或做措辞变体实验（详见 `INSTRUCTION_TEMPLATES.md` 的歧义清单）。
6. **Turnon/Turnoff 不可回滚**：L90 单目标池里 `08/24`（Turnon）与 `18`（Turnoff）只能作 s2 或 P1 双目标任务，不能作 rollback 用例的 s1。
7. **M2 的合成措辞不是官方原文**：LIVING_ROOM_SCENE2 / STUDY_SCENE2 / LIVING_ROOM_SCENE4 / KITCHEN_SCENE8 的提升候选必须人工确认指令与目标一致。
8. **3 原子候选（9 对 / 18 个方向）难度未知**：GOAL 的 8 个 new-goal（含 3 原子链）动态 0/24，提示 3 原子链在 pi05 下大概率不可解；本文把 3 原子对保留在清单里，3 原子的 hard 对已在 P2。

## 13. 复现与产物索引

| 产物 | 路径 |
| --- | --- |
| **分场景 HTML 报告** | [`runs/libero-90-combos-20261025/report/index.html`](../runs/libero-90-combos-20261025/report/index.html) |
| 模板化候选（330 条，新指令） | [`runs/libero-90-combos-20261025/candidates-instructed.json`](../runs/libero-90-combos-20261025/candidates-instructed.json) |
| 指令模板说明 | [`runs/libero-90-combos-20261025/INSTRUCTION_TEMPLATES.md`](../runs/libero-90-combos-20261025/INSTRUCTION_TEMPLATES.md) |
| pi0 参考视频清单 | [`runs/libero-90-combos-20261025/report/video-manifest.json`](../runs/libero-90-combos-20261025/report/video-manifest.json) / [`VIDEO_SOURCES.md`](../runs/libero-90-combos-20261025/report/VIDEO_SOURCES.md) |
| 生成器（BDDL 解析 → 候选 → JSON/表格） | [`scripts/build_libero90_combos.py`](../scripts/build_libero90_combos.py) |
| 生成器（模板化指令） | [`scripts/build_libero90_instructions.py`](../scripts/build_libero90_instructions.py) |
| 生成器（HTML 报告） | [`scripts/build_libero90_scene_report.py`](../scripts/build_libero90_scene_report.py) |
| 生成器（pi0 视频清单） | [`scripts/build_libero90_video_manifest.py`](../scripts/build_libero90_video_manifest.py) |
| 机读候选清单 | [`runs/libero-90-combos-20261025/candidates.json`](../runs/libero-90-combos-20261025/candidates.json) |
| 全量候选表 | [`runs/libero-90-combos-20261025/CASE_LIST.md`](../runs/libero-90-combos-20261025/CASE_LIST.md) |
| 运行/口径说明 | [`runs/libero-90-combos-20261025/README.md`](../runs/libero-90-combos-20261025/README.md) |
| LIBERO-90 清点与 7/83 对账 | `.tmp/libero90-combos/inventory-summary.md`（脚本 `analyze_libero90.py`） |
| 语义分类原始 JSON | `.tmp/libero90-combos/pair-semantics.json`（BDDL 口径 147 对完整分析；组合候选按 `scene_review_decisions.json` 过滤为 143 对，脚本 `classify_pairs.py`） |
| GOAL / OBJECT 方法抽取 | `.tmp/libero90-combos/method-goal.md`、`method-object.md` |
| 逐场景复核口径（唯一真源） | [`runs/libero-90-combos-20261025/scene_review_decisions.json`](../runs/libero-90-combos-20261025/scene_review_decisions.json) |
| 独立审计（第 1 轮 / 第 2 轮） | `.tmp/libero90-combos/audit.md` / `.tmp/libero90-combos/audit-round2.md` |

复现命令（WSL）：
```bash
cd /home/tarowang/workspace/roboot/libero-rollback
.venv/bin/python scripts/build_libero90_combos.py --check          # 候选/分类/清单
.venv/bin/python scripts/build_libero90_instructions.py --check    # 模板化指令（330 条）
.venv/bin/python scripts/build_libero90_video_manifest.py --check  # pi0 参考视频清单/资产
.venv/bin/python scripts/build_libero90_scene_report.py --check    # 分场景 HTML 报告
```

## 14. 审计结论

> **v2 修订（2026-10-25，用户逐场景复核 v1）**：KS1 剔除 `00` 后，候选数 330→322、M1 294→286 ordered、T5 模板命中 8→0、KS1 场景候选 20→12；4 个生成器已重跑并通过各自 `--check`（combos 80/80、instructions 54/54、video manifest PASS、分场景 HTML 51/51）。下述第二轮审计基于 330 版本，数据层结论对修订后仍适用（只是删除 8 个含 00 的 ordered 候选）。

**第二轮独立审计（verifier，2026-10-25）：PASS-WITH-ISSUES（0 blocker / 4 major / 6 minor）**。4 个 major 都是文档表述问题（模板章节自相矛盾、旧指令残留、范围表述超限），已按审计建议全部修复并重生成本文；6 个 minor 中 5 项已修复（2 条模板 id 误标 T6→T10 已重跑生成器与报告、计数 105→134、§13 脚本索引、VIDEO_SOURCES 扫描口径），第 6 项（L10 证据编号为 tasks_info 序）已在下文注明。完整报告：`.tmp/libero90-combos/audit-round2.md`（第 1 轮：`audit.md`）。

独立复算快照（不采信生成器自述）：
- **指令**：330/330 有模板字段；模板分布 T1 92 / T2 18 / T3 126 / T4 16 / T4b 12 / T5 8 / T6 24 / T7 4 / T8 2 / T9 8 / T10 20 = 330；语义保真 330/330；naive 118 相同、212 改写；生成器 `--check` 47/47，重跑逐字节一致。
- **视频**：53/53 文件 sha256/字节与 manifest 及源视频一致；10 段 exact_scene_l10 经 L10 配置复核确为同场景，43 段同族参考；40 段 pi0 baseline 与 `evidence.json` 一致（success 35/40）；20/20 场景 ≥1 段；53/53 `honest_note` 明示"非 L90 实测"。
- **HTML**：27 sections（20 场景 + 7 全局）、90 单任务行、330 候选行逐字段一致、61/61 指标复算一致、11 模板行、53 视频卡、346 链接 0 失效 / 0 外链 CDN；`--check` 33/33。
- **可复现性**：3 个新脚本的"改坏输入"测试均能失败（fail-fast 有效）。
- **未验证**：没有任何动态仿真（组合任务可解性、模板指令效果、rollback 语义均待实测）；LIBERO-90 全量 baseline 视频缺失（见 `report/VIDEO_SOURCES.md`）。

> 注（审计 minor-⑥）：`INSTRUCTION_TEMPLATES.md` 与本文引用的 LIBERO-10 任务编号（/04、/05…）是 **LIBERO-10 的 `tasks_info.txt` 顺序**，不是 LIBERO-90 的编号，也不是 benchmark idx；跑 runtime 时按 §8.2 的映射换 benchmark idx。

## 15. 低难度子集 pi05 × 3 seeds 验证结果（2026-10-26）

> 运行目录 [`runs/libero-90-easy-pi05-20261026/`](../runs/libero-90-easy-pi05-20261026/README.md) · 结果报告 [`report/index.html`](../runs/libero-90-easy-pi05-20261026/report/index.html) · 原始数据 [`analysis/summary.json`](../runs/libero-90-easy-pi05-20261026/analysis/summary.json) · 校验 [`analysis/final_checks.json`](../runs/libero-90-easy-pi05-20261026/analysis/final_checks.json)。

**范围**：从 322 条候选中按难度分取前 161（50%，规则见验证目录 `prep/select_easy_subset.py`：M1-P0-compatible-n_atoms2，按同落点容量/共享家具/开关/指令长度评分升序）；seeds 0/1/2；max_steps 600、replan 10、video off（吞吐优先）；每个候选使用 `init_source` 官方 `.pruned_init` 的第 `seed%50` 行（sidecar，digest 预检验证）；pi05 zero-shot 单指令。

| 指标 | 结果 |
| --- | --- |
| 总 success | **41 / 483 = 8.49%** |
| 按 seed | seed0 12/161 = 7.45% · seed1 13/161 = 8.07% · seed2 16/161 = 9.94% |
| 稳定性 | **19 候选 ≥1 次成功；12 候选 ≥2 seeds；10 候选 3/3 全成功** |
| 子任务（最终 0/1/2） | 213 / 229 / 41；442/483 跑满 600 步（失败以超时停滞为主） |
| mean steps | 573.2（成功多在 220–380 步） |
| 指令模板 | **T1 14.06%(27/192)** > T3 7.97%(11/138) > T6 4.55%(3/66) > T2 0%(0/72) > T10 0%(0/44) |
| 难度桶 | same_destination(capacity) 10.98%(27/246) > independent 6.48%(14/216) > same_furniture 0%(0/21) |
| 顺序 | ab 8.23% vs ba 8.75%（无方向偏置） |
| 场景 | LIVING_ROOM 主导：LR3 23.33%(14/60)、LR5 20%(6/30)、LR1/LR6 16.67%、LR2 11.67%(7/60)；KITCHEN 仅 KS2 4.17%(3/72)；其余 KITCHEN/STUDY 全 0 |
| s1 轨迹 | 183 episodes 曾完成 s1（首真均值 198.6 步）、163 最终保持、123 次回撤/45 eps |

**10 个 3/3 全成功候选**：`L90_LR1_32_33_ab/ba`、`L90_LR2_38_39_ab/ba`、`L90_LR3_85_86_ba`、`L90_LR3_87_88_ab/ba`、`L90_LR5_45_46_ab/ba`、`L90_LR6_49_52_ab`（全部 LIVING_ROOM，T1 同容器 ×4 / T3 不同落点 ×3 等）。

**结论**：
1. **用户指定的 L10"put both A and B in C"模板（T1）验证为最有效指令族**（14.06%，约为 naive 组合基线 4.3% 的 3 倍）；同容器（capacity）任务显著优于 independent。
2. 10 条 3/3 + 12 条 ≥2 seeds 候选可直接进入 **rollback 用例原型**（补视频 → s1 完成→注入回退→s2 自修复）。
3. KITCHEN/STUDY 场景（除 KS2 3/72）全部 0，且 229/483 是"完成 1 段后停滞" → 下一轮应优先对 kitchen/study 子集做 **staged / instruction-switch** 对照与指令变体实验，而不是继续扩量。
4. 与参考对比：本子集 8.49% > OBJECT 4.0%（12/300，6 any/5 multi/1 all）> GOAL 单指令 4.3%（2/47），且 3/3 稳定候选 10 个（OBJECT 1 个）→ v2 候选 + 模板化指令 + 难度筛查后的低难度子集是**可用的双目标任务来源**。

**未验证部分（161 条）**：M2 34 + S1 2 + M1 中 P1/P2/P3 108（P1 6、P2 38、P3 64）+ 17 条 held-out（P0 中难度最高的 17 条）= **161**，不可外推。

**场景覆盖**：本子集覆盖 17/20 个场景；`KITCHEN_SCENE8`、`KITCHEN_SCENE10`、`STUDY_SCENE2` 不在子集内，其结论不能由本 run 推断（KS10 的 10 对候选全部为 P2/P3）。

**局限**：video off；单指令 zero-shot，未测 staged/rollback；seeds 仅 3（非官方 50 trials）；KITCHEN/STUDY 全部失败可能同时反映场景/指令分布与任务难度，需 staged 对照才能归因。

## 16. 与 LIBERO-10 / LIBERO-GOAL / LIBERO-OBJECT 的重复性审计（2026-10-26）

> 产物：[`dup-audit/DUPLICATE_AUDIT.md`](../runs/libero-90-combos-20261025/dup-audit/DUPLICATE_AUDIT.md) · 逐候选注解 [`duplicates.json`](../runs/libero-90-combos-20261025/dup-audit/duplicates.json) · 清单 [`clean_pool.csv`](../runs/libero-90-combos-20261025/dup-audit/clean_pool.csv) · 匹配器 `dup-audit/audit_duplicates.py`；参考侧抽取 `.tmp/libero90-combos/dup-ref/{l10-goal-reference.json,object-reference.json}`（118 + 140 条，canonicalization 对 L90 90/90 回算验证）。

**判定**：`exact_duplicate` = goal 原子集合相同 **且** 场景指纹（`:regions`+`:fixtures`，fixtures 保原序）相同；`semantic_duplicate` = goal 相同但场景/实例不同；`partial_overlap` = 与参考单任务共享 1 个原子（组合任务固有，不算重复）。

| 判定 | ordered 候选 | 无序任务 | 说明 |
| --- | ---: | ---: | --- |
| **exact（真重复）** | **16** | **8** | 7 个 LIBERO-10 官方任务（/00 /01 /04 /05 /06 /07 /08）+ LIBERO-90 已有双任务 05 |
| internal（与 L90 已有同实体两原子任务重复） | 6 | 3 | degenerate 候选 `KS10_26_30/27_30/28_30` = 已有任务 26/27/28（`In butter/pudding + Close top drawer`），本为 invalid |
| semantic（同 goal 异环境，clean） | 42 | 21 | matcher raw 52；clean 42（OBJECT 40、L10 跨场景 4、GOAL 2、L90 0；含 4 条双套件重叠） |
| **unique（无参考同 goal）** | **258** | **129** | 真正新增候选；组合任务仍会与单任务共享原子（partial_overlap 118 条，正常） |
| 合计 | 322 | 161 | — |

**exact 重复明细（8 任务）**：`L10/00` = KS3 07+08；`L10/01` = KS4 12+14；`L10/04` = LR1 32+33；`L10/05` = LR2 38+39；`L10/06` = **M2** LR2 37+cream_cheese；`L10/07` = LR5 45+46；`L10/08` = LR6 49+52；`L90/05` = KS3 06+08。L10 中不能由 L90 拼出的 3 条：/02（缺"杯进微波炉"单任务）、/03（缺 moka_pot_2）、/09（STUDY_SCENE1 缺 back compartment）。**所有 exact 重复的 init 文件均不同**（L90 用 init_source 的 pruned_init、L10 用自身 init；同分布不同样本）。

**对已验证 161 条的影响（关键）**：

| 分组 | 候选数 | episodes | success | 成功率 |
| --- | ---: | ---: | ---: | ---: |
| exact 重复（L10 已知任务） | 8 | 24 | **23** | **95.8%** |
| semantic 重复 | 24 | 72 | 1 | 1.4% |
| unique（真正新任务） | 129 | 387 | 17 | **4.39%** |
| 合计 | 161 | 483 | 41 | 8.49% |

→ **8.49% 的总成功率被 8 条 L10 已知任务显著抬高**；去掉 exact 重复后为 18/459 = 3.92%，只统计 truly-unique 为 **17/387 = 4.39%**，与 LIBERO-OBJECT 的 4.0% 一致。10 个 3/3 全成功候选中**仅 3 个是真正新任务**（`LR3_85_86_ba`、`LR3_87_88_ab/ba`，均为 wooden_tray 场景——与 OBJECT basket 目标集不同）；其余 7 条是 L10 官方任务的重复。

**建议**：① 16 条 exact 立即打 `duplicate_of` 标签，可保留为对照/校准组（不要计入"新增任务"）；② 6 条 internal（degenerate）直接从任何新增统计剔除；③ 42 条 semantic 打 `goal_set_overlap`（若目标是新任务类型则从新颖性统计排除）；④ 净候选口径：严格去重 306 ordered / 153 任务，新颖性口径 **258 ordered / 129 任务**；⑤ 后续验证/报告必须拆分"重复 vs unique"成功率。⑥ 独立复核（verifier, task-18）：**PASS-WITH-ISSUES（0 blocker / 1 major / 6 minor）**，数据层候选级 0 差异；本报告已按复核意见修正（semantic 两口径、L10 bench index、partial_overlap 措辞、internal degenerate、canonicalization 元数据）。

## 17. 按用户口径的重复处置与 rollback 任务基数（2026-10-26）

> 产物：[`DEDUP_DECISION.md`](../runs/libero-90-combos-20261025/dup-audit/DEDUP_DECISION.md) · 逐候选判定 [`dedup_decision.json`](../runs/libero-90-combos-20261025/dup-audit/dedup_decision.json) · 去重明细 §16。

**用户口径**：**A** = 场景重复 + 任务一致 + 指令完全相同 → 无需验证、永不算新候选；**B** = 场景重复 + 任务一致 + 指令不同 → 仍有验证价值，取成功指令作为任务描述；**C** = 同 goal 原子但场景不同 → 不构成"场景重复"（按用户定义不是重复）；**D** = 无任何参考任务同 goal。

### 17.1 问题 1：322 条构造候选是否需要验证

| 判定 | ordered | 无序任务 | 处置 |
| --- | ---: | ---: | --- |
| **A（跳过）** | **15**（valid 9 + invalid 6） | 11 | **无需验证**；其中 8 条 vs LIBERO-10、1 条 vs L90/05、6 条为 invalid degenerate（26/27/28） |
| **B（需验证）** | **7**（已验 4，剩 3） | —（与 A 共用任务） | 验证指令变体；已验 4 条 11/12 成功，剩 `KS3_06_08_ab`、`KS3_07_08_ab`、`LR2_37_cream_cheese_1_ab` |
| C（同 goal 异场景） | 42 | 21 | 可验证（非重复） |
| D（全新） | 258 | 129 | 可验证 |
| 合计 | 322 | 161 | — |

- **与 LIBERO-10**：7/10 个官方任务被复现（A 8 条 + B 6 条）；L10/02、/03、/09 无法由 L90 拼出。
- **与 LIBERO-GOAL / LIBERO-OBJECT**：场景指纹无交集（独立场景族）→ **0 条场景重复**；分别有 2 / 40 条"同 goal 但场景不同"（C 类，按定义不是重复）。
- **算力**：全部**有效**候选 258 × 3 seeds = 774 episodes；跳过 valid A 9 → **747 episodes（省 27，约 1.5h 双 worker）**。剩余有效 97 条中 valid A 5 可跳过 → 补验 92 条 ×3 = **276 episodes**；B 类剩 3 条可先补 9 episodes 判定指令。

### 17.2 问题 2：本次成功候选的重复性与 rollback 基数

本次成功候选 19 个：

| 类别 | 成功候选 | 处置 |
| --- | ---: | --- |
| A（指令与 L10 官方完全相同） | 4（`LR1_32_33_ba`、`LR2_38_39_ab`、`LR5_45_46_ab`、`LR6_49_52_ab`） | **排除，不能作为新 rollback 基数** |
| B（同任务、指令不同且成功） | 4（`LR1_32_33_ab`、`LR2_38_39_ba`、`LR5_45_46_ba`、`LR6_49_52_ba`） | 可用，任务描述取本次成功指令变体 |
| C（同 goal 异场景） | 1（`LR2_37_38_ba`） | 可用（新场景实例） |
| D（全新） | 10（KS2×3、LR3×7） | 可用（新任务） |
| **可用合计（B+C+D）** | **15 candidates / 11 tasks** | — |
| 其中严格全新（C+D） | 11 candidates / 7 tasks | — |

- **10 个 3/3 全成功候选中**：A 排除 4 条，B 可用 3 条（`LR1_32_33_ab`、`LR2_38_39_ba`、`LR5_45_46_ba`，不同指令均 3/3），D 可用 3 条（`LR3_85_86_ba`、`LR3_87_88_ab/ba`——真正全新）。
- → **把 A 类 4 个成功候选剔除后，可用 rollback 基数 = 15 candidates / 11 tasks**；若只要"全新任务"则用 C+D = 11 candidates / 7 tasks。

## 18. 高难度剩余候选单 seed 验证结果（2026-10-26）

> 运行目录 [`runs/libero-90-hard-pi05-20261026/`](../runs/libero-90-hard-pi05-20261026/README.md) · 结果 [`analysis/summary.md`](../runs/libero-90-hard-pi05-20261026/analysis/summary.md) · 终检 [`analysis/final_checks.json`](../runs/libero-90-hard-pi05-20261026/analysis/final_checks.json) · 独立审计 [`AUDIT.md`](../runs/libero-90-hard-pi05-20261026/AUDIT.md)（verifier PASS 0/0/0）。

**运行集**：去重后剩余 92 条（`valid==True` 且不在 easy 161 且 `axis != A_skip`；排除 64 invalid + 5 valid A）。组成：route M1 57 / M2 33 / S1 2；priority P0 51 / P1 5 / P2 36；axis D 73 / C 16 / B 3；class compatible 56 / hard 36；11 场景。协议：**单 seed0**、max_steps 600、replan 10、video off、双 worker（1.96h 墙钟，46.9 eps/h）。

| 指标 | 结果 |
| --- | --- |
| success | **6 / 92 = 6.52%**（单 seed；mean steps 576.77；子任务最终 0/1/2 = 43/43/6；86/92 跑满 600 步） |
| 成功候选 | `KS3_07_08_ab`（B，=L10/00 重复方向，239 步）、`LR2_37_cream_cheese_1_ab`（B，=L10/06 重复方向，260 步）、`LR4_42_akita_black_bowl_2_ab/ba`（D，M2，254–259 步）、`LR4_44_akita_black_bowl_2_ab/ba`（D，M2，254–257 步） |
| axis | **B 2/3 = 66.7%** · **D 4/73 = 5.48%** · C 0/16 = 0% → **新任务（D）4/73 = 5.48%，C+D 4/89 = 4.49%** |
| route | M2 **5/33 = 15.15%** > M1 1/57 = 1.75% > S1 0/2 |
| priority | P0 **6/51 = 11.76%**；P1 0/5、P2 0/36（**含 switch/P2 的高难度层 0 成功**） |
| class | compatible 6/56 = 10.71%；hard **0/36** |
| 场景 | LR4 **4/6 = 66.7%**、KS3 1/2、LR2 1/19，其余 8 场景 0 |
| bucket / 模板 | same_destination 5/39=12.82% > same_furniture 1/21=4.76% > independent 0/32；T1 5/27=18.52%、T7 1/2，其余 0 |
| s1 轨迹 | 30 eps 曾完成 s1（首真均值 206 步）、28 最终保持、回撤 18 次/5 eps |

**关键结论**：
1. **B 类指令变体验证有效**：剩余 3 条 B 中 2 条成功（L10/00 与 L10/06 的"不同指令顺序/措辞"方向），支持"任务相同但指令不同值得验证、取成功指令"的判断；唯一失败的 B 是 `KS3_06_08_ab`（L90/05 方向）。
2. **高难度层基本不可用**：P1/P2、class hard（含 Turnon/Turnoff/三原子等）**0/41 成功**；C 类（跨场景同 goal）0/16 → 这些任务需要 staged / instruction-switch / rollback 干预，zero-shot 单指令不够。
3. **新任务成功集中在 M2 提升 + LR4 场景**（`LR4_42/44` 两条 M2 任务 ×2 方向），与 easy run 的 LR3 tray 族一起构成"真正新增"的稳定候选来源。

> 注：以下 §18 合并口径为 easy + hard(seed0) 的旧快照；**easy + hard 各 3 seeds 全量合并**见 §20（**253 candidates / 759 episodes / 56 success = 7.38%**）与合并 HTML 报告 [`runs/libero-90-validation-merged-20261027/report/index.html`](../runs/libero-90-validation-merged-20261027/report/index.html)。

**合并 easy + hard 两次验证（累计）**：

| 口径 | episodes | success | 成功率 |
| --- | ---: | ---: | ---: |
| 全部 | 483 + 92 = **575** | 41 + 6 = **47** | **8.17%** |
| **新任务（C+D，剔除 A/B 重复）** | 459 + 89 = **548** | 18 + 4 = **22** | **4.01%** |
| 仅 truly-unique（D） | 387 + 73 = 460 | 17 + 4 = **21** | **4.57%** |

**rollback 候选基数更新**：easy 15 candidates/11 tasks（B 4 + C 1 + D 10）+ hard 6 candidates/4 tasks（B 2 + D 4）→ **累计 21 个成功候选 / 15 个不同任务**；若只要"严格全新"（C+D）：**15 candidates / 9 tasks**。其中 hard 的 6 条只有 seed0 数据，稳定性需补 seed1/2（6 条 ×2 = 12 episodes ≈ 30 分钟）后再进 rollback 原型。

**建议下一步**：① 对 hard 的 6 个成功候选补 seed1/2（12 episodes）确认稳定性；② 若稳定，连同 easy 的 3 个 3/3 新任务（LR3 tray）一起做视频 + rollback 注入原型；③ P1/P2/hard 层（0/41）暂不扩量，应先做 staged/instruction-switch 对照。

## 19. hard 成功候选 seed1/2 稳定性补测（2026-10-26）

> 运行目录 [`runs/libero-90-hard-success-seeds12-20261026/`](../runs/libero-90-hard-success-seeds12-20261026/README.md)（新目录，资产从 hard run 字节拷贝；仅跑 seeds1/2，seed0 引用 hard run）· 结果 [`analysis/summary.md`](../runs/libero-90-hard-success-seeds12-20261026/analysis/summary.md) · 终检 `analysis/final_checks.json`（12/12、rc=0/0、sidecar row1/row2 digest 均与 eval.log 一致）。

**本次运行**：6 条 hard 成功候选 × seeds{1,2} = 12 episodes；双 worker，墙钟 **10.6 min**，max_steps 600 / replan 10 / video off；**success 9/12 = 75%**（seed1 5/6、seed2 4/6）。

**合并稳定性表（18 episodes = 6 × seeds 0/1/2）**：

| candidate_id | axis | seed0 | seed1 | seed2 | 成功 seeds | ≥2 | 3/3 | steps (s0/s1/s2) |
| --- | --- | :---: | :---: | :---: | --- | :---: | :---: | --- |
| `L90_KS3_07_08_ab` | B（=L10/00） | ✅ | ✅ | ✅ | 0,1,2 | ✅ | ✅ | 229/229/255 |
| `L90_LR2_37_cream_cheese_1_ab` | B（=L10/06） | ✅ | ✅ | ✅ | 0,1,2 | ✅ | ✅ | 250/247/254 |
| `L90_LR4_42_akita_black_bowl_2_ab` | D | ✅ | ✅ | ✅ | 0,1,2 | ✅ | ✅ | 249/277/236 |
| `L90_LR4_42_akita_black_bowl_2_ba` | D | ✅ | ✅ | ✅ | 0,1,2 | ✅ | ✅ | 244/355/271 |
| `L90_LR4_44_akita_black_bowl_2_ab` | D | ✅ | ✅ | ❌ | 0,1 | ✅ | ❌ | 244/312/600 |
| `L90_LR4_44_akita_black_bowl_2_ba` | D | ✅ | ❌ | ❌ | 0 | ❌ | ❌ | 247/600/600 |

**合并汇总：15/18 = 83.33%；3/3 共 4 条，≥2 共 5 条，仅 1 共 1 条，0 成功 0 条。**

**独立审计（verifier, task-22）**：**PASS（0 blocker / 0 major / 0 minor 遗留）**；从 raw results+traces 独立复算 12 eps 与 summary **0 差异**，seed0 引用未重复计入；preflight row1/row2 digest 与 eval.log 一致、init 行=seed%50、seeds 仅 [1,2] 全部核实。审计期间发现并修复 2 个分析口径问题（`resume_helper` trace 文件名 seed 过滤缺失导致 seed2 误读 seed1 trace；median 口径 STATUS vs summary 不一致），**success/稳定性数字不变**，子任务/s1 指标已刷新（0/3/9、s1 11/12、0 回撤）。

**结论**：
1. hard run 的成功不是 seed0 偶然：**整体跨 seed 15/18 = 83.3%**；其中 **4 条 3/3 稳定**，说明这些任务（2 条 B 指令变体 + LR4_42 的 2 个方向）对 pi05 是可重复成功的。
2. **真正新任务新增 2 个稳定任务**：`LR4_42_akita_black_bowl_2`（M2 提升，ab/ba 均 3/3，属 D 类）稳定；`LR4_44_akita_black_bowl_2` 为 2/3（ab 方向 ≥2，ba 仅 seed0），可作备选。
3. **B 类指令变体结论闭环**：剩余 3 条 B 中 2 条成功且均 3/3（L10/00、L10/06 的指令变体），1 条（`KS3_06_08_ab`，L90/05）失败 → "任务相同但指令不同需验证、取成功指令"的判断成立。
4. **rollback 稳定基数更新**：3/3 成功候选 easy 10 + hard 4 = **14 条**；其中真正新任务（C+D）**5 条 / 3 任务**（easy LR3：`85_86_ba`、`87_88_ab/ba`；hard LR4_42：`..._ab/ba`）；B 类指令变体 3/3 共 **5 条 / 5 任务**（easy 3 + hard 2）。备选：`LR4_44_..._ab`（≥2）。

**下一步建议**：① 对 5 条真正新任务 3/3 候选 + 5 条 B 指令变体补视频；② 选其中 2–3 条做 rollback 注入原型（s1 完成→回退→s2 自修复），优先 `LR4_42`（新任务稳定）与 easy 的 LR3 tray 任务；③ P1/P2/hard 层仍 0/41，先做 staged/instruction-switch 对照，不再扩量。

## 20. hard 全量 92 条 × seeds 1/2 补跑结果（2026-10-26/27）

> 运行目录 [`runs/libero-90-hard-seeds12-full-20261026/`](../runs/libero-90-hard-seeds12-full-20261026/README.md) · 结果 [`analysis/summary.md`](../runs/libero-90-hard-seeds12-full-20261026/analysis/summary.md) · 终检 [`analysis/final_checks.json`](../runs/libero-90-hard-seeds12-full-20261026/analysis/final_checks.json)（checks_all_passed=true）+ verifier 审计 `AUDIT.md`。

**运行**：hard run 全量 92 条 × seeds{1,2} = **184 episodes**（seed0 引用 hard run，不重跑）；双 worker，墙钟 **3.76h**（13542s），workers rc=0/0，GPU 23.5GB 无 OOM；assets 从 hard run 字节拷贝（92 bddl+92 init，sha 0 mismatch）；静态 92/92；preflight rows{1,2} 4 条 digest 均与 eval.log 一致且异于随机 reset。

| 指标 | 值 |
| --- | --- |
| 本次 seeds 1/2 | **9 / 184 = 4.89%**（seed1 5/92、seed2 4/92；mean/median steps 583.9/600；子任务 0/1/2 = 89/84/11） |
| **3-seed 合并（276 eps）** | **15 / 276 = 5.43%**（seed0 6 + seed1 5 + seed2 4） |
| 稳定性 | **≥1 次 6 条；≥2 seeds 5 条；3/3 4 条；仅 1 seed 1 条；从未成功 86 条** |
| **新增可用候选** | **0 条**（seed0 失败但 seeds1/2 成功：无）→ **seed0 单 seed 对"有成功候选"的召回 = 100%**，hard 集合再加 seed 无收益 |
| 失败模式 | 175/184 跑满 600 步；89 条 0 段停滞、84 条完成 1 段后停滞；2 条 near-miss（goal 原子曾全真但 check_success 未触发，值得复查评估口径） |

**独立审计（verifier, task-24）**：**PASS-WITH-ISSUES（0 blocker / 0 major / 1 minor）**；从 raw results+traces 独立复算 184 eps 与 3-seed 276 eps 表**0 差异**（success 9/184、15/276、3/3=4、≥2=5、仅1=1、none=86、新增可用=0、final_checks 19/19 全 PASS），资产 sha 与 preflight 4 条 digest 均一致。唯一 minor：queue 完成后 `summary.progress.queue_running`/`STATUS.md` 仍短暂显示 True（生成顺序问题，不影响结果），已回填为 false。

**3-seed 稳定名单**：
- **3/3（4 条）**：`L90_KS3_07_08_ab`（B，=L10/00 指令变体）、`L90_LR2_37_cream_cheese_1_ab`（B，=L10/06 指令变体）、`L90_LR4_42_akita_black_bowl_2_ab`、`L90_LR4_42_akita_black_bowl_2_ba`（**D 真正新任务**）
- **≥2（5 条）**：上述 4 条 + `L90_LR4_44_akita_black_bowl_2_ab`（D，2/3）
- **仅 1（1 条）**：`L90_LR4_44_akita_black_bowl_2_ba`；**0-success 86 条**

**3-seed 分布（276 eps 口径）**：axis **B 6/9 = 66.7%** · C **0/48** · D 9/219 = 4.11%；route M2 **12/99 = 12.12%** > M1 3/171 = 1.75%；priority P0 **15/153 = 9.80%**，P1+P2 **0/123**；scene LR4 **9/18 = 50%**、KS3 3/6 = 50%、LR2 3/57 = 5.26%，其余 0；template T1 **12/81 = 14.81%**、T7 3/6 = 50%；bucket same_destination **12/117 = 10.26%** > same_furniture 3/63 = 4.76% > independent **0/96**；class compatible 15/168 = 8.93%，**hard 0/108**。

**结论**：
1. **hard 集合已榨干**：seed0 6 条成功候选 = 3-seed 下全部 ≥1 成功候选；seeds1/2 没有发现任何 seed0 漏掉的可用候选 → 继续对 hard 加 seed 是无效算力。
2. **稳定性结论不变**：4 条 3/3（其中 2 条真正新任务 `LR4_42` 两方向、2 条 B 指令变体）+ 1 条 ≥2（`LR4_44_ab`）。
3. **P1/P2/hard（0/123）与 C 类跨场景同 goal（0/48）在 zero-shot 单指令下完全不可解**：这些层不是 seed 噪声问题，必须改协议（staged / instruction-switch / rollback 干预）。
4. **rollback 基数**（与 §19 一致，本轮无新增）：3/3 候选 14 条（easy 10 + hard 4）；真正新任务 3/3 共 5 条/3 任务（easy LR3 三条 + hard LR4_42 两条）；B 指令变体 5 条/5 任务；备选 `LR4_44_ab`（≥2）。

**下一步**：① 停止对 hard 集合加 seed；② 用 §19 的稳定集（5 条真正新任务 3/3 + 5 条 B 指令变体）补视频并进入 rollback 原型；③ 若仍想扩大候选池，应对 P1/P2/hard 层做 staged 对照，而不是继续全量加 seed。

## 21. 完整 LIBERO 5 套件 × pi05 官方评测（2026-10-27，参考基线）

> 运行目录 [`runs/libero-official-5suites-pi05-20261027/`](../runs/libero-official-5suites-pi05-20261027/README.md) · 结果 [`analysis/summary.md`](../runs/libero-official-5suites-pi05-20261027/analysis/summary.md) · 校验 [`analysis/final_checks.json`](../runs/libero-official-5suites-pi05-20261027/analysis/final_checks.json) · **带视频证据 HTML 报告 [`report/index.html`](../runs/libero-official-5suites-pi05-20261027/report/index.html)**。

**目的**：此前 pi05 只跑过 LIBERO 标准 4 套件（first-pass 40/40，原始数据已丢失），**LIBERO-90 从未用 pi05 全量评测**。本 run 补齐完整 5 套件（130 tasks），作为以后参考基线，并保留全部 episode 视频证据。

**协议**：pi05（`pi05_libero`，PyTorch 后端）；原版 LIBERO shadow（只读 symlink）+ runtime 副本（2 处最小 patch：放行 LIBERO_90 90 tasks 的基准守卫、生成 90 个 libero_90 task yaml）；**单 seed=0**（init state 0）、**max_steps=500**、**replan_steps=5**、**video on**（20 fps，256×256）、单进程串行；套件顺序 LIBERO_90 → SPATIAL → OBJECT → GOAL → 10。

| suite | tasks | success | rate | mean steps | wall（suite 实测） |
| --- | ---: | ---: | ---: | ---: | ---: |
| **LIBERO_90** | 90 | **29** | **32.22%** | 405.6 | 2.49h |
| LIBERO_SPATIAL | 10 | 10 | **100%** | 106.0 | 6.5 min |
| LIBERO_OBJECT | 10 | 10 | **100%** | 146.9 | 5.6 min |
| LIBERO_GOAL | 10 | 10 | **100%** | 125.5 | 6.8 min |
| LIBERO_10 | 10 | 10 | **100%** | 248.7 | 10.2 min |
| **合计** | **130** | **69** | **53.08%** | 329.1 | 2.98h（队列端到端 3.59h） |

**视频证据**：**130/130 episode mp4**（20 fps / 256×256 / 43.07 MB）全部 cv2 可解码；HTML 报告的视频库按**测试套 / 测试场景**筛选（32 个 suite×scene 分组，130 张首帧缩略图卡片），点击卡片在**单一弹层播放器**中播放（卡片内无内嵌播放器），全部 130 个视频可播放；`analysis/video_index.json`、`analysis/scene_map.json` 提供索引与场景映射。

**关键结论/局限**：
1. **LIBERO_90 首次 pi05 全量基线 = 29/90 = 32.22%**（单 seed/500 步/zero-shot）。61 个失败任务**全部跑满 500 步超时**，无 near-miss/提前失败分类；失败集中在 pick up（23，含 book 13）、put（34）、drawer/cabinet 等长程操作。
2. **其余 4 套件在本配置下饱和（各 100%）**：说明 shadow/runtime 管线正确，但该配置对标准 4 套件已无区分度；不能与官方论文 50-trials/JAX 数字严格横比。
3. 视频是后续定性复核/回归对照的直接证据（失败任务 500 步轨迹可回放）。
4. 参考用途：作为 pi05 在完整 LIBERO 130 tasks 上的**单 seed 参考基线**；未来改 staged/rollback/多 seed 时可与此对照（同协议下）。

## 22. 组合任务补跑 seeds 3/4（2026-10-28，5-seed 合并）

> 运行目录 [`runs/libero-90-combos-seeds345-20261027/`](../runs/libero-90-combos-seeds345-20261027/README.md) · 结果 [`analysis/summary.md`](../runs/libero-90-combos-seeds345-20261027/analysis/summary.md) · 校验 [`analysis/final_checks.json`](../runs/libero-90-combos-seeds345-20261027/analysis/final_checks.json) · verifier `AUDIT.md`。

**范围**：此前已跑 seeds0–2 的全部组合候选 **253 条**（easy 161 + hard 92，无重复并集）× **seeds{3,4}** = **506 episodes**（seed5 按用户指示暂缓）。协议与 seeds0–2 完全一致：pi05、max_steps=600、replan=10、video off、双 worker、check_success；init 行 = seed%50（3/4）；资产从 easy/hard run 字节拷贝（253 bddl+253 init，sha 0 mismatch），静态 253/253 PASS。

| 指标 | 值 |
| --- | --- |
| 本次 seeds 3/4 | **41 / 506 = 8.10%**（seed3 23/253 = 9.09%、seed4 18/253 = 7.11%；mean steps 574.7；子任务 0/1/2 = 226/235/45；9.83h / ~51.5 eps/h） |
| **合并 5-seed（1265 eps）** | **97 / 1265 = 7.67%**（3-seed 时 56/759 = 7.38%，+0.29pp） |
| 稳定性 | 至少一次 **32**；≥2 **22**（3-seed 17，+5）；≥3 **17**（3-seed 14，+3）；≥4 **14**；**5/5 12**；从未成功 221 |
| 新增可用候选 | **7 条**（seeds0–2 全失败、seeds3/4 至少一次成功） |

**5/5 全成功（12 条）**：`KS3_07_08_ab`、`LR1_32_33_ab/ba`、`LR2_37_cream_cheese_1_ab`、`LR2_38_39_ab/ba`、`LR3_87_88_ab/ba`、`LR4_42_akita_black_bowl_2_ba`、`LR5_45_46_ab/ba`、`LR6_49_52_ab`。

**新增可用 7 条（按去重 axis）**：D 新任务 4 条——`KS5_61_64_ba`（seed3）、`KS5_63_64_ba`（seed3）、`LR3_85_87_ab`（seed4）、`LR3_85_87_ba`（seed4）；C 跨场景同 goal 3 条——`LR2_37_39_ba`（seed3+4）、`LR2_39_cream_cheese_1_ab`（seed4）、`LR2_39_cream_cheese_1_ba`（seed3+4）。

**稳定性集按 axis 拆解**：

| 集合 | 总数 | A_skip（排除） | B 指令变体 | C 跨场景 | D 新任务 | **可用（B+C+D）** |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ≥2 | 22 | 4 | 6 | 2 | 10 | **18** |
| ≥3 | 17 | 4 | 6 | 0 | 7 | **13** |
| ≥4 | 14 | 4 | 5 | 0 | 5 | **10** |
| 5/5 | 12 | 4 | 5 | 0 | 3 | **8** |

→ 按用户"去重后可用于 rollback"的口径（A 类=场景/任务/指令全同，仅作对照/校准）：**rollback 稳定基数 = ≥3 的 13 条（B 6 + 新任务 7）**；高置信子集 ≥4 = 10 条、5/5 = 8 条（B 5 + 新任务 3：LR3_87_88_ab/ba、LR4_42_..._ba）。新增 7 条建议补视频/人工复核后再纳入。

**5-seed 分布（1265 eps 口径）**：axis **B 28/35 = 80%** > D 43/1010 = 4.26% > C 6/200 = 3%；场景 LR3 24%、LR4 23.3%、LR5 20%、LR1 16.7%、LR6 16%、LR2 10.8%、KS3 25%（5/20），其余多 0；template T1 15.16%（69/455）、T7 50%（5/10）、T3 5.29%、T6 2.5%，T2/T4/T4b/T8/T9 0；bucket same_destination 11.40% > same_furniture 4.29% ≈ independent 4.23%；route M2 13.33% > M1 6.88% > S1 0；priority 仅 P0 成功（9.15%），P1/P2 0；class compatible 8.94% vs hard 0/180。

**结论**：① 补 seeds3/4 使"至少一次成功"候选从 25→32、≥3 稳定从 14→17、新增 7 条 seeds0–2 漏掉的候选（主要 KITCHEN_SCENE5 与 LIVING_ROOM_SCENE2/3）；② 5-seed 稳定集（≥3，13 条可用）可作为 rollback 主基数，5/5 的 8 条为高置信子集；③ 新增候选目前只 1–2 seeds 成功（KS5 仅 seed3、LR2_39/ LR3_85_87 部分 seed4），需人工复核/补 seed5 确认；④ seed5 暂缓，若补则扩展为 6-seed 并复核稳定性排序。

## 23. 补 seed5 与合并 6-seed 结果（2026-10-28）

> 运行目录 [`runs/libero-90-combos-seed5-20261028/`](../runs/libero-90-combos-seed5-20261028/README.md) · 结果 [`analysis/summary.md`](../runs/libero-90-combos-seed5-20261028/analysis/summary.md) · 校验 [`analysis/final_checks.json`](../runs/libero-90-combos-seed5-20261028/analysis/final_checks.json) · verifier `AUDIT.md`。

**范围**：与前两批相同的 **253 组合候选**（easy 161 + hard 92）× **seed5 only** = **253 episodes**（seeds0–4 引用既有 easy/hard/seeds345 run，不重跑）。独立子 run；资产从 seeds345 run 字节拷贝（253+253，sha 0 mismatch）；静态 253/253 PASS；协议与 seeds0–4 一致（pi05/max600/replan10/video off/双 worker；init row5）。

| 指标 | 值 |
| --- | --- |
| 本次 seed5 | **24 / 253 = 9.49%**（easy 17/161 = 10.56%、hard 7/92 = 7.61%；mean steps 571.5；子任务 0/1/2 = 97/131/25；5.33h / 47.5 eps/h） |
| **合并 6-seed（1518 eps）** | **121 / 1518 = 7.97%**（5-seed 97/1265 = 7.67%，+0.30pp） |
| 稳定性 | 至少一次 **34**；≥2 **25**（+3）；≥3 **20**（+3）；≥4 **17**（+3）；≥5-of-6 **13**；**6/6 12**；从未成功 219 |
| 5→6 变化 | **5/5 的 12 条全部维持 6/6**（没有候选止步 5/5） |
| seed5 新增可用 | **2 条**（seeds0–4 全失败、seed5 成功）：`LR2_37_39_ab`（C 跨场景，seed5 steps 471）、`LR4_42_43_ba`（D 新任务，seed5 steps 347）——均仅 1/6，建议人工复核 |

**6/6 全成功（12 条）**：`KS3_07_08_ab`、`LR1_32_33_ab/ba`、`LR2_37_cream_cheese_1_ab`、`LR2_38_39_ab/ba`、`LR3_87_88_ab/ba`、`LR4_42_akita_black_bowl_2_ba`、`LR5_45_46_ab/ba`、`LR6_49_52_ab`。

**稳定性集按 axis 拆解（6-seed 口径）**：

| 集合 | 总数 | A_skip（排除） | B 指令变体 | C 跨场景 | D 新任务 | **可用（B+C+D）** |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ≥3 | 20 | 4 | 6 | 2 | 8 | **16** |
| ≥4 | 17 | 4 | 6 | 0 | 7 | **13** |
| ≥5-of-6 | 13 | 4 | 5 | 0 | 4 | **9** |
| 6/6 | 12 | 4 | 5 | 0 | 3 | **8** |

→ **rollback 可用基数（A 类排除，B/C/D 可用）：≥3 = 16 条；≥4 = 13 条；≥5-of-6 = 9 条；6/6 = 8 条**。高置信子集 6/6 的 8 条：B 5 条（`KS3_07_08_ab`、`LR1_32_33_ab`、`LR2_37_cream_cheese_1_ab`、`LR2_38_39_ba`、`LR5_45_46_ba`）+ 新任务 3 条（`LR3_87_88_ab/ba`、`LR4_42_..._ba`）。A 类 4 条（`LR1_32_33_ba`、`LR2_38_39_ab`、`LR5_45_46_ab`、`LR6_49_52_ab`）为完全重复指令，保留作对照/校准，不计入 rollback 基数。

**6-seed 分布要点（1518 eps）**：axis A_skip 24/24、**B 34/42 = 80.95%**、C 10/240 = 4.17%、D 53/1212 = 4.37%；场景 LR3 ~25%、LR4 ~25%、LR5 20%、LR1/LR6 16.67%、LR2 11.97%、KS3 25%（6/24），其余多为 0；template **T1 16.12%**（88/546）、T7 50%、T3 5.39%；bucket same_destination **12.12%** > independent/same_furniture 4.17%；route M2 14.14% > M1 7.11% > S1 0；仅 P0 有成功；class compatible 有成功、hard 0。

**结论**：① seed5 把 6-seed 总成功率推到 **7.97%**（+0.30pp），稳定性集继续单调增长（≥2/≥3/≥4 各 +3），6/6 12 条（5/5 全部维持）；② 可用 rollback 基数确定为 **≥3 16 条 / ≥4 13 条 / 6/6 8 条**（A 类 4 条排除）；③ seed5 只多发现 2 条弱候选（均 1/6），边际收益递减——**6-seed 已完成，不再继续加 seed**；④ 下一步用可用 6/6（8 条）与 ≥4（13 条）补视频并做 rollback 注入原型。

## 24. 可行候选（34 条）指令与逐 seed 完成详情（2026-10-28）

> 口径：**可行候选 = 6 seeds（0–5）中至少成功 1 次**。共 **34 条**（B 指令变体 6 / C 跨场景 5 / D 新任务 19 / A 重复对照 4）；按去重规则 A 类仅作对照，**usable = 30 条**。数据来自 seeds0–5 合并结果（[`runs/libero-90-combos-seed5-20261028/analysis/summary.md`](../runs/libero-90-combos-seed5-20261028/analysis/summary.md)）。**每列 steps 依次为 seed0/1/2/3/4/5；600 = 跑满 600 步上限（失败），其他数字 = 该 seed 成功时步数。**

| candidate_id | 场景 | 模板 | axis | 任务指令 | 成功 seeds | steps (s0/s1/s2/s3/s4/s5) |
| --- | --- | --- | --- | --- | --- | --- |
| `L90_KS3_07_08_ab` | KITCHEN_SCENE3 | T7 | B 指令变体 | put the moka pot on the stove and turn it on | 0,1,2,3,4,5 | 229 / 229 / 255 / 240 / 240 / 258 |
| `L90_LR1_32_33_ab` | LIVING_ROOM_SCENE1 | T1 | B 指令变体 | put both the cream cheese box and the alphabet soup in the basket | 0,1,2,3,4,5 | 234 / 225 / 245 / 240 / 253 / 245 |
| `L90_LR1_32_33_ba` | LIVING_ROOM_SCENE1 | T1 | A 重复(对照) | put both the alphabet soup and the cream cheese box in the basket | 0,1,2,3,4,5 | 264 / 268 / 240 / 268 / 262 / 250 |
| `L90_LR2_37_cream_cheese_1_ab` | LIVING_ROOM_SCENE2 | T1 | B 指令变体 | put both the butter and the cream cheese box in the basket | 0,1,2,3,4,5 | 250 / 247 / 254 / 257 / 240 / 271 |
| `L90_LR2_38_39_ab` | LIVING_ROOM_SCENE2 | T1 | A 重复(对照) | put both the alphabet soup and the tomato sauce in the basket | 0,1,2,3,4,5 | 261 / 232 / 250 / 390 / 259 / 270 |
| `L90_LR2_38_39_ba` | LIVING_ROOM_SCENE2 | T1 | B 指令变体 | put both the tomato sauce and the alphabet soup in the basket | 0,1,2,3,4,5 | 239 / 250 / 250 / 263 / 251 / 248 |
| `L90_LR3_87_88_ab` | LIVING_ROOM_SCENE3 | T1 | D 新任务 | put both the butter and the cream cheese in the tray | 0,1,2,3,4,5 | 264 / 266 / 294 / 275 / 253 / 263 |
| `L90_LR3_87_88_ba` | LIVING_ROOM_SCENE3 | T1 | D 新任务 | put both the cream cheese and the butter in the tray | 0,1,2,3,4,5 | 294 / 261 / 254 / 262 / 268 / 296 |
| `L90_LR4_42_akita_black_bowl_2_ba` | LIVING_ROOM_SCENE4 | T1 | D 新任务 | put both the black bowl on the right and the black bowl on the left in the tray | 0,1,2,3,4,5 | 244 / 355 / 271 / 235 / 366 / 273 |
| `L90_LR5_45_46_ab` | LIVING_ROOM_SCENE5 | T3 | A 重复(对照) | put the white mug on the left plate and put the yellow and white mug on the right plate | 0,1,2,3,4,5 | 223 / 220 / 217 / 234 / 228 / 230 |
| `L90_LR5_45_46_ba` | LIVING_ROOM_SCENE5 | T3 | B 指令变体 | put the yellow and white mug on the right plate and put the white mug on the left plate | 0,1,2,3,4,5 | 221 / 225 / 213 / 233 / 235 / 218 |
| `L90_LR6_49_52_ab` | LIVING_ROOM_SCENE6 | T3 | A 重复(对照) | put the white mug on the plate and put the chocolate pudding to the right of the plate | 0,1,2,3,4,5 | 262 / 217 / 378 / 205 / 256 / 218 |
| `L90_LR4_42_akita_black_bowl_2_ab` | LIVING_ROOM_SCENE4 | T1 | D 新任务 | put both the black bowl on the left and the black bowl on the right in the tray | 0,1,2,3,5 | 249 / 277 / 236 / 228 / 600 / 233 |
| `L90_LR3_85_86_ba` | LIVING_ROOM_SCENE3 | T1 | D 新任务 | put both the tomato sauce and the alphabet soup in the tray | 0,1,2,3 | 277 / 451 / 350 / 489 / 600 / 600 |
| `L90_LR3_86_88_ab` | LIVING_ROOM_SCENE3 | T1 | D 新任务 | put both the tomato sauce and the cream cheese in the tray | 0,2,3,5 | 366 / 600 / 493 / 275 / 600 / 555 |
| `L90_LR4_44_akita_black_bowl_2_ab` | LIVING_ROOM_SCENE4 | T1 | D 新任务 | put both the chocolate pudding and the black bowl on the right in the tray | 0,1,3,5 | 244 / 312 / 600 / 297 / 600 / 246 |
| `L90_LR6_49_52_ba` | LIVING_ROOM_SCENE6 | T3 | B 指令变体 | put the chocolate pudding to the right of the plate and put the white mug on the plate | 1,2,3,5 | 600 / 209 / 203 / 209 / 600 / 216 |
| `L90_LR2_37_39_ba` | LIVING_ROOM_SCENE2 | T1 | C 跨场景 | put both the tomato sauce and the butter in the basket | 3,4,5 | 600 / 600 / 600 / 355 / 340 / 497 |
| `L90_LR2_39_cream_cheese_1_ba` | LIVING_ROOM_SCENE2 | T1 | C 跨场景 | put both the cream cheese box and the tomato sauce in the basket | 3,4,5 | 600 / 600 / 600 / 509 / 346 / 258 |
| `L90_LR3_85_86_ab` | LIVING_ROOM_SCENE3 | T1 | D 新任务 | put both the alphabet soup and the tomato sauce in the tray | 2,3,5 | 600 / 600 / 291 / 270 / 600 / 382 |
| `L90_LR2_39_cream_cheese_1_ab` | LIVING_ROOM_SCENE2 | T1 | C 跨场景 | put both the tomato sauce and the cream cheese box in the basket | 4,5 | 600 / 600 / 600 / 600 / 247 / 244 |
| `L90_LR3_85_87_ab` | LIVING_ROOM_SCENE3 | T1 | D 新任务 | put both the alphabet soup and the butter in the tray | 4,5 | 600 / 600 / 600 / 600 / 270 / 265 |
| `L90_LR3_86_87_ab` | LIVING_ROOM_SCENE3 | T1 | D 新任务 | put both the tomato sauce and the butter in the tray | 2,5 | 600 / 600 / 431 / 600 / 600 / 425 |
| `L90_LR3_86_88_ba` | LIVING_ROOM_SCENE3 | T1 | D 新任务 | put both the cream cheese and the tomato sauce in the tray | 0,4 | 269 / 600 / 600 / 600 / 276 / 600 |
| `L90_LR4_44_akita_black_bowl_2_ba` | LIVING_ROOM_SCENE4 | T1 | D 新任务 | put both the black bowl on the right and the chocolate pudding in the tray | 0,3 | 247 / 600 / 600 / 258 / 600 / 600 |
| `L90_KS2_53_57_ab` | KITCHEN_SCENE2 | T6 | D 新任务 | put the black bowl at the back on the plate and open the top drawer of the cabinet | 1 | 600 / 549 / 600 / 600 / 600 / 600 |
| `L90_KS2_53_57_ba` | KITCHEN_SCENE2 | T6 | D 新任务 | open the top drawer of the cabinet and put the black bowl at the back on the plate | 1 | 600 / 295 / 600 / 600 / 600 / 600 |
| `L90_KS2_55_57_ba` | KITCHEN_SCENE2 | T6 | D 新任务 | open the top drawer of the cabinet and put the middle black bowl on the plate | 2 | 600 / 600 / 298 / 600 / 600 / 600 |
| `L90_KS5_61_64_ba` | KITCHEN_SCENE5 | T10 | D 新任务 | close the top drawer of the cabinet and put the black bowl on the plate | 3 | 600 / 600 / 600 / 444 / 600 / 600 |
| `L90_KS5_63_64_ba` | KITCHEN_SCENE5 | T10 | D 新任务 | close the top drawer of the cabinet and put the black bowl on top of the cabinet | 3 | 600 / 600 / 600 / 442 / 600 / 600 |
| `L90_LR2_37_38_ba` | LIVING_ROOM_SCENE2 | T1 | C 跨场景 | put both the alphabet soup and the butter in the basket | 2 | 600 / 600 / 402 / 600 / 600 / 600 |
| `L90_LR2_37_39_ab` | LIVING_ROOM_SCENE2 | T1 | C 跨场景 | put both the butter and the tomato sauce in the basket | 5 | 600 / 600 / 600 / 600 / 600 / 471 |
| `L90_LR3_85_87_ba` | LIVING_ROOM_SCENE3 | T1 | D 新任务 | put both the butter and the alphabet soup in the tray | 4 | 600 / 600 / 600 / 600 / 313 / 600 |
| `L90_LR4_42_43_ba` | LIVING_ROOM_SCENE4 | T1 | D 新任务 | put both the salad dressing and the black bowl on the left in the tray | 5 | 600 / 600 / 600 / 600 / 600 / 347 |

**统计**：34 条 = B 6 + C 5 + D 19 + A 4；**6/6 = 12 条**、≥5-of-6 = 13、≥4 = 17、≥3 = 20（含 A）；剔除 A 后 usable 口径：**6/6 = 8、≥5 = 9、≥4 = 13、≥3 = 16**。rollback 主基数建议 ≥3 的 16 条（B 6 + C 2 + D 8），高置信子集 6/6 的 8 条（B 5 + D 3：`LR3_87_88_ab/ba`、`LR4_42_akita_black_bowl_2_ba`）。A 类 4 条（`LR1_32_33_ba`、`LR2_38_39_ab`、`LR5_45_46_ab`、`LR6_49_52_ab`）为与 LIBERO-10 官方指令完全相同的重复任务，仅作对照/校准。

**视频实验（进行中）**：对上述 34 条可行候选补 **6 seeds × video × max_steps=600 = 204 episodes**，用于生成带视频证据的 HTML 报告（内容：每候选指令/场景/种子成功率/成功 steps/失败模式/rollback 可用性 + 可筛选视频库）。

## 附录 A：与参考方法的差异一页表

| 项 | LIBERO-GOAL | LIBERO-OBJECT | 本方法（LIBERO-90） |
| --- | --- | --- | --- |
| 组合来源 | 同场景两任务 goal 原子 | 同任务场景内提升干扰物 | 同场景两任务 goal 原子（M1）+ 少量纯干扰物提升（M2） |
| 改动段 | goal/obj_of_interest/language | 同左 | 同左 |
| init | 复用任务 i | 复用源任务 | 复用（两条都合法，需选定 init 源） |
| 每任务原子数 | 恒 1 | 恒 1 | 1 或 2（4 条约 2 原子任务在池内） |
| 候选规模（unordered / ordered） | 45 / 90 | 50 / 100 | **147 / 294；另 M2 +17/34、S1 +1/2** |
| 分类（compatible/hard/conflict/degenerate，pair 级） | 33/5/7/— | 50/0/0/0 | **92/19/29/3** |
| 动态预期 | 4.3% 单指令、staged 有效 | 4.0% 单指令 | 未测；按 staged 设计 |