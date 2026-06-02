---
name: memory-currency-protocol
description: 现状类 memory 防过时的治本协议 — 身份vs现状分离 + 单一 living 现状源 + phase 转换更新仪式 + transient 断言带日期 + 周期 staleness sweep + 仓库相对路径 + **现状变更当下主动传播到所有嵌旧值的 memory (非等 sweep 反应式; 触发器=变更事件本身)**. 治 3 个 HIGH 过时问题 (记忆更新滞后于 phase 转换) 的 root cause.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

记忆树更新长期滞后于项目 phase 转换 → 现状类 memory 反复过时 (2026-06-01 staleness 审计抓出 3 个 HIGH: 项目身份根 memory 仍把 Phase 3B tuning 当现状 + 06_current_status 仍说 Phase 1.1 GO + F3 oracle 闭环口径错)。**补 (2026-06-01)**: 同类 drift 还有 `CLAUDE.md` "Current Phase: 3B Optimization" 旧编号 (实际已转 cut-family LBBD / P1.3A), 本 session 已改正 —— staleness sweep 要把 **CLAUDE.md 自身**也纳入扫描对象, 不只 memory。本协议是这类 drift 的治本规则。

**Why**: phase close / milestone / paradigm shift 频繁, 但「现状」散写在多条 memory 里, 每次转换只更新一两条, 其余变 stale。下次 session 接手按 stale memory 误判项目所处阶段 / 找已废弃的路径。根因不是某条写错, 是**没有单一权威现状源 + 没有转换时的更新仪式**。

**How to apply (6 条)**:

1. **身份 vs 现状分离**: 项目身份根 memory (如 [[endfield-solver]]) 只放**稳定身份** (项目是什么 / PROJECT_LOCK 边界 / 依赖) + 一个指向 living 现状文档的指针。**绝不**在身份根放 phase 快照 (一定会过时)。

2. **单一 living 现状源**: 恰好**一条** memory/doc 是权威「当前 phase/状态」(现在 = [[windows-ninth-review-pending]])。其余任何提到 phase/状态的 memory 必须**带日期 + 标 snapshot/历史**, 不重述现状, 只指向 living 源。

3. **phase 转换更新仪式**: phase close / milestone / paradigm shift 时跑 checklist —— (a) 更新那条 living 现状源; (b) 给被取代的状态文档加 `superseded by <现状源>` / `(历史, 日期)` 标; (c) 核身份根 memory 的指针仍指向 living 文档。每个 phase boundary 都跑一遍。

4. **transient 断言带日期**: 任何「current / 下一步 / 待启 / 在跑」类 claim 必须带日期 (如 `(更新 2026-05-31)`)。无日期的状态断言 = 默认会被当永久真相误读。

5. **周期性 staleness sweep**: phase boundary / 大 review 前跑一次 staleness 审计 (像 2026-06-01 这次: detect → 对抗 verify → 改/标), 抓累积 drift。不等「积一堆再统一清」。**审计的 verifiability 边界**: 自动化/磁盘/git 实况能核 **factual file-state** (路径/版本/计数/文件在不在), 自补自标没问题; 但 **judgment 级结论** (如"独立九审 = CLEAN GO"、某 verdict) 磁盘+git **证不了**, 审计不擅自改写, 须由做出该判断的主体补/确认 (本 session: 审计没擅自把 phase_1_2 memory 写成"九审 CLEAN GO", 因那是判断不是文件事实, 由 main 本 session 亲做才自补)。

6. **memory 用仓库相对路径**: 引用仓库文件用相对路径 (如 `docs/...`), 不用绝对 `D:\...`。项目搬家 (Codex → `D:\claude pj` → `D:\追光\zmd\zmd` → `D:\追光\zmd`) 即让绝对路径失效 —— 本次迁移 + roadmap drift 都是教训。

7. **现状变更当下主动传播 (proactive, 不是等 sweep 反应式捞 — 2026-06-02 用户 catch)**: 触发器 = **现状变更事件本身** (做了改变某事实的工作 / 拍了改变状态的决定 / 配置变了), **不是**事后审计。变更当下**别停在"更新了单一 living 源 / 改了手头这条"就当完事** —— 立刻 grep 全树 (+ `CLAUDE.md`) 找**旧值** (计数 / URL / phase 名 / settings 字面 / 版本号 / 触发条件), 把每一处嵌了旧值的 memory 一起改。
   - **为什么反复犯**: 我把"更新了 living 源的 body"当 done, 但别的 memory (甚至同一条) 的 **frontmatter / header / 触发条件 / description** 里**嵌着旧值**, 静默 drift。**本 session 的过时全是这个失败**: handoff frontmatter/header 停 v23 而 body 已 v25 / phase3b·phase3a 锚死范式 Phase 3B / settings.json 字面 `{hooks:{}}` / gpt-error "3 种" vs body "4 种" / review_strategy URL `zmd` —— **没一个是变更当下主动更的, 全靠周期 sweep 反应式捞回** (rule 5)。reactive 总有 drift 窗口期 (期间下个 session 会被误导), proactive 才根治。
   - **结构预防**: 优先"指向 living 源"而非"嵌值" (rule 1/2); **每个嵌入的状态值都是 drift 负债** —— 一旦嵌了, 它就进"变更当下 sweep"的清单。能指针就别 copy 值。
   - 这是 [[memory-tree-structural-health]] 第三轴 (改不全, **编辑**触发: 改 memory X 时 grep 同话题) 的**现状轴孪生** (**现状变更**触发: 事实变时 grep 旧值)。两个触发点都要有反射。

relate [[endfield-solver]] [[windows-ninth-review-pending]] [[review-pkg-data-completeness]] [[main-merger-scope-creep-bias]] [[memory-tree-structural-health]]。

## 链 (补连 2026-06-02 连通审计 whcb890zi)
- [[memory-tree-structural-health]] — 记忆树两失效轴: 内容过时 vs 结构
- [[memory-edit-confirmation]] — 改 memory 仪式共触发
- [[github-backup]] — memory sync/备份义务 + 周期维护同精神
