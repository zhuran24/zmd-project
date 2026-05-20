# Candidate C — Column Generation / Branch-and-Price

## 当前项目状况

24 lever 全 verdict 死. paradigm 调研里 Column generation 是**真换 master form 思路**: master 不见 pose-bool 个体, 只见 pattern (黑盒 column). 跟项目 24 lever 在 pose-bool framework 内不同 dimension.

但**前提不满足** — 我们 problem 是 forced-unique-instance, 每 mandatory facility instance 必须摆且仅 1 次, column 退化.

## 为什么列为候选

paper:
- **"Column Generation for the Micro-Transit Zoning Problem"** (arxiv 2603.07821, 2026-03-08), 主要 paradigm refrigerator: master = set-covering of patterns, pricing = IQP/ILP
- **"Column-generation for a two-dimensional multi-criteria bin-packing problem"** (arxiv 2509.01218, 2025-09-01), Ryan-Foster branching + pricing 产 bin-layout
- production tooling: GCG 3.5.0 + PyGCGOpt (RWTH Aachen), BaPCod 0.84 (INRIA Bordeaux C++)

paradigm 描述:

| 维度 | 当前 LBBD master | Column Generation master |
|---|---|---|
| master variable | pose-bool: x_{i, p} per (instance, pose) | column: λ_l per (valid pattern) |
| master size | 270K vars (instance × pose enumeration) | column 数 (生成式, 可少可多) |
| sub-problem 角色 | binding/routing feasibility cut | pricing: 找 negative reduced cost column |
| master 表达力 | 跟 cut 锁死同 dim | master 不见 pose, cut 表达力可能不同 dim |

## 理论上潜在收益

24 lever 死法是 cut 表达力被 pose-bool 维度锁死. Column generation 让 master 不见 pose-bool 个体, 只见 pattern. 跟之前 24 lever **不同 dimension**. 这是 production tooling 范畴内**真未试** paradigm shift.

## 理论上潜在限制 (关键)

**前提失败风险**: 我们 problem 是 **forced-unique-instance + heterogeneous facility** structure:

- 266 mandatory instance 必须 1-1 摆放 (forced unique)
- 16+ 种 facility type 不同形状不同 port (heterogeneous)
- column = "valid pattern" 在标准 CG 是 "某 bin / zone / vehicle 的 valid 内部布局 by item subset"

我们问题 column 粒度的两种退化:
- (a) **column = whole-base layout (所有 266 facility 一摆)**: 1 column = 整个 problem solution. master 变成 enumeration, pricing sub-problem 跟原 problem 等同. paradigm 退化无意义
- (b) **column = single facility pose**: column 跟 pose-bool x_{i,p} 1-1 对应. paradigm 退化等价当前

中间粒度 (e.g. column = facility-type-cluster 的某 valid 局部布局) 可能不退化, 但**没paper 给 principled 选择方法**.

## 实施 plan (未实施, 远期备选)

| Phase | 工作 | 估时 (Claude pace) |
|---|---|---|
| Phase 0 cheap gate | 用 PyGCGOpt 写 minimum demo: 5 instance + 单 anchor + 无 routing, 验 GCG 能否给出 LP bound + integer feasible solution. column 粒度先定 "per-facility-type-cluster" 试 | 1-2 周 Claude (paradigm shift cost) |
| Phase 1 production | column 粒度真定 + pricing sub-problem 真接现有 routing/binding sub-problem | **3-6 月** Claude (跟做新 paradigm 同量级) |
| Phase 2 multi-anchor | 8 anchor 实测 | 1-2 周 |

## Phase 0 cheap gate GO/NO-GO 信号

**GO 条件 (高度依赖 column 粒度选择)**:
- 5 instance 单 anchor cheap gate 在 5 min 内 master LP bound 收敛
- pricing sub-problem 解 < 10s (跟当前 binding sub-problem 同档)
- column 粒度退化少于一半 (即不退化到 single pose 也不退化到 whole problem)

**NO-GO 条件**:
- column 粒度退化无法 principled 选 (paper 0 篇 paradigm 给 method)
- pricing sub-problem 跟 binding+routing sub-problem 同复杂度 (paradigm shift 无收益)
- LP relaxation 给的 bound 不收敛 (lex objective 在 CG 是 known 难点)

## 项目 24 lever 死法是否在此 paradigm 上同质重复?

**理论上不同 dimension**. paradigm 真换 master form. 但前提满足才有意义.

paper hunt:
- "column 粒度怎么定" — 2026-01 ~ 2026-05 调研窗口 0 paper 显式讨论
- micro-transit / bin packing / VRP 等域都是 domain-conventional (zone-as-column / bin-as-column / route-as-column), 没有 principled comparison

## 实施前需澄清的不确定

1. column 粒度怎么定 (paper 0 篇 method, paradigm 选错就退化)
2. lex objective max_lex(area, min_side) 在 CG 怎么表达 (CG 天然单目标 LP)
3. PyGCGOpt vs BaPCod 哪个真能集成 (PyGCGOpt 还是 0.1.x early, BaPCod 是 C++ no Python)
4. pricing sub-problem 是 IQP / ILP 还是 CP — 我们 routing 用 CP-SAT, pricing 用啥 solver?

## 包内 paper 信息

详 `paper.md`.

## 远期备选标记

当前 priority 排序里这个候选**最低**. 主要因实施成本估 3-6 月 + column 粒度未解决 + paper 0 篇 method. 优先于 lever 25 / 26 / candidate A 全死后再考虑.
