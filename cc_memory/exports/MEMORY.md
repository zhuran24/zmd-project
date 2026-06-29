# Project Memory Export

Generated from `cc_memory/memory.db`. Do not hand-edit this file; run `python cc_memory/mem.py export`.

Fresh session:

```bash
python cc_memory/mem.py boot
```

## Stats

- facts: 21
- entries: 130
- hard edges: 158
- pending relation suggestions: 0

## Start Here

- `cc-memory-meta-index` — cc_memory meta-index: PINNED/RULE, 读写纪律/关系/检索/git/hooks 入口。
- `memory-runtime-protocol` — 新会话 boot;查询 search/read --body/--semantic;改记忆 impact/read → set-fact/add-entry --force(订正)/ supersede(真取代)→ finalize…
- `offline-mode-autonomy-criterion` — 离线判据: RULE, owner_sleep.flag 为准; CC 不自行推断在线/离线。

## Active Facts

- `cc-memory-semantic-low-adoption-verdict-20260619` — 2026-06-19 复盘:语义层(P1 嵌入+P2 reranker)目前近乎闲置——其他会话(含 codex 侧 0b26e341)几乎只用 LIKE 子串/词法检索(非真 FTS);retrieval_runs 遥测表根本没建(语义查询连日志都没)…
- `codex-subagent-has-web-access` — ONLINE: codex 子代理(本机 MCP)同时有 web.run(search/open/fetch)和带网络出口的 shell_command…
- `concurrent-session-shared-index-hazard-20260617` — 本 repo 常有并发 cc 会话共用同一工作区 + 同一 .git/index。另一会话 git add/rm 的改动会进共享 index;若你 git commit -m(无 pathspec)会把别人在改的文件(如 src/ 核心)一起扫进你的提交…
- `fact-generated-memory-md-is-view` — cc_memory/exports/MEMORY.md 由 memory.db 生成, 可删可重建, 禁止手改当真相源。
- `fact-hard-edge-soft-link-separation` — DEPENDS_ON/DERIVED_FROM/SUPERSEDES/CONTRADICTS 是硬边触发传播; MENTIONS/RELATED_TO/SUPPORTS 只帮助检索和阅读。
- `fact-impact-before-memory-change` — 改 fact 或 entry 前先跑 impact/read, 只重写硬依赖影响面。
- `fact-p1-2-release-gate-status-20260626` — blocked_manual_review_count; next_phase_entry.allowed=false; 人类阶段名 P1.3, 机器兼容字段 p1_3b_entry_allowed=false…
- `fact-p1-2-supervisor-operability-20260626` — supervisor_seal 已实现且有测试, 但仓库无生产 CLI/launcher/service 调用它; main.py 止于 CANDIDATE_PROPOSED
- `fact-p1-2-test-inventory-20260626` — 425 files/3450 = collect-only inventory; post-D 组 + GPT 文本审计落地后全量 preflight(跳@slow) 3346 passed/0 failed; 机器检查全过; 无独立完整 3450 @slow 套件通过声明
- `fact-relation-discovery-is-system-job` — 新增/修改记忆时系统主动生成候选相关 fact/entry 和候选边;使用者只负责审阅,不负责凭记忆发现完整相关集合;有高分 pending relation_suggestions 未处理时 check 必须 FAIL(A 方案强制闸)…
- `fact-single-source-memory-db` — cc_memory/memory.db 是唯一活记忆真相; Markdown exports 和 archive 都不是源状态。
- `fact-workflow-subagents-default-codex` — 开 workflow 时, workflow 内 agent() 派子代理默认用 codex (agentType=codex), 省 Claude 额度; owner 指示
- `hf-model-download-via-isolated-jp-20260617` — 更正 codex-skills-and-download-route 的 HF 下载法。实测(2026-06-17 下 Qwen3-Reranker-0.6B)…
- `memory-db-cross-session-push-conflict-20260619` — 2026-06-19 实测:多会话/多 checkout 都把共享 memory.db 提交到同一 main 时,push 非-ff 撞二进制冲突(git 无法 auto-merge SQLite)…
- `reranker-conservative-needs-specific-query-20260617` — 线上实测(2026-06-17):Qwen3-Reranker 高精度但保守——query 具体/点名时真目标≈1.0(完美剪噪声),但 query 缺锚定词(泛/口语化…
- `semantic-engine-ab-on-own-data-20260617` — 2026-06-17 在本机真实 cc_memory 节点(21 节点/16 条换词中文查询)做嵌入模型 A/B。决定性语义测试 Eval B:harrier-oss-v1-0.6b 最强(MRR 0.969、recall@3/@5 满分、最快 1.1s)…
- `semantic-engine-picks-hf-verified-20260617` — 2026-06-17 用 HF API(createdAt+license)硬核验证 10 候选:Qwen3-Embedding-0.6B/4B、Qwen3-Reranker-0.6B(2025, Apache…

## Entries

- `21a9dda-argv0-live-12` — 21a9dda 三审 2026-06-23: LIVE/BLOCKED, argv0 升 LIVE, §12 设计补。
- `4-fix-1-3-reopen-capsule` — 第 4 轮外审(3 个独立 GPT Pro reviewer，blind A-G，2026-06-23)裁了 FIX-1/2/3。报告原文:C:\22957\download\新建文件夹\{1,2,3}\回复.txt…
- `agents-team-open-task-in-process` — 2026-06-19 开 hook-coverage-council 4人会议(2c2c)踩到两个运维坑。 坑1【团队成员认领主会话 open task】…
- `arch-layering-plan-proof-vs-ops` — 架构分层 2026-06: DONE, pre-gate TCB 三模块不可移出, 采 A-prime。
- `boundary-debt-pregate-init-py` — 边界债 bfea3b9: DONE, 删除3个 pre-gate __init__.py 并加静态防回归。
- `capsule-opus-canonical-binding-mock` — FIX-5 canonical-binding: DONE, benders_loop snapshot kwargs + mock 坑。
- `cc-memory-crud-gotchas` — cc_memory CRUD 2026-06-20: RULE, 7个静默坑+已修归档, impact/硬边优先。
- `cc-memory-crud-operations` — cc_memory CRUD 命令: RULE, read/impact/add-entry/link/supersede/archive/finalize。
- `cc-memory-hook-backstop-landed-20260620` — cc_memory hook c6cd8fd: LANDED 2026-06-20, PostToolUse finalize + SessionStart。
- `cc-memory-meta-system-consolidated-index-20260628` — cc_memory C档 2026-06-28: INDEX, 折叠 search/read/semantic/rerank/hook 元系统旧节点。
- `cc-memory-update-vs-supersede-rule` — 记忆改写 2026-06-20: RULE, 订正 --force; 真取代 supersede。
- `ci-saga-slow-blindspot-flaky-mechanism-20260626` — CI saga 0bc36db: DONE 2026-06-26, @slow 盲区+delivery flaky 均修绿。
- `claude-md-maintenance-method-20260628` — CLAUDE.md 维护 2026-06-28: RULE, 工具归属+保守缩写+归档边界。
- `clipboard-relay-deliverables-to-owner` — relay 交付 2026-06-20/23: RULE, 剪贴板给提示词正文+包完整路径。
- `close-kernel-necessity-verdict-20260619` — V99 close-kernel 2026-06-19: VERDICT, sink hash-pin lint; 防虚假安全感。
- `close-kernel-sealed-lint-v99-reseal-re-export-patch-ruff-f401` — close-kernel lint 2026-06-28: WARN, sealed 改动会触发 reseal/F401 patch 坑。
- `codegraph-codegraph-codegraph-init-proof-cc-memory` — CodeGraph: RULE, 项目代码结构索引/MCP/CLI; 非 proof、非 cc_memory。
- `codegraph-freshness-lazy-sync-on-use` — CodeGraph 2026-06-28: RULE, lazy sync-on-use; watcher 非常驻, sync hook 已删。
- `codegraph-precompact` — precompact/codegraph 2026-06-26: WARN, 已记规则未先查导致三犯。
- `codex-agents-team-sendmessage-sonnet` — Codex Team 2026-06: RULE, 进 Agents Team 互通需 sonnet 中介 SendMessage。
- `codex-agenttype-schema-structuredoutput-empty-loop` — codex schema 2026-06-21: FIXED, 空提交根因=shim纯管道 vs 结构化。
- `codex-claude-clean-workflow` — 大活流程 2026-06-21/28: RULE, Codex 实现→Claude 审→回环到 clean。
- `codex-claude-codex-claude-4-1-high` — owner 2026-06-21 当场纠正 + 实证。规矩(承 [[feedback-default-codex-desktop-mcp]]):**实现工作交 Codex(`mcp__codex_desktop__codex`)…
- `codex-desktop-bridge-auto-cwd` — 机制:codex_desktop 桥(C:\Users\22957\codex_desktop_mcp.py)run_turn 没收到 cwd 就默认 CLAUDE_PROJECT_DIR or os.getcwd()=本项目目录→no-isolation codex 自动在我活工作树跑(含未提交)、不落 codex…
- `codex-direct-mcp-emits-strict-schema-json` — codex direct MCP 2026-06-21: VERIFIED, schema JSON 稳; codex.md fix#3 已可用。
- `codex-executes-claude-orchestrates` — 分工 2026-06-26/28: RULE, 先按工作量; 大活 Codex, Claude 编排终审。
- `codex-needs-explicit-read-memory` — Codex 记忆 2026-06: RULE, 子代理不会自动读 CLAUDE/cc_memory, 提示词要写明。
- `codex-owner-2026-06-27-30min` — 2026-06-27 实证 + owner 定调。PR2-b 实现 workflow 的 codex agent 挂死 78 分钟没返回。根因…
- `codex-read-only-mcp-sandbox-approval-policy` — Codex MCP 2026-06-21: RULE, 默认桌面桥; strip 代理是回退路。
- `codex-schema-framework-parity-pure-pipe` — codex+schema定论:框架对codex/原生扶持一样(非grammar,是校验+5次重试);瓶颈=codex.md纯管道不让身体整形;codex.md再修区分整形/实质
- `codex-skills-and-download-route` — Codex skills/HF 2026-06: RULE, skills 在 ~/.codex; HF 下载走隔离 JP 路由。
- `commit-session-id-hook` — commit hook: LIVE, prepare-commit-msg 自动加 CC-Session-Id trailer。
- `defensive-verbosity-when-criticized` — 文字反馈 2026-06-21: RULE, 被批评默认删减, 不加防御 caveat。
- `deleted-memory-found-not-restore` — 旧记忆迁移 2026-06: RULE, 被主动删除=信号; 不整批恢复垃圾镜像。
- `deliverable-text-lean-by-default` — 交付文字 2026-06-21/23: RULE, intro 只点审什么+怎么审, 少防御。
- `feedback-council-create-team-first` — Agents Team 2026-06-20: RULE, 开会先 TeamCreate, 不能散派 Agent。
- `feedback-no-manufactured-owner-decisions` — owner 决策 2026-06-20: RULE, 不从已定可行性里造假拍板项。
- `fix-4-fix-5-i1-toctou` — FIX-4/FIX-5 2026-06-23: SPEC, I1 独立复验 + TOCTOU 原子快照。
- `flaky-worktree-fail-closed-bug-workflow` — flaky 2026-06: VERDICT, worktree 漂移触发正确 fail-closed, 非核心 bug。
- `git-worktree-codex-crlf-worktree-preflight` — 在隔离 git worktree 里跑 preflight/pytest 会撞两个与代码 soundness 无关的机械 BLOCK,实测于 topology-opt worktree(2026-06-27)…
- `github-ruleset-slow-soundness-gate-ci` — 2026-06-21 给 slow-soundness-gate 设 required(GitHub branch protection / ruleset)失败…
- `gpt-pro-sandbox-can-edit-files` — GPT Pro relay 2026-06: LIVE, 可解包读改文件并回传 diff/包。
- `insight-digest-whitelist-protects-pregate-tcb` — digest 白名单: INSIGHT, 保护 pre-gate 可执行 TCB, 非普通数据流。
- `memory-prune-2026-06-21-manual-baseline-system-deferred` — 记忆剪枝 2026-06-21: DONE, 归档5+修漂移9; 自动系统 deferred。
- `memory-vnext-gate-reframe-20260628` — vnext gate 2026-06-28: REFRAME, ZMEM_PROOF 提交点强制查证。
- `mock-based-patch-mock-unproven-preflight` — mock patch 2026-06: RULE, 重构下游入口后同步迁 patch 点。
- `naming-p1-3-vs-p1-2-fix` — 命名 2026-06-22: RULE, master 集成=P1.3; soundness 必修=P1.2-FIX。
- `owner` — owner 偏好 2026-06-26: RULE, 非主线但不小的子项目要单独快照。
- `owner-rejected-rigid-authorization-ledger` — owner 2026-06-17 明确否决了 standing-authorizations.json 那套"17 条要不要问 owner"的僵硬授权台账治理(太僵硬)…
- `p1-2-4b-sink-replay-rootcure-landed-20260620` — P1.2 ④b a5ff5aa: LANDED 2026-06-20, sink-replay 隔离根治。
- `p1-2-c1-landed-reseal-mechanism-20260620` — 2026-06-20 C1落地(commit 91476ae push):8个src/cuts孤岛sink p1_2_certified_path→out_of_scope_future_phase3b…
- `p1-2-c3-kernel-audit-3source-20260620` — P1.2 C3 2026-06-20: BLOCKED, I1+吞吐两 CRITICAL; 供电 sound。
- `p1-2-c4-c5-2026-06-21-3-latent-false-infeasible-f7-f8-f3-cuts-live-canonical-p1-3b-tcb` — P1.2 C4/C5 2026-06-21: LIVE, 3个 false-INFEASIBLE 雷; P1.3B 修。
- `p1-2-capsule-f492690-fix-1-3-fix-5` — P1.2 capsule 根治 bundle 已提交 f492690(FIX-1+FIX-3+FIX-5 一并)。闭第4轮外审推翻的 FIX-1/FIX-3 + 顺带 FIX-5 TOCTOU…
- `p1-2-close-kernel-sink-write-chokepoint-runtime` — P1.2 close-kernel 2026-06-19: VERDICT, sink chokepoint 留; runtime 锁剥离。
- `p1-2-closegate-obligation-mechanism` — P1.2 close-gate: RULE, owner 手动门禁 + obligation 名称锚定。
- `p1-2-closure-path-verdict-20260619` — P1.2 闭合 2026-06-19: VERDICT, 原理可终结; 语义层仍 TCB。
- `p1-2-consumer-map-proof-freshness-stamp` — 2026-06-19 workflow wy3ymwhtw(10 子代理:5 字段组 enum claude/codex 混 + 异源 adversary,只读 codex pj working tree)产出…
- `p1-2-current-publication-surface-status-20260626` — P1.2 发布面 2026-06-26: BLOCKED, PR1外审全闭; PR2仍开放。
- `p1-2-current-validation-20260626` — D组终审 3343 passed;GPT 文本审计落地后终审 3346 passed/0 failed;机器检查全过;425/3450 是 collect-only 非通过数
- `p1-2-fix-1-close-kernel-crlf` — P1.2-FIX-1 2026-06-22: LANDED, fixed-witness verifier; CRLF 重封坑。
- `p1-2-fix-1-design-fixed-witness-verifier` — P1.2-FIX-1 设计 2026-06-22: SPEC, terminal fixed-witness verifier。
- `p1-2-fix-1-memory-disk-surface-binding-20260622` — V93 regression root cause: terminal_certified_final_result_violation_for_project could validate on-disk authority_state when campaign_path…
- `p1-2-fix-2-open-gate-landed-20260623` — P1.2-FIX-2 OPEN-GATE 已提交 `de68515`(ahead origin/main 12、未推)。闭 [[p1-2-witness-split-block-2026-06-21]] 登记的 OPEN-GATE BLOCK…
- `p1-2-fix-4-landed-44089a3` — P1.2-FIX-4(I1)已提交 44089a3。闭 round-3/外审登记的 I1 BLOCK(whole-layout nogood 缺独立 ⊆-infeasible 复验)。承设计 [[fix-4-fix-5-i1-toctou]]…
- `p1-2-p-b-7-mock-stale-5-2xfail-premise-obsolete-gate-c5-harness-flaky` — P1.2 命题P尾巴 2026-06-20: DONE, 7 mock stale+gate 慢测盲区。
- `p1-2-pyc-exec-digest-narrow-closure-20260623` — PYC-EXEC-DIGEST 88b2d32: DONE, 窄洞真闭; 第5轮确认非 capsule 全局收敛。
- `p1-2-resume-2026-06-21-origin-main-67139a5-p-landed-b-stale-gate-c0-c3-c4-c5-codex-claude` — P1.2 resume 2026-06-21: SNAPSHOT, C0-C5 done; GPT Pro 外审在飞。
- `p1-2-review-converged-tcb-start-p1-3` — P1.2 外审 2026-06-21: VERDICT, 三轮均 BLOCK; 进入 P1.3 TCB 线。
- `p1-2-round5-external-review-capsule-not-closed` — P1.2 第5轮 2026-06-23: BLOCKED, capsule 根未闭; supervisor 重做。
- `p1-2-supervisor-l0-l1-design-meeting-20260623` — P1.2 supervisor 2026-06-23: SPEC, L0/L1 两层+受控 loader。
- `p1-2-supervisor-production-entry-gap-20260626` — P1.2 supervisor 2026-06-26: GAP, seal 有实现但无生产入口。
- `p1-2-witness-split-block-2026-06-21` — P1.2 witness-split 2026-06-21: BLOCK, 发布 π* 未复验 binding/routing。
- `pathspec-must-cover-full-reseal-set` — pathspec 2026-06-28: RULE, reseal 提交必须覆盖完整一致集防 CI drift。
- `pr1-publication-blocks-abc-fixed` — PR1 A/B/C/D 2026-06-26: DONE, 7类发布面 BLOCK 全修+终审绿。
- `pr1-soundness-b085a75-ci` — GPT Pro 对 0bc36db 做了【三轮独立外审 + 三份补丁】(互冲不能叠加),并集 = B/D/A/C/B2/E。走 codex-claude-clean-workflow…
- `pr1-supervisor-mint-preflight` — PR1 supervisor 地基两块 2026-06-23 落地、**已提交 `ddb3b5a`**(feat(p1.2): PR1 supervisor 地基…
- `pr2-5-seal-frontier-gate-landed` — PR2 #5: child升格漏declare_mode/last_stop_reason致seal路径穷尽校验死代码;已修+GPT Pro panel挖2 BLOCK(parent mint不归一+AST pin松)+CRLF reseal坑;待复审merge
- `pr2-8-9a-hardened-landed-099f5a3` — PR2 #8(删自跳过)+#9a(floor钉死)+GPT Pro外审硬化(#8-A子进程-I-S-B/#8-B源码sha楼面/#9a-A L0 runtime byte-pin堵时序旁路)合 main 099f5a3,CI两gate绿。多会话panel验证有效(2会话收敛挖3 BLOCK本地审都漏)…
- `pr2-b-codex-2-false-certified-opus-0-pr2-b-sound-tcb-b1-owner` — PR2-b 2026-06-28: BLOCKED, codex 找2条 false-CERTIFIED; 待B1/B2硬化。
- `pr2b-landed-pr2-remaining-status-20260628` — PR2-b 69980b3+592ea13: LANDED 2026-06-28, SOUND; PR2余项表。
- `precompact-a-b-compact-codex-race` — precompact A+B 2026-06-28: PARTIAL/SUPERSEDED, offline SeqWorker 适用。
- `precompact-scope-precompact-hook-codex-hooks-json-taskstop` — 2026-06-28 precompact 判官(codex 第二遍)逮到我自审漏的 4 条 + 后续 owner 对 precompact 机制的最终拍板…
- `precompact-skill-compact-inline-owner` — precompact skill 2026-06-28: PARTIAL/SUPERSEDED, offline 先记忆回合。
- `pref-creative-tasks-use-discussion-not-workflow` — 任务路由 2026-06-20: RULE, 创造/判断用 Agents Team, 不用 Workflow。
- `relay` — relay 2026-06-23: RULE, 发出外审动作要当场记; 打包≠已发送。
- `review-prompt-also-request-patches` — 外审提示 2026-06-26: RULE, 找全 BLOCK 后直接要补丁+根因+行号。
- `review-prompt-request-exhaustive-coverage` — 外审提示 2026-06-23: RULE, 要全覆盖; 不用裸 STOP 造成只找一个。
- `review-routing-codex-local-then-gptpro-relay` — 审查路由 2026-06-28: RULE, 本地 Codex 审修→GPT Pro relay; 不派 workflow。
- `setter-barrier-p1-3b-getframe` — owner 2026-06-19 决策 setter barrier 留 P1.3B;它是禁令卡(TaskList 无此工单),P1.2 收到去做指令一律拒绝+上报 owner,不可认领
- `soundness-claims-cxwf-verdict-20260616` — 5 个未修的 soundness 致命漏洞 + 1 个数据相关存疑；当前 repo = 补丁基线；带 file:line 与采用建议
- `soundness-opus-codex-pr2-b-codex-2-false-certified-opus-0` — PR2-b 终审 2026-06-28: LIVE, 跨模型必要; codex 2 blocker/opus 0。
- `soundness-patches-adopted-20260617` — 采补丁完成合入本地 main，commit a8b18d8/f226a55/44ef95e，preflight PASSED，含残留 followup 清单
- `subagent-model-floor-sonnet` — owner 2026-06-23 纠:workflow 里给映射 agent 用了 agentType:'Explore'(默认掉到 haiku),被指出太弱…
- `symmetric-tasks-need-symmetric-agent-dispatch` — 对称派遣 2026-06-20: RULE, 同质任务才对称; 双源是 opt-in。
- `terminology-meeting-equals-team` — 术语 2026-06-23: RULE, 开会=Agents Team, 不是独立 Workflow。
- `topology-opt-chunk2-landed` — topology-opt a20ee31: LANDED, Chunk2 S2/S3 诊断 hint planner 未接线。
- `topology-opt-gpt-chunk1-codex` — topology-opt 2026-06-27: DONE, GPT 两优化书评估+Chunk1 落地。
- `transcript-decompact-extract-tool` — transcript抽3视图:live(全线程+工具输出,看守进程实时)/history(纯对话分卷~1MB)/latest(最新段=刚被压那段,PreCompact写);Stop hook弃用改看守
- `v-next` — cc_memory_vnext 2026-06-27: LIVE, MVP-0 上线; zmem 卡/金标准为准。
- `wf-verify-also-codex-no-parallel-bolt` — WF 验证 2026-06-21: RULE, 审计也走 Codex→Claude; 别旁路加并行。
- `workflow-default-multimodel-opus-codex` — workflow 2026-06-28: RULE, 诊断用 opus+codex; 审查改 GPT Pro relay。
- `worktree-baseref-head-vs-fresh` — owner 2026-06-29 拍 + 官方文档/Issue#60588 核实。head=本地当前HEAD(含未push commit+当前分支),fresh=origin/HEAD永远盯main不跟当前分支。我们高频派subagent接feature分支干→要head。两者都不带未commit工作区改
- `xmodel-review-is-standing-rule-symmetric` — 跨模型审 2026-06-23: RULE, 站立规则自动触发, 非 owner 逐次指派。
