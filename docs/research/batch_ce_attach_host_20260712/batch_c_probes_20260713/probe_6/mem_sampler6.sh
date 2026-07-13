#!/bin/bash
D=/tmp/claude-1000/-home-zhuran24-zmd-pj/3e9c4e4c-c0ae-4a71-98f5-05f8b3a5a644/scratchpad/batch_c_probe_6
echo "ts,pid,tag,rss_kb,hwm_kb,swap_kb" >> "$D/mem.csv"
while true; do
  P=$(pgrep -f batch_c_probe_6_auto | head -1)
  if [ -n "$P" ] && [ -r /proc/$P/status ]; then
    RSS=$(awk '/VmRSS/{print $2}' /proc/$P/status)
    HWM=$(awk '/VmHWM/{print $2}' /proc/$P/status)
    SWP=$(awk '/VmSwap/{print $2}' /proc/$P/status)
    echo "$(date +%T),$P,probe6,$RSS,$HWM,$SWP" >> "$D/mem.csv"
  fi
  sleep 1
done
