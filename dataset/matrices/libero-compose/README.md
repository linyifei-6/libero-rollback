# compose 测试套（D-intact + D-rollback）

> 状态：**base-only / case 定义已构建**（2026-11-21）。
> 维度：**D = compose in-execution rollback**；`D-intact` 是同一批 n=2 组合结构的无撤销基线。
> 数据来源：已构建的 compose 仓 `libero-goal-compose`（76 valid）与 `libero-object-compose`（100 valid）的 **n=2** 定义；不含 n=3/n=4。

## 文件

| 文件 | 行数 | 角色 | 状态 |
|---|---:|---|---|
| [`intact.csv`](intact.csv) | **176** | D-intact：76 goal + 100 object，无撤销 | ✅ 定义已建 |
| [`rollback.csv`](rollback.csv) | **528** | D-rollback：176 结构 × 3 窗口 × `L0` | ✅ 定义已建；runner 未实现 |

`definitions/metadata.jsonl` 是导入的 valid-only 定义快照（176 行），用于可复现构建。

## 规模与口径

- **只取 n=2**：goal 76 个 valid ordered 任务（90 个 ordered 中 14 个 conflict 被排除） + object 100 个 valid ordered 任务 = **176**。
- 不构建 n=3/n=4；旧 `160 = 120 n=2 + 40 n=3` 的口径作废。
- D-intact 每个结构 1 条；D-rollback 每个结构 3 条（`early` / `mid` / `later`），均 `L0`。
- D-rollback 的 `s1` = 该 ordered 任务的第一 goal 原子；`s2` 为第二原子，`s2_must_stay_true=true`。
- 没有矩阵内 C0；目标设计是窗口 synthetic no-op，当前未实现。

## 列

### D-intact（`intact.csv`）

关键列：`case_id,test_suite=compose,dimension=intact,arm=intact,struct_id,source_suite,order,task_id,instruction,goal_atoms,n_atoms,family,level=INTACT,param,semantics=relation_holds_intact,max_steps=600,repair_window=0,expected_relation_after=true,bddl_name,init_source,bddl_sha256,pruned_init_sha256,valid,class`。

- `case_id = compose-intact-<task_id>`。
- `goal_atoms` 用 `|` 连接两个原子。
- `bddl_name = task_id`；实际资产在外部 compose 根目录的 `bddl/<task_id>.bddl` 与 `bddl/<task_id>.pruned_init`。

### D-rollback（`rollback.csv`）

关键列：`case_id,test_suite=compose,dimension=in-execution,arm=rollback,struct_id,source_suite,order,task_id,instruction,window,trigger_criterion,target=s1,revoked_predicate,revoked_object,family,level=L0,param,semantics=relation_then_resume,max_steps=600,repair_window=600,expected_relation_after=false,s2_must_stay_true=true,bddl_name,init_source,bddl_sha256,pruned_init_sha256,valid,class`。

- `case_id = compose-rollback-<task_id>-<window>-l0`。
- `window ∈ {early, mid, later}`；`trigger_criterion` 仍是旧标签（实现必须映射到 GT 事件）。
- `revoked_object` 是 `s1` 谓词的被操物体；joint 的 region 后缀会剥离到 body（例如 `wooden_cabinet_1`）。
- `level=L0`，没有 `L1/L2`；D 的 level 曲线不在本套件。

## 资产与可复现

- BDDL/init 已复制进本仓 `dataset/compose/bddl/`；`COMPOSE_ROOT=dataset/compose`。
- `bddl_sha256` / `pruned_init_sha256` 来自导入的 metadata，可用于资产对账。
- 生成/校验：

```bash
python scripts/build_compose_suite.py          # 重建 intact.csv + rollback.csv
python scripts/build_compose_suite.py --check  # 静态比对
```

## 限制

- 只有 case 定义；**D runner / 窗口触发未实现**，没有 D 执行结果。
- 资产已入仓；静态测试校验矩阵与 352 个 BDDL/init 文件。
- 没有矩阵 C0；窗口 `control_rate` 目前为 `N/A` 或需要 synthetic no-op。
- 14 个 goal conflict ordered 任务被排除；不要把它们算进 D 主表。
- `test_suite` 列用 `compose`（数据集文本的独立性守卫不允许前序仓 token）；显示名见 `docs/d-matrix.md`。
