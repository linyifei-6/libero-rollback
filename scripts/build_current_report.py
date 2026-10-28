"""Build a filterable HTML report from the current catalog and existing runs."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "dataset" / "current"
DEFAULT_OUTPUT = ROOT / "runs" / "final-report"
sys.path.insert(0, str(ROOT / "src"))
from libero_rollback.evidence import classify_result  # noqa: E402
from libero_rollback.runtime import runtime_binding  # noqa: E402

DEFAULT_RUNS = tuple(
    ROOT / "runs" / name
    for name in (
        "two-subtask-pi05",
        "rollback-battery-pi05",
        "pose-control-pi05",
        "reference-object-pi05",
    )
)


def load(path: Path) -> Any:
    return (
        yaml.safe_load(path.read_text(encoding="utf-8"))
        if path.suffix in {".yaml", ".yml"}
        else json.loads(path.read_text(encoding="utf-8"))
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_baseline(document: dict[str, Any]) -> dict[str, Any] | None:
    for task in document.values():
        if not isinstance(task, dict) or not isinstance(task.get("results"), dict):
            continue
        for value in task["results"].values():
            if isinstance(value, dict) and value.get("kind") == "baseline":
                return value
    return None


def find_perturbation(
    document: dict[str, Any], case_id: str
) -> tuple[str | None, dict[str, Any] | None]:
    candidates: list[tuple[str, dict[str, Any]]] = []
    for task in document.values():
        if not isinstance(task, dict) or not isinstance(task.get("results"), dict):
            continue
        for key, value in task["results"].items():
            if not isinstance(value, dict) or value.get("kind") == "baseline":
                continue
            candidates.append((key, value))
            report = value.get("report")
            report_id = report.get("case_id") if isinstance(report, dict) else None
            if report_id == case_id or case_id.replace("-", "_") in str(key):
                return key, value
    return candidates[0] if len(candidates) == 1 else (None, None)


def run_index(run_dirs: tuple[Path, ...]) -> dict[str, list[Path]]:
    result: dict[str, list[Path]] = defaultdict(list)
    for root in run_dirs:
        if root.is_dir():
            for child in root.iterdir():
                if child.is_dir():
                    result[child.name].append(child)
    return result


def copy_media(
    run_dir: Path, report_dir: Path, case_id: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    destination_dir = report_dir / "videos"
    destination_dir.mkdir(parents=True, exist_ok=True)
    media: list[dict[str, Any]] = []
    for source in sorted(run_dir.rglob("*.mp4")):
        role = "baseline" if "baseline" in source.name.lower() else "perturbation"
        destination = destination_dir / f"{case_id}--{role}--{source.name}"
        source_hash = sha256(source)
        if not destination.exists() or sha256(destination) != source_hash:
            shutil.copy2(source, destination)
        if destination.stat().st_size:
            media.append(
                {
                    "role": role,
                    "path": destination.relative_to(report_dir).as_posix(),
                    "source": str(source),
                    "size_bytes": destination.stat().st_size,
                    "sha256": sha256(destination),
                }
            )
    return (
        [x for x in media if x["role"] == "perturbation"],
        [x for x in media if x["role"] == "baseline"],
    )


def provenance_status(run_dir: Path, case: dict, case_path: Path) -> str | None:
    """Only evidence with the current definition and recorded binding is current."""
    plan_path = run_dir / "execution-plan.json"
    completion_path = run_dir / "completion.json"
    if not plan_path.is_file():
        return "historical_unverified"
    plan = load(plan_path)
    if plan.get("case_sha256") != sha256(case_path):
        return "stale_definition"
    binding_path = run_dir / "binding.yaml"
    if not binding_path.is_file() or load(binding_path) != runtime_binding(case):
        return "stale_binding"
    if not completion_path.is_file():
        return "incomplete"
    completion = load(completion_path)
    if not completion.get("fingerprint") or completion["fingerprint"] != plan.get("fingerprint"):
        return "provenance_mismatch"
    if completion.get("returncode") not in (0, 2, 3):
        return "runtime_error"
    return None


def evaluation_settings(run_dir: Path | None) -> dict[str, Any]:
    """Expose the recorded settings so mixed runtimes are reviewable."""
    path = run_dir / "execution-plan.json" if run_dir else None
    if path is None or not path.is_file():
        return {}
    plan = load(path)
    command = plan.get("command", [])

    def argument(flag):
        return command[command.index(flag) + 1] if flag in command else None

    return {
        "model": argument("--model"),
        "seed": plan.get("seed"),
        "max_steps": plan.get("max_steps"),
        "mode": argument("--mode"),
        "runtime_sha256": plan.get("runtime_sha256"),
        "runtime_root": str(Path(command[1]).parent.parent) if len(command) >= 2 else None,
    }


def collect(dataset_root: Path, run_dirs: tuple[Path, ...], output: Path) -> list[dict[str, Any]]:
    manifest = load(dataset_root / "manifest.yaml")
    repo_root = dataset_root.resolve().parents[1]
    runs = run_index(run_dirs)
    rows: list[dict[str, Any]] = []
    for entry in manifest.get("cases", []):
        case = load(repo_root / entry["path"])
        case_id = case["case_id"]
        candidates = runs.get(case_id, [])
        # Prefer matching provenance, then the latest attempt. Never pick an
        # attempt because its model outcome happened to be successful.
        candidates.sort(
            key=lambda p: (
                provenance_status(p, case, repo_root / entry["path"]) is None,
                (p / "execution-plan.json").stat().st_mtime
                if (p / "execution-plan.json").exists()
                else p.stat().st_mtime,
            )
        )
        run_dir = candidates[-1] if candidates else None
        provenance = (
            provenance_status(run_dir, case, repo_root / entry["path"]) if run_dir else "not_run"
        )
        document: dict[str, Any] = {}
        result_path: Path | None = None
        if run_dir:
            completion_path = run_dir / "completion.json"
            completion = load(completion_path) if completion_path.exists() else {}
            result_paths = [run_dir / p for p in completion.get("results", [])]
            if not result_paths:
                result_paths = sorted(run_dir.rglob("results.json"))
            if result_paths:
                if len(result_paths) != 1:
                    provenance = "ambiguous_results"
                result_path = result_paths[0]
                try:
                    loaded = load(result_path)
                    document = loaded if isinstance(loaded, dict) else {}
                except (OSError, json.JSONDecodeError):
                    document = {}
        perturbation_key, perturbation = find_perturbation(document, case_id)
        baseline = find_baseline(document)
        report = perturbation.get("report") if isinstance(perturbation, dict) else {}
        report = report if isinstance(report, dict) else {}
        trigger = report.get("trigger", {})
        trigger = trigger if isinstance(trigger, dict) else {}
        observed = (report.get("intervention") or {}).get("observed", {})
        observed = observed if isinstance(observed, dict) else {}
        validation = report.get("validation", {})
        validation = validation if isinstance(validation, dict) else {}
        outcome = report.get("outcome", {})
        outcome = outcome if isinstance(outcome, dict) else {}
        change = case.get("rollback_target", {}).get("state_change", {})
        perturbation_videos, baseline_videos = (
            copy_media(result_path.parent, output, case_id)
            if result_path and provenance != "ambiguous_results"
            else ([], [])
        )
        valid = report.get(
            "injection_valid", perturbation.get("injection_valid") if perturbation else None
        )
        rows.append(
            {
                "case_id": case_id,
                "dataset_version": case.get("dataset_version"),
                "case_path": entry["path"],
                "source_id": case.get("source", {}).get("case_source_id"),
                "source_reference": case.get("source", {}).get("case_reference"),
                "collection": Path(entry["path"]).parts[1],
                "task_id": case["task"]["task_id"],
                "task_index": case["task"]["task_index"],
                "task_locator": case["task"].get("source_task_locator"),
                "stage": case.get("stage", {}).get("name"),
                "window": case.get("trigger", {}).get("time_point"),
                "event": case.get("trigger", {}).get("event"),
                "delay_steps": case.get("trigger", {}).get("delay_steps"),
                "mechanism": change.get("kind"),
                "severity": case.get("severity"),
                "template_id": case.get("template_id"),
                "expected_semantics": case.get("expected_evaluation_semantics"),
                "status": provenance
                or (
                    "baseline_missing"
                    if baseline is None
                    else "baseline_failed"
                    if baseline.get("success") is not True
                    else classify_result(case, perturbation)
                ),
                "run_dir": str(run_dir) if run_dir else None,
                "evaluation": evaluation_settings(run_dir),
                "result_file": str(result_path) if result_path else None,
                "perturbation_key": perturbation_key,
                "baseline_success": baseline.get("success") if baseline else None,
                "baseline_steps": baseline.get("steps") if baseline else None,
                "task_success": outcome.get(
                    "success", perturbation.get("success") if perturbation else None
                ),
                "injection_valid": valid,
                "trigger_reached": trigger.get("reached"),
                "trigger_step": trigger.get("step"),
                "pre_relation": observed.get("pre_predicate"),
                "post_relation": observed.get("post_predicate"),
                "recovered": outcome.get("recovered"),
                "recovery_latency_steps": outcome.get("recovery_latency_steps"),
                "steps": perturbation.get("steps") if perturbation else None,
                "validation_passed": validation.get("passed"),
                "validation_errors": validation.get("errors", []),
                "report_errors": report.get("errors", []),
                "videos": perturbation_videos,
                "baseline_videos": baseline_videos,
            }
        )
    return sorted(rows, key=lambda row: (row["task_index"], row["case_id"]))


def grouped(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        groups[str(row.get(key) or "unknown")][row["status"]] += 1
    return [
        {"value": value, "total": sum(counts.values()), "statuses": dict(sorted(counts.items()))}
        for value, counts in sorted(groups.items())
    ]


def analyse(
    rows: list[dict[str, Any]], manifest: dict[str, Any], run_dirs: tuple[Path, ...]
) -> dict[str, Any]:
    status_counts = Counter(row["status"] for row in rows)
    valid = [row for row in rows if row["status"].startswith("valid_")]
    result_count = sum(row["result_file"] is not None for row in rows)
    valid_injection_count = len(valid)
    recovered_count = status_counts["valid_recovered"]
    rollback_count = recovered_count + status_counts["valid_not_recovered"]

    def percent(numerator: int, denominator: int) -> float | None:
        return round(100.0 * numerator / denominator, 1) if denominator else None

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_version": manifest.get("dataset_version"),
        "dataset_case_count": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "run_result_case_count": result_count,
        "valid_injection_count": valid_injection_count,
        "valid_recovered_count": recovered_count,
        "result_coverage_percent": percent(result_count, len(rows)),
        "injection_validity_percent": percent(valid_injection_count, result_count),
        "evaluable_rollback_count": rollback_count,
        "recovery_percent_of_evaluable_rollbacks": percent(recovered_count, rollback_count),
        "valid_not_recovered_count": status_counts["valid_not_recovered"],
        "injection_invalid_count": status_counts["injection_invalid"],
        "runtime_error_count": status_counts["runtime_error"],
        "not_run_count": status_counts["not_run"],
        "video_case_count": sum(bool(row["videos"]) for row in rows),
        "video_count": sum(len(row["videos"]) for row in rows),
        "baseline_video_count": sum(len(row["baseline_videos"]) for row in rows),
        "by_task": grouped(rows, "task_id"),
        "by_window": grouped(rows, "window"),
        "by_source": grouped(rows, "source_id"),
        "by_collection": grouped(rows, "collection"),
        "by_mechanism": grouped(rows, "mechanism"),
        "by_severity": grouped(rows, "severity"),
        "run_directories": [str(path) for path in run_dirs if path.exists()],
        "interpretation": [
            f"The inventory denominator is {len(rows)} definitions; candidates are not assumed physically valid.",
            "Recovery requires current provenance, a true-to-false native transition and explicit repair evidence; controls and external restoration are separate.",
            "Selected evidence records model, seed, step budget and runtime fingerprint per case; mixed settings are not one controlled comparison.",
            "Invalid injection evidence is excluded from recovery rates and remains visible for scenario debugging.",
        ],
        "next_steps": [
            "Complete or rerun cases marked not_run/runtime_error, prioritizing reference-object and pose handlers.",
            "Calibrate invalid penetration and container-above placements with a preflight validator.",
            "Validate implemented temporal, completion-boundary and atomic relation-set protocols in live episodes; preflight alone is insufficient.",
            "Run a controlled seed/model/max_steps sweep on a fixed subset before comparing mechanisms.",
        ],
    }


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


def analysis_html(analysis: dict[str, Any]) -> tuple[str, str]:
    labels = [
        ("数据集用例", "dataset_case_count", ""),
        ("已关联结果", "run_result_case_count", ""),
        ("有效注入", "valid_injection_count", ""),
        ("有效恢复", "valid_recovered_count", ""),
        ("注入无效", "injection_invalid_count", ""),
        ("运行错误", "runtime_error_count", ""),
        ("未运行", "not_run_count", ""),
        ("有扰动视频用例", "video_case_count", ""),
        ("结果覆盖率", "result_coverage_percent", "%"),
        ("注入有效率", "injection_validity_percent", "%"),
        ("可评估回滚恢复率", "recovery_percent_of_evaluable_rollbacks", "%"),
    ]
    cards = "".join(
        '<div class="metric"><strong>'
        + esc(analysis[key])
        + suffix
        + "</strong><span>"
        + label
        + "</span></div>"
        for label, key, suffix in labels
    )
    boxes: list[str] = []
    for title, key in [
        ("按任务", "by_task"),
        ("按时间窗口", "by_window"),
        ("按来源", "by_source"),
        ("按机制", "by_mechanism"),
        ("按严重度", "by_severity"),
        ("按集合", "by_collection"),
    ]:
        content = "".join(
            "<li>"
            + esc(item["value"])
            + "："
            + str(item["total"])
            + "（"
            + "，".join(esc(k) + " " + str(v) for k, v in item["statuses"].items())
            + "）</li>"
            for item in analysis[key]
        )
        boxes.append(
            '<div class="analysis-box"><h3>' + title + "</h3><ul>" + content + "</ul></div>"
        )
    content = "".join("<li>" + esc(item) + "</li>" for item in analysis["next_steps"])
    boxes.append('<div class="analysis-box"><h3>下一步改进</h3><ul>' + content + "</ul></div>")
    return cards, "".join(boxes)


def build_html(rows: list[dict[str, Any]], analysis: dict[str, Any]) -> str:
    cards, boxes = analysis_html(analysis)
    rows_json = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    analysis_json = json.dumps(analysis, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>libero-rollback 全量实验报告</title>
<style>
:root{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#202124;background:#f6f7f9}}
body{{margin:0}}header{{background:#172033;color:white;padding:28px 5vw}}main{{max-width:1800px;margin:auto;padding:22px 5vw}}
h1{{margin:0 0 8px;font-size:28px}}h2{{margin-top:30px}}.muted{{color:#667085}}header .muted{{color:#cbd5e1}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:18px 0}}
.metric,.analysis-box,.case{{background:white;border-radius:10px;padding:14px;box-shadow:0 1px 4px #1018281a}}
.metric strong{{display:block;font-size:25px}}.metric span{{color:#667085;font-size:13px}}
.controls{{display:flex;flex-wrap:wrap;gap:8px;background:white;padding:14px;border-radius:10px;position:sticky;top:0;z-index:2}}
label{{font-size:12px;color:#667085;display:flex;flex-direction:column;gap:3px}}
select,input{{font:inherit;padding:7px;border:1px solid #d0d5dd;border-radius:6px;background:white}}
button{{padding:7px 12px;border:0;border-radius:6px;background:#344054;color:white;cursor:pointer;align-self:end}}
.case{{margin:10px 0}}.case summary{{cursor:pointer;font-weight:600}}.meta{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:4px 16px;margin:10px 0;font-size:13px}}
.meta b{{color:#667085;font-weight:500}}.status{{font-weight:600}}.valid_recovered{{color:#027a48}}.valid_not_recovered{{color:#b54708}}
.injection_invalid{{color:#b42318}}.runtime_error{{color:#667085}}.not_run{{color:#98a2b3}}.valid_task_success_without_recovery_evidence{{color:#7a5af8}}
video{{max-width:360px;width:100%;background:#000;margin:4px 8px 4px 0}}.video-row{{display:flex;flex-wrap:wrap}}
.analysis-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}}code{{font-size:11px;word-break:break-all}}
footer{{color:#667085;font-size:12px;margin:30px 0}}
</style></head><body><header><h1>libero-rollback 全量实验报告</h1>
<div class="muted">dataset/current · 版本 1.0.0 · 生成时间 {esc(analysis["generated_at"])}</div></header><main>
<section><div class="metrics">{cards}</div><p class="muted">库存为 {len(rows)} 条定义，候选不等于物理验证通过。历史证据、定义变化、对照、外部恢复和重复协议未完成分别统计。</p></section>
<section><h2>数据分析</h2><div class="analysis-grid">{boxes}</div></section>
<section><h2>用例与视频证据</h2><div class="controls">
<label>任务<select id="task"><option value="">全部</option></select></label><label>时间窗口<select id="window"><option value="">全部</option></select></label>
<label>来源<select id="source"><option value="">全部</option></select></label><label>集合<select id="collection"><option value="">全部</option></select></label>
<label>机制<select id="mechanism"><option value="">全部</option></select></label><label>严重度<select id="severity"><option value="">全部</option></select></label>
<label>状态<select id="status"><option value="">全部</option></select></label><label>视频<select id="video"><option value="">全部</option><option value="yes">有视频</option><option value="no">无视频</option></select></label>
<label>搜索<input id="search" placeholder="case_id / 任务 / 事件"></label><button id="reset">清除筛选</button></div>
<p id="count" class="muted"></p><div id="cases"></div></section><footer>原始运行目录未被修改。视频副本和 JSON 证据位于本报告目录。</footer></main>
<script>
const rows={rows_json};const analysis={analysis_json};
const escHtml=function(x){{return String(x==null?"":x).replace(/[&<>"]/g,function(c){{return {{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]}})}};
const filters={{task:"task_id",window:"window",source:"source_id",collection:"collection",mechanism:"mechanism",severity:"severity",status:"status"}};
function vals(key){{return Array.from(new Set(rows.map(function(r){{return r[key]}}).filter(function(x){{return x!==null&&x!==undefined&&x!==""}}))).sort()}}
Object.keys(filters).forEach(function(id){{vals(filters[id]).forEach(function(v){{var o=document.createElement("option");o.value=v;o.textContent=v;document.getElementById(id).appendChild(o)}})}});
function filtered(){{var q=document.getElementById("search").value.toLowerCase();return rows.filter(function(r){{return Object.keys(filters).every(function(id){{var value=document.getElementById(id).value;return !value||String(r[filters[id]])===value}})&&(!q||JSON.stringify(r).toLowerCase().indexOf(q)>=0)&&(!document.getElementById("video").value||(document.getElementById("video").value==="yes"?r.videos.length>0:r.videos.length===0))}})}}
function media(r){{return r.videos.concat(r.baseline_videos).map(function(v){{return "<div><video controls preload='metadata' src='"+escHtml(v.path)+"'></video><br><code>"+escHtml(v.path)+"</code></div>"}}).join("")}}
function render(){{var data=filtered();document.getElementById("count").textContent="显示 "+data.length+" / "+rows.length+" 条用例";document.getElementById("cases").innerHTML=data.map(function(r){{return "<details class='case'><summary><span class='status "+escHtml(r.status)+"'>"+escHtml(r.status)+"</span> · "+escHtml(r.case_id)+" · "+escHtml(r.task_id)+" · "+escHtml(r.window)+" · 视频 "+r.videos.length+"</summary><div class='meta'>"+
"<div><b>版本</b> "+escHtml(r.dataset_version)+"</div><div><b>来源</b> "+escHtml(r.source_id)+"</div><div><b>机制</b> "+escHtml(r.mechanism)+"</div><div><b>严重度</b> "+escHtml(r.severity)+"</div>"+
"<div><b>模型 / seed / 步数</b> "+escHtml(r.evaluation.model)+" / "+escHtml(r.evaluation.seed)+" / "+escHtml(r.evaluation.max_steps)+"</div><div><b>运行时</b> <code>"+escHtml(r.evaluation.runtime_root)+"</code></div>"+
"<div><b>事件</b> "+escHtml(r.event)+" / delay "+escHtml(r.delay_steps)+"</div><div><b>触发</b> "+escHtml(r.trigger_reached)+" @ "+escHtml(r.trigger_step)+"</div><div><b>关系</b> "+escHtml(r.pre_relation)+" → "+escHtml(r.post_relation)+"</div>"+
"<div><b>注入</b> "+escHtml(r.injection_valid)+"；校验 "+escHtml(r.validation_passed)+"</div><div><b>任务成功</b> "+escHtml(r.task_success)+"；恢复 "+escHtml(r.recovered)+"；延迟 "+escHtml(r.recovery_latency_steps)+"</div><div><b>baseline</b> "+escHtml(r.baseline_success)+" / "+escHtml(r.baseline_steps)+" 步</div></div>"+
(r.validation_errors.length?"<p><b>校验错误：</b>"+escHtml(JSON.stringify(r.validation_errors))+"</p>":"")+"<div class='video-row'>"+media(r)+"</div></details>"}}).join("")}}
Object.keys(filters).concat(["video","search"]).forEach(function(id){{document.getElementById(id).addEventListener("input",render)}});document.getElementById("reset").onclick=function(){{Object.keys(filters).concat(["video"]).forEach(function(id){{document.getElementById(id).value=""}});document.getElementById("search").value="";render()}};render();
</script></body></html>"""


def build(dataset_root: Path, run_dirs: tuple[Path, ...], output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    manifest = load(dataset_root / "manifest.yaml")
    rows = collect(dataset_root, run_dirs, output)
    analysis = analyse(rows, manifest, run_dirs)
    for name, value in (
        ("data.json", rows),
        ("summary.json", analysis),
        ("analysis.json", analysis),
    ):
        (output / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    evidence = {
        "dataset_manifest": str(dataset_root / "manifest.yaml"),
        "cases": {
            row["case_id"]: {
                "result_file": row["result_file"],
                "status": row["status"],
                "videos": row["videos"],
                "baseline_videos": row["baseline_videos"],
            }
            for row in rows
        },
    }
    (output / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "index.html").write_text(build_html(rows, analysis), encoding="utf-8")
    return analysis


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs-dir", type=Path, action="append", dest="run_dirs")
    args = parser.parse_args()
    run_dirs = tuple(args.run_dirs) if args.run_dirs else DEFAULT_RUNS
    analysis = build(args.dataset_root, run_dirs, args.output)
    print(json.dumps(analysis, ensure_ascii=False, indent=2))
    print("report:", args.output / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
