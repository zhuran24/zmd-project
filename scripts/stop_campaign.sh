#!/usr/bin/env bash
# Stop all 168h campaign processes cleanly.
#
# 杀:
#   - main.py --campaign-hours (single or parallel)
#   - 其 multiprocessing.spawn 子 worker
#   - campaign_watchdog.sh
#   - /tmp/zmd_campaign_watchdog.lock stale file
#
# 绝不动:
#   - Claude Code 进程 (claude, node, npm)
#   - 心跳 watcher (CC_PID 监控 bash + tail -F + Monitor pipeline)
#   - 其他 Python / shell session
#
# 用法:
#   bash scripts/stop_campaign.sh          # graceful: TERM → 5s → KILL 残留
#   bash scripts/stop_campaign.sh --force  # 直接 KILL, 不等
#   bash scripts/stop_campaign.sh --dry-run  # 只列, 不杀

set -u

FORCE=0
DRY=0
for arg in "$@"; do
    case "$arg" in
        --force) FORCE=1 ;;
        --dry-run) DRY=1 ;;
        -h|--help)
            sed -n '2,15p' "$0"; exit 0 ;;
        *) echo "unknown arg: $arg" >&2; exit 2 ;;
    esac
done

WATCHDOG_LOCK="/tmp/zmd_campaign_watchdog.lock"

collect_pids() {
    # 主 main + watchdog + main 的 multiprocessing 子 worker.
    # 严格匹配避免误杀其他 python / shell.
    local main_pids=()
    local watchdog_pids=()
    local worker_pids=()

    # main.py with --campaign-hours arg
    while IFS= read -r pid; do
        [[ -n "$pid" ]] && main_pids+=("$pid")
    done < <(pgrep -f "main\.py.*--campaign-hours" 2>/dev/null || true)

    # watchdog shell loop
    while IFS= read -r pid; do
        [[ -n "$pid" ]] && watchdog_pids+=("$pid")
    done < <(pgrep -f "campaign_watchdog\.sh" 2>/dev/null || true)

    # multiprocessing workers of main_pids — 用 pgrep -P 递归找子树
    if [[ ${#main_pids[@]} -gt 0 ]]; then
        local frontier=("${main_pids[@]}")
        local visited=""
        while [[ ${#frontier[@]} -gt 0 ]]; do
            local next=()
            for parent in "${frontier[@]}"; do
                while IFS= read -r child; do
                    [[ -z "$child" ]] && continue
                    if ! grep -q "(^| )$child( |$)" <<<"$visited"; then
                        worker_pids+=("$child")
                        next+=("$child")
                        visited="$visited $child"
                    fi
                done < <(pgrep -P "$parent" 2>/dev/null || true)
            done
            frontier=("${next[@]}")
        done
    fi

    # 输出 dedup
    printf '%s\n' "${main_pids[@]}" "${watchdog_pids[@]}" "${worker_pids[@]}" \
        | awk 'NF && !seen[$0]++'
}

list_targets() {
    local pids=()
    while IFS= read -r p; do [[ -n "$p" ]] && pids+=("$p"); done < <(collect_pids)
    if [[ ${#pids[@]} -eq 0 ]]; then
        echo "[stop_campaign] 无 campaign 进程"
        return 1
    fi
    echo "[stop_campaign] 待 kill 进程列表:"
    for p in "${pids[@]}"; do
        ps -p "$p" -o pid,etime,pcpu,cmd --no-headers 2>/dev/null \
            | sed 's/^/  /'
    done
    return 0
}

if [[ $DRY -eq 1 ]]; then
    list_targets || true
    echo "[stop_campaign] DRY-RUN, 不执行 kill"
    if [[ -e "$WATCHDOG_LOCK" ]]; then
        echo "[stop_campaign] would also rm $WATCHDOG_LOCK"
    fi
    exit 0
fi

list_targets
HAVE_TARGETS=$?

if [[ $HAVE_TARGETS -ne 0 && ! -e "$WATCHDOG_LOCK" ]]; then
    echo "[stop_campaign] 无需操作"
    exit 0
fi

# 防误杀确认 — 列出 Claude / 心跳进程让用户看到没碰它们
echo
echo "[stop_campaign] 以下进程 **不会** 被动 (sanity check):"
pgrep -af "tail -F.*zmd_heartbeat" 2>/dev/null | sed 's/^/  KEEP: /' || true
pgrep -af "HEARTBEAT.*date.*+%Y-%m-%d" 2>/dev/null | sed 's/^/  KEEP: /' || true
pgrep -af "^claude " 2>/dev/null | head -3 | sed 's/^/  KEEP: /' || true

PIDS=()
while IFS= read -r p; do [[ -n "$p" ]] && PIDS+=("$p"); done < <(collect_pids)

if [[ ${#PIDS[@]} -gt 0 ]]; then
    if [[ $FORCE -eq 1 ]]; then
        echo
        echo "[stop_campaign] --force: 直接 SIGKILL"
        kill -KILL "${PIDS[@]}" 2>/dev/null || true
    else
        echo
        echo "[stop_campaign] step 1: SIGTERM"
        kill -TERM "${PIDS[@]}" 2>/dev/null || true
        sleep 5
        # 再 collect, 剩下的 KILL
        REMAINING=()
        while IFS= read -r p; do [[ -n "$p" ]] && REMAINING+=("$p"); done < <(collect_pids)
        if [[ ${#REMAINING[@]} -gt 0 ]]; then
            echo "[stop_campaign] step 2: SIGKILL 残留 ${#REMAINING[@]} 个"
            kill -KILL "${REMAINING[@]}" 2>/dev/null || true
            sleep 1
        fi
    fi
fi

# stale lock file
if [[ -e "$WATCHDOG_LOCK" ]]; then
    if fuser "$WATCHDOG_LOCK" >/dev/null 2>&1; then
        echo "[stop_campaign] $WATCHDOG_LOCK 仍有 holder, 不删"
    else
        rm -f "$WATCHDOG_LOCK"
        echo "[stop_campaign] removed stale $WATCHDOG_LOCK"
    fi
fi

# 验证
echo
echo "[stop_campaign] 最终检查:"
LEFT=$(collect_pids | wc -l)
if [[ "$LEFT" -eq 0 ]]; then
    echo "  ✓ campaign 进程清零"
else
    echo "  ✗ 仍有 $LEFT 个 campaign 进程, 列表:"
    collect_pids | while read -r p; do
        ps -p "$p" -o pid,etime,cmd --no-headers 2>/dev/null | sed 's/^/    /'
    done
    exit 1
fi

# 健康提示心跳还在
HB=$(pgrep -f "tail -F.*zmd_heartbeat" 2>/dev/null | head -1)
if [[ -n "$HB" ]]; then
    echo "  ✓ 心跳 watcher 仍活 (PID $HB) — 未被误动"
fi
exit 0
