---
name: cachyos-paste-and-nm
description: 用户主机 (CachyOS + KDE Wayland) 已配置：wl-clipboard 让 cc Ctrl+V 贴图；NM 探测 URL 改国内端点防"受限"误报；zhuran24 全局 NOPASSWD sudo
type: reference
originSessionId: aa49aecd-27de-4e55-bc9c-eabf1ea214a9
---
## isolcpus + nohz_full + cstate=0 + idle=poll 副作用清单 (2026-05-21 latency tuning 后)

跑了 Gemini round 11 latency tuning + reboot 后, 这些 known 副作用全 trigger, 不是 bug:

1. **nohz_full=0-7 被 kernel 强制改 1-7**: kernel 至少留 1 housekeeping CPU 处理 timer tick + kthread 调度. `/sys/devices/system/cpu/nohz_full` 实测 `1-7` 不是 cmdline 写的 `0-7`. cpu0 仍是 housekeeping.

2. **lm_sensors coretemp 不报 P-core**: 已知, 用 `/sys/class/thermal/x86_pkg_temp` zone 替代. `temp_logger.sh` 已正确实施.

3. **top 在 nohz_full CPU 上不准确**: top 用 timer tick 采样, nohz_full=1-7 cpu 没 tick → top 报 idle 但实际 NOP polling. `idle=poll` 让 cpu 1-7 永远 active. 真实利用率看 `perf stat -C 0-7 cycles` 或 cat `/proc/stat`. top 显示 97% idle **误导**.

4. **"P-core 只能响应一个" 不是 bug**: isolcpus 让默认进程不 schedule 到 cpu 0-7. 用户看到"只 cpu0 active" = cpu0 housekeeping 唯一默认跑进程. cpu 1-7 只在显式 `taskset -c` / `sched_setaffinity` 时被用. **必须用 `scripts/run_campaign_linux.sh` wrapper** (已 auto-detect + taskset -c 0-7) 才能 spread CP-SAT workers 到全 8 P-core. 直接 `python main.py` 不走 wrapper 会被推到 E-core.

5. **cpu 0-7 idle 频率 800 MHz**: cstate=0 + idle=poll 阻止 sleep, 但 P-state (频率) 仍 scaling, NOP polling 时 800 MHz 节能. 跑 workload 时频率上 5.6+ GHz.

6. **散热 idle 显著高**: cstate=0 + idle=poll 让 P-core 永远 active. idle pkg_c 60-65°C (vs cstate-on 27°C). 满载 70-90°C 是正常 i9-13900KS 范围, 超 90°C 可能 throttle.

7. **perf / VTune 都没装**: `pacman -S perf` 安 perf, AUR `intel-vtune` 安 VTune. Implementation phase profile 时再装.

---

用户主机环境（CachyOS + KDE Plasma + Wayland，2026-05-10 配置）：

## Claude Code 粘贴图片
- 已装 `wl-clipboard`（pacman），cc 终端 `Ctrl+V` 直接粘剪贴板图片
- KDE 工作流：Spectacle 截图 → "复制到剪贴板" → 切回 cc → `Ctrl+V`，cc 显示 `[Image #N]`
- 原理：cc 在 Linux 上调 `wl-paste`(Wayland) / `xclip`(X11) 读图像剪贴板

## NetworkManager connectivity check
- 配置: `/etc/NetworkManager/conf.d/20-connectivity-cn.conf`
- URL: `http://www.qualcomm.cn/generate_204`（高通中国 captive portal 探测端点）
- 关键: `response=`（空字符串）→ NM 只认 HTTP 204 状态码，不要求 body 含 "NetworkManager is online"
- 默认 `ping.archlinux.org/nm-check.txt` 在国内被 GFW reset，会误报"网络受限"
- 验证: `nmcli networking connectivity check` → `full`
- 备用 URL（如 qualcomm.cn 端点失效）: `http://connect.rom.miui.com/generate_204` / `http://wifi.vivo.com.cn/generate_204`

## 免密 sudo（zhuran24 全局 NOPASSWD）
- 文件: `/etc/sudoers.d/99-zhuran24-nopasswd`
- 内容: `zhuran24 ALL=(ALL) NOPASSWD: ALL`
- **关键坑：必须 99- 前缀**——CachyOS 装机时自带 `/etc/sudoers.d/10-installer` 给 wheel 组规则**不含 NOPASSWD**，按字母序读到这条会覆盖前面的 NOPASSWD。99- 前缀确保最后才生效
- 验证: `sudo -k && sudo -n whoami` → `root`

## 为什么 KDE "记住密码" 勾选对 sudo 无效
- 弹窗是 ksshaskpass（cc 的 sudo 因 stdin 非 tty 走 askpass）
- "记住密码"是把密码存进 KWallet，**给 SSH key passphrase 用的**
- sudo 不读 KWallet，只把 askpass 当一次性密码获取工具
- 用户层面这个勾就是错配，所以现在直接走 NOPASSWD 绕过整个机制
