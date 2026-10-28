"""Cross-task summary report: injection validity, success rates and charts.

Reuses the per-task report helpers so the numbers are computed exactly the same way
(injection-invalid cases never enter a success-rate denominator).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_eval_report import (  # noqa: E402
    MECHANISM_LABEL, SEVERITY_ORDER, SEMANTICS_LABEL, bar_chart, collect, esc, fmt,
    group, load_catalog, outcome_label, tri,
)

RUNS = [
    "runs/retest-20261018/task%s" % n for n in
    ("00", "01", "02", "03", "04", "05", "06", "07", "08", "09")
]


def counts(rows, key):
    out = {}
    for name in sorted({str(r.get(key)) for r in rows}, key=lambda x: (x == "None", x)):
        bucket = [r for r in rows if str(r.get(key)) == name]
        valid = [r for r in bucket if r["injection_valid"] is True]
        ok = sum(1 for r in valid if r["perturbation_success"] is True)
        rec = sum(1 for r in valid if r["recovered"] is True)
        out[name] = (len(bucket), len(valid), ok, rec)
    return out


def chart_data(stats):
    return [(name, rec, valid - rec, total)
            for name, (total, valid, ok, rec) in stats.items()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--run", action="append", default=None)
    parser.add_argument("--title", default="LIBERO-10 rollback 注入有效性总览")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    catalog = load_catalog()
    rows = []
    for run in (args.run or RUNS):
        path = root / run
        if path.is_dir():
            rows.extend(collect(path, catalog))
    if not rows:
        print("no rows collected")
        return 1

    valid = [r for r in rows if r["injection_valid"] is True]
    ok = [r for r in valid if r["perturbation_success"] is True]
    recovered = [r for r in valid if r["recovered"] is True]
    rejected = len(rows) - len(valid)
    rate = 100.0 * len(ok) / len(valid) if valid else 0.0

    by_task = counts(rows, "task")
    by_window = counts(rows, "time_point")
    by_mechanism = counts(rows, "mechanism")
    by_severity = counts(rows, "severity")
    by_semantics = counts(rows, "semantics")

    def table(stats, label_name="分组"):
        body = []
        for name, (total, n_valid, n_ok, n_rec) in stats.items():
            r = 100.0 * n_ok / n_valid if n_valid else 0.0
            body.append(f"<tr><td>{esc(name)}</td><td>{total}</td><td>{n_valid}</td>"
                        f"<td>{n_ok}</td><td>{r:.0f}%</td><td>{n_rec}</td></tr>")
        return ("<table class='data'><thead><tr><th>" + label_name +
                "</th><th>用例</th><th>注入有效（分母）</th><th>episode 成功</th>"
                "<th>成功率</th><th>自修恢复</th></tr></thead><tbody>" +
                "".join(body) + "</tbody></table>")

    task_data = chart_data(by_task)
    window_data = chart_data(by_window)
    mechanism_data = chart_data(by_mechanism)
    severity_data = {k: v for k, v in by_severity.items() if k in SEVERITY_ORDER}
    severity_data = chart_data(severity_data) if severity_data else chart_data(by_severity)
    semantics_data = chart_data(by_semantics)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(args.title)}</title>
<style>
:root{{--ink:#16232f;--muted:#5d7183;--line:#dbe4ec;--bg:#f5f8fb;--card:#fff;--ok:#0f7a3d;--bad:#b3261e;--warn:#8a5a00}}
*{{box-sizing:border-box}} body{{margin:0;padding:28px 22px 64px;font:15px/1.65 -apple-system,"Segoe UI","Noto Sans CJK SC",sans-serif;color:var(--ink);background:var(--bg)}}
h1{{font-size:26px;margin:0 0 6px}} h2{{font-size:20px;margin:34px 0 12px;padding-bottom:8px;border-bottom:2px solid var(--line)}}
.sub{{color:var(--muted);margin:0 0 18px}}
.chips{{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}} .chip{{border:1px solid var(--line);border-radius:10px;padding:10px 14px;background:#fbfdff;min-width:132px}}
.chip b{{display:block;font-size:21px}} .chip span{{font-size:12px;color:var(--muted)}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:12px 0}}
table.data{{border-collapse:collapse;width:100%;font-size:13px;background:var(--card)}}
table.data th,table.data td{{border:1px solid var(--line);padding:6px 8px;text-align:left}}
table.data th{{background:#eef4f9}} .chart{{width:100%;height:auto;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px;margin:12px 0}}
.chart-title{{font-size:13px;font-weight:600;fill:var(--ink)}} .chart-label{{font-size:12px;fill:var(--ink)}}
.chart-label.small{{font-size:11px}} .chart-value{{font-size:12px;fill:var(--muted)}} .seg-label{{font-size:11px;fill:#fff;text-anchor:middle}}
.tick{{font-size:11px;fill:var(--muted);text-anchor:middle}} .axis{{stroke:#9fb2c2;stroke-width:1}}
.green{{fill:#0f7a3d}} .red{{fill:#b3261e}} .amber{{fill:#d9a300}} .legend{{font-size:12px;color:var(--muted)}}
</style></head><body>
<h1>{esc(args.title)}</h1>
<p class="sub">跨任务汇总：注入有效性、成功率与逐维度分解。本次实验重点关注<b>注入有效性</b>，模型恢复不在范围内；成功率的分母只含<b>注入有效</b>的用例。</p>

<div class="chips">
  <div class="chip"><b>{len(rows)}</b><span>用例总数</span></div>
  <div class="chip"><b>{len(valid)}</b><span>注入有效（成功率分母）</span></div>
  <div class="chip"><b>{rejected}</b><span>注入被拒</span></div>
  <div class="chip"><b>{len(ok)}/{len(valid)}</b><span>episode 成功（{rate:.1f}%）</span></div>
  <div class="chip"><b>{len(recovered)}/{len(valid)}</b><span>自修恢复</span></div>
  <div class="chip"><b>{len({r["task"] for r in rows})}</b><span>任务数</span></div>
</div>

<h2>一、整体成功率</h2>
<div class="panel">
<p><b>成功率 = {len(ok)}/{len(valid)} = {rate:.1f}%</b>。分母只含注入有效的用例；注入被拒（{rejected} 条）与基线失败不计入分母，
也不计为模型失败。自修恢复 = {len(recovered)} 条。</p>
</div>

<h2>二、逐任务</h2>
<div class="panel">{table(by_task, "任务")}</div>
{bar_chart("按任务（绿=恢复，黄=有效未恢复，灰=无效）", task_data)}

<h2>三、按窗口</h2>
<div class="panel">{table(by_window, "窗口")}</div>
{bar_chart("按窗口", window_data)}

<h2>四、按机制</h2>
<div class="panel">{table(by_mechanism, "机制")}</div>
{bar_chart("按机制", mechanism_data)}

<h2>五、按档位 / 语义</h2>
<div class="panel">{table(by_severity, "档位")}</div>
{bar_chart("按档位", severity_data)}
<div class="panel">{table(by_semantics, "语义")}</div>
{bar_chart("按语义", semantics_data)}

<h2>六、注入有效性明细</h2>
<div class="panel"><table class="data">
<thead><tr><th>任务</th><th>用例</th><th>注入有效</th><th>注入被拒</th><th>有效率</th></tr></thead><tbody>
{''.join(f"<tr><td>T{str(t).zfill(2)}</td><td>{v[0]}</td><td>{v[1]}</td><td>{v[0]-v[1]}</td><td>{(100.0*v[1]/v[0]):.0f}%</td></tr>" for t, v in by_task.items() if t != 'None')}
</tbody></table></div>
</body></html>"""
    out = args.report / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(out, out.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
