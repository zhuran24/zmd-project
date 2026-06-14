---
name: chatgpt-browser-automation-pitfalls
description: chatgpt.com 浏览器/CDP 自动化(zmd gpt_dispatch + MCP)所有实测坑的索引节点;具体坑见各聚焦子节点
metadata: 
  node_type: memory
  type: reference
  originSessionId: 1d0fe198-5723-4668-85c2-edc9cf1fa94a
---

2026-06 给 zmd 写 `gpt_dispatch` 外发自动化(Playwright `connect_over_cdp` / raw CDP 接管专用 Chrome)+ 后续 MCP(claude-in-chrome)手动通道调试出的 chatgpt.com 自动化经验,跨项目适用。已按触发情境拆成聚焦子节点:

- [[chatgpt-login-and-completion-detection]] — 登录态(302 重定向)/完成检测双信号/Pro 静默降级判据/文字稳≠交付完成
- [[chatgpt-attachment-capture]] — 附件三形态 + 结构 class 判据 + CDP 浏览器级下载捕获 + GUID/已删除 痕迹
- [[chatgpt-sandbox-file-404]] — 沙盒文件分钟级回收 404 + 重生成救援
- [[chatgpt-tab-hygiene]] — tab 回收/卫生三层(启动清扫 / 异常留现场 / owns_tab)
- [[chatgpt-text-file-input]] — composer 灌长文本/文件(ProseMirror insert_text / set_input_files)
- [[chatgpt-project-sources-upload]] — Project 来源区两级上传流程 + 字节通道 + 挂载 POST 200 + --replace 白名单
- [[chatgpt-playwright-cdp-timeout]] — connect_over_cdp 超时真根因(病页毒死全初始化)→ raw CDP 重写 + 页面卡死恢复处方
- [[chatgpt-download-behavior-global-leak]] — setDownloadBehavior 全局态不复位泄漏 + --out-dir 相对路径 canceled + resume 下载故障
- [[chatgpt-dispatch-dda2210-fixes]] — commit dda2210 一批防呆(fake conv URL / followup 验证 / 降级重试 / GBK 断管 / links_found)
- [[chatgpt-dispatch-background-dying]] — CC harness 后台 dispatch 骤死 → Start-Process detached + 唤醒单后台 shell
- [[chatgpt-throttled-tab-render]] — 后台 tab 节流两事故(渲染停滞误判 / 坐标点击丢弃发送失败)+ 三旗标根治
- [[chatgpt-package-snapshot-hygiene]] — 快照包套娃指数膨胀 + 在途单未收完别清旧包
- [[chatgpt-desktop-app-driving]] — ChatGPT 桌面 App(MSIX/Electron)Playwright 驱动两坑
- [[chatgpt-mcp-manual-send]] — MCP claude-in-chrome 手动发 GPT 拿 Pro扩展 + 剪贴板污染/超长转附件/重试按钮/间歇审查坑

相关:[[no-workflow-use-chrome-gpt-review]]
