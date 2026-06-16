# L01-L10 — Coordinate Master Era (10 lever 合并)

## 当时项目情况

2025-12 ~ 2026-04 早期阶段. master form 用 **coordinate-based**: 每 slot 有 (x, y, mode) 3 个 IntVar + AddNoOverlap2D. 在 27×15 ghost rectangle 等 anchor 上 master.solve 30 min UNKNOWN.

## 为什么走这条路

CP-SAT 标准 placement 表达就是 coordinate-based. AddNoOverlap2D 是 OR-Tools 内置 propagator. 项目初始 paradigm 选择直接 follow CP 经典做法.

## 试过的 10 个 lever 类目

- L1 RAM 优化 (jemalloc / P-core taskset / THP / spike 各种)
- L2 换 solver (HiGHS / SCIP MIP family)
- L3 OR-Tools 参数 tuning
- L4 power placement 拆 subproblem (PROJECT_LOCK 禁)
- L5 等 OR-Tools 9.16
- L6 AI sidecar (long-term, 不在此 era 实施)
- L7 community blueprint hint (D step 2, 798 AddHint 零损耗但仍 UNKNOWN)
- L8 search profile 切换 (guided / ghost-first / ghost-after-counts)
- L9 objective relaxation
- L10 加 time + worker

## 实验结果

10 个 lever 全 verdict 死. 单独看每个 lever 都有局部 improvement (e.g. workers=1 vs 8 让 master peak RAM 30 → 12 GB), 但 master.solve 仍 30 min UNKNOWN. **没有任何 lever 单独 break wall**.

## 经验跟教训 (含瓶颈理解更新)

- 早期认知错误 1: **以为 RAM 是瓶颈**. workers 减小 → RAM 减但 wall 仍 UNKNOWN.
- 早期认知错误 2: **以为 wall 是 NP-hard 本质难度**. 后来 B1 paradigm 换 master form 后 53s OPTIMAL.
- 早期认知错误 3: **以为 hint 注入能救**. D step 2 798 hint 零损耗注入仍 UNKNOWN — hint 不是 cut.
- **真瓶颈在 coordinate-based master form 本身, 不在工程优化层**. 这是 B1 paradigm 切换的 evidence base.

## code/

无独立 trial script (大部分在 production src/ 内已 commit). 详 `shared_infra/src/models/exact_coordinate_master.py` (coordinate master 实施) + `shared_infra/docs/lever_verdicts.md` 表 L1-L10 完整明细.
