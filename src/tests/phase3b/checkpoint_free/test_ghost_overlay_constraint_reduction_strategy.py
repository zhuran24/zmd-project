from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.build_ghost_overlay_constraint_reduction_strategy import (
    build_ghost_overlay_constraint_reduction_strategy,
    write_ghost_overlay_constraint_reduction_strategy,
)


def test_ghost_overlay_strategy_prefers_existing_enforced_no_solve_probe(tmp_path: Path) -> None:
    review_path = tmp_path / "review.json"
    inventory_path = tmp_path / "inventory.json"
    _write_review(review_path, inventory_path)
    _write_inventory(inventory_path)

    strategy = build_ghost_overlay_constraint_reduction_strategy(review_path=review_path)

    assert strategy["schema"] == (
        "phase3b-checkpoint-free-ghost-overlay-constraint-reduction-strategy/v0"
    )
    assert strategy["interpretation"]["classification"] == "family_bound_overlay_dominates"
    assert strategy["recommendation"]["action"] == (
        "run_no_solve_enforced_family_bound_formulation_probe"
    )
    assert strategy["evidence"]["ghost_aware_via_pole_feasibility"][
        "conditioned_family_upper_bound_constraints"
    ] == 11976
    assert strategy["evidence"]["ghost_aware_via_pole_feasibility"][
        "constraints_share_of_overlay_delta"
    ] == pytest.approx(11976 / 14788)
    first_action = strategy["candidate_actions"][0]
    assert first_action["env"] == {
        "EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION": "enforced"
    }
    assert first_action["allowed"] is True
    assert first_action["solver_allowed"] is False
    assert strategy["safety"]["builder_executes_solver"] is False
    assert strategy["safety"]["checkpoint_written"] is False
    assert strategy["proof_source"] is False


def test_ghost_overlay_strategy_holds_without_matching_review_classification(tmp_path: Path) -> None:
    review_path = tmp_path / "review.json"
    inventory_path = tmp_path / "inventory.json"
    _write_review(review_path, inventory_path, classification="manual_review_required")
    _write_inventory(inventory_path)

    strategy = build_ghost_overlay_constraint_reduction_strategy(review_path=review_path)

    assert strategy["interpretation"]["classification"] == "manual_review_required"
    assert strategy["recommendation"]["action"] == "hold_for_manual_ghost_overlay_review"
    assert strategy["candidate_actions"] == []


def test_ghost_overlay_strategy_write_mode_is_namespaced(tmp_path: Path) -> None:
    review_path = tmp_path / "review.json"
    inventory_path = tmp_path / "inventory.json"
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "26_ghost_overlay_constraint_reduction_strategy"
    )
    _write_review(review_path, inventory_path)
    _write_inventory(inventory_path)
    strategy = build_ghost_overlay_constraint_reduction_strategy(review_path=review_path)

    paths = write_ghost_overlay_constraint_reduction_strategy(strategy, output_dir)

    assert paths["json"] == output_dir / "ghost_overlay_constraint_reduction_strategy.json"
    assert paths["md"] == output_dir / "ghost_overlay_constraint_reduction_strategy.md"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["recommendation"]["action"] == (
        "run_no_solve_enforced_family_bound_formulation_probe"
    )
    assert "CpSolver.Solve called: `false`" in paths["md"].read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="outside ghost overlay strategy namespace"):
        write_ghost_overlay_constraint_reduction_strategy(payload, tmp_path / "bad")


def _write_review(path: Path, inventory_path: Path, *, classification: str = "ghost_overlay_constraint_build_dominates") -> None:
    path.write_text(
        json.dumps(
            {
                "source_inventory_path": str(inventory_path),
                "target": {"candidate_key": "42x32"},
                "evidence": {
                    "overlay_delta": {"overlay_constraints_added": 14788},
                    "timing_hotspots": {
                        "ghost_constraint_seconds": 53.4,
                        "ghost_constraint_fraction_of_model_build": 0.889,
                    },
                    "proto": {
                        "constraints_by_type": {
                            "linear": 139536,
                            "interval": 5408,
                        }
                    },
                },
                "interpretation": {
                    "classification": classification,
                    "linear_constraint_dominance": 0.912,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_inventory(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "inventory": {
                    "build_stats_summary": {
                        "global_valid_inequalities": {
                            "ghost_aware_via_pole_feasibility": {
                                "conditioned_family_bound_formulation": "big_m",
                                "conditioned_family_upper_bound_constraints": 11976,
                                "disabled_placements": 0,
                                "surviving_placements": 1131,
                                "family_reduction_anchor_count": 1012,
                                "template_fail_counts": {},
                            },
                            "signature_bucket_capacity_bounds": {
                                "ghost_conditioned_mandatory_bucket_constraints": 68,
                                "ghost_conditioned_required_optional_bucket_constraints": 0,
                                "ghost_signature_reduction_anchor_count": 67,
                            },
                            "residual_signature_bucket_capacity_bounds": {
                                "ghost_conditioned_residual_bucket_constraints": 480,
                                "ghost_residual_signature_reduction_anchor_count": 480,
                            },
                        }
                    }
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
