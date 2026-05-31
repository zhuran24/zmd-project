---
name: lever25-ihs-dead
description: "GPT v12 lever 25 IHS Phase 0 实测 NO-GO: 10/10 cut size=1, offline HS compression=1.0, IHS 跟 LBBD 用同 oracle 同质退化. GPT 自评 70% NO-GO 应验"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-20 commit 7f0756f: GPT v12 review 包给的 4 个 alive 候选之 3. Implicit Hitting Set (IHS) architecture: 外部 core store + 跑 minimum hitting set ILP 算 cut, 不在 master 直接 accumulate.

## Phase 0 实测 (anchor 22,28 27×15, B1 + PCR-CUT active)

| metric | 实测 | threshold | 判定 |
|---|---|---|---|
| m1 core size p50 | **1.0** | ≥ 3 (Stage 1 GO) | ❌ |
| m1 pct size = 1 | **100%** (10/10) | < 80% (Stage 1 GO) | ❌ |
| m1 distribution | {1: 10} 全 size=1 | — | — |
| m4 final status | UNPROVEN | CERTIFIED/INFEASIBLE | ❌ |
| LBBD wall | 593s (10 iter 完整跑完) | — | — |
| offline HS compression (Stage 2 vestigial) | **1.0** (hs_size=10 = union_size=10) | < 1.0 | ❌ |

Stage 1 NO-GO → Stage 2 ineligible. 但 probe 跑完整 10 iter (没 mid-flight abort), offline HS 数据 also 出来 — compression=1.0 confirm IHS 跟 LBBD 完全等价 (HS = union 退化 union-of-singletons).

## Core finding

**IHS 用同一 oracle (master + binding + routing precheck via PCR-CUT) 抽出来的 core 仍是 size=1 退化 pose no-good**. 跟 Path 17 D2 (verdict 死时 core size 全 1) + Path 14 PCR-CUT (cut all single pose) + Path 12 RAB-SEP 完全同症状.

这正是 GPT v12 自己 self-flag 的 caveat: "如果 oracle 给的 core 是 `{x_instance_pose}` 或少量 conjunction, 那么 hitting set 只是在 pose literals 上做覆盖". GPT 自评 NO-GO 概率 ~70%, 实测应验.

**结构性原因**: 项目所有现有 cut path (PCR-CUT / SAC-Hull / D2 / RAB-SEP) 产 size=1 core 是 pose-bool master + routing precheck 死法的**结构性**事实, 不是 separator 设计问题. IHS 这种 cut accumulation 方式调换不解决 cut 本身 expressiveness 问题.

## Verdict

**第 27 lever 死**. GPT v12 lever 25 进 dead lever list. Infrastructure (class-level monkey-patch + CP-SAT minimum hitting set ILP + offline batch mode) 留作 future reference.

## 三连 Phase 0 NO-GO 模式总结 (2026-05-20)

24 lever verdict 死后跑 3 个独立 Phase 0:
1. **Lever 26 Benders symmetry** (GPT v12): symmetry 被 ghost/boundary/port_dir 打碎, m5=1.0
2. **Path 18 layout-invariant cert** (独立 Claude brainstorm): cell-front 几乎决定 pose, m1=2
3. **Lever 25 IHS** (GPT v12): core size 全=1, HS 退化 union

**共同 root cause**: 项目几何 high-resolution (266 facility × 70×70 grid × port direction × ghost anchor × boundary mask) **结构性**打碎了所有 sub-pose-level 等价性 / symmetry / amplification. **Cut 强度 / cut accumulation 设计 / cut family 抽象 这三个 axis 上都没 free lunch**. 必须从 cut 之外的 axis 攻 (master variable basis / problem reformulation / heuristic + verify pipeline / scope reset).

## Next: GPT v12 剩 2 候选

- cand C **Column generation / branch-and-price** (3-6 月, **唯一真换 master variable basis**)
- cand A **CDCL warm-start** (1 周, hint 类已死过, GPT 自评低优先级)

或 paradigm shift (e.g. heuristic + replay validator separation) / scope reset / 独立 Claude Plan B "Candidate-batch shared cut pool" (但 cut 表达 axis 已三死, F 方向也 high-risk).

用户决策.

## 链 (补连 2026-06-01)
- [[paradigm-death-timeline-27-lever]] — 本条是 27 lever 之一
