"""Unit contracts for the RFC-001 Stage-B typed platform layer."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import weakref
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, get_type_hints

import pytest

from src.cuts import typed_platform as typed_platform_module
from src.cuts.frozen_artifacts import build_frozen_artifact_bundle
from src.cuts.families.pattern_nogood import validate_pattern_nogood
from src.cuts.lifecycle import (
    GHOST_AGNOSTIC,
    AnonymousSlotRef,
    BState,
    Cut,
    CutLiteral,
    CutScope,
    GroupState,
    OracleCert,
    _encode_region_bitset,
    canonical_bytes_for_cert,
    capture_scope_identity_preimage_v1,
    compute_blocked_cells_hash,
    compute_exterior_blocks_hash,
    compute_ghost_rect_id,
    compute_source_digest,
)
from src.cuts.state_snapshot import (
    ValidatedStateSnapshot,
    build_validated_state_snapshot,
)
from src.cuts.replay import LEGACY_DIAGNOSTIC_VALIDATORS, TYPED_REPLAY_FAMILIES
from src.cuts.oracles.pattern_nogood_oracle import (
    clear_sub_problem_oracle_registry,
    register_sub_problem_oracle,
)
from src.cuts.typed_platform import (
    CapabilityStage,
    CompiledCut,
    ConstraintPlan,
    CutEnvelope,
    CutProvenance,
    CutRejection,
    DependencyHash,
    ExecutionPath,
    FamilyCapability,
    FamilyCapabilityRegistry,
    FamilyPlugin,
    FrozenFamilyProof,
    ModelScope,
    ModelScopeBinding,
    ScopeAssumption,
    ScopeManifest,
    SemanticCutRejection,
    ShadowValidated,
    SUPPORTED_OPERATIONS,
    build_production_registry,
    cut_to_envelope_v1,
    validate_and_compile_cut,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
TESTS_ROOT = SRC_ROOT / "tests"
TYPED_PLATFORM_PATH = REPO_ROOT / "src" / "cuts" / "typed_platform.py"

_PROOF_FRAME_PREFIX = b"zmd.proof.v1:"
_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64
_ARTIFACT_HASHES = {
    "candidate_placements.json": _SHA_B,
    "canonical_rules.json": _SHA_A,
    "mandatory_exact_instances.json": _SHA_C,
}
_MISSING_OPTIONAL_ARTIFACT = "__MISSING_OPTIONAL_EXACT_ARTIFACT__"
_PRODUCTION_ARTIFACT_HASHES = {
    "candidate_placements": _SHA_B,
    "canonical_rules": _SHA_A,
    "certified_exact_source_tree": "d" * 64,
    "commodity_demands": _MISSING_OPTIONAL_ARTIFACT,
    "generic_io_requirements": "e" * 64,
    "mandatory_exact_instances": _SHA_C,
    "orbit_homogeneity_digest": "f" * 64,
    "preprocess_plan": _MISSING_OPTIONAL_ARTIFACT,
}

_EXPECTED_FAMILIES = {
    "component_reach",
    "cutset",
    "density_envelope",
    "pattern_nogood",
    "port_exposure",
    "power_grid_reach",
    "power_hitting_set",
    "region_capacity",
    "shape_packing_hall",
}
_EXPECTED_MODES = {
    "component_reach": "geometric",
    "cutset": "geometric",
    "density_envelope": "geometric",
    "pattern_nogood": "literal",
    "port_exposure": "literal",
    "power_grid_reach": "geometric",
    "power_hitting_set": "literal",
    "region_capacity": "geometric",
    "shape_packing_hall": "geometric",
}
_EXPECTED_STAGES = {
    "component_reach": CapabilityStage.VALIDATED,
    "cutset": CapabilityStage.VALIDATED,
    "density_envelope": CapabilityStage.VALIDATED,
    "pattern_nogood": CapabilityStage.VALIDATED,
    "port_exposure": CapabilityStage.VALIDATED,
    "power_grid_reach": CapabilityStage.RETIRED,
    "power_hitting_set": CapabilityStage.COMPILABLE,
    "region_capacity": CapabilityStage.COMPILABLE,
    "shape_packing_hall": CapabilityStage.COMPILABLE,
}
_EXPECTED_PATHS = {
    "component_reach": ExecutionPath.LEGACY_DIAGNOSTIC,
    "cutset": ExecutionPath.LEGACY_DIAGNOSTIC,
    "density_envelope": ExecutionPath.LEGACY_DIAGNOSTIC,
    "pattern_nogood": ExecutionPath.TYPED,
    "port_exposure": ExecutionPath.LEGACY_DIAGNOSTIC,
    "power_grid_reach": ExecutionPath.LEGACY_DIAGNOSTIC,
    "power_hitting_set": ExecutionPath.TYPED,
    "region_capacity": ExecutionPath.TYPED,
    "shape_packing_hall": ExecutionPath.TYPED,
}


def _assert_sha256(value: str) -> None:
    assert len(value) == 64
    assert value == value.lower()
    int(value, 16)


def _build_world(
    *,
    artifact_hashes: dict[str, str] | None = None,
    oracle_capabilities: frozenset[str] | None = None,
) -> tuple[BState, ValidatedStateSnapshot]:
    selected_hashes = _ARTIFACT_HASHES if artifact_hashes is None else artifact_hashes
    facility_templates = {
        "test_machine": {
            "placement_rule": "free",
            "dimensions": {"w": 1, "h": 1},
            "needs_power": False,
        }
    }
    canonical_rules = {
        "globals": {"grid": {"width": 70, "height": 70}},
        "facility_templates": facility_templates,
    }
    candidate_placements = {
        "facility_pools": {
            "test_machine": [
                {
                    "pose_id": "pA",
                    "anchor": {"x": 1, "y": 1},
                    "occupied_cells": [[1, 1]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                },
                {
                    "pose_id": "pB",
                    "anchor": {"x": 2, "y": 1},
                    "occupied_cells": [[2, 1]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                },
            ]
        }
    }
    instance_to_facility_type = {"g1": "test_machine"}
    ghost_rect = (11, 17, 2, 3)
    ghost_cells = frozenset(
        (x, y)
        for x in range(ghost_rect[0], ghost_rect[0] + ghost_rect[2])
        for y in range(ghost_rect[1], ghost_rect[1] + ghost_rect[3])
    )
    state = BState(
        groups={
            "g1": GroupState(
                group_id="g1",
                demand=1,
                pose_domain=frozenset({"pA", "pB"}),
                selected_poses=[],
            )
        },
        ghost_rect=ghost_rect,
        ghost_cells=ghost_cells,
        exterior_blocks=frozenset({(7, 0)}),
        artifact_hashes=dict(selected_hashes),
        available_oracle_versions=(
            frozenset({"binding_empty_domain_v1", "region_capacity_v1"})
            if oracle_capabilities is None
            else oracle_capabilities
        ),
        canonical_rules=canonical_rules,
        candidate_placements=candidate_placements,
        facility_templates=facility_templates,
        instance_to_facility_type=instance_to_facility_type,
    )
    state.source_digest = compute_source_digest(state)
    bundle = build_frozen_artifact_bundle(
        canonical_rules=canonical_rules,
        candidate_placements=candidate_placements,
        facility_templates=facility_templates,
        instance_to_facility_type=instance_to_facility_type,
        artifact_hashes=selected_hashes,
    )
    return state, build_validated_state_snapshot(state, bundle)


def _pick_f5_verifiable_op() -> tuple[str, str]:
    """A real exact-binding operation (no generic hub slots) with >=1 required
    port slot, so a zero-port pose has a genuinely empty binding domain that the
    independent verifier can re-derive from the frozen profile."""
    from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES

    for op, profile in sorted(OPERATION_PORT_PROFILES.items()):
        if profile.generic_input_slots or profile.generic_output_slots:
            continue
        if sum(profile.input_slots.values()) + sum(profile.output_slots.values()) > 0:
            return op, profile.facility_type
    raise AssertionError("no exact-binding operation with port slots in profiles")


def _f5_dead_pose() -> dict[str, Any]:
    return {
        "pose_id": "p_dead",
        "anchor": {"x": 1, "y": 1},
        "occupied_cells": [[1, 1]],
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": None,
    }


def _f5_live_pose(op: str) -> dict[str, Any]:
    from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES

    profile = OPERATION_PORT_PROFILES[op]
    n_in = sum(profile.input_slots.values())
    n_out = sum(profile.output_slots.values())
    return {
        "pose_id": "p_live",
        "anchor": {"x": 3, "y": 1},
        "occupied_cells": [[3, 1]],
        "input_port_cells": [{"x": i, "y": 0, "dir": "N"} for i in range(n_in)],
        "output_port_cells": [{"x": i, "y": 9, "dir": "S"} for i in range(n_out)],
        "power_coverage_cells": None,
    }


def _build_f5_verifiable_world(
    *,
    artifact_hashes: dict[str, str] | None = None,
) -> tuple[BState, ValidatedStateSnapshot, str]:
    """A production-shaped F5 world: a real ``group::{facility}::{op}::0`` group
    whose ``p_dead`` pose has an empty binding domain the RFC-002 verifier can
    independently confirm (unlike the synthetic ``g1``/``test_machine`` world)."""
    op, facility_type = _pick_f5_verifiable_op()
    group_id = f"group::{facility_type}::{op}::0"
    selected_hashes = _ARTIFACT_HASHES if artifact_hashes is None else artifact_hashes
    facility_templates = {
        facility_type: {
            "placement_rule": "free",
            "dimensions": {"w": 1, "h": 1},
            "needs_power": False,
        }
    }
    canonical_rules = {
        "globals": {"grid": {"width": 70, "height": 70}},
        "facility_templates": facility_templates,
    }
    candidate_placements = {"facility_pools": {facility_type: [_f5_dead_pose(), _f5_live_pose(op)]}}
    instance_to_facility_type = {group_id: facility_type}
    ghost_rect = (11, 17, 2, 3)
    ghost_cells = frozenset(
        (x, y)
        for x in range(ghost_rect[0], ghost_rect[0] + ghost_rect[2])
        for y in range(ghost_rect[1], ghost_rect[1] + ghost_rect[3])
    )
    state = BState(
        groups={
            group_id: GroupState(
                group_id=group_id,
                demand=1,
                pose_domain=frozenset({"p_dead", "p_live"}),
                selected_poses=[],
            )
        },
        ghost_rect=ghost_rect,
        ghost_cells=ghost_cells,
        exterior_blocks=frozenset({(7, 0)}),
        artifact_hashes=dict(selected_hashes),
        available_oracle_versions=frozenset({"binding_empty_domain_v1", "region_capacity_v1"}),
        canonical_rules=canonical_rules,
        candidate_placements=candidate_placements,
        facility_templates=facility_templates,
        instance_to_facility_type=instance_to_facility_type,
    )
    state.source_digest = compute_source_digest(state)
    bundle = build_frozen_artifact_bundle(
        canonical_rules=canonical_rules,
        candidate_placements=candidate_placements,
        facility_templates=facility_templates,
        instance_to_facility_type=instance_to_facility_type,
        artifact_hashes=selected_hashes,
    )
    return state, build_validated_state_snapshot(state, bundle), group_id


def _make_verifiable_pattern_cut(
    state: BState,
    group_id: str,
    *,
    pose_id: str = "p_dead",
    oracle_name: str = "binding_empty_domain_v1",
    oracle_version: str = "v1.0",
    with_identity_preimage: bool = False,
) -> Cut:
    proof = canonical_bytes_for_cert(
        {
            "cert_kind": "bounded_deletion_core",
            "sub_problem_oracle_name": oracle_name,
            "sub_problem_oracle_version": oracle_version,
            "forbidden_pose_pattern": [[group_id, 0, pose_id]],
            "core_minimization": {
                "size_before": 1,
                "size_after": 1,
                "calls": 1,
                "stopped_reason": "INFEASIBLE_VERIFIED",
                "is_verified_infeasible": True,
            },
        }
    )
    proof_hash = hashlib.sha256(proof).hexdigest()
    scope = _scope(state, ghost_bound=True)
    if with_identity_preimage:
        # A raw scope preimage lets the cut pass the production cut_to_envelope_v1
        # adapter, so the full orchestration (not just _trusted_test_envelope)
        # can carry it into the shadow bucket.
        scope = CutScope(
            ghost_rect_id=scope.ghost_rect_id,
            blocked_cells_hash=scope.blocked_cells_hash,
            exterior_blocks_hash=scope.exterior_blocks_hash,
            source_digest=scope.source_digest,
            artifact_hashes=dict(scope.artifact_hashes),
            oracle_abstraction_version=scope.oracle_abstraction_version,
            identity_preimage=capture_scope_identity_preimage_v1(state),
        )
    return Cut(
        cut_id="b15-pattern-verifiable",
        family="pattern_nogood",
        literals=(
            CutLiteral(
                slot_ref=AnonymousSlotRef(group_id=group_id, slot_index=0),
                pose_id=pose_id,
            ),
        ),
        scope=scope,
        cert=OracleCert(
            cert_kind="bounded_deletion_core",
            cert_payload=proof,
            cert_hash=proof_hash,
        ),
        family_version="v1",
        validator_version="pattern-nogood-v1",
        payload_schema_version=1,
        oracle_name="pattern_nogood_v1",
        oracle_cert_hash=proof_hash,
    )


def _scope(state: BState, *, ghost_bound: bool) -> CutScope:
    assert state.source_digest is not None
    return CutScope(
        ghost_rect_id=(compute_ghost_rect_id(state.ghost_rect) if ghost_bound else GHOST_AGNOSTIC),
        blocked_cells_hash=compute_blocked_cells_hash(state),
        exterior_blocks_hash=compute_exterior_blocks_hash(state),
        source_digest=state.source_digest,
        artifact_hashes=dict(state.artifact_hashes),
        oracle_abstraction_version=("binding_empty_domain_v1" if ghost_bound else "region_capacity_v1"),
    )


def _probe_payload(*, family: str) -> bytes:
    if family == "cutset":
        return canonical_bytes_for_cert(
            {
                "cert_kind": "menger_min_cut",
                "side_a_bitset_b64": _encode_region_bitset([(0, 0)], grid_size=70),
                "side_b_bitset_b64": _encode_region_bitset([(0, 1)], grid_size=70),
                "cut_edges": [[[0, 0], [0, 1]]],
                "cut_size": 1,
                "commodity_demand": 1,
                "contributing_commodities": ["probe"],
            }
        )
    if family == "shape_packing_hall":
        return canonical_bytes_for_cert(
            {
                "cert_kind": "hall_interval_witness",
                "region_kind": "left_baseline",
                "region_total_length": 70,
                "partition_lens": [70],
                "partition_offsets": [0],
                "pose_length": 2,
                "pose_shape_canonical": "1x2_rigid",
                "max_packable": [35],
                "total_packable": 35,
                "contributing_group": "g1",
                "region_demand": 36,
                "group_demand": 36,
                "ghost_rect_repr": [11, 17, 2, 3],
                "exterior_blocks_digest": "probe-exterior",
            }
        )
    raise AssertionError(f"unsupported probe family {family!r}")


def _make_region_cut(
    state: BState,
    *,
    geometric_payload: bytes | None = None,
    cert_payload: bytes | None = None,
    ghost_bound: bool = False,
    family: str = "cutset",
) -> Cut:
    # Default rejection fixtures use permanent legacy-diagnostic F2. Tests that
    # intentionally exercise the complete typed plugin protocol must opt in to
    # a typed family explicitly, so later family migrations cannot change the
    # rejection arm by accident.
    body = _probe_payload(family=family) if geometric_payload is None else geometric_payload
    proof = body if cert_payload is None else cert_payload
    proof_hash = hashlib.sha256(proof).hexdigest()
    cert_kind = "menger_min_cut" if family == "cutset" else "hall_interval_witness"
    return Cut(
        cut_id="b15-region",
        family=family,
        geometric_payload=body,
        scope=_scope(state, ghost_bound=ghost_bound),
        cert=OracleCert(
            cert_kind=cert_kind,
            cert_payload=proof,
            cert_hash=proof_hash,
        ),
        family_version="v1",
        validator_version="region-capacity-v1",
        payload_schema_version=1,
        oracle_name="region_capacity_v1",
        oracle_cert_hash=proof_hash,
    )


def _pattern_payload(
    *,
    oracle_name: str = "binding_empty_domain_v1",
    oracle_version: str = "v1.0",
) -> bytes:
    return canonical_bytes_for_cert(
        {
            "cert_kind": "bounded_deletion_core",
            "sub_problem_oracle_name": oracle_name,
            "sub_problem_oracle_version": oracle_version,
            "forbidden_pose_pattern": [["g1", 0, "pA"]],
            "core_minimization": {
                "size_before": 1,
                "size_after": 1,
                "calls": 1,
                "stopped_reason": "INFEASIBLE_VERIFIED",
                "is_verified_infeasible": True,
            },
        }
    )


def _make_pattern_cut(
    state: BState,
    *,
    pose_id: str = "pA",
    oracle_name: str = "binding_empty_domain_v1",
    oracle_version: str = "v1.0",
) -> Cut:
    proof = _pattern_payload(
        oracle_name=oracle_name,
        oracle_version=oracle_version,
    )
    proof_hash = hashlib.sha256(proof).hexdigest()
    return Cut(
        cut_id="b15-pattern",
        family="pattern_nogood",
        literals=(
            CutLiteral(
                slot_ref=AnonymousSlotRef(group_id="g1", slot_index=0),
                pose_id=pose_id,
            ),
        ),
        scope=_scope(state, ghost_bound=True),
        cert=OracleCert(
            cert_kind="bounded_deletion_core",
            cert_payload=proof,
            cert_hash=proof_hash,
        ),
        family_version="v1",
        validator_version="pattern-nogood-v1",
        payload_schema_version=1,
        oracle_name="pattern_nogood_v1",
        oracle_cert_hash=proof_hash,
    )


@dataclass(frozen=True)
class _ProbeProof(FrozenFamilyProof):
    group_id: str = "g1"


@dataclass(frozen=True)
class _ProbeBody:
    group_id: str = "g1"


class _OrderedPlugin:
    def __init__(self, plan: ConstraintPlan, *, proof: FrozenFamilyProof | None = None) -> None:
        self.events: list[tuple[str, tuple[object, ...]]] = []
        self.proof = _ProbeProof(family=plan.family, schema_version=plan.schema_version) if proof is None else proof
        self.body = _ProbeBody()
        self.plan = plan

    def parse_and_validate_proof(
        self,
        proof_payload: bytes,
        snapshot: ValidatedStateSnapshot,
    ) -> FrozenFamilyProof:
        self.events.append(("parse_and_validate_proof", (proof_payload, snapshot)))
        return self.proof

    def derive_body(self, proof: FrozenFamilyProof) -> _ProbeBody:
        assert proof is self.proof
        self.events.append(("derive_body", (proof,)))
        return self.body

    def compile(
        self,
        body: object,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> ConstraintPlan:
        assert body is self.body
        assert proof is self.proof
        self.events.append(("compile", (body, proof, snapshot)))
        return self.plan

    def validate_plan(
        self,
        plan: ConstraintPlan,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> None:
        assert plan is self.plan
        assert proof is self.proof
        self.events.append(("validate_plan", (plan, proof, snapshot)))


def _plan(
    *,
    operation: str = "shape_packing_hall_le",
    family: str = "cutset",
    ghost_policy: str = "agnostic",
    ghost_rect_digest: str | None = None,
    domain_fingerprint: str = "probe-domain-fingerprint",
    hall_region_kind: object = "left_baseline",
) -> ConstraintPlan:
    parameters_by_operation: dict[str, dict[str, object]] = {
        "power_pose_exclusion": {
            "blocked_cells_digest": "7" * 64,
            "group_id": "g1",
            "pose_id": "pA",
        },
        "region_capacity_le": {
            "capacity": 1,
            "group_cell_weights": {"g1": 1},
        },
        "shape_packing_hall_le": {
            "capacity": 1,
            "group_id": "g1",
            "region_kind": hall_region_kind,
        },
    }
    return ConstraintPlan(
        family=family,
        schema_version=1,
        semantic_fingerprint="5" * 64,
        model_scope=ModelScope(
            ghost_policy=ghost_policy,  # type: ignore[arg-type]
            ghost_rect_digest=ghost_rect_digest,
            domain_fingerprint=domain_fingerprint,
        ),
        operation=operation,
        parameters=parameters_by_operation.get(
            operation,
            {"capacity": 1, "group_cell_weights": {"g1": 1}},
        ),
    )


def _capability(
    *,
    family: str = "cutset",
    mode: str = "geometric",
    stage: CapabilityStage = CapabilityStage.VALIDATED,
    execution_path: ExecutionPath = ExecutionPath.LEGACY_DIAGNOSTIC,
    compiler_version: str | None = None,
) -> FamilyCapability:
    return FamilyCapability(
        name=family,
        mode=mode,
        proof_schema_version=1,
        validator_version="b15-probe-v1",
        compiler_version=compiler_version,
        stage=stage,
        required_dependencies=frozenset(_ARTIFACT_HASHES),
        execution_path=execution_path,
    )


def _registry(
    plugin: object | None,
    *,
    capability: FamilyCapability | None = None,
) -> FamilyCapabilityRegistry:
    selected = _capability() if capability is None else capability
    return FamilyCapabilityRegistry(
        capabilities={selected.name: selected},
        plugins={} if plugin is None else {selected.name: plugin},
    )


def _typed_probe_cut(
    state: BState,
    *,
    geometric_payload: bytes | None = None,
    cert_payload: bytes | None = None,
    ghost_bound: bool = False,
) -> Cut:
    return _make_region_cut(
        state,
        geometric_payload=geometric_payload,
        cert_payload=cert_payload,
        ghost_bound=ghost_bound,
        family="shape_packing_hall",
    )


def _typed_probe_plan(
    *,
    operation: str = "shape_packing_hall_le",
    ghost_policy: str = "agnostic",
    ghost_rect_digest: str | None = None,
    domain_fingerprint: str = "probe-domain-fingerprint",
    hall_region_kind: object = "left_baseline",
) -> ConstraintPlan:
    return _plan(
        family="shape_packing_hall",
        operation=operation,
        ghost_policy=ghost_policy,
        ghost_rect_digest=ghost_rect_digest,
        domain_fingerprint=domain_fingerprint,
        hall_region_kind=hall_region_kind,
    )


def _typed_probe_capability(
    *,
    mode: str = "geometric",
    stage: CapabilityStage = CapabilityStage.COMPILABLE,
    execution_path: ExecutionPath = ExecutionPath.TYPED,
    compiler_version: str | None = "b15-probe-v1",
) -> FamilyCapability:
    return _capability(
        family="shape_packing_hall",
        mode=mode,
        stage=stage,
        execution_path=execution_path,
        compiler_version=compiler_version,
    )


def _typed_probe_registry(plugin: object) -> FamilyCapabilityRegistry:
    return _registry(plugin, capability=_typed_probe_capability())


def _decode_proof_frame(envelope: CutEnvelope) -> dict[str, Any]:
    assert envelope.proof_payload.startswith(_PROOF_FRAME_PREFIX)
    decoded = json.loads(envelope.proof_payload.removeprefix(_PROOF_FRAME_PREFIX))
    assert type(decoded) is dict
    return decoded


def _trusted_test_envelope(
    raw_cut: Cut,
    snapshot: ValidatedStateSnapshot,
) -> CutEnvelope:
    """Build a full-scope test envelope without the legacy 16-hex adapter.

    ``CutScope`` currently has no raw ghost/cell preimage, so the production
    v1 adapter must reject it under §2.7.  Typed-pipeline tests bind their
    scope directly to the immutable snapshot instead.
    """

    assert raw_cut.cert is not None
    assert raw_cut.scope is not None
    proof = json.loads(raw_cut.cert.cert_payload)
    assert type(proof) is dict
    proof_payload = typed_platform_module._proof_frame(
        family=raw_cut.family,
        schema_version=1,
        proof=proof,
    )
    if raw_cut.scope.ghost_rect_id == GHOST_AGNOSTIC:
        ghost_policy = "agnostic"
        ghost_rect_digest = None
        blocked_cells_digest = None
    else:
        ghost_policy = "bound"
        ghost_rect_digest = typed_platform_module._snapshot_ghost_rect_digest(snapshot)
        assert ghost_rect_digest is not None
        blocked_cells_digest = snapshot.blocked_cells_digest
    scope = ScopeManifest(
        scope_schema_version=1,
        family=raw_cut.family,
        ghost_policy=ghost_policy,
        ghost_rect_digest=ghost_rect_digest,
        blocked_cells_digest=blocked_cells_digest,
        exterior_blocks_digest=snapshot.exterior_blocks_digest,
        source_digest=snapshot.source_digest,
        dependency_hashes=tuple(
            DependencyHash(
                name=name,
                digest=typed_platform_module._normalize_v1_artifact_identity(
                    name,
                    digest,
                ),
            )
            for name, digest in sorted(raw_cut.scope.artifact_hashes.items())
        ),
        oracle_abstraction_version=raw_cut.scope.oracle_abstraction_version,
        assumptions=tuple(ScopeAssumption(key=item.key, value=item.value) for item in raw_cut.scope.active_assumptions),
    )
    return CutEnvelope(
        cut_id=raw_cut.cut_id,
        family=raw_cut.family,
        family_schema_version=1,
        proof_payload=proof_payload,
        proof_hash=hashlib.sha256(proof_payload).hexdigest(),
        scope=scope,
        provenance=CutProvenance(
            family_version=raw_cut.family_version,
            validator_version=raw_cut.validator_version,
            oracle_name=raw_cut.oracle_name,
            oracle_cert_hash=raw_cut.oracle_cert_hash,
            created_at=raw_cut.created_at,
            iter_index=raw_cut.iter_index,
        ),
    )


def test_public_type_shapes_and_three_branch_result_algebra() -> None:
    expected_fields = {
        CutEnvelope: (
            "cut_id",
            "family",
            "family_schema_version",
            "proof_payload",
            "proof_hash",
            "scope",
            "provenance",
        ),
        ConstraintPlan: (
            "family",
            "schema_version",
            "semantic_fingerprint",
            "model_scope",
            "operation",
            "parameters",
            "digest",
        ),
        CompiledCut: (
            "cut_id",
            "proof_digest",
            "scope_digest",
            "snapshot_digest",
            "plan",
            "digest",
        ),
        ShadowValidated: (
            "cut_id",
            "proof_digest",
            "snapshot_digest",
            "telemetry_tag",
        ),
        CutRejection: ("stage", "reason", "cut_id"),
        ModelScopeBinding: (
            "rect_idx",
            "ghost_rect_digest",
            "condition_lits",
            "blocked_cells",
            "snapshot_digest",
            "master_domain_family",
            "master_domain_projection",
            "master_ref",
        ),
    }
    for type_, field_names in expected_fields.items():
        assert is_dataclass(type_)
        assert type_.__dataclass_params__.frozen  # type: ignore[attr-defined]
        assert tuple(field.name for field in fields(type_)) == field_names

    master_ref_field = next(field for field in fields(ModelScopeBinding) if field.name == "master_ref")
    assert not master_ref_field.repr
    assert not master_ref_field.compare

    state, snapshot = _build_world()
    region_envelope = _trusted_test_envelope(_typed_probe_cut(state), snapshot)
    plugin = _OrderedPlugin(_typed_probe_plan())
    compiled = validate_and_compile_cut(region_envelope, snapshot, _typed_probe_registry(plugin))

    pattern_envelope = _trusted_test_envelope(_make_pattern_cut(state), snapshot)
    shadow_plugin = _OrderedPlugin(_plan(family="pattern_nogood"))
    shadow_capability = _capability(
        family="pattern_nogood",
        mode="literal",
        stage=CapabilityStage.VALIDATED,
        execution_path=ExecutionPath.TYPED,
        compiler_version=None,
    )
    shadow = validate_and_compile_cut(
        pattern_envelope,
        snapshot,
        _registry(shadow_plugin, capability=shadow_capability),
    )

    rejection_state, rejection_snapshot = _build_world(
        artifact_hashes=_PRODUCTION_ARTIFACT_HASHES,
    )
    rejection_envelope = _trusted_test_envelope(
        _make_region_cut(rejection_state),
        rejection_snapshot,
    )
    rejected = validate_and_compile_cut(
        rejection_envelope,
        rejection_snapshot,
        build_production_registry(),
    )

    assert isinstance(compiled, CompiledCut)
    assert isinstance(shadow, ShadowValidated)
    assert isinstance(rejected, CutRejection)
    assert rejected.stage == "registry"
    assert rejected.reason == "legacy diagnostic family cannot enter typed dispatch"
    assert {type(compiled), type(shadow), type(rejected)} == {
        CompiledCut,
        ShadowValidated,
        CutRejection,
    }
    assert shadow_plugin.events[0][0] == "parse_and_validate_proof"
    assert all(event[0] not in {"compile", "validate_plan"} for event in shadow_plugin.events)


def test_single_entry_executes_steps_in_order_without_mutating_inputs() -> None:
    state, snapshot = _build_world()
    envelope = _trusted_test_envelope(_typed_probe_cut(state), snapshot)
    plan = _typed_probe_plan()
    plugin = _OrderedPlugin(plan)
    snapshot_digest_before = snapshot.digest
    envelope_proof_before = envelope.proof_payload
    plan_digest_before = plan.digest

    result = validate_and_compile_cut(envelope, snapshot, _typed_probe_registry(plugin))

    assert isinstance(result, CompiledCut)
    assert [name for name, _args in plugin.events] == [
        "parse_and_validate_proof",
        "derive_body",
        "compile",
        "validate_plan",
    ]
    assert plugin.events[0][1][1] is snapshot
    assert plugin.events[2][1][1] is plugin.proof
    assert plugin.events[2][1][2] is snapshot
    assert plugin.events[3][1][1] is plugin.proof
    assert plugin.events[3][1][2] is snapshot
    assert snapshot.digest == snapshot_digest_before
    assert envelope.proof_payload == envelope_proof_before
    assert plan.digest == plan_digest_before
    assert result.snapshot_digest == snapshot.digest
    for digest in (
        result.proof_digest,
        result.scope_digest,
        result.snapshot_digest,
        result.plan.digest,
        result.digest,
    ):
        _assert_sha256(digest)


@pytest.mark.parametrize(
    "operation",
    [
        "power_pose_exclusion",
        "region_capacity_le",
        "shape_packing_hall_le",
    ],
)
def test_constraint_plan_accepts_only_closed_operations(operation: str) -> None:
    assert _plan(operation=operation).operation == operation


@pytest.mark.parametrize("region_kind", ["left_baseline", "bottom_baseline"])
def test_shape_packing_hall_plan_accepts_closed_region_kinds(region_kind: str) -> None:
    assert _plan(hall_region_kind=region_kind).parameters["region_kind"] == region_kind


@pytest.mark.parametrize("region_kind", ["", "interior_rect", "left_or_bottom_union", 1, None])
def test_shape_packing_hall_plan_rejects_region_kind_outside_closed_set(region_kind: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        _plan(hall_region_kind=region_kind)


def test_model_scope_domain_fingerprint_is_nonempty_opaque_until_b3() -> None:
    scope = ModelScope(
        ghost_policy="agnostic",
        ghost_rect_digest=None,
        domain_fingerprint="opaque-projection-contract-pending-b3",
    )

    assert scope.domain_fingerprint == "opaque-projection-contract-pending-b3"
    with pytest.raises((TypeError, ValueError)):
        ModelScope(
            ghost_policy="agnostic",
            ghost_rect_digest=None,
            domain_fingerprint="",
        )


@pytest.mark.parametrize("mismatch", ["ghost-policy", "ghost-rect-digest"])
def test_compiler_plan_scope_drift_returns_rejection(mismatch: str) -> None:
    state, snapshot = _build_world()
    if mismatch == "ghost-policy":
        envelope = _trusted_test_envelope(_typed_probe_cut(state), snapshot)
        plan = _typed_probe_plan(
            ghost_policy="bound",
            ghost_rect_digest="8" * 64,
        )
        capability = _typed_probe_capability()
    else:
        envelope = _trusted_test_envelope(
            _typed_probe_cut(state, ghost_bound=True),
            snapshot,
        )
        plan = _typed_probe_plan(
            ghost_policy="bound",
            ghost_rect_digest="8" * 64,
        )
        capability = _typed_probe_capability()
    plugin = _OrderedPlugin(plan)

    result = validate_and_compile_cut(
        envelope,
        snapshot,
        _registry(plugin, capability=capability),
    )

    assert isinstance(result, CutRejection)
    assert [event for event, _args in plugin.events] == [
        "parse_and_validate_proof",
        "derive_body",
        "compile",
    ]


def test_compiler_plan_operation_must_match_envelope_family() -> None:
    state, snapshot = _build_world()
    envelope = _trusted_test_envelope(_typed_probe_cut(state), snapshot)
    plugin = _OrderedPlugin(_typed_probe_plan(operation="power_pose_exclusion"))

    result = validate_and_compile_cut(envelope, snapshot, _typed_probe_registry(plugin))

    assert isinstance(result, CutRejection)
    assert [event for event, _args in plugin.events] == [
        "parse_and_validate_proof",
        "derive_body",
        "compile",
    ]


@pytest.mark.parametrize(
    "operation",
    ["", "region_capacity", "raw_linear_constraint", "power_pose_exclusion_v2"],
)
def test_constraint_plan_rejects_unknown_operations(operation: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        _plan(operation=operation)


def _region_plan_with_parameters(parameters: Mapping[object, object]) -> ConstraintPlan:
    return ConstraintPlan(
        family="region_capacity",
        schema_version=1,
        semantic_fingerprint="5" * 64,
        model_scope=ModelScope(
            ghost_policy="agnostic",
            ghost_rect_digest=None,
            domain_fingerprint="probe-domain-fingerprint",
        ),
        operation="region_capacity_le",
        parameters=parameters,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("ambiguous_key", "exact_key"),
    [(1, "1"), (True, "true")],
    ids=("int-vs-str", "bool-vs-str"),
)
def test_plan_and_proof_digest_layers_reject_mapping_key_collisions(
    ambiguous_key: object,
    exact_key: str,
) -> None:
    valid_plan = _region_plan_with_parameters(
        {
            "capacity": 1,
            "group_cell_weights": {exact_key: 7},
        }
    )
    valid_frame = typed_platform_module._proof_frame(
        family="digest_probe",
        schema_version=1,
        proof={exact_key: 7},
    )

    _assert_sha256(valid_plan.digest)
    assert valid_frame.startswith(_PROOF_FRAME_PREFIX)
    with pytest.raises((TypeError, ValueError)):
        _region_plan_with_parameters(
            {
                "capacity": 1,
                "group_cell_weights": {ambiguous_key: 7},
            }
        )
    with pytest.raises((TypeError, ValueError)):
        typed_platform_module._proof_frame(
            family="digest_probe",
            schema_version=1,
            proof={ambiguous_key: 7},  # type: ignore[dict-item]
        )


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_plan_and_proof_digest_layers_reject_non_finite_numbers(
    bad_value: float,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        _region_plan_with_parameters(
            {
                "capacity": 1,
                "group_cell_weights": {"g1": bad_value},
            }
        )
    with pytest.raises((TypeError, ValueError)):
        typed_platform_module._proof_frame(
            family="digest_probe",
            schema_version=1,
            proof={"value": bad_value},
        )


class _PlanParametersMutatingDuringItems(dict[str, object]):
    def __init__(self) -> None:
        super().__init__(
            capacity=1,
            group_cell_weights={"g1": 1},
        )
        self.items_calls = 0

    def items(self) -> Iterator[tuple[str, object]]:  # type: ignore[override]
        self.items_calls += 1
        yield "capacity", self["capacity"]
        weights = self["group_cell_weights"]
        assert isinstance(weights, dict)
        weights["g1"] = 2
        yield "group_cell_weights", weights


class _ProofMappingWithSideEffect(Mapping[str, object]):
    def __init__(self) -> None:
        self.backing: dict[str, object] = {"first": 1, "second": 1}
        self.iterations = 0

    def __iter__(self) -> Iterator[str]:
        self.iterations += 1
        self.backing["second"] = self.iterations
        return iter(tuple(self.backing))

    def __len__(self) -> int:
        return len(self.backing)

    def __getitem__(self, key: str) -> object:
        return self.backing[key]


def test_plan_side_effect_iterator_either_fails_closed_or_stays_self_consistent() -> None:
    source = _PlanParametersMutatingDuringItems()

    try:
        plan = _region_plan_with_parameters(source)
    except (TypeError, ValueError):
        assert source.items_calls >= 1
        return

    assert source.items_calls == 1
    frozen_weights = plan.parameters["group_cell_weights"]
    assert isinstance(frozen_weights, Mapping)
    assert frozen_weights == {"g1": 2}
    reference = _region_plan_with_parameters(
        {
            "capacity": plan.parameters["capacity"],
            "group_cell_weights": dict(frozen_weights),
        }
    )
    assert plan.digest == reference.digest
    digest_before = plan.digest
    source["capacity"] = 99
    source_weights = source["group_cell_weights"]
    assert isinstance(source_weights, dict)
    source_weights["g1"] = 99
    assert plan.digest == digest_before
    assert frozen_weights == {"g1": 2}


def test_proof_frame_side_effect_iterator_either_fails_closed_or_stays_self_consistent() -> None:
    source = _ProofMappingWithSideEffect()

    try:
        frame = typed_platform_module._proof_frame(
            family="digest_probe",
            schema_version=1,
            proof=source,
        )
    except (TypeError, ValueError):
        return

    decoded = json.loads(frame.removeprefix(_PROOF_FRAME_PREFIX))
    assert type(decoded) is dict
    proof = decoded["proof"]
    assert type(proof) is dict
    assert frame == typed_platform_module._proof_frame(
        family="digest_probe",
        schema_version=1,
        proof=proof,
    )
    source.backing["first"] = 99
    assert json.loads(frame.removeprefix(_PROOF_FRAME_PREFIX))["proof"] == proof


def test_production_registry_has_exact_nine_family_mirror() -> None:
    registry = build_production_registry()

    assert set(registry.capabilities) == _EXPECTED_FAMILIES
    assert set(registry.plugins) == {
        "pattern_nogood",
        "power_hitting_set",
        "region_capacity",
        "shape_packing_hall",
    }
    for family in sorted(_EXPECTED_FAMILIES):
        capability = registry.capabilities[family]
        assert capability.name == family
        assert capability.mode == _EXPECTED_MODES[family]
        assert capability.stage is _EXPECTED_STAGES[family]
        assert capability.execution_path is _EXPECTED_PATHS[family]
        assert capability.proof_schema_version == 1
        assert capability.required_dependencies == frozenset(_PRODUCTION_ARTIFACT_HASHES)
        assert capability.requires_ghost_bound is (family in {"power_hitting_set", "shape_packing_hall"})
        if family == "pattern_nogood":
            assert capability.compiler_version is None
            assert family in registry.plugins
        elif family == "region_capacity":
            assert capability.compiler_version == "stage-b-f1-compiler-v1"
            assert family in registry.plugins
        elif family == "shape_packing_hall":
            assert capability.validator_version == "stage-b-f6-validator-v1"
            assert capability.compiler_version == "stage-b-f6-compiler-v1"
            assert family in registry.plugins
        elif family == "power_hitting_set":
            assert capability.validator_version == "stage-b-f7-validator-v1"
            assert capability.compiler_version == "stage-b-f7-compiler-v1"
            assert family in registry.plugins
        else:
            assert family not in registry.plugins
        if capability.stage is CapabilityStage.COMPILABLE:
            assert capability.execution_path is ExecutionPath.TYPED
            assert capability.compiler_version is not None
            assert family in registry.plugins


@pytest.mark.parametrize("invalid", [0, 1, None, "true"])
def test_family_capability_requires_ghost_bound_is_an_exact_bool(invalid: object) -> None:
    with pytest.raises(TypeError, match="requires_ghost_bound"):
        replace(_capability(), requires_ghost_bound=invalid)


def test_production_registry_replay_and_step_8_family_tables_are_consistent() -> None:
    # B5a: the raw family-branch step_8 shim is gone.  The public
    # step_8_apply_to_master is the typed entry, dispatching on plan.operation
    # (typed_platform.SUPPORTED_OPERATIONS) via typed_apply, and replay splits
    # its old single FAMILY_VALIDATORS table into two mutually-exclusive tables.
    # The registry-vs-replay-vs-single-entry consistency contract (RFC-001
    # §2.8/§2.9) now pins those three views against one another.
    registry = build_production_registry()
    retired = {
        family for family, capability in registry.capabilities.items() if capability.stage is CapabilityStage.RETIRED
    }
    non_retired = set(registry.capabilities) - retired
    typed = {
        family
        for family, capability in registry.capabilities.items()
        if capability.stage is not CapabilityStage.RETIRED and capability.execution_path is ExecutionPath.TYPED
    }
    legacy_diagnostic = {
        family
        for family, capability in registry.capabilities.items()
        if capability.stage is not CapabilityStage.RETIRED
        and capability.execution_path is ExecutionPath.LEGACY_DIAGNOSTIC
    }
    compilable = {
        family for family, capability in registry.capabilities.items() if capability.stage is CapabilityStage.COMPILABLE
    }

    assert retired == {"power_grid_reach"}

    # Registry execution paths vs the replay double-table: disjoint + exhaustive.
    assert set(TYPED_REPLAY_FAMILIES) == typed
    assert set(LEGACY_DIAGNOSTIC_VALIDATORS) == legacy_diagnostic
    assert typed.isdisjoint(legacy_diagnostic)
    assert typed | legacy_diagnostic == non_retired
    assert set(TYPED_REPLAY_FAMILIES).isdisjoint(LEGACY_DIAGNOSTIC_VALIDATORS)

    # The typed single entry has an apply path (a plan.operation) exactly for
    # the COMPILABLE families; the VALIDATED shadow family (pattern_nogood, F5)
    # is TYPED but carries no operation — structurally no step_8/apply path.
    assert compilable == {"region_capacity", "shape_packing_hall", "power_hitting_set"}
    operation_by_family = {
        "power_hitting_set": "power_pose_exclusion",
        "region_capacity": "region_capacity_le",
        "shape_packing_hall": "shape_packing_hall_le",
    }
    assert set(operation_by_family) == compilable
    assert set(operation_by_family.values()) == set(SUPPORTED_OPERATIONS)
    shadow_typed = typed - compilable
    assert shadow_typed == {"pattern_nogood"}
    assert shadow_typed.isdisjoint(operation_by_family)


@pytest.mark.parametrize(
    ("capability", "with_plugin"),
    [
        (_typed_probe_capability(), False),
        (
            _capability(),
            True,
        ),
        (
            _typed_probe_capability(
                stage=CapabilityStage.VALIDATED,
                compiler_version=None,
            ),
            False,
        ),
        (
            _capability(
                stage=CapabilityStage.RETIRED,
                execution_path=ExecutionPath.LEGACY_DIAGNOSTIC,
                compiler_version=None,
            ),
            True,
        ),
    ],
    ids=(
        "compilable-without-plugin",
        "legacy-with-plugin",
        "typed-validated-without-plugin",
        "retired-with-plugin",
    ),
)
def test_registry_rejects_inconsistent_stage_path_plugin_combinations(
    capability: FamilyCapability,
    with_plugin: bool,
) -> None:
    plan = _typed_probe_plan() if capability.name == "shape_packing_hall" else _plan()
    plugin = _OrderedPlugin(plan) if with_plugin else None
    with pytest.raises((TypeError, ValueError)):
        _registry(plugin, capability=capability)


def test_family_plugin_protocol_has_precise_proof_and_return_annotations() -> None:
    expected_parameters = {
        "parse_and_validate_proof": ("self", "proof_payload", "snapshot"),
        "derive_body": ("self", "proof"),
        "compile": ("self", "body", "proof", "snapshot"),
        "validate_plan": ("self", "plan", "proof", "snapshot"),
    }
    for method_name, parameter_names in expected_parameters.items():
        method = getattr(FamilyPlugin, method_name)
        assert tuple(inspect.signature(method).parameters) == parameter_names
    assert get_type_hints(FamilyPlugin.parse_and_validate_proof)["return"] is FrozenFamilyProof
    assert get_type_hints(FamilyPlugin.derive_body)["proof"] is FrozenFamilyProof
    assert get_type_hints(FamilyPlugin.compile)["proof"] is FrozenFamilyProof
    validate_hints = get_type_hints(FamilyPlugin.validate_plan)
    assert validate_hints["proof"] is FrozenFamilyProof
    assert validate_hints["return"] is type(None)
    assert build_production_registry().plugins["pattern_nogood"] is typed_platform_module._PRODUCTION_F5_PLUGIN


class _WrongArityPlugin(_OrderedPlugin):
    def derive_body(
        self,
        proof: FrozenFamilyProof,
        unexpected: object,
    ) -> _ProbeBody:
        del unexpected
        return super().derive_body(proof)


class _DefaultedArgumentPlugin(_OrderedPlugin):
    def compile(
        self,
        body: object,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot | None = None,
    ) -> ConstraintPlan:
        assert snapshot is not None
        return super().compile(body, proof, snapshot)


class _AsyncParserPlugin(_OrderedPlugin):
    async def parse_and_validate_proof(
        self,
        proof_payload: bytes,
        snapshot: ValidatedStateSnapshot,
    ) -> FrozenFamilyProof:
        return super().parse_and_validate_proof(proof_payload, snapshot)


@pytest.mark.parametrize(
    "plugin_type",
    [_WrongArityPlugin, _DefaultedArgumentPlugin, _AsyncParserPlugin],
    ids=("wrong-arity", "defaulted-argument", "async-method"),
)
def test_registry_rejects_family_plugin_signature_violations(
    plugin_type: type[_OrderedPlugin],
) -> None:
    with pytest.raises(TypeError):
        _registry(plugin_type(_plan()))


class _ParserRaisesPlugin(_OrderedPlugin):
    def __init__(self, plan: ConstraintPlan, error: BaseException) -> None:
        super().__init__(plan)
        self.error = error

    def parse_and_validate_proof(
        self,
        proof_payload: bytes,
        snapshot: ValidatedStateSnapshot,
    ) -> FrozenFamilyProof:
        self.events.append(("parse_and_validate_proof", (proof_payload, snapshot)))
        raise self.error


@pytest.mark.parametrize(
    "error",
    [
        ValueError("representation failure"),
        TypeError("plugin contract failure"),
        AssertionError("TCB assertion failure"),
        RuntimeError("TCB runtime failure"),
        MemoryError("TCB memory failure"),
    ],
    ids=("value", "type", "assertion", "runtime", "memory"),
)
def test_non_semantic_plugin_failures_propagate(
    error: BaseException,
) -> None:
    state, snapshot = _build_world()
    envelope = _trusted_test_envelope(_typed_probe_cut(state), snapshot)
    plugin = _ParserRaisesPlugin(_typed_probe_plan(), error)

    with pytest.raises(type(error)):
        validate_and_compile_cut(envelope, snapshot, _typed_probe_registry(plugin))
    assert [name for name, _args in plugin.events] == ["parse_and_validate_proof"]


def test_dedicated_semantic_plugin_failure_becomes_rejection() -> None:
    state, snapshot = _build_world()
    envelope = _trusted_test_envelope(_typed_probe_cut(state), snapshot)
    plugin = _ParserRaisesPlugin(
        _typed_probe_plan(),
        SemanticCutRejection("proof", "well-formed proof is unsound"),
    )

    result = validate_and_compile_cut(envelope, snapshot, _typed_probe_registry(plugin))

    assert isinstance(result, CutRejection)
    assert result.stage == "proof"
    assert result.cut_id == envelope.cut_id


class _WrongProofReturnPlugin(_OrderedPlugin):
    def parse_and_validate_proof(
        self,
        proof_payload: bytes,
        snapshot: ValidatedStateSnapshot,
    ) -> FrozenFamilyProof:
        self.events.append(("parse_and_validate_proof", (proof_payload, snapshot)))
        return _ProbeBody()  # type: ignore[return-value]


def test_plugin_wrong_proof_return_type_propagates() -> None:
    state, snapshot = _build_world()
    envelope = _trusted_test_envelope(_typed_probe_cut(state), snapshot)
    plugin = _WrongProofReturnPlugin(_typed_probe_plan())

    with pytest.raises(TypeError):
        validate_and_compile_cut(envelope, snapshot, _typed_probe_registry(plugin))


class _WrongPlanReturnPlugin(_OrderedPlugin):
    def compile(
        self,
        body: object,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> ConstraintPlan:
        self.events.append(("compile", (body, proof, snapshot)))
        return object()  # type: ignore[return-value]


def test_plugin_wrong_plan_return_type_propagates() -> None:
    state, snapshot = _build_world()
    envelope = _trusted_test_envelope(_typed_probe_cut(state), snapshot)
    plugin = _WrongPlanReturnPlugin(_typed_probe_plan())

    with pytest.raises(TypeError):
        validate_and_compile_cut(envelope, snapshot, _typed_probe_registry(plugin))


def test_v1_adapter_rejects_legacy_truncated_scope_without_raw_preimage() -> None:
    state, _snapshot = _build_world()
    raw_cut = _make_region_cut(state)

    with pytest.raises(ValueError):
        cut_to_envelope_v1(raw_cut)


@pytest.mark.parametrize(
    "changes",
    [
        {"payload_schema_version": 2},
        {"is_quarantined": True},
        {"quarantine_reason": "quarantined-by-test"},
    ],
    ids=("schema-v2", "quarantined-flag", "quarantine-reason"),
)
def test_v1_adapter_rejects_non_v1_and_quarantined_cuts(
    changes: dict[str, object],
) -> None:
    state, _snapshot = _build_world()
    raw_cut = replace(_make_region_cut(state), **changes)

    with pytest.raises((TypeError, ValueError)):
        cut_to_envelope_v1(raw_cut)


def test_v1_adapter_rejects_geometric_body_proof_drift() -> None:
    state, _snapshot = _build_world()
    body = _probe_payload(family="cutset")
    mismatched_proof = body.replace(b'"cut_size": 1', b'"cut_size": 2')
    assert body != mismatched_proof
    raw_cut = _make_region_cut(
        state,
        geometric_payload=body,
        cert_payload=mismatched_proof,
    )

    with pytest.raises((TypeError, ValueError)):
        cut_to_envelope_v1(raw_cut)


def test_v1_adapter_rejects_literal_body_proof_drift() -> None:
    state, _snapshot = _build_world()
    raw_cut = _make_pattern_cut(state, pose_id="pB")

    with pytest.raises((TypeError, ValueError)):
        cut_to_envelope_v1(raw_cut)


def test_proof_frame_tampering_is_rejected_before_plugin_dispatch() -> None:
    state, snapshot = _build_world()
    envelope = _trusted_test_envelope(_typed_probe_cut(state), snapshot)
    plugin = _OrderedPlugin(_typed_probe_plan())
    registry = _typed_probe_registry(plugin)
    frame = _decode_proof_frame(envelope)
    frame["family"] = "pattern_nogood"
    tampered_payload = _PROOF_FRAME_PREFIX + json.dumps(
        frame,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    tampered = replace(
        envelope,
        proof_payload=tampered_payload,
        proof_hash=hashlib.sha256(tampered_payload).hexdigest(),
    )

    with pytest.raises(ValueError):
        validate_and_compile_cut(tampered, snapshot, registry)
    assert plugin.events == []


def test_proof_hash_tampering_is_rejected_before_plugin_dispatch() -> None:
    state, snapshot = _build_world()
    envelope = _trusted_test_envelope(_typed_probe_cut(state), snapshot)
    plugin = _OrderedPlugin(_typed_probe_plan())

    with pytest.raises(ValueError):
        replace(envelope, proof_hash="0" * 64)
    assert plugin.events == []


@pytest.mark.parametrize("payload_kind", ["raw-unframed", "noncanonical-frame"])
def test_noncanonical_proof_frames_are_rejected_before_plugin_dispatch(
    payload_kind: str,
) -> None:
    state, snapshot = _build_world()
    envelope = _trusted_test_envelope(_typed_probe_cut(state), snapshot)
    frame = _decode_proof_frame(envelope)
    if payload_kind == "raw-unframed":
        payload = json.dumps(
            frame,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    else:
        payload = _PROOF_FRAME_PREFIX + json.dumps(
            frame,
            sort_keys=False,
            indent=2,
            ensure_ascii=False,
        ).encode("utf-8")
    tampered = replace(
        envelope,
        proof_payload=payload,
        proof_hash=hashlib.sha256(payload).hexdigest(),
    )
    plugin = _OrderedPlugin(_typed_probe_plan())

    with pytest.raises(ValueError):
        validate_and_compile_cut(tampered, snapshot, _typed_probe_registry(plugin))
    assert plugin.events == []


def test_excessively_nested_self_consistent_frame_fails_closed_before_dispatch() -> None:
    state, snapshot = _build_world()
    envelope = _trusted_test_envelope(_typed_probe_cut(state), snapshot)
    # The platform's pre-decode structural scanner caps proof JSON nesting at
    # 128.  One level over the cap exercises fail-closed admission without
    # driving CPython's JSON decoder into its recursion guard.
    depth = 129
    nested = b"[" * depth + b"0" + b"]" * depth
    payload = (
        _PROOF_FRAME_PREFIX + b'{"family":"shape_packing_hall","proof":{"nested":' + nested + b'},"schema_version":1}'
    )
    tampered = replace(
        envelope,
        proof_payload=payload,
        proof_hash=hashlib.sha256(payload).hexdigest(),
    )
    plugin = _OrderedPlugin(_typed_probe_plan())

    with pytest.raises(ValueError):
        validate_and_compile_cut(tampered, snapshot, _typed_probe_registry(plugin))
    assert plugin.events == []


@dataclass(frozen=True)
class _FrozenProofWithList(FrozenFamilyProof):
    values: list[str]


@dataclass(frozen=True)
class _FrozenProofWithMapping(FrozenFamilyProof):
    values: dict[str, object]


@dataclass(frozen=True)
class _FrozenProofWithRawBytes(FrozenFamilyProof):
    raw: bytes


@dataclass(frozen=True)
class _FrozenProofWithMappingProxy(FrozenFamilyProof):
    values: object


@pytest.mark.parametrize(
    "hostile_proof",
    [
        _FrozenProofWithList(
            family="shape_packing_hall",
            schema_version=1,
            values=["mutable"],
        ),
        _FrozenProofWithMapping(
            family="shape_packing_hall",
            schema_version=1,
            values={"nested": ["mutable"]},
        ),
        _FrozenProofWithRawBytes(
            family="shape_packing_hall",
            schema_version=1,
            raw=b"second-raw-proof-channel",
        ),
    ],
    ids=("mutable-list", "mutable-dict", "raw-bytes"),
)
def test_plugin_parsed_proof_must_be_deeply_frozen_and_body_free(
    hostile_proof: FrozenFamilyProof,
) -> None:
    state, snapshot = _build_world()
    envelope = _trusted_test_envelope(_typed_probe_cut(state), snapshot)
    plugin = _OrderedPlugin(_typed_probe_plan(), proof=hostile_proof)

    with pytest.raises(TypeError):
        validate_and_compile_cut(envelope, snapshot, _typed_probe_registry(plugin))
    assert [name for name, _args in plugin.events] == ["parse_and_validate_proof"]


def test_mapping_proxy_with_mutable_backing_is_not_a_frozen_proof_value() -> None:
    state, snapshot = _build_world()
    envelope = _trusted_test_envelope(_typed_probe_cut(state), snapshot)
    backing = {"value": "before"}
    proof = _FrozenProofWithMappingProxy(
        family="shape_packing_hall",
        schema_version=1,
        values=MappingProxyType(backing),
    )
    plugin = _OrderedPlugin(_typed_probe_plan(), proof=proof)

    with pytest.raises(TypeError):
        validate_and_compile_cut(envelope, snapshot, _typed_probe_registry(plugin))
    assert [name for name, _args in plugin.events] == ["parse_and_validate_proof"]
    backing["value"] = "after"
    assert proof.values["value"] == "after"  # type: ignore[index]


class _RawBodyPlugin(_OrderedPlugin):
    def __init__(self, plan: ConstraintPlan) -> None:
        super().__init__(plan)
        self.raw_payload: bytes | None = None

    def parse_and_validate_proof(
        self,
        proof_payload: bytes,
        snapshot: ValidatedStateSnapshot,
    ) -> FrozenFamilyProof:
        self.raw_payload = proof_payload
        return super().parse_and_validate_proof(proof_payload, snapshot)

    def derive_body(self, proof: FrozenFamilyProof) -> object:
        assert proof is self.proof
        self.events.append(("derive_body", (proof,)))
        assert self.raw_payload is not None
        return self.raw_payload


def test_plugin_cannot_reintroduce_cached_raw_bytes_as_derived_body() -> None:
    state, snapshot = _build_world()
    envelope = _trusted_test_envelope(_typed_probe_cut(state), snapshot)
    plugin = _RawBodyPlugin(_typed_probe_plan())

    with pytest.raises(TypeError):
        validate_and_compile_cut(envelope, snapshot, _typed_probe_registry(plugin))
    assert [name for name, _args in plugin.events] == [
        "parse_and_validate_proof",
        "derive_body",
    ]


class _FalsePlanValidationPlugin(_OrderedPlugin):
    def validate_plan(
        self,
        plan: ConstraintPlan,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> bool:
        assert plan is self.plan
        assert proof is self.proof
        self.events.append(("validate_plan", (plan, proof, snapshot)))
        return False


def test_false_plan_validation_result_cannot_compile() -> None:
    state, snapshot = _build_world()
    envelope = _trusted_test_envelope(_typed_probe_cut(state), snapshot)
    plugin = _FalsePlanValidationPlugin(_typed_probe_plan())

    with pytest.raises(TypeError):
        validate_and_compile_cut(envelope, snapshot, _typed_probe_registry(plugin))
    assert [name for name, _args in plugin.events] == [
        "parse_and_validate_proof",
        "derive_body",
        "compile",
        "validate_plan",
    ]


class _DifferentialF5Oracle:
    name = "binding_empty_domain_v1"

    def __init__(
        self,
        *,
        version: str = "v1.0",
        verdict: str = "INFEASIBLE",
        error: Exception | None = None,
    ) -> None:
        self.version = version
        self.verdict = verdict
        self.error = error
        self.calls: list[tuple[tuple[tuple[str, int, str], ...], object, float]] = []

    def query_liftable(
        self,
        core: tuple[tuple[str, int, str], ...],
        scope: object,
        *,
        deadline_seconds: float,
    ) -> tuple[str, bytes | None]:
        self.calls.append((core, scope, deadline_seconds))
        if self.error is not None:
            raise self.error
        return self.verdict, b"independent-test-witness"


def test_production_registry_f5_envelope_runs_full_shadow_path() -> None:
    # RFC-002 batch D: the full shadow path now requires BOTH the same-oracle
    # re-query (the fake INFEASIBLE oracle below) AND the independent verifier
    # to agree, so this exercises a production-shaped world whose p_dead pose
    # has a genuinely empty binding domain the verifier re-derives.  The shadow
    # tag is upgraded to independently-verified.
    state, snapshot, group_id = _build_f5_verifiable_world(
        artifact_hashes=_PRODUCTION_ARTIFACT_HASHES,
    )
    envelope = _trusted_test_envelope(_make_verifiable_pattern_cut(state, group_id), snapshot)
    oracle = _DifferentialF5Oracle()
    clear_sub_problem_oracle_registry()
    register_sub_problem_oracle(oracle)  # type: ignore[arg-type]
    try:
        result = validate_and_compile_cut(
            envelope,
            snapshot,
            build_production_registry(),
        )
    finally:
        clear_sub_problem_oracle_registry()

    assert isinstance(result, ShadowValidated)
    assert result.cut_id == envelope.cut_id
    assert result.telemetry_tag == "independently-verified"
    assert result.proof_digest == envelope.proof_hash
    assert result.snapshot_digest == snapshot.digest
    dependency_map = {dependency.name: dependency.digest for dependency in envelope.scope.dependency_hashes}
    assert set(dependency_map) == set(_PRODUCTION_ARTIFACT_HASHES)
    for name, raw_identity in _PRODUCTION_ARTIFACT_HASHES.items():
        if raw_identity == _MISSING_OPTIONAL_ARTIFACT:
            _assert_sha256(dependency_map[name])
            assert dependency_map[name] != raw_identity
        else:
            assert dependency_map[name] == raw_identity
    _assert_sha256(result.proof_digest)
    _assert_sha256(result.snapshot_digest)
    # The retained same-oracle re-query still runs exactly once ahead of the
    # independent verifier (defence in depth).
    assert len(oracle.calls) == 1
    assert oracle.calls[0][0] == ((group_id, 0, "p_dead"),)
    assert oracle.calls[0][2] == 15.0


def _plain_liftable_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain_liftable_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_plain_liftable_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_plain_liftable_value(item) for item in value)
    return value


@pytest.mark.parametrize(
    ("case", "legacy_kind"),
    [
        ("registry-missing", "schema_err"),
        ("version-drift", "unsound"),
        ("feasible", "unsound"),
        ("timeout", "timeout"),
        ("oracle-exception", "timeout"),
    ],
)
def test_legacy_and_typed_f5_reject_the_same_five_oracle_failures(
    case: str,
    legacy_kind: str,
) -> None:
    state, snapshot = _build_world(
        artifact_hashes=_PRODUCTION_ARTIFACT_HASHES,
    )
    raw_cut = _make_pattern_cut(state)
    envelope = _trusted_test_envelope(raw_cut, snapshot)
    oracle: _DifferentialF5Oracle | None
    if case == "registry-missing":
        oracle = None
    elif case == "version-drift":
        oracle = _DifferentialF5Oracle(version="v2.0")
    elif case == "feasible":
        oracle = _DifferentialF5Oracle(verdict="FEASIBLE")
    elif case == "timeout":
        oracle = _DifferentialF5Oracle(verdict="TIMEOUT")
    else:
        oracle = _DifferentialF5Oracle(error=RuntimeError("untrusted oracle failed"))

    clear_sub_problem_oracle_registry()
    if oracle is not None:
        register_sub_problem_oracle(oracle)  # type: ignore[arg-type]
    try:
        legacy = validate_pattern_nogood(raw_cut, state, state.canonical_rules)
        assert legacy.kind == legacy_kind
        if case == "oracle-exception":
            with pytest.raises(RuntimeError):
                validate_and_compile_cut(
                    envelope,
                    snapshot,
                    build_production_registry(),
                )
        else:
            typed = validate_and_compile_cut(
                envelope,
                snapshot,
                build_production_registry(),
            )
            assert isinstance(typed, CutRejection)
    finally:
        clear_sub_problem_oracle_registry()

    if oracle is not None and case not in {"registry-missing", "version-drift"}:
        assert len(oracle.calls) == 2
        legacy_scope = oracle.calls[0][1]
        typed_scope = oracle.calls[1][1]
        for field_name in (
            "artifact_hashes",
            "canonical_rules",
            "facility_pools",
            "facility_templates",
            "group_demands",
            "group_pose_domains",
            "instance_to_facility_type",
        ):
            assert _plain_liftable_value(getattr(typed_scope, field_name)) == _plain_liftable_value(
                getattr(legacy_scope, field_name)
            )


def test_f5_proof_oracle_name_must_bind_to_scope_oracle_name() -> None:
    state, snapshot = _build_world(
        artifact_hashes=_PRODUCTION_ARTIFACT_HASHES,
        oracle_capabilities=frozenset(
            {
                "binding_empty_domain_v1",
                "other_available_oracle_v1",
                "region_capacity_v1",
            }
        ),
    )
    envelope = _trusted_test_envelope(
        _make_pattern_cut(state, oracle_name="other_available_oracle_v1"),
        snapshot,
    )

    result = validate_and_compile_cut(
        envelope,
        snapshot,
        build_production_registry(),
    )

    assert isinstance(result, CutRejection)


def test_f5_oracle_version_must_be_nonempty_exact_string() -> None:
    state, snapshot = _build_world(
        artifact_hashes=_PRODUCTION_ARTIFACT_HASHES,
    )
    envelope = _trusted_test_envelope(
        _make_pattern_cut(state, oracle_version=""),
        snapshot,
    )

    result = validate_and_compile_cut(
        envelope,
        snapshot,
        build_production_registry(),
    )

    assert isinstance(result, CutRejection)


# Private typed-platform construction points plus the private master-lowering
# call sites (B5b §4.10/§7 拍板 1-2). The same call collector pins:
#   - the typed construction factories (CompiledCut/CutEnvelope/…/ModelScopeBinding);
#   - ``_build_model_scope_binding`` — sole legal caller is the resolver
#     ``_resolve_model_scope_binding`` (B5a LOW×2 amendment ①);
#   - the three private ``_lower_*_cut`` master mutation methods — only the typed
#     plan interpreter (typed_apply) and the master facade delegate may call them.
_PRIVATE_CONSTRUCTION_SYMBOLS = frozenset(
    {
        "CompiledCut",
        "CutEnvelope",
        "FamilyCapabilityRegistry",
        "ModelScopeBinding",
        "ShadowValidated",
        "_build_model_scope_binding",
        "_lower_region_capacity_cut",
        "_lower_baseline_packing_cut",
        "_lower_power_pose_exclusion_cut",
    }
)


def _assigned_name_ids(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Starred):
        return _assigned_name_ids(target.value)
    if isinstance(target, (ast.List, ast.Tuple)):
        return set().union(*(_assigned_name_ids(item) for item in target.elts))
    return set()


def _resolved_symbols(
    node: ast.AST,
    *,
    targets: frozenset[str],
    aliases: Mapping[str, frozenset[str]],
) -> frozenset[str]:
    if isinstance(node, ast.Name):
        if node.id in targets:
            return frozenset({node.id})
        return aliases.get(node.id, frozenset())
    if isinstance(node, ast.Attribute) and node.attr in targets:
        return frozenset({node.attr})
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and type(node.args[1].value) is str
        and node.args[1].value in targets
    ):
        return frozenset({node.args[1].value})
    return frozenset()


def _argument_names(arguments: ast.arguments) -> set[str]:
    names = {
        argument.arg
        for argument in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        )
    }
    if arguments.vararg is not None:
        names.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        names.add(arguments.kwarg.arg)
    return names


def _merge_alias_maps(
    *alias_maps: Mapping[str, frozenset[str]],
) -> dict[str, frozenset[str]]:
    merged: dict[str, frozenset[str]] = {}
    for name in set().union(*(set(alias_map) for alias_map in alias_maps)):
        symbols = frozenset().union(*(alias_map.get(name, frozenset()) for alias_map in alias_maps))
        if symbols:
            merged[name] = symbols
    return merged


class _ConstructionCallCollector(ast.NodeVisitor):
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.class_stack: list[str | None] = [None]
        self.function_stack: list[str | None] = [None]
        self.alias_scopes: list[dict[str, frozenset[str]]] = [{}]
        self.calls: list[tuple[str, str, str | None, str | None, int]] = []

    @property
    def aliases(self) -> dict[str, frozenset[str]]:
        return self.alias_scopes[-1]

    def _symbols(self, node: ast.AST) -> frozenset[str]:
        return _resolved_symbols(
            node,
            targets=_PRIVATE_CONSTRUCTION_SYMBOLS,
            aliases=self.aliases,
        )

    def _refresh_aliases(
        self,
        targets: list[ast.AST],
        symbols: frozenset[str],
    ) -> None:
        for target in targets:
            for name in _assigned_name_ids(target):
                if symbols:
                    self.aliases[name] = symbols
                else:
                    self.aliases.pop(name, None)

    def _visit_definition_header(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    ) -> None:
        for field_name, value in ast.iter_fields(node):
            if field_name == "body":
                continue
            if isinstance(value, ast.AST):
                self.visit(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        self.visit(item)

    def _visit_function_body(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        function_aliases = dict(self.aliases)
        for parameter_name in _argument_names(node.args):
            function_aliases.pop(parameter_name, None)
        self.alias_scopes.append(function_aliases)
        self.function_stack.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.function_stack.pop()
        self.alias_scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_definition_header(node)
        self._visit_function_body(node)
        self.aliases.pop(node.name, None)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_definition_header(node)
        self._visit_function_body(node)
        self.aliases.pop(node.name, None)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)
        lambda_aliases = dict(self.aliases)
        for parameter_name in _argument_names(node.args):
            lambda_aliases.pop(parameter_name, None)
        self.alias_scopes.append(lambda_aliases)
        self.function_stack.append("<lambda>")
        self.visit(node.body)
        self.function_stack.pop()
        self.alias_scopes.pop()

    def _visit_comprehension_scope(
        self,
        node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp,
        *,
        scope_name: str,
        result_nodes: tuple[ast.AST, ...],
    ) -> None:
        generators = list(node.generators)
        if not generators:
            return
        self.visit(generators[0].iter)
        self.alias_scopes.append(dict(self.aliases))
        self.function_stack.append(scope_name)
        for name in _assigned_name_ids(generators[0].target):
            self.aliases.pop(name, None)
        for condition in generators[0].ifs:
            self.visit(condition)
        for generator in generators[1:]:
            self.visit(generator.iter)
            for name in _assigned_name_ids(generator.target):
                self.aliases.pop(name, None)
            for condition in generator.ifs:
                self.visit(condition)
        for result_node in result_nodes:
            self.visit(result_node)
        self.function_stack.pop()
        self.alias_scopes.pop()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension_scope(node, scope_name="<listcomp>", result_nodes=(node.elt,))

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension_scope(node, scope_name="<setcomp>", result_nodes=(node.elt,))

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension_scope(node, scope_name="<genexpr>", result_nodes=(node.elt,))

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension_scope(node, scope_name="<dictcomp>", result_nodes=(node.key, node.value))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_definition_header(node)
        self.alias_scopes.append(dict(self.aliases))
        self.class_stack.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.class_stack.pop()
        self.alias_scopes.pop()
        self.aliases.pop(node.name, None)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        self._refresh_aliases(list(node.targets), self._symbols(node.value))

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit(node.annotation)
        if node.value is None:
            self._refresh_aliases([node.target], frozenset())
            return
        self.visit(node.value)
        self._refresh_aliases([node.target], self._symbols(node.value))

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        self._refresh_aliases([node.target], self._symbols(node.value))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for imported in node.names:
            local_name = imported.asname or imported.name
            if imported.name in _PRIVATE_CONSTRUCTION_SYMBOLS:
                self.aliases[local_name] = frozenset({imported.name})
            else:
                self.aliases.pop(local_name, None)

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        aliases_before = dict(self.aliases)
        self.alias_scopes[-1] = dict(aliases_before)
        for statement in node.body:
            self.visit(statement)
        aliases_body = dict(self.aliases)
        self.alias_scopes[-1] = dict(aliases_before)
        for statement in node.orelse:
            self.visit(statement)
        aliases_else = dict(self.aliases)
        self.alias_scopes[-1] = _merge_alias_maps(aliases_body, aliases_else)

    def visit_Call(self, node: ast.Call) -> None:
        for called_name in sorted(self._symbols(node.func)):
            self.calls.append(
                (
                    called_name,
                    self.filename,
                    self.class_stack[-1],
                    self.function_stack[-1],
                    node.lineno,
                )
            )
        self.generic_visit(node)


_PRIVATE_TOKEN_SYMBOLS = frozenset(
    {
        "_COMPILED_CUT_CONSTRUCTION_TOKEN",
        "_MODEL_SCOPE_BINDING_CONSTRUCTION_TOKEN",
        "_SHADOW_VALIDATED_CONSTRUCTION_TOKEN",
    }
)
_PRIVATE_CONSTRUCTION_REFERENCE_ALLOWLIST = Counter(
    {
        ("CompiledCut", "src/cuts/lifecycle.py", None, "step_6_attach_scope_check"): 2,
        ("CompiledCut", "src/cuts/lifecycle.py", None, "step_8_apply_to_master"): 2,
        ("CompiledCut", "src/cuts/lifecycle.py", None, None): 1,
        ("CompiledCut", "src/cuts/replay.py", None, "_replay_typed"): 2,
        ("CompiledCut", "src/cuts/typed_apply.py", None, "apply_compiled_cut"): 1,
        ("CompiledCut", "src/cuts/typed_apply.py", None, None): 2,
        ("CompiledCut", "src/cuts/typed_platform.py", None, "validate_and_compile_cut"): 1,
        ("CompiledCut", "src/cuts/typed_platform.py", None, None): 1,
        ("CompiledCut", "src/search/benders_loop.py", "LBBDController", "_maybe_attach_framework_cuts"): 2,
        ("CutEnvelope", "src/cuts/typed_platform.py", None, "cut_to_envelope_v1"): 1,
        ("CutEnvelope", "src/cuts/typed_platform.py", None, "validate_and_compile_cut"): 1,
        ("CutEnvelope", "src/cuts/typed_platform.py", None, None): 5,
        ("FamilyCapabilityRegistry", "src/cuts/typed_platform.py", None, "build_production_registry"): 1,
        ("FamilyCapabilityRegistry", "src/cuts/typed_platform.py", None, "validate_and_compile_cut"): 1,
        ("FamilyCapabilityRegistry", "src/cuts/typed_platform.py", None, None): 2,
        ("ModelScopeBinding", "src/cuts/lifecycle.py", None, "step_8_apply_to_master"): 2,
        ("ModelScopeBinding", "src/cuts/lifecycle.py", None, None): 1,
        ("ModelScopeBinding", "src/cuts/typed_apply.py", None, "apply_compiled_cut"): 1,
        ("ModelScopeBinding", "src/cuts/typed_apply.py", None, None): 2,
        ("ModelScopeBinding", "src/cuts/typed_platform.py", None, "_build_model_scope_binding"): 1,
        ("ModelScopeBinding", "src/cuts/typed_platform.py", None, None): 1,
        ("ShadowValidated", "src/cuts/replay.py", None, "_replay_typed"): 2,
        ("ShadowValidated", "src/cuts/typed_platform.py", None, "validate_and_compile_cut"): 1,
        ("ShadowValidated", "src/cuts/typed_platform.py", None, None): 1,
        ("ShadowValidated", "src/search/benders_loop.py", "LBBDController", "_maybe_attach_framework_cuts"): 2,
        ("_build_model_scope_binding", "src/cuts/lifecycle.py", None, "_resolve_model_scope_binding"): 2,
        ("_lower_baseline_packing_cut", "src/cuts/typed_apply.py", None, "apply_compiled_cut"): 1,
        (
            "_lower_baseline_packing_cut",
            "src/models/master_model.py",
            "MasterPlacementModel",
            "_lower_baseline_packing_cut",
        ): 3,
        ("_lower_power_pose_exclusion_cut", "src/cuts/typed_apply.py", None, "apply_compiled_cut"): 1,
        (
            "_lower_power_pose_exclusion_cut",
            "src/models/master_model.py",
            "MasterPlacementModel",
            "_lower_power_pose_exclusion_cut",
        ): 3,
        ("_lower_region_capacity_cut", "src/cuts/typed_apply.py", None, "apply_compiled_cut"): 1,
        (
            "_lower_region_capacity_cut",
            "src/models/master_model.py",
            "MasterPlacementModel",
            "_lower_region_capacity_cut",
        ): 3,
    }
)


_PRIVATE_TOKEN_REFERENCE_ALLOWLIST = Counter(
    {
        (
            "_COMPILED_CUT_CONSTRUCTION_TOKEN",
            "src/cuts/typed_platform.py",
            "CompiledCut",
            "__init__",
        ): 1,
        (
            "_COMPILED_CUT_CONSTRUCTION_TOKEN",
            "src/cuts/typed_platform.py",
            None,
            "validate_and_compile_cut",
        ): 1,
        (
            "_MODEL_SCOPE_BINDING_CONSTRUCTION_TOKEN",
            "src/cuts/typed_platform.py",
            "ModelScopeBinding",
            "__init__",
        ): 1,
        (
            "_MODEL_SCOPE_BINDING_CONSTRUCTION_TOKEN",
            "src/cuts/typed_platform.py",
            None,
            "_build_model_scope_binding",
        ): 1,
        (
            "_SHADOW_VALIDATED_CONSTRUCTION_TOKEN",
            "src/cuts/typed_platform.py",
            "ShadowValidated",
            "__init__",
        ): 1,
        (
            "_SHADOW_VALIDATED_CONSTRUCTION_TOKEN",
            "src/cuts/typed_platform.py",
            None,
            "validate_and_compile_cut",
        ): 1,
    }
)


class _PrivateTokenReferenceCollector(ast.NodeVisitor):
    def __init__(
        self,
        filename: str,
        *,
        targets: frozenset[str] = _PRIVATE_TOKEN_SYMBOLS,
    ) -> None:
        self.filename = filename
        self.targets = targets
        self.class_stack: list[str | None] = [None]
        self.function_stack: list[str | None] = [None]
        self.alias_scopes: list[dict[str, frozenset[str]]] = [{}]
        self.references: list[tuple[str, str, str | None, str | None, int]] = []

    @property
    def aliases(self) -> dict[str, frozenset[str]]:
        return self.alias_scopes[-1]

    def _symbols(self, node: ast.AST) -> frozenset[str]:
        return _resolved_symbols(
            node,
            targets=self.targets,
            aliases=self.aliases,
        )

    def _refresh_aliases(
        self,
        targets: list[ast.AST],
        symbols: frozenset[str],
    ) -> None:
        for target in targets:
            for name in _assigned_name_ids(target):
                if symbols:
                    self.aliases[name] = symbols
                else:
                    self.aliases.pop(name, None)

    def _record(self, symbol: str, node: ast.AST) -> None:
        self.references.append(
            (
                symbol,
                self.filename,
                self.class_stack[-1],
                self.function_stack[-1],
                node.lineno,
            )
        )

    def _visit_definition_header(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    ) -> None:
        for field_name, value in ast.iter_fields(node):
            if field_name == "body":
                continue
            if isinstance(value, ast.AST):
                self.visit(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        self.visit(item)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_definition_header(node)
        self.alias_scopes.append(dict(self.aliases))
        self.class_stack.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.class_stack.pop()
        self.alias_scopes.pop()
        self.aliases.pop(node.name, None)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_definition_header(node)
        function_aliases = dict(self.aliases)
        for parameter_name in _argument_names(node.args):
            function_aliases.pop(parameter_name, None)
        self.alias_scopes.append(function_aliases)
        self.function_stack.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.function_stack.pop()
        self.alias_scopes.pop()
        self.aliases.pop(node.name, None)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_definition_header(node)
        function_aliases = dict(self.aliases)
        for parameter_name in _argument_names(node.args):
            function_aliases.pop(parameter_name, None)
        self.alias_scopes.append(function_aliases)
        self.function_stack.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.function_stack.pop()
        self.alias_scopes.pop()
        self.aliases.pop(node.name, None)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)
        lambda_aliases = dict(self.aliases)
        for parameter_name in _argument_names(node.args):
            lambda_aliases.pop(parameter_name, None)
        self.alias_scopes.append(lambda_aliases)
        self.function_stack.append("<lambda>")
        self.visit(node.body)
        self.function_stack.pop()
        self.alias_scopes.pop()

    def _visit_comprehension_scope(
        self,
        node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp,
        *,
        scope_name: str,
        result_nodes: tuple[ast.AST, ...],
    ) -> None:
        generators = list(node.generators)
        if not generators:
            return
        self.visit(generators[0].iter)
        self.alias_scopes.append(dict(self.aliases))
        self.function_stack.append(scope_name)
        for name in _assigned_name_ids(generators[0].target):
            self.aliases.pop(name, None)
        for condition in generators[0].ifs:
            self.visit(condition)
        for generator in generators[1:]:
            self.visit(generator.iter)
            for name in _assigned_name_ids(generator.target):
                self.aliases.pop(name, None)
            for condition in generator.ifs:
                self.visit(condition)
        for result_node in result_nodes:
            self.visit(result_node)
        self.function_stack.pop()
        self.alias_scopes.pop()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension_scope(node, scope_name="<listcomp>", result_nodes=(node.elt,))

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension_scope(node, scope_name="<setcomp>", result_nodes=(node.elt,))

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension_scope(node, scope_name="<genexpr>", result_nodes=(node.elt,))

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension_scope(node, scope_name="<dictcomp>", result_nodes=(node.key, node.value))

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        self._refresh_aliases(list(node.targets), self._symbols(node.value))

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit(node.annotation)
        if node.value is None:
            self._refresh_aliases([node.target], frozenset())
            return
        self.visit(node.value)
        self._refresh_aliases([node.target], self._symbols(node.value))

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        self._refresh_aliases([node.target], self._symbols(node.value))

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            for symbol in sorted(self._symbols(node)):
                self._record(symbol, node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load):
            for symbol in sorted(self._symbols(node)):
                self._record(symbol, node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for imported in node.names:
            local_name = imported.asname or imported.name
            if imported.name in self.targets:
                self._record(imported.name, node)
                self.aliases[local_name] = frozenset({imported.name})
            else:
                self.aliases.pop(local_name, None)

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        aliases_before = dict(self.aliases)
        self.alias_scopes[-1] = dict(aliases_before)
        for statement in node.body:
            self.visit(statement)
        aliases_body = dict(self.aliases)
        self.alias_scopes[-1] = dict(aliases_before)
        for statement in node.orelse:
            self.visit(statement)
        aliases_else = dict(self.aliases)
        self.alias_scopes[-1] = _merge_alias_maps(aliases_body, aliases_else)

    def visit_Call(self, node: ast.Call) -> None:
        for symbol in sorted(self._symbols(node)):
            self._record(symbol, node)
        self.generic_visit(node)


def _production_python_files() -> list[Path]:
    return [path for path in sorted(SRC_ROOT.rglob("*.py")) if path != TESTS_ROOT and TESTS_ROOT not in path.parents]


def test_private_typed_construction_points_are_exactly_allowlisted() -> None:
    calls: list[tuple[str, str, str | None, str | None, int]] = []
    for path in _production_python_files():
        relative = path.relative_to(REPO_ROOT).as_posix()
        collector = _ConstructionCallCollector(relative)
        collector.visit(ast.parse(path.read_text(encoding="utf-8"), filename=relative))
        calls.extend(collector.calls)

    actual = Counter(
        (symbol, filename, class_name, function_name) for symbol, filename, class_name, function_name, _line in calls
    )
    expected = Counter(
        {
            (
                "CompiledCut",
                "src/cuts/typed_platform.py",
                None,
                "validate_and_compile_cut",
            ): 1,
            (
                "CutEnvelope",
                "src/cuts/typed_platform.py",
                None,
                "cut_to_envelope_v1",
            ): 1,
            (
                "FamilyCapabilityRegistry",
                "src/cuts/typed_platform.py",
                None,
                "build_production_registry",
            ): 1,
            (
                "ModelScopeBinding",
                "src/cuts/typed_platform.py",
                None,
                "_build_model_scope_binding",
            ): 1,
            (
                "ShadowValidated",
                "src/cuts/typed_platform.py",
                None,
                "validate_and_compile_cut",
            ): 1,
            # B5b §7 拍板 1: the ModelScopeBinding factory's sole legal caller.
            (
                "_build_model_scope_binding",
                "src/cuts/lifecycle.py",
                None,
                "_resolve_model_scope_binding",
            ): 1,
            # B5b §7 拍板 2: each private master-lowering method may be called
            # only by the typed plan interpreter and its own facade delegate.
            (
                "_lower_region_capacity_cut",
                "src/cuts/typed_apply.py",
                None,
                "apply_compiled_cut",
            ): 1,
            (
                "_lower_region_capacity_cut",
                "src/models/master_model.py",
                "MasterPlacementModel",
                "_lower_region_capacity_cut",
            ): 1,
            (
                "_lower_baseline_packing_cut",
                "src/cuts/typed_apply.py",
                None,
                "apply_compiled_cut",
            ): 1,
            (
                "_lower_baseline_packing_cut",
                "src/models/master_model.py",
                "MasterPlacementModel",
                "_lower_baseline_packing_cut",
            ): 1,
            (
                "_lower_power_pose_exclusion_cut",
                "src/cuts/typed_apply.py",
                None,
                "apply_compiled_cut",
            ): 1,
            (
                "_lower_power_pose_exclusion_cut",
                "src/models/master_model.py",
                "MasterPlacementModel",
                "_lower_power_pose_exclusion_cut",
            ): 1,
        }
    )
    assert actual == expected, calls


def test_private_construction_references_are_exactly_allowlisted() -> None:
    references: list[tuple[str, str, str | None, str | None, int]] = []
    for path in _production_python_files():
        relative = path.relative_to(REPO_ROOT).as_posix()
        collector = _PrivateTokenReferenceCollector(relative, targets=_PRIVATE_CONSTRUCTION_SYMBOLS)
        collector.visit(ast.parse(path.read_text(encoding="utf-8"), filename=relative))
        references.extend(collector.references)

    actual = Counter(
        (symbol, filename, class_name, function_name)
        for symbol, filename, class_name, function_name, _line in references
    )
    assert actual == _PRIVATE_CONSTRUCTION_REFERENCE_ALLOWLIST, references


def test_private_construction_tokens_have_no_production_escape() -> None:
    references: list[tuple[str, str, str | None, str | None, int]] = []
    for path in _production_python_files():
        relative = path.relative_to(REPO_ROOT).as_posix()
        collector = _PrivateTokenReferenceCollector(relative)
        collector.visit(ast.parse(path.read_text(encoding="utf-8"), filename=relative))
        references.extend(collector.references)

    actual = Counter(
        (symbol, filename, class_name, function_name)
        for symbol, filename, class_name, function_name, _line in references
    )
    assert actual == _PRIVATE_TOKEN_REFERENCE_ALLOWLIST, references


def test_construction_analyzer_catches_assignment_import_and_reflection_aliases() -> None:
    source = """
from src.cuts.typed_platform import CompiledCut as imported_compiled
import src.cuts.typed_platform as platform

assigned = CutEnvelope
qualified = platform.ShadowValidated
reflected = getattr(platform, "ModelScopeBinding")
imported_compiled()
assigned()
qualified()
reflected()
getattr(platform, "FamilyCapabilityRegistry")()
assigned = object
assigned()
"""
    collector = _ConstructionCallCollector("src/cuts/construction_attack.py")
    collector.visit(ast.parse(source, filename=collector.filename))

    assert Counter(symbol for symbol, *_rest in collector.calls) == Counter(
        {
            "CompiledCut": 1,
            "CutEnvelope": 1,
            "FamilyCapabilityRegistry": 1,
            "ModelScopeBinding": 1,
            "ShadowValidated": 1,
        }
    )


def test_construction_reference_analyzer_catches_container_and_partial_smuggling() -> None:
    source = """
from functools import partial

direct_alias = _build_model_scope_binding
direct_alias()

holder = [_build_model_scope_binding]
holder[0]()

deferred = partial(_lower_region_capacity_cut, group_cell_weights={})
deferred()
"""
    calls = _ConstructionCallCollector("src/cuts/construction_smuggle.py")
    calls.visit(ast.parse(source, filename=calls.filename))
    assert Counter(symbol for symbol, *_rest in calls.calls) == Counter({"_build_model_scope_binding": 1})

    references = _PrivateTokenReferenceCollector(
        "src/cuts/construction_smuggle.py",
        targets=_PRIVATE_CONSTRUCTION_SYMBOLS,
    )
    references.visit(ast.parse(source, filename=references.filename))
    assert Counter(symbol for symbol, *_rest in references.references) == Counter(
        {
            "_build_model_scope_binding": 3,
            "_lower_region_capacity_cut": 1,
        }
    )


def test_private_token_analyzer_catches_alias_reflection_and_reference_counts() -> None:
    source = """
from src.cuts.typed_platform import _COMPILED_CUT_CONSTRUCTION_TOKEN as imported_token
import src.cuts.typed_platform as platform

direct = _COMPILED_CUT_CONSTRUCTION_TOKEN
consume(direct)
via_import = imported_token
consume(via_import)
via_attribute = platform._COMPILED_CUT_CONSTRUCTION_TOKEN
consume(via_attribute)
via_getattr = getattr(platform, "_COMPILED_CUT_CONSTRUCTION_TOKEN")
consume(via_getattr)
via_alias = via_getattr
consume(via_alias)
direct = object()
consume(direct)
"""
    collector = _PrivateTokenReferenceCollector("src/cuts/token_attack.py")
    collector.visit(ast.parse(source, filename=collector.filename))

    # One import plus ten direct/aliased capability reads.  A set would erase these
    # repeated references and let extra uses inside an allowlisted scope pass.
    assert len(collector.references) == 11
    assert all(reference[0] == "_COMPILED_CUT_CONSTRUCTION_TOKEN" for reference in collector.references)

    repeated_owner_use = """
def validate_and_compile_cut():
    first = _COMPILED_CUT_CONSTRUCTION_TOKEN
    second = _COMPILED_CUT_CONSTRUCTION_TOKEN
    return first, second
"""
    collector = _PrivateTokenReferenceCollector("src/cuts/typed_platform.py")
    collector.visit(ast.parse(repeated_owner_use, filename=collector.filename))
    locations = Counter(
        (symbol, filename, class_name, function_name)
        for symbol, filename, class_name, function_name, _line in collector.references
    )
    assert (
        locations[
            (
                "_COMPILED_CUT_CONSTRUCTION_TOKEN",
                "src/cuts/typed_platform.py",
                None,
                "validate_and_compile_cut",
            )
        ]
        == 4
    )

    owner_escape = """
def unrelated_factory():
    return _MODEL_SCOPE_BINDING_CONSTRUCTION_TOKEN
"""
    collector = _PrivateTokenReferenceCollector("src/cuts/typed_platform.py")
    collector.visit(ast.parse(owner_escape, filename=collector.filename))
    assert {
        (filename, class_name, function_name)
        for _symbol, filename, class_name, function_name, _line in collector.references
    } == {("src/cuts/typed_platform.py", None, "unrelated_factory")}

    allowed_name_default_leak = """
def validate_and_compile_cut(leaked=_COMPILED_CUT_CONSTRUCTION_TOKEN):
    return leaked
"""
    collector = _PrivateTokenReferenceCollector("src/cuts/typed_platform.py")
    collector.visit(
        ast.parse(
            allowed_name_default_leak,
            filename=collector.filename,
        )
    )
    assert {
        (filename, class_name, function_name)
        for _symbol, filename, class_name, function_name, _line in collector.references
    } == {("src/cuts/typed_platform.py", None, None)}


def test_model_scope_binding_rejects_direct_construction() -> None:
    class _WeakrefableMaster:
        pass

    master = _WeakrefableMaster()
    with pytest.raises(TypeError, match="ModelScopeBinding is private"):
        ModelScopeBinding(
            rect_idx=None,
            ghost_rect_digest=None,
            condition_lits=(),
            blocked_cells=None,
            snapshot_digest="8" * 64,
            master_domain_family="region_capacity",
            master_domain_projection="9" * 64,
            master_ref=weakref.ref(master),
            _construction_token=object(),
        )


def test_v1_adapter_and_production_registry_factory_each_have_one_definition() -> None:
    module = ast.parse(
        TYPED_PLATFORM_PATH.read_text(encoding="utf-8"),
        filename=TYPED_PLATFORM_PATH.as_posix(),
    )
    definitions = [
        node.name
        for node in ast.walk(module)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"build_production_registry", "cut_to_envelope_v1"}
    ]
    assert sorted(definitions) == ["build_production_registry", "cut_to_envelope_v1"]
