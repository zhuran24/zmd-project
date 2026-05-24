# 15 — 测试 strategy + fixture 清单

当前 189 cuts test 不是平铺, 按目标分 4 层. 本节定层 + 各层覆盖哪些 family + fixture 清单 + Phase 1.2 加 F5-F9 时怎么扩展.

### 21.1 测试 4 层

| 层 | 目标 | 文件 | 数量 |
|---|---|---|---|
| **Unit** | 单 function/class 行为 (helpers / store / lifecycle 各 step 各分支) | `test_store.py` / `test_lifecycle.py` / `test_helpers_*.py` / `test_assumptions_verifiers.py` | ~80+ test |
| **Family** | 单 family validator + evaluator + oracle 端到端 (per family schema + 真数据反例) | `test_family_{region_capacity,cutset,port_exposure,component_reach}.py` | ~90+ test |
| **Integration** | replay flow / on_ghost_rect_changed / add_cut 多 family 串 (跨 family interaction) | `test_replay.py` + 部分 `test_lifecycle.py` | ~15+ test |
| **Adversarial** | 假 cert / cert↔literal 不绑 / GHOST_AGNOSTIC 非法 / canonical_rules=None bypass / out-of-grid cell 等 | 散在各 `test_family_*.py` (e.g. test_*_p_g_outside_R / test_*_ghost_agnostic_rejected) | ~10+ test |

具体 count 以 `pytest --collect-only -q src/tests/cuts/` 为准.

### 21.2 helper / fixture 当前组织

- **无 conftest.py / 无独立 fixture file** — 各 test 文件内 inline `_make_state` / `_make_<family>_cut` helper, 按 family 独立
- 主要 helper:
  - `test_family_component_reach.py::_make_state` + `_make_component_reach_cut`
  - `test_family_cutset.py::_make_enclosed_state` + `_make_cutset_cut`
  - `test_family_port_exposure.py::_make_state` + `_make_port_exposure_cert` + `_make_port_exposure_cut`
  - `test_family_region_capacity.py::_make_state`
  - `test_replay.py::_make_state` + `_make_f1_cut`
  - `test_store.py::_make_state` + `_make_cut`
  - `test_lifecycle.py::make_state_with_crusher_on_left_baseline` + `make_clean_state`
- 政策: Phase 1.2 加 F5-F9 时新 family test 沿用 inline helper 模式, **不**抽 conftest.py (避免跨 family 共享状态意外耦合, adversarial 测试主战场要的就是各 family 独立反例)

### 21.3 red fixture 清单 (docs/research/.../red_fixtures/)

`docs/research/p3_b_design_v2_20260521/red_fixtures/` 5 个 known-infeasibility 反例 (schema-level, 跑 evaluate_cut_as_multiset 验拦截):

| ID | 文件 | 反例几何 | 应拦 family | 来源 |
|---|---|---|---|---|
| **F1** | `F1_boundary_saturation.md` | 138 left+bottom cells 必 100% 铺满, 缺格 → INFEASIBLE | F1 region_capacity + F3 port_exposure | v14 review boundary correction (commit 976bc10) |
| **F2** | `F2_shape_packing_hall.md` | 长度 10 boundary 被 ghost 切 [1-4]+[6-10], 9 cell ≥ demand 9 pass capacity 但 length-3 `⌊4/3⌋+⌊5/3⌋=2<3` infeasible | F1 + F6 shape_packing_hall (Phase 1.2 P1.2B-F6) | Gemini 反例 B |
| **F3** | `F3_power_no_cover.md` | pose p 在 G1 ghost 下无 power_pole 候选覆盖 → INFEASIBLE | F1 region_capacity + F7 power_hitting_set (Phase 1.2 P1.2B-F7) | GPT 反例 power_cover + L16 lazy power |
| **F4** | `F4_ghost_scoped_replay.md` | G1 学 cut `not(A=pA ∧ B=pB)`; G2 移挡后 A=pA∧B=pB 合法 → 旧 pose-id-only replay 误剪 | F5 pattern_nogood (Phase 1.2 P1.2B-F5) + scope-aware replay HOLD | cut_lifecycle_v2 §4 walk-through |
| **F5** | `F5_power_grid_disconnect.md` | power network 断连, source → sink 4-conn 不连通 → INFEASIBLE | F8 power_grid_reach (Phase 1.2 P1.2B-F8) | GPT power cover ext |

每 fixture .md 文件结构: 反例几何 + MasterStateV2 表达 + 期待结果 + Hardcode cut object + evaluate 期望.

Phase 1.2 加 F5-F9 时按 §11 各 family 步骤每加 1 family 至少 1 red fixture (含反例几何 + cert + literal binding).

### 21.4 测试 strategy by phase

**Phase 1.2 入门 (§10, 7 项 factual fix)**
- 不加新 family, 强 strict gate / spec align / source_digest 真 hash
- test 要求: §10.1 strict gate 加 regression (未注册 family OFF→fail-closed)
- §10.4 ghost_rect tuple 改 object 加非方形 fixture e.g. `(10, 20, 3, 7)`

**Phase 1.2 P1.2B-F5/F6/F7/F8/F9 (§11, 5 family)**
- 每 family 至少: 1 unit (helper) + 3 family (validator schema + cert binding + evaluator 真重算) + 1 adversarial (假 cert) + 1 red fixture 拦
- F5 deletion + QuickXplain test 单独 (复杂, 加 minimize step)
- F6 Hall theorem 加 4-5 反例 (interval graph 各类)
- F7 set cover 加 LP relax 边界 + ln(n) approximation 上限
- F8 Liang-Barsky AABB 加非方形 + 正交 + 退化 (零长度) 反例
- F9 density envelope 加 baseline `cap/area=1.0` 边界

**Phase 1.3 (§12, propagator 真集成)**
- 加 integration test: master.AddLinear mock + cut store apply_to_master + cp_sat propagator round-trip
- 加 perf test: step_7 / replay latency p95 < §20.2 阈值
- 加 telemetry test: jsonl schema validate (§20.3)

**Phase 1.5+ (§13, production integration)**
- 接 real benders_loop, 加端到端 24h shadow trial (test 不跑, 是 trial)
- regression: 历史 168h baseline outcome (UNPROVEN candidate 列表) 不退化

### 21.5 viewer sample vs production 全集

cut framework 测试用 **viewer sample** (~273 pose, BSP=54), production 168h 用 **全集** (~81795 pose, BSP=134). Sample 是单测 + 反例 reproduce 用 (上传 review pkg 时也是 sample, 大小 < 1 MB), 全集仅生产 trial 用 (53 MB).

差异:
- sample F1 14 outside-pose 反例数字 (GPT v3 cite) 来自 viewer sample, **production 全集 outside count 不同**
- adversarial 反例若 cite 具体 pose_id, 测试 fixture 必显式声明 sample-only, 不假定全集 reproduce

review pkg 默认 ship 全集 (53 MB), README 提醒 reviewer 反例数字 vs sample 关系 (build_v8 script 已加).

### 21.6 静态 gate (lint / type / dead code / security / complexity)

随测试一起 enforce, 不只 `pytest` pass:

| 工具 | 当前 strict | Phase 1.2 入门 (§10.5/10.6) | 用途 |
|---|---|---|---|
| `ruff check` | clean (default + no-ignores) | 维持 | F401 / import order |
| `mypy --strict` | ✅ pass (0 errors, exit hardening 清零) | 维持 | 类型 hygiene |
| `vulture` | ✅ pass (`src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py`) | 维持 | dead code |
| `bandit` | ✅ 0 issues | 维持 | security |
| `radon cc` | ✅ average A, no D (max C(15), 2026-05-24 复查后仍满足) | 维持 | complexity |

每 commit 必跑 `pytest src/tests/cuts/ -q` + `ruff check src/cuts/`; 大 commit (新 family / 改 step) 必跑全套 5 工具.

---

### 21.7 Phase 1.2 P0 red fixture matrix (Gemini math review meta-audit, 2026-05-23)

11 个 critical fixture, 覆盖 Phase 1.2 P0 acceptance checklist 各项 (cite `external_review/gemini_math_review_bundle_20260523/checklists/RED_FIXTURE_MATRIX.md`):

| Fixture | Purpose | Owner family |
|---|---|---|
| `F5-timeout-last-verified-core` | QX/deletion minimizer timeout 必 sound (返回 last verified, 不是 unverified partial) | F5 |
| `F5-132-group-anonymous` | Slot/index permutation 必触同一 cut (multiset 不绑 instance label) | F5 multiset |
| `F5-cardinality-unsound-routing` | Routing failure 不能 auto-lift 成 cardinality cut (necessary ≠ sufficient) | F5/F9 boundary |
| `F9-reject-routing-overflow` | F9 generator 拒 `routing_overflow` witness, 必走 F5 fallback | F9 |
| `F9-any-overlap-overcount` | 历史 FP: any overlap 算 whole facility, 必拦 | F9 |
| `F9-origin-in-window` | 历史 FP: origin in W 算 whole facility, 必拦 | F9 |
| `F9-all-in-window-FN` | 历史 FN: edge partial 被忽略, 必抓 | F9 |
| `F2-narrow-corridor-capacity` | BFS connected 但 capacity < demand (F2 主战场, F4 拦不住) | F2 |
| `F4-disconnected-zero-capacity` | 完全无 path, F4 在 F2 前触发 (容量 0 特例) | F4 |
| `CP-SAT-no-lazy` | Step 8 用普通 constraint, 不依赖 `AddLazyConstraint` (CP-SAT 9.15 无此 API) | integration |
| `DarkMatter-empty-families` | INFEASIBLE + 所有 family 返空 → 必写 jsonl (telemetry §17.4) | telemetry |

每 fixture 必 land **新 red_fixture .md 文件** + **新 test_family_*.py 测试**. 跟现有 5 red fixture (`docs/research/p3_b_design_v2_20260521/red_fixtures/F1-F5*.md`) 加成 16 fixture.

实施顺序跟 P1.2B family 顺序对齐:
- P1.2B-F5 实施时 land 3 个 F5 fixture
- P1.2B-F9 实施时 land 4 个 F9 fixture (+1 boundary fixture)
- P1.2B-F2 / F4 实施时 land 2 个 F2/F4 fixture
- P1.3A spike 时 land CP-SAT-no-lazy fixture
- P1.3B 集成时 land DarkMatter fixture

---

