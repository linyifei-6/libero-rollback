# 实验 HTML 报告标准提示词

> **用途**：本仓库（`libero-rollback`，LIBERO-10 rollback 评测）每完成一次实验，需要为实验产物生成一份 HTML 报告。本文件给出可直接复用的标准提示词，保证不同实验的报告在**章节结构、指标口径、图表和视频证据版式**上保持一致。
>
> **使用方式**：
> 1. 复制下面「标准提示词」整节（从「你是一名……」到「交付前自检」结束），替换 `{{...}}` 占位符（见附录 A）；
> 2. 建议连同**附录 B（数据契约与已知坑）**一起提供给执行者；附录 A 的示例只用于核对口径，不能硬编码进报告；
> 3. 交付后按附录 C 验收。
>
> **版本**：v1.2（2026-10-23）。本版新增：**网页必须使用浅色背景（light theme），禁止深色背景**；正文深色文字，卡片/表头/图表使用白/浅灰底并保持对比度。v1.1 曾新增：1.3 对四个扰动维度逐值解释含义并给出真实示例；新增 2.7「扰动未生效用例拆解」小节。口径、版式或仓库结构变化时更新本文件并提升版本号。
>
> **快速开始**：一般只需填写 `{{EXPERIMENT_NAME}}`、`{{RUN_DIRS}}`、`{{REPORT_DIR}}`、`{{NOTES}}` 四项，其余保持默认；报告目录建议放在对应 run 目录下（如 `runs/<实验名>/report`）。
> **对执行者下指令的示例**：「请按 `docs/html-report-prompt.md` 的标准提示词，为这次实验生成 HTML 报告。参数：实验名 = …；运行目录 = …；输出目录 = …。」

---

# 标准提示词：LIBERO-10 rollback 实验 HTML 报告

你是一名负责 LIBERO-10 rollback 评测的实验报告工程师。请在本仓库中为下面这次实验生成一份**可离线打开的中文 HTML 报告**，并在交付前逐项自检。你对 `runs/`、`dataset/` 中的原始数据只有读权限：可以读取、转码并把视频副本写入报告目录，但不得修改、删除或移动原始文件。

报告有两类读者：需要 5 分钟内看懂结论的负责人，以及需要逐条核对视频证据的研究者。所有数字必须能从运行产物复现；不得推测或编造实验背景、配置与结果。

## 0. 本次实验参数

| 参数 | 值 |
| --- | --- |
| 实验名称 | `{{EXPERIMENT_NAME}}` |
| 运行目录（一个或多个，相对仓库根） | `{{RUN_DIRS}}` |
| 报告输出目录 | `{{REPORT_DIR}}`（默认 `runs/<实验名>/report`） |
| 报告标题 | `{{TITLE}}`（默认由实验名生成） |
| 本次实验关注点 / 备注 | `{{NOTES}}` |
| 是否单文件 HTML | `{{SINGLE_FILE}}`（默认 `false`：报告目录 + `videos/` 外链；`true` 才内嵌 base64 视频） |

如果运行目录不存在、关键文件缺失或参数互相冲突：先列出缺失项并询问，不要猜测路径、口径或实验背景。

## 1. 数据核对（先于写作；核对结果写进报告「数据质量与口径核对」小节）

1.1 **识别输入布局**。先探测再读取；本仓库至少存在两种运行产物布局：

```
# 布局 A：批次（当前主力）。下面的「批次根」可以就是 <run>，也可以是 <run> 的子目录
批次根/
  batch-summary.json            # 可选：runner 中断时可能缺失
  driver.log
  taskNN/                       # 任务目录
    binding.yaml
    batch.log
    run/<model>_<timestamp>/
      results.json              # 1 条 baseline + N 条 perturbation
      videos/*.mp4
      eval.log / evaluation_summary.json / episode_details.jsonl

# 布局 B：逐用例（历史）
<run>/<case-dir>/{binding.yaml, completion.json, execution-plan.json, runner.log}
<run>/<case-dir>/<timestamp>/{results.json, videos/*.mp4}
```

`<run>` 可能是容器（如 `runs/retest-20261018` 下挂 `task00`…`task09` 十个批次根，results.json 在容器根下第 4 层）、单批次根或逐用例根，需递归发现：**不要设固定深度上限**；按 `results.json` 路径去重；跳过报告目录（含 `index.html`/`evidence.json`）、`runtime/`、`validation-*` 等无结果目录。不要只凭 `batch-summary.json` 是否存在判断布局：runner 中断的批次可能缺该文件，但 `results.json` 与视频仍在。报告要写明**实际探测到的布局、每个运行目录覆盖的任务、跳过的目录及原因**。

1.2 **建立案例级明细表**。每条记录 = 一个用例的一个 seed episode（多 seed 实验按 episode 统计并标注 seeds），至少包含：`task`、`instruction`、`case_id`、`run`、`seed`、`time_point`（报告中显示为 window）、`mechanism`、`severity`、`semantics`、`verdict`、`baseline_success`、`baseline_steps`、`injection_valid`、`injection_step`、`trigger_reached`、`perturbation_success`、`perturbation_steps`、`recovered`、`recovery_latency`、`baseline_clip`、`perturbation_clip`、`errors`。把该表落盘为报告目录内的 `evidence.json`，供复核；报告中图表、表格、视频卡的数字都必须能由它复现。

1.3 **用例元数据 join**。用例定义在 `dataset/current/manifest.yaml` 及其指向的 case YAML 中。匹配规则：
- 用 `case_id` 精确匹配；结果标签带 `_s<seed>` 后缀，先在标签侧剥离；
- **归一化必须两侧同时进行**：对 catalog `case_id` 与结果侧 `case_id` 都做 `_ ↔ -` 归一化后再匹配（例如 `all_done` 在 catalog 中带下划线、在结果侧被写成 `all-done`；只替换单侧会让全部 all_done 用例 join 失败）；
- 结果标签 → `case_name` 的可靠推导：去掉 `<task_profile>_` 前缀、去掉结尾 `_s<seed>`、去掉 `<binding severities[0]>` 片段；`case_name` 与 catalog `case_id` 的关系为 `case_name = "dataset_" + case_id.replace("-", "_")`；另外可用报告记录中的 `report.case_id` / `report.pert_id` 做兜底；
- 匹配失败**不得丢弃**：保留在明细与视频区，维度标为「未映射」，并统计条数。旧命名运行（2026-10-17 及更早）可能整批使用改名前的 case 名，与当前 catalog 匹配率为 0；此时必须显式标注「旧命名 run，元数据未映射」，不要把旧用例静默当作新用例，也不要把 `docs/case-renaming-proposal.md` 当作权威 crosswalk。

1.4 **统一指标口径**（每个数字都要写明分子、分母和排除项；不同维度不得混用分母）。本提示词固定以下口径：

| 指标 | 定义 | 备注 |
| --- | --- | --- |
| 配对基线成功率 | 基线成功的 episode 条目数 / 用例条目数 | 每个用例共享其任务级配对基线 |
| 注入有效率 | 注入有效条目数 / 用例条目数 | 注入无效必须拆成「注入被拒」（`injection_invalid`）与「触发未到达」（`trigger_not_reached`）分别计数 |
| **成功率（报告主指标）** | 扰动 episode `success=True` 的条目数 / **（基线成功且注入有效）条目数** | 基线失败或注入无效的条目不进分母，也不计为模型失败；本实验基线全部成功时，该分母等于注入有效条目数 |
| **自修恢复率** | 判定为 `valid_recovered` 的条目数 / **（基线成功且注入有效）条目数** | 与成功率同分母；分子只算模型自修恢复 |
| 协议不完整 | `protocol_incomplete` 条目数 / 用例条目数 | **计入成功率分母、单列统计、不计恢复分子**；堆叠图中单独成段 |
| 对照 / 关系保持探针 | `valid_control` / `valid_relation_preserving_probe` 条目数 | 计入成功率分母但不计恢复分子；必须单独声明并给敏感性成功率 |

补充规则：
- **判定以仓库分类器为准**（`src/libero_rollback/evidence.py::classify_result`），不要自行重判；`valid_recovered` 必须同时满足注入有效、`repair_completed`、`outcome.recovered` 等条件；
- **外部复原、协议不完整、真值未验证不得计入模型恢复**；
- **成功率与自修恢复率是两个指标**（现有脚本中曾出现「总体用分类器、分组用 episode success」两套统计，新报告必须显式写出各自定义，不能混用）；本提示词让两者使用同一分母（基线成功 ∧ 注入有效），但分子不同；
- 对照（`valid_control`）与关系保持探针（`valid_relation_preserving_probe`）在现有实现中进入成功率分母、但不进恢复分子：报告必须声明其条数，并**额外给出一版排除对照/探针后的成功率**作为敏感性分析（放在 2.1 指标卡与 2.5 分析中）；
- 批次返回码语义：`0` = 全部成功结束；`2` = 部分用例扰动后未完成任务（是评测结果，不是执行错误）；`3` = 配对基线失败、扰动未启动（该批次不能用于成功率/恢复率分母）。报告中要写明各批次返回码；
- **多 seed 时所有比率以 episode 条目计**（同一 case 的每个 seed 是一条记录），并注明 seeds 列表；视频卡要标注 seed，不能把不同 seed 的条目混为一谈。

1.5 **视频核对**。按下列规则定位视频并统计缺失：
- 基线：`{TASKKEY}__baseline_seed<n>.mp4`（`TASKKEY` = `results.json` 的任务 key，如 `LIBERO_10_T33`）；
- 扰动：`{TASKKEY}__{结果标签，末尾 _s<n> 替换为 _seed<n>}.mp4`；
- 必须 **seed-aware**；回退顺序：①精确构造名 → ②glob 且唯一 → ③去 seed 后缀的子串且唯一 → ④该 run 内唯一非 baseline 视频 → ⑤否则置空并标「视频缺失/歧义」。多 run 目录时读取全部 `results.json`，不能只取第一个；同一 (task, label) 重复时按修改时间取新并注明来源。
- 每个任务的配对基线通常只有 1 条；多 run/多 seed 时报告只展示 1 条代表性基线，选择规则：优先 `seed=0` → 其次该任务最新 run（按 mtime）→ 再其次取基线成功者；任务头列出全部候选基线（run / seed / 成功 / 步数）链接。扰动视频按 seed 分组/切换。缺失视频必须逐条列出，不能静默跳过。

1.6 **维度枚举与固定顺序**（写进图注；不得按数量排序）：
- `window`：`early` → `mid` → `later` → `all_done` →「未识别」；
- `task`：`T00` → `T09`（或本次实验实际覆盖的任务，按序）。注意 runtime `task_key`/`task_idx` 是**来源定位符**（如 `LIBERO_10_T33`、33），不等于 catalog 的 `task_index`（如 1）；任务映射必须走 catalog `task.task_index` 或批次目录 `taskNN`，不要解析 `task_key` 里的数字；
- `severity`：**只用 catalog `severity`**（当前 catalog 出现 14 种，固定顺序 `d0, pose, n3, n5, n8, p3, p5, p8, p10, r05, above, boundary, reference, articulation`；schema 共 18 种，另有 `d1/d2/d3/checkpoint`）。未来出现未列值时以原码显示并标注「未映射档位」，不得丢弃。binding 中的 `severities` 是 40 种 runtime grid 标签（如 `l2_grid_pose_early`），与 catalog 档位是两套空间，只能作为「运行标签」原样展示，**不得当作档位维度画图**；
- `mechanism`：catalog `rollback_target.state_change.kind`；当前数据有 10 种，schema 共 11 种。标签表必须覆盖实际出现的全部种类（现有脚本缺 `move_to_relation_target` 等中文标签），缺失时显示原文并标注「未映射标签」；
- `semantics`：当前 catalog 出现 3 种，固定顺序 `relation_then_resume` → `relation_holds_control` → `relation_only`；schema 共 5 种（另有 `protected_partial`、`unsupported_boundary`），出现未列值时原码显示并标注；
- `verdict`：固定顺序 `valid_recovered → valid_control → valid_relation_preserving_probe → valid_not_recovered → protocol_incomplete → truth_unverified → trigger_not_reached → injection_invalid → valid_external_restoration → incomplete`，中文标签见附录 B；不得出现「未判定」兜底文案。

1.7 **实验元数据核查**。报告中必须逐项列出下列信息（取不到的写「未记录」，禁止用默认值或其他运行推断）：
- 模型名 + checkpoint、replan 步数（`results.json` 的 `protocol`，`eval.log`/README 可交叉验证）；
- runtime overlay 路径/版本（`driver.log` 的 `runtime=`；一次实验可能混用不同 overlay，要逐任务写明）；
- seeds（全局与按任务覆盖，`driver.log` 与 `batch-summary.json.tasks.NN.seeds`）；
- 步数上限 `max_steps`（`eval.log`；逐条位于 `report.outcome.termination.max_steps`）；
- `--post-success-window` 是否开启、以及哪些任务开启（`eval.log` 的 RUN_PROTOCOL / `protocol.post_success_window`）；`all_done` 用例依赖该开关，未开启时触发未到达要写明原因；
- 选择条件与实际运行条数、相对 catalog 的未覆盖差集（例如 catalog 522 条、实际运行 518 条，要写明缺哪几条/哪个机制）；
- catalog 版本与 `case_count`（以 `dataset/current/manifest.yaml` 为准；README/文档中的旧条数口径不作为依据，冲突时注明）；
- 实验日期（优先取 run 目录名 / `eval.log` 时间戳 / `batch-summary.json` mtime；都取不到写「未记录」）；
- 输出目录、各批次返回码。

## 2. 报告结构（按顺序包含；标题可微调，内容不可缺）

### 页头
- 标题、实验名称、一行元信息（模型 · suite · 任务数 · 用例数 · 步数上限 · seeds · 实验日期 · 运行目录）；
- 生成时间、生成脚本路径与命令、模板版本（`html-report-prompt v1.2`）；
- 固定的章节目录导航：实验介绍 / 结果总览 / 视频证据 / 方法与复现 / 逐条结果；
- **页面视觉（硬性）**：必须使用**浅色背景（light theme）**，禁止深色背景；正文深色文字，卡片/表头/图表使用白/浅灰底，固定左侧导航同样使用浅色，保证任何环境下都可读。

### 一、实验介绍
1.1 **实验背景**（2–4 段，事实必须来自仓库文档与运行产物）：
- LIBERO-10 是十个长程操作任务（每个任务由两个子目标/关系构成），任务名、顺序、instruction 以 LIBERO-plus `tasks_info.txt` 与对应 BDDL 的 `:language` 原文为准；
- 本仓库是 LIBERO-10 的模型无关 rollback 评测数据集：记录「已确认完成的关系被外部干预撤销」的场景、状态变化、有效性条件与预期评测语义；不实现恢复算法、控制器、仿真器或模型本身；
- 本次实验的评测协议：每条用例跑「配对基线 + 扰动 episode」，两者共享同一初始状态与随机种子，差异只来自注入；注入是否真实改变状态由注入有效性判定；
- 必须区分四层证据：用例定义 → 静态校验 → 原生端点预检（baseline-only）→ live 模型恢复；预检通过不等于模型恢复；
- 必须写清本次实验关注点（来自 `{{NOTES}}`；未提供时按数据如实描述）；
- 解读提醒：LIBERO-10 的 BDDL 目标是纯合取，「是否恢复被撤销的前序关系」与「任务最终是否成功」并不绑定；解释成功率时必须说明这一点。
1.2 **被测任务与覆盖范围**：任务表（`task_index`、`task_id`、instruction（BDDL 原文小写；可附展示用 title-case）、`source_bddl`、主要对象/子目标关系、用例数、各窗口用例数、基线成功数/率、扰动成功率 `k/N`）。表后说明本次覆盖的任务子集、未覆盖任务、catalog 中未运行的用例差集。
1.3 **扰动设置与评测口径**：
- **维度取值含义表（必须，共四张）**：对 `window`、`mechanism`、`severity`、`semantics` 四个维度**逐值**解释含义，并给出「本次用例数 + 一条本次实验真实 case 示例（链接到视频卡）」，禁止只列代码/数量或使用虚构/旧实验示例：
  * **window**：每个窗口给含义 + 触发事件示例（如 `enter_first_subgoal_completed`、`enter_next_subgoal_approach`、`enter_next_subgoal_lift` 等）+ 本次用例数 + 示例；
  * **mechanism**：解释撤销方式（恢复到回合初始位姿、施加初始偏移、从已完成位姿位移、移动参照物、整对平移、回退关节目标、移动到关系目标等），并给本次用例数与示例；
  * **severity**：解释历史标签 `d0–d3/checkpoint`（距离/检查点位姿）、`n*/p*/r05`（带符号水平偏移）、`above/pose/reference/boundary/articulation`（机制族）的含义；明确说明它是机制/幅度代号，**不是窗口、也不代表模型难度**；给本次用例数与示例；
  * **semantics**：解释 `relation_then_resume`（关系失效后应恢复）、`relation_holds_control`（关系保持对照）、`relation_only`（仅关系探针）等评测契约；schema 中其他枚举值若出现也一并解释；
  * 示例选择规则：同一取值下优先选注入有效、排序稳定的用例；示例链接必须能跳到 3.x 视频区的对应卡片。
- 维度规模可以直接体现在上述表格的「本次用例数」列中，不需要再单独列一张只有数量的表；
- 用例族（family）说明：同一 family 的用例只差注入窗口（`case_id` 去掉独立的 `early`/`mid`/`later`/`all_done` 片段后相同，all_done 也折叠用于识别同一 family），是跨窗口对照的基本单位；报告给出三窗口齐全的 family 数、缺窗口 family 数与单窗口 family 数；**版式固定三槽（early/mid/later），不要求用例条数等量**——三窗口条数通常不等量，某窗口无对应用例时按第 3.3 节用空位说明卡。
1.4 **评测对象与配置**：按 1.7 的信息逐项列出并注明来源文件；缺失项写「未记录」。
1.5 **阅读指引**：颜色/徽标含义、筛选器用法、基线卡与扰动卡的区别、空位卡含义。

### 二、实验结果总览
2.1 **关键指标卡**：用例总数、配对基线成功率、注入有效率（并拆出注入被拒 / 触发未到达）、整体成功率（`k/N` + %）、自修恢复率、协议不完整、基线失败、任务数；另加一张「敏感性成功率」卡：排除对照（`valid_control`）与关系保持探针（`valid_relation_preserving_probe`）后的成功率（`k/N` + %）。每张卡附口径提示。
2.2 **整体成功率图表**：醒目的整体成功率（如 100% 进度条或环形图 + 大号百分比 + `k/N`）+ 对比条形图（配对基线成功率 / 注入有效率 / 整体成功率 / 自修恢复率，横轴 0–100%）；图下注明「成功率分母 = 基线成功且注入有效条目；本实验基线全部成功时等于注入有效条目数」。
2.3 **按维度成功率柱状图**（**纵轴必须是成功率 0–100%**）：
- 第一优先：**按 window 的成功率柱状图**，x 轴固定 `early`→`mid`→`later`→`all_done`（→未识别）；
- 其后：按 task、mechanism、severity、semantics 的同类柱状图（数据存在才画；本次未记录则写「未记录」）；
- 每根柱标注 `k/N`（可加百分比），其中 **N = 该组成功率分母（基线成功且注入有效的条目数）**；柱下/图角标注 **n = 该组用例条目数**（含注入无效）。若 `n ≠ N`，同时标注 `n` 与无效条数/原因；`n < 5` 的柱加视觉提示（如虚线边框 + ⚠）；
- 空分组区分两种状态并都给灰色/斜纹空柱：`n = 0` 标「本组无用例」；`n > 0` 但 `N = 0` 标「有用例但无有效条目」并注明原因（注入被拒/触发未到达/基线失败）；
- 图注写明排序规则、分母口径与 n/N 定义。
- 建议补充「注入有效性构成」堆叠条形图，分段为：有效且成功 / 有效未成功（并细分未恢复、对照、探针、协议不完整）/ 注入被拒 / 触发未到达；**协议不完整必须单独成段**，不能并入「有效未成功」后当作模型未恢复。
2.4 **其他维度成功率柱状图**：task / mechanism / severity / semantics 的成功率柱状图（纵轴同为 0–100%），每根柱标 `k/N` 与 `n`；本次实验只覆盖单个任务时注明「按任务维度图省略」。**多任务/全量报告必须包含按任务成功率柱状图**，筛选栏提供任务筛选，指标卡展示任务数。
2.5 **维度明细表**：维度、分组、用例条目数、注入有效（成功率分母）、成功数、成功率、自修恢复数、备注；与图表数字一致。
2.6 **简要实验分析**：4–6 条 bullet，每条引用具体数字，至少覆盖：
- 整体成功率与基线成功率的差距、注入有效性/被拒与基线失败对结论的影响；
- window 间差异：最高/最低窗口、差值、是否呈窗口趋势（没有趋势直说）；**三窗口用例数通常不等量，必须同时给每组 n 与 N**；
- 任务间差异：最高/最低任务；
- mechanism/severity 层面的主要失败来源；
- 协议不完整/对照/探针在成功率分母中的占比，以及排除对照/探针后的敏感性成功率；
- 数据限制：样本量、单 seed、未映射/视频缺失、覆盖缺口；
- 对「扰动未生效」的条目只给数量与指向 2.7 的链接，避免把运行配置/几何问题混进模型能力结论。
不要写无数字的泛泛结论，不要把相关性表述为因果。

2.7 **扰动未生效用例拆解（注入无效）**：必须单独成小节（建议标题「2.7 扰动未生效用例拆解（注入无效）」），只统计 `injection_valid is not True` 的用例（触发未到达、触发到达但注入未执行、注入激活失败等），要求：
- **定义与影响**：明确这些条目不计入成功率/恢复率分母，也不计为模型失败；与「注入有效但模型未恢复」严格区分；
- **原因分类汇总**：列出原因类别（至少区分：触发未到达；触发到达但注入未执行，含 all_done 未开 `--post-success-window`；注入激活失败：保护体碰撞；注入激活失败：无合法关系边界对；其他几何/关系约束；其他错误；未记录原因）、判定依据或错误码、条数、涉及窗口、涉及机制、一个真实示例；并给出「原因分布」图（横轴为条数，不是成功率）；
- **按窗口 / 机制拆解**：每个窗口的用例数、未生效数、注入有效数、类别分布；每个机制的同上；
- **逐条原因明细**：case_id、窗口、机制、档位、结论、`trigger.reached`、`rule_executed`、错误码、错误明细、跳转视频卡的链接；
- **影响与处理建议**：逐类说明是运行配置（如 all_done 未开 post-success-window）、用例几何/搜索策略（如 `NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR`）、保护体碰撞还是触发问题，并给出重跑建议（开启 post-success-window、调整平移/边界搜索后重跑等）；禁止把这些条目计为模型失败；
- 若本次实验没有未生效用例，显示「全部注入生效」空态，不要省略小节。

### 三、视频证据（可按扰动维度筛选）
3.1 **筛选栏**（固定在视频区顶部）：
- `window` 筛选（主维度，可多选，默认全选；选项全集必须含 `early`、`mid`、`later`、`all_done`、「未识别」）；
- `task`、`mechanism`、`severity`、`semantics`、`verdict` 筛选，`case_id` 关键字搜索；多 seed 实验需提供 `seed` 筛选或切换；
- 「重置」按钮；实时显示「显示 x / y 条扰动条目，z 个任务」（x = 当前可见扰动条目，不含 baseline 与占位卡；y = 全实验扰动条目总数；z = 有 ≥1 可见扰动条目的任务数），另显示可见占位卡数量；
- **baseline 卡不参与筛选、始终显示**；筛选只影响扰动卡与占位卡；
- 任务分组折叠规则：仅当 `task` 筛选把整个任务排除时隐藏该任务分组；因 window/mechanism/severity/semantics/verdict/搜索导致任务内无可见扰动卡时，保留任务分组并显示 baseline + 空态说明。
3.2 **逐任务分组**（任务按 T00→T09 顺序；每个任务一个分组）：
- 任务头：任务编号 + instruction、本任务用例数、成功率 `k/N`、各窗口用例数（如 `early 18 / mid 22 / later 16 / all_done 3`）；若某窗口在本次任务中完全没有用例，在任务头标注计数；若任务完全没有 early/mid/later 用例（如 T09 全为 all_done），在三窗口网格位置显示一条全宽任务级空位说明「本任务无三窗口用例，见下方 all_done 小节」，不再渲染 family 行；
- **每个任务最前面放且只放 1 条 baseline 视频**：全宽突出卡片，标注「Baseline（配对基线，无扰动）」，显示成功/失败、步数、seed/run、原片链接（多 run/seed 的基线选择规则见 1.5）；基线失败时在任务头醒目标注「基线失败，扰动结果不计入成功率分母」；
- 之后才是扰动视频区（见 3.3）。
3.3 **扰动视频网格（硬性版式）**：

布局示意（每个任务一个分组；每行固定三个窗口槽位）：

```
┌ T00 · <instruction> ─ 用例 10 · early 1 / mid 5 / later 1 / all_done 3 ┐
│                                                                        │
│  [ Baseline（配对基线，无扰动）· 成功 · 240 步 · seed 0 · 原片链接 ]   │
│                                                                        │
│  family: target-joint-upright-setback1-restore · 机制/档位：…           │
│  ┌─────────────────┬─────────────────┬─────────────────┐               │
│  │ early           │ mid             │ later           │               │
│  │ [空位说明卡]    │ [视频卡]        │ [视频卡]        │               │
│  │ 该用例族仅含    │                 │                 │               │
│  │ mid、later      │                 │                 │               │
│  └─────────────────┴─────────────────┴─────────────────┘               │
│                                                                        │
│  [ all_done / 未识别窗口：单独小节，位于三窗口区之后 ]                 │
└────────────────────────────────────────────────────────────────────────┘
```
- **每行 3 个**，按「用例族 × 窗口」排列，从左到右固定 `early` → `mid` → `later`；
- **视频网格固定 3 列**：窄屏（<1200px）也保持 3 列并允许横向滚动，不得改为 2 列/1 列；页面其余部分可响应式；
- 每个任务的扰动网格顶部显示列标题 `early | mid | later`（可 sticky），保证滚动时窗口位置可辨认；
- 同一 family（同一任务内，`case_id` 去掉独立 `early`/`mid`/`later`/`all_done` 片段后相同）占一行，行首或行上方显示 family 标识（机制 + 档位 + family 短名）；
- **某窗口无对应用例时，该槽位必须渲染空位说明卡**（虚线边框、灰底）：写明「该窗口无对应用例」及该 family 实际包含的窗口（如「该用例族仅含 mid、later」）。不得跳过槽位，不得把后面的视频挤上来；
- 同一 family 在同一窗口有多条用例（多 seed/重复）时，按 (seed, case_id) 排序拆成多行，第 k 行放各窗口第 k 条，缺者用空位卡，保持窗口列对齐（不同 seed 不得混入同一槽位）；
- 单窗口 family（early/mid/later 中仅有一个窗口）同样按 3 槽规则渲染（1 条视频 + 2 个空位说明卡），保证「窗口位置固定」；仅含 all_done 的 family 直接放到 all_done 小节；
- **`all_done` 与「未识别」窗口**单独小节，放在三窗口区之后；同样采用每行 3 个的网格（按 family_key、case_id 排序），但**不套三窗口槽位、不渲染窗口空位卡**；卡片标窗口徽标与说明，all_done 用例还要标注是否开启 `--post-success-window`。不得把它们混进 early/mid/later 的 3 槽行；若某 family 同时有 e/m/l 与 all_done 用例，`all_done` 卡放独立小节并注明「同 family 另有三窗口视频」并给出锚点链接；
- 只有基线、没有扰动用例的任务也要渲染分组并说明。
3.4 **视频卡内容**：窗口徽标、`case_id`（可简写，完整值悬停可见）、mechanism 中文标签（见附录 B）、severity 原码（附档位说明，不强行翻译）、seed、结论徽标（按完整 verdict 映射：恢复/对照/探针/未恢复/协议不完整/触发未到达/注入无效/关系未验证/数据不完整）、注入步、扰动步数、恢复延迟、`<video controls preload="metadata" playsinline muted loop>`、原片链接；缺失视频显示「无视频证据」并保留其他字段。
3.5 **视频处理**：把报告引用的视频按统一参数转码复制到 `{{REPORT_DIR}}/videos/`（建议 `256×256、12 fps、H.264 CRF 30、无音轨`，参数与现有报告一致），用相对路径引用；每个卡片保留原片相对路径链接；缺失视频不得静默跳过，必须在卡片与数据质量小节列出。
3.6 **筛选与占位的交互**：**无论默认还是筛选状态，扰动网格始终保持 3 列格位、不重排**；筛选后不匹配的卡片不渲染（保留其格位为空），整行无可见卡时隐藏该行；占位卡在其对应窗口仍处于筛选范围、且该 family 行仍有可见卡时保留；任务分组折叠规则见 3.1；筛选计数按 3.1 定义更新。

### 四、方法与复现
- 生成命令/脚本路径、`evidence.json` 生成方式；
- 数据来源、布局探测结果、join 规则（含 `_s<seed>` 后缀与 `all_done` 归一化）与 join 成功率；
- 配对基线与注入校验方法（strict pairing / pairing audit）的简要说明；
- 视频转码参数与报告目录布局；
- 已知限制：注入被拒、触发未到达（含 all_done 未开 post-success-window 的情况）、协议不完整、未映射元数据、视频缺失、单 seed、窗口/用例数不等量、相对 catalog 的覆盖缺口、返回码含义。

### 五、附录：逐条结果表
全量案例表（用例、任务、窗口、机制、档位、基线、注入有效、步数、恢复延迟、结论），支持按列排序或至少按任务/窗口分组；表格行与视频卡锚点互链，便于定位。

> 可选增强（不强制）：任务 × 窗口成功率分组柱状图/热力图、基线与扰动步数对比图、失败模式汇总、基线失败/注入无效专表、按 family 的成功率对照表。

## 3. 实现与交付要求

- **可复现**：生成报告的代码必须落盘为脚本（优先复用 `scripts/build_eval_report.py` 的 `metrics()`/`group()` 与分类器口径，新增或重写渲染层；必要时新建 `scripts/build_*_report.py`），报告可由一条命令重新生成；禁止手工拼数字。脚本需幂等，不修改 `runs/`、`dataset/` 原始文件。注意现有 `collect()` 只支持「单 batch 根」：对容器根（如 `runs/retest-20261018`）与 legacy 逐用例根返回 0 行，必须补 layout adapter / 递归发现，或自行实现 collector。
- **复用现有数据层时必须先修正其已知缺陷**：layout 发现（`collect()` 仅支持单 batch 根）、`all_done` 归一化 join（当前实现会丢全部 40 条 all_done 元数据）、catalog `severity` 与 binding 运行标签混用、verdict 标签缺 4 个键（其中 3 个在 retest 出现，导致约 144 条「未判定」）、`instruction` 字段实际存 suite 等问题（详见附录 B）。
- **离线可用**：默认输出 `{{REPORT_DIR}}/index.html` + `{{REPORT_DIR}}/videos/` + `{{REPORT_DIR}}/evidence.json`；HTML 内联 CSS/JS/SVG，不引用 CDN、外部字体或网络资源；`{{SINGLE_FILE}} = true` 时才把视频以 base64 内嵌并说明体积。
- **页面质量**：UTF-8、`lang="zh-CN"`；页面整体响应式（导航/表格/图表自适应），但**视频网格固定 3 列**（窄屏横向滚动，不改为 2/1 列）；所有数据文本做 HTML 转义；视频不自动播放、不自动带声；`file://` 直接打开可用；浏览器控制台无报错。
- **性能**：HTML 本体建议 < 10 MB（不含视频目录）；视频懒加载（`preload="metadata"`），不要一次性加载全部视频。
- **一致性**：图表、明细表、视频卡、`evidence.json` 四处数字一致；`evidence.json` 含口径字段与视频路径；报告中给出生成溯源（脚本、命令、时间、模板版本）。
- **交付回复**（给发起人）：报告目录、`index.html` 大小、用例数/任务数、整体成功率、生成命令、数据质量问题清单、自检结果。

## 4. 禁止事项

- 不编造实验背景、模型配置、数字或结论；取不到的信息写「未记录」。
- 不把注入被拒/触发未到达/基线失败计为模型失败；不把注入无效计入成功率分母，不把基线失败计入成功率/恢复率分母。
- 不把外部复原、协议不完整、真值未验证计为模型自修恢复。
- 不丢弃未映射元数据、缺视频用例、缺窗口用例；必须显式说明。
- 不混用不同分母；不把 catalog `severity` 与 binding 运行标签混为一谈；不把 runtime locator 当 catalog task_index。
- 不改变窗口固定顺序；不把 baseline 混入扰动网格；不用占位替代真实视频。
- 不引用 CDN/网络资源；不修改原始运行产物；不在数据核对完成前写实验介绍和结论。

## 5. 交付前自检（逐项勾选，并在最终回复中列出结果）

- [ ] 运行目录、报告目录、标题、模型/checkpoint、步数上限、seeds、runtime overlay、post-success-window、实验日期已核对并注明来源；
- [ ] 数据质量清单完整：未映射、注入被拒、触发未到达、协议不完整、基线失败、视频缺失、多 seed、窗口不等量、相对 catalog 的覆盖缺口、返回码；
- [ ] 1.3 对 window / mechanism / severity / semantics 逐值解释了含义，并给出「本次用例数 + 一条本次真实 case 示例（视频卡链接）」，没有只列代码或数量；
- [ ] 指标口径与分母在报告中显式写出；图表/表格/视频卡/`evidence.json` 数字一致；成功率与自修恢复率分开定义；
- [ ] 成功率分母 = 基线成功且注入有效条目；协议不完整、对照、探针的归属已声明；敏感性成功率（排除对照/探针）已展示；
- [ ] 指标卡包含注入被拒、触发未到达、协议不完整、基线失败与敏感性成功率；
- [ ] catalog join 成功率已统计（当前命名 run 应为 100%；未匹配条数单独列出）；
- [ ] 整体成功率图表存在；window 成功率柱状图纵轴 0–100%、顺序 `early→mid→later→all_done`；
- [ ] 各维度柱状图均标注 `k/N` 与 `n`（定义见 2.3）；空分组两种状态、`n<5` 有提示；severity 使用 catalog 档位；
- [ ] 视频区每个任务最前面只有 1 条 baseline，之后才是扰动视频；
- [ ] 扰动视频每行 3 个、3 列格位固定（窄屏横向滚动），按 family 分行、窗口列固定，缺窗口有明确空位说明（含单窗口 family）；
- [ ] `all_done`/未识别窗口在单独小节（同样每行 3 个），未混入三窗口网格；
- [ ] `window` 筛选选项含 `all_done`/未识别；筛选计数定义正确；筛选状态不重排；baseline 始终可见，任务分组折叠规则正确；
- [ ] 视频可播放、原片链接可点、缺失视频有说明；
- [ ] HTML 离线可用、无外部依赖、无控制台错误；体积与视频懒加载符合要求；
- [ ] **页面使用浅色背景（light theme），非深色背景**；正文/表格/图表/卡片对比度正常；
- [ ] 存在单独的「2.7 扰动未生效用例拆解」小节：原因分类汇总、按窗口/机制拆解、逐条错误明细、影响与重跑建议齐全；这些条目未被计为模型失败；
- [ ] 实验介绍中的每项背景/配置都有来源，未记录项已标注；
- [ ] 报告生成脚本已落盘，可用一条命令重建；交付回复包含自检结果与遗留问题。

---

# 附录 A：占位符与填写示例

```
{{EXPERIMENT_NAME}} = libero_10 T00–T09 全量重测（step=600，恢复导向）
{{RUN_DIRS}}       = runs/retest-20261018
{{REPORT_DIR}}     = runs/retest-20261018/report
{{TITLE}}          = LIBERO-10 rollback 实验报告 · T00–T09 全量重测（step=600）
{{NOTES}}          = 本次实验关注扰动后的恢复行为；成功率分母 = 基线成功且注入有效条目；模型 pi05。
{{SINGLE_FILE}}    = false
```

填写原则：路径用仓库根相对路径；一次实验有多个运行目录时用逗号或换行分隔，并在报告中写明每个目录覆盖的任务；`NOTES` 只写实验事实与关注点，不写结论。

**示例实验的已核对数字（2026-10-18 的 `runs/retest-20261018`，仅用于核对口径，禁止硬编码进新报告）**：

| 项目 | 数值 |
| --- | --- |
| catalog 用例数（manifest） | 522；本次实际运行 518（T07 缺 3 条、T08 缺 1 条，均为 `move_to_relation_target`） |
| 任务数 / 用例数 | 10 个任务 / 518 条 |
| 每任务×窗口（early/mid/later/all_done） | T00 1/5/1/3；T01 18/22/16/3；T02 15/22/13/3；T03 19/25/16/3；T04 14/32/21/3；T05 14/32/21/3；T06 14/32/21/3；T07 15/24/13/3；T08 9/27/16/3；T09 0/0/0/13；合计 119/221/138/40（其中注入有效 119/217/128/13） |
| 配对基线成功率 | 518/518 |
| 注入有效率 | 477/518；注入无效合计 41（注入被拒 8 / 触发未到达 33） |
| 成功率 / 自修恢复率 | 160/477 = 33.5% / 42/477 = 8.8%（分母 = 基线成功且注入有效） |
| 敏感性成功率（排除对照/探针） | 43/339 = 12.7%（12 条对照中成功 10、126 条探针中成功 107，均从分子分母剔除） |
| 协议不完整 | 7（计入成功率分母，不计恢复） |
| 视频 | 扰动 518 条 + 每任务 1 条基线（10 条），共 528 个 mp4；配对精确 518/518 |
| 返回码 | 各任务批次 returncode=2（部分扰动后未完成，是评测结果） |
| 扰动未生效原因（示例） | T01：6 条 = 3 条 all_done「触发后未执行」（post-success-window 未开启）+ 1 条保护体碰撞 + 2 条无合法关系边界对；需在报告 2.7 中按错误码/原因逐条拆解 |

> 用本提示词生成的示例报告：`runs/retest-20261018/report-task01-v2/index.html`（T01，2026-10-18 数据；生成脚本 `scripts/build_standard_task_report.py`）。

> 注意：`runs/report-all-tasks-20261018` 是旧版生成器产物，存在 all_done 元数据缺失（40 条 `task=None`）、「按档位」图缺失、144 条结论显示「未判定」、窗口筛选缺 `all_done` 等缺陷；新报告不得复制这些缺陷，但可参考其样式与脚本结构。

# 附录 B：数据契约与已知坑（执行者速查，2026-10-18 核对）

## B1. 输入布局与发现
| 布局 | 结构 | 说明 |
| --- | --- | --- |
| batch（当前主力） | `<root>/batch-summary.json`（可选）+ `<root>/taskNN/binding.yaml` + `<root>/taskNN/run/<ts>/results.json` + `videos/` | 17 个 batch 根 + 容器（如 `runs/retest-20261018` 下有 10 个 batch）；4 个 batch 风格根缺 `batch-summary.json`（runner 中断），仍应读取 `results.json` |
| legacy 逐用例（历史） | `<root>/<case-dir>/binding.yaml` + `<root>/<case-dir>/<ts>/results.json` + `videos/` | 逐 case 根（按顶层含 case 目录计数，本仓库约 54 个；如 `runs/full-eval-pi05`：199 目录/198 有结果）；每 results 恰 1 baseline + 1 perturbation |
| 容器/混合 | `<root>` 下多个 batch/legacy 子根，或 task-NN 与逐用例混合（`runs/full-coverage`） | 递归发现（不设固定深度上限：retest 容器下 results.json 在第 4 层）；按 `results.json` 路径去重 |

现有 `scripts/build_eval_report.py::collect()` 只支持「单 batch 根」：对容器根返回 0 行、对 legacy 根返回 0 行，需要 layout adapter + 递归发现（不要依赖 `batch-summary.json` 存在性）。

## B2. results.json / binding 契约
- 顶层：`{ "<TASK_KEY>": { "suite", "task_idx", "instruction", "protocol", "results" } }`；`TASK_KEY = {suite}_{runtime locator}`（如 `LIBERO_10_T33`），`task_idx` 是 locator（33），**不是** catalog `task_index`（1）。
- `results["baseline_s<seed>"]`：`kind="baseline"`，含 `success`、`steps`、`recovery_cost`。
- `results[<perturbation label>]`：`kind="perturbation"`，label = `{task_profile}_{case_name}_{severity}_s<seed>`；含 `success`、`steps`、`report`、`pairing_audit`、`reproducibility`。
- `report` 关键字段：`injection_valid`、`injection_step`、`trigger.reached`、`rule_executed`、`outcome.recovered`、`outcome.recovery_latency_steps`、`outcome.termination.max_steps`、`errors`；`pairing_audit` 在 perturbation 记录顶层（`eligible`、`required_prefix_queries`）。
- `protocol` 关键字段：`model`、`checkpoint`、`replan_steps`、`strict_paired_baseline`、`post_success_window` 等。
- `binding.yaml`：`perturbation_binding.task_profile` + `enabled_cases[{case_name, template, severities, trigger_event, parameters}]`。
- 其他文件：`batch-summary.json`（model/cases/tasks.NN.{cases,seeds,returncode,binding,log}）、`driver.log`（全局 seeds、model、runtime 路径、output、每任务 seeds/rc）、`eval.log`（Model/Suite/Task/MaxSteps/Seeds/RUN_PROTOCOL）、`evaluation_summary.json`（baseline success_rate/steps、每 case 注入计数）、`episode_details.jsonl`（逐条 report）。

## B3. 视频命名与配对
- baseline：`{TASKKEY}__baseline_seed<n>.mp4`；
- 扰动：`{TASKKEY}__{label 末尾 _s<n> 替换为 _seed<n>}.mp4`；
- 当前数据实测：扰动视频精确配对 518/518、每批次 baseline 10/10（baseline 每任务 1 条、跨用例共享，因此 518 条扰动 + 10 条 baseline = 528 个 mp4）；legacy `full-eval-pi05` 198/198（198 条扰动 + 198 条 baseline = 396 个视频）。必须 seed-aware（多 seed 时同一 case 会有多条），并按 1.5 的回退链处理。

## B4. catalog 与 join
- 入口：`dataset/current/manifest.yaml` → `cases[].path`；case YAML 关键字段：`case_id`、`task.{suite, task_id, task_index, source_task_locator, source_bddl}`、`trigger.{time_point, event, window, delay_steps}`、`severity`、`expected_evaluation_semantics`、`rollback_target.state_change.kind`、`template_id`、`scenario_type`、`stage`。
- 十任务（catalog 当前 522 条；manifest `case_count` 为准）：

| task_index | task_id | runtime locator | instruction（BDDL 原文） |
| --- | --- | --- | --- |
| 0 | libero_10/00 | T0 | turn on the stove and put the moka pot on it |
| 1 | libero_10/01 | T33 | put the black bowl in the bottom drawer of the cabinet and close it |
| 2 | libero_10/02 | T78 | put the yellow and white mug in the microwave and close it |
| 3 | libero_10/03 | T133 | put both moka pots on the stove |
| 4 | libero_10/04 | T137 | put both the alphabet soup and the cream cheese box in the basket |
| 5 | libero_10/05 | T145 | put both the alphabet soup and the tomato sauce in the basket |
| 6 | libero_10/06 | T158 | put both the cream cheese box and the butter in the basket |
| 7 | libero_10/07 | T193 | put the white mug on the left plate and put the yellow and white mug on the right plate |
| 8 | libero_10/08 | T237 | put the white mug on the plate and put the chocolate pudding to the right of the plate |
| 9 | libero_10/09 | T276 | pick up the book and place it in the back compartment of the caddy |

- join 归一化：`norm(s) = s.replace("_","-")`，两侧同时归一化后再匹配；`case_name = "dataset_" + case_id.replace("-","_")`。
- 旧命名 run（2026-10-17 及更早）不能直接 join 当前 catalog（旧名如 `dataset_libero_10_00_moka_pot_stove_rollback_s1_s2_early_p1`，当前 catalog 匹配率 0/63、0/198）；`docs/case-renaming-proposal.md` 是未执行提案，不可作权威 crosswalk。此类运行必须标注「旧命名、未映射」。

## B5. family 算法
```
family_key(case_id) = 把独立的 early | mid | later | all_done 片段替换为占位符 X 后的 case_id
                      （正则: -(early|mid|later|all_done)(?=-|$) → "-<W>"）
```
- 同一 task 内按 family_key 分组；每行固定 3 槽：early / mid / later；同窗口多条按 (seed, case_id) 排序拆行；
- 单窗口/双窗口 family（仅指 early/mid/later 窗口）一样渲染 3 槽，缺失窗口放空位说明卡；`all_done` 用例放在单独小节、不参与三槽行；仅含 all_done 的 family 直接放 all_done 小节。family_key 仍折叠 all_done，便于与同 family 的三窗口视频互相引用；
- 参考统计（同时折叠 early/mid/later/all_done 的口径，catalog 522 条 → 282 family）：size 1/2/3/4 = 134/60/84/4；三窗口齐全 84 个；含 all_done 的 family 40 个；无重复窗口。retest 518 条 → 280 family（比 catalog 少 2 个 family：T07 的三窗口 family 整体未跑、T08 的 mid-only family 未跑，对应 4 条 `move_to_relation_target` 用例）。**若只折叠 early/mid/later，会得到 290 family（142/64/84）；两种口径都可用，但报告必须在方法小节写明所用口径，并与图表、视频区一致。**

## B6. 维度枚举与中文标签
- window（schema 定义）：`early` = 第一个子目标刚确认；`mid` = 机械手撤离并转向下一步；`later` = 收尾/下一步动作进行中；`all_done` = 全部目标谓词已成立（完成边界）。中文短标签建议用「early（刚完成）/ mid（撤离转向）/ later（收尾进行中）/ all_done（全部完成边界）」。
- window ↔ trigger event（参考）：early → `enter_first_subgoal_completed` / `enter_next_subgoal_approach`；mid → `enter_next_subgoal_approach` / `enter_post_completion_retreat`；later → `enter_next_subgoal_lift` / `enter_x3a_actuation`；all_done → `enter_next_subgoal_completed`。
- severity（当前 catalog 14 种，固定顺序）：`d0, pose, n3, n5, n8, p3, p5, p8, p10, r05, above, boundary, reference, articulation`；schema 共 18 种，另有 `d1/d2/d3/checkpoint`，出现未列值时原码显示并标注；binding 的 40 种 grid 标签只作「运行标签」。
- semantics：当前 catalog 3 种——`relation_then_resume`（关系失效后应恢复）、`relation_holds_control`（关系保持，对照）、`relation_only`（仅关系，探针）；schema 共 5 种（另有 `protected_partial`、`unsupported_boundary`），出现未列值时原码显示并标注。
- mechanism（catalog 当前 10 种；schema 共 11 种）：`restore_episode_initial_pose` 恢复回合初始位姿、`apply_episode_initial_offset` 施加初始位姿偏移、`displace_from_completed_pose` 从已完成位姿位移、`restore_native_relation_set` 恢复原生关系集、`displace_to_relation_boundary` 位移到关系边界、`restore_container_above_pose` 恢复到容器上方位姿、`revert_articulation_goal` 回退关节目标、`translate_relation_pair` 整对平移、`displace_reference_object` 位移参照物、`move_to_relation_target` 移动到关系目标；schema 另有 `restore_captured_checkpoint_pose`（恢复到捕获检查点位姿，当前 catalog 未用）。缺失标签显示原文 + 「未映射标签」。
- verdict（按报告展示顺序，不是 `classify_result` 的代码返回顺序）：`valid_recovered` 模型自修恢复、`valid_control` 关系保持（对照）、`valid_relation_preserving_probe` 关系保持（探针）、`valid_not_recovered` 注入有效但模型未恢复、`protocol_incomplete` 协议不完整（模型未修，第二次撤销未触发）、`truth_unverified` 关系真值未验证、`trigger_not_reached` 触发未到达、`injection_invalid` 注入无效、`valid_external_restoration` 外部复原（不计模型恢复）、`incomplete` 数据不完整。

## B7. 指标与分类器
- 判定器：`src/libero_rollback/evidence.py::classify_result`；`valid_recovered` 需注入有效 + `repair_completed` + `outcome.recovered`，多关系还要谓词身份与最终真值全对；`valid_external_restoration` 永不进入 recovered。
- 三套分母（统一按本提示词口径）：成功率 = perturbation `success ÷ (baseline 成功 ∧ 注入有效条目数)`；恢复率 = `valid_recovered ÷ (baseline 成功 ∧ 注入有效条目数)`；注入有效率 = 注入有效数 ÷ 用例条目数。
- 现有 `scripts/build_eval_report.py` 内部有两套恢复统计（`totals` 用 classifier、分组图表用 `perturbation_success`），新报告必须统一。
- 返回码：0 全部成功结束；2 部分用例扰动后未完成（评测结果）；3 配对基线失败、扰动未启动。

## B8. 现有生成器已知缺陷（新报告必须修正，勿照抄）
1. `canonical()` 只对结果/binding 侧做 `_`→`-`，未归一化 catalog 侧 → 40 条 all_done 用例 `task=None`、8 个元数据字段为空；同时缺 layout adapter：`collect()` 仅支持单 batch 根，容器根与 legacy 根返回 0 行；
2. 「按档位」图用 binding grid label 与 `SEVERITY_ORDER` 匹配 → 图为空；
3. `VERDICT_LABEL` 只有 6 个键，缺 4 个（`valid_control` / `valid_relation_preserving_probe` / `truth_unverified` / `incomplete`），其中前 3 个在 retest 出现（约 144 条「未判定」）；
4. 窗口筛选器漏 `all_done`；行字段 `instruction` 实际存 suite；
5. 同一报告内两套恢复统计；`metrics()` 的 `recovered` 用 classifier 但 `group()` 的 `recovered` 用 `perturbation_success`；
6. `metrics()` 的 `rejected` 把「触发未到达」并入「注入被拒」（retest 的 41 = 注入被拒 8 + 触发未到达 33），报告必须拆分统计。

## B9. 其他口径
- 文档中 catalog 条数存在 288 / 522 / 287 / 518 等多套口径：以 `dataset/current/manifest.yaml`（当前 522）为准，报告中注明冲突；
- `all_done` 用例需要真实任务成功 + 释放 + 成功后继续窗口，依赖 `--post-success-window`；未开启时触发未到达要写明原因；
- 报告中的实验介绍不得把「原生端点预检通过」写成「模型恢复成功」；预检、静态校验与 live 恢复是不同层证据。

## B10. 扰动未生效（injection 未生效）原因映射（2.7 速查）

| 判定 / 错误码 | 含义 | 常见原因 | 建议处理 |
| --- | --- | --- | --- |
| `trigger_not_reached` | 触发事件未到达，注入规则未执行 | 触发条件/步数预算/运行协议 | 检查触发事件与预算 |
| `INTERVENTION_NOT_EXECUTED` | 触发到达但规则未执行（触发后没有后续 before_step） | all_done 场景未开启 `--post-success-window` | 开启 post-success-window 后重跑 |
| `INTERVENTION_ACTIVATION_FAILED` + `ROLLBACK_CONTACTS_PROTECTED_BODY` | 注入路径会碰到受保护物体 | 平移方向/幅度与保护体约束冲突 | 调整平移参数/保护体配置后重跑 |
| `INTERVENTION_ACTIVATION_FAILED` + `NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR` | 搜索范围内找不到「界内合法→界外合法」位姿配对 | 封闭容器（抽屉/微波炉）的边界搜索受限 | 调整边界搜索策略或用例设计后重跑 |
| 其他 errors / `rule_executed=False` | 其他注入规则执行错误 | 规则执行异常 | 查看 error detail 后定位 |
| `injection_valid=False` 且无 error | 未记录原因 | 产物缺少错误明细 | 标注「未记录」，不要猜原因 |

这些条目一律不计入成功率/恢复率分母，也不计为模型失败；报告 2.7 必须逐类给出条数、涉及窗口/机制、逐条明细与重跑建议。

---

# 附录 C：评审验收清单

除第 5 节自检外，评审者可额外核对：

1. 首屏（不滚动）能看到：实验名称、模型/suite/步数、整体成功率 `k/N`、用例数、生成时间与模板版本。
2. 任取一个 window 柱值，能与 `evidence.json` 按 `time_point` 分组的 `k/N` 对上，且分母与报告声明一致；`all_done` 没被漏掉。
3. 任取一个任务：baseline 视频在该任务所有扰动视频之前，且该任务只有一条 baseline。
4. 任取一个缺窗口的 family：能看到对应空位说明卡（写明缺哪个窗口、该 family 实际有哪些窗口）；单窗口 family 也按 3 槽渲染。
5. 筛选 `window=mid`：计数、任务分组、卡片集合正确，无残留不匹配卡片；3 列格位不重排；重置后恢复完整视图；baseline 始终可见。
6. 断网、双击 `index.html` 打开：结构、图表、筛选、视频均正常；控制台无报错。
7. 「方法与复现」中的命令能重跑并生成同结构报告；重跑后 `evidence.json` 主要数字一致。
8. 报告中「数据质量与口径核对」小节完整，未映射/被拒/未触发/协议不完整/视频缺失/覆盖缺口均有条数，且没有用「未判定」「None」「未记录」掩盖可解释的缺失。
9. 敏感性成功率、按窗口的有效分母（例如 retest 的 119/217/128/13）能由 `evidence.json` 复算；协议不完整在堆叠图中单独成段。
10. 1.3 的 window / mechanism / severity / semantics 四张表逐值有含义、有本次真实示例，示例链接能跳到 3.x 视频卡；没有只列代码/数量。
11. 2.7 小节存在且完整（原因分类汇总、按窗口/机制拆解、逐条错误明细、影响与重跑建议）；未生效条目数与 `evidence.json` 的 `invalid_analysis` 一致，且未被计入成功率分母或计为模型失败。
