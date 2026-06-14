---
name: claude-installer-download-stall
description: 本机 claude install / 自动更新下载器会卡死 (0 TCP 连接、0 字节文件)，启动器 shim 用符号链接修，别死磕下载器
metadata: 
  node_type: memory
  type: reference
  originSessionId: 7bc35788-90db-4f24-b9b9-239535020d15
---

本机 (Windows 11, 用户 22957) Claude Code 自带下载器全坏：`claude install` 和启动时自动更新都会卡死——进程活着但**零 TCP 连接**，`C:\Users\22957\.local\share\claude\versions\<版本号>` 永远 0 字节。网络本身通 (直连 storage.googleapis.com 成功)，根因未明 (2026-06-10 排查：无代理 env、无锁文件、无报错输出)。

**Why:** 启动警告 "claude command at C:\Users\22957\.local\bin\claude.exe missing or broken" 的官方修法 `claude install` 在本机走不通；重试只会再卡 20 分钟。

**How to apply:** 实际生效的 claude 二进制由 Claude Desktop 维护在 `C:\Users\22957\AppData\Roaming\Claude\claude-code\current\claude.exe` (它的更新机制是好的)。2026-06-10 修了两件事才消警告：(1) 符号链接 `C:\Users\22957\.local\bin\claude.exe` → 该路径 (官方检查代码会 readlink 验证目标，symlink 是受支持的形态)；(2) 把 `C:\Users\22957\.local\bin` 追加进 User PATH 注册表末尾 (注意 .NET SetEnvironmentVariable 会把 REG_EXPAND_SZ 改成 REG_SZ，已手动改回 ExpandString)。否则报 "Native installation exists but ~/.local/bin is not in your PATH"。若警告复现先查这两项，而不是跑 `claude install`。系统有 Clash (127.0.0.1:7890) 但当时处于关闭状态；如以后要真修下载器，可试开代理再 install。
