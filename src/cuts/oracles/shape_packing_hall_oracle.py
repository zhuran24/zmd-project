"""F6 shape_packing_hall generator (Phase 1.2 P1.2B-F6).

Generator scans each baseline region (left + bottom) × each boundary group,
recomputes ghost+exterior-induced partition_lens, and emits an INFEASIBLE
witness when ``sum(⌊len(I_j) / L⌋) < region_demand``.

Phase 1.2 region_demand contract (Gemini F6 round 2 HIGH #2/#3 fixes):
- The naive ``min(group.demand, region_cap)`` default was unsound: facility
  placement_rule ``left_or_bottom_boundary`` lets the group satisfy its
  total demand entirely on the OTHER baseline, so a single-region cut is
  not justified just because this region is blocked.
- The conservative ``region_demand = 1`` fallback in round 1 had the same
  defect — it pruned states where the master legally places 0 poses here
  and the group's demand is met entirely on the other baseline.
- Phase 1.2 contract: the generator emits cuts ONLY when the caller passes
  explicit ``region_demand_overrides``. Missing overrides → no cut.
  Phase 1.5+ wiring will pull the real per-region count from
  ``master_solution``. Multi-region union (spec §10 #5) covers the
  ``left_or_bottom_boundary`` decoupling.
- Missing key in ``region_demand_overrides`` means the master placed 0
  poses in that region: skip rather than emit (master cannot violate
  Hall on a region it isn't using).

Fail-closed contract:
- state.ghost_rect is None → [] (F6 ghost-bound)
- state.groups missing the requested boundary group → [] for that group
- pose_length < 2 → [] (would degenerate into F1)
- recomputed total_packable >= region_demand → [] for that region/group

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F6
- docs/项目说明/12_go_criteria.md §8.1.x acceptance D
- docs/research/p3_b_design_v2_20260521/cut_family_specs/06_shape_packing_hall.md v1.1
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple, cast

from src.cuts.helpers.baseline_partition import (
    RegionKind,
    compute_baseline_partition_lens,
)
from src.cuts.lifecycle import (
    BState,
    Cut,
    CutScope,
    GroupId,
    OracleCert,
    canonical_bytes_for_cert,
    compute_blocked_cells_hash,
    compute_exterior_blocks_hash,
    compute_ghost_rect_id,
    compute_source_digest,
)


ORACLE_NAME: str = "shape_packing_hall_v1"
FAMILY_VERSION: str = "v1.0"
VALIDATOR_VERSION: str = "v1.0"
CERT_KIND: str = "hall_interval_witness"
_GRID_SIZE: int = 70

_DEFAULT_REGION_KINDS: Tuple[RegionKind, ...] = ("left_baseline", "bottom_baseline")


def _facility_template_length(state: BState, group_id: GroupId) -> Optional[int]:
    """Look up ``boundary_storage_port``-style pose length from canonical_rules.

    Returns the max dimension if the facility is 1×L rigid; None otherwise.
    """
    if state.instance_to_facility_type is None or state.facility_templates is None:
        return None
    facility_type = state.instance_to_facility_type.get(group_id)
    if facility_type is None:
        return None
    tpl = state.facility_templates.get(facility_type)
    if not isinstance(tpl, dict):
        return None
    dims = tpl.get("dimensions")
    if not isinstance(dims, dict):
        return None
    w_raw = dims.get("w")
    h_raw = dims.get("h")
    if not (isinstance(w_raw, int) and not isinstance(w_raw, bool)):
        return None
    if not (isinstance(h_raw, int) and not isinstance(h_raw, bool)):
        return None
    if min(w_raw, h_raw) != 1:
        return None  # not a 1×L rigid pose; F6 Phase 1.2 single-shape only
    return max(w_raw, h_raw)


def generate_shape_packing_hall_cuts(
    state: BState,
    *,
    boundary_groups: Optional[List[GroupId]] = None,
    region_kinds: Tuple[RegionKind, ...] = _DEFAULT_REGION_KINDS,
    region_demand_overrides: Optional[Dict[Tuple[GroupId, RegionKind], int]] = None,
    iter_index: int = -1,
) -> List[Cut]:
    """Scan each (boundary_group, region_kind) for Hall infeasibility.

    Args:
        state: BState with ghost_rect, ghost_cells, exterior_blocks, groups,
            (optionally) instance_to_facility_type + facility_templates.
        boundary_groups: list of group_id to scan. Default: auto-detect from
            state.facility_templates entries with ``placement_rule ==
            "left_or_bottom_boundary"``. Phase 1.2 fixture tests pass
            explicit lists; Phase 1.5+ wiring auto-detects.
        region_kinds: regions to scan. Default (left, bottom).
        region_demand_overrides: Phase 1.5+ master_solution per-region count.
            Phase 1.2 default uses ``min(group.demand, region capacity)``.
        iter_index: outer-loop iteration for cut_id provenance.
    """
    if state.ghost_rect is None:
        return []

    if boundary_groups is None:
        boundary_groups = _auto_detect_boundary_groups(state)

    cuts: List[Cut] = []
    for group_id in boundary_groups:
        if group_id not in state.groups:
            continue
        pose_length = _facility_template_length(state, group_id)
        if pose_length is None or pose_length < 2:
            continue
        group_demand = state.groups[group_id].demand
        if group_demand < 1:
            continue
        region_cap = _GRID_SIZE // pose_length
        if region_demand_overrides is None:
            # Gemini F6 round 2 HIGH #2 fix: Phase 1.2 default disabled.
            # Conservative defaults (group total / region_cap / 1) are all
            # unsound for placement_rule="left_or_bottom_boundary" because
            # the group's demand can legally be met entirely on the other
            # baseline. Generator only emits cuts when Phase 1.5+ wiring
            # supplies explicit per-region demand from master_solution.
            continue
        for region_kind in region_kinds:
            override_key = (group_id, region_kind)
            if override_key not in region_demand_overrides:
                # Gemini F6 round 2 HIGH #3 fix: missing key = master plans
                # 0 poses in this region. Cannot trigger Hall infeasibility
                # on an unused region.
                continue
            region_demand = region_demand_overrides[override_key]
            if region_demand < 1:
                continue
            if region_demand > min(group_demand, region_cap):
                # Override exceeded sane bound — skip rather than emit a
                # cert that validator phase 7 would reject as unsound.
                continue
            cut = _try_build_cut(
                state=state,
                region_kind=region_kind,
                group_id=group_id,
                pose_length=pose_length,
                group_demand=group_demand,
                region_demand=region_demand,
                iter_index=iter_index,
            )
            if cut is not None:
                cuts.append(cut)
    return cuts


def _auto_detect_boundary_groups(state: BState) -> List[GroupId]:
    if state.instance_to_facility_type is None or state.facility_templates is None:
        return []
    out: List[GroupId] = []
    for group_id, facility_type in state.instance_to_facility_type.items():
        tpl = state.facility_templates.get(facility_type)
        if not isinstance(tpl, dict):
            continue
        if tpl.get("placement_rule") != "left_or_bottom_boundary":
            continue
        out.append(group_id)
    return sorted(out)


def _try_build_cut(
    *,
    state: BState,
    region_kind: RegionKind,
    group_id: GroupId,
    pose_length: int,
    group_demand: int,
    region_demand: int,
    iter_index: int,
) -> Optional[Cut]:
    lens, offsets = compute_baseline_partition_lens(region_kind, state)
    max_packable = [L // pose_length for L in lens]
    total_packable = sum(max_packable)
    if total_packable >= region_demand:
        return None  # feasible, no cut

    ghost_rect_repr = list(cast(Tuple[int, int, int, int], state.ghost_rect))
    exterior_digest = compute_exterior_blocks_hash(state)

    cert_payload_dict: Dict[str, Any] = {
        "cert_kind": CERT_KIND,
        "region_kind": region_kind,
        "region_total_length": _GRID_SIZE,
        "partition_lens": list(lens),
        "partition_offsets": list(offsets),
        "pose_length": pose_length,
        "pose_shape_canonical": f"1x{pose_length}_rigid",
        "max_packable": list(max_packable),
        "total_packable": total_packable,
        "contributing_group": group_id,
        "region_demand": region_demand,
        "group_demand": group_demand,
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

    cut = Cut(
        cut_id=f"f6_{iter_index}_{cert_hash[:12]}",
        family="shape_packing_hall",
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
            "size_before": len(lens),
            "size_after": len(lens),
            "calls": 0,
        },
        iter_index=iter_index,
    )
    return cut
