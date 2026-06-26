---
id: meeting-equals-team
kind: decision
title: "开会就是起 Agents Team"
summary: "owner 说开会或开个会时，默认路由到能互发消息、互相挑战并收敛的 Agents Team；不要路由成 Workflow 或单个 subagent。"
scope:
  domains: [agents-team, meeting-routing]
  paths: []
  symbols: []
status: active
priority: P1
triggers:
  intents: [meeting-review, multi-agent-discussion, design-review, routing-decision]
  keywords: [开会, 开个会, 评审一下, team, Agents Team, 多代理讨论, 互发消息, SendMessage]
  negative_keywords: []
  paths: []
  symbols: [TeamCreate, SendMessage]
  error_regex: []
  examples:
    - 给 supervisor 重构设计开个会评审一下
    - 找几个 agent 开会讨论这个方案
    - 我说开会是 team，不是 workflow
activation:
  layer_hint: L1
  must_know: false
  reason: 把开会误路由成 Workflow 会破坏 owner 想要的多代理互相讨论语义。
provenance:
  op: record
  reason: owner 纠正过开会语义；从既有 cc_memory 条目提炼为 v-next 路由卡。
  evidence: ["python cc_memory/mem.py read terminology-meeting-equals-team --body"]
updated_at: "2026-06-26"
---
owner 说"开会"或"开个会"时，含义是起一个 Agents Team：多个 agent 在同一个 team 里能互相发消息、讨论、挑战观点并收敛结论。它不是 Workflow，也不是把几个独立 worker 并行跑完后交报告，更不是单个 subagent 自己分析。

路由时直接按 team 语义执行：创建 team，把 panelist/评审者放进同一个 team，并明确要求他们互相讨论和质疑后再形成结论。只有 owner 明说要 workflow、批量并行跑、各自独立产报告，才走 Workflow。
