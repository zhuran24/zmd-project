from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_family_bound_ablation_patch_spec import (
    build_family_bound_ablation_patch_spec,
    write_family_bound_ablation_patch_spec,
)


def test_family_bound_ablation_patch_spec_requires_explicit_source_authorization(
    tmp_path: Path,
) -> None:
    comparison = tmp_path / "comparison.json"
    _write_comparison(comparison)

    spec = build_family_bound_ablation_patch_spec(comparison_path=comparison)

    assert spec["schema"] == "phase3b-checkpoint-free-family-bound-ablation-patch-spec/v0"
    assert spec["interpretation"]["classification"] == (
        "patch_spec_ready_source_mutation_still_blocked"
    )
    assert spec["interpretation"]["implementation_allowed_now"] is False
    assert spec["interpretation"]["source_mutation_authorized_by_this_artifact"] is False
    assert spec["source_mutation_performed"] is False
    assert spec["patch_spec"]["target_file"] == "src/models/exact_coordinate_master.py"
    assert spec["patch_spec"]["env_var"] == "EXACT_GHOST_CONDITIONED_FAMILY_BOUNDS_ENABLED"
    assert spec["recommendation"]["action"] == (
        "prepare_no_source_candidate_shape_inventory_comparison"
    )
    assert spec["safety"]["builder_executes_solver"] is False
    assert spec["checkpoint_written"] is False
    assert spec["proof_source"] is False


def test_family_bound_ablation_patch_spec_holds_for_unready_comparison(tmp_path: Path) -> None:
    comparison = tmp_path / "comparison.json"
    _write_comparison(comparison, action="hold_for_family_bound_comparison_review")

    spec = build_family_bound_ablation_patch_spec(comparison_path=comparison)

    assert spec["interpretation"]["classification"] == "manual_review_required"
    assert spec["patch_spec"] == {}
    assert spec["validation_plan"] == []


def test_family_bound_ablation_patch_spec_write_mode_is_namespaced(tmp_path: Path) -> None:
    comparison = tmp_path / "comparison.json"
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "28_family_bound_ablation_patch_spec"
    )
    _write_comparison(comparison)
    spec = build_family_bound_ablation_patch_spec(comparison_path=comparison)

    paths = write_family_bound_ablation_patch_spec(spec, output_dir)

    assert paths["json"] == output_dir / "family_bound_ablation_patch_spec.json"
    assert paths["md"] == output_dir / "family_bound_ablation_patch_spec.md"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["source_mutation_performed"] is False
    assert "Source mutation performed: `false`" in paths["md"].read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="outside family bound patch spec namespace"):
        write_family_bound_ablation_patch_spec(payload, tmp_path / "bad")


def _write_comparison(
    path: Path,
    *,
    classification: str = "formulation_switch_not_material_for_no_solve_model_size",
    action: str = "prepare_default_off_family_bound_ablation_patch_spec",
) -> None:
    path.write_text(
        json.dumps(
            {
                "interpretation": {
                    "classification": classification,
                },
                "recommendation": {
                    "action": action,
                },
                "evidence": {
                    "proto_shape_identical": True,
                    "deltas_enforced_minus_big_m": {
                        "constraint_count": 0,
                        "ghost_constraint_seconds": -0.1,
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
