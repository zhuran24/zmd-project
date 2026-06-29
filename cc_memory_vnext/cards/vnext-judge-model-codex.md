---
id: vnext-judge-model-codex
kind: decision
title: v-next 查漏层默认用 Codex 跑,不用 MiMo
summary: v-next 查漏层(读 transcript 找漏召回/纠正/stale、起草补卡)真实跑当前默认用 Codex,不用 MiMo。理由:MiMo(Token Plan)限流不稳(429 limitation 冷却比分钟级 RPM 长),而 blind codex 查漏 smoke-test 已 4/4 全中。MiMo 稳定性/限流恢复并验证前,不作查漏默认模型(只当可丢弃二意见的备选)。
scope:
  domains: [vnext-judge, judge-model]
  paths: []
  symbols: []
status: active
priority: P1
triggers:
  intents: [judge-layer, judge-model-choice, run-judge]
  keywords: [查漏, judge, 查漏模型, 查漏用哪个模型, 查漏层, MiMo 查漏, 用 codex 跑查漏, 漏召回, 起草补卡, 判官, 判官回合, 查漏回合]
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 查漏这一跑用 MiMo 还是 Codex?
    - 要跑一遍查漏找漏记的,派谁?
    - MiMo 不稳,查漏改用什么模型
activation:
  layer_hint: L1
  must_know: false
  reason: 查漏选错不稳的模型会卡住整个测量/补全闭环。
provenance:
  op: record
  reason: 2026-06-27 owner 定:MiMo 不稳(持续 429),查漏改用 codex;blind codex 查漏 smoke-test 已 4/4 验证可行。
  evidence:
    - "本会话:MiMo 持续 429 limitation;owner 说'这个任务交给 codex 处理'"
    - "blind codex 查漏 smoke-test 对 opencode 坑节选 4/4 命中"
updated_at: "2026-06-27"
---
v-next 查漏层(V2 的测量件:读 transcript、经遥测预筛只看可疑切片、找漏召回/纠正/stale 卡、**起草**补丁)真实跑时,**默认用 Codex**,不用 MiMo。

理由:① MiMo(Token Plan)限流不稳——`429 limitation` 风暴后冷却期明显长于分钟级 RPM、会持续不可用;② blind codex 查漏 smoke-test 对真实材料 4/4 全中,干这活够格;③ codex 直接派(`subagent_type:'codex'`)就行,不依赖 MiMo 那条易抖的链路。

MiMo 不是不能用——它仍是"廉价二意见 / 可丢弃小活"的备选;但**查漏默认模型 = codex**,直到 MiMo 稳定性与限额恢复并经验证后再议。查漏产出永远只是**草稿**,过 verify/eval 闸 + 抽检才落,绝不自动改卡(无论哪个模型)。

**何时跑**:① 主跑 = **Pre-compact 流程里**(记忆更新回合结束后单独跑,专抓我手动那遍漏的);② 辅 = on-demand(怀疑漏了手动跑)。

**机制详见 `Pre-compact` SKILL(权威,`.claude/skills/Pre-compact/`)**:查漏天然跨异步两回合(回合A spawn 异步 codex / 回合B 收通知 triage+应用+自注 /compact);/compact 绝不预排进序列(否则两回合间 idle 空窗被提前注入 → 查漏没应用就压缩);fail-open 两处兜底,查漏≠压缩前置门。**只有调用 Pre-compact skill 才级联三阶段;单独注入「记忆更新回合」=只记一遍、不级联。** 查漏草稿 inbox-first(默认记 cc_memory 条目,够格才晋升卡)。系统化遥测预筛/小模型评估器仍属 V2。

**边界(2026-06-28):本卡只管"查漏用 Codex、precompact/测量怎么跑"。** ③ 召回触发的近期落地【地基】已转到「可观测提交点记忆闸(ZMEM_PROOF)」(详 `design/observable-commitment-gate-20260628.md`)——**别再把"查漏/看守"误当 ③ 的主解**;查漏/看守在 gate 体系里是【第四档】(只管"外露了计划但还没变成动作/结论"那块的 cross-check),不是 ③ 的近期键石。
