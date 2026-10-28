"""Summarise LIBERO-90 baseline runs produced by run_libero90_baseline.py.

Handles both single-seed and multi-seed runs.  Joins:
  * ``results.json`` from the stock runner (keys ``baseline_s<seed>``)
  * ``atom-traces/*.jsonl`` from the read-only goal-atom probe
  * the LIBERO-90 task configs, to map BDDL name -> benchmark task_idx

Outputs markdown tables (stdout) and ``baseline-seed-summary.json`` next to the
run directory.  Usage:
    python3 scripts/analyze_libero90_baseline.py --run-dir runs/<name>
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# benchmark task_idx -> inventory number in docs/libero-90-task-inventory.md
INVENTORY = {
    1: 25,
    3: 27,
    4: 26,
    5: 28,
    8: 0,
    21: 5,
    23: 9,
    38: 17,
    45: 19,
    63: 40,
    64: 41,
}

SEED_KEY = re.compile(r"^baseline_s(\d+)$")


def latest_exp_dir(run_dir: Path) -> Path:
    candidates = [
        p for p in run_dir.iterdir() if p.is_dir() and (p / "results.json").is_file()
    ]
    if not candidates:
        raise SystemExit(f"no results.json under {run_dir}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_bddl_map(runtime_root: Path) -> dict[str, int]:
    mapping = {}
    for path in sorted((runtime_root / "configs/tasks/libero_90").glob("*.yaml")):
        idx = None
        for line in path.read_text().splitlines():
            line = line.strip()
            if line.startswith("task_idx:"):
                idx = int(line.split(":")[1])
        mapping[path.stem] = idx
    return mapping


def read_trace(path: Path) -> dict:
    meta, summary, steps = None, None, []
    with path.open() as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("_meta"):
                meta = row
            elif row.get("_summary"):
                summary = row
            else:
                steps.append(row)
    atoms = [a.lower() for a in (meta or {}).get("atoms", [])]
    ever = [any(step["truth"][i] for step in steps) for i in range(len(atoms))]
    return {
        "seed": (meta or {}).get("seed"),
        "atoms": atoms,
        "n_steps": len(steps),
        "ever_true": ever,
        "true_at_end": steps[-1]["truth"] if steps else [],
        "all_true_steps": sum(1 for step in steps if all(step["truth"])),
        "true_count": (summary or {}).get("true_count", {}),
        "first_true": (summary or {}).get("first_true_step", {}),
        "last_true": (summary or {}).get("last_true_step", {}),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument(
        "--runtime-root",
        type=Path,
        default=Path.home() / "workspace/roboot/libero-plus/libero-runtime",
    )
    args = ap.parse_args()

    exp = latest_exp_dir(args.run_dir)
    results = json.loads((exp / "results.json").read_text())
    bddl_to_idx = load_bddl_map(args.runtime_root)

    # traces keyed by (bench_idx, seed); seed may be None for the older naming
    traces: dict[tuple[int, int | None], dict] = {}
    for path in sorted((args.run_dir / "atom-traces").glob("*.jsonl")):
        parts = path.name.split("__")
        bddl = parts[0]
        seed = None
        for part in parts[1:]:
            if part.startswith("seed") and part[4:].isdigit():
                seed = int(part[4:])
        idx = bddl_to_idx.get(bddl, -1)
        trace = read_trace(path)
        if trace.get("seed") is not None:
            seed = trace["seed"]
        traces[(idx, seed)] = trace

    tasks = []
    for key, payload in results.items():
        idx = int(payload["task_idx"])
        seed_rows = {}
        for name, baseline in payload["results"].items():
            match = SEED_KEY.match(name)
            if not match:
                continue
            seed = int(match.group(1))
            trace = traces.get((idx, seed)) or traces.get((idx, None)) or {}
            seed_rows[seed] = {
                "success": bool(baseline.get("success")),
                "steps": baseline.get("steps"),
                "time_s": baseline.get("time_s"),
                "atoms": trace.get("atoms", []),
                "ever_true": trace.get("ever_true", []),
                "true_at_end": trace.get("true_at_end", []),
                "all_true_steps": trace.get("all_true_steps", 0),
                "first_true": trace.get("first_true", {}),
                "last_true": trace.get("last_true", {}),
            }
        tasks.append(
            {
                "bench_idx": idx,
                "inventory_idx": INVENTORY.get(idx),
                "instruction": payload["instruction"],
                "seeds": seed_rows,
            }
        )
    tasks.sort(key=lambda t: (t["inventory_idx"] is None, t["inventory_idx"]))

    all_seeds = sorted({s for t in tasks for s in t["seeds"]})
    print(f"# baseline sweep: {exp}")
    print(f"# seeds: {all_seeds}")
    print()
    header = "| inv | bench | instruction | " + " | ".join(
        f"s{s}" for s in all_seeds
    )
    print(header + " | pass | mean pass steps |")
    print("| --- | --- | --- | " + " | ".join("---" for _ in all_seeds) + " | --- | --- |")
    for task in tasks:
        cells = []
        pass_steps = []
        for seed in all_seeds:
            row = task["seeds"].get(seed)
            if row is None:
                cells.append("—")
            elif row["success"]:
                cells.append("**PASS**")
                pass_steps.append(row["steps"])
            else:
                cells.append("fail")
        mean_steps = f"{sum(pass_steps) / len(pass_steps):.0f}" if pass_steps else "—"
        label = (
            f"`{task['inventory_idx']:02d}`"
            if task["inventory_idx"] is not None
            else f"— ({task['bench_idx']})"
        )
        print(
            f"| {label} | {task['bench_idx']} | {task['instruction']} | "
            + " | ".join(cells)
            + f" | {len(pass_steps)}/{len(all_seeds)} | {mean_steps} |"
        )

    print("\n## 子任务达成情况（各 seed 计数）\n")
    print("| inv | 指令 | s1 曾为真 | s1 末步仍为真 | s2 曾为真 | 两个原子同时为真 |")
    print("| --- | --- | --- | --- | --- | --- |")
    for task in tasks:
        n = len(task["seeds"])
        if not n:
            continue
        s1_ever = sum(1 for r in task["seeds"].values() if len(r["ever_true"]) > 0 and r["ever_true"][0])
        s1_end = sum(1 for r in task["seeds"].values() if len(r["true_at_end"]) > 0 and r["true_at_end"][0])
        s2_ever = sum(1 for r in task["seeds"].values() if len(r["ever_true"]) > 1 and r["ever_true"][1])
        both = sum(1 for r in task["seeds"].values() if r["all_true_steps"] > 0)
        label = (
            f"`{task['inventory_idx']:02d}`"
            if task["inventory_idx"] is not None
            else f"— ({task['bench_idx']})"
        )
        print(
            f"| {label} | {task['instruction']} | {s1_ever}/{n} | "
            f"{s1_end}/{n} | {s2_ever}/{n} | {both}/{n} |"
        )

    out = args.run_dir / "baseline-seed-summary.json"
    out.write_text(json.dumps({"exp_dir": str(exp), "seeds": all_seeds, "tasks": tasks}, indent=2) + "\n")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
