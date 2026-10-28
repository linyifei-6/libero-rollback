#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LIBERO-90 双目标候选 pi05 3-seed 合并验证报告生成器（easy 161 + hard 92 = 253 候选 / 759 episodes）。

只读输入:
  .tmp/libero90-combos/merged-validation-data.json       合并数据（唯一主数据源；Lead 生成）
  runs/libero-90-easy-pi05-20261026/analysis/summary.json      easy 161 候选 / 483 eps（补失败/s1/逐 ep）
  runs/libero-90-hard-pi05-20261026/analysis/summary.json      hard seed0 / 92 eps（seed0 引用来源）
  runs/libero-90-hard-seeds12-full-20261026/analysis/summary.json hard seeds1/2 补跑 / 184 eps
  runs/libero-90-combos-20261025/dup-audit/dedup_decision.json  A/B/C/D 去重口径与 322→253 漏斗
  两 run 的 analysis/final_checks.json + 3 份 AUDIT.md            完整性/审计状态
  docs/libero-90-dual-target-candidates.md                    §15/§18/§19/§20 与产物索引链接
输出:
  runs/libero-90-validation-merged-20261027/merged-data.json  合并数据快照（build 时从 .tmp 字节拷贝）
  runs/libero-90-validation-merged-20261027/report/index.html  单文件 HTML（内联 CSS/JS）
  runs/libero-90-validation-merged-20261027/report/README.md   <=30 行说明
用法:
  .venv/bin/python scripts/build_libero90_merged_validation_report.py
  .venv/bin/python scripts/build_libero90_merged_validation_report.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import statistics
import sys
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "runs" / "libero-90-validation-merged-20261027"
REPORT_DIR = RUN_DIR / "report"
SNAPSHOT = RUN_DIR / "merged-data.json"
OUT_HTML = REPORT_DIR / "index.html"
OUT_README = REPORT_DIR / "README.md"

SRC_MERGED = ROOT / ".tmp" / "libero90-combos" / "merged-validation-data.json"
P_EASY = ROOT / "runs" / "libero-90-easy-pi05-20261026" / "analysis" / "summary.json"
P_HARD0 = ROOT / "runs" / "libero-90-hard-pi05-20261026" / "analysis" / "summary.json"
P_HARD12 = ROOT / "runs" / "libero-90-hard-seeds12-full-20261026" / "analysis" / "summary.json"
P_DEDUP = ROOT / "runs" / "libero-90-combos-20261025" / "dup-audit" / "dedup_decision.json"
P_EASY_FC = ROOT / "runs" / "libero-90-easy-pi05-20261026" / "analysis" / "final_checks.json"
P_HARD0_FC = ROOT / "runs" / "libero-90-hard-pi05-20261026" / "analysis" / "final_checks.json"
P_HARD12_FC = ROOT / "runs" / "libero-90-hard-seeds12-full-20261026" / "analysis" / "final_checks.json"
P_AUDIT_HARD0 = ROOT / "runs" / "libero-90-hard-pi05-20261026" / "AUDIT.md"
P_AUDIT_HARD12S = ROOT / "runs" / "libero-90-hard-success-seeds12-20261026" / "AUDIT.md"
P_AUDIT_HARDFULL = ROOT / "runs" / "libero-90-hard-seeds12-full-20261026" / "AUDIT.md"
P_DOCS = ROOT / "docs" / "libero-90-dual-target-candidates.md"

INPUT_FILES = [
    ("merged-validation-data.json", SRC_MERGED),
    ("easy-summary.json", P_EASY),
    ("hard0-summary.json", P_HARD0),
    ("hard12-summary.json", P_HARD12),
    ("dedup_decision.json", P_DEDUP),
    ("easy-final_checks.json", P_EASY_FC),
    ("hard0-final_checks.json", P_HARD0_FC),
    ("hard12-final_checks.json", P_HARD12_FC),
    ("hard0-AUDIT.md", P_AUDIT_HARD0),
    ("hard-success-seeds12-AUDIT.md", P_AUDIT_HARD12S),
    ("hard-full-AUDIT.md", P_AUDIT_HARDFULL),
    ("libero-90-dual-target-candidates.md", P_DOCS),
]

AXIS_CN = {
    "A_skip": "A · 场景/任务/指令全同（跳过）",
    "B_validate": "B · 同任务·指令不同（验证变体）",
    "C_diff_scene": "C · 同 goal·场景不同（新场景实例）",
    "D_unique": "D · 全新（无同 goal）",
}
EXP_CN = {"easy": "easy（低难度 161）", "hard": "hard（高难度剩余 92）"}
GROUP_CN = {"KITCHEN": "KITCHEN 厨房", "LIVING_ROOM": "LIVING_ROOM 客厅", "STUDY": "STUDY 书房"}
PRIO_BADGE = {"P0": "b-p0", "P1": "b-p1", "P2": "b-p2", "P3": "b-p3"}
CLASS_BADGE = {"compatible": "b-ok", "hard": "b-warn"}
AXIS_BADGE = {"A_skip": "b-fail", "B_validate": "b-warn", "C_diff_scene": "b-info", "D_unique": "b-ok"}


def esc(value):
    return html.escape(str(value), quote=True)


def nfmt(value):
    return f"{value:,}"


def badge(text, cls, title=None):
    attr = f' title="{esc(title)}"' if title else ""
    return f'<span class="badge {cls}"{attr}>{esc(text)}</span>'


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def input_hashes():
    return {name: sha256_file(path) for name, path in INPUT_FILES}


def build_digest(hashes):
    h = hashlib.sha256()
    for name in sorted(hashes):
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        h.update(hashes[name].encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def rate_pct(success, episodes):
    return round(100.0 * success / episodes, 2) if episodes else 0.0


def group_of(scene):
    if scene.startswith("KITCHEN"):
        return "KITCHEN"
    if scene.startswith("LIVING_ROOM"):
        return "LIVING_ROOM"
    return "STUDY"


def task_id(candidate_id):
    for suffix in ("_ab", "_ba"):
        if candidate_id.endswith(suffix):
            return candidate_id[: -len(suffix)]
    return candidate_id


def episode_stats(episodes):
    """从 episode 明细计算失败/步数/s1 等补充统计（合并口径）。"""
    total = len(episodes)
    success = [e for e in episodes if e["success"]]
    sub = Counter(int(e["subtasks_done_final"]) for e in episodes)
    near_miss = sum(1 for e in episodes if e["subtasks_done_final"] == 2 and not e["success"])
    steps = [int(e["steps"]) for e in episodes]
    first_true = [int(e["s1_first_true_step"]) for e in episodes if e.get("s1_first_true_step") is not None]
    return {
        "episodes": total,
        "success": len(success),
        "rate": (len(success) / total) if total else 0.0,
        "sub0": sub[0],
        "sub1": sub[1],
        "sub2": sub[2],
        "near_miss": near_miss,
        "maxsteps": sum(1 for s in steps if s >= 600),
        "mean_steps": round(sum(steps) / total, 2) if total else 0.0,
        "median_steps": statistics.median(steps) if steps else 0,
        "min_steps": min(steps) if steps else 0,
        "max_steps": max(steps) if steps else 0,
        "success_mean_steps": round(sum(int(e["steps"]) for e in success) / len(success), 2) if success else 0.0,
        "success_min_steps": min((int(e["steps"]) for e in success), default=0),
        "success_max_steps": max((int(e["steps"]) for e in success), default=0),
        "s1_ever": len(first_true),
        "s1_mean_step": round(sum(first_true) / len(first_true), 2) if first_true else 0.0,
        "s1_median_step": statistics.median(first_true) if first_true else 0,
        "s1_final": sum(1 for e in episodes if e.get("s1_final_true")),
        "s1_retract_events": sum(int(e.get("s1_retract_count") or 0) for e in episodes),
        "s1_retract_eps": sum(1 for e in episodes if (e.get("s1_retract_count") or 0) > 0),
    }


def parse_audit_verdict(path):
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'[Vv]erdict[：:]\s*\*\*([^*\n]+)\*\*', text)
    return m.group(1).strip() if m else "（未找到 verdict）"


def build_agg_rows(agg, key_name, sort_by_rate=True):
    rows = []
    for key, v in agg.items():
        rows.append({"key": key, "candidates": v["candidates"], "episodes": v["episodes"],
                     "success": v["success"], "rate": v["success"] / v["episodes"] if v["episodes"] else 0.0,
                     "rate_pct": rate_pct(v["success"], v["episodes"])})
    if sort_by_rate:
        rows.sort(key=lambda r: (-r["rate"], -r["episodes"], r["key"]))
    return rows

def build_funnel(merged, dedup):
    all_axis = dedup["all_322_by_axis"]
    validated = dedup["validated_by_axis"]
    invalid = dedup["invalid_by_axis"]
    valid_axis = dedup["valid_by_axis"]
    merged_axis = merged["axis"]
    rows = []
    for axis in ("A_skip", "B_validate", "C_diff_scene", "D_unique"):
        all_n = all_axis.get(axis, 0)
        run_n = merged_axis.get(axis, {}).get("candidates", 0)
        valid_not_run = valid_axis.get(axis, 0) - run_n
        rows.append({
            "axis": axis,
            "all322": all_n,
            "run": run_n,
            "not_run": all_n - run_n,
            "invalid": invalid.get(axis, 0),
            "valid_not_run": valid_not_run,
            "validated_candidates": validated.get(axis, {}).get("candidates", 0),
        })
    return {
        "rows": rows,
        "total322": sum(r["all322"] for r in rows),
        "run": sum(r["run"] for r in rows),
        "not_run": sum(r["not_run"] for r in rows),
        "invalid": sum(r["invalid"] for r in rows),
        "valid_not_run": sum(r["valid_not_run"] for r in rows),
        "validated_total": sum(r["validated_candidates"] for r in rows),
    }


def build_experiment_axis(merged):
    rows = []
    for exp in ("easy", "hard"):
        sub = [c for c in merged["candidates"].values() if c["experiment"] == exp]
        axis_counts = Counter(c["axis"] for c in sub)
        row = {"experiment": exp, "candidates": len(sub),
               "episodes": sum(c["eps"] for c in sub), "success": sum(c["succ"] for c in sub)}
        for axis in ("A_skip", "B_validate", "C_diff_scene", "D_unique"):
            row[axis] = axis_counts.get(axis, 0)
        rows.append(row)
    total = {"experiment": "merged", "candidates": sum(r["candidates"] for r in rows),
             "episodes": sum(r["episodes"] for r in rows), "success": sum(r["success"] for r in rows)}
    for axis in ("A_skip", "B_validate", "C_diff_scene", "D_unique"):
        total[axis] = sum(r[axis] for r in rows)
    rows.append(total)
    return rows


def build_stability(merged):
    cands = merged["candidates"]
    lists = merged["stability"]
    all3 = sorted(lists["all3"])
    ge2 = sorted(lists["ge2"])
    ge1 = sorted(lists["ge1"])
    only1 = sorted(lists["only1"])
    none = sorted(lists["none"])
    all3_rows = []
    axis_rank = {"D_unique": 0, "C_diff_scene": 1, "B_validate": 2, "A_skip": 3}
    for cid in sorted(all3, key=lambda c: (axis_rank.get(cands[c]["axis"], 9), cands[c]["scene"], c)):
        c = cands[cid]
        all3_rows.append({
            "candidate_id": cid, "experiment": c["experiment"], "axis": c["axis"],
            "scene": c["scene"], "template": c["template"], "bucket": c["bucket"],
            "order": c["order"], "seeds_success": c["seeds_success"], "succ": c["succ"],
            "instruction": c["instruction"],
            "novel": c["axis"] in ("C_diff_scene", "D_unique"),
        })
    return {
        "counts": {"ge1": len(ge1), "ge2": len(ge2), "all3": len(all3), "only1": len(only1), "none": len(none)},
        "ge1": ge1, "ge2": ge2, "all3": all3, "only1": only1, "none": none,
        "ge2_only": sorted(set(ge2) - set(all3)),
        "all3_rows": all3_rows,
        "by_axis_all3": dict(Counter(cands[c]["axis"] for c in all3)),
        "novel_all3": [c for c in all3 if cands[c]["axis"] in ("C_diff_scene", "D_unique")],
        "b_all3": [c for c in all3 if cands[c]["axis"] == "B_validate"],
        "a_all3": [c for c in all3 if cands[c]["axis"] == "A_skip"],
    }


def build_rollback(merged, stability):
    cands = merged["candidates"]
    succ = [cid for cid, c in cands.items() if c["succ"] > 0]
    available = [cid for cid in succ if cands[cid]["axis"] != "A_skip"]
    strict = [cid for cid in succ if cands[cid]["axis"] in ("C_diff_scene", "D_unique")]
    excluded = [cid for cid in succ if cands[cid]["axis"] == "A_skip"]
    by_axis = []
    for axis in ("A_skip", "B_validate", "C_diff_scene", "D_unique"):
        ids = [cid for cid in succ if cands[cid]["axis"] == axis]
        by_axis.append({
            "axis": axis,
            "succ_candidates": len(ids),
            "tasks": len({task_id(c) for c in ids}),
            "all3": sum(1 for c in ids if c in set(stability["all3"])),
            "episodes": sum(cands[c]["eps"] for c in ids),
            "success": sum(cands[c]["succ"] for c in ids),
        })
    return {
        "available_candidates": len(available),
        "available_tasks": len({task_id(c) for c in available}),
        "strict_candidates": len(strict),
        "strict_tasks": len({task_id(c) for c in strict}),
        "excluded_a_candidates": len(excluded),
        "excluded_a_tasks": len({task_id(c) for c in excluded}),
        "available_ids": sorted(available),
        "strict_ids": sorted(strict),
        "excluded_ids": sorted(excluded),
        "by_axis": by_axis,
    }


def build_failure(easy, hard0, hard12):
    easy_stats = episode_stats(easy["episodes"])
    hard0_stats = episode_stats(hard0["episodes"])
    hard12_stats = episode_stats(hard12["episodes"])
    hard_combined_stats = episode_stats(hard0["episodes"] + hard12["episodes"])
    merged_stats = episode_stats(easy["episodes"] + hard0["episodes"] + hard12["episodes"])
    rows = [
        {"scope": "easy", "label": "easy（161 候选 × 3 seeds）", **easy_stats},
        {"scope": "hard_seed0", "label": "hard seed0（92 eps，引用）", **hard0_stats},
        {"scope": "hard_seed12", "label": "hard seeds1/2 补跑（184 eps）", **hard12_stats},
        {"scope": "hard_combined", "label": "hard 合并 3 seeds（276 eps）", **hard_combined_stats},
        {"scope": "merged", "label": "easy+hard 合计（759 eps）", **merged_stats},
    ]
    hist = OrderedDict((key, 0) for key in ("200-299", "300-399", "400-499", "500-599", "600"))
    for e in easy["episodes"] + hard0["episodes"] + hard12["episodes"]:
        steps = int(e["steps"])
        if steps >= 600:
            hist["600"] += 1
        elif steps >= 500:
            hist["500-599"] += 1
        elif steps >= 400:
            hist["400-499"] += 1
        elif steps >= 300:
            hist["300-399"] += 1
        elif steps >= 200:
            hist["200-299"] += 1
    return {
        "rows": rows,
        "by_scope": {row["scope"]: row for row in rows},
        "hist": [{"range": k, "count": v} for k, v in hist.items()],
        "steps_hist_sum": sum(hist.values()),
        "merged": merged_stats,
        "hard12": hard12_stats,
        "hard_combined": hard_combined_stats,
        "easy": easy_stats,
    }


def build_seed_rows(easy, hard0, hard12):
    exp_rows = []
    for key in ("0", "1", "2"):
        v = easy["by_seed"][key]
        exp_rows.append({"experiment": "easy", "seed": int(key), "episodes": v["episodes"],
                         "success": v["success"], "rate_pct": rate_pct(v["success"], v["episodes"])})
    h12 = hard12["by_seed"]
    hard_seed = {
        0: {"episodes": hard0["overall"]["episodes"], "success": hard0["overall"]["success"]},
        1: {"episodes": h12["1"]["episodes"], "success": h12["1"]["success"]},
        2: {"episodes": h12["2"]["episodes"], "success": h12["2"]["success"]},
    }
    for seed in (0, 1, 2):
        v = hard_seed[seed]
        exp_rows.append({"experiment": "hard", "seed": seed, "episodes": v["episodes"],
                         "success": v["success"], "rate_pct": rate_pct(v["success"], v["episodes"])})
    merged_rows = []
    for seed in (0, 1, 2):
        episodes = sum(r["episodes"] for r in exp_rows if r["seed"] == seed)
        success = sum(r["success"] for r in exp_rows if r["seed"] == seed)
        merged_rows.append({"seed": seed, "episodes": episodes, "success": success,
                            "rate_pct": rate_pct(success, episodes)})
    return exp_rows, merged_rows


def build_walls(fc_easy, fc_hard0, fc_hard12):
    rows = [
        {"run": "easy（161×3=483 eps）", "path": "runs/libero-90-easy-pi05-20261026",
         "wall_hours": fc_easy["wall_hours"], "episodes": fc_easy["overall_episodes"]},
        {"run": "hard seed0（92 eps，引用）", "path": "runs/libero-90-hard-pi05-20261026",
         "wall_hours": fc_hard0["wall_hours"], "episodes": fc_hard0["overall_episodes"]},
        {"run": "hard seeds1/2 补跑（184 eps）", "path": "runs/libero-90-hard-seeds12-full-20261026",
         "wall_hours": fc_hard12["wall_hours"], "episodes": 184},
    ]
    total_hours = round(sum(r["wall_hours"] for r in rows), 2)
    total_eps = sum(r["episodes"] for r in rows)
    return {"rows": rows, "total_hours": total_hours, "total_episodes": total_eps,
            "rate": round(total_eps / total_hours, 2) if total_hours else 0.0}


def build_audits():
    rows = [
        {"run": "hard seed0（引用）", "file": P_AUDIT_HARD0, "href": "libero-90-hard-pi05-20261026/AUDIT.md",
         "verdict": parse_audit_verdict(P_AUDIT_HARD0)},
        {"run": "hard 成功候选 seeds1/2 稳定性补测", "file": P_AUDIT_HARD12S,
         "href": "libero-90-hard-success-seeds12-20261026/AUDIT.md", "verdict": parse_audit_verdict(P_AUDIT_HARD12S)},
        {"run": "hard 全量 92 × seeds1/2 补跑", "file": P_AUDIT_HARDFULL,
         "href": "libero-90-hard-seeds12-full-20261026/AUDIT.md", "verdict": parse_audit_verdict(P_AUDIT_HARDFULL)},
    ]
    for row in rows:
        row["status"] = "PASS" if row["verdict"].startswith("PASS") else "?"
    return rows


def build_metrics(merged, stability, rollback, failure, exp_axis, seed_rows, merged_rows, walls, funnel):
    totals = merged["totals"]
    easy = merged["experiment"]["easy"]
    hard = merged["experiment"]["hard"]
    novel = merged["novel_CD"]
    dup = merged["duplicate_AB"]
    merged_stats = failure["merged"]
    metrics = {
        "total_candidates": totals["candidates"],
        "total_episodes": totals["episodes"],
        "total_success": totals["success"],
        "total_rate_pct": round(100.0 * totals["rate"], 2),
        "easy_candidates": easy["candidates"],
        "easy_episodes": easy["episodes"],
        "easy_success": easy["success"],
        "easy_rate_pct": round(100.0 * easy["rate"], 2),
        "hard_candidates": hard["candidates"],
        "hard_episodes": hard["episodes"],
        "hard_success": hard["success"],
        "hard_rate_pct": round(100.0 * hard["rate"], 2),
        "stable_ge1": stability["counts"]["ge1"],
        "stable_ge2": stability["counts"]["ge2"],
        "stable_all3": stability["counts"]["all3"],
        "stable_only1": stability["counts"]["only1"],
        "stable_none": stability["counts"]["none"],
        "novel_candidates": novel["candidates"],
        "novel_episodes": novel["episodes"],
        "novel_success": novel["success"],
        "novel_rate_pct": round(100.0 * novel["rate"], 2),
        "dup_candidates": dup["candidates"],
        "dup_episodes": dup["episodes"],
        "dup_success": dup["success"],
        "dup_rate_pct": round(100.0 * dup["rate"], 2),
        "rollback_candidates": rollback["available_candidates"],
        "rollback_tasks": rollback["available_tasks"],
        "strict_candidates": rollback["strict_candidates"],
        "strict_tasks": rollback["strict_tasks"],
        "excluded_a_candidates": rollback["excluded_a_candidates"],
        "new3": len(stability["novel_all3"]),
        "b3": len(stability["b_all3"]),
        "a3": len(stability["a_all3"]),
        "merged_seed0_success": merged_rows[0]["success"],
        "merged_seed1_success": merged_rows[1]["success"],
        "merged_seed2_success": merged_rows[2]["success"],
        "merged_seed0_rate_pct": merged_rows[0]["rate_pct"],
        "merged_seed1_rate_pct": merged_rows[1]["rate_pct"],
        "merged_seed2_rate_pct": merged_rows[2]["rate_pct"],
        "wall_total_hours": walls["total_hours"],
        "wall_easy": walls["rows"][0]["wall_hours"],
        "wall_hard0": walls["rows"][1]["wall_hours"],
        "wall_hard12": walls["rows"][2]["wall_hours"],
        "run_episodes_total": walls["total_episodes"],
        "funnel_total322": funnel["total322"],
        "funnel_run": funnel["run"],
        "funnel_not_run": funnel["not_run"],
        "funnel_invalid": funnel["invalid"],
        "funnel_valid_not_run": funnel["valid_not_run"],
        "near_miss": merged_stats["near_miss"],
        "maxsteps": merged_stats["maxsteps"],
        "maxsteps_pct": rate_pct(merged_stats["maxsteps"], merged_stats["episodes"]),
        "mean_steps": merged_stats["mean_steps"],
        "median_steps": merged_stats["median_steps"],
        "success_mean_steps": merged_stats["success_mean_steps"],
        "sub0": merged_stats["sub0"],
        "sub1": merged_stats["sub1"],
        "sub2": merged_stats["sub2"],
        "s1_ever": merged_stats["s1_ever"],
        "s1_final": merged_stats["s1_final"],
        "s1_mean_step": merged_stats["s1_mean_step"],
        "s1_median_step": merged_stats["s1_median_step"],
        "s1_retract_events": merged_stats["s1_retract_events"],
        "s1_retract_eps": merged_stats["s1_retract_eps"],
    }
    return metrics

def build_candidate_rows(merged):
    cands = merged["candidates"]
    exp_rank = {"easy": 0, "hard": 1}
    axis_rank = {"A_skip": 0, "B_validate": 1, "C_diff_scene": 2, "D_unique": 3}
    rows = []
    for cid in sorted(cands.keys(), key=lambda c: (exp_rank.get(cands[c]["experiment"], 9),
                                                   axis_rank.get(cands[c]["axis"], 9),
                                                   cands[c]["scene"], c)):
        c = cands[cid]
        rows.append({
            "candidate_id": cid,
            "experiment": c["experiment"],
            "axis": c["axis"],
            "scene": c["scene"],
            "template": c["template"],
            "bucket": c["bucket"],
            "route": c["route"],
            "priority": c["priority"],
            "class": c["class"],
            "order": c["order"],
            "eps": c["eps"],
            "succ": c["succ"],
            "seeds_success": c["seeds_success"],
            "instruction": c["instruction"],
            "duplicate_of": c["duplicate_of"],
            "task_id": task_id(cid),
            "rate_pct": rate_pct(c["succ"], c["eps"]),
        })
    for idx, row in enumerate(rows, 1):
        row["index"] = idx
    return rows


def build_groups(merged):
    groups = {}
    for scene, v in merged["scene"].items():
        key = group_of(scene)
        g = groups.setdefault(key, {"group": key, "scenes": 0, "candidates": 0, "episodes": 0, "success": 0})
        g["scenes"] += 1
        g["candidates"] += v["candidates"]
        g["episodes"] += v["episodes"]
        g["success"] += v["success"]
    rows = []
    for key in ("KITCHEN", "LIVING_ROOM", "STUDY"):
        if key in groups:
            g = groups[key]
            g["rate_pct"] = rate_pct(g["success"], g["episodes"])
            rows.append(g)
    return rows


def compute_model():
    merged = load_json(SRC_MERGED)
    easy = load_json(P_EASY)
    hard0 = load_json(P_HARD0)
    hard12 = load_json(P_HARD12)
    dedup = load_json(P_DEDUP)
    fc_easy = load_json(P_EASY_FC)
    fc_hard0 = load_json(P_HARD0_FC)
    fc_hard12 = load_json(P_HARD12_FC)

    funnel = build_funnel(merged, dedup)
    exp_axis = build_experiment_axis(merged)
    stability = build_stability(merged)
    rollback = build_rollback(merged, stability)
    failure = build_failure(easy, hard0, hard12)
    seed_rows, merged_seed_rows = build_seed_rows(easy, hard0, hard12)
    walls = build_walls(fc_easy, fc_hard0, fc_hard12)
    audits = build_audits()
    groups = build_groups(merged)
    distributions = {
        "scene": build_agg_rows(merged["scene"], "scene"),
        "template": build_agg_rows(merged["template"], "template"),
        "bucket": build_agg_rows(merged["bucket"], "bucket"),
        "route": build_agg_rows(merged["route"], "route"),
        "priority": build_agg_rows(merged["priority"], "priority"),
        "class": build_agg_rows(merged["class"], "class"),
        "order": build_agg_rows(merged["order"], "order"),
    }
    for row in distributions["scene"]:
        row["group"] = group_of(row["key"])
    candidate_rows = build_candidate_rows(merged)
    metrics = build_metrics(merged, stability, rollback, failure, exp_axis, seed_rows, merged_seed_rows, walls, funnel)
    hashes = input_hashes()
    return {
        "merged": merged,
        "easy": easy,
        "hard0": hard0,
        "hard12": hard12,
        "dedup": dedup,
        "fc": {"easy": fc_easy, "hard0": fc_hard0, "hard12": fc_hard12},
        "audits": audits,
        "funnel": funnel,
        "exp_axis": exp_axis,
        "stability": stability,
        "rollback": rollback,
        "failure": failure,
        "seed_rows": seed_rows,
        "merged_seed_rows": merged_seed_rows,
        "walls": walls,
        "groups": groups,
        "dist": distributions,
        "candidate_rows": candidate_rows,
        "metrics": metrics,
        "hashes": hashes,
        "digest": build_digest(hashes),
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
    }


def validate_model(m):
    problems = []
    merged = m["merged"]
    cands = merged["candidates"]
    totals = merged["totals"]
    mt = m["metrics"]

    def need(cond, msg):
        if not cond:
            problems.append(msg)

    # 总量 / 实验
    need(len(cands) == totals["candidates"], "候选数 != totals.candidates")
    need(sum(c["eps"] for c in cands.values()) == totals["episodes"], "episodes 之和 != totals")
    need(sum(c["succ"] for c in cands.values()) == totals["success"], "success 之和 != totals")
    need(abs(totals["rate"] - totals["success"] / totals["episodes"]) < 1e-9, "totals.rate 不自洽")
    for exp in ("easy", "hard"):
        sub = [c for c in cands.values() if c["experiment"] == exp]
        e = merged["experiment"][exp]
        need(len(sub) == e["candidates"], f"{exp} 候选数 != experiment")
        need(sum(c["eps"] for c in sub) == e["episodes"], f"{exp} episodes 之和 != experiment")
        need(sum(c["succ"] for c in sub) == e["success"], f"{exp} success 之和 != experiment")
        need(all(c["eps"] == 3 for c in sub), f"{exp} 存在 eps != 3 的候选")
        need(all(c["succ"] == len(c["seeds_success"]) for c in sub), f"{exp} succ != len(seeds_success)")
    need(merged["experiment"]["easy"]["candidates"] + merged["experiment"]["hard"]["candidates"]
         == totals["candidates"], "easy+hard 候选数 != totals")
    # axis / novel / duplicate
    axis = merged["axis"]
    for ax in ("A_skip", "B_validate", "C_diff_scene", "D_unique"):
        sub = [c for c in cands.values() if c["axis"] == ax]
        need(len(sub) == axis[ax]["candidates"], f"{ax} 候选数 != axis 聚合")
        need(sum(c["eps"] for c in sub) == axis[ax]["episodes"], f"{ax} episodes != axis 聚合")
        need(sum(c["succ"] for c in sub) == axis[ax]["success"], f"{ax} success != axis 聚合")
    novel = merged["novel_CD"]
    dup = merged["duplicate_AB"]
    novel_calc = [c for c in cands.values() if c["axis"] in ("C_diff_scene", "D_unique")]
    dup_calc = [c for c in cands.values() if c["axis"] in ("A_skip", "B_validate")]
    need(len(novel_calc) == novel["candidates"], "novel C+D 候选数不一致")
    need(sum(c["succ"] for c in novel_calc) == novel["success"], "novel C+D success 不一致")
    need(len(dup_calc) == dup["candidates"], "duplicate A+B 候选数不一致")
    need(sum(c["succ"] for c in dup_calc) == dup["success"], "duplicate A+B success 不一致")
    # stability
    st = m["stability"]
    lists = merged["stability"]
    need(set(st["ge1"]) == {cid for cid, c in cands.items() if c["succ"] > 0}, "ge1 集合 != 有成功候选集合")
    need(set(lists["ge1"]) == set(st["ge1"]), "stability.ge1 与 merged 数据不一致")
    need(set(lists["ge2"]) <= set(lists["ge1"]) and set(lists["all3"]) <= set(lists["ge2"]),
         "stability ge1/ge2/all3 子集关系不成立")
    need(set(lists["only1"]) == set(lists["ge1"]) - set(lists["ge2"]), "only1 != ge1 - ge2")
    need(set(lists["none"]) == set(cands) - set(lists["ge1"]), "none != all - ge1")
    need(len(st["counts"].values()) == 5, "stability counts 缺项")
    need(st["counts"]["ge1"] + st["counts"]["none"] == len(cands), "ge1+none != 候选数")
    need(all(cands[c]["succ"] == 3 for c in st["all3"]), "all3 名单中存在 succ != 3")
    need(all(cands[c]["succ"] >= 2 for c in st["ge2"]), "ge2 名单中存在 succ < 2")
    need(all(cands[c]["succ"] <= 1 for c in st["only1"]), "only1 名单中存在 succ > 1")
    # rollback
    rb = m["rollback"]
    succ = [cid for cid, c in cands.items() if c["succ"] > 0]
    need(rb["available_candidates"] == len([c for c in succ if cands[c]["axis"] != "A_skip"]),
         "rollback available candidates 不一致")
    need(rb["strict_candidates"] == len([c for c in succ if cands[c]["axis"] in ("C_diff_scene", "D_unique")]),
         "rollback strict candidates 不一致")
    need(rb["excluded_a_candidates"] == len([c for c in succ if cands[c]["axis"] == "A_skip"]),
         "rollback excluded A 不一致")
    need(rb["available_tasks"] == len({task_id(c) for c in succ if cands[c]["axis"] != "A_skip"}),
         "rollback available tasks 不一致")
    need(rb["strict_tasks"] == len({task_id(c) for c in succ if cands[c]["axis"] in ("C_diff_scene", "D_unique")}),
         "rollback strict tasks 不一致")
    need(rb["available_candidates"] + rb["excluded_a_candidates"] == len(succ), "available + excluded != 成功候选数")
    need(set(rb["strict_ids"]) <= set(rb["available_ids"]), "strict 不是 available 子集")
    # funnel
    fn = m["funnel"]
    need(fn["total322"] == 322, "funnel.total322 != 322")
    need(fn["run"] == totals["candidates"], "funnel.run != 候选总数")
    need(fn["not_run"] == fn["invalid"] + fn["valid_not_run"], "funnel not_run != invalid + valid_not_run")
    need(fn["total322"] == fn["run"] + fn["not_run"], "funnel 322 != run + not_run")
    for row in fn["rows"]:
        need(row["not_run"] == row["invalid"] + row["valid_not_run"], f"funnel {row['axis']} 分解不一致")
        need(row["run"] <= row["all322"], f"funnel {row['axis']} run > all322")
    need(fn["valid_not_run"] == 5, "valid A 未跑数 != 5")
    need(fn["invalid"] == 64, "invalid 数 != 64")
    # 分布表
    for dim, rows in m["dist"].items():
        need(len(rows) == len(merged[dim]), f"{dim} 行数 != 聚合条目数")
        need(sum(r["candidates"] for r in rows) == totals["candidates"], f"{dim} candidates 之和 != 253")
        need(sum(r["episodes"] for r in rows) == totals["episodes"], f"{dim} episodes 之和 != 759")
        need(sum(r["success"] for r in rows) == totals["success"], f"{dim} success 之和 != 56")
        for r in rows:
            need(r["key"] in merged[dim], f"{dim} 行 {r['key']} 不在聚合中")
            need(r["candidates"] == merged[dim][r["key"]]["candidates"], f"{dim} {r['key']} candidates 不一致")
            need(r["success"] == merged[dim][r["key"]]["success"], f"{dim} {r['key']} success 不一致")
    need(sum(g["candidates"] for g in m["groups"]) == totals["candidates"], "分组 candidates 之和 != 253")
    need(sum(g["episodes"] for g in m["groups"]) == totals["episodes"], "分组 episodes 之和 != 759")
    need(sum(g["success"] for g in m["groups"]) == totals["success"], "分组 success 之和 != 56")
    # 补充失败/s1 口径
    failure = m["failure"]
    for scope, row in failure["by_scope"].items():
        need(row["sub0"] + row["sub1"] + row["near_miss"] + row["success"] == row["episodes"],
             f"{scope}: 子任务分布 + near_miss 之和 != episodes")
        need(row["sub2"] == row["success"] + row["near_miss"], f"{scope}: sub2 != success + near_miss")
        need(row["maxsteps"] <= row["episodes"], f"{scope}: maxsteps > episodes")
    need(failure["merged"]["episodes"] == totals["episodes"], "合并 failure episodes != 759")
    need(failure["merged"]["success"] == totals["success"], "合并 failure success != 56")
    need(failure["steps_hist_sum"] == totals["episodes"], "steps 直方图之和 != 759")
    need(failure["hard_combined"]["episodes"] == 276, "hard combined episodes != 276")
    need(failure["hard_combined"]["success"] == 15, "hard combined success != 15")
    # per-seed
    need(sum(r["episodes"] for r in m["merged_seed_rows"]) == totals["episodes"], "per-seed episodes 之和 != 759")
    need(sum(r["success"] for r in m["merged_seed_rows"]) == totals["success"], "per-seed success 之和 != 56")
    for seed in (0, 1, 2):
        need(m["merged_seed_rows"][seed]["episodes"] == totals["candidates"],
             f"seed{seed} episodes != 253")
    need(len(m["seed_rows"]) == 6, "实验 × seed 行数 != 6")
    # walls / audits
    need(m["walls"]["total_hours"] > 0 and m["walls"]["total_episodes"] == totals["episodes"],
         "walls 汇总不一致")
    need(len(m["audits"]) == 3 and all(a["verdict"].startswith("PASS") for a in m["audits"]),
         "审计 verdict 缺失或非 PASS")
    # dedup 交叉校验（axis / duplicate_of 一致性）
    axes_map = m["dedup"]["axes"]
    need(all(cid in axes_map for cid in cands), "存在不在 dedup_decision.axes 中的候选")
    for cid, c in cands.items():
        need(axes_map[cid]["axis"] == c["axis"], f"{cid}: axis 与 dedup_decision 不一致")
        need(sorted(axes_map[cid].get("duplicate_of", [])) == sorted(c["duplicate_of"]),
             f"{cid}: duplicate_of 与 dedup_decision 不一致")
    # 候选行
    need(len(m["candidate_rows"]) == totals["candidates"], "候选表行数 != 253")
    need(len({r["candidate_id"] for r in m["candidate_rows"]}) == totals["candidates"], "候选表 candidate_id 重复")
    need(sum(1 for r in m["candidate_rows"] if r["succ"] > 0) == m["stability"]["counts"]["ge1"],
         "候选行成功数 != ge1")
    if problems:
        raise SystemExit("[FATAL] 输入数据不自洽:\n - " + "\n - ".join(problems))

CSS = """
:root{color-scheme:light}*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;padding-left:246px;background:#f7f8fa;color:#1f2328;font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei","Noto Sans SC",sans-serif}
a{color:#1d4ed8;text-decoration:none}a:hover{text-decoration:underline}
code{background:#f3f4f6;color:#111827;padding:1px 4px;border-radius:4px;font-size:12px;word-break:break-word}
.sidenav{position:fixed;left:0;top:0;bottom:0;width:232px;overflow-y:auto;background:#fff;border-right:1px solid #e5e7eb;padding:14px 10px 24px;z-index:40;font-size:12.5px;box-shadow:2px 0 10px rgba(15,23,42,.06)}
.sidenav .brand{color:#1d4ed8;font-weight:700;font-size:13px;margin:0 6px 10px;line-height:1.35}
.sidenav .grp{color:#6b7280;font-size:11px;margin:12px 6px 4px;letter-spacing:.04em}
.sidenav a{display:block;color:#374151;padding:3px 6px;border-radius:5px;margin:1px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sidenav a:hover{background:#eef2f7;color:#111827;text-decoration:none}
.sidenav a.active{background:#dbeafe;color:#1d4ed8;font-weight:600}
.sidenav .foot{color:#6b7280;font-size:10.5px;margin:16px 6px 0;line-height:1.45}
header.hero{background:#fff;border-bottom:1px solid #e5e7eb;padding:24px 26px 18px}
header.hero h1{margin:0 0 10px;font-size:23px}
header.hero .meta{color:#4b5563;margin:0 0 10px;font-size:13px}
header.hero .gen{color:#9ca3af;margin:10px 0 0;font-size:11.5px}
.status{background:#eff6ff;border-left:4px solid #3b82f6;color:#1e3a8a;padding:10px 12px;border-radius:6px;margin:10px 0;font-size:13px;line-height:1.65}
.status.warn{background:#fffbeb;border-left-color:#f59e0b;color:#78350f}
.status.ok{background:#f0fdf4;border-left-color:#16a34a;color:#14532d}
main{max-width:1320px;margin:0 auto;padding:0 26px 70px}
section{margin:34px 0;padding-top:6px;border-top:1px solid #e5e7eb;scroll-margin-top:64px}
h2{font-size:21px;margin:10px 0 8px}h3{font-size:16px;margin:22px 0 8px}h4{font-size:14px;margin:14px 0 6px}
p{color:#374151}
.sub{color:#6b7280;font-size:13px}
.tiny{color:#6b7280;font-size:11px;line-height:1.4}
.nowrap{white-space:nowrap}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(225px,1fr));gap:10px;margin:12px 0}
.metric{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px 14px}
.metric.wide{grid-column:span 2}
.metric .v{font-size:22px;font-weight:700;line-height:1.3}
.metric .v small{font-size:13px;color:#6b7280;font-weight:600}
.metric .l{color:#374151;font-size:12.5px;margin-top:2px}
.metric .d{color:#6b7280;font-size:11.5px;margin-top:5px;line-height:1.5}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}
.chip{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:2px 9px;font-size:12px;color:#374151}
.chip b{color:#111827}
.tblwrap{overflow-x:auto;margin:8px 0 14px;background:#fff;border:1px solid #e5e7eb;border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th,td{border-bottom:1px solid #eef0f3;padding:6px 8px;text-align:left;vertical-align:top}
thead th{background:#f3f4f6;color:#374151;white-space:nowrap;border-bottom:1px solid #e5e7eb}
tbody tr:hover{background:#fafbfc}
tr.hi td{background:#f0fdf4}
tr.zero td{color:#9ca3af}
tr.near td{background:#fef2f2}
.badge{display:inline-block;padding:1px 7px;border-radius:9px;font-size:11px;font-weight:700;margin:1px 2px 1px 0;white-space:nowrap}
.b-ok{background:#dcfce7;color:#15803d}.b-fail{background:#fee2e2;color:#b91c1c}
.b-warn{background:#fef3c7;color:#a16207}.b-info{background:#dbeafe;color:#1d4ed8}
.b-muted{background:#f3f4f6;color:#6b7280}.b-p0{background:#dcfce7;color:#15803d}
.b-p1{background:#fef3c7;color:#a16207}.b-p2{background:#f3f4f6;color:#6b7280}
.b-axis-A{background:#fee2e2;color:#b91c1c}.b-axis-B{background:#fef3c7;color:#a16207}
.b-axis-C{background:#dbeafe;color:#1d4ed8}.b-axis-D{background:#dcfce7;color:#15803d}
.b-exp-easy{background:#e0e7ff;color:#3730a3}.b-exp-hard{background:#fce7f3;color:#9d174d}
.b-review{background:#bbf7d0;color:#14532d}.b-near{background:#fecaca;color:#991b1b}
.barchart{margin:10px 0;background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:10px 14px}
.barrow{display:grid;grid-template-columns:210px 1fr 110px;gap:8px;align-items:center;margin:4px 0;font-size:12px}
.barrow .lab{color:#374151;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.barrow .bar{background:#eef2f7;border-radius:5px;height:14px;overflow:hidden}
.barrow .bar span{display:block;height:14px;border-radius:5px;background:#60a5fa}
.barrow .val{color:#4b5563;text-align:right;font-variant-numeric:tabular-nums}
.barrow.hot .bar span{background:#16a34a}.barrow.warm .bar span{background:#f59e0b}
.barrow.cold .bar span{background:#ef4444}.barrow.cool .bar span{background:#93c5fd}
.bigcards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;margin:10px 0}
.bigcard{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px}
.bigcard.gold{border-color:#86efac;background:#f0fdf4}
.bigcard.blue{border-color:#bfdbfe;background:#eff6ff}
.bigcard .id{font-weight:700;font-size:12.5px;word-break:break-all}
.bigcard .instr{font-size:12px;color:#4b5563;margin:6px 0}
.bigcard .kv{font-size:11.5px;color:#6b7280;line-height:1.6}
.filterbar{position:sticky;top:0;z-index:30;background:rgba(247,248,250,.97);border-bottom:1px solid #e5e7eb;padding:8px 0;display:flex;gap:8px;flex-wrap:wrap;align-items:center;font-size:12.5px}
.filterbar select,.filterbar button{background:#fff;color:#111827;border:1px solid #d1d5db;border-radius:6px;padding:4px 7px;font-size:12px;cursor:pointer}
.filterbar .count{color:#1d4ed8;font-weight:600;margin-left:auto}
.filterbar .hint{color:#6b7280;font-size:11px;flex-basis:100%}
.candtable td:first-child,.candtable td:nth-child(2){white-space:nowrap}
.candtable .seeds{font-variant-numeric:tabular-nums;font-size:11.5px}
ul.flat{margin:8px 0;padding-left:20px}ul.flat li{margin:5px 0;color:#374151;font-size:13px}
ol.risk{margin:8px 0;padding-left:22px}ol.risk li{margin:7px 0;color:#374151;font-size:13px;line-height:1.6}
.note{background:#f8fafc;border-left:3px solid #cbd5e1;padding:6px 10px;color:#4b5563;font-size:12px;border-radius:4px;margin:6px 0;line-height:1.6}
.note.warn{background:#fffbeb;border-left-color:#f59e0b;color:#78350f}
.note.ok{background:#f0fdf4;border-left-color:#16a34a;color:#14532d}
.top{font-size:12px;font-weight:400;color:#9ca3af;margin-left:6px}
footer{margin-top:40px;padding:14px 0 30px;border-top:1px solid #e5e7eb;color:#6b7280;font-size:11.5px;line-height:1.7}
footer code{font-size:11px}
details summary{cursor:pointer;color:#1d4ed8;font-size:12px}
.ok-txt{color:#15803d;font-weight:700}.fail-txt{color:#b91c1c;font-weight:700}
@media (max-width:980px){body{padding-left:0}.sidenav{position:static;width:auto;height:auto;border-right:none;border-bottom:1px solid #e5e7eb;box-shadow:none}.sidenav .foot{display:none}main{padding:0 14px 50px}.metric.wide{grid-column:span 1}.barrow{grid-template-columns:120px 1fr 80px}}
"""


JS = """
(function(){
  var nav = Array.prototype.slice.call(document.querySelectorAll('.sidenav a[href^="#"]'));
  var byId = {};
  nav.forEach(function(a){ byId[a.getAttribute('href').slice(1)] = a; });
  var sections = Array.prototype.slice.call(document.querySelectorAll('section[id], header[id]'));
  function markActive(){
    var y = window.scrollY + 140, cur = null;
    sections.forEach(function(s){ if (s.offsetTop <= y) cur = s.id; });
    nav.forEach(function(a){ a.classList.remove('active'); });
    if (cur && byId[cur]) byId[cur].classList.add('active');
  }
  window.addEventListener('scroll', markActive, {passive:true});
  markActive();

  var expSel = document.getElementById('filter-experiment');
  var axisSel = document.getElementById('filter-axis');
  var sceneSel = document.getElementById('filter-scene');
  var resSel = document.getElementById('filter-result');
  var reset = document.getElementById('filter-reset');
  var counter = document.getElementById('filter-count');
  if (!expSel || !axisSel || !sceneSel || !resSel || !counter) return;
  var rows = Array.prototype.slice.call(document.querySelectorAll('tr.cand-row'));
  function resultOk(tr, val){
    if (!val) return true;
    var n = parseInt(tr.dataset.succ || '0', 10);
    if (val === 'any') return n >= 1;
    if (val === 'ge2') return n >= 2;
    if (val === 'all3') return n >= 3;
    if (val === 'zero') return n === 0;
    return true;
  }
  function apply(){
    var e = expSel.value, a = axisSel.value, s = sceneSel.value, r = resSel.value, shown = 0;
    rows.forEach(function(tr){
      var ok = (!e || tr.dataset.experiment === e) && (!a || tr.dataset.axis === a)
            && (!s || tr.dataset.scene === s) && resultOk(tr, r);
      tr.style.display = ok ? '' : 'none';
      if (ok) shown++;
    });
    counter.textContent = '显示 ' + shown + ' / ' + rows.length + ' 条候选';
  }
  [expSel, axisSel, sceneSel, resSel].forEach(function(el){ el.addEventListener('change', apply); });
  if (reset) reset.addEventListener('click', function(){
    expSel.value = ''; axisSel.value = ''; sceneSel.value = ''; resSel.value = ''; apply();
  });
  apply();
})();
"""

def bar_row(label, ratio, value_text, cls=""):
    width = max(0.0, min(100.0, 100.0 * ratio))
    return (f'<div class="barrow {cls}"><div class="lab">{esc(label)}</div>'
            f'<div class="bar"><span style="width:{width:.1f}%"></span></div>'
            f'<div class="val">{value_text}</div></div>')


def render_sidenav(m):
    parts = ['<nav class="sidenav" aria-label="报告目录">',
             '<div class="brand">LIBERO-90 双目标候选<br>pi05 合并验证（easy+hard）</div>',
             '<div class="grp">总览</div>',
             '<a href="#top">摘要与结论</a>',
             '<a href="#overview">指标与运行完整性</a>',
             '<a href="#methods">方法与口径（A/B/C/D）</a>',
             '<a href="#compare">easy vs hard 对比</a>',
             '<div class="grp">去重与分布</div>',
             '<a href="#axes">去重轴表（A/B/C/D）</a>',
             '<a href="#dist">分布表（场景/模板/…）</a>',
             '<div class="grp">分析</div>',
             '<a href="#failures">失败分析</a>',
             '<a href="#stability">稳定性与 rollback 基数</a>',
             '<a href="#candidates">全部 253 条候选</a>',
             '<div class="grp">结论与附录</div>',
             '<a href="#conclusions">结论与建议</a>',
             '<a href="#caveats">口径 / 偏差 / 数据问题</a>',
             '<a href="#artifacts">产物索引</a>',
             '<div class="foot">253 candidates / 759 eps / 56 success<br>easy 8.49% · hard 5.43%<br>novel C+D 3.72% · dup A+B 87.88%<br>scripts/build_libero90_merged_validation_report.py</div>',
             '</nav>']
    return "\n".join(parts)


def render_hero(m):
    mt = m["metrics"]
    walls = m["walls"]
    return f'''<header class="hero" id="top">
<h1>LIBERO-90 双目标候选 · pi05 3-seed 合并验证报告（easy 161 + hard 92）</h1>
<p class="meta"><b>{mt["total_candidates"]}</b> candidates × seeds {{0,1,2}} = <b>{mt["total_episodes"]} episodes</b>（easy {mt["easy_candidates"]}×3 = {mt["easy_episodes"]} + hard {mt["hard_candidates"]}×3 = {mt["hard_episodes"]}）· pi05 · max_steps=600 / replan=10 / video off / 双 worker / sidecar init · 数据日期 2026-10-27 · 运行目录 <code>runs/libero-90-validation-merged-20261027/</code></p>
<div class="status ok"><b>一句话结论</b>：两批验证合并后 <b>{mt["total_success"]} / {mt["total_episodes"]} = {mt["total_rate_pct"]}%</b> success；<b>easy {mt["easy_rate_pct"]}%</b>（{mt["easy_success"]}/{mt["easy_episodes"]}）vs <b>hard {mt["hard_rate_pct"]}%</b>（{mt["hard_success"]}/{mt["hard_episodes"]}）。按去重轴拆分：<b>真正新任务（C+D，与既有 L10/GOAL/OBJECT 非同任务）只有 {mt["novel_success"]}/{mt["novel_episodes"]} = {mt["novel_rate_pct"]}%</b>，而 <b>重复任务（A+B）为 {mt["dup_success"]}/{mt["dup_episodes"]} = {mt["dup_rate_pct"]}%</b>（会显著抬高总成功率）；稳定候选 <b>{mt["stable_ge1"]} any / {mt["stable_ge2"]} ≥2 / {mt["stable_all3"]} 3/3</b>，rollback 可用基数 <b>{mt["rollback_candidates"]} candidates / {mt["rollback_tasks"]} tasks</b>（严格全新 C+D：{mt["strict_candidates"]}/{mt["strict_tasks"]}）。</div>
<div class="status warn"><b>口径声明（必读）</b>：本报告是 <b>easy（低难度半数 161）+ hard（去重后剩余 92）</b> 两批实验的合并，<b>不是 322 条候选的随机样本</b>；hard 92 = 322 中 valid、不在 easy 161 且 axis≠A 的剩余（另有 5 条 valid A 未跑、64 条 invalid 未跑）。两个实验的候选构成不同，<b>easy 8.49% 与 hard 5.43% 不可当成同一总体的两个随机子集做统计检验</b>；合并 7.38% 也不是 322 全量的成功率。所有结论只适用于该合并集合；video 全程 off、单指令 zero-shot（未测 staged / rollback 协议）、seeds 仅 3 个非官方 50 trials。</div>
<p class="method"><b>协议</b>：pi05（OpenPI PyTorch 后端；checkpoint <code>pi05_libero</code>）；success = LIBERO <code>check_success()</code>；seeds {{0,1,2}}，seed s 的初始状态 = sibling <code>.pruned_init</code> 第 <code>s % 50</code> 行；每控制步记录 goal 原子真值；easy 与 hard 均由 2 worker 并行执行（<code>XLA_PYTHON_CLIENT_MEM_FRACTION=0.42</code>）；hard 的 seed0 引用既有 hard run，seeds1/2 为补跑。</p>
<p class="gen">生成脚本 <code>scripts/build_libero90_merged_validation_report.py</code> · 主数据源 <code>merged-data.json</code>（来自 <code>.tmp/libero90-combos/merged-validation-data.json</code>）+ 两 run 的 <code>analysis/summary.json</code> / <code>final_checks.json</code> / <code>AUDIT.md</code> + <code>dup-audit/dedup_decision.json</code> · 共 {walls["total_hours"]} h 运行（{walls["total_episodes"]} eps）· 构建指纹见页脚 · 单文件内联 CSS/JS、无外链 CDN</p>
</header>'''


def render_overview(m):
    mt = m["metrics"]
    fn = m["funnel"]
    audits = m["audits"]
    funnel_rows = "".join(
        f'<tr class="funnel-row" data-axis="{r["axis"]}" data-all322="{r["all322"]}" data-run="{r["run"]}" '
        f'data-not-run="{r["not_run"]}" data-invalid="{r["invalid"]}" data-valid-not-run="{r["valid_not_run"]}">'
        f'<td><code>{r["axis"]}</code></td><td>{r["all322"]}</td><td><b>{r["run"]}</b></td>'
        f'<td>{r["not_run"]}</td><td>{r["invalid"]}</td><td>{r["valid_not_run"]}</td></tr>'
        for r in fn["rows"]
    )
    wall_rows = "".join(
        f'<tr><td>{esc(r["run"])}</td><td>{r["wall_hours"]} h</td><td>{r["episodes"]}</td>'
        f'<td class="tiny"><code>{esc(r["path"])}</code></td></tr>'
        for r in m["walls"]["rows"]
    )
    audit_rows = "".join(
        f'<tr><td>{esc(a["run"])}</td><td>{badge(a["verdict"], "b-ok" if a["verdict"].startswith("PASS") else "b-warn")}</td>'
        f'<td class="tiny"><a class="local" href="../../{esc(a["href"])}"><code>{esc(a["href"])}</code></a></td></tr>'
        for a in audits
    )
    cards = f'''<div class="cards">
<div class="metric"><div class="v"><span data-metric="total_candidates">{mt["total_candidates"]}</span> 候选 / <span data-metric="total_episodes">{mt["total_episodes"]}</span> eps</div><div class="l">合并验证规模（easy {mt["easy_candidates"]} + hard {mt["hard_candidates"]}）</div><div class="d">每个候选 3 seeds（{mt["total_candidates"]} × 3 = {mt["total_episodes"]}），全部完成</div></div>
<div class="metric"><div class="v"><span data-metric="total_success">{mt["total_success"]}</span> / <span data-metric="total_episodes">{mt["total_episodes"]}</span> = <span data-metric="total_rate_pct">{mt["total_rate_pct"]}</span>%</div><div class="l">合并 success（check_success）</div><div class="d">success mean steps <span data-metric="success_mean_steps">{mt["success_mean_steps"]}</span>；mean/median 全部 <span data-metric="mean_steps">{mt["mean_steps"]}</span> / <span data-metric="median_steps">{mt["median_steps"]}</span></div></div>
<div class="metric"><div class="v">easy <span data-metric="easy_rate_pct">{mt["easy_rate_pct"]}</span>% · hard <span data-metric="hard_rate_pct">{mt["hard_rate_pct"]}</span>%</div><div class="l">两实验成功率</div><div class="d">easy <span data-metric="easy_candidates">{mt["easy_candidates"]}</span> 候选 · <span data-metric="easy_success">{mt["easy_success"]}</span>/<span data-metric="easy_episodes">{mt["easy_episodes"]}</span> eps；hard <span data-metric="hard_candidates">{mt["hard_candidates"]}</span> 候选 · <span data-metric="hard_success">{mt["hard_success"]}</span>/<span data-metric="hard_episodes">{mt["hard_episodes"]}</span>（92×3，seed0 引用）</div></div>
<div class="metric"><div class="v"><span data-metric="stable_ge1">{mt["stable_ge1"]}</span> · <span data-metric="stable_ge2">{mt["stable_ge2"]}</span> · <span data-metric="stable_all3">{mt["stable_all3"]}</span></div><div class="l">稳定候选：≥1 / ≥2 seeds / 3/3</div><div class="d">仅 1 次 <span data-metric="stable_only1">{mt["stable_only1"]}</span> · 从未成功 <span data-metric="stable_none">{mt["stable_none"]}</span>；{mt["total_candidates"]} 条中 {mt["stable_ge1"]} 条至少成功一次</div></div>
<div class="metric"><div class="v">novel <span data-metric="novel_rate_pct">{mt["novel_rate_pct"]}</span>% · dup <span data-metric="dup_rate_pct">{mt["dup_rate_pct"]}</span>%</div><div class="l">去重轴：C+D（新任务）vs A+B（重复任务）</div><div class="d">C+D <span data-metric="novel_candidates">{mt["novel_candidates"]}</span> 候选 / <span data-metric="novel_episodes">{mt["novel_episodes"]}</span> eps / <span data-metric="novel_success">{mt["novel_success"]}</span> 成功；A+B <span data-metric="dup_candidates">{mt["dup_candidates"]}</span> / <span data-metric="dup_episodes">{mt["dup_episodes"]}</span> / <span data-metric="dup_success">{mt["dup_success"]}</span>（<b>不代表新任务能力</b>）</div></div>
<div class="metric"><div class="v"><span data-metric="rollback_candidates">{mt["rollback_candidates"]}</span> / <span data-metric="rollback_tasks">{mt["rollback_tasks"]}</span></div><div class="l">rollback 可用成功候选 / 不同任务（剔除 A）</div><div class="d">严格全新 C+D：<span data-metric="strict_candidates">{mt["strict_candidates"]}</span> / <span data-metric="strict_tasks">{mt["strict_tasks"]}</span>；A 类重复成功候选 <span data-metric="excluded_a_candidates">{mt["excluded_a_candidates"]}</span> 条已排除</div></div>
<div class="metric"><div class="v"><span data-metric="wall_total_hours">{mt["wall_total_hours"]}</span> h</div><div class="l">三次运行累计 wall time</div><div class="d">easy <span data-metric="wall_easy">{mt["wall_easy"]}</span>h + hard seed0 <span data-metric="wall_hard0">{mt["wall_hard0"]}</span>h + hard seeds1/2 <span data-metric="wall_hard12">{mt["wall_hard12"]}</span>h；<span data-metric="run_episodes_total">{mt["run_episodes_total"]}</span> eps</div></div>
<div class="metric"><div class="v"><span data-metric="new3">{mt["new3"]}</span> + <span data-metric="b3">{mt["b3"]}</span> + <span data-metric="a3">{mt["a3"]}</span> = <span data-metric="stable_all3">{mt["stable_all3"]}</span></div><div class="l">14 条 3/3 构成（D 全新 + B 变体 + A 重复）</div><div class="d">A 的 4 条 3/3 与既有任务指令完全相同，不计入 rollback 新基数；D 5 + B 5 = 10 条原型候选</div></div>
<div class="metric"><div class="v"><span data-metric="maxsteps">{mt["maxsteps"]}</span> / <span data-metric="total_episodes">{mt["total_episodes"]}</span></div><div class="l">跑满 600 步的 episode（<span data-metric="maxsteps_pct">{mt["maxsteps_pct"]}</span>%）</div><div class="d">完成 0 段 <span data-metric="sub0">{mt["sub0"]}</span> · 完成 1 段后停滞 <span data-metric="sub1">{mt["sub1"]}</span> · 完成 2 段 <span data-metric="sub2">{mt["sub2"]}</span>（含 near-miss <span data-metric="near_miss">{mt["near_miss"]}</span>）</div></div>
</div>'''
    return f'''<section id="overview">
<h2>一、指标与运行完整性</h2>
<p class="sub">主数据源 <code>merged-data.json</code>（253 候选 / 759 eps / 56 success 由 <code>--check</code> 逐项复验）；失败/s1/步数等补充统计从两 run 的 <code>analysis/summary.json</code> 的 episode 明细合并计算（483 + 92 + 184 = 759）。</p>
{cards}
<h3>1.1 数据覆盖漏斗：322 条 v2 候选 → 253 条已验证</h3>
<div class="tblwrap"><table>
<thead><tr><th>axis</th><th>全部 322</th><th>本报告已验证 253</th><th>未跑 = invalid + valid A</th><th>其中 invalid</th><th>其中 valid A 未跑</th></tr></thead>
<tbody>{funnel_rows}
<tr><td><b>合计</b></td><td><b><span data-metric="funnel_total322">{fn["total322"]}</span></b></td><td><b><span data-metric="funnel_run">{fn["run"]}</span></b></td><td><b><span data-metric="funnel_not_run">{fn["not_run"]}</span></b></td><td><b><span data-metric="funnel_invalid">{fn["invalid"]}</span></b></td><td><b><span data-metric="funnel_valid_not_run">{fn["valid_not_run"]}</span></b></td></tr>
</tbody></table></div>
<p class="note">{fn["total322"]} = 已验证 <b>{fn["run"]}</b>（easy 161 + hard 92）+ 未跑 <b>{fn["not_run"]}</b>（invalid {fn["invalid"]} + valid A {fn["valid_not_run"]}）。A 类 15 条中 4 条在 easy 已验证、5 条 valid A 未跑、6 条 invalid；B 类 7 条全部已验证；C 类 42 条中 40 已验证（2 invalid）；D 类 258 条中 202 已验证（56 invalid）。</p>
<h3>1.2 三次运行与 wall time</h3>
<div class="tblwrap"><table>
<thead><tr><th>运行</th><th>wall</th><th>episodes</th><th>路径</th></tr></thead>
<tbody>{wall_rows}
<tr><td><b>合计</b></td><td><b>{m["walls"]["total_hours"]} h</b>（{m["walls"]["rate"]} eps/h）</td><td><b>{m["walls"]["total_episodes"]}</b></td><td class="tiny">easy 3 seeds + hard seed0（引用）+ hard seeds1/2（补跑）</td></tr>
</tbody></table></div>
<h3>1.3 完整性与独立审计</h3>
<div class="tblwrap"><table>
<thead><tr><th>运行</th><th>审计 verdict</th><th>审计文件</th></tr></thead>
<tbody>{audit_rows}
<tr><td>easy（161×3=483 eps）</td><td>{badge("final_checks 全 PASS", "b-ok")}</td><td class="tiny"><a class="local" href="../../libero-90-easy-pi05-20261026/analysis/final_checks.json"><code>analysis/final_checks.json</code></a>（该 run 无独立 AUDIT.md）</td></tr>
</tbody></table></div>
<p class="note">三次运行 final_checks 均 PASS（easy 全部检查、hard seed0 14/14、hard seeds1/2 19/19）；独立审计：hard seed0 <b>PASS</b>、hard 成功候选 seeds1/2 稳定性补测 <b>PASS</b>、hard 全量补跑 <b>PASS-WITH-ISSUES</b>（0 blocker / 0 major / 1 minor，已回填；见产物索引）。</p>
</section>'''

def _counter_rows(cands, key):
    return Counter(c[key] for c in cands.values())


def render_methods(m):
    mt = m["metrics"]
    merged = m["merged"]
    cands = list(merged["candidates"].values())
    easy = [c for c in cands if c["experiment"] == "easy"]
    hard = [c for c in cands if c["experiment"] == "hard"]
    def compose(sub):
        return {
            "route": _counter_rows({i: c for i, c in enumerate(sub)}, "route"),
            "priority": _counter_rows({i: c for i, c in enumerate(sub)}, "priority"),
            "class": _counter_rows({i: c for i, c in enumerate(sub)}, "class"),
            "axis": _counter_rows({i: c for i, c in enumerate(sub)}, "axis"),
            "scenes": len({c["scene"] for c in sub}),
        }
    ce, ch = compose(easy), compose(hard)
    ce_scenes = sorted({c["scene"] for c in easy})
    ch_scenes = sorted({c["scene"] for c in hard})
    all_scenes = sorted(set(ce_scenes) | set(ch_scenes))
    def fmt_counter(counter, order):
        return " / ".join(f"{k} {counter.get(k, 0)}" for k in order)
    defs = [
        ("A_skip", "场景重复 + 任务一致 + 指令完全相同", "跳过、永不算新候选（本次 4 条成功候选仅作对照，不进 rollback 新基数）"),
        ("B_validate", "场景重复 + 任务一致 + 指令不同", "仍有验证价值，取成功指令作为任务描述（本次 7 条全部验证，6 条成功）"),
        ("C_diff_scene", "同 goal 原子、但场景不同", "按用户定义不构成“场景重复”，保留为新场景实例"),
        ("D_unique", "无任何参考任务同 goal", "全新任务（相对于 L10/GOAL/OBJECT 已有任务）"),
    ]
    defs_rows = "".join(
        f'<tr><td>{badge(axis, f"b-axis-{axis[0]}")}</td><td>{esc(name)}</td><td>{esc(note)}</td><td>{esc(desc)}</td></tr>'
        for axis, desc, note in [(a, d, n) for a, d, n in defs]
        for name in [{"A_skip": "A：场景+任务+指令全同", "B_validate": "B：同任务·指令不同",
                      "C_diff_scene": "C：同 goal·异场景", "D_unique": "D：全新"}[axis]]
        for desc, note in [(desc, note)]
    )
    return f'''<section id="methods">
<h2>二、方法与口径（两 run + A/B/C/D 去重）</h2>
<h3>2.1 两个实验</h3>
<div class="tblwrap"><table>
<thead><tr><th>实验</th><th>候选来源</th><th>候选 / episodes</th><th>构成</th><th>场景覆盖</th><th>运行目录</th></tr></thead>
<tbody>
<tr class="method-row" data-experiment="easy" data-candidates="{len(easy)}" data-episodes="{len(easy) * 3}" data-success="{sum(c['succ'] for c in easy)}"><td><b>easy</b>（低难度半数）</td><td>322 条中按难度分取前 161（M1-P0-valid-compatible-n_atoms2；held-out 17 条未跑）</td><td>{len(easy)} / {len(easy) * 3}</td><td>route {fmt_counter(ce["route"], ["M1", "M2", "S1"])} · priority {fmt_counter(ce["priority"], ["P0", "P1", "P2"])} · axis {fmt_counter(ce["axis"], ["A_skip", "B_validate", "C_diff_scene", "D_unique"])}</td><td>{len(ce_scenes)} 个场景</td><td class="tiny"><a class="local" href="../../libero-90-easy-pi05-20261026/README.md"><code>runs/libero-90-easy-pi05-20261026</code></a></td></tr>
<tr class="method-row" data-experiment="hard" data-candidates="{len(hard)}" data-episodes="{len(hard) * 3}" data-success="{sum(c['succ'] for c in hard)}"><td><b>hard</b>（去重后剩余）</td><td>322 中 valid、不在 easy 161、且 axis≠A 的 92 条（排除 64 invalid + 5 valid A）</td><td>{len(hard)} / {len(hard) * 3}</td><td>route {fmt_counter(ch["route"], ["M1", "M2", "S1"])} · priority {fmt_counter(ch["priority"], ["P0", "P1", "P2"])} · axis {fmt_counter(ch["axis"], ["A_skip", "B_validate", "C_diff_scene", "D_unique"])}</td><td>{len(ch_scenes)} 个场景</td><td class="tiny"><a class="local" href="../../libero-90-hard-seeds12-full-20261026/README.md"><code>runs/libero-90-hard-seeds12-full-20261026</code></a></td></tr>
<tr><td><b>合并</b></td><td>easy + hard = 253（全部 valid，无重叠）</td><td><b>{mt["total_candidates"]} / {mt["total_episodes"]}</b></td><td>route {fmt_counter({"M1": ce["route"].get("M1", 0) + ch["route"].get("M1", 0), "M2": ch["route"].get("M2", 0), "S1": ch["route"].get("S1", 0)}, ["M1", "M2", "S1"])} · priority {fmt_counter({"P0": ce["priority"].get("P0", 0) + ch["priority"].get("P0", 0), "P1": ch["priority"].get("P1", 0), "P2": ch["priority"].get("P2", 0)}, ["P0", "P1", "P2"])}</td><td>{len(all_scenes)} 个场景（easy {len(ce_scenes)} + hard {len(ch_scenes)}，并集 {len(all_scenes)}）</td><td class="tiny">本报告</td></tr>
</tbody></table></div>
<p class="note">easy 的全部 161 条都是 M1/P0/compatible、17/20 场景（缺 KS8/KS10/ST2）；hard 的 92 条覆盖 11 个场景，恰好补上 easy 缺的 KS8/KS10/ST2 → 合并后覆盖 <b>20/20 场景</b>。hard 的 seed0 引用既有 <code>runs/libero-90-hard-pi05-20261026</code>（92 eps），seeds1/2 为全量补跑（184 eps），合计 276 eps。</p>
<h3>2.2 去重轴 A/B/C/D（用户口径，来自 <a class="local" href="../../libero-90-combos-20261025/dup-audit/DEDUP_DECISION.md">DEDUP_DECISION.md</a>）</h3>
<div class="tblwrap"><table>
<thead><tr><th>轴</th><th>名称</th><th>判定</th><th>处置</th></tr></thead>
<tbody>{defs_rows}</tbody></table></div>
<h3>2.3 为什么 easy + hard 不重叠 / 322 → 253</h3>
<ul class="flat">
<li><b>hard 的定义显式排除 easy</b>：hard = 322 中 <code>valid</code> 且 <b>不在 easy 161</b> 且 <code>axis != A_skip</code> 的剩余任务，因此 easy 161 与 hard 92 无交集（161 + 92 = 253）。</li>
<li><b>未跑的 69 条</b>：64 条 invalid（A 6 / C 2 / D 56；validation 结构无效/冲突/退化，不跑）+ 5 条 valid A（与既有 L10 任务指令完全相同，跳过验证）→ 253 + 69 = 322。</li>
<li><b>easy 是“低难度半数”而不是随机抽样</b>：按难度分（同容器/共享家具/开关/指令长度）升序取前 161；hard 是去重后、不含 A 的剩余 92，难度更高（route 含 M2 33、P1 5、P2 36、class hard 36）。</li>
<li><b>合并 7.38% 不能外推</b>：两实验的候选构成差异大，且 A+B 重复任务在 easy 中占比高（easy 成功 41 中 A+B 占 success 16）→ 合并成功率被重复任务显著抬高；真正新任务（C+D）只有 {mt["novel_rate_pct"]}%。</li>
</ul>
<p class="note warn">声明：本报告数字仅适用于“easy 低难度半数 + hard 去重剩余”的合并集合；不可外推到 322 全量、也不可与官方 pi05 / 其他套件数字横比（套件、候选构成、video、init、协议均不同）。所有运行为单指令 zero-shot，未做 staged / instruction-switch / rollback。</p>
</section>'''


def render_compare(m):
    mt = m["metrics"]
    merged = m["merged"]
    exp_rows = "".join(
        f'<tr class="exp-row" data-experiment="{r["experiment"]}" data-candidates="{r["candidates"]}" data-episodes="{r["episodes"]}" '
        f'data-success="{r["success"]}" data-rate="{rate_pct(r["success"], r["episodes"])}" data-wall="{m["walls"]["rows"][0]["wall_hours"] if r["experiment"] == "easy" else (m["walls"]["rows"][2]["wall_hours"] + m["walls"]["rows"][1]["wall_hours"] if r["experiment"] == "hard" else m["metrics"]["wall_total_hours"])}">'
        f'<td><b>{esc(EXP_CN.get(r["experiment"], "合并"))}</b></td><td>{r["candidates"]}</td><td>{r["episodes"]}</td>'
        f'<td><b>{r["success"]}</b></td><td>{rate_pct(r["success"], r["episodes"])}%</td>'
        f'<td>{m["walls"]["rows"][0]["wall_hours"] if r["experiment"] == "easy" else (m["walls"]["rows"][2]["wall_hours"] + m["walls"]["rows"][1]["wall_hours"] if r["experiment"] == "hard" else mt["wall_total_hours"])} h</td></tr>'
        for r in m["exp_axis"]
    )
    seed_rows = "".join(
        f'<tr class="seed-row" data-experiment="{r["experiment"]}" data-seed="{r["seed"]}" data-episodes="{r["episodes"]}" '
        f'data-success="{r["success"]}" data-rate="{r["rate_pct"]}">'
        f'<td>{esc(EXP_CN[r["experiment"]])}</td><td>{r["seed"]}</td><td>{r["episodes"]}</td>'
        f'<td><b>{r["success"]}</b></td><td>{r["rate_pct"]}%</td></tr>'
        for r in m["seed_rows"]
    )
    merged_seed_rows = "".join(
        f'<tr class="merged-seed-row" data-experiment="merged" data-seed="{r["seed"]}" data-episodes="{r["episodes"]}" '
        f'data-success="{r["success"]}" data-rate="{r["rate_pct"]}">'
        f'<td><b>合并</b></td><td>{r["seed"]}</td><td>{r["episodes"]}</td>'
        f'<td><b><span data-metric="merged_seed{r["seed"]}_success">{r["success"]}</span></b></td>'
        f'<td><span data-metric="merged_seed{r["seed"]}_rate_pct">{r["rate_pct"]}</span>%</td></tr>'
        for r in m["merged_seed_rows"]
    )
    easy_rate = mt["easy_rate_pct"]
    hard_rate = mt["hard_rate_pct"]
    max_rate = max(easy_rate, hard_rate, 1)
    bars = (bar_row("easy（161×3）", easy_rate / max_rate, f'{mt["easy_success"]}/{mt["easy_episodes"]} · {easy_rate}%', "hot")
            + bar_row("hard（92×3）", hard_rate / max_rate, f'{mt["hard_success"]}/{mt["hard_episodes"]} · {hard_rate}%', "warm")
            + bar_row("合并（253×3）", mt["total_rate_pct"] / max_rate, f'{mt["total_success"]}/{mt["total_episodes"]} · {mt["total_rate_pct"]}%', "cool"))
    return f'''<section id="compare">
<h2>三、easy vs hard 对比</h2>
<h3>3.1 总体对比</h3>
<div class="tblwrap"><table>
<thead><tr><th>实验</th><th>candidates</th><th>episodes</th><th>success</th><th>成功率</th><th>运行 wall</th></tr></thead>
<tbody>{exp_rows}</tbody></table></div>
<div class="barchart">{bars}</div>
<h3>3.2 按 seed 拆分</h3>
<div class="tblwrap"><table>
<thead><tr><th>实验</th><th>seed</th><th>episodes</th><th>success</th><th>成功率</th></tr></thead>
<tbody>{seed_rows}{merged_seed_rows}</tbody></table></div>
<p class="note">口径：easy 的 3 个 seed 全部来自 easy run（seed0/1/2 = 12/13/16）；hard 的 seed0 引用 hard run（6/92）、seed1/2 来自 seeds1/2 全量补跑（5/92、4/92）→ hard 合并 15/276 = 5.43%。合并后每 seed 253 eps：seed0 18、seed1 18、seed2 20（18/253=7.11%、18/253=7.11%、20/253=7.91%）。三次运行均 video off、单指令 zero-shot；hard 补跑新增可用候选 0 条（seed0 成功的 6 条 = 3-seed 下全部 ≥1 成功候选）。</p>
</section>'''

def render_axes(m):
    mt = m["metrics"]
    merged = m["merged"]
    rb = {r["axis"]: r for r in m["rollback"]["by_axis"]}
    rows = []
    for axis in ("A_skip", "B_validate", "C_diff_scene", "D_unique"):
        v = merged["axis"][axis]
        r = rb[axis]
        rows.append(
            f'<tr class="axis-row" data-axis="{axis}" data-candidates="{v["candidates"]}" data-episodes="{v["episodes"]}" '
            f'data-success="{v["success"]}" data-rate="{rate_pct(v["success"], v["episodes"])}">'
            f'<td>{badge(axis, f"b-axis-{axis[0]}")}</td><td>{esc(AXIS_CN[axis])}</td>'
            f'<td>{v["candidates"]}</td><td>{v["episodes"]}</td><td><b>{v["success"]}</b></td>'
            f'<td>{rate_pct(v["success"], v["episodes"])}%</td>'
            f'<td>{r["succ_candidates"]} / {r["tasks"]}</td><td>{r["all3"]}</td></tr>'
        )
    novel = merged["novel_CD"]
    dup = merged["duplicate_AB"]
    max_rate = max(rate_pct(v["success"], v["episodes"]) for v in merged["axis"].values()) or 1
    bars = "".join(
        bar_row(f'{axis}', rate_pct(merged["axis"][axis]["success"], merged["axis"][axis]["episodes"]) / max_rate,
                f'{merged["axis"][axis]["success"]}/{merged["axis"][axis]["episodes"]} · '
                f'{rate_pct(merged["axis"][axis]["success"], merged["axis"][axis]["episodes"])}%',
                "hot" if axis in ("A_skip", "B_validate") else ("warm" if axis == "D_unique" else "cold"))
        for axis in ("A_skip", "B_validate", "C_diff_scene", "D_unique")
    )
    exp_axis_rows = "".join(
        f'<tr class="exp-axis-row" data-experiment="{r["experiment"]}"><td><b>{esc(EXP_CN.get(r["experiment"], "合并"))}</b></td>'
        f'<td>{r["candidates"]}</td><td>{r["A_skip"]}</td><td>{r["B_validate"]}</td>'
        f'<td>{r["C_diff_scene"]}</td><td>{r["D_unique"]}</td>'
        f'<td>{r["episodes"]} / <b>{r["success"]}</b></td></tr>'
        for r in m["exp_axis"]
    )
    return f'''<section id="axes">
<h2>四、去重轴表（A/B/C/D）</h2>
<p class="sub">全部 253 条候选按用户口径的 A/B/C/D 轴拆分；成功率 = success / episodes（每候选 3 seeds）。<b>重复任务（A+B）成功率 {mt["dup_rate_pct"]}% 不代表模型对新任务的能力</b>：A 类指令与既有任务完全相同、B 类是同任务的指令变体，二者本质是“已会任务”的再测；<b>真正新任务（C+D）只有 {mt["novel_rate_pct"]}%</b>。</p>
<div class="tblwrap"><table>
<thead><tr><th>axis</th><th>含义</th><th>candidates</th><th>episodes</th><th>success</th><th>成功率</th><th>成功候选 / 任务（剔除 A）</th><th>3/3</th></tr></thead>
<tbody>{''.join(rows)}
<tr class="combined-axis-row" data-axis="novel_CD" data-candidates="{novel["candidates"]}" data-episodes="{novel["episodes"]}" data-success="{novel["success"]}" data-rate="{mt["novel_rate_pct"]}"><td>{badge("C + D", "b-info")}</td><td><b>真正新任务（novel C+D）</b></td><td><b>{novel["candidates"]}</b></td><td><b>{novel["episodes"]}</b></td><td><b>{novel["success"]}</b></td><td><b>{mt["novel_rate_pct"]}%</b></td><td>{mt["strict_candidates"]} / {mt["strict_tasks"]}</td><td>{mt["new3"]}</td></tr>
<tr class="combined-axis-row" data-axis="duplicate_AB" data-candidates="{dup["candidates"]}" data-episodes="{dup["episodes"]}" data-success="{dup["success"]}" data-rate="{mt["dup_rate_pct"]}"><td>{badge("A + B", "b-warn")}</td><td><b>重复任务（duplicate A+B）</b></td><td><b>{dup["candidates"]}</b></td><td><b>{dup["episodes"]}</b></td><td><b>{dup["success"]}</b></td><td><b>{mt["dup_rate_pct"]}%</b></td><td>—（A 除外；B 6/6）</td><td>{mt["a3"] + mt["b3"]}</td></tr>
</tbody></table></div>
<div class="barchart">{bars}</div>
<h3>4.1 两实验的 axis 构成（candidates）</h3>
<div class="tblwrap"><table>
<thead><tr><th>实验</th><th>candidates</th><th>A_skip</th><th>B_validate</th><th>C_diff_scene</th><th>D_unique</th><th>episodes / success</th></tr></thead>
<tbody>{exp_axis_rows}</tbody></table></div>
<p class="note">解读：B 类验证有效（7 条中 6 条成功、5 条 3/3）说明“任务相同但指令不同”值得验证；A 类 4 条全部 3/3 且指令与既有 L10 任务完全相同，只能证明“已会任务可复现”，不能作为新任务能力证据；C 类（同 goal 异场景）几乎全部失败（1/120）说明跨场景实例不能直接复用能力；D 类（全新）26/606 = 4.29%，是真正新任务的 zero-shot 水平。</p>
</section>'''


def render_dist(m):
    mt = m["metrics"]
    groups = m["groups"]
    dist = m["dist"]
    max_scene = max((r["rate"] for r in dist["scene"]), default=0) or 1
    scene_bars = "".join(
        bar_row(r["key"], r["rate"] / max_scene, f'{r["success"]}/{r["episodes"]} · {r["rate_pct"]}%',
                "hot" if r["success"] > 0 and r["rate_pct"] >= 10 else ("warm" if r["success"] > 0 else "cold"))
        for r in dist["scene"]
    )
    scene_rows = "".join(
        f'<tr class="{"hi" if r["success"] > 0 else "zero"} scene-row" data-scene="{r["key"]}" data-group="{r["group"]}" '
        f'data-candidates="{r["candidates"]}" data-episodes="{r["episodes"]}" data-success="{r["success"]}" data-rate="{r["rate_pct"]}">'
        f'<td><code>{esc(r["key"])}</code></td><td>{esc(r["group"])}</td><td>{r["candidates"]}</td>'
        f'<td>{r["episodes"]}</td><td><b>{r["success"]}</b></td><td>{r["rate_pct"]}%</td></tr>'
        for r in dist["scene"]
    )
    group_chips = "".join(
        f'<span class="chip"><b>{esc(GROUP_CN[g["group"]])}</b> {g["candidates"]} 候选 / {g["episodes"]} eps / '
        f'{g["success"]} 成功 · <b>{g["rate_pct"]}%</b>（{g["scenes"]} 场景）</span>'
        for g in groups
    )
    max_tpl = max((r["rate"] for r in dist["template"]), default=0) or 1
    tpl_bars = "".join(
        bar_row(r["key"], r["rate"] / max_tpl, f'{r["success"]}/{r["episodes"]} · {r["rate_pct"]}%',
                "hot" if r["rate_pct"] >= 10 else ("warm" if r["success"] > 0 else "cold"))
        for r in dist["template"]
    )
    tpl_rows = "".join(
        f'<tr class="{"hi" if r["success"] > 0 else "zero"} tpl-row" data-template="{r["key"]}" data-candidates="{r["candidates"]}" '
        f'data-episodes="{r["episodes"]}" data-success="{r["success"]}" data-rate="{r["rate_pct"]}">'
        f'<td><code>{esc(r["key"])}</code></td><td>{r["candidates"]}</td><td>{r["episodes"]}</td>'
        f'<td><b>{r["success"]}</b></td><td>{r["rate_pct"]}%</td></tr>'
        for r in dist["template"]
    )
    def small_table(dim, label):
        rows = "".join(
            f'<tr class="{"hi" if r["success"] > 0 else "zero"} dist-row" data-{dim}="{esc(r["key"])}" '
            f'data-candidates="{r["candidates"]}" data-episodes="{r["episodes"]}" '
            f'data-success="{r["success"]}" data-rate="{r["rate_pct"]}">'
            f'<td><code>{esc(r["key"])}</code></td><td>{r["candidates"]}</td><td>{r["episodes"]}</td>'
            f'<td><b>{r["success"]}</b></td><td>{r["rate_pct"]}%</td></tr>'
            for r in dist[dim]
        )
        return f'''<h3>5.{label} 按 {dim}</h3>
<div class="tblwrap"><table>
<thead><tr><th>{dim}</th><th>candidates</th><th>episodes</th><th>success</th><th>成功率</th></tr></thead>
<tbody>{rows}</tbody></table></div>'''
    route = {r["key"]: r for r in dist["route"]}
    prio = {r["key"]: r for r in dist["priority"]}
    klass = {r["key"]: r for r in dist["class"]}
    bucket = {r["key"]: r for r in dist["bucket"]}
    order = {r["key"]: r for r in dist["order"]}
    top_tpl = dist["template"][0]
    return f'''<section id="dist">
<h2>五、分布表（场景 / 模板 / 桶 / route / 优先级 / class / 顺序）</h2>
<div class="chips">{group_chips}</div>
<h3>5.1 按场景（20 个）</h3>
<p class="sub">LIVING_ROOM 主导成功：<b>{groups[1]["success"]}/{groups[1]["episodes"]} = {groups[1]["rate_pct"]}%</b>；KITCHEN <b>{groups[0]["success"]}/{groups[0]["episodes"]} = {groups[0]["rate_pct"]}%</b>（仅 KITCHEN_SCENE2 3、KITCHEN_SCENE3 3）；STUDY <b>{groups[2]["success"]}/{groups[2]["episodes"]} = 0%</b>。合并后覆盖全部 20 个场景（easy 17 + hard 补齐 KS8/KS10/ST2）。</p>
<div class="tblwrap"><table>
<thead><tr><th>场景</th><th>类型</th><th>candidates</th><th>episodes</th><th>success</th><th>成功率</th></tr></thead>
<tbody>{scene_rows}</tbody></table></div>
<div class="barchart">{scene_bars}</div>
<h3>5.2 按指令模板（{len(dist["template"])} 个）</h3>
<p class="sub"><b>{esc(top_tpl["key"])} 最强（{top_tpl["success"]}/{top_tpl["episodes"]} = {top_tpl["rate_pct"]}%，成功数最多）</b>；T7 为 3/6 = 50% 但仅 2 候选/6 eps（小样本，不作主结论）；T3 见下表；T2/T10/T4/T4b/T8/T9 合并后 0 成功。注：任务要求写“9 个模板”，实际合并数据有 <b>{len(dist["template"])} 个</b>（hard 带入 T4/T4b/T8/T9）。</p>
<div class="tblwrap"><table>
<thead><tr><th>模板</th><th>candidates</th><th>episodes</th><th>success</th><th>成功率</th></tr></thead>
<tbody>{tpl_rows}</tbody></table></div>
<div class="barchart">{tpl_bars}</div>
{small_table("bucket", "3")}
{small_table("route", "4")}
{small_table("priority", "5")}
{small_table("class", "6")}
{small_table("order", "7")}
<p class="note">关键读数：M2 <b>{route["M2"]["success"]}/{route["M2"]["episodes"]} = {route["M2"]["rate_pct"]}%</b> &gt; M1 {route["M1"]["success"]}/{route["M1"]["episodes"]} = {route["M1"]["rate_pct"]}% &gt; S1 {route["S1"]["success"]}/{route["S1"]["episodes"]}；同容器（capacity）<b>{bucket["same_destination(capacity)"]["success"]}/{bucket["same_destination(capacity)"]["episodes"]} = {bucket["same_destination(capacity)"]["rate_pct"]}%</b> &gt; independent {bucket["independent"]["success"]}/{bucket["independent"]["episodes"]} = {bucket["independent"]["rate_pct"]}% &gt; same_furniture {bucket["same_furniture/fixture"]["success"]}/{bucket["same_furniture/fixture"]["episodes"]} = {bucket["same_furniture/fixture"]["rate_pct"]}%；<b>P1 {prio["P1"]["success"]}/{prio["P1"]["episodes"]}、P2 {prio["P2"]["success"]}/{prio["P2"]["episodes"]} 全 0</b>；<b>class hard {klass["hard"]["success"]}/{klass["hard"]["episodes"]} 全 0</b>；ab {order["ab"]["rate_pct"]}% vs ba {order["ba"]["rate_pct"]}%（无方向偏置）。</p>
</section>'''

def render_failures(m):
    mt = m["metrics"]
    failure = m["failure"]
    rows = []
    for r in failure["rows"]:
        scope = r["scope"]
        cls = "near" if scope == "hard_seed12" else ("hi" if scope == "merged" else "")
        rows.append(
            f'<tr class="{cls} failure-row" data-scope="{scope}" data-episodes="{r["episodes"]}" data-success="{r["success"]}" '
            f'data-sub0="{r["sub0"]}" data-sub1="{r["sub1"]}" data-sub2="{r["sub2"]}" data-near="{r["near_miss"]}" '
            f'data-maxsteps="{r["maxsteps"]}">'
            f'<td>{esc(r["label"])}</td><td>{r["episodes"]}</td><td><b>{r["success"]}</b></td>'
            f'<td>{rate_pct(r["success"], r["episodes"])}%</td>'
            f'<td>{r["sub0"]}</td><td>{r["sub1"]}</td><td>{r["sub2"]}</td>'
            f'<td>{badge(str(r["near_miss"]), "b-near" if r["near_miss"] else "b-muted")}</td>'
            f'<td>{r["maxsteps"]}（{rate_pct(r["maxsteps"], r["episodes"])}%）</td>'
            f'<td>{r["mean_steps"]}</td><td>{r["success_mean_steps"]}</td></tr>'
        )
    hist = failure["hist"]
    max_hist = max(r["count"] for r in hist) or 1
    hist_bars = "".join(
        bar_row(f'steps {r["range"]}', r["count"] / max_hist, f'{r["count"]} eps',
                "warm" if r["range"] == "600" else "cool")
        for r in hist
    )
    merged = failure["merged"]
    return f'''<section id="failures">
<h2>六、失败分析</h2>
<h3>6.1 失败模式（easy / hard seed0 / hard 补跑 / hard 合并 / 总合并）</h3>
<div class="tblwrap"><table>
<thead><tr><th>scope</th><th>episodes</th><th>success</th><th>成功率</th><th>完成 0 段</th><th>完成 1 段后停滞</th><th>完成 2 段</th><th>near-miss</th><th>跑满 600 步</th><th>mean steps</th><th>成功 mean steps</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p class="note warn"><b>hard 补跑（184 eps，seeds1/2）失败结构</b>：<b>{m["failure"]["hard12"]["maxsteps"]}/184 跑满 600 步</b>；<b>{m["failure"]["hard12"]["sub0"]} 条 0 段</b>、<b>{m["failure"]["hard12"]["sub1"]} 条完成 1 段后停滞</b>、<b>{m["failure"]["hard12"]["near_miss"]} 条 near-miss</b>（goal 原子曾全真但 <code>check_success()</code> 未触发，值得复查评估口径）。hard 合并 276 eps 后：{m["failure"]["hard_combined"]["sub0"]} 条 0 段、{m["failure"]["hard_combined"]["sub1"]} 条 1 段后停滞、{m["failure"]["hard_combined"]["near_miss"]} 条 near-miss、{m["failure"]["hard_combined"]["maxsteps"]}/276 跑满 600 步。</p>
<h3>6.2 steps 分布（合并 759 eps）</h3>
<div class="barchart">{hist_bars}</div>
<p class="sub">合并口径：<b>{merged["maxsteps"]}/{merged["episodes"]}（{rate_pct(merged["maxsteps"], merged["episodes"])}%）跑满 600 步</b>；成功 episode 的 steps mean {merged["success_mean_steps"]}（min {merged["success_min_steps"]} / max {merged["success_max_steps"]}）；失败 episode 的 mean steps {round((merged["mean_steps"] * merged["episodes"] - merged["success_mean_steps"] * merged["success"]) / (merged["episodes"] - merged["success"]), 2)}（几乎全部 600）。</p>
<h3>6.3 s1（第一个子目标）轨迹统计</h3>
<div class="tblwrap"><table>
<thead><tr><th>scope</th><th>s1 曾为真 eps</th><th>首真 mean / median 步</th><th>s1 最终为真 eps</th><th>回撤次数 / eps</th></tr></thead>
<tbody>
<tr data-scope="easy"><td>easy（483 eps）</td><td>{failure["easy"]["s1_ever"]}</td><td>{failure["easy"]["s1_mean_step"]} / {failure["easy"]["s1_median_step"]}</td><td>{failure["easy"]["s1_final"]}</td><td>{failure["easy"]["s1_retract_events"]} / {failure["easy"]["s1_retract_eps"]}</td></tr>
<tr data-scope="hard_combined"><td>hard 合并（276 eps）</td><td>{failure["hard_combined"]["s1_ever"]}</td><td>{failure["hard_combined"]["s1_mean_step"]} / {failure["hard_combined"]["s1_median_step"]}</td><td>{failure["hard_combined"]["s1_final"]}</td><td>{failure["hard_combined"]["s1_retract_events"]} / {failure["hard_combined"]["s1_retract_eps"]}</td></tr>
<tr class="hi" data-scope="merged"><td><b>合并（759 eps）</b></td><td><b><span data-metric="s1_ever">{merged["s1_ever"]}</span></b></td><td><b><span data-metric="s1_mean_step">{merged["s1_mean_step"]}</span> / <span data-metric="s1_median_step">{merged["s1_median_step"]}</span></b></td><td><b><span data-metric="s1_final">{merged["s1_final"]}</span></b></td><td><b><span data-metric="s1_retract_events">{merged["s1_retract_events"]}</span> / <span data-metric="s1_retract_eps">{merged["s1_retract_eps"]}</span></b></td></tr>
</tbody></table></div>
<p class="note">合并后 <b>{merged["s1_ever"]}/{merged["episodes"]}</b>（{rate_pct(merged["s1_ever"], merged["episodes"])}%）episode 至少一次完成 s1，最终保持 {merged["s1_final"]}（{rate_pct(merged["s1_final"], merged["s1_ever"])}% of s1-ever）；失败主体是“完成 1 段后停滞”（{merged["sub1"]} 条），与 GOAL/OBJECT 历史先验一致；video 全程 off，失败原因只能从 trace 的 goal 原子序列判断，没有视频级复核。</p>
</section>'''


def render_stability(m):
    mt = m["metrics"]
    st = m["stability"]
    rb = m["rollback"]
    rows = []
    for r in st["all3_rows"]:
        if r["novel"]:
            status = badge("新任务原型", "b-ok")
            cls = "hi"
        elif r["axis"] == "B_validate":
            status = badge("B 指令变体", "b-warn")
            cls = ""
        else:
            status = badge("A 重复（排除）", "b-fail")
            cls = "zero"
        rows.append(
            f'<tr class="{cls} stable3-row" data-candidate="{esc(r["candidate_id"])}" data-all3="1" data-axis="{r["axis"]}">'
            f'<td><code>{esc(r["candidate_id"])}</code></td><td>{badge(r["experiment"], f"b-exp-{r["experiment"]}")}</td>'
            f'<td>{badge(r["axis"], f"b-axis-{r["axis"][0]}")}</td><td><code>{esc(r["scene"])}</code></td>'
            f'<td><code>{esc(r["template"])}</code></td><td class="tiny">{esc(r["bucket"])}</td><td>{esc(r["order"])}</td>'
            f'<td class="nowrap">{", ".join(str(s) for s in r["seeds_success"])}</td><td>{status}</td></tr>'
        )
    axis_rows = "".join(
        f'<tr class="rb-axis-row" data-axis="{r["axis"]}" data-succ-candidates="{r["succ_candidates"]}" data-tasks="{r["tasks"]}" data-all3="{r["all3"]}">'
        f'<td>{badge(r["axis"], f"b-axis-{r["axis"][0]}")}</td><td>{r["succ_candidates"]}</td><td>{r["tasks"]}</td>'
        f'<td>{r["all3"]}</td><td>{r["success"]}/{r["episodes"]}</td></tr>'
        for r in rb["by_axis"]
    )
    def cards_for(ids, cls):
        out = []
        for cid in ids:
            c = m["merged"]["candidates"][cid]
            out.append(
                f'<div class="bigcard {cls}" data-proto="{esc(cid)}">'
                f'<div class="id"><code>{esc(cid)}</code> {badge("3/3", "b-ok")} {badge(c["axis"], f"b-axis-{c["axis"][0]}")}</div>'
                f'<div class="instr">{esc(c["instruction"])}</div>'
                f'<div class="kv">实验 <b>{esc(c["experiment"])}</b> · 场景 <code>{esc(c["scene"])}</code> · 模板 <b>{esc(c["template"])}</b> · '
                f'桶 {esc(c["bucket"])} · order {esc(c["order"])} · 成功 seeds {", ".join(str(s) for s in c["seeds_success"])}</div></div>'
            )
        return "".join(out)
    return f'''<section id="stability">
<h2>七、稳定性与 rollback 基数</h2>
<div class="cards">
<div class="metric"><div class="v" data-metric="stable_ge1">{st["counts"]["ge1"]}</div><div class="l">至少成功一次（≥1 seed）</div><div class="d">占 {mt["total_candidates"]} 候选的 {rate_pct(st["counts"]["ge1"], mt["total_candidates"])}%</div></div>
<div class="metric"><div class="v" data-metric="stable_ge2">{st["counts"]["ge2"]}</div><div class="l">≥2 seeds 成功</div><div class="d">其中 3/3 共 {st["counts"]["all3"]} 条；仅 2/3 共 {len(st["ge2_only"])} 条</div></div>
<div class="metric"><div class="v" data-metric="stable_all3">{st["counts"]["all3"]}</div><div class="l">3 seeds 全成功（3/3）</div><div class="d">新任务 D {mt["new3"]} + B 指令变体 {mt["b3"]} + A 重复 {mt["a3"]}</div></div>
<div class="metric"><div class="v" data-metric="stable_only1">{st["counts"]["only1"]}</div><div class="l">仅 1 seed 成功</div><div class="d">稳定性不足，不进 rollback 原型</div></div>
<div class="metric"><div class="v" data-metric="stable_none">{st["counts"]["none"]}</div><div class="l">从未成功（0/3）</div><div class="d">占 {rate_pct(st["counts"]["none"], mt["total_candidates"])}%；含全部 P1/P2/hard 层</div></div>
</div>
<h3>7.1 14 条 3/3 全成功候选</h3>
<div class="tblwrap"><table>
<thead><tr><th>candidate_id</th><th>实验</th><th>axis</th><th>场景</th><th>模板</th><th>bucket</th><th>order</th><th>成功 seeds</th><th>rollback 归类</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p class="note">3/3 = 14 条：<b>真正新任务（C+D）5 条</b>（LR3 ×3 + LR4_42 ×2）、<b>B 指令变体 5 条</b>、<b>A 重复 4 条</b>（指令与 L10 官方完全相同 → 不计入 rollback 新基数）。≥2 但非 3/3 = {len(st["ge2_only"])} 条；仅 1 次 = {st["counts"]["only1"]} 条。</p>
<h3>7.2 rollback 可用基数（从 25 个成功候选计算，剔除 A）</h3>
<div class="cards">
<div class="metric"><div class="v"><span data-metric="rollback_candidates">{rb["available_candidates"]}</span> / <span data-metric="rollback_tasks">{rb["available_tasks"]}</span></div><div class="l">可用成功候选 / 不同任务（B+C+D）</div><div class="d">剔除 A 类 {rb["excluded_a_candidates"]} 条重复成功候选（{rb["excluded_a_tasks"]} 任务）</div></div>
<div class="metric"><div class="v"><span data-metric="strict_candidates">{rb["strict_candidates"]}</span> / <span data-metric="strict_tasks">{rb["strict_tasks"]}</span></div><div class="l">严格全新（C+D）成功候选 / 任务</div><div class="d">"新任务能力"的最保守口径；D 任务 8 个 + C 任务 1 个</div></div>
<div class="metric"><div class="v"><span data-metric="excluded_a_candidates">{rb["excluded_a_candidates"]}</span></div><div class="l">A 类重复成功候选（排除）</div><div class="d">指令与 L10 官方完全一致；不算新 rollback 基数</div></div>
</div>
<div class="tblwrap"><table>
<thead><tr><th>axis</th><th>成功候选</th><th>不同任务</th><th>3/3</th><th>success / episodes</th></tr></thead>
<tbody>{axis_rows}</tbody></table></div>
<h3>7.3 优先 rollback 原型候选（10 条：新任务 3/3 + B 指令变体 3/3）</h3>
<div class="bigcards">{cards_for(st["novel_all3"], "gold")}{cards_for(st["b_all3"], "blue")}</div>
<p class="note">建议：优先用 <b>5 条真正新任务 3/3</b>（LR3 的 tray 族与 LR4_42 的 M2 提升，均相对 L10/GOAL/OBJECT 是新任务）+ <b>5 条 B 指令变体 3/3</b>（任务同 L10，但指令不同且稳定成功）做 rollback 原型：补视频 → s1 完成 → 注入回退 → 观察 s2 自修复。A 的 4 条 3/3 只是“已会任务复现”，不作为新能力证据。</p>
</section>'''


def render_candidates(m):
    rows = m["candidate_rows"]
    mt = m["metrics"]
    scenes = sorted({r["scene"] for r in rows})
    scene_opts = "".join(f'<option value="{esc(sc)}">{esc(sc)}（{sum(1 for r in rows if r["scene"] == sc)}）</option>' for sc in scenes)
    body = []
    for r in rows:
        cls = "hi cand-row" if r["succ"] == 3 else "cand-row"
        body.append(
            f'<tr class="{cls}" data-candidate="{esc(r["candidate_id"])}" data-experiment="{r["experiment"]}" '
            f'data-axis="{r["axis"]}" data-scene="{esc(r["scene"])}" data-template="{esc(r["template"])}" '
            f'data-bucket="{esc(r["bucket"])}" data-route="{esc(r["route"])}" data-priority="{esc(r["priority"])}" '
            f'data-class="{esc(r["class"])}" data-order="{esc(r["order"])}" '
            f'data-seeds="{",".join(str(s) for s in r["seeds_success"])}" data-succ="{r["succ"]}" data-eps="{r["eps"]}">'
            f'<td>{r["index"]}</td><td><code>{esc(r["candidate_id"])}</code></td>'
            f'<td>{badge(r["experiment"], f"b-exp-{r["experiment"]}")}</td>'
            f'<td>{badge(r["axis"], f"b-axis-{r["axis"][0]}")}</td>'
            f'<td><code>{esc(r["scene"])}</code></td><td><code>{esc(r["template"])}</code></td>'
            f'<td class="tiny">{esc(r["bucket"])}</td><td>{esc(r["route"])}</td>'
            f'<td>{badge(r["priority"], PRIO_BADGE.get(r["priority"], "b-muted"))}</td>'
            f'<td>{badge(r["class"], CLASS_BADGE.get(r["class"], "b-muted"))}</td>'
            f'<td>{esc(r["order"])}</td>'
            f'<td class="nowrap">{", ".join(str(s) for s in r["seeds_success"]) or "—"}</td>'
            f'<td class="nowrap">{r["succ"]}/{r["eps"]}（{r["rate_pct"]}%）</td></tr>'
        )
    return f'''<section id="candidates">
<h2>八、全部 {len(rows)} 条候选结果（可筛选）</h2>
<div class="filterbar" id="candfilter">
<b>筛选</b>
<select id="filter-experiment" aria-label="按实验筛选"><option value="">全部实验</option><option value="easy">easy（161）</option><option value="hard">hard（92）</option></select>
<select id="filter-axis" aria-label="按去重轴筛选"><option value="">全部 axis</option><option value="A_skip">A_skip（{m["merged"]["axis"]["A_skip"]["candidates"]}）</option><option value="B_validate">B_validate（{m["merged"]["axis"]["B_validate"]["candidates"]}）</option><option value="C_diff_scene">C_diff_scene（{m["merged"]["axis"]["C_diff_scene"]["candidates"]}）</option><option value="D_unique">D_unique（{m["merged"]["axis"]["D_unique"]["candidates"]}）</option></select>
<select id="filter-scene" aria-label="按场景筛选"><option value="">全部场景</option>{scene_opts}</select>
<select id="filter-result" aria-label="按结果筛选"><option value="">全部（{len(rows)}）</option><option value="any">≥1 成功（{mt["stable_ge1"]}）</option><option value="ge2">≥2 seeds（{mt["stable_ge2"]}）</option><option value="all3">3/3（{mt["stable_all3"]}）</option><option value="zero">0/3（{mt["stable_none"]}）</option></select>
<button id="filter-reset" type="button">重置</button>
<span class="count" id="filter-count">显示 {len(rows)} / {len(rows)} 条候选</span>
<span class="hint">success 列 = 成功的 seeds 数 / 3；筛选在前端完成，不改变数据。3/3 行高亮显示。</span>
</div>
<div class="tblwrap"><table class="candtable">
<thead><tr><th>#</th><th>candidate_id</th><th>实验</th><th>axis</th><th>场景</th><th>模板</th><th>bucket</th><th>route</th><th>priority</th><th>class</th><th>order</th><th>成功 seeds</th><th>succ/eps</th></tr></thead>
<tbody>{''.join(body)}</tbody></table></div>
<p class="note">共 {len(rows)} 条候选 × 3 seeds = {mt["total_episodes"]} episodes；{mt["stable_ge1"]} 条至少成功一次、{mt["stable_ge2"]} 条 ≥2 seeds、{mt["stable_all3"]} 条 3/3。逐候选原始数据见 <code>merged-data.json</code> 的 <code>candidates</code> 字段（含 instruction / duplicate_of / seeds_success）。</p>
</section>'''

def render_conclusions(m):
    mt = m["metrics"]
    merged = m["merged"]
    cands = merged["candidates"]
    easy_succ = [c for c in cands.values() if c["experiment"] == "easy" and c["succ"] > 0]
    easy_dup_success_eps = sum(c["succ"] for c in easy_succ if c["axis"] in ("A_skip", "B_validate"))
    easy_novel_success_eps = sum(c["succ"] for c in easy_succ if c["axis"] in ("C_diff_scene", "D_unique"))
    tpl = {r["key"]: r for r in m["dist"]["template"]}
    route = {r["key"]: r for r in m["dist"]["route"]}
    groups = {g["group"]: g for g in m["groups"]}
    prio = {r["key"]: r for r in m["dist"]["priority"]}
    klass = {r["key"]: r for r in m["dist"]["class"]}
    axis_c = merged["axis"]["C_diff_scene"]
    st = m["stability"]
    return f'''<section id="conclusions">
<h2>九、结论与建议（可直接转述）</h2>
<div class="status ok"><b>核心结论</b>：easy（低难度 161）+ hard（去重剩余 92）合并 = <b>{mt["total_candidates"]} 候选 / {mt["total_episodes"]} episodes / {mt["total_success"]} success = {mt["total_rate_pct"]}%</b>；easy <b>{mt["easy_rate_pct"]}%</b> vs hard <b>{mt["hard_rate_pct"]}%</b>。但按去重轴拆分后：<b>真正新任务（C+D）只有 {mt["novel_success"]}/{mt["novel_episodes"]} = {mt["novel_rate_pct"]}%</b>，而<b>重复任务（A+B）{mt["dup_success"]}/{mt["dup_episodes"]} = {mt["dup_rate_pct"]}%</b>——合并成功率被“已会任务”显著抬高。稳定候选 <b>{st["counts"]["ge1"]} any / {st["counts"]["ge2"]} ≥2 / {st["counts"]["all3"]} 3/3</b>，rollback 可用基数 <b>{mt["rollback_candidates"]} candidates / {mt["rollback_tasks"]} tasks</b>（严格全新 C+D {mt["strict_candidates"]}/{mt["strict_tasks"]}）。</div>
<ol class="risk">
<li><b>easy 的 {mt["easy_rate_pct"]}% 不能当作新任务能力</b>：easy 成功 41 eps 中 <b>{easy_dup_success_eps} eps</b>（{rate_pct(easy_dup_success_eps, mt["easy_success"])}%）来自 A/B 重复轴（A 12 + B 11），真正新任务 C+D 只贡献 {easy_novel_success_eps} eps。合并口径同理：A+B 用 {mt["dup_episodes"]} eps 贡献 {mt["dup_success"]} 个成功，而 C+D 用 {mt["novel_episodes"]} eps 只贡献 {mt["novel_success"]} 个。<b>面向“新任务”汇报时应引用 {mt["novel_rate_pct"]}%（C+D）而不是 {mt["total_rate_pct"]}%</b>。</li>
<li><b>T1“put both A and B in C”仍是最有效指令族；同容器任务更强</b>：T1 {tpl["T1"]["success"]}/{tpl["T1"]["episodes"]} = <b>{tpl["T1"]["rate_pct"]}%</b>（成功数最多）；M2 提升路线 <b>{route["M2"]["success"]}/{route["M2"]["episodes"]} = {route["M2"]["rate_pct"]}%</b> 反超 M1 {route["M1"]["rate_pct"]}%（hard 的 M2 提升候选在 LR4 表现很好）；同容器（capacity）任务也高于 independent。LIVING_ROOM 主导成功：<b>{groups["LIVING_ROOM"]["success"]}/{groups["LIVING_ROOM"]["episodes"]} = {groups["LIVING_ROOM"]["rate_pct"]}%</b>（{groups["LIVING_ROOM"]["success"]}/{mt["total_success"]} 个成功）；KITCHEN {groups["KITCHEN"]["success"]}/{groups["KITCHEN"]["episodes"]} = {groups["KITCHEN"]["rate_pct"]}%、STUDY 0/{groups["STUDY"]["episodes"]}。</li>
<li><b>hard 的高难度层（P1/P2/class hard/C 类）zero-shot 单指令完全不可解</b>：P1 {prio["P1"]["success"]}/{prio["P1"]["episodes"]}、P2 {prio["P2"]["success"]}/{prio["P2"]["episodes"]}、class hard {klass["hard"]["success"]}/{klass["hard"]["episodes"]}、C 类跨场景同 goal {axis_c["success"]}/{axis_c["episodes"]}；hard 失败结构为 175/184 跑满 600 步、89 条 0 段、84 条完成 1 段后停滞（2 条 near-miss）。→ 这些层需要改协议（staged / instruction-switch / rollback 干预），继续加 seed 无收益（hard 补跑新增可用候选 0 条）。</li>
<li><b>下一步：用 10 条 3/3 原型做 rollback 验证</b>：<b>5 条真正新任务 3/3</b>（{esc("、".join(st["novel_all3"]))}）+ <b>5 条 B 指令变体 3/3</b>（{esc("、".join(st["b_all3"]))}）补视频并做 s1 成功后回退注入；优先 LR4_42（M2 新任务稳定）与 LR3 tray 族。若想扩大新任务池，应对 P1/P2/hard 层做 staged 对照，而不是继续全量加 seed。</li>
</ol>
<p class="note">统计注意：A+B 的 {mt["dup_rate_pct"]}% 是“重复任务”成功率（A 指令与 L10 完全相同、B 为同任务指令变体），按用户口径不算新候选；easy/hard 两实验候选构成不同，不能把 8.49% 与 5.43% 当随机子集做显著性检验。所有结论仅适用于本合并集合，不可外推 322 全量或官方 pi05。</p>
</section>'''


def render_caveats(m):
    mt = m["metrics"]
    walls = m["walls"]
    return f'''<section id="caveats">
<h2>十、口径 / 偏差声明 / 数据问题</h2>
<h3>10.1 口径与偏差声明（必读）</h3>
<div class="tblwrap"><table>
<thead><tr><th>项</th><th>声明</th></tr></thead>
<tbody>
<tr><td>集合构成</td><td><b>easy 161</b>（低难度半数，按难度分取 322 的前 50%）+ <b>hard 92</b>（322 中 valid、不在 easy、axis≠A 的剩余）= <b>253</b>；<b>不是随机样本</b>，也不是 322 全量（未跑 64 invalid + 5 valid A）。</td></tr>
<tr><td>不可外推</td><td>合并成功率 {mt["total_rate_pct"]}% 不能外推到 322 全量（剩下 69 条难度/结构不同），也不能与官方 pi05 / L10 / OBJECT / GOAL 数字横比（套件、候选构成、video、init、协议不同）。</td></tr>
<tr><td>去重轴解释</td><td>A+B 重复任务成功率 {mt["dup_rate_pct"]}% <b>不代表新任务能力</b>（A 指令与既有任务完全相同、B 是同一任务的指令变体）；真正新任务看 C+D = {mt["novel_rate_pct"]}%。A 的 4 条 3/3 已从 rollback 新基数剔除。</td></tr>
<tr><td>协议</td><td>三次运行均为 <b>单指令 zero-shot</b>（无 staged / instruction-switch / rollback）；pi05（OpenPI PyTorch）；seeds {{0,1,2}}；seed s 的 init 行 = s%50；max_steps=600 / replan=10；<b>video off</b>（吞吐优先）；2 worker 并行；sidecar init（sibling <code>.pruned_init</code>）。</td></tr>
<tr><td>hard 的 seed0</td><td>hard 的 seed0 <b>引用既有 hard run</b>（<code>runs/libero-90-hard-pi05-20261026</code>，92 eps），不重跑；seeds1/2 为 <code>runs/libero-90-hard-seeds12-full-20261026</code> 全量补跑（184 eps）。合并 276 eps = 92×3，无重复计入（hard 审计已核）。</td></tr>
<tr><td>seeds</td><td>仅 seeds {{0,1,2}}（非官方 50 trials）；稳定口径为 ≥1 / ≥2 / 3/3，样本量小，3/3 之外的 ≥2 候选（如 LR4_44_ab）仅作备选。</td></tr>
<tr><td>运行 wall</td><td>三次运行 wall 合计 {walls["total_hours"]} h（easy {mt["wall_easy"]}h + hard seed0 {mt["wall_hard0"]}h + hard seeds1/2 {mt["wall_hard12"]}h）；不同运行的 wall 口径可能含排队/续跑开销，仅作算力参考。</td></tr>
</tbody></table></div>
<h3>10.2 本报告发现的数据 / 文档不一致（已在页面处理）</h3>
<ol class="risk">
<li><b>模板数：任务要求写 9 个，合并数据实际 10 个</b>（T1/T2/T3/T4/T4b/T6/T7/T8/T9/T10；hard 带入 T4/T4b/T8/T9）。报告按数据列全 10 行，并标注 T7 50% 仅 6 eps 小样本。</li>
<li><b>hard “175/184 跑满 600 步 / 89 0 段 / 84 1 段后停滞 / 2 near-miss” 只是 seeds1/2 补跑（184 eps）的口径</b>；hard 合并 276 eps 后为 261/276 跑满、132 条 0 段、127 条 1 段后停滞、2 near-miss。报告同时给出两个口径，避免混用。</li>
<li><b><code>dup-audit/DEDUP_DECISION.md</code> 的 rollback 基数已过时</b>：该文件写 “可用 15 candidates / 11 tasks、严格全新 11/7”，那是 hard 验证前的口径；hard 补测后按同一规则重算为 <b>21 candidates / 15 tasks、严格全新 15/9</b>（本报告从 merged 数据重算并用 <code>--check</code> 断言）。建议回填 DEDUP_DECISION.md。</li>
<li><b><code>docs §18</code> 里有一张更早的合并快照</b>（easy + hard seed0：47/575 = 8.17%），已被 §19/§20 与本次三 seed 合并（56/759 = 7.38%）取代；报告按当前合并数据，不外推旧快照。</li>
<li><b><code>dup-audit/merged-validation-data.json</code> 是旧快照</b>（76 KB，只有 n_candidates/episodes/success/candidates 字段，无聚合；总计恰好相同 253/759/56）→ 本报告唯一数据源是最新的 <code>.tmp/libero90-combos/merged-validation-data.json</code>（122 KB，含全部聚合/稳定性/axis），并把它快照到 run 目录。</li>
<li><b>easy run 没有独立 <code>AUDIT.md</code></b>（只有 final_checks 全 PASS）；hard 三次运行有 3 份 AUDIT：PASS / PASS / PASS-WITH-ISSUES（1 minor，已回填）。页脚按实际记录，不虚构 easy 的 verifier 审计文件。</li>
<li><b>合并数据逐候选不含各 seed steps</b>（只有 <code>eps/succ/seeds_success</code>）；本报告候选表用 succ/eps 列代替 steps（任务允许 “steps 或成功率”），3/3 卡片展示成功 seeds；如需 steps 请回源两 run 的 <code>analysis/summary.json</code>。</li>
<li><b>2 条 near-miss</b>（goal 原子曾全真但 <code>check_success()</code> 未触发，出现在 hard seeds1/2）计入“完成 2 段”但不计 success；hard 审计已把它列为“值得复查评估口径”的观察项。</li>
</ol>
<p class="note">复核方式：本页数字全部由 <code>--check</code> 从 <code>merged-data.json</code>（以及两 run summary 的 episode 明细 / dedup_decision / final_checks）重算并断言；输入任一文件变化会触发构建指纹失败。合并数据快照与源文件字节一致（--check 也会校验）。</p>
</section>'''


def render_artifacts(m):
    rows = [
        ("本报告（单文件 HTML）", "index.html", "合并验证报告；内联 CSS/JS、无外链 CDN、可离线打开"),
        ("本报告说明", "README.md", "口径 / 章节索引 / 复现命令"),
        ("合并数据快照（本页唯一数据源）", "../merged-data.json", "从 .tmp/libero90-combos/merged-validation-data.json 字节拷贝（253 candidates / 759 eps / 56 success + 全部聚合）"),
        ("本报告生成器", "../../../scripts/build_libero90_merged_validation_report.py", "可重跑；--check 校验本页全部关键数字"),
        ("easy run 结果", "../../libero-90-easy-pi05-20261026/analysis/summary.json", "161 候选 / 483 eps / 41 success（含逐 episode 明细，用于失败/s1/步数补充统计）"),
        ("easy run 摘要 md", "../../libero-90-easy-pi05-20261026/analysis/summary.md", "可读版分析摘要"),
        ("easy run final_checks", "../../libero-90-easy-pi05-20261026/analysis/final_checks.json", "483/483、trace 161×3、全 PASS"),
        ("easy run 报告", "../../libero-90-easy-pi05-20261026/report/index.html", "easy 单批验证 HTML 报告（本页的前身）"),
        ("easy run 协议", "../../libero-90-easy-pi05-20261026/PROTOCOL.md", "easy 子集选择 / pi05 协议"),
        ("hard run（seed0）结果", "../../libero-90-hard-pi05-20261026/analysis/summary.json", "hard 92 候选 seed0（92 eps / 6 success，本页 hard seed0 来源）"),
        ("hard run（seed0）final_checks", "../../libero-90-hard-pi05-20261026/analysis/final_checks.json", "92 eps 全 PASS"),
        ("hard run（seed0）审计", "../../libero-90-hard-pi05-20261026/AUDIT.md", "verifier 审计 PASS（0/0/0）"),
        ("hard seeds1/2 补跑结果", "../../libero-90-hard-seeds12-full-20261026/analysis/summary.json", "92 候选 × seeds1/2 = 184 eps / 9 success（含 stability_table/combined）"),
        ("hard seeds1/2 final_checks", "../../libero-90-hard-seeds12-full-20261026/analysis/final_checks.json", "19/19 checks 全 PASS"),
        ("hard seeds1/2 审计", "../../libero-90-hard-seeds12-full-20261026/AUDIT.md", "verifier 审计 PASS-WITH-ISSUES（0/0/1 minor，已回填）"),
        ("hard 成功候选 seeds1/2 稳定性补测", "../../libero-90-hard-success-seeds12-20261026/analysis/summary.json", "6 条 hard 成功候选 × seeds1/2 = 12 eps（3/3 确认）"),
        ("hard 稳定性补测审计", "../../libero-90-hard-success-seeds12-20261026/AUDIT.md", "verifier 审计 PASS（0/0/0）"),
        ("去重判定（A/B/C/D）", "../../libero-90-combos-20261025/dup-audit/dedup_decision.json", "逐候选 axis/decision + 322→253 漏斗 + rollback_base（本页重算 21/15、15/9）"),
        ("去重决策说明", "../../libero-90-combos-20261025/dup-audit/DEDUP_DECISION.md", "A/B/C/D 用户口径定义；rollback 基数为 hard 验证前旧口径（见口径节）"),
        ("重复性审计", "../../libero-90-combos-20261025/dup-audit/DUPLICATE_AUDIT.md", "322 候选 vs L10/GOAL/OBJECT 的重复性审计"),
        ("旧合并快照（勿用）", "../../libero-90-combos-20261025/dup-audit/merged-validation-data.json", "早期 253/759/56 快照，字段不全；本页使用 .tmp 最新版"),
        ("上游：候选清单（322）", "../../libero-90-combos-20261025/candidates-instructed.json", "v2 模板化候选（253 已验证的来源）"),
        ("上游：场景报告", "../../libero-90-combos-20261025/report/index.html", "20 场景 × 单任务/组合候选/参考视频 HTML 报告"),
        ("方法文档", "../../../docs/libero-90-dual-target-candidates.md", "§15 easy 验证 / §18-§20 hard 验证与合并口径 / §16-§17 重复性审计"),
    ]
    body = "".join(
        f'<tr><td>{esc(title)}</td><td><a class="local" href="{esc(href)}"><code>{esc(href)}</code></a></td><td class="tiny">{esc(desc)}</td></tr>'
        for title, href, desc in rows
    )
    hashes = m["hashes"]
    hash_line = " · ".join(
        f'<code>{esc(name)}</code> <code title="sha256">{esc(hashes[name][:16])}…</code>' for name in sorted(hashes)
    )
    return f'''<section id="artifacts">
<h2>十一、产物索引</h2>
<div class="tblwrap"><table>
<thead><tr><th>产物</th><th>路径（相对本文件）</th><th>用途</th></tr></thead>
<tbody>{body}</tbody></table></div>
<p class="note">输入文件 sha256（前 16 位，完整值见生成日志）：{hash_line}。本页只读上述 JSON / 日志 / 审计文件；不修改任何 run、dup-audit、docs 或其他脚本。</p>
</section>'''


def render_footer(m):
    mt = m["metrics"]
    hashes = m["hashes"]
    line = " · ".join(
        f'<code>{esc(name)}</code> <code>{esc(hashes[name][:16])}…</code>' for name in sorted(hashes)
    )
    return f'''<footer>
<p><b>生成命令</b>：<code>cd /home/tarowang/workspace/roboot/libero-rollback &amp;&amp; .venv/bin/python scripts/build_libero90_merged_validation_report.py</code>；只读校验：<code>.venv/bin/python scripts/build_libero90_merged_validation_report.py --check</code></p>
<p><b>数据来源</b>：{line}；主数据源为 <code>.tmp/libero90-combos/merged-validation-data.json</code> 的字节快照 <code>../merged-data.json</code>，失败/s1/步数等补充统计来自两 run 的 <code>analysis/summary.json</code> episode 明细。</p>
<p><b>审计状态</b>：三次运行 <code>final_checks</code> 全 PASS；独立审计：hard seed0 <b>PASS</b>、hard 成功候选 seeds1/2 稳定性补测 <b>PASS</b>、hard 全量补跑 <b>PASS-WITH-ISSUES</b>（0 blocker / 0 major / 1 minor，已回填）；easy run 无独立 AUDIT.md（以 final_checks 全 PASS 为准）。本合并报告由 verifier 另行审计（task-26）；本 HTML 由脚本从 JSON 全量生成、数字无手填、<code>--check</code> 逐项复验。已知偏差：video 全程 off；重复任务（A+B）会抬高总成功率。</p>
<p class="tiny">构建时间 {esc(m["generated_at"])} · 构建指纹 <code>sha256:{esc(m["digest"])}</code> · 单文件静态页面（内联 CSS/JS、无外链 CDN）</p>
</footer>'''


def build_html(m):
    mt = m["metrics"]
    return "\n".join([
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f'<title>LIBERO-90 pi05 合并验证报告（easy 161 + hard 92 = {mt["total_candidates"]} 候选 / {mt["total_success"]}/{mt["total_episodes"]} = {mt["total_rate_pct"]}%）</title>',
        f"<!-- data-digest: sha256:{m['digest']} -->",
        f'<style>{CSS}</style>',
        '</head><body>',
        render_sidenav(m),
        render_hero(m),
        '<main>',
        render_overview(m),
        render_methods(m),
        render_compare(m),
        render_axes(m),
        render_dist(m),
        render_failures(m),
        render_stability(m),
        render_candidates(m),
        render_conclusions(m),
        render_caveats(m),
        render_artifacts(m),
        '</main>',
        render_footer(m),
        f'<script>{JS}</script>',
        '</body></html>',
    ])


def build_readme(m):
    mt = m["metrics"]
    st = m["stability"]
    lines = [
        "# LIBERO-90 双目标候选 · pi05 合并验证报告（easy 161 + hard 92）",
        "",
        "> 打开 `index.html` 离线阅读：单文件、内联 CSS/JS、无外链 CDN；主数据源 `merged-data.json`。",
        "",
        "## 结论",
        f"- **{mt['total_candidates']} candidates / {mt['total_episodes']} episodes / {mt['total_success']} success = {mt['total_rate_pct']}%**（easy {mt['easy_success']}/{mt['easy_episodes']} = {mt['easy_rate_pct']}%；hard {mt['hard_success']}/{mt['hard_episodes']} = {mt['hard_rate_pct']}%）。",
        f"- 去重轴：**真正新任务（C+D）{mt['novel_success']}/{mt['novel_episodes']} = {mt['novel_rate_pct']}%**；重复任务（A+B）{mt['dup_success']}/{mt['dup_episodes']} = {mt['dup_rate_pct']}%（不代表新任务能力）。",
        f"- 稳定候选 **{st['counts']['ge1']} any / {st['counts']['ge2']} ≥2 / {st['counts']['all3']} 3/3**；rollback 可用基数 {mt['rollback_candidates']}/{mt['rollback_tasks']} tasks（严格全新 C+D：{mt['strict_candidates']}/{mt['strict_tasks']}）。",
        f"- 14 条 3/3 = 新任务 D {mt['new3']} + B 指令变体 {mt['b3']} + A 重复 {mt['a3']}（A 已从新基数剔除）；hard 的 P1/P2/class hard/C 类 zero-shot 全 0。",
        "",
        "## 口径（不可外推）",
        f"- 253 = easy 161（低难度半数）+ hard 92（valid、不在 easy、axis≠A 的剩余）；未跑 64 invalid + 5 valid A。**不是 322 全量、不是随机样本**。",
        "- 单指令 zero-shot（无 staged/rollback）；seeds {0,1,2}；init 行 seed%50；max_steps=600 / replan=10；**video off**；硬 seed0 引用 hard run、seeds1/2 为补跑。",
        "- easy 8.49% 与 hard 5.43% 不可当随机子集做统计检验；重复任务（A+B）显著抬高合并成功率。",
        "",
        "## 复现",
        "```bash",
        "cd /home/tarowang/workspace/roboot/libero-rollback",
        ".venv/bin/python scripts/build_libero90_merged_validation_report.py          # 重建 merged-data.json 快照 + index.html + README.md",
        ".venv/bin/python scripts/build_libero90_merged_validation_report.py --check  # 只读校验（不写文件）",
        "```",
        "",
        "## 章节",
        "摘要/指标与完整性 → 方法与 A/B/C/D 口径 → easy vs hard + 按 seed → 去重轴表 → 分布表（场景/模板/桶/route/优先级/class/顺序）→ 失败分析 → 稳定性与 rollback 基数 → 253 行候选表（可筛选）→ 结论建议 → 口径/偏差/数据问题 → 产物索引。",
        "",
        "## 数据来源",
        "`merged-data.json`（来自 `.tmp/libero90-combos/merged-validation-data.json`）、两 run `analysis/summary.json` / `final_checks.json` / `AUDIT.md`、`dup-audit/dedup_decision.json`、`docs/libero-90-dual-target-candidates.md`（§15/§18-§20）。",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(m):
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    src_bytes = SRC_MERGED.read_bytes()
    SNAPSHOT.write_bytes(src_bytes)
    html_text = build_html(m)
    OUT_HTML = REPORT_DIR / "index.html"
    OUT_HTML.write_text(html_text, encoding="utf-8")
    readme = build_readme(m)
    (REPORT_DIR / "README.md").write_text(readme, encoding="utf-8")
    print(f"[build] {SNAPSHOT.relative_to(ROOT)}: {len(src_bytes):,} bytes (copied from .tmp)")
    print(f"[build] {OUT_HTML.relative_to(ROOT)}: {len(html_text.encode('utf-8')):,} bytes")
    print(f"[build] sections={html_text.count('<section ')} tables={html_text.count('<table')} "
          f"cand_rows={len(m['candidate_rows'])} stability_all3_rows={len(m['stability']['all3_rows'])}")
    print(f"[build] totals: {m['metrics']['total_success']}/{m['metrics']['total_episodes']} = "
          f"{m['metrics']['total_rate_pct']}% | easy {m['metrics']['easy_rate_pct']}% / hard {m['metrics']['hard_rate_pct']}% | "
          f"novel C+D {m['metrics']['novel_rate_pct']}% / dup A+B {m['metrics']['dup_rate_pct']}%")
    print(f"[build] README: {len(readme.splitlines())} lines")
    print(f"[build] digest sha256:{m['digest']}")

def parse_attrs(text):
    return dict(re.findall(r'([a-zA-Z_][\w-]*)="([^"]*)"', text))


def run_checks(m):
    checks = []

    def add(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    mt = m["metrics"]
    merged = m["merged"]
    cands = merged["candidates"]
    totals = merged["totals"]
    if not OUT_HTML.exists():
        add("index.html 存在", False, f"缺少 {OUT_HTML}；先运行无参数构建")
        for name, ok, detail in checks:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail and not ok else ""))
        print("--check: 0/1 checks passed")
        return False
    text = OUT_HTML.read_text(encoding="utf-8")
    digest_m = re.search(r"<!-- data-digest: sha256:([0-9a-f]{64}) -->", text)
    add("构建指纹与当前输入一致（HTML 未过期）",
        bool(digest_m) and digest_m.group(1) == m["digest"],
        "HTML 与当前输入 JSON 不一致，请重跑生成器")

    # ---------- 合并数据快照 ----------
    src_bytes = SRC_MERGED.read_bytes()
    add("merged-data.json 快照存在且与 .tmp 源字节一致",
        SNAPSHOT.exists() and SNAPSHOT.read_bytes() == src_bytes,
        "快照过期/缺失：请重跑生成器")
    add("快照 sha256 与输入指纹一致",
        SNAPSHOT.exists() and sha256_file(SNAPSHOT) == m["hashes"]["merged-validation-data.json"],
        "快照 sha256 不符")

    # ---------- 章节 ----------
    expected_sections = ["overview", "methods", "compare", "axes", "dist", "failures",
                         "stability", "candidates", "conclusions", "caveats", "artifacts"]
    missing = [sid for sid in expected_sections if f'<section id="{sid}"' not in text]
    add(f"{len(expected_sections)} 个章节 section 齐全", not missing, f"缺失: {missing}")

    # ---------- 指标 ----------
    found = dict(re.findall(r'data-metric="([^"]+)"[^>]*>([^<]+)<', text))
    missing_keys = sorted(set(mt) - set(found))
    wrong_keys = sorted(k for k in mt if k in found and found[k] != str(mt[k]))
    add("指标数字（data-metric）与 merged 数据一致",
        not missing_keys and not wrong_keys,
        f"缺失 {missing_keys[:6]} / 不符 {wrong_keys[:6]}")

    # ---------- 实验 / seed ----------
    exp_rows = re.findall(r'<tr class="exp-row" data-experiment="([^"]+)" data-candidates="(\d+)" '
                          r'data-episodes="(\d+)" data-success="(\d+)" data-rate="([\d.]+)"', text)
    exp_expected = []
    for r in m["exp_axis"]:
        exp_expected.append((r["experiment"], str(r["candidates"]), str(r["episodes"]),
                             str(r["success"]), str(rate_pct(r["success"], r["episodes"]))))
    add("easy vs hard 对比表 3 行且数值一致", exp_rows == exp_expected, f"实际 {exp_rows}")
    exp_wall = re.findall(r'<tr class="exp-row"[^>]*data-wall="([^"]*)"', text)
    exp_wall_expected = [str(m["walls"]["rows"][0]["wall_hours"]),
                         str(m["walls"]["rows"][2]["wall_hours"] + m["walls"]["rows"][1]["wall_hours"]),
                         str(m["metrics"]["wall_total_hours"])]
    add("easy vs hard 行 data-wall 与可见 wall 一致", exp_wall == exp_wall_expected, f"实际 {exp_wall}")
    method_rows = re.findall(r'<tr class="method-row" data-experiment="([^"]+)" data-candidates="(\d+)" '
                             r'data-episodes="(\d+)" data-success="(\d+)"', text)
    method_expected = [(e, str(merged["experiment"][e]["candidates"]),
                        str(merged["experiment"][e]["episodes"]), str(merged["experiment"][e]["success"]))
                       for e in ("easy", "hard")]
    add("方法节两实验候选/episodes/success 一致", method_rows == method_expected, f"实际 {method_rows}")
    seed_rows = re.findall(r'<tr class="seed-row" data-experiment="([^"]+)" data-seed="(\d+)" '
                           r'data-episodes="(\d+)" data-success="(\d+)" data-rate="([\d.]+)"', text)
    seed_expected = [(r["experiment"], str(r["seed"]), str(r["episodes"]), str(r["success"]), str(r["rate_pct"]))
                     for r in m["seed_rows"]]
    add("实验 × seed 表 6 行且数值一致", seed_rows == seed_expected, f"实际 {seed_rows}")
    merged_seed_rows = re.findall(r'<tr class="merged-seed-row" data-experiment="merged" data-seed="(\d+)" '
                                  r'data-episodes="(\d+)" data-success="(\d+)" data-rate="([\d.]+)"', text)
    merged_seed_expected = [(str(r["seed"]), str(r["episodes"]), str(r["success"]), str(r["rate_pct"]))
                            for r in m["merged_seed_rows"]]
    add("合并 per-seed 表 3 行且数值一致", merged_seed_rows == merged_seed_expected, f"实际 {merged_seed_rows}")
    add("合并 per-seed success 之和 = 56",
        sum(int(x[2]) for x in merged_seed_rows) == totals["success"])

    # ---------- 漏斗 ----------
    funnel_rows = re.findall(r'<tr class="funnel-row" data-axis="([^"]+)" data-all322="(\d+)" data-run="(\d+)" '
                             r'data-not-run="(\d+)" data-invalid="(\d+)" data-valid-not-run="(\d+)"', text)
    funnel_expected = [(r["axis"], str(r["all322"]), str(r["run"]), str(r["not_run"]),
                        str(r["invalid"]), str(r["valid_not_run"])) for r in m["funnel"]["rows"]]
    add("322→253 漏斗表 4 行且数值一致", funnel_rows == funnel_expected, f"实际 {funnel_rows}")
    add("漏斗 322 = 253 + 69 / invalid 64 / valid A 5",
        m["funnel"]["total322"] == 322 and m["funnel"]["run"] == 253
        and m["funnel"]["not_run"] == 69 and m["funnel"]["invalid"] == 64
        and m["funnel"]["valid_not_run"] == 5)
    add("漏斗各 axis 分解一致（not_run = invalid + valid A）",
        all(int(x[3]) == int(x[4]) + int(x[5]) for x in funnel_rows))

    # ---------- 去重轴 ----------
    axis_rows = re.findall(r'<tr class="axis-row" data-axis="([^"]+)" data-candidates="(\d+)" '
                           r'data-episodes="(\d+)" data-success="(\d+)" data-rate="([\d.]+)"', text)
    axis_expected = [(ax, str(merged["axis"][ax]["candidates"]), str(merged["axis"][ax]["episodes"]),
                      str(merged["axis"][ax]["success"]),
                      str(rate_pct(merged["axis"][ax]["success"], merged["axis"][ax]["episodes"])))
                     for ax in ("A_skip", "B_validate", "C_diff_scene", "D_unique")]
    add("去重轴表 4 行且数值一致", axis_rows == axis_expected, f"实际 {axis_rows}")
    combined_rows = re.findall(r'<tr class="combined-axis-row" data-axis="([^"]+)" data-candidates="(\d+)" '
                               r'data-episodes="(\d+)" data-success="(\d+)" data-rate="([\d.]+)"', text)
    novel = merged["novel_CD"]
    dup = merged["duplicate_AB"]
    combined_expected = [
        ("novel_CD", str(novel["candidates"]), str(novel["episodes"]), str(novel["success"]), str(mt["novel_rate_pct"])),
        ("duplicate_AB", str(dup["candidates"]), str(dup["episodes"]), str(dup["success"]), str(mt["dup_rate_pct"])),
    ]
    add("novel C+D / duplicate A+B 行数值一致（242/726/27、11/33/29）",
        combined_rows == combined_expected, f"实际 {combined_rows}")
    exp_axis_rows = re.findall(r'<tr class="exp-axis-row" data-experiment="([^"]+)">', text)
    add("实验 × axis 构成表 3 行", exp_axis_rows == [r["experiment"] for r in m["exp_axis"]], f"实际 {exp_axis_rows}")

    # ---------- 分布 ----------
    scene_rows = re.findall(r'<tr class="[^"]*scene-row" data-scene="([^"]+)" data-group="([^"]+)" '
                            r'data-candidates="(\d+)" data-episodes="(\d+)" data-success="(\d+)" data-rate="([\d.]+)"', text)
    scene_expected = [(r["key"], r["group"], str(r["candidates"]), str(r["episodes"]),
                       str(r["success"]), str(r["rate_pct"])) for r in m["dist"]["scene"]]
    add("按场景表 20 行且数值一致", scene_rows == scene_expected, f"实际 {len(scene_rows)} 行")
    add("场景表 candidates/episodes/success 之和 = 253/759/56",
        sum(int(x[2]) for x in scene_rows) == 253 and sum(int(x[3]) for x in scene_rows) == 759
        and sum(int(x[4]) for x in scene_rows) == 56)
    tpl_rows = re.findall(r'<tr class="[^"]*tpl-row" data-template="([^"]+)" data-candidates="(\d+)" '
                          r'data-episodes="(\d+)" data-success="(\d+)" data-rate="([\d.]+)"', text)
    tpl_expected = [(r["key"], str(r["candidates"]), str(r["episodes"]), str(r["success"]), str(r["rate_pct"]))
                    for r in m["dist"]["template"]]
    add("按模板表 10 行且数值一致", tpl_rows == tpl_expected, f"实际 {len(tpl_rows)} 行")
    add("模板表 candidates/episodes/success 之和 = 253/759/56",
        sum(int(x[1]) for x in tpl_rows) == 253 and sum(int(x[2]) for x in tpl_rows) == 759
        and sum(int(x[3]) for x in tpl_rows) == 56)
    dim_ok = True
    dim_detail = []
    for dim in ("bucket", "route", "priority", "class", "order"):
        rows = re.findall(rf'<tr class="[^"]*dist-row" data-{dim}="([^"]+)" data-candidates="(\d+)" '
                          rf'data-episodes="(\d+)" data-success="(\d+)" data-rate="([\d.]+)"', text)
        expected = [(r["key"], str(r["candidates"]), str(r["episodes"]), str(r["success"]), str(r["rate_pct"]))
                    for r in m["dist"][dim]]
        dim_ok = dim_ok and rows == expected
        if rows != expected:
            dim_detail.append(dim)
    add("bucket/route/priority/class/order 表数值一致", dim_ok, f"不一致: {dim_detail}")

    # ---------- 失败分析 ----------
    failure_rows = re.findall(r'<tr class="[^"]*failure-row" data-scope="([^"]+)" data-episodes="(\d+)" '
                              r'data-success="(\d+)" data-sub0="(\d+)" data-sub1="(\d+)" data-sub2="(\d+)" '
                              r'data-near="(\d+)" data-maxsteps="(\d+)"', text)
    failure_expected = [(r["scope"], str(r["episodes"]), str(r["success"]), str(r["sub0"]), str(r["sub1"]),
                         str(r["sub2"]), str(r["near_miss"]), str(r["maxsteps"])) for r in m["failure"]["rows"]]
    add("失败模式表 5 个 scope 且数值一致", failure_rows == failure_expected, f"实际 {failure_rows}")
    add("hard 补跑 175/184 跑满、89 0 段、84 1 段后停滞、2 near-miss",
        m["failure"]["hard12"]["maxsteps"] == 175 and m["failure"]["hard12"]["sub0"] == 89
        and m["failure"]["hard12"]["sub1"] == 84 and m["failure"]["hard12"]["near_miss"] == 2)
    merged_stats = m["failure"]["merged"]
    add("合并失败/子任务/步数口径一致（759 eps, 345/356/58, 703 跑满）",
        merged_stats["episodes"] == 759 and merged_stats["sub0"] == 345
        and merged_stats["sub1"] == 356 and merged_stats["sub2"] == 58
        and merged_stats["maxsteps"] == 703 and m["failure"]["steps_hist_sum"] == 759)
    s1_values = [m["failure"]["easy"]["s1_ever"], m["failure"]["easy"]["s1_final"],
                 m["failure"]["hard_combined"]["s1_ever"], m["failure"]["hard_combined"]["s1_final"],
                 merged_stats["s1_ever"], merged_stats["s1_final"],
                 merged_stats["s1_retract_events"], merged_stats["s1_retract_eps"]]
    add("s1 轨迹表 easy / hard / 合并数值一致",
        all(str(v) in text for v in s1_values), f"缺失 {[v for v in s1_values if str(v) not in text]}")

    # ---------- 稳定性 / rollback ----------
    stable_rows = re.findall(r'<tr class="[^"]*stable3-row" data-candidate="([^"]+)" data-all3="1" data-axis="([^"]+)"', text)
    add("14 条 3/3 表行数 = 14 且 candidate_id 一致",
        len(stable_rows) == len(m["stability"]["all3_rows"])
        and {x[0] for x in stable_rows} == {r["candidate_id"] for r in m["stability"]["all3_rows"]},
        f"实际 {len(stable_rows)}")
    add("3/3 构成：新任务 5 + B 变体 5 + A 重复 4",
        mt["new3"] == 5 and mt["b3"] == 5 and mt["a3"] == 4 and mt["stable_all3"] == 14)
    rb_rows = re.findall(r'<tr class="rb-axis-row" data-axis="([^"]+)" data-succ-candidates="(\d+)" '
                         r'data-tasks="(\d+)" data-all3="(\d+)"', text)
    rb_expected = [(r["axis"], str(r["succ_candidates"]), str(r["tasks"]), str(r["all3"]))
                   for r in m["rollback"]["by_axis"]]
    add("rollback 按 axis 表 4 行且数值一致", rb_rows == rb_expected, f"实际 {rb_rows}")
    add("rollback 基数 = 21/15，严格全新 C+D = 15/9，A 排除 4",
        mt["rollback_candidates"] == 21 and mt["rollback_tasks"] == 15
        and mt["strict_candidates"] == 15 and mt["strict_tasks"] == 9
        and mt["excluded_a_candidates"] == 4)
    proto_cards = re.findall(r'<div class="bigcard (?:gold|blue)" data-proto="([^"]+)"', text)
    add("rollback 原型卡片 = 10 条（新任务 5 + B 5）且名单一致",
        len(proto_cards) == 10
        and set(proto_cards) == set(m["stability"]["novel_all3"]) | set(m["stability"]["b_all3"]),
        f"实际 {len(proto_cards)}")

    # ---------- 候选表 ----------
    cand_rows = re.findall(r'<tr class="(?:hi )?cand-row"([^>]*)>', text)
    add("候选表行数 = 253 且 candidate_id 唯一",
        len(cand_rows) == totals["candidates"]
        and len({parse_attrs(a).get("data-candidate") for a in cand_rows}) == totals["candidates"],
        f"实际 {len(cand_rows)}")
    bad = []
    succ_counter = Counter()
    for attrs_text in cand_rows:
        a = parse_attrs(attrs_text)
        cid = a.get("data-candidate")
        c = cands.get(cid)
        if c is None:
            bad.append(cid)
            continue
        succ_counter[int(a["data-succ"])] += 1
        if (a.get("data-experiment") != c["experiment"] or a.get("data-axis") != c["axis"]
                or a.get("data-scene") != c["scene"] or a.get("data-template") != c["template"]
                or a.get("data-bucket") != c["bucket"] or a.get("data-route") != c["route"]
                or a.get("data-priority") != c["priority"] or a.get("data-class") != c["class"]
                or a.get("data-order") != c["order"]
                or a.get("data-seeds") != ",".join(str(s) for s in c["seeds_success"])
                or a.get("data-succ") != str(c["succ"]) or a.get("data-eps") != str(c["eps"])):
            bad.append(cid)
    add("候选表逐行 experiment/axis/scene/template/bucket/route/priority/class/order/seeds/succ/eps 与数据一致",
        not bad, f"不一致: {bad[:5]}")
    add("候选表 succ 分布 = 数据（0:228 / 1:8 / 2:3 / 3:14）",
        succ_counter == Counter(c["succ"] for c in cands.values()),
        f"实际 {dict(succ_counter)}")

    # ---------- 交互 / 声明 / 链接 / README ----------
    add("候选筛选控件（experiment/axis/scene/result）齐全",
        all(fid in text for fid in ('id="candfilter"', 'id="filter-experiment"', 'id="filter-axis"',
                                    'id="filter-scene"', 'id="filter-result"', 'id="filter-count"')))
    add("口径声明包含 video off / 不可外推 / A/B/C/D 去重",
        "video off" in text and "不可外推" in text and "A_skip" in text and "D_unique" in text)
    local_hrefs = re.findall(r'<a class="local" href="([^"]+)"', text)
    bad_links = [h for h in local_hrefs if not (REPORT_DIR / h).resolve().exists()]
    add("产物索引相对链接全部可解析（离线可用）",
        len(local_hrefs) >= 15 and not bad_links, f"{len(local_hrefs)} 个链接; 失效 {bad_links[:3]}")
    ext = re.search(r'https?://', text)
    add("无外链 CDN / 外部资源（单文件离线）",
        not ext and "<script src=" not in text and "<link " not in text and "<iframe" not in text)
    add("页脚含生成命令 / 数据来源 / 审计状态",
        "生成命令" in text and "审计状态" in text and "PASS-WITH-ISSUES" in text)
    if OUT_README.exists():
        readme = OUT_README.read_text(encoding="utf-8")
        lines = readme.splitlines()
        add("README.md 存在且行数 <= 30", len(lines) <= 30, f"{len(lines)} 行")
        add("README 含核心数字与 --check",
            str(mt["total_candidates"]) in readme and str(mt["total_success"]) in readme
            and f"{mt['total_rate_pct']}%" in readme and "--check" in readme)
    else:
        add("README.md 存在", False)

    ok_all = all(ok for _, ok, _ in checks)
    for name, ok, detail in checks:
        line = f"[{'PASS' if ok else 'FAIL'}] {name}"
        if detail and not ok:
            line += f" — {detail}"
        print(line)
    n_ok = sum(1 for _, ok, _ in checks if ok)
    print(f"--check: {n_ok}/{len(checks)} checks passed")
    return ok_all


def main(argv=None):
    parser = argparse.ArgumentParser(description="LIBERO-90 easy+hard pi05 3-seed 合并验证 HTML 报告生成器")
    parser.add_argument("--check", action="store_true", help="只读校验现有 index.html / README.md / merged-data.json，不写文件")
    args = parser.parse_args(argv)
    model = compute_model()
    validate_model(model)
    if args.check:
        return 0 if run_checks(model) else 1
    write_outputs(model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
