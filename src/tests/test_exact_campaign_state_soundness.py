from __future__ import annotations

from pathlib import Path

import pytest

from src.models.cut_manager import RUN_STATUS_CERTIFIED, RUN_STATUS_UNKNOWN
from src.search.exact_campaign import ExactCampaign, validate_exact_campaign_resume_state
from src.tests.test_v89_terminal_ghost_pick_protocol_validation import _write_project


def _certified_solution() -> dict[str, object]:
    return {
        "solid_001": {"facility_type": "solid", "pose_idx": 0},
        "ghost_pick": {"anchor": {"x": 1, "y": 0}},
    }


def test_candidate_strong_result_survives_rerun_and_requires_fresh_solution(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_project(project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)

    campaign.mark_candidate_started(2, 3)
    campaign.mark_candidate_result(
        2,
        3,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )

    campaign.mark_candidate_started(2, 3)
    record_after_start = campaign.get_candidate_record(2, 3)
    assert record_after_start is not None
    assert record_after_start["status"] == RUN_STATUS_CERTIFIED
    assert record_after_start["solution"] == _certified_solution()

    with pytest.raises(ValueError, match="fresh solution"):
        campaign.mark_candidate_result(
            2,
            3,
            RUN_STATUS_CERTIFIED,
            proof_summary={"master_status": RUN_STATUS_CERTIFIED},
            exact_safe_cuts=[],
            loaded_exact_safe_cut_count=0,
            generated_exact_safe_cut_count=0,
        )

    campaign.mark_candidate_result(
        2,
        3,
        RUN_STATUS_UNKNOWN,
        proof_summary={"master_status": RUN_STATUS_UNKNOWN},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )

    record_after_weak_result = campaign.get_candidate_record(2, 3)
    assert record_after_weak_result is not None
    assert record_after_weak_result["status"] == RUN_STATUS_CERTIFIED
    assert record_after_weak_result["solution"] == _certified_solution()
    assert any(
        entry.get("event") == "CANDIDATE_STRONG_STATUS_DOWNGRADE_BLOCKED"
        and entry.get("incoming_status") == RUN_STATUS_UNKNOWN
        for entry in campaign.get_audit_log()
    )


def test_resume_rejects_non_certified_candidate_with_stale_solution(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_project(project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(2, 3)
    campaign.mark_candidate_result(
        2,
        3,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )

    campaign.state["candidates"]["2x3"]["status"] = RUN_STATUS_UNKNOWN

    assert (
        validate_exact_campaign_resume_state(
            campaign.state,
            campaign.artifact_hashes,
            project_root=project_root,
        )
        == "candidate_non_certified_solution_present:2x3"
    )
