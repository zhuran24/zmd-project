from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_payload_footprint_probe_review import (
    EXPECTED_RUN_ID,
    build_signature_bucket_payload_footprint_probe_review,
)


def test_payload_footprint_probe_review_classifies_effective(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            stability_used=5400,
            stability_fallbacks=100,
            gap_reasons={"unstable_footprint_bounds_within_payload": 100},
            current_scan=18.0,
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "payload_footprint_stability_effective"
    assert review["interpretation"]["payload_footprint_stability_used"] == 5400


def test_payload_footprint_probe_review_zero_current_fallbacks_allows_empty_reasons(
    tmp_path: Path,
) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            stability_used=6786,
            stability_fallbacks=0,
            gap_reasons={},
            current_scan=0.2,
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "payload_footprint_stability_effective"
    assert review["interpretation"]["support_gap_reason_total"] == 0
    assert review["interpretation"]["current_unstable_footprint_bounds_fallbacks"] == 0


def test_payload_footprint_probe_review_fallbacks_without_reasons_are_inconclusive(
    tmp_path: Path,
) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            stability_used=4000,
            stability_fallbacks=10,
            gap_reasons={},
            current_scan=2.0,
        ),
    )

    assert review["status"] == "payload_footprint_probe_inconclusive"
    assert review["interpretation"]["classification"] == "payload_footprint_probe_inconclusive"


def test_payload_footprint_probe_review_classifies_not_used(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            stability_used=0,
            stability_fallbacks=6786,
            gap_reasons={"unstable_footprint_bounds_within_payload": 6786},
            current_scan=26.0,
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "payload_footprint_stability_not_used"


def test_payload_footprint_probe_review_classifies_unstable_still_dominant(
    tmp_path: Path,
) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            stability_used=10,
            stability_fallbacks=6000,
            gap_reasons={"unstable_footprint_bounds_within_payload": 6000},
            current_scan=25.0,
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "unstable_bounds_still_dominates"


def test_payload_footprint_probe_review_classifies_mandatory_scan_still_hot(
    tmp_path: Path,
) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            stability_used=4000,
            stability_fallbacks=100,
            gap_reasons={"legacy_scan_required_other": 100},
            current_scan=24.0,
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "mandatory_scan_still_hot"


def test_payload_footprint_probe_review_reports_missing_support_gap_instrumentation(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    instrumentation = probe["inventory"]["build_stats_summary"]["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]["signature_tightening_instrumentation"]
    instrumentation.pop("template_footprint_support_gap_reasons")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "support_gap_instrumentation_missing"
    assert review["interpretation"]["classification"] == "support_gap_instrumentation_missing"


def test_payload_footprint_probe_review_missing_timing_is_inconclusive(tmp_path: Path) -> None:
    probe = _probe_payload()
    phase_seconds = probe["inventory"]["build_stats_summary"]["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]["signature_tightening_instrumentation"]["phase_seconds"]
    phase_seconds.pop("per_anchor_mandatory_scan")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "payload_footprint_probe_inconclusive"
    assert review["interpretation"]["classification"] == "payload_footprint_probe_inconclusive"


def test_payload_footprint_probe_review_strict_safety_disqualifies(tmp_path: Path) -> None:
    probe = _probe_payload()
    probe["sensitive_path_comparison"] = {
        "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
        "changed": False,
        "changed_paths": [],
    }

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_payload_footprint_probe_review_rejects_hard_boundary_truthy_flag(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    probe["runtime_execution_performed"] = "false"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_payload_footprint_probe_review_rejects_wrong_run_id(tmp_path: Path) -> None:
    probe = _probe_payload()
    probe["run_id"] = "wrong"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_payload_footprint_probe_review_namespace_guard(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    probe = tmp_path / "probe.json"
    readiness.write_text(json.dumps(_readiness_payload()) + "\n", encoding="utf-8")
    probe.write_text(json.dumps(_probe_payload()) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="S87 probe review namespace"):
        build_signature_bucket_payload_footprint_probe_review(
            project_root=tmp_path,
            readiness_path=readiness,
            probe_path=probe,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _build_review(tmp_path: Path, probe_payload: dict[str, object]) -> dict[str, object]:
    readiness = tmp_path / "readiness.json"
    probe = tmp_path / "probe.json"
    readiness.write_text(json.dumps(_readiness_payload()) + "\n", encoding="utf-8")
    probe.write_text(json.dumps(probe_payload) + "\n", encoding="utf-8")
    return build_signature_bucket_payload_footprint_probe_review(
        project_root=tmp_path,
        readiness_path=readiness,
        probe_path=probe,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )


def _readiness_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "readiness": {
            "classification": "ready_for_payload_footprint_probe_review",
            "baseline_mandatory_scan_seconds": 27.0,
            "baseline_unstable_footprint_bounds_fallbacks": 6786,
        },
        "probe_execution_enabled": False,
        "next_probe_allowed_only_after_readiness_review": True,
    }


def _probe_payload(
    *,
    stability_used: int = 3000,
    stability_fallbacks: int = 100,
    gap_reasons: dict[str, int] | None = None,
    current_scan: float = 20.0,
) -> dict[str, object]:
    instrumentation = {
        "enabled": True,
        "phase_seconds": {"per_anchor_mandatory_scan": current_scan},
        "totals": {
            "mandatory_payload_footprint_stability_attempts": 6786,
            "mandatory_payload_footprint_stability_used": stability_used,
            "mandatory_payload_footprint_stability_fallbacks": stability_fallbacks,
            "mandatory_payload_footprint_stability_cohorts": max(stability_used * 2, 0),
        },
        "template_footprint_support_gap_reasons": (
            {"unstable_footprint_bounds_within_payload": 100}
            if gap_reasons is None
            else gap_reasons
        ),
        "top_template_footprint_gap_entries": []
        if gap_reasons == {}
        else [
            {
                "rect_idx": 1,
                "anchor": {"x": 1, "y": 2},
                "group_id_or_template": "group::a",
                "bucket_id": "sig_002",
                "reason": "unstable_footprint_bounds_within_payload",
                "pose_count": 4,
                "occupied_cell_count": 7,
                "elapsed_seconds": 0.1,
            }
        ],
        "top_payload_footprint_stability_entries": [
            {
                "rect_idx": 1,
                "anchor": {"x": 1, "y": 2},
                "group_id_or_template": "group::a",
                "bucket_id": "sig_002",
                "cohort_count": 2,
                "legacy_scan_count": 10,
                "elapsed_seconds": 0.1,
            }
        ],
    }
    payload: dict[str, object] = {
        "status": "completed",
        "run_id": EXPECTED_RUN_ID,
        "target": {"candidate_key": "42x32"},
        "execute_no_solve": True,
        "no_solve": True,
        "sensitive_path_comparison": {
            "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
            "changed": False,
            "changed_paths": [],
            "changed_entries": [],
        },
        "inventory": {
            "model_build_seconds": 32.0,
            "build_stats_summary": {
                "global_valid_inequalities": {
                    "signature_bucket_capacity_bounds": {
                        "signature_tightening_instrumentation": instrumentation
                    }
                }
            },
        },
    }
    for flag in (
        "fresh_solver_run_started",
        "main_py_executed",
        "exact_campaign_used",
        "cp_solver_solve_called",
        "checkpoint_written",
        "proof_source",
        "source_model_mutation",
        "source_mutation_performed",
        "candidate_universe_changed",
        "scheduler_integration",
        "runtime_execution_performed",
        "production_profile_changed",
    ):
        payload[flag] = False
    return payload


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "87_signature_bucket_payload_footprint_probe_review"
    )
