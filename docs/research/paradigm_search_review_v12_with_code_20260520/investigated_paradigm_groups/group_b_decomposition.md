# Group B — Decomposition Paradigms (4 paradigm, 全 NO-GO)

调研覆盖跟 LBBD 不同 dimension 的 decomposition framework. 校验后 verdict.

## B1: Column Generation / Branch-and-Price (远期备选, 见 candidates/candidate_c)

详 `candidates/candidate_c_column_generation/`. 这里仅总结 group dead 表象:

- Production tooling: GCG 3.5.0 + PyGCGOpt v0.1.3 (early stage); BaPCod 0.84 (2025-11) C++ only; Coluna.jl Julia
- 2024-2026 paper: 0 显式讨论 "column 粒度怎么定", 多 domain-conventional (zone/bin/route)
- 实施成本 3-6 月 Claude (跟做新 paradigm 同量级)
- **State**: 不在 production-tool-ready 范围. 列在 candidates/ 但 priority 最低.

## B2: Lagrangian relaxation + subgradient

- **State**: 2024-25 主流方向是 hybrid Lagrangian + Benders (Edinburgh stochastic hub) 和 zero-duality-gap reformulation (arxiv 2411.12085 — 需要 tree-decomposition + intersection graph treewidth as extension, 不是 hard requirement).
- **Paradigm**: dualize coupling 约束进 objective (relax 后变 multiplier × violation 罚项), sub-problem 仍可解. dual bound 来自 max_λ L(λ).
- **vs LBBD**: Lagrangian 不动 master 结构, 它给的是 dual bound 用于 prune, 不是 cuts.
- **Fit 致命问题**: 70×70 + 266 facility 是 **dense 2D combinatorial**, 非 separable. ghost rectangle / power coverage / port clearance 跨 facility 强耦合, 不是 facility location 经典 "每客户分 1 仓库" 那种弱耦合. ISPD VLSI 用 continuous Lagrangian (gate width 连续), discrete 下 "Lagrangian dual 非凸".
- **Subgradient 收敛**: stepsize 1/(k+1) 极慢 (Hooker CMU notes), 大规模数千-数万 iter.
- **Verdict NO-GO**: (a) Lagrangian dual 给的是 lower bound 不是 cert, 跟 PROJECT_LOCK certified path 语义不对齐; (b) 2D dense combinatorial 不 separable; (c) 仍要叠回 LBBD/Benders 闭合.

## B3: Modern Benders Decomposition advances (2024-2025)

- **2025 进展 paper**:
  - Pareto-optimal cut selection (Springer 2025, 12532-025-00291-1, paywall 无法 verify 完整 content)
  - Deepest Cuts (Hosseini & Turner, INFORMS OR 2024) — p-norm 几何深度选 cut
  - Disjunctive Benders Decomposition (arxiv 2506.03561, 2025) — 解决 tail-off + (sub-agent 说 "自报 CP-SAT 不实用" 但 abstract 没原话, **caveat 是 sub-agent 推断**)
  - Hierarchical Recursive LBBD (arxiv 2512.20239, 2025-12) — multi-level 7 hierarchy. **paper 自报是 heuristic method 不是 exact** (校验中发现 caveat)
- **Fit 致命问题**:
  - Pareto/Deepest/Disjunctive 全部依赖 LP duality / continuous relaxation; 我们 binding/routing/flow 都是组合 subproblem 无 LP 对偶, 没有 cut 选择空间可挑深. Disjunctive paper "not practical on CP-SAT" (sub-agent 推断).
  - Hierarchical Recursive LBBD 要求**问题天然层级结构**, 我们 70×70 flat 不 fit
  - Hierarchical LBBD 是 **heuristic, 违 PROJECT_LOCK** certified exact
- **Verdict NO-GO**: paper 加速方向跟 CP-SAT + 组合 subproblem 架构 fundamental 不兼容. 唯一同领域 paper (Hierarchical) 违 LOCK + 不 fit.

## B4: Decision Diagrams (BDD / MDD / sDD)

- **State**: 学术活跃 (Bergman/van Hoeve/Hooker CMU 主线; 2024 ECAI CODD solver = Michel + van Hoeve 2 作者; IJCAI 2024 MDD-constrained path).
- **Production tooling**: 极少, DDO (Rust, xgillard, **stable v2.0.0 + 450 commits + CI** — sub-agent 误报 "experimental") / DDOLib (Java port) / CODD (PoC). 无 OR-Tools/Gurobi 级成熟度.
- **Paradigm**: 要求问题表达成 dynamic program (Markov state + 变量序列化 transition). relaxed DD 给 dual bound, restricted DD 给 primal heuristic, branch on **DD 节点**而非变量.
- **Fit 致命问题**: 我们问题**非自然 DP** — 266 facility 同时 2D placement + 全局 power_coverage + multi-commodity routing, 无清晰变量顺序产生小 Markov state. state 至少要 encode "已 placed 格子 + 已用 power pole + port demand 累积" → state space 爆炸 (70×70 binary occupancy ≈ 2^4900).
- **Verdict NO-GO**: paper 实测 scale 50-300 vars (结构友好), 我们 266 facility + 4900 cell dense 维度远超. 重写 2-4 周 Rust 不可复用现 CP-SAT/OR-Tools infrastructure.
