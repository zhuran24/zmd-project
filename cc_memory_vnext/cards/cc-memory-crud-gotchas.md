---
id: cc-memory-crud-gotchas
kind: pitfall
title: cc_memory CRUD 静默坑与调和纪律
summary: mem.py CRUD 有多类 check 不一定报的静默坑；v-next 写入闸必须前置 schema、冲突、supersede/contradict 和 evidence 校验。
scope:
  domains:
    - cc-memory-crud
    - memory-vnext
  paths:
    - cc_memory/mem.py
  symbols:
    - mem.py:set-fact
    - mem.py:add-entry
    - mem.py:relations
status: active
priority: P0
error_regex:
  - "(--force|SUPERSEDES|CONTRADICTS|pending|semantic.*exit 0|relation)"
triggers:
  intents:
    - memory-write
    - memory-schema
    - memory-system-redesign
  keywords:
    - 记忆系统
    - CRUD
    - mem.py
    - --force
    - supersede
    - contradict
    - relation
    - pending
    - schema
  negative_keywords: []
  paths:
    - cc_memory/mem.py
    - cc_memory_vnext/cards/**
  symbols:
    - set-fact
    - add-entry
    - supersede
  error_regex:
    - "(--force|SUPERSEDES|CONTRADICTS|pending|semantic.*exit 0|relation)"
  examples:
    - 重新设计记忆系统时要避免旧 mem.py 的 CRUD 静默坑
    - 用 set-fact --force 更新旧节点会不会丢 SUPERSEDES 语义
activation:
  layer_hint: L1
  must_know: false
  reason: 写入/调和/迁移相关任务中，CRUD 坑会改变系统正确性。
provenance:
  op: record
  reason: 从旧 cc_memory 节点 cc-memory-crud-gotchas 提炼；该节点列出仍真实的 mem.py CRUD 静默坑。
  evidence:
    - python cc_memory/mem.py read cc-memory-crud-gotchas --body
updated_at: "2026-06-26"
---
旧系统的危险点不是“命令会显式失败”，而是很多坑是静默的：`set-fact --force` 会原地覆盖而不表达 SUPERSEDES 语义；impact 只沿硬边传播，孤儿节点会漏影响；propose 是单向死路；search 纯 LIKE，不走语义；语义层不可用时可能 WARN 后 exit 0；新增节点推翻旧认知时必须回填旧节点内容或显式 supersede。

v-next 的对应设计要求：失败卡不进入 active `cards/`，高优卡必须有 evidence，同 scope active 冲突必须声明 supersede/contradict，pending_nonactive 只能进隔离区或直接失败。
