from __future__ import annotations

from pathlib import Path

from src.models.cut_manager import RUN_STATUS_CERTIFIED, RUN_STATUS_UNKNOWN
from src.search.certified_frontier import (
    TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
    build_terminal_frontier_evidence,
)
from src.search.exact_campaign import (
    ExactCampaign,
    has_valid_terminal_full_frontier_certified_evidence,
    validate_exact_campaign_resume_state,
)
from src.search.exact_campaign_inspector import build_exact_campaign_inspection
from src.search.phase3b.b5a.b5_anchor_sprint import build_phase3b_b5_anchor_sprint_summary
from src.tests.certified_frontier_helpers import attach_terminal_frontier_evidence
from src.tests.test_exact_contract import _build_frontier_project


def _forge_legacy_terminal_certified_stop(campaign: ExactCampaign) -> None:
    campaign.state["last_stop_reason"] = {
        "reason": "search_exhausted_all_candidates",
        "status": RUN_STATUS_CERTIFIED,
        "updated_at": "2026-03-16T00:00:00Z",
    }
    campaign.state["final_status"] = RUN_STATUS_CERTIFIED


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


def test_v75_resume_rejects_terminal_certified_without_replayable_frontier_evidence(
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
    _forge_legacy_terminal_certified_stop(campaign)
    campaign.save()

    reason = validate_exact_campaign_resume_state(
        campaign.state,
        campaign.artifact_hashes,
        project_root=project_root,
    )
    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert reason == "terminal_frontier_evidence_missing"
    assert resumed.resumed is False
    assert resumed.compatible_hashes is False
    assert resumed.state["reset_reason"] == "terminal_frontier_evidence_missing"


def test_v75_resume_rejects_terminal_evidence_with_unexhausted_frontier(
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
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    campaign.save()

    reason = validate_exact_campaign_resume_state(
        campaign.state,
        campaign.artifact_hashes,
        project_root=project_root,
    )
    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert reason == "terminal_frontier_potential_domain_not_exhausted"
    assert resumed.resumed is False
    assert resumed.compatible_hashes is False
    assert resumed.state["reset_reason"] == "terminal_frontier_potential_domain_not_exhausted"


def test_v75_resume_rejects_terminal_evidence_from_start_area_slice(
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=1, height=1)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={},
        proof_summary={"mode": "certified_exact", "master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1},
        "placement_solution": {},
        "search_status": RUN_STATUS_CERTIFIED,
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    campaign.state["terminal_frontier_evidence"]["candidate_generation"]["start_area"] = 1
    campaign.save()

    reason = validate_exact_campaign_resume_state(
        campaign.state,
        campaign.artifact_hashes,
        project_root=project_root,
    )

    assert reason == "terminal_frontier_start_area_not_full_domain"


def test_v79_resume_rejects_terminal_evidence_from_aspect_ratio_slice(
    tmp_path: Path,
) -> None:
    # V79: max_aspect_ratio 切片域与 start_area 同形 — 被滤掉的高长宽比候选从未
    # 被反驳, 耗尽的子域不得宣称权威全域 terminal CERTIFIED。
    project_root = _build_frontier_project(tmp_path / "project", width=1, height=1)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={},
        proof_summary={"mode": "certified_exact", "master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1},
        "placement_solution": {},
        "search_status": RUN_STATUS_CERTIFIED,
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root, max_aspect_ratio=3.0)
    campaign.save()

    reason = validate_exact_campaign_resume_state(
        campaign.state,
        campaign.artifact_hashes,
        project_root=project_root,
    )

    assert reason == "terminal_frontier_aspect_ratio_sliced_domain"


def test_v79_resume_rejects_terminal_evidence_from_min_side_slice(
    tmp_path: Path,
) -> None:
    # V79: min_side 高于 admissibility 下限 (6, PROJECT_LOCK) 意味着只搜了目标域的
    # 真子域; 这种 evidence 不得宣称权威全域 terminal CERTIFIED。
    project_root = _build_frontier_project(tmp_path / "project", width=7, height=7)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(7, 7)
    campaign.mark_candidate_result(
        7,
        7,
        RUN_STATUS_CERTIFIED,
        solution={},
        proof_summary={"mode": "certified_exact", "master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 7, "h": 7, "area": 49},
        "placement_solution": {},
        "search_status": RUN_STATUS_CERTIFIED,
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root, min_side=7)
    campaign.save()

    reason = validate_exact_campaign_resume_state(
        campaign.state,
        campaign.artifact_hashes,
        project_root=project_root,
    )

    assert reason == "terminal_frontier_min_side_sliced_domain"


def test_v67_resume_inspector_and_b5a_reject_terminal_final_result_without_candidate_record(
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=2, height=2)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.state["candidates"] = {}
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 2, "h": 2, "area": 4},
        "placement_solution": {"tiny_001": {"facility_type": "tiny_facility", "pose_idx": 0}},
        "search_status": RUN_STATUS_CERTIFIED,
    }
    _forge_legacy_terminal_certified_stop(campaign)
    campaign.save()

    reason = validate_exact_campaign_resume_state(
        campaign.state,
        campaign.artifact_hashes,
        project_root=project_root,
    )
    resumed = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )
    inspection = build_exact_campaign_inspection(project_root)
    b5a_summary = build_phase3b_b5_anchor_sprint_summary(project_root)

    assert reason == "terminal_certified_candidate_record_missing"
    assert resumed.resumed is False
    assert resumed.compatible_hashes is False
    assert resumed.state["reset_reason"] == "terminal_certified_candidate_record_missing"
    assert inspection["campaign"]["resume_compatible_with_current_hashes"] is False
    assert inspection["campaign"]["resume_validation_reason"] == (
        "terminal_certified_candidate_record_missing"
    )
    assert inspection["campaign"]["terminal_full_frontier_certified"] is False
    assert inspection["campaign"]["best_certified_result"] is None
    assert b5a_summary["status"]["anchor_found"] is False
    assert b5a_summary["anchor"] is None


def test_v68_resume_rejects_certified_candidate_without_solution(
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=1, height=1)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    record = campaign.state["candidates"]["1x1"]
    record["status"] = RUN_STATUS_CERTIFIED
    record["finished_at"] = record["updated_at"]
    record["proof_summary"] = {
        "mode": "certified_exact",
        "master_status": RUN_STATUS_CERTIFIED,
    }
    campaign.save()

    reason = validate_exact_campaign_resume_state(
        campaign.state,
        campaign.artifact_hashes,
        project_root=project_root,
    )
    resumed = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )

    assert reason == "candidate_certified_solution_missing:1x1"
    assert resumed.resumed is False
    assert resumed.compatible_hashes is False
    assert resumed.state["reset_reason"] == "candidate_certified_solution_missing:1x1"


def test_v69_resume_inspector_and_b5a_reject_terminal_final_result_not_best_candidate(
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=2, height=2)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={},
        proof_summary={"mode": "certified_exact", "master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.mark_candidate_started(2, 2)
    campaign.mark_candidate_result(
        2,
        2,
        RUN_STATUS_CERTIFIED,
        solution={},
        proof_summary={"mode": "certified_exact", "master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1},
        "placement_solution": {},
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    campaign.save()

    reason = validate_exact_campaign_resume_state(
        campaign.state,
        campaign.artifact_hashes,
        project_root=project_root,
    )
    resumed = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )
    inspection = build_exact_campaign_inspection(project_root)
    b5a_summary = build_phase3b_b5_anchor_sprint_summary(project_root)

    assert reason == "terminal_certified_final_result_not_best_candidate"
    assert resumed.resumed is False
    assert resumed.compatible_hashes is False
    assert resumed.state["reset_reason"] == "terminal_certified_final_result_not_best_candidate"
    assert inspection["campaign"]["resume_compatible_with_current_hashes"] is False
    assert inspection["campaign"]["resume_validation_reason"] == (
        "terminal_certified_final_result_not_best_candidate"
    )
    assert inspection["campaign"]["terminal_full_frontier_certified"] is False
    assert inspection["campaign"]["best_certified_result"] is None
    assert b5a_summary["status"]["anchor_found"] is False
    assert b5a_summary["anchor"] is None

def test_v76_best_certified_result_rejects_frontier_evidence_not_bound_to_project_domain(
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=2, height=2)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    solution = {"tiny_001": {"facility_type": "tiny_facility", "pose_idx": 0}}
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution=solution,
        proof_summary={"mode": "certified_exact", "master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
    }
    _forge_legacy_terminal_certified_stop(campaign)
    campaign.state["terminal_frontier_evidence"] = build_terminal_frontier_evidence(
        candidates=[(1, 1, 1)],
        candidate_records=campaign.state["candidates"],
        final_result=campaign.state["final_result"],
        candidate_generation={
            "max_w": 1,
            "max_h": 1,
            "min_side": 1,
            "max_aspect_ratio": None,
            "area_upper_bound": 1,
            "start_area": None,
            "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
            "safe_area_upper_bound": 1,
            "min_side_admissibility": 1,
        },
    )

    reason = validate_exact_campaign_resume_state(
        campaign.state,
        campaign.artifact_hashes,
        project_root=project_root,
    )

    assert has_valid_terminal_full_frontier_certified_evidence(campaign.state) is True
    assert campaign.best_certified_result() is None
    assert reason == "terminal_frontier_candidate_generation_grid_mismatch"


def test_v80_resume_rejects_terminal_evidence_unknown_candidate_generation_key(
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=1, height=1)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={},
        proof_summary={"mode": "certified_exact", "master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1},
        "placement_solution": {},
        "search_status": RUN_STATUS_CERTIFIED,
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    campaign.state["terminal_frontier_evidence"]["candidate_generation"][
        "future_candidate_axis"
    ] = "full"

    reason = validate_exact_campaign_resume_state(
        campaign.state,
        campaign.artifact_hashes,
        project_root=project_root,
    )

    assert reason == "terminal_frontier_candidate_generation_unknown_key"


def test_v80_resume_rejects_terminal_evidence_min_side_admissibility_mismatch(
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=1, height=1)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={},
        proof_summary={"mode": "certified_exact", "master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1},
        "placement_solution": {},
        "search_status": RUN_STATUS_CERTIFIED,
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    campaign.state["terminal_frontier_evidence"]["candidate_generation"][
        "min_side_admissibility"
    ] = 2

    reason = validate_exact_campaign_resume_state(
        campaign.state,
        campaign.artifact_hashes,
        project_root=project_root,
    )

    assert reason == "terminal_frontier_min_side_admissibility_mismatch"


def test_v80_resume_rejects_v1_terminal_frontier_evidence_schema(
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "project", width=1, height=1)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={},
        proof_summary={"mode": "certified_exact", "master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1},
        "placement_solution": {},
        "search_status": RUN_STATUS_CERTIFIED,
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    campaign.state["terminal_frontier_evidence"]["schema_version"] = 1
    campaign.state["terminal_frontier_evidence"]["source"] = (
        "certified_terminal_frontier_evidence_v1"
    )

    reason = validate_exact_campaign_resume_state(
        campaign.state,
        campaign.artifact_hashes,
        project_root=project_root,
    )

    assert reason == "terminal_frontier_evidence_schema_invalid"


def test_v80_resume_rejects_terminal_final_result_below_project_admissibility(
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(
        tmp_path / "project",
        width=7,
        height=7,
        min_side_admissibility=6,
    )
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(7, 5)
    campaign.mark_candidate_result(
        7,
        5,
        RUN_STATUS_CERTIFIED,
        solution={},
        proof_summary={"mode": "certified_exact", "master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 7, "h": 5, "area": 35},
        "placement_solution": {},
        "search_status": RUN_STATUS_CERTIFIED,
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root, min_side=1)

    reason = validate_exact_campaign_resume_state(
        campaign.state,
        campaign.artifact_hashes,
        project_root=project_root,
    )

    assert reason == "terminal_certified_final_result_below_admissibility"
