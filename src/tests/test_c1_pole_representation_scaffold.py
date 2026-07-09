"""Batch 1A scaffold tests for C1 native power-pole pose bools."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import pytest
from ortools.sat.python import cp_model

from src.models._cpsat_compat import cp_model_from_proto
from src.models.master_model import MasterPlacementModel


def _coverage_cells(
    x_val: int,
    y_val: int,
    *,
    width: int,
    height: int,
    radius: int = 1,
) -> List[List[int]]:
    return [
        [x, y]
        for x in range(
            max(0, int(x_val) - int(radius)),
            min(int(width) - 1, int(x_val) + 2 + int(radius) - 1) + 1,
        )
        for y in range(
            max(0, int(y_val) - int(radius)),
            min(int(height) - 1, int(y_val) + 2 + int(radius) - 1) + 1,
        )
    ]


def _power_pole_pool(width: int = 3, height: int = 3) -> List[Dict[str, Any]]:
    return [
        {
            "pose_id": f"pole_{x}_{y}",
            "anchor": {"x": x, "y": y},
            "pose_params": {"orientation": "north", "port_mode": "none"},
            "occupied_cells": [[x, y]],
            "input_port_cells": [],
            "output_port_cells": [],
            "power_coverage_cells": _coverage_cells(x, y, width=width, height=height),
        }
        for y in range(int(height))
        for x in range(int(width))
    ]


def _machine_pool(x_val: int = 0, y_val: int = 0) -> List[Dict[str, Any]]:
    return [
        {
            "pose_id": f"machine_{x_val}_{y_val}",
            "anchor": {"x": int(x_val), "y": int(y_val)},
            "pose_params": {"orientation": "north", "port_mode": "none"},
            "occupied_cells": [[int(x_val), int(y_val)]],
            "input_port_cells": [],
            "output_port_cells": [],
            "power_coverage_cells": None,
        }
    ]


def _rules(
    *,
    width: int = 3,
    height: int = 3,
    machine_needs_power: bool = True,
) -> Dict[str, Any]:
    return {
        "globals": {"grid": {"width": int(width), "height": int(height)}},
        "facility_templates": {
            "machine": {
                "dimensions": {"w": 1, "h": 1},
                "needs_power": bool(machine_needs_power),
            },
            "power_pole": {
                "dimensions": {"w": 1, "h": 1},
                "needs_power": False,
                "power_coverage_radius": 1,
            },
        },
    }


def _machine_instances() -> List[Dict[str, Any]]:
    return [
        {
            "instance_id": "machine_001",
            "facility_type": "machine",
            "operation_type": "crafting",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]


def _build_c1_core(
    *,
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    rules: Mapping[str, Any],
    instances: Optional[Sequence[Mapping[str, Any]]] = None,
):
    return MasterPlacementModel.build_exact_core(
        instances if instances is not None else _machine_instances(),
        {str(tpl): [dict(pose) for pose in pool] for tpl, pool in pools.items()},
        rules,
        skip_power_coverage=True,
        c1_power_pole_representation=True,
    )


def _proto_variable_names_by_index(proto: Any) -> Dict[int, str]:
    return {int(idx): str(var.name) for idx, var in enumerate(proto.variables)}


def _clone_proto(proto: Any) -> Any:
    cloned = proto.__class__()
    if hasattr(cloned, "CopyFrom"):
        cloned.CopyFrom(proto)
    else:
        cloned.copy_from(proto)
    return cloned


def _has_sum_upper_bound(
    proto: Any,
    *,
    bool_indices: Iterable[int],
    upper_bound: int,
) -> bool:
    target_indices = {int(idx) for idx in bool_indices}
    for constraint in proto.constraints:
        linear = constraint.linear
        if {int(idx) for idx in linear.vars} != target_indices:
            continue
        if any(int(coeff) != 1 for coeff in linear.coeffs):
            continue
        domain = [int(value) for value in linear.domain]
        if len(domain) >= 2 and int(domain[-1]) == int(upper_bound):
            return True
    return False


def _has_family_count_sum_equality(
    proto: Any,
    *,
    count_var_index: int,
    expected_bool_indices: Iterable[int],
) -> bool:
    expected_bool_index_set = {int(idx) for idx in expected_bool_indices}
    for constraint in proto.constraints:
        linear = constraint.linear
        vars_by_coeff = {
            int(var_idx): int(coeff)
            for var_idx, coeff in zip(linear.vars, linear.coeffs)
        }
        if int(count_var_index) not in vars_by_coeff:
            continue
        other_vars = set(vars_by_coeff) - {int(count_var_index)}
        if other_vars != expected_bool_index_set:
            continue
        domain = [int(value) for value in linear.domain]
        if domain != [0, 0]:
            continue
        count_coeff = int(vars_by_coeff[int(count_var_index)])
        other_coeffs = {int(vars_by_coeff[var_idx]) for var_idx in other_vars}
        if count_coeff == -1 and other_coeffs == {1}:
            return True
        if count_coeff == 1 and other_coeffs == {-1}:
            return True
    return False


def _expected_family_bool_indices(
    master: MasterPlacementModel,
    family_name: str,
) -> List[int]:
    delegate = master._coordinate_delegate
    assert delegate is not None
    expected: List[int] = []
    for pose_idx, var, _coverage in delegate._c1_pole_bools:
        family_id = delegate._power_pole_family_id_by_pose_idx.get(int(pose_idx))
        if family_id is None:
            continue
        pose_family_name = delegate._power_pole_family_name_by_int[int(family_id)]
        if str(pose_family_name) == str(family_name):
            expected.append(int(var.Index()))
    return expected


def _c1_pole_bool_for_anchor(master: MasterPlacementModel, anchor: Tuple[int, int]):
    delegate = master._coordinate_delegate
    assert delegate is not None
    for pose_idx, var, _coverage in delegate._c1_pole_bools:
        pose = master.facility_pools["power_pole"][int(pose_idx)]
        pose_anchor = dict(pose["anchor"])
        if (int(pose_anchor["x"]), int(pose_anchor["y"])) == anchor:
            return var
    raise AssertionError(f"missing C1 pole bool for anchor {anchor!r}")


def test_default_off_keeps_residual_power_pole_coordinate_slots() -> None:
    pools = {"machine": _machine_pool(), "power_pole": _power_pole_pool()}

    core = MasterPlacementModel.build_exact_core(
        _machine_instances(),
        pools,
        _rules(),
        skip_power_coverage=True,
    )

    residual_counts = core.build_stats["master_slot_counts"]["residual_optionals"]
    assert residual_counts["power_pole"] == 1
    assert any(
        str(key).startswith("residual_optional::power_pole::")
        for key in core.coordinate_binding["slot_binding"]
    )
    assert core.coordinate_binding["c1_power_pole_binding"]["enabled"] is False


def test_c1_creates_pose_bools_without_residual_power_pole_slots() -> None:
    pools = {"machine": _machine_pool(), "power_pole": _power_pole_pool()}

    core = _build_c1_core(pools=pools, rules=_rules())

    residual_counts = core.build_stats["master_slot_counts"]["residual_optionals"]
    assert "power_pole" not in residual_counts
    binding = core.coordinate_binding["c1_power_pole_binding"]
    assert binding["enabled"] is True
    assert len(binding["entries"]) == len(pools["power_pole"])
    proto_names = _proto_variable_names_by_index(core.proto)
    assert {
        proto_names[int(entry["bool_var_index"])]
        for entry in binding["entries"]
    } == {f"c1pole__{idx}" for idx in range(len(pools["power_pole"]))}
    for entry in binding["entries"]:
        assert proto_names[int(entry["bool_var_index"])] == f"c1pole__{entry['pose_idx']}"
    assert _has_sum_upper_bound(
        core.proto,
        bool_indices=[entry["bool_var_index"] for entry in binding["entries"]],
        upper_bound=1,
    )

    model = MasterPlacementModel(
        _machine_instances(),
        pools,
        _rules(),
        solve_mode="certified_exact",
        skip_power_coverage=True,
        c1_power_pole_representation=True,
    )
    model.build()
    delegate = model._coordinate_delegate
    assert delegate is not None
    assert delegate.power_pole_family_count_vars
    for family_name, count_var in delegate.power_pole_family_count_vars.items():
        assert _has_family_count_sum_equality(
            model.model.Proto(),
            count_var_index=int(count_var.Index()),
            expected_bool_indices=_expected_family_bool_indices(model, family_name),
        )


@pytest.mark.parametrize(
    "bad_pool",
    [
        [pose for pose in _power_pole_pool() if pose["anchor"] != {"x": 1, "y": 1}],
        [
            *_power_pole_pool(),
            {
                **_power_pole_pool()[0],
                "pose_id": "pole_duplicate_anchor_other_mode",
                "pose_params": {"orientation": "south", "port_mode": "none"},
            },
        ],
        [
            {
                **pose,
                "occupied_cells": [[2, 1]] if pose["anchor"] == {"x": 1, "y": 1} else pose["occupied_cells"],
            }
            for pose in _power_pole_pool()
        ],
        [
            {
                key: value
                for key, value in pose.items()
                if not (pose["anchor"] == {"x": 0, "y": 0} and key == "anchor")
            }
            for pose in _power_pole_pool()
        ],
        [
            {
                **pose,
                "anchor": {"y": 0} if pose["anchor"] == {"x": 0, "y": 0} else pose["anchor"],
            }
            for pose in _power_pole_pool()
        ],
        [
            {
                **pose,
                "power_coverage_cells": [] if pose["anchor"] == {"x": 1, "y": 1} else pose["power_coverage_cells"],
            }
            for pose in _power_pole_pool()
        ],
        [
            {
                **pose,
                "power_coverage_cells": [[0, 0]] if pose["anchor"] == {"x": 1, "y": 1} else pose["power_coverage_cells"],
            }
            for pose in _power_pole_pool()
        ],
    ],
)
def test_c1_power_pole_pool_integrity_fail_closed(
    bad_pool: Sequence[Mapping[str, Any]],
) -> None:
    with pytest.raises((RuntimeError, ValueError), match="C1|Duplicate"):
        _build_c1_core(
            pools={"machine": _machine_pool(), "power_pole": bad_pool},
            rules=_rules(),
        )


def test_c1_power_pole_pool_rejects_duplicate_pose_ids() -> None:
    duplicate_ids = [
        {**pose, "pose_id": "dup"}
        for pose in _power_pole_pool()
    ]

    with pytest.raises(RuntimeError, match="duplicate pose_id"):
        _build_c1_core(
            pools={"machine": _machine_pool(), "power_pole": duplicate_ids},
            rules=_rules(),
        )


def test_c1_bind_from_core_requires_c1_binding_when_pool_nonempty() -> None:
    pools = {"power_pole": _power_pole_pool()}
    rules = _rules(machine_needs_power=False)
    core = _build_c1_core(pools=pools, rules=rules, instances=[])
    model = MasterPlacementModel(
        [],
        pools,
        rules,
        solve_mode="certified_exact",
        skip_power_coverage=True,
        c1_power_pole_representation=True,
    )
    model.model = cp_model_from_proto(_clone_proto(core.proto))
    delegate = model._coordinate_delegate
    assert delegate is not None
    delegate.model = model.model

    missing_binding = {
        key: value
        for key, value in core.coordinate_binding.items()
        if key != "c1_power_pole_binding"
    }
    with pytest.raises(RuntimeError, match="C1 power_pole binding"):
        delegate.bind_from_core(missing_binding)

    disabled_binding = dict(core.coordinate_binding)
    disabled_binding["c1_power_pole_binding"] = {"enabled": False, "entries": []}
    with pytest.raises(RuntimeError, match="C1 power_pole binding"):
        delegate.bind_from_core(disabled_binding)


def test_c1_clone_rebinds_intervals_for_ghost_overlay_no_overlap() -> None:
    pools = {
        "machine": _machine_pool(0, 0),
        "power_pole": _power_pole_pool(width=5, height=5),
    }
    rules = _rules(width=5, height=5, machine_needs_power=True)
    core = _build_c1_core(pools=pools, rules=rules, instances=_machine_instances())

    blocked = MasterPlacementModel.from_exact_core(
        core,
        ghost_rect=(1, 1),
        ghost_anchor_filter=[(1, 1)],
    )
    blocked.model.Add(_c1_pole_bool_for_anchor(blocked, (1, 1)) == 1)
    assert blocked.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE

    clear = MasterPlacementModel.from_exact_core(
        core,
        ghost_rect=(1, 1),
        ghost_anchor_filter=[(4, 4)],
    )
    clear.model.Add(_c1_pole_bool_for_anchor(clear, (1, 1)) == 1)
    assert clear.solve(time_limit_seconds=5.0) in {cp_model.OPTIMAL, cp_model.FEASIBLE}


def test_c1_required_power_pole_uses_pose_bool_pool() -> None:
    model = MasterPlacementModel(
        _machine_instances(),
        {
            "machine": _machine_pool(),
            "power_pole": _power_pole_pool(width=2, height=1),
        },
        _rules(width=2, height=1),
        solve_mode="certified_exact",
        skip_power_coverage=True,
        c1_power_pole_representation=True,
        exact_required_pose_optional_counts={"power_pole": 1},
    )

    assert model.solve(time_limit_seconds=2.0) in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    delegate = model._coordinate_delegate
    assert delegate is not None
    assert "power_pole" not in delegate.required_optional_slots
    assert "power_pole" not in delegate.residual_optional_slots
    assert sum(
        model._solver.Value(var) for _pose_idx, var, _coverage in delegate._c1_pole_bools
    ) == 1


def test_c1_coverage_path_builds_cov_channel_stats() -> None:
    model = MasterPlacementModel(
        instances=[],
        facility_pools={"power_pole": _power_pole_pool()},
        rules=_rules(machine_needs_power=False),
        solve_mode="certified_exact",
        skip_power_coverage=False,
        c1_power_pole_representation=True,
    )

    model.build()

    power_coverage = model.build_stats["power_coverage"]
    assert power_coverage["representation"] == "coordinate_geometric"
    assert power_coverage["encoding"] == "c1_pose_bool_cov_channel_v1"
    assert power_coverage["powered_slots"] == 0
    assert power_coverage["pole_pose_bools"] == 9
    assert power_coverage["cov_channel_literals"] == 9
