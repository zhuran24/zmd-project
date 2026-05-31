---
name: index-packaging-cluster
description: 打包/外部审查规范的 hub — 串起全簇并标用途. 召回任一打包条 → 这里一次拿全套 (何时打包 / prompt 怎么写 / 包里放什么不放什么 / 怎么压 / 给新窗口 / finding 先 reproduce / GPT 错估分类).
metadata: 
  node_type: memory
  type: reference
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

打包一个外部审查包 (GPT pro / 别窗口) 要用到的规范全在这。按打包流程顺序串:

- **何时打包**: 大节点结束 → [[big-milestone-gpt-pro-review]] (Phase 1.0/1.1/.../ramp / paradigm shift)。

- **prompt 怎么写**: 7-section 结构 [[external-review-prompt-template]] + armor 三件套 ——
  - [[gpt-review-prompt-armor]] (真瓶颈 + 死路黑名单 + 不可达必须形式化证明)
  - [[gpt-review-no-history]] (新窗口零历史, prompt/包不准引用上次 GPT 输出)
  - [[no-role-priming-for-reasoning-models]] (不要「你是 X 专家」催眠前缀, 直接讲任务+format+约束)

- **包里放什么 / 不放什么**:
  - [[review-pkg-no-prompt-inside]] (zip 只放纯事实素材; **不放** prompt + 主动性内容/verdict claim/审查指引; 唯一例外: spike code / reproducer 等作 **code_context / review-only mirror** 非 master, 定向标注)
  - [[review-pkg-data-completeness]] (与上条互补: 禁主动性 priming 的同时要 factual 完整 —— spike code / Gemini archive / raw telemetry / reproducer 全入)

- **怎么压**: [[review-pkg-7z-strategy]] (全项目 scope 用 7z -mx=9, zip 壳含 project.7z + tools/7za + README; 本机无 7z 时单层 zip)。

- **给新窗口 reviewer**: [[review-package-for-new-window]] (README 不带 carry-forward 历史, standalone 极简点指引)。

- **收到 finding 先 reproduce**: [[audit-verify-before-archive]] (NOT GO + finding 也必 specific reproduce 全 pass 才 archive) + [[external-review-reproducibility]] (同 prompt 跑两次 finding 列表可能不同, 多次报告交叉信, sandbox 链接会过期立刻 cp 副本)。

- **GPT 错估分类** (收到 verdict 后判属哪类): [[gpt-error-types-taxonomy]] (算法错估 push / 前提错估 push / 数学能力上限 承认 paradigm 限制)。

## 链 (补连 2026-06-01)
- [[review-strategy]] — 项目 3 层审查策略
