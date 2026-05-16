from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.model_shell.build_subphase_probe_review import (
    EXPECTED_RUN_ID,
    build_signature_bucket_model_shell_subphase_probe_review,
)


def test_model_shell_subphase_probe_review_classifies_mandatory_group_hotspot(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(model_shell_subphases={"mandatory_group_build": 4.0, "constructor_finalize": 0.2}),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "mandatory_group_build_hotspot"


def test_model_shell_subphase_probe_review_classifies_candidate_cache_hotspot(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            model_shell_subphases={
                "candidate_domain_or_pose_cache_initialization": 3.5,
                "mandatory_group_build": 0.2,
            }
        ),
    )

    assert review["status"] == "completed"
    assert (
        review["interpretation"]["classification"]
        == "candidate_domain_or_pose_cache_initialization_hotspot"
    )


def test_model_shell_subphase_probe_review_classifies_unattributed_hotspot(tmp_path: Path) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(model_shell_subphases={"mandatory_group_build": 0.1}, unattributed=2.0),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "model_shell_unattributed_hotspot"


def test_model_shell_subphase_probe_review_reports_missing_instrumentation(tmp_path: Path) -> None:
    probe = _probe_payload()
    residual = probe["inventory"]["build_stats_summary"]["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]
    residual.pop("model_shell_subphase_seconds")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "model_shell_subphase_instrumentation_missing"
    assert review["interpretation"]["classification"] == "model_shell_subphase_instrumentation_missing"


def test_model_shell_subphase_probe_review_missing_numeric_fields_is_inconclusive(tmp_path: Path) -> None:
    probe = _probe_payload()
    residual = probe["inventory"]["build_stats_summary"]["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]
    residual.pop("model_shell_subphase_total_seconds")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "model_shell_subphase_probe_inconclusive"
    assert review["interpretation"]["classification"] == "model_shell_subphase_probe_inconclusive"


def test_model_shell_subphase_probe_review_strict_safety_disqualifies(tmp_path: Path) -> None:
    probe = _probe_payload()
    probe["sensitive_path_comparison"] = {
        "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
        "changed": False,
        "changed_paths": [],
    }

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_model_shell_subphase_probe_review_rejects_hard_boundary_truthy_flag(tmp_path: Path) -> None:
    probe = _probe_payload()
    probe["runtime_execution_performed"] = "false"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_model_shell_subphase_probe_review_rejects_wrong_run_id(tmp_path: Path) -> None:
    probe = _probe_payload()
    probe["run_id"] = "wrong"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_model_shell_subphase_probe_review_namespace_guard(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    probe = tmp_path / "probe.json"
    readiness.write_text(json.dumps(_readiness_payload()) + "\n", encoding="utf-8")
    probe.write_text(json.dumps(_probe_payload()) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="S111 probe review namespace"):
        build_signature_bucket_model_shell_subphase_probe_review(
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
    return build_signature_bucket_model_shell_subphase_probe_review(
        project_root=tmp_path,
        readiness_path=readiness,
        probe_path=probe,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )


def _readiness_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "readiness": {"classification": "ready_for_model_shell_subphase_probe_review"},
        "probe_execution_enabled": False,
        "next_probe_allowed_only_after_readiness_review": True,
    }


def _probe_payload(
    *,
    model_shell_subphases: dict[str, float] | None = None,
    unattributed: float = 0.1,
) -> dict[str, object]:
    if model_shell_subphases is None:
        model_shell_subphases = {"mandatory_group_build": 1.0, "constructor_finalize": 0.5}
    subphase_total = sum(model_shell_subphases.values())
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
                        "model_shell_instrumentation_enabled": True,
                        "model_shell_subphase_seconds": model_shell_subphases,
                        "model_shell_subphase_total_seconds": subphase_total,
                        "model_shell_total_seconds": subphase_total + unattributed,
                        "model_shell_unattributed_seconds": unattributed,
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
        / "111_signature_bucket_model_shell_subphase_probe_review"
    )
