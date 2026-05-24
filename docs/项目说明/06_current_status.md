# 06 — 现状细则 (Phase 1.1 GO, 2026-05-24 复查补强后)

**当前状态**: Phase 1.1 cut framework 闭环 + 外部 reviewer exit hardening 已落地；2026-05-24 又补了一层 fail-closed 复查修复。结论仍是 Phase 1.1 GO blessed，可进 Phase 1.2。

### 已闭环 (Phase 1.1 GO)
- F1 region_capacity / F2 cutset / F3 port_exposure / F4 component_reach
  validator + oracle + evaluator
- Lifecycle 9 step (generate → minimize → serialize → deserialize → validate →
  attach-scope → evaluate → apply-to-master → replay/regression);
  `canonicalize` 是所有步骤共用的哈希/序列化基础工具, 不单独算业务生命周期步
  - Step 2 minimize defer Phase 1.2 P1.2B-F5 (F5 deletion + QuickXplain)
  - Step 8 apply-to-master defer Phase 1.3 P1.3B (CP-SAT 真集成, P1.3A spike 先验)
- CutStore 6-dim watcher (by_cell / by_group / by_pose / by_commodity /
  by_region / by_ghost), quarantine / hold / on_ghost_rect_changed 状态机
- Replay fail-closed (canonical_rules=None → state.canonical_rules fallback
  → HOLD)
- CutStore.add_cut 默认 `initial_state="held"` (production 必经 replay /
  validator gate 才 active, test fixture 可 bypass)
- on_ghost_rect_changed 默认走 full family validator; test stub 注入需显式
  `unsafe_test_replay_fn=...` + `allow_unsafe_test_replay_fn=True` (exit hardening 2.6)
- F1 GHOST_AGNOSTIC 验 `ghost ∩ R == ∅`; F2/F4 GHOST_AGNOSTIC 直接 reject
- **strict registration gate 默认 ON** (`EXACT_FAMILY_VALIDATOR_STRICT="1"`,
  exit hardening 2.1) — 未知 / 漏注册 family fail-closed
- **source_digest 真 hash** (sha256, exit hardening 2.2) — 含 canonical_rules /
  candidate_placements / mandatory_exact_instances / instance_to_facility_type /
  facility_templates / commodity_demands / commodity_routes. 运行时 cache `__*`
  key 不入 hash. 替代之前 `"poc_source_digest"` 占位
- **ghost_rect tuple 语义锁定** `(x, y, x_span, y_span)` (exit hardening 2.5,
  非方形 fixture `(10,20,3,7)` → `(10,20,13,27)` 转换锁定 — 防 F8 接入时高宽反)
- **F8 mode 锁 geometric** (cert 可引用 power pole group/pose 上下文, lifecycle
  body 不走 literal multiset path — 改 mode 必先改 PROJECT_LOCK)
- **F9 area-only** invariant: generator 只接受 `area_capacity_overflow` witness,
  不接受 `routing_overflow` / `binding_overflow` / `pcr_cut_overflow` (PROJECT_LOCK
  §3A, [Gemini math review verdict 2026-05-23](../research/p3_b_design_v2_20260521/external_review/gemini_math_review_action_plan_20260523.md))
- **2026-05-24 fail-closed 复查补强**:
  - lifecycle: base64 改为 strict decode (`validate=True`), region bitset 拒绝长度不对 / grid 外高位置 1, `Cut.scope` / `Cut.cert` 必须是真对象
  - F1/F2/F3/F4 validator: `bool` 不再被当成 `int`, 字符串数字不再被偷转成数字, 非空 ID / cell / registry schema 更严格
  - F2/F4 evaluator: 遇到 malformed cert 直接 `False`, 不让脏 payload 走成误判

### 测试 / 静态 gate 状态 (2026-05-24 复查后)
- pytest: **188 cuts test pass** (普通模式 + `python -O`; v10 为 181, 本次新增 7 个边界 regression)
- ruff: clean (default config + `--config "lint.per-file-ignores={}"` 都 clean)
- **mypy --strict: pass** (exit hardening 清零 37 typing debt, 现 0 errors)
- vulture: pass (`src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py`; exit hardening 2.4 已删 `evaluate_literal_port_exposure`)
- bandit: 0 issues (exit hardening clean)
- **radon: average A, no D** (2026-05-24 再拆 lifecycle helper 后仍最高 C(15))

### 非阻塞项
- `scripts/b_design_v2_exit_criteria.py`: 1/2/4 PASS；其余 8 项是 Phase 1.2/168h ramp 数据或后续 family 测试尚未生成，因此为 PENDING_PHASE_1，**0 FAIL**。这不是 Phase 1.1 阻塞项。
- full `src/tests` 里的 optional solver 依赖 (highspy / pyscipopt) 不在 cut framework gate；Phase 1.5+ 决定 zmd_deps_v3 是否补 wheel 或继续 skip。

### Audit archive
- `docs/research/p3_b_design_v2_20260521/external_review/`:
  - `gpt_pro_phase1_1_v{1,2,3,4,5,6}_audit_*.md` (11 GPT pro audit, v1-v6 全 NOT GO)
  - `phase1_1_exit_hardening_audit_report_20260523.md` (本次 exit hardening verdict GO)
  - `phase1_1_recheck_20260524/phase1_1_final_recheck_report.md` (2026-05-24 复查补强报告 + 188 pass 验收)
  - `phase1_1_exit_hardening_plan_v2_20260523.md` (原 deliverable plan v2, 内容已 merge 本 dir)
  - `gemini_math_review_action_plan_20260523.md` (Gemini 数学 review meta-review)
  - `gemini_math_review_bundle_20260523/` (checklist + red fixture matrix + CP-SAT notes + F9 morphology caution)
- `docs/research/p3_b_design_v2_20260521/cross_check/`:
  - `gemini_round_{14..35}*.md` (22 Gemini per-commit cross-check)

---

