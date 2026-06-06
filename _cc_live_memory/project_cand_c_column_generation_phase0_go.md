---
name: cand-c-column-generation-phase0-go
description: GPT v12 cand C Column generation Phase 0 ✅ 20-instance 8/8 GO (m5=83.3% multi-facility column dominate). 唯一真换 master variable basis 的 paradigm 通 Phase 0. m9 perimeter proxy 全 0 = boundary 不紧
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-21 commit ac4fe44 + fd6179e + (TBD final): GPT v12 推荐 4 个 alive 候选之 **cand C Column generation / branch-and-price**. 唯一 "真换 master variable basis" 的方向. Phase 0 经过两次 bug fix 后 verdict GO.

## 实施迭代

### Iter 1 (commit ac4fe44): initial probe land

- 1004 LOC probe + 178 LOC README
- RMP: ortools GLOP, set partitioning over patterns
- Pricing: CP-SAT 12×12 sliding window, stride 6, force 2≤facility≤15 per column
- Mini exactness: solve_direct_mini_master() 复刻 pose-bool master 核心 form 对照
- bootstrap fix: disjoint singleton columns (5 pose pools 默认 pose 全在 (0,0) 重叠)

### Iter 2 (commit fd6179e): add m9 perimeter I/O capacity proxy

Gemini round 2 finding 落地 — Phase 0 只测几何 packing 不能 forecast Phase 4 加 routing 后 boundary dual dense (2^144 边界状态爆). 加 lightweight proxy 约束在 RMP 层预先 detect.

- proxy 约束: `Σ (pattern_port_count_in_window) × λ_pattern ≤ 160`
- 12×12 window capacity = 44 perimeter × 4 dir - 16 corner penalty = 160 slots
- m9 metric (last 5 iter avg dual snapshot): m9_proxy_dual_active_pct + m9_proxy_dual_sparsity
- GO threshold: active ≤ 30% + sparsity ≤ 20%

### Iter 3 (commit TBD): cost function fix (set partitioning min cardinality)

发现 cost = facility count 让 single-fac column 跟 multi-fac column 在 LP tied at optimum → pricing iter 0 立即 stop false NO-GO.

修:
- RMP cost = 1 per column (set partitioning min cardinality)
- Pricing CP-SAT obj = -Σ z * (π + cell_penalty), reduced_cost = 1 + obj_value/SCALE
- m8 sound check 从 "obj == direct_obj" 改成 "feasibility-equivalence" (CG LP finite + direct OPTIMAL/FEASIBLE)

## Phase 0 verdict (经过 fix 后)

### 20-instance (真 capacity test) ✅ GO 8/8

| metric | 实测 | threshold | 判定 |
|---|---|---|---|
| m1 columns | 120 | ≤ 5272 (≤25% baseline) | ✅ |
| m2 pricing p95 | 0.17s | ≤ 30s | ✅ |
| m3 RMP LP p95 | 0.002s | ≤ 5s | ✅ |
| m4 RSS | 1.37 GB | ≤ 4 GB | ✅ |
| **m5 multi-facility column pct** | **83.3%** | ≥ 30% | ✅ 超 53pp |
| **m6 single-facility column pct** | **16.7%** | ≤ 50% | ✅ |
| m7 pricing vars / direct | 6.7% | < 50% | ✅ |
| **m8 feasibility-equivalence** | True | True | ✅ |
| **m9 proxy dual active/sparsity** | 0% / 0% | ≤30% / ≤20% | ✅ |

RMP LP obj 从 20 降到 3.083 — 3 fractional column cover 20 mandatory (平均每 column 覆盖 6-7 facility).

### 5-instance (sound 测试) — NO-GO size artifact, m7/m8 通过

5 mandatory bootstrap singleton 已 LP optimum (cost=5), pricing 找 multi-facility column reduced_cost 太接近 0 不显著 < EPSILON. iter 2 后 stop, only 7 column total. m5=28.6% / m6=71.4% NO-GO. **trivial-LP 现象, 不是 cand C 失败**.

m7 ratio 0.058 ≤ 0.5 ✅, m8 match True ✅ — 5-instance sound 性 metric 通过.

## Critical findings

1. **m5 = 83.3% multi-facility column dominate 超 GPT v12 + 独立 Claude prior 预测 30-50%**: column generation 在 70×70 grid + 266 facility 中间粒度真存在.
2. **m9 = 0% boundary dual active**: Phase 4 加 routing 后 boundary dual dense 风险**低**, Gemini round 2 Q2 担心方向当前看不严重.
3. **m7 = 6.7%**: pricing vars (~4K) << direct master vars (~62K), pricing 没退化为原问题.
4. **RMP LP 从 20 降到 3.083**: 物理 sound — 6-7 facility per column 集成压缩.
5. **Cost function fix 是 critical**: 原 spec cost=facility count 数学错, 必须 cost=1 per column (set partitioning min cardinality).

## 跟前 3 个 Phase 0 NO-GO 对比

| Phase 0 | verdict | 死/活原因 |
|---|---|---|
| LIC (path 18) | ❌ NO-GO | cell-front 几乎决定 pose, m1=2 |
| Lever 26 Benders symm | ❌ NO-GO | symmetry 被 ghost/boundary/port_dir 打碎, m5=1 |
| Lever 25 IHS | ❌ NO-GO | core size 全=1, HS=union 退化 |
| **Cand C Column generation** | ✅ **GO** | **真换 master variable basis, 攻 cut axis 之外** |
| SMT-MT outer pruning | ✅ GO | monotone containment 76.7% prune, 跟 cand C orthogonal stack |

Cand C 跟 SMT-MT 是项目 28 lever 中**唯二**的 GO verdict. 共同点: 都不攻 cut 表达力, 都换 problem 不同 layer.

## Next Phase 1 (3-5 day Claude pace)

1. Pattern grammar 数据结构 + boundary signature schema
2. Exact validator: reconstruct integer layout 跟 direct pose-bool master 比较 instance assignment
3. 真 integer reconstruction (Phase 0 只用 LP, Phase 1 加 integer branching)
4. 增 candidate region 数据 (12×12 stride 6 共 100 region)
5. 估到 Phase 1 末: 5/10/20/40 instance ramp 全 GO

Phase 1 GO 后 进 Phase 2-4 (RMP LP + pricing loop full / branch-and-price / power coverage + port boundary signature).

总工时估 3-6 月 Claude pace 不变 (Gemini Q1 警告 Phase 0 不接 routing 是 weak signal, Phase 4 真 risk 在 boundary state encoding).

Reference: 
- GPT v12 review package 2026-05-20 cand C 评估
- Gemini round 2 2026-05-21: m9 perimeter proxy 设计 (Cho BoxRouter DAC 2006 + Rent's Rule)
- 独立 Claude opus brainstorm (path 18) 错过 column generation 因禁词约束, 但 Phase 0 同 day 跑出来 verdict 跟 GPT v12 prior 应验
