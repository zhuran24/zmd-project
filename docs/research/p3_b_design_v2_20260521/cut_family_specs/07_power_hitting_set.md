# Cut Family 7 — power_hitting_set (完整 spec, v3 新 family)

> **Status**: Day 16c v1.1 (2026-05-21) — Gemini round 14 cross-check 修
> **Cross-refs**: `../cut_lifecycle_v2.md` v3 §3 §4 §5 §6 + `../state_machine_v2.md` §6 ghost-conditioned power_cover_domain + `../red_fixtures/F3_power_no_cover.md` + `src/search/benders_loop.py:4219-4268` (L16 lazy power completion) + `../cross_check/gemini_round_14_cut_families.md`
> **Mode**: literal (_FAMILY_MODE_MAP)
> **Family_version**: v1.1 (cell_owner causation fix)
> **来源**: GPT v14 review power cut + L16 lazy power completion landed
> **复用**: L16 lazy power infrastructure (`benders_loop.py:4219-4268`)

## Changelog

- **v1.0** (Day 16b, commit 824c9b6): 初版 12 段 spec
- **v1.1** (Day 16c, 本 commit): 修 Gemini round 14 finding #1 **致命 sound bug** —
  generator 必须区分 CoverSet 被 ghost/exterior 彻底清空 (v1.0 单 literal 安全)
  vs 被 cell_owner 挤空 (必须多 literal 含占用 facility, 退化 pattern_nogood 形式),
  否则 master 回溯移走 cell_owner facility 后误剪合法 pose

## 1. 数学定义

### 1a. Power coverage 基本

设 facility pose `p` (e.g. `crusher_blue_iron@(30,30)..(32,32)`) 需要 power
覆盖. Power pole 1×1 shape, 覆盖半径 `R` (e.g. R=5 Euclidean). Pole 候选
pose pool `PoolPole` 是 grid 上所有 cell 上可放 pole 的位置.

定义 `Cover(p, q)`: pole pose `q` 覆盖 facility pose `p` 的几何谓词 (q 的
cell 在 p 任一 cell 的 R 邻域内).

定义 `CoverSet(p, state) = { q ∈ PoolPole : Cover(p, q) AND q 在 state.free_cells (未被 ghost / cell_owner 占) }`.

### 1b. Cut 形式

Hitting set 视角: facility pose `p` 必须 hit `PoolPole` 子集 `CoverSet(p, state)`
中至少 1 个 pole pose. 若 `CoverSet(p, state) = ∅` →

```
∀ q ∈ PoolPole : ¬ Cover(p, q)  ∨  q ∉ free_cells
            ⇒ p 没法被 power 覆盖
            ⇒ master 选 p INFEASIBLE
```

Cut 表达: "ghost = G 下, slot (group_id, slot_idx) = p 是 INFEASIBLE"

### 1c. F3 反例 (GPT power)

- facility pose: `crusher_blue_iron@(30,30)..(32,32)` 3×3 块
- pole R = 5, 应有 ~50 candidate pole pose 在 facility 周围
- ghost `G = (x=25..40, y=25..40)` 16×16 covers facility 周围 R 半径所有 candidate
- `CoverSet(p, state) = ∅` → INFEASIBLE
- cut: `not(crusher_blue_iron[slot=*] = pose_17)` with scope ghost=G

### 1d. 一般化 hitting-set INFEASIBLE (现 v1.0 不实现)

更一般 case: `CoverSet(p, state) ≠ ∅` 但**多 facility 共用 pole** 时
hitting-set INFEASIBLE (e.g. 3 facility 都只能用同 1 pole, 但需 ≥ 2 pole).
v1.0 只拦空 set case (empty hitting set), 不证 hitting set min size 不够.
v1.1 generalize.

### 1e. 跟 L16 lazy power completion 关系

L16 (benders_loop.py:4219-4268, env-gated EXACT_POWER_PLACEMENT_SUBPROBLEM)
已 land lazy power completion: master 跑 OPTIMAL → check power coverage on
selected facility → 若某 facility coverage 不足 → 加 ghost-conditioned
power no-cover cut. Family 7 是 L16 cut 在 v2 framework 内的形式化.

L16 cut sound 性 already proven by lazy completion + benders cut framework.
Family 7 重写成 typed cut + scope-aware replay form.

## 2. Soundness proof

### 2a. Empty CoverSet ⇒ INFEASIBLE

**引理**: 若 `CoverSet(p, state) = ∅`, master 选 pose `p` 后, 不存在 pole
pose `q` 使得 `Cover(p, q)` AND `q ∈ free_cells`. 任何 placement 完成时,
state 的 free_cells 单调缩小 (placements monotonic add). 因此后续 state
`state' ⊇ state.cell_owner` → `state'.free_cells ⊆ state.free_cells` →
`CoverSet(p, state') ⊆ CoverSet(p, state) = ∅`. **空集单调保持**.

→ 不存在任何 future state 让 facility p 被 power 覆盖 → INFEASIBLE.

### 2b. Sound 性 anchor: ghost monotone

实际 ghost monotone hold 吗? 不一定 — outer LBBD 切换 candidate 时 ghost 可能
**变** (不一定缩). 所以 scope 必须 carry 当前 ghost_rect_id, 切换 ghost 时
HOLD 不 attach.

state machine v2 §6 ghost-conditioned `power_cover_domain` 已 enforce: ghost
change → trail GhostConditionChange → power_cover_invalid → lazy rebuild.
Family 7 cut scope 绑 ghost_rect_id 跟此一致.

### 2c. Scope 限定

`CoverSet(p, state)` 依赖:
- ghost_rect (key — F3 反例核心)
- canonical_rules pole_radius (source-of-truth)
- canonical_rules pole_shape (source-of-truth, 当前 1×1)
- candidate_placements PoolPole (source-of-truth)

→ scope: ghost_rect_id 必非 GHOST_AGNOSTIC + source_digest + assumptions
`power_pole_radius=R=5` + `power_pole_shape=1x1_rigid`.

## 3. Cert payload schema

```python
@dataclass(frozen=True)
class PowerHittingSetCert:
    """Cert for Family 7 power_hitting_set cut.

    cert.cert_kind = "power_cover_emptyset_ghost"      (v1.1 — ghost/exterior 彻底清空, 单 literal cut)
                  | "power_cover_emptyset_cell_owner"  (v1.1 — cell_owner 挤空, 多 literal cut)
                  | "power_hitting_set_min_size"       (v1.2 — hitting set min size 不够, defer)
    """
    facility_pose: Tuple[GroupId, PoseId]
                                            # ("crusher_blue_iron", 17)
    facility_cells: Tuple[Tuple[int, int], ...]
                                            # ((30,30), (30,31), ..., (32,32))
    pole_radius: float                      # 5.0 Euclidean
    pole_shape_canonical: str                # "1x1_rigid"

    # CoverSet before/after ghost (empty witness)
    candidate_pole_poses_before_ghost: Tuple[int, ...]
                                            # global pose id of candidate poles
                                            # before ghost masks; v1.0 verify
                                            # this set is the "full" potential set
    candidate_pole_poses_after_ghost: Tuple[int, ...]
                                            # = () for v1.0/v1.1 (empty set witness)
    ghost_blocked_pole_cells: Tuple[Tuple[int, int], ...]
                                            # cells blocked by ghost that intersect
                                            # candidate poles (debug + replay verify)
    ghost_rect_repr: Tuple[int, int, int, int]
                                            # (x, y, h, w) — replay sanity check
                                            # 跟 scope.ghost_rect_id 一致

    # v1.1 改 (Gemini round 14 finding #1 causation split)
    witness_kind: Literal[
        "empty_coverset_ghost",             # v1.1 — ghost 单 cause
        "empty_coverset_cell_owner",        # v1.1 — cell_owner 单 cause (含混合 ghost+cell_owner)
        "min_hitting_set_infeasible",       # v1.2 defer
    ]
    blocking_facility_literals: Tuple[Tuple[GroupId, int, int], ...] = ()
                                            # v1.1 新: (group, slot, pose_id) 三元组
                                            # witness_kind=="empty_coverset_ghost" → ()
                                            # witness_kind=="empty_coverset_cell_owner" → 非空
                                            # cut.literals = facility_A literal + 这些 facility 阻塞 literal
```

cert_payload bytes = `canonical_bytes(PowerHittingSetCert.asdict())`.
cert_hash = sha256(cert_payload).

## 4. Cut object 构造 (literal-based)

按 `cut_lifecycle_v2 v3 §3` Cut schema, power_hitting_set 是 **literal**:

```python
def construct_power_hitting_set_cut(state: BState, witness: PowerHittingSetCert) -> Cut:
    facility_group, facility_pose_id = witness.facility_pose
    return Cut(
        cut_id=uuid4().hex,
        family="power_hitting_set",
        literals=(
            # literal 表达: "facility group 内任 slot = pose_id" 都 INFEASIBLE
            # slot_index=0 占位 (跨 group permutation multiset 等价 §5 cut_lifecycle_v2)
            CutLiteral(
                slot_ref=AnonymousSlotRef(facility_group, 0),
                pose_id=facility_pose_id,
            ),
        ),
        geometric_payload=None,                    # literal mode
        scope=CutScope(
            ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),  # 必非 AGNOSTIC
            blocked_cells_hash=compute_blocked_cells_hash(state),
            source_digest=compute_source_digest(state).canonical_hash(),
            artifact_hashes={
                "canonical_rules.json": sha256_file("rules/canonical_rules.json"),
                "candidate_placements.json": sha256_file("data/preprocessed/candidate_placements.json"),
                "mandatory_exact_instances.json": sha256_file("data/preprocessed/mandatory_exact_instances.json"),
            },
            oracle_abstraction_version="power_cover_v1",
            active_assumptions=(
                Assumption("power_pole_radius",
                           f"R={canonical_rules['power_pole']['radius']}"),
                Assumption("power_pole_shape",
                           f"{canonical_rules['power_pole']['shape']}_rigid"),
            ),
        ),
        cert=OracleCert(
            cert_kind="power_cover_emptyset",
            cert_payload=canonical_bytes(witness.asdict()),
            cert_hash=sha256(...).hexdigest(),
        ),
        family_version="v1.0",
        validator_version="v1.0",
        payload_schema_version=1,
        oracle_name="power_cover_v1",
        oracle_cert_hash=...,
    )
```

**关键**: Family 7 literal-only carry facility pose, **不** carry pole 信息.
pole 端通过 cert.cert_payload 内的 CoverSet before/after 重算 verify.

## 5. Generator algorithm (L16 复用)

### 5a. L16 lazy power completion 入口

L16 已 land 在 `benders_loop.py:4219-4268` (env-gated
`EXACT_POWER_PLACEMENT_SUBPROBLEM=1`). 算法骨架:

```python
# 现 L16 代码 (简化, ref benders_loop.py:4219-4268):
def _try_complete_power_coverage(state, master_solution):
    for facility_pose in master_solution.placed_facility_poses:
        if requires_power(facility_pose):
            cover_set = compute_cover_set(facility_pose, state.ghost_rect, state.free_cells)
            if not cover_set:
                # ← Family 7 cut trigger 点
                return PowerNoCoverInfeasibility(facility_pose, ghost=state.ghost_rect)
    return None
```

### 5b. Family 7 generator — causation split (v1.1 修)

> **Gemini round 14 finding #1 critical sound bug**: 单 literal cut 仅在
> CoverSet 被 `ghost ∪ exterior` 彻底清空时 sound. 若 CoverSet 被 `cell_owner`
> (其他 facility) 挤空, 单 literal cut 永久封杀 pose_A 但 master 回溯移走那
> 个 facility 后 pose_A 本来 OK → False Positive 误剪.

v1.1 generator 必须做 **causation split**: CoverSet 被 ghost-cleared 还是
cell_owner-cleared? 二者构造**不同形式的 cut**:

```python
class PowerCoverOracle:
    name = "power_cover_v1.1"

    def generate(self, state: BState, master_solution: MasterSolution) -> List[Cut]:
        cuts = []
        for placed in master_solution.placed_facility_poses:
            if not requires_power(placed.facility_group):
                continue

            # 三个 CoverSet 用于 causation split:
            # 1. ignore_all = 忽略 ghost + cell_owner (pure 几何 + canonical 内 pole)
            cover_set_pure = compute_cover_set_ignoring_blocks(placed)
            # 2. ghost_only = 应用 ghost + exterior_blocks, 不应用 cell_owner
            cover_set_after_ghost = compute_cover_set_ghost_only(placed, state.ghost_rect)
            # 3. full = 应用 ghost + exterior + cell_owner (现 free_cells)
            cover_set_after_all = compute_cover_set(placed, state.ghost_rect, state.free_cells)

            if cover_set_after_all:
                continue  # power 可覆盖, 不需要 cut

            # CoverSet 被清空, 分两 case:
            if not cover_set_after_ghost:
                # CASE A: ghost/exterior 彻底清空 (cell_owner 无关)
                # → 单 literal cut sound, 整个 ghost scope 内永久封杀此 pose
                ghost_blocked = compute_ghost_blocked_pole_cells(
                    placed, state.ghost_rect, cover_set_pure,
                )
                witness = PowerHittingSetCert(
                    facility_pose=(placed.facility_group, placed.pose_id),
                    facility_cells=tuple(placed.cells),
                    pole_radius=canonical_rules["power_pole"]["radius"],
                    pole_shape_canonical=f"{canonical_rules['power_pole']['shape']}_rigid",
                    candidate_pole_poses_before_ghost=tuple(cover_set_pure),
                    candidate_pole_poses_after_ghost=(),
                    ghost_blocked_pole_cells=tuple(ghost_blocked),
                    ghost_rect_repr=(state.ghost_rect.x, state.ghost_rect.y,
                                     state.ghost_rect.h, state.ghost_rect.w),
                    witness_kind="empty_coverset_ghost",   # v1.1 新 — 标 ghost causation
                    blocking_facility_literals=(),            # 空 = pure ghost cause
                )
                cuts.append(construct_power_hitting_set_cut_single_literal(state, witness))
            else:
                # CASE B: cell_owner 挤空 (ghost 不足以清, cell_owner 才挤空)
                # → 必须把占用 cover_set_after_ghost \ cover_set_after_all 的
                # cell_owner facility 加进 cut literals, 退化 pattern_nogood 形式
                blocking_pole_poses = set(cover_set_after_ghost) - set(cover_set_after_all)
                blocking_facility_slots = []
                for pole_pose_id in blocking_pole_poses:
                    pole_cells = canonical_rules_pose_cells("power_pole", pole_pose_id)
                    for pole_cell in pole_cells:
                        if pole_cell in state.cell_owner:
                            blocking_group, blocking_slot = state.cell_owner[pole_cell]
                            # 取 master 当前 selected pose at slot
                            blocking_pose_id = state.groups[blocking_group].selected_poses[blocking_slot][1]
                            blocking_facility_slots.append(
                                (blocking_group, blocking_slot, blocking_pose_id)
                            )

                witness = PowerHittingSetCert(
                    facility_pose=(placed.facility_group, placed.pose_id),
                    facility_cells=tuple(placed.cells),
                    pole_radius=canonical_rules["power_pole"]["radius"],
                    pole_shape_canonical=f"{canonical_rules['power_pole']['shape']}_rigid",
                    candidate_pole_poses_before_ghost=tuple(cover_set_pure),
                    candidate_pole_poses_after_ghost=(),
                    ghost_blocked_pole_cells=tuple(...),
                    ghost_rect_repr=(...),
                    witness_kind="empty_coverset_cell_owner",  # v1.1 — 标 cell_owner causation
                    blocking_facility_literals=tuple(blocking_facility_slots),  # 非空
                )
                cuts.append(construct_power_hitting_set_cut_multi_literal(state, witness))
        return cuts


def construct_power_hitting_set_cut_multi_literal(state: BState, witness: PowerHittingSetCert) -> Cut:
    """Cell_owner 挤空 case: cut.literals 含 facility_A pose + blocking_facility_literals."""
    facility_group, facility_pose_id = witness.facility_pose
    literals = [
        # facility A pose
        CutLiteral(
            slot_ref=AnonymousSlotRef(facility_group, 0),
            pose_id=facility_pose_id,
        ),
        # blocking facility poses (v1.1)
        *[
            CutLiteral(
                slot_ref=AnonymousSlotRef(blocking_group, blocking_slot),
                pose_id=blocking_pose_id,
            )
            for blocking_group, blocking_slot, blocking_pose_id in witness.blocking_facility_literals
        ],
    ]
    return Cut(
        ...,
        literals=tuple(literals),
        ...,
    )
```

### 5b.bis Cert payload schema 改 (v1.1)

`PowerHittingSetCert` 加两 field:
- `witness_kind: Literal["empty_coverset_ghost", "empty_coverset_cell_owner"]`
  (v1.0 `"empty_coverset"` deprecated)
- `blocking_facility_literals: Tuple[Tuple[GroupId, SlotIdx, PoseId], ...] = ()`
  (空 → ghost causation; 非空 → cell_owner causation)

### 5c. Minimize (Step 2)

Family 7 v1.0 cut 已 minimal — 单 literal `(facility_group, *, pose_id)`.
不需要 QuickXplain.

v1.1 generalize 后 (hitting set min size 不够) 需要 minimal 多 facility
literal subset, 走 QuickXplain on power oracle.

## 6. evaluate_cut (literal-based, 走 §5 multiset)

按 `cut_lifecycle_v2 v3 §5` family-dispatch:

```python
def evaluate_cut(cut: Cut, state: BState) -> bool:
    if cut.literals is not None:    # ← Family 7 走此 path
        return evaluate_cut_literal_based(cut, state)
    ...
```

`evaluate_cut_literal_based` (cut_lifecycle_v2 §5 multiset):

```python
# Family 7 cut.literals = (CutLiteral(AnonymousSlotRef("crusher_blue_iron", 0), pose_id=17),)
# cut_demand_by_group = {"crusher_blue_iron": Counter({17: 1})}
# state_by_group = {"crusher_blue_iron": Counter({17: 1, ...}), ...}
# Counter({17:1}) <= Counter({17:1, ...}) → True (violate iff state 含 pose 17 in crusher_blue_iron group)
```

→ cut violates iff state.groups[crusher_blue_iron].selected_pose_assignments 含 pose_17.

跟 Family 1/6 区别: Family 7 不 carry pole 信息在 cut 表达, 只通过 active_assumption
+ cert payload 间接绑. ghost change 时 scope mismatch HOLD 救 sound.

## 7. Validator (Step 5) — 独立重算

```python
class PowerHittingSetValidator(CutValidator):
    family = "power_hitting_set"
    validator_version = "v1.0"

    def validate(self, cut: Cut, state: BState) -> ValidationResult:
        start = time.monotonic()
        try:
            cert_dict = json.loads(canonical_bytes_decode(cut.cert.cert_payload))
            facility_group, facility_pose_id = cert_dict["facility_pose"]
            facility_cells = [tuple(c) for c in cert_dict["facility_cells"]]
            pole_radius = cert_dict["pole_radius"]
            cert_ghost_repr = tuple(cert_dict["ghost_rect_repr"])

            # 1. 验 facility pose 数据一致 (canonical_rules pose registry)
            recomputed_cells = canonical_rules_pose_cells(facility_group, facility_pose_id)
            if tuple(recomputed_cells) != tuple(facility_cells):
                return ValidationResult(
                    kind="unsound", elapsed_seconds=time.monotonic() - start,
                    detail=f"facility_cells mismatch: cert={facility_cells}, recomputed={recomputed_cells}",
                )

            # 2. 验 ghost_rect_repr 跟当前 state ghost 一致 (replay step 2 已 cover, 二保)
            if state.ghost_rect is None or \
               (state.ghost_rect.x, state.ghost_rect.y, state.ghost_rect.h, state.ghost_rect.w) != cert_ghost_repr:
                return ValidationResult(
                    kind="unsound", elapsed_seconds=time.monotonic() - start,
                    detail=f"ghost mismatch: cert={cert_ghost_repr}, state={state.ghost_rect}",
                )

            # 3. 独立重算 CoverSet under current ghost + free_cells
            recomputed_cover_set = compute_cover_set(
                facility_pose=(facility_group, facility_pose_id),
                facility_cells=facility_cells,
                pole_radius=pole_radius,
                ghost_rect=state.ghost_rect,
                free_cells=state.free_cells,
            )

            # 4. 验 CoverSet empty
            if recomputed_cover_set:
                return ValidationResult(
                    kind="unsound", elapsed_seconds=time.monotonic() - start,
                    detail=f"witness fail: CoverSet not empty, size={len(recomputed_cover_set)}",
                )

            # 4.bis (v1.1 — Gemini round 14 finding #1 causation split):
            # 验 witness_kind 跟 cell_owner causation 一致.
            # ghost-only CoverSet (忽略 cell_owner) 验:
            recomputed_cover_set_ghost_only = compute_cover_set_ghost_only(
                facility_pose=(facility_group, facility_pose_id),
                facility_cells=facility_cells,
                pole_radius=pole_radius,
                ghost_rect=state.ghost_rect,
            )
            witness_kind = cert_dict.get("witness_kind", "")
            blocking_literals = cert_dict.get("blocking_facility_literals", ())

            if witness_kind == "empty_coverset_ghost":
                # 单 cause = ghost: ghost-only CoverSet 也必须空 (sound 严格 invariant)
                if recomputed_cover_set_ghost_only:
                    return ValidationResult(
                        kind="unsound", elapsed_seconds=time.monotonic() - start,
                        detail=f"witness_kind=ghost but ghost-only CoverSet 非空 "
                               f"(size={len(recomputed_cover_set_ghost_only)}) → cell_owner 才是 cause",
                    )
                # blocking_literals 必空
                if blocking_literals:
                    return ValidationResult(
                        kind="unsound", elapsed_seconds=time.monotonic() - start,
                        detail=f"witness_kind=ghost 但 blocking_literals 非空 (len={len(blocking_literals)})",
                    )
            elif witness_kind == "empty_coverset_cell_owner":
                # cell_owner cause: ghost-only CoverSet 必非空 (否则就是 ghost cause)
                if not recomputed_cover_set_ghost_only:
                    return ValidationResult(
                        kind="unsound", elapsed_seconds=time.monotonic() - start,
                        detail=f"witness_kind=cell_owner 但 ghost-only 已空, 应标 ghost cause",
                    )
                # blocking_literals 必非空 + 每条 (group, slot, pose) 必占 ghost-only CoverSet 内 pole cell
                if not blocking_literals:
                    return ValidationResult(
                        kind="unsound", elapsed_seconds=time.monotonic() - start,
                        detail=f"witness_kind=cell_owner 但 blocking_literals 空 (单 literal cut unsound)",
                    )
                # 验每 blocking literal 在 state 上确实占 ghost-only CoverSet 内 pole cell
                for blocking_group, blocking_slot, blocking_pose_id in blocking_literals:
                    blocking_cells = canonical_rules_pose_cells(blocking_group, blocking_pose_id)
                    occupies_pole_candidate = any(
                        any(c in pole_cells for c in blocking_cells)
                        for pole_pose_id in recomputed_cover_set_ghost_only
                        for pole_cells in [canonical_rules_pose_cells("power_pole", pole_pose_id)]
                    )
                    if not occupies_pole_candidate:
                        return ValidationResult(
                            kind="unsound", elapsed_seconds=time.monotonic() - start,
                            detail=f"blocking_literal ({blocking_group}[{blocking_slot}]={blocking_pose_id}) "
                                   f"不占 ghost-only CoverSet 内 pole cell → cut over-strict",
                        )
            else:
                return ValidationResult(
                    kind="schema_err", elapsed_seconds=time.monotonic() - start,
                    detail=f"unknown witness_kind={witness_kind}",
                )

            # 5. 验 ghost_blocked_pole_cells 是 candidate_pole_poses_before_ghost 的 ghost mask
            cert_blocked = set(tuple(c) for c in cert_dict["ghost_blocked_pole_cells"])
            recomputed_blocked = compute_ghost_blocked_pole_cells(
                facility_pose=(facility_group, facility_pose_id),
                ghost_rect=state.ghost_rect,
                pool_before_ghost=cert_dict["candidate_pole_poses_before_ghost"],
            )
            if cert_blocked != set(recomputed_blocked):
                return ValidationResult(
                    kind="unsound", elapsed_seconds=time.monotonic() - start,
                    detail=f"ghost_blocked mismatch",
                )

            return ValidationResult(kind="ok", elapsed_seconds=time.monotonic() - start)
        except Exception as e:
            return ValidationResult(
                kind="schema_err", elapsed_seconds=time.monotonic() - start,
                detail=str(e),
            )

    def evaluate_geometric(self, cut: Cut, state: BState) -> bool:
        # Family 7 literal-based — geometric path 不实现
        raise NotImplementedError("Family 7 is literal-based, use evaluate_cut_literal_based")
```

### 7b. compute_cover_set 复用 L16 helper

L16 helper (benders_loop.py:4219-4268) compute_cover_set 直接 import 不复制
(Phase 1 实施). Validator 内 wrap.

## 8. Replay (Step 9)

按 cut_lifecycle_v2 v3 §4 replay 算法 + Family 7 特殊:

1. Step 1 source_digest: 比 3 file hash. 不 match → quarantine.
2. Step 2 ghost match: **必 match** 当前 ghost_rect_id (CoverSet 跟 ghost 绑).
   GHOST_AGNOSTIC 不允许.
3. Step 3 artifact: 同 step 1.
4. Step 4 oracle version: `power_cover_v1`.
5. Step 5 active_assumptions:
   - `power_pole_radius=R=5` 验 (canonical_rules pole_radius hash match)
   - `power_pole_shape=1x1_rigid` 验 (canonical_rules pole_shape hash match)
6. 通过 5 步 → validator.validate 重算 CoverSet empty → ATTACH or unsound→quarantine.

### Watcher index 添加 (Step 8)

```python
def add_watchers_power_hitting_set(store: CutStore, cut: Cut) -> None:
    cert = decode_power_hitting_set_cert(cut.cert.cert_payload)

    # by_cell_watcher: facility cells + ghost_blocked_pole_cells
    for cell in cert.facility_cells:
        store.by_cell_watcher[cell].add(cut.cut_id)
    for cell in cert.ghost_blocked_pole_cells:
        store.by_cell_watcher[cell].add(cut.cut_id)

    # by_group_watcher: facility group
    facility_group, _ = cert.facility_pose
    store.by_group_watcher[facility_group].add(cut.cut_id)

    # by_pose_watcher: facility pose
    store.by_pose_watcher[cert.facility_pose].add(cut.cut_id)

    # by_ghost_watcher (6 维新 Day 17): ghost_rect_id
    # ghost change 必 invalidate Family 7 cut
    store.by_ghost_watcher[cut.scope.ghost_rect_id].add(cut.cut_id)
```

→ ghost change watcher trigger replay re-eval (step 2 ghost match 必失败 →
HOLD). cell_owner change at facility cell / ghost cell trigger.

## 9. 跟 F3 fixture 对齐 验

F3 反例: facility pose `(crusher_blue_iron, 17)` at (30,30)..(32,32), ghost
G=(25,25,16,16) 覆盖周围 R=5 全 candidate pole → 空 CoverSet.

```python
F3_power_hitting_cut = Cut(
    cut_id="F3-power-hitting-001",
    family="power_hitting_set",
    literals=(
        CutLiteral(
            slot_ref=AnonymousSlotRef("crusher_blue_iron", 0),
            pose_id=17,
        ),
    ),
    geometric_payload=None,                       # literal mode (v3)
    scope=CutScope(
        ghost_rect_id="<G canonical hash>",
        blocked_cells_hash=...,
        source_digest=...,
        artifact_hashes={...},
        oracle_abstraction_version="power_cover_v1",
        active_assumptions=(
            Assumption("power_pole_radius", "R=5"),
            Assumption("power_pole_shape", "1x1_rigid"),
        ),
    ),
    cert=OracleCert(
        cert_kind="power_cover_emptyset",
        cert_payload=canonical_bytes({
            "facility_pose": ["crusher_blue_iron", 17],
            "facility_cells": [[30,30],[30,31],[30,32],[31,30],...,[32,32]],
            "pole_radius": 5.0,
            "pole_shape_canonical": "1x1_rigid",
            "candidate_pole_poses_before_ghost": [1, 5, 17, 42, 89, ...],  # ~50
            "candidate_pole_poses_after_ghost": [],                          # empty
            "ghost_blocked_pole_cells": [[25,25],[25,26],...,[40,40]],     # all 256 ghost cells
            "ghost_rect_repr": [25, 25, 16, 16],
            "witness_kind": "empty_coverset",
        }),
        cert_hash=...,
    ),
    family_version="v1.0",
    validator_version="v1.0",
    ...
)
```

`evaluate_cut_literal_based(F3_cut, state_with_pose_17)`:
- cut_demand: `{"crusher_blue_iron": Counter({17: 1})}`
- state: `{"crusher_blue_iron": Counter({17: 1, ...}), ...}`
- Counter({17:1}) <= Counter({17:1,...}) → True (violate) ✅

不同 ghost G' 下 (scope-aware HOLD):
- replay step 2: cut.scope.ghost_rect_id != state.candidate.ghost_rect_id
  → `AttachDecision.HOLD` (cut 留, 不 attach)

F3 fixture 6 [SCHEMA_GAP]/[NEEDS_NEW_FAMILY] 解:
- `CutFamily` enum `power_hitting_set`: ✅ v3 加
- `cert_kind` "power_cover_emptyset": ✅ 本 spec 定义
- `DerivedDomain.power_cover_domain` 反例 carry: ✅ state_machine_v2 §6
- `GhostConditionChange` 触发 power_cover_invalid: ✅ state_machine_v2 §6
- Validator §6 加 Family: ✅ 本 spec §7
- Pole literal 必要性: ❌ v1.0 不加 pole literal, 通过 cert payload 间接.
  v1.1 generalize 时若 hitting set min size 不够才需要多 pole literal.

## 10. Open questions

1. **v1.1 hitting set min size 不够**: 现 v1.0 只拦 empty case. 多 facility
   共用 pole 但 pole 数不够的 case 不拦. Phase 1 generalize 走 ILP min hitting
   set on (multiple facility, shared pole pool).
2. **Power radius shape 一般化**: 现 spec assumes 1×1 pole + Euclidean R.
   若 game 实际 power 拓扑 (Manhattan / L∞ / 不规则 polygon / 多 radius pole),
   cert payload 加 shape data + active_assumption 加 power_shape_kind.
3. **Cut 跟 L16 cut store 重复**: L16 当前 cut 直接在 benders_loop add 不进
   cut store. Family 7 把 L16 cut 改写成 typed cut 进 cut store. 两路并存 →
   double cut. Phase 1 切 L16 cut 路径全走 Family 7 store.
4. **`candidate_pole_poses_before_ghost` 排序**: 现 cert 用 tuple, 顺序不固定
   → cert_hash 不稳. canonical_bytes 序列化前应 sort. Phase 1 加 helper
   `canonical_sort_pose_ids`.
5. **ghost_blocked_pole_cells 大小**: F3 反例 256 cells (16×16 ghost). cert
   payload 大. canonical_bytes base64 后 ~1.5KB / cut. 168h campaign 多 cuts
   累积 OK. v1.1 sparse encoding (e.g. ghost rect repr alone, blocked cells
   derived) 减 size.

## 11. Implementation pre-decision

- `PowerHittingSetValidator` 实现: `src/cuts/families/power_hitting_set.py` (Phase 1)
- `PowerCoverOracle.generate`: `src/cuts/generators/power_cover_oracle.py` (Phase 1)
- `compute_cover_set` helper: **复用** `src/search/benders_loop.py:4219-4268` (L16)
- `compute_ghost_blocked_pole_cells`: 新 helper Phase 1
- 测试 fixture 位置: `src/tests/cuts/test_family_7_power_hitting_set.py` (Phase 1)
- L16 cut 切到 Family 7 store: Phase 1 task (env flag toggle, A/B 测试)

## 12. Phase 0 Day 16b 验收 status

- ✅ 数学定义 (CoverSet + empty hitting set → INFEASIBLE; F3 反例验证;
  v1.1 generalize 提及但 defer)
- ✅ Soundness proof (empty set monotone hold; ghost monotone scope-aware
  fix; scope 限定)
- ✅ Cert payload schema (PowerHittingSetCert dataclass)
- ✅ Cut object 构造 (literal mode, ghost-bound scope, AnonymousSlotRef
  slot_index=0 占位)
- ✅ Generator (L16 lazy power completion 复用 + Family 7 wrap)
- ✅ evaluate_cut (走 §5 multiset literal-based path)
- ✅ Validator 5 步独立重算 (facility cells + ghost match + CoverSet 重算
  + empty 验 + ghost_blocked mask 比对)
- ✅ Replay 5 步 + watcher (cell + group + pose + 6 维 by_ghost Day 17)
- ✅ 跟 F3 fixture 对齐验证, 6 [SCHEMA_GAP]/[NEEDS_NEW_FAMILY] 全解
  (pole literal 留 v1.1)
- ⚠️ 5 open question (v1.1 hitting set min size / power shape 一般化 /
  L16 cut store 切换 / pose id 排序 / cert payload 大小)
- ⏸ 实施在 Phase 1, 复用 L16 helper

Day 16b close. Day 17 Family 2 cutset + Family 3 port_exposure + Family 4
component_reach + Family 5 pattern_nogood (复用 PCR-CUT / D2 /
boundary_constraints / L16 minimizer) + F1-F4 fixture sweep update + by_ghost
watcher schema 加 cut_lifecycle §7.
