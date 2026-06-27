---
id: vnext-self-history
kind: reference
title: 记忆系统自己的来历/现状/路线在 cc_memory_vnext/HISTORY.md
summary: 问到记忆系统的背景、重写前情况、整个重写过程、关键裁决、现状或待做未做(路线)时,先读 cc_memory_vnext/HISTORY.md(单一连贯档案),一手设计语料在 cc_memory_vnext/design/。
scope:
  domains: [memory-system-history, memory-vnext-dossier]
  paths: [cc_memory_vnext/HISTORY.md, cc_memory_vnext/design]
  symbols: []
status: active
priority: P1
triggers:
  intents: [memory-system-background, memory-system-roadmap, memory-rewrite-history]
  keywords:
    - 记忆系统背景
    - 记忆系统历史
    - 记忆系统重写
    - 记忆系统演进
    - 为什么重做记忆
    - 记忆系统路线
    - 被动数据库悖论
    - 记忆系统档案
    - 记忆系统重构过程
    - HISTORY.md
  negative_keywords: []
  paths: [cc_memory_vnext/HISTORY.md, cc_memory_vnext/design]
  symbols: []
  error_regex: []
  examples:
    - 记忆系统重写之前是什么样的、整个重构过程是怎么走的
    - 跟记忆系统有关的背景/现状/待做未做都在哪
    - 这套记忆系统为什么要重做,路线还有哪些没做
activation:
  layer_hint: L1
  must_know: false
  reason: 记忆系统自己的来历/路线问题,该直接指到那份连贯档案,而不是让人重新拼散落信息。
provenance:
  op: record
  reason: owner 2026-06-27 指出记忆系统自己的故事(背景/过程/现状/待做)散落易丢、基本没记;建档案 HISTORY.md + 导入 design 语料后,补此指针卡。
  evidence:
    - "cc_memory_vnext/HISTORY.md"
    - "cc_memory_vnext/design/ (8 份一手设计语料,143KB)"
updated_at: "2026-06-27"
---
凡是问到"记忆系统的来历 / 重写前是什么样 / 整个重写过程怎么走的 / 现在什么状态 / 还有哪些待做未做(路线)"——别去散落信息里重新拼,先读 `cc_memory_vnext/HISTORY.md`:那是这套系统自己故事的单一连贯入口(背景演进链 → 重写关键裁决 → 现状三层并存 → 未解矛盾 → V2 路线 → 东西都在哪)。

需要一手深读时,`cc_memory_vnext/design/` 有 8 份权威设计语料(143KB):两提案(A 事件账本 / B 卡片库)、两议会产出、MASTER_PLAN、演进总结、原始议会记录——它们原本散在易丢的 download 文件夹,已搬进仓库随 clone 存活。
