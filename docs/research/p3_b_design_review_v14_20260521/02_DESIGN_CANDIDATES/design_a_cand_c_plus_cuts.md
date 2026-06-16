# Design A: Cand C + cut language 升级

## 概述

Design A 继续走 Phase 2 v3 后的自然下一步: **在 cand C 的 column generation
/ branch-and-price framework 内, 升级 cut language 表达力**, 加新 cut family
来 close cand C 在 160/266 inst RMP 0 iter infeasible 的 gap.

## A 设计内容

Phase 2 v3 之后 cand C 的 cut language 表达力是:

- set covering / set partition LP (instance cover)
- cell exclusivity (Σ_k λ_k * cell_use(k, c) ≤ 1 per cell)
- ghost-rect filter (poses overlapping ghost 不入 column pool)
- Ryan-Foster branching (`same(i, j)` / `diff(i, j)` decisions)
- routing-aware pricing seed (Rent's-Rule cap + perimeter port-direction bonus)
- boundary equality dual (per-(cell, dir) flow net)

A 设计要新增的 cut family (推测, 项目方未深入设计):

1. **Perimeter Capacity cut** — 限制 column pool 占某个 perimeter side 的
   facility 数量, 强制 boundary_storage_port × 边长 ≤ 边可用长度
2. **Component reachability cut** — 强制 column pool 选出的 facility 集合
   组成 connected routing component (绕 ghost rect)
3. **Pattern no-good cut** — λ-space conjunction cut, 切掉某些 column
   subset 组合
4. **Cluster symmetry cut** — manufacturing_3x3 132 同质 facility 的
   symmetry breaking

## 优点

- **复用 cand C Phase 0/1/2 v3 ~3000 LOC** (`feasibility_bootstrap.py` /
  `ryan_foster.py` / `pricing_cache.py` / `routing_aware_pricing.py` /
  `boundary_constraints.py` 等)
- **不重写 master form** — 仍是 LP + pricing CP-SAT + B&P, 不动 pose-bool
  master 或 coordinate master
- **incremental engineering** — 加 cut, 改 pricing dual, 不影响现有
  bootstrap / RF logic
- **column generation 是 well-studied paradigm**, 有 Vanderbeck / Lübbecke
  /  Desaulniers 等 textbook 的 stabilization / smoothing 工具支撑

## 缺点

- **cand C v3 实测撞墙** — 96% utilization 几何死结让 LP 0 iter infeasible.
  cut 加再多 column 都不能让 LP 可行, 因为根本 LP relax 在此 utilization
  下 dual 不兼容
- **cut language 跟 LP 框架强耦合** — 任何新 cut family 都要表达成 λ-space
  线性约束 (Σ_k a_k λ_k ≥ b 形式), 这对 connectivity / topological
  invariant 等 non-linear 性质表达力受限
- **boundary_storage_port × perimeter trap 无 LP-natural 表达** — perimeter
  长度约束跟 cell coverage 不在同一空间, 需要 lift 到全图 column pool 的
  meta-property, LP variable 数量爆炸
- **27 lever 调研已经 cover 部分 cut language 升级方向**, e.g. Path 13
  SAC-Hull (corridor capacity Menger min-cut) 跟 perimeter capacity cut
  数学接近, 实测 necessary ≠ sufficient — sub-problem 给的 cut 在 master
  LP 翻译后维度丢失
- **Cand C v3 m14 RF/std nodes ratio 4.38 (40 inst)** — Ryan-Foster 比标
  准 branching 多 4 倍 nodes, 已经是 RF degeneracy. 加新 cut family 可能
  让 RF 更糟

## A 设计的实施成本估算 (Claude pace)

- 3-4 个新 cut family × ~300-500 LOC 每个 = ~1200-2000 LOC
- 加 stabilization (Wentges / interior dual stabilization) ~500 LOC
- m10 sound 性临界点 fix (80 inst False) ~300 LOC
- Phase 3 测试 + 重新跑 160/266 inst measure 10-12 hr wall × 3-5 round
  = ~50 hr wall
- 总成本估 ~3 周 (Claude pace)

## A 设计的 confidence

**项目方判断: 中-低 confidence**

- v3 v2 v1 实测累积 NO-GO, 3 个 iteration 同根因 (96% utilization)
- 加 cut family 在 LP infeasibility 0 iter 上没有 leverage — bootstrap 都
  filled column cover instance individually 还是 LP 不可行
- → 加 cut language 不能让 LP variable space 可行, 只能改 RF 决策 / B&P
  tree 形状

## Stress test 视角

Design A 的 stress test 问题:

1. 加新 cut family 能否突破 LP iter 0 infeasibility?
2. 96% utilization 几何死结是 LP-natural 表达极限吗? (有没有数学论证)
3. 如果 A 升 cut language 解决不了, 是否 cut language 在 set partition LP
   范畴**fundamentally 不够**, 必须换 master form?

→ 项目方选 B 是基于 "A 升级 cut language 仍在 LP 范畴内, 不能跨 master
form rewrite". Stress test 可以验证 / 反驳这个判断.

## 跟 Design B 的关系

A 跟 B 是**互斥**而不是 stack:

- A 留 cand C LP master + B&P, 加 cut 在 LP variable space
- B 砍掉 cand C master, 自研 state machine master + 5 cut family 直接
  在 placement variable space

**不能** "在 cand C 上加 B 的 cut family" — 因为 B cut family 表达力跟
master state machine 强耦合 (cut store reference state machine vars), 不
能直接 lift 到 cand C 的 λ-space.

→ 选 A 还是 B 是 path decision, 不是组件 selection. 项目方推 B 推 10
day plan 是因为 B 严格 stronger.
