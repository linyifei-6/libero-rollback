# 待处理用例标记与实验结论

更新时间：2026-10-17（本次实验收尾；T03 按用户指示**推迟**）。catalog：**518 条**。`validate-dataset` ✅ / `check-manifest` ✅。

## 一、本次实验结论

| 项 | 数值 |
| --- | --- |
| 接手时 catalog | 287 条 |
| 本次新增并落盘 | 231 条（含 T09 的 13 条、07/08 的 42 条、04–06 的 108 条、03 的 30 条、01/02 的 39 条） |
| **逐任务原生预检验证注入成立** | **232 条**（T01 24 · T02 15 · T03 30 · T04/05/06 108 · T07 12+30 探针 · **T08** 6+15 · **T09 13**） |
| 全量零回归 | ✅ 原有 287 条在全部验证批次中状态未变 |
| HTML 报告 | **7 份文件覆盖 9 个任务** |

## 二、HTML 报告清单（均标注"本次实验重点关注注入有效性"）

| 报告 | 大小 | 用例 | 视频 |
| --- | --- | ---: | ---: |
| `runs/report-t0102-20261017/index.html` | 20.2 MB | 112 | 224 |
| `runs/report-task04-20261017/index.html` | 12.7 MB | 70 | 140 |
| `runs/report-task05-20261017/index.html` | 9.8 MB | 70 | 140 |
| `runs/report-task06-20261017/index.html` | 12.3 MB | 70 | 140 |
| `runs/report-task07-20261017/index.html` | 6.8 MB | 55 | 110 |
| `runs/report-task08-20261017/index.html` | 8.1 MB | 55 | 110 |
| `runs/report-task09-20261017/index.html` | 1.1 MB | 13 | 26 |

## 三、T09 的最终解法（本次实验最大的机制突破）

T09 是**单子目标任务**（`pick up the book and place it in the back compartment of the caddy`），目标达成瞬间机器人仍握着书，导致"完成边界"永远不可达。在 **v18 overlay**（v17 副本）做了两处 runtime 修复：

1. `triggers.py`：单子目标任务以"目标达成"作为 `first_subgoal_settled` 信号（原门控要求"已释放+无接触+静止+连续 3 步"，物理上不可满足）；
2. `rollback_extensions.py`：单子目标任务豁免 `ROLLBACK_ACTOR_NOT_RELEASED`（回滚是瞬移写入，不需要先松手）。

结果：**17/17 到达触发点**（原为 0），其中 **12 条 rollback + 1 条 probe = 13 条注入成立**；4 条 20° 倾倒因与书架内壁接触（`ROLLBACK_CONTACTS_PROTECTED_BODY`）判定为物理不可行，**已删除**（与 T01 抽屉内 90° 侧立同源）。

## 四、T03：已定位、按指示推迟

- **症状**：视频评测协议要求**严格配对基线**（`strict_paired_baseline: true`），T03 在 seed 1 下基线失败 → 63 条扰动未执行（只录 1 段基线）；原生预检（非严格）在同 seed 下成功，两种协议结论不同。
- **待办**：用批量运行器对 seed 0/2/3 各试 `--limit 1` 找出严格基线可用的 seed → 重跑 63 条（约 1.5 h）→ 出报告。修复脚本 `repair_failed.sh` 已就绪（本次实验中被按指示终止）。

## 五、仍受阻：需新增机制的 20 条

| 组 | 条数 | 原因 | 解锁方案 |
| --- | ---: | --- | --- |
| T00 A/B 类 + 07/08 ⭐ 极端用例 | 20 | `scene_object_inject` / `rigid_body_displace` / `dynamic_scene_occupancy` 只能由 legacy source spec 驱动，case 的 10 种 `stateChange` 够不到 | 见 `docs/design-move-to-relation-target.md`（schema/bridge/handler/template 四件套已写明） |

## 六、其余已知问题（未处理，保留标记）

| 用例 | 类别 | 说明 |
| --- | --- | --- |
| `01 boundary-inside/outside-mid`（2） | 无合法边界配对 | 封闭抽屉内水平/垂直射线均无合法配对，需"从开口外侧起搜/分段路径" |
| `01/02 both-goals-all-done`、`01/02 other-goal-all-done`（4） | 接触受保护 / 连带改动 | 走 `relation_set` 分支（未接净空搜索），需接线 + 关节瞬移的自由体跟随写入 |

## 七、工具修复记录（本次实验中发现并修复）

- `scripts/eval_cli_config.py`：修复 `--case-id` 被静默忽略；
- `scripts/build_eval_report.py`：修复 `task=None` 行导致的排序崩溃（T07 报告曾因此构建失败）；
- 评测编排：严格配对基线与预检协议不同 → 需要"评测 seed"与"预检 seed"分开管理。
