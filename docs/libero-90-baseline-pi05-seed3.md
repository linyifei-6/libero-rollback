# LIBERO-90 候选任务 pi05 baseline 实测（seed 3 · 600 步）

这是真实仿真运行记录：只回答"模型能否独立完成基础任务"，不是 rollback 用例验证，也不改变任何数据集版本。
候选来自 [`libero-90-task-inventory.md`](libero-90-task-inventory.md) 的筛选（10 条"至少两段子任务"任务 + 1 条单段对照）。

## 结论摘要

- 11 个 episode（10 条两段候选 + 对照 `17`），seed 3、600 步上限、pi05：**通过 1/11**。
- 唯一通过的是**单段对照任务 `17`**（"put the right moka pot on the stove"，361 步）——它正是被静态筛选判为"只有一段"的任务，实测中 `(Turnon flat_stove_1)` 在 `:init` 已为真、全程为真，模型只需放壶。静态判断与实测一致。
- **10 条两段候选全部未通过。** 目标谓词轨迹显示失败不是"没动"，而是普遍**卡在 s2**：

| 任务 | s1（已完成段） | s2（执行中段） | 实测 |
| --- | --- | --- | --- |
| `27` `28` | 物体入上层抽屉：第 374 / 482 步成立，保持到结束 | 关抽屉 | s2 从未成立，s1 完成后仍有 230 / 122 步在 s2 区域操作 |
| `05` `19` | 打开炉子：第 89 / 98 步成立，保持到结束 | 煎锅放上炉子 | s2 从未成立 |
| `09` | 关上下层抽屉（初始为开）：第 216 步成立，保持到结束 | 打开上层抽屉 | s2 从未成立 |
| `00` | 打开上层抽屉：第 66 步成立，第 481 步又变假 | 把碗放进抽屉 | s2 从未成立，且 **s1 被策略自己撤销** |
| `40` `41` | 叠放 | 碗进托盘：第 288 / 117 步成立并保持 | 顺序相反：**s1 从未成立**，模型只完成了"进托盘" |
| `25` `26` | — | — | 两个目标谓词全程为假 |

- 因此**没有任何一条两段候选满足 schema 的 `baseline_task_solvable` 有效性约束**
  （见 [`rollback-case.v1.schema.json`](../schemas/rollback-case.v1.schema.json) 的 `validity_constraints`）。
  在这组 seed/步数下，它们不能直接作为 rollback 基础用例。

> 后续 5 种子扫描（seed 0–4）与失败原因诊断见 [`libero-90-baseline-seed-sweep.md`](libero-90-baseline-seed-sweep.md)：seed 3 的结论在多种子下被部分修正（叠放对 `40`/`41` 只在种子 0/1 通过）。

## 运行协议

| 项 | 值 |
| --- | --- |
| 模型 / 策略配置 | `pi05` / OpenPI `pi05_libero` |
| checkpoint | `/home/tarowang/.cache/openpi/openpi-assets/checkpoints/pi05_libero` |
| 模式 | `baseline`（无任何扰动注入） |
| suite / 任务 | `LIBERO_90`，11 个 benchmark task_idx（见下表） |
| seed | 3（episode seed 3、environment seed 1003、初始状态取 `init_states[3]`，每任务 50 个可选状态） |
| 步数上限 / 重规划 | 600 / 10 |
| 观测与稳定化 | 5 个控制步稳定化后取真值观测作为首个策略观测 |
| 相机 / 视频 | 256×256，开启视频录制 |
| 硬件与耗时 | RTX 3090；模型加载 + JIT ≈ 53 s，11 个 episode 合计 792 s，总墙钟 17.9 min |

## 索引映射（本次最容易出错的地方）

`libero.libero.benchmark` 的 LIBERO-90 顺序是**字母序**，与
`bddl_files/libero_90/tasks_info.txt` 的顺序**不同**，所以清单编号不能直接当 `--task-ids` 用。
`configs/tasks/libero_90/*.yaml` 由 [`prepare_libero90_task_configs.py`](../scripts/prepare_libero90_task_configs.py)
从两份源文件解析生成，本次映射为：

| 清单编号 | benchmark idx | 指令 |
| --- | --- | --- |
| `26` | 4 | put the butter at the front in the top drawer of the cabinet and close it |
| `27` | 3 | put the butter at the back in the top drawer of the cabinet and close it |
| `28` | 5 | put the chocolate pudding in the top drawer of the cabinet and close it |
| `00` | 8 | open the top drawer of the cabinet and put the bowl in it |
| `25` | 1 | close the top drawer of the cabinet and put the black bowl on top of it |
| `09` | 23 | close the bottom drawer of the cabinet and open the top drawer |
| `40` | 63 | stack the left bowl on the right bowl and place them in the tray |
| `41` | 64 | stack the right bowl on the left bowl and place them in the tray |
| `05` | 21 | turn on the stove and put the frying pan on it |
| `19` | 45 | turn on the stove and put the frying pan on it |
| `17`（对照） | 38 | put the right moka pot on the stove |

## 结果

`--phase-probe` 在缺少 `configs/task_profiles/libero_90_t*.yaml` 时会被静默忽略，因此本次用只读探针
（[`run_libero90_baseline.py`](../scripts/run_libero90_baseline.py)）在**每个控制步**求值 BDDL `:goal`
的每个原子条件。轨迹步号 = 5 个稳定化步 + 策略步。

| 清单 | bench | 结果 | 步数 | s1 首次为真 | s1 末步仍为真 | s2 曾为真 |
| --- | --- | --- | --- | --- | --- | --- |
| `00` | 8 | 失败 | 600 | 66（第 481 步变假） | 否 | 否 |
| `05` | 21 | 失败 | 600 | 89 | 是 | 否 |
| `09` | 23 | 失败 | 600 | 216 | 是 | 否 |
| `17` | 38 | **通过** | 361 | 365（单段目标） | 是 | 不适用（`Turnon` 初始已真） |
| `19` | 45 | 失败 | 600 | 98 | 是 | 否 |
| `25` | 1 | 失败 | 600 | 从未 | 否 | 否 |
| `26` | 4 | 失败 | 600 | 从未 | 否 | 否 |
| `27` | 3 | 失败 | 600 | 374 | 是 | 否 |
| `28` | 5 | 失败 | 600 | 482 | 是 | 否 |
| `40` | 63 | 失败 | 600 | 从未 | 否 | 是（288 起保持） |
| `41` | 64 | 失败 | 600 | 从未 | 否 | 是（117 起，中途短暂变假） |

单 episode 耗时 57–103 s，失败用例全部跑满 600 步。

### 逐条观察

- **`27` / `28`（P0 结构，与 LIBERO-10 `/01` 同构）**：s1 达成且**稳定保持到结束**，随后长时间停留在 s2
  （关抽屉）却始终未完成。s1 完成到 episode 结束之间的窗口（230 / 122 步）在语义上正是 rollback 期望的
  "s2 执行中"区间，但基线本身不成功。
- **`26`（同场景、只换成前排黄油）**：两个原子全程为假。与 `27` 结构完全相同、只差被放置物体，
  结果却从"s1 达成"变成"完全没动"，说明该场景对初始位姿/物体选择很敏感。
- **`05` / `19`（C 级，含 `Turnon`）**：策略**能打开炉子**并保持到结束，卡在把煎锅放上炉子。
  因此阻碍不是策略能力，而是 runtime 未建模开关类回退机制（与 LIBERO-10 `/00` 同一结论）。
- **`00`（先开抽屉再放碗）**：s1 第 66 步成立，但第 481 步变假——**策略自己把已打开的抽屉又关了回去**。
  这条对"已完成关系保持"的用例设计有直接影响：s1 的失效可能来自策略自身而非外部干预。
- **`09`（关下层抽屉 + 开上层抽屉）**：s1（关节）可达且保持，s2 从未成立。两段都是关节，机制上仍是 A 级候选。
- **`40` / `41`（叠放 + 进托盘）**：模型把**下层碗先放进了托盘**（s2 成立），叠放（s1）从未成立；
  `41` 的 s2 还在第 415 步短暂变假后于第 418 步恢复。顺序与目标顺序相反，不能靠"模型按顺序做两段"来构造时机。
- **`25`（关上层抽屉 + 黑碗放柜顶）**：两个原子全程为假，模型连抽屉都没关上。

## 与既有运行的对照（seed 0）

同一 suite、同一 runner 在 2026-10-11 有过 seed 0 的基线：

| 运行 | 步数 | 结果 |
| --- | --- | --- |
| `runs/pi05-libero90-baseline-video` | 300 | T64（`41`）通过 240 步；其余 6 条失败 |
| `runs/pi05-libero90-baseline-video-600` | 600 | T63（`40`）通过 453 步、T64（`41`）通过 240 步；其余 5 条失败 |
| `runs/openvla-libero90-baseline-video-600` | 600 | 7 条全部失败 |

本次 seed 3 下 `40` / `41` 都失败。结论：**叠放类任务（`40`/`41`）是这批候选里唯一在实测中通过过的两段任务，
但成功率对初始状态高度敏感**；两段候选的整体基线成功率在 seed 3 上为 0/10。

## 对 rollback 基础测试集的取舍建议

1. **先做多种子基线筛选再写用例。** 单个 seed 的结论不足以支撑任务取舍（`40`/`41` 在 seed 0 通过、seed 3 不通过）。
   建议对候选统一跑 5 个初始状态并记录成功率，把结果写进候选的 `baseline_task_solvable` 依据。
2. **`26`/`27`/`28` 仍是结构最合适的一组**（放置 + 关节关闭，与已验证的 LIBERO-10 `/01` 同构），
   但当前 pi05 在 LIBERO-90 场景里完不成"关上层抽屉"。要么提高步数/换适配器把基线做实，
   要么把 s2 换成模型确实能完成的动作后重新评估。
3. **`40`/`41` 是唯一有实测通过记录的两段候选**，可作为 B 级候选，但必须固定并记录能通过的初始状态，
   且 s1 与 s2 的完成顺序与目标顺序相反（先入托盘、后叠放），用例时机要按实测顺序定义。
4. **`05`/`19` 的开关段值得补建模**：策略能打开炉子（s1 可达且保持），阻碍在 runtime 侧；
   补上开关回退后才有资格进入候选。
5. **`00` 暴露了一个新场景**："已完成的关节关系被策略自己撤销"（第 481 步），
   与"外部干预撤销"需要分开统计，否则会把自撤销算成有效 rollback。
6. 在上述基线成功率问题解决前，不建议把 LIBERO-90 的两段候选升级为正式用例；
   已有的 LIBERO-10 基础集（基线可完成）仍是更稳的起点。

## 复现

```bash
# 1) 生成 LIBERO-90 任务配置（写入 libero-runtime 的 configs/tasks/libero_90/）
python3 scripts/prepare_libero90_task_configs.py \
  --runtime-root ../libero-plus/libero-runtime --include-control

# 2) 跑 baseline（pi05 / 600 步 / seed 3 / 视频 + 目标谓词探针）
../libero-plus/pi0-env/bin/python scripts/run_libero90_baseline.py \
  --runtime-root ../libero-plus/libero-runtime \
  --output runs/libero90-candidates-baseline-pi05-seed3 \
  --trace-dir runs/libero90-candidates-baseline-pi05-seed3/atom-traces \
  --model pi05 --suite LIBERO_90 \
  --task-ids 4,3,5,8,1,23,63,64,21,45,38 \
  --seed-ids 3 --max-steps 600 --replan-steps 10 --video

# 3) 汇总成功率与目标谓词轨迹
python3 scripts/analyze_libero90_baseline.py \
  --run-dir runs/libero90-candidates-baseline-pi05-seed3
```

驱动脚本调用的是同一份 `tools/run_benchmark.py` 的 `main()`，只额外包装了 `OffScreenRenderEnv.step`
用于只读求值目标谓词，不改变动作与动力学；`results.json`、`evaluation_summary.json`、视频格式与标准运行一致。

## 产物

- 运行目录：`runs/libero90-candidates-baseline-pi05-seed3/pi05_20261013_154019/`
  （`results.json`、`evaluation_summary.json`、`eval.log`、`videos/` 11 个 mp4、`frames/` 三张 contact sheet）
- 轨迹：`runs/libero90-candidates-baseline-pi05-seed3/atom-traces/*.jsonl`（每控制步一行）
- 汇总：`runs/libero90-candidates-baseline-pi05-seed3/baseline-atom-summary.json`
- 脚本：`scripts/prepare_libero90_task_configs.py`、`scripts/run_libero90_baseline.py`、`scripts/analyze_libero90_baseline.py`
- 任务配置（写入同级 runtime 仓库）：`../libero-plus/libero-runtime/configs/tasks/libero_90/`（11 个 yaml）
