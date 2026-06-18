"""Test-only support for downstream proof-surface fixtures.

The production freshness grant remains caller-checked.  Tests that deliberately
construct already-verified candidate records may temporarily replace only that
caller check while running under pytest.  This helper is outside the production
source digest and must never be imported by runtime code.
"""

from __future__ import annotations

import os

import src.search.exact_campaign as exact_campaign_module
from src.search.exact_campaign import ExactCampaign


def seal_test_candidate_status(
    campaign: ExactCampaign,
    key: str,
    status: str,
) -> None:
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        raise RuntimeError("test freshness bypass is available only inside pytest")
    original_validator = (
        exact_campaign_module._verified_producer_grant_caller_violation
    )
    exact_campaign_module._verified_producer_grant_caller_violation = (
        lambda _caller: None
    )
    try:
        exact_campaign_module._grant_candidate_status_freshness_from_verified_producer(
            campaign,
            str(key),
            str(status),
        )
    finally:
        exact_campaign_module._verified_producer_grant_caller_violation = (
            original_validator
        )
