from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.mandatory_region.build_mandatory_scan_strategy import (
    ENV_VAR,
    TARGET_CLASSIFICATION,
    build_signature_bucket_mandatory_scan_strategy,
    write_signature_bucket_mandatory_scan_strategy,
)


def test_mandatory_scan_strategy_classifies_s48_hotspot(tmp_path: Path) -> None:
    s46_path, s48_path, agents_path, source_path = _write_inputs(tmp_path)

    strategy = build_signature_bucket_mandatory_scan_strategy(
        s46_path=s46_path,
        s48_path=s48_path,
        agents_path=agents_path,
        source_path=source_path,
    )

    assert strategy["status"] == "completed"
    assert strategy["interpretation"]["classification"] == TARGET_CLASSIFICATION
    assert strategy["source_mutation_performed"] is False
    assert strategy["interpretation"]["implementation_allowed_now"] is False
    assert strategy["review_required_before_authorization"] is True
    assert strategy["future_patch_spec"]["env_var"] == ENV_VAR
    assert "fallback to the legacy" in strategy["future_patch_spec"]["fallback_contract"]
    assert "_apply_ghost_anchor_signature_bucket_tightening" in strategy["future_patch_spec"]["target_method"]
    assert any(
        "ModelProto" in item
        for item in strategy["future_patch_spec"]["default_off_contract"]
    )


def test_mandatory_scan_strategy_dirty_safety_requires_manual_review(tmp_path: Path) -> None:
    s46_path, s48_path, agents_path, source_path = _write_inputs(tmp_path)
    s48 = json.loads(s48_path.read_text(encoding="utf-8"))
    s48["probe_safety"]["actual_flags"]["cp_solver_solve_called"] = True
    s48_path.write_text(json.dumps(s48) + "\n", encoding="utf-8")

    strategy = build_signature_bucket_mandatory_scan_strategy(
        s46_path=s46_path,
        s48_path=s48_path,
        agents_path=agents_path,
        source_path=source_path,
    )

    assert strategy["status"] == "manual_review_required"
    assert strategy["interpretation"]["classification"] == "manual_review_required"
    failed_checks = {
        check["name"]
        for check in strategy["input_checks"]
        if check["status"] == "failed"
    }
    assert "s48_safety_clean" in failed_checks


def test_mandatory_scan_strategy_missing_region_source_requires_manual_review(
    tmp_path: Path,
) -> None:
    s46_path, s48_path, agents_path, source_path = _write_inputs(tmp_path)
    source_path.write_text("class Other: pass\n", encoding="utf-8")

    strategy = build_signature_bucket_mandatory_scan_strategy(
        s46_path=s46_path,
        s48_path=s48_path,
        agents_path=agents_path,
        source_path=source_path,
    )

    assert strategy["status"] == "manual_review_required"
    failed_checks = {
        check["name"]
        for check in strategy["input_checks"]
        if check["status"] == "failed"
    }
    assert "source_has_region_metadata_and_legacy_scan" in failed_checks


def test_mandatory_scan_strategy_write_and_namespace_guard(tmp_path: Path) -> None:
    s46_path, s48_path, agents_path, source_path = _write_inputs(tmp_path)
    strategy = build_signature_bucket_mandatory_scan_strategy(
        s46_path=s46_path,
        s48_path=s48_path,
        agents_path=agents_path,
        source_path=source_path,
    )

    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "49_signature_bucket_mandatory_scan_strategy"
    )
    paths = write_signature_bucket_mandatory_scan_strategy(strategy, output_dir)

    assert paths["json"].is_file()
    assert paths["md"].is_file()
    assert json.loads(paths["json"].read_text(encoding="utf-8"))["status"] == "completed"
    with pytest.raises(ValueError, match="S49 mandatory scan strategy namespace"):
        write_signature_bucket_mandatory_scan_strategy(strategy, tmp_path / "bad")


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    s46_path = tmp_path / "s46.json"
    s48_path = tmp_path / "s48.json"
    agents_path = tmp_path / "AGENTS.md"
    source_path = tmp_path / "exact_coordinate_master.py"
    s46_path.write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "source_patch": {
                    "env_var": "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    s48_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "model_build_seconds": 77.9,
                "wrapper_timing": {
                    "ghost_signature_bucket_total_seconds": 68.4,
                },
                "signature_instrumentation": {
                    "present": True,
                    "visibility_status": "instrumentation_visible",
                    "dominant_phase": "per_anchor_mandatory_scan",
                    "dominant_phase_seconds": 68.08,
                    "dominant_phase_fraction": 0.996,
                    "phase_seconds": {
                        "mandatory_payload_build": 0.23,
                        "required_optional_payload_build": 0.0,
                        "per_anchor_mandatory_scan": 68.08,
                        "per_anchor_required_optional_scan": 0.0,
                        "constraint_add": 0.002,
                        "stats_finalize": 0.0,
                    },
                    "totals": {
                        "mandatory_payload_count": 19,
                        "required_optional_payload_count": 0,
                        "mandatory_cells_scanned": 28881216,
                        "required_optional_cells_scanned": 0,
                        "mandatory_pose_hits": 1980380266,
                        "required_optional_pose_hits": 0,
                        "mandatory_unique_blocked_poses": 122364420,
                        "mandatory_bucket_reductions": 68,
                        "required_optional_bucket_reductions": 0,
                        "mandatory_constraints_added": 68,
                    },
                },
                "interpretation": {
                    "classification": "mandatory_scan_hotspot",
                    "dominant_phase": "per_anchor_mandatory_scan",
                },
                "probe_safety": {
                    "actual_flags": {
                        "fresh_solver_run_started": False,
                        "main_py_executed": False,
                        "exact_campaign_used": False,
                        "cp_solver_solve_called": False,
                        "checkpoint_written": False,
                        "proof_source": False,
                        "source_model_mutation": False,
                        "production_profile_changed": False,
                    },
                    "sensitive_path_comparison": {"changed": False},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    agents_path.write_text(
        "# AGENTS\n\n- Current S48 signature-bucket visibility probe result: classification `mandatory_scan_hotspot`.\n",
        encoding="utf-8",
    )
    source_path.write_text(
        "\n".join(
            [
                "class SignatureRegion:",
                "    pass",
                "_mandatory_group_bucket_regions = {}",
                "def _apply_ghost_anchor_signature_bucket_tightening(self):",
                "    for cell in domain.get(\"cells\", []):",
                "        blocked_pose_indices = set()",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return s46_path, s48_path, agents_path, source_path
