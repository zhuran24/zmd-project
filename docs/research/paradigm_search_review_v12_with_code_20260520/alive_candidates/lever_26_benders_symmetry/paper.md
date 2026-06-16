# Paper: arxiv 2511.22251

## 真实性校验 (2026-05-20)

- arxiv ID 存在 ✅
- 作者: Christopher Hojny, Cédric Roy ✅
- 日期: Submitted 2025-11-27, revised 2025-12-17 ✅
- 应用 domain in paper: bin packing + scheduling (verified in abstract) ✅

## 完整 title

"A Framework for Handling and Exploiting Symmetry in Benders' Decomposition"

## Abstract (paper 原文摘要核心 — fetched 2026-05-20)

> "We address symmetry handling in Benders' decomposition (BD), a technique previously underutilized in this context. We introduce a tailored family of graphs that capture the symmetry information of both the Benders master problem and the Benders oracles. Once symmetries are identified through established methods, classical approaches can accelerate BD. We develop techniques for separating and aggregating symmetric cuts via specialized routines and extended formulations, reducing oracle executions. Numerical experiments demonstrate the effectiveness of symmetry handling and cut aggregation specifically on bin packing and scheduling problems."

## paradigm 关键性质

1. **跨层 graph-based symmetry detection**: 不是只看 master 或 sub-problem, 而是构造一族图捕捉 master + oracle 联合 symmetry. 用 established symmetry detection (nauty/bliss/Saucy) 跑 graph automorphism.

2. **两种 exploitation 技术**:
   - **Separating symmetric cuts**: 同 symmetry orbit 内的 cut 不重复加, 单 cut 等价多个 cut
   - **Aggregating extended formulations**: 把 symmetric cuts 合成 stronger aggregate cut + extended variables

3. **paper 自报 reducing oracle executions**: 实测 bin packing + scheduling 上 oracle 调用次数减少.

## 我们项目 fit 度评估

- 概念层面 fit: 项目 270K pose vars 内 facility-type-internal symmetry 没真利用. paper paradigm 是 master+sub-problem 跨层 — 项目 LBBD 也是 master+sub-problem
- scale 层面 fit 未验: paper 测 bin packing scale 未跟我们 70×70 + 266 facility 对比
- paradigm 实质区别: paper 是 **paradigm-orthogonal 增强**, 不直接换 master form, 也不改 cut form structure, 只是减少 redundant cut + 加速 oracle

## 项目 24 lever 死法是否在此 paradigm 上同质重复?

**部分**.

- 同 paradigm 部分: paper 在 Benders framework 内, 不改 master/cut structure. 项目 24 lever 死在 master form / cut 表达力. 如果 root cause 是表达力不是 redundancy, symmetry framework 帮不了
- 不同 paradigm 部分: 项目之前没在 master+sub-problem 联合 symmetry 上下功夫. paper 是 paradigm-orthogonal 增强, 跟 lever framework 不冲突 — 加在任何 LBBD lever 上都可能有 multiplicative 加速

## 包内估算 vs 实施前需澄清的不确定

1. paper graph 构造在我们 mass-scale (270K pose) 上 nauty/bliss 跑时间未知 — 是否 > 1 min?
2. paper 测的 bin packing instance scale (item 数) 跟我们 facility 数 (266) 同量级 vs 不同量级?
3. extended formulations 加多少 vars / cstr? 我们 master cstr 280K 基线, paper 加 30% 还是 100%+?
4. **paradigm 加速的 multiplicative factor** 在 paper 实测 bin packing 是多少 (e.g. 2x / 10x / 100x)? abstract 没给具体数字

paper 全文阅读后才能 cheap gate.

## 链接

- arxiv abstract: https://arxiv.org/abs/2511.22251
- PDF: https://arxiv.org/pdf/2511.22251
