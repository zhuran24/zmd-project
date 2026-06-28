---
id: review-routing-gptpro-relay
kind: decision
title: 审查走 codex 本地审修 → 打包 relay GPT Pro，不派 workflow
summary: 双模型对抗审原则不变，但把 opus/claude 那侧换成 GPT Pro（claude/opus 审也烧额度）；流程=本地 codex 先审+修→打包+写任务书提示词 relay 给 GPT Pro 第二遍跨模型审；审查不派 workflow（会拉 opus 烧 claude 额度）。
scope:
  domains:
    - agent-orchestration
    - delegation
    - review
  paths:
    - AGENTS.md
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - review
    - audit
    - cross-model-review
    - soundness
    - delegation
  keywords:
    - 审查
    - 审
    - soundness
    - 跨模型
    - 外审
    - review
    - GPT Pro
    - relay
    - 打包
    - 提示词
    - 补丁
    - 对抗审
    - 认证核心
    - 双模型
  negative_keywords: []
  paths:
    - AGENTS.md
  symbols: []
  error_regex: []
  examples:
    - 这个认证核心改动要做跨模型审，派个 workflow 双引擎对吧
    - 改完 PR2 这项了，要 soundness 审，该怎么走
    - 要两个模型一起审，怎么安排
activation:
  layer_hint: L1
  must_know: false
  reason: 反射派 workflow 审会拉 opus 烧 claude/opus 额度，owner 2026-06-28 明确禁止；审查改走 codex 本地 + GPT Pro relay。
provenance:
  op: record
  reason: owner 2026-06-28 改审查路由：把双模型审里 opus/claude 那侧换成 GPT Pro，省 claude 额度。
  evidence:
    - python cc_memory/mem.py read review-routing-codex-local-then-gptpro-relay --body
updated_at: "2026-06-28"
---
要做 soundness / 认证核心**审查**时（不管是审我自己刚改的，还是审 codex/外审回来的）：**双模型对抗审的原则不变**（两个不同模型各独立审一遍），但那两个模型从 [opus + codex] 改成 **[codex（本地）+ GPT Pro（relay）]**——把 opus/claude 那一侧换成 GPT Pro，因为把审查交给 claude/opus（典型=workflow 挂 opus agent）**也烧 claude 额度**。

标准流程：
1. **本地 codex 先审 + 修**（first pass，省额度、本地快）。
2. **打包 HEAD 快照/diff + 写任务书提示词 → owner relay 上传 GPT Pro 第二遍跨模型审**（替代旧 opus 引擎）。提示词三维不变：干练 + 全覆盖 + 每个 BLOCK 直接要补丁；交付走剪贴板双条（路径+提示词）；GPT Pro 沙盒可直接改文件/出 diff。
3. **审查【绝不派 workflow】**——workflow fan-out 会拉 opus = 烧 claude 额度，正是要省的。「两个模型一起审」= codex 本地 + GPT Pro relay，不是 workflow 双引擎。
4. **claude（我）只编排 + 终裁**：审 GPT Pro/codex 回来的补丁真伪 + 重封 ritual + 全量 preflight（认证核心补丁不管谁写都不盲应用）。这是整合门、不是烧额度的审查跳。

非审查的诊断/砍短 fan-out 仍可用 opus+codex 双引擎（见 cc_memory `workflow-default-multimodel-opus-codex`）；本卡只管**审查**这一用例。
