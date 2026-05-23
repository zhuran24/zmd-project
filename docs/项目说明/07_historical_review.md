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

---

