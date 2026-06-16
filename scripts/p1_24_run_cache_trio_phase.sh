#!/usr/bin/env bash
#
# P1 #24 验证 phase 2: baseline 完成后切到 cache-trio 跑.
# 假设 baseline 状态已经在 data/checkpoints/, 这个 script 做:
# 1. snapshot baseline state + telemetry → .artifacts/p1_24_validation/baseline_run/
# 2. wipe data/checkpoints/exact_campaign_state.json + telemetry.json
# 3. exec cache-trio 30 min run via wrapper (background detach)
#
# 用法:
#   bash scripts/p1_24_run_cache_trio_phase.sh
#
# Cache-trio run 退出后会留下 data/checkpoints/{state, telemetry}.json
# 调用方应再 cp 这两个文件到 .artifacts/p1_24_validation/cache_trio_run/

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

VALIDATION_DIR="$PROJECT_ROOT/.artifacts/p1_24_validation"
BASELINE_DIR="$VALIDATION_DIR/baseline_run_p2"
TRIO_DIR="$VALIDATION_DIR/cache_trio_run_p2"

mkdir -p "$BASELINE_DIR" "$TRIO_DIR"

# Phase 1: snapshot baseline outputs
echo "[phase2] snapshotting baseline state → $BASELINE_DIR"
if [[ -f data/checkpoints/exact_campaign_state.json ]]; then
    cp data/checkpoints/exact_campaign_state.json "$BASELINE_DIR/exact_campaign_state.json"
fi
if [[ -f data/checkpoints/exact_campaign_telemetry.json ]]; then
    cp data/checkpoints/exact_campaign_telemetry.json "$BASELINE_DIR/exact_campaign_telemetry.json"
fi

# Phase 2: wipe state for fresh cache-trio start
echo "[phase2] wiping checkpoint state"
rm -f data/checkpoints/exact_campaign_state.json data/checkpoints/exact_campaign_telemetry.json

# Phase 3: launch cache-trio (wrapper handles jemalloc + taskset)
echo "[phase2] launching cache-trio @ $(date -Iseconds)"
nohup bash scripts/run_campaign_linux.sh \
    --campaign-hours 0.5 \
    --parallel-processes 2 \
    --skip-readiness-gate \
    > "$TRIO_DIR/stdout.log" 2> "$TRIO_DIR/stderr.log" &

echo "[phase2] cache-trio PID=$!"
echo "[phase2] log: $TRIO_DIR/stdout.log"
echo "[phase2] ETA exit: ~30 min wall-clock"
