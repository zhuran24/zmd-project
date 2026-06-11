"""Regression coverage for certified-exact P0 soundness fixes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ortools.sat.python import cp_model

import src.search.benders_loop as benders_loop_module
from src.models.cut_manager import RUN_STATUS_CERTIFIED
from src.models.master_model import MasterPlacementModel
from src.models.routing_subproblem import RoutingGrid, RoutingSubproblem
from src.search.benders_loop import run_benders_for_ghost_rect


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_tiny_exact_project(project_root: Path) -> Path:
    data_dir = project_root / "data" / "preprocessed"
    rules_dir = project_root / "rules"
    _write_json(
        rules_dir / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": 2, "height": 1},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 1,
                },
            },
            "facility_templates": {
                "tiny_facility": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            },
        },
    )
    _write_json(
        data_dir / "candidate_placements.json",
        {
            "facility_pools": {
                "tiny_facility": [
                    {
                        "pose_id": "tiny_left",
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [[0, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    }
                ]
            }
        },
    )
    instances = [
        {
            "instance_id": "tiny_001",
            "facility_type": "tiny_facility",
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_modes": ["certified_exact"],
        }
    ]
    _write_json(data_dir / "mandatory_exact_instances.json", instances)
    _write_json(data_dir / "all_facility_instances.json", instances)
    _write_json(
        data_dir / "generic_io_requirements.json",
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )
    return project_root


def test_routing_feasible_incumbent_requires_source_to_sink_connectivity() -> None:
    """Reject a locally closed source component plus a separate sink component."""

    active_cells = {(1, 0), (1, 1), (2, 1), (2, 0), (5, 0), (5, 1), (6, 1), (6, 0)}
    port_specs = [
        {"instance_id": "src", "x": 0, "y": 0, "dir": "E", "type": "out", "commodity": "ore"},
        {"instance_id": "sink", "x": 6, "y": 0, "dir": "W", "type": "in", "commodity": "ore"},
    ]
    domain_analysis = {
        "status": "feasible",
        "commodity_component_cells": {"ore": [list(cell) for cell in sorted(active_cells)]},
        "commodity_active_cells": {"ore": [list(cell) for cell in sorted(active_cells)]},
        "domain_stats": {
            "domain_cells": len(active_cells),
            "terminal_core_cells": len(active_cells),
            "commodity_component_cells": {"ore": len(active_cells)},
            "commodity_active_cells": {"ore": len(active_cells)},
        },
    }
    routing = RoutingSubproblem(
        RoutingGrid(set(), port_specs),
        ["ore"],
        domain_analysis=domain_analysis,
    )
    routing.build()

    disconnected_incumbent = {
        (1, 0, 0, ("E", "W"), ("N",), "ore"),
        (1, 1, 0, ("S",), ("E",), "ore"),
        (2, 1, 0, ("W",), ("S",), "ore"),
        (2, 0, 0, ("N",), ("W",), "ore"),
        (5, 0, 0, ("E",), ("N", "W"), "ore"),
        (5, 1, 0, ("S",), ("E",), "ore"),
        (6, 1, 0, ("W",), ("S",), "ore"),
        (6, 0, 0, ("N",), ("W",), "ore"),
    }
    assert disconnected_incumbent <= set(routing.r_vars)
    for key, var in routing.r_vars.items():
        routing.model.Add(var == (1 if key in disconnected_incumbent else 0))

    assert routing.solve(time_limit=5.0) == "INFEASIBLE"
    guard = routing.build_stats["last_solve"]["connectivity_guard"]
    assert guard["rejected_incumbents"] == 1
    assert guard["attempts"][0]["connectivity"]["failures"][0]["unreachable_sink_fronts"] == [
        [5, 0, "W"]
    ]


def test_coordinate_master_no_overlap_uses_pose_footprint_not_template_dims() -> None:
    """Two real 4x6 vertical footprints cannot pass as template-sized 6x4 rectangles."""

    def vertical_footprint(anchor_y: int) -> list[list[int]]:
        return [[x, y] for x in range(4) for y in range(anchor_y, anchor_y + 6)]

    instances = [
        {
            "instance_id": "rotator_001",
            "facility_type": "rotator",
            "operation_type": "manufacturing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "rotator_002",
            "facility_type": "rotator",
            "operation_type": "manufacturing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "rotator": [
            {
                "pose_id": "rotator_v0",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": "vertical", "port_mode": "A"},
                "occupied_cells": vertical_footprint(0),
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "rotator_v4",
                "anchor": {"x": 0, "y": 4},
                "pose_params": {"orientation": "vertical", "port_mode": "A"},
                "occupied_cells": vertical_footprint(4),
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ]
    }
    rules = {
        "globals": {"grid": {"width": 10, "height": 10}},
        "facility_templates": {
            "rotator": {"dimensions": {"w": 6, "h": 4}, "needs_power": False},
        },
    }
    core = MasterPlacementModel.build_exact_core(
        instances,
        pools,
        rules,
        skip_power_coverage=True,
        enable_symmetry_breaking=False,
    )
    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=None)

    assert overlay.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_front_blocked_safe_reject_enumerates_binding_before_master_cut(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """A binding-local blocked front must not become a placement-only nogood."""

    project_root = _build_tiny_exact_project(tmp_path / "front_blocked_binding_local")
    precheck_calls = {"count": 0}

    class FakeBindingModel:
        nogood_count = 0

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.index = 0
            self.binding_vars = {"tiny_001": {0: object(), 1: object()}}
            self.generic_input_vars = {}
            self.generic_output_vars = {}

        def build(self) -> None:
            return None

        def solve(self, time_limit_seconds: float = 30.0) -> str:
            return "FEASIBLE" if self.index < 2 else "INFEASIBLE"

        def extract_selection(self) -> dict[str, Any]:
            return {
                "binding_choice": {"tiny_001": self.index},
                "generic_inputs": {},
                "generic_outputs": {},
            }

        def extract_port_specs(self) -> list[dict[str, Any]]:
            return []

        def add_nogood_cut(self, selection: dict[str, Any]) -> None:
            assert selection["binding_choice"]["tiny_001"] == self.index
            FakeBindingModel.nogood_count += 1
            self.index += 1

        def extract_conflict_summary(self) -> dict[str, Any]:
            return {"index": self.index, "nogoods": FakeBindingModel.nogood_count}

    class FakeRoutingSubproblem:
        solve_calls = 0

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.build_stats = {"fake": "routing"}

        def build(self) -> None:
            return None

        def solve(self, time_limit: float = 60.0) -> str:
            FakeRoutingSubproblem.solve_calls += 1
            return "FEASIBLE"

    def fake_precheck(*args: Any, **kwargs: Any) -> dict[str, Any]:
        del args, kwargs
        precheck_calls["count"] += 1
        if precheck_calls["count"] == 1:
            return {
                "status": "front_blocked",
                "binding_selection_safe_reject": True,
                "placement_level_conflict_set": ["tiny_001"],
                "blocked_ports": [
                    {
                        "instance_id": "tiny_001",
                        "placement_level_conflict_set": ["tiny_001"],
                        "port_cell": [0, 0],
                        "front_cell": [1, 0],
                        "dir": "E",
                    }
                ],
                "disconnected_commodities": [],
            }
        return {
            "status": "feasible",
            "binding_selection_safe_reject": False,
            "placement_level_conflict_set": [],
            "blocked_ports": [],
            "disconnected_commodities": [],
        }

    monkeypatch.setattr(benders_loop_module, "PortBindingModel", FakeBindingModel)
    monkeypatch.setattr(benders_loop_module, "RoutingSubproblem", FakeRoutingSubproblem)
    monkeypatch.setattr(benders_loop_module, "run_exact_routing_precheck", fake_precheck)
    monkeypatch.setattr(
        benders_loop_module.LBBDController,
        "_run_flow_diagnostic",
        lambda self, solution: ("FEASIBLE", set()),
    )

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=5.0,
        binding_seconds=5.0,
        routing_seconds=5.0,
        max_iterations=2,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")

    assert status == RUN_STATUS_CERTIFIED
    assert result is not None
    assert precheck_calls["count"] == 2
    assert FakeBindingModel.nogood_count == 1
    assert FakeRoutingSubproblem.solve_calls == 1
    assert metadata["generated_exact_safe_cut_count"] == 0
    assert metadata["routing_front_blocked_cut_count"] == 0
