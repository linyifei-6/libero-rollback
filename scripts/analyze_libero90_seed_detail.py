"""Per-(task, seed) detail for a LIBERO-90 baseline sweep.

Prints one row per episode with the goal-atom evidence needed to judge whether a
task can host a rollback case: when s1 first became true, whether it held to the
end, when s2 became true, and how many steps both atoms were true together.

Usage:
    python3 scripts/analyze_libero90_seed_detail.py --run-dir runs/<name> [--task 27]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--task", type=int, default=None, help="inventory index filter")
    args = ap.parse_args()

    summary = json.loads((args.run_dir / "baseline-seed-summary.json").read_text())
    print(
        "| inv | seed | result | steps | s1 first | s1 last | s1 hold steps | s2 first | s2 last | both true |"
    )
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for task in summary["tasks"]:
        inv = task["inventory_idx"]
        if args.task is not None and inv != args.task:
            continue
        for seed in sorted(task["seeds"], key=int):
            row = task["seeds"][seed]
            atoms = row["atoms"]
            first = row["first_true"]
            last = row["last_true"]
            s1 = atoms[0] if atoms else ""
            s2 = atoms[1] if len(atoms) > 1 else ""
            s1_first = first.get(s1, "—")
            s1_last = last.get(s1, "—")
            hold = (
                (s1_last - s1_first + 1)
                if isinstance(s1_first, int) and isinstance(s1_last, int)
                else "—"
            )
            print(
                f"| `{inv:02d}` | {seed} | {'PASS' if row['success'] else 'fail'} | "
                f"{row['steps']} | {s1_first} | {s1_last} | {hold} | "
                f"{first.get(s2, '—')} | {last.get(s2, '—')} | {row['all_true_steps']} |"
            )


if __name__ == "__main__":
    main()
