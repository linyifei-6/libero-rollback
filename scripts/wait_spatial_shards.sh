#!/usr/bin/env bash
# Wait for the three spatial shards (63 cases total), merge them into the
# official spatial run dir, then run the final four-suite aggregate.
set -uo pipefail
cd /home/tarowang/workspace/roboot/libero-rollback-2

STAMP=20261120
EXPECT_TOTAL=197

count_official() { find "runs/b-plus-spatial-full-smolvla-$STAMP/spatial" -name summary.json 2>/dev/null | wc -l; }
count_shards() {
  local n=0
  for i in 1 2 3; do
    n=$((n + $(find "runs/b-plus-spatial-shard$i-smolvla-$STAMP/spatial" -name summary.json 2>/dev/null | wc -l)))
  done
  echo "$n"
}

tick=0
while true; do
  official=$(count_official)
  shards=$(count_shards)
  alive=$(pgrep -cf "venvs/smolvla/bin/python.*run_b_plus.py")
  if [ "$tick" -eq 0 ] || [ $((tick % 5)) -eq 0 ]; then
    echo "$(date -Is) spatial official=$official shards=$shards/63 smolvla_procs=$alive"
  fi
  if [ "$shards" -ge 63 ]; then
    echo "=== all shards done, merging $(date -Is)"
    break
  fi
  if [ "$alive" -eq 0 ]; then
    echo "=== no workers alive with shards=$shards/63; stopping $(date -Is)"
    break
  fi
  sleep 60
  tick=$((tick + 1))
done

bash scripts/merge_spatial_shards.sh

echo ""
echo "=== final aggregate ==="
python3 scripts/build_b_plus_summary.py \
  "runs/b-plus-goal-full-smolvla-$STAMP" \
  "runs/b-plus-object-full-smolvla-$STAMP" \
  "runs/b-plus-spatial-full-smolvla-$STAMP" \
  "runs/b-plus-l10-full-smolvla-$STAMP" \
  --title "SmolVLA · B-plus full" \
  --json "runs/b-plus-smolvla-$STAMP.summary.json"
