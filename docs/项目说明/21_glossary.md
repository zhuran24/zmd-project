# 21 — Glossary 术语表 + refs

按字母 / 类别归. 术语首次在 plan 出现时不展开, 来此 anchor.

### A.1 项目顶层

- **终末地 (Arknights: Endfield)** — 鹰角网络游戏, 项目目标为其工业规划解题
- **IndustrialPlanner** — 终末地游戏内工业规划玩法, 70×70 grid + 266 facility instance
- **70×70 grid certified exact solver** — 本项目, 求 `max_lex(area, min_side)` 最大空矩形 + 全 facility placement 可行性证明
- **valley4_protocol_core** — 当前 active scope 单 base; 其他 base (`valley4_infra_outpost` 等) future_scope
- **certified_exact mode** — 项目主路径, 跟 `exploratory` 路径严格分离; 本 plan 全 scope 在 certified_exact
- **Phase 命名 crosswalk (旧→新)** — 文档里若见旧命名按此对照（2026-05-23 v2 起规范化，见 08/09 preamble）：
  - `P1.11` → **P1.2A**（entry hardening，已 done）或 **P1.2B-F5**（pattern_nogood）——旧 `P1.11` 曾混用二者，v2 拆开
  - `P1.12`→**P1.2B-F6**(shape_packing_hall) / `P1.13`→**P1.2B-F7**(power_hitting_set) / `P1.14`→**P1.2B-F8**(power_grid_reach) / `P1.15`→**P1.2B-F9**(density_envelope)
  - `P1.21` → **P1.3B**（真 master integration，`step_8_apply_to_master`，待接）
  - **P1.3A** = CP-SAT attach spike（已先验）。⚠️ doc-P1.3A/B ≠ CC memory 口径的"P1.3A 主体"（memory 的"P1.3A 主体" = doc-P1.3B），见 `CLAUDE.md` 命名错位提示

### A.2 Cut Framework (B Design v2)

- **B Design v2** — cut framework spec 第二版, 含 9 family + 9-step lifecycle + state machine v2. (v1 早期 spec 死, 详 §4.7)
- **F1-F9** — 9 个 cut family (frozen, PROJECT_LOCK §3A):
  - F1 `region_capacity` (geometric) — 区域容量 pigeonhole / set covering
  - F2 `cutset` (geometric) — Menger min-cut max-flow
  - F3 `port_exposure` (literal) — 命题逻辑 + slot anonymity
  - F4 `component_reach` (geometric) — 4-conn graph BFS connectivity
  - F5 `pattern_nogood` (literal) — minimal unsat core + QuickXplain
  - F6 `shape_packing_hall` (geometric) — Hall's marriage theorem
  - F7 `power_hitting_set` (literal) — set cover NP-hard / LP relaxation
  - F8 `power_grid_reach` (geometric) — Liang-Barsky AABB intersection
  - F9 `density_envelope` (geometric) — 上界几何 (≥ area baseline=1.0 trivial)
- **family mode (literal vs geometric)** — F1/F2/F4/F6/F8/F9=geometric (sound deduction from geometry), F3/F5/F7=literal (proposition over pose assignments). PROJECT_LOCK §3A XOR
- **9-step lifecycle** — canonicalize → generate → minimize → serialize → deserialize → validate → attach-scope check → evaluate → apply-to-master
  - 当前 Phase 1.1: step 1/3-7 sound 闭环; step 2 (minimize) defer Phase 1.2 P1.11 (F5 deletion+QuickXplain); step 8 (apply-to-master) defer Phase 1.3 P1.21
- **cert (certificate)** — cut 的 mathematical 证明对象, 含 region/partition/component/commodity 等 family-specific 字段. validator 重算 cert 验 sound
- **literal** — cut 中排除的具体 pose assignment (`x[instance_id, pose_id]` boolean). literal-mode cut 用; geometric-mode cut 不直接持 literal
- **blocker** — F3 cert 中 blocking 一个 port slot 的另一 pose; F5 cert 中 "如果这些 literal 都 true 则 INFEASIBLE" 的支撑集
- **multiset eval** — slot anonymity 的形式化: slot 集合上 S_n permutation 群作用不变. evaluate 不绑具体 slot id, 看 multiset 计数 (state_machine v2 §5)
- **watcher** — `CutStore` 6 维 index (by_cell / by_group / by_pose / by_commodity / by_region / by_ghost), state 变化时 O(查询命中) 而非 O(总 cut) 找 affected cut
- **replay** — ghost rectangle 变 / state 变 / canonical_rules 变 → 触发 `on_ghost_rect_changed`, 已 active/held cut re-validate. fail-closed: canonical_rules=None → HOLD (Step M)
- **state machine (held / active / quarantined)** — cut 入 store 默认 held (per Step N); replay 通过 validator → active; validator reject → quarantined (隔离, 不再 try)
- **GHOST_AGNOSTIC** — sentinel scope value, 标记 cut 对 ghost rectangle 不敏感. F1 必验 ghost ∩ region == ∅ (Step O); F2/F4 直接 reject GHOST_AGNOSTIC scope
- **scope versioning** — `cut.scope` 含 `ghost_rect` + `source_digest`; ghost/data 变 → scope 失效 → cut 进 replay path
- **source_digest** — `canonical_rules.json` + preprocessed data 的 sha256 content hash；replay 时按当前 `BState` 注入 source 重新计算，不信任外部手写缓存
- **adversarial soundness** — validator 必须扛 "假 cert 攻击" — oracle 不可信 (Byzantine), validator 是 trust boundary. Step A-O 主要 close 的层
- **strict gate** — `EXACT_FAMILY_VALIDATOR_STRICT="1"` 时未注册 family / dispatch 漏 → fail-closed；当前默认已 ON

### A.3 Solver / Master 拓扑

- **CP-SAT** — Google OR-Tools Constraint Programming SAT solver (`ortools.sat.python.cp_model`). 项目 master / binding / routing 都用 CP-SAT
- **LBBD** — Logic-Based Benders Decomposition. master 出主决策 → sub-problem 验 (binding/routing/flow) → INFEASIBLE 出 nogood 回 master → master 加 cut. 项目核心 paradigm
- **master / binding / routing / flow** — 项目 4 层 solve 拓扑:
  - master — placement (各 instance 选 pose) + ghost rectangle
  - binding — port binding (每 port 出/入 connect 哪条带)
  - routing — grid routing (belts 怎么连)
  - flow — multi-commodity flow diagnostic (诊断 routing INFEASIBLE 时为啥)
- **outer search** — 枚举 (area, min_side) candidate 矩形, frontier-based, Phase 3A delivery
- **candidate** — outer search 一次 try 的 (area, min_side, anchor) 三元组. ~1000-10000 candidate / 168h
- **benders_loop** — `src/search/benders_loop.py` 的 LBBD 主循环. cut framework Phase 1.3 接进的 attach point
- **ghost rectangle** — 70×70 grid 中 candidate 选中的目标 max empty rect, master 必保留其内部空
- **pose** — 一个 facility instance 在 grid 上的具体 (位置, 方向, port mode). 项目 production data 81795 pose / 266 instance
- **anchor** — ghost rectangle 的锚定 cell (左下角 / 旋转中心 等, 视 family 定)
- **BSP** — `boundary_storage_port` (边界存储口 facility). production 134 BSP, sample 54 BSP
- **mfg_3x3 / mfg_5x5 / mfg_6x4** — manufacturing facility 尺寸变体 (3x3 / 5x5 / 6x4 grid cell)
- **power_pole** — 50 个 (exploratory cap 旧值, certified_exact 无 hard cap) 电力柱 facility
- **power_coverage** — power network 用 power_pole 覆盖各 facility 的几何 + topology constraint
- **commodity** — multi-commodity flow 中一个 (source, sink, demand) 三元组. F2/F4 cert 含 commodity_id, Phase 1.5 真接 data pipeline (§13.1)

### A.4 Paradigm 死路 (历史)

详 `paradigm_death_timeline_27_lever.md` (memory)

- **B1 (pose-bool master)** — L11 paradigm, 27×15 interior pose-bool 7.2s FEASIBLE 但 master.solve INFEASIBLE 不收敛. **L11-L16 ❌**
- **PCR-CUT (Patch-Certified Routing Conflict Core)** — Path 14, env-gated. Phase 0-4 GO, Phase 5 multi-anchor marginal. 详 §4.2
- **SAC-Hull** — Path 13, separator capacity. L2 工作但 binding/routing reject 不收敛. **❌** §4.3
- **RAB-SEP** — Path 12, routing abstraction binding-separator. cert tight 8/8 UNPROVEN. **❌**
- **D2 commodity flow / arc** — Path 17, Phase 2 multi-anchor. **❌** §4.4
- **cand C column generation** — Phase 1 4-ramp GO 但 master basis 真换后 reservation **superseded** by paradigm shift. §4.5
- **L01-L26 + L27 IHS / L26 Benders symm / L25 layout-invariant** — paradigm_death_timeline cite, **全 ❌**

### A.5 审查 / 工具

- **Gemini per-commit cross-check** — 每 commit 调 Gemini 3.1 pro 验 schema/spec/data gap. 详 §22.1
- **GPT pro batch audit** — 大节点打包 GPT pro 验 adversarial soundness. 详 §22.2
- **v1-v8 review package** — Phase 1.1 audit 累积包. v1-v7 cut-only 0.3 MB; v8 全项目 7z 6 MB
- **7z + zip 壳 + 7za binary** — 大 review pkg 压缩 strategy. 详 [[review-pkg-7z-strategy]]
- **audit armor** — GPT review prompt 三段式: 真瓶颈 + 死路黑名单/白名单 + 不可达必须形式化证明. 详 [[gpt-review-prompt-armor]]
- **adversarial soundness audit** — Step A-O 主战场. 5 验: cert 内 sound + cert↔literals + cert↔真数据 + cert↔state + cert↔不变量. 详 [[adversarial-soundness-audit]]
- **red fixture** — known-infeasibility 反例 .md, 在 `docs/research/.../red_fixtures/`. 5 个 F1-F5. 详 §21.3

### A.6 Data sources (`data/preprocessed/`)

- **canonical_rules.json** — 项目 SoT, 含 17 recipe + facility templates + targets + commodity types. 详 `rules/canonical_rules.json`
- **candidate_placements.json** — 全 pose 枚举 (instance, pose_idx, occupied_cells, ports, orientation, port_mode). Production 53 MB / 81795 pose; viewer sample ~273 pose
- **mandatory_exact_instances.json** — 266 必装 facility instance
- **generic_io_requirements.json** — commodity flow demand (per recipe / target)
- **all_facility_instances.json** — 全 facility instance 详 (含可选 deployment)

### A.7 项目 invariants / locks

- **PROJECT_LOCK §3A** — 数学 / 工程 invariant lock; cut framework 边界 (family mode XOR / 9 family frozen / cert+literals XOR geometric_payload / GHOST_AGNOSTIC sentinel / multiset eval slot anonymity / adversarial soundness). 改任一必先 PROJECT_LOCK 更新 + 跨 spec/src/test 同步. 详 §18
- **`certified_exact` vs `exploratory`** — 严格分离, 不混路径. exploratory artifacts 不算 certified proof; exploratory 的 `50 power pole + 10 storage box` cap 不进 certified_exact
- **postprocess-only** — `src/adapters/` / `src/render/` / `data/exports/` / `data/examples/` 不重定义 solve schema; 仅消费 certified proof
- **`max_lex(area, min_side)`** — 项目 objective; `min_side >= 6` 是 admissibility 不是 tie-break

### A.8 Phase 命名

- **Phase 3A** — productization, release `r20260416`, complete
- **Phase 3B** — full-scale exact proof, in progress (repair5 master 30→47 GB fits)
- **Phase 3C** — Linux migration + CachyOS 调优 + observability + 路线图 22 P0/P1/P2 项
- **Phase 0/1.0/1.1/1.2/1.3/1.5+** — B Design v2 phase 命名 (cut framework 内):
  - Phase 0 — B Design v2 spec + invariants frozen
  - Phase 1.0 — framework migration (Day 13-17)
  - Phase 1.1 — F1-F4 production validator + oracle + lifecycle + replay + Step A-O (**当前闭环**)
  - Phase 1.2 — F5-F9 5 family 加 + 入门 7 项 factual fix
  - Phase 1.3 — propagator 真接 master.AddLinear / step_8 apply_to_master / by_exterior_watcher / perf opt
  - Phase 1.5+ — production integration, commodity registry 真接 data pipeline



## 9. 引用 / refs

### 项目 doc
- `docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md`
- `docs/research/p3_b_design_v2_20260521/state_machine_v2.md`
- `docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md` ~ `09_density_envelope.md`
- `docs/research/p3_b_design_v2_20260521/paradigm_death_timeline.md`
- `docs/research/p3_b_design_v2_20260521/PHASE_POST_1_1_REFACTOR_PLAN.md`
- `docs/research/p3_b_design_v2_20260521/PHASE_0_CLOSE.md`
- `docs/research/p3_b_design_v2_20260521/PHASE_1_PLAN.md`
- `docs/research/p3_b_design_v2_20260521/red_fixtures/README.md` + `F1-F5*.md`
- `PROJECT_LOCK.md` §3A
- `CLAUDE.md` (project + global)

### 学术 reference (paradigm 数学根据)
- Hooker, J. N. (2003). *Logic-based Benders decomposition*. Mathematical Programming 96(1).
- Bertsimas, D., & Tsitsiklis, J. N. (1997). *Introduction to Linear Optimization*. Athena Scientific. Ch.11 (LP duality).
- Menger, K. (1927). *Zur allgemeinen Kurventheorie*. Fundamenta Mathematicae 10. (min-cut max-flow theorem)
- Ford, L. R., & Fulkerson, D. R. (1956). *Maximal flow through a network*. Canadian Journal of Mathematics 8.
- Hall, P. (1935). *On representatives of subsets*. Journal of the London Mathematical Society 10. (marriage theorem)
- Garey, M. R., & Johnson, D. S. (1979). *Computers and Intractability: A Guide to the Theory of NP-Completeness*. (set cover NP-complete)
- Chvátal, V. (1979). *A greedy heuristic for the set-covering problem*. Mathematics of Operations Research 4. (ln n approximation)
- Liang, Y. D., & Barsky, B. A. (1984). *A new concept and method for line clipping*. ACM Transactions on Graphics 3. (AABB intersection)
- Liffiton, M. H., & Sakallah, K. A. (2008). *Algorithms for computing minimal unsatisfiable subsets of constraints*. Journal of Automated Reasoning 40. (MUS computation)
- Junker, U. (2004). *QuickXplain: Preferred explanations and relaxations for over-constrained problems*. AAAI. (QuickXplain divide-and-conquer)

### 工具 / 实现
- Google OR-Tools CP-SAT — `ortools.sat.python.cp_model`
- CPMpy 0.10.0 — MUS extraction PoC (P2 #18, [[cachyos-paste-and-nm]] 不相关)

---

*Last updated*: 2026-06-04 (initial 2026-05-23; 后续随 Phase 1.2 close / F3·F8 mode 锁 / strict gate 默认 ON / F9 quarantine 等口径更新)
