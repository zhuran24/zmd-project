---
id: memory-write-for-future-reader-not-present
kind: constraint
severity: high
title: 记忆写给未来的我(无当下上下文),只放要用的事实/机制;别放当下的元叙述
summary: 写持久记忆(cc_memory 条目 / vnext 卡)时只放未来读者要用这知识时需要的事实/机制/决定;别放只对当下有意义的元叙述——谈记录行为本身、narrate 当下决定/指令、对话/时间锚、跟 supersede 边重复、流水账自我推理。
scope:
  domains:
    - memory-system
    - writing-discipline
  paths:
    - cc_memory_vnext/cards
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - memory-write
    - record
    - memory-maintenance
  keywords:
    - 记忆
    - 记一下
    - 记下来
    - 记进
    - 写记忆
    - 记成卡
    - cc_memory
    - 条目
    - 卡片
    - 元叙述
  negative_keywords: []
  paths:
    - cc_memory_vnext/cards
  symbols: []
  error_regex: []
  examples:
    - 把这个机制记进 cc_memory
    - 顺手写一句"所以以后不用记那条旧规则了"
    - 记一下这个决定
activation:
  layer_hint: L1
  must_know: true
  claim_guards:
    - 记一下
    - 记下来
    - 记进
    - 写进记忆
    - 记成卡
    - 记进 cc_memory
  reason: 这是反复犯的写记忆毛病——把当下的我才需要的元叙述写进未来读者读的记忆,污染条目。owner 2026-06-29 第 N 次点出。
provenance:
  op: record
  reason: owner 2026-06-29 点出反复犯的写记忆毛病:把当下元叙述(谈记录行为/narrate 指令/对话锚)写进持久记忆。
  evidence:
    - python cc_memory/mem.py read codex-desktop-bridge-auto-cwd --body
updated_at: "2026-06-29"
---
写持久记忆(cc_memory 条目 / vnext 卡)时,**只放未来的我(没有当下对话上下文)要用这知识时需要的【事实 / 机制 / 决定】**。别放**只对当下有意义的元叙述**。

**要删的几种形态**:
1. **谈记录行为本身**:"所以记忆里不再需要 X、只记 Y" / "这条记下来是为了…" / "本条只留指针"。
2. **narrate 当下决定 / 指令**:"owner 刚让我 X 所以我 Y" / "我现在改成 Z"。
3. **对话 / 时间锚**:"本回合 / 刚才 / 这次 / 当下"——对未来读者无意义。
4. **跟机制重复**:body 里 narrate "已 supersede 旧的"——supersede 边 / SUPERSEDES 关系已经记了这事,body 别再说。
5. **流水账自我推理**:"我之前以为 X、现在发现 Y、所以…"——纠正本身是有用事实,但 blow-by-blow 过程是当下的。

**判据(写每句过一遍)**:这句给未来读者一个【要用的事实 / 机制 / 决定】,还是我在【谈记录这件事 / 我此刻的推理 / 这段对话】?后者 → 删。

**保留(别一刀切)**:provenance(谁定 / 何时 / 为何——用于信任 + 断代,如 "owner 2026-06-29 定")、纠正标记("corrects 早先 X" 一句带过,防重蹈)。

属 [[deliverable-text-lean-by-default]] 家族(都治写给读者、去冗余),但更具体 = **记忆要写给未来读者、不写给当下的我**。
