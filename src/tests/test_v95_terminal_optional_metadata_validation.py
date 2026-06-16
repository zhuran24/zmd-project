from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.io.delivery_manifest import export_certified_delivery_manifest
from src.models.cut_manager import RUN_STATUS_CERTIFIED
from src.search.exact_campaign import (
    ExactCampaign,
    terminal_certified_final_result_violation_for_project,
)
from src.tests.certified_frontier_helpers import attach_terminal_frontier_evidence


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_optional_project(root: Path) -> dict[str, list[dict[str, object]]]:
    facility_pools: dict[str, list[dict[str, object]]] = {
        "solid": [
            {
                "pose_id": "solid_at_0_0",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
            }
        ],
        "protocol_storage_box": [
            {
                "pose_id": "box_at_0_1",
                "anchor": {"x": 0, "y": 1},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[0, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
            }
        ],
    }
    _write_json(
        root / "rules" / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": 2, "height": 2},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 1,
                },
            },
            "facility_templates": {
                "solid": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
                "protocol_storage_box": {
                    "dimensions": {"w": 1, "h": 1},
                    "needs_power": False,
                },
            },
            "commodity_metadata": {
                "demo_input": {"source_kind": "internal_only", "sink_kind": "generic_input"},
            },
        },
    )
    _write_json(
        root / "rules" / "preprocess_plan.json",
        {
            "utility_operations": {
                "wireless_sink": {
                    "facility_type": "protocol_storage_box",
                    "generic_input_slots": 3,
                }
            }
        },
    )
    _write_json(root / "data" / "preprocessed" / "candidate_placements.json", {"facility_pools": facility_pools})
    _write_json(
        root / "data" / "preprocessed" / "mandatory_exact_instances.json",
        [
            {
                "instance_id": "solid_001",
                "facility_type": "solid",
                "operation_type": "solid_op",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            }
        ],
    )
    # wireless_sink exposes generic-input capacity, so one protocol storage box is required.
    _write_json(
        root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_inputs": {"demo_input": 1}, "required_generic_outputs": {}},
    )
    return facility_pools


def _terminal_campaign_with_optional_extra(
    project_root: Path,
    *,
    optional_extra: dict[str, object],
) -> ExactCampaign:
    _write_optional_project(project_root)
    optional_key = "pose_optional::protocol_storage_box::box_at_0_1"
    solution: dict[str, dict[str, object]] = {
        "solid_001": {
            "facility_type": "solid",
            "pose_idx": 0,
            "pose_id": "solid_at_0_0",
            "anchor": {"x": 0, "y": 0},
            "instance_id": "solid_001",
            "operation_type": "solid_op",
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_mode": "certified_exact",
        },
        optional_key: {
            "facility_type": "protocol_storage_box",
            "pose_idx": 0,
            "pose_id": "box_at_0_1",
            "anchor": {"x": 0, "y": 1},
            "instance_id": optional_key,
            "operation_type": "wireless_sink",
            "is_mandatory": False,
            "bound_type": "exact_pose_optional",
            "solve_mode": "certified_exact",
            **optional_extra,
        },
    }
    certified_solution = dict(solution)
    certified_solution["ghost_pick"] = {
        "pose_idx": 0,
        "pose_id": "ghost_anchor::1,0",
        "anchor": {"x": 1, "y": 0},
        "facility_type": "ghost_rect",
    }

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    campaign.mark_candidate_started(1, 2)
    campaign.mark_candidate_result(
        1,
        2,
        RUN_STATUS_CERTIFIED,
        solution=certified_solution,
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 2, "area": 2, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    campaign.mark_campaign_stopped("search_exhausted_all_candidates", status=RUN_STATUS_CERTIFIED)
    attach_terminal_frontier_evidence(campaign, project_root)
    campaign.save()
    return campaign


@pytest.mark.parametrize(
    "optional_extra",
    [
        {"instance_id": "fake_certified_optional_instance"},
        {"operation_type": "CERTIFIED_BY_FORGED_OPTIONAL_OPERATION"},
    ],
)
def test_v95_rejects_contradictory_pose_optional_public_metadata(
    tmp_path: Path,
    optional_extra: dict[str, object],
) -> None:
    project_root = tmp_path / "v95_contradictory_pose_optional_public_metadata"
    campaign = _terminal_campaign_with_optional_extra(
        project_root,
        optional_extra=optional_extra,
    )

    reason = terminal_certified_final_result_violation_for_project(
        campaign.state,
        project_root=project_root,
    )

    assert reason == "terminal_certified_final_result_solution_metadata_mismatch"
    assert campaign.best_certified_result() is None
    with pytest.raises(ValueError, match="solution_metadata_mismatch"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_v95_rejects_terminal_public_last_stop_reason_extra_claim_field(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "v95_terminal_last_stop_reason_extra_claim"
    campaign = _terminal_campaign_with_optional_extra(
        project_root,
        optional_extra={},
    )
    campaign.state["last_stop_reason"]["note"] = "CERTIFIED_BY_FORGED_STOP_REASON_NOTE"
    campaign.save()

    reason = terminal_certified_final_result_violation_for_project(
        campaign.state,
        project_root=project_root,
    )

    assert reason == "terminal_certified_last_stop_reason_unknown_field:note"
    assert campaign.best_certified_result() is None
    with pytest.raises(ValueError, match="last_stop_reason_unknown_field:note"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )
