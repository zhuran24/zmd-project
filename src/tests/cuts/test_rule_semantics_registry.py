from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

import src.cuts.rule_semantics as rule_semantics_module
from src.cuts.rule_semantics import (
    AvailableExactChecker,
    ExactCheckerUnavailableReason,
    InformationDependencyDagV1,
    InformationDependencyEdge,
    InformationLayer,
    InvalidationConditionSpec,
    PINNED_PRODUCTION_RULE_CONTENT_DIGESTS_V1,
    PINNED_PRODUCTION_RULE_LEDGER_AUDIT_DIGEST_V1,
    PRODUCTION_INFORMATION_DEPENDENCY_DAG_V1,
    PRODUCTION_RULE_SEMANTICS_V1,
    PremiseSpec,
    RuleDeploymentState,
    RuleSemanticFacet,
    RuleSemanticRegistry,
    RuleSemanticSpec,
    SemanticPolarity,
    UnavailableExactChecker,
    VersionedRuleRef,
)


_FAMILY_RULE_IDS = frozenset(
    {
        "region_capacity",
        "cutset",
        "port_exposure",
        "component_reach",
        "pattern_nogood",
        "shape_packing_hall",
        "power_hitting_set",
        "power_grid_reach",
        "density_envelope",
    }
)
_DIRECT_PROTOCOL_RULE_IDS = frozenset(
    {
        "cut_scope_currentness",
        "complete_premise_implication",
        "master_domain_projection_binding",
    }
)


def _exact_facet(
    *,
    rule_id: str = "probe",
    owner: InformationLayer = InformationLayer.MASTER,
    facet_id: str | None = None,
) -> RuleSemanticFacet:
    return RuleSemanticFacet(
        facet_id=facet_id or f"{rule_id}.exact",
        semantic_version="v1",
        polarity=SemanticPolarity.EXACT_SEMANTICS,
        owner=owner,
        claim="The probe's exact semantic claim.",
        source_ref="test_rule_semantics_registry.py",
    )


def _necessary_facet(
    *,
    rule_id: str = "probe",
    owner: InformationLayer = InformationLayer.MASTER,
    facet_id: str | None = None,
) -> RuleSemanticFacet:
    return RuleSemanticFacet(
        facet_id=facet_id or f"{rule_id}.necessary",
        semantic_version="v1",
        polarity=SemanticPolarity.NECESSARY_PROJECTION,
        owner=owner,
        claim="The probe's necessary projection.",
        source_ref="test_rule_semantics_registry.py",
    )


def _sufficient_facet(
    *,
    rule_id: str = "probe",
    owner: InformationLayer = InformationLayer.MASTER,
) -> RuleSemanticFacet:
    return RuleSemanticFacet(
        facet_id=f"{rule_id}.sufficient",
        semantic_version="v1",
        polarity=SemanticPolarity.SUFFICIENT_RESTRICTION,
        owner=owner,
        claim="The probe's sufficient restriction.",
        source_ref="test_rule_semantics_registry.py",
    )


def _probe_spec(
    *,
    rule_id: str = "probe",
    dependencies: frozenset[InformationLayer] = frozenset({InformationLayer.MASTER}),
    authoritative_owner: InformationLayer = InformationLayer.MASTER,
    representation_owner: InformationLayer = InformationLayer.MASTER,
    deployment_state: RuleDeploymentState = RuleDeploymentState.SHARED_PROTOCOL,
    necessary_projection: RuleSemanticFacet | None = None,
    exact_semantics: RuleSemanticFacet | None = None,
    semantic_dependencies: tuple[str, ...] = (),
) -> RuleSemanticSpec:
    return RuleSemanticSpec(
        rule_id=rule_id,
        semantic_version="v1",
        deployment_state=deployment_state,
        information_dependencies=dependencies,
        authoritative_owner=authoritative_owner,
        representation_owner=representation_owner,
        necessary_projection=necessary_projection,
        sufficient_restriction=None,
        exact_semantics=exact_semantics or _exact_facet(rule_id=rule_id, owner=authoritative_owner),
        complete_premises=(
            PremiseSpec(
                premise_id=f"{rule_id}.premise",
                semantic_version="v1",
                owner=authoritative_owner,
                source_ref="test_rule_semantics_registry.py",
            ),
        ),
        assumptions=(),
        invalidation_conditions=(
            InvalidationConditionSpec(
                condition_id=f"{rule_id}.changed",
                semantic_version="v1",
                owner=authoritative_owner,
                source_ref="test_rule_semantics_registry.py",
            ),
        ),
        exact_twin_checker=UnavailableExactChecker(
            reason=ExactCheckerUnavailableReason.PROTOCOL_ASSERTION_ONLY,
            detail="Test probe has no production checker.",
        ),
        protocol_obligations=(),
        semantic_dependencies=tuple(
            VersionedRuleRef(rule_id=dependency, semantic_version="v1")
            for dependency in semantic_dependencies
        ),
        source_refs=("test_rule_semantics_registry.py",),
    )


def test_information_dependency_dag_uses_edges_not_enum_or_string_order() -> None:
    dag = PRODUCTION_INFORMATION_DEPENDENCY_DAG_V1

    assert dag.reaches(InformationLayer.PRECHECK, InformationLayer.TERMINAL_VALIDATION)
    assert dag.reaches(InformationLayer.MASTER, InformationLayer.MASTER)
    assert not dag.reaches(InformationLayer.ROUTING, InformationLayer.BINDING)
    assert (
        dag.unique_maximum(
            frozenset(
                {
                    InformationLayer.PRECHECK,
                    InformationLayer.BINDING,
                    InformationLayer.ROUTING,
                }
            )
        )
        is InformationLayer.ROUTING
    )


def test_information_dependency_dag_rejects_cycles() -> None:
    with pytest.raises(ValueError, match="acyclic"):
        InformationDependencyDagV1(
            dag_id="cycle_probe",
            schema_version=1,
            nodes=frozenset({InformationLayer.MASTER, InformationLayer.BINDING}),
            edges=(
                InformationDependencyEdge(InformationLayer.MASTER, InformationLayer.BINDING),
                InformationDependencyEdge(InformationLayer.BINDING, InformationLayer.MASTER),
            ),
        )


def test_information_dependency_dag_rejects_incomparable_maxima() -> None:
    dag = InformationDependencyDagV1(
        dag_id="branch_probe",
        schema_version=1,
        nodes=frozenset(
            {
                InformationLayer.PRECHECK,
                InformationLayer.MASTER,
                InformationLayer.BINDING,
            }
        ),
        edges=(
            InformationDependencyEdge(InformationLayer.PRECHECK, InformationLayer.MASTER),
            InformationDependencyEdge(InformationLayer.PRECHECK, InformationLayer.BINDING),
        ),
    )

    with pytest.raises(ValueError, match="no unique maximum owner"):
        dag.unique_maximum(frozenset({InformationLayer.MASTER, InformationLayer.BINDING}))


def test_registry_rejects_authoritative_owner_not_derived_from_dag() -> None:
    spec = _probe_spec(
        dependencies=frozenset(
            {
                InformationLayer.MASTER,
                InformationLayer.BINDING,
            }
        ),
        authoritative_owner=InformationLayer.MASTER,
        exact_semantics=_exact_facet(owner=InformationLayer.MASTER),
    )

    with pytest.raises(ValueError, match="does not match DAG-derived owner"):
        RuleSemanticRegistry(
            schema_version=1,
            information_dag=PRODUCTION_INFORMATION_DEPENDENCY_DAG_V1,
            rules={"probe": spec},
        )


def test_registry_requires_projection_when_representation_precedes_authority() -> None:
    spec = _probe_spec(
        dependencies=frozenset({InformationLayer.BINDING}),
        authoritative_owner=InformationLayer.BINDING,
        representation_owner=InformationLayer.MASTER,
        exact_semantics=_exact_facet(owner=InformationLayer.BINDING),
    )

    with pytest.raises(ValueError, match="requires a necessary projection"):
        RuleSemanticRegistry(
            schema_version=1,
            information_dag=PRODUCTION_INFORMATION_DEPENDENCY_DAG_V1,
            rules={"probe": spec},
        )

    projected = replace(
        spec,
        necessary_projection=_necessary_facet(owner=InformationLayer.MASTER),
    )
    registry = RuleSemanticRegistry(
        schema_version=1,
        information_dag=PRODUCTION_INFORMATION_DEPENDENCY_DAG_V1,
        rules={"probe": projected},
    )
    assert registry.get("probe") is projected


def test_rule_spec_rejects_polarity_mixing_and_facet_reuse() -> None:
    wrong_polarity = _exact_facet()
    with pytest.raises(ValueError, match="wrong semantic polarity"):
        _probe_spec(necessary_projection=wrong_polarity)

    shared_id = "probe.shared_facet"
    with pytest.raises(ValueError, match="cannot be reused"):
        RuleSemanticSpec(
            rule_id="probe",
            semantic_version="v1",
            deployment_state=RuleDeploymentState.COMPILABLE,
            information_dependencies=frozenset({InformationLayer.MASTER}),
            authoritative_owner=InformationLayer.MASTER,
            representation_owner=InformationLayer.MASTER,
            necessary_projection=_necessary_facet(facet_id=shared_id),
            sufficient_restriction=None,
            exact_semantics=_exact_facet(facet_id=shared_id),
            complete_premises=(
                PremiseSpec(
                    premise_id="probe.premise",
                    semantic_version="v1",
                    owner=InformationLayer.MASTER,
                    source_ref="test_rule_semantics_registry.py",
                ),
            ),
            assumptions=(),
            invalidation_conditions=(
                InvalidationConditionSpec(
                    condition_id="probe.changed",
                    semantic_version="v1",
                    owner=InformationLayer.MASTER,
                    source_ref="test_rule_semantics_registry.py",
                ),
            ),
            exact_twin_checker=UnavailableExactChecker(
                reason=ExactCheckerUnavailableReason.NO_INDEPENDENT_PRODUCTION_CHECKER,
                detail="No checker.",
            ),
            protocol_obligations=(),
            source_refs=("test_rule_semantics_registry.py",),
        )


def test_rule_spec_rejects_semantic_facet_version_drift() -> None:
    drifted = replace(_exact_facet(), semantic_version="v2")

    with pytest.raises(ValueError, match="semantic version differs from rule"):
        _probe_spec(exact_semantics=drifted)


def test_registry_derives_owner_from_complete_semantic_scope() -> None:
    spec = _probe_spec()
    routing_premise = replace(
        spec.complete_premises[0],
        owner=InformationLayer.ROUTING,
    )
    omitted = replace(spec, complete_premises=(routing_premise,))

    with pytest.raises(ValueError, match="omit semantic-scope owner"):
        RuleSemanticRegistry(
            schema_version=1,
            information_dag=PRODUCTION_INFORMATION_DEPENDENCY_DAG_V1,
            rules={"probe": omitted},
        )


def test_registry_rejects_sufficient_restriction_at_wrong_representation_owner() -> None:
    spec = replace(
        _probe_spec(),
        sufficient_restriction=_sufficient_facet(
            owner=InformationLayer.TERMINAL_VALIDATION,
        ),
    )

    with pytest.raises(ValueError, match="owner differs from representation owner"):
        RuleSemanticRegistry(
            schema_version=1,
            information_dag=PRODUCTION_INFORMATION_DEPENDENCY_DAG_V1,
            rules={"probe": spec},
        )


def test_legacy_and_retired_rows_cannot_claim_live_projection_or_checker() -> None:
    checker = AvailableExactChecker(
        checker_id="probe.checker",
        checker_version="v1",
        module="probe.checker",
        qualname="verify",
        independence_basis="Independent test derivation.",
    )

    with pytest.raises(ValueError, match="legacy diagnostic rules cannot advertise"):
        replace(
            _probe_spec(
                deployment_state=RuleDeploymentState.VALIDATED_LEGACY_DIAGNOSTIC,
                necessary_projection=None,
            ),
            necessary_projection=_necessary_facet(),
        )

    with pytest.raises(ValueError, match="retired rules cannot advertise a live semantic facet"):
        replace(
            _probe_spec(),
            deployment_state=RuleDeploymentState.RETIRED,
            exact_twin_checker=checker,
        )


def test_registry_rejects_unknown_or_cyclic_semantic_dependencies() -> None:
    unknown = _probe_spec(semantic_dependencies=("missing",))
    with pytest.raises(ValueError, match="unknown semantic dependency"):
        RuleSemanticRegistry(
            schema_version=1,
            information_dag=PRODUCTION_INFORMATION_DEPENDENCY_DAG_V1,
            rules={"probe": unknown},
        )

    first = _probe_spec(rule_id="first", semantic_dependencies=("second",))
    second = _probe_spec(rule_id="second", semantic_dependencies=("first",))
    with pytest.raises(ValueError, match="must be acyclic"):
        RuleSemanticRegistry(
            schema_version=1,
            information_dag=PRODUCTION_INFORMATION_DEPENDENCY_DAG_V1,
            rules={"first": first, "second": second},
        )


def test_registry_rejects_semantic_dependency_version_drift() -> None:
    base = replace(
        _probe_spec(rule_id="base"),
        semantic_version="v2",
        exact_semantics=replace(
            _exact_facet(rule_id="base"),
            semantic_version="v2",
        ),
    )
    dependent = _probe_spec(
        rule_id="dependent",
        semantic_dependencies=("base",),
    )

    with pytest.raises(
        ValueError,
        match="pins semantic dependency.*current version",
    ):
        RuleSemanticRegistry(
            schema_version=1,
            information_dag=PRODUCTION_INFORMATION_DEPENDENCY_DAG_V1,
            rules={"base": base, "dependent": dependent},
        )


def test_semantic_dependencies_affect_owner_but_protocol_obligations_do_not() -> None:
    terminal = _probe_spec(
        rule_id="terminal",
        dependencies=frozenset({InformationLayer.TERMINAL_VALIDATION}),
        authoritative_owner=InformationLayer.TERMINAL_VALIDATION,
        representation_owner=InformationLayer.TERMINAL_VALIDATION,
        exact_semantics=_exact_facet(
            rule_id="terminal",
            owner=InformationLayer.TERMINAL_VALIDATION,
        ),
    )
    semantic_dependent = _probe_spec(
        rule_id="semantic_dependent",
        dependencies=frozenset(
            {
                InformationLayer.MASTER,
                InformationLayer.TERMINAL_VALIDATION,
            }
        ),
        semantic_dependencies=("terminal",),
    )
    with pytest.raises(ValueError, match="does not match DAG-derived owner"):
        RuleSemanticRegistry(
            schema_version=1,
            information_dag=PRODUCTION_INFORMATION_DEPENDENCY_DAG_V1,
            rules={
                "semantic_dependent": semantic_dependent,
                "terminal": terminal,
            },
        )

    protocol_dependent = replace(
        _probe_spec(rule_id="protocol_dependent"),
        protocol_obligations=(
            VersionedRuleRef(rule_id="terminal", semantic_version="v1"),
        ),
    )
    registry = RuleSemanticRegistry(
        schema_version=1,
        information_dag=PRODUCTION_INFORMATION_DEPENDENCY_DAG_V1,
        rules={
            "protocol_dependent": protocol_dependent,
            "terminal": terminal,
        },
    )
    assert registry.get("protocol_dependent") is protocol_dependent


def test_production_seed_covers_f1_through_f9_and_direct_protocol_rules() -> None:
    registry = PRODUCTION_RULE_SEMANTICS_V1

    assert frozenset(registry.rules) == _FAMILY_RULE_IDS | _DIRECT_PROTOCOL_RULE_IDS
    assert registry.get("region_capacity").deployment_state is RuleDeploymentState.COMPILABLE
    assert registry.get("shape_packing_hall").deployment_state is RuleDeploymentState.COMPILABLE
    assert registry.get("power_hitting_set").deployment_state is RuleDeploymentState.COMPILABLE
    assert (
        registry.get("pattern_nogood").deployment_state
        is RuleDeploymentState.VALIDATED_SHADOW_ONLY
    )
    for family in ("cutset", "port_exposure", "component_reach", "density_envelope"):
        assert (
            registry.get(family).deployment_state
            is RuleDeploymentState.VALIDATED_LEGACY_DIAGNOSTIC
        )
    assert registry.get("power_grid_reach").deployment_state is RuleDeploymentState.RETIRED

    for family in _FAMILY_RULE_IDS - {"power_grid_reach"}:
        dependencies = registry.get(family).protocol_obligation_ids
        assert "cut_scope_currentness" in dependencies
        assert "complete_premise_implication" in dependencies


def test_production_checker_availability_is_honest_and_independent() -> None:
    registry = PRODUCTION_RULE_SEMANTICS_V1
    available = {
        rule_id
        for rule_id, spec in registry.rules.items()
        if spec.exact_twin_checker.is_available
    }

    assert available == {"pattern_nogood"}
    f5_checker = registry.get("pattern_nogood").exact_twin_checker
    assert isinstance(f5_checker, AvailableExactChecker)
    assert f5_checker.module == "src.cuts.verifiers.binding_empty_domain_verifier"
    assert f5_checker.qualname == "verify_binding_empty_domain"

    for family in ("cutset", "port_exposure", "component_reach", "density_envelope"):
        checker = registry.get(family).exact_twin_checker
        assert isinstance(checker, UnavailableExactChecker)
        assert checker.reason is ExactCheckerUnavailableReason.LEGACY_DIAGNOSTIC_ONLY

    retired_checker = registry.get("power_grid_reach").exact_twin_checker
    assert isinstance(retired_checker, UnavailableExactChecker)
    assert retired_checker.reason is ExactCheckerUnavailableReason.RETIRED_FALSE_PREMISE


def test_production_projection_columns_do_not_invent_legacy_or_retired_capability() -> None:
    registry = PRODUCTION_RULE_SEMANTICS_V1
    projection_rules = {
        rule_id
        for rule_id in _FAMILY_RULE_IDS
        if registry.get(rule_id).necessary_projection is not None
    }

    assert projection_rules == {"region_capacity", "shape_packing_hall", "power_hitting_set"}
    for rule_id in registry.rules:
        assert registry.get(rule_id).sufficient_restriction is None


def test_production_rows_have_complete_versioned_premise_and_invalidation_columns() -> None:
    for spec in PRODUCTION_RULE_SEMANTICS_V1.rules.values():
        assert spec.semantic_version
        assert spec.complete_premises
        assert spec.invalidation_conditions
        assert len({premise.premise_id for premise in spec.complete_premises}) == len(
            spec.complete_premises
        )
        assert all(premise.semantic_version for premise in spec.complete_premises)
        assert all(condition.semantic_version for condition in spec.invalidation_conditions)


def test_audit_digest_is_canonical_order_independent_and_non_authoritative() -> None:
    registry = PRODUCTION_RULE_SEMANTICS_V1
    reversed_rules = dict(reversed(tuple(registry.rules.items())))
    rebuilt = RuleSemanticRegistry(
        schema_version=1,
        information_dag=registry.information_dag,
        rules=reversed_rules,
    )

    assert rebuilt.audit_digest == registry.audit_digest
    assert len(registry.audit_digest) == 64
    int(registry.audit_digest, 16)
    assert set(RuleSemanticRegistry.__dataclass_fields__) == {
        "schema_version",
        "information_dag",
        "rules",
        "rule_content_digests",
        "audit_digest",
    }
    assert (
        registry.rule_content_digests
        == PINNED_PRODUCTION_RULE_CONTENT_DIGESTS_V1
    )
    assert (
        registry.audit_digest
        == PINNED_PRODUCTION_RULE_LEDGER_AUDIT_DIGEST_V1
    )

    f1 = registry.get("region_capacity")
    assert f1.necessary_projection is not None
    changed_facet = replace(
        f1.necessary_projection,
        claim=f"{f1.necessary_projection.claim} Audit-only change.",
    )
    changed_f1 = replace(f1, necessary_projection=changed_facet)
    changed_rules = dict(registry.rules)
    changed_rules["region_capacity"] = changed_f1
    changed_registry = RuleSemanticRegistry(
        schema_version=1,
        information_dag=registry.information_dag,
        rules=changed_rules,
    )
    assert changed_registry.audit_digest != registry.audit_digest


def test_registry_snapshots_input_mapping_and_exposes_read_only_rules() -> None:
    spec = _probe_spec()
    source = {"probe": spec}
    registry = RuleSemanticRegistry(
        schema_version=1,
        information_dag=PRODUCTION_INFORMATION_DEPENDENCY_DAG_V1,
        rules=source,
    )
    source.clear()

    assert registry.get("probe") is spec
    with pytest.raises(TypeError):
        registry.rules["other"] = spec  # type: ignore[index]


def test_rule_semantics_module_has_no_production_runtime_import_or_dynamic_loader() -> None:
    source_path = Path(rule_semantics_module.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    assert all(not module.startswith("src.") for module in imported_modules)
    assert not hasattr(AvailableExactChecker, "load")
    assert not hasattr(AvailableExactChecker, "resolve")
