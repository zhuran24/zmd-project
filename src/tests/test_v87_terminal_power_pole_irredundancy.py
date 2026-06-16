from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


def _pose(
    *,
    pose_id: str,
    x: int,
    y: int,
    occupied_cells: list[list[int]],
    power_coverage_cells: list[list[int]] | None = None,
) -> dict[str, Any]:
    pose: dict[str, Any] = {
        "pose_id": pose_id,
        "anchor": {"x": x, "y": y},
        "pose_params": {"orientation": 0, "port_mode": "default"},
        "occupied_cells": occupied_cells,
        "input_port_cells": [],
        "output_port_cells": [],
    }
    if power_coverage_cells is not None:
        pose["power_coverage_cells"] = power_coverage_cells
    return pose


def test_terminal_project_validator_rejects_unforced_power_pole_blocker(
    tmp_path: Path,
) -> None:
    root = tmp_path / "unforced_power_pole_blocker"
    data_dir = root / "data" / "preprocessed"
    rules_dir = root / "rules"
    data_dir.mkdir(parents=True)
    rules_dir.mkdir(parents=True)

    rules = {
        "globals": {
            "grid": {"width": 3, "height": 3},
            "empty_rectangle": {
                "objective": "max_lex_area_min_side",
                "min_side_admissibility": 1,
            },
        },
        "facility_templates": {
            "powered_sink": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "power_pole": {
                "dimensions": {"w": 1, "h": 1},
                "needs_power": False,
                "power_coverage_radius": 0,
            },
        },
    }
    facility_pools = {
        "powered_sink": [
            _pose(pose_id="sink_at_0_0", x=0, y=0, occupied_cells=[[0, 0]]),
        ],
        "power_pole": [
            _pose(
                pose_id="pole_cover_sink",
                x=1,
                y=0,
                occupied_cells=[[1, 0]],
                power_coverage_cells=[[0, 0]],
            ),
            _pose(
                pose_id="pole_extra_blocker",
                x=1,
                y=1,
                occupied_cells=[[1, 1]],
                power_coverage_cells=[],
            ),
        ],
    }
    _write_json(rules_dir / "canonical_rules.json", rules)
    _write_json(data_dir / "candidate_placements.json", {"facility_pools": facility_pools})
    _write_json(
        data_dir / "mandatory_exact_instances.json",
        [
            {
                "instance_id": "sink_001",
                "facility_type": "powered_sink",
                "operation_type": "sink_op",
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

    placement_solution = {
        "sink_001": {"facility_type": "powered_sink", "pose_idx": 0},
        "pose_optional::power_pole::pole_cover_sink": {
            "facility_type": "power_pole",
            "pose_idx": 0,
            "pose_id": "pole_cover_sink",
            "is_mandatory": False,
            "bound_type": "exact_pose_optional",
            "solve_mode": "certified_exact",
        },
        "pose_optional::power_pole::pole_extra_blocker": {
            "facility_type": "power_pole",
            "pose_idx": 1,
            "pose_id": "pole_extra_blocker",
            "is_mandatory": False,
            "bound_type": "exact_pose_optional",
            "solve_mode": "certified_exact",
        },
    }
    final_result = {
        "search_status": "CERTIFIED",
        "ghost_rect": {"w": 3, "h": 1, "area": 3, "anchor_x": 0, "anchor_y": 2},
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
        status = "CERTIFIED" if (ghost_w, ghost_h) == (3, 1) else "INFEASIBLE"
        record: dict[str, object] = {
            "ghost_rect": {"w": ghost_w, "h": ghost_h, "area": area},
            "attempts": 1,
            "started_at": "2026-06-10T00:00:00Z",
            "updated_at": "2026-06-10T00:00:01Z",
            "finished_at": "2026-06-10T00:00:01Z",
            "status": status,
            "proof_summary": {"probe": "unforced power pole blocker"},
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
        == "terminal_certified_final_result_solution_unforced_power_pole_instance"
    )
