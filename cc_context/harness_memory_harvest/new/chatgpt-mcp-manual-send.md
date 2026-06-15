---
name: chatgpt-mcp-manual-send
description: "MCP claude-in-chrome 浏览器工具手动发 GPT(区别于 dispatch 脚本通道,要 Pro扩展而 dispatch 冷导航 project URL 会降级超高时用)——流程:navigate homepage(Pro扩展默认)→点终末地 project toggle→navigate project URL 继承 Pro扩展(直接冷导航会变超高,必须先 homepage)→验 model 含 Pro 扩展→粘贴发送验 composer 清空+generating;三坑:剪贴板污染(owner 复制覆盖 prompt 须回读确认)/超长 prompt>~9189中文字符自动转附件/错误页「重试」按钮把 prompt 塞 URL 跳 homepage 别点;OpenAI 间歇审查拦截自动化发送;dispatch --resume 可盯 MCP 发的会话"
metadata: 
  node_type: memory
  type: reference
  originSessionId: d4206461-b836-4607-899b-5e644bbe37f6
---

用 MCP(claude-in-chrome)浏览器工具手动给 GPT 发任务(2026-06-14, 区别于 dispatch 脚本通道):

- **MCP (claude-in-chrome) 浏览器工具手动发 GPT (2026-06-14, 区别于 dispatch 脚本通道)**: 当需要 Pro扩展、而 dispatch 冷导航 project URL 会降级「超高」时, 用 MCP 走 owner 打开方式拿 Pro扩展。流程: `navigate` chatgpt.com homepage(owner 日常默认 Pro扩展) → JS `TreeWalker(SHOW_TEXT)` 找含「终末地」的文本节点、向上找 role=button 可点击祖先(坐标随窗口变, 实测 122,302) `computer left_click` toggle 出 project → `navigate` project URL(**从 homepage session 继承 Pro扩展; 直接冷导航 project URL 会变「超高」**, owner 理论是 URL 某字符触发, 必须先 homepage) → JS 验证 composer 上方 model 文本含「Pro 扩展」 → `computer left_click` `#prompt-textarea`(宽屏 ~904,234) + `key ctrl+v` → JS 找 `button[data-testid="send-button"]` 坐标(~1336,452) `left_click` → JS 验证 composer 清空(textContent 0)+generating+无「Something went wrong」+ 记 `/c/<id>` 会话 URL。**三个坑**: ① **剪贴板污染** — owner 在对话里复制东西会覆盖 clip_send 设的 prompt(实测粘出上一条回复文本「回 homepage…」); `clip_send.ps1 -TextFile` 后必 `Get-Clipboard -Raw` 回读确认 head+len, 发前提醒 owner 别复制。② **超长 prompt 自动转附件** — >~9189 字符(中文)时 ChatGPT 把粘贴文本转成附件文件, `#prompt-textarea` textContent=0 是**假象**(粘贴其实成功、内容在附件); 判 isAttach=找含文件名+「文本字段中显示」的卡片 div, 删附件按钮 `aria=「移除文件N」`(aria 里带序号可判附件个数); 想要纯文本就把 prompt 拆短到阈值下(face 7/8 拆开各 ~7800 字符就纯文本不变附件)。③ **错误页「重试」按钮异常** — GPT 回「Something went wrong」后点「重试」会把整个 prompt 塞进 `chatgpt.com/?prompt=<URL编码>` 跳 homepage(且该 URL 很顽固、navigate homepage 都换不掉), **别点重试**, navigate 回 project 重新粘贴发。**OpenAI 间歇审查故障(重要新坑)**: 插件/自动化发送会间歇触发服务端「Something went wrong while generating」(face 3 插件连两次失败、owner 手动发同 prompt 正常 = 针对自动化的间歇拦截, 非网络非 prompt); 但**间歇** — owner 手动夹发一次之后插件就放行(同批 face 6/7/8 插件全成功)。owner 录「手动成功→插件失败→手动成功」夹汉堡视频给客服取证(但间歇性导致夹不稳、插件也可能成功反而削弱取证)。**dispatch resume 也能盯 MCP 发的会话**: `dispatch_gpt_task.py --resume <会话URL> --out-dir <dir>` 不管谁发的, raw-page-cdp attach 会话盯 done+自动收附件落盘; 3 个 detached 并发(各 owns_tab)实测没节流死, 配后台 bash 盯各自 run_log 的 finish stage(单次完成唤醒, 任一 finish 就读那个验收再重起盯剩下)。**owner 建议(待落地)**: 以后省掉 homepage→sidebar、直接 navigate project + 加「检查模型不是 Pro扩展就手动切」环节, dispatch 脚本同理。

相关:[[chatgpt-browser-automation-pitfalls]] [[no-workflow-use-chrome-gpt-review]]
