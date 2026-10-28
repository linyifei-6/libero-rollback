# 稳定成功（success-delay）协议

> 状态：已实现（rollback 侧 overlay 补丁 + bridge/基线脚本接入）。本文固定判定口径与构建方式，避免不同批次对"稳定成功"做不同解释。
>
> **仓库边界**：所有代码与补丁都在 `libero-rollback`。同级 `libero-plus/libero-runtime` 只作为只读参考，评测时使用本仓库脚本生成的、位于 `runs/` 下的 disposable overlay（不受 git 跟踪）。

## 1. 为什么需要

LIBERO 的任务谓词是瞬时的：首次 `check_success()` 为真时 episode 立即结束。这样测到的是
`∃t: P(t)`，无法区分三种情况：

1. 真正完成（动作收敛、目标进入稳定状态）；
2. 路过式命中（轨迹扫过目标区，或接触瞬间让谓词短暂为真）；
3. 完成但不稳定（放置后物体仍在滑、继续动作把目标碰走，或模型自己撤销刚完成的关系）。

hold window 让 episode 在首次成功后继续运行 K 个控制步，并要求谓词在这些步的采样检查点上保持为真。
它**不能**证明模型"知道"任务已完成，只能证明完成状态没有被后续动作破坏。

## 2. 判定定义

- **hit**：`first_success_step`，首次成功步。
- **stable@K**：hit 之后再运行 K 个控制步；在 `first_success_step + S, +2S, …, +K`
  这些检查点上谓词全部为真（`S = --success-check-interval`，默认 1 即严格连续）。最后一个检查点固定为
  `+K`，即使 K 不是 S 的整数倍。
- **unstable**：任一检查点谓词为假，立即终止并记为 `success_unstable`。
- **censored**：窗口未跑完 episode 就被环境/异常终止，不能认证稳定成功，记为
  `success_window_censored`（保守处理，不计入 stable）。
- 窗口内发生外部干预/谓词切换时计数必须清零重算；当前 bridge 对 completion_boundary / all_done
  用例直接拒绝 `--success-delay`，避免与注入窗口混淆。

## 3. 预算

验证尾预算**追加**在 `--max-steps` 之后，不从活跃预算里扣：

- hit 发生在 `s` 步、`delay=K` 时，episode 最多运行到 `s + K`；此前活跃预算仍为 `max_steps`。
- 例：`max_steps=400, delay=100, hit=390` → 窗口为 390→490。
- 窗口失败**不重试**；窗口只验证一次。
- 未 hit 的 episode 行为与 `delay=0` 完全一致。

参数建议：`K` 应取 `replan_steps` 的若干倍。默认 `replan_steps=10` 时 `K=50` 覆盖 5 个重规划周期；
若 `K` 小于一个重规划周期，窗口可能在同一动作块内结束，测到的是开环残余动作而不是模型的新决策。
LIBERO 控制频率 20 Hz，`K=50` 约 2.5 s。

## 4. 构建 overlay（必需）

参考 runtime 没有这个参数；需要通过本仓库脚本把补丁打到一份 overlay 拷贝上：

```bash
uv run python scripts/prepare_success_delay_runtime.py \
  --base runs/validation-runtime-20261019-v19 \
  --output runs/validation-runtime-20261020-v20-success-delay
```

- `--base` 可以是任意包含 `tools/run_benchmark.py` 的评测 overlay（例如 v19 rollback overlay，或
  `runs/libero-std-baseline-20261019/runtime` 这类标准 baseline overlay）；
- 脚本复制 base、给拷贝打 runner 补丁、把 `src/libero_rollback/success_window.py` 复制为
  overlay 根目录的 `success_window.py`，并在 `rollback-capabilities.json` 追加
  `success_window` capability；
- 同时写 `success-delay-provenance.json`（base、runner/module sha256、patch 数）；
- 输出目录必须不存在；参考 runtime 不被修改。

## 5. 用法

单条/批量 bridge（`--runtime-root` 指向刚构建的 overlay）：

```bash
uv run libero-rollback evaluate <case.yaml> ... \
  --runtime-root runs/validation-runtime-20261020-v20-success-delay \
  --success-delay 50 --success-check-interval 10
```

`scripts/run_batched_eval.py` / `run_grid_cases.py` 通过 `--forward` 透传：

```bash
--runtime-root runs/validation-runtime-20261020-v20-success-delay \
--forward="--success-delay 50 --success-check-interval 10"
```

标准 baseline 脚本：

```bash
.venv/bin/python scripts/run_libero90_baseline.py ... \
  --runtime-root runs/validation-runtime-20261020-v20-success-delay \
  --success-delay 50 --success-check-interval 10
```

`--success-delay 0`（默认）与旧行为完全一致；`--success-check-interval` 只在 delay>0 时生效。
bridge 与 `run_libero90_baseline.py` 会在启动前检查 overlay 的 capability；未打补丁的 overlay
会直接报错并提示构建命令，而不是把 `unrecognized arguments` 留给外部 runner。

## 6. 结果字段

`results.json` / `case_result.json` 新增：

| 字段 | 含义 |
| --- | --- |
| `episode_success` / `success` | 稳定成功（开启 delay 时）；未开启时等同旧 success |
| `first_hit_success` | 是否至少 hit 一次（基线资格门槛仍用这一项，避免稳定失败的基线把批次挡掉） |
| `first_hit_step` | 首次成功步；**报告"完成步数"应使用该字段**，不要用 episode 总长 |
| `success_window.status` | `idle / pending / stable / lost` |
| `success_window.checks` | 检查点列表（step、elapsed_steps、kind、success） |
| `success_window.trace` | 逐 step 谓词轨迹（可离线重算任意 K 的 S(K) 曲线） |
| `termination.status` | `success_stable / success_unstable / success_window_censored / success / max_steps / environment_done` |

## 7. 兼容与限制

- 与 `--post-success-window`、PFCR / T0-anchor handoff、instruction switch 互斥；bridge 对
  completion_boundary / all_done 用例直接报错。
- 开启 delay 后 `steps` 包含验证尾，报告中的步数/配对步数差不可与旧结果直接比较；
  必须同时记录 `success_delay` 与 `success_check_interval`（已写入 execution-plan / manifest /
  evaluation-summary）。
- 旧结果没有成功后逐 step 轨迹，无法离线补算，只能重跑。
- 主评测口径只使用 **continue 模式**（成功后策略继续正常出动作）；`hold`（成功后零动作/冻结）
  仅作为对照，当前未实现。
- 补丁基于 runner 源码文本锚点；参考 runtime 或 base overlay 的 runner 结构变化时，构建脚本会以
  `runtime source changed: <anchor>` 失败而不是静默打错位置，需要同步 rebase 补丁。
