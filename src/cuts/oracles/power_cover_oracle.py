"""F7 power_hitting_set generator (Phase 1.2 P1.2B-F7, default-disabled).

Phase 1.2 generator default-disabled (Gemini F6 round 2 pattern): no cuts
emitted unless ``EXACT_F7_GENERATOR_ENABLED=1``. The Phase 1.5+ wiring will
plug into ``benders_loop._run_power_placement_subproblem`` (currently L16's
ad-hoc INFEASIBLE nogood path) and emit a typed cut per facility whose
CoverSet is fully cleared by ghost + exterior (single-literal case).

Phase 1.2 single-case scope (per Gemini F7 minimum-viable agent + spec §1d
"v1.0 only拦空 set case"):
- Emit cert_kind = "power_cover_emptyset_ghost" only.
- Skip facilities whose cell_owner causation is the true cause (i.e.
  ``compute_cover_set_ghost_only`` non-empty but ``compute_cover_set``
  with full free_cells is empty). Phase 1.5+ multi-literal handles these.

Fail-closed contract:
- env disabled → []
- state.ghost_rect None → [] (F7 ghost-bound)
- facility not powered (needs_power != True) → skip
- pose_length < 2 / pose missing from canonical_rules → skip

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F7
- docs/研究/p3_b_design_v2_20260521/cut_family_specs/07_power_hitting_set.md v1.1
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, FrozenSet, List, Optional, Tuple, cast

from src.cuts.helpers.power_cover import compute_cover_set
from src.cuts.lifecycle import (
    AnonymousSlotRef,
    BState,
    Cell,
    Cut,
    CutLiteral,
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


ORACLE_NAME: str = "power_cover_v1"
FAMILY_VERSION: str = "v1.0"
VALIDATOR_VERSION: str = "v1.0"
CERT_KIND: str = "power_cover_emptyset_ghost"
_POLE_SHAPE_CANONICAL: str = "2x2_rigid"  # canonical_rules ground truth
_GRID_SIZE: int = 70


def _env_enabled() -> bool:
    return os.environ.get("EXACT_F7_GENERATOR_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "on",
    }


def _facility_template_needs_power(state: BState, group_id: GroupId) -> Optional[str]:
    """Return facility_type string if group needs power, else None."""
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
    """Look up the rigid pose's occupied cells from candidate_placements.

    Phase 1.2 expects ``state.candidate_placements`` to be a dict mirroring
    ``data/preprocessed/candidate_placements.json`` (or the in-memory
    derivative). Returns None if the facility/pose cannot be resolved.
    """
    placements = state.candidate_placements
    if not isinstance(placements, dict):
        return None
    facility_type_raw = (
        state.instance_to_facility_type.get(group_id)
        if state.instance_to_facility_type is not None
        else None
    )
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


_GRID_CELLS: FrozenSet[Cell] = frozenset(
    (x, y) for x in range(_GRID_SIZE) for y in range(_GRID_SIZE)
)


def _full_free_cells_minus_facility(
    state: BState, facility_cells: Tuple[Cell, ...]
) -> FrozenSet[Cell]:
    """Build free-cell mask: grid - ghost - exterior - cell_owner - facility_cells.

    Per Gemini F7 round 1 BLOCKER #1: facility's own cells must be excluded.
    During generator the facility may already appear in cell_owner (master
    selected it), but excluding facility_cells explicitly is robust against
    pre-master probes or fixture states.
    """
    blocked = (
        frozenset(state.ghost_cells)
        | frozenset(state.exterior_blocks)
        | frozenset(state.cell_owner.keys())
        | frozenset(facility_cells)
    )
    return frozenset(c for c in _GRID_CELLS if c not in blocked)


def _ghost_only_free_cells_minus_facility(
    state: BState, facility_cells: Tuple[Cell, ...]
) -> FrozenSet[Cell]:
    """Ghost+exterior mask + facility_cells exclude (cell_owner ignored)."""
    blocked = (
        frozenset(state.ghost_cells)
        | frozenset(state.exterior_blocks)
        | frozenset(facility_cells)
    )
    return frozenset(c for c in _GRID_CELLS if c not in blocked)


def generate_power_hitting_set_cuts(
    state: BState,
    *,
    target_poses: Optional[List[Tuple[GroupId, PoseId]]] = None,
    pole_radius: Optional[float] = None,
    iter_index: int = -1,
) -> List[Cut]:
    """Emit one F7 cut per (group, pose) whose CoverSet is fully cleared by
    ghost+exterior (single-literal case).

    Args:
        state: BState with ghost_rect, ghost_cells, exterior_blocks, groups,
            instance_to_facility_type, facility_templates, candidate_placements,
            cell_owner.
        target_poses: explicit ``(group_id, pose_id)`` pairs to evaluate.
            Phase 1.5+ wiring will derive these from ``master_solution`` (the
            poses the master picked). Phase 1.2 fixture tests pass explicit
            lists; without overrides the generator skips all.
        pole_radius: explicit Euclidean radius. When None, the generator pulls
            from ``state.facility_templates["power_pole"].power_coverage_radius``.
        iter_index: outer-loop iteration tag for cut_id provenance.
    """
    if not _env_enabled():
        return []
    if state.ghost_rect is None:
        return []
    if target_poses is None:
        return []

    if pole_radius is None:
        pole_radius = _resolve_pole_radius(state)
        if pole_radius is None:
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
        full_free = _full_free_cells_minus_facility(state, facility_cells)
        cover_full = compute_cover_set(facility_cells, full_free, pole_radius)
        if cover_full:
            continue  # power coverage OK
        ghost_only_free = _ghost_only_free_cells_minus_facility(state, facility_cells)
        cover_ghost_only = compute_cover_set(
            facility_cells, ghost_only_free, pole_radius
        )
        if cover_ghost_only:
            # cell_owner is the true cause — Phase 1.5+ multi-literal cut
            continue
        cut = _build_cut(
            state=state,
            group_id=group_id,
            pose_id=pose_id,
            facility_cells=facility_cells,
            pole_radius=pole_radius,
            iter_index=iter_index,
        )
        cuts.append(cut)
    return cuts


def _resolve_pole_radius(state: BState) -> Optional[float]:
    if state.facility_templates is None:
        return None
    tpl = state.facility_templates.get("power_pole")
    if not isinstance(tpl, dict):
        return None
    raw = tpl.get("power_coverage_radius")
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


def _build_cut(
    *,
    state: BState,
    group_id: GroupId,
    pose_id: PoseId,
    facility_cells: Tuple[Cell, ...],
    pole_radius: float,
    iter_index: int,
) -> Cut:
    ghost_rect_repr = list(cast(Tuple[int, int, int, int], state.ghost_rect))
    exterior_digest = compute_exterior_blocks_hash(state)

    cert_payload_dict: Dict[str, Any] = {
        "cert_kind": CERT_KIND,
        "facility_group": group_id,
        "facility_pose_id": pose_id,
        "facility_cells": [[c[0], c[1]] for c in facility_cells],
        "pole_radius": float(pole_radius),
        "pole_shape_canonical": _POLE_SHAPE_CANONICAL,
        "ghost_rect_repr": ghost_rect_repr,
        "exterior_blocks_digest": exterior_digest,
    }
    cert_payload_bytes = canonical_bytes_for_cert(cert_payload_dict)
    cert_hash = hashlib.sha256(cert_payload_bytes).hexdigest()

    source_digest = compute_source_digest(state)

    scope = CutScope(
        ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),
        blocked_cells_hash=compute_blocked_cells_hash(state),
        exterior_blocks_hash=exterior_digest,
        source_digest=source_digest,
        oracle_abstraction_version=ORACLE_NAME,
        artifact_hashes=dict(state.artifact_hashes),
    )

    cut_literals = (
        CutLiteral(
            slot_ref=AnonymousSlotRef(group_id=group_id, slot_index=0),
            pose_id=pose_id,
        ),
    )

    return Cut(
        cut_id=f"f7_{iter_index}_{cert_hash[:12]}",
        family="power_hitting_set",
        literals=cut_literals,
        geometric_payload=None,
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
