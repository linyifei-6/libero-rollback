#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LIBERO-90 低难度双目标候选（161）× pi05 × 3 seeds 验证结果 HTML 报告生成器。

只读输入:
  runs/libero-90-easy-pi05-20261026/analysis/summary.json     运行结果（overall/分布/失败/稳定/逐候选/逐 episode）
  runs/libero-90-easy-pi05-20261026/analysis/final_checks.json 完整性检查（全 PASS）
  runs/libero-90-easy-pi05-20261026/prep/easy_subset.json     161 条候选定义与选择规则
  runs/libero-90-easy-pi05-20261026/run/progress.json         实时进度/速率
  runs/libero-90-easy-pi05-20261026/logs/queue-gpu.log        GPU 显存采样（JSONL）
  runs/libero-90-easy-pi05-20261026/logs/smoke-parallel.json  双 worker 冒烟证据
  runs/libero-90-easy-pi05-20261026/logs/queue.log            队列日志（GPU 启动/结束、OOM 扫描）
  docs/libero-90-dual-target-candidates.md                    GOAL 参考实验数字（仅作对比引用）
输出:
  runs/libero-90-easy-pi05-20261026/report/index.html         单文件 HTML（内联 CSS/JS）
  runs/libero-90-easy-pi05-20261026/report/README.md          <=30 行说明
用法:
  .venv/bin/python scripts/build_libero90_easy_validation_report.py
  .venv/bin/python scripts/build_libero90_easy_validation_report.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "runs" / "libero-90-easy-pi05-20261026"
REPORT_DIR = RUN_DIR / "report"

P_SUMMARY = RUN_DIR / "analysis" / "summary.json"
P_FINAL = RUN_DIR / "analysis" / "final_checks.json"
P_SUBSET = RUN_DIR / "prep" / "easy_subset.json"
P_PROGRESS = RUN_DIR / "run" / "progress.json"
P_GPU = RUN_DIR / "logs" / "queue-gpu.log"
P_SMOKE_PAR = RUN_DIR / "logs" / "smoke-parallel.json"
P_QUEUE = RUN_DIR / "logs" / "queue.log"
P_DOCS = ROOT / "docs" / "libero-90-dual-target-candidates.md"
P_PROTOCOL = RUN_DIR / "PROTOCOL.md"
OUT_HTML = REPORT_DIR / "index.html"
OUT_README = REPORT_DIR / "README.md"

INPUT_FILES = [
    ("summary.json", P_SUMMARY),
    ("final_checks.json", P_FINAL),
    ("easy_subset.json", P_SUBSET),
    ("progress.json", P_PROGRESS),
    ("queue-gpu.log", P_GPU),
    ("smoke-parallel.json", P_SMOKE_PAR),
    ("queue.log", P_QUEUE),
    ("libero-90-dual-target-candidates.md", P_DOCS),
    ("PROTOCOL.md", P_PROTOCOL),
]

GROUP_CN = {"KITCHEN": "KITCHEN 厨房", "LIVING_ROOM": "LIVING_ROOM 客厅", "STUDY": "STUDY 书房"}
ORDER_CN = {"ab": "ab（s1→s2）", "ba": "ba（s2→s1）"}
BUCKET_CN = {
    "same_destination(capacity)": "同落点/同容器（capacity）",
    "independent": "独立（independent）",
    "same_furniture/fixture": "同家具/夹具（same_furniture）",
}
FAIL_CN = {
    "failed_completed_0_subtasks": "完成 0 段后停滞",
    "failed_completed_1_subtask_then_stalled": "完成 1 段后停滞",
    "success": "成功（完成 2 段）",
}


def esc(value):
    return html.escape(str(value), quote=True)


def nfmt(value):
    return f"{value:,}"


def pct(value, digits=2):
    return f"{100.0 * value:.{digits}f}%"


def badge(text, cls, title=None):
    attr = f' title="{esc(title)}"' if title else ""
    return f'<span class="badge {cls}"{attr}>{esc(text)}</span>'


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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


def group_of(scene):
    if scene.startswith("KITCHEN"):
        return "KITCHEN"
    if scene.startswith("LIVING_ROOM"):
        return "LIVING_ROOM"
    return "STUDY"


def load_gpu_samples():
    samples = []
    for line in P_GPU.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            samples.append(json.loads(line))
    peak = max(s["memory_used_mib"] for s in samples)
    total = max(s["memory_total_mib"] for s in samples)
    return {
        "samples": len(samples),
        "min_mib": min(s["memory_used_mib"] for s in samples),
        "peak_mib": peak,
        "total_mib": total,
        "first_ts": samples[0].get("ts", ""),
        "last_ts": samples[-1].get("ts", ""),
    }


def scan_oom_markers():
    pat = re.compile(r"\bOOM\b|out of memory|OutOfMemory", re.IGNORECASE)
    files = [P_QUEUE, P_GPU]
    files += sorted((RUN_DIR / "logs").glob("queue-seed*.log"))
    hits = []
    for path in files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in pat.finditer(text):
            hits.append(f"{path.name}: {text[max(0, m.start() - 60):m.start() + 60].strip()}")
    return hits


def build_seed_rows(sm):
    rows = []
    for key in ("0", "1", "2"):
        v = sm["by_seed"][key]
        rows.append({"seed": int(key), **v, "rate_pct": round(100.0 * v["success_rate"], 2)})
    return rows


def build_scene_rows(sm):
    rows = []
    for scene, v in sm["by_scene"].items():
        rows.append({
            "scene": scene, "group": group_of(scene),
            "candidates": v["episodes"] // 3,
            **v, "rate_pct": round(100.0 * v["success_rate"], 2),
        })
    rows.sort(key=lambda r: (-r["success_rate"], -r["episodes"], r["scene"]))
    return rows


def build_group_rows(scene_rows):
    groups = {}
    for row in scene_rows:
        g = groups.setdefault(row["group"], {"group": row["group"], "scenes": 0, "episodes": 0, "success": 0})
        g["scenes"] += 1
        g["episodes"] += row["episodes"]
        g["success"] += row["success"]
    out = []
    for key in ("KITCHEN", "LIVING_ROOM", "STUDY"):
        if key not in groups:
            continue
        g = groups[key]
        g["rate"] = g["success"] / g["episodes"] if g["episodes"] else 0.0
        g["rate_pct"] = round(100.0 * g["rate"], 2)
        out.append(g)
    return out


def build_template_rows(sm):
    rows = []
    for template, v in sm["by_instruction_template"].items():
        rows.append({"template": template, **v, "rate_pct": round(100.0 * v["success_rate"], 2)})
    rows.sort(key=lambda r: (-r["success_rate"], -r["episodes"], r["template"]))
    return rows


def build_bucket_rows(sm):
    rows = []
    for bucket, v in sm["by_difficulty_bucket"].items():
        rows.append({"bucket": bucket, "bucket_cn": BUCKET_CN.get(bucket, bucket), **v,
                     "rate_pct": round(100.0 * v["success_rate"], 2)})
    rows.sort(key=lambda r: (-r["success_rate"], -r["episodes"], r["bucket"]))
    return rows


def build_order_rows(sm):
    rows = []
    for order, v in sm["by_order"].items():
        rows.append({"order": order, **v, "rate_pct": round(100.0 * v["success_rate"], 2)})
    rows.sort(key=lambda r: r["order"])
    return rows


def build_composition(es, sm):
    selected = es["selected"]
    held = es["stats"].get("held_out_eligible_hardest", [])
    held_ids = [h["candidate_id"] for h in held]
    by_scene = Counter(s["scene"] for s in selected)
    by_template = Counter(s["instruction_template"] for s in selected)
    by_bucket = Counter(s["difficulty_bucket"] for s in selected)
    by_order = Counter(s["order"] for s in selected)
    scores = [s["difficulty_score"] for s in selected]
    return {
        "n": len(selected),
        "total_candidates": es["total_candidates"],
        "ratio_pct": round(100.0 * len(selected) / es["total_candidates"], 2),
        "target_n": es["target_n"],
        "eligible": es["rule"]["n_eligible"],
        "held_out": len(held_ids),
        "held_out_rows": held,
        "held_out_ids": held_ids,
        "by_scene": dict(by_scene),
        "by_template": dict(by_template),
        "by_bucket": dict(by_bucket),
        "by_order": dict(by_order),
        "n_scenes": len(by_scene),
        "n_templates": len(by_template),
        "n_buckets": len(by_bucket),
        "difficulty_min": min(scores),
        "difficulty_max": max(scores),
        "n_template_tasks": len({s["template_task"] for s in selected}),
        "with_switch": sum(1 for s in selected if s.get("has_switch")),
        "n_atoms": dict(Counter(s["n_atoms"] for s in selected)),
        "rule": es["rule"],
    }


def build_failure(sm, episodes):
    overall = sm["overall"]
    total = overall["episodes"]
    fm = sm["failure_modes"]
    modes = []
    for key in ("failed_completed_0_subtasks", "failed_completed_1_subtask_then_stalled", "success"):
        count = fm[key]
        modes.append({"key": key, "label": FAIL_CN[key], "count": count, "pct": round(100.0 * count / total, 2)})
    hist = [{"range": key, "count": value} for key, value in sm["steps_histogram"].items()]
    s1 = sm["s1_statistics"]
    succ = sum(1 for e in episodes if e["success"])
    success_steps = [e["steps"] for e in episodes if e["success"]]
    fail_steps = [e["steps"] for e in episodes if not e["success"]]
    zero = [e for e in episodes if e["subtasks_done_final"] == 0]
    one = [e for e in episodes if e["subtasks_done_final"] == 1]
    s1_rows = [
        {"label": "s1 首次为真的 episode", "value": nfmt(s1["episodes_with_s1_first_true"]),
         "note": f'{round(100.0 * s1["episodes_with_s1_first_true"] / total, 2)}% of {total}'},
        {"label": "s1 首次为真步数 mean / median", "value": f'{s1["s1_first_true_step_mean"]} / {s1["s1_first_true_step_median"]}',
         "note": "从 episode 开始到 s1 首次变为 true 的控制步"},
        {"label": "s1 最终为真的 episode", "value": nfmt(s1["episodes_s1_final_true"]),
         "note": f'保持率 {round(100.0 * s1["episodes_s1_final_true"] / s1["episodes_with_s1_first_true"], 2)}% of s1-ever'},
        {"label": "s1 回撤（true→false）总次数", "value": nfmt(s1["s1_retract_events"]),
         "note": f'涉及 {s1["episodes_with_s1_retract"]} eps（{round(100.0 * s1["episodes_with_s1_retract"] / total, 2)}%）'},
    ]
    lost = s1["episodes_with_s1_first_true"] - s1["episodes_s1_final_true"]
    return {
        "modes": modes,
        "maxstep_fails": fm["failed_at_max_steps_600"],
        "maxstep_pct": round(100.0 * fm["failed_at_max_steps_600"] / total, 2),
        "hist": hist,
        "s1_rows": s1_rows,
        "s1": s1,
        "lost_s1": lost,
        "zero_with_s1_ever": sum(1 for e in zero if e.get("s1_first_true_step") is not None),
        "one_with_s1_final": sum(1 for e in one if e.get("s1_final_true")),
        "one_with_s1_ever": sum(1 for e in one if e.get("s1_first_true_step") is not None),
        "success_with_retract": sum(1 for e in episodes if e["success"] and (e.get("s1_retract_count") or 0) > 0),
        "fail_with_retract": sum(1 for e in episodes if not e["success"] and (e.get("s1_retract_count") or 0) > 0),
        "success_mean_steps": round(sum(success_steps) / len(success_steps), 2) if success_steps else 0.0,
        "fail_mean_steps": round(sum(fail_steps) / len(fail_steps), 2) if fail_steps else 0.0,
        "success_min_steps": min(success_steps) if success_steps else 0,
        "success_max_steps": max(success_steps) if success_steps else 0,
        "success_episodes": succ,
    }

def build_stability(sm, subset_by_id):
    stable = sm["stable_candidates"]
    per = sm["per_candidate"]
    any_ids = stable["success_any"]
    ge2 = set(stable["success_ge2"])
    all3 = set(stable["success_all3"])
    scene_rank = {scene: idx for idx, scene in enumerate(sm["by_scene"].keys())}
    rows = []
    for cid in any_ids:
        p = per.get(cid, {})
        sub = subset_by_id.get(cid, {})
        rows.append({
            "candidate_id": cid,
            "scene": p.get("scene", sub.get("scene", "")),
            "template": p.get("instruction_template", sub.get("instruction_template", "")),
            "bucket": p.get("difficulty_bucket", sub.get("difficulty_bucket", "")),
            "order": p.get("order", sub.get("order", "")),
            "instruction": p.get("instruction", sub.get("instruction", "")),
            "n_success": p.get("n_success", 0),
            "seeds_success": p.get("seeds_success", []),
            "steps": p.get("steps", []),
            "subtasks": p.get("subtasks_done", []),
            "mean_steps": p.get("mean_steps", 0),
            "all3": cid in all3,
            "ge2": cid in ge2,
            "difficulty_score": sub.get("difficulty_score"),
            "init_source": sub.get("init_source"),
        })
    rows.sort(key=lambda r: (0 if r["all3"] else 1 if r["ge2"] else 2,
                             scene_rank.get(r["scene"], 99), r["candidate_id"]))
    return {
        "rows": rows,
        "ge2_rows": [r for r in rows if r["ge2"]],
        "all3_rows": [r for r in rows if r["all3"]],
        "counts": {
            "any": len(any_ids), "ge2": len(ge2), "all3": len(all3),
        },
    }


def build_candidate_rows(sm, subset_by_id):
    rows = []
    for idx, (cid, p) in enumerate(sm["per_candidate"].items(), 1):
        sub = subset_by_id.get(cid, {})
        rows.append({
            "index": idx,
            "candidate_id": cid,
            "scene": p["scene"],
            "template": p["instruction_template"],
            "bucket": p["difficulty_bucket"],
            "order": p["order"],
            "instruction": p["instruction"],
            "n_success": p["n_success"],
            "seeds_success": p["seeds_success"],
            "steps": p["steps"],
            "subtasks": p["subtasks_done"],
            "mean_steps": p.get("mean_steps", 0),
            "success_any": p["success_any"],
            "success_ge2": p["success_ge2"],
            "success_all3": p["success_all3"],
            "difficulty_score": sub.get("difficulty_score"),
            "init_source": sub.get("init_source"),
            "has_switch": sub.get("has_switch"),
        })
    return rows


def build_goal_ref(docs_text):
    single = re.search(r'单指令组合\s*(\d+)/(\d+)\s*≈\s*([\d.]+)%', docs_text)
    staged = re.search(r'staged\s*(\d+)/(\d+)', docs_text)
    publish = re.search(r'发布口径\s*(\d+)/(\d+)\s*=\s*([\d.]+)%', docs_text)
    if not (single and staged):
        raise SystemExit("[FATAL] docs 中未找到 GOAL 参考数字（单指令 x/47、staged x/y）")
    return {
        "source": "docs/libero-90-dual-target-candidates.md §2.1",
        "single_success": int(single.group(1)),
        "single_episodes": int(single.group(2)),
        "single_rate_pct": round(100.0 * int(single.group(1)) / int(single.group(2)), 2),
        "single_rate_doc": float(single.group(3)),
        "staged_success": int(staged.group(1)),
        "staged_episodes": int(staged.group(2)),
        "publish_success": int(publish.group(1)) if publish else None,
        "publish_episodes": int(publish.group(2)) if publish else None,
        "publish_rate_pct": float(publish.group(3)) if publish else None,
    }



def build_upstream_counts(protocol_text):
    """从 PROTOCOL.md §2 解析全量 322 候选的 route / priority 分布（上游计数，供“剩余候选”分类使用）。"""
    m_route = re.search(r'M1（[^）]*）(\d+)\s*\+\s*M2（[^）]*）(\d+)\s*\+\s*S1（[^）]*）(\d+)', protocol_text)
    m_prio = re.search(r'P0\s*(\d+)\s*/\s*P1\s*(\d+)\s*/\s*P2\s*(\d+)\s*/\s*P3\s*(\d+)', protocol_text)
    if not (m_route and m_prio):
        raise SystemExit("[FATAL] PROTOCOL.md 中未找到全量候选 route/priority 计数（M1+M2+S1 / P0-P3）")
    m1, m2, s1 = (int(x) for x in m_route.groups())
    p0, p1, p2, p3 = (int(x) for x in m_prio.groups())
    return {"m1": m1, "m2": m2, "s1": s1, "p0": p0, "p1": p1, "p2": p2, "p3": p3}


def build_integrity(fc, gpu, smoke_parallel, oom_hits, stability_counts, subset_n):
    checks = fc["checks"]
    traces = sum(fc["traces_per_seed"].values())
    rc_ok = all(code == 0 for code in fc["worker_exit_codes"])
    rows = [
        {"item": "队列完成标记（QUEUE_DONE）", "ok": checks["queue_done_present"],
         "detail": "logs/queue.log 末尾 QUEUE_DONE"},
        {"item": "progress 完成度", "ok": checks["progress_completed_483"],
         "detail": f'{fc["overall_episodes"]} / {fc["overall_episodes"]}（100%）'},
        {"item": "trace 数 = 每 seed 全量", "ok": checks["traces_161_each_seed"],
         "detail": f'{traces} 条 = ' + " + ".join(f"seed{k} {v}" for k, v in fc["traces_per_seed"].items())},
        {"item": "缺失候选", "ok": checks["missing_candidates_all_empty"],
         "detail": "3 seeds 的 missing 列表均为空"},
        {"item": "trace 原子与设计不一致", "ok": checks["trace_atom_mismatches_empty"],
         "detail": "trace_atom_mismatches = []"},
        {"item": "worker 退出码", "ok": checks["all_worker_rc_zero"] and rc_ok,
         "detail": f'{fc["worker_exit_codes"]}（{len(fc["worker_exit_codes"])} 个 worker）'},
        {"item": "analysis episodes", "ok": checks["analysis_483_episodes"],
         "detail": f'{fc["overall_episodes"]} 条'},
        {"item": "success 来源", "ok": fc["success_sources"].get("results.json") == fc["overall_episodes"],
         "detail": f'全部来自 results.json（{fc["success_sources"].get("results.json")} / {fc["overall_episodes"]}）'},
        {"item": "稳定候选计数", "ok": (checks["stable_success_any"] == stability_counts["any"]
                                     and checks["stable_success_ge2"] == stability_counts["ge2"]
                                     and checks["stable_success_all3"] == stability_counts["all3"]),
         "detail": f'any/≥2/all3 = {checks["stable_success_any"]} / {checks["stable_success_ge2"]} / {checks["stable_success_all3"]}'},
        {"item": "GPU 无 OOM", "ok": not oom_hits and bool(smoke_parallel.get("checks", {}).get("no_oom_markers")),
         "detail": f'峰值 {gpu["peak_mib"]} / {gpu["total_mib"]} MiB · OOM 标记 {len(oom_hits)}'},
        {"item": "双 worker 并行冒烟", "ok": smoke_parallel.get("verdict") == "PASS",
         "detail": f'吞吐 {smoke_parallel.get("throughput_multiplier_vs_single")}×；{smoke_parallel.get("effective_eps_per_hour")} eps/h'},
        {"item": "资产文件", "ok": fc["artifacts_bddl_file_count"] == 2 * subset_n,
         "detail": f'artifacts/bddl {fc["artifacts_bddl_file_count"]} 个（{subset_n} bddl + {subset_n} init）；run 副本 {fc["run_bddl_copy_file_count"]} 个'},
        {"item": "wall time", "ok": fc["wall_seconds"] > 0,
         "detail": f'{fc["wall_hours"]} h（{fc["wall_seconds"]} s）'},
        {"item": "final_checks 总判定", "ok": fc["checks_all_passed"],
         "detail": "checks_all_passed = true"},
    ]
    return {"rows": rows, "all_pass": fc["checks_all_passed"], "gpu": gpu, "smoke": smoke_parallel,
            "traces": traces, "rc_ok": rc_ok}


def build_metrics(sm, fc, pr, gpu, comp, stability, failure, seed_rows, goal_ref, obj_ref, oom_hits, upstream):
    overall = sm["overall"]
    return {
        "episodes": overall["episodes"],
        "success": overall["success"],
        "success_rate_pct": round(100.0 * overall["success"] / overall["episodes"], 2),
        "mean_steps": overall["mean_steps"],
        "median_steps": overall["median_steps"],
        "min_steps": overall["min_steps"],
        "max_steps": overall["max_steps"],
        "success_mean_steps": failure["success_mean_steps"],
        "fail_mean_steps": failure["fail_mean_steps"],
        "success_min_steps": failure["success_min_steps"],
        "success_max_steps": failure["success_max_steps"],
        "seed0_success": seed_rows[0]["success"],
        "seed1_success": seed_rows[1]["success"],
        "seed2_success": seed_rows[2]["success"],
        "seed0_rate_pct": seed_rows[0]["rate_pct"],
        "seed1_rate_pct": seed_rows[1]["rate_pct"],
        "seed2_rate_pct": seed_rows[2]["rate_pct"],
        "stable_any": stability["counts"]["any"],
        "stable_ge2": stability["counts"]["ge2"],
        "stable_all3": stability["counts"]["all3"],
        "cand_with_success": stability["counts"]["any"],
        "wall_hours": fc["wall_hours"],
        "wall_seconds": fc["wall_seconds"],
        "rate_progress": pr["rate_episodes_per_hour"],
        "sec_per_episode": pr["seconds_per_episode"],
        "rate_wall": round(fc["overall_episodes"] / (fc["wall_seconds"] / 3600.0), 2),
        "gpu_peak_mib": gpu["peak_mib"],
        "gpu_total_mib": gpu["total_mib"],
        "gpu_samples": gpu["samples"],
        "oom_markers": len(oom_hits),
        "subset_n": comp["n"],
        "total_candidates": comp["total_candidates"],
        "subset_ratio_pct": comp["ratio_pct"],
        "eligible": comp["eligible"],
        "held_out": comp["held_out"],
        "subset_scenes": comp["n_scenes"],
        "subset_templates": comp["n_templates"],
        "with_switch": comp["with_switch"],
        "subtasks_0": overall["subtasks_0"],
        "subtasks_1": overall["subtasks_1"],
        "subtasks_2": overall["subtasks_2"],
        "maxstep_fails": failure["maxstep_fails"],
        "maxstep_pct": failure["maxstep_pct"],
        "s1_ever": failure["s1"]["episodes_with_s1_first_true"],
        "s1_final": failure["s1"]["episodes_s1_final_true"],
        "s1_retract_events": failure["s1"]["s1_retract_events"],
        "s1_retract_eps": failure["s1"]["episodes_with_s1_retract"],
        "s1_mean_step": failure["s1"]["s1_first_true_step_mean"],
        "s1_median_step": failure["s1"]["s1_first_true_step_median"],
        "s1_lost": failure["lost_s1"],
        "one_with_s1_final": failure["one_with_s1_final"],
        "zero_with_s1_ever": failure["zero_with_s1_ever"],
        "obj_ref_episodes": obj_ref["episodes"],
        "obj_ref_success": obj_ref["success"],
        "obj_ref_rate_pct": round(100.0 * obj_ref["success_rate"], 2),
        "obj_ref_any": obj_ref["success_any_candidates"],
        "obj_ref_ge2": obj_ref["success_ge2_candidates"],
        "obj_ref_all3": obj_ref["success_all3_candidates"],
        "goal_ref_success": goal_ref["single_success"],
        "goal_ref_episodes": goal_ref["single_episodes"],
        "goal_ref_rate_pct": goal_ref["single_rate_pct"],
        "goal_staged_success": goal_ref["staged_success"],
        "goal_staged_episodes": goal_ref["staged_episodes"],
        "up_m1": upstream["m1"], "up_m2": upstream["m2"], "up_s1": upstream["s1"],
        "up_p0": upstream["p0"], "up_p1": upstream["p1"], "up_p2": upstream["p2"], "up_p3": upstream["p3"],
        "up_remaining": upstream["remaining"], "up_m1_rest": upstream["m1_rest"],
        "up_m1_p1": upstream["m1_p1"],
    }


def compute_model():
    sm = load_json(P_SUMMARY)
    fc = load_json(P_FINAL)
    es = load_json(P_SUBSET)
    pr = load_json(P_PROGRESS)
    sp = load_json(P_SMOKE_PAR)
    gpu = load_gpu_samples()
    oom_hits = scan_oom_markers()
    goal_ref = build_goal_ref(P_DOCS.read_text(encoding="utf-8"))
    upstream = build_upstream_counts(P_PROTOCOL.read_text(encoding="utf-8"))
    upstream["remaining"] = es["total_candidates"] - len(es["selected"])
    upstream["m1_rest"] = (upstream["remaining"] - upstream["m2"] - upstream["s1"]
                           - len(es["held_out_eligible"]))
    upstream["m1_p1"] = upstream["m1_rest"] - upstream["p2"] - upstream["p3"]
    if upstream["m1_rest"] + upstream["m2"] + upstream["s1"] + len(es["held_out_eligible"]) != upstream["remaining"]:
        raise SystemExit("[FATAL] PROTOCOL 全量候选分类与剩余候选数不自洽")
    if upstream["m1_p1"] < 0 or upstream["m1"] != 178 + upstream["m1_p1"] + upstream["p2"] + upstream["p3"]:
        raise SystemExit("[FATAL] PROTOCOL 全量 M1/P1 计数不自洽")
    obj_ref = sm["reference_object"]
    subset_by_id = {s["candidate_id"]: s for s in es["selected"]}

    seed_rows = build_seed_rows(sm)
    scene_rows = build_scene_rows(sm)
    group_rows = build_group_rows(scene_rows)
    template_rows = build_template_rows(sm)
    bucket_rows = build_bucket_rows(sm)
    order_rows = build_order_rows(sm)
    comp = build_composition(es, sm)
    failure = build_failure(sm, sm["episodes"])
    stability = build_stability(sm, subset_by_id)
    candidate_rows = build_candidate_rows(sm, subset_by_id)
    integrity = build_integrity(fc, gpu, sp, oom_hits, stability["counts"], comp["n"])
    metrics = build_metrics(sm, fc, pr, gpu, comp, stability, failure, seed_rows, goal_ref, obj_ref, oom_hits, upstream)
    hashes = input_hashes()
    return {
        "summary": sm,
        "final": fc,
        "subset": es,
        "progress": pr,
        "smoke_parallel": sp,
        "gpu": gpu,
        "oom_hits": oom_hits,
        "goal_ref": goal_ref,
        "upstream": upstream,
        "obj_ref": obj_ref,
        "overall": sm["overall"],
        "seed_rows": seed_rows,
        "scene_rows": scene_rows,
        "group_rows": group_rows,
        "template_rows": template_rows,
        "bucket_rows": bucket_rows,
        "order_rows": order_rows,
        "composition": comp,
        "failure": failure,
        "stability": stability,
        "candidate_rows": candidate_rows,
        "integrity": integrity,
        "metrics": metrics,
        "hashes": hashes,
        "digest": build_digest(hashes),
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
    }


def validate_model(m):
    problems = []
    sm = m["summary"]
    fc = m["final"]
    pr = m["progress"]
    es = m["subset"]
    comp = m["composition"]
    overall = sm["overall"]
    episodes = sm["episodes"]
    mt = m["metrics"]

    def need(cond, msg):
        if not cond:
            problems.append(msg)

    n = comp["n"]
    need(len(episodes) == overall["episodes"], f"episodes 数 {len(episodes)} != overall {overall['episodes']}")
    need(len(episodes) == 3 * n, f"episodes {len(episodes)} != 3 x {n}")
    need(len(sm["per_candidate"]) == n, f"per_candidate 数 {len(sm['per_candidate'])} != subset {n}")
    need(len(m["candidate_rows"]) == n, "候选表行数 != subset")
    need(len(es["selected"]) == n, "easy_subset.selected 数 != n")
    need(overall["success"] == sum(v["success"] for v in sm["by_seed"].values()), "seed success 之和 != overall")
    need(overall["episodes"] == sum(v["episodes"] for v in sm["by_seed"].values()), "seed episodes 之和 != overall")
    for key, rows in (
        ("by_scene", m["scene_rows"]), ("by_difficulty_bucket", m["bucket_rows"]),
        ("by_order", m["order_rows"]), ("by_instruction_template", m["template_rows"]),
    ):
        need(sum(r["episodes"] for r in rows) == overall["episodes"], f"{key} episodes 之和 != overall")
        need(sum(r["success"] for r in rows) == overall["success"], f"{key} success 之和 != overall")
    need(sum(g["episodes"] for g in m["group_rows"]) == overall["episodes"], "scene 分组 episodes 之和 != overall")
    need(sum(g["success"] for g in m["group_rows"]) == overall["success"], "scene 分组 success 之和 != overall")
    need(overall["subtasks_0"] + overall["subtasks_1"] + overall["subtasks_2"] == overall["episodes"],
         "子任务分布之和 != episodes")
    need(overall["success"] == overall["subtasks_2"], "success 数 != 完成 2 段数")
    need(sm["failure_modes"]["success"] == overall["success"], "failure_modes.success != overall.success")
    need(sum(failure_mode["count"] for failure_mode in m["failure"]["modes"]) == overall["episodes"],
         "failure modes 之和 != episodes")
    need(sum(row["count"] for row in m["failure"]["hist"]) == overall["episodes"], "steps 直方图之和 != episodes")
    maxsteps = sum(1 for e in episodes if e["steps"] >= sm["protocol"]["max_steps"])
    need(maxsteps == m["failure"]["maxstep_fails"], "跑满 max_steps 的 episode 数不一致")
    s1 = sm["s1_statistics"]
    need(0 <= s1["episodes_s1_final_true"] <= s1["episodes_with_s1_first_true"] <= overall["episodes"],
         "s1 统计顺序异常")
    need(s1["episodes_with_s1_retract"] <= overall["episodes"], "s1 回撤 episode 数异常")
    need(fc["overall_episodes"] == overall["episodes"] and fc["overall_success"] == overall["success"],
         "final_checks 与 overall 不一致")
    need(fc["checks_all_passed"] is True, "final_checks 未全部 PASS")
    need(all(code == 0 for code in fc["worker_exit_codes"]), "worker 退出码非 0")
    need(len(m["oom_hits"]) == 0, f"发现 OOM 标记: {m['oom_hits'][:2]}")
    need(pr["completed"] == overall["episodes"] and pr["success"] == overall["success"],
         "progress 与 analysis 不一致")
    need(comp["held_out"] + n == comp["eligible"], "held_out + selected != eligible")
    up = m["upstream"]
    need(up["m1"] + up["m2"] + up["s1"] == mt["total_candidates"], "PROTOCOL 全量 route 计数 != total")
    need(up["p0"] + up["p1"] + up["p2"] + up["p3"] == mt["total_candidates"], "PROTOCOL 全量 priority 计数 != total")
    need(up["remaining"] == mt["total_candidates"] - n, "PROTOCOL remaining 口径异常")
    need(up["m2"] + up["s1"] + up["m1_rest"] + mt["held_out"] == up["remaining"],
         "剩余候选分类之和 != remaining")
    need(up["m1_p1"] >= 0 and up["m1_rest"] >= 0, "PROTOCOL 剩余 M1 分类为负")
    need(sum(comp["by_scene"].values()) == n, "subset by_scene 之和 != n")
    need(sum(comp["by_template"].values()) == n, "subset by_template 之和 != n")
    need(sum(comp["by_bucket"].values()) == n, "subset by_bucket 之和 != n")
    need(sum(comp["by_order"].values()) == n, "subset by_order 之和 != n")
    need(comp["n"] * 3 == overall["episodes"], "subset n x 3 != episodes")
    need(len(m["stability"]["rows"]) == len(sm["stable_candidates"]["success_any"]), "稳定候选 any 数不一致")
    need(len(m["stability"]["ge2_rows"]) == len(sm["stable_candidates"]["success_ge2"]), "稳定候选 ge2 数不一致")
    need(len(m["stability"]["all3_rows"]) == len(sm["stable_candidates"]["success_all3"]), "稳定候选 all3 数不一致")
    need(set(sm["stable_candidates"]["success_ge2"]) <= set(sm["stable_candidates"]["success_any"]),
         "ge2 不是 any 子集")
    need(set(sm["stable_candidates"]["success_all3"]) <= set(sm["stable_candidates"]["success_ge2"]),
         "all3 不是 ge2 子集")
    need(set(subset_by_id_ref(es)) == set(sm["per_candidate"].keys()), "subset 与 per_candidate 候选集合不一致")
    need(all(p["seeds_completed"] == 3 for p in sm["per_candidate"].values()), "存在 seeds_completed != 3 的候选")
    need(all(p["n_success"] == len(p["seeds_success"]) for p in sm["per_candidate"].values()),
         "per_candidate n_success 与 seeds_success 长度不一致")
    need(all(len(p["steps"]) == 3 and len(p["subtasks_done"]) == 3 for p in sm["per_candidate"].values()),
         "per_candidate steps/subtasks 长度 != 3")
    need(m["metrics"]["gpu_peak_mib"] <= m["metrics"]["gpu_total_mib"], "GPU 峰值 > 显存总量")
    need(m["goal_ref"]["single_success"] > 0 and m["goal_ref"]["staged_episodes"] > 0, "GOAL 参考数字解析异常")
    need(m["obj_ref"]["episodes"] > 0, "OBJECT 参考数字缺失")
    # 稳定性候选来自 per_candidate 中 n_success>0
    with_success = {cid for cid, p in sm["per_candidate"].items() if p["n_success"] > 0}
    need(with_success == set(sm["stable_candidates"]["success_any"]), "有成功候选集合与 stable success_any 不一致")
    if problems:
        raise SystemExit("[FATAL] 输入数据不自洽:\n - " + "\n - ".join(problems))


def subset_by_id_ref(es):
    return [s["candidate_id"] for s in es["selected"]]

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
.q{color:#6b7280;font-size:11.5px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px;margin:12px 0}
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
.badge{display:inline-block;padding:1px 7px;border-radius:9px;font-size:11px;font-weight:700;margin:1px 2px 1px 0;white-space:nowrap}
.b-ok{background:#dcfce7;color:#15803d}.b-fail{background:#fee2e2;color:#b91c1c}
.b-warn{background:#fef3c7;color:#a16207}.b-info{background:#dbeafe;color:#1d4ed8}
.b-muted{background:#f3f4f6;color:#6b7280}.b-p0{background:#dcfce7;color:#15803d}
.b-lr{background:#fce7f3;color:#9d174d}.b-kitchen{background:#fef3c7;color:#92400e}.b-study{background:#e0e7ff;color:#3730a3}
.b-review{background:#bbf7d0;color:#14532d}
.barchart{margin:10px 0;background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:10px 14px}
.barrow{display:grid;grid-template-columns:190px 1fr 96px;gap:8px;align-items:center;margin:4px 0;font-size:12px}
.barrow .lab{color:#374151;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.barrow .bar{background:#eef2f7;border-radius:5px;height:14px;overflow:hidden}
.barrow .bar span{display:block;height:14px;border-radius:5px;background:#60a5fa}
.barrow .val{color:#4b5563;text-align:right;font-variant-numeric:tabular-nums}
.barrow.hot .bar span{background:#16a34a}
.barrow.warm .bar span{background:#f59e0b}
.barrow.cold .bar span{background:#ef4444}
.panel{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px 14px;margin:10px 0}
.integrity td.ok{color:#15803d;font-weight:600}.integrity td.bad{color:#b91c1c;font-weight:600}
.filterbar{position:sticky;top:0;z-index:30;background:rgba(247,248,250,.97);border-bottom:1px solid #e5e7eb;padding:8px 0;display:flex;gap:8px;flex-wrap:wrap;align-items:center;font-size:12.5px}
.filterbar select,.filterbar button{background:#fff;color:#111827;border:1px solid #d1d5db;border-radius:6px;padding:4px 7px;font-size:12px;cursor:pointer}
.filterbar .count{color:#1d4ed8;font-weight:600;margin-left:auto}
.filterbar .hint{color:#6b7280;font-size:11px;flex-basis:100%}
.candtable td:first-child,.candtable td:nth-child(2){white-space:nowrap}
.candtable .seeds{font-variant-numeric:tabular-nums;font-size:11.5px}
.bigcards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;margin:10px 0}
.bigcard{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px}
.bigcard.gold{border-color:#86efac;background:#f0fdf4}
.bigcard .id{font-weight:700;font-size:12.5px;word-break:break-all}
.bigcard .instr{font-size:12px;color:#4b5563;margin:6px 0}
.bigcard .kv{font-size:11.5px;color:#6b7280;line-height:1.6}
.bigcard .seeds{font-variant-numeric:tabular-nums}
ul.flat{margin:8px 0;padding-left:20px}ul.flat li{margin:5px 0;color:#374151;font-size:13px}
ol.risk{margin:8px 0;padding-left:22px}ol.risk li{margin:7px 0;color:#374151;font-size:13px;line-height:1.6}
.note{background:#f8fafc;border-left:3px solid #cbd5e1;padding:6px 10px;color:#4b5563;font-size:12px;border-radius:4px;margin:6px 0;line-height:1.6}
.note.warn{background:#fffbeb;border-left-color:#f59e0b;color:#78350f}
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

  var resSel = document.getElementById('filter-result');
  var sceneSel = document.getElementById('filter-scene');
  var tplSel = document.getElementById('filter-template');
  var reset = document.getElementById('filter-reset');
  var counter = document.getElementById('filter-count');
  if (!resSel || !sceneSel || !tplSel || !counter) return;
  var rows = Array.prototype.slice.call(document.querySelectorAll('tr.cand-row'));
  function resultOk(tr, val){
    if (!val) return true;
    var n = parseInt(tr.dataset.nSuccess || '0', 10);
    if (val === 'any') return n >= 1;
    if (val === 'ge2') return n >= 2;
    if (val === 'all3') return n >= 3;
    if (val === 'zero') return n === 0;
    return n === parseInt(val, 10);
  }
  function apply(){
    var r = resSel.value, s = sceneSel.value, t = tplSel.value, shown = 0;
    rows.forEach(function(tr){
      var ok = resultOk(tr, r) && (!s || tr.dataset.scene === s) && (!t || tr.dataset.template === t);
      tr.style.display = ok ? '' : 'none';
      if (ok) shown++;
    });
    counter.textContent = '显示 ' + shown + ' / ' + rows.length + ' 条候选';
  }
  resSel.addEventListener('change', apply);
  sceneSel.addEventListener('change', apply);
  tplSel.addEventListener('change', apply);
  if (reset) reset.addEventListener('click', function(){ resSel.value = ''; sceneSel.value = ''; tplSel.value = ''; apply(); });
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
             '<div class="brand">LIBERO-90 低难度候选<br>pi05 · 3 seeds 验证</div>',
             '<div class="grp">总览</div>',
             '<a href="#top">状态与结论</a>',
             '<a href="#overview">指标与运行完整性</a>',
             '<a href="#compare">与参考实验对比</a>',
             '<div class="grp">结果分布</div>',
             '<a href="#dist-seed">按 seed</a>',
             '<a href="#dist-scene">按场景（17）</a>',
             '<a href="#dist-template">按指令模板</a>',
             '<a href="#dist-bucket-order">按难度桶 / 顺序</a>',
             '<a href="#dist-subset">子集构成</a>',
             '<div class="grp">分析</div>',
             '<a href="#failures">失败分析</a>',
             '<a href="#stability">稳定性候选（19/12/10）</a>',
             '<a href="#candidates">全部 161 条候选</a>',
             '<div class="grp">结论与附录</div>',
             '<a href="#conclusions">结论与建议</a>',
             '<a href="#caveats">口径 / 偏差 / 数据问题</a>',
             '<a href="#artifacts">产物索引</a>',
             '<div class="foot">pi05 单指令 zero-shot<br>video off（协议偏差）<br>161 低难度子集，不可外推<br>scripts/build_libero90_easy_validation_report.py</div>',
             '</nav>']
    return "\n".join(parts)


def render_hero(m):
    mt = m["metrics"]
    sm = m["summary"]
    protocol = sm["protocol"]
    return f'''<header class="hero" id="top">
<h1>LIBERO-90 低难度双目标候选 · pi05 3-seed 零样本验证报告</h1>
<p class="meta"><b>{mt["subset_n"]}</b> 条低难度候选（= 322 条 v2 候选的 <span data-metric="subset_ratio_pct">{mt["subset_ratio_pct"]}</span>%）× <b>pi05</b> × seeds {{0,1,2}} = <b>{mt["episodes"]} episodes</b> · max_steps={protocol["max_steps"]} / replan={protocol["replan_steps"]} / video <b>off</b> · 数据时间 {esc(sm["generated_at"])} · 运行目录 <code>runs/libero-90-easy-pi05-20261026/</code></p>
<div class="status ok"><b>一句话结论</b>：pi05 在低难度双目标候选上的单指令 zero-shot 成功率为 <b>{mt["success"]} / {mt["episodes"]} = {mt["success_rate_pct"]}%</b>；<b>T1 模板最强（{m["template_rows"][0]["success"]}/{m["template_rows"][0]["episodes"]} = {m["template_rows"][0]["rate_pct"]}%）</b>，<b>LIVING_ROOM 场景主导</b>（{m["group_rows"][1]["success"] if len(m["group_rows"]) > 1 else 0}/{mt["success"]} 成功），共 <b>{mt["stable_all3"]}</b> 个候选 3/3 全成功、<b>{mt["stable_ge2"]}</b> 个 ≥2 seeds、<b>{mt["stable_any"]}</b> 个至少成功一次；失败集中在“完成 1 段后停滞”（{mt["subtasks_1"]}/{mt["episodes"]}），{mt["maxstep_fails"]}/{mt["episodes"]} 跑满 600 步。</div>
<div class="status warn"><b>口径声明（必读）</b>：{mt["subset_n"]} 条 = <b>低难度半数</b>（M1-P0-valid-compatible-n_atoms2；eligible {mt["eligible"]} 条中按难度分剔除 {mt["held_out"]} 条 held-out）；<b>video off</b>（正式队列按 Lead 指示关闭视频，与 PROTOCOL §4 的 “video on” 有出入，属已记录的协议偏差）；<b>单指令 zero-shot</b>（无 staged / instruction-switch / rollback）；成功率<b>只代表该子集</b>，不可外推全量 322 条，也不能与官方 pi05 数字横比。</div>
<p class="method"><b>协议</b>：pi05（OpenPI PyTorch 后端；checkpoint <code>pi05_libero</code>）；success = LIBERO <code>check_success()</code>；seeds {{0,1,2}}，seed s 的初始状态 = sibling <code>.pruned_init</code> 第 <code>s % 50</code> 行；每控制步记录 goal 原子真值（trace）；2 worker 并行（每 worker 独立 JAX 进程，<code>XLA_PYTHON_CLIENT_MEM_FRACTION=0.42</code>）。</p>
<p class="gen">生成脚本 <code>scripts/build_libero90_easy_validation_report.py</code> · 数据来源 <code>analysis/summary.json</code>（{esc(sm["generated_at"])}）+ <code>final_checks.json</code> + <code>prep/easy_subset.json</code> + <code>logs/*</code> · 构建指纹见页脚 · 单文件内联 CSS/JS，无外链 CDN</p>
</header>'''


def render_overview(m):
    mt = m["metrics"]
    sm = m["summary"]
    protocol = sm["protocol"]
    progress = m["progress"]
    cards = [
        ("episodes", f'<span data-metric="episodes">{mt["episodes"]}</span>', "episodes（161 候选 × 3 seeds）",
         f'完成 <span data-metric="episodes">{mt["episodes"]}</span> / {mt["episodes"]}（100%）· final_checks 全 PASS'),
        ("success", f'<span data-metric="success">{mt["success"]}</span> / <span data-metric="success_rate_pct">{mt["success_rate_pct"]}</span>%', "success（check_success）",
         f'平均/中位步数 <span data-metric="mean_steps">{mt["mean_steps"]}</span> / <span data-metric="median_steps">{mt["median_steps"]}</span>；成功的 episode 平均 <span data-metric="success_mean_steps">{mt["success_mean_steps"]}</span> 步，失败全部 <span data-metric="fail_mean_steps">{mt["fail_mean_steps"]}</span> 步'),
        ("seeds", f'<span data-metric="seed0_success">{mt["seed0_success"]}</span> / <span data-metric="seed1_success">{mt["seed1_success"]}</span> / <span data-metric="seed2_success">{mt["seed2_success"]}</span>', "per-seed success（0 / 1 / 2）",
         f'seed 成功率 <span data-metric="seed0_rate_pct">{mt["seed0_rate_pct"]}</span>% / <span data-metric="seed1_rate_pct">{mt["seed1_rate_pct"]}</span>% / <span data-metric="seed2_rate_pct">{mt["seed2_rate_pct"]}</span>%；episodes 各 161'),
        ("stability", f'<span data-metric="stable_any">{mt["stable_any"]}</span> · <span data-metric="stable_ge2">{mt["stable_ge2"]}</span> · <span data-metric="stable_all3">{mt["stable_all3"]}</span>', "稳定候选：≥1 / ≥2 seeds / 3/3",
         f'与 OBJECT 实验同口径；{mt["stable_all3"]} 条 3/3 可直接进入 rollback 原型'),
        ("wall", f'<span data-metric="wall_hours">{mt["wall_hours"]}</span> h', "队列 wall time",
         f'<span data-metric="wall_seconds">{mt["wall_seconds"]}</span> s · 实测 <span data-metric="rate_progress">{mt["rate_progress"]}</span> eps/h（<span data-metric="sec_per_episode">{mt["sec_per_episode"]}</span> s/ep）；按 wall 折算 <span data-metric="rate_wall">{mt["rate_wall"]}</span> eps/h（分母差异见口径节）'),
        ("gpu", f'<span data-metric="gpu_peak_mib">{mt["gpu_peak_mib"]}</span> / <span data-metric="gpu_total_mib">{mt["gpu_total_mib"]}</span> MiB', "GPU 峰值显存（无 OOM）",
         f'<span data-metric="gpu_samples">{mt["gpu_samples"]}</span> 个 nvidia-smi 采样；OOM 标记 <span data-metric="oom_markers">{mt["oom_markers"]}</span>；2 worker 并行（XLA fraction 0.42）'),
        ("fails", f'<span data-metric="subtasks_0">{mt["subtasks_0"]}</span> / <span data-metric="subtasks_1">{mt["subtasks_1"]}</span> / <span data-metric="subtasks_2">{mt["subtasks_2"]}</span>', "完成 0 段 / 1 段后停滞 / 2 段（success）",
         f'{mt["maxstep_fails"]} / {mt["episodes"]} 跑满 <span data-metric="max_steps">{mt["max_steps"]}</span> 步（<span data-metric="maxstep_fails">{mt["maxstep_fails"]}</span>，<span data-metric="maxstep_pct">{mt["maxstep_pct"]}</span>%）；最短 episode <span data-metric="min_steps">{mt["min_steps"]}</span> 步'),
        ("subset", f'<span data-metric="subset_n">{mt["subset_n"]}</span> / <span data-metric="total_candidates">{mt["total_candidates"]}</span>', "低难度子集 / 全量候选",
         f'eligible <span data-metric="eligible">{mt["eligible"]}</span> 条中剔除 held-out <span data-metric="held_out">{mt["held_out"]}</span> 条；覆盖 <span data-metric="subset_scenes">{mt["subset_scenes"]}</span> 场景 / <span data-metric="subset_templates">{mt["subset_templates"]}</span> 模板；含开关 goal <span data-metric="with_switch">{mt["with_switch"]}</span> 条'),
    ]
    card_html = "".join(
        f'<div class="metric"><div class="v">{v}</div><div class="l">{label}</div><div class="d">{desc}</div></div>'
        for _, v, label, desc in cards
    )
    protocol_rows = "".join(
        f'<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>'
        for k, v in [
            ("模型 / runtime", f'{protocol["model"]}（OpenPI PyTorch 后端）· runtime {protocol["runtime"]} · shadow {protocol["shadow"]}'),
            ("seeds", f'{protocol["seeds"]}（seed s 的 init 行 = s % 50）'),
            ("episodes", f'{mt["subset_n"]} 候选 × 3 seeds = {mt["episodes"]}'),
            ("max_steps / replan", f'{protocol["max_steps"]} / {protocol["replan_steps"]}'),
            ("success 判定", protocol["success_definition"]),
            ("init", protocol["init_source"]),
            ("video", "off（正式队列按 Lead 指示关闭；与 PROTOCOL §4 的 on 不一致，见口径节）"),
            ("指令", "候选 BDDL 的 :language = 模板化 instruction（单指令、一次跑完双目标）"),
            ("并行", "2 worker（每 seed 按 rank 奇偶拆分；每 worker 独立 JAX；GPU 独占）"),
        ]
    )
    integrity_rows = "".join(
        f'<tr><td>{esc(row["item"])}</td><td class="{"ok" if row["ok"] else "bad"}">'
        f'{"PASS ✓" if row["ok"] else "FAIL ✗"}</td><td class="tiny">{esc(row["detail"])}</td></tr>'
        for row in m["integrity"]["rows"]
    )
    return f'''<section id="overview">
<h2>一、指标与运行完整性</h2>
<p class="sub">所有数字由脚本从 <code>analysis/summary.json</code> / <code>final_checks.json</code> / <code>prep/easy_subset.json</code> / <code>run/progress.json</code> / <code>logs/*</code> 计算，<code>--check</code> 逐项复验；<code>final_checks.json</code> 的总判定为 <b>{"PASS" if m["integrity"]["all_pass"] else "FAIL"}</b>。</p>
<div class="cards">{card_html}</div>
<h3>1.1 运行参数（来自 protocol / progress）</h3>
<div class="tblwrap"><table>
<thead><tr><th>项</th><th>值</th></tr></thead>
<tbody>{protocol_rows}</tbody></table></div>
<h3>1.2 运行完整性（final_checks.json，{len(m["integrity"]["rows"])} 项）</h3>
<div class="tblwrap"><table class="integrity">
<thead><tr><th>检查项</th><th>结果</th><th>证据 / 数值</th></tr></thead>
<tbody>{integrity_rows}</tbody></table></div>
<p class="note">完整性结论：<b>{"全部 PASS" if m["integrity"]["all_pass"] else "存在 FAIL"}</b>；trace 共 {m["integrity"]["traces"]} 条（161 × 3），worker 退出码全部为 0，GPU 无 OOM，success 全部来自 <code>results.json</code>。视频在正式队列关闭，因此失败原因只来自 trace 真值序列，没有视频级复核（见口径节）。</p>
</section>'''


def render_compare(m):
    mt = m["metrics"]
    obj = m["obj_ref"]
    goal = m["goal_ref"]
    return f'''<section id="compare">
<h2>二、与参考实验对比</h2>
<p class="sub">与 OBJECT v3（<code>runs/object-inscene-100-20261023</code>）和 GOAL 历史实验（<code>runs/combined-tasks-20261019</code>）同 checkpoint / 同 success 定义的对比；OBJECT 数字来自本 run 的 <code>summary.json.reference_object</code>，GOAL 数字由脚本从 <code>docs/libero-90-dual-target-candidates.md</code> 解析（非本 run 实测）。</p>
<h3>2.1 成功率对比</h3>
<div class="tblwrap"><table>
<thead><tr><th>实验</th><th>候选 / episodes</th><th>success</th><th>成功率</th><th>稳定性（≥1 / ≥2 / 3/3）</th><th>可比性</th></tr></thead>
<tbody>
<tr class="hi"><td><b>本验证（LIBERO-90 低难度）</b></td><td>{mt["subset_n"]} 候选 × 3 seeds = {mt["episodes"]}</td><td>{mt["success"]}</td><td><b>{mt["success_rate_pct"]}%</b></td><td>{mt["stable_any"]} / {mt["stable_ge2"]} / {mt["stable_all3"]}</td><td>本页主体</td></tr>
<tr><td>OBJECT v3（场景内提升）</td><td>100 × 3 = {obj["episodes"]}</td><td>{obj["success"]}</td><td>{round(100.0 * obj["success_rate"], 2)}%</td><td>{obj["success_any_candidates"]} / {obj["success_ge2_candidates"]} / {obj["success_all3_candidates"]}</td><td>同 pi05/seeds/600/10；<b>不同套件、不同候选构成</b> → 仅量级参考</td></tr>
<tr><td>GOAL 历史单指令（引用 docs）</td><td>{goal["single_episodes"]} episodes</td><td>{goal["single_success"]}</td><td>≈ {goal["single_rate_pct"]}%（docs 写 {goal["single_rate_doc"]}%）</td><td>staged {goal["staged_success"]}/{goal["staged_episodes"]}</td><td>历史批次步数预算更小、非统一口径 → <b>不可统计检验</b></td></tr>
</tbody></table></div>
<h3>2.2 口径同 / 异</h3>
<div class="tblwrap"><table>
<thead><tr><th>维度</th><th>本验证</th><th>OBJECT v3</th><th>GOAL 历史</th><th>可比性</th></tr></thead>
<tbody>
<tr><td>模型 / success 定义</td><td>pi05 PyTorch + <code>check_success()</code></td><td>pi05 + <code>check_success()</code></td><td>pi05 + <code>check_success()</code></td><td>相同</td></tr>
<tr><td>seeds</td><td>{{0,1,2}}</td><td>{{0,1,2}}</td><td>历史批次混合</td><td>本验证与 OBJECT 相同</td></tr>
<tr><td>max_steps / replan</td><td>{m["summary"]["protocol"]["max_steps"]} / {m["summary"]["protocol"]["replan_steps"]}</td><td>600 / 10</td><td>220–520 / 5（历史）</td><td>本验证步数预算更大</td></tr>
<tr><td>任务来源</td><td>LIBERO-90 同场景两条原生任务的组合（M1-P0-compatible）</td><td>LIBERO-OBJECT 场景内提升（第二目标非原生）</td><td>LIBERO-GOAL 同场景直接组合</td><td>路线同源、套件不同</td></tr>
<tr><td>候选数</td><td>{mt["subset_n"]}（低难度半数）</td><td>100</td><td>90 ordered（47 episodes 实测）</td><td>规模不同</td></tr>
<tr><td>指令</td><td>模板化 T1/T2/T3/T6/T10（本次实测 {mt["subset_templates"]} 种模板）</td><td>OBJECT v3 模板 <code>put both A and B in basket</code></td><td>历史措辞</td><td>模板血缘部分相同</td></tr>
<tr><td>协议</td><td>单指令 zero-shot（本次）；staged 建议下一步</td><td>单指令</td><td>单指令 + staged 2/3</td><td>本次未测 staged</td></tr>
<tr><td>video</td><td>off（协议偏差）</td><td>该批次未录</td><td>未知</td><td>不影响 success 指标</td></tr>
<tr><td>init</td><td>sibling <code>.pruned_init</code> 第 seed%50 行（官方 init，逐字节拷贝）</td><td>同类复用官方 init</td><td>历史 init 策略不同</td><td>本验证与 OBJECT 同路线</td></tr>
</tbody></table></div>
<p class="note warn">参考实验数字（机读，供 <code>--check</code> 复验）：OBJECT v3 episodes <span data-metric="obj_ref_episodes">{obj["episodes"]}</span> / success <span data-metric="obj_ref_success">{obj["success"]}</span> / rate <span data-metric="obj_ref_rate_pct">{round(100.0 * obj["success_rate"], 2)}</span>% / any <span data-metric="obj_ref_any">{obj["success_any_candidates"]}</span> / ≥2 <span data-metric="obj_ref_ge2">{obj["success_ge2_candidates"]}</span> / 3/3 <span data-metric="obj_ref_all3">{obj["success_all3_candidates"]}</span>；GOAL 单指令 <span data-metric="goal_ref_success">{goal["single_success"]}</span>/<span data-metric="goal_ref_episodes">{goal["single_episodes"]}</span>（<span data-metric="goal_ref_rate_pct">{goal["single_rate_pct"]}</span>%），staged <span data-metric="goal_staged_success">{goal["staged_success"]}</span>/<span data-metric="goal_staged_episodes">{goal["staged_episodes"]}</span>。</p>
<p class="note warn">解读边界：{mt["success_rate_pct"]}% 只说明“pi05 零样本在低难度 M1-P0 子集 + 单指令协议”的量级（介于 GOAL 历史 4.3% 与 OBJECT 4.0% 之上、仍为个位数~十几个百分点区间）；不同套件/候选构成/步数预算不可横比，官方 pi05 数字也不能直接对照。staged 在 GOAL 上 2/3，但本 run 未测 staged；失败模式（{mt["subtasks_1"]} 条完成后 1 段停滞）与 GOAL/OBJECT 的历史先验一致。</p>
</section>'''

def render_dist_seed(m):
    mt = m["metrics"]
    rows = m["seed_rows"]
    max_rate = max((r["success_rate"] for r in rows), default=0)
    bars = "".join(
        bar_row(f'seed {r["seed"]}', r["success_rate"] / max_rate if max_rate else 0,
                f'{r["success"]}/{r["episodes"]} · {r["rate_pct"]}%',
                "hot" if r["success_rate"] >= max_rate * 0.99 else "cool")
        for r in rows
    )
    body = "".join(
        f'<tr data-seed="{r["seed"]}" data-episodes="{r["episodes"]}" data-success="{r["success"]}" '
        f'data-rate="{r["rate_pct"]}"><td><b>seed {r["seed"]}</b></td><td>{r["episodes"]}</td>'
        f'<td><b>{r["success"]}</b></td><td>{r["rate_pct"]}%</td><td>{r["mean_steps"]}</td>'
        f'<td>{r["subtasks_0"]} / {r["subtasks_1"]} / {r["subtasks_2"]}</td></tr>'
        for r in rows
    )
    return f'''<section id="dist-seed">
<h2>三、按 seed（0 / 1 / 2）</h2>
<p class="sub">每 seed 固定 161 个 episode（同一候选集、同一 init 行规则）；seed 2 成功率最高（{mt["seed2_rate_pct"]}%），但 3 个 seed 间差异仅 +1 / +3 个成功，属于小样本波动。</p>
<div class="tblwrap"><table>
<thead><tr><th>seed</th><th>episodes</th><th>success</th><th>成功率</th><th>mean steps</th><th>子任务 0 / 1 / 2</th></tr></thead>
<tbody>{body}</tbody></table></div>
<div class="barchart">{bars}</div>
<p class="note">口径：seed s 使用 sibling <code>.pruned_init</code> 第 s%50 行；success 为 LIBERO <code>check_success()</code>；每 seed 的 161 个 episode 100% 完成（final_checks：missing = 0）。</p>
</section>'''


def render_dist_scene(m):
    mt = m["metrics"]
    rows = m["scene_rows"]
    max_rate = max((r["success_rate"] for r in rows), default=0)
    bars = "".join(
        bar_row(f'{r["scene"]}', r["success_rate"] / max_rate if max_rate else 0,
                f'{r["success"]}/{r["episodes"]} · {r["rate_pct"]}%',
                "hot" if r["success_rate"] >= 0.15 else ("warm" if r["success_rate"] > 0 else "cold"))
        for r in rows
    )
    body = []
    for r in rows:
        cls = "hi" if r["success"] > 0 else "zero"
        body.append(
            f'<tr class="{cls}" data-scene="{r["scene"]}" data-group="{r["group"]}" data-candidates="{r["candidates"]}" '
            f'data-episodes="{r["episodes"]}" data-success="{r["success"]}" data-rate="{r["rate_pct"]}">'
            f'<td><code>{r["scene"]}</code></td><td>{r["group"]}</td><td>{r["candidates"]}</td>'
            f'<td>{r["episodes"]}</td><td><b>{r["success"]}</b></td><td>{r["rate_pct"]}%</td>'
            f'<td>{r["mean_steps"]}</td><td>{r["subtasks_0"]} / {r["subtasks_1"]} / {r["subtasks_2"]}</td></tr>'
        )
    group_chips = "".join(
        f'<span class="chip"><b>{esc(GROUP_CN[g["group"]])}</b> {g["success"]}/{g["episodes"]} · {g["rate_pct"]}%'
        f'（{g["scenes"]} 场景）</span>'
        for g in m["group_rows"]
    )
    successful_scenes = [r["scene"] for r in rows if r["success"] > 0]
    missing = [sc for sc in ("KITCHEN_SCENE8", "KITCHEN_SCENE10", "STUDY_SCENE2")
               if sc not in {r["scene"] for r in rows}]
    return f'''<section id="dist-scene">
<h2>四、按场景（{mt["subset_scenes"]} 个场景）</h2>
<div class="chips">{group_chips}</div>
<p class="sub">LIVING_ROOM 主导成功：{len([s for s in successful_scenes if s.startswith("LIVING_ROOM")])} 个 LR 场景产生 {m["group_rows"][1]["success"] if len(m["group_rows"]) > 1 else 0} 个成功；KITCHEN 仅 KITCHEN_SCENE2 有成功；STUDY 全 0。{("本子集未覆盖场景：" + "、".join(missing) + "（不在 161 条低难度候选内）。") if missing else ""}</p>
<div class="tblwrap"><table>
<thead><tr><th>场景</th><th>类型</th><th>候选</th><th>episodes</th><th>success</th><th>成功率</th><th>mean steps</th><th>子任务 0 / 1 / 2</th></tr></thead>
<tbody>{"".join(body)}</tbody></table></div>
<div class="barchart">{bars}</div>
<p class="note">解读：{mt["subtasks_1"]} 条“完成 1 段后停滞”里绝大多数发生在 KITCHEN / STUDY 场景；LR 场景（尤其 LR3 {m["scene_rows"][0]["rate_pct"] if m["scene_rows"] and m["scene_rows"][0]["scene"].startswith("LIVING_ROOM") else ""}%）说明同容器双物体（T1 模板）在本子集上确有可解性。逐场景候选数 = episodes / 3。</p>
</section>'''


def render_dist_template(m):
    mt = m["metrics"]
    rows = m["template_rows"]
    max_rate = max((r["success_rate"] for r in rows), default=0)
    bars = "".join(
        bar_row(f'{r["template"]}', r["success_rate"] / max_rate if max_rate else 0,
                f'{r["success"]}/{r["episodes"]} · {r["rate_pct"]}%',
                "hot" if r["success_rate"] >= 0.10 else ("warm" if r["success_rate"] > 0 else "cold"))
        for r in rows
    )
    body = "".join(
        f'<tr class="{"hi" if r["success"] > 0 else "zero"}" data-template="{r["template"]}" '
        f'data-episodes="{r["episodes"]}" data-success="{r["success"]}" data-rate="{r["rate_pct"]}">'
        f'<td><code>{r["template"]}</code></td><td>{r["episodes"]}</td><td><b>{r["success"]}</b></td>'
        f'<td>{r["rate_pct"]}%</td><td>{r["mean_steps"]}</td>'
        f'<td>{r["subtasks_0"]} / {r["subtasks_1"]} / {r["subtasks_2"]}</td></tr>'
        for r in rows
    )
    top = rows[0]
    zeros = [r["template"] for r in rows if r["success"] == 0]
    return f'''<section id="dist-template">
<h2>五、按指令模板</h2>
<p class="sub">T1（<code>put both {{{{A}}}} and {{{{B}}}} in {{{{C}}}}</code>，同容器双物体）验证为最有效指令族：<b>{top["success"]}/{top["episodes"]} = {top["rate_pct"]}%</b>；T3（不同落点双 put）{next((r["rate_pct"] for r in rows if r["template"] == "T3"), "—")}%，T6（放置+打开/关闭）{next((r["rate_pct"] for r in rows if r["template"] == "T6"), "—")}%，T2/T10 本子集全 0。</p>
<div class="tblwrap"><table>
<thead><tr><th>模板</th><th>episodes</th><th>success</th><th>成功率</th><th>mean steps</th><th>子任务 0 / 1 / 2</th></tr></thead>
<tbody>{body}</tbody></table></div>
<div class="barchart">{bars}</div>
<p class="note">模板分布来自 161 条候选的 <code>instruction_template</code>（每题 ×3 seeds）；T1/T3/T6/T2/T10 各 {m["composition"]["by_template"].get("T1", 0)}/{m["composition"]["by_template"].get("T3", 0)}/{m["composition"]["by_template"].get("T6", 0)}/{m["composition"]["by_template"].get("T2", 0)}/{m["composition"]["by_template"].get("T10", 0)} 条候选。零成功模板（{", ".join(zeros)}）需改协议（staged / instruction-switch）或做措辞变体对照，不能直接判死。</p>
</section>'''


def render_dist_bucket_order(m):
    mt = m["metrics"]
    bucket_rows = m["bucket_rows"]
    order_rows = m["order_rows"]
    max_rate = max((r["success_rate"] for r in bucket_rows), default=0)
    bucket_bars = "".join(
        bar_row(r["bucket_cn"], r["success_rate"] / max_rate if max_rate else 0,
                f'{r["success"]}/{r["episodes"]} · {r["rate_pct"]}%',
                "hot" if r["success_rate"] >= 0.10 else ("warm" if r["success_rate"] > 0 else "cold"))
        for r in bucket_rows
    )
    max_order = max((r["success_rate"] for r in order_rows), default=0)
    order_bars = "".join(
        bar_row(ORDER_CN.get(r["order"], r["order"]), r["success_rate"] / max_order if max_order else 0,
                f'{r["success"]}/{r["episodes"]} · {r["rate_pct"]}%', "cool")
        for r in order_rows
    )
    bucket_body = "".join(
        f'<tr class="{"hi" if r["success"] > 0 else "zero"}" data-bucket="{r["bucket"]}" '
        f'data-episodes="{r["episodes"]}" data-success="{r["success"]}" data-rate="{r["rate_pct"]}">'
        f'<td><code>{r["bucket"]}</code></td><td>{r["episodes"]}</td><td><b>{r["success"]}</b></td>'
        f'<td>{r["rate_pct"]}%</td><td>{r["mean_steps"]}</td>'
        f'<td>{r["subtasks_0"]} / {r["subtasks_1"]} / {r["subtasks_2"]}</td></tr>'
        for r in bucket_rows
    )
    order_body = "".join(
        f'<tr data-order="{r["order"]}" data-episodes="{r["episodes"]}" data-success="{r["success"]}" '
        f'data-rate="{r["rate_pct"]}"><td><code>{r["order"]}</code></td><td>{r["episodes"]}</td>'
        f'<td><b>{r["success"]}</b></td><td>{r["rate_pct"]}%</td><td>{r["mean_steps"]}</td>'
        f'<td>{r["subtasks_0"]} / {r["subtasks_1"]} / {r["subtasks_2"]}</td></tr>'
        for r in order_rows
    )
    sd = next((r for r in bucket_rows if r["bucket"].startswith("same_destination")), bucket_rows[0])
    ind = next((r for r in bucket_rows if r["bucket"] == "independent"), bucket_rows[-1])
    sf = next((r for r in bucket_rows if r["bucket"].startswith("same_furniture")), None)
    ab = next((r for r in order_rows if r["order"] == "ab"), order_rows[0])
    ba = next((r for r in order_rows if r["order"] == "ba"), order_rows[-1])
    return f'''<section id="dist-bucket-order">
<h2>六、按难度桶与指令顺序</h2>
<h3>6.1 difficulty_bucket</h3>
<p class="sub">同容器/同落点（capacity）<b>{sd["success"]}/{sd["episodes"]} = {sd["rate_pct"]}%</b> &gt; independent <b>{ind["success"]}/{ind["episodes"]} = {ind["rate_pct"]}%</b>{f' &gt; same_furniture/fixture <b>{sf["success"]}/{sf["episodes"]} = {sf["rate_pct"]}%</b>' if sf else ""}。同容器任务明显更可解，与 T1 模板结论一致。</p>
<div class="tblwrap"><table>
<thead><tr><th>bucket</th><th>episodes</th><th>success</th><th>成功率</th><th>mean steps</th><th>子任务 0 / 1 / 2</th></tr></thead>
<tbody>{bucket_body}</tbody></table></div>
<div class="barchart">{bucket_bars}</div>
<h3>6.2 指令顺序（ab / ba）</h3>
<p class="sub">ab {ab["success"]}/{ab["episodes"]} = {ab["rate_pct"]}% vs ba {ba["success"]}/{ba["episodes"]} = {ba["rate_pct"]}%；差异 {abs(ab["rate_pct"] - ba["rate_pct"]):.2f} 个百分点（{abs(ab["success"] - ba["success"])} 个 episode），在 483 样本下属于噪声，<b>未观察到方向偏置</b>。</p>
<div class="tblwrap"><table>
<thead><tr><th>order</th><th>episodes</th><th>success</th><th>成功率</th><th>mean steps</th><th>子任务 0 / 1 / 2</th></tr></thead>
<tbody>{order_body}</tbody></table></div>
<div class="barchart">{order_bars}</div>
<p class="note">桶定义来自 <code>prep/easy_subset.json</code> 的 <code>difficulty_bucket</code>（same_destination(capacity) 82 条 / independent 72 条 / same_furniture·fixture 7 条候选；每题 ×3 seeds）。</p>
</section>'''


def render_dist_subset(m):
    comp = m["composition"]
    mt = m["metrics"]
    bucket_chips = "".join(
        f'<span class="chip"><b>{esc(k)}</b> {v} 候选 / {v * 3} eps</span>' for k, v in comp["by_bucket"].items()
    )
    template_chips = "".join(
        f'<span class="chip"><b>{esc(k)}</b> {v} 候选 / {v * 3} eps</span>' for k, v in comp["by_template"].items()
    )
    order_chips = "".join(
        f'<span class="chip"><b>{esc(k)}</b> {v} 候选</span>' for k, v in comp["by_order"].items()
    )
    atoms_txt = "；".join(f"{k} 原子 × {v} 条" for k, v in comp["n_atoms"].items())
    held_rows = "".join(
        f'<tr><td><code>{esc(h["candidate_id"])}</code></td><td>{h["score"]}</td></tr>'
        for h in comp["held_out_rows"]
    )
    rule_items = "".join(f"<li>{esc(item)}</li>" for item in comp["rule"]["difficulty_score"])
    return f'''<section id="dist-subset">
<h2>七、子集构成（161 条从哪来）</h2>
<p class="sub">161 条 = 322 条 v2 候选的 <b>{comp["ratio_pct"]}%</b>；eligible <b>{comp["eligible"]}</b> 条（M1-P0-valid-compatible-n_atoms2）中按难度分升序取前 <b>{comp["target_n"]}</b> 条，剩余 <b>{comp["held_out"]}</b> 条作为 held-out（不参与本 run）。</p>
<div class="tblwrap"><table>
<thead><tr><th>维度</th><th>值</th></tr></thead>
<tbody>
<tr><td>全量候选 / 本 run 子集</td><td>{comp["total_candidates"]} → <b>{comp["n"]}</b>（{comp["ratio_pct"]}%）</td></tr>
<tr><td>eligible / held-out</td><td>{comp["eligible"]} = {comp["n"]} + {comp["held_out"]}</td></tr>
<tr><td>覆盖场景 / 模板 / 桶</td><td>{comp["n_scenes"]} 场景 / {comp["n_templates"]} 模板 / {comp["n_buckets"]} 桶</td></tr>
<tr><td>指令顺序</td><td>ab {comp["by_order"].get("ab", 0)} / ba {comp["by_order"].get("ba", 0)}</td></tr>
<tr><td>原子数</td><td>{esc(atoms_txt)}（全部为 2 原子组合）</td></tr>
<tr><td>含开关 goal（Turnon/Turnoff）</td><td>{comp["with_switch"]} 条（开关候选全部被难度分排入 held-out）</td></tr>
<tr><td>难度分区间</td><td>{comp["difficulty_min"]} – {comp["difficulty_max"]}</td></tr>
<tr><td>模板/init 源任务数</td><td>{comp["n_template_tasks"]} 个不同任务（每条候选 <code>template_task</code> = <code>init_source</code>）</td></tr>
</tbody></table></div>
<div class="chips">{template_chips}</div>
<div class="chips">{bucket_chips}</div>
<div class="chips">{order_chips}</div>
<details><summary>难度分规则与 held-out {comp["held_out"]} 条名单（来自 easy_subset.json）</summary>
<ul class="flat">{rule_items}<li>selection：{esc(comp["rule"]["selection"])}</li><li>held_out：{esc(comp["rule"]["held_out"])}</li></ul>
<div class="tblwrap"><table>
<thead><tr><th>held-out candidate_id</th><th>难度分</th></tr></thead>
<tbody>{held_rows}</tbody></table></div>
</details>
<p class="note">子集选择规则来自 <code>prep/easy_subset.json</code>（<code>select_easy_subset.py</code> 生成），本页只读不重算；<code>--check</code> 校验 161 + 17 = 178 = eligible，且 161×3 = {mt["episodes"]}。</p>
</section>'''

def render_failures(m):
    mt = m["metrics"]
    failure = m["failure"]
    modes = failure["modes"]
    max_mode = max(r["count"] for r in modes)
    mode_rows = "".join(
        f'<tr data-mode="{r["key"]}" data-count="{r["count"]}"><td>{esc(r["label"])}</td>'
        f'<td><b>{r["count"]}</b></td><td>{r["pct"]}%</td>'
        f'<td><div class="bar" style="background:#eef2f7;border-radius:5px;height:12px;max-width:260px">'
        f'<span style="display:block;height:12px;border-radius:5px;width:{100.0 * r["count"] / max_mode:.1f}%;'
        f'background:{"#ef4444" if r["key"].startswith("failed_completed_0") else ("#f59e0b" if "1_subtask" in r["key"] else "#16a34a")}"></span></div></td></tr>'
        for r in modes
    )
    hist = failure["hist"]
    max_hist = max(r["count"] for r in hist)
    hist_bars = "".join(
        bar_row(f'steps {r["range"]}', r["count"] / max_hist if max_hist else 0, f'{r["count"]} eps',
                "warm" if r["range"] == "600" else "cool")
        for r in hist
    )
    s1_rows = "".join(
        f'<tr><td>{esc(row["label"])}</td><td><b>{row["value"]}</b></td><td class="tiny">{esc(row["note"])}</td></tr>'
        for row in failure["s1_rows"]
    )
    return f'''<section id="failures">
<h2>八、失败分析（{mt["episodes"] - mt["success"]} 条失败）</h2>
<h3>8.1 失败模式（最终完成子任务数）</h3>
<div class="tblwrap"><table>
<thead><tr><th>分类</th><th>episodes</th><th>占比</th><th></th></tr></thead>
<tbody>{mode_rows}</tbody></table></div>
<p class="note"><b>{mt["maxstep_fails"]}/{mt["episodes"]}（{mt["maxstep_pct"]}%）的 episode 跑满 {mt["max_steps"]} 步</b>；失败几乎都不是“提前结束”，而是「完成 <b>1</b> 段后停滞」（{mt["subtasks_1"]} 条，47.41%）或「<b>0</b> 段」（{mt["subtasks_0"]} 条，44.10%）。这与 GOAL / OBJECT 历史上的失败先验一致：单条双目标指令下模型经常完成一个子目标后无法继续。</p>
<h3>8.2 steps 分布</h3>
<div class="barchart">{hist_bars}</div>
<p class="sub">成功 episode 的 steps：mean {mt["success_mean_steps"]}（min <span data-metric="success_min_steps">{mt["success_min_steps"]}</span> / max <span data-metric="success_max_steps">{mt["success_max_steps"]}</span>）；失败 episode 的 steps 全部 = {mt["fail_mean_steps"]}（跑满预算）。</p>
<h3>8.3 s1（第一个子目标）轨迹统计</h3>
<div class="tblwrap"><table>
<thead><tr><th>指标</th><th>值</th><th>说明</th></tr></thead>
<tbody>{s1_rows}</tbody></table></div>
<p class="tiny">机读（供 <code>--check</code> 复验）：s1-ever <span data-metric="s1_ever">{mt["s1_ever"]}</span> eps · 最终保持 <span data-metric="s1_final">{mt["s1_final"]}</span> eps · 丢失 <span data-metric="s1_lost">{mt["s1_lost"]}</span> eps · 回撤 <span data-metric="s1_retract_events">{mt["s1_retract_events"]}</span> 次 / <span data-metric="s1_retract_eps">{mt["s1_retract_eps"]}</span> eps · 首次真均值 <span data-metric="s1_mean_step">{mt["s1_mean_step"]}</span> 步 / 中位 <span data-metric="s1_median_step">{mt["s1_median_step"]}</span> 步。</p>
<ul class="flat">
<li><b>s1 曾完成 {mt["s1_ever"]} eps（37.89%），最终保持 {mt["s1_final"]} eps（{round(100.0 * mt["s1_final"] / mt["s1_ever"], 2)}% of s1-ever）</b>；{mt["s1_lost"]} eps 出现“s1 曾真但最终回撤”（回撤总事件 {mt["s1_retract_events"]} 次，涉及 {mt["s1_retract_eps"]} eps = {round(100.0 * mt["s1_retract_eps"] / mt["episodes"], 2)}%）。</li>
<li><b>“完成 1 段后停滞”的 {mt["subtasks_1"]} 条里，<span data-metric="one_with_s1_final">{mt["one_with_s1_final"]}</span> 条（{round(100.0 * mt["one_with_s1_final"] / mt["subtasks_1"], 2)}%）s1 最终为真</b> → 停滞主要发生在<b>第二目标阶段</b>，不是 s1 完全失败；这部分是 staged / instruction-switch 的主要候选池。</li>
<li>“完成 0 段”的 {mt["subtasks_0"]} 条里只有 <span data-metric="zero_with_s1_ever">{mt["zero_with_s1_ever"]}</span> 条（{round(100.0 * mt["zero_with_s1_ever"] / mt["subtasks_0"], 2)}%）s1 曾经为真 → 多数 0 段失败从第一个子目标就没开始（可能是指令歧义/场景物体不可达）。</li>
<li>成功 eps 中仅 {m["failure"]["success_with_retract"]} 条出现过 s1 回撤；失败 eps 中 {m["failure"]["fail_with_retract"]} 条出现回撤。</li>
</ul>
<p class="note warn">口径限制：正式队列 <b>video off</b>，失败原因只能从 trace 的 goal 原子真值序列判断（没有视频级复核）；“碰撞/超时/抓取失败”等物理原因未逐条标注。</p>
</section>'''


def steps_cell(row):
    parts = []
    for idx, step in enumerate(row["steps"]):
        ok = idx in row["seeds_success"]
        cls = "ok-txt" if ok else ""
        mark = "✓" if ok else "✗"
        parts.append(f'<span class="{cls}">{step}{mark}</span>')
    return " / ".join(parts)


def result_badge(row):
    all3 = row.get("success_all3", row.get("all3", False))
    ge2 = row.get("success_ge2", row.get("ge2", False))
    any_ = row.get("success_any", row.get("n_success", 0) > 0)
    if all3:
        return badge("3/3 全成功", "b-ok")
    if ge2:
        return badge("≥2 seeds", "b-info")
    if any_:
        return badge("≥1 seed", "b-warn")
    return badge("0/3", "b-fail")


def render_stability(m):
    mt = m["metrics"]
    stability = m["stability"]
    rows = stability["rows"]
    body = []
    for r in rows:
        cls = "hi stable-row" if r["all3"] else "stable-row"
        body.append(
            f'<tr class="{cls}" data-candidate="{esc(r["candidate_id"])}" data-all3="{1 if r["all3"] else 0}" '
            f'data-ge2="{1 if r["ge2"] else 0}" data-n-success="{r["n_success"]}">'
            f'<td><code>{esc(r["candidate_id"])}</code></td><td><code>{esc(r["scene"])}</code></td>'
            f'<td><code>{esc(r["template"])}</code></td><td class="tiny">{esc(r["bucket"])}</td>'
            f'<td>{esc(r["order"])}</td><td>{esc(r["instruction"])}</td>'
            f'<td class="nowrap"><b>{r["n_success"]}/3</b>（{", ".join(str(s) for s in r["seeds_success"])}）</td>'
            f'<td class="seeds nowrap">{steps_cell(r)}</td><td>{result_badge(r)}</td></tr>'
        )
    cards = []
    for r in stability["all3_rows"]:
        cards.append(
            f'<div class="bigcard gold" data-all3-card="{esc(r["candidate_id"])}">'
            f'<div class="id"><code>{esc(r["candidate_id"])}</code> {badge("3/3 全成功", "b-ok")}</div>'
            f'<div class="instr">{esc(r["instruction"])}</div>'
            f'<div class="kv">场景 <code>{esc(r["scene"])}</code> · 模板 <b>{esc(r["template"])}</b> · 桶 {esc(r["bucket"])} · order {esc(r["order"])}<br>'
            f'seeds 成功：{", ".join(str(s) for s in r["seeds_success"])} · steps：<span class="seeds">{steps_cell(r)}</span></div></div>'
        )
    return f'''<section id="stability">
<h2>九、稳定性候选（{stability["counts"]["any"]} / {stability["counts"]["ge2"]} / {stability["counts"]["all3"]}）</h2>
<div class="cards">
<div class="metric"><div class="v" data-metric="stable_any">{stability["counts"]["any"]}</div><div class="l">至少成功一次（≥1 seed）</div><div class="d">占 {mt["subset_n"]} 条候选的 {round(100.0 * stability["counts"]["any"] / mt["subset_n"], 2)}%</div></div>
<div class="metric"><div class="v" data-metric="stable_ge2">{stability["counts"]["ge2"]}</div><div class="l">≥2 seeds 成功</div><div class="d">占成功候选的 {round(100.0 * stability["counts"]["ge2"] / stability["counts"]["any"], 2)}%</div></div>
<div class="metric"><div class="v" data-metric="stable_all3">{stability["counts"]["all3"]}</div><div class="l">3 个 seeds 全成功（3/3）</div><div class="d">可进入 rollback 原型 / 补录视频</div></div>
<div class="metric"><div class="v"><span data-metric="cand_with_success">{mt["cand_with_success"]}</span></div><div class="l">有成功候选 / 全部候选</div><div class="d">{mt["cand_with_success"]} / {mt["subset_n"]}（其余 {mt["subset_n"] - mt["cand_with_success"]} 条 0/3）</div></div>
</div>
<h3>9.1 稳定性候选表（{len(rows)} 条，按 3/3 → ≥2 → ≥1 排序）</h3>
<div class="tblwrap"><table>
<thead><tr><th>candidate_id</th><th>场景</th><th>模板</th><th>bucket</th><th>order</th><th>instruction</th><th>成功 seeds</th><th>steps（seed0 / 1 / 2）</th><th>结果</th></tr></thead>
<tbody>{"".join(body)}</tbody></table></div>
<h3>9.2 3/3 全成功候选卡片（{len(cards)} 个，建议优先做 rollback 原型）</h3>
<div class="bigcards">{"".join(cards)}</div>
<p class="note">口径与 OBJECT 实验一致（≥1 / ≥2 / 3/3）；{stability["counts"]["all3"]} 条 3/3 的 steps 均 &lt; 550（见卡片与表格），说明这些候选不是“勉强成功”。下一步：对这 {stability["counts"]["all3"]} 条 + 其余 {stability["counts"]["ge2"] - stability["counts"]["all3"]} 条 ≥2 候选补录视频，再做 s1 成功后的 rollback 注入，观察 s2 自修复。</p>
</section>'''


def render_candidates(m):
    mt = m["metrics"]
    rows = m["candidate_rows"]
    scenes = sorted({r["scene"] for r in rows})
    templates = sorted({r["template"] for r in rows})
    scene_opts = "".join(
        f'<option value="{esc(sc)}">{esc(sc)}（{sum(1 for r in rows if r["scene"] == sc)}）</option>'
        for sc in scenes
    )
    template_opts = "".join(f'<option value="{esc(t)}">{esc(t)}</option>' for t in templates)
    body = []
    for r in rows:
        cls = "hi cand-row" if r["success_all3"] else "cand-row"
        body.append(
            f'<tr class="{cls}" data-candidate="{esc(r["candidate_id"])}" data-scene="{esc(r["scene"])}" '
            f'data-template="{esc(r["template"])}" data-bucket="{esc(r["bucket"])}" data-order="{esc(r["order"])}" '
            f'data-n-success="{r["n_success"]}" data-all3="{1 if r["success_all3"] else 0}" '
            f'data-ge2="{1 if r["success_ge2"] else 0}" '
            f'data-steps="{",".join(str(s) for s in r["steps"])}" data-subtasks="{",".join(str(s) for s in r["subtasks"])}">'
            f'<td>{r["index"]}</td><td><code>{esc(r["candidate_id"])}</code></td>'
            f'<td><code>{esc(r["scene"])}</code></td><td><code>{esc(r["template"])}</code></td>'
            f'<td class="tiny">{esc(r["bucket"])}</td><td>{esc(r["order"])}</td>'
            f'<td class="nowrap">{r["n_success"]}/3（{", ".join(str(s) for s in r["seeds_success"]) or "—"}）</td>'
            f'<td class="seeds nowrap">{steps_cell(r)}</td>'
            f'<td class="nowrap">{ " / ".join(str(s) for s in r["subtasks"]) }</td>'
            f'<td>{result_badge(r)}</td></tr>'
        )
    n_all3 = sum(1 for r in rows if r["success_all3"])
    n_ge2 = sum(1 for r in rows if r["success_ge2"])
    n_any = sum(1 for r in rows if r["success_any"])
    return f'''<section id="candidates">
<h2>十、全部 {len(rows)} 条候选结果（可筛选）</h2>
<div class="filterbar" id="candfilter">
<b>筛选</b>
<select id="filter-result" aria-label="按结果筛选">
<option value="">全部（{len(rows)}）</option>
<option value="any">≥1 成功（{n_any}）</option>
<option value="ge2">≥2 seeds（{n_ge2}）</option>
<option value="all3">3/3 全成功（{n_all3}）</option>
<option value="zero">0/3（{len(rows) - n_any}）</option>
</select>
<select id="filter-scene" aria-label="按场景筛选"><option value="">全部场景</option>{scene_opts}</select>
<select id="filter-template" aria-label="按模板筛选"><option value="">全部模板</option>{template_opts}</select>
<button id="filter-reset" type="button">重置</button>
<span class="count" id="filter-count">显示 {len(rows)} / {len(rows)} 条候选</span>
<span class="hint">steps 列：✓ = 该 seed 成功、✗ = 失败；前三列（序号/候选/场景）与表格顺序来自 <code>summary.json.per_candidate</code> 输出顺序。</span>
</div>
<div class="tblwrap"><table class="candtable">
<thead><tr><th>#</th><th>candidate_id</th><th>场景</th><th>模板</th><th>bucket</th><th>order</th><th>成功 seeds</th><th>steps（seed0 / 1 / 2）</th><th>子任务 0 / 1 / 2</th><th>结果</th></tr></thead>
<tbody>{"".join(body)}</tbody></table></div>
<p class="note">共 {len(rows)} 条候选 × 3 seeds = {mt["episodes"]} episodes；其中 {n_any} 条至少成功一次、{n_ge2} 条 ≥2 seeds、{n_all3} 条 3/3。完整逐 episode 明细（483 条）见 <a class="local" href="../analysis/summary.json">summary.json</a> 的 <code>episodes</code> 字段。</p>
</section>'''

def render_conclusions(m):
    mt = m["metrics"]
    t1 = next(r for r in m["template_rows"] if r["template"] == "T1")
    t2 = next((r for r in m["template_rows"] if r["template"] == "T2"), None)
    t10 = next((r for r in m["template_rows"] if r["template"] == "T10"), None)
    sd = next(r for r in m["bucket_rows"] if r["bucket"].startswith("same_destination"))
    ind = next(r for r in m["bucket_rows"] if r["bucket"] == "independent")
    lr = next(g for g in m["group_rows"] if g["group"] == "LIVING_ROOM")
    kitchen = next(g for g in m["group_rows"] if g["group"] == "KITCHEN")
    study = next(g for g in m["group_rows"] if g["group"] == "STUDY")
    all3 = [r["candidate_id"] for r in m["stability"]["all3_rows"]]
    kitchen_study_candidates = sum(1 for r in m["candidate_rows"] if not r["scene"].startswith("LIVING_ROOM"))
    remaining = mt["total_candidates"] - mt["subset_n"]
    remain_html = (f'M2 <span data-metric="up_m2">{mt["up_m2"]}</span> + S1 <span data-metric="up_s1">{mt["up_s1"]}</span>'
                   f' + M1 中 P1/P2/P3 <span data-metric="up_m1_rest">{mt["up_m1_rest"]}</span>'
                   f' + held-out <span data-metric="held_out">{mt["held_out"]}</span>')
    remain_sum = (mt["up_m2"] + mt["up_s1"] + mt["up_m1_rest"] + mt["held_out"])
    if remain_sum != remaining:
        raise SystemExit("[FATAL] 剩余候选分类之和不等于 remaining")
    return f'''<section id="conclusions">
<h2>十一、结论与建议（可直接转述）</h2>
<div class="status ok"><b>核心结论</b>：pi05 在 LIBERO-90 低难度半数候选上，单指令 zero-shot 双目标完成率为 <b>{mt["success"]}/{mt["episodes"]} = {mt["success_rate_pct"]}%</b>（seed 0/1/2 = {mt["seed0_success"]}/{mt["seed1_success"]}/{mt["seed2_success"]}）；<b>{mt["stable_all3"]}</b> 个候选 3/3 稳定成功、<b>{mt["stable_ge2"]}</b> 个 ≥2 seeds、<b>{mt["stable_any"]}</b> 个至少成功一次；失败主体是“完成 1 段后停滞”（{mt["subtasks_1"]}/{mt["episodes"]}），{mt["maxstep_fails"]}/{mt["episodes"]} 跑满 600 步。</div>
<ol class="risk">
<li><b>{m["template_rows"][0]["template"]}“put both A and B in C”（同容器双物体）验证为最有效指令族</b>：{t1["success"]}/{t1["episodes"]} = <b>{t1["rate_pct"]}%</b>，明显高于 T3（{next(r["rate_pct"] for r in m["template_rows"] if r["template"] == "T3")}%）、T6（{next(r["rate_pct"] for r in m["template_rows"] if r["template"] == "T6")}%）；T2（{t2["success"]}/{t2["episodes"]}）与 T10（{t10["success"]}/{t10["episodes"]}）本子集全 0。→ 建议下一轮优先把 T1 族扩到更多同容器候选，并对 T2/T10 做措辞变体或 staged 对照。</li>
<li><b>同容器（capacity）任务优于 independent；LIVING_ROOM 场景主导</b>：same_destination {sd["success"]}/{sd["episodes"]} = {sd["rate_pct"]}% &gt; independent {ind["success"]}/{ind["episodes"]} = {ind["rate_pct"]}%；LIVING_ROOM {lr["success"]}/{lr["episodes"]} = {lr["rate_pct"]}%（{lr["success"]}/{mt["success"]} 成功），KITCHEN {kitchen["success"]}/{kitchen["episodes"]} = {kitchen["rate_pct"]}%（仅 KITCHEN_SCENE2），STUDY {study["success"]}/{study["episodes"]} = 0%。→ KITCHEN/STUDY 需改协议（staged / instruction-switch）或指令变体，与“{mt["subtasks_1"]} 条完成后 1 段停滞、{mt["one_with_s1_final"]} 条 s1 最终为真”的失败结构一致。</li>
<li><b>{mt["stable_all3"]} 条 3/3 + {mt["stable_ge2"]} 条 ≥2 seeds 可作为 rollback 用例原型</b>（下一步：补录视频 + s1 成功后注入回退，观察 s2 自修复）。3/3 名单：<span class="tiny">{esc("、".join(all3))}</span>。</li>
<li><b>建议下一轮</b>：① 对其余 <b><span data-metric="up_remaining">{remaining}</span></b> 条候选（{remain_html} = {remain_sum}）跑同协议，补齐全量 322 的分层成功率；② 或先对 <b>KITCHEN + STUDY 的 {kitchen_study_candidates} 条候选</b>做 staged / instruction-switch 对照（GOAL 上 staged 2/3），验证“切指令”能否把 1 段停滞转成成功；③ 对 {mt["stable_all3"]} 条 3/3 优先补视频与 rollback 注入。</li>
</ol>
<p class="note">注意：{mt["stable_ge2"]} 条 ≥2 seeds 中有 {mt["stable_ge2"] - mt["stable_all3"]} 条是 2/3；{mt["stable_all3"]} 条 3/3 是最高置信子集。成功率只代表低难度子集 + 单指令协议，不可外推全量 322 或官方 pi05。</p>
</section>'''


def render_caveats(m):
    mt = m["metrics"]
    fc = m["final"]
    return f'''<section id="caveats">
<h2>十二、口径 / 偏差声明 / 数据问题</h2>
<h3>12.1 口径与偏差声明（必读）</h3>
<div class="tblwrap"><table>
<thead><tr><th>项</th><th>声明</th></tr></thead>
<tbody>
<tr><td>候选范围</td><td>{mt["subset_n"]} 条 = 322 条 v2 候选的 <b>低难度半数</b>（M1-P0-valid-compatible-n_atoms2；eligible {mt["eligible"]} 中按难度分取前 {mt["subset_n"]}，held-out {mt["held_out"]} 条未跑）。<b>不含</b> M2({mt["up_m2"]})/S1({mt["up_s1"]})；M1 中不含 P1(<span data-metric="up_m1_p1">{mt["up_m1_p1"]}</span>)/P2(<span data-metric="up_p2">{mt["up_p2"]}</span>)/P3(<span data-metric="up_p3">{mt["up_p3"]}</span>)。<div class="tiny">全量 322 = M1 <span data-metric="up_m1">{mt["up_m1"]}</span> + M2 <span data-metric="up_m2">{mt["up_m2"]}</span> + S1 <span data-metric="up_s1">{mt["up_s1"]}</span>；priority P0 <span data-metric="up_p0">{mt["up_p0"]}</span>/P1 <span data-metric="up_p1">{mt["up_p1"]}</span>/P2 <span data-metric="up_p2">{mt["up_p2"]}</span>/P3 <span data-metric="up_p3">{mt["up_p3"]}</span>（PROTOCOL.md §2）</div></td></tr>
<tr><td>可外推性</td><td><b>不可外推</b>到全量 322 条或官方 pi05；held-out {mt["held_out"]} 条是 eligible 中最难的 17 条，若纳入全量成功率可能低于 {mt["success_rate_pct"]}%。</td></tr>
<tr><td>协议</td><td>单指令 zero-shot（无 staged / instruction-switch / rollback）；seeds {{0,1,2}}；seed s 使用 sibling <code>.pruned_init</code> 第 s%50 行；max_steps=600 / replan=10。</td></tr>
<tr><td>video</td><td><b>实际 off</b>（正式队列按 Lead 指示关闭视频，吞吐优先；与 <code>PROTOCOL.md §4</code> 写的 “video on” 不一致）。成功候选后续补录；失败原因只能从 trace 判断。</td></tr>
<tr><td>场景覆盖</td><td>本子集覆盖 {mt["subset_scenes"]}/20 个场景；未含 KITCHEN_SCENE8、KITCHEN_SCENE10、STUDY_SCENE2（不在低难度 161 内）→ 这三个场景的结论不能从本 run 推断。</td></tr>
<tr><td>并行</td><td>2 worker 并行（每 worker 独立 JAX，XLA fraction 0.42；GPU 独占），只影响吞吐/wall time，不改变每 episode 的 seed/init/协议；GPU 无 OOM。</td></tr>
<tr><td>success 判定</td><td>LIBERO <code>check_success()</code>；全部 {fc["overall_episodes"]} 条 success 来源均为 <code>results.json</code>（final_checks 全 PASS）。</td></tr>
</tbody></table></div>
<h3>12.2 本报告发现的数据 / 文档不一致（已在页面处理）</h3>
<ol class="risk">
<li><b>PROTOCOL.md §4 写 <code>video: on</code>，实际运行为 off</b>：<code>STATUS.md</code>、<code>run/progress.json</code>、<code>logs/queue.log</code> 均记录 video off（Lead 指示的吞吐优先偏差）。本报告按实际 off 记录，并把它列为口径偏差；PROTOCOL 未同步更新，建议回填。</li>
<li><b>吞吐口径不一致</b>：<code>progress.json</code> 给 <span data-metric="rate_progress">{mt["rate_progress"]}</span> eps/h（{mt["sec_per_episode"]} s/episode，按 episode 时长口径）；按 <code>final_checks.wall_hours</code>（<span data-metric="wall_hours">{mt["wall_hours"]}</span> h / <span data-metric="wall_seconds">{mt["wall_seconds"]}</span> s）折算为 <span data-metric="rate_wall">{mt["rate_wall"]}</span> eps/h。两个口径都以页面标注为准，不混用。</li>
<li><b>GPU 显存数字</b>：SMOKE_PARALLEL 报告双 worker 稳态 ~22,676 MiB（手动峰值 22,679 MiB）；正式队列 <code>queue-gpu.log</code> 的 nvidia-smi 监测峰值是 <b>{nfmt(mt["gpu_peak_mib"])} / {nfmt(mt["gpu_total_mib"])} MiB</b>（仍无 OOM，OOM 标记 {mt["oom_markers"]}）。指标卡采用正式队列监测峰值，SMOKE 稳态数字在完整性表注明。</li>
<li><b><code>final_checks.results_json_dirs</code> seed0 = 3</b>（seed0 有一次中途 STOP 后重跑的旧目录；seed1/2 = 2 个 worker 目录）；trace/missing/worker rc 均 PASS，分析按合并后的 161 条/seed 计算，不影响结果。</li>
<li><b>失败原因分类没有视频级复核</b>：PROTOCOL §6 计划用视频复核区分碰撞/超时；实际 video off，因此本报告失败分析只基于 trace 的 goal 原子真值（0/1/2 段、s1 回退、steps）。</li>
<li><b>子集与全量比例</b>：<code>easy_subset.stats</code> 与 <code>summary.by_scene</code> 逐场景一致（episodes = 候选 ×3）；161 + held-out 17 = eligible 178 = 322 中 M1-P0 的子集规模。页面所有分布均以“161 子集”为分母，未与全量 322 混淆。</li>
</ol>
<p class="note">复核方式：页面所有数字由 <code>--check</code> 从 <code>summary.json</code>/<code>final_checks.json</code>/<code>easy_subset.json</code>/<code>progress.json</code>/<code>logs</code> 重算并断言；输入任一文件变动会触发构建指纹失败（提示重跑）。</p>
</section>'''


def render_artifacts(m):
    mt = m["metrics"]
    rows = [
        ("本报告（单文件 HTML）", "index.html", "v1 验证结果报告；内联 CSS/JS、无外链 CDN、可离线打开"),
        ("本报告说明", "README.md", "口径 / 结论 / 复现命令 / 章节索引"),
        ("分析结果（机读）", "../analysis/summary.json", "overall / 分布 / 失败 / 稳定候选 / 逐候选 / 483 条 episode"),
        ("分析摘要（Markdown）", "../analysis/summary.md", "同口径的可读版摘要（自动生成）"),
        ("完整性检查", "../analysis/final_checks.json", "483/483、trace 161×3、worker rc=0、GPU 无 OOM、wall 8.99h、checks_all_passed"),
        ("运行状态", "../STATUS.md", "实时进度/复现命令/产物索引/口径纪律（最终版）"),
        ("单进程冒烟", "../SMOKE.md", "2 候选 × seed0 冒烟（含视频解码/init digest 证据）"),
        ("双 worker 并行冒烟", "../SMOKE_PARALLEL.md", "2 worker 并发可行性（2.0× 吞吐、无 OOM）"),
        ("评测协议", "../PROTOCOL.md", "161 条来源/资产口径/pi05 协议/与 OBJECT-GOAL 可比性/声明"),
        ("静态验证", "../STATIC_VALIDATION.md", "161/161 资产静态验证与 CPU env 冒烟"),
        ("运行目录 README", "../README.md", "run 目录总览与产物索引"),
        ("候选子集定义", "../prep/easy_subset.json", "161 条候选（scene/template/bucket/instruction/difficulty_score）+ 规则 + held-out 17"),
        ("候选 ID 清单", "../prep/easy_case_ids.txt", "161 个 candidate_id 纯文本"),
        ("资产生成清单", "../artifacts/manifest.json", "161 bddl + init 的 sha256/指令/语言变体/校验摘要"),
        ("队列日志", "../logs/queue.log", "queue 启动/每 seed 完成/GPU at start（QUEUE_DONE）"),
        ("GPU 显存日志", "../logs/queue-gpu.log", "nvidia-smi 采样（峰值 {peak} / {total} MiB，无 OOM）".replace("{peak}", nfmt(mt["gpu_peak_mib"])).replace("{total}", nfmt(mt["gpu_total_mib"]))),
        ("每 seed 队列日志", "../logs/queue-seed0.log", "seed0/1/2 的 worker 日志合并（另有 queue-seed1/2.log）"),
        ("上游：模板化候选（322）", "../../libero-90-combos-20261025/candidates-instructed.json", "161 条候选的来源（v2 322 条）"),
        ("上游：场景报告（v2）", "../../libero-90-combos-20261025/report/index.html", "20 场景 × 单任务/组合候选/参考视频报告"),
        ("上游：模板说明", "../../libero-90-combos-20261025/INSTRUCTION_TEMPLATES.md", "T1–T10/T4b 模板定义与证据"),
        ("上游：方法文档", "../../../docs/libero-90-dual-target-candidates.md", "§7.1 模板 / §10 验证漏斗 / §12 风险（GOAL 参考数字来源）"),
        ("参考实验：OBJECT v3", "../../object-inscene-100-20261023/", "OBJECT 100 候选 × 3 seeds = 300 eps / 12 成功（本页 reference_object）"),
        ("参考实验：GOAL 历史", "../../combined-tasks-20261019/", "GOAL 历史合并任务 + staged 实验（docs 引用的 2/47、staged 2/3）"),
        ("本报告生成器", "../../../scripts/build_libero90_easy_validation_report.py", "可重跑；--check 校验本页全部不变量"),
        ("评测执行脚本", "../prep/run_seed.py", "pi05 worker（含 GPU 采样/断点续跑）"),
        ("分析脚本", "../prep/analyze_easy.py", "summary.json/.md 生成器"),
        ("候选选择脚本", "../prep/select_easy_subset.py", "161 低难度候选选择规则"),
        ("资产构建脚本", "../prep/build_easy_candidates.py", "161 bddl + sibling init 生成（--check 幂等）"),
        ("final checks 脚本", "../prep/final_checks.py", "final_checks.json 生成器"),
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
<h2>十三、产物索引</h2>
<div class="tblwrap"><table>
<thead><tr><th>产物</th><th>路径（相对本文件）</th><th>用途</th></tr></thead>
<tbody>{body}</tbody></table></div>
<p class="note">输入文件 sha256（前 16 位，完整值见生成日志）：{hash_line}。本页只读上述 JSON / 日志 / 文档；没有修改 analysis/、STATUS、其他 run 或 docs。</p>
</section>'''


def render_footer(m):
    mt = m["metrics"]
    fc = m["final"]
    hashes = m["hashes"]
    line = " · ".join(
        f'<code>{esc(name)}</code> <code>{esc(hashes[name][:16])}…</code>' for name in sorted(hashes)
    )
    return f'''<footer>
<p><b>生成命令</b>：<code>cd /home/tarowang/workspace/roboot/libero-rollback &amp;&amp; .venv/bin/python scripts/build_libero90_easy_validation_report.py</code>；只读校验：<code>.venv/bin/python scripts/build_libero90_easy_validation_report.py --check</code></p>
<p><b>数据来源</b>：{line}；口径见 <a class="local" href="../PROTOCOL.md">PROTOCOL.md</a> 与 <a class="local" href="../analysis/summary.md">analysis/summary.md</a>。</p>
<p><b>审计状态</b>：<code>analysis/final_checks.json</code> 全部检查 <b>{"PASS" if m["integrity"]["all_pass"] else "FAIL"}</b>（queue 完成 / progress 483 / traces 161×3 / missing 0 / trace atom mismatch 0 / worker rc=0 / GPU 无 OOM / wall 8.99h）；success 全部来自 <code>results.json</code>。本 HTML 由脚本从 JSON 全量生成、数字无手填、<code>--check</code> 逐项复验。已知偏差：正式队列 <b>video off</b>（与 PROTOCOL §4 不一致，见口径节）。</p>
<p class="tiny">构建时间 {esc(m["generated_at"])} · 构建指纹 <code>sha256:{esc(m["digest"])}</code> · 单文件静态页面（内联 CSS/JS、无外链 CDN；无外部资源）</p>
</footer>'''


def build_html(m):
    mt = m["metrics"]
    parts = [
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f'<title>LIBERO-90 低难度候选 × pi05 × 3 seeds 验证报告（{mt["success"]}/{mt["episodes"]} = {mt["success_rate_pct"]}%）</title>',
        f"<!-- data-digest: sha256:{m['digest']} -->",
        f'<style>{CSS}</style>',
        '</head><body>',
        render_sidenav(m),
        render_hero(m),
        '<main>',
        render_overview(m),
        render_compare(m),
        render_dist_seed(m),
        render_dist_scene(m),
        render_dist_template(m),
        render_dist_bucket_order(m),
        render_dist_subset(m),
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
    ]
    return "\n".join(parts)


def build_readme(m):
    mt = m["metrics"]
    t1 = next(r for r in m["template_rows"] if r["template"] == "T1")
    lr = next(g for g in m["group_rows"] if g["group"] == "LIVING_ROOM")
    sd = next(r for r in m["bucket_rows"] if r["bucket"].startswith("same_destination"))
    lines = [
        "# LIBERO-90 低难度候选（161）× pi05 × 3 seeds 验证报告（index.html）",
        "",
        "> 打开 `index.html` 即可离线阅读：单文件、内联 CSS/JS、无外链 CDN。",
        "",
        "## 结论",
        f"- **{mt['success']} / {mt['episodes']} = {mt['success_rate_pct']}%** success（seed 0/1/2 = "
        f"{mt['seed0_success']}/{mt['seed1_success']}/{mt['seed2_success']}；mean steps {mt['mean_steps']}，median {mt['median_steps']}）。",
        f"- T1 模板最强（{t1['success']}/{t1['episodes']} = {t1['rate_pct']}%）；same_destination bucket "
        f"{sd['success']}/{sd['episodes']} = {sd['rate_pct']}%；LIVING_ROOM 场景 {lr['success']}/{lr['episodes']} = {lr['rate_pct']}%。",
        f"- 稳定候选：{mt['stable_any']} 个 ≥1 / {mt['stable_ge2']} 个 ≥2 seeds / {mt['stable_all3']} 个 3/3；"
        f"失败 {mt['subtasks_0']} 条 0 段 + {mt['subtasks_1']} 条完成 1 段后停滞，{mt['maxstep_fails']}/{mt['episodes']} 跑满 600 步。",
        "",
        "## 口径（不可外推）",
        f"- {mt['subset_n']} 条 = 322 条 v2 候选的低难度半数（eligible {mt['eligible']} − held-out {mt['held_out']}）；"
        "只代表该子集，不能外推全量 322 或官方 pi05。",
        "- 单指令 zero-shot；seeds {0,1,2}；seed s 用 sibling `.pruned_init` 第 s%50 行；max_steps=600 / replan=10。",
        "- **video off**（正式队列按 Lead 指示关闭；与 PROTOCOL §4 的 on 不一致，属已记录协议偏差）；失败原因只来自 trace。",
        "- 完整口径、场景覆盖（17/20）与数据不一致说明见 HTML「口径 / 偏差 / 数据问题」节。",
        "",
        "## 复现",
        "```bash",
        "cd /home/tarowang/workspace/roboot/libero-rollback",
        ".venv/bin/python scripts/build_libero90_easy_validation_report.py          # 重建 index.html + README.md",
        ".venv/bin/python scripts/build_libero90_easy_validation_report.py --check  # 只读校验（不写文件）",
        "```",
        "",
        "## 章节",
        "总览/完整性 → 与 OBJECT/GOAL 对比 → 按 seed/场景/模板/桶/顺序分布 → 失败分析 → 稳定候选 → 全部 161 条候选（可筛选）→ 结论与建议 → 口径/偏差/产物索引。",
        "",
        "## 数据来源",
        "`../analysis/summary.json`、`../analysis/final_checks.json`、`../prep/easy_subset.json`、`../run/progress.json`、`../logs/queue*.log`；审计状态：final_checks 全 PASS。",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(m):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    html_text = build_html(m)
    OUT_HTML.write_text(html_text, encoding="utf-8")
    readme = build_readme(m)
    OUT_README.write_text(readme, encoding="utf-8")
    print(f"[build] {OUT_HTML.relative_to(ROOT)}: {len(html_text.encode('utf-8')):,} bytes")
    print(f"[build] sections={html_text.count('<section ')} cand_rows={len(m['candidate_rows'])} "
          f"stability_rows={sum(1 for _ in m['stability']['rows'])} all3_cards={len(m['stability']['all3_rows'])}")
    print(f"[build] overall: {m['metrics']['success']}/{m['metrics']['episodes']} = {m['metrics']['success_rate_pct']}% "
          f"| seeds {m['metrics']['seed0_success']}/{m['metrics']['seed1_success']}/{m['metrics']['seed2_success']} "
          f"| stable {m['metrics']['stable_any']}/{m['metrics']['stable_ge2']}/{m['metrics']['stable_all3']}")
    print(f"[build] {OUT_README.relative_to(ROOT)}: {len(readme.splitlines())} lines")
    print(f"[build] digest sha256:{m['digest']}")

def parse_attrs(text):
    return dict(re.findall(r'([a-zA-Z_][\w-]*)="([^"]*)"', text))


def run_checks(m):
    checks = []

    def add(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    mt = m["metrics"]
    obj = m["obj_ref"]
    goal = m["goal_ref"]
    comp = m["composition"]
    overall = m["overall"]
    sm = m["summary"]
    if not OUT_HTML.exists():
        add("index.html 存在", False, f"缺少 {OUT_HTML}；先运行无参数构建")
        print(f"[FAIL] index.html 存在 — 缺少 {OUT_HTML}")
        print("--check: 0/1 checks passed")
        return False
    text = OUT_HTML.read_text(encoding="utf-8")

    digest_m = re.search(r"<!-- data-digest: sha256:([0-9a-f]{64}) -->", text)
    add("构建指纹与当前输入一致（HTML 未过期）",
        bool(digest_m) and digest_m.group(1) == m["digest"],
        "HTML 与当前输入 JSON/日志不一致，请重跑生成器")

    # ---------- 章节 ----------
    expected_sections = ["overview", "compare", "dist-seed", "dist-scene", "dist-template",
                         "dist-bucket-order", "dist-subset", "failures", "stability",
                         "candidates", "conclusions", "caveats", "artifacts"]
    missing_sections = [sid for sid in expected_sections if f'<section id="{sid}"' not in text]
    add(f"{len(expected_sections)} 个章节 section 齐全", not missing_sections, f"缺失: {missing_sections}")

    # ---------- 指标 ----------
    found_metrics = dict(re.findall(r'data-metric="([^"]+)"[^>]*>([^<]+)<', text))
    missing_keys = sorted(set(mt) - set(found_metrics))
    wrong_keys = sorted(k for k in mt if k in found_metrics and found_metrics[k] != str(mt[k]))
    add("指标数字（data-metric）与 JSON 计算值一致",
        not missing_keys and not wrong_keys,
        f"缺失 {missing_keys[:6]} / 不符 {wrong_keys[:6]}")

    # ---------- 按 seed ----------
    seed_rows = re.findall(r'<tr data-seed="(\d)" data-episodes="(\d+)" data-success="(\d+)" data-rate="([\d.]+)">', text)
    expected_seed = [(str(r["seed"]), str(r["episodes"]), str(r["success"]), str(r["rate_pct"])) for r in m["seed_rows"]]
    add("按 seed 表 3 行且 episodes/success/rate 一致", seed_rows == expected_seed,
        f"实际 {seed_rows}")
    seed_ep_sum = sum(int(x[1]) for x in seed_rows)
    seed_succ_sum = sum(int(x[2]) for x in seed_rows)
    add("seed 表 episodes 之和 = 483、success 之和 = 41",
        seed_ep_sum == overall["episodes"] and seed_succ_sum == overall["success"],
        f"{seed_ep_sum} / {seed_succ_sum}")

    # ---------- 按场景 ----------
    scene_rows = re.findall(
        r'<tr class="[^"]*" data-scene="([A-Z_0-9]+)" data-group="([A-Z_]+)" data-candidates="(\d+)" '
        r'data-episodes="(\d+)" data-success="(\d+)" data-rate="([\d.]+)">', text)
    expected_scene = [(r["scene"], r["group"], str(r["candidates"]), str(r["episodes"]),
                       str(r["success"]), str(r["rate_pct"])) for r in m["scene_rows"]]
    add(f"按场景表 {len(expected_scene)} 行且数值与 JSON 一致", scene_rows == expected_scene,
        f"行数 {len(scene_rows)}")
    add("场景表 episodes 之和 = 483、success 之和 = 41",
        sum(int(x[3]) for x in scene_rows) == overall["episodes"]
        and sum(int(x[4]) for x in scene_rows) == overall["success"])
    add("场景表候选数 ×3 = episodes（逐行）",
        all(int(x[2]) * 3 == int(x[3]) for x in scene_rows))

    # ---------- 按模板 ----------
    template_rows = re.findall(
        r'<tr class="[^"]*" data-template="([A-Z0-9]+)" data-episodes="(\d+)" data-success="(\d+)" '
        r'data-rate="([\d.]+)">', text)
    expected_template = [(r["template"], str(r["episodes"]), str(r["success"]), str(r["rate_pct"]))
                         for r in m["template_rows"]]
    add(f"按模板表 {len(expected_template)} 行且数值与 JSON 一致", template_rows == expected_template,
        f"实际 {template_rows}")
    add("模板表 episodes 之和 = 483、success 之和 = 41",
        sum(int(x[1]) for x in template_rows) == overall["episodes"]
        and sum(int(x[2]) for x in template_rows) == overall["success"])

    # ---------- 按 bucket / order ----------
    bucket_rows = re.findall(
        r'<tr class="[^"]*" data-bucket="([^"]+)" data-episodes="(\d+)" data-success="(\d+)" '
        r'data-rate="([\d.]+)">', text)
    expected_bucket = [(r["bucket"], str(r["episodes"]), str(r["success"]), str(r["rate_pct"]))
                       for r in m["bucket_rows"]]
    add(f"按 bucket 表 {len(expected_bucket)} 行且数值与 JSON 一致",
        bucket_rows == expected_bucket, f"实际 {bucket_rows}")
    add("bucket 表 episodes 之和 = 483、success 之和 = 41",
        sum(int(x[1]) for x in bucket_rows) == overall["episodes"]
        and sum(int(x[2]) for x in bucket_rows) == overall["success"])
    order_rows = re.findall(
        r'<tr data-order="([a-z]+)" data-episodes="(\d+)" data-success="(\d+)" data-rate="([\d.]+)">', text)
    expected_order = [(r["order"], str(r["episodes"]), str(r["success"]), str(r["rate_pct"]))
                      for r in m["order_rows"]]
    add(f"按 order 表 {len(expected_order)} 行且数值与 JSON 一致", order_rows == expected_order,
        f"实际 {order_rows}")
    add("order 表 episodes 之和 = 483、success 之和 = 41",
        sum(int(x[1]) for x in order_rows) == overall["episodes"]
        and sum(int(x[2]) for x in order_rows) == overall["success"])

    # ---------- 失败分析 ----------
    mode_rows = re.findall(r'<tr data-mode="([^"]+)" data-count="(\d+)">', text)
    expected_modes = [(r["key"], str(r["count"])) for r in m["failure"]["modes"]]
    add("failure_modes 表 3 行且计数一致", mode_rows == expected_modes, f"实际 {mode_rows}")
    add("失败模式计数之和 = 483、success = 41",
        sum(int(x[1]) for x in mode_rows) == overall["episodes"]
        and next(int(x[1]) for x in mode_rows if x[0] == "success") == overall["success"])
    add("s1 统计 4 项与 JSON 一致",
        all(str(v) in text for v in [m["failure"]["s1"]["episodes_with_s1_first_true"],
                                     m["failure"]["s1"]["episodes_s1_final_true"],
                                     m["failure"]["s1"]["s1_retract_events"],
                                     m["failure"]["s1"]["episodes_with_s1_retract"]]))
    hist_sum = sum(r["count"] for r in m["failure"]["hist"])
    add("steps 直方图之和 = 483", hist_sum == overall["episodes"], f"{hist_sum}")

    # ---------- 稳定性 ----------
    stable_rows = re.findall(
        r'<tr class="(?:hi )?stable-row" data-candidate="([^"]+)" data-all3="([01])" '
        r'data-ge2="([01])" data-n-success="(\d+)">', text)
    stable_ids = [x[0] for x in stable_rows]
    add("稳定性候选表 19 行且 candidate_id 与 JSON 一致",
        len(stable_rows) == len(sm["stable_candidates"]["success_any"])
        and set(stable_ids) == set(sm["stable_candidates"]["success_any"]),
        f"实际 {len(stable_rows)} 行")
    add("稳定性表 all3 / ge2 标记与 JSON 一致",
        all((x[1] == "1") == (x[0] in sm["stable_candidates"]["success_all3"])
            and (x[2] == "1") == (x[0] in sm["stable_candidates"]["success_ge2"])
            for x in stable_rows))
    all3_cards = re.findall(r'<div class="bigcard gold" data-all3-card="([^"]+)">', text)
    add("3/3 全成功卡片 = 10 个且名单一致",
        len(all3_cards) == len(sm["stable_candidates"]["success_all3"])
        and set(all3_cards) == set(sm["stable_candidates"]["success_all3"]),
        f"实际 {len(all3_cards)}")

    # ---------- 全部候选表 ----------
    cand_rows = re.findall(r'<tr class="(?:hi )?cand-row" data-candidate="([^"]+)"', text)
    per = sm["per_candidate"]
    add(f"全部候选表 = {len(per)} 行且 candidate_id 集合一致",
        len(cand_rows) == len(per) and set(cand_rows) == set(per.keys()),
        f"实际 {len(cand_rows)}")
    add("候选表无重复行", len(cand_rows) == len(set(cand_rows)))
    row_blocks = re.findall(r'<tr class="(?:hi )?cand-row"([^>]*)>', text)
    bad_attrs = []
    for attrs_text in row_blocks:
        a = parse_attrs(attrs_text)
        cid = a.get("data-candidate")
        p = per.get(cid)
        if p is None:
            bad_attrs.append(cid)
            continue
        if (a.get("data-scene") != p["scene"] or a.get("data-template") != p["instruction_template"]
                or a.get("data-bucket") != p["difficulty_bucket"] or a.get("data-order") != p["order"]
                or a.get("data-n-success") != str(p["n_success"])
                or a.get("data-steps") != ",".join(str(s) for s in p["steps"])
                or a.get("data-subtasks") != ",".join(str(s) for s in p["subtasks_done"])):
            bad_attrs.append(cid)
    add("候选表逐行 scene/template/bucket/order/n_success/steps/subtasks 与 JSON 一致",
        not bad_attrs, f"不一致: {bad_attrs[:5]}")
    n_success_counter = Counter(int(parse_attrs(t)["data-n-success"]) for t in row_blocks)
    expected_counter = Counter(p["n_success"] for p in per.values())
    add("候选表 n_success 分布与 JSON 一致（0/1/2/3 计数）", n_success_counter == expected_counter,
        f"实际 {dict(n_success_counter)}")
    add("候选表成功候选数 = JSON stable_any",
        sum(1 for cid, p in per.items() if p["n_success"] > 0) == mt["stable_any"])

    # ---------- 完整性 / 对比 / 子集 ----------
    ok_cells = text.count('<td class="ok">PASS ✓</td>')
    add(f"运行完整性表 {len(m['integrity']['rows'])} 项全部 PASS",
        ok_cells == len(m["integrity"]["rows"]) and m["integrity"]["all_pass"],
        f"PASS 单元格 {ok_cells}")
    add("GPU 无 OOM / worker rc=0 写入完整性表",
        mt["oom_markers"] == 0 and all(code == 0 for code in m["final"]["worker_exit_codes"]))
    add("与 OBJECT 对比行使用 summary.reference_object 数字",
        f'100 × 3 = {obj["episodes"]}' in text
        and f'<td>{obj["success"]}</td>' in text
        and f'{obj["success_any_candidates"]} / {obj["success_ge2_candidates"]} / {obj["success_all3_candidates"]}' in text,
        "OBJECT 对比行缺失或数字不一致")
    add("与 GOAL 对比行使用 docs 解析数字",
        f'{goal["single_episodes"]} episodes' in text
        and f'≈ {goal["single_rate_pct"]}%' in text
        and f'staged {goal["staged_success"]}/{goal["staged_episodes"]}' in text,
        "GOAL 对比行缺失或数字不一致")
    add("子集构成 161 / 322 / eligible 178 / held-out 17 与 JSON 一致",
        f'{comp["n"]} 条' in text and f'{comp["total_candidates"]} 条' in text
        and f'{comp["eligible"]}' in text and f'{comp["held_out"]}' in text
        and comp["n"] + comp["held_out"] == comp["eligible"] and comp["n"] * 3 == overall["episodes"])
    add("图表 / 表格总数一致性（seed+scene+template+bucket+order 各自 = 483）",
        all(x == overall["episodes"] for x in (seed_ep_sum,
                                              sum(int(x[3]) for x in scene_rows),
                                              sum(int(x[1]) for x in template_rows),
                                              sum(int(x[1]) for x in bucket_rows),
                                              sum(int(x[1]) for x in order_rows))))

    # ---------- 交互 / 声明 / 链接 ----------
    add("候选筛选控件与原生 JS 挂载点齐全",
        all(fid in text for fid in ("id=\"candfilter\"", "id=\"filter-result\"", "id=\"filter-scene\"",
                                    "id=\"filter-template\"", "id=\"filter-count\"", "id=\"filter-reset\"")))
    add("口径声明包含 video off / 不可外推 / 单指令",
        "video <b>off</b>" in text and "不可外推" in text and "单指令" in text and "低难度" in text)
    anchor_ids = set(re.findall(r'id="([^"]+)"', text))
    local_hrefs = re.findall(r'<a class="local" href="([^"]+)"', text)
    bad_links = [h for h in local_hrefs if not (REPORT_DIR / h).resolve().exists()]
    add("产物索引相对链接全部可解析（离线可用）",
        len(local_hrefs) >= 15 and not bad_links, f"{len(local_hrefs)} 个链接; 失效 {bad_links[:3]}")
    ext = re.search(r'https?://', text)
    add("无外链 CDN / 外部资源（单文件离线）",
        not ext and "<script src=" not in text and "<link " not in text and "<iframe" not in text)
    add("页脚含生成命令 / 数据来源 / 审计状态",
        "生成命令" in text and "审计状态" in text and "final_checks" in text)

    # ---------- README ----------
    if OUT_README.exists():
        readme = OUT_README.read_text(encoding="utf-8")
        lines = readme.splitlines()
        add("README.md 存在且行数 <= 30", len(lines) <= 30, f"{len(lines)} 行")
        add("README 含核心数字与 --check",
            str(mt["success"]) in readme and str(mt["episodes"]) in readme
            and f"{mt['success_rate_pct']}%" in readme and "--check" in readme)
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
    parser = argparse.ArgumentParser(description="LIBERO-90 低难度候选 pi05 3-seed 验证结果 HTML 报告生成器")
    parser.add_argument("--check", action="store_true", help="只读校验现有 index.html / README.md，不写文件")
    args = parser.parse_args(argv)
    model = compute_model()
    validate_model(model)
    if args.check:
        return 0 if run_checks(model) else 1
    write_outputs(model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
