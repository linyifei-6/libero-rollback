# 数据集扩展与验收计划

当前 `dataset/current` catalog 1.0.0 包含 288 条定义：原三个来源集合 190 条（two-subtask 129、rollback-battery 57、reference-object 4），以及来源 `progress-failure-expansion-20261014` 的 98 条未发布候选（case version 1.8.0）。10 个基础任务均有定义；不同来源的定义和验证证据分别标注。具体参数与逐任务表见 [case-matrix-current.md](case-matrix-current.md)，动态实施状态见 [implementation-status.md](implementation-status.md)。

## 已实现的失效方向

| 方向 | 候选数 | 定义与限制 |
| --- | ---: | --- |
| 原生位置边界配对 | 16 | 01–08 各 inside/outside；在实际状态搜索合法水平边界，没有合法位置则拒绝。 |
| 完成位姿探针 | 40 | 01–08 各 roll15/30/45/60、yaw180；角度是构造参数，原生真值决定是否失效。 |
| 恢复后再次失效 | 8 | 01–08 各一条 repeat-after-recovery；第二次撤销必须等关系真实恢复并保持 3 步后才触发。原同族的 pulse5/20/60（24 条）已于 2026-10-16 退出，见 `archive/pulse-descoped-20261016/`。 |
| 参照物/成对移动 | 6 | 05/06/08 各 reference-only 和 pair control；保留其它任务目标。 |
| 完成边界单对象 | 8 | 00/01/02/04/05/06/08/09；所有实际目标成立、对象释放后回到初始位姿并继续运行。 |
| 功能边界配对 | 2 | 00 stove 的原生 Turnon 阈值两侧；阈值读取实际对象定义。 |
| 完成边界其它目标/全部目标 | 18 | 00–08 各撤销另一目标、原子撤销两个目标；关节和自由物体端点分别记录。 |
| 合计 | 98 | 定义数量不是物理验收数量（退出 pulse 24 条后）。 |

原子关系集仅定义状态端点重置，不证明连续无碰撞干预轨迹。Task 03 没有 Turnon 子任务，04/05/06 当前 profile 是两个目标，09 只有一个目标，不能按场景物体数量编造额外子目标。Canonical BDDL 与安装 runtime variant 分开追溯。

## 验证顺序

1. 静态 schema、任务/来源引用、manifest 文件与 SHA-256、全量外部 binding 编译。
2. 在十个任务的真实 baseline 上逐例原生预检，记录 pre/post 真值、release、workspace、穿透、保护关系和状态恢复。未触发、物理拒绝及需动态驱动单独列出。
3. 对新机制进行 live 配对代表测试，验证模型确实看到变更及时间协议完成。预检不能替代模型恢复测试，外部 pulse 复原不能计作模型恢复。
4. 对可修的实现问题修复复验；不能通过放宽碰撞或伪造前置状态提高有效率。存在 episode 依赖的候选保留可解释拒绝。
5. 每份证据携带 case/binding/runtime provenance，报告排除过时绑定与缺失 baseline；模型未恢复与场景无效分别统计。

验证入口：

```bash
uv run libero-rollback --dataset-root dataset/current validate-dataset
uv run libero-rollback --dataset-root dataset/current check-manifest
uv run pytest
uv run ruff check .
uv run python scripts/prepare_validation_runtime.py --output runs/isolated-runtime
/path/to/external-env/bin/python scripts/compile_catalog.py \
  --runtime-root runs/isolated-runtime --output runs/binding-audit.json
uv run python scripts/run_grid_cases.py --model pi05 --task 07 \
  --runtime-root runs/isolated-runtime --cases dataset/current \
  --native-preflight --baseline-only --limit 1 --max-steps 600 --video \
  --output runs/native-preflight
```

最后一条在一份真实 baseline 中预检该 task 的所有定义，`--limit 1` 只避免重复运行 baseline。运行依赖始终位于外部环境。

## 后续扩展规则

先确认原生目标可撤销及可行状态，再扩展 early/mid/later、随机种子和模型；不机械复制无法构造的维度。新增定义需独立来源、模板、schema、binding、能力协商与正负测试。已发布定义的目标、时机、状态变换和约束不可静默改变。当前工作 catalog 保留 1.0.0，历史 case version 保留，新候选 1.8.0 单独标注；正式发布遵循 dataset-card.md 的版本规则。
