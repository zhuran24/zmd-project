"""Family 9 density_envelope — area-only validator + evaluator (Phase 1.2 P1.2B-F9).

PROJECT_LOCK §3A locked invariants (per docs/项目说明/04_design_invariants.md §18):
- **area-only**: generator only accepts ``area_capacity_overflow`` witness;
  ``routing_overflow`` / ``binding_overflow`` / ``pcr_cut_overflow`` rejected.
- Evaluator: ``sum_{cell ∈ cell_owner with group == cert.group_id} 1[cell ∈ W]
  > cert.max_allowed_area`` (NOT instance count, NOT origin-in-window,
  NOT all-in-window).
- **strict inequality**: equality does not cut.
- ``max_allowed_area`` must be a safe upper bound (validator independently
  recomputes via ``|W| - |(ghost ∪ exterior ∪ cell_owner_other) ∩ W|``).
- F9 is ghost-bound; ``cut.scope.ghost_rect_id == GHOST_AGNOSTIC`` rejected.

Cert payload schema (canonical JSON, sorted keys):
    cert_kind: "density_envelope_v1"
    witness_kind: "area_capacity_overflow"  (closed-set)
    window_rect: [x, y, h, w] (4 strict int, 70×70 grid bound)
    group_id: non-empty str ∈ state.groups
    max_allowed_area: strict int >= 0, <= |W|, <= validator-recomputed safe_ub
    oracle_assignment_witness: list of [group_id, pose_id]; all group_id ==
        cert.group_id; pose_id ∈ state.groups[group_id].pose_domain;
        multiset count per pose ≤ state.groups[g].demand
    ghost_rect_repr: [x, y, h, w] byte-equal state.ghost_rect

Evaluator dispatches via ``lifecycle.step_7_evaluate_cut``.

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F9
- docs/项目说明/12_go_criteria.md §8.1.x acceptance B
- docs/项目说明/02_mathematical_foundations.md §3.9
- docs/项目说明/04_design_invariants.md §18
- docs/research/p3_b_design_v2_20260521/cut_family_specs/09_density_envelope.md
"""
from __future__ import annotations

import json
import time
from collections import Counter
from typing import Any, Dict, FrozenSet, List, Literal, Optional, Tuple, cast

from src.cuts.lifecycle import (
    GHOST_AGNOSTIC,
    BState,
    Cell,
    Cut,
    GroupId,
    PoseId,
    ValidationResult,
)


ValidationKind = Literal["ok", "unsound", "timeout", "schema_err"]


# Closed-set witness kind whitelist. F9 area-only invariant (PROJECT_LOCK §3A).
ACCEPTED_WITNESS_KIND: frozenset[str] = frozenset({"area_capacity_overflow"})

# F1 / F9 are complementary families (cell-based vs area-based). The capacity
# helpers are intentionally NOT shared: F1 cap_R is static (cell_owner-free
# for cross-ghost replay), F9 safe_ub is dynamic (cell_owner-aware because F9
# is always ghost-bound). Do not refactor into a shared helper.


def _vr(kind: ValidationKind, t0: float, detail: str = "") -> ValidationResult:
    return ValidationResult(
        kind=kind, elapsed_seconds=time.monotonic() - t0, detail=detail or None
    )


def _is_strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_non_empty_str(value: object) -> bool:
    return isinstance(value, str) and value != ""


def _parse_window_rect(value: object) -> Tuple[int, int, int, int]:
    """Parse [x, y, h, w] with strict int + 70×70 grid bound + h/w > 0."""
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"window_rect must be 4-element list, got {value!r}")
    coords = []
    for i, v in enumerate(value):
        if not _is_strict_int(v):
            raise ValueError(f"window_rect[{i}] must be strict int, got {v!r}")
        coords.append(cast(int, v))
    x, y, h, w = coords
    if h < 1 or w < 1:
        raise ValueError(f"window_rect h/w must be >= 1, got h={h} w={w}")
    if x < 0 or y < 0:
        raise ValueError(f"window_rect x/y must be >= 0, got x={x} y={y}")
    if x + h > 70 or y + w > 70:
        raise ValueError(
            f"window_rect out of 70×70 grid: x+h={x + h}, y+w={y + w}"
        )
    return (x, y, h, w)


def _window_cells(window_rect: Tuple[int, int, int, int]) -> FrozenSet[Cell]:
    x, y, h, w = window_rect
    return frozenset((x + i, y + j) for i in range(h) for j in range(w))


def _parse_ghost_rect_repr(value: object) -> Tuple[int, int, int, int]:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"ghost_rect_repr must be 4-element list, got {value!r}")
    coords = []
    for i, v in enumerate(value):
        if not _is_strict_int(v):
            raise ValueError(f"ghost_rect_repr[{i}] must be strict int, got {v!r}")
        coords.append(cast(int, v))
    return (coords[0], coords[1], coords[2], coords[3])


def _parse_cert_payload(cert_payload: bytes) -> Dict[str, Any]:
    if not isinstance(cert_payload, bytes):
        raise ValueError("cert_payload must be bytes")
    try:
        loaded = json.loads(cert_payload)
    except Exception as e:
        raise ValueError(f"cert_payload JSON decode failed: {e}") from e
    if not isinstance(loaded, dict):
        raise ValueError(f"cert_payload must decode to dict, got {type(loaded).__name__}")
    return cast(Dict[str, Any], loaded)


def _validate_cert_kind(cert_dict: Dict[str, Any], t0: float) -> Optional[ValidationResult]:
    if cert_dict.get("cert_kind") != "density_envelope_v1":
        return _vr(
            "schema_err",
            t0,
            f"cert_kind must be 'density_envelope_v1', got {cert_dict.get('cert_kind')!r}",
        )
    return None


def _validate_witness_kind(cert_dict: Dict[str, Any], t0: float) -> Optional[ValidationResult]:
    wk = cert_dict.get("witness_kind")
    if wk not in ACCEPTED_WITNESS_KIND:
        return _vr(
            "schema_err",
            t0,
            f"witness_kind {wk!r} not in {sorted(ACCEPTED_WITNESS_KIND)} "
            f"(F9 area-only invariant, PROJECT_LOCK §3A)",
        )
    return None


def _validate_window_rect(
    cert_dict: Dict[str, Any], t0: float
) -> Tuple[Optional[ValidationResult], Optional[Tuple[int, int, int, int]]]:
    try:
        rect = _parse_window_rect(cert_dict.get("window_rect"))
    except ValueError as e:
        return _vr("schema_err", t0, str(e)), None
    return None, rect


def _validate_group(
    cert_dict: Dict[str, Any], state: BState, t0: float
) -> Tuple[Optional[ValidationResult], Optional[GroupId]]:
    gid = cert_dict.get("group_id")
    if not _is_non_empty_str(gid):
        return _vr("schema_err", t0, f"group_id must be non-empty str, got {gid!r}"), None
    gid_str = cast(GroupId, gid)
    if gid_str not in state.groups:
        return _vr("unsound", t0, f"group_id {gid_str!r} not in state.groups"), None
    return None, gid_str


def _validate_assignment_witness(
    cert_dict: Dict[str, Any],
    state: BState,
    cert_group_id: GroupId,
    t0: float,
) -> Tuple[Optional[ValidationResult], Optional[Tuple[Tuple[GroupId, PoseId], ...]]]:
    raw = cert_dict.get("oracle_assignment_witness")
    if not isinstance(raw, list) or not raw:
        return (
            _vr("schema_err", t0, "oracle_assignment_witness must be non-empty list"),
            None,
        )
    pairs: List[Tuple[GroupId, PoseId]] = []
    for idx, entry in enumerate(raw):
        if not isinstance(entry, list) or len(entry) != 2:
            return (
                _vr("schema_err", t0, f"oracle_assignment_witness[{idx}] must be 2-element list"),
                None,
            )
        g, p = entry
        if not _is_non_empty_str(g):
            return (
                _vr("schema_err", t0, f"oracle_assignment_witness[{idx}].group_id must be non-empty str"),
                None,
            )
        if not _is_non_empty_str(p):
            return (
                _vr("schema_err", t0, f"oracle_assignment_witness[{idx}].pose_id must be non-empty str"),
                None,
            )
        if g != cert_group_id:
            return (
                _vr(
                    "unsound",
                    t0,
                    f"oracle_assignment_witness[{idx}] group {g!r} != cert.group_id {cert_group_id!r} "
                    f"(F9 single-group invariant)",
                ),
                None,
            )
        group_state = state.groups[cert_group_id]
        if p not in group_state.pose_domain:
            return (
                _vr(
                    "unsound",
                    t0,
                    f"oracle_assignment_witness[{idx}] pose {p!r} not in group {cert_group_id!r} pose_domain",
                ),
                None,
            )
        pairs.append((cast(GroupId, g), cast(PoseId, p)))
    # Multiset count per pose ≤ group.demand
    counts = Counter(pairs)
    group_demand = state.groups[cert_group_id].demand
    for (g_p, count) in counts.items():
        if count > group_demand:
            return (
                _vr(
                    "unsound",
                    t0,
                    f"oracle_assignment_witness pose {g_p[1]!r} count {count} > group demand {group_demand}",
                ),
                None,
            )
    return None, tuple(pairs)


def _validate_ghost_scope(
    cert_dict: Dict[str, Any], cut: Cut, state: BState, t0: float
) -> Optional[ValidationResult]:
    if cut.scope is None or cut.scope.ghost_rect_id == GHOST_AGNOSTIC:
        return _vr(
            "unsound",
            t0,
            "F9 scope.ghost_rect_id == GHOST_AGNOSTIC rejected (F9 must be ghost-bound)",
        )
    try:
        cert_ghost = _parse_ghost_rect_repr(cert_dict.get("ghost_rect_repr"))
    except ValueError as e:
        return _vr("schema_err", t0, str(e))
    state_ghost = state.ghost_rect
    if state_ghost is None:
        return _vr(
            "unsound",
            t0,
            "state.ghost_rect is None but F9 is ghost-bound (state drift)",
        )
    if cert_ghost != tuple(state_ghost):
        return _vr(
            "unsound",
            t0,
            f"cert.ghost_rect_repr {cert_ghost} != state.ghost_rect {tuple(state_ghost)} (scope drift)",
        )
    return None


def _compute_safe_max_allowed_area(
    window_cells: FrozenSet[Cell],
    cert_group_id: GroupId,
    state: BState,
) -> int:
    """Recompute the safe upper bound for F9 max_allowed_area.

    Mathematical basis: |W| - |(ghost ∪ exterior ∪ cell_owner_other) ∩ W|.
    cell_owner_other = cells owned by other groups (cert.group_id excluded
    because those cells are part of the witness assignment under consideration).

    See module-level note: this helper is intentionally NOT shared with F1's
    compute_static_capacity. F1 cap_R is static (no cell_owner); F9 safe_ub
    is dynamic (cell_owner-aware). Sharing would silently break F1's
    cross-ghost-replay invariant.
    """
    blocked_other: set[Cell] = set(state.ghost_cells) | set(state.exterior_blocks)
    for cell, (owner_g, _slot) in state.cell_owner.items():
        if owner_g != cert_group_id:
            blocked_other.add(cell)
    return len(window_cells) - len(blocked_other & window_cells)


def _validate_max_allowed_area(
    cert_dict: Dict[str, Any],
    window_cells: FrozenSet[Cell],
    cert_group_id: GroupId,
    state: BState,
    t0: float,
) -> Tuple[Optional[ValidationResult], int, int]:
    """Returns (error_or_None, cert_max_allowed_area, safe_ub)."""
    raw = cert_dict.get("max_allowed_area")
    if not _is_strict_int(raw):
        return (
            _vr("schema_err", t0, f"max_allowed_area must be strict int, got {raw!r}"),
            -1,
            -1,
        )
    cert_max = cast(int, raw)
    if cert_max < 0:
        return _vr("schema_err", t0, f"max_allowed_area must be >= 0, got {cert_max}"), -1, -1
    if cert_max > len(window_cells):
        return (
            _vr(
                "schema_err",
                t0,
                f"max_allowed_area {cert_max} > |W| {len(window_cells)} (cannot exceed window area)",
            ),
            -1,
            -1,
        )
    safe_ub = _compute_safe_max_allowed_area(window_cells, cert_group_id, state)
    if cert_max > safe_ub:
        return (
            _vr(
                "unsound",
                t0,
                f"max_allowed_area {cert_max} > safe upper bound {safe_ub} "
                f"(cert claims a looser bound than the static geometry allows)",
            ),
            cert_max,
            safe_ub,
        )
    return None, cert_max, safe_ub


def _recompute_assignment_area_overlap(
    witness_pairs: Tuple[Tuple[GroupId, PoseId], ...],
    window_cells: FrozenSet[Cell],
    state: BState,
) -> int:
    """Sum |occupied_cells(pose) ∩ W| for each (group, pose) in witness.

    Uses state.candidate_placements when available (real source-of-truth).
    Returns -1 if any pose lookup fails (validator treats as unsound).
    """
    from src.cuts.helpers.candidate_placements import find_pose

    total = 0
    for (g, p) in witness_pairs:
        pose = find_pose(state, g, p)
        if pose is None:
            return -1
        occupied = pose.get("occupied_cells", [])
        for raw_cell in occupied:
            if not isinstance(raw_cell, (list, tuple)) or len(raw_cell) != 2:
                continue
            cell = (int(raw_cell[0]), int(raw_cell[1]))
            if cell in window_cells:
                total += 1
    return total


def _validate_witness_overflow(
    witness_pairs: Tuple[Tuple[GroupId, PoseId], ...],
    window_cells: FrozenSet[Cell],
    cert_max_allowed_area: int,
    state: BState,
    t0: float,
) -> Optional[ValidationResult]:
    recomputed_sum = _recompute_assignment_area_overlap(witness_pairs, window_cells, state)
    if recomputed_sum < 0:
        return _vr(
            "unsound",
            t0,
            "oracle_assignment_witness references pose not findable in state.candidate_placements",
        )
    if recomputed_sum <= cert_max_allowed_area:
        return _vr(
            "unsound",
            t0,
            f"recomputed witness area overlap {recomputed_sum} <= max_allowed_area "
            f"{cert_max_allowed_area} (strict overflow required, equality does not cut)",
        )
    return None


def validate_density_envelope(
    cut: Cut,
    state: BState,
    canonical_rules: Dict[str, Any],
) -> ValidationResult:
    """Re-validate F9 density_envelope cut. Trust boundary: oracle untrusted.

    7-phase validation:
    1. cert payload JSON parse
    2. cert_kind == 'density_envelope_v1'
    3. witness_kind ∈ ACCEPTED_WITNESS_KIND (area-only invariant)
    4. window_rect schema + 70×70 grid bound
    5. group_id ∈ state.groups
    6. oracle_assignment_witness: 1-tuple per (g, p), g == cert.group_id,
       p ∈ pose_domain, multiset count ≤ group.demand
    7. ghost scope: scope.ghost_rect_id != GHOST_AGNOSTIC + cert.ghost_rect_repr
       byte-equal state.ghost_rect
    8. max_allowed_area: strict int, 0 ≤ value ≤ |W|, ≤ safe upper bound
       (validator independently recomputed)
    9. Witness overflow: sum |pose_cells ∩ W| > max_allowed_area (strict)
    """
    t0 = time.monotonic()
    del canonical_rules

    if cut.cert is None or cut.geometric_payload is None:
        return _vr(
            "schema_err",
            t0,
            "F9 requires non-empty cert + geometric_payload (geometric mode)",
        )

    try:
        cert_dict = _parse_cert_payload(cut.cert.cert_payload)
    except ValueError as e:
        return _vr("schema_err", t0, str(e))

    for error in (
        _validate_cert_kind(cert_dict, t0),
        _validate_witness_kind(cert_dict, t0),
    ):
        if error is not None:
            return error

    win_err, window_rect = _validate_window_rect(cert_dict, t0)
    if win_err is not None:
        return win_err
    if window_rect is None:
        return _vr("schema_err", t0, "window_rect parse returned None")
    window_cells = _window_cells(window_rect)

    group_err, cert_group_id = _validate_group(cert_dict, state, t0)
    if group_err is not None:
        return group_err
    if cert_group_id is None:
        return _vr("schema_err", t0, "group_id parse returned None")

    witness_err, witness_pairs = _validate_assignment_witness(cert_dict, state, cert_group_id, t0)
    if witness_err is not None:
        return witness_err
    if witness_pairs is None:
        return _vr("schema_err", t0, "oracle_assignment_witness parse returned None")

    ghost_err = _validate_ghost_scope(cert_dict, cut, state, t0)
    if ghost_err is not None:
        return ghost_err

    area_err, cert_max, _safe_ub = _validate_max_allowed_area(
        cert_dict, window_cells, cert_group_id, state, t0
    )
    if area_err is not None:
        return area_err

    overflow_err = _validate_witness_overflow(
        witness_pairs, window_cells, cert_max, state, t0
    )
    if overflow_err is not None:
        return overflow_err

    return _vr("ok", t0)


def evaluate_geometric_density_envelope(cut: Cut, state: BState) -> bool:
    """Evaluator: sum(|cells_of_cert_group ∈ cell_owner ∩ W|) > max_allowed_area.

    Strict inequality per PROJECT_LOCK §3A — equality does not cut.
    Fail-safe: returns False on any malformed payload.
    """
    if cut.geometric_payload is None:
        return False
    try:
        cert_dict = _parse_cert_payload(cut.geometric_payload)
        if cert_dict.get("cert_kind") != "density_envelope_v1":
            return False
        window_rect = _parse_window_rect(cert_dict.get("window_rect"))
        group_id = cert_dict.get("group_id")
        max_allowed = cert_dict.get("max_allowed_area")
        if not _is_non_empty_str(group_id) or not _is_strict_int(max_allowed):
            return False
        wx, wy, wh, ww = window_rect
        occupied = 0
        for cell, (owner_g, _slot) in state.cell_owner.items():
            if owner_g != group_id:
                continue
            cx, cy = cell
            if wx <= cx < wx + wh and wy <= cy < wy + ww:
                occupied += 1
        return occupied > cast(int, max_allowed)
    except Exception:  # noqa: BLE001 — fail-safe
        return False


def watcher_keys_density_envelope(cut: Cut) -> Dict[str, List[Any]]:
    """Return watcher keys for CutStore.add_cut.

    F9 watches: cells inside window (by_cell_watcher) + cert.group_id
    (by_group_watcher) + window region id (by_region_watcher).
    by_ghost_watcher is auto-added by store from cut.scope.ghost_rect_id.
    """
    if cut.geometric_payload is None:
        return {"cell_keys": [], "group_keys": [], "region_keys": []}
    try:
        cert_dict = _parse_cert_payload(cut.geometric_payload)
        rect = _parse_window_rect(cert_dict.get("window_rect"))
        group_id = cert_dict.get("group_id")
        if not _is_non_empty_str(group_id):
            return {"cell_keys": [], "group_keys": [], "region_keys": []}
        x, y, h, w = rect
        cells = [(x + i, y + j) for i in range(h) for j in range(w)]
        region_id = f"density_envelope:{x},{y},{h},{w}"
        return {
            "cell_keys": cells,
            "group_keys": [cast(str, group_id)],
            "region_keys": [region_id],
        }
    except Exception:  # noqa: BLE001 — fail-safe
        return {"cell_keys": [], "group_keys": [], "region_keys": []}
