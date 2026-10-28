#!/usr/bin/env python3
"""Build an index page that links the per-task HTML reports of one experiment.

Scans ``<run-root>/report-task*-v2/evidence.json`` and renders a compact summary
page with per-task metrics and links to the individual reports.

Usage:
    python scripts/build_report_index.py --run runs/retest-20261018
"""

from __future__ import annotations

import argparse
import html
import json
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def pct(k: int, n: int) -> str:
    return f"{(100.0 * k / n):.1f}%" if n else "—"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="experiment run root")
    parser.add_argument("--glob", default="report-task*-v2/evidence.json")
    parser.add_argument("--out", type=Path, default=None, help="output index.html path")
    args = parser.parse_args()

    run_root = args.run if args.run.is_absolute() else ROOT / args.run
    if not run_root.is_dir():
        raise SystemExit(f"run root not found: {run_root}")
    out = args.out or (run_root / "reports" / "index.html")
    if not out.is_absolute():
        out = ROOT / out

    entries = []
    for evidence_path in sorted(run_root.glob(args.glob)):
        report_dir = evidence_path.parent
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        totals = evidence.get("totals", {})
        meta = evidence.get("meta", {})
        task_index = None
        for case in evidence.get("cases", []):
            if case.get("task_index") is not None:
                task_index = int(case["task_index"])
                break
        report_html = report_dir / "index.html"
        if not report_html.is_file():
            continue
        report_rel = os.path.relpath(report_html, out.parent)
        evidence_rel = os.path.relpath(evidence_path, out.parent)
        entries.append({
            "task_index": task_index if task_index is not None else 99,
            "title": meta.get("title") or report_dir.name,
            "cases": totals.get("cases", 0),
            "valid": totals.get("valid", 0),
            "success": totals.get("success", 0),
            "recovered": totals.get("recovered", 0),
            "invalid": totals.get("invalid", 0),
            "probes": totals.get("probes", 0),
            "report": report_html,
            "evidence": evidence_path,
            "report_rel": report_rel,
            "evidence_rel": evidence_rel,
            "model": meta.get("model"),
            "max_steps": meta.get("max_steps"),
            "seeds": meta.get("seeds"),
        })
    if not entries:
        raise SystemExit(f"no report-task*-v2/evidence.json found under {run_root}")
    entries.sort(key=lambda item: item["task_index"])

    total_cases = sum(e["cases"] for e in entries)
    total_valid = sum(e["valid"] for e in entries)
    total_success = sum(e["success"] for e in entries)
    total_recovered = sum(e["recovered"] for e in entries)
    total_invalid = sum(e["invalid"] for e in entries)
    total_probes = sum(e["probes"] for e in entries)
    first = entries[0]
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    rows = []
    for e in entries:
        label = f"T{e['task_index']:02d}" if e["task_index"] != 99 else "未识别"
        rows.append(f'''<tr>
  <td class="mono">{label}</td>
  <td>{esc(e["title"])}</td>
  <td>{e["cases"]}</td>
  <td>{e["valid"]}/{e["cases"]}</td>
  <td>{e["success"]}/{e["valid"]}（{pct(e["success"], e["valid"])}）</td>
  <td>{e["recovered"]}</td>
  <td>{e["invalid"]}</td>
  <td>{e["probes"]}</td>
  <td><a href="{esc(e["report_rel"])}">打开报告</a> · <a href="{esc(e["evidence_rel"])}">evidence.json</a></td>
</tr>''')

    css = r"""
:root{--ink:#16232f;--muted:#5d7183;--line:#dbe4ec;--bg:#f5f8fb;--card:#fff;--accent:#1f5f9e;
--ok:#0f7a3d;--bad:#b3261e;--warn:#8a5a00}
*{box-sizing:border-box}
body{margin:0;padding:34px 22px 64px;font:15px/1.65 -apple-system,"Segoe UI","Noto Sans CJK SC",sans-serif;
color:var(--ink);background:var(--bg)}
.wrap{max-width:1200px;margin:0 auto}
h1{font-size:27px;margin:0 0 6px}
h2{font-size:20px;margin:32px 0 12px;padding-bottom:8px;border-bottom:2px solid var(--line)}
.sub{color:var(--muted);margin:0 0 18px}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}
.chip{border:1px solid var(--line);border-radius:10px;padding:10px 14px;background:#fbfdff;min-width:120px}
.chip b{display:block;font-size:21px}
.chip span{font-size:12px;color:var(--muted)}
.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0}
table.data{border-collapse:collapse;width:100%;font-size:13px;background:var(--card)}
table.data th,table.data td{border:1px solid var(--line);padding:7px 9px;text-align:left}
table.data th{background:#eef4f9}
tfoot td{font-weight:600;background:#f8fbfd}
a{color:var(--accent)}
.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px}
.note{color:var(--muted);font-size:12.5px}
"""

    html_text = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LIBERO-10 rollback 报告总览 · {esc(run_root.name)}</title>
<style>{css}</style></head><body><div class="wrap">
<h1>LIBERO-10 rollback 报告总览 · {esc(run_root.name)}</h1>
<p class="sub">按任务拆分的 HTML 报告索引；每份报告遵循 <span class="mono">docs/html-report-prompt.md v1.1</span>（实验介绍 / 结果总览 / 视频证据 / 方法 / 逐条结果）。生成时间：{esc(generated_at)}</p>
<div class="chips">
  <div class="chip"><b>{len(entries)}</b><span>任务报告</span></div>
  <div class="chip"><b>{total_cases}</b><span>用例条目数</span></div>
  <div class="chip"><b>{total_valid}/{total_cases}</b><span>注入有效（成功率分母）</span></div>
  <div class="chip"><b>{total_success}/{total_valid}</b><span>整体成功（{pct(total_success, total_valid)}）</span></div>
  <div class="chip"><b>{total_recovered}/{total_valid}</b><span>自修恢复</span></div>
  <div class="chip"><b>{total_invalid}</b><span>扰动未生效</span></div>
  <div class="chip"><b>{total_probes}</b><span>关系保持探针</span></div>
</div>
<div class="panel">
<table class="data"><thead><tr><th>任务</th><th>报告标题</th><th>用例条目数</th><th>注入有效</th><th>成功率 k/N</th><th>自修恢复</th><th>扰动未生效</th><th>探针</th><th>链接</th></tr></thead>
<tbody>{"".join(rows)}</tbody>
<tfoot><tr><td>合计</td><td>{len(entries)} 个任务</td><td>{total_cases}</td><td>{total_valid}</td><td>{total_success}/{total_valid}（{pct(total_success, total_valid)}）</td><td>{total_recovered}</td><td>{total_invalid}</td><td>{total_probes}</td><td>—</td></tr></tfoot>
</table>
<p class="note">模型 {esc(first.get("model") or "未记录")}；步数上限 {esc(first.get("max_steps") or "未记录")}；seeds {esc(first.get("seeds"))}；运行目录 <span class="mono">{esc(run_root.as_posix())}</span>。成功率分母 = 基线成功且注入有效条目；各任务口径与可视化见对应报告。</p>
</div>
<p class="note">生成脚本：<span class="mono">scripts/build_report_index.py</span>；单任务报告由 <span class="mono">scripts/build_standard_task_report.py</span> 生成。</p>
</div></body></html>'''
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8")
    print(f"index: {out} ({out.stat().st_size} bytes), {len(entries)} reports, totals "
          f"success={total_success}/{total_valid} invalid={total_invalid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
