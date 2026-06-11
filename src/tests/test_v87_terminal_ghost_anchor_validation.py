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


def test_terminal_project_validator_rejects_occupied_claimed_ghost_anchor(
    tmp_path: Path,
) -> None:
    root = tmp_path / "occupied_claimed_ghost_anchor"
    data_dir = root / "data" / "preprocessed"
    rules_dir = root / "rules"
    data_dir.mkdir(parents=True)
    rules_dir.mkdir(parents=True)

    _write_json(
        rules_dir / "canonical_rules.json",
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
        data_dir / "candidate_placements.json",
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
        data_dir / "mandatory_exact_instances.json",
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
        data_dir / "generic_io_requirements.json",
        {"required_generic_inputs": {}, "required_generic_outputs": {}},
    )

    placement_solution = {"solid_001": {"facility_type": "solid", "pose_idx": 0}}
    final_result = {
        "search_status": "CERTIFIED",
        "ghost_rect": {"w": 3, "h": 2, "area": 6, "anchor_x": 0, "anchor_y": 0},
        "placement_solution": placement_solution,
        "search_stats": {"campaign_resumed": False},
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
    candidate_records: dict[str, dict[str, object]] = {}
    for area, ghost_w, ghost_h in candidates:
        status = "CERTIFIED" if (ghost_w, ghost_h) == (3, 2) else "INFEASIBLE"
        record: dict[str, object] = {
            "ghost_rect": {"w": ghost_w, "h": ghost_h, "area": area},
            "attempts": 1,
            "started_at": "2026-06-10T00:00:00Z",
            "updated_at": "2026-06-10T00:00:01Z",
            "finished_at": "2026-06-10T00:00:01Z",
            "status": status,
            "proof_summary": {"probe": "occupied claimed ghost anchor"},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        if status == "CERTIFIED":
            record["solution"] = placement_solution
        candidate_records[f"{ghost_w}x{ghost_h}"] = record

    state = {
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

    assert (
        terminal_certified_final_result_violation_for_project(state, project_root=root)
        == "terminal_certified_final_result_ghost_rect_anchor_occupied"
    )
