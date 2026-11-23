# ruff: noqa: E501
"""Regression report for the t033/t078/t133 window fixes."""

from __future__ import annotations

import html
import json
import os
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "experiments" / "c-regression-20261122"
ROOTS = {t: REPO / "runs/c-regression-20261122" / t for t in ("t033", "t078", "t133")}
ROOTS["t033"] = REPO / "runs/c-regression-20261122" / "t033-final"
ROOTS["t133"] = REPO / "runs/c-regression-20261122" / "t133-dynamic"
WINDOWS = ("early", "mid", "later")
LEVELS = ("L0", "L1", "L2")


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def pct(k: int, n: int) -> str:
    return "—" if not n else f"{100*k/n:.1f}%"


def rel(path: str | Path | None) -> str:
    if not path:
        return ""
    p = Path(path)
    return os.path.relpath(p, OUT).replace(os.sep, "/") if p.exists() else ""


rows = []
for task, root in ROOTS.items():
    data = [json.loads(line) for line in (root / "episodes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in data:
        r["_task"] = task
    rows.extend(data)

def stats(rs):
    v = [r for r in rs if r.get("case_valid")]
    return len(rs), sum(1 for r in rs if r.get("trigger_reached")), len(v), sum(1 for r in v if r.get("recovered")), sum(1 for r in v if r.get("success"))

task_rows = []
for task in ("t033", "t078", "t133"):
    n, trig, valid, rec, sr = stats([r for r in rows if r["_task"] == task])
    task_rows.append(f"<tr><td>{task}</td><td class='num'>{n}</td><td class='num'>{trig}</td><td class='num'>{valid}</td><td class='num'>{rec} ({pct(rec, valid)})</td><td class='num'>{sr} ({pct(sr, valid)})</td></tr>")

window_rows = []
for task in ("t033", "t078", "t133"):
    for w in WINDOWS:
        n, trig, valid, rec, sr = stats([r for r in rows if r["_task"] == task and r.get("window") == w])
        window_rows.append(f"<tr><td>{task}</td><td>{w}</td><td class='num'>{n}</td><td class='num'>{trig}</td><td class='num'>{valid}</td><td class='num'>{rec} ({pct(rec,valid)})</td><td class='num'>{sr} ({pct(sr,valid)})</td></tr>")

invalid = Counter()
for r in rows:
    if r.get("case_valid"):
        continue
    if not r.get("trigger_reached"):
        invalid["trigger 未到"] += 1
    for k, v in (r.get("validity") or {}).items():
        if v is False:
            invalid[k] += 1
invalid_rows = "".join(f"<tr><td>{esc(k)}</td><td class='num'>{v}</td></tr>" for k, v in invalid.items())

cards = []
for r in sorted(rows, key=lambda x: (("t033","t078","t133").index(x["_task"]), WINDOWS.index(x.get("window")), LEVELS.index(x.get("level")), x.get("param") or "")):
    cls = "ok" if r.get("case_valid") and r.get("recovered") else ("bad" if r.get("case_valid") else "na")
    label = "recovered" if r.get("case_valid") and r.get("recovered") else ("not recovered" if r.get("case_valid") else "invalid/N/A")
    path = rel((r.get("video") or {}).get("path"))
    video = f'<video controls preload="metadata" playsinline muted loop src="{esc(path)}"></video>' if path else '<div class="missing">no video</div>'
    cards.append(
        f'<div class="card" data-task="{r["_task"]}" data-level="{esc(r.get("level"))}" data-window="{esc(r.get("window"))}" data-status="{esc(label)}">'
        f'<div class="head"><b>{r["_task"]} · {esc(r.get("window"))} · {esc(r.get("level"))}-{esc(r.get("param") or "")}</b><span class="badge {cls}">{label}</span></div>'
        f'{video}<div class="meta">trigger {esc(r.get("trigger_step"))} · inject {esc(r.get("injection_step"))} · steps {esc(r.get("steps"))}<br>'
        f'valid {esc(r.get("case_valid"))} · recovered {esc(r.get("recovered"))} · SR {esc(r.get("success"))}<br>{esc(r.get("case_id"))}</div></div>'
    )

html_text = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>C regression · t033/t078/t133</title><style>
body{{margin:0;background:#fff;color:#1f2933;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1500px;margin:0 auto;padding:24px 20px 60px}}h1{{font-size:24px;margin:0 0 5px}}.sub{{color:#52606d;margin:0 0 12px;font-size:13.5px}}
table{{width:100%;border-collapse:collapse;font-size:12.5px;border:1px solid #d9e2ec;border-radius:9px;overflow:hidden;margin:8px 0}}th,td{{padding:6px 8px;border-bottom:1px solid #d9e2ec;text-align:left}}th{{background:#f4f6f8;color:#52606d}}td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}
.filters{{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.98);border:1px solid #d9e2ec;border-radius:9px;padding:8px 10px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:10px 0}}select{{font:inherit;font-size:13px;padding:3px 6px;border:1px solid #d9e2ec;border-radius:6px}}#count{{margin-left:auto;color:#2563eb;font-weight:650}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px}}.card{{border:1px solid #d9e2ec;border-radius:9px;padding:7px;min-width:0}}.head{{display:flex;justify-content:space-between;gap:6px;align-items:center;margin-bottom:4px;font-size:11.5px}}video{{width:100%;aspect-ratio:4/5;background:#0b0f14;border-radius:6px;display:block}}
.meta{{font-size:10.8px;color:#52606d;margin-top:3px;line-height:1.45;overflow-wrap:anywhere}}.badge{{display:inline-block;padding:1px 6px;border-radius:999px;font-size:10.5px;border:1px solid #bbf7d0;background:#ecfdf3;color:#166534;white-space:nowrap}}.badge.bad{{border-color:#fecdca;background:#fef3f2;color:#b42318}}.badge.na{{border-color:#e5e7eb;background:#f3f4f6;color:#4b5563}}.missing{{display:flex;align-items:center;justify-content:center;aspect-ratio:4/5;background:#f7f8fa;border:1px dashed #d9e2ec;border-radius:6px;color:#7b8794}}.note{{background:#f7f8fa;border:1px solid #d9e2ec;border-left:4px solid #2563eb;border-radius:9px;padding:10px 12px;margin:9px 0;font-size:12.5px}}.card[hidden]{{display:none}}
</style></head><body><div class="wrap">
<h1>C 回归测试 · t033 / t078 / t133</h1>
<p class="sub">π0.5 · 600+600 · video · 63 cases（每任务 21 = 3 windows × 7 levels）</p>
<div class="note"><b>改动：</b>t033 early 在 s1 后 20 步、释放后、碰把手过程中触发；mid 在 s2 开始（接触把手），later 在 s2 开始且释放后、progress 0.20（推门）。t078 mid 在门开始动（0.05）、later 0.65。t133 现在由 runner 在运行时选择第一个完成的目标作为 s1；本轮 seed 0 选择 moka_pot_2，s2=moka_pot_1。t078 的 0 Recovery 是模型表现，翻转/穿模已按审核确认解决。</div>
<table><thead><tr><th>task</th><th class="num">cases</th><th class="num">trigger</th><th class="num">valid</th><th class="num">Recovery</th><th class="num">Full SR</th></tr></thead><tbody>{''.join(task_rows)}</tbody></table>
<table><thead><tr><th>task</th><th>window</th><th class="num">cases</th><th class="num">trigger</th><th class="num">valid</th><th class="num">Recovery</th><th class="num">Full SR</th></tr></thead><tbody>{''.join(window_rows)}</tbody></table>
<table><thead><tr><th>invalid / N/A reason</th><th class="num">count</th></tr></thead><tbody>{invalid_rows}</tbody></table>
<div class="filters"><label>task <select id="task"><option value="all">all</option><option>t033</option><option>t078</option><option>t133</option></select></label>
<label>level <select id="level"><option value="all">all</option><option>L0</option><option>L1</option><option>L2</option></select></label>
<label>window <select id="window"><option value="all">all</option><option>early</option><option>mid</option><option>later</option></select></label>
<label>status <select id="status"><option value="all">all</option><option>recovered</option><option>not recovered</option><option>invalid/N/A</option></select></label>
<span id="count"></span></div>
<div class="grid" id="grid">{''.join(cards)}</div>
<script>const cards=[...document.querySelectorAll('.card')],ts=document.getElementById('task'),lv=document.getElementById('level'),wd=document.getElementById('window'),st=document.getElementById('status'),ct=document.getElementById('count');function run(){{let n=0;cards.forEach(c=>{{const ok=(ts.value==='all'||c.dataset.task===ts.value)&&(lv.value==='all'||c.dataset.level===lv.value)&&(wd.value==='all'||c.dataset.window===wd.value)&&(st.value==='all'||c.dataset.status===st.value);c.hidden=!ok;if(ok)n++;}});ct.textContent=n+' cases';}}[ts,lv,wd,st].forEach(e=>e.onchange=run);run();</script>
</div></body></html>"""
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "index.html").write_text(html_text, encoding="utf-8")
print("wrote", OUT / "index.html", "cases", len(rows))
