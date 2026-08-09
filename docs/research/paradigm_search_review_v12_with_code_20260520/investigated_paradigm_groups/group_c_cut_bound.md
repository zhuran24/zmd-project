# Group C — Cut/Bound Theory (4 paradigm, 全 NO-GO)

调研覆盖 lift-and-project hierarchy / PBO / MaxSAT / FourierCSP 等 cut/bound 加强方向. 校验后 verdict.

## C1: Lift-and-project hierarchy (Sherali-Adams / Lasserre / LS+)

- **State**: 2024-2025 主流方向是 sparsity-exploiting (TSSOS / CS-TSSOS / multi-ordered) 把 SDP 拆 block, 仍依赖 polynomial structure.
- **Paradigm**:
  - Sherali-Adams (SA): LP-based lift-and-project, level-d 把所有 r ≤ d 的变量乘积加入, LP 变量数 O(n choose d)
  - Lasserre / Moment-SOS: SDP-based, level-d 的 PSD 矩阵尺寸 O(n choose d), 比 SA 紧但贵
  - LS+ 介于两者之间
- **Fit 致命问题**: n ≈ 250,000 binary. SA level-2 LP 已 O(n²) = **6.25×10^10 vars**. Lasserre level-2 SDP 矩阵 ≈ 6.25×10^10 entry. **单机 48 GB 内连 build 都不起来**.
- **literature industrial 案例**: sparsity-exploit 后能上 n=10³-10⁴ (e.g. OPF). 我们 n=2.5×10⁵ + 全局耦合 (power/connector/ghost) → **超 sparsity-exploit 边界 1-2 数量级**.
- **校验后 caveat**: sub-agent 引用的 arxiv 2101.05167 经校验是 "Sublevel Moment-SOS Hierarchy" 不讲 Sherali-Adams / OPF / sparsity n=10³-10⁴, 反方向论证 "standard Lasserre 或 sparse variant computationally intractable". **sub-agent 错引 paper**, 但 paradigm verdict NO-GO 整体方向仍对 (n=250K 远超 sparsity 极限).
- **Verdict NO-GO**: 物理 scale 不可达, 4-8 周 PoC 出 build OOM verdict. CVXPY+MOSEK / SDPA / TSSOS 不直接接 OR-Tools CP-SAT.

## C2: Pseudo-Boolean Optimization (PBO)

- **State**: PB Competition 2024 — SCIP/FiberSCIP 赢 5/6 category (759 / 776 of 1207 instances). RoundingSAT 是 backbone (12 best solvers 里 9 个用 RoundingSAT).
- **Paradigm**: 0-1 ILP 专用 + cutting planes proof system (addition + saturation/division, 比 resolution 强), CDCL on PB constraints.
- **vs CP-SAT**: 我们 model 99% BoolVar + linear constraint, 本来就在 PB 子集. 换 PBO 换的是底层证明系统 + 求解引擎, 不改 LBBD master/cut 结构.
- **Fit 关键问题**: 项目瓶颈不是 propagation 弱, 是 paradigm-level cut 表达力. PBO 不改 master/cut 维度 — paradigm 同质死.
- **Lex objective**: PBO 标准要 2-stage solve (固定 area→optim min_side) 或 lex encoding.
- **Verdict NO-GO**: PB24 SCIP 759/1207 ≈ 63% success rate — **没有 "换 solver 就解开" 的证据**. SCIP 是 MIP family, 不是 paradigm shift. 2 周重写 OPB + LBBD 适配, ROI 太低.

## C3: MaxSAT / Weighted Partial MaxSAT (lex optimization)

- **State**: MaxSAT 2024 SOTA = CashWMaxSAT IJCAI 2025 (Pan/Wang/Cai 北师大) core-guided + 异步 stratification + disjoint cores. EvalMaxSAT 2024 portfolio strategy = **SCIP 400s + 自身 3200s** (3600s total) — 这是 EvalMaxSAT 策略, **校验后确认** (sub-agent 之前 README 误报 → 实际策略在 evaluation paper 里).
- **Paradigm**: MaxSAT 强项是 weighted soft clause + core-guided. Lex 操作化 = weighted MaxSAT 高/低权重编码 (priority₁ weight ≫ priority₂), 或 multi-objective MaxSAT 框架 (Jabs et al. 2025 Pareto certification arxiv 2501.17493).
- **Fit 致命问题**:
  - MaxSAT 无 CP propagator — no AllDifferent / no flow / no diffN
  - port_clearance / power_coverage / connectivity 全靠 clause+cardinality 展开 — encoder size 爆炸 (CP-SAT 4 lines 表达的 routing 约束, MaxSAT 要 O(n²) clauses)
  - Historical facility layout benchmark 上限 **~13 departments** (n×n grid 不超过 ~30). 我们 70×70 + 266 facility + 10 commodity 远超 paradigm scale
  - MaxSAT Eval 2024 benchmark 集没收 layout/placement track — paradigm 不 fit
- **Verdict NO-GO**: 重写 master + binding 为 WCNF (~2000 LOC) + cardinality encoder + 砍 routing/flow 约束 → 6-8 周 paradigm investment + 大概率 model build 几小时 RAM 100+ GB.

## C4: Constraint reformulation / FourierCSP / Hexaly (2024-2025 新 paradigm)

- **FourierCSP** (arxiv 2510.04480): Walsh-Fourier 把离散 CSP 转连续 GPU 梯度上升, CP-SAT 13.88x 加速 (sub-agent 报数字 + "非结构不 work" caveat, **abstract 前 3 页未支持具体数字 / caveat 字眼, 部分 unverified**).
- **Lazy Linear Generation (LLG)**: CP solver 把 cutting plane 整合进 conflict analysis 生成 linear inequalities, 45% benchmark 降冲突.
- **Hexaly** (LocalSolver 改名 2023-11): column generation + local search + MIP/NLP/CP hybrid 商业 solver. **校验后 confirmed** = LocalSolver 改名 (Hexaly 13.0 2024-07 切换, Hexaly 14.0 mid-2025 LocalSolver API 完全 disappear).
- **Fit 致命问题**:
  - FourierCSP benchmark 是 task scheduling/graph coloring 结构化稀疏, paper 自承非结构模式不 work (sub-agent 推断, unverified). 我们 2D facility 2.7M dense cstr 不 fit
  - LLG 仍 cut-based, 跟项目 24 lever cut 同质死风险
  - **Hexaly 纯启发式 gap 路径**, 无 certified optimal proof — 违 PROJECT_LOCK certified_exact (确认)
- **Verdict NO-GO**: 三个全 fit 度低或违 LOCK. 不投资新 paradigm.
