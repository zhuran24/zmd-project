"""V81: the single-base release path must not trust a self-claimed CERTIFIED status.

These are pure unit tests against _validate_ready_run_summary; they deliberately
live outside test_industrial_planner_single_base_delivery_release.py, whose whole
module is skipped when the .artifacts e2e fixture is absent.
"""

from __future__ import annotations

import pytest

from scripts.build_industrial_planner_single_base_delivery_release import (
    SingleBaseDeliveryReleaseError,
    _validate_ready_run_summary,
)


def _delivery_ready_run_summary(base_id: str) -> dict:
    return {
        "overall_status": "success",
        "deliverable_status": "ready_for_single_base_delivery",
        "requested_base_id": base_id,
        "active_contract_base_id": base_id,
        "requested_base_is_active_contract": True,
        "validation": {"is_import_compatible": True, "is_layout_healthy": True},
        "throughput": {"status": "proven_equivalent"},
        "checked_in_support_suite_inventory": {"status": "clean"},
        "checked_artifact_suite": {"status": "clean"},
    }


def test_v81_release_rejects_self_claimed_certified_run_summary() -> None:
    summary = _delivery_ready_run_summary("valley4_protocol_core")
    summary["exact_full_scale_certified"] = {"status": "CERTIFIED", "note": "forged"}
    with pytest.raises(SingleBaseDeliveryReleaseError, match="may not claim 'CERTIFIED'"):
        _validate_ready_run_summary(summary, expected_base_id="valley4_protocol_core")


def test_v81_release_rejects_lowercase_certified_claim() -> None:
    summary = _delivery_ready_run_summary("valley4_protocol_core")
    summary["exact_full_scale_certified"] = {"status": "certified"}
    with pytest.raises(SingleBaseDeliveryReleaseError, match="may not claim 'CERTIFIED'"):
        _validate_ready_run_summary(summary, expected_base_id="valley4_protocol_core")


def test_v92_release_rejects_embedded_certified_claim() -> None:
    summary = _delivery_ready_run_summary("valley4_protocol_core")
    summary["exact_full_scale_certified"] = {
        "status": "CERTIFIED_BY_FAKE_RELEASE_SUMMARY",
        "note": "token smuggled through a non-authoritative status",
    }
    with pytest.raises(SingleBaseDeliveryReleaseError, match="may not claim 'CERTIFIED'"):
        _validate_ready_run_summary(summary, expected_base_id="valley4_protocol_core")


def test_v92_release_rejects_non_allowlisted_exact_status() -> None:
    summary = _delivery_ready_run_summary("valley4_protocol_core")
    summary["exact_full_scale_certified"] = {"status": "proof_complete"}
    with pytest.raises(SingleBaseDeliveryReleaseError, match="must be one of"):
        _validate_ready_run_summary(summary, expected_base_id="valley4_protocol_core")


def test_v81_release_accepts_open_exact_certified_status() -> None:
    summary = _delivery_ready_run_summary("valley4_protocol_core")
    summary["exact_full_scale_certified"] = {"status": "open"}
    _validate_ready_run_summary(summary, expected_base_id="valley4_protocol_core")


def test_v93_release_rejects_forged_exact_note_with_open_status() -> None:
    summary = _delivery_ready_run_summary("valley4_protocol_core")
    summary["exact_full_scale_certified"] = {
        "status": "open",
        "note": "CERTIFIED_BY_FAKE_RELEASE_SUMMARY: terminal proof accepted by release summary",
    }
    with pytest.raises(SingleBaseDeliveryReleaseError, match="canonical non-authoritative exact-status note"):
        _validate_ready_run_summary(summary, expected_base_id="valley4_protocol_core")

