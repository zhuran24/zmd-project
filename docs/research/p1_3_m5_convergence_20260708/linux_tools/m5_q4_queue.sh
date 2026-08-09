#!/bin/bash
# M5 Q4 收尾队列：q3b/q3c 缓存鬼复跑 + ghost_first 首次完整跑。w12（防 OOM）、每发前清缓存（防撕裂鬼）。
cd /home/zhuran24/zmd-pj
DIR=docs/research/p1_3_m5_convergence_20260708
LOG=$DIR/results_scan/scan_progress.log
RUNNER=$DIR/m5_cell_runner.py
BASE="--ghost-w 6 --ghost-h 6 --binding-seconds 600 --routing-seconds 600 --max-iterations 3 --workers 12 --probing-level 1 --symmetry-level 1 --max-memory-mb 28000"

clean_cache() {
  find /home/zhuran24/zmd-pj -name "__pycache__" -type d -not -path "*/.venv/*" -exec rm -rf {} + 2>/dev/null
}

run_cell() {
  local name=$1; shift
  clean_cache
  .venv/bin/python $RUNNER $BASE "$@" --out $DIR/results_scan/cell_$name.json \
    > /home/zhuran24/m5_runs/$name.log 2>&1
  echo "=== $name done exit=$? $(date -Iseconds) ===" >> $LOG
}

# q4a: 无 LP subsolver（q3b 的缓存鬼复跑）
export EXACT_MASTER_IGNORE_LP_SUBSOLVERS=1
run_cell g6x6_q4a_nolp_retry --attach on --master-seconds 1800 --master-branching automatic
unset EXACT_MASTER_IGNORE_LP_SUBSOLVERS

# q4b: PORTFOLIO 分支（q3c 的段错误复跑）
run_cell g6x6_q4b_portfolio_retry --attach on --master-seconds 1800 --master-branching portfolio

# q4c: ghost_first 档首次完整跑（q3z 死于 w24 OOM，w12 复测）
run_cell g6x6_q4c_ghostfirst_w12 --attach on --master-seconds 1800 --search-profile exact_coordinate_ghost_first_v1

echo "=== Q4_QUEUE_DONE $(date -Iseconds) ===" >> $LOG
