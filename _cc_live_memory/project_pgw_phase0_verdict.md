---
name: pgw-phase0-verdict
description: "PGW-UB (Path 15) Phase 0 cheap gate ❌ NO-GO 2026-05-19. P0.3 locality signal 0/7 anchor, top5_cov 10x off target (0.046 vs 0.55). 第 21 lever 死. GPT v4 给的'正向 witness + UB closure' framework 在 production data 前提不成立"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

# PGW-UB (Path 15) Phase 0 verdict

## 终态

❌ **P0.3 极强 NO-GO 1h cheap gate**. PGW 主线死, 21 lever 全 verdict.

GPT v4 给的方向 **PGW-UB (Positive Global Witness + UB Closure)** 是 paradigm-level
真不同于 RAB-SEP/SAC-Hull/PCR-CUT (它们全 "local cert + master cut" 框架). 但
Phase 0 cheap gate 在 8 anchor production data 上**前提不成立**.

## 实测 8 anchor

| anchor | blocked_owners | top5_cov | sac |
|---|---|---|---|
| interior_22_28 | 276 | 0.048 | 22 |
| interior_10_10 | 311 | 0.046 | 71 |
| interior_44_30 | 312 | 0.046 | 80 |
| interior_15_40 | 286 | 0.053 | 12 |
| corner_0_0 | (master INFEASIBLE sound) | — | — |
| small_10x10 | 324 | 0.044 | 73 |
| small_15x10 | 327 | 0.046 | 78 |
| small_15x15 | 327 | 0.046 | 77 |

target: blocked ≤120, top5_cov ≥0.55, sac ≤5. 实测全 fail, top5_cov **10x off**.

0/7 eligible anchors 满足任一 P0.3 子条件.

## 数学含义

PGW Phase 2 (Route-aware pinned LNS master) 需要 routing residual **集中**才能
LNS repair. 实测 top 5 blocker owners 只占 **4.6%-5.3% 总压力** — LNS unpin
top-k 改了 5%, 没动剩 95%. 退化成 full master 重 solve, neighborhood 失效.

routing 问题在 production 上是**全图 conjunction** 不是 spatial-cluster local.

## 跟之前 paradigm 比较

| paradigm | end-to-end land | breakthrough | Phase 0 |
|---|---|---|---|
| L12 RAB-SEP | ✅ | ❌ | no Phase 0 |
| L13 SAC-Hull | ✅ | ❌ | GO |
| L14 PCR-CUT | ✅ | ❌ | GO |
| **L15 PGW-UB** | **❌ Phase 0 cheap gate fail** | ❌ | **NO-GO 极强** |

PGW 是**第一个 Phase 0 cheap gate 直接 fail** 的 paradigm. workflow
[[paradigm-phase0-cheap-gate]] 验证有效 — 1h 投入 + 不改 production
就能拿真 verdict, 避免投资 Phase 1-7 ~30h.

## paradigm-level meta-finding (4 paradigm 后)

2 大类 paradigm 都试过死了:

1. **"局部反馈 + master cut"** (RAB-SEP / SAC-Hull / PCR-CUT 3 paradigm)
   - 设计完全不同抽象层 (binding-side / corridor capacity / patch belt CP-SAT)
   - 全 端到端 land ✅, 全 breakthrough ❌
   - root: necessary 不 sufficient, cut 累加切空间但全图 routing-feasibility 始终未达

2. **"正向 witness + UB closure"** (PGW-UB)
   - 不写 cut, 改正向找 witness + master C1 松弛上界闭合
   - Phase 0 cheap gate 前提**直接 fail** (residual 不 local, LNS 失效)
   - root: production data 的 routing residual 全域均匀, 不 spatial-cluster

合起来的 strong evidence — 但还**不**是 formal proof "在当前约束下不可解":
严格 formal proof 需要 GPT 给 reduction / proof system lower bound / resource
inequality, 不是单凭 paradigm 全 fail 能 imply.

## 实测投入

- 整体 wall: ~12 min (8 anchor × 90s avg)
- 实施 LOC: 1 文件 360 LOC trial script (paths/15_positive_global_witness/phase0_pgw_probe.py)
- 总 Claude pace: < 1h (符合 cheap gate workflow)
- commit `a76b4f8`

## 21 lever 全死清单

L1-L16 (前 session 已死) + Path 12 RAB-SEP + Path 13 SAC-Hull + Path 14 PCR-CUT +
**Path 15 PGW-UB** = 21 条全 verdict.

## 下一步候选 (待用户决策, 不主动推)

1. **GPT v5 review**: 把"4 paradigm 撞 2 类 framework 死" + "Phase 0 cheap gate
   workflow 验证 6 次有效" 加进 review 包, 求 GPT 给真新 paradigm 或 formal
   proof. v5 包估 ~1h prep + GPT 1-2 day.
2. **formal unsolvability proof attempt**: 直接让 GPT 给 reduction / proof
   system lower bound (per [[gpt-review-prompt-armor]]). 不准 "I believe".
3. **paradigm investigation 长 pause**: 21 lever 死后 paradigm investigation
   穷尽, 无明确下条路.

## Related

- [[pcr-cut-phase5-verdict]] — Path 14 前 paradigm verdict
- [[paradigm-session-2026-05-18-19]] — 19 lever 总结
- [[paradigm-phase0-cheap-gate]] — workflow 验证 6 次有效
- [[no-giveup-options]] — 不准列放弃选项除非 formal proof
- v4 plan: /home/zhuran24/下载/B1_paradigm_breakthrough_plan_v4.md
- review package: ~/linwin_share/b1_phase6_review_package_v4.zip
