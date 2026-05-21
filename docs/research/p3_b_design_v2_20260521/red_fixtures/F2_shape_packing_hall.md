# F2 — Shape Packing Hall (Red Fixture)

> **Status**: Day 12 skeleton (2026-05-21) — `[NEEDS_NEW_FAMILY]` Day 13-17
> **Cross-refs**: `../cut_lifecycle_v2.md` §3 §6 + v14 review Gemini 反例 B
> **Cut family owner**: **新 family** "shape_packing_hall" (Day 13-17 schema) — v14 5 family 不覆盖

## 1. 反例几何 (Gemini 反例 B)

### Setup

- left baseline 长度 10 (取 x=0, y=0..9 的简化版, 实际 70 grid 是同 pattern 放大)
- ghost 占 (x=0, y=4) 单格 → baseline 被切两段:
  - 段 A: y=0..3 (4 cell)
  - 段 B: y=5..9 (5 cell)
- 共 9 free cell
- demand: 3 个 boundary port pose (1×3 shape)

### 表面 sound 但实际 infeasible

- region capacity check: 9 cell ≥ 3 × 3 = 9 → **pass**
- 但 length-3 interval scheduling:
  - 段 A (length 4): 能放 ⌊4/3⌋ = 1 个 1×3
  - 段 B (length 5): 能放 ⌊5/3⌋ = 1 个 1×3
  - 合计 max 2 < demand 3 → **INFEASIBLE**

### 真实 production 几何

70 grid left baseline 长 70, ghost 任意分割 → 各段 ⌊len/3⌋ 求和必 ≥ 23 才可能放下 23 boundary port. ghost 切位置敏感 — Hall-condition 类约束.

## 2. MasterStateV2 表达

```python
state = MasterStateV2(
    groups={
        "boundary_storage_port": GroupState(
            group_id="boundary_storage_port",
            demand=23,                              # 简化: 实际 23 (one edge) 或 46 (both)
            pose_domain=frozenset([...]),           # 67 candidate poses (left baseline)
            selected_poses=[],                       # 反例 setup 前空
            remaining_count=23,
        ),
        # 其他 facility groups 略
    },
    cell_owner={},
    free_cells=bitset_compute(...),                 # 70x70 - ghost cell
    ghost_rect=Rect(x=0, y=4, h=1, w=1),            # 单格 ghost (简化反例)
    ghost_cells=bitset_with_set_bits([(0, 4)]),
    ...
)
```

### 实际 production 反例 (ghost 是 rectangle)

- ghost = Rect(x=0..2, y=30..32) 3×3 ghost
- left baseline 被切成 y=0..29 (30 cell) + y=33..69 (37 cell) (假设 ghost 触 baseline)
- 30 / 3 = 10 pose, 37 / 3 = 12 pose, 合计 22 < demand 23 → INFEASIBLE
- region_capacity 看 30+37 = 67 ≥ 69 = 23×3 → **pass** (但 lower-bound on cells)

## 3. 期待结果

任何 master OPTIMAL → sub-problem oracle (binding / shape Hall) 必返:
- region_capacity Family 1 **不够**: pass 但实际 INFEASIBLE
- 需要 **新 cut family** "shape_packing_hall" / "interval_scheduling_hall":
  - 对每个 maximal-free-interval `I_k` (free cells contiguous on baseline)
  - 计算 `⌊len(I_k) / pose_length⌋` (能放 max pose 数)
  - 若 `sum_k ⌊len(I_k) / pose_length⌋ < demand` → INFEASIBLE
  - cut 形式: `not(ghost_rect=G ∧ baseline_segment_lens=(4,5))` 或更一般的 Hall constraint

## 4. Hardcode cut object (skeleton, [NEEDS_NEW_FAMILY])

```python
F2_cut = Cut(
    cut_id="F2-shape-hall-001",
    family="shape_packing_hall",                    # ← 新 family, Day 13-17 加进 CutFamily enum
    literals=(),                                     # 几何 cut, 无 instance-level literal
    scope=CutScope(
        ghost_rect_id="<G canonical hash>",
        blocked_cells_hash="<G ghost + boundary blocks>",
        source_digest="...",
        artifact_hashes={...},
        oracle_abstraction_version="shape_hall_v1",  # 新 oracle (Day 13-17)
        active_assumptions=(
            Assumption(
                key="boundary_pose_shape",
                value="1x3_rigid",                  # 反例假设 boundary pose 都是 1×3 shape
            ),
            Assumption(
                key="boundary_region",
                value="left_baseline",
            ),
        ),
    ),
    cert=OracleCert(
        cert_kind="hall_interval_witness",          # 新 cert kind
        cert_payload=canonical_bytes({
            "region": "left_baseline",
            "ghost_partition_lens": [4, 5],          # 段 lens after ghost cut
            "pose_length": 3,
            "max_packable": [1, 1],                  # ⌊4/3⌋=1, ⌊5/3⌋=1
            "total_packable": 2,
            "demand": 3,
            "gap": 1,
            "witness": "interval_scheduling_LP_dual",
        }),
        cert_hash="<sha256>",
    ),
    family_version="v1.0",
    validator_version="v1.0",
    payload_schema_version=1,
    oracle_name="shape_hall_v1",
    oracle_cert_hash="<sha256>",
    ...
)
```

## 5. Schema gaps vs cut_lifecycle_v2 / state_machine_v2

| 检查 | 状态 |
|---|---|
| `CutFamily` enum 需加 `"shape_packing_hall"` | ❌ [NEEDS_NEW_FAMILY] Day 13-17 |
| `OracleCert.cert_kind` "hall_interval_witness" | ❌ [NEEDS_NEW_CERT_KIND] Day 13-17 |
| literals 非空约束 (跟 F1 同) | ❌ [SCHEMA_GAP] cut_lifecycle_v2 §3 强制 `Tuple[CutLiteral, ...]` |
| Validator §6 没列 Family "shape_packing_hall" | ❌ Day 13-17 加 |
| `evaluate_cut_as_multiset` 在 literals=() 行为? | ⚠️ cut_lifecycle_v2 §5 `cut_demand_by_group` 空 dict → multiset 检查空集 ⊆ 任何 state → 永远 True. 不对! 几何 cut 不该用 multiset evaluate. **需 family-specific evaluate**, 不全用 multiset. Day 13-17 必须 split evaluate path |
| `state.ghost_cells` carry 反例 ghost | ✅ bitset 直接支持 |
| `DerivedDomain.front_resource_load` carry baseline cell occupancy? | ⚠️ 当前 schema 是 Counter[(cell, layer)] — `(cell, "port")` 或 `(cell, "boundary")` 待定 |

## 6. Day 13-17 接力清单 (F2 暴露 schema gap)

1. **`CutFamily` enum 加 `shape_packing_hall`** (在 cut_lifecycle_v2 §3)
2. **Validator §6 加 Family 6: shape_packing_hall**:
   - cert_payload schema: `{region, partition_lens, pose_length, max_packable, demand, witness}`
   - 独立重算: 对当前 free_cells 按 region 切 maximal interval, 算 `⌊len/pose_length⌋` 求和, 验 < demand
   - 复用: 暂无 (新 oracle), Day 13-17 写
3. **`evaluate_cut` family-dispatch 改造**:
   - literals-based families (3 port_exposure, 5 pattern_nogood) → multiset evaluate
   - geometric families (1 region_capacity, 2 cutset, 4 component_reach, 6 shape_hall) → family-specific evaluator on cert + state
4. **Active assumption `boundary_pose_shape=1x3_rigid`** 在 state 怎么 verify:
   `canonical_rules.json` 内 `boundary_storage_port` shape definition 哈希 → assumption hold iff hash match
5. **F2 ↔ F1 关系**: F1 Family 1 region_capacity cut 在 F2 反例上 evaluate 返
   what? 应**不 violate** (region capacity 6.9.cells ≥ 6.9 demand) — 这是 F2
   需新 family 的 raison d'être. Day 13-17 加 unit test confirm.

## 7. 开放 questions

1. **Hall condition 的 generic form**: 上面 max_packable 是 `⌊len/3⌋` 假设
   pose 是 rigid 1×3. 若 pose 可 rotate (1×3 vs 3×1) 或 pose 多 shape
   (boundary_storage_port 只 1×3 简化, 其他 facility 不一样), Hall condition
   要更复杂. Day 13-17 schema 决定 simple 还是 generic.
2. **Multi-edge interaction**: 反例只看 left baseline. 真 production left +
   bottom 都受 ghost 影响. cut 是 per-edge 还是 cross-edge? Day 13-17 定.
3. **Ghost shape 影响**: ghost 是矩形, 切 baseline 时只有 ghost rectangle
   touch baseline 那些边才切. 怎么从 ghost_rect → baseline partition_lens?
   Helper function in `state_machine_v2.py:compute_baseline_partition_lens`.
4. **LP dual witness 怎么算**: cert.payload 标 "interval_scheduling_LP_dual",
   但 interval scheduling 不是 LP — 是 combinatorial. 应该是 "Hall's marriage
   theorem witness" 形式: 给一个 subset S of poses 使 `|N(S)| < |S|`.
   Day 13-17 cert schema 精确化.

## 8. 验收 status (Day 12)

- ✅ 反例几何 concrete (length-10 simplified + 70-grid production both 列出)
- ✅ MasterStateV2 表达力够 (ghost_cells + cell_owner + groups carry 反例)
- ✅ Hardcode cut skeleton 写 (literals=(), 新 family, 新 cert_kind)
- ⚠️ **5 个 [SCHEMA_GAP] / [NEEDS_NEW_FAMILY]** → Day 13-17 必接 §6
- ⏸ Validator implementation defer to Day 13-17

F2 close (skeleton + schema gap 接力清单完整).
