# Papers: Column Generation 系列

## 系列里相关 paper (verified 2026-05-20)

### Paper 1: arxiv 2603.07821 — Micro-Transit Zoning Column Generation

- arxiv ID 存在 ✅
- 作者: Hins Hu, Rishav Sen, Jose Paolo Talusan, Abhishek Dubey, Aron Laszka, Samitha Samaranayake ✅
- 日期: 2026-03-08 ✅

**Title**: "Column Generation for the Micro-Transit Zoning Problem"

**Abstract 关键 (fetched)**:
> "The authors address planning geo-fenced zones for micro-transit services. They 'generalize the Micro-Transit Zoning Problem (MZP) to allow a global budget rather than imposing a size limit for candidate zones' and 'design a Column Generation (CG) framework to solve the problem and several pricing heuristics to accelerate computation.'"

**paradigm 关键 (推断, abstract 未明示)**:
- column = whole-zone (cell 集合)
- pricing sub-problem = IQP / ILP
- pricing heuristics 加速

**项目 fit caveat**: paper 自己**没明示 "column = whole-zone" 用法**, sub-agent 是推断. abstract 未给具体 column 粒度.

### Paper 2: arxiv 2509.01218 — 2D Multi-Criteria Bin-Packing CG

- arxiv ID 存在 ✅
- 日期: 2025-09-01 ✅

**Title**: "Column-generation for a two-dimensional multi-criteria bin-packing problem"

**paradigm 关键**: Ryan-Foster branching + pricing 产 bin-layout. column = whole-bin pattern. 应用 PCB 制造.

**项目 fit caveat**: 同样 column = whole-bin (pattern). 我们 problem 是 single-bin (70×70) + 266 异质 facility, 不是 multi-bin homogeneous item.

### Paper 3: arxiv 2604.04740 — Generalized Multiple Strip Packing

- arxiv ID 存在 ✅
- 日期: 2026-04-06 ✅

**Title**: "Exact Methods for the Generalized Multiple Strip Packing Problem with Heterogeneous Costs"

**paradigm 关键**: BendM (Benders' Method for Multiple strips), normal-position formulation.

**项目 fit caveat**: 是 strip packing 不是 grid layout, 但 BendM Benders 方法学跟我们 LBBD 同 family.

## production tooling state (2026-05-20)

| Tool | Version | Python binding | Maturity |
|---|---|---|---|
| **GCG** (RWTH Aachen, Lübbecke + ZIB) | 3.5.0 | PyGCGOpt v0.1.3 (早期版本) | academic, 长期 maintain |
| **BaPCod** (INRIA Bordeaux) | 0.84 (2025-11) | None (C++ only) | academic prototype |
| **Coluna.jl** | latest | Julia/JuMP-native | 教程级 (1D cutting stock) |

## column 粒度问题 — 2026 paper 调研

**关键调研结论 (2026-01 ~ 2026-05 窗口)**: 0 paper 显式讨论 "column 粒度怎么定". 现存惯例都是 domain-conventional:
- zone-as-column (transit)
- bin-as-column (packing)
- route-as-column (VRP / VRPTW)

没有 principled method 帮我们选 column 粒度.

## 项目 fit 度评估

对项目应用的 5 个限制 (调研确认):

1. **column = "完整 valid 摆放" 退化为整个 problem solution** (pricing = 原 problem)
2. **column = "single facility pose" 退化回 pose-bool** (跟 24 lever 同 dim)
3. **column = "facility-type-cluster 局部布局"** — middle ground 但 paradigm 未有 paper method 选粒度
4. **lex objective** max_lex(area, min_side) — CG 天然单目标 LP, lex 要分层 + epsilon 约束转换
5. **forced-unique-instance**: 266 mandatory + each unique. CG 经典 pattern 反复用 (set-partitioning), 我们 set-packing 退化

## 链接

- Paper 1 arxiv abstract: https://arxiv.org/abs/2603.07821
- Paper 2 arxiv abstract: https://arxiv.org/abs/2509.01218
- Paper 3 arxiv abstract: https://arxiv.org/abs/2604.04740
- GCG: https://gcg.or.rwth-aachen.de/
- BaPCod: https://bapcod.math.u-bordeaux.fr/
- PyGCGOpt: https://github.com/scipopt/PyGCGOpt
