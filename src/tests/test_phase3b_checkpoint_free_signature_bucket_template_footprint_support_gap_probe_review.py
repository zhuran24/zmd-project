from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_template_footprint_support_gap_probe_review import (
    EXPECTED_RUN_ID,
    build_signature_bucket_template_footprint_support_gap_probe_review,
)


def test_support_gap_probe_review_classifies_dominant_non_rectangular_reason(
    tmp_path: Path,
) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            gap_reasons={
                "non_rectangular_occupied_cells": 80,
                "missing_template_or_group_metadata": 20,
            }
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "non_rectangular_occupied_cells_dominates"
    assert review["interpretation"]["dominant_gap_reason"] == "non_rectangular_occupied_cells"


def test_support_gap_probe_review_reports_missing_instrumentation(tmp_path: Path) -> None:
    probe = _probe_payload(gap_reasons={"non_rectangular_occupied_cells": 1})
    instrumentation = probe["inventory"]["build_stats_summary"]["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]["signature_tightening_instrumentation"]
    instrumentation.pop("template_footprint_support_gap_reasons")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "support_gap_instrumentation_missing"
    assert review["interpretation"]["classification"] == "support_gap_instrumentation_missing"


def test_support_gap_probe_review_missing_timing_is_inconclusive(tmp_path: Path) -> None:
    probe = _probe_payload(gap_reasons={"non_rectangular_occupied_cells": 10})
    phase_seconds = probe["inventory"]["build_stats_summary"]["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]["signature_tightening_instrumentation"]["phase_seconds"]
    phase_seconds.pop("per_anchor_mandatory_scan")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "support_gap_probe_inconclusive"
    assert review["interpretation"]["classification"] == "support_gap_probe_inconclusive"


def test_support_gap_probe_review_strict_safety_disqualifies(tmp_path: Path) -> None:
    probe = _probe_payload(gap_reasons={"non_rectangular_occupied_cells": 10})
    probe["sensitive_path_comparison"] = {
        "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
        "changed": False,
        "changed_paths": [],
    }

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_support_gap_probe_review_rejects_hard_boundary_truthy_flag(tmp_path: Path) -> None:
    probe = _probe_payload(gap_reasons={"non_rectangular_occupied_cells": 10})
    probe["runtime_execution_performed"] = "false"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_support_gap_probe_review_namespace_guard(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    probe = tmp_path / "probe.json"
    readiness.write_text(json.dumps(_readiness_payload()) + "\n", encoding="utf-8")
    probe.write_text(json.dumps(_probe_payload()) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="S80 probe review namespace"):
        build_signature_bucket_template_footprint_support_gap_probe_review(
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
    return build_signature_bucket_template_footprint_support_gap_probe_review(
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
            "classification": "ready_for_support_gap_probe_review",
            "baseline_mandatory_scan_seconds": 27.0,
        },
        "probe_execution_enabled": False,
        "next_probe_allowed_only_after_readiness_review": True,
    }


def _probe_payload(gap_reasons: dict[str, int] | None = None) -> dict[str, object]:
    instrumentation = {
        "enabled": True,
        "phase_seconds": {"per_anchor_mandatory_scan": 25.0},
        "totals": {
            "mandatory_template_footprint_support_attempts": 100,
            "mandatory_template_footprint_support_used": 0,
            "mandatory_template_footprint_support_fallbacks": 100,
        },
        "template_footprint_support_gap_reasons": gap_reasons
        or {"non_rectangular_occupied_cells": 10},
        "top_template_footprint_gap_entries": [
            {
                "rect_idx": 1,
                "anchor": {"x": 1, "y": 2},
                "group_id_or_template": "group::a",
                "bucket_id": "__all__",
                "reason": "non_rectangular_occupied_cells",
                "pose_count": 4,
                "occupied_cell_count": 7,
                "footprint_bounds_when_available": {"min_dx": 0, "max_dx": 2},
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
            "model_build_seconds": 36.0,
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
        / "80_signature_bucket_template_footprint_support_gap_probe_review"
    )
