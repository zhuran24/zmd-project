from __future__ import annotations

import json
from pathlib import Path

from src.search.certified_frontier import (
    TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
    build_terminal_frontier_evidence,
    candidate_generation_kwargs,
    generate_candidate_sizes,
)
from src.search.exact_campaign import (
    TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    terminal_certified_final_result_violation_for_project,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")


def _write_project(root: Path) -> None:
    _write_json(
        root / "rules" / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": 3, "height": 3},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 1,
                },
            },
            "facility_templates": {
                "solid": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            },
        },
    )
    _write_json(
        root / "data" / "preprocessed" / "candidate_placements.json",
        {
            "facility_pools": {
                "solid": [
                    {
                        "pose_id": "solid_at_0_0",
                        "anchor": {"x": 0, "y": 0},
                        "pose_params": {"orientation": 0, "port_mode": "default"},
                        "occupied_cells": [[0, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                    }
                ]
            }
        },
    )
    _write_json(
        root / "data" / "preprocessed" / "mandatory_exact_instances.json",
        [
            {
                "instance_id": "solid_001",
                "facility_type": "solid",
                "operation_type": "solid_op",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            }
        ],
    )
    _write_json(
        root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_inputs": {}, "required_generic_outputs": {}},
    )


def _terminal_state(root: Path, record_solution: dict[str, object]) -> dict[str, object]:
    _write_project(root)
    placement_solution = {"solid_001": {"facility_type": "solid", "pose_idx": 0}}
    final_result = {
        "search_status": "CERTIFIED",
        "ghost_rect": {"w": 2, "h": 3, "area": 6, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": placement_solution,
        "search_stats": {"probe": "v89_terminal_ghost_pick_protocol"},
    }
    candidate_generation = {
        "max_w": 3,
        "max_h": 3,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 8,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 8,
        "min_side_admissibility": 1,
    }
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    candidate_records = {
        "2x3": {
            "ghost_rect": {"w": 2, "h": 3, "area": 6},
            "attempts": 1,
            "started_at": "2026-06-10T00:00:00Z",
            "updated_at": "2026-06-10T00:00:01Z",
            "finished_at": "2026-06-10T00:00:01Z",
            "status": "CERTIFIED",
            "solution": record_solution,
            "proof_summary": {"test": "v89_terminal_ghost_pick_protocol"},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
    }
    return {
        "declare_mode": "strict",
        "final_status": "CERTIFIED",
        "last_stop_reason": {
            "status": "CERTIFIED",
            "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        },
        "final_result": final_result,
        "candidates": candidate_records,
        "terminal_frontier_evidence": build_terminal_frontier_evidence(
            candidates=candidates,
            candidate_records=candidate_records,
            final_result=final_result,
            candidate_generation=candidate_generation,
        ),
    }


def test_terminal_project_validator_rejects_missing_candidate_ghost_pick(tmp_path: Path) -> None:
    state = _terminal_state(
        tmp_path,
        {"solid_001": {"facility_type": "solid", "pose_idx": 0}},
    )

    assert (
        terminal_certified_final_result_violation_for_project(state, project_root=tmp_path)
        == "terminal_certified_candidate_solution_ghost_pick_missing"
    )


def test_terminal_project_validator_rejects_mismatched_candidate_ghost_pick_anchor(
    tmp_path: Path,
) -> None:
    state = _terminal_state(
        tmp_path,
        {
            "solid_001": {"facility_type": "solid", "pose_idx": 0},
            "ghost_pick": {"anchor": {"x": 0, "y": 0}},
        },
    )

    assert (
        terminal_certified_final_result_violation_for_project(state, project_root=tmp_path)
        == "terminal_certified_candidate_solution_ghost_pick_mismatch"
    )


def test_terminal_project_validator_accepts_bound_candidate_ghost_pick_anchor(
    tmp_path: Path,
) -> None:
    state = _terminal_state(
        tmp_path,
        {
            "solid_001": {"facility_type": "solid", "pose_idx": 0},
            "ghost_pick": {"anchor": {"x": 1, "y": 0}},
        },
    )

    assert terminal_certified_final_result_violation_for_project(state, project_root=tmp_path) is None
