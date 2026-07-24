"""External parity gate for lifecycle's closed projection switch."""

from __future__ import annotations

import ast
from pathlib import Path

from src.tests.cuts.rule_cut_evolution.family_specs import SHADOW_FAMILY_SPECS_V1


LIFECYCLE_PATH = Path(__file__).resolve().parents[3] / "src/cuts/lifecycle.py"


def _function(name: str) -> ast.FunctionDef:
    tree = ast.parse(
        LIFECYCLE_PATH.read_text(encoding="utf-8"),
        filename=str(LIFECYCLE_PATH),
    )
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert len(matches) == 1
    return matches[0]


def test_projection_families_match_lifecycle_closed_switch() -> None:
    expected = {
        family
        for family, row in SHADOW_FAMILY_SPECS_V1.trust_specs.items()
        if row.snapshot_projection.value is not None
    }
    method = _function("_live_master_domain_projection")
    compared_family_literals = {
        comparator.value
        for node in ast.walk(method)
        if isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == "family"
        for comparator in node.comparators
        if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str)
    }
    assert compared_family_literals == expected


def test_snapshot_projection_field_names_match_resolver_branches() -> None:
    expected_fields = {
        row.snapshot_projection.value.snapshot_field_id
        for row in SHADOW_FAMILY_SPECS_V1.trust_specs.values()
        if row.snapshot_projection.value is not None
    }
    resolver = _function("_resolve_live_master_domain_projection")
    observed_snapshot_attributes = {
        node.attr
        for node in ast.walk(resolver)
        if isinstance(node, ast.Attribute)
        and node.attr.endswith("master_domain_projection")
    }
    assert observed_snapshot_attributes == expected_fields


def test_lifecycle_does_not_import_a_runtime_family_manifest() -> None:
    tree = ast.parse(
        LIFECYCLE_PATH.read_text(encoding="utf-8"),
        filename=str(LIFECYCLE_PATH),
    )
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "src.cuts.family_specs" not in imported
    assert all(not module.startswith("src.tests.") for module in imported)
