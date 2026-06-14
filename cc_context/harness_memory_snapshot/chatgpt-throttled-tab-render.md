---
name: chatgpt-throttled-tab-render
description: chatgpt.com 后台/非活动 tab 被节流的两类事故——①后台 tab 前端停止渲染 DOM(回复卡第一个字符)脚本误判 1 字符完成+0 附件;②后台 tab 坐标点击 Input.dispatchMouseEvent 被 compositor 静默丢弃=发送失败提示词留 composer;根治=start 脚本给 Edge 带三旗标(disable-background-timer-throttling 等);读取/发送/下载侧兜底=异常留现场+渲染挂起重导航+会话锚定+发送三层升级验证+下载 attempt≥2 先 /json/activate
metadata: 
  node_type: memory
  type: reference
  originSessionId: d4206461-b836-4607-899b-5e644bbe37f6
---

chatgpt.com 后台/非活动 tab 被浏览器节流引发的渲染停滞与点击丢弃两类事故及根治(2026-06-12/13):

- **并发 dispatch 单字符事故 (2026-06-12 晚, owner 破案)**: 两单并发时被节流的**后台 tab 前端停止渲染 DOM** (回复卡在第一个字符如「我」「边」), GPT 服务端实际生成完整交付; 脚本读冻结 DOM → 误判 1 字符完成 + 0 附件 + 把现场 tab 关掉。owner 手动点开 tab 前端恢复渲染才看见完整回复。**根治 = start 脚本给 Edge 带三旗标** (`--disable-background-timer-throttling/-backgrounding-occluded-windows/-renderer-backgrounding`, Edge 重启生效, 已实战验证后台 tab reply_chars 正常增长); **读取侧三兜底已落** (dispatch): ① 异常退出 (timeout/attention/no_attachments/降级/fatal) 一律 owns_tab=False 留现场不关 tab; ② done 后回复 <50 字符判定渲染挂起 → 重导航会话 URL 强制重渲染再读 (stalled_render 事件); ③ **会话锚定** = wait_done 发现当前页漂到别的会话就主动导航回自己的 conv_url, 绝不跟随 (owner 手动切换脚本 tab 曾导致 face 3 交付串线 — 脚本把别的会话的附件收进自己的 out_dir 然后正常退出)。被误判的交付用 `--resume <会话URL>` 全数可救回。
- **后台 tab 坐标点击静默丢弃 = 发送失败 (2026-06-13 owner 破案)**: `Input.dispatchMouseEvent` 合成点击在**非活动 tab** 上会被 compositor 丢掉 — 平时 dispatch 开新 tab 默认前台所以没踩; owner 同窗口期用 Edge 切走活动 tab → dispatch tab 变后台 → 发送点击无效, 提示词全程留在 composer (run_log 表象 = send 后 "URL did not switch within 60s" + 会话列表无新会话)。**修复已落 (dispatch_gpt_task.py `_click_send_verified`)**: 发送改三层升级验证 — ①坐标点击 → ②JS `button.click()` (渲染进程内派发, 不依赖前台) → ③`/json/activate` 拉前台再点; 每层验证「composer 清空 (<10 字符) 或 URL 切 /c/」才算真发出; followup 同套但 URL 验证关闭 (本来就在会话页, 会假阳性)。**处置模式 (修复前的单子)**: send NEEDS_ATTENTION "URL did not switch" → 看截图判 composer 是否还满 — 满 = 未发出 → 杀 dispatch 进程 + 关 project 页孤儿 tab + 新 out_dir 重发; 不满 = 可能已发出 → 找真会话 URL resume。**collect 下载侧同根因加固也已落 (2026-06-13, 三次踩坑后)**: `_download_via_click` attempt≥2 时先 `/json/activate` 拉前台再点 (REVIEW.md 下载在双单并发时 tab 在后台必败, 曾连害 face3 r4/bind r7/bl r6 三单靠 --resume 救); 加固后双单并发实测零 resume 全收。

- **高并发 (≥~4) collect 串台/卡死 — 三旗标治不了 (2026-06-14 P1.2 round-1/2/3 三轮 8 并发实测)**: 三旗标 + 会话锚定只把可靠收集缓解到 ~2 并发。**8 路并发同时 collect 时 Edge 只渲染 1 个前台 tab, 其余 7 个后台 DOM 冻结** → `collect()` 从渲染 DOM 读 reply (`dispatch_gpt_task.py` collect 调 `_last_assistant`, 读的是渲染后的 assistant 消息文本) 读到 0/1 字符 → exit 2 `no_attachments` / 误判零。三轮每轮 2-3 个面 collect 节流; 更狠的一例 (benders r10) **渲染在生成中途就冻结、连"生成完成"都检测不到** → 卡在 wait 心跳循环 (reply_chars=1) 直到 3.5h 超时, 须 `TaskStop` 杀进程 + `--resume` 救。**根因 = DOM-collect 本质受"单前台 tab 才渲染"限制, 不是三旗标 (旗标治 timer-throttle, 治不了非活动 tab 的渲染冻结) 能根治**。**当前办法 = 收集串行化**: 8 并发 send+generate (服务端生成无碍), 全 finish 后逐个 `--resume <conv_url>` 前台读 (串行 resume 实测全收回、真 Pro 无降级)。**真根治待做 (follow-up) = `collect()` 改从 ChatGPT 后端会话 JSON (网络/CDP) 读, 不靠 DOM 渲染 → 真并发收集免前台**。owner 已放开并发 (不自我设限/不限并发), 故修法是脚本侧并发安全 (serial-collect pass 或 network-read), 不是退回小批。配套: 用一个 Bash 后台 watcher 等全部 N 个 output 出现 `finish:` (节流/no_attachments 也有 finish 标记) 当"全收齐"信号, 但卡死的面无 finish → watcher 会空等, 须先 TaskStop 卡死进程再手动 resume。

相关:[[chatgpt-browser-automation-pitfalls]] [[no-gpt-channel-architecture]]
