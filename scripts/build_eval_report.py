"""Build the HTML evidence report for a batched pi05 rollback evaluation.

Reads one or more ``run_batched_eval.py`` output directories (``task<NN>/`` batches with a
merged binding, a benchmark ``run/`` tree and videos), joins every case back to its catalog
definition, and renders a single self-contained page: headline metrics, SVG charts, the
per-case result table and one card per case with the baseline / perturbation clips embedded
as size-reduced data URIs (originals stay on disk and are linked).

Usage:
    python scripts/build_eval_report.py \
        --run runs/eval-mid-d0-pi05 --run runs/eval-mid-rest-pi05 \
        --report runs/eval-mid-pi05-report --title "pi05 · mid 窗口"
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
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
EMBED_ARGS = [
    "-vf", "scale=256:256", "-r", "12", "-an",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
]
SEVERITY_ORDER = [
    "d0", "pose", "n3", "n5", "n8", "p3", "p5", "p8", "p10", "r05",
    "above", "boundary", "reference", "articulation",
]
MECHANISM_LABEL = {
    "restore_episode_initial_pose": "恢复回合初始位姿",
    "apply_episode_initial_offset": "施加初始位姿偏移",
    "displace_from_completed_pose": "从已完成位姿位移",
    "restore_native_relation_set": "恢复原生关系集",
    "displace_to_relation_boundary": "位移到关系边界",
    "restore_container_above_pose": "恢复到容器上方位姿",
    "revert_articulation_goal": "回退关节目标",
    "translate_relation_pair": "整对平移",
    "displace_reference_object": "位移参照物",
}
SEMANTICS_LABEL = {
    "relation_then_resume": "关系失效后应恢复",
    "relation_only": "仅关系（探针）",
    "relation_holds_control": "关系保持（对照）",
}


def load_catalog() -> dict[str, dict]:
    manifest = yaml.safe_load((ROOT / "dataset/current/manifest.yaml").read_text())
    return {
        entry["case_id"]: yaml.safe_load((ROOT / entry["path"]).read_text())
        for entry in manifest["cases"]
    }


def canonical(case_name: str) -> str:
    stripped = case_name[len("dataset_"):] if case_name.startswith("dataset_") else case_name
    return stripped.replace("_", "-")


def collect(run_root: Path, catalog: dict[str, dict]) -> list[dict]:
    summary_path = run_root / "batch-summary.json"
    if not summary_path.exists():
        return []
    summary = json.loads(summary_path.read_text())
    rows: list[dict] = []
    for task_key, task_summary in sorted(summary.get("tasks", {}).items()):
        task_dir = run_root / ("task" + task_key)
        binding_path = task_dir / "binding.yaml"
        results = sorted((task_dir / "run").rglob("results.json"))
        if not binding_path.exists() or not results:
            continue
        enabled_cases = yaml.safe_load(binding_path.read_text())["perturbation_binding"]["enabled_cases"]
        doc = json.loads(results[0].read_text())
        videos = {
            path.name: path for path in sorted(results[0].parent.rglob("*.mp4"))
        }
        for task_data in doc.values():
            baseline = next(
                (v for v in task_data["results"].values() if v.get("kind") == "baseline"), None
            )
            for label, value in task_data["results"].items():
                if value.get("kind") != "perturbation":
                    continue
                enabled = next(e for e in enabled_cases if e["case_name"] in label)
                severity = (enabled.get("severities") or [None])[0]
                case_id = canonical(enabled["case_name"])
                case = catalog.get(case_id, {})
                state = (case.get("rollback_target") or {}).get("state_change") or {}
                report = value.get("report") or {}
                outcome = report.get("outcome") or {}
                audit = value.get("pairing_audit") or {}
                cost = outcome.get("recovery_cost") or {}
                # Result labels carry a ``_s<seed>`` suffix that the video file name does
                # not, so the perturbation clip is matched on the suffix-free label first
                # and on the binding's case_name as a fallback.
                base_label = re.sub(r"_s\d+$", "", label)
                perturbation_clip = next(
                    (p for name, p in videos.items() if base_label in name), None
                )
                if perturbation_clip is None:
                    perturbation_clip = next(
                        (p for name, p in videos.items()
                         if "baseline" not in name and enabled["case_name"] in name),
                        None,
                    )
                baseline_clip = next(
                    (p for name, p in videos.items() if "baseline" in name), None
                )
                verdict = classify_result(case, {
                    "report": report,
                    "injection_valid": report.get("injection_valid"),
                })
                rows.append({
                    "run": run_root.name,
                    "case_id": case_id,
                    "verdict": verdict,
                    "label": label,
                    "task": case.get("task", {}).get("task_index"),
                    "task_ticket": case.get("task", {}).get("source_task_locator"),
                    "instruction": case.get("task", {}).get("suite"),
                    "severity": severity,
                    "mechanism": state.get("kind"),
                    "semantics": case.get("expected_evaluation_semantics"),
                    "time_point": (case.get("trigger") or {}).get("time_point"),
                    "trigger_event": (case.get("trigger") or {}).get("event"),
                    "description": case.get("intervention_description"),
                    "baseline_success": (baseline or {}).get("success"),
                    "baseline_steps": (baseline or {}).get("steps"),
                    "injection_valid": report.get("injection_valid"),
                    "injection_step": report.get("injection_step"),
                    "trigger_reached": (report.get("trigger") or {}).get("reached"),
                    "perturbation_success": value.get("success"),
                    "perturbation_steps": value.get("steps"),
                    "recovered": outcome.get("recovered"),
                    "recovery_latency": outcome.get("recovery_latency_steps"),
                    "audit_eligible": audit.get("eligible"),
                    "audit_queries": audit.get("required_prefix_queries"),
                    "eef_path_perturbation": cost.get("eef_path_length_m"),
                    "reversal_perturbation": cost.get("action_reversal_count"),
                    "regrasp_perturbation": cost.get("regrasp_attempt_count"),
                    "errors": report.get("errors") or [],
                    "returncode": task_summary.get("returncode"),
                    "baseline_clip": baseline_clip,
                    "perturbation_clip": perturbation_clip,
                })
    return rows


def metrics(rows: list[dict]) -> dict:
    base_ok = [r for r in rows if r["baseline_success"] is True]
    valid = [r for r in base_ok if r["injection_valid"] is True]
    # A case whose relation the evaluator restored must never be counted as the model
    # repairing it, so the verdict comes from the repository classifier rather than from the
    # episode's own success flag.
    recovered = [r for r in valid if r.get("verdict") == "valid_recovered"]
    external = [r for r in valid if r.get("verdict") == "valid_external_restoration"]
    protocol = [r for r in valid if r.get("verdict") == "protocol_incomplete"]
    return {
        "cases": len(rows),
        "baseline_ok": len(base_ok),
        "valid": len(valid),
        "recovered": len(recovered),
        "external": len(external),
        "protocol_incomplete": len(protocol),
        "rejected": len(rows) - len(valid),
        "audit_ok": len([r for r in rows if r["audit_eligible"] is True]),
        "tasks": len({r["task"] for r in rows}),
    }


def group(rows: list[dict], key: str) -> dict:
    buckets: dict = defaultdict(lambda: {"cases": 0, "valid": 0, "recovered": 0})
    for row in rows:
        bucket = buckets[row[key]]
        bucket["cases"] += 1
        if row["injection_valid"] is True:
            bucket["valid"] += 1
            if row["perturbation_success"] is True:
                bucket["recovered"] += 1
    return dict(buckets)


def esc(value) -> str:
    return html.escape(str(value))


def fmt(value, digits: int = 0, suffix: str = "") -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}{suffix}"
    return "—"


def tri(value, true="是", false="否") -> str:
    if value is True:
        return f'<span class="ok">{true}</span>'
    if value is False:
        return f'<span class="bad">{false}</span>'
    return '<span class="na">n/a</span>'


VERDICT_LABEL = {
    "valid_recovered": ("模型自修恢复", "ok"),
    "valid_external_restoration": ("外部复原（不计模型恢复）", "warn"),
    "valid_not_recovered": ("注入有效但模型未恢复", "bad"),
    "protocol_incomplete": ("协议不完整：模型未修，第二次撤销未触发", "warn"),
    "injection_invalid": ("注入无效", "warn"),
    "trigger_not_reached": ("触发未到达", "warn"),
}


def outcome_label(row: dict) -> tuple[str, str]:
    return VERDICT_LABEL.get(row.get("verdict"), ("未判定", "warn"))


def bar_chart(title: str, data: list[tuple[str, float, float, int]], unit: str = "") -> str:
    """Stacked bar chart: valid+recovered (green) over valid-not-recovered (amber) over invalid (grey)."""
    if not data:
        return ""
    width, row_h = 720, 26
    label_w, value_w = 132, 96
    height = row_h * len(data) + 34
    max_total = max(total for _, _, _, total in data) or 1
    plot_w = width - label_w - value_w
    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="{esc(title)}">']
    parts.append(f'<text x="0" y="12" class="chart-title">{esc(title)}</text>')
    for index, (label, recovered, valid_not, total) in enumerate(data):
        y = 24 + index * row_h
        parts.append(f'<text x="0" y="{y + 13}" class="chart-label">{esc(label)}</text>')
        x = label_w
        for value, cls in ((valid_not, "amber"), (recovered, "green")):
            seg = (value / max_total) * plot_w if max_total else 0
            if seg <= 0:
                continue
            parts.append(
                f'<rect x="{x:.1f}" y="{y + 2}" width="{seg:.1f}" height="{row_h - 6}" class="{cls}"/>'
            )
            if seg > 22:
                parts.append(
                    f'<text x="{x + seg / 2:.1f}" y="{y + 15}" class="seg-label">{int(value)}</text>'
                )
            x += seg
        parts.append(
            f'<text x="{width - value_w + 8}" y="{y + 15}" class="chart-value">'
            f'{int(recovered)}/{int(valid_not + recovered)}/{int(total)}{esc(unit)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def steps_scatter(rows: list[dict]) -> str:
    valid = [r for r in rows if r["injection_valid"] is True and r["baseline_steps"] and r["perturbation_steps"]]
    if not valid:
        return ""
    width, height, pad = 620, 320, 54
    max_steps = max(max(r["baseline_steps"], r["perturbation_steps"]) for r in valid)
    max_steps = int(max_steps * 1.08)
    def sx(value): return pad + (value / max_steps) * (width - pad - 24)
    def sy(value): return height - pad - (value / max_steps) * (height - pad - 28)
    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="基线与扰动步数">']
    parts.append('<text x="0" y="12" class="chart-title">基线与扰动步数（每点一条用例，虚线为 y=x）</text>')
    parts.append(f'<line x1="{sx(0)}" y1="{sy(0)}" x2="{sx(max_steps)}" y2="{sy(max_steps)}" class="axis dashed"/>')
    parts.append(f'<line x1="{pad}" y1="{sy(0)}" x2="{width - 24}" y2="{sy(0)}" class="axis"/>')
    parts.append(f'<line x1="{pad}" y1="{sy(0)}" x2="{pad}" y2="28" class="axis"/>')
    for tick in range(0, max_steps + 1, 200):
        parts.append(f'<text x="{sx(tick):.1f}" y="{height - pad + 18}" class="tick">{tick}</text>')
        parts.append(f'<text x="{pad - 10}" y="{sy(tick) + 4:.1f}" class="tick end">{tick}</text>')
    parts.append(f'<text x="{width / 2:.0f}" y="{height - 8}" class="axis-label">基线步数</text>')
    parts.append('<text x="12" y="20" class="axis-label">扰动步数</text>')
    for row in valid:
        cx, cy = sx(row["baseline_steps"]), sy(row["perturbation_steps"])
        cls = "green" if row["perturbation_success"] is True else "red"
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" class="{cls}">'
            f'<title>{esc(row["case_id"])}: 基线 {row["baseline_steps"]} → 扰动 {row["perturbation_steps"]}</title>'
            f'</circle>'
        )
    parts.append("</svg>")
    return "".join(parts)


def delta_chart(rows: list[dict]) -> str:
    valid = [r for r in rows if r["injection_valid"] is True and r["baseline_steps"] and r["perturbation_steps"]]
    if not valid:
        return ""
    data = []
    for row in sorted(valid, key=lambda r: r["perturbation_steps"] - r["baseline_steps"]):
        delta = row["perturbation_steps"] - row["baseline_steps"]
        data.append((row["case_id"].replace("libero-10-", ""), delta, row["perturbation_success"]))
    width, row_h = 720, 20
    height = row_h * len(data) + 40
    label_w = 250
    max_abs = max(abs(delta) for _, delta, _ in data) or 1
    plot_w = width - label_w - 60
    zero = label_w + plot_w / 2
    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="步数差">']
    parts.append('<text x="0" y="12" class="chart-title">相对配对的步数差（正=比基线多花步数；600 表示耗满预算）</text>')
    parts.append(f'<line x1="{zero:.1f}" y1="20" x2="{zero:.1f}" y2="{height - 18}" class="axis"/>')
    for index, (label, delta, success) in enumerate(data):
        y = 24 + index * row_h
        length = (abs(delta) / max_abs) * (plot_w / 2)
        x = zero if delta >= 0 else zero - length
        cls = "green" if success is True else "red"
        parts.append(f'<text x="0" y="{y + 12}" class="chart-label small">{esc(label)}</text>')
        parts.append(f'<rect x="{x:.1f}" y="{y + 2}" width="{length:.1f}" height="{row_h - 6}" class="{cls}"/>')
        parts.append(f'<text x="{width - 46}" y="{y + 12}" class="chart-value">{int(delta)}</text>')
    parts.append("</svg>")
    return "".join(parts)


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


def clip_block(sources: list[tuple[str, Path | None]], case_id: str, media: Path, cache: Path,
               embed_enabled: bool) -> str:
    parts = []
    for caption, source in sources:
        if source is None or not source.is_file():
            continue
        target = media / f"{case_id}--{source.name}"
        # Overwrite stale copies: a report directory can be rebuilt from a newer run whose
        # clip file names are identical, and keeping the old file would silently show the
        # wrong (e.g. pre-repair) footage.
        if not target.exists() or target.stat().st_mtime < source.stat().st_mtime:
            shutil.copy2(source, target)
        rel = f"videos/{target.name}"
        data_uri = embed(target, cache, embed_enabled)
        parts.append(
            f'<figure><video controls preload="metadata" playsinline muted loop '
            f'src="{esc(data_uri or rel)}"></video>'
            f'<figcaption>{esc(caption)}'
            f'<a href="{esc(rel)}" target="_blank">原片</a></figcaption></figure>'
        )
    if not parts:
        return '<p class="na">无视频证据</p>'
    return '<div class="clips">' + "".join(parts) + "</div>"


def case_card(row: dict, media: Path, cache: Path, embed_enabled: bool) -> str:
    label, cls = outcome_label(row)
    metrics_rows = [
        ("配对基线", f'{fmt(row["baseline_steps"])} 步' if row["baseline_success"] else "失败"),
        ("注入", f'第 {row["injection_step"]} 步' if row["injection_valid"] is True else "被拒绝"),
        ("扰动 episode", f'{fmt(row["perturbation_steps"])} 步'),
        ("恢复延迟", f'{fmt(row["recovery_latency"])} 步'),
        ("配对审计", f'{fmt(row["audit_queries"])} 个前缀查询' if row["audit_eligible"] else "不成立"),
        ("末端路径", fmt(row["eef_path_perturbation"], 3, " m")),
        ("重抓取次数", fmt(row["regrasp_perturbation"])),
    ]
    detail = "".join(
        f"<dt>{esc(key)}</dt><dd>{esc(value)}</dd>" for key, value in metrics_rows
    )
    errors = ""
    if row["errors"]:
        errors = '<p class="invalid-reason">' + "；".join(
            f'{esc(err.get("name"))}: {esc(err.get("detail"))}' for err in row["errors"]
        ) + "</p>"
    return f'''
<article class="card {cls}" id="{esc(row["case_id"])}" data-task="T{str(row["task"]).zfill(2)}" data-window="{esc(row["time_point"] or "")}" data-mechanism="{esc(row["mechanism"] or "")}" data-severity="{esc(row["severity"] or "")}" data-semantics="{esc(row["semantics"] or "")}" data-verdict="{esc(label)}" data-case="{esc(row["case_id"].lower())}">
  <header>
    <h3>{esc(row["case_id"])}</h3>
    <span class="badge {cls}">{esc(label)}</span>
  </header>
  <p class="meta">任务 {esc(row["task_ticket"])} · 档位 {esc(row["severity"])} ·
     机制 {esc(MECHANISM_LABEL.get(row["mechanism"], row["mechanism"]))} ·
     触发 {esc(row["trigger_event"])} ·
     语义 {esc(SEMANTICS_LABEL.get(row["semantics"], row["semantics"]))}</p>
  <p class="desc">{esc(row.get("description") or "")}</p>
  {errors}
  <dl class="metrics">{detail}</dl>
  {clip_block([("配对基线", row["baseline_clip"]), ("扰动后", row["perturbation_clip"])],
              row["case_id"], media, cache, embed_enabled)}
</article>'''


def render(title: str, rows: list[dict], totals: dict, media: Path, cache: Path,
           embed_enabled: bool, note: str) -> str:
    by_task = group(rows, "task")
    task_data = []
    for task in sorted(by_task, key=lambda t: (t is None, t)):
        bucket = by_task[task]
        recovered = bucket["recovered"]
        valid_not = bucket["valid"] - recovered
        task_data.append((f"T{str(task).zfill(2)}", recovered, valid_not, bucket["cases"]))
    by_severity = group(rows, "severity")
    severity_data = []
    for severity in SEVERITY_ORDER:
        if severity not in by_severity:
            continue
        bucket = by_severity[severity]
        severity_data.append((severity, bucket["recovered"], bucket["valid"] - bucket["recovered"], bucket["cases"]))
    by_window = group(rows, "time_point")
    by_semantics = group(rows, "semantics")
    window_data = []
    for window in ("early", "mid", "later", "all_done"):
        if window not in by_window:
            continue
        b = by_window[window]
        window_data.append((window, b["recovered"], b["valid"] - b["recovered"], b["cases"]))
    semantics_data = []
    for sem, b in sorted(by_semantics.items(), key=lambda kv: str(kv[0])):
        semantics_data.append((str(sem), b["recovered"], b["valid"] - b["recovered"], b["cases"]))
    success_rows = []
    for dim, key in (("窗口", "time_point"), ("机制", "mechanism"), ("语义", "semantics"), ("档位", "severity")):
        buckets = group(rows, key)
        for name, b in sorted(buckets.items(), key=lambda kv: str(kv[0])):
            ok = sum(1 for r in rows if r["injection_valid"] is True and r[key] == name
                     and r["perturbation_success"] is True)
            denom = b["valid"]
            rate = (100.0 * ok / denom) if denom else 0.0
            success_rows.append(
                f"<tr><td>{dim}</td><td>{esc(name)}</td><td>{b['cases']}</td><td>{denom}</td>"
                f"<td>{ok}</td><td>{rate:.0f}%</td><td>{b['recovered']}</td></tr>")
    success_table = "".join(success_rows)
    valid_rows = [r for r in rows if r["injection_valid"] is True]
    overall_ok = sum(1 for r in valid_rows if r["perturbation_success"] is True)
    overall_rate = (100.0 * overall_ok / len(valid_rows)) if valid_rows else 0.0
    by_mechanism = group(rows, "mechanism")
    mechanism_data = [
        (str(m), b["recovered"], b["valid"] - b["recovered"], b["cases"])
        for m, b in sorted(by_mechanism.items(), key=lambda kv: str(kv[0]))
    ]
    mechanism_rows = "".join(
        f'<tr><td>{esc(MECHANISM_LABEL.get(m, m))}</td><td>{b["cases"]}</td>'
        f'<td>{b["valid"]}</td><td>{b["recovered"]}</td></tr>'
        for m, b in sorted(by_mechanism.items(), key=lambda kv: str(kv[0]))
    )
    table_rows = "".join(
        "<tr>"
        f'<td><a href="#{esc(r["case_id"])}">{esc(r["case_id"].replace("libero-10-", ""))}</a></td>'
        f'<td>T{str(r["task"]).zfill(2)}</td><td>{esc(r["severity"])}</td>'
        f'<td>{tri(r["baseline_success"])}</td>'
        f'<td>{tri(r["injection_valid"])}</td>'
        f'<td>{tri(r["audit_eligible"])}</td>'
        f'<td>{fmt(r["baseline_steps"])}</td>'
        f'<td>{fmt(r["perturbation_steps"])}</td>'
        f'<td>{fmt(r["recovery_latency"]) if r["recovery_latency"] is not None else "—"}</td>'
        f'<td>{esc(outcome_label(r)[0])}</td>'
        "</tr>"
        for r in sorted(rows, key=lambda r: r["case_id"])
    )
    cards = "".join(
        case_card(r, media, cache, embed_enabled)
        # Default order is case name: related cases of one family stay adjacent, so the
        # differences between them are visible when scrolling the evidence section.
        for r in sorted(rows, key=lambda r: r["case_id"])
    )
    def options(values):
        return "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in sorted({str(x) for x in values if x}))
    task_opts = options(f'T{str(r["task"]).zfill(2)}' for r in rows if r["task"] is not None)
    window_opts = options(r["time_point"] for r in rows)
    mechanism_opts = options(r["mechanism"] for r in rows)
    severity_opts = options(r["severity"] for r in rows)
    semantics_opts = options(r["semantics"] for r in rows)
    verdict_opts = options(outcome_label(r)[0] for r in rows)
    valid = totals["valid"]
    recovery_rate = (totals["recovered"] / valid * 100) if valid else 0.0
    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
:root{{--ink:#16232f;--muted:#5d7183;--line:#dbe4ec;--bg:#f5f8fb;--card:#fff;
--ok:#0f7a3d;--bad:#b3261e;--warn:#8a5a00;--accent:#1f5f9e}}
*{{box-sizing:border-box}}
body{{margin:0;padding:28px 22px 64px;font:15px/1.65 -apple-system,"Segoe UI","Noto Sans CJK SC",sans-serif;
color:var(--ink);background:var(--bg)}}
h1{{font-size:26px;margin:0 0 6px}}
h2{{font-size:20px;margin:38px 0 14px;padding-bottom:8px;border-bottom:2px solid var(--line)}}
h3{{font-size:15px;margin:0}}
.sub{{color:var(--muted);margin:0 0 18px}}
.chips{{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0 8px}}
.chip{{border:1px solid var(--line);border-radius:10px;padding:10px 14px;background:#fbfdff;min-width:132px}}
.chip b{{display:block;font-size:21px}}
.chip span{{font-size:12px;color:var(--muted)}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0}}
table.data{{border-collapse:collapse;width:100%;font-size:13px;background:var(--card)}}
table.data th,table.data td{{border:1px solid var(--line);padding:6px 8px;text-align:left}}
table.data th{{background:#eef4f9;position:sticky;top:0}}
.table-wrap{{max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:12px}}
.chart{{width:100%;height:auto;background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:10px;margin:12px 0}}
.chart-title{{font-size:13px;font-weight:600;fill:var(--ink)}}
.chart-label{{font-size:12px;fill:var(--ink)}}
.chart-label.small{{font-size:11px}}
.chart-value{{font-size:12px;fill:var(--muted)}}
.seg-label{{font-size:11px;fill:#fff;text-anchor:middle}}
.tick{{font-size:11px;fill:var(--muted);text-anchor:middle}}
.tick.end{{text-anchor:end}}
.axis-label{{font-size:11px;fill:var(--muted);text-anchor:middle}}
.axis{{stroke:#9fb2c2;stroke-width:1}}
.axis.dashed{{stroke-dasharray:4 4;stroke:#c3d2de}}
.green{{fill:#0f7a3d}} .red{{fill:#b3261e}} .amber{{fill:#d9a300}}
circle.green{{fill:#0f7a3d}} circle.red{{fill:#b3261e}}
.ok{{color:var(--ok);font-weight:600}} .bad{{color:var(--bad);font-weight:600}}
.warn{{color:var(--warn);font-weight:600}} .na{{color:var(--muted)}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(430px,1fr));gap:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-left-width:5px;border-radius:12px;padding:14px}}
.card.ok{{border-left-color:var(--ok)}} .card.bad{{border-left-color:var(--bad)}}
.card.warn{{border-left-color:var(--warn)}}
.card header{{display:flex;justify-content:space-between;align-items:baseline;gap:8px}}
.badge{{font-size:12px;border-radius:999px;padding:2px 10px;background:#eef4f9}}
.badge.ok{{background:#e6f4ea;color:var(--ok)}} .badge.bad{{background:#fdeceb;color:var(--bad)}}
.badge.warn{{background:#fdf5e2;color:var(--warn)}}
.meta{{font-size:12px;color:var(--muted);margin:6px 0}}
.desc{{font-size:13px;color:#33475b;margin:6px 0}}
.metrics{{display:grid;grid-template-columns:repeat(2,1fr);gap:2px 12px;margin:8px 0;font-size:12px}}
.metrics dt{{color:var(--muted)}} .metrics dd{{margin:0 0 4px}}
.invalid-reason{{font-size:12px;color:var(--bad);background:#fdeceb;border-radius:8px;padding:8px;margin:6px 0}}
.clips{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}}
.clips video{{width:100%;border-radius:8px;background:#0d1117}}
.clips figcaption{{font-size:11px;color:var(--muted);display:flex;justify-content:space-between;margin-top:2px}}
.legend{{font-size:12px;color:var(--muted);margin:6px 0 0}}
.note{{font-size:13px;color:#33475b;background:#fdf5e2;border:1px solid #f0dca8;border-radius:10px;padding:12px}}
.filters{{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;font-size:13px}}
.filters label{{display:flex;flex-direction:column;gap:4px;color:var(--muted)}}
.filters select,.filters input{{font:inherit;padding:5px 8px;border:1px solid var(--line);border-radius:8px;background:#fff}}
.filters button{{font:inherit;padding:6px 14px;border:1px solid var(--line);border-radius:8px;background:#eef4f9;cursor:pointer}}
.filter-note{{color:var(--muted);margin-left:auto}}
.card.hidden{{display:none}}
</style></head><body>
<h1>{esc(title)}</h1>
<p class="sub">{esc(note)}</p>

<div class="chips">
  <div class="chip"><b>{totals["cases"]}</b><span>用例总数</span></div>
  <div class="chip"><b>{totals["baseline_ok"]}/{totals["cases"]}</b><span>配对基线成功</span></div>
  <div class="chip"><b>{totals["valid"]}/{totals["cases"]}</b><span>注入有效</span></div>
  <div class="chip"><b>{totals["recovered"]}/{valid}</b><span>模型自修恢复（{recovery_rate:.0f}%）</span></div>
  <div class="chip"><b>{totals["external"]}</b><span>外部复原（不计模型恢复）</span></div>
  <div class="chip"><b>{totals["protocol_incomplete"]}</b><span>协议不完整（模型未修）</span></div>
  <div class="chip"><b>{totals["rejected"]}</b><span>注入被拒（几何约束）</span></div>
  <div class="chip"><b>{totals["audit_ok"]}/{totals["cases"]}</b><span>配对审计成立</span></div>
  <div class="chip"><b>{totals["tasks"]}</b><span>任务批次</span></div>
</div>

<h2>一、总体指标</h2>
<div class="panel">
<p>恢复率的分母是「基线成功 <b>且</b> 注入有效」的用例：只有注入真实改写了状态，
「模型是否把它修回来」才是可判定的问题。基线失败或注入无效的用例不计入分母，
也不计为模型失败。</p>
<p><b>注入无效</b>的用例其 episode 实际是<b>未受扰动</b>的（原始结果里成功率是 1.0，
Δ步与 Δ末端路径为 0），本报告把它们标注为「注入无效」并排除在恢复率之外。</p>
</div>

<h2>二、成功率分析</h2>
<div class="panel">
<p><b>整体成功率：{overall_ok}/{len(valid_rows)} = {overall_rate:.1f}%</b>（分母只含<b>注入有效</b>的用例；
注入被拒 / 基线失败的用例不计入分母，也不计为模型失败）。</p>
<p>成功率 = 扰动 episode 中模型仍完成任务的比例；自修恢复率 = 模型主动把被破坏的关系修回来的比例
（{totals["recovered"]}/{valid} = {recovery_rate:.1f}%）。</p>
</div>
<div class="panel"><table class="data">
<thead><tr><th>维度</th><th>分组</th><th>用例</th><th>注入有效（分母）</th><th>episode 成功</th><th>成功率</th><th>自修恢复</th></tr></thead>
<tbody>{success_table}</tbody></table></div>
{bar_chart("按窗口（绿=恢复，黄=注入有效但未恢复，灰=注入无效）", window_data)}
{bar_chart("按机制", mechanism_data)}
{bar_chart("按语义", semantics_data)}

<h2>三、按任务与档位</h2>
{bar_chart("按任务（绿=恢复，黄=注入有效但未恢复，灰=注入无效；右列为 恢复/有效/总数）", task_data)}
{bar_chart("按档位", severity_data)}
<p class="legend">绿色 = 模型恢复；黄色 = 注入有效但模型未恢复；灰色 = 注入无效（不进分母）。</p>

<h2>四、步数视角</h2>
{steps_scatter(rows)}
{delta_chart(rows)}

<h2>五、逐条结果</h2>
<div class="table-wrap"><table class="data">
<thead><tr><th>用例</th><th>任务</th><th>档位</th><th>基线</th><th>注入</th><th>配对审计</th>
<th>基线步数</th><th>扰动步数</th><th>恢复延迟</th><th>结论</th></tr></thead>
<tbody>{table_rows}</tbody></table></div>

<h2>六、机制分布</h2>
<div class="panel"><table class="data">
<thead><tr><th>机制</th><th>用例</th><th>注入有效</th><th>模型恢复</th></tr></thead>
<tbody>{mechanism_rows}</tbody></table></div>

<h2>七、逐条证据（含视频）</h2>
<div class="panel filters">
  <label>任务 <select id="f-task"><option value="">全部</option>{task_opts}</select></label>
  <label>窗口 <select id="f-window"><option value="">全部</option>{window_opts}</select></label>
  <label>机制 <select id="f-mechanism"><option value="">全部</option>{mechanism_opts}</select></label>
  <label>档位 <select id="f-severity"><option value="">全部</option>{severity_opts}</select></label>
  <label>语义 <select id="f-semantics"><option value="">全部</option>{semantics_opts}</select></label>
  <label>结论 <select id="f-verdict"><option value="">全部</option>{verdict_opts}</select></label>
  <label>搜索 <input id="f-case" placeholder="case_id 关键字"></label>
  <button id="f-reset" type="button">重置</button>
  <span class="filter-note" id="f-count"></span>
</div>
<div class="cards" id="case-cards">{cards}</div>

<h2>八、方法与复现</h2>
<div class="panel">
<p>每个任务批次一次进程：加载模型（含 JIT warmup）一次 → 跑一次无扰动配对基线 →
依次跑该任务的全部扰动；每条扰动与基线做 <code>audit_strict_pairing</code>，
比对注入前 17 个 policy 查询的 observation / sim-state / noise / action 哈希，
不一致则该条审计不成立。</p>
<p>视频为 benchmark 记录的原始 MP4 的等比缩小转码（256×256、12 fps、CRF 30、无音轨），
完整原片保存在 <code>task*/run/*/videos/</code>，每张卡片都给出原片链接。</p>
</div>
<script>
(function(){{
  const ids=["f-task","f-window","f-mechanism","f-severity","f-semantics","f-verdict"];
  const cards=[...document.querySelectorAll("#case-cards .card")];
  const q=document.getElementById("f-case");
  const count=document.getElementById("f-count");
  function apply(){{
    const v={{}};
    ids.forEach(function(id){{v[id]=document.getElementById(id).value;}});
    const needle=(q.value||"").trim().toLowerCase();
    let shown=0;
    cards.forEach(function(card){{
      const ok = (!v["f-task"]||card.dataset.task===v["f-task"])
        && (!v["f-window"]||card.dataset.window===v["f-window"])
        && (!v["f-mechanism"]||card.dataset.mechanism===v["f-mechanism"])
        && (!v["f-severity"]||card.dataset.severity===v["f-severity"])
        && (!v["f-semantics"]||card.dataset.semantics===v["f-semantics"])
        && (!v["f-verdict"]||card.dataset.verdict===v["f-verdict"])
        && (!needle || card.dataset.case.includes(needle));
      card.classList.toggle("hidden", !ok);
      if(ok) shown++;
    }});
    count.textContent="显示 "+shown+" / "+cards.length+" 条";
  }}
  ids.forEach(function(id){{document.getElementById(id).addEventListener("change",apply);}});
  q.addEventListener("input",apply);
  document.getElementById("f-reset").addEventListener("click",function(){{
    ids.forEach(function(id){{document.getElementById(id).value="";}});
    q.value=""; apply();
  }});
  apply();
}})();
</script>
</body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, action="append", required=True,
                        help="batched run directory (repeatable)")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--title", default="pi05 回滚评测")
    parser.add_argument("--note", default="")
    parser.add_argument("--no-embed", action="store_true")
    args = parser.parse_args()

    catalog = load_catalog()
    rows: list[dict] = []
    for run in args.run:
        run_path = run if run.is_absolute() else ROOT / run
        rows.extend(collect(run_path, catalog))
    if not rows:
        raise SystemExit("no cases collected from the given run directories")
    totals = metrics(rows)
    report = args.report if args.report.is_absolute() else ROOT / args.report
    report.mkdir(parents=True, exist_ok=True)
    media = report / "videos"
    media.mkdir(exist_ok=True)
    cache = media / "embed"
    note = args.note or (
        f"{totals['cases']} 条用例 · {totals['tasks']} 个任务批次 · "
        f"基线成功 {totals['baseline_ok']}/{totals['cases']} · "
        f"注入有效 {totals['valid']}/{totals['cases']} · "
        f"模型恢复 {totals['recovered']}/{totals['valid']}"
    )
    page = render(args.title, rows, totals, media, cache, not args.no_embed, note)
    target = report / "index.html"
    target.write_text(page, encoding="utf-8")
    (report / "evidence.json").write_text(
        json.dumps({"totals": totals, "cases": [
            {k: (str(v) if isinstance(v, Path) else v) for k, v in row.items()} for row in rows
        ]}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"{target}: {target.stat().st_size / 1e6:.1f} MB, "
          f"{totals['cases']} cases, {totals['recovered']}/{totals['valid']} recovered, "
          f"videos: {len(list(media.glob('*.mp4')))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
