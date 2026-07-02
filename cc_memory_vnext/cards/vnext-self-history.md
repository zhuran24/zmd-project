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

**设计、讨论或重推记忆系统功能前，先读 `cc_memory_vnext/HISTORY.md §5`、`design/MASTER_PLAN` 和 `design/council_B`；「判官/看守」结论、「冻结/迁移」路线和分档门槛(Action Recall@L1≥80%、误拦率<15%)已有既定方案。**但压缩摘要把它丢了、`HISTORY`/`design` 又是"拉"层没人推 → 我没召回到、重新昂贵推了一遍。**教训:捕获≠召回——东西记下来了不等于用到的时候会出现。所以要【设计/讨论/重推记忆系统任何功能】前,先读 `HISTORY.md` + `design/`(尤其 `MASTER_PLAN`/`council_B`),十有八九计划已在那。** 别再用一场大会重推已经定过的东西。

**深入教训(2026-06-28 owner 点出)**:涉及记忆系统设计判断时，summary 深度不足；必须 plan-depth 深读 `MASTER_PLAN`/`council_B` 原文，并把相关章节显式映射到当前问题。教训:**查记忆 on 你要动手的话题,summary 深度不够 → 要 plan 深度**(读 `MASTER_PLAN`/`council_B` 原文,不是扫 dossier 叙事),而且**读完要把它【连】到当前问题**(我读了 §5 却没连到 ③ = 纯被动悖论)。最后这"连接"一环卡片推指针保证不了——**当前更强的解是「可观测提交点记忆闸(ZMEM_PROOF)」**:做设计判断/下结论前必须有"查过记忆"的证明,否则 Stop/PreToolUse 闸挡回去先查(详 `design/observable-commitment-gate-20260628.md`);③ 的「看守」已**降为第四档**(只管"外露了计划但还没变成动作/结论"那块的 cross-check),不再是 ③ 的主解。
