---
name: memory-currency-protocol
description: 现状类 memory 防过时的治本协议 — 身份vs现状分离 + 单一 living 现状源 + phase 转换更新仪式 + transient 断言带日期 + 周期 staleness sweep + 仓库相对路径. 治 3 个 HIGH 过时问题 (记忆更新滞后于 phase 转换) 的 root cause.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

记忆树更新长期滞后于项目 phase 转换 → 现状类 memory 反复过时 (2026-06-01 staleness 审计抓出 3 个 HIGH: 项目身份根 memory 仍把 Phase 3B tuning 当现状 + 06_current_status 仍说 Phase 1.1 GO + F3 oracle 闭环口径错)。本协议是这类 drift 的治本规则。

**Why**: phase close / milestone / paradigm shift 频繁, 但「现状」散写在多条 memory 里, 每次转换只更新一两条, 其余变 stale。下次 session 接手按 stale memory 误判项目所处阶段 / 找已废弃的路径。根因不是某条写错, 是**没有单一权威现状源 + 没有转换时的更新仪式**。

**How to apply (6 条)**:

1. **身份 vs 现状分离**: 项目身份根 memory (如 [[endfield-solver]]) 只放**稳定身份** (项目是什么 / PROJECT_LOCK 边界 / 依赖) + 一个指向 living 现状文档的指针。**绝不**在身份根放 phase 快照 (一定会过时)。

2. **单一 living 现状源**: 恰好**一条** memory/doc 是权威「当前 phase/状态」(现在 = [[windows-ninth-review-pending]])。其余任何提到 phase/状态的 memory 必须**带日期 + 标 snapshot/历史**, 不重述现状, 只指向 living 源。

3. **phase 转换更新仪式**: phase close / milestone / paradigm shift 时跑 checklist —— (a) 更新那条 living 现状源; (b) 给被取代的状态文档加 `superseded by <现状源>` / `(历史, 日期)` 标; (c) 核身份根 memory 的指针仍指向 living 文档。每个 phase boundary 都跑一遍。

4. **transient 断言带日期**: 任何「current / 下一步 / 待启 / 在跑」类 claim 必须带日期 (如 `(更新 2026-05-31)`)。无日期的状态断言 = 默认会被当永久真相误读。

5. **周期性 staleness sweep**: phase boundary / 大 review 前跑一次 staleness 审计 (像 2026-06-01 这次: detect → 对抗 verify → 改/标), 抓累积 drift。不等「积一堆再统一清」。

6. **memory 用仓库相对路径**: 引用仓库文件用相对路径 (如 `docs/...`), 不用绝对 `D:\...`。项目搬家 (Codex → `D:\claude pj` → `D:\追光\zmd\zmd` → `D:\追光\zmd`) 即让绝对路径失效 —— 本次迁移 + roadmap drift 都是教训。

relate [[endfield-solver]] [[windows-ninth-review-pending]] [[review-pkg-data-completeness]] [[main-merger-scope-creep-bias]]。
