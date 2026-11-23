# ruff: noqa: E501
"""L0 audit report for t033/t078/t133 window fixes."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "experiments" / "c-l0-audit-20261122"
CASES = {
    "t033": {
        "early": REPO / "runs/c-l0-audit/t033-v2/l10/d-l10-t033-early-l0/seed-0/summary.json",
        "mid": REPO / "runs/c-l0-audit/t033/l10/d-l10-t033-mid-l0/seed-0/summary.json",
        "later": REPO / "runs/c-l0-audit/t033/l10/d-l10-t033-later-l0/seed-0/summary.json",
    },
    "t078": {
        w: REPO / f"runs/c-l0-audit/t078/l10/d-l10-t078-{w}-l0/seed-0/summary.json"
        for w in ("early", "mid", "later")
    },
    "t133": {
        w: REPO / f"runs/c-l0-audit/t133/l10/d-l10-t133-{w}-l0/seed-0/summary.json"
        for w in ("early", "mid", "later")
    },
}


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def rel(p: str | Path | None) -> str:
    if not p:
        return ""
    p = Path(p)
    return os.path.relpath(p, OUT).replace(os.sep, "/") if p.exists() else ""


rows = []
for task, by_w in CASES.items():
    for w in ("early", "mid", "later"):
        d = json.loads(by_w[w].read_text(encoding="utf-8"))
        s2 = d.get("s2_at_trigger") or {}
        rows.append(
            {
                "task": task,
                "window": w,
                "case": d.get("case_id"),
                "trigger": d.get("trigger_step"),
                "s1": d.get("s1_done_step"),
                "s2start": d.get("s2_started_step"),
                "progress": s2.get("progress"),
                "valid": d.get("case_valid"),
                "rec": d.get("recovered"),
                "video": rel((d.get("video") or {}).get("path")),
                "s2": s2,
                "revoked": d.get("revoked_objects"),
                "injection_step": d.get("injection_step"),
            }
        )

# group by task
by_task = {}
for r in rows:
    by_task.setdefault(r["task"], {})[r["window"]] = r

cards = []
for task in ("t033", "t078", "t133"):
    cells = []
    for w in ("early", "mid", "later"):
        r = by_task[task][w]
        cls = "ok" if r["valid"] and r["rec"] else ("bad" if r["valid"] else "na")
        label = "recovered" if r["valid"] and r["rec"] else ("valid / no recovery" if r["valid"] else "invalid")
        video = f'<video controls preload="metadata" playsinline muted loop src="{esc(r["video"])}"></video>' if r["video"] else '<div class="missing">video missing</div>'
        cells.append(
            f'<div class="cell"><div class="cell-head"><b>{w}</b><span class="badge {cls}">{label}</span></div>{video}'
            f'<div class="meta">trigger {r["trigger"]} · s1 {r["s1"]} · s2_start {r["s2start"]}<br>'
            f's2 progress {r["progress"]} · inject {r["injection_step"]}<br>revoked {esc(r["revoked"])}</div></div>'
        )
    cards.append(
        f'<section class="task"><h2>{task}</h2><div class="triple">{"".join(cells)}</div></section>'
    )

html_text = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>C L0 audit · t033/t078/t133</title><style>
body{{margin:0;background:#fff;color:#1f2933;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1400px;margin:0 auto;padding:26px 22px 60px}}h1{{font-size:25px;margin:0 0 6px}}.sub{{color:#52606d;margin:0 0 12px}}
h2{{font-size:17px;margin:20px 0 8px;padding-top:12px;border-top:1px solid #d9e2ec}}.task{{margin:18px 0}}
.triple{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}}.cell{{border:1px solid #d9e2ec;border-radius:9px;padding:8px}}
.cell-head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}}video{{width:100%;aspect-ratio:4/5;background:#0b0f14;border-radius:6px}}
.meta{{font-size:11px;color:#52606d;margin-top:4px;line-height:1.45}}.badge{{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;border:1px solid #bbf7d0;background:#ecfdf3;color:#166534}}
.badge.bad{{border-color:#fecdca;background:#fef3f2;color:#b42318}}.badge.na{{border-color:#e5e7eb;background:#f3f4f6;color:#4b5563}}
.note{{background:#f7f8fa;border:1px solid #d9e2ec;border-left:4px solid #2563eb;border-radius:10px;padding:10px 12px;margin:10px 0;font-size:13px}}
.missing{{display:flex;align-items:center;justify-content:center;aspect-ratio:4/5;background:#f7f8fa;border:1px dashed #d9e2ec;border-radius:6px;color:#7b8794}}
</style></head><body><div class="wrap">
<h1>C 矩阵 · L0 三任务窗口验证</h1>
<p class="sub">t033 / t078 / t133，early / mid / later，π0.5，600+600，video。用于审核触发时机与 s1/s2 选择。</p>
<div class="note"><b>t033：</b>early 改为要求 s2 已经开始，mid/later 用 joint progress 0.50 / 0.85；现在 early 在 s2 开始（progress≈0.07），mid≈0.53，later≈0.87。</div>
<div class="note"><b>t078：</b>mid 已改为 s2 开始即触发（door progress≈0.10）；later 仍被 s1 的反复 true/false 拖到 progress≈0.92。注入前 C 代码只读，不写状态；马克杯翻转需要从策略/接触物理排查。</div>
<div class="note"><b>t133：</b>本版按 seed 0 实际顺序把 s1 改为先放置的 moka_pot_2，s2=moka_pot_1；early/mid/later 分别 203/318/400。注意这是顺序特定的验证，不是运行时自动识别。</div>
<div class="note"><b>结论标记：</b>9 条都 trigger=True、valid=True；但 recovered 都是 False。这里先审核“时机/目标是否对”，不是最终 recovery 结论。</div>
{''.join(cards)}
</div></body></html>"""
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "index.html").write_text(html_text, encoding="utf-8")
print("wrote", OUT / "index.html", "cards", len(rows))
