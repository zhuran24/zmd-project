from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_payload_footprint_stability_strategy import (
    DOMINANT_REASON,
    FUTURE_ENV_VAR,
    TARGET_CLASSIFICATION,
    build_signature_bucket_payload_footprint_stability_strategy,
    write_signature_bucket_payload_footprint_stability_strategy,
)


def test_payload_footprint_stability_strategy_builds_ready_artifact(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)

    strategy = build_signature_bucket_payload_footprint_stability_strategy(
        s82_path=inputs["s82"],
        s80_path=inputs["s80"],
        s81_path=inputs["s81"],
        s78_path=inputs["s78"],
        agents_path=inputs["agents"],
        source_path=inputs["source"],
    )

    assert strategy["status"] == "completed"
    assert strategy["interpretation"]["classification"] == TARGET_CLASSIFICATION
    assert strategy["review_required_before_authorization"] is True
    assert strategy["external_review_is_authorization"] is False
    assert strategy["source_mutation_performed"] is False
    assert strategy["future_patch_spec"]["env_var"] == FUTURE_ENV_VAR
    assert strategy["future_patch_spec"]["target_method"].endswith(
        "._apply_ghost_anchor_signature_bucket_tightening"
    )
    assert strategy["recommendation"]["action"] == (
        "prepare_signature_bucket_payload_footprint_stability_external_review_package"
    )

    paths = write_signature_bucket_payload_footprint_stability_strategy(
        strategy,
        _output_dir(tmp_path),
    )
    assert paths["json"].is_file()
    assert paths["md"].is_file()


def test_payload_footprint_stability_strategy_blocks_wrong_gap_reason(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    s80 = _s80_payload()
    s80["interpretation"]["dominant_gap_reason"] = "non_rectangular_occupied_cells"
    s80["signature_instrumentation"]["support_gap_reasons"] = {
        "non_rectangular_occupied_cells": 6786,
    }
    inputs["s80"].write_text(json.dumps(s80) + "\n", encoding="utf-8")

    strategy = build_signature_bucket_payload_footprint_stability_strategy(
        s82_path=inputs["s82"],
        s80_path=inputs["s80"],
        s81_path=inputs["s81"],
        s78_path=inputs["s78"],
        agents_path=inputs["agents"],
        source_path=inputs["source"],
    )

    checks = {check["name"]: check["status"] for check in strategy["input_checks"]}
    assert strategy["status"] == "manual_review_required"
    assert checks["s80_classification_unstable_bounds"] == "failed"


def test_payload_footprint_stability_strategy_blocks_dirty_safety(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    s80 = _s80_payload()
    s80["probe_safety"]["sensitive_path_comparison"]["changed_entries"] = [
        {"path": "data/checkpoints/exact_campaign_state.json"}
    ]
    inputs["s80"].write_text(json.dumps(s80) + "\n", encoding="utf-8")

    strategy = build_signature_bucket_payload_footprint_stability_strategy(
        s82_path=inputs["s82"],
        s80_path=inputs["s80"],
        s81_path=inputs["s81"],
        s78_path=inputs["s78"],
        agents_path=inputs["agents"],
        source_path=inputs["source"],
    )

    checks = {check["name"]: check["status"] for check in strategy["input_checks"]}
    assert strategy["status"] == "manual_review_required"
    assert checks["s80_safety_clean"] == "failed"


def test_payload_footprint_stability_strategy_write_namespace_guard(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    strategy = build_signature_bucket_payload_footprint_stability_strategy(
        s82_path=inputs["s82"],
        s80_path=inputs["s80"],
        s81_path=inputs["s81"],
        s78_path=inputs["s78"],
        agents_path=inputs["agents"],
        source_path=inputs["source"],
    )

    with pytest.raises(ValueError, match="S83 payload-footprint stability strategy namespace"):
        write_signature_bucket_payload_footprint_stability_strategy(strategy, tmp_path / "bad")


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    inputs = tmp_path / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    paths = {
        "s82": inputs / "s82.json",
        "s80": inputs / "s80.json",
        "s81": inputs / "s81.json",
        "s78": inputs / "s78.json",
        "agents": inputs / "AGENTS.md",
        "source": inputs / "exact_coordinate_master.py",
    }
    paths["s82"].write_text(json.dumps(_s82_payload()) + "\n", encoding="utf-8")
    paths["s80"].write_text(json.dumps(_s80_payload()) + "\n", encoding="utf-8")
    paths["s81"].write_text(json.dumps(_s81_payload()) + "\n", encoding="utf-8")
    paths["s78"].write_text(json.dumps(_s78_payload()) + "\n", encoding="utf-8")
    paths["agents"].write_text(
        "\n".join(
            [
                "## GPT Project Review Standing Authorization",
                "- Current S81/S82 support-gap probe review and execution state: "
                "S82 classified `unstable_footprint_bounds_dominates`; next gate is "
                "payload-footprint stability review-first strategy.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["source"].write_text(
        "\n".join(
            [
                "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION = '1'",
                "template_footprint_support_gap_reasons = {}",
                "unstable_footprint_bounds_within_payload = True",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return paths


def _s82_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "probe_status": "completed",
        "run_id": "local_hotspot_42x32_signature_bucket_template_footprint_support_gap_inst_no_solve_001",
        "probe_path": "overlay_timing_probe.json",
        "review_path": "signature_bucket_template_footprint_support_gap_probe_review.json",
        "s80_classification": "unstable_footprint_bounds_dominates",
        "safety": {
            "cp_solver_solve_called": False,
            "runtime_execution_performed": False,
            "main_py_executed": False,
            "exact_campaign_used": False,
            "checkpoint_written": False,
            "proof_source": False,
            "sensitive_path_comparison": {
                "changed": False,
                "changed_paths": [],
                "changed_entries": [],
            },
        },
    }


def _s80_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "model_build_seconds": 37.5,
        "interpretation": {
            "classification": "unstable_footprint_bounds_dominates",
            "baseline_mandatory_scan_seconds": 27.088005699990504,
            "current_mandatory_scan_seconds": 26.631284100032644,
            "mandatory_scan_reduction_ratio": 0.01686,
            "template_footprint_support_attempts": 21489,
            "template_footprint_support_used": 0,
            "template_footprint_support_fallbacks": 6786,
            "dominant_gap_reason": DOMINANT_REASON,
            "dominant_gap_count": 6786,
            "dominant_gap_ratio": 1.0,
        },
        "signature_instrumentation": {
            "support_gap_reasons": {DOMINANT_REASON: 6786},
            "top_support_gap_entries": [
                {
                    "rect_idx": 0,
                    "anchor": [1, 2],
                    "group_id_or_template": "g",
                    "bucket_id": "b",
                    "reason": DOMINANT_REASON,
                    "elapsed_seconds": 0.1,
                }
            ],
        },
        "probe_safety": {
            "status_completed": True,
            "run_id_matches": True,
            "candidate_key_42x32": True,
            "execute_no_solve": True,
            "hard_boundary_flags_literal_false": True,
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


def _s81_payload() -> dict[str, object]:
    return {
        "review_verdict": "pass",
        "review_is_authorization": False,
        "authorization_required_next": True,
    }


def _s78_payload() -> dict[str, object]:
    return {
        "status": "implemented_and_verified",
        "env_var": "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION",
    }


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "83_signature_bucket_payload_footprint_stability_strategy"
    )
