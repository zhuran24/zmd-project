from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.region_counting_fallback.build_strategy import (
    ENV_VAR,
    TARGET_CLASSIFICATION,
    build_signature_bucket_region_counting_fallback_strategy,
    write_signature_bucket_region_counting_fallback_strategy,
)


def test_region_counting_fallback_strategy_classifies_s59_residual_fallback(
    tmp_path: Path,
) -> None:
    s51_path, s53_path, probe_path, agents_path, source_path = _write_inputs(tmp_path)

    strategy = build_signature_bucket_region_counting_fallback_strategy(
        s51_path=s51_path,
        s53_path=s53_path,
        probe_path=probe_path,
        agents_path=agents_path,
        source_path=source_path,
    )

    assert strategy["status"] == "completed"
    assert strategy["interpretation"]["classification"] == TARGET_CLASSIFICATION
    assert strategy["source_mutation_performed"] is False
    assert strategy["interpretation"]["implementation_allowed_now"] is False
    assert strategy["review_required_before_authorization"] is True
    assert strategy["future_patch_spec"]["env_var"] == ENV_VAR
    assert "fallback-reason" in strategy["future_patch_spec"]["enabled_scope"]
    assert "bounded" in " ".join(strategy["future_patch_spec"]["enabled_safety_contract"])
    assert strategy["evidence_summary"]["mandatory_region_counting_fallbacks"] == 6786
    assert strategy["evidence_summary"]["region_counting_fallback_ratio"] == pytest.approx(
        6786 / 21489
    )


def test_region_counting_fallback_strategy_requires_nontrivial_fallbacks(
    tmp_path: Path,
) -> None:
    s51_path, s53_path, probe_path, agents_path, source_path = _write_inputs(tmp_path)
    s53 = json.loads(s53_path.read_text(encoding="utf-8"))
    s53["signature_instrumentation"]["totals"]["mandatory_region_counting_fallbacks"] = 0
    s53_path.write_text(json.dumps(s53) + "\n", encoding="utf-8")

    strategy = build_signature_bucket_region_counting_fallback_strategy(
        s51_path=s51_path,
        s53_path=s53_path,
        probe_path=probe_path,
        agents_path=agents_path,
        source_path=source_path,
    )

    assert strategy["status"] == "manual_review_required"
    failed_checks = {
        check["name"]
        for check in strategy["input_checks"]
        if check["status"] == "failed"
    }
    assert "region_counting_effective_but_fallback_nontrivial" in failed_checks


def test_region_counting_fallback_strategy_dirty_safety_requires_manual_review(
    tmp_path: Path,
) -> None:
    s51_path, s53_path, probe_path, agents_path, source_path = _write_inputs(tmp_path)
    s53 = json.loads(s53_path.read_text(encoding="utf-8"))
    s53["probe_safety"]["actual_flags"]["runtime_execution_performed"] = True
    s53_path.write_text(json.dumps(s53) + "\n", encoding="utf-8")

    strategy = build_signature_bucket_region_counting_fallback_strategy(
        s51_path=s51_path,
        s53_path=s53_path,
        probe_path=probe_path,
        agents_path=agents_path,
        source_path=source_path,
    )

    assert strategy["status"] == "manual_review_required"
    failed_checks = {
        check["name"]
        for check in strategy["input_checks"]
        if check["status"] == "failed"
    }
    assert "s53_safety_clean" in failed_checks


def test_region_counting_fallback_strategy_write_and_namespace_guard(
    tmp_path: Path,
) -> None:
    s51_path, s53_path, probe_path, agents_path, source_path = _write_inputs(tmp_path)
    strategy = build_signature_bucket_region_counting_fallback_strategy(
        s51_path=s51_path,
        s53_path=s53_path,
        probe_path=probe_path,
        agents_path=agents_path,
        source_path=source_path,
    )

    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "60_signature_bucket_region_counting_fallback_strategy"
    )
    paths = write_signature_bucket_region_counting_fallback_strategy(strategy, output_dir)

    assert paths["json"].is_file()
    assert paths["md"].is_file()
    assert json.loads(paths["json"].read_text(encoding="utf-8"))["status"] == "completed"
    with pytest.raises(ValueError, match="S60 region-counting fallback strategy namespace"):
        write_signature_bucket_region_counting_fallback_strategy(strategy, tmp_path / "bad")


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    s51_path = tmp_path / "s51.json"
    s53_path = tmp_path / "s53.json"
    probe_path = tmp_path / "probe.json"
    agents_path = tmp_path / "AGENTS.md"
    source_path = tmp_path / "exact_coordinate_master.py"
    s51_path.write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "source_patch": {
                    "env_var": "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    s53_path.write_text(json.dumps(_s53_payload()) + "\n", encoding="utf-8")
    probe_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "execute_no_solve": True,
                "cp_solver_solve_called": False,
                "checkpoint_written": False,
                "proof_source": False,
                "runtime_execution_performed": False,
                "sensitive_path_comparison": {"changed": False, "changed_paths": []},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    agents_path.write_text(
        "# AGENTS\n\n- Current S59 enabled no-solve probe result: classification `mandatory_region_counting_effective`.\n",
        encoding="utf-8",
    )
    source_path.write_text(
        "\n".join(
            [
                "def _mandatory_region_counting_payload(self):",
                "    pass",
                "def _mandatory_region_blocked_counts_for_domain(self):",
                "    pass",
                "def _apply_ghost_anchor_signature_bucket_tightening(self):",
                "    for cell in domain.get(\"cells\", []):",
                "        blocked_pose_indices = set()",
                "        _add_total(\"mandatory_region_counting_fallbacks\", 1)",
                "    mandatory_region_counting_fallbacks = 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return s51_path, s53_path, probe_path, agents_path, source_path


def _s53_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "run_id": "local_hotspot_42x32_signature_bucket_region_counting_inst_no_solve_001",
        "probe_path": "probe.json",
        "model_build_seconds": 45.27,
        "wrapper_timing": {
            "from_exact_core_total_seconds": 45.27,
            "ghost_constraints_total_seconds": 36.99,
            "ghost_signature_bucket_total_seconds": 34.28,
        },
        "interpretation": {
            "classification": "mandatory_region_counting_effective",
            "baseline_mandatory_scan_seconds": 68.0824784,
            "mandatory_scan_seconds": 32.2747502,
        },
        "signature_instrumentation": {
            "present": True,
            "visibility_status": "instrumentation_visible",
            "region_counting_status": "mandatory_region_counting_used",
            "phase_seconds": {
                "mandatory_payload_build": 1.92,
                "required_optional_payload_build": 0.0,
                "per_anchor_mandatory_scan": 32.2747502,
                "per_anchor_required_optional_scan": 0.0,
                "constraint_add": 0.003,
                "stats_finalize": 0.0,
            },
            "totals": {
                "mandatory_payload_count": 19,
                "required_optional_payload_count": 0,
                "mandatory_region_counting_attempts": 21489,
                "mandatory_region_counting_used": 14703,
                "mandatory_region_counting_fallbacks": 6786,
                "mandatory_cells_scanned": 9120384,
                "required_optional_cells_scanned": 0,
                "mandatory_pose_hits": 716870890,
                "mandatory_unique_blocked_poses": 122364420,
                "mandatory_region_rectangles_evaluated": 174174,
                "mandatory_region_overlap_counts": 74502,
                "mandatory_region_counted_blocked_poses": 86275936,
            },
            "top_slow_entries": [
                {
                    "kind": "mandatory",
                    "rect_idx": 195,
                    "anchor": {"x": 5, "y": 0},
                    "group_id_or_template": "group::boundary_storage_port::boundary_io::0",
                    "bucket_id": "sig_001",
                    "scan_count": 1344,
                    "reduction_count": 1,
                    "elapsed_seconds": 0.0013,
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
            "sensitive_path_comparison": {"changed": False, "changed_paths": []},
        },
    }
