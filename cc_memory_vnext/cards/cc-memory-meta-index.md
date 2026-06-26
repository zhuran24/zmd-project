---
id: cc-memory-meta-index
kind: reference
title: cc_memory 元记忆索引必须先读
summary: cc_memory 自身操作手册是元记忆常驻层；改记忆系统或做实质决定前，先读元索引和相关节点，不只依赖上下文。
scope:
  domains:
    - cc-memory-system
    - memory-vnext
  paths:
    - cc_memory/mem.py
    - cc_memory/exports/MEMORY.md
    - cc_memory_vnext/**
  symbols:
    - cc_memory_meta_index
    - zmem
status: active
priority: P0
triggers:
  intents:
    - memory-system-redesign
    - memory-bootstrap
  keywords:
    - 记忆系统
    - v-next
    - cc_memory
    - meta-index
    - 元记忆
    - hook
  negative_keywords: []
  paths:
    - cc_memory/**
    - cc_memory_vnext/**
  symbols:
    - zmem
    - cc_memory
  error_regex: []
  examples:
    - 重新设计记忆系统前先读哪些旧记忆
    - 给 cc_memory_vnext 做 hook 注入和卡片编译
activation:
  layer_hint: L1
  must_know: false
  session_start_l0: true
  reason: 系统自指记忆靠常驻与强触发避免抽象查询漏召回。
provenance:
  op: record
  reason: 从旧 cc_memory 节点 cc-memory-meta-index 提炼；旧节点明确要求每次 boot 必读，并把它作为记忆系统操作手册。
  evidence:
    - python cc_memory/mem.py read cc-memory-meta-index --body
updated_at: "2026-06-26"
---
当任务涉及记忆系统本身、hook、检索层、关系边、语义检索、跨会话提醒或旧 cc_memory 操作纪律时，先把 `cc-memory-meta-index` 当导航卡读入。它不是项目内容记忆，而是告诉代理怎样正确使用记忆系统的元层。

关键提炼：`cc_memory/memory.db` 是旧系统唯一活真相源，`exports/MEMORY.md` 是生成视图；系统级元知识要更新元索引；做实质决定时看到相关覆盖域就先 search/read，而不是只信当前上下文。
