# Project Memory Export

Generated from `cc_memory/memory.db`. Do not hand-edit this file; run `python cc_memory/mem.py export`.

Fresh session:

```bash
python cc_memory/mem.py boot
```

## Stats

- facts: 4
- entries: 4
- hard edges: 6
- pending relation suggestions: 1

## Start Here

- `cc-memory-meta-index` — cc_memory meta-index: PINNED/RULE, 读写纪律/关系/检索/git/hooks 入口。
- `memory-runtime-protocol` — 新会话 boot;查询 search/read --body/--semantic;改记忆 impact/read → set-fact/add-entry --force(订正)/ supersede(真取代)→ finalize…

## Active Facts

- `fact-generated-memory-md-is-view` — cc_memory/exports/MEMORY.md 由 memory.db 生成, 可删可重建, 禁止手改当真相源。
- `fact-hard-edge-soft-link-separation` — DEPENDS_ON/DERIVED_FROM/SUPERSEDES/CONTRADICTS 是硬边触发传播; MENTIONS/RELATED_TO/SUPPORTS 只帮助检索和阅读。
- `fact-impact-before-memory-change` — 改 fact 或 entry 前先跑 impact/read, 只重写硬依赖影响面。
- `fact-single-source-memory-db` — cc_memory/memory.db 是唯一活记忆真相; Markdown exports 和 archive 都不是源状态。

## Entries

- `codex-needs-explicit-read-memory` — Codex 记忆 2026-06: RULE, 子代理不会自动读 CLAUDE/cc_memory, 提示词要写明。
- `test-suite-speedup-2026-07-04` — 2026-07-04 提速线四个 commit 落地;slow 登记实测对时;三个假红坑;剩余项绑批2a/2b/#5-F spike/#1,不再独立推进(sealed 名单核实为据)
