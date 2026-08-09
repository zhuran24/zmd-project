#!/bin/bash
# 批C §1b 分支 B 预案:ghost 尺寸扫描找组织性触发窗(6×7→7×6 串行,attach on,其余同 probe_3)
D=/tmp/claude-1000/-home-zhuran24-zmd-pj/3e9c4e4c-c0ae-4a71-98f5-05f8b3a5a644/scratchpad/batch_c_probe_5
cd /home/zhuran24/zmd-pj || exit 1
for GEOM in "6 7" "7 6"; do
  set -- $GEOM; W=$1; H=$2
  mkdir -p "$D/g${W}x${H}"
  PYTHONFAULTHANDLER=1 EXACT_BINDING_CP_SAT_WORKERS=6 EXACT_SUBPROBLEM_PARAMS="log_search_progress=true" .venv/bin/python \
    docs/research/batch_ce_attach_host_20260712/attach_host_runner.py \
    --ghost-w $W --ghost-h $H --attach on --workers 6 --master-seconds 1800 \
    --run-tag "batch_c_scan_${W}x${H}" --out "$D/g${W}x${H}/cell.json" > "$D/g${W}x${H}/run.log" 2>&1 &
  PYPID=$!
  echo "$(date +%T) scan ${W}x${H} pid=$PYPID" >> "$D/probe5.log"
  t0=$SECONDS
  while kill -0 $PYPID 2>/dev/null && [ $((SECONDS-t0)) -lt 7200 ]; do sleep 30; done
  if kill -0 $PYPID 2>/dev/null; then
    kill $PYPID; sleep 10; kill -0 $PYPID 2>/dev/null && kill -9 $PYPID
    echo "$(date +%T) scan ${W}x${H} TIMEOUT@7200s" >> "$D/probe5.log"
  else
    wait $PYPID; echo "$(date +%T) scan ${W}x${H} EXITED rc=$? cell=$([ -f $D/g${W}x${H}/cell.json ] && echo yes || echo no) wall=$((SECONDS-t0))s" >> "$D/probe5.log"
  fi
done
echo "$(date +%T) SCAN DONE" >> "$D/probe5.log"
