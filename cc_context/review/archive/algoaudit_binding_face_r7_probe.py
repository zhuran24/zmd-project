#!/usr/bin/env python3
"""Round-7 binding audit probe.

This is an evidence probe, not production code.  It checks the current canonical
snapshot, exercises the current binding decision families, and constructs one
artificial owner-gated extension scenario to classify the future overlap boundary.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from src.models.binding_subproblem import PortBindingModel
from src.models.port_binding import enumerate_pose_level_port_bindings, supports_exact_pose_level_binding
from src.models.routing_binding_context import RoutingBindingContext
from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES

ROOT = Path(__file__).resolve().parents[2]


def _load_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def check_current_role_sets() -> dict[str, object]:
    canonical = _load_json("rules/canonical_rules.json")
    generic_io = _load_json("data/preprocessed/generic_io_requirements.json")
    metadata = canonical["commodity_metadata"]
    required_outputs = {
        str(k) for k, v in generic_io["required_generic_outputs"].items() if int(v) > 0
    }
    required_inputs = {
        str(k) for k, v in generic_io["required_generic_inputs"].items() if int(v) > 0
    }
    external_and_generic = sorted(
        commodity
        for commodity, meta in metadata.items()
        if meta.get("source_kind") == "external_boundary" and meta.get("sink_kind") == "generic_input"
    )
    assert not (required_outputs & required_inputs), required_outputs & required_inputs
    assert not external_and_generic, external_and_generic
    return {
        "required_generic_outputs": sorted(required_outputs),
        "required_generic_inputs": sorted(required_inputs),
        "output_input_intersection": sorted(required_outputs & required_inputs),
        "external_boundary_and_generic_input": external_and_generic,
    }


def check_fixed_domains() -> list[dict[str, object]]:
    facility_pools = _load_json("data/preprocessed/candidate_placements.json")["facility_pools"]
    rows: list[dict[str, object]] = []
    for operation_type, profile in sorted(OPERATION_PORT_PROFILES.items()):
        if not supports_exact_pose_level_binding(operation_type):
            continue
        pose = facility_pools[profile.facility_type][0]
        domains = enumerate_pose_level_port_bindings(operation_type, pose)
        expected_inputs = Counter({k: v for k, v in profile.input_slots.items() if int(v) > 0})
        expected_outputs = Counter({k: v for k, v in profile.output_slots.items() if int(v) > 0})
        for domain in domains:
            actual_inputs = Counter(port["commodity"] for port in domain["input_ports"])
            actual_outputs = Counter(port["commodity"] for port in domain["output_ports"])
            assert actual_inputs == expected_inputs, (operation_type, actual_inputs, expected_inputs)
            assert actual_outputs == expected_outputs, (operation_type, actual_outputs, expected_outputs)
            assert all(port["type"] == "input" for port in domain["input_ports"])
            assert all(port["type"] == "output" for port in domain["output_ports"])
        rows.append(
            {
                "operation_type": operation_type,
                "facility_type": profile.facility_type,
                "domain_count": len(domains),
                "input_slots": dict(expected_inputs),
                "output_slots": dict(expected_outputs),
            }
        )
    return rows


def check_selection_coverage_and_nogood() -> dict[str, object]:
    facility_pools = _load_json("data/preprocessed/candidate_placements.json")["facility_pools"]
    instances = [
        {
            "instance_id": "packaging_battery_001",
            "facility_type": "manufacturing_6x4",
            "operation_type": "packaging_battery",
            "is_mandatory": True,
        },
        {
            "instance_id": "boundary_port_001",
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "is_mandatory": True,
        },
        {
            "instance_id": "protocol_box_001",
            "facility_type": "protocol_storage_box",
            "operation_type": "wireless_sink",
            "is_mandatory": False,
        },
    ]
    placement_solution = {
        "packaging_battery_001": {
            "pose_idx": 0,
            "pose_id": facility_pools["manufacturing_6x4"][0]["pose_id"],
            "anchor": facility_pools["manufacturing_6x4"][0]["anchor"],
            "facility_type": "manufacturing_6x4",
        },
        "boundary_port_001": {
            "pose_idx": 0,
            "pose_id": facility_pools["boundary_storage_port"][0]["pose_id"],
            "anchor": facility_pools["boundary_storage_port"][0]["anchor"],
            "facility_type": "boundary_storage_port",
        },
        "protocol_box_001": {
            "pose_idx": 0,
            "pose_id": facility_pools["protocol_storage_box"][0]["pose_id"],
            "anchor": facility_pools["protocol_storage_box"][0]["anchor"],
            "facility_type": "protocol_storage_box",
        },
    }
    model = PortBindingModel(
        placement_solution,
        facility_pools,
        instances,
        required_generic_outputs={"source_ore": 1, "blue_iron_ore": 0},
        required_generic_inputs={"valley_battery": 1, "qiaoyu_capsule": 0},
        wireless_sink_generic_input_slots=3,
    )
    model.build()
    assert model.solve(time_limit_seconds=5.0) == "FEASIBLE"
    first = model.extract_selection()

    assert set(first["binding_choice"]) == set(model.binding_domains)
    assert set(first["generic_inputs"]) == {slot["slot_id"] for slot in model.generic_input_slots}
    assert set(first["generic_outputs"]) == {slot["slot_id"] for slot in model.generic_output_slots}
    assert set(model.binding_vars) <= set(first["binding_choice"])
    assert Counter(first["generic_inputs"].values())["valley_battery"] == 1
    assert Counter(first["generic_outputs"].values())["source_ore"] == 1
    assert all("x" not in slot and "y" not in slot and "dir" not in slot for slot in model.generic_input_slots)
    assert all(slot.get("routing_free") is True and slot.get("virtual") is True for slot in model.generic_input_slots)
    assert not any(spec.get("instance_id") == "protocol_box_001" for spec in model.extract_port_specs())
    assert not any(spec.get("commodity") == "valley_battery" and spec.get("type") == "out" for spec in model.extract_port_specs())

    model.add_nogood_cut(first)
    retry_status = model.solve(time_limit_seconds=5.0)
    assert retry_status in {"FEASIBLE", "INFEASIBLE", "TIMEOUT"}
    second_differs = None
    if retry_status == "FEASIBLE":
        second_differs = model.extract_selection() != first
        assert second_differs
    return {
        "binding_domain_instances": sorted(model.binding_domains),
        "binding_var_instances": sorted(model.binding_vars),
        "generic_input_slots": len(model.generic_input_slots),
        "generic_output_slots": len(model.generic_output_slots),
        "port_specs_after_routing_free_filter": len(model.extract_port_specs()) if retry_status != "FEASIBLE" else "re-solved-after-nogood",
        "nogood_retry_status": retry_status,
        "nogood_second_selection_differs": second_differs,
    }


def check_artificial_overlap_boundary() -> dict[str, object]:
    core_pose = {
        "pose_id": "core_single_output_probe",
        "anchor": {"x": 10, "y": 10},
        "occupied_cells": [],
        "input_port_cells": [],
        "output_port_cells": [{"x": 10, "y": 10, "dir": "E"}],
    }
    box_pose = {
        "pose_id": "wireless_box_probe",
        "anchor": {"x": 30, "y": 30},
        "occupied_cells": [],
        "input_port_cells": [],
        "output_port_cells": [],
    }
    facility_pools = {
        "protocol_core": [core_pose],
        "protocol_storage_box": [box_pose],
    }
    instances = [
        {
            "instance_id": "core_001",
            "facility_type": "protocol_core",
            "operation_type": "protocol_core",
            "is_mandatory": True,
        },
        {
            "instance_id": "sink_001",
            "facility_type": "protocol_storage_box",
            "operation_type": "wireless_sink",
            "is_mandatory": False,
        },
    ]
    placement_solution = {
        "core_001": {
            "pose_idx": 0,
            "pose_id": core_pose["pose_id"],
            "anchor": dict(core_pose["anchor"]),
            "facility_type": "protocol_core",
        },
        "sink_001": {
            "pose_idx": 0,
            "pose_id": box_pose["pose_id"],
            "anchor": dict(box_pose["anchor"]),
            "facility_type": "protocol_storage_box",
        },
    }
    model = PortBindingModel(
        placement_solution,
        facility_pools,
        instances,
        required_generic_outputs={"dual_role_probe": 1},
        required_generic_inputs={"dual_role_probe": 1},
        wireless_sink_generic_input_slots=1,
    )
    model.build()
    assert model.solve(time_limit_seconds=5.0) == "FEASIBLE"
    selection = model.extract_selection()
    assert selection["generic_outputs"] == {"core_001:out:0": "dual_role_probe"}
    assert selection["generic_inputs"] == {"sink_001:in:0": "dual_role_probe"}
    assert model.extract_port_specs() == []

    blocked_context = RoutingBindingContext(
        grid_width=70,
        grid_height=70,
        occupied_cells=frozenset({(11, 10)}),
        component_by_cell={},
        cells_by_component={},
        occupied_owner_by_cell={(11, 10): "blocker_001"},
    )
    blocked_model = PortBindingModel(
        placement_solution,
        facility_pools,
        instances,
        required_generic_outputs={"dual_role_probe": 1},
        required_generic_inputs={"dual_role_probe": 1},
        wireless_sink_generic_input_slots=1,
        routing_context=blocked_context,
    )
    blocked_model.build()
    blocked_status = blocked_model.solve(time_limit_seconds=5.0)
    assert blocked_status == "INFEASIBLE"
    return {
        "no_routing_context_selection": selection,
        "no_routing_context_port_specs": model.extract_port_specs(),
        "blocked_front_status": blocked_status,
        "blocked_generic_output_slots_after_rab": len(blocked_model.generic_output_slots),
        "classification": "future-overlap owner-gate hazard, not current snapshot bug",
    }


def main() -> None:
    result = {
        "current_role_sets": check_current_role_sets(),
        "fixed_domain_count": len(check_fixed_domains()),
        "fixed_domain_max_count": max(row["domain_count"] for row in check_fixed_domains()),
        "selection_coverage": check_selection_coverage_and_nogood(),
        "artificial_overlap_boundary": check_artificial_overlap_boundary(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
