"""F5 binding-empty-domain independent verifier (RFC-002 §4).

TCB.  Given an F5 ``bounded_deletion_core`` cert's ``forbidden_pose_pattern`` and
the frozen liftable bundle, this module RE-DERIVES — with an algorithm that
shares no code path with the production binding enumerator — whether some
pattern literal names a ``(operation_type, pose)`` whose pose-level
port-binding domain is empty.  A single empty-domain literal makes the whole
forbidden conjunction infeasible, so forbidding the pattern is sound.

Why a second, independent implementation (RFC-002 §1 common-mode fix)
--------------------------------------------------------------------
The F5 generator obtains INFEASIBLE from ``SubProblemOracleAdapter.query_liftable``
and the typed re-verifier asks the SAME adapter again.  If that adapter's math,
input mapping, or dependency capture is systematically wrong, generator and
re-verifier accept the same wrong conclusion.  This verifier removes that
common mode:

* it never imports the oracle / adapter / registry modules — pinned by
  ``test_f5_independent_verifier.py::test_verifier_module_imports_no_oracle_surface``;
* the emptiness decision is an explicit bipartite COMPLETE-MATCHING feasibility
  test (Hall / system-of-distinct-representatives), not a call to
  ``enumerate_pose_level_port_bindings`` — a double-implementation differential
  cross-checks the two on a constructed domain;
* ``operation_type`` is re-derived from the snapshot-resident ``group_id`` plus
  the authoritative frozen instance→facility binding, never read back from a
  mutable adapter instance (the stale ``group_id → operation_type`` mapping is
  exactly the RFC-002 §1 defect).

Emptiness model.  The production enumerator assigns commodity slots to distinct
port cells with NO commodity/cell compatibility constraint, so the per-side
binding graph is complete bipartite; a complete assignment saturating every
required slot exists iff ``required_slots <= available_port_cells``.  The domain
is therefore empty iff either side is short of port cells.  The matching is
retained (rather than collapsed to a scalar comparison) so the check stays
structurally independent of the enumerator.  B-D dual-review (math LOW #1):
under future compatibility edges the complete-graph matching would OVERESTIMATE
feasibility — that direction is sound (verifier says non-empty -> refute, never
a false empty-domain endorsement) but NOT complete; the wording here is
deliberately "remains sound (conservative)", not "remains correct".

Fail-closed and deterministic.  Any parse / lookup / domain-construction
failure yields NO confirmation for that literal; a pattern with no
independently-confirmed empty-domain literal is REFUTED, never silently
accepted.  No environment variable is read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from src.preprocess.operation_profiles import (
    OperationPortProfile,
    get_operation_port_profile,
)

# The synthetic group identity minted by MasterModel._build_mandatory_groups is
# ``group::{facility_type}::{operation_type}::{group_index}``.  The verifier only
# ever parses group_ids the snapshot already vouches for, and always cross-checks
# the recovered operation_type's facility against the frozen instance binding.
_GROUP_ID_PREFIX = "group::"

PortCell = Mapping[str, object]
Pose = Mapping[str, object]
Literal = tuple[str, int, str]


class BindingDomainUndecidable(Exception):
    """A literal's binding domain could not be independently decided.

    Raised (and, at the pattern level, swallowed into "no confirmation") when
    the operation is not an exact pose-level binding operation, the group_id /
    profile / pose facts are inconsistent, or a pose is malformed.  It never
    means "empty": the verifier only ever CONFIRMS emptiness from a cleanly
    reconstructed domain.
    """


@dataclass(frozen=True)
class BindingEmptyDomainVerdict:
    """Outcome of an independent F5 binding-empty-domain re-derivation."""

    verified: bool
    reason: str
    witness_literal: Literal | None = None


def verify_binding_empty_domain(
    forbidden_pose_pattern: object,
    *,
    instance_to_facility_type: Mapping[str, object],
    facility_pools: Mapping[str, object],
) -> BindingEmptyDomainVerdict:
    """Independently re-derive the F5 empty-binding-domain refutation.

    Returns ``verified=True`` iff at least one literal of the pattern names a
    pose whose pose-level port-binding domain this verifier reconstructs as
    empty.  Any literal that cannot be cleanly decided contributes no
    confirmation; a pattern with no confirmed empty-domain literal is REFUTED.
    """

    try:
        pattern = _normalize_pattern(forbidden_pose_pattern)
    except BindingDomainUndecidable as exc:
        return BindingEmptyDomainVerdict(
            verified=False,
            reason=f"F5 forbidden_pose_pattern is not a well-formed literal tuple: {exc}",
        )

    for literal in pattern:
        try:
            confirmed = _literal_domain_is_confirmed_empty(
                literal,
                instance_to_facility_type=instance_to_facility_type,
                facility_pools=facility_pools,
            )
        except BindingDomainUndecidable:
            # This literal cannot be independently decided — it contributes no
            # confirmation.  It never flips the verdict to accepted.
            continue
        if confirmed:
            return BindingEmptyDomainVerdict(
                verified=True,
                reason="independent complete-matching enumeration is empty",
                witness_literal=literal,
            )
    return BindingEmptyDomainVerdict(
        verified=False,
        reason="no pattern literal has an independently-empty binding domain",
    )


def binding_domain_is_empty(operation_type: str, pose: Pose) -> bool:
    """Independently decide whether ``(operation_type, pose)`` has an empty
    pose-level port-binding domain.

    Raises :class:`BindingDomainUndecidable` for operations that do not support
    exact pose-level binding (generic hub slots), which are anti-monotone and
    never liftable.  This is the double-implementation differential target
    cross-checked against ``enumerate_pose_level_port_bindings``.
    """

    profile = _require_exact_binding_profile(operation_type)
    need_in = _required_slot_count(profile.input_slots)
    need_out = _required_slot_count(profile.output_slots)
    have_in = _count_port_cells(pose, "input_port_cells")
    have_out = _count_port_cells(pose, "output_port_cells")
    input_saturated = _complete_assignment_exists(need_in, have_in)
    output_saturated = _complete_assignment_exists(need_out, have_out)
    return not (input_saturated and output_saturated)


# ----------------------------------------------------------------------------
# Literal-level re-derivation
# ----------------------------------------------------------------------------


def _literal_domain_is_confirmed_empty(
    literal: Literal,
    *,
    instance_to_facility_type: Mapping[str, object],
    facility_pools: Mapping[str, object],
) -> bool:
    group_id, _slot_index, pose_id = literal
    facility_type = instance_to_facility_type.get(group_id)
    if not isinstance(facility_type, str) or not facility_type:
        raise BindingDomainUndecidable(f"group {group_id!r} has no frozen instance→facility binding")
    operation_type = _operation_type_from_group_id(group_id, facility_type)
    profile = _require_exact_binding_profile(operation_type)
    if profile.facility_type != facility_type:
        raise BindingDomainUndecidable("group_id operation_type is inconsistent with the frozen facility binding")
    pose = _find_pose(facility_pools, facility_type, pose_id)
    if pose is None:
        raise BindingDomainUndecidable(f"pose {pose_id!r} not found in facility pool {facility_type!r}")
    return binding_domain_is_empty(operation_type, pose)


def _operation_type_from_group_id(group_id: str, facility_type: str) -> str:
    """Recover operation_type from a snapshot-vouched synthetic group_id.

    Uses the authoritative frozen ``facility_type`` (not string position) to
    strip the ``group::{facility_type}::`` prefix, so a ``::`` inside the
    facility name cannot mis-split the operation_type.
    """

    prefix = f"{_GROUP_ID_PREFIX}{facility_type}::"
    if not group_id.startswith(prefix):
        raise BindingDomainUndecidable("group_id does not encode the frozen facility prefix")
    remainder = group_id[len(prefix) :]
    if "::" not in remainder:
        raise BindingDomainUndecidable("group_id lacks the operation/index suffix")
    operation_type, _group_index = remainder.rsplit("::", 1)
    if not operation_type:
        raise BindingDomainUndecidable("group_id encodes an empty operation_type")
    return operation_type


def _find_pose(facility_pools: Mapping[str, object], facility_type: str, pose_id: str) -> Pose | None:
    pool = facility_pools.get(facility_type)
    # Frozen bundles thaw lists to tuples; accept either sequence shape.
    if not isinstance(pool, (list, tuple)):
        return None
    for pose in pool:
        if isinstance(pose, Mapping) and str(pose.get("pose_id", "")) == pose_id:
            return pose
    return None


# ----------------------------------------------------------------------------
# Independent emptiness primitives
# ----------------------------------------------------------------------------


def _require_exact_binding_profile(operation_type: str) -> OperationPortProfile:
    try:
        profile = get_operation_port_profile(operation_type)
    except Exception as exc:  # noqa: BLE001 — unknown op is undecidable, not empty
        raise BindingDomainUndecidable(f"operation {operation_type!r} has no frozen port profile") from exc
    if profile.generic_input_slots != 0 or profile.generic_output_slots != 0:
        raise BindingDomainUndecidable(
            f"operation {operation_type!r} has generic hub slots; "
            "its INFEASIBLE mode is anti-monotone and never liftable"
        )
    return profile


def _required_slot_count(slots: Mapping[str, int]) -> int:
    """Total required port slots on one side (positive counts only, mirroring
    the enumerator's ``count > 0`` requirement filter)."""

    total = 0
    for count in slots.values():
        exact = int(count)
        if exact > 0:
            total += exact
    return total


def _count_port_cells(pose: Pose, key: str) -> int:
    """Count physical port cells on one side.

    Mirrors the enumerator's ``_normalize_port_cell`` discipline: a cell must
    carry exact ``x``/``y``/``dir`` fields, so a malformed pose is undecidable
    rather than silently counted.  An absent key means zero cells (the
    enumerator defaults it to ``[]``); an explicit null is malformed.
    """

    if key not in pose:
        return 0
    raw = pose[key]
    if raw is None:
        raise BindingDomainUndecidable(f"pose {key} is explicitly null")
    if not isinstance(raw, (list, tuple)):
        raise BindingDomainUndecidable(f"pose {key} is not a sequence of port cells")
    count = 0
    for cell in raw:
        if not isinstance(cell, Mapping):
            raise BindingDomainUndecidable(f"pose {key} entry is not a port-cell mapping")
        if "x" not in cell or "y" not in cell or "dir" not in cell:
            raise BindingDomainUndecidable(f"pose {key} entry lacks x/y/dir fields")
        # Value-shape parity with _normalize_port_cell: reject unparsable cells.
        _require_int_like(cell["x"])
        _require_int_like(cell["y"])
        str(cell["dir"])
        count += 1
    return count


def _require_int_like(value: object) -> int:
    """Parity with ``_normalize_port_cell``'s ``int(port[...])`` over the
    JSON-native domain; a non-int-like coordinate is malformed (undecidable)."""

    if isinstance(value, bool):
        raise BindingDomainUndecidable("port-cell coordinate is a bool, not an int")
    if isinstance(value, int):
        return value
    if isinstance(value, (str, float)):
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise BindingDomainUndecidable("port-cell coordinate is not int-like") from exc
    raise BindingDomainUndecidable("port-cell coordinate is not int-like")


def _complete_assignment_exists(required_slots: int, available_cells: int) -> bool:
    """Does a complete assignment saturating every required slot exist?

    Independent bipartite complete-matching (augmenting paths / Kuhn) over the
    complete bipartite graph of ``required_slots`` slot units and
    ``available_cells`` port cells.  For the complete graph this is equivalent
    to ``required_slots <= available_cells`` by Hall's theorem, but it is
    computed as a matching so the primitive stays structurally distinct from
    the enumerator and remains sound (conservative — may overestimate
    feasibility, never underestimate) under future compatibility edges.
    """

    if required_slots <= 0:
        return True
    if available_cells <= 0:
        return False

    cell_to_slot: list[int] = [-1] * available_cells

    def _augment(slot: int, visited: list[bool]) -> bool:
        for cell in range(available_cells):
            if visited[cell]:
                continue
            visited[cell] = True
            if cell_to_slot[cell] == -1 or _augment(cell_to_slot[cell], visited):
                cell_to_slot[cell] = slot
                return True
        return False

    matched = 0
    for slot in range(required_slots):
        if _augment(slot, [False] * available_cells):
            matched += 1
    return matched == required_slots


def _normalize_pattern(forbidden_pose_pattern: object) -> tuple[Literal, ...]:
    if not isinstance(forbidden_pose_pattern, (list, tuple)):
        raise BindingDomainUndecidable("pattern is not a sequence")
    literals: list[Literal] = []
    seq: Sequence[object] = forbidden_pose_pattern
    for entry in seq:
        if not isinstance(entry, (list, tuple)) or len(entry) != 3:
            raise BindingDomainUndecidable("pattern literal is not a 3-tuple")
        group_id, slot_index, pose_id = entry[0], entry[1], entry[2]
        if not isinstance(group_id, str) or not isinstance(pose_id, str):
            raise BindingDomainUndecidable("pattern literal group/pose is not str")
        if isinstance(slot_index, bool) or not isinstance(slot_index, int):
            raise BindingDomainUndecidable("pattern literal slot index is not an exact int")
        literals.append((group_id, slot_index, pose_id))
    return tuple(literals)


__all__ = [
    "BindingDomainUndecidable",
    "BindingEmptyDomainVerdict",
    "binding_domain_is_empty",
    "verify_binding_empty_domain",
]
