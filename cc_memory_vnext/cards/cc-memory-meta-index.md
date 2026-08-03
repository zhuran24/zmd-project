---
id: cc-memory-meta-index
kind: reference
title: cc_memory = 只读档案层(2026-08-03 冻结):还能读什么、别再往里写、find 是跨层入口
summary: owner 2026-08-03 拍板把 cc_memory 冻结为只读档案——新记忆一律写文件记忆层，cc_memory 只供考古(search/read --body/impact)；只知道 id 不知道在哪层就用 `mem.py find <id>`(跨三层)；写命令保留但只为档案订正，跑之前会打一行提醒、不拦。问"这条写哪/旧库还能不能写/这个 id 在哪层"按此答。
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
    - 只读档案
    - 冻结
    - 写哪层
    - 跨层
    - find
  negative_keywords: []
  paths:
    - cc_memory/**
    - cc_memory_vnext/**
  symbols:
    - zmem
    - cc_memory
  error_regex: []
  examples:
    - 这条新记忆写哪层
    - cc_memory 还能不能写、是不是冻了
    - 这个 id 在哪层记忆里,怎么跨层找
    - 重新设计记忆系统前先读哪些旧记忆
activation:
  layer_hint: L1
  must_know: false
  session_start_l0: true
  reason: 冻结后最容易犯的错是把新记忆写进档案层;常驻这张卡就是为了在动手前把"写哪层"答掉。
provenance:
  op: record
  reason: 2026-08-03 owner 拍板冻结 cc_memory 为只读档案后改写：本卡从"记忆系统操作手册"变成"档案导览 + 写哪层的答案"。原始出处是旧 cc_memory 节点 cc-memory-meta-index。
  evidence:
    - "owner 2026-08-03 拍板：cc_memory 冻结为只读档案，收件箱地位移交文件记忆层"
    - "2026-08-03 普查：cc_memory 仅 11 条 entries、07-14 起实际停写，却仍占收件箱名分 → 三层写入路由税 + 跨层找卡病"
    - python cc_memory/mem.py read cc-memory-meta-index --body
updated_at: "2026-08-03"
---
**cc_memory 从 2026-08-03 起是只读档案层**(owner 拍板)。它不再是收件箱,新记忆一律写文件记忆层 `~/.claude/projects/-home-zhuran24-zmd-pj/memory/`(`MEMORY.md` 是索引、一张卡一个 `.md`)。活跃的是两层:文件记忆 + 本层 vnext cards;cc_memory 是第三层,只剩考古价值。

**还能读什么、怎么读**:
- `python cc_memory/mem.py search "<词>"` — 档案里翻关键词;
- `python cc_memory/mem.py read <id> --body` — 读全文;
- `python cc_memory/mem.py impact <id>` — 看这条牵连了哪些边(图和边永久留在这一层,vnext 吞不下);
- `python cc_memory/mem.py find <id>` — **跨层入口**:只知道一个 id、不知道它在哪层时用这个,它会把三层都查一遍再答。记忆分层各有各的库,"这一层没有" 从来不等于 "没记过"。

**别再往里写**。写命令(`add-entry` / `set-fact` / `add-event` / `propose` / `supersede` …)一条没删——档案必须能订正——但每次执行前会打一行提醒,提醒的意思就是:如果你正在记的是**新知识**,地方错了,去文件记忆层。真是档案订正就照常做,改完 `finalize` 收口,`exports/MEMORY.md` 是生成视图别手改。

**冻结的原因**(2026-08-03 普查):三层写入路由税 + 跨层找卡病。cc_memory 只有 11 条 entries、07-14 起实际停写,却仍占着"收件箱"的名分,于是每次记东西都要先决定写哪层,而写完的东西下次又找不到。收件箱地位移交文件记忆层后,这个问题类别整个消失。
