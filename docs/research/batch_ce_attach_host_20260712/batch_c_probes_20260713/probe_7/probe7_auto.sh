#!/bin/bash
# probe_7 = F-5 修复验证臂:binding AUTOMATIC search + 6 worker(修复后 env 注入应真正生效)
# 判定点:①binding 段 CPU 应看到 ~600%(6 worker 真干活)②binding 出结论时长 vs probe_2/3 的 >100min
D=/tmp/claude-1000/-home-zhuran24-zmd-pj/3e9c4e4c-c0ae-4a71-98f5-05f8b3a5a644/scratchpad/batch_c_probe_7
cd /home/zhuran24/zmd-pj || exit 1
PYTHONFAULTHANDLER=1 \
EXACT_BINDING_CP_SAT_WORKERS=6 \
EXACT_SUBPROBLEM_PARAMS="search_branching=0,log_search_progress=true" \
.venv/bin/python docs/research/batch_ce_attach_host_20260712/attach_host_runner.py \
  --ghost-w 6 --ghost-h 6 --attach on --workers 6 --master-seconds 1800 \
  --run-tag "batch_c_probe_7_auto" --out "$D/cell.json" > "$D/run.log" 2>&1 &
PYPID=$!
echo "$(date +%T) probe7 solve pid=$PYPID (binding AUTOMATIC+w6)" >> "$D/probe7.log"
t0=$SECONDS
while kill -0 $PYPID 2>/dev/null && [ $((SECONDS-t0)) -lt 7200 ]; do sleep 30; done
if kill -0 $PYPID 2>/dev/null; then
  kill $PYPID; sleep 10; kill -0 $PYPID 2>/dev/null && kill -9 $PYPID
  echo "$(date +%T) probe7 TIMEOUT@7200s" >> "$D/probe7.log"
else
  wait $PYPID; RC=$?
  echo "$(date +%T) probe7 EXITED rc=$RC cell=$([ -f $D/cell.json ] && echo yes || echo no) wall=$((SECONDS-t0))s" >> "$D/probe7.log"
fi
