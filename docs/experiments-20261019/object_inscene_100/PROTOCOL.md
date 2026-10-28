# 场景内双抓取（in-scene promoted-target double-grasp）100 候选验证

## 设计
- 沿用 LIBERO-OBJECT 每个任务的原有场景：1 basket + 6 个可操作物体（7 个刚体，qpos/init 不变）。
- 原目标 A 保留；从 5 个干扰物中提升 1 个为第二目标 B，剩 4 个干扰项。
- goal = `(And (In A basket_1_contain_region) (In B basket_1_contain_region))`；
  BDDL 只改 `:language` / `:obj_of_interest` / `:goal`，`:regions/:objects/:fixtures/:init` 原样不动。
- init 状态：直接复制源任务的 `.pruned_init`（50 行，同一场景）。
- 每个 (场景, B) 两个 instruction 顺序变体：`_ab`（A 先）/ `_ba`（B 先）；共 100 候选。

## 静态验证（CPU-only）
`prep/static_validate.py`：BDDL 解析、scene state_len 与 init 宽度一致、seed 行 0/1/2
注入后初始 success=False、两 goal atom 初始为 False、conjunction 可满足性探针
（两个 target 瞬移进 basket contain region → 两 atom 与 check_success 均为 True）。

## 动态验证（pi05, GPU）
- 单一 pi05 checkpoint（OpenPI PyTorch 后端），单卡串行；`MUJOCO_GL=osmesa`。
- 100 candidates × seeds **0,1,2**，`max_steps=600`，`replan_steps=10`，官方 instruction 即候选 `:language`。
- 每个控制步记录 goal atom 真值 trace（first_true_step 用于判断完成了几段）。
- 不录视频（节省时间；需要时可对成功/典型失败样本补录）。
- 每 seed 一个 run：`run/seed{s}/<timestamp>/results.json`，轨迹 `run/seed{s}-traces/`。

## 分析
`prep/analyze_results.py` → `analysis/summary.json` / `summary.md` / `episodes.csv`：
success 率、per-candidate 3-seed 结果、失败时完成子任务数分布、按顺序/场景/B 的聚合。

## 注意
- 顺序变体 `_ab`/`_ba` 的 goal 原子集合相同（And 可交换），差异仅在 instruction 顺序与 `:obj_of_interest` 顺序。
- 不涉及跨任务场景合并/新增槽位/init 重采样；B 均为其他任务原生目标（pi05 原 10 任务 baseline 10/10）。
