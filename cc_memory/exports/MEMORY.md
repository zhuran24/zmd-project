# Project Memory Export

Generated from `cc_memory/memory.db`. Do not hand-edit this file; run `python cc_memory/mem.py export`.

Fresh session:

```bash
python cc_memory/mem.py boot
```

## Stats

- facts: 7
- entries: 3
- hard edges: 5

## Start Here

- `memory-runtime-protocol` — 新会话只需 boot; 改记忆先 impact/read; memory.db 是唯一真相, exports/MEMORY.md 是生成视图。

## Active Facts

- `fact-generated-memory-md-is-view` — cc_memory/exports/MEMORY.md 由 memory.db 生成, 可删可重建, 禁止手改当真相源。
- `fact-hard-edge-soft-link-separation` — DEPENDS_ON/DERIVED_FROM/SUPERSEDES/CONTRADICTS 是硬边触发传播; MENTIONS/RELATED_TO/SUPPORTS 只帮助检索和阅读。
- `fact-impact-before-memory-change` — 改 fact 或 entry 前先跑 impact/read, 只重写硬依赖影响面。
- `fact-single-source-memory-db` — cc_memory/memory.db 是唯一活记忆真相; Markdown exports 和 archive 都不是源状态。
- `fact-workflow-subagents-default-codex` — 开 workflow 时, workflow 内 agent() 派子代理默认用 codex (agentType=codex), 省 Claude 额度; owner 指示

## Entries

- `soundness-claims-cxwf-verdict-20260616` — 5 个未修的 soundness 致命漏洞 + 1 个数据相关存疑；当前 repo = 补丁基线；带 file:line 与采用建议
- `soundness-patches-adopted-20260617` — 采补丁完成合入本地 main，commit a8b18d8/f226a55/44ef95e，preflight PASSED，含残留 followup 清单
