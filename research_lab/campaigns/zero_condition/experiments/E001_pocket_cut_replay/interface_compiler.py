"""Research-only compilation of cheap fixed-layout routing facts into binding.

This module is intentionally campaign-local.  It separates three interface
questions that the historical pipeline had bundled into routing precheck:

1. static port-domain viability (implemented by ``PortBindingModel`` when a
   ``RoutingBindingContext`` is supplied),
2. duplicate terminal-key exclusion, and
3. free-space component support for selected commodity terminals.

It is not a production lowering and grants no certified effect.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
from typing import Any, Iterable, Mapping


def json_safe(value: Any) -> Any:
    """Return a JSON-compatible projection without writing anything."""
    import json

    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            default=str,
        )
    )


def build_routing_context(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, list[dict[str, Any]]],
    ghost_cells: Iterable[tuple[int, int]] = (),
) -> dict[str, Any]:
    """Build the fixed occupancy, free components, and binding context once."""
    from src.models.routing_binding_context import RoutingBindingContext
    from src.models.routing_subproblem import RoutingPlacementCore
    from src.search.pr2_l0_fixed_witness_core import _extract_pose_resolved_occupancy

    owners, occupied = _extract_pose_resolved_occupancy(
        solution=solution,
        facility_pools=facility_pools,
        ghost_cells=list(ghost_cells),
    )
    placement_core = RoutingPlacementCore.from_occupied_cells(
        occupied,
        occupied_owner_by_cell=owners,
    )
    context = RoutingBindingContext(
        grid_width=70,
        grid_height=70,
        occupied_cells=frozenset(occupied),
        component_by_cell=dict(placement_core.component_by_cell),
        cells_by_component={
            int(component): set(cells)
            for component, cells in placement_core.cells_by_component.items()
        },
        occupied_owner_by_cell=dict(owners),
    )
    component_sizes = sorted(
        (len(cells) for cells in placement_core.cells_by_component.values()),
        reverse=True,
    )
    return {
        "occupied_owner_by_cell": dict(owners),
        "occupied_cells": set(occupied),
        "placement_core": placement_core,
        "routing_context": context,
        "summary": {
            "occupied_cell_count": len(occupied),
            "free_cell_count": len(placement_core.free_cells),
            "free_component_count": len(placement_core.cells_by_component),
            "component_sizes": component_sizes,
            "largest_free_component": component_sizes[0] if component_sizes else 0,
        },
    }


def _exact_or(model: Any, name: str, literals: list[Any], *, fixed: bool) -> Any:
    variable = model.NewBoolVar(name)
    unique = {int(literal.Index()): literal for literal in literals}
    ordered = [unique[index] for index in sorted(unique)]
    if fixed:
        model.Add(variable == 1)
    elif not ordered:
        model.Add(variable == 0)
    else:
        for literal in ordered:
            model.AddImplication(literal, variable)
        model.AddBoolOr(ordered).OnlyEnforceIf(variable)
    return variable


def compile_interface_constraints(
    *,
    binding_model: Any,
    routing_context: Any,
    required_generic_inputs: Mapping[str, Any],
    enforce_duplicate_keys: bool,
    enforce_component_support: bool,
    enabled_component_commodities: set[str] | None = None,
) -> dict[str, Any]:
    """Compile selected interface families into an already-built binding model.

    ``PortBindingModel`` has already performed static front filtering before this
    function is called.  The two booleans permit an ordered attribution ladder:

    port-domain only -> + duplicate terminal keys -> + component support.
    """
    from src.models.port_binding import (
        is_routing_visible_output_commodity,
        routing_free_sink_commodities_from_generic_inputs,
    )
    from src.models.routing_subproblem import DIR_OPP

    routing_free = routing_free_sink_commodities_from_generic_inputs(
        required_generic_inputs
    )
    contribution_table: dict[tuple[str, str, int], dict[str, Any]] = defaultdict(
        lambda: {"fixed": False, "literals": {}}
    )
    duplicate_table: dict[
        tuple[int, int, str, str, str], dict[str, Any]
    ] = defaultdict(lambda: {"fixed_count": 0, "literals": {}})
    contribution_occurrences = 0

    def add_contribution(
        *,
        commodity: str,
        side: str,
        component: int,
        literal: Any | None,
    ) -> None:
        row = contribution_table[(commodity, side, component)]
        if literal is None:
            row["fixed"] = True
        else:
            row["literals"][int(literal.Index())] = literal

    def add_duplicate(
        *,
        key: tuple[int, int, str, str, str],
        literal: Any | None,
    ) -> None:
        row = duplicate_table[key]
        if literal is None:
            row["fixed_count"] += 1
            return
        index = int(literal.Index())
        literal_row = row["literals"].setdefault(
            index,
            {"literal": literal, "count": 0},
        )
        literal_row["count"] += 1

    def record_port(port: Mapping[str, Any], side: str, literal: Any | None) -> None:
        nonlocal contribution_occurrences
        commodity = str(port["commodity"])
        if side == "out" and not is_routing_visible_output_commodity(
            commodity,
            routing_free,
        ):
            return
        cell = (int(port["x"]), int(port["y"]))
        component = routing_context.component_by_cell.get(cell)
        if component is None or cell in routing_context.occupied_cells:
            raise RuntimeError(f"front-filtered model retained unusable port {cell}")
        add_contribution(
            commodity=commodity,
            side=side,
            component=int(component),
            literal=literal,
        )
        duplicate_key = (
            cell[0],
            cell[1],
            str(DIR_OPP[str(port["dir"])]),
            commodity,
            side,
        )
        add_duplicate(key=duplicate_key, literal=literal)
        contribution_occurrences += 1

    for instance_id, domain in sorted(binding_model.binding_domains.items()):
        variables = binding_model.binding_vars.get(instance_id)
        if variables is None:
            selected = int(binding_model.fixed_binding_choice[instance_id])
            option = domain[selected]
            for port in option.get("input_ports", []):
                record_port(port, "in", None)
            for port in option.get("output_ports", []):
                record_port(port, "out", None)
            continue
        for index, option in enumerate(domain):
            literal = variables[index]
            for port in option.get("input_ports", []):
                record_port(port, "in", literal)
            for port in option.get("output_ports", []):
                record_port(port, "out", literal)

    for slots, variables_by_slot, side in (
        (binding_model.generic_input_slots, binding_model.generic_input_vars, "in"),
        (binding_model.generic_output_slots, binding_model.generic_output_vars, "out"),
    ):
        for slot in slots:
            slot_id = str(slot["slot_id"])
            for commodity, literal in variables_by_slot[slot_id].items():
                if str(commodity) == "__unused__":
                    continue
                record_port(
                    {
                        "x": int(slot["x"]),
                        "y": int(slot["y"]),
                        "dir": str(slot["dir"]),
                        "commodity": str(commodity),
                    },
                    side,
                    literal,
                )

    model = binding_model.model
    duplicate_constraints = 0
    duplicate_forbidden_literals = 0
    duplicate_fixed_contradictions = 0
    duplicate_multi_literal_options = 0
    if enforce_duplicate_keys:
        for key, row in sorted(duplicate_table.items()):
            fixed_count = int(row["fixed_count"])
            literal_rows = row["literals"]
            if fixed_count > 1:
                suffix = hashlib.sha256(repr(key).encode("utf-8")).hexdigest()[:16]
                contradiction = model.NewBoolVar(f"dup_fixed_contradiction_{suffix}")
                model.Add(contradiction == 0)
                model.Add(contradiction == 1)
                duplicate_fixed_contradictions += 1
                duplicate_constraints += 2
                continue
            allowed_literals: list[Any] = []
            for index in sorted(literal_rows):
                literal = literal_rows[index]["literal"]
                multiplicity = int(literal_rows[index]["count"])
                if fixed_count == 1 or multiplicity > 1:
                    model.Add(literal == 0)
                    duplicate_forbidden_literals += 1
                    duplicate_constraints += 1
                    if multiplicity > 1:
                        duplicate_multi_literal_options += 1
                else:
                    allowed_literals.append(literal)
            if fixed_count == 0 and len(allowed_literals) > 1:
                model.AddAtMostOne(allowed_literals)
                duplicate_constraints += 1

    by_commodity: dict[str, set[int]] = defaultdict(set)
    for commodity, _side, component in contribution_table:
        by_commodity[commodity].add(int(component))
    if enabled_component_commodities is None:
        component_commodities = set(by_commodity)
    else:
        component_commodities = {
            str(commodity)
            for commodity in enabled_component_commodities
            if str(commodity) in by_commodity
        }

    component_presence_variables = 0
    component_union_variables = 0
    global_presence_variables = 0
    component_rule_constraints = 0
    if enforce_component_support:
        for commodity in sorted(component_commodities):
            components = sorted(by_commodity[commodity])
            source_presence: list[Any] = []
            sink_presence: list[Any] = []
            union_presence: list[Any] = []
            for component in components:
                source_row = contribution_table[(commodity, "out", component)]
                sink_row = contribution_table[(commodity, "in", component)]
                source = _exact_or(
                    model,
                    f"cmp_src_{commodity}_{component}",
                    list(source_row["literals"].values()),
                    fixed=bool(source_row["fixed"]),
                )
                sink = _exact_or(
                    model,
                    f"cmp_sink_{commodity}_{component}",
                    list(sink_row["literals"].values()),
                    fixed=bool(sink_row["fixed"]),
                )
                source_presence.append(source)
                sink_presence.append(sink)
                union = _exact_or(
                    model,
                    f"cmp_union_{commodity}_{component}",
                    [source, sink],
                    fixed=False,
                )
                union_presence.append(union)
                component_presence_variables += 2
                component_union_variables += 1

            source_global = _exact_or(
                model,
                f"global_src_{commodity}",
                source_presence,
                fixed=False,
            )
            sink_global = _exact_or(
                model,
                f"global_sink_{commodity}",
                sink_presence,
                fixed=False,
            )
            both_global = model.NewBoolVar(f"global_both_{commodity}")
            model.Add(both_global <= source_global)
            model.Add(both_global <= sink_global)
            model.Add(both_global >= source_global + sink_global - 1)
            global_presence_variables += 3
            component_rule_constraints += 3

            for source, sink in zip(source_presence, sink_presence, strict=True):
                model.Add(source == sink).OnlyEnforceIf(both_global)
                component_rule_constraints += 1
            model.Add(sum(union_presence) <= 1).OnlyEnforceIf(both_global.Not())
            component_rule_constraints += 1

    proto = model.Proto()
    serialize = getattr(proto, "SerializeToString", None)
    if callable(serialize):
        proto_bytes = serialize()
    else:
        proto_bytes = str(proto).encode("utf-8")
    return {
        "static_port_filter": json_safe(binding_model.routing_aware_filter_stats),
        "empty_filtered_domain_count": len(binding_model.empty_binding_domain_instances),
        "empty_filtered_domains": json_safe(binding_model.empty_binding_domain_instances),
        "filtered_binding_instance_count": len(binding_model.binding_domains),
        "filtered_binding_option_count": sum(
            len(domain) for domain in binding_model.binding_domains.values()
        ),
        "generic_input_slot_count": len(binding_model.generic_input_slots),
        "generic_output_slot_count": len(binding_model.generic_output_slots),
        "commodity_count": len(by_commodity),
        "commodity_components": {
            commodity: sorted(components)
            for commodity, components in sorted(by_commodity.items())
        },
        "component_commodities_enabled": sorted(component_commodities),
        "contribution_key_count": len(contribution_table),
        "contribution_occurrences": contribution_occurrences,
        "duplicate_keys_observed": len(duplicate_table),
        "duplicate_constraints_enabled": bool(enforce_duplicate_keys),
        "duplicate_constraints": duplicate_constraints,
        "duplicate_forbidden_literals": duplicate_forbidden_literals,
        "duplicate_fixed_contradictions": duplicate_fixed_contradictions,
        "duplicate_multi_literal_options": duplicate_multi_literal_options,
        "component_support_enabled": bool(enforce_component_support),
        "component_presence_variable_count": component_presence_variables,
        "component_union_variable_count": component_union_variables,
        "global_presence_variable_count": global_presence_variables,
        "component_rule_constraint_count": component_rule_constraints,
        "model_variable_count": len(proto.variables),
        "model_constraint_count": len(proto.constraints),
        "model_proto_sha256": hashlib.sha256(proto_bytes).hexdigest(),
    }
