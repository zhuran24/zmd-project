#!/bin/bash
# 批C probe_3:binding 多 worker 提速实验(独占,w6 master + binding w6,7200s 兜底)
D=/tmp/claude-1000/-home-zhuran24-zmd-pj/3e9c4e4c-c0ae-4a71-98f5-05f8b3a5a644/scratchpad/batch_c_probe_3
cd /home/zhuran24/zmd-pj || exit 1
PYTHONFAULTHANDLER=1 EXACT_BINDING_CP_SAT_WORKERS=6 .venv/bin/python \
  docs/research/batch_ce_attach_host_20260712/attach_host_runner.py \
  --ghost-w 6 --ghost-h 6 --attach on --workers 6 --master-seconds 1800 \
  --run-tag batch_c_probe_3_bw6 --out "$D/cell.json" > "$D/run.log" 2>&1 &
PYPID=$!
echo "$(date +%T) probe3 solve pid=$PYPID (binding w6)" >> "$D/probe3.log"
t0=$SECONDS
while kill -0 $PYPID 2>/dev/null && [ $((SECONDS-t0)) -lt 7200 ]; do sleep 30; done
if kill -0 $PYPID 2>/dev/null; then
  kill $PYPID; sleep 10; kill -0 $PYPID 2>/dev/null && kill -9 $PYPID
  echo "$(date +%T) probe3 TIMEOUT@7200s" >> "$D/probe3.log"
else
  wait $PYPID; echo "$(date +%T) probe3 EXITED rc=$? cell=$([ -f $D/cell.json ] && echo yes || echo no) wall=$((SECONDS-t0))s" >> "$D/probe3.log"
fi
