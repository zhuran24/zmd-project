from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_outer_overlay_subphase_probe_review import (
    EXPECTED_RUN_ID,
    build_signature_bucket_outer_overlay_subphase_probe_review,
)


def test_outer_overlay_subphase_probe_review_classifies_proto_clone_hotspot(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            outer_subphases={"model_proto_clone_bind": 3.0, "build_stats_deepcopy": 0.2},
            unattributed=0.1,
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "model_proto_clone_bind_hotspot"


def test_outer_overlay_subphase_probe_review_classifies_build_stats_deepcopy_hotspot(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            outer_subphases={"model_proto_clone_bind": 0.2, "build_stats_deepcopy": 2.5},
            unattributed=0.1,
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "build_stats_deepcopy_hotspot"


def test_outer_overlay_subphase_probe_review_classifies_unattributed_hotspot(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            outer_subphases={"model_proto_clone_bind": 0.1, "build_stats_deepcopy": 0.2},
            unattributed=4.0,
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "outer_overlay_unattributed_hotspot"


def test_outer_overlay_subphase_probe_review_classifies_search_guidance_hotspot(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            outer_subphases={"model_proto_clone_bind": 0.1},
            ghost_subphases={"search_guidance_rebuild": 3.4},
            unattributed=0.2,
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "search_guidance_rebuild_hotspot"


def test_outer_overlay_subphase_probe_review_reports_missing_instrumentation(tmp_path: Path) -> None:
    probe = _probe_payload()
    probe["inventory"]["build_stats_summary"]["exact_core_reuse"].pop("residual_overlay_instrumentation")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "subphase_instrumentation_missing"
    assert review["interpretation"]["classification"] == "subphase_instrumentation_missing"


def test_outer_overlay_subphase_probe_review_missing_numeric_fields_is_inconclusive(tmp_path: Path) -> None:
    probe = _probe_payload()
    residual = probe["inventory"]["build_stats_summary"]["exact_core_reuse"]["residual_overlay_instrumentation"]
    residual.pop("outer_exact_core_overlay_subphase_total_seconds")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "outer_overlay_subphase_probe_inconclusive"
    assert review["interpretation"]["classification"] == "outer_overlay_subphase_probe_inconclusive"


def test_outer_overlay_subphase_probe_review_strict_safety_disqualifies(tmp_path: Path) -> None:
    probe = _probe_payload()
    probe["sensitive_path_comparison"] = {
        "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
        "changed": False,
        "changed_paths": [],
    }

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_outer_overlay_subphase_probe_review_rejects_hard_boundary_truthy_flag(tmp_path: Path) -> None:
    probe = _probe_payload()
    probe["runtime_execution_performed"] = "false"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_outer_overlay_subphase_probe_review_rejects_wrong_run_id(tmp_path: Path) -> None:
    probe = _probe_payload()
    probe["run_id"] = "wrong"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_outer_overlay_subphase_probe_review_namespace_guard(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    probe = tmp_path / "probe.json"
    readiness.write_text(json.dumps(_readiness_payload()) + "\n", encoding="utf-8")
    probe.write_text(json.dumps(_probe_payload()) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="S104 probe review namespace"):
        build_signature_bucket_outer_overlay_subphase_probe_review(
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
    return build_signature_bucket_outer_overlay_subphase_probe_review(
        project_root=tmp_path,
        readiness_path=readiness,
        probe_path=probe,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )


def _readiness_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "readiness": {"classification": "ready_for_outer_overlay_subphase_probe_review"},
        "probe_execution_enabled": False,
        "next_probe_allowed_only_after_readiness_review": True,
    }


def _probe_payload(
    *,
    outer_subphases: dict[str, float] | None = None,
    ghost_subphases: dict[str, float] | None = None,
    unattributed: float = 0.3,
) -> dict[str, object]:
    if outer_subphases is None:
        outer_subphases = {"model_proto_clone_bind": 1.0, "build_stats_deepcopy": 0.5}
    if ghost_subphases is None:
        ghost_subphases = {"ghost_constraint_add": 0.1}
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
                        "profile_validation_seconds": 0.01,
                        "outer_exact_core_overlay_residual_seconds": 6.0,
                        "outer_exact_core_overlay_subphase_seconds": outer_subphases,
                        "outer_exact_core_overlay_subphase_total_seconds": sum(outer_subphases.values()),
                        "outer_exact_core_overlay_unattributed_seconds": unattributed,
                        "ghost_overlay_subphase_seconds": ghost_subphases,
                        "overlay_build_seconds": 12.0,
                        "ghost_constraint_seconds": 6.0,
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
        / "104_signature_bucket_outer_overlay_subphase_probe_review"
    )
