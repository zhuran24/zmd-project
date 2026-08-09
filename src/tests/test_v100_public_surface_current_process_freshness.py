"""V100 compatibility checks after process-local freshness ceased being authority."""

from __future__ import annotations

import src.search.exact_campaign as exact_campaign_module
from src.search.exact_campaign import ExactCampaign


def test_v100_process_local_freshness_runtime_is_not_a_proof_authority_surface() -> None:
    removed = (
        "_grant_candidate_status_freshness_from_verified_producer",
        "_mark_candidate_status_fresh_for_current_process",
        "proof_bearing_candidate_status_freshness_violation",
        "terminal_proof_bearing_candidate_freshness_violation",
        "FreshProofBearingCandidateRecord",
    )
    for name in removed:
        assert not hasattr(exact_campaign_module, name)
    assert ExactCampaign._mark_candidate_result_from_verified_producer.__closure__ is None
