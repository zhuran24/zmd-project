---
name: memory-tree-structural-health
description: "记忆树结构健康 (区别于 [[memory-currency-protocol]] 的内容现状轴): wikilink 命名须统一口径否则断链 + MEMORY.md ~24576B 自动加载上限超了尾部静默截断 + harness 重写 frontmatter 但保 name 字段→rename 耐久 + 维护脚本语义 + **第三轴: 同话题散多条 memory 没跨链 → 改不全(改一漏多)+召不全(该用的没 surface), 治法=改前 grep 全树找全实例一起改 + 同话题簇互相 wikilink + description 带共同话题词**。"
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

## 第三个失效轴: 同话题散在多条 memory 没跨链 (2026-06-02 用户 catch)

同一情况/规则常散在**多条** memory。它们若没好好互相 wikilink, 两个失效, 都已实证复发:
- **改不全 (write 时)**: 改正一条、漏掉同话题其它条 = 假修。实例: "≤29MB 是下载安全线"这个未验证幻觉散在 SendUserFile 段 + pitfalls description + handoff 三处, 我第一次"修"只改了一处 (用户 catch)。
- **召不全 (read 时)**: 召回一条、没拉进同簇其它条 → 该用的规则没 surface。实例: "修完再审直到 clean" 记在 [[gemini-review-algorithm-math]] §循环规则 (Gemini 语境), 但没连 [[verification-independent-backstop]]/[[audit-verify-before-archive]]; 我跑 GPT-review workflow loop 时没想起它 → 同问题复发 (用户 2026-06-02 第二次 catch)。

**协议 (两手都要 —— 别只靠被动 recall: recall 按 description 匹配注入、不自动顺着 wikilink 走)**:
1. **改/记一条 memory 前, 先 grep 该话题关键词跨全树**找所有实例 (不只手头那条), 全部一起改/对齐 —— 这是 [[verification-independent-backstop]] 的"完整性"用到 memory 编辑本身 ("修就修全, 别只改手头一处")。
2. **同话题簇必互相 wikilink** (双方括号包对方 slug) 双向互指, 让改一条能顺链到同簇、召一条能拉同簇。
3. **clustered memory 的 description 带共同话题词**, 让同簇在 recall 时倾向 co-surface (description 是 recall 匹配面)。
4. 周期性 (大 review / phase boundary) 跑**簇连通审计** (可派 workflow, 主体=记忆树): 找"同话题但互不 link"的 memory 对, 补链。这跟 `report_link_graph.py` 查的"断链/孤点"是不同轴 —— 那查 link 解不解析, 这查**该有的 link 缺没缺**。

**How to apply**: 周期性 (phase boundary / 大 review 前) 跑 `report_link_graph.py` 查连通 + 看 MEMORY.md 字节数 + 按上面协议查同话题簇缺链。加索引条前先 slim。改/记 memory 前 grep 全树找同话题所有实例一起改。关联 [[memory-currency-protocol]] (内容轴, 互补) [[verification-independent-backstop]] (完整性 → 改全) [[github-backup]] [[memory-edit-confirmation]]。
