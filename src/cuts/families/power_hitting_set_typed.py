"""Stage-B typed F7 power-cover proof, validator, and compiler.

The legacy F7 path remains the production authority until the Stage-B wiring
cut-over.  This module reproduces its complete empty-CoverSet obligations from
one deeply frozen :class:`ValidatedStateSnapshot` and emits a
``power_pose_exclusion`` plan.  F7 is unconditionally ghost-bound.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Final, cast

from src.cuts import typed_platform as _platform
from src.cuts.helpers.power_cover import compute_cover_set
from src.cuts.state_snapshot import F7PowerInputs, ValidatedStateSnapshot
from src.cuts.typed_platform import (
    ConstraintPlan,
    FrozenFamilyProof,
    ModelScope,
    SemanticCutRejection,
)


Cell = tuple[int, int]

POWER_HITTING_SET_VALIDATOR_VERSION: Final = "stage-b-f7-validator-v1"
POWER_HITTING_SET_COMPILER_VERSION: Final = "stage-b-f7-compiler-v1"

_GRID_SIZE: Final = 70
_POLE_SIZE: Final = 2
_POLE_SHAPE_CANONICAL: Final = "2x2_rigid"
_SEMANTIC_FINGERPRINT_PREFIX: Final = b"zmd.semantic-fingerprint.v1:"
_GRID_CELLS: Final = frozenset((x, y) for x in range(_GRID_SIZE) for y in range(_GRID_SIZE))


@dataclass(frozen=True, slots=True)
class PowerHittingSetProof(FrozenFamilyProof):
    """Immutable projection of the closed eight-field F7 certificate."""

    cert_kind: str
    facility_group: str
    facility_pose_id: str
    facility_cells: tuple[Cell, ...]
    pole_radius: float
    pole_shape_canonical: str
    ghost_rect_repr: tuple[int, int, int, int]
    exterior_blocks_digest: str


@dataclass(frozen=True, slots=True)
class PowerHittingSetBody:
    """Pure compiler input derived from one frozen F7 proof."""

    group_id: str
    pose_id: str


def _f7_inputs(snapshot: ValidatedStateSnapshot) -> F7PowerInputs:
    inputs = snapshot.family_inputs.get("power_hitting_set")
    if type(inputs) is not F7PowerInputs:
        raise TypeError("validated snapshot lacks exact F7PowerInputs")
    return inputs


def _proof_rejection(reason: str) -> SemanticCutRejection:
    return SemanticCutRejection("proof", reason)


def _require_non_empty_str(value: object, *, field_name: str) -> str:
    if type(value) is not str or not value:
        raise _proof_rejection(f"F7 {field_name} must be a non-empty exact str")
    return value


def _require_exact_int(value: object, *, field_name: str) -> int:
    if type(value) is not int:
        raise _proof_rejection(f"F7 {field_name} must be an exact int")
    return value


def _parse_pole_radius(value: object) -> float:
    # Legacy accepts both JSON ``5`` and ``5.0``.  Normalize only after the
    # exact-type check so bool and numeric subclasses cannot enter the proof.
    if type(value) not in (int, float):
        raise _proof_rejection("F7 pole_radius must be an exact int or float")
    try:
        radius = float(cast(int | float, value))
    except (OverflowError, ValueError) as exc:
        raise _proof_rejection("F7 pole_radius cannot be represented as a finite float") from exc
    if not math.isfinite(radius) or radius <= 0.0:
        raise _proof_rejection("F7 pole_radius must be finite and positive")
    return radius


def _parse_facility_cells(value: object) -> tuple[Cell, ...]:
    if type(value) is not list or not value:
        raise _proof_rejection("F7 facility_cells must be a non-empty exact list")
    cells: list[Cell] = []
    previous: Cell | None = None
    for index, raw_cell in enumerate(value):
        if type(raw_cell) is not list or len(raw_cell) != 2:
            raise _proof_rejection(f"F7 facility_cells[{index}] must be a two-item exact list")
        x = _require_exact_int(raw_cell[0], field_name=f"facility_cells[{index}][0]")
        y = _require_exact_int(raw_cell[1], field_name=f"facility_cells[{index}][1]")
        cell = (x, y)
        if not (0 <= x < _GRID_SIZE and 0 <= y < _GRID_SIZE):
            raise _proof_rejection(f"F7 facility_cells[{index}] is outside the 70-cell grid")
        if previous is not None and cell <= previous:
            raise _proof_rejection("F7 facility_cells must be strictly sorted and unique")
        previous = cell
        cells.append(cell)
    return tuple(cells)


def _parse_ghost_rect(value: object) -> tuple[int, int, int, int]:
    if type(value) is not list or len(value) != 4:
        raise _proof_rejection("F7 ghost_rect_repr must be an exact four-item list")
    parsed = tuple(_require_exact_int(item, field_name=f"ghost_rect_repr[{index}]") for index, item in enumerate(value))
    first, second, third, fourth = parsed
    return (first, second, third, fourth)


def _parse_power_hitting_set_proof(proof_payload: bytes) -> PowerHittingSetProof:
    proof = _platform._decode_proof_frame(  # noqa: SLF001 - shared Stage-B frame primitive
        proof_payload,
        expected_family="power_hitting_set",
        expected_schema_version=1,
    )
    expected_fields = frozenset(
        {
            "cert_kind",
            "exterior_blocks_digest",
            "facility_cells",
            "facility_group",
            "facility_pose_id",
            "ghost_rect_repr",
            "pole_radius",
            "pole_shape_canonical",
        }
    )
    if frozenset(proof) != expected_fields:
        raise _proof_rejection("F7 proof fields are not exact")
    if proof["cert_kind"] != "power_cover_emptyset_ghost":
        raise _proof_rejection("F7 cert_kind must be power_cover_emptyset_ghost")
    pole_shape = _require_non_empty_str(
        proof["pole_shape_canonical"],
        field_name="pole_shape_canonical",
    )
    if pole_shape != _POLE_SHAPE_CANONICAL:
        raise _proof_rejection("F7 pole_shape_canonical must be 2x2_rigid")
    return PowerHittingSetProof(
        family="power_hitting_set",
        schema_version=1,
        cert_kind="power_cover_emptyset_ghost",
        facility_group=_require_non_empty_str(
            proof["facility_group"],
            field_name="facility_group",
        ),
        facility_pose_id=_require_non_empty_str(
            proof["facility_pose_id"],
            field_name="facility_pose_id",
        ),
        facility_cells=_parse_facility_cells(proof["facility_cells"]),
        pole_radius=_parse_pole_radius(proof["pole_radius"]),
        pole_shape_canonical=pole_shape,
        ghost_rect_repr=_parse_ghost_rect(proof["ghost_rect_repr"]),
        exterior_blocks_digest=_require_non_empty_str(
            proof["exterior_blocks_digest"],
            field_name="exterior_blocks_digest",
        ),
    )


def _legacy_exterior_blocks_digest(snapshot: ValidatedStateSnapshot) -> str:
    payload = ";".join(f"{x},{y}" for x, y in sorted(snapshot.exterior_blocks)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _validate_group_and_pose(
    proof: PowerHittingSetProof,
    inputs: F7PowerInputs,
) -> None:
    pose_domain = inputs.group_pose_domains.get(proof.facility_group)
    if not isinstance(pose_domain, frozenset):
        raise _proof_rejection("F7 proof references an unknown facility_group")
    if proof.facility_pose_id not in pose_domain:
        raise _proof_rejection("F7 facility_pose_id is outside its group pose_domain")
    facility_type = inputs.group_to_facility_type.get(proof.facility_group)
    if type(facility_type) is not str:
        raise _proof_rejection("F7 facility_group has no facility-type binding")
    if inputs.template_needs_power.get(facility_type) is not True:
        raise _proof_rejection("F7 facility template does not require power")
    occupied = inputs.pose_occupied_cells.get((facility_type, proof.facility_pose_id))
    if not isinstance(occupied, frozenset):
        raise _proof_rejection("F7 facility pose has no occupied-cell registration")
    if proof.facility_cells != tuple(sorted(occupied)):
        raise _proof_rejection("F7 facility_cells differ from the snapshot pose registry")


def _validate_power_source_of_truth(
    proof: PowerHittingSetProof,
    inputs: F7PowerInputs,
) -> None:
    if inputs.pole_radius is None or inputs.pole_radius != proof.pole_radius:
        raise _proof_rejection("F7 pole_radius differs from the snapshot source of truth")
    if inputs.pole_dimensions != (_POLE_SIZE, _POLE_SIZE):
        raise _proof_rejection("F7 canonical power-pole dimensions must be 2x2")


def _validate_cover_sets(
    proof: PowerHittingSetProof,
    snapshot: ValidatedStateSnapshot,
    inputs: F7PowerInputs,
) -> None:
    facility_set = frozenset(proof.facility_cells)
    full_blocked = snapshot.ghost_cells | snapshot.exterior_blocks | frozenset(inputs.cell_owner) | facility_set
    full_free = _GRID_CELLS.difference(full_blocked)
    cover_full = compute_cover_set(
        proof.facility_cells,
        full_free,
        proof.pole_radius,
        grid_size=_GRID_SIZE,
        pole_size=_POLE_SIZE,
    )
    if cover_full:
        raise _proof_rejection("F7 full CoverSet recomputation is non-empty")

    ghost_only_blocked = snapshot.ghost_cells | snapshot.exterior_blocks | facility_set
    ghost_only_free = _GRID_CELLS.difference(ghost_only_blocked)
    cover_ghost_only = compute_cover_set(
        proof.facility_cells,
        ghost_only_free,
        proof.pole_radius,
        grid_size=_GRID_SIZE,
        pole_size=_POLE_SIZE,
    )
    if cover_ghost_only:
        raise _proof_rejection("F7 ghost-only CoverSet recomputation is non-empty; cell_owner is the true cause")


def _validate_power_hitting_set_proof(
    proof: PowerHittingSetProof,
    snapshot: ValidatedStateSnapshot,
) -> None:
    inputs = _f7_inputs(snapshot)
    if inputs.ghost is None or snapshot.ghost is None:
        raise _proof_rejection("F7 requires a ghost-bound snapshot")
    if inputs.ghost is not snapshot.ghost and inputs.ghost != snapshot.ghost:
        raise TypeError("F7PowerInputs ghost projection differs from the public snapshot ghost")
    if inputs.cell_owner is not snapshot.cell_owner and inputs.cell_owner != snapshot.cell_owner:
        raise TypeError("F7PowerInputs cell_owner projection differs from the public snapshot cell_owner")
    if proof.ghost_rect_repr != snapshot.ghost.as_tuple():
        raise _proof_rejection("F7 ghost_rect_repr differs from the snapshot")
    if proof.exterior_blocks_digest != _legacy_exterior_blocks_digest(snapshot):
        raise _proof_rejection("F7 exterior_blocks_digest differs from the snapshot recomputation")

    _validate_group_and_pose(proof, inputs)
    _validate_power_source_of_truth(proof, inputs)
    _validate_cover_sets(proof, snapshot, inputs)


def _body_from_proof(proof: PowerHittingSetProof) -> PowerHittingSetBody:
    return PowerHittingSetBody(
        group_id=proof.facility_group,
        pose_id=proof.facility_pose_id,
    )


def power_hitting_set_master_domain_projection_v1(
    snapshot: ValidatedStateSnapshot,
    group_id: str,
    pose_id: str,
) -> str:
    """Return the builder-captured F7 side of MasterDomainProjectionV1."""

    if type(snapshot) is not ValidatedStateSnapshot:
        raise TypeError("F7 MasterDomainProjectionV1 requires ValidatedStateSnapshot")
    if type(group_id) is not str or not group_id:
        raise TypeError("F7 MasterDomainProjectionV1 group_id must be a non-empty exact str")
    if type(pose_id) is not str or not pose_id:
        raise TypeError("F7 MasterDomainProjectionV1 pose_id must be a non-empty exact str")
    inputs = _f7_inputs(snapshot)
    pose_domain = inputs.group_pose_domains.get(group_id)
    facility_type = inputs.group_to_facility_type.get(group_id)
    if (
        not isinstance(pose_domain, frozenset)
        or pose_id not in pose_domain
        or type(facility_type) is not str
        or (facility_type, pose_id) not in inputs.pose_occupied_cells
    ):
        raise TypeError("validated F7 inputs lack the projected facility pose")
    return snapshot.power_hitting_set_master_domain_projection


def power_hitting_set_semantic_fingerprint_v1(
    *,
    parameters: dict[str, object],
    model_scope: ModelScope,
    snapshot: ValidatedStateSnapshot,
) -> str:
    """Return the content identity of the B4 F7 lowering semantics."""

    projection = {
        "compiler_version": POWER_HITTING_SET_COMPILER_VERSION,
        "family": "power_hitting_set",
        "model_scope": {
            "domain_fingerprint": model_scope.domain_fingerprint,
            "ghost_policy": model_scope.ghost_policy,
            "ghost_rect_digest": model_scope.ghost_rect_digest,
        },
        "operation": "power_pose_exclusion",
        "parameters": parameters,
        "parameter_schema": {
            "blocked_cells_digest": "lowercase-sha256",
            "group_id": "non-empty-str",
            "pose_id": "non-empty-str",
        },
        "schema_version": 1,
        "snapshot_artifact_identities": dict(sorted(snapshot.artifact_hashes.items())),
        "snapshot_source_digest": snapshot.source_digest,
    }
    return _platform._domain_digest(  # noqa: SLF001 - shared canonical digest primitive
        _SEMANTIC_FINGERPRINT_PREFIX,
        _platform._canonical_node(projection),  # noqa: SLF001 - shared canonical digest primitive
    )


class PowerHittingSetPlugin:
    """Complete B4 typed F7 parser/validator/compiler chain."""

    def parse_and_validate_proof(
        self,
        proof_payload: bytes,
        snapshot: ValidatedStateSnapshot,
    ) -> PowerHittingSetProof:
        try:
            proof = _parse_power_hitting_set_proof(proof_payload)
        except SemanticCutRejection:
            raise
        except ValueError as exc:
            raise _proof_rejection(str(exc) or type(exc).__name__) from exc
        _validate_power_hitting_set_proof(proof, snapshot)
        return proof

    def derive_body(self, proof: FrozenFamilyProof) -> PowerHittingSetBody:
        if type(proof) is not PowerHittingSetProof:
            raise TypeError("F7 derive_body requires PowerHittingSetProof")
        return _body_from_proof(proof)

    def compile(
        self,
        body: object,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> ConstraintPlan:
        if type(body) is not PowerHittingSetBody or type(proof) is not PowerHittingSetProof:
            raise TypeError("F7 compiler requires PowerHittingSetBody/PowerHittingSetProof")
        if body != _body_from_proof(proof):
            raise TypeError("F7 body is not the pure projection of its proof")
        ghost_rect_digest = _platform._snapshot_ghost_rect_digest(  # noqa: SLF001 - shared identity primitive
            snapshot
        )
        if ghost_rect_digest is None:
            raise TypeError("F7 compiler requires a ghost-bound snapshot")
        model_scope = ModelScope(
            ghost_policy="bound",
            ghost_rect_digest=ghost_rect_digest,
            domain_fingerprint=power_hitting_set_master_domain_projection_v1(
                snapshot,
                body.group_id,
                body.pose_id,
            ),
        )
        parameters: dict[str, object] = {
            "blocked_cells_digest": snapshot.blocked_cells_digest,
            "group_id": body.group_id,
            "pose_id": body.pose_id,
        }
        return ConstraintPlan(
            family="power_hitting_set",
            schema_version=1,
            semantic_fingerprint=power_hitting_set_semantic_fingerprint_v1(
                parameters=parameters,
                model_scope=model_scope,
                snapshot=snapshot,
            ),
            model_scope=model_scope,
            operation="power_pose_exclusion",
            parameters=parameters,
        )

    def validate_plan(
        self,
        plan: ConstraintPlan,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> None:
        if type(plan) is not ConstraintPlan or type(proof) is not PowerHittingSetProof:
            raise TypeError("F7 plan validator requires ConstraintPlan/PowerHittingSetProof")
        expected_body = _body_from_proof(proof)
        expected_ghost_digest = _platform._snapshot_ghost_rect_digest(  # noqa: SLF001
            snapshot
        )
        if expected_ghost_digest is None:
            raise SemanticCutRejection("plan", "F7 plan cannot bind a snapshot without a ghost")
        expected_parameters: dict[str, object] = {
            "blocked_cells_digest": snapshot.blocked_cells_digest,
            "group_id": expected_body.group_id,
            "pose_id": expected_body.pose_id,
        }
        if plan.family != "power_hitting_set" or plan.schema_version != 1 or plan.operation != "power_pose_exclusion":
            raise SemanticCutRejection("plan", "F7 plan family/schema/operation differs from the compiler contract")
        if dict(plan.parameters) != expected_parameters:
            raise SemanticCutRejection("plan", "F7 plan parameters differ from the frozen proof/snapshot")
        if plan.model_scope.ghost_policy != "bound" or plan.model_scope.ghost_rect_digest != expected_ghost_digest:
            raise SemanticCutRejection("plan", "F7 plan ghost scope differs from the frozen proof/snapshot")
        expected_domain = power_hitting_set_master_domain_projection_v1(
            snapshot,
            expected_body.group_id,
            expected_body.pose_id,
        )
        if plan.model_scope.domain_fingerprint != expected_domain:
            raise SemanticCutRejection("plan", "F7 plan master-domain projection is stale")
        expected_semantic_fingerprint = power_hitting_set_semantic_fingerprint_v1(
            parameters=expected_parameters,
            model_scope=plan.model_scope,
            snapshot=snapshot,
        )
        if plan.semantic_fingerprint != expected_semantic_fingerprint:
            raise SemanticCutRejection("plan", "F7 plan semantic fingerprint is stale")


__all__ = [
    "POWER_HITTING_SET_COMPILER_VERSION",
    "POWER_HITTING_SET_VALIDATOR_VERSION",
    "PowerHittingSetBody",
    "PowerHittingSetPlugin",
    "PowerHittingSetProof",
    "power_hitting_set_master_domain_projection_v1",
    "power_hitting_set_semantic_fingerprint_v1",
]
