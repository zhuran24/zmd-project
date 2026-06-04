"""Family 8 power_grid_reach — empty BFS-disconnect validator + watcher (P1.2B-F8).

PROJECT_LOCK §3A locked invariants (Phase 1.2 single-case scope):
- **Single cert_kind**: only ``"power_pole_bfs_disconnect_ghost"``. The
  ``cell_owner``-causes case (``"power_pole_bfs_disconnect_cell_owner"``)
  and ``"exterior_blocks_jump"`` variant deferred to Phase 1.5+.
- **Ghost-bound**: ``cut.scope.ghost_rect_id == GHOST_AGNOSTIC`` rejected;
  the pole-jump graph topology depends on ghost AABB occlusion.
- **F7 ↔ F8 mutual exclusion**: F7 fires when CoverSet is empty (no pole
  candidate within radius). F8 fires when CoverSet is non-empty but the
  pole-jump BFS from protocol_core does not reach any candidate. Oracle
  pipeline runs F7 first; F8 only when F7 returns nothing.
- **Real canonical data**: pole shape is **2×2 rigid** (canonical_rules
  ``power_pole.dimensions``), protocol_core footprint is **9×9**
  (canonical_rules ``protocol_core.dimensions``), and ``pole_jump_radius``
  must equal ``canonical_rules.facility_templates.power_pole.power_coverage_radius``
  in Phase 1.2. Dedicated pole→pole jump-radius schema can supersede this
  only with an explicit lock/spec/test update.
- **needs_power gate**: validator rejects facilities whose
  ``facility_templates[ft].needs_power`` is not True (mirror F7).
- **Cert holds NO graph snapshot**: validator independently rebuilds the
  power graph + BFS from ``state``; ``cert.power_graph_b64`` deprecated
  per Gemini F8 design merger (4 MB/cut otherwise; validator recompute
  is the soundness source).

Cert payload schema (canonical JSON, sorted keys, no Optionals):
    cert_kind: "power_pole_bfs_disconnect_ghost"
    facility_group: non-empty str ∈ state.groups
    facility_pose_id: non-empty str ∈ state.groups[facility_group].pose_domain
    facility_cells: list of [int, int] (sorted lex, dedup, in-grid)
    pole_jump_radius: float (> 0)
    pole_shape_canonical: "2x2_rigid"
    protocol_core_cell: [int, int] (anchor cell, in-grid)
    ghost_rect_repr: [x, y, h, w] (4 strict int, byte-equal state.ghost_rect)
    exterior_blocks_digest: sha256 hex of sorted exterior_blocks canonical

Evaluator: F8 is **geometric** mode (``_FAMILY_MODE_MAP``); cert in
``geometric_payload`` (``cut.literals`` MUST be None). The
``evaluate_geometric_power_grid_reach`` hot path is O(1): under the scope
binding (ghost + exterior), the pole-jump BFS disconnect is monotonically
preserved by ``free_cells`` shrinking (cell_owner only adds blockers), so
the validator's heavy BFS recompute is unnecessary on each evaluation.

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F8
- docs/研究/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md v1.1
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, FrozenSet, List, Literal, Optional, Tuple, cast

from src.cuts.helpers import canonical_sot
from src.cuts.helpers.power_cover import compute_cover_set, enumerate_valid_pole_anchors
from src.cuts.helpers.power_network import any_target_reachable_from_pc
from src.cuts.lifecycle import (
    GHOST_AGNOSTIC,
    BState,
    Cell,
    Cut,
    ValidationResult,
    compute_exterior_blocks_hash,
    compute_ghost_rect_id,
)


ValidationKind = Literal["ok", "unsound", "timeout", "schema_err"]


_POLE_SHAPE_PATTERN: re.Pattern[str] = re.compile(r"^\d+x\d+_rigid$")
_GRID_SIZE: int = 70
_PROTOCOL_CORE_SIZE: int = 9  # canonical_rules.facility_templates.protocol_core.dimensions


def _vr(kind: ValidationKind, t0: float, detail: str = "") -> ValidationResult:
    return ValidationResult(kind=kind, elapsed_seconds=time.monotonic() - t0, detail=detail or None)


def _is_strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_strict_float(value: object) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float))


def _is_non_empty_str(value: object) -> bool:
    return isinstance(value, str) and value != ""


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


def _parse_facility_cells(value: object) -> Tuple[Tuple[int, int], ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("facility_cells must be a non-empty list")
    out: List[Tuple[int, int]] = []
    seen: set[Tuple[int, int]] = set()
    prev: Optional[Tuple[int, int]] = None
    for idx, entry in enumerate(value):
        if not isinstance(entry, list) or len(entry) != 2:
            raise ValueError(f"facility_cells[{idx}] must be 2-element list")
        x_raw, y_raw = entry
        if not _is_strict_int(x_raw) or not _is_strict_int(y_raw):
            raise ValueError(f"facility_cells[{idx}] must contain strict ints, got {entry!r}")
        x = cast(int, x_raw)
        y = cast(int, y_raw)
        if not (0 <= x < _GRID_SIZE and 0 <= y < _GRID_SIZE):
            raise ValueError(f"facility_cells[{idx}] out of grid: {(x, y)!r}")
        if (x, y) in seen:
            raise ValueError(f"facility_cells[{idx}] duplicate cell {(x, y)!r}")
        seen.add((x, y))
        if prev is not None and (x, y) <= prev:
            raise ValueError(
                f"facility_cells not sorted ascending at {idx}: {prev!r} >= {(x, y)!r}"
            )
        prev = (x, y)
        out.append((x, y))
    return tuple(out)


def _parse_protocol_core_cell(value: object) -> Tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"protocol_core_cell must be 2-element list, got {value!r}")
    x_raw, y_raw = value
    if not _is_strict_int(x_raw) or not _is_strict_int(y_raw):
        raise ValueError(f"protocol_core_cell must contain strict ints, got {value!r}")
    x = cast(int, x_raw)
    y = cast(int, y_raw)
    # Gemini F8 round 4 Finding #4 (HIGH): explicit lower-bound check —
    # the prior `0 <= x + size <= GRID_SIZE` form silently accepted x=-1
    # (size 9 → 8, in [0, 70]).
    if x < 0 or y < 0:
        raise ValueError(f"protocol_core_cell must be non-negative, got {(x, y)!r}")
    if x + _PROTOCOL_CORE_SIZE > _GRID_SIZE:
        raise ValueError(
            f"protocol_core_cell x={x} + size {_PROTOCOL_CORE_SIZE} exceeds grid {_GRID_SIZE}"
        )
    if y + _PROTOCOL_CORE_SIZE > _GRID_SIZE:
        raise ValueError(
            f"protocol_core_cell y={y} + size {_PROTOCOL_CORE_SIZE} exceeds grid {_GRID_SIZE}"
        )
    return (x, y)


def _protocol_core_cells(anchor: Tuple[int, int]) -> FrozenSet[Cell]:
    ax, ay = anchor
    return frozenset(
        (ax + dx, ay + dy)
        for dx in range(_PROTOCOL_CORE_SIZE)
        for dy in range(_PROTOCOL_CORE_SIZE)
    )


def _validate_cert_kind(cert_dict: Dict[str, Any], t0: float) -> Optional[ValidationResult]:
    kind = cert_dict.get("cert_kind")
    if kind != "power_pole_bfs_disconnect_ghost":
        return _vr(
            "schema_err",
            t0,
            f"cert_kind must be 'power_pole_bfs_disconnect_ghost' (Phase 1.2 single-case), got {kind!r}",
        )
    return None


def _validate_scalars(
    cert_dict: Dict[str, Any], t0: float
) -> Tuple[Optional[ValidationResult], Optional[Tuple[Tuple[int, int], ...]], Optional[Tuple[int, int]]]:
    fg = cert_dict.get("facility_group")
    if not _is_non_empty_str(fg):
        return _vr("schema_err", t0, f"facility_group must be non-empty str, got {fg!r}"), None, None
    fp = cert_dict.get("facility_pose_id")
    if not _is_non_empty_str(fp):
        return _vr("schema_err", t0, f"facility_pose_id must be non-empty str, got {fp!r}"), None, None
    pjr = cert_dict.get("pole_jump_radius")
    if not _is_strict_float(pjr) or cast(float, pjr) <= 0.0:
        return _vr("schema_err", t0, f"pole_jump_radius must be float > 0, got {pjr!r}"), None, None
    psc = cert_dict.get("pole_shape_canonical")
    if not _is_non_empty_str(psc) or not _POLE_SHAPE_PATTERN.match(cast(str, psc)):
        return (
            _vr(
                "schema_err",
                t0,
                f"pole_shape_canonical must match r'^\\d+x\\d+_rigid$', got {psc!r}",
            ),
            None,
            None,
        )
    if cast(str, psc) != "2x2_rigid":
        return (
            _vr(
                "schema_err",
                t0,
                f"pole_shape_canonical locked to '2x2_rigid' Phase 1.2 (canonical_rules truth), got {psc!r}",
            ),
            None,
            None,
        )
    eb = cert_dict.get("exterior_blocks_digest")
    if not _is_non_empty_str(eb):
        return (
            _vr("schema_err", t0, f"exterior_blocks_digest must be non-empty str, got {eb!r}"),
            None,
            None,
        )
    try:
        cells = _parse_facility_cells(cert_dict.get("facility_cells"))
    except ValueError as e:
        return _vr("schema_err", t0, str(e)), None, None
    try:
        pc_cell = _parse_protocol_core_cell(cert_dict.get("protocol_core_cell"))
    except ValueError as e:
        return _vr("schema_err", t0, str(e)), None, None
    return None, cells, pc_cell


def _validate_ghost_scope_binding(
    cut: Cut, cert_dict: Dict[str, Any], state: BState, t0: float
) -> Optional[ValidationResult]:
    if cut.scope is None:
        return _vr("schema_err", t0, "cut.scope must be non-None for F8")
    if cut.scope.ghost_rect_id == GHOST_AGNOSTIC:
        return _vr(
            "unsound",
            t0,
            "F8 power_grid_reach does not allow GHOST_AGNOSTIC scope "
            "(power-graph topology depends on ghost AABB occlusion)",
        )
    if state.ghost_rect is None:
        return _vr(
            "unsound",
            t0,
            "F8 cert is ghost-bound but state.ghost_rect is None — drift",
        )
    cert_ghost = cert_dict.get("ghost_rect_repr")
    if not isinstance(cert_ghost, list) or len(cert_ghost) != 4:
        return _vr(
            "schema_err",
            t0,
            f"ghost_rect_repr must be 4-element list, got {cert_ghost!r}",
        )
    for idx, value in enumerate(cert_ghost):
        if not _is_strict_int(value):
            return _vr(
                "schema_err",
                t0,
                f"ghost_rect_repr[{idx}] must be strict int, got {value!r}",
            )
    if tuple(cast(List[int], cert_ghost)) != tuple(state.ghost_rect):
        return _vr(
            "unsound",
            t0,
            f"ghost_rect_repr drift: cert={tuple(cert_ghost)}, state={tuple(state.ghost_rect)}",
        )
    cert_exterior = cast(str, cert_dict["exterior_blocks_digest"])
    actual_digest = compute_exterior_blocks_hash(state)
    if cert_exterior != actual_digest:
        return _vr(
            "unsound",
            t0,
            f"exterior_blocks_digest drift: cert={cert_exterior!r}, state={actual_digest!r}",
        )
    return None


def _validate_group_and_template(
    cert_dict: Dict[str, Any], state: BState, t0: float
) -> Optional[ValidationResult]:
    gid = cast(str, cert_dict["facility_group"])
    pose_id = cast(str, cert_dict["facility_pose_id"])
    if gid not in state.groups:
        return _vr(
            "unsound",
            t0,
            f"facility_group {gid!r} not in state.groups (registry rotated or fake gid)",
        )
    if pose_id not in state.groups[gid].pose_domain:
        return _vr(
            "unsound",
            t0,
            f"facility_pose_id {pose_id!r} not in state.groups[{gid!r}].pose_domain",
        )
    if state.instance_to_facility_type is None:
        return _vr(
            "unsound",
            t0,
            "state.instance_to_facility_type missing — F8 cannot verify needs_power "
            "without source-of-truth (fail-closed)",
        )
    facility_type = state.instance_to_facility_type.get(gid)
    if facility_type is None:
        return _vr(
            "unsound",
            t0,
            f"facility_group {gid!r} has no facility_type mapping",
        )
    if state.facility_templates is None:
        return _vr(
            "unsound",
            t0,
            "state.facility_templates missing — F8 cannot verify needs_power "
            "without source-of-truth (fail-closed)",
        )
    tpl = state.facility_templates.get(facility_type)
    if not isinstance(tpl, dict):
        return _vr(
            "unsound",
            t0,
            f"facility_templates[{facility_type!r}] missing or not a dict",
        )
    if tpl.get("needs_power") is not True:
        return _vr(
            "unsound",
            t0,
            f"facility_group {gid!r} (facility_type {facility_type!r}) needs_power is not True "
            f"— F8 cut against non-powered facility is bogus",
        )
    return None



def _validate_facility_cells_match_pose_registry(
    facility_cells: Tuple[Tuple[int, int], ...],
    cert_dict: Dict[str, Any],
    state: BState,
    t0: float,
) -> Optional[ValidationResult]:
    # Fail closed unless cert facility_cells exactly match the named pose.
    gid = cast(str, cert_dict["facility_group"])
    pose_id = cast(str, cert_dict["facility_pose_id"])

    if state.instance_to_facility_type is None:
        return _vr("unsound", t0, "state.instance_to_facility_type missing")
    facility_type = state.instance_to_facility_type.get(gid)
    if facility_type is None:
        return _vr("unsound", t0, f"facility_group {gid!r} has no facility_type mapping")

    placements = state.candidate_placements
    if not isinstance(placements, dict):
        return _vr("unsound", t0, "state.candidate_placements missing or malformed")
    pools = placements.get("facility_pools")
    if not isinstance(pools, dict):
        return _vr("unsound", t0, "candidate_placements.facility_pools missing or malformed")
    pool = pools.get(facility_type)
    if not isinstance(pool, list):
        return _vr(
            "unsound",
            t0,
            f"candidate_placements.facility_pools[{facility_type!r}] missing or malformed",
        )

    matches = [
        entry
        for entry in pool
        if isinstance(entry, dict) and entry.get("pose_id") == pose_id
    ]
    if not matches:
        return _vr(
            "unsound",
            t0,
            f"facility_pose_id {pose_id!r} not found in candidate_placements for {facility_type!r}",
        )
    if len(matches) != 1:
        return _vr(
            "unsound",
            t0,
            f"facility_pose_id {pose_id!r} is not unique in candidate_placements for {facility_type!r}; "
            "registry binding ambiguous",
        )

    entry = matches[0]
    occupied = entry.get("occupied_cells")
    if not isinstance(occupied, list) or not occupied:
        return _vr("unsound", t0, f"pose {pose_id!r} occupied_cells missing or malformed")
    actual_cells: List[Tuple[int, int]] = []
    seen: set[Tuple[int, int]] = set()
    for idx, raw in enumerate(occupied):
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            return _vr("unsound", t0, f"occupied_cells[{idx}] malformed for pose {pose_id!r}")
        x_raw, y_raw = raw
        if not _is_strict_int(x_raw) or not _is_strict_int(y_raw):
            return _vr("unsound", t0, f"occupied_cells[{idx}] has non-int coords")
        cell = (cast(int, x_raw), cast(int, y_raw))
        if not (0 <= cell[0] < _GRID_SIZE and 0 <= cell[1] < _GRID_SIZE):
            return _vr("unsound", t0, f"occupied_cells[{idx}] out of grid: {cell!r}")
        if cell in seen:
            return _vr("unsound", t0, f"occupied_cells duplicate cell {cell!r}")
        seen.add(cell)
        actual_cells.append(cell)
    actual = tuple(sorted(actual_cells))
    if facility_cells != actual:
        return _vr(
            "unsound",
            t0,
            f"facility_cells do not match candidate_placements for {(gid, pose_id)!r}",
        )
    return None


def _build_full_free_mask(
    state: BState, facility_cells: Tuple[Tuple[int, int], ...], pc_anchor: Tuple[int, int]
) -> FrozenSet[Cell]:
    """Free-cell mask = grid - ghost - exterior - cell_owner - facility - protocol_core.

    Per Gemini F7/F8 design (same pattern as F7 round 1 fix): the protected
    facility and protocol_core both occupy their footprint, so pole anchors
    cannot live there.
    """
    facility_set = frozenset(facility_cells)
    pc_cells = _protocol_core_cells(pc_anchor)
    blocked = (
        frozenset(state.ghost_cells)
        | frozenset(state.exterior_blocks)
        | frozenset(state.cell_owner.keys())
        | facility_set
        | pc_cells
    )
    return frozenset(
        (x, y) for x in range(_GRID_SIZE) for y in range(_GRID_SIZE) if (x, y) not in blocked
    )


def _validate_disconnect_witness(
    facility_cells: Tuple[Tuple[int, int], ...],
    pc_anchor: Tuple[int, int],
    cert_dict: Dict[str, Any],
    state: BState,
    t0: float,
) -> Optional[ValidationResult]:
    """Phase 6/7: independently rebuild power graph and verify disconnect.

    Gemini F8 round 1 Finding #1 + #2:
    - poles fed to ``build_power_network`` MUST be the full free-mask anchor
      set, not just CoverSet — otherwise the graph lacks the spanning
      intermediate poles and BFS reports a false disconnect.
    - protocol_core is 9×9; pass the full footprint as ``pc_cells`` so that
      pole↔core edges fire when any core cell is within radius.

    1. Full free mask excludes ghost ∪ exterior ∪ cell_owner ∪ facility ∪ pc footprint
    2. CoverSet (facility) must be non-empty (else this is F7 territory)
    3. Build power graph over the full pole-anchor set ∪ pc footprint
    4. BFS from any pc cell must NOT reach any CoverSet pole
    """
    pole_radius = float(cast(float, cert_dict["pole_jump_radius"]))
    free_cells = _build_full_free_mask(state, facility_cells, pc_anchor)
    cover_set = compute_cover_set(facility_cells, free_cells, pole_radius)
    if not cover_set:
        return _vr(
            "unsound",
            t0,
            "F8 cert claims disconnect but CoverSet is empty — should be F7 case",
        )
    all_poles = enumerate_valid_pole_anchors(free_cells)
    pc_cells = _protocol_core_cells(pc_anchor)
    if any_target_reachable_from_pc(
        all_poles,
        cover_set,
        pole_radius=pole_radius,
        pc_cells=pc_cells,
        ghost_rect=state.ghost_rect,
    ):
        return _vr(
            "unsound",
            t0,
            "F8 cert claims disconnect but BFS recompute connects "
            "at least one CoverSet pole to protocol_core",
        )
    return None


def _validate_ghost_only_disconnect(
    facility_cells: Tuple[Tuple[int, int], ...],
    pc_anchor: Tuple[int, int],
    cert_dict: Dict[str, Any],
    state: BState,
    t0: float,
) -> Optional[ValidationResult]:
    """Phase 8: ensure the ghost is the SOLE cause (not cell_owner).

    Drop cell_owner from the mask. If the resulting CoverSet has at least
    one pole that reaches pc_anchor via the ghost-only power graph, then
    cell_owner is what actually disconnected the network → single-cause
    "ghost" cert is unsound (Phase 1.5+ multi-cause cut).
    """
    pole_radius = float(cast(float, cert_dict["pole_jump_radius"]))
    facility_set = frozenset(facility_cells)
    pc_cells = _protocol_core_cells(pc_anchor)
    blocked = (
        frozenset(state.ghost_cells)
        | frozenset(state.exterior_blocks)
        | facility_set
        | pc_cells
    )
    ghost_only_free = frozenset(
        (x, y) for x in range(_GRID_SIZE) for y in range(_GRID_SIZE) if (x, y) not in blocked
    )
    cover_ghost = compute_cover_set(facility_cells, ghost_only_free, pole_radius)
    if not cover_ghost:
        # Ghost+exterior alone already empty the CoverSet → F7 territory,
        # not F8 — but phase 6/7 already caught that. Here we only need to
        # confirm that the disconnect persists ignoring cell_owner.
        return _vr(
            "unsound",
            t0,
            "F8 cert claims ghost cause but ghost+exterior alone leave CoverSet empty "
            "— belongs to F7 (empty-CoverSet) family",
        )
    # Gemini F8 round 1 Finding #1 + #2: pass FULL anchor set + multi-cell pc
    all_poles_ghost = enumerate_valid_pole_anchors(ghost_only_free)
    if any_target_reachable_from_pc(
        all_poles_ghost,
        cover_ghost,
        pole_radius=pole_radius,
        pc_cells=pc_cells,
        ghost_rect=state.ghost_rect,
    ):
        return _vr(
            "unsound",
            t0,
            "F8 cert claims ghost cause but ghost-only power graph reconnects "
            "CoverSet to protocol_core — cell_owner is the true cause "
            "(Phase 1.5+ multi-literal handles this)",
        )
    return None


def _lookup_canonical_pole_radius(state: BState) -> Optional[float]:
    """Delegates to the shared SoT helper (single implementation, fail-closed)."""
    return canonical_sot.lookup_canonical_pole_radius(state)


def _lookup_canonical_template_dims(state: BState, template_id: str) -> Optional[Tuple[int, int]]:
    """Delegates to the shared SoT helper (single implementation, fail-closed)."""
    return canonical_sot.lookup_canonical_template_dims(state, template_id)


def _validate_power_pole_template_sot(state: BState, t0: float) -> Optional[ValidationResult]:
    dims = _lookup_canonical_template_dims(state, "power_pole")
    if dims is None:
        return _vr(
            "unsound",
            t0,
            "state.canonical_rules.facility_templates.power_pole.dimensions missing "
            "— cannot verify pole_shape_canonical against source-of-truth (fail-closed)",
        )
    if dims != (2, 2):
        return _vr(
            "unsound",
            t0,
            f"canonical power_pole dimensions {dims[0]}x{dims[1]} != cert/helper locked 2x2",
        )
    return None


def _validate_protocol_core_template_sot(state: BState, t0: float) -> Optional[ValidationResult]:
    dims = _lookup_canonical_template_dims(state, "protocol_core")
    if dims is None:
        return _vr(
            "unsound",
            t0,
            "state.canonical_rules.facility_templates.protocol_core.dimensions missing "
            "— cannot verify protocol_core_cell footprint against source-of-truth (fail-closed)",
        )
    if dims != (_PROTOCOL_CORE_SIZE, _PROTOCOL_CORE_SIZE):
        return _vr(
            "unsound",
            t0,
            f"canonical protocol_core dimensions {dims[0]}x{dims[1]} != "
            f"validator locked {_PROTOCOL_CORE_SIZE}x{_PROTOCOL_CORE_SIZE}",
        )
    return None


def _validate_pole_radius_sot(
    cert_dict: Dict[str, Any],
    state: BState,
    t0: float,
) -> Optional[ValidationResult]:
    """Cross-check cert.pole_jump_radius against canonical power_pole radius."""
    cert_radius_raw = cert_dict.get("pole_jump_radius")
    if not _is_strict_float(cert_radius_raw):
        return _vr("schema_err", t0, "pole_jump_radius missing or not numeric")
    cert_radius = float(cast(float, cert_radius_raw))
    canonical_radius = _lookup_canonical_pole_radius(state)
    if canonical_radius is None:
        return _vr(
            "unsound",
            t0,
            "state.canonical_rules.facility_templates.power_pole.power_coverage_radius "
            "missing — cannot verify pole_jump_radius against source-of-truth (fail-closed)",
        )
    if canonical_radius != cert_radius:
        return _vr(
            "unsound",
            t0,
            f"cert.pole_jump_radius={cert_radius} != canonical "
            f"power_coverage_radius={canonical_radius} — possibly forged",
        )
    return None


def _validate_pc_anchor_sot(
    pc_anchor: Tuple[int, int],
    state: BState,
    t0: float,
) -> Optional[ValidationResult]:
    """Cross-check protocol_core anchor footprint vs state.cell_owner.

    Phase 1.2: when state.cell_owner is empty (fixture / early phase),
    accept bounds-only (already validated upstream by _parse_protocol_core_cell).
    """
    if state.instance_to_facility_type is None or not state.cell_owner:
        return None
    ax, ay = pc_anchor
    for dx in range(_PROTOCOL_CORE_SIZE):
        for dy in range(_PROTOCOL_CORE_SIZE):
            owner = state.cell_owner.get((ax + dx, ay + dy))
            if owner is None:
                return _vr(
                    "unsound",
                    t0,
                    f"protocol_core_cell {pc_anchor}: footprint cell "
                    f"({ax + dx}, {ay + dy}) has no cell_owner — not a master placement",
                )
            gid = owner[0] if isinstance(owner, tuple) else owner
            if state.instance_to_facility_type.get(gid) != "protocol_core":
                return _vr(
                    "unsound",
                    t0,
                    f"protocol_core_cell {pc_anchor}: footprint cell "
                    f"({ax + dx}, {ay + dy}) owned by group {gid!r} "
                    f"which is not facility_type=protocol_core",
                )
    return None


def _validate_source_of_truth_scalars(
    pc_anchor: Tuple[int, int],
    cert_dict: Dict[str, Any],
    state: BState,
    t0: float,
) -> Optional[ValidationResult]:
    """Gemini F8 round 4 Finding #2 (CRITICAL): validator must independently
    cross-check the cert's ``pole_jump_radius`` and ``protocol_core_cell``
    against source-of-truth (canonical_rules + state.cell_owner). Without
    this check, an attacker can supply ``cert.pole_jump_radius = 0.001`` to
    fake a BFS disconnect, even when the matching active_assumption is set
    correctly to ``R=5`` (attach-scope passes, validator's recompute uses
    the malicious 0.001).
    """
    err = _validate_pole_radius_sot(cert_dict, state, t0)
    if err is not None:
        return err
    err = _validate_power_pole_template_sot(state, t0)
    if err is not None:
        return err
    err = _validate_protocol_core_template_sot(state, t0)
    if err is not None:
        return err
    return _validate_pc_anchor_sot(pc_anchor, state, t0)


def validate_power_grid_reach(
    cut: Cut,
    state: BState,
    canonical_rules: Dict[str, Any],
) -> ValidationResult:
    """9-phase F8 validator (Phase 1.2 single-case scope).

    Phases (fail-closed, first error returns):
    1. cert + payload non-None + JSON parse
    2. cert_kind == "power_pole_bfs_disconnect_ghost"
    3. scalar schema (group / pose / pole_jump_radius / shape_canonical /
       facility_cells / protocol_core_cell) — geometric mode, literals=None
    4. Ghost scope binding (non-AGNOSTIC + ghost_rect_repr + exterior digest)
    5. Group source-of-truth (group ∈ state.groups, pose ∈ pose_domain,
       facility_template lookup + needs_power == True)
    6. Cert↔source-of-truth scalar cross-check (Gemini F8 round 4 Finding #2):
       cert.pole_jump_radius == canonical_rules.power_pole.power_coverage_radius;
       power_pole/protocol_core dimensions match canonical_rules;
       cert.protocol_core_cell footprint owned by protocol_core in state
       (when cell_owner populated)
    7. Full disconnect recompute (CoverSet non-empty + BFS disjoint from pc)
    8. Ghost-only cause check (cell_owner is NOT the true cause)
    """
    t0 = time.monotonic()
    del canonical_rules

    if cut.cert is None or cut.geometric_payload is None:
        return _vr(
            "schema_err",
            t0,
            "F8 is geometric mode; cut.cert and cut.geometric_payload must be non-None",
        )
    if cut.literals is not None:
        return _vr(
            "schema_err",
            t0,
            "F8 is geometric mode; cut.literals must be None (got non-None)",
        )

    try:
        cert_dict = _parse_cert_payload(cut.cert.cert_payload)
    except ValueError as e:
        return _vr("schema_err", t0, str(e))

    err = _validate_cert_kind(cert_dict, t0)
    if err is not None:
        return err

    scalar_err, facility_cells, pc_anchor = _validate_scalars(cert_dict, t0)
    if scalar_err is not None:
        return scalar_err
    if facility_cells is None or pc_anchor is None:
        return _vr("schema_err", t0, "scalar parse returned None unexpectedly")

    for error in (
        _validate_ghost_scope_binding(cut, cert_dict, state, t0),
        _validate_group_and_template(cert_dict, state, t0),
        _validate_facility_cells_match_pose_registry(facility_cells, cert_dict, state, t0),
        _validate_source_of_truth_scalars(pc_anchor, cert_dict, state, t0),
        _validate_disconnect_witness(facility_cells, pc_anchor, cert_dict, state, t0),
        _validate_ghost_only_disconnect(facility_cells, pc_anchor, cert_dict, state, t0),
    ):
        if error is not None:
            return error

    return _vr("ok", t0)


def _eval_check_facility_placed(cert_dict: Dict[str, Any], state: BState) -> bool:
    """Gemini F8 round 1 Finding #3: facility must still be in selected_poses."""
    gid_raw = cert_dict.get("facility_group")
    pose_raw = cert_dict.get("facility_pose_id")
    if not isinstance(gid_raw, str) or not gid_raw:
        return False
    if not isinstance(pose_raw, str) or not pose_raw:
        return False
    group_state = state.groups.get(gid_raw)
    if group_state is None:
        return False
    return pose_raw in group_state.selected_poses


def _parse_pc_anchor_int_pair(pc_raw: object) -> Optional[Tuple[int, int]]:
    """Strict [int, int] parse; None on any malformed value."""
    if not isinstance(pc_raw, list) or len(pc_raw) != 2:
        return None
    x_raw, y_raw = pc_raw
    if isinstance(x_raw, bool) or isinstance(y_raw, bool):
        return None
    if not isinstance(x_raw, int) or not isinstance(y_raw, int):
        return None
    return (x_raw, y_raw)


def _footprint_owned_by_protocol_core(
    anchor: Tuple[int, int], state: BState
) -> bool:
    """All 9×9 cells at ``anchor`` owned by facility_type=protocol_core."""
    if state.instance_to_facility_type is None:
        return True
    for dx in range(_PROTOCOL_CORE_SIZE):
        for dy in range(_PROTOCOL_CORE_SIZE):
            owner = state.cell_owner.get((anchor[0] + dx, anchor[1] + dy))
            if owner is None:
                return False
            gid = owner[0] if isinstance(owner, tuple) else owner
            if state.instance_to_facility_type.get(gid) != "protocol_core":
                return False
    return True


def _eval_check_protocol_core_position(
    cert_dict: Dict[str, Any], state: BState
) -> bool:
    """Gemini F8 round 4 Finding #1: if master moves protocol_core away from
    the cert anchor, the disconnect may no longer hold. Hot-path O(81)
    check. Phase 1.2: bounds-only when state.cell_owner is empty.
    """
    anchor = _parse_pc_anchor_int_pair(cert_dict.get("protocol_core_cell"))
    if anchor is None:
        return False
    if not state.cell_owner:
        return True  # Phase 1.2 fixture/early-phase: bounds-only via validator scalars
    return _footprint_owned_by_protocol_core(anchor, state)


def evaluate_geometric_power_grid_reach(cut: Cut, state: BState) -> bool:
    """Hot-path evaluator. True iff F8 disconnect still holds.

    Per the F6/F7 pattern: under the scope binding (ghost + exterior), the
    BFS disconnect is monotonically preserved by ``free_cells`` shrinking
    (cell_owner only adds blockers). O(1) scope-drift guard suffices —
    re-running the heavy BFS recompute on every evaluation is wasted work.

    Gemini F8 round 1 Finding #3 (CRITICAL): spec §6 requires checking that
    the cert's (facility_group, facility_pose_id) is still in
    ``state.groups[gid].selected_poses``. Without this, ``literals=None``
    means the cut fires forever once active — even if the master moves the
    facility off the offending pose, the ghost-only scope is unchanged so
    the cut would poison the entire ghost AABB. Adding the placement check
    here keeps the evaluator O(1) (dict lookup + list-in) and preserves
    soundness while restoring correctness.

    Fail-safe: malformed payload / scope drift returns False.
    """
    if cut.geometric_payload is None or cut.scope is None:
        return False
    try:
        cert_dict = json.loads(cut.geometric_payload)
        if not isinstance(cert_dict, dict):
            return False
        if cert_dict.get("cert_kind") != "power_pole_bfs_disconnect_ghost":
            return False
        if cut.scope.ghost_rect_id != compute_ghost_rect_id(state.ghost_rect):
            return False
        if cut.scope.exterior_blocks_hash != compute_exterior_blocks_hash(state):
            return False
        if not _eval_check_facility_placed(cert_dict, state):
            return False
        if not _eval_check_protocol_core_position(cert_dict, state):
            return False
        return True
    except Exception:  # noqa: BLE001 — fail-safe
        return False


def watcher_keys_power_grid_reach(cut: Cut) -> Dict[str, List[Any]]:
    """Return watcher keys for CutStore.add_cut.

    F8 watches: facility_group (by_group) + (facility_group, facility_pose_id)
    (by_pose) + facility_cells (by_cell). by_ghost_watcher is auto-added by
    store from cut.scope.ghost_rect_id.

    Note: Phase 1.5+ may add a wider by_cell watcher covering the full pole
    anchor enumeration neighborhood (BoundingBox(facility, R_jump + pc_size))
    so cell_owner releases that reconnect the power graph re-trigger replay;
    Phase 1.2 keeps the watcher tight per F7's spec §8 v1.1 simplification.
    """
    if cut.geometric_payload is None:
        return {"group_keys": [], "pose_keys": [], "cell_keys": []}
    try:
        cert_dict = _parse_cert_payload(cut.geometric_payload)
        gid = cert_dict.get("facility_group")
        pose_id = cert_dict.get("facility_pose_id")
        if not _is_non_empty_str(gid) or not _is_non_empty_str(pose_id):
            return {"group_keys": [], "pose_keys": [], "cell_keys": []}
        cells_raw = cert_dict.get("facility_cells")
        if not isinstance(cells_raw, list):
            return {"group_keys": [], "pose_keys": [], "cell_keys": []}
        cells: List[Tuple[int, int]] = []
        for entry in cells_raw:
            if not isinstance(entry, list) or len(entry) != 2:
                return {"group_keys": [], "pose_keys": [], "cell_keys": []}
            cells.append((int(entry[0]), int(entry[1])))
        return {
            "group_keys": [cast(str, gid)],
            "pose_keys": [(cast(str, gid), cast(str, pose_id))],
            "cell_keys": cells,
        }
    except Exception:  # noqa: BLE001 — fail-safe
        return {"group_keys": [], "pose_keys": [], "cell_keys": []}
