# 人工审核报告模板规范 v1（`review-report-v1.0`）

> 适用对象：LIBERO-Rollback **B 套件（完成边界回滚）**及其它“注入扰动 + 条件恢复”实验的
> **人工审核报告**。本规范定义页面结构、白色主题 token、审核口径与验收清单；
> 生成器为 [`scripts/build_review_report.py`](../../scripts/build_review_report.py)，
> 可直接打开的样例为 [`case-review.html`](case-review.html)（**样例数据，非实验结论**）。
>
> 模板定位：**不是**论文结果页，也**不是**自动判定器；它是让审核者逐条确认
> “注入是否真的发生、恢复是否真的来自策略自修复”的**证据台账**。

---

## 1. 用途：人工审核两件事

### 1.1 审核问题 A：注入是否真实有效（injection validity）

一个 case 只有在同时满足下列条件时，才允许进入“恢复有效性”讨论：

| 门控 | 含义 | 失败意味着 |
|---|---|---|
| `completed_relation_true_before_intervention` | 触发时被撤销关系在 GT 中为真 | 本来没达成 → 不是“撤销” |
| `all_revoked_false_after_intervention` | L0/L1/L2 注入后关系为假；C0 相反必须仍为真 | 注入没改状态 / C0 被误改 |
| `no_object_penetration` | 物体-场景/物体侵入 ≤ 1 cm | 写回位姿穿模，物理不可信 |
| `zero_velocity_after_intervention` | 注入后物体线/角速度归零 | 物体还带着残余速度 |
| `object_released_before_intervention` | 注入前机器人已松开（两指间距 > 1 cm） | “还拿着物体”不构成撤销 |

`restorable`（状态写回 oracle）是**辅助证据，不是硬门控**：它只证明“几何上写得回去”，
**不等于**策略能自己恢复。报告必须把它与恢复分子严格分开。

> 口径：`injection_valid = trigger_reached ∧ 上述 5 个硬门控全通过`。
> 注入无效的 case **不计入 Recovery 分母，也不计为模型失败**，必须单列原因。

### 1.2 审核问题 B：恢复是否真实来自策略自修复（recovery validity）

`Recovery = 注入有效且非 C0 的 case 中，episode 结束时被撤销关系全部恢复为真`。

审核时必须区分下面这些**都不是**模型恢复：

| 状态 | 处理 |
|---|---|
| **注入无效**（`injection_invalid`） | 不进分母；不计模型失败 |
| **触发未到达**（`trigger_not_reached`） | 记 `N/A`，**不是 0%**，不进分母 |
| **`restorable` oracle 通过** | 只证明几何可修；不是策略恢复，不进分子 |
| **外部复原**（`valid_external_restoration`） | 永不进恢复分子 |
| **协议不完整 / 真值未验证** | 不进恢复分子，单列 |
| **C0 no-op 对照** | 不进 Recovery；单独报 `control_rate` |
| **单步 success 但终局关系仍假** | 不进 Recovery 分子（Recovery 看终局关系） |

### 1.3 审核者要落下的两个勾选

每条 case 卡片底部固定两个复选框 + 备注：

- **注入有效**：我认可这次注入确实按门控改变了状态；
- **恢复有效**：我认可“恢复/未恢复”的判定是策略自身行为（不是 oracle、外部或未触发误判）。

勾选与备注写入浏览器 `localStorage`（键含报告 ID），可一键导出 JSON 归档。
报告本身**不写入**人工结论；人工结论以导出 JSON 为准。

---

## 2. 生成方式与产物

### 2.1 一键生成

```bash
.venv/bin/python scripts/build_review_report.py \
  --from-run <B_RUN_DIR> \
  --out experiments/b-rollback/report-goal-object-20261118 \
  --title "B 测试集 · pi05 · Goal+Object 注入/恢复有效性审核" \
  --model pi05 \
  --protocol "max_steps=600; trigger=all_done+delay=10; init_row=0; seed=0; replan=10; camera=256; video=20fps" \
  --source-run "libero-compose:/runs/b-matrix/full-20261118" \
  --old-report "libero-compose:/runs/b-matrix/report-goal-object-20261118" \
  --reconcile-json <OLD_REPORT_DIR>/aggregate.json \
  --run-summary <B_RUN_DIR>/run-summary.json \
  --notes <REPORT_DIR>/NOTES.txt \
  --per-page 60 \
  --extra-file <REPORT_DIR>/SUMMARY.md
```

- `<B_RUN_DIR>`：包含 `<suite>/<case_id>/summary.json` 的源 run 目录；
- `<OLD_REPORT_DIR>` / `<REPORT_DIR>`：旧报告与新报告目录（主机路径只经 CLI 传入，
  **不写入仓库文件**；生成的 `command_template` 用占位符脱敏）；
- `--reconcile-json`：可选，与旧报告 `aggregate.json` 逐项对账并渲染差异；
- `--run-summary`：可选，核对源 run 根目录的 `run-summary.json` 是否与逐 case 数量一致；
- `--migrated-source REL=PATH`：可选（可重复），迁移旧报告文档（如 `SUMMARY.md`）时在
  `provenance.json` 同时记录**源文件 sha256** 与**迁移副本 sha256**；迁移副本若加入说明行
  或脱敏主机路径，两个哈希会不同，便于跨仓对账；
- 也可用 `--cases <cases.jsonl>` 直接读已有 review bundle。

### 2.2 产物清单

```text
<REPORT_DIR>/
├── index.html                  # 总览 + 注入/恢复总表 + 对账 + 全部 case 索引（165 条）
├── <suite>-partN.html          # 每 suite 分页的逐 case 审核卡（默认每页 60 条）
├── evidence.json               # 口径字段 + 逐 case 审核事实 + 视频相对路径
├── cases.jsonl                 # 规范化的 review bundle（一行一个 case）
├── README.md                   # 本报告说明（自动生成）
├── provenance.json             # 源 run/旧报告标记、生成命令、时间、artifact sha256
└── videos/
    ├── README.md               # 本地视频复制命令；“视频不入库”声明
    └── <case_id>.mp4           # 本地审核产物（*.mp4 被 .gitignore 忽略，不入库）
```

旧报告的 `SUMMARY.md` / `NOTES.txt` 作为历史材料迁移时可一并放入 `<REPORT_DIR>/`；
**迁移副本必须把主机绝对路径脱敏**，数字与结论不得改动，并注明“旧报告原样迁移”。

### 2.3 分页与命名

- `--split-by suite`（当前唯一支持）：每个 suite 独立分页，文件名固定
  `<suite>-part1.html`、`<suite>-part2.html`…；
- `--per-page N`（默认 60）：分页只影响“逐 case 卡片”所在文件；
  `index.html` 的索引表始终列出**全部** case 并链接到对应分页锚点；
- 旧模板的深色 part 页面**不得保留**：重建后 `index.html` 只能链接本次生成的页面。

---

## 3. 页面结构（必须逐节存在）

### 3.1 页头（每个页面都有）

| 字段 | 要求 |
|---|---|
| 标题 / 副标题 | 报告主题 + “人工审核两件事”的一句话 |
| 模型 | 如 `pi05`；取不到写“未记录” |
| 范围 | case 数、suite、**明确未跑的 suite**（如 spatial/l10 未跑） |
| 协议 | `max_steps / trigger / delay / init_row / seed / replan / camera / fps` |
| 数据来源 | 源 run 的相对标记（如 `libero-compose:/runs/...`） |
| 旧报告（只读对账） | 旧报告相对标记；没有写“未提供” |
| 模板版本 | 如 `review-report-v1.0` |
| 生成时间 / 报告 ID | ISO-8601（带时区）与稳定 ID（localStorage 用） |

### 3.2 `index.html` 章节顺序

1. **关键指标卡**：总 case、触发 all_done、注入有效（含无效数）、C0 对照、
   Recovery（分子/分母 + Wilson 95% CI）、恢复失败数；
2. **注入有效性总表**：逐门控 `通过 / 未通过 / 未记录 / 硬门控或辅助 / 说明`；
   `restorable` 必须标注“辅助、非硬门控”；未触发原因单独拆解；
3. **恢复有效性总表**：定义 + 整体 `k/N` + CI；按 suite / level / target / family 的分母与恢复数；
   C0 对照单独表；恢复字段含义表；
4. **数据来源与对账**（提供 `--reconcile-json`/`--run-summary` 时）：
   与旧报告 `aggregate.json` 逐项一致/不一致表、几何量量纲核对、差异解释、
   源 run `run-summary.json` 数量不一致说明；
5. **数据质量与范围**：覆盖/缺口、N/A、视频缺失、单 seed/init 限制；
6. **实验备注**：`--notes` 原文（`pre` 保留换行）；
7. **分套件页面**：每 suite 的 case 数、触发/有效/Recovery、分页链接；
8. **全部 case 索引**：筛选栏 + 全量表格（case_id→分页锚点、suite、level、
   target、family、指令、审核判定、注入、Recovery、视频、审核状态）；
9. **生成方法与自检**：生成器、命令、bundle 口径、自包含/localStorage/视频说明、自检清单。

### 3.3 逐 case 审核卡（每页每 case 一张）

| 区块 | 必含内容 |
|---|---|
| 卡头 | `case_id`、verdict 徽标、level/target/family/semantics、suite/task_idx/bddl、expected_relation_after |
| 指令 | BDDL instruction 原文 |
| **① 注入有效性** | 7 个门控逐项（真/假/未记录 + 期望）、`penetration_m`、`max_velocity`、geometry（`delta_translation_m`/`delta_angle_rad`/`delta_joint_max`/`axis`）、`trigger_step`/`injection_step`/`injection_wait_steps` |
| **② 恢复有效性** | `relation_before` / `relation_after_injection` / `relation_final` / `recovered` / `restored_at_step` / `notice_latency` / `repair_budget_steps` / `termination` / `steps` / `success` / `final_*_truth`；C0 与未触发显式写 `N/A`（不是 0%） |
| **③ 视频证据** | `<video controls preload="metadata" playsinline muted loop>` + “跳到注入 / 跳到首次恢复 / 跳到结束”三个按钮（`video.currentTime`）+ 文件相对路径/fps/注入时刻；视频缺失显示**显式提示**，不得静默 |
| **审核** | “注入有效”“恢复有效”两个 checkbox + 备注 textarea + 本地保存状态 |
| 机器可读 | 卡内 `<script type="application/json" class="case-facts">`，含全部审核事实与判定 |

字段来源：源 run 的 `summary.json`。源数据没有的字段写“未记录”，**禁止推测**；
原始数值不得改写，派生字段只有 `injection_valid` 与 `verdict` 两个口径标签。

---

## 4. 视觉规范：白色主题（硬性）

### 4.1 CSS 颜色 token（页面 `:root` 固定）

| token | 值 | 用途 |
|---|---|---|
| `--bg` | `#ffffff` | 页面背景（**必须白色**） |
| `--bg-soft` | `#f7f8fa` | 侧栏 / 弱底 |
| `--card` | `#ffffff` | 卡片底 |
| `--card-alt` | `#f4f6f8` | 表头 / 公式底 |
| `--ink` | `#1f2933` | 正文/标题（深色文字） |
| `--ink-soft` | `#52606d` | 次级文字 |
| `--muted` | `#7b8794` | 说明文字 |
| `--line` | `#d9e2ec` | 边框/分隔线 |
| `--accent` | `#2563eb` | 链接/主按钮 |
| `--accent-soft` | `#eff6ff` | 高亮底 |
| `--ok` / `--ok-bg` | `#166534` / `#ecfdf3` | 通过/恢复 |
| `--warn` / `--warn-bg` | `#92400e` / `#fffbeb` | 缺失/警示 |
| `--bad` / `--bad-bg` | `#b42318` / `#fef3f2` | 未通过/未恢复 |
| `--na` / `--na-bg` | `#4b5563` / `#f3f4f6` | N/A |
| `--radius` / `--shadow` | `10px` / 两段浅阴影 | 卡片圆角与层次 |

### 4.2 硬性禁止

- ❌ 深色背景（如 `#0d1117`、`#111827`）、`prefers-color-scheme: dark` 暗色分支；
- ❌ 任何 CDN / 外部字体 / 外链 CSS / 外链 JS / 远程图片；`index.html` 内联全部 CSS/JS；
- ❌ 自动播放带声视频、自动弹窗、阻止 `file://` 打开的绝对路径；
- ❌ 用截图或 base64 大视频替代 `videos/` 相对路径（单文件内嵌仅在明确要求时）；
- ✅ `file://` 双击可打开；1280px 与 1920px 视口均正常；
- ✅ 左侧导航 `position:sticky; top:0; height:100vh; overflow-y:auto`，内容区可读。

### 4.3 自检（文本即可验证）

- `background:#ffffff`、`--bg:#ffffff` 存在；
- `http://`、`https://`、`<link`、`<script src`、`prefers-color-scheme:dark` 均不出现；
- `lang="zh-CN"`、`<meta charset="utf-8">` 存在。

---

## 5. 交互规范

### 5.1 左侧 sticky 导航（严格层级）

- 侧栏按“总览 / 分套件页面 / 本页”分组，`<details open>` + 链接；
- 链接 `display:block; white-space:normal; overflow-wrap:anywhere`，避免长 case_id 撑破；
- 每个分页顶部有 `← 返回总览`、`← 上一页 / 第 N 页 / 下一页 →`；
- `index.html` 的索引表把每个 case 链接到 `<suite>-partN.html#case-<case_id>`；
- 所有 `h2/h3` 目标带 `scroll-margin-top`，避免 sticky 栏遮挡。

### 5.2 分类筛选与计数

分页提供 `level / target / verdict / 注入有效 / 恢复状态 / 审核状态 / 关键字`；
`index.html` 另加 `suite`。要求：

- 关键字匹配 `case_id / 指令 / bddl_name / family / task_idx`；
- 实时显示 `显示 x / y case`；
- 无可见 case 的 task 分组自动隐藏；重置按钮恢复全量；
- 筛选只改可见性，**不得改变 case 排序**，不得丢卡片数据。

### 5.3 跳转（index ↔ 分页 ↔ case 锚点 ↔ 视频时间点）

| 跳转 | 实现 |
|---|---|
| index → 分页 | 索引表每行 `href="<suite>-partN.html#case-<case_id>"` |
| 分页 → index | 页头/页脚/侧栏 `href="index.html"` |
| 分页内 → 任务 | 侧栏 `#task-<task_idx>`；卡片 `id="case-<case_id>"` |
| 卡片 → 视频时刻 | 按钮读取 `data-time`（注入，来自 `video.injection_time_s`）或 `data-step`（恢复/结束，按 `duration × step / steps` 估算）写入 `video.currentTime` 并 `play()` |

### 5.4 审核勾选与导出

- 每 case：`data-review="injection"`、`data-review="recovery"`、`data-review="note"`；
- localStorage 键：`libero-rollback-review:v1:<report_id>`；
- 页面加载时恢复；勾选/输入实时保存；卡片加 `reviewed` 左侧强调条；
- 顶部与分页底部提供“导出审核 JSON”，内容：

```json
{
  "report_id": "rr-xxxxxxxxxxxx",
  "template_version": "review-report-v1.0",
  "exported_at": "2026-11-18T12:00:00+08:00",
  "n_reviewed": 12,
  "reviews": {
    "b-goal-t000-g-l0": {
      "injection": true,
      "recovery": true,
      "note": "注入帧可见物体被移走；恢复确由策略完成",
      "updated_at": "2026-11-18T12:05:00Z"
    }
  }
}
```

> `file://` 下主流浏览器允许同源 localStorage；若被禁用，页面仍可正常阅读，
> 导出按钮会写出空/当前能读到的记录——审核结论必须及时导出归档。

---

## 6. 数据契约

### 6.1 `cases.jsonl`（review bundle，一行一个 case）

必须是源 run `summary.json` 的**忠实投影**（原始数值不改写）。生成器读取/补齐的最小字段：

| 字段组 | 字段 |
|---|---|
| 身份 | `case_id, suite, task_idx, bddl_name, instruction, target, level, param, family, semantics, expected_relation_after` |
| 触发 | `trigger_reached, trigger_step, injection_step, injection_wait_steps, trigger_skipped_reason` |
| 注入门控 | `validity.*`（7 项）、`injection.geometry.*`、`penetration_m, max_velocity, no_penetration, zero_velocity, object_released, restorable, restore_probe` |
| 恢复 | `relation_before, relation_after_injection, relation_final, recovered, recovery, restored_at_step, notice_latency, repair_budget_steps, termination, steps, success, final_goal_truth, final_revoked_truth` |
| 视频 | `video.path（相对 videos/<case_id>.mp4）, fps, injection_time_s, injection_frame, card_seconds` |
| 派生 | `injection_valid, verdict` |

**派生口径**（唯一允许的派生）：

```text
injection_valid = trigger_reached ∧ (5 个硬门控全为 true)
verdict = trigger_not_reached            （未触发）
        | injection_invalid              （触发但硬门控失败）
        | valid_control                   （C0 且 success）
        | control_failed                  （C0 且非 success）
        | valid_recovered                 （有效非 C0 且 recovered）
        | valid_not_recovered             （有效非 C0 且未 recovered）
        | incomplete                      （status != ok）
```

### 6.2 `evidence.json`

至少包含：`schema_version, template_version, meta（标题/模型/协议/来源/生成命令/报告ID/时间）、
case_count、verdict_counts、injection（attempted/triggered/trigger_rate/not_triggered/
not_triggered_reasons/硬门控计数/injection_valid/injection_invalid/controls/restorable 辅助）、
recovery（definition/na_rule/denominator/numerator/value/ci95/by_suite/by_level/by_target/
by_family/c0_controls）、failure_counts、notice_latency、geometry_by_level、data_quality、
videos、cases[]`。页面任何数字都必须能由 `evidence.json` 复现。

### 6.3 `provenance.json`

`template_version, generated_at, model, protocol, source_run, old_report, report_id,
report_dir, case_count, command_template, reconcile_file, run_summary_file,
sha256{相对路径: 哈希}, notes[]`。**不得含主机绝对路径**，源 run/旧报告用仓内相对标记。

---

## 7. 数字口径（红线）

1. **Recovery 分母 = 注入有效且非 C0**；C0、注入无效、触发未到达都不进分母；
2. **不可触发 = `N/A`，不是 0%**；`N/A` 必须进总表与 case 卡；
3. **`restorable` oracle ≠ 模型恢复**；不得进恢复分子，不得混入注入硬门控；
4. 每个率给 **Wilson 95% CI**；每个数字注明 `init_row` / `seed` / `max_steps`；
5. 分母为 0 时写 `N/A`，不得显示 `0.0%`；
6. 页面 KPI、总表、case 卡、索引表、`evidence.json` 五处数字必须一致；
7. 旧报告对账不一致时**必须写明差异与原因**，不得静默改数或照抄旧数。

---

## 8. 人工审核口径与验收清单

### 8.1 逐 case 审核步骤

1. 先看 **① 注入有效性**：5 个硬门控是否全通过；`restorable` 只作参考；
2. 若门控失败 → 勾“注入有效”不通过，备注原因，不进入恢复判断；
3. 若 `trigger_reached=false` → 记 N/A，不勾“恢复有效”，备注“触发未到达”；
4. 若注入有效：看 **② 恢复有效性** 的 `relation_final / recovered / restored_at_step`；
5. 播放视频，用“跳到注入 / 跳到首次恢复 / 跳到结束”核对时间点；
6. 判断恢复是否可见地由策略完成（而非瞬移/外部写回）→ 勾“恢复有效”；
7. 备注写明证据（视频帧、关系变化、可疑点）；
8. 定期点“导出审核 JSON”归档（localStorage 不是长期存储）。

### 8.2 验收清单（生成后逐项勾）

- [ ] 文件齐全：`index.html`、每个 `<suite>-partN.html`、`evidence.json`、`cases.jsonl`、`README.md`、`provenance.json`、`videos/README.md`；
- [ ] 白色主题：`background:#ffffff`；无深色背景/`prefers-color-scheme:dark`；
- [ ] 自包含：0 个 `http(s)://`、0 个外链 `<link>`/`<script src>`；`file://` 双击可开；
- [ ] 页头含模型、范围、协议、数据来源、模板版本、生成时间、生成命令；
- [ ] KPI 含 注入有效 / 触发 / C0 / Recovery（`k/N` + % + CI）/ N/A 数；
- [ ] 注入有效性总表逐门控计数，`restorable` 标注“辅助、非硬门控”；
- [ ] Recovery 分母口径写在页面正文；`N/A` 未显示为 `0%`；
- [ ] 左侧 sticky 导航 + 分页前后跳转 + `index ↔ partN ↔ #case-*` 链接全部可达；
- [ ] 筛选（suite/level/target/verdict/恢复/关键字）与“显示 x / y”计数正常；
- [ ] 每 case 卡含注入门控、几何量、恢复字段、视频跳转三按钮；
- [ ] 视频缺失有显式提示（不是空白/静默跳过）；
- [ ] 每 case 两个审核勾选 + 备注；localStorage 恢复；导出 JSON 可用；
- [ ] `evidence.json` 的 `case_count`/分母/分子/门控计数与页面、`cases.jsonl` 一致；
- [ ] `provenance.json` 的 sha256 与实际文件匹配；
- [ ] 报告文件内 0 处主机绝对路径（如 `/path/to/...` 这类以根目录开头的路径）；
- [ ] 旧报告差异已在对账节写明（若有）。

---

## 9. 样例

[`case-review.html`](case-review.html) 是同一套 CSS/JS 的**单文件样例**，含 3 个代表性 case：

- `b-goal-t000-c0`：C0 no-op 对照；
- `b-object-t000-g-l0`：注入有效但未恢复；
- `b-goal-t000-g-l0`：注入有效且恢复。

样例页顶部标注 **“样例数据，非实验结论”**；样例不附带视频文件，
因此卡片显示“视频缺失”提示（正式报告把视频放在 `videos/<case_id>.mp4` 即可播放）。

---

## 10. 版本历史

| 版本 | 日期 | 变更 |
|---|---|---|
| `review-report-v1.0` | 2026-11-18 | 首版：白色主题、注入/恢复双审核、sticky 导航、筛选、视频时间点、localStorage 勾选与 JSON 导出、旧报告对账 |

## 11. 已知限制

- 审核勾选依赖浏览器 localStorage，不是数据库；结论以导出 JSON 为准；
- 视频时间点中，注入时刻来自 `summary.json`，恢复/结束为按 step 比例估算；
- 报告是**人工审核台账**，不替代 `evidence.json` 与源 run 的自动判定；
- 单次运行、单 seed/init 的审核报告不构成统计结论。
