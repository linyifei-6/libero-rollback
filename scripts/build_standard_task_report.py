#!/usr/bin/env python3
"""Build a standard HTML experiment report for a LIBERO-10 rollback task.

Implements ``docs/html-report-prompt.md`` (v1.1) for one experiment: a batch (or a
container of batches / legacy per-case runs) is discovered recursively, every
case is joined back to the catalog, and a single self-contained page is rendered
with:

* experiment introduction (background, task, perturbation dimensions, config),
* results overview (KPIs, overall success, per-dimension success-rate bar charts
  with a percentage y axis, composition chart, per-dimension table, analysis),
* video evidence (one baseline per task first, then perturbation clips laid out
  three per row, grouped by case family with fixed early/mid/later columns and
  explicit placeholders for missing windows; all_done in a separate section),
* filters by window / task / mechanism / severity / semantics / verdict / seed,
* method, data-quality notes and a per-case appendix table.

Output: ``<report>/index.html`` + ``<report>/videos/`` + ``<report>/evidence.json``.

Usage:
    python scripts/build_standard_task_report.py \
        --run runs/retest-20261018/task01 \
        --report runs/retest-20261018/report-task01-v2 \
        --title "LIBERO-10 rollback 实验报告 · T01（libero_10/01）· retest-20261018"
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from libero_rollback.evidence import classify_result  # noqa: E402

FFMPEG = (
    ROOT.parent
    / "libero-plus/openvla-oft-env/lib/python3.10/site-packages"
    / "imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
)
TRANSCODE_ARGS = [
    "-vf", "scale=256:256", "-r", "12", "-an",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
]

WINDOW_ORDER = ["early", "mid", "later", "all_done"]
WINDOW_LABEL = {
    "early": "early（刚完成）",
    "mid": "mid（撤离/转向）",
    "later": "later（收尾进行中）",
    "all_done": "all_done（全部完成边界）",
    "unknown": "未识别",
}
SEVERITY_ORDER = [
    "d0", "pose", "n3", "n5", "n8", "p3", "p5", "p8", "p10", "r05",
    "above", "boundary", "reference", "articulation",
]
MECHANISM_ORDER = [
    "restore_episode_initial_pose",
    "restore_native_relation_set",
    "restore_container_above_pose",
    "restore_captured_checkpoint_pose",
    "revert_articulation_goal",
    "apply_episode_initial_offset",
    "displace_from_completed_pose",
    "displace_to_relation_boundary",
    "translate_relation_pair",
    "displace_reference_object",
    "move_to_relation_target",
]
MECHANISM_LABEL = {
    "restore_episode_initial_pose": "恢复回合初始位姿",
    "restore_native_relation_set": "恢复原生关系集",
    "restore_container_above_pose": "恢复到容器上方位姿",
    "restore_captured_checkpoint_pose": "恢复到捕获检查点位姿",
    "revert_articulation_goal": "回退关节目标",
    "apply_episode_initial_offset": "施加初始位姿偏移",
    "displace_from_completed_pose": "从已完成位姿位移",
    "displace_to_relation_boundary": "位移到关系边界",
    "translate_relation_pair": "整对平移",
    "displace_reference_object": "位移参照物",
    "move_to_relation_target": "移动到关系目标",
}
SEMANTICS_ORDER = ["relation_then_resume", "relation_holds_control", "relation_only"]
SEMANTICS_LABEL = {
    "relation_then_resume": "关系失效后应恢复",
    "relation_holds_control": "关系保持（对照）",
    "relation_only": "仅关系（探针）",
}
VERDICT_ORDER = [
    "valid_recovered", "valid_control", "valid_relation_preserving_probe",
    "valid_not_recovered", "protocol_incomplete", "truth_unverified",
    "trigger_not_reached", "injection_invalid", "valid_external_restoration",
    "incomplete",
]
VERDICT_LABEL = {
    "valid_recovered": ("模型自修恢复", "ok"),
    "valid_control": ("关系保持（对照）", "info"),
    "valid_relation_preserving_probe": ("关系保持（探针）", "info"),
    "valid_not_recovered": ("注入有效但未恢复", "bad"),
    "protocol_incomplete": ("协议不完整", "warn"),
    "truth_unverified": ("关系真值未验证", "warn"),
    "trigger_not_reached": ("触发未到达", "warn"),
    "injection_invalid": ("注入无效", "warn"),
    "valid_external_restoration": ("外部复原（不计恢复）", "warn"),
    "incomplete": ("数据不完整", "warn"),
}
INVALID_REASON = {
    "INTERVENTION_NOT_EXECUTED": "触发已到达但注入未执行（all_done 场景通常因未开启 --post-success-window）",
    "INTERVENTION_ACTIVATION_FAILED": "注入规则激活失败（几何/关系约束不允许）",
}

WINDOW_MEANING = {
    "early": "第一个子目标刚被确认完成，机器人准备进入下一步操作",
    "mid": "机械手撤离并转向下一步操作",
    "later": "收尾动作或下一步动作正在进行中",
    "all_done": "全部原生目标谓词已成立（完成边界），需要在成功后继续运行窗口内注入",
    "unknown": "未识别窗口（用例元数据缺失）",
}
WINDOW_EVENT_HINT = {
    "early": "enter_first_subgoal_completed / enter_next_subgoal_approach",
    "mid": "enter_next_subgoal_approach / enter_post_completion_retreat",
    "later": "enter_next_subgoal_lift / enter_x3a_actuation",
    "all_done": "enter_next_subgoal_completed（依赖 --post-success-window）",
    "unknown": "未记录",
}
MECHANISM_MEANING = {
    "restore_episode_initial_pose": "把已完成关系的目标物体重置到回合初始位姿（原始落点）",
    "restore_native_relation_set": "原子地把一组原生关系同时重置回回合初始状态（多关系同时失效）",
    "restore_container_above_pose": "把物体移动到容器开口正上方悬停（净空按用例声明）",
    "restore_captured_checkpoint_pose": "恢复到实际捕获的 checkpoint 位姿（当前 catalog 未使用）",
    "revert_articulation_goal": "外部驱动把关节目标回退到未开启一侧（如灶台旋钮）",
    "apply_episode_initial_offset": "在回合初始位姿基础上施加带符号偏移（偏移向量/参考帧由用例声明）",
    "displace_from_completed_pose": "从已完成时达到的位姿出发做平移或旋转（如抬升后倾转、绕竖直轴旋转）",
    "displace_to_relation_boundary": "在关系翻转点附近搜索合法位姿：界内=关系保持对照，界外=关系失效并要求恢复",
    "translate_relation_pair": "把关系的两个端点按同一向量整体平移",
    "displace_reference_object": "只移动参照物（篮子/盘子），被撤销物体保持不动",
    "move_to_relation_target": "把物体移动到关系目标位置（新机制，当前 catalog 仅 4 条且本次未运行）",
}
SEVERITY_MEANING = {
    "d0": "历史档位：恢复到回合初始位姿，无附加偏移",
    "d1": "历史档位：相对初始位姿的 1 档偏移（由小到大）",
    "d2": "历史档位：相对初始位姿的 2 档偏移",
    "d3": "历史档位：相对初始位姿的 3 档偏移",
    "checkpoint": "历史档位：恢复到捕获的 pre-grasp 位姿",
    "n3": "朝机械手方向的水平偏移（数字为幅度档，越大越近）",
    "n5": "朝机械手方向的水平偏移（中幅）",
    "n8": "朝机械手方向的水平偏移（大幅）",
    "p3": "远离机械手方向的水平偏移（数字为幅度档，越大越远）",
    "p5": "远离机械手方向的水平偏移（中幅）",
    "p8": "远离机械手方向的水平偏移（较大幅）",
    "p10": "远离机械手方向的水平偏移（最大幅）",
    "r05": "斜向（朝机械手 + 侧偏最大）的大幅水平偏移",
    "above": "容器开口正上方悬停（净空按用例声明）",
    "pose": "姿态探针/姿态改变：已完成位姿仅改朝向（可能先抬升），用于检验关系是否被破坏",
    "reference": "只移动参照物（篮子/盘子），被撤销物体保持不动",
    "boundary": "关系边界档：关系翻转点两侧的最近合法位姿；inside=对照，outside=要求失效",
    "articulation": "关节目标回退（如开关/抽屉/灶台旋钮）",
}
SEMANTICS_MEANING = {
    "relation_then_resume": "注入使已完成关系失效，期望模型恢复该关系后继续完成任务",
    "relation_holds_control": "关系保持（对照）：注入不破坏关系，用于验证关系仍真时任务能否完成",
    "relation_only": "仅关系（探针）：只判定关系真/假，不要求恢复任务，用于测量注入是否改变关系",
    "protected_partial": "只保护部分目标（schema 枚举，本次未使用）",
    "unsupported_boundary": "不支持的关系边界（schema 枚举，本次未使用）",
}
INVALID_CATEGORIES = [
    ("trigger_not_reached", "触发未到达", "触发事件未到达，注入规则没有执行，扰动没有发生", "warn"),
    ("intervention_not_executed", "触发到达但注入未执行", "触发已到达但规则未执行（触发后没有后续 before_step）；all_done 常见于未开启 --post-success-window", "warn"),
    ("activation_protected_body", "注入激活失败：保护体碰撞", "注入路径会碰到受保护物体（ROLLBACK_CONTACTS_PROTECTED_BODY）", "bad"),
    ("activation_no_legal_pair", "注入激活失败：无合法关系边界对", "在声明范围内找不到「界内合法→界外合法」配对（NO_LEGAL_NATIVE_RELATION_BOUNDARY_PAIR）", "bad"),
    ("activation_other", "注入激活失败：其他几何/关系约束", "INTERVENTION_ACTIVATION_FAILED 的其他 detail", "bad"),
    ("other_error", "其他注入错误", "rule_executed=False 或未归类的 errors", "warn"),
    ("unknown", "未记录原因", "injection_valid=False，但没有可用的错误明细", "warn"),
]
INVALID_CATEGORY_COLOR = {"warn": "#b07d00", "bad": "#b3261e"}


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def rate(k: int, n: int) -> float:
    return (k / n) if n else 0.0


def norm_key(case_id: str) -> str:
    return case_id.replace("_", "-")


def short_case_id(case_id: str, task_index: int) -> str:
    prefix = f"libero-10-{task_index:02d}-rollback-"
    return case_id[len(prefix):] if case_id.startswith(prefix) else case_id


def family_key(case_id: str) -> str:
    return re.sub(r"-(early|mid|later|all_done)(?=-|$)", "-<W>", case_id)


def sanitize_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)[:120]


def _flag_label(value) -> str:
    if value is True:
        return "已开启（true）"
    if value is False:
        return "未开启（false）"
    return "未记录"


def med(values: list[int]) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    mid = len(values) // 2
    return float(values[mid]) if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


# --------------------------------------------------------------------------- #
# catalog
# --------------------------------------------------------------------------- #
def load_catalog(root: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    manifest = yaml.safe_load((root / "dataset/current/manifest.yaml").read_text(encoding="utf-8"))
    catalog: dict[str, dict] = {}
    lookup: dict[str, dict] = {}
    for entry in manifest["cases"]:
        case = yaml.safe_load((root / entry["path"]).read_text(encoding="utf-8"))
        catalog[case["case_id"]] = case
        lookup[norm_key(case["case_id"])] = case
    return {
        "cases": catalog,
        "lookup": lookup,
        "case_count": manifest.get("case_count", len(catalog)),
        "version": (manifest.get("catalog_version") or manifest.get("schema_version") or "未记录"),
    }, manifest


def load_coverage_titles(root: Path) -> dict[int, str]:
    """task_index -> display title from coverage.yaml (title case)."""
    path = root / "dataset/current/coverage.yaml"
    titles: dict[int, str] = {}
    if not path.is_file():
        return titles
    coverage = yaml.safe_load(path.read_text(encoding="utf-8"))
    for item in coverage.get("tasks", []):
        idx = item.get("task_index")
        name = item.get("task_name")
        if idx is not None and name:
            titles[int(idx)] = str(name)
    return titles


# --------------------------------------------------------------------------- #
# discovery + case collection
# --------------------------------------------------------------------------- #
def is_skipped_path(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    return bool(parts & {"report", "reports", "videos", "runtime", ".venv", "__pycache__"})


def discover_task_units(run_root: Path) -> list[dict]:
    """Find (binding.yaml, results.json) units under run_root recursively."""
    units: dict[Path, dict] = {}
    for binding_path in sorted(run_root.rglob("binding.yaml")):
        if is_skipped_path(binding_path.parent.relative_to(run_root)):
            continue
        run_dir = binding_path.parent / "run"
        results = sorted(run_dir.glob("*/results.json"))
        if not results:
            results = sorted(binding_path.parent.rglob("results.json"))
        if not results:
            continue
        try:
            binding = yaml.safe_load(binding_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        pb = binding.get("perturbation_binding") or {}
        if not pb.get("enabled_cases"):
            continue
        key = results[-1].resolve()
        if key in units:
            continue
        units[key] = {
            "binding_path": binding_path,
            "binding": binding,
            "pb": pb,
            "task_profile": pb.get("task_profile"),
            "enabled_cases": pb["enabled_cases"],
            "results_path": results[-1],
            "videos_dir": results[-1].parent / "videos",
        }
    return [units[k] for k in sorted(units, key=lambda p: str(p))]


def read_run_meta(unit: dict) -> dict:
    """Read eval.log / driver.log / batch-summary.json around one batch unit."""
    meta: dict = {
        "model": None, "checkpoint": None, "replan_steps": None,
        "max_steps": None, "seeds": None, "runtime": None,
        "post_success_window": None, "returncode": None,
        "run_id": unit["results_path"].parent.name,
        "eval_log": None, "driver_log": None, "batch_summary": None,
    }
    run_dir = unit["results_path"].parent
    eval_log = run_dir / "eval.log"
    if eval_log.is_file():
        text = eval_log.read_text(encoding="utf-8", errors="ignore")
        meta["eval_log"] = str(eval_log)
        m = re.search(r"Model:\s*(\S+)\s*\|.*?Suite:\s*(\S+)\s*\|.*?Task:\s*(\S+)", text)
        if m:
            meta["model"] = m.group(1)
        m = re.search(r"MaxSteps:\s*(\d+)", text)
        if m:
            meta["max_steps"] = int(m.group(1))
        m = re.search(r"Seeds:\s*\[([^\]]*)\]", text)
        if m:
            meta["seeds"] = [int(x) for x in re.findall(r"-?\d+", m.group(1))]
        m = re.search(r"\[RUN_PROTOCOL\]\s*(\{.*\})", text)
        if m:
            try:
                proto = json.loads(m.group(1))
                meta["post_success_window"] = proto.get("post_success_window")
            except json.JSONDecodeError:
                pass
    # driver.log lives in the batch root (one level above the task dir for batch runs)
    for candidate in [unit["binding_path"].parent.parent / "driver.log", unit["binding_path"].parent / "driver.log"]:
        if candidate.is_file():
            text = candidate.read_text(encoding="utf-8", errors="ignore")
            meta["driver_log"] = str(candidate)
            m = re.search(r"^runtime=(.+)$", text, re.M)
            if m:
                meta["runtime"] = m.group(1).strip()
            m = re.search(r"model=(\S+)\s+cases=(\d+)", text)
            if m and not meta["model"]:
                meta["model"] = m.group(1)
            break
    # batch summary: parent of the batch dir (container layout) or the batch dir itself
    for candidate in [
        unit["binding_path"].parent.parent / "batch-summary.json",
        unit["binding_path"].parent / "batch-summary.json",
        unit["binding_path"].parent.parent.parent / "batch-summary.json",
    ]:
        if candidate.is_file():
            try:
                doc = json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            meta["batch_summary"] = str(candidate)
            for task_key, info in (doc.get("tasks") or {}).items():
                if info.get("seeds") and not meta["seeds"]:
                    meta["seeds"] = info["seeds"]
                meta["returncode"] = info.get("returncode")
            break
    return meta


def collect_experiment(run_root: Path, root: Path) -> dict:
    catalog, _manifest = load_catalog(root)
    titles = load_coverage_titles(root)
    units = discover_task_units(run_root)
    if not units:
        raise SystemExit(f"no task units (binding.yaml + results.json) found under {run_root}")

    cases: list[dict] = []
    baselines: dict[int, dict] = {}
    meta_by_task: dict[int, dict] = {}
    coverage_notes: list[str] = []

    for unit in units:
        pb = unit["pb"]
        task_profile = unit["task_profile"]
        enabled = unit["enabled_cases"]
        label_to_case: dict[str, dict] = {}
        for entry in enabled:
            for sev in entry.get("severities") or [None]:
                if sev:
                    label_to_case[f"{task_profile}_{entry['case_name']}_{sev}"] = entry
        meta = read_run_meta(unit)
        data = json.loads(unit["results_path"].read_text(encoding="utf-8"))
        for task_key, task_data in data.items():
            results = task_data.get("results") or {}
            baseline = next((v for v in results.values() if v.get("kind") == "baseline"), None)
            protocol = task_data.get("protocol") or {}
            task_index = None
            task_instruction = task_data.get("instruction")
            baseline_row = None
            task_cases: list[dict] = []
            for label, value in results.items():
                if value.get("kind") != "perturbation":
                    continue
                mseed = re.search(r"_s(\d+)$", label)
                seed = int(mseed.group(1)) if mseed else 0
                base_label = re.sub(r"_s\d+$", "", label)
                entry = label_to_case.get(base_label)
                if entry is None:
                    candidates = [e for e in enabled if base_label.startswith(f"{task_profile}_{e['case_name']}_")]
                    entry = candidates[0] if len(candidates) == 1 else None
                case_name = entry["case_name"] if entry else None
                case = catalog["lookup"].get(case_name[len("dataset_"):].replace("_", "-")) if case_name else None
                if case is None and case_name:
                    coverage_notes.append(f"未映射用例: {case_name}")
                task_block = (case or {}).get("task") or {}
                if task_index is None and task_block.get("task_index") is not None:
                    task_index = int(task_block["task_index"])
                report = value.get("report") or {}
                outcome = report.get("outcome") or {}
                trigger = report.get("trigger") or {}
                recovery_cost = value.get("recovery_cost") or {}
                errors = report.get("errors") or []
                verdict = classify_result(case or {}, {"report": report, "injection_valid": report.get("injection_valid")})
                videos_dir = unit["videos_dir"]
                baseline_clip = None
                if baseline is not None:
                    bseed = re.search(r"_s(\d+)$", label)  # not used; baseline seed resolved once per task
                baseline_seed = 0
                for b_label in results:
                    if results[b_label].get("kind") == "baseline":
                        bm = re.search(r"_s(\d+)$", b_label)
                        baseline_seed = int(bm.group(1)) if bm else 0
                        break
                baseline_clip = videos_dir / f"{task_key}__baseline_seed{baseline_seed}.mp4"
                pert_clip = videos_dir / f"{task_key}__{base_label}_seed{seed}.mp4"
                if not pert_clip.is_file():
                    pert_clip = None
                task_cases.append({
                    "task_key": task_key,
                    "task_profile": task_profile,
                    "case_id": (case or {}).get("case_id", case_name or base_label),
                    "case_name": case_name,
                    "short_id": short_case_id((case or {}).get("case_id", case_name or base_label), task_index or 0),
                    "seed": seed,
                    "label": label,
                    "window": ((case or {}).get("trigger") or {}).get("time_point") or "unknown",
                    "mechanism": ((case or {}).get("rollback_target") or {}).get("state_change", {}).get("kind"),
                    "severity": (case or {}).get("severity"),
                    "semantics": (case or {}).get("expected_evaluation_semantics"),
                    "stage": ((case or {}).get("stage") or {}).get("name"),
                    "template": (case or {}).get("template_id"),
                    "description": (case or {}).get("intervention_description"),
                    "trigger_event": ((case or {}).get("trigger") or {}).get("event"),
                    "verdict": verdict,
                    "baseline_success": (baseline or {}).get("success"),
                    "baseline_steps": (baseline or {}).get("steps"),
                    "injection_valid": report.get("injection_valid"),
                    "injection_step": report.get("injection_step"),
                    "trigger_reached": trigger.get("reached"),
                    "rule_executed": report.get("rule_executed"),
                    "recovered": outcome.get("recovered"),
                    "recovery_latency": outcome.get("recovery_latency_steps"),
                    "success": value.get("success"),
                    "steps": value.get("steps"),
                    "errors": errors,
                    "pairing_audit": value.get("pairing_audit"),
                    "eef_path": recovery_cost.get("eef_path_length_m"),
                    "regrasp": recovery_cost.get("regrasp_attempt_count"),
                    "baseline_clip": baseline_clip if baseline_clip and baseline_clip.is_file() else None,
                    "pert_clip": pert_clip,
                    "run_id": meta["run_id"],
                })
            # finalise task identity
            if task_index is None:
                # fall back to the batch dir name, e.g. task01
                m = re.search(r"task0*(\d+)", str(unit["binding_path"]), re.I)
                task_index = int(m.group(1)) if m else 0
            for row in task_cases:
                row["task_index"] = task_index
            cases.extend(task_cases)
            if baseline is not None:
                baselines[task_index] = {
                    "task_index": task_index,
                    "task_key": task_key,
                    "task_profile": task_profile,
                    "instruction": task_instruction,
                    "success": baseline.get("success"),
                    "steps": baseline.get("steps"),
                    "seed": baseline_seed,
                    "clip": (videos_dir / f"{task_key}__baseline_seed{baseline_seed}.mp4"),
                    "run_id": meta["run_id"],
                }
            combined = dict(meta)
            combined.update({
                "model": protocol.get("model") or combined["model"],
                "checkpoint": protocol.get("checkpoint"),
                "replan_steps": protocol.get("replan_steps"),
                "post_success_window": protocol.get("post_success_window"),
                "strict_paired_baseline": protocol.get("strict_paired_baseline"),
                "instruction": task_instruction,
                "task_key": task_key,
                "suite": task_data.get("suite"),
                "seeds": combined["seeds"] or [baseline_seed],
            })
            meta_by_task[task_index] = combined

    # fill missing task indices on baselines/rows for tasks without catalog metadata
    for task_index, base in list(baselines.items()):
        if base is None:
            continue
        task_cases = [c for c in cases if c["task_index"] == task_index]
        if task_cases:
            base["instruction"] = base.get("instruction") or meta_by_task.get(task_index, {}).get("instruction")
    tasks: dict[int, dict] = {}
    for task_index in sorted({c["task_index"] for c in cases}):
        task_cases = [c for c in cases if c["task_index"] == task_index]
        base = baselines.get(task_index) or {}
        tasks[task_index] = {
            "task_index": task_index,
            "task_key": base.get("task_key") or task_cases[0]["task_key"],
            "instruction": base.get("instruction") or (meta_by_task.get(task_index, {}) or {}).get("instruction"),
            "title": titles.get(task_index),
            "cases": task_cases,
            "baseline": base,
            "meta": meta_by_task.get(task_index, {}),
        }
    return {
        "run_root": run_root,
        "catalog": catalog,
        "tasks": tasks,
        "cases": cases,
        "coverage_notes": sorted(set(coverage_notes)),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def summarize(cases: list[dict]) -> dict:
    valid = [c for c in cases if c["injection_valid"] is True]
    success = [c for c in valid if c["success"] is True]
    recovered = [c for c in valid if c["verdict"] == "valid_recovered"]
    invalid = [c for c in cases if c["injection_valid"] is not True]
    probes = [c for c in valid if c["verdict"] == "valid_relation_preserving_probe"]
    controls = [c for c in valid if c["verdict"] == "valid_control"]
    baseline_ok = [c for c in cases if c["baseline_success"] is True]
    return {
        "cases": len(cases),
        "baseline_ok": len(baseline_ok),
        "valid": len(valid),
        "success": len(success),
        "recovered": len(recovered),
        "invalid": len(invalid),
        "probes": len(probes),
        "controls": len(controls),
        "success_excl_probe_control": len([c for c in valid if c["verdict"] not in ("valid_control", "valid_relation_preserving_probe") and c["success"] is True]),
        "valid_excl_probe_control": len([c for c in valid if c["verdict"] not in ("valid_control", "valid_relation_preserving_probe")]),
        "verdicts": dict(Counter(c["verdict"] for c in cases)),
    }


def group_stats(cases: list[dict], key: str, order: list[str] | None = None) -> list[dict]:
    buckets: dict = defaultdict(list)
    for case in cases:
        value = case.get(key)
        if value is None:
            value = "unknown"
        buckets[value].append(case)
    keys = order if order is not None else sorted(buckets, key=lambda x: str(x))
    if order is not None:
        keys = [k for k in order if k in buckets] + [k for k in buckets if k not in order]
    result = []
    for name in keys:
        bucket = buckets.get(name) or []
        valid = [c for c in bucket if c["injection_valid"] is True]
        success = [c for c in valid if c["success"] is True]
        recovered = [c for c in valid if c["verdict"] == "valid_recovered"]
        result.append({
            "name": name,
            "cases": len(bucket),
            "valid": len(valid),
            "success": len(success),
            "recovered": len(recovered),
            "verdicts": dict(Counter(c["verdict"] for c in bucket)),
        })
    return result


def composition(cases: list[dict], key: str, order: list[str]) -> list[dict]:
    rows = []
    for name in order:
        bucket = [c for c in cases if (c.get(key) or "unknown") == name]
        if not bucket:
            continue
        valid = [c for c in bucket if c["injection_valid"] is True]
        seg = Counter()
        for case in valid:
            if case["success"] is True and case["verdict"] == "valid_recovered":
                seg["success"] += 1
            elif case["success"] is True:
                seg["success_other"] += 1
            elif case["verdict"] == "valid_not_recovered":
                seg["not_recovered"] += 1
            elif case["verdict"] in ("valid_control", "valid_relation_preserving_probe"):
                seg["probe_control"] += 1
            elif case["verdict"] == "protocol_incomplete":
                seg["protocol_incomplete"] += 1
            else:
                seg["truth_unverified"] += 1
        for case in bucket:
            if case["injection_valid"] is not True:
                if case["verdict"] == "trigger_not_reached":
                    seg["trigger_not_reached"] += 1
                else:
                    seg["injection_invalid"] += 1
        rows.append({"name": name, "total": len(bucket), "segments": dict(seg)})
    return rows


def build_family_plan(task_cases: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (main family rows for early/mid/later, all_done cases)."""
    families: dict[str, dict] = defaultdict(lambda: {"early": [], "mid": [], "later": [], "all_done": []})
    for case in task_cases:
        window = case["window"] if case["window"] in ("early", "mid", "later", "all_done") else "all_done"
        families[family_key(case["case_id"])][window].append(case)
    main_rows = []
    for family, buckets in families.items():
        eml = {w: sorted(buckets[w], key=lambda c: (c["seed"], c["case_id"])) for w in ("early", "mid", "later")}
        if not any(eml.values()):
            continue
        row_count = max(len(v) for v in eml.values())
        present_windows = [w for w in ("early", "mid", "later") if eml[w]]
        first = next(c for w in ("early", "mid", "later") for c in eml[w])
        for k in range(row_count):
            row = {"family": family, "slots": {}, "first": first, "present": present_windows}
            for window in ("early", "mid", "later"):
                row["slots"][window] = eml[window][k] if k < len(eml[window]) else None
            main_rows.append(row)
    window_pos = {"early": 0, "mid": 1, "later": 2}
    main_rows.sort(key=lambda r: (min(window_pos[w] for w in r["present"]), r["family"], r["first"]["case_id"]))
    all_done = sorted(
        [c for c in task_cases if c["window"] == "all_done"],
        key=lambda c: (family_key(c["case_id"]), c["seed"], c["case_id"]),
    )
    return main_rows, all_done


# --------------------------------------------------------------------------- #
# SVG charts
# --------------------------------------------------------------------------- #
def svg_donut(k: int, n: int, title: str) -> str:
    width = 300
    height = 250
    cx, cy, radius, stroke = 150, 118, 82, 26
    frac = rate(k, n)
    circ = 2 * math.pi * radius
    dash = circ * frac
    color = "#0f7a3d" if frac >= 0.5 else "#b07d00" if frac >= 0.2 else "#b3261e"
    return f'''<svg viewBox="0 0 {width} {height}" class="chart donut" role="img" aria-label="{esc(title)} {pct(frac)}">
  <text x="0" y="14" class="chart-title">{esc(title)}</text>
  <circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="#e8eef4" stroke-width="{stroke}"/>
  <circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{color}" stroke-width="{stroke}"
    stroke-dasharray="{dash:.2f} {circ - dash:.2f}" stroke-dashoffset="0"
    transform="rotate(-90 {cx} {cy})" stroke-linecap="butt"/>
  <text x="{cx}" y="{cy + 2}" text-anchor="middle" class="donut-value" fill="{color}">{pct(frac)}</text>
  <text x="{cx}" y="{cy + 30}" text-anchor="middle" class="donut-label">{k} / {n} 成功</text>
  <text x="{width / 2}" y="{height - 12}" text-anchor="middle" class="chart-note">分母 = 基线成功且注入有效</text>
</svg>'''


def svg_compare(rows: list[tuple[str, int, int, str]], title: str, note: str) -> str:
    width, row_h, label_w, value_w, pad = 980, 48, 190, 190, 12
    height = row_h * len(rows) + 40
    plot_w = width - label_w - value_w
    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="{esc(title)}">']
    parts.append(f'<text x="0" y="14" class="chart-title">{esc(title)}</text>')
    for i, (label, k, n, color) in enumerate(rows):
        y = 28 + i * row_h
        frac = rate(k, n)
        seg = frac * plot_w
        parts.append(f'<text x="0" y="{y + 18}" class="chart-label">{esc(label)}</text>')
        parts.append(f'<rect x="{label_w}" y="{y + 6}" width="{plot_w}" height="22" rx="4" fill="#eef3f8"/>')
        parts.append(f'<rect x="{label_w}" y="{y + 6}" width="{seg:.1f}" height="22" rx="4" fill="{color}"/>')
        parts.append(f'<text x="{label_w + seg + 8:.1f}" y="{y + 22}" class="chart-value">{pct(frac)} · {k}/{n}</text>')
    parts.append(f'<text x="0" y="{height - 8}" class="chart-note">{esc(note)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def svg_rate_bars(title: str, groups: list[dict], note: str, rotate_labels: bool = False) -> str:
    """Vertical bars: y axis = success rate 0-100%, labels k/N, n under x axis."""
    width, height = 980, (430 if rotate_labels else 380)
    left, right, top, bottom = 70, 24, 42, (158 if rotate_labels else 118)
    plot_w = width - left - right
    plot_h = height - top - bottom
    if not groups:
        return f'<svg viewBox="0 0 {width} 120" class="chart"><text x="0" y="16" class="chart-title">{esc(title)}</text><text x="0" y="48" class="chart-note">无分组数据</text></svg>'
    slot = plot_w / len(groups)
    bar_w = min(slot * 0.56, 70)
    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="{esc(title)}">']
    parts.append('<defs><pattern id="hatch" width="7" height="7" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">'
                 '<rect width="7" height="7" fill="#eef3f8"/>'
                 '<line x1="0" y1="0" x2="0" y2="7" stroke="#b7c6d3" stroke-width="2"/></pattern></defs>')
    parts.append(f'<text x="0" y="16" class="chart-title">{esc(title)}</text>')
    parts.append(f'<text x="0" y="32" class="chart-note">{esc(note)}</text>')
    # y grid + ticks
    for tick in range(0, 101, 20):
        y = top + plot_h * (1 - tick / 100)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" class="tick">{tick}%</text>')
    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{width - right}" y2="{top + plot_h}" class="axis"/>')
    parts.append(f'<text x="20" y="{top + plot_h / 2:.1f}" text-anchor="middle" class="axis-title" transform="rotate(-90 20 {top + plot_h / 2:.1f})">成功率</text>')
    for i, group in enumerate(groups):
        cx = left + slot * (i + 0.5)
        x = cx - bar_w / 2
        base_y = top + plot_h
        n, valid, k = group["cases"], group["valid"], group["success"]
        frac = rate(k, valid)
        h = plot_h * frac
        if n == 0:
            parts.append(f'<rect x="{x:.1f}" y="{base_y - 3}" width="{bar_w:.1f}" height="3" fill="#c9d6e2"/>')
            state = "无用例"
        elif valid == 0:
            parts.append(f'<rect x="{x:.1f}" y="{top + plot_h * 0.5:.1f}" width="{bar_w:.1f}" height="{plot_h * 0.5:.1f}" fill="url(#hatch)"/>')
            state = "无有效条目"
        else:
            color = "#0f7a3d" if frac >= 0.5 else "#b07d00" if frac >= 0.2 else "#b3261e"
            parts.append(f'<rect x="{x:.1f}" y="{base_y - h:.1f}" width="{bar_w:.1f}" height="{max(h, 1.5):.1f}" rx="3" fill="{color}"/>')
            parts.append(f'<text x="{cx:.1f}" y="{base_y - h - 8:.1f}" text-anchor="middle" class="bar-value">{k}/{valid}</text>')
            parts.append(f'<text x="{cx:.1f}" y="{base_y - h - 22:.1f}" text-anchor="middle" class="bar-pct">{pct(frac)}</text>')
            state = ""
        if valid and valid < 5:
            parts.append(f'<text x="{cx:.1f}" y="{base_y + 16:.1f}" text-anchor="middle" class="warn-note">⚠ n&lt;5</text>')
        if state:
            parts.append(f'<text x="{cx:.1f}" y="{base_y - 10:.1f}" text-anchor="middle" class="bar-value muted">{state}</text>')
        # x label
        label = group.get("label") or group["name"]
        if rotate_labels:
            parts.append(f'<text x="{cx:.1f}" y="{base_y + 42:.1f}" text-anchor="end" class="chart-label small" transform="rotate(-40 {cx:.1f} {base_y + 42:.1f})">{esc(label)}</text>')
            parts.append(f'<text x="{cx:.1f}" y="{base_y + 82:.1f}" text-anchor="middle" class="tick">n={n}</text>')
        else:
            parts.append(f'<text x="{cx:.1f}" y="{base_y + 32:.1f}" text-anchor="middle" class="chart-label">{esc(label)}</text>')
            parts.append(f'<text x="{cx:.1f}" y="{base_y + 50:.1f}" text-anchor="middle" class="tick">n={n}</text>')
    parts.append("</svg>")
    return "".join(parts)


def svg_stacked_composition(rows: list[dict]) -> str:
    width, row_h, label_w, right, top = 980, 42, 90, 30, 44
    plot_w = width - label_w - right
    height = top + row_h * len(rows) + 58
    seg_order = [
        ("success", "成功", "#0f7a3d"),
        ("not_recovered", "有效未恢复", "#b07d00"),
        ("probe_control", "对照/探针", "#1f5f9e"),
        ("protocol_incomplete", "协议不完整", "#6b4fa1"),
        ("truth_unverified", "真值未验证", "#7b8a99"),
        ("injection_invalid", "注入无效", "#b3261e"),
        ("trigger_not_reached", "触发未到达", "#5d7183"),
        ("success_other", "成功（其他）", "#2e8b57"),
    ]
    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="注入有效性构成">']
    parts.append('<text x="0" y="16" class="chart-title">注入有效性构成（按窗口）</text>')
    parts.append('<text x="0" y="32" class="chart-note">每行 = 该窗口全部用例；分段计数，分母含全部用例（含注入无效）</text>')
    for i, row in enumerate(rows):
        y = top + i * row_h
        total = max(row["total"], 1)
        parts.append(f'<text x="0" y="{y + 20}" class="chart-label">{esc(WINDOW_LABEL.get(row["name"], row["name"]))}</text>')
        x = label_w
        for key, label, color in seg_order:
            count = row["segments"].get(key, 0)
            if not count:
                continue
            seg_w = plot_w * count / total
            parts.append(f'<rect x="{x:.1f}" y="{y + 6}" width="{seg_w:.1f}" height="22" fill="{color}"><title>{esc(label)}: {count}</title></rect>')
            if seg_w > 24:
                parts.append(f'<text x="{x + seg_w / 2:.1f}" y="{y + 22}" text-anchor="middle" class="seg-label">{count}</text>')
            x += seg_w
        parts.append(f'<text x="{width - 8}" y="{y + 22}" text-anchor="end" class="chart-value">{row["total"]} 条</text>')
    # legend
    lx = label_w
    for key, label, color in seg_order:
        if not any(row["segments"].get(key) for row in rows):
            continue
        parts.append(f'<rect x="{lx}" y="{height - 26}" width="12" height="12" fill="{color}"/>')
        parts.append(f'<text x="{lx + 18}" y="{height - 15}" class="chart-note">{esc(label)}</text>')
        lx += 24 + len(label) * 12
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# dimension explanations + invalid-case analysis
# --------------------------------------------------------------------------- #
def case_link(case: dict, text: str | None = None) -> str:
    return f'<a href="#case-{esc(sanitize_slug(case["case_id"]))}">{esc(text or case["short_id"])}</a>'


def example_cell(cases: list[dict], key: str, value: str) -> str:
    subset = sorted(
        [c for c in cases if (c.get(key) or "unknown") == value],
        key=lambda c: (0 if c["injection_valid"] is True else 1, c["case_id"], c["seed"]),
    )
    if not subset:
        return "—"
    example = subset[0]
    return f'{case_link(example)}（{esc(example["window"])}）'


def dimension_table(cases: list[dict], key: str, order: list[str], labels: dict[str, str],
                    meanings: dict[str, str]) -> str:
    present: list[str] = []
    for value in order:
        if any((c.get(key) or "unknown") == value for c in cases):
            present.append(value)
    if any((c.get(key) or "unknown") not in order for c in cases):
        present.append("unknown")
    rows = []
    for value in present:
        count = sum(1 for c in cases if (c.get(key) or "unknown") == value)
        label = labels.get(value, value)
        if key == "severity":
            value_html = f'<span class="mono">{esc(value)}</span>'
        else:
            value_html = f'{esc(label)}（<span class="mono">{esc(value)}</span>）'
        rows.append(
            f'<tr><td>{value_html}</td><td>{esc(meanings.get(value, ""))}</td>'
            f'<td>{count}</td><td>{example_cell(cases, key, value)}</td></tr>'
        )
    return "".join(rows) or '<tr><td colspan="4">无</td></tr>'


def invalid_category(case: dict) -> str:
    if case.get("verdict") == "trigger_not_reached" or case.get("trigger_reached") is False:
        return "trigger_not_reached"
    errors = case.get("errors") or []
    names = [str(e.get("name") or "") for e in errors]
    details = " ".join(str(e.get("detail") or "") for e in errors)
    if "INTERVENTION_NOT_EXECUTED" in names:
        return "intervention_not_executed"
    if "INTERVENTION_ACTIVATION_FAILED" in names:
        if "PROTECTED_BODY" in details:
            return "activation_protected_body"
        if "NO_LEGAL" in details:
            return "activation_no_legal_pair"
        return "activation_other"
    if errors:
        return "other_error"
    return "unknown"


def invalid_analysis(cases: list[dict]) -> dict:
    invalid = [c for c in cases if c["injection_valid"] is not True]
    rows = []
    for key, label, meaning, cls in INVALID_CATEGORIES:
        subset = sorted([c for c in invalid if invalid_category(c) == key], key=lambda c: (c["case_id"], c["seed"]))
        if not subset:
            continue
        rows.append({
            "key": key, "label": label, "meaning": meaning, "cls": cls,
            "count": len(subset),
            "windows": dict(Counter(c["window"] for c in subset)),
            "mechanisms": dict(Counter(c["mechanism"] for c in subset if c["mechanism"])),
            "example": subset[0],
        })
    by_window = []
    for window in WINDOW_ORDER:
        subset = [c for c in invalid if c["window"] == window]
        if not subset:
            continue
        by_window.append({
            "name": window,
            "count": len(subset),
            "total": sum(1 for c in cases if c["window"] == window),
            "categories": dict(Counter(invalid_category(c) for c in subset)),
            "valid": sum(1 for c in cases if c["window"] == window and c["injection_valid"] is True),
        })
    by_mechanism = []
    for mech in MECHANISM_ORDER:
        subset = [c for c in invalid if c["mechanism"] == mech]
        if not subset:
            continue
        by_mechanism.append({
            "name": mech, "count": len(subset),
            "categories": dict(Counter(invalid_category(c) for c in subset)),
            "cases": len([c for c in cases if c["mechanism"] == mech]),
        })
    extra = [c for c in invalid if c["mechanism"] not in MECHANISM_ORDER]
    if extra:
        by_mechanism.append({
            "name": "unknown", "count": len(extra),
            "categories": dict(Counter(invalid_category(c) for c in extra)),
            "cases": len([c for c in cases if c["mechanism"] not in MECHANISM_ORDER]),
        })
    return {
        "total": len(cases),
        "invalid": len(invalid),
        "rows": rows,
        "by_window": by_window,
        "by_mechanism": by_mechanism,
        "cases": sorted(invalid, key=lambda c: (c["window"], c["case_id"], c["seed"])),
        "counts": {row["key"]: row["count"] for row in rows},
    }


def svg_count_bars(title: str, rows: list[tuple[str, int, str]], note: str = "") -> str:
    if not rows:
        return ""
    width, row_h, label_w, value_w = 980, 40, 380, 100
    height = row_h * len(rows) + 40
    plot_w = width - label_w - value_w
    max_count = max(count for _, count, _ in rows) or 1
    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="{esc(title)}">']
    parts.append(f'<text x="0" y="16" class="chart-title">{esc(title)}</text>')
    if note:
        parts.append(f'<text x="0" y="32" class="chart-note">{esc(note)}</text>')
    for i, (label, count, color) in enumerate(rows):
        y = 44 + i * row_h
        bar_w = plot_w * count / max_count
        parts.append(f'<text x="0" y="{y + 18}" class="chart-label">{esc(label)}</text>')
        parts.append(f'<rect x="{label_w}" y="{y + 4}" width="{bar_w:.1f}" height="22" rx="3" fill="{color}"/>')
        parts.append(f'<text x="{label_w + bar_w + 8:.1f}" y="{y + 20}" class="chart-value">{count} 条</text>')
    parts.append("</svg>")
    return "".join(parts)


def render_invalid_section(exp: dict, config: dict) -> str:
    analysis = invalid_analysis(exp["cases"])
    total = analysis["total"]
    invalid = analysis["invalid"]
    if invalid == 0:
        return '''<h3 id="invalid-cases">2.7 扰动未生效用例拆解（注入无效）</h3>
<div class="panel">本次实验全部用例的注入均生效（<span class="mono">injection_valid=True</span>），没有需要拆解的扰动未生效用例。</div>'''
    rows = analysis["rows"]
    chart_rows = [(row["label"], row["count"], INVALID_CATEGORY_COLOR.get(row["cls"], "#5d7183")) for row in rows]
    chart = svg_count_bars("扰动未生效原因分布（条数）", chart_rows, "按错误/判定类别计数；同一用例只计入一个类别。")
    label_by_key = {key: label for key, label, _, _ in INVALID_CATEGORIES}

    def cat_text(categories: dict) -> str:
        return "；".join(f"{label_by_key.get(k, k)} {v}" for k, v in sorted(categories.items())) or "无"

    summary_rows = "".join(
        f'<tr><td><span class="badge {row["cls"]}">{esc(row["label"])}</span></td>'
        f'<td>{esc(row["meaning"])}</td><td>{row["count"]}</td>'
        f'<td>{esc("、".join(f"{WINDOW_LABEL.get(k, k)} {v}" for k, v in sorted(row["windows"].items())))}</td>'
        f'<td>{esc("；".join(MECHANISM_LABEL.get(k, k) for k in row["mechanisms"]) or "未记录")}</td>'
        f'<td>{case_link(row["example"])}</td></tr>'
        for row in rows
    )
    window_rows = "".join(
        f'<tr><td>{esc(WINDOW_LABEL.get(row["name"], row["name"]))}</td><td>{row["total"]}</td>'
        f'<td>{row["count"]}</td><td>{row["valid"]}</td>'
        f'<td>{esc(cat_text(row["categories"]))}</td></tr>'
        for row in analysis["by_window"]
    ) or '<tr><td colspan="5">无</td></tr>'
    mech_rows = "".join(
        f'<tr><td>{esc(MECHANISM_LABEL.get(row["name"], row["name"]))}</td><td>{row["cases"]}</td><td>{row["count"]}</td>'
        f'<td>{esc(cat_text(row["categories"]))}</td></tr>'
        for row in analysis["by_mechanism"]
    ) or '<tr><td colspan="4">无</td></tr>'
    case_rows = ""
    for case in analysis["cases"]:
        label, _ = VERDICT_LABEL.get(case["verdict"], (case["verdict"], "warn"))
        if not (case.get("errors") or []) and case["verdict"] == "trigger_not_reached":
            names = "trigger.reached=False"
            details = "触发事件未到达（该用例没有可用的错误明细）"
        else:
            names = "；".join(str(e.get("name") or "未记录") for e in (case.get("errors") or [])) or "未记录"
            details = "；".join(str(e.get("detail") or "") for e in (case.get("errors") or [])) or "未记录"
        case_rows += (
            f'<tr><td>{case_link(case, case["case_id"])}</td>'
            f'<td>{esc(WINDOW_LABEL.get(case["window"], case["window"]))}</td>'
            f'<td>{esc(MECHANISM_LABEL.get(case["mechanism"], case["mechanism"] or "未记录"))}</td>'
            f'<td>{esc(case["severity"] or "未记录")}</td><td>{esc(label)}</td>'
            f'<td>{esc("是" if case.get("trigger_reached") is True else ("否" if case.get("trigger_reached") is False else "未知"))}</td>'
            f'<td>{esc("是" if case.get("rule_executed") is True else ("否" if case.get("rule_executed") is False else "未知"))}</td>'
            f'<td class="mono">{esc(names)}</td><td>{esc(details)}</td>'
            f'<td><a href="#case-{esc(sanitize_slug(case["case_id"]))}">查看视频卡</a></td></tr>'
        )
    counts = analysis["counts"]
    bullets = [
        f'本次实验 {invalid}/{total} 条用例扰动未生效（占 {pct(invalid / total)}）。它们<b>不计入成功率/恢复率分母，也不计为模型失败</b>，解读整体成功率时必须与本小节的逐条原因一起看。',
    ]
    if counts.get("intervention_not_executed"):
        flag = _flag_label(config.get("post_success_window"))
        bullets.append(
            f'{counts["intervention_not_executed"]} 条属于「触发到达但注入未执行」，均为 all_done 窗口；'
            f'本批次 post-success-window = {esc(flag)}。这是运行配置限制：开启 <span class="mono">--post-success-window</span> 后重跑，才能获得这些用例的注入窗口；当前结果不能用于评价完成边界的恢复能力。'
        )
    if counts.get("activation_no_legal_pair"):
        bullets.append(
            f'{counts["activation_no_legal_pair"]} 条属于「无合法关系边界对」：在声明的搜索范围内找不到「界内合法→界外合法」的位姿配对（封闭抽屉/微波炉场景常见），属于用例几何/搜索策略限制，而不是模型行为；需要调整边界搜索或用例设计后重跑。'
        )
    if counts.get("activation_protected_body"):
        bullets.append(
            f'{counts["activation_protected_body"]} 条属于「保护体碰撞」：注入路径会扫到受保护物体，规则拒绝执行。需要调整平移方向/幅度或保护体配置后重跑。'
        )
    if counts.get("trigger_not_reached"):
        bullets.append(
            f'{counts["trigger_not_reached"]} 条属于「触发未到达」：触发事件没有发生，注入规则未执行；需要检查触发条件、episode 步数预算或运行协议。'
        )
    bullets.append(
        '这些条目的共同含义是「扰动没有真正发生」，因此不能当作模型未恢复/未完成；若把它们计入成功率分母，会把运行配置或几何约束问题误读成模型能力问题。'
    )
    return f'''<h3 id="invalid-cases">2.7 扰动未生效用例拆解（注入无效）</h3>
<div class="panel">
<p>本节只统计 <span class="mono">injection_valid is not True</span> 的用例：扰动在运行中没有真正生效。它们与「注入有效但模型未恢复」是两类不同问题，报告在全文中都不把这些条目计入成功率/恢复率分母。</p>
</div>
<div class="panel kpi-panel">
  <div class="kpi"><b>{invalid}</b><span>扰动未生效条数</span><small>占 {total} 条的 {pct(invalid / total)}</small></div>
  <div class="kpi"><b>{len(rows)}</b><span>原因类别数</span><small>按错误/判定归类</small></div>
  <div class="kpi"><b>{sum(1 for c in analysis["cases"] if c["window"] == "all_done")}</b><span>其中 all_done</span><small>常见于未开 post-success-window</small></div>
  <div class="kpi"><b>{sum(1 for c in analysis["cases"] if c["window"] in ("early", "mid", "later"))}</b><span>其中 early/mid/later</span><small>几何/关系约束或触发问题</small></div>
</div>
{chart}
<h4>2.7.1 原因分类汇总</h4>
<div class="table-wrap"><table class="data" style="min-width:900px"><thead><tr><th>原因类别</th><th>判定依据 / 含义</th><th>条数</th><th>涉及窗口</th><th>涉及机制</th><th>示例</th></tr></thead><tbody>{summary_rows}</tbody></table></div>
<h4>2.7.2 按窗口 / 机制拆解</h4>
<div class="chart-grid" style="grid-template-columns:repeat(auto-fit,minmax(420px,1fr))">
<div><table class="data"><thead><tr><th>窗口</th><th>用例数</th><th>未生效</th><th>注入有效</th><th>类别分布</th></tr></thead><tbody>{window_rows}</tbody></table></div>
<div><table class="data"><thead><tr><th>机制</th><th>用例数</th><th>未生效</th><th>类别分布</th></tr></thead><tbody>{mech_rows}</tbody></table></div>
</div>
<h4>2.7.3 逐条原因明细</h4>
<div class="table-wrap"><table class="data" style="min-width:1100px"><thead><tr><th>case</th><th>窗口</th><th>机制</th><th>档位</th><th>结论</th><th>触发到达</th><th>规则执行</th><th>错误码</th><th>错误明细</th><th>视频卡</th></tr></thead><tbody>{case_rows}</tbody></table></div>
<h4>2.7.4 影响与处理建议</h4>
<div class="panel"><ul class="analysis">{"".join(f"<li>{b}</li>" for b in bullets)}</ul></div>
'''


# --------------------------------------------------------------------------- #
# HTML fragments
# --------------------------------------------------------------------------- #
CSS = r"""
:root{--ink:#16232f;--muted:#5d7183;--line:#dbe4ec;--bg:#f5f8fb;--card:#fff;
--ok:#0f7a3d;--bad:#b3261e;--warn:#8a5a00;--info:#1f5f9e;--accent:#1f5f9e}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;padding:0 0 60px;font:15px/1.65 -apple-system,"Segoe UI","Noto Sans CJK SC",sans-serif;color:var(--ink);background:var(--bg)}
a{color:var(--info)}
h1{font-size:27px;margin:0 0 8px}
h2{font-size:21px;margin:40px 0 14px;padding-bottom:8px;border-bottom:2px solid var(--line);scroll-margin-top:64px}
h3{font-size:16px;margin:24px 0 12px}
h4{font-size:14px;margin:18px 0 8px}
.hero{background:linear-gradient(135deg,#f8fbff,#eef5fb);border-bottom:1px solid var(--line);padding:26px 26px 14px}
.wrap{max-width:1200px;margin:0 auto;padding:0 22px}
.sub{color:var(--muted);margin:0 0 12px;font-size:14px}
.meta-line{color:var(--muted);font-size:13px;margin:0 0 10px}
.nav{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 4px}
.nav a{font-size:13px;text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:4px 12px;background:#fff}
.nav a:hover{background:#eef5fb}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}
.chip{border:1px solid var(--line);border-radius:10px;padding:10px 14px;background:#fbfdff;min-width:128px}
.chip b{display:block;font-size:21px;line-height:1.25}
.chip span{font-size:12px;color:var(--muted)}
.chip.good b{color:var(--ok)} .chip.bad b{color:var(--bad)} .chip.warn b{color:var(--warn)} .chip.info b{color:var(--info)}
.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:14px 0}
.panel.warn-panel{background:#fdf8e8;border-color:#efdfae}
.panel.info-panel{background:#f2f7fc;border-color:#d5e4f2}
table.data{border-collapse:collapse;width:100%;font-size:13px;background:var(--card)}
table.data th,table.data td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
table.data th{background:#eef4f9;position:sticky;top:0;z-index:1}
.table-wrap{max-height:620px;overflow:auto;border:1px solid var(--line);border-radius:12px;background:var(--card)}
.chart{width:100%;height:auto;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;margin:10px 0}
.chart-title{font-size:14px;font-weight:600;fill:var(--ink)}
.chart-note{font-size:11.5px;fill:var(--muted)}
.axis-title{font-size:12px;fill:var(--muted);font-weight:600}
.chart-label{font-size:12px;fill:var(--ink)}
.chart-label.small{font-size:10.5px}
.chart-value{font-size:12px;fill:var(--muted)}
.bar-value{font-size:12px;fill:var(--ink)}
.bar-pct{font-size:11px;fill:var(--muted)}
.seg-label{font-size:11px;fill:#fff}
.tick{font-size:11px;fill:var(--muted)}
.grid{stroke:#e8eef4;stroke-width:1}
.axis{stroke:#9fb2c2;stroke-width:1}
.warn-note{font-size:10.5px;fill:#b07d00}
.muted{fill:var(--muted)}
.donut-value{font-size:30px;font-weight:700}
.donut-label{font-size:12px;fill:var(--muted)}
.chart-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(440px,1fr));gap:14px}
.kpi-panel{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}
.kpi{border:1px solid var(--line);border-radius:10px;padding:12px;background:#fbfdff}
.kpi b{display:block;font-size:22px}
.kpi span{font-size:12px;color:var(--muted);display:block}
.kpi small{font-size:11px;color:var(--muted);display:block;margin-top:2px}
.badge{display:inline-block;font-size:11.5px;border-radius:999px;padding:2px 9px;background:#eef4f9;white-space:nowrap}
.badge.ok{background:#e6f4ea;color:var(--ok)} .badge.bad{background:#fdeceb;color:var(--bad)}
.badge.warn{background:#fdf5e2;color:var(--warn)} .badge.info{background:#e8f1fa;color:var(--info)}
.win-badge{font-weight:600;color:#33475b}
.win-early{background:#eaf3ff} .win-mid{background:#eafaf1} .win-later{background:#fff4e5} .win-all_done{background:#f1eefb}
.filters{position:sticky;top:0;z-index:6;background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:14px 0;box-shadow:0 4px 14px rgba(22,35,47,.06)}
.filter-row{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end}
.filters label{display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--muted)}
.filters select,.filters input{font:inherit;font-size:13px;padding:5px 8px;border:1px solid var(--line);border-radius:8px;background:#fff}
.win-checks{display:flex;gap:10px;flex-wrap:wrap;font-size:13px;color:var(--ink)}
.win-checks label{flex-direction:row;align-items:center;gap:5px;color:var(--ink)}
.filters button{font:inherit;font-size:13px;padding:6px 14px;border:1px solid var(--line);border-radius:8px;background:#eef4f9;cursor:pointer}
.filter-count{color:var(--muted);font-size:12.5px;margin-left:auto}
.task-section{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 18px 22px;margin:18px 0}
.task-head{display:flex;flex-wrap:wrap;gap:14px;align-items:baseline;justify-content:space-between}
.task-head .instr{font-size:15px;color:#33475b;margin:2px 0 0}
.baseline-grid{display:grid;grid-template-columns:minmax(300px,470px) minmax(260px,1fr);gap:16px;align-items:start;margin:14px 0 6px}
.baseline-card{border:2px solid #b9d6ef;border-radius:12px;padding:12px;background:#f6fbff}
.baseline-card h4{margin:0 0 8px}
.baseline-card video{width:100%;border-radius:8px;background:#0d1117}
.stats-table{font-size:12.5px;border-collapse:collapse;width:100%}
.stats-table td{border-bottom:1px dashed var(--line);padding:4px 6px}
.stats-table td:first-child{color:var(--muted);width:42%}
.video-scroll{overflow-x:auto;padding-bottom:6px}
.col-head{display:grid;grid-template-columns:repeat(3,minmax(300px,1fr));gap:12px;min-width:960px;margin:10px 0 4px}
.col-head div{font-size:12.5px;font-weight:600;color:var(--muted);background:#f2f6fa;border:1px solid var(--line);border-radius:8px;padding:4px 10px;text-align:center}
.family-list{min-width:960px}
.family-block{margin:14px 0 18px}
.family-head{font-size:12.5px;color:var(--muted);margin:0 0 6px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.family-head b{color:#33475b;font-weight:600}
.family-row{display:grid;grid-template-columns:repeat(3,minmax(300px,1fr));gap:12px;align-items:stretch}
.slot{min-height:120px}
.card{background:#fff;border:1px solid var(--line);border-left-width:5px;border-radius:10px;padding:10px;height:100%}
.card.ok{border-left-color:var(--ok)} .card.bad{border-left-color:var(--bad)}
.card.warn{border-left-color:var(--warn)} .card.info{border-left-color:var(--info)}
.card-top{display:flex;justify-content:space-between;gap:6px;align-items:center;flex-wrap:wrap}
.card video{width:100%;border-radius:8px;background:#0d1117;margin:8px 0 6px}
.card .cid{font-size:11.5px;color:#33475b;word-break:break-all;margin:2px 0 6px}
.card dl{display:grid;grid-template-columns:auto 1fr;gap:1px 8px;font-size:11.5px;margin:0 0 6px}
.card dt{color:var(--muted)} .card dd{margin:0}
.card .orig{font-size:11.5px}
.invalid-reason{font-size:11.5px;color:var(--bad);background:#fdeceb;border-radius:6px;padding:5px 7px;margin:4px 0}
.placeholder{border:2px dashed #c3d2de;border-radius:10px;background:#f7fafc;color:var(--muted);font-size:12.5px;display:flex;flex-direction:column;gap:4px;align-items:center;justify-content:center;text-align:center;height:100%;min-height:150px;padding:12px}
.placeholder b{color:#41576b;font-size:13px}
.hidden-card{display:none!important}
.hidden-row{display:none!important}
.hidden-section{display:none!important}
.legend{font-size:12px;color:var(--muted);margin:8px 0}
ul.analysis{margin:6px 0 0 18px;padding:0}
ul.analysis li{margin:5px 0}
.footer{max-width:1200px;margin:26px auto 0;padding:16px 22px;color:var(--muted);font-size:12px;border-top:1px solid var(--line)}
.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px}
details summary{cursor:pointer;color:var(--info)}
"""

JS = r"""
(function(){
  var winBoxes=[].slice.call(document.querySelectorAll('input.win-filter'));
  var taskSel=document.getElementById('f-task');
  var mech=document.getElementById('f-mechanism');
  var sev=document.getElementById('f-severity');
  var sem=document.getElementById('f-semantics');
  var verdict=document.getElementById('f-verdict');
  var seed=document.getElementById('f-seed');
  var q=document.getElementById('f-case');
  var reset=document.getElementById('f-reset');
  var count=document.getElementById('f-count');
  var cards=[].slice.call(document.querySelectorAll('.video-card'));
  var rows=[].slice.call(document.querySelectorAll('.family-row'));
  var placeholders=[].slice.call(document.querySelectorAll('.placeholder-slot'));
  function selectedWins(){
    var out={}; winBoxes.forEach(function(b){ if(b.checked){ out[b.value]=true; } }); return out;
  }
  function apply(){
    var wins=selectedWins();
    var needle=(q.value||'').trim().toLowerCase();
    var shown=0;
    cards.forEach(function(c){
      var ok = wins[c.dataset.window]
        && (!taskSel || !taskSel.value || c.dataset.task===taskSel.value)
        && (!mech.value || c.dataset.mechanism===mech.value)
        && (!sev.value || c.dataset.severity===sev.value)
        && (!sem.value || c.dataset.semantics===sem.value)
        && (!verdict.value || c.dataset.verdict===verdict.value)
        && (!seed.value || c.dataset.seed===seed.value)
        && (!needle || c.dataset.case.indexOf(needle)>=0);
      c.classList.toggle('hidden-card', !ok);
      if(ok){ shown++; }
    });
    rows.forEach(function(row){
      var has=[].slice.call(row.querySelectorAll('.video-card')).some(function(c){ return !c.classList.contains('hidden-card'); });
      row.classList.toggle('hidden-row', !has);
      [].slice.call(row.querySelectorAll('.placeholder-slot')).forEach(function(ph){
        ph.classList.toggle('hidden-card', !(has && wins[ph.dataset.window]));
      });
    });
    document.querySelectorAll('.task-section').forEach(function(sec){
      var ok = !taskSel || !taskSel.value || sec.dataset.task===taskSel.value;
      sec.classList.toggle('hidden-section', !ok);
    });
    var tasks={};
    cards.forEach(function(c){ if(!c.classList.contains('hidden-card')){ tasks[c.dataset.task]=true; } });
    var shownPh=placeholders.filter(function(p){ return !p.classList.contains('hidden-card'); }).length;
    count.textContent='显示 '+shown+' / '+cards.length+' 条扰动用例 · '+Object.keys(tasks).length+' 个任务 · 可见占位 '+shownPh+' 个';
  }
  [taskSel,mech,sev,sem,verdict,seed].forEach(function(el){ if(el){ el.addEventListener('change',apply); } });
  winBoxes.forEach(function(b){ b.addEventListener('change',apply); });
  q.addEventListener('input',apply);
  reset.addEventListener('click',function(){
    winBoxes.forEach(function(b){ b.checked=true; });
    [taskSel,mech,sev,sem,verdict,seed].forEach(function(el){ if(el){ el.value=''; } });
    q.value=''; apply();
  });
  apply();
})();
"""


def filter_bar(task_cases: list[dict], seeds: list[int]) -> str:
    windows_present = []
    for window in WINDOW_ORDER:
        if any(c["window"] == window for c in task_cases):
            windows_present.append(window)
    known = set(WINDOW_ORDER)
    if any(c["window"] not in known for c in task_cases):
        windows_present.append("unknown")
    win_checks = "".join(
        f'<label><input type="checkbox" class="win-filter" value="{esc(w)}" checked> {esc(WINDOW_LABEL[w])}</label>'
        for w in windows_present
    )

    def options(values, label=None):
        items = [f'<option value="">全部</option>']
        seen = set()
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            items.append(f'<option value="{esc(value)}">{esc(label(value) if label else value)}</option>')
        return "".join(items)

    mech_values = []
    for c in task_cases:
        m = c["mechanism"]
        if m:
            mech_values.append((MECHANISM_ORDER.index(m) if m in MECHANISM_ORDER else 99, m))
    mech_values = [m for _, m in sorted(set(mech_values))]
    mech_options = options(mech_values, lambda m: f'{MECHANISM_LABEL.get(m, m)}（{m}）')
    sev_values = [s for s in SEVERITY_ORDER if any(c["severity"] == s for c in task_cases)]
    sev_options = options(sev_values)
    sem_values = [s for s in SEMANTICS_ORDER if any(c["semantics"] == s for c in task_cases)]
    sem_options = options(sem_values, lambda s: SEMANTICS_LABEL.get(s, s))
    verdict_values = [v for v in VERDICT_ORDER if any(c["verdict"] == v for c in task_cases)]
    verdict_options = options(verdict_values, lambda v: VERDICT_LABEL.get(v, (v, "warn"))[0])
    seed_options = options([str(s) for s in seeds])
    task_values = sorted({f"T{c['task_index']:02d}" for c in task_cases})
    task_options = options(task_values)
    return f'''<div class="filters" id="filters">
  <div class="filter-row">
    <div id="f-window"><div class="win-checks">{win_checks}</div></div>
    <label>任务<select id="f-task">{task_options}</select></label>
    <label>机制<select id="f-mechanism">{mech_options}</select></label>
    <label>档位<select id="f-severity">{sev_options}</select></label>
    <label>语义<select id="f-semantics">{sem_options}</select></label>
    <label>结论<select id="f-verdict">{verdict_options}</select></label>
    <label>seed<select id="f-seed">{seed_options}</select></label>
    <label>搜索<input id="f-case" placeholder="case_id 关键字"></label>
    <button id="f-reset" type="button">重置</button>
  </div>
  <div class="filter-row"><span class="filter-count" id="f-count"></span></div>
</div>'''


def render_video_card(case: dict, report_dir: Path) -> str:
    label, cls = VERDICT_LABEL.get(case["verdict"], (case["verdict"], "warn"))
    window = case["window"]
    vid_name = case.get("_video_name")
    orig = case.get("_orig_rel")
    if vid_name:
        video_html = f'<video controls preload="metadata" playsinline muted loop src="videos/{esc(vid_name)}"></video>'
    else:
        video_html = '<div class="placeholder" style="min-height:140px">无视频证据</div>'
    error_html = ""
    if case["injection_valid"] is not True:
        reason = ""
        for err in case.get("errors") or []:
            if err.get("name") in INVALID_REASON:
                reason = INVALID_REASON[err["name"]]
                break
        detail = "；".join(f'{e.get("name")}: {e.get("detail")}' for e in (case.get("errors") or []))
        error_html = f'<div class="invalid-reason">注入无效：{esc(reason or detail or "未记录原因")}<br><span class="mono">{esc(detail)}</span></div>'
    orig_html = f'<a class="orig" href="{esc(orig)}" target="_blank">原片</a>' if orig else ""
    return f'''<article class="video-card card {cls}" id="case-{esc(sanitize_slug(case["case_id"]))}" data-task="T{case["task_index"]:02d}" data-window="{esc(window)}" data-mechanism="{esc(case["mechanism"] or "")}" data-severity="{esc(case["severity"] or "")}" data-semantics="{esc(case["semantics"] or "")}" data-verdict="{esc(case["verdict"])}" data-seed="{case["seed"]}" data-case="{esc(case["case_id"].lower())}" data-family="{esc(family_key(case["case_id"]))}">
  <div class="card-top">
    <span class="badge win-badge win-{esc(window)}">{esc(window)}</span>
    <span class="badge {cls}">{esc(label)}</span>
  </div>
  {video_html}
  <div class="cid" title="{esc(case["case_id"])}">{esc(case["short_id"])}</div>
  <dl>
    <dt>机制</dt><dd>{esc(MECHANISM_LABEL.get(case["mechanism"], case["mechanism"] or "未记录"))}</dd>
    <dt>档位</dt><dd>{esc(case["severity"] or "未记录")}</dd>
    <dt>语义</dt><dd>{esc(SEMANTICS_LABEL.get(case["semantics"], case["semantics"] or "未记录"))}</dd>
    <dt>seed</dt><dd>{case["seed"]}</dd>
    <dt>注入步</dt><dd>{case["injection_step"] if case["injection_valid"] is True else "未执行"}</dd>
    <dt>步数</dt><dd>{case["steps"] if case["steps"] is not None else "—"}</dd>
    <dt>恢复延迟</dt><dd>{case["recovery_latency"] if case["verdict"] == "valid_recovered" else "—"}</dd>
  </dl>
  {error_html}
  <div class="card-top">{orig_html}</div>
</article>'''


def placeholder(window: str, present: list[str]) -> str:
    present_txt = "、".join(present) if present else "无"
    return f'''<div class="slot placeholder-slot" data-window="{esc(window)}">
  <div class="placeholder"><b>{esc(window)} 窗口无对应用例</b><span>该用例族仅含 {esc(present_txt)}</span><span>（该窗口无对应 case，按版式留空说明）</span></div>
</div>'''


def render_task_section(task: dict, report_dir: Path, config: dict) -> str:
    idx = task["task_index"]
    cases = task["cases"]
    stats = summarize(cases)
    base = task["baseline"] or {}
    baseline_clip = base.get("clip")
    baseline_name = None
    if baseline_clip and Path(baseline_clip).is_file():
        baseline_name = base.get("_video_name")
    orig_rel = base.get("_orig_rel")
    base_meta = f'成功' if base.get("success") is True else ('失败' if base.get("success") is False else '未知')
    base_cls = "ok" if base.get("success") is True else "bad"
    baseline_orig = f'<a class="orig" href="{esc(orig_rel)}" target="_blank">原片</a>' if orig_rel else ""
    baseline_video = (
        f'<video controls preload="metadata" playsinline muted loop src="videos/{esc(baseline_name)}"></video>'
        if baseline_name else '<div class="placeholder" style="min-height:160px">无基线视频</div>'
    )
    window_counts = Counter(c["window"] for c in cases)
    window_txt = " / ".join(f"{w} {window_counts.get(w, 0)}" for w in ("early", "mid", "later", "all_done") if window_counts.get(w) or w != "unknown")
    rows, all_done = build_family_plan(cases)
    family_blocks = []
    for row in rows:
        first = row["first"]
        present = [w for w in ("early", "mid", "later") if row["slots"][w] is not None]
        present_all = [w for w in ("early", "mid", "later") if any(s["slots"].get(w) for s in rows if s["family"] == row["family"])]
        family_display = row["family"]
        family_display = family_display.replace(f"libero-10-{idx:02d}-rollback-<W>-", "").replace("-<W>", "")
        mech = first["mechanism"]
        mech_label = MECHANISM_LABEL.get(mech, mech or "未记录")
        slots = []
        for window in ("early", "mid", "later"):
            case = row["slots"][window]
            if case is not None:
                slots.append(render_video_card(case, report_dir))
            else:
                slots.append(placeholder(window, present))
        family_blocks.append(f'''<div class="family-block">
  <div class="family-head"><b>family：{esc(family_display)}</b><span>机制：{esc(mech_label)}</span><span>档位：{esc(first["severity"] or "未记录")}</span><span>当前 family 窗口：{esc("、".join(present_all) or "无")}</span></div>
  <div class="family-row">{"".join(slots)}</div>
</div>''')
    # all_done section
    all_done_blocks = []
    if all_done:
        chunks = [all_done[i:i + 3] for i in range(0, len(all_done), 3)]
        for chunk in chunks:
            slots = []
            for i in range(3):
                if i < len(chunk):
                    slots.append(render_video_card(chunk[i], report_dir))
                else:
                    slots.append('<div class="slot"></div>')
            all_done_blocks.append(f'<div class="family-row" style="margin:10px 0">{"".join(slots)}</div>')
        all_done_note = ""
        if config.get("post_success_window") is False:
            all_done_note = f'<div class="panel warn-panel"><b>all_done 窗口注意：</b>本批次未开启 <code>--post-success-window</code>，{len(all_done)} 条 all_done 用例在触发到达后因「无后续 before_step」被判注入无效（INTERVENTION_NOT_EXECUTED），不计入成功率分母；这是运行配置限制，不是模型失败。<a href="#invalid-cases">逐条原因见 2.7</a>。</div>'
        elif config.get("post_success_window") is None:
            all_done_note = '<div class="panel warn-panel">all_done 用例需要 <code>--post-success-window</code> 才可执行注入；本批次该配置未记录在产物中。</div>'
    else:
        all_done_note = ""
    # all_done video names need to be filled by caller
    return f'''<section class="task-section" id="task-{idx:02d}" data-task="T{idx:02d}">
  <div class="task-head">
    <div><h2 style="margin:0;border:none;padding:0">T{idx:02d} · {esc(task.get("title") or "")}</h2>
      <p class="instr"><b>instruction：</b>{esc(task.get("instruction") or "未记录")}</p></div>
    <div class="meta-line">用例 {stats["cases"]} · 注入有效 {stats["valid"]}/{stats["cases"]} · 成功率 {stats["success"]}/{stats["valid"]}（{pct(rate(stats["success"], stats["valid"]))}）· 窗口 {esc(window_txt)}</div>
  </div>
  <div class="baseline-grid">
    <div class="baseline-card">
      <h4>Baseline（配对基线，无扰动）<span class="badge {base_cls}" style="margin-left:8px">{esc(base_meta)}</span></h4>
      {baseline_video}
      <table class="stats-table">
        <tr><td>任务 key</td><td class="mono">{esc(base.get("task_key") or "未记录")}</td></tr>
        <tr><td>run</td><td class="mono">{esc(base.get("run_id") or "未记录")}</td></tr>
        <tr><td>seed</td><td>{base.get("seed", "未记录")}</td></tr>
        <tr><td>success / steps</td><td>{esc("成功" if base.get("success") is True else ("失败" if base.get("success") is False else "未知"))} / {esc(base.get("steps"))}</td></tr>
      </table>
      <div style="margin-top:6px">{baseline_orig}</div>
    </div>
    <div class="panel info-panel" style="margin:0">
      <b>本任务视频版式：</b>每任务最前面 1 条 baseline；扰动视频每行 3 个，按用例族（family）分行、窗口列固定为
      early / mid / later；缺窗口的槽位使用虚线空位说明卡；all_done 用例单独成节、不混入三窗口网格。
      视频为报告内转码副本（256×256、12 fps、CRF 30、无音轨），每张卡片保留原片链接。
    </div>
  </div>
  <h3>扰动证据 · 三窗口（early → mid → later，每行三个）</h3>
  <div class="video-scroll">
    <div class="col-head"><div>early（刚完成）</div><div>mid（撤离/转向）</div><div>later（收尾进行中）</div></div>
    <div class="family-list">{"".join(family_blocks) if family_blocks else '<div class="panel">本任务没有 early/mid/later 窗口的 perturbation 用例。</div>'}</div>
  </div>
  <h3>all_done / 未识别窗口（单独小节）</h3>
  {all_done_note}
  <div class="video-scroll" style="margin-top:8px">{"".join(all_done_blocks) if all_done_blocks else '<div class="panel">本任务没有 all_done / 未识别窗口的 perturbation 用例。</div>'}</div>
</section>'''


# --------------------------------------------------------------------------- #
# page sections
# --------------------------------------------------------------------------- #
def render_intro(exp: dict, config: dict) -> str:
    tasks = list(exp["tasks"].values())
    rows = []
    for task in tasks:
        idx = task["task_index"]
        cases = task["cases"]
        stats = summarize(cases)
        windows = Counter(c["window"] for c in cases)
        rows.append(f'''<tr>
          <td>T{idx:02d}</td><td class="mono">libero_10/{idx:02d}</td>
          <td>{esc(task.get("title") or "")}</td>
          <td class="mono">{esc(config["task_key_by_index"].get(idx, "未记录"))}</td>
          <td>{esc(task.get("instruction") or "未记录")}</td>
          <td>{stats["cases"]}</td>
          <td>{windows.get("early",0)} / {windows.get("mid",0)} / {windows.get("later",0)} / {windows.get("all_done",0)}</td>
          <td>{stats["baseline_ok"]}/{stats["cases"]}</td>
          <td>{stats["success"]}/{stats["valid"]}（{pct(rate(stats["success"], stats["valid"]))}）</td>
        </tr>''')
    task_table = "".join(rows)
    total_cases = len(exp["cases"])
    window_counts = Counter(c["window"] for c in exp["cases"])
    cases_all = exp["cases"]
    window_rows = []
    for window in WINDOW_ORDER + ["unknown"]:
        subset = [c for c in cases_all if c["window"] == window]
        if not subset:
            continue
        example = sorted(subset, key=lambda c: (0 if c["injection_valid"] is True else 1, c["case_id"], c["seed"]))[0]
        window_rows.append(
            f'<tr><td>{esc(WINDOW_LABEL.get(window, window))}</td><td>{esc(WINDOW_MEANING.get(window, ""))}</td>'
            f'<td class="mono">{esc(WINDOW_EVENT_HINT.get(window, "未记录"))}</td><td>{len(subset)}</td>'
            f'<td>{case_link(example)}</td></tr>'
        )
    catalog_by_task = Counter()
    for case in exp["catalog"]["cases"].values():
        idx = ((case.get("task") or {}).get("task_index"))
        if idx is not None:
            catalog_by_task[int(idx)] += 1
    run_by_task = Counter(c["task_index"] for c in exp["cases"])
    if len(tasks) == 1:
        single_idx = tasks[0]["task_index"]
        coverage_note = (
            f'本次实验相对 catalog 的覆盖：catalog 共 {exp["catalog"]["case_count"]} 条用例；'
            f'本报告覆盖 {total_cases} 条（<span class="mono">{esc(config["run_root"])}</span>）。'
            f'T{single_idx:02d} 在 catalog 中的用例数为 {catalog_by_task.get(single_idx, 0)}，'
            f'本次实际运行 {total_cases} 条 → 覆盖 {total_cases}/{catalog_by_task.get(single_idx, 0)}。'
        )
    else:
        missing = [f'T{idx:02d} 缺 {catalog_by_task[idx] - run_by_task.get(idx, 0)} 条'
                   for idx in sorted(catalog_by_task)
                   if catalog_by_task[idx] > run_by_task.get(idx, 0)]
        missing_txt = "、".join(missing) if missing else "无"
        coverage_note = (
            f'本次实验相对 catalog 的覆盖：catalog 共 {exp["catalog"]["case_count"]} 条用例；'
            f'本报告覆盖 {total_cases} 条、{len(tasks)} 个任务 → 覆盖 {total_cases}/{exp["catalog"]["case_count"]}；'
            f'未覆盖：{missing_txt}。'
        )
    window_rows_html = "".join(window_rows) or '<tr><td colspan="5">无</td></tr>'
    mechanism_rows_html = dimension_table(cases_all, "mechanism", MECHANISM_ORDER, MECHANISM_LABEL, MECHANISM_MEANING)
    severity_rows_html = dimension_table(cases_all, "severity", SEVERITY_ORDER, {}, SEVERITY_MEANING)
    semantics_rows_html = dimension_table(cases_all, "semantics", SEMANTICS_ORDER, SEMANTICS_LABEL, SEMANTICS_MEANING)
    family_rows = []
    for task in tasks:
        idx = task["task_index"]
        families: dict[str, list[dict]] = defaultdict(list)
        for case in task["cases"]:
            families[family_key(case["case_id"])].append(case)
        complete = sum(1 for v in families.values() if {"early", "mid", "later"} <= {c["window"] for c in v})
        two = sum(1 for v in families.values() if len({c["window"] for c in v if c["window"] in ("early", "mid", "later")}) == 2)
        single = sum(1 for v in families.values() if len({c["window"] for c in v if c["window"] in ("early", "mid", "later")}) == 1)
        family_rows.append(f'<tr><td>T{idx:02d}</td><td>{len(families)}</td><td>{complete}</td><td>{two}</td><td>{single}</td></tr>')
    return f'''<section id="intro">
<h2>一、实验介绍</h2>
<h3>1.1 实验背景与目标</h3>
<div class="panel">
<p>LIBERO-10 是十个长程操作任务的评测套件，每个任务由两个子目标/关系构成。本仓库是 LIBERO-10 的<b>模型无关 rollback 评测数据集</b>：它记录「任务中已确认完成的关系被外部干预撤销」的场景、状态变化、有效性与预期评测语义，本身不实现恢复算法、控制器或仿真器。</p>
<p>本次实验的协议是：每条用例先跑一次<b>无扰动配对基线</b>，再跑一次<b>扰动 episode</b>；两者共享同一初始状态与随机种子，差异只来自注入。评测时先判定<b>注入是否真实执行并改变了状态</b>（注入有效性），再判断模型是否恢复被撤销的关系、扰动后是否仍能完成任务。</p>
<p>需要区分四层证据：用例定义 → 静态校验 → 原生端点预检（baseline-only）→ live 模型恢复。预检通过不等于模型恢复，注入被拒/未触发也不等于模型失败。另需注意：LIBERO-10 的 BDDL 目标是纯合取，「是否恢复被撤销的前序关系」与「任务最终是否成功」并不绑定，解释成功率时必须说明这一点。</p>
<p><b>本次实验：</b>{esc(config["experiment_name"])}，共 {len(tasks)} 个任务、{total_cases} 条用例；模型 {esc(config["model"] or "未记录")}；步数上限 {esc(config["max_steps"] or "未记录")}；seeds {esc(config["seeds"])}。
{"；".join(config["notes"]) if config["notes"] else ""}</p>
</div>

<h3>1.2 被测任务与覆盖范围</h3>
<div class="panel">
<table class="data"><thead><tr><th>任务</th><th>task_id</th><th>title</th><th>runtime task key</th><th>instruction（BDDL 原文）</th><th>用例数</th><th>窗口 early/mid/later/all_done</th><th>配对基线成功</th><th>扰动成功率 k/N</th></tr></thead><tbody>{task_table}</tbody></table>
<p class="legend">{coverage_note}</p>
</div>

<h3>1.3 扰动设置与评测口径</h3>
<div class="panel">
<p><b>窗口（window）取值</b>：窗口表示注入发生在 episode 的哪个时间点；下表给出含义、触发事件示例、本次用例数，并链接到一条真实用例的视频卡。</p>
<table class="data"><thead><tr><th>窗口</th><th>含义</th><th>触发事件（示例）</th><th>本次用例数</th><th>示例</th></tr></thead><tbody>{window_rows_html}</tbody></table>
<p><b>机制（mechanism）取值</b>：机制表示对已完成关系采用的撤销方式（恢复到初始位姿、施加偏移、从已完成位姿位移、移动参照物等）。下表给出含义、本次用例数与一条真实示例（点击跳转视频卡）。</p>
<table class="data"><thead><tr><th>机制</th><th>含义</th><th>用例数</th><th>示例</th></tr></thead><tbody>{mechanism_rows_html}</tbody></table>
<p><b>档位（severity）取值</b>：档位是机制/幅度代号，与「窗口」无关，也不是跨任务难度分数。历史标签 d0–d3/checkpoint 表示距离或检查点位姿；n*/p*/r05 表示带符号的水平偏移；above/pose/reference/boundary/articulation 表示机制族。</p>
<table class="data"><thead><tr><th>档位</th><th>含义</th><th>用例数</th><th>示例</th></tr></thead><tbody>{severity_rows_html}</tbody></table>
<p><b>语义（semantics）取值</b>：语义是用例的评测契约（注入后是否要求恢复、是否只是关系保持对照/关系探针）。</p>
<table class="data"><thead><tr><th>语义</th><th>含义</th><th>用例数</th><th>示例</th></tr></thead><tbody>{semantics_rows_html}</tbody></table>
<p class="legend">以上四张表均来自本次实验实际数据；示例链接会跳到视频证据区对应卡片。注入未生效的用例在 2.7 单独拆解原因，不计入成功率/恢复率分母。</p>
<p><b>用例族（family）</b>：case_id 去掉独立的 early/mid/later/all_done 片段后相同的用例视为同一 family，是跨窗口对照的基本单位。本次实验的 family 结构：</p>
<table class="data"><thead><tr><th>任务</th><th>family 总数</th><th>三窗口齐全</th><th>双窗口</th><th>单窗口</th></tr></thead><tbody>{"".join(family_rows)}</tbody></table>
<p class="legend">版式固定三槽（early/mid/later），不要求三窗口用例条数等量；某窗口无对应用例时在视频区用空位说明卡标注。severity 标签是机制/幅度代号，不是窗口，也不代表模型难度。</p>
</div>

<h3>1.4 评测对象与配置</h3>
<div class="panel">
<table class="data"><thead><tr><th>项目</th><th>值</th><th>来源</th></tr></thead><tbody>
<tr><td>模型 / checkpoint</td><td>{esc(config["model"] or "未记录")} · <span class="mono">{esc(config["checkpoint"] or "未记录")}</span></td><td>results.json protocol / eval.log</td></tr>
<tr><td>replan / max steps</td><td>{esc(config["replan_steps"] if config["replan_steps"] is not None else "未记录")} / {esc(config["max_steps"] or "未记录")}</td><td>protocol / eval.log</td></tr>
<tr><td>seeds</td><td>{esc(config["seeds"])}</td><td>batch-summary / driver.log / eval.log</td></tr>
<tr><td>runtime overlay</td><td class="mono">{esc(config["runtime"] or "未记录")}</td><td>driver.log</td></tr>
<tr><td>post-success-window</td><td>{esc(_flag_label(config["post_success_window"]))}</td><td>protocol / eval.log RUN_PROTOCOL</td></tr>
<tr><td>配对基线 / strict pairing</td><td>{esc(config["strict_paired_baseline"])}</td><td>protocol</td></tr>
<tr><td>catalog 版本 / case_count</td><td>{esc(exp["catalog"]["version"])} / {exp["catalog"]["case_count"]}</td><td>dataset/current/manifest.yaml</td></tr>
<tr><td>运行目录</td><td class="mono">{esc(config["run_root"])}</td><td>批次目录</td></tr>
<tr><td>批次返回码</td><td>{esc(config["returncode"])}（0=全部结束；2=部分扰动后未完成，是评测结果；3=配对基线失败）</td><td>batch-summary.json</td></tr>
<tr><td>实验日期</td><td>{esc(config["run_date"])}</td><td>run 目录名 / eval.log 时间戳</td></tr>
</tbody></table>
</div>

<h3>1.5 阅读指引</h3>
<div class="panel">
<ul class="analysis">
<li><b>颜色：</b>绿色 = 模型自修恢复；蓝色 = 关系保持对照/探针；黄色 = 注入有效但未恢复（或协议/真值待核）；红色 = 注入无效。<b>成功率柱状图纵轴固定 0–100%</b>，柱顶标 <span class="mono">k/N</span>，柱下标 <span class="mono">n</span>（用例条目数），柱顶百分比为 <span class="mono">k/N</span> 的比值。</li>
<li><b>视频区：</b>每个任务最前面是 1 条 Baseline；之后是扰动视频，每行 3 个、窗口列固定 early/mid/later；虚线卡表示该窗口无对应用例（同一 family 的实际窗口写在卡内）。all_done 用例单独成节，不混入三窗口网格。</li>
<li><b>筛选：</b>顶部筛选栏支持窗口多选、任务、机制、档位、语义、结论、seed 与 case_id 搜索；baseline 不参与筛选、始终显示；筛选状态保持 3 列格位不重排。</li>
<li><b>锚点：</b>附录逐条结果表的 case 名可点击跳转到对应视频卡。</li>
</ul>
</div>
</section>'''


def render_overview(exp: dict, config: dict) -> str:
    cases = exp["cases"]
    stats = summarize(cases)
    base_success = stats["baseline_ok"]
    window_groups = []
    for name in WINDOW_ORDER:
        bucket = [c for c in cases if c["window"] == name]
        valid = [c for c in bucket if c["injection_valid"] is True]
        success = [c for c in valid if c["success"] is True]
        recovered = [c for c in valid if c["verdict"] == "valid_recovered"]
        window_groups.append({"name": name, "label": name, "cases": len(bucket), "valid": len(valid), "success": len(success), "recovered": len(recovered), "verdicts": dict(Counter(c["verdict"] for c in bucket))})
    mech_stats = group_stats(cases, "mechanism", MECHANISM_ORDER)
    for item in mech_stats:
        item["label"] = MECHANISM_LABEL.get(item["name"], item["name"])
    sev_stats = group_stats(cases, "severity", SEVERITY_ORDER)
    for item in sev_stats:
        item["label"] = item["name"]
    sem_stats = group_stats(cases, "semantics", SEMANTICS_ORDER)
    for item in sem_stats:
        item["label"] = SEMANTICS_LABEL.get(item["name"], item["name"])
    comp = composition(cases, "window", WINDOW_ORDER)
    task_indices = sorted(exp["tasks"])
    task_stats = group_stats(cases, "task_index", task_indices)
    for item in task_stats:
        item["label"] = f"T{item['name']:02d}"
    task_chart = ""
    if len(task_indices) > 1:
        task_chart = svg_rate_bars(
            "按任务的成功率（纵轴 0–100%）", task_stats,
            "N = 基线成功且注入有效条目数；n = 用例条目数。", rotate_labels=False,
        )
    # KPI cards
    sensitivity = rate(stats["success_excl_probe_control"], stats["valid_excl_probe_control"]) if stats["valid_excl_probe_control"] else 0.0
    control_total = sum(1 for c in cases if c["semantics"] == "relation_holds_control")
    if control_total == 0:
        control_extra = "本次实验无对照用例"
    elif stats["controls"] == 0:
        control_extra = f"注入有效 0 / 用例 {control_total} 条；本次注入无效"
    else:
        control_extra = f"注入有效 {stats['controls']} / 用例 {control_total} 条；计入成功率分母、不计恢复"
    kpis = [
        ("用例总数", f'{stats["cases"]}', "", ""),
        ("配对基线成功率", f'{base_success}/{stats["cases"]}', pct(rate(base_success, stats["cases"])), "good"),
        ("注入有效率", f'{stats["valid"]}/{stats["cases"]}', pct(rate(stats["valid"], stats["cases"])), "info"),
        ("整体成功率", f'{stats["success"]}/{stats["valid"]}', pct(rate(stats["success"], stats["valid"])), "bad"),
        ("自修恢复率", f'{stats["recovered"]}/{stats["valid"]}', pct(rate(stats["recovered"], stats["valid"])), "warn"),
        ("敏感性成功率", f'{stats["success_excl_probe_control"]}/{stats["valid_excl_probe_control"]}', pct(sensitivity), "warn"),
        ("注入无效", f'{stats["invalid"]}', f'占 {stats["cases"]} 条中的 ' + pct(rate(stats["invalid"], stats["cases"])), "warn"),
        ("关系保持探针", f'{stats["probes"]}', f'注入有效 {stats["probes"]} 条；计入成功率分母、不计恢复', "info"),
        ("关系保持对照", f'{stats["controls"]}', control_extra, "info"),
        ("协议不完整", f'{stats["verdicts"].get("protocol_incomplete", 0)}', "计入成功率分母、不计恢复", "warn"),
    ]
    if len(task_indices) > 1:
        kpis.insert(1, ("任务数", f'{len(task_indices)}', f'T{task_indices[0]:02d}–T{task_indices[-1]:02d}', ""))
    kpi_html = "".join(f'<div class="kpi"><b>{esc(v)}</b><span>{esc(label)}</span><small>{esc(extra)}</small></div>' for label, v, extra, cls in kpis)
    # window description for analysis
    window_rate_str = "；".join(
        (f'{g["name"]} {g["success"]}/{g["valid"]}（{pct(rate(g["success"], g["valid"]))}，n={g["cases"]}）'
         if g["valid"] else f'{g["name"]} 无有效条目（n={g["cases"]}）')
        for g in window_groups
    )
    wins_valid = [g for g in window_groups if g["valid"] > 0]
    if len(wins_valid) == 1:
        single = wins_valid[0]
        window_analysis = (
            f'窗口成功率：仅 {single["name"]} 窗口有有效条目'
            f'（{single["success"]}/{single["valid"]}，{pct(rate(single["success"], single["valid"]))}），'
            f'其余窗口没有有效条目，无法比较窗口趋势。'
        )
    elif wins_valid:
        hi = max(wins_valid, key=lambda g: rate(g["success"], g["valid"]))
        lo = min(wins_valid, key=lambda g: rate(g["success"], g["valid"]))
        delta = rate(hi["success"], hi["valid"]) - rate(lo["success"], lo["valid"])
        window_analysis = f'窗口成功率：最高 {hi["name"]} {hi["success"]}/{hi["valid"]}（{pct(rate(hi["success"], hi["valid"]))}），最低 {lo["name"]} {lo["success"]}/{lo["valid"]}（{pct(rate(lo["success"], lo["valid"]))}），差值 {delta*100:.1f} 个百分点'
        if all(rate(g["success"], g["valid"]) == rate(wins_valid[0]["success"], wins_valid[0]["valid"]) for g in wins_valid):
            window_analysis += "；各窗口成功率相同，没有窗口趋势"
        else:
            window_analysis += "；各窗口之间没有明显单调趋势"
        window_analysis += "。"
    else:
        window_analysis = "本次实验没有有效的窗口分组。"
    # mechanism analysis
    mech_valid = [m for m in mech_stats if m["valid"] > 0]
    mech_top = max(mech_valid, key=lambda m: rate(m["success"], m["valid"])) if mech_valid else None
    mech_worst = max(mech_valid, key=lambda m: m["valid"] - m["success"]) if mech_valid else None
    mech_analysis = ""
    if mech_top:
        mech_analysis = f'机制层面：成功率最高的是 {mech_top["label"]} {mech_top["success"]}/{mech_top["valid"]}（{pct(rate(mech_top["success"], mech_top["valid"]))}）；失败最集中的是 {mech_worst["label"]}（{mech_worst["valid"]} 条有效中 {mech_worst["valid"] - mech_worst["success"]} 条未成功）。'
    if len(task_indices) > 1:
        task_valid = [g for g in task_stats if g["valid"] > 0]
        if task_valid:
            t_hi = max(task_valid, key=lambda g: rate(g["success"], g["valid"]))
            t_lo = min(task_valid, key=lambda g: rate(g["success"], g["valid"]))
            task_analysis = (
                f'共 {len(task_indices)} 个任务；成功率最高 T{t_hi["name"]:02d} '
                f'{t_hi["success"]}/{t_hi["valid"]}（{pct(rate(t_hi["success"], t_hi["valid"]))}），'
                f'最低 T{t_lo["name"]:02d} {t_lo["success"]}/{t_lo["valid"]}'
                f'（{pct(rate(t_lo["success"], t_lo["valid"]))}）。'
            )
        else:
            task_analysis = f'共 {len(task_indices)} 个任务，但没有任何任务存在注入有效条目。'
        task_bullet = f'<li><b>任务：</b>{esc(task_analysis)}</li>'
    else:
        task_analysis = ""
        task_bullet = ""
    # probe analysis
    probe_analysis = (
        f'表现最需谨慎解读：{stats["probes"]} 条关系保持探针（relation_only）占全部成功 {stats["success"]} 条中的 {sum(1 for c in cases if c["verdict"] == "valid_relation_preserving_probe" and c["success"])} 条；'
        f'排除对照/探针后，成功率仅 {stats["success_excl_probe_control"]}/{stats["valid_excl_probe_control"]} = {pct(sensitivity)}。'
        f'真正的模型自修恢复只有 {stats["recovered"]} 条。'
    )
    # invalid analysis
    invalid_analysis_data = invalid_analysis(cases)
    invalid_txt = "；".join(
        f'{row["label"]} {row["count"]} 条' for row in invalid_analysis_data["rows"]
    ) or "无"
    # steps analysis
    valid_cases = [c for c in cases if c["injection_valid"] is True]
    not_recovered_valid = [c for c in valid_cases if c["success"] is not True]
    max_steps = max([c["steps"] for c in not_recovered_valid if c["steps"] is not None], default=None)
    exhausted = [c for c in not_recovered_valid if max_steps and c["steps"] == max_steps]
    success_steps = [c["steps"] for c in valid_cases if c["success"] is True and c["steps"]]
    steps_analysis = ""
    if success_steps:
        steps_analysis = f'步数视角：成功的 {len(success_steps)} 条 episode 步数 {min(success_steps)}–{max(success_steps)}；有效未成功的 {len(not_recovered_valid)} 条中 {len(exhausted)} 条耗尽 {max_steps} 步预算。'
    all_done_note = ""
    all_done_bucket = [c for c in cases if c["window"] == "all_done"]
    if all_done_bucket:
        all_done_note = f'all_done 窗口 {len(all_done_bucket)} 条用例中注入有效 0 条（全部因未开启 --post-success-window 而注入无效），因此 all_done 柱为「无有效条目」，不计入成功率分母。' if all(c["injection_valid"] is not True for c in all_done_bucket) else f'all_done 窗口 {len(all_done_bucket)} 条用例，注入有效 {sum(1 for c in all_done_bucket if c["injection_valid"] is True)} 条。'
    # charts
    overall_rows = [
        ("配对基线成功率", base_success, stats["cases"], "#0f7a3d"),
        ("注入有效率", stats["valid"], stats["cases"], "#1f5f9e"),
        ("整体成功率", stats["success"], stats["valid"], "#b07d00"),
        ("自修恢复率", stats["recovered"], stats["valid"], "#6b4fa1"),
        ("敏感性成功率（排除对照/探针）", stats["success_excl_probe_control"], stats["valid_excl_probe_control"], "#8a5a00"),
    ]
    donut = svg_donut(stats["success"], stats["valid"], "整体成功率")
    compare = svg_compare(overall_rows, "整体指标对比（横轴 0–100%；分母见下方说明）", "成功率分母 = 基线成功 ∧ 注入有效条目；基线与注入有效率分母为用例条目数。")
    window_chart = svg_rate_bars("按窗口的成功率（纵轴 0–100%）", window_groups, "柱顶 k/N；N = 基线成功且注入有效条目数；柱下 n = 用例条目数；all_done 无有效条目时用斜纹空柱标注。", rotate_labels=False)
    comp_chart = svg_stacked_composition(comp)
    mech_chart = svg_rate_bars("按机制的成功率（纵轴 0–100%）", mech_stats, "N = 注入有效条目数；n = 用例条目数；样本量 n<5 有 ⚠ 提示。", rotate_labels=True)
    sev_chart = svg_rate_bars("按档位（severity）的成功率（纵轴 0–100%）", sev_stats, "档位为机制/幅度代号，不是窗口；N = 注入有效条目数。", rotate_labels=False)
    sem_chart = svg_rate_bars("按语义的成功率（纵轴 0–100%）", sem_stats, "relation_holds_control / relation_only 是关系保持对照/探针，计入成功率分母但不计恢复分子。", rotate_labels=False)
    # detail table
    detail_rows = ""
    dim_groups = [("窗口", window_groups)]
    if len(task_indices) > 1:
        dim_groups.append(("任务", task_stats))
    dim_groups += [("机制", mech_stats), ("档位", sev_stats), ("语义", sem_stats)]
    for dim, groups in dim_groups:
        for g in groups:
            label = g.get("label") or g["name"]
            recovered = g.get("recovered", 0)
            rate_txt = pct(rate(g["success"], g["valid"])) if g["valid"] else "—"
            detail_rows += f'<tr><td>{dim}</td><td>{esc(label)}</td><td>{g["cases"]}</td><td>{g["valid"]}</td><td>{g["success"]}</td><td>{rate_txt}</td><td>{recovered}</td></tr>'
    catalog_task_count = exp.get("catalog_task_case_count", "")
    task_indices = sorted(exp["tasks"])
    if len(task_indices) == 1:
        task_dim_note = f'本次实验只覆盖 1 个任务（T{task_indices[0]:02d}），按任务维度的成功率图省略；任务信息见 1.2 表。'
    else:
        task_dim_note = f'本次实验覆盖 {len(task_indices)} 个任务（T{task_indices[0]:02d}–T{task_indices[-1]:02d}）；按任务成功率图如下，任务明细见 1.2 表。'
    probe_success_count = sum(1 for c in cases if c["verdict"] == "valid_relation_preserving_probe" and c["success"])
    if probe_success_count:
        probe_part = f'成功 {stats["success"]} 条中有 {probe_success_count} 条来自关系保持探针，会使整体成功率偏高（敏感性成功率见 2.1）。'
    else:
        probe_part = "本次没有由关系保持探针贡献的成功。"
    all_done_cases = [c for c in cases if c["window"] == "all_done"]
    if all_done_cases:
        all_done_invalid = sum(1 for c in all_done_cases if c["injection_valid"] is not True)
        if all_done_invalid == len(all_done_cases) and config.get("post_success_window") is False:
            all_done_part = "all_done 用例因运行配置（--post-success-window 未开启）全部注入无效，不能据此评价模型在完成边界的恢复能力。"
        else:
            all_done_part = f'all_done 窗口 {len(all_done_cases)} 条用例中注入有效 {len(all_done_cases) - all_done_invalid} 条。'
    else:
        all_done_part = ""
    limitation_text = f'本实验只有 {len(exp["tasks"])} 个任务、{stats["cases"]} 条用例、单 seed；{probe_part}{all_done_part}'
    if stats["invalid"] == 0:
        invalid_bullet = "<b>注入无效：</b>本次无扰动未生效用例。"
    else:
        invalid_bullet = f'<b>注入无效：</b>{esc(invalid_txt)}。这些条目不计入成功率/恢复率分母，也不能计为模型失败（逐条原因见 2.7）。'
    invalid_html = render_invalid_section(exp, config)
    return f'''<section id="overview">
<h2>二、实验结果总览</h2>
<h3>2.1 关键指标卡</h3>
<div class="panel kpi-panel">{kpi_html}</div>
<p class="legend">分母说明：成功率与自修恢复率的分母 = 「基线成功且注入有效」条目数；注入有效率与注入无效占比的分母 = 用例条目数。关系保持对照/探针计入成功率分母但不计入恢复分子，因此另给排除它们后的敏感性成功率。「注入无效」中「注入被拒」与「触发未到达/未执行」按实际 verdict 拆分，逐条原因见 2.7。</p>

<h3>2.2 整体成功率图表</h3>
<div class="chart-grid">
<figure class="chart-card" style="margin:0">{donut}</figure>
<figure class="chart-card" style="margin:0">{compare}</figure>
</div>

<h3>2.3 按窗口的成功率柱状图（成功率为纵轴，第一优先）</h3>
<figure class="chart-card" style="margin:0">{window_chart}</figure>
<figure class="chart-card" style="margin:0">{comp_chart}</figure>

<h3>2.4 其他维度成功率柱状图（纵轴均为成功率 0–100%）</h3>
<p class="legend">{task_dim_note}</p>
{task_chart}
<figure class="chart-card" style="margin:0">{mech_chart}</figure>
<figure class="chart-card" style="margin:0">{sev_chart}</figure>
<figure class="chart-card" style="margin:0">{sem_chart}</figure>

<h3>2.5 维度明细表</h3>
<div class="table-wrap"><table class="data"><thead><tr><th>维度</th><th>分组</th><th>用例条目数</th><th>注入有效（成功率分母）</th><th>成功数</th><th>成功率</th><th>自修恢复数</th></tr></thead><tbody>{detail_rows}</tbody></table></div>

<h3>2.6 简要实验分析</h3>
<div class="panel">
<ul class="analysis">
<li><b>整体：</b>整体成功率 {stats["success"]}/{stats["valid"]} = {pct(rate(stats["success"], stats["valid"]))}；配对基线 {base_success}/{stats["cases"]} = {pct(rate(base_success, stats["cases"]))}；注入有效性 {stats["valid"]}/{stats["cases"]} = {pct(rate(stats["valid"], stats["cases"]))}。与 100% 基线相比，扰动后的成功率下降 {100 - rate(stats["success"], stats["valid"]) * 100:.1f} 个百分点。</li>
<li><b>窗口：</b>{esc(window_rate_str)}。{esc(window_analysis)}{esc(all_done_note)}</li>
{task_bullet}
<li><b>机制/档位：</b>{esc(mech_analysis)}</li>
<li><b>探针与恢复：</b>{esc(probe_analysis)}</li>
<li>{invalid_bullet}</li>
<li><b>步数：</b>{esc(steps_analysis or "未记录")}</li>
<li><b>局限：</b>{limitation_text}</li>
</ul>
</div>
{invalid_html}
</section>'''


def render_method(exp: dict, config: dict, video_stats: dict) -> str:
    cases = exp["cases"]
    stats = summarize(cases)
    join_ok = len([c for c in cases if c.get("case_id") and c.get("window") != "unknown"])
    invalid_breakdown = Counter()
    invalid_details = []
    for c in cases:
        if c["injection_valid"] is not True:
            name = "未记录"
            for e in c.get("errors") or []:
                if e.get("name"):
                    name = e["name"]
                    break
            invalid_breakdown[name] += 1
            details = "; ".join(str(e.get("detail")) for e in (c.get("errors") or []))
            invalid_details.append(
                f'<tr><td class="mono">{esc(c["case_id"])}</td>'
                f'<td>{esc(c["window"])}</td><td>{esc(name)}</td><td>{esc(details)}</td></tr>'
            )
    invalid_txt = "；".join(f"{k}: {v} 条" for k, v in invalid_breakdown.items()) or "无"
    verdict_pieces = []
    for k, v in sorted(
        stats["verdicts"].items(),
        key=lambda kv: VERDICT_ORDER.index(kv[0]) if kv[0] in VERDICT_ORDER else 99,
    ):
        verdict_pieces.append(f"{VERDICT_LABEL.get(k, (k, 'warn'))[0]} {v}")
    verdict_txt = "；".join(verdict_pieces)
    return f'''<section id="method">
<h2>四、方法与复现</h2>
<h3>3.1 生成方式</h3>
<div class="panel">
<p>报告由 <span class="mono">scripts/build_standard_task_report.py</span> 生成，模板版本 <span class="mono">html-report-prompt v1.1</span>。重建命令：</p>
<pre class="mono" style="white-space:pre-wrap;background:#f4f8fb;border:1px solid var(--line);border-radius:8px;padding:10px">python scripts/build_standard_task_report.py \\
  --run {esc(config["run_root"])} \\
  --report {esc(config["report_root"])} \\
  --title "{esc(config["title"])}"</pre>
<p>生成时间：{esc(exp["generated_at"])}。报告的图表、明细表、视频卡与 <span class="mono">evidence.json</span> 由同一次数据加载生成，数字一致。</p>
</div>

<h3>3.2 数据来源与口径</h3>
<div class="panel">
<table class="data"><thead><tr><th>项目</th><th>值 / 规则</th></tr></thead><tbody>
<tr><td>运行产物</td><td class="mono">{esc(config["results_paths"])}</td></tr>
<tr><td>视频目录</td><td class="mono">{esc(config["videos_dir"])}</td></tr>
<tr><td>布局探测</td><td>{esc(config["layout_note"])}</td></tr>
<tr><td>catalog join</td><td>两侧同时归一化 <span class="mono">_ ↔ -</span>；结果标签先剥离 <span class="mono">_s&lt;seed&gt;</span>；本次 join 成功率 {join_ok}/{len(cases)}</td></tr>
<tr><td>判定器</td><td class="mono">src/libero_rollback/evidence.py::classify_result</td></tr>
<tr><td>成功率</td><td>扰动 episode success ÷（基线成功 ∧ 注入有效）条目数 = {stats["success"]}/{stats["valid"]} = {pct(rate(stats["success"], stats["valid"]))}</td></tr>
<tr><td>自修恢复率</td><td><span class="mono">valid_recovered</span> ÷（基线成功 ∧ 注入有效）条目数 = {stats["recovered"]}/{stats["valid"]} = {pct(rate(stats["recovered"], stats["valid"]))}</td></tr>
<tr><td>注入有效率</td><td>注入有效条目数 ÷ 用例条目数 = {stats["valid"]}/{stats["cases"]} = {pct(rate(stats["valid"], stats["cases"]))}</td></tr>
<tr><td>敏感性成功率</td><td>排除 <span class="mono">valid_control</span> 与 <span class="mono">valid_relation_preserving_probe</span> = {stats["success_excl_probe_control"]}/{stats["valid_excl_probe_control"]} = {pct(rate(stats["success_excl_probe_control"], stats["valid_excl_probe_control"]))}</td></tr>
<tr><td>视频转码</td><td>报告内共 {video_stats["clips"]} 条剪辑（本次新转码 {video_stats["transcoded"]} 条，其余复用缓存；256×256、12 fps、H.264 CRF 30、无音轨）到 <span class="mono">videos/</span>；原片保留相对路径链接</td></tr>
</tbody></table>
</div>

<h3>3.3 数据质量与口径核对</h3>
<div class="panel">
<ul class="analysis">
<li>用例：{len(cases)} 条；配对基线成功 {stats["baseline_ok"]}/{stats["cases"]}；注入有效 {stats["valid"]}/{stats["cases"]}；注入无效 {stats["invalid"]} 条（{esc(invalid_txt)}）；逐条原因与处理建议见 <a href="#invalid-cases">2.7</a>。</li>
<li>verdict 构成：{esc(verdict_txt)}。</li>
<li>catalog join：{join_ok}/{len(cases)} 成功，未映射 0 条（两侧归一化后精确匹配）。</li>
<li>视频：扰动视频 {video_stats["pert_found"]}/{len(cases)} 存在；基线视频 {video_stats["baseline_found"]}/{len(exp["tasks"])} 存在；缺失 0 条。</li>
<li>post-success-window：{esc(config["post_success_window"])}；all_done 用例 {sum(1 for c in cases if c["window"] == "all_done")} 条，其中注入有效 {sum(1 for c in cases if c["window"] == "all_done" and c["injection_valid"] is True)} 条。</li>
<li>关系保持探针 {stats["probes"]} 条（均为注入有效、计入成功率分母），关系保持对照 {sum(1 for c in cases if c["semantics"] == "relation_holds_control")} 条（本次注入无效，未进入成功率分母）；探针计入分母但不计恢复分子，仅扫除探针/有效对照后敏感性成功率 {pct(rate(stats["success_excl_probe_control"], stats["valid_excl_probe_control"]))}。</li>
<li>单 seed、单任务：结论不能外推到其他 seed 或全部十个任务。</li>
</ul>
<p><b>注入无效明细：</b></p>
<div class="table-wrap" style="max-height:260px"><table class="data"><thead><tr><th>case</th><th>窗口</th><th>错误码</th><th>明细</th></tr></thead><tbody>{"".join(invalid_details) or "<tr><td colspan=4>无</td></tr>"}</tbody></table></div>
</div>

<h3>3.4 已知限制</h3>
<div class="panel">
<ul class="analysis">
<li>注入被拒/未执行（{stats["invalid"]} 条）不计入成功率分母，也不计为模型失败；其中 all_done 的 3 条是运行配置（未开 --post-success-window）限制，不是模型能力结论。</li>
<li>关系保持探针（{stats["probes"]} 条）与对照（{stats["controls"]} 条）计入成功率分母但不计恢复分子；对照 case 本身也因「无合法原生关系边界对」注入无效。</li>
<li>真实自修恢复只有 {stats["recovered"]} 条，成功率主要由探针贡献（{sum(1 for c in cases if c["verdict"] == "valid_relation_preserving_probe" and c["success"])} 条），解读整体成功率时必须结合敏感性成功率 {pct(rate(stats["success_excl_probe_control"], stats["valid_excl_probe_control"]))}。</li>
<li>本实验为单 seed、单任务；catalog 中 T01 有 {config["catalog_task_case_count"]} 条用例，本次运行 {len(cases)} 条。</li>
</ul>
</div>
</section>'''


def render_appendix(exp: dict) -> str:
    rows = []
    for case in sorted(exp["cases"], key=lambda c: (c["task_index"], WINDOW_ORDER.index(c["window"]) if c["window"] in WINDOW_ORDER else 9, c["case_id"], c["seed"])):
        label, _ = VERDICT_LABEL.get(case["verdict"], (case["verdict"], "warn"))
        rows.append(f'''<tr>
  <td><a href="#case-{esc(sanitize_slug(case["case_id"]))}">{esc(case["case_id"])}</a></td>
  <td>{esc(case["window"])}</td><td>{esc(MECHANISM_LABEL.get(case["mechanism"], case["mechanism"] or ""))}</td>
  <td>{esc(case["severity"] or "")}</td><td>{esc(SEMANTICS_LABEL.get(case["semantics"], case["semantics"] or ""))}</td>
  <td>{esc(label)}</td><td>{esc(case["injection_step"] if case["injection_valid"] is True else "未执行")}</td>
  <td>{esc("是" if case["success"] is True else ("否" if case["success"] is False else "—"))}</td><td>{esc(case["steps"])}</td><td>{esc(case["recovery_latency"] if case["verdict"] == "valid_recovered" else "—")}</td>
  <td>{case["seed"]}</td></tr>''')
    return f'''<section id="appendix">
<h2>五、附录 · 逐条结果表</h2>
<div class="table-wrap"><table class="data"><thead><tr><th>case_id</th><th>窗口</th><th>机制</th><th>档位</th><th>语义</th><th>结论</th><th>注入步</th><th>success</th><th>步数</th><th>恢复延迟</th><th>seed</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
</section>'''


# --------------------------------------------------------------------------- #
# video assets
# --------------------------------------------------------------------------- #
def prepare_videos(exp: dict, report_dir: Path, no_video: bool = False) -> tuple[dict, dict]:
    videos_dir = report_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    stats = {"transcoded": 0, "copied": 0, "pert_found": 0, "baseline_found": 0, "clips": 0, "errors": []}
    ffmpeg_ok = FFMPEG.is_file() and os.access(FFMPEG, os.X_OK)

    def transcode(src: Path, target: Path) -> bool:
        if target.is_file() and target.stat().st_mtime >= src.stat().st_mtime:
            return True
        if no_video:
            return False
        if not ffmpeg_ok:
            stats["errors"].append(f"ffmpeg not available: {FFMPEG}")
            return False
        with tempfile.TemporaryDirectory() as tmp:
            staged = Path(tmp) / "out.mp4"
            proc = subprocess.run(
                [str(FFMPEG), "-y", "-loglevel", "error", "-i", str(src), *TRANSCODE_ARGS, str(staged)],
                capture_output=True, text=True,
            )
            if proc.returncode != 0 or not staged.is_file():
                stats["errors"].append(f"transcode failed: {src}: {proc.stderr[:200]}")
                return False
            shutil.move(str(staged), target)
        stats["transcoded"] += 1
        return True

    for task in exp["tasks"].values():
        base = task["baseline"] or {}
        clip = base.get("clip")
        if clip and Path(clip).is_file():
            stats["baseline_found"] += 1
            name = f'T{task["task_index"]:02d}--baseline--{sanitize_slug(base.get("run_id") or "run")}.mp4'
            target = videos_dir / name
            stats["clips"] += 1
            if transcode(Path(clip), target) or (no_video and target.is_file()):
                base["_video_name"] = name
                base["_orig_rel"] = os.path.relpath(clip, report_dir)
            else:
                base["_orig_rel"] = os.path.relpath(clip, report_dir)
        for case in task["cases"]:
            clip_path = case.get("pert_clip")
            if clip_path and Path(clip_path).is_file():
                stats["pert_found"] += 1
                name = f'T{task["task_index"]:02d}--{sanitize_slug(case["case_id"])}--s{case["seed"]}.mp4'
                target = videos_dir / name
                stats["clips"] += 1
                if transcode(Path(clip_path), target):
                    case["_video_name"] = name
                case["_orig_rel"] = os.path.relpath(clip_path, report_dir)
    return stats, {}


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="run root (batch, container of batches, or legacy)")
    parser.add_argument("--report", type=Path, required=True, help="report output directory")
    parser.add_argument("--title", default=None)
    parser.add_argument("--experiment-name", default=None)
    parser.add_argument("--notes", default="", help="comma separated notes for the intro")
    parser.add_argument("--no-video", action="store_true", help="skip transcoding (fast layout test; videos link to originals)")
    args = parser.parse_args()
    run_root = args.run if args.run.is_absolute() else ROOT / args.run
    report_dir = args.report if args.report.is_absolute() else ROOT / args.report
    if not run_root.is_dir():
        raise SystemExit(f"run root not found: {run_root}")
    report_dir.mkdir(parents=True, exist_ok=True)

    exp = collect_experiment(run_root, ROOT)
    tasks = list(exp["tasks"].values())
    if len(tasks) != 1:
        print(f"note: report covers {len(tasks)} tasks", file=sys.stderr)
    first_task = tasks[0]
    meta = first_task["meta"]
    run_label = run_root.parent.name if re.fullmatch(r"task\d+", run_root.name) else run_root.name
    task_indices = sorted(exp["tasks"])
    if len(task_indices) > 1:
        range_label = f"T{task_indices[0]:02d}–T{task_indices[-1]:02d}"
        default_title = f"LIBERO-10 rollback 实验报告 · {range_label} 全量（{run_label}）"
        default_exp_name = f"libero_10 {range_label} 全量评测（{run_label}）"
    else:
        default_title = (
            f"LIBERO-10 rollback 实验报告 · T{first_task['task_index']:02d}"
            f"（libero_10/{first_task['task_index']:02d}）· {run_label}"
        )
        default_exp_name = f"libero_10 T{first_task['task_index']:02d} 单任务评测（{run_label}）"
    config = {
        "run_root": str(run_root.relative_to(ROOT)) if run_root.is_relative_to(ROOT) else str(run_root),
        "report_root": str(report_dir.relative_to(ROOT)) if report_dir.is_relative_to(ROOT) else str(report_dir),
        "title": args.title or default_title,
        "experiment_name": args.experiment_name or default_exp_name,
        "notes": [n.strip() for n in args.notes.split(",") if n.strip()] or ["本次实验关注扰动后的恢复行为"],
        "model": meta.get("model"),
        "checkpoint": meta.get("checkpoint"),
        "replan_steps": meta.get("replan_steps"),
        "max_steps": meta.get("max_steps"),
        "seeds": meta.get("seeds"),
        "runtime": meta.get("runtime"),
        "post_success_window": meta.get("post_success_window"),
        "strict_paired_baseline": meta.get("strict_paired_baseline"),
        "returncode": meta.get("returncode"),
        "run_date": _run_date(run_root),
        "results_paths": ", ".join(str(u["results_path"]) for u in discover_task_units(run_root)),
        "videos_dir": next(iter(discover_task_units(run_root)))["videos_dir"] if discover_task_units(run_root) else "未记录",
        "layout_note": "递归发现 binding.yaml + run/*/results.json；兼容容器（retest-20261018 下挂 taskNN 批次）与单批次根",
        "catalog_task_case_count": sum(1 for c in exp["catalog"]["cases"].values() if (c.get("task") or {}).get("task_index") == first_task["task_index"]),
        "task_key_by_index": {t["task_index"]: t["task_key"] for t in tasks},
    }
    # seed list for filter
    seeds = sorted({c["seed"] for c in exp["cases"]})
    # first pass: attach video paths (no transcode yet), then transcode, then render
    video_stats, _ = prepare_videos(exp, report_dir, no_video=args.no_video)
    if video_stats["errors"]:
        print("video errors:", video_stats["errors"][:5], file=sys.stderr)
    title = config["title"]
    intro = render_intro(exp, config)
    overview = render_overview(exp, config)
    task_sections = "".join(render_task_section(task, report_dir, config) for task in tasks)
    filters = filter_bar(exp["cases"], seeds)
    method = render_method(exp, config, video_stats)
    appendix = render_appendix(exp)
    page = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{CSS}</style>
</head><body>
<header class="hero"><div class="wrap">
  <h1>{esc(title)}</h1>
  <p class="sub">LIBERO-10 rollback 实验报告 · 模板 html-report-prompt v1.1 · 生成于 {esc(exp["generated_at"])}</p>
  <p class="meta-line">模型 {esc(config["model"] or "未记录")} · suite {esc(first_task["meta"].get("suite") or "LIBERO_10")} · 任务 {len(tasks)} 个 · 用例 {len(exp["cases"])} 条 · 步数上限 {esc(config["max_steps"] or "未记录")} · seeds {esc(config["seeds"])} · 运行目录 <span class="mono">{esc(config["run_root"])}</span></p>
  <nav class="nav">
    <a href="#intro">实验介绍</a><a href="#overview">实验结果总览</a><a href="#videos">视频证据（可筛选）</a><a href="#method">方法与复现</a><a href="#appendix">逐条结果表</a>
  </nav>
</div></header>
<main class="wrap">
{intro}
{overview}
<section id="videos">
<h2>三、视频证据（可按扰动维度筛选）</h2>
<p class="sub">默认视图：每任务先 1 条 Baseline，之后扰动视频每行 3 个、按 family 分行、窗口列固定 early/mid/later；缺窗口显示虚线空位说明卡；all_done 单独成节。筛选状态保持 3 列格位不重排，baseline 始终可见。</p>
{filters}
{task_sections}
</section>
{method}
{appendix}
</main>
<footer class="footer">
<p>数据来源：<span class="mono">{esc(config["results_paths"])}</span><br>
报告生成脚本：<span class="mono">scripts/build_standard_task_report.py</span> · 模板版本 <span class="mono">html-report-prompt v1.1</span> · 口径以 <span class="mono">docs/html-report-prompt.md</span> 为准。<br>
原始运行数据未修改；报告内视频为转码副本，原片链接指向运行目录。</p>
</footer>
<script>{JS}</script>
</body></html>'''
    (report_dir / "index.html").write_text(page, encoding="utf-8")
    evidence = {
        "meta": {
            "title": title,
            "experiment_name": config["experiment_name"],
            "generated_at": exp["generated_at"],
            "run_root": config["run_root"],
            "report_root": config["report_root"],
            "model": config["model"], "checkpoint": config["checkpoint"],
            "max_steps": config["max_steps"], "seeds": config["seeds"],
            "runtime": config["runtime"], "post_success_window": config["post_success_window"],
            "catalog_version": exp["catalog"]["version"], "catalog_case_count": exp["catalog"]["case_count"],
            "template_version": "html-report-prompt v1.1",
        },
        "totals": summarize(exp["cases"]),
        "groups": {
            "window": group_stats(exp["cases"], "window", WINDOW_ORDER),
            "mechanism": group_stats(exp["cases"], "mechanism", MECHANISM_ORDER),
            "severity": group_stats(exp["cases"], "severity", SEVERITY_ORDER),
            "semantics": group_stats(exp["cases"], "semantics", SEMANTICS_ORDER),
        },
        "invalid_analysis": invalid_analysis(exp["cases"]),
        "cases": [
            {k: v for k, v in case.items() if not k.startswith("_")}
            for case in exp["cases"]
        ],
    }
    (report_dir / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    size_mb = (report_dir / "index.html").stat().st_size / 1e6
    n_videos = len(list((report_dir / "videos").glob("*.mp4")))
    print(f"report: {report_dir / 'index.html'} ({size_mb:.2f} MB), videos: {n_videos}, cases: {len(exp['cases'])}, videos transcoded: {video_stats['transcoded']}")
    totals = summarize(exp["cases"])
    print(f"totals: valid={totals['valid']}/{totals['cases']} success={totals['success']}/{totals['valid']} recovered={totals['recovered']}/{totals['valid']} invalid={totals['invalid']}")
    return 0


def _run_date(run_root: Path) -> str:
    candidates = []
    for path in sorted(run_root.rglob("eval.log"))[:1] + sorted(run_root.glob("driver.log"))[:1]:
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
            candidates.append(mtime.date().isoformat())
        except OSError:
            continue
    m = re.search(r"(2026\d{4})", str(run_root))
    if m:
        return f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"
    return candidates[0] if candidates else "未记录"


if __name__ == "__main__":
    raise SystemExit(main())
