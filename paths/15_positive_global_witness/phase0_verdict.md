# PGW-UB (Path 15) Phase 0 cheap gate verdict — 2026-05-19

## 结论

❌ **P0.3 极强 NO-GO** — PGW-UB 主线死. 21 lever 全 verdict.

P0.3 (routing residual locality) 在 8 anchor 全部 fail, 不是边缘 fail 是数量级差距:

| 指标 | target | 实测 range | over-target |
|---|---|---|---|
| blocked_owner_count | ≤ 120 | 276 - 327 | **2.3-2.7x off** |
| top5_blocker_coverage | ≥ 0.55 | 0.044 - 0.053 | **10x off** |
| sac_violation_count | ≤ 5 | 12 - 80 | **2.4-16x off** |

`0 / 7 eligible anchors` (corner negative sound master-INFEASIBLE 排除) 满足任一 P0.3 子条件.

## 7 anchor full data

| anchor | outer | blocked | top5_cov | sac |
|---|---|---|---|---|
| interior_22_28 | UNPROVEN 87.8s | 276 | 0.048 | 22 |
| interior_10_10 | UNPROVEN 90.8s | 311 | 0.046 | 71 |
| interior_44_30 | UNPROVEN 90.0s | 312 | 0.046 | 80 |
| interior_15_40 | UNPROVEN 90.6s | 286 | 0.053 | 12 |
| corner_0_0_NEGATIVE | INFEASIBLE 56.1s | (no capture, master infeasible sound) | — | — |
| small_10x10 | UNPROVEN 98.9s | 324 | 0.044 | 73 |
| small_15x10 | UNPROVEN 95.6s | 327 | 0.046 | 78 |
| small_15x15 | UNPROVEN 92.6s | 327 | 0.046 | 77 |

P0.1 (master C1-feasible 7/8 + corner negative INFEASIBLE 1/8) partial GO, 但 caveat:
**Phase 0 only checks "UB_C1 candidates exist", NOT "UB closes to OPT(F)"**. 真闭合需要 Phase 1+ 找 witness.

## 数学含义 — 为啥 P0.3 fail 等于 PGW 死

PGW-UB Phase 2 (Route-aware pinned LNS master) 的硬前提是: **routing residual 集中**, top blocked cluster 占大部分压力, LNS 只 unpin top-k 个 owners 重 solve 就 expected 修复.

实测**前 5 大 blocker owners 只占总 blocker 量 4.6%-5.3%** — 即 top 5 改了不动剩下 94.7% 压力. 要 unpin 50%+ blocker 必须 unpin ~120-150 owners, **退化成 full master 重 solve**. LNS neighborhood 失效.

跟 Path 11 (架构改: 真 enumerate 10 layout 全 INFEASIBLE) 同质 — 全图 routing residual 是**全域均匀的**, 不是 spatial-local.

## 跟之前 paradigm 比较

| paradigm | end-to-end | breakthrough | Phase 0 cheap gate verdict |
|---|---|---|---|
| Path 12 RAB-SEP (local cert + cut) | ✅ | ❌ | (no Phase 0, 直接 Phase 1) |
| Path 13 SAC-Hull (global capacity + L2) | ✅ | ❌ | GO (22 violations) |
| Path 14 PCR-CUT (patch belt CP-SAT + cut) | ✅ | ❌ | GO (770 cells cover 98%) |
| **Path 15 PGW-UB (positive witness + UB)** | ❌ | ❌ | **NO-GO 极强 (P0.3 10x off)** |

PGW 是第一个 Phase 0 cheap gate 直接 fail 的 paradigm — paradigm 设计本身依赖的前提**在 production data 上根本不成立**.

## 实测投入

- 整体 wall: ~12 min (8 anchor × 90s avg)
- 实施 LOC: 1 文件 360 LOC trial script (没改 production)
- 总 Claude pace: < 1h (符合 cheap gate workflow)

## 关于 Plan B fallback

v4 plan 给的 fallback 选项分析:

| fallback | 适用条件 | 实测可用 |
|---|---|---|
| Plan B-UB (UB 未闭合 → lower-bound only) | P0.1 fail | P0.1 partial GO, 不适用 |
| Plan B-self-seed (community hint 0 兼容) | P0.2 fail | P0.3 fail 不是 seed 问题 |
| Plan B-route-skeleton-soft | layout repair 有改善但 routing 仍败 | **前提是 P0.3 GO 才能进 Phase 2**, 不适用 |
| Plan B-abort | 所有正向 witness 失败 | **当前命中** |

Phase 0 P0.3 fail 直接命中 Plan B-abort.

## 实际意义

PGW-UB 是 v4 plan 给的 **第一个完全不同于 "local cert + master cut" 的 paradigm**. 它 fail 加上之前 3 paradigm (RAB-SEP / SAC-Hull / PCR-CUT) 全 fail, 整体 framework:

1. **"局部反馈 + master cut"** — 3 paradigm 实测同墙 (necessary 不 sufficient)
2. **"正向 witness + UB closure"** — Phase 0 cheap gate 在 production data 上前提不成立

两大类 paradigm 都试过死了, 离 formal proof "在当前约束下不可解" 又近一步. 但严格 formal proof 仍需 GPT 给出 reduction / lower bound — 不是单凭 paradigm 全 fail 就能 imply.

## commit

phase 0 trial: TBD (本 commit 落 Phase 0 results)

## Related

- v4 plan: `<external-local-input>/B1_paradigm_breakthrough_plan_v4.md`
- review package: `~/linwin_share/b1_phase6_review_package_v4.zip`
- review prompt: `~/linwin_share/b1_phase6_review_prompt_v4.md`
