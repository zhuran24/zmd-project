# Group F — 2026 Window Extra (2026-01 ~ 2026-05 调研)

第二批 8 个 sub-agent 校验补充 2026-01~05 时间窗. 大部分 finding 已 merge 进 group A-E 或 candidates/. 这里列**仅在 2026 窗口找到的 extra finds** + paper 校验状态.

## F1: arxiv 2601.06542 — RCPSP LBBD (2026-01)

- **Title**: "Resource-constrained Project Scheduling Logic-based Benders Decomposition (with Time-of-Use Energy Tariffs and Machine States)"
- **校验后**: arxiv ID 存在 ✅, 日期 2026-01-10 ✓, ILP master + CP subproblem ✓, RCPSP + 电价 ✓
- **vs project**: 跟项目同 LBBD framework 但 domain 是 RCPSP 调度 + 电价, 不是 2D placement. **没新 cut form, 标准 no-good**. paradigm 项目已 24 lever 覆盖 (Path 12 RAB-SEP / Path 17 D2 同结构).
- **Verdict NO-GO**: 不同 domain, paradigm 已穷尽.

## F2: arxiv 2604.20338 — Column Generation for Quantum Network Switching (2026-04)

- **校验后**: arxiv ID 存在 ✅, 跟 2D placement domain 完全不沾边
- **Verdict NO-GO**: 不相关 domain.

## F3: AAAI 2026 录用 (4167 paper)

- **校验后**: papers.cool 确认 CSO track **35 篇**. 但 "4167 总数" 未在此页验证 (仅 CSO 子集).
- **跟项目相关 paper** (除 lever 25 IHS 之外):
  - **A GPU-based Constraint Programming Solver** (CSO #24): GPU interval bound propagation + backtracking. **硬件加速, 用户已明排除硬件方向**
  - **Assignment Problems in Cost Function Networks** (CSO #23): soft arc consistency + AllDifferent linear assignment QAP. 跟项目 facility-to-pose assignment 结构相似但 paradigm 同 CP 项目已用
  - **Constraint Optimization of MicroPlate Designs** (CSO #14): discrete plate layout, paradigm 不详
- **Verdict NO-GO** (除 lever 25 IHS 已升候选): 其他 paper paradigm 跟项目 fit 度低或违硬件 constraint.

## F4: ICAPS 2026 accepted list

- **校验后**: 列表已公开, ~90 paper. Sample title 多为 HTN / MAPF / LLM-planning, **跟 max empty rect / packing 几乎无关**.
- **GPMS** (Generalized Parallel Machine Scheduling Framework with Rich Temporal and Resource Constraints, Frühwirth et al.): 复杂资源约束 + CP 框架, 跟项目 power/port/connector 多资源耦合结构相似但 domain 不同
- **Verdict NO-GO**: 对项目 ROI 低.

## F5: arxiv 2604.00094 — Sparse Learning for MIP Branching (2026-03)

- **Title**: "Speeding Up MIP Solvers with Sparse Learning for Branching"
- **校验后**: arxiv ID + 作者 (Bayramoğlu/Nemhauser/Sahinidis) + 2026-03-31 ✓. < 4% GNN 参数, CPU-only 比 GPU GNN 快, SCIP-targeted.
- **保 exactness** ✅
- **Fit caveat**: SCIP-specific, **OR-Tools CP-SAT 不暴露 branching callback 接口**, 改造门槛高. 加速数字 paper 未给具体百分比.
- **Verdict NO-GO**: 工业 instance 不在 paper benchmark 重点 (paper 测的是 standard MIP benchmark). 类似 ML branching 方向 (D step 2 community blueprint hint) 已实测 master inherent 难解.

## F6: arxiv 2603.07176 — Learning to Rank SAT Initial Branching (2026-03)

- **Title**: "Learning to Rank the Initial Branching Order of SAT Solvers"
- **校验后**: arxiv ID + 作者 + 2026-03-07 ✓. GNN 一次 forward 给变量评分 → 初始化 VSIDS activity (预处理一次性).
- **保 exactness** ✅
- **Fit 致命问题**:
  - 加速实测: 随机 3-CNF >50%, G4SATBench 10-20%, **工业实例 fail** (sub-agent 误报 "工业 0.8% 收益" — 校验后 paper 摘要承认**"工业 instance fail"**, **方向相反**)
  - 我们 70×70 ghost rectangle + 266 facility 属于 large structured industrial 类
- **Verdict NO-GO**: ML hint paradigm 在 industrial 工业级别 fail, 类似 D step 2 community blueprint hint 同 quality regime.

## F7: arxiv 2604.22107 — RL-aided Benders (2026-04)

- **Title**: 校验后 confirmed **"A Hybrid Reinforcement and Self-Supervised Learning Aided Benders Decomposition Algorithm"** (不只 RL, 是 RL + self-supervised hybrid)
- **校验后**: 2026-04-23 ✓. 57.5% solve time reduction. **paradigm 是 GBD (generalized Benders) 不是 LBBD** (校验后 caveat).
- **Verdict NO-GO**: GBD 跟项目 LBBD 不同 framework, 移植要重写 master + cut form, paradigm 跟项目 24 lever cut 表达力 root cause 不对症.

## F8: Hierarchical Rectangle Packing (arxiv 2512.20239, 2025-12) — 已 candidate B 排除

- **校验后**: paper 真实, Grus/Hanzálek/Artigues/Briand/Hebrard, 7 hierarchy levels.
- **关键 caveat**: **paper 自报 "This heuristic method dynamically refines block dimension constraints"** — 是 heuristic 不是 exact.
- **Verdict NO-GO**: 违 PROJECT_LOCK certified_exact. 之前在 candidates/ 列为 candidate B, 校验后 reclassify 排除.

## CPAIOR 2026 未覆盖窗口

- 5-26 召开 (在我们 2026-05-20 调研之后), 录用 paper 5 月才会公开
- 如果有真新 paradigm 在 CPAIOR 2026, 此包未覆盖
- 时间窗口 caveat 在独立 prompt 文件已显式标
