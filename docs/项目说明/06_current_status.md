# 06 — 现状细则 (commit `c8fb7ef` 起算)

### 已闭环
- F1 region_capacity / F2 cutset / F3 port_exposure / F4 component_reach
  validator + oracle + evaluator
- Lifecycle 9 step (gen / minimize / serialize / deserialize / validate /
  attach-scope check / evaluate / apply-to-master / replay)
  - Step 2 minimize defer Phase 1.2 P1.11 (F5 deletion + QuickXplain)
  - Step 8 apply-to-master defer Phase 1.3 P1.21 (CP-SAT 真集成)
- CutStore 6-dim watcher (by_cell / by_group / by_pose / by_commodity /
  by_region / by_ghost), quarantine / hold / on_ghost_rect_changed 状态机
- Replay fail-closed (canonical_rules=None → state.canonical_rules fallback
  → HOLD)
- CutStore.add_cut 默认 `initial_state="held"` (production 必经 replay /
  validator gate 才 active, test fixture 可 bypass)
- on_ghost_rect_changed 默认 lazy import replay_cut 走 full family validator
- F1 GHOST_AGNOSTIC 验 `ghost ∩ R == ∅`; F2/F4 GHOST_AGNOSTIC 直接 reject

### 测试 / 静态 gate 状态
- pytest: 172 cuts test pass (普通模式 + `python -O` 防线 regression)
- ruff: clean (default config + `--config "lint.per-file-ignores={}"` 都 clean)
- mypy --strict: 37 errors (typing hygiene, 非 runtime fatal — Dict/Callable
  缺泛型 + Any return + unused ignore)
- vulture: `evaluate_literal_port_exposure` 仍标 unused (走 generic multiset path)
- bandit: 5 Low B101 assert (lifecycle/replay 内部, validator 入口已改 explicit guard)
- radon: average A; `validate_cutset` D(27), `validate_component_reach` D(24),
  `validate_port_exposure` D(23) — 5 轮 audit 反复加 binding 后升级, P1 拆 helper

### Audit archive (包内 ship)
- `external_review/gpt_pro_phase1_1_v{1,2,3,4,5,6}_audit_*.md` (11 GPT pro audit)
- `cross_check/gemini_round_{14..35}*.md` (22 Gemini cross-check)
- `PHASE_POST_1_1_REFACTOR_PLAN.md` (本文件)

---

