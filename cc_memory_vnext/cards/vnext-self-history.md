---
id: vnext-self-history
kind: reference
title: 记忆系统自己的来历/现状/路线在 cc_memory_vnext/HISTORY.md
summary: 问到记忆系统的背景/重写过程/关键裁决/现状/路线时,先读 cc_memory_vnext/HISTORY.md(单一连贯档案),一手设计语料在 cc_memory_vnext/design/。**同样重要:要【设计/讨论/重推记忆系统任何功能】前也先读——计划很可能早就在 HISTORY/design 里(2026-06-28 真踩:重推了已在 §5/council_B 的判官-看守结论+分档门槛)。捕获≠召回,HISTORY/design 是拉层没人推,不主动读就会重 litigate。
scope:
  domains: [memory-system-history, memory-vnext-dossier]
  paths: [cc_memory_vnext/HISTORY.md, cc_memory_vnext/design]
  symbols: []
status: active
priority: P1
triggers:
  intents: [memory-system-background, memory-system-roadmap, memory-rewrite-history, memory-system-design, memory-feature-rederive]
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
    - 记忆系统怎么设计
    - 记忆系统该不该建
    - 召回触发怎么设计
    - 判官要不要建
    - 看守要不要建
    - 记忆系统整合
    - 记忆系统迁移
    - 重新讨论记忆系统
  negative_keywords: []
  paths: [cc_memory_vnext/HISTORY.md, cc_memory_vnext/design]
  symbols: []
  error_regex: []
  examples:
    - 记忆系统重写之前是什么样的、整个重构过程是怎么走的
    - 跟记忆系统有关的背景/现状/待做未做都在哪
    - 这套记忆系统为什么要重做,路线还有哪些没做
    - 记忆系统的召回触发条件该怎么设计、要不要建个判官/看守
    - 老系统注入该不该整合/迁移/冻结、记忆系统某功能该怎么做
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
updated_at: "2026-06-28"
---
凡是问到"记忆系统的来历 / 重写前是什么样 / 整个重写过程怎么走的 / 现在什么状态 / 还有哪些待做未做(路线)"——别去散落信息里重新拼,先读 `cc_memory_vnext/HISTORY.md`:那是这套系统自己故事的单一连贯入口(背景演进链 → 重写关键裁决 → 现状三层并存 → 未解矛盾 → V2 路线 → 东西都在哪)。

需要一手深读时,`cc_memory_vnext/design/` 有 8 份权威设计语料(143KB):两提案(A 事件账本 / B 卡片库)、两议会产出、MASTER_PLAN、演进总结、原始议会记录——它们原本散在易丢的 download 文件夹,已搬进仓库随 clone 存活。

**这张卡也覆盖"设计/重推记忆系统功能"那一刻(2026-06-28 血泪教训)**:本会话我开了两场六代理大会重推「召回触发(③)」和「老系统整合(①)」,辛苦推出来的"判官/看守"结论和"冻结/迁移"路线,**早就写在 `HISTORY.md §5` + `design/council_B`**(连 Action Recall@L1≥80%、误拦率<15% 那种具体分档门槛都有)。但压缩摘要把它丢了、`HISTORY`/`design` 又是"拉"层没人推 → 我没召回到、重新昂贵推了一遍。**教训:捕获≠召回——东西记下来了不等于用到的时候会出现。所以要【设计/讨论/重推记忆系统任何功能】前,先读 `HISTORY.md` + `design/`(尤其 `MASTER_PLAN`/`council_B`),十有八九计划已在那。** 别再用一场大会重推已经定过的东西。

**更深一层(2026-06-28 owner 又追问出来的)**:这次连"压缩后第一句就是'读记忆梳理历史'、我也真读了 HISTORY"都没救——因为 ① 我把"读历史"做成了**出综述**(summary 深度),压综述时把"§5 判官=③ 的答案"这个**含义**丢了,只留了"有个判官层"的标签;② 我**没深读 design 原文**(council_B 的具体分档门槛根本没翻到)。教训:**查记忆 on 你要动手的话题,summary 深度不够 → 要 plan 深度**(读 `MASTER_PLAN`/`council_B` 原文,不是扫 dossier 叙事),而且**读完要把它【连】到当前问题**(我读了 §5 却没连到 ③ = 纯被动悖论)。最后这"连接"一环卡片推指针保证不了——**只有 ③ 的看守(读我输出 cross-check 全量记忆、喊"你在重推 §5")兜得住**。
