"""Tests for the PR2 #7 production supervisor certify entrypoint.

The entrypoint is a thin CLI wiring layer: find an already-committed
CANDIDATE_PROPOSED proposal, call ExactCampaign.supervisor_seal(), avoid
publishing a delivery surface, and fail closed when preconditions are missing.
True seal E2E sentinels live in test_p1_2_supervisor_pr1.py, including direct
campaign.supervisor_seal() coverage around lines 323-350 and 439-446; this file
does not test the isolated L0 seal semantics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.models.cut_manager import RUN_STATUS_CERTIFIED
from src.search.exact_campaign import (
    CANDIDATE_PROPOSED_STATUS,
    ExactCampaign,
    TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    proposal_ready_marker_path_for_campaign,
)
from src.tests.test_exact_contract import _build_toy_exact_project
from scripts import run_supervisor_seal


def _campaign_checkpoint(project_root: Path) -> Path:
    return project_root / "data" / "checkpoints" / "exact_campaign_state.json"


def _proposal_final_result() -> dict[str, Any]:
    return {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": {
            "tiny_001": {
                "facility_type": "tiny_facility",
                "pose_idx": 0,
                "pose_id": "tiny_left",
                "anchor": {"x": 0, "y": 0},
                "orientation": 0,
                "port_mode": "default",
            }
        },
        "search_status": CANDIDATE_PROPOSED_STATUS,
        "search_stats": {"solve_mode": "certified_exact", "campaign_resumed": False},
    }


def _proposal_terminal_frontier_evidence() -> dict[str, Any]:
    return {"candidate_generation": {"domain_authority": "test_cli_wiring"}}


def _prepare_candidate_proposed_campaign(
    project_root: Path,
    *,
    run_id: str,
    write_marker: bool = True,
) -> ExactCampaign:
    campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=False,
    )
    campaign.set_supervisor_proposal_run_id(run_id)
    campaign.state["final_result"] = _proposal_final_result()
    campaign.mark_campaign_stopped(
        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        status=CANDIDATE_PROPOSED_STATUS,
    )
    campaign.state["terminal_frontier_evidence"] = _proposal_terminal_frontier_evidence()
    campaign.save()
    if write_marker:
        campaign.write_proposal_ready_marker(run_id=run_id, exit_code=0)
    return campaign


def test_seals_proposal_and_second_run_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "seal_ok")
    _prepare_candidate_proposed_campaign(
        project_root,
        run_id="test-run-supervisor-seal-cli-wiring",
    )

    pre = ExactCampaign.load_or_create(project_root, resume=True)
    assert pre.state["final_status"] == CANDIDATE_PROPOSED_STATUS

    seal_calls: list[Path] = []

    def fake_supervisor_seal(self: ExactCampaign) -> None:
        seal_calls.append(self.project_root)
        final_result = dict(self.state["final_result"])
        final_result["search_status"] = RUN_STATUS_CERTIFIED
        self.state["final_result"] = final_result
        self.state["final_status"] = RUN_STATUS_CERTIFIED
        self.state["last_stop_reason"] = {
            "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
            "status": RUN_STATUS_CERTIFIED,
            "updated_at": "2000-01-01T00:00:00+00:00",
        }
        self.state["test_cli_wiring_fake_seal"] = True
        self.path.write_text(
            json.dumps(self.state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        proposal_ready_marker_path_for_campaign(self.path).unlink(missing_ok=True)

    monkeypatch.setattr(ExactCampaign, "supervisor_seal", fake_supervisor_seal)

    # 通电≠发布: spy the central publisher so we assert the entrypoint itself never
    # publishes a delivery surface during the seal (file existence is a poor proxy —
    # the proposal stage legitimately writes a delivery manifest as evidence material).
    import src.search.certified_surface as certified_surface_module

    publish_calls: list[tuple] = []
    monkeypatch.setattr(
        certified_surface_module,
        "publish_verified_certified_delivery_surface",
        lambda *a, **k: publish_calls.append((a, k)),
    )

    assert run_supervisor_seal.main(["--project-root", str(project_root)]) == 0
    assert seal_calls == [project_root.resolve()]
    assert publish_calls == []  # the seal entrypoint must not publish

    sealed = json.loads(_campaign_checkpoint(project_root).read_text(encoding="utf-8"))
    assert sealed["final_status"] == RUN_STATUS_CERTIFIED
    assert sealed["final_result"]["search_status"] == RUN_STATUS_CERTIFIED
    assert sealed["test_cli_wiring_fake_seal"] is True
    # marker consumed on a successful seal
    assert not proposal_ready_marker_path_for_campaign(
        _campaign_checkpoint(project_root)
    ).exists()

    # already sealed → second run finds no CANDIDATE_PROPOSED proposal, fails closed
    assert run_supervisor_seal.main(["--project-root", str(project_root)]) == 2


def test_missing_checkpoint_fails_closed(tmp_path: Path) -> None:
    assert run_supervisor_seal.main(["--project-root", str(tmp_path)]) == 2


def test_missing_marker_fails_closed(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "no_marker")
    _prepare_candidate_proposed_campaign(
        project_root,
        run_id="test-run-supervisor-seal-no-marker",
        write_marker=False,
    )

    assert run_supervisor_seal.main(["--project-root", str(project_root)]) == 2
    # main returns before any resume, so the on-disk proposal is untouched — still
    # CANDIDATE_PROPOSED, never forged to CERTIFIED. (Read disk directly: a
    # resume() here would itself demote the marker-less proposal.)
    disk = json.loads(
        _campaign_checkpoint(project_root).read_text(encoding="utf-8")
    )
    assert disk["final_status"] == CANDIDATE_PROPOSED_STATUS
