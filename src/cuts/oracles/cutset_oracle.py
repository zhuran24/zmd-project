"""F2 cutset generator (Phase 1.2 P1.2B-F2/F4).

Per spec 02_cutset.md §5 + 12_go_criteria.md §8.1.x C: emit a cut when a
commodity's demand exceeds the max-flow / min-cut capacity between its
endpoints on the free-cells graph.

Algorithm (Phase 1.2: edge-only mode, cell_capacity=∞):
1. fail-closed gates: commodity_routes / commodity_demands / ghost None → []
2. For each commodity:
   a. parse src, sink; skip if either ∉ free_cells
   b. BFS reachability — if disconnected, F4 handles (skip F2 here)
   c. Run Dinic max-flow (edge-only mode); if cut_capacity >= demand, skip
   d. Verify patch enclosure (side_a ∪ side_b has no escape edge to free cells)
   e. Build CutsetCert + Cut

Phase 1.5+ deferred:
- node-split mode (cell_capacity < ∞) for belt routing with cell capacities
- PCR-CUT patch enumerate + integration with patch_routing_core
- LP dual algebraic witness (currently witness_blob_b64=None per F2 v1.0
  validator allowance)

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F2/F4
- docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md
"""
from __future__ import annotations

import base64
import hashlib
from typing import Any, Dict, FrozenSet, List, Tuple

from src.cuts.families.cutset import (
    _cross_partition_edges,
    _free_cells,
    _has_patch_escape,
    _parse_cell,
)
from src.cuts.helpers.dinic_node_split import (
    bfs_component,
    dinic_node_split_min_cut,
)
from src.cuts.lifecycle import (
    BState,
    Cell,
    Cut,
    CutScope,
    OracleCert,
    canonical_bytes_for_cert,
    compute_blocked_cells_hash,
    compute_exterior_blocks_hash,
    compute_ghost_rect_id,
    compute_source_digest,
)


ORACLE_NAME: str = "cutset_v1"
FAMILY_VERSION: str = "v1.0"
VALIDATOR_VERSION: str = "v1.0"
CERT_KIND: str = "menger_min_cut"

# Edge-only mode: internal v_in→v_out edges cannot be cut (cell capacity ∞).
# Phase 1.5+ may switch to true node-split when belt cell capacity matters.
_INF_CAP: int = 10**9


def _encode_bitset(cells: FrozenSet[Cell], grid_size: int = 70) -> str:
    """Encode cell set as 70x70 bitset base64 (mirrors families.cutset._decode_bitset)."""
    n_bytes = (grid_size * grid_size + 7) // 8
    arr = bytearray(n_bytes)
    for (x, y) in cells:
        if not (0 <= x < grid_size and 0 <= y < grid_size):
            raise ValueError(f"cell {(x, y)} out of grid")
        idx = x * grid_size + y
        arr[idx // 8] |= 1 << (idx % 8)
    return base64.b64encode(bytes(arr)).decode("ascii")


def _is_strict_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def generate_cutset_cuts(
    state: BState,
    master_solution: Any = None,
    *,
    iter_index: int = -1,
) -> List[Cut]:
    """Produce F2 cuts for commodities whose demand exceeds the min-cut capacity."""
    del master_solution
    if state.commodity_routes is None:
        return []
    if state.commodity_demands is None:
        return []
    if state.ghost_rect is None:
        return []

    try:
        free_cells = _free_cells(state)
    except Exception:  # noqa: BLE001
        return []
    if not free_cells:
        return []

    cuts: List[Cut] = []
    for commodity_id, route in state.commodity_routes.items():
        try:
            cut = _try_generate_one(
                state=state,
                commodity_id=str(commodity_id),
                route=route,
                free_cells=free_cells,
                iter_index=iter_index,
            )
        # Intentional fail-closed per commodity (oracle isolation).
        except Exception:  # noqa: BLE001  # nosec B112
            continue
        if cut is not None:
            cuts.append(cut)
    return cuts


def _try_generate_one(
    *,
    state: BState,
    commodity_id: str,
    route: Dict[str, Any],
    free_cells: FrozenSet[Cell],
    iter_index: int,
) -> Cut | None:
    if not isinstance(route, dict):
        return None
    try:
        src = _parse_cell(route.get("src"), f"commodity_routes[{commodity_id!r}].src")
        sink = _parse_cell(route.get("sink"), f"commodity_routes[{commodity_id!r}].sink")
    except (ValueError, TypeError):
        return None
    if src not in free_cells or sink not in free_cells or src == sink:
        return None
    # F4 territory: disconnected → other family covers
    src_component = bfs_component(src, free_cells)
    if sink not in src_component:
        return None
    if state.commodity_demands is None:
        return None
    demand_raw = state.commodity_demands.get(commodity_id)
    if not _is_strict_positive_int(demand_raw):
        return None
    demand = int(demand_raw)  # type: ignore[arg-type]
    try:
        result = dinic_node_split_min_cut(
            free_cells,
            sources=[(src, demand)],
            sinks=[(sink, demand)],
            cell_capacity=_INF_CAP,  # edge-only mode (Phase 1.2)
            edge_capacity=1,
        )
    except Exception:  # noqa: BLE001
        return None
    if result.cut_capacity >= demand:
        return None  # no F2 cut needed (capacity satisfies demand)
    if not result.side_a or not result.side_b:
        return None  # degenerate partition
    if _has_patch_escape(result.side_a | result.side_b, free_cells):
        return None  # patch not enclosed — fail-closed
    # Cross-check: cut_edges from Dinic should match recomputed cross-partition edges
    recomputed_edges = _cross_partition_edges(result.side_a, result.side_b, free_cells)
    if frozenset(result.cut_cell_edges) != recomputed_edges:
        return None  # Dinic / recompute drift — fail-closed
    return _build_cutset_cut(
        state=state,
        commodity_id=commodity_id,
        side_a=result.side_a,
        side_b=result.side_b,
        cut_edges=result.cut_cell_edges,
        cut_capacity=result.cut_capacity,
        demand=demand,
        iter_index=iter_index,
    )


def _build_cutset_cut(
    *,
    state: BState,
    commodity_id: str,
    side_a: FrozenSet[Cell],
    side_b: FrozenSet[Cell],
    cut_edges: Tuple[Tuple[Cell, Cell], ...],
    cut_capacity: int,
    demand: int,
    iter_index: int,
) -> Cut:
    cert_payload_dict: Dict[str, Any] = {
        "cert_kind": CERT_KIND,
        "side_a_bitset_b64": _encode_bitset(side_a),
        "side_b_bitset_b64": _encode_bitset(side_b),
        "cut_edges": [[list(u), list(v)] for (u, v) in cut_edges],
        "cut_size": int(cut_capacity),
        "commodity_demand": int(demand),
        "contributing_commodities": [commodity_id],
    }
    cert_payload_bytes = canonical_bytes_for_cert(cert_payload_dict)
    cert_hash = hashlib.sha256(cert_payload_bytes).hexdigest()

    source_digest = state.source_digest or compute_source_digest(state)

    scope = CutScope(
        ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),
        blocked_cells_hash=compute_blocked_cells_hash(state),
        exterior_blocks_hash=compute_exterior_blocks_hash(state),
        source_digest=source_digest,
        oracle_abstraction_version=ORACLE_NAME,
        artifact_hashes=dict(state.artifact_hashes),
    )

    cut = Cut(
        cut_id=f"f2_{iter_index}_{cert_hash[:12]}",
        family="cutset",
        literals=None,
        geometric_payload=cert_payload_bytes,
        scope=scope,
        cert=OracleCert(
            cert_kind=CERT_KIND,
            cert_payload=cert_payload_bytes,
            cert_hash=cert_hash,
        ),
        family_version=FAMILY_VERSION,
        validator_version=VALIDATOR_VERSION,
        oracle_name=ORACLE_NAME,
        oracle_cert_hash=cert_hash,
        minimization_audit={
            "size_before": len(side_a) + len(side_b),
            "size_after": len(cut_edges),
            "calls": 0,
        },
        iter_index=iter_index,
    )
    return cut
