---
name: smt-mt-phase1-marginal
description: "SMT-MT outer pruning Phase 1 production trial verdict ⚠️ marginal: 真 inner B1 LBBD 5 iter UNPROVEN → 仅 9 INFEASIBLE notify → prune 9/1196 = 0.75% (vs Phase 0 mock 76.7%). src 改动 land env-gated default off, 留作未来 inner solver 改进后自动 unlock"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-21 commit 3d36018: SMT-MT Phase 1 production trial 实测 verdict 比 Phase 0 mock 弱 100x. **不是死路, 是 ROI 评估比 mock 低**.

## Phase 0 mock vs Phase 1 production 对比

| metric | Phase 0 mock | Phase 1 real | 倍率 |
|---|---|---|---|
| candidate pool | 2.35M (positional 4-tuple) | 1196 (production size-only 2-tuple) | -1965x |
| INFEASIBLE trigger | 464 (random area≥500) | 9 (mandatory_rect_precheck 70xH series) | -52x |
| 平均 prune per trigger | 3877 candidate | 1 candidate | -3877x |
| total prune ratio | 76.7% | **0.75%** (9/1196) | -102x |
| query p95 | 293ms | **0.08ms** (微秒级) | +3700x faster |

## Root cause 为啥 prune 这么少

SMT-MT 触发**依赖 inner solver 返 INFEASIBLE**:
- 现项目 inner B1 LBBD 经常 UNPROVEN 而非 INFEASIBLE (24 lever 死症根本)
- **UNPROVEN 不能触发 SMT-MT prune** (unsound — UNPROVEN 可能 ghost_B 仍 fit)
- 9 个真 INFEASIBLE 全来自 mandatory_rect_precheck eliminate 70xH (全宽 candidate facility 放不下)
- 每次只剪 1 个 candidate 上集 (70xH series superset 几乎没有)

Phase 0 mock area≥500→INFEASIBLE 触发的 prune 在 production 几何上不存在.

## src 改动 land 状态 (env-gated default off)

src/search/smt_mt_outer_pruning.py (338 LOC) + src/search/outer_search.py (~35 LOC delta, 4 hook 点) + src/tests/test_smt_mt_outer_pruning.py (224 LOC 20 tests).

env flag: `EXACT_SMT_MT_OUTER_PRUNING=1` (默认 off byte-identical to baseline).

**为啥 land 但 default off**: marginal ROI 不足现在 enable. 等未来 B engine / cand C cut language 升级让 inner solver 返 INFEASIBLE 频率提升, SMT-MT 自动 unlock marginal 增益. Infrastructure 完整不浪费.

## 真 production ROI 重估

168h campaign:
- ~500 sound INFEASIBLE × 平均剪 5-10 candidate 上集 ≈ 2.5K-5K prune / 1196 pool ≈ 2-4x 覆盖 (有 superset 重复)
- 实际节省 ~50-100 candidate 不重跑 inner × 60-120s/inner = **~1-3 hr / 168h campaign 边际增益**
- 跟 cand C / B 比 ROI 低很多

## 跟 B design 关系

B design B 后 inner solver 可能返更多 INFEASIBLE (因 cut language 升级 + 5 cut family 可证 sound INFEASIBLE), SMT-MT 真 unlock 时机在 B Phase 4-5 之后. 现在不动 src 持续保留 env-gated 是对的.

## Refs

- Phase 0 GO memory [[smt-mt-outer-pruning-phase0-go]]
- commits: aa350f5 (Phase 0 probe) + 3d36018 (Phase 1 wire + tests)
