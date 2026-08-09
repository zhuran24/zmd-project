#!/bin/bash
# probe_14 = cap 收敛验证臂:6×6 attach-on + EXACT_B1_BINDING_ALT_CAP=1500
# 预期:master ~9min 出解 → binding 循环 ~1500 轮(~25min)→ ALT_CAP_REACHED → UNKNOWN → cell.json 落地
# 判定点:①cell.json 产出(首次)②telemetry 全套读回(cut_count/dedup/ledger)③cap 生效轮数与 proof_summary
D=/tmp/claude-1000/-home-zhuran24-zmd-pj/3e9c4e4c-c0ae-4a71-98f5-05f8b3a5a644/scratchpad/batch_c_probe_14
cd /home/zhuran24/zmd-pj || exit 1
PYTHONFAULTHANDLER=1 \
EXACT_BINDING_CP_SAT_WORKERS=6 \
EXACT_B1_BINDING_ALT_CAP=1500 \
.venv/bin/python docs/research/batch_ce_attach_host_20260712/attach_host_runner.py \
  --ghost-w 7 --ghost-h 6 --attach off --workers 6 --master-seconds 1800 \
  --run-tag "batch_c_probe_14_6x7" --out "$D/cell.json" > "$D/run.log" 2>&1 &
PYPID=$!
echo "$(date +%T) probe14 solve pid=$PYPID (cap=1500)" >> "$D/probe14.log"
t0=$SECONDS
while kill -0 $PYPID 2>/dev/null && [ $((SECONDS-t0)) -lt 5400 ]; do sleep 30; done
if kill -0 $PYPID 2>/dev/null; then
  kill $PYPID; sleep 10; kill -0 $PYPID 2>/dev/null && kill -9 $PYPID
  echo "$(date +%T) probe14 TIMEOUT@5400s" >> "$D/probe14.log"
else
  wait $PYPID; RC=$?
  echo "$(date +%T) probe14 EXITED rc=$RC cell=$([ -f $D/cell.json ] && echo yes || echo no) wall=$((SECONDS-t0))s" >> "$D/probe14.log"
fi
