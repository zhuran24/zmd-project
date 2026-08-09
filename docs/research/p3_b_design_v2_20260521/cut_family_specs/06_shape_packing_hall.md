# Cut Family 6 — shape_packing_hall (完整 spec, v3 新 family)

> **Status**: Day 16c v1.1 (2026-05-21) — Gemini round 14 cross-check 修
> **Cross-refs**: `../cut_lifecycle_v2.md` v3 §3 §4 §5 §6 + `../red_fixtures/F2_shape_packing_hall.md` + `../cross_check/gemini_round_14_cut_families.md`
> **Mode**: geometric (_FAMILY_MODE_MAP)
> **Family_version**: v1.1 (geometric partition 只依赖 ghost + exterior, 不依赖 cell_owner)
> **来源**: Gemini round 12 v14 review 反例 B

## Changelog

- **v1.0** (Day 16a, commit 30b0a2d): 初版 12 段 spec
- **v1.1** (Day 16c, 本 commit): 修 Gemini round 14 finding #2 **致命 replay bug** —
  `compute_baseline_partition_lens` v1.0 包 `cell_owner.keys()` 使 partition
  state-dependent, 深层学的 cut 回浅层 cell_owner 空 → recompute lens 跟 cert
  不一致 → Validator 永久 Quarantine, Family 6 cut 跨层活不下来. v1.1 partition
  **只**依赖 ghost + exterior_blocks (static), cell_owner 不入 partition. 若需
  cell_owner 碎片化路径走 Family 5 pattern_nogood (literal-based) 而非 geometric.

## 1. 数学定义

### 1a. Cut 形式

设 `R` 是 region (e.g. left baseline), `R` 被 ghost `G` 切成 maximal-free
intervals `I_1, I_2, ..., I_k`. 每个 interval `I_j` 有 length `len(I_j)`.
Mandatory pose 是 rigid shape `1 × L` (L = pose_length), 必须连续占 L 个 cells.

定义 `max_packable(I_j, L) = ⌊len(I_j) / L⌋` — 此 interval 最多放 pose 数.

Hall infeasibility:

```
sum_{j=1..k} max_packable(I_j, L) < demand    (4) Hall witness
                                  ⇒  INFEASIBLE
```

Cut 触发 (4): 当各 interval 能容纳的 pose 数之和 < demand → INFEASIBLE.
跟 Family 1 region_capacity 区别: region_capacity 看 cell 总数, shape_hall
看 **interval 切片能否各装下 pose** (rigid shape constraint).

### 1b. F2 反例 (Gemini 反例 B)

- left baseline length 10, ghost 占 (x=0, y=4) 单格切两段
- 段 A length 4, 段 B length 5, 总 9 cells
- pose_length L = 3, demand = 3
- region_capacity 看 `cells_in_region = 9 ≥ demand × L = 9` → **pass**
- shape_packing_hall 看 `⌊4/3⌋ + ⌊5/3⌋ = 1 + 1 = 2 < 3` → **INFEASIBLE** ✅

### 1c. Generalization (mixed pose lengths)

Boundary_storage_port 是 1×3 rigid, 但其他 facility (crusher 3×3 / refinery
5×5 / etc) shape 不一. Hall condition 推广到多 shape:

```
Let demand vector d = (d_L1, d_L2, ...) by pose shape length.
Let interval i provide (i_L1, i_L2, ...) = (⌊len(I_i)/L1⌋, ⌊len(I_i)/L2⌋, ...).
Feasible iff there exists nonneg integer assignment x_{i,L}:
    sum_L L * x_{i,L} ≤ len(I_i)   ∀i (cell constraint)
    sum_i x_{i,L} ≥ d_L            ∀L (demand)
```

这是 **bin packing with multiple item sizes** 问题. NP-hard in general
(reduction from PARTITION). 但 boundary_storage_port + crusher_etc 都是
fixed L → small constant # shapes → polynomial special case.

**Phase 0 spec scope**: single shape (L = 3 boundary port). Multi-shape
Phase 1 + Family 6 v1.1.

### 1d. 跟 LP relaxation 关系

Single-shape Hall ≡ LP relaxation `min Σ x_{i,j}` s.t. `Σ_j x_{i,j} ≤
max_packable(I_i, L); Σ_i x_{i,j} = 1 ∀ j ∈ {1..demand}` is INFEASIBLE
when (4) holds. Farkas dual ray gives Hall witness.

Multi-shape LP relaxation 仍 sound but **不 tight** (LP gap → 实际
infeasible 但 LP feasible). Phase 1 + 用 ILP exact.

## 2. Soundness proof

### 2a. Single-shape (现实施 scope)

**引理 (interval packing upper bound)**: 在 length `L` cells 的 interval
`I` 上, rigid `1 × L` pose 数上界是 `⌊len(I) / L⌋`.

**证明**: pose 占 L 连续 cells. K 个 pose 占 K * L cells. 不重叠条件 → K * L
≤ len(I) → K ≤ ⌊len(I) / L⌋. ∎

**主定理**: (4) 蕴含 INFEASIBLE.

**证明**: 总 placed pose 数 ≤ Σ_j max_packable(I_j, L) (每 interval 独立).
若 Σ < demand → 必少放 → INFEASIBLE. ∎

### 2b. Multi-shape (Phase 1 待证)

Hall's marriage theorem: bipartite graph `(intervals, demand slots)` with
edge `(i, j)` iff demand `j` 的 shape `L_j` fits in interval `i`. 完美 matching
存在 iff for all subset `S ⊆ demand slots`, `|N(S)| ≥ |S|` (Hall condition).

Multi-shape capacity: 每 interval 能 host 多 pose, 上是 `weighted` Hall:
`Σ_{i ∈ N(S)} max_packable(I_i, L_j) ≥ |S|` ∀ subset S. 这是 polynomial
verifiable iff demand 全 same shape — 否则 PARTITION-reducible.

Phase 1 多 shape exact 走 ILP feasibility check on small partition (≤ 20 intervals).

### 2c. Scope 限定

`max_packable` 依赖:
- ghost_rect (影响 partition_lens)
- canonical_rules pose shape (L) — source-of-truth
- mandatory_exact_instances demand — source-of-truth

→ scope carry: ghost_rect_id (非 GHOST_AGNOSTIC, ghost 关键) + source_digest
+ active_assumption `boundary_pose_shape=<L>x<W>_rigid` + `boundary_region=<kind>`.

## 3. Cert payload schema

```python
@dataclass(frozen=True)
class ShapePackingHallCert:
    """Cert for Family 6 shape_packing_hall cut.

    cert.cert_kind = "hall_interval_witness"
    """
    region_kind: Literal["left_baseline", "bottom_baseline"]  # Phase 0: only baseline
    region_total_length: int                # e.g. 70 for left baseline

    # ghost-induced partition (computed in scope of ghost)
    partition_lens: Tuple[int, ...]         # e.g. (4, 5) for F2 反例
    partition_offsets: Tuple[int, ...]      # 每段 start cell in region (debug)

    pose_length: int                         # L = 3 for boundary_storage_port
    pose_shape_canonical: str                # e.g. "1x3_rigid"

    max_packable: Tuple[int, ...]            # per interval: ⌊len/L⌋
    total_packable: int                      # sum(max_packable)
    demand: int                              # demand_R for this shape
    gap: int                                 # demand - total_packable (> 0)

    # 单 shape only (Phase 0); multi-shape Phase 1 加 demand_by_shape: Dict[L, int]
    contributing_group: GroupId              # 单 group (boundary_storage_port)

    # LP dual / Farkas witness (optional, Phase 1)
    lp_dual_ray_b64: Optional[str] = None
    lp_dual_objective: Optional[float] = None
```

cert_payload bytes = `canonical_bytes(ShapePackingHallCert.asdict())`.
cert_hash = sha256(cert_payload).

## 4. Cut object 构造

按 `cut_lifecycle_v2 v3 §3` Cut schema, shape_packing_hall 是 **geometric**:

```python
def construct_shape_hall_cut(state: BState, witness: ShapePackingHallCert) -> Cut:
    return Cut(
        cut_id=uuid4().hex,
        family="shape_packing_hall",
        literals=None,                              # geometric
        geometric_payload=canonical_bytes(witness.asdict()),
        scope=CutScope(
            ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),  # 非 AGNOSTIC
            blocked_cells_hash=compute_blocked_cells_hash(state),
            source_digest=compute_source_digest(state).canonical_hash(),
            artifact_hashes={
                "canonical_rules.json": sha256_file("rules/canonical_rules.json"),
                "candidate_placements.json": sha256_file("data/preprocessed/candidate_placements.json"),
                "mandatory_exact_instances.json": sha256_file("data/preprocessed/mandatory_exact_instances.json"),
            },
            oracle_abstraction_version="shape_hall_v1",
            active_assumptions=(
                Assumption(
                    key="boundary_pose_shape",
                    value=witness.pose_shape_canonical,
                ),
                Assumption(
                    key="boundary_region",
                    value=witness.region_kind,
                ),
            ),
        ),
        cert=OracleCert(
            cert_kind="hall_interval_witness",
            cert_payload=canonical_bytes(witness.asdict()),
            cert_hash=sha256(...).hexdigest(),
        ),
        family_version="v1.0",
        validator_version="v1.0",
        payload_schema_version=1,
        oracle_name="shape_hall_v1",
        oracle_cert_hash=...,
    )
```

## 5. Generator algorithm

### 5a. Partition lens 计算 helper

```python
def compute_baseline_partition_lens(
    region_kind: Literal["left_baseline", "bottom_baseline"],
    state: BState,
) -> Tuple[List[int], List[int]]:
    """v1.1 改 — 只依赖 ghost + exterior_blocks (static), **不**依赖 cell_owner.

    Why: Gemini round 14 finding #2 — v1.0 包 cell_owner 后 partition 是 state-
    dependent, 深层学的 cut 回浅层因 cell_owner 不同 recompute lens 全变 → Validator
    永久 Quarantine. v1.1 partition 只 carry static structural 信息, cell_owner
    碎片化场景走 Family 5 pattern_nogood (literal-based).

    Returns (partition_lens, partition_offsets):
        e.g. left baseline length 70, ghost 占 (0, 30) 单格 →
             partition_lens=[30, 39], partition_offsets=[0, 31]
    """
    region_cells = compute_region_cells(region_kind)   # ordered along baseline
    blocked = set()
    # ghost cells
    if state.ghost_rect is not None:
        blocked.update(state.ghost_cells)
    # exterior_blocks (static map blocks 来自 canonical_rules / mandatory_exact_instances)
    blocked.update(state.exterior_blocks)
    # !!! 不再 update cell_owner.keys() —— v1.1 critical fix !!!
    # cell_owner 碎片化的场景走 Family 5 pattern_nogood 不走 Family 6

    # Scan baseline, split on blocked cells
    partition_lens, partition_offsets = [], []
    current_len, current_offset = 0, 0
    for idx, cell in enumerate(region_cells):
        if cell in blocked:
            if current_len > 0:
                partition_lens.append(current_len)
                partition_offsets.append(current_offset)
            current_len = 0
            current_offset = idx + 1
        else:
            if current_len == 0:
                current_offset = idx
            current_len += 1
    if current_len > 0:
        partition_lens.append(current_len)
        partition_offsets.append(current_offset)
    return partition_lens, partition_offsets
```

### 5a.bis Demand 计算 — v1.1 改

partition 改 static 后, `demand = state.groups[contributing_group].remaining_count`
也变成 state-dependent → cut 跨层 validator 重算 `state.groups[gid].remaining_count`
跟 cert 不一致仍 quarantine.

v1.1 改: demand 用 **group.demand** (initial 总 demand) 而不是 remaining_count, +
cert.contributing_groups 标 `(group_id, total_demand_at_gen)`. Validator 比 cert
跟 canonical_rules group demand. group demand 是 source-of-truth, 不会 state-dep.

```python
# v1.1: demand 用 group.demand (source-of-truth) 不是 remaining_count (state-dep)
demand = state.groups[contributing_group].demand   # ← 改
```

### 5b. Hall infeasibility detect

```python
def detect_shape_hall_infeasibility(
    state: BState,
    region_kind: Literal["left_baseline", "bottom_baseline"],
    contributing_group: GroupId,
) -> Optional[ShapePackingHallCert]:
    """对 single region + single contributing group 检 Hall infeasibility.

    Phase 0: single shape (boundary_storage_port 1×3 rigid).
    Phase 1: multi-shape generalize (ILP feasibility on partition).
    """
    pose_length = canonical_rules[contributing_group]["pose_shape"]["length"]  # = 3
    demand = state.groups[contributing_group].remaining_count * 1  # 单 pose / instance

    partition_lens, partition_offsets = compute_baseline_partition_lens(region_kind, state)
    max_packable = [length // pose_length for length in partition_lens]
    total_packable = sum(max_packable)

    if total_packable >= demand:
        return None  # feasible, no cut

    return ShapePackingHallCert(
        region_kind=region_kind,
        region_total_length=len(compute_region_cells(region_kind)),
        partition_lens=tuple(partition_lens),
        partition_offsets=tuple(partition_offsets),
        pose_length=pose_length,
        pose_shape_canonical=f"{pose_length}x{1}_rigid",
        max_packable=tuple(max_packable),
        total_packable=total_packable,
        demand=demand,
        gap=demand - total_packable,
        contributing_group=contributing_group,
    )
```

### 5c. Generator 入口 (Phase 1 oracle)

```python
class ShapeHallOracle:
    name = "shape_hall_v1"

    def generate(self, state: BState) -> List[Cut]:
        """For each baseline region + each boundary group, check Hall."""
        cuts = []
        for region_kind in ["left_baseline", "bottom_baseline"]:
            for gid in self._boundary_groups():
                witness = detect_shape_hall_infeasibility(state, region_kind, gid)
                if witness is not None:
                    cuts.append(construct_shape_hall_cut(state, witness))
        return cuts
```

### 5d. Minimize / Normalize (Step 2)

shape_hall cert 的 minimal core 是 `partition_lens` 子集 — 选最少 partition
使 sum `max_packable` 仍 < demand. 但 partition 是 ghost-induced 固有结构, 不
可选 subset (cut 必须 carry 全 partition 让 replay 验). → minimize 是 no-op
(partition 已是 minimal).

Multi-shape phase 1 走 QuickXplain on contributing_groups subset.

## 6. evaluate_geometric (hot path)

```python
def evaluate_geometric_shape_hall(cut: Cut, state: BState) -> bool:
    """shape_packing_hall hot path. v3 §5 family-dispatch.

    重算当前 state 内 partition + total_packable, 验是否仍 < cert.demand.
    若 ghost change → partition 变 → cap 可能变.
    """
    cert_dict = json.loads(canonical_bytes_decode(cut.geometric_payload))
    region_kind = cert_dict["region_kind"]
    pose_length = cert_dict["pose_length"]
    demand = cert_dict["demand"]

    # 重算当前 partition
    current_lens, _ = compute_baseline_partition_lens(region_kind, state)
    current_total_packable = sum(length // pose_length for length in current_lens)

    return current_total_packable < demand
```

跟 Family 1 evaluate_geometric 区别: Family 1 cert 在 scope 内 always violate
(cap_R/demand_R 都 fixed); shape_hall cert 需要重算 partition (ghost 间接
影响). 所以 evaluate_geometric 不 trivial.

## 7. Validator (Step 5) — 独立重算

```python
class ShapeHallValidator(CutValidator):
    family = "shape_packing_hall"
    validator_version = "v1.0"

    def validate(self, cut: Cut, state: BState) -> ValidationResult:
        start = time.monotonic()
        try:
            cert_dict = json.loads(canonical_bytes_decode(cut.geometric_payload))
            region_kind = cert_dict["region_kind"]
            pose_length = cert_dict["pose_length"]
            cert_demand = cert_dict["demand"]
            cert_partition_lens = cert_dict["partition_lens"]
            cert_total_packable = cert_dict["total_packable"]

            # 1. 重算 partition (验 ghost + cell_owner 一致性)
            recomputed_lens, _ = compute_baseline_partition_lens(region_kind, state)
            if tuple(recomputed_lens) != tuple(cert_partition_lens):
                # ghost 或 cell_owner 已变 → cert 不在 cur scope sound
                return ValidationResult(
                    kind="unsound", elapsed_seconds=time.monotonic() - start,
                    detail=f"partition_lens mismatch: cert={cert_partition_lens}, recomputed={recomputed_lens}",
                )

            # 2. 重算 max_packable + total_packable
            recomputed_max_packable = [length // pose_length for length in recomputed_lens]
            recomputed_total = sum(recomputed_max_packable)
            if recomputed_total != cert_total_packable:
                return ValidationResult(
                    kind="unsound", elapsed_seconds=time.monotonic() - start,
                    detail=f"total_packable mismatch: cert={cert_total_packable}, recomputed={recomputed_total}",
                )

            # 3. 验 Hall witness (4): total_packable < demand
            if recomputed_total >= cert_demand:
                return ValidationResult(
                    kind="unsound", elapsed_seconds=time.monotonic() - start,
                    detail=f"witness fail: total_packable={recomputed_total} ≥ demand={cert_demand}",
                )

            # 4. v1.1 改 — demand 用 group.demand (source-of-truth) 比对, 不用 remaining_count
            #
            # Why: v1.0 用 remaining_count → state-dep, 跨层 quarantine. v1.1 用
            # group.demand (canonical_rules source-of-truth), state-independent
            # → 跨层 cut 仍 sound.
            gid = cert_dict["contributing_group"]
            if state.groups[gid].demand != cert_demand:
                # group demand 改 → source-of-truth rotated → quarantine
                return ValidationResult(
                    kind="unsound", elapsed_seconds=time.monotonic() - start,
                    detail=f"demand mismatch: cert={cert_demand}, group.demand={state.groups[gid].demand} (source-of-truth rotated)",
                )

            return ValidationResult(kind="ok", elapsed_seconds=time.monotonic() - start)
        except Exception as e:
            return ValidationResult(
                kind="schema_err", elapsed_seconds=time.monotonic() - start,
                detail=str(e),
            )

    def evaluate_geometric(self, cut: Cut, state: BState) -> bool:
        return evaluate_geometric_shape_hall(cut, state)
```

### 7b. multi-shape generalize (Phase 1)

Phase 1 multi-shape: validator 跑 ILP `feasibility(partition, demands_by_shape)`
in 1s budget. Phase 0 单 shape 走 closed-form ⌊·/L⌋.

## 8. Replay (Step 9)

按 cut_lifecycle_v2 v3 §4 replay 算法 + Family 6 特殊:

1. Step 1 source_digest: 比 canonical_rules / candidate_placements /
   mandatory_exact_instances. 不 match → quarantine.
2. Step 2 ghost match: **必 match** 当前 ghost_rect_id (ghost 是 partition_lens
   决定因素). 不 match → HOLD.
3. Step 3 artifact: 同 step 1.
4. Step 4 oracle version: `shape_hall_v1`.
5. Step 5 active_assumptions:
   - `boundary_pose_shape=1x3_rigid` 验 (canonical_rules pose shape 没改)
   - `boundary_region=left_baseline` 验 (verifier 跟 region_kind 比对)
6. 通过 5 步 → validator.validate (Step 5) → ATTACH 或 unsound→quarantine.

### Watcher index 添加 (Step 8)

```python
def add_watchers_shape_hall(store: CutStore, cut: Cut) -> None:
    cert = decode_shape_hall_cert(cut.geometric_payload)

    # by_cell_watcher: region 内所有 cells (任一 cell_owner change 触发 re-eval)
    for cell in iter_region_cells(cert.region_kind):
        store.by_cell_watcher[cell].add(cut.cut_id)

    # by_region_watcher
    region_id = f"{cert.region_kind}:shape_hall"
    store.by_region_watcher[region_id].add(cut.cut_id)

    # by_group_watcher: contributing_group
    store.by_group_watcher[cert.contributing_group].add(cut.cut_id)

    # NOTE: ghost_rect change 需 by_ghost_watcher (新 watcher kind)
    # 当前 §7 5 维 watcher 不含 ghost; Phase 1 加 6 维 or 走全 store replay.
```

### 6 维 watcher (Phase 1 加, Day 17 schema)

Day 17 改 cut_lifecycle §7 watcher index 加 `by_ghost_watcher: Dict[GhostRectId, Set[CutId]]`,
shape_hall + ghost_complement region_capacity 入此 watcher. Ghost_rect change
→ invalidate 整个 watcher group.

## 9. 跟 F2 fixture 对齐 验

F2 fixture: length 10 baseline 切 [4,5], demand 3, L=3 → infeasible.

```python
F2_shape_hall_cut = Cut(
    cut_id="F2-shape-hall-001",
    family="shape_packing_hall",
    literals=None,
    geometric_payload=canonical_bytes({
        "region_kind": "left_baseline",
        "region_total_length": 70,                # full prod scale
        "partition_lens": (4, 5),                  # F2 simplified
        "partition_offsets": (0, 5),
        "pose_length": 3,
        "pose_shape_canonical": "1x3_rigid",
        "max_packable": (1, 1),
        "total_packable": 2,
        "demand": 3,
        "gap": 1,
        "contributing_group": "boundary_storage_port",
    }),
    scope=CutScope(
        ghost_rect_id="<G canonical hash>",        # F2 ghost rect (0, 4, 1, 1)
        ...
        active_assumptions=(
            Assumption("boundary_pose_shape", "1x3_rigid"),
            Assumption("boundary_region", "left_baseline"),
        ),
    ),
    cert=OracleCert(
        cert_kind="hall_interval_witness",
        cert_payload=canonical_bytes({...}),
        cert_hash=...,
    ),
    family_version="v1.0",
    validator_version="v1.0",
    ...
)
```

`evaluate_geometric_shape_hall(F2_cut, state_with_ghost_G)`:
- recomputed_lens = (4, 5)
- recomputed_total_packable = 1 + 1 = 2
- 2 < demand 3 → return True ✅

F2 fixture 5 个 [SCHEMA_GAP] / [NEEDS_NEW_FAMILY] 解:
- `CutFamily` enum `shape_packing_hall`: ✅ v3 加
- `cert_kind` "hall_interval_witness": ✅ 本 spec 定义
- literals 非空约束: ✅ v3 解 (geometric_payload)
- Validator §6 加 Family: ✅ 本 spec §7
- `evaluate_cut` family-dispatch: ✅ v3 §5 + 本 spec §6

F1-F4 cross-family 不冲突 ✅.

## 10. Open questions

1. **Multi-shape Hall generalize**: 真 production 不止 boundary_storage_port,
   其他 facility (crusher / refinery / etc) 共享 baseline. Phase 1 generalize
   时需要 multi-shape ILP feasibility. v1.1 family.
2. **Interior region shape_hall**: 当前 spec 只 left/bottom baseline. 70x70
   interior region (interior_rect) 也可能 shape_hall infeasible (e.g. 5×5
   region 装 5 个 3×3 crusher). Day 17 / Phase 1 extend.
3. **Partition_offsets soundness**: cert carry offsets 是 debug-only, replay
   不验. 但若 offsets 改 (ghost shape 变但 lens 不变) → cert 仍 sound? 是 —
   max_packable 不依赖 absolute offset, 只依赖 lens. offsets 可任意 reorder.
4. **Hall cut 跟 region_capacity cut 重复**: 部分 case 两 family 都 trigger
   (e.g. cap < demand AND interval scheduling 也 < demand). cut store dedupe
   政策: 同 scope 同 contributing_group 优先保 shape_hall (更精细). Phase 1.
5. **Multi-region Hall**: left + bottom baseline 一起被 ghost 切, sum
   max_packable 都看. 当前 spec 单 region. Multi-region union 在 Phase 1.

## 11. Implementation pre-decision

- `ShapeHallValidator` 实现: `src/cuts/families/shape_packing_hall.py` (Phase 1)
- `ShapeHallOracle.generate`: `src/cuts/generators/shape_hall_generator.py` (Phase 1)
- `compute_baseline_partition_lens` helper: `src/cuts/helpers/baseline_partition.py` (Phase 1)
- 复用: 暂无 src 复用 (新 helper 是 ground-up).
- 测试 fixture 位置: `src/tests/cuts/test_family_6_shape_packing_hall.py` (Phase 1)
- Watcher 加 6 维 by_ghost: Day 17 cut_lifecycle_v2 update.

## 12. Phase 0 Day 16a 验收 status

- ✅ 数学定义 (Hall infeasibility 形式 + F2 反例验证 + multi-shape generalize 提及)
- ✅ Soundness proof (single shape 完整, multi-shape Phase 1 defer)
- ✅ Cert payload schema (ShapePackingHallCert dataclass)
- ✅ Cut object 构造 (geometric mode, ghost-bound scope)
- ✅ Generator (compute_baseline_partition_lens helper + detect 入口)
- ✅ evaluate_geometric (重算 partition + total_packable < demand)
- ✅ Validator 独立重算 + 4 步检验
- ✅ Replay 5 步 + watcher index (6 维加 by_ghost Day 17 schema)
- ✅ 跟 F2 fixture 对齐验证, 5 [SCHEMA_GAP] 全解
- ⚠️ 5 open question (multi-shape / interior region / partition_offsets /
  duplicate cut / multi-region) → Phase 1 / Day 17 接
- ⏸ 实施在 Phase 1

Day 16a close. 下一步 Day 16b Family 7 power_hitting_set (literal mode,
L16 lazy power 复用).


## Soundness amendment — 2026-06-04 (v28 GPT pro 外审)

Validator + generator 加 `region_demand` source-of-truth 下界: `region_demand ≤ max(0, group_demand − 对侧 baseline 容量)`, 且仅接受 `left_or_bottom_boundary` 模板。Why: 单边 Hall cut 只对被 pigeonhole 强制到该侧的数量 sound; 容量上界 ≠ 强制下界, 伪 `region_demand` 会错剪合法 split (全放另一侧 baseline)。见 PROJECT_LOCK §3。
