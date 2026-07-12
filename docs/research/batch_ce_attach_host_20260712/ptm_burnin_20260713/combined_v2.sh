#!/bin/bash
# v2:续 cycle1 冷段后跑 4 轮 [w6 solve(master 1800s)+nice19 stress 16核 → 冷却 ≤40°C/30min]
D=/tmp/claude-1000/-home-zhuran24-zmd-pj/3e9c4e4c-c0ae-4a71-98f5-05f8b3a5a644/scratchpad/ptm_burnin
REPO=/home/zhuran24/zmd-pj
COOL_TARGET=40; COOL_MAX=1800; SOLVE_WALL_MAX=3600
get_temp() { sensors 2>/dev/null | grep 'Package id 0' | sed 's/Package id 0:[^+]*+\([0-9]*\).*/\1/' | head -1; }
cd "$REPO" || exit 1
# 续 cycle 1 的冷段
t0=$SECONDS
while t=$(get_temp); [ -n "$t" ] && [ "$t" -gt $COOL_TARGET ] && [ $((SECONDS-t0)) -lt $COOL_MAX ]; do
  echo "$(date +%T),1,cool,$t" >> "$D/temps.csv"; sleep 30
done
echo "$(date +%T) CYCLE 1/5 COOL end temp=$(get_temp)C cool_secs=$((SECONDS-t0)) (v2 接管)" >> "$D/cycle.log"
for i in 2 3 4 5; do
  peak=0
  echo "$(date +%T) CYCLE $i/5 HOT begin temp=$(get_temp)C (v2: master1800s stress16)" >> "$D/cycle.log"
  nice -n 19 stress-ng --cpu 16 >> "$D/stress.log" 2>&1 &
  SPID=$!
  mkdir -p "$D/cycle_$i"
  PYTHONFAULTHANDLER=1 .venv/bin/python docs/research/batch_ce_attach_host_20260712/attach_host_runner.py \
    --ghost-w 6 --ghost-h 6 --attach on --workers 6 --master-seconds 1800 \
    --run-tag "ptm_cycle_$i" --out "$D/cycle_$i/cell.json" > "$D/cycle_$i/run.log" 2>&1 &
  PYPID=$!
  t0=$SECONDS
  while kill -0 $PYPID 2>/dev/null && [ $((SECONDS-t0)) -lt $SOLVE_WALL_MAX ]; do
    t=$(get_temp); [ -n "$t" ] && [ "$t" -gt "$peak" ] && peak=$t
    echo "$(date +%T),$i,hot,$t" >> "$D/temps.csv"; sleep 30
  done
  if kill -0 $PYPID 2>/dev/null; then
    kill $PYPID 2>/dev/null; solve_status="TIMEOUT@${SOLVE_WALL_MAX}s"
  else
    wait $PYPID; rc=$?
    if [ -f "$D/cycle_$i/cell.json" ]; then solve_status="OK_rc=$rc"; else solve_status="NO_OUTPUT_rc=$rc"; fi
  fi
  kill $SPID 2>/dev/null; pkill -x stress-ng 2>/dev/null
  echo "$(date +%T) CYCLE $i/5 HOT end peak=${peak}C solve=$solve_status wall=$((SECONDS-t0))s" >> "$D/cycle.log"
  t0=$SECONDS
  while t=$(get_temp); [ -n "$t" ] && [ "$t" -gt $COOL_TARGET ] && [ $((SECONDS-t0)) -lt $COOL_MAX ]; do
    echo "$(date +%T),$i,cool,$t" >> "$D/temps.csv"; sleep 30
  done
  echo "$(date +%T) CYCLE $i/5 COOL end temp=$(get_temp)C cool_secs=$((SECONDS-t0))" >> "$D/cycle.log"
done
echo "$(date +%T) COMBINED v2 DONE" >> "$D/cycle.log"
