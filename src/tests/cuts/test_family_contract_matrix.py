"""Machine-checkable family contract matrix and executable test-only fixture."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from dataclasses import fields, replace
from pathlib import Path
from typing import cast

import pytest
from ortools.sat.python import cp_model

from src.cuts import typed_apply
from src.cuts.family_specs import (
    FAMILY_CONTRACT_IDS_V1,
    LoweringSpec,
    PRODUCTION_FAMILY_MANIFEST_V1,
    StaticSymbolIdentity,
)
from src.cuts.lifecycle import _resolve_model_scope_binding, step_8_apply_to_master
from src.cuts.typed_platform import (
    CompiledCut,
    ConstraintPlan,
    CutEnvelope,
    CutRejection,
    FrozenFamilyProof,
    SemanticCutRejection,
    validate_and_compile_cut,
)
from src.tests.cuts import test_stage_b_region_capacity as _f1_fixture
from src.tests.cuts.family_contract_harness import (
    FAMILY_CONTRACT_EVIDENCE_V1,
    TEST_ONLY_FAMILY,
    TEST_ONLY_GROUP_ID,
    TestOnlyRegionCapacityPlugin,
    TestOnlyRegionCapacityProof,
    TestOnlyTcbFaultPlugin,
    build_test_only_family_manifest,
    build_test_only_family_world,
    compile_test_only_family,
    exact_check_test_only_region_capacity,
    generate_test_only_region_capacity_proof,
    interpret_test_only_region_capacity_plan,
    verify_test_only_region_capacity_proof,
)


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _test_functions(path: Path) -> frozenset[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return frozenset(
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    )


def test_contract_evidence_registry_is_exhaustive_and_resolvable() -> None:
    assert frozenset(FAMILY_CONTRACT_EVIDENCE_V1) == FAMILY_CONTRACT_IDS_V1
    for contract_id, evidence_rows in FAMILY_CONTRACT_EVIDENCE_V1.items():
        assert evidence_rows, contract_id
        for evidence in evidence_rows:
            relative_path, test_name = evidence.node_id.split("::")
            path = _REPO_ROOT / relative_path
            assert path.is_file(), evidence.node_id
            assert test_name in _test_functions(path), evidence.node_id
            assert evidence.authority_effect == "none"


def test_test_only_family_roles_are_independent_and_non_production() -> None:
    production_families_before = tuple(
        PRODUCTION_FAMILY_MANIFEST_V1.trust_specs
    )
    production_digest_before = PRODUCTION_FAMILY_MANIFEST_V1.audit_digest
    manifest = build_test_only_family_manifest()
    trust = manifest.trust(TEST_ONLY_FAMILY)
    generation = manifest.generation(TEST_ONLY_FAMILY)
    world = build_test_only_family_world()
    semantic_version = manifest.rule_semantics.get(
        TEST_ONLY_FAMILY
    ).semantic_version

    generator = generation.generator.require(
        family=TEST_ONLY_FAMILY,
        capability="generator",
    )
    assert type(generator) is StaticSymbolIdentity
    assert generator.qualname == "generate_test_only_region_capacity_proof"
    role_qualnames = {
        generate_test_only_region_capacity_proof.__qualname__,
        verify_test_only_region_capacity_proof.__qualname__,
        exact_check_test_only_region_capacity.__qualname__,
        TestOnlyRegionCapacityPlugin.__qualname__,
    }
    assert len(role_qualnames) == 4
    assert generation.family_version.require(
        family=TEST_ONLY_FAMILY,
        capability="family version",
    ) == semantic_version
    assert world.envelope.provenance.family_version == semantic_version

    # The exact checker is deliberately a test oracle, not a production claim.
    assert not trust.production_exact_checker.is_available
    assert not manifest.rule_semantics.get(
        TEST_ONLY_FAMILY
    ).exact_twin_checker.is_available
    assert TEST_ONLY_FAMILY not in PRODUCTION_FAMILY_MANIFEST_V1.trust_specs
    assert tuple(PRODUCTION_FAMILY_MANIFEST_V1.trust_specs) == (
        production_families_before
    )
    assert PRODUCTION_FAMILY_MANIFEST_V1.audit_digest == production_digest_before


def test_test_only_family_full_differential_chain_reuses_closed_operation() -> None:
    world = build_test_only_family_world()
    compiled = compile_test_only_family(world)
    plugin = world.registry.plugins[TEST_ONLY_FAMILY]
    proof = plugin.parse_and_validate_proof(
        world.envelope.proof_payload,
        world.snapshot,
    )
    assert type(proof) is TestOnlyRegionCapacityProof
    checked_proof = cast(TestOnlyRegionCapacityProof, proof)
    for count, expected in ((0, True), (1, True), (2, False)):
        counts = {TEST_ONLY_GROUP_ID: count}
        interpreted = interpret_test_only_region_capacity_plan(
            compiled.plan,
            group_presence_counts=counts,
        )
        exact = exact_check_test_only_region_capacity(
            checked_proof,
            group_presence_counts=counts,
        )
        assert interpreted is expected
        assert exact is interpreted

    base_lowering = cast(
        LoweringSpec,
        world.manifest.trust("region_capacity").lowering.require(
            family="region_capacity",
            capability="lowering",
        ),
    )
    fixture_lowering = cast(
        LoweringSpec,
        world.manifest.trust(TEST_ONLY_FAMILY).lowering.require(
            family=TEST_ONLY_FAMILY,
            capability="lowering",
        ),
    )
    assert fixture_lowering == base_lowering
    apply_source = inspect.getsource(typed_apply.apply_compiled_cut)
    assert TEST_ONLY_FAMILY not in apply_source
    assert apply_source.count('operation == "region_capacity_le"') == 1

    baseline_master = _f1_fixture._build_tiny_master(
        placement_rule="left_or_bottom_boundary"
    )
    baseline_status = baseline_master.solve(time_limit_seconds=5.0)
    assert baseline_status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    master = _f1_fixture._build_tiny_master(
        placement_rule="left_or_bottom_boundary"
    )
    binding = _resolve_model_scope_binding(
        compiled.plan.model_scope,
        world.snapshot,
        master,
        family=TEST_ONLY_FAMILY,
        family_specs=world.manifest,
    )
    step_8_apply_to_master(
        compiled,
        master,
        scope_binding=binding,
        family_specs=world.manifest,
    )
    assert master.build_stats["coordinate_framework_cut_count"] == 1
    status = master.solve(time_limit_seconds=5.0)
    assert status not in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_test_only_family_malformed_proof_is_rejected() -> None:
    world = build_test_only_family_world()
    malformed = json.dumps(
        {
            "family": TEST_ONLY_FAMILY,
            "proof": {
                "capacity": 1,
                "cert_kind": "test_only_region_capacity_contract",
            },
            "schema_version": 1,
        },
        allow_nan=False,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    malformed = b"zmd.proof.v1:" + malformed
    envelope = replace(
        world.envelope,
        proof_payload=malformed,
        proof_hash=hashlib.sha256(malformed).hexdigest(),
    )

    result = validate_and_compile_cut(envelope, world.snapshot, world.registry)

    assert result == CutRejection(
        stage="proof",
        reason="test-only proof fields are not exact",
        cut_id=envelope.cut_id,
    )


@pytest.mark.parametrize("drift", ["premise", "version"])
def test_test_only_family_premise_and_version_drift_are_rejected(
    drift: str,
) -> None:
    world = build_test_only_family_world()
    if drift == "premise":
        proof_payload = generate_test_only_region_capacity_proof(
            capacity=2,
            group_cell_weights={TEST_ONLY_GROUP_ID: 1},
        )
        envelope = replace(
            world.envelope,
            proof_payload=proof_payload,
            proof_hash=hashlib.sha256(proof_payload).hexdigest(),
        )
        result = validate_and_compile_cut(
            envelope,
            world.snapshot,
            world.registry,
        )
        assert result == CutRejection(
            stage="proof",
            reason=(
                "test-only proof premise does not establish a violated capacity"
            ),
            cut_id=envelope.cut_id,
        )
    else:
        raw = json.loads(
            generate_test_only_region_capacity_proof(
                capacity=1,
                group_cell_weights={TEST_ONLY_GROUP_ID: 1},
            )[len(b"zmd.proof.v1:") :]
        )
        raw["schema_version"] = 2
        payload = b"zmd.proof.v1:" + json.dumps(
            raw,
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        envelope = replace(
            world.envelope,
            family_schema_version=2,
            proof_payload=payload,
            proof_hash=hashlib.sha256(payload).hexdigest(),
        )
        result = validate_and_compile_cut(
            envelope,
            world.snapshot,
            world.registry,
        )
        assert result == CutRejection(
            stage="envelope",
            reason="proof schema version differs from capability",
            cut_id=envelope.cut_id,
        )


def test_test_only_family_stale_snapshot_scope_is_rejected() -> None:
    world = build_test_only_family_world()
    envelope = replace(
        world.envelope,
        scope=replace(world.envelope.scope, source_digest="f" * 64),
    )

    result = validate_and_compile_cut(envelope, world.snapshot, world.registry)

    assert result == CutRejection(
        stage="scope",
        reason="scope source digest is stale",
        cut_id=envelope.cut_id,
    )


def test_test_only_family_wrong_strengthening_is_rejected() -> None:
    world = build_test_only_family_world()
    compiled = compile_test_only_family(world)
    plugin = world.registry.plugins[TEST_ONLY_FAMILY]
    proof = plugin.parse_and_validate_proof(
        world.envelope.proof_payload,
        world.snapshot,
    )
    strengthened = ConstraintPlan(
        family=compiled.plan.family,
        schema_version=compiled.plan.schema_version,
        semantic_fingerprint=compiled.plan.semantic_fingerprint,
        model_scope=compiled.plan.model_scope,
        operation=compiled.plan.operation,
        parameters={
            "capacity": 0,
            "group_cell_weights": {TEST_ONLY_GROUP_ID: 1},
        },
    )

    with pytest.raises(
        SemanticCutRejection,
        match="parameters strengthen or drift",
    ):
        plugin.validate_plan(strengthened, proof, world.snapshot)


def test_test_only_family_unknown_entry_type_fails_closed() -> None:
    world = build_test_only_family_world()
    with pytest.raises(TypeError, match="exact CutEnvelope"):
        validate_and_compile_cut(
            cast(CutEnvelope, object()),
            world.snapshot,
            world.registry,
        )


def test_test_only_family_tcb_fault_propagates() -> None:
    world = build_test_only_family_world(plugin_type=TestOnlyTcbFaultPlugin)

    with pytest.raises(RuntimeError, match="test-only TCB verifier fault"):
        validate_and_compile_cut(
            world.envelope,
            world.snapshot,
            world.registry,
        )


def test_first_batch_public_wire_shapes_remain_unchanged() -> None:
    # The synthetic family creates only a CutEnvelope directly; it does not add
    # fields or lifecycle/cert-schema rows.  These exact field sets pin the
    # first-batch no-wire-change boundary in the reusable acceptance suite.
    assert tuple(field.name for field in fields(CutEnvelope)) == (
        "cut_id",
        "family",
        "family_schema_version",
        "proof_payload",
        "proof_hash",
        "scope",
        "provenance",
    )
    assert tuple(field.name for field in fields(ConstraintPlan)) == (
        "family",
        "schema_version",
        "semantic_fingerprint",
        "model_scope",
        "operation",
        "parameters",
        "digest",
    )
    assert tuple(field.name for field in fields(CompiledCut)) == (
        "cut_id",
        "proof_digest",
        "scope_digest",
        "snapshot_digest",
        "plan",
        "digest",
    )
    assert tuple(field.name for field in fields(FrozenFamilyProof)) == (
        "family",
        "schema_version",
    )
