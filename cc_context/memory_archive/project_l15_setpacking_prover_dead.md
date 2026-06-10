---
name: l15-setpacking-prover-dead
description: "2026-05-17: GPT L14 升级建议 set-packing branch-and-bound prover (1-2 月投资) PoC 实测 ❌ — paradigm 攻错层. minimum set-packing 核心 CP-SAT 几秒就 verdict (corner 2.3s INFEASIBLE, interior 7s FEASIBLE 8 worker); 真瓶颈是 master 多余的 port/power/connector/boundary 约束, 让 full master.solve 30 min 也 UNKNOWN. paradigm 不 cover 这些. 13 条 lever 全 verdict. v9 包送 GPT 后第一次 paradigm 级建议也死."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**2026-05-17 set-packing prover PoC verdict (~3 小时 Claude pace)**:

GPT 在 L14 weighted-occupancy 死路后推荐 set-packing branch-and-bound prover. 1-2 个月工作, paradigm-level investment. 在投资之前先验**底层假设是否成立**.

## 验证 question + 实测

| 维度 | GPT 假设 | 实测结果 |
|---|---|---|
| paradigm 攻的层是 bottleneck? | 是 (set-packing 核心难) | ❌ **不是** — minimum set-packing CP-SAT 几秒搞定 |
| prover 比 CP-SAT 快几个数量级? | 是 (custom > generic) | ❌ paradigm 攻的是已 fast 的层, 没增益空间 |

## 实测数据 (docs/research/setpacking_prover_poc_20260517/)

**Step A** (full master.solve via LBBD): 27×15 anchor (22,28) 30 min UNKNOWN. anchor (0,0) corner 10 min UNKNOWN.

**Step B** (minimum set-packing CP-SAT — 只 demand + cell exclusivity + ghost-forbidden, 不含 master 多余约束):
- 27×15 corner (0,0) 1 worker 60s → **INFEASIBLE 2.4s, 0 branch** (propagator instant)
- 27×15 interior (22,28) 8 worker 5 min → **OPTIMAL feasible 7.2s 12K branch**
- 27×15 corner 8 worker → INFEASIBLE 2.3s
- 27×15 edge (21,0) 8 worker → INFEASIBLE 2.3s
- 28×15 corner (0,0) → INFEASIBLE 2.3s
- 28×15 interior (21,27) → OPTIMAL 7.1s

**规律**:
- Corner/boundary anchor: minimum CP-SAT propagator 2-3s INFEASIBLE
- Interior anchor: minimum CP-SAT 8w 7s feasible

minimum set-packing **CP-SAT 已经轻松解决**, 不是瓶颈.

## 真瓶颈 layer-by-layer 锁定 (Step D 加跑)

用现成 `skip_power_coverage=True` 开关对比:

| Config | vars | constraints | master.solve wall | status |
|---|---|---|---|---|
| skip_power=True | 24,824 | 69,910 | **65.9s** 2 LBBD iter 完整 | UNPROVEN |
| skip_power=False (full) | 57,668 | 132,515 | **30 min UNKNOWN** | UNKNOWN |

差异: +32,844 vars (+132%) + 62,605 constraints (+90%). master.solve **从秒级 → 30 min UNKNOWN, 跨数量级**.

**锁定**: 真 bottleneck = `_add_geometric_power_coverage_constraints` (`src/models/exact_coordinate_master.py:5327`).

encoding 内部: 每 powered_slot (facility cell) 需 element_witness_v1 / table_pairwise_witness_v1 找 pole_slot 在 radius 内 cover. 是 disjunctive coverage (OR-of-many-pair), CP-SAT 跟 LP-MIP 一样 stuck.

跟 [[highs-rewrite-blocker]] (HiGHS PoC 加 power_coverage 撞 42 GB) / [[rewrite-path-exhausted]] (LP-MIP 对 dense linear constraint 解不动) **同根因**. 不是 solver 选错, 是 power_coverage encoding 本身 hard.

## 算法改进方向 (下次围绕这个做)

不是 set-packing prover. 应该针对 power_coverage encoding 重设计:
1. **column generation / lazy cut 重 encode** — 别 disjunctive over-all-pair upfront, 按需 separator 加. SCIP separator callback PoC 验过 fire OK 但 production 未集成
2. **缩 powered_slot × pole_slot pair 数量** — 几何 pre-prune 减一半
3. **Lazy power_coverage 进 binding subproblem** — master 留 set-packing 核心. PROJECT_LOCK L4 禁 EXACT_POWER_PLACEMENT_SUBPROBLEM 重开, 但 lazy cut style 不同, 需 PROJECT_LOCK 重审
4. **#84 tight pole_slot upper bound** — Phase 3C roadmap 已 land 但还有空间

## paradigm verdict

❌ **死路 — 攻错层**.

GPT 三连错估 + L14 数学能力上限 + 现在 L15 paradigm 攻错层 = GPT review 投资全部回报为零.

## 跟 v3/v8/v10/L14 错估对比

| | v3 | v8 | v10 | L14 | **L15** |
|---|---|---|---|---|---|
| 错估类型 | 算法 | 算法 | 前提 | **没错估** (数学能力) | **paradigm 攻错层** |
| GPT caveat | 没说 | 没说 | 暗示 | 明说 3 个 hit #1 | 没说 — 没意识到 minimum 不是瓶颈 |
| PoC 时间 | hours | hours | hours | 70 min | 3 hours |
| Verdict 类型 | wall-clock 同 quality | 同上 | 0 trigger | LP=1.0 数学不可 | paradigm 攻的层 CP-SAT 已 fast |

L15 是新错估类型: **paradigm 选择 (针对哪层下手) 错了**. 不是数学能力不够, 不是数据不匹配, 是**问题诊断不对** — GPT 假设 set-packing 核心是 stuck, 实测 set-packing 核心几秒搞定, stuck 在 master 多余约束.

## 还有 1 个未实测的副 finding (data 无效, 留着)

我尝试用 `MasterPlacementModel.from_exact_core(...).build().solve()` 直接调 (跳过 LBBD pipeline), 全 0.0s INFEASIBLE 但 build_stats 显示 integers=0 booleans=0 — **模型 presolve 后空了**. 不是真 verdict, 是 isolated build 漏 setup. 数据无效, 但留在 README 提醒未来直接 m.solve() 路径需要先解决 build 完整性.

## 累积 lever verdict

L1-L10 + L12 (v8) + L13 (v10) + L14 (weighted occupancy) + **L15 (set-packing prover paradigm)** = **13 条 lever 全 verdict 死路**.

GPT 4 次出招 (v8 / v10 / L14 / L15) 全死. paradigm + 算法 + 数据 + 数学全方向 attempt 后, **在不放宽硬约束的前提下没有路径**.

剩下选项:
- L11 牺牲严格性 (用户拒绝)
- L6 AI sidecar (long-term)
- 改数据 (扩 blueprint 到 266 + 改 greedy)
- Paradigm shift (SMT / Z3 + theory plugin / 自写 propagator / ML 学 cut)
- 接受 verdict (用户决定 release 现有 incumbent area=405 还是搁置)

## 归档位置

- `docs/research/setpacking_prover_poc_20260517/` — README + 2 PoC script + logs/
- 直接 m.solve() 副 finding 也归档 (poc_minimum_with_power.py, 数据无效但留作 reference)
- commit: 待 land

## 链

- [[l14-weighted-occupancy-dead]] — 上一步
- [[2026-05-16-session-final-state]] — 12 lever 状态 (本次后 +1 → 13)
- [[highs-rewrite-blocker]] — 同根因 (dense linear constraint 在 MIP 上天然 hard)
- [[gpt-error-types-taxonomy]] — 新加 type: paradigm 选择错估
- [lever verdicts](docs/lever_verdicts.md) L15 加入 ❌
