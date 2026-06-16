# Paradigm Death Timeline — 27 lever consolidated

> **Status**: Day 16c-2 补做 (2026-05-21) — 上次 prep 清单项 2 没做的 consolidated timeline
> **Why this doc**: Phase 0 Day 13-17 期间 Gemini cross-check 时, 给 LLM 只 paste B Design v2 framework 不够 — LLM 看不到 27 lever 死法历史, 可能 propose 已死 paradigm 又不自知. 这是 paradigm-investigation transcript 的 consolidated reference.
> **来源**: 27 个 memory file + 25 个 `docs/research/` 文件夹的 chronological aggregation

## 1. 5 类死法分类

按死因 axis 分:

### Class A — Cut amplification 不够 (cut 太弱)

cut 形式 sound 但**不 sufficient** — necessary condition pass 但实际 INFEASIBLE
未被表达. 通常 cut 在 LBBD loop 不收敛 / 不学到全部 infeasibility 类型.

| Lever | Date | Memory | 死法概述 |
|---|---|---|---|
| Path 12 RAB-SEP | 5-18 | [[project_b1_phase6_path1_dead]] | routing-aware binding separation, cert tight 8/8 UNPROVEN. 单独 binding-port cut 不 sufficient |
| Path 13 SAC-Hull | 5-18 | (paradigm_session_2026_05_18_19) | separating axis capacity hull, violations 减 80% 但 necessary ≠ sufficient. L2 工作但 binding/routing reject |
| Path 14 PCR-CUT | 5-19 | [[project_pcr_cut_phase5_verdict]] | patch belt CP-SAT min-cut, multi-anchor 0/8 CERTIFIED. cut 表达力被 pose-bool master 卡死 |
| D2 Path 17 | 5-20 | [[project_d2_path17_verdict]] | commodity cell-flow + arc + conditional flow conservation, multi-anchor 0/8 CERTIFIED 跟 Path 12-14 同质死法 |
| B1 Phase 6 path-2 lazy demand cut | 5-18 | [[project_b1_phase6_path2_dead]] | lazy demand cut UNPROVEN 778s 10 iter 不收敛, sum(blockers) ≤ K-demand OnlyEnforceIf 不约束 binding port-selection |
| B1 Phase 5 cell cut | 5-18 | [[project_b1_phase5_cell_cut_findings]] | 3 种 cell-level cut 形式实测均 over-restrictive, master 不知 binding 选哪些 port active |

### Class B — Cut accumulation 不够 (cut 收敛失败)

cut 单条 sound 且 sufficient, 但 cut 总数 / 强度 / accumulation rate 不够,
master 多 iter 仍 UNPROVEN.

| Lever | Date | Memory | 死法概述 |
|---|---|---|---|
| L16 Lazy Power Completion | 5-17 | [[project_l16_lazy_power_completion_phase0]] | master 端 81.8s OPTIMAL (vs production 30 min UNKNOWN), 但 cut 端 loose 134→133 stuck / tight 134→123 振荡不收敛 |
| Lever 25 IHS | 5-20 | [[project_lever25_ihs_dead]] | Implicit Hitting Set Phase 0 cheap gate 10 iter 全 size=1 core (p50=1.0), offline HS compression=1.0 (HS=union 完全退化) |

### Class C — Cut family abstraction 不够 (cut family 表达力差)

设的 cut family 数学上完备但**等价于 full no-good**, 几何上不能用 sub-linear
size cut. 168h budget 内不可能枚举.

| Lever | Date | Memory | 死法概述 |
|---|---|---|---|
| Path 18 LIC (layout-invariant cert) | 5-20 | [[project_path18_layout_invariant_cert_dead]] | m1=2 远低于 ≥100 target — cell-front pattern 几乎决定 pose (per-instance mean=1.74), cut lift 不跨数量级 |
| Lever 26 Benders symmetry | 5-20 | [[project_lever26_benders_symmetry_dead]] | typed automorphism graph + cut-orbit lifting, m5=1.0 (5/5 core 全 trivial orbit), nontrivial 仅 8, symmetry 被 ghost/boundary/port_dir 打碎 |

### Class D — Master augmentation 撞 scale 墙

master variable space 重新设计后 build/solve 撞 RAM/wall budget.

| Lever | Date | Memory | 死法概述 |
|---|---|---|---|
| Lever 24 augmented master | 5-20 | [[project_lever24_augmented_master_dead]] | Phase 3 cheap gate single anchor 603.9s UNKNOWN + RSS 32 GB. pose-bool master 280K pose vars × 8 ports/pose = 2.36M OnlyEnforceIf 约束 |
| GOC-C2 Phase 0 | 5-19 | [[project_goc_phase0_verdict]] | 全图 owner-optional + virtual terminal, production scale 30 min build 未完成, RSS 25 GB > Pre2 cap 12 GB |
| PGW-UB Phase 0 | 5-19 | [[project_pgw_phase0_verdict]] | positive witness + UB closure, 8 anchor 实测 P0.3 locality 全 fail, top5_cov 10x off, routing residual 全域均匀分散不 spatial-cluster |
| L23 (rewrite path exhausted) | 5-15 | [[project_rewrite_path_exhausted]] | 所有 viable 重写路径实测后 hard verdict: 单机 48 GB + 准确性必保 + 现 solver, 决定性收益物理不可达 |

### Class E — Column generation / 几何死结

cand C 系列 — column generation paradigm 设计完备但撞 96% utilization 几何死结
(boundary_storage_port × perimeter trap).

| Lever | Date | Memory | 死法概述 |
|---|---|---|---|
| cand C Phase 0 GO | 5-21 | [[project_cand_c_column_generation_phase0_go]] | 20-inst 8/8 metric GO, 唯一真换 master variable basis 方向 ✅ Phase 0 GO |
| cand C Phase 1 GO (4-ramp) | 5-21 | [[project_cand_c_phase1_go]] | 5/20/40/80 inst 全 GO, m10 sound 性维持, m9 proxy dual 跨所有 ramp 0% ✅ Phase 1 GO |
| cand C Phase 2 v3 — 160/266 INFEASIBLE | 5-21 | [[v14-review-findings]] 内 cand_c_phase2_v3 | A1/A2/A3 3 fallback paradigm 全 land 但 160/266 实测仍 INFEASIBLE. 96% utilization 几何死结 |

### Class F — 早期/其他死路

| Lever | Date | Memory | 死法概述 |
|---|---|---|---|
| v8 anchor slicing | 5-16 | [[project_v8_anchor_slicing_dead]] | GPT v8 patch clean apply + 2211 pytest pass + build wall -92% 真实, 但单 anchor 5 min UNKNOWN 5.5M branches 跟 trial7 1h UNKNOWN 同 quality. 错估同 v3 |
| v10 witness preflight | 5-16 | [[project_v10_witness_preflight_dead]] | GPT v10 patch clean apply, 算法 sound 但**前提错估** — community blueprint 缺 41 mandatory, greedy 填位置破坏 27×15 空地, compatible anchor=0 |
| L14 weighted occupancy | 5-16 | [[project_l14_weighted_occupancy_dead]] | Farkas weighted-occupancy blocker oracle PoC, interior anchor LP=1.000 exact 永远不可 cert |
| L15 set-packing prover | 5-17 | [[project_l15_setpacking_prover_dead]] | minimum set-packing 核心 CP-SAT 几秒搞定, 真瓶颈是 master 多余约束 (port/power/connector). paradigm 攻错层 |
| Path 12 RAB-SEP Phase 6 | 5-18 | [[project_b1_phase6_path1_dead]] | master 持有 port-selection 4 个 form 全 verdict 死 (v1 2.3M vars UNPROVEN, v2 anchor bug, v3 8w 300s UNKNOWN) |
| B1 Phase 4 routing convergence 🟡 | 5-18 | [[project_b1_phase4_routing_convergence]] | port-direction-aware cut 修 inferred counts 但 routing precheck front_blocked ~500-610 ports 系统性, pose-bool master 不知 port direction |

## 2. 共同 root cause (4 axis)

跨 27 lever 总结的 4 个 fundamental 限制:

### Root cause 1 — Pose-bool master 表达力 limits

B1 pose-bool master 280K pose vars × 8 ports/pose = 2.36M OnlyEnforceIf 约束.
master 不知 port direction / pole selection / belt routing, 任何 master OPTIMAL
都让 sub-problem oracle 拒绝. master 端 cut 学习不到 binding port_active /
routing path / power coverage 关联.

**6 paradigm 撞同墙** (Path 12/13/14/17/B1-path1/B1-path2): pose-bool master
是 cut 表达力 fundamental 限制.

### Root cause 2 — 96% utilization 几何死结

valley4_protocol_core 70×70 grid + 266 mandatory facility ≈ 4800 cells / 4900
total → 96% utilization. boundary_storage_port × perimeter trap: 46 pose × 3
cells = 138 cells 必 100% 铺满 left+bottom 138 cells. 任何 ghost 切 left/bottom
都触发 Hall infeasibility. cand C 160/266 全 INFEASIBLE.

### Root cause 3 — Cell-front pattern 已 break symmetry

per-instance 几何 high-resolution 已让 sub-pose 等价性消失. LIC m1=2 (cell-front
近 deterministic pose), Benders symmetry m5=1.0 (orbit 全 trivial). Cut lift /
symmetry 无 free lunch.

### Root cause 4 — Single-machine RAM 不可扩

48 GB RAM + 现 solver 下, augmented master / GOC-C2 / PGW-UB 等 RAM scale 全
撞 25-32 GB peak (Pre2 cap 12 GB)/(单机 48 GB) 上界. L23 audit 已确认重写路径
全穷尽.

## 3. B 设计要 explicit 处理的 5 unsolved issue

按 root cause 提炼出 Phase 0 / Phase 1 / Phase 2 必须解决的 5 件事:

### Issue 1 — 96% utilization 几何死结

**B Design 应对**: Family 1 region_capacity + Family 6 shape_packing_hall
拦 boundary perimeter / interval scheduling INFEASIBLE. 已在 Phase 0 spec
covered (Day 15 / Day 16a).

### Issue 2 — Boundary × perimeter 容量

138 cells 100% saturation 不允许任何 boundary 上 facility 占其他 cells. v14
review GPT pro 已 catch (boundary source-of-truth correction Day 1-2 commit
976bc10). Active_assumption "left_or_bottom_boundary_saturation" cover.

### Issue 3 — Manufacturing cluster trap (132 个最大类)

最大 facility group (manufacturing_3x3, 132 instance). 这类 facility 在 70×70
内分布密集, 互相挤压. Family 5 pattern_nogood + Family 3 port_exposure 覆盖.
**Phase 0 Day 16c-2 评估**: 现 spec **不足** — Family 5 pattern_nogood literal
全 facility full assignment no-good 退化, 跟 v14 review Pattern no-good >50%
stop-ship signal 矛盾. Day 18-21 需 dedicated solution (e.g. orbit-aware
pattern lift, 防 132! permutation 撞墙).

### Issue 4 — Routing 反馈翻译成强 cut (不是 pose no-good)

routing/binding sub-problem 端 INFEASIBLE 反馈, 应翻译成 region/cutset 级 cut,
而**不是 pose-level no-good**. Family 2 cutset + Family 4 component_reach
cover, Phase 0 Day 17 详细 spec (现 skeleton).

### Issue 5 — m10 sound 性跨 scale 维持

cand C m10 integer validator 在 80-inst 维持 True, 但 160/266 false 是因为
INFEASIBLE 不是 m10 sound 性破坏. B Design cut framework m10 等价是 validator
(§6) 跨 scale 必须 sound. Phase 0 Validator 每 family 独立重算 cert 设计已 cover.

## 4. F5 全局电力孤岛反例评估 (Gemini round 14 task B)

Gemini 提的 F5 反例: Ghost 纵切宽 15 把 grid 切 Left/Right, protocol_core 在
Left, crusher/shop 在 Right. F1/F2/F4/F6/F7 全静默但实际 INFEASIBLE: Right 区
pole `R_conn=10 < ghost width 15`, 没法跨 ghost 连回 Left 的 protocol_core.

### 撞已死 paradigm 检查

- **vs Path 14 PCR-CUT (belt cutset min-cut)**: PCR-CUT 拦 **belt routing** 跨
  ghost 不可达, 死法 patch CP-SAT scale. F5 是 **power pole network** 不可达,
  pole BFS 是 sub-linear graph (R-radius pole 链) 不是 patch CP-SAT. **不撞**.
- **vs Path 13 SAC-Hull**: 是 spatial capacity LP cut, 跟 connectivity 无关. **不撞**.
- **vs Lever 23 D2 commodity flow**: master 端 cell-flow, 跟 power network
  reachability 间接. F5 应该是 sub-problem oracle 层独立 BFS, 不挤 master scale. **不撞**.

### 加 Family 8 power_grid_reach 还是 Family 4 generalize?

两选项:
- **A**: Family 4 component_reach 语义泛化. 现 Family 4 cert 含 `(src, sink,
  witness_path)` BFS on `state.free_cells`. 加 graph kind tag (`belt_routing` vs
  `power_pole_network`), cert 加 `pole_connectivity_radius` 字段. 单 family
  含两 reachability semantics.
- **B**: 加 Family 8 `power_grid_reach` 独立 family. cert 全 power-specific
  (pole_radius / pole_chain_witness / connectivity_graph). 跟 Family 4 表面相似
  但 schema/validator 分.

**推荐 B**: power network 跟 belt network 是不同 graph (pole 链 vs free_cell
BFS), 同 family 容易 schema 字段冲突. 独立 family schema 清晰.

**Phase 0 Day 17 应做**:
- 加 Family 8 power_grid_reach 完整 spec (跟 Family 1/6/7 同 12 段)
- F5 fixture (red_fixtures/F5_power_grid_disconnect.md) 写完整
- F5 fixture 用 Family 8 cut 拦截验证

## 5. Cross-ref

- [[v14-review-findings]] — GPT pro + Gemini round 12/13 v14 review verdict
- [[phase0-b-prep-progress]] — Phase 0 Day 1-16c 进度
- [[gemini-review-algorithm-math]] — algorithm/math layer cross-check 规则
- `docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_14_cut_families.md` — Gemini round 14 答复 (Day 16b 后)
- 各 lever single-memory file (17 个 in memory/)
- 各 paradigm investigation 文件夹 (25 个 in docs/research/)
