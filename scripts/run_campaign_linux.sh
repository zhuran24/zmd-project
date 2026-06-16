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

# EXACT_POWER_PLACEMENT_SUBPROBLEM 当前是 exploratory — cut scope 没补齐 (P0 #1/#2)
# 进 certified path 会误切合法布局, wrapper 拒启动.
case "${EXACT_POWER_PLACEMENT_SUBPROBLEM:-}" in
    ""|0|false|False) ;;
    *)
        echo "ERROR: EXACT_POWER_PLACEMENT_SUBPROBLEM=$EXACT_POWER_PLACEMENT_SUBPROBLEM" >&2
        echo "  当前 exploratory only — ghost-conditioned cut + pole alternatives" >&2
        echo "  exhaustion 未实现, 进 certified path 风险过切. unset 后重跑." >&2
        exit 3
        ;;
esac

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
    # 2026-05-21 latency tuning: jemalloc 极致 tunables (Gemini round 11)
    # narenas:1            single-process workload 单 arena 减碎片 + TLB 压力
    # metadata_thp:always  jemalloc 内部 metadata 走 THP 减 TLB miss
    # dirty_decay_ms:-1    禁 madvise(MADV_DONTNEED) 内存永驻进程 (减 minor page fault + 内核态切换)
    # muzzy_decay_ms:-1    同 dirty_decay 处理 muzzy state, 内存只增不减 (CP-SAT 单机专用 OK)
    export JEMALLOC_CONF="narenas:1,metadata_thp:always,dirty_decay_ms:-1,muzzy_decay_ms:-1"
    echo "[run_campaign_linux] LD_PRELOAD=$LD_PRELOAD"
    echo "[run_campaign_linux] PYTHONMALLOC=$PYTHONMALLOC"
    echo "[run_campaign_linux] JEMALLOC_CONF=$JEMALLOC_CONF"
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
# Auto-inject --resume-campaign for campaign runs (audit F MED 修复)
# 防止崩溃后用户手动重启时忘加 → 从头开始跑丢进度.
# 只在用户传了 --campaign-hours 时注入 (--vis 等非 campaign 模式不加).
# ---------------------------------------------------------------------------
args=("$@")
has_resume=false
is_campaign=false
parallel_value=""
prev_was_parallel=false
for a in "${args[@]}"; do
    if $prev_was_parallel; then
        parallel_value="$a"
        prev_was_parallel=false
        continue
    fi
    case "$a" in
        --resume-campaign|--resume-campaign=*) has_resume=true ;;
        --campaign-hours|--campaign-hours=*) is_campaign=true ;;
        --parallel-processes) prev_was_parallel=true ;;
        --parallel-processes=*) parallel_value="${a#--parallel-processes=}" ;;
    esac
done
if $is_campaign && ! $has_resume; then
    args+=("--resume-campaign")
    echo "[run_campaign_linux] 自动注入 --resume-campaign (audit F MED: 防崩溃重启忘加丢进度)"
fi
# Forward --parallel-processes 到 env 给 readiness gate 读 (gate 内部用 env, 不直接读 argv)
if [[ -n "$parallel_value" ]]; then
    export EXACT_PARALLEL_PROCESSES="$parallel_value"
    echo "[run_campaign_linux] EXACT_PARALLEL_PROCESSES=$parallel_value (forwarded for readiness gate)"
fi

# ---------------------------------------------------------------------------
# Launch: prefer taskset (always available, no systemd dependency); fall back
# to plain exec if no P-cores detected.
# ---------------------------------------------------------------------------
cd "$PROJECT_ROOT"

if [[ -n "$P_CORE_LIST" ]] && command -v taskset >/dev/null 2>&1; then
    echo "[run_campaign_linux] exec taskset -c $P_CORE_LIST $PYTHON_BIN main.py ${args[*]}"
    exec taskset -c "$P_CORE_LIST" "$PYTHON_BIN" main.py "${args[@]}"
else
    echo "[run_campaign_linux] exec $PYTHON_BIN main.py ${args[*]} (no cpuset pinning)"
    exec "$PYTHON_BIN" main.py "${args[@]}"
fi
