"""Tests for canonical_rules helper lookup typing and defaults."""
from __future__ import annotations

from src.cuts.helpers.canonical_rules import (
    cells_per_pose_for_group,
    facility_template_for_group,
    placement_rule_for_group,
    port_rule_for_group,
)
from src.cuts.lifecycle import BState, GroupState


def _state() -> BState:
    return BState(
        groups={
            "boundary_io": GroupState(
                group_id="boundary_io",
                demand=1,
                pose_domain=frozenset(),
                selected_poses=[],
            )
        },
        instance_to_facility_type={"boundary_io": "boundary_storage_port"},
        facility_templates={
            "boundary_storage_port": {
                "dimensions": {"w": 1, "h": 3},
                "placement_rule": "left_or_bottom_boundary",
                "port_rule": "inward_facing",
            }
        },
    )


def test_canonical_rules_helpers_return_typed_values():
    s = _state()
    template = facility_template_for_group(s, "boundary_io")
    assert template is not None
    assert cells_per_pose_for_group(s, "boundary_io") == 3
    assert placement_rule_for_group(s, "boundary_io") == "left_or_bottom_boundary"
    assert port_rule_for_group(s, "boundary_io") == "inward_facing"


def test_canonical_rules_helpers_fail_closed_on_missing_mapping():
    s = BState(groups={})
    assert facility_template_for_group(s, "missing") is None
    assert cells_per_pose_for_group(s, "missing") is None
    assert placement_rule_for_group(s, "missing") == "unknown"
    assert port_rule_for_group(s, "missing") == "unknown"
