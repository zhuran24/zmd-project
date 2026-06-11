# 06 — 现状细则 (Phase 1.2 spike close 闭关中)

> **现状权威源**: 项目「当前 phase/状态」的 living 权威源 = `CLAUDE.md`（Current Phase 段）+ CC memory handoff（仓库外）。本文以下 Phase 1.1 段落是**已完成的历史里程碑**, 不是当前状态。

**当前状态 (2026-06-11)**: **Phase 1.2 spike close 闭关中**（cut-family / certified lifecycle evidence soundness 审查）。P1.2 仍未正式收口；V50 已将 phase close gate 简化为人工计数模型，三次连续 clean full review 仍是 owner 标准，但 clean 计数由 owner 在 repo 外维护，仓库不再从 JSON receipt、Markdown/HTML/XML 报告 metadata、source-tree manifest、package metadata 或包内 Git authority 自动推导 P1.3B ready。V57-V96 之后，当前审查锚点是 `v96_symlink_ancestor_boundary_sealing`：certified lifecycle evidence 现在拆成 proof obligation compartments，覆盖 exact-safe cut replay（persisted exact_safe_cuts 只是 telemetry，certified 不消费为 proof object）、certified master-domain / power-witness representation（time-budget 打断的 partial precheck group 不得当完整 infeasibility 证明消费）、replayable full-frontier terminal evidence（candidate 域全有向枚举 (w,h)/(h,w)、candidate-domain 切片轴封闭、canonical min_side admissibility 绑定、unknown evidence key 拒绝）、delivery-manifest writer disk authority、canonical certified manifest publication、certified export surface（single-base release 路径拒绝 run summary 自称 CERTIFIED），以及 certified `EXACT_*` env allowlist。当前 repo 默认 fail-closed；只有显式 owner manual decision 才能打开 **P1.3B PoseBoolExactMaster LBBD master integration**。其中 **F9 = tight-K quarantine（实质停用，见下方 F9 条 + PROJECT_LOCK §3A）**。

---

## (历史里程碑) Phase 1.1 GO, 2026-05-24 final polish 后

> 以下为 Phase 1.1 闭环时的现状细则, 保留作历史记录。当前状态见上方。

**(历史) Phase 1.1 结论**: Phase 1.1 cut framework 闭环 + 外部 reviewer exit hardening 已落地；2026-05-24 又补了 fail-closed 复查修复与 final polish。结论是 Phase 1.1 GO blessed，可进 Phase 1.2。

### 已闭环 (Phase 1.1 GO)
- F1 region_capacity / F2 cutset / F3 port_exposure / F4 component_reach:
  Phase 1.1 闭环的是 **validator + evaluator** (F1 oracle/generator 同期)。
  **注意 oracle/generator 不是 Phase 1.1 同期全闭环**: F2/F4 generator 在 Phase 1.2
  才落地; F3 port_exposure oracle 在 Phase 1.1 是 `return []` stub (GPT pro v15 三审
  catch 的 G10 fixture coverage 真 gap), 直到 Phase 1.2 之后的 F3 special-case phase
  (commit `c768806`, oracle 277→344 行) 才实现, 现 `EXACT_F3_GENERATOR_ENABLED` gated
  default-disabled。见 [[phase-1-2-progress]]。
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
  - **⚠️ (2026-06-04) F9 tight-K quarantine（实质停用）**: v28 外审后 validator 对
    `max_allowed_area = K < safe_ub` fail-closed 拒（cert 不携带 replayable tight-bound
    proof）→ F9 只剩 `K == safe_ub` 的平凡 cut, **整族实质停用**（reverses Gemini
    round-4 oracle-trust deferral；解封须 P1.5+ 给 cert 加 area-capacity proof-carrying
    字段）。**故本文/计划文档里把 F9 当"主力几何 lift / 主解"的措辞已不成立**。见 PROJECT_LOCK §3A。
- **2026-05-24 fail-closed 复查补强**:
  - lifecycle: base64 改为 strict decode (`validate=True`), region bitset 拒绝长度不对 / grid 外高位置 1, `Cut.scope` / `Cut.cert` 必须是真对象
  - F1/F2/F3/F4 validator: `bool` 不再被当成 `int`, 字符串数字不再被偷转成数字, 非空 ID / cell / registry schema 更严格
  - F2/F4 evaluator: 遇到 malformed cert 直接 `False`, 不让脏 payload 走成误判
  - F3 `port_exposure`: cert cell 统一强制在 70×70 board 内，out-of-grid 直接 `schema_err`

### 测试 / 静态 gate 状态 (2026-05-24 复查后)
- pytest: **189 cuts test pass** (普通模式 + `python -O`; v11 为 188，本次新增 F3 out-of-grid cell regression)
- ruff: clean (default config + `--config "lint.per-file-ignores={}"` 都 clean)
- **mypy --strict: pass** (exit hardening 清零 37 typing debt, 现 0 errors)
- vulture: pass (`src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py`; exit hardening 2.4 已删 `evaluate_literal_port_exposure`)
- bandit: 0 issues (exit hardening clean)
- **radon: average A, no D** (2026-05-24 再拆 lifecycle helper 后仍最高 C(15))

### 非阻塞项
- `scripts/b_design_v2_exit_criteria.py`: 1/2/4 PASS；其余 8 项是 Phase 1.2/168h ramp 数据或后续 family 测试尚未生成，因此为 PENDING_PHASE_1，**0 FAIL**。这不是 Phase 1.1 阻塞项。
- full `src/tests` 里的 optional solver 依赖 (highspy / pyscipopt) 不在 cut framework gate；Phase 1.5+ 决定 zmd_deps_v3 是否补 wheel 或继续 skip。

### Sound ≠ converge 警句 (2026-05-24 GPT pro P1.2 in-progress review)

外部 reviewer (GPT pro, P1.2 in-progress audit) 提醒: Phase 1.1 闭环证明的是
**cut framework sound**, 不是 **168h 必收敛**. sound 意思是 "剪掉的东西确实
不可能是解". 收敛还需另外两件事:
- cut 提取得**够多够快够便宜**: F5 core 不能太大, F9 envelope 不能 trivial,
  F2/F4 generator 要产 enough useful cut, cut 加多后 CP-SAT propagation 不能
  显著变慢, 168h 内 cut 复用率得够.
- shadow telemetry 验证: 每个 family attach 前先 shadow, 记录"如果 attach 会
  剪掉什么 / 剪掉的解是不是合法 / cut 复用率多高", shadow 数据过关再 true attach.

所以现 plan / cut spec / lock 文档**任何"唯一可走 paradigm" / "最终数学工具"
类措辞应降温**为: "**目前证据下最值得继续推进的主线**; 收敛性仍需 Phase 1.2 /
1.3 / ramp 数据确认". 见 [[gpt-pro-p1-2-in-progress-review]] memory 9 条
verdict.

### Audit archive
- `docs/research/p3_b_design_v2_20260521/external_review/`:
  - `gpt_pro_phase1_1_v{1,2,3,4,5,6}_audit_*.md` (11 GPT pro audit, v1-v6 全 NOT GO)
  - `phase1_1_exit_hardening_audit_report_20260523.md` (本次 exit hardening verdict GO)
  - `phase1_1_recheck_20260524/phase1_1_final_recheck_report.md` (2026-05-24 复查补强报告 + 188 pass 验收)
  - `phase1_1_final_polish_20260524/phase1_1_final_polish_report.md` (v12 final polish + 189 pass 验收)
  - `phase1_1_exit_hardening_plan_v2_20260523.md` (原 deliverable plan v2, 内容已 merge 本 dir)
  - `gemini_math_review_action_plan_20260523.md` (Gemini 数学 review meta-review)
  - `gemini_math_review_bundle_20260523/` (checklist + red fixture matrix + CP-SAT notes + F9 morphology caution)
- `docs/research/p3_b_design_v2_20260521/cross_check/`:
  - `gemini_round_{14..35}*.md` (22 Gemini per-commit cross-check)

---
