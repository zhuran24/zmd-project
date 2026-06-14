---
name: no-gpt-dispatch-command-and-downgrade
description: "GPT 外发首选通道=零 token 自动化脚本 dispatch_gpt_task.py --pack --prompt-file;前置 start_gpt_automation_chrome.ps1 默认 attach 用户日常 Edge 主实例(无端口时会温和重启 Edge,重启后端口丢需重跑 start);Pro 静默降级唯一判据=生成耗时(5min 内极大概率降级,脚本默认 300s),托底两层=插件通道手动/ChatGPT 桌面 App 通道(CDP 9224)"
metadata:
  node_type: memory
  type: feedback
---

**首选通道(2026-06-11 起):外发自动化脚本,全程零 token。** `python cc_context\review\gpt_dispatch\dispatch_gpt_task.py --pack --prompt-file <md>`。前置 = `start_gpt_automation_chrome.ps1`:**默认 attach 用户日常 Edge 主实例**(用户裁决,不搞独立 profile,直接用已登录态零配置)。**⚠️ 重要 caveat:Edge 在跑但没带调试端口时,start 脚本会温和重启用户的 Edge**——跑之前先想想用户是不是正用着浏览器,必要时知会;Edge 每次正常重启后端口就丢了,下次 dispatch 前要再跑一次 start。打包→上传→发送→等完成→收交付全自动;挂了 `--resume <会话URL>` 续;完整流程已验收(含 40MB 包、附件 404 自动救援)。退出码/细节见项目 CLAUDE.md runbook 段。**Pro 静默降级(用户经验)**:无任何明面标注(DOM model-slug 照写 pro,不可信),唯一判据 = 生成耗时(真实审查/实现任务要 30min+,**5min 内完成 = 极大概率降级**;脚本默认判据已改 300s);处置 = 脚本自动刷新重跑一次,仍快(exit 5)→ 托底两层:① 我改走插件通道手动发收(同一个 Edge 上的 Claude in Chrome 插件);② 还不行切 **ChatGPT 桌面 App 通道**(`start 脚本 -App` 以 MSIX 包身份带 CDP 9224 启动,dispatch 加 `--cdp-url http://localhost:9224`;Electron,DOM 与网页同构,不同客户端可能不同限流池)。
