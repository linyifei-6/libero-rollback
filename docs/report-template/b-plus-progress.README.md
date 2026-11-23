# B-plus Goal HTML 报告模板

> 模板：[`b-plus-progress.html`](b-plus-progress.html) ｜ 生成器：[`scripts/build_b_plus_report.py`](../../scripts/build_b_plus_report.py) ｜ 样例：[`experiments/b-plus-goal-20261118/index.html`](../../experiments/b-plus-goal-20261118/index.html)

## 用途

把一次 B-plus run 的 `episodes.jsonl` 渲染成**自包含 HTML 进度/结果报告**：

- 白色主题、无 CDN / 无外部字体 / 无网络请求，`file://` 双击即可打开；
- 顶部 KPI：完成数、O2 valid、O2 recovery（Wilson 95% CI）、C0 control、early stopped、视频数；
- Progress by arm、O2 recovery by level（表 + 条形）、recovery by task；
- trigger failure / invalid injection 清单；
- 视频网格（`<video controls preload="metadata">`），可按 level / task / status 过滤；
- 页脚注明生成器与数据来源。

## 生成

```bash
.venv/bin/python scripts/build_b_plus_report.py \
  --run runs/b-plus-goal-core-20261118-v2 \
  --out experiments/b-plus-goal-20261118 \
  --title "B-plus Goal · 回滚模测报告"
```

产物：

```text
<out>/
├── index.html        # 自包含报告
└── provenance.json   # run / 计数 / 生成时间 / 模板路径
```

## 模板占位符

| 占位符 | 含义 |
|---|---|
| `{{TITLE}}` / `{{SUBTITLE}}` | 标题 / 副标题 |
| `{{STATUS_CLASS}}` / `{{STATUS}}` | `ok` / `warn` 与 `COMPLETE · n/N` / `RUNNING · n/N` |
| `{{GENERATED_AT}}` / `{{RUN_DIR}}` | 生成时间 / run 目录 |
| `{{META}}` | `<dt>/<dd>` 运行设置 |
| `{{KPIS}}` | KPI 卡片 |
| `{{ARM_TABLE}}` / `{{LEVEL_TABLE}}` / `{{TASK_TABLE}}` | 三张表 |
| `{{LEVEL_BARS}}` | level 恢复率条形 |
| `{{FAILURES}}` | trigger failure / invalid 清单 |
| `{{VIDEO_COUNT}}` / `{{VIDEO_OPTIONS...}}` / `{{VIDEO_CARDS}}` | 视频区 |
| `{{NOTES}}` | 实现 / 限制 / 下一步 |

## 口径

- Recovery 分母 = `case_valid=true` 且 `level != C0` 的 case；`trigger=False` 记 N/A，不进分母。
- C0 的 `case_valid` 还要求**终局 goal 仍为真**；若 no-op 后目标被碰倒，会记 invalid（当前 t183-c0 就是这种情况）。
- 视频路径是相对 `index.html` 的路径；把报告目录和 `runs/` 一起移动时保持相对位置即可播放。
- 模板只依赖 stdlib；生成器不读仿真、不加载模型，可在 CPU 环境重跑。
