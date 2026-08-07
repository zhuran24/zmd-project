"""Regression coverage for physical ``box_sink`` binding semantics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.models.binding_subproblem import PortBindingModel
from src.models.routing_binding_context import build_routing_binding_context
from src.models.routing_subproblem import (
    RoutingPlacementCore,
    run_exact_routing_precheck,
)
from src.placement.placement_generator import (
    gen_protocol_core,
    gen_square_manufacturing,
)
from src.search.exact_campaign import ExactCampaign


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_GENERIC_INPUTS = {"valley_battery": 1, "qiaoyu_capsule": 1}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _box_sink_pose(anchor_x: int = 10, anchor_y: int = 10) -> dict[str, Any]:
    return {
        "pose_id": f"box_x{anchor_x:02d}_y{anchor_y:02d}_sink",
        "anchor": {"x": anchor_x, "y": anchor_y},
        "pose_params": {"orientation": 0, "port_mode": "box_sink"},
        "occupied_cells": [
            [anchor_x + dx, anchor_y + dy]
            for dx in range(3)
            for dy in range(3)
        ],
        "input_port_cells": [
            {"x": anchor_x + dx, "y": anchor_y - 1, "dir": "S"}
            for dx in range(3)
        ],
        "output_port_cells": [],
        "power_coverage_cells": None,
    }


def _filling_capsule_pose(anchor_x: int = 10, anchor_y: int = 10) -> dict[str, Any]:
    return {
        "pose_id": f"filling_capsule_probe_x{anchor_x:02d}_y{anchor_y:02d}",
        "anchor": {"x": anchor_x, "y": anchor_y},
        "pose_params": {"orientation": 0, "port_mode": "probe"},
        "occupied_cells": [
            [anchor_x + dx, anchor_y + dy]
            for dx in range(6)
            for dy in range(4)
        ],
        "input_port_cells": [
            {"x": anchor_x + dx, "y": anchor_y + 4, "dir": "N"}
            for dx in range(6)
        ],
        "output_port_cells": [
            {"x": anchor_x + dx, "y": anchor_y - 1, "dir": "S"}
            for dx in range(6)
        ],
        "power_coverage_cells": None,
    }


def _box_sink_binding_model(
    *,
    required_inputs: dict[str, int],
    instance_id: str = "pose_optional::protocol_storage_box::box_x10_y10_sink",
    pose: dict[str, Any] | None = None,
    routing_aware: bool = False,
) -> PortBindingModel:
    if pose is None:
        pose = _box_sink_pose()
    placement_solution = {
        instance_id: {
            "facility_type": "protocol_storage_box",
            "pose_idx": 0,
            "pose_id": pose["pose_id"],
            "anchor": dict(pose["anchor"]),
            "orientation": int(pose["pose_params"]["orientation"]),
            "port_mode": str(pose["pose_params"]["port_mode"]),
            "bound_type": "exact_pose_optional",
            "solve_mode": "certified_exact",
        }
    }
    facility_pools = {"protocol_storage_box": [pose]}
    routing_context = None
    if routing_aware:
        routing_context = build_routing_binding_context(
            placement_solution,
            facility_pools,
            grid_w=70,
            grid_h=70,
        )
    return PortBindingModel(
        placement_solution=placement_solution,
        facility_pools=facility_pools,
        instances=[],
        required_generic_outputs={},
        required_generic_inputs=required_inputs,
        project_root=PROJECT_ROOT,
        routing_context=routing_context,
    )


def test_box_sink_physical_slots_bind_positive_required_inputs() -> None:
    pose = _box_sink_pose()
    model = _box_sink_binding_model(
        required_inputs={"valley_battery": 1, "qiaoyu_capsule": 1}
    )
    model.build()

    assert model.solve(time_limit_seconds=5.0) == "FEASIBLE"
    assert len(model.generic_input_slots) == 3
    assert all(
        slot["slot_id"].endswith(f":in:{idx}")
        for idx, slot in enumerate(model.generic_input_slots)
    )
    assert all(slot.get("operation_type") == "box_sink" for slot in model.generic_input_slots)
    assert all("virtual" not in slot and "routing_free" not in slot for slot in model.generic_input_slots)
    assert [
        {key: slot[key] for key in ("x", "y", "dir")}
        for slot in model.generic_input_slots
    ] == pose["input_port_cells"]

    selection = model.extract_selection()["generic_inputs"]
    assert sorted(selection.values()) == ["__unused__", "qiaoyu_capsule", "valley_battery"]


def test_box_sink_bound_slots_emit_routing_sink_specs() -> None:
    model = _box_sink_binding_model(required_inputs=CANONICAL_GENERIC_INPUTS)
    model.build()

    assert model.solve(time_limit_seconds=5.0) == "FEASIBLE"
    port_specs = model.extract_port_specs()

    selection = model.extract_selection()["generic_inputs"]
    assert set(selection.values()) == {"__unused__", *CANONICAL_GENERIC_INPUTS}
    assert {spec["commodity"] for spec in port_specs} == set(CANONICAL_GENERIC_INPUTS)
    assert all(spec["type"] == "in" for spec in port_specs)
    slots_by_id = {slot["slot_id"]: slot for slot in model.generic_input_slots}
    for slot_id, commodity in selection.items():
        if commodity == "__unused__":
            continue
        slot = slots_by_id[slot_id]
        assert {
            "instance_id": slot["instance_id"],
            "x": slot["x"],
            "y": slot["y"],
            "dir": slot["dir"],
            "type": "in",
            "commodity": commodity,
            # U-01: the emitted sink spec names the receiving operation, which
            # is how routing tells a box apart from a wired warehouse port.
            "operation_type": "box_sink",
        } in port_specs


def test_box_sink_required_zero_is_rejected_by_canonical_role_guard() -> None:
    with pytest.raises(ValueError, match="non_positive=valley_battery"):
        _box_sink_binding_model(
            required_inputs={"valley_battery": 0, "qiaoyu_capsule": 1}
        )


def test_box_sink_routing_filter_removes_blocked_physical_sink_front() -> None:
    pose = _box_sink_pose()
    box_id = "pose_optional::protocol_storage_box::box_x10_y10_sink"
    blocker_pose = {
        "pose_id": "block_first_box_sink_front",
        "anchor": {"x": 10, "y": 9},
        "occupied_cells": [[10, 9]],
        "input_port_cells": [],
        "output_port_cells": [],
    }
    placement_solution = {
        box_id: {
            "facility_type": "protocol_storage_box",
            "pose_idx": 0,
            "pose_id": pose["pose_id"],
            "anchor": dict(pose["anchor"]),
            "orientation": 0,
            "port_mode": "box_sink",
        },
        "blocker_001": {
            "facility_type": "blocker",
            "pose_idx": 0,
            "pose_id": blocker_pose["pose_id"],
            "anchor": dict(blocker_pose["anchor"]),
            "orientation": 0,
            "port_mode": "none",
        },
    }
    facility_pools = {
        "protocol_storage_box": [pose],
        "blocker": [blocker_pose],
    }
    routing_context = build_routing_binding_context(
        placement_solution,
        facility_pools,
        grid_w=70,
        grid_h=70,
    )
    model = PortBindingModel(
        placement_solution=placement_solution,
        facility_pools=facility_pools,
        instances=[
            {
                "instance_id": "blocker_001",
                "facility_type": "blocker",
                "operation_type": "power_supply",
                "is_mandatory": True,
            }
        ],
        required_generic_outputs={},
        required_generic_inputs=CANONICAL_GENERIC_INPUTS,
        project_root=PROJECT_ROOT,
        routing_context=routing_context,
    )
    model.build()
    assert model.solve(time_limit_seconds=5.0) == "FEASIBLE"

    port_specs = model.extract_port_specs()
    assert model.routing_aware_filter_stats["generic_input_slots_pre_filter"] == 3
    assert model.routing_aware_filter_stats["generic_input_slots_post_filter"] == 2
    assert {(slot["x"], slot["y"]) for slot in model.generic_input_slots} == {
        (11, 9),
        (12, 9),
    }
    assert {(spec["x"], spec["y"]) for spec in port_specs} == {(11, 9), (12, 9)}
    assert {spec["commodity"] for spec in port_specs} == set(CANONICAL_GENERIC_INPUTS)


def test_edge_box_allows_inactive_oog_outputs_but_rejects_oog_active_inputs() -> None:
    edge_poses = [
        pose
        for pose in gen_square_manufacturing(
            3,
            allow_inactive_oog_port_sides=True,
        )
        if pose["anchor"] == {"x": 10, "y": 0}
    ]
    inactive_output_pose = next(
        pose for pose in edge_poses if pose["pose_params"]["port_mode"] == "TB"
    )
    assert all(port["y"] == -1 for port in inactive_output_pose["output_port_cells"])

    feasible_model = _box_sink_binding_model(
        required_inputs=CANONICAL_GENERIC_INPUTS,
        instance_id="pose_optional::protocol_storage_box::edge_inactive_outputs",
        pose=inactive_output_pose,
        routing_aware=True,
    )
    feasible_model.build()
    assert feasible_model.routing_aware_filter_stats["generic_input_slots_pre_filter"] == 3
    assert feasible_model.routing_aware_filter_stats["generic_input_slots_post_filter"] == 3
    assert feasible_model.solve(time_limit_seconds=5.0) == "FEASIBLE"
    assert all(spec["type"] == "in" for spec in feasible_model.extract_port_specs())

    active_input_pose = next(
        pose for pose in edge_poses if pose["pose_params"]["port_mode"] == "BT"
    )
    assert all(port["y"] == -1 for port in active_input_pose["input_port_cells"])

    infeasible_model = _box_sink_binding_model(
        required_inputs=CANONICAL_GENERIC_INPUTS,
        instance_id="pose_optional::protocol_storage_box::edge_active_inputs",
        pose=active_input_pose,
        routing_aware=True,
    )
    infeasible_model.build()
    assert infeasible_model.routing_aware_filter_stats["generic_input_slots_pre_filter"] == 3
    assert infeasible_model.routing_aware_filter_stats["generic_input_slots_post_filter"] == 0
    assert infeasible_model.solve(time_limit_seconds=5.0) == "INFEASIBLE"


def test_edge_core_uses_in_grid_generic_inputs_and_leaves_oog_slots_unused() -> None:
    pose = next(
        pose
        for pose in gen_protocol_core()
        if pose["anchor"] == {"x": 1, "y": 0}
        and pose["pose_params"]["orientation"] == 0
    )
    south_inputs = [port for port in pose["input_port_cells"] if port["dir"] == "S"]
    north_inputs = [port for port in pose["input_port_cells"] if port["dir"] == "N"]
    assert len(south_inputs) == len(north_inputs) == 7
    assert all(port["y"] == -1 for port in south_inputs)
    assert all(port["y"] == 9 for port in north_inputs)

    instance_id = "protocol_core_001"
    placement_solution = {
        instance_id: {
            "facility_type": "protocol_core",
            "pose_idx": 0,
            "pose_id": pose["pose_id"],
            "anchor": dict(pose["anchor"]),
            "orientation": int(pose["pose_params"]["orientation"]),
            "port_mode": str(pose["pose_params"]["port_mode"]),
        }
    }
    facility_pools = {"protocol_core": [pose]}
    routing_context = build_routing_binding_context(
        placement_solution,
        facility_pools,
        grid_w=70,
        grid_h=70,
    )
    model = PortBindingModel(
        placement_solution=placement_solution,
        facility_pools=facility_pools,
        instances=[
            {
                "instance_id": instance_id,
                "facility_type": "protocol_core",
                "operation_type": "protocol_core",
                "is_mandatory": True,
            }
        ],
        required_generic_outputs={},
        required_generic_inputs=CANONICAL_GENERIC_INPUTS,
        project_root=PROJECT_ROOT,
        routing_context=routing_context,
    )
    model.build()

    assert model.routing_aware_filter_stats["generic_input_slots_pre_filter"] == 14
    assert model.routing_aware_filter_stats["generic_input_slots_post_filter"] == 7
    assert model.solve(time_limit_seconds=5.0) == "FEASIBLE"
    selected = model.extract_selection()["generic_inputs"]
    assert sorted(selected.values()) == [
        "__unused__",
        "__unused__",
        "__unused__",
        "__unused__",
        "__unused__",
        "qiaoyu_capsule",
        "valley_battery",
    ]
    assert all(spec["y"] == 9 for spec in model.extract_port_specs())


def test_final_commodities_keep_producer_sources_and_box_sink_terminals() -> None:
    producer_pose = _filling_capsule_pose()
    sink_pose = _box_sink_pose(anchor_x=30, anchor_y=30)
    sink_instance_id = "pose_optional::protocol_storage_box::box_x30_y30_sink"
    model = PortBindingModel(
        placement_solution={
            "filling_capsule_001": {
                "facility_type": "manufacturing_6x4",
                "pose_idx": 0,
                "pose_id": producer_pose["pose_id"],
                "anchor": dict(producer_pose["anchor"]),
                "orientation": 0,
                "port_mode": "probe",
            },
            sink_instance_id: {
                "facility_type": "protocol_storage_box",
                "pose_idx": 0,
                "pose_id": sink_pose["pose_id"],
                "anchor": dict(sink_pose["anchor"]),
                "orientation": 0,
                "port_mode": "box_sink",
                "bound_type": "exact_pose_optional",
                "solve_mode": "certified_exact",
            },
        },
        facility_pools={
            "manufacturing_6x4": [producer_pose],
            "protocol_storage_box": [sink_pose],
        },
        instances=[
            {
                "instance_id": "filling_capsule_001",
                "facility_type": "manufacturing_6x4",
                "operation_type": "filling_capsule",
                "is_mandatory": True,
            }
        ],
        required_generic_outputs={},
        required_generic_inputs=CANONICAL_GENERIC_INPUTS,
        project_root=PROJECT_ROOT,
    )
    model.build()

    assert model.solve(time_limit_seconds=5.0) == "FEASIBLE"
    selection = model.extract_selection()
    port_specs = model.extract_port_specs()

    assert {"qiaoyu_capsule", "valley_battery"} <= set(
        selection["generic_inputs"].values()
    )
    assert {
        spec["commodity"]
        for spec in port_specs
        if spec["instance_id"] == sink_instance_id and spec["type"] == "in"
    } == set(CANONICAL_GENERIC_INPUTS)
    assert any(
        spec["instance_id"] == "filling_capsule_001"
        and spec["type"] == "out"
        and spec["commodity"] == "qiaoyu_capsule"
        for spec in port_specs
    )
    assert any(spec["commodity"] == "fine_buckwheat_powder" for spec in port_specs)
    assert any(spec["commodity"] == "steel_bottle" for spec in port_specs)

    occupied = {
        (int(x), int(y))
        for pose in (producer_pose, sink_pose)
        for x, y in pose["occupied_cells"]
    }
    placement_core = RoutingPlacementCore.from_occupied_cells(occupied)
    precheck = run_exact_routing_precheck(
        placement_core=placement_core,
        port_specs=port_specs,
    )

    assert precheck["status"] == "feasible"
    metadata = precheck["_analysis"]["commodity_front_metadata"]
    assert metadata["qiaoyu_capsule"]["source_front_cells"]
    assert metadata["qiaoyu_capsule"]["sink_front_cells"]
    assert metadata["valley_battery"]["sink_front_cells"]


def test_routing_aware_filter_rejects_blocked_final_output_fronts() -> None:
    producer_pose = _filling_capsule_pose()
    first_blocker_pose = _box_sink_pose(anchor_x=10, anchor_y=7)
    second_blocker_pose = _box_sink_pose(anchor_x=13, anchor_y=7)
    placement_solution = {
        "filling_capsule_001": {
            "facility_type": "manufacturing_6x4",
            "pose_idx": 0,
            "pose_id": producer_pose["pose_id"],
            "anchor": dict(producer_pose["anchor"]),
            "orientation": 0,
            "port_mode": "probe",
        },
        "pose_optional::protocol_storage_box::blocks_left_output_fronts": {
            "facility_type": "protocol_storage_box",
            "pose_idx": 0,
            "pose_id": first_blocker_pose["pose_id"],
            "anchor": dict(first_blocker_pose["anchor"]),
            "orientation": 0,
            "port_mode": "box_sink",
            "bound_type": "exact_pose_optional",
            "solve_mode": "certified_exact",
        },
        "pose_optional::protocol_storage_box::blocks_right_output_fronts": {
            "facility_type": "protocol_storage_box",
            "pose_idx": 1,
            "pose_id": second_blocker_pose["pose_id"],
            "anchor": dict(second_blocker_pose["anchor"]),
            "orientation": 0,
            "port_mode": "box_sink",
            "bound_type": "exact_pose_optional",
            "solve_mode": "certified_exact",
        },
    }
    facility_pools = {
        "manufacturing_6x4": [producer_pose],
        "protocol_storage_box": [first_blocker_pose, second_blocker_pose],
    }
    routing_context = build_routing_binding_context(
        placement_solution,
        facility_pools,
        grid_w=70,
        grid_h=70,
    )
    model = PortBindingModel(
        placement_solution=placement_solution,
        facility_pools=facility_pools,
        instances=[
            {
                "instance_id": "filling_capsule_001",
                "facility_type": "manufacturing_6x4",
                "operation_type": "filling_capsule",
                "is_mandatory": True,
            }
        ],
        required_generic_outputs={},
        required_generic_inputs=CANONICAL_GENERIC_INPUTS,
        project_root=PROJECT_ROOT,
        routing_context=routing_context,
    )
    model.build()

    assert model.extract_empty_binding_domain_instances() == [
        {
            "instance_id": "filling_capsule_001",
            "facility_type": "manufacturing_6x4",
            "operation_type": "filling_capsule",
            "pose_idx": 0,
            "pose_id": producer_pose["pose_id"],
        }
    ]
    assert "filling_capsule_001" not in model.binding_domains
    assert model.routing_aware_filter_stats["front_blocked_patterns_pruned"] == 540
    assert model.routing_aware_filter_stats["empty_filtered_owners"] == [
        "filling_capsule_001"
    ]
    certs = model.extract_routing_aware_certificates()
    assert len(certs) == 1
    assert certs[0]["owner_instance_id"] == "filling_capsule_001"
    assert set(certs[0]["blocker_instance_ids"]) == {
        "pose_optional::protocol_storage_box::blocks_left_output_fronts",
        "pose_optional::protocol_storage_box::blocks_right_output_fronts",
    }
    assert model.solve(time_limit_seconds=5.0) == "INFEASIBLE"


def test_campaign_resume_rejects_stale_candidate_placement_hash(tmp_path: Path) -> None:
    project_root = tmp_path / "resume_hash_project"
    data_dir = project_root / "data" / "preprocessed"
    rules_dir = project_root / "rules"

    _write_json(
        rules_dir / "canonical_rules.json",
        {
            "globals": {"grid": {"width": 2, "height": 2}},
            "facility_templates": {},
        },
    )
    _write_json(data_dir / "mandatory_exact_instances.json", [])
    _write_json(
        data_dir / "generic_io_requirements.json",
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )
    candidate_path = data_dir / "candidate_placements.json"
    _write_json(candidate_path, {"facility_pools": {"tiny": [{"pose_id": "old"}]}})

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    old_candidate_hash = campaign.artifact_hashes["candidate_placements"]
    campaign.save()

    _write_json(candidate_path, {"facility_pools": {"tiny": [{"pose_id": "new"}]}})
    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.compatible_hashes is False
    assert resumed.reset_reason == "artifact_hash_mismatch"
    assert resumed.artifact_hashes["candidate_placements"] != old_candidate_hash
