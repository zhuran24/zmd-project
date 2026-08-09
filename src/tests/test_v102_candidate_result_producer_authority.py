"""V102 compatibility checks for the data-only candidate writer boundary."""

from __future__ import annotations

import inspect
from pathlib import Path

from src.search.candidate_proof_replay import (
    CANDIDATE_PROOF_FIELD,
    project_candidate_records_for_sink,
)
from src.search.exact_campaign import ExactCampaign
from src.tests.test_p1_2_sink_replay_authority import _build_single_pose_project


def test_v102_candidate_writer_identity_is_not_proof_authority() -> None:
    writer = ExactCampaign._mark_candidate_result_from_verified_producer
    source = inspect.getsource(writer)
    assert writer.__closure__ is None
    assert "sys._getframe" not in source
    assert "mark_candidate_result" in source
    assert "candidate_proof" not in inspect.signature(writer).parameters


def test_v102_compatibility_writer_claim_is_data_until_sink_replay(
    tmp_path: Path,
) -> None:
    root = _build_single_pose_project(tmp_path / "compat_writer", width=3, height=3)
    campaign = ExactCampaign.load_or_create(root, campaign_hours=1.0, resume=False)

    campaign._mark_candidate_result_from_verified_producer(
        3,
        2,
        "INFEASIBLE",
        proof_summary={"claim_source": "compatibility_writer_without_replay_proof"},
    )

    raw_record = campaign.state["candidates"]["3x2"]
    assert raw_record["status"] == "INFEASIBLE"
    assert CANDIDATE_PROOF_FIELD not in raw_record

    projected, violations = project_candidate_records_for_sink(
        state=campaign.state,
        project_root=root,
        campaign_path=campaign.path,
    )

    assert projected["3x2"]["status"] == "UNPROVEN"
    assert CANDIDATE_PROOF_FIELD not in projected["3x2"]
    assert violations["3x2"] == "candidate_sink_replay_proof_missing:3x2"
