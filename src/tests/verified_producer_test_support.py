"""Data-only helpers for certified candidate replay fixtures.

These helpers never patch production validators and never mint proof authority.
They only attach the same replay request data that production records carry.  A
frontier, terminal, manifest, or public sink must still execute the isolated
solver replay before accepting the status.
"""

from __future__ import annotations

from collections.abc import Mapping

from src.search.candidate_proof_replay import (
    CANDIDATE_PROOF_FIELD,
    build_candidate_replay_proof,
)
from src.search.exact_campaign import ExactCampaign, STRONG_CANDIDATE_STATUSES


def seal_test_candidate_status(
    campaign: ExactCampaign,
    key: str,
    status: str,
) -> None:
    """Attach an untrusted replay request to a synthetic candidate record."""

    normalized_status = str(status)
    if normalized_status not in STRONG_CANDIDATE_STATUSES:
        raise ValueError("test replay fixtures require a proof-bearing status")
    candidates = campaign.state.get("candidates")
    normalized_key = str(key)
    if not isinstance(candidates, dict):
        raise AssertionError("test campaign candidates must be a mutable mapping")
    record = candidates.get(normalized_key)
    if not isinstance(record, Mapping):
        raise AssertionError(f"test candidate record missing: {normalized_key}")
    if str(record.get("status", "")) != normalized_status:
        raise AssertionError(
            f"test candidate status mismatch: {normalized_key}:{record.get('status')}"
        )
    raw_rect = record.get("ghost_rect")
    if not isinstance(raw_rect, Mapping):
        raise AssertionError(f"test candidate ghost_rect missing: {normalized_key}")
    solution = record.get("solution") if normalized_status == "CERTIFIED" else None
    proof = build_candidate_replay_proof(
        campaign,
        int(raw_rect["w"]),
        int(raw_rect["h"]),
        normalized_status,
        solution=solution if isinstance(solution, Mapping) else None,
    )
    mutable_record = dict(record)
    mutable_record[CANDIDATE_PROOF_FIELD] = proof
    candidates[normalized_key] = mutable_record
