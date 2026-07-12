#!/bin/bash
# v5:新 BIOS 参数验证轮 cycle 4-5;同 v4(taskset 隔离/master1800s/45C 冷判据),修 TIMEOUT kill(TERM→10s→KILL)
D=/tmp/claude-1000/-home-zhuran24-zmd-pj/3e9c4e4c-c0ae-4a71-98f5-05f8b3a5a644/scratchpad/ptm_burnin
REPO=/home/zhuran24/zmd-pj
COOL_TARGET=45; COOL_MAX=1200; COOL_HOLD=600; SOLVE_WALL_MAX=3600
get_temp() { sensors 2>/dev/null | grep 'Package id 0' | sed 's/Package id 0:[^+]*+\([0-9]*\).*/\1/' | head -1; }
cd "$REPO" || exit 1
for i in 4 5; do
  peak=0
  echo "$(date +%T) CYCLE $i/5 HOT begin temp=$(get_temp)C (v5 新BIOS验证轮: taskset solve@0-6 stress@7-23)" >> "$D/cycle.log"
  taskset -c 7-23 nice -n 10 stress-ng --cpu 17 >> "$D/stress.log" 2>&1 &
  SPID=$!
  mkdir -p "$D/cycle_$i"
  PYTHONFAULTHANDLER=1 taskset -c 0-6 .venv/bin/python docs/research/batch_ce_attach_host_20260712/attach_host_runner.py \
    --ghost-w 6 --ghost-h 6 --attach on --workers 6 --master-seconds 1800 \
    --run-tag "ptm_cycle_${i}_newbios" --out "$D/cycle_$i/cell.json" > "$D/cycle_$i/run.log" 2>&1 &
  PYPID=$!
  t0=$SECONDS
  while kill -0 $PYPID 2>/dev/null && [ $((SECONDS-t0)) -lt $SOLVE_WALL_MAX ]; do
    t=$(get_temp); [ -n "$t" ] && [ "$t" -gt "$peak" ] && peak=$t
    echo "$(date +%T),$i,hot,$t" >> "$D/temps.csv"; sleep 30
  done
  if kill -0 $PYPID 2>/dev/null; then
    kill $PYPID 2>/dev/null; sleep 10
    kill -0 $PYPID 2>/dev/null && kill -9 $PYPID 2>/dev/null
    solve_status="TIMEOUT@${SOLVE_WALL_MAX}s"
  else
    wait $PYPID 2>/dev/null; rc=$?
    if [ -f "$D/cycle_$i/cell.json" ]; then solve_status="OK_rc=$rc"; else solve_status="NO_OUTPUT_rc=$rc"; fi
  fi
  kill $SPID 2>/dev/null; pkill -x stress-ng 2>/dev/null
  echo "$(date +%T) CYCLE $i/5 HOT end peak=${peak}C solve=$solve_status wall=$((SECONDS-t0))s" >> "$D/cycle.log"
  t0=$SECONDS
  while t=$(get_temp); [ -n "$t" ] && [ "$t" -gt $COOL_TARGET ] && [ $((SECONDS-t0)) -lt $COOL_MAX ]; do
    echo "$(date +%T),$i,cool,$t" >> "$D/temps.csv"; sleep 30
  done
  sleep $COOL_HOLD
  echo "$(date +%T) CYCLE $i/5 COOL end temp=$(get_temp)C total_cool=$((SECONDS-t0))s (45C判据)" >> "$D/cycle.log"
done
echo "$(date +%T) COMBINED v5 DONE (5 cycles complete)" >> "$D/cycle.log"
