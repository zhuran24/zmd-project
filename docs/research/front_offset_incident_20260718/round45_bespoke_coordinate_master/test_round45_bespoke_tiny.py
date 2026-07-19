"""Tiny solving sentinels for the Round 4/5 encoding helpers.

These models contain only a handful of variables.  They intentionally exercise
the same helper functions used by the full 266-slot research model without ever
starting a canonical full-pool solve.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Sequence

import pytest
from ortools.sat.python import cp_model


RESEARCH_DIR = Path(__file__).resolve().parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

import compact_model  # noqa: E402


def _status(model: cp_model.CpModel) -> int:
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.log_search_progress = False
    return solver.Solve(model)


def _fixed(model: cp_model.CpModel, value: int, name: str) -> Any:
    return model.NewIntVar(value, value, name)


def _provider(
    model: cp_model.CpModel,
    *,
    key: str,
    x: int,
    y: int,
    ports: Sequence[tuple[int, int, str]],
    optional: bool,
) -> compact_model._FacilitySlot:
    active = model.NewBoolVar(f"active__{key}") if optional else None
    x_var = _fixed(model, x, f"x__{key}")
    y_var = _fixed(model, y, f"y__{key}")
    mode = _fixed(model, 0, f"mode__{key}")
    order = _fixed(model, x * 70 + y, f"order__{key}")
    x_end = _fixed(model, x + 1, f"body_x_end__{key}")
    y_end = _fixed(model, y + 1, f"body_y_end__{key}")
    if active is None:
        x_interval = model.NewIntervalVar(x_var, 1, x_end, f"body_x_iv__{key}")
        y_interval = model.NewIntervalVar(y_var, 1, y_end, f"body_y_iv__{key}")
    else:
        x_interval = model.NewOptionalIntervalVar(x_var, 1, x_end, active, f"body_x_iv__{key}")
        y_interval = model.NewOptionalIntervalVar(y_var, 1, y_end, active, f"body_y_iv__{key}")
    return compact_model._FacilitySlot(
        key=key,
        template=key,
        operation_type="tiny",
        group_id=None,
        slot_index=0,
        active=active,
        x=x_var,
        y=y_var,
        mode=mode,
        order=order,
        body_x_start=x_var,
        body_y_start=y_var,
        body_x_end=x_end,
        body_y_end=y_end,
        x_interval=x_interval,
        y_interval=y_interval,
        modes={0: {"input": tuple(ports)}},
        tuple_to_pose={},
        needs_power=optional,
    )


def _provider_case(
    owner_pair: tuple[int, int],
    *,
    shared_core_front: bool = False,
    equal_keys: bool = False,
) -> tuple[cp_model.CpModel, compact_model._GenericFrontEncoding]:
    model = cp_model.CpModel()
    core_ports = (
        ((1, 0, "E"), (1, 0, "N"))
        if shared_core_front
        else ((1, 0, "E"), (0, 1, "N"))
    )
    providers = [
        _provider(model, key="core", x=10, y=10, ports=core_ports, optional=False),
        _provider(
            model,
            key="box0",
            x=20,
            y=10,
            ports=((1, 0, "E"), (0, 1, "N")),
            optional=True,
        ),
        _provider(
            model,
            key="box1",
            x=30,
            y=10,
            ports=((1, 0, "E"), (0, 1, "N")),
            optional=True,
        ),
    ]
    encoding = compact_model._add_generic_input_witnesses(
        model,
        providers=providers,
        commodities=("commodity_a", "commodity_b"),
        body_x_intervals=[provider.x_interval for provider in providers],
        body_y_intervals=[provider.y_interval for provider in providers],
    )
    for witness, owner in zip(encoding.witnesses, owner_pair):
        model.Add(witness["owner"] == owner)
    if equal_keys:
        model.Add(encoding.keys[0] == encoding.keys[1])
    return model, encoding


@pytest.mark.parametrize("owners", ((0, 0), (0, 1), (1, 0), (1, 1), (1, 2)))
def test_tiny_core_and_box_provider_combinations_are_feasible(
    owners: tuple[int, int],
) -> None:
    model, _encoding = _provider_case(owners)
    assert _status(model) in (cp_model.FEASIBLE, cp_model.OPTIMAL)


def test_same_provider_requires_distinct_physical_slots() -> None:
    model, _encoding = _provider_case((0, 0), equal_keys=True)
    assert _status(model) == cp_model.INFEASIBLE


def test_labeled_generic_inputs_have_no_cross_commodity_order_symmetry() -> None:
    model, encoding = _provider_case((1, 1))
    model.Add(encoding.keys[0] > encoding.keys[1])
    assert _status(model) in (cp_model.FEASIBLE, cp_model.OPTIMAL)


def test_distinct_physical_ports_may_share_one_front_cell() -> None:
    model, encoding = _provider_case((0, 0), shared_core_front=True)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    assert solver.Solve(model) in (cp_model.FEASIBLE, cp_model.OPTIMAL)
    assert solver.Value(encoding.keys[0]) != solver.Value(encoding.keys[1])
    assert (
        solver.Value(encoding.witnesses[0]["x"]),
        solver.Value(encoding.witnesses[0]["y"]),
    ) == (
        solver.Value(encoding.witnesses[1]["x"]),
        solver.Value(encoding.witnesses[1]["y"]),
    )


def test_unselected_out_of_grid_port_does_not_remove_pose() -> None:
    model = cp_model.CpModel()
    provider = _provider(
        model,
        key="edge",
        x=0,
        y=5,
        ports=((-1, 0, "W"), (1, 0, "E")),
        optional=False,
    )
    encoding = compact_model._add_generic_input_witnesses(
        model,
        providers=[provider],
        commodities=("selected_in_grid",),
        body_x_intervals=[provider.x_interval],
        body_y_intervals=[provider.y_interval],
    )
    solver = cp_model.CpSolver()
    assert solver.Solve(model) in (cp_model.FEASIBLE, cp_model.OPTIMAL)
    assert solver.Value(encoding.keys[0]) == 1

    rejected = cp_model.CpModel()
    rejected_provider = _provider(
        rejected,
        key="edge",
        x=0,
        y=5,
        ports=((-1, 0, "W"), (1, 0, "E")),
        optional=False,
    )
    rejected_encoding = compact_model._add_generic_input_witnesses(
        rejected,
        providers=[rejected_provider],
        commodities=("selected_oob",),
        body_x_intervals=[rejected_provider.x_interval],
        body_y_intervals=[rejected_provider.y_interval],
    )
    rejected.Add(rejected_encoding.keys[0] == 0)
    assert _status(rejected) == cp_model.INFEASIBLE


def test_identity_front_uses_stored_cell_not_direction_offset() -> None:
    pose = {
        "pose_id": "identity_sentinel",
        "anchor": {"x": 10, "y": 10},
        "occupied_cells": [{"x": 10, "y": 10}],
        "input_port_cells": [{"x": 11, "y": 10, "dir": "E"}],
    }
    assert compact_model._relative_port_pattern(pose, "input_port_cells") == ((1, 0, "E"),)
    model = cp_model.CpModel()
    provider = _provider(
        model,
        key="identity",
        x=10,
        y=10,
        ports=compact_model._relative_port_pattern(pose, "input_port_cells"),
        optional=False,
    )
    encoding = compact_model._add_generic_input_witnesses(
        model,
        providers=[provider],
        commodities=("identity",),
        body_x_intervals=[provider.x_interval],
        body_y_intervals=[provider.y_interval],
    )
    solver = cp_model.CpSolver()
    assert solver.Solve(model) in (cp_model.FEASIBLE, cp_model.OPTIMAL)
    assert solver.Value(encoding.witnesses[0]["x"]) == 11
    assert solver.Value(encoding.witnesses[0]["y"]) == 10


def test_front_may_overlap_ghost_but_not_a_body() -> None:
    model = cp_model.CpModel()
    provider = _provider(
        model,
        key="core",
        x=10,
        y=10,
        ports=((1, 0, "E"),),
        optional=False,
    )
    ghost_x = _fixed(model, 11, "ghost_x")
    ghost_y = _fixed(model, 10, "ghost_y")
    ghost_x_end = _fixed(model, 12, "ghost_x_end")
    ghost_y_end = _fixed(model, 11, "ghost_y_end")
    ghost_x_iv = model.NewIntervalVar(ghost_x, 1, ghost_x_end, "ghost_x_iv")
    ghost_y_iv = model.NewIntervalVar(ghost_y, 1, ghost_y_end, "ghost_y_iv")
    model.AddNoOverlap2D(
        [provider.x_interval, ghost_x_iv],
        [provider.y_interval, ghost_y_iv],
    )
    compact_model._add_generic_input_witnesses(
        model,
        providers=[provider],
        commodities=("front_on_ghost",),
        body_x_intervals=[provider.x_interval],
        body_y_intervals=[provider.y_interval],
    )
    assert _status(model) in (cp_model.FEASIBLE, cp_model.OPTIMAL)

    blocked = cp_model.CpModel()
    blocked_provider = _provider(
        blocked,
        key="core",
        x=10,
        y=10,
        ports=((1, 0, "E"),),
        optional=False,
    )
    blocker = _provider(
        blocked,
        key="blocker",
        x=11,
        y=10,
        ports=((1, 0, "E"),),
        optional=False,
    )
    compact_model._add_generic_input_witnesses(
        blocked,
        providers=[blocked_provider],
        commodities=("front_on_body",),
        body_x_intervals=[blocked_provider.x_interval, blocker.x_interval],
        body_y_intervals=[blocked_provider.y_interval, blocker.y_interval],
    )
    assert _status(blocked) == cp_model.INFEASIBLE


@pytest.mark.parametrize(
    ("box_active", "pole_active", "pole_xy", "expected"),
    (
        (0, 0, (5, 5), cp_model.OPTIMAL),
        (1, 0, (5, 5), cp_model.INFEASIBLE),
        (1, 1, (5, 5), cp_model.OPTIMAL),
        (1, 1, (50, 50), cp_model.INFEASIBLE),
    ),
)
def test_optional_box_power_witness_is_conditionally_enforced(
    box_active: int,
    pole_active: int,
    pole_xy: tuple[int, int],
    expected: int,
) -> None:
    model = cp_model.CpModel()
    box = _provider(
        model,
        key="box",
        x=10,
        y=10,
        ports=((1, 0, "E"),),
        optional=True,
    )
    active = model.NewBoolVar("pole_active")
    pole_x = _fixed(model, pole_xy[0], "pole_x")
    pole_y = _fixed(model, pole_xy[1], "pole_y")
    pole_x_end = _fixed(model, pole_xy[0] + 2, "pole_x_end")
    pole_y_end = _fixed(model, pole_xy[1] + 2, "pole_y_end")
    pole = compact_model._PoleSlot(
        index=0,
        active=active,
        x=pole_x,
        y=pole_y,
        order=_fixed(model, 350, "pole_order"),
        x_interval=model.NewOptionalIntervalVar(pole_x, 2, pole_x_end, active, "pole_x_iv"),
        y_interval=model.NewOptionalIntervalVar(pole_y, 2, pole_y_end, active, "pole_y_iv"),
    )
    compact_model._add_designated_power_witness(model, slot=box, pole_slots=[pole])
    model.Add(box.active == box_active)
    model.Add(active == pole_active)
    assert _status(model) == expected


def test_safe_symmetry_orders_only_interchangeable_slots() -> None:
    mandatory = cp_model.CpModel()
    left = _fixed(mandatory, 2, "mandatory_left")
    right = _fixed(mandatory, 5, "mandatory_right")
    assert compact_model._add_unconditional_strict_order(mandatory, [left, right]) == 1
    assert _status(mandatory) == cp_model.OPTIMAL

    reversed_mandatory = cp_model.CpModel()
    left = _fixed(reversed_mandatory, 5, "mandatory_left")
    right = _fixed(reversed_mandatory, 2, "mandatory_right")
    compact_model._add_unconditional_strict_order(reversed_mandatory, [left, right])
    assert _status(reversed_mandatory) == cp_model.INFEASIBLE

    optional = cp_model.CpModel()
    slots = []
    for index, (is_active, order) in enumerate(((1, 2), (1, 5))):
        slots.append(
            type(
                "TinySlot",
                (),
                {
                    "active": _fixed(optional, is_active, f"active_{index}"),
                    "order": _fixed(optional, order, f"order_{index}"),
                },
            )()
        )
    assert compact_model._add_active_prefix_strict_order(optional, slots) == 1
    assert _status(optional) == cp_model.OPTIMAL

    bad_prefix = cp_model.CpModel()
    slots = []
    for index, (is_active, order) in enumerate(((0, 2), (1, 5))):
        slots.append(
            type(
                "TinySlot",
                (),
                {
                    "active": _fixed(bad_prefix, is_active, f"active_{index}"),
                    "order": _fixed(bad_prefix, order, f"order_{index}"),
                },
            )()
        )
    compact_model._add_active_prefix_strict_order(bad_prefix, slots)
    assert _status(bad_prefix) == cp_model.INFEASIBLE

    inactive_tail = cp_model.CpModel()
    slots = []
    for index, (is_active, order) in enumerate(((1, 5), (0, 2))):
        slots.append(
            type(
                "TinySlot",
                (),
                {
                    "active": _fixed(inactive_tail, is_active, f"active_{index}"),
                    "order": _fixed(inactive_tail, order, f"order_{index}"),
                },
            )()
        )
    compact_model._add_active_prefix_strict_order(inactive_tail, slots)
    assert _status(inactive_tail) == cp_model.OPTIMAL
