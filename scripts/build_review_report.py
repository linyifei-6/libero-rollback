#!/usr/bin/env python3
"""Build a self-contained white-theme human-review report for B-suite rollback runs.

The report is a *manual audit* artifact with exactly two review questions per case:

1. **Injection validity** — was the perturbation really applied to a relation that
   was true, leaving it false (or, for the ``C0`` control, untouched), without
   object penetration, residual velocity or a still-grasped object?
2. **Recovery validity** — is the observed final relation recovery genuinely the
   policy's own repair, rather than the script-level ``restorable`` oracle, an
   external restoration, or a trigger that never fired?

It reads a review bundle (``cases.jsonl``, one case per line) and emits::

    <out>/index.html            overview + injection/recovery tables + full index
    <out>/<suite>-partN.html    paginated per-suite review cards
    <out>/evidence.json         machine-readable denominators + per-case facts
    <out>/README.md             generated report notes / reproduction command
    <out>/provenance.json       source, template version, sha256 of every artifact
    <out>/videos/README.md      local-only video copy instructions (videos not in git)

All CSS/JS is inlined; the pages open with ``file://`` and never touch the network.
Review checkboxes/notes are persisted in ``localStorage`` and can be exported as JSON.

Usage::

    python scripts/build_review_report.py \
        --from-run <B_RUN_DIR> \
        --out experiments/b-rollback/report-goal-object-20261118 \
        --title "B 测试集 · pi05 · Goal+Object 注入/恢复有效性审核" \
        --model pi05 \
        --protocol "max_steps=600; trigger=all_done+delay=10; init_row=0; seed=0; replan=10" \
        --source-run "libero-compose:/runs/b-matrix/full-20261118"

Add ``--reconcile-json <old aggregate.json>`` to emit a data-quality reconciliation
against a previous report. ``--cases`` can be used instead of ``--from-run``.
"""

# ruff: noqa: E501

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import shlex
import sys
from collections import Counter, OrderedDict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TEMPLATE_VERSION = "review-report-v1.0"
SCHEMA_VERSION = 1
TZ = timezone(timedelta(hours=8))  # Asia/Singapore; evidence timestamps are explicit

SUITE_ORDER = ["goal", "object", "spatial", "l10"]
SUITE_LABELS = {
    "goal": "goal（Goal 套件）",
    "object": "object（Object 套件）",
    "spatial": "spatial（Spatial 套件）",
    "l10": "l10（LIBERO-10）",
}
LEVEL_ORDER = ["C0", "L0", "L1", "L2"]
TARGET_ORDER = ["c0", "g", "both", "pre", "s1", "s2"]
VERDICT_ORDER = [
    "valid_recovered",
    "valid_control",
    "valid_not_recovered",
    "control_failed",
    "injection_invalid",
    "trigger_not_reached",
    "protocol_incomplete",
    "incomplete",
]
VERDICT_LABELS = {
    "valid_recovered": "有效注入 · 策略自修复恢复",
    "valid_control": "C0 对照 · 终局成功",
    "valid_not_recovered": "有效注入 · 未恢复",
    "control_failed": "C0 对照 · 终局失败",
    "injection_invalid": "触发到达 · 注入无效",
    "trigger_not_reached": "触发未到达 · N/A",
    "protocol_incomplete": "协议不完整",
    "incomplete": "数据不完整",
}
VERDICT_CLASS = {
    "valid_recovered": "ok",
    "valid_control": "ok",
    "valid_not_recovered": "bad",
    "control_failed": "bad",
    "injection_invalid": "warn",
    "trigger_not_reached": "na",
    "protocol_incomplete": "warn",
    "incomplete": "na",
}
HARD_GATES = [
    "completed_relation_true_before_intervention",
    "all_revoked_false_after_intervention",
    "no_object_penetration",
    "zero_velocity_after_intervention",
    "object_released_before_intervention",
]
GATE_ORDER = HARD_GATES + ["restorable", "goal_preserved_after_pre"]
GATE_LABELS = {
    "completed_relation_true_before_intervention": "注入前关系为真（GT）",
    "all_revoked_false_after_intervention": "注入后关系为假（C0 保持为真）",
    "no_object_penetration": "无物体穿模（≤1 cm）",
    "zero_velocity_after_intervention": "注入后线/角速度归零",
    "object_released_before_intervention": "注入前机器人已释放物体",
    "restorable": "状态写回 oracle 可恢复关系（辅助，非硬门控）",
    "goal_preserved_after_pre": "pre 目标：原生 goal 保持为真（仅 pre case）",
}
GATE_NOTES = {
    "completed_relation_true_before_intervention": "触发时被撤销关系在 GT 中为真；避免把“本来就没达成”的 case 计入。",
    "all_revoked_false_after_intervention": "L0/L1/L2 注入后被撤销关系必须为假；C0 相反，必须仍为真；违反即注入无效。",
    "no_object_penetration": "物体与场景/其它物体侵入 ≤ 1 cm（初始 resting contact 常约 8 mm）。",
    "zero_velocity_after_intervention": "写回 qpos/qvel 后 mj_forward；残余速度必须为 0。",
    "object_released_before_intervention": "注入前机械手已张开（两指间距 > 1 cm），排除“拿着物体注入”的伪撤销。",
    "restorable": "脚本把状态写回后关系可恢复为真；只证明“几何上能修”，不是策略恢复，也不参与硬门控。",
    "goal_preserved_after_pre": "pre case 的附带检查：撤销 s2 时原生 goal 仍应为真。",
}
VERDICT_EXPLANATIONS = [
    ("valid_recovered", "注入有效且非 C0，episode 结束时被撤销关系全部恢复为真（策略自修复）。"),
    ("valid_not_recovered", "注入有效且非 C0，但预算结束时被撤销关系仍为假（策略未恢复）。"),
    ("valid_control", "C0 no-op 对照：同样延迟/强制继续、不动状态，终局任务成功。"),
    ("trigger_not_reached", "触发事件未到达，未注入；记 N/A，**不是 0%**，也不计入 Recovery 分母。"),
    ("injection_invalid", "触发到达但至少一个硬门控未通过；不计入 Recovery 分母，也不计为模型失败。"),
]
RECOVERY_FIELD_NOTES = [
    ("relation_before", "触发时被撤销关系（GT）是否为真。"),
    ("relation_after_injection", "注入后同一关系（GT）；有效 L 类应为 false，C0 应为 true。"),
    ("relation_final", "episode 结束时同一关系（GT）是否为真。"),
    ("recovered", "终局是否恢复（仅对注入有效非 C0 进入 Recovery 分子）。"),
    ("restored_at_step", "首次观测到关系恢复的步数；未恢复为 null。"),
    ("notice_latency", "注入后首次朝被撤销物体移动的步数；行为读数，不是 0/1。"),
    ("repair_budget_steps", "注入后剩余的修复窗口步数（600 活跃步 + 300 repair window 口径下由 runner 记录）。"),
    ("termination", "episode 终止原因（如 step_limit / trigger_not_reached）。"),
]
DEFAULT_PROTOCOL = (
    "max_steps=600; trigger=all_done+delay=10; init_row=0; seed=0; replan=10; camera=256; video=20fps"
)


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def esc(value: Any) -> str:
    """Escape a value for HTML text/attribute context."""
    return html.escape("" if value is None else str(value), quote=True)


def fmt_num(value: Any, digits: int = 5) -> str:
    if value is None:
        return "未记录"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return "未记录"
        if float(value).is_integer():
            return str(int(value))
        return f"{float(value):.{digits}f}"
    return str(value)


def fmt_bool(value: Any, *, na: str = "未记录") -> str:
    if value is None:
        return na
    return "✓ 是" if value else "✗ 否"


def fmt_gate(value: Any) -> str:
    if value is None:
        return "— 未记录"
    return "✓ 通过" if value else "✗ 未通过"


def fmt_list(values: Any) -> str:
    if not values:
        return "—"
    if isinstance(values, (list, tuple)):
        return ", ".join(str(v) for v in values)
    return str(values)


def fmt_pct(k: int | None, n: int | None) -> str:
    """Percentage text; N/A for a zero denominator (never 0%)."""
    if n is None or n == 0 or k is None:
        return "N/A"
    return f"{100.0 * k / n:.1f}%"


def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson 95% CI for a binomial proportion; N/A-safe callers check n > 0."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    spread = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def rate_block(k: int, n: int) -> dict[str, Any]:
    if n <= 0:
        return {"numerator": k, "denominator": n, "value": None, "na": True, "ci95": None}
    lo, hi = wilson_ci(k, n)
    return {
        "numerator": k,
        "denominator": n,
        "value": k / n,
        "na": False,
        "ci95": [round(lo, 6), round(hi, 6)],
    }


def pct_ci(k: int, n: int) -> str:
    if n <= 0:
        return "N/A"
    lo, hi = wilson_ci(k, n)
    return f"{100.0 * k / n:.1f}% [{100.0 * lo:.1f}–{100.0 * hi:.1f}%]"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def now_iso() -> str:
    return datetime.now(TZ).replace(microsecond=0).isoformat()


def parse_iso(value: str | None) -> str:
    if not value:
        return now_iso()
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.replace(microsecond=0).isoformat()


# --------------------------------------------------------------------------- #
# bundle construction / normalization
# --------------------------------------------------------------------------- #
def _validity(case: Mapping[str, Any]) -> dict[str, Any]:
    value = case.get("validity")
    if isinstance(value, Mapping):
        return dict(value)
    value = case.get("injection_gates")
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def compute_injection_valid(case: Mapping[str, Any]) -> bool:
    if not case.get("trigger_reached"):
        return False
    validity = _validity(case)
    return all(validity.get(gate) is True for gate in HARD_GATES)


def compute_verdict(case: Mapping[str, Any]) -> str:
    status = case.get("status") or "ok"
    if status != "ok":
        return "incomplete"
    if not case.get("trigger_reached"):
        return "trigger_not_reached"
    if not compute_injection_valid(case):
        return "injection_invalid"
    if case.get("level") == "C0":
        return "valid_control" if case.get("success") is True else "control_failed"
    return "valid_recovered" if case.get("recovered") is True else "valid_not_recovered"


def case_sort_key(case: Mapping[str, Any]) -> tuple:
    suite = str(case.get("suite") or "")
    suite_rank = SUITE_ORDER.index(suite) if suite in SUITE_ORDER else len(SUITE_ORDER)
    try:
        task = int(case.get("task_idx"))
    except (TypeError, ValueError):
        task = 10**6
    level = str(case.get("level") or "")
    level_rank = LEVEL_ORDER.index(level) if level in LEVEL_ORDER else len(LEVEL_ORDER)
    target = str(case.get("target") or "")
    target_rank = TARGET_ORDER.index(target) if target in TARGET_ORDER else len(TARGET_ORDER)
    return (suite_rank, task, level_rank, target_rank, str(case.get("param") or ""), str(case.get("case_id")))


def _injection_subset(injection: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(injection, Mapping):
        return None
    keep = [
        "case_id",
        "level",
        "param",
        "kind",
        "goal_before",
        "goal_after",
        "revoked_before",
        "revoked_after",
        "relation_after",
        "expected_relation_after",
        "goal_preserved",
        "applied",
        "geometry",
        "max_velocity",
        "zero_velocity",
        "penetration_m",
        "no_penetration",
        "penetration_bodies",
        "object_released",
        "restorable",
        "restore_probe",
    ]
    return {key: injection[key] for key in keep if key in injection}


def case_from_summary(summary: Mapping[str, Any], suite: str) -> dict[str, Any]:
    """Extract one review-bundle record from a runner ``summary.json``.

    Raw numeric values are preserved verbatim; no value is recomputed except the
    derived``injection_valid`` / ``verdict`` labels, which are documented口径 fields.
    """
    case_id = str(summary.get("case_id"))
    video_raw = summary.get("video") if isinstance(summary.get("video"), Mapping) else {}
    raw = {
        "case_id": case_id,
        "suite": summary.get("suite") or suite,
        "task_idx": summary.get("task_idx"),
        "bddl_name": summary.get("bddl_name"),
        "instruction": summary.get("instruction") or summary.get("language"),
        "language": summary.get("language"),
        "target": summary.get("target"),
        "level": summary.get("level"),
        "param": summary.get("param"),
        "family": summary.get("family"),
        "semantics": summary.get("semantics"),
        "expected_relation_after": summary.get("expected_relation_after"),
        "status": summary.get("status"),
        "max_steps": summary.get("max_steps"),
        "steps": summary.get("steps"),
        "checks": summary.get("checks"),
        "termination": summary.get("termination"),
        "trigger_reached": summary.get("trigger_reached"),
        "trigger_step": summary.get("trigger_step"),
        "injection_step": summary.get("injection_step"),
        "injection_wait_steps": summary.get("injection_wait_steps"),
        "trigger_skipped_reason": summary.get("trigger_skipped_reason"),
        "relation_before": summary.get("relation_before"),
        "relation_after_injection": summary.get("relation_after_injection"),
        "relation_final": summary.get("relation_final"),
        "recovered": summary.get("recovered"),
        "recovery": summary.get("recovery"),
        "recovery_ever": summary.get("recovery_ever"),
        "restored_at_step": summary.get("restored_at_step"),
        "notice_latency": summary.get("notice_latency"),
        "repair_budget_steps": summary.get("repair_budget_steps"),
        "success": summary.get("success"),
        "success_ever": summary.get("success_ever"),
        "final_goal_truth": summary.get("final_goal_truth"),
        "final_revoked_truth": summary.get("final_revoked_truth"),
        "goal_atoms": summary.get("goal_atoms"),
        "revoked_objects": summary.get("revoked_objects"),
        "revoked_predicates": summary.get("revoked_predicates"),
        "validity": dict(summary.get("validity") or {}),
        "injection": _injection_subset(summary.get("injection")),
        "video": {
            "path": f"videos/{case_id}.mp4",
            "source_relpath": f"{summary.get('suite') or suite}/{case_id}/video.mp4",
            "fps": video_raw.get("fps"),
            "frames": video_raw.get("frames"),
            "injection_frame": video_raw.get("injection_frame"),
            "injection_time_s": video_raw.get("injection_time_s"),
            "card_seconds": video_raw.get("card_seconds"),
            "timing": video_raw.get("timing"),
        },
        "elapsed_s": summary.get("elapsed_s"),
    }
    return normalize_case(raw)


def normalize_case(case: Mapping[str, Any]) -> dict[str, Any]:
    """Fill defaults and derived fields so arbitrary bundles render consistently."""
    out = dict(case)
    case_id = str(out.get("case_id") or "unknown-case")
    out["case_id"] = case_id
    out.setdefault("suite", "未记录")
    out.setdefault("level", "未记录")
    out.setdefault("target", "未记录")
    out.setdefault("family", "未记录")
    out.setdefault("semantics", "未记录")
    out.setdefault("status", "ok")
    out.setdefault("trigger_reached", False)
    out["trigger_reached"] = bool(out.get("trigger_reached"))
    out.setdefault("validity", {})
    out.setdefault("injection", None)
    video = dict(out.get("video") or {})
    video.setdefault("path", f"videos/{case_id}.mp4")
    out["video"] = video
    out["injection_valid"] = compute_injection_valid(out)
    if not out.get("verdict"):
        out["verdict"] = compute_verdict(out)
    return out


def load_cases_jsonl(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for lineno, line in enumerate(stream, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                raise SystemExit(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            cases.append(normalize_case(raw))
    if not cases:
        raise SystemExit(f"{path}: review bundle is empty")
    return cases


def _case_summary_path(case_dir: Path) -> Path | None:
    """Resolve one case summary in either flat or runner-native layout.

    ``build_review_report`` historically consumed a flattened run
    (``<suite>/<case>/summary.json``).  The current B runner writes
    ``<suite>/<case>/seed-<n>/summary.json``; accept both so a run can be
    reported without copying it.  If several seeds exist, the lowest seed is
    used (the review bundle is one row per case).
    """

    direct = case_dir / "summary.json"
    if direct.is_file():
        return direct
    seeded = sorted(case_dir.glob("seed-*/summary.json"))
    return seeded[0] if seeded else None


def build_cases_from_run(run_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Discover ``<run>/<suite>/<case_id>[/seed-<n>]/summary.json``."""
    if not run_dir.is_dir():
        raise SystemExit(f"--from-run is not a directory: {run_dir}")
    cases: list[dict[str, Any]] = []
    missing: list[str] = []
    for suite_dir in sorted(child for child in run_dir.iterdir() if child.is_dir()):
        suite = suite_dir.name
        for case_dir in sorted(child for child in suite_dir.iterdir() if child.is_dir()):
            summary_path = _case_summary_path(case_dir)
            if summary_path is None:
                missing.append(f"{suite}/{case_dir.name}")
                continue
            with summary_path.open("r", encoding="utf-8") as stream:
                summary = json.load(stream)
            cases.append(case_from_summary(summary, suite))
    if not cases:
        raise SystemExit(f"no summary.json found under {run_dir}/<suite>/<case_id>/")
    return cases, missing


def write_cases_jsonl(path: Path, cases: Sequence[Mapping[str, Any]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for case in cases:
            stream.write(json.dumps(case, ensure_ascii=False, sort_keys=False) + "\n")


# --------------------------------------------------------------------------- #
# aggregate / reconciliation
# --------------------------------------------------------------------------- #
def _group_cases(cases: Iterable[Mapping[str, Any]], key: str) -> list[tuple[str, list[Mapping[str, Any]]]]:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for case in cases:
        value = case.get(key)
        label = str(value) if value not in (None, "") else "未记录"
        groups.setdefault(label, []).append(case)
    order = {
        "suite": SUITE_ORDER,
        "level": LEVEL_ORDER,
        "target": TARGET_ORDER,
        "family": [],
        "semantics": [],
        "verdict": VERDICT_ORDER,
    }.get(key, [])
    return sorted(
        groups.items(),
        key=lambda item: (order.index(item[0]) if item[0] in order else len(order), item[0]),
    )


def _stats(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    triggered = sum(1 for c in cases if c["trigger_reached"])
    valid = sum(1 for c in cases if c["injection_valid"])
    controls = [c for c in cases if c["level"] == "C0"]
    control_ok = sum(1 for c in controls if c.get("success") is True)
    recovery_den = [c for c in cases if c["injection_valid"] and c["level"] != "C0"]
    recovery_num = sum(1 for c in recovery_den if c.get("recovered") is True)
    block = rate_block(recovery_num, len(recovery_den))
    return {
        "cases": total,
        "triggered": triggered,
        "trigger_rate": rate_block(triggered, total),
        "injection_valid": valid,
        "injection_invalid": triggered - valid,
        "injection_valid_rate_of_triggered": rate_block(valid, triggered),
        "controls": len(controls),
        "control_success": control_ok,
        "control_rate": rate_block(control_ok, len(controls)),
        "recovery": block,
    }


def build_aggregate(
    cases: Sequence[Mapping[str, Any]],
    *,
    meta: Mapping[str, Any],
    video_root: Path,
) -> dict[str, Any]:
    total = len(cases)
    triggered = [c for c in cases if c["trigger_reached"]]
    not_triggered = [c for c in cases if not c["trigger_reached"]]
    injection_valid = [c for c in triggered if c["injection_valid"]]
    injection_invalid = [c for c in triggered if not c["injection_valid"]]
    controls = [c for c in cases if c["level"] == "C0"]
    control_ok = [c for c in controls if c.get("success") is True]
    recovery_den = [c for c in injection_valid if c["level"] != "C0"]
    recovery_num = [c for c in recovery_den if c.get("recovered") is True]
    recovery = rate_block(len(recovery_num), len(recovery_den))

    gates: dict[str, Any] = {}
    for gate in GATE_ORDER:
        passed = sum(1 for c in cases if _validity(c).get(gate) is True)
        failed = sum(1 for c in cases if _validity(c).get(gate) is False)
        gates[gate] = {
            "label": GATE_LABELS[gate],
            "note": GATE_NOTES[gate],
            "hard": gate in HARD_GATES,
            "passed": passed,
            "failed": failed,
            "not_recorded": total - passed - failed,
            "attempted": total,
        }

    reason_counts = Counter(
        str(c.get("trigger_skipped_reason")) for c in not_triggered if c.get("trigger_skipped_reason")
    )
    if sum(reason_counts.values()) < len(not_triggered):
        reason_counts["未记录原因"] += len(not_triggered) - sum(reason_counts.values())

    verdict_counts = Counter(str(c["verdict"]) for c in cases)
    failure_counts = {
        "valid_but_not_recovered": verdict_counts.get("valid_not_recovered", 0),
        "control_failed": verdict_counts.get("control_failed", 0),
    }
    for reason, count in sorted(reason_counts.items()):
        failure_counts[f"trigger_not_reached: {reason}"] = count

    notice = [c["notice_latency"] for c in cases if c.get("notice_latency") is not None]
    notice_stats = {
        "n": len(notice),
        "mean": round(sum(notice) / len(notice), 2) if notice else None,
        "median": sorted(notice)[len(notice) // 2] if notice else None,
    }

    def by(key: str) -> OrderedDict[str, Any]:
        result: OrderedDict[str, Any] = OrderedDict()
        for label, group in _group_cases(cases, key):
            result[label] = _stats(group)
        return result

    by_suite = OrderedDict()
    for suite in SUITE_ORDER + sorted({str(c["suite"]) for c in cases} - set(SUITE_ORDER)):
        group = [c for c in cases if str(c["suite"]) == suite]
        if group:
            by_suite[suite] = _stats(group)

    geometry = OrderedDict()
    for level in LEVEL_ORDER:
        group = [c for c in cases if c["level"] == level and isinstance(c.get("injection"), Mapping)]
        if not group:
            continue
        geom = [c["injection"].get("geometry") or {} for c in group]
        translations = [g.get("delta_translation_m") for g in geom if g.get("delta_translation_m") is not None]
        angles = [g.get("delta_angle_rad") for g in geom if g.get("delta_angle_rad") is not None]
        joints = [g.get("delta_joint_max") for g in geom if g.get("delta_joint_max") is not None]
        geometry[level] = {
            "n": len(group),
            "delta_translation_m": {
                "n": len(translations),
                "mean": round(sum(translations) / len(translations), 5) if translations else None,
                "max": round(max(translations), 5) if translations else None,
            },
            "delta_angle_rad": {
                "n": len(angles),
                "mean": round(sum(angles) / len(angles), 5) if angles else None,
                "max": round(max(angles), 5) if angles else None,
            },
            "delta_joint_max": {
                "n": len(joints),
                "mean": round(sum(joints) / len(joints), 5) if joints else None,
                "max": round(max(joints), 5) if joints else None,
            },
        }

    restorable = gates["restorable"]
    videos_available = sum(1 for c in cases if video_available(c, video_root))
    data_quality = build_data_quality(
        total=total,
        triggered=len(triggered),
        injection_valid=len(injection_valid),
        not_triggered=len(not_triggered),
        reason_counts=reason_counts,
        restorable_passed=restorable["passed"],
        videos_available=videos_available,
        by_suite=by_suite,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "template_version": TEMPLATE_VERSION,
        "meta": dict(meta),
        "case_count": total,
        "verdict_counts": {v: verdict_counts.get(v, 0) for v in VERDICT_ORDER if verdict_counts.get(v, 0)},
        "injection": {
            "attempted": total,
            "triggered": len(triggered),
            "trigger_rate": rate_block(len(triggered), total),
            "not_triggered": len(not_triggered),
            "not_triggered_reasons": dict(sorted(reason_counts.items())),
            "not_triggered_case_ids": sorted(str(c["case_id"]) for c in not_triggered),
            "hard_gates": list(HARD_GATES),
            "gates": gates,
            "injection_valid": len(injection_valid),
            "injection_invalid": len(injection_invalid),
            "injection_invalid_case_ids": sorted(str(c["case_id"]) for c in injection_invalid),
            "valid_rate_of_triggered": rate_block(len(injection_valid), len(triggered)),
            "controls": {
                "attempted": len(controls),
                "success": len(control_ok),
                "rate": rate_block(len(control_ok), len(controls)),
            },
            "experimental_aux": {
                "restorable_passed": restorable["passed"],
                "restorable_not_passed": restorable["failed"],
                "restorable_note": "状态写回 oracle 只证明几何可修，不是策略恢复，也不参与硬门控。",
            },
        },
        "recovery": {
            "definition": "Recovery = 注入有效且非 C0 case 中，episode 结束时被撤销关系全部恢复为真。",
            "na_rule": "触发未到达、注入无效、C0 对照都不进入 Recovery 分母；分母为 0 时显示 N/A，不是 0%。",
            "denominator": len(recovery_den),
            "numerator": len(recovery_num),
            "value": recovery["value"],
            "ci95": recovery["ci95"],
            "na": recovery["na"],
            "by_suite": by_suite,
            "by_level": by("level"),
            "by_target": by("target"),
            "by_family": by("family"),
            "c0_controls": {
                "attempted": len(controls),
                "success": len(control_ok),
                "rate": rate_block(len(control_ok), len(controls)),
                "by_suite": OrderedDict(
                    (
                        suite,
                        {
                            "attempted": len(group),
                            "success": sum(1 for c in group if c.get("success") is True),
                        },
                    )
                    for suite, group in _group_cases(controls, "suite")
                ),
            },
        },
        "failure_counts": failure_counts,
        "notice_latency": notice_stats,
        "geometry_by_level": geometry,
        "data_quality": data_quality,
        "videos": {
            "directory": "videos/",
            "available": videos_available,
            "candidates": total,
            "note": "视频为本地审核产物，.gitignore 忽略 *.mp4，不入库；缺失视频在卡片中显式提示。",
        },
    }


def build_data_quality(
    *,
    total: int,
    triggered: int,
    injection_valid: int,
    not_triggered: int,
    reason_counts: Mapping[str, int],
    restorable_passed: int,
    videos_available: int,
    by_suite: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    items: list[str] = []
    suite_counts = " / ".join(
        f"{suite} {stats.get('cases', 0)}" for suite, stats in by_suite.items()
    )
    missing = [suite for suite in SUITE_ORDER if suite not in by_suite]
    missing_text = (
        "；未包含 " + ", ".join(missing) + "（未运行），因此不是 B 矩阵 442 的全量结论"
        if missing
        else "；suite 覆盖完整"
    )
    items.append(
        f"共 {total} 个 case（{suite_counts}）{missing_text}。"
    )
    items.append(
        f"触发 all_done：{triggered}/{total}（{fmt_pct(triggered, total)}）；未触发 {not_triggered} 条记 N/A，"
        f"原因分布：{json.dumps(dict(reason_counts), ensure_ascii=False)}。"
    )
    items.append(
        f"注入硬门控：{injection_valid}/{triggered} 条有效（阈值：注入前关系真、注入后关系假 / C0 保持真、无穿模、零速度、已释放）；"
        f"restorable oracle 通过 {restorable_passed}/{triggered}，它只证明“几何上能修”，不是策略恢复。"
    )
    items.append(
        "Recovery 分母 = 注入有效且非 C0；C0 只做 no-op 对照（延迟 10 步 + 强制继续本身无害），"
        "触发未到达与注入无效都不计为模型失败。"
    )
    items.append(
        f"视频可用 {videos_available}/{total}（videos/ 为本地审核产物，*.mp4 已被 .gitignore 忽略，不入库）；"
        "未复制的 case 在卡片上显示“视频缺失”，不会静默跳过。"
    )
    items.append(
        "单 seed=0、单 init_row=0；本报告是单次运行的审核材料，不含跨 seed 方差或 Wilson CI 之外的统计推断。"
    )
    return items


def video_available(case: Mapping[str, Any], video_root: Path) -> bool:
    rel = str((case.get("video") or {}).get("path") or f"videos/{case.get('case_id')}.mp4")
    return (video_root / Path(rel).name).is_file()


def build_reconciliation(
    aggregate: Mapping[str, Any],
    *,
    old_report_label: str | None,
    reconcile_path: Path | None,
    run_summary_path: Path | None,
    run_label: str | None,
) -> dict[str, Any] | None:
    if reconcile_path is None and run_summary_path is None:
        return None
    result: dict[str, Any] = {
        "old_report": old_report_label,
        "reconcile_file": "<OLD_REPORT_DIR>/aggregate.json" if reconcile_path else None,
        "checks": [],
        "differences": [],
        "geometry_checks": [],
        "metric_notes": [],
        "run_summary": None,
        "run_summary_match": None,
        "all_match": True,
    }

    def check(label: str, old_value: Any, new_value: Any, tol: float | None = None) -> None:
        if tol is not None and isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
            match = abs(float(old_value) - float(new_value)) <= tol
        else:
            match = old_value == new_value
        item = {"label": label, "old": old_value, "new": new_value, "match": bool(match)}
        result["checks"].append(item)
        if not match:
            result["all_match"] = False
            result["differences"].append(item)

    if reconcile_path is not None:
        with reconcile_path.open("r", encoding="utf-8") as stream:
            old = json.load(stream)
        injection = aggregate["injection"]
        recovery = aggregate["recovery"]
        check("cases", old.get("cases"), aggregate["case_count"])
        check("triggered", old.get("triggered"), injection["triggered"])
        check("valid（注入有效）", old.get("valid"), injection["injection_valid"])
        check(
            "perturbed_valid（Recovery 分母）",
            old.get("perturbed_valid"),
            recovery["denominator"],
        )
        check("recovered（Recovery 分子）", old.get("recovered"), recovery["numerator"])
        check(
            "recovery_rate",
            old.get("recovery_rate"),
            recovery["value"],
            tol=1e-4 if recovery["value"] is not None else None,
        )
        for gate, expected in (old.get("gates") or {}).items():
            ours = injection["gates"].get(gate)
            if ours is not None:
                check(f"gate:{gate}", expected, ours["passed"])
        for suite, old_stats in (old.get("by_suite") or {}).items():
            ours = recovery["by_suite"].get(suite) or {}
            check(f"by_suite:{suite}.cases(triggered)", old_stats.get("cases"), ours.get("triggered"))
            check(f"by_suite:{suite}.valid(Recovery 分母)", old_stats.get("valid"), ours.get("recovery", {}).get("denominator"))
            check(f"by_suite:{suite}.recovered", old_stats.get("recovered"), ours.get("recovery", {}).get("numerator"))
            check(f"by_suite:{suite}.controls", old_stats.get("controls"), ours.get("controls"))
            check(f"by_suite:{suite}.control_success", old_stats.get("control_success"), ours.get("control_success"))
        for level, old_stats in (old.get("by_level") or {}).items():
            ours = recovery["by_level"].get(level) or {}
            if level == "C0":
                check("by_level:C0.controls", old_stats.get("controls"), ours.get("controls"))
                check("by_level:C0.control_success", old_stats.get("control_success"), ours.get("control_success"))
            else:
                check(f"by_level:{level}.valid(Recovery 分母)", old_stats.get("valid"), ours.get("recovery", {}).get("denominator"))
                check(f"by_level:{level}.recovered", old_stats.get("recovered"), ours.get("recovery", {}).get("numerator"))
        for target, old_stats in (old.get("by_target") or {}).items():
            ours = recovery["by_target"].get(target) or {}
            if target == "c0":
                check("by_target:c0.controls", old_stats.get("controls"), ours.get("controls"))
            else:
                check(f"by_target:{target}.valid(Recovery 分母)", old_stats.get("valid"), ours.get("recovery", {}).get("denominator"))
                check(f"by_target:{target}.recovered", old_stats.get("recovered"), ours.get("recovery", {}).get("numerator"))
        old_failures = old.get("failures") or {}
        new_failures = aggregate["failure_counts"]
        for key, old_value in old_failures.items():
            if "valid_but_not_recovered" in key:
                new_key = "valid_but_not_recovered"
            elif "all_done not reached" in key:
                new_key = next((k for k in new_failures if "all_done not reached" in k), None)
            elif "revoked relation was not true" in key:
                new_key = next((k for k in new_failures if "revoked relation was not true" in k), None)
            else:
                new_key = None
            if new_key:
                check(f"failures:{key}", old_value, new_failures.get(new_key))
        old_notice = old.get("notice_latency") or {}
        new_notice = aggregate["notice_latency"]
        check("notice_latency.n", old_notice.get("n"), new_notice.get("n"))
        if old_notice.get("mean") is not None and new_notice.get("mean") is not None:
            check("notice_latency.mean", old_notice.get("mean"), new_notice.get("mean"), tol=0.01)
        check("notice_latency.median", old_notice.get("median"), new_notice.get("median"))
        for level, old_geom in (old.get("geometry") or {}).items():
            ours = aggregate["geometry_by_level"].get(level)
            if not ours:
                continue
            candidates = {
                "delta_translation_m": ours["delta_translation_m"],
                "delta_angle_rad": ours["delta_angle_rad"],
                "delta_joint_max": ours["delta_joint_max"],
            }
            match_metric = None
            for metric, stats in candidates.items():
                if (
                    stats.get("mean") is not None
                    and old_geom.get("mean") is not None
                    and abs(stats["mean"] - float(old_geom["mean"])) < 5e-5
                    and abs((stats.get("max") or 0) - float(old_geom.get("max") or 0)) < 5e-5
                ):
                    match_metric = metric
                    break
            result["geometry_checks"].append(
                {
                    "level": level,
                    "old_mean": old_geom.get("mean"),
                    "old_max": old_geom.get("max"),
                    "matched_metric": match_metric,
                }
            )
            if match_metric is None:
                result["all_match"] = False
                result["metric_notes"].append(
                    f"旧报告几何量 {level} 的 mean/max 无法匹配 translation/angle/joint 任一量纲。"
                )
        matched = {item["matched_metric"] for item in result["geometry_checks"]}
        if len(matched) > 1:
            result["metric_notes"].append(
                "旧报告 SUMMARY.md 的几何量行在 L0/L1/L2 之间混用了不同量纲（"
                + "、".join(
                    f"{item['level']}={item['matched_metric']}" for item in result["geometry_checks"]
                )
                + "）；本报告按 delta_translation_m / delta_angle_rad / delta_joint_max 分列，不做跨量纲平均。"
            )

    if run_summary_path is not None:
        with run_summary_path.open("r", encoding="utf-8") as stream:
            run_summary = json.load(stream)
        run_cases = run_summary.get("cases")
        match = run_cases == aggregate["case_count"]
        result["run_summary_match"] = match
        result["run_summary"] = {
            "label": run_label or "<B_RUN_DIR>/run-summary.json",
            "cases": run_cases,
            "triggered": run_summary.get("triggered"),
            "valid": run_summary.get("valid"),
            "recoverable_valid": run_summary.get("recoverable_valid"),
            "recovered": run_summary.get("recovered"),
            "recomputed_cases": aggregate["case_count"],
            "match": match,
            "note": (
                "源 run 根目录的 run-summary.json 与逐 case summary.json 数量不一致："
                "它是更早/中间快照，不是最终汇总；本报告一律以逐 case summary.json 重算为准。"
                if not match
                else "源 run 根目录 run-summary.json 与逐 case 数量一致。"
            ),
        }
    return result


# --------------------------------------------------------------------------- #
# CSS / JS (self-contained, white theme, no external resources)
# --------------------------------------------------------------------------- #
BASE_CSS = r"""
:root{
  --bg:#ffffff; --bg-soft:#f7f8fa; --card:#ffffff; --card-alt:#f4f6f8;
  --ink:#1f2933; --ink-soft:#52606d; --muted:#7b8794; --line:#d9e2ec;
  --accent:#2563eb; --accent-soft:#eff6ff;
  --ok:#166534; --ok-bg:#ecfdf3; --ok-line:#bbf7d0;
  --warn:#92400e; --warn-bg:#fffbeb; --warn-line:#fde68a;
  --bad:#b42318; --bad-bg:#fef3f2; --bad-line:#fecdca;
  --na:#4b5563; --na-bg:#f3f4f6; --na-line:#e5e7eb;
  --radius:10px; --shadow:0 1px 2px rgba(16,24,40,.06),0 1px 3px rgba(16,24,40,.08);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:#ffffff;color:var(--ink);font:15px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;font-size:12.5px}
.layout{display:flex;align-items:flex-start;max-width:1680px;margin:0 auto}
.sidebar{position:sticky;top:0;height:100vh;overflow-y:auto;flex:0 0 252px;background:var(--bg-soft);border-right:1px solid var(--line);padding:16px 12px 40px;font-size:13px}
.sidebar-title{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 8px;font-weight:700}
.sidebar nav{display:block}
.sidebar details{margin:4px 0}
.sidebar summary{cursor:pointer;font-weight:600;color:var(--ink);padding:3px 5px;border-radius:6px;list-style-position:inside}
.sidebar a{display:block;white-space:normal;overflow-wrap:anywhere;color:var(--ink-soft);padding:3px 8px;border-radius:6px;line-height:1.45}
.sidebar a:hover{background:var(--accent-soft);color:var(--accent);text-decoration:none}
.sidebar .lvl2{padding-left:18px;font-size:12.5px}
.main-col{flex:1;min-width:0;padding:26px 34px 70px}
h1{font-size:26px;line-height:1.3;margin:0 0 8px}
h2{font-size:20px;margin:34px 0 12px;padding-top:14px;border-top:1px solid var(--line);scroll-margin-top:16px}
h3{font-size:16px;margin:22px 0 8px;scroll-margin-top:78px}
h4{font-size:14px;margin:0 0 8px;color:var(--ink)}
p{margin:6px 0}
.subtitle{color:var(--ink-soft);margin:0 0 14px;font-size:14px}
.meta-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:6px 18px;background:var(--bg-soft);border:1px solid var(--line);border-radius:var(--radius);padding:14px;margin:12px 0}
.meta-grid dt{font-size:11.5px;color:var(--muted);letter-spacing:.02em}
.meta-grid dd{margin:0 0 6px;font-weight:500;overflow-wrap:anywhere}
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px;margin:12px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:13px 14px}
.kpi .kpi-label{font-size:12.5px;color:var(--ink-soft)}
.kpi .kpi-value{font-size:24px;font-weight:750;margin:3px 0 2px;font-variant-numeric:tabular-nums}
.kpi .kpi-sub{font-size:12px;color:var(--muted);overflow-wrap:anywhere}
.badge{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;border:1px solid var(--line);background:var(--bg-soft);color:var(--ink-soft);margin:1px 4px 1px 0;white-space:nowrap}
.badge.ok{background:var(--ok-bg);border-color:var(--ok-line);color:var(--ok)}
.badge.bad{background:var(--bad-bg);border-color:var(--bad-line);color:var(--bad)}
.badge.warn{background:var(--warn-bg);border-color:var(--warn-line);color:var(--warn)}
.badge.na{background:var(--na-bg);border-color:var(--na-line);color:var(--na)}
table.dt{width:100%;border-collapse:collapse;font-size:13px;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;margin:10px 0}
.dt th,.dt td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.dt thead th{background:var(--card-alt);font-weight:650;font-size:12.5px;color:var(--ink-soft)}
.dt tbody tr:nth-child(even){background:#fcfcfd}
.dt tr:last-child td{border-bottom:0}
.dt td.num,.dt th.num{text-align:right;font-variant-numeric:tabular-nums}
.dt td.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;overflow-wrap:anywhere}
.filters{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.97);border:1px solid var(--line);border-radius:var(--radius);padding:9px 12px;display:flex;flex-wrap:wrap;gap:7px 14px;align-items:center;box-shadow:var(--shadow);margin:12px 0}
.filters label{font-size:12.5px;color:var(--ink-soft);display:inline-flex;gap:5px;align-items:center}
.filters select,.filters input[type=search]{font:inherit;font-size:12.5px;padding:3px 6px;border:1px solid var(--line);border-radius:6px;background:#fff;color:var(--ink)}
.filters .chips{display:inline-flex;gap:8px;flex-wrap:wrap}
.filters .chip{display:inline-flex;align-items:center;gap:4px;font-size:12.5px;color:var(--ink-soft)}
.filter-count{font-size:12.5px;color:var(--accent);font-weight:650;margin-left:auto;white-space:nowrap}
button{font:inherit;font-size:12.5px;padding:4px 11px;border-radius:6px;border:1px solid var(--line);background:#fff;color:var(--ink);cursor:pointer;line-height:1.5}
button:hover:not(:disabled){border-color:var(--accent);color:var(--accent)}
button:disabled{opacity:.45;cursor:not-allowed}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
button.primary:hover:not(:disabled){background:#1d4ed8;color:#fff}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:12px 0}
.toolbar .muted{font-size:12.5px;color:var(--muted)}
.case-card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:16px;margin:14px 0;scroll-margin-top:14px}
.case-card.reviewed{border-left:4px solid var(--accent);padding-left:13px}
.case-card[hidden]{display:none}
.case-head{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:flex-start}
.case-title{font-size:15px;font-weight:700;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere}
.case-badges{text-align:right}
.instruction{font-size:14px;color:var(--ink-soft);margin:7px 0 10px}
.case-subline{font-size:12px;color:var(--muted);margin:0 0 10px;overflow-wrap:anywhere}
.case-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:12px}
.panel{border:1px solid var(--line);border-radius:8px;padding:12px;background:var(--bg-soft);min-width:0}
.panel table{width:100%;border-collapse:collapse;font-size:12.5px}
.panel th,.panel td{padding:3px 4px;border-bottom:1px dashed var(--line);text-align:left;vertical-align:top}
.panel th{color:var(--muted);font-weight:500;width:44%}
.panel tr:last-child th,.panel tr:last-child td{border-bottom:0}
.panel td.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11.5px;overflow-wrap:anywhere}
.panel .hint{font-size:11.5px;color:var(--muted);margin:8px 0 0}
.video-panel video{width:100%;max-height:270px;background:#000;border-radius:6px;display:block}
.video-missing{border:1px dashed var(--warn-line);background:var(--warn-bg);color:var(--warn);padding:16px 12px;border-radius:8px;font-size:12.5px;line-height:1.55}
.video-buttons{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.video-meta{font-size:11.5px;color:var(--muted);margin-top:6px;overflow-wrap:anywhere}
.review-panel{margin-top:12px;border-top:1px solid var(--line);padding-top:10px;display:flex;flex-wrap:wrap;align-items:center;gap:12px 18px}
.review-panel label{font-size:13.5px;display:inline-flex;align-items:center;gap:6px;cursor:pointer;font-weight:550}
.review-panel input[type=checkbox]{width:16px;height:16px;accent-color:var(--accent)}
.review-panel textarea{flex:1 1 340px;min-height:34px;max-height:140px;padding:6px 9px;border:1px solid var(--line);border-radius:6px;font:inherit;font-size:13px;background:#fff;color:var(--ink);resize:vertical}
.review-state{font-size:12px;color:var(--muted)}
.task-head{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:baseline;margin:30px 0 6px;padding-bottom:6px;border-bottom:2px solid var(--line)}
.task-head h3{margin:0}
.task-meta{font-size:12.5px;color:var(--muted);overflow-wrap:anywhere}
.task-group[hidden]{display:none}
.pager{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:20px 0;padding:10px 0;border-top:1px solid var(--line)}
.notice{border:1px solid var(--warn-line);background:var(--warn-bg);color:var(--warn);padding:10px 12px;border-radius:8px;font-size:13px;margin:10px 0}
.note-box{border:1px solid var(--line);background:var(--bg-soft);border-radius:8px;padding:12px;font-size:13px}
.note-box ul{margin:6px 0;padding-left:20px}
pre.notes-text{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;margin:0;font-family:inherit}
.section-intro{color:var(--ink-soft);font-size:13.5px;margin:-2px 0 10px}
.formula{background:var(--card-alt);border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:13px;margin:8px 0}
.formula code{font-size:12.5px}
.legend{font-size:12.5px;color:var(--muted);margin:6px 0}
.swatches{display:flex;flex-wrap:wrap;gap:10px;margin:8px 0}
.swatch{display:flex;gap:6px;align-items:center;font-size:12.5px;color:var(--ink-soft)}
.swatch i{width:14px;height:14px;border-radius:3px;border:1px solid var(--line);display:inline-block}
@media (max-width:1100px){
  .layout{display:block}
  .sidebar{position:static;height:auto;width:auto;border-right:0;border-bottom:1px solid var(--line)}
  .main-col{padding:18px 16px 50px}
}
@media print{.sidebar,.filters,.toolbar,.pager{display:none}.main-col{padding:0}}
"""

BASE_JS = r"""
(function(){
  "use strict";
  var REPORT_ID = "__REPORT_ID__";
  var TEMPLATE_VERSION = "__TEMPLATE_VERSION__";
  var LS_KEY = "libero-rollback-review:v1:" + REPORT_ID;

  function loadAll(){
    try { return JSON.parse(window.localStorage.getItem(LS_KEY) || "{}") || {}; }
    catch (e) { return {}; }
  }
  function saveAll(state){
    try { window.localStorage.setItem(LS_KEY, JSON.stringify(state)); return true; }
    catch (e) { return false; }
  }
  function hasReview(entry){
    return !!(entry && (entry.injection || entry.recovery || (entry.note && entry.note.length)));
  }
  function today(){
    var d = new Date();
    return d.toISOString();
  }
  function reviewEntry(card){
    var state = loadAll();
    return state[card.getAttribute("data-case-id")] || null;
  }
  function updateCard(card){
    var entry = reviewEntry(card);
    card.classList.toggle("reviewed", hasReview(entry));
    var stateEl = card.querySelector(".review-state");
    if (stateEl){
      stateEl.textContent = hasReview(entry) ? "已记录审核（本地保存）" : "未审核";
    }
  }
  function updateReviewCounts(){
    var store = loadAll();
    var cards = document.querySelectorAll(".case-card");
    var out = document.getElementById("review-count");
    if (!out) return;
    if (cards.length){
      var injected = 0, recovered = 0, reviewed = 0;
      Array.prototype.forEach.call(cards, function(card){
        var entry = store[card.getAttribute("data-case-id")] || {};
        if (entry.injection) injected += 1;
        if (entry.recovery) recovered += 1;
        if (hasReview(entry)) reviewed += 1;
      });
      out.textContent = "本页已审核 " + reviewed + " / " + cards.length
        + "（注入勾选 " + injected + "，恢复勾选 " + recovered + "）";
    } else {
      out.textContent = "已保存审核记录 " + Object.keys(store).length + " 条";
    }
    var marks = document.querySelectorAll("[data-review-mark]");
    Array.prototype.forEach.call(marks, function(mark){
      var entry = store[mark.getAttribute("data-review-mark")];
      if (hasReview(entry)){
        mark.textContent = "已审核";
        mark.className = "badge ok";
      } else {
        mark.textContent = "未审核";
        mark.className = "badge na";
      }
    });
  }
  function bindReview(){
    var cards = document.querySelectorAll(".case-card");
    Array.prototype.forEach.call(cards, function(card){
      var caseId = card.getAttribute("data-case-id");
      var state = loadAll()[caseId] || {};
      Array.prototype.forEach.call(card.querySelectorAll("[data-review]"), function(el){
        var field = el.getAttribute("data-review");
        if (el.type === "checkbox") el.checked = !!state[field];
        else el.value = state[field] || "";
      });
      function persist(){
        var all = loadAll();
        var entry = all[caseId] || {};
        Array.prototype.forEach.call(card.querySelectorAll("[data-review]"), function(el){
          var field = el.getAttribute("data-review");
          entry[field] = (el.type === "checkbox") ? el.checked : el.value;
        });
        entry.updated_at = today();
        if (hasReview(entry)) all[caseId] = entry;
        else delete all[caseId];
        saveAll(all);
        updateCard(card);
        updateReviewCounts();
        if (typeof applyFilters === "function") applyFilters();
      }
      Array.prototype.forEach.call(card.querySelectorAll("[data-review]"), function(el){
        el.addEventListener("change", persist);
        if (el.tagName === "TEXTAREA") el.addEventListener("input", persist);
      });
      updateCard(card);
    });
    updateReviewCounts();
  }
  function bindExport(){
    var buttons = document.querySelectorAll(".js-export-review");
    Array.prototype.forEach.call(buttons, function(btn){
      btn.addEventListener("click", function(){
        var store = loadAll();
        var payload = {
          report_id: REPORT_ID,
          template_version: TEMPLATE_VERSION,
          exported_at: today(),
          n_reviewed: Object.keys(store).length,
          reviews: store
        };
        var blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"});
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "review-" + REPORT_ID + ".json";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(function(){ URL.revokeObjectURL(a.href); }, 1500);
      });
    });
  }
  function bindVideoJumps(){
    var buttons = document.querySelectorAll(".video-jump");
    Array.prototype.forEach.call(buttons, function(btn){
      btn.addEventListener("click", function(){
        var card = btn.closest(".case-card");
        if (!card) return;
        var video = card.querySelector("video");
        if (!video) return;
        var sec = parseFloat(btn.getAttribute("data-time"));
        if (!isFinite(sec) || sec < 0){
          var step = parseFloat(btn.getAttribute("data-step"));
          var steps = parseFloat(card.getAttribute("data-steps"));
          if (isFinite(step) && isFinite(steps) && steps > 0 && isFinite(video.duration) && video.duration > 0){
            sec = video.duration * step / steps;
          }
        }
        if (!isFinite(sec) || sec < 0) return;
        if (isFinite(video.duration) && video.duration > 0){
          sec = Math.min(sec, Math.max(video.duration - 0.15, 0));
        }
        try { video.currentTime = sec; } catch (e) { return; }
        var p = video.play();
        if (p && p.catch) p.catch(function(){});
      });
    });
  }
  function applyFilters(){
    var scope = document.querySelector("[data-filter-scope]");
    var cards = document.querySelectorAll(".case-card");
    var rows = document.querySelectorAll("tr.case-row");
    if (!scope && !cards.length && !rows.length) return;
    function val(name){
      var el = scope ? scope.querySelector('[data-filter="' + name + '"]') : null;
      return el ? String(el.value || "").trim() : "";
    }
    var kw = (val("kw") + "").toLowerCase();
    var suites = val("suite");
    var level = val("level");
    var target = val("target");
    var verdict = val("verdict");
    var injection = val("injection");
    var recovery = val("recovery");
    var review = val("review");
    var visible = 0;
    var store = loadAll();
    function matches(el){
      if (suites && el.getAttribute("data-suite") !== suites) return false;
      if (level && el.getAttribute("data-level") !== level) return false;
      if (target && el.getAttribute("data-target") !== target) return false;
      if (verdict && el.getAttribute("data-verdict") !== verdict) return false;
      if (injection && el.getAttribute("data-injection-valid") !== injection) return false;
      if (recovery && el.getAttribute("data-recovery-state") !== recovery) return false;
      var caseId = el.getAttribute("data-case-id") || "";
      if (review){
        var entry = store[caseId] || {};
        var reviewed = hasReview(entry);
        if (review === "reviewed" && !reviewed) return false;
        if (review === "pending" && reviewed) return false;
      }
      if (kw){
        var hay = (caseId + " " + (el.getAttribute("data-search") || "")).toLowerCase();
        if (hay.indexOf(kw) < 0) return false;
      }
      return true;
    }
    Array.prototype.forEach.call(cards, function(card){
      var ok = matches(card);
      card.hidden = !ok;
      if (ok) visible += 1;
    });
    Array.prototype.forEach.call(rows, function(row){
      var ok = matches(row);
      row.hidden = !ok;
      if (ok) visible += 1;
    });
    Array.prototype.forEach.call(document.querySelectorAll(".task-group"), function(group){
      var any = false;
      Array.prototype.forEach.call(group.querySelectorAll(".case-card"), function(card){
        if (!card.hidden) any = true;
      });
      group.hidden = !any;
    });
    var counter = document.getElementById("filter-count");
    if (counter){
      var total = cards.length ? cards.length : rows.length;
      counter.textContent = "显示 " + visible + " / " + total + " case";
    }
  }
  function bindFilters(){
    var scope = document.querySelector("[data-filter-scope]");
    if (!scope) return;
    Array.prototype.forEach.call(scope.querySelectorAll("[data-filter]"), function(el){
      el.addEventListener("input", applyFilters);
      el.addEventListener("change", applyFilters);
    });
    Array.prototype.forEach.call(document.querySelectorAll(".js-reset-filters"), function(btn){
      btn.addEventListener("click", function(){
        Array.prototype.forEach.call(scope.querySelectorAll("[data-filter]"), function(el){
          if (el.type === "checkbox") el.checked = false;
          else el.value = "";
        });
        applyFilters();
      });
    });
    applyFilters();
  }
  function boot(){
    bindReview();
    bindExport();
    bindVideoJumps();
    bindFilters();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
"""


# --------------------------------------------------------------------------- #
# render helpers
# --------------------------------------------------------------------------- #
def attr(value: Any) -> str:
    return esc(value)


def badge(text: str, klass: str = "") -> str:
    return f'<span class="badge {klass}">{esc(text)}</span>'


def verdict_badge(verdict: str) -> str:
    label = VERDICT_LABELS.get(verdict, verdict)
    klass = VERDICT_CLASS.get(verdict, "na")
    return f'<span class="badge {klass}">{esc(label)}</span>'


def meta_grid(items: Sequence[tuple[str, Any]]) -> str:
    rows = "".join(
        f"<dt>{esc(label)}</dt><dd>{value if isinstance(value, str) and value.startswith('<') else esc(value)}</dd>"
        for label, value in items
    )
    return f'<dl class="meta-grid">{rows}</dl>'


def kpi_card(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="kpi"><div class="kpi-label">{esc(label)}</div>'
        f'<div class="kpi-value">{value}</div>{sub_html}</div>'
    )


def table(headers: Sequence[str], rows: Sequence[Sequence[str]], *, classes: str = "dt") -> str:
    text_headers = {"门控", "分组", "判定", "字段", "说明", "类型", "指令", "审核判定"}
    numeric_cols = {i for i, header in enumerate(headers) if i > 0 and header not in text_headers}
    head = "".join(
        f'<th class="num">{esc(header)}</th>' if i in numeric_cols else f"<th>{esc(header)}</th>"
        for i, header in enumerate(headers)
    )
    body = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            klass = ' class="num"' if i in numeric_cols else ""
            cells.append(f"<td{klass}>{cell}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        f'<table class="{classes}"><thead><tr>{head}</tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table>"
    )


def rate_cell(k: int, n: int) -> str:
    if n == 0:
        return "N/A"
    return f"{k}/{n}<br><span class='mono'>{pct_ci(k, n)}</span>"


def video_time(case: Mapping[str, Any], key: str) -> float | None:
    video = case.get("video") or {}
    fps = video.get("fps") or 20
    steps = case.get("steps") or case.get("max_steps") or 0
    if key == "injection":
        value = video.get("injection_time_s")
        return float(value) if value is not None else None
    if key == "restore":
        step = case.get("restored_at_step")
        return float(step) / float(fps) if step is not None else None
    if key == "end":
        return float(steps) / float(fps) if steps else None
    return None


def case_facts(case: Mapping[str, Any]) -> dict[str, Any]:
    injection = case.get("injection") or {}
    return {
        "case_id": case.get("case_id"),
        "suite": case.get("suite"),
        "task_idx": case.get("task_idx"),
        "bddl_name": case.get("bddl_name"),
        "instruction": case.get("instruction"),
        "level": case.get("level"),
        "param": case.get("param"),
        "target": case.get("target"),
        "family": case.get("family"),
        "semantics": case.get("semantics"),
        "expected_relation_after": case.get("expected_relation_after"),
        "verdict": case.get("verdict"),
        "trigger_reached": case.get("trigger_reached"),
        "trigger_step": case.get("trigger_step"),
        "injection_step": case.get("injection_step"),
        "injection_wait_steps": case.get("injection_wait_steps"),
        "trigger_skipped_reason": case.get("trigger_skipped_reason"),
        "injection_valid": case.get("injection_valid"),
        "injection_gates": {gate: _validity(case).get(gate) for gate in GATE_ORDER},
        "penetration_m": injection.get("penetration_m"),
        "max_velocity": injection.get("max_velocity"),
        "restorable": injection.get("restorable"),
        "restore_probe": injection.get("restore_probe"),
        "geometry": injection.get("geometry"),
        "recovery": {
            "relation_before": case.get("relation_before"),
            "relation_after_injection": case.get("relation_after_injection"),
            "relation_final": case.get("relation_final"),
            "recovered": case.get("recovered"),
            "restored_at_step": case.get("restored_at_step"),
            "notice_latency": case.get("notice_latency"),
            "repair_budget_steps": case.get("repair_budget_steps"),
            "termination": case.get("termination"),
            "steps": case.get("steps"),
            "success": case.get("success"),
            "recovery_na": _recovery_na(case),
        },
        "video": case.get("video"),
    }


def case_facts_json(case: Mapping[str, Any]) -> str:
    payload = json.dumps(case_facts(case), ensure_ascii=False).replace("<", "\\u003c")
    return f'<script type="application/json" class="case-facts">{payload}</script>'


def _recovery_na(case: Mapping[str, Any]) -> bool:
    return (not case.get("trigger_reached")) or case.get("level") == "C0"


def render_case_card(case: Mapping[str, Any], *, video_root: Path, page_suite: str | None = None) -> str:
    case_id = str(case.get("case_id"))
    level = str(case.get("level"))
    target = str(case.get("target"))
    family = str(case.get("family"))
    verdict = str(case.get("verdict"))
    injection = case.get("injection") or {}
    geometry = injection.get("geometry") or {}
    validity = _validity(case)
    recovery_na = _recovery_na(case)
    available = bool((case.get("video") or {}).get("available"))
    video = case.get("video") or {}
    steps = case.get("steps") or case.get("max_steps")
    fps = video.get("fps") or 20
    search = " ".join(
        str(case.get(key) or "")
        for key in ("case_id", "instruction", "bddl_name", "family", "target", "level", "task_idx")
    )

    injection_rows = []
    for gate in GATE_ORDER:
        expected = _gate_expectation(case, gate)
        injection_rows.append(
            "<tr>"
            f"<th>{esc(GATE_LABELS[gate])}</th>"
            f"<td>{fmt_gate(validity.get(gate))}</td>"
            f"<td class='mono'>{esc(expected)}</td>"
            "</tr>"
        )
    injection_rows.append(
        "<tr><th>穿透量 penetration_m</th>"
        f"<td class='mono'>{esc(fmt_num(injection.get('penetration_m'), 6))} m</td>"
        f"<td>{'✓ 未穿模' if injection.get('no_penetration') is True else ('✗ 穿模' if injection.get('no_penetration') is False else '未记录')}</td></tr>"
    )
    injection_rows.append(
        "<tr><th>注入后最大速度 max_velocity</th>"
        f"<td class='mono'>{esc(fmt_num(injection.get('max_velocity'), 6))}</td>"
        f"<td>{'✓ 零速度' if injection.get('zero_velocity') is True else ('✗ 有残速' if injection.get('zero_velocity') is False else '未记录')}</td></tr>"
    )
    probe = injection.get("restore_probe") or {}
    injection_rows.append(
        "<tr><th>restore_probe（辅助 oracle）</th>"
        f"<td class='mono' colspan='2'>relation_true_after_state_write={esc(fmt_bool(probe.get('relation_true_after_state_write')))}"
        f" · restored_truth={esc(fmt_list(probe.get('restored_truth')))}"
        f" · reapplied_truth={esc(fmt_list(probe.get('reapplied_truth')))}</td></tr>"
    )
    injection_rows.append(
        "<tr><th>几何量 delta_translation_m</th>"
        f"<td class='mono' colspan='2'>{esc(fmt_num(geometry.get('delta_translation_m')))} m</td></tr>"
    )
    injection_rows.append(
        "<tr><th>几何量 delta_angle_rad</th>"
        f"<td class='mono' colspan='2'>{esc(fmt_num(geometry.get('delta_angle_rad')))} rad</td></tr>"
    )
    injection_rows.append(
        "<tr><th>几何量 delta_joint_max</th>"
        f"<td class='mono' colspan='2'>{esc(fmt_num(geometry.get('delta_joint_max')))} rad</td></tr>"
    )
    injection_rows.append(
        "<tr><th>axis（世界系）</th>"
        f"<td class='mono' colspan='2'>{esc(fmt_list(geometry.get('axis')))}</td></tr>"
    )

    if recovery_na and not case.get("trigger_reached"):
        recovery_rows = [
            ("触发状态", "<span class='badge na'>触发未到达</span>"),
            ("relation_before", "N/A（未注入）"),
            ("relation_after_injection", "N/A（未注入）"),
            ("relation_final", "N/A"),
            ("recovered", "N/A（未注入，不是 0%）"),
            ("trigger_skipped_reason", esc(case.get("trigger_skipped_reason") or "未记录")),
            ("termination / steps", esc(f"{case.get('termination')} / {case.get('steps')}")),
        ]
    elif level == "C0":
        recovery_rows = [
            ("触发状态", "<span class='badge ok'>C0 对照（no-op）</span>"),
            ("relation_before", fmt_bool(case.get("relation_before"))),
            ("relation_after_injection", fmt_bool(case.get("relation_after_injection"))),
            ("relation_final", fmt_bool(case.get("relation_final"))),
            ("recovered / success", f"{fmt_bool(case.get('recovered'))} / {fmt_bool(case.get('success'))}"),
            ("C0 说明", "C0 只延迟 10 步 + 强制继续、不动状态；终局成功说明“延迟/强制继续本身无害”。不计入 Recovery。"),
            ("termination / steps", esc(f"{case.get('termination')} / {case.get('steps')}")),
        ]
    else:
        recovery_rows = [
            ("触发状态", "<span class='badge ok'>触发到达</span>"),
            ("relation_before", fmt_bool(case.get("relation_before"))),
            ("relation_after_injection", fmt_bool(case.get("relation_after_injection"))),
            ("relation_final", fmt_bool(case.get("relation_final"))),
            ("recovered（终局恢复）", fmt_bool(case.get("recovered"))),
            ("restored_at_step", esc(fmt_num(case.get("restored_at_step")))),
            ("notice_latency（步）", esc(fmt_num(case.get("notice_latency")))),
            ("repair_budget_steps", esc(fmt_num(case.get("repair_budget_steps")))),
            ("termination / steps", esc(f"{case.get('termination')} / {case.get('steps')}")),
            ("success / final_goal_truth", f"{fmt_bool(case.get('success'))} / {esc(fmt_list(case.get('final_goal_truth')))}"),
            ("final_revoked_truth", esc(fmt_list(case.get('final_revoked_truth')))),
        ]
    recovery_html = "".join(
        f"<tr><th>{esc(label)}</th><td class='mono'>{value}</td></tr>" for label, value in recovery_rows
    )

    if available:
        video_html = (
            f'<video controls preload="metadata" playsinline muted loop src="{esc(video.get("path"))}"></video>'
            f'<div class="video-meta">文件：<code>{esc(video.get("path"))}</code> · fps {esc(fps)}'
            f' · 注入时刻 {esc(fmt_num(video.get("injection_time_s"), 2))} s'
            f' · 注入帧 {esc(fmt_num(video.get("injection_frame")))}</div>'
        )
    else:
        video_html = (
            '<div class="video-missing">视频缺失：未找到 <code>'
            + esc(video.get("path") or f"videos/{case_id}.mp4")
            + '</code>。视频为本地审核产物（*.mp4 不入库）；请按 <code>videos/README.md</code> 的复制命令生成后再打开报告。'
            + "</div>"
        )

    def jump_button(kind: str, label: str) -> str:
        disabled = ""
        time_value = video_time(case, kind)
        step_value = None
        if kind == "restore":
            step_value = case.get("restored_at_step")
            if step_value is None:
                disabled = " disabled"
        if kind == "injection" and (not case.get("trigger_reached") or time_value is None):
            disabled = " disabled"
        if kind == "end" and not steps:
            disabled = " disabled"
        data_time = "" if time_value is None else f' data-time="{time_value:.4f}"'
        data_step = "" if step_value is None else f' data-step="{step_value}"'
        return (
            f'<button type="button" class="video-jump" data-jump="{kind}"{data_time}{data_step}{disabled}>'
            f"{esc(label)}</button>"
        )

    checked = ""
    return f"""
<article class="case-card" id="case-{esc(case_id)}" data-case-id="{esc(case_id)}"
  data-suite="{esc(case.get('suite'))}" data-level="{esc(level)}" data-target="{esc(target)}"
  data-verdict="{esc(verdict)}" data-injection-valid="{'1' if case.get('injection_valid') else '0'}"
  data-recovery-state="{'na' if recovery_na else ('recovered' if case.get('recovered') else 'not_recovered')}"
  data-steps="{esc(steps)}" data-search="{esc(search)}"{checked}>
  <div class="case-head">
    <div>
      <div class="case-title">{esc(case_id)}</div>
      <div class="case-subline">suite={esc(case.get('suite'))} · task_idx={esc(case.get('task_idx'))} · bddl={esc(case.get('bddl_name') or '未记录')} · expected_relation_after={esc(fmt_bool(case.get('expected_relation_after'), na='未记录'))}</div>
    </div>
    <div class="case-badges">{verdict_badge(verdict)} {badge('level ' + level)} {badge('target ' + target)} {badge('family ' + family)} {badge('semantics ' + str(case.get('semantics')))}</div>
  </div>
  <div class="instruction">指令：{esc(case.get('instruction') or '未记录')}</div>
  <div class="case-grid">
    <div class="panel">
      <h4>① 注入有效性（逐门控）</h4>
      <table>
        <thead><tr><th>门控 / 事实</th><th>结果</th><th>期望/说明</th></tr></thead>
        <tbody>{''.join(injection_rows)}</tbody>
      </table>
      <p class="hint">trigger_step={esc(fmt_num(case.get('trigger_step')))} · injection_step={esc(fmt_num(case.get('injection_step')))} · wait={esc(fmt_num(case.get('injection_wait_steps')))}。硬门控 = 注入前关系真 ∧ 注入后关系假（C0 保持真）∧ 无穿模 ∧ 零速度 ∧ 已释放。</p>
    </div>
    <div class="panel">
      <h4>② 恢复有效性（是否策略自修复）</h4>
      <table><tbody>{recovery_html}</tbody></table>
      <p class="hint">restorable oracle 只证明几何可写回，<b>不是策略恢复</b>；C0 与未触发 case 的 Recovery 为 N/A，不是 0%。</p>
    </div>
    <div class="panel video-panel">
      <h4>③ 视频证据与时间点</h4>
      {video_html}
      <div class="video-buttons">
        {jump_button('injection', '跳到注入')}
        {jump_button('restore', '跳到首次恢复')}
        {jump_button('end', '跳到结束')}
      </div>
      <p class="hint">按钮通过 video.currentTime 跳转；恢复/结束时间点按 step 比例估算（视频时长 × step / steps）。</p>
    </div>
  </div>
  <div class="review-panel">
    <label><input type="checkbox" data-review="injection"> 注入有效</label>
    <label><input type="checkbox" data-review="recovery"> 恢复有效</label>
    <textarea data-review="note" rows="1" placeholder="审核备注（例如：注入帧可见物体被移走；恢复确由策略完成…）"></textarea>
    <span class="review-state">未审核</span>
  </div>
  {case_facts_json(case)}
</article>"""


def _gate_expectation(case: Mapping[str, Any], gate: str) -> str:
    level = str(case.get("level"))
    target = str(case.get("target"))
    if gate == "completed_relation_true_before_intervention":
        return "应为 true"
    if gate == "all_revoked_false_after_intervention":
        return "C0 应为 true；L0/L1/L2 应为 false" if level == "C0" else "应为 false"
    if gate == "goal_preserved_after_pre":
        return "仅 target=pre 时要求 true" if target == "pre" else "N/A（非 pre）"
    if gate == "restorable":
        return "辅助 oracle，不参与硬门控"
    return "应为 true"


def render_task_groups(
    cases: Sequence[Mapping[str, Any]], *, video_root: Path, suite: str
) -> str:
    groups: OrderedDict[Any, list[Mapping[str, Any]]] = OrderedDict()
    for case in cases:
        groups.setdefault(case.get("task_idx"), []).append(case)
    blocks = []
    for task_idx, group in groups.items():
        group = sorted(group, key=case_sort_key)
        first = group[0]
        triggered = sum(1 for c in group if c["trigger_reached"])
        valid = sum(1 for c in group if c["injection_valid"])
        den = [c for c in group if c["injection_valid"] and c["level"] != "C0"]
        num = [c for c in den if c.get("recovered") is True]
        control_ok = sum(1 for c in group if c["level"] == "C0" and c.get("success") is True)
        controls = sum(1 for c in group if c["level"] == "C0")
        recovery_text = "N/A（无有效非 C0）" if not den else f"{len(num)}/{len(den)} = {fmt_pct(len(num), len(den))}"
        blocks.append(
            f'<section class="task-group" data-task="{esc(task_idx)}">'
            f'<div class="task-head" id="task-{esc(task_idx)}">'
            f"<h3>task_idx {esc(task_idx)} · {esc(first.get('bddl_name') or '未记录')}</h3>"
            f'<div class="task-meta">{len(group)} case · 触发 {triggered} · 注入有效 {valid} · '
            f"Recovery {recovery_text} · C0 {control_ok}/{controls}</div></div>"
            f"<p class=\"section-intro\">指令：{esc(first.get('instruction') or '未记录')}</p>"
            + "".join(render_case_card(case, video_root=video_root, page_suite=suite) for case in group)
            + "</section>"
        )
    return "".join(blocks)


def render_sidebar(
    *,
    aggregate: Mapping[str, Any],
    suite_pages: Mapping[str, list[Mapping[str, Any]]],
    current: str,
    current_suite: str | None = None,
    task_ids: Sequence[Any] = (),
) -> str:
    def link(href: str, label: str, klass: str = "lvl2") -> str:
        return f'<a class="{klass}" href="{attr(href)}">{esc(label)}</a>'

    parts = ['<aside class="sidebar"><div class="sidebar-title">报告导航</div><nav>']
    parts.append("<details open><summary>总览</summary>")
    for anchor, label in [
        ("sec-kpi", "关键指标"),
        ("sec-injection", "注入有效性"),
        ("sec-recovery", "恢复有效性"),
        ("sec-reconcile", "数据来源与对账"),
        ("sec-quality", "数据质量与范围"),
        ("sec-notes", "实验备注"),
        ("sec-suites", "分套件页面"),
        ("sec-index", "全部 case 索引"),
        ("sec-method", "生成方法与自检"),
    ]:
        parts.append(link(f"index.html#{anchor}", label))
    parts.append("</details>")
    parts.append("<details open><summary>分套件页面</summary>")
    for suite, pages in suite_pages.items():
        for index, _ in enumerate(pages, 1):
            label = f"{suite} · {index}/{len(pages)}（{len(pages[index - 1])} case）"
            parts.append(link(f"{suite}-part{index}.html", label))
    parts.append("</details>")
    if current == "part" and current_suite:
        parts.append("<details open><summary>本页</summary>")
        parts.append(link("#filters", "筛选器"))
        for task_idx in task_ids:
            parts.append(link(f"#task-{task_idx}", f"task {task_idx}"))
        parts.append(link("#page-cards-start", "逐 case 审核卡"))
        parts.append(link("#export-section", "审核导出"))
        parts.append("</details>")
    parts.append("</nav>")
    parts.append(
        '<p class="legend" style="margin-top:14px">白色主题 · 自包含 · file:// 可开<br>'
        "审核状态保存在浏览器 localStorage，可导出 JSON。</p>"
    )
    parts.append("</aside>")
    return "".join(parts)


def page_head(
    *,
    title: str,
    subtitle: str,
    meta_items: Sequence[tuple[str, str]],
) -> str:
    return (
        '<header class="page-head">'
        f"<h1>{esc(title)}</h1>"
        f'<p class="subtitle">{esc(subtitle)}</p>'
        + meta_grid(meta_items)
        + "</header>"
    )


def export_toolbar() -> str:
    return (
        '<div class="toolbar" id="export-section">'
        '<button type="button" class="primary js-export-review">导出审核 JSON</button>'
        '<span class="muted" id="review-count">已保存审核记录 0 条</span>'
        '<span class="muted">勾选/备注自动保存到浏览器 localStorage（键含报告 ID）；导出的 JSON 可随报告提交或归档。</span>'
        "</div>"
    )


def filters_html(
    *,
    cases: Sequence[Mapping[str, Any]],
    include_suite: bool,
    include_recovery: bool = True,
) -> str:
    suites = sorted({str(c.get("suite")) for c in cases}, key=lambda s: SUITE_ORDER.index(s) if s in SUITE_ORDER else 99)
    levels = [lvl for lvl in LEVEL_ORDER if any(str(c.get("level")) == lvl for c in cases)]
    targets = [t for t in TARGET_ORDER if any(str(c.get("target")) == t for c in cases)]
    verdicts = [v for v in VERDICT_ORDER if any(str(c.get("verdict")) == v for c in cases)]
    parts = ['<div class="filters" id="filters" data-filter-scope>']
    if include_suite:
        parts.append(
            '<label>suite <select data-filter="suite"><option value="">全部</option>'
            + "".join(f'<option value="{attr(s)}">{esc(s)}</option>' for s in suites)
            + "</select></label>"
        )
    parts.append(
        '<label>level <select data-filter="level"><option value="">全部</option>'
        + "".join(f'<option value="{attr(lvl)}">{esc(lvl)}</option>' for lvl in levels)
        + "</select></label>"
    )
    parts.append(
        '<label>target <select data-filter="target"><option value="">全部</option>'
        + "".join(f'<option value="{attr(t)}">{esc(t)}</option>' for t in targets)
        + "</select></label>"
    )
    parts.append(
        '<label>verdict <select data-filter="verdict"><option value="">全部</option>'
        + "".join(
            f'<option value="{attr(v)}">{esc(VERDICT_LABELS.get(v, v))}</option>' for v in verdicts
        )
        + "</select></label>"
    )
    parts.append(
        '<label>注入 <select data-filter="injection"><option value="">全部</option>'
        '<option value="1">注入有效</option><option value="0">注入无效/N/A</option></select></label>'
    )
    if include_recovery:
        parts.append(
            '<label>恢复 <select data-filter="recovery"><option value="">全部</option>'
            '<option value="recovered">已恢复</option><option value="not_recovered">未恢复</option>'
            '<option value="na">N/A（C0/未触发）</option></select></label>'
        )
    parts.append(
        '<label>审核 <select data-filter="review"><option value="">全部</option>'
        '<option value="reviewed">已审核</option><option value="pending">未审核</option></select></label>'
    )
    parts.append('<label>关键字 <input type="search" data-filter="kw" placeholder="case_id / 指令 / bddl"></label>')
    parts.append('<button type="button" class="js-reset-filters">重置筛选</button>')
    parts.append(
        f'<span class="filter-count" id="filter-count">显示 {len(cases)} / {len(cases)} case</span>'
    )
    parts.append("</div>")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# page renderers
# --------------------------------------------------------------------------- #
def render_index(
    *,
    aggregate: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
    suite_pages: Mapping[str, list[Mapping[str, Any]]],
    page_case_index: Mapping[str, str],
    notes_text: str | None,
) -> str:
    meta = aggregate["meta"]
    injection = aggregate["injection"]
    recovery = aggregate["recovery"]
    total = aggregate["case_count"]
    recovery_value = recovery["value"]
    recovery_cell = (
        "N/A"
        if recovery_value is None
        else f"{recovery['numerator']}/{recovery['denominator']} = {100.0 * recovery_value:.1f}%"
    )
    recovery_sub = (
        "分母为 0：N/A"
        if recovery_value is None
        else f"Wilson 95% CI {100.0 * recovery['ci95'][0]:.1f}–{100.0 * recovery['ci95'][1]:.1f}%"
    )
    recovery_ci_text = (
        "N/A"
        if recovery_value is None
        else f"{100.0 * recovery['ci95'][0]:.1f}–{100.0 * recovery['ci95'][1]:.1f}%"
    )
    recovery_pct_text = "N/A" if recovery_value is None else f"{100.0 * recovery_value:.1f}%"
    present_suites = list(recovery["by_suite"].keys())
    missing_suites = [suite for suite in SUITE_ORDER if suite not in present_suites]
    range_text = f"{total} cases · suites {', '.join(present_suites)}" + (
        f"（未跑 suite: {', '.join(missing_suites)}）" if missing_suites else ""
    )
    triggered_rate = injection["trigger_rate"]["value"]
    valid_rate = injection["valid_rate_of_triggered"]["value"]
    control_rate = injection["controls"]["rate"]["value"]
    triggered_rate_text = "N/A" if triggered_rate is None else f"{100.0 * triggered_rate:.1f}%"
    valid_rate_text = "N/A" if valid_rate is None else f"{100.0 * valid_rate:.1f}%"
    control_rate_text = "N/A" if control_rate is None else f"{100.0 * control_rate:.1f}%"
    kpis = "".join(
        [
            kpi_card("总 case 数", str(total), f"goal {recovery['by_suite'].get('goal', {}).get('cases', 0)} / object {recovery['by_suite'].get('object', {}).get('cases', 0)}"),
            kpi_card(
                "触发 all_done",
                f"{injection['triggered']}/{injection['attempted']}",
                f"{triggered_rate_text} · 未触发 {injection['not_triggered']} 条记 N/A",
            ),
            kpi_card(
                "注入有效",
                f"{injection['injection_valid']}/{injection['triggered']}",
                f"占触发 {valid_rate_text} · 无效 {injection['injection_invalid']}",
            ),
            kpi_card(
                "C0 no-op 对照",
                f"{injection['controls']['success']}/{injection['controls']['attempted']}",
                f"control rate {control_rate_text}",
            ),
            kpi_card("Recovery（条件恢复率）", recovery_cell, recovery_sub),
            kpi_card(
                "恢复失败（有效非 C0）",
                str(aggregate["failure_counts"].get("valid_but_not_recovered", 0)),
                "注入有效但终局未恢复",
            ),
        ]
    )

    header = page_head(
        title=str(meta.get("title") or "B 套件注入/恢复有效性审核报告"),
        subtitle="人工审核两件事：① 注入是否真实有效；② 恢复是否真实来自策略自修复。",
        meta_items=[
            ("模型", meta.get("model") or "未记录"),
            ("范围", range_text),
            ("协议", meta.get("protocol") or "未记录"),
            ("数据来源", meta.get("source_run") or "未记录"),
            ("旧报告（只读对账）", meta.get("old_report") or "未提供"),
            ("模板版本", aggregate["template_version"]),
            ("生成时间", meta.get("generated_at") or "未记录"),
            ("报告 ID", meta.get("report_id") or "未记录"),
            ("生成命令", meta.get("command_template") or "未记录"),
        ],
    )

    # 1. injection validity
    gate_rows = []
    for gate in GATE_ORDER:
        info = injection["gates"][gate]
        gate_rows.append(
            [
                esc(info["label"]),
                esc(str(info["passed"])),
                esc(str(info["failed"])),
                esc(str(info["not_recorded"])),
                "硬门控" if info["hard"] else "辅助",
                esc(info["note"]),
            ]
        )
    gate_table = table(
        ["门控", "通过", "未通过", "未记录", "类型", "说明"],
        gate_rows,
    )
    not_triggered_rows = [
        [esc(reason), esc(str(count))] for reason, count in injection["not_triggered_reasons"].items()
    ]
    not_triggered_table = table(["触发未到达原因", "条数"], not_triggered_rows) if not_triggered_rows else "<p class='legend'>本次没有触发未到达 case。</p>"

    # 2. recovery validity
    suite_rows = []
    for suite, stats in recovery["by_suite"].items():
        suite_rows.append(
            [
                esc(suite),
                rate_cell(stats["recovery"]["numerator"], stats["recovery"]["denominator"]),
                rate_cell(stats["control_success"], stats["controls"]),
                esc(f"{stats['triggered']}/{stats['cases']}"),
                esc(str(stats["injection_valid"])),
            ]
        )
    level_rows = [
        [
            esc(level),
            rate_cell(stats["recovery"]["numerator"], stats["recovery"]["denominator"]),
            esc(str(stats["triggered"])),
            esc(str(stats["injection_valid"])),
        ]
        for level, stats in recovery["by_level"].items()
    ]
    target_rows = [
        [
            esc(target),
            rate_cell(stats["recovery"]["numerator"], stats["recovery"]["denominator"]),
            esc(str(stats["triggered"])),
            esc(str(stats["injection_valid"])),
        ]
        for target, stats in recovery["by_target"].items()
    ]
    family_order = sorted(
        recovery["by_family"].items(),
        key=lambda item: (-item[1]["recovery"]["denominator"], item[0]),
    )
    family_rows = [
        [
            esc(family),
            esc(rate_cell(stats["recovery"]["numerator"], stats["recovery"]["denominator"])),
            esc(str(stats["triggered"])),
        ]
        for family, stats in family_order
    ]
    recovery_c0_rows = [
        [esc(suite), esc(f"{stats['success']}/{stats['attempted']}")]
        for suite, stats in recovery["c0_controls"]["by_suite"].items()
    ]

    # 3. reconciliation
    reconciliation = aggregate.get("reconciliation")
    if reconciliation:
        rec_rows = [
            [
                esc(item["label"]),
                esc(json.dumps(item["old"], ensure_ascii=False)),
                esc(json.dumps(item["new"], ensure_ascii=False)),
                "✓ 一致" if item["match"] else "✗ 不一致",
            ]
            for item in reconciliation["checks"]
        ]
        rec_table = (
            table(["对账项", "旧报告", "本次重算", "结果"], rec_rows)
            if rec_rows
            else "<p class='legend'>未提供可对账的旧聚合字段。</p>"
        )
        geometry_rows = [
            [
                esc(item["level"]),
                esc(item["old_mean"]),
                esc(item["old_max"]),
                esc(item["matched_metric"] or "未匹配"),
            ]
            for item in reconciliation["geometry_checks"]
        ]
        geometry_table = (
            table(["level", "旧 mean", "旧 max", "匹配到的量纲"], geometry_rows)
            if geometry_rows
            else "<p class='legend'>旧报告未提供几何量。</p>"
        )
        run_summary = reconciliation.get("run_summary")
        run_summary_html = ""
        if run_summary:
            status = "一致" if run_summary["match"] else "不一致（已解释）"
            run_summary_html = (
                '<div class="notice">'
                f"<b>源 run 汇总文件核对：</b>{esc(run_summary['label'])} 记录 cases={esc(run_summary['cases'])}，"
                f"本次逐 case 重算 cases={esc(run_summary['recomputed_cases'])} → {esc(status)}。"
                f"{esc(run_summary['note'])}"
                "</div>"
            )
        metric_notes_html = (
            "<ul>" + "".join(f"<li>{esc(note)}</li>" for note in reconciliation["metric_notes"]) + "</ul>"
            if reconciliation["metric_notes"]
            else "<p class='legend'>旧报告几何量量纲与本次一致。</p>"
        )
        differences_html = (
            "<ul>" + "".join(f"<li>{esc(json.dumps(item, ensure_ascii=False))}</li>" for item in reconciliation["differences"]) + "</ul>"
            if reconciliation["differences"]
            else "<p class='legend'>所有可比字段一致。</p>"
        )
        reconcile_section = f"""
<h2 id="sec-reconcile">数据来源与对账</h2>
<p class="section-intro">本报告的数字全部由 <code>cases.jsonl</code>（来自源 run 的逐 case <code>summary.json</code>）重算，没有照抄旧报告。下表把本次重算与旧报告的机器可读 <code>aggregate.json</code> 逐项对齐。</p>
<h3>与旧报告 aggregate.json 对账</h3>
{rec_table}
<h3>旧报告几何量口径核对</h3>
{geometry_table}
<div class="note-box">{metric_notes_html}</div>
<h3>差异与解释</h3>
{differences_html}
{run_summary_html}
"""
    else:
        reconcile_section = """
<h2 id="sec-reconcile">数据来源与对账</h2>
<p class="section-intro">生成时未提供 <code>--reconcile-json</code>，因此没有自动对账表；报告数字仍由 <code>cases.jsonl</code> 重算。</p>
"""

    # 4. quality
    quality_html = "".join(f"<li>{esc(item)}</li>" for item in aggregate["data_quality"])

    # 5. notes
    notes_html = (
        f'<pre class="notes-text">{esc(notes_text)}</pre>'
        if notes_text
        else "<p class='legend'>未提供实验备注（<code>--notes</code>）。</p>"
    )

    # 6. suite page cards
    suite_cards = []
    for suite, pages in suite_pages.items():
        stats = recovery["by_suite"].get(suite, {})
        total_cases = sum(len(page) for page in pages)
        page_links = " ".join(
            f'<a class="badge ok" href="{suite}-part{index}.html">part{index} · {len(page)} case</a>'
            for index, page in enumerate(pages, 1)
        )
        suite_cards.append(
            f'<div class="kpi"><div class="kpi-label">{esc(SUITE_LABELS.get(suite, suite))}</div>'
            f'<div class="kpi-value">{total_cases} cases</div>'
            f'<div class="kpi-sub">触发 {stats.get("triggered", 0)} · 注入有效 {stats.get("injection_valid", 0)} · '
            f'Recovery {rate_cell(stats.get("recovery", {}).get("numerator", 0), stats.get("recovery", {}).get("denominator", 0))}</div>'
            f'<div style="margin-top:8px">{page_links}</div></div>'
        )

    # 7. full case index
    index_rows = []
    for number, case in enumerate(cases, 1):
        case_id = str(case["case_id"])
        href = page_case_index[case_id]
        video_ok = bool((case.get("video") or {}).get("available"))
        video_cell = (
            f'<a href="{esc((case.get("video") or {}).get("path"))}">视频</a>'
            if video_ok
            else "<span class='badge warn'>缺失</span>"
        )
        index_rows.append(
            f'<tr class="case-row" data-case-id="{esc(case_id)}" data-suite="{esc(case.get("suite"))}" '
            f'data-level="{esc(case.get("level"))}" data-target="{esc(case.get("target"))}" '
            f'data-verdict="{esc(case.get("verdict"))}" data-injection-valid="{"1" if case.get("injection_valid") else "0"}" '
            f'data-recovery-state="{esc("na" if _recovery_na(case) else ("recovered" if case.get("recovered") else "not_recovered"))}" '
            f'data-search="{esc(" ".join(str(case.get(k) or "") for k in ("case_id", "instruction", "bddl_name", "family", "task_idx", "target", "level")))}">'
            f"<td class='num'>{number}</td>"
            f'<td class="mono"><a href="{esc(href)}">{esc(case_id)}</a></td>'
            f"<td>{esc(case.get('suite'))}</td>"
            f"<td class='mono'>{esc(case.get('level'))}{'/' + esc(case.get('param')) if case.get('param') else ''}</td>"
            f"<td>{esc(case.get('target'))}</td>"
            f"<td>{esc(case.get('family'))}</td>"
            f"<td>{esc(_short(case.get('instruction'), 44))}</td>"
            f"<td>{verdict_badge(str(case.get('verdict')))}</td>"
            f"<td>{'✓ 有效' if case.get('injection_valid') else ('— 未触发' if not case.get('trigger_reached') else '✗ 无效')}</td>"
            f"<td>{'N/A' if _recovery_na(case) else ('✓ 恢复' if case.get('recovered') else '✗ 未恢复')}</td>"
            f"<td>{video_cell}</td>"
            f'<td><span class="badge na" data-review-mark="{esc(case_id)}">未审核</span></td>'
            "</tr>"
        )
    index_table = (
        '<table class="dt" id="case-index-table"><thead><tr>'
        "<th>#</th><th>case_id</th><th>suite</th><th>level</th><th>target</th><th>family</th>"
        "<th>指令</th><th>审核判定</th><th>注入</th><th>Recovery</th><th>视频</th><th>审核状态</th>"
        f"</tr></thead><tbody>{''.join(index_rows)}</tbody></table>"
    )

    method_html = f"""
<h2 id="sec-method">生成方法与自检</h2>
<div class="note-box">
<ul>
<li>生成器：<code>scripts/build_review_report.py</code>（模板版本 <code>{esc(aggregate['template_version'])}</code>）。</li>
<li>生成命令（主机路径已脱敏；实际执行时把 <code>&lt;B_RUN_DIR&gt;</code> 指向源 run）：<br><code>{esc(meta.get('command_template') or '未记录')}</code></li>
<li>输入 bundle：<code>cases.jsonl</code>（每行一个 case，来自源 run 的逐 case <code>summary.json</code>；原始数值不改写，仅补派生判定字段）。</li>
<li>派生字段口径：<code>injection_valid = trigger_reached ∧ 5 个硬门控全通过</code>；<code>verdict</code> 按注入有效性、C0/非 C0、recovered 派生。</li>
<li>数字来源：<code>evidence.json</code>；页面上的 KPI、总表、case 卡、索引表都由同一聚合对象渲染。Recovery 分母 = 注入有效且非 C0；N/A 不显示为 0%。</li>
<li>自包含：页面内联全部 CSS/JS，不引用 CDN/字体/网络资源；<code>file://</code> 双击可打开。</li>
<li>审核持久化：勾选与备注写入浏览器 <code>localStorage</code>（键含报告 ID <code>{esc(meta.get('report_id'))}</code>）；「导出审核 JSON」按钮下载 <code>review-{esc(meta.get('report_id'))}.json</code>。</li>
<li>视频：<code>videos/&lt;case_id&gt;.mp4</code> 为本地审核产物，<code>*.mp4</code> 已被 <code>.gitignore</code> 忽略、不入库；缺失时卡片显式提示，不静默跳过。</li>
</ul>
<p class="legend">交付前自检：① 白色主题且无外链；② 注入/恢复字段齐全；③ 分母与 N/A 口径一致；④ 索引 165 条链接到对应 case 锚点；⑤ 两个审核勾选 + 备注可持久化/导出；⑥ 视频缺失有显式提示。</p>
</div>
"""

    body = f"""
<div class="layout">
  {render_sidebar(aggregate=aggregate, suite_pages=suite_pages, current='index')}
  <main class="main-col">
    {header}
    {export_toolbar()}
    <h2 id="sec-kpi">关键指标</h2>
    <div class="kpi-grid">{kpis}</div>
    <div class="formula">Recovery 分母 = <b>注入有效且非 C0</b> = {recovery['denominator']}；分子 = 终局恢复 = {recovery['numerator']}。
    C0 只做 no-op 对照；触发未到达（{injection['not_triggered']} 条）与注入无效（{injection['injection_invalid']} 条）都不进 Recovery 分母，<b>N/A 不是 0%</b>。</div>

    <h2 id="sec-injection">注入有效性总表</h2>
    <p class="section-intro">门控定义：所有计数均来自源 run 的 {total} 个 <code>summary.json</code>。<b>restorable 是辅助 oracle，不是策略恢复，也不参与硬门控</b>。</p>
    {gate_table}
    <h3>触发未到达拆解（N/A，不计入 Recovery 分母）</h3>
    {not_triggered_table}
    <div class="note-box">注入有效性判定：<code>trigger_reached ∧ completed_relation_true_before_intervention ∧ all_revoked_false_after_intervention ∧ no_object_penetration ∧ zero_velocity_after_intervention ∧ object_released_before_intervention</code>。
    本报告本次重算：触发 {injection['triggered']}/{injection['attempted']}，注入有效 {injection['injection_valid']}/{injection['triggered']}，注入无效 {injection['injection_invalid']} 条。</div>

    <h2 id="sec-recovery">恢复有效性总表</h2>
    <p class="section-intro">{esc(recovery['definition'])}　{esc(recovery['na_rule'])}</p>
    <div class="formula">整体：<b>{recovery['numerator']}/{recovery['denominator']}</b> = {recovery_pct_text}；Wilson 95% CI {recovery_ci_text}。</div>
    <h3>按 suite</h3>
    {table(['suite', 'Recovery（条件恢复率）', 'C0 对照成功率', '触发/总数', '注入有效'], suite_rows)}
    <h3>按 level</h3>
    {table(['level', 'Recovery（条件恢复率）', '触发', '注入有效'], level_rows)}
    <h3>按 target</h3>
    {table(['target', 'Recovery（条件恢复率）', '触发', '注入有效'], target_rows)}
    <h3>按 family</h3>
    {table(['family', 'Recovery（条件恢复率）', '触发'], family_rows)}
    <h3>C0 no-op 对照</h3>
    {table(['suite', 'C0 终局成功 / 条数'], recovery_c0_rows)}
    <div class="note-box"><b>恢复证据字段</b><ul>{''.join(f'<li><code>{esc(field)}</code>：{esc(note)}</li>' for field, note in RECOVERY_FIELD_NOTES)}</ul></div>

    {reconcile_section}

    <h2 id="sec-quality">数据质量与范围</h2>
    <div class="note-box"><ul>{quality_html}</ul></div>

    <h2 id="sec-notes">实验备注</h2>
    {notes_html}

    <h2 id="sec-suites">分套件页面</h2>
    <div class="kpi-grid">{''.join(suite_cards)}</div>
    <p class="legend">共 {len(suite_pages)} 个 suite、{sum(len(pages) for pages in suite_pages.values())} 个分页页面；每页 {meta.get('per_page')} 条 case。</p>

    <h2 id="sec-index">全部 case 索引（{total} 条）</h2>
    {filters_html(cases=cases, include_suite=True)}
    {index_table}

    {method_html}
    <footer class="legend" style="margin-top:28px;border-top:1px solid var(--line);padding-top:10px">
      {esc(aggregate['template_version'])} · 生成时间 {esc(meta.get('generated_at'))} · 报告 ID {esc(meta.get('report_id'))} · 本页自包含、无外链。
    </footer>
  </main>
</div>
"""
    return html_document(title=str(meta.get("title") or "审核报告"), body=body, report_id=str(meta.get("report_id")), template_version=aggregate["template_version"])


def _short(value: Any, length: int) -> str:
    text = str(value or "")
    return text if len(text) <= length else text[: length - 1] + "…"


def render_part_page(
    *,
    aggregate: Mapping[str, Any],
    suite: str,
    part_index: int,
    part_total: int,
    page_cases: Sequence[Mapping[str, Any]],
    suite_pages: Mapping[str, list[Mapping[str, Any]]],
    notes_text: str | None,
) -> str:
    meta = aggregate["meta"]
    recovery = aggregate["recovery"]
    suite_stats = recovery["by_suite"].get(suite, {})
    total_cases = sum(len(page) for page in suite_pages[suite])
    task_ids: list[Any] = []
    for case in page_cases:
        if case.get("task_idx") not in task_ids:
            task_ids.append(case.get("task_idx"))
    rec = suite_stats.get("recovery", {})
    ctrl_ok = suite_stats.get("control_success", 0)
    ctrl_n = suite_stats.get("controls", 0)
    kpis = "".join(
        [
            kpi_card("suite", suite, f"本页 {len(page_cases)} / 全 suite {total_cases} · 第 {part_index}/{part_total} 页"),
            kpi_card(
                "触发 / 注入有效",
                f"{suite_stats.get('triggered', 0)}/{suite_stats.get('cases', 0)}",
                f"注入有效 {suite_stats.get('injection_valid', 0)} 条",
            ),
            kpi_card("Recovery", rate_cell(rec.get("numerator", 0), rec.get("denominator", 0)), "分母 = 注入有效且非 C0"),
            kpi_card("C0 对照", f"{ctrl_ok}/{ctrl_n}", "no-op 终局成功"),
        ]
    )
    video_root = Path(".")
    pager = ['<div class="pager">']
    pager.append('<a class="badge ok" href="index.html">← 返回总览</a>')
    if part_index > 1:
        pager.append(f'<a class="badge" href="{suite}-part{part_index - 1}.html">← 上一页</a>')
    for index in range(1, part_total + 1):
        if index == part_index:
            pager.append(f'<span class="badge ok">第 {index} 页</span>')
        else:
            pager.append(f'<a class="badge" href="{suite}-part{index}.html">第 {index} 页</a>')
    if part_index < part_total:
        pager.append(f'<a class="badge" href="{suite}-part{part_index + 1}.html">下一页 →</a>')
    pager.append("</div>")
    body = f"""
<div class="layout">
  {render_sidebar(aggregate=aggregate, suite_pages=suite_pages, current='part', current_suite=suite, task_ids=task_ids)}
  <main class="main-col">
    {page_head(
        title=f"{suite} · 注入/恢复有效性逐 case 审核（第 {part_index}/{part_total} 页）",
        subtitle=f"模型 {meta.get('model') or '未记录'} · 协议 {meta.get('protocol') or '未记录'} · 数据来源 {meta.get('source_run') or '未记录'}",
        meta_items=[
            ("suite", suite),
            ("本页 case 数", str(len(page_cases))),
            ("模板版本", aggregate["template_version"]),
            ("生成时间", meta.get("generated_at") or "未记录"),
            ("报告 ID", meta.get("report_id") or "未记录"),
            ("生成命令", meta.get("command_template") or "未记录"),
        ],
    )}
    <div class="kpi-grid">{kpis}</div>
    {filters_html(cases=page_cases, include_suite=False, include_recovery=True)}
    {export_toolbar()}
    <p class="section-intro" id="page-cards-start">每个 case 两个人工审核勾选：<b>注入有效</b> / <b>恢复有效</b>；备注与勾选写入 localStorage。卡片可折叠查看注入门控、恢复证据与视频时间点跳转。</p>
    {render_task_groups(page_cases, video_root=video_root, suite=suite)}
    {''.join(pager)}
    <footer class="legend" style="margin-top:28px;border-top:1px solid var(--line);padding-top:10px">
      {esc(aggregate['template_version'])} · 生成时间 {esc(meta.get('generated_at'))} · 报告 ID {esc(meta.get('report_id'))} · 本页自包含、无外链。
    </footer>
  </main>
</div>
"""
    return html_document(
        title=f"{suite} part{part_index} · 审核报告",
        body=body,
        report_id=str(meta.get("report_id")),
        template_version=aggregate["template_version"],
    )


def html_document(*, title: str, body: str, report_id: str, template_version: str) -> str:
    js = BASE_JS.replace("__REPORT_ID__", report_id).replace("__TEMPLATE_VERSION__", template_version)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{BASE_CSS}</style>
</head>
<body>
{body}
<script>{js}</script>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# README / videos README / provenance
# --------------------------------------------------------------------------- #
def write_report_readme(
    out_dir: Path,
    *,
    aggregate: Mapping[str, Any],
    files: Sequence[str],
) -> None:
    meta = aggregate["meta"]
    recovery = aggregate["recovery"]
    rec_text = (
        "N/A"
        if recovery["value"] is None
        else f"{recovery['numerator']}/{recovery['denominator']} = {100.0 * recovery['value']:.1f}%"
    )
    text = f"""# {meta.get('title')}

本目录是 **注入有效性 / 恢复有效性人工审核报告**，由 `scripts/build_review_report.py`
（模板版本 `{aggregate['template_version']}`）生成。**双击 `index.html` 即可用 `file://` 打开**，
页面内联全部 CSS/JS，不依赖 CDN、字体或任何网络资源。

## 1. 这份报告审核什么

每个 case 需要人工确认两件事：

1. **注入是否真实有效**（注入前关系为真、注入后关系为假 / C0 保持为真、无穿模、零速度、已释放）；
2. **恢复是否真实来自策略自修复**（不是 `restorable` 状态写回 oracle、不是外部复原、不是触发未到达误判）。

报告明确区分：注入无效 ≠ 模型失败；触发未到达 = `N/A`（不是 0%）；C0 只做 no-op 对照、不进 Recovery 分母。

## 2. 关键数字（来自本报告重算，详见 `evidence.json`）

| 指标 | 值 |
|---|---|
| 模型 | {meta.get('model') or '未记录'} |
| 范围 | {aggregate['case_count']} cases（suite: {', '.join(aggregate['recovery']['by_suite'])}；未包含 suite: {', '.join(s for s in SUITE_ORDER if s not in aggregate['recovery']['by_suite']) or '无'}） |
| 协议 | {meta.get('protocol') or '未记录'} |
| 触发 all_done | {aggregate['injection']['triggered']}/{aggregate['injection']['attempted']} |
| 注入有效 | {aggregate['injection']['injection_valid']}/{aggregate['injection']['triggered']} |
| C0 对照 | {aggregate['injection']['controls']['success']}/{aggregate['injection']['controls']['attempted']} |
| Recovery（条件恢复率） | {rec_text} |

## 3. 文件清单

{chr(10).join(f'- `{name}`' for name in files)}

`videos/` 为本地审核产物，`*.mp4` 已被 `.gitignore` 忽略、不入库；复制命令见 `videos/README.md`。

## 4. 人工审核流程

1. 打开 `index.html`，先看「关键指标 / 注入有效性 / 恢复有效性 / 数据来源与对账」；
2. 进入某个 suite 的分页，用筛选器按 level / target / verdict / 恢复状态 / 关键字定位；
3. 逐 case 核对注入门控与恢复证据，播放视频并用「跳到注入 / 跳到首次恢复 / 跳到结束」定位；
4. 勾选 **注入有效** / **恢复有效**，填写备注；状态自动存 `localStorage`（键含报告 ID）；
5. 点「导出审核 JSON」下载 `review-{meta.get('report_id')}.json`，随报告一起归档。

## 5. 重新生成

```bash
python scripts/build_review_report.py \\
  --from-run <B_RUN_DIR> \\
  --out <OUT_DIR> \\
  --title "{meta.get('title')}" \\
  --model {meta.get('model') or 'pi05'} \\
  --protocol "{meta.get('protocol') or DEFAULT_PROTOCOL}" \\
  --source-run "{meta.get('source_run') or 'libero-compose:/runs/...'}"
```

`<B_RUN_DIR>` 指向包含 `<suite>/<case_id>/summary.json` 的源 run 目录；
本报告所有数字都由这些 `summary.json` 重算，不照抄任何旧报告。
"""
    (out_dir / "README.md").write_text(text, encoding="utf-8")


def write_videos_readme(
    out_dir: Path,
    *,
    cases: Sequence[Mapping[str, Any]],
    source_run: str | None,
    suites: Sequence[str],
) -> None:
    available = sum(1 for case in cases if video_available(case, out_dir / "videos"))
    suite_globs = " ".join(f'"$B_RUN"/{suite}/*/video.mp4' for suite in suites)
    text = f"""# videos/ — 本地审核产物（不入库）

本目录存放逐 case 的审核视频，文件名 `<case_id>.mp4`，供报告中的
「跳到注入 / 跳到首次恢复 / 跳到结束」以及人工逐条核对使用。

> **视频不入库**：仓库 `.gitignore` 已忽略 `*.mp4`；本目录只保留本 README。
> 生成时检测到 **{available}/{len(cases)}** 个视频；缺失的 case 在报告卡片上显示
> 「视频缺失」，不会静默跳过。

## 从源 run 复制（推荐硬链，省磁盘）

源 run 标记：`{source_run or '未记录'}`（实际主机路径由执行者用 `B_RUN` 指定）。

```bash
B_RUN=<源 run 目录>            # 例：libero-compose 仓的 runs/b-matrix/full-20261118
REPORT_DIR=<本报告目录>        # 例：experiments/b-rollback/report-goal-object-20261118
mkdir -p "$REPORT_DIR/videos"
for f in {suite_globs}; do
  [ -f "$f" ] || continue
  cid=$(basename "$(dirname "$f")")
  ln -f "$f" "$REPORT_DIR/videos/$cid.mp4" 2>/dev/null || cp -f "$f" "$REPORT_DIR/videos/$cid.mp4"
done
```

只允许复制/硬链，**不得修改或移动源 run 的原始文件**。

## 命名约定

- 报告中的视频路径统一为 `videos/<case_id>.mp4`（相对 `index.html`）；
- `summary.json` 里的 `video.path` 是源 run 的主机绝对路径，生成器不会把它写入报告；
  `evidence.json` 只保存相对路径与 fps / 注入帧等数值。
"""
    ensure_dir(out_dir / "videos")
    (out_dir / "videos" / "README.md").write_text(text, encoding="utf-8")


def write_provenance(
    out_dir: Path,
    *,
    aggregate: Mapping[str, Any],
    args: argparse.Namespace,
    files: Sequence[str],
    migrated_sources: Mapping[str, Any] | None = None,
) -> None:
    meta = aggregate["meta"]
    hashes = OrderedDict()
    for rel in files:
        path = out_dir / rel
        if path.is_file():
            hashes[rel] = sha256_file(path)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "template_version": aggregate["template_version"],
        "generated_at": meta.get("generated_at"),
        "model": meta.get("model"),
        "protocol": meta.get("protocol"),
        "source_run": meta.get("source_run"),
        "old_report": meta.get("old_report"),
        "report_id": meta.get("report_id"),
        "report_dir": meta.get("report_dir"),
        "case_count": aggregate["case_count"],
        "command_template": meta.get("command_template"),
        "reconcile_file": "<OLD_REPORT_DIR>/aggregate.json" if args.reconcile_json else None,
        "run_summary_file": "<B_RUN_DIR>/run-summary.json" if args.run_summary else None,
        "migrated_sources": dict(migrated_sources or {}),
        "sha256": hashes,
        "notes": [
            "所有数字由 cases.jsonl 重算；cases.jsonl 由源 run 的逐 case summary.json 抽取，原始数值不改写。",
            "报告不含主机绝对路径；源/旧报告以仓内相对标记记录。",
            "videos/*.mp4 为本地审核产物，不入库，不计入 sha256 清单。",
        ],
    }
    (out_dir / "provenance.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# --------------------------------------------------------------------------- #
# command-line interface
# --------------------------------------------------------------------------- #
def sanitize_path(value: str | None, *, placeholder: str) -> str | None:
    if not value:
        return None
    path = Path(value)
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return placeholder


def build_command_template(args: argparse.Namespace) -> str:
    parts = ["python scripts/build_review_report.py"]
    if args.from_run:
        parts += ["--from-run", "<B_RUN_DIR>"]
    else:
        parts += ["--cases", sanitize_path(args.cases, placeholder="<CASES_JSONL>") or "<CASES_JSONL>"]
    parts += ["--out", sanitize_path(args.out, placeholder="<OUT_DIR>") or "<OUT_DIR>"]
    parts += ["--title", shlex.quote(str(args.title))]
    parts += ["--model", shlex.quote(str(args.model))]
    parts += ["--protocol", shlex.quote(str(args.protocol))]
    if args.source_run:
        parts += ["--source-run", shlex.quote(str(args.source_run))]
    if args.old_report:
        parts += ["--old-report", shlex.quote(str(args.old_report))]
    if args.reconcile_json:
        parts += ["--reconcile-json", "<OLD_REPORT_DIR>/aggregate.json"]
    if args.run_summary:
        parts += ["--run-summary", "<B_RUN_DIR>/run-summary.json"]
    if args.notes:
        parts += ["--notes", sanitize_path(args.notes, placeholder="<NOTES>") or "<NOTES>"]
    if args.video_dir:
        parts += ["--video-dir", sanitize_path(args.video_dir, placeholder="<VIDEO_DIR>") or "<VIDEO_DIR>"]
    parts += ["--template-version", shlex.quote(str(args.template_version))]
    parts += ["--per-page", str(args.per_page)]
    if args.generated_at:
        parts += ["--generated-at", shlex.quote(str(args.generated_at))]
    for item in args.extra_file or []:
        parts += ["--extra-file", sanitize_path(item, placeholder="<EXTRA_FILE>") or "<EXTRA_FILE>"]
    for item in args.migrated_source or []:
        rel = item.partition("=")[0]
        parts += [
            "--migrated-source",
            shlex.quote(f"{rel}=<OLD_REPORT_DIR>/{Path(rel).name}"),
        ]
    return " ".join(parts)


def make_report_id(title: str, model: str, source_run: str | None) -> str:
    seed = f"{title}|{model}|{source_run or ''}"
    return "rr-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a self-contained white-theme injection/recovery review report.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--cases", help="review bundle JSONL (one case per line)")
    parser.add_argument("--from-run", help="build the bundle from <run>/<suite>/<case_id>/summary.json")
    parser.add_argument("--out", required=True, help="output report directory")
    parser.add_argument("--title", default="B 套件注入/恢复有效性审核报告", help="report title")
    parser.add_argument("--model", default="未记录", help="model id, e.g. pi05")
    parser.add_argument("--protocol", default=DEFAULT_PROTOCOL, help="evaluation protocol summary")
    parser.add_argument("--source-run", default=None, help="source run marker, e.g. libero-compose:/runs/...")
    parser.add_argument("--video-dir", default=None, help="directory holding <case_id>.mp4 (default: <out>/videos)")
    parser.add_argument("--template-version", default=TEMPLATE_VERSION, help="template version string")
    parser.add_argument("--notes", default=None, help="optional notes file rendered on the index page")
    parser.add_argument("--split-by", default="suite", choices=["suite"], help="page split dimension")
    parser.add_argument("--per-page", type=int, default=60, help="cases per suite page")
    parser.add_argument("--report-id", default=None, help="localStorage report id (default: derived)")
    parser.add_argument("--old-report", default=None, help="old report marker for provenance/reconciliation")
    parser.add_argument("--reconcile-json", default=None, help="old aggregate.json for reproduction checks")
    parser.add_argument("--run-summary", default=None, help="run-summary.json for discrepancy checks")
    parser.add_argument("--extra-file", action="append", default=[], help="extra file to hash in provenance (repeatable)")
    parser.add_argument(
        "--migrated-source",
        action="append",
        default=[],
        metavar="REL=PATH",
        help="migrated artifact REL plus the source file PATH; provenance records both sha256 (repeatable)",
    )
    parser.add_argument("--generated-at", default=None, help="ISO-8601 generation time (default: now, +08:00)")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.cases and not args.from_run:
        raise SystemExit("either --cases or --from-run is required")
    if args.per_page < 1:
        raise SystemExit("--per-page must be >= 1")

    out_dir = ensure_dir(Path(args.out))
    video_dir = Path(args.video_dir) if args.video_dir else out_dir / "videos"
    ensure_dir(video_dir)

    missing_summaries: list[str] = []
    if args.from_run:
        cases, missing_summaries = build_cases_from_run(Path(args.from_run))
    else:
        cases = load_cases_jsonl(Path(args.cases))
    cases = sorted(cases, key=case_sort_key)

    # canonical bundle: always keep <out>/cases.jsonl so the report is reproducible.
    cases_path = out_dir / "cases.jsonl"
    write_cases_jsonl(cases_path, cases)

    generated_at = parse_iso(args.generated_at)
    report_id = args.report_id or make_report_id(args.title, args.model, args.source_run)
    command_template = build_command_template(args)
    try:
        report_dir = out_dir.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        report_dir = "<OUT_DIR>"
    notes_text = None
    if args.notes:
        notes_text = Path(args.notes).read_text(encoding="utf-8")

    meta = {
        "title": args.title,
        "model": args.model,
        "protocol": args.protocol,
        "source_run": args.source_run,
        "old_report": args.old_report,
        "template_version": args.template_version,
        "generated_at": generated_at,
        "report_id": report_id,
        "report_dir": report_dir,
        "command_template": command_template,
        "split_by": args.split_by,
        "per_page": args.per_page,
    }

    aggregate = build_aggregate(cases, meta=meta, video_root=video_dir)
    aggregate["template_version"] = args.template_version
    aggregate["reconciliation"] = build_reconciliation(
        aggregate,
        old_report_label=args.old_report,
        reconcile_path=Path(args.reconcile_json) if args.reconcile_json else None,
        run_summary_path=Path(args.run_summary) if args.run_summary else None,
        run_label=f"{args.source_run}/run-summary.json" if args.source_run else None,
    )
    if missing_summaries:
        aggregate["data_quality"].append(
            f"源 run 中有 {len(missing_summaries)} 个 case 目录缺少 summary.json，已跳过："
            + ", ".join(missing_summaries[:10])
            + ("..." if len(missing_summaries) > 10 else "")
        )
    for case in cases:
        case["video"]["available"] = video_available(case, video_dir)
        case["video"]["exists_at_generation"] = case["video"]["available"]

    # split into suite pages
    suite_pages: OrderedDict[str, list[list[Mapping[str, Any]]]] = OrderedDict()
    suites_present = sorted(
        {str(case["suite"]) for case in cases},
        key=lambda suite: SUITE_ORDER.index(suite) if suite in SUITE_ORDER else len(SUITE_ORDER),
    )
    page_case_index: dict[str, str] = {}
    for suite in suites_present:
        suite_cases = [case for case in cases if str(case["suite"]) == suite]
        pages = [suite_cases[index : index + args.per_page] for index in range(0, len(suite_cases), args.per_page)]
        suite_pages[suite] = pages
        for part_index, page in enumerate(pages, 1):
            for case in page:
                page_case_index[str(case["case_id"])] = f"{suite}-part{part_index}.html#case-{case['case_id']}"

    # render pages
    index_html = render_index(
        aggregate=aggregate,
        cases=cases,
        suite_pages=suite_pages,
        page_case_index=page_case_index,
        notes_text=notes_text,
    )
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    page_files: list[str] = ["index.html"]
    for suite, pages in suite_pages.items():
        for part_index, page in enumerate(pages, 1):
            filename = f"{suite}-part{part_index}.html"
            html_text = render_part_page(
                aggregate=aggregate,
                suite=suite,
                part_index=part_index,
                part_total=len(pages),
                page_cases=page,
                suite_pages=suite_pages,
                notes_text=notes_text,
            )
            (out_dir / filename).write_text(html_text, encoding="utf-8")
            page_files.append(filename)

    # evidence.json
    evidence = dict(aggregate)
    evidence["cases"] = cases
    extra_relpaths: list[str] = []
    for extra in args.extra_file:
        extra_path = Path(extra)
        try:
            extra_relpaths.append(extra_path.resolve().relative_to(out_dir.resolve()).as_posix())
        except ValueError:
            extra_relpaths.append(extra_path.name)
    artifact_files = page_files + [
        "evidence.json",
        "cases.jsonl",
        "README.md",
        "provenance.json",
        "videos/README.md",
        *extra_relpaths,
    ]
    evidence["files"] = artifact_files
    (out_dir / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # README / videos README
    write_report_readme(out_dir, aggregate=aggregate, files=evidence["files"])
    write_videos_readme(
        out_dir,
        cases=cases,
        source_run=args.source_run,
        suites=suites_present,
    )

    # provenance (hash every artifact except local videos)
    hash_targets = [name for name in artifact_files if name != "provenance.json"]
    migrated_sources: dict[str, Any] = {}
    for item in args.migrated_source or []:
        rel, separator, source = item.partition("=")
        if not separator or not rel or not source:
            raise SystemExit(f"--migrated-source expects REL=PATH, got: {item!r}")
        source_path = Path(source)
        if not source_path.is_file():
            raise SystemExit(f"--migrated-source source file not found: {source_path.name}")
        migrated_path = out_dir / rel
        migrated_sources[rel] = {
            "source_label": f"{args.old_report or '<SOURCE>'}/{Path(rel).name}",
            "source_sha256": sha256_file(source_path),
            "migrated_sha256": sha256_file(migrated_path) if migrated_path.is_file() else None,
            "note": "迁移副本可能加入说明行/脱敏主机路径，故 migrated_sha256 与 source_sha256 可以不同。",
        }
    write_provenance(
        out_dir,
        aggregate=aggregate,
        args=args,
        files=hash_targets,
        migrated_sources=migrated_sources,
    )

    recovery = aggregate["recovery"]
    rate_text = "N/A" if recovery["value"] is None else f"{100.0 * recovery['value']:.1f}%"
    print(
        f"[review-report] {len(cases)} cases · {len(suites_present)} suites · "
        f"{sum(len(pages) for pages in suite_pages.values())} part pages"
    )
    print(
        f"[review-report] injection valid {aggregate['injection']['injection_valid']}/"
        f"{aggregate['injection']['triggered']} triggered; "
        f"Recovery {recovery['numerator']}/{recovery['denominator']} = {rate_text}; "
        f"videos {aggregate['videos']['available']}/{aggregate['videos']['candidates']}"
    )
    print(f"[review-report] out: {out_dir}")
    for suite, pages in suite_pages.items():
        print(f"[review-report]   {suite}: " + ", ".join(f"part{i}={len(p)}" for i, p in enumerate(pages, 1)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
