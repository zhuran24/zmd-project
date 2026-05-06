from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_powered_support_compact_item_batched_counter_probe_review import (
    EXPECTED_RUN_ID,
    build_signature_bucket_powered_support_compact_item_batched_counter_probe_review,
)


def test_powered_support_compact_item_batched_counter_probe_review_classifies_union_hotspot(
    tmp_path: Path,
) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            coverer_phases={
                "coverer_union_collection": 4.0,
                "disjoint_filtering": 0.5,
                "power_index_expansion": 0.1,
                "compact_item_accumulation": 1.0,
                "stats_finalize": 0.0,
            }
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "another_powered_support_subphase_hotspot"
    assert review["interpretation"]["dominant_phase"] == "coverer_union_collection"


def test_powered_support_compact_item_batched_counter_probe_review_classifies_filter_hotspot(
    tmp_path: Path,
) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            coverer_phases={
                "coverer_union_collection": 0.4,
                "disjoint_filtering": 3.5,
                "power_index_expansion": 0.1,
                "compact_item_accumulation": 1.0,
                "stats_finalize": 0.0,
            }
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "another_powered_support_subphase_hotspot"
    assert review["interpretation"]["dominant_phase"] == "disjoint_filtering"


def test_powered_support_compact_item_batched_counter_probe_review_classifies_compact_hotspot(
    tmp_path: Path,
) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            coverer_phases={
                "coverer_union_collection": 0.3,
                "disjoint_filtering": 0.2,
                "power_index_expansion": 0.1,
                "compact_item_accumulation": 2.5,
                "stats_finalize": 0.0,
            }
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "compact_item_accumulation_still_hot"


def test_powered_support_compact_item_batched_counter_probe_review_classifies_effective(
    tmp_path: Path,
) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            coverer_phases={
                "coverer_union_collection": 0.3,
                "disjoint_filtering": 0.2,
                "power_index_expansion": 0.1,
                "compact_item_accumulation": 0.4,
                "stats_finalize": 0.0,
            }
        ),
    )

    assert review["status"] == "completed"
    assert (
        review["interpretation"]["classification"]
        == "compact_item_batched_counter_effective"
    )


def test_powered_support_compact_item_batched_counter_probe_review_reports_batched_counter_not_used(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    totals = probe["inventory"]["build_stats_summary"]["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]["powered_support_coverer_instrumentation"][
        "totals"
    ]
    totals["compact_item_batched_counter_used"] = 0
    totals["compact_item_batched_counter_local_update_count"] = 0
    totals["compact_item_batched_counter_merge_update_count"] = 0

    review = _build_review(tmp_path, probe)

    assert review["status"] == "compact_item_batched_counter_not_used"
    assert (
        review["interpretation"]["classification"]
        == "compact_item_batched_counter_not_used"
    )


def test_powered_support_compact_item_batched_counter_probe_review_reports_batched_counter_missing(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    totals = probe["inventory"]["build_stats_summary"]["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]["powered_support_coverer_instrumentation"][
        "totals"
    ]
    totals.pop("compact_item_batched_counter_attempts")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "batched_counter_instrumentation_missing"
    assert (
        review["interpretation"]["classification"]
        == "batched_counter_instrumentation_missing"
    )


def test_powered_support_compact_item_batched_counter_probe_review_classifies_fallback_dominated(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    totals = probe["inventory"]["build_stats_summary"]["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]["powered_support_coverer_instrumentation"][
        "totals"
    ]
    totals["compact_item_batched_counter_fallbacks"] = 3

    review = _build_review(tmp_path, probe)

    assert review["status"] == "completed"
    assert (
        review["interpretation"]["classification"]
        == "compact_item_batched_counter_fallback_dominated"
    )


def test_powered_support_compact_item_batched_counter_probe_review_reports_missing_instrumentation(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    port_profile = probe["inventory"]["build_stats_summary"]["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]
    port_profile.pop("powered_support_coverer_instrumentation")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "batched_counter_instrumentation_missing"
    assert (
        review["interpretation"]["classification"]
        == "batched_counter_instrumentation_missing"
    )


def test_powered_support_compact_item_batched_counter_probe_review_missing_phase_is_inconclusive(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    coverer = probe["inventory"]["build_stats_summary"]["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]["powered_support_coverer_instrumentation"]
    coverer["phase_seconds"].pop("power_index_expansion")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "powered_support_compact_item_batched_counter_probe_inconclusive"
    assert (
        review["interpretation"]["classification"]
        == "powered_support_compact_item_batched_counter_probe_inconclusive"
    )


def test_powered_support_compact_item_batched_counter_probe_review_strict_safety_disqualifies(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    probe["sensitive_path_comparison"] = {
        "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
        "changed": False,
        "changed_paths": [],
    }

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_powered_support_compact_item_batched_counter_probe_review_rejects_hard_boundary_truthy_flag(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    probe["runtime_execution_performed"] = "false"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_powered_support_compact_item_batched_counter_probe_review_rejects_wrong_run_id(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    probe["run_id"] = "wrong"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_powered_support_compact_item_batched_counter_probe_review_namespace_guard(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    probe = tmp_path / "probe.json"
    readiness.write_text(json.dumps(_readiness_payload()) + "\n", encoding="utf-8")
    probe.write_text(json.dumps(_probe_payload()) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="outside artifact namespace"):
        build_signature_bucket_powered_support_compact_item_batched_counter_probe_review(
            project_root=tmp_path,
            readiness_path=readiness,
            probe_path=probe,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def test_powered_support_compact_item_batched_counter_probe_review_rejects_traversal_namespace_before_write(
    tmp_path: Path,
) -> None:
    readiness = tmp_path / "readiness.json"
    probe = tmp_path / "probe.json"
    readiness.write_text(json.dumps(_readiness_payload()) + "\n", encoding="utf-8")
    probe.write_text(json.dumps(_probe_payload()) + "\n", encoding="utf-8")
    bad_output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "140_signature_bucket_powered_support_compact_item_batched_counter_probe_review"
        / ".."
        / ".."
        / ".."
        / "data"
        / "checkpoints"
    )

    with pytest.raises(ValueError, match="outside artifact namespace"):
        build_signature_bucket_powered_support_compact_item_batched_counter_probe_review(
            project_root=tmp_path,
            readiness_path=readiness,
            probe_path=probe,
            output_dir=bad_output_dir,
        )

    assert not (tmp_path / "data" / "checkpoints").exists()


def _build_review(tmp_path: Path, probe_payload: dict[str, object]) -> dict[str, object]:
    readiness = tmp_path / "readiness.json"
    probe = tmp_path / "probe.json"
    readiness.write_text(json.dumps(_readiness_payload()) + "\n", encoding="utf-8")
    probe.write_text(json.dumps(probe_payload) + "\n", encoding="utf-8")
    return build_signature_bucket_powered_support_compact_item_batched_counter_probe_review(
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
            "classification": "ready_for_powered_support_compact_item_batched_counter_probe_review",
            "s133_current_compact_item_seconds": 1.2,
            "s133_phase_seconds": {
                "compact_item_accumulation": 1.2,
                "coverer_union_collection": 0.4,
                "disjoint_filtering": 0.6,
                "power_index_expansion": 0.04,
                "stats_finalize": 0.01,
            },
        },
        "probe_execution_enabled": False,
        "next_probe_allowed_only_after_readiness_review": True,
    }


def _probe_payload(
    *,
    coverer_phases: dict[str, float] | None = None,
) -> dict[str, object]:
    if coverer_phases is None:
        coverer_phases = {
            "coverer_union_collection": 1.0,
            "disjoint_filtering": 0.5,
            "power_index_expansion": 0.25,
            "compact_item_accumulation": 0.75,
            "stats_finalize": 0.0,
        }
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
                "exact_core_reuse": {
                    "residual_overlay_instrumentation": {
                        "enabled": True,
                        "port_profile_cache_instrumentation": {
                            "enabled": True,
                            "phase_seconds": {"powered_support_coverer_build": 2.5},
                            "totals": {"template_count": 2, "pose_count": 3},
                            "top_slow_templates_or_groups": [],
                            "powered_support_coverer_instrumentation": {
                                "enabled": True,
                                "phase_seconds": coverer_phases,
                                "totals": {
                                    "template_count": 2,
                                    "group_count": 3,
                                    "pose_count": 5,
                                    "compact_item_update_count": 10,
                                    "compact_item_optimization_attempts": 3,
                                    "compact_item_optimization_used": 3,
                                    "compact_item_optimization_fallbacks": 0,
                                    "compact_item_optimized_update_count": 10,
                                    "compact_item_fallback_update_count": 0,
                                    "compact_item_batched_counter_attempts": 3,
                                    "compact_item_batched_counter_used": 3,
                                    "compact_item_batched_counter_fallbacks": 0,
                                    "compact_item_batched_counter_local_update_count": 10,
                                    "compact_item_batched_counter_fallback_update_count": 0,
                                    "compact_item_batched_counter_merge_update_count": 10,
                                    "compact_item_batched_counter_unique_item_count": 6,
                                },
                                "top_slow_groups": [],
                            },
                        },
                    }
                }
            },
        },
    }


def _output_dir(tmp_path: Path) -> Path:
    return (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "140_signature_bucket_powered_support_compact_item_batched_counter_probe_review"
    )



