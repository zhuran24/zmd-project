# 05 — 待定 mathematical questions (open problems)

> **问题清单边界**：本文件混合历史问题与未来 P1.3 设计项。当前状态必须回查
> `06_current_status.md`；`soundness_gap_roadmap.md` 只保存截至 2026-07-11 的
> P1.2 历史快照。旧 `P1.3B` 人类名称统一解释为 P1.3。


本节列**当前没答案**的数学问题. 按级别标:

- **P0 (critical)** — 数学层 paradigm 决定性问题, 不解会阻 P1.3/P1.5 实现推进；非 P1.2 owner-close blocker
- **P1 (defer-Phase)** — 实施时 verify, 不阻 paradigm 但阻具体 family
- **P2 (informational)** — 知识层问题, 答了好但不阻
- **P3 (defer-future)** — Phase 2+ 才碰

各 Q 必标: 数学层 vs 工程层 / 难度估 / dependency / 触发决策的 trigger / 当前最佳 understanding.

### 5.1 框架 completeness — sound but how complete?

#### Q1 — 9 family 是否 cover 所有 INFEASIBLE 类? **P0**

**问题**: cut framework 当前 8 个 active family (F1-F7+F9；F8 retired) 数学上是否**充分** — 即任何 master partial assignment 若 INFEASIBLE, 必存在 active F1-F7+F9 之一可产 sound cut 排除该 assignment?

**当前 understanding**:
- active F1-F7+F9 各自针对一类 INFEASIBLE pattern, 数学根据独立 ([cite spec 01-09])
- 跨 family 覆盖度由 timeline §3 5 issue 推 (但 timeline 只列 5 issue, 没数学完整性证明)
- Issue 3 (manufacturing cluster trap, 132 instance) 现 spec **不足** — F5 pattern_nogood literal 全 facility full assignment no-good 退化, 132! permutation 撞墙. paradigm_death_timeline §3 自承

**verification trigger**:
- Phase 1.5+ 真生产 168h trial 后, 若仍有 INFEASIBLE candidate 不被任一 active family 拦 → 暗示 cover 不完整
- 长跑 telemetry 看 cut_count_by_family 分布 (§20.2) — 若某类 INFEASIBLE 反复 trigger 但无 cut 拦, 数学上需 F10+

**数学难度**: paradigm-level, 不能简单 verify. 需:
- 形式化"所有 INFEASIBLE 类"的 partition (proof system 层)
- 对每类构造拦截 family 或证明 ⊥

**defer trigger**: Phase 2+ 决策 (当前 Phase 1.2/1.3 实施前不解, 用 Phase 1.5+ telemetry 数据反推)

> **(2026-07-05 更新)** Q1 的定义层已有正式设计稿
> （`docs/research/q1_infeasibility_class_taxonomy_design_v1.md`，v2 = 双会话
> 对抗审回收版）：建议拆为 **Q1a_complete_candidate_W**（完整候选 +
> replay-verified 观测域上的弱完备——F5 兜底使之近乎结构性成立，数学核已在
> `formal/` 机器证明）与 **Q1p**（partial assignment 原量词域，仍 open）；
> 强进展性拆三层（S_i-progress = 逐类定理义务、S_residual = telemetry、
> S_global = 实验命题）。**拆分与本条状态改写待 owner 裁定**——见
> [00_master_roadmap](00_master_roadmap.md) §4 拍板台账。

**最坏情况**: 9 family 不充分 → 加 F10+ (LOCK §3A 9 family frozen 的约束需重审, paradigm shift 入口)

#### Q2 — cut framework convergence guarantee? **P1**

**问题**: 给定足够 oracle compute, cut framework 累积 cut 后, 是否 finite step 内 master 收敛 OPTIMAL/INFEASIBLE?

**当前 understanding**:
- LBBD 经典结论: nogood cut 数有限 (有限 master assignment 空间), 每次 INFEASIBLE 必排除 ≥1 assignment → finite step 内 done
- 但项目空间 8×10⁷ raw assignment + cut framework lift (within-instance) 让 cut 表达力 enlarge — 单 cut 排除多 assignment, finite step 估算更紧 但具体未证
- 实际 168h budget 内不需 finite proof, "168h 内收敛比 baseline 多 N candidate" 即工程胜利

**数学难度**: theoretical, 不阻实施

**defer trigger**: Phase 1.5+ telemetry 数据足够后做经验估算 (cut 累积速率 + master.solve wall 关系)

#### Q3 — sound cut 跟 over-prune 的边界 **P0**

**问题**: cut framework 验 sound (`validator(cert, state) = OK ⇒ cut excludes only ¬feasible`), 但 over-prune (验 sound 同时排除 feasible) 怎么定义?

**当前 understanding**:
- adversarial soundness §2.6 验 cert 内 sound + cert↔literals/真数据/state/不变量 5 层
- 但 over-prune 是另一回事 — cert 可能 sound (cut.body 排除的 assignment 在该 cert 下 ¬feasible), 但 cert 跟 cut.scope 关系若错 → cut 在更广 scope 误剪 feasible (L14 weighted occupancy / v3 anchor slicing 死法)
- Step O F1 GHOST_AGNOSTIC ghost ∩ R == ∅ 检查就是防 over-prune (cap_R 跨 ghost 不变要求)

**数学难度**: 需 formalize scope 的 "cut sound 范围" 跟 "cut 适用范围" 是同一回事

**verification trigger**:
- 任 family 设计时必声明: cut 对 scope 内任意 state 是否仍 sound?
- Phase 1.2 F5-F9 实施时同步落

**defer trigger**: 每 family 实施时 case-by-case verify (不集中决)

### 5.2 cut 复用边界 — lifting 数学根据

#### Q4 — within-instance lifting sound 性边界 **P1**

**问题**: PCR-CUT Phase 3 signature lifting 已实施 within-instance lift ([cite lifecycle §9 复用 from cand C Phase 2 v3]). 跟 multiset eval slot anonymity 关系是?

**当前 understanding**:
- multiset eval (§2.5): slot 集 modulo S_n action 等价类
- PCR-CUT signature lifting: 同 instance 内不同 pose 若几何 signature 等价, cut 可 lift
- 二者是同一回事 (S_n 自然 act on signature 等价类) 还是独立?

**数学难度**: cheap (~1 day cheap gate verify 形式化二者等价 / 区分)

**defer trigger**: PCR-CUT Phase 1.5+ 整合时定 — multi-anchor 部分实施 (Phase 5 verdict 死) 跟 within-instance lift 关系

#### Q5 — cross-instance lifting 数学边界 **P0 frozen**

**问题**: 跨 instance lifting (e.g. 两个 boundary_storage_port instance 共享 cut) 数学 sound 性?

**当前 understanding**:
- Path 18 LIC (layout-invariant cert) verdict 死, m1=2 远低 ≥100 target — cell-front pattern 已 break instance 等价
- Benders symmetry m5=1.0 orbit 全 trivial
- PROJECT_LOCK §3A 禁跨 instance lifting 是这一层结论

**verification trigger**: **已 frozen** (LOCK §3A 锁), 不解. 任 paradigm propose 跨 instance lift 必 reject

**数学难度**: ❌ 死路 baseline, 不再 propose

#### Q6 — 跨 candidate / 跨 ghost lifting sound 性 **P1**

**问题**: 当前 cut.scope 含 ghost_rect_id (跨 ghost 不 lift 除非 GHOST_AGNOSTIC); cut 跨 candidate 怎么处理?

**当前 understanding**:
- source_digest 锁 data version → 跨 session reuse cut (替代 candidate 跨 session)
- 单 session 内多 candidate, cut 跨 candidate sound 性是: cut.scope.ghost_rect_id 跟 candidate ghost 一致 → 可 reuse; 不一致 → quarantine 或 replay
- GHOST_AGNOSTIC cut (e.g. F1 在 `ghost ∩ R == ∅`) 跨 candidate ghost 可 reuse, 这是数学根据 (cert 不含 ghost 变量)

**数学难度**: 已 Step O 部分解 (F1 ghost ∩ R 检查), 其他 family GHOST_AGNOSTIC 政策 Phase 1.2 实施时 align

**defer trigger**: Phase 1.2 F5-F9 实施时 per-family 定 GHOST_AGNOSTIC 政策

### 5.3 各 family 具体 open questions

#### F1 — LP dual Farkas 自动触发? **P2**

**问题**: F1 region_capacity 是 LP relax valid inequality, 可通过 Farkas dual ray identify ([cite spec 01 §1c]). 实施 Farkas 自动触发是否值得?

**当前 understanding**:
- 当前仓库没有 `farkas_certificate.py`，也没有可发布的 dual-ray/Farkas 证书链
- 当前 F1 oracle 是组合枚举 region，不调用 Farkas；F1/F5/F6/F7 direct Step-8 已接入 unsafe/default-off bridge，其余 active family 仍 fail-closed，整条链尚未 certified promotion
- Farkas 自动触发 → oracle 不需手写 region 列表, 但 LP relax solve 也要 cost

**defer trigger**: 未来 cut-family 集成时，先定义证书格式、独立 verifier 和 replay 义务，再评估 dual-ray 路径是否值得实现

#### F1 — interior_rect 枚举策略 **P1**

**问题**: F1 oracle 4 类 region 含 `interior_rect` (任意轴向 rectangle). 70×70 grid 上 rectangle 数 6.4M, oracle 不能枚举全部. 启发式策略?

**当前 understanding**:
- 当前 oracle 实施 4 类 region 但 `interior_rect` 没明确启发式 (spec 没定)
- 可能策略: facility-centered rect / boundary-adjacent rect / Farkas-driven (Q1 same)

**defer trigger**: F1 production trial 时按 telemetry 看 region 类型分布定

#### F2 — patch_routing_core 复用 sound 性 **P1**

**问题**: F2 oracle 是否复用 PCR-CUT (Path 14) 的 patch belt CP-SAT? 单 cut 数学 sound 但 multi-anchor 复用 (Phase 5 verdict 死 0/8 CERTIFIED) 是否影响 F2?

**当前 understanding**:
- PCR-CUT 死法是**multi-anchor cut 累积不收敛** — pose-bool master 不知 sub-problem 关联 (Root cause 1)
- F2 用 LBBD 标准 nogood lift (not multi-anchor cut), 数学根据是 Menger min-cut
- 单 cut 生成可复用 PCR-CUT helper, 不直接复用 multi-anchor convergence 设计

**verification trigger**: Phase 1.5+ F2 oracle 实施时复 verify (PCR-CUT Phase 0-4 GO 单 cut 数学层 sound)

#### F2 — max-flow LP dual algebraic witness **P2**

**问题**: Menger min-cut max-flow theorem dual 提供 algebraic witness (LP solve 后取 dual ray). F2 oracle 是否实施 LP-based witness verify (cite spec 02)?

**当前 understanding**: cite spec 02 提到 max-flow LP, 但 src 实施未明确

**defer trigger**: Phase 1.5+ §13.4 evaluate

#### F3 — multi-pose port chain (3+ facility 互 block) **P2**

**问题**: F3 当前是 2-literal pattern (两 facility 互 block). 是否扩展到 3+ facility 互 block 链?

**当前 understanding**:
- 数学根据: propositional logic 不限 literal 数, 但 2-literal 比 3+ 紧
- F5 pattern_nogood 是 multi-literal generalization, F3 是 2-literal 特例
- 实施 F3 (Phase 1.1 闭环) 加 multi-pose 是 F3 内扩展还是直接走 F5? 待 F5 实施后决

**defer trigger**: Phase 1.2 P1.2B-F5 (F5) 实施后决 F3 是否扩展

#### F3 — 跟 F5 subsume 关系 **P1**

**问题**: F5 pattern_nogood (multi-literal) 实施后, F3 (2-literal port) 数学上是 F5 特例 — 是否合并 (减 family 数 → 8)?

**当前 understanding**:
- PROJECT_LOCK §3A 9 family frozen
- 但 family 合并不动 LOCK invariant, 是 spec 层简化
- 合并好处: 减 dispatch 复杂; 不合并好处: F3 端口语义清晰, validator 重算更紧

**defer trigger**: Phase 1.2 P1.2B-F5 (F5) 实施后, 看 F5 validator 是否真覆盖 F3 cert↔literals binding 严格性

#### F4 — cell-flow capacity (cell 同时被多 commodity 用)? **P1**

**问题**: F4 当前只 binary connectivity (src reach sink 是/否). 是否引入 cell-flow capacity (cell 同时被多 commodity 用, capacity 上界)?

**当前 understanding**:
- D2 Path 17 试过 (conditional flow conservation), verdict 死 (multi-anchor 0/8)
- F4 走 connectivity 路径不走 flow 路径
- 但有 INFEASIBLE 案例: 2 commodity 共享单 path cell, capacity 1 不够 — F4 当前不拦

**defer trigger**: Phase 1.5+ F4 production trial telemetry 看是否有此类 INFEASIBLE 未拦, 若有则需 F4 扩展或新 family

#### F5 — QuickXplain 超时阈值 **P0**

**问题**: F5 minimize 用 QuickXplain (Junker 2004) 找 minimal unsat core, NP-complete. 实际 instance 上时间预算?

**当前 understanding**:
- L16 deletion-based 已 land helper (paradigm 死但 minimize 算法可复用)
- PCR-CUT QuickXplain helper 已 land (Phase 0-4 GO)
- 项目 instance 上 unsat core 大小未知 (mini PoC 50% reduction, production scale 未测)
- Open question §17.6 (plan doc) cite, defer Phase 1.2 P1.2B-F5 实施时定

**verification trigger**: Phase 1.2 P1.2B-F5 实施时跑 prod data, p95 core size + minimize 时间分布, 定 super-timeout fallback (deletion-only / 不 minimize)

#### F5 — Manufacturing cluster trap (132 instance) 退化 **P0**

**问题**: timeline §3 issue 3 — F5 pattern_nogood literal 全 facility full assignment no-good 退化, 132! permutation 撞墙. Day 18-21 需 dedicated solution (orbit-aware pattern lift).

**当前 understanding**:
- F5 default behavior 是 literal pattern, 132 instance 同 facility group 互相 permute → 132! pattern 数
- 已被识别为**当前 cut framework 最弱点**
- 可能 solution: orbit-aware pattern lift (multiset eval §2.5 自然扩展); 或 F5 + F6/F3 复合 cut; 或 instance-level instance partition

**defer trigger**: Phase 1.2 P1.2B-F5 (F5 实施) 必同步实施 orbit-aware pattern lift, 否则 P1.2B-F5 incomplete

#### F6 — Hall theorem interval graph 反例边界 **P1**

**问题**: F6 用 Hall's marriage theorem on interval graph (boundary interval cover). 各 length-k 反例覆盖率?

**当前 understanding**:
- spec 06 给一个反例 (Gemini 反例 B, length-3, ghost 切 [1-4]+[6-10])
- 其他 length-k 反例: length=2 / 4 / 5 各类 ghost 切, 反例分布未列
- production 几何上常见的 length-k facility: 2x1 / 3x1 / 3x3 / 5x5 / 6x4

**defer trigger**: Phase 1.2 P1.2B-F6 (F6 实施) 时枚举 length-k × ghost-cut 组合, 给反例 fixture 集

#### F6 — 2D interval cover (interior facility) **P2**

**问题**: F6 当前只 boundary 1D interval. 2D interior facility group (e.g. 3x3 mfg) 是否需 Hall 2D version?

**当前 understanding**:
- F1 region_capacity 已 cover interior facility count
- F6 2D 是 F1 stronger refinement (类比 boundary F1 → F6)
- 但 2D Hall 复杂度高, NP-complete (matching in bipartite graph polynomial, 但 2D 几何嵌入有约束)

**defer trigger**: Phase 1.5+ F6 真生产 trial 看 boundary 1D 是否足够; 若 interior 仍 over-demand 走 F1 不走 F6 2D

#### F7 — LP relax ln(n) approximation 实际紧度 **P1**

**问题**: F7 set cover NP-hard, LP relax + greedy 有 ln(n) approximation (Chvátal 1979). 项目实际 instance 上 approximation factor 多少?

**当前 understanding**:
- F7 oracle 是 set cover **必要条件**检查 (power_cover_domain ∅) 不解 set cover
- 但 Phase 1.5+ refine (power_cover_domain 非空但 hitting set unsat) 需解 set cover, 走 LP relax 还是 exact?
- 项目 instance n ~ 数百 (power_pole 候选数), ln(n) ~ 5-6 倍 — exact 时间 vs LP 速度 tradeoff

**defer trigger**: Phase 1.2 P1.2B-F7 (F7 实施) 决 LP 还是 exact, 用 Phase 1.5+ telemetry 验

#### F7 — 跟 master.solve power_coverage constraint 冲突 **P1**

**问题**: F7 是 cut layer 检查 power cover; master.solve 已有 power_coverage constraint (`src/models/master_model.py`). 二者关系?

**当前 understanding**:
- master power_coverage 是 hard constraint, F7 是 cut layer 检查 (sound deduction)
- 数学上 F7 sound = master 在该 cut 后必 INFEASIBLE
- 但实施上: F7 cut 加进 master 后是 redundant (master 已经会拒) 还是 amplify (master propagation 提前 cut)?

**defer trigger**: 后续 P1.3 propagator 集成时验

#### F8 — Liang-Barsky 退化 case **P1**

> **【已随 F8 退役关闭，2026-07-08】** owner 游戏规则确认电杆不需连网
> （协议核心自动无线连接），F8 整族前提为假、retired-false-premise——本问题
> 与下一个「power network 独立性」问题均不再有对象。见卡
> `p1-3-m2-coverage-stencil-ruling` 与 02 号 §3.8 退役注。

**问题**: F8 用 Liang-Barsky line-segment AABB intersection. 退化 case (零长度 / 共线 / 正交) 数学边界?

**当前 understanding**:
- Liang-Barsky 标准实施处理一般 case, 退化 case (segment 长度 0, segment 跟 AABB edge 共线, segment 正交于 AABB) 需 careful
- spec 08 v1.1 Gemini round 14 finding 改严格 line-segment AABB intersection (不是 cell-level 离散 block)
- 实施时若退化 case 处理不对, F8 cut 可能 unsound 或 over-prune

**verification trigger**: Phase 1.2 P1.2B-F8 实施时加退化 fixture (零长度 + 共线 + 正交)

#### F8 — power network 跟 belt routing 独立性 **P2**

**问题**: F8 假定 power network (pole 连接) 跟 belt routing (commodity flow) 独立. 是否真独立?

**当前 understanding**:
- 数学上独立: pole 不占 belt cell (pole 几何小 vs belt 用 free cell)
- 但实际 instance 几何上 pole + belt 共占 free_cells → 互相 block 可能
- 若不独立, F8 cut 跟 F4 cut 有交叉, 数学上需复合 family

**defer trigger**: Phase 1.5+ telemetry 看 pole / belt 共占冲突频率

#### F9 — envelope baseline 紧度 **P0**

**问题**: F9 density_envelope 用 `cap/area` ratio 作 envelope. baseline=1.0 (trivial, 每 cell 至多 1 facility) 是否 trivial 永不可 cert? L14 weighted occupancy verdict 死的教训说明 trivial bound 不够.

**当前 understanding**:
- L14 死法: interior anchor LP=1.000 exact 永远不可 cert
- F9 必须用真重算的 envelope (不是 LP relax 1.000), 即 oracle 真计算 region 内 facility 数 + cell_owner 已占
- spec 09 v1.0 表态: envelope ≠ trivial baseline, 必 stronger bound

**verification trigger**: Phase 1.2 P1.2B-F9 实施时, fixture 必含 envelope < trivial 的反例 (否则 F9 退化 F1)

#### F9 — 跟 F1 数学独立性 **P1**

**问题**: F9 cap 严格 ≥ F1 cap? 即 F9 是 F1 弱化 (允许更弱 envelope) 还是 F1 强化 (envelope 更紧)?

**当前 understanding**:
- 02 §3.9 权威定调: F9 与 F1 是**互补 family**（F9 area-based vs F1 cell-based），**非** F1 的 scope 扩展（早先"scope 扩展"措辞已纠，见 02 §3.9 / §3.10）
- 但若 F9 envelope < F1 cap (e.g. cell_owner 已占), F9 反而更紧
- 数学边界: F9.cap = F1.cap - cell_owner_in_R × cells_per_pose? 还是其他公式?

**defer trigger**: Phase 1.2 P1.2B-F9 spec 写时数学 formula 明确

### 5.4 LBBD 集成的 open questions

#### Q7 — attach point 选择 **P0**

**问题**: cut framework Phase 1.3 接 benders_loop 时, cut 在哪 attach master? 当前 PCR-CUT (Path 14) 只在 front_blocked routing precheck branch attach. 其他受 theorem 接纳的 INFEASIBLE 来源（binding / routing / power / independently reverified whole-layout；flow diagnostic 不在其列） wire 进 cut framework 怎么 sound?

**当前 understanding**:
- LBBD 经典: 每 sub-problem INFEASIBLE 出 nogood → master 加 lazy
- cut framework 是 nogood 的累积层, 每 sub-problem 触发 attach 点不同 (binding INFEASIBLE 触发 F3/F5/F7; routing INFEASIBLE 触发 F2/F4; power INFEASIBLE 触发 F7/F8)
- 每 attach 点必 sound 确认 (cert ↔ sub-problem reject 数据)

**defer trigger**: 后续 P1.3 propagator 集成时设计 (cite plan §12.1)

#### Q8 — lazy attach vs eager attach **P1**

**问题**: cut 在 master 是 lazy constraint (master.AddLazyConstraint) 还是 eager constraint (master.AddLinear 立即)?

**当前 understanding**:
- CP-SAT 支持 AddLinear eager + AddBoolOr lazy 但 lazy 用法限制 (callback 方式)
- eager attach: cut 立即影响 propagation, master 立即缩 search; lazy attach: cut 仅在 master solve 时触发, 不影响 propagation
- 项目 cut 数预期 ~thousands per candidate, eager 可能撞 propagation cost; lazy 可能 cut 不触发 (master 没 hit cut.scope)

**defer trigger**: 后续 P1.3 实施时 ab test eager vs lazy

#### Q9 — master OPTIMAL vs INFEASIBLE 触发路径 **P1**

**问题**: 当前 cut 只在 master OPTIMAL + sub-problem reject 触发 (PCR-CUT Phase 4 hook). 其他路径 (master UNPROVEN time-out / master 直接 INFEASIBLE) 是否触发 cut?

**当前 understanding**:
- master OPTIMAL: sub-problem reject 是 classic LBBD nogood path
- master UNPROVEN time-out: 没 best 答案, 不能产 sound cut (因为没确认 INFEASIBLE)
- master INFEASIBLE: 已经 ⊥, cut 没必要 (但 cut framework 累积 cut 可减后续 master.solve 时间)

**defer trigger**: 后续 P1.3 实施时设计

#### Q10 — cp_sat propagator vs master.AddLinear ✅ **VERDICT (2026-05-23)**

**问题**: cut 用 CP-SAT propagator (custom propagation) 还是 master.AddLinear?

**Verdict** (Gemini math review meta-audit 2026-05-23):
- ❌ `model.AddLazyConstraint(...)` **不可用** — OR-Tools 9.15 Python `cp_model.CpModel()` 没此 API
- ❌ Python callback heavy separation — wrong place for independent mathematical proof reconstruction
- ✅ **走 LBBD 外循环** (跟现 benders_loop 一致): `master solve → independent subproblem verification → generate cut object → validate/replay/scope-check → translate active cuts into normal CP-SAT constraints → solve again`
- ✅ 用普通 `Add` / `AddLinearConstraint` / `AddBoolOr` / `OnlyEnforceIf` / `AddAssumption`
- ✅ Ghost-bound cut: `constraint.OnlyEnforceIf(ghost_lit)` 或 per-ghost rebuild model

**Family translation** (CP-SAT integration notes):
| Family | CP-SAT shape |
|---|---|
| F3/F5/F7 literal | `sum(present_lits) <= len(present_lits)-1` |
| F9 area envelope | `sum(overlap_area[p,W] * x[g,p]) <= max_allowed_area` |
| F6 shape packing | `sum(x[g,p] for p in pose_set) <= packing_upper_bound` |
| F2 capacity | `sum(crossing_demand_lits) <= cut_capacity`, 不行 fallback F5 |
| F4 reachability | 优先转 F2 / F5; 纯 BFS cut 无线性 separator cert 则 fallback |

**剩余 sub-question (P1.3A spike)**: solve-rebuild vs C++ propagator hook vs hard-constraint rebuild 哪条 wall-clock 最优? Phase 1.3 P1.3A spike 验.

cite: `docs/research/p3_b_design_v2_20260521/external_review/gemini_math_review_bundle_20260523/notes/CP_SAT_INTEGRATION_NOTES.md`

### 5.5 schema / data 层 open questions

#### Q11 — commodity registry 级别 (commodity_id vs route_id) **P0**

**问题**: F2 / F4 cert 含 commodity_id (Step M registry require). 但 commodity_id 是流粒度 (e.g. "ore_iron") 还是路径粒度 (e.g. "ore_iron_route_A")?

**当前 understanding**:
- 流粒度: 1 commodity 对应 1 demand pair, 路径 fungible
- 路径粒度: 同 commodity 多路径, 各路径独立 cert
- 流粒度 simpler 但路径粒度精细; F2/F4 cert ↔ data pipeline 接合点决于此

**defer trigger**: Phase 1.5+ §13.1 commodity registry 真接 data pipeline 时决

**数学影响**: 流粒度 cut sound 性证明简单; 路径粒度 cut sound 性需额外 verify (路径独立性)

#### Q12 — ghost_rect tuple vs object schema **P1**

**问题**: 当前 ghost_rect 是 tuple `(x, y, w, h)`. 改 object schema `{x, y, w, h, anchor_id, ...}` 是否更好?

**当前 understanding**:
- tuple: 简单, hashable, serializable
- object: extensible (加 anchor_id / rotation / metadata 不破 backward compat)
- 实际 cut.scope.ghost_rect_id 用 hash(tuple) → 改 object 后 hash 不变 (用 sorted keys)

**defer trigger**: Phase 1.2 §10.4 实施时决 (加非方形 fixture 触发)

#### Q13 — source_digest hash 算法 **CLOSED in Phase 1.1 exit hardening**

**结论**: 使用 sha256；replay 时按当前 `BState` 注入 source 重新计算，不信任外部手写 `source_digest`。

**当前 understanding**:
- 覆盖范围: `canonical_rules`, `candidate_placements`, `mandatory_exact_instances`, `facility_templates`, `generic_io_requirements`, `commodity_routes`
- 不含: telemetry / cache / 临时文件；`__*` runtime cache key 会被排除

**status**: done; Phase 1.2 只需要沿用该约束。

### 5.6 paradigm-level open questions

#### Q14 — 整体框架 completeness 形式 proof **P3**

**问题**: 形式化 proof 9 family 数学上 sound + complete (cover 所有 INFEASIBLE 类)?

**当前 understanding**:
- Soundness: per-family validator 重算 cert 已是 sound 工程证明 (但非形式化 proof system)
- Completeness: §5.1 Q1 open
- 形式化 proof 需 Coq / Lean / Isabelle 工具 — 项目当前不投资

**defer trigger**: Phase 2+ 决策 (paradigm 投资 ≥ 数月)

> **(2026-07-05 更新)** Q14 已由 owner 授权提前"头启动"（P3.0 双轴）——
> **"项目当前不投资"口径作废**：轴 A（范式数学的 Lean 机器检查）已落 main
> `formal/` **68 条定理**（零 sorry、公理审计仅经典三公理、两轮独立外审
> 回收闭环）；轴 B（证书侧 proof logging：PB/VeriPB + 经形式化验证的检查器）
> 七阶段路线图定型、第一落点 binding PB sidecar 待开工。但注意：
> `16_workflow_review.md` §6.4 政策条款（数学 sound 用工程 verify、formal/
> **不进认证 TCB**、不改任何 gate）**原样有效**——头启动是前瞻投资，
> 不是信任底座切换；本条 P3 分级是否改判待 owner 裁定。
> 总图见 [00_master_roadmap](00_master_roadmap.md) §2a/§2b。

#### Q15 — 跨 base transfer 可行性 **P3**

**问题**: valley4_protocol_core cut framework 能 transfer 到其他 base (`valley4_infra_outpost` / `wuling_protocol_core` 等)?

**当前 understanding**:
- 各 base 几何 (grid size / mandatory instance / canonical_rules) 不同
- cut framework 数学 paradigm (LBBD + 9 family) 应 transfer, 但 oracle 实施 (region 枚举策略 / interval cover / power network 拓扑) 跟 base 几何耦合
- PROJECT_LOCK active_scope `valley4_protocol_core` only, 其他 base future_scope

**defer trigger**: future_scope, Phase 2+

#### Q16 — 多 base 联合 optimization **P3**

**问题**: 多 base 同时 optimize (e.g. valley4_protocol_core + valley4_infra_outpost 共用 commodity flow) 数学定义?

**当前 understanding**:
- 当前 PROJECT_LOCK active_scope 单 base, 多 base 联合是 future_scope
- 数学上需扩展 objective (max_lex 跨 base?) + 跨 base commodity 流定义

**defer trigger**: future_scope, Phase 3+

### 5.7 工程层 (数学 adjacent) open questions

#### Q17 — cut redundancy 跟 propagation cost tradeoff **P1**

**问题**: 加越多 cut, master.solve propagation 越慢 (CP-SAT BCP cost). Sound vs cost 怎么 tradeoff?

**当前 understanding**:
- 数学上 cut 越多越好 (排除更多 ¬feasible space)
- 工程上 propagation cost ~ cut 数 × literal 数, 项目 thousands cut 可能 master.solve wall +20%
- Phase 1.3 telemetry §20.2 看 cut_redundancy_rate + step_7_latency 决

**defer trigger**: 后续 P1.3 实施 + 24h shadow trial 后定 cut 上限策略 (LRU evict / cut score threshold)

#### Q18 — cut quality metric 形式定义 **P2**

**问题**: 什么 metric 衡量"好 cut"? active_rate / pruning_contribution / 还是其他?

**当前 understanding**:
- §20.2 列了 4 类 metric (cardinality / quality / latency / safety)
- 但"好 cut"定义模糊 — sound 是必要不充分; "cut 排除多 assignment" 直接量化困难
- 可能 proxy: cut.active_after_replay rate / cut.attached_count / cut.contribution_to_master_INFEASIBLE

**defer trigger**: Phase 1.3 telemetry 落地后用真数据归纳

#### Q19 — registry schema 跟 cut framework decoupling **P1**

**问题**: commodity registry (Q11) 跟 BState schema 强耦合. 改 registry schema 是否 break cut framework?

**当前 understanding**:
- 当前 Step M Stafe.commodity_demands + commodity_routes registry 是 BState field
- 若 registry 改 schema (e.g. 加 priority / 加 fungibility flag), cut framework 是否需同步改?
- 数学上 cut 不依赖 registry detail (只用 commodity_id 标识), 但 validator 实施依赖 schema

**defer trigger**: Phase 1.5+ §13.1 真接 data pipeline 时决

### 5.8 Issue 3 manufacturing cluster trap 单独深入 (timeline §3 自承不足)

**timeline 自承**: Issue 3 (manufacturing_3x3 132 instance) 现 spec **不足** — F5 pattern_nogood literal 全 facility full assignment no-good 退化, 132! permutation 撞墙. v14 review Pattern no-good >50% stop-ship signal 矛盾. Day 18-21 需 dedicated solution.

**已 propose solution (P0)**:

#### A. Orbit-aware pattern lift (优先)
- multiset eval §2.5 自然扩展: 132 instance 的 S_132 permutation orbit 等价类
- 单 cut 排除整 orbit, 不是 132! single literal
- 数学根据: slot anonymity invariant 已在 §2.5 verify, 扩展到 132 instance 是 cheap (lifting within-instance)
- **难度**: 中等 — orbit 计算 cheap, 但 cut.scope.orbit_id 加新字段 (state_machine 扩展)

#### B. F5 + F6/F3 复合 cut
- F5 single literal + F6 Hall theorem refinement (interval cover) + F3 port_exposure 跨 instance
- 复合 cut 单 cut 排除更多, 但 cert 复杂度高
- **难度**: 高 — 跨 family 复合 cert 是新 paradigm, 需 spec-level 决

#### C. Instance-level instance partition
- 132 instance partition into K group (e.g. 10 group 各 13 instance), 各 group 独立 cut
- 减 permutation 撞墙到 13! × 10 group (~10⁹ vs 132!)
- **难度**: 低 — 不动 cut framework, 加 instance partition layer; 但 partition 启发式需设计

**当前推荐**: A (orbit-aware pattern lift) 是数学上 cleanest. 实施 trigger: Phase 1.2 P1.2B-F5 (F5 实施) 必同步 land A, 否则 P1.2B-F5 incomplete.

**verification**: Phase 1.5+ trial 看 132 instance manufacturing_3x3 group F5 cut 数量是否撞墙 (>10⁵ cut → 撞; <10³ cut → A 工作).

---

## 5.9 Open Q summary 表

跨 5.1-5.8 列, 实施 priority order:

| Q | 主题 | 级别 | defer Phase | 数学/工程 |
|---|---|---|---|---|
| Q1 | 9 family completeness | P0 | Phase 2+ telemetry 反推 | 数学 |
| Q2 | convergence guarantee | P1 | Phase 1.5+ 经验估 | 数学 |
| Q3 | sound vs over-prune 边界 | P0 | per-family case-by-case | 数学 |
| Q4 | within-instance lifting sound | P1 | PCR-CUT 整合时 | 数学 |
| Q5 | cross-instance lifting (frozen) | P0 死 | LOCK §3A | 数学 |
| Q6 | 跨 candidate/ghost lifting | P1 | Phase 1.2 per-family | 数学 |
| F1-LP | LP dual Farkas 自动触发 | P2 | Phase 1.3 | 工程 |
| F1-int | interior_rect 启发式 | P1 | Phase 1.5+ telemetry | 工程 |
| F2-PCR | patch core 复用 sound | P1 | Phase 1.5+ F2 oracle | 数学 |
| F2-LP | max-flow LP dual | P2 | Phase 1.5+ §13.4 | 工程 |
| F3-multi | multi-pose chain | P2 | F5 实施后决 | 数学 |
| F3-F5 | 跟 F5 subsume | P1 | F5 实施后决 | 工程 |
| F4-cap | cell-flow capacity | P1 | Phase 1.5+ trial | 数学 |
| F5-QX | QuickXplain 时间预算 | P0 | Phase 1.2 P1.2B-F5 | 工程 |
| F5-mfg | 132! permutation 撞墙 | **P0 critical** | **Phase 1.2 P1.2B-F5 必同步** | 数学 |
| F6-len | Hall length-k 反例覆盖 | P1 | Phase 1.2 P1.2B-F6 | 数学 |
| F6-2D | 2D Hall (interior) | P2 | Phase 1.5+ trial 看必要 | 数学 |
| F7-LP | LP relax ln(n) factor | P1 | Phase 1.2 P1.2B-F7 | 工程 |
| F7-master | 跟 master.power_coverage | P1 | Phase 1.3 propagator | 工程 |
| F8-deg | ~~Liang-Barsky 退化 case~~ | ~~P1~~ 已关闭 | F8 整族退役（前提为假，2026-07-08） | 数学 |
| F8-ind | ~~power/belt 独立性~~ | ~~P2~~ 已关闭 | 同上（见 §F8 退役注） | 数学 |
| F9-base | envelope baseline 紧度 | P0 | Phase 1.2 P1.2B-F9 | 数学 |
| F9-F1 | 跟 F1 数学独立性 | P1 | Phase 1.2 P1.2B-F9 spec | 数学 |
| Q7 | attach point 选择 | P0 | 后续 P1.3 | 工程 |
| Q8 | lazy vs eager attach | P1 | 后续 P1.3 ab test | 工程 |
| Q9 | OPTIMAL vs INFEASIBLE 路径 | P1 | 后续 P1.3 | 工程 |
| Q10 | propagator vs AddLinear | P0 | Phase 1.3 §12.4 | 工程 |
| Q11 | commodity_id vs route_id | P0 | Phase 1.5+ §13.1 | 数学+工程 |
| Q12 | ghost_rect tuple vs object | P1 | Phase 1.2 §10.4 | 工程 |
| Q13 | source_digest hash 算法 | CLOSED | Phase 1.1 exit hardening | 工程 |
| Q14 | 形式 proof completeness | P3 | Phase 2+ | 数学 |
| Q15 | 跨 base transfer | P3 | future_scope | 数学+工程 |
| Q16 | 多 base 联合 opt | P3 | future_scope | 数学 |
| Q17 | cut redundancy tradeoff | P1 | Phase 1.3 telemetry | 工程 |
| Q18 | cut quality metric | P2 | Phase 1.3 telemetry | 工程 |
| Q19 | registry schema decoupling | P1 | Phase 1.5+ | 工程 |

**当前 P0 critical (不解阻 P1.3/P1.5 实现推进；非 P1.2 close blocker)**:
- Q1 (9 family completeness — 用 telemetry 反推)
- Q3 (sound vs over-prune 边界 — per-family verify)
- F5-mfg (132! permutation — Phase 1.2 P1.2B-F5 必同步 orbit-aware lift)
- F5-QX (QuickXplain budget — Phase 1.2 P1.2B-F5)
- F9-base (envelope baseline 紧度 — Phase 1.2 P1.2B-F9)
- Q7 (attach point — 后续 P1.3)
- Q10 (propagator vs AddLinear — Phase 1.3 §12.4)
- Q11 (commodity_id vs route_id — Phase 1.5+ §13.1)

8 个 P0, 主要集中 Phase 1.2 P1.2B-F5 (F5 实施) 跟 后续 P1.3 (propagator 集成) 两个 milestone.

---


## 17. Open questions (待定)

1. Phase 1.5+ commodity registry schema (commodity_id vs route_id 级别) 何时
   决策? — Phase 1.5 真生产 data pipeline 设计时
2. F2 patch_routing_core 复用是否真 sound (paradigm 死在 multi-anchor 收敛,
   单 cut 生成仍 OK)? — Phase 1.5+ F2 oracle 实施时复 verify
3. evaluate_literal_port_exposure 删 vs 接进 dispatch — Phase 1.2 §10.7 一行决定
4. ghost_rect tuple 改 object schema vs 保留 tuple + 明确文档 — Phase 1.2 §10.4
   F8 实施前
5. Phase 1.3 propagator integration 跟 Phase 3B repair5 master 兼容性 — Phase 1.3
   §12.1 实施时验
6. F5 minimize NP-hard 超时阈值 — Phase 1.2 §11.1 实施时定

---
