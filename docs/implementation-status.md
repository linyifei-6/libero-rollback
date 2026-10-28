# 完整数据集实施与验证状态

最后更新：2026-10-16 17:05（Asia/Singapore）。**上下文恢复只读本文件及当前步骤所需文件**，不重新读取大段会话/日志。每次运行状态变化、阶段完成及上下文压缩前更新。

## 当前 catalog 状态（2026-10-16）

**`progress-pulse-*`（24 条）已退出当前数据集**：该族由评测器**外部复原**被撤销的关系，
实测 18/18 条 `repair_step` 等于 `externally_restored_step`，无法测量模型自身修复；且 `pulse-5`
的窗口（5 控制步）短于一个策略查询周期（`replan_steps=10`）。定义、实验数据（含视频）、
报告与代码快照归档在 `archive/pulse-descoped-20261016/`。

| 项 | 值 |
| --- | --- |
| catalog 用例数 | **288**（原 312，−24 pulse） |
| 来源集合 | two-subtask 129、rollback-battery 57、reference-object 4、progress-failure 98 |
| 任务 00–09 数量 | 8/38/38/33/34/34/34/34/34/1 |
| 窗口分布 | early 46、mid 149、later 65、all_done 28 |
| 机制 | `apply_episode_initial_offset` 143、`restore_episode_initial_pose` 44、`displace_from_completed_pose` 40、`restore_native_relation_set` 18、`displace_to_relation_boundary` 16、`restore_container_above_pose` 12、`revert_articulation_goal` 5、`translate_relation_pair` 5、`displace_reference_object` 5 |
| 保留的时间协议用例 | 8 条 `progress-repeat-after-recovery-mid`（`gate=relation_recovered` + `initial_offset`，靠 transient 机制做第二次撤销） |
| 校验 | `validate-dataset`、`check-manifest` 通过；`dataset/current` 由 `scripts/build_current_catalog.py` 重新生成 |

下文出现的 327 / 312 / 122 等数字是**各自测量当时的口径**，作为历史记录保留，不再代表当前 catalog。

## 目标与约束

完成最新矩阵的LIBERO-10全任务数据集、实现修复、静态/绑定检查及实际验证。用户已授权实现和验证，不重复询问。中文沟通；不创建子代理；保留用户文件及只读同级libero-plus；当前无.git/AGENTS.md。24GB GPU只允许一个Pi05进程，运行/冻结overlay不修改。

## 数据与实现

catalog1.0.0共288定义（2026-10-16 退出 pulse 24 条后；此前为327），原190条版本保留，progress-failure98条为未发布case1.8.0候选。分来源统计，不合并语义。当前任务00–09数量8/38/38/33/34/34/34/34/34/1；集合two-subtask129、rollback-battery57、reference-object4、progress-failure98。

已实现schema/manifest/coverage、逐条矩阵、CLI、可选外部runtime桥、独立overlay、原生预检、原子关系集、边界/姿态/repeat（pulse 已退出，见上）、保护目标/碰撞检查、来源/哈希/覆盖保护、保守证据分类、HTML与视频审计。默认依赖不含仿真/模型。

安装语义00 Turnon+On、01 In+Close drawer、02 In+Close microwave、03两On无Turnon、04/05/06各两placement、07两On、08 mug+pudding On plate、09单book In。canonical09 T256与installedT276分开。不能从物体数编造目标。

## 最近修复及静态检查

- 01/02完成milestone缺失：持久profile启用next_subgoal_completed；overlay复制全部版本profile；bridge模型加载前检查能力。
- 旧4条reference用basket_1/plate_1实体名：bridge按profile精确实体转body角色，未知实体/非body拒绝。不修改原case，旧绑定证据过期。
- 显式actor绑定实际历史目标，泛型actor才依完成次序选择；seed导致尚未完成不能偷偷重绑。
- report每例暴露model/seed/max_steps/mode/runtime hash/path。atomic证据检查身份/全部真→假/最终全部恢复；未触发、外部复原、重复未完成不计模型恢复。
- 最新全pytest已通过：1030收集项，911 passed/119 skipped（显式统计复核：911 passed, 119 skipped in 5.43s）。ruff、validate-dataset、check-manifest通过。
- v12修复后外部编译327/327：runs/validation-20261014-v12-reference-binding-audit.json。轻量Python缺numpy的误用编译0接受文件不计验收。

## 已完成实测

v11全10任务baseline/native-preflight结束，runs/catalog-native-preflight-20261014-v11/summary.json：200 rollback、66 rejected、7 trigger_not_reached、7 relation_preserving_probe、5control、5dynamic、37baseline_failed，errors空。Pi05/600steps/video，03seed1，其余0。06seed0 baseline失败（butter完成而cream cheese未完成）；不能归为用例失败。01/02完成事件与旧reference错误已修复，必须用v12复验。

v4十条live机制：00inside control/outside未恢复；01pulse5与02pulse20外部复原；03repeat首事件后未恢复且第二事件未发生；07inside control/outside未恢复/roll15穿透拒绝；08pair moved control；09completion未触发。目录runs/progress-validation-20261014-v4；v4不含最新原生保护/profile修复。

失败v9/v9b/v10仅故障历史，不计验收。预检只试端点/首次事件，不证明动态驱动、完整temporal协议、连续轨迹或模型恢复。

## 最终状态（本轮已结束，无活动测试）

- v12五条live结束：00/03有效回滚未恢复；01/02注入被保护接触拒绝；09未触发。GPU session86923已结束。
- v12补充04/06/07 baseline/native-preflight全结束，session21101已结束。旧4条reference绑定复验为2rollback+2control。06seed1 baseline成功，25rollback/10reject/1control/1probe；seed0失败记录保留。
- 最终按完整task profile选新版、保留05/08 v11：**327例均有原生预检记录；229rollback、76rejected、8probe、8control、5dynamic待验、1未触发，全部选定baseline成功，errors空**。03/06 seed1，其余0，Pi05/600steps/video；混合runtime条件不能作为受控模型比较。
- 汇总runs/validation-report-20261014/native-preflight-summary.json明确各task来源与seed，不能相加重复summary。
- 报告runs/validation-report-20261014/index.html，共327行；14唯一case有本轮模型证据：4有效回滚未恢复、3control、2external restoration、3invalid、1trigger未达、1stale binding（v4repeat）。313无完整本轮模型episode。15尝试包含09新旧两次；按最新选择。
- 视频audit结束：28/28选定视频SHA/完整解码通过，runs/validation-report-20261014/video-audit.json。
- 最终911 passed/119 skipped（119为not-an-offset-case参数化检查分支）；ruff、validate-dataset、check-manifest及327外部编译通过。最后仅编辑文档，代码未变。
- docs/validation-current.md已完成逐任务新旧统计、live结果、来源/seed/边界/拒绝原因、复现命令。docs/case-matrix-current.md保留完整327定义表。

## 尚待确认（不能误写为通过）

122新增候选未正式发布；76端点拒绝需要后续合法构造校准；5动态关节case需独立live；09释放窗口未触发；repeat新绑定完整协议未验，pulse外部复原不计模型修复。只有14唯一case的模型episode，不是327全量模型恢复评测。实现与本轮验证交付完成，未来扩大物理验收应另起明确批次，不重复运行已完成检查。

恢复时先看本文件，若用户另行要求扩展验证，再读validation-current及指定case/evidence；不重新遍历全部历史日志。

## 接续命令

```bash
# 本轮已完成；以下运行命令仅供复现，新运行必须使用新输出目录，不并行GPU
.venv/bin/python scripts/run_grid_cases.py --model pi05 --runtime-root runs/validation-runtime-20261014-v12 --baseline-only --native-preflight --task-seed 06=1 --max-steps 600 --video --output runs/catalog-native-preflight-20261014-v12 --case-id libero-10-04-soup-cheese-basket-rollback-s1-mid-ref-moved --case-id libero-10-06-progress-both-goals-all-done --case-id libero-10-07-white-mug-left-plate-rollback-s1-mid-ref-moved
.venv/bin/python scripts/summarize_preflight.py --preflight-dir runs/catalog-native-preflight-20261014-v11 --output runs/catalog-native-preflight-20261014-v11/summary.json
.venv/bin/python scripts/build_current_report.py --dataset-root dataset/current --runs-dir runs/progress-validation-20261014-v4 --runs-dir runs/progress-live-20261014-v12 --output runs/validation-report-20261014
../libero-plus/openpi/.venv/bin/python scripts/audit_report_videos.py --report runs/validation-report-20261014
.venv/bin/python -m pytest -o addopts='' -q
.venv/bin/ruff check .
.venv/bin/libero-rollback --dataset-root dataset/current validate-dataset
.venv/bin/libero-rollback --dataset-root dataset/current check-manifest
```

源码入口scripts/runtime_extensions.py、runtime_preflight.py、prepare_validation_runtime.py、run_grid_cases.py、compile_catalog.py、summarize_preflight.py、build_current_report.py；src/libero_rollback/runtime.py、evidence.py。

只解析小型completion/evaluation-summary/summary.json，不倾倒PHASE_PROBE日志；必要时流式取最后一步、native状态及traceback。
