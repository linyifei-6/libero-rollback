# ruff: noqa: E501
"""All-suite base-rollback static-init ablation report."""

from __future__ import annotations

import html
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "experiments" / "b-rollback-static-exact-20261121"
STATIC_RUNS = {
    "goal": [REPO / "runs" / "b-static-goal-20261120", REPO / "runs" / "b-static-goal-l2-20261120"],
    "object": [REPO / "runs" / "b-static-object-20261120"],
    "spatial": [REPO / "runs" / "b-static-spatial-20261120"],
    "l10": [REPO / "runs" / "b-static-l10-20261120"],
}
ROLLBACK_CASES = REPO / "experiments" / "b-rollback" / "report-goal-object-20261118" / "cases.jsonl"
SPATIAL_AGG = REPO / "experiments" / "b-rollback" / "report-spatial-20261118" / "aggregate.json"


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def pct(k: int, n: int) -> str:
    return "—" if n <= 0 else f"{100 * k / n:.1f}%"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")

    static: dict[str, dict[str, list[dict]]] = {}
    for suite, paths in STATIC_RUNS.items():
        rows = []
        for path in paths:
            rows.extend(read_jsonl(path / "episodes.jsonl"))
        static[suite] = {level: [r for r in rows if r.get("static_init") and r["level"] == level] for level in ("L0", "L1", "L2")}

    rollback_cases = read_jsonl(ROLLBACK_CASES)
    spatial_agg = json.loads(SPATIAL_AGG.read_text(encoding="utf-8")) if SPATIAL_AGG.exists() else {}
    rollback: dict[str, dict[str, tuple[int, int]]] = {}
    for suite in ("goal", "object"):
        rollback[suite] = {}
        for level in ("L0", "L1", "L2"):
            rs = [r for r in rollback_cases if r.get("suite") == suite and r.get("level") == level and r.get("injection_valid")]
            rollback[suite][level] = (sum(1 for r in rs if r.get("recovered")), len(rs))
    rollback["spatial"] = {}
    for level in ("L0", "L1", "L2"):
        item = spatial_agg.get("by_level", {}).get(level, {})
        rollback["spatial"][level] = (int(item.get("recovered") or 0), int(item.get("valid") or 0))
    rollback["l10"] = None

    def static_stats(suite: str, level: str):
        rows = static.get(suite, {}).get(level, [])
        return sum(1 for r in rows if r.get("success")), len(rows), sum(1 for r in rows if r.get("case_valid")), sum(1 for r in rows if r.get("case_valid") and r.get("success"))

    table_rows = []
    for suite in ("goal", "object", "spatial", "l10"):
        cells = [f"<td>{esc(suite)}</td>"]
        for level in ("L0", "L1", "L2"):
            ok, n, valid, valid_ok = static_stats(suite, level)
            cells.append(f"<td class='num'>{ok}/{n}<br><span class='muted'>{pct(ok, n)}</span></td>")
        for level in ("L0", "L1", "L2"):
            if rollback.get(suite) is None:
                cells.append("<td class='num muted'>N/A</td>")
            else:
                k, n = rollback[suite][level]
                cells.append(f"<td class='num'>{k}/{n}<br><span class='muted'>{pct(k, n)}</span></td>")
        table_rows.append("<tr>" + "".join(cells) + "</tr>")

    total_static_ok = sum(static_stats(s, l)[0] for s in static for l in ("L0", "L1", "L2"))
    total_static_n = sum(static_stats(s, l)[1] for s in static for l in ("L0", "L1", "L2"))
    total_rb_ok = sum(k for s in ("goal", "object", "spatial") for k, n in rollback[s].values())
    total_rb_n = sum(n for s in ("goal", "object", "spatial") for k, n in rollback[s].values())

    html_text = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Base-rollback · static-init 全 suite 消融</title><style>
body{{margin:0;background:#fff;color:#1f2933;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1200px;margin:0 auto;padding:28px 22px 60px}}h1{{font-size:25px;margin:0 0 6px}}.sub{{color:#52606d;margin:0 0 16px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px;margin:16px 0}}.kpi{{border:1px solid #d9e2ec;border-radius:10px;padding:12px 14px}}.kpi .l{{font-size:12.5px;color:#52606d}}.kpi .v{{font-size:25px;font-weight:780}}.kpi .s{{font-size:12px;color:#7b8794}}
table{{width:100%;border-collapse:collapse;font-size:13px;border:1px solid #d9e2ec;border-radius:10px;overflow:hidden;margin:10px 0}}
th,td{{padding:8px 8px;border-bottom:1px solid #d9e2ec;text-align:left;vertical-align:top}}th{{background:#f4f6f8;color:#52606d;font-size:12px}}tr:last-child td{{border-bottom:0}}
td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}.muted{{color:#7b8794;font-size:11.5px}}.mono{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px}}
.note{{background:#f7f8fa;border:1px solid #d9e2ec;border-left:4px solid #2563eb;border-radius:10px;padding:12px 14px;margin:12px 0}}
</style></head><body><div class="wrap">
<h1>Base-rollback · static-init 全 suite 消融</h1>
<p class="sub">所有 base-rollback 回滚位置（L0/L1/L2，C0 除外）在 t=0 注入，π0.5 从零开始跑；用于判断 rollback 失败是否来自 target pose 本身。生成 {esc(generated)}。</p>
<div class="kpis">
<div class="kpi"><div class="l">Static success</div><div class="v">{pct(total_static_ok, total_static_n)}</div><div class="s">{total_static_ok}/{total_static_n}</div></div>
<div class="kpi"><div class="l">Rollback recovery</div><div class="v">{pct(total_rb_ok, total_rb_n)}</div><div class="s">{total_rb_ok}/{total_rb_n}（Goal+Object+Spatial）</div></div>
<div class="kpi"><div class="l">Static suites</div><div class="v">4</div><div class="s">Goal / Object / Spatial / L10</div></div>
<div class="kpi"><div class="l">L10 rollback base</div><div class="v">N/A</div><div class="s">base-rollback L10 未跑</div></div>
</div>
<table><thead><tr><th>suite</th><th class="num">static L0</th><th class="num">static L1</th><th class="num">static L2</th><th class="num">rollback L0</th><th class="num">rollback L1</th><th class="num">rollback L2</th></tr></thead><tbody>
{''.join(table_rows)}
</tbody></table>
<div class="note"><b>读法：</b>static 是 t=0 注入 target pose 后从零跑的成功率；rollback 是 base-rollback 的 all_done 回滚恢复率。static 高、rollback 低，说明 target pose 本身不是主要瓶颈，失败更像 rollback / 完成上下文导致。L10 的 base-rollback 未跑，所以 L10 只有 static 列。</div>
<div class="note"><b>口径：</b>static 600 步上限、首次成功即停、settle 10 步；rollback 为 base-rollback 的历史数据（Goal/Object 完整窗口，Spatial 恢复即停）。static success 与 rollback recovery 不能相加；只比较同 suite/level 的率。C0 不在本表。</div>
</div></body></html>"""
    (OUT / "index.html").write_text(html_text, encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps({"generated_at": generated}, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT / "index.html")
    print("static", total_static_ok, "/", total_static_n, "rollback", total_rb_ok, "/", total_rb_n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
