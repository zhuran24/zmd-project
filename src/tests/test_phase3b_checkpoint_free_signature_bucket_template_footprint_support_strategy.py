from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_template_footprint_support_strategy import (
    ENV_VAR,
    TARGET_CLASSIFICATION,
    build_signature_bucket_template_footprint_support_strategy,
    write_signature_bucket_template_footprint_support_strategy,
)


def test_template_footprint_support_strategy_classifies_s68_unsupported_footprint(
    tmp_path: Path,
) -> None:
    s68_path, s64_path, agents_path, source_path = _write_inputs(tmp_path)

    strategy = build_signature_bucket_template_footprint_support_strategy(
        s68_path=s68_path,
        s64_path=s64_path,
        agents_path=agents_path,
        source_path=source_path,
    )

    assert strategy["status"] == "completed"
    assert strategy["interpretation"]["classification"] == TARGET_CLASSIFICATION
    assert strategy["source_mutation_performed"] is False
    assert strategy["interpretation"]["implementation_allowed_now"] is False
    assert strategy["review_required_before_authorization"] is True
    assert strategy["future_patch_spec"]["env_var"] == ENV_VAR
    assert "legacy pose-footprint" in strategy["future_patch_spec"]["exactness_contract"]
    assert strategy["evidence_summary"]["dominant_reason"] == (
        "unsupported_or_missing_template_footprint"
    )
    assert strategy["evidence_summary"]["fallback_reason_total"] == 6786


def test_template_footprint_support_strategy_requires_visible_dominant_reason(
    tmp_path: Path,
) -> None:
    s68_path, s64_path, agents_path, source_path = _write_inputs(tmp_path)
    s64 = json.loads(s64_path.read_text(encoding="utf-8"))
    s64["signature_instrumentation"]["fallback_reasons"] = {
        "legacy_scan_required_other": 6786
    }
    s64_path.write_text(json.dumps(s64) + "\n", encoding="utf-8")

    strategy = build_signature_bucket_template_footprint_support_strategy(
        s68_path=s68_path,
        s64_path=s64_path,
        agents_path=agents_path,
        source_path=source_path,
    )

    assert strategy["status"] == "manual_review_required"
    failed_checks = {
        check["name"]
        for check in strategy["input_checks"]
        if check["status"] == "failed"
    }
    assert "fallback_reasons_visible_and_dominant" in failed_checks


def test_template_footprint_support_strategy_dirty_safety_requires_manual_review(
    tmp_path: Path,
) -> None:
    s68_path, s64_path, agents_path, source_path = _write_inputs(tmp_path)
    s68 = json.loads(s68_path.read_text(encoding="utf-8"))
    s68["safety"]["runtime_execution_performed"] = True
    s68_path.write_text(json.dumps(s68) + "\n", encoding="utf-8")

    strategy = build_signature_bucket_template_footprint_support_strategy(
        s68_path=s68_path,
        s64_path=s64_path,
        agents_path=agents_path,
        source_path=source_path,
    )

    assert strategy["status"] == "manual_review_required"
    failed_checks = {
        check["name"]
        for check in strategy["input_checks"]
        if check["status"] == "failed"
    }
    assert "s68_safety_clean" in failed_checks


def test_template_footprint_support_strategy_write_and_namespace_guard(
    tmp_path: Path,
) -> None:
    s68_path, s64_path, agents_path, source_path = _write_inputs(tmp_path)
    strategy = build_signature_bucket_template_footprint_support_strategy(
        s68_path=s68_path,
        s64_path=s64_path,
        agents_path=agents_path,
        source_path=source_path,
    )

    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "69_signature_bucket_template_footprint_support_strategy"
    )
    paths = write_signature_bucket_template_footprint_support_strategy(
        strategy,
        output_dir,
    )

    assert paths["json"].is_file()
    assert paths["md"].is_file()
    assert json.loads(paths["json"].read_text(encoding="utf-8"))["status"] == "completed"
    with pytest.raises(ValueError, match="S69 template-footprint support strategy namespace"):
        write_signature_bucket_template_footprint_support_strategy(strategy, tmp_path / "bad")


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    s68_path = tmp_path / "s68.json"
    s64_path = tmp_path / "s64.json"
    agents_path = tmp_path / "AGENTS.md"
    source_path = tmp_path / "exact_coordinate_master.py"
    s68_path.write_text(json.dumps(_s68_payload()) + "\n", encoding="utf-8")
    s64_path.write_text(json.dumps(_s64_payload()) + "\n", encoding="utf-8")
    agents_path.write_text(
        "\n".join(
            [
                "# AGENTS",
                "- Current S68 fallback-reason no-solve probe result: unsupported_footprint_dominates.",
                "- Next gate is a review-first template-footprint support strategy.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    source_path.write_text(
        "\n".join(
            [
                "def _pose_has_template_rect_footprint(self):",
                "    return False",
                "def _mandatory_region_counting_payload(self):",
                "    return {'reason': 'unsupported_pose_footprint'}",
                "def _mandatory_region_blocked_counts_for_domain(self):",
                "    return {}",
                "def _fallback_reason_category(reason):",
                "    return 'unsupported_or_missing_template_footprint'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return s68_path, s64_path, agents_path, source_path


def _s68_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "probe": {
            "run_id": "local_hotspot_42x32_signature_bucket_fallback_reason_inst_no_solve_001",
            "overlay_timing_probe_json": "probe.json",
            "model_build_seconds": 38.14,
            "signature_bucket_tightening_seconds": 28.78,
        },
        "safety": {
            "execute_no_solve": True,
            "no_solve": True,
            "fresh_solver_run_started": False,
            "cp_solver_solve_called": False,
            "runtime_execution_performed": False,
            "main_py_executed": False,
            "exact_campaign_used": False,
            "checkpoint_written": False,
            "proof_source": False,
            "source_model_mutation": False,
            "source_mutation_performed": False,
            "candidate_universe_changed": False,
            "scheduler_integration": False,
            "production_profile_changed": False,
            "sensitive_path_comparison_changed": False,
            "sensitive_path_schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
            "changed_paths": [],
            "changed_entries": [],
            "canonical_checkpoint_state_exists_after": False,
            "canonical_checkpoint_telemetry_exists_after": False,
        },
        "s64_review": {
            "status": "completed",
            "classification": "unsupported_footprint_dominates",
            "dominant_reason": "unsupported_or_missing_template_footprint",
            "dominant_reason_count": 6786,
            "dominant_reason_ratio": 1.0,
            "fallback_reason_total": 6786,
            "mandatory_scan_seconds": 27.09,
            "mandatory_region_counting_attempts": 21489,
            "mandatory_region_counting_used": 14703,
            "mandatory_region_counting_fallbacks": 6786,
            "next_engineering_step": "prepare_template_footprint_support_strategy_or_review",
        },
        "next_gate": "prepare_template_footprint_support_strategy_or_review",
    }


def _s64_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "interpretation": {
            "classification": "unsupported_footprint_dominates",
            "dominant_reason": "unsupported_or_missing_template_footprint",
            "dominant_reason_count": 6786,
            "dominant_reason_ratio": 1.0,
            "fallback_reason_total": 6786,
            "mandatory_scan_seconds": 27.097,
        },
        "signature_instrumentation": {
            "present": True,
            "fallback_reason_visibility": "fallback_reason_instrumentation_visible",
            "phase_seconds": {"per_anchor_mandatory_scan": 27.097},
            "totals": {
                "mandatory_region_counting_attempts": 21489,
                "mandatory_region_counting_used": 14703,
                "mandatory_region_counting_fallbacks": 6786,
                "required_optional_payload_count": 0,
            },
            "fallback_reasons": {"unsupported_or_missing_template_footprint": 6786},
            "top_fallback_entries": [
                {
                    "rect_idx": 1058,
                    "anchor": {"x": 27, "y": 5},
                    "group_id_or_template": "group::manufacturing_6x4::filling_capsule::13",
                    "bucket_id": "__all__",
                    "reason": "unsupported_or_missing_template_footprint",
                    "legacy_scan_count": 1344,
                    "legacy_pose_hits": 124160,
                    "elapsed_seconds": 0.008,
                }
            ],
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
                "source_mutation_performed": False,
                "candidate_universe_changed": False,
                "scheduler_integration": False,
                "runtime_execution_performed": False,
                "production_profile_changed": False,
            },
            "sensitive_path_comparison": {
                "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
                "changed": False,
                "changed_paths": [],
                "changed_entries": [],
            },
        },
    }
