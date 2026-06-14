---
name: chatgpt-tab-hygiene
description: "chatgpt.com 自动化 tab 回收卫生——每轮 new_page+点击开的新 tab 不清理会堆满;启动清扫残留 chatgpt tab(保证浏览器始终≥1 tab,关最后一个会带退浏览器断 CDP);结束自关;异常留现场 tab 三层回收(resume 按 /c/ 精确收同会话+--cleanup-tabs 运维全关+owns_tab 成功即关)"
metadata: 
  node_type: memory
  type: reference
  originSessionId: d4206461-b836-4607-899b-5e644bbe37f6
---

chatgpt.com 自动化里 tab 的回收与卫生(2026-06):

- **tab 必须回收**:每轮 `ctx.new_page()` + 点击开出的新 tab 不清理会堆满浏览器。启动时清扫残留 chatgpt tab(先开好自己的 page 再扫,保证浏览器始终 ≥1 tab,关最后一个 tab 会把浏览器带退、CDP 断)+ 结束时自关(最后一个则 goto about:blank 保活)。
- **tab 卫生机制 (2026-06-12 深夜, owner 提出)**: 异常留现场的 tab 没人回收会堆孤儿 (一晚 5 个)。已焊三层: ① resume 启动时 `close_same_conversation_tabs` 按 `/c/<conv-id>` 精确回收同会话旧 tab (现场截图/DOM 已落盘, 零损失, 不碰其它页面); ② `--cleanup-tabs` 运维模式关本 Project 全部 tab (⚠️ 在途任务的 tab 也会被关, 确认无在途才跑); ③ 既有 owns_tab 成功即关。

相关:[[chatgpt-browser-automation-pitfalls]]
