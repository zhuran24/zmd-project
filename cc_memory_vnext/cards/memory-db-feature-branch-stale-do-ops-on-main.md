---
id: memory-db-feature-branch-stale-do-ops-on-main
kind: pitfall
title: feature 分支的 memory.db 可能早于 main → 记忆读写要在 main 权威库做
summary: 在 feature 分支上 search/read cc_memory 可能【假 no-match】,因为该分支的 cc_memory/memory.db 比 main 旧、缺 main 上新建的条目;cc_memory 读写应切到 main 权威库做。
error_regex: ["(mem\\.py|cc_memory)[\\s\\S]{0,300}no match"]
scope:
  domains: [cc-memory-branch]
  paths: [cc_memory/memory.db]
  symbols: []
status: active
priority: P1
triggers:
  intents: [memory-write, memory-read, memory-search, branch-switch]
  keywords: [memory.db, cc_memory, search no matches, 假 no-match, feature 分支, 权威库, main, 跨分支, 分叉, 搜不到刚建的条目]
  negative_keywords: []
  paths: [cc_memory/memory.db]
  symbols: []
  error_regex: ["(mem\\.py|cc_memory)[\\s\\S]{0,300}no match"]
  examples:
    - 在 feature/PR 分支上 mem.py search 自己之前建的条目却 no matches
    - 当前分支的 cc_memory/memory.db 比 main 旧、缺最近建的条目
    - 想在 feature 分支上更新记忆但条目都在 main 上
activation:
  layer_hint: L1
  must_know: false
  reason: cc_memory 的真相库在 main;feature 分支 memory.db 可能 stale,直接在其上读写会假 no-match 或写进分叉副本。
provenance:
  op: record
  reason: 记录 2026-06-30 在 pr2-5 分支上 search 本会话条目假 no-match 的实测坑。
  evidence: ["2026-06-30 实测：在 pr2-5-domain-frontier-gate 分支上 `python cc_memory/mem.py search` 找本会话在 main 建的 pr2-5 条目，返回 no matches；根因=pr2-5 的 memory.db 还是 d68bdc9 版、早于 main、缺那些条目"]
updated_at: "2026-07-03"
---
`cc_memory/memory.db` 是 SQLite 二进制,各分支各有一份、**不会自动跟 main 同步**。在一条 feature / PR 分支上做记忆操作时,该分支的 `memory.db` 可能是早先从 main 分出来的旧版本——比 main 落后好几个提交,**缺 main 上后来新建的条目**。

典型信号:在 feature 分支上 `python cc_memory/mem.py search`(或 `read <id>`)找一条你确定建过的条目,却返回 `no matches` / 找不到。别误以为条目没建成或丢了——大概率是**你站在 stale 分支的 memory.db 上**,而条目活在 main 的权威库里。

正确做法:**cc_memory 的真相库在 main,读写都去 main 做**。代码在 feature 分支时:① 先 `git checkout -- cc_memory/memory.db` 丢掉当前分支的水位印记,再 `git checkout main` 切过去做记忆(改完在 main 提交 memory.db + exports/MEMORY.md);② 若要边看 feature 分支代码边用 main 最新记忆,用 git archive/overlay 把代码与 main 记忆组合(见 [[git-archive-overlay-snapshot-no-branch-switch]]),别把 feature 分支的 stale memory.db 当真。与并发提交冲突坑 [[memory-db-cross-session-push-conflict]]、共享 index 坑 [[concurrent-session-shared-index-hazard]] 同属"共享/分叉 memory.db 的协作陷阱"族。
