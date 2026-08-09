# Path 14 — PCR-CUT (Patch-Certified Routing Conflict Core)

## 当时项目情况

Path 12 (binding-side) + Path 13 (corridor capacity) 死后. GPT v3 review.

## 为什么走这条路

GPT v3 plan: 兼具 Path 12 local pose conjunction + Path 13 global focus + **belt-level actual conflict**.

**核心 idea**: master 给 layout → 找最堵小区域 (10×10-20×20 patch) → patch 内**真用 belt routing CP-SAT 跑** → patch INFEASIBLE → assumption core + replay validate → signature lifting 成 master nogood cut.

跟前 2 paradigm 区别: PCR-CUT 真用 patch 局部 CP-SAT 跑 routing (含 ground+elevated layer / capacity / bridge / continuity / port adherence), 不只 cert tight.

## 实验过程

6 个 Phase (commits 24ed7d8 → Phase 5 trial):
- Phase 0 GO ✅: top-3 patches sac coverage 2.8x, 770 cells cover 98%
- Phase 1 GO ✅: patch belt CP-SAT 21/21 INFEASIBLE in 0.17s ≤ 5s, p95 metrics 全过
- Phase 2 land: replay validate + QuickXplain, 8 unit tests pass
- Phase 3 land: signature lifting + master cut + separator, +10 tests
- Phase 4 land: benders_loop hook, 5/5 iter cut_added
- Phase 5 multi-anchor: 8 anchor × max_iter=10, master_seconds=180

## 实验结果

| anchor | size | status | wall_s |
|---|---|---|---|
| interior_22_28 | 27×15 | UNPROVEN | 594.8 |
| interior_10_10 | 27×15 | UNPROVEN | 611.3 |
| interior_44_30 | 27×15 | UNPROVEN | 591.3 |
| interior_15_40 | 27×15 | UNPROVEN | 613.3 |
| corner_0_0_NEGATIVE | 27×15 | INFEASIBLE | 55.9 (sound, no patch entry) |
| small_10x10 | 10×10 | UNPROVEN | 648.6 |
| small_15x10 | 15×10 | UNPROVEN | 622.6 |
| small_15x15 | 15×15 | UNPROVEN | 657.6 |

**0/8 CERTIFIED**, 7/8 UNPROVEN. master 加 70 cuts 后 sustain OPTIMAL — paradigm 工程上 work, 但单独不破局.

## 经验跟教训 (含瓶颈理解更新)

- **3 个 paradigm 框架同质死法** (RAB-SEP / SAC-Hull / PCR-CUT). 设计完全不同抽象层 (binding-side / corridor capacity / patch belt CP-SAT), 全 端到端 land ✅, 全 breakthrough ❌.
- **signature lifting 实际 lift count 都 = 1** — 每 cut 只切 exact pose, 没真 lift family. 原因: instance pose pool 每 pose 都有 unique footprint+ports pattern, 没 equivalence 可 lift.
- **瓶颈理解更新**: routing INFEASIBLE 由**全局 geometry 决定**, patch 局部 INFEASIBLE 是 necessary 不 sufficient. 累 cut 后 master 给 alternative layout L2 — L2 同 patch routing-feasible 但**别的 patch P2 上 routing-INFEASIBLE**, 不收敛.

## code/

- `code/` 含 patch_routing_core.py (983 LOC) + patch_conflict_separator.py (469 LOC) + Phase 0-5 trial scripts + replay + QuickXplain unit tests
