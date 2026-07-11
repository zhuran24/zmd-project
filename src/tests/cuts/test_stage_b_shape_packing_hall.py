"""RFC-001 Stage-B B3 differential tests for F6 shape_packing_hall.

The production attach path remains raw until B5.  This module therefore drives
the complete B3 typed chain explicitly and lowers the resulting immutable plan
through the existing master facade only as a test seam.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from copy import copy, deepcopy
from dataclasses import replace
from typing import Any, cast

import pytest
from ortools.sat.python import cp_model

from src.cuts.families.shape_packing_hall import validate_shape_packing_hall
from src.cuts.families.shape_packing_hall_typed import (
    ShapePackingHallProof,
    shape_packing_hall_master_domain_projection_v1,
)
from src.cuts.frozen_artifacts import (
    FrozenArtifactBundle,
    build_frozen_artifact_bundle,
)
from src.cuts.helpers.baseline_partition import RegionKind
from src.cuts.lifecycle import (
    GHOST_AGNOSTIC,
    Assumption,
    BState,
    Cut,
    GroupState,
    ScopeIdentityPreimageV1,
    canonical_bytes_for_cert,
    compute_scope_identity_legacy_hashes,
    compute_source_digest,
    validate_cut_integrity,
)
from src.cuts.oracles.shape_packing_hall_oracle import (
    generate_shape_packing_hall_cuts,
)
from src.cuts.state_snapshot import (
    ValidatedStateSnapshot,
    build_validated_state_snapshot,
    master_domain_facility_pool_projection_v1,
    master_domain_projection_v1,
)
from src.cuts.typed_platform import (
    CapabilityStage,
    CompiledCut,
    ConstraintPlan,
    CutRejection,
    FamilyCapabilityRegistry,
    FamilyPlugin,
    FrozenFamilyProof,
    build_production_registry,
    cut_to_envelope_v1,
    validate_and_compile_cut,
)
from src.models.master_model import MasterPlacementModel


_GROUP_ID = "group::port::storage::0"
_FACILITY_TYPE = "port"
_OPERATION_TYPE = "storage"
_ARTIFACT_HASHES = {
    "candidate_placements": "1" * 64,
    "canonical_rules": "2" * 64,
    "certified_exact_source_tree": "3" * 64,
    "commodity_demands": "4" * 64,
    "generic_io_requirements": "5" * 64,
    "mandatory_exact_instances": "6" * 64,
    "orbit_homogeneity_digest": "7" * 64,
    "preprocess_plan": "8" * 64,
}

# B3 accept-set completeness audit.  Every reachable F6 adapter/plugin reject
# category is classified here as a ratified typed-only tightening, a legacy
# parity obligation, or a typed-internal invariant that cannot be controlled by
# a raw cut.  Differential tests below name the typed-only and parity rows.
_F6_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT = {
    "adapter.exact_cut_and_constructor_schema": "typed-internal-invariant",
    "adapter.payload_schema_version": "typed-only",
    "adapter.quarantine": "typed-only",
    "adapter.integrity_bookkeeping": "legacy-parity",
    "adapter.cert_and_scope_presence": "legacy-parity",
    "adapter.geometric_empty_literals": "legacy-parity",
    "adapter.shared_cert_payload_schema": "legacy-parity",
    "adapter.outer_cert_kind": "typed-only",
    "adapter.geometric_body_projection": "legacy-parity",
    "adapter.identity_preimage_presence": "typed-only",
    "adapter.identity_preimage_structural_consistency": "typed-only",
    "adapter.identity_preimage_blocked_identity": "typed-only",
    "adapter.identity_preimage_exterior_identity": "typed-only",
    "adapter.identity_preimage_ghost_identity": "typed-only",
    "adapter.legacy_scope_identity_recompute": "legacy-parity",
    "scope.exterior_preimage_snapshot_currentness": "typed-only",
    "scope.nonempty_assumptions": "typed-only",
    "scope.requires_ghost_bound": "legacy-parity",
    "plugin.closed_schema_and_cert_kind": "legacy-parity",
    "plugin.closed_enums_and_scalar_shape": "legacy-parity",
    "plugin.partition_and_hall_internal": "legacy-parity",
    "plugin.snapshot_group_and_template": "legacy-parity",
    "plugin.region_demand_lower_bound": "legacy-parity",
    "plugin.snapshot_ghost_and_exterior": "legacy-parity",
    "plugin.snapshot_partition_recompute": "legacy-parity",
    "plugin.compiler_and_plan_self_checks": "typed-internal-invariant",
}

_ALL_POSES: tuple[dict[str, Any], ...] = (
    {
        "pose_id": "left_a",
        "anchor": {"x": 0, "y": 0},
        "occupied_cells": [[0, 0], [1, 0], [2, 0]],
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": None,
    },
    {
        "pose_id": "left_b",
        "anchor": {"x": 3, "y": 0},
        "occupied_cells": [[3, 0], [4, 0], [5, 0]],
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": None,
    },
    {
        "pose_id": "bottom",
        "anchor": {"x": 0, "y": 3},
        "occupied_cells": [[0, 3], [0, 4], [0, 5]],
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": None,
    },
    {
        "pose_id": "interior",
        "anchor": {"x": 2, "y": 3},
        "occupied_cells": [[2, 3], [3, 3], [4, 3]],
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": None,
    },
)
_LEFT_ONLY_POSES = _ALL_POSES[:2]


def _build_world(
    *,
    all_baselines_blocked: bool = False,
    demand: int = 2,
    poses: Sequence[Mapping[str, Any]] = _ALL_POSES,
) -> tuple[BState, FrozenArtifactBundle]:
    """Build a production-manifest F6 world with independently known capacities.

    Normal geometry leaves three horizontal cells on the left baseline
    (capacity one for a 1x3 pose) and only the shared corner on the bottom
    baseline (capacity zero).  The ghost is at (5,5), so F6 remains bound while
    the cert partition is controlled entirely by immutable exterior geometry.
    """

    copied_poses = [deepcopy(dict(pose)) for pose in poses]
    facility_templates: dict[str, Any] = {
        _FACILITY_TYPE: {
            "placement_rule": "left_or_bottom_boundary",
            "dimensions": {"w": 3, "h": 1},
            "needs_power": False,
        }
    }
    canonical_rules: dict[str, Any] = {
        "globals": {"grid": {"width": 70, "height": 70}},
        "facility_templates": facility_templates,
    }
    candidate_placements: dict[str, Any] = {"facility_pools": {_FACILITY_TYPE: copied_poses}}
    instance_to_facility_type = {_GROUP_ID: _FACILITY_TYPE}
    left_baseline = {(coordinate, 0) for coordinate in range(70)}
    bottom_baseline = {(0, coordinate) for coordinate in range(70)}
    if all_baselines_blocked:
        exterior_blocks = frozenset(left_baseline | bottom_baseline)
    else:
        exterior_blocks = frozenset(
            {(coordinate, 0) for coordinate in range(3, 70)} | {(0, coordinate) for coordinate in range(1, 70)}
        )
    state = BState(
        groups={
            _GROUP_ID: GroupState(
                group_id=_GROUP_ID,
                demand=demand,
                pose_domain=frozenset(cast(str, pose["pose_id"]) for pose in copied_poses),
            )
        },
        ghost_rect=(5, 5, 1, 1),
        ghost_cells=frozenset({(5, 5)}),
        exterior_blocks=exterior_blocks,
        artifact_hashes=dict(_ARTIFACT_HASHES),
        available_oracle_versions=frozenset({"shape_packing_hall_v1"}),
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
        artifact_hashes=_ARTIFACT_HASHES,
    )
    return state, bundle


def _oracle_cut(
    state: BState,
    *,
    region_kind: RegionKind,
    region_demand: int,
    iter_index: int = -1,
) -> Cut:
    cuts = generate_shape_packing_hall_cuts(
        state,
        boundary_groups=[_GROUP_ID],
        region_kinds=(region_kind,),
        region_demand_overrides={(_GROUP_ID, region_kind): region_demand},
        iter_index=iter_index,
    )
    assert len(cuts) == 1
    cut = cuts[0]
    assert cut.scope is not None
    assert cut.scope.identity_preimage is not None
    return cut


def _compile_cut(
    state: BState,
    bundle: FrozenArtifactBundle,
    *,
    region_kind: RegionKind,
    region_demand: int,
    iter_index: int = -1,
    registry: FamilyCapabilityRegistry | None = None,
) -> tuple[Cut, ValidatedStateSnapshot, CompiledCut]:
    raw_cut = _oracle_cut(
        state,
        region_kind=region_kind,
        region_demand=region_demand,
        iter_index=iter_index,
    )
    envelope = cut_to_envelope_v1(raw_cut)
    snapshot = build_validated_state_snapshot(state, bundle)
    result = validate_and_compile_cut(
        envelope,
        snapshot,
        build_production_registry() if registry is None else registry,
    )
    assert isinstance(result, CompiledCut)
    return raw_cut, snapshot, result


def _plan_parameters(plan: ConstraintPlan) -> tuple[str, RegionKind, int]:
    group_id = plan.parameters["group_id"]
    region_kind = plan.parameters["region_kind"]
    capacity = plan.parameters["capacity"]
    assert type(group_id) is str
    assert region_kind in {"left_baseline", "bottom_baseline"}
    assert type(capacity) is int
    return group_id, cast(RegionKind, region_kind), capacity


@pytest.mark.parametrize(
    ("region_kind", "region_demand", "expected_capacity"),
    [
        ("left_baseline", 2, 1),
        ("bottom_baseline", 1, 0),
    ],
)
def test_production_f6_oracle_cut_compiles_and_matches_legacy(
    region_kind: RegionKind,
    region_demand: int,
    expected_capacity: int,
) -> None:
    state, bundle = _build_world()
    raw_cut, snapshot, compiled = _compile_cut(
        state,
        bundle,
        region_kind=region_kind,
        region_demand=region_demand,
    )
    legacy = validate_shape_packing_hall(
        raw_cut,
        state,
        state.canonical_rules or {},
    )
    capability = build_production_registry().capabilities["shape_packing_hall"]
    assert raw_cut.cert is not None
    cert = json.loads(raw_cut.cert.cert_payload)

    assert legacy.kind == "ok", legacy.detail
    assert capability.stage is CapabilityStage.COMPILABLE
    assert compiled.cut_id == raw_cut.cut_id
    assert compiled.snapshot_digest == snapshot.digest
    assert compiled.plan.family == "shape_packing_hall"
    assert compiled.plan.operation == "shape_packing_hall_le"
    assert compiled.plan.model_scope.ghost_policy == "bound"
    assert _plan_parameters(compiled.plan) == (
        _GROUP_ID,
        region_kind,
        expected_capacity,
    )
    assert cert["total_packable"] == expected_capacity
    assert cert["total_packable"] < cert["region_demand"]


def test_f6_empty_partition_is_a_valid_strict_cap_zero_proof() -> None:
    state, bundle = _build_world(all_baselines_blocked=True, demand=1)
    raw_cut, _snapshot, compiled = _compile_cut(
        state,
        bundle,
        region_kind="left_baseline",
        region_demand=1,
    )
    assert raw_cut.cert is not None
    cert = json.loads(raw_cut.cert.cert_payload)

    assert cert["partition_lens"] == []
    assert cert["partition_offsets"] == []
    assert cert["max_packable"] == []
    assert cert["total_packable"] == 0
    assert cert["region_demand"] == 1
    assert _plan_parameters(compiled.plan) == (
        _GROUP_ID,
        "left_baseline",
        0,
    )


def test_f6_reversed_one_by_l_shape_is_accepted_by_legacy_and_typed_paths() -> None:
    state, bundle = _build_world()
    raw_cut = _oracle_cut(
        state,
        region_kind="left_baseline",
        region_demand=2,
    )
    reversed_shape = _tampered_cut(
        raw_cut,
        lambda cert: cert.__setitem__("pose_shape_canonical", "3x1_rigid"),
    )

    legacy = validate_shape_packing_hall(
        reversed_shape,
        state,
        state.canonical_rules or {},
    )
    typed = validate_and_compile_cut(
        cut_to_envelope_v1(reversed_shape),
        build_validated_state_snapshot(state, bundle),
        build_production_registry(),
    )

    assert legacy.kind == "ok", legacy.detail
    assert isinstance(typed, CompiledCut)


def test_f6_empty_literal_tuple_is_rejected_by_legacy_and_typed_paths() -> None:
    state, _bundle = _build_world()
    with_empty_literals = replace(
        _oracle_cut(
            state,
            region_kind="left_baseline",
            region_demand=2,
        ),
        literals=(),
    )

    legacy = validate_shape_packing_hall(
        with_empty_literals,
        state,
        state.canonical_rules or {},
    )

    assert _F6_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT["adapter.geometric_empty_literals"] == "legacy-parity"
    assert legacy.kind != "ok"
    with pytest.raises(ValueError, match="geometric cuts require literals to be None"):
        cut_to_envelope_v1(with_empty_literals)


@pytest.mark.parametrize(
    "stage",
    [CapabilityStage.COMPILABLE, CapabilityStage.VALIDATED],
)
def test_f6_agnostic_scope_is_rejected_at_the_common_scope_boundary(
    stage: CapabilityStage,
) -> None:
    state, bundle = _build_world()
    raw_cut = _oracle_cut(
        state,
        region_kind="left_baseline",
        region_demand=2,
    )
    assert raw_cut.scope is not None
    agnostic = replace(
        raw_cut,
        scope=replace(raw_cut.scope, ghost_rect_id=GHOST_AGNOSTIC),
    )

    legacy = validate_shape_packing_hall(
        agnostic,
        state,
        state.canonical_rules or {},
    )
    registry = build_production_registry()
    production_capability = registry.capabilities["shape_packing_hall"]
    selected_capability = replace(
        production_capability,
        stage=stage,
        compiler_version=(production_capability.compiler_version if stage is CapabilityStage.COMPILABLE else None),
    )
    selected_registry = FamilyCapabilityRegistry(
        capabilities={
            **registry.capabilities,
            "shape_packing_hall": selected_capability,
        },
        plugins=dict(registry.plugins),
    )
    typed = validate_and_compile_cut(
        cut_to_envelope_v1(agnostic),
        build_validated_state_snapshot(state, bundle),
        selected_registry,
    )

    assert legacy.kind != "ok"
    assert _F6_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT["scope.requires_ghost_bound"] == "legacy-parity"
    assert isinstance(typed, CutRejection)
    assert typed.stage == "scope"
    assert typed.reason == "family capability requires a ghost-bound scope"


def _tampered_cut(cut: Cut, mutate: Callable[[dict[str, Any]], None]) -> Cut:
    assert cut.cert is not None
    cert = json.loads(cut.cert.cert_payload)
    assert type(cert) is dict
    mutate(cert)
    payload = canonical_bytes_for_cert(cert)
    cert_hash = hashlib.sha256(payload).hexdigest()
    return replace(
        cut,
        geometric_payload=payload,
        cert=replace(cut.cert, cert_payload=payload, cert_hash=cert_hash),
        oracle_cert_hash=cert_hash,
    )


def _set_many(cert: dict[str, Any], **changes: Any) -> None:
    cert.update(changes)


def _typed_rejects(
    state: BState,
    bundle: FrozenArtifactBundle,
    cut: Cut,
    *,
    registry: FamilyCapabilityRegistry | None = None,
) -> bool:
    try:
        envelope = cut_to_envelope_v1(cut)
    except (TypeError, ValueError):
        return True
    snapshot = build_validated_state_snapshot(state, bundle)
    result = validate_and_compile_cut(
        envelope,
        snapshot,
        build_production_registry() if registry is None else registry,
    )
    return isinstance(result, CutRejection)


def _replace_outer_cert_kind(cut: Cut) -> Cut:
    assert cut.cert is not None
    return replace(
        cut,
        cert=replace(cut.cert, cert_kind="drifted_outer_cert_kind"),
    )


def _wrong_cert_hash(cut: Cut) -> Cut:
    assert cut.cert is not None
    return replace(cut, cert=replace(cut.cert, cert_hash="0" * 64))


def _wrong_geometric_body(cut: Cut) -> Cut:
    assert cut.geometric_payload is not None
    return replace(cut, geometric_payload=cut.geometric_payload + b" ")


def _structurally_inconsistent_preimage(
    preimage: ScopeIdentityPreimageV1,
) -> ScopeIdentityPreimageV1:
    forged = copy(preimage)
    object.__setattr__(
        forged,
        "exterior_blocks",
        tuple(sorted((*preimage.exterior_blocks, (69, 69)))),
    )
    return forged


def _blocked_identity_drift(
    preimage: ScopeIdentityPreimageV1,
) -> ScopeIdentityPreimageV1:
    return replace(
        preimage,
        blocked_cells=tuple(sorted((*preimage.blocked_cells, (69, 69)))),
    )


def _exterior_identity_drift(
    preimage: ScopeIdentityPreimageV1,
) -> ScopeIdentityPreimageV1:
    assert preimage.exterior_blocks
    return replace(preimage, exterior_blocks=preimage.exterior_blocks[1:])


def _ghost_identity_drift(
    preimage: ScopeIdentityPreimageV1,
) -> ScopeIdentityPreimageV1:
    assert preimage.ghost_rect is not None
    x, y, width, height = preimage.ghost_rect
    return replace(preimage, ghost_rect=(x + 1, y, width, height))


def test_f6_accept_set_audit_has_exact_ratified_typed_only_rows() -> None:
    typed_only = {
        key for key, classification in _F6_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT.items() if classification == "typed-only"
    }

    assert typed_only == {
        "adapter.payload_schema_version",
        "adapter.quarantine",
        "adapter.outer_cert_kind",
        "adapter.identity_preimage_presence",
        "adapter.identity_preimage_structural_consistency",
        "adapter.identity_preimage_blocked_identity",
        "adapter.identity_preimage_exterior_identity",
        "adapter.identity_preimage_ghost_identity",
        "scope.exterior_preimage_snapshot_currentness",
        "scope.nonempty_assumptions",
    }


@pytest.mark.parametrize(
    ("audit_key", "mutate", "message"),
    [
        (
            "adapter.payload_schema_version",
            lambda cut: replace(cut, payload_schema_version=2),
            "payload_schema_version must be exact int 1",
        ),
        (
            "adapter.quarantine",
            lambda cut: replace(
                cut,
                is_quarantined=True,
            ),
            "quarantined cuts cannot enter",
        ),
        (
            "adapter.quarantine",
            lambda cut: replace(cut, quarantine_reason="quarantined-by-test"),
            "quarantined cuts cannot enter",
        ),
        (
            "adapter.outer_cert_kind",
            _replace_outer_cert_kind,
            "cert_kind differs from proof cert_kind",
        ),
    ],
    ids=("schema-v2", "quarantine-flag", "quarantine-reason", "outer-cert-kind"),
)
def test_f6_ratified_adapter_tightenings_reject_legacy_accepted_cuts(
    audit_key: str,
    mutate: Callable[[Cut], Cut],
    message: str,
) -> None:
    state, _bundle = _build_world()
    raw_cut = _oracle_cut(
        state,
        region_kind="left_baseline",
        region_demand=2,
    )
    attacked = mutate(raw_cut)

    legacy = validate_shape_packing_hall(
        attacked,
        state,
        state.canonical_rules or {},
    )

    assert _F6_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT[audit_key] == "typed-only"
    assert legacy.kind == "ok", legacy.detail
    with pytest.raises(ValueError, match=message):
        cut_to_envelope_v1(attacked)


@pytest.mark.parametrize(
    "mutate",
    [
        _wrong_cert_hash,
        lambda cut: replace(cut, oracle_cert_hash="0" * 64),
        _wrong_geometric_body,
    ],
    ids=("cert-hash", "oracle-cert-hash", "geometric-body"),
)
def test_f6_integrity_bookkeeping_rejection_is_shared_legacy_parity(
    mutate: Callable[[Cut], Cut],
) -> None:
    state, _bundle = _build_world()
    attacked = mutate(
        _oracle_cut(
            state,
            region_kind="left_baseline",
            region_demand=2,
        )
    )

    assert _F6_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT["adapter.integrity_bookkeeping"] == "legacy-parity"
    assert validate_cut_integrity(attacked) is not None
    with pytest.raises(ValueError, match="v1 cut integrity failed"):
        cut_to_envelope_v1(attacked)


@pytest.mark.parametrize(
    ("audit_key", "mutate", "message"),
    [
        (
            "adapter.identity_preimage_structural_consistency",
            _structurally_inconsistent_preimage,
            "exterior_blocks must be a subset",
        ),
        (
            "adapter.identity_preimage_blocked_identity",
            _blocked_identity_drift,
            "blocked-cells identity differs",
        ),
        (
            "adapter.identity_preimage_exterior_identity",
            _exterior_identity_drift,
            "exterior-blocks identity differs",
        ),
        (
            "adapter.identity_preimage_ghost_identity",
            _ghost_identity_drift,
            "ghost-rect identity differs",
        ),
    ],
    ids=("structural", "blocked", "exterior", "ghost"),
)
def test_f6_preimage_inconsistencies_are_ratified_typed_only_rejections(
    audit_key: str,
    mutate: Callable[[ScopeIdentityPreimageV1], ScopeIdentityPreimageV1],
    message: str,
) -> None:
    state, _bundle = _build_world()
    raw_cut = _oracle_cut(
        state,
        region_kind="left_baseline",
        region_demand=2,
    )
    assert raw_cut.scope is not None
    preimage = raw_cut.scope.identity_preimage
    assert isinstance(preimage, ScopeIdentityPreimageV1)
    attacked = replace(
        raw_cut,
        scope=replace(raw_cut.scope, identity_preimage=mutate(preimage)),
    )

    legacy = validate_shape_packing_hall(
        attacked,
        state,
        state.canonical_rules or {},
    )

    assert _F6_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT[audit_key] == "typed-only"
    assert legacy.kind == "ok", legacy.detail
    with pytest.raises(ValueError, match=message):
        cut_to_envelope_v1(attacked)


def test_f6_coherent_wrong_exterior_preimage_is_rejected_by_snapshot_currentness() -> None:
    state, bundle = _build_world()
    raw_cut = _oracle_cut(
        state,
        region_kind="left_baseline",
        region_demand=2,
    )
    assert raw_cut.scope is not None
    preimage = raw_cut.scope.identity_preimage
    assert isinstance(preimage, ScopeIdentityPreimageV1)
    wrong_preimage = _exterior_identity_drift(preimage)
    _ghost_id, _blocked_hash, wrong_exterior_hash = compute_scope_identity_legacy_hashes(wrong_preimage)
    attacked = replace(
        raw_cut,
        scope=replace(
            raw_cut.scope,
            identity_preimage=wrong_preimage,
            exterior_blocks_hash=wrong_exterior_hash,
        ),
    )

    legacy = validate_shape_packing_hall(
        attacked,
        state,
        state.canonical_rules or {},
    )
    envelope = cut_to_envelope_v1(attacked)
    typed = validate_and_compile_cut(
        envelope,
        build_validated_state_snapshot(state, bundle),
        build_production_registry(),
    )

    assert _F6_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT["scope.exterior_preimage_snapshot_currentness"] == "typed-only"
    assert legacy.kind == "ok", legacy.detail
    assert isinstance(typed, CutRejection)
    assert typed.stage == "scope"
    assert typed.reason == "scope exterior-block identity is stale"


@pytest.mark.parametrize(
    ("label", "region_kind", "region_demand", "mutate"),
    [
        (
            "closed_14_field_schema",
            "left_baseline",
            2,
            lambda cert: cert.__setitem__("future_field", 1),
        ),
        (
            "cert_kind",
            "left_baseline",
            2,
            lambda cert: cert.__setitem__("cert_kind", "not_hall"),
        ),
        (
            "closed_region_enum",
            "left_baseline",
            2,
            lambda cert: cert.__setitem__("region_kind", "right_baseline"),
        ),
        (
            "strict_scalar_schema",
            "left_baseline",
            2,
            lambda cert: cert.__setitem__("group_demand", True),
        ),
        (
            "partition_internal_consistency",
            "left_baseline",
            2,
            lambda cert: cert.__setitem__("partition_offsets", []),
        ),
        (
            "strict_hall_inequality",
            "left_baseline",
            2,
            lambda cert: cert.__setitem__("region_demand", 1),
        ),
        (
            "group_source_of_truth",
            "left_baseline",
            2,
            lambda cert: cert.__setitem__("group_demand", 3),
        ),
        (
            "facility_template_match",
            "left_baseline",
            2,
            lambda cert: _set_many(
                cert,
                pose_length=4,
                pose_shape_canonical="1x4_rigid",
                max_packable=[0],
                total_packable=0,
            ),
        ),
        (
            "region_demand_lower_bound",
            "bottom_baseline",
            1,
            lambda cert: cert.__setitem__("region_demand", 2),
        ),
        (
            "ghost_scope_binding",
            "left_baseline",
            2,
            lambda cert: cert.__setitem__("ghost_rect_repr", [4, 5, 1, 1]),
        ),
        (
            "exterior_digest_recompute",
            "left_baseline",
            2,
            lambda cert: cert.__setitem__("exterior_blocks_digest", "0" * 16),
        ),
        (
            "partition_and_max_recompute",
            "left_baseline",
            2,
            lambda cert: _set_many(
                cert,
                partition_lens=[2],
                partition_offsets=[0],
                max_packable=[0],
                total_packable=0,
            ),
        ),
    ],
)
def test_f6_legacy_and_typed_paths_jointly_reject_all_semantic_tampers(
    label: str,
    region_kind: RegionKind,
    region_demand: int,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    """Each legacy proof obligation has a representation-consistent red case."""

    state, bundle = _build_world()
    raw_cut = _oracle_cut(
        state,
        region_kind=region_kind,
        region_demand=region_demand,
    )
    tampered = _tampered_cut(raw_cut, mutate)

    legacy = validate_shape_packing_hall(
        tampered,
        state,
        state.canonical_rules or {},
    )

    assert legacy.kind != "ok", f"{label}: legacy accepted tampered proof"
    assert _typed_rejects(state, bundle, tampered), f"{label}: typed chain accepted tampered proof"


def test_f6_validator_version_cannot_bypass_unconditional_plugin_obligations() -> None:
    state, bundle = _build_world()
    raw_cut = _oracle_cut(
        state,
        region_kind="left_baseline",
        region_demand=2,
    )
    tampered = _tampered_cut(
        raw_cut,
        lambda cert: cert.__setitem__("partition_offsets", [1]),
    )
    registry = build_production_registry()
    attacker_capability = replace(
        registry.capabilities["shape_packing_hall"],
        validator_version="attacker-version-with-no-obligations",
    )
    attacker_registry = FamilyCapabilityRegistry(
        capabilities={
            **registry.capabilities,
            "shape_packing_hall": attacker_capability,
        },
        plugins=dict(registry.plugins),
    )

    legacy = validate_shape_packing_hall(
        tampered,
        state,
        state.canonical_rules or {},
    )
    typed = validate_and_compile_cut(
        cut_to_envelope_v1(tampered),
        build_validated_state_snapshot(state, bundle),
        attacker_registry,
    )

    assert legacy.kind != "ok"
    assert isinstance(typed, CutRejection)
    assert typed.stage == "proof"
    assert typed.reason == "F6 partition_offsets differs from the snapshot recomputation"


def test_old_f6_cut_without_identity_preimage_is_expected_typed_only_rejection() -> None:
    state, _bundle = _build_world()
    raw_cut = _oracle_cut(
        state,
        region_kind="left_baseline",
        region_demand=2,
    )
    assert raw_cut.scope is not None
    legacy_only = replace(
        raw_cut,
        scope=replace(raw_cut.scope, identity_preimage=None),
    )

    legacy = validate_shape_packing_hall(
        legacy_only,
        state,
        state.canonical_rules or {},
    )
    assert _F6_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT["adapter.identity_preimage_presence"] == "typed-only"
    assert legacy.kind == "ok", legacy.detail
    with pytest.raises((TypeError, ValueError)):
        cut_to_envelope_v1(legacy_only)


def test_nonempty_f6_scope_assumptions_are_expected_typed_only_rejection() -> None:
    state, bundle = _build_world()
    raw_cut = _oracle_cut(
        state,
        region_kind="left_baseline",
        region_demand=2,
    )
    assert raw_cut.scope is not None
    with_assumption = replace(
        raw_cut,
        scope=replace(
            raw_cut.scope,
            active_assumptions=(
                Assumption(
                    key="placement_rule",
                    value=f"{_GROUP_ID}=left_or_bottom_boundary",
                ),
            ),
        ),
    )

    legacy = validate_shape_packing_hall(
        with_assumption,
        state,
        state.canonical_rules or {},
    )
    envelope = cut_to_envelope_v1(with_assumption)
    snapshot = build_validated_state_snapshot(state, bundle)
    typed = validate_and_compile_cut(
        envelope,
        snapshot,
        build_production_registry(),
    )

    assert legacy.kind == "ok", legacy.detail
    assert _F6_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT["scope.nonempty_assumptions"] == "typed-only"
    assert isinstance(typed, CutRejection)
    assert typed.stage == "scope"


class _RecordingPlugin:
    def __init__(self, delegate: FamilyPlugin) -> None:
        self.delegate = delegate
        self.snapshots: list[ValidatedStateSnapshot] = []
        self.returned_proofs: list[FrozenFamilyProof] = []
        self.proof_arguments: list[FrozenFamilyProof] = []

    def parse_and_validate_proof(
        self,
        proof_payload: bytes,
        snapshot: ValidatedStateSnapshot,
    ) -> FrozenFamilyProof:
        self.snapshots.append(snapshot)
        proof = self.delegate.parse_and_validate_proof(proof_payload, snapshot)
        self.returned_proofs.append(proof)
        return proof

    def derive_body(self, proof: FrozenFamilyProof) -> object:
        self.proof_arguments.append(proof)
        return self.delegate.derive_body(proof)

    def compile(
        self,
        body: object,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> ConstraintPlan:
        self.proof_arguments.append(proof)
        self.snapshots.append(snapshot)
        return self.delegate.compile(body, proof, snapshot)

    def validate_plan(
        self,
        plan: ConstraintPlan,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> None:
        self.proof_arguments.append(proof)
        self.snapshots.append(snapshot)
        self.delegate.validate_plan(plan, proof, snapshot)


def test_f6_verifier_and_compiler_share_one_snapshot_and_frozen_proof() -> None:
    state, bundle = _build_world()
    raw_cut = _oracle_cut(
        state,
        region_kind="left_baseline",
        region_demand=2,
    )
    snapshot = build_validated_state_snapshot(state, bundle)
    production = build_production_registry()
    recorder = _RecordingPlugin(production.plugins["shape_packing_hall"])
    plugins = dict(production.plugins)
    plugins["shape_packing_hall"] = recorder
    registry = FamilyCapabilityRegistry(
        capabilities=production.capabilities,
        plugins=plugins,
    )

    result = validate_and_compile_cut(
        cut_to_envelope_v1(raw_cut),
        snapshot,
        registry,
    )

    assert isinstance(result, CompiledCut)
    assert len(recorder.returned_proofs) == 1
    proof = recorder.returned_proofs[0]
    assert isinstance(proof, ShapePackingHallProof)
    assert len(recorder.snapshots) == 3
    assert all(argument is snapshot for argument in recorder.snapshots)
    assert all(argument is proof for argument in recorder.proof_arguments)
    assert len(recorder.proof_arguments) == 3


def _drifted_poses() -> list[dict[str, Any]]:
    poses = deepcopy(list(_ALL_POSES))
    poses[1]["occupied_cells"] = [[3, 1], [4, 1], [5, 1]]
    return poses


def test_f6_projection_and_semantic_fingerprint_are_stable_and_domain_bound() -> None:
    state_a, bundle_a = _build_world()
    state_b, bundle_b = _build_world()
    raw_a, snapshot_a, compiled_a = _compile_cut(
        state_a,
        bundle_a,
        region_kind="left_baseline",
        region_demand=2,
        iter_index=1,
    )
    raw_b, snapshot_b, compiled_b = _compile_cut(
        state_b,
        bundle_b,
        region_kind="left_baseline",
        region_demand=2,
        iter_index=2,
    )

    assert raw_a.cut_id != raw_b.cut_id
    assert snapshot_a.shape_packing_hall_master_domain_projection == (
        snapshot_b.shape_packing_hall_master_domain_projection
    )
    assert snapshot_a.shape_packing_hall_master_domain_projection != (snapshot_a.master_domain_projection)
    assert (
        shape_packing_hall_master_domain_projection_v1(
            snapshot_a,
            _GROUP_ID,
        )
        == snapshot_a.shape_packing_hall_master_domain_projection
    )
    assert compiled_a.plan.digest == compiled_b.plan.digest
    assert compiled_a.plan.semantic_fingerprint == (compiled_b.plan.semantic_fingerprint)
    assert compiled_a.digest != compiled_b.digest

    drift_state, drift_bundle = _build_world(poses=_drifted_poses())
    _raw_drift, drift_snapshot, drift_compiled = _compile_cut(
        drift_state,
        drift_bundle,
        region_kind="left_baseline",
        region_demand=2,
        iter_index=1,
    )
    assert drift_snapshot.shape_packing_hall_master_domain_projection != (
        snapshot_a.shape_packing_hall_master_domain_projection
    )
    assert drift_compiled.plan.model_scope.domain_fingerprint != (compiled_a.plan.model_scope.domain_fingerprint)
    assert drift_compiled.plan.semantic_fingerprint != (compiled_a.plan.semantic_fingerprint)


def _pose_cells() -> dict[str, tuple[tuple[int, int], ...]]:
    result: dict[str, tuple[tuple[int, int], ...]] = {}
    for pose in _ALL_POSES:
        pose_id = cast(str, pose["pose_id"])
        raw_cells = cast(list[list[int]], pose["occupied_cells"])
        result[pose_id] = tuple((cell[0], cell[1]) for cell in raw_cells)
    return result


def _interpret_f6_plan(
    plan: ConstraintPlan,
    *,
    selected_pose_ids: Sequence[str],
    condition_active: bool,
) -> bool:
    """Independent second implementation of ``shape_packing_hall_le``."""

    assert plan.operation == "shape_packing_hall_le"
    if plan.model_scope.ghost_policy == "bound" and not condition_active:
        return True
    _group_id, region_kind, capacity = _plan_parameters(plan)
    cells_by_pose = _pose_cells()

    def on_baseline(cell: tuple[int, int]) -> bool:
        if region_kind == "left_baseline":
            return cell[1] == 0
        return cell[0] == 0

    presence_count = sum(
        1 for pose_id in selected_pose_ids if all(on_baseline(cell) for cell in cells_by_pose[pose_id])
    )
    return presence_count <= capacity


@pytest.mark.parametrize(
    (
        "region_kind",
        "region_demand",
        "selected_pose_ids",
        "condition_active",
        "expected",
    ),
    [
        ("left_baseline", 2, ("left_a",), True, True),
        ("left_baseline", 2, ("left_a", "left_b"), True, False),
        ("left_baseline", 2, ("left_a", "interior"), True, True),
        ("left_baseline", 2, ("left_a", "left_b"), False, True),
        ("bottom_baseline", 1, ("bottom",), True, False),
        ("bottom_baseline", 1, ("left_a", "interior"), True, True),
    ],
)
def test_independent_f6_plan_interpreter_covers_boundaries_and_dormancy(
    region_kind: RegionKind,
    region_demand: int,
    selected_pose_ids: tuple[str, ...],
    condition_active: bool,
    expected: bool,
) -> None:
    state, bundle = _build_world()
    _raw_cut, _snapshot, compiled = _compile_cut(
        state,
        bundle,
        region_kind=region_kind,
        region_demand=region_demand,
    )

    assert (
        _interpret_f6_plan(
            compiled.plan,
            selected_pose_ids=selected_pose_ids,
            condition_active=condition_active,
        )
        is expected
    )


def _build_tiny_master(
    poses: Sequence[Mapping[str, Any]],
) -> MasterPlacementModel:
    instances = [
        {
            "instance_id": f"port_{index:03d}",
            "facility_type": _FACILITY_TYPE,
            "operation_type": _OPERATION_TYPE,
            "is_mandatory": True,
            "bound_type": "exact",
        }
        for index in (1, 2)
    ]
    pools = {
        _FACILITY_TYPE: [deepcopy(dict(pose)) for pose in poses],
    }
    rules = {
        "globals": {"grid": {"width": 6, "height": 6}},
        "facility_templates": {
            _FACILITY_TYPE: {
                "placement_rule": "left_or_bottom_boundary",
                "dimensions": {"w": 3, "h": 1},
                "needs_power": False,
            }
        },
    }
    core = MasterPlacementModel.build_exact_core(
        instances,
        pools,
        rules,
        skip_power_coverage=True,
    )
    return MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))


def test_f6_snapshot_and_live_master_rows_share_one_domain_projection_schema() -> None:
    state, bundle = _build_world()
    snapshot = build_validated_state_snapshot(state, bundle)
    master = _build_tiny_master(_ALL_POSES)
    delegate = master._coordinate_delegate
    assert delegate is not None

    live_pools = {_FACILITY_TYPE: master.facility_pools[_FACILITY_TYPE]}
    pose_tuples = delegate._template_pose_tuple_by_idx[_FACILITY_TYPE]
    registration_rows: list[object] = [
        {
            "facility_type": _FACILITY_TYPE,
            "poses": [
                {
                    "anchor": [pose_tuple[0], pose_tuple[1]],
                    "mode_id": pose_tuple[2],
                    "pose_id": str(master.facility_pools[_FACILITY_TYPE][pose_index]["pose_id"]),
                    "pose_index": pose_index,
                }
                for pose_index, pose_tuple in sorted(pose_tuples.items())
            ],
        }
    ]
    slot_rows: list[object] = []
    for group_id, slots in sorted(delegate.mandatory_slots.items()):
        if group_id != _GROUP_ID:
            continue
        for slot in slots:
            slot_rows.append(
                {
                    "allowed_pose_tuples": [list(pose_tuple) for pose_tuple in sorted(slot.allowed_tuples)],
                    "candidate_pose_count": slot.candidate_pose_count,
                    "facility_type": slot.template,
                    "group_id": group_id,
                    "slot_index": slot.slot_index,
                    "slot_key": str(slot.key),
                    "slot_kind": "mandatory",
                    "template_dimensions": [slot.dims[0], slot.dims[1]],
                }
            )

    live_projection = master_domain_projection_v1(
        family_subset="shape_packing_hall",
        facility_pool_projection=master_domain_facility_pool_projection_v1(live_pools),
        mandatory_slot_rows=slot_rows,
        template_pose_registration_rows=registration_rows,
    )

    assert live_projection == snapshot.shape_packing_hall_master_domain_projection


def _lower_plan(
    plan: ConstraintPlan,
    master: MasterPlacementModel,
    *,
    condition_lits: Sequence[Any],
) -> bool:
    group_id, region_kind, capacity = _plan_parameters(plan)
    return master.add_baseline_packing_cut(
        group_id=group_id,
        region_kind=region_kind,
        capacity=capacity,
        condition_lits=condition_lits,
    )


@pytest.mark.parametrize(
    ("region_kind", "region_demand", "expected_terms"),
    [
        ("left_baseline", 2, 2),
        ("bottom_baseline", 1, 1),
    ],
)
def test_real_master_counts_only_poses_whose_entire_body_is_on_the_baseline(
    region_kind: RegionKind,
    region_demand: int,
    expected_terms: int,
) -> None:
    state, bundle = _build_world()
    _raw_cut, _snapshot, compiled = _compile_cut(
        state,
        bundle,
        region_kind=region_kind,
        region_demand=region_demand,
    )
    master = _build_tiny_master(_ALL_POSES)
    assert master._group_id_by_instance["port_001"] == _GROUP_ID
    condition = master.u_vars[35]

    assert _lower_plan(compiled.plan, master, condition_lits=(condition,))
    stats = master.build_stats["coordinate_baseline_packing_last_cut"]
    assert stats["presence_terms"] == expected_terms
    assert stats["region_kind"] == region_kind
    assert "interior" not in {
        pose_id
        for pose_id, cells in _pose_cells().items()
        if all((cell[1] == 0 if region_kind == "left_baseline" else cell[0] == 0) for cell in cells)
    }


def test_real_master_f6_cut_is_dormant_until_its_anchor_is_pinned() -> None:
    """Anchor-free is FEASIBLE; pinning the bound anchor makes the cap bite."""

    # Both 1x3 bodies lie horizontally and entirely on y=0.  This guards the
    # master-side all-cells predicate: a partly-on-baseline fixture would yield
    # zero terms and be refused rather than test the F6 inequality.
    for pose in _LEFT_ONLY_POSES:
        cells = cast(list[list[int]], pose["occupied_cells"])
        assert len(cells) == 3
        assert all(cell[1] == 0 for cell in cells)

    state, bundle = _build_world(poses=_LEFT_ONLY_POSES)
    raw_cut, _snapshot, compiled = _compile_cut(
        state,
        bundle,
        region_kind="left_baseline",
        region_demand=2,
    )
    assert raw_cut.cert is not None
    cert = json.loads(raw_cut.cert.cert_payload)
    assert cert["total_packable"] == 1
    assert cert["region_demand"] == 2
    assert cert["total_packable"] < cert["region_demand"]

    master = _build_tiny_master(_LEFT_ONLY_POSES)
    assert master._group_id_by_instance["port_001"] == _GROUP_ID
    bound_anchor = master.u_vars[35]
    assert _lower_plan(
        compiled.plan,
        master,
        condition_lits=(bound_anchor,),
    )
    assert master.build_stats["coordinate_baseline_packing_last_cut"] == {
        "group_id": _GROUP_ID,
        "region_kind": "left_baseline",
        "capacity": 1,
        "presence_terms": 2,
        "semantics": "baseline_packing_count_ghost_conditioned_v1",
    }

    # With the anchor free, the solver selects another anchor and the cut sleeps.
    assert master.solve(time_limit_seconds=5.0) in {
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    }
    delegate = master._coordinate_delegate
    assert delegate is not None
    delegate.model.Add(bound_anchor == 1)
    assert master.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE
