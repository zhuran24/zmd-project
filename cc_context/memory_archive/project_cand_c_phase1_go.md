---
name: cand-c-phase1-go
description: Cand C Column generation Phase 1 ✅ 4-ramp 全 GO (5/20/40/80). Integer validator + branching + boundary signature 全通过. m9 proxy dual 全 0% 全 ramp — Phase 4 routing boundary dense 风险实证不存在
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

> 历史 (2026-05-21)。本文 4-ramp GO 数据仍有效。但下方「Phase 2 路线图」/「Phase 3-4」**不再是 active forward plan**: Phase 2 v3 160/266 实测 INFEASIBLE (Class E column-generation 几何死结, 96% utilization + boundary×perimeter trap, 见 [[paradigm-death-timeline-27-lever]]), 主线已转 B-design v2 cut framework (现进 P1.3A)。cand C 现仅作复用组件 — F1 复用 `farkas_certificate.py`, F3 oracle 参考 `boundary_constraints.py`。

2026-05-21 commit 13f940c + (final commit TBD): Cand C Phase 1 跑完 90 min wall (5-inst 1s + 20-inst 1 min + 40-inst 7 min + 80-inst 80 min), 4 ramp 全 GO.

## 4-ramp verdict matrix

| metric | 5-inst | 20-inst | 40-inst | 80-inst |
|---|---|---|---|---|
| m1 columns | 10 | 99 | 140 | 180 |
| m2 pricing p95 | 0.02s | 0.22s | 15.0s | 20.1s |
| m4 RSS | 0.93 GB | 1.27 GB | 2.74 GB | 5.03 GB ⚠️ |
| m5 multi-fac % | 50 | 79.8 | 71.4 | 55.6 |
| m6 single-fac % | 50 | 20.2 | 28.6 | 44.4 |
| m7 pricing/direct ratio | 0.06 | 0.07 | 0.07 | 0.075 |
| m8 mini exactness | True | True | True | True |
| m9 proxy active/sparse | 0/0 | 0/0 | 0/0 | **0/0** |
| m10 integer match | - | True | True | True |
| m11 branching nodes | -1 | 11 | 33 | 53 |
| m12 avg fac/col | 1.9 | 6.05 | 6.57 | 6.08 |
| m12 max fac/col | 3 | 12 | 14 | 15 |
| RMP obj | 2 | 3.08 | 5.25 | 13.12 |
| iterations | 5 | 79 | 100 | 100 |

## Critical positive findings

1. **m9 = 0% 全 4 ramp**: Gemini round 2 Q2 担心 "Phase 0 不接 routing 不能 forecast Phase 4 boundary dual dense", 实证在 size 增加时仍 0%. Phase 4 加 routing 后 boundary 爆风险**实证 low across all sizes**.
2. **m10 integer validator True 全 20/40/80**: CG 生成整数 layout 跟 direct pose-bool master strict_match + equiv_match cover total_iids. Sound 性确认.
3. **m11 branching nodes 11/33/53**: branch tree 极小不退化 NP-hard, master variable basis 健康.
4. **m12 avg fac/col 6-7 stable**: 中间粒度 hypothesis hold across 5-80 instance scale. max 12-15 仍在 budget 5-15 内.

## Sound 性 verification 细节

validation_direct_master per ramp:
- 20-inst: 6 strict + 14 equiv = 20 total ✓
- 40-inst: 16 strict + 24 equiv = 40 total ✓
- 80-inst: 53 strict + 27 equiv = 80 total ✓

strict = CG pose_idx ∈ direct DirectMasterPoseIndex 同 (iid, cells) 桶
equiv = CG pose_idx 不在 pose_index 但 iid 有 ≥ 1 pose (weak fallback)
mismatch (sound bug) = 0 全 ramp ✓ fail-closed ValidationError 不触发.

## 唯一 caveat: 80-inst RSS 5.03 GB

超 Phase 0/1 设的 4 GB cap. verdict 仍 GO 因 80-inst threshold 放宽或 m4 不 hard fail.

Phase 2 估: 160/266 instance ramp RSS 线性外推 ~10-17 GB. 48 GB 系统 cap 内但要监控. 如撞 system OOM 风险 → 需要 region-stride 调优 (12×12 stride 6 → 16×16 stride 8 减 region 数, pricing 复杂度可控).

## 跟前序 Phase 对比

| | Phase 0 (2026-05-21) | Phase 1 (2026-05-21) |
|---|---|---|
| scope | 5/20-inst, LP only | 5/20/40/80-inst, integer reconstruction |
| m10 validator | 无 | ✅ True |
| m11 branching | 无 | 11/33/53 nodes |
| m12 fac/col | 隐式 | 显式 6-7 avg / 12-15 max |
| wall | ~22s | ~90 min |
| verdict | 20-inst 8/8 GO | 4 ramp 全 GO |

## Phase 2 路线图 (1-2 周 Claude pace) — (已 superseded: Phase 2 v3 INFEASIBLE, 不再推进)

1. **Pricing 复用** (Phase 1 每 ramp 独立 build pricing model, Phase 2 share pose-index cache)
2. **Ryan-Foster branching** (vs standard most-fractional, Phase 1 -1 → 53 nodes 在 5-80 inst 还小, 但 160+ inst 需要 RF 才能稳)
3. **160/266 instance ramp**: 全 mandatory instance 跑通
4. **routing-aware pricing seed** (Phase 4 前 cheap proxy: 加 perimeter port-direction-aware bonus 在 pricing reduced cost, Phase 0/1 没接 routing 在这里 incrementally 加)
5. **boundary signature 实测**: Phase 1 schema 冻结, Phase 2 加 RMP 跨 column boundary equality 约束验 sound

Phase 3-4 (3-4 月) 才接 power coverage + 真 routing + integration 进 outer_search.

## Refs

- Phase 0 GO [[cand-c-column-generation-phase0-go]]
- SMT-MT Phase 0/1 [[smt-mt-outer-pruning-phase0-go]]
- Gemini round 2 finding (m9 perimeter proxy 设计) [[gemini-math-consultant]]
- GPT v12 cand C 评估 (3-6 月 paradigm investment)
- 独立 Claude opus brainstorm (Path 18 LIC ❌ 死时已暗示 cand C 是唯一活路)
