#!/usr/bin/env bash
#
# P1 #24 follow-up B: 跑各 CP-SAT 参数组合 -p 1 短跑 (2 min) 量 main RSS ramp.
# 找压到 ~14 GB 以下的 combo, 让 -p 2 production 跑得动.
#
# 每个 combo:
#   1. wipe state
#   2. nohup main.py 启动 (background)
#   3. 每 5s 记 main RSS 进 csv
#   4. 2 min 后杀 main
#   5. 输出 peak RSS + RSS @ 60s
#
# Abort 条件: RSS > 32 GB (32 ÷ 41 avail 留 buffer 防 OOM)
#
# 用法: bash scripts/p1_24_cpsat_param_sweep.sh

set -uo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

OUTDIR=".artifacts/p1_24_validation/cpsat_param_sweep"
mkdir -p "$OUTDIR"
echo "combo,peak_rss_gb,rss_at_30s_gb,rss_at_60s_gb,rss_at_90s_gb,rss_at_120s_gb,aborted" > "$OUTDIR/results.csv"

# Combo definitions: name|env_value
COMBOS=(
    "default|"
    "cleanup_only|clause_cleanup_period=3000,clause_cleanup_ratio=0.8"
    "cleanup_probing|clause_cleanup_period=3000,clause_cleanup_ratio=0.8,cp_model_probing_level=0"
    "cleanup_probing_lin|clause_cleanup_period=3000,clause_cleanup_ratio=0.8,cp_model_probing_level=0,linearization_level=0"
)

for combo_def in "${COMBOS[@]}"; do
    name="${combo_def%%|*}"
    params="${combo_def#*|}"
    echo ""
    echo "======================================="
    echo "Combo: $name"
    echo "Params: $params"
    echo "======================================="

    # wipe state for fresh start
    rm -f data/checkpoints/exact_campaign_state.json data/checkpoints/exact_campaign_telemetry.json

    # spawn
    if [ -n "$params" ]; then
        EXACT_SUBPROBLEM_PARAMS="$params" nohup .venv/bin/python main.py \
            --campaign-hours 0.05 --parallel-processes 1 --skip-readiness-gate \
            > "$OUTDIR/${name}.log" 2>&1 &
    else
        nohup .venv/bin/python main.py \
            --campaign-hours 0.05 --parallel-processes 1 --skip-readiness-gate \
            > "$OUTDIR/${name}.log" 2>&1 &
    fi

    sleep 2
    MAIN_PID=$(pgrep -f '\.venv/bin/python main\.py' | head -1)
    if [ -z "$MAIN_PID" ]; then
        echo "  ERROR: main.py did not start"
        continue
    fi

    echo "  main PID: $MAIN_PID"

    # sample RSS every 5s for 120s (or abort if > 32 GB)
    peak_kb=0
    rss_30=""
    rss_60=""
    rss_90=""
    rss_120=""
    aborted="false"
    > "$OUTDIR/${name}.rss.csv"
    echo "ts_s,rss_gb" >> "$OUTDIR/${name}.rss.csv"

    for i in $(seq 1 24); do
        sleep 5
        elapsed=$((i * 5))
        rss_kb=$(ps -p $MAIN_PID -o rss= 2>/dev/null | tr -d ' ')
        if [ -z "$rss_kb" ]; then
            echo "  main exited at ${elapsed}s"
            break
        fi
        rss_gb=$(awk -v r="$rss_kb" 'BEGIN {printf "%.2f", r/1048576}')
        echo "  t=${elapsed}s rss=${rss_gb}GB"
        echo "${elapsed},${rss_gb}" >> "$OUTDIR/${name}.rss.csv"
        if [ "$rss_kb" -gt "$peak_kb" ]; then peak_kb="$rss_kb"; fi
        if [ "$elapsed" -eq 30 ]; then rss_30="$rss_gb"; fi
        if [ "$elapsed" -eq 60 ]; then rss_60="$rss_gb"; fi
        if [ "$elapsed" -eq 90 ]; then rss_90="$rss_gb"; fi
        if [ "$elapsed" -eq 120 ]; then rss_120="$rss_gb"; fi
        # abort if dangerous
        if [ "$rss_kb" -gt 33554432 ]; then
            echo "  ABORT: rss=${rss_gb}GB > 32 GB"
            aborted="true"
            break
        fi
    done

    # kill main + any spawn workers
    kill -TERM $MAIN_PID 2>/dev/null
    sleep 2
    pkill -KILL -f '\.venv/bin/python main\.py' 2>/dev/null
    pkill -KILL -f "from multiprocessing.spawn" 2>/dev/null
    sleep 2

    peak_gb=$(awk -v r="$peak_kb" 'BEGIN {printf "%.2f", r/1048576}')
    echo "  RESULT: peak=${peak_gb}GB rss_at_60s=${rss_60} aborted=${aborted}"
    echo "${name},${peak_gb},${rss_30},${rss_60},${rss_90},${rss_120},${aborted}" >> "$OUTDIR/results.csv"
done

echo ""
echo "==== sweep done ===="
cat "$OUTDIR/results.csv" | column -t -s,
