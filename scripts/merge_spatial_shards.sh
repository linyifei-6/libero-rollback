#!/usr/bin/env bash
# Merge the three spatial shards back into the official spatial run dir.
#
# The official worker was stopped to split its 63 remaining cases into three
# parallel shards.  This script appends the missing episode records and copies
# the missing per-case directories, then verifies 197/197 summaries.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="${STAMP:-20261120}"
OFFICIAL="$REPO_ROOT/runs/b-plus-spatial-full-smolvla-$STAMP"

python3 - "$REPO_ROOT" "$STAMP" "$OFFICIAL" <<'PY'
import json
import shutil
import sys
from pathlib import Path

repo = Path(sys.argv[1])
stamp = sys.argv[2]
official = Path(sys.argv[3])
shards = [repo / f"runs/b-plus-spatial-shard{i}-smolvla-{stamp}" for i in (1, 2, 3)]

def load_ids(path: Path) -> set[str]:
    ids = set()
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                ids.add(json.loads(line)["case_id"])
    return ids

official_ids = load_ids(official / "episodes.jsonl")
appended = 0
with (official / "episodes.jsonl").open("a", encoding="utf-8") as out:
    for shard in shards:
        episodes = shard / "episodes.jsonl"
        if not episodes.is_file():
            print(f"skip missing {episodes}")
            continue
        for line in episodes.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            case_id = json.loads(line)["case_id"]
            if case_id in official_ids:
                continue
            out.write(line + "\n")
            official_ids.add(case_id)
            appended += 1
        for case_dir in sorted((shard / "spatial").glob("*")):
            target = official / "spatial" / case_dir.name
            if target.exists():
                continue
            shutil.copytree(case_dir, target)
print(f"appended {appended} episode records")

summaries = list((official / "spatial").glob("*/seed-0/summary.json"))
print(f"official summaries: {len(summaries)} / 197")
ids = load_ids(official / "episodes.jsonl")
print(f"official episode ids: {len(ids)}")
PY

echo "=== merge done $(date -Is)"
