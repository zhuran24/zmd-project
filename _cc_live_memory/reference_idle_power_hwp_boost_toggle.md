---
name: idle-power-hwp-boost-toggle
description: "host-level perf 调优 idle 时全 revert 默认 + 正式/试生产前恢复. 待机 100+W 真凶是 idle=poll + max_cstate=0 (cmdline), HWP boost 跟 PPD performance 次要."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-22 用户原话: "现在待机功耗就有100+w" + "先把所有调优暂时都改回去,
后续要正式开始生产或者试生产的时候再改回来".

## 待机 100+W 真凶 (按贡献排)

i9-13900KS + CachyOS, 多层叠加但 cmdline 是大头:

1. **cmdline `idle=poll` + `intel_idle.max_cstate=0` + `processor.max_cstate=0`**
   — CPU 永远不进 C1/C6/C8 deep sleep, idle 也 busy-loop 100% load. **这是
   idle 100W 真正大头, 不是 HWP boost**. CLAUDE.md 之前没写全这几个.
2. **isolcpus=0-7 副作用** — P-core 全 800 MHz idle 正常, 但所有 user-space
   task (systemd / msedge / coolercontrold / netdata / claude) 都被 kernel
   推到 E-core (cpu8-23). E-core 持续有 load → HWP 一直 boost 4.5 GHz.
3. **PPD performance + HWP dynamic boost = 1** — 即使切 PPD balanced, HWP
   boost=1 让 CPU 见 load 仍激进 boost. 次要 vs cmdline.
4. **runaway user process** (常见 msedge tab 卡死 117% CPU) — 跟调优无关, 但
   叠加 idle=poll/no-cstate 时功耗成倍.

## 完整 revert 工序 (2026-05-22 已执行)

```bash
# 1. backup current cmdline (撤销前快照)
sudo cp /boot/loader/entries/linux-cachyos.conf \
        /boot/loader/entries/linux-cachyos.conf.bak.YYYYMMDD_pre_revert_tuning

# 2. restore stock cmdline (revert 全 cmdline 调优) — 需重启生效
sudo cp /boot/loader/entries/linux-cachyos.conf.bak.20260510_pre_isolcpus \
        /boot/loader/entries/linux-cachyos.conf
# stock cmdline: rw zswap.enabled=0 nowatchdog quiet splash (无其他 perf flag)

# 3. disable HWP dynamic boost service (重启不自启)
sudo systemctl disable hwp-dynamic-boost.service
# runtime 关 (立刻生效):
echo 0 | sudo tee /sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost

# 4. PPD 切 balanced (默认行为, 让 governor 真降 idle freq)
powerprofilesctl set balanced

# 5. disable sysctl tuning (revert vm.swappiness / dirty_ratio / inotify 等)
sudo mv /etc/sysctl.d/99-zmd-tuning.conf \
        /etc/sysctl.d/99-zmd-tuning.conf.bak.YYYYMMDD_disabled
sudo sysctl --system

# 6. pacman freeze — 平时该 unfrozen (CLAUDE.md 写过), verify:
bash scripts/pacman_campaign_freeze.sh --status   # 期望 UNFROZEN
```

### 立刻生效 vs 重启生效

| 项 | 生效 | revert effect |
|---|---|---|
| HWP boost runtime + service | 立刻 (echo 0 + stop/disable) | idle 时 CPU 不预防性 boost |
| PPD performance → balanced | 立刻 | governor 真降 idle freq (但 cmdline 限) |
| sysctl 99-zmd-tuning.conf disable | 立刻 (sysctl --system) | vm.swappiness=0 等回默认 |
| **cmdline (idle=poll/cstate/isolcpus)** | **重启** | **idle 真深度休眠, ~30-50W baseline** |
| pacman freeze | 立刻 | 平时 unfrozen 该是默认 |

cmdline 不重启不生效 — 当前 session 还跑 idle=poll. **真见 30-50W 待机需重启**.

## 正式/试生产开始前恢复 (再调优 on)

```bash
# 1. cmdline 加回所有 perf flag
sudo tee /boot/loader/entries/linux-cachyos.conf <<'EOF'
title Linux Cachyos
options root=UUID=549e7395-b764-4971-af60-dcbff5d14b59 rw zswap.enabled=0 nowatchdog quiet splash mitigations=off isolcpus=0-7 nohz_full=0-7 rcu_nocbs=0-7 irqaffinity=8-23 rcu_nocb_poll intel_idle.max_cstate=0 processor.max_cstate=0 idle=poll transparent_hugepage=always
linux /vmlinuz-linux-cachyos
initrd /initramfs-linux-cachyos.img
EOF

# 2. HWP boost service enable + 立刻起
sudo systemctl enable hwp-dynamic-boost.service
sudo systemctl start hwp-dynamic-boost.service
echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost

# 3. PPD performance
powerprofilesctl set performance

# 4. sysctl 调优 re-enable
sudo mv /etc/sysctl.d/99-zmd-tuning.conf.bak.YYYYMMDD_disabled \
        /etc/sysctl.d/99-zmd-tuning.conf
sudo sysctl --system

# 5. 重启让 cmdline 生效
sudo reboot

# 6. 启动前 readiness gate (当前 11 项 = 5 blocker + 6 warning, 以脚本 docstring 为准)
.venv/bin/python scripts/production_readiness_gate.py

# 7. pacman freeze (campaign 启动前)
bash scripts/pacman_campaign_freeze.sh --enable

# 8. campaign 用 wrapper (jemalloc + P-core pin + THP)
bash scripts/run_campaign_linux.sh --campaign-hours 168.0 --parallel-processes 4
```

## 真凶完整分解 (待重启验证)

revert 全 cmdline 后预期 idle:
- idle=poll 关 → CPU 可 hlt + 进 C-state
- max_cstate 限制移除 → C6/C8 deep sleep 可用 → CPU idle 几瓦
- isolcpus 移除 → P-core (5.6 GHz 闲置) 也可被 scheduler 用, task 不再
  全堆 E-core → load 分散 + 各 core 都能降频
- mitigations 移除 → CPU vuln mitigations 重启 (轻微 overhead 但不影响 idle)

预期重启后 idle 30-50W (i9-13900KS + nvidia GPU + 主板 baseline).

## Apply when

- 用户提"功耗高 / 电费 / 发热 / 待机太热"
- idle pkg 温度 ≥ 60°C 持续 (正常 < 50°C)
- E-core 跑 max freq idle (期望 < 2 GHz)
- 不在 168h campaign 跑期间 (campaign 中 perf 调优必须保留)

## 文件位置 (backup 索引)

- `/boot/loader/entries/linux-cachyos.conf` — 当前 cmdline (revert 后 stock)
- `/boot/loader/entries/linux-cachyos.conf.bak.20260510_pre_isolcpus` — stock baseline
- `/boot/loader/entries/linux-cachyos.conf.bak.20260510_pre_mitigations` — 同 stock
- `/boot/loader/entries/linux-cachyos.conf.bak.20260521_pre_latency` — 同 stock
- `/boot/loader/entries/linux-cachyos.conf.bak.20260522_pre_revert_tuning` — 调优全套 (用作恢复)
- `/etc/sysctl.d/99-zmd-tuning.conf.bak.20260522_disabled` — sysctl 调优 (重启 enable 改回 .conf 即可)

## Refs

- CLAUDE.md "CachyOS 主机生产力调优 (host-level, 2026-05-10)" 段
- [[workload-latency-bound-not-bandwidth]] — 项目 perf 调优 latency-bound 假设
- scripts/production_readiness_gate.py — 168h campaign 启动前 gate (当前 11 项 = 5 blocker + 6 warning, 随门禁演进以脚本 docstring 为准)
- scripts/pacman_campaign_freeze.sh — 包冻结 toggle
