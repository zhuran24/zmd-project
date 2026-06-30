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
2. **打包【完整 HEAD 快照包】+ 写任务书提示词 → owner relay 上传 GPT Pro 第二遍跨模型审**（替代旧 opus 引擎）。**包用 `scripts/package_review_snapshot.py` 出全源码树 .7z（含内嵌自测收据）——给完整包、绝不给 diff**（reviewer 要完整上下文才审得透；不管记忆/旧惯例/审查质量都是完整包，owner 2026-06-29 纠）。**写提示词前先 `python cc_memory/mem.py search`（review-prompt / deliverable-text-lean / clipboard-relay / relay）+ 重读本卡——别凭会话印象套（这条最常翻车，已五次；2026-06-30 r5 relay 又凭压缩后印象写、把③要求的"具体补丁"漂成"补丁方向"，owner 抓出）。** 提示词纪律：① **lean 且【绝不剧透我的分析/结论】**——写"漏洞机制是 X / 我判断它 sound 因为 Y / 这是死分支无递归"= 把 reviewer 往附和我上带、破坏盲审独立性；intro 只点"审什么 + 怎么审（默认怀疑、逐行对源）"，把"原缺口/改动是啥"中性描述清楚即可，**结论与机制判定留给 reviewer 独立得出**（中性问句："独立判定 X 是否成立"，别写成"X 不成立，请确认"）；② 全覆盖（每维度 CLEAN/CONCERN/BLOCK + 别 stop-at-first 别裸 STOP）；③ 每个 BLOCK 直接要补丁（根因 + 文件:行 + 不弱化 + reseal 影响面 + 守 PR1/PR2 边界）。交付走剪贴板（包名带 hash 唯一 + 提示词点名该包）：**单提示词=双条**（路径 + 提示词）；**panel 多份提示词=多条 Win+V**（包路径 + 每条提示词各一条，每条自包含=标识头+共享头+一份提示词；owner 2026-06-29 纠"不是像以前那样只双条"）。GPT Pro 沙盒可直接改文件/出 diff。**真 relay 出去那一刻当场把"发了什么包/在等什么"记进 cc_memory / 当前 RESUME（打包≠已发送、发出状态会被压缩丢）。**
2b. **GPT Pro 可多会话并行 → 写多份【不同角度】提示词（perspective-diverse panel）**（owner 2026-06-28）：GPT Pro 网页端能同时开多个会话，所以像旧 workflow"多模型从不同角度审"那样，对同一批改动**写多份镜头不同的提示词**（典型：红队/绕过 · 完整性/reseal · 不变量回归 各一份，每份覆盖全部改动但视角不同），分发到并行会话——不同镜头抓不同失效模式=提质，并行非串行=提效，补回单 GPT Pro 丢掉的多视角覆盖（≈旧"3 独立 blind reviewer"）。份数按改动规模定（小改 2-3 份够）。审回后我 union + 去重 + 逐条 triage/验证。**panel 组成 = 多份【分角度】prompts + 1 份【全角度综合审】**（owner 2026-06-29 加）：除红队/绕过 · reseal · 不变量 这些分角度外，**另配一份单会话全维度审**（一个会话里把全部维度逐项 CLEAN/CONCERN/BLOCK + 末尾全局判，像旧单引擎全维度审那样写）；分角度抓深、全角度兜全，两者都要。
3. **审查【绝不派 workflow】**——workflow fan-out 会拉 opus = 烧 claude 额度，正是要省的。「两个模型一起审」= codex 本地 + GPT Pro relay，不是 workflow 双引擎。
4. **claude（我）只编排 + 终裁**：审 GPT Pro/codex 回来的补丁真伪 + 重封 ritual + 全量 preflight（认证核心补丁不管谁写都不盲应用）。这是整合门、不是烧额度的审查跳。

非审查的诊断/砍短 fan-out 仍可用 opus+codex 双引擎（见 cc_memory `workflow-default-multimodel-opus-codex`）；本卡只管**审查**这一用例。
