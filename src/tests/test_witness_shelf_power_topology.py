from __future__ import annotations

import importlib


geometry = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.geometry"
)
router = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.network_router"
)
shelf = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.shelf_constructor"
)
solver = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.solve_shelf_power"
)


def _packed_row(
    x0: int, y: int, width: int, height: int, count: int
) -> list[frozenset[tuple[int, int]]]:
    return [
        geometry.Rect(x0 + index * width, y, width, height).cells
        for index in range(count)
    ]


def test_routing_aware_network_has_exact_core_bypass_and_is_scc() -> None:
    edges = shelf.routing_aware_network_edges()
    cells = router.network_cells(edges)

    assert len(edges) == 1169
    assert len(cells) == 1154
    router.assert_strongly_connected(edges)
    assert {
        ((x, y), (x, y - 1))
        for x in (2, 12)
        for y in range(63, 52, -1)
    } <= edges
    assert {((x, 58), (x + 1, 58)) for x in range(12, 69)} <= edges
    assert not {((x, 58), (x + 1, 58)) for x in range(1, 12)} & edges
    assert {((x, 52), (x + 1, 52)) for x in range(2, 69)} <= edges
    assert ((1, 53), (2, 53)) in edges
    assert ((2, 53), (2, 52)) in edges


def test_upper_core_body_is_clear_and_all_fixed_terminals_attach() -> None:
    bundle, _ = shelf.strict_contract.load_and_reconcile()
    instance = bundle.strict_instance.value
    edges = shelf.routing_aware_network_edges()
    network_cells = set(router.network_cells(edges))
    core_mode = solver._strict_mode(instance, "protocol_core", "inputs_north_south")
    core = geometry.strict_mode_geometry(core_mode, shelf.FIXED_CORE_ANCHOR)

    assert shelf.FIXED_CORE_ANCHOR == (3, 53)
    assert len(core.body_cells) == 81
    assert not (core.body_cells & network_cells)
    fixed = solver._fixed_terminal_attachments(instance, network_cells)
    assert len(fixed) == 54
    assert all(cell in network_cells for cell, _kind, _direction in fixed)


def test_interleaved_topology_needs_no_ew_mini_shelf_exception() -> None:
    assert solver.MINI_EW_MODE_BY_ANCHOR == {}


def test_protected_rectangle_keeps_exact_body_free_baseline() -> None:
    network_cells = set(router.network_cells(shelf.routing_aware_network_edges()))
    protected = shelf.SHELF_PROTECTED_RECT

    assert protected == geometry.Rect(2, 34, 7, 6)
    assert len(protected.cells) == 42
    assert len(protected.cells & network_cells) == 7
    assert len(protected.cells - network_cells) == 35


def test_static_template_capacity_closes_exactly_before_poles() -> None:
    network_cells = set(router.network_cells(shelf.routing_aware_network_edges()))
    fixed = geometry.Rect(*shelf.FIXED_CORE_ANCHOR, 9, 9).cells
    three_rows = [
        *[
            geometry.Rect(3 + 3 * index, y, 3, 3).cells
            for y in (2, 11, 21, 30, 40, 49)
            for index in range(22)
        ],
    ]
    five_rows = [
        *_packed_row(3, 15, 5, 5, 13),
        *_packed_row(9, 34, 5, 5, 12),
        *_packed_row(13, 53, 5, 5, 11),
        *_packed_row(3, 64, 5, 5, 13),
    ]
    six_rows = [
        *_packed_row(3, 6, 6, 4, 11),
        *_packed_row(3, 25, 6, 4, 11),
        *_packed_row(3, 44, 6, 4, 11),
        *_packed_row(15, 59, 6, 4, 9),
    ]

    assert (len(three_rows), len(five_rows), len(six_rows)) == (132, 49, 42)
    for bodies in (three_rows, five_rows, six_rows):
        union = set().union(*bodies)
        assert sum(map(len, bodies)) == len(union)
        assert not (union & network_cells)
        assert not (union & fixed)
        assert not (union & shelf.SHELF_PROTECTED_RECT.cells)


def test_solver_model_has_collapsed_domains_and_static_component_audit() -> None:
    state = solver.build_shelf_power_model()

    assert state.stats.network_edges == 1169
    assert state.stats.network_cells == 1154
    assert state.stats.geometry_pose_count == 859
    assert state.stats.group_pose_var_count == 859
    assert len(state.group_vars) == len(state.occupancy_vars) == 859
    assert state.stats.pole_var_count == 2533
    assert state.stats.pole_domain_mode == "full"
    assert state.stats.component_allowed_row_count == 48
    assert state.stats.component_table_constraint_count == 0
    assert state.stats.component_presence_var_count == 0
    assert state.stats.component_static_audit_cell_count == 981
    assert state.stats.component_static_audit_state_count == 3512
    assert state.stats.fixed_terminal_count == 54
    assert state.stats.fixed_power_constraint_count == 0
    assert all(
        state.stats.group_domain_sizes[group["id"]] == 389
        for group in state.groups
        if group["template"] == "manufacturing_3x3"
    )
    assert all(
        state.stats.group_domain_sizes[group["id"]] == 234
        for group in state.groups
        if group["template"] == "manufacturing_5x5"
    )
    assert all(
        state.stats.group_domain_sizes[group["id"]] == 236
        for group in state.groups
        if group["template"] == "manufacturing_6x4"
    )


def test_template_collapse_rejects_signature_domain_drift() -> None:
    groups = (
        {"id": "a", "template": "manufacturing_3x3", "count": 100},
        {"id": "b", "template": "manufacturing_3x3", "count": 32},
        {"id": "c", "template": "manufacturing_5x5", "count": 49},
        {"id": "d", "template": "manufacturing_6x4", "count": 38},
    )
    domains = {"a": (1, 2), "b": (1, 3), "c": (4,), "d": (5,)}

    try:
        solver._collapse_template_domains(groups, domains)
    except shelf.ShelfConstructionError as exc:
        assert exc.code == "SIGNATURE_DOMAIN_MISMATCH"
    else:
        raise AssertionError("signature domain drift must fail closed")
