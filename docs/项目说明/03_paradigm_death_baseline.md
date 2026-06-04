# 03 — 已 verify 不通的 paradigm (数学死路 baseline)

本节按**数学根据 attempt** 分类 27 lever (paradigm_death_timeline.md 按时间 + 死因 axis 分 5 Class, 本节按"当时试什么数学方向"reorganize). 不重复 timeline 详, cite memory + timeline.

### 4.1 完整 master 重写 paradigm — pose-bool / augmented / GOC variant 全死

**数学 attempt**: 改 master variable basis, 让 master 自己解 pose-level + binding + routing + power 联合优化, 不依赖 sub-problem.

**lever**:
- **L11-L16 B1 pose-bool master** — 27×15 interior pose-bool 7.2s FEASIBLE (vs coord 30 min UNKNOWN). Phase 4 routing convergence 🟡 ~500-610 ports 系统性, pose-bool master 不知 port direction. Phase 5 cell cut 3 form 全 over-restrictive. Phase 6 path-1 4 form 全 verdict 死. [[project-b1-phase6-path1-dead]]
- **Lever 24 augmented master** — 280K pose × 8 ports = 2.24M OnlyEnforceIf, 603.9s UNKNOWN + RSS 32 GB. [[project-lever24-augmented-master-dead]]
- **GOC-C2** — 全图 owner-optional, RSS 25 GB > 12 GB cap. [[project-goc-phase0-verdict]]
- **PGW-UB** — positive witness + UB closure, locality 全 fail. [[project-pgw-phase0-verdict]]
- **L23 rewrite_path_exhausted** — 所有 viable 重写路径实测后 hard verdict. [[project-rewrite-path-exhausted]]

**数学根据失败的层**: 
- **Root cause 1** (Class A death timeline): pose-bool master 表达力 fundamental limit. master 不知 binding port-selection / routing path / power coverage 关联, 任何 master OPTIMAL 都让 sub-problem oracle 拒绝.
- 6 paradigm 撞同墙 (B1 path 1 / path 2 / Path 12 RAB-SEP / Path 13 SAC-Hull / Path 14 PCR-CUT / Path 17 D2)

**教训**: master variable basis 改不通. **不能再 propose master 重写**.

### 4.2 Sub-problem cut paradigm — over-restrictive / 不收敛 全死

**数学 attempt**: 在 sub-problem (routing / binding / flow) INFEASIBLE 时找 cut, master 不动.

**lever**:
- **Path 12 RAB-SEP** (routing-aware binding separation) — cert tight 8/8 UNPROVEN. 单独 binding-port cut 不 sufficient. [[paradigm-death-timeline LP12]]
- **Path 13 SAC-Hull** (separating axis capacity hull) — violations 减 80% 但 necessary ≠ sufficient. L2 工作但 binding/routing reject. [[paradigm-session-2026-05-18-19]]
- **Path 14 PCR-CUT** (patch belt CP-SAT min-cut) — Phase 0-4 GO, Phase 5 multi-anchor 0/8 CERTIFIED. cut 表达力被 pose-bool master 卡死. [[project-pcr-cut-phase5-verdict]]
- **D2 Path 17** (commodity cell-flow + arc + conditional flow) — multi-anchor 0/8 CERTIFIED 跟 Path 12-14 同质. [[project-d2-path17-verdict]]
- **B1 Phase 5 cell cut** — 3 种 cell-level cut 全 over-restrictive. [[project-b1-phase5-cell-cut-findings]]
- **B1 Phase 6 path-2 lazy demand cut** — UNPROVEN 778s 10 iter 不收敛. [[project-b1-phase6-path2-dead]]
- **L16 Lazy Power Completion** — master 端 81.8s OPTIMAL, 但 cut 端 loose 134→133 stuck / tight 134→123 振荡. [[project-l16-lazy-power-completion-phase0]]

**数学根据失败的层**:
- **Root cause 1**: cut 表达力被 pose-bool master 卡死 (master 不知 sub-problem 关联)
- **Root cause 2** (Class A): cut amplification 不够 — 单 cut sound 但不 sufficient
- **Root cause 3** (Class C): cut family abstraction 不够 — 等价 full no-good, 几何上不能 sub-linear

**教训**: 简单的 sub-problem nogood lift 跨 multi-anchor 必败. B Design v2 cut framework 不走这条 — 而是用 family-specific 数学根据 (Menger / Hall / pigeonhole) 作 sound deduction, 不是 ad-hoc cut form.

### 4.3 Cert lifting paradigm — symmetry / orbit lifting 死

**数学 attempt**: 学到 cert 后试 lift 跨 instance / 跨 orbit / 跨 candidate, 减 cut 数.

**lever**:
- **Path 18 LIC (layout-invariant cert)** — m1=2 远低于 ≥100 target. cell-front pattern 几乎决定 pose (per-instance mean=1.74), cut lift 不跨数量级. [[project-path18-layout-invariant-cert-dead]]
- **Lever 26 Benders symmetry** — typed automorphism graph + cut-orbit lifting, m5=1.0 (5/5 core 全 trivial orbit). symmetry 被 ghost/boundary/port_dir 打碎. [[project-lever26-benders-symmetry-dead]]

**数学根据失败的层**:
- **Root cause 3** (Class C): cell-front pattern 已 break symmetry. per-instance 几何 high-resolution 让 sub-pose 等价性消失.
- LIC m1=2 / Benders symmetry m5=1.0 都 measure 出 lifting "free lunch" 不存在.

**教训**: 项目 layout 是 anti-symmetry 的 (各 instance + ghost + boundary + port direction 全打碎对称). PROJECT_LOCK §3A 禁跨 instance lifting 是这一层的结论. **within-instance** lifting (PCR-CUT Phase 3 signature lifting) 可以 sound 但跨 instance 必死.

### 4.4 Column generation paradigm — cand C 96% utilization 几何死结

**数学 attempt**: 用 LP-based column generation, master 持 column (pose 子集) 不持 full pose-bool. Phase 0 Phase 1 m9 dual + m10 sound 性 8/8 GO.

**lever**:
- **cand C Phase 0** — 20-inst 8/8 metric GO, 唯一真换 master variable basis 方向 ✅ [[project-cand-c-column-generation-phase0-go]]
- **cand C Phase 1** (4-ramp) — 5/20/40/80 inst 全 GO ✅ [[project-cand-c-phase1-go]]
- **cand C Phase 2 v3 — 160/266 INFEASIBLE** — A1/A2/A3 3 fallback paradigm 全 land 但 160/266 实测仍 INFEASIBLE. [[v14-review-findings]] cand_c_phase2_v3

**数学根据失败的层**:
- **Root cause 2** (Class E): 96% utilization 几何死结. valley4_protocol_core 70×70 + 266 mandatory = 4800/4900 cells ≈ 98% (4800/4900). boundary_storage_port × perimeter trap: 46 pose × 3 cells = 138 cells 必 100% saturation. cand C column gen 数学 sound 但底层几何不变.

**教训**: paradigm 数学 sound 不等于 instance 可行. 项目 instance 几何是 fundamental constraint, 任何 paradigm 在 instance 真 INFEASIBLE 时都 INFEASIBLE. column gen 是 master basis 改而不是 instance 改, 不能改 instance 几何.

### 4.5 Set-packing prover / IHS paradigm — 攻错层

**数学 attempt**: 抽出 set-packing 核心独立解, 不动 master.

**lever**:
- **L15 set-packing prover** — minimum set-packing 核心 CP-SAT 几秒搞定 (corner 2.3s INFEASIBLE, interior 7s feasible). 真瓶颈是 master **多余**约束 (port/power/connector). paradigm 攻错层. [[project-l15-setpacking-prover-dead]]
- **Lever 25 IHS (Implicit Hitting Set)** — Phase 0 cheap gate 10 iter 全 size=1 core (p50=1.0), offline HS compression=1.0 (HS=union 完全退化). [[project-lever25-ihs-dead]]

**数学根据失败的层**:
- L15: paradigm 攻的是 set-packing 子结构, 但 instance 主瓶颈不在 set-packing — 在 port + power + connector 约束的组合. 抽掉子结构不解原问题.
- L25: IHS Phase 0 core size 全 1, hitting set 数学退化 trivial.

**教训**: paradigm investment 前**必 Phase 0 cheap gate** 验前提. L15 用 3 小时 PoC catch "攻错层", L25 用 10 iter cheap gate catch "core 全 trivial". [[paradigm-phase0-cheap-gate]] 来源.

### 4.6 Witness / weighted occupancy / heuristic blueprint paradigm — 前提错估 死

**数学 attempt**: 用 witness / weighted bound / community blueprint 作 hint 加速 master.

**lever**:
- **v8 anchor slicing** — GPT v8 patch clean apply + 2211 pytest pass + build wall -92% 真实, 但单 anchor 5 min UNKNOWN 5.5M branches. 错估 — 关注 build 没量 solve. [[project-v8-anchor-slicing-dead]]
- **v10 witness preflight** — community blueprint 缺 41 mandatory, greedy 填位置破坏 27×15 空地, compatible anchor=0. [[project-v10-witness-preflight-dead]]
- **L14 weighted occupancy** — Farkas weighted-occupancy blocker oracle, interior anchor LP=1.000 exact 永远不可 cert. [[project-l14-weighted-occupancy-dead]]
- **D step 2 blueprint hint** — blueprint A 路径死, master inherent 难解非 hint failure. [[project-d-step2-hint-landed]] superseded

**数学根据失败的层**:
- v8/v10: paradigm 数学 sound 但**前提错估** — v8 关注 build wall 没量 solve quality; v10 假定 blueprint 含 41 mandatory 但实际缺. [[gpt-error-types-taxonomy]] 区分: 算法错估 vs 前提错估 vs 数学能力上限.
- L14: weighted occupancy LP=1.000 是**数学能力上限** — interior anchor 几何 inherent 不可 cert. L14 修不了, 是 paradigm 类不够强.

**教训**: paradigm 实施前必 verify 前提 (data 真满足 hidden assumption 吗?). GPT review 给方案带 hidden assumption 是常态, audit armor 要明确要求 reviewer 给出"该方案需 data 满足什么"清单. [[gpt-review-prompt-armor]] 来源.

### 4.7 Solver 替换 paradigm — HiGHS / LP-MIP 全死

**数学 attempt**: 换 OR-Tools CP-SAT 为 HiGHS / Gurobi / 其他 LP-MIP solver, 期待 RAM/wall 下降.

**lever**:
- **HiGHS rewrite blocker** — PoC 42 GB > OR-Tools 30 GB (Phase 3B repair5). LP-MIP 对 dense linear constraint 不适合. [[project-highs-rewrite-blocker]]
- **L23 rewrite path exhausted** — 所有 viable 重写路径实测/推理后 hard verdict: 单机 48 GB + 准确性必保 + 现 solver, 决定性收益物理不可达. [[project-rewrite-path-exhausted]]

**数学根据失败的层**:
- **Root cause 4** (Class D): single-machine RAM 不可扩. solver 之间差异 < 单机 cap 限制.
- LP-MIP 对项目这类 dense + indicator + cross-product constraint 不适合 — propagation cost CP-SAT 实测最优.

**教训**: solver 不是瓶颈. paradigm 是. **不能再 propose solver 替换**.

### 4.8 共同 root cause (4 axis 从 27 lever 抽)

paradigm_death_timeline §2 已整理. 重列以方便 reference:

**Root cause 1 — Pose-bool master 表达力 limits**
- B1 pose-bool master 280K pose vars × 8 ports/pose = 2.24M OnlyEnforceIf
- master 不知 port direction / pole selection / belt routing
- 任何 master OPTIMAL 都让 sub-problem oracle 拒绝
- master 端 cut 学习不到 binding port_active / routing path / power coverage 关联
- **6 paradigm 撞同墙**: Path 12/13/14/17/B1-path1/B1-path2

**Root cause 2 — 96% utilization 几何死结**
- valley4_protocol_core 70×70 grid + 266 mandatory facility ≈ 4800 cells / 4900 total → ≈98% utilization (4800/4900)
- boundary_storage_port × perimeter trap: 46 pose × 3 cells = 138 cells 必 100% 铺满 left+bottom 138 cells
- 任何 ghost 切 left/bottom 都触发 Hall infeasibility
- cand C 160/266 全 INFEASIBLE 是这一层的下界

**Root cause 3 — Cell-front pattern 已 break symmetry**
- per-instance 几何 high-resolution 已让 sub-pose 等价性消失
- LIC m1=2 (cell-front 近 deterministic pose, mean=1.74)
- Benders symmetry m5=1.0 (orbit 全 trivial)
- Cut lift / symmetry 无 free lunch
- **PROJECT_LOCK §3A 禁跨 instance lifting** 是这一层结论

**Root cause 4 — Single-machine RAM 不可扩**
- 48 GB RAM + 现 solver 下, augmented master / GOC-C2 / PGW-UB 等 RAM scale 全撞 25-32 GB peak (Pre2 cap 12 GB) / 单机 48 GB 上界
- L23 audit 已确认重写路径全穷尽
- 硬件方向被用户排除 (1 主机 + 1 远程 WAN 延迟 ≥ 100ms)

### 4.9 cut framework paradigm 为啥选

把 27 lever 4 root cause 翻译成"paradigm 必须满足"清单:

| Root cause | Paradigm 要求 |
|---|---|
| 1. pose-bool master 表达力 limits | 不重写 master; 在 master 外累积知识 |
| 2. 96% utilization 几何死结 | cut 必表达几何 INFEASIBLE (F1 capacity / F6 Hall) 跟物流 INFEASIBLE (F2 cutset / F4 reach) |
| 3. cell-front break symmetry | cut 限 within-instance scope, 不跨 instance lift |
| 4. RAM 不可扩 | cut 累积 + replay, 不重新 build master; sub-problem 独立 oracle 不挤 master scale |

**cut framework B Design v2 是这 4 个约束唯一满足的 paradigm** (除非 paradigm shift, 但 set-packing / IHS / LIC 系列已证 paradigm shift 全死). 这是项目数学上**不得不**走的路, 不是"试着搞搞看".

### 4.10 5 unsolved issue cut framework 要处理 (timeline §3)

cut framework 不解上面 4 root cause, 但**explicit 处理**衍生的 5 issue:

| Issue | 来源 | cut framework 应对 |
|---|---|---|
| 1. 96% utilization 几何死结 | Root cause 2 | F1 region_capacity + F6 shape_packing_hall |
| 2. Boundary × perimeter 容量 (138 cells 100% saturation) | v14 review GPT pro catch | F1 left_baseline / bottom_baseline / boundary union region |
| 3. Manufacturing cluster trap (132 个最大类) | Class C insight | F5 pattern_nogood + F3 port_exposure (但 Day 16c-2 评估**不足**, Day 18-21 需 dedicated solution) |
| 4. Routing 反馈翻译成强 cut | Class A insight | F2 cutset + F4 component_reach, **不**翻译成 pose-level no-good |
| 5. m10 sound 性跨 scale 维持 | cand C ramp insight | Validator 每 family 独立重算 cert (adversarial soundness, §2.6) |

Issue 3 (manufacturing cluster trap) 是当前 cut framework 最弱点 — F5 pattern_nogood 退化成 full no-good 风险, 132! permutation 撞墙. Phase 1.2 P1.2B-F5 实施 + Day 18-21 dedicated solution (orbit-aware pattern lift) 是 open Q (§5.3).

---


## 4. paradigm 决策 (overview, 详 MATHEMATICAL_FOUNDATIONS.md §4 + paradigm_death_timeline.md)

**SoT 政策**: 死路 paradigm baseline 详 `MATHEMATICAL_FOUNDATIONS.md` §4 (按数学根据 attempt 分类) + `paradigm_death_timeline.md` (按时间 + 死因 axis 分类). plan doc 本段只给 implementer "为啥选 cut framework" 决定性 summary + 实施层衔接.

### 4.1 paradigm 选择 summary

27 lever 死路实测穷尽 7 类 attempt, 全死 (math §4.1-§4.7 + paradigm_death_timeline §1):

| Attempt | 代表 lever | 数学根据失败 |
|---|---|---|
| 完整 master 重写 | B1 pose-bool / augmented master / GOC-C2 / PGW-UB / HiGHS | pose-bool master 表达力 fundamental 限制 (Root cause 1) |
| Sub-problem cut | PCR-CUT / SAC-Hull / RAB-SEP / D2 / B1 lazy demand / L16 lazy power | over-restrictive 或不收敛, multi-anchor 0/8 (Root cause 1+2) |
| Cert lifting | Path 18 LIC / Lever 26 Benders symmetry | cell-front pattern 已 break symmetry (Root cause 3) |
| Column generation | cand C Phase 0+1 GO, Phase 2 160/266 INFEASIBLE | 96% utilization 几何死结 (Root cause 2) |
| Set-packing / IHS | L15 / Lever 25 IHS | 攻错层 / IHS core 全 trivial |
| Witness / weighted | v8 / v10 / L14 / D step 2 blueprint | 前提错估 或 数学能力上限 |
| Solver 替换 | HiGHS / Gurobi propose | single-machine RAM 不可扩 (Root cause 4) |

详死法 + cheap gate metric 各 lever cite math §4.1-§4.7. paradigm_death_timeline §2 列 4 共同 root cause.

### 4.2 cut framework 是 4 root cause 唯一满足的 paradigm

4 个约束 (从 4 root cause 翻译):
- 不重写 master (Root cause 1)
- 表达几何 + 物流 INFEASIBLE 各类 (Root cause 2)
- 限 within-instance scope, 不跨 instance lift (Root cause 3)
- cut 累积 + replay, 不挤 master scale (Root cause 4)

详 math §4.9.

### 4.3 跟 Phase 3B 衔接

Phase 3B repair5 (见 `docs/phase3b_repair5_acceleration_tuning_ai_plan.md`, 20260429 包) master oracle 30 GB → 47 GB 是 cut framework 跑前提 — master 跑不起来 cut 没意义.

Phase 1.3 P1.3B 真集成时 cut framework wire 到 benders_loop 内 (`src/search/benders_loop.py`), env flag (§19) 切新框架. 不动 Phase 3A outer_search 跟 Phase 3B master/binding/routing/flow 架构.

---

