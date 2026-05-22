"""Family 1 region_capacity generator (combinatorial path).

Per cut_family_specs/01_region_capacity.md v1.2 §5b: combinatorial path
enumerates 4 region kinds and checks demand_R > cap_R. O(4 × |R|) per call —
hot-path safe. LP dual path (preferred) is Phase 1.5+.

Phase 1.1 P1.5 scope:
- ``generate_region_capacity_cuts(state, canonical_rules, iter_index=-1)``
  → List[Cut]. enumerate 4 region kinds; for each, build cert + scope per
  spec §3-§4.

Phase 1.5+ extends:
- LP dual ray hotspot clustering for interior_rect generator (spec §5a +
  cand C farkas_certificate.py 复用).
- Minimize via greedy contributing_groups subset (spec §5c).
- LP dual algebraic check (spec §7b).

Refs:
- docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md v1.2
"""
from __future__ import annotations

import base64
import hashlib
import time
from typing import Dict, FrozenSet, List, Tuple

from src.cuts.families.region_capacity import (
    _PLACEMENT_RULE_REGIONS,
    RegionKind,
    compute_static_capacity,
)
from src.cuts.lifecycle import (
    GHOST_AGNOSTIC,
    Assumption,
    BState,
    Cell,
    Cut,
    CutScope,
    GroupId,
    OracleCert,
    canonical_bytes_for_cert,
    compute_blocked_cells_hash,
    compute_exterior_blocks_hash,
    compute_ghost_rect_id,
)


_ORACLE_NAME = "region_capacity_v1"
_FAMILY_VERSION = "v1.2"
_VALIDATOR_VERSION = "v1.2"
_CERT_KIND_COMBINATORIAL = "region_capacity_combinatorial"


def _encode_region_bitset(cells: FrozenSet[Cell], grid_size: int = 70) -> str:
    arr = bytearray(grid_size * grid_size // 8 + 1)
    for x, y in cells:
        idx = x * grid_size + y
        arr[idx // 8] |= 1 << (idx % 8)
    return base64.b64encode(bytes(arr)).decode("ascii")


def _baseline_cells(region_kind: RegionKind, grid_size: int) -> FrozenSet[Cell]:
    if region_kind == "left_baseline":
        return frozenset((x, 0) for x in range(grid_size))
    if region_kind == "bottom_baseline":
        return frozenset((0, y) for y in range(grid_size))
    raise ValueError(f"_baseline_cells unsupported region_kind={region_kind!r}")


def _enumerate_contributing_groups(
    region_kind: RegionKind,
    canonical_rules: Dict,
) -> List[Tuple[GroupId, int]]:
    """Return list of (gid, demand_in_R) for groups whose placement_rule maps
    to region_kind.

    demand_in_R is the group's full demand × cells_per_pose (assumes group is
    entirely allocated to this region, per placement_rule). For
    "left_or_bottom_boundary" groups, demand is split across left + bottom; the
    cut form treats each baseline independently and the cert's demand_R reflects
    the union when needed (spec §1c open question #4 — Phase 1.5+ multi-region).
    """
    result: List[Tuple[GroupId, int]] = []
    for gid, entry in canonical_rules.items():
        if not isinstance(entry, dict):
            continue
        rule = entry.get("placement_rule")
        if rule is None:
            continue
        if region_kind in _PLACEMENT_RULE_REGIONS.get(rule, frozenset()):
            cells_per_pose = entry.get("cells_per_pose", 0)
            result.append((gid, cells_per_pose))
    return result


def _build_cut(
    region_kind: RegionKind,
    region_cells: FrozenSet[Cell],
    cap_R: int,
    demand_R: int,
    gap: int,
    contributing_groups: List[Tuple[GroupId, int]],
    canonical_rules: Dict,
    state: BState,
    *,
    iter_index: int,
) -> Cut:
    cells_per_pose_map = {
        gid: canonical_rules[gid]["cells_per_pose"]
        for gid, _ in contributing_groups
    }
    cert_dict = {
        "region_kind": region_kind,
        "region_cells_bitset_b64": _encode_region_bitset(region_cells),
        "cap_R": cap_R,
        "demand_R": demand_R,
        "gap": gap,
        "contributing_groups": [[gid, d] for gid, d in contributing_groups],
        "cells_per_pose": cells_per_pose_map,
        "lp_dual_ray_b64": None,
        "lp_dual_objective": None,
    }
    cert_payload = canonical_bytes_for_cert(cert_dict)
    cert_hash = hashlib.sha256(cert_payload).hexdigest()

    # Build active_assumptions (per spec §4)
    assumptions: List[Assumption] = []
    if region_kind in {"left_baseline", "bottom_baseline"}:
        assumptions.append(
            Assumption(
                key="left_or_bottom_boundary_saturation",
                value="left_baseline=23,bottom_baseline=23,demand=46,cells=138",
            )
        )
    for gid, _ in contributing_groups:
        assumptions.append(
            Assumption(
                key="placement_rule",
                value=f"{gid}={canonical_rules[gid]['placement_rule']}",
            )
        )

    # v1.2 (Gemini round 18 B1): GHOST_AGNOSTIC iff ghost ∩ R == ∅; else bind
    # to current ghost_rect_id.
    ghost_intersects = bool(state.ghost_cells & region_cells)
    ghost_rect_id = (
        compute_ghost_rect_id(state.ghost_rect)
        if ghost_intersects
        else GHOST_AGNOSTIC
    )

    scope = CutScope(
        ghost_rect_id=ghost_rect_id,
        blocked_cells_hash=compute_blocked_cells_hash(state),
        exterior_blocks_hash=compute_exterior_blocks_hash(state),
        source_digest="poc_source_digest",  # P1.21 加真 source_digest
        artifact_hashes=state.artifact_hashes,
        oracle_abstraction_version=_ORACLE_NAME,
        active_assumptions=tuple(assumptions),
    )

    return Cut(
        cut_id=f"F1-region-{region_kind}-{int(time.time() * 1e6)}-{iter_index}",
        family="region_capacity",
        literals=None,
        geometric_payload=cert_payload,
        scope=scope,
        cert=OracleCert(
            cert_kind=_CERT_KIND_COMBINATORIAL,
            cert_payload=cert_payload,
            cert_hash=cert_hash,
        ),
        family_version=_FAMILY_VERSION,
        validator_version=_VALIDATOR_VERSION,
        payload_schema_version=1,
        oracle_name=_ORACLE_NAME,
        oracle_cert_hash=cert_hash,
        minimization_audit={"size_before": 1, "size_after": 1, "qx_calls": 0},
        iter_index=iter_index,
    )


def generate_region_capacity_cuts(
    state: BState,
    canonical_rules: Dict,
    *,
    iter_index: int = -1,
    grid_size: int = 70,
) -> List[Cut]:
    """Enumerate 4 region kinds (combinatorial path); emit cut for each
    INFEASIBLE region (demand_R > cap_R).

    Phase 1.1 P1.5: emits left_baseline + bottom_baseline cuts only.
    interior_rect + ghost_complement enumeration deferred to Phase 1.5+
    (LP dual / heuristic).
    """
    cuts: List[Cut] = []

    for region_kind in ("left_baseline", "bottom_baseline"):
        region_cells = _baseline_cells(region_kind, grid_size)  # type: ignore[arg-type]
        cap_R = compute_static_capacity(region_cells, state)
        contributing = _enumerate_contributing_groups(
            region_kind, canonical_rules,  # type: ignore[arg-type]
        )
        if not contributing:
            continue
        demand_R = sum(
            state.groups[gid].demand * cpp for gid, cpp in contributing
        )
        gap = demand_R - cap_R
        if gap <= 0:
            continue

        cuts.append(
            _build_cut(
                region_kind,  # type: ignore[arg-type]
                region_cells,
                cap_R,
                demand_R,
                gap,
                contributing,
                canonical_rules,
                state,
                iter_index=iter_index,
            )
        )

    return cuts
