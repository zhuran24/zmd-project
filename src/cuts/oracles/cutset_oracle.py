"""Family 2 cutset generator — Phase 1.1 P1.6 stub.

Per cut_family_specs/02_cutset.md v1.0 §5: wrap PCR-CUT
``patch_routing_core`` min-cut extraction. Phase 1.5+ real implementation;
Phase 1.1 P1.6 provides stub for downstream wiring.

Phase 1.5+ implementation outline:
1. Per ``iter_patches(state, master_solution)``, call
   ``patch_routing_core.PatchRoutingCore.run()`` on patch belt CP-SAT.
2. INFEASIBLE patches → extract (A, B) partition + cut_edges from belt model
   conflict core.
3. Compute commodity_demand crossing (A, B) via master_solution.commodities.
4. If demand > len(cut_edges) → build CutsetCert + Cut.

Stub returns []; framework wires (replay / store / watcher) ready when real
generator lands.

Refs:
- docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md v1.0
- src/models/patch_routing_core.py (PCR-CUT Path 14 helper)
"""
from __future__ import annotations

from typing import Any, List

from src.cuts.lifecycle import BState, Cut


_ORACLE_NAME = "cutset_v1"
_FAMILY_VERSION = "v1.0"
_VALIDATOR_VERSION = "v1.0"
_CERT_KIND_MENGER = "menger_min_cut"


def generate_cutset_cuts(
    state: BState,
    master_solution: Any = None,
    *,
    iter_index: int = -1,
) -> List[Cut]:
    """Stub generator for Family 2 cutset (Phase 1.1 P1.6).

    Returns empty list; real implementation Phase 1.5+ wraps
    ``patch_routing_core`` per spec §5.
    """
    # Phase 1.5+ TODO:
    # from src.models.patch_routing_core import PatchRoutingCore
    # for patch in iter_patches(state, master_solution):
    #     res = PatchRoutingCore(...).run(...)
    #     if res.status != "INFEASIBLE":
    #         continue
    #     A, B, cut_edges = _extract_partition(res, patch)
    #     demand = _sum_commodity_demand_cross(A, B, master_solution.commodities)
    #     if demand > len(cut_edges):
    #         cuts.append(_build_cutset_cut(state, A, B, cut_edges, demand, iter_index))
    # return cuts
    return []
