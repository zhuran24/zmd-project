"""Reusable negative and differential contract for one shadow onboarding row."""

from __future__ import annotations

import json

import pytest

from src.cuts.typed_platform import ConstraintPlan, ModelScope, build_production_registry
from src.tests.cuts.rule_cut_evolution.contract_harness import (
    DEFAULT_PREMISES,
    SHADOW_FAMILY,
    SHADOW_SNAPSHOT_FINGERPRINT,
    ShadowDisposition,
    TinyRealMaster,
    build_shadow_onboarding_registry,
    generate_proof,
    independent_exact_checker,
    independent_interpreter,
    production_disposition,
    verify_proof_to_plan,
)


def _mutated_proof(**changes: object) -> bytes:
    payload = json.loads(generate_proof())
    payload.update(changes)
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def test_shadow_onboarding_adds_one_identity_row_but_no_production_admission() -> None:
    shadow = build_shadow_onboarding_registry()
    production = build_production_registry()
    assert SHADOW_FAMILY in shadow.trust_specs
    lowering = shadow.trust(SHADOW_FAMILY).lowering.value
    assert lowering is not None
    assert lowering.operation == "region_capacity_le"
    assert SHADOW_FAMILY not in production.capabilities
    assert SHADOW_FAMILY not in production.plugins


@pytest.mark.parametrize(
    "proof,match",
    [
        (b"{", "malformed"),
        (_mutated_proof(cert_kind="unknown"), "unknown shadow proof type"),
        (_mutated_proof(semantic_version="v0"), "semantic version drift"),
        (_mutated_proof(premise_digest="0" * 64), "premise drift"),
        (_mutated_proof(snapshot_fingerprint="stale"), "stale shadow snapshot"),
        (_mutated_proof(capacity=1), "wrong strengthening"),
        (
            _mutated_proof(group_cell_weights={"alpha": 3, "beta": 1}),
            "wrong strengthening",
        ),
    ],
)
def test_negative_proof_paths_reject_before_master_mutation(
    proof: bytes,
    match: str,
) -> None:
    master = TinyRealMaster(("alpha", "beta"))
    before = master.proto_bytes()
    with pytest.raises((TypeError, ValueError), match=match):
        verify_proof_to_plan(proof)
    assert master.proto_bytes() == before
    assert production_disposition(proof_valid=False) is ShadowDisposition.QUARANTINE


def test_missing_or_extra_proof_field_is_fail_closed() -> None:
    missing = json.loads(generate_proof())
    del missing["premise_digest"]
    extra = {**json.loads(generate_proof()), "unregistered": True}
    for payload in (missing, extra):
        with pytest.raises(ValueError, match="closed proof schema"):
            verify_proof_to_plan(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            )


def test_proof_plan_interpreter_tiny_master_exact_checker_chain() -> None:
    proof = generate_proof()
    plan = verify_proof_to_plan(proof)
    assert plan.family == SHADOW_FAMILY
    assert plan.operation == "region_capacity_le"
    assert independent_exact_checker(DEFAULT_PREMISES, plan)

    for selected in (
        frozenset(),
        frozenset({"alpha"}),
        frozenset({"beta"}),
        frozenset({"alpha", "beta"}),
    ):
        interpreted = independent_interpreter(plan, selected)
        master = TinyRealMaster(("alpha", "beta"))
        before = master.proto_bytes()
        master.apply(plan)
        assert master.proto_bytes() != before
        assert master.solve_assignment(selected) is interpreted
    assert production_disposition(proof_valid=True) is ShadowDisposition.HOLD


def test_replay_is_deterministic_and_revalidates_current_premises() -> None:
    proof = generate_proof()
    first = verify_proof_to_plan(proof)
    second = verify_proof_to_plan(proof)
    assert first == second
    assert first.digest == second.digest
    with pytest.raises(ValueError, match="stale shadow snapshot"):
        verify_proof_to_plan(proof, snapshot_fingerprint="different-current-snapshot")


def test_tiny_master_application_is_atomic_on_stale_scope() -> None:
    good = verify_proof_to_plan(generate_proof())
    stale = ConstraintPlan(
        family=good.family,
        schema_version=good.schema_version,
        semantic_fingerprint=good.semantic_fingerprint,
        model_scope=ModelScope(
            ghost_policy="agnostic",
            ghost_rect_digest=None,
            domain_fingerprint="stale",
        ),
        operation=good.operation,
        parameters=good.parameters,
    )
    master = TinyRealMaster(("alpha", "beta"))
    before = master.proto_bytes()
    with pytest.raises(ValueError, match="stale snapshot"):
        master.apply(stale)
    assert master.proto_bytes() == before
    assert good.model_scope.domain_fingerprint == SHADOW_SNAPSHOT_FINGERPRINT


def test_tiny_master_application_is_atomic_on_operation_or_parameter_drift() -> None:
    good = verify_proof_to_plan(generate_proof())
    bad_plans = (
        ConstraintPlan(
            family=good.family,
            schema_version=good.schema_version,
            semantic_fingerprint=good.semantic_fingerprint,
            model_scope=good.model_scope,
            operation="shape_packing_hall_le",
            parameters={
                "capacity": 1,
                "group_id": "alpha",
                "region_kind": "left_baseline",
            },
        ),
        ConstraintPlan(
            family=good.family,
            schema_version=good.schema_version,
            semantic_fingerprint=good.semantic_fingerprint,
            model_scope=good.model_scope,
            operation=good.operation,
            parameters={
                "capacity": 2,
                "group_cell_weights": {"alpha": 2, "unregistered": 1},
            },
        ),
    )
    for bad_plan in bad_plans:
        master = TinyRealMaster(("alpha", "beta"))
        before = master.proto_bytes()
        with pytest.raises((KeyError, TypeError, ValueError)):
            master.apply(bad_plan)
        assert master.proto_bytes() == before
