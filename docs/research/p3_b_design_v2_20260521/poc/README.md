# B core PoC — Day 16c-4 (补做 prep 项 3)

> **Status**: 14/14 PASS (2026-05-21)
> **Why**: 上次 prep 清单项 3 (B core 数据结构 PoC) 没做. Schema-first 不
> retrofit. 防 [[feedback_proof_object_lifecycle]] v4 replay bug 教训 — "schema
> landed ≠ runtime correct".

## Scope

`b_core_lifecycle_poc.py` 实现 cut object lifecycle 9 步 (per cut_lifecycle_v2
v3.1 §2) on Family 1 region_capacity (per cut_family_specs/01 v1.1):

| Step | Function | 实施 |
|---|---|---|
| 0 canonicalize | `step_0_canonicalize` | ✅ json.dumps sort_keys |
| 1 generate | `step_1_generate_region_capacity_combinatorial` | ✅ F1 combinatorial path, 含 cert dataclass + canonical_bytes + active_assumptions |
| 2 minimize | (inline in step 1) | ✅ combinatorial 已 minimal |
| 3 serialize | `step_3_serialize` | ✅ Cut → JSON bytes (geometric_payload + cert + scope + literals optional) |
| 4 deserialize | `step_4_deserialize` | ✅ round-trip 等价 (cut_id + cert_hash 一致) |
| 5 validate | `step_5_validate_region_capacity` | ✅ 独立重算 cap_R + demand_R + cert.cells_per_pose 比对 + witness verify |
| 6 attach-scope check | `step_6_attach_scope_check` | ✅ 6 步 verify (source / ghost / **blocked_cells_hash v3.1** / artifact / oracle version / assumption) |
| 7 resolve / evaluate | `step_7_evaluate_cut` | ✅ family-dispatch (Family 1 → True) |
| 8 watcher index | (defer) | ⏸ Phase 1 |
| 9 replay regression | `run_lifecycle` end-to-end | ✅ 跨 state re-validate |

## Test (14 cases, manual run)

```bash
.venv/bin/python docs/research/p3_b_design_v2_20260521/poc/test_b_core_lifecycle.py
# === Summary: 14 passed, 0 failed ===
```

测试覆盖:
1. `test_cut_post_init_mutual_exclusion` — v3 互斥契约 (literals XOR geometric_payload)
2. `test_ghost_agnostic_sentinel` — `compute_ghost_rect_id(None) == "__ghost_agnostic__"`
3. `test_blocked_cells_hash_deterministic` — canonical hash 跨 instantiation 稳定
4. `test_f1_generator_triggers_when_baseline_overflow` — cap=68 < demand=69 → cut
5. `test_f1_generator_silent_when_no_overflow` — cap=70 ≥ demand=69 → 不 cut
6. `test_full_lifecycle_round_trip` — 9 步 end-to-end ✓✓✓✓✓✓✓
7. `test_serialize_deserialize_roundtrip` — Step 3 ↔ Step 4 round-trip equivalence
8. `test_validator_catches_cap_R_tampering` — cert cap_R=999 篡改 → unsound
9. `test_validator_catches_cells_per_pose_source_rotated` — v1.1 finding #5 修验证 (cells_per_pose mismatch → unsound)
10. `test_attach_scope_ghost_agnostic_passes_step_2` — GHOST_AGNOSTIC sentinel 跳 step 2, **但** step 3 blocked_cells_hash 仍校验 (F1 ghost 变后 blocked 也变 → quarantine)
11. `test_attach_scope_blocked_cells_hash_v3_1_step_3` — v3.1 finding #4 修验证 (exterior_blocks 变 → quarantine)
12. `test_attach_scope_oracle_version_unavailable` — Oracle 版本不在 state.available → HOLD (不 quarantine)
13. `test_evaluate_geometric_region_capacity_returns_true` — v1.1 §6 简化 (scope 内 deterministically violate)
14. `test_assumption_unknown_key_fails_closed` — v3.1 §4 Gap 5 fail-closed (未知 key → False, 不 quarantine)

## 关键发现 (Phase 1 implementation 时注意)

1. **F1 ghost_agnostic 不等于 blocked_cells_agnostic**. F1 cut 用 `GHOST_AGNOSTIC`
   sentinel 跳过 step 2 ghost_rect_id 比对, **但** step 3 `blocked_cells_hash`
   仍校验 — ghost_cells 影响 blocked_cells_hash. test #10 验证: GHOST_AGNOSTIC
   不绕过 step 3, 这是预期行为, 保持 v3.1 sound.

2. **PoC scope 简化**: cap_R 只看 `ghost ∪ exterior_blocks` (v1.1 static), 不看
   `cell_owner`. F1 反例 (crusher 占 left baseline 2 cells) 通过 mock
   `exterior_blocks=frozenset({(15, 0), (16, 0)})` 触发 — 实际 production 这 2
   cells 是 "永久 block" 而不是 "动态 cell_owner". 跟 v1.1 spec §2a 一致.

3. **Validator 跑 0.02ms**. PoC 简化 region (left_baseline = 70 cells). 真
   production 70x70 grid + Farkas dual check 时延会高. v1 spec §6 evaluate
   "无条件 True" 简化保 hot path O(1).

4. **`__post_init__` 互斥契约 enforce 在 Cut() 时**, 不需要单独 validator.
   抓 5 finding #1 (literals/geometric_payload 互斥) 跟 _FAMILY_MODE_MAP 一致性.

## 不在 PoC scope

- Phase 1 实施: 迁 src/cuts/families/region_capacity.py
- Family 2/3/4/5/8/9 (其他 family)
- Step 8 watcher index (Phase 1 + 6 维 by_ghost Day 17 加)
- Step 10 dominance/expiry (defer Phase 2)
- Multi-anchor / multi-candidate runtime (PoC single anchor only)
- Real Farkas LP dual check (PoC combinatorial path only)

## Cross-ref

- `../cut_lifecycle_v2.md` v3.1 §2-§9 (9 步 lifecycle)
- `../cut_family_specs/01_region_capacity.md` v1.1 (Family 1 完整 spec)
- `../red_fixtures/F1_boundary_saturation.md` (反例)
- `../cross_check/gemini_round_14_cut_families.md` + `gemini_round_15_followup.md`
- [[feedback_proof_object_lifecycle]] memory (v4 replay bug 教训)
