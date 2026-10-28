# LIBERO-90 候选任务 pi05 多种子 baseline 扫描（seed 0–4 · 600 步）

这是真实仿真运行记录，用于回答"这批两段候选里，哪些的基线本身能完成"。
它不改变任何数据集版本，也不构成 rollback 用例验证。

- 主扫描：11 个任务 × 5 个初始状态 = 55 episodes，耗时 82.5 min。
- 追加诊断：单段 `close` 任务 2 个 × 5 seeds = 10 episodes，耗时 11.5 min（用于定位失败原因）。

## 结论摘要

| 结论 | 证据 |
| --- | --- |
| **10 条两段候选里只有叠放对（`40`/`41`）有基线成功记录，且成功率很低** | `41` 2/5（seed 0/1）、`40` 1/5（seed 0）；其余 8 条 0/5 |
| **失败模式统一：s1 常能完成并保持，s2 从不完成** | `27`/`28` 的 s1 在 2/5 个 seed 达成并保持到结束，s2（关抽屉）0/5 |
| **`25`/`26`/`27`/`28` 的 s2 不是时机问题，而是策略缺这项技能** | 单段 `close the top drawer`（SCENE10）独立测试 **0/5**；同一策略对 SCENE4 的下层抽屉 **5/5** |
| **叠放对的实际执行顺序与 BDDL 目标顺序相反** | 通过的 episode 里"碗进托盘"先成立（第 98–116 步），"叠放"只在成功瞬间成立 1 步 |
| **单段对照 `17` 5/5 通过** | 均值 379 步；说明运行管线与基线本身没有问题 |
| **运行可复现** | 与 2026-10-11 的 stock runner 运行及本次 seed-3 运行对比 18 个 (任务, seed) 对：sim-state 哈希与结果**全部一致，0 处不符** |

因此：**当前 pi05 + pi05_libero checkpoint 下，没有一条两段候选同时满足"基线可完成 + 干净的两段结构"**。

## 运行协议

| 项 | 值 |
| --- | --- |
| 模型 / 策略配置 | `pi05` / OpenPI `pi05_libero` |
| checkpoint | `/home/tarowang/.cache/openpi/openpi-assets/checkpoints/pi05_libero` |
| 模式 | `baseline`（无扰动注入） |
| suite / 任务 | `LIBERO_90`，11 个 benchmark task_idx（10 条候选 + 对照 `17`） |
| seeds | 0、1、2、3、4（episode seed = s、environment seed = 1000+s、初始状态取 `init_states[s]`，每任务 50 个可选） |
| 步数上限 / 重规划 | 600 / 10 |
| 观测 | 5 个控制步稳定化后取真值观测作为首个策略观测 |
| 视频 / 相机 | 开启，256×256 |
| 硬件与耗时 | RTX 3090；模型加载 + JIT ≈ 55 s；55 episodes 合计 82.5 min |

## 通过矩阵

| 清单 | bench | 指令 | s0 | s1 | s2 | s3 | s4 | 通过 | 通过步数均值 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `00` | 8 | open the top drawer of the cabinet and put the bowl in it | fail | fail | fail | fail | fail | 0/5 | — |
| `05` | 21 | turn on the stove and put the frying pan on it | fail | fail | fail | fail | fail | 0/5 | — |
| `09` | 23 | close the bottom drawer of the cabinet and open the top drawer | fail | fail | fail | fail | fail | 0/5 | — |
| `17` | 38 | put the right moka pot on the stove（单段对照） | **PASS** | **PASS** | **PASS** | **PASS** | **PASS** | **5/5** | 379 |
| `19` | 45 | turn on the stove and put the frying pan on it | fail | fail | fail | fail | fail | 0/5 | — |
| `25` | 1 | close the top drawer of the cabinet and put the black bowl on top of it | fail | fail | fail | fail | fail | 0/5 | — |
| `26` | 4 | put the butter at the front in the top drawer of the cabinet and close it | fail | fail | fail | fail | fail | 0/5 | — |
| `27` | 3 | put the butter at the back in the top drawer of the cabinet and close it | fail | fail | fail | fail | fail | 0/5 | — |
| `28` | 5 | put the chocolate pudding in the top drawer of the cabinet and close it | fail | fail | fail | fail | fail | 0/5 | — |
| `40` | 63 | stack the left bowl on the right bowl and place them in the tray | **PASS** | fail | fail | fail | fail | 1/5 | 453 |
| `41` | 64 | stack the right bowl on the left bowl and place them in the tray | **PASS** | **PASS** | fail | fail | fail | 2/5 | 232 |

## 子任务达成统计（各 seed 计数）

| 清单 | s1 曾为真 | s1 末步仍为真 | s2 曾为真 | 两原子同时为真 |
| --- | --- | --- | --- | --- |
| `00` | 5/5 | 1/5 | 0/5 | 0/5 |
| `05` | 5/5 | 5/5 | 0/5 | 0/5 |
| `09` | 5/5 | 5/5 | 0/5 | 0/5 |
| `17` | 5/5 | 5/5 | 5/5 | 5/5 |
| `19` | 5/5 | 5/5 | 0/5 | 0/5 |
| `25` | 0/5 | 0/5 | 0/5 | 0/5 |
| `26` | 1/5 | 1/5 | 0/5 | 0/5 |
| `27` | 2/5 | 2/5 | 0/5 | 0/5 |
| `28` | 2/5 | 2/5 | 0/5 | 0/5 |
| `40` | 2/5 | 1/5 | 5/5 | 1/5 |
| `41` | 2/5 | 2/5 | 5/5 | 2/5 |

## 逐 seed 明细（关键任务）

只列与"是否存在可用干预窗口"相关的字段；完整表见 `runs/.../seed-detail.md`。

| 清单 | seed | 结果 | 步数 | s1 首真 | s1 末真 | s1 保持步数 | s2 首真 | s2 末真 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `27` | 3 | fail | 600 | 374 | 604 | 231 | — | — |
| `27` | 4 | fail | 600 | 306 | 604 | 299 | — | — |
| `28` | 2 | fail | 600 | 509 | 604 | 96 | — | — |
| `28` | 3 | fail | 600 | 482 | 604 | 123 | — | — |
| `26` | 2 | fail | 600 | 486 | 604 | 119 | — | — |
| `00` | 0 | fail | 600 | 65 | 603 | 539 | — | — |
| `00` | 3 | fail | 600 | 66 | 480 | 415 | — | — |
| `40` | 0 | **PASS** | 453 | 457 | 457 | 1 | 98 | 457 |
| `40` | 1 | fail | 600 | — | — | — | 371 | 604 |
| `40` | 2 | fail | 600 | 94 | 94 | 1 | 259 | 604 |
| `41` | 0 | **PASS** | 240 | 244 | 244 | 1 | 116 | 244 |
| `41` | 1 | **PASS** | 224 | 228 | 228 | 1 | 109 | 228 |
| `41` | 2 | fail | 600 | — | — | — | 126 | 604 |

`40`/`41` 的通过路径是"先把作为底座的碗放进托盘，再把另一只碗叠上去"——与 BDDL 目标顺序
（先 `On` 叠放、后 `In` 入托盘）相反，且叠放关系只在成功瞬间成立一步。
视觉证据见 `runs/libero90-candidates-baseline-pi05-seeds0-4/pi05_20261013_161222/frames/`
（`LIBERO_90_T64_seed0-contact.jpg`、`LIBERO_90_T63_seed0-contact.jpg`）。

## 失败原因定位：单段 `close` 诊断

`27`/`28` 与 `09` 的对照引出一个问题：同样是"关抽屉"，为什么 SCENE4 能关、SCENE10 关不上？
用两条单段任务（同一策略、同一 5 个 seed）单独测试：

| bench | 指令 | 场景 | 结果 | 通过步数 |
| --- | --- | --- | --- | --- |
| 0 | close the top drawer of the cabinet | KITCHEN_SCENE10 | **0/5** | — |
| 22 | close the bottom drawer of the cabinet | KITCHEN_SCENE4 | **5/5** | 238 / 228 / 204 / 219 / 209（均值 220） |

结论：**"关抽屉"这项技能本身存在（SCENE4 下层抽屉 5/5），但在这位策略上对 SCENE10 的上层抽屉完全不成立（0/5）**。
所以 `25`/`26`/`27`/`28` 的 s2 失败不是步数不足、不是 seed 不好、也不是 rollback 设计问题，
而是策略在该场景缺这项技能；增加步数或更换 seed 都不会让它们变成"基线可完成"。

## 与历史运行的对照

| 运行 | 时间 | 覆盖 | 结果 |
| --- | --- | --- | --- |
| `runs/pi05-libero90-baseline-video-600` | 2026-10-11 | seed 0，7 个任务 | T63 通过 453、T64 通过 240，其余失败 |
| `runs/openvla-libero90-baseline-video-600` | 2026-10-11 | seed 0，7 个任务 | 全部失败 |
| `runs/libero90-candidates-baseline-pi05-seed3` | 本次 | seed 3，11 个任务 | 仅 T38（`17`）通过 361 |
| 本扫描 | 本次 | seeds 0–4，11 个任务 | 见上表 |

两次独立运行的 T63/T64 seed 0 通过步数（453 / 240）与失败任务的步数完全一致，
且 `scripts/compare_libero90_runs.py` 核对 18 个重叠 (任务, seed) 对：sim-state 哈希与结果全部一致。
这同时证明**只读目标谓词探针不改变 episode 动力学**（历史运行没有探针）。

## 对 rollback 基础测试集的取舍建议

1. **现在不要把这批候选写成正式用例。** schema 的 `validity_constraints` 要求 `baseline_task_solvable`，
   而 8/10 条候选在 5 个初始状态上 0 通过。
2. **`25`/`26`/`27`/`28` 建议直接排除**（在 pi05 下）。原因是 s2 的技能缺失已被单段诊断定位，
   不是调参能解决的；除非换更强/更匹配的 checkpoint，或把 s2 换成模型能完成的动作。
3. **`40`/`41` 可作为"完成边界型"候选**：基线可完成（但仅 seed 0/1），实际顺序是"托盘 → 叠放"，
   叠放关系瞬时成立。对应的 rollback 场景只能是"任务完成后撤销任一已完成关系"（hold window），
   而不是"s2 执行中回滚 s1"。用例必须固定并记录可用 seed，且要在 `open_questions` 里写明顺序与瞬时性。
4. **`05`/`19` 需要 runtime 先补开关建模**：策略能稳定打开炉子并保持（5/5），阻碍在机制侧；
   这两条与 LIBERO-10 `/00` 是同一问题，可作为同一批工程任务处理。
5. **`00` 是独立的一类现象**：s1（打开抽屉）5/5 曾成立，但只有 1/5 保持到结束——
   策略会自己把已完成的关节关系撤销。这类"自撤销"必须与外部干预分开统计，否则会污染 rollback 指标。
6. **多种子筛选是必需的，不是可选的**：`40`/`41` 只在部分 seed 通过，
   单 seed 筛选会得出相反结论（本次 seed 3 会误判为"叠放对不可用"）。
   建议后续任何候选都按 ≥5 个初始状态筛选，并记录通过 seed 与步数。
7. 若目标是尽快得到可用的 rollback 基础集，**继续使用 LIBERO-10 的已验证任务**（如 `/01`、`/02`）
   比等待 LIBERO-90 候选更稳妥；LIBERO-90 的这 10 条更适合作为"策略能力筛查"的输入。

## 复现

```bash
# 主扫描（55 episodes，约 1.4 h）
../libero-plus/pi0-env/bin/python scripts/run_libero90_baseline.py \
  --runtime-root ../libero-plus/libero-runtime \
  --output runs/libero90-candidates-baseline-pi05-seeds0-4 \
  --trace-dir runs/libero90-candidates-baseline-pi05-seeds0-4/atom-traces \
  --model pi05 --suite LIBERO_90 \
  --task-ids 4,3,5,8,1,23,63,64,21,45,38 \
  --seed-ids 0,1,2,3,4 --max-steps 600 --replan-steps 10 --video

# 汇总（成功率 + 子任务达成统计 + 逐 seed 明细）
python3 scripts/analyze_libero90_baseline.py --run-dir runs/libero90-candidates-baseline-pi05-seeds0-4
python3 scripts/analyze_libero90_seed_detail.py --run-dir runs/libero90-candidates-baseline-pi05-seeds0-4

# 单段 close 诊断（10 episodes，约 12 min）
python3 scripts/prepare_libero90_task_configs.py \
  --runtime-root ../libero-plus/libero-runtime --inventory 30,14
../libero-plus/pi0-env/bin/python scripts/run_libero90_baseline.py \
  --runtime-root ../libero-plus/libero-runtime \
  --output runs/libero90-close-diagnostic-pi05-seeds0-4 \
  --trace-dir runs/libero90-close-diagnostic-pi05-seeds0-4/atom-traces \
  --model pi05 --suite LIBERO_90 --task-ids 0,22 \
  --seed-ids 0,1,2,3,4 --max-steps 600 --replan-steps 10 --video

# 跨运行可复现性核对
python3 scripts/compare_libero90_runs.py \
  --run runs/libero90-candidates-baseline-pi05-seed3 \
  --run runs/pi05-libero90-baseline-video-600 \
  --run runs/libero90-candidates-baseline-pi05-seeds0-4
```

## 产物

- 主扫描：`runs/libero90-candidates-baseline-pi05-seeds0-4/pi05_20261013_161222/`
  （`results.json`、`evaluation_summary.json`、`eval.log`、55 个视频、`frames/`）
- 主扫描汇总：`runs/libero90-candidates-baseline-pi05-seeds0-4/{seed-summary.md,seed-detail.md,baseline-seed-summary.json}`
- 轨迹：`runs/libero90-candidates-baseline-pi05-seeds0-4/atom-traces/*.jsonl`（每控制步一行，文件名含 seed）
- 诊断：`runs/libero90-close-diagnostic-pi05-seeds0-4/`
- 脚本：`scripts/run_libero90_baseline.py`、`scripts/analyze_libero90_baseline.py`、
  `scripts/analyze_libero90_seed_detail.py`、`scripts/compare_libero90_runs.py`、
  `scripts/build_libero90_contact_sheets.py`、`scripts/prepare_libero90_task_configs.py`
- 任务配置（同级 runtime 仓库）：`../libero-plus/libero-runtime/configs/tasks/libero_90/`（13 个 yaml）
