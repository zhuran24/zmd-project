---
name: chatgpt-login-and-completion-detection
description: chatgpt.com 自动化的状态判定——登录态判定看 302 重定向不看输入框;完成检测双信号(停止按钮消失+文本3×10s稳定);Pro 静默降级唯一判据=真实任务<1min;model-slug 不可信;「继续生成」按钮已不存在;文字稳≠交付完成(先文字后附件)
metadata: 
  node_type: memory
  type: reference
  originSessionId: d4206461-b836-4607-899b-5e644bbe37f6
---

chatgpt.com Playwright/CDP 自动化里「这个会话现在处于什么状态」的判定经验(2026-06):

- **登录态判定不能只看输入框**:chatgpt.com 匿名也有 composer(免登录模式),但 Project URL 会 302 到 `auth/login`。判登录 = goto 目标页后查 URL 是否被重定向,不是查元素存在。
- **完成检测双信号**:停止按钮(`button[data-testid="stop-button"]` + aria fallback)消失 + 最后一条 assistant 消息(`div[data-message-author-role="assistant"]`)文本长度连续 3×10s 不变。发送/追问后要求 assistant 消息数 > 发送前基线,否则旧消息的稳定文本会被误判完成。
- **`data-message-model-slug` 不可信于降级检测**:Pro 静默降级时它照写 pro。唯一判据是行为:真实任务完整生成 <1min ≈ 被限。
- 「继续生成」按钮是 GPT-4 时代陈年知识,现版 ChatGPT 不存在;宽文本匹配 `button:has-text(...)` 有误点风险,别加。
- **dispatch「文字稳定≠交付完成」误判终态 (2026-06-12 深夜两案: pre_r9 79字符 / bl_r4 158字符)**: GPT Pro 交付是**先文字后附件**两段渲染, wait_done 判定 = 文本稳定+无生成迹象, 恰好踩在「总结文字已稳、附件未渲染」的窗口 → file_links_found=0 → no_attachments 错误收工退出。**处置 = `--resume <会话URL>` 重连必收** (附件几分钟后渲染完, resume 一次全齐)。**待修点 (未做)**: done 后 0 附件 + 回复 <500 字符 → 延迟 60-120s 重读 DOM 再终判。识别: finish no_attachments + final_reply 是一小段总结/开场白 → 先 resume 别当真无附件。

相关:[[chatgpt-browser-automation-pitfalls]] [[no-workflow-use-chrome-gpt-review]]
