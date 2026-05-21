# Cut Family 8 — power_grid_reach (完整 spec, v3 新 family, F5 反例 owner)

> **Status**: Day 17e v1.1 (2026-05-21) — Gemini round 16 finding B1 修
> **Cross-refs**: `../cut_lifecycle_v2.md` v3.2 + `../red_fixtures/F5_power_grid_disconnect.md` + `../cross_check/gemini_round_14` (F5 反例提出) + `../cross_check/gemini_round_15` (独立 family verdict) + `../cross_check/gemini_round_16` (B1 算法 unsound finding)
> **Mode**: geometric (_FAMILY_MODE_MAP)
> **Family_version**: v1.1 (ghost_blocks_line 改严格 line-segment AABB intersection)
> **来源**: Gemini round 14 F5 反例 + round 15 Family 8 独立 family 推荐

## 0. Changelog

- **v1.0** (Day 17b, commit 1c757ff): F5 全局电力孤岛反例 owner.
- **v1.1** (Day 17e/f): 修 2 round bug:
  - 17e (Gemini round 16 B1): §5a `ghost_blocks_line` 算法简化版 "ghost 中心
    点 ∩ line(p1, p2)" 绝对 unsound (线段可切 ghost 边角不过中心点 → False
    Negative). 改严格 line-segment to AABB intersection (Liang-Barsky 裁剪).
  - 17f (Gemini round 17 B1): §8 watcher v1.0 by_cell 只 carry candidate_pole_cells
    (生成时 CoverSet). cell_owner 占的 cell 释放后变新 pole 候选时 watcher
    不 trigger → False Positive 误剪. v1.1 改监听 `PoolPole ∩
    BoundingBox(facility, R_conn)` 内所有合法 grid cell.

## 1. 数学定义

### 1a. Power network 连通性

Power network 不是 belt 那种连续 free_cell graph, 是**离散 pole 跃迁 graph**:

- Pole pose `q1`, `q2` 互联 iff geometric distance ≤ `R_conn` (e.g. R_conn=10)
- protocol_core (全局电力枢纽) 是 source, 必须连到所有 powered facility 的
  candidate pole
- Power network = Graph G_power = (V_pole, E_jump), V_pole = candidate pole
  poses + protocol_core, E_jump = pole 对 within R_conn (允许 placement)

### 1b. Cut 形式

Family 8 cut 表达:

```
∃ facility A with CoverSet(A) ⊆ V_pole_subset, V_pole_subset 不连到 protocol_core
                                in G_power constrained by ghost
            ⇒ INFEASIBLE (A 永远无法供电)
```

跟 Family 7 power_hitting_set 区别 (key!):
- **Family 7**: A 的 CoverSet **空** (没 pole 候选, local 问题)
- **Family 8**: A 的 CoverSet **非空** 但 candidate poles 跟 protocol_core
  跨 ghost **不可达** (global connectivity 问题)

### 1c. F5 反例 (Gemini round 14)

- ghost 纵切宽 15 把 grid 切 Left/Right
- protocol_core 在 Left (10, 10), crusher_A 在 Right (60, 60)
- pole R_conn = 10, ghost 宽 15 → 任何 Left 的 pole 跟 Right 的 pole 距离 >
  15 > 10, **不可跃迁**
- Family 7 局部 CoverSet(crusher_A) 非空 (Right 区 pole 多) → Family 7 静默
- Family 4 component_reach 看 **belt** graph, F5 belt 内部闭环 (crusher_A
  + shop_B 内部连接) → Family 4 静默
- Family 8 应拦: crusher_A 的 candidate pole 在 power graph 上不连到
  protocol_core → INFEASIBLE

### 1d. 跟 Family 4 component_reach 区别 (Gemini round 15 verdict)

|  | Family 4 belt | Family 8 power |
|---|---|---|
| Graph V | free_cells | candidate pole poses + protocol_core |
| Graph E | 相邻 free_cell | within R_conn distance |
| Connectivity 判定 | BFS on free_cells | BFS on pole jump graph |
| Capacity | binary reachability | binary reachability |
| Schema 字段 | src_cell / sink_cell / separator_cells | source_pole_set / target_protocol_core / jump_radius / blocked_pole_cells |

Gemini round 15 强烈支持独立 Family 8: 强行 generalize Family 4 会让 Schema
变 union type, Validator 逻辑充满 `if-else`. **独立 family**.

## 2. Soundness proof

### 2a. Connectivity monotonicity

state.free_cells 单调缩 (placement 加 cell_owner). pole candidate set 跟
free_cells 一致单调缩 → power network connectivity 单调减弱. 若 ghost-bound
state 下 BFS disconnect, 后续 state 仍 disconnect (单调保持).

### 2b. F5 反例数学

- ghost width = 15, pole R_conn = 10 → 任何 pole pair p1 ∈ Left, p2 ∈ Right
  距离 ≥ ghost width = 15 > R_conn → E_jump(p1, p2) = False
- Right 区 pole 集 P_R, Left 区 pole 集 P_L (含 protocol_core)
- BFS from protocol_core ⊆ P_L, 终点不在 P_R → P_R 上的 facility 不可供电
  → 任 A ∈ Right 区的 powered facility INFEASIBLE

### 2c. Scope 限定

connectivity 依赖:
- ghost_rect (key, 切 power network 的根因)
- canonical_rules `power_pole_radius` R_conn (source-of-truth)
- protocol_core 位置 (master 端选, 通常固定)

scope: ghost_rect_id 必非 GHOST_AGNOSTIC + active_assumption
`power_pole_radius=R=10` + `protocol_core_position=(10,10)` (后者 state-conditioned
或 source-of-truth, Day 18 决定).

## 3. Cert payload schema

```python
@dataclass(frozen=True)
class PowerGridReachCert:
    """cert_kind = "power_pole_bfs_disconnect_witness"."""
    facility_pose: Tuple[GroupId, PoseId]
                                            # 受影响的 powered facility
    facility_cells: Tuple[Tuple[int, int], ...]

    # power network 描述
    pole_radius: float                      # R_conn
    protocol_core_cell: Tuple[int, int]     # 全局电力源
    candidate_pole_poses: Tuple[int, ...]   # CoverSet(facility_pose) — 非空但孤立
    candidate_pole_cells: Tuple[Tuple[int, int], ...]
                                            # candidate pole 的 cell 位置 (替代 pose id)

    # disconnect witness
    source_component_pole_set: Tuple[int, ...]  # protocol_core 所在 power graph component
    target_component_pole_set: Tuple[int, ...]  # facility candidate 所在 component
    disconnect_witness_kind: Literal["ghost_blocks_jump", "exterior_blocks_jump"]
    blocking_ghost_cells: Tuple[Tuple[int, int], ...]
                                            # ghost 内挡住跃迁的 cells

    # F8 specific: full power graph snapshot (canonical bytes, replay 重建)
    power_graph_b64: str                    # 编码 (V_pole, E_jump) graph

    # ghost 信息 (跟 scope.ghost_rect_id 一致, replay 二保)
    ghost_rect_repr: Tuple[int, int, int, int]
```

## 4. Cut object 构造

geometric mode, ghost-bound scope:

```python
cut = Cut(
    family="power_grid_reach", literals=None,
    geometric_payload=canonical_bytes(PowerGridReachCert.asdict()),
    scope=CutScope(
        ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),  # 必非 AGNOSTIC
        blocked_cells_hash=compute_blocked_cells_hash(state),
        source_digest=...,
        artifact_hashes={...},
        oracle_abstraction_version="power_grid_reach_v1",
        active_assumptions=(
            Assumption("power_pole_radius", value=f"R={pole_radius}"),
            Assumption("protocol_core_position", value=f"({pc[0]},{pc[1]})"),
        ),
    ),
    cert=OracleCert(cert_kind="power_pole_bfs_disconnect_witness", ...),
)
```

## 5. Generator

### 5a. Power network 构建

```python
def build_power_network(state: BState, pole_radius: float) -> "PowerGraph":
    """V_pole = candidate pole poses 在 state.free_cells 上 + protocol_core.
       E_jump = pole 对 distance ≤ pole_radius, 且 jump 路径不被 ghost block.

    v1.1 (Gemini round 16 finding B1 critical sound bug 修):
    ghost_blocks_line 必须用严格 line-segment to AABB intersection (Liang-Barsky
    裁剪), 不能用 v1.0 简化版 "ghost 中心点 ∩ line(p1, p2)" — 后者漏判线段
    切 ghost 边角不过中心点的 case (False Negative 漏发 cut).
    """
    candidate_poles = enumerate_candidate_poles(state.free_cells)
    pc_cell = state.protocol_core_cell  # state field 或 canonical_rules constant
    V = candidate_poles | {pc_cell}
    E = set()
    for p1 in V:
        for p2 in V:
            if p1 != p2 and euclidean_distance(p1, p2) <= pole_radius:
                # v1.1 严格 AABB intersection: line-segment (p1, p2) 跟
                # ghost rectangle 任意 intersection 都阻断 jump
                if not line_segment_intersects_aabb(p1, p2, state.ghost_rect):
                    E.add((p1, p2))
    return PowerGraph(V, E)


def line_segment_intersects_aabb(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    rect: Tuple[int, int, int, int],  # (x, y, h, w)
) -> bool:
    """Liang-Barsky line clipping. 返 True iff line segment p1→p2 intersects
    AABB rectangle (含边).

    经典计算几何, sound: 任何切 ghost 边角的线段都被识别.
    """
    x_min, y_min = rect[0], rect[1]
    x_max, y_max = rect[0] + rect[2], rect[1] + rect[3]

    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    t0, t1 = 0.0, 1.0

    # 4 边 inside-test via parametric form
    for p, q in [(-dx, p1[0] - x_min),
                  ( dx, x_max - p1[0]),
                  (-dy, p1[1] - y_min),
                  ( dy, y_max - p1[1])]:
        if p == 0:
            if q < 0:
                return False  # 平行边外
        else:
            r = q / p
            if p < 0:
                if r > t1:
                    return False
                if r > t0:
                    t0 = r
            else:
                if r < t0:
                    return False
                if r < t1:
                    t1 = r
    return t0 <= t1  # 有交点 → block jump


# (PoC scope: ghost_cells 离散版若仍需要, 可走 cell-by-cell DDA line raster
# 化, 但严格 AABB intersection 已 sound 不需要 cell 版.)
```

### 5b. Disconnect detection

```python
class PowerGridReachOracle:
    name = "power_grid_reach_v1"

    def generate(self, state, master_solution) -> List[Cut]:
        cuts = []
        pole_radius = canonical_rules["power_pole"]["radius"]
        power_graph = build_power_network(state, pole_radius)
        pc_component = bfs_component(power_graph, state.protocol_core_cell)

        for placed in master_solution.placed_facility_poses:
            if not requires_power(placed.facility_group):
                continue
            # CoverSet(placed) — Family 7 已检查空集 case
            cover_set = compute_cover_set(placed, state.ghost_rect, state.free_cells)
            if not cover_set:
                continue  # Family 7 handles, F8 skip

            # F8 trigger: CoverSet 非空但全在不连 protocol_core 的 component
            target_component = bfs_component(power_graph,
                                              next(iter(cover_set)))  # 任 1 pole 的 component
            if target_component != pc_component:
                # Disconnect detected!
                cert = PowerGridReachCert(
                    facility_pose=(placed.facility_group, placed.pose_id),
                    facility_cells=tuple(placed.cells),
                    pole_radius=pole_radius,
                    protocol_core_cell=state.protocol_core_cell,
                    candidate_pole_poses=tuple(cover_set),
                    candidate_pole_cells=tuple(pole_id_to_cell(p) for p in cover_set),
                    source_component_pole_set=tuple(sorted(pc_component)),
                    target_component_pole_set=tuple(sorted(target_component)),
                    disconnect_witness_kind="ghost_blocks_jump",
                    blocking_ghost_cells=tuple(sorted(state.ghost_cells)),
                    power_graph_b64=encode_power_graph(power_graph),
                    ghost_rect_repr=tuple(state.ghost_rect),
                )
                cuts.append(construct_power_grid_reach_cut(state, cert))
        return cuts
```

### 5c. Minimize (Step 2)

F8 v1.0 cut 已 minimal — facility_pose + ghost. ghost-witness 不需要 QuickXplain
shrink (整 ghost 是 cause).

v1.1 generalize 后 (cell_owner 挤压 power network): 走 QuickXplain on
master_solution.placed_facility_poses subset.

## 6. evaluate_geometric

```python
def evaluate_geometric_power_grid_reach(cut: Cut, state: BState) -> bool:
    """重算当前 power network 上 facility's CoverSet 是否仍跟 protocol_core
    disconnect.

    跟 Family 4 component_reach evaluate 同 pattern: 必须 hot path 重算
    (state.free_cells / ghost 变可能 reconnect).
    """
    cert = decode_power_grid_reach_cert(cut.geometric_payload)
    pole_radius = cert.pole_radius
    pc_cell = cert.protocol_core_cell

    # 重算 power network on current state
    power_graph = build_power_network(state, pole_radius)
    pc_component = bfs_component(power_graph, pc_cell)

    # facility CoverSet 仍在不连 protocol_core 的 component?
    facility_group, facility_pose_id = cert.facility_pose
    if (facility_group, facility_pose_id) not in [
        (g, p) for g, slots in state.groups.items() for _, p in slots.selected_poses
    ]:
        # facility 不再 selected, cut 不 trigger
        return False

    current_cover_set = compute_cover_set(
        cert.facility_pose, state.ghost_rect, state.free_cells
    )
    if not current_cover_set:
        return False  # Family 7 takes over

    target_component = bfs_component(power_graph, next(iter(current_cover_set)))
    return target_component != pc_component
```

## 7. Validator

```python
class PowerGridReachValidator(CutValidator):
    family = "power_grid_reach"
    validator_version = "v1.0"

    def validate(self, cut, state) -> ValidationResult:
        cert = decode_power_grid_reach_cert(cut.cert.cert_payload)
        # 1. 验 pole_radius 跟 canonical_rules 一致 (source rotated 检查)
        if cert.pole_radius != canonical_rules["power_pole"]["radius"]:
            return ValidationResult("unsound", ..., "pole_radius mismatch")
        # 2. 验 ghost_rect_repr 跟当前 state 一致
        if cert.ghost_rect_repr != tuple(state.ghost_rect):
            return ValidationResult("unsound", ..., "ghost_rect mismatch")
        # 3. 独立重建 power network on cur state
        recomputed_power_graph = build_power_network(state, cert.pole_radius)
        pc_component_recomputed = bfs_component(recomputed_power_graph,
                                                  cert.protocol_core_cell)
        if frozenset(pc_component_recomputed) != frozenset(cert.source_component_pole_set):
            return ValidationResult("unsound", ..., "pc_component reconnected/changed")
        # 4. 验 candidate_pole_poses 仍在 target_component
        cover_recomputed = compute_cover_set(cert.facility_pose, state.ghost_rect, state.free_cells)
        if not cover_recomputed:
            return ValidationResult("unsound", ..., "Family 8 cert but CoverSet empty (Family 7 case)")
        target_component_recomputed = bfs_component(recomputed_power_graph,
                                                     next(iter(cover_recomputed)))
        if pc_component_recomputed == target_component_recomputed:
            return ValidationResult("unsound", ..., "F8 witness fail: power reconnected")
        return ValidationResult("ok", ...)

    def evaluate_geometric(self, cut, state):
        return evaluate_geometric_power_grid_reach(cut, state)
```

## 8. Replay + watcher (v1.1 修 Gemini round 17 B1)

按 v3.1 §4 6 步 verify. watcher:
- by_cell_watcher: **v1.1 改** — 不止 `candidate_pole_cells` (生成时 CoverSet),
  必须监听 `PoolPole ∩ BoundingBox(facility_pose, R_conn)` 内**所有**合法 grid
  cell. 原因 (Gemini round 17 B1): cell_owner 占的 cell 当前不在
  candidate_pole_cells, master 移走后那 cell 释放成新 pole 候选 →
  power network reconnect. v1.0 watcher 不监听此 cell → False Positive 误剪.
- by_pose_watcher (facility_pose)
- by_ghost_watcher (Day 17d 加, ghost 变直接 invalidate)
- 不需 by_group_watcher (F8 单 facility, 不跨 group)

```python
def add_watchers_power_grid_reach(store: CutStore, cut: Cut) -> None:
    cert = decode_power_grid_reach_cert(cut.geometric_payload)

    # facility cells
    for cell in cert.facility_cells:
        store.by_cell_watcher[cell].add(cut.cut_id)

    # v1.1: 监听 BoundingBox(facility, R_conn) ∩ PoolPole 全合法 grid cell
    # (不止 candidate_pole_cells, 防 cell_owner 释放后 reconnect 误剪)
    bb = compute_bounding_box(cert.facility_cells, cert.pole_radius)
    for cell in iter_cells_in_box(bb):
        if is_legal_pole_candidate_cell(cell):  # PoolPole 内
            store.by_cell_watcher[cell].add(cut.cut_id)

    # 其他维 (pose, ghost) 不变
    store.by_pose_watcher[cert.facility_pose].add(cut.cut_id)
    store.by_ghost_watcher[cut.scope.ghost_rect_id].add(cut.cut_id)
```

## 9. 跟 Family 7 power_hitting_set 协调 (cut store dedup)

Family 7 拦 CoverSet **空** (local), Family 8 拦 CoverSet **非空但跟 protocol_core
disconnect** (global). 应该**互斥** trigger:

```python
# Oracle 顺序: Family 7 → Family 8
if cover_set_empty:
    emit_family_7_cut(...)
else:
    if not connected_to_protocol_core:
        emit_family_8_cut(...)
```

cut store dedup: 同 (facility_group, facility_pose_id, ghost_rect_id) 不应同时
有 F7 + F8 cut.

## 10. Open questions

1. **Ghost-block-jump 算法**: cur §5a 简化 ghost 中心点 ∩ line(p1, p2). 真实
   pole-pole 跃迁应是 line-segment intersect ghost rectangle. Phase 1 真算法.
2. **v1.1 cell_owner 挤压 power network**: cur v1.0 单 cause = ghost. cell_owner
   挤压 (相邻 pole 候选被 facility 占) 也可 disconnect. Phase 1 加 causation
   split sub_kind (类 F7).
3. **Multi-facility shared disconnect**: 多 facility 都在 target_component, 1
   cut 拦 1 facility. cut store 累积 N facility 的 N cut → 是否合并 region-cut.
4. **Protocol_core 多个 case**: 现 spec 假设 protocol_core 唯一 source. canonical_rules
   有 1 个 protocol_core 但游戏未来扩展可能多源. Phase 2 generalize.
5. **跟 belt routing 配合**: belt 经过 ghost 的 case 跟 power 不一样 (belt 连续
   free_cells, power 跨 cell pole jump). cut 应分发到 Family 4 vs Family 8.

## 11. Implementation pre-decision

- `PowerGridReachValidator` 实现: `src/cuts/families/power_grid_reach.py` (Phase 1)
- `build_power_network` helper: `src/cuts/helpers/power_network.py` (Phase 1, 新)
- `bfs_component`: 复用 `src/search/d2_separator.py:compute_bfs_components` 但
  on pole jump graph (graph kind 传参化)
- 测试 fixture: `src/tests/cuts/test_family_8_power_grid_reach.py` (Phase 1)
- F5 fixture (Day 17d) 验 cert/validator round-trip
- A/B 测试: Family 7 + 8 协作避免 cut store 冗余

## 12. 验收

- ✅ 数学定义 (power network jump graph + BFS disconnect)
- ✅ Soundness proof (connectivity monotonicity + F5 反例数学)
- ✅ Cert schema (PowerGridReachCert 含 pole_radius / protocol_core / candidate
  pole + ghost 信息 + power graph snapshot)
- ✅ Cut 构造 (geometric, ghost-bound)
- ✅ Generator (build_power_network + bfs_component + disconnect detection)
- ✅ evaluate_geometric (hot path 重算, 跟 Family 4 同 pattern)
- ✅ Validator 4 步 (pole_radius / ghost / power graph / target_component)
- ✅ Replay + watcher (6 维 by_ghost Day 17d 加)
- ✅ Family 7 协调 dedup 政策
- ⚠️ 5 open question (ghost-line algorithm / v1.1 cell_owner causation /
  multi-facility merge / multi-protocol_core / belt-power 分发)
- ⏸ Phase 1 实施 + F5 fixture round-trip 测试
