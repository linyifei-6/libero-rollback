# pi05 LIBERO-OBJECT 场景内双抓取 100 候选 · v3 · seeds 0/1/2 · 标准模板报告

按 `docs/html-report-prompt.md` v1.2 模板整理（浅色主题、离线 HTML、videos/ 外链、evidence.json 可复算）。

- `index.html`：标准 HTML 报告（五章：实验介绍 / 结果总览 / 视频证据 / 方法与复现 / 逐条结果；附录含模板适配与自检）
- `evidence.json` / `summary.json`：300 episodes 逐条记录与聚合统计
- `videos/`：300 个 episode 原始 mp4（seed0 100 + seeds1,2 200）
- `candidates-v3.json`：100 个候选定义
- `static-validation-v3.json`：静态验证 100/100
- `preflight-v3-pre/post.json`、`preflight-seeds12-pre.json`：运行时通道预检
- `CASE_LIST-v3.md`：100 条 case 列表
- 报告生成脚本：`runs/object-inscene-100-20261023/prep/build_report_template.py`（一条命令重建）
