# ruff: noqa: E501
"""C matrix (in-execution rollback) report: summary + per-window video pages."""

from __future__ import annotations

import html
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUN = REPO / "runs" / "c-matrix-pi05-20261121"
OUT = REPO / "experiments" / "c-matrix-pi05-20261121"
PLANNED = 180


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


def rows() -> list[dict]:
    p = RUN / "episodes.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


CSS = """
body{margin:0;background:#fff;color:#1f2933;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1300px;margin:0 auto;padding:26px 22px 60px}h1{font-size:24px;margin:0 0 6px}.sub{color:#52606d;margin:0 0 14px}
a{color:#2563eb;text-decoration:none}.kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin:16px 0}
.kpi{border:1px solid #d9e2ec;border-radius:10px;padding:12px 14px}.kpi .l{font-size:12.5px;color:#52606d}.kpi .v{font-size:24px;font-weight:780}.kpi .s{font-size:12px;color:#7b8794}
table{width:100%;border-collapse:collapse;font-size:13px;border:1px solid #d9e2ec;border-radius:10px;overflow:hidden;margin:10px 0}th,td{padding:7px 9px;border-bottom:1px solid #d9e2ec;text-align:left}th{background:#f4f6f8;color:#52606d;font-size:12px}tr:last-child td{border-bottom:0}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}.note{background:#f7f8fa;border:1px solid #d9e2ec;border-left:4px solid #2563eb;border-radius:10px;padding:12px 14px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}.card{border:1px solid #d9e2ec;border-radius:10px;padding:10px}
.head{display:flex;justify-content:space-between;gap:8px;margin-bottom:5px;min-width:0}.head .mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
video{width:100%;aspect-ratio:4/5;background:#0b0f14;border-radius:7px}.meta{font-size:11.5px;color:#52606d;margin-top:4px;line-height:1.45}.badge{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;border:1px solid #bbf7d0;background:#ecfdf3;color:#166534}.badge.bad{border-color:#fecdca;background:#fef3f2;color:#b42318}.badge.na{border-color:#e5e7eb;background:#f3f4f6;color:#4b5563}.muted{color:#7b8794;font-size:11.5px}
.filters{position:sticky;top:0;background:#fff;border:1px solid #d9e2ec;border-radius:10px;padding:8px 12px;display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:10px 0}select{font:inherit;font-size:13px;padding:3px 6px;border:1px solid #d9e2ec;border-radius:6px}#count{margin-left:auto;color:#2563eb;font-weight:650;font-size:13px}
"""


def badge(r: dict) -> tuple[str, str]:
    if not r.get("trigger_reached"):
        return "na", "N/A trigger"
    if not r.get("case_valid"):
        return "na", "invalid"
    if r.get("recovered"):
        return "ok", "recovered"
    return "bad", "not recovered"


def main() -> int:
    data = rows()
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    by_window = {"early": [], "mid": [], "later": []}
    for r in data:
        if r.get("window") in by_window:
            by_window[r["window"]].append(r)

    def stats(rs: list[dict]) -> dict[str, int]:
        return {
            "n": len(rs),
            "trigger": sum(1 for r in rs if r.get("trigger_reached")),
            "valid": sum(1 for r in rs if r.get("case_valid")),
            "rec": sum(1 for r in rs if r.get("case_valid") and r.get("recovered")),
            "sr": sum(1 for r in rs if r.get("case_valid") and r.get("success")),
            "s2ok": sum(1 for r in rs if r.get("case_valid") and r.get("s2_undisturbed_by_injection")),
        }

    total = stats(data)
    rows_html = []
    for window, rs in by_window.items():
        s = stats(rs)
        rows_html.append(
            f"<tr><td><a href='{window}.html'>{window}</a></td><td class='num'>{s['n']}</td>"
            f"<td class='num'>{s['trigger']}/{s['n']} ({pct(s['trigger'], s['n'])})</td>"
            f"<td class='num'>{s['valid']}</td><td class='num'>{s['rec']}/{s['valid']} ({pct(s['rec'], s['valid'])})</td>"
            f"<td class='num'>{s['sr']}/{s['valid']} ({pct(s['sr'], s['valid'])})</td>"
            f"<td class='num'>{s['s2ok']}/{s['valid']} ({pct(s['s2ok'], s['valid'])})</td></tr>"
        )
    # by level
    level_rows = []
    for level in ("L0", "L1", "L2"):
        rs = [r for r in data if r.get("level") == level]
        s = stats(rs)
        level_rows.append(
            f"<tr><td>{level}</td><td class='num'>{s['n']}</td><td class='num'>{s['valid']}</td>"
            f"<td class='num'>{s['rec']}/{s['valid']} ({pct(s['rec'], s['valid'])})</td>"
            f"<td class='num'>{s['sr']}/{s['valid']} ({pct(s['sr'], s['valid'])})</td></tr>"
        )

    html_index = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>C matrix · L10 in-execution rollback · pi05</title><style>{CSS}</style></head><body><div class="wrap">
<h1>C matrix · L10 in-execution rollback</h1>
<p class="sub">π0.5 · max_steps=600 + repair_window=600 · video · {len(data)}/{PLANNED} cases · generated {esc(now)}</p>
<div class="kpis">
<div class="kpi"><div class="l">Completed</div><div class="v">{len(data)}/{PLANNED}</div><div class="s">{pct(len(data), PLANNED)}</div></div>
<div class="kpi"><div class="l">Trigger</div><div class="v">{total['trigger']}/{total['n']}</div><div class="s">{pct(total['trigger'], total['n'])}</div></div>
<div class="kpi"><div class="l">Valid</div><div class="v">{total['valid']}</div><div class="s">treatment denominator</div></div>
<div class="kpi"><div class="l">Recovery</div><div class="v">{total['rec']}/{total['valid']}</div><div class="s">{pct(total['rec'], total['valid'])}</div></div>
<div class="kpi"><div class="l">Full SR</div><div class="v">{total['sr']}/{total['valid']}</div><div class="s">{pct(total['sr'], total['valid'])}</div></div>
<div class="kpi"><div class="l">s2 preserved</div><div class="v">{total['s2ok']}/{total['valid']}</div><div class="s">{pct(total['s2ok'], total['valid'])}</div></div>
</div>
<table><thead><tr><th>window</th><th class="num">done</th><th class="num">trigger</th><th class="num">valid</th><th class="num">recovery</th><th class="num">full SR</th><th class="num">s2 preserved</th></tr></thead><tbody>
{''.join(rows_html)}
</tbody></table>
<table><thead><tr><th>level</th><th class="num">done</th><th class="num">valid</th><th class="num">recovery</th><th class="num">full SR</th></tr></thead><tbody>
{''.join(level_rows)}
</tbody></table>
<div class="note"><b>Recovery</b> 只看被撤销的 s1；<b>Full SR</b> 看全部原生 goal 原子；C 的 s2 仍 pending，所以 Recovery 可能高于 SR。门控：trigger 后注入有效、s1 假、s2 不受破坏。</div>
<div class="note"><b>预算：</b>触发前最多 600 步；注入后追加 600 步（total = injection_step + 600），不是固定 1200。C 没有 C0；窗口控制暂为 N/A。</div>
</div></body></html>"""
    (OUT / "index.html").write_text(html_index, encoding="utf-8")

    for window, rs in by_window.items():
        cards = []
        for r in sorted(rs, key=lambda x: x["case_id"]):
            cls, label = badge(r)
            path = rel((r.get("video") or {}).get("path"))
            video = f'<video controls preload="metadata" playsinline muted loop src="{esc(path)}"></video>' if path else '<div class="badge na">video missing</div>'
            cards.append(f'''<article class="card"><div class="head"><span class="mono">{esc(r['case_id'])}</span><span class="badge {cls}">{label}</span></div>{video}
<div class="meta"><b>{esc(r.get('level'))}-{esc(r.get('param') or '')}</b> · {esc(r.get('bddl_name'))}<br>
trigger {esc(r.get('trigger_step'))} · inject {esc(r.get('injection_step'))} · steps {esc(r.get('steps'))}<br>
trigger_reached {esc(r.get('trigger_reached'))} · valid {esc(r.get('case_valid'))} · recovered {esc(r.get('recovered'))} · SR {esc(r.get('success'))} · s2_ok {esc(r.get('s2_undisturbed_by_injection'))}</div></article>''')
        html_window = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>C {window} · video</title><style>{CSS}</style></head><body><div class="wrap"><p><a href="index.html">← C summary</a></p>
<h1>C matrix · {window} window · {len(rs)} cases</h1><p class="sub">逐 case 视频与读数；视频为 20 fps。</p>
<div class="grid">{''.join(cards)}</div></div></body></html>"""
        (OUT / f"{window}.html").write_text(html_window, encoding="utf-8")
        print("wrote", window, len(cards))
    print("wrote index", len(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
