"""Self-contained HTML report + machine-readable aggregate for one run.

Input is the artifact directory written by :mod:`libero_rollback.runner`::

    <run>/
    ├── run-manifest.json
    ├── matrix.json
    ├── episodes.jsonl      # one JSON object per case
    ├── run-summary.json
    └── <suite>/<case_id>/  # summary.json, trace.jsonl, video.mp4

The report is deliberately static (stdlib only): it can be produced on a CPU
machine, embeds its own CSS, reads no external fonts/scripts, and never puts a
VLM judge or a derived heuristic on the metric path.  Denominators follow
``docs/SPEC.md`` §6.2: ``Recovery`` excludes ``C0`` controls and invalid
injections, and a zero denominator is reported as ``N/A`` — never as 0 %.
"""

from __future__ import annotations

import html
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .evidence import VERDICTS, classify_episode
from .metrics import summarize

SCHEMA = "libero-rollback.report.v1"

_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
       margin: 0; padding: 24px; color: #1f2328; background: #f6f8fa; }
h1 { font-size: 22px; margin: 0 0 4px 0; }
h2 { font-size: 16px; margin: 28px 0 8px 0; border-bottom: 1px solid #d0d7de; padding-bottom: 4px; }
.muted { color: #57606a; font-size: 12px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 16px 0; }
.card { background: #fff; border: 1px solid #d0d7de; border-radius: 8px; padding: 12px 14px; }
.card .label { font-size: 12px; color: #57606a; }
.card .value { font-size: 22px; font-weight: 600; margin-top: 2px; }
.card .ci { font-size: 11px; color: #57606a; }
table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d0d7de;
        font-size: 12px; margin: 6px 0 16px 0; }
th, td { text-align: left; padding: 5px 8px; border-bottom: 1px solid #eaeef2; vertical-align: top; }
th { background: #f6f8fa; font-weight: 600; position: sticky; top: 0; }
tr:hover td { background: #f6f8fa; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.na { color: #9a6700; font-weight: 600; }
.bad { color: #cf222e; }
.good { color: #1a7f37; }
.warn { color: #9a6700; }
code { font-size: 11px; background: #eff1f3; padding: 1px 4px; border-radius: 4px; }
footer { margin-top: 32px; color: #57606a; font-size: 12px; }
"""


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_episodes(run_dir: str | Path) -> list[dict[str, Any]]:
    """Read ``episodes.jsonl`` (tolerating a trailing partial line)."""

    path = Path(run_dir) / "episodes.jsonl"
    if not path.is_file():
        return []
    episodes: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            episodes.append(payload)
    return episodes


def _verdict(episode: Mapping[str, Any]) -> str:
    explicit = episode.get("verdict")
    if isinstance(explicit, str) and explicit in VERDICTS:
        return explicit
    return classify_episode(episode)


def _rate(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _fmt_rate(rate: Mapping[str, Any]) -> str:
    if rate.get("na"):
        return '<span class="na">N/A</span>'
    value = rate.get("value")
    if value is None:
        return '<span class="na">N/A</span>'
    return f"{float(value) * 100:.1f}%"


def _fmt_ci(rate: Mapping[str, Any]) -> str:
    ci = rate.get("ci")
    if not ci:
        return ""
    return f"[{ci[0] * 100:.1f}, {ci[1] * 100:.1f}]"


def _fmt_fraction(rate: Mapping[str, Any]) -> str:
    numerator = rate.get("numerator")
    denominator = rate.get("denominator")
    if numerator is None or denominator is None:
        return ""
    return f"{numerator}/{denominator}"


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------


def _video_ref(run_dir: Path, episode: Mapping[str, Any], out_dir: Path) -> str | None:
    video = episode.get("video") or {}
    path = video.get("path")
    if not isinstance(path, str) or not path:
        return None
    absolute = Path(path)
    if not absolute.is_absolute():
        absolute = run_dir / absolute
    try:
        return os.path.relpath(absolute, out_dir)
    except ValueError:  # different drive on Windows
        return str(absolute)


def _case_rows(run_dir: Path, out_dir: Path, episodes: Sequence[Mapping[str, Any]]) -> list[dict]:
    rows = []
    for episode in episodes:
        injection = episode.get("injection") or {}
        geometry = injection.get("geometry") or {}
        rows.append(
            {
                "case_id": episode.get("case_id"),
                "suite": episode.get("suite"),
                "task_idx": episode.get("task_idx"),
                "bddl_name": episode.get("bddl_name"),
                "level": episode.get("level"),
                "param": episode.get("param"),
                "target": episode.get("target"),
                "status": episode.get("status"),
                "trigger_reached": episode.get("trigger_reached"),
                "case_valid": episode.get("case_valid"),
                "verdict": _verdict(episode),
                "recovered": episode.get("recovered"),
                "relation_before": episode.get("relation_before"),
                "relation_after_injection": episode.get("relation_after_injection"),
                "relation_final": episode.get("relation_final"),
                "steps": episode.get("steps"),
                "repair_budget_steps": episode.get("repair_budget_steps"),
                "delta_translation_m": geometry.get("delta_translation_m"),
                "delta_angle_rad": geometry.get("delta_angle_rad"),
                "video": _video_ref(run_dir, episode, out_dir),
            }
        )
    return rows


def build_aggregate(run_dir: str | Path, out_dir: str | Path | None = None) -> dict[str, Any]:
    """Build the machine-readable aggregate for one run directory."""

    run_dir = Path(run_dir)
    out_dir = Path(out_dir) if out_dir is not None else run_dir / "report"
    episodes = load_episodes(run_dir)
    manifest = _read_json(run_dir / "run-manifest.json")
    run_summary = _read_json(run_dir / "run-summary.json")
    matrix = _read_json(run_dir / "matrix.json")

    stats = summarize(episodes)
    defaults = manifest.get("defaults") or run_summary.get("defaults") or {}
    aggregate = {
        "schema_version": SCHEMA,
        "generator": f"libero-rollback {__version__}",
        "run": {
            "dir": str(run_dir),
            "mode": "dry-run" if (run_dir / "plan.json").is_file() and not episodes else "run",
            "matrix": defaults.get("matrix") or matrix.get("source"),
            "policy": defaults.get("policy"),
            "checkpoint": defaults.get("checkpoint"),
            "config_name": defaults.get("config_name"),
            "init_row": defaults.get("init_row"),
            "seed": defaults.get("seed"),
            "max_steps": defaults.get("max_steps"),
            "delay_steps": defaults.get("delay_steps"),
            "repair_window": defaults.get("repair_window"),
            "video": defaults.get("video"),
        },
        "matrix": matrix,
        "episodes": len(episodes),
        "recovery": stats["recovery"],
        "control": stats["control"],
        "trigger": stats["trigger"],
        "success": stats["success"],
        "by_verdict": stats["by_verdict"],
        "by_suite": stats["by_suite"],
        "by_level": stats["by_level"],
        "cases": _case_rows(run_dir, out_dir, episodes),
    }
    return aggregate


def write_report(run_dir: str | Path, out_dir: str | Path | None = None) -> dict[str, Any]:
    """Write ``aggregate.json``, ``SUMMARY.md`` and ``index.html``."""

    run_dir = Path(run_dir).resolve()
    out_dir = Path(out_dir).resolve() if out_dir is not None else run_dir / "report"
    out_dir.mkdir(parents=True, exist_ok=True)
    aggregate = build_aggregate(run_dir, out_dir)
    (out_dir / "aggregate.json").write_text(
        json.dumps(aggregate, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    (out_dir / "SUMMARY.md").write_text(render_markdown(aggregate), encoding="utf-8")
    (out_dir / "index.html").write_text(render_html(aggregate), encoding="utf-8")
    return aggregate


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------


def _card(label: str, rate: Mapping[str, Any], *, fraction: bool = True) -> str:
    fraction_text = _fmt_fraction(rate)
    return (
        '<div class="card">'
        f'<div class="label">{html.escape(label)}</div>'
        f'<div class="value">{_fmt_rate(rate)}</div>'
        f'<div class="ci">{html.escape(fraction_text)} {_fmt_ci(rate)}</div>'
        "</div>"
    )


def render_markdown(aggregate: Mapping[str, Any]) -> str:
    run = aggregate.get("run") or {}
    lines = [
        "# LIBERO-Rollback run report",
        "",
        f"- run: `{run.get('dir')}`",
        f"- mode: {run.get('mode')}",
        f"- matrix: `{run.get('matrix')}`",
        f"- policy: `{run.get('policy')}` / checkpoint `{run.get('checkpoint')}`",
        f"- protocol: init_row={run.get('init_row')} seed={run.get('seed')} "
        f"max_steps={run.get('max_steps')} delay_steps={run.get('delay_steps')} "
        f"repair_window={run.get('repair_window')}",
        "",
        "| metric | value | fraction | 95% CI |",
        "|---|---:|---:|---|",
    ]
    for label, key in (
        ("Recovery", "recovery"),
        ("C0 control", "control"),
        ("Trigger rate", "trigger"),
        ("Success rate", "success"),
    ):
        rate = aggregate.get(key) or {}
        value = "N/A" if rate.get("na") else rate.get("value")
        ci = rate.get("ci") or ["", ""]
        lines.append(
            f"| {label} | {value} | {_fmt_fraction(rate)} | [{ci[0]}, {ci[1]}] |"
            if rate.get("ci")
            else f"| {label} | {value} | {_fmt_fraction(rate)} | - |"
        )
    lines += ["", "## Cases", ""]
    lines.append(
        "| case | suite | level | target | trigger | valid | verdict | recovered | steps | video |"
    )
    lines.append("|---|---|---|---|---:|---|---|---:|---:|---|")
    for case in aggregate.get("cases") or []:
        video = "yes" if case.get("video") else "-"
        lines.append(
            f"| {case.get('case_id')} | {case.get('suite')} | {case.get('level')}"
            f"-{case.get('param') or ''} | {case.get('target')} | {case.get('trigger_reached')} |"
            f" {case.get('case_valid')} | {case.get('verdict')} | {case.get('recovered')} |"
            f" {case.get('steps')} | {video} |"
        )
    lines.append("")
    return "\n".join(lines)


def _render_rate_rows(rows: Mapping[str, Mapping[str, Any]]) -> str:
    out = []
    for name, stats in rows.items():
        recovery = _rate(stats.get("recovery"))
        control = _rate(stats.get("control"))
        out.append(
            "<tr>"
            f"<td><code>{html.escape(str(name))}</code></td>"
            f'<td class="num">{stats.get("cases", 0)}</td>'
            f'<td class="num">{_fmt_rate(recovery)}</td>'
            f'<td class="num">{_fmt_fraction(recovery)}</td>'
            f'<td class="num">{_fmt_rate(control)}</td>'
            "<td>"
            + "".join(
                f'<code>{html.escape(verdict)}</code>: {count} '
                for verdict, count in (stats.get("by_verdict") or {}).items()
            )
            + "</td></tr>"
        )
    return "".join(out)


def render_html(aggregate: Mapping[str, Any]) -> str:
    run = aggregate.get("run") or {}
    title = f"LIBERO-Rollback report — {run.get('dir', '')}"
    episode_count = aggregate.get("episodes", 0)
    cases_rate = {
        "value": episode_count,
        "numerator": episode_count,
        "denominator": episode_count,
        "ci": None,
    }
    cards = "".join(
        [
            _card("Cases", cases_rate),
            _card("Recovery (conditional)", _rate(aggregate.get("recovery"))),
            _card("C0 control", _rate(aggregate.get("control"))),
            _card("Trigger rate", _rate(aggregate.get("trigger"))),
            _card("Success rate", _rate(aggregate.get("success"))),
        ]
    )
    suite_rows = _render_rate_rows(aggregate.get("by_suite") or {})
    level_rows = _render_rate_rows(aggregate.get("by_level") or {})

    case_rows = []
    for case in aggregate.get("cases") or []:
        level = f"{case.get('level')}-{case.get('param') or ''}".rstrip("-")
        video = case.get("video")
        video_cell = (
            f'<a href="{html.escape(str(video))}">video</a>' if video else "-"
        )
        rows = {
            "trigger": case.get("trigger_reached"),
            "valid": case.get("case_valid"),
            "recovered": case.get("recovered"),
        }
        cells = "".join(
            f'<td class="num">{html.escape(str(rows[key]))}</td>' for key in rows
        )
        case_rows.append(
            "<tr>"
            f"<td><code>{html.escape(str(case.get('case_id')))}</code></td>"
            f"<td>{html.escape(str(case.get('suite')))}</td>"
            f"<td>{html.escape(level)}</td>"
            f"<td>{html.escape(str(case.get('target')))}</td>"
            f"{cells}"
            f"<td><code>{html.escape(str(case.get('verdict')))}</code></td>"
            f"<td>{html.escape(str(case.get('relation_final')))}</td>"
            f'<td class="num">{html.escape(str(case.get("steps")))}</td>'
            f"<td>{video_cell}</td>"
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<h1>LIBERO-Rollback run report</h1>
<p class="muted">
  <code>{html.escape(str(run.get('dir', '')))}</code> ·
  mode <b>{html.escape(str(run.get('mode', '')))}</b> ·
  matrix <code>{html.escape(str(run.get('matrix', '')))}</code> ·
  policy <b>{html.escape(str(run.get('policy', '')))}</b>
</p>
<p class="muted">
  protocol: init_row={html.escape(str(run.get('init_row')))} ·
  seed={html.escape(str(run.get('seed')))} ·
  max_steps={html.escape(str(run.get('max_steps')))} ·
  delay_steps={html.escape(str(run.get('delay_steps')))} ·
  repair_window={html.escape(str(run.get('repair_window')))}
</p>
<div class="grid">{cards}</div>
<p class="muted">Recovery is conditional on a valid injection and excludes C0 controls.
A zero denominator is shown as <span class="na">N/A</span>, never as 0 %.
Verdicts are produced by <code>libero_rollback.evidence</code> from
<code>check_success()</code> and ground-truth predicate traces; no VLM judge is
used on the metric path (docs/SPEC.md §6).</p>

<h2>By suite</h2>
<table>
<thead><tr><th>suite</th><th class="num">cases</th><th class="num">Recovery</th>
<th class="num">n/N</th><th class="num">C0 control</th><th>verdicts</th></tr></thead>
<tbody>{suite_rows or '<tr><td colspan="6">no data</td></tr>'}</tbody>
</table>

<h2>By level</h2>
<table>
<thead><tr><th>level</th><th class="num">cases</th><th class="num">Recovery</th>
<th class="num">n/N</th><th class="num">C0 control</th><th>verdicts</th></tr></thead>
<tbody>{level_rows or '<tr><td colspan="6">no data</td></tr>'}</tbody>
</table>

<h2>Cases</h2>
<table>
<thead><tr><th>case</th><th>suite</th><th>level</th><th>target</th>
<th class="num">trigger</th><th class="num">valid</th><th class="num">recovered</th>
<th>verdict</th><th>final relation</th><th class="num">steps</th><th>video</th></tr></thead>
<tbody>{''.join(case_rows) or '<tr><td colspan="11">no episodes recorded</td></tr>'}</tbody>
</table>

<footer>Generated by {html.escape(str(aggregate.get('generator', '')))} ·
schema <code>{html.escape(str(aggregate.get('schema_version', '')))}</code> ·
This page is self-contained (no external assets).</footer>
</body>
</html>
"""


def report(run_dir: str | Path, out_dir: str | Path | None = None) -> dict[str, Any]:
    """Alias kept for CLI symmetry."""

    return write_report(run_dir, out_dir)


__all__ = [
    "SCHEMA",
    "build_aggregate",
    "load_episodes",
    "render_html",
    "render_markdown",
    "report",
    "write_report",
]
