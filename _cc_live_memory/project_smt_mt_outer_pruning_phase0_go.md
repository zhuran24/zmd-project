---
name: smt-mt-outer-pruning-phase0-go
description: "SMT Modulo Monotonic Theories outer pruning Phase 0 ✅ GO — 项目第一个 GO verdict (24+3 lever 全 NO-GO 后), prune 76.7% candidate, 跟 cand C orthogonal stack"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-21 commit aa350f5: Gemini 3.1 pro round 2 sanity check 推荐的方向 — 利用 ghost rect monotone property 在 outer 做 candidate registry 批量剪枝.

## Monotone property

ghost_A INFEASIBLE → 任何几何上 cover ghost_A 的 ghost_B 必然 INFEASIBLE (空地更大 → facility 可用 grid 更小 → 更不可能 fit).

Outer 收到内层 INFEASIBLE 时, R-tree containment query 找所有 cover ghost_A 的 candidate, 全 mark INFEASIBLE 不重跑.

## Phase 0 实测 (Dummy Inner Solver: area≥500 INFEASIBLE)

| metric | 实测 | threshold | 判定 |
|---|---|---|---|
| m1 total candidates | 2,347,345 (比 spec 10K 大 2 数量级因 anchor 让 size × position blow up) | — | — |
| m2 prune_ratio | **76.7%** (1,799,267 pruned / 2,347,345 total) | ≥ 50% | ✅ |
| m3 query p95 | 293ms | ≤ 1s | ✅ (接近上限, p99=329ms) |
| m4 R-tree build | 38.6s | ≤ 60s | ✅ |
| m5 RSS delta / abs | 0.43 GB / 0.65 GB | ≤ 2 GB | ✅ |
| total wall | 129s (build 38.6s + 1000 trial loop 90s) | — | — |

464 INFEASIBLE trials 触发 prune 1.8M candidate. **1 trial 平均剪 3877 candidate**, amortize 极高效.

## m6 prune by area bucket — 完美 monotone

| area | total | pruned | ratio |
|---|---|---|---|
| ≥ 2000 | 136,210 | 136,210 | **100%** |
| 1000-1999 | 465,144 | 465,137 | 99.998% |
| 500-999 | 644,179 | 644,122 | 99.99% |
| 200-499 | 734,108 | 538,292 | 73.3% |
| < 200 | 367,704 | 15,506 | **4.2%** |

完美 monotone: 大 area 被剪光 (Dummy area≥500 全 INFEASIBLE), 小 area 不被剪 (ghost_A 小 ⊄ ghost_B 大).

## Verdict

**第 28 lever 第一个 GO ✅**. 24 lever + path 18 + lever 25 IHS + lever 26 Benders symm 全 NO-GO 后, SMT-MT 是项目当前唯一活的方向之一.

## 关键 caveat (Phase 1 production 前必 verify)

1. **Dummy Inner Solver vs real**: Dummy area≥500 全 INFEASIBLE. 真 inner (cand C / B1 LBBD) 返 INFEASIBLE 频率取决于 problem geometry. 实际 prune ratio 可能更低 (但仍有意义).
2. **query p95 293ms 接近 1s 上限**: 10K candidate × 300ms overhead ≈ 50 min wall acceptable but not great. Phase 1 production wire 前考虑 R-tree leaf_capacity / fill_factor 调优.
3. **Wire 进 outer_search.py 需改 src**: Phase 0 用 Dummy mock, Phase 1 接 benders_loop 返 INFEASIBLE 后调 monotone prune callback. PROJECT_LOCK 边界不破 (outer 是 enumeration 不是 proof).
4. **不替代 cand C / B1 等 inner solver**: SMT-MT 是 orthogonal speedup, 不是 paradigm replacement. cand C / future inner verdict 仍要靠真 LBBD 跑.

## 跟 cand C 关系

- SMT-MT: outer candidate registry monotone pruning
- cand C: inner LBBD master variable basis replacement
- **不冲突, 可 stack**: SMT-MT 减 outer candidate 数, cand C 加速 inner per-candidate. 两条独立 ROI 都成立.

## Next

1. Phase 1: wire 进 outer_search.py (R-tree build 启动 + INFEASIBLE callback 触发 prune + telemetry)
2. Phase 2: 真 inner solver (B1 / cand C) 跑 5-10 candidate, 测真 prune ratio
3. 估总工时: Phase 1-2 1-2 周 Claude pace

[[gemini-math-consultant]] Gemini round 2 finding 落地实测 GO, fat-context 设计起作用.

## Reference

- Bayless, Bayless, Hoos, Hu — "SAT Modulo Monotonic Theories", AAAI 2015
- rtree 1.4.1 (libspatialindex C++ wrapper, no venv conflict)
