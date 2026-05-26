"""Family 3 port_exposure generator (F3 special-case phase Stage 1).

Phase 1.2 default-disabled (Gemini F6 round 2 pattern, mirrors F7 power_cover):
no cuts unless ``EXACT_F3_GENERATOR_ENABLED=1``. Per spec §5 + §6 + §9 OQ#2
F3 special-case phase v1.0 scope:

- Emit cert_kind = "port_exposure_blocked" (literal mode, 2 literals).
- Per F3 spec §6 + §9 OQ#2: skip ghost-occluded fronts — master ghost_rect
  constraint already排除此 pose. Cell_owner causation (true blocker) is the
  v1.0 trigger.
- per spec §1 / §2 / §4: cut.literals = (facility A, blocking facility B).
  Per F7 finding #1 same pattern — multi-literal carries the cell_owner
  causation so cut doesn't over-restrict when blocker moves.
- active_port_witness_b64 = None (Phase 1.5+ defer cand C
  boundary_constraints LP solution wrap; current validator does not check
  this field per src/cuts/families/port_exposure.py, so None placeholder is
  safe).

Fail-closed contract:
- env disabled → []
- state.candidate_placements / instance_to_facility_type / facility_templates
  missing → []
- target_poses None and unable to derive from cell_owner → []
- ghost-occluded front (front ∈ ghost_cells or ∉ grid) → skip
- ports_by_pose lookup miss → skip facility

Refs:
- docs/research/p3_b_design_v2_20260521/cut_family_specs/03_port_exposure.md v1.0
- src/cuts/families/port_exposure.py (validator接口 frozen)
- src/cuts/oracles/power_cover_oracle.py (F7 pattern, literal mode multi-cause)
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, List, Optional, Tuple

from src.cuts.helpers.candidate_placements import direction_offset, pose_ports
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


ORACLE_NAME: str = "port_exposure_v1"
FAMILY_VERSION: str = "v1.0"
VALIDATOR_VERSION: str = "v1.0"
CERT_KIND: str = "port_exposure_blocked"
_GRID_SIZE: int = 70


def _env_enabled() -> bool:
    return os.environ.get("EXACT_F3_GENERATOR_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "on",
    }


def _in_grid(cell: Cell) -> bool:
    return 0 <= cell[0] < _GRID_SIZE and 0 <= cell[1] < _GRID_SIZE


def _derive_targets_from_cell_owner(
    state: BState,
) -> List[Tuple[GroupId, int, PoseId]]:
    """Build (group_id, slot, pose_id) triples for facilities currently placed.

    Phase 1.2 generator scope: master_solution wiring deferred Phase 1.5+. The
    generator derives the active poses from ``state.cell_owner`` —
    ``selected_poses[slot]`` carries the pose chosen for each slot, so we walk
    each group's slot-indexed pose list once. Duplicates removed via set.
    """
    triples: List[Tuple[GroupId, int, PoseId]] = []
    seen: set[Tuple[GroupId, int]] = set()
    for (gid, slot) in state.cell_owner.values():
        if (gid, slot) in seen:
            continue
        seen.add((gid, slot))
        gstate = state.groups.get(gid)
        if gstate is None:
            continue
        if slot < 0 or slot >= len(gstate.selected_poses):
            continue
        pose_id = gstate.selected_poses[slot]
        triples.append((gid, slot, pose_id))
    return triples


def generate_port_exposure_cuts(
    state: BState,
    master_solution: Any = None,
    *,
    target_poses: Optional[List[Tuple[GroupId, int, PoseId]]] = None,
    iter_index: int = -1,
) -> List[Cut]:
    """Emit F3 port_exposure cuts: facility port front cell blocked by another facility.

    Args:
        state: BState with ghost_rect, ghost_cells, cell_owner, groups,
            candidate_placements, instance_to_facility_type, facility_templates.
        master_solution: Phase 1.5+ wiring; currently unused (Phase 1.2 derives
            placed facilities from ``state.cell_owner``).
        target_poses: explicit ``(group_id, slot, pose_id)`` triples to evaluate.
            When None, generator derives from ``state.cell_owner``.
        iter_index: outer-loop iteration tag for cut_id provenance.

    Emits one cut per (facility_pose, port) whose front cell is occupied by a
    DIFFERENT facility in ``state.cell_owner``. Ghost-occluded fronts and out-of-
    grid fronts are skipped per spec §6 + §9 OQ#2.
    """
    del master_solution  # Phase 1.5+ wiring
    if not _env_enabled():
        return []
    if state.candidate_placements is None:
        return []
    if state.instance_to_facility_type is None:
        return []

    targets: List[Tuple[GroupId, int, PoseId]]
    if target_poses is not None:
        targets = list(target_poses)
    else:
        targets = _derive_targets_from_cell_owner(state)
    if not targets:
        return []

    cuts: List[Cut] = []
    seen_cuts: set[Tuple[GroupId, PoseId, Cell, str, GroupId, int, PoseId]] = set()
    for facility_group, facility_slot, facility_pose_id in targets:
        del facility_slot  # Phase 1.2 slot anonymity (state_machine_v2 §5)
        ports = pose_ports(state, facility_group, facility_pose_id)
        if ports is None:
            continue
        for port_entry in ports:
            cut = _try_emit_one(
                state=state,
                facility_group=facility_group,
                facility_pose_id=facility_pose_id,
                port_entry=port_entry,
                iter_index=iter_index,
                seen_cuts=seen_cuts,
            )
            if cut is not None:
                cuts.append(cut)
    return cuts


def _try_emit_one(
    *,
    state: BState,
    facility_group: GroupId,
    facility_pose_id: PoseId,
    port_entry: Dict[str, Any],
    iter_index: int,
    seen_cuts: set[Tuple[GroupId, PoseId, Cell, str, GroupId, int, PoseId]],
) -> Optional[Cut]:
    """Inner one-port emit; returns a Cut or None (skip)."""
    port_x = port_entry.get("x")
    port_y = port_entry.get("y")
    port_dir = port_entry.get("dir")
    if not isinstance(port_x, int) or isinstance(port_x, bool):
        return None
    if not isinstance(port_y, int) or isinstance(port_y, bool):
        return None
    if not isinstance(port_dir, str) or port_dir == "":
        return None
    port_cell: Cell = (port_x, port_y)
    try:
        dx, dy = direction_offset(port_dir)
    except ValueError:
        return None
    front_cell: Cell = (port_cell[0] + dx, port_cell[1] + dy)
    # Spec §6 + §9 OQ#2: ghost-occluded / out-of-grid front skip.
    if not _in_grid(front_cell):
        return None
    if front_cell in state.ghost_cells:
        return None
    if front_cell in state.exterior_blocks:
        return None
    # cell_owner causation: front must be occupied by ANOTHER facility (not self).
    blocking_entry = state.cell_owner.get(front_cell)
    if blocking_entry is None:
        return None  # front is free — no cut needed
    blocking_group, blocking_slot = blocking_entry
    blocking_gstate = state.groups.get(blocking_group)
    if blocking_gstate is None:
        return None
    if blocking_slot < 0 or blocking_slot >= len(blocking_gstate.selected_poses):
        return None
    blocking_pose_id = blocking_gstate.selected_poses[blocking_slot]
    # Dedup signature includes port_dir to keep distinct port directions sharing
    # the same front_cell separate (rare but possible per F3 spec multi-port).
    sig = (
        facility_group,
        facility_pose_id,
        port_cell,
        port_dir,
        blocking_group,
        blocking_slot,
        blocking_pose_id,
    )
    if sig in seen_cuts:
        return None
    seen_cuts.add(sig)
    return _build_port_exposure_cut(
        state=state,
        facility_group=facility_group,
        facility_pose_id=facility_pose_id,
        port_cell=port_cell,
        port_direction=port_dir,
        front_cell=front_cell,
        blocking_group=blocking_group,
        blocking_slot=blocking_slot,
        blocking_pose_id=blocking_pose_id,
        iter_index=iter_index,
    )


def _build_port_exposure_cut(
    *,
    state: BState,
    facility_group: GroupId,
    facility_pose_id: PoseId,
    port_cell: Cell,
    port_direction: str,
    front_cell: Cell,
    blocking_group: GroupId,
    blocking_slot: int,
    blocking_pose_id: PoseId,
    iter_index: int,
) -> Cut:
    """Construct F3 cut object per spec §3 + §4."""
    cert_payload_dict: Dict[str, Any] = {
        "cert_kind": CERT_KIND,
        "facility_group": facility_group,
        "facility_pose_id": facility_pose_id,
        "port_cell": [port_cell[0], port_cell[1]],
        "port_direction": port_direction,
        "front_cell": [front_cell[0], front_cell[1]],
        "blocking_facility": [blocking_group, blocking_slot, blocking_pose_id],
        # active_port_witness_b64 = None: validator (port_exposure.py v1.0) 不
        # 校验此字段; Phase 1.5+ 完整 cand C boundary_constraints LP wrap.
        "active_port_witness_b64": None,
    }
    cert_payload_bytes = canonical_bytes_for_cert(cert_payload_dict)
    cert_hash = hashlib.sha256(cert_payload_bytes).hexdigest()

    source_digest = compute_source_digest(state)

    scope = CutScope(
        ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),
        blocked_cells_hash=compute_blocked_cells_hash(state),
        exterior_blocks_hash=compute_exterior_blocks_hash(state),
        source_digest=source_digest,
        oracle_abstraction_version=ORACLE_NAME,
        artifact_hashes=dict(state.artifact_hashes),
    )

    cut_literals = (
        CutLiteral(
            slot_ref=AnonymousSlotRef(group_id=facility_group, slot_index=0),
            pose_id=facility_pose_id,
        ),
        CutLiteral(
            slot_ref=AnonymousSlotRef(group_id=blocking_group, slot_index=blocking_slot),
            pose_id=blocking_pose_id,
        ),
    )

    return Cut(
        cut_id=f"f3_{iter_index}_{cert_hash[:12]}",
        family="port_exposure",
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
            "size_before": 2,
            "size_after": 2,
            "calls": 0,
        },
        iter_index=iter_index,
    )
