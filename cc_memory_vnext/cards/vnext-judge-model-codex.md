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
