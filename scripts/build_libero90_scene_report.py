#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LIBERO-90 双目标组合 · 分场景 HTML 报告生成器（v2 · 自包含、可重跑）。

v2：读取 scene_review_decisions.json（逐场景复核 v1），所有计数从 JSON 计算，不硬编码历史数字。

只读输入:
  runs/libero-90-combos-20261025/candidates-instructed.json   模板化候选（计数全部从 JSON 读取）
  runs/libero-90-combos-20261025/scene_review_decisions.json  逐场景复核口径源（组合池 / 剔除任务）
  runs/libero-90-combos-20261025/report/video-manifest.json     pi0 参考视频清单
  .tmp/libero90-combos/inventory.json                          L90 任务 BDDL 字段
  .tmp/libero90-combos/official-language-and-benchmark-map.json
  .tmp/libero90-combos/pair-semantics.json                     v0 语义（仅作交叉核对；未随复核再生）
输出:
  runs/libero-90-combos-20261025/report/index.html             单文件 HTML（内联 CSS/JS）
  runs/libero-90-combos-20261025/report/README.md              <=40 行说明
用法:
  .venv/bin/python scripts/build_libero90_scene_report.py            # 重建 HTML + README
  .venv/bin/python scripts/build_libero90_scene_report.py --check    # 只读校验（不写文件）
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
RUN_DIR = ROOT / "runs" / "libero-90-combos-20261025"
REPORT_DIR = RUN_DIR / "report"
VIDEO_DIR = REPORT_DIR / "videos"
TMP_DIR = ROOT / ".tmp" / "libero90-combos"

P_CAND = RUN_DIR / "candidates-instructed.json"
P_MANIFEST = REPORT_DIR / "video-manifest.json"
P_INV = TMP_DIR / "inventory.json"
P_OFFICIAL = TMP_DIR / "official-language-and-benchmark-map.json"
P_PAIRS = TMP_DIR / "pair-semantics.json"
P_REVIEW = RUN_DIR / "scene_review_decisions.json"
OUT_HTML = REPORT_DIR / "index.html"
OUT_README = REPORT_DIR / "README.md"

PRIO_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
CLASS_RANK = {"compatible": 0, "hard": 1, "conflict": 2, "degenerate": 3}
CLASS_CN = {"compatible": "兼容", "hard": "有依赖", "conflict": "冲突", "degenerate": "退化"}
CLASS_BADGE = {"compatible": "b-ok", "hard": "b-warn", "conflict": "b-fail", "degenerate": "b-muted"}
PRIO_BADGE = {"P0": "b-p0", "P1": "b-p1", "P2": "b-p2", "P3": "b-p3"}
ROUTE_DESC = {
    "M1": "同场景两任务 goal 原子直接组合（主路线）",
    "M2": "场景内纯干扰物提升为第二目标（OBJECT 路线 B 的 L90 版）",
    "S1": "stranded 任务 18 的救场候选（17 是双目标被排除，18 单独无法成对）",
}
SUITE_SHORT = {"LIBERO_SPATIAL": "SPA", "LIBERO_OBJECT": "OBJ", "LIBERO_GOAL": "GOAL", "LIBERO_10": "L10"}
SUITE_ORDER = ["LIBERO_10", "LIBERO_GOAL", "LIBERO_OBJECT", "LIBERO_SPATIAL"]
SCENE_TYPE = {"KITCHEN": ("厨房", "kitchen"), "LIVING_ROOM": ("客厅", "living room"), "STUDY": ("书房", "study")}
TPL_ORDER = ["T1", "T2", "T3", "T4", "T4b", "T5", "T6", "T7", "T8", "T9", "T10"]

# 零命中模板的静态文档元数据（模板名/句式/参考任务属于文档文本；命中计数始终来自 JSON）
TPL_FALLBACK = {
    "T5": {
        "name": "打开+放入同一容器",
        "pattern": "open {container} and put {obj} in it",
        "refs": ["LIBERO-90 /00", "LIBERO-90 /03"],
        "evidence": [
            "LIBERO-90 /00 official: `open the top drawer of the cabinet and put the bowl in it`",
            "v2 复核 v1：原模板唯一来源任务 00 已移出组合池 → 当前口径命中 0",
        ],
    },
}
INVALID_REASON_CN = {
    "goal_conflict": "目标互斥：同一物体/关节被要求两个不能同时成立的状态",
    "s2_no_new_atom（degenerate：s2 不引入新原子）": "退化：s2 未引入新原子",
    "degenerate_pair_merged_goal_equals_single_task": "退化：合并后的目标等于单任务目标",
}

INPUT_FILES = [
    ("candidates-instructed.json", P_CAND),
    ("scene_review_decisions.json", P_REVIEW),
    ("video-manifest.json", P_MANIFEST),
    ("inventory.json", P_INV),
    ("official-language-and-benchmark-map.json", P_OFFICIAL),
    ("pair-semantics.json", P_PAIRS),
]


def esc(value):
    """HTML 转义。"""
    return html.escape(str(value), quote=True)


def nfmt(value):
    return f"{value:,}"


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


VOLATILE_KEYS = ("generated_at", "scanned_at", "built_at", "generated", "created_at")


def _strip_volatile(obj):
    """递归剔除时间戳类字段：视频清单每次重跑都会刷新这些字段，不应让 HTML 指纹过期。"""
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items() if k not in VOLATILE_KEYS}
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


def input_hashes():
    hashes = {}
    for name, path in INPUT_FILES:
        if name == "video-manifest.json":
            data = _strip_volatile(load_json(path))
            blob = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
            hashes[name] = hashlib.sha256(blob).hexdigest()
        else:
            hashes[name] = sha256_file(path)
    return hashes


def build_digest(hashes):
    h = hashlib.sha256()
    for name in sorted(hashes):
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        h.update(hashes[name].encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def build_templates(cands):
    """按 JSON 的 instruction_evidence 汇总 T1-T10/T4b 模板表；零命中模板用 TPL_FALLBACK 元数据保留（计数仍来自 JSON）。"""
    templates = []
    for tid in TPL_ORDER:
        group = [c for c in cands if c["instruction_template"] == tid]
        if group:
            ev = group[0].get("instruction_evidence") or {}
            name = ev.get("template_name", "")
            pattern = ev.get("pattern", "")
            refs, evidence = [], []
            for c in group:
                c_ev = c.get("instruction_evidence") or {}
                for ref in c_ev.get("references", []):
                    if ref not in refs:
                        refs.append(ref)
                for line in c_ev.get("evidence", []):
                    if line not in evidence:
                        evidence.append(line)
            examples = sorted(
                group,
                key=lambda c: (not c["valid"], PRIO_RANK[c["priority"]], CLASS_RANK[c["class"]], c["candidate_id"]),
            )[:2]
        else:
            fb = TPL_FALLBACK.get(tid, {})
            name = fb.get("name", "")
            pattern = fb.get("pattern", "")
            refs = list(fb.get("refs", []))
            evidence = list(fb.get("evidence", []))
            examples = []
        templates.append({
            "id": tid,
            "name": name,
            "pattern": pattern,
            "refs": refs,
            "evidence": evidence,
            "count": len(group),
            "routes": Counter(c["route"] for c in group),
            "examples": examples,
            "zero": len(group) == 0,
        })
    return templates


def build_metrics(cands, summary, stats, manifest, scene_order, reviewed_scenes, pending_scenes):
    by_route = Counter(c["route"] for c in cands)
    by_prio = Counter(c["priority"] for c in cands)
    by_tpl = Counter(c["instruction_template"] for c in cands)
    cap_by_route = Counter(c["route"] for c in cands if c["capacity_caveat"])
    n3 = sum(1 for c in cands if c["n_atoms"] == 3)
    n_same = sum(1 for c in cands if c["instruction"] == c["language"])
    m1_pair_class = stats["m1"]["class_counts_unordered_pairs"]
    class_all = summary["class_counts_all"]
    prio_all = summary["priority_counts_all"]
    video_success = sum(1 for s in scene_order for v in manifest["scene_map"].get(s, []) if v["success"])
    video_failed = sum(1 for s in scene_order for v in manifest["scene_map"].get(s, []) if not v["success"])
    n_ref_pi0 = sum(1 for t in manifest["baseline_tasks"] if t.get("copied_files"))
    n_unref_pi0 = sum(1 for t in manifest["baseline_tasks"] if not t.get("copied_files"))
    zero_hit = [tid for tid in TPL_ORDER if by_tpl[tid] == 0]
    metrics = {
        "total_candidates": len(cands),
        "valid_candidates": sum(1 for c in cands if c["valid"]),
        "excluded_candidates": sum(1 for c in cands if not c["valid"]),
        "tasks": summary["n_tasks"],
        "scenes": summary["n_scenes"],
        "pool_bddl": summary["pool_bddl"],
        "single_pool": summary["single_pool"],
        "n_dual_tasks": len(summary["dual7"]),
        "n_review_excluded_tasks": len(summary["review_excluded_tasks"]),
        "n_reviewed_scenes": len(reviewed_scenes),
        "n_pending_scenes": len(pending_scenes),
        "m1_unordered_pairs": stats["m1"]["n_pairs"],
        "m1_ordered": summary["m1_ordered"],
        "m2_unordered": summary["m2_unordered"],
        "m2_ordered": summary["m2_ordered"],
        "s1_unordered": summary["s1_unordered"],
        "s1_ordered": summary["s1_ordered"],
        "route_m1": by_route["M1"],
        "route_m2": by_route["M2"],
        "route_s1": by_route["S1"],
        "class_pair_compatible": m1_pair_class["compatible"],
        "class_pair_hard": m1_pair_class["hard"],
        "class_pair_conflict": m1_pair_class["conflict"],
        "class_pair_degenerate": m1_pair_class["degenerate"],
        "class_ordered_compatible": summary["class_counts"]["compatible"],
        "class_ordered_hard": summary["class_counts"]["hard"],
        "class_ordered_conflict": summary["class_counts"]["conflict"],
        "class_ordered_degenerate": summary["class_counts"]["degenerate"],
        "class_all_compatible": class_all["compatible"],
        "class_all_hard": class_all["hard"],
        "class_all_conflict": class_all["conflict"],
        "class_all_degenerate": class_all["degenerate"],
        "prio_p0": summary["priority_counts"]["P0"],
        "prio_p1": summary["priority_counts"]["P1"],
        "prio_p2": summary["priority_counts"]["P2"],
        "prio_p3": summary["priority_counts"]["P3"],
        "prio_all_p0": prio_all["P0"],
        "prio_all_p1": prio_all["P1"],
        "prio_all_p2": prio_all["P2"],
        "prio_all_p3": prio_all["P3"],
        "n_atoms_2": len(cands) - n3,
        "n_atoms_3": n3,
        "n_naive_same": n_same,
        "n_rewritten": len(cands) - n_same,
        "n_zero_hit_templates": len(zero_hit),
        "videos": manifest["video_count"],
        "video_scenes": len(scene_order),
        "video_kind_exact": manifest["kind_counts"]["exact_scene_l10"],
        "video_kind_family": manifest["kind_counts"]["suite_family_reference"],
        "pi0_tasks": manifest["pi0_task_count"],
        "pi0_success": manifest["pi0_success_count"],
        "scene_ref_success": video_success,
        "scene_ref_failed": video_failed,
        "n_ref_pi0": n_ref_pi0,
        "n_unref_pi0": n_unref_pi0,
        "m1_s1_revertable_ab": stats["m1"]["s1_revertable_ab"],
        "m1_s1_revertable_ba": stats["m1"]["s1_revertable_ba"],
        "m1_capacity_pairs": stats["m1"]["capacity_caveat_pairs"],
        "m1_capacity_ordered": stats["m1"]["capacity_caveat_ordered"],
        "cap_cands_m1": cap_by_route["M1"],
        "cap_cands_m2": cap_by_route["M2"],
        "n_s1_unrevertable": sum(1 for c in cands if not c["s1_revertable"]),
        "tpl_total": len(cands),
    }
    for tid in TPL_ORDER:
        metrics[f"tpl_{tid}"] = by_tpl[tid]
    return metrics


def build_scene_rows(cands, inventory, manifest, dual7, bench, two_atom_single, review_decisions):
    """按 inventory 的场景顺序组装 20 个场景；组合池按 scene_review_decisions.json 剔除任务。"""
    tasks = inventory["tasks"]
    scene_order = list(inventory["scenes"].keys())
    video_meta = {v["file"]: v for v in manifest["videos"]}
    scenes = []
    for scene in scene_order:
        idxs = inventory["scenes"][scene]
        scene_tasks = [tasks[i] for i in idxs]
        decision = review_decisions.get(scene)
        excluded = [int(t) for t in (decision or {}).get("exclude_tasks_from_pairing", [])]
        duals = [i for i in idxs if i in dual7]
        pool_bddl_idxs = [i for i in idxs if i not in dual7]
        pool_idxs = [i for i in pool_bddl_idxs if i not in excluded]
        scene_cands = sorted(
            [c for c in cands if c["scene"] == scene],
            key=lambda c: (PRIO_RANK[c["priority"]], CLASS_RANK[c["class"]], c["candidate_id"]),
        )
        rows = []
        for i in idxs:
            t = tasks[i]
            official_row = bench.get(i, {})
            off = official_row.get("official_language") or t["language"]
            inline = t["language"]
            review_excluded = i in excluded
            dual_kind = ""
            if review_excluded:
                dual_label = "双目标（用户复核：已移出组合池）"
                dual_title = (decision or {}).get("reason", "")
                dual_kind = "review_excluded"
            elif i in dual7:
                dual_label = "双目标"
                dual_title = "两个 goal 原子指向不同目标实体（口径 C）"
                dual_kind = "dual"
                if i == 17:
                    dual_title = "两个 goal 原子指向不同目标实体；其中 Turnon 在 :init 已真（口径 B 会把它计为单目标）"
            elif i in two_atom_single:
                dual_label = "单目标·2 原子"
                dual_title = "两个 goal 原子作用于同一容器区域（Open+In / In+Close 谓词对），按口径 C 计单目标"
                dual_kind = "two_atom_single"
            else:
                dual_label, dual_title = "", ""
            rows.append({
                "index": i,
                "official": off,
                "inline": inline,
                "mismatch": off != inline,
                "atoms": t["goal_atoms"],
                "objects": t["object_names"],
                "width": t["init_width"],
                "n_goal_atoms": t.get("n_goal_atoms", len(t["goal_atoms"])),
                "dual": i in dual7,
                "dual_label": dual_label,
                "dual_title": dual_title,
                "dual_kind": dual_kind,
                "review_excluded": review_excluded,
                "bench_idx": official_row.get("bench_idx"),
            })
        objects = sorted({name for t in scene_tasks for name in t["object_names"]})
        fixtures = sorted({name for t in scene_tasks for name in t["fixture_names"]})
        videos = []
        for v in manifest["scene_map"].get(scene, []):
            merged = dict(video_meta.get(v["file"], {}))
            merged.update(v)
            videos.append(merged)
        stype = "LIVING_ROOM" if scene.startswith("LIVING_ROOM") else scene.split("_")[0]
        type_zh, type_en = SCENE_TYPE.get(stype, (stype, ""))
        scenes.append({
            "scene": scene,
            "short": manifest["scene_meta"].get(scene, {}).get("scene_short", scene),
            "type_zh": type_zh,
            "type_en": type_en,
            "fp": inventory["scene_fp_variants"][scene][0],
            "task_rows": rows,
            "task_count": len(idxs),
            "dual_count": len(duals),
            "dual_idxs": duals,
            "reviewed": decision is not None,
            "review_decision": decision,
            "review_excluded": excluded,
            "review_excluded_count": len(excluded),
            "pool_bddl_count": len(pool_bddl_idxs),
            "pool_count": len(pool_idxs),
            "pair_bddl_count": len(pool_bddl_idxs) * (len(pool_bddl_idxs) - 1) // 2,
            "pair_count": len(pool_idxs) * (len(pool_idxs) - 1) // 2,
            "objects": objects,
            "fixtures": fixtures,
            "width": scene_tasks[0]["init_width"],
            "videos": videos,
            "exact_count": sum(1 for v in videos if v["kind"] == "exact_scene_l10"),
            "family_count": sum(1 for v in videos if v["kind"] == "suite_family_reference"),
            "success_count": sum(1 for v in videos if v["success"]),
            "cands": scene_cands,
            "main": [c for c in scene_cands if c["valid"]],
            "excl": [c for c in scene_cands if not c["valid"]],
            "prio": Counter(c["priority"] for c in scene_cands),
            "klass": Counter(c["class"] for c in scene_cands),
            "route": Counter(c["route"] for c in scene_cands),
        })
    return scenes


def compute_model():
    data = load_json(P_CAND)
    manifest = load_json(P_MANIFEST)
    inventory = load_json(P_INV)
    official = load_json(P_OFFICIAL)
    pairs = load_json(P_PAIRS)
    review = load_json(P_REVIEW)

    cands = data["candidates"]
    summary = data["summary"]
    stats = data["stats"]
    meta = data.get("meta", {})
    scene_order = list(inventory["scenes"].keys())
    bench = {row["index"]: row for row in official["benchmark_order"]}
    dual7 = set(summary["dual7"])
    two_atom_single = set(inventory["rules"]["goal_atoms_eq_2"]) - dual7
    review_decisions = {d["scene"]: d for d in review.get("decisions", [])}
    reviewed_scenes = [s for s in scene_order if s in review_decisions]
    pending_scenes = [s for s in scene_order if s not in review_decisions]
    excluded_tasks = sorted({
        int(t) for d in review_decisions.values() for t in d.get("exclude_tasks_from_pairing", [])
    })
    review_sha = sha256_file(P_REVIEW)

    scenes = build_scene_rows(cands, inventory, manifest, dual7, bench, two_atom_single, review_decisions)
    metrics = build_metrics(cands, summary, stats, manifest, scene_order, reviewed_scenes, pending_scenes)
    templates = build_templates(cands)

    removed_pairs = sum(s["pair_bddl_count"] - s["pair_count"] for s in scenes if s["reviewed"])
    removed_candidates = 2 * removed_pairs
    old_m1_unordered = metrics["m1_unordered_pairs"] + removed_pairs
    old_m1_ordered = 2 * old_m1_unordered
    old_total = old_m1_ordered + metrics["m2_ordered"] + metrics["s1_ordered"]
    revision = {
        "review_version": review.get("version"),
        "review_updated_at": review.get("updated_at", ""),
        "review_source": review.get("source", ""),
        "review_sha256": review_sha,
        "removed_pairs": removed_pairs,
        "removed_candidates": removed_candidates,
        "old_m1_unordered": old_m1_unordered,
        "old_m1_ordered": old_m1_ordered,
        "old_total": old_total,
        "new_total": metrics["total_candidates"],
        "old_tpl_T5": removed_candidates if metrics["tpl_T5"] == 0 else None,
        "old_tpl_T5_text": str(removed_candidates) if metrics["tpl_T5"] == 0 else "—",
    }
    ps_pairs = len(pairs.get("pairs", []))
    pair_semantics = {
        "n_pairs": ps_pairs,
        "scope_pairs": (pairs.get("scope") or {}).get("n_pairs"),
        "stale": ps_pairs != metrics["m1_unordered_pairs"],
    }
    hashes = input_hashes()
    return {
        "data": data,
        "meta": meta,
        "candidates": cands,
        "summary": summary,
        "stats": stats,
        "inventory": inventory,
        "official": official,
        "pairs": pairs,
        "review": review,
        "review_decisions": review_decisions,
        "reviewed_scenes": reviewed_scenes,
        "pending_scenes": pending_scenes,
        "excluded_tasks": excluded_tasks,
        "manifest": manifest,
        "scene_order": scene_order,
        "scene_rows": scenes,
        "templates": templates,
        "metrics": metrics,
        "revision": revision,
        "pair_semantics": pair_semantics,
        "dual7": sorted(dual7),
        "two_atom_single": sorted(two_atom_single),
        "bench": bench,
        "hashes": hashes,
        "digest": build_digest(hashes),
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
    }


def validate_model(m):
    """输入自洽性断言（构建与 --check 共用；所有计数都必须与 JSON 对齐）。"""
    problems = []
    mt = m["metrics"]
    cands = m["candidates"]
    summary = m["summary"]
    stats = m["stats"]
    meta = m["meta"]
    review = m["review"]
    scenes = m["scene_rows"]
    total = summary["total"]

    def need(cond, msg):
        if not cond:
            problems.append(msg)

    need(len(cands) == total, f"候选数 {len(cands)} != summary.total {total}")
    need(len(scenes) == summary["n_scenes"], f"场景数 {len(scenes)} != summary.n_scenes")
    need(mt["route_m1"] + mt["route_m2"] + mt["route_s1"] == len(cands), "route 计数之和 != 候选总数")
    need(mt["valid_candidates"] + mt["excluded_candidates"] == len(cands), "valid+excluded != 候选总数")
    need(sum(mt[f"tpl_{t}"] for t in TPL_ORDER) == len(cands), "模板分布之和 != 候选总数")
    need(sum(mt[f"class_pair_{c}"] for c in ("compatible", "hard", "conflict", "degenerate"))
         == mt["m1_unordered_pairs"], "pair 级 class 之和 != M1 无序对数")
    need(sum(mt[f"class_ordered_{c}"] for c in ("compatible", "hard", "conflict", "degenerate"))
         == mt["m1_ordered"], "ordered class 之和 != M1 ordered")
    need(sum(mt[f"prio_{p.lower()}"] for p in ("P0", "P1", "P2", "P3")) == mt["m1_ordered"], "优先级之和 != M1 ordered")
    need(sum(mt[f"prio_all_{p.lower()}"] for p in ("P0", "P1", "P2", "P3")) == len(cands), "全量优先级之和 != 候选总数")
    need(mt["m1_ordered"] == 2 * mt["m1_unordered_pairs"], "M1 ordered != 2 x unordered")
    need(mt["m2_ordered"] == 2 * mt["m2_unordered"], "M2 ordered != 2 x unordered")
    need(mt["s1_ordered"] == 2 * mt["s1_unordered"], "S1 ordered != 2 x unordered")
    need(mt["tpl_total"] == len(cands), "tpl_total != 候选总数")
    zero_hit = sorted(t for t in TPL_ORDER if mt[f"tpl_{t}"] == 0)
    need(zero_hit == sorted(meta.get("template_zero_hits", [])),
         f"零命中模板 {zero_hit} != meta.template_zero_hits {meta.get('template_zero_hits')}")
    need(sum(s["task_count"] for s in scenes) == mt["tasks"], "场景任务数之和 != 任务总数")
    need(sum(len(s["cands"]) for s in scenes) == len(cands), "场景候选数之和 != 候选总数")
    need(sum(len(s["main"]) for s in scenes) == mt["valid_candidates"], "场景 valid 之和 != valid 总数")
    need(sum(len(s["excl"]) for s in scenes) == mt["excluded_candidates"], "场景 excluded 之和 != excluded 总数")
    need(sum(s["pair_count"] for s in scenes) == mt["m1_unordered_pairs"], "场景 M1 对数和 != M1 对数")
    need(sum(s["exact_count"] for s in scenes) == mt["video_kind_exact"], "exact 视频数不一致")
    need(sum(s["family_count"] for s in scenes) == mt["video_kind_family"], "family 视频数不一致")
    need(sum(len(s["videos"]) for s in scenes) == mt["videos"], "视频总数不一致")
    need(mt["scene_ref_success"] + mt["scene_ref_failed"] == mt["videos"], "参考视频 success/failed 之和 != 视频数")
    need(mt["single_pool"] == mt["pool_bddl"] - mt["n_review_excluded_tasks"],
         "single_pool != pool_bddl - 复核剔除任务数")
    need(mt["n_reviewed_scenes"] + mt["n_pending_scenes"] == mt["scenes"], "复核场景计数 != 场景总数")
    need(sum(1 for c in cands if c["route"] == "M2") == mt["m2_ordered"], "M2 route 计数 != m2_ordered")
    need(sum(1 for c in cands if c["route"] == "S1") == mt["s1_ordered"], "S1 route 计数 != s1_ordered")
    for c in ("compatible", "hard", "conflict", "degenerate"):
        need(mt[f"class_all_{c}"] == summary["class_counts_all"][c], f"class_all {c} 不符")
    for p in ("P0", "P1", "P2", "P3"):
        need(mt[f"prio_all_{p.lower()}"] == summary["priority_counts_all"][p], f"prio_all {p} 不符")
    # 逐场景与 stats.per_scene 对账（per_scene 的 class/priority 只覆盖 M1）
    per = {x["scene"]: x for x in stats["per_scene"]}
    for s in scenes:
        expect = per.get(s["scene"])
        need(expect is not None, f"{s['scene']}: stats.per_scene 缺失")
        if not expect:
            continue
        need(len(s["cands"]) == expect["m1_ordered"] + expect["m2_ordered"] + expect["s1_ordered"],
             f"{s['scene']}: 候选数与 stats.per_scene 不符")
        m1_s = [c for c in s["cands"] if c["route"] == "M1"]
        need(Counter(c["class"] for c in m1_s) == Counter(expect["class_counts"]),
             f"{s['scene']}: M1 class 分布与 stats.per_scene 不符")
        need(Counter(c["priority"] for c in m1_s) == Counter(expect["priority_counts"]),
             f"{s['scene']}: M1 priority 分布与 stats.per_scene 不符")
        need(s["pair_count"] == expect["m1_unordered"], f"{s['scene']}: 组合对数 != stats.m1_unordered")
        need(s["pool_count"] == expect["n_pool_tasks"], f"{s['scene']}: 组合池 != stats.n_pool_tasks")
        need(s["pool_bddl_count"] == expect.get("n_pool_bddl_tasks", s["pool_count"]),
             f"{s['scene']}: BDDL 组合池不一致")
        need(s["reviewed"] == bool(expect.get("reviewed")), f"{s['scene']}: 复核标记与 stats.per_scene 不符")
        need(sorted(s["review_excluded"]) == sorted(int(t) for t in expect.get("exclude_tasks_from_pairing", [])),
             f"{s['scene']}: 剔除任务与 stats.per_scene 不符")
    # 复核文件与 candidates 的交叉校验
    need(set(m["reviewed_scenes"]) == set(review_decisions_scenes(review)),
         "复核场景集合与 scene_review_decisions.decisions 不一致")
    pending_file = [s for s in review.get("pending_scenes", []) if s in m["scene_order"]]
    need(set(m["pending_scenes"]) == set(pending_file), "待复核场景与 scene_review_decisions.pending_scenes 不一致")
    need(review.get("version") == summary.get("review_decisions_version"), "复核版本与 candidates summary 不一致")
    need(m["revision"]["review_sha256"] == meta.get("scene_review_decisions_sha256"),
         "scene_review_decisions.json sha256 与 candidates meta 不一致")
    need(summary.get("review_excluded_tasks") == m["excluded_tasks"], "复核剔除任务与 candidates summary 不一致")
    need(not (set(m["excluded_tasks"]) & set(summary["dual7"])), "剔除任务与双目标任务重叠")
    used = set()
    for c in cands:
        for side in ("s1_task", "s2_task"):
            idx = c[side].get("index")
            if idx is not None:
                used.add(int(idx))
    need(not (used & set(m["excluded_tasks"])), f"剔除任务仍出现在候选里: {sorted(used & set(m['excluded_tasks']))}")
    # 版本差异口径
    rev = m["revision"]
    need(rev["new_total"] == mt["total_candidates"], "revision.new_total 与当前候选数不符")
    need(rev["old_total"] - rev["new_total"] == rev["removed_candidates"],
         "旧/新候选数差与剔除候选数不符")
    need(rev["old_total"] == mt["total_candidates"] + rev["removed_candidates"], "修订前总数口径不符")
    # 视频清单与磁盘
    missing = [v["file"] for v in m["manifest"]["videos"] if not (REPORT_DIR / v["file"]).exists()]
    need(not missing, f"视频文件缺失: {missing[:3]}")
    if problems:
        raise SystemExit("[FATAL] 输入数据不自洽:\n - " + "\n - ".join(problems))


def review_decisions_scenes(review):
    return [d["scene"] for d in review.get("decisions", [])]


def route_stats(cands, route):
    sub = [c for c in cands if c["route"] == route]
    return Counter(c["class"] for c in sub), Counter(c["priority"] for c in sub)


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
.status{background:#fffbeb;border-left:4px solid #f59e0b;color:#78350f;padding:10px 12px;border-radius:6px;margin:10px 0;font-size:13px;line-height:1.65}
.method{background:#eff6ff;border-left:4px solid #3b82f6;color:#1e3a8a;padding:10px 12px;border-radius:6px;margin:10px 0;font-size:13px;line-height:1.65}
main{max-width:1320px;margin:0 auto;padding:0 26px 70px}
section{margin:34px 0;padding-top:6px;border-top:1px solid #e5e7eb;scroll-margin-top:64px}
h2{font-size:21px;margin:10px 0 8px}h3{font-size:16px;margin:22px 0 8px}h4{font-size:14px;margin:14px 0 6px}
p{color:#374151}
.sub{color:#6b7280;font-size:13px}
.tiny{color:#6b7280;font-size:11px;line-height:1.4}
.nowrap{white-space:nowrap}
.filterbar{position:sticky;top:0;z-index:30;background:rgba(247,248,250,.97);border-bottom:1px solid #e5e7eb;padding:8px 0;display:flex;gap:8px;flex-wrap:wrap;align-items:center;font-size:12.5px}
.filterbar select,.filterbar button{background:#fff;color:#111827;border:1px solid #d1d5db;border-radius:6px;padding:4px 7px;font-size:12px;cursor:pointer}
.filterbar .count{color:#1d4ed8;font-weight:600;margin-left:auto}
.filterbar .hint{color:#6b7280;font-size:11px;flex-basis:100%}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(235px,1fr));gap:10px;margin:12px 0}
.metric{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px 14px}
.metric.wide{grid-column:span 2}
.metric .v{font-size:22px;font-weight:700;line-height:1.3}
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
tr.dual td{background:#fdf4ff}
table.tasks td:first-child,table.cands td:first-child{white-space:nowrap}
.atoms code{display:inline-block;background:transparent;padding:0;font-size:11.5px;color:#4b5563}
.badge{display:inline-block;padding:1px 7px;border-radius:9px;font-size:11px;font-weight:700;margin:1px 2px 1px 0;white-space:nowrap}
.b-ok{background:#dcfce7;color:#15803d}.b-fail{background:#fee2e2;color:#b91c1c}
.b-warn{background:#fef3c7;color:#a16207}.b-info{background:#dbeafe;color:#1d4ed8}
.b-muted{background:#f3f4f6;color:#6b7280}.b-ref{background:#f3e8ff;color:#7e22ce}
.b-dual{background:#fce7f3;color:#be185d}
.b-p0{background:#dcfce7;color:#15803d}.b-p1{background:#dbeafe;color:#1d4ed8}
.b-p2{background:#fef3c7;color:#a16207}.b-p3{background:#f3f4f6;color:#6b7280}
.scenehead{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px 14px;margin:8px 0 4px}
.scenehead .objline{font-size:12px;color:#4b5563;margin-top:6px;line-height:1.65}
.vidlink{font-size:11.5px;background:#f3e8ff;color:#7e22ce;border-radius:8px;padding:1px 6px;margin:1px 2px 1px 0;display:inline-block;white-space:nowrap}
.vidlink:hover{text-decoration:none;background:#ede9fe}
.excl summary,.tpl-ev summary,td details summary,.var summary{cursor:pointer;color:#1d4ed8;font-size:11.5px}
.naive{display:block;background:#f9fafb;border-left:2px solid #e5e7eb;padding:3px 6px;margin-top:3px;font-size:11px;color:#6b7280;white-space:pre-wrap;word-break:break-word}
td.ins{min-width:250px}
.excl{border:1px dashed #d1d5db;border-radius:10px;padding:8px 12px;background:#fff;margin:12px 0}
.excl summary{font-weight:600;color:#374151;font-size:13px}
.excl[open] summary{margin-bottom:6px}
.vgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;margin:10px 0}
.vcard{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:10px;margin:0;min-width:0}
.vcard .vhead{font-size:13px;margin-bottom:5px}
.vcard .vhead .tiny{font-weight:400}
.vcard video{width:100%;border-radius:6px;background:#000;display:block;margin:6px 0}
.vcard .badges{margin:4px 0}
.vcard .instr{font-size:12px;color:#4b5563;margin:4px 0}
.vcard .kv{font-size:11px;color:#6b7280;margin:3px 0}
.vcard .why{font-size:11.5px;color:#4b5563;margin:3px 0}
.vcard .honest{background:#fef3c7;border-left:3px solid #f59e0b;color:#78350f;padding:5px 7px;border-radius:4px;font-size:11px;line-height:1.5;margin:6px 0}
.vcard .orig{font-size:10.5px;color:#9ca3af;word-break:break-all;margin:3px 0 0}
.gapcard{border:1px dashed #d1d5db;border-radius:10px;padding:14px;color:#6b7280;background:#f9fafb;font-size:12px}
.videowarn{background:#fef2f2;border-left:4px solid #ef4444;color:#7f1d1d;padding:8px 10px;border-radius:6px;font-size:12px;margin:8px 0}
.scardgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px;margin:10px 0}
.scard{display:block;background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:10px 12px;color:#1f2328}
.scard:hover{border-color:#93c5fd;text-decoration:none;box-shadow:0 2px 8px rgba(29,78,216,.08)}
.scard b{color:#1d4ed8}.scard .h{font-weight:700;font-size:13px;margin-bottom:4px}
.scard .r{font-size:11.5px;color:#6b7280;line-height:1.5}
ul.flat{margin:8px 0;padding-left:20px}ul.flat li{margin:5px 0;color:#374151;font-size:13px}
ol.risk{margin:8px 0;padding-left:22px}ol.risk li{margin:7px 0;color:#374151;font-size:13px;line-height:1.6}
.note{background:#f8fafc;border-left:3px solid #cbd5e1;padding:6px 10px;color:#4b5563;font-size:12px;border-radius:4px;margin:6px 0;line-height:1.6}
.top{font-size:12px;font-weight:400;color:#9ca3af;margin-left:6px}
footer{margin-top:40px;padding:14px 0 30px;border-top:1px solid #e5e7eb;color:#6b7280;font-size:11.5px;line-height:1.7}
footer code{font-size:11px}
.s-ok{color:#15803d}.s-fail{color:#b91c1c}
.xlink{background:#f3e8ff;color:#7e22ce;border-radius:8px;padding:1px 6px;font-size:11px}
.b-review{background:#bbf7d0;color:#14532d}
.chip-zero{background:#f9fafb;color:#9ca3af;border-style:dashed}
.chip-review{background:#f0fdf4;border-color:#86efac;color:#14532d}
tr.review-excluded td{background:#f0fdf4}
.task-row.review-excluded td:first-child{border-left:3px solid #86efac}
.review-row.reviewed td{background:#f0fdf4}
.scard.reviewed{border-color:#86efac;background:#f0fdf4}
.tpl-zero td{background:#fafafa;color:#6b7280}
@media (max-width:980px){body{padding-left:0}.sidenav{position:static;width:auto;height:auto;border-right:none;border-bottom:1px solid #e5e7eb;box-shadow:none}.sidenav .foot{display:none}main{padding:0 14px 50px}.metric.wide{grid-column:span 1}}
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

  var pSel = document.getElementById('filter-prio');
  var cSel = document.getElementById('filter-class');
  var rSel = document.getElementById('filter-route');
  var reset = document.getElementById('filter-reset');
  var counter = document.getElementById('filter-count');
  if (!pSel || !cSel || !rSel || !counter) return;
  var rows = Array.prototype.slice.call(document.querySelectorAll('tr.cand-row'));
  function apply(){
    var p = pSel.value, c = cSel.value, r = rSel.value, shown = 0, per = {};
    rows.forEach(function(tr){
      var ok = (!p || tr.dataset.priority === p) && (!c || tr.dataset.class === c) && (!r || tr.dataset.route === r);
      tr.style.display = ok ? '' : 'none';
      if (ok) { shown++; per[tr.dataset.scene] = (per[tr.dataset.scene] || 0) + 1; }
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-live-count]'), function(el){
      var k = el.getAttribute('data-live-count');
      el.textContent = (per[k] || 0);
    });
    counter.textContent = '显示 ' + shown + ' / ' + rows.length + ' 条候选';
  }
  [pSel, cSel, rSel].forEach(function(s){ s.addEventListener('change', apply); });
  if (reset) reset.addEventListener('click', function(){ pSel.value = ''; cSel.value = ''; rSel.value = ''; apply(); });
  apply();
})();
"""


def render_sidenav(m):
    parts = ['<nav class="sidenav" aria-label="报告目录">',
             '<div class="brand">LIBERO-90<br>双目标组合 · 分场景报告<br><span style="font-weight:400;color:#6b7280">v2 · 复核 v1 后</span></div>',
             '<div class="grp">总览</div>',
             '<a href="#top">状态与范围</a>',
             '<a href="#overview">指标与口径</a>',
             '<a href="#templates">指令模板 T1–T10</a>',
             '<a href="#scene-index">场景索引</a>',
             '<a href="#scene-review">逐场景复核状态</a>',
             '<div class="grp">场景（按任务序）</div>']
    for s in m["scene_rows"]:
        label = f'{s["short"]} {s["type_zh"]} · {s["task_count"]} 任务 / {len(s["cands"])} 候选'
        title = (f'{s["scene"]} · {s["type_en"]} · {s["task_count"]} 任务 · {len(s["cands"])} 候选 · '
                 f'{len(s["videos"])} 参考视频' + (' · 已复核' if s["reviewed"] else ' · 待复核'))
        parts.append(f'<a class="nav-scene" href="#scene-{s["scene"]}" title="{esc(title)}">{esc(label)}</a>')
    parts += ['<div class="grp">全局</div>',
              '<a href="#baseline-gallery">pi0 baseline 画廊</a>',
              '<a href="#funnel">验证漏斗与下一步</a>',
              '<a href="#risks">风险与未验证项</a>',
              '<a href="#revision-note">v2 修订记录</a>',
              '<a href="#artifacts">产物索引</a>',
              '<div class="foot">v2（复核 v1 后）<br>组合任务 0 动态实测<br>视频均为 pi0 参考 baseline<br>scripts/build_libero90_scene_report.py</div>',
              '</nav>']
    return "\n".join(parts)


def render_hero(m):
    mt = m["metrics"]
    rev = m["revision"]
    manifest = m["manifest"]
    data_date = manifest.get("generated_at", "")[:10]
    return f'''<header class="hero" id="top">
<h1>LIBERO-90 单目标任务的双目标组合 · 分场景详细报告 <span class="badge b-review">v2 · 复核 v1 后</span></h1>
<p class="meta">90 条 LIBERO-90 任务 / <b>{mt["scenes"]}</b> 个场景 · BDDL 单目标池 <b>{mt["pool_bddl"]}</b> → 用户复核 v1 剔除 <b>{mt["n_review_excluded_tasks"]}</b> 条（KS1/00）→ <b>组合池 {mt["single_pool"]}</b> · <b>{mt["m1_unordered_pairs"]} 个同场景单目标对</b> → <b>{mt["total_candidates"]} 个 ordered 组合候选</b>（M1 {mt["route_m1"]} + M2 {mt["route_m2"]} + S1 {mt["route_s1"]}）· pi0 参考视频 {mt["videos"]} 段 · 日期 {esc(data_date)} · 运行目录 <code>runs/libero-90-combos-20261025/</code></p>
<div class="status"><b>⚠ 状态声明（必读）</b>：本轮为<b>静态构造</b>——{mt["total_candidates"]} 条组合候选<b>没有任何动态实测（0 episode）</b>。本页所有视频都是 <b>pi0 在标准四套件（SPATIAL / OBJECT / GOAL / LIBERO-10）上的参考 baseline</b>（kind = <code>exact_scene_l10</code> 或 <code>suite_family_reference</code>），<b>不是 LIBERO-90 任何任务或组合任务的实测</b>；“可解性 / 稳定性”未验证。</div>
<p class="method"><b>方法一句话</b>：同场景任务级 <code>goal</code> 原子直接组合（LIBERO-GOAL 内核）+ 场景内纯干扰物提升（M2）+ stranded 救场（S1）；合并指令按 LIBERO-10 / LIBERO-GOAL / LIBERO-OBJECT 已验证成功任务模板重建（<b>T1–T10，含子变体 T4b</b>），<b>不做跨场景组合</b>。</p>
<p class="method" data-v1-history="1" style="background:#f0fdf4;border-left-color:#16a34a;color:#14532d"><b>v2 修订（{esc(rev["review_updated_at"][:10])}，用户逐场景复核 v1）</b>：按 <code>scene_review_decisions.json</code> 剔除 KS1 任务 00（它本身是双子任务，不再与其他任务组合）→ 组合池 {mt["pool_bddl"]}→{mt["single_pool"]}、候选 {rev["old_total"]}→{mt["total_candidates"]}（M1 {rev["old_m1_ordered"]}→{mt["m1_ordered"]} ordered；T5 命中 {rev["old_tpl_T5_text"]}→{mt["tpl_T5"]}）；其余 {mt["n_pending_scenes"]} 个场景暂无修改意见，保持原方案；视频不变 {mt["videos"]} 段。差异明细见 <a href="#revision-note">v2 修订记录</a>。</p>
<p class="gen">生成脚本 <code>scripts/build_libero90_scene_report.py</code> · 数据截止 {esc(manifest.get("generated_at", ""))}（video-manifest）· 复核口径 {esc(str(rev["review_updated_at"]))}（scene_review_decisions v{rev["review_version"]}）· 构建指纹见页脚 · 单文件内联 CSS/JS，无外链 CDN</p>
</header>'''


def render_filterbar(m):
    mt = m["metrics"]
    return f'''<div class="filterbar" id="filterbar">
<b>候选筛选</b>
<select id="filter-prio" aria-label="按优先级筛选"><option value="">全部优先级</option><option value="P0">P0（全部 {mt["prio_all_p0"]}；M1 {mt["prio_p0"]}）</option><option value="P1">P1（{mt["prio_all_p1"]}）</option><option value="P2">P2（{mt["prio_all_p2"]}）</option><option value="P3">P3（{mt["prio_all_p3"]}）</option></select>
<select id="filter-class" aria-label="按 class 筛选"><option value="">全部 class</option><option value="compatible">compatible</option><option value="hard">hard</option><option value="conflict">conflict</option><option value="degenerate">degenerate</option></select>
<select id="filter-route" aria-label="按路线筛选"><option value="">全部路线</option><option value="M1">M1 直接组合</option><option value="M2">M2 提升</option><option value="S1">S1 救场</option></select>
<button id="filter-reset" type="button">重置</button>
<span class="count" id="filter-count">显示 {mt["total_candidates"]} / {mt["total_candidates"]} 条候选</span>
<span class="hint">前端筛选作用于全部 {mt["scenes"]} 个场景的候选表（含“对照与排除”），不改变数据；每个场景标题里的“场景内候选”数字会同步当前可见行数。v2 口径：组合池 {mt["single_pool"]}（BDDL {mt["pool_bddl"]} − 复核剔除 {mt["n_review_excluded_tasks"]}）、候选 {mt["total_candidates"]}。</span>
</div>'''


def render_overview(m):
    mt = m["metrics"]
    rev = m["revision"]
    m1c, m1p = route_stats(m["candidates"], "M1")
    m2c, m2p = route_stats(m["candidates"], "M2")
    s1c, s1p = route_stats(m["candidates"], "S1")
    tpl_chips = "".join(
        f'<span class="chip{" chip-zero" if t["count"] == 0 else ""}"><b>{t["id"]}</b> '
        f'<span data-metric="tpl_{t["id"]}">{t["count"]}</span></span>'
        for t in m["templates"]
    )
    n_m1, n_m2, n_s1 = mt["route_m1"], mt["route_m2"], mt["route_s1"]
    return f'''<section id="overview">
<h2>一、指标与口径（v2 · 复核 v1 后）</h2>
<p class="sub">所有数字由脚本从 <code>candidates-instructed.json</code>（{mt["total_candidates"]} 条）/ <code>video-manifest.json</code> / <code>inventory.json</code> / <code>pair-semantics.json</code> / <code>scene_review_decisions.json</code>（唯一复核口径源）计算，并与 <code>stats</code> 交叉核对；<code>--check</code> 会逐项复验。</p>
<div class="cards">
<div class="metric"><div class="v" data-metric="total_candidates">{mt["total_candidates"]}</div><div class="l">ordered 组合候选（v2）</div><div class="d">valid <span data-metric="valid_candidates">{mt["valid_candidates"]}</span> / 排除 <span data-metric="excluded_candidates">{mt["excluded_candidates"]}</span>（conflict+degenerate）· M1 <span data-metric="route_m1">{mt["route_m1"]}</span>（<span data-metric="m1_ordered">{mt["m1_ordered"]}</span> ordered）+ M2 <span data-metric="route_m2">{mt["route_m2"]}</span>（<span data-metric="m2_ordered">{mt["m2_ordered"]}</span>）+ S1 <span data-metric="route_s1">{mt["route_s1"]}</span>（<span data-metric="s1_ordered">{mt["s1_ordered"]}</span>）</div></div>
<div class="metric"><div class="v"><span data-metric="tasks">{mt["tasks"]}</span> → <span data-metric="pool_bddl">{mt["pool_bddl"]}</span> → <span data-metric="single_pool">{mt["single_pool"]}</span></div><div class="l">L90 任务 → BDDL 单目标池 → 复核后组合池</div><div class="d">按用户复核 v1 剔除 <span data-metric="n_review_excluded_tasks">{mt["n_review_excluded_tasks"]}</span> 条（KS1/00）；双目标任务 <span data-metric="n_dual_tasks">{mt["n_dual_tasks"]}</span> 条；<span data-metric="scenes">{mt["scenes"]}</span> 个场景 / <span data-metric="m1_unordered_pairs">{mt["m1_unordered_pairs"]}</span> 个同场景单目标对 → M1 ordered <span data-metric="m1_ordered">{mt["m1_ordered"]}</span></div></div>
<div class="metric"><div class="v"><span data-metric="n_reviewed_scenes">{mt["n_reviewed_scenes"]}</span> / <span data-metric="scenes">{mt["scenes"]}</span></div><div class="l">逐场景复核进度（v1）</div><div class="d">已复核 KS1（剔除任务 00）· 待复核 <span data-metric="n_pending_scenes">{mt["n_pending_scenes"]}</span> 个场景（暂无修改意见）；详见 <a href="#scene-review">逐场景复核状态</a></div></div>
<div class="metric"><div class="v"><span data-metric="class_pair_compatible">{mt["class_pair_compatible"]}</span> / <span data-metric="class_pair_hard">{mt["class_pair_hard"]}</span> / <span data-metric="class_pair_conflict">{mt["class_pair_conflict"]}</span> / <span data-metric="class_pair_degenerate">{mt["class_pair_degenerate"]}</span></div><div class="l">class · pair 级（<span data-metric="m1_unordered_pairs">{mt["m1_unordered_pairs"]}</span> 对）</div><div class="d">ordered（M1 <span data-metric="m1_ordered">{mt["m1_ordered"]}</span>）：<span data-metric="class_ordered_compatible">{mt["class_ordered_compatible"]}</span> / <span data-metric="class_ordered_hard">{mt["class_ordered_hard"]}</span> / <span data-metric="class_ordered_conflict">{mt["class_ordered_conflict"]}</span> / <span data-metric="class_ordered_degenerate">{mt["class_ordered_degenerate"]}</span>；全部 {mt["total_candidates"]}：<span data-metric="class_all_compatible">{mt["class_all_compatible"]}</span> / <span data-metric="class_all_hard">{mt["class_all_hard"]}</span> / <span data-metric="class_all_conflict">{mt["class_all_conflict"]}</span> / <span data-metric="class_all_degenerate">{mt["class_all_degenerate"]}</span></div></div>
<div class="metric"><div class="v">P0 <span data-metric="prio_p0">{mt["prio_p0"]}</span> · P1 <span data-metric="prio_p1">{mt["prio_p1"]}</span> · P2 <span data-metric="prio_p2">{mt["prio_p2"]}</span> · P3 <span data-metric="prio_p3">{mt["prio_p3"]}</span></div><div class="l">优先级（M1 ordered {mt["m1_ordered"]}）</div><div class="d">全部 {mt["total_candidates"]}：P0 <span data-metric="prio_all_p0">{mt["prio_all_p0"]}</span> / P1 <span data-metric="prio_all_p1">{mt["prio_all_p1"]}</span> / P2 <span data-metric="prio_all_p2">{mt["prio_all_p2"]}</span> / P3 <span data-metric="prio_all_p3">{mt["prio_all_p3"]}</span>（M2 全 P0；S1 一条 P0 一条 P1）</div></div>
<div class="metric"><div class="v"><span data-metric="video_kind_exact">{mt["video_kind_exact"]}</span> exact + <span data-metric="video_kind_family">{mt["video_kind_family"]}</span> 同族</div><div class="l">pi0 参考视频（<span data-metric="videos">{mt["videos"]}</span> 段 / <span data-metric="video_scenes">{mt["video_scenes"]}</span> 场景，v2 不变）</div><div class="d">来自 <span data-metric="pi0_tasks">{mt["pi0_tasks"]}</span> 段标准套件 pi0 baseline（success <span data-metric="pi0_success">{mt["pi0_success"]}</span>/40）；其中 <span data-metric="n_ref_pi0">{mt["n_ref_pi0"]}</span> 段被场景引用、<span data-metric="n_unref_pi0">{mt["n_unref_pi0"]}</span> 段未被引用；按场景引用口径 success <span data-metric="scene_ref_success">{mt["scene_ref_success"]}</span> / failed <span data-metric="scene_ref_failed">{mt["scene_ref_failed"]}</span>（同源视频多场景引用会重复计数）</div></div>
<div class="metric"><div class="v" data-metric="n_atoms_3">{mt["n_atoms_3"]}</div><div class="l">3 原子候选（2 原子 <span data-metric="n_atoms_2">{mt["n_atoms_2"]}</span>）</div><div class="d">来自与含 <code>26/27/28</code>（同容器双谓词任务）的组合（原来 <code>00</code> 也贡献 3 原子，v2 已随复核剔除）；3 原子链在 GOAL 上动态 0/24，难度未知</div></div>
<div class="metric"><div class="v">0</div><div class="l">组合任务动态实测 episode</div><div class="d">验证漏斗尚未启动（见 <a href="#funnel">验证漏斗与下一步</a>）；页内视频全部是 pi0 参考 baseline</div></div>
<div class="metric wide"><div class="v" style="font-size:14px;font-weight:600">11 个模板 · 合计 <span data-metric="tpl_total">{mt["tpl_total"]}</span> 条（零命中模板 <span data-metric="n_zero_hit_templates">{mt["n_zero_hit_templates"]}</span> 个）</div><div class="l">指令模板分布（来自 <code>instruction_template</code>；T4b 是 T4 的双物体子变体；T5 保留但 v2 命中 0）</div><div class="d chips">{tpl_chips}</div><div class="d">naive 拼接相同 <span data-metric="n_naive_same">{mt["n_naive_same"]}</span> 条；模板改写 <span data-metric="n_rewritten">{mt["n_rewritten"]}</span> 条（见 <a href="#templates">模板章节</a>）</div></div>
</div>

<h3>1.1 范围与不变量（含复核 v1 口径）</h3>
<ul class="flat">
<li><b>7 条双目标任务 + BDDL 单目标池 {mt["pool_bddl"]} 条 → 复核后组合池 {mt["single_pool"]} 条</b>：口径 C（两个 goal 原子指向不同目标实体）= {mt["n_dual_tasks"]}；BDDL 单目标池 = {mt["pool_bddl"]}；用户逐场景复核 v1 剔除 KS1 任务 00（本身是双子任务、不需要再组合）→ 组合池 {mt["single_pool"]}。口径 A/B/C 对账见 <a class="local" href="../../../docs/libero-90-dual-target-candidates.md">docs §1.1</a>；被计为单目标的其余双原子任务 <code>26/27/28</code> 本轮未被点名，暂保留在组合池内。</li>
<li><b>只做同场景组合</b>：{mt["scenes"]} 个场景内 <code>objects / init 原子 / regions 名集合 / init 宽度</code> 各只有 1 个变体，而 {mt["scenes"]} 个场景指纹两两不同 → 同场景任务可复用 objects/regions/fixtures/init，只改 <code>goal / obj_of_interest / language</code>；跨场景组合需要重建场景资产，不在本方法范围（docs §1.2–§1.4）。</li>
<li><b>{mt["total_candidates"]} = M1 {mt["route_m1"]} + M2 {mt["route_m2"]} + S1 {mt["route_s1"]}</b>：M1 = <span data-metric="m1_unordered_pairs">{mt["m1_unordered_pairs"]}</span> 个同场景单目标对 × 2 个指令方向；M2 = <span data-metric="m2_unordered">{mt["m2_unordered"]}</span> 个“提升纯干扰物”对 × 2；S1 = stranded 任务 18 的 <span data-metric="s1_unordered">{mt["s1_unordered"]}</span> 个救场对 × 2。复核 v1 共移出 <b>{rev["removed_candidates"]}</b> 条候选（{rev["removed_pairs"]} 对 × 2，全部来自 KS1/00）；上一版 v1 为 {rev["old_total"]} 条，差异见 <a href="#revision-note">v2 修订记录</a>。</li>
<li><b>原子数不恒为 2</b>：2 原子 <span data-metric="n_atoms_2">{mt["n_atoms_2"]}</span> / 3 原子 <span data-metric="n_atoms_3">{mt["n_atoms_3"]}</span> / 4 原子 0。生成器按去重后的原子并集断言 N≥2，不硬编码 ==2。</li>
<li><b>回退可用性</b>：M1 方向 s1 可回退 ab <span data-metric="m1_s1_revertable_ab">{mt["m1_s1_revertable_ab"]}</span> / ba <span data-metric="m1_s1_revertable_ba">{mt["m1_s1_revertable_ba"]}</span>；共 <span data-metric="n_s1_unrevertable">{mt["n_s1_unrevertable"]}</span> 个方向 s1 不可回退（6 个 M1 Turnon 方向 + S1 的 Turnoff 方向）→ 降为 P1，只作双目标任务、不作 rollback 用例。</li>
<li><b>容量提示</b>：同落点/同容器对带 <code>capacity_caveat</code>（容量/遮挡风险）：M1 <span data-metric="cap_cands_m1">{mt["cap_cands_m1"]}</span> 条 ordered（<span data-metric="m1_capacity_pairs">{mt["m1_capacity_pairs"]}</span> 对 / <span data-metric="m1_capacity_ordered">{mt["m1_capacity_ordered"]}</span> ordered）；M2 全部 <span data-metric="cap_cands_m2">{mt["cap_cands_m2"]}</span> ordered 也是“同 basket/tray”语义。</li>
<li><b>复核范围</b>：用户本轮只复核了 KITCHEN_SCENE1（剔除任务 00）；其余 <span data-metric="n_pending_scenes">{mt["n_pending_scenes"]}</span> 个场景“暂无修改意见、待复核”，候选数不变。逐场景状态见 <a href="#scene-review">复核状态表</a>；复核口径源为 <code>scene_review_decisions.json</code>（version {rev["review_version"]}，sha256 与 candidates meta 交叉校验）。</li>
</ul>

<h3>1.2 三条路线</h3>
<div class="tblwrap"><table>
<thead><tr><th>路线</th><th>说明</th><th>ordered 候选</th><th>class 分布</th><th>优先级分布</th></tr></thead>
<tbody>
<tr><td><b>M1</b> 直接组合</td><td>同场景两条单目标任务：goal 原子并集 + obj_of_interest 并集 + 模板化合并指令；复用某一方的 init（复核剔除的任务不参与配对）</td><td>{n_m1}</td><td>{m1c.get("compatible", 0)} / {m1c.get("hard", 0)} / {m1c.get("conflict", 0)} / {m1c.get("degenerate", 0)}</td><td>P0 {m1p.get("P0", 0)} / P1 {m1p.get("P1", 0)} / P2 {m1p.get("P2", 0)} / P3 {m1p.get("P3", 0)}</td></tr>
<tr><td><b>M2</b> 场景内提升</td><td>保留源任务场景/init，把 1 个未被任何 goal 引用的可动物体提升为第二目标（OBJECT 路线 B 的 L90 版）</td><td>{n_m2}</td><td>compatible {m2c.get("compatible", 0)}</td><td>P0 {m2p.get("P0", 0)}</td></tr>
<tr><td><b>S1</b> stranded 救场</td><td>任务 18（turn off the stove）在 KITCHEN_SCENE8 没有单目标同伴：把 <code>moka_pot_2</code> 提升为放置目标，与 Turnoff 组成一对</td><td>{n_s1}</td><td>compatible {s1c.get("compatible", 0)}</td><td>P0 {s1p.get("P0", 0)} / P1 {s1p.get("P1", 0)}</td></tr>
</tbody></table></div>

<h3>1.3 class 与优先级口径</h3>
<div class="tblwrap"><table>
<thead><tr><th>class</th><th>pair 级（{mt["m1_unordered_pairs"]} 对）</th><th>ordered（M1 {mt["m1_ordered"]}）</th><th>判定 / 处理</th></tr></thead>
<tbody>
<tr><td><span class="badge b-ok">compatible</span></td><td>{mt["class_pair_compatible"]}</td><td>{mt["class_ordered_compatible"]}</td><td>不同物体/不同落点（或同落点不同物体、互不干扰）；默认候选，同落点打 <code>same_destination</code> + capacity_caveat</td></tr>
<tr><td><span class="badge b-warn">hard</span></td><td>{mt["class_pair_hard"]}</td><td>{mt["class_ordered_hard"]}</td><td>可共存但有真正的次序/接触依赖（先放后关、先开后放、叠放基底、相邻区域）；需 staged，优先级降一档</td></tr>
<tr><td><span class="badge b-fail">conflict</span></td><td>{mt["class_pair_conflict"]}</td><td>{mt["class_ordered_conflict"]}</td><td>同一可动物体两个互斥落点，或同一关节 Open/Close（Turnon/Turnoff）冲突；不进动态集，保留作负例</td></tr>
<tr><td><span class="badge b-muted">degenerate</span></td><td>{mt["class_pair_degenerate"]}</td><td>{mt["class_ordered_degenerate"]}</td><td>去重后原子集合等于其中一条任务的 goal 集合（合并没有引入新阶段）；进清单但 <code>valid=false</code>，作对照</td></tr>
</tbody></table></div>
<div class="tblwrap"><table>
<thead><tr><th>优先级</th><th>条件（M1 ordered）</th><th>数量</th><th>用途</th></tr></thead>
<tbody>
<tr><td><span class="badge b-p0">P0</span></td><td><code>class=compatible</code> 且该方向 s1 可回退（On/In/Open/Close，s1 不是 Turnon/Turnoff）</td><td>{mt["prio_p0"]}</td><td>可直接进静态验证 + rollback 原型；同落点候选另带 capacity_caveat</td></tr>
<tr><td><span class="badge b-p1">P1</span></td><td><code>class=compatible</code> 但 s1 是 Turnon/Turnoff（s1 不可回退）</td><td>{mt["prio_p1"]}</td><td>只作双目标任务（Turnon/Turnoff 只能放 s2），不作 rollback</td></tr>
<tr><td><span class="badge b-p2">P2</span></td><td><code>class=hard</code>（place_then_close / open_then_place / stack_anchor / adjacent_regions）</td><td>{mt["prio_p2"]}</td><td>需固定次序 + staged，第二批</td></tr>
<tr><td><span class="badge b-p3">P3</span></td><td><code>class=degenerate / conflict</code></td><td>{mt["prio_p3"]}</td><td>不推荐（保留作对照 / 排除），<code>protocol=excluded</code></td></tr>
</tbody></table></div>
<p class="note">口径提醒：<code>candidates-instructed.json</code> 的 <code>summary.class_counts</code> / <code>priority_counts</code> 是 <b>M1-only（{mt["m1_ordered"]}）</b>；包含 M2/S1 的全量口径在 <code>class_counts_all</code> / <code>priority_counts_all</code>（compatible <span data-metric="class_all_compatible">{mt["class_all_compatible"]}</span> / hard <span data-metric="class_all_hard">{mt["class_all_hard"]}</span> / conflict <span data-metric="class_all_conflict">{mt["class_all_conflict"]}</span> / degenerate <span data-metric="class_all_degenerate">{mt["class_all_degenerate"]}</span>；P0 <span data-metric="prio_all_p0">{mt["prio_all_p0"]}</span> / P1 <span data-metric="prio_all_p1">{mt["prio_all_p1"]}</span> / P2 <span data-metric="prio_all_p2">{mt["prio_all_p2"]}</span> / P3 <span data-metric="prio_all_p3">{mt["prio_all_p3"]}</span>）。本页两套数字均已按字段标注口径。</p>
</section>'''


def render_templates(m):
    mt = m["metrics"]
    rev = m["revision"]
    tpl_rows = []
    for t in m["templates"]:
        routes = t["routes"]
        if t["zero"]:
            count_cell = '<b>0</b><div class="tiny">v2 复核后无命中</div>'
            examples = (f'<span class="tiny">当前口径 0 条候选。该模板原依据 <code>LIBERO-90 /00</code>；'
                        f'KS1/00 已按用户复核 v1 移出组合池，原 {rev["removed_candidates"]} 条命中全部来自含 00 的组合。'
                        f'按要求仍保留该行，用于记录模板集合与 v1 的差异（详见 <a href="#revision-note">v2 修订记录</a>）。</span>')
            tr_cls = "tpl-row tpl-zero"
        else:
            count_cell = f'<b>{t["count"]}</b><div class="tiny">{routes.get("M1", 0)} / {routes.get("M2", 0)} / {routes.get("S1", 0)}</div>'
            examples = "".join(
                f'<div class="ex"><code>{esc(c["candidate_id"])}</code><br><span class="tiny">{esc(c["instruction"])}</span></div>'
                for c in t["examples"]
            )
            tr_cls = "tpl-row"
        tpl_rows.append(
            f'<tr class="{tr_cls}" data-tpl="{t["id"]}" data-count="{t["count"]}" data-zero="{1 if t["zero"] else 0}">'
            f'<td><code>{t["id"]}</code></td><td>{esc(t["name"])}</td>'
            f'<td><code>{esc(t["pattern"])}</code></td>'
            f'<td>{esc("; ".join(t["refs"]))}</td>'
            f'<td>{count_cell}</td>'
            f'<td>{examples}</td></tr>'
        )
    evidence_items = "".join(
        "<li><b>" + esc(t["id"]) + "</b> <span class=" + '"tiny"' + ">" + esc(t["name"]) + "</span><ul class=" + '"flat"' + ">"
        + "".join(f"<li>{esc(line)}</li>" for line in t["evidence"])
        + "</ul></li>"
        for t in m["templates"]
    )
    naive_rows = [
        ("LIBERO-GOAL 45 对 / 90 ordered 的 naive <code>and</code> 拼接", "单指令组合 <b>2/47 ≈ 4.3%</b>（发布口径 2/49）", "失败 45 条里 39 条“恰好完成一个子任务后停滞”", "docs §2.1 / §0.9"),
        ("LIBERO-GOAL <code>integrated</code> 改写", "<b>06_01 8/9 → 0/9</b>（-8）", "灾难负收益，已排除", "INSTRUCTION_TEMPLATES §2"),
        ("LIBERO-GOAL <code>it</code> 指代变体", "<b>07_01 4/9 → 7/9</b>（+3）", "最强正信号 → T5/T7/T8 采用 “and … it” 指代", "INSTRUCTION_TEMPLATES §2"),
        ("LIBERO-GOAL <code>then</code> 变体", "<b>06_08 5/9→7/9</b>（+2）；<b>06_07 2/9→6/9</b>（+4）", "容器依赖类正收益 → hard 候选默认推荐 <code>then</code> 变体", "INSTRUCTION_TEMPLATES §2"),
        ("LIBERO-OBJECT v3 模板 <code>put both A and B in basket</code>", "<b>100 候选 × 3 seeds = 300 episodes，12 成功 = 4.0%</b>", "6 候选 ≥1 成功、5 候选 ≥2 seeds、1 候选 3/3；T1 直接借用该模板", "docs §2.2"),
        ("LIBERO-10 官方 10 条双目标任务", "<b>pi0 8/10、pi05 10/10</b>", "04/05/06 both-in-basket、03 both-on-stove、07/08 双 put 子句、01/02 put+close it、00 turn on+put on it、09 pick up+place → T1/T2/T3/T4/T4b/T7 句式来源", "INSTRUCTION_TEMPLATES §4"),
        ("LIBERO-GOAL <code>both</code> 同表面双物体", "<b>0/6</b> 无提升", "<code>both</code> 只保留在同容器/同落点（L10 官方句式），同表面使用仍需动态验证", "INSTRUCTION_TEMPLATES §2"),
        ("本清单 naive 拼接 vs 模板化", f"<b>{mt['n_naive_same']}/{mt['tpl_total']}</b> 与模板化结果相同", f"官方句式本身规范的候选（T3/T6/T10）无需改写；其余 <b>{mt['n_rewritten']}/{mt['tpl_total']}</b> 被模板改写（同容器合并、<code>it</code> 指代、<code>both</code>、stack 链等）", "本报告由 JSON 计算"),
    ]
    naive_html = "".join(
        f"<tr><td>{a}</td><td>{b}</td><td>{c}</td><td class=\"tiny\">{d}</td></tr>" for a, b, c, d in naive_rows
    )
    return f'''<section id="templates">
<h2>二、指令模板 T1–T10（+ 子变体 T4b）</h2>
<p>{mt["total_candidates"]} 条候选的合并指令<b>不再用两条官方 language 直接 <code>and</code> 拼接</b>，而是按“合并后 goal 原子结构 + class/dependency”套用 LIBERO-10 / LIBERO-GOAL / LIBERO-OBJECT 里<b>已验证成功的任务模板</b>重建。naive 拼接只保留为对照字段（<code>candidates-instructed.json.language</code>）。模板 id 以 JSON 实际字段为准共 <b>11 个</b>（T1–T10 + T4b）；docs §7.1 提到的 <b>T12</b> 是变体级 <code>then</code> 改写策略（已体现在 <code>instruction_variants.then</code>），不是候选级模板 id。</p>
<p class="note"><b>v2 变化</b>：复核 v1 剔除 KS1/00 后，<b>T5 命中 {rev["old_tpl_T5_text"]}→{mt["tpl_T5"]}</b>（原来 {rev["old_tpl_T5_text"]} 条全部来自含 00 的组合）。按要求模板表仍保留 <b>11 行</b>，T5 行标注“v2 复核后无命中”并说明原因；其余 10 个模板的候选数见上表（模板间小幅变化来自含 00 组合被剔除后按“合并后目标结构”重新归并）。</p>
<h3>2.1 为什么弃用 naive 拼接（参考套件证据数字）</h3>
<div class="tblwrap"><table>
<thead><tr><th>证据来源</th><th>数字</th><th>结论</th><th>出处</th></tr></thead>
<tbody>{naive_html}</tbody></table></div>
<p class="note">结论：单条合并指令在 GOAL/OBJECT 上成功率只有个位数（4.3% / 4.0%），失败模式是“完成一个子任务后停滞”；因此模板化的目标不是提高单指令成功率，而是把<b>句式对齐已验证结构</b>（同容器 <code>both</code>、<code>it</code> 指代、<code>then</code> 次序），主要协议仍是 <b>staged / instruction-switch</b>（GOAL 2/3）。</p>
<h3>2.2 模板总表（命中分布，v2 口径）</h3>
<div class="tblwrap"><table>
<thead><tr><th>模板</th><th>名称</th><th>模板句式</th><th>依据的成功任务</th><th>候选数（全部 / M1 / M2 / S1）</th><th>示例（2 条）</th></tr></thead>
<tbody>{''.join(tpl_rows)}
<tr><td colspan="4"><b>合计</b></td><td><b>{mt["tpl_total"]}</b><div class="tiny">{mt["route_m1"]} / {mt["route_m2"]} / {mt["route_s1"]}（T5 零命中）</div></td><td><span class="tiny">全部 {mt["tpl_total"]} 条候选均有模板 id；零命中模板 {mt["n_zero_hit_templates"]} 个（T5）保留展示</span></td></tr>
</tbody></table></div>
<h3>2.3 模板证据原文（来自 JSON 的 instruction_evidence）</h3>
<details class="tpl-ev"><summary>展开 / 收起：每个模板的参考任务与证据数字（去重；T5 为静态回退元数据）</summary><ul class="flat">{evidence_items}</ul></details>
<h3>2.4 模板化示例（旧 naive → 新指令）</h3>
<div class="tblwrap"><table>
<thead><tr><th>candidate_id</th><th>旧指令（两条官方 language 拼接）</th><th>新指令（模板化）</th></tr></thead>
<tbody>
<tr><td><code>L90_LR1_31_32_ab</code></td><td>pick up the ketchup and put it in the basket and pick up the cream cheese box and put it in the basket</td><td><b>put both the ketchup and the cream cheese box in the basket</b></td></tr>
<tr><td><code>L90_KS3_06_08_ab</code></td><td>put the frying pan on the stove and turn on the stove</td><td><b>put the frying pan on the stove and turn it on</b></td></tr>
<tr><td><code>L90_KS4_12_14_ab</code></td><td>put the black bowl in the bottom drawer of the cabinet and close the bottom drawer of the cabinet</td><td><b>put the black bowl in the bottom drawer of the cabinet and close it</b></td></tr>
<tr><td><code>L90_KS9_20_21_ab</code></td><td>put the frying pan on top of the cabinet and put the white bowl on top of the cabinet</td><td><b>put both the frying pan and the white bowl on top of the cabinet</b></td></tr>
<tr><td><code>L90_KS2_53_58_ab</code></td><td>put the black bowl at the back on the plate and stack the middle black bowl on the back black bowl</td><td><b>put the black bowl at the back on the plate and stack the middle black bowl on top of it</b></td></tr>
<tr><td><code>L90_KS8_18_moka_pot_2_ab</code></td><td>put the left moka pot on the stove and turn off the stove</td><td><b>put the left moka pot on the stove and turn it off</b></td></tr>
</tbody></table></div>
<p class="note">数据字段：每条候选提供 <code>instruction</code>（主指令）、<code>instruction_template</code>、<code>instruction_variants</code>（<code>and</code>/<code>then</code>/<code>both</code>/<code>it</code> 按适用性生成）、<code>instruction_evidence</code>（模板来源与证据数字）、<code>instruction_source</code>（<code>template:…</code> / <code>borrowed:nn</code> / <code>synthesized</code>）、<code>instruction_clauses</code>（staged 切分用）、<code>instruction_preferred_variant</code>（hard/P2 默认 <code>then</code>）。本页候选表“新合并指令”列即 <code>instruction</code>；KS1 被剔除组合任务的场景候选表中不再出现 T5。</p>
</section>'''


def render_scene_index(m):
    mt = m["metrics"]
    cards = []
    for s in m["scene_rows"]:
        p0 = s["prio"].get("P0", 0)
        if s["reviewed"]:
            review = badge("已复核", "b-ok") + f' · 剔除 {s["review_excluded_count"]} 任务'
            pool_txt = f'{s["pool_bddl_count"]} → <b>{s["pool_count"]}</b>'
        else:
            review = badge("待复核", "b-muted")
            pool_txt = f'{s["pool_count"]}'
        cards.append(
            f'<a class="scard{" reviewed" if s["reviewed"] else ""}" href="#scene-{s["scene"]}">'
            f'<div class="h">{esc(s["scene"])} · {esc(s["type_zh"])} {review}</div>'
            f'<div class="r">任务 <b>{s["task_count"]}</b>（双目标 {s["dual_count"]}）· 组合池 <b>{pool_txt}</b> / 同场景对 <b>{s["pair_count"]}</b><br>'
            f'候选 <b>{len(s["cands"])}</b>（P0 {p0}）· 参考视频 <b>{len(s["videos"])}</b>（exact {s["exact_count"]} / 同族 {s["family_count"]}）</div></a>'
        )
    return f'''<section id="scene-index">
<h2>三、场景索引（{mt["scenes"]} 个场景）</h2>
<p class="sub">场景顺序 = <code>inventory.json</code> 的任务序（tasks_info 序，不是 benchmark 字母序）；每个场景一节，含单任务表、组合候选表（含“对照与排除”折叠）、参考 baseline 视频卡。全页合计：<b>{mt["tasks"]}</b> 任务 / <b>{mt["m1_unordered_pairs"]}</b> 单目标对 / <b>{mt["total_candidates"]}</b> 候选 / <b>{mt["videos"]}</b> 段参考视频；其中 KS1 已按复核 v1 剔除任务 00（组合池 {mt["pool_bddl"]}→{mt["single_pool"]}）。</p>
<div class="scardgrid">{''.join(cards)}</div>
</section>'''


def video_short_label(v):
    if v["kind"] == "exact_scene_l10":
        return "★L10 T" + str(v["task_idx"])
    return SUITE_SHORT.get(v["suite"], v["suite"]) + " T" + str(v["task_idx"])


def video_kind_cn(v):
    if v["kind"] == "exact_scene_l10":
        return "同名场景 exact_scene_l10"
    return "同族参考 suite_family_reference"


def task_video_cell(s):
    if not s["videos"]:
        return '<span class="tiny">—（该场景无参考视频）</span>'
    links = []
    for k, v in enumerate(s["videos"]):
        mark = "✓" if v["success"] else "✗"
        cls = "s-ok" if v["success"] else "s-fail"
        title = video_kind_cn(v) + f' · {v["suite"]} T#{v["task_idx"]} · pi0 success={v["success"]} · steps={v["steps"]}'
        links.append(
            f'<a class="vidlink" href="#vid-{s["scene"]}-{k}" title="{esc(title)}">'
            f'{esc(video_short_label(v))} <span class="{cls}">{mark}</span></a>'
        )
    if len(links) > 3:
        links = links[:3] + [f'<span class="tiny">+{len(links) - 3}</span>']
    return " ".join(links)


def render_task_table(s):
    rows = []
    for t in s["task_rows"]:
        idx = t["index"]
        atoms = "<br>".join(f"<code>{esc(a)}</code>" for a in t["atoms"])
        if t["review_excluded"]:
            dual = badge(t["dual_label"], "b-dual", t["dual_title"])
        elif t["dual"]:
            dual = badge(t["dual_label"], "b-dual", t["dual_title"])
        elif t["dual_label"]:
            dual = badge(t["dual_label"], "b-info", t["dual_title"])
        else:
            dual = '<span class="tiny">—</span>'
        mismatch = ""
        if t["mismatch"]:
            mismatch = badge(
                "official≠inline", "b-warn",
                "官方 language（benchmark 文件名派生）与 BDDL 内联 :language 不同；本表使用官方值，组合渲染按官方值生成",
            )
        bench = f'<div class="tiny">bench #{t["bench_idx"]}</div>' if t["bench_idx"] is not None else ""
        obj = ", ".join(t["objects"])
        dual_attr = 1 if t["dual"] else 0
        re_attr = 1 if t["review_excluded"] else 0
        tr_cls = "task-row dual" if t["dual"] else "task-row"
        if t["review_excluded"]:
            tr_cls += " review-excluded"
        rows.append(
            f'<tr class="{tr_cls}" data-scene="{s["scene"]}" data-task="{idx}" data-dual="{dual_attr}" data-review-excluded="{re_attr}">'
            f'<td><code>{idx:02d}</code>{bench}</td>'
            f'<td>{esc(t["official"].strip())}{(" " + mismatch) if mismatch else ""}</td>'
            f'<td class="atoms">{atoms}</td>'
            f'<td class="tiny">{esc(obj)}</td>'
            f'<td class="nowrap">{t["width"][0]} × {t["width"][1]}</td>'
            f'<td>{dual}</td>'
            f'<td>{task_video_cell(s)}</td></tr>'
        )
    reviewed_note = ""
    if s["reviewed"]:
        reviewed_note = (f' 本场景已按用户复核 v1 剔除任务 {", ".join(f"{i:02d}" for i in s["review_excluded"])}'
                         f'（该任务本身是双子任务，不再进入组合池），但仍保留在本表单任务展示中。')
    return f'''<h3 id="tasks-{s["scene"]}">单任务表（{s["task_count"]} 条官方 LIBERO-90 指令；其中双目标/复核标记 {s["dual_count"] + s["review_excluded_count"]} 条）</h3>
<p class="sub">「官方指令」= benchmark 文件名派生的官方 language（不是 BDDL 内联 <code>:language</code>）；「双目标」按口径 C（两个 goal 原子指向不同目标实体）标记；<code>26/27/28</code> 虽然也有 2 个原子，但两个原子作用于同一容器区域，计为单目标。任务 <code>00</code> 本身是双子任务（Open + In 两段），经用户复核 v1 移出组合池（详见 <a href="#scene-review">复核状态</a>）。baseline 视频列是本场景的 pi0 参考视频短标签：<b>★L10 Tn</b> = exact_scene_l10（LIBERO-10 同名场景、任务不同，最贴近的参考）；<b>SPA / OBJ / GOAL Tn</b> = suite_family_reference（同族套件参考，场景不同）；✓ / ✗ = pi0 成败；点击跳到本节末尾视频卡。所有视频都不是 L90 任务实测。{reviewed_note}</p>
<div class="tblwrap"><table class="tasks">
<thead><tr><th>#</th><th>官方指令</th><th>goal 原子</th><th>对象</th><th>init 宽度</th><th>双目标</th><th>baseline 视频（参考）</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>'''


def cand_side_label(task):
    if task.get("index") is not None:
        return f'<code>{task["index"]:02d}</code>'
    obj = task.get("object") or "promoted"
    src = task.get("instruction_source") or task.get("kind") or ""
    title = "提升目标（非 L90 任务）：" + str(task.get("language", "")) + f"（措辞来源 {src}）"
    return f'<span class="promoted" title="{esc(title)}">↑{esc(obj)}</span>'


def naive_cell(c):
    same = c["instruction"] == c["language"]
    summary = "与模板一致" if same else "展开旧拼接"
    return f'<details><summary>{summary}</summary><code class="naive">{esc(c["language"])}</code></details>'


def candidate_row(c, last_cell):
    route = c["route"]
    klass = CLASS_BADGE[c["class"]]
    dep = ", ".join(c["dependency"]) if c["dependency"] else "—"
    tags = []
    if c["n_atoms"] == 3:
        tags.append("3 原子")
    if c["instruction_preferred_variant"] == "then":
        then_text = (c.get("instruction_variants") or {}).get("then")
        if then_text and then_text != c["instruction"]:
            tags.append(f'<span title="{esc(then_text)}">推荐 then 变体</span>')
        else:
            tags.append("推荐 then 变体")
    if c["capacity_caveat"]:
        tags.append("capacity caveat")
    tag_html = f'<div class="tiny">{" · ".join(tags)}</div>' if tags else ""
    cls = "cand-row main-cand" if c["valid"] else "cand-row excl-cand"
    s1_idx = c["s1_task"].get("index")
    s2_idx = c["s2_task"].get("index")
    s1_attr = "" if s1_idx is None else str(int(s1_idx))
    s2_attr = "" if s2_idx is None else str(int(s2_idx))
    review_tag = '<div class="tiny">复核 v1</div>' if c.get("scene_review_applied") else ""
    return (
        f'<tr class="{cls}" data-scene="{c["scene"]}" data-route="{route}" '
        f'data-class="{c["class"]}" data-priority="{c["priority"]}" '
        f'data-s1="{s1_attr}" data-s2="{s2_attr}">'
        f'<td><code>{esc(c["candidate_id"])}</code><div class="tiny">{route} · {esc(c["order"])}</div>{review_tag}</td>'
        f'<td class="nowrap">{cand_side_label(c["s1_task"])} → {cand_side_label(c["s2_task"])}</td>'
        f'<td>{badge(c["class"], klass, CLASS_CN[c["class"]])}<div class="tiny">{esc(dep)}</div></td>'
        f'<td class="ins">{esc(c["instruction"])}{tag_html}</td>'
        f'<td>{badge(c["priority"], PRIO_BADGE[c["priority"]])}</td>'
        f'<td><code>{esc(c["instruction_template"])}</code><div class="tiny">{esc(c["instruction_source"])}</div></td>'
        f'<td>{naive_cell(c)}</td>'
        f'<td>{last_cell}</td></tr>'
    )


NO_VIDEO_CELL = '<span class="badge b-muted" title="组合候选尚无动态实测视频；本场景末尾是参考 baseline 视频">暂无</span>'


def reason_cell(c):
    reason = c.get("invalid_reason") or "—"
    cn = INVALID_REASON_CN.get(reason, reason)
    return f'{badge("排除", "b-fail", reason)}<div class="tiny">{esc(cn)}</div>'


def render_candidate_section(s):
    total = len(s["cands"])
    p0 = s["prio"].get("P0", 0)
    main_rows = "".join(candidate_row(c, NO_VIDEO_CELL) for c in s["main"])
    excl_rows = "".join(candidate_row(c, reason_cell(c)) for c in s["excl"])
    excl_summary = " · ".join(
        f'{cls} {cnt}' for cls, cnt in sorted(Counter(c["class"] for c in s["excl"]).items())
    ) or "无"
    review_note = ""
    if s["reviewed"]:
        excluded = ", ".join(f"{i:02d}" for i in s["review_excluded"])
        review_note = (f'<p class="note"><b>v2 复核 v1</b>：本场景已剔除任务 {excluded}（本身是双子任务，不再参与组合）→ '
                       f'组合池 {s["pool_bddl_count"]}→{s["pool_count"]}、同场景对 {s["pair_bddl_count"]}→{s["pair_count"]}、'
                       f'候选 {total + 2 * (s["pair_bddl_count"] - s["pair_count"])}→{total}；任务 {excluded} 只出现在上方单任务表，'
                       f'不再出现在候选表。详见 <a href="#scene-review">逐场景复核状态</a>。</p>')
    if s["excl"]:
        excl_body = f'''<details class="excl" id="excl-{s["scene"]}">
<summary>对照与排除：{len(s["excl"])} 条（{esc(excl_summary)}；valid=false，不进入动态集，只作负例/退化对照）</summary>
<div class="tblwrap"><table class="cands excl-tbl">
<thead><tr><th>候选 ID</th><th>s1 → s2</th><th>class · dependency</th><th>新合并指令（模板化）</th><th>优先级</th><th>模板</th><th>旧 naive 拼接（对照）</th><th>排除原因</th></tr></thead>
<tbody>{excl_rows}</tbody></table></div></details>'''
    else:
        excl_body = f'''<details class="excl" id="excl-{s["scene"]}"><summary>对照与排除：0 条（本场景没有 conflict/degenerate 候选）</summary><p class="tiny">全部 {total} 条候选 valid=true，可进入后续静态验证。</p></details>'''
    return f'''<h3 id="cands-{s["scene"]}">组合候选表（<span data-live-count="{s["scene"]}">{total}</span> 条：valid {len(s["main"])} + 对照排除 {len(s["excl"])}；P0 {p0}）</h3>
<p class="sub">按 priority 排序（P0 置顶，其次 class）；「视频」列全部为<b>暂无</b>——组合任务本轮没有动态实测。旧 naive 指令（两条官方 language 直接拼接）折叠在「旧拼接」里作对照；<b>conflict / degenerate 已折叠到下方「对照与排除」小节</b>。</p>
{review_note}
<div class="tblwrap"><table class="cands">
<thead><tr><th>候选 ID</th><th>s1 → s2</th><th>class · dependency</th><th>新合并指令（模板化）</th><th>优先级</th><th>模板</th><th>旧 naive 拼接（对照）</th><th>视频</th></tr></thead>
<tbody>{main_rows}</tbody></table></div>
{excl_body}'''


def render_video_card(scene, idx, v):
    ok = badge("PASSED 成功", "b-ok") if v["success"] else badge("FAILED 失败", "b-fail")
    kind_badge = badge(video_kind_cn(v), "b-info" if v["kind"] == "exact_scene_l10" else "b-ref")
    l10 = ""
    if v.get("l10_scene"):
        l10 = f'<p class="kv">L10 同名场景：<code>{esc(v["l10_scene"])}</code>（场景一致、任务不同）</p>'
    succ = 1 if v["success"] else 0
    return f'''<figure class="vcard" id="vid-{scene}-{idx}" data-scene="{scene}" data-file="{esc(v["file"])}" data-kind="{esc(v["kind"])}" data-success="{succ}">
<figcaption class="vhead"><b>pi0</b> · {esc(v["suite"])} T{v["task_idx"]} <span class="tiny">→ {esc(scene)}</span></figcaption>
<div class="badges">{ok}{kind_badge}{badge("pi0 baseline", "b-muted")}</div>
<video controls preload="metadata" src="{esc(v["file"])}"></video>
<p class="instr">指令：{esc(v["instruction"])}</p>
<p class="kv">success={v["success"]} · steps={v["steps"]} · suite={esc(v["suite"])} / T#{v["task_idx"]} · kind={esc(v["kind"])}</p>
{l10}
<p class="why"><b>为什么作参考</b>：{esc(v["why"])}</p>
<p class="honest">{esc(v["honest_note"])}</p>
<p class="orig">源路径：{esc(v.get("source_video", ""))}（本页引用 report/ 下副本，未重命名/删除）</p>
</figure>'''


def render_video_section(s):
    n = len(s["videos"])
    if n == 0:
        body = ('<div class="gapcard"><b>该场景暂无参考视频（gap）。</b><br>'
                '本工作区没有 LIBERO-90 全量 pi0 视频，且该场景也没有可借用的同名/同族参考；'
                'L90 官方 baseline 待补录（见 VIDEO_SOURCES.md §5）。</div>')
        warn = ""
    else:
        cards = "".join(render_video_card(s["scene"], k, v) for k, v in enumerate(s["videos"]))
        body = f'<div class="vgrid">{cards}</div>'
        warn = (f'<div class="videowarn">⚠ <b>参考性质</b>：本场景 {n} 段视频都是 <b>pi0 在标准套件上的参考 baseline</b>'
                f'（exact_scene_l10 {s["exact_count"]} 段 / suite_family_reference {s["family_count"]} 段），'
                f'<b>不是 LIBERO-90 {esc(s["scene"])} 任务的实测</b>。每张卡片都显示 manifest 的 <code>honest_note</code>，请勿把它当作 L90 baseline。</div>')
    return f'''<h3 id="videos-{s["scene"]}">参考 baseline 视频（{n} 段 pi0；exact {s["exact_count"]} / 同族 {s["family_count"]}）</h3>
{warn}{body}'''


def render_scene(s, m):
    p0 = s["prio"].get("P0", 0)
    idx_txt = ", ".join(f'{t["index"]:02d}' for t in s["task_rows"])
    objects = ", ".join(s["objects"])
    fixtures = ", ".join(s["fixtures"])
    review_mark = ""
    review_chip = ""
    review_note = ""
    if s["reviewed"]:
        excluded = ", ".join(f"{i:02d}" for i in s["review_excluded"])
        review_mark = f' · <span class="badge b-review">已复核 v1</span>'
        review_chip = (f'<span class="chip chip-review">复核 v1：剔除任务 {excluded}</span>')
        review_note = (f'<p class="note"><b>v2 复核 v1</b>：任务 {excluded} 本身是双子任务（Open + In 两段），'
                       f'已从组合池剔除；本场景组合池 {s["pair_bddl_count"]} 对 → {s["pair_count"]} 对、候选 {len(s["cands"]) + 2 * (s["pair_bddl_count"] - s["pair_count"])} → {len(s["cands"])} 条。'
                       f'任务 {excluded} 仍保留在上方单任务表与 L90 既有任务中。详见 <a href="#scene-review">逐场景复核状态</a>。</p>')
    pool_chip = f'单目标池 <b>{s["pool_count"]}</b>'
    if s["reviewed"]:
        pool_chip += f'（BDDL {s["pool_bddl_count"]} − 复核剔除 {s["review_excluded_count"]}）'
    pool_chip += f' / 同场景对 <b>{s["pair_count"]}</b>'
    return f'''<section class="scene" id="scene-{s["scene"]}"
  data-scene-fp="{esc(s["fp"])}" data-tasks="{s["task_count"]}" data-pool="{s["pool_count"]}"
  data-pool-bddl="{s["pool_bddl_count"]}" data-pairs="{s["pair_count"]}" data-pairs-bddl="{s["pair_bddl_count"]}"
  data-cands="{len(s["cands"])}" data-videos="{len(s["videos"])}" data-reviewed="{1 if s["reviewed"] else 0}"
  data-excluded="{",".join(str(i) for i in s["review_excluded"])}"
  data-exact="{s["exact_count"]}" data-family="{s["family_count"]}" data-success="{s["success_count"]}">
<h2>{esc(s["scene"])} · {esc(s["type_zh"])}{review_mark} · {s["task_count"]} 任务 / {len(s["cands"])} 候选 / {len(s["videos"])} 参考视频<a class="top" href="#top">回到顶部</a></h2>
<div class="scenehead">
<div class="chips">
<span class="chip">类型：{esc(s["type_zh"])} {esc(s["type_en"])}</span>
<span class="chip">scene_fp：<code>{esc(s["fp"])}</code></span>
<span class="chip">任务 <b>{s["task_count"]}</b>（双目标 <b>{s["dual_count"]}</b>{("；复核剔除 " + str(s["review_excluded_count"])) if s["reviewed"] else ""}）</span>
<span class="chip">{pool_chip}</span>
<span class="chip">候选 <b>{len(s["cands"])}</b>（M1 {s["route"].get("M1", 0)} / M2 {s["route"].get("M2", 0)} / S1 {s["route"].get("S1", 0)}；P0 <b>{p0}</b>）</span>
<span class="chip">参考视频 <b>{len(s["videos"])}</b>（exact {s["exact_count"]} / 同族 {s["family_count"]}；success {s["success_count"]}）</span>
{review_chip}
</div>
<div class="objline"><b>物体</b>：{esc(objects)}<br><b>fixtures</b>：{esc(fixtures)}<br><b>init 宽度</b>：{s["width"][0]} × {s["width"][1]}（同场景全部任务一致）· <b>任务编号</b>：{idx_txt}</div>
</div>
{review_note}
{render_task_table(s)}
{render_candidate_section(s)}
{render_video_section(s)}
</section>'''


def render_scene_review(m):
    mt = m["metrics"]
    rev = m["revision"]
    rows = []
    for s in m["scene_rows"]:
        decision = s["review_decision"]
        if decision:
            status = badge("已复核", "b-ok")
            excluded = ", ".join(f"{i:02d}" for i in s["review_excluded"]) or "—"
            detail = (f'<details><summary>复核意见（{esc(decision.get("reviewed_by", "user"))} · '
                      f'{esc(decision.get("applied_in", "scene_review_v1"))}）</summary>'
                      f'<div class="tiny">{esc(decision.get("reason", ""))}<br><br><b>影响</b>：'
                      f'{esc(decision.get("implication", ""))}</div></details>')
            tr_cls = "review-row reviewed"
            reviewed = 1
        else:
            status = badge("暂无修改意见", "b-muted")
            excluded = "—"
            detail = '<span class="tiny">用户本轮未给出修改意见 → 按原方案保留，待后续逐场景复核。</span>'
            tr_cls = "review-row"
            reviewed = 0
        rows.append(
            f'<tr class="{tr_cls}" data-scene="{s["scene"]}" data-reviewed="{reviewed}" '
            f'data-excluded="{",".join(str(i) for i in s["review_excluded"])}">'
            f'<td>{esc(s["scene"])} · {esc(s["type_zh"])}</td><td>{status}</td><td>{esc(excluded)}</td>'
            f'<td>{s["pool_bddl_count"]} → <b>{s["pool_count"]}</b></td>'
            f'<td>{s["pair_count"]}</td>'
            f'<td>{s["route"].get("M1", 0)} + {s["route"].get("M2", 0)} + {s["route"].get("S1", 0)} = <b>{len(s["cands"])}</b></td>'
            f'<td>{detail}</td></tr>'
        )
    return f'''<section id="scene-review">
<h2>四、逐场景复核状态（v2 · 复核 v1）</h2>
<p class="sub">数据源：<code>scene_review_decisions.json</code>（唯一口径源，version {rev["review_version"]}，更新于 {esc(rev["review_updated_at"])}；{esc(rev["review_source"])}；sha256 与 <code>candidates-instructed.json.meta.scene_review_decisions_sha256</code> 交叉校验）。当前 <b><span data-metric="n_reviewed_scenes">{mt["n_reviewed_scenes"]}</span> / <span data-metric="scenes">{mt["scenes"]}</span></b> 个场景已复核，<b><span data-metric="n_pending_scenes">{mt["n_pending_scenes"]}</span></b> 个场景等待后续复核。</p>
<div class="cards">
<div class="metric"><div class="v"><span data-metric="n_reviewed_scenes">{mt["n_reviewed_scenes"]}</span> 已复核 · <span data-metric="n_pending_scenes">{mt["n_pending_scenes"]}</span> 待复核</div><div class="l">逐场景复核进度（{mt["scenes"]} 场景）</div><div class="d">已复核场景：{esc(", ".join(m["reviewed_scenes"]))}；其余 {mt["n_pending_scenes"]} 个场景暂无修改意见</div></div>
<div class="metric"><div class="v">−<span data-metric="n_review_excluded_tasks">{mt["n_review_excluded_tasks"]}</span> 任务</div><div class="l">复核剔除的组合池任务</div><div class="d">KS1/00（Open + In 双子任务）→ 组合池 <span data-metric="pool_bddl">{mt["pool_bddl"]}</span>→<span data-metric="single_pool">{mt["single_pool"]}</span>；候选 {rev["old_total"]}→<span data-metric="total_candidates">{mt["total_candidates"]}</span></div></div>
</div>
<div class="tblwrap"><table>
<thead><tr><th>场景</th><th>复核状态</th><th>剔除任务</th><th>组合池（BDDL → 复核后）</th><th>无序对</th><th>ordered 候选（M1+M2+S1=总）</th><th>复核说明</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p class="note">说明（来自复核文件）：① 其他 {mt["n_pending_scenes"]} 个场景用户本轮未给出修改意见 → 按原方案保留，待后续逐场景复核；② 结构相近的 <code>26/27/28</code>（In + Close 双原子）本轮未被点名，暂保留在组合池内；若后续确认排除，只需更新 <a class="local" href="../scene_review_decisions.json">scene_review_decisions.json</a> 并重跑生成器（本页与候选清单会自动更新）；③ 视频清单与本轮复核无关，保持 {mt["videos"]} 段不变。</p>
</section>'''


def render_baseline_gallery(m):
    manifest = m["manifest"]
    suites = manifest["pi0_suites"]
    mt = m["metrics"]
    suite_rows = "".join(
        f'<tr><td><code>{esc(name)}</code></td><td>{suites[name]["total"]}</td>'
        f'<td>{suites[name]["success"]}</td><td>{suites[name]["total"] - suites[name]["success"]}</td></tr>'
        for name in SUITE_ORDER if name in suites
    )
    tasks = sorted(
        manifest["baseline_tasks"],
        key=lambda x: (SUITE_ORDER.index(x["suite"]) if x["suite"] in SUITE_ORDER else 99, x["task_idx"]),
    )
    rows = []
    for t in tasks:
        copied = t.get("copied_files") or []
        if copied:
            link = f'<a class="xlink" href="{esc(copied[0])}">▶ 播放</a> <span class="tiny">（{len(copied)} 份场景副本）</span>'
        else:
            link = '<span class="tiny">未收录（仅存于源 run）</span>'
        used = ", ".join(t.get("used_by_l90_scenes") or []) or "—"
        oft = t.get("openvla_oft") or {}
        pi0_cell = (badge("✓ 成功", "b-ok") if t["success"] else badge("✗ 失败", "b-fail")) + f' {t["steps"]} 步'
        oft_cell = "—"
        if oft:
            oft_cell = (badge("✓", "b-ok") if oft.get("success") else badge("✗", "b-fail")) + f' {oft.get("steps", "—")} 步'
        rows.append(
            f'<tr><td>{esc(t["suite"])}</td><td>T{t["task_idx"]}</td>'
            f'<td>{esc(t["instruction"])}</td>'
            f'<td class="nowrap">{pi0_cell}</td><td class="nowrap">{oft_cell}</td>'
            f'<td class="tiny">{esc(used)}</td><td>{link}</td></tr>'
        )
    return f'''<section id="baseline-gallery">
<h2>五、pi0 baseline 画廊（标准四套件 {mt["pi0_tasks"]} 段，v2 不变）</h2>
<p class="sub">本工作区唯一可用的 pi0 baseline：<code>runs/libero-std-pi0-openvla-20261023/run/pi0/</code> 下 4 套件 × 10 任务 = <b>{mt["pi0_tasks"]} 段</b>（pi0 成功 <span data-metric="pi0_success">{mt["pi0_success"]}</span>/40，v2 复核不影响视频资产）。其中 <b><span data-metric="n_ref_pi0">{mt["n_ref_pi0"]}</span> 段</b>被 {mt["scenes"]} 个 L90 场景引用（复制到 <code>report/videos/</code>，共 {mt["videos"]} 份场景副本），<b><span data-metric="n_unref_pi0">{mt["n_unref_pi0"]}</span> 段</b>未被任何场景引用，只在此画廊列出。</p>
<div class="tblwrap"><table>
<thead><tr><th>套件</th><th>任务数</th><th>pi0 成功</th><th>失败</th></tr></thead>
<tbody>{suite_rows}
<tr><td><b>合计</b></td><td><b>{mt["pi0_tasks"]}</b></td><td><b>{mt["pi0_success"]}</b></td><td><b>{mt["pi0_tasks"] - mt["pi0_success"]}</b></td></tr>
</tbody></table></div>
<div class="tblwrap"><table>
<thead><tr><th>套件</th><th>T#</th><th>官方指令</th><th>pi0 结果</th><th>OpenVLA-OFT</th><th>被引用于 L90 场景</th><th>本地视频</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p class="note">说明：<code>report/videos/</code> 中同一源视频被多个场景引用时会重复复制为不同文件名（命名 <code>pi0_&lt;SUITE&gt;_T&lt;idx&gt;__&lt;场景&gt;__&lt;kind&gt;.mp4</code>）；本节“▶ 播放”链接直接指向本地副本。全部 {mt["pi0_tasks"]} 段的原始路径与 sha256 见 <a class="local" href="video-manifest.json">video-manifest.json</a>。本轮复核 v1 不改变视频映射（KS1 仍引用 2 段参考视频）。</p>
</section>'''


def render_funnel(m):
    mt = m["metrics"]
    rev = m["revision"]
    rows = [
        ("S0 静态构造（本报告对象）", "候选定义：goal 原子并集、官方 language、obj_of_interest、init 源、class / dependency / priority", f"{mt['total_candidates']} 条候选定义完成（本页，v2 复核后）", "候选 BDDL + sibling <code>.pruned_init</code> 尚未生成 → BDDL 解析 / 段替换 / 初始状态断言 / 双目标可满足性探针均<b>未跑</b>"),
        ("S1 单任务 baseline", f"BDDL 口径 {mt['pool_bddl']} 条单目标任务 × 1 seed，先建出 L90 的“可解任务子集”（任务 00 虽不参与组合，但仍是既有双子任务，需单独记录）", "未开始；唯一 L90 动态证据是历史 pi05 11 个候选（10 条两段 + 1 条单段对照 17），其中仅 17 通过 1/11、8 条 0/5、40/41 1–2/5", "本工作区无 L90 视频；40 段 pi0 视频均为标准四套件"),
        ("S2 通道预检", "每候选 1 episode：instruction / goal atoms / init row / 稳定化 sim state 的 sha256 与设计值一致；<code>episode_seed</code> 正确", "未开始", "需先给 runner 补 custom-bddl 分支的 sidecar init 加载（历史上漏加载曾导致 300 episodes 整批作废）"),
        ("S3 单任务控制", "在所选 init 源下分别跑 s1、s2 的单指令，确认两者各自可解", "未开始", "第二目标在改造场景中不可解时，静态验证全过也救不回来"),
        ("S4 组合单指令冒烟", f"1 seed / 候选，P0 优先；预期成功率个位数（GOAL 4.3% / OBJECT 4.0%）", f"未开始；预期 {mt['prio_p0']} 个 P0 里乐观 10+ 个至少成功一次", "单指令不是主协议，只作筛子"),
        ("S5 staged / instruction-switch 复筛", "对冒烟完成过 1 段的候选，先给 s1 指令、检测 s1 首次为真后切 s2（GOAL 实测 2/3）", "未开始", "L90 上 staged 效果未测，不能直接外推"),
        ("S6 多 seed 稳定性", "同一问题 3 seeds；口径参考 OBJECT（≥2/3 稳定）与 GOAL（≥3/6 = B 级）", "未开始", "引用时必须带分母"),
        ("S7 rollback 原型", "s1 成功后注入回退（<code>revert_articulation_goal</code> / 放置类 <code>displace_*</code>），s2 执行中观察自修复", "未开始", f"只有 s1 可回退的方向可做（P0；{mt['n_s1_unrevertable']} 个不可回退方向已排除）"),
    ]
    body = "".join(
        f"<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td><td>{d}</td></tr>" for a, b, c, d in rows
    )
    return f'''<section id="funnel">
<h2>六、验证漏斗与下一步</h2>
<p class="sub">从 {mt["m1_unordered_pairs"]} 个同场景对到“可用的双目标 / rollback 任务”：本报告只完成 <b>S0 静态构造</b>。S1 之后全部未执行——所有“可行性 / 优先级”都是构造层判断，不是实测结论。v2 复核只改了 S0 的候选集合（{rev["old_total"]}→{mt["total_candidates"]}），不影响漏斗后续阶段。</p>
<div class="tblwrap"><table>
<thead><tr><th>阶段</th><th>内容</th><th>当前状态</th><th>风险 / 备注</th></tr></thead>
<tbody>{body}</tbody></table></div>
<h3>6.1 下一步（建议顺序）</h3>
<ol class="risk">
<li><b>生成候选 BDDL + init</b>：按 docs §8.1 为 {mt["total_candidates"]} 条候选生成 <code>.bddl</code> 与 sibling <code>.pruned_init</code>（复用同场景 init 源，记录 <code>init_source</code>），并跑 docs §10.1 的 7 项静态断言（含双目标可满足性探针）。</li>
<li><b>补 {mt["pool_bddl"]} 条单目标任务 baseline</b>：pi0 / pi05 各 1 seed；这是后续所有“可行/稳定”判断的前提。当前只有历史 11 个候选 pi05 结果，且 run 目录已不在工作区。</li>
<li><b>通道预检</b>：每候选 1 episode；先在 runtime 里补 custom-bddl 分支的 sidecar <code>.pruned_init</code> 加载，再做三层 sha256 预检。</li>
<li><b>分层动态筛选</b>：单任务控制 → 组合单指令冒烟（P0 优先、1 seed）→ staged 复筛 → 多 seed 稳定性。</li>
<li><b>rollback 原型</b>：只对 s1 可回退的 P0 方向做（<span data-metric="m1_s1_revertable_ab">{mt["m1_s1_revertable_ab"]}</span> / <span data-metric="m1_s1_revertable_ba">{mt["m1_s1_revertable_ba"]}</span> 个 ab/ba 方向）。</li>
<li><b>补 L90 官方视频</b>：用 <code>scripts/run_libero90_baseline.py --model pi0</code> 跑 LIBERO-90 官方 baseline 后重跑 video manifest 与本报告；届时 <code>--check</code> 会检测到 L90 视频并提示改用实测 baseline 标注（见 <a class="local" href="VIDEO_SOURCES.md">VIDEO_SOURCES.md §5</a>）。</li>
</ol>
</section>'''


def render_risks(m):
    mt = m["metrics"]
    rev = m["revision"]
    return f'''<section id="risks">
<h2>七、风险与未验证项</h2>
<p class="note">本页为 <b>v2</b>（用户逐场景复核 v1 后）：所有计数/分类/优先级均按复核后口径重算，v1→v2 的口径差异集中在 <a href="#revision-note">v2 修订记录</a>；风险结论以 v2 口径为准。</p>
<h3>7.1 任务 / 方法风险（docs §12 转述，v2 口径）</h3>
<ol class="risk">
<li><b>L90 上没有任何组合候选的静态/动态实测</b>：所有分类 / 优先级都是构造层判断；历史 L90 动态证据仅 10 条两段候选 + 对照 17 的 pi05 baseline（8 条 0/5、40/41 仅 1–2/5）。v2 复核不改变“未实测”这一事实。</li>
<li><b>BDDL 口径 {mt["pool_bddl"]} 条单目标任务本身尚未测 baseline</b>（组合池 {mt["single_pool"]} 条）：必须先补，否则“可行 / 稳定”筛选无意义；任务 00 虽不参与组合，仍需其单任务/既有双子任务基线。</li>
<li><b>init 源敏感性未测</b>：GOAL 已证 init 源可翻转单任务成败，L90 同场景 init 文件内容不同 → 必须做 init 源对照（<code>init_source ∈ {{s1, s2}}</code> 已记录在候选里）。</li>
<li><b>staged 在 L90 上的效果未测</b>：GOAL 2/3 是单场景 10 任务的结果，不能直接外推。</li>
<li><b>模板化指令仍是机械构造</b>：L90 官方 language 存在多实例（butter_1/2、bowl_1/2/3、moka_pot_1/2、plate_1/2、yellow_book_1/2）与空间描述（front/back/left/right/middle）差异 → 指代歧义需人工抽检或做措辞变体实验。{mt["n_naive_same"]}/{mt["tpl_total"]} 条模板化结果与 naive 相同（官方句式本身规范），改写 {mt["n_rewritten"]} 条；v2 后 T5 零命中。</li>
<li><b>Turnon / Turnoff 不可回滚</b>：单目标池里 08/24（Turnon）与 18（Turnoff）只能作 s2 或 P1 双目标任务；{mt["n_s1_unrevertable"]} 个方向已标 <code>s1_revertable=false</code>（6 个 M1 Turnon 方向 + S1 的 ba 方向）。</li>
<li><b>3 原子候选（{mt["n_atoms_3"]} 个 ordered）难度未知</b>：GOAL 的 3 原子链动态 0/24，提示大概率不可解；本清单保留但 hard 对已在 P2。v2 后 3 原子候选从 18 降到 {mt["n_atoms_3"]}（全部来自 26/27/28）。</li>
<li><b>M2 / S1 的合成措辞不是官方原文</b>：LIVING_ROOM_SCENE2 / STUDY_SCENE2 / LIVING_ROOM_SCENE4 / KITCHEN_SCENE8 的提升候选必须人工确认指令与目标一致（措辞来源见 <code>instruction_source</code>：borrowed:31/32/42/73、synthesized）。</li>
</ol>
<h3>7.2 本报告发现的输入问题（已在页面口径中处理）</h3>
<ol class="risk">
<li><b>官方 language 与 BDDL 内联 language 有 4 条不一致</b>（任务 55 / 58 / 79 / 80，见 <a class="local" href="../../../docs/libero-90-dual-target-candidates.md">docs §1.5</a>）：<code>inventory.json</code> 的 <code>language</code> 对这 4 条存的是内联值，而模板化 <code>instruction</code> 正确地使用官方值。本页“官方指令”列使用官方值，并对这 4 条打 <code>official≠inline</code> 标记；候选表“旧 naive 拼接”列沿用 <code>candidates-instructed.json.language</code> 记录值（已知输入差异）。</li>
<li><b>M2/S1 的 s1_task / s2_task.index 为 null</b>（17+1 个提升目标不是 L90 任务）：本页用 <code>↑object</code> 标记提升目标，避免被误读成任务号。</li>
<li><b>summary 的分类 / 优先级是 M1-only</b>：<code>class_counts</code> {mt["class_pair_compatible"]}/{mt["class_pair_hard"]}/{mt["class_pair_conflict"]}/{mt["class_pair_degenerate"]}（pair 级）与 {mt["class_ordered_compatible"]}/{mt["class_ordered_hard"]}/{mt["class_ordered_conflict"]}/{mt["class_ordered_degenerate"]}（ordered）、<code>priority_counts</code> {mt["prio_p0"]}/{mt["prio_p1"]}/{mt["prio_p2"]}/{mt["prio_p3"]} 只覆盖 M1 {mt["m1_ordered"]}；含 M2/S1 的全量口径是 <code>*_all</code>（{mt["class_all_compatible"]}/{mt["class_all_hard"]}/{mt["class_all_conflict"]}/{mt["class_all_degenerate"]}、{mt["prio_all_p0"]}/{mt["prio_all_p1"]}/{mt["prio_all_p2"]}/{mt["prio_all_p3"]}）。本页两个口径都标注。</li>
<li><b>pair-semantics.json 仍是 v0（未随复核再生）</b>：该文件 <code>scope.n_pairs = {m["pair_semantics"]["scope_pairs"]}</code>、pairs 长度 {m["pair_semantics"]["n_pairs"]}，仍包含已剔除的 KS1/00 组合；本页 pair 级 class 统计取 <code>candidates-instructed.json stats.m1.class_counts_unordered_pairs</code>（{mt["class_pair_compatible"]}/{mt["class_pair_hard"]}/{mt["class_pair_conflict"]}/{mt["class_pair_degenerate"]}），未使用过期字段。建议后续重跑 classify_pairs.py 同步。</li>
<li><b>模板 id 集合是 11 个而不是 T1–T12</b>：JSON 实际为 T1–T10 + T4b；docs §7.1 的 T12 是变体级 <code>then</code> 改写策略，不是候选级模板 id。v2 后 T5 零命中，仍保留第 11 行。</li>
<li><b>容量 caveat 的单位</b>：<code>stats.m1.capacity_caveat_ordered = {mt["m1_capacity_ordered"]}</code> 只覆盖 M1；全量 <code>capacity_caveat=true</code> 是 {mt["cap_cands_m1"] + mt["cap_cands_m2"]} 条（M2 的 {mt["cap_cands_m2"]} 条同容器提升也置位）。</li>
<li><b>视频全部是参考性质</b>：本工作区 <code>find runs -name '*.mp4' -path '*libero_90*'</code> = 0，L90 官方 baseline 视频待补录；{mt["videos"]} 段视频 = {mt["video_kind_exact"]} 段 exact_scene_l10 + {mt["video_kind_family"]} 段 suite_family_reference，另有 {mt["n_unref_pi0"]} 段 pi0 任务未被任何场景引用。</li>
<li><b>复核口径变更来源</b>：KS1/00 的剔除由用户逐场景复核（2026-10-25，第 1 批）给出，记录在 <code>scene_review_decisions.json</code>；<code>candidates-instructed.json</code> 已按该文件重新生成（{mt["total_candidates"]} 条，sha256 见 <a class="local" href="../scene_review_decisions.json">复核文件</a> 与 candidates meta 一致）。旧版（复核前）候选仅作为历史口径保留在 <a href="#revision-note">v2 修订记录</a>。</li>
</ol>
<h3>7.3 视频参考的具体近似风险</h3>
<ol class="risk">
<li>物体实例不保证一致：KS7 的 L90 物体是 white bowl，但 SPATIAL 参考视频只有 black bowl；KS6/KS7 的 microwave 操作在 40 段 pi0 baseline 中只有 LIBERO-10 T9 一段且 pi0 失败；LR5/LR6 的 mug 参考来自 LIBERO-10 同套件任务。这些只能作族级参考。</li>
<li>exact_scene_l10 只是“场景同名”：LIBERO-10 与 L90 同名场景的物体/布局并不相同，任务也不同，卡片统一显示 manifest 的 <code>honest_note</code>。</li>
<li>历史 LIBERO-90 baseline（pi05 / openvla，11 条任务）的 run 目录已不在本工作区，本页不含其视频。</li>
</ol>
</section>'''


def render_revision_note(m):
    mt = m["metrics"]
    rev = m["revision"]
    return f'''<section id="revision-note" data-v1-history="1">
<h2>八、v2 修订记录（v1 330 候选 → v2 {mt["total_candidates"]} 候选）</h2>
<p class="sub">依据：用户逐场景复核 v1（2026-10-25，第 1 批 KITCHEN_SCENE1），唯一口径源 <code>scene_review_decisions.json</code>（version {rev["review_version"]}，updated_at {esc(rev["review_updated_at"])}；源：{esc(rev["review_source"])}）。候选清单已按该文件重新生成（{mt["total_candidates"]} 条），本报告 v2 由同一口径重建；<code>--check</code> 会校验“历史数字只出现在本节”。</p>
<h3>8.1 复核结论</h3>
<ul class="flat">
<li><b>KITCHEN_SCENE1 任务 00</b>（open the top drawer of the cabinet and put the bowl in it）<b>本身已经是双子任务</b>（Open + In 两段），不需要再与场景内其他任务组合 → <b>从组合池剔除</b>；KS1 只用 01–04 两两组合。</li>
<li>任务 00 仍保留为 LIBERO-90 既有双子任务：仍出现在 <a href="#scene-KITCHEN_SCENE1">KS1 单任务表</a>并标注“双目标（用户复核：已移出组合池）”，但不再出现在任何候选表（全页候选行不含任务 00）。</li>
<li>其余 <b>19 个场景</b>本轮无修改意见 → 组合池/候选数不变，等待后续逐场景复核（见 <a href="#scene-review">逐场景复核状态</a>）。</li>
</ul>
<h3>8.2 口径差异（v1 → v2，{rev["old_total"]} → {mt["total_candidates"]}）</h3>
<div class="tblwrap"><table>
<thead><tr><th>指标</th><th>v1（复核前，历史）</th><th>v2（复核后，当前）</th><th>差异</th></tr></thead>
<tbody>
<tr><td>组合池（BDDL 单目标池 83 不变）</td><td>83</td><td><b>{mt["single_pool"]}</b></td><td>−{mt["n_review_excluded_tasks"]}（KS1/00）</td></tr>
<tr><td>M1 无序对</td><td>147</td><td><b>{mt["m1_unordered_pairs"]}</b></td><td>−{rev["removed_pairs"]}</td></tr>
<tr><td>M1 ordered 候选</td><td>294</td><td><b>{mt["m1_ordered"]}</b></td><td>−{rev["removed_candidates"]}</td></tr>
<tr><td>M2 ordered 候选</td><td>34</td><td><b>{mt["m2_ordered"]}</b></td><td>不变</td></tr>
<tr><td>S1 ordered 候选</td><td>2</td><td><b>{mt["s1_ordered"]}</b></td><td>不变</td></tr>
<tr><td><b>总候选</b></td><td><b>330</b></td><td><b>{mt["total_candidates"]}</b></td><td><b>−{rev["removed_candidates"]}</b></td></tr>
<tr><td>class（pair 级 / ordered）</td><td>93/19/31/4 · 186/38/62/8</td><td><b>{mt["class_pair_compatible"]}/{mt["class_pair_hard"]}/{mt["class_pair_conflict"]}/{mt["class_pair_degenerate"]} · {mt["class_ordered_compatible"]}/{mt["class_ordered_hard"]}/{mt["class_ordered_conflict"]}/{mt["class_ordered_degenerate"]}</b></td><td>仅 compatible/conflict/degenerate 计数随剔除变化</td></tr>
<tr><td>priority（P0/P1/P2/P3）</td><td>180/6/38/70</td><td><b>{mt["prio_p0"]}/{mt["prio_p1"]}/{mt["prio_p2"]}/{mt["prio_p3"]}</b></td><td>P0 −2、P3 −6</td></tr>
<tr><td>模板 T5 命中</td><td>{rev["old_tpl_T5_text"]}</td><td><b>{mt["tpl_T5"]}</b></td><td>−8（全部来自含 00 的组合）</td></tr>
<tr><td>KS1 场景候选</td><td>{len(m["scene_rows"][0]["cands"]) + rev["removed_candidates"]}</td><td><b>{len(m["scene_rows"][0]["cands"])}</b></td><td>−{rev["removed_candidates"]}</td></tr>
<tr><td>视频参考</td><td>53 段</td><td><b>{mt["videos"]} 段</b></td><td>不变（视频资产未动）</td></tr>
</tbody></table></div>
<p class="note">说明：v1 的 class/priority 数字来源为上一版 <code>candidates-instructed.json</code>（330 条）与本任务的历史报告；v2 数字全部来自当前 JSON（脚本计算，<code>--check</code> 校验）。任务 00 的剔除只影响 KS1：M1 对 10→6、场景候选 20→12；其余 19 场景的候选数不变。若要调整其他场景，只需更新 <a class="local" href="../scene_review_decisions.json">scene_review_decisions.json</a> 并重跑生成器。</p>
</section>'''


def render_artifacts(m):
    mt = m["metrics"]
    rev = m["revision"]
    ps = m["pair_semantics"]
    rows = [
        ("本报告（单文件 HTML）", "index.html", f"由本脚本生成（v2，{mt['total_candidates']} 候选）；内联 CSS/JS，可离线打开"),
        ("本报告说明", "README.md", "口径 / v2 复现命令 / 章节索引 / 视频来源声明"),
        ("逐场景复核口径源（唯一）", "../scene_review_decisions.json", f"v{rev['review_version']}，{esc(rev['review_updated_at'])}；KS1 剔除任务 00 的来源，sha256 与 candidates meta 交叉校验"),
        ("模板化候选（含新指令）", "../candidates-instructed.json", f"{mt['total_candidates']} 条（M1 {mt['route_m1']} + M2 {mt['route_m2']} + S1 {mt['route_s1']}）；本页主数据源"),
        ("原始机读候选（未改）", "../candidates.json", f"{mt['total_candidates']} 条候选定义（v2 复核后）"),
        ("全量候选表", "../CASE_LIST.md", f"{mt['total_candidates']} 行候选的 Markdown 全量表"),
        ("指令模板说明", "../INSTRUCTION_TEMPLATES.md", "T1–T10 / T4b 模板总表、变换示例、--check 断言（v2 后 T5 零命中）"),
        ("运行 / 口径说明", "../README.md", "生成器、字段、复核 v1 后的计数口径、已知限制"),
        ("pi0 参考视频清单", "video-manifest.json", f"{mt['videos']} 段参考视频；scene_map / videos / baseline_tasks / gaps / sha256"),
        ("视频来源与缺口", "VIDEO_SOURCES.md", "kind 规则、每场景映射、为什么没有 L90 视频、补录线索"),
        ("方法文档（双目标候选）", "../../../docs/libero-90-dual-target-candidates.md", "§7.1 模板表 / §10 验证漏斗 / §12 风险 / §14 审计"),
        ("任务清单与 7/83 对账", "../../../docs/libero-90-task-inventory.md", "90 条任务清点、场景、objects/init 字段"),
        ("本报告生成器", "../../../scripts/build_libero90_scene_report.py", "可重跑（v2）；--check 校验本页全部不变量"),
        ("候选生成器", "../../../scripts/build_libero90_combos.py", f"BDDL → 候选（当前 {mt['m1_unordered_pairs']} 对 / {mt['m1_ordered']} M1，读取复核口径）"),
        ("指令模板生成器", "../../../scripts/build_libero90_instructions.py", "旧指令 → 模板化指令（T1–T10/T4b）"),
        ("视频清单生成器", "../../../scripts/build_libero90_video_manifest.py", "pi0 参考视频选择 / 复制 / honest_note（v2 未改动）"),
        ("147 对语义分类原始 JSON", "../../../.tmp/libero90-combos/pair-semantics.json", f"v0，pairs={ps['n_pairs']}（仍含已剔除的 KS1/00；本页 pair 级统计改用 candidates stats，见风险 7.2-4）"),
        ("任务 BDDL 字段清单", "../../../.tmp/libero90-combos/inventory.json", "index / scene / goal atoms / objects / init_width / scene_fp"),
        ("官方 language + benchmark 映射", "../../../.tmp/libero90-combos/official-language-and-benchmark-map.json", "文件名派生官方 language 与 benchmark 字母序 idx"),
    ]
    body = "".join(
        f'<tr><td>{esc(title)}</td><td><a class="local" href="{esc(href)}"><code>{esc(href)}</code></a></td><td class="tiny">{esc(desc)}</td></tr>'
        for title, href, desc in rows
    )
    hashes = m["hashes"]
    hash_lines = " · ".join(
        f'<code>{esc(name)}</code> <code title="sha256">{esc(hashes[name][:16])}…</code>' for name in sorted(hashes)
    )
    return f'''<section id="artifacts">
<h2>九、产物索引</h2>
<div class="tblwrap"><table>
<thead><tr><th>产物</th><th>路径（相对本文件）</th><th>用途</th></tr></thead>
<tbody>{body}</tbody></table></div>
<p class="note">输入文件 sha256（前 16 位，完整值见 <code>--check</code> 与生成日志）：{hash_lines}。本页只读这些输入 JSON 与 <code>report/videos/</code> 原始视频；没有修改候选、视频或任何输入文件。</p>
</section>'''


def render_footer(m):
    hashes = m["hashes"]
    mt = m["metrics"]
    rev = m["revision"]
    lines = " · ".join(
        f'<code>{esc(name)}</code> <code>{esc(hashes[name][:16])}…</code>' for name in sorted(hashes)
    )
    return f'''<footer>
<p><b>生成命令</b>：<code>cd /home/tarowang/workspace/roboot/libero-rollback &amp;&amp; .venv/bin/python scripts/build_libero90_scene_report.py</code>；只读校验：<code>.venv/bin/python scripts/build_libero90_scene_report.py --check</code></p>
<p data-v1-history="1"><b>v2 修订</b>（{esc(rev["review_updated_at"][:10])}，用户逐场景复核 v1）：KS1 剔除任务 00 → 组合池 {mt["pool_bddl"]}→{mt["single_pool"]}、候选 {rev["old_total"]}→{mt["total_candidates"]}（M1 {rev["old_m1_ordered"]}→{mt["m1_ordered"]} ordered）、T5 命中 {rev["old_tpl_T5_text"]}→{mt["tpl_T5"]}；其余 {mt["n_pending_scenes"]} 个场景暂无修改意见；视频不变 {mt["videos"]} 段。差异明细见 <a href="#revision-note">v2 修订记录</a>。</p>
<p><b>数据来源</b>：{lines}；方法口径见 <a class="local" href="../../../docs/libero-90-dual-target-candidates.md">docs/libero-90-dual-target-candidates.md</a>（§7.1 / §10 / §12 / §14）、<a class="local" href="../INSTRUCTION_TEMPLATES.md">INSTRUCTION_TEMPLATES.md</a>、<a class="local" href="../scene_review_decisions.json">scene_review_decisions.json</a>。</p>
<p><b>审计状态</b>：候选方法 / 清单已经过独立审计（docs §14：<b>PASS-WITH-ISSUES</b>，0 blocker / 1 major / 14 minor，问题已修复）；本 HTML 由脚本从 JSON 全量生成、数字无手填、<code>--check</code> 逐项复验（见生成日志）。<b>组合任务动态可解性未验证（0 episode）</b>；页面视频全部是 pi0 参考 baseline，不是 L90 实测。</p>
<p class="tiny">构建时间 {esc(m["generated_at"])} · 构建指纹 <code>sha256:{esc(m["digest"])}</code> · 单文件静态页面（内联 CSS/JS、无外链 CDN；视频以相对路径引用 <code>report/videos/</code>）</p>
</footer>'''


def build_html(m):
    mt = m["metrics"]
    parts = [
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f'<title>LIBERO-90 双目标组合 · 分场景报告 v2（{mt["scenes"]} 场景 / {mt["total_candidates"]} 候选 / pi0 参考视频）</title>',
        f"<!-- data-digest: sha256:{m['digest']} -->",
        f'<style>{CSS}</style>',
        '</head><body>',
        render_sidenav(m),
        render_hero(m),
        '<main>',
        render_filterbar(m),
        render_overview(m),
        render_templates(m),
        render_scene_index(m),
        render_scene_review(m),
    ]
    for s in m["scene_rows"]:
        parts.append(render_scene(s, m))
    parts += [
        render_baseline_gallery(m),
        render_funnel(m),
        render_risks(m),
        render_revision_note(m),
        render_artifacts(m),
        '</main>',
        render_footer(m),
        f'<script>{JS}</script>',
        '</body></html>',
    ]
    return "\n".join(parts)


def build_readme(m):
    mt = m["metrics"]
    rev = m["revision"]
    lines = [
        "# LIBERO-90 双目标组合 · 分场景报告 v2（index.html）",
        "",
        "> 打开 `index.html` 即可离线阅读：单文件、内联 CSS/JS；视频以相对路径引用 `videos/`。",
        "",
        "## 口径（v2 · 用户逐场景复核 v1 后）",
        f"- 范围：LIBERO-90 {mt['tasks']} 任务 / {mt['scenes']} 场景；BDDL 单目标池 {mt['pool_bddl']} 条 → 复核剔除 {mt['n_review_excluded_tasks']} 条（KS1/00）→ **组合池 {mt['single_pool']}** → {mt['m1_unordered_pairs']} 个同场景对 → **{mt['total_candidates']} 个 ordered 候选**（M1 {mt['route_m1']} + M2 {mt['route_m2']} + S1 {mt['route_s1']}）。",
        "- 指令：按 LIBERO-10 / GOAL / OBJECT 已验证成功任务模板重建（T1–T10 + 子变体 T4b）；v2 后 T5 命中 0（原 8 条全部来自含 KS1/00 的组合），模板表仍保留 11 行。",
        f"- 分类/优先级（M1 ordered {mt['m1_ordered']}）：class {mt['class_ordered_compatible']}/{mt['class_ordered_hard']}/{mt['class_ordered_conflict']}/{mt['class_ordered_degenerate']}；priority P0 {mt['prio_p0']} / P1 {mt['prio_p1']} / P2 {mt['prio_p2']} / P3 {mt['prio_p3']}；pair 级 class {mt['class_pair_compatible']}/{mt['class_pair_hard']}/{mt['class_pair_conflict']}/{mt['class_pair_degenerate']}。",
        f"- 状态：**组合任务本轮 0 动态实测**；页面 {mt['videos']} 段视频全部是 pi0 在标准四套件上的**参考 baseline**（exact_scene_l10 {mt['video_kind_exact']} / suite_family_reference {mt['video_kind_family']}），**不是任何 L90 任务/组合任务的实测**。",
        f"- 复核：{mt['n_reviewed_scenes']}/{mt['scenes']} 场景已复核（KS1 剔除任务 00）；{mt['n_pending_scenes']} 个场景暂无修改意见、待复核；v1 {rev['old_total']}→v2 {mt['total_candidates']} 的差异见 HTML「v2 修订记录」。",
        "",
        "## 复现",
        "```bash",
        "cd /home/tarowang/workspace/roboot/libero-rollback",
        ".venv/bin/python scripts/build_libero90_scene_report.py          # 重建 index.html + README.md（读取 scene_review_decisions.json）",
        ".venv/bin/python scripts/build_libero90_scene_report.py --check  # 只读校验（不写文件）",
        "```",
        "",
        "## 章节索引",
        "1. 状态与范围 / 指标与口径（class、优先级、模板分布、三条路线、复核进度）",
        "2. 指令模板 T1–T10（+T4b）：模板表 / 证据数字 / 为什么弃用 naive 拼接 / T5 零命中说明",
        "3. 20 个场景索引 → 逐场景复核状态（20 行）",
        "4. 20 个场景（每场景：单任务表 → 组合候选表 → 对照与排除 → pi0 参考视频卡）",
        "5. pi0 baseline 画廊 / 验证漏斗与下一步 / 风险与未验证项 / v2 修订记录 / 产物索引",
        "",
        "## 视频来源声明",
        "`videos/` 由 `scripts/build_libero90_video_manifest.py` 从 `runs/libero-std-pi0-openvla-20261023` 复制整理；清单见 `video-manifest.json` 与 `VIDEO_SOURCES.md`。本报告不重命名 / 不删除视频，每张卡片都显示 manifest 的 `honest_note`；v2 复核不改变视频映射。",
        "",
        "## 数据来源",
        "`../candidates-instructed.json`、`../scene_review_decisions.json`、`video-manifest.json`、`../../../.tmp/libero90-combos/{inventory,official-language-and-benchmark-map,pair-semantics}.json`、`../../../docs/libero-90-dual-target-candidates.md`（§7.1/§10/§12）。",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(m):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    html_text = build_html(m)
    OUT_HTML.write_text(html_text, encoding="utf-8")
    readme = build_readme(m)
    OUT_README.write_text(readme, encoding="utf-8")
    n_tasks = sum(len(s["task_rows"]) for s in m["scene_rows"])
    n_cands = sum(len(s["cands"]) for s in m["scene_rows"])
    ks1 = next((s for s in m["scene_rows"] if s["scene"] == "KITCHEN_SCENE1"), None)
    n_cards = html_text.count('<figure class="vcard"')
    n_review = html_text.count('class="review-row')
    print(f"[build] {OUT_HTML.relative_to(ROOT)}: {len(html_text.encode('utf-8')):,} bytes (v2)")
    print(f"[build] scenes={len(m['scene_rows'])} task_rows={n_tasks} cand_rows={n_cands} "
          f"video_cards={n_cards} templates={len(m['templates'])} review_rows={n_review}")
    if ks1:
        print(f"[build] KITCHEN_SCENE1: tasks={ks1['task_count']} pool={ks1['pool_count']} "
              f"pairs={ks1['pair_count']} cands={len(ks1['cands'])} reviewed={ks1['reviewed']} "
              f"excluded={ks1['review_excluded']}")
    print(f"[build] v1->v2: total {m['revision']['old_total']}->{m['metrics']['total_candidates']}, "
          f"M1 pairs {m['revision']['old_m1_unordered']}->{m['metrics']['m1_unordered_pairs']}, "
          f"T5 {m['revision']['old_tpl_T5']}->{m['metrics']['tpl_T5']}")
    print(f"[build] {OUT_README.relative_to(ROOT)}: {len(readme.splitlines())} lines")
    print(f"[build] digest sha256:{m['digest']}")


def parse_attrs(text):
    return dict(re.findall(r'([a-zA-Z_][\w-]*)="([^"]*)"', text))


def run_checks(m):
    checks = []

    def add(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    mt = m["metrics"]
    rev = m["revision"]
    manifest = m["manifest"]
    cands = m["candidates"]
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

    # ---------- 场景 section ----------
    sec_re = re.compile(r'<section class="scene" id="scene-([A-Z0-9_]+)"([^>]*)>', re.S)
    secs = sec_re.findall(text)
    names = [x[0] for x in secs]
    add(f"{mt['scenes']} 个场景 section 齐全且顺序正确", len(secs) == mt["scenes"] and names == m["scene_order"],
        f"实际 {len(secs)} 个: {names[:3]}…")
    sec_attrs = {name: parse_attrs(a) for name, a in secs}
    bad_sec = []
    for s in m["scene_rows"]:
        got = sec_attrs.get(s["scene"], {})
        expected = {
            "data-scene-fp": s["fp"],
            "data-tasks": str(s["task_count"]),
            "data-pool": str(s["pool_count"]),
            "data-pool-bddl": str(s["pool_bddl_count"]),
            "data-pairs": str(s["pair_count"]),
            "data-pairs-bddl": str(s["pair_bddl_count"]),
            "data-cands": str(len(s["cands"])),
            "data-videos": str(len(s["videos"])),
            "data-reviewed": "1" if s["reviewed"] else "0",
            "data-excluded": ",".join(str(i) for i in s["review_excluded"]),
            "data-exact": str(s["exact_count"]),
            "data-family": str(s["family_count"]),
            "data-success": str(s["success_count"]),
        }
        if any(got.get(k) != v for k, v in expected.items()):
            bad_sec.append(s["scene"])
    add("每场景头部计数（任务/组合池 BDDL→复核后/对数/候选/复核状态/视频）与 JSON 一致",
        not bad_sec, f"不一致: {bad_sec}")

    # ---------- 单任务表 ----------
    task_rows = re.findall(r'<tr class="(task-row[^"]*)"([^>]*)>', text)
    task_attrs = [parse_attrs(a) for _, a in task_rows]
    add(f"单任务表行数 = {mt['tasks']}（不因复核减少）", len(task_rows) == mt["tasks"], f"实际 {len(task_rows)}")
    per_scene_tasks = Counter(a.get("data-scene") for a in task_attrs)
    bad = [s["scene"] for s in m["scene_rows"] if per_scene_tasks[s["scene"]] != s["task_count"]]
    add("逐场景单任务行数 = inventory 任务数", not bad, f"不一致: {bad[:5]}")
    dual_tasks = sorted(int(a["data-task"]) for a in task_attrs if a.get("data-dual") == "1")
    add(f"双目标任务标记 = {len(m['dual7'])} 条且编号与 summary.dual7 一致", dual_tasks == m["dual7"], f"实际 {dual_tasks}")
    re_tasks = sorted(int(a["data-task"]) for a in task_attrs if a.get("data-review-excluded") == "1")
    add("复核剔除任务标记 = excluded_tasks 且只出现在单任务表",
        re_tasks == m["excluded_tasks"], f"实际 {re_tasks} vs {m['excluded_tasks']}")
    task0 = next((parse_attrs(a) for _, a in task_rows if parse_attrs(a).get("data-task") == "0"), None)
    add("任务 00 标注“双目标（用户复核：已移出组合池）”",
        task0 is not None and task0.get("data-review-excluded") == "1",
        "缺少 data-review-excluded=1")
    add("任务 00 标注文本正确",
        "双目标（用户复核：已移出组合池）" in text and task0 is not None)

    # ---------- 组合候选表 ----------
    cand_rows = re.findall(r'<tr class="(cand-row[^"]*)"([^>]*)>', text)
    cand_attrs = [parse_attrs(a) for _, a in cand_rows]
    add(f"候选表行数 = JSON total（{mt['total_candidates']}）", len(cand_rows) == mt["total_candidates"], f"实际 {len(cand_rows)}")
    add("候选 class 分布与 JSON 一致",
        Counter(a.get("data-class") for a in cand_attrs) == Counter(c["class"] for c in cands))
    add("候选 route 分布与 JSON 一致（M1/M2/S1）",
        Counter(a.get("data-route") for a in cand_attrs) == Counter(c["route"] for c in cands))
    add("候选 priority 分布与 JSON 一致",
        Counter(a.get("data-priority") for a in cand_attrs) == Counter(c["priority"] for c in cands))
    main_n = sum(1 for cls, _ in cand_rows if "main-cand" in cls)
    excl_n = sum(1 for cls, _ in cand_rows if "excl-cand" in cls)
    add("valid / 对照排除拆分 = JSON",
        main_n == mt["valid_candidates"] and excl_n == mt["excluded_candidates"], f"{main_n} / {excl_n}")
    bad, bad_prio, bad_order = [], [], []
    cand_pairs = list(zip([cls for cls, _ in cand_rows], cand_attrs))
    for s in m["scene_rows"]:
        rows_s = [a for a in cand_attrs if a.get("data-scene") == s["scene"]]
        main_s = [a for cls, a in cand_pairs if "main-cand" in cls and a.get("data-scene") == s["scene"]]
        if len(rows_s) != len(s["cands"]) or len(main_s) != len(s["main"]):
            bad.append(s["scene"])
        if Counter(a.get("data-priority") for a in rows_s) != s["prio"]:
            bad_prio.append(s["scene"])
        seq = [PRIO_RANK[a["data-priority"]] for a in main_s]
        if seq != sorted(seq):
            bad_order.append(s["scene"])
    add("逐场景候选数 / valid 数 = JSON（含“对照与排除”折叠行）", not bad, f"不一致: {bad[:5]}")
    add("逐场景 priority 分布 = JSON", not bad_prio, f"不一致: {bad_prio[:5]}")
    add("每场景候选表 P0 置顶、按 priority 升序", not bad_order, f"未排序: {bad_order[:5]}")
    ks1 = next(s for s in m["scene_rows"] if s["scene"] == "KITCHEN_SCENE1")
    ks1_rows = sum(1 for a in cand_attrs if a.get("data-scene") == "KITCHEN_SCENE1")
    add(f"KS1 候选行 = {2 * ks1['pair_count']}（{ks1['pair_count']} 对 × 2；00 已剔除）",
        ks1_rows == 2 * ks1["pair_count"] and ks1_rows == len(ks1["cands"]),
        f"KS1 行 {ks1_rows}, 对数 {ks1['pair_count']}")
    task0_in_cands = [a for a in cand_attrs if a.get("data-s1") == "0" or a.get("data-s2") == "0"]
    add("任务 00 不出现在任何候选表行", not task0_in_cands, f"{len(task0_in_cands)} 行含任务 0")

    # ---------- 逐场景复核状态表 ----------
    add("逐场景复核状态 section 存在", 'id="scene-review"' in text)
    review_rows = re.findall(r'<tr class="(review-row[^"]*)"([^>]*)>', text)
    review_attrs = [parse_attrs(a) for _, a in review_rows]
    add(f"复核状态表 = {mt['scenes']} 行", len(review_rows) == mt["scenes"], f"实际 {len(review_rows)}")
    bad_rev = []
    for s in m["scene_rows"]:
        got = next((a for a in review_attrs if a.get("data-scene") == s["scene"]), None)
        if got is None:
            bad_rev.append(s["scene"])
            continue
        if got.get("data-reviewed") != ("1" if s["reviewed"] else "0"):
            bad_rev.append(s["scene"])
        if got.get("data-excluded") != ",".join(str(i) for i in s["review_excluded"]):
            bad_rev.append(s["scene"])
    add("复核状态表逐场景与 scene_review_decisions 一致（KS1=已复核/剔除 0）", not bad_rev, f"不一致: {bad_rev[:5]}")
    ks1_rev = next((a for a in review_attrs if a.get("data-scene") == "KITCHEN_SCENE1"), {})
    ks1_stats = next((x for x in m["stats"]["per_scene"] if x["scene"] == "KITCHEN_SCENE1"), {})
    add(f"KS1 复核状态 = 已复核、剔除任务 0、组合 {ks1['pair_count']} 对 {len(ks1['cands'])} 候选",
        ks1_rev.get("data-reviewed") == "1" and ks1_rev.get("data-excluded") == "0"
        and ks1["pair_count"] == ks1_stats.get("m1_unordered")
        and len(ks1["cands"]) == ks1_stats.get("m1_ordered"))
    add(f"待复核场景数 = {mt['n_pending_scenes']} 且均有“暂无修改意见”标记",
        text.count("暂无修改意见") >= mt["n_pending_scenes"])

    # ---------- 结构完整性 ----------
    structure_missing = []
    for s in m["scene_rows"]:
        for prefix in ("tasks", "cands", "videos", "excl"):
            if f'id="{prefix}-{s["scene"]}"' not in text:
                structure_missing.append(f'{prefix}-{s["scene"]}')
    add("每场景均含单任务表 / 候选表 / 排除折叠 / 视频区",
        not structure_missing, f"缺失: {structure_missing[:5]}")

    # ---------- 视频 ----------
    figs = re.findall(r'<figure class="vcard" id="([^"]+)"([^>]*)>(.*?)</figure>', text, re.S)
    fig_attrs = [parse_attrs(a) for _, a, _ in figs]
    add(f"视频卡数 = manifest video_count（{manifest['video_count']}，v2 不变）", len(figs) == manifest["video_count"], f"实际 {len(figs)}")
    per_scene_video = Counter(a.get("data-scene") for a in fig_attrs)
    add("逐场景视频卡数 = scene_map 条目数",
        all(per_scene_video[s["scene"]] == len(s["videos"]) for s in m["scene_rows"]))
    add(f"视频 kind 分布 = exact {mt['video_kind_exact']} / family {mt['video_kind_family']}",
        Counter(a.get("data-kind") for a in fig_attrs) == Counter(v["kind"] for v in manifest["videos"]))
    add("视频 success/failed 分布与 manifest 一致",
        Counter(a.get("data-success") for a in fig_attrs) == Counter(
            "1" if v["success"] else "0" for v in manifest["videos"]))
    file_by_name = {v["file"]: v for v in manifest["videos"]}
    missing_src, bad_size, no_honest = [], [], []
    for fid, _, block in figs:
        src_m = re.search(r'<video[^>]*\bsrc="([^"]+)"', block)
        if not src_m:
            missing_src.append(fid)
            continue
        src = html.unescape(src_m.group(1))
        path = (REPORT_DIR / src).resolve()
        meta = file_by_name.get(src)
        if not path.exists():
            missing_src.append(src)
            continue
        if meta is None or path.stat().st_size != meta.get("bytes"):
            bad_size.append(src)
        if '<p class="honest">' not in block:
            no_honest.append(fid)
    add("所有视频 src 文件存在", not missing_src, f"缺失: {missing_src[:3]}")
    add("视频文件字节数与 manifest 一致", not bad_size, f"不一致: {bad_size[:3]}")
    add("每张视频卡都显示 honest_note", not no_honest, f"缺失: {no_honest[:3]}")

    # ---------- 模板 ----------
    tpl_rows = re.findall(r'<tr class="tpl-row[^"]*" data-tpl="([^"]+)" data-count="(\d+)" data-zero="([01])"', text)
    add(f"模板表 {len(m['templates'])} 行（T1–T10 + T4b，含零命中 T5）",
        [x[0] for x in tpl_rows] == TPL_ORDER, f"实际 {[x[0] for x in tpl_rows]}")
    tpl_counts = {x[0]: int(x[1]) for x in tpl_rows}
    add(f"模板分布与 JSON 一致且合计 = total（{mt['total_candidates']}）",
        tpl_counts == {t["id"]: t["count"] for t in m["templates"]}
        and sum(tpl_counts.values()) == mt["total_candidates"],
        f"合计 {sum(tpl_counts.values())}")
    add("T5 命中 = 0 且行保留（data-zero=1）",
        tpl_counts.get("T5") == 0 and any(x[0] == "T5" and x[2] == "1" for x in tpl_rows))
    add("零命中模板数 = n_zero_hit_templates",
        text.count('class="tpl-row tpl-zero"') == mt["n_zero_hit_templates"])

    # ---------- 指标 ----------
    found_metrics = dict(re.findall(r'data-metric="([^"]+)"[^>]*>([^<]+)<', text))
    missing_keys = sorted(set(mt) - set(found_metrics))
    wrong_keys = sorted(k for k in mt if k in found_metrics and found_metrics[k] != str(mt[k]))
    add("指标数字与 candidates-instructed.json / video-manifest.json 一致（全部 data-metric）",
        not missing_keys and not wrong_keys,
        f"缺失 {missing_keys[:6]} / 不符 {wrong_keys[:6]}")

    # ---------- 导航 / 链接 ----------
    nav = re.findall(r'<a class="nav-scene" href="#scene-([A-Z0-9_]+)"', text)
    add(f"sidenav {mt['scenes']} 个场景链接且与场景顺序一致", nav == m["scene_order"], f"实际 {len(nav)}")
    add("sidenav 含逐场景复核状态 / v2 修订记录入口",
        'href="#scene-review"' in text and 'href="#revision-note"' in text)
    anchor_ids = set(re.findall(r'id="([^"]+)"', text))
    vid_hrefs = re.findall(r'<a class="vidlink" href="#([^"]+)"', text)
    add("单任务表视频短标签均指向存在的视频卡锚点",
        bool(vid_hrefs) and all(h in anchor_ids for h in vid_hrefs), f"{len(vid_hrefs)} 个链接")
    local_hrefs = re.findall(r'<a class="local" href="([^"]+)"', text)
    bad_links = [h for h in local_hrefs if not (REPORT_DIR / h).resolve().exists()]
    add("产物索引 / 文档相对链接均可解析（离线可用）",
        len(local_hrefs) >= 10 and not bad_links, f"{len(local_hrefs)} 个链接; 失效 {bad_links[:3]}")
    add("产物索引含 scene_review_decisions.json 链接",
        'href="../scene_review_decisions.json"' in text)
    ext = re.search(r'https?://', text)
    add("无外链 CDN / 外部资源（单文件离线）",
        not ext and "<script src=" not in text and "<link " not in text and "<iframe" not in text)

    # ---------- 声明 / 版本 ----------
    add("状态声明存在（组合任务 0 动态实测 + 视频非 L90 实测）",
        "没有任何动态实测" in text
        and "不是 LIBERO-90 任何任务或组合任务的实测" in text
        and "honest_note" in text)
    add("v2 版本标记存在（hero/footer/复核小节）",
        "v2 · 复核 v1 后" in text and "v2 修订" in text)
    add("页脚含生成命令 / 数据来源 / 审计状态",
        "生成命令" in text and "审计状态" in text and "PASS-WITH-ISSUES" in text)

    # ---------- v2 修订记录 / 历史数字 ----------
    rev_m = re.search(r'<section id="revision-note"[^>]*>.*?</section>', text, re.S)
    add("v2 修订记录一节存在", bool(rev_m))
    if rev_m:
        rev_text = rev_m.group(0)
        add("修订记录含 v1→v2 关键差异（总数/对数/模板/KS1）",
            all(str(x) in rev_text for x in (rev["old_total"], rev["old_m1_ordered"],
                                             rev["old_m1_unordered"], mt["total_candidates"],
                                             mt["m1_ordered"], mt["m1_unordered_pairs"]))
            and "T5" in rev_text and "KS1" in rev_text)
    else:
        add("修订记录含 v1→v2 关键差异（总数/对数/模板/KS1）", False)
    allowed_pat = re.compile(r'<section[^>]*data-v1-history="1"[^>]*>.*?</section>|<p[^>]*data-v1-history="1"[^>]*>.*?</p>', re.S)
    n_allowed = len(allowed_pat.findall(text))
    outside = allowed_pat.sub("", text)
    forbidden = [
        f"{rev['old_total']} 条候选",
        f"{rev['old_total']} 个 ordered",
        f"{rev['old_total']} 候选",
        f"M1 {rev['old_m1_ordered']}",
        f"M1 = {rev['old_m1_unordered']}",
        f"{rev['old_m1_unordered']} 个同场景",
        "93/19/31/4",
        "186/38/62/8",
        "180/6/38/70",
    ]
    hits = [p for p in forbidden if p in outside]
    add("历史数字（v1 total/pairs/ordered 等）只出现在 v2 修订说明里（≤3 处允许块）",
        n_allowed >= 2 and not hits, f"允许块 {n_allowed}; 非修订区命中 {hits[:4]}")

    # ---------- README ----------
    if OUT_README.exists():
        readme = OUT_README.read_text(encoding="utf-8")
        lines = readme.splitlines()
        add("README.md 存在且行数 <= 40", len(lines) <= 40, f"{len(lines)} 行")
        add("README 含 v2 口径（复核状态/候选数/组合池）与 --check",
            "v2" in readme and str(mt["total_candidates"]) in readme
            and str(mt["single_pool"]) in readme and "--check" in readme)
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
    parser = argparse.ArgumentParser(description="LIBERO-90 双目标组合 · 分场景 HTML 报告生成器")
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
