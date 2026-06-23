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
from src.tests.certified_frontier_helpers import (
    attach_terminal_frontier_evidence,
    forge_legacy_terminal_certified_stop,
)
from src.tests.test_delivery_manifest import _V89_GHOST_PICK, _build_manifest_project


def _terminal_campaign_with_public_payload(
    project_root: Path,
    *,
    ghost_rect_extra: dict[str, object] | None = None,
    solution_extra: dict[str, object] | None = None,
    search_stats_extra: dict[str, object] | None = None,
    mandatory_operation_type: str | None = None,
) -> ExactCampaign:
    project_root, _facility_pools = _build_manifest_project(project_root)
    if mandatory_operation_type is not None:
        mandatory_path = project_root / "data" / "preprocessed" / "mandatory_exact_instances.json"
        mandatory_payload = json.loads(mandatory_path.read_text(encoding="utf-8"))
        mandatory_payload[0]["operation_type"] = mandatory_operation_type
        mandatory_path.write_text(
            json.dumps(mandatory_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }
    if solution_extra is not None:
        solution["tiny_001"].update(solution_extra)

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**solution, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
        loaded_exact_safe_cut_count=1,
        generated_exact_safe_cut_count=2,
    )
    ghost_rect = {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0}
    if ghost_rect_extra is not None:
        ghost_rect.update(ghost_rect_extra)
    search_stats = {"campaign_resumed": False}
    if search_stats_extra is not None:
        search_stats.update(search_stats_extra)
    campaign.state["final_result"] = {
        "ghost_rect": ghost_rect,
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": search_stats,
    }
    forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    campaign.save()
    return campaign


def test_v91_rejects_nested_ghost_rect_fake_certified_claim(tmp_path: Path) -> None:
    project_root = tmp_path / "v91_nested_ghost_rect_fake_claim"
    campaign = _terminal_campaign_with_public_payload(
        project_root,
        ghost_rect_extra={
            "proof_status": "CERTIFIED_BY_FORGED_FIELD",
            "routing_solution_certified": True,
        },
    )

    reason = terminal_certified_final_result_violation_for_project(
        campaign.state,
        project_root=project_root,
    )

    assert reason == "terminal_certified_final_result_ghost_rect_unknown_field:proof_status"
    assert campaign.best_certified_result() is None
    with pytest.raises(ValueError, match="ghost_rect_unknown_field:proof_status"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_v91_rejects_search_stats_fake_certified_claim(tmp_path: Path) -> None:
    project_root = tmp_path / "v91_search_stats_fake_certified_claim"
    campaign = _terminal_campaign_with_public_payload(
        project_root,
        search_stats_extra={
            "proof_status": "CERTIFIED_BY_FORGED_SEARCH_STATS",
        },
    )

    reason = terminal_certified_final_result_violation_for_project(
        campaign.state,
        project_root=project_root,
    )

    assert reason == "terminal_certified_final_result_search_stats_unknown_field:proof_status"
    assert campaign.best_certified_result() is None
    with pytest.raises(ValueError, match="search_stats_unknown_field:proof_status"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_v91_rejects_contradictory_mandatory_solution_metadata(tmp_path: Path) -> None:
    project_root = tmp_path / "v91_contradictory_solution_metadata"
    campaign = _terminal_campaign_with_public_payload(
        project_root,
        solution_extra={
            "instance_id": "tiny_001",
            "is_mandatory": False,
            "bound_type": "heuristic",
            "solve_mode": "exploratory",
        },
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

def test_v91_rejects_mandatory_operation_type_metadata_mismatch(tmp_path: Path) -> None:
    project_root = tmp_path / "v91_mandatory_operation_type_metadata_mismatch"
    campaign = _terminal_campaign_with_public_payload(
        project_root,
        mandatory_operation_type="canonical_operation",
        solution_extra={
            "operation_type": "exploratory_injected",
        },
    )

    reason = terminal_certified_final_result_violation_for_project(
        campaign.state,
        project_root=project_root,
    )

    assert reason == "terminal_certified_final_result_solution_metadata_mismatch"
    assert campaign.best_certified_result() is None



def test_v93_rejects_solution_entry_fake_certified_claim(tmp_path: Path) -> None:
    project_root = tmp_path / "v93_solution_entry_fake_certified_claim"
    campaign = _terminal_campaign_with_public_payload(
        project_root,
        solution_extra={
            "proof_status": "CERTIFIED_BY_FORGED_SOLUTION_FIELD",
        },
    )

    reason = terminal_certified_final_result_violation_for_project(
        campaign.state,
        project_root=project_root,
    )

    assert reason == "terminal_certified_final_result_solution_unknown_field:tiny_001.proof_status"
    assert campaign.best_certified_result() is None
    with pytest.raises(ValueError, match="solution_unknown_field:tiny_001.proof_status"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_v93_rejects_public_final_result_ghost_pick_marker(tmp_path: Path) -> None:
    project_root = tmp_path / "v93_public_final_result_ghost_pick_marker"
    campaign = _terminal_campaign_with_public_payload(project_root)
    campaign.state["final_result"]["placement_solution"]["ghost_pick"] = {
        "proof_status": "CERTIFIED_BY_GHOST_PICK_PUBLIC",
    }

    reason = terminal_certified_final_result_violation_for_project(
        campaign.state,
        project_root=project_root,
    )

    assert reason == "terminal_certified_final_result_solution_contains_ghost_pick_marker"
    assert campaign.best_certified_result() is None
    with pytest.raises(ValueError, match="solution_contains_ghost_pick_marker"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )
