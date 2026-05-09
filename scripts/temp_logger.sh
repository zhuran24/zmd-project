#!/usr/bin/env bash
#
# Phase 3C — 简易温度 / 频率 logger（168h campaign thermal monitoring）
#
# 用法（campaign 启动前后台启）：
#   nohup bash scripts/temp_logger.sh 60 > data/telemetry/temp_log.csv 2>&1 &
#   # campaign 结束后手动 kill: pkill -f temp_logger.sh
#
# 输出 CSV 列：timestamp_iso,pkg_c,ecore_max_c,max_pcore_freq_mhz
# - pkg_c: CPU 整体 package temp，从 /sys/class/thermal/x86_pkg_temp 读
#   (直接从 PCH/MSR 读, 不依赖 lm_sensors coretemp 模块)
# - ecore_max_c: E-core (Core 32-47) 中最高温度
#   * 注意: 开 isolcpus=0-7 后 lm_sensors coretemp 不再报 P-core
#     温度。pkg_c 已包含 P-core 的整体热量，足够监控 thermal throttle
#   * E-core max 拿来交叉验证 (E-core 不被隔离, 也跑系统 daemon)
# - max_pcore_freq_mhz: P-core (cpu0-7) 当前最高频
#
# 监控目的: 13900KS 在 PPD performance 下持续负载 thermal throttle 阈值
# ~90°C+。如果 pkg_c 持续 ≥ 90°C 且 max_pcore_freq_mhz 显著低于 5600,
# 撞 thermal throttle ——散热不够 / PPD 切回 balanced。

set -euo pipefail

INTERVAL_SEC="${1:-60}"

# Locate x86_pkg_temp thermal zone (one-time)
PKG_TEMP_ZONE=""
for z in /sys/class/thermal/thermal_zone*; do
    if [[ -r "$z/type" ]] && [[ "$(cat "$z/type")" == "x86_pkg_temp" ]]; then
        PKG_TEMP_ZONE="$z/temp"
        break
    fi
done
if [[ -z "$PKG_TEMP_ZONE" ]]; then
    echo "WARN: x86_pkg_temp thermal zone not found — pkg_c column will be empty" >&2
fi

# CSV header
echo "timestamp_iso,pkg_c,ecore_max_c,max_pcore_freq_mhz"

while true; do
    ts="$(date -Iseconds)"

    # Package temp from x86_pkg_temp (millidegC -> degC with 1 decimal)
    pkg_c=""
    if [[ -n "$PKG_TEMP_ZONE" ]] && [[ -r "$PKG_TEMP_ZONE" ]]; then
        millideg="$(cat "$PKG_TEMP_ZONE")"
        # awk for floating point; bash arithmetic is integer only
        pkg_c="$(awk -v m="$millideg" 'BEGIN { printf "%.1f", m/1000 }')"
    fi

    # E-core max temp (Core 32-47) via sensors -j; tolerate parse failure
    ecore_max_c="$(sensors -j 2>/dev/null | /home/zhuran24/claude-pj/zmd/.venv/bin/python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ct = d.get('coretemp-isa-0000', {})
    temps = []
    for k, v in ct.items():
        if k.startswith('Core ') and isinstance(v, dict):
            for sk, sv in v.items():
                if sk.endswith('_input'):
                    temps.append(float(sv))
                    break
    print(f'{max(temps):.1f}' if temps else '')
except Exception:
    print('')
" 2>/dev/null || echo "")"

    # Max P-core (cpu0-7) current freq via cpufreq
    max_pcore_freq=0
    for cpu in 0 1 2 3 4 5 6 7; do
        f="/sys/devices/system/cpu/cpu${cpu}/cpufreq/scaling_cur_freq"
        if [[ -r "$f" ]]; then
            v="$(cat "$f")"
            (( v > max_pcore_freq )) && max_pcore_freq="$v"
        fi
    done
    max_pcore_mhz=$(( max_pcore_freq / 1000 ))

    echo "${ts},${pkg_c},${ecore_max_c},${max_pcore_mhz}"
    sleep "$INTERVAL_SEC"
done
