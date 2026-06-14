from __future__ import annotations

import json
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


def test_resume_rejects_null_campaign_hours_without_crashing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_project(project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.state["campaign_hours"] = None
    campaign.save()

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "campaign_hours_invalid"


def test_resume_rejects_torn_top_level_timestamp_and_metadata_fields(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_project(project_root)

    created_at_campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=False,
    )
    created_at_campaign.state["created_at"] = None
    created_at_campaign.path.write_text(
        json.dumps(created_at_campaign.state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    resumed_created_at = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )

    assert resumed_created_at.resumed is False
    assert resumed_created_at.reset_reason == "created_at_invalid"

    updated_at_campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=False,
    )
    updated_at_campaign.state["updated_at"] = []
    updated_at_campaign.path.write_text(
        json.dumps(updated_at_campaign.state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    resumed_updated_at = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )

    assert resumed_updated_at.resumed is False
    assert resumed_updated_at.reset_reason == "updated_at_invalid"


def test_resume_rejects_torn_reset_reason_and_nonterminal_evidence_shape(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_project(project_root)

    reset_reason_campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=False,
    )
    reset_reason_campaign.state["reset_reason"] = []
    reset_reason_campaign.path.write_text(
        json.dumps(reset_reason_campaign.state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    resumed_reset_reason = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )

    assert resumed_reset_reason.resumed is False
    assert resumed_reset_reason.reset_reason == "reset_reason_invalid"

    evidence_campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=False,
    )
    evidence_campaign.state["terminal_frontier_evidence"] = []
    evidence_campaign.path.write_text(
        json.dumps(evidence_campaign.state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    resumed_evidence = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )

    assert resumed_evidence.resumed is False
    assert resumed_evidence.reset_reason == "terminal_frontier_evidence_invalid"


def test_resume_rejects_torn_candidate_timestamp_shapes(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _write_project(project_root)

    campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=False,
    )
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
    campaign.state["candidates"]["2x3"]["started_at"] = []
    campaign.path.write_text(
        json.dumps(campaign.state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    resumed_started_at = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )

    assert resumed_started_at.resumed is False
    assert resumed_started_at.reset_reason == "candidate_invalid_timestamp:2x3:started_at"

    campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=False,
    )
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
    campaign.state["candidates"]["2x3"]["finished_at"] = []
    campaign.path.write_text(
        json.dumps(campaign.state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    resumed_finished_at = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )

    assert resumed_finished_at.resumed is False
    assert resumed_finished_at.reset_reason == "candidate_invalid_timestamp:2x3:finished_at"

