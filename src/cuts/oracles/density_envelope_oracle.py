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
from typing import Any, Dict, FrozenSet, List, Tuple

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


def _normalize_window_rect(value: object) -> Tuple[int, int, int, int] | None:
    """Return a validated 70x70 window rect, or ``None`` on schema error."""
    if not isinstance(value, tuple) or len(value) != 4:
        return None
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in value):
        return None
    x, y, h, w = value
    if h < 1 or w < 1 or x < 0 or y < 0 or x + h > 70 or y + w > 70:
        return None
    return x, y, h, w


def _is_valid_max_allowed_area(value: object, window_cell_count: int) -> bool:
    """F9 only accepts a non-negative integer capacity no larger than the window."""
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= window_cell_count
    )


def _witness_belongs_to_group(
    assignment_witness: Tuple[Tuple[GroupId, PoseId], ...],
    group_id: GroupId,
) -> bool:
    """All witness entries must be ``(cert.group_id, pose)`` pairs."""
    return all(g == group_id for (g, _p) in assignment_witness)


def _has_strict_area_overflow(
    *,
    state: BState,
    group_id: GroupId,
    window_cells: FrozenSet[Tuple[int, int]],
    max_allowed_area: int,
    assignment_witness: Tuple[Tuple[GroupId, PoseId], ...],
) -> bool:
    """Oracle-side sanity check; the validator re-verifies independently."""
    safe_ub = _compute_safe_max_allowed_area(window_cells, group_id, state)
    if max_allowed_area > safe_ub:
        return False
    recomputed_sum = _recompute_assignment_area_overlap(
        assignment_witness, window_cells, state
    )
    return recomputed_sum >= 0 and recomputed_sum > max_allowed_area


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
    normalized_window = _normalize_window_rect(window_rect)
    if (
        witness_kind not in ACCEPTED_WITNESS_KIND
        or group_id not in state.groups
        or state.ghost_rect is None
        or not assignment_witness
        or normalized_window is None
    ):
        return []

    window_cells = _window_cells(normalized_window)
    if (
        not _is_valid_max_allowed_area(max_allowed_area, len(window_cells))
        or not _witness_belongs_to_group(assignment_witness, group_id)
    ):
        return []

    try:
        if not _has_strict_area_overflow(
            state=state,
            group_id=group_id,
            window_cells=window_cells,
            max_allowed_area=max_allowed_area,
            assignment_witness=assignment_witness,
        ):
            return []
        cut = _build_density_envelope_cut(
            state=state,
            group_id=group_id,
            window_rect=normalized_window,
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

    # Per Gemini F9 round 1 review #3 HIGH: sort the witness list so
    # permuted-but-equivalent witnesses produce identical cert_hash and the
    # CutStore can dedup them (matches F5 round 1's multiset-canonicalization
    # lesson — same trap re-emerging in F9).
    sorted_witness = sorted([[g, p] for (g, p) in assignment_witness])

    cert_payload_dict: Dict[str, Any] = {
        "cert_kind": CERT_KIND,
        "witness_kind": "area_capacity_overflow",
        "window_rect": list(window_rect),
        "group_id": group_id,
        "max_allowed_area": int(max_allowed_area),
        "oracle_assignment_witness": sorted_witness,
        "ghost_rect_repr": ghost_rect_repr,
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
