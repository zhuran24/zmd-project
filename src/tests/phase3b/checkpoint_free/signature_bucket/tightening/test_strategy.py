from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.tightening.build_strategy import (
    build_signature_bucket_tightening_strategy,
)


def test_signature_bucket_strategy_marks_internal_loop_strategy_required(tmp_path: Path) -> None:
    probe = tmp_path / "overlay_timing_probe.json"
    output_dir = _output_dir(tmp_path)
    _write_overlay_timing_probe(probe)

    payload = build_signature_bucket_tightening_strategy(
        overlay_timing_probe_path=probe,
        output_dir=output_dir,
    )

    assert payload["status"] == "completed"
    assert payload["wrapper_timing_complete"] is True
    assert payload["hotspot_method"].endswith("_apply_ghost_anchor_signature_bucket_tightening")
    assert payload["interpretation"]["classification"] == "signature_bucket_internal_loop_strategy_required"
    assert payload["recommendation"]["action"] == (
        "prepare_default_off_signature_bucket_tightening_instrumentation_patch_spec"
    )
    assert payload["no_solve"] is True
    assert payload["source_model_mutation"] is False
    assert payload["checkpoint_written"] is False
    assert payload["proof_source"] is False
    assert payload["evidence"]["signature_bucket_tightening_seconds"] == 66.0
    assert payload["evidence"]["ghost_conditioned_mandatory_bucket_constraints"] == 68
    assert payload["evidence"]["ghost_conditioned_required_optional_bucket_constraints"] == 0
    assert payload["evidence"]["ghost_cell_visits_per_mandatory_payload_lower_bound"] == 1_520_064
    assert (output_dir / "signature_bucket_tightening_strategy.json").exists()
    assert (output_dir / "signature_bucket_tightening_strategy.md").exists()


def test_signature_bucket_strategy_no_write_does_not_create_output(tmp_path: Path) -> None:
    probe = tmp_path / "overlay_timing_probe.json"
    output_dir = _output_dir(tmp_path)
    _write_overlay_timing_probe(probe)

    payload = build_signature_bucket_tightening_strategy(
        overlay_timing_probe_path=probe,
        output_dir=output_dir,
        no_write=True,
    )

    assert payload["interpretation"]["classification"] == "signature_bucket_internal_loop_strategy_required"
    assert not output_dir.exists()


def test_signature_bucket_strategy_missing_optional_fields_needs_manual_review(tmp_path: Path) -> None:
    probe = tmp_path / "overlay_timing_probe.json"
    _write_overlay_timing_probe(probe, include_build_stats=False)

    payload = build_signature_bucket_tightening_strategy(
        overlay_timing_probe_path=probe,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert payload["interpretation"]["classification"] == "manual_review_required"
    assert payload["recommendation"]["action"] == "hold_for_manual_signature_bucket_tightening_review"
    assert payload["evidence"]["ghost_conditioned_mandatory_bucket_constraints"] is None


def test_signature_bucket_strategy_holds_when_hotspot_is_small(tmp_path: Path) -> None:
    probe = tmp_path / "overlay_timing_probe.json"
    _write_overlay_timing_probe(probe, signature_seconds=5.0)

    payload = build_signature_bucket_tightening_strategy(
        overlay_timing_probe_path=probe,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert payload["interpretation"]["classification"] == "manual_review_required"


def test_signature_bucket_strategy_rejects_bad_namespace(tmp_path: Path) -> None:
    probe = tmp_path / "overlay_timing_probe.json"
    _write_overlay_timing_probe(probe)

    with pytest.raises(ValueError, match="signature bucket tightening strategy namespace"):
        build_signature_bucket_tightening_strategy(
            overlay_timing_probe_path=probe,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_overlay_timing_probe(
    path: Path,
    *,
    signature_seconds: float = 66.0,
    include_build_stats: bool = True,
) -> None:
    build_stats_summary = {}
    if include_build_stats:
        build_stats_summary = {
            "ghost_rect": {
                "enabled": True,
                "placements": 1131,
                "size": {"w": 42, "h": 32},
                "signature_tightening_anchor_reductions": 67,
            },
            "global_valid_inequalities": {
                "signature_bucket_capacity_bounds": {
                    "applied": True,
                    "mandatory_bucket_upper_bound_constraints": 0,
                    "required_optional_bucket_upper_bound_constraints": 0,
                    "ghost_conditioned_mandatory_bucket_constraints": 68,
                    "ghost_conditioned_required_optional_bucket_constraints": 0,
                    "ghost_signature_reduction_anchor_count": 67,
                    "mandatory_groups": [{"group_id": "g0", "buckets": []}],
                    "required_optional_groups": [],
                },
                "residual_signature_bucket_capacity_bounds": {
                    "applied": True,
                    "ghost_conditioned_residual_bucket_constraints": 480,
                    "ghost_residual_signature_reduction_anchor_count": 480,
                },
                "ghost_aware_via_pole_feasibility": {
                    "evaluated_placements": 1131,
                    "conditioned_family_upper_bound_constraints": 11976,
                    "family_reduction_anchor_count": 1012,
                },
            },
        }
    path.write_text(
        json.dumps(
            {
                "status": "completed",
                "no_solve": True,
                "cp_solver_solve_called": False,
                "checkpoint_written": False,
                "proof_source": False,
                "source_model_mutation": False,
                "sensitive_path_comparison": {"changed": False},
                "target": {
                    "candidate_key": "42x32",
                    "candidate_tuple": [1344, 42, 32],
                    "ghost_rect": {"w": 42, "h": 32, "area": 1344},
                },
                "timing": {
                    "from_exact_core_total_seconds": 78.0,
                    "recorded_phase_seconds_sum": 138.0,
                    "ghost_anchor_interval_and_outer_residual_seconds": 0.11,
                    "coverage": {"wrapper_level_only": True, "source_model_mutation": False},
                    "build_stats_exact_core_reuse": {"ghost_constraint_seconds": 69.0},
                    "phases": [
                        {
                            "phase": "CoordinateExactMasterDelegate._add_ghost_constraints",
                            "calls": 1,
                            "total_seconds": 69.0,
                            "max_seconds": 69.0,
                        },
                        {
                            "phase": (
                                "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening"
                            ),
                            "calls": 1,
                            "total_seconds": signature_seconds,
                            "max_seconds": signature_seconds,
                        },
                        {
                            "phase": (
                                "CoordinateExactMasterDelegate._apply_ghost_anchor_residual_signature_bucket_tightening"
                            ),
                            "calls": 1,
                            "total_seconds": 2.2,
                            "max_seconds": 2.2,
                        },
                    ],
                },
                "inventory": {
                    "model_build_seconds": 78.0,
                    "build_stats_summary": build_stats_summary,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _output_dir(root: Path) -> Path:
    return root / ".artifacts" / "phase3b_local_13900ks_tuning_20260430" / "36_signature_bucket_tightening_strategy"
