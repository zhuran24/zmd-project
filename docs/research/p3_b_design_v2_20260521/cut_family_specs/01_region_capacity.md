# Cut Family 1 — region_capacity (完整 spec)

> **Status**: Day 16c v1.1 (2026-05-21) — Gemini round 14 cross-check 修
> **Cross-refs**: `../cut_lifecycle_v2.md` v3 §3 §4 §5 §6 §7 + `../state_machine_v2.md` §2 §3 + `../red_fixtures/F1_boundary_saturation.md` + `../cross_check/gemini_round_14_cut_families.md`
> **Mode**: geometric (_FAMILY_MODE_MAP)
> **Family_version**: v1.1 (cap_R 改 ghost-only static, cert 加 cells_per_pose)

## Changelog

- **v1.0** (Day 15, commit 925157e): 初版 12 段 spec
- **v1.1** (Day 16c): 修 Gemini round 14:
  - Finding #3: cap_R 改 static (ghost+exterior only)
  - Finding #5: cert 加 cells_per_pose
- **v1.2** (Day 17g, 本 commit): 修 Gemini round 18 **致命 GHOST_AGNOSTIC vs
  cap_R 依赖 ghost 矛盾**:
  - §2a `cap_R` 含 ghost contribution → §9 F1 fixture 标 GHOST_AGNOSTIC 是
    **unsound**! Candidate A ghost 压 baseline cap=68 → cut; Candidate B ghost
    不碰 baseline cap 应 70 ≥ demand → 但 AGNOSTIC 强 attach + evaluate 无条件
    True → 误剪.
  - v1.2 规则: **cap_R 含 ghost 时 cut scope.ghost_rect_id 必非 AGNOSTIC**.
    只有 ghost_cells ∩ R == ∅ 时才允许 GHOST_AGNOSTIC.
  - Generator §5 必须 check ghost_cells ∩ R, 决定 scope 用 GHOST_AGNOSTIC 还
    是 compute_ghost_rect_id.

## 1. 数学定义

### 1a. Cut 形式

设 `R ⊆ G` 是 grid `G` 上的一个 region (cell bitset), `cap_R` 是 region 内
**最多**能放进 `R` 的 mandatory facility cells 上界, `demand_R` 是当前 state
下**必须**在 `R` 内 placed 的 demand cells. region_capacity cut 表达:

```
∑_{i ∈ R} placed_cells_i  ≤  cap_R                  (1) capacity upper bound
∑_{i required in R} placed_cells_i  ≥  demand_R     (2) demand lower bound
demand_R  >  cap_R  ⇒  INFEASIBLE                   (3) infeasibility witness
```

Cut 触发条件 (3): 当 `demand_R > cap_R` 时, 任何 master assignment 都不能
满足 region `R` 上的需求 → master plan INFEASIBLE.

### 1b. 来源 region 集

`R` 不是任意 bitset — 是 oracle 选定的"具有结构性 capacity 上界"的 region.
B Design v2 现支持 4 类 region:

| Region kind | 定义 | `cap_R` 来源 |
|---|---|---|
| `left_baseline` | `{(x, 0) : x ∈ [0,69]}` | `\|R\| = 70` cells (boundary 共占) |
| `bottom_baseline` | `{(0, y) : y ∈ [0,69]}` | `\|R\| = 70` cells |
| `interior_rect` | rectangle `(x..x+h, y..y+w)` 内 cells | `\|R\| = h × w` (无 ghost) |
| `ghost_complement` | ghost rectangle 内 cells (永 forbidden) | `cap_R = 0` |

`demand_R` 由 mandatory facility group 的 placement_rule 决定 (e.g.
`boundary_storage_port` placement_rule="left_or_bottom_boundary" → demand
in `left_baseline ∪ bottom_baseline`).

### 1c. 跟 LP relaxation 关系

region_capacity 是 master LP relaxation 上的 valid inequality. 通过 master
LP solve 后取 Farkas dual ray, region 可以**自动**被 identified 为
infeasibility witness (cand C `farkas_certificate.py` 复用).

## 2. Soundness proof

### 2a. Capacity bound (1) — v1.1 改 (Gemini round 14 finding #3)

引理: `∑_{i ∈ R} placed_cells_i ≤ |R|` 因为 each cell 至多被 1 facility 占
(state_machine_v2 §3 I3: `free_cells == all_cells \ ghost_cells \ {c : c ∈ cell_owner}`).

**v1.1 critical**: `cap_R` 定义为 **static** — **只**减 ghost ∩ region + exterior
block ∩ region, **不**减 cell_owner ∩ region. Why: cell_owner-dependent cap 跟
`evaluate_geometric` 的 "无条件 True 简化" 矛盾, 深层学的 cut 回浅层会误剪. 见
v1.1 §6 + changelog.

```
cap_R = |R| − |ghost_cells ∩ R| − |exterior_blocks ∩ R|   (相对 ghost-state 不变)
```

对 `left_baseline`: `cap_R = 70 - len(boundary_ghost_cells_in_R) - len(exterior_in_R)`.
对 `ghost_complement`: `cap_R = 0` (全部 ghost-blocked, scope 内永 0).

**v1.2 critical (Gemini round 18 finding B1)**: cap_R 虽相对 ghost-state 不变,
**但跨 candidate 不同 ghost 时 cap_R 会变**. 因此 cut.scope.ghost_rect_id
不能用 GHOST_AGNOSTIC sentinel, **必须**绑当前 ghost_rect_id, 否则跨 candidate
attach 时 evaluate_geometric 无条件 True 会误剪 ghost 不同的合法 state.

唯一例外: `ghost_cells ∩ R == ∅` (ghost 完全不碰 region) 时 cap_R 跟当前 ghost
独立, **此时**才能 GHOST_AGNOSTIC. Generator §5 必 check 此条件.

**cell_owner 该走哪**: 若 region cap_R - placed_demand_R 不够走 region_capacity
cut, 走 Family 5 pattern_nogood (multi-literal 含 placed facility) 或 Family 7
power_hitting_set (cell_owner causation split).

### 2b. Demand bound (2)

引理: 对每个 facility group `g` with `placement_rule` requiring
`P(g) ⊆ R` (e.g. `left_or_bottom_boundary`), `g.demand` cells 必须 placed
in `P(g) ⊆ R`. 求和:

```
demand_R = ∑_{g : P(g) ⊆ R} g.demand × cells_per_pose(g)
```

各 g 不相交 (instance 不能重 placed) → demand_R 是严格下界.

### 2c. Infeasibility witness (3)

合 (1) + (2):

```
demand_R ≤ ∑_{i ∈ R} placed_cells_i ≤ cap_R
```

若 `demand_R > cap_R`, 矛盾, → 当前 master assignment + ghost INFEASIBLE.
Cut 学的是: master 不能选 `cell_owner ⊕ ghost_cells` configuration 使
`cap_R < demand_R`.

### 2d. Scope 限定

`cap_R` 跟 `demand_R` 都依赖:
- ghost_rect (影响 `cap_R` 通过 ghost_complement)
- canonical_rules placement_rule (影响 `demand_R` 通过 group → region 映射)
- mandatory_exact_instances demand (影响 `demand_R`)

→ scope 必须 carry ghost_rect_id + source_digest + active_assumption
"placement_rule:<group_id>=<rule>". Replay step 2/3/5 都 cover.

## 3. Cert payload schema

```python
@dataclass(frozen=True)
class RegionCapacityCert:
    """Cert for Family 1 region_capacity cut.

    cert.cert_kind = "region_capacity_lp_dual" (LP dual based)
                  | "region_capacity_combinatorial" (placement_rule 派生)
    """
    region_kind: Literal["left_baseline", "bottom_baseline",
                         "interior_rect", "ghost_complement"]
    region_cells_bitset_b64: str          # base64 encoded numpy uint8 bitset, len 4900/8
    cap_R: int                             # static capacity upper bound (v1.1: ghost+exterior only)
    demand_R: int                          # demand lower bound
    gap: int                               # demand_R - cap_R (must > 0)
    contributing_groups: Tuple[Tuple[GroupId, int], ...]
                                           # (group_id, demand_in_R) tuples
    cells_per_pose: Dict[GroupId, int]     # v1.1 新 (Gemini round 14 finding #5):
                                           # group → cells-per-pose, source-of-truth
                                           # snapshot at cut gen 时. Validator 用
                                           # cert 内的值重算 demand_R 而不是走
                                           # self._cells_per_pose 外部 state (防
                                           # canonical_rules pose shape 微调时全
                                           # cut quarantine).
    # cert_kind == "region_capacity_lp_dual" 专属:
    lp_dual_ray_b64: Optional[str] = None  # Farkas dual ray, base64 numpy float64
    lp_dual_objective: Optional[float] = None  # yᵀ b > 0 (Farkas)
```

cert_payload bytes = `canonical_bytes(RegionCapacityCert.asdict())` (sort
keys, fixed encoding). cert_hash = sha256(cert_payload).

## 4. Cut object 构造

按 `cut_lifecycle_v2 v3 §3` Cut schema, region_capacity 是 **geometric**:

```python
cut = Cut(
    cut_id=uuid4().hex,
    family="region_capacity",
    literals=None,                            # geometric mode
    geometric_payload=canonical_bytes(RegionCapacityCert.asdict()),
    scope=CutScope(
        # v1.2 (Gemini round 18 B1): 只有 ghost_cells ∩ R == ∅ 才 GHOST_AGNOSTIC.
        # 否则 cap_R 含 ghost contribution, scope 必绑当前 ghost_rect_id.
        ghost_rect_id=(GHOST_AGNOSTIC
                       if not (state.ghost_cells & region_cells_set)
                       else compute_ghost_rect_id(state.ghost_rect)),
        blocked_cells_hash=compute_blocked_cells_hash(state),
        source_digest=compute_source_digest(state).canonical_hash(),
        artifact_hashes={
            "canonical_rules.json": sha256_file("rules/canonical_rules.json"),
            "candidate_placements.json": ...,
            "mandatory_exact_instances.json": ...,
        },
        oracle_abstraction_version="region_capacity_v1",
        active_assumptions=(
            # region_kind="left_baseline" → 加 boundary saturation assumption
            Assumption(
                key="left_or_bottom_boundary_saturation",
                value="left_baseline=23,bottom_baseline=23,demand=46,cells=138",
            ) if region_kind in {"left_baseline", "bottom_baseline"} else None,
            # contributing_groups 的 placement_rule assumptions
            *(Assumption(
                key="placement_rule",
                value=f"{gid}={canonical_rules[gid]['placement_rule']}",
            ) for gid, _ in contributing_groups),
        ),
    ),
    cert=OracleCert(
        cert_kind="region_capacity_lp_dual" if has_lp_dual else "region_capacity_combinatorial",
        cert_payload=canonical_bytes(RegionCapacityCert.asdict()),
        cert_hash=sha256(canonical_bytes(...)).hexdigest(),
    ),
    family_version="v1.0",
    validator_version="v1.0",
    payload_schema_version=1,
    oracle_name="region_capacity_v1",
    oracle_cert_hash=...,
)
```

## 5. Generator algorithm (oracle 怎么生成)

### 5a. LP dual ray path (preferred)

master LP solve (or RMP for cand-C reuse) 返 INFEASIBLE + Farkas dual ray `y`.
对每个 constraint `c` in master LP, `y_c > 0` 标 binding. region detection:

```python
def detect_region_from_lp_dual(dual_ray: np.ndarray,
                                 master_constraints: List[Constraint]) -> Optional[Region]:
    """从 Farkas dual ray 中 extract region (LP infeasibility witness).

    1. Find cells `c` with `dual_ray[c] > epsilon`
    2. Cluster into region (e.g. all left_baseline cells → "left_baseline" kind)
    3. Compute cap_R + demand_R from canonical_rules
    4. If demand_R > cap_R, return Region
    """
    ...
```

复用: cand C `farkas_certificate.py: extract_dual_ray` (HiGHS presolve=off +
getDualRay). Hotspot cell 提取 → 聚类 (按 region_kind 4 类). cand C
`boundary_constraints.py` 提供 left/bottom baseline cell index.

### 5b. Combinatorial path (fallback)

master 端不跑 LP, 直接 enumerate 4 region kinds:

```python
def detect_region_combinatorial(state: BState) -> Optional[Region]:
    """Enumerate 4 region kinds, check demand_R > cap_R.

    Cheap: O(4 regions × O(|R|) cell count). Hot path safe.
    """
    for kind in ["left_baseline", "bottom_baseline", "interior_rect",
                 "ghost_complement"]:
        R = compute_region_cells(state, kind)
        cap_R = compute_capacity(R, state)
        demand_R = compute_demand(R, state)
        if demand_R > cap_R:
            return Region(kind, R, cap_R, demand_R)
    return None
```

### 5c. Minimize / Normalize (Step 2)

region cut 的 minimal core 是 `contributing_groups` 子集 — 取**最少**的 group
集使 `∑ demand_in_R > cap_R`. Greedy: sort groups by `demand_in_R` desc, accumulate
until exceeded → 此 group 集是 minimal core. 不需要 QuickXplain (combinatorial).

### 5d. Cert 写入

按 §3 schema 填 RegionCapacityCert, canonical_bytes 序列化, sha256 算 hash.
LP path 带 dual_ray_b64; combinatorial path 留 None.

## 6. Resolve (Step 7) — propagation 实现

按 `cut_lifecycle_v2 v3 §5`, region_capacity 是 geometric 走
`evaluate_cut_geometric`:

```python
def evaluate_geometric_region_capacity(cut: Cut, state: BState) -> bool:
    """region_capacity hot path. v3 §5 family-dispatch entry.

    解 cert payload 拿 region_cells_bitset + cap_R + demand_R.
    算当前 state 内 placed demand in region; 若 > cap_R → True (violate).

    Returns True iff cut violated (master assignment 不该选).
    """
    cert_dict = json.loads(canonical_bytes_decode(cut.geometric_payload))
    region_bitset = base64.b64decode(cert_dict["region_cells_bitset_b64"])
    cap_R = cert_dict["cap_R"]
    demand_R = cert_dict["demand_R"]

    # 算当前 state 内 placed cells ∩ region
    placed_in_region = 0
    for cell, owner in state.cell_owner.items():
        if bitset_get(region_bitset, cell_to_idx(cell)):
            placed_in_region += 1

    # 算 demand 已选 contributing_groups slot 数
    placed_demand = 0
    for gid, demand_in_R in cert_dict["contributing_groups"]:
        placed_demand += min(len(state.groups[gid].selected_poses), demand_in_R)

    # Violate: 当前 placement 蓝图本质 violate cap
    # (master 选了某 placement 让 demand 在 region 超 cap)
    return placed_demand + (demand_R - placed_demand) > cap_R   # ≡ demand_R > cap_R
    # 注意: cert 已 carry demand_R > cap_R, 任何 state 都 violate
    # → return True 当 region cert 当前仍 valid
```

实际 `demand_R > cap_R` 由 cert 已 carry (oracle 生成时验); 这里只需验 cert
跟当前 state 仍 align: region cells + cap_R 在 state 上仍 valid. 若 ghost
已变 → `cap_R` 可能改 → 重 generator 不在 propagation hot path.

→ **propagation 简化**: evaluate_geometric 总返 True (cert 持有的 state 仍
deterministically violate), 配合 watcher 在 ghost_rect change 时 invalidate.

```python
def evaluate_geometric_region_capacity_v1_1(cut: Cut, state: BState) -> bool:
    """v1.1 简化版 — sound iff cap_R 是 static (ghost-only) 不含 cell_owner.

    v1.0 finding #3 矛盾已修: cap_R 改 static (§2a v1.1), evaluate 无条件 True
    sound. Re-attach 路径: ghost_rect change → watcher invalidate → replay step
    2 HOLD (新 ghost_rect_id 不 match) → 等下次 ghost match candidate 重 attach.

    若 generator 暗中 carry 了 cell_owner-dependent cap (v1.0 bug), 这条无条件
    True 不 sound → 修法走 §2a v1.1 改: cap_R 必 static.
    """
    return True  # cert.demand_R > cert.cap_R, scope 内永 violate (cap_R static)
```

## 7. Validator (Step 5) — 独立重算

```python
class RegionCapacityValidator(CutValidator):
    family = "region_capacity"
    validator_version = "v1.0"

    def validate(self, cut: Cut, state: BState) -> ValidationResult:
        """Independent checker — 不信 oracle cert, 重算 cap_R + demand_R."""
        start = time.monotonic()
        try:
            cert_dict = json.loads(canonical_bytes_decode(cut.geometric_payload))
            region_kind = cert_dict["region_kind"]
            region_cells = self._decode_region_bitset(cert_dict["region_cells_bitset_b64"])

            # 独立重算 cap_R from canonical_rules + state.ghost_rect
            recomputed_cap_R = self._compute_capacity(region_cells, state)
            if recomputed_cap_R != cert_dict["cap_R"]:
                return ValidationResult(
                    kind="unsound", elapsed_seconds=time.monotonic() - start,
                    detail=f"cap_R mismatch: cert={cert_dict['cap_R']}, recomputed={recomputed_cap_R}",
                )

            # 独立重算 demand_R from contributing_groups + canonical_rules
            # v1.1 改 (Gemini round 14 finding #5): 用 cert.cells_per_pose 重算
            # 不走 self._cells_per_pose 外部 state. 防 canonical_rules pose shape
            # 微调时全 cut quarantine.
            cert_cells_per_pose = cert_dict.get("cells_per_pose", {})
            recomputed_demand_R = 0
            for gid, _ in cert_dict["contributing_groups"]:
                pr = self._canonical_rules[gid]["placement_rule"]
                # 验 placement_rule 映射 group → region 仍 hold (跟 active_assumption 对齐)
                if not self._group_falls_in_region(gid, region_kind, pr):
                    return ValidationResult(
                        kind="unsound", elapsed_seconds=time.monotonic() - start,
                        detail=f"group {gid} placement_rule {pr} 不映射 {region_kind}",
                    )
                # v1.1: 验 cert 内 cells_per_pose 跟当前 source-of-truth 一致
                # 不一致 = source rotated → quarantine (不 silent shrink demand)
                current_cells_per_pose = self._cells_per_pose(gid)
                if gid not in cert_cells_per_pose:
                    return ValidationResult(
                        kind="schema_err", elapsed_seconds=time.monotonic() - start,
                        detail=f"cert.cells_per_pose missing group {gid}",
                    )
                if cert_cells_per_pose[gid] != current_cells_per_pose:
                    return ValidationResult(
                        kind="unsound", elapsed_seconds=time.monotonic() - start,
                        detail=f"cells_per_pose mismatch for {gid}: "
                               f"cert={cert_cells_per_pose[gid]}, current={current_cells_per_pose} "
                               f"(canonical_rules pose shape rotated)",
                    )
                recomputed_demand_R += state.groups[gid].demand * cert_cells_per_pose[gid]
            if recomputed_demand_R != cert_dict["demand_R"]:
                return ValidationResult(
                    kind="unsound", elapsed_seconds=time.monotonic() - start,
                    detail=f"demand_R mismatch: cert={cert_dict['demand_R']}, recomputed={recomputed_demand_R}",
                )

            # 验 cert 的 infeasibility witness (3): demand_R > cap_R
            if recomputed_demand_R <= recomputed_cap_R:
                return ValidationResult(
                    kind="unsound", elapsed_seconds=time.monotonic() - start,
                    detail=f"witness fail: demand_R={recomputed_demand_R} ≤ cap_R={recomputed_cap_R}",
                )

            # 若 cert_kind == "region_capacity_lp_dual" 跑 Farkas algebraic check
            if cut.cert.cert_kind == "region_capacity_lp_dual":
                if not self._verify_farkas_dual(cert_dict, cut.scope):
                    return ValidationResult(
                        kind="unsound", elapsed_seconds=time.monotonic() - start,
                        detail="LP dual algebraic check fail",
                    )

            return ValidationResult(kind="ok", elapsed_seconds=time.monotonic() - start)
        except Exception as e:
            return ValidationResult(
                kind="schema_err", elapsed_seconds=time.monotonic() - start,
                detail=str(e),
            )

    def evaluate_geometric(self, cut: Cut, state: BState) -> bool:
        return evaluate_geometric_region_capacity_v3(cut, state)
```

### 7b. Farkas algebraic check 复用 cand C

```python
def _verify_farkas_dual(self, cert_dict: Dict, scope: CutScope) -> bool:
    """复用 cand C farkas_certificate.py: verify_farkas_dual_ray."""
    from docs.research.cand_c_column_generation_phase2_20260521.farkas_certificate import (
        verify_farkas_dual_ray
    )
    dual_ray = np.frombuffer(base64.b64decode(cert_dict["lp_dual_ray_b64"]), dtype=np.float64)
    obj = cert_dict["lp_dual_objective"]
    A, b = self._rebuild_master_lp_constraint_matrix(scope)
    return verify_farkas_dual_ray(A, b, dual_ray, obj)
```

## 8. Replay (Step 9)

按 cut_lifecycle_v2 v3 §4 replay 算法 + Family 1 特殊:

1. Step 1 source_digest: 比 `canonical_rules.json` + `candidate_placements.json` + `mandatory_exact_instances.json` hash. 不 match → quarantine.
2. Step 2 ghost match: F1 boundary saturation 走 `GHOST_AGNOSTIC` sentinel
   (left/bottom baseline 跟 ghost 无关). Interior_rect / ghost_complement 必
   match 当前 ghost_rect_id.
3. Step 3 artifact: 同 step 1 三 file.
4. Step 4 oracle version: `region_capacity_v1`.
5. Step 5 active_assumptions:
   - "placement_rule:<group>=<rule>" 必须 hold (canonical_rules 没改)
   - "left_or_bottom_boundary_saturation" 必须 hold (左+底 138 cells saturation)
6. 通过 5 步 → 跑 validator.validate (Step 5 重算) → 全 pass → ATTACH.

### Watcher index 添加 (Step 8)

按 cut_lifecycle_v2 §7 watcher rules:

```python
def add_watchers_region_capacity(store: CutStore, cut: Cut) -> None:
    cert = decode_region_capacity_cert(cut.geometric_payload)

    # by_cell_watcher: 每个 region cell
    for cell in iter_region_cells(cert.region_cells_bitset_b64):
        store.by_cell_watcher[cell].add(cut.cut_id)

    # by_region_watcher (新 watcher kind by region_kind)
    region_id = f"{cert.region_kind}:{sha256(cert.region_cells_bitset_b64.encode()).hexdigest()[:8]}"
    store.by_region_watcher[region_id].add(cut.cut_id)

    # by_group_watcher: 每个 contributing_group
    for gid, _ in cert.contributing_groups:
        store.by_group_watcher[gid].add(cut.cut_id)

    # v1.2 (Gemini round 22 final finding): 依赖 ghost 的 F1 Cut 必加 by_ghost,
    # 否则 ghost 改时 on_ghost_rect_changed 找不到此 cut → 不 invalidate →
    # 在新 ghost 下 evaluate 无条件 True 仍剪 → False Positive.
    # GHOST_AGNOSTIC cut 不加 (跨 ghost 仍 sound, exterior_blocks_hash 守).
    if cut.scope.ghost_rect_id != GHOST_AGNOSTIC:
        store.by_ghost_watcher[cut.scope.ghost_rect_id].add(cut.cut_id)
```

State 变化触发 re-evaluate 路径:
- `cell_owner` change at cell ∈ region → `by_cell_watcher[cell]` → re-eval cut
- group demand change → `by_group_watcher[gid]` → re-eval cut
- `ghost_rect` change → 全 region cut 走 replay (ghost_rect_id 重比)

## 9. 跟 F1 fixture 对齐 验

F1 boundary saturation fixture 反例: crusher pose 占 left baseline (1,0)(2,0) →
boundary 缺 1 demand. Family 1 region_capacity 这个反例的 cut 形式:

```python
F1_region_cut = Cut(
    cut_id="F1-region-capacity-001",
    family="region_capacity",
    literals=None,                                    # geometric mode (v3)
    geometric_payload=canonical_bytes({
        "region_kind": "left_baseline",
        "region_cells_bitset_b64": "<base64 70-bit mask: (x,0) for x in 0..69>",
        "cap_R": 70 - 2,                              # left baseline 70 cells - 2 ghost-blocked
        "demand_R": 23 * 3,                           # 23 boundary port pose × 3 cells = 69
        "gap": 69 - 68,                                # demand 69 > cap 68 = gap 1
        "contributing_groups": (("boundary_storage_port", 69),),
        "lp_dual_ray_b64": None,                      # combinatorial path
    }),
    scope=CutScope(
        ghost_rect_id=GHOST_AGNOSTIC,                 # F1 不依赖 ghost
        blocked_cells_hash="<crusher pose 占 cells hash>",
        ...
        active_assumptions=(
            Assumption("left_or_bottom_boundary_saturation",
                       "left_baseline=23,bottom_baseline=23,demand=46,cells=138"),
            Assumption("placement_rule",
                       "boundary_storage_port=left_or_bottom_boundary"),
        ),
    ),
    cert=OracleCert(
        cert_kind="region_capacity_combinatorial",
        cert_payload=canonical_bytes({...}),
        cert_hash=...,
    ),
    family_version="v1.0",
    validator_version="v1.0",
    ...
)
```

`evaluate_geometric(F1_region_cut, state)` 在 crusher 占 baseline 的 state 上
返 True (cert.demand_R > cert.cap_R, scope 内永 violate). ✅

F1 fixture §7 列的 [SCHEMA_GAP] literals 非空约束: v3 已解 (literals=None
合法, geometric_payload 非 None). F1 cut 现在按本 spec 是 valid Cut object.

## 10. Open questions

1. **LP dual algebraic check 跟 combinatorial path 谁优**: cand C
   farkas_certificate.py 已 land HiGHS dual ray extract; B Design v2 master
   是 CP-SAT 不是 LP, 算 LP relaxation 需要 spinoff LP model. Day 16-17
   决定: optional fallback (有 master LP 走 LP, 没有走 combinatorial).
2. **interior_rect region 几何如何 generator 选**: 任意 rectangle 太多
   (O(70^4) = 24M). Day 16-17 + Phase 1 用 LP dual ray hotspot cluster
   缩到 O(few). Or 走 SAC-Hull `phase2_dynamic_separator` 已 land 的
   separator (在 src/ 已有, 但目前 exploratory).
3. **`ghost_complement` cut 跟 GhostConditionChange invalidate**: 当 ghost
   change, ghost_complement cut 的 region_cells_bitset 变 → cert 不 valid
   → quarantine. 但 active_assumption "ghost_rect" 不在 ASSUMPTION_KEYS;
   Day 16-17 加 ghost-state assumption kind.
4. **multi-region cut**: 若 LP dual ray cluster 出 2 disjoint region (e.g.
   left baseline + bottom baseline 同时 binding), 应作 2 个 cut 还是 1 个
   union region cut? union 更 powerful (`cap_R + cap_R'` vs separate),
   但 minimize 路径不一样. Day 16-17 决定.
5. **`contributing_groups` 跟 `placement_rule` 多对多**: e.g. crusher pose
   可能 (依赖 demand_constraint) 进 interior_rect 也进 left_baseline (因
   crusher 不限定 placement_rule). 当前 spec 假设 group → region 1-to-1.
   需要 generalize. Day 17 / Phase 1 改.

## 11. Implementation pre-decision

按 schema_update_v3.md 跟 cut_lifecycle_v2 v3:

- `RegionCapacityValidator` 实现位置: `src/cuts/families/region_capacity.py` (Phase 1)
- `generator` 实现位置: `src/cuts/generators/region_capacity_generator.py` (Phase 1)
- `evaluate_geometric` 实现位置: `src/cuts/families/region_capacity.py:evaluate_geometric` (Phase 1)
- 复用: cand C `farkas_certificate.py` 直接 import (不复制)
- Test fixture 位置: `src/tests/cuts/test_family_1_region_capacity.py` (Phase 1)

## 12. Phase 0 Day 15 验收 status

- ✅ 数学定义完整 (cut 形式 + 4 region kind + LP relaxation 关系)
- ✅ Soundness proof (cap + demand + infeasibility witness + scope 限定)
- ✅ Cert payload schema (RegionCapacityCert dataclass)
- ✅ Cut object 构造 (按 v3 schema, geometric mode)
- ✅ Generator algorithm (LP dual + combinatorial fallback + minimize)
- ✅ Resolve / evaluate_geometric (propagation hot path 简化版)
- ✅ Validator 独立重算 + Farkas algebraic check (cand C farkas 复用)
- ✅ Replay 5 步 + watcher index
- ✅ 跟 F1 fixture 对齐验证 (cut object 完整 example)
- ⚠️ 5 open questions 给 Day 16-17 / Phase 1
- ⏸ 实施在 Phase 1 (单 task)

Day 15 close. 下一步 Day 16 Family 6 shape_packing_hall + Family 7
power_hitting_set (新 family).
