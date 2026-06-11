"""Regression coverage for certified-exact P0 soundness fixes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from ortools.sat.python import cp_model

import src.search.benders_loop as benders_loop_module
from src.models.cut_manager import RUN_STATUS_CERTIFIED
from src.models.master_model import MasterPlacementModel
import src.models.routing_subproblem as routing_subproblem_module
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


def test_routing_guard_timeout_does_not_expose_rejected_routes(monkeypatch: Any) -> None:
    """A timeout after a guard rejection must not leave extract_routes on a stale incumbent."""

    active_cells = {(1, 0), (1, 1), (2, 1), (2, 0), (5, 0), (5, 1), (6, 1), (6, 0)}
    port_specs = [
        {"instance_id": "src", "x": 0, "y": 0, "dir": "E", "type": "out", "commodity": "ore"},
        {"instance_id": "sink", "x": 6, "y": 0, "dir": "W", "type": "in", "commodity": "ore"},
    ]
    domain_analysis = {
        "status": "feasible",
        "commodity_component_cells": {"ore": [list(cell) for cell in sorted(active_cells)]},
        "commodity_active_cells": {"ore": [list(cell) for cell in sorted(active_cells)]},
        "domain_stats": {},
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
    for key, var in routing.r_vars.items():
        routing.model.Add(var == (1 if key in disconnected_incumbent else 0))

    perf_counter_values = iter([0.0, 0.0, 100.0, 100.0])
    monkeypatch.setattr(
        routing_subproblem_module.time,
        "perf_counter",
        lambda: next(perf_counter_values, 100.0),
    )

    assert routing.solve(time_limit=1.0) == "TIMEOUT"
    guard = routing.build_stats["last_solve"]["connectivity_guard"]
    assert guard["rejected_incumbents"] == 1
    assert routing.extract_routes() == []



def test_routing_guard_checks_each_selected_commodity() -> None:
    """A disconnected incumbent must be rejected for every commodity, not just the first."""

    def shifted_state(state: tuple[Any, ...], dy: int, commodity: str) -> tuple[Any, ...]:
        x, y, layer, flow_in, flow_out, _old_commodity = state
        return (x, y + dy, layer, flow_in, flow_out, commodity)

    base_states = {
        (1, 0, 0, ("E", "W"), ("N",), "ore"),
        (1, 1, 0, ("S",), ("E",), "ore"),
        (2, 1, 0, ("W",), ("S",), "ore"),
        (2, 0, 0, ("N",), ("W",), "ore"),
        (5, 0, 0, ("E",), ("N", "W"), "ore"),
        (5, 1, 0, ("S",), ("E",), "ore"),
        (6, 1, 0, ("W",), ("S",), "ore"),
        (6, 0, 0, ("N",), ("W",), "ore"),
    }
    port_specs = [
        {"instance_id": "ore_src", "x": 0, "y": 0, "dir": "E", "type": "out", "commodity": "ore"},
        {"instance_id": "ore_sink", "x": 6, "y": 0, "dir": "W", "type": "in", "commodity": "ore"},
        {"instance_id": "water_src", "x": 0, "y": 3, "dir": "E", "type": "out", "commodity": "water"},
        {"instance_id": "water_sink", "x": 6, "y": 3, "dir": "W", "type": "in", "commodity": "water"},
    ]
    domain_analysis = {
        "status": "feasible",
        "commodity_component_cells": {
            "ore": [list(cell) for cell in sorted((state[0], state[1]) for state in base_states)],
            "water": [list(cell) for cell in sorted((state[0], state[1] + 3) for state in base_states)],
        },
        "commodity_active_cells": {
            "ore": [list(cell) for cell in sorted((state[0], state[1]) for state in base_states)],
            "water": [list(cell) for cell in sorted((state[0], state[1] + 3) for state in base_states)],
        },
        "domain_stats": {},
    }
    routing = RoutingSubproblem(
        RoutingGrid(set(), port_specs),
        ["ore", "water"],
        domain_analysis=domain_analysis,
    )
    routing.build()

    disconnected_incumbent = base_states | {shifted_state(state, 3, "water") for state in base_states}
    assert disconnected_incumbent <= set(routing.r_vars)
    for key, var in routing.r_vars.items():
        routing.model.Add(var == (1 if key in disconnected_incumbent else 0))

    assert routing.solve(time_limit=5.0) == "INFEASIBLE"
    connectivity = routing.build_stats["last_solve"]["connectivity_guard"]["attempts"][0]["connectivity"]
    assert connectivity["failure_count"] == 2
    assert {failure["commodity"] for failure in connectivity["failures"]} == {"ore", "water"}


def test_coordinate_powered_pose_without_occupied_cells_fails_closed() -> None:
    """Missing footprint evidence on a powered pose must not fall through to bbox witnesses."""

    rules = {
        "globals": {"grid": {"width": 4, "height": 4}},
        "facility_templates": {
            "powered": {"dimensions": {"w": 2, "h": 2}, "needs_power": True},
            "power_pole": {
                "dimensions": {"w": 1, "h": 1},
                "needs_power": False,
                "power_coverage_radius": 1,
            },
        },
    }
    instances = [
        {
            "instance_id": "powered_001",
            "facility_type": "powered",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "pole_001",
            "facility_type": "power_pole",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "powered": [
            {
                "pose_id": "powered_missing_cells",
                "anchor": {"x": 1, "y": 1},
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
        "power_pole": [
            {
                "pose_id": "pole",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[0, 0], [0, 1], [1, 0], [1, 1]],
            }
        ],
    }

    with pytest.raises(ValueError, match="Missing occupied_cells for coordinate footprint domain"):
        core = MasterPlacementModel.build_exact_core(
            instances,
            pools,
            rules,
            generic_io_requirements={"required_generic_outputs": {}, "required_generic_inputs": {}},
        )
        MasterPlacementModel.from_exact_core(core, ghost_rect=None)


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


def test_geometric_power_coverage_falls_back_for_nonrectangular_powered_footprints() -> None:
    """Bounding-box overlap must not certify power through a hole in an L footprint."""

    instances = [
        {
            "instance_id": "blocker_001",
            "facility_type": "blocker",
            "operation_type": "block",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools = {
        "blocker": [
            {
                "pose_id": "block_B",
                "anchor": {"x": 2, "y": 1},
                "occupied_cells": [[2, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
        "protocol_storage_box": [
            {
                "pose_id": "box_A_hole_false",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": "L", "port_mode": "same"},
                "occupied_cells": [[0, 0], [0, 1], [1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "box_B_real_covered_but_blocked",
                "anchor": {"x": 1, "y": 1},
                "pose_params": {"orientation": "L", "port_mode": "same"},
                "occupied_cells": [[1, 1], [1, 2], [2, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
        "power_pole": [
            {
                "pose_id": "pole_covers_A_hole_and_B",
                "anchor": {"x": 1, "y": 1},
                "occupied_cells": [[3, 3]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[1, 1], [1, 2], [2, 1], [2, 2]],
            }
        ],
    }
    rules = {
        "globals": {"grid": {"width": 4, "height": 4}},
        "facility_templates": {
            "blocker": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 2, "h": 2}, "needs_power": True},
            "power_pole": {
                "dimensions": {"w": 1, "h": 1},
                "needs_power": False,
                "power_coverage_radius": 0,
            },
        },
    }
    generic_io_requirements = {"required_generic_inputs": {"ore": 1}, "required_generic_outputs": {}}
    core = MasterPlacementModel.build_exact_core(
        instances,
        pools,
        rules,
        generic_io_requirements=generic_io_requirements,
        enable_symmetry_breaking=False,
    )
    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=None)

    assert overlay.build_stats["power_coverage"]["representation"] == "coordinate_cover_table"
    assert overlay._power_coverers_by_template_pose["protocol_storage_box"] == {0: [], 1: [0]}
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
