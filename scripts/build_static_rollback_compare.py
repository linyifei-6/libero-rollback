# ruff: noqa: E501
"""Side-by-side static vs rollback video review report."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "experiments" / "b-rollback-static-compare-20261121"
STATIC_RUNS = {
    "goal": REPO / "runs" / "b-static-exact-goal-20261121",
    "object": REPO / "runs" / "b-static-exact-object-20261121",
    "spatial": REPO / "runs" / "b-static-exact-spatial-20261121",
    "l10": REPO / "runs" / "b-static-exact-l10-20261121",
}
GO_VIDEOS = REPO / "experiments" / "b-rollback" / "report-goal-object-20261118" / "videos"
L10_VIDEOS = REPO / "runs" / "b-rollback-l10-20261120"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def rel(path: str | Path | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    return os.path.relpath(p, OUT).replace(os.sep, "/")


static_rows: list[dict] = []
for suite, run in STATIC_RUNS.items():
    for row in read_jsonl(run / "episodes.jsonl"):
        row["_suite"] = suite
        static_rows.append(row)
static_rows.sort(key=lambda r: (r["_suite"], r["level"], r.get("param") or "", r["case_id"]))

# rollback metadata
rb_meta: dict[str, dict] = {}
for row in read_jsonl(REPO / "experiments" / "b-rollback" / "report-goal-object-20261118" / "cases.jsonl"):
    rb_meta[row["case_id"]] = row
for name in ("spatial-part1.json", "spatial-part2.json"):
    data = json.loads((REPO / "experiments" / "b-rollback" / "report-spatial-20261118" / name).read_text(encoding="utf-8"))
    for row in data.get("cases") or []:
        cid = row.get("case_id") or row.get("id")
        if cid:
            rb_meta[cid] = row
for row in read_jsonl(L10_VIDEOS / "episodes.jsonl"):
    rb_meta[row["case_id"]] = row


def rollback_video(case_id: str) -> Path | None:
    if case_id.startswith(("b-goal-", "b-object-")):
        path = GO_VIDEOS / f"{case_id}.mp4"
        return path if path.exists() else None
    if case_id.startswith("b-l10-"):
        path = L10_VIDEOS / "l10" / case_id / "seed-0" / "video.mp4"
        return path if path.exists() else None
    return None


def rollback_status(row: dict | None) -> str:
    if row is None:
        return "no_rollback"
    if "injection_valid" not in row and "case_valid" not in row:
        return "no_rollback"
    valid = bool(row.get("injection_valid", row.get("case_valid")))
    if not row.get("trigger_reached", True):
        return "n/a"
    if not valid:
        return "invalid"
    return "recovered" if row.get("recovered") else "not_recovered"


def static_status(row: dict) -> str:
    if not row.get("case_valid"):
        return "invalid"
    return "success" if row.get("success") else "fail"


badge = {
    "success": ("ok", "static success"),
    "fail": ("bad", "static fail"),
    "invalid": ("na", "static invalid"),
    "recovered": ("ok", "rollback recovered"),
    "not_recovered": ("bad", "rollback not recovered"),
    "invalid_rollback": ("na", "rollback invalid"),
    "n/a": ("na", "rollback N/A"),
    "no_rollback": ("na", "no rollback video"),
}

cards = []
paired = 0
for r in static_rows:
    cid = r["case_id"]
    sstatus = static_status(r)
    svideo = rel((r.get("video") or {}).get("path"))
    rb = rb_meta.get(cid)
    rstatus = rollback_status(rb)
    rvideo_path = rollback_video(cid)
    rvideo = rel(rvideo_path)
    if rvideo:
        paired += 1
    left_video = f'<video controls preload="metadata" playsinline muted loop src="{esc(svideo)}"></video>' if svideo else '<div class="missing">static video missing</div>'
    if rvideo:
        right_video = f'<video controls preload="metadata" playsinline muted loop src="{esc(rvideo)}"></video>'
    else:
        right_video = f'<div class="missing">rollback video not available locally<br><span class="mono">{esc(cid)}</span></div>'
    scls, slabel = badge[sstatus]
    rbadge = {
        "recovered": ("ok", "rollback recovered"),
        "not_recovered": ("bad", "rollback not recovered"),
        "invalid": ("na", "rollback invalid"),
        "n/a": ("na", "rollback N/A"),
        "no_rollback": ("na", "no rollback video"),
    }
    rcls, rlabel = rbadge.get(rstatus, ("na", rstatus))
    cards.append(f'''
<article class="card" data-suite="{esc(r['_suite'])}" data-level="{esc(r['level'])}" data-static="{sstatus}" data-rollback="{rstatus}">
  <div class="card-head"><span class="mono">{esc(cid)}</span><span class="muted">{esc(r['_suite'])} / {esc(r['level'])}-{esc(r.get('param') or '')}</span></div>
  <div class="pair">
    <div class="side"><div class="side-head"><span class="badge {scls}">{slabel}</span><span class="muted">t=0</span></div>{left_video}<div class="meta">steps {esc(r.get('steps'))} · first_success {esc(r.get('first_success_step'))} · valid {esc(r.get('case_valid'))}</div></div>
    <div class="side"><div class="side-head"><span class="badge {rcls}">{rlabel}</span><span class="muted">all_done</span></div>{right_video}<div class="meta">{esc((rb or {}).get('relation_final', rb.get('recovered') if rb else '—'))}</div></div>
  </div>
</article>''')

html_text = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>base-rollback · static vs rollback 对照视频</title>
<style>
body{{margin:0;background:#fff;color:#1f2933;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1500px;margin:0 auto;padding:24px 20px 60px}}h1{{font-size:24px;margin:0 0 6px}}.sub{{color:#52606d;margin:0 0 14px}}
.filters{{position:sticky;top:0;z-index:10;background:#fff;border:1px solid #d9e2ec;border-radius:10px;padding:8px 12px;display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:10px 0}}
select{{font:inherit;font-size:13px;padding:3px 6px;border:1px solid #d9e2ec;border-radius:6px}}#count{{margin-left:auto;color:#2563eb;font-weight:650;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:16px}}
.card{{border:1px solid #d9e2ec;border-radius:12px;padding:12px;background:#fff;box-shadow:0 1px 2px rgba(16,24,40,.05)}}.card[hidden]{{display:none}}
.card-head{{display:flex;justify-content:space-between;gap:10px;margin-bottom:8px;min-width:0}}.card-head .mono{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.side{{min-width:0}}.side-head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}}
video{{width:100%;aspect-ratio:4/5;background:#0b0f14;border-radius:8px;display:block}}.meta{{font-size:11.5px;color:#52606d;margin-top:4px;overflow-wrap:anywhere}}
.badge{{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11.5px;border:1px solid #bbf7d0;background:#ecfdf3;color:#166534}}.badge.bad{{border-color:#fecdca;background:#fef3f2;color:#b42318}}.badge.na{{border-color:#e5e7eb;background:#f3f4f6;color:#4b5563}}
.missing{{display:flex;align-items:center;justify-content:center;aspect-ratio:4/5;background:#f7f8fa;border:1px dashed #d9e2ec;border-radius:8px;color:#7b8794;font-size:12px;text-align:center;padding:8px}}
.note{{background:#f7f8fa;border:1px solid #d9e2ec;border-left:4px solid #2563eb;border-radius:10px;padding:12px 14px;margin:12px 0}}.mono{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px}}.muted{{color:#7b8794;font-size:11.5px}}
</style></head><body><div class="wrap">
<h1>base-rollback · static vs rollback 对照视频</h1>
<p class="sub">左：t=0 static 注入；右：all_done rollback。每条 static 视频都有；rollback 视频本地可用 {paired}/{len(cards)} 条（Spatial 的 rollback 视频未迁移）。</p>
<div class="note"><b>怎么看：</b>static 视频开头应出现 <span class="mono">STATIC-INIT</span> 卡片；L0 是 baseline（无扰动），L1/L2 应看到 target 在 t=0 已位移/旋转。右边 rollback 视频是任务完成后再注入；若右侧缺失，只说明视频未迁移，不是实验没跑。</div>
<div class="filters">
<label>suite <select id="suite"><option value="all">all</option><option>goal</option><option>object</option><option>spatial</option><option>l10</option></select></label>
<label>level <select id="level"><option value="all">all</option><option>L0</option><option>L1</option><option>L2</option></select></label>
<label>static <select id="sstatus"><option value="all">all</option><option>success</option><option>fail</option><option>invalid</option></select></label>
<label>rollback <select id="rstatus"><option value="all">all</option><option>recovered</option><option>not_recovered</option><option>invalid</option><option>n/a</option><option>no_rollback</option></select></label>
<span id="count">{len(cards)} shown</span></div>
<div class="grid" id="grid">{''.join(cards)}</div>
<script>
const cards=[...document.querySelectorAll('.card')],els=['suite','level','sstatus','rstatus'].map(id=>document.getElementById(id)),cnt=document.getElementById('count');
function apply(){{let n=0;cards.forEach(c=>{{const ok=els.every((el,i)=>{{const key=['suite','level','static','rollback'][i];return el.value==='all'||c.dataset[key]===el.value;}});c.hidden=!ok;if(ok)n++;}});cnt.textContent=n+' shown';}}
els.forEach(el=>el.onchange=apply);apply();
</script></div></body></html>"""
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "index.html").write_text(html_text, encoding="utf-8")
print("wrote", OUT / "index.html", "cards", len(cards), "paired", paired)
