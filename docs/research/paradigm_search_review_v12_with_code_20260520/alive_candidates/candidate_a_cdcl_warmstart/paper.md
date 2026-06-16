# Paper: arxiv 2512.18034

## 真实性校验 (2026-05-20)

- arxiv ID 存在 ✅
- 作者 verified: Joshua Gibson, Kapil Dhakal ✅
- 日期: Submitted 2025-12-19, v3 2026-05-07 ✅
- problem domain: discrete facility layout (verified in abstract) ✅

## 完整 title

"Accelerating Discrete Facility Layout Optimization: A Hybrid CDCL and CP-SAT Architecture"

## Abstract (paper 原文摘要核心 — fetched 2026-05-20)

> "The paper addresses discrete facility layout design—placing physical entities to minimize costs while respecting constraints. It compares CDCL, CP-SAT, and MILP approaches across varying problem sizes. Key findings show CDCL excels at feasibility detection but struggles with optimization."

> "Leveraging this finding, we developed a novel 'Warm-Start' hybrid architecture that utilizes CDCL to rapidly generate valid feasibility hints, which are then injected into a CP-SAT optimizer."

> The research confirms this layered approach "successfully accelerates exact optimization" by bridging "rapid satisfiability and proven optimality."

## paradigm 关键性质

1. **两层架构**: outer CDCL (SAT solver, 跑 feasibility detection) + inner CP-SAT optimizer (基于 hint 跑 optimization)
2. **CDCL feasibility 比 CP-SAT 快 orders-of-magnitude** (paper 主张, 在 highly-constrained 场景下)
3. **paradigm 跟 hint injection 同类**: hint 不当 cut / 不破坏 exactness, 只引导 search

## 我们项目 fit 度评估

- 概念 fit: 当前 D step 2 community blueprint hint 是同 dim 路径 (hint injection 不改 master form). paradigm 实测 paper 是 discrete facility layout
- scale fit: paper 跑的是 QAP-style scale, 我们 70×70 + 266 facility + routing 不同结构
- paradigm 实质区别: paper 用 SAT-derived hint 替代 human-curated hint. 在 hint quality / scale-able 维度可能更好

## 项目 24 lever 死法是否在此 paradigm 上同质重复?

**可能同质**.

- D step 2 (community blueprint hint) 已实测: 798 AddHint 零损耗 + master 3600s + workers 8 仍 UNKNOWN
- Candidate A 跟 D step 2 区别仅是 hint source. 如果 master inherent 难解 (我们 hypothesis), 换 hint source 不解决
- 但 paper 实测 hint 跟 CP-SAT pose-bool master 在 paper-scale 上加速 — 我们 scale 是否也 work 未知

## paper 自身的 limitations

paper abstract 没明确给数字 (e.g. 加速倍数 / problem scale). 需要全文核实:

- paper 实测 facility 数 (n)?
- paper 实测 location 数 (m)?
- paper 解的 problem 是 pure QAP (assignment) 还是包含 routing / multi-commodity flow?
- CDCL 跟 CP-SAT 速度差到底几个 orders-of-magnitude?

校验后 unanswered:
- paper v3 13 KB 体积异常小 (比 v1/v2 533 KB 小 40x). 可能 metadata-only update, 真实质内容可能没变
- 单 paper, 零 follow-up paper in 2026-01 ~ 2026-05 窗口
- 没独立复现实测

## 包内信息

paper 全文未在包内 (arxiv 公开). 包仅含 abstract + 项目 fit 评估.

## 链接

- arxiv abstract: https://arxiv.org/abs/2512.18034
- PDF v1: https://arxiv.org/pdf/2512.18034v1
- PDF v3 (latest 2026-05-07): https://arxiv.org/pdf/2512.18034
