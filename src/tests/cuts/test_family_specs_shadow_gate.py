"""Milestone-A shadow gates for the static family manifest.

The production tables remain authoritative in this milestone.  These tests
fail closed when the shadow manifest disagrees with any current registration
surface, while proving that no runtime module consumes the new manifest yet.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import fields, replace
from pathlib import Path
from typing import Protocol, cast

import pytest

import src.cuts.state_snapshot as state_snapshot_module
from src.cuts.cert_schema import (
    CERT_PAYLOAD_ALLOWED_FIELDS,
    CERT_PAYLOAD_CERT_KIND_BY_FAMILY,
    CERT_PAYLOAD_REQUIRED_FIELDS,
)
from src.cuts.family_specs import (
    FAMILY_CONTRACT_IDS_V1,
    AvailableCapability,
    CapabilityUnavailableError,
    FamilyGenerationSpec,
    FamilySpecRegistry,
    FamilyTrustSpec,
    GenerationSurface,
    LoweringSpec,
    PINNED_PRODUCTION_FAMILY_MANIFEST_AUDIT_DIGEST_V1,
    PRODUCTION_FAMILY_MANIFEST_V1,
    PRODUCTION_V1_AUTHORITY_DEPENDENCY_CLOSURE,
    PluginProviderSpec,
    ProofSchemaSpec,
    ReplayKind,
    ReplaySpec,
    SnapshotInputSpec,
    SnapshotProjectionSpec,
    StaticCallableRef,
    StaticSymbolIdentity,
    TelemetryProfile,
    UnavailableCapability,
)
from src.cuts.lifecycle import _FAMILY_MODE_MAP
from src.cuts.replay import (
    LEGACY_DIAGNOSTIC_VALIDATORS,
    TYPED_REPLAY_FAMILIES,
)
from src.cuts.rule_semantics import (
    PRODUCTION_RULE_SEMANTICS_V1,
    RuleDeploymentState,
    RuleSemanticRegistry,
    VersionedRuleRef,
)
from src.cuts.typed_platform import (
    SUPPORTED_OPERATIONS,
    CapabilityStage,
    ExecutionPath,
    FamilyCapability,
    build_production_registry,
    validate_and_compile_cut,
)
from src.search.family_generation import (
    TYPED_FAMILY_GENERATION_INVOKERS_V1,
    TYPED_FAMILY_GENERATION_ORDER_V1,
    typed_family_generation_invoker,
)


_REPO_ROOT = Path(__file__).resolve().parents[3]
_RUNTIME_FILES = (
    "src/cuts/typed_platform.py",
    "src/cuts/state_snapshot.py",
    "src/cuts/lifecycle.py",
    "src/cuts/typed_apply.py",
    "src/cuts/replay.py",
    "src/cuts/store.py",
    "src/cuts/cert_schema.py",
    "src/search/benders_loop.py",
)
_EXPECTED_LIVE_FAMILIES = frozenset(
    {
        "component_reach",
        "cutset",
        "density_envelope",
        "pattern_nogood",
        "port_exposure",
        "power_hitting_set",
        "region_capacity",
        "shape_packing_hall",
    }
)
_COMMON_TYPED_SNAPSHOT_FIELDS = frozenset(
    {
        "artifact_hashes",
        "digest",
        "exterior_blocks_digest",
        "oracle_capabilities",
        "source_digest",
    }
)
_GHOST_BOUND_SNAPSHOT_FIELDS = frozenset(
    {
        "blocked_cells_digest",
        "ghost",
    }
)
_EXPECTED_CONSUMED_SNAPSHOT_FIELDS = {
    "region_capacity": _COMMON_TYPED_SNAPSHOT_FIELDS
    | frozenset(
        {
            "canonical_rules_source_present",
            "exterior_blocks",
            "family_inputs.region_capacity.group_demands",
            "family_inputs.region_capacity.group_pose_domains",
            "family_inputs.region_capacity.instance_to_facility_type",
            "family_inputs.region_capacity.pose_occupied_cells",
            "family_inputs.region_capacity.template_dimensions",
            "family_inputs.region_capacity.template_placement_rules",
            "ghost_cells",
            "master_domain_projection",
        }
    ),
    "pattern_nogood": _COMMON_TYPED_SNAPSHOT_FIELDS
    | frozenset(
        {
            "family_inputs.pattern_nogood.artifact_hashes",
            "family_inputs.pattern_nogood.canonical_rules",
            "family_inputs.pattern_nogood.facility_pools",
            "family_inputs.pattern_nogood.facility_templates",
            "family_inputs.pattern_nogood.group_demands",
            "family_inputs.pattern_nogood.group_pose_domains",
            "family_inputs.pattern_nogood.instance_to_facility_type",
            "groups",
        }
    ),
    "shape_packing_hall": _COMMON_TYPED_SNAPSHOT_FIELDS
    | _GHOST_BOUND_SNAPSHOT_FIELDS
    | frozenset(
        {
            "exterior_blocks",
            "family_inputs.shape_packing_hall.ghost",
            "family_inputs.shape_packing_hall.group_demands",
            "family_inputs.shape_packing_hall.group_to_facility_type",
            "family_inputs.shape_packing_hall.template_dimensions",
            "family_inputs.shape_packing_hall.template_placement_rules",
            "ghost_cells",
            "shape_packing_hall_master_domain_projection",
        }
    ),
    "power_hitting_set": _COMMON_TYPED_SNAPSHOT_FIELDS
    | _GHOST_BOUND_SNAPSHOT_FIELDS
    | frozenset(
        {
            "cell_owner",
            "exterior_blocks",
            "family_inputs.power_hitting_set.cell_owner",
            "family_inputs.power_hitting_set.ghost",
            "family_inputs.power_hitting_set.group_pose_domains",
            "family_inputs.power_hitting_set.group_to_facility_type",
            "family_inputs.power_hitting_set.pole_dimensions",
            "family_inputs.power_hitting_set.pole_radius",
            "family_inputs.power_hitting_set.pose_occupied_cells",
            "family_inputs.power_hitting_set.template_needs_power",
            "ghost_cells",
            "power_hitting_set_master_domain_projection",
        }
    ),
}
_EXPECTED_PROJECTIONS = {
    "region_capacity": "_build_f1_master_domain_projection",
    "shape_packing_hall": "_build_f6_master_domain_projection",
    "power_hitting_set": "_build_f7_master_domain_projection",
}
_EXPECTED_LOWERINGS = {
    "region_capacity": ("region_capacity_le", "_lower_region_capacity_cut"),
    "shape_packing_hall": (
        "shape_packing_hall_le",
        "_lower_baseline_packing_cut",
    ),
    "power_hitting_set": (
        "power_pose_exclusion",
        "_lower_power_pose_exclusion_cut",
    ),
}
_EXPECTED_TYPED_ORCHESTRATION_CONTEXTS = {
    "region_capacity": ("state", "canonical_rules", "iter_index"),
    "power_hitting_set": ("state", "solution", "target_poses", "iter_index"),
    "shape_packing_hall": ("state", "region_demand_overrides", "iter_index"),
    "pattern_nogood": ("state", "solution", "mandatory_groups", "iter_index"),
}


class _CapabilitySlot(Protocol):
    def require(self, *, family: str, capability: str) -> object: ...


def _available(
    value: _CapabilitySlot,
    *,
    expected_type: type[object],
    family: str,
    capability: str,
) -> object:
    required = value.require(family=family, capability=capability)
    assert type(required) is expected_type
    return required


def _runtime_imports(path: Path) -> frozenset[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return frozenset(imported)


def _oracle_wire_metadata(module_name: str) -> tuple[str, str, str]:
    path = _REPO_ROOT / f"{module_name.replace('.', '/')}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    constants: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        if not isinstance(value, ast.Constant) or type(value.value) is not str:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                constants[target.id] = value.value
    oracle_name = constants.get("ORACLE_NAME", constants.get("_ORACLE_NAME"))
    family_version = constants.get(
        "FAMILY_VERSION",
        constants.get("_FAMILY_VERSION"),
    )
    validator_version = constants.get(
        "VALIDATOR_VERSION",
        constants.get("_VALIDATOR_VERSION"),
    )
    assert oracle_name is not None
    assert family_version is not None
    assert validator_version is not None
    return oracle_name, family_version, validator_version


def _benders_manifest() -> tuple[frozenset[str], tuple[str, ...]]:
    tree = ast.parse(
        (_REPO_ROOT / "src/search/benders_loop.py").read_text(encoding="utf-8")
    )
    framework_families: frozenset[str] | None = None
    attach_method: ast.FunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if not any(
                isinstance(target, ast.Name)
                and target.id == "_CUT_FRAMEWORK_ALL_FAMILIES"
                for target in targets
            ):
                continue
            value = node.value
            assert isinstance(value, ast.Call)
            assert isinstance(value.func, ast.Name) and value.func.id == "frozenset"
            assert len(value.args) == 1 and isinstance(value.args[0], ast.Set)
            framework_families = frozenset(
                cast(str, ast.literal_eval(element))
                for element in value.args[0].elts
            )
        elif isinstance(node, ast.FunctionDef) and node.name == "_maybe_attach_framework_cuts":
            attach_method = node
    assert framework_families is not None
    assert attach_method is not None

    generator_calls = {
        "generate_pattern_nogood_cuts": "pattern_nogood",
        "generate_power_hitting_set_cuts": "power_hitting_set",
        "generate_region_capacity_cuts": "region_capacity",
        "generate_shape_packing_hall_cuts": "shape_packing_hall",
    }
    ordered_calls = sorted(
        (
            (node.lineno, generator_calls[node.func.id])
            for node in ast.walk(attach_method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in generator_calls
        ),
        key=lambda item: item[0],
    )
    return framework_families, tuple(family for _, family in ordered_calls)


def _typed_apply_surface() -> tuple[frozenset[str], frozenset[str]]:
    tree = ast.parse(
        (_REPO_ROOT / "src/cuts/typed_apply.py").read_text(encoding="utf-8")
    )
    operations: set[str] = set()
    primitives: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Compare)
            and isinstance(node.left, ast.Name)
            and node.left.id == "operation"
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.Eq)
            and len(node.comparators) == 1
            and isinstance(node.comparators[0], ast.Constant)
            and type(node.comparators[0].value) is str
        ):
            operations.add(node.comparators[0].value)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "master"
            and node.func.attr.startswith("_lower_")
        ):
            primitives.add(node.func.attr)
    return frozenset(operations), frozenset(primitives)


def test_shadow_manifest_matches_existing_registry_and_lifecycle_tables() -> None:
    manifest = PRODUCTION_FAMILY_MANIFEST_V1
    runtime_registry = build_production_registry()
    trust = manifest.trust_specs

    assert {family: spec.capability for family, spec in trust.items()} == dict(
        runtime_registry.capabilities
    )
    assert {
        family
        for family, spec in trust.items()
        if spec.typed_plugin.is_available
    } == set(runtime_registry.plugins)
    for family, runtime_plugin in runtime_registry.plugins.items():
        provider = cast(
            PluginProviderSpec,
            _available(
                trust[family].typed_plugin,
                expected_type=PluginProviderSpec,
                family=family,
                capability="typed plugin",
            ),
        )
        runtime_plugin_type = type(runtime_plugin)
        assert type(provider.build()) is runtime_plugin_type
        assert provider.provider.identity.module == runtime_plugin_type.__module__
        assert provider.provider.identity.qualname == runtime_plugin_type.__qualname__

    assert {
        family: spec.capability.mode
        for family, spec in trust.items()
        if spec.capability.stage is not CapabilityStage.RETIRED
    } == _FAMILY_MODE_MAP
    assert (
        frozenset(
            family
            for family, spec in trust.items()
            if spec.capability.stage is not CapabilityStage.RETIRED
        )
        == _EXPECTED_LIVE_FAMILIES
    )
    assert all(
        spec.authority_dependency_closure
        == PRODUCTION_V1_AUTHORITY_DEPENDENCY_CLOSURE
        == spec.capability.required_dependencies
        for spec in trust.values()
    )


def test_shadow_proof_schemas_match_current_cert_payload_tables() -> None:
    trust = PRODUCTION_FAMILY_MANIFEST_V1.trust_specs

    assert frozenset(CERT_PAYLOAD_CERT_KIND_BY_FAMILY) == _EXPECTED_LIVE_FAMILIES
    assert frozenset(CERT_PAYLOAD_ALLOWED_FIELDS) == _EXPECTED_LIVE_FAMILIES
    assert frozenset(CERT_PAYLOAD_REQUIRED_FIELDS) == _EXPECTED_LIVE_FAMILIES
    for family in sorted(_EXPECTED_LIVE_FAMILIES):
        proof_schema = cast(
            ProofSchemaSpec,
            _available(
                trust[family].proof_schema,
                expected_type=ProofSchemaSpec,
                family=family,
                capability="proof schema",
            ),
        )
        assert proof_schema.schema_version == trust[family].capability.proof_schema_version
        assert proof_schema.cert_kind == CERT_PAYLOAD_CERT_KIND_BY_FAMILY[family]
        assert proof_schema.allowed_fields == CERT_PAYLOAD_ALLOWED_FIELDS[family]
        assert proof_schema.required_fields == CERT_PAYLOAD_REQUIRED_FIELDS[family]

    retired = trust["power_grid_reach"]
    assert not retired.proof_schema.is_available
    with pytest.raises(
        CapabilityUnavailableError,
        match="retired-family-has-no-live-proof-schema",
    ):
        retired.proof_schema.require(
            family=retired.family,
            capability="proof schema",
        )


def test_shadow_replay_rule_semantics_and_checker_availability_are_coherent() -> None:
    trust = PRODUCTION_FAMILY_MANIFEST_V1.trust_specs
    semantics = PRODUCTION_RULE_SEMANTICS_V1

    typed_replay: set[str] = set()
    legacy_replay: set[str] = set()
    expected_states = {
        (CapabilityStage.COMPILABLE, ExecutionPath.TYPED): RuleDeploymentState.COMPILABLE,
        (CapabilityStage.VALIDATED, ExecutionPath.TYPED): RuleDeploymentState.VALIDATED_SHADOW_ONLY,
        (
            CapabilityStage.VALIDATED,
            ExecutionPath.LEGACY_DIAGNOSTIC,
        ): RuleDeploymentState.VALIDATED_LEGACY_DIAGNOSTIC,
        (
            CapabilityStage.RETIRED,
            ExecutionPath.LEGACY_DIAGNOSTIC,
        ): RuleDeploymentState.RETIRED,
    }
    for family, spec in trust.items():
        assert all(rule_id in semantics.rules for rule_id in spec.rule_semantic_ids)
        family_rule = semantics.get(family)
        assert (
            family_rule.deployment_state
            is expected_states[(spec.capability.stage, spec.capability.execution_path)]
        )
        assert (
            family_rule.exact_twin_checker.is_available
            is spec.production_exact_checker.is_available
        )
        if spec.replay.is_available:
            replay = cast(
                ReplaySpec,
                _available(
                    spec.replay,
                    expected_type=ReplaySpec,
                    family=family,
                    capability="replay",
                ),
            )
            if replay.kind is ReplayKind.TYPED_SINGLE_ENTRY:
                typed_replay.add(family)
                assert replay.entrypoint.target is validate_and_compile_cut
            else:
                legacy_replay.add(family)
                assert replay.entrypoint.target is LEGACY_DIAGNOSTIC_VALIDATORS[family]

    assert typed_replay == set(TYPED_REPLAY_FAMILIES)
    assert legacy_replay == set(LEGACY_DIAGNOSTIC_VALIDATORS)


def test_snapshot_consumption_and_projection_identities_are_valid() -> None:
    trust = PRODUCTION_FAMILY_MANIFEST_V1.trust_specs
    snapshot_fields = {item.name for item in fields(state_snapshot_module.ValidatedStateSnapshot)}
    input_types = {
        "region_capacity": state_snapshot_module.F1RegionInputs,
        "pattern_nogood": state_snapshot_module.F5PatternNogoodInputs,
        "shape_packing_hall": state_snapshot_module.F6HallInputs,
        "power_hitting_set": state_snapshot_module.F7PowerInputs,
    }
    assert {
        family: spec.consumed_snapshot_field_ids
        for family, spec in trust.items()
        if spec.consumed_snapshot_field_ids
    } == _EXPECTED_CONSUMED_SNAPSHOT_FIELDS
    for family, spec in trust.items():
        if spec.snapshot_input.is_available:
            snapshot_input = cast(
                SnapshotInputSpec,
                _available(
                    spec.snapshot_input,
                    expected_type=SnapshotInputSpec,
                    family=family,
                    capability="snapshot input",
                ),
            )
            input_type = input_types[family]
            assert snapshot_input.family_input_key == family
            assert snapshot_input.record_type.module == input_type.__module__
            assert snapshot_input.record_type.qualname == input_type.__qualname__
            nested_fields = {item.name for item in fields(input_type)}
            for field_id in spec.consumed_snapshot_field_ids:
                parts = field_id.split(".")
                assert parts[0] in snapshot_fields
                if parts[0] == "family_inputs":
                    assert len(parts) == 3
                    assert parts[1] == family
                    assert parts[2] in nested_fields
        else:
            assert not spec.consumed_snapshot_field_ids

        if spec.master_domain_projection.is_available:
            projection = cast(
                SnapshotProjectionSpec,
                _available(
                    spec.master_domain_projection,
                    expected_type=SnapshotProjectionSpec,
                    family=family,
                    capability="master-domain projection",
                ),
            )
            builder = getattr(state_snapshot_module, projection.builder.qualname)
            assert projection.builder.qualname == _EXPECTED_PROJECTIONS[family]
            assert projection.builder.module == builder.__module__
            assert projection.builder.qualname == builder.__qualname__
        else:
            assert family not in _EXPECTED_PROJECTIONS


def test_lowering_and_benders_shadow_rows_match_closed_runtime_surfaces() -> None:
    manifest = PRODUCTION_FAMILY_MANIFEST_V1
    lowering_rows: dict[str, LoweringSpec] = {}
    for family, spec in manifest.trust_specs.items():
        if spec.lowering.is_available:
            lowering_rows[family] = cast(
                LoweringSpec,
                _available(
                    spec.lowering,
                    expected_type=LoweringSpec,
                    family=family,
                    capability="lowering",
                ),
            )

    operations, primitives = _typed_apply_surface()
    assert operations == SUPPORTED_OPERATIONS
    assert {
        family: (row.operation, row.master_primitive)
        for family, row in lowering_rows.items()
    } == _EXPECTED_LOWERINGS
    assert frozenset(
        row.operation for row in lowering_rows.values()
    ) == SUPPORTED_OPERATIONS
    assert frozenset(
        row.master_primitive for row in lowering_rows.values()
    ) == primitives

    benders_families, benders_order = _benders_manifest()
    assert benders_families == frozenset(manifest.typed_generation_order)
    assert benders_order == manifest.typed_generation_order
    assert TYPED_FAMILY_GENERATION_ORDER_V1 == manifest.typed_generation_order
    assert frozenset(TYPED_FAMILY_GENERATION_INVOKERS_V1) == benders_families
    for family, generation in manifest.generation_specs.items():
        if generation.surface is GenerationSurface.RETIRED:
            assert not generation.oracle_name.is_available
            assert not generation.family_version.is_available
            assert not generation.validator_version.is_available
            assert not generation.generation_invoker.is_available
            continue
        generator_ref = cast(
            StaticCallableRef,
            generation.generator.require(
                family=family,
                capability="generator",
            ),
        )
        assert (
            cast(
                str,
                generation.oracle_name.require(
                    family=family,
                    capability="oracle name",
                ),
            ),
            cast(
                str,
                generation.family_version.require(
                    family=family,
                    capability="family version",
                ),
            ),
            cast(
                str,
                generation.validator_version.require(
                    family=family,
                    capability="validator version",
                ),
            ),
        ) == _oracle_wire_metadata(generator_ref.identity.module)
        if generation.surface is GenerationSurface.LEGACY_DIAGNOSTIC:
            assert generation.orchestration_context_ids == ()
            assert not generation.generation_invoker.is_available

    for family in manifest.typed_generation_order:
        generation = manifest.generation(family)
        assert generation.surface is GenerationSurface.TYPED_ATTACH
        assert (
            generation.orchestration_context_ids
            == _EXPECTED_TYPED_ORCHESTRATION_CONTEXTS[family]
        )
        generator_ref = cast(
            StaticCallableRef,
            generation.generator.require(
                family=family,
                capability="generator",
            ),
        )
        assert generator_ref.target.__name__ == f"generate_{family}_cuts"
        invoker_identity = cast(
            StaticSymbolIdentity,
            generation.generation_invoker.require(
                family=family,
                capability="generation invoker",
            ),
        )
        invoker = TYPED_FAMILY_GENERATION_INVOKERS_V1[family]
        assert typed_family_generation_invoker(family) is invoker
        assert invoker_identity.module == invoker.__module__
        assert invoker_identity.qualname == invoker.__qualname__
        assert tuple(inspect.signature(invoker).parameters) == ("request",)


def test_contract_ids_and_unavailable_capabilities_fail_closed() -> None:
    manifest = PRODUCTION_FAMILY_MANIFEST_V1
    assert set().union(
        *(set(spec.required_contract_ids) for spec in manifest.trust_specs.values())
    ) <= FAMILY_CONTRACT_IDS_V1

    retired = manifest.trust("power_grid_reach")
    for name, capability in (
        ("typed plugin", retired.typed_plugin),
        ("exact checker", retired.production_exact_checker),
        ("snapshot input", retired.snapshot_input),
        ("master-domain projection", retired.master_domain_projection),
        ("lowering", retired.lowering),
        ("replay", retired.replay),
    ):
        with pytest.raises(CapabilityUnavailableError):
            capability.require(family=retired.family, capability=name)

    with pytest.raises(KeyError, match="unknown family trust spec"):
        manifest.trust("unknown_family")
    with pytest.raises(KeyError, match="unknown family generation spec"):
        manifest.generation("unknown_family")
    with pytest.raises(TypeError):
        manifest.trust_specs["unknown_family"] = retired  # type: ignore[index]


def test_manifest_rows_are_deeply_immutable_and_stage_contracts_are_required() -> None:
    manifest = PRODUCTION_FAMILY_MANIFEST_V1
    trust = manifest.trust("region_capacity")
    generation = manifest.generation("region_capacity")

    with pytest.raises(TypeError, match="non-empty exact tuple"):
        replace(trust, rule_semantics=list(trust.rule_semantics))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="exact tuple"):
        replace(
            trust,
            required_contract_ids=list(trust.required_contract_ids),  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="available value"):
        replace(
            trust,
            typed_plugin=AvailableCapability(object()),  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="missing stage/path contract"):
        replace(trust, required_contract_ids=("unknown_type",))
    with pytest.raises(TypeError, match="preparation_steps must be an exact tuple"):
        replace(
            generation,
            preparation_steps=list(generation.preparation_steps),  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="requires a static uniform invoker"):
        replace(
            generation,
            generation_invoker=UnavailableCapability("missing-test-invoker"),
        )
    legacy_generation = manifest.generation("cutset")
    with pytest.raises(ValueError, match="cannot advertise a typed invoker"):
        replace(
            legacy_generation,
            generation_invoker=generation.generation_invoker,
        )


def test_family_manifest_audit_digest_is_canonical_and_rule_ledger_bound() -> None:
    manifest = PRODUCTION_FAMILY_MANIFEST_V1
    rebuilt = FamilySpecRegistry(
        schema_version=1,
        rule_semantics=manifest.rule_semantics,
        trust_specs=dict(reversed(tuple(manifest.trust_specs.items()))),
        generation_specs=dict(
            reversed(tuple(manifest.generation_specs.items()))
        ),
        typed_generation_order=manifest.typed_generation_order,
    )

    assert rebuilt.audit_projection() == manifest.audit_projection()
    assert rebuilt.audit_digest == manifest.audit_digest
    assert (
        manifest.audit_digest
        == PINNED_PRODUCTION_FAMILY_MANIFEST_AUDIT_DIGEST_V1
    )
    assert len(manifest.audit_digest) == 64
    int(manifest.audit_digest, 16)
    assert (
        manifest.audit_projection()["rule_semantics_audit_digest"]
        == PRODUCTION_RULE_SEMANTICS_V1.audit_digest
    )


@pytest.mark.parametrize(
    ("capability_stage", "rule_state", "surface", "telemetry", "extra_contracts"),
    (
        (
            CapabilityStage.EXPERIMENTAL,
            RuleDeploymentState.EXPERIMENTAL,
            GenerationSurface.EXPERIMENTAL,
            TelemetryProfile.EXPERIMENTAL,
            frozenset({"experimental_fail_closed"}),
        ),
        (
            CapabilityStage.ENABLED,
            RuleDeploymentState.ENABLED,
            GenerationSurface.TYPED_ATTACH,
            TelemetryProfile.TYPED_ENABLED,
            frozenset({"enabled_authority_gate"}),
        ),
    ),
)
def test_manifest_protocol_represents_experimental_and_enabled_stages(
    capability_stage: CapabilityStage,
    rule_state: RuleDeploymentState,
    surface: GenerationSurface,
    telemetry: TelemetryProfile,
    extra_contracts: frozenset[str],
) -> None:
    manifest = PRODUCTION_FAMILY_MANIFEST_V1
    family = "region_capacity"
    base_trust = manifest.trust(family)
    base_generation = manifest.generation(family)
    base_rule = PRODUCTION_RULE_SEMANTICS_V1.get(family)
    rules = dict(PRODUCTION_RULE_SEMANTICS_V1.rules)
    rules[family] = replace(base_rule, deployment_state=rule_state)
    rule_registry = RuleSemanticRegistry(
        schema_version=1,
        information_dag=PRODUCTION_RULE_SEMANTICS_V1.information_dag,
        rules=rules,
    )

    if capability_stage is CapabilityStage.EXPERIMENTAL:
        unavailable = UnavailableCapability("experimental-not-production")
        trust = replace(
            base_trust,
            capability=replace(
                base_trust.capability,
                stage=CapabilityStage.EXPERIMENTAL,
                compiler_version=None,
            ),
            master_domain_projection=unavailable,
            lowering=unavailable,
            replay=unavailable,
            telemetry_profile=telemetry,
            required_contract_ids=(
                "experimental_fail_closed",
                "tcb_fault_propagation",
                "unknown_type",
            ),
        )
        generation = replace(
            base_generation,
            surface=surface,
            generation_invoker=UnavailableCapability(
                "experimental-not-production"
            ),
            orchestration_context_ids=(),
            production_typed_order=None,
        )
        typed_order: tuple[str, ...] = ()
    else:
        trust = replace(
            base_trust,
            capability=replace(
                base_trust.capability,
                stage=CapabilityStage.ENABLED,
            ),
            telemetry_profile=telemetry,
            required_contract_ids=(
                *base_trust.required_contract_ids,
                *sorted(extra_contracts),
            ),
        )
        generation = base_generation
        typed_order = (family,)

    local = FamilySpecRegistry(
        schema_version=1,
        rule_semantics=rule_registry,
        trust_specs={family: trust},
        generation_specs={family: generation},
        typed_generation_order=typed_order,
    )
    assert local.trust(family).capability.stage is capability_stage
    assert local.generation(family).surface is surface


def test_manifest_schema_allows_registered_family_to_share_operation_metadata() -> None:
    """A metadata-only fixture can share a primitive without widening typed_apply.

    This Milestone-A fixture proves registration convergence only.  It does not
    claim an executable proof-to-plan chain: a future family still needs its own
    generator, proof verifier, and independent exact checker before promotion.
    """

    manifest = PRODUCTION_FAMILY_MANIFEST_V1
    base_trust = manifest.trust("region_capacity")
    base_generation = manifest.generation("region_capacity")
    fixture_family = "test_region_capacity_fixture"
    fixture_capability = replace(base_trust.capability, name=fixture_family)
    base_proof_schema = cast(
        ProofSchemaSpec,
        base_trust.proof_schema.require(
            family=base_trust.family,
            capability="proof schema",
        ),
    )
    fixture_trust = replace(
        base_trust,
        capability=fixture_capability,
        proof_schema=AvailableCapability(
            replace(base_proof_schema, family=fixture_family)
        ),
        rule_semantics=(
            VersionedRuleRef(
                rule_id=fixture_family,
                semantic_version=base_trust.rule_semantics[0].semantic_version,
            ),
            *base_trust.rule_semantics[1:],
        ),
    )
    fixture_generation = replace(
        base_generation,
        family=fixture_family,
        production_typed_order=1,
    )
    trust_specs = {
        base_trust.family: base_trust,
        fixture_family: fixture_trust,
    }
    generation_specs = {
        base_generation.family: base_generation,
        fixture_family: fixture_generation,
    }
    with pytest.raises(ValueError, match="unknown rule semantic IDs"):
        FamilySpecRegistry(
            schema_version=1,
            rule_semantics=PRODUCTION_RULE_SEMANTICS_V1,
            trust_specs=trust_specs,
            generation_specs=generation_specs,
            typed_generation_order=(base_trust.family, fixture_family),
        )

    base_rule = PRODUCTION_RULE_SEMANTICS_V1.get(base_trust.family)
    fixture_rule = replace(
        base_rule,
        rule_id=fixture_family,
        necessary_projection=(
            None
            if base_rule.necessary_projection is None
            else replace(
                base_rule.necessary_projection,
                facet_id=f"{fixture_family}.necessary_projection",
            )
        ),
        exact_semantics=(
            None
            if base_rule.exact_semantics is None
            else replace(
                base_rule.exact_semantics,
                facet_id=f"{fixture_family}.exact_semantics",
            )
        ),
    )
    fixture_rule_registry = RuleSemanticRegistry(
        schema_version=1,
        information_dag=PRODUCTION_RULE_SEMANTICS_V1.information_dag,
        rules={
            **PRODUCTION_RULE_SEMANTICS_V1.rules,
            fixture_family: fixture_rule,
        },
    )
    local = FamilySpecRegistry(
        schema_version=1,
        rule_semantics=fixture_rule_registry,
        trust_specs=trust_specs,
        generation_specs=generation_specs,
        typed_generation_order=(base_trust.family, fixture_family),
    )

    base_lowering = cast(
        LoweringSpec,
        local.trust(base_trust.family).lowering.require(
            family=base_trust.family,
            capability="lowering",
        ),
    )
    fixture_lowering = cast(
        LoweringSpec,
        local.trust(fixture_family).lowering.require(
            family=fixture_family,
            capability="lowering",
        ),
    )
    assert fixture_lowering.operation == base_lowering.operation
    assert (
        fixture_lowering.typed_apply_entrypoint.target
        is base_lowering.typed_apply_entrypoint.target
    )


def test_milestone_a_runtime_modules_do_not_import_shadow_specs() -> None:
    forbidden = frozenset(
        {
            "src.cuts.family_specs",
            "src.cuts.rule_semantics",
            "src.search.family_generation",
        }
    )
    for relative_path in _RUNTIME_FILES:
        assert _runtime_imports(_REPO_ROOT / relative_path).isdisjoint(forbidden)
