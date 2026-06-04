# 07 — 历史回顾 (Phase 0 → Step O)

不是天降一份 4 family validator. 是 22+ commit + 11 GPT pro audit + 22
Gemini round 一轮轮调过来的. 看完这段知道为啥某些 invariant 这样设计, 为啥
某些 fix 反复在同一函数加.

### 5.1 Phase 0 (B Design v2 spec + invariants)

22 commit + 26 round Gemini cross-check. 锁定:
- 9 family final list (无 symmetry_lift — round 18 decide)
- cut_lifecycle_v2 v3.2.2 (round 21 exterior_blocks_hash 加)
- 5 fixture frozen (red_fixtures/)
- 8 invariant frozen (PROJECT_LOCK §3A)
- 10 exit criterion (PHASE_1_PLAN.md)

Gemini r26 GO, 不再 Phase 0 layer cross-check. Step 跨 Phase 0 → 1.0.

### 5.2 Phase 1.0 (framework migration)

P1.1 carry PoC b_core_lifecycle_poc.py 14/14 PASS 到 production
`src/cuts/lifecycle.py`. 9 step + Cut/CutScope/BState schema + 6-dim watcher
+ replay store. F1 region_capacity 作 framework reference (其他 F2-F9 stub).

### 5.3 Phase 1.1 P1.5-P1.8 (F1-F4 production validator + oracle)

每 family 实施: validator + evaluator + oracle (F2-F4 oracle stub). F1 P(g)⊆R
strict / F2 partition / F3 cert↔literal / F4 BFS component 各自 spec land
(cut_family_specs/01-04.md).

Gemini r27-29 三轮 cross-check, r29 GO. 但 GO 后立刻 r30 catch 5 critical
gap — 全因 prompt mode 只验 spec↔src 没 push spec↔data (`[[gemini-prompt-audit-mode]]`).

### 5.4 Phase 1.1 Gap fixing (r30-r32)

Gemini audit mode 改 prompt: 真数据 inline + armor + 反 GO 章. r30-r32 三轮
catch 15 gap:
- Gap 6 union region (left ∪ bottom)
- Gap 7-8 cells_per_pose / placement_rule helper lookup
- Gap 9 direction N/S/E/W 真数据 vs spec up/down 漂移
- Gap 10 PoseId = str 替 int
- Gap 11 direction offset N=(0,-1) vs (-1,0)
- Gap 12 GroupState.selected_poses 类型 List[PoseId] 跟 spec align
- Gap 13 cut_family_specs/01 fixture drift
- Gap 14 find_pose O(N) → O(1) cache
- (5 个 high-risk follow-up 进 #239)

### 5.5 GPT pro round 1+2 (Phase 1.1 v1 audit)

大节点打包给 GPT pro. r1+r2 一致 NOT GO + 4 P0 + 7 必修. 引出 Step A-H 8
commit (3d35a62 → e5c41b9):
- A `python -O` 防线 (assert → explicit if)
- B F3 cert ↔ literal multiset 绑定
- C F2 partition enclosure + cut_edges canonical
- D F4 cert.bitset == BFS 严等
- E F1 P(g)⊆R strict (核心数学层)
- F F1 evaluate 真重算 (Gemini r33 P0)
- G lru_cache(256) + F4 commodity_id spec align (Gemini r34)
- H Phase 1.3 perf opt TODO + Gemini r33-35 archive

期间 Gemini r33-r35 catch 4 升级 P0/High 全在 Step F/G 修.

### 5.6 GPT pro v2 audit + Step I/J/K (bdaa303)

v2 r1+r2 catch 3 新 P0:
- I `step_7_evaluate_cut` 接 family dispatch (Step F family 函数永远 bypass)
- J F3 blocking_slot → selected_poses[slot] → blocking_pose_id 真绑定
- K F4 separator_cells in-grid + ∈ owner∪ghost 显式验

### 5.7 GPT pro v3 audit + Step L (a38620c)

v3 catch F1 duplicate `contributing_groups` P0: cert 同 group 重复列让
demand_R 双算. Step L 加 seen_gids 去重 + tuple demand 真等 + gap consistency.
顺手清 ruff F401 12 个 (但因 ruff.toml ignore 没真清, Step M 才真清).

### 5.8 GPT pro v4 audit + Step M (273fbff)

v4 r1+r2 catch 3 新 critical:
- M.1 `replay_cut(canonical_rules=None)` silent ATTACH 绕 validator → fail-closed
  (state.canonical_rules fallback → 没就 HOLD)
- M.2 F2 commodity_demand 无 source-of-truth registry → BState 加
  commodity_demands 字段, validator require
- M.3 F4 commodity_id pass-through → BState 加 commodity_routes 字段,
  validator require registry route src/sink == cert
- ruff F401 force-fix 真清

### 5.9 GPT pro v5 audit + Step N (afef8f1)

v5 r1+r2 catch 2 新 P0:
- N.1 F2 commodity registry 仍不 sound — duplicate contributing + same-side
  route 不跨 partition 全允过 → contributing 去重 + commodity_routes require +
  cross-partition route check
- N.2 `CutStore.add_cut` 直接 active 注册 silent attach window → default
  `initial_state="held"`, caller (replay 成功) 必显式 reactivate

### 5.10 GPT pro v6 audit + Step O (c8fb7ef)

v6 r1+r2 catch 3 新 P0, 同一 ghost lifecycle 漏口两端:
- O.1 (round 2) validator 不验 `scope.ghost_rect_id == GHOST_AGNOSTIC` 合法性
  → F1 验 `ghost ∩ R == ∅`, F2/F4 直接 reject GHOST_AGNOSTIC
- O.2 (round 1) `on_ghost_rect_changed` accept scope-only replay_fn 绕 family
  validator → `replay_fn` 改 Optional, default lazy import `replay_cut` 走
  full gate
- O.3 (round 1) add_cut 非法 `initial_state` raise 后 cut 残留 store →
  validate 移到所有 mutation 前

### 5.11 累积现状 (Step O 结束)

- 14 commit src/ 改动 (Step A-O)
- 5 commit infra (build script v2-v7)
- 11 GPT pro audit (v1 r1/r2 + v2 r1/r2 + v3 + v4 r1/r2 + v5 r1/r2 + v6 r1/r2)
- 22 Gemini round (r14-r35)
- 172 cuts test (从 v1 包的 139 累计 +33 regression)
- 8 高位 invariant 全 close (没 unsolved P0)

### 5.12 Phase 1.1 exit hardening (2026-05-23, 外部 reviewer delivery)

继 Step A-O 之后, 外部 reviewer (GPT pro batch audit + v8 全项目 7z 包) 给完整 exit hardening delivery (内含 audit report + plan v2 + 26 file patch + 8 gate output).

修了 8 项 (其中 7 项是 plan §10 入门 7 项, 1 项新发现):
- 1. strict gate 默认 `"0"` → `"1"`
- 2. source_digest 占位 → 真 sha256 (含 7 类 source data, 排除 `__*` cache key)
- 3. validator 拆 helper, radon D → 最高 C(15)
- 4. F3 删 `evaluate_literal_port_exposure` (vulture catch unused)
- 5. ghost_rect tuple 锁定 `(x, y, x_span, y_span)` + 非方形 fixture
- 6. **新发现**: `on_ghost_rect_changed` 改 `unsafe_test_replay_fn` + `allow_unsafe_test_replay_fn` 双 flag (防生产误用 stub 绕 family validator)
- 7. mypy strict 37 errors → 0
- 8. spec drift 全清 (state_machine v2 `PoseId=str`; cut_lifecycle v2 family list 删 `symmetry_lift` 加 F8/F9; 03 direction N/S/E/W; 02/04 commodity registry semantic)

测试 / gate 验收 (exit hardening delivery 含):
- pytest cuts: 172 → 181 pass (+6 regression cover ghost_rect / source_digest / unsafe stub)
- python -O cuts: 181 pass
- ruff default + no-ignores: pass
- mypy --strict --explicit-package-bases src/cuts/: pass
- bandit: 0 issues
- radon: average A, no D
- vulture (w/ whitelist): pass

**Verdict**: Phase 1.1 GO. 进 Phase 1.2 必先做 P1.2A entry (已大部分完成) → P1.2B-F5/F6/F7/F8/F9 (按 v2 plan 顺序).

### 5.13 Gemini math review meta-audit (2026-05-23)

同时另一份 deliverable: 外部 reviewer 评估 Gemini 数学 review 建议的 meta-review (action plan + 11 red fixture matrix + acceptance checklist + CP-SAT integration notes + F9 morphology caution).

3 个 "降温" 修正 (Gemini 大方向对, 但表述过满 / 方法不可用):
- **F5 不能扛 132 集群** (orbit-aware lift Gemini 说太满) — F5 是 fallback 不是主力, F9 才是主解, F5 ratio > 50% = stop-ship
- **F9 不能 routing/binding overflow → density** (PROJECT_LOCK 锁: F9 only `area_capacity_overflow`)
- **CP-SAT 当前不支持 `AddLazyConstraint`** (OR-Tools 9.15 没此 API) — 必须 LBBD 外循环 `solve → verify → generate cut → rebuild/resolve`

5 P0 (per acceptance checklist):
- P0-A: F5 fallback bounded core minimizer + last-verified-core
- P0-B: F9 area-only (拒 routing/binding overflow witness)
- P0-C: Step 8 apply-to-master 不能再悬空
- P0-D: F2/F4 generator 不能长期 stub (BFS 容量 0 是 F4 特例, 容量不足是 F2 min-cut)
- P0-E: unknown infeasible / dark matter telemetry (jsonl)

详 [Phase 1.2 P0 acceptance checklist](12_go_criteria.md) + [11 red fixture matrix](15_workflow_testing.md).

---

## 5.14 Phase 1.2 历史 (摘要, 2026-06-04 补)

本「历史回顾」此前止于 2026-05-23 Phase 1.1 exit hardening，缺整个 Phase 1.2。摘要补齐（详细 living 记录在 CC memory `phase-1-2-progress` / handoff + `docs/research/` 归档，仓库外为权威）：

- **cut-family close (F5–F9)**：F5 pattern_nogood / F6 shape_packing_hall / F2·F4 / F7 power_hitting_set / F8 power_grid_reach / F9 density_envelope 各经多轮 Gemini per-commit cross-check（F8 最严 5 轮 12 finding）。
- **F3 special-case phase**：F3 port_exposure generator 落地（commit `c768806`，oracle 277→344 行，`EXACT_F3_GENERATOR_ENABLED` gated）。
- **外审 v14→v28**（非早期"八轮收口"）：GPT pro 多轮外审 + 内部多镜头对抗审查。**v28 catch 4 个真 soundness 洞**（F5 slot-collision / F9 量词倒置 / F6 region_demand / F7F8 footprint），全修；**F9 = tight-K quarantine 实质停用**（见 PROJECT_LOCK §3A）。
- **数字单一来源 (Design A) + 共享 canonical SoT (Design B)** 工装落地（核心节点 `authoritative_numbers.json` + drift-test + `canonical_sot` helper + meta-test）。
- **close 门禁**：大节点 **≥3 次连续独立审查零问题**；v28 找洞后计数器重置、**尚未达标**（spike close 闭关进行中）。

---

