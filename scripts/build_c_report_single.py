# ruff: noqa: E501
"""Single-page C matrix report with early/mid/later video columns."""

from __future__ import annotations

import html
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUN = REPO / "runs" / "c-matrix-pi05-20261121"
OUT = REPO / "experiments" / "c-matrix-pi05-20261121"
WINDOWS = ("early", "mid", "later")
LEVEL_ORDER = {"L0": 0, "L1": 1, "L2": 2}
PARAM_ORDER = {"": 0, "d03": 1, "d06": 2, "d10": 3, "r30": 4, "r60": 5, "r90": 6}


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def pct(k: int, n: int) -> str:
    return "—" if n <= 0 else f"{100 * k / n:.1f}%"


def rel(path: str | Path | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    return os.path.relpath(p, OUT).replace(os.sep, "/")


def status(r: dict | None) -> tuple[str, str]:
    if r is None:
        return "na", "missing"
    if not r.get("trigger_reached"):
        return "na", "N/A trigger"
    if not r.get("case_valid"):
        return "na", "invalid"
    if r.get("recovered"):
        return "ok", "recovered"
    return "bad", "not recovered"


CSS = """
body{margin:0;background:#fff;color:#1f2933;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1480px;margin:0 auto;padding:24px 20px 60px}h1{font-size:24px;margin:0 0 5px}.sub{color:#52606d;margin:0 0 12px;font-size:14px}
a{color:#2563eb;text-decoration:none}.kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px;margin:14px 0}
.kpi{border:1px solid #d9e2ec;border-radius:10px;padding:10px 12px}.kpi .l{font-size:12px;color:#52606d}.kpi .v{font-size:23px;font-weight:780}.kpi .s{font-size:11.5px;color:#7b8794}
table{width:100%;border-collapse:collapse;font-size:13px;border:1px solid #d9e2ec;border-radius:10px;overflow:hidden;margin:8px 0}th,td{padding:7px 9px;border-bottom:1px solid #d9e2ec;text-align:left}th{background:#f4f6f8;color:#52606d;font-size:12px}tr:last-child td{border-bottom:0}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}.note{background:#f7f8fa;border:1px solid #d9e2ec;border-left:4px solid #2563eb;border-radius:10px;padding:10px 12px;margin:10px 0;font-size:13px}
.filters{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.98);border:1px solid #d9e2ec;border-radius:10px;padding:8px 12px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:12px 0}
select,input{font:inherit;font-size:13px;padding:3px 6px;border:1px solid #d9e2ec;border-radius:6px;background:#fff}#count{margin-left:auto;color:#2563eb;font-weight:650;font-size:13px}
.row-head{display:flex;justify-content:space-between;gap:10px;align-items:baseline;margin:18px 0 6px;padding-top:12px;border-top:1px solid #d9e2ec}
.row-head h2{font-size:15px;margin:0}.row-head .meta{font-size:11.5px;color:#52606d}
.triple{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.cell{border:1px solid #d9e2ec;border-radius:9px;padding:7px;min-width:0}
.cell-head{display:flex;justify-content:space-between;align-items:center;gap:6px;margin-bottom:4px}.cell-head b{font-size:12px}.cell video{width:100%;aspect-ratio:4/5;background:#0b0f14;border-radius:6px;display:block}
.meta{font-size:10.8px;color:#52606d;margin-top:3px;line-height:1.4;overflow-wrap:anywhere}.badge{display:inline-block;padding:1px 6px;border-radius:999px;font-size:10.5px;border:1px solid #bbf7d0;background:#ecfdf3;color:#166534}.badge.bad{border-color:#fecdca;background:#fef3f2;color:#b42318}.badge.na{border-color:#e5e7eb;background:#f3f4f6;color:#4b5563}
.missing{display:flex;align-items:center;justify-content:center;aspect-ratio:4/5;background:#f7f8fa;border:1px dashed #d9e2ec;border-radius:6px;color:#7b8794;font-size:11px;text-align:center;padding:5px}
.row[hidden]{display:none}.small{font-size:11.5px;color:#7b8794}
@media(max-width:900px){.triple{grid-template-columns:1fr}}
"""


def main() -> int:
    data = [json.loads(line) for line in (RUN / "episodes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    OUT.mkdir(parents=True, exist_ok=True)

    groups: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in data:
        key = r["case_id"]
        for w in WINDOWS:
            key = key.replace(f"-{w}-", "-WINDOW-")
        groups[key][r["window"]] = r

    def group_sort(key: str):
        r = next(iter(groups[key].values()))
        return (int(r.get("task_idx") or 0), LEVEL_ORDER.get(r.get("level"), 9), PARAM_ORDER.get(r.get("param") or "", 9), key)

    # summary
    def stats(rs):
        v = [r for r in rs if r.get("case_valid")]
        return {
            "n": len(rs),
            "trigger": sum(1 for r in rs if r.get("trigger_reached")),
            "valid": len(v),
            "rec": sum(1 for r in v if r.get("recovered")),
            "sr": sum(1 for r in v if r.get("success")),
            "s2": sum(1 for r in v if r.get("s2_undisturbed_by_injection")),
        }

    total = stats(data)
    win_rows = []
    for w in WINDOWS:
        s = stats([r for r in data if r.get("window") == w])
        win_rows.append(
            f"<tr><td>{w}</td><td class='num'>{s['n']}</td><td class='num'>{s['trigger']} ({pct(s['trigger'], s['n'])})</td>"
            f"<td class='num'>{s['valid']}</td><td class='num'>{s['rec']} ({pct(s['rec'], s['valid'])})</td>"
            f"<td class='num'>{s['sr']} ({pct(s['sr'], s['valid'])})</td><td class='num'>{s['s2']}</td></tr>"
        )
    level_rows = []
    for lv in ("L0", "L1", "L2"):
        s = stats([r for r in data if r.get("level") == lv])
        level_rows.append(
            f"<tr><td>{lv}</td><td class='num'>{s['n']}</td><td class='num'>{s['valid']}</td>"
            f"<td class='num'>{s['rec']} ({pct(s['rec'], s['valid'])})</td><td class='num'>{s['sr']} ({pct(s['sr'], s['valid'])})</td></tr>"
        )

    reasons = Counter()
    for r in data:
        if r.get("case_valid"):
            continue
        if not r.get("trigger_reached"):
            reasons["trigger 未到"] += 1
        for k, v in (r.get("validity") or {}).items():
            if v is False:
                reasons[k] += 1
    reason_html = "".join(f"<tr><td>{esc(k)}</td><td class='num'>{v}</td></tr>" for k, v in reasons.items())

    rows_html = []
    for key in sorted(groups, key=group_sort):
        by_w = groups[key]
        base = next(iter(by_w.values()))
        task = base.get("bddl_name")
        level = base.get("level")
        param = base.get("param") or ""
        row_status = "recovered" if any(r.get("case_valid") and r.get("recovered") for r in by_w.values()) else ("invalid" if any(not r.get("case_valid") for r in by_w.values()) else "not_recovered")
        cells = []
        for w in WINDOWS:
            r = by_w.get(w)
            cls, label = status(r)
            if r is None:
                cells.append(f'<div class="cell"><div class="cell-head"><b>{w}</b><span class="badge na">missing</span></div><div class="missing">no case</div></div>')
                continue
            path = rel((r.get("video") or {}).get("path"))
            video = f'<video controls preload="metadata" playsinline muted loop src="{esc(path)}"></video>' if path else '<div class="missing">video missing</div>'
            cells.append(
                f'<div class="cell"><div class="cell-head"><b>{w}</b><span class="badge {cls}">{label}</span></div>{video}'
                f'<div class="meta">trigger {esc(r.get("trigger_step"))} · inject {esc(r.get("injection_step"))} · steps {esc(r.get("steps"))}<br>'
                f'valid {esc(r.get("case_valid"))} · recovered {esc(r.get("recovered"))} · SR {esc(r.get("success"))}</div></div>'
            )
        rows_html.append(
            f'<div class="row" data-task="{esc(task)}" data-level="{esc(level)}" data-status="{row_status}">'
            f'<div class="row-head"><h2>{esc(task)}</h2><div class="meta">{esc(level)}-{esc(param)} · <span class="small">{esc(key)}</span></div></div>'
            f'<div class="triple">{"".join(cells)}</div></div>'
        )

    task_options = "".join(f'<option value="{esc(t)}">{esc(t)}</option>' for t in sorted({r.get("bddl_name") for r in data}))
    html_text = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>C matrix · L10 in-execution rollback · pi05</title><style>{CSS}</style></head><body><div class="wrap">
<h1>C matrix · L10 in-execution rollback</h1>
<p class="sub">π0.5 · max_steps=600 + repair_window=600 · video · {len(data)}/180 cases · generated {esc(datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'))}</p>
<div class="kpis">
<div class="kpi"><div class="l">Completed</div><div class="v">{len(data)}/180</div><div class="s">{pct(len(data), 180)}</div></div>
<div class="kpi"><div class="l">Trigger</div><div class="v">{total['trigger']}/{total['n']}</div><div class="s">{pct(total['trigger'], total['n'])}</div></div>
<div class="kpi"><div class="l">Valid</div><div class="v">{total['valid']}</div><div class="s">denominator</div></div>
<div class="kpi"><div class="l">Recovery</div><div class="v">{total['rec']}/{total['valid']}</div><div class="s">{pct(total['rec'], total['valid'])}</div></div>
<div class="kpi"><div class="l">Full SR</div><div class="v">{total['sr']}/{total['valid']}</div><div class="s">{pct(total['sr'], total['valid'])}</div></div>
<div class="kpi"><div class="l">s2 preserved</div><div class="v">{total['s2']}/{total['valid']}</div><div class="s">{pct(total['s2'], total['valid'])}</div></div>
</div>
<table><thead><tr><th>window</th><th class="num">done</th><th class="num">trigger</th><th class="num">valid</th><th class="num">Recovery</th><th class="num">Full SR</th><th class="num">s2 ok</th></tr></thead><tbody>
{''.join(win_rows)}
</tbody></table>
<table><thead><tr><th>level</th><th class="num">done</th><th class="num">valid</th><th class="num">Recovery</th><th class="num">Full SR</th></tr></thead><tbody>
{''.join(level_rows)}
</tbody></table>
<table><thead><tr><th>invalid / N/A reason</th><th class="num">count</th></tr></thead><tbody>{reason_html}</tbody></table>
<div class="note"><b>视频证据：</b>下面每一行是同一 task/level/param 的 <b>early / mid / later</b> 三列。L0 是 baseline；L1/L2 才应看到注入后的差异。Recovery 只看 s1，Full SR 看全部原生 goal。<br><b>预算：</b>触发前最多 600 步；注入后恰好追加 600 步（total = injection_step + 600），不是固定 1200。C 无 C0。</div>
<div class="filters"><label>task <select id="task"><option value="all">all</option>{task_options}</select></label>
<label>level <select id="level"><option value="all">all</option><option>L0</option><option>L1</option><option>L2</option></select></label>
<label>status <select id="status"><option value="all">all</option><option value="recovered">any recovered</option><option value="not_recovered">none recovered</option><option value="invalid">any invalid/N/A</option></select></label>
<span id="count">{len(groups)} rows</span></div>
<div id="rows">{''.join(rows_html)}</div>
<script>
const rows=[...document.querySelectorAll('.row')],t=document.getElementById('task'),l=document.getElementById('level'),s=document.getElementById('status'),c=document.getElementById('count');
function apply(){{let n=0;rows.forEach(r=>{{const ok=(t.value==='all'||r.dataset.task===t.value)&&(l.value==='all'||r.dataset.level===l.value)&&(s.value==='all'||r.dataset.status===s.value);r.hidden=!ok;if(ok)n++;}});c.textContent=n+' rows';}}
[t,l,s].forEach(e=>e.onchange=apply);apply();
</script>
</div></body></html>"""
    (OUT / "index.html").write_text(html_text, encoding="utf-8")

    # remove the old per-window pages so the deliverable is one report
    for name in ("early.html", "mid.html", "later.html"):
        p = OUT / name
        if p.exists():
            p.unlink()
    print("wrote", OUT / "index.html", "groups", len(groups))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
