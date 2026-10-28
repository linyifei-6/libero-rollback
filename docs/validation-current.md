# 当前数据集验证记录

> **历史记录（勿按当前 catalog 解读）**：本文记录 当前验证状态 的实验，其中的用例总数（327 条）与逐条数字均为**当时口径**。2026-10-16 起 `progress-pulse-*`（24 条）已退出数据集（理由见 `archive/pulse-descoped-20261016/README.md`），当前 catalog 为 **288 条**。本文的数字未改写，以保证历史结论可追溯；需要当前口径时以 `docs/case-matrix-current.md` 与 `dataset/current/manifest.yaml` 为准。

更新：2026-10-14。本轮实现、静态检查、十任务原生预检及代表性模型验证已结束，状态入口为 [implementation-status.md](implementation-status.md)。本文区分用例定义、静态接受、原生端点预检和 live 模型恢复，不把候选数量写成物理验收数量。

## 定义与静态检查

当前 catalog 1.0.0 共327条，保留每例来源版本。其中205条为已有来源集合，122条 progress-failure（case 1.8.0）为未发布候选。来源集合分开标注，定义重叠也不自动合并。

| 任务 | 定义数 |
| --- | ---: |
| libero_10/00 | 8 |
| libero_10/01 | 46 |
| libero_10/02 | 41 |
| libero_10/03 | 36 |
| libero_10/04 | 42 |
| libero_10/05 | 37 |
| libero_10/06 | 37 |
| libero_10/07 | 42 |
| libero_10/08 | 37 |
| libero_10/09 | 1 |
| 合计 | 327 |

已通过schema、清单文件与SHA-256完整性、静态引用、代码检查及单元测试。最新全量测试911通过、119跳过，ruff及两项CLI校验通过。使用外部Python与冻结v12编译器，327/327绑定接受：`runs/validation-20261014-v12-reference-binding-audit.json`。编译不运行仿真，不证明物理可行性。

## 原生端点预检

全10任务预检运行于冻结`runs/validation-runtime-20261014-v11`，输出`runs/catalog-native-preflight-20261014-v11`。Pi05、600步、task03 seed1，其余seed0。每个任务只运行无扰动baseline，在真实触发状态试写对应任务的全部catalog候选并还原qpos/qvel/ctrl/act/warmstart；不查询模型来恢复每个候选。短暂/重复协议仅检查首次写入，动态关节驱动需要独立live episode。

当前已发现并修复01/02完成事件未启用：持久profile增加`next_subgoal_completed`，overlay复制版本化profile，bridge在加载模型前拒绝未启用事件。v11保留原证据，修复复验使用新v12；全部批次已结束，冻结overlay保持不变。

拒绝可能来自穿透、机器人/受保护物体接触、关系未失效、没有合法边界对或显式目标在该seed/次序尚未完成。它们不等于模型失败，也不能据一个seed推断用例在全部状态均不可能。01/02的实现错误已修复；09仍是本次运行未暴露释放窗口，不能计为模型失败。


### 首轮v11逐任务结果（已结束）

| 任务 | baseline | 真→假端点 | 拒绝 | 未触发 | 保持关系probe | control | 动态待验 | baseline失败 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 00 | 成功 | 3 | 0 | 0 | 0 | 0 | 5 | 0 |
| 01 | 成功 | 30 | 13 | 3 | 0 | 0 | 0 | 0 |
| 02 | 成功 | 28 | 8 | 3 | 2 | 0 | 0 | 0 |
| 03 | 成功 | 21 | 13 | 0 | 1 | 1 | 0 | 0 |
| 04 | 成功 | 32 | 9 | 0 | 1 | 0 | 0 | 0 |
| 05 | 成功 | 27 | 8 | 0 | 1 | 1 | 0 | 0 |
| 06 | 失败 | 0 | 0 | 0 | 0 | 0 | 0 | 37 |
| 07 | 成功 | 29 | 11 | 0 | 1 | 1 | 0 | 0 |
| 08 | 成功 | 30 | 4 | 0 | 1 | 2 | 0 | 0 |
| 09 | 成功 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |

总计200真→假端点、66拒绝、7未触发、7保持关系probe、5control、5动态待验、37 baseline失败；汇总一致性errors为空。01/02完成事件与04/07旧reference绑定需修复后复验。06 seed0未完成cream cheese目标，不能把其37条标为物理拒绝。


### 当前选择的逐任务证据

以整项task profile选择新版证据，不按单条结果好坏择取。00/01/02/03/09来自v12 live批次的基线预检；04/06/07来自v12补充基线；05/08保留v11。所有选定baseline均成功，均为Pi05、600步、录制视频；03和06使用seed1，其余seed0。这些混合运行条件不是单一受控模型比较。

| 任务 | 定义数 | seed | 真→假端点 | 拒绝 | 未触发 | 保持关系probe | control | 动态待验 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| libero_10/00 | 8 | 0 | 3 | 0 | 0 | 0 | 0 | 5 |
| libero_10/01 | 46 | 0 | 31 | 15 | 0 | 0 | 0 | 0 |
| libero_10/02 | 41 | 0 | 29 | 10 | 0 | 2 | 0 | 0 |
| libero_10/03 | 36 | 1 | 21 | 13 | 0 | 1 | 1 | 0 |
| libero_10/04 | 42 | 0 | 33 | 7 | 0 | 1 | 1 | 0 |
| libero_10/05 | 37 | 0 | 27 | 8 | 0 | 1 | 1 | 0 |
| libero_10/06 | 37 | 1 | 25 | 10 | 0 | 1 | 1 | 0 |
| libero_10/07 | 42 | 0 | 30 | 9 | 0 | 1 | 2 | 0 |
| libero_10/08 | 37 | 0 | 30 | 4 | 0 | 1 | 2 | 0 |
| libero_10/09 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |

合计229个真→假端点、76拒绝、1未触发、8保持关系probe、8control、5动态待验。327条均有记录，汇总errors为空。原生预检不执行每条用例的模型恢复，不能称作327条模型测试通过。

76项拒绝分为：47项穿透、10项没有合法原生边界对、9项目标尚未完成、6项受保护接触、3项目标关系没有失效、1项连带改变保护关系。完整case ID、原因和来源见 [选定预检证据](../runs/validation-report-20261014/native-preflight-summary.json)。这些结论只针对本次触发状态与seed，不等于所有状态下均不可能。

旧4条reference-object绑定已全部实际复验：04/07各一条关系失效、一条有效对照。06 seed0失败记录保留，seed1成功后补齐其37条预检。

## Live机制验证

历史本轮v4目录`runs/progress-validation-20261014-v4`已有10条配对测试。其有效性范围不含v12新增的profile修复及完整原生保护检查。

| 任务 / 机制 | v4结果 | 解释 |
| --- | --- | --- |
| 00 functional inside | 有效对照 | native关系保持真 |
| 00 functional outside | 有效回滚、未恢复 | native关系真→假 |
| 01 pulse5 | 外部复原、协议完成 | 不计模型修复 |
| 02 pulse20 | 外部复原、协议完成 | 不计模型修复 |
| 03 repeat-after-recovery | 协议未完成 | 首次真→假，无模型修复，第二事件未发生 |
| 07 boundary inside | 有效对照 | native关系保持真 |
| 07 boundary outside | 有效回滚、未恢复 | native关系真→假 |
| 07 completed roll15 | 穿透拒绝 | 不计模型失败 |
| 08 pair moved | 有效对照 | native关系保持真 |
| 09 completion | 未触发 | baseline成功不代表已释放注入窗口到达 |

v12五条模型测试已结束，运行环境与视频可追溯：

| 任务 / 用例后缀 | 结果 | 证据与限制 |
| --- | --- | --- |
| 00 / both-goals-all-done | 有效回滚、未完全恢复 | 两关系真→假；36次后续query；最终放置真、Turnon假 |
| 01 / both-goals-all-done | 注入拒绝 | 受保护接触；任务最终成功也不能计模型恢复 |
| 02 / both-goals-all-done | 注入拒绝 | 受保护接触 |
| 03 / both-goals-all-done | 有效回滚、未恢复 | 两关系真→假；19次后续query；最终两关系均假 |
| 09 / initial-pose-all-done | 未触发 | baseline成功，释放条件下完成事件仍未出现 |

01/02各三条完成阶段用例已全部实际尝试原生端点写入：各一条initial-pose接受，两条因保护约束拒绝。端点接受的initial-pose本轮未另做完整模型恢复episode。原子重置只证明端点合法，不宣称连续轨迹无碰撞。

### 本轮报告与视频

[交互报告](../runs/validation-report-20261014/index.html)包含327行，选定14个唯一case的模型运行证据（v4和v12共15次尝试，09选择最新一次）：4项有效回滚未恢复、3项有效对照、2项外部复原、3项注入无效、1项未触发、1项旧绑定过期；另外313项没有本轮完整模型episode。v4 repeat-after-recovery保留历史protocol_incomplete观察，但因显式actor绑定更新，在当前报告标记stale_binding，不能计当前协议验收。报告不使用更早历史实验作为当前物理验收。

[视频审计](../runs/validation-report-20261014/video-audit.json)对所选报告证据的28个视频（14 baseline、14 perturbation）逐一核对SHA-256并完整解码，全部通过。每条报告暴露model、seed、步数、runtime hash/path，结果不写入case定义。

### 待确认与后续验证

- 122条新增progress-failure仍为未发布候选；本轮编译/端点检查不足以发布为全部物理验收通过。
- 76个端点拒绝需逐条寻找其他合法状态或调整明确记录的构造参数，不能放松穿透与保护目标规则凑数量。
- 00的5条动态关节驱动尚无逐条live验收；00原子关节重置不能替代动态路径验证。
- 09需确认成功后的释放窗口；不能以baseline成功代替触发证据。
- pulse外部复原不等于模型修复；repeat仍需用最新绑定完成包含第二事件的live协议；姿态/边界端点不证明持续动力学可行。
- 本轮只有14个唯一case的模型episode；327定义的全量模型恢复评测尚未进行。模型能力比较应固定runtime、seed集合和预算后另行运行。

## 复现命令

```bash
uv sync --extra dev
uv run libero-rollback --dataset-root dataset/current validate-dataset
uv run libero-rollback --dataset-root dataset/current check-manifest
uv run pytest
uv run ruff check .

# 模型/仿真环境由外部独立维护
../libero-plus/openpi/.venv/bin/python scripts/compile_catalog.py \
  --runtime-root runs/validation-runtime-20261014-v12 \
  --output runs/validation-20261014-v12-external-binding-audit.json

uv run python scripts/summarize_preflight.py \
  --preflight-dir runs/catalog-native-preflight-20261014-v11 \
  --output runs/catalog-native-preflight-20261014-v11/summary.json
```

```bash
uv run python scripts/build_current_report.py \
  --dataset-root dataset/current \
  --runs-dir runs/progress-validation-20261014-v4 \
  --runs-dir runs/progress-live-20261014-v12 \
  --output runs/validation-report-20261014
../libero-plus/openpi/.venv/bin/python scripts/audit_report_videos.py \
  --report runs/validation-report-20261014
```

原始汇总保留在v11、v12 live及v12 baseline三个输出目录。选定汇总记录每任务summary_file和每条evidence_file，按上方完整profile选择规则复查；不能把三个summary的总数相加。runs是忽略的本地证据，文档链接需要本次工作区中的输出文件。
