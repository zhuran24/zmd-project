import copy
import json
from pathlib import Path

import pytest
from ortools.sat.python import cp_model

from src.interchange.preprocess_context import build_preprocess_context_from_rules_and_plan
from src.models.port_binding import routing_free_sink_commodities_from_generic_inputs
from src.models.pose_bool_exact_master import PoseBoolExactMasterDelegate
from src.models.separator_capacity_hull import Separator, classify_pose_commodity_side
from src.search.routing_deletion_core_minimizer import (
    _oracle_front_blocked,
    build_routing_visible_port_keys_by_instance,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


CANONICAL_GENERIC_INPUTS = {"valley_battery": 1, "qiaoyu_capsule": 1}


def test_preprocess_context_rejects_dual_role_generic_input_overlay() -> None:
    root = _project_root()
    rules = json.loads((root / "rules" / "canonical_rules.json").read_text(encoding="utf-8"))
    plan = json.loads((root / "rules" / "preprocess_plan.json").read_text(encoding="utf-8"))
    mutated = copy.deepcopy(rules)
    mutated["commodity_metadata"]["steel_part"]["sink_kind"] = "generic_input"
    mutated["production_targets"]["steel_part"] = {
        "mode": "equivalent_full_speed_lines",
        "value": 1.0,
        "final_recipe_id": "parts_maker",
    }

    with pytest.raises(ValueError, match="cannot also be a recipe input"):
        build_preprocess_context_from_rules_and_plan(mutated, plan)


def test_deletion_core_oracle_consumes_filtered_routing_visible_ports() -> None:
    facility_pools = {
        "capsule_maker": [
            {
                "occupied_cells": [(0, 0)],
                "input_port_cells": [],
                "output_port_cells": [{"x": 1, "y": 0, "dir": "E"}],
            }
        ],
        "blocker": [
            {"occupied_cells": [(1, 0)], "input_port_cells": [], "output_port_cells": []}
        ],
    }
    layout = {
        "producer": {"facility_type": "capsule_maker", "pose_idx": 0},
        "blocker": {"facility_type": "blocker", "pose_idx": 0},
    }

    rfsc = routing_free_sink_commodities_from_generic_inputs(CANONICAL_GENERIC_INPUTS)
    assert rfsc == frozenset()
    visible_ports = build_routing_visible_port_keys_by_instance(
        [
            {
                "instance_id": "producer",
                "x": 1,
                "y": 0,
                "dir": "E",
                "type": "out",
                "commodity": "qiaoyu_capsule",
            }
        ]
    )
    assert _oracle_front_blocked(
        layout,
        facility_pools,
        70,
        70,
        routing_visible_port_keys_by_instance=visible_ports,
    )
    assert not _oracle_front_blocked(
        layout,
        facility_pools,
        70,
        70,
        routing_visible_port_keys_by_instance={},
    )


def test_pose_bool_front_caches_include_routed_final_output_side() -> None:
    class Owner:
        def __init__(self) -> None:
            self.model = cp_model.CpModel()
            self.grid_w = 70
            self.grid_h = 70
            self.generic_io_requirements = {
                "required_generic_inputs": {"qiaoyu_capsule": 1},
                "required_generic_outputs": {},
            }
            self.facility_pools = {
                "maker": [
                    {
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [(5, 5)],
                        "input_port_cells": [{"x": 5, "y": 5, "dir": "W"}],
                        "output_port_cells": [{"x": 5, "y": 5, "dir": "E"}],
                    }
                ]
            }

    owner = Owner()
    delegate = PoseBoolExactMasterDelegate(owner)
    delegate.x_vars[("g", 0)] = owner.model.NewBoolVar("x_g_0")
    delegate._mandatory_template_by_group["g"] = "maker"
    delegate._mandatory_operation_by_group["g"] = "filling_capsule"

    assert delegate._routing_visible_profile_demands("filling_capsule") == (4, 1)

    delegate._build_port_lookup_cache()
    assert (5, 5, "E") in delegate._poses_by_port_at_cell_dir
    assert (5, 5, "W") in delegate._routing_visible_poses_by_port_at_cell_dir
    assert (5, 5, "E") in delegate._routing_visible_poses_by_port_at_cell_dir


def test_pose_bool_visible_cache_keeps_mixed_final_output_side(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.models.pose_bool_exact_master as pose_master

    class MixedProfile:
        input_slots = {}
        output_slots = {"visible_widget": 1, "qiaoyu_capsule": 1}
        generic_input_slots = 0
        generic_output_slots = 0

    monkeypatch.setattr(
        pose_master,
        "get_operation_port_profile",
        lambda operation_type: MixedProfile(),
    )

    class Owner:
        def __init__(self) -> None:
            self.model = cp_model.CpModel()
            self.grid_w = 70
            self.grid_h = 70
            self.generic_io_requirements = {
                "required_generic_inputs": {"qiaoyu_capsule": 1},
                "required_generic_outputs": {},
            }
            self.facility_pools = {
                "mixed_maker": [
                    {
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [(5, 5)],
                        "input_port_cells": [],
                        "output_port_cells": [
                            {"x": 5, "y": 5, "dir": "E"},
                            {"x": 6, "y": 5, "dir": "E"},
                        ],
                    }
                ]
            }

    owner = Owner()
    delegate = PoseBoolExactMasterDelegate(owner)
    delegate.x_vars[("g", 0)] = owner.model.NewBoolVar("x_g_0")
    delegate._mandatory_template_by_group["g"] = "mixed_maker"
    delegate._mandatory_operation_by_group["g"] = "mixed_output"

    assert delegate._routing_visible_profile_demands("mixed_output") == (0, 2)

    delegate._build_port_lookup_cache()
    assert (5, 5, "E") in delegate._poses_by_port_at_cell_dir
    assert (6, 5, "E") in delegate._poses_by_port_at_cell_dir
    assert (5, 5, "E") in delegate._routing_visible_poses_by_port_at_cell_dir
    assert (6, 5, "E") in delegate._routing_visible_poses_by_port_at_cell_dir


def test_pose_bool_cell_pattern_cut_refuses_unbound_generic_input_overcount(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.models.pose_bool_exact_master as pose_master

    class MixedGenericInputProfile:
        input_slots = {"iron_plate": 1}
        output_slots = {}
        generic_input_slots = 1
        generic_output_slots = 0

    monkeypatch.setattr(
        pose_master,
        "get_operation_port_profile",
        lambda operation_type: MixedGenericInputProfile(),
    )

    class Owner:
        def __init__(self) -> None:
            self.model = cp_model.CpModel()
            self.grid_w = 5
            self.grid_h = 5
            self.generic_io_requirements = {
                "required_generic_inputs": {"wireless_part": 1},
                "required_generic_outputs": {},
            }
            self.build_stats = {}
            self._last_solution = None
            self.facility_pools = {
                "maker": [
                    {
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [(0, 0)],
                        "input_port_cells": [
                            {"x": 0, "y": 1, "dir": "N"},
                            {"x": 1, "y": 1, "dir": "N"},
                        ],
                        "output_port_cells": [],
                    }
                ],
                "blocker": [
                    {
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [(1, 2)],
                        "input_port_cells": [],
                        "output_port_cells": [],
                    }
                ],
            }

    owner = Owner()
    delegate = PoseBoolExactMasterDelegate(owner)
    delegate.x_vars[("g_maker", 0)] = owner.model.NewBoolVar("maker")
    delegate.x_vars[("g_blocker", 0)] = owner.model.NewBoolVar("blocker")
    delegate._mandatory_template_by_group["g_maker"] = "maker"
    delegate._mandatory_operation_by_group["g_maker"] = "mixed_generic_input"
    delegate._mandatory_template_by_group["g_blocker"] = "blocker"
    delegate._mandatory_operation_by_group["g_blocker"] = "mixed_generic_input"

    assert delegate.add_routing_port_blocking_cell_cut(
        port_cell=(1, 1),
        direction="N",
        front_cell=(1, 2),
    ) is False


def test_pose_bool_port_lookup_cache_uses_global_cells_without_anchor_shift() -> None:
    class Owner:
        def __init__(self) -> None:
            self.model = cp_model.CpModel()
            self.grid_w = 70
            self.grid_h = 70
            self.generic_io_requirements = {"required_generic_inputs": {}, "required_generic_outputs": {}}
            self.facility_pools = {
                "maker": [
                    {
                        # candidate_placements.json stores global cells and an
                        # anchor snapshot.  The cache must not add the anchor a
                        # second time.
                        "anchor": {"x": 10, "y": 20},
                        "occupied_cells": [(11, 21)],
                        "input_port_cells": [{"x": 11, "y": 22, "dir": "N"}],
                        "output_port_cells": [],
                    }
                ]
            }

    owner = Owner()
    delegate = PoseBoolExactMasterDelegate(owner)
    delegate.x_vars[("g", 0)] = owner.model.NewBoolVar("x_g_0")
    delegate._mandatory_template_by_group["g"] = "maker"
    delegate._mandatory_operation_by_group["g"] = "crusher_blue_iron"

    delegate._build_port_lookup_cache()

    assert (11, 21) in delegate._poses_by_cell
    assert (21, 41) not in delegate._poses_by_cell
    assert (11, 22, "N") in delegate._routing_visible_poses_by_port_at_cell_dir
    assert (21, 42, "N") not in delegate._routing_visible_poses_by_port_at_cell_dir


def test_pose_bool_cell_pattern_cut_refuses_inactive_binding_slot_overcut(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.models.pose_bool_exact_master as pose_master

    class OneOfTwoInputProfile:
        input_slots = {"ore": 1}
        output_slots = {}
        generic_input_slots = 0
        generic_output_slots = 0

    monkeypatch.setattr(
        pose_master,
        "get_operation_port_profile",
        lambda operation_type: OneOfTwoInputProfile(),
    )

    class Owner:
        def __init__(self) -> None:
            self.model = cp_model.CpModel()
            self.grid_w = 70
            self.grid_h = 70
            self.generic_io_requirements = {"required_generic_inputs": {}, "required_generic_outputs": {}}
            self.build_stats = {}
            self._last_solution = None
            self.facility_pools = {
                "maker": [
                    {
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [(0, 0)],
                        # Demand is one, so either input slot can be selected by
                        # binding.  A blocked first slot does not make the pose
                        # plus blocker pattern infeasible: the second slot can be
                        # used instead.
                        "input_port_cells": [
                            {"x": 0, "y": 1, "dir": "N"},
                            {"x": 1, "y": 1, "dir": "N"},
                        ],
                        "output_port_cells": [],
                    }
                ],
                "blocker": [
                    {
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [(0, 2)],
                        "input_port_cells": [],
                        "output_port_cells": [],
                    }
                ],
            }

    owner = Owner()
    delegate = PoseBoolExactMasterDelegate(owner)
    maker = owner.model.NewBoolVar("maker")
    blocker = owner.model.NewBoolVar("blocker")
    delegate.x_vars[("g_maker", 0)] = maker
    delegate.x_vars[("g_blocker", 0)] = blocker
    delegate._mandatory_template_by_group["g_maker"] = "maker"
    delegate._mandatory_operation_by_group["g_maker"] = "one_of_two_inputs"
    delegate._mandatory_template_by_group["g_blocker"] = "blocker"
    delegate._mandatory_operation_by_group["g_blocker"] = "one_of_two_inputs"

    owner.model.Add(maker == 1)
    owner.model.Add(blocker == 1)

    added = delegate.add_routing_port_blocking_cell_cut(
        port_cell=(0, 1),
        direction="N",
        front_cell=(0, 2),
    )

    assert added is False
    assert cp_model.CpSolver().Solve(owner.model) in {cp_model.FEASIBLE, cp_model.OPTIMAL}


def test_pose_bool_cell_pattern_cut_refuses_unused_generic_output_slot_overcut() -> None:
    """Generic-output slots are capacity, not per-port mandatory demand.

    With one required generic output and two physical output slots, binding may
    leave the blocked first slot unused and route from the second slot.  A raw
    cell-pattern cut over the first output cell would therefore ban a feasible
    placement pattern.
    """

    from src.models.binding_subproblem import PortBindingModel
    from src.models.routing_binding_context import build_routing_binding_context

    class Owner:
        def __init__(self) -> None:
            self.model = cp_model.CpModel()
            self.grid_w = 5
            self.grid_h = 5
            self.generic_io_requirements = {
                "required_generic_outputs": {"source_ore": 1},
                "required_generic_inputs": CANONICAL_GENERIC_INPUTS,
            }
            self.build_stats = {}
            self._last_solution = None
            self.facility_pools = {
                "protocol_core": [
                    {
                        "pose_id": "core_two_outputs",
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [(0, 0)],
                        "input_port_cells": [
                            {"x": x, "y": y, "dir": "S"}
                            for x, y in (
                                (1, 0),
                                (2, 0),
                                (3, 0),
                                (4, 0),
                                (2, 1),
                                (3, 1),
                                (4, 1),
                                (1, 2),
                                (2, 2),
                                (3, 2),
                                (4, 2),
                                (0, 3),
                                (1, 3),
                                (2, 3),
                            )
                        ],
                        "output_port_cells": [
                            {"x": 0, "y": 1, "dir": "N"},
                            {"x": 1, "y": 1, "dir": "N"},
                        ],
                    }
                ],
                "blocker": [
                    {
                        "pose_id": "block_first_output_front",
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [(0, 2)],
                        "input_port_cells": [],
                        "output_port_cells": [],
                    }
                ],
            }

    owner = Owner()
    delegate = PoseBoolExactMasterDelegate(owner)
    core = owner.model.NewBoolVar("core")
    blocker = owner.model.NewBoolVar("blocker")
    delegate.x_vars[("g_core", 0)] = core
    delegate.x_vars[("g_blocker", 0)] = blocker
    delegate._mandatory_template_by_group["g_core"] = "protocol_core"
    delegate._mandatory_operation_by_group["g_core"] = "protocol_core"
    delegate._mandatory_template_by_group["g_blocker"] = "blocker"
    delegate._mandatory_operation_by_group["g_blocker"] = "power_supply"
    owner.model.Add(core == 1)
    owner.model.Add(blocker == 1)

    placement_solution = {
        "core_001": {
            "facility_type": "protocol_core",
            "operation_type": "protocol_core",
            "pose_idx": 0,
        },
        "blocker_001": {
            "facility_type": "blocker",
            "operation_type": "power_supply",
            "pose_idx": 0,
        },
    }
    instances = [
        {
            "instance_id": "core_001",
            "facility_type": "protocol_core",
            "operation_type": "protocol_core",
            "is_mandatory": True,
        },
        {
            "instance_id": "blocker_001",
            "facility_type": "blocker",
            "operation_type": "power_supply",
            "is_mandatory": True,
        },
    ]
    routing_context = build_routing_binding_context(
        placement_solution,
        owner.facility_pools,
        owner.grid_w,
        owner.grid_h,
    )
    binding_model = PortBindingModel(
        placement_solution,
        owner.facility_pools,
        instances,
        required_generic_outputs={"source_ore": 1},
        required_generic_inputs=CANONICAL_GENERIC_INPUTS,
        generic_output_slots_by_operation={"protocol_core": 2},
        routing_context=routing_context,
    )
    binding_model.build()

    assert binding_model.solve(time_limit_seconds=5.0) == "FEASIBLE"
    port_specs = binding_model.extract_port_specs()
    assert [spec for spec in port_specs if spec["type"] == "out"] == [
        {
            "instance_id": "core_001",
            "x": 1,
            "y": 1,
            "dir": "N",
            "type": "out",
            "commodity": "source_ore",
        }
    ]
    assert {
        spec["commodity"] for spec in port_specs if spec["type"] == "in"
    } == set(CANONICAL_GENERIC_INPUTS)

    added = delegate.add_routing_port_blocking_cell_cut(
        port_cell=(0, 1),
        direction="N",
        front_cell=(0, 2),
    )

    assert added is False
    assert cp_model.CpSolver().Solve(owner.model) in {cp_model.FEASIBLE, cp_model.OPTIMAL}


def test_pose_bool_cell_pattern_cut_keeps_saturated_generic_output_side() -> None:
    class Owner:
        def __init__(self) -> None:
            self.model = cp_model.CpModel()
            self.grid_w = 10
            self.grid_h = 10
            self.generic_io_requirements = {
                "required_generic_outputs": {"source_ore": 6},
                "required_generic_inputs": {},
            }
            self.build_stats = {}
            self._last_solution = None
            self.facility_pools = {
                "protocol_core": [
                    {
                        "pose_id": "core_six_outputs",
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [(0, 0)],
                        "input_port_cells": [],
                        "output_port_cells": [
                            {"x": x, "y": 1, "dir": "N"} for x in range(6)
                        ],
                    }
                ],
                "blocker": [
                    {
                        "pose_id": "block_first_output_front",
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [(0, 2)],
                        "input_port_cells": [],
                        "output_port_cells": [],
                    }
                ],
            }

    owner = Owner()
    delegate = PoseBoolExactMasterDelegate(owner)
    delegate.x_vars[("g_core", 0)] = owner.model.NewBoolVar("core")
    delegate.x_vars[("g_blocker", 0)] = owner.model.NewBoolVar("blocker")
    delegate._mandatory_template_by_group["g_core"] = "protocol_core"
    delegate._mandatory_operation_by_group["g_core"] = "protocol_core"
    delegate._instance_ids_by_group["g_core"] = ["core_001"]
    delegate._mandatory_template_by_group["g_blocker"] = "blocker"
    delegate._mandatory_operation_by_group["g_blocker"] = "power_supply"
    delegate._instance_ids_by_group["g_blocker"] = ["blocker_001"]

    assert delegate.add_routing_port_blocking_cell_cut(
        port_cell=(0, 1),
        direction="N",
        front_cell=(0, 2),
    ) is True


def test_pose_bool_cell_pattern_cut_refuses_unknowable_generic_output_capacity() -> None:
    """A provider group without an instance list makes capacity unknowable.

    Assuming one instance per group undercounts multi-instance groups, which
    could fake the saturation proof and over-cut; the capacity total must fail
    closed to None and the side must not be registered.
    """

    class Owner:
        def __init__(self) -> None:
            self.model = cp_model.CpModel()
            self.grid_w = 10
            self.grid_h = 10
            self.generic_io_requirements = {
                "required_generic_outputs": {"source_ore": 6},
                "required_generic_inputs": {},
            }
            self.build_stats = {}
            self._last_solution = None
            self.facility_pools = {
                "protocol_core": [
                    {
                        "pose_id": "core_six_outputs",
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [(0, 0)],
                        "input_port_cells": [],
                        "output_port_cells": [
                            {"x": x, "y": 1, "dir": "N"} for x in range(6)
                        ],
                    }
                ],
                "blocker": [
                    {
                        "pose_id": "block_first_output_front",
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [(0, 2)],
                        "input_port_cells": [],
                        "output_port_cells": [],
                    }
                ],
            }

    owner = Owner()
    delegate = PoseBoolExactMasterDelegate(owner)
    delegate.x_vars[("g_core", 0)] = owner.model.NewBoolVar("core")
    delegate.x_vars[("g_blocker", 0)] = owner.model.NewBoolVar("blocker")
    delegate._mandatory_template_by_group["g_core"] = "protocol_core"
    delegate._mandatory_operation_by_group["g_core"] = "protocol_core"
    delegate._mandatory_template_by_group["g_blocker"] = "blocker"
    delegate._mandatory_operation_by_group["g_blocker"] = "power_supply"
    delegate._instance_ids_by_group["g_blocker"] = ["blocker_001"]

    assert delegate._mandatory_generic_output_capacity_total() is None
    assert delegate.add_routing_port_blocking_cell_cut(
        port_cell=(0, 1),
        direction="N",
        front_cell=(0, 2),
    ) is False


def test_pose_bool_saturated_generic_output_keeps_final_output_front_visible() -> None:
    """Generic-output saturation does not suppress an ordinary final-product source."""

    from src.models.binding_subproblem import PortBindingModel

    required_outputs = {"source_ore": 2}
    required_inputs = CANONICAL_GENERIC_INPUTS
    facility_pools = {
        "boundary_storage_port": [
            {
                "pose_id": "bsp_a",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [(0, 0)],
                "input_port_cells": [],
                "output_port_cells": [{"x": 5, "y": 1, "dir": "N"}],
            },
            {
                "pose_id": "bsp_b",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [(2, 0)],
                "input_port_cells": [],
                "output_port_cells": [{"x": 6, "y": 1, "dir": "N"}],
            },
        ],
        "manufacturing_6x4": [
            {
                "pose_id": "capsule_maker",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [(0, 0)],
                "input_port_cells": [],
                "output_port_cells": [{"x": 0, "y": 1, "dir": "N"}],
            }
        ],
        "protocol_storage_box": [
            {
                "pose_id": "box_sink",
                "anchor": {"x": 4, "y": 4},
                "occupied_cells": [
                    (4 + dx, 4 + dy)
                    for dx in range(3)
                    for dy in range(3)
                ],
                "input_port_cells": [
                    {"x": 4 + dx, "y": 3, "dir": "S"}
                    for dx in range(3)
                ],
                "output_port_cells": [],
            }
        ],
        "blocker": [
            {
                "pose_id": "block_a_front",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [(0, 2)],
                "input_port_cells": [],
                "output_port_cells": [],
            }
        ],
    }
    placement_solution = {
        "b1": {
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "pose_idx": 0,
        },
        "b2": {
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "pose_idx": 1,
        },
        "sink1": {
            "facility_type": "protocol_storage_box",
            "operation_type": "box_sink",
            "pose_idx": 0,
        },
        "blk": {"facility_type": "blocker", "operation_type": "power_supply", "pose_idx": 0},
    }
    instances = [
        {
            "instance_id": "b1",
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "is_mandatory": True,
        },
        {
            "instance_id": "b2",
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "is_mandatory": True,
        },
        {
            "instance_id": "sink1",
            "facility_type": "protocol_storage_box",
            "operation_type": "box_sink",
            "is_mandatory": False,
        },
        {
            "instance_id": "blk",
            "facility_type": "blocker",
            "operation_type": "power_supply",
            "is_mandatory": True,
        },
    ]
    binding_model = PortBindingModel(
        placement_solution,
        facility_pools,
        instances,
        required_generic_outputs=required_outputs,
        required_generic_inputs=required_inputs,
    )
    binding_model.build()

    assert binding_model.solve(time_limit_seconds=5.0) == "FEASIBLE"
    port_specs = binding_model.extract_port_specs()
    assert [spec for spec in port_specs if spec["type"] == "out"] == [
        {
            "instance_id": "b1",
            "x": 5,
            "y": 1,
            "dir": "N",
            "type": "out",
            "commodity": "source_ore",
        },
        {
            "instance_id": "b2",
            "x": 6,
            "y": 1,
            "dir": "N",
            "type": "out",
            "commodity": "source_ore",
        },
    ]
    assert {
        spec["commodity"] for spec in port_specs if spec["type"] == "in"
    } == set(CANONICAL_GENERIC_INPUTS)

    class Owner:
        def __init__(self) -> None:
            self.model = cp_model.CpModel()
            self.grid_w = 8
            self.grid_h = 8
            self.generic_io_requirements = {
                "required_generic_outputs": required_outputs,
                "required_generic_inputs": required_inputs,
            }
            self.build_stats = {}
            self._last_solution = None
            self.facility_pools = facility_pools
            self._mandatory_groups = [
                {
                    "group_id": "g_boundary",
                    "facility_type": "boundary_storage_port",
                    "operation_type": "boundary_io",
                    "count": 2,
                    "instance_ids": ["b1", "b2"],
                },
                {
                    "group_id": "g_maker",
                    "facility_type": "manufacturing_6x4",
                    "operation_type": "filling_capsule",
                    "count": 1,
                    "instance_ids": ["maker1"],
                },
                {
                    "group_id": "g_blocker",
                    "facility_type": "blocker",
                    "operation_type": "power_supply",
                    "count": 1,
                    "instance_ids": ["blk"],
                },
            ]

    owner = Owner()
    delegate = PoseBoolExactMasterDelegate(owner)
    b1_var = owner.model.NewBoolVar("b1_pose")
    b2_var = owner.model.NewBoolVar("b2_pose")
    maker_var = owner.model.NewBoolVar("maker_pose")
    blocker_var = owner.model.NewBoolVar("blocker_pose")
    delegate.x_vars[("g_boundary", 0)] = b1_var
    delegate.x_vars[("g_boundary", 1)] = b2_var
    delegate.x_vars[("g_maker", 0)] = maker_var
    delegate.x_vars[("g_blocker", 0)] = blocker_var
    delegate._mandatory_template_by_group["g_boundary"] = "boundary_storage_port"
    delegate._mandatory_operation_by_group["g_boundary"] = "boundary_io"
    delegate._instance_ids_by_group["g_boundary"] = ["b1", "b2"]
    delegate._mandatory_template_by_group["g_maker"] = "manufacturing_6x4"
    delegate._mandatory_operation_by_group["g_maker"] = "filling_capsule"
    delegate._instance_ids_by_group["g_maker"] = ["maker1"]
    delegate._mandatory_template_by_group["g_blocker"] = "blocker"
    delegate._mandatory_operation_by_group["g_blocker"] = "power_supply"
    delegate._instance_ids_by_group["g_blocker"] = ["blk"]
    owner.model.Add(b1_var == 1)
    owner.model.Add(b2_var == 1)
    owner.model.Add(maker_var == 1)
    owner.model.Add(blocker_var == 1)

    assert delegate._generic_output_slots_are_globally_saturated() is True
    assert delegate._routing_visible_profile_demands("boundary_io") == (0, 1)
    assert delegate._routing_visible_profile_demands("filling_capsule") == (4, 1)
    assert delegate.add_routing_port_blocking_cell_cut(
        port_cell=(0, 1),
        direction="N",
        front_cell=(0, 2),
    ) is True
    assert cp_model.CpSolver().Solve(owner.model) == cp_model.INFEASIBLE


def test_separator_capacity_classification_keeps_final_sources_with_empty_rfsc_ssot() -> None:
    sep = Separator(
        sep_id="V_5",
        kind="axis_V",
        wall_cells=frozenset({(5, y) for y in range(70)}),
        is_left_of_wall=lambda x, _y: x < 5,
    )
    pose = {
        "input_port_cells": [{"x": 10, "y": 0, "dir": "E"}],
        "output_port_cells": [{"x": 3, "y": 0, "dir": "E"}],
    }

    rfsc = routing_free_sink_commodities_from_generic_inputs(CANONICAL_GENERIC_INPUTS)
    assert rfsc == frozenset()
    classified = classify_pose_commodity_side(
        "filling_capsule",
        pose,
        sep,
        70,
        70,
        routing_free_sink_commodities=set(rfsc),
    )

    assert classified["qiaoyu_capsule"].source_side == "L"
    assert {"fine_buckwheat_powder", "steel_bottle"}.issubset(classified)
