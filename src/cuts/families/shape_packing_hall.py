"""Family 6 shape_packing_hall — Hall infeasibility validator + evaluator (P1.2B-F6).

PROJECT_LOCK §3A locked invariants:
- **Single-shape Phase 1.2**: only ``boundary_storage_port`` 1×3 rigid pose along
  baseline. Multi-shape Hall (PARTITION-reducible NP-hard) deferred Phase 1.5+.
- **Ghost-bound**: ``cut.scope.ghost_rect_id == GHOST_AGNOSTIC`` rejected; the
  partition recompute depends on ghost cells, so F6 cert cannot survive a
  ghost change.
- **Cell-owner independence (v1.1)**: partition_lens is recomputed from
  ``ghost_cells ∪ exterior_blocks`` only, NEVER ``cell_owner.keys()``.
  Per spec §5a Gemini round 14 critical fix — including ``cell_owner`` made
  partition state-dependent and cross-layer cuts permanently quarantined.
- **Strict inequality**: ``total_packable < region_demand``; equality does not
  cut.
- **Pose_length >= 2**: F6 with ``pose_length == 1`` degenerates into
  F1 region_capacity (each cell holds one pose); reject as schema_err to
  keep F6 non-trivial.

Cert payload schema (canonical JSON, sorted keys, no Optionals):
    cert_kind: "hall_interval_witness"
    region_kind: "left_baseline" | "bottom_baseline"  (closed-set)
    region_total_length: int  (== 70, audit-anchor)
    partition_lens: list[int]  (each >= 1, validator recomputes)
    partition_offsets: list[int]  (validator recomputes, strict equal — NOT
        debug-only per spec §10 q3 patch; mutating offsets without recompute
        is a real attack vector)
    pose_length: int  (>= 2)
    pose_shape_canonical: str  (regex ``^\\d+x\\d+_rigid$``)
    max_packable: list[int]  (len == len(partition_lens),
        max_packable[i] == partition_lens[i] // pose_length)
    total_packable: int  (== sum(max_packable))
    contributing_group: non-empty str  (∈ state.groups)
    region_demand: int  (>= 1, <= group_demand,
        <= ⌊region_total_length / pose_length⌋ — per-region demand
        Phase 1.5+ comes from master.solution placement count;
        Phase 1.2 generator uses region capacity upper bound)
    group_demand: int  (>= 1, source-of-truth audit anchor — must equal
        state.groups[contributing_group].demand at validate time)
    ghost_rect_repr: list[int]  (4 strict int, byte-equal state.ghost_rect)
    exterior_blocks_digest: str  (sha256 hex of sorted exterior_blocks
        canonical bytes; mirrors compute_exterior_blocks_hash)

Evaluator dispatches via ``lifecycle.step_7_evaluate_cut``.

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F6
- docs/项目说明/12_go_criteria.md §8.1.x acceptance D
- docs/research/p3_b_design_v2_20260521/cut_family_specs/06_shape_packing_hall.md v1.1
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Literal, Optional, Tuple, cast

from src.cuts.helpers.baseline_partition import (
    RegionKind,
    compute_baseline_partition_lens,
)
from src.cuts.lifecycle import (
    GHOST_AGNOSTIC,
    BState,
    Cut,
    ValidationResult,
    compute_exterior_blocks_hash,
)


ValidationKind = Literal["ok", "unsound", "timeout", "schema_err"]


_VALID_REGION_KINDS: frozenset[str] = frozenset({"left_baseline", "bottom_baseline"})
_POSE_SHAPE_CANONICAL_PATTERN: re.Pattern[str] = re.compile(r"^\d+x\d+_rigid$")
_GRID_SIZE: int = 70


def _vr(kind: ValidationKind, t0: float, detail: str = "") -> ValidationResult:
    return ValidationResult(kind=kind, elapsed_seconds=time.monotonic() - t0, detail=detail or None)


def _is_strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


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


def _parse_int_list(value: object, field_name: str) -> List[int]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be list, got {type(value).__name__}")
    out: List[int] = []
    for idx, item in enumerate(value):
        if not _is_strict_int(item):
            raise ValueError(f"{field_name}[{idx}] must be strict int, got {item!r}")
        out.append(cast(int, item))
    return out


def _validate_cert_kind(cert_dict: Dict[str, Any], t0: float) -> Optional[ValidationResult]:
    kind = cert_dict.get("cert_kind")
    if kind != "hall_interval_witness":
        return _vr("schema_err", t0, f"cert_kind must be 'hall_interval_witness', got {kind!r}")
    return None


def _validate_closed_enums(cert_dict: Dict[str, Any], t0: float) -> Optional[ValidationResult]:
    region_kind = cert_dict.get("region_kind")
    if region_kind not in _VALID_REGION_KINDS:
        return _vr(
            "schema_err",
            t0,
            f"region_kind must be in {sorted(_VALID_REGION_KINDS)}, got {region_kind!r}",
        )
    pose_shape = cert_dict.get("pose_shape_canonical")
    if not _is_non_empty_str(pose_shape) or not _POSE_SHAPE_CANONICAL_PATTERN.match(
        cast(str, pose_shape)
    ):
        return _vr(
            "schema_err",
            t0,
            f"pose_shape_canonical must match r'^\\d+x\\d+_rigid$', got {pose_shape!r}",
        )
    return None


def _validate_scalars(cert_dict: Dict[str, Any], t0: float) -> Optional[ValidationResult]:
    for field, lo in (
        ("region_total_length", _GRID_SIZE),
        ("pose_length", 2),
        ("total_packable", 0),
        ("region_demand", 1),
        ("group_demand", 1),
    ):
        v = cert_dict.get(field)
        if not _is_strict_int(v):
            return _vr("schema_err", t0, f"{field} must be strict int, got {v!r}")
        if field == "region_total_length":
            if cast(int, v) != _GRID_SIZE:
                return _vr(
                    "schema_err",
                    t0,
                    f"region_total_length must equal {_GRID_SIZE} (grid bound), got {v}",
                )
        elif cast(int, v) < lo:
            return _vr("schema_err", t0, f"{field} must be >= {lo}, got {v}")
    # pose_shape_canonical "1x3_rigid" — first dim must == pose_length OR
    # the smaller dim must equal 1 (1×L rigid along baseline).
    pose_length = cast(int, cert_dict["pose_length"])
    pose_shape = cast(str, cert_dict["pose_shape_canonical"])
    m = _POSE_SHAPE_CANONICAL_PATTERN.match(pose_shape)
    if m is None:  # belt-and-suspenders (already checked in _validate_closed_enums)
        return _vr("schema_err", t0, f"pose_shape_canonical regex parse failed for {pose_shape!r}")
    parts = pose_shape[: -len("_rigid")].split("x")
    if len(parts) != 2:
        return _vr("schema_err", t0, f"pose_shape_canonical parse failed for {pose_shape!r}")
    try:
        a, b = int(parts[0]), int(parts[1])
    except ValueError:
        return _vr("schema_err", t0, f"pose_shape_canonical dim parse failed for {pose_shape!r}")
    if min(a, b) != 1:
        return _vr(
            "schema_err",
            t0,
            f"pose_shape_canonical must be 1×L rigid (Phase 1.2 single-shape), got {pose_shape!r}",
        )
    if max(a, b) != pose_length:
        return _vr(
            "schema_err",
            t0,
            f"pose_length {pose_length} != pose_shape_canonical max dim {max(a, b)}",
        )
    return None


def _validate_partition_internal_consistency(
    cert_dict: Dict[str, Any], t0: float
) -> Tuple[Optional[ValidationResult], Optional[Tuple[List[int], List[int], List[int]]]]:
    try:
        lens = _parse_int_list(cert_dict.get("partition_lens"), "partition_lens")
        offsets = _parse_int_list(cert_dict.get("partition_offsets"), "partition_offsets")
        max_packable = _parse_int_list(cert_dict.get("max_packable"), "max_packable")
    except ValueError as e:
        return _vr("schema_err", t0, str(e)), None
    if not (len(lens) == len(offsets) == len(max_packable)):
        return (
            _vr(
                "schema_err",
                t0,
                f"partition_lens / partition_offsets / max_packable len mismatch: "
                f"{len(lens)} / {len(offsets)} / {len(max_packable)}",
            ),
            None,
        )
    pose_length = cast(int, cert_dict["pose_length"])
    total_packable = cast(int, cert_dict["total_packable"])
    # Each segment: len >= 1, offset >= 0, offset + len <= 70 (within grid),
    # offsets strictly increasing, non-overlap (off_i + len_i <= off_{i+1}),
    # max_packable[i] == lens[i] // pose_length (strict).
    prev_end = -1
    for i, (L, off, mp) in enumerate(zip(lens, offsets, max_packable)):
        if L < 1:
            return _vr("schema_err", t0, f"partition_lens[{i}] must be >= 1, got {L}"), None
        if off < 0:
            return _vr("schema_err", t0, f"partition_offsets[{i}] must be >= 0, got {off}"), None
        if off + L > _GRID_SIZE:
            return (
                _vr(
                    "schema_err",
                    t0,
                    f"segment {i} extends past grid: offset={off} + len={L} > {_GRID_SIZE}",
                ),
                None,
            )
        if off <= prev_end:
            return (
                _vr(
                    "schema_err",
                    t0,
                    f"partition_offsets[{i}]={off} overlaps prev_end={prev_end}",
                ),
                None,
            )
        if mp != L // pose_length:
            return (
                _vr(
                    "schema_err",
                    t0,
                    f"max_packable[{i}]={mp} != partition_lens[{i}]={L} // pose_length={pose_length}",
                ),
                None,
            )
        prev_end = off + L - 1
    if sum(max_packable) != total_packable:
        return (
            _vr(
                "schema_err",
                t0,
                f"total_packable {total_packable} != sum(max_packable) {sum(max_packable)}",
            ),
            None,
        )
    return None, (lens, offsets, max_packable)


def _validate_hall_witness_strict(cert_dict: Dict[str, Any], t0: float) -> Optional[ValidationResult]:
    total_packable = cast(int, cert_dict["total_packable"])
    region_demand = cast(int, cert_dict["region_demand"])
    if total_packable >= region_demand:
        return _vr(
            "unsound",
            t0,
            f"Hall witness fails: total_packable {total_packable} >= region_demand {region_demand} "
            f"(strict < required)",
        )
    return None


def _validate_group_source_of_truth(
    cert_dict: Dict[str, Any], state: BState, t0: float
) -> Optional[ValidationResult]:
    gid = cert_dict.get("contributing_group")
    if not _is_non_empty_str(gid):
        return _vr(
            "schema_err",
            t0,
            f"contributing_group must be non-empty str, got {gid!r}",
        )
    if cast(str, gid) not in state.groups:
        return _vr(
            "unsound",
            t0,
            f"contributing_group {gid!r} not in state.groups (registry rotated or fake gid)",
        )
    group_demand = cast(int, cert_dict["group_demand"])
    actual_demand = state.groups[cast(str, gid)].demand
    if actual_demand != group_demand:
        return _vr(
            "unsound",
            t0,
            f"group_demand mismatch: cert={group_demand}, state.groups[{gid!r}].demand={actual_demand} "
            f"(source-of-truth rotated)",
        )
    region_demand = cast(int, cert_dict["region_demand"])
    if region_demand > group_demand:
        return _vr(
            "schema_err",
            t0,
            f"region_demand {region_demand} > group_demand {group_demand} (per-region must be <= total)",
        )
    pose_length = cast(int, cert_dict["pose_length"])
    region_cap = _GRID_SIZE // pose_length
    if region_demand > region_cap:
        return _vr(
            "schema_err",
            t0,
            f"region_demand {region_demand} > region capacity {region_cap} (= 70 / pose_length); "
            f"per-region demand cannot exceed region physical upper bound",
        )
    return None


def _validate_facility_template_match(
    cert_dict: Dict[str, Any], state: BState, t0: float
) -> Optional[ValidationResult]:
    """Cross-check pose_length × pose_shape against canonical_rules facility template.

    Adversary plants pose_length=35 but canonical_rules dimensions show 1×3 →
    caught here. **Fail-closed** (Gemini F6 round 1 BLOCKER #1): if the
    facility_templates source-of-truth is missing, return ``unsound`` rather
    than silently passing. The previous fail-open shortcut (defer when
    fixtures lacked wiring) let an attacker bypass the dimensions check by
    omitting templates from state — tests must supply real templates.
    """
    gid = cast(str, cert_dict["contributing_group"])
    pose_length = cast(int, cert_dict["pose_length"])
    if state.instance_to_facility_type is None:
        return _vr(
            "unsound",
            t0,
            "state.instance_to_facility_type missing — F6 cannot verify "
            "pose_length without source-of-truth (fail-closed)",
        )
    facility_type = state.instance_to_facility_type.get(gid)
    if facility_type is None:
        return _vr(
            "unsound",
            t0,
            f"contributing_group {gid!r} has no facility_type in "
            f"instance_to_facility_type (registry rotated or fake gid)",
        )
    if state.facility_templates is None:
        return _vr(
            "unsound",
            t0,
            "state.facility_templates missing — F6 cannot verify pose_length "
            "without source-of-truth (fail-closed)",
        )
    tpl = state.facility_templates.get(facility_type)
    if not isinstance(tpl, dict):
        return _vr(
            "unsound",
            t0,
            f"facility_templates[{facility_type!r}] missing or not a dict",
        )
    dims = tpl.get("dimensions")
    if not isinstance(dims, dict):
        return _vr(
            "unsound",
            t0,
            f"facility_templates[{facility_type!r}].dimensions missing or not a dict",
        )
    w_raw = dims.get("w")
    h_raw = dims.get("h")
    if not _is_strict_int(w_raw) or not _is_strict_int(h_raw):
        return _vr(
            "unsound",
            t0,
            f"facility_templates[{facility_type!r}].dimensions w/h must be strict int",
        )
    w_dim = cast(int, w_raw)
    h_dim = cast(int, h_raw)
    if min(w_dim, h_dim) != 1:
        return _vr(
            "unsound",
            t0,
            f"contributing_group {gid!r} facility_type {facility_type!r} dimensions "
            f"({w_dim}x{h_dim}) is not 1×L rigid; F6 Phase 1.2 only supports single-shape",
        )
    if max(w_dim, h_dim) != pose_length:
        return _vr(
            "unsound",
            t0,
            f"pose_length {pose_length} does not match canonical_rules "
            f"facility_templates[{facility_type!r}].dimensions max dim {max(w_dim, h_dim)}",
        )
    return None


def _validate_ghost_scope_binding(
    cut: Cut, cert_dict: Dict[str, Any], state: BState, t0: float
) -> Optional[ValidationResult]:
    if cut.scope is None:
        return _vr("schema_err", t0, "cut.scope must be non-None for F6")
    if cut.scope.ghost_rect_id == GHOST_AGNOSTIC:
        return _vr(
            "unsound",
            t0,
            "F6 shape_packing_hall does not allow GHOST_AGNOSTIC scope "
            "(partition_lens depends on ghost_cells)",
        )
    if state.ghost_rect is None:
        return _vr(
            "unsound",
            t0,
            "F6 requires state.ghost_rect non-None to validate ghost binding",
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
    cert_exterior = cert_dict.get("exterior_blocks_digest")
    if not _is_non_empty_str(cert_exterior):
        return _vr(
            "schema_err",
            t0,
            f"exterior_blocks_digest must be non-empty str, got {cert_exterior!r}",
        )
    actual_digest = compute_exterior_blocks_hash(state)
    if cast(str, cert_exterior) != actual_digest:
        return _vr(
            "unsound",
            t0,
            f"exterior_blocks_digest drift: cert={cert_exterior!r}, state={actual_digest!r}",
        )
    return None


def _validate_partition_recompute(
    cert_dict: Dict[str, Any],
    parsed: Tuple[List[int], List[int], List[int]],
    state: BState,
    t0: float,
) -> Optional[ValidationResult]:
    cert_lens, cert_offsets, _cert_max = parsed
    region_kind = cast(RegionKind, cert_dict["region_kind"])
    recomputed_lens, recomputed_offsets = compute_baseline_partition_lens(region_kind, state)
    if recomputed_lens != cert_lens:
        return _vr(
            "unsound",
            t0,
            f"partition_lens drift: cert={cert_lens}, recomputed={recomputed_lens} "
            f"(ghost ∪ exterior changed since gen)",
        )
    if recomputed_offsets != cert_offsets:
        return _vr(
            "unsound",
            t0,
            f"partition_offsets drift: cert={cert_offsets}, recomputed={recomputed_offsets}",
        )
    pose_length = cast(int, cert_dict["pose_length"])
    region_demand = cast(int, cert_dict["region_demand"])
    recomputed_max = [L // pose_length for L in recomputed_lens]
    recomputed_total = sum(recomputed_max)
    if recomputed_total != cast(int, cert_dict["total_packable"]):
        return _vr(
            "unsound",
            t0,
            f"total_packable drift on recompute: cert={cert_dict['total_packable']}, "
            f"recomputed={recomputed_total}",
        )
    if recomputed_total >= region_demand:
        return _vr(
            "unsound",
            t0,
            f"Hall witness fails on recompute: total_packable={recomputed_total} >= "
            f"region_demand={region_demand}",
        )
    return None


def validate_shape_packing_hall(
    cut: Cut,
    state: BState,
    canonical_rules: Dict[str, Any],
) -> ValidationResult:
    """11-phase F6 validator. Trust boundary: cert is untrusted; recompute partition.

    Phases (fail-closed, first error returns):
    1. cert + payload non-None + JSON parse
    2. cert_kind == "hall_interval_witness"
    3. literals is None (geometric mode) + closed-set enums
    4. Strict-int scalars + range
    5. Partition internal consistency (lens/offsets/max_packable triple)
    6. Hall witness strict (cert-internal total_packable < region_demand)
    7. Group source-of-truth (contributing_group ∈ state.groups,
       group_demand == state.groups[gid].demand, region_demand bounds)
    8. Facility template match (pose_length × dimensions via
       instance_to_facility_type → facility_templates)
    9. Ghost scope binding (non-AGNOSTIC + ghost_rect_repr byte-equal +
       exterior_blocks_digest byte-equal)
    10. Partition recompute byte-equal (lens + offsets)
    11. Recomputed max_packable / total_packable / Hall strict
    """
    t0 = time.monotonic()
    del canonical_rules  # state.canonical_rules carried inside state

    if cut.cert is None or cut.geometric_payload is None:
        return _vr("schema_err", t0, "F6 requires non-None cert + geometric_payload")
    if cut.literals is not None:
        return _vr(
            "schema_err",
            t0,
            "F6 is geometric mode; cut.literals must be None (got non-None)",
        )

    try:
        cert_dict = _parse_cert_payload(cut.cert.cert_payload)
    except ValueError as e:
        return _vr("schema_err", t0, str(e))

    for error in (
        _validate_cert_kind(cert_dict, t0),
        _validate_closed_enums(cert_dict, t0),
        _validate_scalars(cert_dict, t0),
    ):
        if error is not None:
            return error

    consistency_err, parsed = _validate_partition_internal_consistency(cert_dict, t0)
    if consistency_err is not None:
        return consistency_err
    if parsed is None:
        return _vr("schema_err", t0, "partition parse returned None unexpectedly")

    for error in (
        _validate_hall_witness_strict(cert_dict, t0),
        _validate_group_source_of_truth(cert_dict, state, t0),
        _validate_facility_template_match(cert_dict, state, t0),
        _validate_ghost_scope_binding(cut, cert_dict, state, t0),
        _validate_partition_recompute(cert_dict, parsed, state, t0),
    ):
        if error is not None:
            return error

    return _vr("ok", t0)


def evaluate_geometric_shape_packing_hall(cut: Cut, state: BState) -> bool:
    """Hot-path evaluator. True iff Hall witness still holds in current state.

    Strict ``<``: equality does NOT cut (PROJECT_LOCK invariant).

    Performance optimization (Gemini F6 round 1 HIGH #2): under v1.1 the
    partition only depends on ``ghost_cells ∪ exterior_blocks``, and both
    are bound into the cut scope (``ghost_rect_id`` + ``exterior_blocks_hash``).
    An ``active`` cut has already cleared ``step_6_attach_scope_check`` —
    so the recomputed partition is guaranteed byte-equal to ``cert``.
    Re-scanning the baseline in the hot path is wasted O(N) work.

    The evaluator therefore trusts ``cert.total_packable`` /
    ``cert.region_demand`` directly. Schema sanity is preserved so a
    malformed payload still returns False.

    Fail-safe: malformed payload returns False (no cut).
    """
    del state
    if cut.geometric_payload is None:
        return False
    try:
        cert_dict = json.loads(cut.geometric_payload)
        if not isinstance(cert_dict, dict):
            return False
        if cert_dict.get("cert_kind") != "hall_interval_witness":
            return False
        total_packable = cert_dict.get("total_packable")
        region_demand = cert_dict.get("region_demand")
        if not _is_strict_int(total_packable) or not _is_strict_int(region_demand):
            return False
        if cast(int, region_demand) < 1:
            return False
        return cast(int, total_packable) < cast(int, region_demand)
    except Exception:  # noqa: BLE001 — fail-safe
        return False


def watcher_keys_shape_packing_hall(cut: Cut) -> Dict[str, List[Any]]:
    """Return watcher keys for CutStore.add_cut.

    F6 walls on by_group (contributing_group) + by_region (region kind).
    by_ghost_watcher is auto-added by store from cut.scope.ghost_rect_id.

    No cell_keys: F6 partition is independent of cell_owner (v1.1 invariant).
    Listing 70 baseline cells in by_cell_watcher would cause every boundary
    pose placement to trigger 70 cut re-evaluations, with 99% returning
    unchanged (cell_owner change does not affect partition). Per Gemini
    round 14 finding #2 + throughput design rationale.
    """
    if cut.geometric_payload is None:
        return {"group_keys": [], "region_keys": []}
    try:
        cert_dict = _parse_cert_payload(cut.geometric_payload)
        gid = cert_dict.get("contributing_group")
        region_kind = cert_dict.get("region_kind")
        if not _is_non_empty_str(gid) or region_kind not in _VALID_REGION_KINDS:
            return {"group_keys": [], "region_keys": []}
        # region_id format per spec 06_shape_packing_hall.md §8 + Gemini F6
        # round 1 MEDIUM #3: region-first prefix lets a future region-wide
        # invalidator (e.g. on_baseline_change) wake all shape_hall cuts
        # without scanning by family. Format: f"{region_kind}:shape_hall"
        region_id = f"{region_kind}:shape_hall"
        return {
            "group_keys": [cast(str, gid)],
            "region_keys": [region_id],
        }
    except Exception:  # noqa: BLE001 — fail-safe
        return {"group_keys": [], "region_keys": []}
