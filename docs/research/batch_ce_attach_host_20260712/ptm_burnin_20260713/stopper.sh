#!/bin/bash
# cycle 3 COOL end 后全停+归档(owner 03:4x 指示:改 BIOS,重启前抢救 /tmp 数据)
D=/tmp/claude-1000/-home-zhuran24-zmd-pj/3e9c4e4c-c0ae-4a71-98f5-05f8b3a5a644/scratchpad/ptm_burnin
ARCH=/home/zhuran24/zmd-pj/docs/research/batch_ce_attach_host_20260712/ptm_burnin_20260713
while ! grep -q "CYCLE 3/5 COOL end" "$D/cycle.log" 2>/dev/null; do sleep 15; done
kill 102208 2>/dev/null          # v4 主脚本
pkill -x stress-ng 2>/dev/null
pkill -f "run-tag ptm_cycle_4" 2>/dev/null   # 保险:若 cycle 4 已被抢跑
kill 79262 2>/dev/null           # mem_sampler
sleep 1
mkdir -p "$ARCH"
cp -r "$D"/. "$ARCH"/ 2>/dev/null
echo "$(date +%T) STOPPED_AND_ARCHIVED -> $ARCH" | tee -a "$D/cycle.log"
