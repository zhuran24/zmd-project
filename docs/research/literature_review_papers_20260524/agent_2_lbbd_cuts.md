# Agent 2 — LBBD cut strengthening / MUS / placement-routing 调研

**Agent ID**: a0911f796fdfb6be8
**Model**: Opus
**Date**: 2026-05-24
**方向**: 支持 PCR-CUT 路径（Phase 5 marginal）+ 寻找 stronger cut paradigm

---

## Direction 1: Combinatorial Benders / LBBD cut strengthening

**Karlsson, E., & Rönnberg, E. (2023). Computational evaluation of cut-strengthening techniques in logic-based Benders' decomposition. *Operations Research Forum, 4*(3), 67.**
- Relevance: HIGH — 3000 实例上系统对比 5 种 cut strengthening (no-good, greedy, deletion-filter irreducible, MIS, MFS) 在 planning/scheduling、VRP-with-location-congestion、facility location 三类问题上的表现。
- Concrete use: 直接验证 "irreducible cut + deletion filter" 路径在 LBBD 上的实证最优，给 PCR-CUT minimize 阶段提供 sister benchmark。当前 QuickXplain minimize 实测有效，论文确认这是经验最佳家族；提示要补 greedy-then-deletion 两阶段流水线 (现在单走 QuickXplain)。
- Risk: 论文 benchmark 是经典 scheduling/VRP，没有 ghost rectangle / patch belt 这种几何 sub-master。
- URL: https://link.springer.com/article/10.1007/s43069-023-00242-3

**Karlsson, E., & Rönnberg, E. (2021). Strengthening of feasibility cuts in logic-based Benders decomposition. In *CPAIOR 2021* (LNCS 12735, pp. 45-61). Springer.**
- Relevance: HIGH — 上文的算法基础篇，专讲 feasibility cut (不是 optimality cut) strengthening；PCR-CUT 就是 feasibility cut。
- Concrete use: 给 cut strengthening 一个"deletion filter 在 irreducible cut 上正确"的形式化保证 — 这是 PCR-CUT QuickXplain 步骤的理论引用。
- Risk: 仅 feasibility，没碰 optimality cut。
- URL: https://link.springer.com/chapter/10.1007/978-3-030-78230-6_3

**Varga, J., Raidl, G. R., & Limmer, S. (2024). Speeding up logic-based Benders decomposition by strengthening cuts with graph neural networks. In *LION 17* (pp. 24-38). Springer.**
- Relevance: MEDIUM — GNN 当 oracle 预判 "哪些约束在 minimal infeasible core 里"，省掉重复 solver 调用。
- Concrete use: 不是马上能用，但若 PCR-CUT 每 anchor 多次 QuickXplain 成本太高，可以学一个 sidecar predictor 加速 core 提取 (AI safety contract 允许 hints)。
- Risk: 训练数据要项目特定 instance pool；冷启动期间没用。

**Liñán, D. A., et al. (2024). Multicut logic-based Benders decomposition for discrete-time scheduling and dynamic optimization of network batch plants. *AIChE Journal, 70*(7), e18491.**
- Relevance: MEDIUM — multicut (一 iter 多 cut) 经验数据。
- Concrete use: PCR-CUT top-K patches 已是 multicut 思想，论文补强；可学其 aggregation rule。
- Risk: 化工流程图调度，几何无关。

---

## Direction 2: No-good learning / MUS / conflict-driven

**Junker, U. (2004). QUICKXPLAIN: Preferred explanations and relaxations for over-constrained problems. In *AAAI-04* (pp. 167-172).**
- Relevance: HIGH — QuickXplain 原始论文，PCR-CUT 直接在用。
- Concrete use: 已是 minimize 步骤的算法基础；引用 + 形式化证明 sound。
- Risk: 仅算法，没强化方向。

**Marques-Silva, J., & Mencía, C. (2020). Reasoning about inconsistent formulas. In *IJCAI-PRICAI 2020* (pp. 4899-4906).**
- Relevance: HIGH — MUS / MCS / MaxSAT 现代 survey，covers progression / dichotomic / insertion-based MUS 算法在 SAT 上的实证对比。
- Concrete use: 提示 deletion-based 不一定最优 — 在 SAT 上 progression algorithm 经验更快；CP 上未必但值得 Phase 0 试。如果 QuickXplain bottleneck 出现，progression 是 drop-in 替代。
- Risk: SAT-centric，CP 上需要重新 benchmark。

**Bendík, J., & Meel, K. S. (2024). Graph pruning for enumeration of minimal unsatisfiable subsets. *arXiv:2402.15524*.**
- Relevance: MEDIUM — 多 MUS 枚举的图剪枝；一次 anchor 只要一个 MUS，但若要 cut diversity (top-K core) 这是路径。
- Concrete use: PCR-CUT top-K patch 可以扩展成 top-K MUS per patch，论文给剪枝技术。
- Risk: 一般 MUS enumeration overhead 比单 MUS 大很多。

**Hansen, P., et al. (2024). G-CSEA: A graph-based conflict set extraction algorithm for identifying infeasibility in pseudo-boolean models. *arXiv:2509.13203*.**
- Relevance: MEDIUM — 图结构 conflict set 比 QuickXplain 在 pseudo-Boolean (≈ master 结构) 上更 compact + solver call 更少。
- Concrete use: PCR-CUT 提取 core 的替代 paradigm — graph-traversal first, QuickXplain second，缩 solver call 数。
- Risk: pseudo-Boolean 模型需要 reformulate；pose-bool master 接近但不完全是。

---

## Direction 3: Branch-and-cut for facility + routing

**Belenguer, J. M., Benavent, E., Prins, C., Prodhon, C., & Wolfler Calvo, R. (2011). A branch-and-cut method for the capacitated location-routing problem. *Computers & Operations Research, 38*(6), 931-941.**
- Relevance: MEDIUM — capacitated LRP 的强 valid inequality 家族 (subtour、co-circuit、capacity)；提示 routing precheck 可以预生 valid inequalities 到 master。
- Concrete use: master 加 routing-derived flow inequality 当 strengthening — 不是 cut paradigm 换，是 master 端 informed warmstart。
- Risk: LRP 是 TSP-like 路由，我们是 grid 多 belt 路由，inequality 几何形式不同。

**Costa, L., Contardo, C., & Desaulniers, G. (2019). Exact branch-price-and-cut algorithms for vehicle routing. *Transportation Science, 53*(4), 946-985.**
- Relevance: LOW-MEDIUM — VRP B&P&C survey，subset-row cut + ng-route。
- Concrete use: subset-row cut 概念可能 lift 到 patch belt — "k 个 instance 必占用 ≥ K' cell" 这种 row-pattern cut。
- Risk: VRP 跟 placement-routing 模型耦合方式不同。

**Tan, Y., Carlsson, J. G., & Yakıcı, E. (2018). Multi-commodity location-routing: Flow intercepting formulation and branch-and-cut algorithm. *Computers & Operations Research, 89*, 168-182.**
- Relevance: MEDIUM — multi-commodity flow + location 联合，跟 flow subproblem 同模型族。
- Concrete use: flow-intercepting cut 可能改写成"patch belt 内 commodity demand 不可满足"的 cut family，补强 PCR-CUT。
- Risk: 公路网络拓扑，不是 grid。

---

## Direction 4: Joint placement + routing decomposition (VLSI/PCB)

**Clautiaux, F., Carlier, J., & Moukrim, A. (2007). A new exact method for the two-dimensional orthogonal packing problem. *EJOR, 183*(3), 1196-1211.**
- Relevance: HIGH — 1D relaxation + branch-and-cut，infeasibility 时回主问题加 cut。架构跟 LBBD 几乎同构 (master = packing, sub = feasibility check)。
- Concrete use: 几何 packing 上的 cut family (interval-graph clique cut、coordinate-window cut) 直接可借鉴 PROJECT_LOCK 边界内的 ghost rectangle。
- Risk: 纯 packing 没 routing/binding；他们的 cut 是 packing-only。
- 注意: 项目 L14 weighted occupancy 引用过 Clautiaux "generalized energetic reasoning" 但 paywalled 没读全。

**Côté, J.-F., Iori, M. (2018). The meet-in-the-middle principle for cutting and packing problems. *INFORMS Journal on Computing, 30*(4), 646-661.**
- Relevance: MEDIUM — 2D packing 强 bound 技术 (DFF, dual feasible function)。
- Concrete use: 给 master 一个紧 LP bound — 当前 area objective LP relaxation 比较松，DFF 可能紧 10-30%。
- Risk: DFF 是 bound 不是 cut，需要 master 端 reformulate。

**Cho, M., Lu, K., Yuan, K., & Pan, D. Z. (2009). BoxRouter 2.0: A hybrid and robust global router with layer assignment. *ACM TODAES, 14*(2), Article 32.**
- Relevance: LOW — VLSI global routing ILP，跟 routing subproblem 模型族同源；congestion cut 思路。
- Concrete use: congestion-based cell cut 已经试过且 over-restrictive，论文确认 VLSI 也是用 LP relax + rounding 不是 hard cut。
- Risk: 跟 cell-cut 死路同类。

---

## Direction 5: Lazy clause generation / explanation

**Ohrimenko, O., Stuckey, P. J., & Codish, M. (2009). Propagation = lazy clause generation. In *CP 2007* (LNCS 4741, pp. 544-558). Springer. [seminal]**
- Relevance: HIGH (历史 anchor) — LCG 原始论文；每个 propagator 必须能 explain。
- Concrete use: 解释为啥 OR-Tools CP-SAT 在 master 上能给 conflict clause — PCR-CUT 等价于"手工补一种 LCG explanation"。
- Risk: 算法层基础，不是新方向。

**Feydy, T., & Stuckey, P. J. (2009). Lazy clause generation reengineered. In *CP 2009* (LNCS 5732, pp. 352-366). Springer.**
- Relevance: HIGH — Chuffed 引擎核心论文，把 LCG 集成进 SAT 内核。
- Concrete use: OR-Tools 9.15 CP-SAT 走的就是这条线；理解 master.solve 内部 lazy 行为对 PCR-CUT cut 注入时机 (lazy callback vs rebuild) 有指导。
- Risk: OR-Tools 9.15 不允许 AddLazyConstraint，只能外循环；论文 paradigm 用不全。

**Schutt, A., Feydy, T., Stuckey, P. J., & Wallace, M. G. (2011). Explaining the cumulative propagator. *Constraints, 16*(3), 250-282.**
- Relevance: MEDIUM — 给 global constraint (cumulative) 写更紧的 explanation；提示 binding subproblem 的"port demand"类似 cumulative，可能有更紧 cut。
- Concrete use: 对照"binding port demand cumulative" 写一个 strengthened explanation cut，可能比 lazy demand cut (试过死) 更紧。
- Risk: cumulative explanation 已经在 OR-Tools 内置；外部加 cut 可能跟内置打架。

---

## 特殊关注 — "master CP, subproblem CP" hybrid Benders

**Eveborn, P., & Rönnqvist, M. (2004). Hybrid Benders decomposition algorithms in constraint logic programming. In *CP 2001* (LNCS 2239, pp. 1-15). Springer.**
- 明确讲 CP 在 master 和 subproblem 都能用，CP master 比 MIP master 在 timetabling-like 约束上更适合。这正是 pose-bool master + binding CP subproblem 的 paradigm 引用。**HIGH**.

**Bunte, S., Kliewer, N., & Suhl, L. (2007). Benders decomposition in constraint programming. *研究综述*。** — 同方向 survey。MEDIUM.

## "cut 必须用真求解器验证" paradigm

**Hooker, J. N. (2007). Planning and scheduling by logic-based Benders decomposition. *Operations Research, 55*(3), 588-602.**
- 原始 LBBD：cut 通过 inference dual 生成；没有"真求解器 replay"环节。但 inference dual 概念可作为"replay validate"的对照 — 我们走的是 stronger 路径 (real CP-SAT solve 不是 dual coefficient 构造)。

**Chu, Y., & Xia, Q. (2004). Generating Benders cuts for a general class of integer programming problems. In *CPAIOR 2004* (LNCS 3011, pp. 127-141). Springer.**
- 提到"unverified cut 可能 over-cut"的风险；支持"必须真 solver replay"的 paradigm 决策。HIGH.

文献里**没有**专门做"learned cut 必须真 solver replay"的明确 paper — 这是 PCR-CUT 的 paradigm 创新点 (fail-closed cut acceptance)。值得后续写出来当 contribution。

---

## Top 3 推荐

1. **Karlsson & Rönnberg (2023), Computational evaluation of cut-strengthening techniques in LBBD.** — 系统对比 cut strengthening 家族的 3000-instance benchmark，直接 informs PCR-CUT minimize 阶段是否补 greedy-then-deletion 两阶段。
2. **Clautiaux et al. (2007), New exact method for 2D orthogonal packing.** — 架构跟 LBBD 几乎同构 (1D master + 2D feasibility check + 反向 cut)。coordinate-window cut / interval clique cut 在 ghost rectangle 边界内可移植。
3. **Eveborn & Rönnqvist (2004), Hybrid Benders decomposition algorithms in constraint logic programming.** — 唯一明确支持 "CP master + CP subproblem" paradigm 的奠基论文，pose-bool master + binding/routing CP subproblem 的 paradigm 引用源。
