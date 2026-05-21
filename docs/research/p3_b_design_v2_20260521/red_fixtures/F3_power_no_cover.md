# F3 — Power No-Cover Ghost-Conditioned (Red Fixture)

> **Status**: Day 12 skeleton (2026-05-21) — `[NEEDS_NEW_FAMILY]` Day 13-17
> **Cross-refs**: `../cut_lifecycle_v2.md` §3 §6 + `../state_machine_v2.md` §6 ghost-conditioned power_cover + `src/search/benders_loop.py:4219-4268` (L16 ref impl)
> **Cut family owner**: **新 family** "power_hitting_set" (Day 13-17 schema) — GPT power cut

## 1. 反例几何

### Setup

- Facility pose `p` (e.g. `crusher_blue_iron` pose 17) at (x=30, y=30)..(32,32) 3x3 块
- Pose `p` 需要 power 覆盖 (从 power_pole)
- Power pole `1×1` shape, 覆盖半径 R (e.g. 5 cells)
- Pole 候选 pose pool (e.g. 200 pole pose 全 grid)
- ghost rectangle `G` = (x=25..40, y=25..40) 16×16 — ghost 覆盖 facility pose `p` 周围 R 半径内的**所有 candidate pole pose location**
- 结果: facility pose `p` 在 ghost `G` 下没**任何** valid pole 能覆盖 → INFEASIBLE

### 在 state machine v2 schema 内表达

按 `../state_machine_v2.md` §2 `DerivedDomain.power_cover_domain`:

```python
state.derived.power_cover_domain[("crusher_blue_iron", 17)] = Bitset.empty(200)
# ↑ 该 (group, pose) 的 power cover candidate 集合是空 bitset → 没 pole 能覆盖
# state.derived.power_cover_invalid = False (已 rebuild against ghost G)
```

按 `../state_machine_v2.md` §6 ghost-conditioned 路径:
- `ghost_rect = G` 已 set, trail event `GhostConditionChange` emitted
- `power_cover_domain` 被 lazy rebuild 后该 (group, pose) entry 是空 bitset
- 任何 master OPTIMAL 含 `crusher_blue_iron[slot=*] = 17` 都 INFEASIBLE

## 2. MasterStateV2 表达

```python
state = MasterStateV2(
    groups={
        "crusher_blue_iron": GroupState(
            group_id="crusher_blue_iron",
            demand=34,
            pose_domain=frozenset([
                ("crusher_blue_iron", 17),       # ← 反例 pose
                # ... 其他 pose
            ]),
            selected_poses=[
                ("crusher_blue_iron", 17),       # ← master 选了这个 pose
                # ... 33 个其他
            ],
            remaining_count=0,
        ),
        "power_pole": GroupState(
            group_id="power_pole",
            demand=K,                             # K = 必要 power pole 数
            pose_domain=frozenset([...]),         # 200 candidate pole poses
            selected_poses=[...],                  # master 选的 pole
            remaining_count=0,
        ),
    },
    cell_owner={
        # crusher pose 17 占 (30,30)..(32,32)
        (30,30): ("crusher_blue_iron", 0),
        # ... 9 cells
        # 已选 pole 占的 cells
    },
    free_cells=bitset_compute(...),
    ghost_rect=Rect(x=25, y=25, h=16, w=16),     # ← G ghost
    ghost_cells=compute_ghost_cells(Rect(25, 25, 16, 16)),
    derived=DerivedDomain(
        binding_domain_summary={...},
        forced_terminal_resources={...},
        front_resource_load=Counter(),
        power_cover_domain={
            ("crusher_blue_iron", 17): Bitset.empty(200),   # ← 反例核心
            # ... 其他 (group, pose) entry (正常非空)
        },
        power_cover_invalid=False,                 # 已 rebuild against G
    ),
    trail=[
        # GhostConditionChange(old_rect=None, new_rect=G, ...)
        # PowerCoverShrink(("crusher_blue_iron", 17), all_bits=removed)
    ],
    decision_level=1,
    ...
)
```

## 3. 期待结果

任何 master OPTIMAL 含 `crusher_blue_iron[slot=*] = 17` 在 ghost `G` 下:
- power oracle (L16-style lazy power completion) 跑: check power cover for
  pose `crusher_blue_iron@17` against current ghost `G` + free cells →
  **INFEASIBLE** (空 candidate pole set)
- 学 cut: `not(ghost_rect=G ∧ crusher_blue_iron[slot=*]=17)` 即:
  在 ghost `G` 下禁止此 pose

## 4. Hardcode cut object ([NEEDS_NEW_FAMILY])

```python
F3_cut = Cut(
    cut_id="F3-power-hitting-001",
    family="power_hitting_set",                  # ← 新 family, Day 13-17 加
    literals=(
        CutLiteral(
            slot_ref=AnonymousSlotRef("crusher_blue_iron", 0),
            pose_id=17,
        ),
    ),
    scope=CutScope(
        ghost_rect_id="<G canonical hash>",      # ← scope 绑 G ghost
        blocked_cells_hash="<G ∪ exterior ∪ mandatory pre-block>",
        source_digest="...",
        artifact_hashes={...},
        oracle_abstraction_version="power_cover_v1",  # 新 oracle (Day 13-17)
        active_assumptions=(
            Assumption(
                key="power_pole_radius",
                value="R=5",                      # canonical_rules.json 上 pole radius
            ),
            Assumption(
                key="power_pole_shape",
                value="1x1_rigid",
            ),
        ),
    ),
    cert=OracleCert(
        cert_kind="power_cover_emptyset",        # 新 cert kind
        cert_payload=canonical_bytes({
            "facility_pose": ("crusher_blue_iron", 17),
            "facility_cells": [(30,30),(30,31),...,(32,32)],
            "pole_radius": 5,
            "candidate_pole_poses_before_ghost": [1, 5, 17, 42, ...],
            "candidate_pole_poses_after_ghost": [],  # ← 空
            "ghost_blocked_pole_cells": [...],        # 哪些 cell 在 ghost 内
            "witness": "hitting_set_emptyset_against_ghost_G",
        }),
        cert_hash="<sha256>",
    ),
    family_version="v1.0",
    validator_version="v1.0",
    payload_schema_version=1,
    oracle_name="power_cover_v1",
    oracle_cert_hash="<sha256>",
    ...
)
```

## 5. `evaluate_cut_as_multiset(cut, state)` + scope-aware replay

### 同 ghost G 下 (cut 应 violate)

```python
result = evaluate_cut_as_multiset(F3_cut, state)
# cut_demand_by_group = {"crusher_blue_iron": Counter({17: 1})}
# state_by_group = {"crusher_blue_iron": Counter({17: 1, ...})}
# Counter({17:1}) ≤ Counter({17:1,...})  → True
assert result == True
```

### 不同 ghost G' 下 (scope-aware HOLD, 同 F4 pattern)

```python
state_G_prime = state.replace(ghost_rect=Rect(60, 60, 5, 5), ...)
replay_result = replay_cut(F3_cut, state_G_prime, store)
# scope.ghost_rect_id != state.ghost_rect_id → AttachDecision.HOLD
assert replay_result == AttachDecision.HOLD
```

### 同 G ghost 但 pole 候选已经 placed (Day 13-17 待定)

若 master 已经选了 pole pose 100 覆盖 pose 17 → power cover not empty →
应该 cut 不 violate? 但 cut literals 只看 `crusher_blue_iron[slot=*]=17`,
不看 pole. 跟 ghost G + pose 17 选 fixed 时 violate, 不管 pole 怎么选.

→ 这暴露 **F3 cut 不充分**: 只在 "ghost G 下 pose 17 完全没法 power 覆盖"
为 sound INFEASIBLE; 若 G 下有部分 pole 候选但 hitting-set INFEASIBLE
(更弱 case), cut 需要含 pole-domain 信息. Day 13-17 加 power_pole literal.

## 6. Schema gaps vs cut_lifecycle_v2 / state_machine_v2

| 检查 | 状态 |
|---|---|
| `CutFamily` enum 加 `"power_hitting_set"` | ❌ [NEEDS_NEW_FAMILY] Day 13-17 |
| `OracleCert.cert_kind` "power_cover_emptyset" | ❌ [NEEDS_NEW_CERT_KIND] Day 13-17 |
| `DerivedDomain.power_cover_domain` carry empty bitset 反例 | ✅ schema 直接支持 |
| `GhostConditionChange` event 触发 power_cover_invalid rebuild | ✅ state_machine_v2 §6 |
| Validator §6 加 Family 7: power_hitting_set | ❌ Day 13-17 |
| Cut literals 只 carry facility pose 是否 sufficient (pole 不显式 literal) | ⚠️ §5 暴露 — Day 13-17 决定加 pole literal 还是用 active_assumption |
| Active assumption `power_pole_radius=R=5` 在 state 怎么 verify | ⚠️ `canonical_rules.json` 内 hash 比对 |
| `state.derived.power_cover_invalid` flag undo on `GhostConditionChange` revert | ✅ §6 undo 路径已定义 |

## 7. Day 13-17 接力清单 (F3 暴露 schema gap)

1. **`CutFamily` enum 加 `power_hitting_set`** + cert_kind `power_cover_emptyset`
2. **Validator Family 7 spec**:
   - cert_payload schema: `{facility_pose, facility_cells, pole_radius, candidate_pole_poses_before_ghost, candidate_pole_poses_after_ghost, ghost_blocked_pole_cells, witness}`
   - 独立重算: 取 state.derived.power_cover_domain[(group, pose)], 验空 bitset; 或重算 pose 在 ghost 下的 candidate pole set 验空
   - 复用: `src/search/benders_loop.py:4219-4268` L16 lazy power completion logic
3. **Family-specific evaluate** (同 F2 暴露): geometric/power cut 跟 multiset
   evaluate 不同 path. Day 13-17 必 split.
4. **Pole literal 必要性**: F3 cert payload 含 pole_poses 但 cut.literals
   只含 facility pose. 待 Day 13-17 决定加 pole literal (更精确 cut).
5. **F3 ↔ L16 关系**: L16 已 land in benders_loop.py:4219-4268
   (lazy power completion). F3 fixture 是 L16 cut 在 v2 framework 内的
   重表达. Day 13-17 把 L16 cut 改写成 power_hitting_set Family 7 形式
   验证 paradigm 兼容.

## 8. 开放 questions

1. **ghost 不挡 pole 但挡 facility 的 case**: ghost 在 facility 内部 (覆盖
   facility cells), pole 都在 ghost 外. 反例核心 facility pose 在 ghost 下
   不 valid (cell ghost-blocked). 这个 case 应该 `pose_domain` 直接 shrink
   掉 pose 17 (state_machine_v2 §6 DomainShrink), 用不到 F3 cut.
2. **Power radius shape**: 当前假设 1×1 pole + Euclidean R=5. 若 game 实际
   power 拓扑 (Manhattan / L∞ / 不规则 polygon), cert payload 要 carry
   shape data.
3. **Multiple poles 覆盖 single facility**: 假设 1 pole 覆盖 1 facility 是
   简化, 实际可能多 pole 一起覆盖 (hitting set 不止 size 1). 待 Day 13-17
   generalize cert payload.
4. **L16 lazy power completion 跟 F3 cut 谁先**: L16 已实施 (env-gated).
   B Design v2 framework 接 L16 logic 成 F3 family. Day 13-17 是 wrap 不是
   重写.

## 9. 验收 status (Day 12)

- ✅ 反例几何 concrete (ghost G 覆盖 R=5 圈住 facility pose 17 → 空 pole set)
- ✅ `state_machine_v2.power_cover_domain` 反例 carry: 空 bitset
- ✅ `GhostConditionChange` trail event 触发路径定义 (§6)
- ✅ Hardcode cut skeleton 写 (literals + cert + scope)
- ⚠️ **5 个 [SCHEMA_GAP] / [NEEDS_NEW_FAMILY]** → Day 13-17 接 §7
- ⚠️ Cut soundness 不充分 (无 pole literal 时不一定 cover all power INFEASIBLE
  case) — Day 13-17 决定加 pole literal
- ⏸ Validator implementation defer to Day 13-17, 复用 L16 logic

F3 close (skeleton + schema gap + L16 复用 path 完整).
