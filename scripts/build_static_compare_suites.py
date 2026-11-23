# ruff: noqa: E501
"""Per-suite static vs rollback video reports, with task Init0 screenshots."""

from __future__ import annotations

import html
import json
import os
import shutil
from collections import defaultdict
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
INIT0 = OUT / "init0"


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


def static_rows() -> dict[str, list[dict]]:
    out = {}
    for suite, run in STATIC_RUNS.items():
        rows = read_jsonl(run / "episodes.jsonl")
        for r in rows:
            r["_suite"] = suite
        out[suite] = rows
    return out


def rb_meta() -> dict[str, dict]:
    meta = {}
    for row in read_jsonl(REPO / "experiments" / "b-rollback" / "report-goal-object-20261118" / "cases.jsonl"):
        meta[row["case_id"]] = row
    for name in ("spatial-part1.json", "spatial-part2.json"):
        data = json.loads((REPO / "experiments" / "b-rollback" / "report-spatial-20261118" / name).read_text(encoding="utf-8"))
        for row in data.get("cases") or []:
            cid = row.get("case_id") or row.get("id")
            if cid:
                meta[cid] = row
    for row in read_jsonl(L10_VIDEOS / "episodes.jsonl"):
        meta[row["case_id"]] = row
    return meta


def rollback_video(case_id: str) -> Path | None:
    if case_id.startswith(("b-goal-", "b-object-")):
        p = GO_VIDEOS / f"{case_id}.mp4"
        return p if p.exists() else None
    if case_id.startswith("b-l10-"):
        p = L10_VIDEOS / "l10" / case_id / "seed-0" / "video.mp4"
        return p if p.exists() else None
    return None


def rollback_status(row: dict | None) -> str:
    if row is None or ("injection_valid" not in row and "case_valid" not in row):
        return "no_rollback"
    if not row.get("trigger_reached", True):
        return "n/a"
    if not bool(row.get("injection_valid", row.get("case_valid"))):
        return "invalid"
    return "recovered" if row.get("recovered") else "not_recovered"


def static_status(row: dict) -> str:
    if not row.get("case_valid"):
        return "invalid"
    return "success" if row.get("success") else "fail"


def badges() -> dict[str, tuple[str, str]]:
    return {
        "success": ("ok", "static success"),
        "fail": ("bad", "static fail"),
        "invalid": ("na", "static invalid"),
        "recovered": ("ok", "rollback recovered"),
        "not_recovered": ("bad", "rollback not recovered"),
        "invalid_rb": ("na", "rollback invalid"),
        "n/a": ("na", "rollback N/A"),
        "no_rollback": ("na", "no rollback video"),
    }


CSS = """
body{margin:0;background:#fff;color:#1f2933;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1400px;margin:0 auto;padding:22px 20px 60px}h1{font-size:23px;margin:0 0 5px}.sub{color:#52606d;margin:0 0 12px;font-size:14px}
a{color:#2563eb;text-decoration:none}a:hover{text-decoration:underline}
.filters{position:sticky;top:0;z-index:10;background:#fff;border:1px solid #d9e2ec;border-radius:10px;padding:8px 12px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:10px 0}
select{font:inherit;font-size:13px;padding:3px 6px;border:1px solid #d9e2ec;border-radius:6px}#count{margin-left:auto;color:#2563eb;font-weight:650;font-size:13px}
.task{border-top:1px solid #d9e2ec;margin:24px 0 10px;padding-top:14px}.task-head{display:grid;grid-template-columns:180px 1fr;gap:14px;align-items:start;margin-bottom:10px}
.init0{width:180px;height:180px;object-fit:cover;border-radius:10px;border:1px solid #d9e2ec;background:#f7f8fa}
.task h2{font-size:16px;margin:0 0 4px}.task .meta{font-size:12px;color:#52606d}.task .mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11.5px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:14px}
.card{border:1px solid #d9e2ec;border-radius:10px;padding:10px;background:#fff}.card[hidden]{display:none}
.card-head{display:flex;justify-content:space-between;gap:8px;margin-bottom:6px;min-width:0}.card-head .mono{font-size:11.5px;font-family:ui-monospace,Menlo,Consolas,monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:8px}.side{min-width:0}.side-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:3px}
video{width:100%;aspect-ratio:4/5;background:#0b0f14;border-radius:7px;display:block}.meta{font-size:11px;color:#52606d;margin-top:3px;overflow-wrap:anywhere}
.badge{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;border:1px solid #bbf7d0;background:#ecfdf3;color:#166534}.badge.bad{border-color:#fecdca;background:#fef3f2;color:#b42318}.badge.na{border-color:#e5e7eb;background:#f3f4f6;color:#4b5563}
.missing{display:flex;align-items:center;justify-content:center;aspect-ratio:4/5;background:#f7f8fa;border:1px dashed #d9e2ec;border-radius:7px;color:#7b8794;font-size:11px;text-align:center;padding:6px}
.note{background:#f7f8fa;border:1px solid #d9e2ec;border-left:4px solid #2563eb;border-radius:10px;padding:10px 12px;margin:10px 0;font-size:13px}
"""


def page(title: str, subtitle: str, body: str, suite: str) -> str:
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head><body><div class="wrap">
<p><a href="index.html">← 返回 suite 索引</a></p>
<h1>{esc(title)}</h1><p class="sub">{esc(subtitle)}</p>
<div class="note"><b>Init0：</b>每个 task 上方是原始任务的 Init0（reset + settle 10，无任何扰动）截图，用来对照 static 左视频在 t=0 是否真的有位移/旋转。L0 是 baseline，本来无扰动；L1/L2 才应看到变化。</div>
{body}
</div></body></html>"""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    # preserve the old huge all-in-one page but stop using it as index
    old = OUT / "index.html"
    if old.exists() and not (OUT / "all.html").exists():
        shutil.copyfile(old, OUT / "all.html")
    static = static_rows()
    meta = rb_meta()
    bmap = badges()

    suite_stats = {}
    for suite in ("goal", "object", "spatial", "l10"):
        rows = static[suite]
        by_task: dict[tuple[int, str], list[dict]] = defaultdict(list)
        for r in rows:
            by_task[(int(r["task_idx"]), r["bddl_name"])].append(r)
        task_html = []
        for (task_idx, name), trs in sorted(by_task.items()):
            trs.sort(key=lambda r: (r["level"], r.get("param") or "", r["case_id"]))
            init_path = INIT0 / f"{suite}-t{task_idx:03d}.png"
            init_rel = rel(init_path)
            img = f'<img class="init0" loading="lazy" src="{esc(init_rel)}" alt="Init0 {esc(name)}">' if init_rel else '<div class="init0" style="display:flex;align-items:center;justify-content:center;color:#7b8794;font-size:12px">Init0 missing</div>'
            cards = []
            for r in trs:
                cid = r["case_id"]
                sstatus = static_status(r)
                svideo = rel((r.get("video") or {}).get("path"))
                rb = meta.get(cid)
                rstatus = rollback_status(rb)
                rvideo = rel(rollback_video(cid))
                left = f'<video controls preload="metadata" playsinline muted loop src="{esc(svideo)}"></video>' if svideo else '<div class="missing">static video missing</div>'
                right = f'<video controls preload="metadata" playsinline muted loop src="{esc(rvideo)}"></video>' if rvideo else f'<div class="missing">rollback video not available locally<br><span class="mono">{esc(cid)}</span></div>'
                scls, slabel = bmap[sstatus]
                rbmap = {
                    "recovered": ("ok", "rollback recovered"),
                    "not_recovered": ("bad", "rollback not recovered"),
                    "invalid": ("na", "rollback invalid"),
                    "n/a": ("na", "rollback N/A"),
                    "no_rollback": ("na", "no rollback video"),
                }
                rcls, rlabel = rbmap.get(rstatus, ("na", rstatus))
                cards.append(f'''<article class="card" data-level="{esc(r['level'])}" data-static="{sstatus}" data-rollback="{rstatus}">
<div class="card-head"><span class="mono">{esc(cid)}</span><span class="meta">{esc(r['level'])}-{esc(r.get('param') or '')}</span></div>
<div class="pair"><div class="side"><div class="side-head"><span class="badge {scls}">{slabel}</span><span class="meta">t=0</span></div>{left}<div class="meta">steps {esc(r.get('steps'))} · first_success {esc(r.get('first_success_step'))} · valid {esc(r.get('case_valid'))}</div></div>
<div class="side"><div class="side-head"><span class="badge {rcls}">{rlabel}</span><span class="meta">all_done</span></div>{right}<div class="meta">{esc((rb or {}).get('relation_final', rb.get('recovered') if rb else '—'))}</div></div></div>
</article>''')
            task_html.append(f'''<section class="task"><div class="task-head">{img}<div><h2>{esc(name)}</h2><div class="meta">task_idx {task_idx} · {len(trs)} cases · <span class="mono">{esc(suite)}</span></div><div class="meta">左侧 static 视频应显示 t=0 注入；右侧 rollback 是 all_done 注入。</div></div></div>
<div class="grid">{''.join(cards)}</div></section>''')
        body = '\n'.join(task_html)
        # small per-suite filter placed before tasks
        body = '''<div class="filters"><label>level <select id="level"><option value="all">all</option><option>L0</option><option>L1</option><option>L2</option></select></label>
<label>static <select id="sstatus"><option value="all">all</option><option>success</option><option>fail</option><option>invalid</option></select></label>
<label>rollback <select id="rstatus"><option value="all">all</option><option>recovered</option><option>not_recovered</option><option>invalid</option><option>n/a</option><option>no_rollback</option></select></label>
<span id="count">''' + str(len(rows)) + ''' shown</span></div>''' + body
        body += '''<script>const cards=[...document.querySelectorAll('.card')],els=['level','sstatus','rstatus'].map(id=>document.getElementById(id)),cnt=document.getElementById('count');function apply(){let n=0;cards.forEach(c=>{const ok=(els[0].value==='all'||c.dataset.level===els[0].value)&&(els[1].value==='all'||c.dataset.static===els[1].value)&&(els[2].value==='all'||c.dataset.rollback===els[2].value);c.hidden=!ok;if(ok)n++;});cnt.textContent=n+' shown';}els.forEach(e=>e.onchange=apply);apply();</script>'''
        filename = f"{suite}.html"
        (OUT / filename).write_text(
            page(
                f"base-rollback · {suite} · static vs rollback",
                f"{len(rows)} cases · 左侧 static(t=0)，右侧 rollback(all_done)；每个 task 顶部是 Init0 原始截图。",
                body,
                suite,
            ),
            encoding="utf-8",
        )
        suite_stats[suite] = len(rows)
        print("wrote", filename, len(rows))

    # small index
    idx = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>base-rollback · static vs rollback 对照索引</title><style>{CSS}</style></head><body><div class="wrap">
<h1>base-rollback · static vs rollback 对照索引</h1>
<p class="sub">按 suite 拆分，避免单页加载 402 条视频。<b>Goal / Object / L10</b> 左右两侧都有视频；<b>Spatial</b> 的 rollback 视频未迁移，右侧为占位。</p>
<table style="width:100%;border-collapse:collapse;font-size:14px;border:1px solid #d9e2ec;border-radius:10px;overflow:hidden">
<thead><tr style="background:#f4f6f8"><th style="padding:8px 10px;text-align:left">suite</th><th style="padding:8px 10px;text-align:right">cases</th><th style="padding:8px 10px;text-align:left">report</th><th style="padding:8px 10px;text-align:left">rollback video</th></tr></thead><tbody>
<tr><td style="padding:8px 10px">Goal</td><td style="padding:8px 10px;text-align:right">75</td><td style="padding:8px 10px"><a href="goal.html">goal.html</a></td><td style="padding:8px 10px">有（历史 165 中的 Goal 75）</td></tr>
<tr><td style="padding:8px 10px">Object</td><td style="padding:8px 10px;text-align:right">70</td><td style="padding:8px 10px"><a href="object.html">object.html</a></td><td style="padding:8px 10px">有（历史 165 中的 Object 70）</td></tr>
<tr><td style="padding:8px 10px">Spatial</td><td style="padding:8px 10px;text-align:right">70</td><td style="padding:8px 10px"><a href="spatial.html">spatial.html</a></td><td style="padding:8px 10px"><b>无</b>（右侧占位）</td></tr>
<tr><td style="padding:8px 10px">L10</td><td style="padding:8px 10px;text-align:right">187</td><td style="padding:8px 10px"><a href="l10.html">l10.html</a></td><td style="padding:8px 10px">有（本轮 197 中的 187）</td></tr>
</tbody></table>
<div class="note"><b>Init0：</b>每个 suite 页面里，每个 task 顶部都有原始任务 Init0 截图（reset + settle 10，无扰动）。L0 是 baseline，L1/L2 才应看到 t=0 位移/旋转。</div>
<p class="sub">旧的 402 条大页面保留在 <a href="all.html">all.html</a>，不推荐直接打开。</p>
</div></body></html>"""
    (OUT / "index.html").write_text(idx, encoding="utf-8")
    print("wrote index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
