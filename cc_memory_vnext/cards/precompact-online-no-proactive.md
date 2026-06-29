---
id: precompact-online-no-proactive
kind: constraint
title: 在线未明令时禁止主动 precompact 或 /compact
summary: 无 owner_sleep.flag 且 owner 没明确要求执行 precompact/压缩时，绝不主动注入记忆更新回合或 /compact；owner 只是陈述计划、预告要压缩不算执行指令。
scope:
  domains: [autonomy-mode, context-compaction]
  paths: [".claude/skills/Pre-compact", "C:/Users/22957/cc_watchdog/owner_sleep.flag"]
  symbols: []
status: active
priority: P0
severity: high
triggers:
  intents: [context-compaction, precompact, autonomous-run, online-mode]
  keywords: [precompact, Pre-compact, /compact, /precompact, /Pre-compact, 记忆更新回合, owner_sleep.flag, 在线, 压缩上下文, 主动压缩, 陈述计划, 预告压缩]
  negative_keywords: [离线模式开启, 明确让我执行压缩, 你来压一下, 跑 precompact]
  paths: [".claude/skills/Pre-compact", "C:/Users/22957/cc_watchdog/owner_sleep.flag"]
  symbols: []
  error_regex: ["不能主动.*compact", "自己.*compact", "主动.*precompact"]
  examples:
    - owner 说把没记的记一下然后压缩完上下文再继续做，我要不要现在注入 /compact
    - 在线没有 owner_sleep.flag 时，owner 只是预告接下来要压缩，我能不能自调 precompact
    - 都说不能主动用这个 skill 了你怎么还自己 compact 了
activation:
  layer_hint: L1
  must_know: true
  claim_guards: ["上下文压一压", "压一压", "清一清上下文", "清一清", "压缩上下文", "压一下上下文"]
  reason: 在线误把 owner 的计划陈述当执行指令会越权主动压缩上下文。
provenance:
  op: record
  reason: 记录 2026-06-26 owner 对 precompact 在线触发边界的纠正，并绑定离线判据。
  evidence: ["python cc_memory/mem.py read precompact-flow-current-20260630 --body", "python cc_memory/mem.py read offline-mode-autonomy-criterion --body"]
updated_at: "2026-06-30"
---
在线判据只看 `C:/Users/22957/cc_watchdog/owner_sleep.flag`：不存在就是在线。在线且 owner 没明确调用 precompact、也没明确要求 CC 执行压缩时，CC 绝不主动自调 precompact，绝不注入"记忆更新回合"，也绝不注入 `/compact`。owner 说"把没记的记一下，然后压缩完上下文，再继续做""接下来要压缩上下文"这类话，是在陈述计划或预告动作，不等于命令 CC 现在执行压缩。

只有 owner 明确让 CC 执行压缩，例如敲 `/Pre-compact`（或旧名 `/precompact`），或说"你来压一下""跑 Pre-compact"，才进入在线手动触发分支。进入后按 `Pre-compact` SKILL 跑三阶段（记忆更新 → 查漏 → /compact）：`/Pre-compact` 时 hook 的 additionalContext 驱动**本回合直接做记忆更新**、做完自注查漏回合，`/compact` 永在记忆更新+查漏之后。**铁律不变：/compact 不能在记忆更新之前。**（机制详见 `Pre-compact` SKILL 与 cc_memory `precompact-flow-current-20260630`；注意：单独注入「记忆更新回合」不级联、只记一遍。）

如果 `owner_sleep.flag` 存在，则属于离线模式，是否可自主触发按 `offline-mode-autonomy-criterion` 和 precompact skill 铁律处理。本卡只约束在线默认态：owner 没明确调，就什么都不主动做。
