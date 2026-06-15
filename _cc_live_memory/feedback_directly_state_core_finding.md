---
name: directly-state-core-finding
index_summary: "第一句给结论+真问题定位. 不准先列 A/B/C 选项让用户选."
description: 报告状态/问题/分析时, 直接讲核心定位 + 数据, 不要先列 menu 选项让用户提问"再用人话讲一遍"——浪费 turn + 用户挫败
type: feedback
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---
报告状态 / 问题 / 分析时, **第一段直接讲核心 finding + 真正定位**, 不要：
- 先列 A/B/C 选项让用户选
- 用术语 + 表格堆数据但回避"所以问题在哪"的结论
- 等用户问"用人话解释一遍"再说核心

**Why:** 用户反馈"以后说话最好能直接这样子说不用我再问一下说什么用人话解释一遍"
(2026-05-11 P2 #14 dumper 卡 boundary precheck 那次). 当时我先列了 candidate 状态表格 + ABC 选项 → 用户问"用人话讲讲" → 我才说出真核心 "boundary precheck 到 master 之间有个判断让 outer return UNKNOWN, 要 debug outer_search 源码".

应该一开始就是: "现在卡在 X 位置, 真问题是 Y, 因为 Z. 选项 A1/A2..."

**How to apply:**

- 调研 / debug / 状态报告: 第一句直接说 "卡在 X" / "bug 在 Y" / "已 verify Z" 等结论性陈述
- 数据表格只作为支撑结论的证据, 不替代结论
- 选项 menu 放在结论 + finding 之后, 不放在前面
- 如果有不确定性, 直接说"不确定 X / Y, 倾向 Z" 而不是"看你怎么选"

## 链 (补连 2026-06-02 连通审计 whcb890zi)
- [[clarity-over-brevity]] — 互补对(结论先讲+展开), 单独召会半对
