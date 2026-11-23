# ruff: noqa: E501
"""Compare static-init Goal L0/L1 success with base-rollback Goal recovery."""

from __future__ import annotations

import html
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATIC_RUN = REPO / "runs" / "b-static-goal-20261120"
STATIC_L2_RUN = REPO / "runs" / "b-static-goal-l2-20261120"
ROLLBACK_CASES = REPO / "experiments" / "b-rollback" / "report-goal-object-20261118" / "cases.jsonl"
OUT = REPO / "experiments" / "b-rollback-static-20261120"


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def pct(k: int, n: int) -> str:
    return "—" if n <= 0 else f"{100 * k / n:.1f}%"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    static_rows = read_jsonl(STATIC_RUN / "episodes.jsonl")
    static_l2_rows = read_jsonl(STATIC_L2_RUN / "episodes.jsonl")
    rollback_rows = read_jsonl(ROLLBACK_CASES)
    generated = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")

    static = [r for r in static_rows if r.get("static_init")]
    s0 = [r for r in static if r["level"] == "L0"]
    s1 = [r for r in static if r["level"] == "L1"]
    s0_ok = [r for r in s0 if r.get("success")]
    s1_ok = [r for r in s1 if r.get("success")]
    s0_valid = [r for r in s0 if r.get("case_valid")]
    s1_valid = [r for r in s1 if r.get("case_valid")]
    s2 = [r for r in static_l2_rows if r.get("static_init") and r["level"] == "L2"]
    s2_ok = [r for r in s2 if r.get("success")]
    s2_valid = [r for r in s2 if r.get("case_valid")]

    rb = [r for r in rollback_rows if r.get("suite") == "goal" and r.get("level") in ("L0", "L1", "L2") and r.get("injection_valid")]
    rb0 = [r for r in rb if r["level"] == "L0"]
    rb1 = [r for r in rb if r["level"] == "L1"]
    rb2 = [r for r in rb if r["level"] == "L2"]
    rb0_rec = [r for r in rb0 if r.get("recovered")]
    rb1_rec = [r for r in rb1 if r.get("recovered")]
    rb2_rec = [r for r in rb2 if r.get("recovered")]

    def by_param(rows, key):
        out = {}
        for p in ("d03", "d06", "d10"):
            rs = [r for r in rows if r.get("param") == p]
            out[p] = (sum(1 for r in rs if key(r)), len(rs))
        return out

    s1_param = by_param(s1, lambda r: r.get("success"))
    rb1_param = by_param(rb1, lambda r: r.get("recovered"))

    def by_angle(rows, key):
        out = {}
        for p in ("r30", "r60", "r90"):
            rs = [r for r in rows if r.get("param") == p]
            out[p] = (sum(1 for r in rs if key(r)), len(rs))
        return out

    s2_angle = by_angle(s2, lambda r: r.get("success"))
    rb2_angle = by_angle(rb2, lambda r: r.get("recovered"))

    def row(label, k, n, extra=""):
        return f"<tr><td>{esc(label)}</td><td class='num'>{k}/{n}</td><td class='num'><b>{pct(k, n)}</b></td><td>{extra}</td></tr>"

    s1_valid_ok = [r for r in s1_valid if r.get("success")]

    def mode_of(r):
        ap = (r.get("injection") or {}).get("applied") or [{}]
        return ap[0].get("mode")

    s1_free = [r for r in s1 if mode_of(r) == "translation"]
    s1_joint = [r for r in s1 if mode_of(r) == "joint_ratio"]
    s1_free_ok = [r for r in s1_free if r.get("success")]
    s1_joint_ok = [r for r in s1_joint if r.get("success")]
    level_rows = [
        row("Static L0（无扰动）", len(s0_ok), len(s0), "target 已在 init；这是 baseline，不是扰动"),
        row("Static L1 free（init 平移）", len(s1_free_ok), len(s1_free), "3/6/10 cm；真实位移"),
        row("Static L1 joint（no-op，bug）", len(s1_joint_ok), len(s1_joint), "q_applied=0；不能作为 L1 结果"),
        row("Static L1 raw", len(s1_ok), len(s1), "free + no-op joint，仅作审计"),
        row("Static L1（valid only）", len(s1_valid_ok), len(s1_valid), "排除 zero_velocity invalid"),
        row("Static L2（init yaw）", len(s2_ok), len(s2), "30/60/90°"),
        row("Rollback L0（base）", len(rb0_rec), len(rb0), "all_done 后回滚"),
        row("Rollback L1（base）", len(rb1_rec), len(rb1), "all_done 后回滚"),
        row("Rollback L2（base）", len(rb2_rec), len(rb2), "all_done 后回滚"),
    ]
    angle_rows = []
    for p in ("r30", "r60", "r90"):
        sk, sn = s2_angle[p]
        rk, rn = rb2_angle[p]
        angle_rows.append(
            f"<tr><td>{p}（{int(p[1:])}°）</td><td class='num'>{sk}/{sn} ({pct(sk, sn)})</td>"
            f"<td class='num'>{rk}/{rn} ({pct(rk, rn)})</td></tr>"
        )
    param_rows = []
    for p in ("d03", "d06", "d10"):
        sk, sn = s1_param[p]
        rk, rn = rb1_param[p]
        param_rows.append(
            f"<tr><td>{p}（{int(p[1:])} cm）</td><td class='num'>{sk}/{sn} ({pct(sk, sn)})</td>"
            f"<td class='num'>{rk}/{rn} ({pct(rk, rn)})</td></tr>"
        )

    # representative videos: static L0 and L1 success, plus one static L1 failure if present
    reps = []
    for r in s0_ok[:1] + s1_ok[:1]:
        reps.append(r)
    fail = [r for r in s1 if not r.get("success")]
    if fail:
        reps.append(fail[0])
    cards = []
    for r in reps:
        path = (r.get("video") or {}).get("path")
        rel = os.path.relpath(path, OUT).replace(os.sep, "/") if path and os.path.exists(path) else ""
        video = f'<video controls preload="metadata" playsinline muted loop src="{esc(rel)}"></video>' if rel else '<div class="missing">video missing</div>'
        status = "success" if r.get("success") else "fail"
        cls = "ok" if status == "success" else "bad"
        cards.append(
            f'<article class="card"><div class="head"><span class="mono">{esc(r["case_id"])}</span>'
            f'<span class="badge {cls}">{status}</span></div>{video}'
            f'<div class="meta">{esc(r["level"])}-{esc(r.get("param") or "")} · '
            f'steps {esc(r.get("steps"))} · first_success {esc(r.get("first_success_step"))}</div></article>'
        )

    html_text = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Base-rollback · static-init Goal L0/L1 消融</title>
<style>
body{{margin:0;background:#fff;color:#1f2933;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:28px 22px 60px}}h1{{font-size:25px;margin:0 0 6px}}.sub{{color:#52606d;margin:0 0 16px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px;margin:16px 0}}
.kpi{{border:1px solid #d9e2ec;border-radius:10px;padding:12px 14px}}.kpi .l{{font-size:12.5px;color:#52606d}}.kpi .v{{font-size:25px;font-weight:780}}.kpi .s{{font-size:12px;color:#7b8794}}
table{{width:100%;border-collapse:collapse;font-size:13.5px;border:1px solid #d9e2ec;border-radius:10px;overflow:hidden;margin:10px 0}}
th,td{{padding:8px 10px;border-bottom:1px solid #d9e2ec;text-align:left}}th{{background:#f4f6f8;color:#52606d;font-size:12.5px}}tr:last-child td{{border-bottom:0}}
td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}.mono{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px}}
.note{{background:#f7f8fa;border:1px solid #d9e2ec;border-left:4px solid #2563eb;border-radius:10px;padding:12px 14px;margin:12px 0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}}.card{{border:1px solid #d9e2ec;border-radius:10px;padding:10px}}
.head{{display:flex;justify-content:space-between;margin-bottom:6px}}.card video{{width:100%;aspect-ratio:4/5;background:#0b0f14;border-radius:7px}}.meta{{font-size:12px;color:#52606d;margin-top:6px}}
.badge{{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;border:1px solid #bbf7d0;background:#ecfdf3;color:#166534}}.badge.bad{{border-color:#fecdca;background:#fef3f2;color:#b42318}}
</style></head><body><div class="wrap">
<h1>Base-rollback · static-init Goal L0/L1/L2 消融</h1>
<p class="sub">目的：把 L0/L1 target pose 在 init 时注入，让 π0.5 从 t=0 就看到它；如果 static L1 成功率高而 rollback L1 recovery 低，失败就归因于 rollback/history，而不是 target offset。生成 {esc(generated)}。</p>

<div class="kpis">
<div class="kpi"><div class="l">Static L0 success</div><div class="v">{pct(len(s0_ok), len(s0))}</div><div class="s">{len(s0_ok)}/{len(s0)}</div></div>
<div class="kpi"><div class="l">Static L1 free success</div><div class="v">{pct(len(s1_free_ok), len(s1_free))}</div><div class="s">{len(s1_free_ok)}/{len(s1_free)}（真实位移）</div></div>
<div class="kpi"><div class="l">Static L1 valid success</div><div class="v">{pct(len(s1_valid_ok), len(s1_valid))}</div><div class="s">{len(s1_valid_ok)}/{len(s1_valid)}</div></div>
<div class="kpi"><div class="l">Static L2 success</div><div class="v">{pct(len(s2_ok), len(s2))}</div><div class="s">{len(s2_ok)}/{len(s2)}</div></div>
<div class="kpi"><div class="l">Rollback L0 recovery</div><div class="v">{pct(len(rb0_rec), len(rb0))}</div><div class="s">{len(rb0_rec)}/{len(rb0)}（Goal, base）</div></div>
<div class="kpi"><div class="l">Rollback L1 recovery</div><div class="v">{pct(len(rb1_rec), len(rb1))}</div><div class="s">{len(rb1_rec)}/{len(rb1)}（Goal, base）</div></div>
</div>

<h2>主对照</h2>
<table><thead><tr><th>条件</th><th class="num">成功/恢复</th><th class="num">rate</th><th>说明</th></tr></thead><tbody>{''.join(level_rows)}</tbody></table>

<h2>Static L1 vs Rollback L1（按 δ）</h2>
<table><thead><tr><th>L1 δ</th><th class="num">Static success</th><th class="num">Rollback recovery</th></tr></thead><tbody>{''.join(param_rows)}</tbody></table>

<h2>Static L2 vs Rollback L2（按 yaw）</h2>
<table><thead><tr><th>L2 yaw</th><th class="num">Static success</th><th class="num">Rollback recovery</th></tr></thead><tbody>{''.join(angle_rows)}</tbody></table>

<div class="note bad"><b>⚠ 2026-11-20 审计发现：</b>Goal L1 的 36 条里有 <b>9 条 joint-target case 的 q_applied=0</b>（t=0 时“已达成 span”为空，ratio 扰动退化为 no-op）。这些视频当然看不到位移。raw 86.1% 被这 9 条 no-op 抬高；真实平移的 free-object L1 是 <b>22/27 = 81.5%</b>。joint L1 已用“goal-side limit”修复并 smoke 验证，但本报告中的 9 条仍是旧结果，需重跑后才能用于结论。</div>
<div class="note"><b>Static L1 的 6 条 invalid：</b>全部是 <span class="mono">zero_velocity_after_intervention=False</span>（10 步 settle 后目标仍在动），没有 penetration；其中 5 条仍然 success。valid-only 口径是 90.0%，与 raw 86.1% 的结论一致。</div>
<div class="note"><b>怎么读：</b>static L0 是“target 在 init、没有扰动”的基线；static L1 是“target 从 t=0 就平移 δ”的静态扰动；rollback L0/L1 是“任务完成后再回滚到同一目标 pose”。如果 static L1 明显高于 rollback L1，说明模型能处理这个 target pose，失败来自 rollback/完成上下文；如果 static L1 也低，说明 pose 本身/可达性有问题。</div>

<h2>代表视频</h2><div class="grid">{''.join(cards)}</div>

<div class="note"><b>口径：</b>static-init 的 600 是最大预算，首次成功后停止并记 <span class="mono">static_stopped_on_success</span>；rollback 是 base-rollback 的 Goal all_done 结果。static 与 rollback 的预算/停止规则不同，success 与 recovery 不能相加；只比较同 level 的率。</div>
</div></body></html>"""
    (OUT / "index.html").write_text(html_text, encoding="utf-8")
    (OUT / "summary.json").write_text(
        json.dumps(
            {
                "generated_at": generated,
                "static": {
                    "L0": {"n": len(s0), "success": len(s0_ok)},
                    "L1": {"n": len(s1), "success": len(s1_ok)},
                    "L2": {"n": len(s2), "success": len(s2_ok)},
                },
                "rollback_goal": {
                    "L0": {"n": len(rb0), "recovered": len(rb0_rec)},
                    "L1": {"n": len(rb1), "recovered": len(rb1_rec)},
                    "L2": {"n": len(rb2), "recovered": len(rb2_rec)},
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT / 'index.html'}")
    print("static", len(s0_ok), "/", len(s0), "L1", len(s1_ok), "/", len(s1), "L2", len(s2_ok), "/", len(s2))
    print("rollback goal", len(rb0_rec), "/", len(rb0), "L1", len(rb1_rec), "/", len(rb1), "L2", len(rb2_rec), "/", len(rb2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
