# F4 — Ghost-Scoped Replay False Positive (Red Fixture)

> **Status**: Day 17d sweep v3.1 (2026-05-21)
> **Cross-refs**: `../cut_lifecycle_v2.md` v3.2 §4 (6 步 verify 加 blocked_cells_hash) + §5 multiset + `../cut_family_specs/05_pattern_nogood.md` v1.0
> **Cut family owner**: Family 5 pattern_nogood + scope-aware replay HOLD path

## Day 17d sweep changelog

原 §6 [SCHEMA_GAP] 全解:
- ✅ ghost_rect_id canonical hash 算法 → v3 `compute_ghost_rect_id` (cut_lifecycle §4) sha256(f"{x},{y},{h},{w}")[:16]
- ✅ HOLD cut disk 占用 → Phase 1 quota 政策 (cut_lifecycle §8 quarantine 政策)
- ✅ HOLD ↔ candidate enumeration → v3.2 by_ghost_watcher (Day 17d §7) ghost change 触发 hold/active 切换
- ✅ Regression sweep scope-aware → cut_lifecycle §4 6 步 verify 含 ghost_rect_id + blocked_cells_hash 双校验
- ✅ Replay 反例完整 walk-through → cut_lifecycle §4 §5 反例数学 + PoC test_attach_scope_ghost_agnostic 验证

### Day 17f sweep — F8/F9 静默说明 (Gemini round 17 A4)

F4 反例 (ghost-scoped replay false positive — G1 学的 cut 在 G2 误剪):
- **F8 power_grid_reach**: 静默. F4 是 scope-aware replay 机制问题, 不是 power 几何反例.
- **F9 density_envelope**: 静默. F4 不涉 density / cluster.
- F4 owner: Family 5 pattern_nogood + cut_lifecycle scope-aware HOLD path (任 family 都受 v3.1 6 步 verify 保护).

## 1. 反例几何 (cut_lifecycle_v2 §4 walk-through)

**两个 candidate 切换 ghost 暴露 v14 pose-id-only replay bug.**

### G1 ghost candidate

- ghost rectangle: 比如 (x=10..25, y=10..25) 16×16 ghost
- 该 ghost 切断 A facility ↔ B facility 间的 belt path
- master OPTIMAL 给一个 placement: `crusher_blue_iron[slot=0] = pA`,
  `shop_blue_iron[slot=0] = pB`
- routing oracle (PCR-CUT) 在 G1 下跑: A→B routing **INFEASIBLE** (ghost 挡)
- 学 cut: `not(crusher_blue_iron[slot=0] = pA ∧ shop_blue_iron[slot=0] = pB)`
- cut scope: `ghost_rect_id = G1_canonical_hash`

### G2 ghost candidate (移开此挡)

- ghost rectangle: 比如 (x=40..55, y=40..55) 不挡 A↔B path
- 同 placement `(pA, pB)` 在 G2 下 routing **FEASIBLE**
- 但 v14 replay 算法只查 `pA ∈ pose_domain[crusher_blue_iron]` +
  `pB ∈ pose_domain[shop_blue_iron]` → both true → attach cut →
  **误剪合法解** `(pA, pB)`

## 2. MasterStateV2 表达 (skeleton)

```python
state_G2 = MasterStateV2(
    groups={
        "crusher_blue_iron": GroupState(
            ...,
            selected_poses=[("crusher_blue_iron", pA), ...],
        ),
        "shop_blue_iron": GroupState(
            ...,
            selected_poses=[("shop_blue_iron", pB), ...],
        ),
    },
    ghost_rect=Rect(x=40, y=40, h=16, w=16),  # G2 ghost
    ghost_cells=compute_ghost_cells(Rect(40, 40, 16, 16)),
    ...
)
```

## 3. Hardcode cut object (from G1 generation, replay 在 G2)

```python
F4_cut_from_G1 = Cut(
    cut_id="F4-pattern-nogood-G1",
    family="pattern_nogood",
    literals=(
        CutLiteral(AnonymousSlotRef("crusher_blue_iron", 0), pose_id=pA),
        CutLiteral(AnonymousSlotRef("shop_blue_iron", 0), pose_id=pB),
    ),
    scope=CutScope(
        ghost_rect_id="<G1 canonical hash>",   # ← 关键: scope 绑 G1
        blocked_cells_hash="<G1 ghost ∪ exterior block hash>",
        source_digest="...",
        artifact_hashes={...},
        oracle_abstraction_version="pcr_cut_v1",
        active_assumptions=(
            Assumption(key="g1_blocks_AB_path",
                       value="ghost_rect=(10,10,16,16),blocks_cells_between_A_B=23"),
        ),
    ),
    cert=OracleCert(
        cert_kind="pcr_cut_routing_core",
        cert_payload=canonical_bytes({
            "anchor_patch": [...],            # PCR-CUT patch core
            "infeasibility_witness": "min-cut size=0 between A and B",
        }),
        cert_hash="<sha256>",
    ),
    ...
)
```

## 4. 期待 replay 路径

按 `cut_lifecycle_v2.md` §4 replay 算法:

```python
# 在 G2 candidate 上 replay F4_cut_from_G1
result = replay_cut(F4_cut_from_G1, state_G2, store)

# 推理:
# Step 1: source_digest 比对 → match (同 session)
# Step 2: ghost_rect_id 比对 → G1_hash != G2_hash → return AttachDecision.HOLD
# (HOLD 不 quarantine, 留作 G1 ghost candidate 再 attach)

assert result == AttachDecision.HOLD
```

v14 行为对比 (bug):
```python
# v14 没 scope check, 只查 pose_domain:
# pA ∈ pose_domain[crusher_blue_iron] → True
# pB ∈ pose_domain[shop_blue_iron] → True
# attach! → 误剪 G2 下合法 (pA, pB)
```

## 5. `evaluate_cut_as_multiset` 在 G2 state 上 (假设 attach 强行成功)

```python
# 假设 bug-mode: 跳过 scope check 直接 attach
result = evaluate_cut_as_multiset(F4_cut_from_G1, state_G2)

# cut_demand_by_group = {
#   "crusher_blue_iron": Counter({pA: 1}),
#   "shop_blue_iron": Counter({pB: 1}),
# }
# state_by_group_G2 = {
#   "crusher_blue_iron": Counter({pA: 1, ...}),
#   "shop_blue_iron": Counter({pB: 1, ...}),
# }
# Both Counter ≤ Counter → True (violate, cut 拒 placement)
assert result == True   # ← 这就是 v14 bug 的 false positive 表现

# v2 正确路径: replay step 2 HOLD, evaluate_cut_as_multiset 根本不被调用
```

## 6. Schema cross-check

| 检查 | 状态 |
|---|---|
| `CutScope.ghost_rect_id` carry G1 hash | ✅ |
| `replay_cut` step 2 用 `state.candidate.ghost_rect_id` 比对 | ✅ §4 algorithm 行 |
| `AttachDecision.HOLD` 不删 cut | ✅ §4 注释 |
| Pose-id-only false positive **不发生** | ✅ §4 step 2 拦截 |
| ghost_rect_id 是 canonical hash 还是 candidate.id? | ⚠️ [SCHEMA_GAP] §4 用 `cut.scope.ghost_rect_id != state.candidate.ghost_rect_id` — `candidate.ghost_rect_id` 怎么算? 用 `Rect(x,y,h,w)` canonical bytes hash 还是 candidate enum index? Day 18-21 集成时定 |
| F4 cut 在 G1 重新出现的 candidate 上 attach 路径完整? | ⚠️ replay step 2 match → step 3-5 全 pass → attach. 但 active_assumptions "g1_blocks_AB_path" 在 G1 always hold (同 ghost 不变) → ✅ |

## 7. Open questions

1. **`ghost_rect_id` canonical hash 算法**: Rect `(x, y, h, w)` 四元组按
   `f"{x},{y},{h},{w}".encode()` sha256? 还是含 `blocked_cells_hash`? Day 18-21 定.
2. **HOLD cut disk 占用**: 168h campaign 内大量 HOLD cut (跨 candidate 不 match
   累积) → cut store 可能上 GB. cut_lifecycle_v2 §10 open question 2 已列, defer Phase 1.
3. **HOLD ↔ candidate enumeration order 关系**: 若 candidate enumeration 是
   max_lex(area, min_side) 降序, G1 大 candidate 先跑, G2 小 candidate 后跑.
   G1 → G2 → G3 切换时, G1 cut 在 G2 HOLD, G3 若再用 G1 ghost 应 re-attach.
   replay_cut 每 candidate 启动时 sweep? 增量? Phase 1 定.
4. **Regression sweep (Step 9) 在 G2 上验 G1 cut 怎么算 "sound"**? 在 G2
   state 上跑 F4 cut → 若 evaluate 返 True 说明 cut 违反 G2, 但 cut 不应
   apply on G2 (scope mismatch). 应不视为 unsound, 只是 scope 不 match → HOLD.
   Regression 跑 dry-run validate 应该 scope-aware (用 cut.scope 而不是
   current state). Day 18-21 集成定.

## 8. 验收 status (Day 11)

- ⏸ 待 Day 11 填 full state setup + G1/G2 ghost concrete coordinates
- ✅ replay HOLD 路径表达完整
- ✅ v14 bug walk-through 已记 (与 cut_lifecycle_v2 §4 一致)
- ⚠️ 2 个 [SCHEMA_GAP]: ghost_rect_id hash 算法 + HOLD cut disk 政策
- ✅ 跟 cut_lifecycle_v2 §4 §5 contract 一致 (无 schema-mismatch)
