---
name: chatgpt-dispatch-dda2210-fixes
description: "gpt_dispatch commit dda2210 同批防呆修复——fake conversation_url(project?tab=sources 曾被记成会话 URL 毒化 resume,只认 /c/ URL);send_followup 不验证消息真发出(救援重试空等 timeout);降级重试刷到 project 主页变无上下文会话;Reporter GBK UnicodeEncodeError+Errno22 断管已吞;finish 加 links_found 区分无附件 vs 下载失败"
metadata: 
  node_type: memory
  type: reference
  originSessionId: d4206461-b836-4607-899b-5e644bbe37f6
---

gpt_dispatch commit dda2210 一批实跑踩出来的防呆修复(2026-06-12):

- **dda2210 同批其它防呆 (都是实跑踩出来的)**: ① fake conversation_url — `project?tab=sources` 曾被记成会话 URL, 毒化 revive/--resume/重试导航 (修复 = 只认 `/c/` URL, wait_done 后回捞真 URL); ② send_followup 以前不验证消息真发出去了, 救援/降级重试会对一条从未发送的消息空等全程 timeout (修复 = 验证 composer+发送钮+返回 success); ③ 降级重试以前刷到 project 主页 → retry prompt 变成全新无上下文会话 (修复 = 只刷新会话页); ④ Reporter.log 的 GBK UnicodeEncodeError 与 Errno 22 断管同 kill-chain, 已全部吞掉 (run_log 是唯一真相); ⑤ finish 日志加 links_found, exit 2 可区分"无附件"vs"下载失败"。

相关:[[chatgpt-browser-automation-pitfalls]]
