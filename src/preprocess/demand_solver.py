"""Global Demand Solver（全局需求求解器）.

本模块把冻结业务目标展开成：
1. commodity_demands.json（物料需求）
2. machine_counts.json（机器数量）
3. port_budget.json（端口预算）
4. generic_io_requirements.json（通用 I/O 需求）

当前实现以 `PreprocessContext` 为 build-time 数据入口：
- recipe / target / commodity role / cycle group 不再硬编码在 Python 逻辑里；
- 默认 certified runtime 仍继续消费冻结的 `data/preprocessed/*` 工件；
- 本模块只负责再生这些工件，不改变 exact solver 的运行时真值边界。
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

import json
import math
from collections import defaultdict, deque
from fractions import Fraction
from typing import Any, Dict, Mapping

from src.interchange.preprocess_context import (
    PreprocessContext,
    build_producer_index,
    load_default_preprocess_context,
    solve_cycle_group_exact,
)

EPSILON = 1e-9
INTEGER_SNAP_TOLERANCE = 1e-9
ARTIFACT_DECIMAL_PLACES = 10


def normalize_artifact_number(value: Any) -> Any:
    """Normalize artifact-boundary numbers with a small near-integer tolerance."""

    if isinstance(value, Fraction):
        if value.denominator == 1:
            return int(value.numerator)
        value = float(value)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    if isinstance(value, int):
        return int(value)
    numeric = float(value)
    rounded_int = round(numeric)
    if abs(numeric - rounded_int) <= INTEGER_SNAP_TOLERANCE:
        return int(rounded_int)
    rounded = round(numeric, ARTIFACT_DECIMAL_PLACES)
    rounded_int = round(rounded)
    if abs(rounded - rounded_int) <= INTEGER_SNAP_TOLERANCE:
        return int(rounded_int)
    return float(rounded)


def normalize_json_numbers(value: Any) -> Any:
    """Recursively normalize numbers before JSON serialization."""

    if isinstance(value, Mapping):
        return {
            str(key): normalize_json_numbers(subvalue)
            for key, subvalue in value.items()
        }
    if isinstance(value, list):
        return [normalize_json_numbers(item) for item in value]
    if isinstance(value, tuple):
        return [normalize_json_numbers(item) for item in value]
    return normalize_artifact_number(value)


def ceil_machine_count(value: float | Fraction) -> int:
    """Ceil machine counts with the same tolerance contract as artifact output."""

    normalized = normalize_artifact_number(value)
    if isinstance(normalized, int):
        return int(normalized)
    return int(math.ceil(float(normalized) - INTEGER_SNAP_TOLERANCE))


def solve_demands(context: PreprocessContext | None = None) -> tuple[Dict[str, float], Dict[str, float]]:
    """Return realized commodity flows and fractional machine counts.

    The public API remains float-based for compatibility with the existing tests,
    render helpers, and preprocess scripts. Internally all propagation and cycle
    solving uses `Fraction` for exact arithmetic.
    """

    exact_flows, exact_machine_runs = solve_demands_exact(context=context)
    return (
        _fraction_mapping_to_float_dict(exact_flows),
        _fraction_mapping_to_float_dict(exact_machine_runs),
    )


def solve_demands_exact(
    context: PreprocessContext | None = None,
) -> tuple[dict[str, Fraction], dict[str, Fraction]]:
    resolved_context = context or load_default_preprocess_context()
    target_demands = {
        commodity_id: _target_rate_per_tick(resolved_context, commodity_id)
        for commodity_id in sorted(resolved_context.targets)
    }
    flows, machine_runs, cycle_external_demands = _backpropagate_non_cycle_demands(
        resolved_context,
        target_demands,
    )

    mutable_machine_runs: defaultdict[str, Fraction] = defaultdict(Fraction, machine_runs)
    for group_id in sorted(cycle_external_demands):
        cycle_recipe_runs = solve_cycle_group_exact(
            resolved_context,
            group_id,
            cycle_external_demands[group_id],
        )
        for recipe_id, run_rate in cycle_recipe_runs.items():
            mutable_machine_runs[recipe_id] += run_rate

    return (
        _sort_fraction_mapping(flows),
        _sort_fraction_mapping(mutable_machine_runs),
    )


def generate_ceil_machine_counts(machines_fractional: Mapping[str, float | Fraction]) -> Dict[str, int]:
    return {
        machine_type: ceil_machine_count(frac_count)
        for machine_type, frac_count in sorted(machines_fractional.items())
    }


def generate_port_budget(
    flows: Mapping[str, float | Fraction],
    context: PreprocessContext | None = None,
) -> Dict[str, Any]:
    """The 52-Port Miracle（52 口闭环）预算。"""

    resolved_context = context or load_default_preprocess_context()
    external_requirements = {
        commodity_id: _mapping_get_fraction(flows, commodity_id)
        for commodity_id, role in sorted(resolved_context.commodity_roles.items())
        if role.source_kind == "external_boundary" and _mapping_get_fraction(flows, commodity_id) > 0
    }

    source_req = normalize_artifact_number(external_requirements.get("source_ore", Fraction(0)))
    blue_iron_req = normalize_artifact_number(external_requirements.get("blue_iron_ore", Fraction(0)))
    total_req = normalize_artifact_number(sum(external_requirements.values(), Fraction(0)))

    return {
        "miracle_52_budget": {
            "source_ore_inputs_required": source_req,
            "blue_iron_ore_inputs_required": blue_iron_req,
            "total_boundary_and_core_ports_required": total_req,
        },
        "available_resources": {
            "max_boundary_ports_left_and_bottom": 46,
            "protocol_core_extra_outputs": 6,
            "total_available": 52,
        },
        "status": "FEASIBLE" if float(total_req) <= 52.0 + EPSILON else "INFEASIBLE_EXCEEDS_CAPACITY",
    }


def generate_generic_io_requirements(
    flows: Mapping[str, float | Fraction],
    port_budget: Mapping[str, Any],
    context: PreprocessContext | None = None,
) -> Dict[str, Any]:
    """Generate generic_io_requirements.json（生成通用 I/O 需求工件）."""

    resolved_context = context or load_default_preprocess_context()
    del port_budget  # retained in the signature for backward compatibility.

    required_generic_outputs = {
        commodity_id: int(ceil_machine_count(_mapping_get_fraction(flows, commodity_id)))
        for commodity_id, role in sorted(resolved_context.commodity_roles.items())
        if role.source_kind == "external_boundary" and _mapping_get_fraction(flows, commodity_id) > 0
    }

    required_generic_inputs = {
        commodity_id: 1
        for commodity_id, role in sorted(resolved_context.commodity_roles.items())
        if role.sink_kind == "generic_input" and _mapping_get_fraction(flows, commodity_id) > 0
    }

    return {
        "metadata": {
            "artifact_type": "generic_io_requirements",
            "generated_by": "src/preprocess/demand_solver.py",
            "unit": "discrete_port_slots",
            "notes": [
                "required_generic_outputs describes resource-source slots from boundary ports and protocol core.",
                "required_generic_inputs describes sink slots for final products at generic receiving facilities.",
            ],
        },
        "required_generic_outputs": required_generic_outputs,
        "required_generic_inputs": required_generic_inputs,
    }


def save_preprocessed_artifacts(
    output_dir: Path,
    flows: Mapping[str, float | Fraction],
    machine_counts: Mapping[str, int],
    port_budget: Mapping[str, Any],
    generic_io_requirements: Mapping[str, Any],
) -> None:
    """Write JSON artifacts（写出 JSON 工件）到 data/preprocessed。"""

    output_dir.mkdir(parents=True, exist_ok=True)

    artifacts = {
        "commodity_demands.json": flows,
        "machine_counts.json": machine_counts,
        "port_budget.json": port_budget,
        "generic_io_requirements.json": generic_io_requirements,
    }
    for filename, payload in artifacts.items():
        with (output_dir / filename).open("w", encoding="utf-8") as fh:
            json.dump(normalize_json_numbers(payload), fh, indent=2, ensure_ascii=False, allow_nan=False)
            fh.write("\n")


def main() -> None:
    print("🚀 [预处理] 启动 Global Demand Solver（全局需求求解器）...")

    context = load_default_preprocess_context()
    flows, machines_fractional = solve_demands(context=context)
    machine_counts = generate_ceil_machine_counts(machines_fractional)
    port_budget = generate_port_budget(flows, context=context)
    generic_io_requirements = generate_generic_io_requirements(flows, port_budget, context=context)

    output_dir = Path(__file__).resolve().parent.parent.parent / "data" / "preprocessed"
    save_preprocessed_artifacts(
        output_dir=output_dir,
        flows=flows,
        machine_counts=machine_counts,
        port_budget=port_budget,
        generic_io_requirements=generic_io_requirements,
    )

    total_machines = sum(machine_counts.values())
    miracle = port_budget["miracle_52_budget"]
    print(f"✅ [完成] machine_counts 总量 = {total_machines}")
    print(
        "✅ [完成] 52 口预算 = "
        f"source_ore={miracle['source_ore_inputs_required']}, "
        f"blue_iron_ore={miracle['blue_iron_ore_inputs_required']}, "
        f"total={miracle['total_boundary_and_core_ports_required']}"
    )
    print(f"💾 [保存] 工件已写入 {output_dir}")


def _target_rate_per_tick(context: PreprocessContext, commodity_id: str) -> Fraction:
    target = context.targets[commodity_id]
    if target.mode == "rate_per_tick":
        return target.value
    if target.mode != "equivalent_full_speed_lines":
        raise ValueError(f"unsupported production target mode: {target.mode!r}")
    recipe = context.recipes[target.final_recipe_id]
    if commodity_id not in recipe.outputs:
        raise ValueError(
            f"final recipe {target.final_recipe_id!r} does not produce target commodity {commodity_id!r}"
        )
    return target.value * recipe.output_rate(commodity_id)


def _backpropagate_non_cycle_demands(
    context: PreprocessContext,
    target_demands: Mapping[str, Fraction],
) -> tuple[dict[str, Fraction], dict[str, Fraction], dict[str, dict[str, Fraction]]]:
    flows: defaultdict[str, Fraction] = defaultdict(Fraction)
    machine_runs: defaultdict[str, Fraction] = defaultdict(Fraction)
    cycle_external_demands: defaultdict[str, defaultdict[str, Fraction]] = defaultdict(lambda: defaultdict(Fraction))
    producer_index = build_producer_index(context)

    pending = deque(sorted(target_demands.items(), key=lambda item: item[0]))
    while pending:
        commodity_id, demand_rate = pending.popleft()
        demand_rate = _to_fraction(demand_rate)
        if demand_rate <= 0:
            continue
        flows[commodity_id] += demand_rate

        role = context.commodity_role(commodity_id)
        if role.cycle_group is not None:
            cycle_external_demands[role.cycle_group][commodity_id] += demand_rate
            continue
        if role.source_kind == "external_boundary":
            continue

        producer_ids = producer_index.get(commodity_id, ())
        if not producer_ids:
            raise ValueError(f"commodity {commodity_id!r} has positive demand but no producer recipe")
        if len(producer_ids) != 1:
            raise ValueError(
                f"commodity {commodity_id!r} must have exactly one non-cycle producer, found {len(producer_ids)}"
            )
        recipe = context.recipes[producer_ids[0]]
        output_rate = recipe.output_rate(commodity_id)
        if output_rate <= 0:
            raise ValueError(
                f"recipe {recipe.recipe_id!r} produces non-positive rate for commodity {commodity_id!r}"
            )
        run_rate = demand_rate / output_rate
        machine_runs[recipe.recipe_id] += run_rate
        for input_commodity, amount in recipe.inputs.items():
            pending.append((input_commodity, run_rate * amount / Fraction(recipe.ticks_per_cycle)))

    return (
        _sort_fraction_mapping(flows),
        _sort_fraction_mapping(machine_runs),
        {
            group_id: _sort_fraction_mapping(group_demands)
            for group_id, group_demands in sorted(cycle_external_demands.items())
        },
    )


def _fraction_mapping_to_float_dict(values: Mapping[str, Fraction]) -> Dict[str, float]:
    return {
        key: float(value)
        for key, value in sorted(values.items())
    }


def _sort_fraction_mapping(values: Mapping[str, Fraction]) -> dict[str, Fraction]:
    return {
        key: _to_fraction(value)
        for key, value in sorted(values.items())
        if _to_fraction(value) > 0
    }


def _mapping_get_fraction(values: Mapping[str, float | Fraction], commodity_id: str) -> Fraction:
    raw = values.get(commodity_id, 0)
    return _to_fraction(raw)


def _to_fraction(value: Any) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise TypeError("boolean values are not valid Fraction inputs")
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, float):
        return Fraction(str(value))
    if isinstance(value, str):
        return Fraction(value)
    raise TypeError(f"cannot convert {type(value).__name__} to Fraction")


__all__ = [
    "ARTIFACT_DECIMAL_PLACES",
    "EPSILON",
    "INTEGER_SNAP_TOLERANCE",
    "ceil_machine_count",
    "generate_ceil_machine_counts",
    "generate_generic_io_requirements",
    "generate_port_budget",
    "normalize_artifact_number",
    "normalize_json_numbers",
    "save_preprocessed_artifacts",
    "solve_demands",
    "solve_demands_exact",
]


if __name__ == "__main__":
    main()
