# Cut Family 2 — cutset (完整 spec, 复用 PCR-CUT)

> **Status**: Day 17a v1.0 (2026-05-21)
> **Mode**: geometric (_FAMILY_MODE_MAP)
> **Family_version**: v1.0
> **来源**: B Design v2 5 cut family taxonomy
> **复用**: `src/search/patch_routing_core.py` (PCR-CUT min-cut helper, Path 14
> 死路 留下 oracle infrastructure)

## 1. 数学定义

### 1a. Cut 形式

设 belt routing graph `G = (V, E)`. `V` = grid free_cells, `E` = 相邻 free_cells
间的 belt edge. demand 是 (commodity, src, sink) 三元组要求 belt 路径连通.

给定 partition `(A, B)` of cells (A ∪ B = V, A ∩ B = ∅), 定义
`cut(A, B) = #{e ∈ E : e 连接 A 和 B}`. Menger min-cut: 任意 (src∈A, sink∈B) 对的
edge-disjoint path 数上限 = cut(A, B).

Family 2 cut 表达:

```
∃ partition (A, B) s.t.
    sum_{commodity c} demand(c) > cut(A, B)
    ⇒  INFEASIBLE (Menger violation)
```

cut(A, B) 是 belt-usable edge 数上界. 若所有 commodity 需路过 cut, 需 ≤
cut(A, B) edge-disjoint 路径, 超过即不可达.

### 1b. 跟 Family 4 component_reach 区别

- Family 4: src→sink **连通性** (BFS reachability binary). 跟 capacity 无关.
- Family 2: src→sink **flow capacity** (min-cut quantitative). cut size < demand 是 sound INFEASIBLE.

Family 4 适用单 commodity 简单连通; Family 2 适用 multi-commodity 共享 cut 容量.

### 1c. 复用 Path 14 PCR-CUT 死路 留下的 patch belt CP-SAT min-cut helper

Path 14 PCR-CUT 死法是 multi-anchor 0/8 CERTIFIED (paradigm-level 死), **但**
patch belt CP-SAT min-cut helper 本身 work (Phase 0 验证 770 cells cover 98%
SAC slack). v2 cutset cut 复用此 helper 作为 oracle.

## 2. Soundness proof

### 2a. Menger's theorem

Menger: max edge-disjoint paths from A to B = min edge cut size. 若 demand
要 K 个 disjoint commodity 流过 (A, B) cut, 必 cut size ≥ K. 反之 cut size <
demand → INFEASIBLE.

### 2b. Scope 限定

cut(A, B) 跟 free_cells 一致变化:
- ghost_rect change → free_cells 变 → cut size 可变
- cell_owner change → free_cells 缩 → cut size 单调减

scope 必绑 ghost_rect_id 但 cell_owner 影响通过 multi-literal cut (类似 F7
causation split) 或 oracle 重生成. v1.0 单 literal 不充分场景走 oracle 重生成.

## 3. Cert payload schema

```python
@dataclass(frozen=True)
class CutsetCert:
    """Cert for Family 2 cutset cut. cert.cert_kind = "menger_min_cut" """
    side_a_bitset_b64: str          # base64 cell bitset
    side_b_bitset_b64: str
    cut_edges: Tuple[Tuple[Cell, Cell], ...]   # cross-partition belt edges
    cut_size: int                    # |cut_edges|
    commodity_demand: int             # 总 flow demand cross partition
    gap: int                          # demand - cut_size (>0 = INFEASIBLE)
    contributing_commodities: Tuple[str, ...]
    menger_witness_kind: Literal["max_flow_LP", "node_disjoint_paths"]
    witness_blob_b64: Optional[str]  # 复用 PCR-CUT 的 cert format
```

## 4. Cut object 构造

geometric mode (literals=None, geometric_payload=cert_payload):

```python
cut = Cut(
    family="cutset", literals=None,
    geometric_payload=canonical_bytes(CutsetCert.asdict()),
    scope=CutScope(
        ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),  # 必非 AGNOSTIC
        blocked_cells_hash=compute_blocked_cells_hash(state),
        ...,
        oracle_abstraction_version="cutset_v1",
        active_assumptions=(
            Assumption("commodity_demand_set", value=str(commodities_sorted)),
        ),
    ),
    cert=OracleCert(cert_kind="menger_min_cut", ...),
)
```

## 5. Generator (复用 PCR-CUT helper)

```python
class CutsetOracle:
    name = "cutset_v1"

    def generate(self, state: BState, master_solution) -> List[Cut]:
        from src.search.patch_routing_core import compute_patch_min_cut
        cuts = []
        # 复用 PCR-CUT helper 在 patch boundary 跑 min-cut
        for patch in iter_patches(state, master_solution):
            (A, B, cut_edges) = compute_patch_min_cut(patch, state.free_cells)
            demand = sum_commodity_demand_cross_partition(A, B, master_solution.commodities)
            if demand > len(cut_edges):
                cert = CutsetCert(
                    side_a_bitset_b64=encode_bitset(A),
                    side_b_bitset_b64=encode_bitset(B),
                    cut_edges=tuple(cut_edges),
                    cut_size=len(cut_edges),
                    commodity_demand=demand,
                    gap=demand - len(cut_edges),
                    contributing_commodities=tuple(involved_commodities),
                    menger_witness_kind="max_flow_LP",
                    witness_blob_b64=encode_pcr_witness(...),
                )
                cuts.append(construct_cutset_cut(state, cert))
        return cuts
```

## 6. evaluate_geometric

```python
def evaluate_geometric_cutset(cut: Cut, state: BState) -> bool:
    """重算当前 free_cells 上 (A, B) partition 的 cut size, 验仍 < demand."""
    cert = decode_cutset_cert(cut.geometric_payload)
    A = decode_bitset(cert.side_a_bitset_b64)
    B = decode_bitset(cert.side_b_bitset_b64)
    current_cut_edges = compute_cross_partition_edges(A, B, state.free_cells)
    return len(current_cut_edges) < cert.commodity_demand
```

## 7. Validator

```python
class CutsetValidator(CutValidator):
    family = "cutset"
    validator_version = "v1.0"

    def validate(self, cut: Cut, state: BState) -> ValidationResult:
        cert = decode_cutset_cert(cut.geometric_payload)
        # 独立重算 Menger min-cut on cur state.free_cells
        recomputed_cut = compute_min_cut(decode_bitset(cert.side_a_bitset_b64),
                                          decode_bitset(cert.side_b_bitset_b64),
                                          state.free_cells)
        if len(recomputed_cut) != cert.cut_size:
            return ValidationResult("unsound", ..., f"cut_size mismatch")
        # 验 witness Menger algebraic check (max_flow LP dual)
        if cert.menger_witness_kind == "max_flow_LP" and cert.witness_blob_b64:
            if not verify_max_flow_witness(cert.witness_blob_b64, A, B):
                return ValidationResult("unsound", ..., "max_flow witness fail")
        if cert.commodity_demand <= cert.cut_size:
            return ValidationResult("unsound", ..., "witness fail: demand ≤ cut")
        return ValidationResult("ok", ...)

    def evaluate_geometric(self, cut, state):
        return evaluate_geometric_cutset(cut, state)
```

## 8. Replay + watcher

按 v3.1 §4 6 步 verify. Watcher:
- by_cell_watcher (每 cut_edge 端点)
- by_ghost_watcher (Day 17d §7 加, ghost 变直接 invalidate)
- by_commodity_watcher (每 contributing_commodity)

## 9. Open questions → Phase 1

1. Patch boundary selection (现复用 PCR-CUT patch enumerate, ROI 待测)
2. Multi-commodity vertex split graph 跟 cut_edges 表达力差异
3. Cell_owner 挤压 cut size 时多 literal cut 形式

## 10. 验收

- ✅ 数学定义 (Menger min-cut)
- ✅ Soundness proof (Menger theorem)
- ✅ Cert schema + cut 构造 + generator (PCR-CUT 复用) + evaluate + validator + replay
- ⚠️ 复用 PCR-CUT patch enumerate (Phase 1 验 ROI)
- ⏸ 实施 Phase 1, 直接 import patch_routing_core
