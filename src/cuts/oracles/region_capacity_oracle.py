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
from typing import Any, Dict, FrozenSet, List, Tuple

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
    compute_source_digest,
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
    if region_kind == "left_or_bottom_union":
        # Gap 6 union region: left ∪ bottom = 139 cells, (0,0) 共同 cell 去重
        left = {(x, 0) for x in range(grid_size)}
        bottom = {(0, y) for y in range(grid_size)}
        return frozenset(left | bottom)
    raise ValueError(f"_baseline_cells unsupported region_kind={region_kind!r}")


def _enumerate_contributing_groups(
    region_kind: RegionKind,
    region_cells: "FrozenSet[Cell]",
    state: BState,
) -> List[Tuple[GroupId, int]]:
    """Return list of (gid, demand_in_R) for groups whose placement_rule maps
    to region_kind AND P(g) ⊆ R strict.

    Gap 7/8 (round 30) 修: 遍历 state.groups + helper lookup (不查 canonical_rules
    顶层).

    HR2 修 (round 32): result 第二项必 demand_in_R (= group.demand × cpp).

    GPT pro round 2 P0-1 修: 加 strict P(g) ⊆ R check 经 all_poses_in_region.
    placement_rule 是必要 NOT 充分条件 — boundary_io 14/54 pose 真数据落 union
    外, 整 group fail-closed 不当 contributing (spec §2b 严格).
    """
    from src.cuts.helpers.candidate_placements import all_poses_in_region
    from src.cuts.helpers.canonical_rules import (
        cells_per_pose_for_group,
        placement_rule_for_group,
    )
    result: List[Tuple[GroupId, int]] = []
    for gid in state.groups:
        rule = placement_rule_for_group(state, gid)
        if rule in ("unknown", "free"):
            continue
        if region_kind not in _PLACEMENT_RULE_REGIONS.get(rule, frozenset()):
            continue
        # GPT pro round 2 P0-1: strict P(g) ⊆ R verification
        pgr = all_poses_in_region(state, gid, region_cells)
        if pgr is not True:
            continue  # fail-closed: P(g) 含 R 外 cell 或 data 不全 → not contributing
        cpp = cells_per_pose_for_group(state, gid)
        if cpp is None:
            continue
        demand_in_R = state.groups[gid].demand * cpp
        result.append((gid, demand_in_R))
    return result


def _build_cut(
    region_kind: RegionKind,
    region_cells: FrozenSet[Cell],
    cap_R: int,
    demand_R: int,
    gap: int,
    contributing_groups: List[Tuple[GroupId, int]],
    state: BState,
    *,
    iter_index: int,
) -> Cut:
    """Gap 8 (round 30) 修: cells_per_pose / placement_rule lookup 经 helper,
    不直接查 canonical_rules[gid].
    """
    from src.cuts.helpers.canonical_rules import (
        cells_per_pose_for_group,
        placement_rule_for_group,
    )
    cells_per_pose_map = {
        gid: cells_per_pose_for_group(state, gid) or 0
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
    if region_kind in {"left_baseline", "bottom_baseline", "left_or_bottom_union"}:
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
                value=f"{gid}={placement_rule_for_group(state, gid)}",
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
        source_digest=compute_source_digest(state),
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
    canonical_rules: Dict[str, Any],  # 保留参数兼容 (oracle sig stable); 内部不用, helper 走 state
    *,
    iter_index: int = -1,
    grid_size: int = 70,
) -> List[Cut]:
    """Enumerate region kinds (combinatorial path); emit cut for each INFEASIBLE
    region (demand_R > cap_R).

    Gap 6 (Gemini round 30) 修: 真 region 是 ``left_or_bottom_union`` (139 cells),
    **不**是 per-side single baseline. 旧版 per-side enumeration 因
    demand_R 不能 fully static carry 单边 split 数 (state-dependent on
    other-side cap) → FN. union 是 spec §2b 严格 sound 形式.

    Phase 1.1 P1.5: emits left_or_bottom_union cuts only. interior_rect +
    ghost_complement enumeration deferred to Phase 1.5+ (LP dual / heuristic).
    """
    del canonical_rules
    cuts: List[Cut] = []

    for region_kind in ("left_or_bottom_union",):
        region_cells = _baseline_cells(region_kind, grid_size)
        cap_R = compute_static_capacity(region_cells, state)
        contributing = _enumerate_contributing_groups(
            region_kind, region_cells, state,
        )
        if not contributing:
            continue
        # HR2 修: contributing 第二项现是 demand_in_R 已含 cpp factor, 直接 sum
        demand_R = sum(d for _, d in contributing)
        gap = demand_R - cap_R
        if gap <= 0:
            continue

        cuts.append(
            _build_cut(
                region_kind,
                region_cells,
                cap_R,
                demand_R,
                gap,
                contributing,
                state,
                iter_index=iter_index,
            )
        )

    return cuts
