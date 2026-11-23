#!/usr/bin/env bash
# Wait for the four SmolVLA B-plus suite runs to finish, then aggregate them.
#
# Exit conditions:
#   * every suite has as many summary.json files as planned cases  -> "complete"
#   * no SmolVLA run_b_plus worker is alive and some suite is short -> "incomplete"
#
# Prints a per-suite progress line every 10 minutes and a final aggregate.
set -uo pipefail
cd /home/tarowang/workspace/roboot/libero-rollback-2

STAMP=20261120
declare -A EXPECT=( [goal]=164 [object]=215 [spatial]=197 [l10]=159 )
SUITES="goal object spatial l10"

count_done() {
  local s="$1"
  find "runs/b-plus-$s-full-smolvla-$STAMP" -name summary.json 2>/dev/null | wc -l
}

workers_alive() {
  # only the SmolVLA interpreters: a concurrent pi05 run must not mask a stall
  pgrep -f "venvs/smolvla/bin/python.*run_b_plus.py" | wc -l
}

tick=0
while true; do
  pending=0
  line=""
  for s in $SUITES; do
    n=$(count_done "$s")
    e=${EXPECT[$s]}
    [ "$n" -lt "$e" ] && pending=$((pending + e - n))
    line="$line $s=$n/$e"
  done
  alive=$(workers_alive)
  if [ "$tick" -eq 0 ] || [ $((tick % 10)) -eq 0 ]; then
    echo "$(date -Is) smolvla:$line workers=$alive"
  fi
  if [ "$pending" -eq 0 ]; then
    echo "=== all suites complete $(date -Is)"
    break
  fi
  if [ "$alive" -eq 0 ]; then
    echo "=== no SmolVLA workers alive, $pending cases missing $(date -Is)"
    break
  fi
  sleep 60
  tick=$((tick + 1))
done

echo ""
echo "=== aggregate ==="
python3 scripts/build_b_plus_summary.py \
  "runs/b-plus-goal-full-smolvla-$STAMP" \
  "runs/b-plus-object-full-smolvla-$STAMP" \
  "runs/b-plus-spatial-full-smolvla-$STAMP" \
  "runs/b-plus-l10-full-smolvla-$STAMP" \
  --title "SmolVLA · B-plus full" \
  --json "runs/b-plus-smolvla-$STAMP.summary.json"
