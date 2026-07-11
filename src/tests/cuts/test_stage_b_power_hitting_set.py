"""RFC-001 Stage-B B4 differential tests for F7 power_hitting_set.

The production attach path remains raw until B5.  These tests build one
bundle-backed F7 world from canonical facility/pole pools, drive real v1 oracle
cuts through the typed compiler explicitly, and exercise the existing master
coverer gate without borrowing the old Step-8 fixture.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from copy import copy, deepcopy
from dataclasses import replace
from typing import Any, cast

import pytest
from ortools.sat.python import cp_model

from src.cuts import state_snapshot as state_snapshot_module
from src.cuts.families.power_hitting_set import validate_power_hitting_set
from src.cuts.families.power_hitting_set_typed import (
    PowerHittingSetProof,
    power_hitting_set_master_domain_projection_v1,
)
from src.cuts.frozen_artifacts import FrozenArtifactBundle, build_frozen_artifact_bundle
from src.cuts.lifecycle import (
    GHOST_AGNOSTIC,
    AnonymousSlotRef,
    Assumption,
    BState,
    Cut,
    CutLiteral,
    CutScope,
    GroupState,
    OracleCert,
    ScopeIdentityPreimageV1,
    canonical_bytes_for_cert,
    capture_scope_identity_preimage_v1,
    compute_scope_identity_legacy_hashes,
    compute_source_digest,
)
from src.cuts.oracles.power_cover_oracle import generate_power_hitting_set_cuts
from src.cuts.state_snapshot import (
    SnapshotValidationError,
    ValidatedStateSnapshot,
    blocked_cells_digest_v1,
    build_validated_state_snapshot,
    power_hitting_set_master_domain_projection_v1 as f7_projection_digest_v1,
)
from src.cuts.typed_platform import (
    CapabilityStage,
    CompiledCut,
    ConstraintPlan,
    CutRejection,
    FamilyCapabilityRegistry,
    build_production_registry,
    cut_to_envelope_v1,
    validate_and_compile_cut,
)
from src.models.master_model import MasterPlacementModel


Cell = tuple[int, int]

_GROUP_ID = "group::powered_widget::assembly::0"
_FACILITY_TYPE = "powered_widget"
_OPERATION_TYPE = "assembly"
_TARGET_POSE_ID = "pose_mid"
_POLE_POSE_ID = "power_pole_0"
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

_POWERED_POSES: tuple[dict[str, Any], ...] = (
    {
        "pose_id": "pose_left",
        "anchor": {"x": 0, "y": 0},
        "occupied_cells": [[0, 0]],
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": None,
    },
    {
        "pose_id": _TARGET_POSE_ID,
        "anchor": {"x": 4, "y": 0},
        "occupied_cells": [[4, 0]],
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": None,
    },
    {
        "pose_id": "pose_right",
        "anchor": {"x": 8, "y": 0},
        "occupied_cells": [[8, 0]],
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": None,
    },
)


def _canonical_pole_coverage() -> list[list[int]]:
    # A 2x2 pole at (2,1), radius five, clipped to the non-negative quadrant.
    return [[x, y] for x in range(0, 9) for y in range(0, 8)]


_POWER_POLES: tuple[dict[str, Any], ...] = (
    {
        "pose_id": _POLE_POSE_ID,
        "anchor": {"x": 2, "y": 1},
        "occupied_cells": [[2, 1], [2, 2], [3, 1], [3, 2]],
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": _canonical_pole_coverage(),
    },
)

_SECOND_POWER_POLE: dict[str, Any] = {
    "pose_id": "power_pole_1",
    "anchor": {"x": 12, "y": 1},
    "occupied_cells": [[12, 1], [12, 2], [13, 1], [13, 2]],
    "input_port_cells": [],
    "output_port_cells": [],
    "power_coverage_cells": [[x, y] for x in range(7, 19) for y in range(0, 8)],
}
_TWO_POWER_POLES: tuple[dict[str, Any], ...] = (
    _POWER_POLES[0],
    _SECOND_POWER_POLE,
)

_FACILITY_POSE_CELLS = frozenset({(0, 0), (4, 0), (8, 0)})
_GHOST_CAUSED_BLOCKS = frozenset(
    (x, y) for x in range(0, 11) for y in range(0, 7) if (x, y) not in _FACILITY_POSE_CELLS
)

# B4 accept-set completeness audit.  Every reachable adapter/plugin rejection
# category is classified as a ratified typed-only tightening, a legacy parity
# obligation, or an internal invariant inaccessible to a raw cut.
_F7_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT = {
    "adapter.exact_cut_and_constructor_schema": "typed-internal-invariant",
    "adapter.payload_schema_version": "typed-only",
    "adapter.quarantine": "typed-only",
    "adapter.integrity_bookkeeping": "legacy-parity",
    "adapter.cert_and_scope_presence": "legacy-parity",
    "adapter.literal_nonempty": "legacy-parity",
    "adapter.shared_cert_payload_schema": "legacy-parity",
    "adapter.outer_cert_kind": "typed-only",
    "adapter.literal_group_pose_projection": "legacy-parity",
    "adapter.literal_slot_zero_placeholder": "typed-only",
    "adapter.identity_preimage_presence": "typed-only",
    "adapter.identity_preimage_structural_consistency": "typed-only",
    "adapter.identity_preimage_blocked_identity": "typed-only",
    "adapter.identity_preimage_exterior_identity": "typed-only",
    "adapter.identity_preimage_ghost_identity": "typed-only",
    "adapter.legacy_scope_identity_recompute": "legacy-parity",
    "scope.exterior_preimage_snapshot_currentness": "typed-only",
    "scope.required_dependency_set": "typed-only",
    "scope.nonempty_assumptions": "typed-only",
    "scope.requires_ghost_bound": "legacy-parity",
    "plugin.closed_schema_and_cert_kind": "legacy-parity",
    "plugin.strict_scalar_and_cell_schema": "legacy-parity",
    "plugin.pole_radius_int_float_normalization": "legacy-parity",
    "plugin.snapshot_ghost_and_exterior": "legacy-parity",
    "plugin.snapshot_group_and_template": "legacy-parity",
    "plugin.snapshot_pole_source_of_truth": "legacy-parity",
    "plugin.snapshot_pose_registry": "legacy-parity",
    "plugin.full_coverset_empty": "legacy-parity",
    "plugin.ghost_only_coverset_empty": "legacy-parity",
    "plugin.compiler_and_plan_self_checks": "typed-internal-invariant",
}


def _facility_templates(*, include_noise: bool = False) -> dict[str, Any]:
    templates: dict[str, Any] = {
        _FACILITY_TYPE: {
            "placement_rule": "free",
            "dimensions": {"w": 1, "h": 1},
            "needs_power": True,
        },
        "power_pole": {
            "placement_rule": "free",
            "dimensions": {"w": 2, "h": 2},
            "needs_power": False,
            "power_coverage_radius": 5,
        },
    }
    if include_noise:
        templates["unpowered_noise"] = {
            "placement_rule": "free",
            "dimensions": {"w": 1, "h": 1},
            "needs_power": False,
        }
    return templates


def _candidate_placements(
    *,
    powered_poses: Sequence[Mapping[str, Any]] = _POWERED_POSES,
    pole_poses: Sequence[Mapping[str, Any]] = _POWER_POLES,
    include_noise: bool = False,
) -> dict[str, Any]:
    pools: dict[str, Any] = {
        _FACILITY_TYPE: [deepcopy(dict(pose)) for pose in powered_poses],
        "power_pole": [deepcopy(dict(pose)) for pose in pole_poses],
    }
    if include_noise:
        pools["unpowered_noise"] = [
            {
                "pose_id": "noise_pose",
                "anchor": {"x": 69, "y": 69},
                "occupied_cells": [[69, 69]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ]
    return {"facility_pools": pools}


def _build_world(
    *,
    cover_mode: str = "ghost",
    powered_poses: Sequence[Mapping[str, Any]] = _POWERED_POSES,
    pole_poses: Sequence[Mapping[str, Any]] = _POWER_POLES,
    include_noise: bool = False,
) -> tuple[BState, FrozenArtifactBundle]:
    templates = _facility_templates(include_noise=include_noise)
    canonical_rules: dict[str, Any] = {
        "globals": {"grid": {"width": 70, "height": 70}},
        "facility_templates": templates,
    }
    candidates = _candidate_placements(
        powered_poses=powered_poses,
        pole_poses=pole_poses,
        include_noise=include_noise,
    )
    instance_mapping = {_GROUP_ID: _FACILITY_TYPE}

    if cover_mode == "ghost":
        ghost_rect = (0, 0, 1, 1)
        ghost_cells = frozenset({(0, 0)})
        exterior_blocks = _GHOST_CAUSED_BLOCKS
        cell_owner: dict[Cell, tuple[str, int]] = {}
    elif cover_mode == "live":
        ghost_rect = (60, 60, 1, 1)
        ghost_cells = frozenset({(60, 60)})
        exterior_blocks = frozenset()
        cell_owner = {}
    elif cover_mode == "cell_owner":
        ghost_rect = (60, 60, 1, 1)
        ghost_cells = frozenset({(60, 60)})
        exterior_blocks = frozenset()
        cell_owner = {cell: (_GROUP_ID, 0) for cell in _GHOST_CAUSED_BLOCKS}
    else:  # pragma: no cover - helper contract
        raise AssertionError(f"unknown cover_mode={cover_mode!r}")

    pose_ids = frozenset(cast(str, pose["pose_id"]) for pose in powered_poses)
    state = BState(
        groups={
            _GROUP_ID: GroupState(
                group_id=_GROUP_ID,
                demand=2,
                pose_domain=pose_ids,
            )
        },
        cell_owner=cell_owner,
        ghost_rect=ghost_rect,
        ghost_cells=ghost_cells,
        exterior_blocks=exterior_blocks,
        artifact_hashes=dict(_ARTIFACT_HASHES),
        available_oracle_versions=frozenset({"power_cover_v2_stencil"}),
        canonical_rules=canonical_rules,
        candidate_placements=candidates,
        facility_templates=templates,
        instance_to_facility_type=instance_mapping,
    )
    state.source_digest = compute_source_digest(state)
    bundle = build_frozen_artifact_bundle(
        canonical_rules=canonical_rules,
        candidate_placements=candidates,
        facility_templates=templates,
        instance_to_facility_type=instance_mapping,
        artifact_hashes=_ARTIFACT_HASHES,
    )
    return state, bundle


def _oracle_cut(state: BState, *, iter_index: int = -1) -> Cut:
    previous = os.environ.get("EXACT_F7_GENERATOR_ENABLED")
    os.environ["EXACT_F7_GENERATOR_ENABLED"] = "1"
    try:
        cuts = generate_power_hitting_set_cuts(
            state,
            target_poses=[(_GROUP_ID, _TARGET_POSE_ID)],
            iter_index=iter_index,
        )
    finally:
        if previous is None:
            os.environ.pop("EXACT_F7_GENERATOR_ENABLED", None)
        else:
            os.environ["EXACT_F7_GENERATOR_ENABLED"] = previous
    assert len(cuts) == 1
    cut = cuts[0]
    assert cut.oracle_name == "power_cover_v2_stencil"
    assert cut.scope is not None
    assert cut.scope.identity_preimage is not None
    assert cut.scope.active_assumptions == ()
    assert cut.literals is not None
    assert cut.literals[0].slot_ref.slot_index == 0
    return cut


def _manual_cut(state: BState, *, pole_radius: int | float = 5.0) -> Cut:
    preimage = capture_scope_identity_preimage_v1(state)
    ghost_id, blocked_hash, exterior_hash = compute_scope_identity_legacy_hashes(preimage)
    payload = canonical_bytes_for_cert(
        {
            "cert_kind": "power_cover_emptyset_ghost",
            "facility_group": _GROUP_ID,
            "facility_pose_id": _TARGET_POSE_ID,
            "facility_cells": [[4, 0]],
            "pole_radius": pole_radius,
            "pole_shape_canonical": "2x2_rigid",
            "ghost_rect_repr": list(cast(tuple[int, int, int, int], state.ghost_rect)),
            "exterior_blocks_digest": exterior_hash,
        }
    )
    cert_hash = hashlib.sha256(payload).hexdigest()
    return Cut(
        cut_id=f"f7_manual_{cert_hash[:12]}",
        family="power_hitting_set",
        literals=(
            CutLiteral(
                slot_ref=AnonymousSlotRef(group_id=_GROUP_ID, slot_index=0),
                pose_id=_TARGET_POSE_ID,
            ),
        ),
        geometric_payload=None,
        scope=CutScope(
            ghost_rect_id=ghost_id,
            blocked_cells_hash=blocked_hash,
            exterior_blocks_hash=exterior_hash,
            source_digest=compute_source_digest(state),
            artifact_hashes=dict(state.artifact_hashes),
            oracle_abstraction_version="power_cover_v2_stencil",
            identity_preimage=preimage,
        ),
        cert=OracleCert(
            cert_kind="power_cover_emptyset_ghost",
            cert_payload=payload,
            cert_hash=cert_hash,
        ),
        family_version="v1.0",
        validator_version="v1.0",
        oracle_name="power_cover_v2_stencil",
        oracle_cert_hash=cert_hash,
    )


def _compile_cut(
    state: BState,
    bundle: FrozenArtifactBundle,
    cut: Cut,
    *,
    registry: FamilyCapabilityRegistry | None = None,
) -> tuple[ValidatedStateSnapshot, CompiledCut]:
    snapshot = build_validated_state_snapshot(state, bundle)
    result = validate_and_compile_cut(
        cut_to_envelope_v1(cut),
        snapshot,
        build_production_registry() if registry is None else registry,
    )
    assert isinstance(result, CompiledCut)
    return snapshot, result


def _typed_rejects(
    state: BState,
    bundle: FrozenArtifactBundle,
    cut: Cut,
) -> bool:
    try:
        envelope = cut_to_envelope_v1(cut)
    except (TypeError, ValueError):
        return True
    result = validate_and_compile_cut(
        envelope,
        build_validated_state_snapshot(state, bundle),
        build_production_registry(),
    )
    return isinstance(result, CutRejection)


def _tampered_cut(cut: Cut, mutate: Callable[[dict[str, Any]], None]) -> Cut:
    assert cut.cert is not None
    proof = json.loads(cut.cert.cert_payload)
    assert type(proof) is dict
    mutate(proof)
    payload = canonical_bytes_for_cert(proof)
    cert_hash = hashlib.sha256(payload).hexdigest()
    return replace(
        cut,
        cert=replace(cut.cert, cert_payload=payload, cert_hash=cert_hash),
        oracle_cert_hash=cert_hash,
    )


def _assert_sha256(value: str) -> None:
    assert len(value) == 64
    assert value == value.lower()
    int(value, 16)


def _plan_parameters(plan: ConstraintPlan) -> tuple[str, str, str]:
    group_id = plan.parameters["group_id"]
    pose_id = plan.parameters["pose_id"]
    blocked_digest = plan.parameters["blocked_cells_digest"]
    assert type(group_id) is str
    assert type(pose_id) is str
    assert type(blocked_digest) is str
    return group_id, pose_id, blocked_digest


def _lower_f7_plan(
    plan: ConstraintPlan,
    master: MasterPlacementModel,
    *,
    blocked_cells: Iterable[Cell],
    condition_lits: Sequence[Any],
) -> bool:
    group_id, pose_id, plan_blocked_digest = _plan_parameters(plan)
    blocked_body = frozenset(blocked_cells)
    assert plan.family == "power_hitting_set"
    assert plan.operation == "power_pose_exclusion"
    assert plan_blocked_digest == blocked_cells_digest_v1(blocked_body)
    return master._lower_power_pose_exclusion_cut(
        group_id=group_id,
        pose_id=pose_id,
        blocked_cells=blocked_body,
        condition_lits=condition_lits,
    )


def _build_master(
    *,
    pole_poses: Sequence[Mapping[str, Any]] = _POWER_POLES,
    skip_power_coverage: bool = False,
) -> MasterPlacementModel:
    instances = [
        {
            "instance_id": f"powered_widget_{index}",
            "facility_type": _FACILITY_TYPE,
            "operation_type": _OPERATION_TYPE,
            "is_mandatory": True,
            "bound_type": "exact",
        }
        for index in (1, 2)
    ]
    pools = cast(
        dict[str, list[dict[str, Any]]],
        _candidate_placements(pole_poses=pole_poses)["facility_pools"],
    )
    rules = {
        "globals": {"grid": {"width": 12, "height": 8}},
        "facility_templates": _facility_templates(),
    }
    core = MasterPlacementModel.build_exact_core(
        instances,
        pools,
        rules,
        skip_power_coverage=skip_power_coverage,
        c1_power_pole_representation=False,
        enable_symmetry_breaking=False,
    )
    master = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    assert master._group_id_by_instance["powered_widget_1"] == _GROUP_ID
    return master


def test_production_f7_oracle_cut_compiles_and_matches_legacy() -> None:
    state, bundle = _build_world()
    raw_cut = _oracle_cut(state)
    legacy = validate_power_hitting_set(raw_cut, state, state.canonical_rules or {})
    snapshot, compiled = _compile_cut(state, bundle, raw_cut)
    capability = build_production_registry().capabilities["power_hitting_set"]

    assert legacy.kind == "ok", legacy.detail
    assert capability.stage is CapabilityStage.COMPILABLE
    assert capability.requires_ghost_bound is True
    assert compiled.cut_id == raw_cut.cut_id
    assert compiled.snapshot_digest == snapshot.digest
    assert compiled.plan.family == "power_hitting_set"
    assert compiled.plan.operation == "power_pose_exclusion"
    assert compiled.plan.model_scope.ghost_policy == "bound"
    assert _plan_parameters(compiled.plan) == (
        _GROUP_ID,
        _TARGET_POSE_ID,
        snapshot.blocked_cells_digest,
    )
    assert snapshot.blocked_cells_digest == blocked_cells_digest_v1(state.ghost_cells | state.exterior_blocks)
    assert compiled.plan.model_scope.domain_fingerprint == snapshot.power_hitting_set_master_domain_projection


@pytest.mark.parametrize(
    "stage",
    [CapabilityStage.COMPILABLE, CapabilityStage.VALIDATED],
)
def test_f7_agnostic_scope_is_rejected_at_the_common_scope_boundary(
    stage: CapabilityStage,
) -> None:
    state, bundle = _build_world()
    raw_cut = _oracle_cut(state)
    assert raw_cut.scope is not None
    agnostic = replace(
        raw_cut,
        scope=replace(raw_cut.scope, ghost_rect_id=GHOST_AGNOSTIC),
    )
    registry = build_production_registry()
    production_capability = registry.capabilities["power_hitting_set"]
    selected_capability = replace(
        production_capability,
        stage=stage,
        compiler_version=(production_capability.compiler_version if stage is CapabilityStage.COMPILABLE else None),
    )
    selected_registry = FamilyCapabilityRegistry(
        capabilities={
            **registry.capabilities,
            "power_hitting_set": selected_capability,
        },
        plugins=dict(registry.plugins),
    )

    legacy = validate_power_hitting_set(
        agnostic,
        state,
        state.canonical_rules or {},
    )
    typed = validate_and_compile_cut(
        cut_to_envelope_v1(agnostic),
        build_validated_state_snapshot(state, bundle),
        selected_registry,
    )

    assert legacy.kind != "ok"
    assert _F7_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT["scope.requires_ghost_bound"] == "legacy-parity"
    assert isinstance(typed, CutRejection)
    assert typed.stage == "scope"
    assert typed.reason == "family capability requires a ghost-bound scope"


@pytest.mark.parametrize("pole_radius", [5, 5.0], ids=("exact-int", "exact-float"))
def test_f7_pole_radius_int_and_float_are_legacy_typed_positive_cases(
    pole_radius: int | float,
) -> None:
    state, bundle = _build_world()
    raw_cut = _tampered_cut(
        _oracle_cut(state),
        lambda proof: proof.__setitem__("pole_radius", pole_radius),
    )

    legacy = validate_power_hitting_set(raw_cut, state, state.canonical_rules or {})
    _snapshot, compiled = _compile_cut(state, bundle, raw_cut)

    assert legacy.kind == "ok", legacy.detail
    assert compiled.plan.operation == "power_pose_exclusion"


@pytest.mark.parametrize(
    ("cover_mode", "expected_reason"),
    [
        ("live", "full CoverSet recomputation is non-empty"),
        (
            "cell_owner",
            "ghost-only CoverSet recomputation is non-empty; cell_owner is the true cause",
        ),
    ],
)
def test_f7_legacy_and_typed_jointly_reject_nonempty_cover_sets(
    cover_mode: str,
    expected_reason: str,
) -> None:
    state, bundle = _build_world(cover_mode=cover_mode)
    raw_cut = _manual_cut(state)
    legacy = validate_power_hitting_set(raw_cut, state, state.canonical_rules or {})
    typed = validate_and_compile_cut(
        cut_to_envelope_v1(raw_cut),
        build_validated_state_snapshot(state, bundle),
        build_production_registry(),
    )

    assert legacy.kind != "ok"
    assert isinstance(typed, CutRejection)
    assert typed.stage == "proof"
    assert typed.reason == f"F7 {expected_reason}"


@pytest.mark.parametrize(
    ("mutate", "typed_arm"),
    [
        # typed_arm: ("adapter", exception-message substring) locks the adapter
        # rejection branch; ("proof", exact reason) locks the plugin branch.
        # B4 dual-review codex#2/opus#1: every joint-reject arm pins the exact
        # rejection site so a branch mismatch cannot hide behind a bare bool.
        (
            lambda proof: proof.__setitem__("future_field", 1),
            ("adapter", "has unknown field"),
        ),
        (
            lambda proof: proof.__setitem__("cert_kind", "not_f7"),
            ("adapter", "must be 'power_cover_emptyset_ghost'"),
        ),
        (
            lambda proof: proof.__setitem__("pole_radius", True),
            ("proof", "F7 pole_radius must be an exact int or float"),
        ),
        (
            lambda proof: proof.__setitem__("pole_radius", 4.0),
            ("proof", "F7 pole_radius differs from the snapshot source of truth"),
        ),
        (
            lambda proof: proof.__setitem__("pole_shape_canonical", "1x1_rigid"),
            ("proof", "F7 pole_shape_canonical must be 2x2_rigid"),
        ),
        (
            lambda proof: proof.__setitem__("facility_cells", [[4, 1]]),
            ("proof", "F7 facility_cells differ from the snapshot pose registry"),
        ),
        (
            lambda proof: proof.__setitem__("ghost_rect_repr", [1, 0, 1, 1]),
            ("proof", "F7 ghost_rect_repr differs from the snapshot"),
        ),
        (
            lambda proof: proof.__setitem__("exterior_blocks_digest", "0" * 16),
            ("proof", "F7 exterior_blocks_digest differs from the snapshot recomputation"),
        ),
    ],
    ids=(
        "closed-schema",
        "cert-kind",
        "radius-bool",
        "radius-sot",
        "pole-shape",
        "pose-registry",
        "ghost",
        "exterior",
    ),
)
def test_f7_legacy_and_typed_jointly_reject_semantic_tampers(
    mutate: Callable[[dict[str, Any]], None],
    typed_arm: tuple[str, str],
) -> None:
    state, bundle = _build_world()
    tampered = _tampered_cut(_oracle_cut(state), mutate)

    legacy = validate_power_hitting_set(tampered, state, state.canonical_rules or {})

    assert legacy.kind != "ok"
    arm, expected = typed_arm
    if arm == "adapter":
        with pytest.raises(ValueError, match=expected):
            cut_to_envelope_v1(tampered)
        return
    result = validate_and_compile_cut(
        cut_to_envelope_v1(tampered),
        build_validated_state_snapshot(state, bundle),
        build_production_registry(),
    )
    assert isinstance(result, CutRejection)
    assert result.stage == arm
    assert result.reason == expected


def test_f7_validator_version_cannot_bypass_unconditional_plugin_obligations() -> None:
    state, bundle = _build_world()
    tampered = _tampered_cut(
        _oracle_cut(state),
        lambda proof: proof.__setitem__("pole_radius", 4.0),
    )
    registry = build_production_registry()
    attacker_capability = replace(
        registry.capabilities["power_hitting_set"],
        validator_version="attacker-version-with-no-obligations",
    )
    attacker_registry = FamilyCapabilityRegistry(
        capabilities={
            **registry.capabilities,
            "power_hitting_set": attacker_capability,
        },
        plugins=dict(registry.plugins),
    )

    legacy = validate_power_hitting_set(tampered, state, state.canonical_rules or {})
    typed = validate_and_compile_cut(
        cut_to_envelope_v1(tampered),
        build_validated_state_snapshot(state, bundle),
        attacker_registry,
    )

    assert legacy.kind != "ok"
    assert isinstance(typed, CutRejection)
    assert typed.stage == "proof"
    assert typed.reason == "F7 pole_radius differs from the snapshot source of truth"


def _replace_outer_cert_kind(cut: Cut) -> Cut:
    assert cut.cert is not None
    return replace(cut, cert=replace(cut.cert, cert_kind="drifted_outer_cert_kind"))


def _replace_literal_slot(cut: Cut) -> Cut:
    assert cut.literals is not None and len(cut.literals) == 1
    literal = cut.literals[0]
    return replace(
        cut,
        literals=(
            replace(
                literal,
                slot_ref=replace(literal.slot_ref, slot_index=7),
            ),
        ),
    )


def test_f7_accept_set_audit_has_exact_ratified_typed_only_rows() -> None:
    typed_only = {
        key for key, classification in _F7_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT.items() if classification == "typed-only"
    }
    assert typed_only == {
        "adapter.payload_schema_version",
        "adapter.quarantine",
        "adapter.outer_cert_kind",
        "adapter.literal_slot_zero_placeholder",
        "adapter.identity_preimage_presence",
        "adapter.identity_preimage_structural_consistency",
        "adapter.identity_preimage_blocked_identity",
        "adapter.identity_preimage_exterior_identity",
        "adapter.identity_preimage_ghost_identity",
        "scope.exterior_preimage_snapshot_currentness",
        "scope.nonempty_assumptions",
        "scope.required_dependency_set",
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
            lambda cut: replace(cut, is_quarantined=True),
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
        (
            "adapter.literal_slot_zero_placeholder",
            _replace_literal_slot,
            "literal body differs from proof canonical projection",
        ),
    ],
    ids=("schema-v2", "quarantine-flag", "quarantine-reason", "outer-cert-kind", "slot-nonzero"),
)
def test_f7_ratified_adapter_tightenings_reject_legacy_accepted_cuts(
    audit_key: str,
    mutate: Callable[[Cut], Cut],
    message: str,
) -> None:
    state, _bundle = _build_world()
    attacked = mutate(_oracle_cut(state))
    legacy = validate_power_hitting_set(attacked, state, state.canonical_rules or {})

    assert _F7_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT[audit_key] == "typed-only"
    assert legacy.kind == "ok", legacy.detail
    with pytest.raises(ValueError, match=message):
        cut_to_envelope_v1(attacked)


def _structurally_inconsistent_preimage(
    preimage: ScopeIdentityPreimageV1,
) -> ScopeIdentityPreimageV1:
    forged = copy(preimage)
    object.__setattr__(
        forged,
        "exterior_blocks",
        tuple(sorted((*preimage.exterior_blocks, (99, 99)))),
    )
    return forged


def _blocked_identity_drift(
    preimage: ScopeIdentityPreimageV1,
) -> ScopeIdentityPreimageV1:
    return replace(
        preimage,
        blocked_cells=tuple(sorted((*preimage.blocked_cells, (99, 99)))),
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
def test_f7_preimage_inconsistencies_are_ratified_typed_only_rejections(
    audit_key: str,
    mutate: Callable[[ScopeIdentityPreimageV1], ScopeIdentityPreimageV1],
    message: str,
) -> None:
    state, _bundle = _build_world()
    raw_cut = _oracle_cut(state)
    assert raw_cut.scope is not None
    preimage = raw_cut.scope.identity_preimage
    assert isinstance(preimage, ScopeIdentityPreimageV1)
    attacked = replace(
        raw_cut,
        scope=replace(raw_cut.scope, identity_preimage=mutate(preimage)),
    )

    legacy = validate_power_hitting_set(attacked, state, state.canonical_rules or {})

    assert _F7_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT[audit_key] == "typed-only"
    assert legacy.kind == "ok", legacy.detail
    with pytest.raises(ValueError, match=message):
        cut_to_envelope_v1(attacked)


def test_old_f7_cut_without_identity_preimage_is_expected_typed_only_rejection() -> None:
    state, _bundle = _build_world()
    raw_cut = _oracle_cut(state)
    assert raw_cut.scope is not None
    attacked = replace(
        raw_cut,
        scope=replace(raw_cut.scope, identity_preimage=None),
    )

    legacy = validate_power_hitting_set(attacked, state, state.canonical_rules or {})

    assert _F7_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT["adapter.identity_preimage_presence"] == "typed-only"
    assert legacy.kind == "ok", legacy.detail
    with pytest.raises(ValueError, match="legacy scope identity has no raw preimage"):
        cut_to_envelope_v1(attacked)


def test_f7_coherent_wrong_exterior_preimage_is_rejected_by_snapshot_currentness() -> None:
    state, bundle = _build_world()
    raw_cut = _oracle_cut(state)
    assert raw_cut.scope is not None
    preimage = raw_cut.scope.identity_preimage
    assert isinstance(preimage, ScopeIdentityPreimageV1)
    wrong_preimage = _exterior_identity_drift(preimage)
    _ghost_hash, _blocked_hash, wrong_exterior_hash = compute_scope_identity_legacy_hashes(wrong_preimage)
    attacked = replace(
        raw_cut,
        scope=replace(
            raw_cut.scope,
            identity_preimage=wrong_preimage,
            exterior_blocks_hash=wrong_exterior_hash,
        ),
    )

    legacy = validate_power_hitting_set(attacked, state, state.canonical_rules or {})
    typed = validate_and_compile_cut(
        cut_to_envelope_v1(attacked),
        build_validated_state_snapshot(state, bundle),
        build_production_registry(),
    )

    assert _F7_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT["scope.exterior_preimage_snapshot_currentness"] == "typed-only"
    assert legacy.kind == "ok", legacy.detail
    assert isinstance(typed, CutRejection)
    assert typed.stage == "scope"
    assert typed.reason == "scope exterior-block identity is stale"


def test_nonempty_f7_scope_assumptions_are_expected_typed_only_rejection() -> None:
    state, bundle = _build_world()
    raw_cut = _oracle_cut(state)
    assert raw_cut.scope is not None
    attacked = replace(
        raw_cut,
        scope=replace(
            raw_cut.scope,
            active_assumptions=(
                Assumption(
                    key="placement_rule",
                    value=f"{_GROUP_ID}=free",
                ),
            ),
        ),
    )

    legacy = validate_power_hitting_set(attacked, state, state.canonical_rules or {})
    typed = validate_and_compile_cut(
        cut_to_envelope_v1(attacked),
        build_validated_state_snapshot(state, bundle),
        build_production_registry(),
    )

    assert _F7_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT["scope.nonempty_assumptions"] == "typed-only"
    assert legacy.kind == "ok", legacy.detail
    assert isinstance(typed, CutRejection)
    assert typed.stage == "scope"
    assert typed.reason == "typed assumption verification is unavailable for this family"


def test_f7_projection_and_semantic_fingerprint_are_stable() -> None:
    state_a, bundle_a = _build_world()
    state_b, bundle_b = _build_world()
    raw_a = _oracle_cut(state_a, iter_index=1)
    raw_b = _oracle_cut(state_b, iter_index=2)
    snapshot_a, compiled_a = _compile_cut(state_a, bundle_a, raw_a)
    snapshot_b, compiled_b = _compile_cut(state_b, bundle_b, raw_b)

    assert raw_a.cut_id != raw_b.cut_id
    assert snapshot_a.power_hitting_set_master_domain_projection == (
        snapshot_b.power_hitting_set_master_domain_projection
    )
    assert (
        power_hitting_set_master_domain_projection_v1(
            snapshot_a,
            _GROUP_ID,
            _TARGET_POSE_ID,
        )
        == snapshot_a.power_hitting_set_master_domain_projection
    )
    assert compiled_a.plan.digest == compiled_b.plan.digest
    assert compiled_a.plan.semantic_fingerprint == compiled_b.plan.semantic_fingerprint
    assert compiled_a.digest != compiled_b.digest
    _assert_sha256(snapshot_a.power_hitting_set_master_domain_projection)
    _assert_sha256(compiled_a.plan.semantic_fingerprint)


def _projection_for_variant(
    *,
    powered_poses: Sequence[Mapping[str, Any]] = _POWERED_POSES,
    pole_poses: Sequence[Mapping[str, Any]] = _POWER_POLES,
    include_noise: bool = False,
) -> str:
    state, bundle = _build_world(
        powered_poses=powered_poses,
        pole_poses=pole_poses,
        include_noise=include_noise,
    )
    return build_validated_state_snapshot(state, bundle).power_hitting_set_master_domain_projection


def _powered_pool_drift() -> list[dict[str, Any]]:
    poses = deepcopy(list(_POWERED_POSES))
    poses[2]["anchor"] = {"x": 9, "y": 0}
    poses[2]["occupied_cells"] = [[9, 0]]
    return poses


def _pole_occupied_drift() -> list[dict[str, Any]]:
    poles = deepcopy(list(_POWER_POLES))
    poles[0]["occupied_cells"] = [[2, 1], [2, 2], [3, 1], [4, 2]]
    return poles


def _pole_coverage_drift() -> list[dict[str, Any]]:
    poles = deepcopy(list(_POWER_POLES))
    coverage = cast(list[list[int]], poles[0]["power_coverage_cells"])
    poles[0]["power_coverage_cells"] = [cell for cell in coverage if cell != [4, 0]]
    return poles


@pytest.mark.parametrize(
    ("powered_poses", "pole_poses"),
    [
        (_powered_pool_drift(), _POWER_POLES),
        (_POWERED_POSES, _pole_occupied_drift()),
        (_POWERED_POSES, _pole_coverage_drift()),
        (tuple(reversed(_POWERED_POSES)), _POWER_POLES),
    ],
    ids=("powered-pool", "pole-occupied", "pole-coverage", "powered-pool-order"),
)
def test_f7_projection_drifts_with_every_power_domain_input(
    powered_poses: Sequence[Mapping[str, Any]],
    pole_poses: Sequence[Mapping[str, Any]],
) -> None:
    assert (
        _projection_for_variant(
            powered_poses=powered_poses,
            pole_poses=pole_poses,
        )
        != _projection_for_variant()
    )


def test_f7_projection_ignores_unpowered_noise() -> None:
    assert _projection_for_variant(include_noise=True) == _projection_for_variant()


def test_f7_projection_drifts_when_two_distinct_pole_rows_are_reordered() -> None:
    forward = _projection_for_variant(pole_poses=_TWO_POWER_POLES)
    reverse = _projection_for_variant(pole_poses=tuple(reversed(_TWO_POWER_POLES)))

    assert forward != reverse


def _capture_builder_coverer_rows(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pole_poses: Sequence[Mapping[str, Any]],
) -> list[object]:
    captured: list[list[object]] = []
    original = state_snapshot_module.power_hitting_set_master_domain_projection_v1

    def recording_projection(
        *,
        facility_pool_projection: object,
        mandatory_slot_rows: list[object],
        template_pose_registration_rows: list[object],
        power_coverer_rows: list[object],
    ) -> str:
        captured.append(deepcopy(power_coverer_rows))
        return original(
            facility_pool_projection=facility_pool_projection,
            mandatory_slot_rows=mandatory_slot_rows,
            template_pose_registration_rows=template_pose_registration_rows,
            power_coverer_rows=power_coverer_rows,
        )

    monkeypatch.setattr(
        state_snapshot_module,
        "power_hitting_set_master_domain_projection_v1",
        recording_projection,
    )
    _projection_for_variant(pole_poses=pole_poses)
    assert len(captured) == 1
    return captured[0]


def _expected_coverer_rows(
    *,
    middle_coverers: bool,
    any_coverers: bool = True,
) -> list[object]:
    rows: list[object] = []
    for pose_index, pose in enumerate(_POWERED_POSES):
        has_coverer = any_coverers and (pose_index != 1 or middle_coverers)
        rows.append(
            {
                "coverer_entry_state": "present",
                "coverer_pole_pose_ids": [_POLE_POSE_ID] if has_coverer else [],
                "coverer_pole_pose_indices": [0] if has_coverer else [],
                "facility_type": _FACILITY_TYPE,
                "powered_pose_id": pose["pose_id"],
                "powered_pose_index": pose_index,
            }
        )
    return rows


def test_f7_snapshot_builder_feeds_exact_canonical_coverer_rows_to_the_outer_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _capture_builder_coverer_rows(
        monkeypatch,
        pole_poses=_POWER_POLES,
    ) == _expected_coverer_rows(middle_coverers=True)


def test_f7_snapshot_builder_distinguishes_present_empty_and_coverage_drift_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty_rows = _capture_builder_coverer_rows(monkeypatch, pole_poses=())
    assert empty_rows == _expected_coverer_rows(
        middle_coverers=False,
        any_coverers=False,
    )

    # Restore the original before installing a second recording wrapper.
    monkeypatch.undo()
    drifted_rows = _capture_builder_coverer_rows(
        monkeypatch,
        pole_poses=_pole_coverage_drift(),
    )
    assert drifted_rows == _expected_coverer_rows(middle_coverers=False)


def test_f7_projection_digest_binds_canonical_coverer_rows() -> None:
    common = {
        "facility_pool_projection": [],
        "mandatory_slot_rows": [],
        "template_pose_registration_rows": [],
    }
    baseline = f7_projection_digest_v1(
        **common,
        power_coverer_rows=[
            {
                "coverer_entry_state": "present",
                "coverer_pole_pose_ids": [_POLE_POSE_ID],
                "coverer_pole_pose_indices": [0],
                "facility_type": _FACILITY_TYPE,
                "powered_pose_id": _TARGET_POSE_ID,
                "powered_pose_index": 1,
            }
        ],
    )
    present_empty = f7_projection_digest_v1(
        **common,
        power_coverer_rows=[
            {
                "coverer_entry_state": "present",
                "coverer_pole_pose_ids": [],
                "coverer_pole_pose_indices": [],
                "facility_type": _FACILITY_TYPE,
                "powered_pose_id": _TARGET_POSE_ID,
                "powered_pose_index": 1,
            }
        ],
    )
    missing = f7_projection_digest_v1(
        **common,
        power_coverer_rows=[
            {
                "coverer_entry_state": "missing",
                "coverer_pole_pose_ids": [],
                "coverer_pole_pose_indices": [],
                "facility_type": _FACILITY_TYPE,
                "powered_pose_id": _TARGET_POSE_ID,
                "powered_pose_index": 1,
            }
        ],
    )

    assert len({baseline, present_empty, missing}) == 3
    _assert_sha256(baseline)
    _assert_sha256(present_empty)
    _assert_sha256(missing)


def test_f7_runtime_gate_rejects_missing_coverer_entry() -> None:
    master = _build_master(skip_power_coverage=True)
    target_index = 1
    assert master._power_coverers_by_template_pose[_FACILITY_TYPE][target_index] == [0]
    del master._power_coverers_by_template_pose[_FACILITY_TYPE][target_index]

    assert not master._lower_power_pose_exclusion_cut(
        group_id=_GROUP_ID,
        pose_id=_TARGET_POSE_ID,
        blocked_cells={(2, 1)},
        condition_lits=(master.u_vars[0],),
    )


def test_f7_runtime_gate_accepts_naturally_empty_coverer_row() -> None:
    master = _build_master(pole_poses=(), skip_power_coverage=True)
    assert master._power_coverers_by_template_pose[_FACILITY_TYPE][1] == []

    assert master._lower_power_pose_exclusion_cut(
        group_id=_GROUP_ID,
        pose_id=_TARGET_POSE_ID,
        blocked_cells=set(),
        condition_lits=(master.u_vars[0],),
    )


def test_f7_runtime_gate_rejects_a_live_real_coverer() -> None:
    master = _build_master(skip_power_coverage=True)
    assert master._power_coverers_by_template_pose[_FACILITY_TYPE][1] == [0]

    assert not master._lower_power_pose_exclusion_cut(
        group_id=_GROUP_ID,
        pose_id=_TARGET_POSE_ID,
        blocked_cells={(69, 69)},
        condition_lits=(master.u_vars[0],),
    )


def test_f7_runtime_gate_accepts_a_dead_real_coverer() -> None:
    master = _build_master(skip_power_coverage=True)
    assert master._power_coverers_by_template_pose[_FACILITY_TYPE][1] == [0]

    assert master._lower_power_pose_exclusion_cut(
        group_id=_GROUP_ID,
        pose_id=_TARGET_POSE_ID,
        blocked_cells={(2, 1)},
        condition_lits=(master.u_vars[0],),
    )


def test_f7_real_master_condition_false_true_anchor_pattern() -> None:
    state, bundle = _build_world()
    raw_cut = _oracle_cut(state)
    _snapshot, compiled = _compile_cut(state, bundle, raw_cut)
    blocked_cells = frozenset(state.ghost_cells | state.exterior_blocks)

    dormant_master = _build_master()
    dormant_u0 = dormant_master.u_vars[0]
    assert _lower_f7_plan(
        compiled.plan,
        dormant_master,
        condition_lits=(dormant_u0,),
        blocked_cells=blocked_cells,
    )
    delegate = dormant_master._coordinate_delegate
    assert delegate is not None
    delegate.model.Add(dormant_u0 == 0)
    assert dormant_master.solve(time_limit_seconds=5.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )

    active_master = _build_master()
    active_u0 = active_master.u_vars[0]
    assert _lower_f7_plan(
        compiled.plan,
        active_master,
        condition_lits=(active_u0,),
        blocked_cells=blocked_cells,
    )
    active_delegate = active_master._coordinate_delegate
    assert active_delegate is not None
    active_delegate.model.Add(active_u0 == 1)
    assert active_master.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


# ---------------------------------------------------------------------------
# B4 dual-review fixes: container-shape drift, dependency-set audit rows,
# needs_power parity (codex#0 / codex#1 / opus#2).
# ---------------------------------------------------------------------------


def test_snapshot_builder_rejects_container_shape_drift_after_bundle() -> None:
    """codex#0 reproduction pin: list->tuple drift in a JSON artifact fails closed.

    The legacy content digest coerces list/tuple to one identity, so currentness
    alone cannot see this drift; the source-capture path must reject non
    JSON-native containers outright.
    """

    state, bundle = _build_world()
    placements = dict(state.candidate_placements)
    pools = dict(placements["facility_pools"])
    pools[_FACILITY_TYPE] = tuple(pools[_FACILITY_TYPE])
    placements["facility_pools"] = pools
    state.candidate_placements = placements

    with pytest.raises(SnapshotValidationError, match="unsupported value type tuple"):
        build_validated_state_snapshot(state, bundle)


def test_bundle_freeze_rejects_non_json_containers_in_single_traversal() -> None:
    """codex#0 pin: the freeze traversal itself is the JSON-native gate.

    tuple/set/non-dict mappings are rejected by the same visit that freezes,
    so there is no validate-then-freeze window for a concurrent mutation.
    """

    state, _bundle = _build_world()
    placements = dict(state.candidate_placements)
    pools = dict(placements["facility_pools"])
    pools[_FACILITY_TYPE] = tuple(pools[_FACILITY_TYPE])
    placements["facility_pools"] = pools

    with pytest.raises(TypeError, match="outside the exact JSON-native domain"):
        build_frozen_artifact_bundle(
            canonical_rules=state.canonical_rules,
            candidate_placements=placements,
            facility_templates=state.facility_templates,
            instance_to_facility_type=state.instance_to_facility_type,
            artifact_hashes=dict(state.artifact_hashes),
        )


def _world_with_artifact_hashes(hashes: dict[str, str]) -> tuple[BState, FrozenArtifactBundle]:
    state, _bundle = _build_world()
    state.artifact_hashes = hashes
    state.source_digest = compute_source_digest(state)
    bundle = build_frozen_artifact_bundle(
        canonical_rules=state.canonical_rules,
        candidate_placements=state.candidate_placements,
        facility_templates=state.facility_templates,
        instance_to_facility_type=state.instance_to_facility_type,
        artifact_hashes=hashes,
    )
    return state, bundle


@pytest.mark.parametrize("drift", ["missing", "extra"], ids=("missing-dependency", "extra-dependency"))
def test_f7_required_dependency_set_mismatch_is_expected_typed_only_rejection(drift: str) -> None:
    """codex#1: typed requires the exact production dependency set; legacy does not."""

    hashes = dict(_ARTIFACT_HASHES)
    if drift == "missing":
        hashes.pop("preprocess_plan")
    else:
        hashes["bogus_extra"] = "2" * 64
    state, bundle = _world_with_artifact_hashes(hashes)
    cut = _manual_cut(state)

    legacy = validate_power_hitting_set(cut, state, state.canonical_rules or {})
    typed = validate_and_compile_cut(
        cut_to_envelope_v1(cut),
        build_validated_state_snapshot(state, bundle),
        build_production_registry(),
    )

    assert _F7_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT["scope.required_dependency_set"] == "typed-only"
    assert legacy.kind == "ok", legacy.detail
    assert isinstance(typed, CutRejection)
    assert typed.stage == "scope"
    assert typed.reason == "scope dependency set differs from family manifest"


def test_f7_dependency_set_baseline_derives_from_production_manifest() -> None:
    """codex#1: the audit baseline derives from the authoritative manifest,
    not from a second hand-written copy of the same set."""

    from src.cuts.typed_platform import _PRODUCTION_V1_ARTIFACT_DEPENDENCIES

    assert set(_ARTIFACT_HASHES) == set(_PRODUCTION_V1_ARTIFACT_DEPENDENCIES)


def test_f7_needs_power_false_template_is_jointly_rejected() -> None:
    """opus#2: legacy-parity pin for the template needs_power obligation."""

    state, _bundle = _build_world()
    templates = {name: dict(template) for name, template in state.facility_templates.items()}
    templates[_FACILITY_TYPE]["needs_power"] = False
    state.facility_templates = templates
    rules = dict(state.canonical_rules)
    rules["facility_templates"] = templates
    state.canonical_rules = rules
    state.source_digest = compute_source_digest(state)
    bundle = build_frozen_artifact_bundle(
        canonical_rules=rules,
        candidate_placements=state.candidate_placements,
        facility_templates=templates,
        instance_to_facility_type=state.instance_to_facility_type,
        artifact_hashes=dict(state.artifact_hashes),
    )
    cut = _manual_cut(state)

    legacy = validate_power_hitting_set(cut, state, state.canonical_rules or {})
    typed = validate_and_compile_cut(
        cut_to_envelope_v1(cut),
        build_validated_state_snapshot(state, bundle),
        build_production_registry(),
    )

    assert _F7_ADAPTER_PLUGIN_ACCEPT_SET_AUDIT["plugin.snapshot_group_and_template"] == "legacy-parity"
    assert legacy.kind == "unsound"
    assert isinstance(typed, CutRejection)
    assert typed.stage == "proof"
    assert typed.reason == "F7 facility template does not require power"
