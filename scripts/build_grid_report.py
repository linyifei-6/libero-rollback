"""Build the HTML evidence report for the v1.2 dimension-grid sweep.

Differences from the v1.1 report builder:
  * the sweep stores one directory per case (``runs/v1.2-grid/<case_id>``), each
    with its own ``results.json`` and ``videos/``;
  * cases carry a runtime time point and destination, so the analysis section
    breaks recovery down by time point, goal kind and destination class;
  * videos are embedded as size-reduced ``data:`` URIs so the report plays from any
    origin, while the verified originals stay on disk and are linked per card.

Usage:
    python scripts/build_grid_report.py
    python scripts/build_grid_report.py --sweep runs/v1.2-grid --no-embed
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
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "dataset/v1.3/cases"
FFMPEG = (
    ROOT.parent
    / "libero-plus/openvla-oft-env/lib/python3.10/site-packages"
    / "imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
)
EMBED_ARGS = [
    "-vf", "scale=256:256", "-r", "12", "-an",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
]
TIME_POINT_ORDER = ["early", "mid", "later", "all_done"]
GOAL_ORDER = ["placement", "articulation"]
DESTINATION_LABEL = {
    "restore_episode_initial_pose": "初始位姿",
    "apply_episode_initial_offset": "初始偏移",
    "restore_captured_checkpoint_pose": "抓取前位姿",
    "restore_container_above_pose": "容器上方",
    "revert_articulation_goal": "articulation 回退",
}
TIME_POINT_LABEL = {
    "early": "early（刚完成）",
    "mid": "mid（撤离/转向）",
    "later": "later（收尾动作进行中）",
    "all_done": "all_done（全部完成边界）",
}


# --------------------------------------------------------------------------- #
# collect
# --------------------------------------------------------------------------- #
def collect(sweep: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(CASES.glob("*.yaml")):
        case = yaml.safe_load(path.read_text())
        case_id = case["case_id"]
        case_dir = sweep / case_id
        state = case["rollback_target"]["state_change"]
        row = {
            "case_id": case_id,
            "task_id": case["task"]["task_id"],
            "task_index": case["task"]["task_index"],
            "time_point": case["trigger"].get("time_point"),
            "trigger_event": case["trigger"]["event"],
            "severity": case["severity"],
            "stage": case["stage"]["name"],
            "state_change_kind": state["kind"],
            "goal_kind": "articulation" if state["kind"] == "revert_articulation_goal" else "placement",
            "offset_m": state.get("offset_m"),
            "clearance_m": state.get("clearance_m"),
            "setback": state.get("setback"),
            "description": case.get("intervention_description"),
            "status": "not run",
            "videos": [],
            "baseline_videos": [],
        }
        result_files = list(case_dir.rglob("results.json")) if case_dir.is_dir() else []
        if result_files:
            result_path = result_files[0]
            row["result_file"] = str(result_path)
            row["result_sha256"] = hashlib.sha256(result_path.read_bytes()).hexdigest()
            document = json.loads(result_path.read_text())
            for task_data in document.values():
                if not isinstance(task_data, dict):
                    continue
                for value in (task_data.get("results") or {}).values():
                    if not isinstance(value, dict):
                        continue
                    if value.get("kind") == "baseline":
                        row["baseline_raw"] = value
                    elif value.get("kind") == "perturbation":
                        row["perturbation_raw"] = value
            perturbation = row.get("perturbation_raw")
            if perturbation:
                row["status"] = "recorded"
                report = perturbation.get("report") or {}
                outcome = report.get("outcome") or {}
                trace = outcome.get("task_predicate_trace") or {}
                metrics = outcome.get("recovery_cost") or {}
                row.update({
                    "injection_valid": report.get("injection_valid"),
                    "task_success": perturbation.get("success"),
                    "steps": perturbation.get("steps"),
                    "trigger_step": report.get("injection_step"),
                    "recovered": outcome.get("recovered"),
                    "recovery_latency_steps": outcome.get("recovery_latency_steps"),
                    "recovery_verified": (outcome.get("recovery_verification") or {}).get(
                        "recovery_verified"
                    ),
                    "failure_reason": trace.get("final_success_false_reason"),
                    "final_subgoal_states": trace.get("final_subgoal_states"),
                    "termination": (outcome.get("termination") or {}).get("status"),
                    "validity_errors": report.get("errors") or [],
                    "policy_queries_after_rollback": (
                        (report.get("intervention") or {}).get("observed") or {}
                    ).get("policy_queries_after_rollback"),
                    "metrics": {
                        key: metrics.get(key)
                        for key in (
                            "regrasp_attempt_count", "failure_event_count",
                            "eef_path_length_m", "action_reversal_count",
                            "reobserve_count", "retreat_count", "reroute_count",
                            "old_subgoal_restore_count",
                        )
                    },
                    "artifacts": str(result_path.parent.relative_to(ROOT)),
                })
            baseline = row.get("baseline_raw")
            if baseline:
                row["baseline_success"] = baseline.get("success")
                row["baseline_steps"] = baseline.get("steps")
            # videos: case footage plus the paired baseline clip
            for mp4 in sorted(result_path.parent.rglob("*.mp4")):
                if "baseline" in mp4.name:
                    row["baseline_videos"].append(str(mp4))
                elif case_id.replace("-", "_") in mp4.name or "dataset_" in mp4.name:
                    row["videos"].append(str(mp4))
        rows.append(row)
    rows.sort(key=lambda r: (
        r["task_index"],
        GOAL_ORDER.index(r["goal_kind"]),
        TIME_POINT_ORDER.index(r["time_point"]) if r["time_point"] in TIME_POINT_ORDER else 9,
        DESTINATION_LABEL.get(r["state_change_kind"], r["state_change_kind"]),
    ))
    return rows


# --------------------------------------------------------------------------- #
# analysis
# --------------------------------------------------------------------------- #
def _rate(hit: int, total: int) -> str:
    return "n/a" if not total else f"{hit / total:.1%}"


def _median(values):
    nums = sorted(v for v in values if isinstance(v, (int, float)))
    if not nums:
        return None
    mid = len(nums) // 2
    return nums[mid] if len(nums) % 2 else (nums[mid - 1] + nums[mid]) / 2


def analyse(rows: list[dict]) -> dict:
    recorded = [r for r in rows if r["status"] == "recorded"]
    valid = [r for r in recorded if r["injection_valid"] is True]
    recovered = [r for r in valid if r["task_success"] is True]

    def bucket(key) -> list[dict]:
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in valid:
            groups[str(key(row))].append(row)
        out = []
        for name, items in groups.items():
            hit = sum(1 for r in items if r["task_success"] is True)
            out.append({"key": name, "valid": len(items), "recovered": hit,
                        "rate": _rate(hit, len(items))})
        return sorted(out, key=lambda b: b["key"])

    steps_delta = [
        r["steps"] - r["baseline_steps"]
        for r in valid
        if isinstance(r.get("steps"), (int, float))
        and isinstance(r.get("baseline_steps"), (int, float))
    ]
    return {
        "planned": len(rows),
        "recorded": len(recorded),
        "valid": len(valid),
        "invalid": len(recorded) - len(valid),
        "recovered": len(recovered),
        "recovery_rate": _rate(len(recovered), len(valid)),
        "baseline_ok": sum(1 for r in recorded if r.get("baseline_success") is True),
        "by_time_point": bucket(lambda r: r["time_point"]),
        "by_goal_kind": bucket(lambda r: r["goal_kind"]),
        "by_destination": bucket(lambda r: r["state_change_kind"]),
        "by_task": bucket(lambda r: r["task_id"]),
        "steps_delta_median": _median(steps_delta),
        "recovered_detail": [
            {
                "case_id": r["case_id"], "task_id": r["task_id"],
                "time_point": r["time_point"], "goal_kind": r["goal_kind"],
                "destination": r["state_change_kind"],
                "latency": r.get("recovery_latency_steps"),
                "steps": r.get("steps"), "baseline_steps": r.get("baseline_steps"),
                "verified": r.get("recovery_verified"),
            }
            for r in recovered
        ],
        "invalid_detail": [
            {"case_id": r["case_id"], "errors": r.get("validity_errors")}
            for r in recorded if r["injection_valid"] is not True
        ],
    }


# --------------------------------------------------------------------------- #
# render
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


def embed(source: Path, cache: Path, enabled: bool) -> str | None:
    if not enabled or not FFMPEG.exists() or not source.is_file():
        return None
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / source.name
    if not target.is_file() or target.stat().st_mtime < source.stat().st_mtime:
        with tempfile.TemporaryDirectory() as tmp:
            staged = Path(tmp) / "out.mp4"
            proc = subprocess.run(
                [str(FFMPEG), "-y", "-loglevel", "error", "-i", str(source), *EMBED_ARGS, str(staged)],
                capture_output=True, text=True,
            )
            if proc.returncode != 0 or not staged.is_file():
                return None
            shutil.move(str(staged), target)
    return "data:video/mp4;base64," + base64.b64encode(target.read_bytes()).decode("ascii")


def video_block(row: dict, media: Path, cache: Path, embed_enabled: bool) -> str:
    sources = list(row.get("videos", [])) + list(row.get("baseline_videos", []))
    if not sources:
        return '<div class="video-wrap empty">无视频证据</div>'
    parts = []
    for index, reference in enumerate(sources):
        source = Path(reference)
        target = media / f"{row['case_id']}--{source.name}"
        if source.is_file() and not target.exists():
            shutil.copy2(source, target)
        rel = f"videos/{target.name}"
        data_uri = embed(target if target.exists() else source, cache, embed_enabled)
        parts.append(
            f'<video controls preload="metadata" playsinline src="{esc(data_uri or rel)}" '
            f'data-original="{esc(rel)}"></video>'
            f'<p class="fallback">播放异常时：<a href="{esc(rel)}" target="_blank" '
            f'title="{esc(source.name)}">打开原始 MP4</a>'
            f'<span class="path" title="{esc(source.name)}">{esc(source.name[:36])}…</span></p>'
        )
    return f'<div class="video-wrap">{"".join(parts)}</div>'


def card(row: dict, media: Path, cache: Path, embed_enabled: bool) -> str:
    valid = row.get("injection_valid") is True
    if row["status"] != "recorded":
        outcome = '<span class="na">未运行</span>'
    elif row.get("task_success") is True and valid:
        outcome = '<span class="ok">模型恢复成功</span>'
    elif row.get("task_success") is True:
        outcome = '<span class="warn">任务成功，但注入无效，不计入恢复</span>'
    else:
        outcome = '<span class="bad">模型恢复失败</span>'
    items = [
        ("时间点", esc(TIME_POINT_LABEL.get(row["time_point"], row["time_point"]))),
        ("目标", "articulation" if row["goal_kind"] == "articulation" else "放置关系"),
        ("目的地", esc(DESTINATION_LABEL.get(row["state_change_kind"], row["state_change_kind"]))),
    ]
    if row.get("offset_m"):
        items.append(("偏移", esc(row["offset_m"])))
    if row.get("clearance_m"):
        items.append(("clearance", f'{row["clearance_m"]} m'))
    if row.get("setback"):
        items.append(("关节回退量", esc(row["setback"])))
    items += [
        ("注入有效性", tri(row.get("injection_valid"))),
        ("干预步", esc(row.get("trigger_step")) if row.get("trigger_step") is not None else '<span class="na">未触发</span>'),
        ("本用例任务成功", tri(row.get("task_success"))),
        ("配对基线成功", tri(row.get("baseline_success"))),
    ]
    if isinstance(row.get("recovery_latency_steps"), (int, float)):
        items.append(("恢复延迟", f'<b>{row["recovery_latency_steps"]} 步</b>'))
    if isinstance(row.get("steps"), (int, float)):
        delta = ""
        if isinstance(row.get("baseline_steps"), (int, float)):
            diff = row["steps"] - row["baseline_steps"]
            delta = f' <span class="sub">（基线 {row["baseline_steps"]}，{"+" if diff >= 0 else ""}{diff}）</span>'
        items.append(("本集步数", f'{row["steps"]}{delta}'))
    metrics = row.get("metrics") or {}
    if metrics.get("eef_path_length_m") is not None:
        items.append(("恢复代价", (
            f'重抓 {esc(metrics.get("regrasp_attempt_count"))} · '
            f'失败事件 {esc(metrics.get("failure_event_count"))} · '
            f'路径 {fmt(metrics.get("eef_path_length_m"), 2, " m")}'
        )))
        items.append(("行为统计", (
            f'重观测 {esc(metrics.get("reobserve_count"))} · '
            f'后退 {esc(metrics.get("retreat_count"))} · '
            f'改道 {esc(metrics.get("reroute_count"))} · '
            f'反向 {esc(metrics.get("action_reversal_count"))}'
        )))
    error_text = ""
    if row.get("validity_errors"):
        codes = "；".join(
            f'{e.get("name", "?")}（{e.get("detail", "")}）' if isinstance(e, dict) else str(e)
            for e in row["validity_errors"]
        )
        error_text = f'<p class="invalid-reason">注入无效原因：{esc(codes)}</p>'
    return (
        f'<article class="card {"recovered" if row.get("task_success") is True and valid else ""}">'
        f'<header><span class="tag">{esc(row["severity"])}</span>'
        f'<h4>{esc(row["case_id"])}</h4></header>'
        f"{video_block(row, media, cache, embed_enabled)}"
        "<dl>" + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in items) + "</dl>"
        f'<p class="outcome">{outcome}</p>'
        + error_text
        + f'<p class="links"><span class="sub">{esc(row.get("artifacts", ""))}</span></p>'
        + "</article>"
    )


def render_analysis(analysis: dict) -> str:
    def chips(buckets: list[dict], label=lambda k: k) -> str:
        return "".join(
            f'<div class="chip"><div class="chip-k">{esc(label(b["key"]))}</div>'
            f'<div class="chip-v {"ok" if b["recovered"] else "bad"}">{b["recovered"]}/{b["valid"]}</div>'
            f'<div class="chip-s">恢复率 {esc(b["rate"])}</div></div>'
            for b in buckets
        )

    def table(buckets: list[dict], label=lambda k: k) -> str:
        return (
            "<table class='data'><thead><tr><th>分组</th><th>有效注入</th><th>恢复</th>"
            "<th>恢复率</th></tr></thead><tbody>"
            + "".join(
                f'<tr><td>{esc(label(b["key"]))}</td><td>{b["valid"]}</td>'
                f'<td class="{"ok" if b["recovered"] else "bad"}">{b["recovered"]}</td>'
                f'<td>{esc(b["rate"])}</td></tr>'
                for b in buckets
            )
            + "</tbody></table>"
        )

    recovered_rows = "".join(
        "<tr>"
        + f'<td>{esc(r["task_id"])}</td><td>{esc(r["time_point"])}</td>'
        + f'<td>{esc(DESTINATION_LABEL.get(r["destination"], r["destination"]))}</td>'
        + f'<td>{esc(r["latency"])} 步</td><td>{esc(r["steps"])}</td>'
        + f'<td>{esc(r["baseline_steps"])}</td><td>{tri(r["verified"])}</td></tr>'
        for r in analysis["recovered_detail"]
    ) or '<tr><td colspan="7" class="na">暂无</td></tr>'
    invalid_rows = "".join(
        "<tr>"
        + f'<td>{esc(r["case_id"])}</td><td>'
        + esc("；".join(e.get("name", str(e)) if isinstance(e, dict) else str(e)
                        for e in (r["errors"] or [])))
        + "</td></tr>"
        for r in analysis["invalid_detail"]
    ) or '<tr><td colspan="2" class="na">无</td></tr>'

    return f"""<section class="analysis">
<h2>一、实验数据分析</h2>
<h3>1.1 规模与注入质量</h3>
<div class="chips">
  <div class="chip"><div class="chip-k">计划用例</div><div class="chip-v">{analysis["planned"]}</div>
    <div class="chip-s">10 个 LIBERO-10 任务</div></div>
  <div class="chip"><div class="chip-k">已完成回合</div><div class="chip-v">{analysis["recorded"]}</div>
    <div class="chip-s">含配对基线</div></div>
  <div class="chip"><div class="chip-k">注入有效</div><div class="chip-v">{analysis["valid"]}</div>
    <div class="chip-s">无效 {analysis["invalid"]}</div></div>
  <div class="chip"><div class="chip-k">配对基线成功</div>
    <div class="chip-v ok">{analysis["baseline_ok"]}/{analysis["recorded"]}</div>
    <div class="chip-s">任务本身可解</div></div>
  <div class="chip"><div class="chip-k">恢复</div>
    <div class="chip-v bad">{analysis["recovered"]}/{analysis["valid"]}</div>
    <div class="chip-s">恢复率 {esc(analysis["recovery_rate"])}</div></div>
</div>

<h3>1.2 按时间点</h3>
<div class="chips">{chips(analysis["by_time_point"], lambda k: TIME_POINT_LABEL.get(k, k))}</div>

<h3>1.3 按目标类型（放置 vs articulation）</h3>
<div class="chips">{chips(analysis["by_goal_kind"])}</div>
{table(analysis["by_goal_kind"])}

<h3>1.4 按回退目的地</h3>
{table(analysis["by_destination"], lambda k: DESTINATION_LABEL.get(k, k))}

<h3>1.5 逐任务</h3>
{table(analysis["by_task"])}

<h3>1.6 成功恢复的回合</h3>
<table class="data"><thead><tr><th>任务</th><th>时间点</th><th>目的地</th><th>恢复延迟</th>
<th>本集步数</th><th>基线步数</th><th>恢复经校验</th></tr></thead>
<tbody>{recovered_rows}</tbody></table>

<h3>1.7 注入无效的回合</h3>
<table class="data"><thead><tr><th>用例</th><th>原因</th></tr></thead>
<tbody>{invalid_rows}</tbody></table>
<p class="note">失败步数中位增量 {esc(analysis["steps_delta_median"])} 步；报告随 sweep 进度更新，
未运行用例以"未运行"标记。</p>
</section>"""


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
a{color:var(--accent)}
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
table.data{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}
table.data th,table.data td{border:1px solid var(--line);padding:7px 9px;text-align:left}
table.data th{background:#eef4fa;font-weight:600}
.note{font-size:13px;color:var(--muted)}
.task h3{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px}
.tag{display:inline-block;font-size:12px;font-weight:700;padding:2px 8px;border-radius:20px;
background:#e8eef5;color:#33506b;white-space:nowrap}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.card{border:1px solid var(--line);border-radius:10px;padding:12px;background:#fff;
display:flex;flex-direction:column;gap:10px}
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
.links{margin:0;font-size:12px}
"""


def render_page(rows: list[dict], analysis: dict, media: Path, cache: Path, embed_enabled: bool) -> str:
    by_task: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_task[row["task_id"]].append(row)
    sections = []
    for task_id in sorted(by_task):
        group = by_task[task_id]
        recorded = [r for r in group if r["status"] == "recorded"]
        hit = sum(1 for r in recorded if r["injection_valid"] is True and r["task_success"] is True)
        valid = sum(1 for r in recorded if r["injection_valid"] is True)
        tags = [
            f'<span class="tag {"ok-tag" if hit else "bad-tag"}">恢复 {hit}/{valid}</span>',
            f'<span class="tag">计划 {len(group)} 条</span>',
        ]
        if any(r["goal_kind"] == "articulation" for r in group):
            tags.append('<span class="tag">含 articulation 回退</span>')
        if any(r["stage"] == "completion_boundary" for r in group):
            tags.append('<span class="tag warn-tag">完成后继续执行窗口</span>')
        sections.append(
            f'<section class="task" id="task-{task_id.split("/")[1]}">'
            f'<h3>{esc(task_id)}<span class="sub"> · {len(group)} 条用例</span></h3>'
            f'<p class="flags">{"".join(tags)}</p>'
            f'<div class="cards">{"".join(card(r, media, cache, embed_enabled) for r in group)}</div>'
            "</section>"
        )
    toc = "".join(
        f'<a href="#task-{task_id.split("/")[1]}">{esc(task_id)}</a>' for task_id in sorted(by_task)
    )
    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LIBERO-rollback 维度网格评测报告（v1.2.0）</title>
<style>{CSS}</style></head><body>
<header>
<h1>LIBERO-rollback 维度网格评测报告</h1>
<p class="sub">数据集 1.2.0 · 模型 OpenVLA-OFT · LIBERO-10 · seed 0 · 400 控制步 ·
时间点 × 回退目的地 × 目标类型 三维网格 · 每用例配对基线</p>
</header>
{render_analysis(analysis)}
<h2>二、逐任务详细结果</h2>
<nav class="toc">{toc}</nav>
{"".join(sections)}
</body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep", type=Path, default=ROOT / "runs/v1.2-grid")
    parser.add_argument("--report", type=Path, default=ROOT / "runs/v1.2-grid/report")
    parser.add_argument("--no-embed", action="store_true")
    parser.add_argument("--cases", default="dataset/v1.3/cases",
                        help="case directory matching the sweep's release")
    args = parser.parse_args()
    sweep = args.sweep if args.sweep.is_absolute() else ROOT / args.sweep
    report = args.report if args.report.is_absolute() else ROOT / args.report
    report.mkdir(parents=True, exist_ok=True)
    media = report / "videos"
    media.mkdir(exist_ok=True)
    cache = report / "videos/embed"

    global CASES
    CASES = ROOT / args.cases if not Path(args.cases).is_absolute() else Path(args.cases)
    print(f"cases: {len(list(CASES.glob('*.yaml')))} from {CASES.relative_to(ROOT)}")
    rows = collect(sweep)
    analysis = analyse(rows)
    page = render_page(rows, analysis, media, cache, not args.no_embed)
    target = report / "index.html"
    target.write_text(page, encoding="utf-8")
    compact = [
        {key: value for key, value in row.items() if not key.endswith("_raw")}
        for row in rows
    ]
    (report / "evidence.json").write_text(json.dumps(compact, indent=2, ensure_ascii=False))
    (report / "analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False))
    print(f"{target}: {target.stat().st_size / 1e6:.1f} MB, "
          f"{analysis['recorded']}/{analysis['planned']} recorded, "
          f"{analysis['recovered']}/{analysis['valid']} recovered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
