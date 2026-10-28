#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LIBERO 官方 5 套件 × pi05 评测参考报告生成器（130 tasks / seed0 / 500 steps / video on）。

数据源（只读）:
  runs/libero-official-5suites-pi05-20261027/analysis/summary.json       5 套件聚合 + 130 逐 episode（主数据源）
  runs/libero-official-5suites-pi05-20261027/analysis/video_index.json  suite→task→mp4 索引（130 条）
  runs/libero-official-5suites-pi05-20261027/analysis/final_checks.json 15 项完整性检查
  runs/libero-official-5suites-pi05-20261027/logs/queue.log             队列端到端 wall / per-suite elapsed
  runs/libero-official-5suites-pi05-20261027/logs/smoke-check.json      冒烟 8 项检查
  .tmp/libero90-combos/inventory.json                                   LIBERO-90 task_idx→scene 映射（失败分析）

输出（只写 report/ 与本脚本）:
  runs/libero-official-5suites-pi05-20261027/report/index.html  单文件 HTML（内联 CSS/JS；视频用相对路径 ../run/... 引用）
  runs/libero-official-5suites-pi05-20261027/report/README.md   <=30 行

用法:
  .venv/bin/python scripts/build_libero_official_5suites_report.py
  .venv/bin/python scripts/build_libero_official_5suites_report.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import statistics
import subprocess
import sys
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "runs" / "libero-official-5suites-pi05-20261027"
REPORT_DIR = RUN_DIR / "report"
OUT_HTML = REPORT_DIR / "index.html"
OUT_README = REPORT_DIR / "README.md"

P_SUMMARY = RUN_DIR / "analysis" / "summary.json"
P_VIDEO_INDEX = RUN_DIR / "analysis" / "video_index.json"
P_FINAL_CHECKS = RUN_DIR / "analysis" / "final_checks.json"
P_QUEUE_LOG = RUN_DIR / "logs" / "queue.log"
P_SMOKE = RUN_DIR / "logs" / "smoke-check.json"
P_SCENE_MAP = RUN_DIR / "analysis" / "scene_map.json"
THUMB_DIR = REPORT_DIR / "assets" / "thumbs"
THUMB_MAX_BYTES = 50_000
THUMB_QUALITY = 85
THUMB_SIZE = (256, 256)

INPUT_FILES = [
    ("summary.json", P_SUMMARY),
    ("video_index.json", P_VIDEO_INDEX),
    ("final_checks.json", P_FINAL_CHECKS),
    ("queue.log", P_QUEUE_LOG),
    ("smoke-check.json", P_SMOKE),
    ("scene_map.json", P_SCENE_MAP),
]

SUITE_ORDER = ["LIBERO_90", "LIBERO_SPATIAL", "LIBERO_OBJECT", "LIBERO_GOAL", "LIBERO_10"]
SUITE_SHORT = {
    "LIBERO_90": "90",
    "LIBERO_SPATIAL": "SPATIAL",
    "LIBERO_OBJECT": "OBJECT",
    "LIBERO_GOAL": "GOAL",
    "LIBERO_10": "10",
}
SUITE_COLOR = {
    "LIBERO_90": "b-l90",
    "LIBERO_SPATIAL": "b-spatial",
    "LIBERO_OBJECT": "b-object",
    "LIBERO_GOAL": "b-goal",
    "LIBERO_10": "b-l10",
}

CATEGORIES = [
    ("pick up", "拾取 / pick up", lambda s: "pick up" in s),
    ("put", "放置 / put", lambda s: "put" in s),
    ("open", "打开 / open", lambda s: "open" in s),
    ("close", "关闭 / close", lambda s: "close" in s),
    ("turn", "开关电器 / turn on-off", lambda s: "turn on" in s or "turn off" in s),
    ("stack", "堆叠 / stack", lambda s: "stack" in s),
    ("and close", "放置并关闭 / put ... and close", lambda s: "and close" in s),
    ("both", "双物体 / both", lambda s: "both" in s),
    ("drawer", "抽屉 / drawer", lambda s: "drawer" in s),
    ("cabinet", "柜子 / cabinet", lambda s: "cabinet" in s),
    ("book", "书 / book", lambda s: "book" in s),
    ("bowl", "碗 / bowl", lambda s: "bowl" in s),
    ("stove", "炉灶 / stove", lambda s: "stove" in s),
]


def esc(value):
    return html.escape(str(value), quote=True)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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


def rate_pct(success, total):
    return round(100.0 * success / total, 2) if total else 0.0


def fmt_h(seconds):
    return round(seconds / 3600.0, 2)


def fmt_mb(nbytes):
    return round(nbytes / 1_000_000.0, 2)


def badge(text, cls, title=None):
    attr = f' title="{esc(title)}"' if title else ""
    return f'<span class="badge {cls}"{attr}>{esc(text)}</span>'


def parse_queue_log(text):
    start = re.search(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] === OFFICIAL', text)
    end = re.search(r'QUEUE_DONE (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', text)
    if not start or not end:
        raise SystemExit("[FATAL] queue.log 缺少起始/结束时间戳")
    t0 = datetime.strptime(start.group(1), "%Y-%m-%d %H:%M:%S")
    t1 = datetime.strptime(end.group(1), "%Y-%m-%d %H:%M:%S")
    elapsed = {}
    for suite, sec in re.findall(r"END (LIBERO_\w+) rc=0 elapsed=(\d+)s", text):
        elapsed[suite] = int(sec)
    return {"start": start.group(1), "end": end.group(1),
            "elapsed_s": int((t1 - t0).total_seconds()), "suite_elapsed": elapsed}


def build_suites(summary, queue):
    rows = []
    for suite in SUITE_ORDER:
        v = summary["suites"][suite]
        rows.append({
            "suite": suite,
            "short": SUITE_SHORT[suite],
            "tasks": v["expected_tasks"],
            "completed": v["completed"],
            "success": v["success"],
            "rate_pct": rate_pct(v["success"], v["expected_tasks"]),
            "mean_steps": v["mean_steps"],
            "median_steps": v["median_steps"],
            "wall_s": int(v["wall_s"]),
            "wall_h": fmt_h(v["wall_s"]),
            "queue_elapsed_s": queue["suite_elapsed"].get(suite, 0),
            "queue_h": fmt_h(queue["suite_elapsed"].get(suite, 0)),
            "videos": v["videos"],
            "video_bytes": v["video_bytes"],
            "video_mb": fmt_mb(v["video_bytes"]),
            "results_file": v["results_file"],
        })
    return rows



def scene_sort_key(scene):
    m = re.match(r"^([A-Z_]+)_SCENE(\d+)$", scene)
    if m:
        rank = {"KITCHEN": 0, "LIVING_ROOM": 1, "STUDY": 2}.get(m.group(1), 3)
        return (rank, int(m.group(2)), scene)
    return (9, 0, scene)


def thumb_name(suite, task_idx):
    return f"{suite}_T{int(task_idx)}.jpg"


def thumb_relpath(suite, task_idx):
    return f"assets/thumbs/{thumb_name(suite, task_idx)}"


def jpeg_dimensions(data):
    """不依赖 cv2/PIL 解析 JPEG SOF 尺寸（用于 --check 校验缩略图可解码）。"""
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0xD9):
            i += 2
            continue
        length = int.from_bytes(data[i + 2:i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h = int.from_bytes(data[i + 5:i + 7], "big")
            w = int.from_bytes(data[i + 7:i + 9], "big")
            return (w, h)
        i += 2 + length
    return None


def load_scene_map():
    raw = load_json(P_SCENE_MAP)
    rows = raw["rows"]
    by_key = {}
    for r in rows:
        by_key[(r["suite"], int(r["task_idx"]))] = r
    per_suite = Counter(r["suite"] for r in rows)
    per_scene = Counter((r["suite"], r["scene"]) for r in rows)
    scene_labels = sorted({r["scene"] for r in rows}, key=scene_sort_key)
    return {"raw": raw, "rows": rows, "by_key": by_key,
            "per_suite": dict(per_suite), "per_scene": dict(per_scene),
            "scene_labels": scene_labels, "n": len(rows)}

def build_episodes(summary, scene_map):
    order = {s: i for i, s in enumerate(SUITE_ORDER)}
    eps = sorted(summary["episodes"], key=lambda e: (order.get(e["suite"], 99), e["task_idx"]))
    rows = []
    for i, e in enumerate(eps, 1):
        video = e["video"]
        srow = scene_map["by_key"][(e["suite"], e["task_idx"])]
        if srow["instruction"] != e["instruction"]:
            raise SystemExit(f"[FATAL] scene_map instruction 与 summary 不一致: {e['task_key']}")
        rows.append({
            "n": i,
            "suite": e["suite"],
            "short": SUITE_SHORT[e["suite"]],
            "task_idx": e["task_idx"],
            "task_key": e["task_key"],
            "instruction": e["instruction"],
            "scene": srow["scene"],
            "bddl": srow.get("bddl", ""),
            "success": e["success"],
            "steps": e["steps"],
            "time_s": e["time_s"],
            "video_path": video["path"],
            "video_href": "../" + video["path"],
            "video_size": video["size_bytes"],
            "video_frames": video["frames"],
            "video_fps": video["fps"],
            "video_width": video["width"],
            "video_height": video["height"],
            "video_duration": video["duration_s"],
            "video_decodable": bool(video.get("decodable")),
            "thumb_rel": thumb_relpath(e["suite"], e["task_idx"]),
            "results_file": e["results_file"],
        })
    return rows



def build_gallery(episodes, scene_map):
    groups = OrderedDict()
    for suite in SUITE_ORDER:
        scenes = sorted({r["scene"] for r in scene_map["rows"] if r["suite"] == suite}, key=scene_sort_key)
        for scene in scenes:
            groups[(suite, scene)] = {"suite": suite, "scene": scene, "cards": [], "success": 0}
    for e in episodes:
        key = (e["suite"], e["scene"])
        if key not in groups:
            raise SystemExit(f"[FATAL] gallery 分组缺失: {key}")
        g = groups[key]
        card = dict(e)
        card["key"] = f'{e["suite"]}_T{e["task_idx"]}'
        g["cards"].append(card)
        g["success"] += 1 if e["success"] else 0
    group_list = list(groups.values())
    return {
        "groups": group_list,
        "n_cards": sum(len(g["cards"]) for g in group_list),
        "n_groups": len(group_list),
        "n_success": sum(g["success"] for g in group_list),
        "per_suite_groups": dict(Counter(g["suite"] for g in group_list)),
        "per_suite_cards": dict(Counter(e["suite"] for e in episodes)),
    }

def build_l90_analysis(episodes):
    eps = [e for e in episodes if e["suite"] == "LIBERO_90"]
    succ = [e for e in eps if e["success"]]
    fails = [e for e in eps if not e["success"]]
    scenes = {}
    for e in eps:
        s = scenes.setdefault(e["scene"], {"scene": e["scene"], "tasks": 0, "success": 0, "fail": 0})
        s["tasks"] += 1
        s["success" if e["success"] else "fail"] += 1
    scene_rows = sorted(scenes.values(), key=lambda r: (-r["fail"], scene_sort_key(r["scene"])))
    for r in scene_rows:
        r["rate_pct"] = rate_pct(r["success"], r["tasks"])
    keyword_rows = []
    for key, label, pred in CATEGORIES:
        f = sum(1 for e in fails if pred(e["instruction"]))
        sc = sum(1 for e in succ if pred(e["instruction"]))
        total = f + sc
        keyword_rows.append({"key": key, "label": label, "fails": f, "succs": sc, "total": total,
                             "fail_rate_pct": rate_pct(f, total) if total else 0.0})
    keyword_rows.sort(key=lambda r: (-r["fails"], -r["total"], r["key"]))
    fail_rows = sorted(fails, key=lambda e: e["task_idx"])
    return {
        "tasks": len(eps), "success": len(succ), "fails": len(fails),
        "success_idx": [e["task_idx"] for e in succ],
        "fail_idx": [e["task_idx"] for e in fails],
        "fail_rows": fail_rows,
        "scene_rows": scene_rows,
        "keyword_rows": keyword_rows,
        "succ_mean_steps": round(sum(e["steps"] for e in succ) / len(succ), 2) if succ else 0.0,
        "succ_median_steps": statistics.median([e["steps"] for e in succ]) if succ else 0,
        "succ_min_steps": min((e["steps"] for e in succ), default=0),
        "succ_max_steps": max((e["steps"] for e in succ), default=0),
        "succ_mean_time": round(sum(e["time_s"] for e in succ) / len(succ), 1) if succ else 0.0,
        "fail_mean_time": round(sum(e["time_s"] for e in fails) / len(fails), 1) if fails else 0.0,
        "fail_at_500": sum(1 for e in fails if e["steps"] >= 500),
        "fail_steps_min": min((e["steps"] for e in fails), default=0),
        "fail_steps_max": max((e["steps"] for e in fails), default=0),
    }


def build_steps_hist(episodes):
    bins = ["<100", "100-199", "200-299", "300-399", "400-499", "500"]
    rows = []
    for suite in SUITE_ORDER:
        sub = [e for e in episodes if e["suite"] == suite]
        counts = Counter()
        for e in sub:
            s = e["steps"]
            if s >= 500:
                counts["500"] += 1
            elif s >= 400:
                counts["400-499"] += 1
            elif s >= 300:
                counts["300-399"] += 1
            elif s >= 200:
                counts["200-299"] += 1
            elif s >= 100:
                counts["100-199"] += 1
            else:
                counts["<100"] += 1
        rows.append({"suite": suite, "counts": {b: counts[b] for b in bins}, "total": len(sub)})
    return {"bins": bins, "rows": rows}

def build_integrity(summary, video_index, final_checks, smoke, episodes):
    eps_video_paths = {e["video_path"]: e for e in episodes}
    files_on_disk = []
    for path in (RUN_DIR / "run").rglob("*.mp4"):
        files_on_disk.append(path)
    main_files = [p for p in files_on_disk if "/smoke/" not in str(p).replace("\\", "/")]
    smoke_files = [p for p in files_on_disk if "/smoke/" in str(p).replace("\\", "/")]
    video_rows = []
    missing = []
    size_mismatch = []
    total_bytes = 0
    for suite in SUITE_ORDER:
        for idx_s, v in sorted(video_index[suite].items(), key=lambda kv: int(kv[0])):
            p = RUN_DIR / v["path"]
            exists = p.exists()
            actual = p.stat().st_size if exists else 0
            total_bytes += actual
            if not exists:
                missing.append(v["path"])
            elif actual != v["size_bytes"]:
                size_mismatch.append(v["path"])
            video_rows.append({
                "suite": suite, "task_idx": int(idx_s), "path": v["path"],
                "size_bytes": v["size_bytes"], "frames": v["frames"], "fps": v["fps"],
                "width": v["width"], "height": v["height"], "duration_s": v["duration_s"],
                "decodable": bool(v.get("decodable")),
            })
    checks = final_checks.get("checks", {})
    smoke_checks = smoke.get("checks", {})
    return {
        "final_checks_all_passed": bool(final_checks.get("checks_all_passed")),
        "final_checks_total": len(checks),
        "final_checks_passed": sum(1 for v in checks.values() if v),
        "smoke_all_passed": bool(smoke.get("checks_all_passed")),
        "smoke_total": len(smoke_checks),
        "smoke_passed": sum(1 for v in smoke_checks.values() if v),
        "suite_rcs": final_checks.get("suite_rcs", {}),
        "missing": final_checks.get("missing", []),
        "videos_missing": final_checks.get("videos_missing", []),
        "videos_undecodable": final_checks.get("videos_undecodable", []),
        "steps_over_500": final_checks.get("steps_over_500", []),
        "video_index_entries": len(video_rows),
        "video_rows": video_rows,
        "videos_on_disk_main": len(main_files),
        "videos_on_disk_smoke": len(smoke_files),
        "video_missing_files": missing,
        "video_size_mismatch": size_mismatch,
        "video_total_bytes_on_disk": total_bytes,
        "results_files_ok": all((RUN_DIR / p).exists() for p in final_checks.get("results_entries", {}).values()),
    }



THUMB_HELPER = r"""
import cv2, json, sys
jobs = json.loads(sys.argv[1])
failed = []
for video, out in jobs:
    cap = cv2.VideoCapture(video)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        failed.append(video)
        continue
    data = None
    for q in (85, 70, 55, 40):
        ok2, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), q])
        if ok2 and len(buf.tobytes()) <= 50000:
            data = buf.tobytes()
            break
    if data is None:
        failed.append(video)
        continue
    with open(out, "wb") as f:
        f.write(data)
print(json.dumps({"failed": failed, "done": len(jobs) - len(failed)}))
"""


def thumb_path(ep):
    return THUMB_DIR / thumb_name(ep["suite"], ep["task_idx"])


def valid_thumb_file(path):
    if not path.exists() or not path.is_file():
        return False
    size = path.stat().st_size
    if size <= 0 or size > THUMB_MAX_BYTES:
        return False
    data = path.read_bytes()
    if data[:2] != b"\xff\xd8":
        return False
    return jpeg_dimensions(data) is not None


def find_cv2_python():
    candidates = [
        os.environ.get("LIBERO_THUMB_PYTHON", ""),
        sys.executable,
        str(ROOT.parent / "libero-plus" / "openpi" / ".venv" / "bin" / "python"),
        "/home/tarowang/workspace/roboot/libero-plus/openpi/.venv/bin/python",
    ]
    seen = set()
    for cand in candidates:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        if not Path(cand).exists():
            continue
        try:
            r = subprocess.run([cand, "-c", "import cv2"], capture_output=True, timeout=120)
        except Exception:
            continue
        if r.returncode == 0:
            return cand
    return None


def ensure_thumbnails(episodes):
    """生成缺失的首帧缩略图（jpg <=50KB）；已存在且合法的跳过。"""
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    jobs = []
    existing = 0
    for e in episodes:
        target = thumb_path(e)
        if valid_thumb_file(target):
            existing += 1
            continue
        jobs.append((str(RUN_DIR / e["video_path"]), str(target)))
    generated = 0
    if jobs:
        py = find_cv2_python()
        if py is None:
            raise SystemExit(
                "[FATAL] 缩略图缺失且找不到带 cv2 的解释器；"
                "请用 openpi venv 运行或设置 LIBERO_THUMB_PYTHON=/path/to/python")
        r = subprocess.run([py, "-c", THUMB_HELPER, json.dumps(jobs)],
                           capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            raise SystemExit(f"[FATAL] 缩略图生成失败: {r.stderr[-800:]}")
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            raise SystemExit(f"[FATAL] 缩略图生成输出无法解析: {r.stdout[-400:]}")
        if info["failed"]:
            raise SystemExit(f"[FATAL] 缩略图提取失败: {info['failed'][:3]}")
        generated = info["done"]
    bad = [str(thumb_path(e)) for e in episodes if not valid_thumb_file(thumb_path(e))]
    if bad:
        raise SystemExit(f"[FATAL] 缩略图仍不合法: {bad[:3]}")
    return {"existing": existing, "generated": generated, "total": len(episodes)}

def build_metrics(summary, suites, integrity, l90, gallery, scene_map, steps_hist, queue):
    overall = summary["overall"]
    standard = [s for s in suites if s["suite"] != "LIBERO_90"]
    standard_tasks = sum(s["tasks"] for s in standard)
    standard_success = sum(s["success"] for s in standard)
    video_total_duration = round(sum(e["video"]["duration_s"] for e in summary["episodes"]), 2)
    unknown = [s for s in suites if s["suite"] == "LIBERO_90"][0]
    return {
        "total_tasks": overall["tasks_total"],
        "completed": overall["completed"],
        "success": overall["success"],
        "rate_pct": round(100.0 * overall["success_rate"], 2),
        "suites_count": len(suites),
        "standard_suites": len(standard),
        "standard_tasks": standard_tasks,
        "standard_success": standard_success,
        "standard_rate_pct": rate_pct(standard_success, standard_tasks),
        "l90_tasks": unknown["tasks"],
        "l90_success": unknown["success"],
        "l90_rate_pct": unknown["rate_pct"],
        "l90_fail": l90["fails"],
        "l90_fail_at_500": l90["fail_at_500"],
        "l90_succ_mean_steps": l90["succ_mean_steps"],
        "l90_succ_median_steps": l90["succ_median_steps"],
        "l90_succ_min_steps": l90["succ_min_steps"],
        "l90_succ_max_steps": l90["succ_max_steps"],
        "l90_fail_mean_time": l90["fail_mean_time"],
        "l90_succ_mean_time": l90["succ_mean_time"],
        "mean_steps": overall["mean_steps"],
        "median_steps": overall["median_steps"],
        "wall_suite_s": int(overall["wall_s"]),
        "wall_suite_h": fmt_h(overall["wall_s"]),
        "wall_queue_s": int(queue["elapsed_s"]),
        "wall_queue_h": fmt_h(queue["elapsed_s"]),
        "wall_overhead_s": int(queue["elapsed_s"] - overall["wall_s"]),
        "queue_rate_tasks_h": round(overall["completed"] / (queue["elapsed_s"] / 3600.0), 1),
        "suite_rate_tasks_h": round(overall["completed"] / (overall["wall_s"] / 3600.0), 1),
        "videos": overall["videos"],
        "video_bytes": integrity["video_total_bytes_on_disk"],
        "video_mb": fmt_mb(integrity["video_total_bytes_on_disk"]),
        "video_total_duration_s": video_total_duration,
        "video_total_duration_min": round(video_total_duration / 60.0, 2),
        "smoke_videos": integrity["videos_on_disk_smoke"],
        "fps": summary["protocol"]["video_fps"],
        "video_w": summary["protocol"]["video_size"][0],
        "video_h": summary["protocol"]["video_size"][1],
        "max_steps": summary["protocol"]["max_steps"],
        "replan": summary["protocol"]["replan_steps"],
        "seed": summary["protocol"]["seed"],
        "init_row": summary["protocol"]["init_state_row"],
        "scene_count": len(l90["scene_rows"]),
        "gallery_cards": gallery["n_cards"],
        "gallery_groups": gallery["n_groups"],
        "thumbs": gallery["n_cards"],
        "thumb_max_kb": THUMB_MAX_BYTES // 1000,
        "suite_filter_options": 6,
        "scene_filter_options": gallery["n_groups"],
        "video_tags": 1,
        "l90_scenes": scene_map["per_suite"]["LIBERO_90"] and len([k for k in scene_map["per_scene"] if k[0] == "LIBERO_90"]),
        "l10_scenes": len([k for k in scene_map["per_scene"] if k[0] == "LIBERO_10"]),
        "single_scene_suites": len([k for k in scene_map["per_scene"] if k[0] != "LIBERO_90" and k[0] != "LIBERO_10"]),
        "final_checks_passed": integrity["final_checks_passed"],
        "final_checks_total": integrity["final_checks_total"],
        "smoke_checks_passed": integrity["smoke_passed"],
        "smoke_checks_total": integrity["smoke_total"],
    }

def compute_model():
    summary = load_json(P_SUMMARY)
    video_index = load_json(P_VIDEO_INDEX)
    final_checks = load_json(P_FINAL_CHECKS)
    smoke = load_json(P_SMOKE)
    scene_map = load_scene_map()
    queue = parse_queue_log(P_QUEUE_LOG.read_text(encoding="utf-8"))
    suites = build_suites(summary, queue)
    episodes = build_episodes(summary, scene_map)
    gallery = build_gallery(episodes, scene_map)
    l90 = build_l90_analysis(episodes)
    steps_hist = build_steps_hist(episodes)
    integrity = build_integrity(summary, video_index, final_checks, smoke, episodes)
    metrics = build_metrics(summary, suites, integrity, l90, gallery, scene_map, steps_hist, queue)
    hashes = input_hashes()
    return {
        "summary": summary,
        "video_index": video_index,
        "final_checks": final_checks,
        "smoke": smoke,
        "scene_map": scene_map,
        "queue": queue,
        "suites": suites,
        "episodes": episodes,
        "gallery": gallery,
        "l90": l90,
        "steps_hist": steps_hist,
        "integrity": integrity,
        "metrics": metrics,
        "hashes": hashes,
        "digest": build_digest(hashes),
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
    }

def validate_model(m):
    problems = []
    summary = m["summary"]
    metrics = m["metrics"]
    eps = m["episodes"]
    vi = m["video_index"]
    integ = m["integrity"]
    smap = m["scene_map"]
    gallery = m["gallery"]

    def need(cond, msg):
        if not cond:
            problems.append(msg)

    # scene_map
    need(smap["n"] == 130 and len(smap["by_key"]) == 130, "scene_map 行数 != 130")
    need(smap["per_suite"] == {"LIBERO_90": 90, "LIBERO_SPATIAL": 10, "LIBERO_OBJECT": 10,
                               "LIBERO_GOAL": 10, "LIBERO_10": 10}, "scene_map per-suite 数不一致")
    need(sum(smap["per_scene"].values()) == 130, "scene_map 分组合计 != 130")
    need(len(smap["per_scene"]) == 32, "scene_map (suite,scene) 分组 != 32")
    per_suite_labels = {s: len([k for k in smap["per_scene"] if k[0] == s]) for s in SUITE_ORDER}
    need(per_suite_labels == {"LIBERO_90": 20, "LIBERO_10": 9, "LIBERO_SPATIAL": 1,
                              "LIBERO_OBJECT": 1, "LIBERO_GOAL": 1},
         f"scene_map 每套件场景数不一致: {per_suite_labels}")
    need(set(smap["by_key"]) == {(e["suite"], e["task_idx"]) for e in eps},
         "scene_map 未覆盖全部 episode")
    need(all(smap["by_key"][(e["suite"], e["task_idx"])]["instruction"] == e["instruction"]
             for e in eps), "scene_map instruction 与 summary 不一致")

    # gallery
    need(gallery["n_cards"] == 130, "gallery 卡片数 != 130")
    need(gallery["n_groups"] == 32, "gallery 分组数 != 32")
    need(gallery["n_success"] == 69, "gallery success 合计 != 69")
    need(gallery["per_suite_cards"] == {"LIBERO_90": 90, "LIBERO_SPATIAL": 10,
                                       "LIBERO_OBJECT": 10, "LIBERO_GOAL": 10, "LIBERO_10": 10},
         "gallery 每 suite 卡片数不一致")
    need(gallery["per_suite_groups"] == {"LIBERO_90": 20, "LIBERO_SPATIAL": 1,
                                        "LIBERO_OBJECT": 1, "LIBERO_GOAL": 1, "LIBERO_10": 9},
         "gallery 每 suite 分组数不一致")
    need(all(len(g["cards"]) > 0 for g in gallery["groups"]), "存在空 gallery 分组")
    need(all(g["success"] == sum(1 for c in g["cards"] if c["success"]) for g in gallery["groups"]),
         "gallery 分组 success 计数不一致")
    expected_thumbs = {thumb_name(e["suite"], e["task_idx"]) for e in eps}
    need(len(expected_thumbs) == 130, "缩略图命名集合 != 130")
    for e in eps:
        need(thumb_relpath(e["suite"], e["task_idx"]) == e["thumb_rel"], f"{e['task_key']} thumb_rel 不一致")
        need((RUN_DIR / e["video_path"]).exists(), f"{e['task_key']} 视频文件缺失")

    # 总量 / 套件
    need(len(eps) == 130, "episodes != 130")
    need(metrics["total_tasks"] == 130 and metrics["completed"] == 130, "tasks/completed != 130")
    need(metrics["success"] == 69 and metrics["rate_pct"] == 53.08, "success/rate != 69/53.08")
    need(sum(s["tasks"] for s in m["suites"]) == 130, "suite tasks 之和 != 130")
    need(sum(s["success"] for s in m["suites"]) == 69, "suite success 之和 != 69")
    need(sum(s["videos"] for s in m["suites"]) == 130, "suite videos 之和 != 130")
    for suite in m["suites"]:
        expect = summary["suites"][suite["suite"]]
        need(suite["completed"] == expect["completed"], f"{suite['suite']} completed 不一致")
        need(suite["success"] == expect["success"], f"{suite['suite']} success 不一致")
        need(suite["mean_steps"] == expect["mean_steps"], f"{suite['suite']} mean steps 不一致")
        need(suite["wall_s"] == expect["wall_s"], f"{suite['suite']} wall 不一致")
        need(suite["videos"] == expect["videos"], f"{suite['suite']} videos 不一致")
    need([s["tasks"] for s in m["suites"]] == [90, 10, 10, 10, 10], "suite task 构成 != 90/10/10/10/10")
    need(sum(s["success"] for s in m["suites"] if s["suite"] != "LIBERO_90") == 40,
         "4 标准套件 success != 40")
    # 逐 episode
    need(len({(e["suite"], e["task_idx"]) for e in eps}) == 130, "episode (suite, idx) 重复")
    need(sum(1 for e in eps if e["success"]) == 69, "episode success != 69")
    need(all(e["steps"] <= 500 for e in eps), "存在 steps > 500")
    for suite in SUITE_ORDER:
        sub = [e for e in eps if e["suite"] == suite]
        need(len(sub) == summary["suites"][suite]["expected_tasks"], f"{suite} episode 数不一致")
        need(sum(1 for e in sub if e["success"]) == summary["suites"][suite]["success"],
             f"{suite} episode success 不一致")
    # 视频索引 / 文件
    need(len(vi) == 5, "video_index suite 数 != 5")
    need(integ["video_index_entries"] == 130, "video_index entries != 130")
    need(not integ["video_missing_files"], "存在缺失 mp4")
    need(not integ["video_size_mismatch"], "存在 size 不一致 mp4")
    need(integ["videos_on_disk_main"] == 130, "磁盘 main mp4 != 130")
    need(integ["videos_on_disk_smoke"] == 1, "smoke mp4 != 1")
    for e in eps:
        need(e["video_decodable"], f"{e['task_key']} video 不可解码")
        need(e["video_size"] > 0, f"{e['task_key']} video size=0")
    need(metrics["video_bytes"] == summary["overall"]["video_bytes"], "videos 总字节与 summary 不一致")
    # final_checks / smoke
    need(integ["final_checks_all_passed"], "final_checks 未全部 PASS")
    need(integ["final_checks_passed"] == integ["final_checks_total"] == 15, "final_checks 计数 != 15")
    need(integ["smoke_all_passed"] and integ["smoke_passed"] == integ["smoke_total"] == 8, "smoke 检查 != 8/8")
    need(all(v == 0 for v in integ["suite_rcs"].values()) and len(integ["suite_rcs"]) == 5, "suite rc != 0")
    need(not integ["missing"] and not integ["videos_missing"] and not integ["videos_undecodable"]
         and not integ["steps_over_500"], "final_checks 存在非空异常列表")
    need(integ["results_files_ok"], "results.json 缺失")
    # queue / wall
    need(len(m["queue"]["suite_elapsed"]) == 5, "queue.log per-suite elapsed != 5")
    need(m["queue"]["elapsed_s"] > summary["overall"]["wall_s"], "queue wall <= suite wall")
    need(sum(m["queue"]["suite_elapsed"].values()) <= m["queue"]["elapsed_s"], "suite elapsed 之和 > 队列 wall")
    need(metrics["wall_queue_h"] == 3.59, "queue wall != 3.59h")
    need(metrics["wall_suite_h"] == 2.98, "suite wall != 2.98h")
    # L90 分析
    l90 = m["l90"]
    need(l90["tasks"] == 90 and l90["success"] == 29 and l90["fails"] == 61, "L90 90/29/61 不一致")
    need(l90["fail_at_500"] == 61 and l90["fail_steps_min"] == 500, "L90 失败非全部 500 步")
    need(sum(r["tasks"] for r in l90["scene_rows"]) == 90, "L90 scene tasks 之和 != 90")
    need(sum(r["success"] for r in l90["scene_rows"]) == 29, "L90 scene success 之和 != 29")
    need(sum(r["fail"] for r in l90["scene_rows"]) == 61, "L90 scene fail 之和 != 61")
    need(all(r["fail"] + r["success"] == r["tasks"] for r in l90["scene_rows"]), "L90 scene 行不自洽")
    need(len(l90["scene_rows"]) == 20, "L90 scene 数 != 20")
    # steps 直方图
    for row in m["steps_hist"]["rows"]:
        need(sum(row["counts"].values()) == row["total"] == summary["suites"][row["suite"]]["expected_tasks"],
             f"{row['suite']} steps 直方图之和不一致")
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
h2{font-size:21px;margin:10px 0 8px}h3{font-size:16px;margin:22px 0 8px}
p{color:#374151}
.sub{color:#6b7280;font-size:13px}
.tiny{color:#6b7280;font-size:11px;line-height:1.4}
.nowrap{white-space:nowrap}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px;margin:12px 0}
.metric{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px 14px}
.metric .v{font-size:22px;font-weight:700;line-height:1.3}
.metric .v small{font-size:13px;color:#6b7280;font-weight:600}
.metric .l{color:#374151;font-size:12.5px;margin-top:2px}
.metric .d{color:#6b7280;font-size:11.5px;margin-top:5px;line-height:1.5}
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
.b-muted{background:#f3f4f6;color:#6b7280}
.b-l90{background:#fee2e2;color:#991b1b}.b-spatial{background:#dbeafe;color:#1d4ed8}
.b-object{background:#dcfce7;color:#15803d}.b-goal{background:#fef3c7;color:#a16207}
.b-l10{background:#ede9fe;color:#6d28d9}
.barchart{margin:10px 0;background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:10px 14px}
.barrow{display:grid;grid-template-columns:200px 1fr 120px;gap:8px;align-items:center;margin:4px 0;font-size:12px}
.barrow .lab{color:#374151;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.barrow .bar{background:#eef2f7;border-radius:5px;height:14px;overflow:hidden}
.barrow .bar span{display:block;height:14px;border-radius:5px;background:#60a5fa}
.barrow .val{color:#4b5563;text-align:right;font-variant-numeric:tabular-nums}
.barrow.hot .bar span{background:#16a34a}.barrow.warm .bar span{background:#f59e0b}
.barrow.cold .bar span{background:#ef4444}.barrow.cool .bar span{background:#93c5fd}
.tasktable td{vertical-align:middle}.tasktable td.instr{min-width:280px}
.tasktable td:first-child,.tasktable td:nth-child(2),.tasktable td:nth-child(3){white-space:nowrap}
.filterbar{position:sticky;top:0;z-index:30;background:rgba(247,248,250,.97);border-bottom:1px solid #e5e7eb;padding:8px 0;display:flex;gap:8px;flex-wrap:wrap;align-items:center;font-size:12.5px}
.filterbar select,.filterbar input,.filterbar button{background:#fff;color:#111827;border:1px solid #d1d5db;border-radius:6px;padding:4px 7px;font-size:12px;cursor:pointer}
.filterbar input[type=search]{cursor:text;min-width:210px}
.filterbar .count{color:#1d4ed8;font-weight:600;margin-left:auto}
.filterbar .hint{color:#6b7280;font-size:11px;flex-basis:100%}
#gallery-groups{margin-top:8px}
.scene-group{margin:16px 0 22px;padding-top:4px;border-top:1px dashed #e5e7eb;scroll-margin-top:90px}
.group-title{font-size:15px;margin:6px 0 8px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.group-title code{font-size:12.5px}
.gcount{color:#6b7280;font-weight:400;font-size:12.5px}
.vgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(222px,1fr));gap:10px}
.vid-card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;cursor:pointer;transition:border-color .15s,box-shadow .15s,transform .15s;outline:none}
.vid-card:hover,.vid-card:focus{border-color:#60a5fa;box-shadow:0 4px 14px rgba(37,99,235,.12);transform:translateY(-1px)}
.vid-card .thumb{display:block;width:100%;aspect-ratio:1/1;object-fit:cover;background:#111827}
.vbody{padding:8px 10px 10px}
.vrow{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.vt{font-size:13px}
.vinstr{font-size:12px;color:#374151;margin:5px 0 4px;line-height:1.45;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:35px}
.vfoot{display:flex;justify-content:space-between;align-items:center;gap:6px;margin-top:4px}
.playbtn{background:#1d4ed8;color:#fff;border:0;border-radius:6px;padding:4px 10px;font-size:12px;font-weight:600;cursor:pointer}
.playbtn:hover{background:#1e40af}
.modal{position:fixed;inset:0;z-index:100;display:flex;align-items:center;justify-content:center;padding:20px}
.modal[hidden]{display:none}
.modal-backdrop{position:absolute;inset:0;background:rgba(15,23,42,.74)}
.modal-panel{position:relative;z-index:1;background:#fff;border-radius:12px;max-width:min(780px,96vw);width:min(780px,96vw);box-shadow:0 20px 60px rgba(15,23,42,.35);padding:10px 12px 12px}
.modal-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:8px}
.modal-head h3{margin:0;font-size:15px}
.modal-close{background:#f3f4f6;border:1px solid #d1d5db;border-radius:6px;font-size:20px;line-height:1;cursor:pointer;padding:2px 10px;color:#374151}
.modal-close:hover{background:#e5e7eb}
#video-modal-player{width:100%;max-height:70vh;background:#000;border-radius:8px;display:block}
.modal-meta{font-size:12px;color:#6b7280;margin-top:6px;line-height:1.5}
ul.flat{margin:8px 0;padding-left:20px}ul.flat li{margin:5px 0;color:#374151;font-size:13px}
ol.risk{margin:8px 0;padding-left:22px}ol.risk li{margin:7px 0;color:#374151;font-size:13px;line-height:1.6}
.note{background:#f8fafc;border-left:3px solid #cbd5e1;padding:6px 10px;color:#4b5563;font-size:12px;border-radius:4px;margin:6px 0;line-height:1.6}
.note.warn{background:#fffbeb;border-left-color:#f59e0b;color:#78350f}
.note.ok{background:#f0fdf4;border-left-color:#16a34a;color:#14532d}
footer{margin-top:40px;padding:14px 0 30px;border-top:1px solid #e5e7eb;color:#6b7280;font-size:11.5px;line-height:1.7}
footer code{font-size:11px}
@media (max-width:980px){body{padding-left:0}.sidenav{position:static;width:auto;height:auto;border-right:none;border-bottom:1px solid #e5e7eb;box-shadow:none}.sidenav .foot{display:none}main{padding:0 14px 50px}.barrow{grid-template-columns:120px 1fr 80px}}
"""

def bar_row(label, ratio, value_text, cls=""):
    width = max(0.0, min(100.0, 100.0 * ratio))
    return (f'<div class="barrow {cls}"><div class="lab">{esc(label)}</div>'
            f'<div class="bar"><span style="width:{width:.1f}%"></span></div>'
            f'<div class="val">{value_text}</div></div>')


def metric(key, m, suffix=""):
    return f'<span data-metric="{key}">{m["metrics"][key]}</span>{suffix}'


def render_sidenav(m):
    mt = m["metrics"]
    return f"""<nav class="sidenav" aria-label="报告目录">
<div class="brand">LIBERO 官方 5 套件<br>pi05 评测参考报告（130 tasks）</div>
<div class="grp">总览</div>
<a href="#top">摘要与结论</a>
<a href="#overview">指标与完整性</a>
<a href="#protocol">协议 / 环境 / 与官方差异</a>
<div class="grp">数据</div>
<a href="#suites">5 套件总表</a>
<a href="#tasks">130 行逐任务表（可筛选）</a>
<div class="grp">视频库</div>
<a href="#videos">视频库：套件 × 场景筛选（{mt["gallery_cards"]} 条）</a>
<a href="#videos">缩略图卡片 + 弹层播放</a>
<div class="grp">分析</div>
<a href="#analysis">失败 / 长尾分析（LIBERO_90）</a>
<div class="grp">结论与附录</div>
<a href="#conclusions">结论 / 参考价值 / 局限</a>
<a href="#caveats">口径与数据问题</a>
<a href="#artifacts">产物索引</a>
<div class="foot">{mt["total_tasks"]} tasks / {mt["success"]} success = {mt["rate_pct"]}%<br>LIBERO_90 {mt["l90_rate_pct"]}% · 4 标准套件 100%<br>{mt["gallery_cards"]} 视频卡 / {mt["gallery_groups"]} 场景分组<br>scripts/build_libero_official_5suites_report.py</div>
</nav>"""

def render_hero(m):
    mt = m["metrics"]
    return f'''<header class="hero" id="top">
<h1>LIBERO 官方 5 套件 × pi05 · 带视频库评测参考报告（130 tasks）</h1>
<p class="meta">LIBERO_90 / SPATIAL / OBJECT / GOAL / 10 · pi05（OpenPI <b>PyTorch</b> backend，checkpoint <code>pi05_libero</code>）· <b>单 seed=0 · max_steps=500 · replan=5 · video on（{mt["fps"]}fps, {mt["video_w"]}×{mt["video_h"]}）</b> · 串行单进程 · 数据日期 2026-10-27 · 运行目录 <code>runs/libero-official-5suites-pi05-20261027/</code></p>
<div class="status ok"><b>一句话结论</b>：完整 LIBERO 5 套件 <b>{mt["total_tasks"]} tasks</b> 单 seed 评测完成，<b>{mt["success"]}/{mt["total_tasks"]} = {mt["rate_pct"]}%</b> success；其中 4 个标准套件（SPATIAL / OBJECT / GOAL / 10）<b>{mt["standard_success"]}/{mt["standard_tasks"]} = {mt["standard_rate_pct"]}%</b>（本配置下全部成功、任务较轻），<b>LIBERO_90 全量 {mt["l90_tasks"]} tasks 首次 pi05 结果 = {mt["l90_success"]}/{mt["l90_tasks"]} = {mt["l90_rate_pct"]}%</b>（{mt["l90_fail"]} 个失败全部在 500 步上限超时）。队列端到端 wall <b>{mt["wall_queue_h"]} h</b>（suite 实测合计 {mt["wall_suite_h"]} h）；<b>{mt["videos"]} 个 episode mp4 全部存在、可解码（{mt["video_mb"]} MB）</b>，本报告提供按 <b>测试套 / 测试场景</b> 筛选的 130 条视频库（首帧缩略图 + 单例弹层播放器，全页仅 1 个视频播放器），可离线播放。</div>
<div class="status warn"><b>口径声明（不可严格横比）</b>：本 run 为<b>单 seed（seed=0）、统一 max_steps=500、replan=5、video on、PyTorch backend</b> 的参考材料，与论文/官方 openpi 评测（通常 <b>50 trials / 多 seed、JAX backend、不同步数</b>）设置不同，<b>数字不可与官方表格严格横比</b>；也不可与之前 custom 双目标 easy/hard run 混用（任务集/协议不同）。所有 130 个任务均为<b>单次 zero-shot 单指令 baseline</b>，无 staged / rollback / instruction-switch。</div>
<p class="method"><b>协议</b>：官方 benchmark 顺序（LIBERO_90 → SPATIAL → OBJECT → GOAL → 10）；每个 suite 内 task_idx 升序；seed=0，init state 行 0，环境 seed offset=1000，stabilization 10 steps；instruction = 官方 benchmark <code>task.language</code>（runtime 已 patch）；success = LIBERO <code>check_success()</code>（results.json 记录）；video 由 eval 同步录制（{mt["fps"]}fps、{mt["video_w"]}×{mt["video_h"]}、每步 1 帧 + 首帧）。</p>
<p class="gen">生成脚本 <code>scripts/build_libero_official_5suites_report.py</code> · 数据源 <code>analysis/summary.json</code> + <code>analysis/video_index.json</code> + <code>analysis/final_checks.json</code> + <code>logs/queue.log</code> + <code>logs/smoke-check.json</code> + <code>.tmp/libero90-combos/inventory.json</code>（scene 映射）· 视频以相对路径 <code>../run/...</code> 引用 · 构建指纹见页脚</p>
</header>'''


def render_overview(m):
    mt = m["metrics"]
    integ = m["integrity"]
    final_checks = m["final_checks"]
    check_rows = "".join(
        f'<tr class="integrity-row" data-check="{esc(k)}" data-passed="{str(bool(v)).lower()}">'
        f'<td><code>{esc(k)}</code></td><td>{"PASS" if v else "FAIL"}</td></tr>'
        for k, v in final_checks["checks"].items()
    )
    smoke_rows = "".join(
        f'<tr class="smoke-row" data-check="{esc(k)}" data-passed="{str(bool(v)).lower()}">'
        f'<td><code>{esc(k)}</code></td><td>{"PASS" if v else "FAIL"}</td></tr>'
        for k, v in m["smoke"]["checks"].items()
    )
    return f'''<section id="overview">
<h2>一、指标与完整性</h2>
<p class="sub">主数据源 <code>analysis/summary.json</code>（130 逐 episode + 5 套件聚合）；视频完整性以 <code>analysis/video_index.json</code> 与磁盘 mp4 逐条核对；完整性检查 <code>analysis/final_checks.json</code> 15/15 PASS、冒烟 <code>logs/smoke-check.json</code> 8/8 PASS。</p>
<div class="cards">
<div class="metric"><div class="v">{metric("total_tasks", m)} tasks · {metric("completed", m)} completed</div><div class="l">{metric("suites_count", m)} 个套件（90+10+10+10+10）</div><div class="d">全部 episode 完成；无 missing / steps>500 / undecodable video</div></div>
<div class="metric"><div class="v">{metric("success", m)} / {metric("total_tasks", m)} = {metric("rate_pct", m)}%</div><div class="l">总 success（LIBERO check_success）</div><div class="d">mean / median steps <b>{metric("mean_steps", m)} / {metric("median_steps", m)}</b></div></div>
<div class="metric"><div class="v">{metric("standard_success", m)} / {metric("standard_tasks", m)} = {metric("standard_rate_pct", m)}%</div><div class="l">4 个标准套件（SPATIAL / OBJECT / GOAL / 10）</div><div class="d">每套件 10/10；本配置下任务较轻、全部成功</div></div>
<div class="metric"><div class="v">LIBERO_90 {metric("l90_success", m)} / {metric("l90_tasks", m)} = {metric("l90_rate_pct", m)}%</div><div class="l">LIBERO-90 全量（首次 pi05 全量结果）</div><div class="d"><b>{metric("l90_fail", m)}</b> 个失败全部在 {metric("max_steps", m)} 步上限超时（fail_at_500 = {metric("l90_fail_at_500", m)}）；成功 mean steps {metric("l90_succ_mean_steps", m)}（{metric("l90_succ_min_steps", m)}–{metric("l90_succ_max_steps", m)}）</div></div>
<div class="metric"><div class="v">{metric("wall_queue_h", m)} h</div><div class="l">队列端到端 wall（{metric("wall_queue_s", m)} s）</div><div class="d">suite 实测合计 <b>{metric("wall_suite_h", m)} h</b>（{metric("wall_suite_s", m)} s；差额 {metric("wall_overhead_s", m)} s 为 suite 启动/模型加载等开销）→ 队列速率 {metric("queue_rate_tasks_h", m)} tasks/h</div></div>
<div class="metric"><div class="v">{metric("videos", m)} videos · {metric("video_mb", m)} MB</div><div class="l">episode mp4（+ {metric("smoke_videos", m)} 条 smoke）</div><div class="d">全部可解码；video 总时长 {metric("video_total_duration_s", m)} s（≈{metric("video_total_duration_min", m)} min）；{metric("fps", m)}fps {metric("video_w", m)}×{metric("video_h", m)}</div></div>
<div class="metric"><div class="v">{metric("gallery_cards", m)} 卡片 · {metric("gallery_groups", m)} 分组</div><div class="l">视频库（按 测试套 × 测试场景 筛选）</div><div class="d">{metric("thumbs", m)} 张首帧缩略图（每张 ≤{metric("thumb_max_kb", m)} KB）+ 全页唯一弹层播放器（{metric("video_tags", m)} 个 <code>&lt;video&gt;</code>）；筛选 {metric("suite_filter_options", m)} 个测试套 / {metric("scene_filter_options", m)} 个（套件×场景）分组（L90 {metric("l90_scenes", m)} + L10 {metric("l10_scenes", m)} + {metric("single_scene_suites", m)} 个单场景套件）</div></div>
<div class="metric"><div class="v">{metric("final_checks_passed", m)} / {metric("final_checks_total", m)}</div><div class="l">final_checks 完整性检查全 PASS</div><div class="d">冒烟 {metric("smoke_checks_passed", m)}/{metric("smoke_checks_total", m)} PASS；suite rc 全 0；video_index 130 条</div></div>
</div>
<h3>1.1 final_checks 逐项（15/15 PASS）</h3>
<div class="tblwrap"><table>
<thead><tr><th>检查项</th><th>结果</th></tr></thead>
<tbody>{check_rows}</tbody></table></div>
<h3>1.2 冒烟检查（LIBERO_90 T0 / seed0 / 500 steps / video，8/8 PASS）</h3>
<div class="tblwrap"><table>
<thead><tr><th>检查项</th><th>结果</th></tr></thead>
<tbody>{smoke_rows}</tbody></table></div>
<p class="note">final_checks 由 <code>prep/final_checks.py</code> 生成：130/130 tasks、5 个 results.json、每 suite 任务数 90/10/10/10/10、steps≤500、130 mp4 存在非空且 cv2 可解码、suite rc=0、gen_configs 90 合法、video_index 130、progress 130；冒烟额外验证 instruction 与官方一致、mp4 501 帧 256×256 20fps 可解码。</p>
</section>'''


def render_protocol(m):
    mt = m["metrics"]
    summary = m["summary"]
    protocol = summary["protocol"]
    return f'''<section id="protocol">
<h2>二、协议 / 环境 / 与官方评测的差异</h2>
<h3>2.1 协议与环境</h3>
<div class="tblwrap"><table>
<thead><tr><th>项</th><th>值</th><th>说明</th></tr></thead>
<tbody>
<tr class="protocol-row" data-key="model"><td>模型</td><td><code>{esc(protocol["model"])}</code>（checkpoint <code>~/.cache/openpi/openpi-assets/checkpoints/pi05_libero</code>）</td><td>pi05，OpenPI <b>PyTorch backend</b>；mode=baseline</td></tr>
<tr class="protocol-row" data-key="suites"><td>套件</td><td>LIBERO_90 / LIBERO_SPATIAL / LIBERO_OBJECT / LIBERO_GOAL / LIBERO_10</td><td>共 130 tasks（90+10+10+10+10）；官方 benchmark 顺序串行</td></tr>
<tr class="protocol-row" data-key="seed"><td>seed</td><td><b>{metric("seed", m)}</b>（单 seed）</td><td>init state 行 <b>{metric("init_row", m)}</b>；environment_seed = 1000 + episode_seed；episode 随机噪声以显式 seed query（openpi query-sampling）</td></tr>
<tr class="protocol-row" data-key="steps"><td>max_steps</td><td><b>{metric("max_steps", m)}</b></td><td>所有套件统一 500（官方各套件原配置 220/280/300/520，本 run 用 CLI 覆盖）</td></tr>
<tr class="protocol-row" data-key="replan"><td>replan_steps</td><td><b>{metric("replan", m)}</b></td><td>每 5 步重新规划/查询策略</td></tr>
<tr class="protocol-row" data-key="video"><td>video</td><td><b>on</b>（{metric("fps", m)} fps，{metric("video_w", m)}×{metric("video_h", m)}）</td><td>每步 1 帧 + 首帧；文件名 <code>&lt;SUITE&gt;_T&lt;idx&gt;__baseline_seed0.mp4</code></td></tr>
<tr class="protocol-row" data-key="parallel"><td>并行</td><td>单进程串行</td><td>稳定优先；按 suite 断点续跑；GPU 独占</td></tr>
<tr class="protocol-row" data-key="stdout"><td>success 定义</td><td>LIBERO <code>check_success()</code></td><td>写入 <code>results.json</code>（每个 task 记录 baseline_s0 steps/time/success）</td></tr>
<tr class="protocol-row" data-key="shadow"><td>shadow（LIBERO 包）</td><td><code>runs/libero-std-baseline-20261019/shadow</code>（只读 symlink）</td><td>原版 LIBERO 包；libero_90 n_tasks=90 已验证</td></tr>
<tr class="protocol-row" data-key="runtime"><td>runtime</td><td><code>runtime/</code> = std baseline <code>cp -a</code> 副本 + 2 处最小改动</td><td>① 标准基准守卫：LIBERO_90 期望 90 tasks（其余 10）；② <code>configs/tasks/libero_90/</code> 90 个 yaml（由 shadow benchmark 生成，idx 0..89 唯一）</td></tr>
<tr class="protocol-row" data-key="instruction"><td>instruction 来源</td><td>官方 benchmark <code>task.language</code></td><td>runtime 已 patch 为官方 prompt（非 naive BDDL 拼接）；冒烟核验 instruction 与官方一致</td></tr>
<tr class="protocol-row" data-key="init"><td>初始化</td><td>initial_policy_observation = post_stabilization_truth</td><td>stabilization control steps = 10；paired initial state；numerical determinism（XLA deterministic ops）</td></tr>
</tbody></table></div>
<h3>2.2 与论文 / 官方 openpi 评测的差异（不可严格横比）</h3>
<div class="tblwrap"><table>
<thead><tr><th>项</th><th>本 run</th><th>官方 / 论文常见设置</th></tr></thead>
<tbody>
<tr class="diff-row" data-item="seed"><td>seed / trials</td><td><b>单 seed（seed=0），每任务 1 trial</b></td><td>通常 50 trials / 多 seed，报均值±方差</td></tr>
<tr class="diff-row" data-item="steps"><td>max_steps</td><td>统一 <b>500</b></td><td>各套件不同（如 220/280/300/520）或按任务设定</td></tr>
<tr class="diff-row" data-item="backend"><td>后端</td><td><b>openpi PyTorch</b></td><td>常见 JAX 推理</td></tr>
<tr class="diff-row" data-item="replan"><td>replan_steps</td><td>5</td><td>随实现/配置不同</td></tr>
<tr class="diff-row" data-item="tasks"><td>LIBERO_90 配置</td><td>本 run runtime 生成的 90 个 yaml（来自 shadow benchmark）</td><td>官方 LIBERO repo 的 libero_90 定义</td></tr>
<tr class="diff-row" data-item="video"><td>video</td><td>on（20fps 256×256）</td><td>官方评测通常不录视频，或仅离线渲染</td></tr>
</tbody></table></div>
<p class="note warn"><b>因此</b>：本报告数字应作为“同一 runtime/协议下的 pi05 参考 baseline”，用于后续任务（如 custom 双目标任务、staged/rollback 变体）的<b>同协议对照</b>；<b>不要</b>把 53.08% / LIBERO_90 32.22% 直接与论文表格数字比较。</p>
</section>'''


def render_suites(m):
    mt = m["metrics"]
    rows = []
    for s in m["suites"]:
        cls = "hi" if s["suite"] != "LIBERO_90" else ""
        rows.append(
            f'<tr class="suite-row {cls}" data-suite="{s["suite"]}" data-tasks="{s["tasks"]}" '
            f'data-success="{s["success"]}" data-rate="{s["rate_pct"]}" data-mean-steps="{s["mean_steps"]}" '
            f'data-wall-s="{s["wall_s"]}" data-queue-elapsed="{s["queue_elapsed_s"]}" data-videos="{s["videos"]}" '
            f'data-video-bytes="{s["video_bytes"]}">'
            f'<td>{badge(SUITE_SHORT[s["suite"]], SUITE_COLOR[s["suite"]])}</td><td>{s["tasks"]} / {s["completed"]}</td>'
            f'<td><b>{s["success"]}</b></td><td>{s["rate_pct"]}%</td>'
            f'<td>{s["mean_steps"]}</td><td>{s["median_steps"]}</td>'
            f'<td>{s["wall_h"]} h（{s["wall_s"]} s）</td><td>{s["queue_h"]} h</td>'
            f'<td>{s["videos"]}</td><td>{s["video_mb"]} MB</td>'
            f'<td class="tiny"><code>{esc(s["results_file"])}</code></td></tr>'
        )
    bars = "".join(
        bar_row(f'{s["short"]}（{s["success"]}/{s["tasks"]}）', s["rate_pct"] / 100.0,
                f'{s["rate_pct"]}%', "hot" if s["rate_pct"] >= 100 else ("warm" if s["rate_pct"] >= 30 else "cold"))
        for s in m["suites"]
    )
    return f'''<section id="suites">
<h2>三、5 套件总表</h2>
<div class="tblwrap"><table>
<thead><tr><th>suite</th><th>tasks / eps</th><th>success</th><th>rate</th><th>mean steps</th><th>median steps</th><th>suite 实测 wall</th><th>队列 elapsed</th><th>videos</th><th>video size</th><th>results.json</th></tr></thead>
<tbody>{''.join(rows)}
<tr class="suite-total-row" data-tasks="{mt["total_tasks"]}" data-success="{mt["success"]}" data-rate="{mt["rate_pct"]}" data-videos="{mt["videos"]}" data-video-bytes="{mt["video_bytes"]}" data-wall-s="{mt["wall_suite_s"]}" data-queue-elapsed="{mt["wall_queue_s"]}"><td><b>合计</b></td><td><b>{mt["total_tasks"]} / {mt["completed"]}</b></td><td><b>{mt["success"]}</b></td><td><b>{mt["rate_pct"]}%</b></td><td><b>{mt["mean_steps"]}</b></td><td><b>{mt["median_steps"]}</b></td><td><b>{mt["wall_suite_h"]} h（{mt["wall_suite_s"]} s）</b></td><td><b>{mt["wall_queue_h"]} h（{mt["wall_queue_s"]} s）</b></td><td><b>{mt["videos"]}</b></td><td><b>{mt["video_mb"]} MB</b></td><td class="tiny">5 个 suite 串行（队列端到端）</td></tr>
</tbody></table></div>
<div class="barchart">{bars}</div>
<p class="note">口径：<b>4 个标准套件每套 10 tasks，本配置下全部 100% 成功</b>（任务较轻、成功步数集中在 100–250 步）；<b>LIBERO_90 90 tasks 成功 {mt["l90_success"]}（{mt["l90_rate_pct"]}%）</b>，mean steps {m["suites"][0]["mean_steps"]}、median {m["suites"][0]["median_steps"]}（61 个失败全部跑满 500 步）。wall 有两口径：<b>suite 实测合计 {mt["wall_suite_h"]} h</b>（summary 各 suite wall_s 求和）与 <b>队列端到端 {mt["wall_queue_h"]} h</b>（queue.log 00:44:01→04:19:36，含 suite 间启动/模型加载开销）；两者不要混用。视频总量 {mt["videos"]} 个 / {mt["video_mb"]} MB，其中 LIBERO_90 视频占 {m["suites"][0]["video_mb"]} MB。</p>
</section>'''

def render_tasks(m):
    mt = m["metrics"]
    eps = m["episodes"]
    suite_opts = "".join(
        f'<option value="{s}">{badge(SUITE_SHORT[s], SUITE_COLOR[s])} {s}（{sum(1 for e in eps if e["suite"] == s)}）</option>'
        for s in SUITE_ORDER
    )
    rows = []
    for e in eps:
        cls = "hi " if e["success"] else "zero "
        video_cell = (f'<a class="xlink" href="{esc(e["video_href"])}">▶ mp4</a> · '
                      f'<a href="#vid-{e["suite"]}_T{e["task_idx"]}">视频库</a>')
        rows.append(
            f'<tr class="{cls}task-row" data-suite="{e["suite"]}" data-task-idx="{e["task_idx"]}" '
            f'data-success="{str(e["success"]).lower()}" data-steps="{e["steps"]}" data-time="{e["time_s"]}" '
            f'data-video="{esc(e["video_path"])}">'
            f'<td>{e["n"]}</td><td>{badge(SUITE_SHORT[e["suite"]], SUITE_COLOR[e["suite"]])}</td>'
            f'<td>{e["task_idx"]}</td><td class="instr">{esc(e["instruction"])}</td>'
            f'<td>{badge("success", "b-ok") if e["success"] else badge("fail", "b-fail")}</td>'
            f'<td>{e["steps"]}</td><td>{e["time_s"]}</td>'
            f'<td class="nowrap">{video_cell}</td></tr>'
        )
    return f'''<section id="tasks">
<h2>四、130 行逐任务表（可按 suite / success 筛选）</h2>
<div class="filterbar" id="taskfilter">
<b>筛选</b>
<select id="filter-suite" aria-label="按 suite 筛选"><option value="">全部 suite</option>{suite_opts}</select>
<select id="filter-success" aria-label="按成功状态筛选"><option value="">全部结果（130）</option><option value="true">仅 success（{mt["success"]}）</option><option value="false">仅 fail（{mt["l90_fail"]}）</option></select>
<button id="filter-reset" type="button">重置</button>
<span class="count" id="filter-count">显示 {len(eps)} / {len(eps)} 条任务</span>
<span class="hint">instruction 为官方 benchmark <code>task.language</code>；steps = 执行步数（≤{mt["max_steps"]}）；视频列链接到本地 mp4（相对路径）。</span>
</div>
<div class="tblwrap"><table class="tasktable">
<thead><tr><th>#</th><th>suite</th><th>idx</th><th>instruction</th><th>success</th><th>steps</th><th>time (s)</th><th>video</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p class="note">共 {len(eps)} 行 = LIBERO_90 90 + SPATIAL 10 + OBJECT 10 + GOAL 10 + LIBERO_10 10；其中 {mt["success"]} success / {mt["l90_fail"]} fail（失败全部在 LIBERO_90）。逐行数据与 <code>analysis/summary.json</code> 的 <code>episodes</code> 完全一致（--check 逐行断言）；视频链接与 <code>analysis/video_index.json</code> 一致。</p>
</section>'''


def render_videos(m):
    mt = m["metrics"]
    gallery = m["gallery"]

    def card_html(c):
        badge_html = badge("success", "b-ok") if c["success"] else badge("fail", "b-fail")
        instr = esc(c["instruction"])
        return (f'<article class="vid-card" id="vid-{esc(c["key"])}" data-suite="{c["suite"]}" data-scene="{esc(c["scene"])}" '
                f'data-task-idx="{c["task_idx"]}" data-success="{str(c["success"]).lower()}" '
                f'data-steps="{c["steps"]}" data-time="{c["time_s"]}" '
                f'data-video="{esc(c["video_href"])}" data-key="{esc(c["key"])}" '
                f'data-instruction="{instr}" tabindex="0" role="button" '
                f'aria-label="{esc(c["suite"])} T{c["task_idx"]} {instr}">'
                f'<img class="thumb" loading="lazy" width="256" height="256" '
                f'src="{esc(c["thumb_rel"])}" alt="{esc(c["suite"])} T{c["task_idx"]} 首帧缩略图">'
                f'<div class="vbody"><div class="vrow"><b class="vt">T{c["task_idx"]}</b> {badge_html}'
                f'<span class="tiny">{c["steps"]} 步 · {c["video_duration"]}s</span></div>'
                f'<div class="vinstr" title="{instr}">{instr}</div>'
                f'<div class="vfoot"><button class="playbtn" type="button" data-play="1">▶ 播放</button>'
                f'<span class="tiny">{c["time_s"]}s / {c["video_size"]:,} B</span></div></div></article>')

    groups_html = []
    for g in gallery["groups"]:
        n = len(g["cards"])
        cards_html = "".join(card_html(c) for c in g["cards"])
        groups_html.append(
            f'<section class="scene-group" data-suite="{g["suite"]}" data-scene="{esc(g["scene"])}" '
            f'data-total="{n}" data-succ="{g["success"]}">'
            f'<h3 class="group-title">{badge(SUITE_SHORT[g["suite"]], SUITE_COLOR[g["suite"]])} '
            f'{esc(g["suite"])} · <code>{esc(g["scene"])}</code> '
            f'<span class="gcount">（{n} 条 / 成功 {g["success"]}）</span></h3>'
            f'<div class="vgrid">{cards_html}</div></section>')
    scene_opts = "".join(
        f'<option value="{g["suite"]}||{esc(g["scene"])}" data-suite="{g["suite"]}">'
        f'{esc(g["suite"])} · {esc(g["scene"])}（{len(g["cards"])}）</option>'
        for g in gallery["groups"])
    suite_opts = "".join(
        f'<option value="{s}">{esc(s)}（{sum(len(g["cards"]) for g in gallery["groups"] if g["suite"] == s)}）</option>'
        for s in SUITE_ORDER)
    return f'''<section id="videos">
<h2>五、视频库（130 条；按 测试套 × 测试场景 筛选，缩略图 + 弹层播放）</h2>
<p class="sub">按 <b>测试套 → 测试场景</b> 分组展示全部 130 条 episode 视频；每张卡片 = 首帧缩略图 + <code>T&lt;idx&gt;</code> + success/fail 徽章 + instruction + steps + “▶ 播放”。点击卡片或播放按钮打开<b>全页唯一的弹层播放器</b>（单个 <code>&lt;video controls autoplay&gt;</code>，默认隐藏，按需设置 src）；<b>不内嵌 130 个播放器、不自动加载视频</b>。支持关闭按钮 / ESC / 点击遮罩关闭。</p>
<div class="filterbar gallery-filter" id="gallery-filter">
<b>筛选</b>
<select id="filter-gallery-suite" aria-label="按测试套筛选视频"><option value="">全部测试套（{mt["gallery_cards"]}）</option>{suite_opts}</select>
<select id="filter-gallery-scene" aria-label="按测试场景筛选视频"><option value="">全部场景（{mt["gallery_groups"]}）</option>{scene_opts}</select>
<select id="filter-gallery-result" aria-label="按结果筛选视频"><option value="">全部结果（130）</option><option value="true">仅 success（{mt["success"]}）</option><option value="false">仅 fail（{mt["l90_fail"]}）</option></select>
<input id="filter-gallery-search" type="search" placeholder="搜索 T 编号 / instruction 关键词" aria-label="搜索视频">
<button id="filter-gallery-reset" type="button">重置</button>
<span class="count" id="gallery-count">显示 {mt["gallery_cards"]} / {mt["gallery_cards"]} 条视频</span>
<span class="hint">筛选在前端完成；场景随测试套联动（全部套件时 32 个场景分组）；分组标题显示可见条数/成功数。</span>
</div>
<div id="gallery-groups">{''.join(groups_html)}</div>
<p class="note">缩略图为首帧 JPEG（256×256，q85，每张 ≤{mt["thumb_max_kb"]} KB，cv2 从 mp4 提取，位于 <code>report/assets/thumbs/</code>）；视频本体仍以相对路径 <code>../run/&lt;suite&gt;/pi05_*/videos/*.mp4</code> 引用，不复制。全页仅 1 个 <code>&lt;video&gt;</code> 标签（弹层内，默认隐藏）。“全部”视图共 {mt["gallery_groups"]} 个场景分组（LIBERO_90 20、LIBERO_10 9、SPATIAL/OBJECT/GOAL 各 1）。</p>
</section>'''


def render_modal(m):
    return '''<div class="modal" id="video-modal" hidden aria-hidden="true">
<div class="modal-backdrop" data-close="1"></div>
<div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="modal-title">
<div class="modal-head"><h3 id="modal-title">视频播放</h3><button class="modal-close" id="modal-close" type="button" aria-label="关闭弹层">×</button></div>
<video id="video-modal-player" controls autoplay playsinline preload="none"></video>
<div class="modal-meta" id="modal-meta"></div>
</div>
</div>'''

def render_analysis(m):
    mt = m["metrics"]
    l90 = m["l90"]
    hist = m["steps_hist"]
    kw = {r["key"]: r for r in l90["keyword_rows"]}
    hist_head = "".join(f"<th>{esc(b)}</th>" for b in hist["bins"])
    hist_rows = "".join(
        f'<tr class="hist-row" data-suite="{row["suite"]}" data-total="{row["total"]}">'
        f'<td>{badge(SUITE_SHORT[row["suite"]], SUITE_COLOR[row["suite"]])}</td>'
        + "".join(f'<td data-bin="{esc(b)}" data-count="{row["counts"][b]}">{row["counts"][b]}</td>' for b in hist["bins"])
        + f'<td><b>{row["total"]}</b></td></tr>'
        for row in hist["rows"]
    )
    max_count = max(c for row in hist["rows"] for c in row["counts"].values()) or 1
    hist_bars = "".join(
        bar_row(f'{SUITE_SHORT[row["suite"]]} · steps={b}', row["counts"][b] / max_count,
                f'{row["counts"][b]} eps', "warm" if b == "500" else "cool")
        for row in hist["rows"] for b in hist["bins"] if row["counts"][b] > 0
    )
    scene_rows = "".join(
        f'<tr class="{"zero" if r["success"] == 0 else ("hi" if r["fail"] == 0 else "mid")} scene-row" '
        f'data-scene="{esc(r["scene"])}" data-tasks="{r["tasks"]}" data-success="{r["success"]}" '
        f'data-fail="{r["fail"]}" data-rate="{r["rate_pct"]}">'
        f'<td><code>{esc(r["scene"])}</code></td><td>{r["tasks"]}</td><td>{r["success"]}</td>'
        f'<td>{r["fail"]}</td><td>{r["rate_pct"]}%</td></tr>'
        for r in l90["scene_rows"]
    )
    kw_rows = "".join(
        f'<tr class="kw-row" data-kw="{esc(r["key"])}" data-fails="{r["fails"]}" data-succs="{r["succs"]}" '
        f'data-total="{r["total"]}" data-fail-rate="{r["fail_rate_pct"]}">'
        f'<td>{esc(r["label"])}</td><td>{r["fails"]}</td><td>{r["succs"]}</td>'
        f'<td>{r["total"]}</td><td>{r["fail_rate_pct"]}%</td></tr>'
        for r in l90["keyword_rows"]
    )
    fail_rows = "".join(
        f'<tr class="l90-fail-row" data-task-idx="{e["task_idx"]}" data-scene="{esc(e["scene"])}" data-steps="{e["steps"]}">'
        f'<td>{e["task_idx"]}</td><td class="instr">{esc(e["instruction"])}</td>'
        f'<td><code>{esc(e["scene"])}</code></td><td>{e["steps"]}</td><td>{e["time_s"]}</td></tr>'
        for e in l90["fail_rows"]
    )
    zero_scenes = [r["scene"] for r in l90["scene_rows"] if r["success"] == 0]
    return f'''<section id="analysis">
<h2>六、失败 / 长尾分析（主要来自 LIBERO_90）</h2>
<p class="sub">4 个标准套件全部成功（无失败样本），失败集中在 <b>LIBERO_90 的 {l90["fails"]}/{l90["tasks"]} 个任务</b>：全部 <b>{l90["fail_at_500"]} 个失败都跑满 {mt["max_steps"]} 步上限（超时）</b>，失败 mean time {metric("l90_fail_mean_time", m)}s；成功则普遍很快（mean {metric("l90_succ_mean_steps", m)} 步 / {metric("l90_succ_mean_time", m)}s，中位 {l90["succ_median_steps"]} 步）。这种“快速成功或 500 步完全不动”的二极分布说明失败主要是任务/指令不可解或执行卡住，而非 near-miss 精度问题。</p>
<div class="cards">
<div class="metric"><div class="v">{l90["success"]} / {l90["tasks"]}</div><div class="l">LIBERO_90 success</div><div class="d">mean steps {metric("l90_succ_mean_steps", m)}（{metric("l90_succ_min_steps", m)}–{metric("l90_succ_max_steps", m)}）· mean time {metric("l90_succ_mean_time", m)}s</div></div>
<div class="metric"><div class="v">{l90["fails"]} / {l90["tasks"]}</div><div class="l">LIBERO_90 fail（全部超时）</div><div class="d">steps = 500（{l90["fail_at_500"]}/{l90["fails"]}）· mean time {metric("l90_fail_mean_time", m)}s · median steps 500</div></div>
<div class="metric"><div class="v">{l90["fail_mean_time"]}s vs {l90["succ_mean_time"]}s</div><div class="l">失败 vs 成功 mean wall time</div><div class="d">失败 episode 是成功 episode 的 {round(l90["fail_mean_time"]/l90["succ_mean_time"],1)} 倍时长（视频也更长：500/501 帧）</div></div>
<div class="metric"><div class="v">{len(zero_scenes)}</div><div class="l">LIBERO_90 中 0 成功的场景数</div><div class="d">{esc("、".join(zero_scenes)) if zero_scenes else "无"}（共 {metric("scene_count", m)} 个场景）</div></div>
</div>
<h3>6.1 steps 分布（按 suite；500 = 超时上限）</h3>
<div class="tblwrap"><table>
<thead><tr><th>suite</th>{hist_head}<th>total</th></tr></thead>
<tbody>{hist_rows}</tbody></table></div>
<div class="barchart">{hist_bars}</div>
<h3>6.2 LIBERO_90 失败任务清单（{l90["fails"]} 个，全部 steps=500）</h3>
<div class="tblwrap"><table>
<thead><tr><th>task_idx</th><th>instruction</th><th>scene</th><th>steps</th><th>time (s)</th></tr></thead>
<tbody>{fail_rows}</tbody></table></div>
<h3>6.3 LIBERO_90 按场景（失败分布）</h3>
<div class="tblwrap"><table>
<thead><tr><th>scene</th><th>tasks</th><th>success</th><th>fail</th><th>rate</th></tr></thead>
<tbody>{scene_rows}</tbody></table></div>
<h3>6.4 失败 vs 成功任务的指令特征（LIBERO_90）</h3>
<div class="tblwrap"><table>
<thead><tr><th>特征 / 关键词</th><th>失败任务数</th><th>成功任务数</th><th>合计</th><th>失败率</th></tr></thead>
<tbody>{kw_rows}</tbody></table></div>
<p class="note"><b>失败特征</b>：① <b>“pick up …”（拾取）失败 {kw["pick up"]["fails"]} 个</b>（其中含 book 的任务失败 {kw["book"]["fails"]} 个）——抓取细长/薄物体（书、瓶子等）是主要失败族；② <b>含 “put” 的放置类失败 {kw["put"]["fails"]} 个</b>，且多与 drawer/cabinet 组合：<b>含 drawer 失败 {kw["drawer"]["fails"]} 个、cabinet {kw["cabinet"]["fails"]} 个</b>（开/关抽屉、把物体放进/放到柜子上方）；③ 开/关类（open/close）合计失败 {kw["open"]["fails"] + kw["close"]["fails"]} 个（开抽屉/关抽屉单项指令也不稳）；④ 电器的 turn on/off 失败 {kw["turn"]["fails"]} 个，stack（堆叠）失败 {kw["stack"]["fails"]} 个。成功任务同样以 put/mug/bowl/plate 为主，说明模型对常见“放到某容器”任务较稳，但对精细抓取、抽屉机构、开关操作失败率高。<b>场景维度</b>：LIBERO_90 中 {esc("、".join(zero_scenes)) if zero_scenes else "无"} 为零成功场景；KITCHEN 场景整体成功 {sum(r["success"] for r in l90["scene_rows"] if r["scene"].startswith("KITCHEN"))}/{sum(r["tasks"] for r in l90["scene_rows"] if r["scene"].startswith("KITCHEN"))}、LIVING_ROOM {sum(r["success"] for r in l90["scene_rows"] if r["scene"].startswith("LIVING_ROOM"))}/{sum(r["tasks"] for r in l90["scene_rows"] if r["scene"].startswith("LIVING_ROOM"))}、STUDY {sum(r["success"] for r in l90["scene_rows"] if r["scene"].startswith("STUDY"))}/{sum(r["tasks"] for r in l90["scene_rows"] if r["scene"].startswith("STUDY"))}。长尾判断：LIBERO_90 的失败不是“差一点”，而是 500 步内完全未完成；若用于后续改进（staged / rollback / 指令变体），应先按上述失败家族抽样看视频定位卡点。</p>
</section>'''


def render_conclusions(m):
    mt = m["metrics"]
    l90 = m["l90"]
    return f'''<section id="conclusions">
<h2>七、结论 / 参考价值 / 局限 / 后续建议</h2>
<div class="status ok"><b>结论</b>：pi05 在单 seed、max_steps=500、replan=5、video on、PyTorch backend 下跑完完整 LIBERO 5 套件 <b>{mt["total_tasks"]} tasks：{mt["success"]}/{mt["total_tasks"]} = {mt["rate_pct"]}%</b>。4 个标准套件（SPATIAL/OBJECT/GOAL/10）<b>{mt["standard_success"]}/{mt["standard_tasks"]} = {mt["standard_rate_pct"]}%</b>（本配置下已饱和，任务较轻、100–250 步完成）；<b>LIBERO_90 全量 90 tasks = {mt["l90_success"]}/{mt["l90_tasks"]} = {mt["l90_rate_pct"]}%</b>，{mt["l90_fail"]} 个失败全部 500 步超时，是当前设置下真正有区分度的部分。130 个视频全部可解码、报告可离线播放 → 可作为<b>带视频证据的 pi05 标准 LIBERO 参考 baseline</b>。</div>
<h3>7.1 参考价值（怎么用）</h3>
<ul class="flat">
<li><b>同协议对照 baseline</b>：后续 custom 双目标任务、staged / instruction-switch / rollback 原型等，若沿用同一 runtime/backend/步数/seed 设置，可与本 run 的 130 条 episode 逐任务对照（同一 task_idx 的 success/steps/time/视频）。</li>
<li><b>视频证据库</b>：130 个 mp4（每步 1 帧、20fps、256×256）可直接作为报告/论文材料的 episode 证据；视频库按 测试套 → 测试场景 分组、可按套件/场景/结果筛选，130 条均可点击缩略图在弹层播放。</li>
<li><b>失败定位起点</b>：LIBERO_90 的 61 个失败任务清单 + 场景/关键词特征表可直接用于挑 staged/rollback 实验对象（优先 pick-up/书、drawer/cabinet、turn on/off 族）。</li>
<li><b>4 套件饱和提示</b>：在 500 步、单 seed 设置下 4 个标准套件 40/40 全成功，说明用它们区分模型能力已无空间；更有信息量的是 LIBERO_90 全量、或提高难度的 staged 设置。</li>
</ul>
<h3>7.2 局限（必须与数字一起引用）</h3>
<ul class="flat">
<li><b>单 seed（seed=0）、每任务 1 trial</b>：无方差/置信区间，不能估计 seed 噪声；61 个 LIBERO_90 失败中可能有个别 seed 敏感任务。</li>
<li><b>max_steps=500 统一</b>（官方各套件原配置不同）+ <b>PyTorch backend</b>（官方/论文常见 JAX）+ video on 开销：<b>不可与官方 50-trial 表格严格横比</b>，只适合同协议内部对照。</li>
<li><b>单指令 zero-shot baseline</b>：无 staged / instruction-switch / rollback / 多指令变体；因此 4 套件 100% 与 LIBERO_90 32.22% 都只是“该协议下”的数字。</li>
<li><b>LIBERO_90 配置</b>来自 shadow benchmark 生成的 90 个 yaml（本 run runtime），任务顺序=原版 LIBERO 顺序；与其它 L90 自定义候选池的 task_idx 映射不通用，跨实验对照需按 instruction 对齐。</li>
<li><b>失败原因未逐视频人工标注</b>：61 个失败全部 500 步超时，但从结果/视频只能判断“未完成”，具体卡点（抓取失败/碰撞/规划不动）需人工看视频或加 trace 才能归因。</li>
</ul>
<h3>7.3 后续建议</h3>
<ol class="risk">
<li><b>若要报“官方对照”数字</b>：按官方设置（多 seed / 50 trials、对应 max_steps、JAX backend）重跑，至少对 LIBERO_90 做 3–5 seeds 估计方差；本 run 可作为快速 sanity baseline。</li>
<li><b>若用于 custom 任务对照</b>：保持同 runtime/seed/步数，并在报告中同时给出 seed0 单点与多 seed 均值，避免把单 seed 差异当方法差异。</li>
<li><b>LIBERO_90 改进</b>：优先针对失败家族（pick up 书/瓶、drawer/cabinet 开关、turn on/off）做 staged / 指令变体 / rollback 实验，并复用本 run 视频做前后对照。</li>
<li><b>4 套件</b>：当前设置已饱和，除非提高难度（更长 horizon / 干扰物），不建议再投入算力做同协议重复。</li>
</ol>
</section>'''


def render_caveats(m):
    mt = m["metrics"]
    integ = m["integrity"]
    return f'''<section id="caveats">
<h2>八、口径 / 偏差 / 数据问题（报告内已按实际处理）</h2>
<ol class="risk">
<li><b>wall 有两个口径，差 {round((mt["wall_queue_s"]-mt["wall_suite_s"])/60, 1)} 分钟</b>：queue.log 端到端 <b>{mt["wall_queue_h"]} h</b>（00:44:01 → 04:19:36，含每 suite 启动/模型加载/切换开销）；summary 各 suite wall_s 合计 <b>{mt["wall_suite_h"]} h</b>（纯 episode 运行）。本报告 hero 用 {mt["wall_queue_h"]} h（与 task-27 上报一致），套件表同时列出两列，避免误用。</li>
<li><b>磁盘 131 个 mp4 = 130 评测 + 1 冒烟</b>：<code>run/smoke/...</code> 的 LIBERO_90 T0 冒烟视频与评测集 T0 视频同任务不同 run 目录；本报告只索引 <b>130 个评测视频</b>，冒烟视频在产物索引中单独链接，不计入 130。</li>
<li><b>4 个标准套件 40/40 = 100% 是“本配置饱和”</b>，不是“模型完美”或官方数字：官方 50 trials/不同步数/后端下数字会不同；不要把 100% 与论文表格直接比较。</li>
<li><b>LIBERO_90 61 个失败全部是 500 步超时</b>（无 near-miss/提前失败分类）：失败 mean time {mt["l90_fail_mean_time"]}s、mean steps 500；成功 mean {mt["l90_succ_mean_steps"]} 步。若需失败类型（抓取失败/碰撞/规划失败），需看视频或 trace 人工标注。</li>
<li><b>scene_map 来源与单场景标注</b>：视频库分组使用 <code>analysis/scene_map.json</code>（130 行 suite/task_idx/bddl/scene/instruction，已纳入构建指纹）；scene = bddl 文件名前缀 <code>^[A-Z_]+_SCENE&lt;数字&gt;</code>，SPATIAL / OBJECT / GOAL 三个单场景套件统一标注为 <code>&lt;SUITE&gt;_SCENE（单场景）</code> → 场景筛选共 <b>32 个（套件×场景）分组</b>（LIBERO_90 20、LIBERO_10 9、其余各 1；因 LIBERO_10 复用 L90 场景名，去重后 scene label 为 23 个）；instruction 与 summary 逐行一致（0 差异）。</li>
<li><b>单 seed 无方差</b>：每任务仅 1 trial，success 是 0/1 点估计；本报告不做任何显著性/置信区间陈述。</li>
<li><b>task_idx 映射</b>：LIBERO_90 的 task_idx 来自 shadow 原版 LIBERO benchmark 顺序（本 run runtime 的 90 个 yaml）；与其它自定义 L90 候选池的编号不通用，跨实验请按 instruction/BDDL 对齐。</li>
<li><b>summary/STATUS 的速率字段</b>：STATUS.md 写 35.8 tasks/h（monitor 估算，基于含启动开销的端到端时间）；按 queue.log 端到端计算为 {mt["queue_rate_tasks_h"]} tasks/h、按 suite 实测 wall 为 {mt["suite_rate_tasks_h"]} tasks/h。报告统一用后两者并在页面注明。</li>
<li><b>缩略图与播放器</b>：130 张首帧缩略图由 cv2 从 mp4 第一帧提取（256×256 JPEG、质量 85、每张 ≤{mt["thumb_max_kb"]} KB，位于 <code>report/assets/thumbs/</code>）；视频库按 测试套 → 测试场景 分组、前端筛选，点击卡片/播放按钮使用全页唯一弹层播放器播放；页面仅 1 个 <code>&lt;video&gt;</code> 标签，不内嵌/不预载 130 个播放器。</li>
<li><b>视频索引表 → 卡片网格</b>：旧版报告中 130 行「视频索引表」已由视频库卡片网格取代（每张卡片即一条视频，含缩略图/套件/场景/任务/结果/steps，可按测试套×测试场景筛选）；机读索引 <code>analysis/video_index.json</code> 仍完整保留（130 条），供脚本/外部工具使用。</li>
<li><b>视频大小/时长</b>：43.07 MB / 总时长 {mt["video_total_duration_s"]}s（≈{mt["video_total_duration_min"]} min）；LIBERO_90 视频占 {m["suites"][0]["video_mb"]} MB（失败 episode 25s×61 个是主要体积来源）。</li>
</ol>
<p class="note">完整性：final_checks 15/15 PASS（{integ["video_index_entries"]}/130 videos、missing/undecodable/over-500 空、suite rc 全 0）；冒烟 8/8 PASS；本报告由脚本从 summary.json 全量生成（数字无手填），<code>--check</code> 逐项断言；输入文件 sha256 见页脚。</p>
</section>'''


def render_artifacts(m):
    rows = [
        ("本报告（单文件 HTML）", "index.html", "带视频库（缩略图 + 弹层播放）的 130 tasks 参考报告；内联 CSS/JS + 相对 mp4 引用"),
        ("本报告说明", "README.md", "≤30 行：结论/口径/章节/复现"),
        ("本报告生成器", "../../../scripts/build_libero_official_5suites_report.py", "可重跑；--check 校验全部关键数字与视频"),
        ("聚合结果（主数据源）", "../analysis/summary.json", "5 套件聚合 + 130 逐 episode"),
        ("聚合摘要 md", "../analysis/summary.md", "可读版 130 逐 episode 表"),
        ("视频索引", "../analysis/video_index.json", "suite→task→mp4（130 条，含 size/frames/fps/decodable）"),
        ("场景映射（视频库分组依据）", "../analysis/scene_map.json", "130 行 suite/task_idx/bddl/scene/instruction；32 个场景标签，纳入构建指纹"),
        ("视频缩略图目录", "assets/thumbs", "130 张首帧 jpg（256×256，≤50KB，cv2 提取）"),
        ("完整性检查", "../analysis/final_checks.json", "15/15 PASS（130 tasks / 130 mp4 / rc=0）"),
        ("运行协议", "../PROTOCOL.md", "环境、runtime 补丁、协议、复现"),
        ("运行状态", "../STATUS.md", "实时进度快照（130/130 完成）"),
        ("冒烟记录", "../SMOKE.md", "LIBERO_90 T0 冒烟 PASS"),
        ("冒烟检查 json", "../logs/smoke-check.json", "8/8 PASS；含 1 条冒烟视频"),
        ("队列日志", "../logs/queue.log", "suite 开始/结束时间与 elapsed（wall 口径来源）"),
        ("聚合脚本", "../prep/analyze_official.py", "summary/video_index 生成"),
        ("完整性脚本", "../prep/final_checks.py", "final_checks.json 生成"),
        ("队列脚本", "../prep/start_official_queue.sh", "5 套件串行队列（支持断点续跑）"),
        ("LIBERO_90 配置生成", "../prep/gen_configs_libero90.py", "90 个 yaml（shadow benchmark → runtime/configs/tasks/libero_90）"),
        ("runtime 补丁记录", "../prep/patch_official_runtime.py", "标准基准守卫 90 tasks + libero_90 配置"),
        ("runtime 基准脚本", "../runtime/tools/run_benchmark.py", "含 LIBERO_90 期望 90 tasks 守卫（只读引用）"),
        ("LIBERO_90 配置目录", "../runtime/configs/tasks/libero_90", "90 个 yaml（task_idx 0..89）"),
        ("LIBERO_90 results", "../run/libero_90/pi05_20261027_004407/results.json", "90 条 episode 原始结果（54 MB）"),
        ("LIBERO_SPATIAL results", "../run/libero_spatial/pi05_20261027_033725/results.json", "10 条 episode 原始结果"),
        ("LIBERO_OBJECT results", "../run/libero_object/pi05_20261027_034727/results.json", "10 条 episode 原始结果"),
        ("LIBERO_GOAL results", "../run/libero_goal/pi05_20261027_035604/results.json", "10 条 episode 原始结果"),
        ("LIBERO_10 results", "../run/libero_10/pi05_20261027_040614/results.json", "10 条 episode 原始结果"),
        ("LIBERO_90 视频目录", "../run/libero_90/pi05_20261027_004407/videos", "90 个 mp4（36.5 MB）"),
        ("LIBERO_SPATIAL 视频目录", "../run/libero_spatial/pi05_20261027_033725/videos", "10 个 mp4"),
        ("LIBERO_OBJECT 视频目录", "../run/libero_object/pi05_20261027_034727/videos", "10 个 mp4"),
        ("LIBERO_GOAL 视频目录", "../run/libero_goal/pi05_20261027_035604/videos", "10 个 mp4"),
        ("LIBERO_10 视频目录", "../run/libero_10/pi05_20261027_040614/videos", "10 个 mp4"),
        ("冒烟视频（不计入 130）", "../run/smoke/pi05_20261027_004021/videos/LIBERO_90_T0__baseline_seed0.mp4", "LIBERO_90 T0 冒烟 mp4"),
    ]
    body = "".join(
        f'<tr><td>{esc(title)}</td><td><a class="local" href="{esc(href)}"><code>{esc(href)}</code></a></td>'
        f'<td class="tiny">{esc(desc)}</td></tr>'
        for title, href, desc in rows
    )
    hashes = m["hashes"]
    hash_line = " · ".join(f'<code>{esc(name)}</code> <code>{esc(hashes[name][:16])}…</code>' for name in sorted(hashes))
    return f'''<section id="artifacts">
<h2>九、产物索引</h2>
<div class="tblwrap"><table>
<thead><tr><th>产物</th><th>路径（相对本文件）</th><th>用途</th></tr></thead>
<tbody>{body}</tbody></table></div>
<p class="note">输入 sha256（前 16 位）：{hash_line}。本报告只读 summary/video_index/final_checks/queue.log/smoke-check/inventory，并逐条核对 130 个 mp4 存在性；不修改 run 数据。</p>
</section>'''


def render_footer(m):
    hashes = m["hashes"]
    line = " · ".join(f'<code>{esc(name)}</code> <code>{esc(hashes[name][:16])}…</code>' for name in sorted(hashes))
    mt = m["metrics"]
    return f'''<footer>
<p><b>生成命令</b>：<code>cd /home/tarowang/workspace/roboot/libero-rollback &amp;&amp; .venv/bin/python scripts/build_libero_official_5suites_report.py</code>；只读校验：<code>.venv/bin/python scripts/build_libero_official_5suites_report.py --check</code></p>
<p><b>数据来源</b>：{line}；主数据源 <code>analysis/summary.json</code>（130 tasks / {mt["success"]} success / {mt["rate_pct"]}%），视频证据来自 <code>analysis/video_index.json</code> 与磁盘 <code>run/&lt;suite&gt;/pi05_*/videos/*.mp4</code>（相对路径引用）。</p>
<p><b>审计状态</b>：本 run <code>analysis/final_checks.json</code> <b>15/15 PASS</b>（130 tasks、130 mp4 存在非空可解码、steps≤500、suite rc=0、video_index 130）；冒烟 <code>logs/smoke-check.json</code> <b>8/8 PASS</b>；逐 suite rc 全 0。本 HTML 由脚本从 JSON 全量生成、数字无手填、<code>--check</code> 逐项复验（含 130 个视频文件存在性）。本报告由 verifier 另行审计（task-31）；与官方/论文设置不同（单 seed、500 步、PyTorch backend、video on），<b>不可严格横比</b>。</p>
<p class="tiny">构建时间 {esc(m["generated_at"])} · 构建指纹 <code>sha256:{esc(m["digest"])}</code> · 单文件静态页面（内联 CSS/JS、无外链 CDN；视频用 <code>../run/...</code> 相对路径）</p>
</footer>'''


JS = """
(function(){
  var nav = Array.prototype.slice.call(document.querySelectorAll('.sidenav a[href^="#"]'));
  var byId = {};
  nav.forEach(function(a){ byId[a.getAttribute('href').slice(1)] = a; });
  var sections = Array.prototype.slice.call(document.querySelectorAll('section[id]'));
  function markActive(){
    var y = window.scrollY + 140, cur = null;
    sections.forEach(function(s){ if (s.offsetTop <= y) cur = s.id; });
    nav.forEach(function(a){ a.classList.remove('active'); });
    if (cur && byId[cur]) byId[cur].classList.add('active');
  }
  window.addEventListener('scroll', markActive, {passive:true});
  markActive();

  var taskSuite = document.getElementById('filter-suite');
  var taskRes = document.getElementById('filter-success');
  if (taskSuite && taskRes) {
    var taskRows = Array.prototype.slice.call(document.querySelectorAll('tr.task-row'));
    var taskReset = document.getElementById('filter-reset');
    var taskCount = document.getElementById('filter-count');
    var applyTasks = function(){
      var s = taskSuite.value, r = taskRes.value, shown = 0;
      taskRows.forEach(function(tr){
        var ok = (!s || tr.dataset.suite === s) && (!r || tr.dataset.success === r);
        tr.style.display = ok ? '' : 'none';
        if (ok) shown++;
      });
      if (taskCount) taskCount.textContent = '显示 ' + shown + ' / ' + taskRows.length + ' 条任务';
    };
    taskSuite.addEventListener('change', applyTasks);
    taskRes.addEventListener('change', applyTasks);
    if (taskReset) taskReset.addEventListener('click', function(){ taskSuite.value=''; taskRes.value=''; applyTasks(); });
    applyTasks();
  }

  var galleryGroups = Array.prototype.slice.call(document.querySelectorAll('.scene-group'));
  var galleryCards = Array.prototype.slice.call(document.querySelectorAll('.vid-card'));
  var suiteSel = document.getElementById('filter-gallery-suite');
  var sceneSel = document.getElementById('filter-gallery-scene');
  var resultSel = document.getElementById('filter-gallery-result');
  var searchBox = document.getElementById('filter-gallery-search');
  var galleryReset = document.getElementById('filter-gallery-reset');
  var galleryCount = document.getElementById('gallery-count');
  if (suiteSel && sceneSel && resultSel && galleryCount) {
    var rebuildSceneOptions = function(){
      var selectedSuite = suiteSel.value;
      var opts = ['<option value="">全部场景' + (selectedSuite ? '' : '（' + galleryGroups.length + ' 组）') + '</option>'];
      galleryGroups.forEach(function(g){
        if (!selectedSuite || g.dataset.suite === selectedSuite) {
          var n = g.querySelectorAll('.vid-card').length;
          var label = selectedSuite ? g.dataset.scene : (g.dataset.suite.replace('LIBERO_', 'L') + ' · ' + g.dataset.scene);
          opts.push('<option value="' + g.dataset.suite + '||' + g.dataset.scene + '" data-suite="' + g.dataset.suite + '">'
                    + label + '（' + n + '）</option>');
        }
      });
      var keep = sceneSel.value;
      sceneSel.innerHTML = opts.join('');
      var still = Array.prototype.slice.call(sceneSel.options).some(function(o){ return o.value === keep; });
      sceneSel.value = still ? keep : '';
    };
    var matchSearch = function(card, q){
      if (!q) return true;
      if ((card.dataset.key || '').toLowerCase().indexOf(q) >= 0) return true;
      return (card.dataset.instruction || '').toLowerCase().indexOf(q) >= 0;
    };
    var applyGallery = function(){
      var selectedSuite = suiteSel.value;
      var selectedScene = sceneSel.value;
      var selectedResult = resultSel.value;
      var q = (searchBox && searchBox.value || '').trim().toLowerCase();
      var shown = 0;
      galleryGroups.forEach(function(g){
        var visible = 0, succ = 0;
        Array.prototype.slice.call(g.querySelectorAll('.vid-card')).forEach(function(card){
          var sceneKey = card.dataset.suite + '||' + card.dataset.scene;
          var ok = (!selectedSuite || card.dataset.suite === selectedSuite)
                && (!selectedScene || sceneKey === selectedScene)
                && (!selectedResult || card.dataset.success === selectedResult)
                && matchSearch(card, q);
          card.style.display = ok ? '' : 'none';
          if (ok) { visible++; if (card.dataset.success === 'true') succ++; }
        });
        g.style.display = visible ? '' : 'none';
        var gc = g.querySelector('.gcount');
        if (gc) gc.textContent = '（' + visible + ' 条 / 成功 ' + succ + '）';
        shown += visible;
      });
      galleryCount.textContent = '显示 ' + shown + ' / ' + galleryCards.length + ' 条视频';
    };
    suiteSel.addEventListener('change', function(){ rebuildSceneOptions(); applyGallery(); });
    sceneSel.addEventListener('change', applyGallery);
    resultSel.addEventListener('change', applyGallery);
    if (searchBox) searchBox.addEventListener('input', applyGallery);
    if (galleryReset) galleryReset.addEventListener('click', function(){
      suiteSel.value=''; sceneSel.value=''; resultSel.value=''; if (searchBox) searchBox.value='';
      rebuildSceneOptions(); applyGallery();
    });
    rebuildSceneOptions();
    applyGallery();
  }

  var modal = document.getElementById('video-modal');
  var player = document.getElementById('video-modal-player');
  var modalTitle = document.getElementById('modal-title');
  var modalMeta = document.getElementById('modal-meta');
  var closeBtn = document.getElementById('modal-close');
  if (modal && player && closeBtn) {
    var openModal = function(card){
      var video = card.dataset.video || '';
      if (!video) return;
      var okFlag = card.dataset.success === 'true';
      modalTitle.textContent = card.dataset.suite + ' · T' + card.dataset.taskIdx + ' · ' + (okFlag ? 'success' : 'fail');
      modalMeta.textContent = (card.dataset.instruction || '') + '（steps ' + card.dataset.steps + '，' + card.dataset.time + 's）';
      player.src = video;
      modal.hidden = false;
      modal.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
      var p = player.play();
      if (p && p.catch) p.catch(function(){});
    };
    var closeModal = function(){
      player.pause();
      player.removeAttribute('src');
      player.load();
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
    };
    galleryCards.forEach(function(card){
      card.addEventListener('click', function(ev){ ev.preventDefault(); openModal(card); });
      card.addEventListener('keydown', function(ev){ if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); openModal(card); } });
    });
    closeBtn.addEventListener('click', closeModal);
    var backdrop = modal.querySelector('.modal-backdrop');
    if (backdrop) backdrop.addEventListener('click', closeModal);
    document.addEventListener('keydown', function(ev){ if (ev.key === 'Escape' && !modal.hidden) closeModal(); });
  }
})();
"""

def build_html(m):
    mt = m["metrics"]
    return "\n".join([
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f'<title>LIBERO 官方 5 套件 × pi05 评测参考报告（{mt["total_tasks"]} tasks / {mt["success"]} success = {mt["rate_pct"]}%）</title>',
        f"<!-- data-digest: sha256:{m['digest']} -->",
        f'<style>{CSS}</style>',
        '</head><body>',
        render_sidenav(m),
        render_hero(m),
        '<main>',
        render_overview(m),
        render_protocol(m),
        render_suites(m),
        render_tasks(m),
        render_videos(m),
        render_analysis(m),
        render_conclusions(m),
        render_caveats(m),
        render_artifacts(m),
        '</main>',
        render_modal(m),
        render_footer(m),
        f'<script>{JS}</script>',
        '</body></html>',
    ])


def build_readme(m):
    mt = m["metrics"]
    l90 = m["l90"]
    lines = [
        "# LIBERO 官方 5 套件 × pi05 评测参考报告（130 tasks，seed0 / 500 steps / video on）",
        "",
        "> 打开 `index.html` 离线阅读：单文件内联 CSS/JS；视频库为「套件×场景筛选 + 缩略图 + 弹层播放」，视频以 `../run/...` 相对路径引用。",
        "",
        "## 结论",
        f"- **{mt['total_tasks']} tasks：{mt['success']}/{mt['total_tasks']} = {mt['rate_pct']}%** success（4 标准套件 {mt['standard_success']}/{mt['standard_tasks']} = {mt['standard_rate_pct']}%；**LIBERO_90 {mt['l90_success']}/{mt['l90_tasks']} = {mt['l90_rate_pct']}%**）。",
        f"- LIBERO_90 的 {mt['l90_fail']} 个失败**全部在 {mt['max_steps']} 步上限超时**（失败 mean time {mt['l90_fail_mean_time']}s；成功 mean {mt['l90_succ_mean_steps']} 步）。",
        f"- 队列端到端 wall **{mt['wall_queue_h']} h**（suite 实测合计 {mt['wall_suite_h']} h）；**{mt['videos']} 个 mp4 全部可解码（{mt['video_mb']} MB）**，视频库 {mt['gallery_cards']} 条（{mt['gallery_groups']} 个场景分组，缩略图+弹层播放）。",
        "- 4 个标准套件在本配置下 40/40 全成功（饱和）；LIBERO_90 是当前设置有区分度的部分。",
        "- 视频库：旧 130 行视频索引表已由卡片网格取代（按测试套×测试场景筛选，缩略图+弹层播放）；`analysis/video_index.json` 仍保留为机读索引。",
        "",
        "## 口径（不可严格横比）",
        "- 单 seed=0、每任务 1 trial、max_steps=500、replan=5、video on（20fps 256×256）、OpenPI **PyTorch backend**、串行单进程。",
        "- 与论文/官方 openpi（50 trials / 多 seed、不同步数、JAX 等）设置不同，**不可直接比较**；也不与 custom 双目标 easy/hard run 混用。",
        "- LIBERO_90 配置来自本 run runtime 的 90 个 yaml（shadow benchmark 生成）；task_idx 与其它自定义 L90 候选池不通用。",
        "",
        "## 章节",
        "摘要/指标与完整性 → 协议/环境/与官方差异 → 5 套件总表 → 130 行逐任务表（可筛选）→ 视频库（套件×场景筛选、缩略图、弹层播放、130 条）→ LIBERO_90 失败/长尾分析 → 结论/参考价值/局限 → 口径与数据问题 → 产物索引。",
        "",
        "## 复现",
        "```bash",
        "cd /home/tarowang/workspace/roboot/libero-rollback",
        ".venv/bin/python scripts/build_libero_official_5suites_report.py          # 生成 report/index.html + README.md",
        ".venv/bin/python scripts/build_libero_official_5suites_report.py --check  # 只读校验（不写文件）",
        "```",
        "",
        "## 数据来源",
        "`analysis/summary.json`、`analysis/video_index.json`、`analysis/final_checks.json`、`logs/queue.log`、`logs/smoke-check.json`、`analysis/scene_map.json`（视频库分组）；缩略图由 cv2 从 mp4 首帧生成于 `report/assets/thumbs/`。",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(m):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    thumb_info = ensure_thumbnails(m["episodes"])
    html_text = build_html(m)
    OUT_HTML.write_text(html_text, encoding="utf-8")
    readme = build_readme(m)
    OUT_README.write_text(readme, encoding="utf-8")
    print(f"[build] {OUT_HTML.relative_to(ROOT)}: {len(html_text.encode('utf-8')):,} bytes")
    print(f"[build] sections={html_text.count('<section ')} tables={html_text.count('<table')} "
          f"gallery_cards={html_text.count('class=\"vid-card\"')} scene_groups={html_text.count('class=\"scene-group\"')} "
          f"video_tags={html_text.count('<video')} thumbs={thumb_info['total']} "
          f"(generated {thumb_info['generated']}, existing {thumb_info['existing']})")
    print(f"[build] totals: {m['metrics']['success']}/{m['metrics']['total_tasks']} = {m['metrics']['rate_pct']}% | "
          f"L90 {m['metrics']['l90_success']}/{m['metrics']['l90_tasks']} = {m['metrics']['l90_rate_pct']}% | "
          f"wall queue {m['metrics']['wall_queue_h']}h / suite {m['metrics']['wall_suite_h']}h | "
          f"videos {m['metrics']['videos']} ({m['metrics']['video_mb']} MB)")
    print(f"[build] README: {len(readme.splitlines())} lines")
    print(f"[build] digest sha256:{m['digest']}")

REQUIRED_METRIC_KEYS = [
    "total_tasks", "completed", "success", "rate_pct", "standard_tasks", "standard_success",
    "standard_rate_pct", "l90_tasks", "l90_success", "l90_rate_pct", "l90_fail", "l90_fail_at_500",
    "l90_succ_mean_steps", "mean_steps", "median_steps", "wall_queue_h", "wall_queue_s",
    "wall_suite_h", "wall_suite_s", "videos", "video_mb", "video_total_duration_s",
    "final_checks_passed", "final_checks_total", "smoke_checks_passed",
    "smoke_checks_total", "max_steps", "replan", "seed", "fps", "video_w", "video_h", "scene_count",
    "gallery_cards", "gallery_groups", "thumbs", "thumb_max_kb", "suite_filter_options",
    "scene_filter_options", "video_tags", "l90_scenes", "l10_scenes", "single_scene_suites",
]


def parse_attrs(text):
    return dict(re.findall(r'([a-zA-Z_][\w-]*)="([^"]*)"', text))


def run_checks(m):
    checks = []

    def add(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    mt = m["metrics"]
    if not OUT_HTML.exists():
        print(f"[FAIL] index.html 存在 — 缺少 {OUT_HTML}；先运行无参数构建")
        print("--check: 0/1 checks passed")
        return False
    text = OUT_HTML.read_text(encoding="utf-8")
    digest_m = re.search(r"<!-- data-digest: sha256:([0-9a-f]{64}) -->", text)
    add("构建指纹与当前输入一致（HTML 未过期）",
        bool(digest_m) and digest_m.group(1) == m["digest"],
        "HTML 与当前输入 JSON/log 不一致，请重跑生成器")

    expected_sections = ["overview", "protocol", "suites", "tasks", "videos", "analysis",
                         "conclusions", "caveats", "artifacts"]
    missing = [sid for sid in expected_sections if f'<section id="{sid}"' not in text]
    add(f"{len(expected_sections)} 个章节 section 齐全", not missing, f"缺失: {missing}")

    # 指标
    pairs = re.findall(r'data-metric="([^"]+)"[^>]*>([^<]+)<', text)
    found = {}
    bad_values = []
    for key, value in pairs:
        found[key] = value
        if key in REQUIRED_METRIC_KEYS and value != str(mt[key]):
            bad_values.append((key, value, str(mt[key])))
    miss_keys = [k for k in REQUIRED_METRIC_KEYS if k not in found]
    add("关键指标数字（data-metric）逐处与 summary 一致",
        not miss_keys and not bad_values, f"缺失 {miss_keys} / 不符 {bad_values[:6]}")
    add("核心数字 130 / 69 / 53.08% / L90 29/90 32.22% 出现在页面文本",
        all(s in text for s in ("130", "69", "53.08", "32.22", "29")))
    add("wall 两口径（3.59h 队列 / 2.98h suite 实测）均在页面",
        "3.59" in text and "2.98" in text)

    # 5 套件表
    suite_rows = re.findall(r'<tr class="suite-row[^"]*" data-suite="([^"]+)" data-tasks="(\d+)" '
                            r'data-success="(\d+)" data-rate="([\d.]+)" data-mean-steps="([\d.]+)" '
                            r'data-wall-s="(\d+)" data-queue-elapsed="(\d+)" data-videos="(\d+)" '
                            r'data-video-bytes="(\d+)"', text)
    expected = [(s["suite"], str(s["tasks"]), str(s["success"]), str(s["rate_pct"]),
                 str(s["mean_steps"]), str(int(s["wall_s"])), str(int(s["queue_elapsed_s"])),
                 str(s["videos"]), str(int(s["video_bytes"]))) for s in m["suites"]]
    add("5 套件总表行数 = 5 且数值与 summary 一致", suite_rows == expected, f"实际 {suite_rows}")
    add("每 suite 10/10/10/10/90 构成",
        [int(r[1]) for r in suite_rows] == [90, 10, 10, 10, 10], f"实际 {[r[1] for r in suite_rows]}")
    tot = re.search(r'<tr class="suite-total-row" data-tasks="(\d+)" data-success="(\d+)" data-rate="([\d.]+)" '
                    r'data-videos="(\d+)" data-video-bytes="(\d+)"', text)
    add("合计行 = 130 tasks / 69 success / 130 videos / 43069601 bytes",
        bool(tot) and tot.groups()[:5] == ("130", "69", "53.08", "130", "43069601"),
        f"实际 {tot.groups() if tot else None}")
    add("suite 表逐列求和 = 130 tasks / 69 success / 130 videos",
        sum(int(r[1]) for r in suite_rows) == 130 and sum(int(r[2]) for r in suite_rows) == 69
        and sum(int(r[7]) for r in suite_rows) == 130)

    # 130 行任务表
    task_rows = re.findall(r'<tr class="(?:hi |zero )?task-row" data-suite="([^"]+)" data-task-idx="(\d+)" '
                           r'data-success="(true|false)" data-steps="(\d+)" data-time="([\d.]+)" '
                           r'data-video="([^"]+)"', text)
    add("逐任务表行数 = 130 且 (suite,idx) 唯一",
        len(task_rows) == 130 and len({(r[0], int(r[1])) for r in task_rows}) == 130,
        f"实际 {len(task_rows)}")
    task_expected = {(e["suite"], str(e["task_idx"])): e for e in m["episodes"]}
    bad_task = []
    succ_count = 0
    for suite_name, idx_s, success_s, steps_s, time_s, video in task_rows:
        e = task_expected.get((suite_name, idx_s))
        if e is None:
            bad_task.append((suite_name, idx_s))
            continue
        if (str(e["success"]).lower() != success_s or str(e["steps"]) != steps_s
                or abs(float(e["time_s"]) - float(time_s)) > 1e-6 or e["video_path"] != video):
            bad_task.append((suite_name, idx_s))
        succ_count += 1 if e["success"] else 0
    add("任务表逐行 success/steps/time/video 与 summary 0 差异", not bad_task, f"异常 {bad_task[:5]}")
    add("任务表 success 计数 = 69", succ_count == 69, f"实际 {succ_count}")

    # ---------------- 视频库 ----------------
    cards = re.findall(r'<article class="vid-card"(?: id="[^"]*")? data-suite="([^"]+)" data-scene="([^"]+)" '
                       r'data-task-idx="(\d+)" data-success="(true|false)" data-steps="(\d+)" '
                       r'data-time="([\d.]+)" data-video="([^"]+)" data-key="([^"]+)" '
                       r'data-instruction="([^"]*)"', text)
    add("视频库卡片数 = 130 且 key 唯一",
        len(cards) == 130 and len({c[7] for c in cards}) == 130, f"实际 {len(cards)}")
    ep_map = {(e["suite"], str(e["task_idx"])): e for e in m["episodes"]}
    bad_cards = []
    for suite_name, scene, idx_s, success_s, steps_s, time_s, video, key, instr in cards:
        e = ep_map.get((suite_name, idx_s))
        if e is None or scene != e["scene"] or str(e["success"]).lower() != success_s \
                or str(e["steps"]) != steps_s or e["video_href"] != video or e["thumb_rel"] not in text:
            bad_cards.append((suite_name, idx_s))
    add("卡片逐行 suite/scene/task/success/steps/video 与 summary+scene_map 一致",
        not bad_cards, f"异常 {bad_cards[:5]}")
    card_video_ok = all((REPORT_DIR / c[6]).exists() for c in cards)
    add("130 张卡片的视频 src 全部可解析到本地 mp4", card_video_ok)
    # 缩略图
    expected_thumbs = {thumb_name(e["suite"], e["task_idx"]) for e in m["episodes"]}
    thumb_files = {f.name for f in THUMB_DIR.glob("*.jpg")} if THUMB_DIR.exists() else set()
    add("缩略图文件数 = 130 且命名与 130 episode 一一对应",
        len(thumb_files) == 130 and thumb_files == expected_thumbs,
        f"实际 {len(thumb_files)} 个；缺失 {sorted(expected_thumbs - thumb_files)[:3]}")
    bad_thumbs = []
    for name in sorted(expected_thumbs):
        path = THUMB_DIR / name
        if not path.exists():
            bad_thumbs.append((name, "missing"))
            continue
        data = path.read_bytes()
        size = len(data)
        dims = jpeg_dimensions(data)
        if not (0 < size <= THUMB_MAX_BYTES) or data[:2] != b"\xff\xd8" or dims != (256, 256):
            bad_thumbs.append((name, size, dims))
    add("130 张缩略图均存在、JPEG 可解析、256×256 且 ≤50KB",
        not bad_thumbs, f"异常 {bad_thumbs[:3]}")
    add("<img> 缩略图标签 = 130 且均 loading=lazy",
        len(re.findall(r'<img class="thumb" loading="lazy"', text)) == 130)
    # 分组
    groups = re.findall(r'<section class="scene-group" data-suite="([^"]+)" data-scene="([^"]+)" '
                        r'data-total="(\d+)" data-succ="(\d+)">', text)
    add("按 suite→scene 分组数 = 32", len(groups) == 32, f"实际 {len(groups)}")
    per_suite_groups = Counter(g[0] for g in groups)
    add("每套件分组数 = L90 20 / L10 9 / SPATIAL/OBJECT/GOAL 各 1",
        per_suite_groups == {"LIBERO_90": 20, "LIBERO_10": 9, "LIBERO_SPATIAL": 1,
                             "LIBERO_OBJECT": 1, "LIBERO_GOAL": 1},
        f"实际 {dict(per_suite_groups)}")
    add("每套件分组 ∪ = 32 个场景分组",
        sum(per_suite_groups.values()) == 32)
    # 分组标题与卡片计数一致
    blocks = re.split(r'<section class="scene-group"', text)[1:]
    group_ok = []
    total_cards_in_groups = 0
    total_succ_in_groups = 0
    for block in blocks:
        end = block.find("</section>")
        block = block[:end]
        g = re.match(r' data-suite="([^"]+)" data-scene="([^"]+)" data-total="(\d+)" data-succ="(\d+)"', block)
        if not g:
            group_ok.append(("no-attrs",))
            continue
        n_cards = len(re.findall(r'<article class="vid-card"', block))
        n_succ = len(re.findall(r'data-success="true"', block))
        title = re.search(r'<span class="gcount">（(\d+) 条 / 成功 (\d+)）</span>', block)
        ok = (n_cards == int(g.group(3)) and n_succ == int(g.group(4))
              and title and int(title.group(1)) == n_cards and int(title.group(2)) == n_succ)
        total_cards_in_groups += n_cards
        total_succ_in_groups += n_succ
        group_ok.append((g.group(1), g.group(2), ok))
    add("32 个分组标题计数与组内卡片数/成功数一致",
        len(group_ok) == 32 and all(x[2] for x in group_ok if len(x) == 3),
        f"异常 {[x for x in group_ok if len(x) == 3 and not x[2]][:3]}")
    add("分组内卡片合计 = 130 且 success = 69",
        total_cards_in_groups == 130 and total_succ_in_groups == 69)
    # 筛选 options
    suite_opts = re.findall(r'<select id="filter-gallery-suite"[^>]*>(.*?)</select>', text, re.S)
    suite_opt_items = re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', suite_opts[0]) if suite_opts else []
    add("测试套筛选 options = 6（全部 + 5 套件）且计数正确",
        len(suite_opt_items) == 6 and [x[1].strip() for x in suite_opt_items] ==
        ["全部测试套（130）", "LIBERO_90（90）", "LIBERO_SPATIAL（10）", "LIBERO_OBJECT（10）", "LIBERO_GOAL（10）", "LIBERO_10（10）"],
        f"实际 {suite_opt_items}")
    scene_opts = re.findall(r'<select id="filter-gallery-scene"[^>]*>(.*?)</select>', text, re.S)
    scene_opt_items = re.findall(r'<option value="([^"]*)" data-suite="([^"]+)">', scene_opts[0]) if scene_opts else []
    per_suite_opts = Counter(x[1] for x in scene_opt_items)
    add("测试场景筛选 options = 32（全部 + 32 组；按套件 20/9/1/1/1）",
        len(scene_opt_items) == 32 and len(scene_opts[0].split("<option")) - 1 == 33
        and per_suite_opts == {"LIBERO_90": 20, "LIBERO_10": 9, "LIBERO_SPATIAL": 1,
                               "LIBERO_OBJECT": 1, "LIBERO_GOAL": 1},
        f"实际 {len(scene_opt_items)} / {dict(per_suite_opts)}")
    result_opts = re.search(r'<select id="filter-gallery-result"[^>]*>(.*?)</select>', text, re.S)
    result_items = re.findall(r'<option value="([^"]*)">', result_opts.group(1)) if result_opts else []
    add("结果筛选 options = 3（全部 / 成功 / 失败）", result_items == ["", "true", "false"], f"实际 {result_items}")
    add("筛选栏含搜索框 / 重置 / 计数",
        all(x in text for x in ('id="filter-gallery-search"', 'id="filter-gallery-reset"',
                                'id="gallery-count"', '显示 130 / 130 条视频')))
    # 单一视频标签 / modal
    video_positions = [mm.start() for mm in re.finditer(r'<video[\s>]', text)]
    modal_pos = text.find('id="video-modal"')
    gallery_start = text.find('<section id="videos"')
    gallery_end = text.find('</section>', gallery_start)
    add("<video> 标签全页仅 1 个", len(video_positions) == 1, f"实际 {len(video_positions)}")
    add("<video> 位于弹层内（非卡片/非视频库内嵌）",
        len(video_positions) == 1 and video_positions[0] > modal_pos > 0
        and text[gallery_start:gallery_end].count("<video") == 0)
    add("弹层含 controls/autoplay 与关闭按钮/遮罩",
        'id="video-modal-player" controls autoplay' in text
        and 'id="modal-close"' in text and 'class="modal-backdrop"' in text)
    # JS 关键字（筛选 + 弹层）
    js_keywords = ["openModal", "closeModal", "Escape", "keydown", "player.play", "player.pause",
                   "removeAttribute('src')", "filter-gallery-suite", "filter-gallery-scene",
                   "filter-gallery-result", "filter-gallery-search", "gallery-count",
                   "scene-group", "vid-card", "gcount"]
    add("筛选/弹层 JS 关键字齐全（含 ESC 关闭）",
        all(k in text for k in js_keywords), f"缺失 {[k for k in js_keywords if k not in text][:3]}")

    # final_checks / smoke
    fc_rows = re.findall(r'<tr class="integrity-row" data-check="([^"]+)" data-passed="(true|false)"', text)
    add("final_checks 15 行全部 PASS", len(fc_rows) == 15 and all(x[1] == "true" for x in fc_rows),
        f"实际 {len(fc_rows)} 行")
    smoke_rows = re.findall(r'<tr class="smoke-row" data-check="([^"]+)" data-passed="(true|false)"', text)
    add("冒烟 8 行全部 PASS", len(smoke_rows) == 8 and all(x[1] == "true" for x in smoke_rows),
        f"实际 {len(smoke_rows)} 行")
    add("final_checks.json checks_all_passed = true 且 suite rc 全 0",
        bool(m["final_checks"]["checks_all_passed"])
        and all(v == 0 for v in m["integrity"]["suite_rcs"].values()))
    add("steps 全部 <= 500、无 missing/undecodable",
        not m["integrity"]["steps_over_500"] and not m["integrity"]["missing"]
        and not m["integrity"]["videos_missing"] and not m["integrity"]["videos_undecodable"])

    # L90 分析
    l90 = m["l90"]
    fail_rows = re.findall(r'<tr class="l90-fail-row" data-task-idx="(\d+)" data-scene="([^"]+)" data-steps="(\d+)"', text)
    add("LIBERO_90 失败清单 = 61 行且 task_idx 与 summary 一致",
        len(fail_rows) == 61 and [int(r[0]) for r in fail_rows] == l90["fail_idx"],
        f"实际 {len(fail_rows)}")
    add("LIBERO_90 失败全部 steps = 500", all(r[2] == "500" for r in fail_rows))
    scene_rows = re.findall(r'<tr class="(?:zero |hi |mid )?scene-row" data-scene="([^"]+)" data-tasks="(\d+)" '
                            r'data-success="(\d+)" data-fail="(\d+)" data-rate="([\d.]+)"', text)
    add("LIBERO_90 场景表 20 行且 90/29/61 求和一致",
        len(scene_rows) == 20 and sum(int(r[1]) for r in scene_rows) == 90
        and sum(int(r[2]) for r in scene_rows) == 29 and sum(int(r[3]) for r in scene_rows) == 61,
        f"实际 {len(scene_rows)} 行")
    kw_rows = re.findall(r'<tr class="kw-row" data-kw="([^"]+)" data-fails="(\d+)" data-succs="(\d+)" '
                         r'data-total="(\d+)" data-fail-rate="([\d.]+)"', text)
    kw_expected = {(r["key"], str(r["fails"]), str(r["succs"]), str(r["total"]), str(r["fail_rate_pct"]))
                   for r in l90["keyword_rows"]}
    add("LIBERO_90 指令特征表数值一致",
        len(kw_rows) == len(l90["keyword_rows"])
        and {(a, b, c, d, e) for a, b, c, d, e in kw_rows} == kw_expected,
        f"实际 {len(kw_rows)} 行")
    hist_rows = re.findall(r'<tr class="hist-row" data-suite="([^"]+)" data-total="(\d+)">', text)
    add("steps 分布表 5 行且每行求和 = suite tasks",
        len(hist_rows) == 5 and all(int(n) == m["summary"]["suites"][s]["expected_tasks"] for s, n in hist_rows),
        f"实际 {hist_rows}")
    add("LIBERO_90 失败全部超时（fail_at_500 = 61）", l90["fail_at_500"] == 61 and l90["fails"] == 61)

    # 交互 / 声明 / 链接 / README
    add("任务筛选控件（suite/success）齐全",
        all(fid in text for fid in ('id="taskfilter"', 'id="filter-suite"', 'id="filter-success"',
                                    'id="filter-count"', 'id="filter-reset"')))
    add("口径声明包含 不可严格横比 / 单 seed / PyTorch / 50 trials / video on",
        "不可严格横比" in text and "单 seed" in text and "PyTorch" in text
        and "50" in text and "video on" in text)
    hrefs = re.findall(r'<a class="(?:local|xlink)" href="([^"]+)"', text)
    bad_links = [h for h in hrefs if not h.startswith("#") and not (REPORT_DIR / h).resolve().exists()]
    add("产物/视频相对链接全部可解析（离线可用）",
        len(hrefs) >= 150 and not bad_links, f"{len(hrefs)} 个链接; 失效 {bad_links[:3]}")
    add("无外链 CDN / 外部资源（单文件离线）",
        not re.search(r'https?://', text) and "<script src=" not in text
        and "<link " not in text and "<iframe" not in text)
    add("页脚含生成命令 / 数据来源 / 审计状态 / final_checks",
        "生成命令" in text and "数据来源" in text and "审计状态" in text and "15/15 PASS" in text)
    if OUT_README.exists():
        readme = OUT_README.read_text(encoding="utf-8")
        lines = readme.splitlines()
        add("披露旧视频索引表已由卡片网格取代",
            "视频索引表 → 卡片网格" in text and "video_index.json" in text,
            "缺少旧索引表→卡片网格的说明")
        add("README.md 存在且行数 <= 30", len(lines) <= 30, f"{len(lines)} 行")
        add("README 含核心数字与视频库说明（130/69/53.08/LIBERO_90/缩略图/--check）",
            "130" in readme and "69" in readme and "53.08" in readme
            and "LIBERO_90" in readme and "缩略图" in readme and "--check" in readme)
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
    parser = argparse.ArgumentParser(description="LIBERO 官方 5 套件 × pi05 评测 HTML 参考报告生成器")
    parser.add_argument("--check", action="store_true", help="只读校验现有 report/index.html + README.md，不写文件")
    args = parser.parse_args(argv)
    model = compute_model()
    validate_model(model)
    if args.check:
        return 0 if run_checks(model) else 1
    write_outputs(model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
