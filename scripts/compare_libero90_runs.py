"""Compare episode reproducibility hashes across LIBERO-90 baseline runs.

Reads ``eval.log`` files and pairs each ``[LIBERO_90 #<idx>]`` header with the
``[EPISODE_REPRODUCIBILITY]`` line that follows it, then reports, for every
(task_idx, seed) that appears in more than one run, whether the stabilized
simulator-state hash and the episode outcome agree.

Usage: python3 scripts/compare_libero90_runs.py --run <dir> --run <dir> ...
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HEADER = re.compile(r"\[LIBERO_90 #(\d+)\]")
REPRO = re.compile(r"\[EPISODE_REPRODUCIBILITY\] (\{.*\})")
SEED = re.compile(r"\[baseline seed=(\d+)\] recording")
SUMMARY = re.compile(r"\[baseline seed=(\d+)\] steps=(\d+), time=[\d.]+s, success=(True|False)")


def parse_log(path: Path) -> dict[tuple[int, int], dict]:
    out: dict[tuple[int, int], dict] = {}
    task = None
    seed = None
    for line in path.read_text(errors="replace").splitlines():
        m = HEADER.search(line)
        if m:
            task = int(m.group(1))
            seed = None
            continue
        m = SEED.search(line)
        if m:
            seed = int(m.group(1))
            continue
        if task is None or seed is None:
            continue
        m = REPRO.search(line)
        if m:
            payload = json.loads(m.group(1))
            out.setdefault((task, seed), {})["sim_state_sha256"] = payload.get(
                "stabilized_sim_state_sha256"
            )
            out[(task, seed)]["obs_sha256"] = payload.get("stabilized_observation_sha256")
            continue
        m = SUMMARY.search(line)
        if m:
            out.setdefault((task, seed), {})["steps"] = int(m.group(2))
            out[(task, seed)]["success"] = m.group(3) == "True"
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, action="append", required=True)
    args = ap.parse_args()

    runs = {}
    for run_dir in args.run:
        logs = sorted(run_dir.glob("*/eval.log"))
        if not logs:
            print(f"no eval.log under {run_dir}")
            continue
        runs[run_dir.name] = parse_log(max(logs, key=lambda p: p.stat().st_mtime))

    keys = sorted({key for data in runs.values() for key in data})
    print(f"runs: {list(runs)}")
    print()
    print("| bench | seed | " + " | ".join(runs) + " | sim-state hash | outcome |")
    print("| --- | --- | " + " | ".join("---" for _ in runs) + " | --- | --- |")
    mismatches = 0
    for key in keys:
        rows = [runs[name].get(key) for name in runs]
        present = [r for r in rows if r]
        if len(present) < 2:
            continue
        hashes = {r.get("sim_state_sha256") for r in present}
        outcomes = {(r.get("success"), r.get("steps")) for r in present}
        same_hash = len(hashes) == 1
        same_outcome = len(outcomes) == 1
        if not (same_hash and same_outcome):
            mismatches += 1
        cells = []
        for r in rows:
            cells.append("—" if not r else ("PASS" if r.get("success") else "fail") + f" ({r.get('steps')})")
        print(
            f"| {key[0]} | {key[1]} | "
            + " | ".join(cells)
            + f" | {'identical' if same_hash else 'DIFFERENT'} | "
            + f"{'identical' if same_outcome else 'DIFFERENT'} |"
        )
    print(f"\ncompared keys with >1 run: {sum(1 for k in keys if sum(1 for n in runs if runs[n].get(k)) > 1)}")
    print(f"mismatches: {mismatches}")


if __name__ == "__main__":
    main()
