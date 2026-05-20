# Paper: arxiv 2508.07015 (AAAI 2026 accepted)

## 真实性校验 (2026-05-20)

- arxiv ID 存在 ✅
- 作者 verified: Hannes Ihalainen, Dieter Vandesande, André Schidler, Jeremias Berg, Bart Bogaerts, Matti Järvisalo ✅
- 日期: Submitted 2025-08-09, revised 2025-11-17 ✅
- AAAI 2026 accepted (paper submission history 显式标 "Accepted for publication in the proceedings of AAAI 2026") ✅

## 完整 title

"Efficient and Reliable Hitting-Set Computations for the Implicit Hitting Set Approach"

## Abstract (paper 原文摘要核心 — fetched 2026-05-20)

> "IHS iterates between a decision oracle used for extracting sources of inconsistency and an optimizer for computing so-called hitting sets (HSs) over the accumulated sources of inconsistency."

> "The researchers evaluate alternative algorithmic techniques for hitting set optimization using pseudo-Boolean reasoning and stochastic local search, highlighting trade-offs between efficiency and reliability in correctness guarantees."

## paradigm 关键性质

1. **iterative oracle + optimizer 架构**: 一个 oracle 用来抽 inconsistency cores (sufficient subsets s.t. accumulated 后 INFEASIBLE), 一个 optimizer (e.g. ILP, pseudo-Boolean, stochastic LS) 算 minimum hitting set.

2. **hitting set 维度 ≠ master 维度**: 跟 LBBD master 不同. master cut 加 sum(x_{i,p}) <= |core|-1; IHS 在 dataset C 里加 core, hitting set 算 hit literal 子集.

3. **应用 traditional 域**: MaxSAT (paper 自报方向), 实际也用于 SAT-based optimization, planning, decision diagrams.

4. **paper 自己关注的 trade-off**: PB reasoning (sound) vs stochastic LS (faster but probabilistic). paper 评估 reliability vs efficiency.

## 我们项目 fit 度评估 (项目自己的, 不主观推荐)

paper 自己**没在 70×70 + 266 facility + routing 上测**. 应用领域是 MaxSAT family.

- 概念层面 fit: 我们 LBBD framework 跟 IHS 都是"oracle + optimizer", 数学结构相似
- scale 层面 fit 未验: paper 不在我们 scale 上 benchmark
- paradigm 实质区别: IHS 不加 cut 进 master, master form 自身不需重写. 跟 24 lever 在 master 加 cut 死法不同 dimension

## 项目 24 lever 死法是否在 IHS 上同质重复?

未知. 待 GPT 评估:
- oracle 抽 core 必须 sufficient. 项目 LBBD 的 binding/routing sub-problem 给的多是 sufficient (binding INFEASIBLE → master pose 不可)
- 但 oracle 抽的 core 维度仍是 pose-bool conjunction. hitting set 算 minimum cover 后仍是切 pose-id-dim. 跟 LBBD nogood 同 dim
- 跟 LBBD 区别可能仅是 "累积 core / lazy 加 cut" vs "累积 cut into master" 工程层. 数学层是否真不同 dim 不清楚

## 项目内已有 infrastructure 复用

- LBBD sub-problem framework 现成 (binding / routing / flow 子求解器 + extract conflict)
- pose-bool master 现成 (`PoseBoolExactMasterDelegate`)
- Phase 0 cheap gate workflow 现成 (paths/ 已有 7 个 paradigm 的 Phase 0)

## 链接

- arxiv abstract: https://arxiv.org/abs/2508.07015
- PDF: https://arxiv.org/pdf/2508.07015
- AAAI 2026 program (待 2026-02 ~ 03 公开正式 program)
