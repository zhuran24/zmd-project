# Group A — Solver Families (8 paradigm, 全 NO-GO)

调研覆盖 CP-SAT 同档 / 不同代 / 不同 paradigm family 的 production solver. 校验后 verdict.

## A1: Choco-solver (Java CP)

- **Version state**: Choco 6.0.0 (2026-05-05 release), pychoco PyPI 三平台 (GraalVM native-image, Py 3.8-3.14). macOS 限 ARM64 + Linux 需 glibc 2.34+.
- **Paradigm**: 历史 propagator-based, 6.0 引入 LCG. Choco 自称 "CP-SAT in Choco-solver".
- **vs CP-SAT**: 同 LCG family. MiniZinc Challenge 2024 OR-Tools 5/5 gold vs Choco silver/bronze.
- **Verdict NO-GO**: 同 family solver paradigm 同质 (LCG), 实测 benchmark 较弱; 项目重写成本 2-3 周, paradigm 不破死局.

## A2: Gecode (C++ modular CP)

- **Version state**: 6.2.0 (2019-04 最后正式 release), 7 年 1 月无新版. develop 分支有 commit 但 release cadence 死.
- **Paradigm**: 传统 propagator + 搜索树, 无 lazy clause generation. CP-SAT = propagation + CDCL + lazy clauses + cut planes hybrid.
- **vs CP-SAT**: MZ24 0 medal, 工业级落后 CP-SAT 一代.
- **Python binding**: gecode-python 2012 最后更新, 现代 3.13 不可用.
- **Verdict NO-GO**: 代际落后, Python 接入 1-2 周自写 cffi.

## A3: MiniZinc + Chuffed (LCG backend)

- **Version state**: Chuffed GitHub 2026-03 commits 全 dependabot bump, 已 light maintenance mode 数年.
- **Paradigm**: Lazy Clause Generation — FD propagator 把 propagation 翻译成 SAT clauses, SAT solver 做 conflict learning + CDCL backjump.
- **vs CP-SAT**: 本质同 paradigm (Stuckey 系直接影响 OR-Tools 设计). **不存在 Chuffed 能 break 但 CP-SAT 不能的 case**.
- **MZ24 排名**: Chuffed-fd 459.69 第 4-5 / OR-Tools-fd 471. mid-tier, 都被 choco/gecode 在 fixed search 拉开. LCG 不再 SOTA.
- **Verdict NO-GO**: 同 paradigm family, 重写 MZN 模型 2-3 周, paradigm 不破死局.

## A4: Z3 SMT solver (theory combination)

- **Version state**: Z3 4.16.0 release 2026-02-19, 12.3k stars. cvc5/Yices2 平分 SMT-COMP 各 division.
- **Paradigm**: SMT = lazy theory combination + DPLL(T) backbone. 整数/数组/bv 各 theory 独立 propagator. **2D placement 需要 no-overlap 强 propagator, CP-SAT 原生, SMT 必须手写 linear constraint 退化为 disjunctive encoding** (paper 实测 "far from CPOptimizer").
- **Lex objective**: Z3 Optimize 支持 lex/Pareto/weighted, 但 OMT 是 SMT 较弱方向, OptiMathSAT 主导 OMT.
- **MZN Challenge 2018-25**: CP-SAT 8 连金.
- **Verdict NO-GO**: dense combinatorial 比 CP-SAT 慢, encoding gap, 没 known paper 在 70×70 + 266 obj scale 上 Z3 解 placement+routing certified exact.

## A5: Picat (B-Prolog hybrid)

- **Version state**: Picat v3.9#7 release 2026-02-26, XCSP'25 main CSP 第一 / MiniZinc'25 free search 第二.
- **Paradigm**: modeling layer (cp/sat/mip/smt 统一接口) + tabling DP. SAT 模块走 log-encoding 编 CNF → 外部 SAT solver.
- **vs CP-SAT**: 不是 paradigm 对立, 是 frontend 不同; 底层 SAT 还是 CDCL.
- **Application 域**: ASP/PDDL planning, 图合成, AoC. **没有 ≥50×50 grid 2D facility layout 公开 case**.
- **Verdict NO-GO**: tabling 对 DP-friendly 问题强 (planning/path), 我们 dense placement + global ghost rect + power coverage 没 subproblem 重用结构. Python 接入只能 subprocess.

## A6: clingo / Answer Set Programming

- **Version state**: clingo v5.8.0 release 2024-04-03, Potassco 主力. ASP solver 自 2024-04 至今 2 年无新版.
- **Paradigm**: declarative rule-based + grounding-then-solving. ground 阶段把 first-order rule 实例化为 propositional, clasp (CDCL) 求解.
- **vs CP-SAT**: ASP 强在 reachability/recursion/默认否定; CP-SAT 强在 numeric+arithmetic+大规模 propagation.
- **Project fit 致命问题 — grounding 爆炸**: 266 facility × 70×70 pose × 多 commodity arc → propositional rule 数量级 **1e7-1e8**, ground 阶段就 OOM/慢. LNPS paper 自报 "systematic ASP search 不 scale to large instances".
- **Verdict NO-GO**: grounding 爆炸早于 CP-SAT propagation buffer 撞墙. 重写 2-3 周必撞 OOM.

## A7: SCIP solver (academic MIP + CP module)

- **Version state**: SCIP 10.0.0 release 2025-11-24, 10.0.2 = 2026-04-02 最新. (sub-agent 误报 2025-12, 实际 2025-11).
- **Paradigm**: CIP = branch-cut-and-price + LP relaxation + constraint handlers (CP propagation 装在 handler 里).
- **vs CP-SAT**: SCIP 强在 MINLP/非线性/column generation; CP-SAT 强在 dense 0-1 combinatorial + 对称破缺 + 复杂逻辑约束 (跟我们 70×70 placement 类同).
- **Benchmark vs Gurobi/CPLEX**: SCIP 慢一档 (小问题最慢). 4-10% 改进 sub-agent 报但 release notes / scipopt.org 都没找到数字, 数字 unverified.
- **Verdict NO-GO**: CP-SAT 强项区 (binary placement) 上 SCIP 反而退步, paradigm shift 重写 2-3 周, 不在我们瓶颈维度 break.

## A8: Lazy Clause Generation (LCG paradigm)

- **State**: 当前 SOTA LCG implementation = Chuffed (Stuckey) 跟 OR-Tools CP-SAT 同代技术. 2025 新方向是 Dekker CP 2025 "modular SAT for LCG".
- **vs 我们 stack**: CP-SAT 自身就是 LCG portfolio (cpsat-primer 自述 "centered around Lazy Clause Generation based CP Solver" + 加 LP relaxation + cutting plane + 8 worker portfolio).
- **Verdict NO-GO**: 已在最强 LCG implementation, 换 Chuffed 期望 1-3x 不是数量级, 工作量 2-4 周.

## 共同 verdict 总结 (Group A 8 个)

每个 paradigm 都跟 CP-SAT 同 family 或代际落后. 项目 24 lever 死法是 cut 表达力被 master form 锁死 + master form scale 限制, **换 production solver 不解决 paradigm-level 死锁**.

重写成本: 2-4 周 / paradigm. 加 24 lever 调试. ROI 全部为负.
