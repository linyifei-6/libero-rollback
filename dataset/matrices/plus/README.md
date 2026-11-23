# b-matrix-plus.csv

**隔离数据**：这是基于 LIBERO-Plus O2 的回滚矩阵，独立于 `dataset/matrices/b-matrix.csv`。现有 `matrices.py` / `validation.py` / `runner.py` 不会读取本目录；不要把它接进 v2 主表。

- 设计文档：[docs/B-matrix-plus.md](../../../docs/B-matrix-plus.md)
- 上游：`sylvestf/LIBERO-plus` @ `4976dc30028e805ff8094b55501d532c48fec182`
- O2 审计：[experiments/plus-o2-audit/README.md](../../../experiments/plus-o2-audit/README.md)

## 计数

| 量 | 数 |
|---|---:|
| `rollback`（all_done，target-only） | 659 |
| `fresh`（t=0 reset 到同一 O2 state） | 659 |
| `c0`（no-op 控制） | 38 |
| `l0`（回滚到 episode init） | 38 |
| **full 总计** | **1,394** |
| **core 总计** | **446**（185 rollback + 185 fresh + 76 controls） |

按 suite：goal 312 / object 410 / spatial 374 / l10 298。

## 选择子集

```bash
# 第一轮：core
awk -F, 'NR==1 || $3=="core"' b-matrix-plus.csv > b-matrix-plus-core.csv

# 最终：full
cp b-matrix-plus.csv b-matrix-plus-full.csv
```

`c0` / `l0` 的 `split` 都是 `core`，full 运行也包含它们。

## 列

见设计文档 §4。关键列：

- `arm`：`rollback` / `fresh` / `c0` / `l0`
- `split`：`core` / `full`
- `o2_name`：LIBERO-Plus O2 文件名
- `target_obj` / `revoked_predicate`：被撤销的目标与 goal 原子
- `o2_bddl` / `o2_init`：相对 LIBERO-plus 根目录的路径
- `risk_flag`：`support_object` / `large_move` / `unknown_distance`

## 注意

- 37 个 fixture-target O2 case（open drawer / turn on stove）**没有**进本矩阵。
- `target_dist_cm` 为空表示 BDDL 里目标在 `In` 容器中、无法用 `On` 关系算距离，不是缺文件。
- `rollback` 与 `fresh` 必须按 `(suite, bddl_name, o2_name)` 配对。
- 本目录不含代码；接入 runner 需要单独 PR。
