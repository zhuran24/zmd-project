from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_residual_overlay_probe_review import (
    EXPECTED_RUN_ID,
    build_signature_bucket_residual_overlay_probe_review,
)


def test_residual_overlay_probe_review_classifies_payload_metadata_hotspot(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            signature_phases={"payload_region_metadata_build_seconds": 3.0},
            residual_phases={"residual_signature_scan_seconds": 0.2},
            outer_seconds=0.1,
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "payload_region_metadata_hotspot"


def test_residual_overlay_probe_review_classifies_residual_scan_hotspot(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            signature_phases={"payload_region_metadata_build_seconds": 0.2},
            residual_phases={"residual_signature_scan_seconds": 2.5},
            outer_seconds=0.1,
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "residual_signature_scan_hotspot"


def test_residual_overlay_probe_review_classifies_outer_residual_hotspot(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            signature_phases={"payload_region_metadata_build_seconds": 0.2},
            residual_phases={"residual_signature_scan_seconds": 0.1},
            outer_seconds=4.0,
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "outer_exact_core_overlay_residual_hotspot"


def test_residual_overlay_probe_review_reports_missing_instrumentation(tmp_path: Path) -> None:
    probe = _probe_payload()
    gvi = probe["inventory"]["build_stats_summary"]["global_valid_inequalities"]
    gvi["signature_bucket_capacity_bounds"]["signature_tightening_instrumentation"].pop(
        "residual_overlay_instrumentation"
    )

    review = _build_review(tmp_path, probe)

    assert review["status"] == "residual_overlay_instrumentation_missing"
    assert review["interpretation"]["classification"] == "residual_overlay_instrumentation_missing"


def test_residual_overlay_probe_review_missing_numeric_timing_is_inconclusive(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(signature_phases={}, residual_phases={}, outer_seconds=None),
    )

    assert review["status"] == "residual_overlay_probe_inconclusive"
    assert review["interpretation"]["classification"] == "residual_overlay_probe_inconclusive"


def test_residual_overlay_probe_review_strict_safety_disqualifies(tmp_path: Path) -> None:
    probe = _probe_payload()
    probe["sensitive_path_comparison"] = {
        "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
        "changed": False,
        "changed_paths": [],
    }

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_residual_overlay_probe_review_rejects_hard_boundary_truthy_flag(tmp_path: Path) -> None:
    probe = _probe_payload()
    probe["runtime_execution_performed"] = "false"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_residual_overlay_probe_review_rejects_wrong_run_id(tmp_path: Path) -> None:
    probe = _probe_payload()
    probe["run_id"] = "wrong"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_residual_overlay_probe_review_namespace_guard(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    probe = tmp_path / "probe.json"
    readiness.write_text(json.dumps(_readiness_payload()) + "\n", encoding="utf-8")
    probe.write_text(json.dumps(_probe_payload()) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="S97 probe review namespace"):
        build_signature_bucket_residual_overlay_probe_review(
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
    return build_signature_bucket_residual_overlay_probe_review(
        project_root=tmp_path,
        readiness_path=readiness,
        probe_path=probe,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )


def _readiness_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "readiness": {"classification": "ready_for_residual_overlay_probe_review"},
        "probe_execution_enabled": False,
        "next_probe_allowed_only_after_readiness_review": True,
    }


def _probe_payload(
    *,
    signature_phases: dict[str, float] | None = None,
    residual_phases: dict[str, float] | None = None,
    outer_seconds: float | None = 0.3,
) -> dict[str, object]:
    if signature_phases is None:
        signature_phases = {"payload_region_metadata_build_seconds": 1.0}
    if residual_phases is None:
        residual_phases = {"residual_signature_scan_seconds": 0.5}
    exact_core_reuse: dict[str, object] = {}
    if outer_seconds is not None:
        exact_core_reuse["residual_overlay_instrumentation"] = {
            "outer_exact_core_overlay_residual_seconds": outer_seconds,
            "overlay_build_seconds": 10.0,
            "ghost_constraint_seconds": 8.0,
        }
    else:
        exact_core_reuse["residual_overlay_instrumentation"] = {"enabled": True}
    return {
        "status": "completed",
        "run_id": EXPECTED_RUN_ID,
        "target": {"candidate_key": "42x32"},
        "execute_no_solve": True,
        "no_solve": True,
        "fresh_solver_run_started": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "checkpoint_written": False,
        "proof_source": False,
        "source_model_mutation": False,
        "source_mutation_performed": False,
        "candidate_universe_changed": False,
        "scheduler_integration": False,
        "runtime_execution_performed": False,
        "production_profile_changed": False,
        "sensitive_path_comparison": {
            "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
            "changed": False,
            "changed_paths": [],
            "changed_entries": [],
        },
        "inventory": {
            "model_build_seconds": 12.0,
            "build_stats_summary": {
                "exact_core_reuse": exact_core_reuse,
                "global_valid_inequalities": {
                    "signature_bucket_capacity_bounds": {
                        "signature_tightening_instrumentation": {
                            "residual_overlay_instrumentation": {
                                "enabled": True,
                                "phase_seconds": signature_phases,
                                "top_slow_payload_groups": [],
                            }
                        }
                    },
                    "residual_signature_bucket_capacity_bounds": {
                        "residual_overlay_instrumentation": {
                            "enabled": True,
                            "phase_seconds": residual_phases,
                            "top_slow_residual_signature_entries": [],
                        }
                    },
                },
            },
        },
    }


def _output_dir(tmp_path: Path) -> Path:
    return (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "97_signature_bucket_residual_overlay_probe_review"
    )
