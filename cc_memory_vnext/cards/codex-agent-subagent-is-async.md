---
id: codex-agent-subagent-is-async
kind: pitfall
title: Agent(subagent_type=codex) 是异步的, 不阻塞主线——别设计依赖"codex 子代理在跑时主线持续忙"的串行/定时机制
summary: 用 Agent 工具 spawn codex 子代理(subagent_type=codex)是【异步】的:工具立刻返回 "Async agent launched, working in the background", 主线随即结束回合进入 idle, 几分钟后才由完成通知驱动新回合。所以任何"串行排在 codex spawn 之后的动作"都不能假定主线在 codex 跑期间持续忙——否则会在 spawn 回合结束后的 idle 空窗里提前触发。
error_regex: ["Async agent launched", "working in the background"]
scope:
  domains: [codex-orchestration, async-subagent]
  paths: []
  symbols: []
status: active
priority: P1
triggers:
  intents: [spawn-codex, serial-after-codex, codex-timing]
  keywords: [codex 异步, Agent subagent_type, codex 子代理, 异步, async, 主线阻塞, 主线忙, 串行, spawn codex, 后台, Async agent launched, 子代理在跑, 等 codex]
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: ["Async agent launched", "working in the background"]
  examples:
    - 我想在 spawn codex 子代理之后串行排一个后续动作, codex 在跑时主线应该一直是忙的吧?
    - 把 /compact 排在判官回合(spawn codex)后面, 子代理在飞主线就一直 busy, 不会提前注入吧?
    - 派 codex 之后我可以接着在同一回合里等它的结果吗?
activation:
  layer_hint: L1
  must_know: false
  reason: 误以为 codex 子代理阻塞主线, 会设计出在异步 idle 空窗里提前触发的串行/定时机制。
provenance:
  op: record
  reason: 2026-06-27 我设计 precompact 判官插链(B)时, 把 /compact 预排成 [记忆回合, 判官回合, /compact] 第三条, 误以为"判官回合 spawn 的 codex 子代理在飞时主线持续忙、worker 不会提前注 /compact"; codex 跨模型审一眼看穿 Agent subagent_type=codex 是异步的, 我那个假设不成立。
  evidence:
    - "本会话 Agent 工具 spawn codex 返回原文: 'Async agent launched successfully... working in the background. You will be notified automatically when it completes.'"
    - "codex 复审: /compact 预排在异步 Agent 边界后会在 spawn 回合结束后的 idle 空窗被 SeqWorker 提前注入 → 判官没应用就压缩"
    - "根治: /compact 不预排、改由 codex 完成通知驱动的回合 B 应用完后自注; 详 cc_memory precompact-seqworker-auto-flow-a"
updated_at: "2026-06-27"
---
用 `Agent` 工具 spawn codex 子代理(`subagent_type=codex`)是**异步**的:工具立刻返回 `Async agent launched successfully... working in the background. You will be notified automatically when it completes.`, **主线随即结束本回合、进入 idle**, codex 在后台跑(可能几分钟), 跑完后由一条**完成通知**驱动一个**新回合**让我处理结果。

**坑**: 任何"串行排在 codex spawn 之后的动作"——尤其是靠外部 worker / 定时器在"主线空闲"时触发的动作——都**不能**假定主线在 codex 子代理跑期间持续"忙"。spawn 回合一结束主线就 idle 了, 那个动作会在 codex 还没跑完时就被提前触发。(2026-06-27 实例: precompact 判官插链把 `/compact` 预排在 spawn codex 的判官回合之后, SeqWorker 在 spawn 回合结束后的 idle 空窗就提前注了 /compact → 判官结果还没应用就压缩。)

**正确用法**: 把"codex 跑完之后才做的事"放到**完成通知驱动的那个回合**里去做(收到通知 = 那一刻才 triage / 应用 / 注入后续), 而不是预排在 spawn 之后的串行/定时位置。需要"超时兜底"时, 用显式的超时**提示词**(非直接执行危险动作)+ 防误伤校验, 别用裸的长延迟定时器。相关: 敏感时序机制需要跨模型审；单模型审曾漏掉 codex 子代理异步本质。
