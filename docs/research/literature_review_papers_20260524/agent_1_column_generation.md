# Agent 1 — Column generation / Branch-and-price 调研

**Agent ID**: a55268203c92cc1fa
**Model**: Opus
**Date**: 2026-05-24
**方向**: 支持 Cand C 列生成主线（Phase 1 GO）

---

## Direction 1: Branch-and-price stabilization

**Pessoa, A., Sadykov, R., Uchoa, E., & Vanderbeck, F. (2018). Automation and combination of linear-programming based stabilization techniques in column generation. *INFORMS Journal on Computing, 30*(2), 339–360.** https://doi.org/10.1287/ijoc.2017.0784
- Relevance: HIGH — canonical reference on auto-tuned smoothing + Wentges-style penalty combo; designed to remove parameter tuning, which matches "Phase 1 GO without manual knob hunting" stance.
- Concrete use: Cand C Phase 2 (post 4-ramp). Replace naive duals fed to pricing with auto-regulated smoothed duals; expected to kill the cycling flagged on naive CG.
- Risk: Assumes LP master with stable basis; pose-bool master is huge (280K vars). Smoothing math is solver-agnostic but the "best dual seen" memory grows O(rounds × |duals|).

**Pessoa, A., Sadykov, R., Uchoa, E., & Vanderbeck, F. (2013). In-out separation and column generation stabilization by dual price smoothing. In V. Bonifaci, C. Demetrescu, & A. Marchetti-Spaccamela (Eds.), *Experimental algorithms (SEA 2013)*, LNCS 7933 (pp. 354–365). Springer.** https://doi.org/10.1007/978-3-642-38527-8_31
- Relevance: HIGH — interior point variant; closed-form, no extra LP.
- Concrete use: m9 proxy dual norm currently used as ramp gate; in-out point gives a principled center to smooth toward.
- Risk: Interior point feasibility requires a known feasible dual; you must seed one (often easy via Lagrangean bound).

**Kraul, S., Seizinger, M., & Brunner, J. O. (2023). Machine learning–supported prediction of dual variables for the cutting stock problem with an application in stabilized column generation. *INFORMS Journal on Computing, 35*(3), 692–709.** https://doi.org/10.1287/ijoc.2023.1277
- Relevance: MEDIUM — predicts dual values from instance features for warm-starting; aligns with AI sidecar contract (hint-only, not proof).
- Concrete use: Lane C sidecar suggests pose-aggregated dual hints; can warm-start CG with a duals vector that already lives in the late-iteration region.
- Risk: Needs training data (multiple solved campaigns at smaller scales). Single-instance, so transfer unclear; treat as exploratory only.

**Uchoa, E. (2025). *Optimizing with column generation*.** (forthcoming book; Inria International Chair announcement, March 2025).
- Relevance: MEDIUM — Part II covers dual stabilization + limited-memory cuts; saves weeks of paper-by-paper reconstruction.
- Concrete use: Reference desk for Phase 1.2+ design review.
- Risk: Book, not vetted code.

---

## Direction 2: Column generation for 2D packing

**da Silva, R. F. F., & Schouery, R. C. S. (2024). Solving cutting stock problems via an extended Ryan–Foster branching scheme and fast column generation. *INFORMS Journal on Computing*.** https://doi.org/10.1287/ijoc.2023.0399 (Preprint: arXiv:2308.03595)
- Relevance: HIGH — most recent SOTA on CG for non-binary cutting stock; diversification-based fast CG + Ryan-Foster on non-binary masters is directly the situation (pose-bool ≠ binary partition).
- Concrete use: Phase 2 branching rule; "conflict propagation lemma" gives a principled way to branch on pose-bool fractional pairs.
- Risk: Their pricing is 1D bounded knapsack DP; you have CP pricing. Branching scheme transfers; pricing acceleration tricks may not.

**Silva, E., Oliveira, J. F., Silveira, T., Mundim, L., & Carravilla, M. A. (2023). The Floating-Cuts model: A general and flexible mixed-integer programming model for non-guillotine and guillotine rectangular cutting problems. *Omega, 114*, 102747.** https://doi.org/10.1016/j.omega.2022.102747
- Relevance: MEDIUM — first unified MIP for non-guillotine; not CG but gives strong compact formulation as comparison baseline.
- Concrete use: LP relaxation benchmark for m9 proxy dual; verify pose-bool LP bound dominates or matches.
- Risk: MIP not CG; cannot drop in.

**Belov, G., & Scheithauer, G. (2006). A branch-and-cut-and-price algorithm for one-dimensional stock cutting and two-dimensional two-stage cutting. *EJOR, 171*(1), 85–106.** — flagged HIGH historically; user already read Belov/Scheithauer.

---

## Direction 3: CP-based pricing in branch-and-price

**Fahle, T., Junker, U., Karisch, S. E., Kohl, N., Sellmann, M., & Vaaben, B. (2002). Constraint programming based column generation for crew assignment. *Journal of Heuristics, 8*(1), 59–81.** https://doi.org/10.1023/A:1013613309224
- Relevance: HIGH — foundational paper on CP-as-pricing-engine. CP wins when subproblem has many side constraints, which is exactly the case (port binding + routing).
- Concrete use: Validates Cand C's architectural choice; design patterns for reduced-cost objective in CP (penalty propagation on dual vector).
- Risk: 2002 era, no modern CP-SAT specifics; their CP solver was ILOG Solver. Pattern transfers, hand-tuning doesn't.

**Morrison, D. R., Sewell, E. C., & Jacobson, S. H. (2014). Solving the pricing problem in a branch-and-price algorithm for graph coloring using zero-suppressed binary decision diagrams. *INFORMS Journal on Computing, 26*(4), 695–709.** (Preprint arXiv:1401.5820)
- Relevance: MEDIUM — uses BDD (a CP-adjacent compact representation) for pricing on hard graph coloring; nearest analog to "CP pricing where DP doesn't fit".
- Concrete use: If Cand C pricing ever needs more compact column representation than pose-bool, ZDD is a known fallback.
- Risk: ZDDs blow up memory on dense conflict structure; 70×70 grid is dense.

---

## Direction 4: Set-packing strengthening

**Pecin, D., Pessoa, A., Poggi, M., & Uchoa, E. (2017). Limited memory rank-1 cuts for vehicle routing problems. *Operations Research Letters, 45*(3), 206–209.** https://doi.org/10.1016/j.orl.2017.02.006
- Relevance: HIGH — the "limited memory" trick is *the* reason modern BCP scales. Idea: lift rank-1 (Chvátal-Gomory) cuts but only over a memory set, so pricing stays tractable.
- Concrete use: Phase 2/3 cut layer on top of pose-bool master. Pose subsets ⇒ rank-1 CG cuts limited to anchor neighborhood.
- Risk: Cut separation needs hypergraph structure; need to define "row family" carefully. Worst case: cut adds DP state and kills pricing speedup.

**Landete, M., & Peiró, J. (2024). Some new clique inequalities in four-index hub location models. *EJOR, 318*(3), 768–777.** https://doi.org/10.1016/j.ejor.2024.04.014
- Relevance: MEDIUM — recent clique-cut lifting for 4-index assignment models; pose-bool is essentially 4-index (instance × orientation × x × y).
- Concrete use: Direct clique separation on pose-bool conflict graph (pairs of poses that share cells or violate port binding).
- Risk: Their proofs assume hub location symmetry; lift cautiously.

**Letchford, A. N., & Souli, F. (2020). On lifted cover inequalities: A new lifting procedure with unusual properties. *Operations Research Letters, 47*(2), 83–87.** https://doi.org/10.1016/j.orl.2018.12.005
- Relevance: MEDIUM — modern lifted cover lifting; pose-bool capacity constraints look like generalized knapsacks.
- Concrete use: Capacity rows (cells, ports, power) admit lifted cover cuts; add as user cuts.
- Risk: Strength depends on having tight capacity rows.

---

## Direction 5: Robust CG under hard combinatorial pricing

**Sadykov, R., Uchoa, E., & Pessoa, A. (2021). A bucket graph–based labeling algorithm with application to vehicle routing. *Transportation Science, 55*(1), 4–28.** https://doi.org/10.1287/trsc.2020.0985
- Relevance: HIGH — modernizes labeling for hard ESPPRC; key insight is bucketing the state space, transferable to CP pricing with tabling.
- Concrete use: If CP pricing ever rewritten in a more structured DP-like form, this is the SOTA recipe.
- Risk: Their setting is sequence-dependent (routing). Pricing is configurational. Transfer is conceptual, not code.

**Pessoa, A., Sadykov, R., Uchoa, E., & Vanderbeck, F. (2020). A generic exact solver for vehicle routing and related problems. *Mathematical Programming, 183*, 483–523.** https://doi.org/10.1007/s10107-020-01523-z
- Relevance: HIGH — VRPSolver paper; codifies BCP design when pricing is NP-hard. Explicit treatment of master cleanup + rounding + ng-paths.
- Concrete use: Reference architecture for Cand C Phase 2 wiring (master heuristics + pricing budget + cut layer interaction).
- Risk: Their codebase is BaPCod-specific; design patterns apply, code does not.

---

## Top 3 by ROI

1. **Pessoa et al. (2018), Automation and combination of stabilization** — drop-in math for naive-CG cycling; weeks of avoided trial-and-error on Phase 2. Implementation cost: ~3–5 days. ROI: very high.
2. **da Silva & Schouery (2024), Extended Ryan-Foster + fast CG (arXiv:2308.03595)** — directly answers "how to branch on non-binary pose-bool master after root CG converges". Their conflict propagation lemma is portable.
3. **Fahle, Junker, Karisch, Kohl, Sellmann & Vaaben (2002), CP-based CG for crew** — validates architectural bet that CP pricing beats DP/LP pricing. Low implementation cost (already doing it); reading gives vocabulary + risk taxonomy for Phase 1.2 design review.
