# pi05 LIBERO-OBJECT 场景内双抓取 100 候选 · v3（LIBERO-10 模板指令）· seeds 0/1/2 + 视频

- `index.html`：标准浅色 HTML 报告（300 条视频证据，evidence.json 可复算）
- `evidence.json` / `summary.json`：逐 episode 记录 + 聚合统计
- `videos/`：300 个 episode 原始 mp4（seed0 100 + seeds1,2 200）
- `candidates-v3.json`：100 个候选定义（含 v1/v2/v3 指令）
- `static-validation-v3.json`：静态验证 100/100
- `preflight-v3-pre/post.json`、`preflight-seeds12-pre.json`：运行时通道预检（seed0 与 seeds1,2 的 init 行 0/1/2 均验证）
- `CASE_LIST-v3.md`：100 条 case 列表
- 指令模板：`put both the <A> and the <B> in the basket` / `put both the <B> and the <A> in the basket`（LIBERO-10 task 0/1/7/8 官方措辞）
