"""Family 4 component_reach generator — Phase 1.1 P1.8 stub.

Per cut_family_specs/04_component_reach.md v1.1 §5: wrap
``src/search/d2_separator.py`` (D2 commodity flow BFS/Tarjan helper, Path 17
死路 留下). Phase 1.5+ implements full integration.

Phase 1.5+ implementation outline:
1. ``compute_bfs_components(state.free_cells)`` → Dict[Cell, ComponentId]
2. For each ``commodity in master_solution.commodities``:
   - If components[src] != components[sink]:
     - ``separator = find_separator(...)``
     - ``blocking_facilities = identify_from_separator(separator, state.cell_owner)``
     - Build ComponentReachCert + Cut.
3. Phase 1.5+ also adds Tarjan SCC for directed reachability (currently 4-conn
   undirected BFS sufficient for belt routing per spec §1).

Refs:
- docs/research/p3_b_design_v2_20260521/cut_family_specs/04_component_reach.md v1.1
- src/search/d2_separator.py (D2 Path 17 helper)
"""
from __future__ import annotations

from typing import Any, List

from src.cuts.lifecycle import BState, Cut


_ORACLE_NAME = "component_reach_v1"
_FAMILY_VERSION = "v1.1"
_VALIDATOR_VERSION = "v1.1"
_CERT_KIND_DISCONNECT = "bfs_disconnect_witness"


def generate_component_reach_cuts(
    state: BState,
    master_solution: Any = None,
    *,
    iter_index: int = -1,
) -> List[Cut]:
    """Stub generator for Family 4 (Phase 1.1 P1.8).

    Returns empty list; real implementation Phase 1.5+ wraps d2_separator.
    """
    return []
