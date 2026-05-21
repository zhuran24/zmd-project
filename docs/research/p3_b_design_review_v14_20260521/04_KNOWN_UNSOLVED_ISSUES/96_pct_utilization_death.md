# Known unsolved issue: 96% 利用率几何死结 (root cause)

## 数据 (重述, 完整推算见 01 项目状态 + geometric_deadlock_data.md)

- Grid: 70 × 70 = **4900 cells**
- 266 mandatory facility footprint: **~3479 cells** (71.0%)
- power_pole + belt + connector: ~800-1000 cells (16-20%)
- Effective occupied (no ghost): **~4300-4500 cells** (88-92%)
- High ghost candidate (area 400-600): free = 4900 - ghost = 4300-4500
- **Effective utilization at high ghost: ~96%**

## 为什么是 root cause

96% utilization 在 packing problem 里是已知 hard threshold:
- 80% 利用率: solver 多数能找出 layout
- 90% 利用率: 难解但仍可
- **95-96% 利用率: 撞 hardness wall**, packing complexity 跳层

特别在 mixed-size strip packing (3x3 / 5x5 / 6x4 / 1x3 boundary 混合):
- 96% 时 packing 几乎是 **perfect packing**, 任何 1-2 cell 间隙都让某
  facility 无法放
- packing 的 feasibility wall 跟 NP-hard 复杂度强相关

cand C v3 实测在 160/266 inst 撞这个 wall (RMP 0 iter infeasible at
column pool 324 covers all individually).

## 为什么 add column / add cut 不能 break

cand C v3 已实施:
- 3-layer bootstrap (direct mini-master + region multi-facility + greedy
  singleton) — column pool 324 cover all 266 instance
- Ryan-Foster branching 跟 std fallback
- A3 set-covering relax LP — 应允许 over-cover
- A1 alternative blueprint generator — 在 congested cell 周围生成 alternative

仍 RMP 0 iter infeasible. **不是 column 不够 / 不是 cut language 不强 /
不是 RF 不聪明**, 是 LP relax 本身在 96% utilization 下 dual 不兼容.

## 形式化论证 (cand C v3 死法的 root cause)

A3 set-covering LP:

```
约束 (per instance i):    sum_{k : iid_k ∋ i} λ_k ≥ 1     (覆盖)
约束 (per cell c):        sum_{k : cell_c ∈ k} λ_k ≤ 1     (排他)
约束 (per port spec):     ...
约束 (per ghost cell):    sum_{k : cell ∈ ghost ∩ k} λ_k = 0  (forbidden)
```

LP 可行 iff exists λ ≥ 0 同时满足. 96% utilization 下:

- 每 cell 约束 dual price ≥ 0 (cell saturated → dual > 0)
- 总 cell dual ≈ |occupied cells| ≈ 4300
- 每 instance 约束 dual 必须 ≥ 0 (covering)
- 总 instance dual ≈ 266

由 LP duality:
```
sum_k λ_k * cells_used(k) = sum_c cell_dual(c) * cell_usage_indicator
```

在 96% utilization, cell_dual sum ≈ 4300, λ_k * cells_used(k) avg ≈ 9-15
(facility footprint), 需要 λ_k 满足非常 tight constraints.

→ LP feasibility region ≈ 0-dimensional or empty 在 96% utilization. column
pool 加多再多都不能扩大 feasibility region.

## 为什么 B 设计能 break

B 不在 LP partition framework, 直接在 placement variable space:

- placement[i] = pose_id (explicit decision, 不是 λ weighting)
- cell_owner[c] = instance_id (explicit ownership, 不是 fractional λ)
- 96% utilization 下, B state machine propagation 早期就识别 cell 冲突
  (bitset `placement.cells & free_cells == 0` 即冲突)
- cut store 内 cut 直接 prune pose_domain, 不需要 LP feasibility

→ B 不需要 LP feasibility 作为前提, 直接 decision-level reasoning.

## 还没解的部分

1. **B 设计的 96% utilization scaling 实测**: 没 PoC, 只是 hypothesis. B
   state machine + 5 cut family 是否真能在 96% utilization 下找出 layout?
2. **packing complexity 的 absolute lower bound**: 即使 B 设计 work, 96%
   utilization 是已知 NP-hard. 真有 polynomial wall-time bound 吗?
3. **5 cut family 在 96% utilization 上的 cut 发射率**: 实测之前不知道
   每 cut family 平均每秒 generate / resolve 多少 cut

## 跟 cand C 死法的 sound 替代

虽然 B 不 LP, **不丢 sound 性**:
- 96% utilization 下 some layout 可能真不可行 (packing infeasibility),
  B 应给 certified INFEASIBLE
- 若 layout 可行, B 应找到并给 certified FEASIBLE

→ B 设计的 sound 性 evidence 来自 5 cut family soundness 论证 (前面定义
里每 family 都有 soundness 段). 完备性 evidence 来自 stress test 验证.

## Stress test 视角

构造恶魔构型起点之四: 一个 layout 在 96% utilization 上是**唯一 feasible
layout** (即只有 1 个 valid layout up to symmetry). 这是 hardest case
— 任何 sub-optimal pose 选择都让 layout infeasible.

观察:
- B 5 cut family 是否能找到此 unique layout? 还是 stuck 在 close-but-not
  layouts?
- 找到此 layout 需要多少 search nodes? wall time?
- 若 B 也 fail, 是否需要补第 6 cut family (e.g. exhaustive
  cross-instance pattern minimization)?

形式化 lower bound: 96% utilization mixed-size packing on 70×70 grid 是
PSPACE-hard / NP-hard / co-NP-hard 之一. 引用 textbook lower bound 论证
B 设计在此 problem class 上的 worst-case complexity.

## 跟 alive candidates 的关系

项目 paradigm investigation 标记的 alive candidates:
- L25 IHS (Implicit Hitting Set, AAAI 2026)
- L26 Benders symmetry framework (arxiv 2511.22251)
- candidate A Hybrid CDCL + CP-SAT warm-start (arxiv 2512.18034)

这些 paradigm 跟 96% utilization 几何死结的关系**没 verify** — 都还没
land. 项目方推 Design B 是基于 cand C 已实测 NO-GO + 24 lever 死法
共同 root cause + Gemini fat-context 推 B 严格 stronger.

比 B 更适合? (这是 paradigm 选择问题, 不是 B 设计细节问题, 但仍欢迎反
馈)
