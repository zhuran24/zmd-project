---
id: codex-executes-claude-orchestrates
kind: decision
title: 大工作量交 Codex 执行，Claude 编排把关
summary: 默认分工按工作量大小，不按“实现/审查”标签；大活交 Codex，Claude 做编排、审查和最终验收。
scope:
  domains:
    - agent-orchestration
    - delegation
  paths:
    - AGENTS.md
  symbols:
    - codex_executes_claude_orchestrates
    - spawn_agent
status: active
priority: P1
triggers:
  intents:
    - delegation
    - multi-agent
  keywords:
    - Codex
    - Claude
    - 子代理
    - 分工
    - 工作量
    - 审查
    - 实现
    - 跨模型
  negative_keywords: []
  paths:
    - AGENTS.md
  symbols:
    - spawn_agent
    - codex-cli-child-sessions
  error_regex: []
  examples:
    - 三轮外审属实性验证这种大工作量应该交给谁
    - 这个实现任务由 Codex 做还是 Claude 做
activation:
  layer_hint: L1
  must_know: false
  reason: 分工判断错误会烧错模型额度并削弱跨模型审查。
provenance:
  op: record
  reason: 从旧 cc_memory 节点 codex-executes-claude-orchestrates 提炼；owner 2026-06-26 纠正底层判据是工作量大小。
  evidence:
    - python cc_memory/mem.py read codex-executes-claude-orchestrates --body
updated_at: "2026-06-26"
---
默认分工不是按任务标签死分，而是先看工作量。大工作量的实现、推进、找问题、验证交 Codex 作为执行体；Claude 负责周边编排、审阅、对抗和最终验收。小工作量的审查或对抗可以留给 Claude。

跨模型审是方向性不变量：谁做了主要工作，就由另一个模型审；默认是 Codex 实现、Claude 审。
