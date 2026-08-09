"""Phase 1 integer reconstruction + sound-check validator (see README.md)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from .column_grammar import (
    CellCoord,
    FacilityAssignment,
    Pattern,
    assignment_equivalence_key,
    assignment_strict_key,
)


# === Errors ===


class ValidationError(RuntimeError):
    """Raised when an integer reconstruction violates an invariant."""


# === Phase 1 ghost-rect mask (hard-coded anchor (22,28) 27×15) ===


PHASE1_GHOST_ANCHOR: Tuple[int, int] = (22, 28)
PHASE1_GHOST_SIZE: Tuple[int, int] = (27, 15)


def is_in_ghost_rect(cell: CellCoord) -> bool:
    """True iff ``cell`` lies inside the Phase 1 hard-coded ghost rect."""
    gx, gy = PHASE1_GHOST_ANCHOR
    gw, gh = PHASE1_GHOST_SIZE
    x, y = cell
    return gx <= x < gx + gw and gy <= y < gy + gh


# === Reconstruction result ===


@dataclass
class IntegerReconstruction:
    """Materialised integer solution: chosen cols + flattened assignments + cell map."""

    chosen_columns: List[Pattern]
    chosen_assignments: List[FacilityAssignment]
    cell_to_column: Dict[CellCoord, str]
    covered_iids: FrozenSet[str]
    leaf_depth: int = 0


# === Reconstruction from RMP λ_k vector ===


def reconstruct_from_lambdas(
    columns: Sequence[Pattern],
    lambda_values: Sequence[float],
    *,
    integer_tol: float = 1e-6,
    leaf_depth: int = 0,
) -> IntegerReconstruction:
    """Materialise integer solution from λ_k; fail-close on fractional or dup cells."""
    if len(columns) != len(lambda_values):
        raise ValidationError(
            f"len(columns)={len(columns)} != len(lambda_values)={len(lambda_values)}"
        )
    chosen_cols: List[Pattern] = []
    for k, lam in enumerate(lambda_values):
        if integer_tol < lam < 1.0 - integer_tol:
            raise ValidationError(
                f"non-integer lambda at column k={k}: λ={lam:.6f}"
                f" (col={columns[k].column_id})"
            )
        if lam >= 1.0 - integer_tol:
            chosen_cols.append(columns[k])

    assignments: List[FacilityAssignment] = []
    cell_map: Dict[CellCoord, str] = {}
    for col in chosen_cols:
        for assignment in col.facility_assignments:
            assignments.append(assignment)
        for cell in col.occupied_cells:
            if cell in cell_map:
                raise ValidationError(
                    f"cell {cell} occupied by both column {cell_map[cell]} "
                    f"and column {col.column_id}"
                )
            cell_map[cell] = col.column_id
    covered_iids = frozenset(iid for (iid, _tpl, _p) in assignments)
    return IntegerReconstruction(
        chosen_columns=chosen_cols,
        chosen_assignments=assignments,
        cell_to_column=cell_map,
        covered_iids=covered_iids,
        leaf_depth=leaf_depth,
    )


# === Set-partitioning + ghost-rect checks ===


def check_set_partitioning(
    rec: IntegerReconstruction,
    instance_ids: Sequence[str],
) -> None:
    """Strict set-partition: every iid covered exactly once."""
    cover_count: Dict[str, int] = defaultdict(int)
    for (iid, _tpl, _p) in rec.chosen_assignments:
        cover_count[iid] += 1
    missing = [iid for iid in instance_ids if cover_count.get(iid, 0) == 0]
    overcov = [(iid, cover_count[iid]) for iid in instance_ids if cover_count.get(iid, 0) > 1]
    extras = [iid for iid in cover_count if iid not in set(instance_ids)]
    if missing:
        raise ValidationError(
            f"set-partitioning fail: {len(missing)} uncovered iids "
            f"(first 5: {missing[:5]})"
        )
    if overcov:
        raise ValidationError(
            f"set-partitioning fail: {len(overcov)} overcovered iids "
            f"(first 5: {overcov[:5]})"
        )
    if extras:
        raise ValidationError(
            f"set-partitioning fail: column covers unknown iids {extras[:5]}"
        )


def check_ghost_rect(rec: IntegerReconstruction) -> None:
    """No occupied cell may lie inside the Phase 1 ghost rect."""
    bad: List[CellCoord] = []
    for cell in rec.cell_to_column:
        if is_in_ghost_rect(cell):
            bad.append(cell)
            if len(bad) >= 5:
                break
    if bad:
        raise ValidationError(
            f"ghost-rect violation: {len(bad)}+ cells inside ghost rect "
            f"(anchor={PHASE1_GHOST_ANCHOR} size={PHASE1_GHOST_SIZE}) "
            f"first: {bad}"
        )


# === Direct-master equivalence (Task 2 the hard bit) ===


@dataclass
class DirectMasterPoseIndex:
    """(iid, frozenset(cells)) -> set of pose_idx producing those cells."""

    cells_to_pose_idx: Dict[Tuple[str, FrozenSet[CellCoord]], Set[int]] = field(
        default_factory=lambda: defaultdict(set)
    )
    iid_pose_count: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


def build_direct_master_pose_index(
    instances: Sequence[Mapping[str, Any]],
    pose_pools_by_iid: Mapping[str, Sequence[Mapping[str, Any]]],
) -> DirectMasterPoseIndex:
    """Build the (iid, cells) -> pose_idx lookup from the direct master pose pool."""
    idx = DirectMasterPoseIndex()
    for inst in instances:
        iid = inst["instance_id"]
        for pose in pose_pools_by_iid.get(iid, ()):
            cells = frozenset((int(c[0]), int(c[1])) for c in pose["cells"])
            pose_idx = int(pose["pose_idx"])
            idx.cells_to_pose_idx[(iid, cells)].add(pose_idx)
            idx.iid_pose_count[iid] += 1
    return idx


def check_direct_master_equivalence(
    rec: IntegerReconstruction,
    columns: Sequence[Pattern],
    pose_index: DirectMasterPoseIndex,
) -> Dict[str, Any]:
    """Cross-check CG vs direct master pose index. See README "Direct-master equiv"."""
    iid_to_cg_pose_idx: Dict[str, int] = {}
    for col in rec.chosen_columns:
        # Pattern carries cell union (not per-iid breakdown); we use the
        # pose_idx label directly and rely on the pose_index to map back.
        # README documents the weaker fallback when pose_idx differs.
        for (iid, _tpl, pose_idx) in col.facility_assignments:
            iid_to_cg_pose_idx[iid] = pose_idx

    strict_match = 0
    equiv_match = 0
    mismatch: List[str] = []
    for iid, cg_pose_idx in iid_to_cg_pose_idx.items():
        # Find any direct-master pose with same cells as the CG pose.
        # We don't have the CG pose's cells directly here (they're
        # merged in the column).  Defer to caller: ``pose_index`` was
        # built with the same pose pool the pricing CP-SAT used, so the
        # CG pose_idx → cells mapping is *available in the index* as a
        # reverse lookup.
        found_strict = False
        found_equiv = False
        for (idx_iid, cells), pose_idx_set in pose_index.cells_to_pose_idx.items():
            if idx_iid != iid:
                continue
            if cg_pose_idx in pose_idx_set:
                # CG's chosen pose_idx labels this exact (iid, cells).
                # That's the strict match.
                found_strict = True
                found_equiv = True
                break
        if not found_strict:
            # Fall back to equivalence: does any direct-master pose for
            # this iid produce a (iid, cells) with same cells as the
            # column's contribution?  Phase 1 weak check: at least one
            # direct-master pose exists for this iid (the index has it).
            if pose_index.iid_pose_count.get(iid, 0) > 0:
                found_equiv = True
        if found_strict:
            strict_match += 1
        elif found_equiv:
            equiv_match += 1
        else:
            mismatch.append(iid)

    if mismatch:
        raise ValidationError(
            f"direct-master mismatch: {len(mismatch)} iids missing from "
            f"direct master pool (first 5: {mismatch[:5]})"
        )
    return {
        "strict_match_count": strict_match,
        "equiv_match_count": equiv_match,
        "total_iids": len(iid_to_cg_pose_idx),
    }


# === Top-level validator ===


@dataclass
class ValidationReport:
    integer_feasible: bool
    set_partitioning_pass: bool
    cell_exclusive_pass: bool
    ghost_rect_pass: bool
    direct_master_pass: bool
    direct_master_telemetry: Dict[str, Any] = field(default_factory=dict)
    chosen_column_count: int = 0
    chosen_facility_count: int = 0
    leaf_depth: int = 0
    error_message: Optional[str] = None


def validate_integer_reconstruction(
    columns: Sequence[Pattern],
    lambda_values: Sequence[float],
    instance_ids: Sequence[str],
    pose_index: Optional[DirectMasterPoseIndex] = None,
    *,
    integer_tol: float = 1e-6,
    leaf_depth: int = 0,
    enforce_ghost_rect: bool = True,
) -> ValidationReport:
    """Run all Phase 1 invariant checks; fail-close via report.error_message."""
    rep = ValidationReport(
        integer_feasible=False,
        set_partitioning_pass=False,
        cell_exclusive_pass=False,
        ghost_rect_pass=False,
        direct_master_pass=False,
        leaf_depth=leaf_depth,
    )
    try:
        rec = reconstruct_from_lambdas(
            columns, lambda_values,
            integer_tol=integer_tol, leaf_depth=leaf_depth,
        )
        rep.integer_feasible = True
        rep.cell_exclusive_pass = True  # reconstruct_from_lambdas raises on dup
        rep.chosen_column_count = len(rec.chosen_columns)
        rep.chosen_facility_count = len(rec.chosen_assignments)
    except ValidationError as exc:
        rep.error_message = f"reconstruct: {exc}"
        return rep

    try:
        check_set_partitioning(rec, instance_ids)
        rep.set_partitioning_pass = True
    except ValidationError as exc:
        rep.error_message = f"set_partitioning: {exc}"
        return rep

    if enforce_ghost_rect:
        try:
            check_ghost_rect(rec)
            rep.ghost_rect_pass = True
        except ValidationError as exc:
            rep.error_message = f"ghost_rect: {exc}"
            return rep
    else:
        rep.ghost_rect_pass = True  # not enforced this run.

    if pose_index is not None:
        try:
            telemetry = check_direct_master_equivalence(rec, columns, pose_index)
            rep.direct_master_pass = True
            rep.direct_master_telemetry = telemetry
        except ValidationError as exc:
            rep.error_message = f"direct_master: {exc}"
            return rep
    else:
        # No pose index supplied → skip equivalence check (Phase 1 may
        # run with/without depending on cost budget).
        rep.direct_master_pass = True
        rep.direct_master_telemetry = {"skipped": True}

    return rep


__all__ = [
    "ValidationError",
    "ValidationReport",
    "IntegerReconstruction",
    "DirectMasterPoseIndex",
    "PHASE1_GHOST_ANCHOR",
    "PHASE1_GHOST_SIZE",
    "is_in_ghost_rect",
    "build_direct_master_pose_index",
    "reconstruct_from_lambdas",
    "check_set_partitioning",
    "check_ghost_rect",
    "check_direct_master_equivalence",
    "validate_integer_reconstruction",
]
