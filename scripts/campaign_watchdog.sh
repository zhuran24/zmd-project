#!/usr/bin/env bash
#
# 168h campaign watchdog daemon
#
# 终末地求解器 outer_search 设计: candidate UNKNOWN 是 terminal stop reason
# (max_lex 字典序正确性要求). 当前求解能力下 candidate 频繁撞 UNKNOWN,
# campaign 短命退出 (实测 30 min 一次). 168h budget 用不满.
#
# Watchdog 策略: 每 60s 检查 main.py 是否活, 死了就 setsid+nohup 重启.
# main.py 内部按 elapsed_seconds 算 budget, 168h 真用完后立即退出, watchdog
# 重启会再启但 main 立刻 stop (budget exhausted), 自然终止循环.
#
# 用法:
#   nohup bash scripts/campaign_watchdog.sh > data/telemetry/watchdog.log 2>&1 &
#
# 停止:
#   pkill -f campaign_watchdog.sh
#
# 配套:
#   - run_campaign_linux.sh wrapper (jemalloc + P-core + auto --resume-campaign)
#   - main.py default master/binding/routing-seconds = 1800s (audit-tuned)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WRAPPER="$SCRIPT_DIR/run_campaign_linux.sh"
PID_FILE="$PROJECT_ROOT/data/telemetry/campaign.pid"
LOG_DIR="$PROJECT_ROOT/data/telemetry"
CHECK_INTERVAL=60

# 重启保护参数: 去掉总次数硬 cap (2026-05-11 教训: cap=100 时 168h 大跑只跑了
# 15-17h 就被强制停 + 烧电 0 产出 5h 因 watchdog 早退), 只保留 QUICK_DEATH 保护
# 防真死循环 (main 启动期崩 5 次连续就 abort, 不会 infinite restart).
RESTART_CAP=0               # 0 = 无上限 (依赖 QUICK_DEATH 兜底)
QUICK_DEATH_THRESHOLD=60    # 启动到死 < N 秒 = quick death
QUICK_DEATH_CONSECUTIVE=5   # 连续 N 次 quick death 触发停机
restart_count=0
quick_death_streak=0
last_start_ts=0

mkdir -p "$LOG_DIR"

start_campaign() {
    local ts
    ts="$(date +%Y%m%d_%H%M%S)"
    local log_file="$LOG_DIR/campaign_run_${ts}_watchdog.log"
    echo "[watchdog $(date -Iseconds)] starting campaign (#$((restart_count+1))) → $log_file"
    setsid nohup bash "$WRAPPER" \
        --campaign-hours 168.0 --parallel-processes 4 \
        --master-seconds 7200 --binding-seconds 7200 --routing-seconds 7200 \
        > "$log_file" 2>&1 < /dev/null &
    disown
    local pid=$!
    echo "$pid" > "$PID_FILE"
    last_start_ts=$(date +%s)
    echo "[watchdog $(date -Iseconds)] launched pid=$pid"
    sleep 5
}

is_alive() {
    local pid="$1"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

abort_daemon() {
    local reason="$1"
    echo "[watchdog $(date -Iseconds)] STOPPING daemon: $reason"
    rm -f "$PID_FILE"
    exit 0
}

echo "[watchdog $(date -Iseconds)] daemon started, check_interval=${CHECK_INTERVAL}s, restart_cap=$RESTART_CAP, quick_death_threshold=${QUICK_DEATH_THRESHOLD}s/${QUICK_DEATH_CONSECUTIVE}consecutive"

# 启动初始进程
current_pid=""
[[ -f "$PID_FILE" ]] && current_pid="$(cat "$PID_FILE" 2>/dev/null || echo "")"
if ! is_alive "$current_pid"; then
    start_campaign
    restart_count=$((restart_count+1))
fi

while true; do
    sleep "$CHECK_INTERVAL"
    current_pid=""
    [[ -f "$PID_FILE" ]] && current_pid="$(cat "$PID_FILE" 2>/dev/null || echo "")"

    if is_alive "$current_pid"; then
        # main 还活, 重置 quick_death streak
        quick_death_streak=0
        continue
    fi

    # main 死了, 算这次跑了多久
    now=$(date +%s)
    duration=$((now - last_start_ts))
    echo "[watchdog $(date -Iseconds)] pid=$current_pid is dead after ${duration}s"

    # 硬 cap (0 = 无上限, 跳过检查)
    if [[ $RESTART_CAP -gt 0 && $restart_count -ge $RESTART_CAP ]]; then
        abort_daemon "restart_cap=$RESTART_CAP reached"
    fi

    # quick death 连续检测
    if [[ $duration -lt $QUICK_DEATH_THRESHOLD ]]; then
        quick_death_streak=$((quick_death_streak+1))
        echo "[watchdog $(date -Iseconds)] quick death streak=$quick_death_streak/$QUICK_DEATH_CONSECUTIVE"
        if [[ $quick_death_streak -ge $QUICK_DEATH_CONSECUTIVE ]]; then
            abort_daemon "$QUICK_DEATH_CONSECUTIVE consecutive quick deaths (< ${QUICK_DEATH_THRESHOLD}s) — likely no more progress (all candidates done or persistent infrastructure failure)"
        fi
    else
        quick_death_streak=0
    fi

    start_campaign
    restart_count=$((restart_count+1))
done
