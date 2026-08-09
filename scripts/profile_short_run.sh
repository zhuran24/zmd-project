#!/usr/bin/env bash
#
# Phase 3C P1 #20 — py-spy --native profile of a short campaign run
#
# 用法:
#   bash scripts/profile_short_run.sh [duration_sec] [campaign_hours]
# 默认 1200s (20 min) py-spy / 0.4h (24 min) main.py budget.
#
# 输出:
#   data/telemetry/profile_<timestamp>/flamegraph.svg
#   data/telemetry/profile_<timestamp>/main.log
#
# py-spy 比 main.py 早 4 min 退出, main.py 自然走完 campaign-hours
# budget 后退出. 跨双层 (Python + native C++) 采样: 看到 ortools.so
# 的真热点 (CP-SAT propagator / GLOP simplex / etc.).

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DURATION_SEC="${1:-1200}"
CAMPAIGN_HOURS="${2:-0.4}"

TS="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${PROJECT_ROOT}/data/telemetry/profile_${TS}"
mkdir -p "$OUT_DIR"

PY_SPY="${PROJECT_ROOT}/.venv/bin/py-spy"
echo "[profile] duration=${DURATION_SEC}s, campaign_hours=${CAMPAIGN_HOURS}, out=${OUT_DIR}"

# py-spy wraps run_campaign_linux.sh which already sets jemalloc + taskset.
# --subprocesses: trace fork()-spawned worker processes too
# --native: include C/C++ frames (ortools.so etc.)
# --rate 100: 100 samples/sec/thread (default)
exec "$PY_SPY" record \
    --native \
    --subprocesses \
    --rate 100 \
    --duration "$DURATION_SEC" \
    --output "${OUT_DIR}/flamegraph.svg" \
    -- bash "${PROJECT_ROOT}/scripts/run_campaign_linux.sh" \
        --campaign-hours "$CAMPAIGN_HOURS" \
        --parallel-processes 1 \
    2>&1 | tee "${OUT_DIR}/main.log"
