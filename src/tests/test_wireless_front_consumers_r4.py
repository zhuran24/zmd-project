import copy
import json
from pathlib import Path

import pytest
from ortools.sat.python import cp_model

from src.interchange.preprocess_context import build_preprocess_context_from_rules_and_plan
from src.models.pose_bool_exact_master import PoseBoolExactMasterDelegate
from src.models.separator_capacity_hull import Separator, classify_pose_commodity_side
from src.search.routing_deletion_core_minimizer import (
    _oracle_front_blocked,
    build_routing_visible_port_keys_by_instance,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


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
                "output_port_cells": [{"x": 0, "y": 0, "dir": "E"}],
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

    assert _oracle_front_blocked(layout, facility_pools, 70, 70)

    visible_ports = build_routing_visible_port_keys_by_instance([])
    assert not _oracle_front_blocked(
        layout,
        facility_pools,
        70,
        70,
        routing_visible_port_keys_by_instance=visible_ports,
    )


def test_pose_bool_front_caches_exclude_routing_free_output_side() -> None:
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

    assert delegate._routing_visible_profile_demands("filling_capsule") == (4, 0)

    delegate._build_port_lookup_cache()
    assert (5, 5, "E") in delegate._poses_by_port_at_cell_dir
    assert (5, 5, "W") in delegate._routing_visible_poses_by_port_at_cell_dir
    assert (5, 5, "E") not in delegate._routing_visible_poses_by_port_at_cell_dir


def test_pose_bool_visible_cache_is_conservative_for_mixed_output_side(monkeypatch: pytest.MonkeyPatch) -> None:
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

    assert delegate._routing_visible_profile_demands("mixed_output") == (0, 1)

    delegate._build_port_lookup_cache()
    assert (5, 5, "E") in delegate._poses_by_port_at_cell_dir
    assert (6, 5, "E") in delegate._poses_by_port_at_cell_dir
    assert not delegate._routing_visible_poses_by_port_at_cell_dir


def test_separator_capacity_classification_excludes_routing_free_sources() -> None:
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

    unfiltered = classify_pose_commodity_side(
        "filling_capsule", pose, sep, 70, 70
    )
    filtered = classify_pose_commodity_side(
        "filling_capsule",
        pose,
        sep,
        70,
        70,
        routing_free_sink_commodities={"qiaoyu_capsule"},
    )

    assert "qiaoyu_capsule" in unfiltered
    assert "qiaoyu_capsule" not in filtered
    assert {"fine_buckwheat_powder", "steel_bottle"}.issubset(filtered)
