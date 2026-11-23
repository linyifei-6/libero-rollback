# ruff: noqa: E501
"""Full video index for the completed Goal static-init ablation."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "experiments" / "b-rollback-static-20261120"
RUNS = [REPO / "runs" / "b-static-goal-20261120", REPO / "runs" / "b-static-goal-l2-20261120"]


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


rows = []
for run in RUNS:
    path = run / "episodes.jsonl"
    if path.exists():
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
rows = [r for r in rows if r.get("static_init")]
rows.sort(key=lambda r: (r["level"], r.get("param") or "", r["case_id"]))

cards = []
for r in rows:
    video = (r.get("video") or {}).get("path")
    rel = os.path.relpath(video, OUT).replace(os.sep, "/") if video and os.path.exists(video) else ""
    status = "success" if r.get("success") else "fail"
    cls = "ok" if status == "success" else "bad"
    cards.append(
        f'<article class="card" data-level="{esc(r["level"])}" data-status="{status}">'
        f'<div class="head"><span class="mono">{esc(r["case_id"])}</span><span class="badge {cls}">{status}</span></div>'
        f'<video controls preload="metadata" playsinline muted loop src="{esc(rel)}"></video>'
        f'<div class="meta">{esc(r["level"])}-{esc(r.get("param") or "")} · steps {esc(r.get("steps"))} · first_success {esc(r.get("first_success_step"))}</div></article>'
    )

html_text = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Goal static-init · 全量视频</title><style>
body{{margin:0;background:#fff;color:#1f2933;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1240px;margin:0 auto;padding:26px 22px 60px}}h1{{font-size:24px;margin:0 0 6px}}.sub{{color:#52606d;margin:0 0 14px}}
.filters{{position:sticky;top:0;background:#fff;border:1px solid #d9e2ec;border-radius:10px;padding:8px 12px;display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin:10px 0}}
select{{font:inherit;font-size:13px;padding:3px 6px;border:1px solid #d9e2ec;border-radius:6px}}#count{{margin-left:auto;color:#2563eb;font-weight:650}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}.card{{border:1px solid #d9e2ec;border-radius:10px;padding:10px}}.card[hidden]{{display:none}}
.head{{display:flex;justify-content:space-between;gap:8px;margin-bottom:6px;min-width:0}}.head .mono{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px}}
video{{width:100%;aspect-ratio:4/5;background:#0b0f14;border-radius:7px}}.meta{{font-size:12px;color:#52606d;margin-top:6px}}
.badge{{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;border:1px solid #bbf7d0;background:#ecfdf3;color:#166534}}.badge.bad{{border-color:#fecdca;background:#fef3f2;color:#b42318}}
</style></head><body><div class="wrap">
<h1>Goal static-init · 全量视频</h1>
<p class="sub">75 条（L0 12 + L1 36 + L2 27），每条都有 video.mp4；这是完整索引，不是代表样本。</p>
<div class="filters"><label>level <select id="level"><option value="all">all</option><option>L0</option><option>L1</option><option>L2</option></select></label>
<label>status <select id="status"><option value="all">all</option><option>success</option><option>fail</option></select></label><span id="count">{len(cards)} shown</span></div>
<div class="grid" id="grid">{''.join(cards)}</div>
<script>
const cards=[...document.querySelectorAll('.card')], lv=document.getElementById('level'), st=document.getElementById('status'), cnt=document.getElementById('count');
function apply(){{let n=0;cards.forEach(c=>{{const ok=(lv.value==='all'||c.dataset.level===lv.value)&&(st.value==='all'||c.dataset.status===st.value);c.hidden=!ok;if(ok)n++;}});cnt.textContent=n+' shown';}}
lv.onchange=apply;st.onchange=apply;
</script></div></body></html>"""
(OUT / "goal-all-videos.html").write_text(html_text, encoding="utf-8")
print("wrote", OUT / "goal-all-videos.html", "cards", len(cards))
