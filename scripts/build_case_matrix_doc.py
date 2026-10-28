"""Generate the current case matrix from dataset/current."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset" / "current"
OUT = ROOT / "docs" / "case-matrix-current.md"


def load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def relation_text(relations: list[dict[str, Any]]) -> str:
    parts = []
    for relation in relations:
        if "predicate" in relation:
            parts.append(relation["predicate"])
        elif "goal_id" in relation:
            parts.append(relation["goal_id"])
        elif "selection_id" in relation:
            parts.append(relation["selection_id"])
        else:
            parts.append("selection")
    return "<br>".join(str(x) for x in parts)


def target_text(target: dict[str, Any]) -> str:
    state = target.get("state_change", {})
    identity = (
        target.get("predicate")
        or target.get("goal_id")
        or target.get("selection_id")
        or "profile-resolved"
    )
    values = {key: value for key, value in state.items() if key not in {"kind", "velocity"}}
    detail = json.dumps(values, ensure_ascii=False, separators=(",", ":")) if values else ""
    return (
        str(identity)
        + ("<br>" + state.get("kind", "") if state.get("kind") else "")
        + (("<br>" + detail) if detail else "")
    )


def build() -> None:
    manifest = load(DATASET / "manifest.yaml")
    coverage = load(DATASET / "coverage.yaml")
    repo_root = DATASET.resolve().parents[1]
    cases = []
    for entry in manifest["cases"]:
        case = load(repo_root / entry["path"])
        cases.append((entry, case))
    by_task = {index: [] for index in range(10)}
    for entry, case in cases:
        by_task[case["task"]["task_index"]].append((entry, case))
    lines = [
        "# 当前用例矩阵",
        "",
        f"更新日期：{date.today().isoformat()}。本文由 dataset/current/manifest.yaml 生成，当前 catalog 共 {len(cases)} 条定义。每条定义保留原始 dataset_version、来源和状态变化；其中 progress-failure 为未发布候选。定义数不等于物理验证通过数。",
        "",
        "## 读取口径",
        "",
        "任务顺序、任务标识和 canonical BDDL 来自同级 libero-plus 的 LIBERO-10 tasks_info.txt。manifest 的 case_version_policy 为 preserve，因此 catalog 发布版本为 1.0.0，但每条 case 保留其来源版本。任务 09 当前仅保留一个单关系完成边界候选，和多子任务任务分开统计。",
        "",
        "来源集合：two-subtask、rollback-battery、reference-object、progress-failure。progress-failure 为 2026-10-14 新增的候选扩展；候选必须经过外部运行时物理验证后才能计为有效用例。旧来源不因标签相同而合并；source_id 是可追溯键。",
        "2026-10-16 变更：`progress-pulse-*`（24 条，全部来自 progress-failure）已退出当前 catalog，"
        "定义、实验数据与报告归档在 `archive/pulse-descoped-20261016/`。退出原因是该族由评测器"
        "外部复原被撤销的关系，实测 18/18 条 `repair_step` 等于外部复原步，因此无法测量模型自身的修复；"
        "且 `pulse-5` 的窗口（5 控制步）短于一个策略查询周期（`replan_steps=10`）。",
        "",
        "显式 actor 按持久 profile 解析为对应原生目标；selected_relation_actor 按实际完成顺序选择，且注入前必须仍为真。真值不能从历史完成记录推断。",
        "",
        "## 总览",
        "",
        "| 任务 | early | mid | later | all_done | 合计 | 主要机制 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in coverage["tasks"]:
        group = by_task[row["task_index"]]
        windows = Counter(case["trigger"].get("time_point") for _, case in group)
        mechanisms = Counter(case["rollback_target"]["state_change"]["kind"] for _, case in group)
        window_cells = [
            str(windows.get(name, 0)) if windows.get(name, 0) else "—"
            for name in ("early", "mid", "later", "all_done")
        ]
        mechanism_text = (
            ", ".join(f"{key} ({value})" for key, value in sorted(mechanisms.items())) or "—"
        )
        lines.append(
            f"| {row['task_id']} | {' | '.join(window_cells)} | {len(group)} | {mechanism_text} |"
        )
    total_windows = Counter(case["trigger"].get("time_point") for _, case in cases)
    lines += [
        f"| **合计** | **{total_windows.get('early', 0)}** | **{total_windows.get('mid', 0)}** | **{total_windows.get('later', 0)}** | **{total_windows.get('all_done', 0)}** | **{len(cases)}** | — |",
        "",
        "## 逐任务用例",
        "",
    ]
    for row in coverage["tasks"]:
        index = row["task_index"]
        group = sorted(by_task[index], key=lambda item: item[1]["case_id"])
        lines += [
            f"### {row['task_id']} — {row['task_name']}",
            "",
            f"- 来源 BDDL：{row['source_bddl']}",
            f"- 来源定位符：{row['source_task_locator']}",
            f"- 实际运行定位符 / BDDL：{row['runtime_task_locator']} / {row['runtime_bddl']}",
            f"- 场景适用性：{row['scenario_applicability']}",
            f"- 用例数：{len(group)}",
        ]
        if not group:
            lines += ["- 待研究：", "  - " + "<br>".join(row.get("open_questions", [])), ""]
            continue
        lines += [
            "",
            "| case_id | 集合 / 来源 | case 版本 | 窗口 / 事件 / delay | 已完成关系 | rollback 目标与状态变化 | severity | 时间协议 / 评测语义 | 约束 | 待确认 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for entry, case in group:
            source = case["source"]
            collection = Path(entry["path"]).parts[1]
            constraints = "<br>".join(case.get("validity_constraints", []))
            questions = "<br>".join(case.get("open_questions", [])) or "—"
            trigger = case["trigger"]
            timing = f"{trigger.get('time_point', '—')} / {trigger.get('event', '—')} / {trigger.get('delay_steps', 0)}"
            lines.append(
                "| "
                + " | ".join(
                    [
                        case["case_id"],
                        collection + " / " + source["case_source_id"],
                        str(case["dataset_version"]),
                        timing,
                        relation_text(case.get("completed_relations", [])),
                        target_text(case.get("rollback_target", {})),
                        str(case.get("severity", "—")),
                        json.dumps(case.get("transient", {}), ensure_ascii=False)
                        + "<br>"
                        + case["expected_evaluation_semantics"],
                        constraints,
                        questions,
                    ]
                )
                + " |"
            )
        lines.append("")
    lines += [
        "## 失效方向覆盖与缺口",
        "",
        "| 方向 | 当前可执行机制 | 已有任务 | 当前缺口 / 下一步 |",
        "| --- | --- | --- | --- |",
        "| 位置/区域 | apply_episode_initial_offset、restore_episode_initial_pose、restore_container_above_pose、displace_to_relation_boundary | 01–08 | 需要以原生 In/On 边界校准的成对控制用例；初始位姿偏移不等同于目标边界距离 |",
        "| 功能状态 | revert_articulation_goal + functional_boundary | 00 | 需要 Turnon 阈值两侧和安全重复撤销协议 |",
        "| 姿态 | displace_from_completed_pose；roll15/30/45/60、yaw180 真值探针 | 01–08 | 转角不能证明失效；需检查穿透与原生谓词，真值保持的探针单列 |",
        "| 参照物 | displace_reference_object、translate_relation_pair | 04–08（07、04为历史组） | 移动参照物与整对移动对照分别统计，禁止改变当前目标或固定 fixture |",
        "| 持续性/重复失效 | pulse5/20/60 外部复原；repeat-after-recovery 真值保持3步门控 | 01–08 | pulse 不计模型恢复；第二事件未发生则协议不完整；逐任务运行验证尚未齐备 |",
        "| 完成边界 | 原生任务当前成功、关系当前为真、对象释放后撤销单关系 | 00–09 | 历史完成列表不能代替当前真值；成功后须继续至少一次策略查询 |",
        "| 多历史关系 | restore_native_relation_set；完成边界撤销另一目标或两个目标，共18个候选 | 00–08 | free-body重置初始位姿、关节重置初始坐标；原子端点协议不声明连续无碰撞路径；逐目标核验true→false并保护其余目标 |",
        "",
        "## 与运行报告的关系",
        "",
        "报告按明确指定的运行目录关联结果，核对 case 摘要、binding 和执行记录。stale_definition、historical_unverified、incomplete、injection_invalid、对照、探针、外部恢复和模型恢复分别统计。完整扩展范围及验收门槛见 expansion-plan.md；实际验证记录见 matrix-implementation-progress.md。",
        "",
        "生成命令：",
        "",
        "~~~bash",
        "uv run python scripts/build_case_matrix_doc.py",
        "~~~",
        "",
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(cases)} cases)")


if __name__ == "__main__":
    build()
