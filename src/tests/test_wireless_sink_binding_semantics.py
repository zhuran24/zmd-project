"""Regression coverage for omni_wireless protocol storage binding semantics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models.binding_subproblem import PortBindingModel
from src.models.flow_subproblem import FlowSubproblem, build_flow_network
from src.models.routing_subproblem import (
    RoutingPlacementCore,
    RoutingSubproblem,
    run_exact_routing_precheck,
)
from src.search.exact_campaign import ExactCampaign


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _wireless_box_pose(anchor_x: int = 10, anchor_y: int = 10) -> dict[str, Any]:
    return {
        "pose_id": f"box_x{anchor_x:02d}_y{anchor_y:02d}_omni",
        "anchor": {"x": anchor_x, "y": anchor_y},
        "pose_params": {"orientation": 0, "port_mode": "omni"},
        "occupied_cells": [
            [anchor_x + dx, anchor_y + dy]
            for dx in range(3)
            for dy in range(3)
        ],
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": None,
    }


def _wireless_binding_model(
    *,
    required_inputs: dict[str, int],
    instance_id: str = "pose_optional::protocol_storage_box::box_x10_y10_omni",
) -> PortBindingModel:
    pose = _wireless_box_pose()
    return PortBindingModel(
        placement_solution={
            instance_id: {
                "facility_type": "protocol_storage_box",
                "pose_idx": 0,
                "pose_id": pose["pose_id"],
                "anchor": dict(pose["anchor"]),
                "orientation": 0,
                "port_mode": "omni",
                "bound_type": "exact_pose_optional",
                "solve_mode": "certified_exact",
            }
        },
        facility_pools={"protocol_storage_box": [pose]},
        instances=[],
        required_generic_outputs={},
        required_generic_inputs=required_inputs,
        project_root=PROJECT_ROOT,
    )


def test_wireless_sink_virtual_slots_bind_positive_required_inputs() -> None:
    model = _wireless_binding_model(
        required_inputs={"valley_battery": 1, "qiaoyu_capsule": 1}
    )
    model.build()

    assert model.solve(time_limit_seconds=5.0) == "FEASIBLE"
    assert len(model.generic_input_slots) == 3
    assert all(
        slot["slot_id"].endswith(f":in:{idx}")
        for idx, slot in enumerate(model.generic_input_slots)
    )
    assert all(slot.get("operation_type") == "wireless_sink" for slot in model.generic_input_slots)
    assert all(slot.get("virtual") is True for slot in model.generic_input_slots)
    assert all(slot.get("routing_free") is True for slot in model.generic_input_slots)
    assert all("x" not in slot and "y" not in slot and "dir" not in slot for slot in model.generic_input_slots)

    selection = model.extract_selection()["generic_inputs"]
    assert sorted(selection.values()) == ["__unused__", "qiaoyu_capsule", "valley_battery"]


def test_wireless_sink_virtual_slots_do_not_emit_routing_port_specs() -> None:
    model = _wireless_binding_model(required_inputs={"valley_battery": 1})
    model.build()

    assert model.solve(time_limit_seconds=5.0) == "FEASIBLE"
    port_specs = model.extract_port_specs()

    assert port_specs == []
    assert model.extract_selection()["generic_inputs"]
    assert all(spec.get("commodity") != "valley_battery" for spec in port_specs)


def test_wireless_sink_required_zero_uses_unused_sentinel() -> None:
    model = _wireless_binding_model(required_inputs={"valley_battery": 0})
    model.build()

    assert model.solve(time_limit_seconds=5.0) == "FEASIBLE"
    selection = model.extract_selection()["generic_inputs"]

    assert len(selection) == 3
    assert set(selection.values()) == {"__unused__"}
    assert model.extract_port_specs() == []


def test_wireless_sink_routing_has_no_sink_front_and_needs_no_belt_to_box() -> None:
    pose = _wireless_box_pose()
    model = _wireless_binding_model(required_inputs={"demo_wireless_item": 1})
    model.build()
    assert model.solve(time_limit_seconds=5.0) == "FEASIBLE"

    port_specs = model.extract_port_specs()
    occupied = {(int(x), int(y)) for x, y in pose["occupied_cells"]}
    owners = {cell: "protocol_storage_box" for cell in occupied}
    placement_core = RoutingPlacementCore.from_occupied_cells(
        occupied,
        occupied_owner_by_cell=owners,
    )

    precheck = run_exact_routing_precheck(
        placement_core=placement_core,
        port_specs=port_specs,
    )
    assert precheck["status"] == "feasible"
    assert precheck["blocked_ports"] == []

    routing = RoutingSubproblem.from_placement_core(
        placement_core,
        port_specs,
        commodities=[],
        domain_analysis=precheck["_analysis"],
    )
    routing.build(time_limit=5.0)
    assert routing.solve(time_limit=5.0) == "FEASIBLE"
    assert routing.build_stats["port_adherence"] == {
        "exact_links": 0,
        "blocked_ports": 0,
        "ports": 0,
    }

    flow_network = build_flow_network(
        occupied_cells=occupied,
        port_dict={},
        commodity_demands={},
    )
    flow = FlowSubproblem(
        flow_network,
        commodity_demands={},
        solve_mode="certified_exact",
    )
    assert flow.build_and_solve(time_limit_ms=1000) == "FEASIBLE"
    assert not any("demo_wireless_item" in node for node in flow_network.nodes)


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
