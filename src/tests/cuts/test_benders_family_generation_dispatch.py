"""Observe the hard-coded Benders branches without making a runtime manifest."""

from __future__ import annotations

import ast
from pathlib import Path

from src.tests.cuts.rule_cut_evolution.family_generation import (
    TYPED_GENERATION_BRANCHES_V1,
    TYPED_GENERATION_ORDER_V1,
)


BENDERS_PATH = Path(__file__).resolve().parents[3] / "src/search/benders_loop.py"


def _generation_method() -> ast.FunctionDef:
    tree = ast.parse(BENDERS_PATH.read_text(encoding="utf-8"), filename=str(BENDERS_PATH))
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_maybe_attach_framework_cuts"
    ]
    assert len(matches) == 1
    return matches[0]


def test_hardcoded_generator_call_order_matches_shadow_rows() -> None:
    expected_name_to_family = {
        row.generator.qualname: family
        for family, row in TYPED_GENERATION_BRANCHES_V1.items()
    }
    observed = [
        (node.lineno, expected_name_to_family[node.func.id])
        for node in ast.walk(_generation_method())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in expected_name_to_family
    ]
    assert tuple(family for _line, family in sorted(observed)) == TYPED_GENERATION_ORDER_V1


def test_each_generation_branch_remains_an_explicit_enabled_family_guard() -> None:
    method = _generation_method()
    family_guards = {
        left.value
        for node in ast.walk(method)
        if isinstance(node, ast.Compare)
        and isinstance(node.ops[0], ast.In)
        for comparator in node.comparators
        if isinstance(comparator, ast.Attribute)
        and comparator.attr == "_enabled_cut_families"
        for left in (node.left,)
        if isinstance(left, ast.Constant) and isinstance(left.value, str)
    }
    assert family_guards >= frozenset(TYPED_GENERATION_ORDER_V1)


def test_benders_does_not_import_or_iterate_a_family_manifest() -> None:
    tree = ast.parse(BENDERS_PATH.read_text(encoding="utf-8"), filename=str(BENDERS_PATH))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "src.search.family_generation" not in imported
    assert "src.cuts.family_specs" not in imported
    assert all(not module.startswith("src.tests.") for module in imported)
