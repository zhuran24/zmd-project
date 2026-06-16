from __future__ import annotations

import json
from pathlib import Path

from src.models.cut_manager import RUN_STATUS_CERTIFIED, RUN_STATUS_INFEASIBLE
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


def _write_project(root: Path) -> dict[str, list[dict[str, object]]]:
    ghost_cells = {(2, 2), (2, 3), (3, 2), (3, 3)}
    box_cells = [
        (x, y)
        for y in range(4)
        for x in range(4)
        if (x, y) not in ghost_cells and (x, y) != (0, 0)
    ]
    facility_pools: dict[str, list[dict[str, object]]] = {
        "solid": [
            {
                "pose_id": "solid_at_0_0",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
            }
        ],
        "protocol_storage_box": [
            {
                "pose_id": f"box_at_{x}_{y}",
                "anchor": {"x": x, "y": y},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[x, y]],
                "input_port_cells": [],
                "output_port_cells": [],
            }
            for x, y in box_cells
        ],
    }
    _write_json(
        root / "rules" / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": 4, "height": 4},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 1,
                },
            },
            "facility_templates": {
                "solid": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
                "protocol_storage_box": {
                    "dimensions": {"w": 1, "h": 1},
                    "needs_power": False,
                },
            },
            "commodity_metadata": {
                "demo_input": {"source_kind": "internal_only", "sink_kind": "generic_input"},
            },
        },
    )
    _write_json(
        root / "rules" / "preprocess_plan.json",
        {
            "utility_operations": {
                "wireless_sink": {
                    "facility_type": "protocol_storage_box",
                    "generic_input_slots": 3,
                }
            }
        },
    )
    _write_json(root / "data" / "preprocessed" / "candidate_placements.json", {"facility_pools": facility_pools})
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
    # wireless_sink has 3 generic input slots, so this requires one protocol box.
    _write_json(
        root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_inputs": {"demo_input": 1}, "required_generic_outputs": {}},
    )
    return facility_pools


def _placement_solution(facility_pools: dict[str, list[dict[str, object]]]) -> dict[str, dict[str, object]]:
    solution: dict[str, dict[str, object]] = {
        "solid_001": {
            "facility_type": "solid",
            "pose_idx": 0,
            "pose_id": "solid_at_0_0",
            "anchor": {"x": 0, "y": 0},
            "instance_id": "solid_001",
            "operation_type": "solid_op",
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_mode": "certified_exact",
        }
    }
    for pose_idx, pose in enumerate(facility_pools["protocol_storage_box"]):
        pose_id = str(pose["pose_id"])
        solution[f"pose_optional::protocol_storage_box::{pose_id}"] = {
            "facility_type": "protocol_storage_box",
            "pose_idx": int(pose_idx),
            "pose_id": pose_id,
            "anchor": dict(pose["anchor"]),
            "is_mandatory": False,
            "bound_type": "exact_pose_optional",
            "solve_mode": "certified_exact",
        }
    return solution


def _candidate_record(
    ghost_w: int,
    ghost_h: int,
    status: str,
    *,
    solution: dict[str, object] | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "ghost_rect": {"w": ghost_w, "h": ghost_h, "area": ghost_w * ghost_h},
        "attempts": 1,
        "started_at": "2026-06-11T00:00:00Z",
        "updated_at": "2026-06-11T00:00:01Z",
        "finished_at": "2026-06-11T00:00:01Z",
        "status": status,
        "proof_summary": {"test": "v94_terminal_protocol_storage_surplus"},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }
    if solution is not None:
        record["solution"] = solution
    return record


def _terminal_state(root: Path) -> dict[str, object]:
    facility_pools = _write_project(root)
    placement_solution = _placement_solution(facility_pools)
    final_result = {
        "search_status": RUN_STATUS_CERTIFIED,
        "ghost_rect": {"w": 2, "h": 2, "area": 4, "anchor_x": 2, "anchor_y": 2},
        "placement_solution": placement_solution,
        "search_stats": {"campaign_resumed": False},
    }
    candidate_generation = {
        "max_w": 4,
        "max_h": 4,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 14,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 14,
        "min_side_admissibility": 1,
    }
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    certified_solution = dict(placement_solution)
    certified_solution["ghost_pick"] = {
        "pose_idx": 0,
        "pose_id": "ghost_anchor::2,2",
        "anchor": {"x": 2, "y": 2},
        "facility_type": "ghost_rect",
    }
    candidate_records: dict[str, object] = {}
    for _area, ghost_w, ghost_h in candidates:
        key = f"{ghost_w}x{ghost_h}"
        if (ghost_w, ghost_h) == (2, 2):
            candidate_records[key] = _candidate_record(
                ghost_w,
                ghost_h,
                RUN_STATUS_CERTIFIED,
                solution=certified_solution,
            )
        else:
            candidate_records[key] = _candidate_record(ghost_w, ghost_h, RUN_STATUS_INFEASIBLE)
    return {
        "declare_mode": "strict",
        "final_status": RUN_STATUS_CERTIFIED,
        "last_stop_reason": {
            "status": RUN_STATUS_CERTIFIED,
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


def test_terminal_project_validator_rejects_surplus_protocol_storage_box_blockers(tmp_path: Path) -> None:
    state = _terminal_state(tmp_path)

    assert (
        terminal_certified_final_result_violation_for_project(state, project_root=tmp_path)
        == "terminal_certified_final_result_solution_excess_protocol_storage_box_instance"
    )
