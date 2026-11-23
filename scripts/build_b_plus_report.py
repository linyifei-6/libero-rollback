# ruff: noqa: E501
#!/usr/bin/env python3
"""Render a self-contained HTML progress report for a B-plus run.

# ruff: noqa: E501

Reads ``episodes.jsonl`` + ``run-manifest.json`` (+ ``matrix.json`` for the
planned case count), fills ``docs/report-template/b-plus-progress.html`` and
writes ``index.html`` + ``provenance.json``.

No third-party dependencies; the output is file:// friendly and contains all
CSS/JS inline. Videos are linked with relative paths from the output directory.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = REPO_ROOT / "docs" / "report-template" / "b-plus-progress.html"


def repo_relative(path) -> str:
    """Repo-relative label when the path lives inside the checkout (no host paths)."""

    path = Path(path).resolve()
    try:
        return path.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def pct(k: int, n: int) -> str:
    return "—" if n <= 0 else f"{100.0 * k / n:.1f}%"


def level_label(row: dict) -> str:
    level = row.get("level") or ""
    if level != "O2":
        return level
    param = str(row.get("param") or "")
    if param.startswith("l") and "s" in param:
        return "L" + param[1 : param.index("s")]
    return "O2"


def status_of(row: dict) -> str:
    """Outcome label used by the video cards / filters.

    ``na`` (the policy never completed the task, so no perturbation was
    triggered) is deliberately **not** ``invalid``: an invalid case reached the
    trigger but failed an injection gate, which is a protocol problem; an
    untriggered case is a model-capability observation.
    """

    if not row.get("trigger_reached"):
        return "na"
    if not row.get("case_valid"):
        return "invalid"
    return "recovered" if row.get("recovered") else "not_recovered"


def badge(text: str, cls: str = "") -> str:
    return f'<span class="badge {cls}">{esc(text)}</span>'


def kpi(label: str, value: str, sub: str) -> str:
    return (
        '<div class="kpi">'
        f'<div class="kpi-label">{esc(label)}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-sub">{sub}</div>'
        "</div>"
    )


def table(headers: list[str], rows: list[list[str]], num_cols: set[int] | None = None) -> str:
    num_cols = num_cols or set()
    out = ['<table class="dt"><thead><tr>']
    for i, h in enumerate(headers):
        cls = ' class="num"' if i in num_cols else ""
        out.append(f"<th{cls}>{esc(h)}</th>")
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>")
        for i, cell in enumerate(row):
            cls = ' class="num"' if i in num_cols else ""
            out.append(f"<td{cls}>{cell}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def bar_rows(levels: list[tuple[str, int, int]]) -> str:
    out = []
    for label, k, n in levels:
        width = 0.0 if n <= 0 else 100.0 * k / n
        out.append(
            '<div class="bar-row">'
            f"<span>{esc(label)}</span>"
            f'<div class="bar"><i style="width:{width:.1f}%"></i></div>'
            f'<span class="num">{k}/{n}</span>'
            "</div>"
        )
    return "".join(out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="run directory with episodes.jsonl")
    parser.add_argument("--out", type=Path, default=None, help="output directory (default: <run>/report)")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--title", default="B-plus Goal · 回滚模测进度")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run = args.run.resolve()
    out_dir = (args.out or (run / "report")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    episodes_path = run / "episodes.jsonl"
    rows = [
        json.loads(line)
        for line in episodes_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    manifest = json.loads((run / "run-manifest.json").read_text(encoding="utf-8"))
    defaults = manifest.get("defaults", {})
    matrix = json.loads((run / "matrix.json").read_text(encoding="utf-8"))
    total = int(matrix.get("cases") or len(rows))

    o2 = [r for r in rows if r.get("level") == "O2"]
    o2_valid = [r for r in o2 if r.get("case_valid")]
    o2_rec = [r for r in o2_valid if r.get("recovered")]
    c0 = [r for r in rows if r.get("level") == "C0"]
    c0_valid = [r for r in c0 if r.get("case_valid")]
    c0_ok = [r for r in c0_valid if r.get("recovered")]
    l0 = [r for r in rows if r.get("level") == "L0"]
    l0_valid = [r for r in l0 if r.get("case_valid")]
    l0_rec = [r for r in l0_valid if r.get("recovered")]
    early = [r for r in rows if r.get("early_stopped")]
    vids = [r for r in rows if (r.get("video") or {}).get("path") and os.path.exists(r["video"]["path"])]
    vid_mb = sum(os.path.getsize(r["video"]["path"]) for r in vids) / 1e6

    completed = len(rows)
    status_class = "warn" if completed < total else "ok"
    run_status = f"{'RUNNING' if completed < total else 'COMPLETE'} · {completed}/{total}"
    generated = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")

    # meta
    suite = ",".join(sorted({r.get("suite", "") for r in rows})) or "goal"
    split_label = "core" if total <= 56 else "full"
    meta_items = [
        ("model", defaults.get("policy")),
        ("checkpoint", defaults.get("checkpoint")),
        ("suite / split", f"{suite} / {split_label}"),
        ("init_row / seed", f"{defaults.get('init_row')} / {defaults.get('seed')}"),
        ("budget", f"{defaults.get('max_steps')} + {defaults.get('repair_window')} repair"),
        ("delay / replan", f"{defaults.get('delay_steps')} / {defaults.get('replan')}"),
        ("camera / video", f"{defaults.get('camera')} / {defaults.get('video_fps')} fps"),
        ("settle_after_injection", defaults.get("settle_after_injection", 0)),
        ("stop_on_recovery", defaults.get("stop_on_recovery")),
        ("matrix", defaults.get("matrix")),
        ("run dir", repo_relative(run)),
        ("generated", generated),
    ]
    meta = "".join(f"<div><dt>{esc(k)}</dt><dd class=\"mono\">{esc(v)}</dd></div>" for k, v in meta_items)

    # KPIs
    ci_lo, ci_hi = wilson(len(o2_rec), len(o2_valid))
    kpis = "".join(
        [
            kpi("Completed", f"{completed}/{total}",
                f"O2 {len(o2)}/{int(matrix.get('by_level', {}).get('O2', len(o2)))} · "
                f"controls {len(c0)+len(l0)}/{int(matrix.get('by_level', {}).get('C0', 0)) + int(matrix.get('by_level', {}).get('L0', 0))}"),
            kpi("O2 valid", f"{len(o2_valid)}", f"of {len(o2)} attempted"),
            kpi("O2 recovery", pct(len(o2_rec), len(o2_valid)),
                f"{len(o2_rec)}/{len(o2_valid)} · 95% CI {100*ci_lo:.0f}–{100*ci_hi:.0f}%"),
            kpi("C0 control", f"{len(c0_ok)}/{len(c0_valid)}", f"valid cases · {len(c0)} attempted"),
            kpi("N/A (not triggered)", f"{sum(1 for r in rows if not r.get('trigger_reached'))}",
                "policy did not complete the task; no perturbation"),
            kpi("Early stopped", f"{len(early)}", "recovered before full repair window"),
            kpi("Videos", f"{len(vids)}", f"{vid_mb:.1f} MB"),
        ]
    )

    # arm table
    arm_rows = []
    for label, group in [("O2 rollback", o2), ("C0 control", c0), ("L0 rollback", l0)]:
        gv = [r for r in group if r.get("case_valid")]
        gr = [r for r in gv if r.get("recovered")]
        arm_rows.append([
            esc(label), str(len(group)), str(len(gv)),
            str(sum(1 for r in group if r.get("trigger_reached"))),
            f"{len(gr)} ({pct(len(gr), len(gv))})",
            str(sum(1 for r in group if r.get("early_stopped"))),
        ])
    arm_table = table(
        ["arm", "done", "valid", "trigger", "recovered / success", "early stopped"],
        arm_rows, {1, 2, 3, 4, 5},
    )

    # levels
    level_rows = []
    level_bars = []
    for lv in ["1", "2", "3", "4", "5"]:
        rs = [r for r in o2_valid if str(r.get("param", "")).startswith(f"l{lv}s")]
        k = sum(1 for r in rs if r.get("recovered"))
        level_rows.append([
            f"L{lv}", str(len(rs)), str(k), pct(k, len(rs)),
            str(sum(1 for r in rs if r.get("early_stopped"))),
        ])
        level_bars.append((f"L{lv}", k, len(rs)))
    level_table = table(["level", "valid", "recovered", "rate", "early stopped"], level_rows, {1, 2, 3, 4})

    # tasks
    task_rows = []
    for task in sorted({r["bddl_name"] for r in o2}):
        rs = [r for r in o2_valid if r["bddl_name"] == task]
        if not rs:
            continue
        k = sum(1 for r in rs if r.get("recovered"))
        task_rows.append([esc(task), str(len(rs)), str(k), pct(k, len(rs))])
    task_table = table(["task", "valid", "recovered", "rate"], task_rows, {1, 2, 3})

    # failures
    failures = []
    trig_fail = [r for r in rows if not r.get("trigger_reached")]
    if trig_fail:
        failures.append(
            f"<h3>N/A · 未触发（{len(trig_fail)}）：策略没能在 600 步内完成原任务，"
            "因此没有可撤销的完成态</h3><ul>"
        )
        for r in trig_fail:
            failures.append(
                f"<li><span class=\"mono\">{esc(r['case_id'])}</span> "
                f"· {esc(r.get('level'))} · steps={esc(r.get('steps'))} "
                f"<span class=\"muted\">— N/A（模型未完成原任务）</span></li>"
            )
        failures.append("</ul>")
    invalid = [r for r in rows if r.get("trigger_reached") and not r.get("case_valid")]
    if invalid:
        failures.append(f"<h3>triggered but invalid（{len(invalid)}）</h3><ul>")
        for r in invalid:
            inj = r.get("injection") or {}
            reasons = []
            if not inj.get("no_penetration", True):
                reasons.append(f"penetration={inj.get('penetration_m')}")
            if not inj.get("zero_velocity", True):
                reasons.append("velocity")
            if not inj.get("object_released", True):
                reasons.append("not_released")
            if r.get("level") != "C0" and r.get("relation_after_injection") is True:
                reasons.append("relation_still_true")
            if r.get("level") == "C0" and not r.get("success"):
                reasons.append("C0 final goal false (no-op not preserved)")
            failures.append(
                f"<li><span class=\"mono\">{esc(r['case_id'])}</span> — {esc(', '.join(reasons) or 'unknown')}</li>"
            )
        failures.append("</ul>")
    if not failures:
        failures.append('<div class="note">当前没有 trigger failure 或 invalid injection。</div>')

    # videos
    cards = []
    task_options = sorted({r["bddl_name"] for r in rows})
    level_options = sorted({level_label(r) for r in rows if r.get("level") == "O2"})
    for r in rows:
        video = r.get("video") or {}
        path = video.get("path")
        rel = ""
        if path and os.path.exists(path):
            rel = os.path.relpath(path, out_dir).replace(os.sep, "/")
        status = status_of(r)
        badge_cls = "ok" if status == "recovered" else ("bad" if status == "not_recovered" else "na")
        badge_txt = {
            "recovered": "recovered",
            "not_recovered": "not recovered",
            "invalid": "invalid injection",
            "na": "N/A · not triggered",
        }[status]
        block = f'<video controls preload="metadata" playsinline muted loop src="{esc(rel)}"></video>' if rel else '<div class="missing">video missing</div>'
        cards.append(
            f'<article class="video-card" data-level="{esc(level_label(r))}" data-task="{esc(r["bddl_name"])}" data-status="{status}">'
            f'<div class="video-head"><span class="mono">{esc(r["case_id"])}</span>{badge(badge_txt, badge_cls)}</div>'
            f"{block}"
            f'<div class="video-meta"><b>{esc(level_label(r))}</b> · steps {esc(r.get("steps"))}'
            f'{" · early stop" if r.get("early_stopped") else ""}'
            f'{" · trigger N/A" if not r.get("trigger_reached") else ""}</div>'
            "</article>"
        )
    video_cards = "".join(cards) if cards else '<div class="note">还没有视频。</div>'
    level_opts = '<option value="all">all</option>' + "".join(
        f'<option value="{esc(x)}">{esc(x)}</option>' for x in level_options
    )
    task_opts = '<option value="all">all</option>' + "".join(
        f'<option value="{esc(t)}">{esc(t)}</option>' for t in task_options
    )

    completion_note = (
        f"这是 <b>最终报告</b>：{completed}/{total} 已完成，控制臂已完成。"
        if completed >= total
        else f"这是 <b>interim 报告</b>：{completed}/{total}，控制臂还未全部完成。"
    )
    notes = f"""
<div class="note">
  <b>实现</b>
  <ul>
    <li>独立入口 <span class="mono">scripts/run_b_plus.py</span>，只读 <span class="mono">dataset/matrices/plus/b-matrix-plus.csv</span>，不触碰 v2 B 矩阵。</li>
    <li><span class="mono">BCase</span> 增加 <span class="mono">O2</span> level；<span class="mono">BInjector</span> 只写被撤销目标的 7 维 pose。</li>
    <li>修复：<span class="mono">.pruned_init</span> 是 <span class="mono">[time, qpos, qvel]</span>，O2 目标 qpos 索引 = 模型 <span class="mono">jnt_qposadr + 1</span>。</li>
  </ul>
</div>
<div class="note warn">
  <b>当前限制</b>
  <ul>
    <li>{completion_note}</li>
    {"<li><b>协议：</b>本报告合并了 immediate-v1 与 post-settle-v1；settle_after_injection = " + esc(str(defaults.get("settle_after_injection", 0))) + "。</li>" if isinstance(defaults.get("settle_after_injection"), str) else ""}
    <li>没有 fresh / fresh-state 臂，不能区分“O2 pose 本身难”与“完成后 history 失效”。</li>
    <li>goal O2 的 target 位移为 16–44 cm，远大于 object/spatial 的 1–10 cm；低 recovery 可能包含 reachability 因素。</li>
    <li>core 每个 task 只有 3–5 条，task 级差异不稳定。</li>
  </ul>
</div>
<div class="note">
  <b>下一步</b>
  <ol>
    <li>跑完剩余控制臂，重跑本生成器得到最终表。</li>
    <li>决定扩到 full 148 个 Goal O2，或先补 fresh / fresh-state 对照。</li>
    <li>把 index.html / provenance.json / videos 归档到 experiments。</li>
  </ol>
</div>
"""

    template = args.template.read_text(encoding="utf-8")
    replacements = {
        "{{TITLE}}": esc(args.title),
        "{{SUBTITLE}}": esc(
            f"LIBERO-PLUS O2 target-only rollback at all_done · {defaults.get('policy')} · "
            f"{total} planned cases · settle_after_injection={defaults.get('settle_after_injection', 0)} · "
            "stop-on-recovery"
        ),
        "{{STATUS_CLASS}}": status_class,
        "{{STATUS}}": esc(run_status),
        "{{GENERATED_AT}}": esc(generated),
        "{{RUN_DIR}}": esc(str(run)),
        "{{META}}": meta,
        "{{KPIS}}": kpis,
        "{{ARM_TABLE}}": arm_table,
        "{{LEVEL_TABLE}}": level_table,
        "{{LEVEL_BARS}}": bar_rows(level_bars),
        "{{TASK_TABLE}}": task_table,
        "{{FAILURES}}": "".join(failures),
        "{{VIDEO_COUNT}}": str(len(cards)),
        "{{VIDEO_CARDS}}": video_cards,
        "{{LEVEL_OPTIONS}}": level_opts,
        "{{TASK_OPTIONS}}": task_opts,
        "{{NOTES}}": notes,
    }
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)

    (out_dir / "index.html").write_text(rendered, encoding="utf-8")
    provenance = {
        "generated_at": generated,
        "run": repo_relative(run),
        "episodes": repo_relative(episodes_path),
        "template": repo_relative(args.template),
        "counts": {
            "completed": completed,
            "planned": total,
            "o2": len(o2),
            "o2_valid": len(o2_valid),
            "o2_recovered": len(o2_rec),
            "c0": len(c0),
            "c0_valid": len(c0_valid),
            "c0_success": len(c0_ok),
            "l0": len(l0),
            "l0_valid": len(l0_valid),
            "l0_recovered": len(l0_rec),
            "videos": len(vids),
        },
    }
    (out_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {out_dir / 'index.html'} ({completed}/{total} cases, {len(vids)} videos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
