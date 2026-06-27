---
id: codex-team-sonnet-mediator
kind: reference
title: Codex 进 Agents Team 用 Sonnet 中介转 SendMessage
summary: "codex agentType 本身=model:sonnet 瘦转发器(sonnet 当手/codex 当脑,调 mcp__codex__codex)。codex.md 有模式A单发+模式B团队(同一 sonnet 在 team 用 SendMessage 转发 codex 进会)。团队里那个'sonnet 中介'很可能就是 codex agentType 模式B本身;是否要另手包一个带 SendMessage 的 sonnet=待实测。别再误判'codex 没有 sonnet/没有模型'。"
scope:
  domains: [agents-team, codex-integration]
  paths: []
  symbols: [SendMessage]
status: active
priority: P1
triggers:
  intents: [agents-team, codex-panelist, multi-agent-discussion, team-messaging]
  keywords: [codex, Agents Team, team, 开会, SendMessage, sonnet 中介, mcp__codex__codex, codex 席位]
  negative_keywords: []
  paths: []
  symbols: [SendMessage, TeamCreate, mcp__codex__codex, StructuredOutput]
  error_regex: ["Output does not match required schema", "error_max_structured_output_retries"]
  examples:
    - 开个会时想让 codex 成员加入 Agents Team 互相讨论
    - 需要 4 claude 加 4 codex 的 team，并且成员要能 SendMessage
    - 给 codex 派 team panelist 任务时准备顺手加 schema
activation:
  layer_hint: L1
  must_know: true
  reason: 误判 Codex 不能进 team 会丢掉跨模型讨论能力，误给 schema 又可能触发空结构化输出问题。
provenance:
  op: record
  reason: owner 纠正 Codex 可通过 sonnet 中介加入 Agents Team，并要求沉淀 route-time 记忆。
  evidence:
    - "python cc_memory/mem.py read codex-agents-team-sendmessage-sonnet --body"
    - "python cc_memory/mem.py read codex-agenttype-schema-structuredoutput-empty-loop --body"
    - "C:/Users/22957/.claude/projects/C--claude-pj-zmd-pj/memory/meeting-equals-team.md"
    - "~/.claude/agents/codex.md (model: sonnet;模式A单发/模式B团队)"
updated_at: "2026-06-27"
---
**先厘清(2026-06-27 校准):codex 这个 agentType 本身就是 `model: sonnet` 的瘦转发器**(见 `~/.claude/agents/codex.md`:frontmatter `model: sonnet`,职责=把任务原文塞进 `mcp__codex__codex`、把 codex(gpt-5.x)输出一字不改带回)。所以"派 codex"= **一个 sonnet 身体在调 codex MCP**:codex 是脑、sonnet 是手——**不存在"没有模型"**(工具不会自己调自己)。早先把"瘦转发层"误读成"没有 sonnet"是错的。

`codex.md` 自带两种模式:**模式 A 单发**(`subagent_type:'codex'` / Workflow `agentType:'codex'`,无 team,一次 codex 调用、文字原样返回);**模式 B 团队**(同一 sonnet 在 team 里用 `SendMessage` 把 codex 结果转发进会)。**所以团队里那个"sonnet 中介",很可能就是 codex agentType 本身在模式 B,未必要另起一个手搭 agent。**

⚠️ **待实测**(本卡早先断言"必须另包中介",但 codex.md 模式 B 暗示未必,没测前两说并存):把 `agentType:'codex'` 直接 spawn 进 team——team 上下文是否自动把 `SendMessage`/`TaskUpdate` 注入给它(frontmatter 只列了两个 codex 工具)、从而它直接就能当讨论席;还是仍需手包一个带 `SendMessage` 的 sonnet 当壳。要用 codex 席位前先拿一个最小 team 实测确认。

使用时把 sonnet 中介明确写成某个 Codex panelist 的身体或嘴：推理来源是 Codex，团队发言和收发消息由中介负责。owner 说"开会/开个会"时，如果需要 Codex 席位，应按这个模式纳入 Agents Team，不要再推断"Codex 用不了 SendMessage 所以进不了 team"。

给 Codex 派活时默认不要给 Codex agentType 直接挂 `StructuredOutput` schema，尤其是在 team 讨论这种只需要自然语言观点的场景。旧问题是 Codex shim 纯管道契约和强制结构化输出冲突，可能提交空 `{}` 并被 schema 校验反复打回；即使某台机器补过 codex.md 结构化分支，也不要让这个补丁成为 team 中介模式的依赖。
