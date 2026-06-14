---
name: chatgpt-attachment-capture
description: "chatgpt.com 回复附件捕获——附件三种渲染形态(a href/decorated-link 无href/behavior-btn);判据用结构 class 不靠扩展名匹配锚文本(会漏);decorated-link 点击弹外部确认框+新标签页下载,page/context 级 expect_download 收不到→必须 CDP 浏览器级 setDownloadBehavior;落盘 GUID 名+下载记录显示已删除是正常痕迹"
metadata: 
  node_type: memory
  type: reference
  originSessionId: d4206461-b836-4607-899b-5e644bbe37f6
---

chatgpt.com 回复里抓附件文件的实测形态与可靠捕获方案(2026-06):

- **回复附件至少三种渲染形态**:`<a href>` 经典链接 / `<a class="decorated-link">`(**无 href**,JS 点击)/ `<button class="behavior-btn">`(内联引用)。扫附件 `a` + `button` 都要扫,**判据优先用结构 class(behavior-btn / decorated-link),不能只靠文件扩展名匹配锚文本**——锚文本经常是中文描述(「下载 V81 审查交付 zip」),按扩展名过滤会漏(实测 3 个附件漏 2 个,恰好漏掉完整包)。空文本按钮(代码块「复制」)要排除。真实文件名从 CDP `Browser.downloadWillBegin` 的 suggestedFilename 拿,与锚文本无关。
- **decorated-link 点击会弹「外部网站」确认框**(按钮文本「打开链接」),且确认后下载发生在**新标签页**——Playwright 的 page/context 级 `expect_download` 都收不到。可靠方案 = CDP 浏览器级:`browser.new_browser_cdp_session()` + `Browser.setDownloadBehavior {behavior: allowAndName, downloadPath, eventsEnabled}` + 监听 `Browser.downloadWillBegin/downloadProgress`(落盘名是 guid,用 suggestedFilename rename)。
- CDP `allowAndName` 下载模式的正常痕迹:浏览器下载记录里显示 GUID 文件名 + 「已删除」——落盘名是 GUID,脚本下载完改成真名,记录指向旧路径就标已删除。文件没丢,在输出目录里。

相关:[[chatgpt-browser-automation-pitfalls]] [[chatgpt-download-behavior-global-leak]]
