#!/usr/bin/env bash
#
# Phase 3C P2 #19 — pacman 关键包冻结/解冻 toggle (CachyOS 168h campaign 稳定性)
#
# 用法:
#   bash scripts/pacman_campaign_freeze.sh --enable      # 168h campaign 启动前调用
#   bash scripts/pacman_campaign_freeze.sh --disable     # campaign 结束后调用
#   bash scripts/pacman_campaign_freeze.sh --status      # 看当前状态
#
# 锁定的包（CachyOS 滚动 + 168h 长跑期间不能 break）:
#   - linux-cachyos*       (BORE kernel + headers)
#   - glibc                (ortools manylinux wheel 依赖)
#   - python               (3.14 — 升 minor 可能 break venv 链接)
#   - jemalloc tcmalloc    (LD_PRELOAD 用)
#
# 平时（非 campaign 期间）应保持 unfreeze 状态让系统跟最新。

set -euo pipefail

PACMAN_CONF="/etc/pacman.conf"
MARKER_BEGIN="# === Phase 3C campaign freeze BEGIN ==="
MARKER_END="# === Phase 3C campaign freeze END ==="
IGNORE_LINE="IgnorePkg = linux-cachyos linux-cachyos-headers linux-cachyos-bore linux-cachyos-bore-headers glibc python jemalloc gperftools"

action="${1:---status}"

case "$action" in
    --enable)
        if grep -qF "$MARKER_BEGIN" "$PACMAN_CONF"; then
            echo "Already frozen — pacman.conf has campaign-freeze markers."
            grep -A 1 "$MARKER_BEGIN" "$PACMAN_CONF"
            exit 0
        fi
        echo "Adding campaign freeze block to $PACMAN_CONF (sudo password may be needed)..."
        echo "" | sudo tee -a "$PACMAN_CONF" > /dev/null
        echo "$MARKER_BEGIN" | sudo tee -a "$PACMAN_CONF" > /dev/null
        echo "$IGNORE_LINE" | sudo tee -a "$PACMAN_CONF" > /dev/null
        echo "$MARKER_END" | sudo tee -a "$PACMAN_CONF" > /dev/null
        echo
        echo "✅ Frozen. Subsequent 'pacman -Syu' will skip these packages:"
        echo "   linux-cachyos*, glibc, python, jemalloc, gperftools"
        echo
        echo "To temporarily upgrade one anyway: pacman -S --ignore= ..."
        echo "To unfreeze after the campaign: $0 --disable"
        ;;
    --disable)
        if ! grep -qF "$MARKER_BEGIN" "$PACMAN_CONF"; then
            echo "Not frozen — no campaign-freeze markers found in $PACMAN_CONF."
            exit 0
        fi
        echo "Removing campaign freeze block from $PACMAN_CONF (sudo password may be needed)..."
        sudo sed -i "/$MARKER_BEGIN/,/$MARKER_END/d" "$PACMAN_CONF"
        # also clean up the leading blank line we added (best effort, no-op if not present)
        sudo sed -i '/^$/N;/^\n$/d' "$PACMAN_CONF"
        echo "✅ Unfrozen. 'pacman -Syu' will now upgrade all packages normally."
        ;;
    --status)
        if grep -qF "$MARKER_BEGIN" "$PACMAN_CONF"; then
            echo "Status: 🔒 FROZEN (campaign mode)"
            echo
            grep -A 2 "$MARKER_BEGIN" "$PACMAN_CONF"
        else
            echo "Status: 🔓 UNFROZEN (normal mode — pacman -Syu upgrades everything)"
        fi
        ;;
    *)
        echo "Usage: $0 [--enable | --disable | --status]" >&2
        exit 2
        ;;
esac
