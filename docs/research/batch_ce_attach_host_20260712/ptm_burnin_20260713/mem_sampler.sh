#!/bin/bash
D=/tmp/claude-1000/-home-zhuran24-zmd-pj/3e9c4e4c-c0ae-4a71-98f5-05f8b3a5a644/scratchpad/ptm_burnin
echo "time,pid,tag,rss_kb,hwm_kb,swap_kb" >> "$D/mem.csv"
while true; do
  PID=$(pgrep -f "run-tag ptm_cycle" | head -1)
  if [ -n "$PID" ] && [ -r /proc/$PID/status ]; then
    TAG=$(tr '\0' ' ' < /proc/$PID/cmdline 2>/dev/null | grep -o 'ptm_cycle_[0-9]*')
    eval $(awk '/VmRSS/{print "R="$2} /VmHWM/{print "H="$2} /VmSwap/{print "S="$2}' /proc/$PID/status 2>/dev/null)
    echo "$(date +%T),$PID,$TAG,$R,$H,$S" >> "$D/mem.csv"
  fi
  sleep 1
done
