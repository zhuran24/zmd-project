# PROJECT_LOCK.md

**Status**: CURRENT_LOCK
**Updated**: 2026-05-22 (B Design v2 Phase 0 close)
**Purpose**: Freeze exactness boundaries, source-of-truth rules, accepted invariants, and forbidden changes for the current repository state.
**History**: Date-stamped engineering history lives in [CHANGELOG.md](CHANGELOG.md). If this file conflicts with older notes, this file wins.

## 1. Exactness Constitution

- `certified_exact` and `exploratory` are separate paths. Exploratory outputs must not be promoted as certified evidence.
- The exact empty-rectangle objective is `max_lex(area, min_side)`.
- `min_side >= 6` is a candidate admissibility rule, not an objective tie-break.
- `Phi(w, h)` is not the exact source of truth.
- `(area, width, height)` is not the exact source-of-truth comparator.
- Exact mode has no hard `50 power poles + 10 protocol storage boxes` cap. If that number appears anywhere, it is exploratory-only guidance.

## 2. Certified Source of Truth

The certified path is grounded in:

- `rules/canonical_rules.json` (now also carries consolidated preprocess recipe / target / commodity truth)
- `data/preprocessed/candidate_placements.json`
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`
- artifact-hash-compatible campaign state
- provenance-complete exact-safe cuts

The following remain additive postprocess artifacts and must not redefine internal solve schemas:

- `data/solutions/final_solution.json`
- `data/blueprints/optimal_blueprint.json`
- `data/solutions/certified_delivery_manifest.json`
- generated viewer/report sidecars such as `viewer_report.json`
- compatibility export bundles such as `data/exports/industrial_planner/*`
- adapter-side outer deployment sidecars / validator probes for IndustrialPlanner larger-base experiments
- neutral interchange contracts under `src/interchange/*`
- build-time / export-time adapters under `src/adapters/*`
- build-time preprocess overlays such as `rules/preprocess_plan.json` and `src/interchange/preprocess_context.py` (currently cycle groups / utility operations / optional future overrides only)

## 2B. B Design v2 Cut Object Boundary (2026-05-22)

Phase 0 close (`docs/research/p3_b_design_v2_20260521/PHASE_0_CLOSE.md`) 后,
**cut object 升级为持久化一等公民**. New source-of-truth additions:

- `docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md` v3.2.2 — cut
  object schema + 10 步 lifecycle + 6 步 replay verify + 6 维 watcher
- `docs/research/p3_b_design_v2_20260521/cut_family_specs/{01-09}` — 9 cut
  family 完整 spec (region_capacity / cutset / port_exposure / component_reach /
  pattern_nogood / shape_packing_hall / power_hitting_set / power_grid_reach /
  density_envelope) 全 final version
- `docs/research/p3_b_design_v2_20260521/state_machine_v2.md` — group-orbit
  state + AnonymousSlotRef (替代 v14 per-instance state, 消 10^134 label
  symmetry)
- Phase 1 起 `data/cuts/*.json` (persisted active cuts) + `data/cuts/
  quarantine/*.json` (quarantined cuts) 加进 certified path source-of-truth
  (currently 空, 等 Phase 1 cut store 落地后启用)

**postprocess/adapter boundary** unchanged: cut object 仅在 certified core 内
循环, 不进 `src/adapters/*` / `data/exports/*`.

## 2A. IndustrialPlanner Active Scope

- The current certified IndustrialPlanner support contract targets `valley4_protocol_core` (70×70) exclusively.
- The other known IndustrialPlanner bases (`valley4_infra_outpost`, `valley4_rebuilt_command`, `valley4_refugee_shelter`, `wuling_tianwangping_aid`, and `wuling_protocol_core`) are preserved as `future_scope` and are not part of the active checked-in audit / CI contract.
- The checked-in full-demand base matrix, deployment-path matrix, umbrella overview, support-suite inventory, and checked-artifact gate must default to that single active 70×70 base.
- The outer-deployment subsystem for larger-base translation remains adapter-side `future_scope`: it may stay in the repository, but it must not be treated as active certified evidence or as part of the default CI-critical path until explicitly reactivated.

## 3. Accepted Invariants

- Best certified result is monotonic across campaign persistence and resume.
- `final_solution.json`, `optimal_blueprint.json`, and `certified_delivery_manifest.json` must be derived from the same best certified result when one exists.
- Optional compatibility exports must be derived from the canonical blueprint and must not become the source of truth for solver/runtime consumers.
- Postprocess manifest/export mappings used to bridge translated larger-base exports remain adapter-side evidence only and must not be promoted into certified proof.
- Production parallel scheduling uses a coordinator-only writer with disjoint candidate waves.
- Optional frontier probe mode is an exact-safe scheduling hint only and must not replace completeness requirements.
- Global pooling semantics for shared boundary/core resources must remain commodity-aggregated.
- A fully enclosed legal empty rectangle remains allowed; exterior connectivity is not part of the exact contract.

### 3A. B Design v2 invariant additions (2026-05-22)

Phase 0 23 round Gemini cross-check 后 frozen invariants. **Phase 1 实施
不可破**:

- **Exactness FP = 0**: 任何 cut 都不能误剪合法解 (False Positive = 0).
  False Negative (cut 漏发, 性能退化) 可接受, FP 致命. Gemini round 19 原则
  "宁可 FN 不可 FP" 写进 lock.
- **Group/orbit-count symmetry**: state 必走 group-orbit 而非 per-instance,
  消 10^134 label symmetry. AnonymousSlotRef multiset 包含语义跨 candidate
  enumeration order 必 sound (slot_index 仅 debug/serialization 用, 不参与
  soundness 推理).
- **Cut family ↔ mode 一致性**: `_FAMILY_MODE_MAP` (cut_lifecycle_v2 v3 §3)
  契约 — literal-based family (3/5/7) 走 multiset evaluate, geometric family
  (1/2/4/6/8/9) 走 evaluate_geometric. `__post_init__` enforce literals
  XOR geometric_payload 互斥.
- **Scope-aware HOLD vs Quarantine**: 6 步 verify (cut_lifecycle v3.2.2 §4)
  失败的处理必须严格区分 — HOLD 不删 cut 等下次 candidate matching;
  QUARANTINE 不删 cut 留 audit trail 不进 active resolve; 两者不能混. ghost-
  agnostic cut (`GHOST_AGNOSTIC` sentinel) 跳 ghost_rect_id 校验**但**仍走
  exterior_blocks_hash 校验 (v3.2.2 dispatch).
- **F9 paradigm 降级 lock**: density_envelope 只 trigger
  `area_capacity_overflow` 凭证. binding/routing/PCR-CUT INFEASIBLE 必 fallback
  Family 5 pattern_nogood (Gemini round 19 verdict). 不允许 silent generalize
  topological deadlock → density cut.
- **F9 area-based counting lock** (Gemini round 24 B2 — round 20 finding 焊死):
  F9 evaluator + validator 必走 area-based `sum(|pose_cells ∩ W|)` 计数,
  **不可退化** instance-based counting (v1.0 over-count / v1.2 origin-in-W
  / v1.3 all-in-W 全 unsound — v1.0 FP, v1.2 FP, v1.3 FN). v1.4+ 全
  area paradigm 是唯一 sound 路径, 任何 refactor 退回 instance-counting 算
  Forbidden Change.
- **(2026-06-04 v28 GPT pro 外审) Cut-family validator 数值/字面量 source-of-truth
  gate**: 任何 accepted cut 里 validator **无法独立便宜重算**的 scalar/literal
  payload, 必须对 canonical_rules / source-of-truth fail-closed 交叉核对 (镜像 v28
  F7 `pole_radius` 修复)。逐 family 焊死:
  - **F5 pattern_nogood slot 完整性**: `forbidden_pose_pattern` 每个 literal 必须绑
    一个真实、唯一、在界内的匿名 slot — `slot_index < group.demand` + `(group, slot)`
    唯一 + per-group literal 数 ≤ demand。Why: generic evaluator
    (`evaluate_literal_multiset`) 刻意丢 slot 身份按 `(group, pose)` multiset 评估,
    一个 slot-collision 核 `[(g,0,pA),(g,0,pB)]` 虽被 oracle 正确判 INFEASIBLE (单
    slot 不能两 pose), lift 成 multiset cut 后却比 oracle 实际证明的更强 → 错剪合法
    布局 slot0→pA/slot1→pB (FP)。
  - **F6 shape_packing_hall region_demand 下界**: `region_demand ≤ max(0, group_demand
    − 对侧 baseline 容量)`, 且仅接受 `left_or_bottom_boundary` 模板。Why: 单边 Hall
    cut 只对 "被 pigeonhole 强制到该侧" 的数量 sound; 容量上界 ≠ 强制下界, 伪
    `region_demand` 会错剪合法 split (全放另一边)。
  - **F7/F8 footprint SoT**: power_pole footprint 2×2、protocol_core footprint 9×9
    必须对 `canonical_rules.facility_templates.{power_pole,protocol_core}.dimensions`
    fail-closed 核对 (与既有 `pole_radius` gate 同款)。当前 canonical 下无 live FP,
    防 footprint drift 退化成 F7 radius 同类洞。
  共享实现集中在 `src/cuts/helpers/canonical_sot.py` (canonical lookup + fail-closed
  dims 校验), F7/F8 委托它 (不再各持私有副本); `src/tests/cuts/test_canonical_sot_coverage.py`
  meta-test 强制 (登记契约 + 私有 lookup 不复活)。**新增信任 canonical 标量的 family 必须
  走 canonical_sot + 进登记表 + 加 behavioral red-test** (meta-test 抓回归, 但发现"全新未守
  标量"仍靠人/审查 —— 诚实边界)。**已知 grandfathered**: F6 (shape_packing_hall) 有一份
  family-local canonical-dims SoT 核对 (pose_length vs template dims, 经 state.facility_templates
  alias, sound fail-closed) 未走 canonical_sot、未进登记表 —— 它**非 fail-open 洞** (v28 合并只
  针对 fail-open), 是预存未 consolidate 项; meta-test 的 dimensions 私有扫描刻意不覆盖它。
- **(2026-06-04 v28) F9 tight-K quarantine (supersedes Gemini round-4 oracle-trust
  deferral)**: density_envelope validator 对 `max_allowed_area = K < safe_ub` fail-
  closed 拒 (Phase 1.2 cert 不携带 replayable tight-bound proof)。净效果: F9 只剩
  K==safe_ub 的平凡 cut (`_validate_witness_overflow` 的 strict `>` 在 K==safe_ub
  不可满足 → F9 实质停用)。**这反转 Gemini round 4 "信任 oracle K、tight-K 重验
  defer P1.5+" 的判断**: replay 实证 validator 是信任边界且不重跑 oracle
  (`replay.py` 对 deserialized cert re-validate), 信任无法重算的 cert 标量 = replay
  时真 FP 暴露; 与上方 validator SoT gate 原则一致。恢复 tight F9 须在 Phase 1.5+
  给 cert 加 area-capacity proof-carrying 字段 + replay 校验 (与 F5 v1.0 信任
  INFEASIBLE 同类升级)。**解封时同步恢复**
  `test_generator_witness_canonical_order_independent_cert_hash` 的 cert_hash 不变量
  覆盖 (quarantine 期间该测试改为 assert 空)。与 "F9 area-based counting lock" 正交
  (不改计数 paradigm, 只加 K fail-closed gate)。
- **RAM 测量必走 psutil RSS** (Gemini round 25 B2 — Phase 1 OOM 防虚假 PASS):
  168h campaign cut store RAM 监测 (`exit_criteria` #6 + ramp report
  `cut_store_peak_mb_per_worker`) **必须** 用
  `psutil.Process(pid).memory_info().rss` 读 OS 级真物理内存. **禁** 用
  逻辑大小计算 (`sys.getsizeof(cut)` / JSON string len 累加 / `dict` len ×
  estimate). Why: Python 对象头 + dict/tuple/dataclass 小对象内存碎片化导致
  逻辑 3 GB → RSS 8 GB. 若 #6 PASS based on 逻辑大小但 RSS 已超 5 GB, 168h
  campaign 仍触发 OS OOM kill. Phase 1 ramp report 必 emit
  `rss_peak_mb_per_worker` field, exit_criteria 优先验该字段.
- **代数 vs 几何分工**: 全局代数约束 (e.g. power supply cap, total worker
  count) 必走 Master CP-SAT 线性约束, 不进 cut framework (Gemini round 22
  F16 verdict — "代数归 Master, 几何归 Cut").

## 4. Forbidden Changes

- Reintroducing exploratory caps as exact-mode bounds.
- Treating exploratory artifacts, legacy cuts, or diagnostic flow checks as certified proof.
- Changing campaign, artifact, or proof schemas without explicitly updating the lock/spec/test boundary together.
- Rebinding globally pooled resources into per-line or per-instance hard bindings without a new exact proof basis.
- Adding any exterior-path requirement for the ghost rectangle.
- Enabling `EXACT_POWER_PLACEMENT_SUBPROBLEM=1` in any certified / production campaign path. The power-pole subproblem feature flag is exploratory only. Status of the three known exactness gaps (as of GPT v4 review follow-up):
  - **Live ghost-conditioned infeasible cut**: implemented (`condition_lits` 走 master.add_benders_cut, `OnlyEnforceIf`).
  - **Persisted cut replay**: `BendersCut.condition_set` 在 `run_benders_for_ghost_rect` 现已通过 `_resolve_condition_lits_from_condition_set` 反解析回 master `u_var`, certified mode 下未知 condition fail-closed skip cut (不退化成无条件).
  - **Feasible-path pole alternatives**: 未实现 witness-complete cut. 现 stop-gap: `_add_exact_whole_layout_nogood` 在 flag on 且 solution 含 synthetic power_pole entry 时 fail-closed skip cut, caller 升 `UNKNOWN`. 真正解锁 feature 需要 enumeration / 多 witness 增量排除.
  
  The production readiness gate and `scripts/run_campaign_linux.sh` both still block when the env var is set; do not bypass them until pole alternatives is implemented and re-audited.

- Bypassing **exact-safe proof object lifecycle**. Any persisted artifact carrying solver-side semantics (e.g. `BendersCut.condition_set`, `BendersCut.metadata`) must have all six steps wired before being trusted in certified mode: generate → serialize → deserialize → validate → resolve runtime literals → replay → behavioral regression test. Landing a new schema field without the runtime resolver + regression coverage is treated as a Forbidden Change, regardless of how harmless the "feature gate currently off" feels.
- **(2026-05-22) Bypassing B Design v2 9 步 cut lifecycle**: new B Design v2
  cut object (Phase 1 起在 `src/cuts/` 落地) 必须 wire 9 步:
  canonicalize → generate → minimize/normalize → serialize → deserialize →
  validate → attach-scope check → resolve → activation index → replay/regression.
  (Step 10 dominance/expiry/demotion defer to Phase 2 per Gemini round 13.)
  跳过任一步骤 (例如 Phase 1 implementation 没写 scope-aware replay 直接进
  168h campaign) 算 Forbidden Change. PoC `docs/research/p3_b_design_v2_20260521/
  poc/b_core_lifecycle_poc.py` 14/14 PASS 必跨 src/ boundary 真验.

  **Capacity-based Eviction 豁免** (Gemini round 24 B1 — A2 §4 vs A3 R2 冲突解):
  Step 10 dominance/expiry/demotion 严禁的是**语义级 expiry** (基于 cut
  hit-count / age / subsumption 主动 demote/expire). **不禁** capacity-based
  eviction — 当 cut store 达 RAM/disk 上限 (e.g. 5 GB/worker per criterion #6)
  时, 走 LRU/FIFO 驱逐**最近最不命中的 cut** (cut 仍 sound 只是工程上不存)
  防 OOM. 这是工程兜底, 不属于 Step 10. Phase 1 实施时驱逐 cut 必走
  `data/cuts/quarantine/evicted/` 子目录留 audit trail (不删, 168h close 后
  归档), 跟 Step 10 semantic expiry 不混.
- **(2026-05-22) Silent recovery 禁止**: B Design v2 9 family cut + replay
  全 fail-closed. cut.scope.source_digest 跟当前 source-of-truth hash 不一致
  → quarantine, **不可 auto-migrate**. 即使重算 cert 在新 source 下 sound,
  仍要手动 audit override (PROJECT_LOCK 一致 — certified exact 不允许 silent
  fix). Validator `ASSUMPTION_VERIFIERS` 未知 key → fail-closed return False
  (HOLD), 不可 silent return True. (Gemini round 14-22 共识 invariant.)

## 5. Allowed Changes

- Exact-safe lower bounds, dominance rules, reuse, caching, and scheduling improvements.
- Optional frontier probes that evaluate legitimate potential-domain candidates without weakening proof semantics.
- Additive postprocess exports, viewer/report sidecars, and delivery summaries.
- Additive neutral contract layers in `src/interchange/*` and build-time/export-time adapters in `src/adapters/*`.
- Adapter-side outer deployment planning/probing for larger IndustrialPlanner bases, plus optional exporter/throughput-manifest bridge metadata for those translated exports, may remain preserved as future-scope tooling provided those artifacts stay postprocess-only and are not promoted as certified evidence.
- Documentation, governance, provenance, and regression coverage improvements.
- Runtime discoverability improvements that do not alter solver semantics.

## 6. Update Rule

If a change affects exact boundaries, runtime roles, or certified output meaning, update:

1. `PROJECT_LOCK.md`
2. `FILE_STATUS.md`
3. the relevant spec(s)
4. the relevant regression tests
