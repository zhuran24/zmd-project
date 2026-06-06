---
name: index-packaging-cluster
description: 打包/外部审查规范的 hub — 串起全簇并标用途. 召回任一打包条 → 这里一次拿全套 (何时打包 / prompt 怎么写 / 包里放什么不放什么 / 怎么压 / 给新窗口 / finding 先 reproduce / GPT 错估分类).
metadata: 
  node_type: memory
  type: reference
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

打包一个外部审查包 (GPT pro / 别窗口) 要用到的规范全在这。按打包流程顺序串:

> **要全套穷尽清单**: 见仓库 `cc_context/review/打包原则_汇总.md` —— 2026-05-31 三源 (memory + build 脚本版本注释 + docs) 去重合成 **10 类** (内容选择 / no-priming / 数据完整性 / 配套 prompt / 打包机制与体积 / 复现性 / 触发时机 / 审查后验证归档 / 门禁 GO 判据 / 沟通新窗口零历史)。本 hub 是 memory 入口, 那份是落地全文。

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

- **交付给谁、附什么** (用户 2026-06-02 定): 送 GPT 复审**只发主包 zip + 贴 prompt 正文, 不再附 deps 块** (`deps_part1/2/3.zip` / `deps_linux_py313.zip`)。v22–v26 一直随包发 3 块离线 wheel (各 ~28MB) 供 reviewer 离线 `pip install` 复现, 但用户判定**以后不用给** (reviewer 自己装/不需跑全环境)。→ 未来 prompt 可删 "deps 分块 cat 合并 + 离线装" 那段 + "包里怎么复现" 的 deps 说明; 交付动作只 SendUserFile 主包 (省 ~84MB 上传 + 手机端少 3 件)。deps 制品仍留 `cc_context/review/deps/` (regenerable, 不删, 只是不再随交付发)。

## 链 (补连 2026-06-01)
- [[review-strategy]] — 项目 3 层审查策略
