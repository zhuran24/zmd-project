#!/usr/bin/env bash
#
# Phase 3C — 简易温度 / 频率 logger（168h campaign thermal monitoring）
#
# 用法（campaign 启动前后台启）：
#   nohup bash scripts/temp_logger.sh 60 > data/telemetry/temp_log.csv 2>&1 &
#   # campaign 结束后手动 kill: pkill -f temp_logger.sh
#
# 输出 CSV 列：timestamp_iso,package_c,max_core_c,max_pcore_freq_mhz
# - package_c: CPU 整体 temp（lm_sensors Package id 0）
# - max_core_c: 所有核里最高温度
# - max_pcore_freq_mhz: P-core (cpu0-7) 当前最高频
#
# 监控目的: 13900KS 在 PPD performance 下持续负载 thermal throttle 阈值
# ~90°C+。如果 max_core_c 持续 ≥ 90°C 且 max_pcore_freq_mhz 显著低于
# 5600，说明撞 throttle 了——要么散热不够，要么把 PPD 切回 balanced。

set -euo pipefail

INTERVAL_SEC="${1:-60}"

# CSV header
echo "timestamp_iso,package_c,max_core_c,max_pcore_freq_mhz"

while true; do
    ts="$(date -Iseconds)"
    # parse sensors -j with python (already installed)
    temps_line="$(sensors -j 2>/dev/null | /home/zhuran24/claude-pj/zmd/.venv/bin/python -c "
import sys, json
d = json.load(sys.stdin)
ct = d.get('coretemp-isa-0000', {})
pkg = ct.get('Package id 0', {}).get('temp1_input', None)
core_temps = []
for k, v in ct.items():
    if k.startswith('Core ') and isinstance(v, dict):
        for sub_k, sub_v in v.items():
            if sub_k.endswith('_input'):
                core_temps.append(float(sub_v))
                break
max_c = max(core_temps) if core_temps else None
print(f\"{pkg if pkg is not None else ''},{max_c if max_c is not None else ''}\")
" 2>/dev/null || echo ",")"
    # Max P-core (cpu0-7) freq via cpufreq
    max_pcore_freq=0
    for cpu in 0 1 2 3 4 5 6 7; do
        f="/sys/devices/system/cpu/cpu${cpu}/cpufreq/scaling_cur_freq"
        if [[ -r "$f" ]]; then
            v="$(cat "$f")"
            if (( v > max_pcore_freq )); then
                max_pcore_freq="$v"
            fi
        fi
    done
    # cpufreq is in kHz; convert to MHz
    max_pcore_mhz=$(( max_pcore_freq / 1000 ))
    echo "${ts},${temps_line},${max_pcore_mhz}"
    sleep "$INTERVAL_SEC"
done
