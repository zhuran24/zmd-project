# F5 — Power Grid Disconnect (Red Fixture)

> **Status**: Day 17d (2026-05-21)
> **Cross-refs**: `../cut_family_specs/08_power_grid_reach.md` v1.0 + `../cross_check/gemini_round_14` (反例提出) + `../cross_check/gemini_round_15` (Family 8 独立 family verdict)
> **Cut family owner**: **Family 8 power_grid_reach** (v3 新)
> **来源**: Gemini round 14 Task B 反例

## 1. 反例几何

### Setup (Gemini round 14 原版)

- 70×70 grid
- ghost = `(x=30..44, y=0..69)` 15 列宽 × 70 行高纵切, 切 grid 成绝对不相连的
  Left (x=0..29) 和 Right (x=45..69) 两半
- 设施:
  - `protocol_core` (全局电力枢纽) placed at Left `(10, 10)`
  - `crusher_blue_iron` (需 power) placed at Right `(60, 60)..(62, 62)` 3×3
  - `shop_blue_iron` (需 power) placed at Right `(60, 65)..(62, 67)` 3×3
- Belt routing: crusher 跟 shop 内部互连 (Right 区闭环), 不跨 ghost
- Power 设定: `power_pole` 1×1 shape, R_conn = 10 (Euclidean)

### 反例数学

任何 Right 区 pole 跟 Left 区 pole 之间最短距离:
- Right 最左 pole 在 x=45, Left 最右 pole 在 x=29 → 距离 ≥ 16 > R_conn=10
- → power network 上 Left/Right 两 component 不连通
- → crusher_A 永远无法通过 pole 链连回 protocol_core
- → **任 master OPTIMAL 选 crusher_A=pose_X 都 INFEASIBLE**

## 2. 现有 8 family 全静默 (Gemini round 16 E1 补 Family 9)

| Family | 静默原因 |
|---|---|
| 1 region_capacity | Right 区空间极大 (25×70=1750 cells), 远超 demand. **Pass** |
| 2 cutset | Belt routing 内部闭环, 无跨区流量 demand. min-cut 不 trigger. **Pass** |
| 3 port_exposure | crusher/shop 的 port 在 Right 区有 free front cell. **Pass** |
| 4 component_reach | Belt graph 内部连通 (crusher↔shop), src/sink 同 component. **Pass** |
| 5 pattern_nogood | sub-problem oracle 在 belt 端 FEASIBLE. **不 trigger** |
| 6 shape_packing_hall | Baseline 没被 ghost 切碎到 Hall infeasible. **Pass** |
| 7 power_hitting_set | crusher_A 周围 Right 区有 pole 候选 (CoverSet 非空). **Pass** ← key |
| 9 density_envelope | 只 2 facility 在 Right 区, 密度极低不触发 oracle K bound. **Pass** |

→ 真 INFEASIBLE 但 8 family 全静默 = **Family 8 power_grid_reach 唯一 owner**.

## 3. MasterStateV2 表达

```python
state = MasterStateV2(
    groups={
        "protocol_core": GroupState(
            group_id="protocol_core",
            demand=1,
            pose_domain=frozenset(...),
            selected_poses=[("protocol_core", 5)],  # Left (10, 10)
        ),
        "crusher_blue_iron": GroupState(
            group_id="crusher_blue_iron",
            demand=34,
            pose_domain=frozenset(...),
            selected_poses=[("crusher_blue_iron", 17), ...],  # 含 Right (60, 60)
        ),
        "shop_blue_iron": GroupState(
            group_id="shop_blue_iron",
            demand=20,
            pose_domain=frozenset(...),
            selected_poses=[("shop_blue_iron", 23), ...],
        ),
        # ...
    },
    cell_owner={
        # protocol_core 占 (10, 10)
        (10, 10): ("protocol_core", 0),
        # crusher_A 占 (60, 60)..(62, 62)
        **{(60+i, 60+j): ("crusher_blue_iron", 0) for i in range(3) for j in range(3)},
        # shop_B 占 (60, 65)..(62, 67)
        **{(60+i, 65+j): ("shop_blue_iron", 0) for i in range(3) for j in range(3)},
    },
    ghost_rect=(30, 0, 70, 15),                    # (x, y, h, w) = 15 列宽纵切
    ghost_cells=frozenset({(x, y) for x in range(30, 45) for y in range(70)}),
    derived=DerivedDomain(
        power_cover_domain={
            # crusher_A 的 candidate pole 全在 Right 区 — Family 7 看是非空 →
            # Family 7 不 trigger
            ("crusher_blue_iron", 17): bitset_with_right_zone_poles(),
        },
        ...,
    ),
    ...
)
```

## 4. Hardcode Family 8 cut object

```python
F5_power_grid_cut = Cut(
    cut_id="F5-power-grid-001",
    family="power_grid_reach",
    literals=None,
    geometric_payload=canonical_bytes({
        "facility_pose": ["crusher_blue_iron", 17],
        "facility_cells": [[60+i, 60+j] for i in range(3) for j in range(3)],
        "pole_radius": 10.0,
        "protocol_core_cell": [10, 10],
        "candidate_pole_poses": [101, 105, 117, ...],  # Right 区 pole pose ID list (非空)
        "candidate_pole_cells": [[55, 55], [55, 60], [60, 55], ...],  # 全 Right 区
        "source_component_pole_set": [1, 5, 9, 13, 17, 22, ...],  # Left 区 + protocol_core
        "target_component_pole_set": [101, 105, 117, ...],         # Right 区 pole
        "disconnect_witness_kind": "ghost_blocks_jump",
        "blocking_ghost_cells": [[x, y] for x in range(30, 45) for y in range(70)],  # 全 ghost
        "power_graph_b64": "<base64 encoded graph snapshot>",
        "ghost_rect_repr": [30, 0, 70, 15],
    }),
    scope=CutScope(
        ghost_rect_id="<sha256 of '30,0,70,15'[:16]>",
        blocked_cells_hash="<sha256 of sorted ghost ∪ exterior cells>",
        source_digest="<canonical_rules + candidate_placements + mandatory hash>",
        artifact_hashes={
            "canonical_rules.json": "<hash>",
            "candidate_placements.json": "<hash>",
            "mandatory_exact_instances.json": "<hash>",
        },
        oracle_abstraction_version="power_grid_reach_v1",
        active_assumptions=(
            Assumption("power_pole_radius", "R=10"),
            Assumption("protocol_core_position", "(10,10)"),
        ),
    ),
    cert=OracleCert(
        cert_kind="power_pole_bfs_disconnect_witness",
        cert_payload=canonical_bytes({...}),
        cert_hash="<sha256>",
    ),
    family_version="v1.0",
    validator_version="v1.0",
    payload_schema_version=1,
    oracle_name="power_grid_reach_v1",
    oracle_cert_hash="<sha256>",
)
```

## 5. `evaluate_geometric_power_grid_reach` 期待

按 cut_family_specs/08 v1.0 §6:

```python
# 在 F5 state 上
result = evaluate_geometric_power_grid_reach(F5_power_grid_cut, state)
# 重算 power network on cur state:
#   build_power_network(state, R_conn=10) → V_pole + E_jump
#   bfs_component(power_graph, protocol_core_cell=(10,10)) → Left 区 component
#   compute_cover_set(("crusher_blue_iron", 17), ghost, free_cells) → Right 区 pole 集
#   bfs_component(power_graph, next(iter(Right 区 pole))) → Right 区 component
#   Left 区 ≠ Right 区 → return True (violate, cut 拦 master)
assert result == True

# clean state (ghost 移开): crusher_A 跟 protocol_core 同 component
clean_state = state.replace(ghost_rect=(60, 60, 5, 5),  # 小 ghost 不切
                             ghost_cells=frozenset())
clean_result = evaluate_geometric_power_grid_reach(F5_power_grid_cut, clean_state)
# Family 8 cert ghost_rect_repr 跟 clean_state.ghost_rect 不同 → validator 在
# step 6 attach-scope check 失败 → cut 不 attach 到 clean_state
# evaluate_geometric 本身在 clean state 上不应该被调用 (cut 不 attach)
# 若 force 调用 → power network 上 protocol_core ↔ crusher_A reachable →
# return False
```

## 6. Scope-aware replay (跨 candidate)

按 cut_lifecycle_v2 v3.1 §4 6 步 verify, F5 ghost-bound cut:

```python
# G1 ghost (cur F5) → cut attached
# G2 ghost (ghost 不切 power) → replay
G2_state = state.replace(ghost_rect=(60, 60, 5, 5), ...)
decision = replay_cut(F5_power_grid_cut, G2_state, store)

# Step 1 source_digest: match ✓
# Step 2 ghost_rect_id: G1 vs G2 不 match → HOLD (不 quarantine)
assert decision == "HOLD"

# 等下次 candidate ghost = G1 时 → re-attach + validate sound 重 evaluate
```

## 7. Schema cross-check vs cut_family_specs/08 v1.0

| 检查 | 状态 |
|---|---|
| `CutFamily` enum 加 `power_grid_reach` | ✅ v3 已加 |
| `cert_kind` "power_pole_bfs_disconnect_witness" | ✅ 本 spec §3 定义 |
| `MasterStateV2.derived.power_cover_domain` carry CoverSet | ✅ state_machine_v2 §6 |
| `GhostConditionChange` ghost 变触发 power_cover_invalid | ✅ state_machine_v2 §6 |
| Family 8 跟 Family 7 互斥 (CoverSet 空 vs 非空 disconnect) | ✅ 08 spec §9 protocol |
| 6 维 by_ghost watcher | ⏸ Day 17d cut_lifecycle §7 加 |

## 8. 验收 status

- ✅ 反例几何 concrete (ghost 15 列纵切 + R_conn=10 < 15 距离)
- ✅ 现有 7 family 全静默原因列出
- ✅ MasterStateV2 表达力 carry 反例
- ✅ Family 8 hardcode cut 完整 example
- ✅ evaluate_geometric 期待结果列出 (violate / scope mismatch HOLD)
- ✅ Scope-aware replay HOLD 路径
- ⏸ Phase 1 实施 validator round-trip 测试 (跟 PoC 同 pattern)

F5 close. 跟 Family 8 spec 一起作 Phase 1 实施 validator 输入.
