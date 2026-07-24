"""External parity and isolation gates for the test-only family manifest."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from src.cuts.cert_schema import (
    CERT_PAYLOAD_ALLOWED_FIELDS,
    CERT_PAYLOAD_CERT_KIND_BY_FAMILY,
    CERT_PAYLOAD_REQUIRED_FIELDS,
)
from src.cuts.typed_platform import SUPPORTED_OPERATIONS, build_production_registry
from src.tests.cuts.rule_cut_evolution.family_specs import (
    PRODUCTION_AUTHORITY_DEPENDENCIES_V1,
    SHADOW_FAMILY_SPECS_V1,
    SUPPORTED_LOWERING_OPERATIONS_V1,
    FamilySpecRegistry,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
REMOVED_PRODUCTION_MANIFESTS = (
    REPO_ROOT / "src/cuts/rule_semantics.py",
    REPO_ROOT / "src/cuts/family_specs.py",
    REPO_ROOT / "src/search/family_generation.py",
)
PRODUCTION_RUNTIME_FILES = (
    REPO_ROOT / "src/cuts/typed_platform.py",
    REPO_ROOT / "src/cuts/lifecycle.py",
    REPO_ROOT / "src/cuts/replay.py",
    REPO_ROOT / "src/search/benders_loop.py",
)
TEST_ONLY_STATIC_MODULES = (
    REPO_ROOT / "src/tests/cuts/rule_cut_evolution/rule_semantics.py",
    REPO_ROOT / "src/tests/cuts/rule_cut_evolution/family_specs.py",
    REPO_ROOT / "src/tests/cuts/rule_cut_evolution/family_generation.py",
)


def _imported_modules(path: Path) -> frozenset[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    return frozenset(imported)


def test_shadow_manifest_matches_hardcoded_production_capabilities_externally() -> None:
    production = build_production_registry()
    shadow = SHADOW_FAMILY_SPECS_V1
    assert tuple(production.capabilities) == tuple(shadow.trust_specs)
    for family, capability in production.capabilities.items():
        row = shadow.trust(family).capability
        assert (
            capability.name,
            capability.mode,
            capability.proof_schema_version,
            capability.validator_version,
            capability.compiler_version,
            capability.stage.value,
            capability.required_dependencies,
            capability.execution_path.value,
            capability.requires_ghost_bound,
        ) == (
            row.family,
            row.mode.value,
            row.proof_schema_version,
            row.validator_version,
            row.compiler_version,
            row.stage.value,
            row.required_dependencies,
            row.execution_path.value,
            row.requires_ghost_bound,
        )


def test_shadow_plugin_identities_match_hardcoded_registry_without_object_storage() -> None:
    production = build_production_registry()
    shadow_plugins = {
        family: row.typed_plugin.value
        for family, row in SHADOW_FAMILY_SPECS_V1.trust_specs.items()
        if row.typed_plugin.value is not None
    }
    assert frozenset(production.plugins) == frozenset(shadow_plugins)
    for family, plugin in production.plugins.items():
        identity = shadow_plugins[family]
        assert identity is not None
        assert (type(plugin).__module__, type(plugin).__qualname__) == (
            identity.identity.module,
            identity.identity.qualname,
        )


def test_shadow_lowering_is_an_exact_selection_from_existing_closed_operations() -> None:
    assert frozenset(SUPPORTED_OPERATIONS) == SUPPORTED_LOWERING_OPERATIONS_V1
    assert {
        family: row.lowering.value.operation
        for family, row in SHADOW_FAMILY_SPECS_V1.trust_specs.items()
        if row.lowering.value is not None
    } == {
        "region_capacity": "region_capacity_le",
        "shape_packing_hall": "shape_packing_hall_le",
        "power_hitting_set": "power_pose_exclusion",
    }
    assert SHADOW_FAMILY_SPECS_V1.trust("pattern_nogood").lowering.value is None


def test_all_live_rows_pin_proof_replay_dependencies_lifecycle_and_tests() -> None:
    for family, row in SHADOW_FAMILY_SPECS_V1.trust_specs.items():
        assert row.authority_dependency_closure == PRODUCTION_AUTHORITY_DEPENDENCIES_V1
        assert row.required_contract_ids
        if family == "power_grid_reach":
            assert row.proof_schema.value is None
            assert row.replay.value is None
            continue
        assert row.proof_schema.value is not None
        assert row.proof_schema.value.family == family
        assert row.replay.value is not None
        assert row.lifecycle_stage.value
        assert row.telemetry_profile.value


def test_shadow_proof_schemas_match_existing_closed_cert_schemas() -> None:
    assert frozenset(CERT_PAYLOAD_ALLOWED_FIELDS) == frozenset(
        family
        for family, row in SHADOW_FAMILY_SPECS_V1.trust_specs.items()
        if row.proof_schema.value is not None
    )
    for family, allowed_fields in CERT_PAYLOAD_ALLOWED_FIELDS.items():
        proof_schema = SHADOW_FAMILY_SPECS_V1.trust(family).proof_schema.value
        assert proof_schema is not None
        assert proof_schema.cert_kind == CERT_PAYLOAD_CERT_KIND_BY_FAMILY[family]
        assert proof_schema.allowed_fields == allowed_fields
        assert proof_schema.required_fields == CERT_PAYLOAD_REQUIRED_FIELDS[family]


def test_manifest_rejects_dependency_or_generation_order_drift() -> None:
    family = "region_capacity"
    base = SHADOW_FAMILY_SPECS_V1.trust(family)
    bad_capability = replace(base.capability, required_dependencies=frozenset({"candidate_placements"}))
    with pytest.raises(ValueError, match="authority dependency closure"):
        replace(base, capability=bad_capability)

    with pytest.raises(ValueError, match="generation order"):
        FamilySpecRegistry(
            schema_version=1,
            rule_semantics=SHADOW_FAMILY_SPECS_V1.rule_semantics,
            trust_specs=SHADOW_FAMILY_SPECS_V1.trust_specs,
            generation_specs=SHADOW_FAMILY_SPECS_V1.generation_specs,
            typed_generation_order=tuple(reversed(SHADOW_FAMILY_SPECS_V1.typed_generation_order)),
        )


def test_production_runtime_cannot_import_test_shadow_or_removed_manifest_modules() -> None:
    prohibited = {
        "src.cuts.rule_semantics",
        "src.cuts.family_specs",
        "src.search.family_generation",
    }
    for path in PRODUCTION_RUNTIME_FILES:
        imports = _imported_modules(path)
        assert imports.isdisjoint(prohibited), (path, imports & prohibited)
        assert all(not module.startswith("src.tests.") for module in imports), path


def test_static_shadow_modules_have_no_object_target_builder_or_dynamic_resolver() -> None:
    prohibited_function_names = {"build", "resolve", "target"}
    prohibited_imports = {"importlib", "pkgutil"}
    for path in TEST_ONLY_STATIC_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert _imported_modules(path).isdisjoint(prohibited_imports)
        assert {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }.isdisjoint(prohibited_function_names)
        annotated_names = {
            node.target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }
        assert annotated_names.isdisjoint({"target", "callable", "factory_object"})


def test_former_production_manifest_paths_are_removed() -> None:
    assert all(not path.exists() for path in REMOVED_PRODUCTION_MANIFESTS)
