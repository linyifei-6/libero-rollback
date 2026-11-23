# ruff: noqa: E501
"""Seed=1 C matrix report with case-level evidence filters."""

from __future__ import annotations

import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUN = REPO / "runs" / "c-matrix-pi05-20261123-seed1-fixed"
OUT = REPO / "experiments" / "c-matrix-seed1-20261123"
WINDOWS = ("early", "mid", "later")
LEVEL_ORDER = {"L0": 0, "L1": 1, "L2": 2}
PARAM_ORDER = {"": 0, "d03": 1, "d06": 2, "d10": 3, "r30": 4, "r60": 5, "r90": 6}

# `restorable` is auxiliary: it is reported but does not invalidate a case.
HARD_GATES = (
    "completed_relation_true_before_intervention",
    "all_revoked_false_after_intervention",
    "no_object_penetration",
    "zero_velocity_after_intervention",
    "object_released_before_intervention",
    "s2_undisturbed_by_injection",
)
REASON_LABEL = {
    "completed_relation_true_before_intervention": "注入前 s1 不为真",
    "all_revoked_false_after_intervention": "注入后 s1 未撤销",
    "no_object_penetration": "穿模",
    "zero_velocity_after_intervention": "非零速度",
    "object_released_before_intervention": "机器人未释放",
    "s2_undisturbed_by_injection": "s2 被扰动",
}
OUTCOME_LABEL = {
    "success": "任务成功",
    "recovered_task_failed": "恢复成功但任务失败",
    "not_recovered": "恢复失败",
    "invalid": "无效",
}


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def pct(k: int, n: int) -> str:
    return "—" if n <= 0 else f"{100*k/n:.1f}%"


def rel(path: str | Path | None) -> str:
    if not path:
        return ""
    p = Path(path)
    return os.path.relpath(p, OUT).replace(os.sep, "/") if p.exists() else ""


def is_valid(r: dict | None) -> bool:
    if r is None or not r.get("trigger_reached"):
        return False
    validity = r.get("validity") or {}
    return all(validity.get(key) is True for key in HARD_GATES)


def invalid_reasons(r: dict) -> list[str]:
    out: list[str] = []
    if not r.get("trigger_reached"):
        out.append("trigger")
    validity = r.get("validity") or {}
    for key in HARD_GATES:
        if validity.get(key) is False:
            out.append(key)
    return out


def outcome(r: dict | None) -> str:
    if not is_valid(r):
        return "invalid"
    if r.get("success"):
        return "success"
    if r.get("recovered"):
        return "recovered_task_failed"
    return "not_recovered"


def status(r: dict | None) -> tuple[str, str]:
    if r is None:
        return "na", "missing"
    if not is_valid(r):
        return "na", "无效"
    if r.get("success"):
        return "ok", "任务成功"
    if r.get("recovered"):
        return "bad", "恢复但任务失败"
    return "bad", "恢复失败"


CSS = """
body{margin:0;background:#fff;color:#1f2933;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1480px;margin:0 auto;padding:24px 20px 60px}h1{font-size:24px;margin:0 0 5px}.sub{color:#52606d;margin:0 0 12px;font-size:14px}
a{color:#2563eb;text-decoration:none}.kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px;margin:14px 0}
.kpi{border:1px solid #d9e2ec;border-radius:10px;padding:10px 12px}.kpi .l{font-size:12px;color:#52606d}.kpi .v{font-size:23px;font-weight:780}.kpi .s{font-size:11.5px;color:#7b8794}
table{width:100%;border-collapse:collapse;font-size:13px;border:1px solid #d9e2ec;border-radius:10px;overflow:hidden;margin:8px 0}th,td{padding:7px 9px;border-bottom:1px solid #d9e2ec;text-align:left}th{background:#f4f6f8;color:#52606d;font-size:12px}tr:last-child td{border-bottom:0}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}.note{background:#f7f8fa;border:1px solid #d9e2ec;border-left:4px solid #2563eb;border-radius:10px;padding:10px 12px;margin:10px 0;font-size:13px}
.filters{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.98);border:1px solid #d9e2ec;border-radius:10px;padding:8px 12px;display:flex;gap:9px;flex-wrap:wrap;align-items:center;margin:12px 0}
select{font:inherit;font-size:13px;padding:3px 6px;border:1px solid #d9e2ec;border-radius:6px;background:#fff}#count{margin-left:auto;color:#2563eb;font-weight:650;font-size:13px}
.row-head{display:flex;justify-content:space-between;gap:10px;align-items:baseline;margin:18px 0 6px;padding-top:12px;border-top:1px solid #d9e2ec}
.row-head h2{font-size:15px;margin:0}.row-head .meta{font-size:11.5px;color:#52606d}
.triple{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.cell{border:1px solid #d9e2ec;border-radius:9px;padding:7px;min-width:0}
.cell[hidden]{display:none}.cell-head{display:flex;justify-content:space-between;align-items:center;gap:6px;margin-bottom:4px}.cell-head b{font-size:12px}.cell video{width:100%;aspect-ratio:4/5;background:#0b0f14;border-radius:6px;display:block}
.meta{font-size:10.8px;color:#52606d;margin-top:3px;line-height:1.4;overflow-wrap:anywhere}.badge{display:inline-block;padding:1px 6px;border-radius:999px;font-size:10.5px;border:1px solid #bbf7d0;background:#ecfdf3;color:#166534}.badge.bad{border-color:#fecdca;background:#fef3f2;color:#b42318}.badge.na{border-color:#e5e7eb;background:#f3f4f6;color:#4b5563}
.missing{display:flex;align-items:center;justify-content:center;aspect-ratio:4/5;background:#f7f8fa;border:1px dashed #d9e2ec;border-radius:6px;color:#7b8794;font-size:11px;text-align:center;padding:5px}.small{font-size:11.5px;color:#7b8794}
@media(max-width:900px){.triple{grid-template-columns:1fr}}
"""


def main() -> int:
    raw = [json.loads(line) for line in (RUN / "episodes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    data = list({row["case_id"]: row for row in raw}.values())
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

    def stats(rs):
        v = [r for r in rs if is_valid(r)]
        return {
            "n": len(rs),
            "trigger": sum(1 for r in rs if r.get("trigger_reached")),
            "valid": len(v),
            "rec": sum(1 for r in v if r.get("recovered")),
            "sr": sum(1 for r in v if r.get("success")),
            "s2": sum(1 for r in v if r.get("s2_undisturbed_by_injection")),
            "success": sum(1 for r in v if r.get("success")),
            "rec_fail_task": sum(1 for r in v if r.get("recovered") and not r.get("success")),
            "not_rec": sum(1 for r in v if not r.get("recovered")),
            "invalid": len(rs) - len(v),
        }

    total = stats(data)
    win_rows = "".join(
        f"<tr><td>{w}</td><td class='num'>{s['n']}</td><td class='num'>{s['trigger']}</td><td class='num'>{s['valid']}</td>"
        f"<td class='num'>{s['rec']} ({pct(s['rec'], s['valid'])})</td><td class='num'>{s['sr']} ({pct(s['sr'], s['valid'])})</td>"
        f"<td class='num'>{s['invalid']}</td></tr>"
        for w in WINDOWS
        for s in [stats([r for r in data if r.get("window") == w])]
    )
    level_rows = "".join(
        f"<tr><td>{lv}</td><td class='num'>{s['n']}</td><td class='num'>{s['valid']}</td>"
        f"<td class='num'>{s['rec']} ({pct(s['rec'], s['valid'])})</td><td class='num'>{s['sr']} ({pct(s['sr'], s['valid'])})</td>"
        f"<td class='num'>{s['invalid']}</td></tr>"
        for lv in ("L0", "L1", "L2")
        for s in [stats([r for r in data if r.get("level") == lv])]
    )

    reasons = Counter()
    for r in data:
        if not is_valid(r):
            for reason in invalid_reasons(r):
                reasons[reason] += 1
    reason_html = "".join(
        f"<tr><td>{esc(REASON_LABEL.get(k, k))}</td><td class='num'>{v}</td></tr>"
        for k, v in reasons.most_common()
    )
    aux_restorable = sum(1 for r in data if is_valid(r) and (r.get("validity") or {}).get("restorable") is False)

    rows_html = []
    for key in sorted(groups, key=group_sort):
        by_w = groups[key]
        base = next(iter(by_w.values()))
        task = base.get("bddl_name")
        level = base.get("level")
        param = base.get("param") or ""
        cells = []
        for w in WINDOWS:
            r = by_w.get(w)
            cls, label = status(r)
            valid = is_valid(r)
            out = outcome(r)
            reasons_for_cell = invalid_reasons(r) if r is not None and not valid else []
            reason_attr = "|".join(reasons_for_cell)
            if r is None:
                cells.append(f'<div class="cell" data-window="{w}" data-valid="false" data-outcome="invalid" data-reasons="missing"><div class="cell-head"><b>{w}</b><span class="badge na">missing</span></div><div class="missing">no case</div></div>')
                continue
            path = rel((r.get("video") or {}).get("path"))
            video = f'<video controls preload="metadata" playsinline muted loop src="{esc(path)}"></video>' if path else '<div class="missing">video missing</div>'
            aux = "" if (r.get("validity") or {}).get("restorable") is not False else " · restorable 辅助=false"
            cells.append(
                f'<div class="cell" data-window="{esc(w)}" data-valid="{str(valid).lower()}" data-outcome="{esc(out)}" data-reasons="{esc(reason_attr)}">'
                f'<div class="cell-head"><b>{esc(w)}</b><span class="badge {cls}">{label}</span></div>{video}'
                f'<div class="meta">trigger {esc(r.get("trigger_step"))} · inject {esc(r.get("injection_step"))} · steps {esc(r.get("steps"))}<br>'
                f'valid {str(valid).lower()} · recovered {esc(r.get("recovered"))} · success {esc(r.get("success"))}{aux}</div></div>'
            )
        rows_html.append(
            f'<div class="row" data-task="{esc(task)}" data-level="{esc(level)}">'
            f'<div class="row-head"><h2>{esc(task)}</h2><div class="meta">{esc(level)}-{esc(param)} · <span class="small">{esc(key)}</span></div></div>'
            f'<div class="triple">{"".join(cells)}</div></div>'
        )

    task_options = "".join(f'<option value="{esc(t)}">{esc(t)}</option>' for t in sorted({r.get("bddl_name") for r in data}))
    reason_options = "".join(f'<option value="{esc(k)}">{esc(REASON_LABEL.get(k, k))}</option>' for k in reasons)
    html_text = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>C matrix seed=1 · L10 in-execution rollback · pi05</title><style>{CSS}</style></head><body><div class="wrap">
<h1>C matrix · L10 in-execution rollback</h1>
<p class="sub">π0.5 · seed=1 · 600+600 · video · {len(data)}/180 cases · restorable 为辅助 oracle，不参与硬门控</p>
<div class="kpis">
<div class="kpi"><div class="l">Completed</div><div class="v">{len(data)}/180</div><div class="s">{pct(len(data), 180)}</div></div>
<div class="kpi"><div class="l">Trigger</div><div class="v">{total['trigger']}/{total['n']}</div><div class="s">{pct(total['trigger'], total['n'])}</div></div>
<div class="kpi"><div class="l">Valid</div><div class="v">{total['valid']}</div><div class="s">hard gates</div></div>
<div class="kpi"><div class="l">Recovery</div><div class="v">{total['rec']}/{total['valid']}</div><div class="s">{pct(total['rec'], total['valid'])}</div></div>
<div class="kpi"><div class="l">Full SR</div><div class="v">{total['sr']}/{total['valid']}</div><div class="s">{pct(total['sr'], total['valid'])}</div></div>
<div class="kpi"><div class="l">恢复但任务失败</div><div class="v">{total['rec_fail_task']}</div><div class="s">valid only</div></div>
<div class="kpi"><div class="l">恢复失败</div><div class="v">{total['not_rec']}</div><div class="s">valid only</div></div>
</div>
<table><thead><tr><th>window</th><th class="num">done</th><th class="num">trigger</th><th class="num">valid</th><th class="num">Recovery</th><th class="num">Full SR</th><th class="num">invalid</th></tr></thead><tbody>{win_rows}</tbody></table>
<table><thead><tr><th>level</th><th class="num">done</th><th class="num">valid</th><th class="num">Recovery</th><th class="num">Full SR</th><th class="num">invalid</th></tr></thead><tbody>{level_rows}</tbody></table>
<table><thead><tr><th>invalid hard-gate reason</th><th class="num">count</th></tr></thead><tbody>{reason_html}</tbody></table>
<div class="note"><b>口径：</b>valid 只看 6 个硬门控；<code>restorable</code> 仅作辅助证据。<b>恢复成功但任务失败</b> = valid &amp; recovered &amp; !success；<b>恢复失败</b> = valid &amp; !recovered。<br><b>aux：</b>本报告有 {aux_restorable} 条 valid 的 restorable 辅助 oracle 为 false，不因此判 invalid。<br><b>视频：</b>每行 early / mid / later 三列；筛选按每个 case 独立生效。<br><b>seed=1：</b>动态 s1/s2，t033/t078 使用审核后的 profile。</div>
<div class="filters">
<label>task <select id="task"><option value="all">all</option>{task_options}</select></label>
<label>level <select id="level"><option value="all">all</option><option>L0</option><option>L1</option><option>L2</option></select></label>
<label>window <select id="window"><option value="all">all</option><option>early</option><option>mid</option><option>later</option></select></label>
<label>validity <select id="validity"><option value="all">all</option><option value="true">valid</option><option value="false">invalid</option></select></label>
<label>outcome <select id="outcome"><option value="all">all</option><option value="success">任务成功</option><option value="recovered_task_failed">恢复成功但任务失败</option><option value="not_recovered">恢复失败</option><option value="task_failed">任务失败（valid & !success）</option><option value="invalid">无效</option></select></label>
<label>invalid reason <select id="reason"><option value="all">all</option>{reason_options}</select></label>
<span id="count"></span></div>
<div id="rows">{''.join(rows_html)}</div>
<script>
const rows=[...document.querySelectorAll('.row')],t=document.getElementById('task'),lv=document.getElementById('level'),wd=document.getElementById('window'),va=document.getElementById('validity'),oc=document.getElementById('outcome'),rs=document.getElementById('reason'),ct=document.getElementById('count');
function run(){{let n=0;rows.forEach(row=>{{let shown=0;row.querySelectorAll('.cell').forEach(cell=>{{const reasons=(cell.dataset.reasons||'').split('|');const ok=(t.value==='all'||row.dataset.task===t.value)&&(lv.value==='all'||row.dataset.level===lv.value)&&(wd.value==='all'||cell.dataset.window===wd.value)&&(va.value==='all'||cell.dataset.valid===va.value)&&(oc.value==='all'||cell.dataset.outcome===oc.value||(oc.value==='task_failed'&&cell.dataset.valid==='true'&&cell.dataset.outcome!=='success'))&&(rs.value==='all'||reasons.includes(rs.value));cell.hidden=!ok;if(ok)shown++;}});row.hidden=shown===0;if(shown>0)n+=shown;}});ct.textContent=n+' cases';}}
[t,lv,wd,va,oc,rs].forEach(e=>e.onchange=run);run();
</script>
</div></body></html>"""
    (OUT / "index.html").write_text(html_text, encoding="utf-8")
    print("wrote", OUT / "index.html", "groups", len(groups), "cases", len(data), "valid", total["valid"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
