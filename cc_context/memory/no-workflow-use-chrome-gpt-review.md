---
name: no-workflow-use-chrome-gpt-review
description: "用户裁决(2026-06-10,当晚精简版):非必要不用 Workflow;审查/实现任务经 Chrome 插件外发 GPT Pro;三条发送设置 + 打包除缓存全打;老审查规范已废除"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 20690dc4-0860-4f42-a5a5-e1cccbd7b8d7
---

用户裁决:**非必要不用 Workflow 多代理编排**(即使 Ultracode 开着)。审查、外审、委托实现类任务用 Claude in Chrome 插件发到 chatgpt.com 让 GPT Pro 做。zmd 项目 v22-v79 全是 GPT 外审的,GPT Pro 沙盒(Python 3.13)能解包、装离线 wheels、跑 pytest 自验,实现任务也能整包委托。

**发送设置三条(用户指定):**
1. 模型选 **Pro·进阶**(= GPT Pro 扩展模式;中文 UI「进阶专业」就是它,不用另找开关)
2. 发在 ChatGPT 的**「终末地」Project** 里面
3. **非必要不用老窗口**——新任务默认开新会话,只有同一任务的连续追问才留原会话

**打包规则(唯一存留):除缓存文件外全项目打**(排除 .git/__pycache__/.pytest_*/.ruff_cache/.venv/.upstream_clones/*.pyc/输出 zip/prompt 文件)。build 脚本在 `cc_context/review/build_v80_single_win.py`(单包,自包含,gpt_dispatch --pack 调用它;分卷版已归档 review/archive/)。**老的审查打包规范(no-priming/7-section prompt 模板/armor/7z 策略等)2026-06-10 全部废除**,备份在项目 `cc_context/memory_archive/` 与 `cc_context/review/archive/`。给 GPT 的 prompt 直接讲任务+约束+交付物即可。

**发送分工(2026-06-11 用户裁决):单发任务默认 CC 用 dispatch 脚本自动发;只有多路并行外发(脚本不支持同浏览器并发,start/cleanup 会互关 tab)或 CC 自己的额度快用尽时,才改由用户手动发**(跟 GPT 那边的额度无关)。CC 手上有现成包+prompt 时别把单发推回给用户。**并发上限(2026-06-11 风控教训):同时在途/正在生成的 GPT 请求最多 2 个**——同窗口期曾 4 路并发,随后脚本通道连续静默降级、App 通道卡顿,疑似触发风控。**脚本被风控/连续降级且 owner 不在场的托底:派 sonnet 档子代理驱动 Claude-in-Chrome 插件(Edge,已登录)按"插件手动上传姿势"发送**(主会话亲自下场=大材小用+额度贵);子代理拿到会话 URL 后,主会话用 dispatch 脚本 `--resume <URL>` 接管等待+收件(零 token;注意 resume 模式跳过降级检测,收件后自查生成耗时)。

**首选通道(2026-06-11 起):外发自动化脚本,全程零 token。** `python cc_context\review\gpt_dispatch\dispatch_gpt_task.py --pack --prompt-file <md>`。前置 = `start_gpt_automation_chrome.ps1`:**默认 attach 用户日常 Edge 主实例**(用户裁决,不搞独立 profile,直接用已登录态零配置)。**⚠️ 重要 caveat:Edge 在跑但没带调试端口时,start 脚本会温和重启用户的 Edge**——跑之前先想想用户是不是正用着浏览器,必要时知会;Edge 每次正常重启后端口就丢了,下次 dispatch 前要再跑一次 start。打包→上传→发送→等完成→收交付全自动;挂了 `--resume <会话URL>` 续;完整流程已验收(含 40MB 包、附件 404 自动救援)。退出码/细节见项目 CLAUDE.md runbook 段。**Pro 静默降级(用户经验)**:无任何明面标注(DOM model-slug 照写 pro,不可信),唯一判据 = 生成耗时(真实审查/实现任务要 30min+,**5min 内完成 = 极大概率降级**;2026-06-11 实测 70s 降级回复溜过旧 60s 判据成 exit 2 + 只回"我计划怎么审"提纲零沙盒动作——脚本默认已改 300s);处置 = 脚本自动刷新重跑一次,仍快(exit 5)→ 我改走插件通道手动托底(同一个 Edge 上的 Claude in Chrome 插件)。

**插件手动上传姿势(托底通道用):** 插件 `file_upload` 工具 10MB 上限且新版拒收主机路径——别用它。走 Windows 剪贴板:PS7 跑 `Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::SetFileDropList($col)`(`Set-Clipboard -Path` 是 5.1 专属),聚焦 ChatGPT 输入框发 Ctrl+V(14.2MB 实测成功,网页上限 512MB)。长 prompt 同理 `Set-Clipboard -Value` + Ctrl+V。LZMA zip 让对方用 `python -m zipfile -e` 解(Linux unzip 不支持)。**sandbox 附件几分钟就回收(404)**:完成后立即收,收不到就追问一句让 GPT 重新生成(沙盒重建文件)。

**Why:** 本地审查 workflow 实测 38 分钟 + API stream 超时挂 critic + 审查 agent 并发跑 pytest 互删 `.pytest_tmp` 污染全量测试;GPT Pro 外发更稳更省额度。老审查规范是几十轮外审循环时代的产物,用户裁决"现在不用这么麻烦了"。

**How to apply:** 默认自己干或单个 Agent 子代理;"必要" = 用户明确点名要 workflow,或任务确实离不开本地多路编排且无法外发。委托实现的交付物拿回来后:本地 apply → check 脚本 + 目标测试 → 独占全量复验 → **`python scripts/preflight_gate.py --ci --base-ref HEAD~1` 全 gate(必跑!pytest 盖不到 frozen hash/行尾/记忆树三类检查,漏跑 = push 即 CI 红 + 邮件轰炸,V80 实测教训)** → 推锚易漏点复核 → commit,不盲信关键论证。外发 prompt 的锚定清单要含:若改 frozen artifact,`preflight_gate.py::FROZEN_ARTIFACTS` sha256 同批推进;要求 GPT 产物 LF 行尾。

相关:[[zmd-project-entry]]
