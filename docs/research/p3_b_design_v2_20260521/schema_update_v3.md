# Schema Update v3 — Day 13 起步 (解 Day 10-12 暴露 5 gap)

> **Status**: Day 13 propose draft (2026-05-21)
> **Cross-refs**: `cut_lifecycle_v2.md` §3 §4 §5 §6 + `state_machine_v2.md` §2 §6 + `red_fixtures/{F1,F2,F3,F4}.md`
> **Aim**: 解决 Day 10-12 4 fixture 暴露的 5 schema gap, 阻塞解开 → Day 14-17 可起 4 新 cut family schema

## Gap 1 — `literals` 非空约束 (F1 region cut + F2 几何 cut 暴露)

### 问题

`cut_lifecycle_v2.md` §3 当前 schema:

```python
@dataclass(frozen=True)
class Cut:
    literals: Tuple[CutLiteral, ...]  # 非空类型注解 (Tuple 默认非空意图)
    ...
```

但 F1 region_capacity / F2 shape_hall / F4 component_reach 这种 geometric/algebraic cut **不需要** literal — cut 通过 cert 上的 region/graph/cells 信息约束 propagation, 不指向具体 (group, slot, pose).

强行用 placeholder literal 会污染 §5 `evaluate_cut_as_multiset` (cut_demand_by_group 含假 literal → 错误 multiset 比对).

### 解 (推荐 A)

把 `literals` 改为 `Optional[Tuple[CutLiteral, ...]] = None`, 加 `geometric_payload: Optional[bytes] = None` field. 二者**互斥**: 任一 cut 必有一个非 None, 不可两者都 None 或都非 None.

```python
@dataclass(frozen=True)
class Cut:
    cut_id: CutId
    family: CutFamily

    # === Cut 主体: literal-based OR geometric, 互斥 ===
    literals: Optional[Tuple[CutLiteral, ...]] = None
    geometric_payload: Optional[bytes] = None

    scope: CutScope
    cert: OracleCert
    ...

    def __post_init__(self) -> None:
        has_lit = self.literals is not None and len(self.literals) > 0
        has_geo = self.geometric_payload is not None
        if has_lit == has_geo:
            raise ValueError(
                f"Cut {self.cut_id}: literals 和 geometric_payload 必有且只有一个非空"
            )
```

### 互斥分类 (per family)

| Family | mode | rationale |
|---|---|---|
| 1 region_capacity | **geometric** | LP/Farkas dual on region bitset, 不依赖 slot |
| 2 cutset | **geometric** | Menger min-cut on graph, 不依赖 slot |
| 3 port_exposure | **literal** | port active depends on group slot 选 |
| 4 component_reach | **geometric** | BFS witness path on free_cells |
| 5 pattern_nogood | **literal** | full assignment 反例 |
| 6 shape_packing_hall (新) | **geometric** | Hall condition on interval partition |
| 7 power_hitting_set (新) | **literal** | 指 facility group slot pose, ghost-conditioned |

### 备选 B (拒)

用 literal 占位 (e.g. `CutLiteral(AnonymousSlotRef("__geometric__", 0), pose_id=-1)`)
→ schema noise, 验 sound 性 false positive 风险, 拒.

## Gap 2 — `CutFamily` enum 加 2 family

### 当前

```python
CutFamily = Literal[
    "region_capacity",
    "cutset",
    "port_exposure",
    "component_reach",
    "pattern_nogood",
    "symmetry_lift",
]
```

### 改

```python
CutFamily = Literal[
    "region_capacity",
    "cutset",
    "port_exposure",
    "component_reach",
    "pattern_nogood",
    "shape_packing_hall",     # ← 新 (F2)
    "power_hitting_set",       # ← 新 (F3)
    "symmetry_lift",            # 1-7 的 lift, 不是新 family
]
```

每 family 在 §6 validator 加 spec (Day 14-17 完整数学定义).

## Gap 3 — `evaluate_cut` family-dispatch

### 问题

§5 `evaluate_cut_as_multiset(cut, state)` 假设 literals 非空, geometric cut 走这条路返 vacuous True (空 multiset ⊆ 任何 state).

### 解

cut object 上加 family-dispatch:

```python
def evaluate_cut(cut: Cut, state: BState) -> bool:
    """Cut 是否在当前 state 上 violate. Family-dispatch."""
    if cut.literals is not None:
        # Literal-based path (Family 3, 5, 7)
        return evaluate_cut_as_multiset(cut, state)
    elif cut.geometric_payload is not None:
        # Geometric path (Family 1, 2, 4, 6)
        validator = state.get_validator(cut.family)
        return validator.evaluate_geometric(cut, state)
    else:
        raise ValueError(f"Cut {cut.cut_id}: both literals and geometric_payload are None")
```

`validator.evaluate_geometric` 是新 method (跟 §6 `validate` 区分):
- `validate(cut, state) -> ValidationResult` — sound 性 second line of defense, 独立重算 cert
- `evaluate_geometric(cut, state) -> bool` — 快速 violate 检查, propagation hot path

### Family-specific `evaluate_geometric` 草拟 (Day 14-17 完整定义)

| Family | evaluate_geometric 逻辑 |
|---|---|
| 1 region_capacity | 取 cert payload `region_cells_bitset + cap_R + demand_R`, 算 `placed_demand_in_region(state, region) > cap_R` → True |
| 2 cutset | 取 cert payload `side_a + side_b + k_AB`, 验当前 free_cells 边界 cut size < k_AB → True |
| 4 component_reach | 取 cert payload `src + sink + witness_path`, 验 src→sink 在 free_cells 不连通 → True |
| 6 shape_packing_hall | 取 cert payload `partition_lens + pose_length + demand`, 算当前 ghost split 后 sum(⌊len/pose_length⌋) < demand → True |

## Gap 4 — `ghost_rect_id` canonical hash 算法 (F4)

### 问题

§4 replay 算法 step 2 用 `cut.scope.ghost_rect_id != state.candidate.ghost_rect_id` 比对, 但 ghost_rect_id 怎么算没定义.

### 解

```python
def compute_ghost_rect_id(rect: Optional[Rect]) -> GhostRectId:
    """Canonical hash for ghost rect, stable across sessions."""
    if rect is None:
        return "__no_ghost__"
    # 4 字段 canonical bytes, fixed delim
    blob = f"{rect.x},{rect.y},{rect.h},{rect.w}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]   # 短 hash 减小 cut store
```

**关键**: 用 `(x, y, h, w)` 四元组而**不**含 `blocked_cells_hash` — ghost 的语义是
矩形, blocked_cells 是 derived (ghost ∪ exterior ∪ mandatory_pre_block). 跨
candidate 同 ghost 不同 exterior block 应该是**同 ghost_rect_id** (cut sound).

`blocked_cells_hash` 单独作为 `CutScope.blocked_cells_hash` field 比对 (replay
step 3 artifact check 范畴).

### F1 boundary cut 不依赖 ghost 的 case

F1 cut `ghost_rect_id=""` 在 replay step 2 fallthrough — 不 match 任何 candidate
ghost_rect_id (因 candidate 必有 ghost). 这是 bug: ghost-agnostic cut 应 attach
all candidates.

**修法**: special-case sentinel `"__ghost_agnostic__"`:

```python
GHOST_AGNOSTIC = "__ghost_agnostic__"

# Step 2 改:
if cut.scope.ghost_rect_id != GHOST_AGNOSTIC and \
   cut.scope.ghost_rect_id != current_ghost_rect_id:
    return AttachDecision.HOLD
```

F1 cut 写 `ghost_rect_id=GHOST_AGNOSTIC`. F3/F4 cut 写实际 ghost hash.

## Gap 5 — `active_assumptions` verify 实现 (F1/F2/F3)

### 问题

§4 replay step 5: `state.assumption_holds(assumption)` 没定义实现.

### 解

`Assumption.key` 用 enum, 每 key 有专属 verify function:

```python
ASSUMPTION_KEYS = Literal[
    "left_or_bottom_boundary_saturation",      # F1
    "boundary_pose_shape",                       # F2
    "boundary_region",                           # F2
    "power_pole_radius",                         # F3
    "power_pole_shape",                          # F3
    "g1_blocks_AB_path",                         # F4
    # Day 14-17 各 cut family 自加
]

ASSUMPTION_VERIFIERS: Dict[str, Callable[[BState, str], bool]] = {
    "left_or_bottom_boundary_saturation": _verify_boundary_saturation,
    "boundary_pose_shape": _verify_pose_shape_constraint,
    # ...
}

def assumption_holds(state: BState, assumption: Assumption) -> bool:
    verifier = ASSUMPTION_VERIFIERS.get(assumption.key)
    if verifier is None:
        return False  # 未知 assumption → fail-closed (HOLD)
    return verifier(state, assumption.value)
```

### Source-of-truth assumption (vs state-conditioned)

两类 assumption:
- **Source-of-truth**: e.g. `left_or_bottom_boundary_saturation` — 全 source rotated
  时变, 否则 always hold. verify = hash check on `canonical_rules.json`.
- **State-conditioned**: e.g. `g1_blocks_AB_path` — 在特定 ghost / state 下成立.
  verify = 重跑 oracle 在当前 state.

Day 14-17 每 assumption key 标 source-of-truth / state-conditioned.

### Fail-closed 政策

未知 assumption key OR verifier 返 False → step 5 → `AttachDecision.HOLD` (不
quarantine, 等下 candidate 再试). 这跟 PROJECT_LOCK 一致 (silent recovery 禁止,
fail-closed default).

## 跟现有 schema 兼容性

### state_machine_v2.md

- §2 `MasterStateV2` 不需改 (state 不 carry cut object)
- §6 ghost-conditioned `power_cover_domain` 跟 Gap 4 配合: ghost_rect_id 算法
  consistent across `set_ghost_rect` + cut scope
- 验证 fixture: `state.ghost_rect` 通过 `compute_ghost_rect_id` 得 hash 与
  `set_ghost_rect` 时算的 hash 一致

### cut_lifecycle_v2.md

- §3 Cut schema 改: literals → Optional + geometric_payload, 加 `__post_init__` 验
- §4 replay step 2 + step 5 算法改: ghost_rect_id special-case + assumption_holds
- §5 `evaluate_cut_as_multiset` 改名 `evaluate_cut_literal_based`, 加
  `evaluate_cut_geometric` (validator dispatch)
- §6 validator 每 family 加 `evaluate_geometric` method (literal-based families
  返 NotImplementedError, geometric families 实)
- §8 quarantine 政策 unchanged (本 v3 不动 quarantine path)

## Day 14-17 接力清单 (本 v3 之后)

按 Day 14-17 plan:
1. Day 14: 改 cut_lifecycle_v2 §3 §4 §5 §6 接 Gap 1-5 (本 v3 propose)
2. Day 15: Family 1 region_capacity 完整 spec (cert schema + soundness + generator + resolve + validator + replay)
3. Day 16: Family 6 shape_packing_hall (新) + Family 7 power_hitting_set (新) 完整 spec
4. Day 17: Family 2 cutset + Family 4 component_reach + Family 3 port_exposure + Family 5 pattern_nogood spec (复用 PCR-CUT / D2 / boundary_constraints / L16 logic)

## 验收 status (Day 13)

- ✅ 5 gap 解决方案完整 propose (Gap 1 schema split, Gap 2 enum, Gap 3 dispatch, Gap 4 hash, Gap 5 verify)
- ✅ 跟 4 fixture (F1-F4) 对齐验证 (每 gap 标出来源 fixture)
- ✅ 跟 state_machine_v2 + cut_lifecycle_v2 兼容性 audit (改/不改 path 明确)
- ⚠️ propose 阶段, **未改 cut_lifecycle_v2.md 文件本身** — Day 14 单独 commit 改
  doc + 配套 fixture 更新
- ⏸ Validator implementation 仍 defer 到 Phase 1

下一步 Day 14: 改 cut_lifecycle_v2.md §3 §4 §5 §6 接本 v3 propose. 改完跑
fixture cross-check (F1-F4 schema 走新路径仍 carry 反例).
