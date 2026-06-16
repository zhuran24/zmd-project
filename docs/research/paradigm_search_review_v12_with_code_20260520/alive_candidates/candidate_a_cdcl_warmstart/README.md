# Candidate A — Hybrid CDCL + CP-SAT Warm-Start

## 当前项目状况

24 lever 全 verdict 死. paradigm 调研发现 2025-12 paper 提出用 CDCL (SAT solver) 当 feasibility oracle 给 CP-SAT optimizer 灌 warm-start hint. 是单一 paper, 没 follow-up.

## 为什么列为候选

paper: **"Accelerating Discrete Facility Layout Optimization: A Hybrid CDCL and CP-SAT Architecture"** (arxiv 2512.18034, 2025-12-19 submitted, latest v3 2026-05-07). Authors: Joshua Gibson, Kapil Dhakal.

paper 直接 domain: **discrete facility layout** (跟我们 problem 同类). paper 自己描述:
> "we developed a novel 'Warm-Start' hybrid architecture that utilizes CDCL to rapidly generate valid feasibility hints, which are then injected into a CP-SAT optimizer."
> "CDCL excels at feasibility detection but struggles with optimization"

跟当前项目 hint 路径区别:

| 维度 | 当前 D step 2 community blueprint hint | Candidate A CDCL warm-start |
|---|---|---|
| hint source | 用户手调 blueprint (human-curated) | CDCL solver-derived feasibility solution |
| hint coverage | 225 entry (5/13 blueprint) | 完整 valid feasibility 解 |
| hint reliability | 几何不可能 match 大 candidate (≥area 500) | 跟 problem scale 同步 (CDCL 跑 feasibility) |
| paradigm 性质 | hint 不当 cut, master form 不变 | hint 不当 cut, master form 不变 |

## 理论上潜在收益

当前 D step 2 hint trial7 (master 3600s + workers 8) 实测仍 UNKNOWN. Phase 6 community hint 798 AddHint 零损耗 (telemetry 验证) 但 master inherent 难解. 候选 A 跟它 source 不同 (SAT-derived vs human-curated). 如果 CDCL 能给 master 更好的 starting point, 可能解锁 master.solve 0% CERTIFIED rate.

## 理论上潜在限制

- paper 底层是 **QAP-style assignment** (每 facility → location 一对一), 不含 routing / port direction / power coverage / commodity flow
- 我们 problem 多含 routing + port + power_coverage + 10 commodity, 跟 paper 实测 problem 类多约束层
- 单一 paper, 5 个月零 follow-up paper. paradigm 不是 active 研究方向
- CDCL 解 feasibility 跟 LBBD framework 的 binding/routing sub-problem 都是 sufficient feasibility — 实质都是给 master 一个 valid placement, 这点跟 D step 2 community blueprint hint 同 dim

## 实施 plan (未实施)

| Phase | 工作 | 估时 (Claude pace) |
|---|---|---|
| Phase 0 cheap gate | 写 minimum SAT model (只 placement + power coverage, 不含 routing), 用 CaDiCaL / MiniSat 跑 feasibility, 把 solution 转 hint 灌 master | 1-2 day Claude + ~10-30 min wall |
| Phase 1 production | 接 binding/routing 之后, hint 集成进 outer search | ~1 周 Claude |
| Phase 2 multi-anchor | 8 anchor × max_iter=5 跟 baseline 比 | ~2h wall |

## Phase 0 cheap gate GO/NO-GO 信号

**GO 条件**:
- ≥1 anchor master.solve(time_limit=600s) 在 hint 注入后 OPTIMAL/INFEASIBLE in budget
- hint 转换成功 (SAT-model + master-pose 模型对齐)
- CDCL 跑 feasibility 在 ≤60s

**NO-GO 条件**:
- 跟 D step 2 hint 同 quality (798 AddHint 零损耗但 master 仍解不动)
- CDCL feasibility 跑 > 60s (没比 master.solve 快)
- SAT model 跟 pose-bool master 不能 1-1 对齐 (encoding gap)

## paper 关键 caveat (校验后)

校验 (2026-05-20):
- paper 是单作者团队 (Gibson + Dhakal), 零独立复现 / follow-up
- v3 (2026-05-07) PDF 13 KB, 比 v1/v2 533 KB 小很多 — 可能是 errata / withdraw 性质 update, 待 paper 全文核实
- paper 底层 problem 是 QAP-style (assignment), 不是我们 placement + routing combined

## 包内 paper 信息

详 `paper.md`.
