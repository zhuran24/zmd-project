# Agent 4 — 未尝试 paradigm 候选调研

**Agent ID**: aafb98bbac9f82ba7
**Model**: Opus
**Date**: 2026-05-24
**方向**: PB / MaxSAT / DD / 2D packing exact / SDP / presolve — 27 paradigm 死后未试方向

---

## 1. Pseudo-Boolean Optimization Solvers（最高优先级）

### 1.1 Devriendt et al. — Cutting to the Core of Pseudo-Boolean Optimization (RoundingSat 现代版)

- Citation: Devriendt, J., Gocht, S., Demirović, E., Nordström, J., & Stuckey, P. J. (2021). Cutting to the core of pseudo-Boolean optimization: Combining core-guided search with cutting planes reasoning. *AAAI*.
- Relevance: HIGH。RoundingSat 是 PB Competition 2024 OPT-LIN 类 8/10 top solver 的 base，cutting planes proof system 比 resolution 指数强；项目 master 现 form 几乎就是 pure 0/1 + linear，PB 是天然 fit。
- Concrete use: PoC 5-8 day。把 pose-bool master 直接 dump 成 OPB 格式（RoundingSat 输入），跑 native PB solver。不需要重写架构，dump_opb 一个 export 函数 + cli wrapper。
- Risk: PB solver 单线程 + 没有 CP-SAT 的 LNS portfolio；如果项目瓶颈是 search heuristic 而非 propagation strength，PB 可能不见得快。需 Phase 0 在 20-inst 子问题验。

### 1.2 Hoen et al. — SCIP for PB Solving (PB Competition 2024 冠军)

- Citation: Hoen, A., Maher, S. J., Müller, B., Salvagnin, D., Sofranac, B., & Witzig, J. (2025). State-of-the-art methods for pseudo-Boolean solving with SCIP. *arXiv:2501.03390*.
- Relevance: HIGH。SCIP/FiberSCIP 在 2024 PB Competition 6 类中赢 5 类，1207 instance 解 759（FiberSCIP 776）。**比 RoundingSat 更强**因为 SCIP 集成 PaPILO presolve + cutting planes + branch-and-bound + 平行 UG。
- Concrete use: PoC 3-5 day（pyscipopt 已有）。把 master 用 pyscipopt 重建（API 比 CP-SAT 略繁但成熟），开 PaPILO 预处理。之前 HiGHS 死是因为 dense linear 不适合 LP-MIP，但 **SCIP PB mode 走的是 cutting planes 不是 LP simplex**——跟 HiGHS 死因不同 paradigm。
- Risk: 需要重新 binding/routing subproblem 的 interface（如果保留 LBBD）；或者整个 monolithic SCIP（master + 全 constraint 一起，会撞 RAM）。Phase 0 必须先量 monolithic RAM。
- URL: https://arxiv.org/abs/2501.03390

### 1.3 Oertel et al. — Practically Feasible Proof Logging for PB Optimization

- Citation: Oertel, A., Gocht, S., Myreen, M. O., Tan, Y. K., & Nordström, J. (2025). Practically feasible proof logging for pseudo-Boolean optimization. *CP 2025, LIPIcs Vol. 340*.
- Relevance: HIGH。VeriPB + CakePB formally verified proof checker，RoundingSat proof overhead 中位数 2.7%，95th percentile <21%。**这是项目"certified_exact"路径的天然 backbone**——能给 machine-checkable 证书，比 CP-SAT 自己的 INFEASIBLE/OPTIMAL 标签强。
- Concrete use: 中长期 (4-8 week)。短期意义不大，长期如果 PB paradigm GO 了，这就是 cert 系统升级。
- Risk: 只有当 PB solver paradigm 本体先 GO 才有意义。

### 1.4 Pseudo-Boolean Competition 2024 / 2025

- Citation: Le Berre, D., & Roussel, O. (Eds.). (2024). Pseudo-Boolean Competition 2024. CRIL, Univ. Artois.
- Relevance: MEDIUM (benchmark reference, not algorithm)。478 OPT-LIN benchmark，可以直接拿项目 master 编码进去横向比 RoundingSat / SCIP / Sat4j-PB / NaPS / Exact 5 个 solver。
- Concrete use: 1-2 day 验证 testbed。
- Risk: 无。
- URL: http://www.cril.univ-artois.fr/PB24/

---

## 2. MaxSAT Solvers

### 2.1 Ignatiev et al. — RC2

- Citation: Ignatiev, A., Morgado, A., & Marques-Silva, J. (2019). RC2: An efficient MaxSAT solver. *Journal on Satisfiability, Boolean Modeling and Computation, 11*(1), 53–64.
- Relevance: MEDIUM。Core-guided OLL，长期 MaxSAT-Eval winner。但 MaxSAT 把 linear constraint 编 cardinality network 后膨胀严重，266 mandatory × pose 数 × cell 数会爆炸。
- Concrete use: 7-10 day（要写 WCNF encoder + cardinality network）。
- Risk: encoding 膨胀 → 解空间反而比 PB 大。**PB 严格优于 MaxSAT 对 linear-heavy 问题**。

### 2.2 Avellaneda — EvalMaxSAT

- Citation: Avellaneda, F. (2020). EvalMaxSAT: A MaxSAT solver based on OLL. *MaxSAT Evaluation 2020 Solver Descriptions*.
- Relevance: LOW-MEDIUM。同 RC2 同家族，weighted MaxSAT top performer。同样受 encoding 膨胀拖累。

### 2.3 Soh et al. — SAT/MaxSAT for 2D Strip Packing

- Citation: Soh, T., Banbara, M., Tamura, N., & Le Berre, D. (2017). Solving multiple-block strip packing using SAT-based techniques. *Pesquisa Operacional*.
- Relevance: MEDIUM。实证 MaxSAT 对 2D strip packing 有效——跟 problem family 接近，但 strip packing 比 max empty rectangle 简单（没 facility + binding + routing）。
- Concrete use: 参考 encoding 思路（hard clause 包结构 / soft penalize 目标）。
- Risk: max_lex 目标不是单变量最小化，需要 lex 分解两次解。

---

## 3. Decision Diagrams (BDD / MDD)

### 3.1 van Hoeve — 2024 INFORMS Tutorial

- Citation: van Hoeve, W.-J. (2024). An introduction to decision diagrams for optimization. *Tutorials in Operations Research, INFORMS*.
- Relevance: MEDIUM。Relaxed MDD 提 dual bound + Restricted MDD 提 primal bound，paradigm 跟 CP-SAT 完全正交。
- Concrete use: **PoC 2-3 week**（写 state DP + merge rule + width control）。**只对"分层 DP-friendly"问题 work** — 70×70 grid 没明显的 layer ordering（266 instance 不是 sequential）。
- Risk: **HIGH**——MDD 强在 sequence/scheduling/routing，2D grid placement 没有自然 stage 划分。可能 m1=2 同样问题。

### 3.2 Coppé et al. — Lookahead Merge Reduce (2024)

- Citation: Coppé, V., Gillard, X., & Schaus, P. (2024). Lookahead, merge and reduce for compiling relaxed decision diagrams for optimization. *CPAIOR 2024, LNCS 14743*.
- Relevance: LOW。同上 MDD risk。

---

## 4. 2D Orthogonal Packing Exact Methods

### 4.1 Clautiaux et al. — New Exact Method for 2D Orthogonal Packing

- Citation: Clautiaux, F., Jouglet, A., Carlier, J., & Moukrim, A. (2007). A new exact method for the two-dimensional orthogonal packing problem. *EJOR, 183*(3), 1196–1211.
- Relevance: LOW-MEDIUM。经典 dichotomic search + interval graph 推断，对 fixed-size rectangle 强。**但 facility 不是任意 rectangle**——有 pose、port、power、connector，比 OPP 复杂一个 paradigm 层。
- Concrete use: 参考 dichotomic relaxation（每个 instance 投影到 1D 算 1D bin-packing lower bound）。
- Risk: 投影 lower bound 跟 cert 要求差距大；可能复用其 lower bound 当 cheap dual bound。

### 4.2 Fekete et al. — Higher-Dimensional Orthogonal Packing

- Citation: Fekete, S. P., Schepers, J., & van der Veen, J. C. (2007). An exact algorithm for higher-dimensional orthogonal packing. *Operations Research, 55*(3), 569–587.
- Relevance: LOW。跟 4.1 同问题但维度泛化，没解额外约束。

---

## 5. SDP Relaxations

### 5.1 Brosch & de Klerk — SDP Bounds via ADMM and Lasserre

- Citation: Brosch, D., & de Klerk, E. (2024). SDP bounds on the stability number via ADMM and intermediate levels of the Lasserre hierarchy. *arXiv:2506.08648*.
- Relevance: LOW。Stability number ≈ max independent set，跟"max empty rectangle"有几何相似性，但 SDP 实际 tractable 只到 300 顶点。70×70 = 4900 cell × 266 pose 远超 SDP scope。
- Concrete use: 不建议。
- Risk: scale 不匹配。**SDP paradigm 对项目体量 hard kill**。

---

## 6. Presolve / Preprocessing

### 6.1 SCIP 10.0 / PaPILO

- Citation: Achterberg, T., et al. (2025). SCIP Optimization Suite 10.0: Exact solving, better decompositions, and a more productive ecosystem. *ZIB Report*.
- Relevance: HIGH (paired with §1.2 SCIP PB)。PaPILO 做 coefficient strengthening, probing, dual proof analysis, parallel presolve。CP-SAT 自己的 presolve 强但**没暴露 LP-level proof analysis** 这一类操作。
- Concrete use: 不是独立 paradigm，是 §1.2 SCIP 路径自带 bonus。
- Risk: 跟 SCIP path 绑定。

---

## 7. Local Search with Dual Certificates

### 7.1 Lozano & Smith — Branching Dual

- Citation: Lozano, L., & Smith, J. C. (2022). Optimization bounds from the branching dual. *INFORMS Journal on Computing*.
- Relevance: LOW-MEDIUM。Dual 解作为 partial branching tree，local search 在 dual space 上跑给 valid bound。理论漂亮，**没成熟开源实现**。
- Concrete use: 自研 2-3 week。
- Risk: 没现成 tooling。

---

## Top 3 Paradigm 推荐（ROI 排序）

### #1 — SCIP-PB Native Solver（最高 ROI）

**为什么**: PB Competition 2024 实证冠军 + PaPILO presolve 别处没有 + 已有 Python 绑定 (pyscipopt) + 跟项目 master form 1:1 对齐 + HiGHS 死因（dense LP simplex）跟 SCIP-PB（cutting planes + branch-and-bound）完全不同 paradigm。

**Cheap gate (Phase 0, 1-2 day)**:
1. 写 `master_to_opb.py`：把现 pose-bool master dump 成 OPB 文件（PB Competition 标准格式）。
2. 跑 20-inst sub-instance（cand C Phase 0 同 testbed），SCIP-PB + RoundingSat 各一遍。
3. GO 判定：SCIP-PB **30s 内** 给 OPTIMAL/INFEASIBLE 8/8 同 cand C Phase 0 baseline。
4. KILL 判定：SCIP-PB > 5 min UNKNOWN 或 build RSS > 8 GB。

**风险**: monolithic（master + binding + routing 一起进 SCIP）撞 RAM；缓解 = 保留 LBBD 但把 master 换 SCIP-PB，subproblem 仍 CP-SAT。

### #2 — RoundingSat 直接替换 master.solve（次高 ROI）

**为什么**: RoundingSat 是 PB Competition 2024 OPT-LIN 80% top solver 的核心，单 binary 入侵小，proof logging（VeriPB）顺带升级 cert 系统。比 SCIP 轻——单一可执行文件、subprocess 调即可。

**Cheap gate (Phase 0, 1 day)**:
1. 同 #1 dump OPB。
2. RoundingSat binary 跑 20-inst。
3. GO 判定：8/8 < 60s OPTIMAL/INFEASIBLE。
4. KILL 判定：> 5 min UNKNOWN 或编码后 > 5M clauses（说明 encoding 膨胀）。

**风险**: RoundingSat 单线程，CP-SAT 8 worker 抹掉一些差距；但 RoundingSat 单 thread 解空间收敛性比 CP-SAT BCP 在 cutting planes proof system 上指数强。

### #3 — Clautiaux 2D Orthogonal Packing dichotomic lower bound 当 dual bound 注入（备选低 ROI 但确定性高）

**为什么**: 不是替换 paradigm，是给现 CP-SAT 注入 cheap dual bound。1D 投影 dichotomic 算每个 row/column 的 bin-packing lower bound，作为 master 额外 cut。

**Cheap gate (Phase 0, 0.5 day)**:
1. 单独脚本：266 instance + 70×70 row-wise / column-wise 投影，跑 1D bin-packing LB（Martello-Toth lower bound）。
2. 对 cand C Phase 1 GO 的 4 candidate 比较 dual bound 紧度。
3. GO 判定：LB 给的 dual ≥ 当前 CP-SAT root LP relaxation dual 在至少 2/4 candidate 上更紧。
4. KILL 判定：dual 全等于或弱于 CP-SAT。

**风险**: 即使 GO 也只是 marginal 提速，不是 paradigm shift；适合 #1/#2 都死后的兜底。

---

**总结**: PB solver paradigm（#1 SCIP + #2 RoundingSat）是 27 死方向后**未被项目尝试过的最大算法层缺口**，且跟 cand C column generation 正交可叠加。Cheap gate 总成本 < 3 day，命中率取决于编码膨胀，需 Phase 0 实测。
