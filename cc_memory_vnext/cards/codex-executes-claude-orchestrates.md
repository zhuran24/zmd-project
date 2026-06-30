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
  layer_hint: L0
  must_know: true
  session_start_l0: true
  reason: 分工判断错误会烧错模型额度并削弱跨模型审查;owner 2026-06-30 要求无条件每会话注入,避免又把大活自己做掉烧 opus 额度。
provenance:
  op: record
  reason: 从旧 cc_memory 节点 codex-executes-claude-orchestrates 提炼；owner 2026-06-26 纠正底层判据是工作量大小；owner 2026-06-30 要求把本卡提到 L0 无条件每会话注入(我又把 round-10 大块机械实现自己做掉、烧 opus 额度后)。
  evidence:
    - python cc_memory/mem.py read codex-executes-claude-orchestrates --body
    - "owner 2026-06-30: 就把这张卡放在会话开始吧，就无条件默认注入"
updated_at: "2026-06-30"
---
默认分工判据【先看工作量】，不按“实现/审查”标签死分：工作量大的活（实现、推进、找问题、验证）交 Codex 作为执行体（省 Claude/opus 额度）；工作量小的活 Claude 自己直接做即可——**小实现也算，别因为它性质叫“实现”就硬派 Codex**。反过来，**大工作量的 read/调查/核查也是大活、同样该走 Codex**——别因为“跨多文件读”这个【工具模式】就反射派 Explore/opus 子代理（2026-06-28 实犯：核 PR2 9 项状态派了 3 个 Explore 子代理读一堆文件、~267K tokens，没套“工作量→Codex”路由＝按工具模式/任务性质路由而非工作量的同一个病）。

【只有在两边工作量相近、分不出高下时】，才用次级偏好：相近时优先 Codex 实现、Claude 审。次序是先工作量、相近时再偏 Codex，不是“实现永远归 Codex”。

跨模型审是方向性硬不变量（独立于上面的分工）：谁做了主要工作就由另一个模型审——Codex 做主活则 Claude 审，Claude 做主活则 Codex 审。所以上面“相近时偏 Codex 实现”只是次级偏好，跨模型这条不受它影响、永远成立。
