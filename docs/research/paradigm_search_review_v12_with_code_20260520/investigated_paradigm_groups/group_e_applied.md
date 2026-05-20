# Group E — Applied / Domain-Specific (2 paradigm, 全 NO-GO)

调研覆盖 factory-building 游戏 layout planners + quantum-inspired classical (非 production CS-style) paradigm. 校验后 verdict.

## E1: Factory-Building Game Layout Planners

- **学术 paper (St Andrews 2023)**: arxiv 2310.01505 "Towards Automatic Design of Factorio Blueprints" (Patterson/Espasa/Chang/Hoffmann). 用 Essence Prime + Savile Row → CP backend, Benders 分解 placement + routing.
  - **校验后**: paper paradigm + 作者 + Essence Prime/Savile Row 都 confirmed. **但 sub-agent 报的 "8×8 intractable" 数字在 PDF 前 3 页没找到** — 实际可能跟 arxiv 2102.04871 Reid 那篇 "12×12 conveyor belt" 数字混淆. 数字 unverified.
- **学术 paper (Reid 2021)**: arxiv 2102.04871 "The Factory Must Grow: Automation in Factorio" (Reid + 4 共作者). SA / GP / ERL meta-heuristic. **3×3 / 6×6 / 12×12 instance** (校验后 abstract 没确认数字, 需 PDF). 只解 placement, 不解 belt routing.
- **社区工具 (Satisfactory / Factorio)**:
  - Zistack/Satisfactory-Optimizer: scipy.linprog 解 recipe rate, 完全不做 2D 摆放
  - ficsit-companion / SatisFactory-Planner / ReikaKalseki / factoriolab / helmod: node-based recipe planner + 手摆 GUI
  - elswindle/factorio_annealer: SA 启发式, 不解 belt routing (LTN mod 预定义)
- **Fit 致命问题**:
  - 量级匹配 0 个: 学术 CP 极限 ≤ 30 grid cells, 我们 70×70 + 266 mandatory + multi-commodity routing 是 SOTA 之外
  - 唯一同 paradigm (CP + Benders + placement+routing) 论文已撞墙在 small scale
  - max_lex(area, min_side) 目标无现成 reference
- **Verdict NO-GO**: recipe planner 在 IP v2 已有 (BP-2026-05-13 blueprint 已验证), grid placement 没有任何 prior art 比项目当前 stack 更进. 学术 paper 给的 paradigm (CP + Benders 拆 placement-routing) 项目已穷尽.

## E2: Quantum-Inspired Classical (QAOA simulator / Ising annealing)

- **Fujitsu Digital Annealer**:
  - sub-agent 引 arxiv 2311.05196 报 "QPLIB 90%+ best-known" — **校验后实质错误**, paper 是台湾 Kao/Liao/Hsu 作者非 Fujitsu, abstract 没提 QPLIB. **sub-agent 错估 paper 内容**
- **D-Wave Leap Hybrid**:
  - 校验后 confirmed: 官方文档原话 "The Stride solver returns a nondeterministic number of solutions. Any feasible states returned are ordered by objective (from low to high)". 无 performance bound.
- **Ising machine benchmark** (arxiv 2507.22117):
  - 校验后 confirmed: 53K vars Max-Cut benchmark 存在. **但 sub-agent 报 "Fujitsu DA 跑赢 D-Wave + QIS3" 不准** — paper 原话 "competitive results" 不是 "beat".
- **QAOA simulators** (supply chain facility location 2024):
  - polynomial runtime 但 "sub-optimal", noiseless 条件下 < 30 var 已被 exact solver 吊打
- **Fit 致命问题 — paradigm 性质级**:
  - QUBO/Ising 范式天生**没 dual bound / branching tree, 不产 proof**. D-Wave SDK + Fujitsu DA SDK 都不导出 LP bound
  - 全 family heuristic by design
  - 违 PROJECT_LOCK "certified_exact / exploratory strictly separate"
- **Verdict NO-GO**: 跟 24 lever 同性质 (heuristic), 但比现 pose-bool master + CP-SAT 退化 — 失去 dual bound 失去 INFEASIBLE 证明能力. 仅可作 exploratory hint 来源, 不可作 certified path.
