from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path

import pytest


shelf = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.shelf_constructor"
)
solver = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.solve_shelf_power"
)


def test_fixed_shelf_network_matches_audited_campaign_topology() -> None:
    edges = shelf.fixed_network_edges()
    cells = shelf.network_router.network_cells(edges)

    assert edges == shelf.routing_aware_network_edges()
    assert len(edges) == 1169
    assert len(cells) == 1154
    assert shelf.FIXED_CORE_ANCHOR == (3, 53)
    assert shelf.FIXED_CHORD_LEVELS == (5, 10, 14, 20, 24, 29, 33, 39, 43, 48, 52, 58, 63)
    assert {(2, y) for y in range(52, 64)} <= cells
    assert {(12, y) for y in range(52, 64)} <= cells
    assert not ({(x, y) for x in range(3, 12) for y in range(53, 62)} & cells)


def test_replay_api_requires_explicit_result_and_has_no_public_inline_solver() -> None:
    parameter = inspect.signature(shelf.construct_shelf_candidate).parameters["result_path"]

    assert parameter.default is inspect.Parameter.empty
    assert not hasattr(solver, "solve_shelf_geometry")


def test_replay_rejects_partial_cgroup_telemetry_schema(tmp_path: Path) -> None:
    bundle = shelf.strict_contract.load_input_bundle()
    result = {
        "schema_version": shelf.SHELF_RESULT_SCHEMA_VERSION,
        "status": "OPTIMAL",
        "input_sha256": bundle.hashes,
        "manufacturing_slots": [],
        "pole_anchors": [],
        "pole_bay_anchors": [],
        "protected_rect": [1, 3, 6, 7],
        "network_edges": [],
        "stats": {},
        "route_validation": {"status": "WITNESS_BUILT"},
        "cgroup_telemetry": {"oom_attribution": "NO_CGROUP_OOM"},
        "failure": None,
    }
    path = tmp_path / "result.json"
    path.write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(shelf.ShelfConstructionError) as exc_info:
        shelf.construct_shelf_candidate(result_path=path)

    assert exc_info.value.code == "RESULT_SCHEMA"
    assert "cgroup_telemetry keys differ" in str(exc_info.value)


def _valid_cgroup_telemetry() -> dict[str, object]:
    unit = "zmd-witness-shelf-power-test.service"
    path = f"/user.slice/{unit}"
    limits = {
        "path": path,
        "memory.high": shelf.cgroup_telemetry.MEMORY_HIGH_BYTES,
        "memory.max": shelf.cgroup_telemetry.MEMORY_MAX_BYTES,
        "memory.swap.max": shelf.cgroup_telemetry.MEMORY_SWAP_MAX_BYTES,
    }
    effective = {
        "memory.high": shelf.cgroup_telemetry.MEMORY_HIGH_BYTES,
        "memory.max": shelf.cgroup_telemetry.MEMORY_MAX_BYTES,
        "memory.swap.max": shelf.cgroup_telemetry.MEMORY_SWAP_MAX_BYTES,
    }
    ancestor_limits = [
        {"path": "/user.slice", "memory.high": "max", "memory.max": "max", "memory.swap.max": "max"},
        {"path": "/", "memory.high": "max", "memory.max": "max", "memory.swap.max": "max"},
    ]
    contract = {"leaf": limits, "ancestors": ancestor_limits, "effective": effective}
    events_start = {"high": 1, "max": 2, "oom": 0, "oom_kill": 0, "oom_group_kill": 0}
    events_end = {**events_start, "high": 3}
    counters_start = {
        "memory.current": 100,
        "memory.peak": 200,
        "memory.swap.current": 0,
        "memory.swap.peak": 0,
        "pids.current": 2,
        "memory.events": events_start,
    }
    counters_end = {
        **counters_start,
        "memory.current": 150,
        "memory.peak": 250,
        "memory.events": events_end,
    }
    return {
        "schema_version": shelf.cgroup_telemetry.TELEMETRY_SCHEMA_VERSION,
        "expected_unit_name": unit,
        "cgroup_path": path,
        "contract_start": contract,
        "contract_end": contract,
        "counters_start": counters_start,
        "counters_end": counters_end,
        "memory.events.delta": {
            "high": 2,
            "max": 0,
            "oom": 0,
            "oom_kill": 0,
            "oom_group_kill": 0,
        },
        "oom_attribution": "NO_CGROUP_OOM",
    }


def test_replay_recomputes_cgroup_event_delta_and_peak_monotonicity() -> None:
    telemetry = _valid_cgroup_telemetry()
    shelf._validate_cgroup_telemetry(telemetry)

    telemetry["memory.events.delta"] = {
        **telemetry["memory.events.delta"],
        "high": 1,
    }
    with pytest.raises(shelf.ShelfConstructionError) as exc_info:
        shelf._validate_cgroup_telemetry(telemetry)

    assert exc_info.value.code == "RESULT_CGROUP_COUNTER"


def test_replay_rejects_tighter_or_incomplete_cgroup_ancestor_chain() -> None:
    telemetry = _valid_cgroup_telemetry()
    telemetry["contract_start"]["ancestors"][0]["memory.max"] = 1
    telemetry["contract_end"] = telemetry["contract_start"]

    with pytest.raises(shelf.ShelfConstructionError) as exc_info:
        shelf._validate_cgroup_telemetry(telemetry)

    assert exc_info.value.code == "RESULT_CGROUP_CONTRACT"

    telemetry = _valid_cgroup_telemetry()
    telemetry["contract_start"]["ancestors"] = telemetry["contract_start"]["ancestors"][:-1]
    telemetry["contract_end"] = telemetry["contract_start"]
    with pytest.raises(shelf.ShelfConstructionError) as exc_info:
        shelf._validate_cgroup_telemetry(telemetry)

    assert exc_info.value.code == "RESULT_CGROUP_CONTRACT"


def test_replay_derives_oom_attribution_from_event_delta() -> None:
    telemetry = _valid_cgroup_telemetry()
    telemetry["counters_end"]["memory.events"]["oom"] = 1
    telemetry["memory.events.delta"]["oom"] = 1

    with pytest.raises(shelf.ShelfConstructionError) as exc_info:
        shelf._validate_cgroup_telemetry(telemetry)

    assert exc_info.value.code == "RESULT_CGROUP_COUNTER"


def test_network_delta_must_remove_a_real_edge_and_preserve_scc() -> None:
    with pytest.raises(shelf.ShelfConstructionError) as exc_info:
        shelf.fixed_network_edges(removed_edges=[((10, 11), (11, 11))])

    assert exc_info.value.code == "REMOVE_UNKNOWN_NETWORK_EDGE"


def test_full_witness_pole_lower_bound_is_fail_closed_but_tiny_fixture_is_exempt() -> None:
    with pytest.raises(shelf.ShelfConstructionError) as exc_info:
        shelf.assert_full_witness_pole_lower_bound(required_count=266, pole_count=8)

    assert exc_info.value.code == "POLE_LOWER_BOUND_BUG"
    shelf.assert_full_witness_pole_lower_bound(required_count=266, pole_count=9)
    shelf.assert_full_witness_pole_lower_bound(required_count=3, pole_count=1)


def test_current_pool_contains_fixed_boundary_core_and_representative_shelf_poses() -> None:
    bundle, reconciliation = shelf.strict_contract.load_and_reconcile()
    pose_index = shelf._candidate_pose_index(bundle)

    assert reconciliation.mandatory_instances == 266
    assert ("protocol_core", "inputs_north_south", 3, 53) in pose_index
    assert ("boundary_storage_port", "left_boundary", 0, 0) in pose_index
    assert ("boundary_storage_port", "bottom_boundary", 1, 0) in pose_index
    assert ("manufacturing_3x3", "north_to_south", 3, 2) in pose_index
    assert ("manufacturing_5x5", "south_to_north", 3, 15) in pose_index
    assert ("manufacturing_6x4", "south_to_north", 3, 6) in pose_index


def test_boundary_slots_use_only_legal_69_0_pattern() -> None:
    bundle = shelf.strict_contract.load_input_bundle()
    slots = shelf._boundary_slots(bundle.strict_instance.value)

    assert len(slots) == 46
    assert sum(slot.mode == "left_boundary" for slot in slots) == 23
    assert sum(slot.mode == "bottom_boundary" for slot in slots) == 23
    assert {slot.anchor[1] for slot in slots if slot.mode == "left_boundary"} == set(range(0, 69, 3))
    assert {slot.anchor[0] for slot in slots if slot.mode == "bottom_boundary"} == set(range(1, 68, 3))


def test_operation_slots_are_assigned_inside_all_17_groups() -> None:
    bundle = shelf.strict_contract.load_input_bundle()
    instance = bundle.strict_instance.value
    slots = []
    for group_index, group in enumerate(instance["operation_groups"]):
        for slot_index in range(group["count"]):
            slots.append(
                shelf.GeometrySlot(
                    str(group["template"]),
                    "north_to_south",
                    (slot_index % 60, group_index),
                    str(group["id"]),
                )
            )

    assigned = shelf._assign_required_ids(instance, slots)
    manufacturing = [pair for pair in assigned if pair[1].template.startswith("manufacturing_")]
    assert len(manufacturing) == 219
    assert all(str(required["operation"]) == slot.operation for required, slot in manufacturing)
    assert len({slot.operation for _required, slot in manufacturing}) == 17


def test_off_network_but_free_manufacturing_front_is_rejected() -> None:
    instance = shelf.strict_contract.load_input_bundle().strict_instance.value
    placement = shelf.ShelfPlacement(
        instance_id="crusher_blue_iron_001",
        template="manufacturing_3x3",
        operation="crusher_blue_iron",
        mode="north_to_south",
        anchor=(3, 2),
        pose_idx=0,
        body_cells=frozenset({(3, 2)}),
        input_front_cells=((3, 5),),
        output_front_cells=((3, 1),),
    )

    with pytest.raises(shelf.ShelfConstructionError) as exc_info:
        shelf._validate_active_front_network(instance, [placement], {(3, 5)})

    assert exc_info.value.code == "ACTIVE_FRONT_NETWORK"
    assert "out 0/1" in str(exc_info.value)


def test_core_north_only_inputs_are_rejected_even_when_outputs_are_on_network() -> None:
    instance = shelf.strict_contract.load_input_bundle().strict_instance.value
    mode = next(
        mode
        for mode in instance["facility_templates"]["protocol_core"]["modes"]
        if mode["id"] == "inputs_north_south"
    )
    pose = shelf.geometry.strict_mode_geometry(mode, shelf.FIXED_CORE_ANCHOR)
    placement = shelf.ShelfPlacement(
        instance_id="protocol_core_001",
        template="protocol_core",
        operation="generic_io",
        mode="inputs_north_south",
        anchor=shelf.FIXED_CORE_ANCHOR,
        pose_idx=0,
        body_cells=pose.body_cells,
        input_front_cells=pose.input_front_cells,
        output_front_cells=pose.output_front_cells,
    )
    # The first seven inputs are N in the strict mode.  Supplying two of them
    # must not satisfy the campaign's two final-input terminals on S.
    network_cells = set(pose.output_front_cells) | set(pose.input_front_cells[:2])

    with pytest.raises(shelf.ShelfConstructionError) as exc_info:
        shelf._validate_active_front_network(instance, [placement], network_cells)

    assert exc_info.value.code == "ACTIVE_FRONT_NETWORK"
    assert "south inputs 0/2" in str(exc_info.value)
