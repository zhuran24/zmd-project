"""Milestone-B parity gates for manifest-backed registry and replay metadata."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import textwrap
from typing import cast

import pytest

from src.cuts.families.component_reach import validate_component_reach
from src.cuts.families.cutset import validate_cutset
from src.cuts.families.density_envelope import validate_density_envelope
from src.cuts.families.port_exposure import validate_port_exposure
from src.cuts.family_specs import (
    PRODUCTION_FAMILY_MANIFEST_V1,
    FamilySpecRegistry,
    FamilyTrustSpec,
    LoweringSpec,
    PluginProviderKind,
    PluginProviderSpec,
    ReplayKind,
    ReplaySpec,
)
from src.cuts.replay import (
    LEGACY_DIAGNOSTIC_VALIDATORS,
    TYPED_REPLAY_FAMILIES,
)
from src.cuts.typed_platform import (
    ConstraintPlan,
    CutEnvelope,
    CutProvenance,
    FamilyCapabilityRegistry,
    ModelScope,
    ScopeManifest,
    SemanticCutRejection,
    _PRODUCTION_F5_PLUGIN,
    _validate_compiled_plan,
    build_production_registry,
)


_ZERO_DIGEST = "0" * 64
_SEMANTIC_FINGERPRINT = "1" * 64


def _envelope(*, family: str) -> CutEnvelope:
    proof_payload = b"manifest-migration-proof"
    return CutEnvelope(
        cut_id="manifest-migration-cut",
        family=family,
        family_schema_version=1,
        proof_payload=proof_payload,
        proof_hash=hashlib.sha256(proof_payload).hexdigest(),
        scope=ScopeManifest(
            scope_schema_version=1,
            family=family,
            ghost_policy="agnostic",
            ghost_rect_digest=None,
            blocked_cells_digest=None,
            exterior_blocks_digest=_ZERO_DIGEST,
            source_digest=_ZERO_DIGEST,
            dependency_hashes=(),
            oracle_abstraction_version="manifest-migration-v1",
            assumptions=(),
        ),
        provenance=CutProvenance(
            family_version="manifest-migration-v1",
            validator_version="manifest-migration-v1",
            oracle_name="manifest-migration",
            oracle_cert_hash="",
            created_at="",
            iter_index=0,
        ),
    )


def _plan(*, family: str, operation: str) -> ConstraintPlan:
    parameters_by_operation: dict[str, dict[str, object]] = {
        "power_pose_exclusion": {
            "blocked_cells_digest": "2" * 64,
            "group_id": "g1",
            "pose_id": "p1",
        },
        "region_capacity_le": {
            "capacity": 1,
            "group_cell_weights": {"g1": 1},
        },
    }
    return ConstraintPlan(
        family=family,
        schema_version=1,
        semantic_fingerprint=_SEMANTIC_FINGERPRINT,
        model_scope=ModelScope(
            ghost_policy="agnostic",
            ghost_rect_digest=None,
            domain_fingerprint="manifest-migration-domain",
        ),
        operation=operation,
        parameters=parameters_by_operation[operation],
    )


def test_production_registry_is_derived_from_exact_manifest() -> None:
    registry = build_production_registry()
    second = build_production_registry()
    manifest = cast(FamilySpecRegistry, PRODUCTION_FAMILY_MANIFEST_V1)

    assert registry.family_specs is manifest
    assert tuple(registry.capabilities) == tuple(manifest.trust_specs)
    for family, trust in manifest.trust_specs.items():
        assert registry.capabilities[family] == trust.capability
        assert registry.capabilities[family] is not trust.capability
        assert registry.capabilities[family] is not second.capabilities[family]

    expected_plugin_families = {
        family
        for family, trust in manifest.trust_specs.items()
        if trust.typed_plugin.is_available
    }
    assert set(registry.plugins) == expected_plugin_families
    assert tuple(registry.plugins) == (
        "pattern_nogood",
        "power_hitting_set",
        "region_capacity",
        "shape_packing_hall",
    )
    assert tuple(registry.plugins) == manifest.typed_plugin_order
    for family in expected_plugin_families:
        provider = cast(
            PluginProviderSpec,
            manifest.trust(family).typed_plugin.require(
                family=family,
                capability="typed plugin",
            ),
        )
        if provider.kind is PluginProviderKind.FACTORY:
            assert type(registry.plugins[family]) is provider.provider.target
            assert registry.plugins[family] is not second.plugins[family]
        else:
            assert registry.plugins[family] is provider.provider.target
            assert second.plugins[family] is provider.provider.target

    assert registry.plugins["pattern_nogood"] is _PRODUCTION_F5_PLUGIN
    assert second.plugins["pattern_nogood"] is _PRODUCTION_F5_PLUGIN


def test_registry_manifest_seam_is_optional_exact_and_checked_after_legacy_errors() -> None:
    local = FamilyCapabilityRegistry(capabilities={}, plugins={})
    assert local.family_specs is None

    with pytest.raises(
        TypeError,
        match="registry capabilities/plugins must be mappings",
    ):
        FamilyCapabilityRegistry(
            capabilities=object(),  # type: ignore[arg-type]
            plugins={},
            family_specs=object(),  # type: ignore[arg-type]
        )
    with pytest.raises(
        TypeError,
        match="registry family_specs must be an exact FamilySpecRegistry or None",
    ):
        FamilyCapabilityRegistry(
            capabilities={},
            plugins={},
            family_specs=object(),  # type: ignore[arg-type]
        )
    with pytest.raises(
        ValueError,
        match="registry capabilities must exactly cover family_specs trust rows",
    ):
        FamilyCapabilityRegistry(
            capabilities={},
            plugins={},
            family_specs=PRODUCTION_FAMILY_MANIFEST_V1,
        )


def test_production_plugin_factory_and_mapping_orders_preserve_v1_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = PRODUCTION_FAMILY_MANIFEST_V1
    provider_family = {
        id(
            manifest.trust(family).typed_plugin.require(
                family=family,
                capability="typed plugin",
            )
        ): family
        for family in manifest.typed_plugin_order
    }
    original_build = PluginProviderSpec.build
    observed: list[str] = []

    def recording_build(provider: PluginProviderSpec) -> object:
        observed.append(provider_family[id(provider)])
        return original_build(provider)

    monkeypatch.setattr(PluginProviderSpec, "build", recording_build)
    registry = build_production_registry()

    assert observed == [
        "region_capacity",
        "power_hitting_set",
        "shape_packing_hall",
        "pattern_nogood",
    ]
    assert manifest.typed_plugin_factory_order == (
        "region_capacity",
        "power_hitting_set",
        "shape_packing_hall",
    )
    assert tuple(registry.plugins) == (
        "pattern_nogood",
        "power_hitting_set",
        "region_capacity",
        "shape_packing_hall",
    )


def test_production_plan_operation_comes_from_manifest_and_local_seam_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = PRODUCTION_FAMILY_MANIFEST_V1
    envelope = _envelope(family="region_capacity")
    capability = manifest.trust("region_capacity").capability
    region_plan = _plan(
        family="region_capacity",
        operation="region_capacity_le",
    )
    assert (
        _validate_compiled_plan(
            region_plan,
            envelope=envelope,
            capability=capability,
            family_specs=manifest,
        )
        is region_plan
    )

    power_plan = _plan(
        family="region_capacity",
        operation="power_pose_exclusion",
    )
    calls: list[str] = []

    def manifest_trust_override(
        self: FamilySpecRegistry,
        family: str,
    ) -> FamilyTrustSpec:
        assert self is manifest
        calls.append(family)
        return manifest.trust_specs["power_hitting_set"]

    monkeypatch.setattr(
        FamilySpecRegistry,
        "trust",
        manifest_trust_override,
    )
    assert (
        _validate_compiled_plan(
            power_plan,
            envelope=envelope,
            capability=capability,
            family_specs=manifest,
        )
        is power_plan
    )
    assert calls == ["region_capacity"]

    with pytest.raises(
        SemanticCutRejection,
        match="ConstraintPlan.operation is invalid for envelope family",
    ) as rejection:
        _validate_compiled_plan(
            power_plan,
            envelope=envelope,
            capability=capability,
            family_specs=None,
        )
    assert rejection.value.stage == "plan"
    assert rejection.value.reason == (
        "ConstraintPlan.operation is invalid for envelope family"
    )


def test_replay_public_tables_preserve_type_order_values_and_manifest_partition() -> None:
    manifest = PRODUCTION_FAMILY_MANIFEST_V1
    expected_legacy = {
        "cutset": validate_cutset,
        "port_exposure": validate_port_exposure,
        "component_reach": validate_component_reach,
        "density_envelope": validate_density_envelope,
    }

    assert type(TYPED_REPLAY_FAMILIES) is frozenset
    assert TYPED_REPLAY_FAMILIES == frozenset(
        {
            "region_capacity",
            "pattern_nogood",
            "shape_packing_hall",
            "power_hitting_set",
        }
    )
    assert type(LEGACY_DIAGNOSTIC_VALIDATORS) is dict
    assert tuple(LEGACY_DIAGNOSTIC_VALIDATORS) == tuple(expected_legacy)
    for family, validator in expected_legacy.items():
        assert LEGACY_DIAGNOSTIC_VALIDATORS[family] is validator

    replay_families: set[str] = set()
    for family, trust in manifest.trust_specs.items():
        if not trust.replay.is_available:
            continue
        replay = cast(
            ReplaySpec,
            trust.replay.require(family=family, capability="replay"),
        )
        replay_families.add(family)
        if replay.kind is ReplayKind.TYPED_SINGLE_ENTRY:
            assert family in TYPED_REPLAY_FAMILIES
        else:
            assert LEGACY_DIAGNOSTIC_VALIDATORS[family] is replay.entrypoint.target
    assert replay_families == (
        set(TYPED_REPLAY_FAMILIES) | set(LEGACY_DIAGNOSTIC_VALIDATORS)
    )


def test_all_production_compilable_rows_have_exact_manifest_lowering() -> None:
    registry = build_production_registry()
    assert registry.family_specs is not None
    for family, capability in registry.capabilities.items():
        if capability.compiler_version is None:
            continue
        lowering = registry.family_specs.trust(family).lowering.require(
            family=family,
            capability="trusted lowering",
        )
        assert type(lowering) is LoweringSpec


def test_manifest_first_import_is_not_captured_by_typed_entrypoint_patch() -> None:
    """A fresh process must record static identity, not a transient monkeypatch."""

    project_root = Path(__file__).resolve().parents[3]
    probe = textwrap.dedent(
        """
        from unittest.mock import patch
        import src.cuts.typed_platform as platform

        with patch.object(platform, "validate_and_compile_cut"):
            import src.cuts.family_specs as specs

        replay = specs.PRODUCTION_FAMILY_MANIFEST_V1.trust(
            "region_capacity"
        ).replay.require(family="region_capacity", capability="replay")
        entrypoint = replay.entrypoint
        assert type(entrypoint) is specs.StaticSymbolIdentity
        assert entrypoint.module == "src.cuts.typed_platform"
        assert entrypoint.qualname == "validate_and_compile_cut"
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
