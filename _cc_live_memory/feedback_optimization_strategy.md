---
name: optimization-strategy
description: 给求解器选优化方向时不能按 ROI 单选，要 stack 所有选项
type: feedback
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---
为终末地工业规划器项目选性能优化方向时，**默认 stack 所有可行方案，而不是按 ROI 单选**。

**Why:** 用户 2026-05-08 明确指出，游戏内容会持续膨胀（70×70 → 80×80，1.0 → 1.2 流水线复杂度 2-3×），实际问题规模指数膨胀。任何单一优化都不足以应对，必须 A+B+C+D 一起上：
- A：solution hint 跨次持久化
- B：decomposition + 长时间 budget
- C：AI ranker 跨问题实例学习
- D：换求解器（CaDiCaL 等）支持持久 learned clauses

之前我判断 D 风险高（怕破坏 proof source lock），但当问题大到现有求解器根本解不出 proof 时，lock 失去意义——这个推理是错的。

**How to apply:**
- 给优化方案对比时，列出**所有**可行选项及其加成关系，不要替用户预先剔除"风险高/成本高"的选项
- 把"难度高、收益不确定"的方案也展示出来，让用户自己决定是否上
- 重点说明各选项之间的协同加成（A+B+C+D 1+1>2）
- 当问题规模会持续增长时，"过度优化"不存在，所有性能空间都值得抓

## 链 (补连 2026-06-01)
- [[avoid-micro-optimization-spiral]] — stack 全上 vs 别钻 micro
- [[phase3c-roadmap]] — 优化项清单
