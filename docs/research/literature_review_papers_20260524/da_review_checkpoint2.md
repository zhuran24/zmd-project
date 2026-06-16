# Devil's Advocate Review — Checkpoint 2 (After Analysis)

**Agent ID**: a06884eb778f5b05b
**Model**: Opus
**Date**: 2026-05-24
**Reviews**: Top 3 文献推荐（README.md Tier 1/2/3）

---

## Verdict: REVISE

3 推荐里 1 个保留降级、1 个降级拆分、1 个 **CRITICAL KILL 或硬 gate**。

---

## Critical Issues (Blocks)

### C1. 推荐 2 (SCIP-PB) — paradigm transfer claim 根本不成立

**Steel-man**: SCIP-PB 跟 HiGHS 不同 paradigm (cutting planes vs LP simplex)，PB Competition 实证冠军，跟 pose-bool form 1:1 对齐。

**Attack**:

1. **HiGHS 死因诊断错误，导致 SCIP-PB 类比失效**。项目 memory `[[project-30gb-real-culprit-power-coverage]]` 明确：HiGHS / master 30 GB peak 死因**不是 LP simplex**，是 **propagation buffer × workers**。SCIP-PB 也是分支搜索 + propagation，同样会爆 propagation state。"paradigm 不同" 是 surface paradigm，不是 RAM scaling paradigm。

2. **Latency-bound 矛盾**：memory `[[project_workload_latency_bound_not_bandwidth]]` 锁定项目 random pointer chasing + L3 spill 是绝对 latency-bound。SCIP-PB cutting plane separator 是稀疏矩阵随机访问 + PaPILO presolve 是 graph 操作 — **比 CP-SAT 更 pointer-chasing 不更少**。

3. **Survivorship bias 致命**：1207-759=**448 unsolved**。PB Competition instance 通常 sparse PB (e.g., MaxSAT-style)。项目 pose-bool master 是 dense linear (port/power/connector/area 全 dense coupling) — 几何形状更接近未解 448 那批。跟 HiGHS PoC 完全同款失败模式 (minimum model -79% RAM 假 win，加 power_coverage 后 42 GB 死)。

4. **5M clauses KILL 条件是虚的**：pose-bool master 现 280K vars × O(facility instance) coupling，OPB encoding 必然产 **10M+ clauses**。5M cap 设计成 "100% trigger 早死"，掩盖了真正的 build 风险。

5. **历史模式**：L15 set-packing 同款失败 — "底层 paradigm sound + benchmark 实证" 但项目语境 master 多余约束让 paradigm 失效。SCIP-PB 是 **L15 加强版重蹈**。

**Action**: KILL 或 Phase 0 cheap gate 必须先做 **20-inst dump 看 clause count + RAM** (4h spike)，不要直接进 Phase 1。

---

## Major Issues

### M1. 推荐 3 (Pessoa stabilization) — LP→CP transfer 未验证

**Steel-man**: Cand C Phase 1 GO，dual stabilization 是 CG cycling 标准解药。

**Attack**: Pessoa 2018 dual stabilization 前提 **LP master + dual variables continuous**。项目 cand C 是 **pose-bool master + CP**，dual 是 LP relaxation 的 m9 proxy — 不是真 dual。把 LP-stabilization 直接搬 CP 会出现：

- proxy dual 在 stabilization 下可能 **drift 离真 dual 更远**，让 m10 sound bound ramp 失效
- da Silva 2024 Ryan-Foster branching 假设 binary master variable — pose-bool 满足，但 **non-binary extension 在项目里没有 use case**，引用是 over-citation

**Action**: 保留 Fahle 2002 (CP pricing 直接相关)，Pessoa/da Silva 降级 Tier 3 → 选读。

### M2. 推荐 1 (Perron 2023) anchoring 偏强

**Steel-man**: 项目主 solver 作者唯一 internal paper，必读。

**Attack**: 27 paradigm 死路里 **solver-knob 类只占 ~3 个** (R5 shared_tree, linearization_level, workers)。多数死路是 paradigm 层 (cell-cut/lazy-demand/anchor slicing/witness preflight)。读 Perron paper 解答 "RAM 涨为啥" 不能 inform paradigm 选择 — 这是 **diagnostic value 高、prescriptive value 低**。"必读 Tier 1" 标签过强。

**Action**: 保留但降级为 "诊断工具，不是 paradigm 输入"。

---

## Minor Issues

- **m1. Confirmation bias 局部成立**: Top 3 全 confirm 当前路径，没有一个推荐挑战 cand C 本身。cand C Phase 1 m9 proxy 跟 m10 sound bound 的 gap 在 5/20/40/80 ramp 越大 — 这个 trend 没人 challenge。
- **m2. PB Competition 跟 70×70 grid 几何根本不一样**: PB Competition instance 平均 ~10K vars，项目 280K vars。28× scale gap，没有 sub-linear scaling 证据。

---

## Observations

- 推荐 2 cheap gate (2-3 day) 本身是健康的 (Phase 0 cheap gate workflow 是项目 lesson)，但 KILL 条件设计太松。
- Fahle 2002 CP-based CG 是 **真正最相关** 那一篇，被埋在 Pessoa/da Silva 包里。

---

## Strongest Counter-Argument

> "SCIP-PB 跟 HiGHS 表面 paradigm 不同 (cutting plane vs simplex)，但 **RAM scaling root cause 同款** — propagation state × parallel workers × dense coupling。项目 memory 已经记录 HiGHS 死因不是 LP simplex 是 propagation buffer，推荐 2 的 paradigm-shift claim 是 **基于过时的 HiGHS 死因诊断**。再叠加 latency-bound 不变 + dense linear 几何不像 PB Competition 那 759 解的部分 + 项目 27 paradigm 死路里类似套路 (L15, Path 18) 已死 — 这是 **第 28 个 paradigm 死路的高概率候选**，不是 paradigm shift bet。"

---

## What's Missing

1. **Cand C Phase 1 → Phase 2 真正 blocker 诊断** — m9/m10 gap ramp 5→80 inst 怎么变？这才该是 Tier 1。
2. **Pose-bool master scaling 文献** — 280K vars CP-SAT 是不是已经撞架构上限？应找 "large-scale CP-SAT in production" case study (Google routing/scheduling 实测数据)，不是 internal mechanism paper。
3. **跟死掉的 paradigm 的 differential diagnosis** — 任何新推荐都该 explicit 解释 "为啥这次不会跟 L15/HiGHS/v8 同款死"。Top 3 都没做这一步。

---

## Stress Test Results

| Test | 推荐 1 (Perron) | 推荐 2 (SCIP-PB) | 推荐 3 (Pessoa+) |
|---|---|---|---|
| **Stranger test** (外行人 1h 内能 challenge?) | 通过 — 诊断工具 claim 合理 | **失败** — paradigm-shift claim 撞项目 memory | 通过 — 但价值高估 |
| **Reverse test** (反向假设也成立?) | 通过 — internal paper 不一定 inform paradigm 选择，这个反向也对 | **失败** — "HiGHS 死 SCIP-PB 不死" 反过来 "SCIP-PB 同样死" 同样有据 | 部分失败 — LP-stabilization 在 CP 反而可能害 m10 |
| **Empirical test** (历史 data 支持?) | 弱通过 — 项目历史 solver-knob 改动 ROI 不一致 | **失败** — L15/HiGHS/v8 三个先例都是同款 "sound paradigm + benchmark 实证" 后死 | 通过 — Fahle 部分；Pessoa LP→CP 无实证 |
| **Cost-benefit test** (worst case 损失?) | 1h 通过 | **2-3 day Phase 0 + 第 28 paradigm 死路风险** — 严重 | 0.5 day 通过 |

---

## 最终建议（Revised Top 3）

- **Tier 1 诊断参考 (1h)**: Perron, Didier & Gay (2023) The CP-SAT-LP Solver — 降"Tier 1 必读"为"诊断参考"
- **Tier 2 主线直接相关 (Cand C Phase 2 必读)**: Fahle, Junker, Karisch, Kohl, Sellmann & Vaaben (2002) CP-based CG — 升 Tier 2
- **KILL 或硬 gate**: SCIP-PB / RoundingSat paradigm shift bet — 4h spike + differential diagnosis "为啥不跟 L15/HiGHS 同款死" 写得出来才进 Phase 0；写不出来 KILL

**降级**: Pessoa 2018 / da Silva 2024 → Tier 3 选读 (LP→CP transfer 未验证)。

**新 Tier 1 缺口（应补充调研）**:
- m9/m10 gap ramp 诊断
- 大规模 CP-SAT production case study (Google routing/scheduling 实测)
- 跟死掉 paradigm 的 differential diagnosis 模板

---

## Concession Threshold Log

按 DA agent v3.0 protocol，若用户/Claude 主对话对这些 finding rebut：

| Finding | 起始 attack 强度 | Concession threshold |
|---|---|---|
| C1 (SCIP-PB) | High — 拿项目 memory 直接对账 3 条 | Score 5/5 only (要新 evidence 推翻 HiGHS 死因诊断 或 SCIP-PB clausal compactness 实测) |
| M1 (Pessoa LP→CP) | Medium — solver-agnostic 论证有，但项目 m9/m10 ramp 实测未做 | Score 4/5 (要 m9/m10 在 stabilization 下实测稳) |
| M2 (Perron anchoring) | Medium — diagnostic vs prescriptive 分类合理但不绝对 | Score 4/5 (要举例 internal paper 反推 paradigm 选择) |
