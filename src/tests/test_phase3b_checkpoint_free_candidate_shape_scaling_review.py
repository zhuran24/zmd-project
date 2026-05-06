from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_candidate_shape_scaling_review import (
    build_candidate_shape_scaling_review,
)


def test_shape_scaling_review_identifies_via_pole_anchor_explosion(tmp_path: Path) -> None:
    comparison = tmp_path / "candidate_shape_inventory_comparison.json"
    _write_comparison(comparison)
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "30_candidate_shape_scaling_review"
    )

    review = build_candidate_shape_scaling_review(comparison_path=comparison, output_dir=output_dir)

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "shape_specific_via_pole_anchor_explosion"
    assert review["recommendation"]["action"] == (
        "prepare_default_off_via_pole_shape_instrumentation_patch_spec"
    )
    assert review["metrics"]["median_non_baseline_anchor_count_ratio"] < 0.1
    assert (output_dir / "candidate_shape_scaling_review.json").exists()
    assert (output_dir / "candidate_shape_scaling_review.md").exists()


def test_shape_scaling_review_no_write_returns_payload_without_artifacts(tmp_path: Path) -> None:
    comparison = tmp_path / "candidate_shape_inventory_comparison.json"
    _write_comparison(comparison)
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "30_candidate_shape_scaling_review"
    )

    review = build_candidate_shape_scaling_review(
        comparison_path=comparison,
        output_dir=output_dir,
        no_write=True,
    )

    assert review["status"] == "completed"
    assert not output_dir.exists()


def test_shape_scaling_review_holds_for_dirty_or_incomplete_comparison(tmp_path: Path) -> None:
    comparison = tmp_path / "candidate_shape_inventory_comparison.json"
    payload = _comparison_payload()
    payload["sensitive_path_comparison"]["changed"] = True
    comparison.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "30_candidate_shape_scaling_review"
    )

    review = build_candidate_shape_scaling_review(
        comparison_path=comparison,
        output_dir=output_dir,
        no_write=True,
    )

    assert review["interpretation"]["classification"] == "shape_scaling_comparison_not_ready"
    assert review["recommendation"]["action"] == "hold_for_manual_shape_scaling_review"


def test_shape_scaling_review_rejects_bad_namespace(tmp_path: Path) -> None:
    comparison = tmp_path / "candidate_shape_inventory_comparison.json"
    _write_comparison(comparison)

    with pytest.raises(ValueError, match="candidate shape scaling review namespace"):
        build_candidate_shape_scaling_review(
            comparison_path=comparison,
            output_dir=tmp_path / "bad_namespace",
        )


def _write_comparison(path: Path) -> None:
    path.write_text(json.dumps(_comparison_payload()) + "\n", encoding="utf-8")


def _comparison_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "execute_no_solve": True,
        "cp_solver_solve_called": False,
        "checkpoint_written": False,
        "source_mutation_performed": False,
        "proof_source": False,
        "sensitive_path_comparison": {"changed": False},
        "rows": [
            {
                "candidate_key": "42x32",
                "status": "completed",
                "variable_count": 58799,
                "constraint_count": 152949,
                "ghost_constraint_seconds": 53.4,
                "conditioned_family_upper_bound_constraints": 11976,
                "family_reduction_anchor_count": 1012,
                "surviving_placements": 1131,
            },
            {
                "candidate_key": "70x12",
                "status": "completed",
                "variable_count": 57727,
                "constraint_count": 139194,
                "ghost_constraint_seconds": 2.13,
                "conditioned_family_upper_bound_constraints": 853,
                "family_reduction_anchor_count": 59,
                "surviving_placements": 59,
            },
            {
                "candidate_key": "70x19",
                "status": "completed",
                "variable_count": 57720,
                "constraint_count": 139124,
                "ghost_constraint_seconds": 2.62,
                "conditioned_family_upper_bound_constraints": 804,
                "family_reduction_anchor_count": 52,
                "surviving_placements": 52,
            },
        ],
    }
