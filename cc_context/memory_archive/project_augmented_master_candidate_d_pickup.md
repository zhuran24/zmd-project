---
name: augmented-master-candidate-d-pickup
description: "Next session pickup point — augmented master Candidate D 路线 (跟之前 Path 17 D2 sub-problem 不同). 是真 untested paradigm: master 内置 D2 vars (u + e + flow conservation), wall budget 放 10x (600s). ROI 6-10h Claude. 23 lever 全 verdict 后 user 明确 sharp 抓出我误把 sub-problem 路线当 augmented master 验证, 600s wall 实际没用上"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

# Augmented master Candidate D pickup (Next session)

> ⚠️ **SUPERSEDED (2026-06-02 标注)**: 下面"## Status 待做 / Next session pickup"是**当时的 live 计划**, 但这个 paradigm **已执行并死** —— 见 [[lever24-augmented-master-dead]] (603.9s UNKNOWN + RSS 32 GB, pose-bool scale 死)。**别把本文当待办 pickup**; 当历史读。现状权威源 [[windows-ninth-review-pending]]。

## Status

23 lever 全 verdict 后, user 2026-05-20 在 review Path 17 D2 Phase 2 结果时 sharp
抓出: **我做的 Path 17 D2 sub-problem 路线**, 不是 user 期望的 **augmented master**
路线. 600s wall budget user 之前明确说要放 10x 解锁 Candidate D, 我实施时**误读
为 sub-problem budget**, 实际 master 仍 100s 内 OK + sub-problem 0.15s 完, **600s
完全没用上**.

augmented master Candidate D 是真 **untested** paradigm — 23 lever 全在 pose-bool
master 不动 + cut 反馈框架内. 这是 GPT v7 Proposition 2 的 "换 master form" 路径
(实测 only Path 16 GOC-C2 全图 routing 撞 RAM 资源爆, 但 Candidate D 比 GOC 轻 6x
vars).

## 跟之前 Path 17 D2 sub-problem 的区别

| 维度 | Path 17 D2 sub-problem (已做, 死) | augmented master Candidate D (待做) |
|---|---|---|
| master form | pose-bool 不动 | 内置 D2 vars (u + e + flow conservation) |
| master.solve wall | 180s (跟 baseline 一样) | **放到 600s** (10x baseline) |
| D2 信息来源 | sub-problem 后台跑, INFEASIBLE 后翻译 cut | master 自己 search (placement + flow) 同 model |
| cut form | instance-pose conjunction no-good (跟 RAB-SEP 同) | 不依赖 cut, master 直接 detect infeasibility |
| sound 性 | sub-problem INFEASIBLE → master cut sound | master FEASIBLE 不 sufficient; INFEASIBLE 是 sufficient (master direct cut 掉 D2-INFEASIBLE 解) |

**核心区别**: sub-problem 路线 cut 表达力被 master pose-bool 卡死 (6 paradigm 实测
全死). augmented master 不靠 cut, 让 master 直接看见 D2 info — 真换 master form.

## 实施 plan

**Phase 0 cheap gate (~1h Claude pace + ~10-30 min wall)**:

写 `paths/17_candidate_d_commodity_flow/phase3_augmented_master_probe.py` (~300 LOC):

1. monkey-patch `pose_bool_exact_master.PoseBoolExactMasterDelegate.build` 在
   `model.solve` 之前加 D2 vars (u + e) + capacity + channeling + flow conservation
2. 跑 master.solve 单 anchor (22,28) 27×15 with **EXACT_B1_MASTER_WALL_SECONDS=600**
3. 量化:
   - augmented master vars count (target ≤ 250K)
   - constraints count (target ≤ 650K)
   - RSS peak (target ≤ 12 GB, 跟 GOC Phase 0 同 cap)
   - master.solve wall (≤ 600s)
   - status (期望 OPTIMAL/INFEASIBLE/可继续 progress)

GO 条件:
- master.solve status ∈ {OPTIMAL, INFEASIBLE} in 600s (不持续 UNKNOWN)
- vars ≤ 250K, constraints ≤ 650K, RSS ≤ 12 GB

NO-GO:
- master 600s UNKNOWN — paradigm 同 Path 08 同 dead zone (200K-330K vars 600s 仍 UNKNOWN)
- RSS 爆 — 同 Path 16 全图 routing state pattern
- master FEASIBLE 但 binding/routing 仍 reject — paradigm necessary 不 sufficient, 跟之前 paradigm 同质

## 数学结构 (从 GPT v7 plan Candidate D + Path 17 D2 实施)

vars:
- 现有 pose-bool: x[group, pose_idx] ~10K
- 加 u[k, c] BoolVar: ~50K (10 commodity × ~4700 free cells, ground layer 简化)
- 加 e[k, arc] BoolVar: ~190K (per directed arc, 4 dir × 4700 free × 10 commodity, prune out-of-grid)
- 总 vars ≈ **250K** (跟 Path 08 333K 同量级)

constraints:
- 现有 master: pose exactly-one + cell-exclusivity + power coverage
- 加 cell capacity: ~4700 AddAtMostOne
- 加 channeling e → u: ~190K × 2 = ~380K (但 e ⇒ u 是 AddImplication, 不 dense)
- 加 flow conservation per (commodity, cell): ~50K linear equations
- 总 cstr ≈ **400-500K**

关键: 加 D2 vars 时, port adherence + terminal balance 必须**conditional on
pose 选择** (跟 Path 17 实施 conditional terminal balance 同). Pose 选择 x_{i,p_i}
通过 forced port front cell u[k, fc] = 1 channeling.

## 复用 Path 17 实施

`src/models/d2_commodity_flow_core.py` 281 LOC 含完整 D2 model 构造逻辑. 关键复用:

- `_build_and_solve_candidate_d2` 函数体 (~150 LOC) 直接 lift 进 augmented master build:
  - u/e/capacity/channeling/flow conservation 代码
  - conditional terminal balance encoding (output_av_by_kc / input_av_by_kc / unconditional_balance)
- conditional channeling 要从 "assumption literal" 改为 "pose vars" (x_{i,p_i}):
  - 旧 (sub-problem): `model.Add(u_var == 1).OnlyEnforceIf(av)` 其中 av = owner_assumption
  - 新 (augmented master): `model.Add(u_var == 1).OnlyEnforceIf(x_{i, p_i})` 其中 x 是 master pose 选择
- terminal_balance per cell sum 也用 pose vars 替 assumption:
  - 旧: `sum(output_av) - sum(input_av)`
  - 新: `sum(x_{i_o, p_o}) - sum(x_{i_s, p_s})` for output/sink ports at this cell

## 不变 (保留)

- pose-bool master 现有结构 (exactly-one + cell-exclusivity + power coverage)
- binding subproblem 后跑 (port_specs 由 binding 决定)
- routing subproblem 真 verify final
- LBBD loop 结构

变的只是: **master 内多了 D2 vars 让 master 自己 search 时同时考虑 flow feasibility**.

## 3 个 unknown (Phase 0 cheap gate 测的)

1. **vars 数实际**: 估 250K, 但 channeling 可能让 CP-SAT 自动 expand. Path 08 不
   同 paradigm (port_active per pose) 同量级 vars 跑出来 333K. Candidate D 实际
   vars 跟估算多大偏差未知.

2. **600s 内 master 能 OPTIMAL 吗**: Path 08 (333K vars) 600s 仍 UNKNOWN. Candidate
   D vars 略低 (~250K) + 结构不同 (cell-flow vs port-conditional), CP-SAT 在
   cell-flow 上是否更高效 — 未知.

3. **sound 性**: master 加 D2 vars 后, 它给的 FEASIBLE 解**不一定 routing FEASIBLE**
   (D2 是 production C2 的 relaxation: 没分 ground/elevated layer, 没 belt grammar
   (splitter/merger), 没 bridge constraint). 但 master **INFEASIBLE 是 sufficient**
   (relaxation INFEASIBLE ⇒ production C2 INFEASIBLE). 这意味 paradigm 仍是 LBBD
   pattern, master 加 D2 给 layout 后 binding+routing 真 verify.

## ROI 估算 + decision

总投入估 6-10h Claude:
- Phase 0 cheap gate (~3-4h Claude + 30 min wall): 真验 master + D2 600s 能否
  OPTIMAL + 资源 fit
- 若 Phase 0 GO, Phase 1 production land (~3-4h Claude + 1h wall): 接进
  benders_loop env-gated hook
- 若 Phase 1 OK, Phase 2 multi-anchor 8 anchor max_iter=5 (~2h wall)

总成本跟之前 Path 14 PCR-CUT / Path 17 D2 同规模.

成败信号在 Phase 0 cheap gate. 1h 投资就出 verdict.

## context (为啥之前没走)

3 个原因 (per user 2026-05-20 review):
1. **implementation 默认 sub-problem**: LBBD 标准 pattern, 不动 master 实施安全快
2. **Path 08 历史 default 偏见**: 333K vars 645s UNKNOWN 让我默认任何 master augment 都死
3. **GPT review 没正式 propose**: v1-v5 默认 master 不动, v6/v7 切 framing 后 GPT 给 hard no-go

## entry points (next session)

新文件:
- `paths/17_candidate_d_commodity_flow/phase3_augmented_master_probe.py` — Phase 0 cheap gate
- 后 (Phase 1+): `src/models/d2_augmented_master.py` 或者直接 extend `pose_bool_exact_master.py`

env knobs:
- `EXACT_B1_MASTER_AUGMENT_D2=1` — 开关
- `EXACT_B1_MASTER_AUGMENT_D2_WALL_SECONDS=600` — wall budget (10x baseline)

代码复用:
- `src/models/d2_commodity_flow_core.py` (Path 17 D2 实施) — 模型构造逻辑
- `src/models/pose_bool_exact_master.py` — master 现有结构

## 23 lever 全 verdict status (verify before invest)

23 lever 全死 in pose-bool + cut framework. augmented master 是真 untested 路径, **跟之前 23 lever 不同 framework**. 投资基础是 sub-problem cut framework 真撞墙, augmented master 真没人验.

但 **augmented master 也可能撞 v7 Proposition 2 资源 dead end** (Path 16 实测全图 routing 资源爆). Phase 0 cheap gate 就是验它的资源是否 fit.

## Related

- [[d2-path17-verdict]] — Path 17 D2 sub-problem 完整 verdict (跟此 augmented 不同)
- [[goc-phase0-verdict]] — Path 16 全图 routing 资源爆 (跟此 augmented 类比)
- [[pgw-phase0-verdict]] — Path 15 PGW
- [[pcr-cut-phase5-verdict]] — Path 14
- [[paradigm-phase0-cheap-gate]] — workflow 8 次验证有效
- GPT v7 plan Candidate D 段 (`b1_phase6_review_package_v7.zip` inline)
- BOTTLENECK_STRUCTURE.md (v6+ 包) — 3 性质 framing
- MASTER_FORM_BASELINE.md (v7 包) — pose-bool master 表达力 limits + user hypothesis

## 链 (补连 2026-06-02 全覆盖审计 w5u712m2y)
- [[lever24-augmented-master-dead]] — superseded→superseding 前向边 (MEMORY.md 已记 superseded)
