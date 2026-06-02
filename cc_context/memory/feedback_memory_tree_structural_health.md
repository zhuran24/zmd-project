---
name: memory-tree-structural-health
description: "记忆树结构健康 (区别于 [[memory-currency-protocol]] 的内容现状轴): wikilink 命名须统一口径否则断链 + MEMORY.md ~24576B 自动加载上限超了尾部静默截断 + harness 重写 frontmatter 但保 name 字段→rename 耐久 + 维护脚本语义。"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

记忆树会"结构性"坏掉 —— 这是跟 [[memory-currency-protocol]] (内容过时轴) **不同的失效轴**, 内容再新, link 断了 / 尾部被截一样废。2026-06-01 梳理时治的就是这层。

## 两个硬机制

1. **wikilink (双方括号包 `name` slug) 命名必须统一一套口径才能解析**。曾三套并存 (剥前缀 / 留 `feedback-` 前缀 / 中文名) → 断链 192、孤点 63。归一为**剥前缀**后 434/434 resolved、孤点 0。维护时新加 link 一律用剥前缀的 `name:` slug。

2. **MEMORY.md 在 ~24KB 附近尾部条目开始不进上下文** (经验阈值 ≈ 24576B=24×1024, **未见 harness 文档, 来自实测推断, 别当文档化硬上限**)。观察: 33396B 时尾部约 33 条 (#85–#117, 含打包规范) 不在 context。**"打包规范召不回"的最佳推断主因是尾部截断** —— 但当时**同期**还有断链 192/孤点 63, 而修复是 slim+重排+重连**一起做的**, 没做对照隔离, 所以"截断是主因"是强推断**不是证实结论** (同 [[no-causal-claim-from-n1]] 那类 N=1 因果, 别说死)。无论真因是哪种, 下面的操作规则都成立。
   - **瘦身**: 超长索引条砍到 <120 字符; 分 6 段重排, **当前状态/打包规范放最前 (永不截), paradigm 死路史放最后 (要截只截低价值历史)**。
   - **headroom 红线**: slim 到 ~23366B 后, 每加一条索引就涨回上限 (24070B 时只剩 ~506B)。**加索引前必先 slim 一条旧的**, 否则尾部重新被截。

## harness 交互 + 维护工具

- **CC harness 写 memory 时会重写 frontmatter** (加 `originSessionId`, 偶尔搞坏某文件需手修), 但**归一后的 `name:` 字段被保留 → rename 耐久**, 不会被 harness 冲掉。
- 维护脚本在 `cc_context/tools/` (相对路径, 别用绝对): `normalize_memory_links.py` (命名归一)、`report_link_graph.py` (健康报告: 文件数/link 数/resolved/孤点)、`deorphan_links.py` (补连, 校验目标存在 + 去重 + fail-closed)、`extract_session_turns.py` (抽对话当 backstop 主体)。

**How to apply**: 周期性 (phase boundary / 大 review 前) 跑 `report_link_graph.py` 查连通 + 看 MEMORY.md 字节数。加索引条前先 slim。关联 [[memory-currency-protocol]] (内容轴, 互补) [[github-backup]] (备份机制) [[memory-edit-confirmation]]。
