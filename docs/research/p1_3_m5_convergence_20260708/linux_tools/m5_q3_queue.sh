#!/bin/bash
# M5 Q3 队列（2026-07-09 凌晨，对抗复核出土的弹药）：
# Q3z = q2b 假崩复现测试（清缓存后）；Q3a = no_overlap_2d 传播器套装；Q3b = 甩掉 LP subsolver；
# Q3c = PORTFOLIO 分支；Q3d = 组合拳。任一出解自动跑 attach-off 孪生。
cd /home/zhuran24/zmd-pj
DIR=docs/research/p1_3_m5_convergence_20260708
LOG=$DIR/results_scan/scan_progress.log
RUNNER=$DIR/m5_cell_runner.py
BASE="--ghost-w 6 --ghost-h 6 --binding-seconds 600 --routing-seconds 600 --max-iterations 3 --workers 24 --probing-level 1 --symmetry-level 1 --max-memory-mb 28000"

# 复现测试前先清缓存（假崩假设的前提）
find /home/zhuran24/zmd-pj -name "__pycache__" -type d -not -path "*/.venv/*" -exec rm -rf {} + 2>/dev/null

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

# Q3z: q2b 复现测试（ghost_first 档，清缓存后；崩=真 bug，跑满=假崩坐实）
run_cell g6x6_q3z_ghostfirst_retry --attach on --master-seconds 1800 --search-profile exact_coordinate_ghost_first_v1
if solved g6x6_q3z_ghostfirst_retry; then WINNER="q3z"; fi

# Q3a: no_overlap_2d 传播器三件套（packing 专用，模型正是 no_overlap_2d-heavy）
if [ -z "$WINNER" ]; then
  export EXACT_MASTER_NO_OVERLAP_2D_AREA_ENERGETIC=1
  export EXACT_MASTER_NO_OVERLAP_2D_TIMETABLING=1
  export EXACT_MASTER_NO_OVERLAP_2D_TRY_EDGE=1
  run_cell g6x6_q3a_no2d_props --attach on --master-seconds 1800 --master-branching automatic
  unset EXACT_MASTER_NO_OVERLAP_2D_AREA_ENERGETIC EXACT_MASTER_NO_OVERLAP_2D_TIMETABLING EXACT_MASTER_NO_OVERLAP_2D_TRY_EDGE
  if solved g6x6_q3a_no2d_props; then WINNER="q3a"; fi
fi

# Q3b: 甩掉 LP subsolver（算力全导向 LP-free 重启式可行性搜索）
if [ -z "$WINNER" ]; then
  export EXACT_MASTER_IGNORE_LP_SUBSOLVERS=1
  run_cell g6x6_q3b_nolp --attach on --master-seconds 1800 --master-branching automatic
  unset EXACT_MASTER_IGNORE_LP_SUBSOLVERS
  if solved g6x6_q3b_nolp; then WINNER="q3b"; fi
fi

# Q3c: PORTFOLIO 分支（三值中唯一没跑过的）
if [ -z "$WINNER" ]; then
  run_cell g6x6_q3c_portfolio --attach on --master-seconds 1800 --master-branching portfolio
  if solved g6x6_q3c_portfolio; then WINNER="q3c"; fi
fi

# Q3d: 组合拳（no_overlap_2d 套 + 无 LP + automatic）
if [ -z "$WINNER" ]; then
  export EXACT_MASTER_NO_OVERLAP_2D_AREA_ENERGETIC=1
  export EXACT_MASTER_NO_OVERLAP_2D_TIMETABLING=1
  export EXACT_MASTER_NO_OVERLAP_2D_TRY_EDGE=1
  export EXACT_MASTER_IGNORE_LP_SUBSOLVERS=1
  run_cell g6x6_q3d_combo --attach on --master-seconds 1800 --master-branching automatic
  unset EXACT_MASTER_NO_OVERLAP_2D_AREA_ENERGETIC EXACT_MASTER_NO_OVERLAP_2D_TIMETABLING EXACT_MASTER_NO_OVERLAP_2D_TRY_EDGE EXACT_MASTER_IGNORE_LP_SUBSOLVERS
  if solved g6x6_q3d_combo; then WINNER="q3d"; fi
fi

if [ -n "$WINNER" ]; then
  echo "=== Q3_WINNER=$WINNER $(date -Iseconds) — 手动跑 attach-off 孪生（配置见本脚本对应块）===" >> $LOG
fi
echo "=== Q3_QUEUE_DONE winner=${WINNER:-none} $(date -Iseconds) ===" >> $LOG
