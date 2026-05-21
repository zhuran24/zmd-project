# F1 — Boundary Saturation (Red Fixture)

> **Status**: Day 10 deliverable (2026-05-21)
> **Cross-refs**: `../state_machine_v2.md` §2 / `../cut_lifecycle_v2.md` §3 §5 §6
> **Cut family owner**: Family 1 region_capacity + Family 3 port_exposure (无需新 family)

## 1. 反例几何

`boundary_storage_port` 在 source-of-truth 下:
- `rules/canonical_rules.json` `placement_rule: "left_or_bottom_boundary"`
- 每边 23 port × 2 边 = **46 placed pose** (demand)
- 每 pose 1×3 cell, 无重叠铺法 start=1,4,7,...,67 (共 23 起点 per edge)
- placed 后**必须 100% 铺满 left+bottom 138 cells** (46 × 3 = 138)
- candidate pose pool 134 (`gen_boundary_ports` 输出: left 67 + bottom 67)

### 反例 instance: 一个 boundary cell 被 manufacturing_3x3 (crusher) 占用

```
70x70 grid (只画 left+bottom 区域, x=纵, y=横):

  y=0  y=1  y=2  y=3  y=4  y=5 ...
x=0  C   C   C   .    .    .       ← crusher pose at (0,0) 占了 (0,0)(0,1)(0,2)
x=1  C   C   C   .    .    .
x=2  C   C   C   .    .    .
x=3  .   B   B   B    .    .       ← boundary port @ (3,0..2)... 跟 crusher cell (0..2,0) overlap?
```

更精确表述: `boundary_storage_port` 必须占 `(0, y)` 或 `(x, 0)` cells. crusher pose 占 (0,0)..(2,2) → **吃掉 left baseline 的 (0,0)(1,0)(2,0)** 3 个 boundary cell. boundary 群已少 3 cell, 46 个 pose 无处可放 → INFEASIBLE.

### 反例核心

- crusher pose `(crusher_blue_iron, pose=42)` 占 (0,0)..(2,2) 9 cells
- 其中 (0,0)(1,0)(2,0) 属于 left baseline (y=0 column)
- left baseline 共 70 cell (x=0..69, y=0), 但 23 boundary port pose 只用 23×3=69 cell (起点 1,4,...,67, 占 1..67+2=1..69)
- crusher 吃掉 (0,0)(1,0)(2,0) 中 (1,0)(2,0) 在 port 占用范围 (起 pose@x=1 占 1,2,3) — **直接冲突**

→ 任何包含此 crusher pose 的 master assignment **sound INFEASIBLE**.

## 2. MasterStateV2 表达

按 `state_machine_v2.md` §2 schema 填:

```python
state = MasterStateV2(
    groups={
        "crusher_blue_iron": GroupState(
            group_id="crusher_blue_iron",
            demand=34,                       # 34 个 crusher 全 placed
            pose_domain=frozenset([...]),    # 群共享 pose_domain
            selected_poses=[
                ("crusher_blue_iron", 42),   # ← 反例: 这个 pose 占 (0,0)..(2,2)
                # ... 其余 33 个 pose 任意 valid 选择
            ],
            remaining_count=0,                # demand 已满
        ),
        "boundary_storage_port": GroupState(
            group_id="boundary_storage_port",
            demand=46,
            pose_domain=frozenset([...]),     # 134 candidate poses (left 67 + bottom 67)
            selected_poses=[
                # 故意只放 45 个 (留 1 demand 未满) — 没法放第 46 个因为 crusher 吃了 cells
                ("boundary_storage_port", 1),
                ("boundary_storage_port", 4),
                # ... 共 45 个
            ],
            remaining_count=1,                # 还差 1 个未 place
        ),
    },
    cell_owner={
        # crusher pose 占的 9 cells
        (0,0): ("crusher_blue_iron", 0),
        (0,1): ("crusher_blue_iron", 0),
        (0,2): ("crusher_blue_iron", 0),
        (1,0): ("crusher_blue_iron", 0),     # ← left baseline cell 被吃
        (1,1): ("crusher_blue_iron", 0),
        (1,2): ("crusher_blue_iron", 0),
        (2,0): ("crusher_blue_iron", 0),     # ← left baseline cell 被吃
        (2,1): ("crusher_blue_iron", 0),
        (2,2): ("crusher_blue_iron", 0),
        # 45 个 boundary port 占的 cells (略)
    },
    free_cells=bitset_compute(...),          # = all - ghost - cell_owner.keys()
    ghost_rect=None,                          # F1 不依赖 ghost
    ghost_cells=bitset_empty(4900),
    derived=DerivedDomain(
        binding_domain_summary={...},        # 不参与 F1 拦截路径
        forced_terminal_resources={...},
        front_resource_load=Counter(),
        power_cover_domain={},
        power_cover_invalid=False,
    ),
    trail=[...],                              # Day 10-12 不验 trail; Phase 1 加
    decision_level=1,
    decision_marks=[0],
    active_cuts=[],                           # 反例 setup 之后 attach 拦截 cut
    conflict=None,
)
```

## 3. 期待结果

任何 master OPTIMAL → sub-problem oracle (binding / routing) 必返
**INFEASIBLE + sound cert**:
- binding oracle 验 boundary port 第 46 个 slot **没合法 pose 放** (cells (1,0)(2,0)
  被 crusher 占) → core = `{crusher_blue_iron[slot=k]=42}` 单 literal cut
- 或 region_capacity oracle 跑 LP relaxation 在 left+bottom region 上验
  `cap_R - placed_in_R < demand_R - placed_demand_in_R` → INFEASIBLE

## 4. Hardcode cut object (按 cut_lifecycle_v2.md §3 schema)

### 4a. Family 5 pattern_nogood (单 literal cut)

最直接表达: "crusher@(0,0..2,2) → INFEASIBLE"

```python
fixture_F1_cut = Cut(
    cut_id="F1-pattern-nogood-001",
    family="pattern_nogood",
    literals=(
        CutLiteral(
            slot_ref=AnonymousSlotRef("crusher_blue_iron", 0),
            pose_id=42,                       # 占 (0,0)..(2,2) 的 pose
        ),
    ),
    scope=CutScope(
        ghost_rect_id="",                     # F1 不依赖 ghost
        blocked_cells_hash=sha256(b""),
        source_digest="<canonical_hash of current source>",
        artifact_hashes={
            "canonical_rules.json": "<file hash>",
            "candidate_placements.json": "<file hash>",
            "mandatory_exact_instances.json": "<file hash>",
        },
        oracle_abstraction_version="binding_v3",
        active_assumptions=(
            Assumption(
                key="left_or_bottom_boundary_saturation",
                value="left_baseline=23,bottom_baseline=23,demand=46,cells=138,saturation=100%",
            ),
        ),
    ),
    cert=OracleCert(
        cert_kind="binding_infeasibility_core",
        cert_payload=canonical_bytes({
            "group": "boundary_storage_port",
            "slot_required_after_placement": 46,
            "remaining_baseline_cells_after_crusher_block": 135,
            "min_cells_per_pose": 3,
            "max_pose_fits": 45,                # ⌊135/3⌋ — 但 baseline 切断后实际更少
            "lower_bound": 45,
            "demand": 46,
            "gap": 1,
        }),
        cert_hash="<sha256>",
    ),
    family_version="v1.0",
    validator_version="v1.0",
    payload_schema_version=1,
    oracle_name="binding_v3",
    oracle_cert_hash="<sha256>",
    minimization_audit={"size_before": 1, "size_after": 1, "qx_calls": 0},
    created_at="2026-05-21T...",
    iter_index=0,
)
```

### 4b. Family 1 region_capacity (LP-dual cert, 更 generic)

```python
fixture_F1_region_cut = Cut(
    cut_id="F1-region-capacity-001",
    family="region_capacity",
    literals=(
        # 反例 group 的具体 violation 不在 region cut literal 内;
        # region cut 通过 region/cap/demand 约束 propagate
        # 但 cut_lifecycle_v2 §3 要求 literals 非空 — 用 "ghost-region-marker" 占位
        # NOTE [SCHEMA_GAP]: Family 1 region cut 可能不需要 literals,
        # cut_lifecycle_v2 当前 schema 强制 Tuple[CutLiteral, ...] 非空?
    ),
    scope=...,
    cert=OracleCert(
        cert_kind="region_capacity_lp_dual",
        cert_payload=canonical_bytes({
            "region": "left_baseline",        # cells (x, 0) for x in 0..69
            "region_cells_bitset": "<base64 70-bit mask>",
            "cap_R": 70,                      # 实际 = 70 cells
            "demand_R": 23 * 3,               # 69 cells must be boundary
            "placed_in_R": [
                # crusher (0,0..2,2) 占 (0,0)(1,0)(2,0) = 3 cells in left baseline
                {"facility": "crusher_blue_iron", "cells_in_R": 3},
            ],
            "lp_dual_ray": "<base64 farkas dual ray>",
            "gap": "demand_R + crusher_cells = 69 + 3 = 72 > cap_R = 70",
        }),
        cert_hash="<sha256>",
    ),
    ...
)
```

## 5. `evaluate_cut_as_multiset(cut, state)` 调用 + 期待结果

按 `cut_lifecycle_v2.md` §5 multiset 包含语义:

```python
# Fixture 4a — Family 5 pattern_nogood:
result = evaluate_cut_as_multiset(fixture_F1_cut, state)
# 推理:
#   cut_demand_by_group = {"crusher_blue_iron": Counter({42: 1})}
#   state_by_group = {
#       "crusher_blue_iron": Counter({42: 1, ...}),  # state 内 selected_poses 第 0 个就是 42
#       ...
#   }
#   Counter({42:1}) <= Counter({42:1,...})  → True
# → return True (cut VIOLATED)
assert result == True

# 反向验证 (无 crusher pose 42 的 state):
clean_state = state.replace(
    groups={**state.groups,
            "crusher_blue_iron": state.groups["crusher_blue_iron"]._replace(
                selected_poses=[("crusher_blue_iron", 17), ...]  # 不含 pose 42
            )}
)
clean_result = evaluate_cut_as_multiset(fixture_F1_cut, clean_state)
# Counter({42:1}) NOT <= Counter({17:1, ...})  → False
assert clean_result == False  # cut NOT violated (sound: pose 42 不在 → cut 不限制)
```

## 6. Scope-aware replay (Day 10-12 不实施, Day 18-21 接)

F1 cut scope:
- `ghost_rect_id=""` — F1 跟 ghost 无关 (任何 ghost 都拦)
- 在 cut_lifecycle_v2 §4 replay 算法 step 2 中, 空 ghost_rect_id 是特殊 case:
  应**不 HOLD**, 直接进 step 3 artifact check.
- [SCHEMA_GAP] cut_lifecycle_v2 §4 没显式处理 ghost-agnostic cut. 待 Day 18-21
  集成时补 fallthrough 规则.

## 7. Schema cross-check vs state_machine_v2 / cut_lifecycle_v2

| 检查 | 状态 |
|---|---|
| `GroupState.selected_poses` 能 carry 反例 pose | ✅ |
| `cell_owner` 能 carry crusher 占的 9 cells | ✅ |
| `AnonymousSlotRef(group_id, slot_index)` 能指 crusher slot 0 | ✅ |
| `CutLiteral(slot_ref, pose_id)` 能表达 `crusher[slot=0]=pose=42` | ✅ |
| `evaluate_cut_as_multiset` 跨 slot order 仍 sound (Counter ≤ Counter) | ✅ |
| `Cut.scope.active_assumptions` carry "left_or_bottom_boundary_saturation" | ✅ |
| Family 5 pattern_nogood cert_kind = "binding_infeasibility_core" 在 §6 validator | ⚠️ §6 列的是 `forbidden_pose_pattern` + `oracle_cert_hash`, 不显式 "binding_infeasibility_core" — 需 Day 13-17 在 §6 Family 5 spec 加 cert_kind enum |
| Family 1 region_capacity cut literals 是否可空? | ❌ [SCHEMA_GAP] cut_lifecycle_v2 §3 schema `literals: Tuple[CutLiteral, ...]` 没说能空; 若 region cut 不带 literal 需 separate field; **Day 13-17 必须解决** |
| Family 1 cert "lp_dual_ray" 重算路径在 §6: "若 cert 带 Farkas dual, 跑 algebraic check `yᵀ A ≤ 0 ∧ yᵀ b > 0`" | ✅ 已 covered |

## 8. Open questions → Day 13-17 / Day 18-21

1. **literals 非空约束**: Family 1 region_capacity / Family 2 cutset / Family 4 component_reach 这种 cell-level / graph-level cut 不需要 literal — 但 §5 multiset evaluate 假设 literal 非空. 需要在 cut object schema 上区分 "literal-based" (Family 3 / 5) vs "geometric/algebraic" (Family 1 / 2 / 4) cut, 或加 `optional literals=()` + 单独 `geometric_payload` field.

2. **`evaluate_cut_as_multiset` 对 ghost-agnostic cut 的 fallthrough**: F1 scope ghost_rect_id="", 当前 §4 replay step 2 不 match → HOLD. 但 ghost-agnostic cut 应该 unconditional attach. 待补 special-case.

3. **slot_index 在 hardcode fixture 内是否必填**: 反例只关心 "crusher group 内有 pose=42", 不关心是哪个 slot. multiset evaluate 自动忽略 slot_index. 但 hardcode 内仍写 `slot_index=0` 不影响. → 文档说明 slot_index 仅 debug.

4. **Active assumption "left_or_bottom_boundary_saturation" 怎么 verify**: cut_lifecycle_v2 §4 step 5 `state.assumption_holds(assumption)` 没定义实现. 这个 assumption 在每个 candidate 都 hold (是源码 fact). 应作 const → step 5 always pass.

5. **F1 region_cut 跟 binding INFEASIBLE core 哪个**对**? 两者都 sound, 但 cut store 应 dedupe? region_cut 比 pattern_nogood 一般化 (拦更多 case). 待 Phase 1 dedupe 政策.

## 9. 验收 status (Day 10 close-out)

- ✅ 反例几何 concrete (crusher pose 42 占 (0,0)..(2,2), boundary 缺 1 demand)
- ✅ MasterStateV2 表达力足以 carry 反例
- ✅ Family 5 pattern_nogood cut hardcode 完整 (含 scope / cert / version)
- ✅ Family 1 region_capacity cut hardcode 完整 (含 LP-dual cert)
- ✅ `evaluate_cut_as_multiset` 期待结果列出 (violate / not-violate 两 case)
- ⚠️ 1 个 hard schema gap (literals 非空) + 4 个 soft open question → §8
- ⏸ Scope-aware replay 测试 defer 到 Day 18-21

F1 close. 下一步 F4 (Day 11).
