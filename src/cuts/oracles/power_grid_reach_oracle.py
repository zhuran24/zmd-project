"""F8 power_grid_reach generator (Phase 1.2 P1.2B-F8, default-disabled).

Phase 1.2 generator default-disabled (matches F6/F7 pattern). Phase 1.5+
wiring in ``benders_loop._run_power_placement_subproblem`` will run the
F7+F8 pipeline in order: F7 fires when ``CoverSet`` is empty; F8 fires
only when ``CoverSet`` is non-empty but the pole-jump BFS from
``protocol_core`` does not reach any pole that covers the facility.

Phase 1.2 single-case scope:
- cert_kind = "power_pole_bfs_disconnect_ghost" (ghost is the sole cause)
- Skip facilities where ``cell_owner`` is the true cause (the ghost-only
  power graph would reconnect); Phase 1.5+ multi-literal handles those.

Fail-closed contract:
- env disabled → []
- state.ghost_rect None → [] (F8 ghost-bound)
- pole_jump_radius missing → [] (caller responsibility, Phase 1.5+ wires
  from a canonical_rules field that does not yet exist)
- protocol_core anchor unknown / not in state.cell_owner → []

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F8
- docs/研究/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md v1.1
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, FrozenSet, List, Optional, Tuple, cast

from src.cuts.helpers.power_cover import compute_cover_set, enumerate_valid_pole_anchors
from src.cuts.helpers.power_network import build_power_network, bfs_component
from src.cuts.lifecycle import (
    BState,
    Cell,
    Cut,
    CutScope,
    GroupId,
    OracleCert,
    PoseId,
    canonical_bytes_for_cert,
    compute_blocked_cells_hash,
    compute_exterior_blocks_hash,
    compute_ghost_rect_id,
    compute_source_digest,
)


ORACLE_NAME: str = "power_grid_reach_v1"
FAMILY_VERSION: str = "v1.0"
VALIDATOR_VERSION: str = "v1.0"
CERT_KIND: str = "power_pole_bfs_disconnect_ghost"
_POLE_SHAPE_CANONICAL: str = "2x2_rigid"
_GRID_SIZE: int = 70
_PROTOCOL_CORE_SIZE: int = 9


_GRID_CELLS: FrozenSet[Cell] = frozenset(
    (x, y) for x in range(_GRID_SIZE) for y in range(_GRID_SIZE)
)


def _env_enabled() -> bool:
    return os.environ.get("EXACT_F8_GENERATOR_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "on",
    }


def _protocol_core_cells(anchor: Tuple[int, int]) -> FrozenSet[Cell]:
    ax, ay = anchor
    return frozenset(
        (ax + dx, ay + dy)
        for dx in range(_PROTOCOL_CORE_SIZE)
        for dy in range(_PROTOCOL_CORE_SIZE)
    )


def _facility_template_needs_power(state: BState, group_id: GroupId) -> Optional[str]:
    if state.instance_to_facility_type is None or state.facility_templates is None:
        return None
    facility_type = state.instance_to_facility_type.get(group_id)
    if facility_type is None:
        return None
    tpl = state.facility_templates.get(facility_type)
    if not isinstance(tpl, dict):
        return None
    if tpl.get("needs_power") is not True:
        return None
    return facility_type


def _pose_cells_from_canonical(
    state: BState, group_id: GroupId, pose_id: PoseId
) -> Optional[Tuple[Cell, ...]]:
    placements = state.candidate_placements
    if not isinstance(placements, dict):
        return None
    if state.instance_to_facility_type is None:
        return None
    facility_type_raw = state.instance_to_facility_type.get(group_id)
    if facility_type_raw is None:
        return None
    pools = placements.get("facility_pools")
    if not isinstance(pools, dict):
        return None
    pool = pools.get(facility_type_raw)
    if not isinstance(pool, list):
        return None
    for entry in pool:
        if not isinstance(entry, dict):
            continue
        if entry.get("pose_id") != pose_id:
            continue
        occupied = entry.get("occupied_cells")
        if not isinstance(occupied, list):
            return None
        out: List[Cell] = []
        for raw in occupied:
            if not isinstance(raw, list) or len(raw) != 2:
                return None
            x, y = raw
            if not (isinstance(x, int) and not isinstance(x, bool)):
                return None
            if not (isinstance(y, int) and not isinstance(y, bool)):
                return None
            out.append((x, y))
        return tuple(sorted(out))
    return None


def _build_full_free_mask(
    state: BState, facility_cells: Tuple[Cell, ...], pc_anchor: Tuple[int, int]
) -> FrozenSet[Cell]:
    blocked = (
        frozenset(state.ghost_cells)
        | frozenset(state.exterior_blocks)
        | frozenset(state.cell_owner.keys())
        | frozenset(facility_cells)
        | _protocol_core_cells(pc_anchor)
    )
    return frozenset(c for c in _GRID_CELLS if c not in blocked)


def _build_ghost_only_free_mask(
    state: BState, facility_cells: Tuple[Cell, ...], pc_anchor: Tuple[int, int]
) -> FrozenSet[Cell]:
    blocked = (
        frozenset(state.ghost_cells)
        | frozenset(state.exterior_blocks)
        | frozenset(facility_cells)
        | _protocol_core_cells(pc_anchor)
    )
    return frozenset(c for c in _GRID_CELLS if c not in blocked)


def generate_power_grid_reach_cuts(
    state: BState,
    *,
    target_poses: Optional[List[Tuple[GroupId, PoseId]]] = None,
    protocol_core_anchor: Optional[Tuple[int, int]] = None,
    pole_jump_radius: Optional[float] = None,
    iter_index: int = -1,
) -> List[Cut]:
    """Emit F8 cuts for facilities disconnected from protocol_core via pole jumps.

    Args:
        state: BState with ghost_rect / cell_owner / candidate_placements /
            facility_templates / instance_to_facility_type.
        target_poses: explicit ``(group_id, pose_id)`` pairs to evaluate.
            Phase 1.5+ wiring derives these from ``master_solution``.
        protocol_core_anchor: ``(x, y)`` of the 9×9 protocol_core anchor cell.
            Phase 1.5+ wiring derives from master_solution.placements.
            Phase 1.2 callers / fixtures pass explicitly.
        pole_jump_radius: float pole-to-pole jump radius. canonical_rules does
            not currently expose a separate field for this (Phase 1.5+ work);
            callers must pass explicitly.
        iter_index: outer-loop iteration tag for cut_id provenance.
    """
    if not _env_enabled():
        return []
    if state.ghost_rect is None:
        return []
    if target_poses is None or protocol_core_anchor is None or pole_jump_radius is None:
        return []
    if pole_jump_radius <= 0.0:
        return []

    cuts: List[Cut] = []
    for group_id, pose_id in target_poses:
        if group_id not in state.groups:
            continue
        if pose_id not in state.groups[group_id].pose_domain:
            continue
        facility_type = _facility_template_needs_power(state, group_id)
        if facility_type is None:
            continue
        facility_cells = _pose_cells_from_canonical(state, group_id, pose_id)
        if facility_cells is None:
            continue

        full_free = _build_full_free_mask(state, facility_cells, protocol_core_anchor)
        cover_set = compute_cover_set(facility_cells, full_free, pole_jump_radius)
        if not cover_set:
            continue  # F7 territory (empty CoverSet)

        # Gemini F8 round 1 Finding #1 + #2: enumerate the FULL pole-anchor
        # set on the current free mask (not just CoverSet) and pass the
        # protocol_core 9×9 footprint as ``pc_cells`` (not a single anchor).
        all_poles = enumerate_valid_pole_anchors(full_free)
        pc_cells = _protocol_core_cells(protocol_core_anchor)
        graph = build_power_network(
            list(all_poles),
            pole_radius=pole_jump_radius,
            pc_cells=pc_cells,
            ghost_rect=state.ghost_rect,
        )
        pc_component = bfs_component(graph, protocol_core_anchor)
        if cover_set & pc_component:
            continue  # connected — no cut

        # Verify the disconnect persists when cell_owner is ignored; otherwise
        # cell_owner is the true cause and Phase 1.5+ multi-literal handles it.
        ghost_only_free = _build_ghost_only_free_mask(
            state, facility_cells, protocol_core_anchor
        )
        cover_ghost = compute_cover_set(
            facility_cells, ghost_only_free, pole_jump_radius
        )
        if not cover_ghost:
            continue  # F7 territory ghost-only
        all_poles_ghost = enumerate_valid_pole_anchors(ghost_only_free)
        graph_ghost = build_power_network(
            list(all_poles_ghost),
            pole_radius=pole_jump_radius,
            pc_cells=pc_cells,
            ghost_rect=state.ghost_rect,
        )
        if cover_ghost & bfs_component(graph_ghost, protocol_core_anchor):
            # cell_owner is the true cause — Phase 1.5+ multi-literal
            continue

        cut = _build_cut(
            state=state,
            group_id=group_id,
            pose_id=pose_id,
            facility_cells=facility_cells,
            pole_jump_radius=pole_jump_radius,
            protocol_core_anchor=protocol_core_anchor,
            iter_index=iter_index,
        )
        cuts.append(cut)
    return cuts


def _build_cut(
    *,
    state: BState,
    group_id: GroupId,
    pose_id: PoseId,
    facility_cells: Tuple[Cell, ...],
    pole_jump_radius: float,
    protocol_core_anchor: Tuple[int, int],
    iter_index: int,
) -> Cut:
    ghost_rect_repr = list(cast(Tuple[int, int, int, int], state.ghost_rect))
    exterior_digest = compute_exterior_blocks_hash(state)

    cert_payload_dict: Dict[str, Any] = {
        "cert_kind": CERT_KIND,
        "facility_group": group_id,
        "facility_pose_id": pose_id,
        "facility_cells": [[c[0], c[1]] for c in facility_cells],
        "pole_jump_radius": float(pole_jump_radius),
        "pole_shape_canonical": _POLE_SHAPE_CANONICAL,
        "protocol_core_cell": [protocol_core_anchor[0], protocol_core_anchor[1]],
        "ghost_rect_repr": ghost_rect_repr,
        "exterior_blocks_digest": exterior_digest,
    }
    cert_payload_bytes = canonical_bytes_for_cert(cert_payload_dict)
    cert_hash = hashlib.sha256(cert_payload_bytes).hexdigest()

    source_digest = state.source_digest or compute_source_digest(state)

    scope = CutScope(
        ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),
        blocked_cells_hash=compute_blocked_cells_hash(state),
        exterior_blocks_hash=exterior_digest,
        source_digest=source_digest,
        oracle_abstraction_version=ORACLE_NAME,
        artifact_hashes=dict(state.artifact_hashes),
    )

    return Cut(
        cut_id=f"f8_{iter_index}_{cert_hash[:12]}",
        family="power_grid_reach",
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
            "size_before": 1,
            "size_after": 1,
            "calls": 0,
        },
        iter_index=iter_index,
    )
