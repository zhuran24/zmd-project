"""Contract tests for the test-only rule-semantics shadow ledger."""

from __future__ import annotations

from dataclasses import replace

import pytest

from src.tests.cuts.rule_cut_evolution.rule_semantics import (
    SHADOW_RULE_SEMANTICS_V1,
    ExactCheckerSpec,
    InformationLayer,
    RuleSemanticRegistry,
    SemanticPolarity,
    StaticSymbolIdentity,
)


EXPECTED_FAMILY_VERSIONS = {
    "region_capacity": "v1.2",
    "cutset": "v1.0",
    "port_exposure": "v1.0",
    "component_reach": "v1.1",
    "pattern_nogood": "v1.0",
    "shape_packing_hall": "v1.0",
    "power_hitting_set": "v1.0",
    "power_grid_reach": "retired-false-premise-v1",
    "density_envelope": "v1.0",
}
PROTOCOL_RULES = {
    "cut_scope_currentness",
    "complete_premise_implication",
    "master_domain_projection_binding",
}


def test_shadow_rule_ledger_covers_current_family_and_protocol_surface() -> None:
    registry = SHADOW_RULE_SEMANTICS_V1
    assert frozenset(registry.rules) == frozenset((*EXPECTED_FAMILY_VERSIONS, *PROTOCOL_RULES))
    assert {
        family: registry.get(family).semantic_version
        for family in EXPECTED_FAMILY_VERSIONS
    } == EXPECTED_FAMILY_VERSIONS
    assert len(registry.audit_digest) == 64
    assert registry.audit_digest == RuleSemanticRegistry(
        schema_version=1,
        rules=dict(registry.rules),
    ).audit_digest


def test_every_rule_records_complete_premises_polarity_owners_and_invalidation() -> None:
    for row in SHADOW_RULE_SEMANTICS_V1.rules.values():
        assert row.complete_premises
        assert row.invalidation_conditions
        assert row.authoritative_owner in row.information_dependencies
        assert row.representation_owner in row.information_dependencies
        assert len({item.fact_id for item in row.complete_premises}) == len(row.complete_premises)
        if row.rule_id == "power_grid_reach":
            assert row.exact_semantics is None
            continue
        assert row.exact_semantics is not None
        assert row.exact_semantics.polarity is SemanticPolarity.EXACT_SEMANTICS
        assert row.exact_semantics.semantic_version == row.semantic_version
        if row.necessary_projection is not None:
            assert row.necessary_projection.polarity is SemanticPolarity.NECESSARY_PROJECTION
        if row.sufficient_restriction is not None:
            assert row.sufficient_restriction.polarity is SemanticPolarity.SUFFICIENT_RESTRICTION


def test_owner_is_latest_registered_information_dependency() -> None:
    assert SHADOW_RULE_SEMANTICS_V1.get("port_exposure").authoritative_owner is InformationLayer.BINDING
    assert SHADOW_RULE_SEMANTICS_V1.get("component_reach").authoritative_owner is InformationLayer.ROUTING
    assert (
        SHADOW_RULE_SEMANTICS_V1.get("complete_premise_implication").authoritative_owner
        is InformationLayer.TERMINAL_VALIDATION
    )


def test_only_f5_names_an_independent_exact_checker_identity() -> None:
    available = {
        rule_id
        for rule_id, row in SHADOW_RULE_SEMANTICS_V1.rules.items()
        if row.exact_twin_checker.is_available
    }
    assert available == {"pattern_nogood"}
    checker = SHADOW_RULE_SEMANTICS_V1.get("pattern_nogood").exact_twin_checker
    assert checker.identity == StaticSymbolIdentity(
        "src.cuts.verifiers.binding_empty_domain_verifier",
        "verify_binding_empty_domain",
    )
    assert checker.independence_basis


def test_registry_rejects_stale_protocol_version_and_owner_drift() -> None:
    row = SHADOW_RULE_SEMANTICS_V1.get("region_capacity")
    stale_ref = replace(row.protocol_obligations[0], semantic_version="v0")
    stale_row = replace(
        row,
        protocol_obligations=(stale_ref, *row.protocol_obligations[1:]),
    )
    with pytest.raises(ValueError, match="pins stale rule version"):
        RuleSemanticRegistry(
            schema_version=1,
            rules={**SHADOW_RULE_SEMANTICS_V1.rules, row.rule_id: stale_row},
        )

    with pytest.raises(ValueError, match="latest information dependency"):
        replace(
            SHADOW_RULE_SEMANTICS_V1.get("port_exposure"),
            authoritative_owner=InformationLayer.MASTER,
        )


def test_checker_spec_is_exactly_available_or_unavailable() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        ExactCheckerSpec(
            identity=None,
            checker_id=None,
            checker_version=None,
            independence_basis=None,
            unavailable_reason=None,
        )
    with pytest.raises(ValueError, match="cannot carry unavailable"):
        ExactCheckerSpec(
            identity=StaticSymbolIdentity("src.tests.fixture", "checker"),
            checker_id="fixture.checker",
            checker_version="v1",
            independence_basis="independent fixture",
            unavailable_reason="also-missing",
        )
