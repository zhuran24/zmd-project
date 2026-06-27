---
id: codex-team-sonnet-mediator
kind: reference
title: Codex 直接进 Agents Team(agentType:'codex' 本身=sonnet 身体、自带 SendMessage,不用手包中介)
summary: "codex agentType 本身=model:sonnet 瘦转发器(sonnet 当手/codex 当脑,调 mcp__codex__codex)。2026-06-27 最小 team 实测确认:直接把 agentType:'codex' 带 team_name spawn 进 team,它在 team 上下文里自带 SendMessage、能直接当讨论席转发 codex 进会——【不需要、也不该再另手包 sonnet 中介】。别再误判'codex 没有模型',也别再多此一举手搭中介。"
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
  reason: 2026-06-27 用最小 team 探针实测确认 agentType:'codex' 直接进 team 自带 SendMessage、不需手包中介;订正早先"必须另包 sonnet 中介"的旧结论。
  evidence:
    - "2026-06-27 最小 team 探针 codex-team-probe:codex-probe(agentType codex/model sonnet)直接 SendMessage 给 lead 成功"
    - "~/.claude/agents/codex.md (model: sonnet;模式A单发/模式B团队 SendMessage)"
    - "python cc_memory/mem.py read codex-agenttype-schema-structuredoutput-empty-loop --body"
    - "C:/Users/22957/.claude/projects/C--claude-pj-zmd-pj/memory/meeting-equals-team.md"
updated_at: "2026-06-27"
---
**先厘清(2026-06-27 校准):codex 这个 agentType 本身就是 `model: sonnet` 的瘦转发器**(见 `~/.claude/agents/codex.md`:frontmatter `model: sonnet`,职责=把任务原文塞进 `mcp__codex__codex`、把 codex(gpt-5.x)输出一字不改带回)。所以"派 codex"= **一个 sonnet 身体在调 codex MCP**:codex 是脑、sonnet 是手——**不存在"没有模型"**(工具不会自己调自己)。早先把"瘦转发层"误读成"没有 sonnet"是错的。

`codex.md` 自带两种模式:**模式 A 单发**(`subagent_type:'codex'` / Workflow `agentType:'codex'`,无 team,一次 codex 调用、文字原样返回);**模式 B 团队**(同一 sonnet 在 team 里用 `SendMessage` 把 codex 结果转发进会)。**所以团队里那个"sonnet 中介",很可能就是 codex agentType 本身在模式 B,未必要另起一个手搭 agent。**

✅ **实测确认(2026-06-27,最小 team 探针 `codex-team-probe`)**:把 `agentType:'codex'`(带 `team_name` + `name`)直接 spawn 进 team,它**在 team 上下文里就有 `SendMessage`**(frontmatter 虽只列两个 codex 工具,team 上下文会注入团队消息工具),成功给 lead 发了消息、把 codex 的推理(2^10=1024)转发进会。member config 实测 `agentType: codex / model: sonnet`。

**所以正解 = 直接 `Agent(subagent_type:'codex', team_name, name, prompt)`**(Workflow 里同理给 `agentType:'codex'`)——它自己会用 SendMessage 把 codex 观点发进会(codex 是脑、它的 sonnet 身体是嘴)。**不需要、也不该再另手搭一个独立 sonnet 中介壳**(那是绕远路,我早些会话手包过=多余)。owner 说"开会/开个会"需要 Codex 席位时按此纳入,别再推断"Codex 用不了 SendMessage 所以进不了 team"。

给 Codex 派活时默认不要给 Codex agentType 直接挂 `StructuredOutput` schema，尤其是在 team 讨论这种只需要自然语言观点的场景。旧问题是 Codex shim 纯管道契约和强制结构化输出冲突，可能提交空 `{}` 并被 schema 校验反复打回；即使某台机器补过 codex.md 结构化分支，也不要让这个补丁成为 team 中介模式的依赖。
