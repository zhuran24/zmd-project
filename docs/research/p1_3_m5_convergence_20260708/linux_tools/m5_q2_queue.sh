#!/bin/bash
# M5 Q2 队列（2026-07-09 凌晨）：三个未试旋钮串行，任一出解自动跑 attach-off 孪生
# Q2a = 重建布局直喂（community hint）+ 修复上限 1000；Q2b = ghost_first 档；Q2c = 修复上限单变量
cd /home/zhuran24/zmd-pj
DIR=docs/research/p1_3_m5_convergence_20260708
LOG=$DIR/results_scan/scan_progress.log
RUNNER=$DIR/m5_cell_runner.py
BASE="--ghost-w 6 --ghost-h 6 --binding-seconds 600 --routing-seconds 600 --max-iterations 3 --workers 24 --probing-level 1 --symmetry-level 1 --max-memory-mb 28000"

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
WINENV=""

# Q2a: 重建布局直喂 + 修复上限 1000 + automatic
export EXACT_COMMUNITY_BLUEPRINT_HINT_PATH=/home/zhuran24/m5_runs/rebuilt_hints/hint_anchor132.json
export EXACT_MASTER_HINT_CONFLICT_LIMIT=1000
run_cell g6x6_q2a_bluehint --attach on --master-seconds 1800 --master-branching automatic
unset EXACT_COMMUNITY_BLUEPRINT_HINT_PATH EXACT_MASTER_HINT_CONFLICT_LIMIT
if solved g6x6_q2a_bluehint; then WINNER="q2a"; WINENV="bluehint"; fi

# Q2b: ghost_first 档（fixed 分支吃 profile 指引）
if [ -z "$WINNER" ]; then
  run_cell g6x6_q2b_ghostfirst --attach on --master-seconds 1800 --search-profile exact_coordinate_ghost_first_v1
  if solved g6x6_q2b_ghostfirst; then WINNER="q2b"; WINENV="ghostfirst"; fi
fi

# Q2c: 修复上限 1000 单变量（ghost-agnostic hint）
if [ -z "$WINNER" ]; then
  export EXACT_MASTER_HINT_CONFLICT_LIMIT=1000
  run_cell g6x6_q2c_hintlimit --attach on --master-seconds 1800 --master-branching automatic
  unset EXACT_MASTER_HINT_CONFLICT_LIMIT
  if solved g6x6_q2c_hintlimit; then WINNER="q2c"; WINENV="hintlimit"; fi
fi

if [ -n "$WINNER" ]; then
  echo "=== Q2_WINNER=$WINNER — running attach-off twin $(date -Iseconds) ===" >> $LOG
  case "$WINNER" in
    q2a)
      export EXACT_COMMUNITY_BLUEPRINT_HINT_PATH=/home/zhuran24/m5_runs/rebuilt_hints/hint_anchor132.json
      export EXACT_MASTER_HINT_CONFLICT_LIMIT=1000
      run_cell g6x6_q2a_bluehint_off --attach off --master-seconds 1800 --master-branching automatic
      unset EXACT_COMMUNITY_BLUEPRINT_HINT_PATH EXACT_MASTER_HINT_CONFLICT_LIMIT ;;
    q2b)
      run_cell g6x6_q2b_ghostfirst_off --attach off --master-seconds 1800 --search-profile exact_coordinate_ghost_first_v1 ;;
    q2c)
      export EXACT_MASTER_HINT_CONFLICT_LIMIT=1000
      run_cell g6x6_q2c_hintlimit_off --attach off --master-seconds 1800 --master-branching automatic
      unset EXACT_MASTER_HINT_CONFLICT_LIMIT ;;
  esac
fi

echo "=== Q2_QUEUE_DONE winner=${WINNER:-none} $(date -Iseconds) ===" >> $LOG
