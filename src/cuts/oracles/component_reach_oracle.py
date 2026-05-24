"""F4 component_reach generator (Phase 1.2 P1.2B-F2/F4).

Per spec 04_component_reach.md §5 + 12_go_criteria.md §8.1.x C: emit a cut
when a commodity's src/sink endpoints lie in disconnected components of the
4-connected free-cells graph.

Algorithm:
1. fail-closed gates: commodity_routes None / ghost None → []
2. For each commodity in state.commodity_routes:
   a. parse src, sink; skip if either ∉ free_cells (other family covers)
   b. BFS src component on free_cells; if sink ∈ src_component, skip (connected)
   c. BFS sink component; extract frontier separator (∈ cell_owner ∪ ghost_cells)
   d. Build ComponentReachCert + Cut
3. Per-commodity exception is fail-closed (skip that commodity, continue others)

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F2/F4
- docs/research/p3_b_design_v2_20260521/cut_family_specs/04_component_reach.md
"""
from __future__ import annotations

import base64
import hashlib
from typing import Any, Dict, FrozenSet, List, Tuple

from src.cuts.families.cutset import _free_cells, _parse_cell
from src.cuts.helpers.dinic_node_split import bfs_component, extract_frontier_separator
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


ORACLE_NAME: str = "component_reach_v1"
FAMILY_VERSION: str = "v1.1"
VALIDATOR_VERSION: str = "v1.1"
CERT_KIND: str = "bfs_disconnect_witness"


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


def generate_component_reach_cuts(
    state: BState,
    master_solution: Any = None,
    *,
    iter_index: int = -1,
) -> List[Cut]:
    """Produce F4 cuts for each disconnected commodity in state.commodity_routes."""
    del master_solution  # commodity_routes is the source of truth
    if state.commodity_routes is None:
        return []
    if state.ghost_rect is None:
        return []

    try:
        free_cells = _free_cells(state)
    except Exception:  # noqa: BLE001
        return []

    blocked_for_separator: FrozenSet[Cell] = (
        frozenset(state.cell_owner.keys()) | frozenset(state.ghost_cells)
    )

    cuts: List[Cut] = []
    for commodity_id, route in state.commodity_routes.items():
        try:
            cut = _try_generate_one(
                state=state,
                commodity_id=str(commodity_id),
                route=route,
                free_cells=free_cells,
                blocked_for_separator=blocked_for_separator,
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
    blocked_for_separator: FrozenSet[Cell],
    iter_index: int,
) -> Cut | None:
    if not isinstance(route, dict):
        return None
    try:
        src = _parse_cell(route.get("src"), f"commodity_routes[{commodity_id!r}].src")
        sink = _parse_cell(route.get("sink"), f"commodity_routes[{commodity_id!r}].sink")
    except (ValueError, TypeError):
        return None
    if src not in free_cells or sink not in free_cells:
        return None
    if src == sink:
        return None
    src_component = bfs_component(src, free_cells)
    if sink in src_component:
        return None  # connected, no F4 cut
    sink_component = bfs_component(sink, free_cells)
    separator = extract_frontier_separator(src_component, blocked_for_separator)
    return _build_component_reach_cut(
        state=state,
        commodity_id=commodity_id,
        src=src,
        sink=sink,
        src_component=src_component,
        sink_component=sink_component,
        separator=separator,
        iter_index=iter_index,
    )


def _build_component_reach_cut(
    *,
    state: BState,
    commodity_id: str,
    src: Cell,
    sink: Cell,
    src_component: FrozenSet[Cell],
    sink_component: FrozenSet[Cell],
    separator: Tuple[Cell, ...],
    iter_index: int,
) -> Cut:
    cert_payload_dict: Dict[str, Any] = {
        "cert_kind": CERT_KIND,
        "commodity_id": commodity_id,
        "src_cell": [src[0], src[1]],
        "sink_cell": [sink[0], sink[1]],
        "src_component_bitset_b64": _encode_bitset(src_component),
        "sink_component_bitset_b64": _encode_bitset(sink_component),
        "separator_cells": [[c[0], c[1]] for c in separator],
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
        cut_id=f"f4_{iter_index}_{cert_hash[:12]}",
        family="component_reach",
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
            "size_before": len(src_component),
            "size_after": len(separator),
            "calls": 0,
        },
        iter_index=iter_index,
    )
    return cut
