from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.io.delivery_manifest import (
    delivery_manifest_output_path,
    export_certified_delivery_manifest,
)
from src.search.exact_campaign import ExactCampaign, has_certified_export_surface
from src.search.exact_campaign_inspector import build_exact_campaign_inspection
from src.search.outer_search import run_outer_search
from src.tests.test_exact_contract import _build_toy_exact_project


_TERMINAL_INFEASIBLE_EVIDENCE_UNAVAILABLE_REASON = (
    "search_exhausted_without_replayable_infeasible_evidence"
)


def test_v101_sliced_empty_domain_cannot_publish_terminal_infeasible(
    tmp_path: Path,
) -> None:
    # The toy project has a real legal 1x1 empty rectangle at cell (1, 0).
    # start_area=0 removes that candidate from the generated domain, so exhausting
    # the sliced domain cannot prove project-level INFEASIBLE.
    project_root = _build_toy_exact_project(tmp_path / "sliced_empty_domain")

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        start_area=0,
        min_side=1,
        max_attempts=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        flow_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=1,
    )

    checkpoint_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    campaign_state = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    manifest = json.loads(delivery_manifest_output_path(project_root).read_text(encoding="utf-8"))
    inspection = build_exact_campaign_inspection(project_root)

    assert status == "UNPROVEN"
    assert result is None
    assert campaign_state["final_status"] == "UNPROVEN"
    assert campaign_state["last_stop_reason"] == {
        "reason": _TERMINAL_INFEASIBLE_EVIDENCE_UNAVAILABLE_REASON,
        "status": "UNPROVEN",
        "updated_at": campaign_state["last_stop_reason"]["updated_at"],
    }
    assert campaign_state["terminal_frontier_evidence"] is None
    assert manifest["campaign"]["final_status"] == "UNPROVEN"
    assert manifest["campaign"]["last_stop_reason"]["reason"] == (
        _TERMINAL_INFEASIBLE_EVIDENCE_UNAVAILABLE_REASON
    )
    assert manifest["best_certified_result"] is None
    assert inspection["campaign"]["final_status"] == "UNPROVEN"
    assert inspection["delivery_manifest"]["campaign_final_status"] == "UNPROVEN"


def test_v101_terminal_infeasible_is_proof_bearing_and_not_exportable_without_evidence(
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "terminal_infeasible_export")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_campaign_stopped(
        "search_exhausted_all_candidates",
        status="INFEASIBLE",
    )
    campaign.save()

    assert has_certified_export_surface(campaign.state) is True
    with pytest.raises(ValueError, match="exhausted strict candidate frontier"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )

    inspection = build_exact_campaign_inspection(project_root)
    assert inspection["campaign"]["final_status"] is None
    assert inspection["campaign"]["last_stop_reason"]["status"] is None
    assert inspection["campaign"]["resume_validation_reason"] == (
        "terminal_certified_frontier_evidence_invalid"
    )
    assert inspection["delivery_manifest"]["present"] is False


def test_v101_resume_rejects_terminal_infeasible_without_replayable_evidence(
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "terminal_infeasible_resume")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_campaign_stopped(
        "search_exhausted_all_candidates",
        status="INFEASIBLE",
    )
    campaign.save()

    resumed = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )

    assert resumed.resumed is False
    assert resumed.compatible_hashes is False
    assert resumed.state["reset_reason"] == "terminal_certified_frontier_evidence_invalid"
    assert resumed.state["final_status"] is None
    assert resumed.state["final_result"] is None
    assert resumed.state["last_stop_reason"] is None
