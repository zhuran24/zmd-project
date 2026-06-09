from __future__ import annotations

from pathlib import Path

from src.models.cut_manager import RUN_STATUS_CERTIFIED, RUN_STATUS_UNKNOWN
from src.search.exact_campaign import ExactCampaign, validate_exact_campaign_resume_state
from src.tests.test_exact_contract import _build_frontier_project


def test_exact_campaign_resume_rejects_certified_final_result_without_terminal_frontier_evidence(
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=2, height=2)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={"tiny_001": {"facility_type": "tiny_facility", "pose_idx": 0}},
        proof_summary={"mode": "certified_exact", "master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1},
        "placement_solution": {"tiny_001": {"facility_type": "tiny_facility", "pose_idx": 0}},
        "search_status": RUN_STATUS_CERTIFIED,
    }
    campaign.mark_campaign_stopped("candidate_returned_unknown", status=RUN_STATUS_UNKNOWN)
    campaign.state["final_status"] = RUN_STATUS_CERTIFIED
    campaign.save()

    reason = validate_exact_campaign_resume_state(
        campaign.state,
        campaign.artifact_hashes,
        project_root=project_root,
    )
    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert reason == "terminal_certified_frontier_evidence_invalid"
    assert resumed.resumed is False
    assert resumed.compatible_hashes is False
    assert resumed.state["reset_reason"] == "terminal_certified_frontier_evidence_invalid"
