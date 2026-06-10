from __future__ import annotations

import json
from pathlib import Path

from src.models.cut_manager import RUN_STATUS_CERTIFIED, RUN_STATUS_INFEASIBLE
from src.search.benders_loop import run_benders_for_ghost_rect
from src.search.certified_frontier import candidate_key, generate_candidate_sizes
from src.search.outer_search import run_outer_search


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_oriented_gap_project(project_root: Path) -> Path:
    data_dir = project_root / "data" / "preprocessed"
    rules_dir = project_root / "rules"
    templates = {
        f"block_{y}": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}
        for y in range(3)
    }
    pools: dict[str, list[dict[str, object]]] = {}
    instances: list[dict[str, object]] = []
    for y in range(3):
        tpl = f"block_{y}"
        pools[tpl] = [
            {
                "pose_id": f"{tpl}_only",
                "anchor": {"x": 1, "y": y},
                "occupied_cells": [[1, y]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
                "pose_params": {"orientation": 0, "port_mode": "default"},
            }
        ]
        instances.append(
            {
                "instance_id": f"block_{y}_001",
                "facility_type": tpl,
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            }
        )
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
            "facility_templates": templates,
        },
    )
    _write_json(data_dir / "candidate_placements.json", {"facility_pools": pools})
    _write_json(data_dir / "mandatory_exact_instances.json", instances)
    _write_json(data_dir / "all_facility_instances.json", instances)
    _write_json(
        data_dir / "generic_io_requirements.json",
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )
    return project_root


def test_full_frontier_candidate_domain_keeps_oriented_dimensions(tmp_path: Path) -> None:
    project_root = _build_oriented_gap_project(tmp_path / "oriented_gap")

    candidate_keys = {
        candidate_key(candidate)
        for candidate in generate_candidate_sizes(
            max_w=3,
            max_h=3,
            min_side=1,
            area_upper_bound=6,
        )
    }
    assert "3x1" in candidate_keys
    assert "1x3" in candidate_keys

    horizontal_status, _ = run_benders_for_ghost_rect(
        ghost_w=3,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=10.0,
        binding_seconds=10.0,
        routing_seconds=10.0,
        flow_seconds=10.0,
        max_iterations=6,
    )
    vertical_status, _ = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=3,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=10.0,
        binding_seconds=10.0,
        routing_seconds=10.0,
        flow_seconds=10.0,
        max_iterations=6,
    )
    assert horizontal_status == RUN_STATUS_INFEASIBLE
    assert vertical_status == RUN_STATUS_CERTIFIED

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=10.0,
        binding_seconds=10.0,
        routing_seconds=10.0,
        flow_seconds=10.0,
        benders_max_iter=6,
        campaign_hours=1.0,
        resume_campaign=False,
        min_side=1,
        area_upper_bound=6,
        parallel_processes=1,
    )
    assert status == RUN_STATUS_CERTIFIED
    assert result is not None
    assert result["ghost_rect"] == {"w": 1, "h": 3, "area": 3}
