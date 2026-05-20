from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.placement.placement_generator import generate_all_pools, load_templates
from src.preprocess.demand_solver import (
    generate_ceil_machine_counts,
    generate_generic_io_requirements,
    normalize_json_numbers,
    generate_port_budget,
    save_preprocessed_artifacts,
    solve_demands,
)
from src.preprocess.instance_builder import (
    EXPLORATORY_OPTIONAL_CAPS,
    TEMPLATE_MAPPING,
    build_boundary_ports,
    build_core_instance,
    build_exploratory_optional_instances,
    build_manufacturing_instances,
    save_json,
)
from src.preprocess.operation_profiles import aggregate_port_slots, count_operations


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _canonicalize_jsonish(value: Any) -> Any:
    value = normalize_json_numbers(value)
    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize_jsonish(val)
            for key, val in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [_canonicalize_jsonish(item) for item in value]
    return value


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_candidate_placements(path: Path, facility_pools: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"facility_pools": facility_pools}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def test_preprocess_chain_regenerates_frozen_artifacts_from_source_code(tmp_path: Path) -> None:
    project_root = _project_root()
    golden_dir = project_root / "data" / "preprocessed"
    regen_dir = tmp_path / "data" / "preprocessed"

    flows, fractional_counts = solve_demands()
    machine_counts = generate_ceil_machine_counts(fractional_counts)
    port_budget = generate_port_budget(flows)
    generic_io_requirements = generate_generic_io_requirements(flows, port_budget)
    save_preprocessed_artifacts(
        output_dir=regen_dir,
        flows=flows,
        machine_counts=machine_counts,
        port_budget=port_budget,
        generic_io_requirements=generic_io_requirements,
    )

    mandatory_exact_instances = (
        build_manufacturing_instances(machine_counts)
        + build_core_instance()
        + build_boundary_ports(46)
    )
    exploratory_optional_instances = build_exploratory_optional_instances()
    all_facility_instances = mandatory_exact_instances + exploratory_optional_instances

    save_json(regen_dir / "mandatory_exact_instances.json", mandatory_exact_instances)
    save_json(regen_dir / "exploratory_optional_caps.json", EXPLORATORY_OPTIONAL_CAPS)
    save_json(regen_dir / "all_facility_instances.json", all_facility_instances)
    _write_candidate_placements(
        regen_dir / "candidate_placements.json",
        generate_all_pools(load_templates()),
    )

    expected_files = [
        "commodity_demands.json",
        "machine_counts.json",
        "port_budget.json",
        "generic_io_requirements.json",
        "mandatory_exact_instances.json",
        "exploratory_optional_caps.json",
        "all_facility_instances.json",
        "candidate_placements.json",
    ]
    for filename in expected_files:
        assert _canonicalize_jsonish(_load_json(regen_dir / filename)) == _canonicalize_jsonish(
            _load_json(golden_dir / filename)
        ), f"semantic drift detected in {filename}"


def test_regenerated_instance_distribution_matches_machine_counts() -> None:
    flows, fractional_counts = solve_demands()
    del flows
    machine_counts = generate_ceil_machine_counts(fractional_counts)
    mandatory_exact_instances = (
        build_manufacturing_instances(machine_counts)
        + build_core_instance()
        + build_boundary_ports(46)
    )

    manufacturing_instances = [
        inst
        for inst in mandatory_exact_instances
        if str(inst.get("operation_type")) in machine_counts
    ]
    operation_counts = {}
    for inst in manufacturing_instances:
        operation_type = str(inst["operation_type"])
        operation_counts[operation_type] = operation_counts.get(operation_type, 0) + 1
        assert inst["facility_type"] == TEMPLATE_MAPPING[operation_type]

    assert operation_counts == machine_counts
    assert len(mandatory_exact_instances) == 266
    assert len(manufacturing_instances) == 219


def test_regenerated_preprocess_invariants_match_current_frozen_contract() -> None:
    flows, fractional_counts = solve_demands()
    machine_counts = generate_ceil_machine_counts(fractional_counts)
    port_budget = generate_port_budget(flows)
    generic_io_requirements = generate_generic_io_requirements(flows, port_budget)
    mandatory_exact_instances = (
        build_manufacturing_instances(machine_counts)
        + build_core_instance()
        + build_boundary_ports(46)
    )
    all_facility_instances = mandatory_exact_instances + build_exploratory_optional_instances()
    slot_summary = aggregate_port_slots(count_operations(all_facility_instances, mandatory_only=True))

    assert sum(machine_counts.values()) == 219
    assert len(mandatory_exact_instances) == 266
    assert len(all_facility_instances) == 326
    assert slot_summary["generic_output_slots"] == 52
    assert generic_io_requirements["required_generic_outputs"] == {"blue_iron_ore": 34, "source_ore": 18}
    assert generic_io_requirements["required_generic_inputs"] == {"qiaoyu_capsule": 1, "valley_battery": 1}


def test_frozen_preprocess_artifacts_are_cleanly_serialized_without_binary_noise() -> None:
    project_root = _project_root()
    preprocessed_dir = project_root / "data" / "preprocessed"

    port_budget_text = (preprocessed_dir / "port_budget.json").read_text(encoding="utf-8")
    commodity_text = (preprocessed_dir / "commodity_demands.json").read_text(encoding="utf-8")
    port_budget = _load_json(preprocessed_dir / "port_budget.json")
    commodity_demands = _load_json(preprocessed_dir / "commodity_demands.json")

    assert "18.000000000000004" not in port_budget_text
    assert "18.000000000000004" not in commodity_text
    assert port_budget["miracle_52_budget"]["source_ore_inputs_required"] == 18
    assert port_budget["miracle_52_budget"]["blue_iron_ore_inputs_required"] == 34
    assert port_budget["miracle_52_budget"]["total_boundary_and_core_ports_required"] == 52
    assert commodity_demands["source_ore"] == 18
    assert commodity_demands["blue_iron_ore"] == 34

