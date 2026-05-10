#!/usr/bin/env bash
# heartbeat_reset.sh — Claude Code SessionStart + UserPromptSubmit hook
#
# 每次 CC session 启动 + 每次 user 主动 prompt submit 时, kill 旧 sleep loop
# + 启新 loop, 实现 reset 模式心跳.
#
# 多 session 隔离: CLAUDE_CODE_SESSION_ID 区分 PID/marker file.
#
# CC 关闭自动 cleanup: 启动时找父链里的 claude 进程 (CC root PID),
# loop 每 iter 检查该 PID 还活, 死了立刻 exit (max 延迟 = INTERVAL).

set -e

SESSION_ID="${CLAUDE_CODE_SESSION_ID:-default}"
PIDFILE="/tmp/zmd_heartbeat_${SESSION_ID}.pid"
MARKER="/tmp/zmd_heartbeat_${SESSION_ID}.log"
INTERVAL=180
MAX_ITER=480  # 24h cap (兜底, CC 真死前 PID 检测先 trigger)

# 找父链里的 claude 进程当 CC root PID
CC_PID=""
_pid="$PPID"
for _i in 1 2 3 4 5 6; do
    [[ -z "$_pid" || "$_pid" == "0" || "$_pid" == "1" ]] && break
    _cmd="$(ps -o cmd= -p "$_pid" 2>/dev/null | head -1 || true)"
    if [[ "$_cmd" =~ ^claude ]] || [[ "$_cmd" =~ /claude($|\ ) ]]; then
        CC_PID="$_pid"
        break
    fi
    _pid="$(ps -o ppid= -p "$_pid" 2>/dev/null | tr -d ' ' || true)"
done

# kill 旧 loop (本 session 的)
if [[ -f "$PIDFILE" ]]; then
    OLD_PID="$(cat "$PIDFILE" 2>/dev/null || true)"
    if [[ -n "$OLD_PID" ]]; then
        kill "$OLD_PID" 2>/dev/null || true
    fi
fi

# 截断 marker
: > "$MARKER"

# 启新 loop, 把 CC_PID 传进去当退出条件
setsid nohup bash -c "
iter=0
while [[ \$iter -lt $MAX_ITER ]]; do
    sleep $INTERVAL
    # CC 死了 loop 自杀 (avoid orphan loop 跑 24h)
    if [[ -n '$CC_PID' ]] && ! kill -0 '$CC_PID' 2>/dev/null; then
        exit 0
    fi
    echo \"--- HEARTBEAT \$(date '+%Y-%m-%dT%H:%M:%S') ---\" >> \"$MARKER\"
    iter=\$((iter+1))
done
" > /dev/null 2>&1 < /dev/null &
disown
NEW_PID=$!

echo "$NEW_PID" > "$PIDFILE"
exit 0
