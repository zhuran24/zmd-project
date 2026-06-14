---
name: chatgpt-playwright-cdp-timeout
description: "Playwright connect_over_cdp 接管 chatgpt.com 浏览器超时的真根因——不是插件独占,是「病页毒死全浏览器初始化」(Playwright 对每个打开页面做完整初始化,任一高频 iframe 轮换的病页如 B站撞 createIsolatedWorld No frame for given id 让 promise 永久挂起 180s);修复=gpt_dispatch 全改 raw CDP over page-level ws 只跟自己 tab 说话;网络抖动/页面卡死恢复处方=同 URL 新开 page 关老的不用 reload"
metadata: 
  node_type: memory
  type: reference
  originSessionId: d4206461-b836-4607-899b-5e644bbe37f6
---

Playwright `connect_over_cdp` 接管已有 Chrome/Edge 实例时 180s 超时的协议级根因与修复,以及页面卡死的恢复处方(2026-06-12 trace 终诊):

- **Playwright `connect_over_cdp` 超时的真根因 = 「病页毒死全浏览器初始化」, 不是插件独占 (2026-06-12 协议级 trace 终诊)**: browser 级 ws 本身**健康且接受多客户端**(裸 ws `Browser.getVersion`/`Target.getTargets` 插件活跃时照样秒回)。Playwright 病在 connect 时对浏览器里**每一个**打开的页面做完整初始化(attach 全 target + 给每个 frame `Page.createIsolatedWorld`): 任何一个 iframe 高频轮换的"病页"(实测元凶 = 开着的 B 站标签, 51 个 worker + 广告/播放器 iframe 秒级生灭)都会让 createIsolatedWorld 撞 `No frame for given id found`, 初始化 promise 永久挂起 → 180s 超时。trace 证据: 269/269 请求全应答、attach 无风暴(60 个 12ms 内完成)、仅两条 frame 错误应答 + 同刻 2 个 iframe detach。**修复(已落地)= gpt_dispatch 两个脚本全部 raw CDP over page-level ws**: `urllib` PUT `/json/new` 开 tab 拿其 `webSocketDebuggerUrl` → `websockets.connect` 直连, 只跟自己的 tab 说话, 其它页什么状态都无关; **下载捕获用一条裸 browser 级 ws**(`Browser.setDownloadBehavior allowAndName` + 事件, 它没有全量初始化所以健康)。带毒环境实弹验证: 同一 Edge(B站开着+插件活跃) Playwright 卡 180s, raw 引擎 4s attach + 3 附件全收(含旧 resume-download 必败场景)。App(Electron 9224) 无 `/json/new` → fallback 用 `/json/list` 复用主窗口页。
- **网络抖动/页面卡死的恢复处方(用户经验)**:同 URL 新开一个 page、关掉老的——比 `page.reload` 可靠,渲染进程挂死时 reload 自己也会卡。活性探测用 `page.evaluate("document.readyState")` 抛异常即挂;连续 ~20s 无响应再动手,单拍抖动别折腾。

相关:[[chatgpt-browser-automation-pitfalls]]
