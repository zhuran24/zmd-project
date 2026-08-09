from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.master.build_proto_inventory_review import (
    build_master_proto_inventory_review,
    find_latest_completed_inventory,
    write_master_proto_inventory_review,
)


def test_master_proto_inventory_review_identifies_ghost_overlay_hotspot(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.json"
    _write_inventory(inventory)

    review = build_master_proto_inventory_review(inventory_path=inventory)

    assert review["schema"] == "phase3b-checkpoint-free-master-proto-inventory-review/v0"
    assert review["source_run_id"] == "exec_002"
    assert review["interpretation"]["classification"] == "ghost_overlay_constraint_build_dominates"
    assert review["interpretation"]["dominant_constraint_type"] == "linear"
    assert review["interpretation"]["constraint_type_classification_usable"] is True
    assert review["interpretation"]["search_guidance_literal_scale_is_large"] is True
    assert review["recommendation"]["action"] == "prepare_ghost_overlay_constraint_reduction_strategy"
    assert review["evidence"]["overlay_delta"]["overlay_variables_added"] == 1131
    assert review["evidence"]["overlay_delta"]["overlay_constraints_added"] == 14788
    assert review["evidence"]["proto"]["top_constraint_types"][0] == {
        "type": "linear",
        "count": 139536,
    }
    assert review["safety"]["builder_executes_solver"] is False
    assert review["safety"]["checkpoint_written"] is False
    assert review["proof_source"] is False


def test_master_proto_inventory_review_holds_when_constraint_types_unknown(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.json"
    _write_inventory(inventory, constraints_by_type={"unknown": 10})

    review = build_master_proto_inventory_review(inventory_path=inventory)

    assert review["interpretation"]["classification"] == "constraint_classification_unusable"
    assert review["recommendation"]["action"] == "hold_for_inventory_review_repair"


def test_master_proto_inventory_review_write_mode_is_namespaced(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.json"
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "25_master_proto_inventory_review"
    )
    _write_inventory(inventory)

    paths = write_master_proto_inventory_review(
        build_master_proto_inventory_review(inventory_path=inventory),
        output_dir,
    )

    assert paths["json"] == output_dir / "master_proto_inventory_review.json"
    assert paths["md"] == output_dir / "master_proto_inventory_review.md"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["recommendation"]["action"] == "prepare_ghost_overlay_constraint_reduction_strategy"
    assert "CpSolver.Solve called: `false`" in paths["md"].read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="outside master proto inventory review namespace"):
        write_master_proto_inventory_review(payload, tmp_path / "bad")


def test_find_latest_completed_inventory_ignores_plan_only(tmp_path: Path) -> None:
    old_path = tmp_path / "old" / "master_proto_inventory.json"
    plan_path = tmp_path / "plan" / "master_proto_inventory.json"
    new_path = tmp_path / "new" / "master_proto_inventory.json"
    _write_inventory(old_path, run_id="old")
    _write_inventory(plan_path, run_id="plan", status="planned_only", execute_no_solve=False)
    _write_inventory(new_path, run_id="new")

    assert find_latest_completed_inventory(tmp_path) == new_path


def _write_inventory(
    path: Path,
    *,
    run_id: str = "exec_002",
    status: str = "completed",
    execute_no_solve: bool = True,
    constraints_by_type: dict[str, int] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    constraints = constraints_by_type or {
        "linear": 139536,
        "interval": 5408,
        "element": 3815,
    }
    path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": status,
                "execute_no_solve": execute_no_solve,
                "target": {"candidate_key": "42x32", "ghost_rect": {"w": 42, "h": 32}},
                "elapsed_seconds": 92.0,
                "inventory": {
                    "model_build_seconds": 60.0,
                    "session_core_build_seconds": 30.0,
                    "proto": {
                        "variable_count": 58799,
                        "boolean_variable_count": 42444,
                        "constraint_count": 152949,
                        "constraints_by_type": constraints,
                    },
                    "build_stats_summary": {
                        "exact_core_reuse": {
                            "core_proto_variables": 57668,
                            "core_proto_constraints": 138161,
                            "overlay_build_seconds": 60.0,
                            "ghost_constraint_seconds": 53.4,
                            "cleared_existing_search_strategy_count": 6046,
                            "rebuilt_search_strategy_count": 6047,
                        },
                        "ghost_rect": {
                            "enabled": True,
                            "placements": 1131,
                            "size": {"w": 42, "h": 32},
                            "signature_tightening_anchor_reductions": 67,
                        },
                        "search_guidance": {
                            "mandatory_literals": 3853132,
                            "ghost_literals": 1131,
                            "residual_optional_literals": {
                                "power_pole": 3632643,
                                "protocol_storage_box": 9765888,
                            },
                        },
                    },
                },
                "sensitive_path_comparison": {"changed": False},
            }
        )
        + "\n",
        encoding="utf-8",
    )
