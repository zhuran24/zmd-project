#!/bin/bash
# Production wrapper: 168h campaign with EXACT_MASTER_CP_SAT_WORKERS=2.
#
# spike#5 verified workers=2 master.solve peak RAM 16.4 GB (vs baseline 30 GB
# at workers=8). 减 45% propagation buffer. solve quality same level (both
# 8-worker baseline + 2-worker spike return UNKNOWN, problem 难度本质非 worker
# 问题).
#
# Usage:
#   bash scripts/run_campaign_workers2.sh [--parallel-processes N] [other main.py args]
#
# Defaults to -p 1 (safe at 16.4 GB peak + 8 GB host = 24 GB < 47 GB).
# -p 2 候选 (待 spike#6 workers=1 数据 verify, 见
# docs/phase3c_master_ram_findings_20260515.md).

set -u
cd "$(dirname "$0")/.."

# spike#5 plateau 16.4 GB, +25% buffer = 20.5 GB conservative for production
# (per-worker peak estimate for readiness gate OOM check).
export EXACT_MASTER_CP_SAT_WORKERS="${EXACT_MASTER_CP_SAT_WORKERS:-2}"
export EXACT_GATE_WORKER_PEAK_RSS_GIB="${EXACT_GATE_WORKER_PEAK_RSS_GIB:-20.5}"
# 防 main.py 在 UNKNOWN 后 auto-stop (实测 workers≤2 trial 大量 UNKNOWN)
export EXACT_OUTER_SKIP_UNKNOWN="${EXACT_OUTER_SKIP_UNKNOWN:-1}"

echo "[run_campaign_workers2] EXACT_MASTER_CP_SAT_WORKERS=$EXACT_MASTER_CP_SAT_WORKERS"
echo "[run_campaign_workers2] EXACT_GATE_WORKER_PEAK_RSS_GIB=$EXACT_GATE_WORKER_PEAK_RSS_GIB"

exec bash scripts/run_campaign_linux.sh "$@"
