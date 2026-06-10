---
name: plan-doc-strategic-layers
description: 计划书 ≠ 执行书. plan doc 必含 战略/上下文/数学原理/设计哲学/paradigm 决策/历史回顾/GO 标准/依赖图/风险 mitigation, 不只列 commit-level TODO. 用户原话验证.
metadata:
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-23 用户原话两次:
1. "他完全不对劲呀, 感觉少了很多东西, 不像计划书更像执行书"
2. "全部东西放进计划书里面, 一个都不要拉! 全部内容都放一个文件里面, 格式做好"

## 错误模式 — TODO 列表当 plan doc

我初版 PHASE_POST_1_1_REFACTOR_PLAN.md 写成 commit-level TODO:
- 现状闭环 ✓
- 死路 baseline ✓
- Phase 1.2 入门 7 项 factual fix (具体每项做什么)
- Phase 1.2 5 family 实施 (各 family 文件位置 + 复用 helper)
- Phase 1.3 perf opt (具体 perf 项)
- Phase 1.5+ production integration
- 排期估算 + open questions + PROJECT_LOCK 边界

用户视角: 像 sprint backlog. 跳过 "为什么" 直接到 "做什么".

## plan doc 该有的 (strategic layers)

计划书的全面性 — 看完知道:
1. **战略 / 上下文** — 为啥需要这事? 解决什么瓶颈? 跟项目其他部分关系?
2. **设计哲学 + 核心 invariants** — 数学 / 结构选择背后的 why
3. **核心数学原理** — 关键算法 / 定理 / 形式系统的根据 (Menger / Hall / pigeonhole / LP / NP-hard / etc)
4. **paradigm 决策 + 死路分析** — 选这 paradigm 不选别的, 跟死路的边界
5. **历史回顾** — 怎么走到当前, 每步什么 finding 驱动
6. **现状细则** — 当前 闭环 / gate / 测试状态
7. **GO 标准 / 验收准则** — 每段 done 怎么定义 (test count / audit verdict /
   metric improve / 不只 "代码 commit pass")
8. **依赖图** — 内部 dependency / phase 间 dependency / 关键 ordering
9. **实施细则** — 文件位置 / 复用 / 风险 / mitigation (这是原 TODO 段, 不是
   plan 全部)
10. **风险 + mitigation + 回滚** — defer 排序 + 每条 risk 减少策略 + 失败回滚
11. **Open questions** — 待定决策点
12. **边界 invariant** — PROJECT_LOCK 等不能跨

## 关键区分

| 执行书 | 计划书 |
|---|---|
| 做什么 (TODO list) | 为什么 + 怎么做 + 做到什么程度 + 走偏怎么回头 |
| commit-level granularity | strategy + tactic + audit checkpoint |
| sprint backlog | living roadmap |
| 给 implementer 看 | 给 reviewer / future maintainer / 外部 audit 看 |

## Apply when

写任何 phase plan / roadmap / 大项目计划:
- 不只列 TODO. 写完后问: 看完知道为啥这么做吗? 知道哪段 done? 知道走偏怎么回头?
- 数学算法 / 复杂决策需含数学原理段
- 大节点 (phase boundary) 必写 GO 标准
- 依赖图防错 order

## Refs

- `docs/research/p3_b_design_v2_20260521/PHASE_POST_1_1_REFACTOR_PLAN.md`
  最终版 — 18 section / 1363 line / 54 KB, 含完整 13 数学原理 subsection
  + 战略 + paradigm + 历史 + GO 标准 + 依赖图 + 风险 + 回滚 + 边界 invariant
- review-pkg-no-prompt-inside — plan/roadmap doc 不放 review pkg
  (引导 reviewer 反 falsification)
