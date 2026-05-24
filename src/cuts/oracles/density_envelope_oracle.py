"""F9 density_envelope generator (Phase 1.2 P1.2B-F9).

Generator accepts only ``area_capacity_overflow`` witness (PROJECT_LOCK §3A
F9 area-only invariant). Other witness kinds (routing/binding/pcr_cut_overflow)
return [] — caller should fall back to F5 pattern_nogood.

Fail-closed contract:
- witness_kind != "area_capacity_overflow" → []
- group_id not in state.groups → []
- window_rect out of 70x70 grid or invalid → []
- state.ghost_rect is None → [] (F9 is ghost-bound)
- max_allowed_area > recomputed safe_ub → [] (oracle's claimed bound is unsound)
- recomputed sum_area_overlap <= max_allowed_area → [] (strict overflow required)
- Phase 1.5+ caller (benders_loop) is responsible for producing the witness
  payload; Phase 1.2 oracle is a stub-friendly entry point.

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F9
- docs/项目说明/12_go_criteria.md §8.1.x acceptance B
- docs/research/p3_b_design_v2_20260521/cut_family_specs/09_density_envelope.md
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Tuple

from src.cuts.families.density_envelope import (
    ACCEPTED_WITNESS_KIND,
    _compute_safe_max_allowed_area,
    _recompute_assignment_area_overlap,
    _window_cells,
)
from src.cuts.lifecycle import (
    BState,
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


ORACLE_NAME: str = "density_envelope_v1"
FAMILY_VERSION: str = "v1.0"
VALIDATOR_VERSION: str = "v1.0"
CERT_KIND: str = "density_envelope_v1"


def generate_density_envelope_cuts(
    state: BState,
    *,
    witness_kind: str,
    group_id: GroupId,
    window_rect: Tuple[int, int, int, int],
    max_allowed_area: int,
    assignment_witness: Tuple[Tuple[GroupId, PoseId], ...],
    iter_index: int = -1,
) -> List[Cut]:
    """Produce 0 or 1 F9 cut from an area_capacity_overflow witness.

    All fail-closed paths return ``[]``.
    """
    if witness_kind not in ACCEPTED_WITNESS_KIND:
        return []
    if group_id not in state.groups:
        return []
    if state.ghost_rect is None:
        return []
    if not assignment_witness:
        return []

    # Schema sanity on window_rect
    if (
        not isinstance(window_rect, tuple)
        or len(window_rect) != 4
        or not all(isinstance(v, int) and not isinstance(v, bool) for v in window_rect)
    ):
        return []
    x, y, h, w = window_rect
    if h < 1 or w < 1 or x < 0 or y < 0 or x + h > 70 or y + w > 70:
        return []

    if not isinstance(max_allowed_area, int) or isinstance(max_allowed_area, bool):
        return []
    if max_allowed_area < 0:
        return []

    window_cells = _window_cells(window_rect)
    if max_allowed_area > len(window_cells):
        return []

    # All witness entries must be (cert.group_id, pose) pairs
    for (g, _p) in assignment_witness:
        if g != group_id:
            return []

    # Oracle-side sanity: recompute safe upper bound and witness overflow.
    # Validator will independently re-verify; this oracle-side check just
    # avoids emitting a guaranteed-unsound cut.
    try:
        safe_ub = _compute_safe_max_allowed_area(window_cells, group_id, state)
        if max_allowed_area > safe_ub:
            return []
        recomputed_sum = _recompute_assignment_area_overlap(
            assignment_witness, window_cells, state
        )
        if recomputed_sum < 0:
            return []
        if recomputed_sum <= max_allowed_area:
            return []
    except Exception:  # noqa: BLE001 — fail-closed
        return []

    try:
        cut = _build_density_envelope_cut(
            state=state,
            group_id=group_id,
            window_rect=window_rect,
            max_allowed_area=max_allowed_area,
            assignment_witness=assignment_witness,
            iter_index=iter_index,
        )
    except Exception:  # noqa: BLE001 — fail-closed
        return []
    return [cut]


def _build_density_envelope_cut(
    *,
    state: BState,
    group_id: GroupId,
    window_rect: Tuple[int, int, int, int],
    max_allowed_area: int,
    assignment_witness: Tuple[Tuple[GroupId, PoseId], ...],
    iter_index: int,
) -> Cut:
    """Construct F9 Cut object. Caller has already validated soundness."""
    if state.ghost_rect is None:
        raise ValueError("F9 generator called without state.ghost_rect")

    ghost_rect_repr = list(state.ghost_rect)

    cert_payload_dict: Dict[str, Any] = {
        "cert_kind": CERT_KIND,
        "witness_kind": "area_capacity_overflow",
        "window_rect": list(window_rect),
        "group_id": group_id,
        "max_allowed_area": int(max_allowed_area),
        "oracle_assignment_witness": [[g, p] for (g, p) in assignment_witness],
        "ghost_rect_repr": ghost_rect_repr,
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
        cut_id=f"f9_{iter_index}_{cert_hash[:12]}",
        family="density_envelope",
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
        oracle_cert_hash=cert_hash,  # R3 invariant: == cert.cert_hash
        minimization_audit={
            "size_before": len(assignment_witness),
            "size_after": len(assignment_witness),
            "calls": 0,
        },
        iter_index=iter_index,
    )
    return cut
