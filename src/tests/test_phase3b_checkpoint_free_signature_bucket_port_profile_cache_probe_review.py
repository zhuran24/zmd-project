from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_port_profile_cache_probe_review import (
    EXPECTED_RUN_ID,
    build_signature_bucket_port_profile_cache_probe_review,
)


def test_port_profile_cache_probe_review_classifies_power_pole_hotspot(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            port_profile_phases={
                "power_pole_index_build": 4.0,
                "per_template_pose_cache_build": 0.5,
            }
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "power_pole_index_hotspot"


def test_port_profile_cache_probe_review_classifies_template_pose_hotspot(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            port_profile_phases={
                "per_template_pose_cache_build": 3.5,
                "power_pole_index_build": 0.2,
            }
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "per_template_pose_cache_hotspot"


def test_port_profile_cache_probe_review_classifies_support_coverer_hotspot(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            port_profile_phases={
                "powered_support_coverer_build": 2.8,
                "local_signature_build": 0.4,
            }
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "powered_support_coverer_hotspot"


def test_port_profile_cache_probe_review_accepts_actual_s116_total_schema(
    tmp_path: Path,
) -> None:
    probe = _probe_payload(
        port_profile_phases={
            "powered_support_coverer_build": 3.0,
            "compact_capacity_signature_store": 1.0,
            "index_pools_unattributed_seconds": 0.25,
        },
        unattributed=0.25,
    )
    port_profile = probe["inventory"]["build_stats_summary"]["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]
    port_profile["total_seconds"] = 4.25
    port_profile.pop("index_pools_total_seconds")
    port_profile.pop("index_pools_subphase_total_seconds")
    port_profile.pop("index_pools_unattributed_seconds")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "powered_support_coverer_hotspot"
    assert review["subphase_summary"]["required_numeric"] == {
        "index_pools_total_seconds": 4.25,
        "index_pools_subphase_total_seconds": 4.0,
        "index_pools_unattributed_seconds": 0.25,
    }


def test_port_profile_cache_probe_review_classifies_unattributed_hotspot(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(port_profile_phases={"power_pole_index_build": 0.1}, unattributed=2.0),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "index_pools_unattributed_hotspot"


def test_port_profile_cache_probe_review_reports_missing_instrumentation(tmp_path: Path) -> None:
    probe = _probe_payload()
    residual = probe["inventory"]["build_stats_summary"]["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]
    residual.pop("port_profile_cache_instrumentation")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "port_profile_cache_instrumentation_missing"
    assert review["interpretation"]["classification"] == "port_profile_cache_instrumentation_missing"


def test_port_profile_cache_probe_review_missing_numeric_fields_is_inconclusive(tmp_path: Path) -> None:
    probe = _probe_payload()
    port_profile = probe["inventory"]["build_stats_summary"]["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]
    port_profile.pop("index_pools_total_seconds")
    port_profile.pop("index_pools_subphase_total_seconds")
    port_profile.pop("index_pools_unattributed_seconds")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "port_profile_cache_probe_inconclusive"
    assert review["interpretation"]["classification"] == "port_profile_cache_probe_inconclusive"


def test_port_profile_cache_probe_review_strict_safety_disqualifies(tmp_path: Path) -> None:
    probe = _probe_payload()
    probe["sensitive_path_comparison"] = {
        "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
        "changed": False,
        "changed_paths": [],
    }

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_port_profile_cache_probe_review_rejects_hard_boundary_truthy_flag(tmp_path: Path) -> None:
    probe = _probe_payload()
    probe["runtime_execution_performed"] = "false"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_port_profile_cache_probe_review_rejects_wrong_run_id(tmp_path: Path) -> None:
    probe = _probe_payload()
    probe["run_id"] = "wrong"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_port_profile_cache_probe_review_namespace_guard(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    probe = tmp_path / "probe.json"
    readiness.write_text(json.dumps(_readiness_payload()) + "\n", encoding="utf-8")
    probe.write_text(json.dumps(_probe_payload()) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="S118 probe review namespace"):
        build_signature_bucket_port_profile_cache_probe_review(
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
    return build_signature_bucket_port_profile_cache_probe_review(
        project_root=tmp_path,
        readiness_path=readiness,
        probe_path=probe,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )


def _readiness_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "readiness": {"classification": "ready_for_port_profile_cache_probe_review"},
        "probe_execution_enabled": False,
        "next_probe_allowed_only_after_readiness_review": True,
    }


def _probe_payload(
    *,
    port_profile_phases: dict[str, float] | None = None,
    unattributed: float = 0.1,
) -> dict[str, object]:
    if port_profile_phases is None:
        port_profile_phases = {"power_pole_index_build": 1.0, "per_template_pose_cache_build": 0.5}
    subphase_total = sum(port_profile_phases.values())
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
                            "phase_seconds": port_profile_phases,
                            "index_pools_subphase_total_seconds": subphase_total,
                            "index_pools_total_seconds": subphase_total + unattributed,
                            "index_pools_unattributed_seconds": unattributed,
                            "totals": {"template_count": 2, "pose_count": 3},
                            "top_slow_templates_or_groups": [],
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
        / "118_signature_bucket_port_profile_cache_probe_review"
    )
