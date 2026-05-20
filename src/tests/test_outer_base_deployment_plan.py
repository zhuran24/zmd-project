"""Tests for adapter-side outer deployment planning and validator probing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.adapters.base_planner.outer_deployment_plan import build_outer_base_deployment_plan
from src.adapters.industrial_planner.outer_export_probe import probe_outer_deployment_plan

_FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "examples" / "industrial_planner"


def _load_full_demand_blueprint() -> dict[str, object]:
    return json.loads((_FIXTURE_DIR / "full_demand_recipe_capacity_canonical_blueprint.json").read_text(encoding="utf-8"))


def test_wuling_outer_plan_builds_centered_truthful_boundary_assignments() -> None:
    blueprint = _load_full_demand_blueprint()
    plan = build_outer_base_deployment_plan(
        blueprint_payload=blueprint,
        base_id="wuling_protocol_core",
    )

    assert plan.plan_version == "0.2.0"
    assert plan.planning_status == "planned_outer_deployment"
    assert plan.base_id == "wuling_protocol_core"
    assert plan.base_lot_size == 80
    assert plan.inner_island_origin.x == 5
    assert plan.inner_island_origin.y == 5
    assert plan.moat_thickness_by_edge == {
        "top": 5,
        "right": 5,
        "bottom": 5,
        "left": 5,
    }
    assert plan.boundary_demand_summary.required_boundary_output_slots == 52
    assert plan.boundary_demand_summary.required_boundary_input_slots == 2
    assert len(plan.boundary_assignments) == 54
    assert len(plan.connector_reservations) == 52
    assert len(plan.witness_reservations) == 56
    assert len(plan.export_mappings) == 273
    assert plan.boundary_assignment_summary_by_edge == {
        "bottom": {"total": 12, "outputs": 12, "inputs": 0},
        "left": {"total": 20, "outputs": 20, "inputs": 0},
        "right": {"total": 2, "outputs": 2, "inputs": 0},
        "top": {"total": 20, "outputs": 18, "inputs": 2},
    }
    assert plan.export_mapping_summary_by_mode == {
        "translated_boundary_assignment": 54,
        "translated_by_outer_plan": 219,
    }

    top_inputs = [entry for entry in plan.boundary_assignments if entry.true_edge == "top" and entry.direction == "required_input"]
    top_outputs = [entry for entry in plan.boundary_assignments if entry.true_edge == "top" and entry.direction == "required_output"]
    left_outputs = [entry for entry in plan.boundary_assignments if entry.true_edge == "left"]
    bottom_outputs = [entry for entry in plan.boundary_assignments if entry.true_edge == "bottom"]
    right_outputs = [entry for entry in plan.boundary_assignments if entry.true_edge == "right"]

    assert {entry.exported_orientation for entry in top_inputs} == {1}
    assert {(entry.exported_anchor.x, entry.exported_anchor.y) for entry in top_inputs} == {(68, 4), (71, 4)}
    assert all("shifted pure-input boundary loader 4 cells inboard" in entry.notes[0] for entry in top_inputs)
    assert {entry.exported_orientation for entry in top_outputs} == {3}
    assert {entry.exported_orientation for entry in left_outputs} == {2}
    assert {entry.exported_orientation for entry in bottom_outputs} == {1}
    assert {entry.exported_orientation for entry in right_outputs} == {0}
    assert plan.witness_summary_by_purpose == {
        "boundary_input_admission": 2,
        "boundary_input_bus": 2,
        "boundary_output_bus": 52,
    }
    assert plan.to_dict()["diagnostics"]["exporter_status"] == "not_run"


def test_canonical_70x70_base_produces_identity_outer_plan() -> None:
    blueprint = _load_full_demand_blueprint()
    plan = build_outer_base_deployment_plan(
        blueprint_payload=blueprint,
        base_id="valley4_protocol_core",
    )

    assert plan.base_lot_size == 70
    assert plan.inner_island_origin.x == 0
    assert plan.inner_island_origin.y == 0
    assert plan.moat_thickness_by_edge == {
        "top": 0,
        "right": 0,
        "bottom": 0,
        "left": 0,
    }
    assert len(plan.boundary_assignments) == 54
    assert len(plan.connector_reservations) == 0
    assert len(plan.witness_reservations) == 54
    assert len(plan.export_mappings) == 273
    assert plan.export_mapping_summary_by_mode == {"identity": 273}
    assert plan.boundary_assignment_summary_by_edge["top"] == {"total": 20, "outputs": 18, "inputs": 2}
    assert plan.boundary_assignment_summary_by_edge["left"] == {"total": 20, "outputs": 20, "inputs": 0}


@pytest.mark.parametrize(
    ("base_id", "kwargs", "expected_fragment"),
    (
        (
            "wuling_tianwangping_aid",
            {},
            "smaller than the canonical 70×70 contract",
        ),
        (
            "wuling_protocol_core",
            {"inner_island_origin": (11, 0)},
            "does not fit canonical size 70 inside base lot 80",
        ),
    ),
)
def test_outer_plan_fails_closed_on_invalid_inputs(
    base_id: str,
    kwargs: dict[str, object],
    expected_fragment: str,
) -> None:
    blueprint = _load_full_demand_blueprint()

    with pytest.raises(ValueError) as exc_info:
        build_outer_base_deployment_plan(
            blueprint_payload=blueprint,
            base_id=base_id,
            **kwargs,
        )

    assert expected_fragment in str(exc_info.value)


def test_outer_export_probe_surfaces_real_input_bus_geometry_blocker_on_wuling() -> None:
    blueprint = _load_full_demand_blueprint()
    plan = build_outer_base_deployment_plan(
        blueprint_payload=blueprint,
        base_id="wuling_protocol_core",
    )
    bundle = probe_outer_deployment_plan(
        blueprint_payload=blueprint,
        deployment_plan=plan,
    )

    assert bundle.status == "validator_clean_outer_export"
    assert bundle.blocker_classification is None
    assert bundle.validation_report["is_import_compatible"] is True
    assert bundle.validation_report["is_layout_healthy"] is True
    assert bundle.error_message is None
    assert bundle.validation_report["placement_constraint_errors"] == []
    assert bundle.deployment_plan.diagnostics.exporter_status == "validator_clean_outer_export"
    assert bundle.deployment_plan.diagnostics.validator_import_compatible is True
    assert bundle.deployment_plan.diagnostics.validator_layout_healthy is True
