#!/usr/bin/env python3
"""LIBERO-90 分场景报告：pi0 baseline 参考视频清单 + 视频资产（静态生成）。

事实前提（本脚本每次生成 / 校验都会重新核查）
--------------------------------------------
本工作区没有 LIBERO-90 全量 pi0 视频。唯一可用的 pi0 baseline 是
``runs/libero-std-pi0-openvla-20261023/run/pi0/<suite>/<run>/videos/*.mp4``：
4 个标准套件（LIBERO_SPATIAL / LIBERO_OBJECT / LIBERO_GOAL / LIBERO_10）
× 10 任务 = 40 段（report/evidence.json：pi0 成功 35/40）。

因此为 LIBERO-90 的 20 个场景准备的是**参考视频**，不是该场景 L90 任务的实测：
  * ``exact_scene_l10``        —— LIBERO-10 任务与 L90 场景同名（场景一致、任务不同）；
  * ``suite_family_reference`` —— 同族套件的代表性视频（物体 / 动作 / 场景族近似）。

产物（全部由本脚本生成，可重跑；只读原始 run 数据，不跑仿真 / 不下载模型）
--------------------------------------------------------------------------
* ``runs/libero-90-combos-20261025/report/videos/``             复制的 mp4
* ``runs/libero-90-combos-20261025/report/video-manifest.json`` 机读清单
* ``runs/libero-90-combos-20261025/report/VIDEO_SOURCES.md``    人读来源说明（<= 60 行）

用法::

    .venv/bin/python scripts/build_libero90_video_manifest.py          # 生成 / 刷新
    .venv/bin/python scripts/build_libero90_video_manifest.py --check  # 生成 + 全量校验
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RUN_REL = "runs/libero-std-pi0-openvla-20261023"
RUN = ROOT / RUN_REL
EVIDENCE_REL = f"{RUN_REL}/report/evidence.json"
EVIDENCE = ROOT / EVIDENCE_REL
L10_CONFIG_DIR = RUN / "runtime/configs/tasks/libero_10"
CANDIDATES_REL = "runs/libero-90-combos-20261025/candidates.json"
CANDIDATES = ROOT / CANDIDATES_REL
INVENTORY_REL = ".tmp/libero90-combos/inventory.json"
INVENTORY = ROOT / INVENTORY_REL
REPORT_REL = "runs/libero-90-combos-20261025/report"
REPORT = ROOT / REPORT_REL
VIDEOS_DIR = REPORT / "videos"
MANIFEST = REPORT / "video-manifest.json"
SOURCES_MD = REPORT / "VIDEO_SOURCES.md"
EXTERNAL_RUNTIME = ROOT.parent / "libero-plus" / "libero-runtime"

# 官方 LIBERO-10 / LIBERO-90 场景名前缀（场景名本身含下划线，不能简单 split("_")）
SCENE_RE = re.compile(r"^(KITCHEN_SCENE\d+|LIVING_ROOM_SCENE\d+|STUDY_SCENE\d+)_(.+)$")
VIDEO_NAME_RE = re.compile(
    r"^pi0_(?P<suite>[A-Z][A-Z0-9_]*)_T(?P<idx>\d+)__"
    r"(?P<scene>(?:KITCHEN|LIVING_ROOM|STUDY)_SCENE\d+)__"
    r"(?P<kind>exact_scene_l10|suite_family_reference)\.mp4$"
)

KIND_EXACT = "exact_scene_l10"
KIND_FAMILY = "suite_family_reference"
KINDS = (KIND_EXACT, KIND_FAMILY)
SUITE_ORDER = ("LIBERO_SPATIAL", "LIBERO_OBJECT", "LIBERO_GOAL", "LIBERO_10")
SUITE_DIR = {s: s.lower() for s in SUITE_ORDER}
MAX_REFS_PER_SCENE = 4

# 场景 -> 同族套件补充参考（exact_scene_l10 由 LIBERO-10 官方任务映射自动生成）。
# 元组: (suite, task_idx, why)；why 是写给报告卡片的中文理由。
SECONDARY_REFS = {
    "KITCHEN_SCENE1": [
        ("LIBERO_SPATIAL", 4, "black bowl 在 wooden cabinet 上层抽屉 -> 放到 plate；动作/物体与本场景 open drawer + put black bowl 最近"),
        ("LIBERO_SPATIAL", 9, "black bowl 在 wooden cabinet 上 -> plate；对应本场景 put the black bowl on top of the cabinet"),
    ],
    "KITCHEN_SCENE3": [
        ("LIBERO_GOAL", 1, "put the bowl on the stove；与本场景 frying pan / moka pot 上炉同族动作"),
        ("LIBERO_GOAL", 7, "turn on the stove；与本场景 turn on the stove 动作相同（物体不同）"),
    ],
    "KITCHEN_SCENE4": [
        ("LIBERO_GOAL", 0, "open the middle drawer of the cabinet；与本场景开 / 关抽屉同族"),
        ("LIBERO_GOAL", 3, "open the top drawer and put the bowl inside；与本场景 black bowl 进抽屉同族（抽屉层不同）"),
        ("LIBERO_GOAL", 9, "put the wine bottle on the rack；与本场景 wine bottle on the wine rack 同族"),
    ],
    "KITCHEN_SCENE6": [
        ("LIBERO_10", 4, "同套件 LIBERO-10、同一组 mug 操作（white mug / yellow and white mug），但场景是 LIVING_ROOM_SCENE5"),
        ("LIBERO_10", 6, "同套件 LIBERO-10、white mug + to the right of 关系，但场景是 LIVING_ROOM_SCENE6"),
    ],
    "KITCHEN_SCENE8": [
        ("LIBERO_GOAL", 1, "bowl 上炉；本场景是把 moka pot 上炉"),
        ("LIBERO_GOAL", 7, "turn on the stove；本场景含 turn off / on 炉"),
    ],
    "KITCHEN_SCENE9": [
        ("LIBERO_GOAL", 1, "bowl 上炉；本场景 frying pan 上炉"),
        ("LIBERO_GOAL", 4, "bowl 放到 cabinet 顶；对应本场景 put ... on top of the cabinet"),
        ("LIBERO_GOAL", 7, "turn on the stove；与本场景 turn on the stove 动作同名"),
    ],
    "KITCHEN_SCENE10": [
        ("LIBERO_GOAL", 0, "open the middle drawer of the cabinet；本场景开 / 关 top drawer"),
        ("LIBERO_GOAL", 3, "open top drawer + bowl 放进；本场景 butter / pudding / bowl 进 top drawer"),
        ("LIBERO_GOAL", 4, "bowl 放到 cabinet 顶；对应本场景 put the black bowl on top of it"),
    ],
    "LIVING_ROOM_SCENE1": [
        ("LIBERO_OBJECT", 0, "alphabet soup -> basket；本场景 L90-33 同物体"),
        ("LIBERO_OBJECT", 1, "cream cheese -> basket；本场景 L90-32 cream cheese box"),
        ("LIBERO_OBJECT", 4, "ketchup -> basket；本场景 L90-31 同物体（pi0 此段失败）"),
    ],
    "LIVING_ROOM_SCENE2": [
        ("LIBERO_OBJECT", 6, "butter -> basket；本场景 L90-37 同物体"),
        ("LIBERO_OBJECT", 7, "milk -> basket；本场景 L90-36 同物体"),
    ],
    "LIVING_ROOM_SCENE4": [
        ("LIBERO_OBJECT", 2, "salad dressing -> basket；本场景 L90-43 同物体（basket vs tray）"),
        ("LIBERO_OBJECT", 8, "chocolate pudding -> basket；本场景 L90-44 同物体（basket vs tray）"),
    ],
    "LIVING_ROOM_SCENE5": [
        ("LIBERO_10", 6, "同套件 LIBERO-10、white mug 放 plate；本场景是 LR5 的左右 plate（不同场景）"),
    ],
    "LIVING_ROOM_SCENE6": [
        ("LIBERO_10", 4, "同套件 LIBERO-10、white / yellow and white mug 放左右 plate；本场景是 LR6（不同场景）"),
    ],
    "KITCHEN_SCENE2": [
        ("LIBERO_SPATIAL", 2, "black bowl 从 table center 放到 plate；对应本场景 bowl on plate 类任务"),
        ("LIBERO_SPATIAL", 4, "black bowl + wooden cabinet 抽屉；对应本场景 open the top drawer / bowl 进抽屉"),
        ("LIBERO_SPATIAL", 8, "black bowl 紧邻 plate -> 放到 plate；对应本场景 stacking / on the plate 类任务"),
    ],
    "KITCHEN_SCENE5": [
        ("LIBERO_SPATIAL", 4, "black bowl 在 wooden cabinet 上层抽屉；本场景 L90-60 同落点"),
        ("LIBERO_SPATIAL", 8, "black bowl 紧邻 plate -> plate；对应本场景 put the black bowl on the plate"),
        ("LIBERO_SPATIAL", 9, "black bowl 在 wooden cabinet 上 -> plate；对应本场景 put ... on top of the cabinet"),
    ],
    "KITCHEN_SCENE7": [
        ("LIBERO_SPATIAL", 0, "bowl -> plate 放置；本场景 white bowl on plate（SPATIAL 只有 black bowl）"),
        ("LIBERO_SPATIAL", 2, "bowl from table center -> plate；对应本场景 white bowl on plate（black bowl）"),
        ("LIBERO_SPATIAL", 8, "bowl 紧邻 plate -> plate；对应本场景 white bowl on plate"),
    ],
    "STUDY_SCENE2": [
        ("LIBERO_10", 5, "同套件 LIBERO-10 同名场景 STUDY_SCENE1 的 caddy / book 任务；ST2 场景不同（caddy / book 同构）"),
    ],
    "STUDY_SCENE3": [
        ("LIBERO_10", 5, "同套件 LIBERO-10 同名场景 STUDY_SCENE1 的 caddy / book 任务；ST3 场景不同（caddy / book 同构）"),
        ("LIBERO_10", 6, "white mug 操作 + to the right of 关系（本场景是把 mug 放到 caddy 右侧）"),
    ],
    "STUDY_SCENE4": [
        ("LIBERO_10", 5, "同套件 LIBERO-10 同名场景 STUDY_SCENE1 的 caddy / book 任务；ST4 场景不同（book / shelf 同构）"),
    ],
    "LIVING_ROOM_SCENE3": [
        ("LIBERO_OBJECT", 0, "alphabet soup -> basket；本场景 L90-85 同物体（basket vs tray）"),
        ("LIBERO_OBJECT", 1, "cream cheese -> basket；本场景 L90-88 cream cheese（basket vs tray）"),
        ("LIBERO_OBJECT", 5, "tomato sauce -> basket；本场景 L90-86 同物体（basket vs tray）"),
        ("LIBERO_OBJECT", 6, "butter -> basket；本场景 L90-87 同物体（basket vs tray）"),
    ],
}

# 生成 VIDEO_SOURCES.md / manifest 时引用的"无 L90 视频"核查命令（结果由 scan_workspace 实测填充）
SEARCH_COMMANDS = [
    "find runs -type d -name libero_90",
    "find runs -name '*.mp4' -path '*libero_90*'",
    "find runs -name '*.mp4' -path '*libero-90*'",
    "find . -name '*.mp4' -path '*libero90*'",
    "find . -path '*configs/tasks/libero_90*' -name '*.yaml'",
    "find runs/libero-std-pi0-openvla-20261023/run/pi0 -maxdepth 2 -type d",
]

# docs/libero-90-baseline-*.md 引用过的历史 L90 baseline run 目录（用于说明它们已不在本工作区）
HISTORICAL_L90_RUNS = [
    "runs/libero90-candidates-baseline-pi05-seed3",
    "runs/libero90-candidates-baseline-pi05-seeds0-4",
    "runs/libero90-close-diagnostic-pi05-seeds0-4",
    "runs/pi05-libero90-baseline-video",
    "runs/pi05-libero90-baseline-video-600",
    "runs/openvla-libero90-baseline-video-600",
]

# ════════════════════════════════════════════════
# 基础工具
# ════════════════════════════════════════════════


def rel(path: Path) -> str:
    """仓库相对路径（posix 风格）；不在仓库内时返回绝对路径。"""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def dump_json(path: Path, obj: dict) -> None:
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


# ════════════════════════════════════════════════
# 输入解析
# ════════════════════════════════════════════════


def load_evidence() -> dict:
    """解析 evidence.json：40 条 pi0 任务 + OpenVLA-OFT 对照 + pi0 视频源路径。"""
    if not EVIDENCE.is_file():
        raise SystemExit(f"[build] FATAL: evidence.json 不存在: {EVIDENCE_REL}")
    ev = load_json(EVIDENCE)
    tasks_raw = ev.get("tasks") or []
    if len(tasks_raw) != 40:
        raise SystemExit(f"[build] FATAL: evidence.json tasks 应为 40 条，实际 {len(tasks_raw)}")
    tasks: dict[tuple[str, int], dict] = {}
    for t in tasks_raw:
        key = (str(t["suite"]), int(t["task_idx"]))
        if key in tasks:
            raise SystemExit(f"[build] FATAL: evidence.json 任务重复: {key}")
        tasks[key] = {
            "suite": key[0],
            "task_idx": key[1],
            "instruction": str(t["instruction"]),
            "pi0": {"success": bool(t["pi0"]["success"]), "steps": int(t["pi0"]["steps"])},
            "openvla_oft": {
                "success": bool(t["openvla_oft"]["success"]),
                "steps": int(t["openvla_oft"]["steps"]),
            },
        }
    if {k[0] for k in tasks} != set(SUITE_ORDER):
        raise SystemExit("[build] FATAL: evidence.json 的套件集合不是 4 个标准套件")
    for suite in SUITE_ORDER:
        idxs = sorted(k[1] for k in tasks if k[0] == suite)
        if idxs != list(range(10)):
            raise SystemExit(f"[build] FATAL: {suite} 任务编号不是 0..9: {idxs}")

    # pi0 records 提供原始视频路径（video_src）与 source_run，用于存在性 / sha256 校验
    pi0_records: dict[tuple[str, int], dict] = {}
    for r in ev.get("records") or []:
        if r.get("kind") != "pi0":
            continue
        key = (str(r["suite"]), int(r["task_idx"]))
        if key in pi0_records:
            raise SystemExit(f"[build] FATAL: evidence.json pi0 record 重复: {key}")
        pi0_records[key] = {
            "record_id": r.get("record_id"),
            "video_src": r.get("video_src"),
            "video_exists": r.get("video_exists"),
            "source_run": r.get("source_run"),
        }
    if set(pi0_records) != set(tasks):
        raise SystemExit("[build] FATAL: evidence.json pi0 records 与 tasks 不一一对应")

    videos: dict[tuple[str, int], Path] = {}
    for key, rec in pi0_records.items():
        suite, idx = key
        src_raw = rec.get("video_src")
        if src_raw:
            src = Path(src_raw)
        else:  # 兜底：从 run/pi0/<suite>/ 下 glob 唯一视频
            hits = sorted((RUN / "run" / "pi0" / SUITE_DIR[suite]).rglob(f"*_T{idx}__baseline_seed0.mp4"))
            if len(hits) != 1:
                raise SystemExit(f"[build] FATAL: 无法定位 {suite} T{idx} 的 pi0 视频（glob={len(hits)}）")
            src = hits[0]
        if not src.is_file():
            raise SystemExit(f"[build] FATAL: pi0 视频不存在: {src}")
        expect_name = f"{suite}_T{idx}__baseline_seed0.mp4"
        if src.name != expect_name:
            raise SystemExit(f"[build] FATAL: 视频文件名与任务不匹配: {src.name} != {expect_name}")
        videos[key] = src

    metrics = (ev.get("metrics") or {}).get("pi0") or {}
    if int(metrics.get("episodes", -1)) != 40:
        raise SystemExit(f"[build] FATAL: evidence.metrics.pi0.episodes != 40: {metrics.get('episodes')}")
    success_count = sum(1 for t in tasks.values() if t["pi0"]["success"])
    if success_count != 35:
        raise SystemExit(f"[build] FATAL: pi0 成功数不是 35: {success_count}")
    if success_count != int(metrics.get("success", -1)):
        raise SystemExit("[build] FATAL: evidence.metrics.pi0.success 与 tasks 汇总不一致")
    suites = {s: {"total": 0, "success": 0} for s in SUITE_ORDER}
    for suite, _idx in tasks:
        suites[suite]["total"] += 1
        if tasks[(suite, _idx)]["pi0"]["success"]:
            suites[suite]["success"] += 1
    return {
        "path": EVIDENCE_REL,
        "tasks": tasks,
        "records": pi0_records,
        "videos": videos,
        "success_count": success_count,
        "suites": suites,
    }


def _parse_simple_yaml(text: str) -> dict:
    """解析 runtime task config 的扁平两空格 YAML（task: / evaluation: 下的 key: value）。"""
    meta: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"^\s{2}([a-z_]+):\s*(.+?)\s*$", line)
        if m:
            meta[m.group(1)] = m.group(2)
    return meta


def load_l10_tasks(ev: dict) -> dict:
    """解析 LIBERO-10 的 10 条官方任务：task_idx -> 场景名（文件名 SCENE 前缀）+ 官方 language。

    LIBERO-10 的 benchmark 顺序（task_idx）由 run_benchmark.py 从
    ``runtime/configs/tasks/libero_10/*.yaml`` 发现，每个 YAML 内显式写
    ``task.task_idx`` 与 ``task.bddl_name``，因此用本次 baseline run 自带的
    configs 解析最可靠（官方 language 由 benchmark ``grab_language_from_filename``
    从文件名派生：去场景前缀、下划线转空格）。
    """
    files = sorted(L10_CONFIG_DIR.glob("*.yaml"))
    if len(files) != 10:
        raise SystemExit(f"[build] FATAL: LIBERO-10 task configs 应为 10 个，实际 {len(files)}")
    by_idx: dict[int, dict] = {}
    scene_to_tasks: dict[str, list[int]] = {}
    for fp in files:
        meta = _parse_simple_yaml(fp.read_text(encoding="utf-8"))
        if meta.get("source") != "LIBERO_10":
            raise SystemExit(f"[build] FATAL: {rel(fp)} 的 task.source 不是 LIBERO_10")
        idx = int(meta["task_idx"])
        bddl_name = meta["bddl_name"]
        m = SCENE_RE.match(bddl_name)
        if not m:
            raise SystemExit(f"[build] FATAL: 无法从 bddl_name 解析场景: {bddl_name}")
        scene, lang_part = m.group(1), m.group(2)
        language = lang_part.replace("_", " ")
        ev_task = ev["tasks"].get(("LIBERO_10", idx))
        if ev_task is None:
            raise SystemExit(f"[build] FATAL: evidence.json 缺 LIBERO-10 T{idx}")
        if ev_task["instruction"] != language:
            raise SystemExit(
                f"[build] FATAL: LIBERO-10 T{idx} 官方 language 与 evidence instruction 不一致:\n"
                f"  config: {language}\n  evidence: {ev_task['instruction']}"
            )
        if idx in by_idx:
            raise SystemExit(f"[build] FATAL: LIBERO-10 task_idx 重复: {idx}")
        by_idx[idx] = {
            "task_idx": idx,
            "scene": scene,
            "language": language,
            "bddl_name": bddl_name,
            "config_file": rel(fp),
        }
        scene_to_tasks.setdefault(scene, []).append(idx)
    if sorted(by_idx) != list(range(10)):
        raise SystemExit(f"[build] FATAL: LIBERO-10 task_idx 不是 0..9: {sorted(by_idx)}")
    for ids in scene_to_tasks.values():
        ids.sort()
    return {"by_idx": by_idx, "scene_to_tasks": scene_to_tasks, "n": len(by_idx)}


def load_l90_scenes() -> dict:
    """从 LIBERO-90 组合清单解析 20 个场景（报告使用的场景顺序）+ 每场景 L90 任务数。

    ``candidates.json`` 的 ``stats.per_scene`` 是报告/文档沿用的 20 场景顺序；
    ``.tmp/libero90-combos/inventory.json``（可选）提供每场景的 L90 任务编号与总数。
    """
    if not CANDIDATES.is_file():
        raise SystemExit(f"[build] FATAL: candidates.json 不存在: {CANDIDATES_REL}")
    cand = load_json(CANDIDATES)
    per_scene = (cand.get("stats") or {}).get("per_scene") or []
    if len(per_scene) != 20:
        raise SystemExit(f"[build] FATAL: candidates.json stats.per_scene 应为 20 场景，实际 {len(per_scene)}")
    order: list[str] = []
    meta: dict[str, dict] = {}
    for row in per_scene:
        scene = str(row["scene"])
        if not SCENE_RE.match(scene + "_x"):  # 场景名本身没有任务后缀，用 SCENE_RE 校验前缀格式
            raise SystemExit(f"[build] FATAL: 非法场景名: {scene}")
        if scene in meta:
            raise SystemExit(f"[build] FATAL: 场景重复: {scene}")
        order.append(scene)
        meta[scene] = {
            "scene_short": row.get("scene_short"),
            "n_pool_tasks": row.get("n_pool_tasks"),
        }
    if not ({"KITCHEN_SCENE1", "LIVING_ROOM_SCENE1", "STUDY_SCENE1"} <= set(order)):
        raise SystemExit("[build] FATAL: 20 场景清单缺少 KITCHEN/LIVING_ROOM/STUDY 场景")
    inventory_used = False
    if INVENTORY.is_file():
        inv = load_json(INVENTORY)
        inv_scenes = inv.get("scenes") or {}
        if set(inv_scenes) != set(order):
            raise SystemExit("[build] FATAL: inventory.json 场景集合与 candidates.json 不一致")
        for scene in order:
            ids = sorted(int(i) for i in inv_scenes[scene])
            meta[scene]["l90_task_indices"] = ids
            meta[scene]["l90_task_count"] = len(ids)
        inventory_used = True
    return {
        "order": order,
        "meta": meta,
        "source": CANDIDATES_REL,
        "inventory_source": INVENTORY_REL if inventory_used else None,
    }


# ════════════════════════════════════════════════
# 映射 + 复制
# ════════════════════════════════════════════════


def build_selection(ev: dict, l10: dict, l90: dict) -> dict:
    """20 个 L90 场景 -> 参考视频列表（exact_scene_l10 优先，其次 suite_family_reference）。"""
    scenes = l90["order"]
    unknown = set(SECONDARY_REFS) - set(scenes)
    if unknown:
        raise SystemExit(f"[build] FATAL: SECONDARY_REFS 含未知场景: {sorted(unknown)}")
    selection: dict[str, list[dict]] = {}
    for scene in scenes:
        refs: list[dict] = []
        for idx in sorted(l10["scene_to_tasks"].get(scene, [])):
            t = l10["by_idx"][idx]
            refs.append(
                {
                    "suite": "LIBERO_10",
                    "task_idx": idx,
                    "kind": KIND_EXACT,
                    "why": (
                        f"LIBERO-10 任务 T{idx}（{t['language']}）与 {scene} 同名场景；"
                        "场景一致、任务不同，是最贴近的参考，但不是 LIBERO-90 该场景任务的实测"
                    ),
                }
            )
        for suite, idx, why in SECONDARY_REFS.get(scene, []):
            refs.append({"suite": suite, "task_idx": idx, "kind": KIND_FAMILY, "why": why})
        if not refs:
            raise SystemExit(f"[build] FATAL: 场景 {scene} 没有参考视频")
        if len(refs) > MAX_REFS_PER_SCENE:
            raise SystemExit(f"[build] FATAL: 场景 {scene} 参考视频超过 {MAX_REFS_PER_SCENE} 段")
        seen: set[tuple[str, int]] = set()
        for r in refs:
            key = (r["suite"], r["task_idx"])
            if key not in ev["tasks"]:
                raise SystemExit(f"[build] FATAL: 引用任务不在 evidence 40 条内: {key}")
            if key in seen:
                raise SystemExit(f"[build] FATAL: 场景 {scene} 内重复引用: {key}")
            seen.add(key)
            r["l10_scene"] = l10["by_idx"][key[1]]["scene"] if key[0] == "LIBERO_10" else None
        selection[scene] = refs
    # 不变量：20 场景；exact 恰好 10 段（每条 LIBERO-10 任务正好对应一个同名 L90 场景）
    if len(selection) != 20:
        raise SystemExit(f"[build] FATAL: 场景数不是 20: {len(selection)}")
    exact = [r for refs in selection.values() for r in refs if r["kind"] == KIND_EXACT]
    if len(exact) != 10 or {r["task_idx"] for r in exact} != set(range(10)):
        raise SystemExit(f"[build] FATAL: exact_scene_l10 不是 10 段或未覆盖 LIBERO-10 全部任务")
    return selection


def materialize(ev: dict, selection: dict) -> dict:
    """复制选中的源视频到 report/videos/（命名 pi0_<SUITE>_T<idx>__<scene>__<kind>.mp4）。"""
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    expected: set[str] = set()
    entries: list[dict] = []
    sha_cache: dict[Path, str] = {}
    copies_new = 0
    for scene, refs in selection.items():
        for ref in refs:
            key = (ref["suite"], ref["task_idx"])
            src = ev["videos"][key]
            task = ev["tasks"][key]
            fname = f"pi0_{key[0]}_T{key[1]}__{scene}__{ref['kind']}.mp4"
            m = VIDEO_NAME_RE.match(fname)
            if not m or m.group("scene") != scene or m.group("kind") != ref["kind"]:
                raise SystemExit(f"[build] FATAL: 视频命名不合规: {fname}")
            dest = VIDEOS_DIR / fname
            src_sha = sha_cache.get(src) or sha256_file(src)
            sha_cache[src] = src_sha
            if dest.exists() and sha256_file(dest) == src_sha:
                pass
            else:
                shutil.copy2(src, dest)
                copies_new += 1
            dest_sha = sha256_file(dest)
            if dest_sha != src_sha:
                raise SystemExit(f"[build] FATAL: 复制后 sha256 不一致: {fname}")
            if fname in expected:
                raise SystemExit(f"[build] FATAL: 目标文件名重复: {fname}")
            expected.add(fname)
            entries.append(
                {
                    "file": f"videos/{fname}",
                    "sha256": dest_sha,
                    "bytes": dest.stat().st_size,
                    "suite": key[0],
                    "task_idx": key[1],
                    "instruction": task["instruction"],
                    "success": task["pi0"]["success"],
                    "steps": task["pi0"]["steps"],
                    "openvla_oft": task["openvla_oft"],
                    "kind": ref["kind"],
                    "l10_scene": ref["l10_scene"],
                    "used_by_l90_scenes": [scene],
                    "source_video": rel(src),
                    "source_run": rel(Path(ev["records"][key]["source_run"])) if ev["records"][key].get("source_run") else None,
                    "why": ref["why"],
                    "honest_note": (
                        f"本视频是 {key[0]} 套件第 {key[1]} 个任务（{task['instruction']}）的 pi0 baseline："
                        f"success={task['pi0']['success']}, steps={task['pi0']['steps']}；"
                        f"不是 LIBERO-90 {scene} 场景某条任务的实测。"
                    ),
                }
            )
    # 清理上一轮生成但本轮不再需要的 pi0_*.mp4（只动本脚本的命名空间，不碰其他文件）
    stale = 0
    for p in VIDEOS_DIR.glob("pi0_*.mp4"):
        if p.name not in expected:
            p.unlink()
            stale += 1
    return {
        "entries": entries,
        "expected": expected,
        "copies_new": copies_new,
        "stale_removed": stale,
        "unique_sources": len(sha_cache),
        "copied_bytes": sum(e["bytes"] for e in entries),
    }

# ════════════════════════════════════════════════
# 工作区扫描："本工作区没有 LIBERO-90 视频" 的实测证据
# ════════════════════════════════════════════════


def scan_workspace() -> dict:
    runs = ROOT / "runs"
    if not runs.is_dir():
        raise SystemExit("[build] FATAL: runs/ 不存在")
    mp4_total = 0
    l90_hits: list[str] = []
    dirs_named_l90: list[str] = []
    l90_config_dirs: list[str] = []
    pi0_under_run_pi0 = 0
    report_parts = Path(REPORT_REL).parts
    report_mp4_excluded = 0
    for dirpath, dirnames, filenames in os.walk(runs):
        rel_dir = Path(dirpath).relative_to(ROOT)
        parts = rel_dir.parts
        # 排除本脚本自己的输出目录（report/videos 里的 pi0_*.mp4 是复制品，不算"工作区里存在 L90 视频"）
        if parts[: len(report_parts)] == report_parts:
            report_mp4_excluded += sum(1 for fn in filenames if fn.lower().endswith(".mp4"))
            dirnames[:] = []
            continue
        if "libero_90" in dirnames:
            dirs_named_l90.append((rel_dir / "libero_90").as_posix())
        if (
            len(parts) >= 2
            and parts[-1] == "tasks"
            and parts[-2] == "configs"
            and "libero_90" in dirnames
        ):
            l90_config_dirs.append((rel_dir / "libero_90").as_posix())
        for fn in filenames:
            if not fn.lower().endswith(".mp4"):
                continue
            mp4_total += 1
            relp = (rel_dir / fn).as_posix()
            low = relp.lower()
            if "libero_90" in low or "libero-90" in low or "libero90" in low:
                l90_hits.append(relp)
            if "/run/pi0/" in relp:
                pi0_under_run_pi0 += 1
    historical_present = [p for p in HISTORICAL_L90_RUNS if (ROOT / p).exists()]
    ext_dir = EXTERNAL_RUNTIME / "configs/tasks/libero_90"
    external_l90_configs = len(list(ext_dir.glob("*.yaml"))) if ext_dir.is_dir() else 0
    return {
        "scanned_at": now_iso(),
        "scope": "工作区 runs/（全部 run 输出）",
        "mp4_total_under_runs": mp4_total,
        "report_output_mp4_excluded": report_mp4_excluded,
        "l90_identified_mp4": l90_hits,
        "l90_identified_mp4_count": len(l90_hits),
        "dirs_named_libero_90": dirs_named_l90,
        "l90_task_config_dirs_in_workspace": l90_config_dirs,
        "pi0_videos_under_run_pi0": pi0_under_run_pi0,
        "historical_l90_run_dirs_from_docs": HISTORICAL_L90_RUNS,
        "historical_l90_run_dirs_present": historical_present,
        "external_runtime_l90_task_configs": external_l90_configs,
    }


def build_no_l90_evidence(scan: dict) -> dict:
    pi0_suites = sorted(p.name for p in (RUN / "run/pi0").iterdir() if p.is_dir())
    rows = [
        {
            "command": "find runs -type d -name libero_90",
            "result": f"{len(scan['dirs_named_libero_90'])} 个目录",
        },
        {
            "command": "find runs -name '*.mp4' -path '*libero_90*'（及变体 *libero-90* / *libero90*）",
            "result": f"{scan['l90_identified_mp4_count']} 个视频 / runs/ 共 {scan['mp4_total_under_runs']} 个 mp4",
        },
        {
            "command": "同上扫描（排除本报告自己的视频副本 report/videos/）",
            "result": f"仍为 0 个 L90 视频；manifest 记录 report_output_mp4_excluded={scan['report_output_mp4_excluded']}（字面扫描会命中这些复制品，不是 L90 素材）",
        },
        {
            "command": "find . -path '*configs/tasks/libero_90*' -name '*.yaml'",
            "result": f"{len(scan['l90_task_config_dirs_in_workspace'])} 个目录 / 0 个 yaml（本工作区无 L90 运行时任务配置）",
        },
        {
            "command": "find runs/libero-std-pi0-openvla-20261023/run/pi0 -maxdepth 2 -type d",
            "result": f"仅 {len(pi0_suites)} 个标准套件目录（{', '.join(pi0_suites)}）；run/pi0 下 pi0 视频共 {scan['pi0_videos_under_run_pi0']} 段",
        },
        {
            "command": "ls docs/libero-90-baseline-*.md 引用的历史 L90 run 目录",
            "result": f"{len(scan['historical_l90_run_dirs_present'])}/{len(scan['historical_l90_run_dirs_from_docs'])} 个仍在工作区（均已不存在）",
        },
    ]
    return {
        "conclusion": "本工作区没有 LIBERO-90 官方任务的 pi0 视频；唯一 pi0 baseline 是 4 个标准套件 × 10 任务 = 40 段",
        "scope": scan["scope"],
        "scanned_at": scan["scanned_at"],
        "search_results": rows,
        "mp4_total_under_runs": scan["mp4_total_under_runs"],
        "l90_identified_mp4_count": scan["l90_identified_mp4_count"],
        "l90_identified_mp4_examples": scan["l90_identified_mp4"][:5],
        "dirs_named_libero_90": scan["dirs_named_libero_90"],
        "l90_task_config_dirs_in_workspace": scan["l90_task_config_dirs_in_workspace"],
        "historical_l90_run_dirs_present": scan["historical_l90_run_dirs_present"],
        "external_runtime_l90_task_configs": scan["external_runtime_l90_task_configs"],
        "note": (
            "历史 LIBERO-90 baseline（pi05 / openvla，11 条任务）见 docs/libero-90-baseline-pi05-seed3.md 与 "
            "docs/libero-90-baseline-seed-sweep.md，但其 run 目录已不在本工作区；外部 runtime "
            "../libero-plus/libero-runtime/configs/tasks/libero_90/ 仍保留部分 L90 任务配置，可用于补录。"
        ),
    }


# ════════════════════════════════════════════════
# 清单 / 文档生成
# ════════════════════════════════════════════════


def build_manifest(ev: dict, l10: dict, l90: dict, selection: dict, materialized: dict, scan: dict) -> dict:
    entries = materialized["entries"]
    by_file = {e["file"]: e for e in entries}
    scene_map: dict[str, list[dict]] = {}
    for scene in l90["order"]:
        rows = []
        for e in entries:
            if scene not in e["used_by_l90_scenes"]:
                continue
            rows.append(
                {
                    "file": e["file"],
                    "kind": e["kind"],
                    "why": e["why"],
                    "suite": e["suite"],
                    "task_idx": e["task_idx"],
                    "instruction": e["instruction"],
                    "success": e["success"],
                    "steps": e["steps"],
                    "l10_scene": e["l10_scene"],
                    "honest_note": e["honest_note"],
                }
            )
        scene_map[scene] = rows
    if set(scene_map) != set(l90["order"]) or set(by_file) != {r["file"] for rows in scene_map.values() for r in rows}:
        raise SystemExit("[build] FATAL: scene_map 与 videos 不一致")

    used: dict[tuple[str, int], list[str]] = {}
    for e in entries:
        used.setdefault((e["suite"], e["task_idx"]), []).extend(e["used_by_l90_scenes"])
    baseline_tasks = []
    for suite in SUITE_ORDER:
        for idx in range(10):
            key = (suite, idx)
            t = ev["tasks"][key]
            scenes = sorted(set(used.get(key, [])), key=l90["order"].index)
            baseline_tasks.append(
                {
                    "suite": suite,
                    "task_idx": idx,
                    "instruction": t["instruction"],
                    "success": t["pi0"]["success"],
                    "steps": t["pi0"]["steps"],
                    "openvla_oft": t["openvla_oft"],
                    "source_video": rel(ev["videos"][key]),
                    "copied_files": [e["file"] for e in entries if (e["suite"], e["task_idx"]) == key],
                    "used_by_l90_scenes": scenes,
                }
            )
    exact_refs = sum(1 for e in entries if e["kind"] == KIND_EXACT)
    family_refs = len(entries) - exact_refs
    unused = [f"{b['suite']} T{b['task_idx']}" for b in baseline_tasks if not b["copied_files"]]
    scene_meta = {}
    for scene in l90["order"]:
        m = dict(l90["meta"][scene])
        m["video_count"] = len(scene_map[scene])
        m["exact_count"] = sum(1 for r in scene_map[scene] if r["kind"] == KIND_EXACT)
        m["family_count"] = m["video_count"] - m["exact_count"]
        scene_meta[scene] = m
    gaps = [
        "本工作区无 LIBERO-90 全量 pi0 视频：唯一 pi0 baseline 是 4 个标准套件 × 10 任务 = 40 段"
        "（runs/libero-std-pi0-openvla-20261023/run/pi0/）；搜索命令与结果见 no_l90_video_evidence；"
        "L90 每场景每任务的官方 baseline 待补录。",
        f"本清单 20 个场景的 {len(entries)} 段视频全部是参考视频，不是 LIBERO-90 任务实测："
        f"{exact_refs} 段 exact_scene_l10（LIBERO-10 同名场景、任务不同）+ "
        f"{family_refs} 段 suite_family_reference（同族套件、场景不同）。",
        "L90 官方 baseline 待补录：scripts/run_libero90_baseline.py --model pi0 可直接跑 LIBERO_90 并"
        "输出标准 results/summary/videos；外部 runtime 已有 13 个 L90 任务配置（见 VIDEO_SOURCES.md §5）。",
        "物体实例近似提示：KS7 的 L90 物体是 white bowl，但 SPATIAL 参考视频只有 black bowl；"
        "KS6/KS7 的 microwave 操作在 40 段 pi0 baseline 中只有 LIBERO-10 T9 一段、且 pi0 失败；"
        "LR5/LR6 的 mug 参考来自 LIBERO-10 同套件任务——这些只能作族级参考，物体实例不保证一致。",
        f"40 段 pi0 中未被任何场景引用 {len(unused)} 段（" + "、".join(unused) + "）；"
        "如需全量 baseline 画廊，可直接读 baseline_tasks[].source_video 指向的原始视频。",
        "历史 LIBERO-90 baseline（pi05 / openvla，11 条任务，见 docs/libero-90-baseline-*.md）的 run 目录"
        "已不在本工作区，本清单不含其视频。",
    ]
    return {
        "schema_version": "libero90-report-video-manifest.v1",
        "generated_at": now_iso(),
        "generator": "scripts/build_libero90_video_manifest.py",
        "model": "pi0",
        "source_run": RUN_REL,
        "source_evidence": EVIDENCE_REL,
        "source_pi0_videos_dir": f"{RUN_REL}/run/pi0",
        "pi0_task_count": 40,
        "pi0_success_count": ev["success_count"],
        "pi0_suites": ev["suites"],
        "video_count": len(entries),
        "unique_source_video_count": materialized["unique_sources"],
        "copied_bytes": materialized["copied_bytes"],
        "source_videos_total_bytes": sum(ev["videos"][k].stat().st_size for k in ev["videos"]),
        "kind_counts": {KIND_EXACT: exact_refs, KIND_FAMILY: family_refs},
        "scene_count": len(l90["order"]),
        "scene_order": list(l90["order"]),
        "scene_meta": scene_meta,
        "selection_rules": {
            "priority": "每场景先列 exact_scene_l10，再列 suite_family_reference，最多 4 段",
            "exact_scene_l10": (
                "LIBERO-10 的 10 条双目标任务与 9 个 LIBERO-90 场景同名；"
                "映射来自 runtime/configs/tasks/libero_10/*.yaml 的 task.task_idx -> task.bddl_name"
            ),
            "suite_family_reference": (
                "非 exact 场景按套件族映射：KS1/KS2/KS5/KS7 -> LIBERO_SPATIAL；KS9/KS10 -> LIBERO_GOAL；"
                "LR1/LR2/LR3/LR4/LR5/LR6 -> LIBERO_OBJECT；ST2/ST3/ST4 -> LIBERO-10 的 STUDY_SCENE1（T5）"
            ),
            "exact_scene_secondary": (
                "exact 场景的补充参考：KS3/KS4/KS8 -> LIBERO_GOAL（stove/drawer/wine 类）；"
                "KS6/LR5/LR6 -> LIBERO-10 同套件 sibling（mug/plate 类）；LR1/LR2 -> LIBERO_OBJECT（同物体进 basket）"
            ),
            "honesty": "所有视频 kind 均非 L90 实测；每段 why / honest_note 写明来源任务与 L90 场景的差别",
        },
        "videos": entries,
        "scene_map": scene_map,
        "baseline_tasks": baseline_tasks,
        "gaps": gaps,
        "no_l90_video_evidence": build_no_l90_evidence(scan),
    }


SUITE_ABBR = {"LIBERO_SPATIAL": "SPATIAL", "LIBERO_OBJECT": "OBJECT", "LIBERO_GOAL": "GOAL", "LIBERO_10": "L10"}


def _refs_summary(refs: list[dict]) -> str:
    groups: dict[str, list[str]] = {}
    order: list[str] = []
    for r in refs:
        suite = r["suite"]
        if suite not in groups:
            groups[suite] = []
            order.append(suite)
        star = "★" if r["kind"] == KIND_EXACT else ""
        groups[suite].append(f"{star}T{r['task_idx']}")
    return " · ".join(f"{SUITE_ABBR[s]} " + ", ".join(groups[s]) for s in order)


def render_video_sources_md(manifest: dict) -> str:
    ev = manifest["no_l90_video_evidence"]
    scene_meta = manifest["scene_meta"]
    scene_map = manifest["scene_map"]
    lines: list[str] = []
    lines.append("# LIBERO-90 分场景报告：pi0 baseline 参考视频来源")
    lines.append("")
    lines.append(
        "> 由 `scripts/build_libero90_video_manifest.py` 生成（`--check` 可复验）。"
        "静态整理：只读原始 run 数据，不跑仿真、不下载模型、不改原始视频。"
    )
    lines.append("")
    lines.append("## 1. 结论")
    lines.append(
        "- **本工作区没有 LIBERO-90 全量 pi0 视频** → 20 个 L90 场景页里的视频全部是**参考视频**，"
        "不是该场景 L90 任务的实测 baseline；L90 官方 baseline 待补录（见 §5）。"
    )
    suites = manifest["pi0_suites"]
    lines.append(
        f"- 唯一 pi0 baseline：`{manifest['source_run']}/run/pi0/<suite>/`，4 套件 × 10 任务 = "
        f"**{manifest['pi0_task_count']} 段**（源视频合计约 {manifest['source_videos_total_bytes'] / 1e6:.1f} MB），"
        f"pi0 成功 **{manifest['pi0_success_count']}/{manifest['pi0_task_count']}**："
        f"SPATIAL {suites['LIBERO_SPATIAL']['success']}/10、OBJECT {suites['LIBERO_OBJECT']['success']}/10、"
        f"GOAL {suites['LIBERO_GOAL']['success']}/10、LIBERO-10 {suites['LIBERO_10']['success']}/10。"
    )
    lines.append(
        f"- 本目录复制 **{manifest['video_count']} 段**（{manifest['unique_source_video_count']} 个不同源视频；"
        "同一源视频被多个场景引用时重复复制，文件名不同），命名 "
        "`pi0_<SUITE>_T<idx>__<L90scene>__<kind>.mp4`；sha256 / 字节数见 `video-manifest.json`。"
    )
    lines.append("")
    lines.append("## 2. kind 标注规则（报告卡片必须原样标注）")
    lines.append("| kind | 含义 | 段数 |")
    lines.append("| --- | --- | ---: |")
    lines.append(
        f"| `{KIND_EXACT}` | LIBERO-10 任务与 L90 场景同名：场景一致、任务不同（最贴近的参考） | "
        f"{manifest['kind_counts'][KIND_EXACT]} |"
    )
    lines.append(
        f"| `{KIND_FAMILY}` | 同族套件参考：物体 / 动作 / 场景族近似，场景不同 | "
        f"{manifest['kind_counts'][KIND_FAMILY]} |"
    )
    lines.append("")
    lines.append(
        '卡片文案模板（照抄 manifest 的 `honest_note`）：**"本视频是 <SUITE> 第 <idx> 个任务的 pi0 baseline'
        '（success=…, steps=…），不是 L90 该场景任务的实测。"**'
    )
    lines.append("")
    lines.append("## 3. 每场景映射表")
    lines.append("| L90 场景（L90 任务数） | 段数 | exact | 参考来源（suite Tidx，★=exact） |")
    lines.append("| --- | ---: | ---: | --- |")
    for scene in manifest["scene_order"]:
        meta = scene_meta[scene]
        n = meta.get("l90_task_count")
        n_label = f"{n}" if n is not None else f"{meta.get('n_pool_tasks')} pool"
        refs = scene_map[scene]
        lines.append(
            f"| {scene}（{n_label}） | {len(refs)} | {meta['exact_count']} | {_refs_summary(refs)} |"
        )
    lines.append("")
    lines.append('## 4. 为什么说"没有 L90 视频"（本清单生成时实测）')
    lines.append("| 核查命令（WSL，仓库根目录） | 结果 |")
    lines.append("| --- | --- |")
    for row in ev["search_results"]:
        lines.append(f"| `{row['command']}` | {row['result']} |")
    lines.append("")
    lines.append("## 5. 后续补录线索（L90 实测 baseline）")
    lines.append(
        "1. 运行时任务配置：外部 runtime 已有 "
        f"{ev['external_runtime_l90_task_configs']} 个 L90 任务配置 "
        "`../libero-plus/libero-runtime/configs/tasks/libero_90/`；补齐 90 条可运行 "
        "`python3 scripts/prepare_libero90_task_configs.py --runtime-root ../libero-plus/libero-runtime "
        "--inventory 0,1,...,89`。"
    )
    lines.append(
        "2. pi0 跑官方 LIBERO-90（标准 results/summary/videos 格式）："
        "`../openpi/.venv/bin/python scripts/run_libero90_baseline.py "
        "--runtime-root ../libero-plus/libero-runtime --output runs/libero90-baseline-pi0-seed0 "
        "--trace-dir runs/libero90-baseline-pi0-seed0/atom-traces --model pi0 "
        "--task-ids <bench_idx,...> --seed-ids 0 --max-steps 600 --replan-steps 5 --video`。"
    )
    lines.append(
        "3. 跑完把新 run 的 evidence 并入后重跑本脚本即可；若工作区出现 L90 视频，"
        "`--check` 会失败并提示改用实测 baseline 标注（不会静默沿用旧口径）。"
    )
    lines.append("")
    lines.append(
        "数字口径：段数 / 成功率 / 映射全部由脚本从 `report/evidence.json`、"
        "`runtime/configs/tasks/libero_10/*.yaml`、`runs/libero-90-combos-20261025/candidates.json` 计算，无手填。"
    )
    text = "\n".join(lines) + "\n"
    if len(lines) > 60:
        raise SystemExit(f"[build] FATAL: VIDEO_SOURCES.md 行数 {len(lines)} > 60")
    return text

# ════════════════════════════════════════════════
# --check：生成后全量校验
# ════════════════════════════════════════════════


def check(ev: dict, l10: dict, l90: dict, selection: dict, materialized: dict, manifest: dict, scan: dict) -> list[str]:
    errors: list[str] = []

    def fail(msg: str) -> None:
        errors.append(msg)

    # 1) manifest 必填字段与 20 场景
    for key in ("generated_at", "source_run", "pi0_task_count", "videos", "scene_map", "gaps"):
        if key not in manifest:
            fail(f"manifest 缺字段: {key}")
    if manifest.get("pi0_task_count") != 40:
        fail(f"pi0_task_count != 40: {manifest.get('pi0_task_count')}")
    if manifest.get("scene_count") != 20 or manifest.get("scene_order") != list(l90["order"]):
        fail("manifest scene_count / scene_order 与 candidates.json 的 20 场景不一致")
    scene_map = manifest.get("scene_map") or {}
    if set(scene_map) != set(l90["order"]):
        fail("scene_map 的 20 个场景集合不正确")
    for scene in l90["order"]:
        refs = scene_map.get(scene) or []
        if len(refs) < 1:
            fail(f"场景 {scene} 没有视频条目（要求 >=1）")
        if len(refs) > MAX_REFS_PER_SCENE:
            fail(f"场景 {scene} 视频条目 {len(refs)} > {MAX_REFS_PER_SCENE}")
        for r in refs:
            if r.get("kind") not in KINDS:
                fail(f"场景 {scene} 条目 kind 不完整 / 非法: {r.get('kind')!r}")
            if not r.get("why"):
                fail(f"场景 {scene} 条目缺 why: {r.get('file')}")
            if not r.get("file"):
                fail(f"场景 {scene} 条目缺 file")

    # 2) videos 数组：字段 / sha256 / 来源 40 条 / kind / 命名
    videos = manifest.get("videos") or []
    materialized_entries = materialized["entries"]
    if len(videos) != len(materialized_entries):
        fail(f"videos 条数 {len(videos)} != 本次生成 {len(materialized_entries)}")
    files = [v.get("file") for v in videos]
    if len(files) != len(set(files)):
        fail("videos 中存在重复文件名")
    manifest_files = set(files)
    scene_files = {r["file"] for refs in scene_map.values() for r in refs}
    if manifest_files != scene_files:
        fail("videos 与 scene_map 的 file 集合不一致")
    disk_files = {f"videos/{p.name}" for p in VIDEOS_DIR.glob("pi0_*.mp4")}
    if disk_files != manifest_files:
        fail(
            f"videos/ 磁盘文件与 manifest 不一致: 多出 {sorted(disk_files - manifest_files)} "
            f"缺少 {sorted(manifest_files - disk_files)}"
        )
    src_sha_cache: dict[Path, str] = {}
    exact_idx: set[int] = set()
    for v in videos:
        f = v.get("file") or ""
        m = VIDEO_NAME_RE.match(Path(f).name)
        if not m:
            fail(f"视频命名不合规: {f}")
            continue
        path = REPORT / f
        if not path.is_file():
            fail(f"视频文件不存在: {f}")
            continue
        key = (str(v.get("suite")), int(v.get("task_idx", -1)))
        if key not in ev["tasks"]:
            fail(f"视频来源任务不在 evidence.json 的 40 条内: {key}（{f}）")
            continue
        task = ev["tasks"][key]
        if v.get("instruction") != task["instruction"]:
            fail(f"instruction 与 evidence 不一致: {f}")
        if bool(v.get("success")) != bool(task["pi0"]["success"]):
            fail(f"success 与 evidence 不一致: {f}")
        if int(v.get("steps", -1)) != int(task["pi0"]["steps"]):
            fail(f"steps 与 evidence 不一致: {f}")
        if v.get("kind") not in KINDS:
            fail(f"kind 不完整 / 非法: {f}")
        expected_l10_scene = l10["by_idx"][key[1]]["scene"] if key[0] == "LIBERO_10" else None
        if v.get("l10_scene") != expected_l10_scene:
            fail(f"l10_scene 标注不正确: {f} 期望 {expected_l10_scene!r} 实际 {v.get('l10_scene')!r}")
        used = v.get("used_by_l90_scenes") or []
        if len(used) != 1 or used[0] != m.group("scene"):
            fail(f"used_by_l90_scenes 与文件名场景不一致: {f} -> {used}")
        if v.get("kind") == KIND_EXACT:
            if key[0] != "LIBERO_10":
                fail(f"exact_scene_l10 的来源套件必须是 LIBERO_10: {f}")
            if expected_l10_scene != m.group("scene"):
                fail(f"exact_scene_l10 的 L10 场景与 L90 场景不一致: {f}")
            exact_idx.add(key[1])
        if m.group("kind") != v.get("kind"):
            fail(f"文件名 kind 与字段不一致: {f}")
        if m.group("suite") != key[0] or int(m.group("idx")) != key[1]:
            fail(f"文件名 suite/Tidx 与字段不一致: {f}")
        # sha256 / 字节数：清单 == 磁盘 == 原始源视频
        sha = sha256_file(path)
        if sha != v.get("sha256"):
            fail(f"sha256 与清单记录不一致: {f}")
        if path.stat().st_size != int(v.get("bytes", -1)):
            fail(f"bytes 与清单记录不一致: {f}")
        src = ev["videos"][key]
        if src not in src_sha_cache:
            src_sha_cache[src] = sha256_file(src)
        if sha != src_sha_cache[src]:
            fail(f"复制视频与原始源视频 sha256 不一致: {f}")
        if not v.get("honest_note"):
            fail(f"缺 honest_note（诚实标注）: {f}")

    # 3) exact / kind 统计
    kind_counts = manifest.get("kind_counts") or {}
    exact_count = sum(1 for v in videos if v.get("kind") == KIND_EXACT)
    family_count = sum(1 for v in videos if v.get("kind") == KIND_FAMILY)
    if exact_count != 10 or exact_idx != set(range(10)):
        fail(f"exact_scene_l10 应为 10 段且覆盖 LIBERO-10 T0..T9: count={exact_count} idx={sorted(exact_idx)}")
    if kind_counts.get(KIND_EXACT) != exact_count or kind_counts.get(KIND_FAMILY) != family_count:
        fail("kind_counts 与实际 videos 统计不一致")
    if exact_count + family_count != len(videos):
        fail("存在 kind 缺失的视频条目")

    # 4) baseline_tasks：40 条 + 与 videos 一致
    baseline = manifest.get("baseline_tasks") or []
    if len(baseline) != 40:
        fail(f"baseline_tasks 应为 40 条，实际 {len(baseline)}")
    for b in baseline:
        key = (b.get("suite"), b.get("task_idx"))
        if key not in ev["tasks"]:
            fail(f"baseline_tasks 含非 evidence 任务: {key}")
            continue
        if b.get("instruction") != ev["tasks"][key]["instruction"]:
            fail(f"baseline_tasks instruction 不一致: {key}")
        if not (ROOT / b.get("source_video", "")).is_file():
            fail(f"baseline_tasks.source_video 不存在: {b.get('source_video')}")
        for cf in b.get("copied_files") or []:
            if cf not in manifest_files:
                fail(f"baseline_tasks.copied_files 不在 videos 中: {cf}")

    # 5) 关键不变量：本工作区没有 L90 视频（否则本清单口径失效，必须改用实测 baseline）
    if scan["l90_identified_mp4_count"] != 0:
        fail(
            "工作区出现 LIBERO-90 视频（"
            f"{scan['l90_identified_mp4_count']} 个，例: {scan['l90_identified_mp4'][:3]}）——"
            "本清单是参考视频口径，必须改用 L90 实测 baseline 后重跑"
        )
    if scan["dirs_named_libero_90"]:
        fail(f"工作区出现名为 libero_90 的目录: {scan['dirs_named_libero_90']}")
    if scan["l90_task_config_dirs_in_workspace"]:
        fail(f"工作区出现 LIBERO_90 运行时任务配置目录: {scan['l90_task_config_dirs_in_workspace']}")
    if scan["pi0_videos_under_run_pi0"] != 40:
        fail(f"run/pi0 下 pi0 视频应为 40 段，实际 {scan['pi0_videos_under_run_pi0']}")
    pi0_suites = sorted(p.name for p in (RUN / "run/pi0").iterdir() if p.is_dir())
    if pi0_suites != sorted(SUITE_DIR[s] for s in SUITE_ORDER):
        fail(f"run/pi0 套件目录不是 4 个标准套件: {pi0_suites}")
    for suite in SUITE_ORDER:
        n = len(list((RUN / "run/pi0" / SUITE_DIR[suite]).rglob("*.mp4")))
        if n != 10:
            fail(f"{suite} 的 pi0 视频应为 10 段，实际 {n}")

    # 6) VIDEO_SOURCES.md：存在、<= 60 行、关键口径齐全
    if not SOURCES_MD.is_file():
        fail("VIDEO_SOURCES.md 不存在")
    else:
        md = SOURCES_MD.read_text(encoding="utf-8")
        n_lines = len(md.rstrip("\n").splitlines())
        if n_lines > 60:
            fail(f"VIDEO_SOURCES.md 行数 {n_lines} > 60")
        for needle in (KIND_EXACT, KIND_FAMILY, "不是", "没有 LIBERO-90", "补录"):
            if needle not in md:
                fail(f"VIDEO_SOURCES.md 缺少关键内容: {needle!r}")

    # 7) gaps 必须有
    if not manifest.get("gaps"):
        fail("manifest.gaps 为空")
    return errors


# ════════════════════════════════════════════════
# main
# ════════════════════════════════════════════════


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="生成 LIBERO-90 分场景报告的 pi0 参考视频清单与视频资产（静态、可重跑）"
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="生成后执行全量校验（20 场景 >=1、sha256、来源 40 条、kind、重名、无 L90 视频等）",
    )
    args = ap.parse_args(argv)

    print("[build] LIBERO-90 分场景报告：pi0 baseline 参考视频清单")
    ev = load_evidence()
    l10 = load_l10_tasks(ev)
    l90 = load_l90_scenes()
    print(
        f"[build] evidence: {len(ev['tasks'])} 条 pi0 任务，success={ev['success_count']}/40，"
        f"suites={ev['suites']}"
    )
    print(
        "[build] L10 task_idx -> scene: "
        + ", ".join(f"T{i}={l10['by_idx'][i]['scene']}" for i in range(10))
    )
    selection = build_selection(ev, l10, l90)
    materialized = materialize(ev, selection)
    scan = scan_workspace()
    manifest = build_manifest(ev, l10, l90, selection, materialized, scan)
    dump_json(MANIFEST, manifest)
    write_text(SOURCES_MD, render_video_sources_md(manifest))
    kind_counts = manifest["kind_counts"]
    print(
        f"[build] scenes={manifest['scene_count']} videos={manifest['video_count']} "
        f"(exact={kind_counts[KIND_EXACT]}, family={kind_counts[KIND_FAMILY]}) "
        f"unique_sources={manifest['unique_source_video_count']} "
        f"copies_new={materialized['copies_new']} stale_removed={materialized['stale_removed']}"
    )
    print(f"[build] wrote {rel(MANIFEST)}")
    print(f"[build] wrote {rel(SOURCES_MD)}")
    print(f"[build] wrote {rel(VIDEOS_DIR)}/（{len(materialized['expected'])} 个 mp4）")
    print(
        f"[build] no-L90 scan: runs/ mp4={scan['mp4_total_under_runs']} "
        f"L90标识mp4={scan['l90_identified_mp4_count']} "
        f"L90配置目录={len(scan['l90_task_config_dirs_in_workspace'])} "
        f"run/pi0 视频={scan['pi0_videos_under_run_pi0']} "
        f"历史L90 run 目录存在={len(scan['historical_l90_run_dirs_present'])}/"
        f"{len(scan['historical_l90_run_dirs_from_docs'])}"
    )

    if not args.check:
        return 0

    errors = check(ev, l10, l90, selection, materialized, manifest, scan)
    if errors:
        for err in errors:
            print(f"[check] FAIL {err}")
        print(f"[check] FAILED: {len(errors)} 个问题")
        return 1
    print(
        f"[check] PASS 20/20 场景；{manifest['video_count']} 段视频"
        f"（{kind_counts[KIND_EXACT]} exact_scene_l10 + {kind_counts[KIND_FAMILY]} suite_family_reference）；"
        f"{manifest['unique_source_video_count']} 个源视频 sha256 全部一致；"
        "来源任务均在 evidence.json 的 40 条内；无重名；本工作区无 L90 视频；VIDEO_SOURCES.md <= 60 行"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())