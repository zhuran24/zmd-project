---
name: subproblem-vs-augmented-master-default
description: "我 implementation 时默认走 LBBD sub-problem pattern (PCR-CUT/SAC-Hull L2/RAB-SEP 都是), 不动 master architecture. 但用户给的'放 wall'类指示通常意指 augmented master, 不是 sub-problem budget. 2026-05-20 Path 17 D2 上踩过 — 600s wall user 意指 augmented master, 我做 sub-problem 0.15s 完, 600s 完全没用上"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

# Sub-problem vs augmented master 默认偏见

**Rule**: 用户给 "放 wall budget" / "扩 master" / "放约束" 类指示时, **不要自动
默认走 LBBD sub-problem 路线**. 先 confirm 用户意图是 sub-problem 还是
augmented master (内置 vars 进 master).

**Why**:
- LBBD sub-problem 是 PCR-CUT / SAC-Hull L2 / RAB-SEP 标准 pattern, 我有
  implementation 惯性
- 不动 master architecture 实施门槛低 (3-6h vs 6-10h)
- 但用户讨论 "放 wall budget" 时, 通常意指 master 在 budget 内能 solve
  (augmented), 不是 sub-problem 自身 budget
- 2026-05-20 Path 17 D2 上踩过: 用户说 wall 600s 解锁 Candidate D, 我做了
  sub-problem 实施, **600s wall 完全没用上** (master 100s OK, sub-problem 0.15s
  完). 用户 sharp 抓出: "这个 600s 条件依旧用的是 Path 01 pose-bool master
  算法吗"
- paradigm investigation 价值: sub-problem 路线 cut 表达力被 master pose-bool
  卡死, 6 paradigm 全撞同墙. augmented master 真换 master form, 才能验
  Proposition 2 是否 imply 全死. 默认 sub-problem 让 augmented 路径**没真测**

**How to apply**:

1. **用户给 wall budget 放开 / vars 放开 / 资源放开 类指示时**:
   - **先 confirm 走 sub-problem 还是 augmented master**
   - 不要自动 default 到 sub-problem
   - 列两种方案 ROI 让用户挑

2. **看 user 用语线索**:
   - "**放开 wall**" 或 "**让 master 多想**" → 多半是 augmented master
   - "**给 sub-problem 多时间**" → sub-problem
   - "**解锁 paradigm X 试**" → 看 X 设计本身, 如果含 master vars (Candidate
     D u/e vars, port_active vars) → augmented master; 如果是 cert/cut form
     (RAB-SEP cert, PCR-CUT patch core) → sub-problem

3. **写实施 plan 前明确 paradigm structure**:
   - vars 是不是加进 master?
   - LBBD loop 怎么走 (master → sub-problem → cut → master 还是 master 自己 search)?
   - cut form 在哪 (master internal constraint vs reflection from sub-problem)?

4. **判断 cut framework 是不是同质死法**:
   - sub-problem 路线 cut form 必落 master pose-bool 维度 (instance-pose
     conjunction). 6 paradigm 全死.
   - augmented master 不依赖 cut, master 自己 search. **跟 cut framework 不同
     dimension**. 不能直接用 sub-problem 死法推 augmented master 也会死.

**反例 (2026-05-20 Path 17 D2)**:

User context (review v6+v7 后): 5 paradigm + 23 lever 全 verdict 死. user 提
hypothesis: pose-bool master 是隐含原因. 讨论时说 "放 60s 到 600s 解锁 Candidate D".

我 implementation:
- 写 sub-problem (Path 17 D2 paradigm)
- master 仍 pose-bool 180s baseline
- sub-problem budget 30s, 实测 0.15s 完
- **600s wall 没用上**

User 在 Phase 2 verdict 后 sharp 抓:
> "这个 600s 的条件依旧用的是 Path 01 pose-bool master 的算法吗"

正确做法应该是: implementation 前 explicit 跟 user confirm "augmented master
(master 内置 D2 vars) 还是 sub-problem (D2 后台跑)". 用户当时讨论 Candidate D
跟 wall 时, 应该是 augmented master 意图 (因为 wall 600s 是 master budget, 不
是 sub-problem budget).

**适用**:
- 任何 paradigm investigation 实施前
- 任何 master 资源放开类指示
- 任何 user 提"换 master form" / "扩 master vars" 类讨论

**不适用**:
- 纯 cut form / signature lifting 调整 (sub-problem 范畴内)
- env knob 调整 (timeout / worker count 等)
- 测试新 paradigm 设计本身 (paradigm sub-problem vs augmented 由 GPT plan
  数学描述确定)

**Related**:
- [[augmented-master-candidate-d-pickup]] — next session 起跑
- [[d2-path17-verdict]] — 实测 sub-problem 死
- [[clarity-over-brevity]] — 用 confirm 而非默认假设
- [[paradigm-phase0-cheap-gate]] — phase 0 验前提
