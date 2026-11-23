# compose 资产（D 套件）

> 状态：**已复制入仓（2026-11-21）**。本目录是 D-intact / D-rollback 的 BDDL 与 sibling init 资产。
> 只包含 n=2、valid 的 176 个组合任务（goal 76 + object 100）；不含 n=3/n=4，也不含 14 个 goal conflict ordered。

## 内容

```text
dataset/compose/bddl/
├── <task_id>.bddl              # 176 个组合 BDDL
└── <task_id>.pruned_init       # 176 个 sibling init（同 task_id）
```

- `task_id` 对应矩阵里的 `struct_id` / `bddl_name`。
- 资产来源：已构建的 compose n=2 套件；每个文件的 `bddl_sha256` / `pruned_init_sha256` 记录在
  the compose definitions metadata snapshot。
- 矩阵里的 `init_source = bddl/<task_id>.pruned_init`，`COMPOSE_ROOT` 指向本目录的父目录
  （即 `dataset/compose`）。
- 14 个 goal conflict ordered 未复制；它们不在 D 主表。

## 校验

```bash
python scripts/build_compose_suite.py --check
python -m pytest tests/test_suite_matrices.py -q
```

静态测试会检查：176 个 BDDL/init 都存在、矩阵 `struct_id` 与文件一一对应、矩阵哈希与文件一致。
