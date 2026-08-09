"""Stage-B typed F1 region-capacity proof, validator, and compiler.

The legacy validator remains the production authority until the later cut-over
batch.  This module is its master-independent, snapshot-native differential
counterpart: a proof is parsed once into an immutable value, validated only
against :class:`ValidatedStateSnapshot`, and lowered into a pure
``region_capacity_le`` plan.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Final, Literal, cast

from src.cuts import typed_platform as _platform
from src.cuts.state_snapshot import F1RegionInputs, ValidatedStateSnapshot
from src.cuts.typed_platform import (
    ConstraintPlan,
    FrozenFamilyProof,
    ModelScope,
    ScopeAssumption,
    SemanticCutRejection,
)


Cell = tuple[int, int]
RegionKind = Literal[
    "left_baseline",
    "bottom_baseline",
    "left_or_bottom_union",
    "interior_rect",
    "ghost_complement",
]

REGION_CAPACITY_VALIDATOR_VERSION: Final = "stage-b-f1-validator-v1"
REGION_CAPACITY_COMPILER_VERSION: Final = "stage-b-f1-compiler-v1"

_REGION_GRID_SIZE: Final = 70
_REGION_BITSET_BYTES: Final = _REGION_GRID_SIZE * _REGION_GRID_SIZE // 8 + 1
_SEMANTIC_FINGERPRINT_PREFIX: Final = b"zmd.semantic-fingerprint.v1:"
_BOUNDARY_ASSUMPTION = "left_or_bottom_boundary_saturation"
_PLACEMENT_ASSUMPTION = "placement_rule"
_BOUNDARY_REGIONS = frozenset(
    {
        "bottom_baseline",
        "left_baseline",
        "left_or_bottom_union",
    }
)
_PLACEMENT_RULE_REGIONS: Final = {
    "left_or_bottom_boundary": frozenset({"left_or_bottom_union"}),
    "free": frozenset(),
}


@dataclass(frozen=True, slots=True)
class RegionCapacityProof(FrozenFamilyProof):
    """Immutable, fully decoded F1 combinatorial witness."""

    cert_kind: str
    region_kind: RegionKind
    region_cells: frozenset[Cell]
    capacity: int
    demand: int
    gap: int
    contributing_groups: tuple[tuple[str, int], ...]
    cells_per_pose: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class RegionCapacityBody:
    """Pure compiler input derived from one ``RegionCapacityProof``."""

    region_kind: RegionKind
    region_cells: frozenset[Cell]
    capacity: int
    group_cell_weights: tuple[tuple[str, int], ...]


def _f1_inputs(snapshot: ValidatedStateSnapshot) -> F1RegionInputs:
    inputs = snapshot.family_inputs.get("region_capacity")
    if type(inputs) is not F1RegionInputs:
        raise TypeError("validated snapshot lacks exact F1RegionInputs")
    return inputs


def _proof_rejection(reason: str) -> SemanticCutRejection:
    return SemanticCutRejection("proof", reason)


def _require_exact_int(value: object, *, field_name: str) -> int:
    if type(value) is not int:
        raise _proof_rejection(f"F1 {field_name} must be an exact int")
    return value


def _require_non_empty_str(value: object, *, field_name: str) -> str:
    if type(value) is not str or not value:
        raise _proof_rejection(f"F1 {field_name} must be a non-empty exact str")
    return value


def _parse_region_kind(value: object) -> RegionKind:
    region_kind = _require_non_empty_str(value, field_name="region_kind")
    if region_kind not in {
        "bottom_baseline",
        "ghost_complement",
        "interior_rect",
        "left_baseline",
        "left_or_bottom_union",
    }:
        raise _proof_rejection("F1 region_kind is outside the closed set")
    return cast(RegionKind, region_kind)


def _decode_region_cells(value: object) -> frozenset[Cell]:
    encoded = _require_non_empty_str(value, field_name="region_cells_bitset_b64")
    try:
        raw = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
        raise _proof_rejection("F1 region bitset is not canonical base64") from exc
    if len(raw) != _REGION_BITSET_BYTES:
        raise _proof_rejection("F1 region bitset has the wrong byte length")
    used_last_bits = (_REGION_GRID_SIZE * _REGION_GRID_SIZE) % 8
    if used_last_bits and raw[-1] >> used_last_bits:
        raise _proof_rejection("F1 region bitset sets cells outside the grid")
    cells: set[Cell] = set()
    for x in range(_REGION_GRID_SIZE):
        for y in range(_REGION_GRID_SIZE):
            index = x * _REGION_GRID_SIZE + y
            if raw[index // 8] & (1 << (index % 8)):
                cells.add((x, y))
    return frozenset(cells)


def _parse_contributing_groups(value: object) -> tuple[tuple[str, int], ...]:
    if type(value) is not list:
        raise _proof_rejection("F1 contributing_groups must be an exact list")
    parsed: list[tuple[str, int]] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if type(item) is not list or len(item) != 2:
            raise _proof_rejection(f"F1 contributing_groups[{index}] must be a two-item exact list")
        group_id = _require_non_empty_str(item[0], field_name=f"contributing_groups[{index}].group_id")
        contribution = _require_exact_int(item[1], field_name=f"contributing_groups[{index}].demand")
        if group_id in seen:
            raise _proof_rejection("F1 contributing_groups contains a duplicate group")
        seen.add(group_id)
        parsed.append((group_id, contribution))
    return tuple(parsed)


def _parse_cells_per_pose(value: object) -> tuple[tuple[str, int], ...]:
    if type(value) is not dict:
        raise _proof_rejection("F1 cells_per_pose must be an exact object")
    parsed: list[tuple[str, int]] = []
    for raw_group_id, raw_weight in value.items():
        group_id = _require_non_empty_str(raw_group_id, field_name="cells_per_pose key")
        weight = _require_exact_int(raw_weight, field_name=f"cells_per_pose[{group_id!r}]")
        parsed.append((group_id, weight))
    return tuple(sorted(parsed))


def _parse_region_capacity_proof(proof_payload: bytes) -> RegionCapacityProof:
    proof = _platform._decode_proof_frame(  # noqa: SLF001 - shared Stage-B frame primitive
        proof_payload,
        expected_family="region_capacity",
        expected_schema_version=1,
    )
    expected_fields = frozenset(
        {
            "cap_R",
            "cells_per_pose",
            "cert_kind",
            "contributing_groups",
            "demand_R",
            "gap",
            "lp_dual_objective",
            "lp_dual_ray_b64",
            "region_cells_bitset_b64",
            "region_kind",
        }
    )
    if frozenset(proof) != expected_fields:
        raise _proof_rejection("F1 proof fields are not exact")
    if proof["cert_kind"] != "region_capacity_combinatorial":
        raise _proof_rejection("F1 cert_kind must be region_capacity_combinatorial")
    if proof["lp_dual_ray_b64"] is not None or proof["lp_dual_objective"] is not None:
        raise _proof_rejection("F1 combinatorial proof cannot carry LP-dual fields")
    return RegionCapacityProof(
        family="region_capacity",
        schema_version=1,
        cert_kind="region_capacity_combinatorial",
        region_kind=_parse_region_kind(proof["region_kind"]),
        region_cells=_decode_region_cells(proof["region_cells_bitset_b64"]),
        capacity=_require_exact_int(proof["cap_R"], field_name="cap_R"),
        demand=_require_exact_int(proof["demand_R"], field_name="demand_R"),
        gap=_require_exact_int(proof["gap"], field_name="gap"),
        contributing_groups=_parse_contributing_groups(proof["contributing_groups"]),
        cells_per_pose=_parse_cells_per_pose(proof["cells_per_pose"]),
    )


def _group_placement_rule(inputs: F1RegionInputs, group_id: str) -> str | None:
    # Divergence from legacy verify_placement_rule (B2 dual-review opus#2): a
    # template without a placement_rule field defaults to "free" on the legacy
    # path but yields None (reject) here. Real F1 contributors always carry an
    # explicit boundary placement rule, so the branch is unreachable in
    # production and the asymmetry errs toward rejection.
    facility_type = inputs.instance_to_facility_type.get(group_id)
    if type(facility_type) is not str:
        return None
    placement_rule = inputs.template_placement_rules.get(facility_type)
    return placement_rule if type(placement_rule) is str else None


def _group_cells_per_pose(inputs: F1RegionInputs, group_id: str) -> int | None:
    facility_type = inputs.instance_to_facility_type.get(group_id)
    if type(facility_type) is not str:
        return None
    dimensions = inputs.template_dimensions.get(facility_type)
    if type(dimensions) is not tuple or len(dimensions) != 2:
        return None
    width, height = dimensions
    if type(width) is not int or type(height) is not int:
        return None
    return width * height


def _registered_pose_ids(inputs: F1RegionInputs, facility_type: str) -> frozenset[str]:
    return frozenset(
        pose_id
        for registered_facility_type, pose_id in inputs.pose_occupied_cells
        if registered_facility_type == facility_type
    )


def _validate_region_capacity_proof(
    proof: RegionCapacityProof,
    snapshot: ValidatedStateSnapshot,
) -> None:
    inputs = _f1_inputs(snapshot)
    recomputed_capacity = len(proof.region_cells) - len(
        proof.region_cells & (snapshot.ghost_cells | snapshot.exterior_blocks)
    )
    if proof.capacity != recomputed_capacity:
        raise _proof_rejection("F1 cap_R differs from the snapshot recomputation")

    cells_per_pose = dict(proof.cells_per_pose)
    recomputed_demand = 0
    for group_id, contribution in proof.contributing_groups:
        demand = inputs.group_demands.get(group_id)
        pose_domain = inputs.group_pose_domains.get(group_id)
        facility_type = inputs.instance_to_facility_type.get(group_id)
        if type(demand) is not int or not isinstance(pose_domain, frozenset) or type(facility_type) is not str:
            raise _proof_rejection(f"F1 proof references unknown group {group_id!r}")
        registered_pose_ids = _registered_pose_ids(inputs, facility_type)
        if not registered_pose_ids or pose_domain != registered_pose_ids:
            raise _proof_rejection(
                f"F1 group {group_id!r} pose domain differs from its complete registered facility pool"
            )
        placement_rule = _group_placement_rule(inputs, group_id)
        if placement_rule is None or proof.region_kind not in _PLACEMENT_RULE_REGIONS.get(
            placement_rule,
            frozenset(),
        ):
            raise _proof_rejection(f"F1 group {group_id!r} placement rule does not map to its region")
        if not pose_domain:
            raise _proof_rejection(f"F1 group {group_id!r} has an empty pose domain")
        current_weight = _group_cells_per_pose(inputs, group_id)
        cert_weight = cells_per_pose.get(group_id)
        if current_weight is None or cert_weight != current_weight:
            raise _proof_rejection(f"F1 cells_per_pose differs for group {group_id!r}")
        for pose_id in pose_domain:
            occupied = inputs.pose_occupied_cells.get((facility_type, pose_id))
            if not isinstance(occupied, frozenset) or not occupied.issubset(proof.region_cells):
                raise _proof_rejection(f"F1 group {group_id!r} has a pose outside its region")
            if len(occupied) != current_weight:
                raise _proof_rejection(
                    f"F1 group {group_id!r} pose {pose_id!r} occupied-cell cardinality "
                    "differs from its template dimensions"
                )
        expected_contribution = demand * current_weight
        if contribution != expected_contribution:
            raise _proof_rejection(f"F1 contribution differs for group {group_id!r}")
        recomputed_demand += expected_contribution

    if proof.demand != recomputed_demand:
        raise _proof_rejection("F1 demand_R differs from the snapshot recomputation")
    expected_gap = recomputed_demand - recomputed_capacity
    if proof.gap != expected_gap or expected_gap <= 0:
        raise _proof_rejection("F1 proof does not establish a strict positive capacity gap")


def _region_scope(proof: RegionCapacityProof, snapshot: ValidatedStateSnapshot) -> tuple[str, str | None]:
    if proof.region_cells & snapshot.ghost_cells:
        ghost_digest = _platform._snapshot_ghost_rect_digest(snapshot)  # noqa: SLF001 - shared identity primitive
        if ghost_digest is None:
            raise TypeError("snapshot ghost cells exist without a ghost rectangle")
        return ("bound", ghost_digest)
    return ("agnostic", None)


def _body_from_proof(proof: RegionCapacityProof) -> RegionCapacityBody:
    cells_per_pose = dict(proof.cells_per_pose)
    return RegionCapacityBody(
        region_kind=proof.region_kind,
        region_cells=proof.region_cells,
        capacity=proof.capacity,
        group_cell_weights=tuple((group_id, cells_per_pose[group_id]) for group_id, _ in proof.contributing_groups),
    )


def region_capacity_master_domain_projection_v1(
    snapshot: ValidatedStateSnapshot,
    group_ids: tuple[str, ...],
) -> str:
    """Return the builder-captured snapshot side of MasterDomainProjectionV1.

    ``ValidatedStateSnapshot`` computes the projection from the complete
    facility-pool records (including anchor/mode tokens), mandatory slot
    structure, and template pose registration.  This F1 gate additionally
    proves that every contributor exists before binding that complete identity
    into its plan.  B5 independently recomputes the same projection from the
    live master.
    """

    if type(snapshot) is not ValidatedStateSnapshot:
        raise TypeError("MasterDomainProjectionV1 requires ValidatedStateSnapshot")
    if type(group_ids) is not tuple or not group_ids:
        raise TypeError("MasterDomainProjectionV1 group_ids must be a non-empty tuple")
    if len(group_ids) != len(set(group_ids)) or tuple(sorted(group_ids)) != group_ids:
        raise ValueError("MasterDomainProjectionV1 group_ids must be unique and sorted")
    inputs = _f1_inputs(snapshot)
    for group_id in group_ids:
        if type(group_id) is not str or not group_id:
            raise TypeError("MasterDomainProjectionV1 group IDs must be non-empty exact strings")
        demand = inputs.group_demands.get(group_id)
        pose_domain = inputs.group_pose_domains.get(group_id)
        facility_type = inputs.instance_to_facility_type.get(group_id)
        if type(demand) is not int or not isinstance(pose_domain, frozenset) or type(facility_type) is not str:
            raise TypeError("validated F1 inputs lack a projected contributor")
    return snapshot.master_domain_projection


def region_capacity_semantic_fingerprint_v1(
    *,
    parameters: dict[str, object],
    model_scope: ModelScope,
    snapshot: ValidatedStateSnapshot,
) -> str:
    """Return the content identity of the B2 F1 lowering semantics."""

    projection = {
        "compiler_version": REGION_CAPACITY_COMPILER_VERSION,
        "family": "region_capacity",
        "model_scope": {
            "domain_fingerprint": model_scope.domain_fingerprint,
            "ghost_policy": model_scope.ghost_policy,
            "ghost_rect_digest": model_scope.ghost_rect_digest,
        },
        "operation": "region_capacity_le",
        "parameters": parameters,
        "parameter_schema": {
            "capacity": "exact-int>=0",
            "group_cell_weights": "non-empty-map[non-empty-str,exact-int>0]",
        },
        "schema_version": 1,
        "snapshot_artifact_identities": dict(sorted(snapshot.artifact_hashes.items())),
        "snapshot_source_digest": snapshot.source_digest,
    }
    return _platform._domain_digest(  # noqa: SLF001 - shared canonical digest primitive
        _SEMANTIC_FINGERPRINT_PREFIX,
        _platform._canonical_node(projection),  # noqa: SLF001 - shared canonical digest primitive
    )


def validate_region_capacity_scope_assumptions(
    assumptions: tuple[ScopeAssumption, ...],
    snapshot: ValidatedStateSnapshot,
) -> str | None:
    """Reverify each supplied F1 assumption against frozen snapshot facts."""

    inputs = _f1_inputs(snapshot)
    seen_placement_groups: set[str] = set()
    if not assumptions:
        return "F1 scope has no active assumptions"
    for assumption in assumptions:
        if assumption.key == _PLACEMENT_ASSUMPTION:
            parts = assumption.value.split("=", 1)
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                return "F1 placement-rule assumption is malformed"
            group_id, expected_rule = parts[0].strip(), parts[1].strip()
            if group_id in seen_placement_groups:
                return "F1 placement-rule assumption is duplicated"
            actual_rule = _group_placement_rule(inputs, group_id)
            if actual_rule is None or actual_rule != expected_rule:
                return "F1 placement-rule assumption differs from the snapshot"
            seen_placement_groups.add(group_id)
        elif assumption.key == _BOUNDARY_ASSUMPTION:
            # Legacy ``verify_boundary_saturation`` treats canonical source
            # availability as the truth condition and deliberately ignores the
            # note-like value. ScopeAssumption already enforces a non-empty
            # value, while the snapshot preserves the source's None-vs-present
            # distinction that the legacy verifier reads.
            if not snapshot.canonical_rules_source_present:
                return "F1 boundary-saturation source is unavailable"
            continue
        else:
            return "F1 scope carries an unsupported assumption"
    return None


def validate_region_capacity_assumption_completeness(
    proof: FrozenFamilyProof,
    assumptions: tuple[ScopeAssumption, ...],
) -> str | None:
    """Bind the already-verified assumption multimap to one frozen F1 proof."""

    if type(proof) is not RegionCapacityProof:
        raise TypeError("F1 assumption completeness requires RegionCapacityProof")
    expected_groups = {group_id for group_id, _ in proof.contributing_groups}
    seen_placement_groups: set[str] = set()
    boundary_count = 0
    for assumption in assumptions:
        if assumption.key == _PLACEMENT_ASSUMPTION:
            group_id = assumption.value.split("=", 1)[0].strip()
            seen_placement_groups.add(group_id)
        elif assumption.key == _BOUNDARY_ASSUMPTION:
            boundary_count += 1

    if seen_placement_groups != expected_groups:
        return "F1 placement-rule assumptions are incomplete or extraneous"
    expected_boundary_count = 1 if proof.region_kind in _BOUNDARY_REGIONS else 0
    if boundary_count != expected_boundary_count:
        return "F1 boundary-saturation assumption is incomplete or extraneous"
    return None


class RegionCapacityPlugin:
    """Complete B2 typed F1 parser/validator/compiler chain."""

    def parse_and_validate_proof(
        self,
        proof_payload: bytes,
        snapshot: ValidatedStateSnapshot,
    ) -> RegionCapacityProof:
        try:
            proof = _parse_region_capacity_proof(proof_payload)
        except SemanticCutRejection:
            raise
        except ValueError as exc:
            raise _proof_rejection(str(exc) or type(exc).__name__) from exc
        _validate_region_capacity_proof(proof, snapshot)
        return proof

    def derive_body(self, proof: FrozenFamilyProof) -> RegionCapacityBody:
        if type(proof) is not RegionCapacityProof:
            raise TypeError("F1 derive_body requires RegionCapacityProof")
        return _body_from_proof(proof)

    def compile(
        self,
        body: object,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> ConstraintPlan:
        if type(body) is not RegionCapacityBody or type(proof) is not RegionCapacityProof:
            raise TypeError("F1 compiler requires RegionCapacityBody/RegionCapacityProof")
        if body != _body_from_proof(proof):
            raise TypeError("F1 body is not the pure projection of its proof")
        ghost_policy, ghost_rect_digest = _region_scope(proof, snapshot)
        group_ids = tuple(sorted(group_id for group_id, _ in body.group_cell_weights))
        model_scope = ModelScope(
            ghost_policy=cast(Literal["agnostic", "bound"], ghost_policy),
            ghost_rect_digest=ghost_rect_digest,
            domain_fingerprint=region_capacity_master_domain_projection_v1(snapshot, group_ids),
        )
        parameters: dict[str, object] = {
            "capacity": body.capacity,
            "group_cell_weights": dict(body.group_cell_weights),
        }
        return ConstraintPlan(
            family="region_capacity",
            schema_version=1,
            semantic_fingerprint=region_capacity_semantic_fingerprint_v1(
                parameters=parameters,
                model_scope=model_scope,
                snapshot=snapshot,
            ),
            model_scope=model_scope,
            operation="region_capacity_le",
            parameters=parameters,
        )

    def validate_plan(
        self,
        plan: ConstraintPlan,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> None:
        if type(plan) is not ConstraintPlan or type(proof) is not RegionCapacityProof:
            raise TypeError("F1 plan validator requires ConstraintPlan/RegionCapacityProof")
        expected_body = _body_from_proof(proof)
        expected_policy, expected_ghost_digest = _region_scope(proof, snapshot)
        expected_group_ids = tuple(sorted(group_id for group_id, _ in expected_body.group_cell_weights))
        expected_parameters = {
            "capacity": expected_body.capacity,
            "group_cell_weights": dict(expected_body.group_cell_weights),
        }
        if plan.family != "region_capacity" or plan.schema_version != 1 or plan.operation != "region_capacity_le":
            raise SemanticCutRejection("plan", "F1 plan family/schema/operation differs from the compiler contract")
        if dict(plan.parameters) != expected_parameters:
            raise SemanticCutRejection("plan", "F1 plan parameters differ from the frozen proof")
        if (
            plan.model_scope.ghost_policy != expected_policy
            or plan.model_scope.ghost_rect_digest != expected_ghost_digest
        ):
            raise SemanticCutRejection("plan", "F1 plan ghost scope differs from the frozen proof/snapshot")
        expected_domain = region_capacity_master_domain_projection_v1(snapshot, expected_group_ids)
        if plan.model_scope.domain_fingerprint != expected_domain:
            raise SemanticCutRejection("plan", "F1 plan master-domain projection is stale")
        expected_semantic_fingerprint = region_capacity_semantic_fingerprint_v1(
            parameters=expected_parameters,
            model_scope=plan.model_scope,
            snapshot=snapshot,
        )
        if plan.semantic_fingerprint != expected_semantic_fingerprint:
            raise SemanticCutRejection("plan", "F1 plan semantic fingerprint is stale")


__all__ = [
    "REGION_CAPACITY_COMPILER_VERSION",
    "REGION_CAPACITY_VALIDATOR_VERSION",
    "RegionCapacityBody",
    "RegionCapacityPlugin",
    "RegionCapacityProof",
    "region_capacity_master_domain_projection_v1",
    "region_capacity_semantic_fingerprint_v1",
    "validate_region_capacity_assumption_completeness",
    "validate_region_capacity_scope_assumptions",
]
