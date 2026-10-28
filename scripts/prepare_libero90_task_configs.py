"""Create LIBERO-90 task configs for the rollback candidate baseline run.

``tools/run_benchmark.py`` discovers tasks from ``<runtime-root>/configs/tasks/
<suite>/*.yaml`` and validates ``task.task_idx`` against the installed benchmark
(``libero.libero.benchmark.get_benchmark("LIBERO_90")``, ``task_order_index=0``).
The LIBERO-90 benchmark order is **alphabetical**, i.e. NOT the ``tasks_info.txt``
order used by ``docs/libero-90-task-inventory.md``.  This script resolves the
mapping from the source files instead of typing indices by hand.

Usage:
    python3 scripts/prepare_libero90_task_configs.py --runtime-root ../libero-plus/libero-runtime
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

# candidate numbering from docs/libero-90-task-inventory.md (tasks_info.txt order)
CANDIDATES = [26, 27, 28, 0, 25, 9, 40, 41, 5, 19]
CONTROL = [17]  # rejected by the >=2 stage filter; kept as a single-stage control

DEFAULT_PLUS = Path.home() / "workspace/roboot/libero-plus"


def bddl_names(libero_root: Path) -> list[str]:
    listing = (libero_root / "libero/libero/bddl_files/libero_90/tasks_info.txt").read_text()
    return [line.strip().split("/")[-1][:-5] for line in listing.splitlines() if line.strip()]


def benchmark_order(libero_root: Path) -> list[str]:
    src = (libero_root / "libero/libero/benchmark/libero_suite_task_map.py").read_text()
    start = src.index('"libero_90"')
    block = src[start:]
    end = block.index("\n    ]")
    return re.findall(r'"([^"]+)"', block[:end])[1:]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime-root", type=Path, required=True)
    ap.add_argument("--libero-root", type=Path, default=DEFAULT_PLUS / "LIBERO-plus")
    ap.add_argument("--max-steps", type=int, default=600)
    ap.add_argument("--include-control", action="store_true")
    ap.add_argument(
        "--inventory",
        help="comma-separated inventory indices (tasks_info.txt order) instead of the defaults",
    )
    args = ap.parse_args()

    names = bddl_names(args.libero_root)
    order = benchmark_order(args.libero_root)
    assert len(names) == 90 and len(order) == 90, (len(names), len(order))
    index = {name: i for i, name in enumerate(order)}

    out_dir = args.runtime_root / "configs/tasks/libero_90"
    out_dir.mkdir(parents=True, exist_ok=True)

    wanted = list(CANDIDATES)
    if args.include_control:
        wanted += CONTROL
    if args.inventory:
        wanted = [int(x) for x in args.inventory.split(",") if x.strip()]

    for i in wanted:
        name = names[i]
        bench_idx = index[name]
        path = out_dir / f"{name}.yaml"
        path.write_text(
            "task:\n"
            f"  source: LIBERO_90\n"
            f"  task_idx: {bench_idx}\n"
            f"  bddl_name: {name}\n"
            "evaluation:\n"
            f"  max_steps: {args.max_steps}\n"
        )
        print(f"wrote {path.relative_to(args.runtime_root)}  (inventory {i:02d} -> bench {bench_idx:02d})")

    ids = ",".join(str(index[names[i]]) for i in wanted)
    print(f"\n--task-ids {ids}")


if __name__ == "__main__":
    main()
