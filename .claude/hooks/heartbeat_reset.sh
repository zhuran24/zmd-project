#!/usr/bin/env bash
# heartbeat_reset.sh — Claude Code SessionStart + UserPromptSubmit hook
#
# 每次 CC session 启动 + 每次 user 主动 prompt submit 时, kill 旧 sleep loop
# + 启新 loop, 实现 reset 模式心跳.
#
# Session 隔离: 用 CC root PID (从 PPID 链找父进程里的 claude 命令) 当 ID,
# 不依赖 CLAUDE_CODE_SESSION_ID env (实测 Claude Code fire hook 时不传该
# env 给 subprocess, fallback 'default' 会让多 session 互相 kill).
# 用 CC_PID 当 ID 既保证 multi-session 隔离, 又跟 CC 进程同生死.
#
# CC 关闭自动 cleanup: loop 每 iter `kill -0 $CC_PID` 检查, 死了立刻 exit
# (max 延迟 = INTERVAL = 180s). 兜底 MAX_ITER=480 (24h cap).

set -e

INTERVAL=180
MAX_ITER=480

# 找父链里的 claude 进程当 CC root PID + session ID
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

# CC_PID 找不到 (异常场景) → fallback PPID, 至少有个隔离 ID
[[ -z "$CC_PID" ]] && CC_PID="$PPID"

PIDFILE="/tmp/zmd_heartbeat_${CC_PID}.pid"
MARKER="/tmp/zmd_heartbeat_${CC_PID}.log"

# kill 旧 loop (本 session 的)
if [[ -f "$PIDFILE" ]]; then
    OLD_PID="$(cat "$PIDFILE" 2>/dev/null || true)"
    if [[ -n "$OLD_PID" ]]; then
        kill "$OLD_PID" 2>/dev/null || true
    fi
fi

# 截断 marker
: > "$MARKER"

# 启新 loop
setsid nohup bash -c "
iter=0
while [[ \$iter -lt $MAX_ITER ]]; do
    sleep $INTERVAL
    if ! kill -0 '$CC_PID' 2>/dev/null; then
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
