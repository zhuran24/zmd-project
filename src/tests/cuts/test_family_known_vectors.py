"""Pure-Python characterization vectors for the Stage-B family platform.

These vectors intentionally stop before model construction.  They pin the
master-independent bytes and rejection semantics that the family-manifest
migration must preserve.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, replace
import hashlib
from typing import Any

import pytest

from src.cuts.oracles.pattern_nogood_oracle import (
    clear_sub_problem_oracle_registry,
    register_sub_problem_oracle,
)
from src.cuts.lifecycle import (
    Cut,
    CutScope,
    OracleCert,
    step_3_serialize,
)
from src.cuts.replay import DiagnosticResult, ReplayContext
from src.cuts.state_snapshot import ValidatedStateSnapshot
from src.cuts.store import CutStore, QuarantineReason
from src.cuts.typed_platform import (
    CompiledCut,
    ConstraintPlan,
    CutEnvelope,
    CutRejection,
    FamilyCapabilityRegistry,
    ModelScope,
    SemanticCutRejection,
    ShadowValidated,
    build_production_registry,
    cut_to_envelope_v1,
    validate_and_compile_cut,
)
from src.tests.cuts import test_stage_b_power_hitting_set as f7_cases
from src.tests.cuts import test_stage_b_region_capacity as f1_cases
from src.tests.cuts import test_stage_b_shape_packing_hall as f6_cases
from src.tests.cuts import test_stage_b_typed_platform as platform_cases


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_plain(item) for item in value), key=repr)
    return value


def _compiled_vectors() -> dict[
    str,
    tuple[ValidatedStateSnapshot, CompiledCut, ConstraintPlan],
]:
    state_f1, bundle_f1 = f1_cases._build_state_and_bundle()
    raw_f1 = replace(
        f1_cases._oracle_cut(state_f1),
        cut_id="f1-known-vector",
    )
    snapshot_f1 = f1_cases.build_validated_state_snapshot(
        state_f1,
        bundle_f1,
    )
    compiled_f1 = validate_and_compile_cut(
        cut_to_envelope_v1(raw_f1),
        snapshot_f1,
        build_production_registry(),
    )
    assert isinstance(compiled_f1, CompiledCut)

    state_f6, bundle_f6 = f6_cases._build_world()
    _raw_f6, snapshot_f6, compiled_f6 = f6_cases._compile_cut(
        state_f6,
        bundle_f6,
        region_kind="left_baseline",
        region_demand=2,
        iter_index=1,
    )

    state_f7, bundle_f7 = f7_cases._build_world()
    raw_f7 = f7_cases._oracle_cut(state_f7, iter_index=1)
    snapshot_f7, compiled_f7 = f7_cases._compile_cut(
        state_f7,
        bundle_f7,
        raw_f7,
    )
    return {
        "region_capacity": (snapshot_f1, compiled_f1, compiled_f1.plan),
        "shape_packing_hall": (snapshot_f6, compiled_f6, compiled_f6.plan),
        "power_hitting_set": (snapshot_f7, compiled_f7, compiled_f7.plan),
    }


_EXPECTED_COMPILED_VECTORS: dict[str, dict[str, Any]] = {
    "region_capacity": {
        "operation": "region_capacity_le",
        "parameters": {
            "capacity": 1,
            "group_cell_weights": {"group::miner::mining::0": 1},
        },
        "plan_digest": "ba5d1d35bbd18b53073ea15c3222bbed64a69f6765ee651dbaf98fafa1e77157",
        "semantic_fingerprint": "d6b35a6002df2d30df9de32fb9e1a26e8960d3450a353b5db30819308e9b57e9",
        "compiled_digest": "3fa919938bcbbf5380c9689a64fee36ae9a7b93810ceeb34d99eeb46faa95c2a",
        "snapshot_digest": "70e7145066f164c2b5559e7956cf12160f4f52089c2288f15d69fd72544fbdbb",
        "ghost_policy": "agnostic",
        "ghost_rect_digest": None,
        "domain_fingerprint": "0a9795dc94bf2a8716b77edd354c5054445f25deef6faf27f15fe9539bfa7d1f",
    },
    "shape_packing_hall": {
        "operation": "shape_packing_hall_le",
        "parameters": {
            "capacity": 1,
            "group_id": "group::port::storage::0",
            "region_kind": "left_baseline",
        },
        "plan_digest": "f79e4b9ef86ae88db3ec37a9d274803adbfd93625f6c96b28ed3953e582d717b",
        "semantic_fingerprint": "cfbd452499a9d82dd2a8118b59f5bec5c00d5379ca7070cdb7cb6ab717da45d7",
        "compiled_digest": "c84fccd934fe6ec62f26c1bb588fb251819ee60ce47d6be1527eaf6a68ea0a86",
        "snapshot_digest": "7e61de55dbc8a184a19a52c656d6dc7aec1f1b237536bd0eed410cc421f11874",
        "ghost_policy": "bound",
        "ghost_rect_digest": "033ca2ecf0d629bb9ee6fbb3b2533bb3088cf5a7bef6a84493441e25f4d8a5c4",
        "domain_fingerprint": "a963524b5b8aa89ed6683c53e89213ddeb13f43758346c10e8dcd0ce50e47b4e",
    },
    "power_hitting_set": {
        "operation": "power_pose_exclusion",
        "parameters": {
            "blocked_cells_digest": "fe0f61bf1ac40baec926da217517c34a4cd45dcc37c529495e566e0980c4302a",
            "group_id": "group::powered_widget::assembly::0",
            "pose_id": "pose_mid",
        },
        "plan_digest": "b8887d54904af14706318fd46229f12bd24702320610912483d926ecf41b22be",
        "semantic_fingerprint": "8974844ce688172b057603de9312632e71b93a3a4b4eeb385da2c64698248be2",
        "compiled_digest": "418a731d97535973eee23401ac90a61f090bd352b1ef198749e610604654873d",
        "snapshot_digest": "b9577240e961babf56995612bab551df0a09cec83d90081b9a401c6382d97795",
        "ghost_policy": "bound",
        "ghost_rect_digest": "bb675996f734b57177e71996f747ce75c8f9d8a83129fce6505223c140638e8d",
        "domain_fingerprint": "45f55de721123994350157523e6a3469cf773a8d6668dc20317df9ef0444b4a7",
    },
}


@pytest.mark.parametrize("family", sorted(_EXPECTED_COMPILED_VECTORS))
def test_compiled_family_master_independent_known_vector(family: str) -> None:
    snapshot, compiled, plan = _compiled_vectors()[family]
    expected = _EXPECTED_COMPILED_VECTORS[family]

    assert plan.family == family
    assert plan.schema_version == 1
    assert plan.operation == expected["operation"]
    assert _plain(plan.parameters) == expected["parameters"]
    assert plan.digest == expected["plan_digest"]
    assert plan.semantic_fingerprint == expected["semantic_fingerprint"]
    assert compiled.digest == expected["compiled_digest"]
    assert snapshot.digest == expected["snapshot_digest"]
    assert plan.model_scope.ghost_policy == expected["ghost_policy"]
    assert plan.model_scope.ghost_rect_digest == expected["ghost_rect_digest"]
    assert (
        plan.model_scope.domain_fingerprint
        == expected["domain_fingerprint"]
    )


def test_f5_shadow_known_vector() -> None:
    state, snapshot, group_id = platform_cases._build_f5_verifiable_world(
        artifact_hashes=platform_cases._PRODUCTION_ARTIFACT_HASHES,
    )
    envelope = platform_cases._trusted_test_envelope(
        platform_cases._make_verifiable_pattern_cut(state, group_id),
        snapshot,
    )
    oracle = platform_cases._DifferentialF5Oracle()
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
    assert result.cut_id == "b15-pattern-verifiable"
    assert (
        result.proof_digest
        == "d515648f0fd65e3ceb0d2f1967b00aa25fb82655c46aec8a5576fd16df7858a8"
    )
    assert (
        result.snapshot_digest
        == "ab6d364fe6c56b563162bc04be9b0876d5eeaaacac7078805f1fdc4de1c6d631"
    )
    assert result.telemetry_tag == "independently-verified"


def test_rejection_stage_and_text_known_vectors() -> None:
    state, snapshot = platform_cases._build_world()
    envelope = platform_cases._trusted_test_envelope(
        platform_cases._typed_probe_cut(state),
        snapshot,
    )

    missing = validate_and_compile_cut(
        envelope,
        snapshot,
        FamilyCapabilityRegistry(capabilities={}, plugins={}),
    )
    assert missing == CutRejection(
        stage="registry",
        reason="family is absent from registry",
        cut_id=envelope.cut_id,
    )

    base_capability = platform_cases._typed_probe_capability()
    schema_registry = FamilyCapabilityRegistry(
        capabilities={
            base_capability.name: replace(
                base_capability,
                proof_schema_version=2,
            )
        },
        plugins={
            base_capability.name: platform_cases._OrderedPlugin(
                platform_cases._typed_probe_plan(),
            )
        },
    )
    schema = validate_and_compile_cut(envelope, snapshot, schema_registry)
    assert schema == CutRejection(
        stage="envelope",
        reason="proof schema version differs from capability",
        cut_id=envelope.cut_id,
    )

    proof_plugin = platform_cases._ParserRaisesPlugin(
        platform_cases._typed_probe_plan(
            domain_fingerprint=(
                snapshot.shape_packing_hall_master_domain_projection
            ),
        ),
        SemanticCutRejection("proof", "well-formed proof is unsound"),
    )
    proof = validate_and_compile_cut(
        envelope,
        snapshot,
        platform_cases._typed_probe_registry(proof_plugin),
    )
    assert proof == CutRejection(
        stage="proof",
        reason="well-formed proof is unsound",
        cut_id=envelope.cut_id,
    )

    plan_plugin = platform_cases._OrderedPlugin(
        platform_cases._typed_probe_plan(
            operation="region_capacity_le",
            domain_fingerprint=(
                snapshot.shape_packing_hall_master_domain_projection
            ),
        ),
    )
    plan = validate_and_compile_cut(
        envelope,
        snapshot,
        platform_cases._typed_probe_registry(plan_plugin),
    )
    assert plan == CutRejection(
        stage="plan",
        reason="ConstraintPlan.operation is invalid for envelope family",
        cut_id=envelope.cut_id,
    )


def test_wire_dataclass_field_sets_are_frozen_v1() -> None:
    expected = {
        Cut: (
            "cut_id",
            "family",
            "literals",
            "geometric_payload",
            "scope",
            "cert",
            "family_version",
            "validator_version",
            "payload_schema_version",
            "oracle_name",
            "oracle_cert_hash",
            "minimization_audit",
            "created_at",
            "iter_index",
            "is_quarantined",
            "quarantine_reason",
        ),
        CutScope: (
            "ghost_rect_id",
            "blocked_cells_hash",
            "exterior_blocks_hash",
            "source_digest",
            "artifact_hashes",
            "oracle_abstraction_version",
            "active_assumptions",
            "identity_preimage",
        ),
        OracleCert: ("cert_kind", "cert_payload", "cert_hash"),
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
        ModelScope: (
            "ghost_policy",
            "ghost_rect_digest",
            "domain_fingerprint",
        ),
        ValidatedStateSnapshot: (
            "source_digest",
            "artifact_hashes",
            "ghost",
            "blocked_cells_digest",
            "exterior_blocks_digest",
            "master_domain_projection",
            "shape_packing_hall_master_domain_projection",
            "power_hitting_set_master_domain_projection",
            "oracle_capabilities",
            "canonical_rules_source_present",
            "family_inputs",
            "groups",
            "cell_owner",
            "ghost_cells",
            "exterior_blocks",
            "digest",
        ),
        CutStore: (
            "cuts",
            "by_cell_watcher",
            "by_group_watcher",
            "by_pose_watcher",
            "by_commodity_watcher",
            "by_region_watcher",
            "by_ghost_watcher",
            "quarantined",
            "held",
        ),
        QuarantineReason: ("reason_code", "detail", "iter_index"),
        ReplayContext: ("snapshot", "registry", "legacy_state"),
        DiagnosticResult: ("family", "cut_id", "outcome", "detail"),
    }
    assert {
        data_type: tuple(item.name for item in fields(data_type))
        for data_type in expected
    } == expected


def test_cut_v1_serialization_known_vector() -> None:
    state, _bundle = f1_cases._build_state_and_bundle()
    cut = replace(
        f1_cases._oracle_cut(state),
        cut_id="f1-wire-known-vector",
        created_at="",
    )

    blob = step_3_serialize(cut)

    assert len(blob) == 7465
    assert (
        hashlib.sha256(blob).hexdigest()
        == "1cf76c3d8dec3267819cec3b99f0df1fad4d9d924f2290c66b562a6d6d66cb2f"
    )
