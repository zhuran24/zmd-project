---
name: claude-config-backup
description: "**(旧 Linux/CachyOS 主机 reference; 当前 CC 在 Windows 跑, 下述 systemd/外盘路径不适用)** ~/.claude.json daily 自动备份到外盘 (systemd timer, 2026-05-20 装). 防 ENOSPC / 覆盖事故. 含恢复命令 + 不要重蹈覆辙的硬警告."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

> **⚠️ 本机制属旧 Linux (CachyOS) 主机环境** (systemd user timer + 外盘 `/mnt/wd_external`)。当前 CC harness 跑在 **Windows**(用户目录 `C:\Users\22957`, 无 systemd), 下述 systemd/外盘路径与恢复命令在 Windows 上**不可执行**, 仅在回到 Linux 主机时有效 —— 别在 Windows 下 .claude.json 损坏时照搬这些 Linux 命令。

## 自动备份机制 (2026-05-20 起)

**为啥有这个**: 2026-05-20 磁盘 / 89% 满 ENOSPC, claude 写 `~/.claude.json` 用 truncate-before-write 模式 → 老内容清空 → 0 字节 → invalid JSON → claude 启动报 "JSON Parse error: Unexpected EOF". Claude 当时 `echo '{}' > ~/.claude.json` 修了 invalid JSON 但**丢了所有 user config** (theme / login token / project history / settings).

之后装了 daily 自动备份防再发生.

## 备份位置

**外盘归档目录**: `/mnt/wd_external/claude_config_backups/`

格式: `.claude.json.YYYYMMDD_HHMMSS` (hidden file 以 `.` 开头, `ls` 默认不显示, 用 `ls -la`)

保留: 最近 30 天, 老的自动 rotate 删

## 触发机制

- **systemd user timer**: `~/.config/systemd/user/claude-config-backup.timer`
- **频率**: daily (默认 00:00)
- **Persistent**: 错过 (系统关机) 开机自动 catch-up
- **service file**: `~/.config/systemd/user/claude-config-backup.service`
- **backup 脚本**: `~/.local/bin/backup_claude_config.sh` (size check: < 10 bytes warn 但仍备份, forensic 用途)

查 status: `systemctl --user status claude-config-backup.timer`
下次触发: `systemctl --user list-timers claude-config-backup.timer`
手动跑: `~/.local/bin/backup_claude_config.sh`

## 恢复命令 (万一 `.claude.json` 再坏)

```bash
# 列最近 backup
ls -la /mnt/wd_external/claude_config_backups/

# 取最新的恢复 (按文件名排序)
LATEST=$(ls -t /mnt/wd_external/claude_config_backups/.claude.json.* | head -1)
cp "$LATEST" ~/.claude.json

# 验证 JSON 有效
python3 -c "import json; json.load(open('$HOME/.claude.json')); print('VALID')"
```

恢复后**不必重新 onboard / 重新 login** — backup 含完整 config (theme + login token + project history + settings).

## ⚠️ Claude 必读 — 不要重蹈覆辙

**绝对不要**用以下命令覆盖 `~/.claude.json`:
- `echo '{}' > ~/.claude.json` — 直接清空老内容
- `cat > ~/.claude.json` — 同上
- 任何 truncate-before-write 操作不 backup

**如果发现 `~/.claude.json` 坏 (0 字节 / invalid JSON), 先**:
1. **backup 当前坏内容**: `cp ~/.claude.json ~/.claude.json.broken_$(date +%Y%m%d_%H%M%S)`
2. **从外盘恢复**: `cp /mnt/wd_external/claude_config_backups/.claude.json.<最新> ~/.claude.json`
3. 不要直接覆盖成 `{}` — 失去所有 user config 触发 onboard 重来

## 相关 memory

- [[cachyos-paste-and-nm]] — 本机环境配置
- [[hardware-constraint-single-machine]] — 硬件状态

(项目无关 user-level config 备份, 不在 project memory 范畴, 但写在此项目 memory 因为只有此项目 memory 系统已经 setup)
