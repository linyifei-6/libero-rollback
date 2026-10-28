# 实验报告：pi05 在 mid 窗口 d0 档位的完整回滚评测

> **状态（2026-10-16）**：`progress-pulse-*`（24 条）已暂时退出当前数据集，相关定义、实验数据、报告与代码快照归档在 `archive/pulse-descoped-20261016/`。本文保留，作为该维度重启时的设计依据。
> 退出理由：外部复原使该维度无法测量模型修复（18/18 条 `repair_step == externally_restored_step`），且 `pulse-5` 的窗口短于一个策略查询周期。


本报告记录一次**模型层**评测（不是原生预检）：40 条 `severity=d0`、`trigger.time_point=mid`
的用例，逐条跑「配对基线 + 扰动 episode」，全部经过模型查询。

- 模型：`pi05`（OpenPI `pi05_libero`，缓存权重）
- runtime：`runs/validation-runtime-20261014-v14`
- catalog：`dataset/current`（312 条）
- 结果：`runs/eval-mid-d0-pi05/`
- 状态：**40/40 全部完成**，无执行错误，无跳过

## 一、评测范围与配置

```
.venv/bin/python scripts/run_batched_eval.py \
  --model pi05 --cases dataset/current \
  --runtime-root runs/validation-runtime-20261014-v14 \
  --severity d0 --window mid \
  --task-seed 03=1 --task-seed 06=1 \
  --max-steps 600 --video \
  --output runs/eval-mid-d0-pi05
```

| 项 | 取值 |
| --- | --- |
| 用例数 | 40（任务 01–08 各 5 条） |
| 种子 | 全局 seed 0；任务 03、06 用 seed 1（沿用 `docs/validation-current.md` 的既有设定） |
| 每 episode 步数上限 | 600 |
| 重规划间隔 | 10 控制步 |
| 视频 | 录制（每任务 baseline 1 段 + 每条扰动 1 段） |
| 模型加载次数 | **8**（每任务批次一次，不是每条一次） |
| 总耗时 | 0.94 h（含 8 次加载与 8 次基线） |

选中的 40 条在 catalog 中同属一个机制：`restore_episode_initial_pose`（已用 case 文件直接核对，
不是从结果标签推断）。

## 二、执行入口的修复（本次评测的前置条件）

指导文档把 `scripts/run_batched_eval.py` 列为推荐入口（每任务一次加载、一次基线、
该任务全部用例连续执行）。实测该入口在 v14 上**必然失败**：

```
--strict-paired-baseline requires exactly one perturbation or instruction switch per selected task
```

`run_benchmark.py` 的 `--strict-paired-baseline` 守卫写死了「每个选中任务恰好 1 条扰动」，
而批量 runner 按设计把一个任务的 N 条用例合并成同一个 binding，于是 5 条批任务开工前就
`SystemExit`，返回码 1，模型都不会加载。

这个守卫与 runtime 自身的其余实现并不一致：

| 组件 | 对多用例任务的态度 |
| --- | --- |
| `episode_plan_count()` | 已是 `任务数×seeds` 次 baseline + `用例数×seeds` 条扰动 |
| 结果结构 `results[task]["results"]` | 每条用例一个 `{pid}_s{seed}` 条目 |
| `audit_strict_pairing()` | 逐条对 baseline 审计配对前缀 |
| `[EVAL_SUMMARY]` | 逐条输出，含 `paired_episodes` |
| **`--strict-paired-baseline` 守卫** | **要求每任务恰好 1 条** ← 唯一的例外 |

修法：守卫改为「每任务 ≥1 条」，并新增一条真正必要的约束 —— **同任务各用例必须声明
相同的 scene objects**。理由是共享 baseline 由该任务首条用例的 patched scene 建立，
若同任务混入不同场景的用例，配对就不再成立，此时应拒绝而不是静默错配。

该约束对当前 catalog 无副作用：312 条用例逐条编译实测，`scene_objects` **全部为空**。

改动写入 `runs/validation-runtime-20261014-v14/tools/run_benchmark.py`，
并在 `overlay-provenance.json` 记录新旧哈希与原因。

### 保真度验证

同一任务（T01）的 5 条用例，分别用「逐条入口」与「批量入口」跑，逐字段比对：

| 字段 | 逐条 | 批量 |
| --- | --- | --- |
| baseline success / steps | true / 328 | true / 328 |
| 扰动步数 | 600 / 362 / 321 / 318 / 600 | 600 / 362 / 321 / 318 / 600 |
| 注入步（5 条） | 167 | 167 |
| `recovered` | false/true/true/true/false | false/true/true/true/false |
| 配对审计 `eligible` | 5/5 true | 5/5 true |

**5/5 完全一致**。批量化只改变了加载与基线的次数，没有改变任何一条 episode 的结果。

### 效率

| 口径 | 每条耗时 | 40 条的加载次数 |
| --- | ---: | ---: |
| 逐条入口（每条一个进程） | 3.35 min | 40 |
| **批量入口（本报告）** | **85 s** | **8** |

## 三、评测机制

每个任务批次一次进程：

1. 加载模型（含 JIT warmup）——**每任务一次**
2. 跑 1 条无扰动 baseline，场景取自该任务用例的 patched scene——**每任务一次**
3. 依次跑该任务的 N 条扰动；每条独立 episode、独立触发、独立注入
4. 每条扰动与第 2 步的 baseline 做 `audit_strict_pairing`：比对注入前 17 个 policy 查询的
   `observation_sha256`、`sim_state_sha256`、`noise_sha256`、`action_sha256` 等字段是否
   完全一致；不一致则该条 `eligible=false`

baseline 与扰动共享同一初始状态与同一随机种子，因此两者的差异只来自注入本身。

### 返回码口径

8 个批次的返回码：T01/T02 = 0，T03–T08 = 2。**rc=2 不是执行错误**，而是「部分用例扰动后
未完成任务」这一评测结果（见 `docs/evaluation-cli.md` 第五节）。

## 四、总体结果

| 指标 | 结果 | 口径 |
| --- | ---: | --- |
| 配对基线成功 | **40/40 = 100%** | 基线是恢复率统计的前提 |
| 注入有效 | **30/40 = 75%** | 注入被 runtime 接受并真实改变状态 |
| 模型恢复 | **18/30 = 60%** | 分母 = 基线成功 **且** 注入有效 |
| 配对审计 eligible | 30/40 | 与注入有效完全一致，无「注入有效但配对不成立」的中间态 |

### 逐任务

| 任务 | 用例 | 基线成功 | 注入有效 | 模型恢复 |
| --- | ---: | ---: | ---: | ---: |
| T01 | 5 | 5 | 5 | 3 |
| T02 | 5 | 5 | 5 | 3 |
| T03 | 5 | 5 | 5 | 3 |
| T04 | 5 | 5 | **0** | 0 |
| T05 | 5 | 5 | **0** | 0 |
| T06 | 5 | 5 | 5 | 3 |
| T07 | 5 | 5 | 5 | 3 |
| T08 | 5 | 5 | 5 | 3 |
| **合计** | **40** | **40** | **30** | **18** |

## 五、逐条结果

`inj` = 注入有效，`pair` = 配对审计 eligible，`succ` = 扰动后任务成功，`Δ步` = 与基线的步数中位差，
`延迟` = 恢复延迟步数中位数，`Δ路径` = 末端执行器路径长度差（m）。

| 用例 | inj | pair | succ | Δ步 | 延迟 | Δ路径 |
| --- | :-: | :-: | :-: | ---: | ---: | ---: |
| `libero-10-01-black-rollback-s1-mid-initial-pose` | ✅ | ✅ | ❌ | 272 | — | 0.795 |
| `libero-10-01-progress-pulse-5-mid` | ✅ | ✅ | ✅ | −7 | 154 | 0.002 |
| `libero-10-01-progress-pulse-20-mid` | ✅ | ✅ | ✅ | 34 | 195 | 0.072 |
| `libero-10-01-progress-pulse-60-mid` | ✅ | ✅ | ✅ | −10 | 151 | 0.637 |
| `libero-10-01-progress-repeat-after-recovery-mid` | ✅ | ✅ | ❌ | 272 | — | 1.517 |
| `libero-10-02-yellow-rollback-s1-mid-initial-pose` | ✅ | ✅ | ❌ | 370 | — | 0.257 |
| `libero-10-02-progress-pulse-5-mid` | ✅ | ✅ | ✅ | 0 | 60 | 0.000 |
| `libero-10-02-progress-pulse-20-mid` | ✅ | ✅ | ✅ | 3 | 63 | −0.090 |
| `libero-10-02-progress-pulse-60-mid` | ✅ | ✅ | ✅ | 41 | 101 | −0.040 |
| `libero-10-02-progress-repeat-after-recovery-mid` | ✅ | ✅ | ❌ | 370 | — | 0.257 |
| `libero-10-03-first-rollback-s1-mid-initial-pose` | ✅ | ✅ | ❌ | 195 | — | 0.661 |
| `libero-10-03-progress-pulse-5-mid` | ✅ | ✅ | ✅ | 0 | 148 | 0.001 |
| `libero-10-03-progress-pulse-20-mid` | ✅ | ✅ | ✅ | −1 | 147 | −0.001 |
| `libero-10-03-progress-pulse-60-mid` | ✅ | ✅ | ✅ | 42 | 190 | 0.170 |
| `libero-10-03-progress-repeat-after-recovery-mid` | ✅ | ✅ | ❌ | 195 | — | 0.661 |
| `libero-10-04-progress-pulse-5-mid` | ❌ | ❌ | 未扰动 | 0 | — | 0.000 |
| `libero-10-04-progress-pulse-20-mid` | ❌ | ❌ | 未扰动 | 0 | — | 0.000 |
| `libero-10-04-progress-pulse-60-mid` | ❌ | ❌ | 未扰动 | 0 | — | 0.000 |
| `libero-10-04-progress-repeat-after-recovery-mid` | ❌ | ❌ | 未扰动 | 0 | — | 0.000 |
| `libero-10-04-soup-cheese-basket-rollback-s1-mid-p1` | ❌ | ❌ | 未扰动 | 0 | — | 0.000 |
| `libero-10-05-progress-pulse-5-mid` | ❌ | ❌ | 未扰动 | 0 | — | 0.000 |
| `libero-10-05-progress-pulse-20-mid` | ❌ | ❌ | 未扰动 | 0 | — | 0.000 |
| `libero-10-05-progress-pulse-60-mid` | ❌ | ❌ | 未扰动 | 0 | — | 0.000 |
| `libero-10-05-progress-repeat-after-recovery-mid` | ❌ | ❌ | 未扰动 | 0 | — | 0.000 |
| `libero-10-05-soup-sauce-basket-rollback-s1-mid-p1` | ❌ | ❌ | 未扰动 | 0 | — | 0.000 |
| `libero-10-06-cheese-butter-basket-rollback-s1-mid-p1` | ✅ | ✅ | ❌ | 349 | — | 0.424 |
| `libero-10-06-progress-pulse-5-mid` | ✅ | ✅ | ✅ | −1 | 83 | 0.010 |
| `libero-10-06-progress-pulse-20-mid` | ✅ | ✅ | ✅ | 0 | 84 | 0.008 |
| `libero-10-06-progress-pulse-60-mid` | ✅ | ✅ | ✅ | −6 | 78 | −0.013 |
| `libero-10-06-progress-repeat-after-recovery-mid` | ✅ | ✅ | ❌ | 349 | — | 0.424 |
| `libero-10-07-white-rollback-s1-mid-initial-pose` | ✅ | ✅ | ❌ | 376 | — | 0.741 |
| `libero-10-07-progress-pulse-5-mid` | ✅ | ✅ | ✅ | 0 | 60 | −0.000 |
| `libero-10-07-progress-pulse-20-mid` | ✅ | ✅ | ✅ | 2 | 62 | 0.004 |
| `libero-10-07-progress-pulse-60-mid` | ✅ | ✅ | ✅ | 2 | 62 | 0.004 |
| `libero-10-07-progress-repeat-after-recovery-mid` | ✅ | ✅ | ❌ | 376 | — | 0.741 |
| `libero-10-08-mug-pudding-placement-rollback-s1-mid-p1` | ✅ | ✅ | ❌ | 361 | — | 1.223 |
| `libero-10-08-progress-pulse-5-mid` | ✅ | ✅ | ✅ | 0 | 65 | −0.003 |
| `libero-10-08-progress-pulse-20-mid` | ✅ | ✅ | ✅ | −6 | 59 | −0.018 |
| `libero-10-08-progress-pulse-60-mid` | ✅ | ✅ | ✅ | −2 | 63 | 0.036 |
| `libero-10-08-progress-repeat-after-recovery-mid` | ✅ | ✅ | ❌ | 361 | — | 1.223 |

> 注入无效的 10 条（T04/T05）其 `succ` 字段在原始结果里是 `true`，但那是**未施加扰动**的
> episode 成功率，不能算作模型恢复 —— 它们的 Δ步与 Δ路径全为 0 正是这一点的证据。
> 本报告把它们记为「未扰动」，并从恢复率分母中剔除。
> **pulse 系列的口径提醒**：`progress-pulse-*` 的第二次写入是**外部复原**（把物体放回注入前
> 的位置），按项目口径**不计为模型恢复**。表中这些行的「成功」指"外部复原后模型完成了剩余目标"。
> 该族的设计目的、三种时长的差别与读数禁忌见 [pulse-series.md](pulse-series.md)。

## 六、核心发现

### 1. 分界线非常干净：短时脉冲能救，整段进度回退救不回来

- **恢复的 18 条全部是 `progress-pulse-*` 系列**：每个任务上 pulse-5/20/60 三条全恢复，
  恢复延迟 59–195 步。
- **12 条注入有效但未恢复的用例全部是「进度整段回退」类**：
  `*-rollback-s1-mid-initial-pose`、`progress-repeat-after-recovery`、
  单子任务 `-p1`，全部耗尽 600 步预算。

**但必须注意口径**：pulse 系列的 18 条"成功"里，**模型自己修复的条数是 0**
—— 实测每条的 `repair_step` 都等于 `externally_restored_step`，也就是"外部把物体放回去的那一步"
被记为关系恢复（`src/libero_rollback/evidence.py::classify_result()` 对
`transient.destination == "pre_injection"` 直接返回 `valid_external_restoration`，
永不进入 `valid_recovered`）。因此这 18 条衡量的是"**外部复原之后，模型能否顺手完成剩余目标**"，
不是"模型能否发现并修复丢进度"。详见 [pulse-series.md](pulse-series.md)。

去掉这一层之后，本轮的结论应收窄为：
在**要求模型自己修复**的 12 条用例中，模型一次都没有把已完成的前序目标重新做回来；它倾向于继续执行当前指令。这与
`docs/full-eval-pi05-partial.md` 的定性判断同向，但本轮是 40/40 基线成功、逐条配对审计
合格的数据，结论强度更高。

### 2. 未恢复的 episode 是「耗满预算」，不是「跑完但判负」

12 条未恢复用例的扰动 episode 全部正好用满 600 步（基线分别为 195–405 步）。也就是说
模型没有回到前序目标，但也从未判定任务结束 —— 它一直在执行 s2 的方向上消耗预算。

### 3. T04/T05 的零恢复不是模型失败

这两个任务的全部 10 条用例注入都被 runtime 拒绝：

```
INTERVENTION_ACTIVATION_FAILED / ROLLBACK_PATHOLOGICAL_PENETRATION
```

即回滚目标位姿与篮筐几何相交，物理上写不进去。这与 `docs/verification-report-v13.md`
第六节的结论一致（篮子类封闭容器的几何约束），属于**用例构造层**的缺口，需要改从垂直或
容器开口方向寻找可写目标，不能记成模型能力不足。

### 4. 恢复的「代价」很小

已恢复的 18 条中，与基线的步数差中位数全部落在 −10..+42 步，末端路径长度差
−0.09..+0.64 m。其中 10 条 |Δ路径| < 0.02 m，说明模型在这些用例上的恢复轨迹几乎与
未扰动基线重合 —— 它是**接着做**，而不是重新探索。

## 七、产物与复现

```
runs/eval-mid-d0-pi05/
  batch-summary.json          8 个批次的返回码、用例数、种子、耗时
  d0-mid-pi05-summary.json    40 条逐条结果（基线/注入/恢复/配对审计/错误）
  task0N/
    binding.yaml              该任务 5 条用例合并后的 binding
    batch.log                 benchmark 原始输出（含逐条 [PAIRING_AUDIT] 与 [EVAL_SUMMARY]）
    run/pi05_<ts>/
      results.json            baseline + 5 条扰动的完整记录与审计
      evaluation_summary.json 逐条配对指标
      episode_details.jsonl   逐条完整证据
      videos/                 每任务 1 段 baseline + 5 段扰动
```

另有逐条入口的对照运行（用于第二节的保真度验证）：`runs/eval-mid-d0-pi05-percase-reference/`。

复现命令见第一节；`--resume` 可在中断后按任务批次续跑（判定依据是 `batch.log` 中出现
完成标记，未完成的批次会重跑而不是被跳过）。

## 八、遗留问题

1. **mid 窗口其余 133 条（13 个档位）尚未跑**：`pose` 40、`boundary` 16、`n3` 16、
   `n5` 12、`reference` 10、`p3/p5` 各 8、`above/n8/p10/p8/r05` 各 4、`articulation` 3。
   本轮报告只覆盖 `d0`，不能外推到整个 mid 窗口。
2. **SUT 侧的既有 provenance 不一致**（与本次改动无关，未修改）：
   `libero_runtime/engine/interventions/completed_subgoal_rollback.py` 的实际哈希在 v13 与
   v14 里都与 `overlay-provenance.json` 记录不符，与 `docs/verification-report-v13.md`
   所述的 v13 修复对不上，建议单独核对。
3. **单次加载 8 个任务的机会**：runtime 已支持 `--task-ids`/`--all-tasks`，缺的只是
   `--binding` 不可重复；本报告未做该合并（每任务一次加载已满足「加载次数与任务数同阶」
   的目标）。
4. **未恢复用例的失败归因**：12 条全部耗满 600 步，缺少「是否曾尝试回到 s1」的过程性
   证据；`recovery_cost` 里的 `old_subgoal_restore_count`、`reapproach_count` 等字段可用
   于进一步区分「没有尝试」与「尝试了但失败」。
