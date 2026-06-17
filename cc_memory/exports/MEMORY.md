# Project Memory Export

Generated from `cc_memory/memory.db`. Do not hand-edit this file; run `python cc_memory/mem.py export`.

Fresh session:

```bash
python cc_memory/mem.py boot
```

## Stats

- facts: 12
- entries: 11
- hard edges: 5
- pending relation suggestions: 6

## Start Here

- `memory-runtime-protocol` — 新会话只需 boot; 改记忆先 impact/read; memory.db 是唯一真相, exports/MEMORY.md 是生成视图。

## Active Facts

- `codex-subagent-has-web-access` — ONLINE: codex 子代理(本机 MCP)同时有 web.run(search/open/fetch)和带网络出口的 shell_command…
- `fact-generated-memory-md-is-view` — cc_memory/exports/MEMORY.md 由 memory.db 生成, 可删可重建, 禁止手改当真相源。
- `fact-hard-edge-soft-link-separation` — DEPENDS_ON/DERIVED_FROM/SUPERSEDES/CONTRADICTS 是硬边触发传播; MENTIONS/RELATED_TO/SUPPORTS 只帮助检索和阅读。
- `fact-impact-before-memory-change` — 改 fact 或 entry 前先跑 impact/read, 只重写硬依赖影响面。
- `fact-relation-discovery-is-system-job` — 新增/修改记忆时系统主动生成候选相关 fact/entry 和候选边;使用者只负责审阅,不负责凭记忆发现完整相关集合;有高分 pending relation_suggestions 未处理时 check 必须 FAIL(A 方案强制闸)
- `fact-single-source-memory-db` — cc_memory/memory.db 是唯一活记忆真相; Markdown exports 和 archive 都不是源状态。
- `fact-workflow-subagents-default-codex` — 开 workflow 时, workflow 内 agent() 派子代理默认用 codex (agentType=codex), 省 Claude 额度; owner 指示
- `semantic-engine-picks-hf-verified-20260617` — 2026-06-17 用 HF API(createdAt+license)硬核验证 10 候选:Qwen3-Embedding-0.6B/4B、Qwen3-Reranker-0.6B(2025, Apache…

## Entries

- `cc-memory-gpu-retrieval-upgrade-plan` — 下一步给 cc_memory 加 GPU 语义检索，补当前词法引擎"逮不到同义/抽象关系"的短板。计划书: C:\22957\download\GPU_RETRIEVAL_ENHANCEMENT_PLAN.md…
- `codex-executes-claude-orchestrates` — 默认分工:具体工作/实现默认交给 codex 执行（它全权限、听指令，按提示词干活）；claude（我）负责周边任务——任务分配/编排、审阅、对抗式验证、最终验收等。即 codex = 执行体，claude = 协调与把关。owner 2026-06-17 定。
- `codex-needs-explicit-read-memory` — 本项目里 codex agent / 子代理不会主动读 CLAUDE.md 或 cc_memory 记忆系统。每次调用 codex（Agent 工具 agentType:codex / Workflow 内 agentType…
- `codex-skills-and-download-route` — codex skill 都在 ~/.codex/skills(CLI/桌面共用一份,子代理需显式调用);本机下模型走 hf-mirror.com 直连、单个海外大文件用 fast-dl-via-jp.ps1(隔离JP节点)、HF缓存在 E:\caches\huggingface
- `commit-session-id-hook` — 本 checkout 装了本地钩子 .git/hooks/prepare-commit-msg（git interpret-trailers 实现），每次 commit 自动追加 trailer CC-Session-Id（取 $CLAUDE_CODE_SESSION_ID）…
- `followup-h50-g-neg-and-publish-20260617` — 采补丁收尾：H/G followup (770270b) + 发布到远程私有库 zhuran24/zmd_pj；白名单收窄 wf 进行中
- `owner-rejected-rigid-authorization-ledger` — owner 2026-06-17 明确否决了 standing-authorizations.json 那套"17 条要不要问 owner"的僵硬授权台账治理(太僵硬)…
- `semantic-engine-selection-2026-06` — bge 默认已过时;本规模改用 Qwen3-Embedding-0.6B + Qwen3-Reranker-0.6B,新货 Harrier/jina 待独立核
- `soundness-claims-cxwf-verdict-20260616` — 5 个未修的 soundness 致命漏洞 + 1 个数据相关存疑；当前 repo = 补丁基线；带 file:line 与采用建议
- `soundness-patches-adopted-20260617` — 采补丁完成合入本地 main，commit a8b18d8/f226a55/44ef95e，preflight PASSED，含残留 followup 清单
