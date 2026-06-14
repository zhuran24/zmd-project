---
name: cc-api-watchdog
description: "CC 会话自助工具索引 (C:\\Users\\22957\\cc_watchdog\\): API 断线自动续跑看门狗 + 上下文自查/给自己发消息 + 自主压缩协议 + 通用坑, 见子节点"
metadata:
  node_type: memory
  type: reference
  originSessionId: 37712a00-f4f3-4562-a3e0-d17d137f4de6
---

CC 在自己会话里用的两套自助工具 (都在 `C:\Users\22957\cc_watchdog\`, 互不依赖) + 通用坑, 已拆为聚焦子节点:

- [[cc-watchdog-api-resume]] — ① API/网络中断自动续跑看门狗 cc_api_watchdog.ps1 (检测 isApiErrorMessage 标记 + 注入「继续」)
- [[cc-selfguard-context-send]] — ② cc_model_selfguard.ps1 的 -Context 上下文自查 + -Send 给自己发消息/斜杠命令的工具机制
- [[cc-autonomous-compaction-protocol]] — 自主压缩协议 (≥~400k 触发 + 压缩前记忆树仪式 + 睡觉状态选发送模式)
- [[cc-watchdog-misc-pitfalls]] — 两套通用坑 (Defender 行为检测重启误报 + 杀 claude 只按 PID 不按进程名)
