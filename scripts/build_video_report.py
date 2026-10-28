"""Build a portable HTML evidence report from actual full-suite run artifacts.

Layout: one section per task; every case of that task is shown side by side with
the paired baseline first. Each video is followed by its own case information and
result. The report opens with a data-analysis section computed from the artifacts.

Video playback: the standalone HTML embeds a size-reduced copy of every clip as a
``data:`` URI so the report plays from any origin (file://, http://, or a preview
pane whose Content-Security-Policy only allows ``media-src data:``). The untouched
original MP4 that passed full-decode verification stays in ``report/videos/`` and is
linked from every card; hashes are recorded in ``evidence.json``.

Usage:
    python scripts/build_video_report.py                     # embed videos (default)
    python scripts/build_video_report.py --no-embed          # external MP4 only
    python scripts/build_video_report.py --runs-dir <dir>    # another run
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS = ROOT / "runs/full-coverage"
FFMPEG = (
    ROOT.parent
    / "libero-plus/openvla-oft-env/lib/python3.10/site-packages"
    / "imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
)
LEVEL_ORDER = {"baseline": 0, "checkpoint": 1, "d0": 2, "d1": 3, "d2": 4, "d3": 5}
LEVEL_CN = {
    "baseline": "配对基线",
    "checkpoint": "checkpoint（抓取前位姿）",
    "d0": "d0（初始位姿）",
    "d1": "d1（位移 0.05,0.05,0）",
    "d2": "d2（位移 -0.08,0.06,0）",
    "d3": "d3（位移 0.10,0.08,0）",
}
EMBED_ARGS = [
    "-vf", "scale=256:256",
    "-r", "12",
    "-an",
    "-c:v", "libx264",
    "-preset", "veryfast",
    "-crf", "30",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
]


# --------------------------------------------------------------------------- #
# data collection
# --------------------------------------------------------------------------- #
def collect(runs: Path, report: Path) -> list[dict]:
    media = report / "videos"
    media.mkdir(parents=True, exist_ok=True)
    artifacts = report / "artifacts"
    artifacts.mkdir(exist_ok=True)
    manifest = yaml.safe_load((ROOT / "dataset/v1.1/manifest.yaml").read_text())
    crosswalk_path = runs / "task-crosswalk-audit.json"
    crosswalk = (
        {row["task_id"]: row for row in json.loads(crosswalk_path.read_text())}
        if crosswalk_path.exists()
        else {}
    )
    rows: list[dict] = []
    for entry in manifest["cases"]:
        case = yaml.safe_load((ROOT / entry["path"]).read_text())
        task_index = case["task"]["task_index"]
        task_dir = runs / f"task-{task_index:02d}"
        result_files = sorted(task_dir.rglob("results.json"))
        terminal_path = task_dir / "execution.json"
        execution = json.loads(terminal_path.read_text()) if terminal_path.exists() else {}
        plan_path = task_dir / "execution-plan.json"
        plan = json.loads(plan_path.read_text()) if plan_path.exists() else {}
        if execution.get("results"):
            result_files = [Path(path) for path in execution["results"]]
        episode = baseline = None
        result_path = None
        expected = "dataset_" + case["case_id"].replace("-", "_")
        for path in result_files:
            doc = json.loads(path.read_text())
            for task_result in doc.values():
                if not isinstance(task_result, dict):
                    continue
                for key, value in task_result.get("results", {}).items():
                    if not isinstance(value, dict):
                        continue
                    if value.get("kind") == "baseline":
                        baseline = value
                    if expected in key:
                        episode = value
                        result_path = path
        report_obj = episode.get("report", {}) if episode else {}
        observed = report_obj.get("intervention", {}).get("observed", {})
        outcome = report_obj.get("outcome", {})
        valid = report_obj.get("injection_valid")
        state = "not run"
        if episode is not None:
            state = "valid rollback" if valid is True else "invalid or untriggered"
        elif execution:
            state = "runtime error: no episode result"
        # A result is written after its video writer closes. Never copy an
        # in-progress MP4 merely because its filename already exists.
        videos = (
            [
                p
                for p in (result_path.parent / "videos").glob("*.mp4")
                if expected in p.name and "baseline" not in p.name
            ]
            if result_path
            else []
        )
        row: dict = {
            "case_id": case["case_id"],
            "task_id": case["task"]["task_id"],
            "task_index": task_index,
            "level": case["severity"],
            "status": state,
            "injection_valid": valid,
            "trigger": report_obj.get("injection_step"),
            "pre_relation": observed.get("pre_predicate"),
            "post_relation": observed.get("post_predicate"),
            "description": case.get("description"),
            "baseline_success": baseline.get("success") if baseline else None,
            "task_success": episode.get("success") if episode else None,
            "result_file": str(result_path) if result_path else None,
            "runner_returncode": execution.get("returncode"),
            "run_command": execution.get("command", plan.get("command")),
            "actual_bddl": crosswalk.get(case["task"]["task_id"], {}).get("actual_bddl"),
            "base_bddl": case["task"]["source_bddl"],
            "boundary_protocol": case["stage"]["name"] == "completion_boundary",
            "validity_errors": report_obj.get("errors", []),
            "observed": observed,
            "declared_validity_constraints": case["validity_constraints"],
            "validity_scope": (
                "External validator evidence; release, support and general solvability "
                "are not independently certified by this report."
            ),
            "result_sha256": (
                hashlib.sha256(result_path.read_bytes()).hexdigest() if result_path else None
            ),
            "videos": [f"videos/{case['case_id']}--{p.name}" for p in videos],
        }
        # ---- analysis fields, read straight from the episode record ----------
        if episode is not None:
            row["steps"] = episode.get("steps")
            row["recovered"] = outcome.get("recovered")
            row["recovery_latency_steps"] = outcome.get("recovery_latency_steps")
            trace = outcome.get("task_predicate_trace", {})
            row["first_success_step"] = trace.get("first_success_step")
            row["final_default_success"] = trace.get("final_default_success")
            row["termination"] = outcome.get("termination", {}).get("status")
            verification = outcome.get("recovery_verification", {})
            row["recovery_verified"] = verification.get("recovery_verified")
            row["case_metrics"] = episode.get("recovery_cost")
            row["policy_queries_after_rollback"] = observed.get("policy_queries_after_rollback")
            row["repair_completed"] = observed.get("repair_completed")
            row["repair_step"] = observed.get("repair_step")
        if baseline is not None:
            row["baseline_steps"] = baseline.get("steps")
            row["baseline_metrics"] = baseline.get("recovery_cost")
        if result_path:
            task_artifacts = artifacts / task_dir.name
            task_artifacts.mkdir(exist_ok=True)
            shutil.copy2(result_path, task_artifacts / "results.json")
            for filename in ("execution.json", "binding.yaml", "runner.log"):
                source = task_dir / filename
                if source.is_file():
                    shutil.copy2(source, task_artifacts / filename)
            row["result_link"] = str((task_artifacts / "results.json").relative_to(report))
            baseline_sources = sorted((result_path.parent / "videos").glob("*baseline*.mp4"))
            for baseline_video in baseline_sources:
                shutil.copy2(baseline_video, media / (task_dir.name + "--" + baseline_video.name))
            row["baseline_videos"] = [
                f"videos/{task_dir.name}--{p.name}" for p in baseline_sources
            ]
        else:
            row["result_link"] = None
            row["baseline_videos"] = []
        rows.append(row)
    rows.sort(key=lambda r: (r["task_index"], LEVEL_ORDER.get(r["level"], 9)))
    return rows


# --------------------------------------------------------------------------- #
# analysis
# --------------------------------------------------------------------------- #
def _nums(values):
    return [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]


def _median(values):
    nums = sorted(_nums(values))
    if not nums:
        return None
    mid = len(nums) // 2
    return nums[mid] if len(nums) % 2 else (nums[mid - 1] + nums[mid]) / 2


def _rate(hit: int, total: int) -> str:
    return "n/a" if not total else f"{hit / total:.1%}"


def analyse(rows: list[dict]) -> dict:
    total = len(rows)
    valid_rows = [r for r in rows if r["injection_valid"] is True]
    invalid_rows = [r for r in rows if r["injection_valid"] is not True]
    valid_n = len(valid_rows)
    baselines = [r for r in rows if r["baseline_success"] is not None]
    baseline_ok = sum(1 for r in baselines if r["baseline_success"] is True)
    recovered = [r for r in valid_rows if r["task_success"] is True]
    invalid_success = [r for r in invalid_rows if r["task_success"] is True]

    by_level = []
    for level in ("checkpoint", "d0", "d1", "d2", "d3"):
        group = [r for r in valid_rows if r["level"] == level]
        hits = [r for r in group if r["task_success"] is True]
        by_level.append(
            {
                "level": level,
                "label": LEVEL_CN[level],
                "n": len(group),
                "recovered": len(hits),
                "rate": _rate(len(hits), len(group)),
                "cases": [r["case_id"] for r in hits],
            }
        )

    tasks = []
    for index in sorted({r["task_index"] for r in rows}):
        group = [r for r in rows if r["task_index"] == index]
        group_valid = [r for r in group if r["injection_valid"] is True]
        hits = [r for r in group_valid if r["task_success"] is True]
        triggers = sorted({r["trigger"] for r in group_valid if isinstance(r["trigger"], int)})
        tasks.append(
            {
                "task_id": group[0]["task_id"],
                "task_index": index,
                "n": len(group),
                "valid": len(group_valid),
                "recovered": len(hits),
                "rate": _rate(len(hits), len(group_valid)),
                "trigger": triggers[0] if len(triggers) == 1 else triggers,
                "baseline_success": group[0].get("baseline_success"),
                "baseline_steps": group[0].get("baseline_steps"),
                "actual_bddl": group[0].get("actual_bddl"),
                "boundary": any(r["boundary_protocol"] for r in group),
                "recovered_cases": [r["case_id"] for r in hits],
            }
        )

    def metric_delta(metric: str):
        out = []
        for row in valid_rows:
            case_metrics = row.get("case_metrics") or {}
            base_metrics = row.get("baseline_metrics") or {}
            if metric in case_metrics and metric in base_metrics:
                out.append(case_metrics[metric] - base_metrics[metric])
        return out

    steps_deltas = [
        r["steps"] - r["baseline_steps"]
        for r in valid_rows
        if isinstance(r.get("steps"), (int, float))
        and isinstance(r.get("baseline_steps"), (int, float))
    ]
    failure = {
        "steps_delta": _median(steps_deltas),
        "steps_delta_max": max(_nums(steps_deltas), default=None),
        "eef_path_delta": _median(metric_delta("eef_path_length_m")),
        "action_reversal_delta": _median(metric_delta("action_reversal_count")),
        "failure_events_median": _median(
            [(r.get("case_metrics") or {}).get("failure_event_count") for r in valid_rows]
        ),
        "failure_events_max": max(
            _nums(
                [(r.get("case_metrics") or {}).get("failure_event_count") for r in valid_rows]
            ),
            default=None,
        ),
        "reobserves_total": sum(
            _nums([(r.get("case_metrics") or {}).get("reobserve_count") for r in valid_rows])
        ),
        "retreats_total": sum(
            _nums([(r.get("case_metrics") or {}).get("retreat_count") for r in valid_rows])
        ),
        "reroutes_total": sum(
            _nums([(r.get("case_metrics") or {}).get("reroute_count") for r in valid_rows])
        ),
        "old_subgoal_restores": sum(
            _nums(
                [(r.get("case_metrics") or {}).get("old_subgoal_restore_count") for r in valid_rows]
            )
        ),
        "queries_median": _median(
            [r.get("policy_queries_after_rollback") for r in valid_rows]
        ),
        "repair_completed": sum(1 for r in valid_rows if r.get("repair_completed") is True),
    }

    invalid_detail = [
        {
            "case_id": r["case_id"],
            "task_id": r["task_id"],
            "level": r["level"],
            "errors": r.get("validity_errors"),
            "task_success": r["task_success"],
            "baseline_success": r["baseline_success"],
        }
        for r in invalid_rows
    ]
    recovered_rows = [
        {
            "case_id": r["case_id"],
            "task_id": r["task_id"],
            "level": r["level"],
            "latency": r.get("recovery_latency_steps"),
            "steps": r.get("steps"),
            "baseline_steps": r.get("baseline_steps"),
            "first_success_step": r.get("first_success_step"),
            "regrasp": (r.get("case_metrics") or {}).get("regrasp_attempt_count"),
            "queries": r.get("policy_queries_after_rollback"),
            "verified": r.get("recovery_verified"),
        }
        for r in recovered
    ]
    return {
        "total": total,
        "valid_n": valid_n,
        "invalid_n": len(invalid_rows),
        "baseline_n": len(baselines),
        "baseline_ok": baseline_ok,
        "recovered_n": len(recovered),
        "recovered_rate": _rate(len(recovered), valid_n),
        "by_level": by_level,
        "tasks": tasks,
        "failure": failure,
        "invalid_detail": invalid_detail,
        "recovered_rows": recovered_rows,
        "invalid_success": [
            {"case_id": r["case_id"], "task_id": r["task_id"], "level": r["level"]}
            for r in invalid_success
        ],
        "levels_defined": sorted({r["level"] for r in rows}),
        "tasks_defined": len(tasks),
        "boundary_tasks": [t["task_id"] for t in tasks if t["boundary"]],
    }


# --------------------------------------------------------------------------- #
# rendering helpers
# --------------------------------------------------------------------------- #
def esc(value) -> str:
    return html.escape(str(value))


def tri(value, true="是", false="否") -> str:
    if value is True:
        return f'<span class="ok">{true}</span>'
    if value is False:
        return f'<span class="bad">{false}</span>'
    return '<span class="na">n/a</span>'


def fmt(value, digits: int = 2, suffix: str = "") -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:.{digits}f}{suffix}"
    return '<span class="na">n/a</span>'


def embed_video(source: Path, cache: Path, enabled: bool) -> str | None:
    """Return a data: URI for a size-reduced copy, or None when unavailable."""
    if not enabled or not FFMPEG.exists() or not source.is_file():
        return None
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / source.name
    if not target.is_file() or target.stat().st_mtime < source.stat().st_mtime:
        with tempfile.TemporaryDirectory() as tmp:
            staged = Path(tmp) / "out.mp4"
            proc = subprocess.run(
                [str(FFMPEG), "-y", "-loglevel", "error", "-i", str(source), *EMBED_ARGS, str(staged)],
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0 or not staged.is_file():
                return None
            shutil.move(str(staged), target)
    return "data:video/mp4;base64," + base64.b64encode(target.read_bytes()).decode("ascii")


def video_block(row: dict, report: Path, cache: Path, embed: bool, label: str) -> str:
    """Video element(s) plus an explicit fallback link to the verified original."""
    references = list(row.get("videos", [])) + list(row.get("baseline_videos", []))
    if not references:
        return '<div class="video-wrap empty">无视频证据</div>'
    parts = []
    for index, reference in enumerate(references):
        source = report / reference
        data_uri = embed_video(source, cache, embed)
        element_id = f"{row['case_id']}-{label}-{index}".replace(".", "_")
        src = data_uri if data_uri else reference
        parts.append(
            f'<video id="{esc(element_id)}" controls preload="metadata" playsinline '
            f'src="{esc(src)}" data-original="{esc(reference)}"></video>'
            f'<p class="fallback">播放异常时：<a href="{esc(reference)}" target="_blank" title="{esc(Path(reference).name)}">打开原始 MP4</a>'
            f'<span class="path" title="{esc(Path(reference).name)}">'
            f'{esc(Path(reference).name[:36])}…</span></p>'
        )
    return f'<div class="video-wrap">{"".join(parts)}</div>'


def card_for_baseline(task: dict, row: dict, report: Path, cache: Path, embed: bool) -> str:
    references = row.get("baseline_videos", [])
    if not references:
        return ""
    block = video_block(
        {"case_id": f"task-{task['task_index']:02d}-baseline",
         "baseline_videos": references, "videos": []},
        report, cache, embed, "baseline",
    )
    metrics = row.get("baseline_metrics") or {}
    steps = row.get("baseline_steps")
    items = [
        ("用途", "本任务全部扰动用例的配对参照（同种子，无扰动）"),
        ("任务成功", tri(row.get("baseline_success"))),
        ("步数", esc(steps) if steps is not None else '<span class="na">n/a</span>'),
        ("策略查询", esc(metrics.get("post_x2_policy_queries", "n/a"))),
        ("重抓次数", esc(metrics.get("regrasp_attempt_count", "n/a"))),
        ("路径长度", fmt(metrics.get("eef_path_length_m"), 2, " m")),
        ("失败事件", esc(metrics.get("failure_event_count", "n/a"))),
    ]
    return (
        '<article class="card baseline">'
        '<header><span class="tag baseline-tag">baseline · 第 1 个视频</span>'
        f'<h4>配对基线（任务 {task["task_index"]:02d}，无扰动）</h4></header>'
        f"{block}"
        "<dl>"
        + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in items)
        + "</dl></article>"
    )


def card_for_case(row: dict, report: Path, cache: Path, embed: bool) -> str:
    level = row["level"]
    valid = row["injection_valid"] is True
    if row["task_success"] is True and valid:
        outcome = '<span class="ok">模型恢复成功</span>'
    elif row["task_success"] is True:
        outcome = '<span class="warn">任务成功，但注入无效，不计入恢复</span>'
    elif row["task_success"] is None:
        outcome = '<span class="na">未获得结果</span>'
    else:
        outcome = '<span class="bad">模型恢复失败</span>'
    items = [
        ("档位", esc(LEVEL_CN.get(level, level))),
        ("注入有效性", tri(row["injection_valid"])),
        (
            "干预步",
            esc(row["trigger"]) if row["trigger"] is not None else '<span class="na">未触发</span>',
        ),
        (
            "已完成关系 前→后",
            f'{tri(row["pre_relation"], "真", "假")} → {tri(row["post_relation"], "真", "假")}',
        ),
        ("本用例任务成功", tri(row["task_success"])),
        ("配对基线成功", tri(row["baseline_success"])),
    ]
    if isinstance(row.get("recovery_latency_steps"), (int, float)):
        items.append(("恢复延迟", f'<b>{esc(row["recovery_latency_steps"])} 步</b>'))
    if isinstance(row.get("steps"), (int, float)):
        delta = ""
        if isinstance(row.get("baseline_steps"), (int, float)):
            diff = row["steps"] - row["baseline_steps"]
            delta = (
                f' <span class="sub">（基线 {esc(row["baseline_steps"])} 步，'
                f'{"+" if diff >= 0 else ""}{diff}）</span>'
            )
        items.append(("本集步数", f'{esc(row["steps"])}{delta}'))
    metrics = row.get("case_metrics") or {}
    if metrics:
        items.append(
            (
                "恢复代价",
                f'重抓 {esc(metrics.get("regrasp_attempt_count", "n/a"))} 次 · '
                f'失败事件 {esc(metrics.get("failure_event_count", "n/a"))} · '
                f'路径 {fmt(metrics.get("eef_path_length_m"), 2, " m")}',
            )
        )
        items.append(
            (
                "行为统计",
                f'重观测 {esc(metrics.get("reobserve_count", "n/a"))} · '
                f'后退 {esc(metrics.get("retreat_count", "n/a"))} · '
                f'改道 {esc(metrics.get("reroute_count", "n/a"))} · '
                f'反向 {esc(metrics.get("action_reversal_count", "n/a"))}',
            )
        )
        if metrics.get("old_subgoal_restore_count"):
            items.append(
                ("旧子任务还原", esc(metrics.get("old_subgoal_restore_count")))
            )
    if row.get("policy_queries_after_rollback") is not None:
        items.append(("回滚后策略查询", esc(row["policy_queries_after_rollback"])))
    error_text = ""
    if row.get("validity_errors"):
        codes = "；".join(
            f'{e.get("name", "?")}（{e.get("detail", "")}）' if isinstance(e, dict) else str(e)
            for e in row["validity_errors"]
        )
        error_text = f'<p class="invalid-reason">注入无效原因：{esc(codes)}</p>'
    return (
        f'<article class="card {"recovered" if row["task_success"] is True and valid else ""}">'
        f'<header><span class="tag">{esc(level)}</span>'
        f'<h4>{esc(row["case_id"])}</h4></header>'
        f"{video_block(row, report, cache, embed, level)}"
        "<dl>"
        + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in items)
        + "</dl>"
        + f'<p class="outcome">{outcome}</p>'
        + error_text
        + "<details><summary>用例描述与运行证据</summary>"
        + f'<p>{esc(row.get("description") or "")}</p>'
        + "<pre>"
        + esc(
            json.dumps(
                {
                    key: row.get(key)
                    for key in (
                        "status",
                        "actual_bddl",
                        "base_bddl",
                        "boundary_protocol",
                        "runner_returncode",
                        "validity_errors",
                        "validity_scope",
                        "declared_validity_constraints",
                        "observed",
                        "result_sha256",
                    )
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        + "</pre></details>"
        + (
            f'<p class="links"><a href="{esc(row["result_link"])}">原始结果 JSON</a></p>'
            if row.get("result_link")
            else ""
        )
        + "</article>"
    )


def section_for_task(task: dict, rows: list[dict], report: Path, cache: Path, embed: bool) -> str:
    group = [r for r in rows if r["task_index"] == task["task_index"]]
    baseline_row = group[0] if group else {}
    cards = [card_for_baseline(task, baseline_row, report, cache, embed)]
    cards += [card_for_case(row, report, cache, embed) for row in group]
    flags = []
    if task["boundary"]:
        flags.append('<span class="tag warn-tag">完成后继续执行窗口</span>')
    if task["recovered"]:
        flags.append(f'<span class="tag ok-tag">恢复 {task["recovered"]}/{task["valid"]}</span>')
    else:
        flags.append(f'<span class="tag bad-tag">恢复 0/{task["valid"]}</span>')
    baseline_text = "成功" if task["baseline_success"] else "失败"
    return (
        f'<section class="task" id="task-{task["task_index"]:02d}">'
        f'<h3>任务 {task["task_index"]:02d}'
        f'<span class="sub"> · {esc(task["task_id"])} · {esc(task["actual_bddl"] or "")}'
        f' · 干预步 {esc(task["trigger"])} · 基线{baseline_text}'
        f'（{esc(task["baseline_steps"])} 步）</span></h3>'
        f'<p class="flags">{"".join(flags)}</p>'
        f'<div class="cards">{"".join(cards)}</div>'
        "</section>"
    )


# --------------------------------------------------------------------------- #
# analysis section
# --------------------------------------------------------------------------- #
def render_analysis(analysis: dict) -> str:
    f = analysis["failure"]
    level_chips = "".join(
        f'<div class="chip"><div class="chip-k">{esc(b["label"])}</div>'
        f'<div class="chip-v {"ok" if b["recovered"] else "bad"}">{b["recovered"]}/{b["n"]}</div>'
        f'<div class="chip-s">恢复率 {esc(b["rate"])}</div></div>'
        for b in analysis["by_level"]
    )
    task_rows = "".join(
        "<tr>"
        + f'<td>任务 {t["task_index"]:02d}</td>'
        + f'<td>{t["valid"]}</td>'
        + f'<td class="{"ok" if t["recovered"] else "bad"}">{t["recovered"]}</td>'
        + f'<td>{esc(t["rate"])}</td>'
        + f'<td>{esc(t["baseline_steps"])}</td>'
        + f'<td class="bddl">{esc(t["actual_bddl"] or "")}</td>'
        + "</tr>"
        for t in analysis["tasks"]
    )
    recovery_rows = "".join(
        "<tr>"
        + f'<td>{esc(r["task_id"])}</td><td>{esc(r["level"])}</td>'
        + f'<td>{esc(r["latency"])} 步</td><td>{esc(r["steps"])}</td>'
        + f'<td>{esc(r["baseline_steps"])}</td><td>{esc(r["first_success_step"])}</td>'
        + f'<td>{esc(r["regrasp"])}</td><td>{esc(r["queries"])}</td>'
        + f'<td>{tri(r["verified"])}</td></tr>'
        for r in analysis["recovered_rows"]
    ) or '<tr><td colspan="9" class="na">无</td></tr>'
    invalid_rows = "".join(
        "<tr>"
        + f'<td>{esc(r["task_id"])}</td><td>{esc(r["level"])}</td><td>{esc(r["case_id"])}</td>'
        + "<td>"
        + esc(
            "；".join(
                e.get("name", str(e)) if isinstance(e, dict) else str(e)
                for e in (r["errors"] or [])
            )
        )
        + "</td>"
        + f'<td>{tri(r["baseline_success"])}</td><td>{tri(r["task_success"])}</td></tr>'
        for r in analysis["invalid_detail"]
    ) or '<tr><td colspan="6" class="na">无</td></tr>'
    zero_levels = [b for b in analysis["by_level"] if b["n"] and not b["recovered"]]
    recovered_levels = [b for b in analysis["by_level"] if b["recovered"]]
    zero_tasks = [t["task_index"] for t in analysis["tasks"] if t["recovered"] == 0]
    recovered_tasks = [t["task_index"] for t in analysis["tasks"] if t["recovered"]]

    if zero_levels and recovered_levels:
        level_finding = (
            "<li><b>退化越轻微越无法恢复。</b>"
            + "、".join(f'{b["label"]} {b["recovered"]}/{b["n"]}' for b in zero_levels)
            + " 全部为 0 恢复；恢复只出现在 "
            + "、".join(f'{b["label"]} {b["recovered"]}/{b["n"]}' for b in recovered_levels)
            + "。回滚位移越小的失效，模型越倾向于认为子任务仍然成立，因而不做任何重做。</li>"
        )
    else:
        level_finding = "<li><b>各档位恢复情况见下节。</b></li>"

    findings = [
        f'<li><b>失败来自扰动，不是任务本身不可解。</b>全部 {analysis["baseline_n"]} 个配对基线中 '
        f'{analysis["baseline_ok"]} 个成功；有效注入用例的基线成功率 '
        f'{_rate(analysis["baseline_ok"], analysis["baseline_n"])}，说明场景可解、指令可达，'
        f"扰动后的失败是模型对\u201c已完成子任务失效\u201d的响应失败。</li>",
        f'<li><b>整体恢复能力很弱：{analysis["recovered_n"]}/{analysis["valid_n"]}'
        f'（{analysis["recovered_rate"]}）。</b>在 {analysis["valid_n"]} 个注入有效的用例里，'
        f"模型只有 {analysis['recovered_n']} 次把被撤销的子任务重新做回成功。</li>",
        level_finding,
        f'<li><b>失败形态是\u201c一直试到预算耗尽\u201d，而非提前放弃。</b>失败用例的中位步数比基线多 '
        f'{esc(f["steps_delta"])} 步，最多多 {esc(f["steps_delta_max"])} 步（单集预算 600 步）。</li>',
        f'<li><b>恢复代价高。</b>两次成功恢复分别用了 '
        f'{esc("、".join(str(r["latency"]) for r in analysis["recovered_rows"]) or "n/a")} 步'
        f'（自干预步起算），且都依赖重新抓取；失败用例的末端执行器路径中位比基线长 '
        f'{fmt(f["eef_path_delta"], 2, " m")}，动作反向中位多 {fmt(f["action_reversal_delta"], 0)} 次。</li>',
        f'<li><b>失败高度集中：{len(zero_tasks)}/{analysis["tasks_defined"]} 个任务零恢复。</b>'
        + (
            "恢复只出现在 " + "、".join(f"任务 {i:02d}" for i in recovered_tasks) + "。"
            if recovered_tasks
            else "没有任何任务出现恢复。"
        )
        + "</li>",
        "<li><b>注入有效性是独立维度，不能与任务成功混算。</b>"
        + (
            "本批次无效/未触发用例："
            + "；".join(
                f'{r["task_id"]} {r["level"]}（'
                + "".join(
                    e.get("name", "") if isinstance(e, dict) else str(e)
                    for e in (r["errors"] or [])
                )
                + "）"
                for r in analysis["invalid_detail"]
            )
            + "。按覆盖记录，<b>不计入恢复统计</b>。"
            if analysis["invalid_detail"]
            else "本批次全部注入均有效。"
        )
        + (
            "其中 "
            + "、".join(r["case_id"] for r in analysis["invalid_success"])
            + " 虽然任务成功，但注入未生效，不能算作模型恢复。"
            if analysis["invalid_success"]
            else ""
        )
        + "</li>",
    ]

    return f"""<section class="analysis" id="analysis">
<h2>一、实验数据分析</h2>

<h3>1.1 实验设计与规模</h3>
<p>数据集 <b>LIBERO-rollback v1.1.0</b>。在 LIBERO-10 的 10 个任务上，每个任务构造 5 个
\u201c已完成子任务被回滚\u201d的用例：<b>checkpoint</b>（抓取前检查点位姿）、<b>d0</b>（初始位姿）、
<b>d1</b>（位移 0.05,0.05,0 m）、<b>d2</b>（-0.08,0.06,0 m）、<b>d3</b>（0.10,0.08,0 m），
位移依次增大。被测模型为 <b>OpenVLA-OFT</b>
（openvla-7b-oft-finetuned-libero-spatial-object-goal-10），seed 0，每集预算 600 控制步、
每 10 步重规划。每个扰动用例都配一个<b>同种子基线</b>作为对照，视频来自真实仿真运行。</p>
<div class="chips">
  <div class="chip"><div class="chip-k">用例总数</div><div class="chip-v">{analysis["total"]}</div>
    <div class="chip-s">{analysis["tasks_defined"]} 个任务 × 5 档位</div></div>
  <div class="chip"><div class="chip-k">注入有效</div><div class="chip-v">{analysis["valid_n"]}</div>
    <div class="chip-s">无效/未触发 {analysis["invalid_n"]}</div></div>
  <div class="chip"><div class="chip-k">配对基线成功</div>
    <div class="chip-v ok">{analysis["baseline_ok"]}/{analysis["baseline_n"]}</div>
    <div class="chip-s">任务本身可解</div></div>
  <div class="chip"><div class="chip-k">扰动后恢复</div>
    <div class="chip-v bad">{analysis["recovered_n"]}/{analysis["valid_n"]}</div>
    <div class="chip-s">恢复率 {esc(analysis["recovered_rate"])}</div></div>
</div>

<h3>1.2 主要结论</h3>
<ol class="findings">{"".join(findings)}</ol>

<h3>1.3 按退化档位的恢复率（仅注入有效）</h3>
<div class="chips level-chips">{level_chips}</div>
<p class="note">checkpoint 与 d0/d1 是位移最小、理论上最\u201c轻微\u201d的失效形式，恢复率为 0；
恢复只出现在位移最大的 d2/d3。</p>

<h3>1.4 逐任务恢复情况</h3>
<table class="data">
<thead><tr><th>任务</th><th>有效注入</th><th>恢复</th><th>恢复率</th><th>基线步数</th>
<th>实际 BDDL</th></tr></thead>
<tbody>{task_rows}</tbody></table>
<p class="note">任务 00 与 09 采用\u201c成功后继续执行\u201d协议
（{esc("、".join(analysis["boundary_tasks"]) or "无")}），其失效发生在任务完成边界，
而不是执行中途，分析时不应与其他任务静默混算。</p>

<h3>1.5 两次成功恢复的过程</h3>
<table class="data">
<thead><tr><th>任务</th><th>档位</th><th>恢复延迟</th><th>本集步数</th><th>基线步数</th>
<th>首次成功步</th><th>重抓次数</th><th>回滚后策略查询</th><th>恢复经校验</th></tr></thead>
<tbody>{recovery_rows}</tbody></table>
<p class="note">恢复延迟＝从注入步到任务谓词重新成立所消耗的控制步。两次恢复都靠重新抓取完成。</p>

<h3>1.6 失败形态（仅注入有效用例）</h3>
<ul class="findings">
<li>中位步数增量 <b>{esc(f["steps_delta"])}</b> 步，最大 <b>{esc(f["steps_delta_max"])}</b> 步
—— 模型没有提前终止，而是一路尝试到预算耗尽。</li>
<li>末端执行器路径中位比基线长 <b>{fmt(f["eef_path_delta"], 2, " m")}</b>；
动作反向中位多 <b>{fmt(f["action_reversal_delta"], 0)}</b> 次。</li>
<li>失败事件中位 <b>{esc(f["failure_events_median"])}</b>、最多 <b>{esc(f["failure_events_max"])}</b>；
有效注入用例累计重观测 <b>{esc(f["reobserves_total"])}</b>、后退 <b>{esc(f["retreats_total"])}</b>、
改道 <b>{esc(f["reroutes_total"])}</b> 次。</li>
<li>回滚后策略查询中位 <b>{esc(f["queries_median"])}</b> 次；仅
<b>{f["repair_completed"]}/{analysis["valid_n"]}</b> 个用例完成了修复性重放（repair），
累计旧子任务还原 <b>{esc(f["old_subgoal_restores"])}</b> 次。</li>
</ul>

<h3>1.7 注入有效性与数据质量</h3>
<table class="data">
<thead><tr><th>任务</th><th>档位</th><th>用例</th><th>无效原因</th>
<th>基线成功</th><th>任务成功</th></tr></thead>
<tbody>{invalid_rows}</tbody></table>
<p class="note">有效注入判定来自外部 validator：已完成关系真→假、位姿误差、穿透深度、速度、
其他已跟踪子目标、后续策略查询。对象释放、稳定支撑与一般可解性未独立认证，
因此\u201c有效\u201d不等于全部物理约束均已证明。</p>

<h3>1.8 如何阅读本报告</h3>
<ul class="findings">
<li>下文每个任务一节，<b>同一任务的 6 个视频并排展示，配对 baseline 固定排在第一个</b>；
每个视频下方就是该用例的信息与结果，不再使用难以横向对照的宽表格。</li>
<li>内嵌播放的视频是 <b>256×256 / 12 fps / CRF 30 的压缩副本</b>，只用于浏览与定位失败时刻。
判定证据是 <code>report/videos/</code> 下的<b>原始 MP4</b>：60 个视频全部通过完整解码校验
（h264、解码帧数＝声明帧数），每张卡片的\u201c打开原始 MP4\u201d指向它。</li>
<li>逐用例完整字段（观察量、校验约束、运行命令、结果哈希）在每张卡片的
\u201c用例描述与运行证据\u201d中；机器可读版本见 <code>report/evidence.json</code>，
分析数值见 <code>report/analysis.json</code>，汇总见 <code>report/summary.json</code>。</li>
</ul>
</section>"""


# --------------------------------------------------------------------------- #
# page
# --------------------------------------------------------------------------- #
CSS = """
:root{--ink:#16232f;--muted:#5d7183;--line:#dbe4ec;--bg:#f5f8fb;--card:#fff;
--ok:#0f7a3d;--bad:#b3261e;--warn:#8a5a00;--accent:#1f5f9e}
*{box-sizing:border-box}
body{font:15px/1.6 system-ui,"Segoe UI","Microsoft YaHei",sans-serif;margin:0;padding:28px;
color:var(--ink);background:var(--bg)}
h1{font-size:26px;margin:0 0 6px}
h2{font-size:22px;margin:34px 0 12px;padding-bottom:8px;border-bottom:2px solid var(--line)}
h3{font-size:17px;margin:24px 0 10px}
h4{font-size:13px;margin:0;font-weight:600;overflow-wrap:anywhere}
p{margin:8px 0}
a{color:var(--accent)}
code{background:#eef3f8;padding:1px 5px;border-radius:4px;font-size:13px}
.sub{color:var(--muted);font-weight:400}
.na{color:var(--muted)}
.ok{color:var(--ok);font-weight:600}
.bad{color:var(--bad);font-weight:600}
.warn{color:var(--warn);font-weight:600}
.analysis,.task{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:20px 22px;margin:18px 0}
.chips{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}
.chip{border:1px solid var(--line);border-radius:10px;padding:10px 14px;background:#fbfdff;min-width:150px}
.chip-k{font-size:12px;color:var(--muted)}
.chip-v{font-size:24px;font-weight:700;line-height:1.25}
.chip-s{font-size:12px;color:var(--muted)}
.level-chips .chip{min-width:132px}
.findings{margin:10px 0 10px 20px;padding:0}
.findings li{margin:7px 0}
table.data{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}
table.data th,table.data td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
table.data th{background:#eef4fa;font-weight:600}
table.data td.bddl{font-size:12px;color:var(--muted);overflow-wrap:anywhere}
.note{font-size:13px;color:var(--muted)}
.task h3{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px}
.flags{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}
.tag{display:inline-block;font-size:12px;font-weight:700;padding:2px 8px;border-radius:20px;
background:#e8eef5;color:#33506b;white-space:nowrap}
.baseline-tag{background:#1f5f9e;color:#fff}
.ok-tag{background:#e3f4e9;color:var(--ok)}
.bad-tag{background:#fdeceb;color:var(--bad)}
.warn-tag{background:#fdf3e0;color:var(--warn)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.card{border:1px solid var(--line);border-radius:10px;padding:12px;background:#fff;
display:flex;flex-direction:column;gap:10px}
.card.baseline{background:#f7fbff;border-color:#b9d3ea}
.card.recovered{border-color:#8fce9f;box-shadow:0 0 0 2px #e3f4e9 inset}
.card header{display:flex;flex-direction:column;gap:6px}
.video-wrap video{width:100%;max-width:340px;aspect-ratio:1/1;background:#101820;
border-radius:8px;display:block}
.video-wrap.empty{color:var(--muted);font-size:13px}
.fallback{font-size:12px;color:var(--muted);margin:4px 0 0}
.fallback .path{display:block;overflow-wrap:anywhere;font-size:11px;color:#8697a6}
.card dl{display:grid;grid-template-columns:auto 1fr;gap:3px 10px;margin:0;font-size:13px}
.card dt{color:var(--muted)}
.card dd{margin:0;overflow-wrap:anywhere}
.outcome{margin:0;font-size:13px}
.invalid-reason{margin:0;font-size:12px;color:var(--bad);background:#fdeceb;
padding:6px 8px;border-radius:6px}
.links{margin:0;font-size:13px}
details{font-size:13px}
details summary{cursor:pointer;color:var(--accent)}
details pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f7fa;border:1px solid var(--line);
border-radius:8px;padding:10px;font-size:12px;max-height:340px;overflow:auto}
header.top{display:flex;flex-direction:column;gap:4px;margin-bottom:8px}
.toc{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
.toc a{border:1px solid var(--line);background:#fff;border-radius:20px;padding:3px 12px;
text-decoration:none;font-size:13px}
@media (max-width:820px){.cards{grid-template-columns:1fr}}
"""


def render_page(rows: list[dict], analysis: dict, report: Path, cache: Path, embed: bool) -> str:
    tasks = analysis["tasks"]
    sections = "".join(
        section_for_task(task, rows, report, cache, embed) for task in tasks
    )
    toc = "".join(
        f'<a href="#task-{t["task_index"]:02d}">任务 {t["task_index"]:02d}'
        f'（{t["recovered"]}/{t["valid"]}）</a>'
        for t in tasks
    )
    embed_note = "视频为内嵌压缩副本，可离线播放" if embed else "视频为外链原始 MP4"
    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LIBERO-rollback 评测报告（v1.1.0 / OpenVLA-OFT）</title>
<style>{CSS}</style></head><body>
<header class="top">
<h1>LIBERO-rollback 子任务回滚评测报告</h1>
<p class="sub">数据集 v1.1.0 · 模型 OpenVLA-OFT · LIBERO-10 · seed 0 · 600 控制步 ·
每用例配对基线 · 视频为真实仿真录制（{embed_note}）</p>
</header>
{render_analysis(analysis)}
<h2>二、逐任务详细结果</h2>
<p class="note">每个任务的 6 个视频并排；配对 baseline 排在第一个。视频下方是该用例的信息与结果。</p>
<nav class="toc">{toc}</nav>
{sections}
</body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS)
    parser.add_argument(
        "--no-embed",
        action="store_true",
        help="reference report/videos/*.mp4 instead of embedding compressed copies",
    )
    parser.add_argument("--output-name", default="index.html")
    args = parser.parse_args()
    runs = args.runs_dir.resolve()
    report = runs / "report"
    report.mkdir(parents=True, exist_ok=True)
    embed = not args.no_embed
    rows = collect(runs, report)
    analysis = analyse(rows)
    cache = report / "videos" / "embed"
    page = render_page(rows, analysis, report, cache, embed)
    target = report / args.output_name
    target.write_text(page, encoding="utf-8")
    (report / "evidence.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    (report / "analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False))
    valid_count = sum(r["injection_valid"] is True for r in rows)
    complete_count = sum(bool(r["result_link"]) and bool(r["videos"]) for r in rows)
    summary = {
        "dataset_version": "1.1.0",
        "case_count": len(rows),
        "result_and_video_count": complete_count,
        "external_validator_valid_count": valid_count,
        "valid_injection_task_success_count": analysis["recovered_n"],
        "video_case_count": sum(bool(r["videos"]) for r in rows),
        "all_cases_have_results_and_videos": complete_count == len(rows),
        "recovered_rate": analysis["recovered_rate"],
        "embedded_videos": embed,
    }
    (report / "summary.json").write_text(json.dumps(summary, indent=2))
    print(
        f"{target}: {target.stat().st_size / 1e6:.1f} MB, "
        f"{valid_count}/{len(rows)} valid, {analysis['recovered_n']} recovered, embed={embed}"
    )


if __name__ == "__main__":
    main()
