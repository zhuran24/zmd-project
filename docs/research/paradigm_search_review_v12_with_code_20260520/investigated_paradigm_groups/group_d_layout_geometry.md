# Group D — Layout / Geometry Specific (5 paradigm, 全 NO-GO)

调研覆盖 VLSI / 2D BPP / max empty rectangle / global constraints / symmetry breaking 等 layout 特定 paradigm. 校验后 verdict.

## D1: VLSI placement / floorplanning algorithms

- **State 工业级 (1M+ cells)**: DREAMPlace / RePlAce — analytic placement (梯度下降 + electrostatic density model) + GPU. **全启发式**, 无 optimality 保证. ICCAD 2024 仍调 initialization (GiFt) / macro 2-stage flow. 校验后 confirmed = "DREAMPlace may not guarantee legalizable placements ... stuck in local optima".
- **State exact 小规模**: Hougardy/Funke/Schneider 2015 (Bonn) branch-and-bound exact wirelength placement — 校验后 confirmed paper 跑到 **industrial instance with 27 rectangles**. 历史上 Korf 跑到 32 squares (special problem class). Onodera 最大 6 rectangles.
- **Topology encoding**: B*-tree / Sequence Pair / O-tree / TCG — 拓扑 encoding (相对位置 + compaction), 不固定 grid. 自然 non-overlap; 但**不直接处理离散 cell-level (grid) constraint** (power coverage / port adjacency 这类邻接约束很难表达). 多跟 SA / GA / RL pair 用, 启发式.
- **Fit 致命问题**:
  - 拓扑 encoding 抽象掉 grid cell semantics, 我们 power_coverage / port-direction / 7-mandatory-types 都需 cell semantics
  - analytic placement 不可证违 PROJECT_LOCK certified
  - exact paradigm 跟我们 CP-SAT + Benders 同 paradigm, 实测天花板 20-35 cells, 我们 266 远超
- **Verdict NO-GO**: VLSI paradigm 已穷尽对我们的启发. 1M cells 业界共识 "exact 只能局部, 全图靠启发式".

## D2: 2D Bin Packing / Strip Packing exact

- **State 2024-2025 SOTA**: branch-and-price-and-cut + arc-flow (Carvalho 1999 → Delorme/Iori/Martello → VRPSolver) 主要 1D / 2D-rectangle 受限. 2D 专门: ktnr/BinPacking2D (Gurobi+CP-SAT no-good cut), GEOM-BP (geometric B&P), Hierarchical LBBD (arxiv 2512.20239 — 校验后 heuristic 不 exact, 已排除).
- **Library**: BPPLIB (1D-focused), 2DPackLib (Springer 2021, 学术 distribution).
- **Paradigm vs project**: BPP 主流 = 多 bin × 异构 rect items, 优化 = min bin count. 项目 = 单 bin (70×70) + 固定 266 items + 多 pose + 复杂 side-effect (port/power/connector), 优化 = max empty rect.
- **arc-flow / column generation 假设**: item 同质可枚举 pattern. 项目 facility 异构 + power/port 强耦合, **pricing subproblem 没法 decompose**.
- **Polyomino packing 复杂度**: FUN 2018 (Bodlaender & van der Zanden) ETH-based tight bound **2^{O(n/log n)}** 既下界又上界. n=266 直接 intractable.
- **Verdict NO-GO**: (a) 文献 SOTA 全 multi-bin/homogeneous item; (b) Hierarchical LBBD 2025 同 LBBD framework + heuristic 违 LOCK; (c) 复杂度 lower bound 自身 intractable.

## D3: Computational geometry — Max Empty Rectangle

- **经典算法**: 1983 Naamad-Lee-Hsu O(n²) → 1986 Chazelle-Drysdale-Lee O(n log³ n) → 2021 Chan O(n·2^O(log*n)·log n) best (point obstacles, area-only).
- **校验后 confirmed**: Chan 2021 paper 真实 (arxiv 2103.08043), point obstacles + area-only.
- **Square variant**: Θ(n log n).
- **Rectangular obstacles**: 1990 起有扩展但复杂度分析稀疏, 无 production library.
- **数学结果能否 prune 项目 search**:
  - 能 prune 的: maximal property (rect 4 边必 abut 障碍) + dominance — **这两条项目 outer_search.py 已经在用** (candidate frontier 走 maximal anchor)
  - 不能 prune 的: 经典 MER 假设 **obstacles 固定**, 我们 266 facility 位置是**决策变量** — paradigm 完全不同. lex(area, min_side) tie-break 文献**零结果**
- **Verdict NO-GO**: paradigm 解决项目子问题 (ghost rectangle 几何枚举, 已在用), 不解 facility placement + 摆放耦合. Chan 2021 优化把 ghost rect 枚举 O(n²)→O(n polylog n), n=70² 时绝对时间 μs 级, 对 master.solve 瓶颈 0 影响.

## D4: Constraint geost / diff2 / disjoint2 (CP-specific 2D global constraints)

- **OR-Tools CP-SAT 现状**: 用 `AddNoOverlap2D` (+ `set_use_cumulative_in_no_overlap_2d`) = 等价 SICStus `disjoint2` / MiniZinc `diffn` 一档. 固定矩形 + sweep + cumulative redundant relaxation. Perron 2022 原话确认.
- **geost** (Beldiceanu+Carlsson+Poder+Sadek+Truchet CP'07, **5 author 非 7** — 校验后 sub-agent 误报): polymorphic k-dim object + generic sweep kernel + longest_hole / visavis / dynamic_programming / polymorphism 等多档 filter. SICStus 4.3 reference. Choco/JaCoP 部分子集.
- **vs CP-SAT NoOverlap2D**: geost 严格上位 paradigm (polymorphic shape). 项目 facility 多 pose = 天然 polymorphic shape, geost 原生表达.
- **Fit 致命问题**:
  - OR-Tools **没有 geost 接口**, CP-SAT 内部也没 sweep-polymorphic propagator. 只能换 solver.
  - SICStus 商业 + Prolog 栈, 整体重写不现实. Choco/JaCoP 没完整 geost (PolyMorphic 只在 SICStus 4.x).
  - 真用 geost = paradigm shift to Prolog/SICStus, 估 4-8 周重写 master + 失去 CP-SAT LP relaxation / lazy clause / SAT-side 优势
- **Verdict NO-GO**: geost paradigm-level 确实更强 (polymorphic + 多档 filter), 但 (a) OR-Tools 不提供; (b) SICStus 替换代价 >> 当前剩余路径 ROI; (c) 项目瓶颈不是 placement propagation 强度 (pose-bool master 50-100s OPTIMAL), 是 LBBD cut 表达力 — geost 不解 cut 侧问题.

## D5: Advanced Symmetry Breaking (跟 candidates/lever_26_benders_symmetry 不同方向)

注: 候选 lever 26 (Benders 框架内 symmetry framework) 是**跨 master+sub-problem 联合**. 这里 D5 是 **master 内 symmetry breaking** (无跨层).

- **Paradigm**:
  - **静态 lex** (现有项目用): O(1) 编码, lex-leader 完备性 NP-hard, 实际不完备
  - **SBDD** (Fahle/Schamberger/Sellmann + Gent generic): 树搜索 runtime dominance check, 2-6 generator → GAP 自动展开, 完备但需 solver hook (CP-SAT 闭源不暴露 node callback)
  - **Certified aux-var orders** (Anders 2025 arxiv 2511.16637): 用辅助变量编码 order, **校验后 confirmed 是 SAT + VeriPB 不含 MIP** (sub-agent 误报 "SAT/MIP 兼容")
  - **nauty / Bliss / Saucy / SAUCY3**: 自动 detect, 输出 generator → 喂给上面方法
- **Fit 致命问题**:
  - CP-SAT 不暴露 search node hook → SBDD ❌
  - 项目 symmetry **已知** (facility 类型/pose), nauty auto-detect 收益低
  - aux-var certified order: 可在现 pose-bool master 内加 lex(pose_i, pose_j), 但**项目 master.solve 时间已 50-100s fast, 边际收益 <10%**
  - 不修复 binding/routing reject 端语义 gap
- **Verdict NO-GO**: 真瓶颈是 LBBD cut 表达力不足 (cut 退化 size=1), 不是 master search space. 跟 Path 17 D2 同质死法风险高.
