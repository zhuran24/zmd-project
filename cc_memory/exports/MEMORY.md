# Project Memory Export

Generated from `cc_memory/memory.db`. Do not hand-edit this file; run `python cc_memory/mem.py export`.

Fresh session:

```bash
python cc_memory/mem.py boot
```

## Stats

- facts: 16
- entries: 24
- hard edges: 11
- pending relation suggestions: 10

## Start Here

- `memory-runtime-protocol` — 新会话只需 boot; 改记忆先 impact/read; memory.db 是唯一真相, exports/MEMORY.md 是生成视图。

## Active Facts

- `codex-subagent-has-web-access` — ONLINE: codex 子代理(本机 MCP)同时有 web.run(search/open/fetch)和带网络出口的 shell_command…
- `concurrent-session-shared-index-hazard-20260617` — 本 repo 常有并发 cc 会话共用同一工作区 + 同一 .git/index。另一会话 git add/rm 的改动会进共享 index;若你 git commit -m(无 pathspec)会把别人在改的文件(如 src/ 核心)一起扫进你的提交…
- `fact-generated-memory-md-is-view` — cc_memory/exports/MEMORY.md 由 memory.db 生成, 可删可重建, 禁止手改当真相源。
- `fact-hard-edge-soft-link-separation` — DEPENDS_ON/DERIVED_FROM/SUPERSEDES/CONTRADICTS 是硬边触发传播; MENTIONS/RELATED_TO/SUPPORTS 只帮助检索和阅读。
- `fact-impact-before-memory-change` — 改 fact 或 entry 前先跑 impact/read, 只重写硬依赖影响面。
- `fact-relation-discovery-is-system-job` — 新增/修改记忆时系统主动生成候选相关 fact/entry 和候选边;使用者只负责审阅,不负责凭记忆发现完整相关集合;有高分 pending relation_suggestions 未处理时 check 必须 FAIL(A 方案强制闸)
- `fact-single-source-memory-db` — cc_memory/memory.db 是唯一活记忆真相; Markdown exports 和 archive 都不是源状态。
- `fact-workflow-subagents-default-codex` — 开 workflow 时, workflow 内 agent() 派子代理默认用 codex (agentType=codex), 省 Claude 额度; owner 指示
- `hf-model-download-via-isolated-jp-20260617` — 更正 codex-skills-and-download-route 的 HF 下载法。实测(2026-06-17 下 Qwen3-Reranker-0.6B)…
- `reranker-conservative-needs-specific-query-20260617` — 线上实测(2026-06-17):Qwen3-Reranker 高精度但保守——query 具体/点名时真目标≈1.0(完美剪噪声),但 query 短/抽象/泛(如 数据以哪份为准 这种)时把真相关也打到 0.02-0.16 全剪光、返回空…
- `semantic-engine-ab-on-own-data-20260617` — 2026-06-17 在本机真实 cc_memory 节点(21 节点/16 条换词中文查询)做嵌入模型 A/B。决定性语义测试 Eval B:harrier-oss-v1-0.6b 最强(MRR 0.969、recall@3/@5 满分、最快 1.1s)…
- `semantic-engine-picks-hf-verified-20260617` — 2026-06-17 用 HF API(createdAt+license)硬核验证 10 候选:Qwen3-Embedding-0.6B/4B、Qwen3-Reranker-0.6B(2025, Apache…

## Entries

- `arch-layering-plan-proof-vs-ops` — 核实+GPT外审:三候选模块当前架构 locally 不可缩短(pre-gate import 即 TCB);原解耦移出白名单前提证伪;衍生 __init__.py 边界债;采纳 A-prime 不动核心
- `boundary-debt-pregate-init-py` — 3 个 pre-gate __init__.py(runtime/phase3b/anchor119)删除变 namespace package 消除执行面;不动白名单故不失效 checkpoint;加 import-boundary 静态测试防重现;commit bfea3b9 已 push。CLOSED
- `cc-memory-gpu-retrieval-upgrade-plan` — 下一步给 cc_memory 加 GPU 语义检索，补当前词法引擎"逮不到同义/抽象关系"的短板。计划书: C:\22957\download\GPU_RETRIEVAL_ENHANCEMENT_PLAN.md…
- `cc-memory-p1-semantic-live-20260617` — P1 语义层上线(harrier-0.6b,d8f6c85/9ea493d);坑:跑前须 HF_HOME=E:\hf_cache;标定:相关余弦~0.42-0.48 故 dense 仅 advisory;残留 minor#2/#3
- `cc-memory-p2-reranker-live-20260617` — P2 reranker 上线(Qwen3-Reranker-0.6B,bf50387);实测果断:具体query真目标~1.0/噪声~0、0.50阈值好,泛query返空(可接受);剪高词法假阳性、真目标顶#1;WARN 可观测;缓存统一
- `close-kernel-necessity-verdict-20260619` — 会议裁决建议(待 owner):V99 close-kernel ≈ 被 frame 成闭合系统的 sink hash-pin lint;④a核心+三自保字段真必要该CI化,闭合/技术封口叙事该砍;最危险=虚假安全感(绿灯掩盖算法层);当前子串扫描连对抗漂移都没兑现,先升AST+建consumer map
- `codex-executes-claude-orchestrates` — 默认分工:具体工作/实现默认交给 codex 执行（它全权限、听指令，按提示词干活）；claude（我）负责周边任务——任务分配/编排、审阅、对抗式验证、最终验收等。即 codex = 执行体，claude = 协调与把关。owner 2026-06-17 定。
- `codex-needs-explicit-read-memory` — 本项目里 codex agent / 子代理不会主动读 CLAUDE.md 或 cc_memory 记忆系统。每次调用 codex（Agent 工具 agentType:codex / Workflow 内 agentType…
- `codex-pj-dual-repo-state` — 约6-17额度用完转codex,工作目录 C:\codex pj\zmd_pj 与 claude pj 共享 remote 但 main 领先(13+commit);P1.2 最新代码/落地/代码实证都在 codex 侧;claude pj 落后停 0c8e99f,别在落后副本上动 P1.2 文件
- `codex-skills-and-download-route` — codex skill 都在 ~/.codex/skills(CLI/桌面共用一份,子代理需显式调用);本机下模型走 hf-mirror.com 直连、单个海外大文件用 fast-dl-via-jp.ps1(隔离JP节点)、HF缓存在 E:\caches\huggingface
- `commit-session-id-hook` — 本 checkout 装了本地钩子 .git/hooks/prepare-commit-msg（git interpret-trailers 实现），每次 commit 自动追加 trailer CC-Session-Id（取 $CLAUDE_CODE_SESSION_ID）…
- `deleted-memory-found-not-restore` — 被主动删/重置的记忆删除本身是信号,找到≠该恢复;旧 _cc_live_memory/cc_context 双镜像因垃圾被重置,备份在 zmd_memory_backup_2026-06-16;只提炼干净内核(开会vs workflow已入 pref-),其余不整批搬
- `followup-h50-g-neg-and-publish-20260617` — 采补丁收尾：H/G followup (770270b) + 发布到远程私有库 zhuran24/zmd_pj；白名单收窄 wf 进行中
- `insight-digest-whitelist-protects-pregate-tcb` — 白名单保护 certified 进程可信执行面;三层 TCB(proof-semantics/pre-gate-executable/integrity-guard);pre-gate import 即必须入白名单,哪怕返回值只是 telemetry
- `owner-rejected-rigid-authorization-ledger` — owner 2026-06-17 明确否决了 standing-authorizations.json 那套"17 条要不要问 owner"的僵硬授权台账治理(太僵硬)…
- `p1-2-close-kernel-sink-write-chokepoint-runtime` — P1.2 soundness 范围: ④ 三分, runtime 活体锁(guard token/closure-cell)是路A残留该剥离, sink登记+write-capability chokepoint 留; 三判据=量词∃/∀ + TCB资格 + 覆盖/安全
- `p1-2-closegate-obligation-mechanism` — P1.2 是 owner 手动 fail-closed 门禁；8 obligation 名称级锚定非 digest；改 proof 核心机制上不强制重审但 owner 应重新攒 clean-review
- `p1-2-closure-path-verdict-20260619` — 会议裁决建议(待owner):P1.2 原理可终结(CERTIFIED被算错信息流信道先验有界A/B/C+D腿2,全史零反例,最强反方codex认账非发散);入口门控层可机器闭(deny-by-default+AST allowlist),语义正确性层永久TCB残留(=模板×3类根集);当前未闭(缺口已定位)…
- `p1-2-scope-verdict-council-20260619` — [已被 p1-2-close-kernel-sink-write-chokepoint-runtime 取代] council 早期粗版(越界2个)→ 最终修正为内部拆/纯整出0个;裁决建议待 owner 落地、改动在 codex pj 侧
- `pref-creative-tasks-use-discussion-not-workflow` — 开放判断/需观点碰撞→agents team 互辩(我主持),成员默认一半 codex 一半 claude 防趋同;Workflow 只留给确定性可分解任务
- `semantic-engine-selection-2026-06` — bge 默认已过时;本规模改用 Qwen3-Embedding-0.6B + Qwen3-Reranker-0.6B,新货 Harrier/jina 待独立核
- `soundness-claims-cxwf-verdict-20260616` — 5 个未修的 soundness 致命漏洞 + 1 个数据相关存疑；当前 repo = 补丁基线；带 file:line 与采用建议
- `soundness-patches-adopted-20260617` — 采补丁完成合入本地 main，commit a8b18d8/f226a55/44ef95e，preflight PASSED，含残留 followup 清单
