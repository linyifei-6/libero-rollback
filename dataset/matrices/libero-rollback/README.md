# libero-rollback 测试套（B + C）

> 状态：**base-only**（2026-11-21）。本套件只使用原始 LIBERO 任务，不使用 LIBERO-Plus / O2。
> 维度：**B = completion rollback**，**C = in-execution rollback**。A/B/C/D 是分析维度，不是文件名。

## 文件

| 文件 | 行数 | 维度 | 含义 |
|---|---:|---|---|
| [`completion-rollback.csv`](completion-rollback.csv) | 442 | B | 原始 `b-matrix.csv` 的 base 版本；`all_done` 后撤销 |
| [`in-execution-rollback.csv`](in-execution-rollback.csv) | 180 | C | 原始 L10 三窗口撤销；无 `all_done_control` |

## 列约定

两个文件都在原矩阵前增加三列：

| 列 | 值 | 说明 |
|---|---|---|
| `test_suite` | `libero-rollback` | 测试套 |
| `dimension` | `completion` / `in-execution` | 分析维度映射到 B/C |
| `arm` | `rollback` / `control` | B 的 `C0` 为 control；C 全为 rollback |

`case_id` 保留来源 id（`b-...` / `d-l10-...`）用于追溯；文件名和列名不使用 B/C/D。

## 计数

### B（`completion-rollback.csv`，442）

- suite：goal 85 / object 80 / spatial 80 / l10 197
- level：`C0` 40 / `L0` 60 / `L1` 180 / `L2` 162
- `arm`：control 40（C0）/ rollback 402
- 每任务恰好 1 条 `C0`；`C0` 是 `all_done` 时机的 no-op 控制。
- 注入后 `repair_window=600`（协议下限；frozen `b-matrix.csv` 的 300 仅作参考）。

### C（`in-execution-rollback.csv`，180）

- 9 个 L10 多目标任务；`early` 60 / `mid` 60 / `later` 60
- `L0` 27 / `L1` 81 / `L2` 72；**无 C0**
- `t000` 12 条（joint `s1` 无 `L2`）；其余 8 个任务各 21 条
- `all_done_control` 已由 B 的 `C0` 覆盖；C 不重复。
- 注入后 `repair_window=600`。

## 生成 / 校验

```bash
python scripts/build_suite_matrices.py          # 重建
python scripts/build_suite_matrices.py --check  # 静态比对，不写文件
```

生成器只重组冻结行，不新增/改值；C 的行来自 `d-native-matrix.csv` 过滤
`window != all_done_control`。旧 `b-matrix.csv` / `d-native-matrix.csv` 保留为来源与
provenance，不在本套件里重复维护两套事实。

A 基线仍使用上层的 [`a-matrix.csv`](../a-matrix.csv)（40 条），不属于本 rollback 套件。
