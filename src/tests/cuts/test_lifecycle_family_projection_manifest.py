"""Pure contract tests for manifest-driven lifecycle projection selection."""

from __future__ import annotations

import weakref
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

import src.cuts.lifecycle as lifecycle
import src.cuts.typed_apply as typed_apply
import src.cuts.typed_platform as typed_platform
from src.cuts.family_specs import (
    PRODUCTION_FAMILY_MANIFEST_V1,
    AvailableCapability,
    FamilySpecRegistry,
    PluginProviderSpec,
    ProofSchemaSpec,
    SnapshotProjectionKind,
)
from src.cuts.rule_semantics import (
    PRODUCTION_RULE_SEMANTICS_V1,
    RuleSemanticRegistry,
    VersionedRuleRef,
)


_BASE_FAMILY = "region_capacity"
_ALIAS_FAMILY = "test_region_capacity_projection_alias"
_F1_FINGERPRINT = "1" * 64
_F6_FINGERPRINT = "6" * 64
_F7_FINGERPRINT = "7" * 64
_SNAPSHOT_DIGEST = "d" * 64


class _WeakrefableMaster:
    pass


def _projection_snapshot(
    *,
    fingerprint: str = _F1_FINGERPRINT,
    f1: str = _F1_FINGERPRINT,
    f6: str = _F6_FINGERPRINT,
    f7: str = _F7_FINGERPRINT,
) -> tuple[SimpleNamespace, SimpleNamespace]:
    scope = SimpleNamespace(
        domain_fingerprint=fingerprint,
        ghost_policy="agnostic",
        ghost_rect_digest=None,
    )
    snapshot = SimpleNamespace(
        digest=_SNAPSHOT_DIGEST,
        master_domain_projection=f1,
        shape_packing_hall_master_domain_projection=f6,
        power_hitting_set_master_domain_projection=f7,
        ghost_cells=frozenset(),
        exterior_blocks=frozenset(),
    )
    return scope, snapshot


def _alias_manifest() -> FamilySpecRegistry:
    base_trust = PRODUCTION_FAMILY_MANIFEST_V1.trust(_BASE_FAMILY)
    base_generation = PRODUCTION_FAMILY_MANIFEST_V1.generation(_BASE_FAMILY)
    base_rule = PRODUCTION_RULE_SEMANTICS_V1.get(_BASE_FAMILY)
    base_proof_schema = base_trust.proof_schema.require(
        family=_BASE_FAMILY,
        capability="proof schema",
    )
    assert type(base_proof_schema) is ProofSchemaSpec
    base_plugin = base_trust.typed_plugin.require(
        family=_BASE_FAMILY,
        capability="typed plugin",
    )
    assert type(base_plugin) is PluginProviderSpec

    fixture_rule = replace(
        base_rule,
        rule_id=_ALIAS_FAMILY,
        necessary_projection=(
            None
            if base_rule.necessary_projection is None
            else replace(
                base_rule.necessary_projection,
                facet_id=f"{_ALIAS_FAMILY}.necessary_projection",
            )
        ),
        exact_semantics=(
            None
            if base_rule.exact_semantics is None
            else replace(
                base_rule.exact_semantics,
                facet_id=f"{_ALIAS_FAMILY}.exact_semantics",
            )
        ),
    )
    rule_semantics = RuleSemanticRegistry(
        schema_version=1,
        information_dag=PRODUCTION_RULE_SEMANTICS_V1.information_dag,
        rules={
            **PRODUCTION_RULE_SEMANTICS_V1.rules,
            _ALIAS_FAMILY: fixture_rule,
        },
    )
    fixture_trust = replace(
        base_trust,
        capability=replace(base_trust.capability, name=_ALIAS_FAMILY),
        proof_schema=AvailableCapability(
            replace(base_proof_schema, family=_ALIAS_FAMILY),
        ),
        rule_semantics=(
            VersionedRuleRef(
                rule_id=_ALIAS_FAMILY,
                semantic_version=base_rule.semantic_version,
            ),
            *base_trust.rule_semantics[1:],
        ),
        typed_plugin=AvailableCapability(
            replace(
                base_plugin,
                production_order=1,
                factory_construction_order=1,
            ),
        ),
    )
    fixture_generation = replace(
        base_generation,
        family=_ALIAS_FAMILY,
        production_typed_order=1,
    )
    return FamilySpecRegistry(
        schema_version=1,
        rule_semantics=rule_semantics,
        trust_specs={
            _BASE_FAMILY: base_trust,
            _ALIAS_FAMILY: fixture_trust,
        },
        generation_specs={
            _BASE_FAMILY: base_generation,
            _ALIAS_FAMILY: fixture_generation,
        },
        typed_generation_order=(_BASE_FAMILY, _ALIAS_FAMILY),
    )


def test_legacy_fingerprint_recognition_keeps_f1_f6_f7_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, snapshot = _projection_snapshot(
        f1=_F1_FINGERPRINT,
        f6=_F1_FINGERPRINT,
        f7=_F1_FINGERPRINT,
    )
    observed: list[tuple[str, object]] = []

    def fake_live_projection(
        master: object,
        family: str,
        *,
        family_specs: object = None,
    ) -> str:
        del master
        observed.append((family, family_specs))
        return _F1_FINGERPRINT

    monkeypatch.setattr(lifecycle, "_live_master_domain_projection", fake_live_projection)

    family, projection = lifecycle._resolve_live_master_domain_projection(
        scope,
        snapshot,
        object(),
    )

    assert family == _BASE_FAMILY
    assert projection == _F1_FINGERPRINT
    assert observed == [(_BASE_FAMILY, None)]


def test_checked_alias_family_can_share_region_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _alias_manifest()
    scope, snapshot = _projection_snapshot()
    observed: list[tuple[str, object]] = []

    def fake_live_projection(
        master: object,
        family: str,
        *,
        family_specs: object = None,
    ) -> str:
        del master
        observed.append((family, family_specs))
        return _F1_FINGERPRINT

    monkeypatch.setattr(lifecycle, "_live_master_domain_projection", fake_live_projection)

    family, projection = lifecycle._resolve_live_master_domain_projection(
        scope,
        snapshot,
        object(),
        family=_ALIAS_FAMILY,
        family_specs=manifest,
    )

    assert (
        lifecycle._family_projection_kind(_ALIAS_FAMILY, manifest)
        is SnapshotProjectionKind.REGION_CAPACITY
    )
    assert family == _ALIAS_FAMILY
    assert projection == _F1_FINGERPRINT
    assert observed == [(_ALIAS_FAMILY, manifest)]


def test_explicit_cross_projection_keeps_legacy_resolved_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, snapshot = _projection_snapshot(fingerprint=_F6_FINGERPRINT)
    observed: list[tuple[str, object]] = []

    def fake_live_projection(
        master: object,
        family: str,
        *,
        family_specs: object = None,
    ) -> str:
        del master
        observed.append((family, family_specs))
        return _F6_FINGERPRINT

    monkeypatch.setattr(lifecycle, "_live_master_domain_projection", fake_live_projection)

    family, projection = lifecycle._resolve_live_master_domain_projection(
        scope,
        snapshot,
        object(),
        family=_BASE_FAMILY,
        family_specs=PRODUCTION_FAMILY_MANIFEST_V1,
    )

    assert family == "shape_packing_hall"
    assert projection == _F6_FINGERPRINT
    assert observed == [("shape_packing_hall", None)]


def test_model_scope_resolver_threads_checked_alias_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _alias_manifest()
    scope, snapshot = _projection_snapshot()
    master = _WeakrefableMaster()
    sentinel = object()
    built: dict[str, object] = {}

    def fake_live_projection(
        live_master: object,
        family: str,
        *,
        family_specs: object = None,
    ) -> str:
        assert live_master is master
        assert family == _ALIAS_FAMILY
        assert family_specs is manifest
        return _F1_FINGERPRINT

    def fake_build_model_scope_binding(**kwargs: object) -> object:
        built.update(kwargs)
        return sentinel

    monkeypatch.setattr(lifecycle, "_live_master_domain_projection", fake_live_projection)
    monkeypatch.setattr(
        typed_platform,
        "_build_model_scope_binding",
        fake_build_model_scope_binding,
    )

    result = lifecycle._resolve_model_scope_binding(
        scope,
        snapshot,
        master,
        family=_ALIAS_FAMILY,
        family_specs=manifest,
    )

    assert result is sentinel
    assert built["master_domain_family"] == _ALIAS_FAMILY
    assert built["master_domain_projection"] == _F1_FINGERPRINT
    assert built["snapshot_digest"] == _SNAPSHOT_DIGEST
    assert built["master_ref"]() is master  # type: ignore[operator]


def test_step_8_uses_supplied_manifest_for_fresh_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _alias_manifest()
    master = _WeakrefableMaster()
    scope = SimpleNamespace(
        ghost_policy="agnostic",
        ghost_rect_digest=None,
        domain_fingerprint=_F1_FINGERPRINT,
    )

    class _CompiledCut:
        def __init__(self) -> None:
            self.plan = SimpleNamespace(family=_ALIAS_FAMILY, model_scope=scope)
            self.snapshot_digest = _SNAPSHOT_DIGEST

    class _ScopeBinding:
        def __init__(self) -> None:
            self.ghost_rect_digest = None
            self.master_domain_projection = _F1_FINGERPRINT
            self.snapshot_digest = _SNAPSHOT_DIGEST
            self.master_domain_family = _ALIAS_FAMILY
            self.master_ref = weakref.ref(master)
            self.rect_idx = None
            self.condition_lits: tuple[object, ...] = ()

    observed: list[tuple[str, object]] = []
    applied: list[tuple[object, object, object]] = []

    def fake_live_projection(
        live_master: object,
        family: str,
        *,
        family_specs: object = None,
    ) -> str:
        assert live_master is master
        observed.append((family, family_specs))
        return _F1_FINGERPRINT

    def fake_apply(
        compiled_cut: object,
        live_master: object,
        *,
        scope_binding: object,
    ) -> None:
        applied.append((compiled_cut, live_master, scope_binding))

    monkeypatch.setattr(typed_platform, "CompiledCut", _CompiledCut)
    monkeypatch.setattr(typed_platform, "ModelScopeBinding", _ScopeBinding)
    monkeypatch.setattr(lifecycle, "_live_master_domain_projection", fake_live_projection)
    monkeypatch.setattr(typed_apply, "apply_compiled_cut", fake_apply)

    compiled = _CompiledCut()
    binding = _ScopeBinding()
    lifecycle.step_8_apply_to_master(
        compiled,  # type: ignore[arg-type]
        master,
        scope_binding=binding,  # type: ignore[arg-type]
        family_specs=manifest,
    )

    assert observed == [(_ALIAS_FAMILY, manifest)]
    assert applied == [(compiled, master, binding)]


def test_unknown_fingerprint_keeps_existing_error_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope, snapshot = _projection_snapshot(fingerprint="0" * 64)
    monkeypatch.setattr(
        lifecycle,
        "_live_master_domain_projection",
        pytest.fail,
    )

    with pytest.raises(
        ValueError,
        match=(
            "resolver: plan domain fingerprint matches no snapshot family "
            "projection \\(fail-closed\\)"
        ),
    ):
        lifecycle._resolve_live_master_domain_projection(
            scope,
            snapshot,
            object(),
        )


def test_explicit_manifest_must_be_exact_registry() -> None:
    scope, snapshot = _projection_snapshot()

    with pytest.raises(
        TypeError,
        match="resolver: family_specs must be an exact FamilySpecRegistry",
    ):
        lifecycle._resolve_live_master_domain_projection(
            scope,
            snapshot,
            object(),
            family=_ALIAS_FAMILY,
            family_specs=object(),  # type: ignore[arg-type]
        )
