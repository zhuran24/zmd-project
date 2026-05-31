---
name: gpt-review-prompt-armor
description: "GPT 外部审查 prompt 要加防 anecdotal verdict 的硬约束: (1) 列死路给 GPT 看防止重复试, (2) 列可接受方向防止花式工程优化, (3) 关键 — 要不可达必须形式化证明 (complexity reduction / proof system lower bound / resource inequality / cite literature), 不准 'I believe / based on my understanding / intuition' 那种 hedge. 实测 L14 起作用了 — GPT 第一次诚实列 caveat 且 caveat 应验."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

## 经验来源

2026-05-16 GPT v3 / v8 / v10 三连错估后, 在 v10 后给 GPT 加料 prompt (要求形式化不可达性证明, 列死路, 列可接受方向). L14 GPT 回复**第一次方向 sound + 诚实列 caveat + caveat 应验**. 加料起作用.

## 加料 prompt 三段式结构

### 段 1: 真瓶颈讲清 (防止 GPT 攻错点)

不只说 "我们求解器卡了", 要展开:
- 项目核心目标是什么 (e.g. 证 max_lex 不是找 incumbent)
- 真瓶颈在哪 (e.g. upper-bound INFEASIBLE 排除而非 candidate FEASIBLE)
- 之前 lever 错在哪 (v3 关注 build / v8 关注 anchor choice / v10 假设有 complete witness — 这些都不是真瓶颈)
- 量化数据 (frontier area 段位 + UNKNOWN 占比 + 资源约束)

### 段 2: 死路 + 可接受方向白名单

明确列:
- "不要再提的方向 (已 verify 死)": 加 hint / 拆 slice / 换 solver flag / 加 worker / build 优化 / RAM 优化 / 等. GPT 看到立刻避开.
- "可接受方向": A 几何 propagator / B dominance argument / C IIS extraction / D paradigm shift / E 诚实承认不可达. 给 GPT 明确 ask 框架.
- 收尾 push: "中间地带 (花式工程优化) 不接受, 我会直接 reject"

### 段 3: 不可达性必须形式化证明 (关键防线)

如果 GPT 选 E (诚实承认不可达), 必须给:
1. **Complexity reduction**: NP-hard / EXPTIME-hard 问题归约到 our setting, 具体构造
2. **Proof system lower bound**: resolution / cutting plane / CP-SAT-specific 下 unsat proof size ≥ 2^k for k 表达 our params, cite Haken / Beame-Pitassi 等
3. **Resource constraint inequality**: 具体 instance 规模 vs hardware 限制的数学不等式
4. **Literature citation**: 已发表 paper 证过 our class problem 的 lower bound

明确拒绝:
- "Based on my understanding..."  — 主观
- "I've seen similar problems..." — anecdotal
- "Intuition says..." — 没 reduction

允许诚实出口: "I cannot provide formal lower bound; this is intuition only" — user 按 intuition 处理, 不当不可达性证据.

## 为啥起作用 (L14 实测)

GPT v3 错估自己 5h 后 audit 推翻 EXACT_POWER_PLACEMENT_SUBPROBLEM 是教训. v8 v10 仍然有 anecdotal hedge.

L14 加料后 GPT:
- 拒绝 declare 不可达 (没法给 formal lower bound, 不下不可达 verdict)
- 给出 proof-carrying weighted occupancy oracle (对准真瓶颈)
- 自己提前列 3 个 failure mode caveat
- 引用真 paper (Clautiaux 2007 generalized energetic reasoning)
- PoC 实测正好 hit caveat #1 — GPT 预言对了

加料起作用的机制: 把 LLM 的 hedge 套话提前 ban 掉, 强迫它要么给 hard evidence 要么显式标 "intuition only". 区分了 GPT 真理解 vs LLM filler.

## 怎么用

下次 GPT review 项目状态前, 把 prompt 按这 3 段结构组装:
1. 真瓶颈 + 数据
2. 死路黑名单 + 可接受方向白名单
3. 不可达必须形式化证明 (列 4 种可接受证明形式 + 3 种不可接受 phrase)

## 链

- [[external-review-reproducibility]] — GPT 全量审查 reproducibility 问题
- [[l14-weighted-occupancy-dead]] — 加料 prompt 起作用的实测
- [[v8-anchor-slicing-dead]], [[v10-witness-preflight-dead]] — 加料前的 baseline 错估
