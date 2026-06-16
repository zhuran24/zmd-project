from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.family_bound.build_formulation_comparison import (
    build_family_bound_formulation_comparison,
    write_family_bound_formulation_comparison,
)


def test_family_bound_formulation_comparison_marks_non_material_no_solve_switch(
    tmp_path: Path,
) -> None:
    big_m = tmp_path / "big_m.json"
    enforced = tmp_path / "enforced.json"
    _write_inventory(big_m, run_id="big_m", formulation="big_m", model_build=60.0, ghost_seconds=53.4)
    _write_inventory(
        enforced,
        run_id="enforced",
        formulation="enforced",
        model_build=59.9,
        ghost_seconds=53.3,
    )

    comparison = build_family_bound_formulation_comparison(
        big_m_inventory_path=big_m,
        enforced_inventory_path=enforced,
    )

    assert comparison["schema"] == (
        "phase3b-checkpoint-free-family-bound-formulation-comparison/v0"
    )
    assert comparison["interpretation"]["classification"] == (
        "formulation_switch_not_material_for_no_solve_model_size"
    )
    assert comparison["recommendation"]["action"] == (
        "prepare_default_off_family_bound_ablation_patch_spec"
    )
    assert comparison["evidence"]["proto_shape_identical"] is True
    assert comparison["evidence"]["deltas_enforced_minus_big_m"]["constraint_count"] == 0
    assert comparison["evidence"]["deltas_enforced_minus_big_m"]["ghost_constraint_seconds"] == pytest.approx(-0.1)
    assert comparison["safety"]["builder_executes_solver"] is False
    assert comparison["checkpoint_written"] is False
    assert comparison["proof_source"] is False


def test_family_bound_formulation_comparison_detects_shape_change(tmp_path: Path) -> None:
    big_m = tmp_path / "big_m.json"
    enforced = tmp_path / "enforced.json"
    _write_inventory(big_m, run_id="big_m", formulation="big_m", constraints=100)
    _write_inventory(enforced, run_id="enforced", formulation="enforced", constraints=90)

    comparison = build_family_bound_formulation_comparison(
        big_m_inventory_path=big_m,
        enforced_inventory_path=enforced,
    )

    assert comparison["interpretation"]["classification"] == "formulation_switch_material"
    assert comparison["recommendation"]["action"] == "hold_for_family_bound_comparison_review"


def test_family_bound_formulation_comparison_write_mode_is_namespaced(tmp_path: Path) -> None:
    big_m = tmp_path / "big_m.json"
    enforced = tmp_path / "enforced.json"
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "27_ghost_overlay_family_bound_formulation_comparison"
    )
    _write_inventory(big_m, run_id="big_m", formulation="big_m")
    _write_inventory(enforced, run_id="enforced", formulation="enforced")
    comparison = build_family_bound_formulation_comparison(
        big_m_inventory_path=big_m,
        enforced_inventory_path=enforced,
    )

    paths = write_family_bound_formulation_comparison(comparison, output_dir)

    assert paths["json"] == output_dir / "family_bound_formulation_comparison.json"
    assert paths["md"] == output_dir / "family_bound_formulation_comparison.md"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["recommendation"]["action"] == (
        "prepare_default_off_family_bound_ablation_patch_spec"
    )
    assert "CpSolver.Solve called: `false`" in paths["md"].read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="outside family bound comparison namespace"):
        write_family_bound_formulation_comparison(payload, tmp_path / "bad")


def _write_inventory(
    path: Path,
    *,
    run_id: str,
    formulation: str,
    model_build: float = 60.0,
    ghost_seconds: float = 53.4,
    variables: int = 58799,
    constraints: int = 152949,
) -> None:
    path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "completed",
                "execute_no_solve": True,
                "target": {"candidate_key": "42x32"},
                "elapsed_seconds": 92.0,
                "inventory": {
                    "model_build_seconds": model_build,
                    "proto": {
                        "variable_count": variables,
                        "constraint_count": constraints,
                        "constraints_by_type": {
                            "linear": constraints - 10,
                            "interval": 10,
                        },
                    },
                    "build_stats_summary": {
                        "exact_core_reuse": {
                            "ghost_constraint_seconds": ghost_seconds,
                        },
                        "global_valid_inequalities": {
                            "ghost_aware_via_pole_feasibility": {
                                "conditioned_family_bound_formulation": formulation,
                                "conditioned_family_upper_bound_constraints": 11976,
                                "family_reduction_anchor_count": 1012,
                                "disabled_placements": 0,
                            }
                        },
                    },
                },
                "sensitive_path_comparison": {"changed": False},
            }
        )
        + "\n",
        encoding="utf-8",
    )
