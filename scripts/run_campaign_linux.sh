#!/usr/bin/env bash
#
# Phase 3C P1 #24 — 168h campaign launch wrapper (Linux/CachyOS)
#
# 一上午 +15-22% 收益的 3 件套打包：
#   (a) THP — 系统层 already always (CachyOS default), 这个 wrapper 不动
#   (b) jemalloc LD_PRELOAD — 缓解 ptmalloc 多线程 contention, 典型 +5-10%
#   (c) cpuset P-core pinning — 避 E-core 抢占, i9-13900KS P-core 5.6GHz vs
#       E-core 4.5GHz, +2-5% from sticking to high-freq cores
#
# THP 留在系统级（不能在子进程改）。本脚本只管 jemalloc + cpuset。
#
# 用法:
#   bash scripts/run_campaign_linux.sh --campaign-hours 168.0 --parallel-processes 4
#   bash scripts/run_campaign_linux.sh --vis
#   bash scripts/run_campaign_linux.sh --skip-readiness-gate --campaign-hours 1.0  # 调试
#
# 参数透传给 python main.py。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "ERROR: venv python not found at $PYTHON_BIN" >&2
    echo "Run cachyos_setup.sh --apply first" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# (b) jemalloc LD_PRELOAD + PYTHONMALLOC=malloc
# ---------------------------------------------------------------------------
# LD_PRELOAD 让 C 层分配走 jemalloc；PYTHONMALLOC=malloc 让 Python 解释器
# 自己的 pymalloc arena 也跨过去走系统 malloc → 一并 hook 到 jemalloc。
# 没有这一行的话 jemalloc 只 hook 到 ortools C++，Python 自己 ~30% 的分
# 配走 pymalloc 拿不到收益。
JEMALLOC_PATH="/usr/lib/libjemalloc.so.2"
if [[ ! -f "$JEMALLOC_PATH" ]]; then
    echo "WARN: $JEMALLOC_PATH not found — jemalloc LD_PRELOAD skipped." >&2
    echo "      Install via: sudo pacman -S jemalloc" >&2
else
    if [[ -n "${LD_PRELOAD:-}" && "$LD_PRELOAD" != *"jemalloc"* ]]; then
        export LD_PRELOAD="${JEMALLOC_PATH}:${LD_PRELOAD}"
    elif [[ -z "${LD_PRELOAD:-}" ]]; then
        export LD_PRELOAD="$JEMALLOC_PATH"
    fi
    export PYTHONMALLOC=malloc
    echo "[run_campaign_linux] LD_PRELOAD=$LD_PRELOAD"
    echo "[run_campaign_linux] PYTHONMALLOC=$PYTHONMALLOC"
fi

# ---------------------------------------------------------------------------
# (c) Auto-detect P-cores by max CPU frequency
# ---------------------------------------------------------------------------
# Collect (cpu_id, max_freq) and select the cores with the global max freq.
# On i9-13900KS HT-off this gives cpu0-7 (P-core 5600 MHz); E-cores are 4500.
declare -A cpu_freq
max_freq=0
for cpu_dir in /sys/devices/system/cpu/cpu[0-9]*; do
    cpu_id="${cpu_dir##*/cpu}"
    freq_file="${cpu_dir}/cpufreq/cpuinfo_max_freq"
    if [[ -r "$freq_file" ]]; then
        freq="$(cat "$freq_file")"
        cpu_freq[$cpu_id]="$freq"
        if (( freq > max_freq )); then
            max_freq=$freq
        fi
    fi
done

if (( max_freq == 0 )); then
    echo "WARN: could not read cpufreq info — cpuset pinning skipped." >&2
    P_CORE_LIST=""
else
    p_cores=()
    for cpu_id in "${!cpu_freq[@]}"; do
        if [[ "${cpu_freq[$cpu_id]}" == "$max_freq" ]]; then
            p_cores+=("$cpu_id")
        fi
    done
    # Sort numerically
    IFS=$'\n' p_cores_sorted=($(sort -n <<<"${p_cores[*]}"))
    unset IFS
    # Build comma-separated list (taskset accepts both ranges and lists; we
    # use list form for transparency since the count is small).
    P_CORE_LIST="$(IFS=,; echo "${p_cores_sorted[*]}")"
    echo "[run_campaign_linux] detected P-cores (${max_freq} kHz): $P_CORE_LIST"
fi

# ---------------------------------------------------------------------------
# Launch: prefer taskset (always available, no systemd dependency); fall back
# to plain exec if no P-cores detected.
# ---------------------------------------------------------------------------
cd "$PROJECT_ROOT"

if [[ -n "$P_CORE_LIST" ]] && command -v taskset >/dev/null 2>&1; then
    echo "[run_campaign_linux] exec taskset -c $P_CORE_LIST $PYTHON_BIN main.py $*"
    exec taskset -c "$P_CORE_LIST" "$PYTHON_BIN" main.py "$@"
else
    echo "[run_campaign_linux] exec $PYTHON_BIN main.py $* (no cpuset pinning)"
    exec "$PYTHON_BIN" main.py "$@"
fi
