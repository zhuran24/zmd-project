---
name: chatgpt-desktop-app-driving
description: "ChatGPT 桌面 App(Windows Store/MSIX 版,Electron)也能 Playwright 驱动——接受 --remote-debugging-port,DOM 与网页同构;两坑:①必须 Invoke-CommandInDesktopPackage 以 MSIX 包身份启动(裸跑 WindowsApps exe 因拿不到包上下文主进程崩溃弹 Error 框);②Electron 不支持 ctx.new_page(),复用 ctx.pages[0] 主窗口页结束不能关它;包身份/路径用 Get-AppxPackage 动态查"
metadata: 
  node_type: memory
  type: reference
  originSessionId: d4206461-b836-4607-899b-5e644bbe37f6
---

- **ChatGPT 桌面 App(Windows Store 版)也能 Playwright 驱动**:Electron 壳,接受 `--remote-debugging-port`,内部就是 chatgpt.com 前端(DOM 同构)。两个坑:① **必须 `Invoke-CommandInDesktopPackage` 以 MSIX 包身份启动**——裸跑 WindowsApps 里的 exe 会因 `Windows.Storage.ApplicationData.get_Current` 拿不到包上下文而主进程崩溃弹 Error 框;② Electron 不支持 `ctx.new_page()`,复用 `ctx.pages[0]` 主窗口页面,结束时不能关它。包身份/路径用 `Get-AppxPackage` 动态查,版本号会随更新变。

相关:[[chatgpt-browser-automation-pitfalls]]
