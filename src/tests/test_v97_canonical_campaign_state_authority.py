from __future__ import annotations

from pathlib import Path

import pytest

from src.io.delivery_manifest import export_certified_delivery_manifest
from src.io.serializer import export_certified_blueprint
from src.models.cut_manager import RUN_STATUS_CERTIFIED
from src.search.certified_surface import verify_certified_delivery_surface
from src.search.exact_campaign import DEFAULT_CAMPAIGN_FILENAME, ExactCampaign
from src.search.exact_campaign_inspector import build_exact_campaign_inspection
from src.tests.certified_frontier_helpers import (
    attach_terminal_frontier_evidence,
    forge_legacy_terminal_certified_stop,
    write_closed_phase_review_gate,
)
from src.tests.test_delivery_manifest import _V89_GHOST_PICK, _build_manifest_project, _write_json


def _build_certified_manifest_toy(
    project_root: Path,
    *,
    campaign_filename: str = DEFAULT_CAMPAIGN_FILENAME,
) -> tuple[Path, ExactCampaign]:
    project_root, facility_pools = _build_manifest_project(project_root)
    write_closed_phase_review_gate(project_root)
    campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=2.0,
        resume=False,
        filename=campaign_filename,
    )
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**_V89_GHOST_PICK, **solution},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    campaign.save()

    best_result = campaign.best_certified_result()
    assert best_result is not None
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    export_certified_blueprint(
        project_root=project_root,
        result=best_result,
        facility_pools=facility_pools,
    )
    (project_root / "data" / "checkpoints" / "benders_cuts.jsonl").write_text(
        '{"schema_version": 2}\n',
        encoding="utf-8",
    )
    return project_root, campaign


def test_v97_delivery_manifest_rejects_certified_shadow_campaign_checkpoint(
    tmp_path: Path,
) -> None:
    project_root, campaign = _build_certified_manifest_toy(
        tmp_path / "shadow_writer",
        campaign_filename="shadow_state.json",
    )
    assert not (project_root / "data" / "checkpoints" / DEFAULT_CAMPAIGN_FILENAME).exists()

    with pytest.raises(ValueError, match="canonical campaign checkpoint authority"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_v97_certified_surface_rejects_certified_shadow_campaign_checkpoint(
    tmp_path: Path,
) -> None:
    project_root, campaign = _build_certified_manifest_toy(
        tmp_path / "shadow_reader",
        campaign_filename="shadow_state.json",
    )

    verdict = verify_certified_delivery_surface(
        project_root=project_root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
    )

    assert verdict.publishable is False
    assert verdict.blocked_reason == "campaign_state_path_not_canonical"


def test_v97_certified_surface_rejects_symlink_campaign_path_to_canonical_checkpoint(
    tmp_path: Path,
) -> None:
    project_root, campaign = _build_certified_manifest_toy(tmp_path / "symlink_reader")
    export_certified_delivery_manifest(
        project_root=project_root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
    )
    alias_path = project_root / "data" / "checkpoints" / "alias_exact_campaign_state.json"
    alias_path.symlink_to(campaign.path.name)

    verdict = verify_certified_delivery_surface(
        project_root=project_root,
        campaign_state=campaign.state,
        campaign_path=alias_path,
    )

    assert verdict.publishable is False
    assert verdict.blocked_reason == "campaign_state_not_regular_file"


def test_v97_inspector_preserves_symlink_campaign_path_until_surface_verifier(
    tmp_path: Path,
) -> None:
    project_root, campaign = _build_certified_manifest_toy(tmp_path / "symlink_inspector")
    export_certified_delivery_manifest(
        project_root=project_root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
    )
    alias_path = project_root / "data" / "checkpoints" / "alias_exact_campaign_state.json"
    alias_path.symlink_to(campaign.path.name)

    inspection = build_exact_campaign_inspection(project_root, campaign_state_path=alias_path)

    assert inspection["certified_surface"]["publishable"] is False
    assert inspection["certified_surface"]["blocked_reason"] == "campaign_state_not_regular_file"
    checks = {entry["check_id"]: entry["status"] for entry in inspection["checks"]}
    assert checks["certified_surface_current"] == "fail"
