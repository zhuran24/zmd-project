---
name: cc-watchdog-misc-pitfalls
description: "CC 看门狗/自助脚本两套通用坑: ⚠️ 内联 powershell -Command 一把梭 Stop-Process+Start-Process -WindowStyle Hidden 重启后台脚本会触发 Defender 行为检测 Trojan:Win32/PowhidSubExec.B (uv_spawn EPERM, 误报无中招), 正确姿势=按 PID 单独杀旧再逐个 -File ... -Launch 让脚本自派生; 杀 claude 实例只能按 PID 永不按进程名 (防误杀用户会话/Claude Desktop)"
metadata:
  node_type: memory
  type: reference
  originSessionId: 37712a00-f4f3-4562-a3e0-d17d137f4de6
---

## 杂项坑 (cc_watchdog 两套自助工具通用)

适用于 API 断线看门狗 ([[cc-watchdog-api-resume]]) 与 cc_model_selfguard ([[cc-selfguard-context-send]]) 两套。

- **⚠️ Defender 坑**: 内联 `powershell -Command` 一把梭 `Stop-Process + Start-Process -WindowStyle Hidden` 重启后台脚本 → Defender 行为检测 `Trojan:Win32/PowhidSubExec.B` 直接拦 (uv_spawn EPERM, 安全中心「严重」告警)。是行为误报, 无文件中招, 告警可删。**正确姿势**: 按 PID 单独杀旧 (小命令) 后逐个 `-File ... -Launch` 让脚本自己派生。
- **杀 claude 实例只能按 PID, 永远不要按进程名** (会误杀用户会话/Claude Desktop, 见 [[no-workflow-use-chrome-gpt-review]] 同类自我保护原则)。
