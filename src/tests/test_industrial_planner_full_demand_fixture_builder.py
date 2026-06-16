"""Tests for the full-demand IndustrialPlanner canonical fixture planner."""

from __future__ import annotations

import pytest

from scripts.build_industrial_planner_full_demand_fixture import (
    FullDemandFixturePlanningError,
    plan_full_demand_recipe_capacity_fixture,
)
from src.adapters.industrial_planner.export_blueprint import build_industrial_planner_export_bundle


def test_default_base_full_demand_planner_stays_validator_clean_and_proven() -> None:
    payload, report = plan_full_demand_recipe_capacity_fixture()
    bundle = build_industrial_planner_export_bundle(blueprint_payload=payload)

    assert report.status == "proven_equivalent"
    assert report.selected_input_slots == (63, 66)
    assert {
        edge: len(positions)
        for edge, positions in report.selected_output_slots_by_edge
    } == {
        "top": 18,
        "left": 20,
        "bottom": 12,
        "right": 2,
    }
    assert report.validator_import_compatible is True
    assert report.validator_layout_healthy is True
    assert bundle["validation_report"]["is_import_compatible"] is True
    assert bundle["validation_report"]["is_layout_healthy"] is True
    assert bundle["throughput_report"]["status"] == "proven_equivalent"


@pytest.mark.parametrize(
    ("base_id", "expected_status", "expected_fragment"),
    (
        (
            "valley4_infra_outpost",
            "infeasible",
            "required manufacturing area 3325 exceeds lot area 1600",
        ),
        (
            "wuling_protocol_core",
            "unsupported_by_canonical_contract",
            "canonical blueprint contract is capped at 70×70",
        ),
    ),
)
def test_full_demand_planner_fails_closed_on_unsupported_bases(
    base_id: str,
    expected_status: str,
    expected_fragment: str,
) -> None:
    with pytest.raises(FullDemandFixturePlanningError) as exc_info:
        plan_full_demand_recipe_capacity_fixture(base_id=base_id)

    report = exc_info.value.report
    assert report.base_id == base_id
    assert report.status == expected_status
    assert report.error_message is not None
    assert expected_fragment in report.error_message
    assert report.selected_input_slots == ()
    assert report.selected_output_slots_by_edge == ()
