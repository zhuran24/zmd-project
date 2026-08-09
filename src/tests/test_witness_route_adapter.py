"""Focused tests for the research-only strict route adapter."""

from __future__ import annotations

import importlib
from itertools import combinations
from typing import Any

import pytest


route_adapter = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.route_adapter"
)

RouteAdapterError = route_adapter.RouteAdapterError
adapt_extracted_routes = route_adapter.adapt_extracted_routes
add_l1_support_constraints = route_adapter.add_l1_support_constraints
build_l1_support_contract = route_adapter.build_l1_support_contract

DIRECTIONS = ("N", "E", "S", "W")
OPPOSITE = {"N": "S", "E": "W", "S": "N", "W": "E"}


def _route(
    x: int,
    y: int,
    *,
    layer: int,
    component_type: str,
    flow_in: tuple[str, ...],
    flow_out: tuple[str, ...],
    commodities: tuple[str, ...] = ("commodity",),
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "x": x,
        "y": y,
        "layer": layer,
        "type": component_type,
        "component_type": component_type,
        "flow_in": list(flow_in),
        "flow_out": list(flow_out),
        "commodities": list(commodities),
        "uses": [
            {
                "commodity": commodity,
                "flow_in": list(flow_in),
                "flow_out": list(flow_out),
            }
            for commodity in commodities
        ],
        "flow": {"flow_in": list(flow_in), "flow_out": list(flow_out)},
    }
    if len(commodities) == 1:
        record["commodity"] = commodities[0]
    if len(flow_in) == 1:
        record["dir_in"] = flow_in[0]
    if len(flow_out) == 1:
        record["dir_out"] = flow_out[0]
    return record


def _variant_signature(component: dict[str, Any]) -> tuple[Any, ...]:
    if component["kind"] == "cross":
        return (
            "cross",
            tuple(
                (tuple(channel["inputs"]), tuple(channel["outputs"]))
                for channel in component["channels"]
            ),
        )
    return (
        component["kind"],
        tuple(component["inputs"]),
        tuple(component["outputs"]),
    )


def test_adapter_covers_all_48_directed_strict_variants() -> None:
    components: list[dict[str, Any]] = []
    cell_index = 0

    for direction_in in DIRECTIONS:
        components.extend(
            adapt_extracted_routes(
                [
                    _route(
                        cell_index,
                        0,
                        layer=0,
                        component_type="belt",
                        flow_in=(direction_in,),
                        flow_out=(OPPOSITE[direction_in],),
                    )
                ]
            )
        )
        cell_index += 1

    for direction_in in DIRECTIONS:
        for direction_out in DIRECTIONS:
            if direction_out in (direction_in, OPPOSITE[direction_in]):
                continue
            components.extend(
                adapt_extracted_routes(
                    [
                        _route(
                            cell_index,
                            0,
                            layer=0,
                            component_type="belt",
                            flow_in=(direction_in,),
                            flow_out=(direction_out,),
                        )
                    ]
                )
            )
            cell_index += 1

    for direction_in in DIRECTIONS:
        remaining = tuple(direction for direction in DIRECTIONS if direction != direction_in)
        for output_count in (2, 3):
            for outputs in combinations(remaining, output_count):
                components.extend(
                    adapt_extracted_routes(
                        [
                            _route(
                                cell_index,
                                0,
                                layer=0,
                                component_type="splitter",
                                flow_in=(direction_in,),
                                flow_out=outputs,
                            )
                        ]
                    )
                )
                cell_index += 1

    for direction_out in DIRECTIONS:
        remaining = tuple(direction for direction in DIRECTIONS if direction != direction_out)
        for input_count in (2, 3):
            for inputs in combinations(remaining, input_count):
                components.extend(
                    adapt_extracted_routes(
                        [
                            _route(
                                cell_index,
                                0,
                                layer=0,
                                component_type="merger",
                                flow_in=inputs,
                                flow_out=(direction_out,),
                            )
                        ]
                    )
                )
                cell_index += 1

    for horizontal_in in ("E", "W"):
        for vertical_in in ("N", "S"):
            components.extend(
                adapt_extracted_routes(
                    [
                        _route(
                            cell_index,
                            0,
                            layer=0,
                            component_type="belt",
                            flow_in=(horizontal_in,),
                            flow_out=(OPPOSITE[horizontal_in],),
                        ),
                        _route(
                            cell_index,
                            0,
                            layer=1,
                            component_type="bridge",
                            flow_in=(vertical_in,),
                            flow_out=(OPPOSITE[vertical_in],),
                        ),
                    ]
                )
            )
            cell_index += 1

    by_kind: dict[str, int] = {}
    for component in components:
        by_kind[component["kind"]] = by_kind.get(component["kind"], 0) + 1

    assert by_kind == {"straight": 4, "turn": 8, "splitter": 16, "merger": 16, "cross": 4}
    assert len(components) == 48
    assert len({_variant_signature(component) for component in components}) == 48


def test_cross_keeps_horizontal_and_vertical_channels_isolated() -> None:
    components = adapt_extracted_routes(
        [
            _route(
                9,
                7,
                layer=0,
                component_type="belt",
                flow_in=("N",),
                flow_out=("S",),
                commodities=("vertical_a", "vertical_b"),
            ),
            _route(
                9,
                7,
                layer=1,
                component_type="bridge",
                flow_in=("W",),
                flow_out=("E",),
                commodities=("horizontal",),
            ),
        ]
    )

    assert components == [
        {
            "cell": {"x": 9, "y": 7},
            "kind": "cross",
            "channels": [
                {"inputs": ["W"], "outputs": ["E"], "commodities": ["horizontal"]},
                {
                    "inputs": ["N"],
                    "outputs": ["S"],
                    "commodities": ["vertical_a", "vertical_b"],
                },
            ],
        }
    ]
    cross = components[0]
    assert "inputs" not in cross
    assert "outputs" not in cross
    assert "commodities" not in cross
    assert set(cross["channels"][0]["commodities"]).isdisjoint(cross["channels"][1]["commodities"])


@pytest.mark.parametrize("ground_type", ["belt", "splitter", "merger"])
def test_adapter_rejects_non_straight_l0_cross(ground_type: str) -> None:
    if ground_type == "belt":
        ground = _route(
            3,
            4,
            layer=0,
            component_type="belt",
            flow_in=("W",),
            flow_out=("N",),
        )
    elif ground_type == "splitter":
        ground = _route(
            3,
            4,
            layer=0,
            component_type="splitter",
            flow_in=("W",),
            flow_out=("N", "E"),
        )
    else:
        ground = _route(
            3,
            4,
            layer=0,
            component_type="merger",
            flow_in=("N", "E"),
            flow_out=("W",),
        )
    elevated = _route(
        3,
        4,
        layer=1,
        component_type="bridge",
        flow_in=("N",),
        flow_out=("S",),
    )

    with pytest.raises(RouteAdapterError, match="NON_STRAIGHT_CROSS") as exc_info:
        adapt_extracted_routes([ground, elevated])
    assert exc_info.value.code == "NON_STRAIGHT_CROSS"


@pytest.mark.parametrize(
    ("routes", "terminal_cells", "error_code"),
    [
        (
            [_route(1, 1, layer=1, component_type="bridge", flow_in=("N",), flow_out=("S",))],
            (),
            "STANDALONE_L1",
        ),
        (
            [
                _route(1, 1, layer=0, component_type="belt", flow_in=("N",), flow_out=("S",)),
                _route(1, 1, layer=1, component_type="bridge", flow_in=("S",), flow_out=("N",)),
            ],
            (),
            "SAME_AXIS_CROSS",
        ),
        (
            [
                _route(1, 1, layer=0, component_type="belt", flow_in=("E",), flow_out=("W",)),
                _route(1, 1, layer=1, component_type="bridge", flow_in=("N",), flow_out=("S",)),
            ],
            ((1, 1),),
            "TERMINAL_ON_L1",
        ),
        (
            [
                _route(1, 1, layer=0, component_type="belt", flow_in=("E",), flow_out=("W",)),
                _route(1, 1, layer=0, component_type="belt", flow_in=("W",), flow_out=("E",)),
            ],
            (),
            "DUPLICATE_LAYER_STATE",
        ),
        (
            [_route(1, 1, layer=0, component_type="mystery", flow_in=("E",), flow_out=("W",))],
            (),
            "UNKNOWN_COMPONENT_TYPE",
        ),
        (
            [_route(1, 1, layer=2, component_type="bridge", flow_in=("N",), flow_out=("S",))],
            (),
            "UNKNOWN_LAYER",
        ),
        (
            [_route(1, 1, layer=1, component_type="bridge", flow_in=("N",), flow_out=("E",))],
            (),
            "INVALID_COMPONENT_SHAPE",
        ),
    ],
    ids=[
        "standalone-l1",
        "same-axis",
        "terminal-on-l1",
        "duplicate-layer",
        "unknown-type",
        "unknown-layer",
        "turning-bridge",
    ],
)
def test_adapter_fails_closed_on_invalid_selected_states(
    routes: list[dict[str, Any]],
    terminal_cells: tuple[tuple[int, int], ...],
    error_code: str,
) -> None:
    with pytest.raises(RouteAdapterError) as exc_info:
        adapt_extracted_routes(routes, terminal_cells=terminal_cells)
    assert exc_info.value.code == error_code


def test_adapter_rejects_type_flow_use_and_commodity_mismatches() -> None:
    type_mismatch = _route(0, 0, layer=0, component_type="belt", flow_in=("E",), flow_out=("W",))
    type_mismatch["type"] = "splitter"
    with pytest.raises(RouteAdapterError) as exc_info:
        adapt_extracted_routes([type_mismatch])
    assert exc_info.value.code == "TYPE_MISMATCH"

    use_mismatch = _route(0, 0, layer=0, component_type="belt", flow_in=("E",), flow_out=("W",))
    use_mismatch["uses"][0]["flow_out"] = ["N"]
    with pytest.raises(RouteAdapterError) as exc_info:
        adapt_extracted_routes([use_mismatch])
    assert exc_info.value.code == "USES_MISMATCH"

    duplicate_commodity = _route(
        0,
        0,
        layer=0,
        component_type="belt",
        flow_in=("E",),
        flow_out=("W",),
        commodities=("same", "same"),
    )
    with pytest.raises(RouteAdapterError) as exc_info:
        adapt_extracted_routes([duplicate_commodity])
    assert exc_info.value.code == "INVALID_COMMODITIES"


def test_l1_support_contract_selects_only_perpendicular_ground_straights() -> None:
    horizontal_east = (5, 6, 0, ("E",), ("W",), "belt")
    horizontal_west = (5, 6, 0, ("W",), ("E",), "belt")
    vertical_ground = (5, 6, 0, ("N",), ("S",), "belt")
    ground_turn = (5, 6, 0, ("E",), ("N",), "belt")
    vertical_l1 = (5, 6, 1, ("N",), ("S",), "bridge")

    contract = build_l1_support_contract(
        [horizontal_east, horizontal_west, vertical_ground, ground_turn, vertical_l1]
    )

    assert len(contract) == 1
    assert contract[0].elevated_key == vertical_l1
    assert contract[0].compatible_ground_keys == (horizontal_east, horizontal_west)
    assert contract[0].forbidden_at_terminal is False

    terminal_contract = build_l1_support_contract(
        [horizontal_east, vertical_l1],
        terminal_cells={(5, 6)},
    )
    assert terminal_contract[0].compatible_ground_keys == ()
    assert terminal_contract[0].forbidden_at_terminal is True


def test_cp_sat_helper_reifies_l1_support_and_terminal_prohibition() -> None:
    cp_model = pytest.importorskip("ortools.sat.python.cp_model")
    horizontal = (5, 6, 0, ("E",), ("W",), "belt")
    vertical_l1 = (5, 6, 1, ("N",), ("S",), "bridge")

    unsupported_model = cp_model.CpModel()
    unsupported_vars = {
        horizontal: unsupported_model.NewBoolVar("horizontal"),
        vertical_l1: unsupported_model.NewBoolVar("vertical_l1"),
    }
    add_l1_support_constraints(unsupported_model, unsupported_vars)
    unsupported_model.Add(unsupported_vars[vertical_l1] == 1)
    unsupported_model.Add(unsupported_vars[horizontal] == 0)
    assert cp_model.CpSolver().Solve(unsupported_model) == cp_model.INFEASIBLE

    supported_model = cp_model.CpModel()
    supported_vars = {
        horizontal: supported_model.NewBoolVar("horizontal"),
        vertical_l1: supported_model.NewBoolVar("vertical_l1"),
    }
    add_l1_support_constraints(supported_model, supported_vars)
    supported_model.Add(supported_vars[vertical_l1] == 1)
    supported_model.Add(supported_vars[horizontal] == 1)
    assert cp_model.CpSolver().Solve(supported_model) in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    terminal_model = cp_model.CpModel()
    terminal_vars = {
        horizontal: terminal_model.NewBoolVar("horizontal"),
        vertical_l1: terminal_model.NewBoolVar("vertical_l1"),
    }
    add_l1_support_constraints(terminal_model, terminal_vars, terminal_cells={(5, 6)})
    terminal_model.Add(terminal_vars[vertical_l1] == 1)
    assert cp_model.CpSolver().Solve(terminal_model) == cp_model.INFEASIBLE
