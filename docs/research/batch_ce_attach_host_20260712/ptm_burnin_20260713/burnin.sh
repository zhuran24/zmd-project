#!/bin/bash
# PTM7950 burn-in: 5 轮 [全核 stress 15min → 冷却至 ≤40°C(上限 20min)]
D=/tmp/claude-1000/-home-zhuran24-zmd-pj/3e9c4e4c-c0ae-4a71-98f5-05f8b3a5a644/scratchpad/ptm_burnin
CYCLES=5; HOT_SECS=900; COOL_TARGET=40; COOL_MAX=1800
get_temp() { sensors 2>/dev/null | grep 'Package id 0' | sed 's/Package id 0:[^+]*+\([0-9]*\).*/\1/' | head -1; }
echo "$(date +%T) BURNIN start ambient_temp=$(get_temp)C" >> "$D/cycle.log"
for i in $(seq 1 $CYCLES); do
  peak=0
  echo "$(date +%T) CYCLE $i/$CYCLES HOT begin temp=$(get_temp)C" >> "$D/cycle.log"
  stress-ng --cpu 24 --timeout ${HOT_SECS}s >> "$D/stress.log" 2>&1 &
  SPID=$!
  while kill -0 $SPID 2>/dev/null; do
    t=$(get_temp); [ -n "$t" ] && [ "$t" -gt "$peak" ] && peak=$t
    echo "$(date +%T),$i,hot,$t" >> "$D/temps.csv"; sleep 30
  done
  echo "$(date +%T) CYCLE $i/$CYCLES HOT end peak=${peak}C" >> "$D/cycle.log"
  t0=$SECONDS
  while t=$(get_temp); [ -n "$t" ] && [ "$t" -gt $COOL_TARGET ] && [ $((SECONDS-t0)) -lt $COOL_MAX ]; do
    echo "$(date +%T),$i,cool,$t" >> "$D/temps.csv"; sleep 30
  done
  echo "$(date +%T) CYCLE $i/$CYCLES COOL end temp=$(get_temp)C cool_secs=$((SECONDS-t0))" >> "$D/cycle.log"
done
echo "$(date +%T) BURNIN DONE all $CYCLES cycles" >> "$D/cycle.log"
