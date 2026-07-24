"""Milestone-B gates for manifest-driven Benders family generation."""

from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path

from src.cuts.family_specs import (
    PRODUCTION_FAMILY_MANIFEST_V1,
    StaticSymbolIdentity,
)
from src.search.benders_loop import LBBDController
from src.search.family_generation import (
    TYPED_FAMILY_GENERATION_INVOKERS_V1,
    TYPED_FAMILY_GENERATION_ORDER_V1,
)


_EXPECTED_GENERATORS = {
    "region_capacity": StaticSymbolIdentity(
        module="src.cuts.oracles.region_capacity_oracle",
        qualname="generate_region_capacity_cuts",
    ),
    "power_hitting_set": StaticSymbolIdentity(
        module="src.cuts.oracles.power_cover_oracle",
        qualname="generate_power_hitting_set_cuts",
    ),
    "shape_packing_hall": StaticSymbolIdentity(
        module="src.cuts.oracles.shape_packing_hall_oracle",
        qualname="generate_shape_packing_hall_cuts",
    ),
    "pattern_nogood": StaticSymbolIdentity(
        module="src.cuts.oracles.pattern_nogood_oracle",
        qualname="generate_pattern_nogood_cuts",
    ),
}


def test_static_invoker_map_matches_manifest_order_and_symbol_identities() -> None:
    manifest = PRODUCTION_FAMILY_MANIFEST_V1
    assert TYPED_FAMILY_GENERATION_ORDER_V1 == manifest.typed_generation_order
    assert tuple(TYPED_FAMILY_GENERATION_INVOKERS_V1) == (
        "region_capacity",
        "power_hitting_set",
        "shape_packing_hall",
        "pattern_nogood",
    )

    for family, invoker in TYPED_FAMILY_GENERATION_INVOKERS_V1.items():
        generation = manifest.generation(family)
        generator_ref = generation.generator.require(
            family=family,
            capability="generator",
        )
        assert type(generator_ref) is StaticSymbolIdentity
        assert generator_ref == _EXPECTED_GENERATORS[family]
        invoker_identity = generation.generation_invoker.require(
            family=family,
            capability="generation invoker",
        )
        assert type(invoker_identity) is StaticSymbolIdentity
        assert (invoker.__module__, invoker.__qualname__) == (
            invoker_identity.module,
            invoker_identity.qualname,
        )


def test_benders_generation_block_uses_manifest_outer_gate_and_static_map() -> None:
    source = textwrap.dedent(
        inspect.getsource(LBBDController._maybe_attach_framework_cuts)
    )
    tree = ast.parse(source)
    manifest_loops = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.For)
        and isinstance(node.target, ast.Name)
        and node.target.id == "family"
        and isinstance(node.iter, ast.Attribute)
        and node.iter.attr == "typed_generation_order"
        and isinstance(node.iter.value, ast.Name)
        and node.iter.value.id == "PRODUCTION_FAMILY_MANIFEST_V1"
    ]
    assert len(manifest_loops) == 1
    loop = manifest_loops[0]
    assert any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and any(isinstance(operator, ast.NotIn) for operator in node.test.ops)
        for node in loop.body
    )
    assert any(
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "TYPED_FAMILY_GENERATION_INVOKERS_V1"
        for node in ast.walk(loop)
    )

    forbidden_direct_calls = {
        "build_binding_empty_domain_adapter",
        "compute_sot_region_demand_overrides",
        "generate_pattern_nogood_cuts",
        "generate_power_hitting_set_cuts",
        "generate_region_capacity_cuts",
        "generate_shape_packing_hall_cuts",
        "lookup_sub_problem_oracle",
        "register_sub_problem_oracle",
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called_names.isdisjoint(forbidden_direct_calls)


def test_oracle_and_adapter_imports_live_inside_their_invokers() -> None:
    module_path = (
        Path(__file__).resolve().parents[3] / "src/search/family_generation.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    top_level_modules = {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(module.startswith("src.cuts.oracles.") for module in top_level_modules)
    assert "src.search.f5_binding_empty_domain_adapter" not in top_level_modules
    forbidden_injection_slots = {
        "build_binding_empty_domain_adapter",
        "compute_sot_region_demand_overrides",
        "generate_pattern_nogood_cuts",
        "generate_power_hitting_set_cuts",
        "generate_region_capacity_cuts",
        "generate_shape_packing_hall_cuts",
        "lookup_sub_problem_oracle",
        "register_sub_problem_oracle",
    }
    assigned_names = {
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            node.targets if isinstance(node, ast.Assign) else (node.target,)
        )
        if isinstance(target, ast.Name)
    }
    assert assigned_names.isdisjoint(forbidden_injection_slots)

    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    expected_local_modules = {
        "invoke_region_capacity_generation": {
            "src.cuts.oracles.region_capacity_oracle",
        },
        "invoke_power_hitting_set_generation": {
            "src.cuts.oracles.power_cover_oracle",
        },
        "invoke_shape_packing_hall_generation": {
            "src.cuts.oracles.shape_packing_hall_oracle",
        },
        "invoke_pattern_nogood_generation": {
            "src.cuts.oracles.pattern_nogood_oracle",
            "src.search.f5_binding_empty_domain_adapter",
        },
    }
    for function_name, expected_modules in expected_local_modules.items():
        local_modules = {
            node.module
            for node in ast.walk(functions[function_name])
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert expected_modules <= local_modules

    f5_source = ast.get_source_segment(
        module_path.read_text(encoding="utf-8"),
        functions["invoke_pattern_nogood_generation"],
    )
    assert f5_source is not None
    assert f5_source.index("if request.solution is None") < f5_source.index(
        "from src.cuts.oracles.pattern_nogood_oracle import"
    )
