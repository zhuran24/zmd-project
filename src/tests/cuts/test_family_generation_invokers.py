"""Static generation branch contract; there are intentionally no invokers."""

from __future__ import annotations

import ast
from pathlib import Path

from src.tests.cuts.rule_cut_evolution.family_specs import SHADOW_FAMILY_SPECS_V1
from src.tests.cuts.rule_cut_evolution.family_generation import (
    TYPED_GENERATION_BRANCHES_V1,
    TYPED_GENERATION_ORDER_V1,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _module_tree(module: str) -> ast.Module:
    path = REPO_ROOT / f"{module.replace('.', '/')}.py"
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _function_parameter_ids(tree: ast.Module, qualname: str) -> tuple[str, ...]:
    function_name = qualname.rsplit(".", maxsplit=1)[-1]
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    ]
    assert len(matches) == 1
    arguments = matches[0].args
    assert arguments.vararg is None
    assert arguments.kwarg is None
    return tuple(
        argument.arg
        for argument in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        )
    )


def _string_constant(tree: ast.Module, *names: str) -> str:
    values: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id in names
                    and isinstance(node.value.value, str)
                ):
                    values[target.id] = node.value.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id in names
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            values[node.target.id] = node.value.value
    assert len(values) == 1
    return next(iter(values.values()))


def test_typed_generation_order_and_generator_identities_are_static() -> None:
    assert TYPED_GENERATION_ORDER_V1 == (
        "region_capacity",
        "power_hitting_set",
        "shape_packing_hall",
        "pattern_nogood",
    )
    assert {
        family: (row.generator.module, row.generator.qualname)
        for family, row in TYPED_GENERATION_BRANCHES_V1.items()
    } == {
        "region_capacity": (
            "src.cuts.oracles.region_capacity_oracle",
            "generate_region_capacity_cuts",
        ),
        "power_hitting_set": (
            "src.cuts.oracles.power_cover_oracle",
            "generate_power_hitting_set_cuts",
        ),
        "shape_packing_hall": (
            "src.cuts.oracles.shape_packing_hall_oracle",
            "generate_shape_packing_hall_cuts",
        ),
        "pattern_nogood": (
            "src.cuts.oracles.pattern_nogood_oracle",
            "generate_pattern_nogood_cuts",
        ),
    }


def test_branch_gates_record_complete_orchestration_premises() -> None:
    assert {
        family: row.enablement_gate
        for family, row in TYPED_GENERATION_BRANCHES_V1.items()
    } == {
        "region_capacity": "enabled_family",
        "power_hitting_set": "solution_and_enabled_family_and_target_poses",
        "shape_packing_hall": "enabled_family_and_sot_region_demand_overrides",
        "pattern_nogood": "solution_and_enabled_family_and_full_assignment_literals",
    }
    assert all(
        row.orchestrator.qualname == "LBBDController._maybe_attach_framework_cuts"
        for row in TYPED_GENERATION_BRANCHES_V1.values()
    )


def test_all_live_generation_rows_match_existing_generator_signatures_and_wire_constants() -> None:
    for row in SHADOW_FAMILY_SPECS_V1.generation_specs.values():
        generator = row.generator.value
        if generator is None:
            assert row.surface.value == "retired"
            continue
        tree = _module_tree(generator.module)
        assert _function_parameter_ids(tree, generator.qualname) == row.generator_parameter_ids
        assert _string_constant(tree, "ORACLE_NAME", "_ORACLE_NAME") == row.oracle_name.value
        assert _string_constant(tree, "FAMILY_VERSION", "_FAMILY_VERSION") == row.family_version.value
        assert (
            _string_constant(tree, "VALIDATOR_VERSION", "_VALIDATOR_VERSION")
            == row.validator_version.value
        )
