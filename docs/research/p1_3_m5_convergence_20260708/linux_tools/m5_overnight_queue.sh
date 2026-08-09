#!/bin/bash
# M5 过夜队列（2026-07-08 夜）：A=7200s 长赌 → 不中则 B/C/D 换种子 1800s×3 → 任一出解自动跑 attach-off 孪生
cd /home/zhuran24/zmd-pj
DIR=docs/research/p1_3_m5_convergence_20260708
LOG=$DIR/results_scan/scan_progress.log
RUNNER=$DIR/m5_cell_runner.py
BASE="--ghost-w 6 --ghost-h 6 --binding-seconds 600 --routing-seconds 600 --max-iterations 3 --workers 12 --probing-level 1 --symmetry-level 1 --master-branching automatic --max-memory-mb 28000"

run_cell() {
  local name=$1; shift
  .venv/bin/python $RUNNER $BASE "$@" --out $DIR/results_scan/cell_$name.json \
    > /home/zhuran24/m5_runs/$name.log 2>&1
  echo "=== $name done exit=$? $(date -Iseconds) ===" >> $LOG
}

solved() {
  .venv/bin/python - "$DIR/results_scan/cell_$1.json" << 'PYEOF'
import json, sys
try:
    r = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(1)
ok = r.get("status") not in (None, "UNKNOWN", "HARNESS_EXCEPTION") or r.get("binding_status") is not None
sys.exit(0 if ok else 1)
PYEOF
}

WINNER=""

run_cell g6x6_ovn_7200_on --attach on --master-seconds 7200
if solved g6x6_ovn_7200_on; then WINNER="7200"; fi

if [ -z "$WINNER" ]; then
  for SEED in 7 13 42; do
    export EXACT_MASTER_RANDOM_SEED=$SEED
    run_cell g6x6_ovn_s${SEED}_on --attach on --master-seconds 1800
    unset EXACT_MASTER_RANDOM_SEED
    if solved g6x6_ovn_s${SEED}_on; then WINNER="s${SEED}"; break; fi
  done
fi

if [ -n "$WINNER" ]; then
  echo "=== WINNER=$WINNER — running attach-off twin $(date -Iseconds) ===" >> $LOG
  if [ "$WINNER" = "7200" ]; then
    run_cell g6x6_ovn_7200_off --attach off --master-seconds 7200
  else
    SEED=${WINNER#s}
    export EXACT_MASTER_RANDOM_SEED=$SEED
    run_cell g6x6_ovn_${WINNER}_off --attach off --master-seconds 1800
    unset EXACT_MASTER_RANDOM_SEED
  fi
fi

echo "=== OVERNIGHT_QUEUE_DONE winner=${WINNER:-none} $(date -Iseconds) ===" >> $LOG
