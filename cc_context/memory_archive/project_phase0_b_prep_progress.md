---
name: phase0-b-prep-progress
description: "B Design v2 Phase 0 + A集成层 + Phase 1.0 framework 全 land (2026-05-22). 26 Gemini round + Phase 1.0 4 件 src (lifecycle/store/replay/assumptions+helpers) + round 28 GO. 下一步 Phase 1.1 P1.5-P1.8 (F1-F4 实施)."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

## 2026-05-22 Phase 1.0 framework 全 land ✅

4 件 src 一日完成 (18a8cab → 2d275f8):
- **P1.1** (18a8cab): `src/cuts/lifecycle.py` 从 PoC 迁 + 9-family map + v3.2.2
  GHOST_AGNOSTIC dispatch + __post_init__ schema-first 强制 (XOR + 9-family +
  scope/cert 必填). 17 test PASS.
- **P1.2** (fe77a0c): `src/cuts/store.py` CutStore + 6 维 watcher + on_ghost_rect_changed
  4-branch dispatch + state machine (quarantine terminal / hold). 14 test PASS.
- **P1.3** (224349e): `src/cuts/replay.py` replay_cut + regression_sweep + FAMILY_VALIDATORS
  dispatch + fail-closed (unsound/timeout/schema_err → QUARANTINE). 8 test PASS.
- **P1.4** (a80a4d6 + cdb0531): BState.canonical_rules + assumptions/verifiers.py
  (production verifier 修 Gemini r27 B1) + helpers/ghost_geometry.py (Liang-Barsky AABB)
  + helpers/baseline_partition.py (v1.1 仅依赖 ghost+exterior) + helpers/power_network.py
  (jump graph + bfs_component). 50 test PASS (15 assumptions + 12 ghost_geometry +
  11 baseline + 12 power_network).

**Total**: src/cuts/ + src/tests/cuts/ ~2600 LOC, 90/90 test PASS, ruff + mypy
全 clean, no regression (full pytest 后台跑).

## Cross-check 节奏

- **Round 27** (P1.1 verify): GO + 3 P1.2+ 盲区 (B1 ASSUMPTION_VERIFIERS 真实施 /
  B2 run_lifecycle deprecate / B3 multiset eval). B1 已修 commit a80a4d6.
- **Round 28** (整 Phase 1.0 framework): **GO**. 4 件 src "完全跟 spec 一致".
  4 个 P1.5+ 盲区: #1 silent skip (HARDENED env flag) / #2 register_verifier
  silent overwrite (HARDENED) / #3 held LRU eviction (DEFER P1.22) / #4 bfs_component
  Set 序列化 (DEFER P1.14 F8 cert).

## Phase 1.1 起步状态

Phase 1.0 framework GO → Phase 1.1 P1.5-P1.8 (F1/F2/F3/F4 实施) ready 推进.
- P1.5: F1 region_capacity 完整 validator + Farkas cert (复用 cand C)
- P1.6: F2 cutset (wrap patch_routing_core)
- P1.7: F3 port_exposure literal (round 27 B3 multiset eval)
- P1.8: F4 component_reach (wrap d2_separator)

Phase 1.1 wall: ~5-6 day Claude pace.



2026-05-21 Phase 0 B preparation v3 plan (Gemini round 13 cross-check 微调后, 3 week wall):

## ✅ 已完成

### Day 1-2 (commit 976bc10): boundary source-of-truth freeze + double-count bug

源码 ground truth verify (跟 v14 包文档矛盾):
- rules/canonical_rules.json `placement_rule: "left_or_bottom_boundary"`
- placement_generator.py gen_boundary_ports: 左基线 67 + 下基线 67 = 134 poses
- 46 × 3 = 138 cells 必须 100% 铺满 left+bottom 138 cells (不是 perimeter 276 占 50%)

决策走方案 B: 改文档不改 generator (源码本来就对). 改的 file:
- README.md: 加 source-of-truth correction note 顶部
- 266_mandatory_breakdown.md: 14 处 perimeter/276 → baseline/138
- geometric_deadlock_data.md: 12 处
- cand_c_phase_0_1_2_v3_verdicts.md: 4 处
- boundary_port_perimeter_trap.md: 24 处 (file name 保留)
- 5_cut_family_definitions.md: resolve_region_capacity double-count bug 修 (加 `if i in placed: continue` 跳过 placed instance)

### Day 3-9 (commit 64c5317): 双线 design doc

**Dev A — state_machine_v2.md (445 LOC)**:
- Group/orbit-count basis (消 10^134 label 对称, 替 v14 per-instance schema)
- 4 derived domain projection: binding_domain / forced_terminal_resources / front_resource_load / power_cover_domain
- 10 trail event + reversible delta log (不靠 cause_decision_id)
- 6 state invariant + O(5K op/call) validator
- AnonymousSlotRef contract: `(group_id, slot_idx)` + 枚举 group subset match
- ghost-conditioned power_cover lazy rebuild

**Dev B — cut_lifecycle_v2.md (678 LOC)**:
- 10 步 lifecycle (Step 10 dominance defer to Phase 2)
- 8 dataclass / 31 field: Cut/CutLiteral/AnonymousSlotRef/CutScope/SourceDigest/OracleCert/Assumption/ValidationResult
- Scope-aware replay 5 步 verify: source_digest → ghost_scope → artifact_hashes → oracle_abstraction_version → active_assumptions
- 6 per-family validator contract
- 5 维 watcher index (cell/group/pose/commodity/region)
- Source rotated → 全 store quarantine 必手动 override (PROJECT_LOCK 不 silent recovery)

**Cross-contract convergent**: Dev A "枚举 group subset match" = Dev B "multiset 包含 (Counter ≤ Counter)". slot_index 仅 debug/serialization. 跨 candidate enumeration order 无关化.

### Day 10-12 (commit 4da7e30): F1-F4 red fixtures

doc-only spec-level, 5 文件 906 行在 `docs/research/p3_b_design_v2_20260521/red_fixtures/`:
- F1 boundary saturation (Day 10 full): crusher pose 占 left baseline → boundary 缺 1 demand. Family 5 pattern_nogood + Family 1 region_capacity 双 cut hardcode. multiset evaluate 期待 violate / not-violate 两 case.
- F4 ghost-scoped replay (Day 11): G1 学 cut, G2 移挡误剪. 期待 replay_cut step 2 → AttachDecision.HOLD.
- F2 shape packing Hall (Day 12, [NEEDS_NEW_FAMILY]): 长度 10 切 [1-4]+[6-10], 9 cells pass region capacity 但 ⌊4/3⌋+⌊5/3⌋=2<3 infeasible.
- F3 power no-cover (Day 12, [NEEDS_NEW_FAMILY]): G ghost 覆盖 facility 周 R 全 pole → 空 power_cover bitset. L16 lazy power 复用.

5 schema gap 接给 Day 13-17:
1. literals 非空约束 — region/几何 cut 需 schema split (literals optional + geometric_payload)
2. CutFamily enum 加 2 family (shape_packing_hall + power_hitting_set)
3. evaluate_cut family-dispatch (literals-based vs geometric)
4. ghost_rect_id canonical hash 算法
5. active_assumptions verify 实现

### Day 13 (commit 3dd3d63): schema update v3 解 5 gap propose

`docs/research/p3_b_design_v2_20260521/schema_update_v3.md` (269 LOC).
5 gap 全 propose 解决方案 + 跟 4 fixture 对齐 + 跟 state_machine_v2 + cut_lifecycle_v2 兼容性 audit.

### Day 14 (commit f861ba7): cut_lifecycle_v2 v3 land 5 gap

`cut_lifecycle_v2.md` +231/-27 LOC. 接 schema_update_v3 propose:
- §3 schema: literals Optional + geometric_payload, _FAMILY_MODE_MAP 一致性, GHOST_AGNOSTIC sentinel, CutFamily enum +2
- §4 replay: GHOST_AGNOSTIC 跳过 + compute_ghost_rect_id 算法 + ASSUMPTION_VERIFIERS dispatch + fail-closed
- §5 evaluate_cut family-dispatch entry + evaluate_cut_literal_based 改名
- §6 CutValidator Protocol 加 evaluate_geometric method + Family 7 power_hitting_set 加 + 6 family 标 geometric/literal mode

### Day 15 (commit 925157e): Family 1 region_capacity 完整 spec

`cut_family_specs/01_region_capacity.md` (489 LOC). 12 段完整 spec — 数学定义 + soundness proof + cert schema + cut 构造 + LP dual generator + combinatorial fallback + evaluate_geometric hot path + 独立 validator + replay 5 步 + watcher index + F1 fixture 对齐验证 + 5 open question + Phase 1 实施 pre-decision. 复用 cand C farkas_certificate.py.

### Day 16a (commit 30b0a2d): Family 6 shape_packing_hall 完整 spec (v3 新 family)

`cut_family_specs/06_shape_packing_hall.md` (523 LOC). v3 新 family, F2 fixture owner. Hall's marriage theorem-based interval scheduling — 拦 region_capacity 不能拦的 Gemini round 12 反例 B (length 10 baseline 切 [4,5], 9 cells pass capacity 但 ⌊4/3⌋+⌊5/3⌋=2<3 INFEASIBLE). compute_baseline_partition_lens helper + evaluate_geometric 重算 partition + Validator 4 步. Multi-shape Phase 1 defer (NP-hardness PARTITION-reducible). by_ghost 6 维 watcher Day 17 加.

### Day 16b (commit 824c9b6): Family 7 power_hitting_set v1.0

### Day 16c-1 (commit 75e5f18): 修 Gemini round 14 5 finding

cross_check/gemini_round_14_cut_families.md (8.6 KB). 3 致命 sound bug:
- F7 v1.1 causation split (ghost-empty 单 literal / cell_owner-empty 多 literal + blocking_facility_literals)
- F6 v1.1 partition 改 static (ghost+exterior only, 不含 cell_owner)
- F1 v1.1 cap_R 改 static (ghost+exterior only)

2 schema 漏:
- cut_lifecycle §4 加 step 3 blocked_cells_hash 校验 (5→6 步 verify)
- F1 cert 加 cells_per_pose field (Validator 自包含, 不走外部 state)

### Day 16c-2 (commit 1f1e051): paradigm death timeline 27 lever consolidated

`paradigm_death_timeline.md` (210 LOC). 补做上次 prep 项 2. 5 类死法 (cut amplification 不够 / accumulation 不够 / family abstraction 不够 / master augmentation 撞 scale / 几何死结) + 4 共同 root cause (pose-bool master 表达力 / 96% util / cell-front break symmetry / 48 GB 上界) + B 5 unsolved issue 状态 + F5 反例不撞已死 paradigm 评估. memory entry [[paradigm-death-timeline-27-lever]].

### Day 16c-3 (commit cdfbdcb): Gemini round 15 cross-check (带 timeline)

cross_check/gemini_round_15_followup.md. 4 任务:
- A 验 round 14 5 finding 修法: ✅ 全 sound 没引入新 bug (F7 causation split 严格优于 Family 5 — 白盒 vs 黑盒)
- B 验 F5 评估: ✅ Family 8 power_grid_reach 独立 family 选择正确
- C 新风险: F7 cell_owner causation 5-literal cut 几何扰动失效 (Class B), M5 trivial orbit 几何对称性 literal-based cut 死绑 pose_id (Class C)
- D 推荐 Family 9 density_envelope (manufacturing cluster trap Class C mitigation)

总体评价: Day 1-16b 架构非常扎实, 已避开 Class A + Class D 死路. Class B/C 风险通过 F9 + Translation Lift 解决.

### Day 16c-4 (commit edecbd7): B core PoC — cut lifecycle 9 步 + Family 1 runtime ✅ 14/14 pass

补做上次 prep 项 3 (B core PoC). `poc/b_core_lifecycle_poc.py` + test (1084 LOC). Schema-first 不 retrofit. 9 步 lifecycle runtime 验证 (含 v1.1 修后 cap_R static / cells_per_pose / blocked_cells_hash step 3 / GHOST_AGNOSTIC + step 3 仍校验). Phase 1 实施直接迁 src/cuts/families/region_capacity.py.

### Day 17 (11 commits — 17a 到 17k): 9 family spec + 7 轮 Gemini cross-check (round 14-22)

- 17a-d: Family 2-9 spec + F5 fixture + by_ghost watcher v3.2
- 17e-j: round 16-21 修 (~15 finding, F9 evaluator 5 版本演进 v1.0/1.2/1.3/1.4/1.5)
- **17k FINAL CLOSE** (8ea6d00): Gemini round 22 verdict 🟢 "Phase 0 无懈可击, 进 Phase 1". 1 行 watcher 漏修 + PHASE_0_CLOSE.md 总结 + F16 反例 verdict (代数归 Master 不进 Cut framework).

## ✅ Phase 0 + A 集成层 ABSOLUTE CLOSE (2026-05-22)

Final state (Day 1 → Day 18c, 32 commit, 26 round Gemini cross-check):
- 9 family 全 final version + B core PoC 14/14 PASS
- cut_lifecycle v3.2.2 (10 步 + 6 步 verify + 6 维 watcher)
- 5 red fixture (F1-F5) + F10-F17 反例全 verdict
- A 集成层: 10 criterion exit checklist + PROJECT_LOCK §2B/§3A/§4 update + PHASE_1_PLAN
- 8 invariant (Exactness FP=0 / Symmetry 消 10^134 / family↔mode / HOLD vs Quarantine / F9 paradigm 降级 + area-based / 代数归 Master / Step 10 vs capacity eviction / RAM 必走 psutil RSS)
- Gemini round 26 verdict: "没有找到任何 bug, **Phase 1 编码 GO, 不再 cross-check 此层**"

完整: `PHASE_0_CLOSE.md` + `PHASE_1_PLAN.md` + `PROJECT_LOCK.md` v2 + `scripts/b_design_v2_exit_criteria.py`

下一步 Phase 1 代码实施 (~22-28 day Claude pace + 3-5 day wall clock):
- 1.0 framework (src/cuts/lifecycle/store/replay/helpers, ~4 day)
- 1.1 Family 1/2/3/4 (~5-6 day)
- 1.2 Family 5/6/7/8/9 (~7-8 day)
- 1.3 integration (~4 day, 含 P1.20 smoke 内存 only 解耦)
- 1.4 ramp 5/20/40/80/160/266 inst (~6 day Claude pace + 3-5 day wall clock)

## 🟡 还剩 Day 13-21

按 plan v3:

- **Day 13-17**: 4 类新 cut family schema (port-front terminal resource / shape packing Hall / multi-commodity vertex capacity / power support hitting-set) 完整数学定义 + soundness 证明 + generator + resolve + validator + replay. **接 Day 10-12 暴露的 5 schema gap**.
- **Day 18-21**: 集成 + 168h campaign 8 条 exit criteria checklist Go/No-Go gate + PROJECT_LOCK update (cut object 一等公民边界).

## 关键 implementation phase pre-decision

1. **不写 Rust/pyo3** (Gemini round 13 defer to Phase 2): Python + numpy bitset 先跑通 168h. 当前最大风险是数学模型 + state machine bug, 不是常数性能.
2. **Step 10 dominance defer to Phase 2**: 10 步 lifecycle 实际实施 9 步, dominance/expiry/demotion 后期再加.
3. **CDCL(T) third option defer Q3/Q4**: 不进 prep phase.

## 168h campaign 启动 8 硬条件 (Day 21 exit criteria)

按 GPT pro 给的 (memory [[v14-review-findings]]):
1. boundary 语义冻结 + 源码文档一致 ✅ (Day 1-2 已 done)
2. q-front overload synthetic test 被 port-resource cut 剪 (不靠 full no-good)
3. power no-cover test ghost-conditioned typed cert
4. replay suite 27+ ghost anchors 无 false positive
5. 80-inst 无 UNKNOWN→cut
6. 160-inst cut store < 12GB/worker
7. pattern no-good 平均 core size 受控 + 非主力 cut source
8. 所有 persisted cuts deserialize+validate+attach-scope 通过

## Refs

- [[v14-review-findings]] — GPT pro + Gemini round 12 + round 13 cross-check 完整 verdict
- [[gpt-v13-cut-language-thesis]] — cut language 升级方向
- [[cand-c-phase1-go]] — cand C 实测 baseline 数据 (Phase 2 无 memory, 见 git commit history)
- Commits: 976bc10 (D1-2) + 64c5317 (D3-9) + 4da7e30 (D10-12) + 3dd3d63 (D13) + f861ba7 (D14) + 925157e (D15 F1) + 30b0a2d (D16a F6) + 824c9b6 (D16b F7 v1.0) + 75e5f18 (D16c-1 修 5 finding) + 1f1e051 (D16c-2 timeline) + cdfbdcb (D16c-3 Gemini r15) + edecbd7 (D16c-4 PoC)
- Design doc: `docs/research/p3_b_design_v2_20260521/` — state_machine_v2 + cut_lifecycle_v2 v3.1 + red_fixtures/F1-F4 + schema_update_v3 + cut_family_specs/{01, 06, 07} v1.1 + paradigm_death_timeline + cross_check/{round_14, round_15} + poc/{b_core_lifecycle_poc, test, README}
