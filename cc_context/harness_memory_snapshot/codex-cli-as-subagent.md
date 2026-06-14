---
name: codex-cli-as-subagent
description: 本机有可非交互调用的 OpenAI Codex CLI，能当子代理/workflow worker；二进制路径、调用姿势、关键坑、wrapper、集成路
metadata: 
  node_type: memory
  type: reference
  originSessionId: 82697e77-563f-49f4-b6d0-521d19d4aa8c
---

本机这台 Windows 上的「codex」= OpenAI **官方 Codex 桌面应用捆绑的 CLI**（不是 `@openai/codex` npm 包，也不是 npm 全局那个无关的 `opencode-ai`）。可在终端非交互驱动，拿来当 Claude Code 的外部子代理 / workflow worker。2026-06-14 端到端验证跑通。

**二进制**（未进 PATH）：`%LOCALAPPDATA%\OpenAI\Codex\bin\<hash>\codex.exe`，版本 v0.140.0-alpha.2。`bin` 下有多个版本子目录，**取 LastWriteTime 最新的那个**（当前是 `f1c7ee7a13db5fed\codex.exe`，旧的顶层 `bin\codex.exe` 别用）。

**认证**：复用 `~/.codex/auth.json`，`auth_mode=chatgpt`（ChatGPT 订阅 OAuth，`OPENAI_API_KEY=null`）→ 调 CLI **走订阅额度、不烧 API key**，零配置。`codex doctor` 可验证 auth + websocket（连 `wss://chatgpt.com/backend-api/`）健康。

**非交互调用** = `codex exec`。核心坑与要点：
- **prompt 必须走 stdin**（管道喂）：非 TTY 环境下 `codex exec` 认定 stdin 是管道、会一直等读到 EOF，若 prompt 只放位置参数而 stdin 不给 EOF 就**永久挂死**。正解 `$prompt | codex exec [opts]`。
- `reasoning effort=minimal` 与 config 默认开的 `image_gen`/`web_search` 工具冲突（400 错误）→ 用 `low`/`medium`/`high`/`xhigh`。
- 关键参数：`-C <dir>` 工作目录、`-s read-only|workspace-write|danger-full-access` 沙箱、`-c approval_policy="never"` 不卡审批（exec 没有 `-a` 顶层那个 flag）、`--skip-git-repo-check`、`-m <model>`、`--ephemeral`。
- 取结果三方式：`-o <file>`（写 agent 最后一条消息，最干净）、`--json`（JSONL 事件流：`thread.started`/`turn.started`/`item.completed{agent_message.text}`/`turn.completed{usage}`）、`--output-schema <file>`（JSON Schema 强制结构化输出，直接 `JSON.parse`）。

**封装好的 wrapper**：`C:\Users\22957\codex_run.ps1`（PowerShell 7）。自动定位最新二进制、prompt 走 stdin、默认 `read-only` 沙箱 + `low` effort、默认只把 agent 最后一条消息打到 stdout（吞掉 banner 噪音）。用法 `.\codex_run.ps1 "<prompt>" -Cwd <dir> [-SchemaFile s.json] [-Sandbox workspace-write] [-Json] [-Model ...]`。

**现成方案优先于自写 wrapper（2026-06-14 查证）—— 别再从头手搓**：
- **OpenAI 官方插件 `openai/codex-plugin-cc`**（2026-03-30 出，最对口「codex 当 Claude 子代理」）：Claude Code 里 `/plugin marketplace add openai/codex-plugin-cc` → `/plugin install codex@openai-codex` → `/reload-plugins` → `/codex:setup`。给 `/codex:rescue`（委托干活）、`/codex:review`+`/codex:adversarial-review`（审查/对抗审查）、`/codex:status|result|cancel`、以及 `codex:codex-rescue` 子代理（`/agents` 可见）。底层走 codex **app-server** JSON-RPC 协议（非 exec）。**本机已铺好（2026-06-14）**：查证插件**硬依赖 PATH 里的 `codex`**（`app-server.mjs` 直接 `spawn("codex",["app-server"])`、`process.mjs` binaryAvailable 靠 PATH，**无任何路径配置项**能指到桌面版 hash 目录里的 codex.exe）→ 故已 `npm install -g @openai/codex`（0.139.0 stable，装进 `E:\tools\node\npm-global`，已在 PATH，复用 `~/.codex` 的 chatgpt 登录、不用重登；选 stable 而非 alpha 桌面版因 app-server 协议要跟插件同步）。插件 `codex-companion.mjs setup --json` 判定 `ready:true` + advanced runtime available + auth verified。**只剩 owner 在 CC 里敲 4 条命令**（`/plugin marketplace add openai/codex-plugin-cc` → `/plugin install codex@openai-codex` → `/reload-plugins` → `/codex:setup`，这是用户 UI 命令、AI 替不了）即装好。
- **社区编排框架**（claude+codex 当 team）：`HERMESquant/oh-my-hermes`（专做双向 handoff + DualForge 同时拆活）、`dsifry/metaswarm`（claude+gemini+codex 18 agent 全生命周期）、`jayminwest/overstory`（11 runtime adapter）、`ruvnet/ruflo`（100+ agent swarm）。
- **owner 自有积累**：`E:\tools\codex-tools-c-root\codex-tools\` 下 `multi_agent_final_review_20260422\multi-agent-orchestrator\SKILL.md`（成熟编排方法论，带决策表/资源分级/五要素委派）+ `codex-child-session-smoke`（验证过 codex 子会话，产物 = events.jsonl + last.txt）；`C--claude-pj-llm` CC 项目有 `digest-codex-rollout` workflow + `codex-docs-pointers` memory。

**自写兜底（不引入框架时）两条路**：
- **路 A（已验证可用）**：Claude 子代理 / Workflow 里通过 Bash/PowerShell 调 `codex_run.ps1`，把活外包给 codex，读回 stdout（纯文本或结构化 JSON）。混合编排：Claude 拆解+验证、codex 实现某段。
- **路 B（更原生，已落地 2026-06-14）**：`codex mcp-server`（stdio）暴露 2 个工具 `codex`(参数 prompt/cwd/sandbox/model/approval-policy/config) + `codex-reply`(threadId/prompt 续跑)。已 `claude mcp add codex --scope user -- cmd /c codex mcp-server` 注册进全局 `~/.claude.json`，`claude mcp list` ✔ Connected，tools/call 验证返回结构化 `{content,structuredContent:{threadId,content}}`。**重启 CC 后**主会话直接 `mcp__codex__codex({prompt,cwd,sandbox,'approval-policy':'never',config:{model_reasoning_effort}})` = 零中介调 codex。还有 `codex review --uncommitted|--base <br>|--commit <sha>` 本地非交互审查（[[no-gpt-pro-outsource-core]] 同类）。

## codex 当 workflow / agents-team 子代理 —— 核实结论 + 落地（2026-06-14）

claude-code-guide 逐字核官方文档：**CC 框架内 workflow / agents team 里「零 Claude 中介的 codex 并发单元」做不到**。三条硬依据：① PreToolUse hook 只能 allow/deny/ask + 改入参(`updatedInput`)，**不能短路工具调用并注入合成 tool_result**（deny 的 reason 被模型读成「调用失败原因」、非「成功结果」）；PostToolUse `updatedToolOutput` 能改结果但工具必须已真跑过（Claude 子代理已 spawn 已烧 token）。② workflow/team 引擎的最小并发单元**就是一个 Claude**（workflow `agent()` 永远 spawn Claude、team teammate 是 Claude 实例），无「跑外部进程」并发原语。③ subagent frontmatter 无 `command/runtime/executor/backend` 字段，执行后端永远 Claude。**结论：「零中介」与「在 CC workflow/team 里编排」不可兼得**——别再走「hook 短路 + 喂假结果」这条死路。

owner 裁决「2+3 都要」，已落地：
- **方案2（主会话零中介）**：codex MCP server（见路 B），重启后主会话直调 `mcp__codex__codex`。CC 内唯一彻底零中介形态，但 codex 是工具非并发子代理。
- **方案3（CC 编排最薄壳）**：`~/.claude/agents/codex.md`（`name: codex`、`model: haiku`、`tools: mcp__codex__codex, mcp__codex__codex-reply`）瘦转发 agent，重启后 workflow `agent(p,{agentType:'codex'})` / Agent `subagent_type:'codex'` / team codex teammate 调。壳退化成「单次 MCP tool call + 原样回传」。**已实测通过**（重启后 2026-06-14）：workflow `agent(p,{agentType:'codex'})` 跑通，haiku 薄壳 `tool_uses=1`（单次 `mcp__codex__codex`）即拿到结果 → **subagent MCP 可见性 OK，不用切 Bash**；薄壳版 26149 tok/30s，比早期 Bash 中介版 37874 tok/64s 更省。方案2 主会话直调 `mcp__codex__codex` 也实测返回结果+threadId、零子 Claude。（若未来某上下文 subagent 看不到 MCP 工具，薄壳 `tools` 可切回 `Bash` 走 `codex_run.ps1` 兜底。）
- **真·zero-Claude 多 codex 编排**（owner 没选但记着）：须把编排主控搬到 codex 侧（codex 原生 subagent `thread_spawn` / `[agents]max_depth=3` / `.codex_child_sessions` + owner 自有 multi-agent-orchestrator skill）或外部框架（oh-my-hermes/metaswarm）。

注意：codex-desktop 应用本体也叫 `codex.exe`（重度定制，`~/.codex` 下有 ultracode/skills/workflow/pets 等）；杀 exec 残留进程时按 commandline 含 `exec` 精确匹配，**绝不误杀桌面应用本体**（同 CLAUDE.md「自我保护」段 + [[cc-watchdog-misc-pitfalls]] 的按 PID/特征单杀、绝不按名误杀原则）。
