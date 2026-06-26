---
id: codex-team-sonnet-mediator
kind: reference
title: Codex 进 Agents Team 用 Sonnet 中介转 SendMessage
summary: "Codex 子代理原生没有 SendMessage，不能直接当互发消息的 team 成员；需要用 sonnet/claude 中介 agent 作身体，内部调用 mcp__codex__codex 取 Codex 推理，再用 SendMessage 发进 Agents Team。"
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
updated_at: "2026-06-26"
---
Codex 子代理原生只挂 Codex MCP 转发工具，本身没有 `SendMessage` 和团队消息工具，所以它不能直接作为能互发消息的 Agents Team 成员。正确接法不是放弃 Codex，也不是只能由主席手动桥接，而是 spawn 一个 sonnet/claude 中介 agent 进 team：这个中介有 `SendMessage`，在内部调用 `mcp__codex__codex` 取得 Codex 的推理，再把 Codex 的观点发到 team 里。

使用时把 sonnet 中介明确写成某个 Codex panelist 的身体或嘴：推理来源是 Codex，团队发言和收发消息由中介负责。owner 说"开会/开个会"时，如果需要 Codex 席位，应按这个模式纳入 Agents Team，不要再推断"Codex 用不了 SendMessage 所以进不了 team"。

给 Codex 派活时默认不要给 Codex agentType 直接挂 `StructuredOutput` schema，尤其是在 team 讨论这种只需要自然语言观点的场景。旧问题是 Codex shim 纯管道契约和强制结构化输出冲突，可能提交空 `{}` 并被 schema 校验反复打回；即使某台机器补过 codex.md 结构化分支，也不要让这个补丁成为 team 中介模式的依赖。
