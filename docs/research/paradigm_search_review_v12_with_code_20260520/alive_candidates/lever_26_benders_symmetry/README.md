# Candidate: Lever 26 — Benders Symmetry Framework

## 当前项目状况

24 lever 全 verdict 死. paradigm 调研发现 2025-11 paper 提供跨 LBBD master+sub-problem 的 symmetry detection framework, 跟项目现有 master-internal symmetry breaking 不同 paradigm.

## 为什么列为候选

paper: **"A Framework for Handling and Exploiting Symmetry in Benders' Decomposition"** (arxiv 2511.22251, 2025-11-27 submitted, revised 2025-12-17). Authors: Christopher Hojny and Cédric Roy.

paradigm 描述 (paper abstract 原文 fetched 2026-05-20):
> "We address symmetry handling in Benders' decomposition (BD), a technique previously underutilized in this context."
> "tailored family of graphs that capture the symmetry information of both the Benders master problem and the Benders oracles."
> "develop techniques for separating and aggregating symmetric cuts via specialized routines and extended formulations, reducing oracle executions."

paper 实测 domain: **bin packing + scheduling** (跟我们 problem 同类组合优化).

跟当前项目 symmetry breaking 区别:

| 维度 | 当前 | Benders symmetry framework |
|---|---|---|
| symmetry detection scope | master-internal (pose-bool 内 orientation symmetry, lex breaking) | **master + sub-problem 跨层 graph-based detection** |
| symmetry exploitation | 加 lex constraint 在 master | aggregating symmetric cuts + reducing oracle executions |
| 适用 framework | 任何 paradigm | 专 Benders 优化 |

## 理论上潜在收益

我们 270K pose vars 里, facility-type-internal symmetry (e.g. 16 个同型号 power pole 互换) 没真利用. paper 实测 bin packing + scheduling 上 "reducing oracle executions". 项目 24 lever 死法之一是 multi-anchor 8 anchor × 10 iter = 0/8 CERTIFIED — 每 iter cut 累积但切空间 ≪ 1%. 如果 symmetric cut aggregation 能让每 cut 切空间放大 N 倍 (N = symmetry group order), paradigm 可能跟 24 lever 不同质.

## 理论上潜在限制

- paper 自己测的 bin packing 跟我们 70×70 placement 同类但具体 scale 未对比
- symmetry framework 是 paradigm-orthogonal **增强**, 不直接 break 现有 dead end. 如果 cut form 表达力 fundamental 限制, symmetry 加速也只是 1-5x, 不解决 0% CERTIFIED rate
- graph-based symmetry detection (nauty / bliss / Saucy) 在 270K pose × ~3000 binding-side var 上是否可行未验

## 实施 plan (未实施)

| Phase | 工作 | 估时 (Claude pace) |
|---|---|---|
| Phase 0 cheap gate | 写 minimum demo: 用 nauty/bliss 跑现有 master.model graph → detect symmetry group order + 验 ≥1 anchor 上 aggregating cut 是否减少 iter | 1-2 day Claude + ~30 min wall |
| Phase 1 production | 接 binding sub-problem symmetry, cross-layer aggregating | 1 周 Claude |
| Phase 2 multi-anchor | 8 anchor × max_iter=5 跟 baseline 比 | ~2h wall |

## Phase 0 cheap gate GO/NO-GO 信号

**GO 条件**:
- master.model 实测有 ≥10 个 facility-type-internal symmetry group, total order ≥100
- aggregating cut 在单 iter 上替代等价 N 个 instance-pose cut, N ≥ 5
- multi-anchor (即使简化版) 8 anchor 累积 cut 数减少 30%+

**NO-GO 条件**:
- 270K pose 互不对称 (symmetry order = 1)
- 即使 aggregate, 单 cut 切空间放大 < 2x (paradigm 同 24 lever 同质死)
- nauty/bliss 在 270K node graph 上跑 > 1 min (computational expense 高)

## 包内 paper 信息

详 `paper.md`.

## 项目内已有 infrastructure 复用

- `PoseBoolExactMasterDelegate` 已有部分 symmetry breaking (lex constraints + ghost mirror)
- benders_loop.py 现成 cut accumulation 逻辑可挂 aggregating cut hook
- group-theoretic library 没装但易加: `pip install pynauty` 或 `bliss-graph-symmetry`
