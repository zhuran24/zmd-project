#!/bin/bash
# Production wrapper: 168h campaign with -p 2 + workers=1 (throughput 2x).
#
# spike#6 verified workers=1 master.solve peak RAM 12.78 GB plateau (vs
# baseline 30 GB at workers=8). -57% propagation buffer.
#
# 数学 fit: 2 × 12.78 × 1.25 (25% buffer) + 8 host = 39.95 GB < 47 GB
# hardware (7 GB headroom).
#
# Usage:
#   bash scripts/run_campaign_p2_workers1.sh [other main.py args]
#
# Defaults to -p 2 (双 outer 并行, 2x throughput). 单 candidate master.solve
# wall 慢 (workers=1 search diversity 弱), 但 baseline 8 workers 也 0 FEASIBLE
# (subagent verified problem 本质难度), 减 worker 不 lose 真 quality.
#
# 风险: workers=1 search 弱可能让某些 candidate UNKNOWN 升级 INFEASIBLE 误
# 报概率略增. 24h trial 验 first (跑 24h 看 candidates_proven_per_hour vs
# baseline).

set -u
cd "$(dirname "$0")/.."

# spike#6 plateau 12.78 GB rock stable 3+ min, +10% buffer = 14 GB (aggressive
# but spike-verified). 2 × 14 + 8 host = 36 GB < 40 GB idle avail (~4 GB margin).
# 若 24h trial 实测 RSS 涨 → 调到 16 GB +25% conservative buffer.
export EXACT_MASTER_CP_SAT_WORKERS="${EXACT_MASTER_CP_SAT_WORKERS:-1}"
export EXACT_GATE_WORKER_PEAK_RSS_GIB="${EXACT_GATE_WORKER_PEAK_RSS_GIB:-14}"

# default --parallel-processes 2 if user 不显式 set
PARALLEL_SET=false
for a in "$@"; do
    case "$a" in
        --parallel-processes|--parallel-processes=*) PARALLEL_SET=true ;;
    esac
done

if [ "$PARALLEL_SET" = false ]; then
    # 加 -p 2 默认
    set -- --parallel-processes 2 "$@"
fi

echo "[run_campaign_p2_workers1] EXACT_MASTER_CP_SAT_WORKERS=$EXACT_MASTER_CP_SAT_WORKERS"
echo "[run_campaign_p2_workers1] EXACT_GATE_WORKER_PEAK_RSS_GIB=$EXACT_GATE_WORKER_PEAK_RSS_GIB"

exec bash scripts/run_campaign_linux.sh "$@"
