---
id: vnext-judge-model-codex
kind: decision
title: v-next 判官层默认用 Codex 跑,不用 MiMo
summary: v-next 判官层(读 transcript 找漏召回/纠正/stale、起草补卡)真实跑当前默认用 Codex,不用 MiMo。理由:MiMo(Token Plan)限流不稳(429 limitation 冷却比分钟级 RPM 长),而 blind codex 判官 smoke-test 已 4/4 全中。MiMo 稳定性/限流恢复并验证前,不作判官默认模型(只当可丢弃二意见的备选)。
scope:
  domains: [vnext-judge, judge-model]
  paths: []
  symbols: []
status: active
priority: P1
triggers:
  intents: [judge-layer, judge-model-choice, run-judge]
  keywords: [判官, judge, 判官模型, 判官用哪个模型, 判官层, MiMo 判官, 用 codex 跑判官, 漏召回, 起草补卡]
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 判官这一跑用 MiMo 还是 Codex?
    - 要跑一遍判官找漏记的,派谁?
    - MiMo 不稳,判官改用什么模型
activation:
  layer_hint: L1
  must_know: false
  reason: 判官选错不稳的模型会卡住整个测量/补全闭环。
provenance:
  op: record
  reason: 2026-06-27 owner 定:MiMo 不稳(持续 429),判官改用 codex;blind codex 判官 smoke-test 已 4/4 验证可行。
  evidence:
    - "本会话:MiMo 持续 429 limitation;owner 说'这个任务交给 codex 处理'"
    - "blind codex 判官 smoke-test 对 opencode 坑节选 4/4 命中"
updated_at: "2026-06-27"
---
v-next 判官层(V2 的测量件:读 transcript、经遥测预筛只看可疑切片、找漏召回/纠正/stale 卡、**起草**补丁)真实跑时,**当前默认用 Codex**,不用 MiMo。

理由:① MiMo(Token Plan)限流不稳——`429 limitation` 风暴后冷却期明显长于分钟级 RPM、会持续不可用;② blind codex 判官 smoke-test 对真实材料 4/4 全中,干这活够格;③ codex 直接派(`subagent_type:'codex'`)就行,不依赖 MiMo 那条易抖的链路。

MiMo 不是不能用——它仍是"廉价二意见 / 可丢弃小活"的备选;但**判官默认模型 = codex**,直到 MiMo 稳定性与限额恢复并经验证后再议。判官产出永远只是**草稿**,过 verify/eval 闸 + 抽检才落,绝不自动改卡(无论哪个模型)。

**何时跑(cadence,owner 2026-06-27 定)**:① **主跑 = precompact 流程里、记忆更新回合【结束之后】单独跑**(不塞进记忆回合里抢注意力)。判官是我手动记完后的"第二遍",专抓我漏的;压缩=原始对话即将被丢的最后机会、窗口有界(配遥测预筛更省)。② **辅 = on-demand**(有理由怀疑漏了就手动跑)。

**B 已接线(2026-06-27,更新原"待接")**:判官已自动接进 precompact 链——SeqWorker 现串行排 **2 条 `[记忆更新回合, 判官回合]`**(不再是 A 的 `[记忆回合, /compact]`)。**关键:判官天然跨【两个回合】因为 `Agent subagent_type=codex` 是异步的**——回合A(判官回合提示词驱动)定位 transcript + spawn 异步 codex + 留面包屑 + 结束;回合B(codex 完成通知驱动)triage + 应用补卡(eval 绿+push)+ **自己注 `-Send "/compact"`**。`/compact` **绝不预排进序列**:codex 跨模型审抓到——预排成第三条会在"判官 spawn 回合结束→等 codex 通知"那段 **idle 空窗**被 SeqWorker 提前注入 → 判官没应用就压缩。所以 /compact 由回合B 应用完那刻自注。fail-open 两处(回合A 起不来 codex / 回合B 收到 codex 失败通知)都照样 `-Send /compact` 收尾,判官 ≠ 压缩前置门。详 SKILL `precompact` 的"判官回合怎么做" + cc_memory `precompact-seqworker-auto-flow-a`。系统化遥测预筛/小模型评估器仍属 V2。
