"""Stage-B typed F6 Hall-witness proof, validator, and compiler.

The legacy F6 path remains the production authority until the Stage-B wiring
cut-over.  This module reproduces its complete Hall proof obligations from one
deeply frozen :class:`ValidatedStateSnapshot` and emits a master-independent
``shape_packing_hall_le`` plan.  F6 is unconditionally ghost-bound.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Final, Literal, cast

from src.cuts import typed_platform as _platform
from src.cuts.state_snapshot import F6HallInputs, ValidatedStateSnapshot
from src.cuts.typed_platform import (
    ConstraintPlan,
    FrozenFamilyProof,
    ModelScope,
    SemanticCutRejection,
)


HallRegionKind = Literal["left_baseline", "bottom_baseline"]

SHAPE_PACKING_HALL_VALIDATOR_VERSION: Final = "stage-b-f6-validator-v1"
SHAPE_PACKING_HALL_COMPILER_VERSION: Final = "stage-b-f6-compiler-v1"

_GRID_SIZE: Final = 70
_VALID_REGION_KINDS = frozenset({"left_baseline", "bottom_baseline"})
_POSE_SHAPE_CANONICAL_PATTERN: re.Pattern[str] = re.compile(r"^\d+x\d+_rigid$")
_SEMANTIC_FINGERPRINT_PREFIX: Final = b"zmd.semantic-fingerprint.v1:"


@dataclass(frozen=True, slots=True)
class ShapePackingHallProof(FrozenFamilyProof):
    """Immutable projection of the closed 14-field F6 certificate."""

    cert_kind: str
    region_kind: HallRegionKind
    region_total_length: int
    partition_lens: tuple[int, ...]
    partition_offsets: tuple[int, ...]
    pose_length: int
    pose_shape_canonical: str
    max_packable: tuple[int, ...]
    total_packable: int
    contributing_group: str
    region_demand: int
    group_demand: int
    ghost_rect_repr: tuple[int, int, int, int]
    exterior_blocks_digest: str


@dataclass(frozen=True, slots=True)
class ShapePackingHallBody:
    """Pure compiler input derived from one frozen F6 proof."""

    group_id: str
    region_kind: HallRegionKind
    capacity: int


def _f6_inputs(snapshot: ValidatedStateSnapshot) -> F6HallInputs:
    inputs = snapshot.family_inputs.get("shape_packing_hall")
    if type(inputs) is not F6HallInputs:
        raise TypeError("validated snapshot lacks exact F6HallInputs")
    return inputs


def _proof_rejection(reason: str) -> SemanticCutRejection:
    return SemanticCutRejection("proof", reason)


def _require_exact_int(value: object, *, field_name: str) -> int:
    if type(value) is not int:
        raise _proof_rejection(f"F6 {field_name} must be an exact int")
    return value


def _require_non_empty_str(value: object, *, field_name: str) -> str:
    if type(value) is not str or not value:
        raise _proof_rejection(f"F6 {field_name} must be a non-empty exact str")
    return value


def _parse_region_kind(value: object) -> HallRegionKind:
    region_kind = _require_non_empty_str(value, field_name="region_kind")
    if region_kind not in _VALID_REGION_KINDS:
        raise _proof_rejection("F6 region_kind is outside the closed set")
    return cast(HallRegionKind, region_kind)


def _parse_int_tuple(value: object, *, field_name: str) -> tuple[int, ...]:
    if type(value) is not list:
        raise _proof_rejection(f"F6 {field_name} must be an exact list")
    return tuple(_require_exact_int(item, field_name=f"{field_name}[{index}]") for index, item in enumerate(value))


def _parse_ghost_rect(value: object) -> tuple[int, int, int, int]:
    parsed = _parse_int_tuple(value, field_name="ghost_rect_repr")
    if len(parsed) != 4:
        raise _proof_rejection("F6 ghost_rect_repr must contain exactly four integers")
    first, second, third, fourth = parsed
    return (first, second, third, fourth)


def _validate_scalar_and_shape_schema(
    *,
    region_total_length: int,
    pose_length: int,
    pose_shape_canonical: str,
    total_packable: int,
    region_demand: int,
    group_demand: int,
) -> None:
    if region_total_length != _GRID_SIZE:
        raise _proof_rejection("F6 region_total_length must equal the 70-cell grid bound")
    if pose_length < 2:
        raise _proof_rejection("F6 pose_length must be at least two")
    if total_packable < 0:
        raise _proof_rejection("F6 total_packable must be non-negative")
    if region_demand < 1:
        raise _proof_rejection("F6 region_demand must be positive")
    if group_demand < 1:
        raise _proof_rejection("F6 group_demand must be positive")
    if not _POSE_SHAPE_CANONICAL_PATTERN.match(pose_shape_canonical):
        raise _proof_rejection("F6 pose_shape_canonical does not match the rigid-shape schema")
    parts = pose_shape_canonical[: -len("_rigid")].split("x")
    if len(parts) != 2:
        raise _proof_rejection("F6 pose_shape_canonical cannot be split into two dimensions")
    try:
        first_dimension, second_dimension = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise _proof_rejection("F6 pose_shape_canonical dimensions are not integers") from exc
    if min(first_dimension, second_dimension) != 1:
        raise _proof_rejection("F6 Phase 1.2 supports only 1xL rigid shapes")
    if max(first_dimension, second_dimension) != pose_length:
        raise _proof_rejection("F6 pose_length differs from pose_shape_canonical")


def _validate_partition_internal_consistency(proof: ShapePackingHallProof) -> None:
    lens = proof.partition_lens
    offsets = proof.partition_offsets
    max_packable = proof.max_packable
    if not (len(lens) == len(offsets) == len(max_packable)):
        raise _proof_rejection("F6 partition_lens/partition_offsets/max_packable lengths differ")
    previous_end = -1
    for index, (segment_length, offset, segment_capacity) in enumerate(zip(lens, offsets, max_packable, strict=True)):
        if segment_length < 1:
            raise _proof_rejection(f"F6 partition_lens[{index}] must be positive")
        if offset < 0:
            raise _proof_rejection(f"F6 partition_offsets[{index}] must be non-negative")
        if offset + segment_length > _GRID_SIZE:
            raise _proof_rejection(f"F6 partition segment {index} extends outside the grid")
        if offset <= previous_end:
            raise _proof_rejection(f"F6 partition segment {index} overlaps its predecessor")
        if segment_capacity != segment_length // proof.pose_length:
            raise _proof_rejection(f"F6 max_packable[{index}] differs from the segment quotient")
        previous_end = offset + segment_length - 1
    if sum(max_packable) != proof.total_packable:
        raise _proof_rejection("F6 total_packable differs from sum(max_packable)")
    if proof.total_packable >= proof.region_demand:
        raise _proof_rejection("F6 proof does not establish the strict Hall inequality")


def _parse_shape_packing_hall_proof(proof_payload: bytes) -> ShapePackingHallProof:
    proof = _platform._decode_proof_frame(  # noqa: SLF001 - shared Stage-B frame primitive
        proof_payload,
        expected_family="shape_packing_hall",
        expected_schema_version=1,
    )
    expected_fields = frozenset(
        {
            "cert_kind",
            "contributing_group",
            "exterior_blocks_digest",
            "ghost_rect_repr",
            "group_demand",
            "max_packable",
            "partition_lens",
            "partition_offsets",
            "pose_length",
            "pose_shape_canonical",
            "region_demand",
            "region_kind",
            "region_total_length",
            "total_packable",
        }
    )
    if frozenset(proof) != expected_fields:
        raise _proof_rejection("F6 proof fields are not exact")
    if proof["cert_kind"] != "hall_interval_witness":
        raise _proof_rejection("F6 cert_kind must be hall_interval_witness")

    region_total_length = _require_exact_int(proof["region_total_length"], field_name="region_total_length")
    pose_length = _require_exact_int(proof["pose_length"], field_name="pose_length")
    pose_shape_canonical = _require_non_empty_str(
        proof["pose_shape_canonical"],
        field_name="pose_shape_canonical",
    )
    total_packable = _require_exact_int(proof["total_packable"], field_name="total_packable")
    region_demand = _require_exact_int(proof["region_demand"], field_name="region_demand")
    group_demand = _require_exact_int(proof["group_demand"], field_name="group_demand")
    _validate_scalar_and_shape_schema(
        region_total_length=region_total_length,
        pose_length=pose_length,
        pose_shape_canonical=pose_shape_canonical,
        total_packable=total_packable,
        region_demand=region_demand,
        group_demand=group_demand,
    )
    parsed = ShapePackingHallProof(
        family="shape_packing_hall",
        schema_version=1,
        cert_kind="hall_interval_witness",
        region_kind=_parse_region_kind(proof["region_kind"]),
        region_total_length=region_total_length,
        partition_lens=_parse_int_tuple(proof["partition_lens"], field_name="partition_lens"),
        partition_offsets=_parse_int_tuple(proof["partition_offsets"], field_name="partition_offsets"),
        pose_length=pose_length,
        pose_shape_canonical=pose_shape_canonical,
        max_packable=_parse_int_tuple(proof["max_packable"], field_name="max_packable"),
        total_packable=total_packable,
        contributing_group=_require_non_empty_str(
            proof["contributing_group"],
            field_name="contributing_group",
        ),
        region_demand=region_demand,
        group_demand=group_demand,
        ghost_rect_repr=_parse_ghost_rect(proof["ghost_rect_repr"]),
        exterior_blocks_digest=_require_non_empty_str(
            proof["exterior_blocks_digest"],
            field_name="exterior_blocks_digest",
        ),
    )
    _validate_partition_internal_consistency(parsed)
    return parsed


def _opposite_region_kind(region_kind: HallRegionKind) -> HallRegionKind:
    return "bottom_baseline" if region_kind == "left_baseline" else "left_baseline"


def _partition_from_snapshot(
    region_kind: HallRegionKind,
    snapshot: ValidatedStateSnapshot,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if region_kind == "left_baseline":
        region_cells = tuple((coordinate, 0) for coordinate in range(_GRID_SIZE))
    else:
        region_cells = tuple((0, coordinate) for coordinate in range(_GRID_SIZE))
    blocked = snapshot.ghost_cells | snapshot.exterior_blocks
    lens: list[int] = []
    offsets: list[int] = []
    current_length = 0
    current_offset = 0
    for index, cell in enumerate(region_cells):
        if cell in blocked:
            if current_length > 0:
                lens.append(current_length)
                offsets.append(current_offset)
            current_length = 0
            current_offset = index + 1
        else:
            if current_length == 0:
                current_offset = index
            current_length += 1
    if current_length > 0:
        lens.append(current_length)
        offsets.append(current_offset)
    return tuple(lens), tuple(offsets)


def _legacy_exterior_blocks_digest(snapshot: ValidatedStateSnapshot) -> str:
    payload = ";".join(f"{x},{y}" for x, y in sorted(snapshot.exterior_blocks)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _validate_shape_packing_hall_proof(
    proof: ShapePackingHallProof,
    snapshot: ValidatedStateSnapshot,
) -> None:
    inputs = _f6_inputs(snapshot)

    actual_group_demand = inputs.group_demands.get(proof.contributing_group)
    if type(actual_group_demand) is not int:
        raise _proof_rejection("F6 proof references an unknown contributing_group")
    if proof.group_demand != actual_group_demand:
        raise _proof_rejection("F6 group_demand differs from the snapshot source of truth")
    if proof.region_demand > proof.group_demand:
        raise _proof_rejection("F6 region_demand exceeds group_demand")
    if proof.region_demand > _GRID_SIZE // proof.pose_length:
        raise _proof_rejection("F6 region_demand exceeds the physical baseline upper bound")

    facility_type = inputs.group_to_facility_type.get(proof.contributing_group)
    if type(facility_type) is not str:
        raise _proof_rejection("F6 contributing_group has no facility-type binding")
    placement_rule = inputs.template_placement_rules.get(facility_type)
    if placement_rule != "left_or_bottom_boundary":
        raise _proof_rejection("F6 contributing_group does not use the boundary placement rule")
    dimensions = inputs.template_dimensions.get(facility_type)
    if type(dimensions) is not tuple or len(dimensions) != 2:
        raise _proof_rejection("F6 facility template has no exact dimensions")
    width, height = dimensions
    if type(width) is not int or type(height) is not int or min(width, height) != 1:
        raise _proof_rejection("F6 facility template is not a 1xL rigid shape")
    if max(width, height) != proof.pose_length:
        raise _proof_rejection("F6 pose_length differs from the snapshot facility template")

    other_lens, _other_offsets = _partition_from_snapshot(
        _opposite_region_kind(proof.region_kind),
        snapshot,
    )
    other_capacity = sum(segment_length // proof.pose_length for segment_length in other_lens)
    proven_lower_bound = max(0, proof.group_demand - other_capacity)
    if proof.region_demand > proven_lower_bound:
        raise _proof_rejection("F6 region_demand exceeds its source-of-truth lower bound")

    if inputs.ghost is None or snapshot.ghost is None:
        raise _proof_rejection("F6 requires a ghost-bound snapshot")
    if inputs.ghost is not snapshot.ghost and inputs.ghost != snapshot.ghost:
        raise TypeError("F6HallInputs ghost projection differs from the public snapshot ghost")
    if proof.ghost_rect_repr != snapshot.ghost.as_tuple():
        raise _proof_rejection("F6 ghost_rect_repr differs from the snapshot")
    if proof.exterior_blocks_digest != _legacy_exterior_blocks_digest(snapshot):
        raise _proof_rejection("F6 exterior_blocks_digest differs from the snapshot recomputation")

    recomputed_lens, recomputed_offsets = _partition_from_snapshot(proof.region_kind, snapshot)
    if proof.partition_lens != recomputed_lens:
        raise _proof_rejection("F6 partition_lens differs from the snapshot recomputation")
    if proof.partition_offsets != recomputed_offsets:
        raise _proof_rejection("F6 partition_offsets differs from the snapshot recomputation")
    recomputed_max = tuple(segment_length // proof.pose_length for segment_length in recomputed_lens)
    recomputed_total = sum(recomputed_max)
    if proof.max_packable != recomputed_max:
        raise _proof_rejection("F6 max_packable differs from the snapshot recomputation")
    if proof.total_packable != recomputed_total:
        raise _proof_rejection("F6 total_packable differs from the snapshot recomputation")
    if recomputed_total >= proof.region_demand:
        raise _proof_rejection("F6 recomputed partition does not establish the strict Hall inequality")


def _body_from_proof(proof: ShapePackingHallProof) -> ShapePackingHallBody:
    return ShapePackingHallBody(
        group_id=proof.contributing_group,
        region_kind=proof.region_kind,
        capacity=proof.total_packable,
    )


def shape_packing_hall_master_domain_projection_v1(
    snapshot: ValidatedStateSnapshot,
    group_id: str,
) -> str:
    """Return the builder-captured F6 side of MasterDomainProjectionV1."""

    if type(snapshot) is not ValidatedStateSnapshot:
        raise TypeError("F6 MasterDomainProjectionV1 requires ValidatedStateSnapshot")
    if type(group_id) is not str or not group_id:
        raise TypeError("F6 MasterDomainProjectionV1 group_id must be a non-empty exact str")
    inputs = _f6_inputs(snapshot)
    demand = inputs.group_demands.get(group_id)
    facility_type = inputs.group_to_facility_type.get(group_id)
    if type(demand) is not int or type(facility_type) is not str:
        raise TypeError("validated F6 inputs lack the projected contributing group")
    return snapshot.shape_packing_hall_master_domain_projection


def shape_packing_hall_semantic_fingerprint_v1(
    *,
    parameters: dict[str, object],
    model_scope: ModelScope,
    snapshot: ValidatedStateSnapshot,
) -> str:
    """Return the content identity of the B3 F6 lowering semantics."""

    projection = {
        "compiler_version": SHAPE_PACKING_HALL_COMPILER_VERSION,
        "family": "shape_packing_hall",
        "model_scope": {
            "domain_fingerprint": model_scope.domain_fingerprint,
            "ghost_policy": model_scope.ghost_policy,
            "ghost_rect_digest": model_scope.ghost_rect_digest,
        },
        "operation": "shape_packing_hall_le",
        "parameters": parameters,
        "parameter_schema": {
            "capacity": "exact-int>=0",
            "group_id": "non-empty-str",
            "region_kind": "enum[left_baseline,bottom_baseline]",
        },
        "schema_version": 1,
        "snapshot_artifact_identities": dict(sorted(snapshot.artifact_hashes.items())),
        "snapshot_source_digest": snapshot.source_digest,
    }
    return _platform._domain_digest(  # noqa: SLF001 - shared canonical digest primitive
        _SEMANTIC_FINGERPRINT_PREFIX,
        _platform._canonical_node(projection),  # noqa: SLF001 - shared canonical digest primitive
    )


class ShapePackingHallPlugin:
    """Complete B3 typed F6 parser/validator/compiler chain."""

    def parse_and_validate_proof(
        self,
        proof_payload: bytes,
        snapshot: ValidatedStateSnapshot,
    ) -> ShapePackingHallProof:
        try:
            proof = _parse_shape_packing_hall_proof(proof_payload)
        except SemanticCutRejection:
            raise
        except ValueError as exc:
            raise _proof_rejection(str(exc) or type(exc).__name__) from exc
        _validate_shape_packing_hall_proof(proof, snapshot)
        return proof

    def derive_body(self, proof: FrozenFamilyProof) -> ShapePackingHallBody:
        if type(proof) is not ShapePackingHallProof:
            raise TypeError("F6 derive_body requires ShapePackingHallProof")
        return _body_from_proof(proof)

    def compile(
        self,
        body: object,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> ConstraintPlan:
        if type(body) is not ShapePackingHallBody or type(proof) is not ShapePackingHallProof:
            raise TypeError("F6 compiler requires ShapePackingHallBody/ShapePackingHallProof")
        if body != _body_from_proof(proof):
            raise TypeError("F6 body is not the pure projection of its proof")
        ghost_rect_digest = _platform._snapshot_ghost_rect_digest(  # noqa: SLF001 - shared identity primitive
            snapshot
        )
        if ghost_rect_digest is None:
            raise TypeError("F6 compiler requires a ghost-bound snapshot")
        model_scope = ModelScope(
            ghost_policy="bound",
            ghost_rect_digest=ghost_rect_digest,
            domain_fingerprint=shape_packing_hall_master_domain_projection_v1(
                snapshot,
                body.group_id,
            ),
        )
        parameters: dict[str, object] = {
            "capacity": body.capacity,
            "group_id": body.group_id,
            "region_kind": body.region_kind,
        }
        return ConstraintPlan(
            family="shape_packing_hall",
            schema_version=1,
            semantic_fingerprint=shape_packing_hall_semantic_fingerprint_v1(
                parameters=parameters,
                model_scope=model_scope,
                snapshot=snapshot,
            ),
            model_scope=model_scope,
            operation="shape_packing_hall_le",
            parameters=parameters,
        )

    def validate_plan(
        self,
        plan: ConstraintPlan,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> None:
        if type(plan) is not ConstraintPlan or type(proof) is not ShapePackingHallProof:
            raise TypeError("F6 plan validator requires ConstraintPlan/ShapePackingHallProof")
        expected_body = _body_from_proof(proof)
        expected_ghost_digest = _platform._snapshot_ghost_rect_digest(  # noqa: SLF001
            snapshot
        )
        if expected_ghost_digest is None:
            raise SemanticCutRejection("plan", "F6 plan cannot bind a snapshot without a ghost")
        expected_parameters = {
            "capacity": expected_body.capacity,
            "group_id": expected_body.group_id,
            "region_kind": expected_body.region_kind,
        }
        if plan.family != "shape_packing_hall" or plan.schema_version != 1 or plan.operation != "shape_packing_hall_le":
            raise SemanticCutRejection("plan", "F6 plan family/schema/operation differs from the compiler contract")
        if dict(plan.parameters) != expected_parameters:
            raise SemanticCutRejection("plan", "F6 plan parameters differ from the frozen proof")
        if plan.model_scope.ghost_policy != "bound" or plan.model_scope.ghost_rect_digest != expected_ghost_digest:
            raise SemanticCutRejection("plan", "F6 plan ghost scope differs from the frozen proof/snapshot")
        expected_domain = shape_packing_hall_master_domain_projection_v1(
            snapshot,
            expected_body.group_id,
        )
        if plan.model_scope.domain_fingerprint != expected_domain:
            raise SemanticCutRejection("plan", "F6 plan master-domain projection is stale")
        expected_semantic_fingerprint = shape_packing_hall_semantic_fingerprint_v1(
            parameters=expected_parameters,
            model_scope=plan.model_scope,
            snapshot=snapshot,
        )
        if plan.semantic_fingerprint != expected_semantic_fingerprint:
            raise SemanticCutRejection("plan", "F6 plan semantic fingerprint is stale")


__all__ = [
    "SHAPE_PACKING_HALL_COMPILER_VERSION",
    "SHAPE_PACKING_HALL_VALIDATOR_VERSION",
    "ShapePackingHallBody",
    "ShapePackingHallPlugin",
    "ShapePackingHallProof",
    "shape_packing_hall_master_domain_projection_v1",
    "shape_packing_hall_semantic_fingerprint_v1",
]
