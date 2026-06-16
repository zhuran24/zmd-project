# Candidate: Lever 25 — Implicit Hitting Set (IHS) paradigm

## 当前项目状况

24 lever 全 verdict 死 (详 `02_LEVER_HISTORY_24_DEAD.md`). 6 paradigm 不同 sub-problem framework 撞同墙 (cut form 表达力被 pose-bool master 限制). 32 个 paradigm 调研里这是 alive 候选之一.

## 为什么列为候选

paper: **"Efficient and Reliable Hitting-Set Computations for the Implicit Hitting Set Approach"** (arxiv 2508.07015), AAAI 2026 accepted.

paradigm 描述 (paper abstract 原文核对):
> "IHS iterates between a decision oracle used for extracting sources of inconsistency and an optimizer for computing so-called hitting sets (HSs) over the accumulated sources of inconsistency."

跟当前项目 LBBD framework 区别:

| 维度 | 当前 LBBD | IHS paradigm |
|---|---|---|
| master 形式 | pose-bool MIP, 每 iter 累积 cut 加入 master | 维护 inconsistency core set + 独立 hitting set ILP |
| cut 维度 | master pose-bool 维度 (instance-pose conjunction) | hitting set 维度 (跨 core 的 minimum cover) |
| sub-problem | binding / routing 反馈 nogood | oracle 抽 core |
| 累积方式 | cut 加入 master constraint | core 加入 dataset, master 不变 |

**理论上的潜在区别**: IHS 不在 master 加 cut, 而是在外层 hitting set 计算. 项目 24 lever 死法都是 "master cut 累积 + 切空间 < 1%". IHS 不在这个 dimension.

**理论上的潜在限制**: oracle 抽出来的 core 仍是 pose-bool conjunction (跟 LBBD nogood 同维度). hitting set 算的是覆盖这些 conjunction 的 minimum subset. 如果 oracle 的 core 表达力同被 pose-bool 限制, 死法跟 LBBD 可能仍同质.

## 实施 plan (未实施)

未 Phase 0 cheap gate. 估计:

| Phase | 工作 | 估时 (Claude pace) |
|---|---|---|
| Phase 0 cheap gate | 写 minimum IHS demo on 单 anchor (22,28) 27×15, 用 CP-SAT 当 oracle, 用 pulp/HiGHS 当 hitting set ILP | 2-3 day Claude + ~10-30 min wall |
| Phase 1 production | 接 binding/routing 当 oracle, IHS loop 跟 outer search 整合 | 1-2 周 Claude |
| Phase 2 multi-anchor | 8 anchor × max_iter=5 campaign | ~2h wall |

## Phase 0 cheap gate GO/NO-GO 信号 (设计中)

**GO 条件**:
- ≥1 non-corner anchor 在 600s 内 CERTIFIED feasibility / infeasibility
- hitting set ILP 单 iter ≤ 5s
- core size 不全退化 size = 1 (不重复 LBBD 同质 fail)

**NO-GO 条件**:
- 全 anchor UNPROVEN at max_iter cap (同 Path 12-14 同质死法)
- hitting set ILP scale 爆 (cores accumulate 后 ILP > 1 min)
- oracle 抽 core 全 size = 1 (paradigm 退化等价 LBBD)

## 数学结构 (paper sect 2 描述, paper abstract 推断)

```
P: set of all possible assignments  (master pose-bool space)
C: incrementally-built collection of inconsistency cores
  each c ∈ C: subset s.t. assignment 同时满足 c 中所有元素 → INFEASIBLE

H: minimum hitting set over C
  H ⊆ "all literals in cores"  s.t.  ∀ c ∈ C, H ∩ c ≠ ∅
  ILP: minimize |H| (or weighted)
        s.t. for each c ∈ C: sum_{x ∈ c} hit_x ≥ 1

Loop:
  H = solve_hitting_set(C)
  if oracle(P \ H) returns OPTIMAL: return solution
  else: c_new = oracle returned core; C.add(c_new)
```

## 包内 paper 信息

paper abstract + AAAI 2026 acceptance verified. 详 `paper.md`.

## 实施前需澄清的不确定

1. paper 描述的 IHS 是否适用 maximization problem (我们 max_lex), 还是仅适用 minimization?
2. oracle 必须给 sufficient core (不只 necessary). 我们 LBBD 的 sub-problem 给的是 sufficient 还是 necessary?
3. hitting set ILP scale 在我们 problem 多大 (core accumulate 后)?
4. paradigm 是 LBBD 的 dual / 还是 paradigm-orthogonal 增强?

paper 全文阅读 verify 后才能 cheap gate.
