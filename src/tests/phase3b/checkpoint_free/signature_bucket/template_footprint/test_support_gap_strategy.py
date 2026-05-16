from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.template_footprint.build_support_gap_strategy import (
    FUTURE_ENV_VAR,
    TARGET_CLASSIFICATION,
    build_signature_bucket_template_footprint_support_gap_strategy,
    write_signature_bucket_template_footprint_support_gap_strategy,
)


def test_template_footprint_support_gap_strategy_classifies_s75_not_used(
    tmp_path: Path,
) -> None:
    s75_path, s73_path, s71_path, agents_path, source_path = _write_inputs(tmp_path)

    strategy = build_signature_bucket_template_footprint_support_gap_strategy(
        s75_path=s75_path,
        s73_path=s73_path,
        s71_path=s71_path,
        agents_path=agents_path,
        source_path=source_path,
    )

    assert strategy["status"] == "completed"
    assert strategy["interpretation"]["classification"] == TARGET_CLASSIFICATION
    assert strategy["source_mutation_performed"] is False
    assert strategy["interpretation"]["implementation_allowed_now"] is False
    assert strategy["review_required_before_authorization"] is True
    assert strategy["future_diagnostic_spec"]["env_var"] == FUTURE_ENV_VAR
    assert "observe why template-footprint support rejects" in strategy["future_diagnostic_spec"]["enabled_scope"]
    assert strategy["evidence_summary"]["template_footprint_support_attempts"] == 21489
    assert strategy["evidence_summary"]["template_footprint_support_used"] == 0
    assert strategy["evidence_summary"]["unsupported_footprint_fallbacks"] == 6786


def test_template_footprint_support_gap_strategy_requires_zero_support_used(
    tmp_path: Path,
) -> None:
    s75_path, s73_path, s71_path, agents_path, source_path = _write_inputs(tmp_path)
    s73 = json.loads(s73_path.read_text(encoding="utf-8"))
    s73["interpretation"]["template_footprint_support_used"] = 12
    s73["signature_instrumentation"]["totals"]["mandatory_template_footprint_support_used"] = 12
    s73_path.write_text(json.dumps(s73) + "\n", encoding="utf-8")

    strategy = build_signature_bucket_template_footprint_support_gap_strategy(
        s75_path=s75_path,
        s73_path=s73_path,
        s71_path=s71_path,
        agents_path=agents_path,
        source_path=source_path,
    )

    assert strategy["status"] == "manual_review_required"
    failed_checks = {
        check["name"]
        for check in strategy["input_checks"]
        if check["status"] == "failed"
    }
    assert "template_support_attempted_but_never_used" in failed_checks


def test_template_footprint_support_gap_strategy_dirty_safety_requires_manual_review(
    tmp_path: Path,
) -> None:
    s75_path, s73_path, s71_path, agents_path, source_path = _write_inputs(tmp_path)
    s75 = json.loads(s75_path.read_text(encoding="utf-8"))
    s75["safety"]["runtime_execution_performed"] = True
    s75_path.write_text(json.dumps(s75) + "\n", encoding="utf-8")

    strategy = build_signature_bucket_template_footprint_support_gap_strategy(
        s75_path=s75_path,
        s73_path=s73_path,
        s71_path=s71_path,
        agents_path=agents_path,
        source_path=source_path,
    )

    assert strategy["status"] == "manual_review_required"
    failed_checks = {
        check["name"]
        for check in strategy["input_checks"]
        if check["status"] == "failed"
    }
    assert "s75_safety_clean" in failed_checks


def test_template_footprint_support_gap_strategy_write_and_namespace_guard(
    tmp_path: Path,
) -> None:
    s75_path, s73_path, s71_path, agents_path, source_path = _write_inputs(tmp_path)
    strategy = build_signature_bucket_template_footprint_support_gap_strategy(
        s75_path=s75_path,
        s73_path=s73_path,
        s71_path=s71_path,
        agents_path=agents_path,
        source_path=source_path,
    )
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "76_signature_bucket_template_footprint_support_gap_strategy"
    )

    paths = write_signature_bucket_template_footprint_support_gap_strategy(
        strategy,
        output_dir,
    )

    assert paths["json"].is_file()
    assert paths["md"].is_file()
    assert json.loads(paths["json"].read_text(encoding="utf-8"))["status"] == "completed"
    with pytest.raises(ValueError, match="S76 template-footprint support gap strategy namespace"):
        write_signature_bucket_template_footprint_support_gap_strategy(strategy, tmp_path / "bad")


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    s75_path = tmp_path / "s75.json"
    s73_path = tmp_path / "s73.json"
    s71_path = tmp_path / "s71.json"
    agents_path = tmp_path / "AGENTS.md"
    source_path = tmp_path / "exact_coordinate_master.py"
    s75_path.write_text(json.dumps(_s75_payload()) + "\n", encoding="utf-8")
    s73_path.write_text(json.dumps(_s73_payload()) + "\n", encoding="utf-8")
    s71_path.write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "env_gate": {"name": "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    agents_path.write_text(
        "\n".join(
            [
                "# AGENTS",
                "- Current S75 no-solve probe state: template_footprint_support_not_used.",
                "- Next gate is a review-first support-gap strategy.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    source_path.write_text(
        "\n".join(
            [
                "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT = '1'",
                "mandatory_template_footprint_support_attempts = 0",
                "mandatory_template_footprint_support_used = 0",
                "unsupported_or_missing_template_footprint = 0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return s75_path, s73_path, s71_path, agents_path, source_path


def _s75_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "s73_status": "completed",
        "s73_classification": "template_footprint_support_not_used",
        "run_id": "local_hotspot_42x32_signature_bucket_template_footprint_inst_no_solve_001",
        "probe_output": "overlay_timing_probe.json",
        "review_output": "signature_bucket_template_footprint_probe_review.json",
        "model_build_seconds": 38.9,
        "interpretation": {
            "template_footprint_support_attempts": 21489,
            "template_footprint_support_used": 0,
            "template_footprint_support_fallbacks": 6786,
            "fallback_reasons": {"unsupported_or_missing_template_footprint": 6786},
            "baseline_mandatory_scan_seconds": 27.097,
            "current_mandatory_scan_seconds": 27.088,
            "mandatory_scan_reduction_ratio": 0.0003,
            "unsupported_footprint_reduction_ratio": 0.0,
            "next_engineering_step": "review_template_footprint_support_coverage_or_fixture_gap",
        },
        "safety": _safety_payload(),
    }


def _s73_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "interpretation": {
            "classification": "template_footprint_support_not_used",
            "baseline_mandatory_scan_seconds": 27.097,
            "current_mandatory_scan_seconds": 27.088,
            "mandatory_scan_reduction_ratio": 0.0003,
            "baseline_unsupported_footprint_fallbacks": 6786,
            "current_unsupported_footprint_fallbacks": 6786,
            "unsupported_footprint_reduction_ratio": 0.0,
            "template_footprint_support_attempts": 21489,
            "template_footprint_support_used": 0,
            "template_footprint_support_fallbacks": 6786,
        },
        "signature_instrumentation": {
            "present": True,
            "fallback_reason_visibility": "fallback_reason_instrumentation_visible",
            "phase_seconds": {"per_anchor_mandatory_scan": 27.088},
            "totals": {
                "mandatory_template_footprint_support_attempts": 21489,
                "mandatory_template_footprint_support_used": 0,
                "mandatory_template_footprint_support_fallbacks": 6786,
            },
            "fallback_reasons": {"unsupported_or_missing_template_footprint": 6786},
            "top_fallback_entries": [],
        },
        "probe_safety": {
            "status_completed": True,
            "run_id_matches": True,
            "candidate_key_42x32": True,
            "execute_no_solve": True,
            "hard_boundary_flags_literal_false": True,
            "actual_flags": {key: False for key in _HARD_BOUNDARY_FLAGS},
            "sensitive_path_comparison": {
                "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
                "changed": False,
                "changed_paths": [],
                "changed_entries": [],
            },
        },
    }


def _safety_payload() -> dict[str, object]:
    safety = {key: False for key in _HARD_BOUNDARY_FLAGS}
    safety.update(
        {
            "execute_no_solve": True,
            "sensitive_path_changed": False,
            "canonical_checkpoint_state_exists": False,
            "canonical_checkpoint_telemetry_exists": False,
        }
    )
    return safety


_HARD_BOUNDARY_FLAGS = (
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
)
