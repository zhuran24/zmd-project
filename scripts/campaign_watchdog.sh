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

mkdir -p "$LOG_DIR"

start_campaign() {
    local ts
    ts="$(date +%Y%m%d_%H%M%S)"
    local log_file="$LOG_DIR/campaign_run_${ts}_watchdog.log"
    echo "[watchdog $(date -Iseconds)] starting campaign → $log_file"
    setsid nohup bash "$WRAPPER" \
        --campaign-hours 168.0 --parallel-processes 4 \
        > "$log_file" 2>&1 < /dev/null &
    disown
    local pid=$!
    echo "$pid" > "$PID_FILE"
    echo "[watchdog $(date -Iseconds)] launched pid=$pid"
    sleep 5  # 给进程一点 startup 时间
}

is_alive() {
    local pid="$1"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

# 主循环
echo "[watchdog $(date -Iseconds)] daemon started, check interval=${CHECK_INTERVAL}s"

# 启动初始进程 (如果当前没在跑)
current_pid=""
if [[ -f "$PID_FILE" ]]; then
    current_pid="$(cat "$PID_FILE" 2>/dev/null || echo "")"
fi

if ! is_alive "$current_pid"; then
    start_campaign
fi

while true; do
    sleep "$CHECK_INTERVAL"
    current_pid=""
    if [[ -f "$PID_FILE" ]]; then
        current_pid="$(cat "$PID_FILE" 2>/dev/null || echo "")"
    fi
    if ! is_alive "$current_pid"; then
        echo "[watchdog $(date -Iseconds)] pid=$current_pid is dead, restarting"
        start_campaign
    fi
done
