# 评测 CLI 指导

本文件是 `libero-rollback` 评测入口的参数参考。所有环境相关取值与评测参数均由命令行提供，
代码内不再写死路径或阈值；新增评测维度不需要改动 runner。

- 批量入口（推荐）：`scripts/run_batched_eval.py`
- 逐条入口（兼容保留）：`scripts/run_grid_cases.py`
- 共享参数定义：`scripts/eval_cli_config.py`

## 一、两个入口的区别

| | `run_batched_eval.py` | `run_grid_cases.py` |
| --- | --- | --- |
| 模型加载 | **每次评测一次** | 每条用例一次 |
| baseline | **每个任务一次** | 每条用例一次 |
| 用例执行 | 同任务的用例连续执行 | 每条单独起进程 |
| 适用 | 全量评测 | 单条调试、逐条排查 |
| 独有参数 | — | `--native-preflight`、`--baseline-only` |

批量入口按任务分组：每个任务生成一个 binding（含该任务的全部用例），调用一次
`tools/run_benchmark.py`。因此模型只加载一次、baseline 只跑一次。

## 二、参数总览

### 模型与路径

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--model` | `pi05` | `openvla_oft`、`pi0`、`pi05`、`pi0_fast`、`pi05_lerobot`、`smolvla` |
| `--plus-root` | 同级 `libero-plus` | 兄弟仓库根目录 |
| `--model-python` | 按模型推定 | 能导入该策略的解释器；**不会被解析符号链接**，否则虚拟环境失效 |
| `--checkpoint` | 按模型推定 | 策略权重；OpenPI 系列从缓存解析，OpenVLA 用本地目录 |
| `--video-encoder-python` | openpi 虚拟环境 | 视频编码所用解释器 |
| `--runtime-root` | 批量入口必填 | 评测 overlay，需含 `tools/run_benchmark.py` |

### 运行设置

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--suite` | `LIBERO_10` | 任务套件 |
| `--dimension` | `rollback` | 评测维度 |
| `--max-steps` | `600` | 每 episode 最大步数 |
| `--replan-steps` | `10` | 每多少控制步查询一次策略 |
| `--success-delay` | `0` | 稳定成功窗口：首次成功后追加 K 步验证；0 = 保持旧的即时终止。需要 `success_window` overlay（见下文“稳定成功”） |
| `--success-check-interval` | `1` | 窗口内每 S 步抽查一次谓词；1 = 严格连续 |
| `--cam` | runtime 默认 256 | 相机分辨率；未指定时不传该参数 |
| `--video` | 关 | 录制视频 |
| `--dry-run` | 关 | 只列选用例，不执行 |

### 用例选择（各维度可自由组合）

| 参数 | 取值 | 说明 |
| --- | --- | --- |
| `--cases` | 目录 | 含 `manifest.yaml` 的 catalog，或单个用例目录 |
| `--task` | `00`–`09` | 按任务序号，可重复 |
| `--window` | `early` `mid` `later` `all_done` | 按触发时机 |
| `--severity` | 档位标签 | 按扰动的位置/类型档位 |
| `--mechanism` | 机制名 | 按 `state_change.kind` |
| `--semantics` | 期望语义 | 按 `expected_evaluation_semantics` |
| `--case-id` | 用例 ID | 精确到单条 |
| `--limit` | 整数 | 只取前 N 条，用于冒烟测试 |

空选择表示不筛选；同一参数重复出现取并集。

**可选值取自当前 catalog（288 条；2026-10-16 起 `progress-pulse-*` 已退出，见 `archive/pulse-descoped-20261016/`）**：

时机窗口：

| 窗口 | 用例 |
| --- | ---: |
| `mid` | 149 |
| `later` | 65 |
| `early` | 46 |
| `all_done` | 28 |

档位标签（共 14 种）：

| 档位 | 用例 |
| --- | ---: |
| `d0` | 62 |
| `pose` | 40 |
| `n3` | 34 |
| `n5` | 20 |
| `n8` | 16 |
| `p10` | 16 |
| `p3` | 16 |
| `boundary` | 16 |
| `p5` | 15 |
| `p8` | 13 |
| `r05` | 13 |
| `above` | 12 |
| `reference` | 10 |
| `articulation` | 5 |

机制（共 9 种）：

| 机制 | 用例 |
| --- | ---: |
| `apply_episode_initial_offset` | 143 |
| `restore_episode_initial_pose` | 44 |
| `displace_from_completed_pose` | 40 |
| `restore_native_relation_set` | 18 |
| `displace_to_relation_boundary` | 16 |
| `restore_container_above_pose` | 12 |
| `revert_articulation_goal` | 5 |
| `translate_relation_pair` | 5 |
| `displace_reference_object` | 5 |

期望语义：

| 语义 | 用例 |
| --- | ---: |
| `relation_then_resume` | 234 |
| `relation_only` | 40 |
| `relation_holds_control` | 14 |

### 随机性与可复现

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--seed` | `0` | 单一种子 |
| `--seed-ids` | — | 逗号分隔的多个种子，如 `0,1,2`；自动去重排序 |
| `--seeds` | — | 从 0 开始的种子个数，如 `--seeds 3` 得到 `0,1,2` |
| `--task-seed` | — | 按任务覆盖种子，如 `--task-seed 03=1`；可重复 |

优先级：`--seed-ids` > `--seeds` > `--seed`；`--task-seed` 对该任务再覆盖一次。

**多种子在同一次运行内完成**：种子列表整体传给 benchmark，模型仍只加载一次。

### 结果管理

| 参数 | 说明 |
| --- | --- |
| `--output` | 输出目录；结果、binding、日志、视频都写在这里 |
| `--resume` | 已完成的批次跳过；**未完成的批次仍会重跑**（判定依据是日志中出现完成标记） |
| `--overwrite` | 清除该批次已有结果后重跑 |
| 两者都不传 | 已有结果时报错退出，不会静默覆盖 |

### 扩展

| 参数 | 说明 |
| --- | --- |
| `--forward` | 追加任意 benchmark 参数，如 `--forward=--post-success-window` |
| 直接传未知参数 | 未被 runner 建模的参数会原样转发给 benchmark |

被 runner 自己设置的参数（`--seed-ids`、`--seeds`、`--cam`、`--suite` 等）不会重复转发。

## 三、常用命令

### 全量评测（单模型）

```bash
.venv/bin/python scripts/run_batched_eval.py \
  --model pi05 \
  --cases dataset/current \
  --runtime-root runs/validation-runtime-20261014-v14 \
  --task-seed 03=1 --task-seed 06=1 \
  --max-steps 600 --video \
  --output runs/full-eval-pi05
```

### 多种子（同一次运行覆盖三个种子）

```bash
.venv/bin/python scripts/run_batched_eval.py \
  --model pi05 --cases dataset/current \
  --runtime-root runs/validation-runtime-20261014-v14 \
  --seeds 3 --max-steps 600 --video \
  --output runs/eval-pi05-3seeds
```

### 按时机分批（对应矩阵的验证顺序）

```bash
# 先在 mid 窗口验证机制
.venv/bin/python scripts/run_batched_eval.py \
  --window mid --output runs/eval-mid ...
# 通过后再补其余窗口
.venv/bin/python scripts/run_batched_eval.py \
  --window early --window later --output runs/eval-rest ...
```

### 单维度排查

```bash
# 只看空间边界机制的失效组
--mechanism displace_to_relation_boundary --semantics relation_then_resume

# 只看姿态真值探针
--severity pose --semantics relation_only

# 只看任务 04 的 mid 窗口
--task 04 --window mid
```

### 中断后续跑

```bash
# 加 --resume 即可；已完成的批次跳过，未完成的重跑
.venv/bin/python scripts/run_batched_eval.py --resume ... 
```

### 冒烟测试（不加载模型）

```bash
.venv/bin/python scripts/run_batched_eval.py --dry-run --limit 5 ...
```

### 稳定成功（success-delay）

参考 runtime 不带该参数；先用本仓库脚本把补丁打到一份 overlay 拷贝上，再把 `--runtime-root`
指向它（参考 runtime 不被修改）：

```bash
uv run python scripts/prepare_success_delay_runtime.py \
  --base runs/validation-runtime-20261019-v19 \
  --output runs/validation-runtime-20261020-v20-success-delay
```

```bash
# 稳定成功：首次成功后要求再保持 100 个控制步，每 20 步抽查一次
--runtime-root runs/validation-runtime-20261020-v20-success-delay \
--forward="--success-delay 100 --success-check-interval 20"
```

判据、预算与结果字段见[稳定成功协议](success-delay.md)。

### 转发 runtime 参数

```bash
# 任务成功之后继续观察（用于完成边界组）
--forward=--post-success-window
```

## 四、输出结构

```
<output>/
  batch-summary.json          每任务的用例数、种子、返回码、耗时
  task00/
    binding.yaml              该任务全部用例合并后的 binding
    batch.log                 benchmark 原始输出
    run/                      benchmark 结果、视频、逐条证据
```

`batch-summary.json` 的 `tasks.<NN>` 记录 `cases`、`seeds`、`returncode`、`elapsed_s`、
`per_case_s`，以及 `skipped`（被 `--resume` 跳过时）。

## 五、示例返回码

| 返回码 | 含义 |
| --- | --- |
| `0` | 该批次全部用例成功结束 |
| `2` | 部分用例扰动后未完成任务（**不是执行错误**，是评测结果） |
| `3` | 配对基线失败，扰动 episode 未启动（保护机制，避免把基线失败记成模型未恢复） |

返回码按批次聚合；逐条结论需读取 `run/**/results.json` 或汇总脚本。

## 六、维护约定

1. 环境相关取值与评测参数一律通过命令行提供，不在 runner 内写死。
2. 新增筛选维度时，在 `eval_cli_config.py` 添加选项与判定函数，两个 runner 共用同一判定，
   避免行为分叉。
3. runtime 已有的参数优先用 `--forward` 或直接透传，不重复实现。
4. 修改默认值前先确认它与既有结果的可比性；`--seeds`、`--cam` 等会改变评测条件。
