"""Family 7 power_hitting_set — empty-CoverSet validator + watcher (P1.2B-F7).

PROJECT_LOCK §3A locked invariants (Phase 1.2 single-case scope):
- **Single cert_kind**: only ``"power_cover_emptyset_ghost"``. The cell_owner
  causation case (``"power_cover_emptyset_cell_owner"`` + multi-literal
  blocking_facility_literals) deferred to Phase 1.5+ (multi-shape generalize +
  causation split lifts).
- **Ghost-bound**: ``cut.scope.ghost_rect_id == GHOST_AGNOSTIC`` rejected;
  CoverSet definition depends on ghost cells.
- **Strict empty**: validator phase 6 requires
  ``compute_cover_set(facility_cells, full_free_cells, pole_radius) == ∅``;
  phase 7 also requires ``compute_cover_set_ghost_only(...) == ∅`` to ensure
  the single-literal cut is sound (a non-empty ghost-only CoverSet means
  ``cell_owner`` is the true cause and Phase 1.2 must NOT cut — multi-literal
  case is Phase 1.5+).
- **Real canonical data**: pole shape is **2×2 rigid** per
  ``rules/canonical_rules.json → facility_templates.power_pole.dimensions``
  (NOT 1×1 as the v1.1 spec text reads). ``pole_shape_canonical`` cert field
  is locked to ``"2x2_rigid"``. ``pole_radius`` cert field is the float carried
  from ``canonical_rules.facility_templates.power_pole.power_coverage_radius``
  (Euclidean cell-to-cell, per project consensus — schema lacks an explicit
  metric label, so cert + validator + helper share a single ``compute_cover_set``
  implementation as source of truth).
- **needs_power gate**: validator rejects facilities whose
  ``facility_templates[ft].needs_power`` is not True (Gemini F7 adversarial
  audit catch — a F7 cert against a non-powered facility is bogus).

Cert payload schema (canonical JSON, sorted keys, no Optionals):
    cert_kind: "power_cover_emptyset_ghost"
    facility_group: non-empty str ∈ state.groups
    facility_pose_id: non-empty str ∈ state.groups[facility_group].pose_domain
    facility_cells: list of [int, int] (sorted lex, dedup, in-grid)
    pole_radius: float (> 0)
    pole_shape_canonical: "2x2_rigid"
    ghost_rect_repr: [x, y, h, w] (4 strict int, byte-equal state.ghost_rect)
    exterior_blocks_digest: sha256 hex of sorted exterior_blocks canonical

Evaluator: F7 is literal-based; delegated to
``lifecycle.evaluate_literal_multiset`` (no F7-specific evaluator).

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F7
- docs/项目说明/12_go_criteria.md §8.1.x acceptance E
- docs/research/p3_b_design_v2_20260521/cut_family_specs/07_power_hitting_set.md v1.1
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Literal, Optional, Tuple, cast

from src.cuts.helpers.power_cover import compute_cover_set
from src.cuts.lifecycle import (
    GHOST_AGNOSTIC,
    BState,
    Cut,
    ValidationResult,
    compute_exterior_blocks_hash,
)


ValidationKind = Literal["ok", "unsound", "timeout", "schema_err"]


_POLE_SHAPE_PATTERN: re.Pattern[str] = re.compile(r"^\d+x\d+_rigid$")
_GRID_SIZE: int = 70


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


def _validate_cert_kind(cert_dict: Dict[str, Any], t0: float) -> Optional[ValidationResult]:
    kind = cert_dict.get("cert_kind")
    if kind != "power_cover_emptyset_ghost":
        return _vr(
            "schema_err",
            t0,
            f"cert_kind must be 'power_cover_emptyset_ghost' (Phase 1.2 single-case), got {kind!r}",
        )
    return None


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


def _validate_scalars(
    cert_dict: Dict[str, Any], t0: float
) -> Tuple[Optional[ValidationResult], Optional[Tuple[Tuple[int, int], ...]]]:
    fg = cert_dict.get("facility_group")
    if not _is_non_empty_str(fg):
        return _vr("schema_err", t0, f"facility_group must be non-empty str, got {fg!r}"), None
    fp = cert_dict.get("facility_pose_id")
    if not _is_non_empty_str(fp):
        return _vr("schema_err", t0, f"facility_pose_id must be non-empty str, got {fp!r}"), None
    pr = cert_dict.get("pole_radius")
    if not _is_strict_float(pr) or cast(float, pr) <= 0.0:
        return _vr("schema_err", t0, f"pole_radius must be strict float > 0, got {pr!r}"), None
    psc = cert_dict.get("pole_shape_canonical")
    if not _is_non_empty_str(psc) or not _POLE_SHAPE_PATTERN.match(cast(str, psc)):
        return (
            _vr(
                "schema_err",
                t0,
                f"pole_shape_canonical must match r'^\\d+x\\d+_rigid$', got {psc!r}",
            ),
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
        )
    eb = cert_dict.get("exterior_blocks_digest")
    if not _is_non_empty_str(eb):
        return (
            _vr("schema_err", t0, f"exterior_blocks_digest must be non-empty str, got {eb!r}"),
            None,
        )
    try:
        cells = _parse_facility_cells(cert_dict.get("facility_cells"))
    except ValueError as e:
        return _vr("schema_err", t0, str(e)), None
    return None, cells


def _validate_ghost_scope_binding(
    cut: Cut, cert_dict: Dict[str, Any], state: BState, t0: float
) -> Optional[ValidationResult]:
    if cut.scope is None:
        return _vr("schema_err", t0, "cut.scope must be non-None for F7")
    if cut.scope.ghost_rect_id == GHOST_AGNOSTIC:
        return _vr(
            "unsound",
            t0,
            "F7 power_hitting_set does not allow GHOST_AGNOSTIC scope "
            "(CoverSet depends on ghost_cells)",
        )
    if state.ghost_rect is None:
        return _vr(
            "unsound",
            t0,
            "F7 requires state.ghost_rect non-None to validate ghost binding",
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
            "state.instance_to_facility_type missing — F7 cannot verify needs_power "
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
            "state.facility_templates missing — F7 cannot verify needs_power "
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
            f"— F7 cut against non-powered facility is bogus",
        )
    return None


def _validate_coverset_empty(
    facility_cells: Tuple[Tuple[int, int], ...],
    cert_dict: Dict[str, Any],
    state: BState,
    t0: float,
) -> Optional[ValidationResult]:
    pole_radius = float(cast(float, cert_dict["pole_radius"]))
    # Per Gemini F7 round 1 BLOCKER #1: facility cells must be excluded from
    # the free-cell mask. During replay the facility may not yet be in
    # state.cell_owner, but its 3×3 (or larger) footprint still cannot host a
    # 2×2 pole — a pole anchor inside the facility's own cells is geometrically
    # impossible (two facilities can't co-locate). Without this exclusion the
    # validator finds a "pole" inside the facility footprint with distance 0 ≤ R
    # and rejects every legitimate F7 cut.
    facility_set = frozenset(facility_cells)
    cell_owner_keys = frozenset(state.cell_owner.keys())
    grid_cells = frozenset(
        (x, y) for x in range(_GRID_SIZE) for y in range(_GRID_SIZE)
    )
    free_cells = frozenset(
        c
        for c in grid_cells
        if c not in state.ghost_cells
        and c not in state.exterior_blocks
        and c not in cell_owner_keys
        and c not in facility_set
    )
    cover_full = compute_cover_set(facility_cells, free_cells, pole_radius)
    if cover_full:
        return _vr(
            "unsound",
            t0,
            f"Hall witness fails: cover_set recompute non-empty (|cover|={len(cover_full)})",
        )
    return None


def _validate_coverset_ghost_only_empty(
    facility_cells: Tuple[Tuple[int, int], ...],
    cert_dict: Dict[str, Any],
    state: BState,
    t0: float,
) -> Optional[ValidationResult]:
    pole_radius = float(cast(float, cert_dict["pole_radius"]))
    # Same R1 BLOCKER fix: exclude facility_cells from the ghost-only mask too.
    facility_set = frozenset(facility_cells)
    blocked = (
        frozenset(state.ghost_cells) | frozenset(state.exterior_blocks) | facility_set
    )
    free = frozenset(
        (x, y)
        for x in range(_GRID_SIZE)
        for y in range(_GRID_SIZE)
        if (x, y) not in blocked
    )
    cover_ghost = compute_cover_set(facility_cells, free, pole_radius)
    if cover_ghost:
        return _vr(
            "unsound",
            t0,
            f"cert_kind='power_cover_emptyset_ghost' but ghost-only CoverSet recompute is "
            f"non-empty (|cover_ghost|={len(cover_ghost)}). cell_owner is the true cause; "
            f"single-literal cut is unsound. Phase 1.5+ multi-literal handles this.",
        )
    return None


def validate_power_hitting_set(
    cut: Cut,
    state: BState,
    canonical_rules: Dict[str, Any],
) -> ValidationResult:
    """7-phase F7 validator (Phase 1.2 single-case scope).

    Phases (fail-closed, first error returns):
    1. cert + payload non-None + JSON parse
    2. cert_kind == "power_cover_emptyset_ghost"
    3. literals must be non-None (literal-based mode, expected single literal)
       + scalar schema (group / pose / radius / shape_canonical / facility_cells)
    4. Ghost scope binding (non-AGNOSTIC + ghost_rect_repr + exterior_blocks_digest)
    5. Group source-of-truth (group ∈ state.groups, pose ∈ pose_domain,
       facility_template lookup + needs_power == True)
    6. Full CoverSet recompute (must be ∅)
    7. Ghost-only CoverSet recompute (must be ∅ — cell_owner not the true cause)
    """
    t0 = time.monotonic()
    del canonical_rules

    if cut.cert is None or cut.geometric_payload is not None:
        return _vr(
            "schema_err",
            t0,
            "F7 is literal-based; cut.cert must be present and "
            "cut.geometric_payload must be None",
        )
    if cut.literals is None or len(cut.literals) == 0:
        return _vr(
            "schema_err",
            t0,
            "F7 requires non-empty cut.literals (single literal Phase 1.2)",
        )

    try:
        cert_dict = _parse_cert_payload(cut.cert.cert_payload)
    except ValueError as e:
        return _vr("schema_err", t0, str(e))

    err = _validate_cert_kind(cert_dict, t0)
    if err is not None:
        return err

    scalar_err, facility_cells = _validate_scalars(cert_dict, t0)
    if scalar_err is not None:
        return scalar_err
    if facility_cells is None:
        return _vr("schema_err", t0, "facility_cells parse returned None unexpectedly")

    # cut.literals must contain exactly one literal binding the facility pose.
    # Multi-literal Phase 1.5+ (cell_owner causation) not in Phase 1.2 scope.
    if len(cut.literals) != 1:
        return _vr(
            "schema_err",
            t0,
            f"F7 Phase 1.2 expects exactly 1 literal (single-literal mode), got {len(cut.literals)}",
        )
    lit = cut.literals[0]
    gid = cast(str, cert_dict["facility_group"])
    pose_id = cast(str, cert_dict["facility_pose_id"])
    if lit.slot_ref.group_id != gid or lit.pose_id != pose_id:
        return _vr(
            "unsound",
            t0,
            f"cut.literals[0] {(lit.slot_ref.group_id, lit.pose_id)!r} != cert "
            f"{(gid, pose_id)!r}",
        )

    for error in (
        _validate_ghost_scope_binding(cut, cert_dict, state, t0),
        _validate_group_and_template(cert_dict, state, t0),
        _validate_coverset_empty(facility_cells, cert_dict, state, t0),
        _validate_coverset_ghost_only_empty(facility_cells, cert_dict, state, t0),
    ):
        if error is not None:
            return error

    return _vr("ok", t0)


def watcher_keys_power_hitting_set(cut: Cut) -> Dict[str, List[Any]]:
    """Return watcher keys for CutStore.add_cut.

    F7 watches: facility_group (by_group) + (facility_group, facility_pose_id)
    (by_pose) + facility_cells (by_cell). by_ghost_watcher is auto-added by
    store from cut.scope.ghost_rect_id.
    """
    if cut.cert is None:
        return {"group_keys": [], "pose_keys": [], "cell_keys": []}
    try:
        cert_dict = _parse_cert_payload(cut.cert.cert_payload)
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
