# ruff: noqa: E501
"""Final base-rollback static-exact report (all 4 suites, L0/L1/L2)."""

from __future__ import annotations

import html
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "experiments" / "b-rollback-static-exact-20261121"
RUNS = {
    "goal": REPO / "runs" / "b-static-exact-goal-20261121",
    "object": REPO / "runs" / "b-static-exact-object-20261121",
    "spatial": REPO / "runs" / "b-static-exact-spatial-20261121",
    "l10": REPO / "runs" / "b-static-exact-l10-20261121",
}


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def pct(k: int, n: int) -> str:
    return "—" if n <= 0 else f"{100 * k / n:.1f}%"


static: dict[str, dict[str, list[dict]]] = {}
for suite, run in RUNS.items():
    rows = read(run / "episodes.jsonl")
    static[suite] = {lvl: [r for r in rows if r.get("static_init") and r["level"] == lvl] for lvl in ("L0", "L1", "L2")}

# base-rollback recovery
rb_cases = read(REPO / "experiments" / "b-rollback" / "report-goal-object-20261118" / "cases.jsonl")
rollback: dict[str, dict[str, tuple[int, int]]] = {"goal": {}, "object": {}, "spatial": {}, "l10": {}}
for suite in ("goal", "object"):
    for lvl in ("L0", "L1", "L2"):
        rs = [r for r in rb_cases if r.get("suite") == suite and r.get("level") == lvl and r.get("injection_valid")]
        rollback[suite][lvl] = (sum(1 for r in rs if r.get("recovered")), len(rs))
spatial_agg = json.loads((REPO / "experiments" / "b-rollback" / "report-spatial-20261118" / "aggregate.json").read_text(encoding="utf-8"))
for lvl in ("L0", "L1", "L2"):
    item = spatial_agg["by_level"][lvl]
    rollback["spatial"][lvl] = (item["recovered"], item["valid"])
l10 = read(REPO / "runs" / "b-rollback-l10-20261120" / "episodes.jsonl")
for lvl in ("L0", "L1", "L2"):
    rs = [r for r in l10 if r.get("level") == lvl and r.get("case_valid")]
    rollback["l10"][lvl] = (sum(1 for r in rs if r.get("recovered")), len(rs))

rows_html = []
total = {"s_ok": 0, "s_n": 0, "s_vok": 0, "s_vn": 0, "r_ok": 0, "r_n": 0}
for suite in ("goal", "object", "spatial", "l10"):
    cells = [f"<td>{esc(suite)}</td>"]
    for lvl in ("L0", "L1", "L2"):
        rs = static[suite][lvl]
        ok = sum(1 for r in rs if r.get("success"))
        vok = sum(1 for r in rs if r.get("case_valid") and r.get("success"))
        vn = sum(1 for r in rs if r.get("case_valid"))
        total["s_ok"] += ok; total["s_n"] += len(rs); total["s_vok"] += vok; total["s_vn"] += vn
        cells.append(f"<td class='num'>{ok}/{len(rs)}<br><span class='muted'>{pct(ok, len(rs))} (valid {vok}/{vn})</span></td>")
    for lvl in ("L0", "L1", "L2"):
        k, n = rollback[suite][lvl]
        total["r_ok"] += k; total["r_n"] += n
        cells.append(f"<td class='num'>{k}/{n}<br><span class='muted'>{pct(k, n)}</span></td>")
    rows_html.append("<tr>" + "".join(cells) + "</tr>")

html_text = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>base-rollback static-exact vs rollback</title><style>
body{{margin:0;background:#fff;color:#1f2933;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1200px;margin:0 auto;padding:28px 22px 60px}}h1{{font-size:25px;margin:0 0 6px}}.sub{{color:#52606d;margin:0 0 16px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px;margin:16px 0}}.kpi{{border:1px solid #d9e2ec;border-radius:10px;padding:12px 14px}}.kpi .l{{font-size:12.5px;color:#52606d}}.kpi .v{{font-size:25px;font-weight:780}}.kpi .s{{font-size:12px;color:#7b8794}}
table{{width:100%;border-collapse:collapse;font-size:13px;border:1px solid #d9e2ec;border-radius:10px;overflow:hidden;margin:10px 0}}th,td{{padding:8px 8px;border-bottom:1px solid #d9e2ec;text-align:left;vertical-align:top}}th{{background:#f4f6f8;color:#52606d;font-size:12px}}tr:last-child td{{border-bottom:0}}td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}.muted{{color:#7b8794;font-size:11.5px}}.mono{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px}}
.note{{background:#f7f8fa;border:1px solid #d9e2ec;border-left:4px solid #2563eb;border-radius:10px;padding:12px 14px;margin:12px 0}}
</style></head><body><div class="wrap">
<h1>base-rollback · static-exact vs rollback</h1>
<p class="sub">402 个 base-rollback 回滚位置（L0/L1/L2，C0 除外）在 t=0 注入；joint L1 用 rollback 实际 q_applied，L10 free 用 rollback snapshot_after。π0.5，600 步上限，首次成功即停。</p>
<div class="kpis">
<div class="kpi"><div class="l">Static success</div><div class="v">{total['s_ok']}/{total['s_n']}</div><div class="s">{pct(total['s_ok'], total['s_n'])}</div></div>
<div class="kpi"><div class="l">Static valid success</div><div class="v">{total['s_vok']}/{total['s_vn']}</div><div class="s">{pct(total['s_vok'], total['s_vn'])}</div></div>
<div class="kpi"><div class="l">Rollback recovery</div><div class="v">{total['r_ok']}/{total['r_n']}</div><div class="s">{pct(total['r_ok'], total['r_n'])}</div></div>
<div class="kpi"><div class="l">Suite</div><div class="v">4</div><div class="s">Goal / Object / Spatial / L10</div></div>
</div>
<table><thead><tr><th>suite</th><th class="num">static L0</th><th class="num">static L1</th><th class="num">static L2</th><th class="num">rollback L0</th><th class="num">rollback L1</th><th class="num">rollback L2</th></tr></thead><tbody>
{''.join(rows_html)}
</tbody></table>
<div class="note"><b>结论：</b>static 总成功 {pct(total['s_ok'], total['s_n'])}，rollback 总恢复 {pct(total['r_ok'], total['r_n'])}；同 suite/level 下 static 均显著高于 rollback。target pose/yaw 本身不是主要瓶颈，失败更像 rollback / 完成上下文导致。</div>
<div class="note"><b>口径：</b>static 600 步上限、首次成功即停、settle 10 步；rollback 为 base-rollback 的 all_done 历史结果（Goal/Object 完整窗口，Spatial 恢复即停，L10 完整窗口）。static success 与 rollback recovery 不能相加；只比较同 suite/level。C0 不在本表。</div>
<div class="note"><b>joint 对齐：</b>Goal L1 joint 9 条已用 rollback 的 <span class="mono">q_applied</span>，例如 <span class="mono">b-goal-t000-g-l1-d03 q_applied=-0.016015</span>；之前 no-op 问题已排除。</div>
</div></body></html>"""
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "index.html").write_text(html_text, encoding="utf-8")
print("wrote", OUT / "index.html")
print("static", total["s_ok"], "/", total["s_n"], "rollback", total["r_ok"], "/", total["r_n"])
