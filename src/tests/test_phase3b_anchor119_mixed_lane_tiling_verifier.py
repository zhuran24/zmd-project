from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.search.phase3b_anchor119_mixed_lane_tiling_verifier import (
    ANCHOR119_MIXED_LANE_TILING_VERIFIER_SOURCE,
    _checks,
    _interval_subset_of_union,
    _p9_p10_windows,
    _sequence_states,
    _sha256_json,
    _status_from_audit,
    render_phase3b_anchor119_mixed_lane_tiling_verifier_markdown,
    render_phase3b_anchor119_mixed_lane_tiling_verifier_text,
)


def test_interval_subset_of_union_requires_complete_coverage() -> None:
    intervals = [(16, 21), (21, 26), (35, 40)]

    assert _interval_subset_of_union(16, 10, intervals) is True
    assert _interval_subset_of_union(17, 5, intervals) is True
    assert _interval_subset_of_union(24, 5, intervals) is False
    assert _interval_subset_of_union(30, 5, intervals) is False
    assert _interval_subset_of_union(35, 5, intervals) is True


def test_p9_p10_windows_allow_any_contained_non_overlapping_intervals() -> None:
    rows_by_xy = {
        (5, 16): [{"signature_id": 0}],
        (5, 18): [{"signature_id": 0}],
        (5, 21): [{"signature_id": 0}],
        (5, 24): [{"signature_id": 0}],
        (5, 35): [{"signature_id": 0}],
    }
    windows = _p9_p10_windows(rows_by_xy, [(16, 26), (35, 45)])

    assert (16, 21) in windows
    assert (18, 35) in windows
    assert (21, 35) in windows
    assert (24, 35) not in windows
    assert all(y10 >= y9 + 5 for y9, y10 in windows)


def test_sequence_states_preserves_order_and_signature_monotonicity() -> None:
    rows_by_xy = {
        (0, 16): [
            {"x": 0, "y": 16, "mode": 0, "order_key": 5, "signature_id": 0},
            {"x": 0, "y": 16, "mode": 1, "order_key": 2, "signature_id": 1},
        ],
        (1, 21): [
            {"x": 1, "y": 21, "mode": 0, "order_key": 6, "signature_id": 0},
            {"x": 1, "y": 21, "mode": 1, "order_key": 4, "signature_id": 1},
            {"x": 1, "y": 21, "mode": 2, "order_key": 7, "signature_id": 1},
        ],
    }

    states = _sequence_states(rows_by_xy, [(0, 0, 16), (1, 1, 21)])
    compact = {(signature, order) for order, signature, _seq in states}

    assert compact == {(0, 6), (1, 4)}
    for _order, _signature, seq in states:
        assert len(seq) == 2
        assert seq[1]["order_key"] >= seq[0]["order_key"]
        assert seq[1]["signature_id"] >= seq[0]["signature_id"]


def test_status_and_checks_keep_witness_diagnostic_only() -> None:
    status = _status_from_audit({"witness": {"protocol_y": 16}})

    assert status["outcome"] == "exact_tiling_witness_found"
    assert status["runtime_promotion_ready"] is False
    assert status["exhaustive"] is True

    checks = _checks(
        {
            "metadata": {"solver_invoked": False, "proof_source": False},
            "status": {"completed": True, "runtime_promotion_ready": False},
            "enumeration": {"total_patterns": 1},
        }
    )
    assert {check["check_id"]: check["status"] for check in checks} == {
        "solver_not_invoked": "pass",
        "diagnostic_not_proof_source": "pass",
        "runtime_not_promoted": "pass",
        "enumeration_completed": "pass",
        "patterns_counted": "pass",
    }


def test_current_artifact_regression_keeps_expected_diagnostic_contract() -> None:
    project_root = Path(__file__).resolve().parents[2]
    artifact_path = (
        project_root
        / ".artifacts"
        / "phase3b_anchor119_mixed_lane_tiling_verifier_module_20260423"
        / "mixed_lane_tiling_verifier.json"
    )
    if not artifact_path.exists():
        pytest.skip("current diagnostic artifact is not present in this checkout")

    report = json.loads(artifact_path.read_text(encoding="utf-8-sig"))

    assert report["metadata"]["source"] == ANCHOR119_MIXED_LANE_TILING_VERIFIER_SOURCE
    assert report["metadata"]["solver_invoked"] is False
    assert report["metadata"]["proof_source"] is False
    assert report["metadata"]["candidate_elimination_claim"] is False
    assert report["metadata"]["runtime_promotion_ready"] is False
    assert report["status"]["outcome"] == "exact_tiling_exhaustive_no_witness"
    assert report["enumeration"]["total_patterns"] == 4608
    assert report["enumeration"]["total_p9p10_window_cases"] == 0
    assert report["witness"] is None
    assert report["provenance"]["domain_rows_sha256"] == _sha256_json(
        {
            "domains": report["domains"],
            "candidate": report["candidate"],
            "derivation": report["derivation"],
        }
    )


def test_renderers_keep_diagnostic_boundaries() -> None:
    report = {
        "metadata": {
            "solver_invoked": False,
            "proof_source": False,
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "ghost_rect": {"x": 2, "y": 3, "w": 67, "h": 13},
        },
        "status": {
            "outcome": "exact_tiling_exhaustive_no_witness",
            "runtime_promotion_ready": False,
            "recommendation": "diagnostic only",
        },
        "domains": {
            "planter_counts": {"kept_rows_avoiding_anchor": 123},
            "protocol_row_count": 90,
        },
        "enumeration": {
            "total_patterns": 4608,
            "total_p9p10_window_cases": 0,
        },
        "witness": None,
        "checks": [
            {"check_id": "solver_not_invoked", "status": "pass", "detail": "no solve"}
        ],
    }

    markdown = render_phase3b_anchor119_mixed_lane_tiling_verifier_markdown(report)
    text = render_phase3b_anchor119_mixed_lane_tiling_verifier_text(report)

    assert "Solver invoked: false" in markdown
    assert "Proof source: false" in markdown
    assert "Runtime promotion ready: `False`" in markdown
    assert "solver_invoked=false" in text
    assert "proof_source=false" in text
    assert "runtime_promotion_ready=False" in text
