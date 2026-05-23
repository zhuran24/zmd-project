# 12 — GO 标准 / 验收准则

每段 done 怎么定义. 不只 "代码改完 commit pass test", 而是要过 reviewer audit.

### 8.1 Phase 1.2 P1.2A 入门 GO (✅ 2026-05-23 exit hardening delivery 落地)

7 项 factual fix + 1 项新发现 全 land (per [Phase 1.1 exit hardening](07_historical_review.md#512-phase-11-exit-hardening-2026-05-23-外部-reviewer-delivery)):
1. ✅ strict gate default ON (`EXACT_FAMILY_VALIDATOR_STRICT="1"`)
2. ✅ spec drift 全清 (PoseId=str / family list 加 F8/F9 删 symmetry_lift / F3 direction N/S/E/W / F2/F4 commodity registry semantic / F1 region_kind / source_digest spec)
3. ✅ source_digest 真 sha256 (含 canonical_rules + candidate_placements + mandatory_exact_instances + facility_templates + commodity_demands + commodity_routes, 排除 `__*` cache)
4. ✅ ghost_rect tuple `(x, y, x_span, y_span)` lock + 非方形 fixture `(10,20,3,7)` → `(10,20,13,27)`
5. ✅ mypy strict 37 → 0
6. ✅ radon D(27)/D(24)/D(23) → max C(15) (helper 拆)
7. ✅ `evaluate_literal_port_exposure` 删除, F3 统一走 `evaluate_literal_multiset`
8. ✅ **新发现**: `on_ghost_rect_changed` test stub 注入收紧 (`unsafe_test_replay_fn` + `allow_unsafe_test_replay_fn` 双 flag)

实际验收 (exit hardening delivery 跑过):
- ✅ pytest cuts: 181 pass (172 → +6 regression for ghost_rect / source_digest / unsafe stub)
- ✅ python -O pytest cuts: 181 pass
- ✅ ruff default + no-ignores: pass
- ✅ mypy --strict --explicit-package-bases src/cuts/: pass
- ✅ bandit: 0 issues
- ✅ radon: average A, no D
- ✅ vulture (whitelist): pass

### 8.1.x Phase 1.2 P1.2B P0 acceptance checklist (from Gemini math review meta-audit)

5 P0 + F (regression gate) — 详 `external_review/gemini_math_review_bundle_20260523/checklists/ACCEPTANCE_CHECKLIST.md`:

**A. F5 bounded fallback**
- [ ] `src/cuts/families/pattern_nogood.py` exists
- [ ] `src/cuts/oracles/pattern_nogood_oracle.py` exists
- [ ] Minimizer 有 `max_calls` + `max_seconds`
- [ ] Timeout 返回 last verified infeasible core, 不返回未验证 partial core
- [ ] Cert 存 `stopped_reason` / `calls` / `size_before` / `size_after` / `last_verified=true`
- [ ] Validator 重跑 subproblem witness 或验独立 oracle cert
- [ ] Evaluator multiset semantics (slot anonymity, 忽略 instance label)
- [ ] Step 8 → `sum(present_lits) <= n-1`
- [ ] 测试覆盖 slot anonymity / duplicate poses / timeout / oracle UNKNOWN / oracle FEASIBLE

**B. F9 area-only density envelope**
- [ ] `src/cuts/families/density_envelope.py` exists
- [ ] Generator reject `routing_overflow` / `binding_overflow` / `pcr_cut_overflow`
- [ ] **Only** `area_capacity_overflow` produce F9
- [ ] Cert 有 `max_allowed_area`
- [ ] Evaluator: `sum(|pose_cells ∩ W|)`, 不是 instance count
- [ ] Validator 同 area-based rule
- [ ] Step 8: linear weighted area overlap coefficient
- [ ] 测试覆盖历史 any-overlap / origin / all-in-window unsound variants

**C. F2/F4 capacity**
- [ ] F4 generator 不再为 disconnected commodity 返 `[]`
- [ ] F2 generator min-cut / max-flow witness (Dinic / node-split)
- [ ] cell-capacity 重要时存 node-split mode
- [ ] Validator 独立重算 cut capacity + demand
- [ ] commodity_id deduplicated + 跟 SoT registry 验

**D. Integration (Step 8)**
- [ ] `step_8_apply_to_master` 实施 F3/F5/F9 (最小集)
- [ ] **没** code path 依赖 `AddLazyConstraint` (CP-SAT 9.15 不支持)
- [ ] Ghost-bound cut 用 `OnlyEnforceIf` 或 per-ghost rebuild
- [ ] `GHOST_AGNOSTIC` cut 仍验 `exterior_blocks_hash`
- [ ] HOLD vs QUARANTINE 在 replay + store 区分

**E. Telemetry**
- [ ] F5 ratio emit
- [ ] F5 core size emit
- [ ] F9/F5 ratio emit
- [ ] unexplained infeasible JSONL 写 (dark matter)
- [ ] psutil RSS per worker emit
- [ ] capacity eviction 留 audit trail

**F. Regression gate**
- [ ] 现有 `src/tests/cuts/` 181 全 green
- [ ] `python -O -m pytest src/tests/cuts/ -q` 181 green
- [ ] 新 red fixture 全 green (详 [15_workflow_testing.md](15_workflow_testing.md))
- [ ] ruff green
- [ ] mypy strict green 或显式标 typing debt (跟 soundness 分开 commit)

报警阈值 (Phase 1.5+ telemetry):
- F5 cut ratio > 50% → stop-ship, 必须补强几何 lift
- F5 median core size > 40 → 需 minimizer 加强 / 更强 family
- F9/F5 ratio 长期 < 0.2 → density lift 没接上
- unexplained infeasible 连续出现 → 人工复盘提炼 F10
- cut_store RSS 逼近 5GB/worker → capacity eviction

### 8.2 Phase 1.2 P1.11-P1.15 (F5-F9 实施) GO

5 family 各自完整:
- validator + evaluator + oracle (oracle 可 stub)
- ≥ 10 unit test (sound + ≥ 3 attack 反例 + schema_err + adversarial scope)
- spec ↔ src ↔ 真数据 三层 align
- 每 family Gemini cross-check 通过
- 跨 family invariant test (e.g. F5 接 lifecycle step 2 minimize, F6 跟 F1 region 重叠 case, F7 跟 F3 port 重叠 case, F8 复用 F4 BFS helper, F9 跟 F6 density)
- F5-F9 全 register FAMILY_VALIDATORS, strict gate ON

验收:
- 总 cuts test ~250+ (172 baseline + 5 family × 10-15 each)
- 大节点 GPT pro batch audit 通过 (整 Phase 1.2 vs 单 family)
- production smoke 真数据 F5-F9 oracle 跑通 (各 oracle 真 emit cut 或合理
  fail-closed)
- 跟 PROJECT_LOCK §3A 不冲突 (family list 仍 9 个, mode 不变)

### 8.3 Phase 1.3 P1.21 (CP-SAT propagator 集成) GO

- step_8_apply_to_master 真接 master CP-SAT (env flag `EXACT_B_DESIGN_V2=1`)
- lazy → hard constraint 转化 sound (cut attach 后 master state 跟 cut violate
  一致)
- 168h smoke (24h 短跑 subset) 真跑 prune 减 search tree (跟 baseline 比节点
  数 / 时间)
- hot path perf 优化:
  - json.loads cache on Cut (避 evaluator 反复 parse)
  - F4 BFS incremental connectivity (替 O(|Grid|) 全图 BFS)
  - by_exterior_watcher 实施 (减 evaluator 调用频次)
- thread-safe 验证 (multiprocess.spawn worker 各 cache 独立 + GIL-safe)

验收:
- 24h smoke 比 Phase 3B repair5 baseline prune ratio improve ≥ 10%
- propagator 10K calls/sec scale evaluator latency ≤ 100 µs / call
- 真 168h campaign 跑通至少 1 个 candidate full search (不只 timeout)
- GPT pro audit Phase 1.3 整 phase 通过

### 8.4 Phase 1.5+ (production integration) GO

- commodity registry production inject 路径 unique builder (一函数从真 data
  build BState)
- 各 family oracle 真实施 (不再 stub `return []`)
- F3 active_port_witness verify
- F2 max_flow_LP algebraic witness
- F4 commodity registry 改 route_id 级别 schema (支持同 commodity 多 route)
- 168h 真 campaign 跑通 + 比 baseline (Phase 3B repair5 without cut framework)
  收敛 ≥ 30%

验收:
- 真 168h campaign 1+ candidate 真 OPTIMAL (不 timeout 不 UNKNOWN)
- GPT pro batch audit Phase 1.5 production GO
- 跟 Phase 3A delivery (r20260416) 衔接验证

---

