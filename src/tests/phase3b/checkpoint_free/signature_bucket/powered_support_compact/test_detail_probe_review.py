from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.powered_support_compact.build_detail_probe_review import (
    EXPECTED_RUN_ID,
    build_signature_bucket_powered_support_compact_item_detail_probe_review,
)


def test_powered_support_compact_item_detail_probe_review_classifies_key_build_hotspot(
    tmp_path: Path,
) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            detail_phases={
                "compact_item_key_build": 2.5,
                "local_counter_update": 0.7,
                "merge_fanout": 0.2,
                "compact_signature_storage": 0.4,
                "stats_finalize": 0.0,
            }
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "compact_item_key_build_hotspot"
    assert review["interpretation"]["dominant_phase"] == "compact_item_key_build"


def test_powered_support_compact_item_detail_probe_review_classifies_local_update_hotspot(
    tmp_path: Path,
) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            detail_phases={
                "compact_item_key_build": 0.3,
                "local_counter_update": 2.4,
                "merge_fanout": 0.4,
                "compact_signature_storage": 0.2,
                "stats_finalize": 0.0,
            }
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "local_counter_update_hotspot"
    assert review["interpretation"]["dominant_phase"] == "local_counter_update"


def test_powered_support_compact_item_detail_probe_review_classifies_merge_hotspot(
    tmp_path: Path,
) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            detail_phases={
                "compact_item_key_build": 0.3,
                "local_counter_update": 0.4,
                "merge_fanout": 2.3,
                "compact_signature_storage": 0.2,
                "stats_finalize": 0.0,
            }
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "merge_fanout_hotspot"
    assert review["interpretation"]["dominant_phase"] == "merge_fanout"


def test_powered_support_compact_item_detail_probe_review_classifies_storage_hotspot(
    tmp_path: Path,
) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            detail_phases={
                "compact_item_key_build": 0.3,
                "local_counter_update": 0.4,
                "merge_fanout": 0.2,
                "compact_signature_storage": 2.3,
                "stats_finalize": 0.0,
            }
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "compact_signature_storage_hotspot"
    assert review["interpretation"]["dominant_phase"] == "compact_signature_storage"


def test_powered_support_compact_item_detail_probe_review_classifies_duplicate_compression_absent(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    detail = _detail_payload(probe)
    detail["duplicate_compression"]["unique_to_local_ratio"] = 1.0
    detail["duplicate_compression"]["merge_to_local_ratio"] = 1.0

    review = _build_review(tmp_path, probe)

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "duplicate_compression_absent"


def test_powered_support_compact_item_detail_probe_review_reports_missing_detail_instrumentation(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    coverer = probe["inventory"]["build_stats_summary"]["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]["powered_support_coverer_instrumentation"]
    coverer.pop("compact_item_detail_instrumentation")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "compact_item_detail_instrumentation_missing"
    assert (
        review["interpretation"]["classification"]
        == "compact_item_detail_instrumentation_missing"
    )


def test_powered_support_compact_item_detail_probe_review_missing_phase_is_inconclusive(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    _detail_payload(probe)["phase_seconds"].pop("merge_fanout")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "powered_support_compact_item_detail_probe_inconclusive"
    assert (
        review["interpretation"]["classification"]
        == "powered_support_compact_item_detail_probe_inconclusive"
    )


def test_powered_support_compact_item_detail_probe_review_strict_safety_disqualifies(
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


def test_powered_support_compact_item_detail_probe_review_rejects_hard_boundary_truthy_flag(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    probe["runtime_execution_performed"] = "false"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_powered_support_compact_item_detail_probe_review_rejects_wrong_run_id(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    probe["run_id"] = "wrong"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_powered_support_compact_item_detail_probe_review_namespace_guard(
    tmp_path: Path,
) -> None:
    readiness = tmp_path / "readiness.json"
    probe = tmp_path / "probe.json"
    readiness.write_text(json.dumps(_readiness_payload()) + "\n", encoding="utf-8")
    probe.write_text(json.dumps(_probe_payload()) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="S146 probe review namespace"):
        build_signature_bucket_powered_support_compact_item_detail_probe_review(
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
    return build_signature_bucket_powered_support_compact_item_detail_probe_review(
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
            "classification": "ready_for_powered_support_compact_item_detail_probe_review",
            "s140_current_compact_item_seconds": 1.9,
            "s140_phase_seconds": {
                "compact_item_accumulation": 1.9,
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
    detail_phases: dict[str, float] | None = None,
) -> dict[str, object]:
    if detail_phases is None:
        detail_phases = {
            "compact_item_key_build": 0.6,
            "local_counter_update": 0.7,
            "merge_fanout": 0.4,
            "compact_signature_storage": 0.2,
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
                                "phase_seconds": {
                                    "coverer_union_collection": 0.3,
                                    "disjoint_filtering": 0.2,
                                    "power_index_expansion": 0.1,
                                    "compact_item_accumulation": 1.9,
                                    "stats_finalize": 0.0,
                                },
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
                                    "compact_item_batched_counter_merge_update_count": 6,
                                    "compact_item_batched_counter_unique_item_count": 6,
                                },
                                "top_slow_groups": [],
                                "compact_item_detail_instrumentation": {
                                    "enabled": True,
                                    "phase_seconds": detail_phases,
                                    "totals": {
                                        "group_count": 3,
                                        "key_build_count": 10,
                                        "local_counter_update_count": 10,
                                        "merge_update_count": 6,
                                        "unique_item_count": 6,
                                        "signature_storage_item_count": 18,
                                    },
                                    "per_template": [
                                        {
                                            "template": "powered_machine",
                                            "group_count": 3,
                                            "key_build_count": 10,
                                            "local_counter_update_count": 10,
                                            "merge_update_count": 6,
                                            "unique_item_count": 6,
                                            "signature_storage_item_count": 18,
                                        }
                                    ],
                                    "top_slow_groups": [],
                                    "duplicate_compression": {
                                        "local_update_count": 10,
                                        "unique_item_count": 6,
                                        "merge_update_count": 6,
                                        "duplicate_update_count": 4,
                                        "unique_to_local_ratio": 0.6,
                                        "merge_to_local_ratio": 0.6,
                                    },
                                },
                            },
                        },
                    }
                }
            },
        },
    }


def _detail_payload(probe: dict[str, object]) -> dict[str, object]:
    return probe["inventory"]["build_stats_summary"]["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]["powered_support_coverer_instrumentation"][
        "compact_item_detail_instrumentation"
    ]


def _output_dir(tmp_path: Path) -> Path:
    return (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "146_signature_bucket_powered_support_compact_item_detail_probe_review"
    )
